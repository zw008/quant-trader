from __future__ import annotations

from quant_trader.data_provider import DataProvider


class Fundamental:

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    def get_financials(self, symbol: str) -> dict:
        """Key financial ratios: PE, PB, ROE, revenue growth, debt ratio."""
        info = self._provider.get_info(symbol)
        return {
            "symbol": symbol.upper(),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

    def get_earnings_calendar(self, symbols: list[str]) -> list[dict]:
        """Batch earnings calendar query."""
        result = []
        for sym in symbols:
            try:
                info = self._provider.get_info(sym)
                dates = info.get("earningsDate", [])
                if not isinstance(dates, list):
                    dates = [dates] if dates else []
                result.append({
                    "symbol": sym,
                    "earnings_dates": [str(d) for d in dates],
                })
            except Exception:
                result.append({"symbol": sym, "earnings_dates": []})
        return result

    def compare_peers(self, symbols: list[str]) -> list[dict]:
        """Cross-compare financials for multiple symbols."""
        return [self.get_financials(sym) for sym in symbols]
