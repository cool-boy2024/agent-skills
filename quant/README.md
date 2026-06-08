# quant/

A 股 + Crypto 量化实验 / 学习目录。回测脚本 + 单元测试。

**目标用户**: 量化新手 + A 股/币圈学习者。脚本里的每个 `TODO` /
边界条件都对应实盘的某个真实坑，header 注释解释了为什么这么写。

## 目录结构

```
quant/
├── README.md                 ← 你正在看
├── ma_cross_yyt.py           ← 5/20 SMA 金叉死叉 (A 股版, 26 个测试)
├── test_ma_cross_yyt.py
├── cross_sma_btc.py          ← 5/20 SMA 金叉死叉 (Crypto 版, 9 个测试)
├── test_cross_sma_btc.py
├── .gitignore                ← data/ output/ 不入库
├── data/                     ← K线缓存 (gitignored, 重跑自动生成)
└── output/                   ← 回测图表 (gitignored, 重跑自动生成)
```

## 快速开始

```bash
# 一次性: 创建 venv + 装依赖
python3 -m venv ~/quant-venv
~/quant-venv/bin/pip install akshare pandas backtesting ccxt pytest

# 跑 A 股默认回测 (002183 怡亚通, 2020-2026, 前复权)
cd /Users/a1111/Project/Hackathons/quant
~/quant-venv/bin/python ma_cross_yyt.py

# 跑 BTC/USDT 默认回测 (Gate.io 拉数据, 2020-2026, 1d)
~/quant-venv/bin/python cross_sma_btc.py

# 跑全部测试 (35 个: 26 A 股 + 9 crypto)
~/quant-venv/bin/python -m pytest -v
```

## CLI 例子

```bash
# 换股票: 贵州茅台 600519
python ma_cross_yyt.py --symbol 600519 --start 20180101

# 创业板 300750 (宁德时代): 涨跌停 20%
python ma_cross_yyt.py --symbol 300750 --limit-pct 0.20

# ST 标的: 涨跌停 5% + 跳过 ST 校验
python ma_cross_yyt.py --symbol 000XXX --skip-st-check --limit-pct 0.05

# 后复权 (跨标的横向比较绝对涨幅)
python ma_cross_yyt.py --adjust hfq

# 蓝筹滑点更低 (0.5 bp 而不是 1 bp)
python ma_cross_yyt.py --symbol 600519 --spread 0.0005

# 看所有参数
python ma_cross_yyt.py --help
```

## 环境变量

| 变量 | 默认值 | 含义 |
|------|--------|------|
| `SPREAD` | `0.001` | bid-ask 价差 (滑点建模): 主板 0.0005, 中小 0.001, ST 0.002 |
| `ADJUST` | `qfq` | 复权方式: `qfq` 前复权 / `hfq` 后复权 / `none` 不复权 |

CLI 参数 (`--spread` / `--adjust`) 优先级高于环境变量。

## CLI 例子 (Crypto)

```bash
# 默认: BTC/USDT 日线 from Gate.io
python cross_sma_btc.py

# ETH/USDT
python cross_sma_btc.py --symbol ETH/USDT

# 4 小时线
python cross_sma_btc.py --timeframe 4h

# Bybit 拉数据 (如果 Gate.io 挂了)
python cross_sma_btc.py --exchange bybit

# 山寨币滑点加大
python cross_sma_btc.py --symbol SOL/USDT --spread 0.001

# MEME 币滑点 0.5% (流动性差)
python cross_sma_btc.py --symbol DOGE/USDT --spread 0.005
```

**Crypto vs A 股 trade rules 差异**:

| 维度 | A 股 (ma_cross_yyt) | Crypto (cross_sma_btc) |
|------|---------------------|------------------------|
| 交易时间 | 工作日 9:30-15:00 | 24/7 连续 |
| 结算 | T+1 | T+0 |
| 涨跌停 | ±10% / ±20% / ±5% | 无 |
| ST/*ST | 需跳过 | 无 |
| 佣金 | 0.025% 买 / 0.076% 卖 | 0.1% 对称 |
| 价差默认 | 0.1% (中小板) | 0.05% (BTC 主流) |
| 数据源 | akshare (东方财富/腾讯) | ccxt (Gate.io/Binance/OKX) |
| 历史数据 | 20+ 年 (2000 起) | ~10 年 (BTC 2017 起) |

## 环境变量

| 变量 | 默认值 | 含义 |
|------|--------|------|
| `SPREAD` | A 股 `0.001`, Crypto `0.0005` | bid-ask 价差 (滑点建模) |
| `ADJUST` | `qfq` (A 股) | 复权方式: `qfq` / `hfq` / `none` |
| `EXCHANGE` | `gate` (Crypto) | ccxt 交易所: `gate` / `binance` / `okx` / `bybit` |
| `SYMBOL` | `BTC/USDT` (Crypto) | 交易对 |
| `TIMEFRAME` | `1d` (Crypto) | K线周期: `1m` / `5m` / `1h` / `4h` / `1d` / `1w` |

CLI 参数 (`--spread` / `--adjust` / `--exchange` / `--symbol` / `--timeframe`) 优先级高于环境变量。

## A 股实盘 handled 了的坑

| 坑 | 修复方式 | 测试 |
|----|---------|------|
| 印花税 0.05% 单边 (卖) + 过户费 0.001% | `a_share_commission(size, price)`: 买 0.025%, 卖 0.076% | (回测 stats 验证) |
| T+1 结算 | `next()` 顶部 `entry_bar` 守门 | `test_sma_cross_t1_settlement` |
| 涨跌停一字板假成交 | `_detect_limit_bar()` 一字板 skip 信号 | `test_detect_limit_bar_*` (5 个) |
| ST/*ST ±5% (默认 ±10% 会误判) | `_check_st_status()` fail-fast | `test_check_st_status_*` (6 个) |
| 滑点 | `Backtest(spread=SPREAD)` bid-ask 价差建模 | `test_spread_*` (3 个) |
| 复权 | `ADJUST` env/CLI 可切 qfq/hfq/none | `test_adjust_*` (4 个) |
| Cache 字段缺失 | `_validate_columns()` 缺列即报错 | `test_fetch_data_cache_hit` |

## 还没做的 (TODO)

5 个学习题都跑完了。下一步可以选:

- **多策略对比**: 把 SmaCross 拆成文件, 加 MACD / RSI / KDJ 等对比
- **参数优化**: `Backtest.optimize(...)` 扫 n1/n2 网格
- **多股票组合**: 用 quantstats / pyfolio 出组合报告
- **实盘对接**: 接 qstock / 券商 API 把信号推送到交易终端
- **Web3 量化栈**: 装好的 Freqtrade (51k star, 支持 Hyperliquid) 还没真正跑起来

## Caveats (脚本已知限制)

- **5/20 SMA cross 是教科书策略**, 已知在趋势市跑输 buy-hold,
  震荡市假信号多。回测怡亚通 2020-2026 是 -25.78% (含 spread + 佣金),
  同期 buy & hold +93.65%。**学 backtesting.py 框架用, 别找 alpha。**
- 数据源是 akshare 腾讯源, 偶发 SSL 抽风。脚本会自动 fallback
  (从东方财富切腾讯) + 缓存到 `data/`。
- 涨跌停 ±10% (主板) / ±20% (创/科) / ±5% (ST) — 不同板块要切 `limit_pct`。
- 滑点 10bp 是中小板 (002) 默认, 实际应根据你的股票池调整。
- 脚本跑实盘会亏钱, 这是 A 股, 不是币圈。

## 跑测试

```bash
cd /Users/a1111/Project/Hackathons/quant
~/quant-venv/bin/python -m pytest test_ma_cross_yyt.py -v

# 26 passed
```

## 关联项目

- `scripts/install.sh` — 装 skill (含米筐 RQData, 项目里 data API 备选)
- `catalog/digest.md` — 量化栈 discovery 入口 (Freqtrade 在 📥 待你决定)
- `skills/ricequant/` + `skills/rqdata-python/` — 米筐 RQData SKILLs (需付费 license)
