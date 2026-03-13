"""
Strategy library for quant-trader.

Provides 7 proven quantitative strategies for US stocks and A-shares,
all backtestable with a unified interface.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
import pandas as pd
import pandas_ta as pta  # noqa: F401 (enables df.ta accessor)
import numpy as np


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BacktestResult:
    strategy: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    params: dict


@dataclass(frozen=True)
class Signal:
    type: str       # "buy" | "sell" | "hold"
    strength: float  # 0-100
    reason: str
    indicators: dict


# ── Protocol ─────────────────────────────────────────────────────────────────

@runtime_checkable
class Strategy(Protocol):
    name: str
    market: str        # "us" | "a_share" | "both"
    description: str

    def generate_signal(self, df: pd.DataFrame, **params) -> Signal: ...
    def backtest(self, df: pd.DataFrame, **params) -> BacktestResult: ...


# ── Registry ─────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, Strategy] = {}


def register(strategy: Strategy) -> Strategy:
    _REGISTRY[strategy.name] = strategy
    return strategy


def get_strategy(name: str) -> Strategy:
    if name not in _REGISTRY:
        available = ", ".join(_REGISTRY.keys())
        raise ValueError(f"Unknown strategy: {name}. Available: {available}")
    return _REGISTRY[name]


def list_strategies(market: str | None = None) -> list[dict]:
    results = []
    for s in _REGISTRY.values():
        if market is None or s.market in (market, "both"):
            results.append({"name": s.name, "market": s.market,
                           "description": s.description})
    return results


# ── Shared Backtest Engine ───────────────────────────────────────────────────

def _run_backtest(df: pd.DataFrame, positions: pd.Series,
                  strategy_name: str, params: dict) -> BacktestResult:
    """Shared backtest: positions is Series of 1 (long) / 0 (flat)."""
    returns = df["Close"].pct_change().fillna(0)
    strat_returns = positions.shift(1).fillna(0) * returns
    total = float((1 + strat_returns).prod() - 1)
    std = float(strat_returns.std())
    sharpe = float(strat_returns.mean() / std * (252 ** 0.5)) if std > 0 else 0.0
    cumulative = (1 + strat_returns).cumprod()
    peak = cumulative.cummax()
    max_dd = float(((peak - cumulative) / peak).max()) if peak.max() > 0 else 0.0
    trades = int((positions.diff().fillna(0) != 0).sum())
    wins = int((strat_returns > 0).sum())
    active = int((strat_returns != 0).sum())
    return BacktestResult(
        strategy=strategy_name,
        total_return=round(total, 4),
        sharpe_ratio=round(sharpe, 3),
        max_drawdown=round(max_dd, 4),
        win_rate=round(wins / active if active > 0 else 0, 3),
        total_trades=trades,
        params=params,
    )


# ── Strategy Implementations ─────────────────────────────────────────────────

class SMACross:
    """Dual moving average crossover. Long when fast MA > slow MA."""
    name = "sma_cross"
    market = "both"
    description = "双均线交叉策略：快线上穿慢线买入，下穿卖出。适用美股/A股。参数: fast_period(20), slow_period(50)"

    def generate_signal(self, df: pd.DataFrame, fast_period: int = 20,
                        slow_period: int = 50, **_) -> Signal:
        fast = df["Close"].rolling(fast_period).mean()
        slow = df["Close"].rolling(slow_period).mean()
        if fast.iloc[-1] > slow.iloc[-1] and fast.iloc[-2] <= slow.iloc[-2]:
            return Signal("buy", 85, f"SMA{fast_period} 上穿 SMA{slow_period} (金叉)",
                         {"fast_sma": round(float(fast.iloc[-1]), 2),
                          "slow_sma": round(float(slow.iloc[-1]), 2)})
        elif fast.iloc[-1] < slow.iloc[-1] and fast.iloc[-2] >= slow.iloc[-2]:
            return Signal("sell", 80, f"SMA{fast_period} 下穿 SMA{slow_period} (死叉)",
                         {"fast_sma": round(float(fast.iloc[-1]), 2),
                          "slow_sma": round(float(slow.iloc[-1]), 2)})
        elif fast.iloc[-1] > slow.iloc[-1]:
            diff_pct = (fast.iloc[-1] - slow.iloc[-1]) / slow.iloc[-1] * 100
            return Signal("hold", 60, f"多头排列中，快线高于慢线 {diff_pct:.1f}%",
                         {"fast_sma": round(float(fast.iloc[-1]), 2),
                          "slow_sma": round(float(slow.iloc[-1]), 2)})
        else:
            return Signal("hold", 40, "空头排列，等待金叉",
                         {"fast_sma": round(float(fast.iloc[-1]), 2),
                          "slow_sma": round(float(slow.iloc[-1]), 2)})

    def backtest(self, df: pd.DataFrame, fast_period: int = 20,
                 slow_period: int = 50, **_) -> BacktestResult:
        fast = df["Close"].rolling(fast_period).mean()
        slow = df["Close"].rolling(slow_period).mean()
        positions = (fast > slow).astype(int)
        return _run_backtest(df, positions, self.name,
                            {"fast_period": fast_period, "slow_period": slow_period})


class RSIMeanReversion:
    """RSI oversold bounce strategy. Buy when RSI < oversold, sell when > overbought."""
    name = "rsi_mean_reversion"
    market = "both"
    description = "RSI均值回归：超卖(<30)买入，超买(>70)卖出。适用震荡市。参数: period(14), oversold(30), overbought(70)"

    def generate_signal(self, df: pd.DataFrame, period: int = 14,
                        oversold: float = 30, overbought: float = 70, **_) -> Signal:
        rsi = df.ta.rsi(length=period)
        if rsi is None or rsi.dropna().empty:
            return Signal("hold", 50, "RSI 数据不足", {"rsi": None})
        val = float(rsi.iloc[-1])
        if pd.isna(val):
            return Signal("hold", 50, "RSI 数据不足", {"rsi": None})
        if val < oversold:
            return Signal("buy", min(95, 50 + (oversold - val) * 2),
                         f"RSI={val:.1f} 超卖区，反弹机会",
                         {"rsi": round(val, 1)})
        elif val > overbought:
            return Signal("sell", min(95, 50 + (val - overbought) * 2),
                         f"RSI={val:.1f} 超买区，回调风险",
                         {"rsi": round(val, 1)})
        else:
            return Signal("hold", 50, f"RSI={val:.1f} 中性区间",
                         {"rsi": round(val, 1)})

    def backtest(self, df: pd.DataFrame, period: int = 14,
                 oversold: float = 30, overbought: float = 70, **_) -> BacktestResult:
        rsi = df.ta.rsi(length=period).fillna(50)
        positions = pd.Series(0, index=df.index, dtype=int)
        in_position = False
        for i in range(len(rsi)):
            if rsi.iloc[i] < oversold and not in_position:
                in_position = True
            elif rsi.iloc[i] > overbought and in_position:
                in_position = False
            positions.iloc[i] = 1 if in_position else 0
        return _run_backtest(df, positions, self.name,
                            {"period": period, "oversold": oversold, "overbought": overbought})


class MACDCrossover:
    """MACD signal line crossover strategy."""
    name = "macd_crossover"
    market = "both"
    description = "MACD金叉/死叉策略：MACD上穿信号线买入，下穿卖出。参数: fast(12), slow(26), signal(9)"

    def generate_signal(self, df: pd.DataFrame, fast: int = 12,
                        slow: int = 26, signal: int = 9, **_) -> Signal:
        macd_df = df.ta.macd(fast=fast, slow=slow, signal=signal)
        if macd_df is None or macd_df.empty:
            return Signal("hold", 50, "MACD 数据不足", {})
        macd_col = f"MACD_{fast}_{slow}_{signal}"
        sig_col = f"MACDs_{fast}_{slow}_{signal}"
        if macd_col not in macd_df.columns:
            return Signal("hold", 50, "MACD 数据不足", {})
        macd_line = macd_df[macd_col]
        sig_line = macd_df[sig_col]
        curr_diff = float(macd_line.iloc[-1] - sig_line.iloc[-1])
        prev_diff = float(macd_line.iloc[-2] - sig_line.iloc[-2])
        indicators = {"macd": round(float(macd_line.iloc[-1]), 3),
                      "signal": round(float(sig_line.iloc[-1]), 3)}
        if prev_diff <= 0 and curr_diff > 0:
            return Signal("buy", 80, "MACD 金叉（上穿信号线）", indicators)
        elif prev_diff >= 0 and curr_diff < 0:
            return Signal("sell", 80, "MACD 死叉（下穿信号线）", indicators)
        elif curr_diff > 0:
            return Signal("hold", 60, "MACD 多头运行中", indicators)
        else:
            return Signal("hold", 40, "MACD 空头运行中", indicators)

    def backtest(self, df: pd.DataFrame, fast: int = 12,
                 slow: int = 26, signal: int = 9, **_) -> BacktestResult:
        macd_df = df.ta.macd(fast=fast, slow=slow, signal=signal)
        macd_col = f"MACD_{fast}_{slow}_{signal}"
        sig_col = f"MACDs_{fast}_{slow}_{signal}"
        if macd_df is None or macd_col not in macd_df.columns:
            return BacktestResult(self.name, 0, 0, 0, 0, 0,
                                 {"fast": fast, "slow": slow, "signal": signal})
        positions = (macd_df[macd_col] > macd_df[sig_col]).astype(int)
        return _run_backtest(df, positions, self.name,
                            {"fast": fast, "slow": slow, "signal": signal})


class Momentum:
    """Relative strength momentum. Long when lookback return positive AND above SMA."""
    name = "momentum"
    market = "us"
    description = "动量策略：N日回报为正且价格在均线上方时做多。偏好趋势股。参数: lookback(126), sma_period(200)"

    def generate_signal(self, df: pd.DataFrame, lookback: int = 126,
                        sma_period: int = 200, **_) -> Signal:
        if len(df) < max(lookback, sma_period):
            return Signal("hold", 50, "数据不足", {})
        ret = float((df["Close"].iloc[-1] / df["Close"].iloc[-lookback] - 1) * 100)
        sma = float(df["Close"].rolling(sma_period).mean().iloc[-1])
        price = float(df["Close"].iloc[-1])
        above_sma = price > sma
        indicators = {"lookback_return_pct": round(ret, 2),
                      "sma": round(sma, 2), "above_sma": above_sma}
        if ret > 0 and above_sma:
            strength = min(95, 60 + ret)
            return Signal("buy", round(strength, 1),
                         f"{lookback}日回报 +{ret:.1f}%，价格在SMA{sma_period}上方",
                         indicators)
        elif ret < -10:
            return Signal("sell", 75, f"{lookback}日回报 {ret:.1f}%，动量衰减", indicators)
        else:
            return Signal("hold", 50, "动量中性", indicators)

    def backtest(self, df: pd.DataFrame, lookback: int = 126,
                 sma_period: int = 200, **_) -> BacktestResult:
        ret = df["Close"].pct_change(lookback)
        sma = df["Close"].rolling(sma_period).mean()
        positions = ((ret > 0) & (df["Close"] > sma)).astype(int)
        return _run_backtest(df, positions, self.name,
                            {"lookback": lookback, "sma_period": sma_period})


class BollingerSqueeze:
    """Bollinger Band squeeze breakout. Buy on upper band breakout after squeeze."""
    name = "bbands_squeeze"
    market = "both"
    description = "布林带挤压突破：带宽收窄后突破上轨买入，跌破中轨卖出。适用突破行情。参数: period(20), std(2.0)"

    def generate_signal(self, df: pd.DataFrame, period: int = 20,
                        std: float = 2.0, **_) -> Signal:
        bb = df.ta.bbands(length=period, std=std)
        if bb is None or bb.empty:
            return Signal("hold", 50, "BB 数据不足", {})
        upper_col = f"BBU_{period}_{std}"
        lower_col = f"BBL_{period}_{std}"
        mid_col = f"BBM_{period}_{std}"
        bw_col = f"BBB_{period}_{std}"
        if upper_col not in bb.columns:
            return Signal("hold", 50, "BB 数据不足", {})
        price = float(df["Close"].iloc[-1])
        upper = float(bb[upper_col].iloc[-1])
        lower = float(bb[lower_col].iloc[-1])
        mid = float(bb[mid_col].iloc[-1])
        # Bandwidth for squeeze detection
        bw = bb.get(bw_col)
        squeeze = False
        if bw is not None and len(bw.dropna()) >= period:
            curr_bw = float(bw.iloc[-1])
            avg_bw = float(bw.rolling(period).mean().iloc[-1])
            squeeze = curr_bw < avg_bw * 0.8 if not pd.isna(avg_bw) else False

        indicators = {"upper": round(upper, 2), "lower": round(lower, 2),
                      "mid": round(mid, 2), "squeeze": squeeze}
        if price > upper:
            return Signal("buy", 80, "突破布林上轨" + ("（挤压后突破）" if squeeze else ""),
                         indicators)
        elif price < lower:
            return Signal("sell", 75, "跌破布林下轨", indicators)
        elif squeeze:
            return Signal("hold", 65, "布林带挤压中，等待突破方向", indicators)
        else:
            return Signal("hold", 50, "价格在布林带内运行", indicators)

    def backtest(self, df: pd.DataFrame, period: int = 20,
                 std: float = 2.0, **_) -> BacktestResult:
        bb = df.ta.bbands(length=period, std=std)
        upper_col = f"BBU_{period}_{std}"
        mid_col = f"BBM_{period}_{std}"
        if bb is None or upper_col not in bb.columns:
            return BacktestResult(self.name, 0, 0, 0, 0, 0,
                                 {"period": period, "std": std})
        # Buy above upper, sell below mid
        positions = pd.Series(0, index=df.index, dtype=int)
        in_pos = False
        for i in range(len(df)):
            if pd.isna(bb[upper_col].iloc[i]):
                continue
            if df["Close"].iloc[i] > bb[upper_col].iloc[i] and not in_pos:
                in_pos = True
            elif df["Close"].iloc[i] < bb[mid_col].iloc[i] and in_pos:
                in_pos = False
            positions.iloc[i] = 1 if in_pos else 0
        return _run_backtest(df, positions, self.name, {"period": period, "std": std})


class VolumePrice:
    """Volume-price confirmation. Buy when price up AND volume surge."""
    name = "volume_price"
    market = "both"
    description = "量价齐升策略：价格上涨+成交量放大时买入。经典技术分析信号。参数: vol_period(20), vol_multiplier(1.5)"

    def generate_signal(self, df: pd.DataFrame, vol_period: int = 20,
                        vol_multiplier: float = 1.5, **_) -> Signal:
        avg_vol = df["Volume"].rolling(vol_period).mean()
        price_chg = df["Close"].pct_change()
        curr_vol = float(df["Volume"].iloc[-1])
        avg = float(avg_vol.iloc[-1]) if not pd.isna(avg_vol.iloc[-1]) else curr_vol
        vol_ratio = curr_vol / avg if avg > 0 else 1.0
        chg = float(price_chg.iloc[-1]) * 100
        indicators = {"volume_ratio": round(vol_ratio, 2),
                      "price_change_pct": round(chg, 2),
                      "avg_volume": round(avg, 0)}
        if chg > 0 and vol_ratio > vol_multiplier:
            return Signal("buy", min(90, 60 + vol_ratio * 10),
                         f"量价齐升：涨幅{chg:.1f}%，成交量{vol_ratio:.1f}倍于均值",
                         indicators)
        elif chg < -1 and vol_ratio > vol_multiplier:
            return Signal("sell", 75, f"放量下跌：跌幅{chg:.1f}%，量比{vol_ratio:.1f}",
                         indicators)
        else:
            return Signal("hold", 50, "量价关系中性", indicators)

    def backtest(self, df: pd.DataFrame, vol_period: int = 20,
                 vol_multiplier: float = 1.5, price_sma: int = 20, **_) -> BacktestResult:
        avg_vol = df["Volume"].rolling(vol_period).mean()
        sma = df["Close"].rolling(price_sma).mean()
        vol_surge = df["Volume"] > avg_vol * vol_multiplier
        price_up = df["Close"] > sma
        positions = (vol_surge & price_up).astype(int)
        return _run_backtest(df, positions, self.name,
                            {"vol_period": vol_period, "vol_multiplier": vol_multiplier,
                             "price_sma": price_sma})


class MAAlignment:
    """Bullish MA alignment. A-share classic: MA5 > MA10 > MA20 > MA60."""
    name = "ma_alignment"
    market = "a_share"
    description = "均线多头排列策略：MA5>MA10>MA20>MA60时做多。A股经典技术信号。参数: periods(5,10,20,60)"

    def _calc_mas(self, df: pd.DataFrame,
                  periods: tuple[int, ...] = (5, 10, 20, 60)) -> dict[int, pd.Series]:
        return {p: df["Close"].rolling(p).mean() for p in periods}

    def _is_aligned(self, mas: dict[int, pd.Series], idx: int) -> bool:
        vals = []
        for p in sorted(mas.keys()):
            v = mas[p].iloc[idx]
            if pd.isna(v):
                return False
            vals.append(v)
        return all(vals[i] > vals[i + 1] for i in range(len(vals) - 1))

    def generate_signal(self, df: pd.DataFrame,
                        periods: tuple[int, ...] = (5, 10, 20, 60), **_) -> Signal:
        mas = self._calc_mas(df, periods)
        aligned = self._is_aligned(mas, -1)
        was_aligned = self._is_aligned(mas, -2) if len(df) > max(periods) + 1 else False
        indicators = {f"ma{p}": round(float(mas[p].iloc[-1]), 2)
                      for p in periods if not pd.isna(mas[p].iloc[-1])}
        indicators["aligned"] = aligned
        if aligned and not was_aligned:
            return Signal("buy", 85,
                         f"均线多头排列刚形成（MA{'> MA'.join(str(p) for p in sorted(periods))}）",
                         indicators)
        elif aligned:
            return Signal("hold", 70, "均线多头排列持续中", indicators)
        else:
            return Signal("hold", 40, "均线未多头排列", indicators)

    def backtest(self, df: pd.DataFrame,
                 periods: tuple[int, ...] = (5, 10, 20, 60), **_) -> BacktestResult:
        mas = self._calc_mas(df, periods)
        positions = pd.Series(0, index=df.index, dtype=int)
        for i in range(max(periods), len(df)):
            if self._is_aligned(mas, i):
                positions.iloc[i] = 1
        return _run_backtest(df, positions, self.name, {"periods": list(periods)})


# ── Register All Strategies ──────────────────────────────────────────────────

register(SMACross())
register(RSIMeanReversion())
register(MACDCrossover())
register(Momentum())
register(BollingerSqueeze())
register(VolumePrice())
register(MAAlignment())
