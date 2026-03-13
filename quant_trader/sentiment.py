from __future__ import annotations

import feedparser

from quant_trader.data_provider import DataProvider


class MarketSentiment:

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    def get_market_mood(self) -> dict:
        """Market mood: VIX, simple fear/greed estimate, SPY change."""
        vix_info = self._provider.get_info("^VIX")
        vix = vix_info.get("regularMarketPrice", 0) or 0
        if vix < 15:
            fear_greed = "greed"
        elif vix < 25:
            fear_greed = "neutral"
        else:
            fear_greed = "fear"
        spy_info = self._provider.get_info("SPY")
        spy_change = spy_info.get("regularMarketChangePercent", 0) or 0
        return {
            "vix": round(vix, 2),
            "fear_greed": fear_greed,
            "spy_change_pct": round(spy_change, 2),
        }

    def get_sector_heat(self) -> list[dict]:
        """S&P 11 sector ETFs ranked by change %."""
        sectors = {
            "XLK": "科技", "XLF": "金融", "XLV": "医疗",
            "XLE": "能源", "XLI": "工业", "XLY": "消费",
            "XLP": "必需消费", "XLU": "公用事业",
            "XLB": "材料", "XLRE": "房地产", "XLC": "通信",
        }
        result = []
        for etf, name in sectors.items():
            try:
                info = self._provider.get_info(etf)
                chg = info.get("regularMarketChangePercent", 0) or 0
                result.append({"etf": etf, "sector": name,
                               "change_pct": round(chg, 2)})
            except Exception:
                continue
        return sorted(result, key=lambda x: x["change_pct"], reverse=True)

    def get_news_sentiment(self, symbol: str, max_items: int = 10) -> list[dict]:
        """Pull Yahoo Finance RSS news, return title + summary (truncated)."""
        url = (
            f"https://feeds.finance.yahoo.com/rss/2.0/headline"
            f"?s={symbol}&region=US&lang=en-US"
        )
        feed = feedparser.parse(url)
        items: list[dict] = []
        for entry in feed.entries[:max_items]:
            title = (entry.get("title") or "")[:200]
            summary = (entry.get("summary") or "")[:500]
            items.append({
                "title": title,
                "summary": summary,
                "published": entry.get("published", ""),
            })
        return items
