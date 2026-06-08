#!/usr/bin/env python3
# cross_sma_btc.py — 5/20 SMA crossover backtest on BTC/USDT (Binance spot)
#
# A 股 ma_cross_yyt.py 的 crypto 镜像版。差异:
#   - 数据源: ccxt (Binance 公开 API, 无需 API key)
#   - 交易规则: 24/7 + T+0 + 无涨跌停 + 无 ST, 全部 A 股 guards 禁用
#   - 佣金: 0.1% 单边 (Binance spot 默认), A 股是 0.025%/0.076% 非对称
#   - 价差: 0.05% (5 bp) 适合 BTC/USDT 主流币, A 股中小板 0.1% 偏紧
#
# 学习目的。**crypto 比 A 股波动更剧烈, 7×24, 策略失灵可能瞬间爆仓**。
# 跑 dry-run / testnet 至少 1-2 周再考虑实盘。
#
# Usage (会自动用当前 Python 解释器，建议 venv):
#   python cross_sma_btc.py
#   python cross_sma_btc.py --symbol ETH/USDT --timeframe 4h
#   python cross_sma_btc.py --exchange bybit --start 20220101
#
# Outputs (created under quant/):
#   - data/btc.csv       : cached daily OHLCV (gitignored, regenerable)
#   - output/backtest_btc.html : equity curve + trade markers (interactive)

import os
import sys
from pathlib import Path

import ccxt
import pandas as pd
from backtesting import Backtest
from backtesting.lib import crossover

# 复用 A 股脚本的 SmaCross (把 limit_pct 改 0 禁用涨跌停检测,
# crypto 24/7 连续交易无涨跌停)
from ma_cross_yyt import SmaCross, _detect_limit_bar
SmaCross.limit_pct = 0  # 0% 阈值 = 永不触发一字板 (crypto 没有涨跌停)

# 自动定位脚本所在目录
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
OUTPUT_DIR = SCRIPT_DIR / "output"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

EXCHANGE = os.environ.get("EXCHANGE", "gate")
SYMBOL = os.environ.get("SYMBOL", "BTC/USDT")
TIMEFRAME = os.environ.get("TIMEFRAME", "1d")  # 1d/4h/1h
START = os.environ.get("START", "20200101")
END = os.environ.get("END", "20260605")

# Fallback 链: macOS 上 Binance/OKX/Bybit/KuCoin/Bitget 都 timeout,
# Gate.io 当前可达。脚本会按顺序试, 第一个能 load_markets() 的就用。
EXCHANGE_FALLBACKS = ["gate", "binance", "okx", "bybit", "kucoin"]

# 限频: ccxt 默认 1000 根/请求, BTC 日线 6 年 ≈ 2200 根需要分页
CCXT_LIMIT = 1000
REQUIRED_COLUMNS = ["Open", "Close", "High", "Low"]

# Crypto 滑点/价差: BTC/USDT 主流币流动性好, 5 bp (0.05%) 偏保守
# 山寨币 0.1% 起, MEME 0.5%+
SPREAD = float(os.environ.get("SPREAD", "0.0005"))


def crypto_commission(size, price):
    """Crypto 交易成本: Binance spot 默认 0.1% 单边。
    backtesting.py 调用约定: commission(size, price), size 正=买/负=卖。
    注: 大多数交易所按成交额收, 不按方向区别 (不像 A 股有印花税)。
    """
    return abs(size) * price * 0.001


def _make_exchange(name: str):
    """工厂: 按名字建 ccxt 交易所实例 (默认 public, 无需 API key)。
    注: macOS + 当前网络下 Binance/OKX/Bybit 普遍 timeout, 推荐 Gate.io。
    """
    cls = getattr(ccxt, name, None)
    if cls is None:
        raise ValueError(f"ccxt 不支持的交易所: {name}, 常见: binance/okx/bybit/kucoin/gate")
    return cls({"enableRateLimit": True})


def _make_exchange_with_fallback(preferred: str = EXCHANGE):
    """按 EXCHANGE_FALLBACKS 顺序逐个试, 第一个 load_markets 成功的就用。
    macOS 上经常有 1-2 个交易所 timeout, 这个 helper 让你跑一次脚本就能拿到数据。
    """
    tried = []
    for name in [preferred] + [e for e in EXCHANGE_FALLBACKS if e != preferred]:
        try:
            ex = _make_exchange(name)
            ex.load_markets()
            if name != preferred:
                print(f"⚠ {preferred} 不可达, 改用 {name}")
            return ex
        except Exception as e:
            tried.append(f"{name}({type(e).__name__})")
    raise RuntimeError(
        f"所有 ccxt 交易所都不可达: {tried}. "
        f"检查网络 / 防火墙, 或 5 分钟后再试。"
    )


def fetch_data() -> pd.DataFrame:
    """从 ccxt 拉 OHLCV, 按 START/END 过滤, 缓存到 data/{symbol}.csv。
    分页: ccxt 默认 1000 根/请求, 用 'since' cursor 翻页。
    """
    safe_name = SYMBOL.replace("/", "_")
    cache = DATA_DIR / f"{safe_name}_{EXCHANGE}_{TIMEFRAME}.csv"
    if cache.exists():
        print(f"✓ loading cached data from {cache}")
        df = pd.read_csv(cache, parse_dates=["date"], index_col="date")
    else:
        print(f"→ fetching {SYMBOL} from {EXCHANGE} ({TIMEFRAME}, {START} → {END})...")
        ex = _make_exchange_with_fallback(EXCHANGE)
        start_ms = pd.Timestamp(START).timestamp() * 1000
        end_ms = pd.Timestamp(END).timestamp() * 1000

        rows = []
        since = int(start_ms)
        while since < end_ms:
            batch = ex.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME,
                                   since=since, limit=CCXT_LIMIT)
            if not batch:
                break
            rows.extend(batch)
            # 下一批从最后根的 open time + 1ms 开始
            since = batch[-1][0] + 1
            print(f"  ... {len(rows)} bars so far, last={pd.Timestamp(batch[-1][0], unit='ms').date()}")

        df = pd.DataFrame(rows, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("date").sort_index()
        # 裁到 [START, END]
        df = df[(df.index >= pd.Timestamp(START)) & (df.index <= pd.Timestamp(END))]
        df = df.drop(columns=["timestamp"])
        df["Amount"] = df["Close"] * df["Volume"]  # 合成成交额, 跟 A 股脚本统一列名
        df.to_csv(cache)
        print(f"✓ saved {len(df)} rows to {cache}")
    return _validate_columns(df)


def _validate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """跟 A 股脚本一致: cache 加载时校验 OHLCV 齐全。"""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"data missing required columns: {missing}. "
            f"got: {list(df.columns)}. "
            f"delete cache and re-run to refetch from source."
        )
    return df


def run_backtest(df: pd.DataFrame, cash: float = 10_000, spread: float = SPREAD) -> None:
    """跑回测 + 出图。初始 1 万 USDT (crypto 常见起点, 比 A 股 10 万 CNY 少 10x)。"""
    bt = Backtest(
        df,
        SmaCross,
        cash=cash,
        commission=crypto_commission,  # crypto: 0.1% 对称
        spread=spread,                  # 0.05% (5 bp) BTC/USDT 主流
        exclusive_orders=True,
    )
    print("\n=== running backtest ===")
    stats = bt.run()
    print(stats)

    out = OUTPUT_DIR / f"backtest_{EXCHANGE}_{SYMBOL.replace('/', '_')}_{TIMEFRAME}.html"
    bt.plot(filename=str(out), open_browser=False)
    print(f"\n✓ equity curve + trades chart → {out}")


def _parse_args():
    """CLI: 不传则用脚本顶部 env/defaults, 向后兼容。"""
    import argparse
    p = argparse.ArgumentParser(
        description="Crypto SMA 5/20 金叉死叉回测 (ccxt + backtesting.py)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--exchange", default=EXCHANGE,
                   help="ccxt 交易所名 (binance/okx/bybit/kucoin)")
    p.add_argument("--symbol", default=SYMBOL,
                   help="交易对, e.g. BTC/USDT, ETH/USDT, SOL/USDT")
    p.add_argument("--timeframe", default=TIMEFRAME,
                   help="K线周期: 1m/5m/15m/1h/4h/1d/1w")
    p.add_argument("--start", default=START, help="起始 YYYYMMDD")
    p.add_argument("--end", default=END, help="结束 YYYYMMDD")
    p.add_argument("--cash", type=float, default=10_000, help="初始资金 (USDT)")
    p.add_argument("--spread", type=float, default=SPREAD,
                   help="bid-ask 价差, 0.0005=BTC/USDT, 0.001 山寨, 0.005 MEME")
    return p.parse_args()


def main():
    global EXCHANGE, SYMBOL, TIMEFRAME, START, END, SPREAD
    args = _parse_args()
    EXCHANGE, SYMBOL, TIMEFRAME = args.exchange, args.symbol, args.timeframe
    START, END = args.start, args.end
    SPREAD = args.spread

    try:
        df = fetch_data()
    except Exception as e:
        print(f"❌ data fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
        print("   可能是网络问题 / 交易所限频 / 交易对不存在。", file=sys.stderr)
        print("   隔几分钟重试, 或换 --exchange bybit 试试。", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== data summary: {len(df)} bars, "
          f"{df.index.min().date()} → {df.index.max().date()} ===")
    print(f"   price range: {df['Close'].min():.2f} ~ {df['Close'].max():.2f}")
    print(f"   latest close: {df['Close'].iloc[-1]:.2f}")
    print(f"   {EXCHANGE} {SYMBOL} {TIMEFRAME} spread={args.spread}")

    run_backtest(df, cash=args.cash, spread=args.spread)


if __name__ == "__main__":
    main()
