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
#
# Known caveats (TODO for the user to learn next):
#   - T+1 结算：当前脚本允许同日买卖，A 股规则 T+1 (今天买的明天才能卖)
#     Fix idea: 在 next() 顶部加 `if self.position and bar == entry_bar: return`，
#     或用 backtesting.py 的 trade_on_close=False + 强制 next bar 处理。
#   - 涨跌停：当前一字板按收盘成交，得到虚假"完美成交"。
#     Fix idea: 监控 High==Low 且 |change|/prev_close ≈ 0.10 时跳过该 bar。
#   - ST/*ST 识别：当前无法迁移到带 ST 的标的。
#     Fix idea: 调 `ak.stock_info_a_code_name()` 拿股票名称，assert 不含 ST/*ST。
#   - 滑点：当前假设 next bar open 完美成交。
#     Fix idea: Backtest(..., slippage=...) 或自定义 fill model。
#   - 复权方式：当前用前复权 (qfq)，看盘软件同；实盘决策有时用后复权 (hfq)。

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

REQUIRED_COLUMNS = ["Open", "Close", "High", "Low"]


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


class SmaCross(Strategy):
    """经典 5/20 SMA 金叉死叉策略。"""
    n1 = 5    # 快线周期
    n2 = 20   # 慢线周期

    def init(self):
        # self.data.Close 是 backtesting.py 的 _Array (numpy view)，
        # 没有 .rolling()，必须先转成 pd.Series
        close = pd.Series(self.data.Close)
        self.sma1 = self.I(lambda: close.rolling(self.n1).mean(), name="SMA5")
        self.sma2 = self.I(lambda: close.rolling(self.n2).mean(), name="SMA20")

    def next(self):
        # TODO(T+1): A 股不允许同日买卖。今天买的要 next bar 才能卖。
        # 当前 next() 在同一天就可能 buy → sell, 实际 T+1 会让信号延迟一天。
        if crossover(self.sma1, self.sma2):
            self.buy()
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
            adjust="qfq",  # 前复权 — 跟看盘软件一致
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
    return _validate_columns(df)


def _validate_columns(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"data missing required columns: {missing}. "
            f"got: {list(df.columns)}. "
            f"delete {CACHE} and re-run to refetch from source."
        )
    return df


def run_backtest(df: pd.DataFrame) -> None:
    bt = Backtest(
        df,
        SmaCross,
        cash=100_000,
        commission=a_share_commission,  # A 股非对称：买 0.025% / 卖 0.076%
        exclusive_orders=True,
    )
    print("\n=== running backtest ===")
    stats = bt.run()
    print(stats)

    out = OUTPUT_DIR / "backtest_yyt.html"
    bt.plot(filename=str(out), open_browser=False)
    print(f"\n✓ equity curve + trades chart → {out}")


if __name__ == "__main__":
    try:
        df = fetch_data()
    except Exception as e:
        # 带上异常类型 + 类名，方便用户 google
        print(f"❌ data fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
        print("   可能是网络问题 / 符号错 / akshare API 改了字段。", file=sys.stderr)
        print(f"   Cache 在: {CACHE}。删掉重试。", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== data summary: {len(df)} trading days, "
          f"{df.index.min().date()} → {df.index.max().date()} ===")
    print(f"   price range: {df['Close'].min():.2f} ~ {df['Close'].max():.2f}")
    print(f"   latest close: {df['Close'].iloc[-1]:.2f}")

    run_backtest(df)
