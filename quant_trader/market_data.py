from __future__ import annotations

import pandas as pd

from quant_trader.data_provider import DataProvider


class MarketData:
    """Market data tools using DataProvider abstraction."""

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    def get_quote(self, symbol: str) -> dict:
        """Real-time quote: price, bid/ask, volume, market cap."""
        return self._provider.get_quote(symbol)

    def get_ohlcv(
        self, symbol: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """OHLCV history. period: 1d/5d/1mo/3mo/1y. interval: 1m/5m/1h/1d."""
        return self._provider.get_ohlcv(symbol, period, interval)

    def screen_stocks(
        self, symbols: list[str], min_volume: int = 1_000_000
    ) -> list[dict]:
        """Batch screen: filter by volume, sort by absolute change %."""
        results: list[dict] = []
        for sym in symbols:
            try:
                info = self._provider.get_info(sym)
                vol = info.get("volume", 0) or 0
                if vol < min_volume:
                    continue
                prev = info.get("regularMarketPreviousClose", 1)
                curr = info.get("regularMarketPrice", prev)
                change_pct = (curr - prev) / prev * 100 if prev else 0
                results.append({
                    "symbol": sym,
                    "price": curr,
                    "change_pct": round(change_pct, 2),
                    "volume": vol,
                })
            except Exception:
                continue
        return sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)
