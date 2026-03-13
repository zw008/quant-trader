"""
quant-trader MCP Server

Security:
- Paper mode by default; live requires explicit config + double-confirmation
- Orders require Plan->Confirm two-step with expiration
- Max order value enforced at plan creation
- No credentials stored in code; IB uses local TWS auth
- All external data (news) truncated to 500 chars
- Audit log for all order operations
"""
from mcp.server.fastmcp import FastMCP

from quant_trader.config import Config, DEFAULT_CONFIG_PATH
from quant_trader.connection import IBConnection
from quant_trader.data_provider import CachedProvider, YFinanceProvider
from quant_trader.fundamental import Fundamental
from quant_trader.market_data import MarketData
from quant_trader.orders import OrderManager
from quant_trader.portfolio import Portfolio
from quant_trader.sentiment import MarketSentiment
from quant_trader.technical import TechnicalAnalysis

cfg = Config.load()
conn = IBConnection(cfg)

# DataProvider: CachedProvider wrapping YFinanceProvider
_raw_provider = YFinanceProvider()
_provider = CachedProvider(_raw_provider, quote_ttl=60, info_ttl=3600)

md = MarketData(_provider)
ta = TechnicalAnalysis()
sent = MarketSentiment(_provider)
fund = Fundamental(_provider)

mcp = FastMCP("quant-trader")

# ── Market Data ──────────────────────────────────────────────────────────────


@mcp.tool()
def get_quote(symbol: str) -> dict:
    """实时报价：价格、买卖盘、成交量"""
    return md.get_quote(symbol)


@mcp.tool()
def get_ohlcv(
    symbol: str, period: str = "3mo", interval: str = "1d"
) -> dict:
    """K线历史数据。period: 1d/1mo/3mo/1y. interval: 1m/5m/1h/1d"""
    df = md.get_ohlcv(symbol, period, interval)
    return df.tail(100).to_dict(orient="records")


@mcp.tool()
def screen_stocks(symbols: list[str], min_volume: int = 1_000_000) -> list:
    """批量选股筛选，按涨跌幅排序"""
    return md.screen_stocks(symbols, min_volume)


# ── Technical Analysis ───────────────────────────────────────────────────────


@mcp.tool()
def calc_indicators(
    symbol: str,
    indicators: list[str] | None = None,
    period: str = "6mo",
) -> dict:
    """计算技术指标。indicators: [rsi, macd, bbands, sma, ema, atr]"""
    df = md.get_ohlcv(symbol, period=period)
    result = ta.calc_indicators(df, indicators)
    return result.tail(30).to_dict(orient="records")


@mcp.tool()
def detect_patterns(symbol: str) -> list:
    """检测金叉/死叉等形态信号"""
    df = md.get_ohlcv(symbol, period="6mo")
    return ta.detect_patterns(df)


@mcp.tool()
def score_stock(symbol: str, period: str = "3mo") -> dict:
    """多因子综合评分(0-100)。>70推荐关注，>80强烈推荐"""
    df = md.get_ohlcv(symbol, period=period)
    mood = sent.get_market_mood()
    news = sent.get_news_sentiment(symbol, max_items=3)
    fin = fund.get_financials(symbol)
    heat = sent.get_sector_heat()
    sector_chg = 0.0
    if fin.get("sector"):
        for s in heat:
            if s.get("sector") == fin["sector"]:
                sector_chg = s["change_pct"]
                break
    news_score = 0.5  # neutral default
    score = ta.score_stock(
        df,
        news_sentiment=news_score,
        pe_ratio=fin.get("pe_ratio"),
        sector_heat=sector_chg,
    )
    targets = ta.calc_atr_targets(df, df["Close"].iloc[-1])
    return {
        "symbol": symbol.upper(),
        "score": score,
        "recommendation": (
            "strong_buy"
            if score > 80
            else ("buy" if score > 70 else ("hold" if score > 50 else "avoid"))
        ),
        "atr_targets": targets,
        "pe_ratio": fin.get("pe_ratio"),
    }


@mcp.tool()
def backtest_strategy(
    symbol: str, strategy: str = "sma_cross", period: str = "1y"
) -> dict:
    """策略回测：胜率、夏普比率、最大回撤、总收益"""
    df = md.get_ohlcv(symbol, period=period)
    return ta.backtest_strategy(df, strategy)


# ── Market Sentiment ─────────────────────────────────────────────────────────


@mcp.tool()
def get_market_mood() -> dict:
    """大盘情绪：VIX、恐贪指数、SPY涨跌"""
    return sent.get_market_mood()


@mcp.tool()
def get_sector_heat() -> list:
    """11个标普行业 ETF 涨跌幅排行"""
    return sent.get_sector_heat()


@mcp.tool()
def get_news_sentiment(symbol: str, max_items: int = 10) -> list:
    """获取个股新闻（标题+摘要，截断至500字符）"""
    return sent.get_news_sentiment(symbol, max_items)


# ── Fundamental ──────────────────────────────────────────────────────────────


@mcp.tool()
def get_financials(symbol: str) -> dict:
    """财务指标：PE/PB/ROE/营收增长/负债率"""
    return fund.get_financials(symbol)


@mcp.tool()
def get_earnings_calendar(symbols: list[str]) -> list:
    """查询财报日历"""
    return fund.get_earnings_calendar(symbols)


@mcp.tool()
def compare_peers(symbols: list[str]) -> list:
    """同行业财务对比"""
    return fund.compare_peers(symbols)


# ── Portfolio ────────────────────────────────────────────────────────────────


@mcp.tool()
def get_positions() -> list:
    """当前持仓（需要 IB TWS 连接）"""
    p = Portfolio(conn, cfg)
    return p.get_positions()


@mcp.tool()
def get_account_info() -> dict:
    """账户净值、购买力、现金余额"""
    p = Portfolio(conn, cfg)
    return p.get_account_info()


@mcp.tool()
def get_pnl() -> dict:
    """今日/历史浮盈浮亏"""
    p = Portfolio(conn, cfg)
    return p.get_pnl()


# ── Orders ───────────────────────────────────────────────────────────────────

_om = OrderManager(conn, cfg)


@mcp.tool()
def create_order_plan(
    symbol: str,
    action: str,
    quantity: int,
    order_type: str = "LMT",
    limit_price: float | None = None,
) -> dict:
    """
    生成订单计划（不执行）。
    action: BUY | SELL. order_type: LMT | MKT
    超出 max_order_value 时拒绝。计划5分钟内过期。
    """
    return _om.create_order_plan(symbol, action, quantity, order_type, limit_price)


@mcp.tool()
def confirm_order(plan_id: str, confirm_live: bool = False) -> dict:
    """确认并提交订单。实盘模式需 confirm_live=True 二次确认。"""
    return _om.confirm_order(plan_id, confirm_live)


@mcp.tool()
def cancel_order(plan_id: str) -> dict:
    """撤销订单"""
    return _om.cancel_order(plan_id)


@mcp.tool()
def get_order_status(plan_id: str) -> dict:
    """查询订单状态"""
    return _om.get_order_status(plan_id)


@mcp.tool()
def list_order_plans() -> list:
    """列出所有订单计划"""
    return _om.list_plans()


# ── System ───────────────────────────────────────────────────────────────────


@mcp.tool()
def connect_ib() -> dict:
    """连接 IB TWS"""
    conn.connect()
    return {
        "status": "connected",
        "paper_mode": cfg.paper_mode,
        "port": cfg.ib_port,
    }


@mcp.tool()
def disconnect_ib() -> dict:
    """断开 IB TWS 连接"""
    conn.disconnect()
    return {"status": "disconnected"}


@mcp.tool()
def doctor() -> dict:
    """环境诊断：配置、TWS 连接状态、模式"""
    return {
        "config_path": str(DEFAULT_CONFIG_PATH),
        "paper_mode": cfg.paper_mode,
        "ib_host": cfg.ib_host,
        "ib_port": cfg.ib_port,
        "ib_connected": conn.is_connected,
        "max_order_value": cfg.max_order_value,
        "max_daily_loss": cfg.max_daily_loss,
        "order_plan_ttl_minutes": cfg.order_plan_ttl_minutes,
        "watchlist": list(cfg.watchlist),
    }


if __name__ == "__main__":
    mcp.run()
