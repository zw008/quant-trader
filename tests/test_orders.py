# tests/test_orders.py
import json
import tempfile
import time

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from quant_trader.orders import OrderManager
from quant_trader.config import Config


def make_conn():
    conn = MagicMock()
    conn.is_connected = True
    return conn


def test_create_plan_returns_plan_id():
    om = OrderManager(make_conn(), Config())
    plan = om.create_order_plan("AAPL", "BUY", 10, order_type="MKT")
    assert "plan_id" in plan
    assert plan["symbol"] == "AAPL"
    assert plan["status"] == "pending_confirmation"
    assert "created_at" in plan


def test_create_plan_rejects_over_limit():
    cfg = Config._from_dict({"max_order_value": 100})
    om = OrderManager(make_conn(), cfg)
    with pytest.raises(ValueError, match="exceeds max_order_value"):
        om.create_order_plan("AAPL", "BUY", 10, limit_price=50.0)


def test_confirm_order_requires_existing_plan():
    om = OrderManager(make_conn(), Config())
    with pytest.raises(KeyError):
        om.confirm_order("nonexistent-plan-id")


def test_paper_mode_logged_in_plan():
    om = OrderManager(make_conn(), Config._from_dict({"mode": "paper"}))
    plan = om.create_order_plan("AAPL", "BUY", 1, limit_price=150.0)
    assert plan["mode"] == "paper"


def test_order_plan_expires():
    cfg = Config._from_dict({"order_plan_ttl_minutes": 0})  # immediate expiry
    om = OrderManager(make_conn(), cfg)
    plan = om.create_order_plan("AAPL", "BUY", 1, order_type="MKT")
    time.sleep(0.1)
    with pytest.raises(ValueError, match="expired"):
        om.confirm_order(plan["plan_id"])


def test_live_mode_requires_double_confirm():
    cfg = Config._from_dict({"mode": "live", "live_double_confirm": True})
    om = OrderManager(make_conn(), cfg)
    plan = om.create_order_plan("AAPL", "BUY", 1, order_type="MKT")
    with pytest.raises(ValueError, match="confirm_live"):
        om.confirm_order(plan["plan_id"])


def test_live_mode_works_with_double_confirm():
    cfg = Config._from_dict({"mode": "live", "live_double_confirm": True})
    conn = make_conn()
    trade_mock = MagicMock()
    trade_mock.order.orderId = 12345
    conn.ib.placeOrder.return_value = trade_mock
    om = OrderManager(conn, cfg)
    plan = om.create_order_plan("AAPL", "BUY", 1, order_type="MKT")
    result = om.confirm_order(plan["plan_id"], confirm_live=True)
    assert result["status"] == "submitted"


def test_audit_log_written():
    with tempfile.TemporaryDirectory() as tmp:
        om = OrderManager(make_conn(), Config(), audit_dir=Path(tmp))
        om.create_order_plan("AAPL", "BUY", 5, order_type="MKT")
        audit_path = Path(tmp) / "audit.json"
        assert audit_path.exists()
        entries = json.loads(audit_path.read_text())
        assert len(entries) == 1
        assert entries[0]["action"] == "plan_created"


def test_cancel_order():
    om = OrderManager(make_conn(), Config())
    plan = om.create_order_plan("AAPL", "BUY", 1, order_type="MKT")
    result = om.cancel_order(plan["plan_id"])
    assert result["status"] == "cancelled"
