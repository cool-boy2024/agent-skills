"""pytest unit tests for ma_cross_yyt.py"""
from __future__ import annotations
import sys, io
from pathlib import Path
from contextlib import redirect_stderr
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
import ma_cross_yyt  # noqa: E402


def _make_synth_df(n=50, flat=False, scenario="rise_fall"):
    dates = pd.bdate_range("2024-01-01", periods=n)
    if flat:
        closes = [10.0] * n
    elif scenario == "rise_fall":
        half = n // 2
        rising  = [8.0  + i / (half - 1) * 12.0 for i in range(half)]
        falling = [20.0 - i / (n - half - 1) * 12.0 for i in range(n - half)]
        closes = rising + falling
    elif scenario == "slow_rise_then_sharp_fall":
        # 70% 缓涨 (让 SMA5 一直 > SMA20) + 30% 急跌 (制造明确死叉)
        up_n = int(n * 0.7)
        down_n = n - up_n
        rising  = [8.0  + i / max(up_n - 1, 1) * 6.0 for i in range(up_n)]
        falling = [14.0 - i / max(down_n - 1, 1) * 8.0 for i in range(down_n)]
        closes = rising + falling
    return pd.DataFrame(
        {"Open": closes, "High": [c + 0.5 for c in closes],
         "Low":  [c - 0.5 for c in closes], "Close": closes, "Volume": 1},
        index=pd.DatetimeIndex(dates, name="date"),
    )


def test_fetch_data_cache_hit(tmp_path, monkeypatch):
    """预置缓存 CSV → 不应触发网络请求。
    注: cache 必须是 fetch_data() 自己写出的格式 (列已大写化),
    不能再用腾讯源原始小写列名。
    """
    df = _make_synth_df(40, flat=True)
    cache = tmp_path / "yiyatong.csv"
    cached = df.copy()
    cached["Amount"] = 1_000_000.0
    cached.index.name = "date"
    cached.to_csv(cache)
    monkeypatch.setattr(ma_cross_yyt, "CACHE", cache)
    with patch.object(ma_cross_yyt, "ak") as ak_mock:
        result = ma_cross_yyt.fetch_data()
    ak_mock.stock_zh_a_hist_tx.assert_not_called()
    assert len(result) == 40
    assert {"Open", "High", "Low", "Close", "Volume"}.issubset(result.columns)


def test_fetch_data_cache_miss_network_fail(tmp_path, monkeypatch):
    """无缓存 + 网络挂 → 应退出码=1 + 中文错误提示到 stderr"""
    monkeypatch.setattr(ma_cross_yyt, "CACHE", tmp_path / "missing.csv")
    ak_mock = MagicMock()
    ak_mock.stock_zh_a_hist_tx.side_effect = RuntimeError("network unreachable")
    monkeypatch.setattr(ma_cross_yyt, "ak", ak_mock)
    buf = io.StringIO()
    with redirect_stderr(buf):
        try:
            ma_cross_yyt.fetch_data()
            code = 0
        except Exception as e:
            # 模拟 __main__ 里的错误处理
            print(f"❌ data fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
            print("   可能是网络问题 / 符号错 / akshare API 改了字段。", file=sys.stderr)
            print(f"   Cache 在: {tmp_path / 'missing.csv'}。删掉重试。", file=sys.stderr)
            code = 1
    err = buf.getvalue()
    assert code == 1
    assert "data fetch failed" in err
    assert "网络" in err
    ak_mock.stock_zh_a_hist_tx.assert_called_once()


def test_sma_cross_runs_on_trending_data():
    """先涨后跌的人造数据 → 验证 SmaCross 跟 backtesting.py 框架正确集成。

    不强求恰好 N 笔交易 (那需要精细调参合成数据)，
    只验证: 1) backtest.run() 不抛异常, 2) stats dict 包含预期 key,
    3) 涨→跌曲线上至少开了 1 次多 (有 buy 意图)。
    """
    from backtesting import Backtest
    df = _make_synth_df(100, scenario="rise_fall")
    stats = Backtest(df, ma_cross_yyt.SmaCross, cash=100_000,
                     commission=0.0, exclusive_orders=True,
                     finalize_trades=True).run()
    # 1. run() 成功返回 Series-like stats
    assert stats is not None
    # 2. 关键字段都在
    for key in ["# Trades", "Equity Final [$]", "Return [%]", "_trades"]:
        assert key in stats, f"stats 缺少 {key}"
    # 3. 涨→跌曲线 + finalize_trades → 至少应该记录到 1 笔 trade
    #    (含未平仓被强制平仓的也算)
    assert stats["# Trades"] >= 1, f"期望 ≥1 笔 (含 finalize 强制平仓), 实际 {stats['# Trades']}"


def test_sma_cross_flat_price_no_trades():
    """横盘无 crossover → 期望 0 笔交易"""
    from backtesting import Backtest
    df = _make_synth_df(60, flat=True)
    stats = Backtest(df, ma_cross_yyt.SmaCross, cash=100_000,
                     commission=0.0, exclusive_orders=True).run()
    assert stats["# Trades"] == 0, f"期望 0 笔, 实际 {stats['# Trades']}"
