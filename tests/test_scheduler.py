# tests/test_scheduler.py
from unittest.mock import patch, MagicMock
from quant_trader.scheduler import run_scheduler, SCHEDULE, ET


def test_schedule_entries():
    """Verify SCHEDULE has expected entries."""
    assert len(SCHEDULE) == 4
    times = [t for t, _ in SCHEDULE]
    assert "08:00" in times
    assert "12:00" in times
    assert "15:00" in times
    assert "16:30" in times


def test_schedule_actions():
    actions = [a for _, a in SCHEDULE]
    assert "morning" in actions
    assert "intraday" in actions
    assert "eod" in actions


def test_et_timezone():
    assert str(ET) == "America/New_York"


@patch("quant_trader.scheduler.DailyWorkflow")
@patch("quant_trader.scheduler.TradeJournal")
@patch("quant_trader.scheduler.Fundamental")
@patch("quant_trader.scheduler.MarketSentiment")
@patch("quant_trader.scheduler.TechnicalAnalysis")
@patch("quant_trader.scheduler.MarketData")
@patch("quant_trader.scheduler.CachedProvider")
@patch("quant_trader.scheduler.YFinanceProvider")
@patch("quant_trader.scheduler.Config")
@patch("quant_trader.scheduler.time")
@patch("quant_trader.scheduler.datetime")
def test_run_scheduler_fires_morning(
    mock_datetime, mock_time, mock_config,
    mock_yf, mock_cached, mock_md, mock_ta,
    mock_sent, mock_fund, mock_journal, mock_workflow_class,
):
    """Test that scheduler fires morning action at 08:00."""
    mock_config.load.return_value = MagicMock()
    mock_workflow = MagicMock()
    mock_workflow_class.return_value = mock_workflow

    # First call returns 08:00, second call raises to exit the loop
    call_count = {"n": 0}
    def fake_now(tz):
        call_count["n"] += 1
        m = MagicMock()
        if call_count["n"] <= 1:
            m.strftime.side_effect = lambda fmt: "08:00" if fmt == "%H:%M" else "2026-03-13"
        else:
            raise StopIteration("exit loop")
        return m

    mock_datetime.now.side_effect = fake_now

    try:
        run_scheduler(["AAPL", "MSFT"])
    except StopIteration:
        pass

    mock_workflow.morning_briefing.assert_called_once_with(["AAPL", "MSFT"])


@patch("quant_trader.scheduler.DailyWorkflow")
@patch("quant_trader.scheduler.TradeJournal")
@patch("quant_trader.scheduler.Fundamental")
@patch("quant_trader.scheduler.MarketSentiment")
@patch("quant_trader.scheduler.TechnicalAnalysis")
@patch("quant_trader.scheduler.MarketData")
@patch("quant_trader.scheduler.CachedProvider")
@patch("quant_trader.scheduler.YFinanceProvider")
@patch("quant_trader.scheduler.Config")
@patch("quant_trader.scheduler.time")
@patch("quant_trader.scheduler.datetime")
def test_run_scheduler_handles_error(
    mock_datetime, mock_time, mock_config,
    mock_yf, mock_cached, mock_md, mock_ta,
    mock_sent, mock_fund, mock_journal, mock_workflow_class,
):
    """Test that scheduler catches workflow errors gracefully."""
    mock_config.load.return_value = MagicMock()
    mock_workflow = MagicMock()
    mock_workflow.morning_briefing.side_effect = RuntimeError("API down")
    mock_workflow_class.return_value = mock_workflow

    call_count = {"n": 0}
    def fake_now(tz):
        call_count["n"] += 1
        m = MagicMock()
        if call_count["n"] <= 1:
            m.strftime.side_effect = lambda fmt: "08:00" if fmt == "%H:%M" else "2026-03-13"
        else:
            raise StopIteration("exit loop")
        return m

    mock_datetime.now.side_effect = fake_now

    # Should not raise despite workflow error
    try:
        run_scheduler(["AAPL"])
    except StopIteration:
        pass

    mock_workflow.morning_briefing.assert_called_once()
