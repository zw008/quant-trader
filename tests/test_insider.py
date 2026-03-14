"""Tests for insider trading module."""
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from quant_trader.insider import InsiderTrading


@pytest.fixture
def insider() -> InsiderTrading:
    return InsiderTrading()


def _mock_insider_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Insider": ["John CEO", "Jane CFO", "Bob Director"],
        "Position": ["CEO", "CFO", "Director"],
        "Start Date": ["2026-03-10", "2026-03-08", "2026-03-05"],
        "Transaction": ["Sale", "Purchase", "Sale"],
        "Shares": [50000, 10000, 5000],
        "Value": [5_000_000, 800_000, 300_000],
        "URL": ["https://sec.gov/1", "https://sec.gov/2", "https://sec.gov/3"],
    })


class TestGetTransactions:
    @patch("quant_trader.insider.yf.Ticker")
    def test_returns_formatted_transactions(self, mock_ticker, insider):
        mock_t = MagicMock()
        mock_t.insider_transactions = _mock_insider_df()
        mock_ticker.return_value = mock_t

        result = insider.get_transactions("AAPL", max_items=10)

        assert len(result) == 3
        assert result[0]["insider"] == "John CEO"
        assert result[0]["transaction"] == "Sale"
        assert result[0]["shares"] == 50000
        assert result[0]["value"] == 5_000_000

    @patch("quant_trader.insider.yf.Ticker")
    def test_empty_df_returns_empty_list(self, mock_ticker, insider):
        mock_t = MagicMock()
        mock_t.insider_transactions = pd.DataFrame()
        mock_ticker.return_value = mock_t

        result = insider.get_transactions("XYZ")
        assert result == []

    @patch("quant_trader.insider.yf.Ticker")
    def test_none_df_returns_empty_list(self, mock_ticker, insider):
        mock_t = MagicMock()
        mock_t.insider_transactions = None
        mock_ticker.return_value = mock_t

        result = insider.get_transactions("XYZ")
        assert result == []

    @patch("quant_trader.insider.yf.Ticker")
    def test_respects_max_items(self, mock_ticker, insider):
        mock_t = MagicMock()
        mock_t.insider_transactions = _mock_insider_df()
        mock_ticker.return_value = mock_t

        result = insider.get_transactions("AAPL", max_items=2)
        assert len(result) == 2

    @patch("quant_trader.insider.yf.Ticker")
    def test_exception_returns_error(self, mock_ticker, insider):
        mock_ticker.side_effect = Exception("API error")
        result = insider.get_transactions("BAD")
        assert len(result) == 1
        assert "error" in result[0]


class TestGetInsiderSummary:
    @patch.object(InsiderTrading, "get_transactions")
    def test_bearish_on_heavy_selling(self, mock_get, insider):
        mock_get.return_value = [
            {"insider": "CEO", "transaction": "Sale", "shares": 50000, "value": 5_000_000},
            {"insider": "CFO", "transaction": "Sale", "shares": 20000, "value": 2_000_000},
            {"insider": "Dir", "transaction": "Purchase", "shares": 1000, "value": 100_000},
        ]
        result = insider.get_insider_summary("AAPL")
        assert result["signal"] == "bearish"
        assert result["sell_count"] == 2
        assert result["buy_count"] == 1

    @patch.object(InsiderTrading, "get_transactions")
    def test_bullish_on_heavy_buying(self, mock_get, insider):
        mock_get.return_value = [
            {"insider": "CEO", "transaction": "Purchase", "shares": 50000, "value": 5_000_000},
            {"insider": "CFO", "transaction": "Purchase", "shares": 20000, "value": 2_000_000},
        ]
        result = insider.get_insider_summary("AAPL")
        assert result["signal"] == "bullish"
        assert result["buy_count"] == 2

    @patch.object(InsiderTrading, "get_transactions")
    def test_no_data(self, mock_get, insider):
        mock_get.return_value = []
        result = insider.get_insider_summary("XYZ")
        assert result["signal"] == "no_data"

    @patch.object(InsiderTrading, "get_transactions")
    def test_neutral_on_balanced(self, mock_get, insider):
        mock_get.return_value = [
            {"insider": "CEO", "transaction": "Sale", "shares": 10000, "value": 1_000_000},
            {"insider": "CFO", "transaction": "Purchase", "shares": 10000, "value": 1_000_000},
        ]
        result = insider.get_insider_summary("AAPL")
        assert result["signal"] == "neutral"


class TestScreenInsiderActivity:
    @patch.object(InsiderTrading, "get_insider_summary")
    def test_screens_multiple_symbols(self, mock_summary, insider):
        mock_summary.side_effect = [
            {"symbol": "AAPL", "buy_value": 100_000, "sell_value": 5_000_000,
             "net_value": -4_900_000, "signal": "bearish"},
            {"symbol": "MSFT", "buy_value": 2_000_000, "sell_value": 500_000,
             "net_value": 1_500_000, "signal": "bullish"},
        ]
        result = insider.screen_insider_activity(["AAPL", "MSFT"])
        assert len(result) == 2
        # Sorted by net_value ascending (biggest sellers first)
        assert result[0]["symbol"] == "AAPL"
        assert result[1]["symbol"] == "MSFT"
