"""
Hot / meme stock screener.

Identifies small-cap stocks with unusual volume and price action
over recent days — potential meme / momentum plays for small positions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from quant_trader.data_provider import DataProvider

logger = logging.getLogger(__name__)

# Default universe: popular meme/small-cap tickers + high-volume movers
DEFAULT_MEME_UNIVERSE = (
    "GME", "AMC", "BBBY", "PLTR", "SOFI", "MARA", "RIOT", "COIN",
    "NIO", "LCID", "RIVN", "MULN", "FFIE", "DWAC", "IONQ", "RKLB",
    "SMCI", "AFRM", "HOOD", "UPST", "SOS", "WISH", "CLOV", "GOEV",
    "DNA", "OPEN", "JOBY", "LUNR", "ASTS", "RDW", "BKKT",
)


class HotStocks:
    """Screen for hot / meme stocks based on volume and price anomalies."""

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    def scan_hot_movers(
        self,
        symbols: list[str] | None = None,
        lookback_days: int = 5,
        min_volume_ratio: float = 2.0,
        min_price_change: float = 5.0,
        max_market_cap: float = 10e9,
    ) -> list[dict]:
        """
        Scan for stocks with unusual activity over the past N days.

        Criteria:
        - Volume > min_volume_ratio × 20-day average
        - Price change > min_price_change% in lookback_days
        - Market cap < max_market_cap (small/mid cap focus)

        Returns list sorted by volume ratio (most unusual first).
        """
        universe = symbols or list(DEFAULT_MEME_UNIVERSE)
        hot: list[dict] = []

        for sym in universe:
            try:
                result = self._analyze_single(
                    sym, lookback_days, min_volume_ratio,
                    min_price_change, max_market_cap,
                )
                if result is not None:
                    hot.append(result)
            except Exception as e:
                logger.debug("Hot scan skip %s: %s", sym, e)
                continue

        return sorted(hot, key=lambda x: x["volume_ratio"], reverse=True)

    def _analyze_single(
        self,
        symbol: str,
        lookback_days: int,
        min_volume_ratio: float,
        min_price_change: float,
        max_market_cap: float,
    ) -> dict | None:
        """Analyze a single ticker for hot-stock criteria."""
        df = self._provider.get_ohlcv(symbol, period="1mo", interval="1d")
        if df is None or len(df) < 5:
            return None

        info = self._provider.get_info(symbol)
        mkt_cap = info.get("marketCap", 0) or 0
        if mkt_cap > max_market_cap and max_market_cap > 0:
            return None

        # Volume analysis (use available data if < 20 days)
        vol_window = min(20, len(df))
        avg_vol_20 = df["Volume"].tail(vol_window).mean()
        recent_vol = df["Volume"].tail(min(lookback_days, len(df))).mean()
        if avg_vol_20 == 0:
            return None
        vol_ratio = recent_vol / avg_vol_20

        # Price change over lookback
        close_now = df["Close"].iloc[-1]
        close_ago = df["Close"].iloc[-lookback_days] if len(df) >= lookback_days else df["Close"].iloc[0]
        pct_change = ((close_now - close_ago) / close_ago) * 100

        # Also check single-day move (today's action matters for meme stocks)
        today_chg = ((df["Close"].iloc[-1] - df["Open"].iloc[-1]) / df["Open"].iloc[-1]) * 100
        max_daily_chg = max(
            abs(((df["Close"].iloc[i] - df["Close"].iloc[i - 1])
                 / df["Close"].iloc[i - 1]) * 100)
            for i in range(-min(lookback_days, len(df) - 1), 0)
        )

        # Filter: need either volume spike, multi-day move, OR big single-day move
        if (vol_ratio < min_volume_ratio
                and abs(pct_change) < min_price_change
                and max_daily_chg < min_price_change):
            return None

        # Momentum signal
        if pct_change > 10 and vol_ratio > 3:
            signal = "strong_momentum"
            emoji = "🔥"
        elif pct_change > 5 and vol_ratio > 2:
            signal = "momentum"
            emoji = "📈"
        elif pct_change < -10 and vol_ratio > 3:
            signal = "capitulation"
            emoji = "💥"
        elif vol_ratio > 3:
            signal = "volume_spike"
            emoji = "📊"
        else:
            signal = "watch"
            emoji = "👀"

        # Recent daily data for context
        recent_days = []
        for i in range(-min(lookback_days, len(df)), 0):
            row = df.iloc[i]
            day_chg = ((row["Close"] - row["Open"]) / row["Open"]) * 100
            recent_days.append({
                "date": str(df.index[i].date()) if hasattr(df.index[i], "date") else str(df.index[i]),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
                "change_pct": round(day_chg, 2),
            })

        return {
            "symbol": symbol.upper(),
            "signal": signal,
            "price": round(float(close_now), 2),
            "change_pct": round(pct_change, 2),
            "volume_ratio": round(vol_ratio, 2),
            "avg_volume_20d": int(avg_vol_20),
            "recent_volume": int(recent_vol),
            "market_cap": mkt_cap,
            "market_cap_label": _fmt_cap(mkt_cap),
            "recent_days": recent_days,
        }

    def get_top_gainers_losers(
        self,
        symbols: list[str] | None = None,
        top_n: int = 10,
    ) -> dict:
        """
        Get today's top gainers and losers from a universe.
        Quick snapshot for daily hot-stock tracking.
        """
        universe = symbols or list(DEFAULT_MEME_UNIVERSE)
        data: list[dict] = []

        for sym in universe:
            try:
                info = self._provider.get_info(sym)
                chg = info.get("regularMarketChangePercent", 0) or 0
                price = info.get("regularMarketPrice", 0) or 0
                vol = info.get("volume", 0) or 0
                avg_vol = info.get("averageDailyVolume10Day", 1) or 1
                data.append({
                    "symbol": sym.upper(),
                    "price": round(price, 2),
                    "change_pct": round(chg, 2),
                    "volume": vol,
                    "volume_ratio": round(vol / avg_vol, 2) if avg_vol else 0,
                })
            except Exception:
                continue

        sorted_data = sorted(data, key=lambda x: x["change_pct"], reverse=True)
        return {
            "gainers": sorted_data[:top_n],
            "losers": sorted_data[-top_n:][::-1],
            "total_scanned": len(data),
        }

    def track_meme_momentum(
        self,
        symbols: list[str],
        days: int = 3,
    ) -> list[dict]:
        """
        Track multi-day momentum for specific meme candidates.
        Shows day-by-day price/volume evolution for decision making.
        """
        results: list[dict] = []
        for sym in symbols:
            try:
                df = self._provider.get_ohlcv(sym, period="1mo", interval="1d")
                if df is None or len(df) < days + 1:
                    continue

                info = self._provider.get_info(sym)
                daily: list[dict] = []
                avg_vol_20 = df["Volume"].tail(20).mean()

                for i in range(-days, 0):
                    row = df.iloc[i]
                    prev_close = df["Close"].iloc[i - 1]
                    day_chg = ((row["Close"] - prev_close) / prev_close) * 100
                    vol_ratio = row["Volume"] / avg_vol_20 if avg_vol_20 > 0 else 0
                    daily.append({
                        "date": str(df.index[i].date()) if hasattr(df.index[i], "date") else str(df.index[i]),
                        "open": round(float(row["Open"]), 2),
                        "close": round(float(row["Close"]), 2),
                        "high": round(float(row["High"]), 2),
                        "low": round(float(row["Low"]), 2),
                        "volume": int(row["Volume"]),
                        "change_pct": round(day_chg, 2),
                        "volume_ratio": round(vol_ratio, 2),
                    })

                # Cumulative change
                start_price = df["Close"].iloc[-(days + 1)]
                end_price = df["Close"].iloc[-1]
                cum_change = ((end_price - start_price) / start_price) * 100

                # Trend pattern
                changes = [d["change_pct"] for d in daily]
                if all(c > 0 for c in changes):
                    pattern = "连涨"
                elif all(c < 0 for c in changes):
                    pattern = "连跌"
                elif changes[-1] > 0 and sum(1 for c in changes if c > 0) > len(changes) / 2:
                    pattern = "偏多"
                elif changes[-1] < 0:
                    pattern = "偏空"
                else:
                    pattern = "震荡"

                results.append({
                    "symbol": sym.upper(),
                    "current_price": round(float(end_price), 2),
                    "cumulative_change_pct": round(cum_change, 2),
                    "pattern": pattern,
                    "short_interest": info.get("shortPercentOfFloat"),
                    "float_shares": info.get("floatShares"),
                    "daily": daily,
                })
            except Exception as e:
                logger.debug("Meme track error %s: %s", sym, e)
                continue

        return sorted(results, key=lambda x: abs(x["cumulative_change_pct"]), reverse=True)


def _fmt_cap(cap: float) -> str:
    """Format market cap to human-readable."""
    if cap >= 1e12:
        return f"${cap / 1e12:.1f}T"
    if cap >= 1e9:
        return f"${cap / 1e9:.1f}B"
    if cap >= 1e6:
        return f"${cap / 1e6:.0f}M"
    return f"${cap:,.0f}"
