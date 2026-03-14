"""Tests for hot stocks / meme stock screener."""
from unittest.mock import MagicMock

import pandas as pd
import numpy as np
import pytest

from quant_trader.hot_stocks import HotStocks, _fmt_cap


def _make_provider(
    price_trend: str = "up",
    volume_spike: bool = True,
    market_cap: float = 1e9,
) -> MagicMock:
    """Create a mock DataProvider with controllable behavior."""
    provider = MagicMock()

    # Build OHLCV DataFrame (25 days)
    dates = pd.date_range("2026-02-10", periods=25, freq="B")
    base_price = 10.0
    if price_trend == "up":
        closes = [base_price * (1 + 0.03 * i) for i in range(25)]
    elif price_trend == "down":
        closes = [base_price * (1 - 0.02 * i) for i in range(25)]
    else:
        closes = [base_price + np.sin(i) * 0.1 for i in range(25)]

    base_vol = 1_000_000
    volumes = [base_vol] * 20
    if volume_spike:
        volumes += [base_vol * 5] * 5  # 5x spike last 5 days
    else:
        volumes += [base_vol] * 5

    df = pd.DataFrame({
        "Open": [c * 0.99 for c in closes],
        "High": [c * 1.02 for c in closes],
        "Low": [c * 0.98 for c in closes],
        "Close": closes,
        "Volume": volumes,
    }, index=dates)

    provider.get_ohlcv.return_value = df
    provider.get_info.return_value = {
        "marketCap": market_cap,
        "regularMarketPrice": closes[-1],
        "regularMarketChangePercent": 5.0 if price_trend == "up" else -3.0,
        "volume": volumes[-1],
        "averageDailyVolume10Day": base_vol,
        "shortPercentOfFloat": 0.15,
        "floatShares": 50_000_000,
    }

    return provider


class TestScanHotMovers:
    def test_detects_volume_spike_with_price_move(self):
        provider = _make_provider(price_trend="up", volume_spike=True)
        hot = HotStocks(provider)

        result = hot.scan_hot_movers(
            symbols=["TEST"],
            lookback_days=5,
            min_volume_ratio=2.0,
            min_price_change=5.0,
        )

        assert len(result) == 1
        assert result[0]["symbol"] == "TEST"
        assert result[0]["volume_ratio"] > 2.0
        assert result[0]["change_pct"] > 0

    def test_filters_large_cap(self):
        provider = _make_provider(market_cap=100e9)
        hot = HotStocks(provider)

        result = hot.scan_hot_movers(
            symbols=["BIGCAP"],
            max_market_cap=10e9,
        )
        assert len(result) == 0

    def test_includes_recent_days_data(self):
        provider = _make_provider(price_trend="up", volume_spike=True)
        hot = HotStocks(provider)

        result = hot.scan_hot_movers(symbols=["TEST"], lookback_days=3)
        if result:
            assert "recent_days" in result[0]
            assert len(result[0]["recent_days"]) <= 3

    def test_no_spike_no_move_filtered(self):
        provider = _make_provider(price_trend="flat", volume_spike=False)
        hot = HotStocks(provider)

        result = hot.scan_hot_movers(
            symbols=["FLAT"],
            min_volume_ratio=2.0,
            min_price_change=5.0,
        )
        assert len(result) == 0

    def test_default_universe_used_when_none(self):
        provider = _make_provider()
        hot = HotStocks(provider)
        # Just verify it doesn't crash with None
        hot.scan_hot_movers(symbols=None, lookback_days=3)
        assert provider.get_ohlcv.called


class TestGetTopGainersLosers:
    def test_returns_gainers_and_losers(self):
        provider = MagicMock()
        provider.get_info.side_effect = [
            {"regularMarketChangePercent": 15.0, "regularMarketPrice": 20, "volume": 5e6, "averageDailyVolume10Day": 1e6},
            {"regularMarketChangePercent": -8.0, "regularMarketPrice": 5, "volume": 3e6, "averageDailyVolume10Day": 1e6},
            {"regularMarketChangePercent": 2.0, "regularMarketPrice": 10, "volume": 2e6, "averageDailyVolume10Day": 1e6},
        ]
        hot = HotStocks(provider)
        result = hot.get_top_gainers_losers(symbols=["A", "B", "C"], top_n=2)

        assert "gainers" in result
        assert "losers" in result
        assert result["gainers"][0]["change_pct"] == 15.0
        assert result["losers"][0]["change_pct"] == -8.0


class TestTrackMemeMomentum:
    def test_tracks_multi_day_momentum(self):
        provider = _make_provider(price_trend="up", volume_spike=True)
        hot = HotStocks(provider)

        result = hot.track_meme_momentum(["TEST"], days=3)
        assert len(result) == 1
        assert result[0]["symbol"] == "TEST"
        assert "daily" in result[0]
        assert len(result[0]["daily"]) == 3
        assert "pattern" in result[0]
        assert "cumulative_change_pct" in result[0]

    def test_empty_on_insufficient_data(self):
        provider = MagicMock()
        provider.get_ohlcv.return_value = pd.DataFrame()
        hot = HotStocks(provider)

        result = hot.track_meme_momentum(["NODATA"], days=3)
        assert result == []


class TestFmtCap:
    def test_trillion(self):
        assert _fmt_cap(2.5e12) == "$2.5T"

    def test_billion(self):
        assert _fmt_cap(1.2e9) == "$1.2B"

    def test_million(self):
        assert _fmt_cap(500e6) == "$500M"

    def test_small(self):
        assert _fmt_cap(50000) == "$50,000"
