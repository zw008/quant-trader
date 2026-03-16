---
name: quant-trader
description: 量化交易助手 — A股/H股/美股全市场分析。触发词：AH早报、AH收盘、美股早报、美股收盘、早盘分析、收盘分析、分析一下、今天怎么样。根据北京时间自动选择报告模式，或手动指定市场。MCP Server可用时优先调用工具，否则直接用 yfinance。
---

# 量化交易助手（quant-trader）

A股 / H股 / 美股全市场日报工作流 + IB TWS 下单工具。

---

## 一、触发方式

### 自动模式（按北京时间）

| 北京时间 | 自动触发 | 报告文件 |
|---------|---------|---------|
| 06:00–14:59 | **AH早报** | `YYYY-MM-DD-ah-morning.md` |
| 15:00–20:59 | **AH收盘** | `YYYY-MM-DD-ah-eod.md` |
| 21:00–00:29 | **美股早报** | `YYYY-MM-DD-us-morning.md` |
| 00:30–05:59 | **美股收盘** | `YYYY-MM-DD-us-eod.md` |

### 手动关键词

- "AH早报" / "早盘" / "A股早报" → AH早报
- "AH收盘" / "A股收盘" / "港股收盘" → AH收盘
- "美股早报" / "美股开盘" → 美股早报
- "美股收盘" / "美股怎样" → 美股收盘

---

## 二、持仓配置

读取工作目录下的 `reports/portfolio.md`。

**文件不存在时**，提示用户创建并按以下模板填写，然后再继续分析：

```markdown
# 当前持仓

## A股持仓
| 代码 | 名称 | 成本价 | 仓位 | 备注 |
|------|------|--------|------|------|
| 600519.SS | 贵州茅台 | 1800.00 | 10% | 示例，请替换 |

## 港股关注
| 代码 | 名称 | 备注 |
|------|------|------|
| 0700.HK | 腾讯 | 示例，请替换 |

## 美股持仓
| 代码 | 名称 | 成本价 | 仓位 | 备注 |
|------|------|--------|------|------|
| AAPL | 苹果 | 150.00 | 10% | 示例，请替换 |
```

**代码格式说明：**
- A股上交所：`600519.SS`，深交所：`000858.SZ`，科创板：`688xxx.SS`
- 港股：`0700.HK`（四位数字）
- 美股：直接代码 `AAPL`、`TSLA`
- 杠杆ETF请在备注注明 `⚠️ 衰减提醒`

---

## 三、数据获取

### 优先：MCP 工具（quant-trader server 已连接时）

```
行情：get_quote / get_ohlcv
技术：calc_indicators / score_stock
情绪：get_market_mood / get_sector_heat
宏观：get_macro_risk / get_risk_news
日报：morning_briefing / eod_summary / meme_daily_report
```

### 备用：直接 yfinance（MCP 不可用时）

在 `quant-trader/` 目录执行 `uv run python`：

```python
import yfinance as yf
import pandas as pd
import time

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs)).iloc[-1]

def calc_macd_signal(close):
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    diff  = (ema12 - ema26) - (ema12 - ema26).ewm(span=9).mean()
    if len(diff) >= 2:
        if diff.iloc[-2] < 0 and diff.iloc[-1] > 0: return "金叉📈"
        elif diff.iloc[-2] > 0 and diff.iloc[-1] < 0: return "死叉📉"
        elif diff.iloc[-1] > 0: return "多头区"
        else: return "空头区"
    return "—"

def full_analysis(symbol, name, cost=None):
    time.sleep(1)
    try:
        info = yf.Ticker(symbol).info
        curr = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        if not curr:
            return f"{name} ({symbol}) — 数据暂不可用"
        chg       = (curr - prev) / prev * 100 if prev else 0
        high52    = info.get("fiftyTwoWeekHigh")
        low52     = info.get("fiftyTwoWeekLow")
        vol       = info.get("volume")
        avg_vol   = info.get("averageVolume") or info.get("averageDailyVolume10Day")
        vol_ratio = vol / avg_vol if vol and avg_vol else None

        df = yf.download(symbol, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"].squeeze()
        rsi  = calc_rsi(close)
        macd = calc_macd_signal(close)
        ma5  = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(min(60, len(close))).mean().iloc[-1]
        ccy  = "¥" if symbol.endswith((".SS", ".SZ")) else ("HK$" if symbol.endswith(".HK") else "$")

        lines = [f"\n{'='*52}", f"  {name}  ({symbol})", f"{'='*52}"]
        lines.append(f"  现价: {ccy}{curr:.2f}  {'▲' if chg>0 else '▼'}{abs(chg):.2f}%")
        if cost:
            pnl = (curr/cost-1)*100
            lines.append(f"  成本: {ccy}{cost:.2f}  浮盈亏: {'+' if pnl>0 else ''}{pnl:.1f}%")
        if high52 and low52 and high52 != low52:
            pos52 = (curr - low52) / (high52 - low52) * 100
            lines.append(f"  52周: {low52:.2f} ←[{pos52:.0f}%]→ {high52:.2f}")
        if vol_ratio:
            tag = "⚡放量" if vol_ratio > 2 else "缩量" if vol_ratio < 0.7 else "正常"
            lines.append(f"  量比: {vol_ratio:.2f}x  {tag}")
        lines.append(f"  RSI:  {rsi:.1f}  {'⚠️超买' if rsi>70 else '💡超卖' if rsi<30 else '中性'}")
        lines.append(f"  MACD: {macd}")
        lines.append(f"  均线: MA5={ma5:.2f} | MA10={ma10:.2f} | MA20={ma20:.2f} | MA60={ma60:.2f}")
        if curr > ma5 > ma10 > ma20:    lines.append("  ✅ 多头排列")
        elif curr < ma5 < ma10 < ma20:  lines.append("  ❌ 空头排列")
        elif curr > ma20:               lines.append("  📊 站上MA20")
        else:                           lines.append("  📉 跌破MA20")

        advice = []
        if rsi < 30:            advice.append("RSI超卖，关注反弹")
        elif rsi > 75:          advice.append("RSI超买，注意回调")
        if macd == "金叉📈":    advice.append("MACD金叉，短线做多信号")
        elif macd == "死叉📉":  advice.append("MACD死叉，短线偏空")
        if vol_ratio and vol_ratio > 2: advice.append("今日放量异动")
        if not advice:          advice.append("无明显强信号，观望为主")
        lines.append("  💬 " + "；".join(advice))
        return "\n".join(lines)
    except Exception as e:
        time.sleep(3)
        return f"{name} ({symbol}) — 获取失败: {e}"
```

**限流处理：** 每次请求间隔 sleep 1s；失败后 sleep 3s 重试一次，仍失败则标注"数据暂不可用"后继续。

---

## 四、报告模式详情

### AH早报

1. **大盘指数**：上证综指 / 沪深300 / 创业板 / 恒生指数
2. **A股持仓**：每只 `full_analysis()`，输出技术信号 + 操作建议
3. **港股关注**：泡泡玛特完整分析；其余科技龙头简表
4. **AH溢价**：溢价 = `(A股价 / (H股价/1.08) - 1) × 100%`，标注 >40% 或负溢价
5. **操作清单**（🔴高/🟡中/🟢低）
6. **风险提示** 3-5 条

主要AH双上市对照：BYD、中国平安、招商银行、中国移动、中国石化、中国银行、中国人寿、中国神华、中国石油

---

### AH收盘

1. 全日指数涨跌复盘
2. 持仓收盘盘点 + 更新 portfolio.md
3. 今日主线总结（什么涨/跌，原因）
4. 明日关注事项 3 条

---

### 美股早报

1. **大盘**：SPY / QQQ / DIA / ^VIX
2. **美股持仓**：每只 `full_analysis()`，杠杆ETF必加衰减提醒
3. **宏观快览**：黄金(GC=F) / 原油(CL=F) / 美元(DX-Y.NYB) / 10年债(^TNX) / BTC
4. **操作清单 + 挂单提醒**

---

### 美股收盘

1. SPY/QQQ/DIA 全日复盘 + VIX 变化
2. 板块热力：XLK / XLE / XLF / XLV / XLY / XLI
3. 持仓收盘盘点 + 更新 portfolio.md
4. 明日预告：重要数据/财报/止盈止损触发条件

---

## 五、下单工具（MCP 模式）

**必须两步确认，绝不自动执行：**

```
Step 1: create_order_plan("AAPL", "BUY", 10, "MKT")
Step 2: 展示计划，等待用户确认
Step 3: confirm_order(plan_id)  ← 仅用户明确同意后执行
```

---

## 六、分析原则

- RSI < 30 超卖 / RSI > 70 超买
- MACD死叉 + 52周高位(>75%) = 🔴 重点预警
- 量比 > 2x = 异动，需说明原因
- 杠杆ETF（SHNY/NVTX/SPXU）每次必提衰减风险
- VIX > 25 = 高恐慌，建议高现金比例
- 地缘政治/宏观风险纳入每次分析
- 分析报告全程中文

---

## 七、首次使用 Setup

**Step 1：创建报告目录**
```bash
mkdir -p reports
```

**Step 2：创建持仓文件** `reports/portfolio.md`（参考第二节模板）

**Step 3：安装依赖（yfinance 模式，零配置）**
```bash
pip install yfinance pandas
# 或使用 uv：
uv add yfinance pandas
```

**Step 4（可选）：安装 MCP Server 获得39个增强工具**
```bash
uv tool install quant-trader
```
配置 `~/.quant-trader/config.yaml`，添加到 Claude Code MCP 设置即可。

---

之后直接说"AH早报"或"美股早报"即可开始分析。
