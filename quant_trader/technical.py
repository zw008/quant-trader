from __future__ import annotations
import pandas as pd
import pandas_ta as pta
import numpy as np


class TechnicalAnalysis:

    def calc_indicators(self, df: pd.DataFrame,
                        indicators: list[str] | None = None) -> pd.DataFrame:
        """Calculate technical indicators. indicators: rsi, macd, bbands, sma, ema, atr"""
        result = df.copy()
        wanted = set(indicators or ["rsi", "macd", "bbands"])
        if "rsi" in wanted:
            result.ta.rsi(append=True)
        if "macd" in wanted:
            result.ta.macd(append=True)
        if "bbands" in wanted:
            result.ta.bbands(append=True)
        if "sma" in wanted:
            result.ta.sma(length=20, append=True)
            result.ta.sma(length=50, append=True)
        if "ema" in wanted:
            result.ta.ema(length=12, append=True)
            result.ta.ema(length=26, append=True)
        if "atr" in wanted:
            result.ta.atr(append=True)
        return result

    def detect_patterns(self, df: pd.DataFrame) -> list[dict]:
        """Detect golden/death cross and other signals."""
        signals: list[dict] = []
        enriched = self.calc_indicators(df, ["sma", "macd"])
        sma20 = enriched.get("SMA_20")
        sma50 = enriched.get("SMA_50")
        if sma20 is not None and sma50 is not None and len(sma20) >= 2:
            prev_diff = sma20.iloc[-2] - sma50.iloc[-2]
            curr_diff = sma20.iloc[-1] - sma50.iloc[-1]
            if prev_diff < 0 and curr_diff >= 0:
                signals.append({"type": "golden_cross", "desc": "SMA20 上穿 SMA50"})
            elif prev_diff > 0 and curr_diff <= 0:
                signals.append({"type": "death_cross", "desc": "SMA20 下穿 SMA50"})
        return signals

    def score_stock(self, df: pd.DataFrame, news_sentiment: float = 0.5,
                    pe_ratio: float | None = None,
                    sector_heat: float = 0.0,
                    spy_relative_strength: float | None = None) -> float:
        """
        Multi-factor stock scoring (0-100).
        Factors & weights:
          RSI (15%), MACD (15%), Volume (10%), Relative Strength vs SPY (15%),
          Bollinger Bands (10%), News Sentiment (15%), PE Ratio (10%), Sector Heat (10%)
        """
        enriched = self.calc_indicators(df, ["rsi", "macd", "bbands", "sma"])
        latest = enriched.iloc[-1]
        scores: dict[str, float] = {}

        # RSI: 30-50 is best (oversold recovery), 50-70 ok, <30 or >70 risky
        rsi = latest.get("RSI_14", 50)
        if pd.isna(rsi):
            rsi = 50
        if 30 <= rsi <= 50:
            scores["rsi"] = 90
        elif 50 < rsi <= 65:
            scores["rsi"] = 70
        elif 20 <= rsi < 30:
            scores["rsi"] = 60
        elif rsi > 70:
            scores["rsi"] = 30
        else:
            scores["rsi"] = 40

        # MACD: positive and rising is bullish
        macd_val = latest.get("MACD_12_26_9", 0)
        macd_sig = latest.get("MACDs_12_26_9", 0)
        if pd.isna(macd_val):
            macd_val = 0
        if pd.isna(macd_sig):
            macd_sig = 0
        if macd_val > 0 and macd_val > macd_sig:
            scores["macd"] = 90
        elif macd_val > 0:
            scores["macd"] = 65
        elif macd_val < 0 and macd_val > macd_sig:
            scores["macd"] = 50
        else:
            scores["macd"] = 30

        # Volume: above average is positive
        avg_vol = df["Volume"].rolling(20).mean().iloc[-1] if len(df) >= 20 else df["Volume"].mean()
        curr_vol = df["Volume"].iloc[-1]
        if pd.isna(avg_vol) or avg_vol == 0:
            scores["volume"] = 50
        elif curr_vol > avg_vol * 1.5:
            scores["volume"] = 85
        elif curr_vol > avg_vol:
            scores["volume"] = 65
        else:
            scores["volume"] = 40

        # Relative strength vs SPY
        if spy_relative_strength is not None:
            if spy_relative_strength > 1.1:
                scores["rel_strength"] = 90
            elif spy_relative_strength > 1.0:
                scores["rel_strength"] = 70
            else:
                scores["rel_strength"] = 40
        else:
            scores["rel_strength"] = 50

        # Bollinger Bands: near lower band = opportunity
        bbl = latest.get("BBL_5_2.0", None)
        bbu = latest.get("BBU_5_2.0", None)
        close = latest.get("Close", 0)
        if bbl is not None and bbu is not None and not pd.isna(bbl) and not pd.isna(bbu):
            bb_range = bbu - bbl
            if bb_range > 0:
                bb_position = (close - bbl) / bb_range
                if bb_position < 0.3:
                    scores["bbands"] = 85
                elif bb_position < 0.6:
                    scores["bbands"] = 65
                else:
                    scores["bbands"] = 35
            else:
                scores["bbands"] = 50
        else:
            scores["bbands"] = 50

        # News sentiment (0-1 scale, 0.5 = neutral)
        scores["news"] = min(100, max(0, news_sentiment * 100))

        # PE ratio
        if pe_ratio is not None and pe_ratio > 0:
            if pe_ratio < 15:
                scores["pe"] = 85
            elif pe_ratio < 25:
                scores["pe"] = 70
            elif pe_ratio < 35:
                scores["pe"] = 50
            else:
                scores["pe"] = 30
        else:
            scores["pe"] = 50

        # Sector heat (change %)
        if sector_heat > 2:
            scores["sector"] = 85
        elif sector_heat > 0:
            scores["sector"] = 65
        elif sector_heat > -1:
            scores["sector"] = 45
        else:
            scores["sector"] = 25

        weights = {
            "rsi": 0.15, "macd": 0.15, "volume": 0.10,
            "rel_strength": 0.15, "bbands": 0.10,
            "news": 0.15, "pe": 0.10, "sector": 0.10,
        }
        total = sum(scores[k] * weights[k] for k in weights)
        return round(total, 1)

    def calc_atr_targets(self, df: pd.DataFrame, entry_price: float,
                         atr_stop_multiplier: float = 2.0,
                         atr_target_multiplier: float = 3.0) -> dict:
        """Calculate dynamic stop-loss and take-profit based on ATR."""
        enriched = self.calc_indicators(df, ["atr"])
        atr_col = [c for c in enriched.columns if c.startswith("ATR")]
        if not atr_col:
            # Fallback to fixed 3%/5%
            return {
                "stop_loss": round(entry_price * 0.97, 2),
                "take_profit": round(entry_price * 1.05, 2),
                "atr": None,
                "method": "fixed_fallback",
            }
        atr = enriched[atr_col[0]].iloc[-1]
        if pd.isna(atr) or atr <= 0:
            return {
                "stop_loss": round(entry_price * 0.97, 2),
                "take_profit": round(entry_price * 1.05, 2),
                "atr": None,
                "method": "fixed_fallback",
            }
        return {
            "stop_loss": round(entry_price - atr * atr_stop_multiplier, 2),
            "take_profit": round(entry_price + atr * atr_target_multiplier, 2),
            "atr": round(float(atr), 2),
            "method": "atr_based",
        }

    def generate_signal(self, df: pd.DataFrame, strategy: str = "sma_cross", **params) -> dict:
        """Run a strategy signal analysis on the given data."""
        from quant_trader.strategies import get_strategy
        from dataclasses import asdict
        strat = get_strategy(strategy)
        signal = strat.generate_signal(df, **params)
        return asdict(signal)

    def backtest_strategy(self, df: pd.DataFrame,
                          strategy: str = "sma_cross", **params) -> dict:
        """Backtest a strategy. Use list_strategies() to see available strategies."""
        from quant_trader.strategies import get_strategy
        from dataclasses import asdict
        strat = get_strategy(strategy)
        result = strat.backtest(df, **params)
        return asdict(result)
