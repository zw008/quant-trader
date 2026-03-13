# tests/test_strategies.py
import pandas as pd
import numpy as np
import pytest
from quant_trader.strategies import (
    get_strategy, list_strategies, BacktestResult, Signal,
    SMACross, RSIMeanReversion, MACDCrossover, Momentum,
    BollingerSqueeze, VolumePrice, MAAlignment,
)


def make_ohlcv(n=120, trend="up"):
    np.random.seed(42)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    if trend == "up":
        close = pd.Series(np.linspace(100, 180, n) + np.random.randn(n) * 3, index=idx)
    elif trend == "down":
        close = pd.Series(np.linspace(180, 100, n) + np.random.randn(n) * 3, index=idx)
    else:  # sideways
        close = pd.Series(140 + np.random.randn(n) * 5, index=idx)
    volume = pd.Series(np.random.randint(500_000, 5_000_000, n), index=idx).astype(float)
    return pd.DataFrame({
        "Open": close - 1, "High": close + 3, "Low": close - 3,
        "Close": close, "Volume": volume,
    }, index=idx)


# ── Registry ────────────────────────────────────────────────────────────────

def test_list_strategies_returns_all():
    strats = list_strategies()
    assert len(strats) >= 7
    names = [s["name"] for s in strats]
    assert "sma_cross" in names
    assert "rsi_mean_reversion" in names


def test_list_strategies_filter_by_market():
    us = list_strategies(market="us")
    both = list_strategies(market="both")
    a_share = list_strategies(market="a_share")
    # ma_alignment is a_share specific
    a_names = [s["name"] for s in a_share]
    assert "ma_alignment" in a_names


def test_get_strategy_unknown_raises():
    with pytest.raises(ValueError, match="Unknown strategy"):
        get_strategy("nonexistent_strategy")


# ── SMA Cross ────────────────────────────────────────────────────────────────

def test_sma_cross_signal():
    df = make_ohlcv(120, "up")
    strat = get_strategy("sma_cross")
    signal = strat.generate_signal(df)
    assert isinstance(signal, Signal)
    assert signal.type in ("buy", "sell", "hold")
    assert 0 <= signal.strength <= 100


def test_sma_cross_backtest():
    df = make_ohlcv(200, "up")
    strat = get_strategy("sma_cross")
    result = strat.backtest(df)
    assert isinstance(result, BacktestResult)
    assert result.strategy == "sma_cross"
    assert result.total_return > -1  # not total loss


def test_sma_cross_custom_params():
    df = make_ohlcv(200, "up")
    strat = get_strategy("sma_cross")
    result = strat.backtest(df, fast_period=10, slow_period=30)
    assert result.params["fast_period"] == 10


# ── RSI Mean Reversion ───────────────────────────────────────────────────────

def test_rsi_mean_reversion_signal():
    df = make_ohlcv(60, "down")  # downtrend may push RSI low
    strat = get_strategy("rsi_mean_reversion")
    signal = strat.generate_signal(df)
    assert signal.type in ("buy", "sell", "hold")


def test_rsi_mean_reversion_backtest():
    df = make_ohlcv(200, "sideways")
    strat = get_strategy("rsi_mean_reversion")
    result = strat.backtest(df)
    assert isinstance(result, BacktestResult)


# ── MACD Crossover ───────────────────────────────────────────────────────────

def test_macd_crossover_signal():
    df = make_ohlcv(60, "up")
    strat = get_strategy("macd_crossover")
    signal = strat.generate_signal(df)
    assert signal.type in ("buy", "sell", "hold")


def test_macd_crossover_backtest():
    df = make_ohlcv(200, "up")
    strat = get_strategy("macd_crossover")
    result = strat.backtest(df)
    assert isinstance(result, BacktestResult)


# ── Momentum ─────────────────────────────────────────────────────────────────

def test_momentum_signal():
    df = make_ohlcv(200, "up")
    strat = get_strategy("momentum")
    signal = strat.generate_signal(df)
    assert signal.type in ("buy", "sell", "hold")


def test_momentum_backtest():
    df = make_ohlcv(250, "up")
    strat = get_strategy("momentum")
    result = strat.backtest(df, lookback=63)
    assert isinstance(result, BacktestResult)


# ── Bollinger Squeeze ─────────────────────────────────────────────────────────

def test_bbands_squeeze_signal():
    df = make_ohlcv(60, "sideways")
    strat = get_strategy("bbands_squeeze")
    signal = strat.generate_signal(df)
    assert signal.type in ("buy", "sell", "hold")


def test_bbands_squeeze_backtest():
    df = make_ohlcv(200, "sideways")
    strat = get_strategy("bbands_squeeze")
    result = strat.backtest(df)
    assert isinstance(result, BacktestResult)


# ── Volume Price ──────────────────────────────────────────────────────────────

def test_volume_price_signal():
    df = make_ohlcv(60, "up")
    strat = get_strategy("volume_price")
    signal = strat.generate_signal(df)
    assert signal.type in ("buy", "sell", "hold")


def test_volume_price_backtest():
    df = make_ohlcv(200, "up")
    strat = get_strategy("volume_price")
    result = strat.backtest(df)
    assert isinstance(result, BacktestResult)


# ── MA Alignment (A-share) ────────────────────────────────────────────────────

def test_ma_alignment_signal():
    df = make_ohlcv(120, "up")
    strat = get_strategy("ma_alignment")
    signal = strat.generate_signal(df)
    assert signal.type in ("buy", "sell", "hold")


def test_ma_alignment_backtest():
    df = make_ohlcv(200, "up")
    strat = get_strategy("ma_alignment")
    result = strat.backtest(df)
    assert isinstance(result, BacktestResult)
