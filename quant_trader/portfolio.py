from __future__ import annotations
from quant_trader.connection import IBConnection
from quant_trader.config import Config


class Portfolio:
    def __init__(self, conn: IBConnection, config: Config) -> None:
        self._conn = conn
        self._cfg = config

    def get_positions(self) -> list[dict]:
        positions = []
        for p in self._conn.ib.positions():
            positions.append({
                "symbol": p.contract.symbol,
                "quantity": p.position,
                "avg_cost": round(p.avgCost, 4),
            })
        return positions

    def get_account_info(self) -> dict:
        values = {v.tag: v.value for v in self._conn.ib.accountValues()}
        return {
            "net_liquidation": float(values.get("NetLiquidation", 0)),
            "buying_power": float(values.get("BuyingPower", 0)),
            "cash_balance": float(values.get("CashBalance", 0)),
            "unrealized_pnl": float(values.get("UnrealizedPnL", 0)),
            "realized_pnl": float(values.get("RealizedPnL", 0)),
        }

    def get_pnl(self) -> dict:
        info = self.get_account_info()
        return {
            "unrealized_pnl": info["unrealized_pnl"],
            "realized_pnl": info["realized_pnl"],
            "total_pnl": info["unrealized_pnl"] + info["realized_pnl"],
        }
