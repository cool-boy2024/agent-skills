#!/usr/bin/env python3
# ma_cross_yyt.py — 5/20 SMA crossover backtest on 002183 怡亚通
#
# Learning purpose only. The author of this script is not a financial advisor.
# DO NOT trade real money based on results from this script. The strategy
# (5/20 SMA crossover) is a well-known textbook strategy that is known to
# underperform buy-and-hold in trending markets and trigger many false signals
# in choppy markets. Run this to learn the backtesting.py framework, not to
# find alpha.
#
# Usage (会自动用当前 Python 解释器，建议 venv):
#   python ma_cross_yyt.py
#
# Outputs (created under quant/):
#   - data/yiyatong.csv    : cached daily K-line (gitignored, regenerable)
#   - output/backtest_yyt.html : equity curve + trade markers (interactive)
#
# Known caveats (FIXED):
#   - A 股非对称佣金：买 0.025% (单边), 卖 0.076% (佣金 + 印花税 0.05% + 过户费 0.001%)
#   - Cache 列校验：cache 加载时检查 Open/Close/High/Low 齐全
#   - T+1 结算：next() 顶部加 entry_bar 守门 (backtesting.py 默认 next-bar
#     成交已是 1 bar = 1 个交易日的延迟, 守门是显式保险 + 防 trade_on_close=True 改坏)
#   - 涨跌停：一字板 (High==Low 且 |change|/prev_close ≈ limit_pct) 当日
#     跳过信号, 避免一字板次日开盘价 ≠ 今日收盘价导致的 fake-perfect-fill
#   - ST/*ST 识别: fetch_data() 调 ak.stock_info_a_code_name() 校验名称,
#     含 ST/*ST 立即 raise, 提示用户改 SmaCross.limit_pct=0.05
#   - 滑点: backtesting.py 0.6.x 无 slippage, 用 spread=SPREAD (默认 0.001=10bp)
#     建模 bid-ask 价差 = 双向滑点; 可 env SPREAD 覆盖 (蓝筹 0.0005, ST 0.002)
#   - 复权方式: ADJUST 默认 "qfq" (前复权, 跟看盘软件一致), env ADJUST=hfq
#     切后复权 (适合跨标的横向比较绝对涨幅), env ADJUST=none 切不复权
#
# Known caveats (TODO for the user to learn next):  (全部 FIXED, 见上)

import os
import sys
from pathlib import Path

import akshare as ak
import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

# 自动定位脚本所在目录（不依赖硬编码 venv 路径）
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
OUTPUT_DIR = SCRIPT_DIR / "output"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

CACHE = DATA_DIR / "yiyatong.csv"
SYMBOL = "002183"
START = "20200101"
END = "20260605"

# 复权方式: "qfq" 前复权 (默认, 跟看盘软件一致, 历史价格按当前股本调整)
#           "hfq" 后复权 (历史价格不变, 适合多标的横向比较绝对涨幅)
#           "不复权" None (原始价格, 适合回测分红/配股事件本身)
# 改用 env: ADJUST=hfq python ma_cross_yyt.py
ADJUST = os.environ.get("ADJUST", "qfq")
if ADJUST.lower() in ("none", "null", "raw", ""):
    ADJUST = None

REQUIRED_COLUMNS = ["Open", "Close", "High", "Low"]

# A 股滑点/价差建模: backtesting.py 0.6.x 没有 slippage 参数,
# 但有 spread (bid-ask 价差) — 买按 ask 价 (price*(1+spread/2)) 成交,
# 卖按 bid 价 (price*(1-spread/2)) 成交, 等效于双向滑点。
# 0.1% (10 bp) 适合中小板 (002xxx) 流动性, 蓝筹 (600xxx) 建议 0.0005 (5 bp),
# ST/低流动性建议 0.002 (20 bp)。可通过环境变量 SPREAD 覆盖。
SPREAD = float(os.environ.get("SPREAD", "0.001"))


def a_share_commission(size, price):
    """A 股非对称交易成本：
    - 买: 0.025% 佣金 (最低 5 元，简化：忽略最低收费)
    - 卖: 0.025% 佣金 + 0.05% 印花税 + 0.001% 过户费 = 0.076%

    backtesting.py 的 commission 函数返回**金额**（不是比率）。
    调用约定: commission(size, price)，size 正数=买，负数=卖。
    """
    gross = abs(size) * price
    if size > 0:  # 买
        return gross * 0.00025
    else:  # 卖
        return gross * 0.00076


def _detect_limit_bar(close, high, low, limit_pct, tolerance=0.005):
    """检测一字板 (涨跌停封板) bar。

    判定条件 (2 个必须同时满足):
    1. High == Low (全日成交价 = 同一价, 没有波动)
    2. |当日 change| / prev_close ≈ limit_pct (幅度到涨跌停)
       tolerance=0.005 (0.5%) 容许小幅计算误差 (复权 / 真实幅度 9.97% 等)

    返回: pd.Series[bool]，True 表示该 bar 是一字板。
    """
    prev_close = close.shift(1)
    change = (close - prev_close) / prev_close
    at_limit = (change.abs() - limit_pct).abs() < tolerance
    no_range = (high == low)
    return (at_limit & no_range).fillna(False)


class SmaCross(Strategy):
    """经典 5/20 SMA 金叉死叉策略。"""
    n1 = 5              # 快线周期
    n2 = 20             # 慢线周期
    limit_pct = 0.10    # 涨跌停幅度 (主板 10%, 创业板/科创板 20%, ST 5%)

    def init(self):
        # self.data.Close 是 backtesting.py 的 _Array (numpy view)，
        # 没有 .rolling()，必须先转成 pd.Series
        close = pd.Series(self.data.Close)
        self.sma1 = self.I(lambda: close.rolling(self.n1).mean(), name="SMA5")
        self.sma2 = self.I(lambda: close.rolling(self.n2).mean(), name="SMA20")
        # T+1 守门: 记录上次开仓的 bar index
        # (backtesting.py 0.6.x 的 Position 对象没有 entry_bar, 自己存)
        self._entry_bar = -1
        # 涨跌停 (一字板) 检测: High==Low 且 |change|/prev_close ≈ limit_pct
        # 一字板日是 fake-perfect-fill 重灾区 — backtesting.py 默认假设
        # next open = today close, 但一字板次日往往一字开盘 (≠ 今日 close)
        self._is_limit = self.I(
            lambda: _detect_limit_bar(close, self.data.High, self.data.Low, self.limit_pct),
            name=f"LimitBar({self.limit_pct:.0%})",
        )

    def next(self):
        # T+1 守门: A 股不允许同日买卖。今天买的要 next bar 才能卖。
        # backtesting.py 默认 trade_on_next_bar_open 已经是 1 bar = 1 个交易日
        # 的延迟, 但加这个显式守门让代码自证, 防谁手贱改成 trade_on_close=True。
        if self.position and len(self.data) - 1 == self._entry_bar:
            return  # 当天开的仓, 等明天才能平
        # 涨跌停守门: 今天一字板 (High==Low 且涨幅 ≈ limit_pct), 不能成交
        if self._is_limit[-1]:
            return
        if crossover(self.sma1, self.sma2):
            self.buy()
            self._entry_bar = len(self.data) - 1  # 记录开仓 bar
        elif crossover(self.sma2, self.sma1):
            self.sell()


def fetch_data() -> pd.DataFrame:
    if CACHE.exists():
        print(f"✓ loading cached data from {CACHE}")
        df = pd.read_csv(CACHE, parse_dates=["date"], index_col="date")
    else:
        # 优先用腾讯源 (push2his.eastmoney.com 在某些网络下 SSL 握手失败)
        print(f"→ fetching {SYMBOL} from akshare via 腾讯源 ({START} → {END})...")
        df = ak.stock_zh_a_hist_tx(
            symbol=f"sz{SYMBOL}",
            start_date=START,
            end_date=END,
            adjust=ADJUST,  # qfq (前复权) / hfq (后复权) / None (不复权)
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df = df.rename(
            columns={
                "open": "Open",
                "close": "Close",
                "high": "High",
                "low": "Low",
                "amount": "Amount",  # 保留成交额方便后续分析
            }
        )
        df["Volume"] = 1   # 腾讯源无 volume；策略不依赖 volume；新手别被这个 1 误导
        df.to_csv(CACHE)
        print(f"✓ saved {len(df)} rows to {CACHE}")
    df = _validate_columns(df)
    _check_st_status(SYMBOL)  # ST/*ST 标的 limit_pct 应改 0.05, 见函数 docstring
    return df


def _validate_columns(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"data missing required columns: {missing}. "
            f"got: {list(df.columns)}. "
            f"delete {CACHE} and re-run to refetch from source."
        )
    return df


def _check_st_status(symbol: str) -> None:
    """校验股票不含 ST/*ST 标记。
    ST/*ST 标的涨跌停 ±5% (非 ±10%), 本脚本 SmaCross.limit_pct=0.10 假设
    会让所有 ±5% 涨跌停都被误判为"一字板"并 skip, 策略会失效。
    修复: 若确认要跑 ST 标的, 改 SmaCross.limit_pct = 0.05。

    实现: 调 ak.stock_info_a_code_name() 拿全 A 股列表, 按 code 过滤
    拿 name, 含 ST/*ST 则 raise。
    """
    try:
        info = ak.stock_info_a_code_name()
    except Exception as e:
        # akshare 接口偶发不稳, 拿不到名称不阻断回测, 只 warn
        print(f"⚠ ST 检查跳过 (ak.stock_info_a_code_name 失败: {e})", file=sys.stderr)
        return
    if info is None or info.empty:
        print(f"⚠ ST 检查跳过 (ak 返回空)", file=sys.stderr)
        return
    # 兼容不同 akshare 版本: 列名可能是 'code'/'symbol', 'name'/'名称'
    code_col = next((c for c in info.columns if c.lower() in ("code", "symbol", "代码")), None)
    name_col = next((c for c in info.columns if c.lower() in ("name", "名称")), None)
    if not code_col or not name_col:
        print(f"⚠ ST 检查跳过 (ak 返回列意外: {list(info.columns)})", file=sys.stderr)
        return
    matched = info[info[code_col].astype(str).str.contains(str(symbol))]
    if matched.empty:
        print(f"⚠ ST 检查跳过 ({symbol} 不在 ak 全 A 股列表)", file=sys.stderr)
        return
    name = str(matched[name_col].iloc[0])
    if "ST" in name.upper():
        raise ValueError(
            f"❌ {symbol} 名称含 ST/*ST: '{name}'。\n"
            f"   ST 标的涨跌停 ±5% (非 ±10%), 本脚本 SmaCross.limit_pct=0.10 会\n"
            f"   误判所有 ±5% 涨跌停为'一字板'并 skip, 策略失效。\n"
            f"   修复: 若确认要跑 ST 标的, 改 SmaCross.limit_pct = 0.05 重跑。"
        )
    print(f"✓ 股票名称: {name} (非 ST/*ST, 校验通过)")


def run_backtest(df: pd.DataFrame) -> None:
    bt = Backtest(
        df,
        SmaCross,
        cash=100_000,
        commission=a_share_commission,  # A 股非对称：买 0.025% / 卖 0.076%
        spread=SPREAD,                   # A 股价差/滑点: 0.1% (中小板默认, 蓝筹可改 0.0005)
        exclusive_orders=True,
    )
    print("\n=== running backtest ===")
    stats = bt.run()
    print(stats)

    out = OUTPUT_DIR / "backtest_yyt.html"
    bt.plot(filename=str(out), open_browser=False)
    print(f"\n✓ equity curve + trades chart → {out}")


def _parse_args():
    """CLI 参数: 不传则用脚本顶部常量默认值, 向后兼容。
    例子: python ma_cross_yyt.py --symbol 600519 --start 20180101 --end 20260605
    """
    import argparse
    p = argparse.ArgumentParser(
        description="A 股 SMA 5/20 金叉死叉回测 (backtesting.py)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--symbol", default=SYMBOL, help="A 股代码 (e.g. 002183, 600519, 300750)")
    p.add_argument("--start", default=START, help="起始日期 YYYYMMDD")
    p.add_argument("--end", default=END, help="结束日期 YYYYMMDD")
    p.add_argument("--cash", type=float, default=100_000, help="初始资金 (CNY)")
    p.add_argument("--spread", type=float, default=SPREAD, help="bid-ask 价差 (滑点), 0.001=10bp")
    p.add_argument("--adjust", default=ADJUST, choices=["qfq", "hfq", "none"],
                   help="复权方式: qfq 前复权 / hfq 后复权 / none 不复权")
    p.add_argument("--skip-st-check", action="store_true",
                   help="跳过 ST/*ST 校验 (跑 ST 标的 + 已手动设 limit_pct=0.05 时用)")
    p.add_argument("--limit-pct", type=float, default=0.10,
                   help="涨跌停幅度: 主板 0.10, 创业板/科创板 0.20, ST 0.05")
    return p.parse_args()


def main():
    args = _parse_args()
    # CLI 参数覆盖模块常量 (用于本次回测)
    global SYMBOL, START, END, CACHE, ADJUST
    SYMBOL, START, END = args.symbol, args.start, args.end
    CACHE = DATA_DIR / f"{SYMBOL}.csv"  # 不同股票独立 cache
    ADJUST = None if args.adjust == "none" else args.adjust
    SmaCross.limit_pct = args.limit_pct

    try:
        df = fetch_data()
    except Exception as e:
        # 带上异常类型 + 类名，方便用户 google
        print(f"❌ data fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
        print("   可能是网络问题 / 符号错 / akshare API 改了字段。", file=sys.stderr)
        print(f"   Cache 在: {CACHE}。删掉重试。", file=sys.stderr)
        sys.exit(1)

    if args.skip_st_check:
        # 把 _check_st_status 替换成 no-op, 跳过 ST 校验
        global _check_st_status
        _check_st_status = lambda symbol: None  # type: ignore

    print(f"\n=== data summary: {len(df)} trading days, "
          f"{df.index.min().date()} → {df.index.max().date()} ===")
    print(f"   price range: {df['Close'].min():.2f} ~ {df['Close'].max():.2f}")
    print(f"   latest close: {df['Close'].iloc[-1]:.2f}")
    print(f"   symbol={SYMBOL} adjust={ADJUST} spread={args.spread} limit_pct={args.limit_pct}")

    run_backtest(df, cash=args.cash, spread=args.spread)


def run_backtest(df: pd.DataFrame, cash: float = 100_000, spread: float = SPREAD) -> None:
    """跑回测 + 出图。cash / spread 走 CLI 参数。"""
    bt = Backtest(
        df,
        SmaCross,
        cash=cash,
        commission=a_share_commission,  # A 股非对称：买 0.025% / 卖 0.076%
        spread=spread,                  # A 股价差/滑点: 0.1% (中小板默认, 蓝筹可改 0.0005)
        exclusive_orders=True,
    )
    print("\n=== running backtest ===")
    stats = bt.run()
    print(stats)

    out = OUTPUT_DIR / "backtest_yyt.html"
    bt.plot(filename=str(out), open_browser=False)
    print(f"\n✓ equity curve + trades chart → {out}")


if __name__ == "__main__":
    main()
