# tests/test_market_data.py
from unittest.mock import MagicMock

import pandas as pd

from quant_trader.market_data import MarketData


def make_mock_provider(price: float = 150.0) -> MagicMock:
    provider = MagicMock()
    provider.get_quote.return_value = {
        "symbol": "AAPL",
        "price": price,
        "bid": price - 0.1,
        "ask": price + 0.1,
        "volume": 1_000_000,
        "market_cap": 2_000_000_000,
    }
    provider.get_ohlcv.return_value = pd.DataFrame({
        "Open": [100],
        "High": [110],
        "Low": [95],
        "Close": [105],
        "Volume": [1000],
    })
    provider.get_info.return_value = {
        "regularMarketPrice": price,
        "volume": 1_000_000,
        "regularMarketPreviousClose": price - 1,
    }
    return provider


def test_get_quote_returns_price() -> None:
    provider = make_mock_provider(150.0)
    md = MarketData(provider)
    q = md.get_quote("AAPL")
    assert q["symbol"] == "AAPL"
    assert q["price"] == 150.0


def test_get_ohlcv_returns_dataframe() -> None:
    provider = make_mock_provider()
    md = MarketData(provider)
    df = md.get_ohlcv("AAPL", period="1mo", interval="1d")
    assert not df.empty
    assert "Close" in df.columns


def test_screen_stocks_filters_by_volume() -> None:
    provider = MagicMock()

    def mock_info(sym: str) -> dict:
        if sym == "AAPL":
            return {
                "volume": 50_000_000,
                "regularMarketPrice": 175.0,
                "regularMarketPreviousClose": 170.0,
            }
        return {
            "volume": 100,
            "regularMarketPrice": 5.0,
            "regularMarketPreviousClose": 5.0,
        }

    provider.get_info.side_effect = mock_info
    md = MarketData(provider)
    results = md.screen_stocks(["AAPL", "TINY"], min_volume=1_000_000)
    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL"
