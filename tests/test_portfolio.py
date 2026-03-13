# tests/test_portfolio.py
from unittest.mock import MagicMock
from quant_trader.portfolio import Portfolio
from quant_trader.config import Config


def make_mock_conn():
    conn = MagicMock()
    pos = MagicMock()
    pos.contract.symbol = "AAPL"
    pos.position = 100
    pos.avgCost = 145.0
    conn.ib.positions.return_value = [pos]
    acc = MagicMock()
    acc.tag = "NetLiquidation"
    acc.value = "50000.0"
    acc2 = MagicMock()
    acc2.tag = "BuyingPower"
    acc2.value = "30000.0"
    acc3 = MagicMock()
    acc3.tag = "CashBalance"
    acc3.value = "20000.0"
    acc4 = MagicMock()
    acc4.tag = "UnrealizedPnL"
    acc4.value = "1500.0"
    acc5 = MagicMock()
    acc5.tag = "RealizedPnL"
    acc5.value = "500.0"
    conn.ib.accountValues.return_value = [acc, acc2, acc3, acc4, acc5]
    return conn


def test_get_positions_returns_list():
    p = Portfolio(make_mock_conn(), Config())
    positions = p.get_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"
    assert positions[0]["quantity"] == 100


def test_get_account_info_returns_net_liquidation():
    p = Portfolio(make_mock_conn(), Config())
    info = p.get_account_info()
    assert "net_liquidation" in info
    assert info["net_liquidation"] == 50000.0


def test_get_pnl_returns_totals():
    p = Portfolio(make_mock_conn(), Config())
    pnl = p.get_pnl()
    assert pnl["unrealized_pnl"] == 1500.0
    assert pnl["realized_pnl"] == 500.0
    assert pnl["total_pnl"] == 2000.0
