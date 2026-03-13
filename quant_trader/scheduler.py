"""
Optional daily scheduler. Usage:
  uv run python -m quant_trader.scheduler --watchlist AAPL MSFT NVDA TSLA

Schedule (ET timezone):
  08:00  → morning_briefing (90 min before open)
  12:00  → intraday_snapshot (midday)
  15:00  → intraday_snapshot (pre-close)
  16:30  → eod_summary (30 min after close)
"""
import argparse
import time
import logging
from datetime import datetime

import pytz

from quant_trader.config import Config
from quant_trader.data_provider import YFinanceProvider, CachedProvider
from quant_trader.market_data import MarketData
from quant_trader.technical import TechnicalAnalysis
from quant_trader.sentiment import MarketSentiment
from quant_trader.fundamental import Fundamental
from quant_trader.trade_journal import TradeJournal
from quant_trader.daily_workflow import DailyWorkflow

ET = pytz.timezone("America/New_York")

SCHEDULE = [
    ("08:00", "morning"),
    ("12:00", "intraday"),
    ("15:00", "intraday"),
    ("16:30", "eod"),
]


def run_scheduler(watchlist: list[str]) -> None:
    cfg = Config.load()
    provider = CachedProvider(YFinanceProvider())
    workflow = DailyWorkflow(
        cfg, MarketData(provider), TechnicalAnalysis(),
        MarketSentiment(provider), Fundamental(provider), TradeJournal(),
    )
    fired: set[str] = set()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.info("Scheduler started. Watchlist: %s", watchlist)

    while True:
        now = datetime.now(ET)
        now_str = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        # Reset fired set at midnight
        if now_str == "00:00":
            fired.clear()

        for trigger_time, action in SCHEDULE:
            key = f"{today}-{trigger_time}-{action}"
            if now_str == trigger_time and key not in fired:
                fired.add(key)
                logging.info("Firing: %s @ %s ET", action, now_str)
                try:
                    if action == "morning":
                        workflow.morning_briefing(watchlist)
                    elif action == "intraday":
                        workflow.intraday_snapshot()
                    elif action == "eod":
                        workflow.eod_summary()
                except Exception as e:
                    logging.error("Scheduler error (%s): %s", action, e)
        time.sleep(30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="quant-trader daily scheduler")
    parser.add_argument("--watchlist", nargs="+",
                        default=["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"])
    args = parser.parse_args()
    run_scheduler(args.watchlist)
