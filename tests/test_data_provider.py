# tests/test_data_provider.py
import time
from unittest.mock import patch, MagicMock
import pandas as pd
from quant_trader.data_provider import (
    DataProvider, YFinanceProvider, CachedProvider
)


def test_yfinance_provider_get_quote():
    with patch("quant_trader.data_provider.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {
            "regularMarketPrice": 175.0,
            "bid": 174.9, "ask": 175.1,
            "volume": 50_000_000, "marketCap": 2_800_000_000_000,
        }
        provider = YFinanceProvider()
        q = provider.get_quote("AAPL")
        assert q["symbol"] == "AAPL"
        assert q["price"] == 175.0


def test_yfinance_provider_get_ohlcv():
    mock_df = pd.DataFrame({
        "Open": [100], "High": [110], "Low": [95],
        "Close": [105], "Volume": [1000],
    })
    with patch("quant_trader.data_provider.yf.download", return_value=mock_df):
        provider = YFinanceProvider()
        df = provider.get_ohlcv("AAPL", period="1mo", interval="1d")
        assert not df.empty
        assert "Close" in df.columns


def test_cached_provider_caches_quotes():
    inner = MagicMock(spec=DataProvider)
    inner.get_quote.return_value = {"symbol": "AAPL", "price": 175.0}
    cached = CachedProvider(inner, quote_ttl=60, info_ttl=3600)

    # First call hits inner
    q1 = cached.get_quote("AAPL")
    assert q1["price"] == 175.0
    assert inner.get_quote.call_count == 1

    # Second call uses cache
    q2 = cached.get_quote("AAPL")
    assert q2["price"] == 175.0
    assert inner.get_quote.call_count == 1  # Still 1, cached


def test_cached_provider_passes_through_ohlcv():
    """OHLCV is not cached (too large, varies by params)."""
    inner = MagicMock(spec=DataProvider)
    inner.get_ohlcv.return_value = pd.DataFrame({"Close": [100]})
    cached = CachedProvider(inner, quote_ttl=60, info_ttl=3600)

    cached.get_ohlcv("AAPL", "1mo", "1d")
    cached.get_ohlcv("AAPL", "1mo", "1d")
    assert inner.get_ohlcv.call_count == 2  # Not cached
