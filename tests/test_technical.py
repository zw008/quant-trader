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
