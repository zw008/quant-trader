---
name: quant-trader
description: Quantitative trading MCP Server — 39 tools for stock analysis, strategy backtesting, macro risk, meme stock scanning, insider trading, and IB order execution with Plan→Confirm safety model.
installer:
  type: uvx
  package: quant-trader
metadata:
  categories: [finance, trading, mcp]
  tags: [interactive-brokers, quantitative-trading, stock-analysis, meme-stocks, macro-risk]
---

# quant-trader

Quantitative trading MCP Server for Claude Code. Connects to Interactive Brokers TWS for US stocks, with yfinance as zero-config fallback.

## Setup

### 1. Install

```bash
uv tool install quant-trader
```

### 2. Configure IB TWS connection (optional)

```bash
mkdir -p ~/.quant-trader
cat > ~/.quant-trader/config.yaml << 'EOF'
mode: paper          # paper | live
ib_host: 127.0.0.1
ib_port: 7497        # 7497=paper TWS, 7496=live TWS
max_order_value: 10000.0
max_daily_loss: 2000.0
max_position_pct: 0.2
watchlist: [AAPL, MSFT, NVDA, TSLA, AMZN]
order_plan_ttl_minutes: 5
EOF
```

### 3. Add to Claude Code

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

### 4. Verify

Ask Claude: "run quant-trader doctor"

## Available Tools (39)

| Category | Tools |
|----------|-------|
| Market Data | `get_quote`, `get_ohlcv`, `screen_stocks` |
| Technical Analysis | `calc_indicators`, `detect_patterns`, `score_stock`, `backtest_strategy` |
| Strategies | `list_strategies`, `run_strategy_signal`, `compare_strategies` |
| Market Sentiment | `get_market_mood`, `get_sector_heat`, `get_news_sentiment` |
| Fundamental | `get_financials`, `get_earnings_calendar`, `compare_peers` |
| Portfolio | `get_positions`, `get_account_info`, `get_pnl` |
| Orders | `create_order_plan`, `confirm_order`, `cancel_order`, `get_order_status`, `list_order_plans` |
| Daily Workflow | `morning_briefing`, `intraday_snapshot`, `eod_summary`, `add_manual_pick`, `win_rate_history`, `meme_daily_report` |
| Macro Risk | `get_macro_risk`, `get_risk_news` |
| Insider Trading | `get_insider_transactions`, `get_insider_summary`, `screen_insider_activity` |
| Hot Stocks | `scan_hot_movers`, `get_top_gainers_losers`, `track_meme_momentum` |
| System | `connect_ib`, `disconnect_ib`, `doctor` |

## Usage Examples

### Daily Workflow
```
"Generate morning briefing"        → Pre-market analysis with macro risk
"Intraday snapshot"                → Real-time P&L for open positions
"EOD summary"                      → Win rate, per-stock recap
"Meme stock scan"                  → Hot/small-cap anomaly detection
```

### Stock Analysis
```
"Score NVDA"                       → Multi-factor 0-100 score
"Backtest SMA cross on AAPL"      → Strategy backtest with Sharpe ratio
"Compare all strategies on TSLA"   → Side-by-side strategy comparison
"Check insider trading for AAPL"   → SEC Form 4 buy/sell signals
```

### Macro Risk
```
"What's the macro risk level?"     → Oil, VIX, gold, rates assessment
"Get risk news"                    → Geopolitical/macro RSS headlines
```

### Safe Order Execution
```
"Buy 10 shares of AAPL at market"
→ Step 1: create_order_plan("AAPL", "BUY", 10, "MKT")
→ Step 2: Claude shows plan, asks for confirmation
→ Step 3: confirm_order(plan_id) — only after user approval
```

## Security

1. **Paper mode by default** — live requires explicit `mode: live` in config
2. **Plan→Confirm two-step** — orders are never auto-executed
3. **Live double-confirmation** — live orders require `confirm_live=True`
4. **Order plan expiration** — plans expire after 5 minutes (configurable)
5. **Max order value** — single order capped at `max_order_value` (default $10,000)
6. **Daily loss limit** — stops new orders when daily loss exceeds threshold
7. **Audit log** — all order operations logged to `reports/audit.json`
8. **No credentials in code** — IB uses local TWS authentication
9. **News truncation** — external content truncated to 500 characters
