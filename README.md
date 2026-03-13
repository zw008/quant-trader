# quant-trader

MCP Server for quantitative trading via Interactive Brokers TWS.

## Quick Start

```bash
# Install
uv tool install quant-trader

# Configure
mkdir -p ~/.quant-trader
cat > ~/.quant-trader/config.yaml << 'EOF'
mode: paper
ib_host: 127.0.0.1
ib_port: 7497
max_order_value: 10000.0
watchlist: [AAPL, MSFT, NVDA, TSLA, AMZN]
EOF

# Verify
quant-trader doctor
```

## Features

- **26 MCP tools** across 8 categories
- **Multi-factor stock scoring** (0-100) with 8 weighted factors
- **ATR-based dynamic targets** (stop-loss and take-profit)
- **Plan→Confirm→Execute** order safety model
- **Daily workflow**: morning briefing, intraday monitoring, EOD summary
- **DataProvider Protocol**: swappable data sources (IB primary, yfinance fallback)
- **TTLCache**: prevents redundant API calls (60s quotes, 1hr fundamentals)
- **Audit log**: all order operations tracked in JSON

## Safety

- Paper mode by default
- Orders require explicit Plan → Confirm two-step
- Live mode requires double-confirmation (`confirm_live=True`)
- Order plans expire after 5 minutes
- Daily loss limit enforced
- All operations logged to audit trail

## Development

```bash
git clone https://github.com/zw008/quant-trader.git
cd quant-trader
uv sync --all-extras
uv run pytest tests/ -v --cov=quant_trader
```

## License

MIT
