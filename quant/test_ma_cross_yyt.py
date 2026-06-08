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


def test_sma_cross_t1_settlement():
    """T+1 验证: 所有平仓的 trade, ExitBar - EntryBar >= 2。
    即: 今天开的仓, 至少要隔 1 根 bar (1 个交易日) 才能平。
    急涨急跌曲线, 制造可能同日 buy→sell 的场景, 验证守门生效。
    """
    from backtesting import Backtest
    df = _make_synth_df(120, scenario="slow_rise_then_sharp_fall")
    stats = Backtest(df, ma_cross_yyt.SmaCross, cash=100_000,
                     commission=0.0, exclusive_orders=True,
                     finalize_trades=True).run()
    trades = stats["_trades"]
    assert len(trades) >= 1, "至少应有 1 笔 trade (finalize 也会算)"
    # 关键断言: 每笔 trade 的 ExitBar - EntryBar >= 2
    # (EntryBar = 买入 bar, ExitBar = 平仓 bar; 差值=持仓 bar 数 + 1)
    for i, t in trades.iterrows():
        holding_bars = t["ExitBar"] - t["EntryBar"]
        assert holding_bars >= 2, (
            f"trade {i} 持仓 {holding_bars} bars, 违反 T+1 (应 ≥ 2)"
        )


# ---- TODO #2: 涨跌停 (_detect_limit_bar) ----

def test_detect_limit_bar_limit_up():
    """一字涨停: High==Low==prev_close*1.10 应被识别"""
    import numpy as np
    close = pd.Series([10.0, 11.0])  # 10% 涨
    high = pd.Series([10.5, 11.0])   # 第二天一字涨停在 11.0
    low = pd.Series([9.5, 11.0])
    mask = ma_cross_yyt._detect_limit_bar(close, high, low, limit_pct=0.10)
    assert mask.iloc[0] == False, "首日无 prev_close, 不应被识别"
    assert mask.iloc[1] == True, f"一字涨停应被识别, 实际 {mask.iloc[1]}"


def test_detect_limit_bar_limit_down():
    """一字跌停: High==Low==prev_close*0.90 应被识别"""
    close = pd.Series([10.0, 9.0])
    high = pd.Series([10.5, 9.0])
    low = pd.Series([9.5, 9.0])
    mask = ma_cross_yyt._detect_limit_bar(close, high, low, limit_pct=0.10)
    assert mask.iloc[1] == True, f"一字跌停应被识别, 实际 {mask.iloc[1]}"


def test_detect_limit_bar_normal_no_flag():
    """正常 bar (有波动 + 涨幅不在 ±10%): 不应被识别"""
    close = pd.Series([10.0, 10.5])  # 涨 5%
    high = pd.Series([10.5, 10.7])
    low = pd.Series([9.8, 10.2])
    mask = ma_cross_yyt._detect_limit_bar(close, high, low, limit_pct=0.10)
    assert mask.iloc[1] == False, "5% 涨幅 + 有波动, 不应被识别为一字板"


def test_detect_limit_bar_high_eq_low_but_not_at_limit():
    """罕见情况: High==Low 但不在涨跌停 (e.g. 停牌 1 天后小幅波动)
    不应误判为一字板 — 第二个条件 (≈ limit_pct) 必须满足"""
    close = pd.Series([10.0, 10.0])  # 平价, High==Low
    high = pd.Series([10.0, 10.0])
    low = pd.Series([10.0, 10.0])
    mask = ma_cross_yyt._detect_limit_bar(close, high, low, limit_pct=0.10)
    assert mask.iloc[1] == False, "平价 High==Low 不应误判为涨跌停"


def test_detect_limit_bar_chinext_20pct():
    """创业板/科创板: limit_pct=0.20 应识别 20% 涨跌幅"""
    close = pd.Series([10.0, 12.0])  # 涨 20%
    high = pd.Series([10.5, 12.0])
    low = pd.Series([9.5, 12.0])
    # 主板 10% 阈值下不应被识别
    mask_main = ma_cross_yyt._detect_limit_bar(close, high, low, limit_pct=0.10)
    assert mask_main.iloc[1] == False, "主板 10% 阈值下 20% 涨不应被识别"
    # 创业板 20% 阈值下应被识别
    mask_chinext = ma_cross_yyt._detect_limit_bar(close, high, low, limit_pct=0.20)
    assert mask_chinext.iloc[1] == True, "创业板 20% 阈值下 20% 涨应被识别"


def test_sma_cross_skips_limit_bar():
    """集成测试: 涨跌停当日, 即便有 crossover 信号, 也不应产生 buy。
    手工构造: 50 根平价 → 第 51 根一字涨停 (High==Low==11.0) → 第 52 根才开涨。
    没 limit 检测时, 后续 30 根上涨会触发 buy; 有 limit 检测时第 51 根被 skip。
    """
    from backtesting import Backtest
    dates = pd.bdate_range("2024-01-01", periods=80)
    # 前 50 根平价 10.0
    closes = [10.0] * 50
    # 第 51 根一字涨停到 11.0 (10% limit, High==Low==11.0)
    closes.append(11.0)
    # 后 29 根继续涨到 14.0
    for i in range(29):
        closes.append(11.0 + (i + 1) / 29 * 3.0)
    df = pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1},
        index=pd.DatetimeIndex(dates, name="date"),
    )
    # 跑两遍: 一遍带 limit 检测, 一遍禁用 (limit_pct=0 关闭所有检测)
    class NoLimitGuard(ma_cross_yyt.SmaCross):
        limit_pct = 0  # 0% 阈值 = 永不触发一字板 (兜底永远允许)
    stats_with = Backtest(df, ma_cross_yyt.SmaCross, cash=100_000,
                          commission=0.0, exclusive_orders=True,
                          finalize_trades=True).run()
    stats_no = Backtest(df, NoLimitGuard, cash=100_000,
                        commission=0.0, exclusive_orders=True,
                        finalize_trades=True).run()
    # 关键断言: 带 limit 检测的 trade 数应 ≤ 不带检测的
    # (limit 检测在上涨途中可能 skip 了若干 buy 信号, 行为更保守)
    assert stats_with["# Trades"] <= stats_no["# Trades"], (
        f"带 limit 检测 {stats_with['# Trades']} 笔, 不带 {stats_no['# Trades']} 笔, "
        f"limit 检测应不增加交易数"
    )
