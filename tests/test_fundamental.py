# tests/test_fundamental.py
from unittest.mock import MagicMock
from quant_trader.fundamental import Fundamental


def test_get_financials_returns_key_ratios():
    provider = MagicMock()
    provider.get_info.return_value = {
        "trailingPE": 28.5, "priceToBook": 3.2,
        "returnOnEquity": 0.35, "revenueGrowth": 0.08,
        "debtToEquity": 45.0, "marketCap": 2_800_000_000_000,
        "sector": "Technology", "industry": "Consumer Electronics",
    }
    f = Fundamental(provider)
    data = f.get_financials("AAPL")
    assert data["pe_ratio"] == 28.5
    assert data["roe"] == 0.35
    assert data["symbol"] == "AAPL"


def test_get_earnings_calendar_returns_list():
    provider = MagicMock()
    provider.get_info.return_value = {
        "earningsDate": ["2026-04-30"],
    }
    f = Fundamental(provider)
    cal = f.get_earnings_calendar(["AAPL", "MSFT"])
    assert isinstance(cal, list)
    assert len(cal) == 2


def test_compare_peers_returns_multiple():
    provider = MagicMock()
    provider.get_info.return_value = {
        "trailingPE": 30.0, "priceToBook": 4.0,
        "returnOnEquity": 0.4, "revenueGrowth": 0.1,
        "debtToEquity": 50.0, "marketCap": 3_000_000_000_000,
        "sector": "Technology", "industry": "Software",
    }
    f = Fundamental(provider)
    result = f.compare_peers(["AAPL", "MSFT", "GOOG"])
    assert len(result) == 3
