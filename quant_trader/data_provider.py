from __future__ import annotations
from typing import Protocol, runtime_checkable
import logging

import pandas as pd
import yfinance as yf
from cachetools import TTLCache

logger = logging.getLogger(__name__)


@runtime_checkable
class DataProvider(Protocol):
    def get_quote(self, symbol: str) -> dict: ...
    def get_ohlcv(self, symbol: str, period: str, interval: str) -> pd.DataFrame: ...
    def get_info(self, symbol: str) -> dict: ...


class YFinanceProvider:
    """yfinance-backed data provider (fallback when IB not connected)."""

    def get_quote(self, symbol: str) -> dict:
        t = yf.Ticker(symbol)
        info = t.info
        return {
            "symbol": symbol.upper(),
            "price": info.get("regularMarketPrice"),
            "bid": info.get("bid"),
            "ask": info.get("ask"),
            "volume": info.get("volume"),
            "market_cap": info.get("marketCap"),
        }

    def get_ohlcv(self, symbol: str, period: str = "3mo",
                  interval: str = "1d") -> pd.DataFrame:
        df = yf.download(symbol, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        return df

    def get_info(self, symbol: str) -> dict:
        return yf.Ticker(symbol).info


class CachedProvider:
    """Wraps any DataProvider with TTLCache for quotes and info."""

    def __init__(self, inner: DataProvider, quote_ttl: int = 60,
                 info_ttl: int = 3600) -> None:
        self._inner = inner
        self._quote_cache: TTLCache = TTLCache(maxsize=256, ttl=quote_ttl)
        self._info_cache: TTLCache = TTLCache(maxsize=256, ttl=info_ttl)

    def get_quote(self, symbol: str) -> dict:
        key = symbol.upper()
        if key in self._quote_cache:
            return self._quote_cache[key]
        result = self._inner.get_quote(symbol)
        self._quote_cache[key] = result
        return result

    def get_ohlcv(self, symbol: str, period: str = "3mo",
                  interval: str = "1d") -> pd.DataFrame:
        # OHLCV not cached — varies by params and too large
        return self._inner.get_ohlcv(symbol, period, interval)

    def get_info(self, symbol: str) -> dict:
        key = symbol.upper()
        if key in self._info_cache:
            return self._info_cache[key]
        result = self._inner.get_info(symbol)
        self._info_cache[key] = result
        return result
