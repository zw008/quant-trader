# Quant Trader — Claude 使用指南

克隆仓库后，在此目录运行 `claude`，以下工作流自动生效。
如需全局使用（任意目录），运行 `bash install.sh`。

---

## 触发方式

根据北京时间自动判断，也可手动指定：

| 说法 | 触发 |
|------|------|
| AH早报 / 早盘 / A股早报 | AH早报（06:00–14:59） |
| AH收盘 / A股收盘 | AH收盘（15:00–20:59） |
| 美股早报 / 美股开盘 | 美股早报（21:00–00:29） |
| 美股收盘 / 美股怎样 | 美股收盘（00:30–05:59） |
| 扫描标的 / 找机会 | 进攻性标的扫描 |

---

## 持仓配置

读取 `reports/portfolio.md`。**文件不存在时**先创建：

```bash
mkdir -p reports
```

按以下模板填写 `reports/portfolio.md`：

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

代码格式：A股上交所 `600519.SS`，深交所 `000858.SZ`，港股 `0700.HK`，美股 `AAPL`

---

## 数据获取

MCP Server 已连接时优先调用工具；否则自动降级到 `uv run python` + yfinance。

**yfinance 核心函数（所有模式共用）：**

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

## AH早报（06:00–14:59）

报告保存：`reports/YYYY-MM-DD-ah-morning.md`

1. **大盘**：上证综指(000001.SS) / 沪深300(000300.SS) / 创业板(399006.SZ) / 恒生(^HSI)
2. **A股持仓**：逐只 `full_analysis()`，输出技术信号 + 操作建议
3. **港股关注**：重点标的完整分析；其余输出简表（现价/涨跌/RSI/MACD）
4. **AH溢价**：`(A股价 / (H股价 / 1.08) - 1) × 100%`，>40% 或负溢价标注 ⚠️
5. **操作清单**（🔴高/🟡中/🟢低）+ 风险提示

---

## AH收盘（15:00–20:59）

报告保存：`reports/YYYY-MM-DD-ah-eod.md`

1. 全日指数涨跌复盘
2. 持仓收盘盘点 + 更新 `reports/portfolio.md`
3. 今日主线总结（什么涨/跌，原因）
4. 明日关注事项 3 条

---

## 美股早报（21:00–00:29）

报告保存：`reports/YYYY-MM-DD-us-morning.md`

1. **大盘**：SPY / QQQ / DIA / ^VIX
2. **美股持仓**：逐只 `full_analysis()`，杠杆ETF必加衰减提醒
3. **宏观**：黄金(GC=F) / 原油(CL=F) / 美元(DX-Y.NYB) / 10年债(^TNX) / BTC-USD
4. **操作清单 + 挂单提醒**

---

## 美股收盘（00:30–05:59）

报告保存：`reports/YYYY-MM-DD-us-eod.md`

1. SPY/QQQ/DIA 全日复盘 + VIX 变化
2. 板块热力：XLK / XLE / XLF / XLV / XLY / XLI
3. 持仓收盘盘点 + 更新 `reports/portfolio.md`
4. 明日预告：重要数据/财报/止盈止损触发条件

---

## 进攻性标的扫描

说"扫描标的"、"找机会"、"有什么好的标的"时执行：

对目标标的池（A股+H股）计算进攻评分（满分100）：
- RSI 45–65：+25分；MACD金叉：+30分，强多头区：+20分
- 多头排列：+25分；52周分位40–70%：+15分；量比放量：+5分

输出评分榜，>60分给出入场建议（价位/止损/理由）。
H股标注 T+0 可当日来回。

---

## 下单工具（MCP 模式）

两步确认，绝不自动执行：

```
Step 1: create_order_plan("AAPL", "BUY", 10, "MKT")  → 生成计划
Step 2: 展示计划详情，等待用户确认
Step 3: confirm_order(plan_id)  ← 仅用户明确同意后执行
```

---

## 分析原则

- RSI < 30 超卖 / RSI > 70 超买
- MACD死叉 + 52周高位(>75%) = 🔴 重点预警
- 量比 > 2x = ⚡ 异动，需说明原因
- 杠杆ETF 每次必提衰减风险
- VIX > 25 建议保持高现金比例
- 地缘政治/宏观风险纳入每次分析
- 报告全程中文
