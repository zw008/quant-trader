# tests/test_config.py
from quant_trader.config import Config


def test_config_defaults():
    cfg = Config._from_dict({})
    assert cfg.ib_host == "127.0.0.1"
    assert cfg.ib_port == 7497
    assert cfg.paper_mode is True


def test_config_live_mode():
    cfg = Config._from_dict({"mode": "live", "ib_port": 7496})
    assert cfg.paper_mode is False
    assert cfg.ib_port == 7496


def test_config_max_order_value():
    cfg = Config._from_dict({"max_order_value": 5000})
    assert cfg.max_order_value == 5000


def test_config_daily_loss_limit():
    cfg = Config._from_dict({"max_daily_loss": 3000})
    assert cfg.max_daily_loss == 3000


def test_config_position_sizing():
    cfg = Config._from_dict({"max_position_pct": 0.15})
    assert cfg.max_position_pct == 0.15


def test_config_watchlist():
    cfg = Config._from_dict({"watchlist": ["GOOG", "META"]})
    assert cfg.watchlist == ("GOOG", "META")


def test_config_order_plan_ttl():
    cfg = Config._from_dict({"order_plan_ttl_minutes": 10})
    assert cfg.order_plan_ttl_minutes == 10


def test_config_live_double_confirm():
    cfg = Config._from_dict({"mode": "live"})
    assert cfg.live_double_confirm is True
