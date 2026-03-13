# tests/test_daily_workflow.py
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd
import numpy as np
from quant_trader.daily_workflow import DailyWorkflow
from quant_trader.config import Config
from quant_trader.trade_journal import TradeJournal


def make_workflow(tmp_dir):
    cfg = Config()
    md_mock = MagicMock()
    ta_mock = MagicMock()
    sent_mock = MagicMock()
    fund_mock = MagicMock()

    md_mock.get_quote.return_value = {"symbol": "AAPL", "price": 175.0, "volume": 50_000_000}

    # Create a realistic DataFrame for get_ohlcv
    n = 60
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 150, n), index=idx)
    mock_df = pd.DataFrame({
        "Open": close - 1, "High": close + 2, "Low": close - 2,
        "Close": close, "Volume": [1_000_000] * n,
    }, index=idx)
    md_mock.get_ohlcv.return_value = mock_df

    # score_stock returns a number
    ta_mock.score_stock.return_value = 75.0
    ta_mock.calc_atr_targets.return_value = {
        "stop_loss": 170.0, "take_profit": 185.0, "atr": 3.5, "method": "atr_based"
    }
    ta_mock.calc_indicators.return_value = mock_df

    sent_mock.get_market_mood.return_value = {"vix": 18.0, "fear_greed": "neutral", "spy_change_pct": 0.3}
    sent_mock.get_sector_heat.return_value = [{"sector": "科技", "etf": "XLK", "change_pct": 1.2}]
    sent_mock.get_news_sentiment.return_value = [{"title": "Apple strong", "summary": "...", "published": ""}]
    fund_mock.get_financials.return_value = {"pe_ratio": 28.0, "sector": "Technology"}

    journal = TradeJournal(Path(tmp_dir))
    return DailyWorkflow(cfg, md_mock, ta_mock, sent_mock, fund_mock, journal, Path(tmp_dir))


def test_morning_briefing_creates_md_file():
    with tempfile.TemporaryDirectory() as tmp:
        wf = make_workflow(tmp)
        result = wf.morning_briefing(watchlist=["AAPL", "MSFT"], date_str="2026-03-13")
        md_path = Path(tmp) / "2026-03-13-morning.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "早报" in content
        assert "AAPL" in content
        assert "recommendations" in result


def test_morning_briefing_uses_score_threshold():
    with tempfile.TemporaryDirectory() as tmp:
        wf = make_workflow(tmp)
        # score_stock returns 75 which is > 70 threshold
        result = wf.morning_briefing(watchlist=["AAPL"], date_str="2026-03-13")
        assert len(result["recommendations"]) > 0


def test_intraday_snapshot_returns_data():
    with tempfile.TemporaryDirectory() as tmp:
        wf = make_workflow(tmp)
        # Add a pick first
        wf._journal.add_pick("2026-03-13", "AAPL", 175.0, 185.0, 170.0, "test")
        result = wf.intraday_snapshot(date_str="2026-03-13")
        assert "snapshot" in result


def test_eod_summary_calculates_win_rate():
    with tempfile.TemporaryDirectory() as tmp:
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-13", "AAPL", 175.0, 185.0, 170.0, "test")
        journal.record_outcome("2026-03-13", "AAPL", 183.0, True)
        wf = make_workflow(tmp)
        # Reload journal
        wf._journal = TradeJournal(Path(tmp))
        result = wf.eod_summary(date_str="2026-03-13")
        assert "win_rate" in result
        md_path = Path(tmp) / "2026-03-13-eod.md"
        assert md_path.exists()
