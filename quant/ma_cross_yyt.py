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
# Usage:
#   ~/quant-venv/bin/python ma_cross_yyt.py
#
# Output:
#   - yiyatong.csv        : daily K-line (cached for re-runs)
#   - backtest result     : printed to stdout (year/return/drawdown/sharpe)
#   - backtest_result.png : equity curve + trade markers (HTML report)
#
# Known caveats (for the user to fix later):
#   - Default commission is 0.001 (10 bps single side). A-share reality: stamp
#     duty 5 bps one-way on sell + transfer fee ~1 bp + brokerage 2-3 bps.
#     Total round-trip ~16 bps single side on sell. This script underestimates
#     transaction cost on the sell side.
#   - T+1 settlement is NOT enforced — script allows same-day sell. Backtest.py
#     supports trade_on_close / exclusive_orders to fix this.
#   - No 涨跌停 (price limit) handling — script assumes any price is reachable.
#   - No ST/*ST/ex-rights delisting handling.
#   - No slippage model — script assumes fill at next bar's close.

import sys
from pathlib import Path

import akshare as ak
import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

CACHE = Path(__file__).parent / "yiyatong.csv"
SYMBOL = "002183"
START = "20200101"
END = "20260605"


class SmaCross(Strategy):
    """经典 5/20 SMA 金叉死叉策略。"""
    n1 = 5    # 快线周期
    n2 = 20   # 慢线周期

    def init(self):
        close = pd.Series(self.data.Close)
        self.sma1 = self.I(lambda: close.rolling(self.n1).mean())
        self.sma2 = self.I(lambda: close.rolling(self.n2).mean())

    def next(self):
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
        # 腾讯源 columns: date, open, close, high, low, amount (成交额, 元)
        # 注意: 没有 volume 列，backtesting.py 在我们不用 Position sizing 时 OK
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
        # backtesting.py 要求有 Volume 列 — 用 1 填占位 (我们策略不依赖 volume)
        df["Volume"] = 1
        df.to_csv(CACHE)
        print(f"✓ saved {len(df)} rows to {CACHE}")
    return df


def run_backtest(df: pd.DataFrame) -> None:
    bt = Backtest(
        df,
        SmaCross,
        cash=100_000,        # 10万初始资金
        commission=0.001,    # 单边 10 bps — UNDERESTIMATES sell-side stamp duty
        exclusive_orders=True,  # 新信号触发立即平掉反向仓，避免 self.sell 卖空
    )
    print("\n=== running backtest ===")
    stats = bt.run()
    print(stats)

    out = Path(__file__).parent / "backtest_yyt.html"
    bt.plot(filename=str(out), open_browser=False)
    print(f"\n✓ equity curve + trades chart → {out}")


if __name__ == "__main__":
    try:
        df = fetch_data()
    except Exception as e:
        print(f"❌ data fetch failed: {e}", file=sys.stderr)
        print("   这是网络问题，akshare 的数据源可能临时不可用。稍后重试。", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== data summary: {len(df)} trading days, "
          f"{df.index.min().date()} → {df.index.max().date()} ===")
    print(f"   price range: {df['Close'].min():.2f} ~ {df['Close'].max():.2f}")
    print(f"   latest close: {df['Close'].iloc[-1]:.2f}")

    run_backtest(df)
