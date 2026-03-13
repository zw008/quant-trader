# tests/test_macro_risk.py
from unittest.mock import MagicMock
from quant_trader.macro_risk import MacroRisk


def make_provider():
    provider = MagicMock()
    def mock_quote(sym):
        data = {
            "CL=F": {"symbol": "CL=F", "price": 96.4},
            "GC=F": {"symbol": "GC=F", "price": 5096.0},
            "^VIX": {"symbol": "^VIX", "price": 27.3},
            "DX-Y.NYB": {"symbol": "DX-Y.NYB", "price": 100.0},
            "^TNX": {"symbol": "^TNX", "price": 4.27},
            "SPY": {"symbol": "SPY", "price": 450.0},
            "ES=F": {"symbol": "ES=F", "price": 4500.0},
            "NQ=F": {"symbol": "NQ=F", "price": 15000.0},
        }
        return data.get(sym, {"symbol": sym, "price": 0})
    provider.get_quote.side_effect = mock_quote

    def mock_info(sym):
        data = {
            "CL=F": {"regularMarketChangePercent": 2.5},
            "GC=F": {"regularMarketChangePercent": -0.5},
            "^VIX": {"regularMarketPrice": 27.3, "regularMarketChangePercent": 8.0},
            "DX-Y.NYB": {"regularMarketChangePercent": 0.3},
            "^TNX": {"regularMarketChangePercent": 1.5},
            "SPY": {"regularMarketChangePercent": -1.5, "regularMarketPrice": 450.0},
        }
        return data.get(sym, {})
    provider.get_info.side_effect = mock_info
    return provider


def test_get_macro_dashboard():
    mr = MacroRisk(make_provider())
    dashboard = mr.get_macro_dashboard()
    assert "oil" in dashboard
    assert "gold" in dashboard
    assert "vix" in dashboard
    assert "usd" in dashboard
    assert "treasury_10y" in dashboard


def test_assess_risk_level():
    mr = MacroRisk(make_provider())
    assessment = mr.assess_risk()
    assert "level" in assessment  # "low" | "medium" | "high" | "extreme"
    assert "factors" in assessment
    assert isinstance(assessment["factors"], list)
    assert assessment["level"] in ("low", "medium", "high", "extreme")


def test_high_oil_flags_risk():
    provider = make_provider()
    # Override oil to be very high change
    original = provider.get_info.side_effect
    def high_oil(sym):
        if sym == "CL=F":
            return {"regularMarketChangePercent": 5.0}
        return original(sym)
    provider.get_info.side_effect = high_oil
    mr = MacroRisk(provider)
    assessment = mr.assess_risk()
    oil_factor = [f for f in assessment["factors"] if "油价" in f or "oil" in f.lower()]
    assert len(oil_factor) > 0


def test_get_risk_news():
    import feedparser
    from unittest.mock import patch, MagicMock
    provider = make_provider()
    mr = MacroRisk(provider)
    with patch("quant_trader.macro_risk.feedparser.parse") as mock_parse:
        mock_entry = MagicMock()
        mock_entry.title = "Iran tensions escalate"
        mock_entry.summary = "Oil prices surge"
        mock_entry.published = "2026-03-13"
        mock_parse.return_value.entries = [mock_entry]
        news = mr.get_risk_news()
        assert isinstance(news, list)
