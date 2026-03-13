from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from ib_insync import LimitOrder, MarketOrder, Stock

from quant_trader.config import Config
from quant_trader.connection import IBConnection

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DIR = Path.home() / "quant-trader-reports"


class OrderManager:
    """Plan -> Confirm -> Execute order workflow with safety guards."""

    def __init__(
        self,
        conn: IBConnection,
        config: Config,
        audit_dir: Path = DEFAULT_AUDIT_DIR,
    ) -> None:
        self._conn = conn
        self._cfg = config
        self._plans: dict[str, dict] = {}
        self._audit_dir = audit_dir
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        self._audit_path = self._audit_dir / "audit.json"

    def _write_audit(self, entry: dict) -> None:
        """Append an audit entry to audit.json."""
        entries: list[dict] = []
        if self._audit_path.exists():
            try:
                entries = json.loads(self._audit_path.read_text())
            except (json.JSONDecodeError, OSError):
                entries = []
        entry["timestamp"] = datetime.now().isoformat()
        entries.append(entry)
        self._audit_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2)
        )

    def create_order_plan(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str = "LMT",
        limit_price: float | None = None,
    ) -> dict:
        """Create order plan (does not execute). Rejects if over max_order_value."""
        action = action.upper()
        if action not in ("BUY", "SELL"):
            raise ValueError(f"Invalid action: {action}")

        if limit_price is not None and limit_price > 0:
            estimated_value = limit_price * quantity
            if estimated_value > self._cfg.max_order_value:
                raise ValueError(
                    f"Order value ${estimated_value:.2f} exceeds "
                    f"max_order_value ${self._cfg.max_order_value:.2f}"
                )

        plan_id = str(uuid.uuid4())[:8]
        plan = {
            "plan_id": plan_id,
            "symbol": symbol.upper(),
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
            "limit_price": limit_price,
            "mode": "paper" if self._cfg.paper_mode else "live",
            "status": "pending_confirmation",
            "created_at": datetime.now().isoformat(),
        }
        self._plans[plan_id] = plan
        self._write_audit({"action": "plan_created", "plan": plan.copy()})
        logger.info("Order plan created: %s", plan)
        return plan

    def confirm_order(
        self, plan_id: str, confirm_live: bool = False
    ) -> dict:
        """Confirm and submit order to IB TWS.

        Safety checks:
        - Order plan expiration (order_plan_ttl_minutes)
        - Live mode requires confirm_live=True (double confirmation)
        """
        plan = self._plans[plan_id]  # KeyError if not found

        # Check expiration
        created = datetime.fromisoformat(plan["created_at"])
        ttl = timedelta(minutes=self._cfg.order_plan_ttl_minutes)
        if datetime.now() - created > ttl:
            plan["status"] = "expired"
            self._write_audit({"action": "plan_expired", "plan_id": plan_id})
            raise ValueError(
                f"Order plan {plan_id} expired "
                f"(TTL={self._cfg.order_plan_ttl_minutes}min)"
            )

        # Live mode double confirmation
        if not self._cfg.paper_mode and self._cfg.live_double_confirm:
            if not confirm_live:
                raise ValueError(
                    "Live mode requires confirm_live=True for double "
                    "confirmation. This is a REAL ORDER with real money."
                )
            logger.warning("LIVE ORDER SUBMITTED: %s", plan)

        contract = Stock(plan["symbol"], "SMART", "USD")
        if plan["order_type"] == "MKT":
            order = MarketOrder(plan["action"], plan["quantity"])
        else:
            order = LimitOrder(
                plan["action"], plan["quantity"], plan["limit_price"]
            )

        trade = self._conn.ib.placeOrder(contract, order)
        plan["status"] = "submitted"
        plan["ib_order_id"] = trade.order.orderId
        self._write_audit(
            {
                "action": "order_submitted",
                "plan_id": plan_id,
                "ib_order_id": trade.order.orderId,
            }
        )
        return plan

    def cancel_order(self, plan_id: str) -> dict:
        """Cancel a planned or submitted order."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise KeyError(f"Plan {plan_id} not found")

        if plan.get("ib_order_id"):
            from ib_insync import Order as IBOrder

            o = IBOrder()
            o.orderId = plan["ib_order_id"]
            self._conn.ib.cancelOrder(o)

        plan["status"] = "cancelled"
        self._write_audit({"action": "order_cancelled", "plan_id": plan_id})
        return plan

    def get_order_status(self, plan_id: str) -> dict:
        """Get the current status of an order plan."""
        return self._plans.get(plan_id, {"error": "plan not found"})

    def list_plans(self) -> list[dict]:
        """List all order plans."""
        return list(self._plans.values())
