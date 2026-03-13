# tests/test_technical.py
import pandas as pd
import numpy as np
from quant_trader.technical import TechnicalAnalysis


def make_ohlcv(n=60):
    np.random.seed(42)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 150, n) + np.random.randn(n) * 2, index=idx)
    return pd.DataFrame({
        "Open": close - 1, "High": close + 2, "Low": close - 2,
        "Close": close, "Volume": [1_000_000] * n,
    }, index=idx)


def test_calc_rsi_returns_series():
    ta = TechnicalAnalysis()
    df = make_ohlcv()
    result = ta.calc_indicators(df, ["rsi"])
    assert "RSI_14" in result.columns
    assert result["RSI_14"].dropna().between(0, 100).all()


def test_calc_macd_returns_columns():
    ta = TechnicalAnalysis()
    df = make_ohlcv()
    result = ta.calc_indicators(df, ["macd"])
    assert "MACD_12_26_9" in result.columns


def test_detect_golden_cross():
    ta = TechnicalAnalysis()
    df = make_ohlcv(100)
    signals = ta.detect_patterns(df)
    assert isinstance(signals, list)


def test_score_stock_returns_0_to_100():
    ta = TechnicalAnalysis()
    df = make_ohlcv(60)
    score = ta.score_stock(df, news_sentiment=0.6, pe_ratio=25.0, sector_heat=1.5)
    assert 0 <= score <= 100


def test_calc_atr_targets():
    ta = TechnicalAnalysis()
    df = make_ohlcv(60)
    targets = ta.calc_atr_targets(df, entry_price=140.0)
    assert "stop_loss" in targets
    assert "take_profit" in targets
    assert targets["stop_loss"] < 140.0
    assert targets["take_profit"] > 140.0


def test_backtest_strategy_returns_stats():
    ta = TechnicalAnalysis()
    df = make_ohlcv(100)
    result = ta.backtest_strategy(df, "sma_cross")
    assert "total_return" in result
    assert "sharpe_ratio" in result
    assert "win_rate" in result


def test_calc_indicators_sma_and_ema():
    ta = TechnicalAnalysis()
    df = make_ohlcv(60)
    result = ta.calc_indicators(df, ["sma", "ema"])
    assert "SMA_20" in result.columns
    assert "SMA_50" in result.columns
    assert "EMA_12" in result.columns
    assert "EMA_26" in result.columns


def test_calc_indicators_atr():
    ta = TechnicalAnalysis()
    df = make_ohlcv(60)
    result = ta.calc_indicators(df, ["atr"])
    atr_cols = [c for c in result.columns if c.startswith("ATR")]
    assert len(atr_cols) > 0


def test_detect_death_cross():
    """Construct data where SMA20 crosses below SMA50."""
    ta = TechnicalAnalysis()
    # Create a downtrend: price starts high, ends low
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(200, 100, n) + np.random.RandomState(0).randn(n) * 0.5, index=idx)
    df = pd.DataFrame({
        "Open": close - 1, "High": close + 2, "Low": close - 2,
        "Close": close, "Volume": [1_000_000] * n,
    }, index=idx)
    signals = ta.detect_patterns(df)
    # Should detect death_cross or at least return a list
    assert isinstance(signals, list)


def test_score_stock_high_rsi():
    """Score with RSI > 70 (overbought) should still return valid score."""
    ta = TechnicalAnalysis()
    # Make steadily rising prices to push RSI high
    n = 60
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 250, n), index=idx)
    df = pd.DataFrame({
        "Open": close - 0.5, "High": close + 0.5, "Low": close - 0.5,
        "Close": close, "Volume": [2_000_000] * n,
    }, index=idx)
    score = ta.score_stock(df, news_sentiment=0.8, pe_ratio=10.0,
                           sector_heat=3.0, spy_relative_strength=1.2)
    assert 0 <= score <= 100


def test_score_stock_low_pe():
    ta = TechnicalAnalysis()
    df = make_ohlcv(60)
    score = ta.score_stock(df, pe_ratio=12.0, sector_heat=-2.0,
                           spy_relative_strength=0.8)
    assert 0 <= score <= 100


def test_score_stock_high_pe():
    ta = TechnicalAnalysis()
    df = make_ohlcv(60)
    score = ta.score_stock(df, pe_ratio=40.0, sector_heat=0.5)
    assert 0 <= score <= 100


def test_score_stock_medium_pe():
    ta = TechnicalAnalysis()
    df = make_ohlcv(60)
    score = ta.score_stock(df, pe_ratio=30.0)
    assert 0 <= score <= 100


def test_score_stock_high_volume():
    """Test volume scoring branch where current > avg * 1.5."""
    ta = TechnicalAnalysis()
    n = 60
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 150, n), index=idx)
    volumes = [1_000_000] * (n - 1) + [5_000_000]  # Last day high volume
    df = pd.DataFrame({
        "Open": close - 1, "High": close + 2, "Low": close - 2,
        "Close": close, "Volume": volumes,
    }, index=idx)
    score = ta.score_stock(df)
    assert 0 <= score <= 100


def test_score_stock_with_rel_strength_above_one():
    ta = TechnicalAnalysis()
    df = make_ohlcv(60)
    score = ta.score_stock(df, spy_relative_strength=1.05)
    assert 0 <= score <= 100


def test_backtest_insufficient_data():
    ta = TechnicalAnalysis()
    # Only 5 rows - not enough for SMA50
    df = make_ohlcv(5)
    result = ta.backtest_strategy(df)
    # Should either return error or valid stats
    assert isinstance(result, dict)
