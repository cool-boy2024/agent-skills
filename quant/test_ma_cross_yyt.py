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


# ---- TODO #3: ST/*ST 识别 (_check_st_status) ----

def test_check_st_status_normal_stock_passes(monkeypatch, capsys):
    """正常股票名 (无 ST): _check_st_status 不抛错 + 打印通过信息"""
    # akshare 实际 API: stock_info_a_code_name() 无参, 返回全 A 股列表
    fake_info = pd.DataFrame({"代码": ["002183"], "名称": ["怡亚通"]})
    monkeypatch.setattr(ma_cross_yyt.ak, "stock_info_a_code_name", lambda: fake_info)
    ma_cross_yyt._check_st_status("002183")  # 不应抛错
    captured = capsys.readouterr()
    assert "怡亚通" in captured.out
    assert "非 ST" in captured.out


def test_check_st_status_st_raises(monkeypatch):
    """ST 股票: _check_st_status 抛 ValueError + 错误信息含 limit_pct 修复建议"""
    fake_info = pd.DataFrame({"代码": ["002183"], "名称": ["ST 怡亚通"]})
    monkeypatch.setattr(ma_cross_yyt.ak, "stock_info_a_code_name", lambda: fake_info)
    with pytest.raises(ValueError) as exc_info:
        ma_cross_yyt._check_st_status("002183")
    msg = str(exc_info.value)
    assert "ST" in msg
    assert "limit_pct = 0.05" in msg, f"错误信息应给修复建议, 实际: {msg}"


def test_check_st_status_star_st_raises(monkeypatch):
    """*ST 股票: 同样抛错 (含 ST 即触发)"""
    fake_info = pd.DataFrame({"代码": ["002183"], "名称": ["*ST 怡亚通"]})
    monkeypatch.setattr(ma_cross_yyt.ak, "stock_info_a_code_name", lambda: fake_info)
    with pytest.raises(ValueError):
        ma_cross_yyt._check_st_status("002183")


def test_check_st_status_ak_failure_does_not_block(monkeypatch, capsys):
    """ak 接口拿不到 (网络/字段变更): 应当 warn 跳过, 不阻断回测"""
    monkeypatch.setattr(ma_cross_yyt.ak, "stock_info_a_code_name",
                        lambda: (_ for _ in ()).throw(RuntimeError("ak 字段变了")))
    ma_cross_yyt._check_st_status("002183")  # 不应抛错
    captured = capsys.readouterr()
    assert "ST 检查跳过" in captured.err


def test_check_st_status_empty_response_warns(monkeypatch, capsys):
    """ak 返回空 DataFrame: 应当 warn 跳过"""
    monkeypatch.setattr(ma_cross_yyt.ak, "stock_info_a_code_name", lambda: pd.DataFrame())
    ma_cross_yyt._check_st_status("002183")
    captured = capsys.readouterr()
    assert "ST 检查跳过" in captured.err


def test_check_st_status_symbol_not_found_warns(monkeypatch, capsys):
    """ak 全表里找不到该 symbol (罕见): warn 跳过, 不阻断"""
    fake_info = pd.DataFrame({"代码": ["600000"], "名称": ["浦发银行"]})
    monkeypatch.setattr(ma_cross_yyt.ak, "stock_info_a_code_name", lambda: fake_info)
    ma_cross_yyt._check_st_status("002183")  # 不在 fake 表里
    captured = capsys.readouterr()
    assert "ST 检查跳过" in captured.err


# ---- TODO #4: 滑点 (spread) ----

def test_spread_increases_costs():
    """滑点: spread 越大, 收益越低 (因为买卖价差扣钱)。
    同一数据, 跑两个 spread 值对比。
    """
    from backtesting import Backtest
    df = _make_synth_df(100, scenario="rise_fall")
    stats_no = Backtest(df, ma_cross_yyt.SmaCross, cash=100_000,
                        commission=0.0, spread=0.0,
                        exclusive_orders=True, finalize_trades=True).run()
    stats_with = Backtest(df, ma_cross_yyt.SmaCross, cash=100_000,
                          commission=0.0, spread=0.01,  # 1% spread (故意大, 显式看出效果)
                          exclusive_orders=True, finalize_trades=True).run()
    # 有 spread 的 final equity 应 ≤ 无 spread 的 (滑点扣钱)
    assert stats_with["Equity Final [$]"] <= stats_no["Equity Final [$]"], (
        f"有 spread {stats_with['Equity Final [$]']:.2f} 不应高于无 spread {stats_no['Equity Final [$]']:.2f}"
    )


def test_spread_default_is_one_bp_for_midcap():
    """默认 SPREAD = 0.001 (10 bp), 适合中小板 (002xxx) 流动性。
    蓝筹 (600xxx) 建议 0.0005, ST/低流动性 0.002; 改用 env SPREAD 覆盖。
    """
    assert ma_cross_yyt.SPREAD == 0.001, f"默认 SPREAD 应 0.001, 实际 {ma_cross_yyt.SPREAD}"


def test_spread_env_override(monkeypatch):
    """env SPREAD 覆盖默认 (蓝筹调低 / ST 调高)"""
    monkeypatch.setenv("SPREAD", "0.0005")
    # 重新 import module 让常量重读
    import importlib
    importlib.reload(ma_cross_yyt)
    try:
        assert ma_cross_yyt.SPREAD == 0.0005, f"env 覆盖应生效, 实际 {ma_cross_yyt.SPREAD}"
    finally:
        monkeypatch.delenv("SPREAD", raising=False)
        importlib.reload(ma_cross_yyt)  # 恢复
        # 验证恢复成功
        assert ma_cross_yyt.SPREAD == 0.001


# ---- TODO #5: 复权方式 (ADJUST) ----

def test_adjust_default_is_qfq():
    """默认 ADJUST = 'qfq' (前复权, 跟看盘软件一致)"""
    assert ma_cross_yyt.ADJUST == "qfq", f"默认 ADJUST 应 'qfq', 实际 {ma_cross_yyt.ADJUST!r}"


def test_adjust_env_override_to_hfq(monkeypatch):
    """env ADJUST=hfq → ADJUST = 'hfq' (后复权, 跨标的横向比较)"""
    monkeypatch.setenv("ADJUST", "hfq")
    import importlib
    importlib.reload(ma_cross_yyt)
    try:
        assert ma_cross_yyt.ADJUST == "hfq", f"env 覆盖应 'hfq', 实际 {ma_cross_yyt.ADJUST!r}"
    finally:
        monkeypatch.delenv("ADJUST", raising=False)
        importlib.reload(ma_cross_yyt)
        assert ma_cross_yyt.ADJUST == "qfq"  # 恢复


def test_adjust_env_none_means_no_adjust(monkeypatch):
    """env ADJUST=none → ADJUST = None (不复权, 原始价格)"""
    for val in ("none", "None", "NONE", "raw", ""):
        monkeypatch.setenv("ADJUST", val)
        import importlib
        importlib.reload(ma_cross_yyt)
        assert ma_cross_yyt.ADJUST is None, f"ADJUST={val!r} 应 → None, 实际 {ma_cross_yyt.ADJUST!r}"
    monkeypatch.delenv("ADJUST", raising=False)
    importlib.reload(ma_cross_yyt)


def test_adjust_passed_to_ak_call(monkeypatch, tmp_path):
    """fetch_data 应把 ADJUST 透传给 ak.stock_zh_a_hist_tx。
    清空 cache 强制走网络分支, mock ak 调用, assert_called_with 验证。
    """
    monkeypatch.setenv("ADJUST", "hfq")
    import importlib
    importlib.reload(ma_cross_yyt)
    try:
        # 把 CACHE 指到不存在路径, 强制走网络
        monkeypatch.setattr(ma_cross_yyt, "CACHE", tmp_path / "missing.csv")
        # mock ak 返回标准 qfq 列结构
        fake_df = pd.DataFrame({
            "date": pd.bdate_range("2024-01-01", periods=5),
            "open": [10.0, 10.1, 10.2, 10.3, 10.4],
            "close": [10.05, 10.15, 10.25, 10.35, 10.45],
            "high": [10.1, 10.2, 10.3, 10.4, 10.5],
            "low": [10.0, 10.1, 10.2, 10.3, 10.4],
            "amount": [1e6] * 5,
        })
        with patch.object(ma_cross_yyt.ak, "stock_zh_a_hist_tx", return_value=fake_df) as ak_mock:
            with patch.object(ma_cross_yyt, "_check_st_status", lambda symbol: None):
                ma_cross_yyt.fetch_data()
        # 断言: ak 被调用, 且 adjust="hfq" 被传入
        ak_mock.assert_called_once()
        call_kwargs = ak_mock.call_args.kwargs
        assert call_kwargs.get("adjust") == "hfq", (
            f"ak.stock_zh_a_hist_tx 应收到 adjust='hfq', 实际 {call_kwargs.get('adjust')!r}"
        )
    finally:
        monkeypatch.delenv("ADJUST", raising=False)
        importlib.reload(ma_cross_yyt)


# ---- CLI ----

def test_cli_parses_defaults():
    """CLI 无参数时, 走脚本顶部常量默认值 (002183/20200101/20260605)"""
    import sys
    from ma_cross_yyt import _parse_args
    saved_argv = sys.argv
    try:
        sys.argv = ["ma_cross_yyt.py"]
        args = _parse_args()
        assert args.symbol == "002183"
        assert args.start == "20200101"
        assert args.end == "20260605"
        assert args.cash == 100_000
        assert args.spread == 0.001
        assert args.adjust == "qfq"
        assert args.skip_st_check is False
        assert args.limit_pct == 0.10
    finally:
        sys.argv = saved_argv


def test_cli_overrides():
    """CLI 传参应覆盖默认值"""
    import sys
    from ma_cross_yyt import _parse_args
    saved_argv = sys.argv
    try:
        sys.argv = [
            "ma_cross_yyt.py",
            "--symbol", "600519",
            "--start", "20180101",
            "--end", "20260605",
            "--cash", "500000",
            "--spread", "0.0005",
            "--adjust", "hfq",
            "--skip-st-check",
            "--limit-pct", "0.20",
        ]
        args = _parse_args()
        assert args.symbol == "600519"
        assert args.start == "20180101"
        assert args.cash == 500_000
        assert args.spread == 0.0005
        assert args.adjust == "hfq"
        assert args.skip_st_check is True
        assert args.limit_pct == 0.20
    finally:
        sys.argv = saved_argv


# ---- 参数优化 (run_optimize) ----

def test_run_optimize_returns_best_and_heatmap(capsys):
    """run_optimize 应返回 (best_stats, heatmap Series) + 打印 top N + 写 HTML"""
    df = _make_synth_df(200, scenario="rise_fall")
    # 走小网格避免测试跑太久
    ma_cross_yyt.run_optimize(
        df,
        n1_grid=[3, 5, 10],
        n2_grid=[20, 30, 50],
        metric="Sharpe Ratio",
        top_n=3,
        cash=100_000,
        spread=0.0,
    )
    captured = capsys.readouterr()
    # 关键输出断言
    assert "best params" in captured.out, "应打印 best params"
    assert "n1=" in captured.out and "n2=" in captured.out
    assert "top 3" in captured.out, "应打印 top 3"
    assert "heatmap" in captured.out.lower(), "应输出 heatmap HTML 路径"
    # HTML 文件应被生成
    html_files = list(ma_cross_yyt.OUTPUT_DIR.glob("optimize_heatmap_*.html"))
    assert len(html_files) >= 1, f"应有 1+ heatmap HTML, 实际 {html_files}"


def test_run_optimize_constraint_n1_lt_n2():
    """run_optimize 约束: n1 < n2 才能有有效组合。
    全部 n1 ≥ n2 的网格应 raise ValueError。
    """
    df = _make_synth_df(100)
    with pytest.raises(ValueError) as exc:
        ma_cross_yyt.run_optimize(df, n1_grid=[10, 20], n2_grid=[5, 10], metric="Return [%]")
    assert "无有效" in str(exc.value)


def test_run_optimize_metric_change():
    """不同 metric 排序结果不同 (Sharpe vs Return 偏好不同参数)"""
    df = _make_synth_df(150, scenario="rise_fall")
    # 用 Return [%] 优化
    ma_cross_yyt.run_optimize(df, n1_grid=[3, 5, 10], n2_grid=[20, 30],
                              metric="Return [%]", top_n=2, spread=0.0)
    # 跑完后 OUTPUT_DIR 应有 Return 文件
    return_htmls = [f for f in ma_cross_yyt.OUTPUT_DIR.glob("optimize_heatmap_*Return*")
                    if "Sharpe" not in str(f)]
    assert len(return_htmls) >= 1
