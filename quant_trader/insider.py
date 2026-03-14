"""
Insider trading monitor.

Tracks SEC Form 4 filings — CEO/CFO/director buy/sell activity.
Large insider sells can signal risk; insider buys are bullish.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InsiderTx:
    insider: str
    relation: str
    date: str
    transaction: str  # "Sale" | "Purchase" | etc.
    shares: int
    value: float
    url: str


class InsiderTrading:
    """Fetch and analyze insider transactions via yfinance (SEC Form 4)."""

    def get_transactions(self, symbol: str, max_items: int = 20) -> list[dict]:
        """Recent insider buy/sell transactions for a single ticker."""
        try:
            t = yf.Ticker(symbol)
            df = t.insider_transactions
            if df is None or df.empty:
                return []
            rows = df.head(max_items)
            result: list[dict] = []
            for _, row in rows.iterrows():
                shares = int(row.get("Shares", 0) or 0)
                value = float(row.get("Value", 0) or 0)
                result.append({
                    "insider": str(row.get("Insider", "")),
                    "relation": str(row.get("Position", row.get("Relation", ""))),
                    "date": str(row.get("Start Date", row.get("Date", ""))),
                    "transaction": str(row.get("Transaction", "")),
                    "shares": shares,
                    "value": round(value, 2),
                    "url": str(row.get("URL", "")),
                })
            return result
        except Exception as e:
            logger.warning("Failed to fetch insider data for %s: %s", symbol, e)
            return [{"error": str(e)}]

    def get_insider_summary(self, symbol: str, days: int = 90) -> dict:
        """
        Summarise insider activity: net buy/sell count, total values,
        and buy/sell ratio over recent period.
        """
        txs = self.get_transactions(symbol, max_items=50)
        if not txs or (len(txs) == 1 and "error" in txs[0]):
            return {"symbol": symbol, "total_txs": 0, "signal": "no_data"}

        buys = [t for t in txs if "purchase" in t.get("transaction", "").lower()
                or "buy" in t.get("transaction", "").lower()]
        sells = [t for t in txs if "sale" in t.get("transaction", "").lower()
                 or "sell" in t.get("transaction", "").lower()]

        buy_value = sum(t["value"] for t in buys)
        sell_value = sum(t["value"] for t in sells)

        if sell_value > buy_value * 3:
            signal = "bearish"
            reason = "内部人大幅净卖出，警惕"
        elif sell_value > buy_value * 1.5:
            signal = "cautious"
            reason = "内部人卖出偏多"
        elif buy_value > sell_value * 2:
            signal = "bullish"
            reason = "内部人净买入，看好"
        elif buy_value > sell_value:
            signal = "mildly_bullish"
            reason = "内部人买入略多"
        else:
            signal = "neutral"
            reason = "内部人买卖均衡"

        return {
            "symbol": symbol.upper(),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "buy_value": round(buy_value, 2),
            "sell_value": round(sell_value, 2),
            "net_value": round(buy_value - sell_value, 2),
            "signal": signal,
            "reason": reason,
            "recent_txs": txs[:5],
        }

    def screen_insider_activity(
        self, symbols: list[str], min_value: float = 100_000
    ) -> list[dict]:
        """
        Screen multiple symbols for significant insider activity.
        Returns sorted by net sell value (biggest sellers first — risk flag).
        """
        results: list[dict] = []
        for sym in symbols:
            try:
                summary = self.get_insider_summary(sym)
                if summary.get("total_txs", 0) == 0 and summary.get("signal") == "no_data":
                    continue
                total_activity = summary.get("buy_value", 0) + summary.get("sell_value", 0)
                if total_activity >= min_value:
                    results.append(summary)
            except Exception as e:
                logger.warning("Insider screen error for %s: %s", sym, e)
                continue

        return sorted(results, key=lambda r: r.get("net_value", 0))
