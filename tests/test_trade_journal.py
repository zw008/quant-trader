# tests/test_trade_journal.py
import json
import tempfile
from pathlib import Path
from quant_trader.trade_journal import TradeJournal


def test_add_pick_and_retrieve():
    with tempfile.TemporaryDirectory() as tmp:
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-13", "AAPL", entry_price=175.0,
                         target=185.0, stop_loss=170.0, reason="金叉+低VIX")
        picks = journal.get_picks("2026-03-13")
        assert len(picks) == 1
        assert picks[0]["symbol"] == "AAPL"


def test_record_outcome_updates_pick():
    with tempfile.TemporaryDirectory() as tmp:
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-13", "NVDA", entry_price=800.0,
                         target=850.0, stop_loss=780.0, reason="AI热度")
        journal.record_outcome("2026-03-13", "NVDA",
                               exit_price=845.0, hit_target=True)
        picks = journal.get_picks("2026-03-13")
        assert picks[0]["result"] == "win"
        assert picks[0]["pnl_pct"] > 0


def test_win_rate_calculation():
    with tempfile.TemporaryDirectory() as tmp:
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-13", "AAPL", 175.0, 185.0, 170.0, "test")
        journal.add_pick("2026-03-13", "MSFT", 380.0, 400.0, 370.0, "test")
        journal.record_outcome("2026-03-13", "AAPL", 183.0, hit_target=True)
        journal.record_outcome("2026-03-13", "MSFT", 372.0, hit_target=False)
        stats = journal.win_rate_stats("2026-03-13")
        assert stats["win_rate"] == 0.5
        assert stats["total_picks"] == 2


def test_win_rate_all_history():
    with tempfile.TemporaryDirectory() as tmp:
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-12", "AAPL", 170.0, 180.0, 165.0, "test")
        journal.add_pick("2026-03-13", "MSFT", 380.0, 400.0, 370.0, "test")
        journal.record_outcome("2026-03-12", "AAPL", 179.0, hit_target=True)
        journal.record_outcome("2026-03-13", "MSFT", 395.0, hit_target=True)
        stats = journal.win_rate_stats()  # all history
        assert stats["total_picks"] == 2
        assert stats["wins"] == 2


def test_journal_persists_to_disk():
    with tempfile.TemporaryDirectory() as tmp:
        journal1 = TradeJournal(Path(tmp))
        journal1.add_pick("2026-03-13", "TSLA", 200.0, 220.0, 190.0, "test")
        # New instance reads from disk
        journal2 = TradeJournal(Path(tmp))
        picks = journal2.get_picks("2026-03-13")
        assert len(picks) == 1
        assert picks[0]["symbol"] == "TSLA"
