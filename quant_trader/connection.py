from __future__ import annotations

import logging
import time

from ib_insync import IB

from quant_trader.config import Config

logger = logging.getLogger(__name__)


class IBConnection:
    def __init__(self, config: Config) -> None:
        self._cfg = config
        self._ib: IB | None = None

    @property
    def port(self) -> int:
        return self._cfg.ib_port

    @property
    def is_connected(self) -> bool:
        return self._ib is not None and self._ib.isConnected()

    def connect(self, max_retries: int = 3, backoff_base: float = 2.0) -> None:
        """Connect to IB TWS with exponential backoff retry."""
        self._ib = IB()
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                self._ib.connect(
                    self._cfg.ib_host,
                    self._cfg.ib_port,
                    clientId=self._cfg.ib_client_id,
                )
                logger.info(
                    "Connected to IB TWS (port=%s, paper=%s, attempt=%d)",
                    self.port,
                    self._cfg.paper_mode,
                    attempt + 1,
                )
                return
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = backoff_base**attempt
                    logger.warning(
                        "IB connect attempt %d/%d failed: %s. Retrying in %.1fs",
                        attempt + 1,
                        max_retries,
                        e,
                        wait,
                    )
                    time.sleep(wait)
        raise ConnectionError(
            f"Failed to connect after {max_retries} attempts"
        ) from last_error

    def disconnect(self) -> None:
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()
            logger.info("Disconnected from IB TWS")

    @property
    def ib(self) -> IB:
        if not self.is_connected:
            raise RuntimeError("Not connected to IB TWS. Call connect() first.")
        return self._ib  # type: ignore[return-value]
