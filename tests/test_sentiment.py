from unittest.mock import patch, MagicMock
from quant_trader.sentiment import MarketSentiment


def test_get_market_mood_returns_dict():
    provider = MagicMock()
    provider.get_quote.side_effect = lambda sym: {
        "^VIX": {"symbol": "^VIX", "price": 18.5},
        "SPY": {"symbol": "SPY", "price": 450.0},
    }.get(sym, {"symbol": sym, "price": 0})
    provider.get_info.side_effect = lambda sym: {
        "^VIX": {"regularMarketPrice": 18.5},
        "SPY": {"regularMarketPrice": 450.0, "regularMarketChangePercent": 0.5},
    }.get(sym, {})
    s = MarketSentiment(provider)
    mood = s.get_market_mood()
    assert "vix" in mood
    assert "fear_greed" in mood


def test_get_news_sentiment_returns_list():
    with patch("quant_trader.sentiment.feedparser.parse") as mock_parse:
        mock_parse.return_value.entries = [
            MagicMock(title="Apple beats earnings", summary="Strong results",
                      published="Thu, 13 Mar 2026 10:00:00 GMT")
        ]
        provider = MagicMock()
        s = MarketSentiment(provider)
        news = s.get_news_sentiment("AAPL")
        assert isinstance(news, list)
        assert len(news) > 0
        assert "title" in news[0]


def test_get_market_mood_greed():
    provider = MagicMock()
    provider.get_info.side_effect = lambda sym: {
        "^VIX": {"regularMarketPrice": 12.0},
        "SPY": {"regularMarketPrice": 460.0, "regularMarketChangePercent": 1.2},
    }.get(sym, {})
    s = MarketSentiment(provider)
    mood = s.get_market_mood()
    assert mood["fear_greed"] == "greed"


def test_get_market_mood_fear():
    provider = MagicMock()
    provider.get_info.side_effect = lambda sym: {
        "^VIX": {"regularMarketPrice": 30.0},
        "SPY": {"regularMarketPrice": 400.0, "regularMarketChangePercent": -2.0},
    }.get(sym, {})
    s = MarketSentiment(provider)
    mood = s.get_market_mood()
    assert mood["fear_greed"] == "fear"


def test_get_sector_heat_returns_sorted_list():
    provider = MagicMock()
    call_count = {"n": 0}
    sector_data = [1.2, -0.5, 0.8, 0.3, -1.0, 2.1, 0.1, -0.2, 0.5, 1.5, -0.8]
    def mock_info(sym):
        idx = call_count["n"]
        call_count["n"] += 1
        return {"regularMarketChangePercent": sector_data[idx % len(sector_data)]}
    provider.get_info.side_effect = mock_info
    s = MarketSentiment(provider)
    heat = s.get_sector_heat()
    assert isinstance(heat, list)
    assert len(heat) > 0
    # Should be sorted descending by change_pct
    if len(heat) > 1:
        assert heat[0]["change_pct"] >= heat[-1]["change_pct"]
