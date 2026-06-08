"""pytest unit tests for cross_sma_btc.py (crypto 镜像 ma_cross_yyt.py)"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
import cross_sma_btc  # noqa: E402


def _make_synth_ohlcv(n=50, flat=False):
    """造合成 OHLCV 模拟 ccxt 返回 [[ts, O, H, L, C, V], ...] 格式"""
    dates_ms = [int(pd.Timestamp("2024-01-01").timestamp() * 1000) + i * 86400000
                for i in range(n)]
    if flat:
        closes = [30000.0] * n
    else:
        half = n // 2
        rising = [20000.0 + i / (half - 1) * 30000.0 for i in range(half)]
        falling = [50000.0 - i / (n - half - 1) * 30000.0 for i in range(n - half)]
        closes = rising + falling
    rows = [[ts, c, c + 200, c - 200, c, 100.0] for ts, c in zip(dates_ms, closes)]
    return rows


def test_crypto_commission_symmetric():
    """crypto 佣金对称: 买/卖都是 0.1% (不像 A 股 0.025% vs 0.076%)"""
    # size=1, price=50000 (BTC 5 万刀)
    buy = cross_sma_btc.crypto_commission(1, 50000)
    sell = cross_sma_btc.crypto_commission(-1, 50000)
    assert buy == 50.0, f"买佣金 1 * 50000 * 0.001 = 50, 实际 {buy}"
    assert sell == 50.0, f"卖佣金对称, 实际 {sell}"


def test_crypto_spread_default_5bp():
    """默认 SPREAD = 0.0005 (5 bp), 适合 BTC/USDT 主流币。
    山寨币建议 0.001, MEME 0.005+, 用 env SPREAD 覆盖。
    """
    assert cross_sma_btc.SPREAD == 0.0005, f"默认 SPREAD 应 0.0005, 实际 {cross_sma_btc.SPREAD}"


def test_crypto_fetch_data_cache_hit(tmp_path, monkeypatch):
    """缓存命中: 不应触发 ccxt。
    关键: 预置的 cache 文件名必须跟脚本生成的命名一致 —
    脚本命名规则: DATA_DIR / f"{SYMBOL.replace('/', '_')}_{EXCHANGE}_{TIMEFRAME}.csv"
    """
    rows = _make_synth_ohlcv(40, flat=True)
    df_raw = pd.DataFrame(rows, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    df_raw["date"] = pd.to_datetime(df_raw["timestamp"], unit="ms")
    df_raw = df_raw.set_index("date").sort_index()
    df_raw = df_raw.drop(columns=["timestamp"])
    df_raw["Amount"] = df_raw["Close"] * df_raw["Volume"]
    # 文件名跟 fetch_data 内部生成的对齐
    cache_path = tmp_path / "BTC_USDT_gate_1d.csv"
    df_raw.to_csv(cache_path)

    monkeypatch.setattr(cross_sma_btc, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cross_sma_btc, "SYMBOL", "BTC/USDT")
    monkeypatch.setattr(cross_sma_btc, "EXCHANGE", "gate")
    monkeypatch.setattr(cross_sma_btc, "TIMEFRAME", "1d")

    with patch.object(cross_sma_btc, "ccxt") as ccxt_mock:
        result = cross_sma_btc.fetch_data()
    # 缓存命中: ccxt 完全没被碰
    ccxt_mock.gate.assert_not_called()
    assert len(result) == 40
    assert {"Open", "High", "Low", "Close", "Volume"}.issubset(result.columns)


def test_crypto_fetch_data_cache_miss(tmp_path, monkeypatch):
    """缓存 miss: 调 ccxt 拉数据, 写 cache。
    关键: mock 第二次返回空 list, 防止 fetch_data 死循环 (since < end_ms 永远成立)。
    """
    rows = _make_synth_ohlcv(20, flat=True)
    monkeypatch.setattr(cross_sma_btc, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cross_sma_btc, "SYMBOL", "BTC/USDT")
    monkeypatch.setattr(cross_sma_btc, "EXCHANGE", "gate")
    monkeypatch.setattr(cross_sma_btc, "TIMEFRAME", "1d")
    monkeypatch.setattr(cross_sma_btc, "START", "2024-01-01")
    monkeypatch.setattr(cross_sma_btc, "END", "2024-12-31")

    fake_ex = MagicMock()
    # 第 1 次: 20 根数据; 第 2 次: [] 触发 fetch_data 的 break (无更多数据)
    fake_ex.fetch_ohlcv.side_effect = [rows, []]
    with patch.object(cross_sma_btc, "_make_exchange_with_fallback", return_value=fake_ex):
        result = cross_sma_btc.fetch_data()
    assert len(result) == 20
    # cache 文件应被写入
    cache_files = list(tmp_path.glob("*.csv"))
    assert len(cache_files) == 1, f"应有 1 个 cache, 实际 {cache_files}"


def test_crypto_exchange_fallback_works():
    """_make_exchange_with_fallback: 第一个失败的应该跳过, 用下一个"""
    with patch.object(cross_sma_btc, "EXCHANGE_FALLBACKS", ["failing1", "failing2", "gate"]):
        with patch.object(cross_sma_btc, "_make_exchange") as make_mock:
            # 前两个失败, 第三个成功
            ex1 = MagicMock()
            ex1.load_markets.side_effect = RuntimeError("timeout")
            ex2 = MagicMock()
            ex2.load_markets.side_effect = RuntimeError("SSL")
            ex3 = MagicMock()
            ex3.load_markets.return_value = None
            make_mock.side_effect = [ex1, ex2, ex3]
            result = cross_sma_btc._make_exchange_with_fallback("failing1")
            assert result is ex3
            assert make_mock.call_count == 3


def test_crypto_exchange_all_failing():
    """所有交易所都不可达: 应抛 RuntimeError 带尝试过的列表"""
    with patch.object(cross_sma_btc, "EXCHANGE_FALLBACKS", ["a", "b"]):
        with patch.object(cross_sma_btc, "_make_exchange") as make_mock:
            ex1 = MagicMock(); ex1.load_markets.side_effect = RuntimeError("net1")
            ex2 = MagicMock(); ex2.load_markets.side_effect = RuntimeError("net2")
            make_mock.side_effect = [ex1, ex2]
            with pytest.raises(RuntimeError) as exc:
                cross_sma_btc._make_exchange_with_fallback("a")
            assert "都不可达" in str(exc.value)


def test_crypto_validate_columns():
    """_validate_columns: 缺 OHLC 任一列即 raise"""
    df = pd.DataFrame({"Open": [1.0], "Close": [1.0]})  # 缺 High/Low
    with pytest.raises(ValueError) as exc:
        cross_sma_btc._validate_columns(df)
    assert "High" in str(exc.value) and "Low" in str(exc.value)


def test_crypto_strategy_uses_smacross_no_limit_guard():
    """crypto 的 SmaCross 应该把 limit_pct=0 禁用涨跌停检测。
    集成测试: 涨跌停日应不 skip 信号 (因为 SmaCross._is_limit 永远 False)。
    注: 价格用小额 (< cash 100k) 避免 broker margin error。
    """
    from backtesting import Backtest
    # 造 V-shape 涨→跌数据, 价格 100-200 区间
    n = 80
    rises = [100.0 + i / 39 * 100.0 for i in range(40)]
    falls = [200.0 - i / 39 * 100.0 for i in range(40)]
    closes = rises + falls
    dates = pd.bdate_range("2024-01-01", periods=n)
    df = pd.DataFrame(
        {"Open": closes, "High": [c + 1 for c in closes],
         "Low": [c - 1 for c in closes], "Close": closes, "Volume": 1},
        index=pd.DatetimeIndex(dates, name="date"),
    )
    stats = Backtest(df, cross_sma_btc.SmaCross, cash=100_000,
                     commission=0.0, spread=0.0, exclusive_orders=True,
                     finalize_trades=True).run()
    # 至少 1 笔 trade (跟 ma_cross_yyt 的对比组一致)
    assert stats["# Trades"] >= 1, f"期望 ≥1 笔 trade, 实际 {stats['# Trades']}"
    # 关键: limit_pct=0 真的注入了 (通过看 SmaCross 类的属性)
    assert cross_sma_btc.SmaCross.limit_pct == 0, (
        f"SmaCross.limit_pct 应 = 0 (crypto 禁用涨跌停), 实际 {cross_sma_btc.SmaCross.limit_pct}"
    )


def test_crypto_exchange_unsupported_raises():
    """ccxt 不支持的交易所: 应 raise ValueError"""
    with pytest.raises(ValueError) as exc:
        cross_sma_btc._make_exchange("definitely_not_a_real_exchange_xyz")
    assert "不支持" in str(exc.value)
