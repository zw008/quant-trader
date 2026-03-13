from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".quant-trader" / "config.yaml"


@dataclass(frozen=True)
class Config:
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 1
    paper_mode: bool = True
    max_order_value: float = 10_000.0
    data_source: str = "ib"
    max_daily_loss: float = 2000.0
    max_position_pct: float = 0.2
    watchlist: tuple[str, ...] = ("AAPL", "MSFT", "NVDA", "TSLA", "AMZN")
    order_plan_ttl_minutes: int = 5
    live_double_confirm: bool = True

    @classmethod
    def _from_dict(cls, d: dict) -> Config:
        mode = d.get("mode", "paper")
        raw_watchlist = d.get("watchlist", ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"])
        return cls(
            ib_host=d.get("ib_host", "127.0.0.1"),
            ib_port=d.get("ib_port", 7497 if mode == "paper" else 7496),
            ib_client_id=d.get("ib_client_id", 1),
            paper_mode=(mode != "live"),
            max_order_value=float(d.get("max_order_value", 10_000.0)),
            data_source=d.get("data_source", "ib"),
            max_daily_loss=float(d.get("max_daily_loss", 2000.0)),
            max_position_pct=float(d.get("max_position_pct", 0.2)),
            watchlist=tuple(raw_watchlist),
            order_plan_ttl_minutes=int(d.get("order_plan_ttl_minutes", 5)),
            live_double_confirm=d.get("live_double_confirm", True),
        )

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> Config:
        if not path.exists():
            return cls()
        with open(path) as f:
            return cls._from_dict(yaml.safe_load(f) or {})
