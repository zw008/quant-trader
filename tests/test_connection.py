# tests/test_connection.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from quant_trader.connection import IBConnection
from quant_trader.config import Config


def test_connection_uses_paper_port():
    cfg = Config._from_dict({"mode": "paper"})
    conn = IBConnection(cfg)
    assert conn.port == 7497


def test_connection_uses_live_port():
    cfg = Config._from_dict({"mode": "live"})
    conn = IBConnection(cfg)
    assert conn.port == 7496


def test_connection_not_connected_initially():
    cfg = Config()
    conn = IBConnection(cfg)
    assert not conn.is_connected


@patch("quant_trader.connection.IB")
def test_connect_calls_ib(mock_ib_class):
    mock_ib = MagicMock()
    mock_ib_class.return_value = mock_ib
    cfg = Config()
    conn = IBConnection(cfg)
    conn.connect()
    mock_ib.connect.assert_called_once_with("127.0.0.1", 7497, clientId=1)


def test_ib_property_raises_when_not_connected():
    cfg = Config()
    conn = IBConnection(cfg)
    with pytest.raises(RuntimeError, match="Not connected"):
        _ = conn.ib


@patch("quant_trader.connection.IB")
def test_reconnect_on_failure(mock_ib_class):
    mock_ib = MagicMock()
    mock_ib.connect.side_effect = [ConnectionError("fail"), ConnectionError("fail"), None]
    mock_ib.isConnected.return_value = True
    mock_ib_class.return_value = mock_ib
    cfg = Config()
    conn = IBConnection(cfg)
    conn.connect(max_retries=3, backoff_base=0.01)  # fast backoff for test
    assert mock_ib.connect.call_count == 3


@patch("quant_trader.connection.IB")
def test_reconnect_exhausted_raises(mock_ib_class):
    mock_ib = MagicMock()
    mock_ib.connect.side_effect = ConnectionError("always fail")
    mock_ib_class.return_value = mock_ib
    cfg = Config()
    conn = IBConnection(cfg)
    with pytest.raises(ConnectionError):
        conn.connect(max_retries=2, backoff_base=0.01)
