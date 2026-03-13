"""
Macro risk analysis module.

Monitors geopolitical, commodity, and macro indicators that should be
factored into every trading decision.
"""
from __future__ import annotations

import logging

import feedparser

from quant_trader.data_provider import DataProvider

logger = logging.getLogger(__name__)

# Risk indicator symbols
RISK_INDICATORS = {
    "CL=F": ("oil", "WTI原油"),
    "GC=F": ("gold", "黄金"),
    "^VIX": ("vix", "VIX恐慌指数"),
    "DX-Y.NYB": ("usd", "美元指数"),
    "^TNX": ("treasury_10y", "10Y国债收益率"),
    "SPY": ("spy", "标普500"),
    "ES=F": ("sp_futures", "标普期货"),
    "NQ=F": ("nq_futures", "纳指期货"),
}

# Geopolitical/macro news RSS sources
RISK_NEWS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=CL=F&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^VIX&region=US&lang=en-US",
]


class MacroRisk:
    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    def get_macro_dashboard(self) -> dict:
        """Fetch all macro risk indicators with current values and changes."""
        dashboard: dict = {}
        for sym, (key, label) in RISK_INDICATORS.items():
            try:
                quote = self._provider.get_quote(sym)
                info = self._provider.get_info(sym)
                price = quote.get("price", 0) or 0
                chg_pct = info.get("regularMarketChangePercent", 0) or 0
                dashboard[key] = {
                    "label": label,
                    "symbol": sym,
                    "price": round(price, 2),
                    "change_pct": round(chg_pct, 2),
                }
            except Exception as e:
                dashboard[key] = {"label": label, "symbol": sym, "error": str(e)}
        return dashboard

    def assess_risk(self) -> dict:
        """
        Assess overall market risk level based on macro indicators.
        Returns level (low/medium/high/extreme) and risk factors.
        """
        dashboard = self.get_macro_dashboard()
        risk_score = 0
        factors: list[str] = []

        # VIX analysis
        vix = dashboard.get("vix", {})
        vix_price = vix.get("price", 15)
        if vix_price > 30:
            risk_score += 3
            factors.append(f"VIX={vix_price:.1f} 极度恐慌（>30）")
        elif vix_price > 25:
            risk_score += 2
            factors.append(f"VIX={vix_price:.1f} 恐慌区间（>25）")
        elif vix_price > 20:
            risk_score += 1
            factors.append(f"VIX={vix_price:.1f} 偏高（>20）")

        # Oil price shock
        oil = dashboard.get("oil", {})
        oil_chg = oil.get("change_pct", 0)
        oil_price = oil.get("price", 0)
        if abs(oil_chg) > 5:
            risk_score += 3
            factors.append(f"油价剧烈波动 {oil_chg:+.1f}%（地缘风险信号）")
        elif abs(oil_chg) > 3:
            risk_score += 2
            factors.append(f"油价大幅波动 {oil_chg:+.1f}%")
        elif oil_chg > 2:
            risk_score += 1
            factors.append(f"油价上涨 {oil_chg:+.1f}%（关注通胀传导）")
        if oil_price > 90:
            risk_score += 1
            factors.append(f"油价 ${oil_price:.0f} 处于高位（>$90）")

        # Gold as safe haven signal
        gold = dashboard.get("gold", {})
        gold_chg = gold.get("change_pct", 0)
        if gold_chg > 2:
            risk_score += 1
            factors.append(f"黄金 +{gold_chg:.1f}%，避险资金涌入")

        # USD strength (hurts exporters, EM)
        usd = dashboard.get("usd", {})
        usd_chg = usd.get("change_pct", 0)
        if usd_chg > 1:
            risk_score += 1
            factors.append(f"美元走强 +{usd_chg:.1f}%，压制跨国企业盈利")

        # Treasury yield spike (hurts growth stocks)
        treasury = dashboard.get("treasury_10y", {})
        t_chg = treasury.get("change_pct", 0)
        t_price = treasury.get("price", 0)
        if t_chg > 3:
            risk_score += 2
            factors.append(f"10Y国债收益率飙升 {t_chg:+.1f}%，成长股承压")
        elif t_price > 4.5:
            risk_score += 1
            factors.append(f"10Y收益率 {t_price:.2f}% 偏高")

        # SPY decline
        spy = dashboard.get("spy", {})
        spy_chg = spy.get("change_pct", 0)
        if spy_chg < -2:
            risk_score += 2
            factors.append(f"大盘暴跌 {spy_chg:.1f}%")
        elif spy_chg < -1:
            risk_score += 1
            factors.append(f"大盘下跌 {spy_chg:.1f}%")

        # Pre-market futures
        futures = dashboard.get("sp_futures", {})
        nq = dashboard.get("nq_futures", {})
        f_chg = futures.get("change_pct", 0)
        nq_chg = nq.get("change_pct", 0)
        if f_chg < -1 or nq_chg < -1:
            factors.append(f"期货偏空: ES {f_chg:+.1f}% / NQ {nq_chg:+.1f}%")

        # Determine level
        if risk_score >= 6:
            level = "extreme"
        elif risk_score >= 4:
            level = "high"
        elif risk_score >= 2:
            level = "medium"
        else:
            level = "low"

        # Position sizing recommendation
        max_position = {
            "extreme": 0.10,
            "high": 0.25,
            "medium": 0.50,
            "low": 0.75,
        }

        return {
            "level": level,
            "risk_score": risk_score,
            "max_total_position": max_position[level],
            "factors": factors,
            "dashboard": dashboard,
            "recommendation": {
                "extreme": "极高风险，建议仅保留10%仓位或空仓观望",
                "high": "高风险，总仓位不超过25%，偏防御配置",
                "medium": "中等风险，总仓位不超过50%，均衡配置",
                "low": "低风险，可正常建仓至75%",
            }[level],
        }

    def get_risk_news(self, max_items: int = 5) -> list[dict]:
        """Fetch geopolitical/macro risk news from multiple sources."""
        all_news: list[dict] = []
        for url in RISK_NEWS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_items]:
                    title = (getattr(entry, "title", "") or "")[:200]
                    summary = (getattr(entry, "summary", "") or "")[:500]
                    all_news.append({
                        "title": title,
                        "summary": summary,
                        "published": getattr(entry, "published", ""),
                    })
            except Exception:
                continue
        # Deduplicate by title
        seen: set[str] = set()
        unique: list[dict] = []
        for n in all_news:
            if n["title"] not in seen:
                seen.add(n["title"])
                unique.append(n)
        return unique[: max_items * 2]
