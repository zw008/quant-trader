from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_REPORTS_DIR = Path.home() / "quant-trader-reports"


@dataclass
class StockPick:
    symbol: str
    entry_price: float
    target: float
    stop_loss: float
    reason: str
    exit_price: float | None = None
    hit_target: bool | None = None
    result: str = "open"
    pnl_pct: float = 0.0


class TradeJournal:
    def __init__(self, reports_dir: Path = DEFAULT_REPORTS_DIR) -> None:
        self._dir = reports_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._dir / "journal.json"
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self._db_path.exists():
            return json.loads(self._db_path.read_text())
        return {}

    def _save(self) -> None:
        self._db_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2)
        )

    def add_pick(
        self,
        date_str: str,
        symbol: str,
        entry_price: float,
        target: float,
        stop_loss: float,
        reason: str,
    ) -> None:
        self._data.setdefault(date_str, [])
        pick = StockPick(
            symbol=symbol.upper(),
            entry_price=entry_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
        )
        self._data[date_str].append(asdict(pick))
        self._save()

    def record_outcome(
        self,
        date_str: str,
        symbol: str,
        exit_price: float,
        hit_target: bool,
    ) -> None:
        for pick in self._data.get(date_str, []):
            if pick["symbol"] == symbol.upper():
                pick["exit_price"] = exit_price
                pick["hit_target"] = hit_target
                pick["result"] = "win" if hit_target else "loss"
                pnl = (exit_price - pick["entry_price"]) / pick["entry_price"]
                pick["pnl_pct"] = round(pnl * 100, 2)
        self._save()

    def get_picks(self, date_str: str) -> list[dict]:
        return self._data.get(date_str, [])

    def win_rate_stats(self, date_str: str | None = None) -> dict:
        all_picks: list[dict] = []
        if date_str:
            all_picks = [
                p
                for p in self._data.get(date_str, [])
                if p["result"] != "open"
            ]
        else:
            for picks in self._data.values():
                all_picks.extend(p for p in picks if p["result"] != "open")
        total = len(all_picks)
        wins = sum(1 for p in all_picks if p["result"] == "win")
        avg_pnl = (
            sum(p["pnl_pct"] for p in all_picks) / total if total else 0
        )
        return {
            "total_picks": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total, 3) if total else 0.0,
            "avg_pnl_pct": round(avg_pnl, 2),
        }
