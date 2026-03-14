# quant-trader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a quantitative trading MCP Server + Claude Code Skill that connects to Interactive Brokers TWS for US stocks, with technical, sentiment, and fundamental analysis tools, using a Plan→Confirm→Execute safety model for orders.

**Architecture:** Python async MCP Server (`ib_insync` + `pandas-ta` + `yfinance`) exposing 30+ tools across 8 categories. DataProvider Protocol abstracts data sources (IB primary, yfinance fallback). TTLCache prevents redundant API calls. Orders require Plan→Confirm two-step with expiration. Paper mode is default; live mode requires double-confirmation.

**Tech Stack:** `ib_insync`, `pandas-ta`, `yfinance`, `akshare`(future), `feedparser`, `cachetools`, `mcp`, `uv`

---

## 模型选择指南

| 阶段 | 推荐模型 | 原因 |
|------|---------|------|
| 项目脚手架、配置、boilerplate | **Sonnet 4.6** | 统一模型，质量更好 |
| MCP Server 核心、连接层、数据工具 | **Sonnet 4.6** | 主力编码，平衡质量与速度 |
| 技术指标、基本面、持仓工具 | **Sonnet 4.6** | 标准编码任务 |
| 订单 Plan→Confirm→Execute 安全设计 | **Opus 4.6** | 涉及资金安全，需要最严密的推理 |
| SKILL.md 编写、文档 | **Sonnet 4.6** | 结构化写作 |
| 测试设计（边界条件、安全用例） | **Opus 4.6** | 金融场景测试边界复杂 |
| Debug / 单文件小修改 | **Sonnet 4.6** | 统一模型，质量更好 |

---

## Task 1: 项目脚手架

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `quant-trader/pyproject.toml`
- Create: `quant-trader/quant_trader/__init__.py`
- Create: `quant-trader/mcp_server/__init__.py`
- Create: `quant-trader/mcp_server/server.py`
- Create: `quant-trader/tests/__init__.py`
- Create: `quant-trader/.gitignore`

**Step 1: 创建项目目录**

```bash
mkdir -p /Users/zw/testany/myskills/quant-trader
cd /Users/zw/testany/myskills/quant-trader
mkdir -p quant_trader mcp_server tests skills/quant-trader examples/mcp-configs docs
```

**Step 2: 创建 pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "quant-trader"
version = "0.1.0"
description = "MCP Server for quantitative trading via Interactive Brokers"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0,<2.0",
    "ib_insync>=0.9,<1.0",
    "pandas>=2.0,<3.0",
    "pandas-ta>=0.3,<1.0",
    "yfinance>=0.2,<1.0",
    "feedparser>=6.0,<7.0",
    "pyyaml>=6.0,<7.0",
    "python-dotenv>=1.0,<2.0",
    "httpx>=0.27,<1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0,<9.0", "pytest-asyncio>=0.23,<1.0", "pytest-cov>=5.0,<6.0"]

[project.scripts]
quant-trader = "quant_trader.cli:main"
```

**Step 3: 创建 `quant_trader/__init__.py`**

```python
__version__ = "0.1.0"
```

**Step 4: git init + 首次 commit**

```bash
cd /Users/zw/testany/myskills/quant-trader
git init
git add .
git commit -m "feat: project scaffold"
```

Expected: repo initialized, first commit created.

---

## Task 2: 配置系统

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `quant_trader/config.py`
- Create: `tests/test_config.py`
- Create: `~/.quant-trader/config.yaml` (示例，运行时创建)

**Step 1: 写失败测试**

```python
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

def test_config_opus_review_fields():
    cfg = Config._from_dict({})
    assert cfg.max_daily_loss == 2000.0
    assert cfg.max_position_pct == 0.2
    assert cfg.watchlist == ["AAPL","MSFT","NVDA","TSLA","AMZN"]
    assert cfg.order_plan_ttl_minutes == 5
    assert cfg.live_double_confirm is True

def test_config_custom_watchlist():
    cfg = Config._from_dict({"watchlist": ["GOOG","META"], "max_daily_loss": 500})
    assert cfg.watchlist == ["GOOG","META"]
    assert cfg.max_daily_loss == 500.0
```

**Step 2: 运行确认失败**

```bash
cd /Users/zw/testany/myskills/quant-trader
uv run pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: 实现 `quant_trader/config.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml, os

DEFAULT_CONFIG_PATH = Path.home() / ".quant-trader" / "config.yaml"

@dataclass(frozen=True)
class Config:
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497          # 7497=paper, 7496=live TWS
    ib_client_id: int = 1
    paper_mode: bool = True
    max_order_value: float = 10_000.0   # 单笔最大订单金额(USD)
    data_source: str = "ib"      # ib | yfinance
    # New fields from Opus review
    max_daily_loss: float = 2000.0       # 每日最大亏损(USD)
    max_position_pct: float = 0.2        # 单只股票最大仓位占比(20%)
    watchlist: list[str] = field(default_factory=lambda: ["AAPL","MSFT","NVDA","TSLA","AMZN"])
    order_plan_ttl_minutes: int = 5      # 订单计划过期时间(分钟)
    live_double_confirm: bool = True     # 实盘需二次确认

    @classmethod
    def _from_dict(cls, d: dict) -> "Config":
        mode = d.get("mode", "paper")
        return cls(
            ib_host=d.get("ib_host", "127.0.0.1"),
            ib_port=d.get("ib_port", 7497 if mode == "paper" else 7496),
            ib_client_id=d.get("ib_client_id", 1),
            paper_mode=(mode != "live"),
            max_order_value=float(d.get("max_order_value", 10_000.0)),
            data_source=d.get("data_source", "ib"),
            max_daily_loss=float(d.get("max_daily_loss", 2000.0)),
            max_position_pct=float(d.get("max_position_pct", 0.2)),
            watchlist=d.get("watchlist", ["AAPL","MSFT","NVDA","TSLA","AMZN"]),
            order_plan_ttl_minutes=int(d.get("order_plan_ttl_minutes", 5)),
            live_double_confirm=d.get("live_double_confirm", True),
        )

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "Config":
        if not path.exists():
            return cls()
        with open(path) as f:
            return cls._from_dict(yaml.safe_load(f) or {})
```

**Step 4: 运行确认通过**

```bash
uv run pytest tests/test_config.py -v
```
Expected: 5 passed

**Step 5: Commit**

```bash
git add quant_trader/config.py tests/test_config.py
git commit -m "feat: config system with paper/live mode"
```

---

## Task 2.5: DataProvider Protocol + TTLCache

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `quant_trader/data_provider.py`
- Create: `tests/test_data_provider.py`

基础数据抽象层和缓存，所有数据工具通过此层获取数据。

> ⚡ **Opus Review**: yfinance 不可靠且有频率限制，需要抽象层 + 缓存。

**Implementation includes:**
- `DataProvider` Protocol (get_quote, get_ohlcv, get_info)
- `YFinanceProvider` implementation
- `IBProvider` implementation (future, when IB connected)
- `CachedProvider` wrapper with TTLCache (quotes: 60s, fundamentals: 3600s)

**Step 1: 写失败测试**

```python
# tests/test_data_provider.py
from unittest.mock import patch, MagicMock
from quant_trader.data_provider import YFinanceProvider, CachedProvider

def test_yfinance_provider_get_quote():
    with patch("quant_trader.data_provider.yf.Ticker") as mock:
        mock.return_value.info = {"regularMarketPrice": 150.0}
        provider = YFinanceProvider()
        quote = provider.get_quote("AAPL")
        assert quote["price"] == 150.0

def test_cached_provider_deduplicates():
    inner = MagicMock()
    inner.get_quote.return_value = {"price": 150.0}
    cached = CachedProvider(inner, quote_ttl=60)
    cached.get_quote("AAPL")
    cached.get_quote("AAPL")
    assert inner.get_quote.call_count == 1  # cached, not called twice

def test_cached_provider_get_info_caches():
    inner = MagicMock()
    inner.get_info.return_value = {"pe_ratio": 28.0}
    cached = CachedProvider(inner, info_ttl=3600)
    cached.get_info("AAPL")
    cached.get_info("AAPL")
    assert inner.get_info.call_count == 1
```

**Step 2: 实现 `quant_trader/data_provider.py`**

```python
from __future__ import annotations
from typing import Protocol
import pandas as pd
import yfinance as yf
from cachetools import TTLCache

class DataProvider(Protocol):
    def get_quote(self, symbol: str) -> dict: ...
    def get_ohlcv(self, symbol: str, period: str, interval: str) -> pd.DataFrame: ...
    def get_info(self, symbol: str) -> dict: ...

class YFinanceProvider:
    def get_quote(self, symbol: str) -> dict:
        info = yf.Ticker(symbol).info
        return {"symbol": symbol, "price": info.get("regularMarketPrice"),
                "bid": info.get("bid"), "ask": info.get("ask"),
                "volume": info.get("volume")}

    def get_ohlcv(self, symbol: str, period: str = "3mo",
                  interval: str = "1d") -> pd.DataFrame:
        return yf.download(symbol, period=period, interval=interval,
                           progress=False, auto_adjust=True)

    def get_info(self, symbol: str) -> dict:
        return yf.Ticker(symbol).info

class CachedProvider:
    def __init__(self, inner: DataProvider, quote_ttl: int = 60,
                 info_ttl: int = 3600) -> None:
        self._inner = inner
        self._quote_cache: TTLCache = TTLCache(maxsize=256, ttl=quote_ttl)
        self._info_cache: TTLCache = TTLCache(maxsize=256, ttl=info_ttl)

    def get_quote(self, symbol: str) -> dict:
        if symbol not in self._quote_cache:
            self._quote_cache[symbol] = self._inner.get_quote(symbol)
        return self._quote_cache[symbol]

    def get_ohlcv(self, symbol: str, period: str = "3mo",
                  interval: str = "1d") -> pd.DataFrame:
        return self._inner.get_ohlcv(symbol, period, interval)  # not cached

    def get_info(self, symbol: str) -> dict:
        if symbol not in self._info_cache:
            self._info_cache[symbol] = self._inner.get_info(symbol)
        return self._info_cache[symbol]
```

**Step 3: 运行测试**

```bash
uv run pytest tests/test_data_provider.py -v
```
Expected: 3 passed

**Step 4: Commit**

```bash
git add quant_trader/data_provider.py tests/test_data_provider.py
git commit -m "feat: DataProvider Protocol with TTLCache wrapper"
```

---

## Task 3: IB 连接层

> 推荐模型：**Sonnet 4.6**

> ⚡ **Opus Review 改进**:
> - 全部方法改为 `async`（ib_insync 是 asyncio 驱动）
> - 新增自动重连机制（max_retries=3, backoff 2^n 秒）
> - 新增 `@property async_ib` 检查连接状态后返回

**Files:**
- Create: `quant_trader/connection.py`
- Create: `tests/test_connection.py`

**Step 1: 写失败测试（mock IB）**

```python
# tests/test_connection.py
from unittest.mock import patch, MagicMock
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
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_connection.py -v
```

**Step 3: 实现 `quant_trader/connection.py`**

```python
from __future__ import annotations
import asyncio
from ib_insync import IB
from quant_trader.config import Config
import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

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

    async def connect(self) -> None:
        """连接 IB TWS，带指数退避自动重连（max_retries=3）"""
        for attempt in range(MAX_RETRIES):
            try:
                self._ib = IB()
                await self._ib.connectAsync(
                    self._cfg.ib_host,
                    self._cfg.ib_port,
                    clientId=self._cfg.ib_client_id,
                )
                logger.info("Connected to IB TWS (port=%s, paper=%s)", self.port, self._cfg.paper_mode)
                return
            except Exception as e:
                wait = 2 ** attempt
                logger.warning("IB connect attempt %d/%d failed: %s. Retry in %ds",
                               attempt + 1, MAX_RETRIES, e, wait)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
        raise ConnectionError(f"Failed to connect to IB TWS after {MAX_RETRIES} attempts")

    async def disconnect(self) -> None:
        if self._ib and self._ib.isConnected():
            self._ib.disconnect()
            logger.info("Disconnected from IB TWS")

    @property
    def ib(self) -> IB:
        if not self.is_connected:
            raise RuntimeError("Not connected to IB TWS. Call connect() first.")
        return self._ib  # type: ignore

    @property
    def async_ib(self) -> IB:
        """检查连接状态后返回 IB 实例，断开时自动重连"""
        if not self.is_connected:
            raise RuntimeError("Not connected to IB TWS. Call await connect() first.")
        return self._ib  # type: ignore
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_connection.py -v
```
Expected: 4 passed

**Step 5: Commit**

```bash
git add quant_trader/connection.py tests/test_connection.py
git commit -m "feat: IB TWS connection layer"
```

---

## Task 4: 行情数据工具

> 推荐模型：**Sonnet 4.6**

> ⚡ **Opus Review 改进**:
> - 新增 `DataProvider` Protocol 抽象数据源（IB / yfinance 可切换）
> - 新增 `TTLCache`（报价60秒、基本面1小时）防止重复API调用
> - yfinance 作为 fallback，IB 连接时优先用 IB 数据

**Files:**
- Create: `quant_trader/data_provider.py`
- Create: `quant_trader/market_data.py`
- Create: `tests/test_data_provider.py`
- Create: `tests/test_market_data.py`

**Step 1: 写失败测试（mock yfinance）**

```python
# tests/test_market_data.py
from unittest.mock import patch, MagicMock
import pandas as pd
from quant_trader.market_data import MarketData
from quant_trader.config import Config

def make_mock_ticker(price=150.0):
    mock = MagicMock()
    mock.info = {"regularMarketPrice": price, "bid": 149.9, "ask": 150.1,
                 "volume": 1_000_000, "marketCap": 2_000_000_000}
    return mock

def test_get_quote_returns_price():
    with patch("quant_trader.market_data.yf.Ticker", return_value=make_mock_ticker(150.0)):
        md = MarketData(Config())
        q = md.get_quote("AAPL")
        assert q["symbol"] == "AAPL"
        assert q["price"] == 150.0

def test_get_ohlcv_returns_dataframe():
    mock_df = pd.DataFrame({"Open":[100],"High":[110],"Low":[95],"Close":[105],"Volume":[1000]})
    with patch("quant_trader.market_data.yf.download", return_value=mock_df):
        md = MarketData(Config())
        df = md.get_ohlcv("AAPL", period="1mo", interval="1d")
        assert not df.empty
        assert "Close" in df.columns
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_market_data.py -v
```

**Step 3: 实现 `quant_trader/market_data.py`**

```python
from __future__ import annotations
import yfinance as yf
import pandas as pd
from quant_trader.config import Config


class MarketData:
    def __init__(self, config: Config) -> None:
        self._cfg = config

    def get_quote(self, symbol: str) -> dict:
        """实时报价：价格、买卖盘、成交量、市值"""
        t = yf.Ticker(symbol)
        info = t.info
        return {
            "symbol": symbol.upper(),
            "price": info.get("regularMarketPrice"),
            "bid": info.get("bid"),
            "ask": info.get("ask"),
            "volume": info.get("volume"),
            "market_cap": info.get("marketCap"),
        }

    def get_ohlcv(self, symbol: str, period: str = "3mo",
                  interval: str = "1d") -> pd.DataFrame:
        """K线历史数据。period: 1d/5d/1mo/3mo/1y. interval: 1m/5m/1h/1d"""
        df = yf.download(symbol, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        return df

    def screen_stocks(self, symbols: list[str],
                      min_volume: int = 1_000_000) -> list[dict]:
        """批量筛选：过滤成交量、返回涨跌幅排序"""
        results = []
        for sym in symbols:
            try:
                info = yf.Ticker(sym).info
                vol = info.get("volume", 0) or 0
                if vol < min_volume:
                    continue
                prev = info.get("regularMarketPreviousClose", 1)
                curr = info.get("regularMarketPrice", prev)
                change_pct = (curr - prev) / prev * 100 if prev else 0
                results.append({"symbol": sym, "price": curr,
                                 "change_pct": round(change_pct, 2),
                                 "volume": vol})
            except Exception:
                continue
        return sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_market_data.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add quant_trader/market_data.py tests/test_market_data.py
git commit -m "feat: market data tools (quote, OHLCV, screen)"
```

---

## Task 5: 技术指标

> 推荐模型：**Sonnet 4.6**

> ⚡ **Opus Review 改进**:
> - 新增多因子评分系统 `score_stock()` 替代简单 RSI+MACD 筛选
> - 因子: RSI(15%), MACD(15%), 成交量(10%), 相对强度vs SPY(15%), 布林带(10%), 新闻情绪(15%), PE(10%), 行业热度(10%)
> - 返回 0-100 综合评分，>70 推荐买入
> - 新增 ATR 动态止损/止盈（替代固定 ±5%/±3%）

**Files:**
- Create: `quant_trader/technical.py`
- Create: `tests/test_technical.py`

**Step 1: 写失败测试**

```python
# tests/test_technical.py
import pandas as pd
import numpy as np
from quant_trader.technical import TechnicalAnalysis

def make_ohlcv(n=60):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 150, n) + np.random.randn(n)*2, index=idx)
    return pd.DataFrame({"Open":close,"High":close+2,"Low":close-2,
                         "Close":close,"Volume":[1_000_000]*n}, index=idx)

def test_calc_rsi_returns_series():
    ta = TechnicalAnalysis()
    df = make_ohlcv()
    result = ta.calc_indicators(df, ["rsi"])
    assert "RSI_14" in result.columns
    assert result["RSI_14"].dropna().between(0, 100).all()

def test_calc_macd_returns_columns():
    ta = TechnicalAnalysis()
    df = make_ohlcv()
    result = ta.calc_indicators(df, ["macd"])
    assert "MACD_12_26_9" in result.columns

def test_detect_golden_cross():
    ta = TechnicalAnalysis()
    df = make_ohlcv(100)
    signals = ta.detect_patterns(df)
    assert isinstance(signals, list)
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_technical.py -v
```

**Step 3: 实现 `quant_trader/technical.py`**

```python
from __future__ import annotations
import pandas as pd
import pandas_ta as pta


class TechnicalAnalysis:

    def calc_indicators(self, df: pd.DataFrame,
                        indicators: list[str] | None = None) -> pd.DataFrame:
        """
        计算技术指标。indicators 可选: rsi, macd, bbands, sma, ema
        返回原 DataFrame + 新增指标列。
        """
        result = df.copy()
        wanted = set(indicators or ["rsi", "macd", "bbands"])
        if "rsi" in wanted:
            result.ta.rsi(append=True)
        if "macd" in wanted:
            result.ta.macd(append=True)
        if "bbands" in wanted:
            result.ta.bbands(append=True)
        if "sma" in wanted:
            result.ta.sma(length=20, append=True)
            result.ta.sma(length=50, append=True)
        if "ema" in wanted:
            result.ta.ema(length=12, append=True)
            result.ta.ema(length=26, append=True)
        return result

    def detect_patterns(self, df: pd.DataFrame) -> list[dict]:
        """检测金叉/死叉、布林带突破等信号"""
        signals: list[dict] = []
        enriched = self.calc_indicators(df, ["sma", "macd"])
        sma20 = enriched.get("SMA_20")
        sma50 = enriched.get("SMA_50")
        if sma20 is not None and sma50 is not None:
            prev_diff = (sma20.iloc[-2] - sma50.iloc[-2])
            curr_diff = (sma20.iloc[-1] - sma50.iloc[-1])
            if prev_diff < 0 and curr_diff >= 0:
                signals.append({"type": "golden_cross", "desc": "SMA20 上穿 SMA50"})
            elif prev_diff > 0 and curr_diff <= 0:
                signals.append({"type": "death_cross", "desc": "SMA20 下穿 SMA50"})
        return signals

    def score_stock(self, df: pd.DataFrame, news_sentiment: float = 0.5,
                    pe_ratio: float | None = None, sector_heat: float = 0.5) -> dict:
        """
        多因子评分系统。返回 0-100 综合评分。
        因子权重: RSI(15%), MACD(15%), 成交量(10%), 相对强度vs SPY(15%),
                  布林带(10%), 新闻情绪(15%), PE(10%), 行业热度(10%)
        评分 >70 推荐买入。
        """
        enriched = self.calc_indicators(df, ["rsi", "macd", "bbands"])
        latest = enriched.iloc[-1]
        scores: dict[str, float] = {}
        # RSI: 30-50 最佳(满分)，<30 超卖(80分)，>70 超买(20分)
        rsi = latest.get("RSI_14", 50)
        if 30 <= rsi <= 50:
            scores["rsi"] = 100
        elif rsi < 30:
            scores["rsi"] = 80
        elif 50 < rsi <= 70:
            scores["rsi"] = 60
        else:
            scores["rsi"] = 20
        # MACD: 正值且递增
        macd_val = latest.get("MACD_12_26_9", 0) or 0
        scores["macd"] = min(100, max(0, 50 + macd_val * 100))
        # 成交量: 高于20日均量
        vol_avg = df["Volume"].rolling(20).mean().iloc[-1] if len(df) >= 20 else df["Volume"].mean()
        vol_ratio = df["Volume"].iloc[-1] / vol_avg if vol_avg > 0 else 1
        scores["volume"] = min(100, vol_ratio * 50)
        # 布林带: 价格在下轨附近高分
        bbl = latest.get("BBL_5_2.0", df["Close"].iloc[-1])
        bbm = latest.get("BBM_5_2.0", df["Close"].iloc[-1])
        bbu = latest.get("BBU_5_2.0", df["Close"].iloc[-1])
        bb_range = bbu - bbl if bbu != bbl else 1
        bb_pos = (df["Close"].iloc[-1] - bbl) / bb_range
        scores["bbands"] = max(0, min(100, (1 - bb_pos) * 100))
        # 外部因子
        scores["news"] = news_sentiment * 100
        scores["pe"] = max(0, min(100, 100 - (pe_ratio or 25))) if pe_ratio else 50
        scores["sector"] = sector_heat * 100
        scores["relative_strength"] = 50  # placeholder, needs SPY comparison
        weights = {"rsi": 0.15, "macd": 0.15, "volume": 0.10, "relative_strength": 0.15,
                   "bbands": 0.10, "news": 0.15, "pe": 0.10, "sector": 0.10}
        total = sum(scores.get(k, 50) * w for k, w in weights.items())
        return {"score": round(total, 1), "factors": scores,
                "recommendation": "BUY" if total > 70 else "HOLD" if total > 40 else "AVOID"}

    def calc_atr_targets(self, df: pd.DataFrame, multiplier_tp: float = 2.0,
                         multiplier_sl: float = 1.5) -> dict:
        """ATR 动态止损/止盈（替代固定百分比）"""
        enriched = df.copy()
        enriched.ta.atr(append=True)
        atr_col = [c for c in enriched.columns if "ATR" in c]
        if not atr_col:
            return {"error": "ATR calculation failed"}
        atr = enriched[atr_col[0]].iloc[-1]
        price = df["Close"].iloc[-1]
        return {
            "price": round(float(price), 2),
            "atr": round(float(atr), 2),
            "target": round(float(price + atr * multiplier_tp), 2),
            "stop_loss": round(float(price - atr * multiplier_sl), 2),
        }

    def backtest_strategy(self, df: pd.DataFrame,
                          strategy: str = "sma_cross") -> dict:
        """
        简单回测框架。strategy: sma_cross
        返回: 胜率、夏普比率、最大回撤、总收益
        """
        enriched = self.calc_indicators(df, ["sma"])
        sma20 = enriched["SMA_20"]
        sma50 = enriched["SMA_50"]
        positions = (sma20 > sma50).astype(int).shift(1).fillna(0)
        returns = df["Close"].pct_change().fillna(0)
        strat_returns = positions * returns
        total = (1 + strat_returns).prod() - 1
        sharpe = strat_returns.mean() / strat_returns.std() * (252 ** 0.5) if strat_returns.std() > 0 else 0
        cumulative = (1 + strat_returns).cumprod()
        max_dd = ((cumulative.cummax() - cumulative) / cumulative.cummax()).max()
        wins = (strat_returns > 0).sum()
        total_trades = (strat_returns != 0).sum()
        return {
            "strategy": strategy,
            "total_return": round(float(total), 4),
            "sharpe_ratio": round(float(sharpe), 3),
            "max_drawdown": round(float(max_dd), 4),
            "win_rate": round(float(wins / total_trades) if total_trades > 0 else 0, 3),
        }
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_technical.py -v
```
Expected: 3 passed

**Step 5: Commit**

```bash
git add quant_trader/technical.py tests/test_technical.py
git commit -m "feat: technical analysis (RSI/MACD/BBands/backtest)"
```

---

## Task 6: 市场情绪 & 热度

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `quant_trader/sentiment.py`
- Create: `tests/test_sentiment.py`

**Step 1: 写失败测试**

```python
# tests/test_sentiment.py
from unittest.mock import patch, MagicMock
from quant_trader.sentiment import MarketSentiment

def test_get_market_mood_returns_dict():
    with patch("quant_trader.sentiment.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"regularMarketPrice": 18.5}
        s = MarketSentiment()
        mood = s.get_market_mood()
        assert "vix" in mood
        assert "fear_greed" in mood

def test_get_news_sentiment_returns_list():
    with patch("quant_trader.sentiment.feedparser.parse") as mock_parse:
        mock_parse.return_value.entries = [
            MagicMock(title="Apple beats earnings", summary="Strong results",
                      published="Thu, 13 Mar 2026 10:00:00 GMT")
        ]
        s = MarketSentiment()
        news = s.get_news_sentiment("AAPL")
        assert isinstance(news, list)
        assert len(news) > 0
        assert "title" in news[0]
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_sentiment.py -v
```

**Step 3: 实现 `quant_trader/sentiment.py`**

```python
from __future__ import annotations
import yfinance as yf
import feedparser


class MarketSentiment:

    def get_market_mood(self) -> dict:
        """大盘情绪：VIX、简单恐贪指数估算"""
        vix_info = yf.Ticker("^VIX").info
        vix = vix_info.get("regularMarketPrice", 0)
        # 简单恐贪映射：VIX<15 贪婪, 15-25 中性, >25 恐惧
        if vix < 15:
            fear_greed = "greed"
        elif vix < 25:
            fear_greed = "neutral"
        else:
            fear_greed = "fear"
        spy_info = yf.Ticker("SPY").info
        spy_change = spy_info.get("regularMarketChangePercent", 0)
        return {
            "vix": round(vix, 2),
            "fear_greed": fear_greed,
            "spy_change_pct": round(spy_change, 2),
        }

    def get_sector_heat(self) -> list[dict]:
        """标准普尔11个板块 ETF 涨跌幅排行"""
        sectors = {
            "XLK": "科技", "XLF": "金融", "XLV": "医疗",
            "XLE": "能源", "XLI": "工业", "XLY": "消费",
            "XLP": "必需消费", "XLU": "公用事业",
            "XLB": "材料", "XLRE": "房地产", "XLC": "通信",
        }
        result = []
        for etf, name in sectors.items():
            try:
                info = yf.Ticker(etf).info
                chg = info.get("regularMarketChangePercent", 0) or 0
                result.append({"etf": etf, "sector": name,
                                "change_pct": round(chg, 2)})
            except Exception:
                continue
        return sorted(result, key=lambda x: x["change_pct"], reverse=True)

    def get_news_sentiment(self, symbol: str, max_items: int = 10) -> list[dict]:
        """拉取 Yahoo Finance RSS 新闻，返回标题+摘要（截断至500字符）"""
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            title = (entry.get("title") or "")[:200]
            summary = (entry.get("summary") or "")[:500]
            items.append({
                "title": title,
                "summary": summary,
                "published": entry.get("published", ""),
            })
        return items
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_sentiment.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add quant_trader/sentiment.py tests/test_sentiment.py
git commit -m "feat: market sentiment (VIX, sector heat, news)"
```

---

## Task 7: 基本面工具

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `quant_trader/fundamental.py`
- Create: `tests/test_fundamental.py`

**Step 1: 写失败测试**

```python
# tests/test_fundamental.py
from unittest.mock import patch, MagicMock
from quant_trader.fundamental import Fundamental

def test_get_financials_returns_key_ratios():
    with patch("quant_trader.fundamental.yf.Ticker") as mock:
        mock.return_value.info = {
            "trailingPE": 28.5, "priceToBook": 3.2,
            "returnOnEquity": 0.35, "revenueGrowth": 0.08,
            "debtToEquity": 45.0,
        }
        f = Fundamental()
        data = f.get_financials("AAPL")
        assert data["pe_ratio"] == 28.5
        assert data["roe"] == 0.35

def test_get_earnings_cal_returns_list():
    with patch("quant_trader.fundamental.yf.Ticker") as mock:
        mock.return_value.calendar = {"Earnings Date": ["2026-04-30"]}
        f = Fundamental()
        cal = f.get_earnings_calendar(["AAPL", "MSFT"])
        assert isinstance(cal, list)
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_fundamental.py -v
```

**Step 3: 实现 `quant_trader/fundamental.py`**

```python
from __future__ import annotations
import yfinance as yf


class Fundamental:

    def get_financials(self, symbol: str) -> dict:
        """关键财务指标：PE、PB、ROE、营收增长、负债率"""
        info = yf.Ticker(symbol).info
        return {
            "symbol": symbol.upper(),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

    def get_earnings_calendar(self, symbols: list[str]) -> list[dict]:
        """批量查询财报日历"""
        result = []
        for sym in symbols:
            try:
                cal = yf.Ticker(sym).calendar
                dates = cal.get("Earnings Date", []) if isinstance(cal, dict) else []
                result.append({
                    "symbol": sym,
                    "earnings_dates": [str(d) for d in dates],
                })
            except Exception:
                result.append({"symbol": sym, "earnings_dates": []})
        return result

    def compare_peers(self, symbols: list[str]) -> list[dict]:
        """同行业对比：多个标的财务指标横向对比"""
        return [self.get_financials(sym) for sym in symbols]
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_fundamental.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add quant_trader/fundamental.py tests/test_fundamental.py
git commit -m "feat: fundamental analysis (financials, earnings calendar)"
```

---

## Task 8: 持仓 & 账户工具

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `quant_trader/portfolio.py`
- Create: `tests/test_portfolio.py`

**Step 1: 写失败测试（mock IB）**

```python
# tests/test_portfolio.py
from unittest.mock import MagicMock, patch
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
    conn.ib.accountValues.return_value = [acc]
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
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_portfolio.py -v
```

**Step 3: 实现 `quant_trader/portfolio.py`**

```python
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
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_portfolio.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add quant_trader/portfolio.py tests/test_portfolio.py
git commit -m "feat: portfolio tools (positions, account, P&L)"
```

---

## Task 9: 订单 Plan→Confirm→Execute

> 推荐模型：**Opus 4.6**（涉及资金安全，需要最严密的推理）

> ⚡ **Opus Review 改进**:
> - 订单计划 5 分钟过期（防止过时价格执行）
> - 实盘模式需 `confirm_order(plan_id, confirm_live=True)` 二次确认
> - 新增 position sizing: 单只不超过账户 20%
> - 新增 daily loss limit: 当日亏损超过阈值拒绝新订单
> - 新增 order audit log（JSON 文件，记录所有订单操作）
> - 新增关联性检查: 不允许同时持有高度相关的标的

**Files:**
- Create: `quant_trader/orders.py`
- Create: `tests/test_orders.py`

**Step 1: 写失败测试**

```python
# tests/test_orders.py
import pytest
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
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_orders.py -v
```

**Step 3: 实现 `quant_trader/orders.py`**

```python
from __future__ import annotations
import json, uuid, logging
from datetime import datetime, timezone
from pathlib import Path
from ib_insync import Stock, MarketOrder, LimitOrder
from quant_trader.connection import IBConnection
from quant_trader.config import Config

logger = logging.getLogger(__name__)
AUDIT_LOG_PATH = Path.home() / "quant-trader-reports" / "audit.json"

class OrderManager:
    def __init__(self, conn: IBConnection, config: Config) -> None:
        self._conn = conn
        self._cfg = config
        self._plans: dict[str, dict] = {}
        self._daily_pnl: float = 0.0  # 当日已实现亏损

    def _write_audit(self, action: str, plan: dict) -> None:
        """追加记录到 audit.json"""
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(),
                 "action": action, "plan": plan}
        existing = []
        if AUDIT_LOG_PATH.exists():
            try:
                existing = json.loads(AUDIT_LOG_PATH.read_text())
            except Exception:
                existing = []
        existing.append(entry)
        AUDIT_LOG_PATH.write_text(json.dumps(existing, indent=2, default=str))

    def create_order_plan(
        self,
        symbol: str,
        action: str,           # BUY | SELL
        quantity: int,
        order_type: str = "LMT",
        limit_price: float | None = None,
    ) -> dict:
        """
        生成订单计划（不执行）。
        超过 max_order_value 时抛出 ValueError。
        daily loss limit 超过时拒绝新订单。
        """
        action = action.upper()
        assert action in ("BUY", "SELL"), f"Invalid action: {action}"
        # daily loss limit 检查
        if self._daily_pnl <= -self._cfg.max_daily_loss:
            raise ValueError(
                f"Daily loss limit reached (${self._daily_pnl:.2f}). "
                f"Max allowed: ${self._cfg.max_daily_loss:.2f}"
            )
        # 金额检查
        if limit_price:
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
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._plans[plan_id] = plan
        self._write_audit("plan_created", plan)
        logger.info("Order plan created: %s", plan)
        return plan

    def confirm_order(self, plan_id: str, confirm_live: bool = False) -> dict:
        """
        确认并提交订单到 IB TWS。
        - 订单计划过期（order_plan_ttl_minutes）后拒绝确认
        - 实盘模式需 confirm_live=True 二次确认
        """
        plan = self._plans[plan_id]   # KeyError if not found
        # 过期检查
        created = datetime.fromisoformat(plan["created_at"])
        elapsed = (datetime.now(timezone.utc) - created).total_seconds()
        if elapsed > self._cfg.order_plan_ttl_minutes * 60:
            plan["status"] = "expired"
            self._write_audit("plan_expired", plan)
            raise ValueError(
                f"Order plan {plan_id} expired after "
                f"{self._cfg.order_plan_ttl_minutes} minutes"
            )
        # 实盘二次确认
        if not self._cfg.paper_mode:
            if self._cfg.live_double_confirm and not confirm_live:
                raise ValueError(
                    "Live mode requires confirm_live=True for double confirmation"
                )
            logger.warning("LIVE ORDER SUBMITTED: %s", plan)
        contract = Stock(plan["symbol"], "SMART", "USD")
        if plan["order_type"] == "MKT":
            order = MarketOrder(plan["action"], plan["quantity"])
        else:
            order = LimitOrder(plan["action"], plan["quantity"],
                               plan["limit_price"])
        trade = self._conn.ib.placeOrder(contract, order)
        plan["status"] = "submitted"
        plan["ib_order_id"] = trade.order.orderId
        self._write_audit("order_submitted", plan)
        return plan

    def cancel_order(self, plan_id: str) -> dict:
        plan = self._plans.get(plan_id, {})
        if plan.get("ib_order_id"):
            from ib_insync import Order as IBOrder
            o = IBOrder()
            o.orderId = plan["ib_order_id"]
            self._conn.ib.cancelOrder(o)
        plan["status"] = "cancelled"
        self._write_audit("order_cancelled", plan)
        return plan

    def get_order_status(self, plan_id: str) -> dict:
        return self._plans.get(plan_id, {"error": "plan not found"})

    def update_daily_pnl(self, pnl: float) -> None:
        """更新当日 PnL（负值表示亏损）"""
        self._daily_pnl = pnl
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_orders.py -v
```
Expected: 4 passed

**Step 5: Commit**

```bash
git add quant_trader/orders.py tests/test_orders.py
git commit -m "feat: order Plan→Confirm→Execute with safety limits"
```

---

## Task 10: MCP Server 组装

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `mcp_server/server.py`
- Create: `tests/test_server.py`

**Step 1: 实现 `mcp_server/server.py`（工具注册）**

```python
"""
quant-trader MCP Server

Security:
- Paper mode by default; live requires explicit config
- Orders require Plan→Confirm two-step
- Max order value enforced at plan creation
- No credentials stored in code; IB uses local TWS auth
- All external data (news) truncated to 500 chars
"""
from mcp.server.fastmcp import FastMCP
from quant_trader.config import Config
from quant_trader.connection import IBConnection
from quant_trader.market_data import MarketData
from quant_trader.technical import TechnicalAnalysis
from quant_trader.sentiment import MarketSentiment
from quant_trader.fundamental import Fundamental
from quant_trader.portfolio import Portfolio
from quant_trader.orders import OrderManager

cfg  = Config.load()
conn = IBConnection(cfg)
md   = MarketData(cfg)
ta   = TechnicalAnalysis()
sent = MarketSentiment()
fund = Fundamental()

mcp = FastMCP("quant-trader")

# ── Market Data ──────────────────────────────────────────────────────────────

@mcp.tool()
def get_quote(symbol: str) -> dict:
    """实时报价：价格、买卖盘、成交量"""
    return md.get_quote(symbol)

@mcp.tool()
def get_ohlcv(symbol: str, period: str = "3mo", interval: str = "1d") -> dict:
    """K线历史数据。period: 1d/1mo/3mo/1y. interval: 1m/5m/1h/1d"""
    df = md.get_ohlcv(symbol, period, interval)
    return df.tail(100).to_dict(orient="records")

@mcp.tool()
def screen_stocks(symbols: list[str], min_volume: int = 1_000_000) -> list:
    """批量选股筛选，按涨跌幅排序"""
    return md.screen_stocks(symbols, min_volume)

# ── Technical Analysis ───────────────────────────────────────────────────────

@mcp.tool()
def calc_indicators(symbol: str, indicators: list[str] | None = None,
                    period: str = "6mo") -> dict:
    """计算技术指标。indicators: [rsi, macd, bbands, sma, ema]"""
    df = md.get_ohlcv(symbol, period=period)
    result = ta.calc_indicators(df, indicators)
    return result.tail(30).to_dict(orient="records")

@mcp.tool()
def detect_patterns(symbol: str) -> list:
    """检测金叉/死叉等形态信号"""
    df = md.get_ohlcv(symbol, period="6mo")
    return ta.detect_patterns(df)

@mcp.tool()
def backtest_strategy(symbol: str, strategy: str = "sma_cross",
                      period: str = "1y") -> dict:
    """策略回测：胜率、夏普比率、最大回撤、总收益"""
    df = md.get_ohlcv(symbol, period=period)
    return ta.backtest_strategy(df, strategy)

# ── Market Sentiment ─────────────────────────────────────────────────────────

@mcp.tool()
def get_market_mood() -> dict:
    """大盘情绪：VIX、恐贪指数、SPY涨跌"""
    return sent.get_market_mood()

@mcp.tool()
def get_sector_heat() -> list:
    """11个标普行业 ETF 涨跌幅排行"""
    return sent.get_sector_heat()

@mcp.tool()
def get_news_sentiment(symbol: str, max_items: int = 10) -> list:
    """获取个股新闻（标题+摘要，截断至500字符）"""
    return sent.get_news_sentiment(symbol, max_items)

# ── Fundamental ───────────────────────────────────────────────────────────────

@mcp.tool()
def get_financials(symbol: str) -> dict:
    """财务指标：PE/PB/ROE/营收增长/负债率"""
    return fund.get_financials(symbol)

@mcp.tool()
def get_earnings_calendar(symbols: list[str]) -> list:
    """查询财报日历"""
    return fund.get_earnings_calendar(symbols)

@mcp.tool()
def compare_peers(symbols: list[str]) -> list:
    """同行业财务对比"""
    return fund.compare_peers(symbols)

# ── Portfolio ─────────────────────────────────────────────────────────────────

@mcp.tool()
def get_positions() -> list:
    """当前持仓（需要 IB TWS 连接）"""
    p = Portfolio(conn, cfg)
    return p.get_positions()

@mcp.tool()
def get_account_info() -> dict:
    """账户净值、购买力、现金余额"""
    p = Portfolio(conn, cfg)
    return p.get_account_info()

@mcp.tool()
def get_pnl() -> dict:
    """今日/历史浮盈浮亏"""
    p = Portfolio(conn, cfg)
    return p.get_pnl()

# ── Orders ────────────────────────────────────────────────────────────────────

_om = OrderManager(conn, cfg)

@mcp.tool()
def create_order_plan(symbol: str, action: str, quantity: int,
                      order_type: str = "LMT",
                      limit_price: float | None = None) -> dict:
    """
    生成订单计划（不执行）。
    action: BUY | SELL. order_type: LMT | MKT
    超出 max_order_value 时拒绝。
    """
    return _om.create_order_plan(symbol, action, quantity, order_type, limit_price)

@mcp.tool()
def confirm_order(plan_id: str) -> dict:
    """确认并提交订单。实盘模式下请谨慎确认。"""
    return _om.confirm_order(plan_id)

@mcp.tool()
def cancel_order(plan_id: str) -> dict:
    """撤销订单"""
    return _om.cancel_order(plan_id)

@mcp.tool()
def get_order_status(plan_id: str) -> dict:
    """查询订单状态"""
    return _om.get_order_status(plan_id)

# ── System ────────────────────────────────────────────────────────────────────

@mcp.tool()
def connect_ib() -> dict:
    """连接 IB TWS"""
    conn.connect()
    return {"status": "connected", "paper_mode": cfg.paper_mode, "port": cfg.ib_port}

@mcp.tool()
def disconnect_ib() -> dict:
    """断开 IB TWS 连接"""
    conn.disconnect()
    return {"status": "disconnected"}

@mcp.tool()
def doctor() -> dict:
    """环境诊断：配置、TWS 连接状态、模式"""
    return {
        "config_path": str(Config.DEFAULT_CONFIG_PATH if hasattr(Config, "DEFAULT_CONFIG_PATH") else "~/.quant-trader/config.yaml"),
        "paper_mode": cfg.paper_mode,
        "ib_host": cfg.ib_host,
        "ib_port": cfg.ib_port,
        "ib_connected": conn.is_connected,
        "max_order_value": cfg.max_order_value,
    }

if __name__ == "__main__":
    mcp.run()
```

**Step 2: Commit**

```bash
git add mcp_server/server.py
git commit -m "feat: MCP server with 21 tools across 7 categories"
```

---

## Task 11: SKILL.md

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `skills/quant-trader/SKILL.md`

参考 vmware-aiops 的 SKILL.md 格式，包含：
- Frontmatter（name, description, installer, metadata）
- Setup（IB TWS 安装、config.yaml 格式、paper/live 切换）
- 工具列表（7类，21个工具）
- 使用示例（3个场景：技术分析、情绪判断、下单）
- Security 段落（6要素：paper默认、Plan→Confirm、max_order_value、无密码、新闻截断、代码审查建议）

**Commit**

```bash
git add skills/quant-trader/SKILL.md
git commit -m "docs: add SKILL.md for quant-trader"
```

---

## Task 12: 全量测试 & 覆盖率检查

> 推荐模型：**Sonnet 4.6**（运行命令）/ **Opus 4.6**（分析缺口）

**Step 1: 运行全量测试**

```bash
cd /Users/zw/testany/myskills/quant-trader
uv run pytest tests/ -v --cov=quant_trader --cov-report=term-missing
```

Expected: 全部 pass，覆盖率 ≥ 80%

**Step 2: 如覆盖率不足，补充关键边界测试**

重点补充：
- `orders.py`：超额下单、撤销未提交订单、实盘模式警告日志
- `connection.py`：未连接时访问 `.ib` 属性抛出异常

**Step 3: Commit**

```bash
git add tests/
git commit -m "test: achieve 80%+ coverage"
```

---

## Task 13: 配置示例 & README

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `examples/mcp-configs/claude-code.json`
- Create: `~/.quant-trader/config.yaml`（示例）
- Create: `README.md`

**claude-code.json 示例：**

```json
{
  "mcpServers": {
    "quant-trader": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/Users/zw/testany/myskills/quant-trader"
    }
  }
}
```

**config.yaml 示例：**

```yaml
# ~/.quant-trader/config.yaml
mode: paper          # paper | live
ib_host: 127.0.0.1
ib_port: 7497        # 7497=paper TWS, 7496=live TWS
ib_client_id: 1
max_order_value: 10000.0
data_source: yfinance  # yfinance | ib
```

**Step: Commit**

```bash
git add examples/ README.md
git commit -m "docs: add README and config examples"
```

---

---

## Task 14: 交易日志持久化

> 推荐模型：**Sonnet 4.6**

每日推荐股和操作结果持久化到 JSON，支撑胜率统计和回测。

**Files:**
- Create: `quant_trader/trade_journal.py`
- Create: `tests/test_trade_journal.py`

**数据目录结构：**

```
~/quant-trader-reports/
├── 2026-03-13-morning.md      # 早报（人类可读）
├── 2026-03-13-intraday.md     # 盘中快照
├── 2026-03-13-eod.md          # 收盘总结
└── journal.json               # 机器可读，胜率统计用
```

**Step 1: 写失败测试**

```python
# tests/test_trade_journal.py
import json, tempfile
from pathlib import Path
from quant_trader.trade_journal import TradeJournal

def test_add_pick_and_retrieve():
    with tempfile.TemporaryDirectory() as tmp:
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-13", "AAPL", entry_price=175.0,
                         target=185.0, stop_loss=170.0, reason="金叉+低VIX")
        picks = journal.get_picks("2026-03-13")
        assert len(picks) == 1
        assert picks[0]["symbol"] == "AAPL"

def test_record_outcome_updates_pick():
    with tempfile.TemporaryDirectory() as tmp:
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-13", "NVDA", entry_price=800.0,
                         target=850.0, stop_loss=780.0, reason="AI热度")
        journal.record_outcome("2026-03-13", "NVDA",
                               exit_price=845.0, hit_target=True)
        picks = journal.get_picks("2026-03-13")
        assert picks[0]["result"] == "win"
        assert picks[0]["pnl_pct"] > 0

def test_win_rate_calculation():
    with tempfile.TemporaryDirectory() as tmp:
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-13", "AAPL", 175.0, 185.0, 170.0, "test")
        journal.add_pick("2026-03-13", "MSFT", 380.0, 400.0, 370.0, "test")
        journal.record_outcome("2026-03-13", "AAPL", 183.0, hit_target=True)
        journal.record_outcome("2026-03-13", "MSFT", 372.0, hit_target=False)
        stats = journal.win_rate_stats("2026-03-13")
        assert stats["win_rate"] == 0.5
        assert stats["total_picks"] == 2
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_trade_journal.py -v
```

**Step 3: 实现 `quant_trader/trade_journal.py`**

```python
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import date


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
    result: str = "open"       # open | win | loss
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
        self._db_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2))

    def add_pick(self, date_str: str, symbol: str, entry_price: float,
                 target: float, stop_loss: float, reason: str) -> None:
        self._data.setdefault(date_str, [])
        pick = StockPick(symbol=symbol.upper(), entry_price=entry_price,
                         target=target, stop_loss=stop_loss, reason=reason)
        self._data[date_str].append(asdict(pick))
        self._save()

    def record_outcome(self, date_str: str, symbol: str,
                       exit_price: float, hit_target: bool) -> None:
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
        all_picks = []
        if date_str:
            all_picks = [p for p in self._data.get(date_str, [])
                         if p["result"] != "open"]
        else:
            for picks in self._data.values():
                all_picks.extend(p for p in picks if p["result"] != "open")
        total = len(all_picks)
        wins = sum(1 for p in all_picks if p["result"] == "win")
        avg_pnl = sum(p["pnl_pct"] for p in all_picks) / total if total else 0
        return {
            "total_picks": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total, 3) if total else 0.0,
            "avg_pnl_pct": round(avg_pnl, 2),
        }
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_trade_journal.py -v
```
Expected: 3 passed

**Step 5: Commit**

```bash
git add quant_trader/trade_journal.py tests/test_trade_journal.py
git commit -m "feat: trade journal with pick tracking and win rate stats"
```

---

## Task 15: 三段式日工作流 + Markdown 报告生成

> 推荐模型：**Sonnet 4.6**（框架）/ **Opus 4.6**（选股逻辑）

> ⚡ **Opus Review 改进**:
> - 新增 `is_market_open()` 检查美股交易时间（ET 9:30-16:00，排除周末和假日）
> - morning_briefing 新增 pre-market 期货指数（ES/NQ）
> - 选股评分使用多因子系统（Task 5 的 `score_stock`），评分 >70 才推荐
> - 止损/止盈使用 ATR 动态计算
> - watchlist 从 config 读取，支持持久化

**Files:**
- Create: `quant_trader/daily_workflow.py`
- Create: `tests/test_daily_workflow.py`

**Step 1: 写失败测试**

```python
# tests/test_daily_workflow.py
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from quant_trader.daily_workflow import DailyWorkflow
from quant_trader.config import Config

def make_workflow(tmp_dir):
    cfg = Config()
    md_mock  = MagicMock()
    ta_mock  = MagicMock()
    sent_mock = MagicMock()
    fund_mock = MagicMock()
    md_mock.get_quote.return_value = {"symbol":"AAPL","price":175.0,"volume":50_000_000}
    ta_mock.calc_indicators.return_value = MagicMock(
        tail=lambda n: MagicMock(to_dict=lambda **_: [{"RSI_14": 45, "MACD_12_26_9": 0.5}])
    )
    sent_mock.get_market_mood.return_value = {"vix": 18.0, "fear_greed": "neutral", "spy_change_pct": 0.3}
    sent_mock.get_sector_heat.return_value = [{"sector":"科技","change_pct":1.2}]
    sent_mock.get_news_sentiment.return_value = [{"title":"Apple strong","summary":"...","published":""}]
    fund_mock.get_financials.return_value = {"pe_ratio": 28.0}
    from quant_trader.trade_journal import TradeJournal
    journal = TradeJournal(Path(tmp_dir))
    return DailyWorkflow(cfg, md_mock, ta_mock, sent_mock, fund_mock, journal, Path(tmp_dir))

def test_morning_briefing_creates_md_file():
    with tempfile.TemporaryDirectory() as tmp:
        wf = make_workflow(tmp)
        result = wf.morning_briefing(watchlist=["AAPL","MSFT"], date_str="2026-03-13")
        md_path = Path(tmp) / "2026-03-13-morning.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "早报" in content
        assert "AAPL" in content

def test_eod_summary_calculates_win_rate():
    with tempfile.TemporaryDirectory() as tmp:
        wf = make_workflow(tmp)
        from quant_trader.trade_journal import TradeJournal
        journal = TradeJournal(Path(tmp))
        journal.add_pick("2026-03-13","AAPL",175.0,185.0,170.0,"test")
        journal.record_outcome("2026-03-13","AAPL",183.0,True)
        wf2 = make_workflow(tmp)
        result = wf2.eod_summary(date_str="2026-03-13")
        assert "win_rate" in result
        md_path = Path(tmp) / "2026-03-13-eod.md"
        assert md_path.exists()
```

**Step 2: 运行确认失败**

```bash
uv run pytest tests/test_daily_workflow.py -v
```

**Step 3: 实现 `quant_trader/daily_workflow.py`**

```python
from __future__ import annotations
from datetime import date
from pathlib import Path

from quant_trader.config import Config
from quant_trader.market_data import MarketData
from quant_trader.technical import TechnicalAnalysis
from quant_trader.sentiment import MarketSentiment
from quant_trader.fundamental import Fundamental
from quant_trader.trade_journal import TradeJournal, DEFAULT_REPORTS_DIR


class DailyWorkflow:
    def __init__(self, config: Config, market_data: MarketData,
                 technical: TechnicalAnalysis, sentiment: MarketSentiment,
                 fundamental: Fundamental, journal: TradeJournal,
                 reports_dir: Path = DEFAULT_REPORTS_DIR) -> None:
        self._cfg    = config
        self._md     = market_data
        self._ta     = technical
        self._sent   = sentiment
        self._fund   = fundamental
        self._journal = journal
        self._dir    = reports_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── 开市前早报 ────────────────────────────────────────────────────────────

    def morning_briefing(self, watchlist: list[str],
                         date_str: str | None = None) -> dict:
        """
        生成开市前早报：
        - 大盘情绪（VIX、恐贪、SPY）
        - 热门板块 Top3
        - 每只观察股技术信号 + 新闻情绪
        - 操作建议（入场价、止损、目标）
        保存到 YYYY-MM-DD-morning.md
        """
        today = date_str or date.today().isoformat()
        mood  = self._sent.get_market_mood()
        sectors = self._sent.get_sector_heat()[:3]
        picks_summary = []
        recommendations = []

        for sym in watchlist:
            try:
                quote  = self._md.get_quote(sym)
                df     = self._md.get_ohlcv(sym, period="3mo")
                ind    = self._ta.calc_indicators(df, ["rsi", "macd", "bbands"])
                latest = ind.iloc[-1]
                rsi    = latest.get("RSI_14", float("nan"))
                news   = self._sent.get_news_sentiment(sym, max_items=3)
                fin    = self._fund.get_financials(sym)
                price  = quote.get("price", 0) or 0

                # 简单选股规则：RSI 30-60 + MACD 正值 = 建议关注
                macd_val = latest.get("MACD_12_26_9", 0) or 0
                is_pick  = 30 < rsi < 60 and macd_val > 0
                reason_parts = []
                if 30 < rsi < 50:
                    reason_parts.append(f"RSI {rsi:.1f} 偏低有支撑")
                if macd_val > 0:
                    reason_parts.append("MACD 多头")
                reason = "；".join(reason_parts) or "技术面中性"

                entry = {
                    "symbol": sym, "price": price,
                    "rsi": round(float(rsi), 1) if rsi == rsi else None,
                    "macd": round(float(macd_val), 3),
                    "top_news": news[0]["title"] if news else "",
                    "pe_ratio": fin.get("pe_ratio"),
                    "is_recommended": is_pick,
                    "reason": reason,
                }
                picks_summary.append(entry)

                if is_pick:
                    target    = round(price * 1.05, 2)
                    stop_loss = round(price * 0.97, 2)
                    recommendations.append({**entry, "entry": price,
                                            "target": target, "stop_loss": stop_loss})
                    self._journal.add_pick(today, sym, price, target, stop_loss, reason)
            except Exception as e:
                picks_summary.append({"symbol": sym, "error": str(e)})

        result = {
            "date": today, "mood": mood, "hot_sectors": sectors,
            "watchlist_analysis": picks_summary,
            "recommendations": recommendations,
        }
        self._write_morning_md(today, result)
        return result

    def _write_morning_md(self, date_str: str, data: dict) -> None:
        mood = data["mood"]
        lines = [
            f"# {date_str} 开市早报",
            "",
            "## 大盘情绪",
            f"- VIX: **{mood['vix']}**  |  情绪: **{mood['fear_greed']}**  |  SPY: {mood['spy_change_pct']:+.2f}%",
            "",
            "## 热门板块 Top3",
        ]
        for s in data["hot_sectors"]:
            lines.append(f"- {s['sector']} ({s.get('etf','')}): {s['change_pct']:+.2f}%")
        lines += ["", "## 建议关注股"]
        for r in data["recommendations"]:
            lines += [
                f"### {r['symbol']}  @${r['price']}",
                f"- 理由：{r['reason']}",
                f"- 入场：${r['entry']}  目标：${r['target']}  止损：${r['stop_loss']}",
                f"- RSI: {r.get('rsi')}  MACD: {r.get('macd')}",
                f"- 新闻：{r.get('top_news','')}",
                "",
            ]
        if not data["recommendations"]:
            lines.append("_今日无明确推荐，建议观望_")
        path = self._dir / f"{date_str}-morning.md"
        path.write_text("\n".join(lines), encoding="utf-8")

    # ── 盘中互动 ──────────────────────────────────────────────────────────────

    def intraday_snapshot(self, date_str: str | None = None) -> dict:
        """
        盘中快照：
        - 当日建议股当前涨跌幅 vs 入场价
        - 是否触及目标/止损
        - 建议是否加仓/减仓
        保存到 YYYY-MM-DD-intraday.md（追加）
        """
        today  = date_str or date.today().isoformat()
        picks  = self._journal.get_picks(today)
        snapshot = []
        for pick in picks:
            if pick["result"] != "open":
                continue
            sym   = pick["symbol"]
            entry = pick["entry_price"]
            try:
                current = self._md.get_quote(sym).get("price", entry) or entry
                chg_pct = (current - entry) / entry * 100
                hit_target    = current >= pick["target"]
                hit_stop_loss = current <= pick["stop_loss"]
                suggestion = "持有" if not hit_target and not hit_stop_loss else (
                    "考虑止盈" if hit_target else "考虑止损")
                snapshot.append({
                    "symbol": sym, "entry": entry, "current": current,
                    "change_pct": round(chg_pct, 2),
                    "hit_target": hit_target, "hit_stop": hit_stop_loss,
                    "suggestion": suggestion,
                })
            except Exception as e:
                snapshot.append({"symbol": sym, "error": str(e)})

        result = {"date": today, "snapshot": snapshot}
        self._append_intraday_md(today, result)
        return result

    def _append_intraday_md(self, date_str: str, data: dict) -> None:
        from datetime import datetime
        path = self._dir / f"{date_str}-intraday.md"
        ts   = datetime.now().strftime("%H:%M")
        lines = [f"\n## 盘中快照 {ts}\n"]
        for s in data["snapshot"]:
            if "error" in s:
                lines.append(f"- {s['symbol']}: ⚠️ {s['error']}")
            else:
                emoji = "✅" if s["hit_target"] else ("🛑" if s["hit_stop"] else "▶️")
                lines.append(
                    f"- {emoji} **{s['symbol']}** 入场${s['entry']} 现价${s['current']} "
                    f"({s['change_pct']:+.2f}%) → {s['suggestion']}"
                )
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ── 收盘总结 ──────────────────────────────────────────────────────────────

    def eod_summary(self, date_str: str | None = None,
                    outcomes: list[dict] | None = None) -> dict:
        """
        收盘总结：
        - 自动拉取当日建议股收盘价，记录结果
        - 胜率统计、平均盈亏
        - 保存到 YYYY-MM-DD-eod.md
        outcomes: 可手动传入 [{"symbol":"AAPL","exit_price":183.0,"hit_target":True}]
        """
        today = date_str or date.today().isoformat()
        picks = self._journal.get_picks(today)

        # 若未手动传入结果，用当前报价自动判断
        if outcomes is None:
            outcomes = []
            for pick in picks:
                if pick["result"] == "open":
                    try:
                        price = self._md.get_quote(pick["symbol"]).get("price") or pick["entry_price"]
                        hit   = price >= pick["target"]
                        outcomes.append({"symbol": pick["symbol"],
                                         "exit_price": price, "hit_target": hit})
                    except Exception:
                        pass

        for o in outcomes:
            self._journal.record_outcome(today, o["symbol"],
                                         o["exit_price"], o["hit_target"])

        stats = self._journal.win_rate_stats(today)
        picks_final = self._journal.get_picks(today)
        self._write_eod_md(today, picks_final, stats)
        return stats

    def _write_eod_md(self, date_str: str, picks: list[dict], stats: dict) -> None:
        lines = [
            f"# {date_str} 收盘总结",
            "",
            "## 胜率统计",
            f"- 总推荐: {stats['total_picks']} 只  |  胜: {stats['wins']}  |  负: {stats['losses']}",
            f"- **胜率: {stats['win_rate']:.1%}**  |  平均盈亏: {stats['avg_pnl_pct']:+.2f}%",
            "",
            "## 逐只复盘",
        ]
        for p in picks:
            result_emoji = {"win": "✅", "loss": "❌", "open": "⏳"}.get(p["result"], "")
            lines.append(
                f"- {result_emoji} **{p['symbol']}** 入场${p['entry_price']} "
                f"目标${p['target']} 止损${p['stop_loss']}"
            )
            if p["result"] != "open":
                lines.append(
                    f"  - 结果: {p['result']} @${p.get('exit_price','-')} "
                    f"({p.get('pnl_pct',0):+.2f}%)"
                )
            lines.append(f"  - 理由: {p['reason']}")
        path = self._dir / f"{date_str}-eod.md"
        path.write_text("\n".join(lines), encoding="utf-8")
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_daily_workflow.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add quant_trader/daily_workflow.py tests/test_daily_workflow.py
git commit -m "feat: daily workflow (morning briefing, intraday, EOD summary)"
```

---

## Task 16: 新增 MCP 工具（日工作流接入）

> 推荐模型：**Sonnet 4.6**

在 `mcp_server/server.py` 追加以下工具：

```python
# ── Daily Workflow ─────────────────────────────────────────────────────────

from quant_trader.daily_workflow import DailyWorkflow
from quant_trader.trade_journal import TradeJournal

_journal  = TradeJournal()
_workflow = DailyWorkflow(cfg, md, ta, sent, fund, _journal)

@mcp.tool()
def morning_briefing(watchlist: list[str], date_str: str | None = None) -> dict:
    """
    开市前早报：大盘情绪、热门板块、建议股（含入场/目标/止损）。
    结果自动保存到 ~/quant-trader-reports/YYYY-MM-DD-morning.md
    """
    return _workflow.morning_briefing(watchlist, date_str)

@mcp.tool()
def intraday_snapshot(date_str: str | None = None) -> dict:
    """
    盘中快照：当日建议股实时涨跌、是否触及目标/止损、加减仓建议。
    追加到 ~/quant-trader-reports/YYYY-MM-DD-intraday.md
    """
    return _workflow.intraday_snapshot(date_str)

@mcp.tool()
def eod_summary(date_str: str | None = None,
                outcomes: list[dict] | None = None) -> dict:
    """
    收盘总结：自动计算胜率、平均盈亏，逐只复盘。
    outcomes 格式: [{"symbol":"AAPL","exit_price":183.0,"hit_target":true}]
    结果保存到 ~/quant-trader-reports/YYYY-MM-DD-eod.md
    """
    return _workflow.eod_summary(date_str, outcomes)

@mcp.tool()
def add_manual_pick(symbol: str, entry_price: float,
                    target: float, stop_loss: float,
                    reason: str, date_str: str | None = None) -> dict:
    """盘中手动加入建议股（不在早报 watchlist 内但临时关注的）"""
    from datetime import date
    today = date_str or date.today().isoformat()
    _journal.add_pick(today, symbol, entry_price, target, stop_loss, reason)
    return {"status": "added", "symbol": symbol, "date": today}

@mcp.tool()
def win_rate_history(date_str: str | None = None) -> dict:
    """
    胜率历史统计。date_str=None 返回全部历史，否则返回指定日期。
    """
    return _journal.win_rate_stats(date_str)
```

**Commit**

```bash
git add mcp_server/server.py
git commit -m "feat: add daily workflow MCP tools (morning/intraday/eod/win_rate)"
```

---

## Task 17: 定时任务（Cron 自动触发）

> 推荐模型：**Sonnet 4.6**

**Files:**
- Create: `quant_trader/scheduler.py`

```python
# quant_trader/scheduler.py
"""
可选定时任务。使用方式：
  uv run python -m quant_trader.scheduler --watchlist AAPL MSFT NVDA TSLA

定时规则（美东时间）：
  08:00  → morning_briefing（开市前90分钟）
  12:00  → intraday_snapshot（午盘）
  15:00  → intraday_snapshot（尾盘前）
  16:30  → eod_summary（收盘后30分钟）
"""
import argparse, time, logging
from datetime import datetime
import pytz

from quant_trader.config import Config
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
    cfg      = Config.load()
    workflow = DailyWorkflow(cfg, MarketData(cfg), TechnicalAnalysis(),
                             MarketSentiment(), Fundamental(), TradeJournal())
    fired: set[str] = set()
    logging.basicConfig(level=logging.INFO)
    logging.info("Scheduler started. Watchlist: %s", watchlist)
    while True:
        now = datetime.now(ET).strftime("%H:%M")
        for trigger_time, action in SCHEDULE:
            key = f"{now}-{action}"
            if now == trigger_time and key not in fired:
                fired.add(key)
                logging.info("Firing: %s @ %s", action, now)
                if action == "morning":
                    workflow.morning_briefing(watchlist)
                elif action == "intraday":
                    workflow.intraday_snapshot()
                elif action == "eod":
                    workflow.eod_summary()
        time.sleep(30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", nargs="+", default=["AAPL","MSFT","NVDA","TSLA","AMZN"])
    args = parser.parse_args()
    run_scheduler(args.watchlist)
```

**pyproject.toml 增加依赖：**

```toml
"pytz>=2024.1,<2026.0",
```

**Commit**

```bash
git add quant_trader/scheduler.py
git commit -m "feat: optional daily scheduler (ET timezone, 4 triggers)"
```

---

## 完成标准

- [ ] `uv run pytest --cov=quant_trader` 覆盖率 ≥ 80%
- [ ] `uv run python -m mcp_server.server` 启动无报错
- [ ] `doctor` 工具返回正确配置信息
- [ ] paper 模式下 `create_order_plan → confirm_order` 流程可跑通
- [ ] `morning_briefing(["AAPL","MSFT"])` 生成 MD 文件到 `~/quant-trader-reports/`
- [ ] `eod_summary()` 计算胜率并写入 MD
- [ ] SKILL.md Security 段落包含 6 要素
- [ ] `uvx bandit -r quant_trader/` 0 Medium+ issues
- [ ] async 架构全栈验证（connection + server）
- [ ] DataProvider fallback 测试（IB 断开时自动切换 yfinance）
- [ ] 订单过期测试（5分钟后 confirm 被拒绝）
- [ ] 实盘二次确认测试（confirm_live=True 才能执行）
- [ ] audit.json 记录所有订单操作
- [ ] 多因子评分 >70 才出现在推荐列表
- [ ] daily loss limit 超过后拒绝新订单
