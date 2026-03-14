# quant-trader

[English](#english) | [中文](#中文)

---

<a id="english"></a>

## Quantitative Trading MCP Server for Claude Code

A comprehensive MCP (Model Context Protocol) Server that brings quantitative stock analysis, strategy backtesting, and trade execution to Claude Code. Connects to Interactive Brokers TWS for live/paper trading of US stocks, with yfinance as a zero-config fallback for analysis.

### What It Does

| Capability | Description |
|------------|-------------|
| **Daily Workflow** | Automated morning briefing, intraday monitoring, EOD summary with win rate tracking |
| **Stock Scoring** | Multi-factor scoring (0-100) combining RSI, MACD, volume, news, PE, sector heat |
| **Strategy Library** | 7 built-in strategies with backtesting: SMA Cross, RSI Mean Reversion, MACD, Momentum, Bollinger Squeeze, Volume-Price, MA Alignment |
| **Macro Risk** | Real-time geopolitical/macro risk assessment (oil, gold, VIX, rates, USD, futures) |
| **Hot Stock Scanner** | Meme/small-cap screener: volume spikes, price anomalies, short squeeze candidates |
| **Insider Trading** | SEC Form 4 monitoring: CEO/CFO buy/sell signals, batch screening |
| **Portfolio Analysis** | Position tracking, P&L, ATR-based stop-loss/take-profit targets |
| **Order Execution** | Plan-Confirm-Execute safety model with audit logging |

### Quick Start

```bash
# 1. Install
uv tool install quant-trader

# 2. Configure IB connection (optional — works without IB using yfinance)
mkdir -p ~/.quant-trader
cat > ~/.quant-trader/config.yaml << 'EOF'
mode: paper
ib_host: 127.0.0.1
ib_port: 7497
max_order_value: 10000.0
max_daily_loss: 2000.0
watchlist: [AAPL, MSFT, NVDA, TSLA, AMZN]
EOF

# 3. Add to Claude Code MCP config
```

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "quant-trader": {
      "command": "quant-trader",
      "args": []
    }
  }
}
```

Then ask Claude: `"run quant-trader doctor"` to verify.

### Daily Workflow

The built-in daily workflow automates a 7-step analysis process:

| Step | Task | Output |
|------|------|--------|
| 1 | **Portfolio Analysis** | Holdings review with RSI/MACD signals, hold/sell/add recommendations |
| 2 | **Market Overview** | VIX, sector heat map, SPY trend, macro risk level |
| 3 | **Opportunity Scan** | Score watchlist stocks, find macro-aligned opportunities |
| 4 | **Hot/Meme Stocks** | Volume anomalies, short squeeze candidates, momentum tracking |
| 5 | **Insider Trading** | SEC Form 4 screening for abnormal CEO/CFO activity |
| 6 | **Next Day Watch** | 3-5 actionable picks with entry/stop/target levels |
| 7 | **Save Reports** | Auto-save to `reports/` directory as dated Markdown files |

**Trigger phrases**: "morning briefing", "intraday snapshot", "EOD summary", "meme scan"

### 39 MCP Tools

| Category | Tools |
|----------|-------|
| Market Data | `get_quote`, `get_ohlcv`, `screen_stocks` |
| Technical | `calc_indicators`, `detect_patterns`, `score_stock`, `backtest_strategy` |
| Strategies | `list_strategies`, `run_strategy_signal`, `compare_strategies` |
| Sentiment | `get_market_mood`, `get_sector_heat`, `get_news_sentiment` |
| Fundamental | `get_financials`, `get_earnings_calendar`, `compare_peers` |
| Portfolio | `get_positions`, `get_account_info`, `get_pnl` |
| Orders | `create_order_plan`, `confirm_order`, `cancel_order`, `get_order_status`, `list_order_plans` |
| Daily Workflow | `morning_briefing`, `intraday_snapshot`, `eod_summary`, `add_manual_pick`, `win_rate_history`, `meme_daily_report` |
| Macro Risk | `get_macro_risk`, `get_risk_news` |
| Insider | `get_insider_transactions`, `get_insider_summary`, `screen_insider_activity` |
| Hot Stocks | `scan_hot_movers`, `get_top_gainers_losers`, `track_meme_momentum` |
| System | `connect_ib`, `disconnect_ib`, `doctor` |

### Strategy Library

| Strategy | Markets | Description |
|----------|---------|-------------|
| SMA Cross | US / A-Share | Golden/death cross of 20/50-day moving averages |
| RSI Mean Reversion | US / A-Share | Buy oversold (RSI<30), sell overbought (RSI>70) |
| MACD Crossover | US / A-Share | MACD line crossing signal line |
| Momentum | US | Top percentile returns over lookback period |
| Bollinger Squeeze | US / A-Share | Breakout after low-volatility squeeze |
| Volume-Price | US / A-Share | Price breakout confirmed by volume surge |
| MA Alignment | A-Share | Bullish/bearish alignment of 5/10/20/60-day MAs |

Each strategy returns: signal (buy/sell/hold), strength (0-100), reason, and key indicators. All strategies include backtesting with Sharpe ratio, max drawdown, win rate, and total return.

### Safety Model

| Layer | Protection |
|-------|-----------|
| Default Mode | Paper trading — live requires explicit `mode: live` in config |
| Order Flow | Plan-Confirm two-step — orders are never auto-executed |
| Live Guard | Live orders require `confirm_live=True` double-confirmation |
| Expiration | Order plans expire after 5 minutes (configurable) |
| Position Limit | Single order capped at `max_order_value` (default $10,000) |
| Loss Limit | New orders blocked when daily loss exceeds threshold |
| Audit Trail | All operations logged to `reports/audit.json` |

### Report Files

All reports are saved to the `reports/` directory (git-ignored for privacy):

```
reports/
├── portfolio.md              # Current holdings (continuously updated)
├── journal.json              # Trade log with win rate tracking
├── audit.json                # Order audit trail
├── YYYY-MM-DD-morning.md     # Pre-market briefing
├── YYYY-MM-DD-intraday.md    # Intraday snapshots
├── YYYY-MM-DD-eod.md         # End-of-day summary
└── YYYY-MM-DD-meme.md        # Hot/meme stock daily report
```

### Development

```bash
git clone https://github.com/zw008/quant-trader.git
cd quant-trader
uv sync --all-extras
uv run pytest tests/ -v --cov=quant_trader    # 136 tests, 90%+ coverage
```

### Tech Stack

- Python 3.12+
- [yfinance](https://github.com/ranaroussi/yfinance) — market data (free, no API key needed)
- [ib_insync](https://github.com/erdewit/ib_insync) — Interactive Brokers connection
- [mcp](https://modelcontextprotocol.io/) — Model Context Protocol server
- [pandas](https://pandas.pydata.org/) + [pandas-ta](https://github.com/twopirllc/pandas-ta) — data analysis & technical indicators
- [feedparser](https://github.com/kurtmckee/feedparser) — news RSS feeds
- [cachetools](https://github.com/tkem/cachetools) — TTL caching for API calls

### License

MIT

---

<a id="中文"></a>

## 量化交易 MCP Server（Claude Code 插件）

为 Claude Code 打造的量化交易 MCP Server，支持美股分析、策略回测、模拟/实盘交易。通过 Interactive Brokers TWS 连接券商，也可以用 yfinance 零配置使用分析功能。

### 核心功能

| 功能 | 说明 |
|------|------|
| **每日工作流** | 开盘早报、盘中快照、收盘总结，自动追踪胜率 |
| **多因子选股** | 8因子综合评分（RSI/MACD/量价/新闻/PE/板块），0-100分 |
| **策略库** | 7个内置策略 + 回测引擎：均线交叉、RSI均值回归、MACD、动量、布林带、量价、均线排列 |
| **宏观风险** | 实时地缘政治/宏观风险评估（油价、黄金、VIX、利率、汇率、期货） |
| **热门股扫描** | Meme/小盘股异动筛选：放量、价格异常、轧空候选 |
| **内部人监控** | SEC Form 4 追踪：CEO/CFO 买卖信号，批量筛查 |
| **持仓管理** | 仓位追踪、浮盈亏、ATR动态止损止盈 |
| **安全下单** | 计划→确认→执行三步安全模型，全程审计日志 |

### 快速开始

```bash
# 1. 安装
uv tool install quant-trader

# 2. 配置 IB 连接（可选 — 不连IB也能用yfinance分析）
mkdir -p ~/.quant-trader
cat > ~/.quant-trader/config.yaml << 'EOF'
mode: paper
ib_host: 127.0.0.1
ib_port: 7497
max_order_value: 10000.0
max_daily_loss: 2000.0
watchlist: [AAPL, MSFT, NVDA, TSLA, AMZN]
EOF

# 3. 添加到 Claude Code MCP 配置
```

在 Claude Code MCP 配置中添加：

```json
{
  "mcpServers": {
    "quant-trader": {
      "command": "quant-trader",
      "args": []
    }
  }
}
```

然后对 Claude 说：`"运行 quant-trader doctor"` 验证安装。

### 每日标准工作流

内置 7 步标准分析流程，对 Claude 说"收盘分析"即可一键执行：

| 步骤 | 任务 | 输出 |
|------|------|------|
| 1 | **持仓分析** | 每只股RSI/MACD信号，持有/减仓/清仓建议 |
| 2 | **大盘宏观** | VIX、板块热力图、宏观风险等级 |
| 3 | **新机会扫描** | 对watchlist评分，寻找宏观趋势受益标的 |
| 4 | **热门Meme股** | 量价异动、轧空候选、动量追踪 |
| 5 | **内部人交易** | SEC Form 4 异常买卖筛查 |
| 6 | **明日关注** | 3-5只可操作标的，含入场/止损/目标 |
| 7 | **保存报告** | 自动存为日期命名的Markdown文件 |

**常用指令**：
- `"开盘早报"` → 盘前分析 + watchlist评分
- `"盘中快照"` → 持仓实时涨跌 + 止盈止损提示
- `"收盘分析"` → 完整7步分析
- `"meme扫描"` → 热门小盘股异动
- `"分析 AAPL"` → 单只股深度分析
- `"回测均线策略 NVDA"` → 策略回测

### 39 个 MCP 工具

| 类别 | 工具 |
|------|------|
| 行情 | `get_quote`, `get_ohlcv`, `screen_stocks` |
| 技术 | `calc_indicators`, `detect_patterns`, `score_stock`, `backtest_strategy` |
| 策略 | `list_strategies`, `run_strategy_signal`, `compare_strategies` |
| 情绪 | `get_market_mood`, `get_sector_heat`, `get_news_sentiment` |
| 基本面 | `get_financials`, `get_earnings_calendar`, `compare_peers` |
| 持仓 | `get_positions`, `get_account_info`, `get_pnl` |
| 订单 | `create_order_plan`, `confirm_order`, `cancel_order`, `get_order_status`, `list_order_plans` |
| 日报 | `morning_briefing`, `intraday_snapshot`, `eod_summary`, `add_manual_pick`, `win_rate_history`, `meme_daily_report` |
| 宏观 | `get_macro_risk`, `get_risk_news` |
| 内部人 | `get_insider_transactions`, `get_insider_summary`, `screen_insider_activity` |
| 热门股 | `scan_hot_movers`, `get_top_gainers_losers`, `track_meme_momentum` |
| 系统 | `connect_ib`, `disconnect_ib`, `doctor` |

### 安全模型

- 默认纸上交易（paper mode）
- 订单需两步确认（计划→执行）
- 实盘需双重确认（`confirm_live=True`）
- 订单计划5分钟过期
- 单笔上限 + 日亏损限制
- 全操作审计日志

### 开发

```bash
git clone https://github.com/zw008/quant-trader.git
cd quant-trader
uv sync --all-extras
uv run pytest tests/ -v --cov=quant_trader    # 136 tests, 90%+ coverage
```

### 协议

MIT
