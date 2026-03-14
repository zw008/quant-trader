# Quant Trader — 项目规范

## 项目目录结构（所有内容必须在此目录下）

```
quant-trader/                          # 项目根目录
├── CLAUDE.md                          # 本文件：项目规范和标准流程
├── README.md                          # 项目说明
├── pyproject.toml                     # Python 依赖和构建配置
├── quant_trader/                      # 核心模块
│   ├── config.py                      #   配置管理
│   ├── connection.py                  #   IB TWS 连接
│   ├── data_provider.py               #   数据源（yfinance + 缓存）
│   ├── market_data.py                 #   行情/K线
│   ├── technical.py                   #   技术指标 + 多因子评分
│   ├── strategies.py                  #   7个量化策略
│   ├── sentiment.py                   #   市场情绪/新闻
│   ├── fundamental.py                 #   基本面分析
│   ├── macro_risk.py                  #   宏观风险/地缘政治
│   ├── insider.py                     #   内部人交易监控
│   ├── hot_stocks.py                  #   热门Meme股追踪
│   ├── portfolio.py                   #   持仓管理
│   ├── orders.py                      #   订单（Plan→Confirm）
│   ├── daily_workflow.py              #   三段式日报 + Meme日报
│   ├── trade_journal.py               #   交易日志/胜率
│   └── scheduler.py                   #   定时任务
├── mcp_server/
│   └── server.py                      # MCP Server（39个工具）
├── tests/                             # 测试（136 tests）
├── skills/quant-trader/SKILL.md       # Claude Code Skill 描述
├── docs/plans/                        # 实现计划
└── reports/                           # ★ 所有报告和数据输出（.gitignore）
    ├── portfolio.md                   #   当前持仓（持续更新）
    ├── journal.json                   #   交易记录
    ├── audit.json                     #   订单审计日志
    ├── YYYY-MM-DD-morning.md          #   开市早报
    ├── YYYY-MM-DD-intraday.md         #   盘中快照
    ├── YYYY-MM-DD-eod.md              #   收盘总结
    └── YYYY-MM-DD-meme.md             #   Meme股日报
```

**重要规则：** 所有与 quant-trader skill 相关的文件（代码、报告、计划、配置）必须放在 `quant-trader/` 目录下，不要散落到其他位置。

---

## 每日标准工作流

用户说"收盘分析"、"今天怎么样"、"分析一下"时，按以下 **完整流程** 执行，不要遗漏任何步骤。

### 第一步：持仓分析

1. 读取 `quant-trader/reports/portfolio.md` 获取当前持仓
2. 对每只持仓股查询：现价、涨跌、RSI、MACD（金叉/死叉）、形态信号
3. 标注止盈/止损触发情况
4. 给出每只股的 **持有/减仓/清仓/加仓** 建议
5. 更新 `portfolio.md` 中的现价和浮盈亏

### 第二步：大盘与宏观

1. `get_market_mood()` — VIX、恐贪指数、SPY涨跌
2. `get_sector_heat()` — 11个行业ETF涨跌排行
3. `get_macro_risk()` — 宏观风险评估（油价、黄金、VIX、利率、汇率、期货）
4. `get_risk_news()` — 地缘政治和宏观新闻
5. 总结当日市场主线（什么涨什么跌，为什么）

### 第三步：新机会扫描

1. `score_stock()` — 对 watchlist + 当日热门板块的代表性标的评分
2. 结合宏观环境筛选：
   - 受益于当前宏观趋势的标的（如油价涨→能源股）
   - 超跌反弹机会（RSI<30 + 基本面OK）
   - 趋势延续机会（均线多头 + 量价配合）
3. 对评分>70的标的给出完整建议：入场价、止损、目标、持仓周期、理由

### 第四步：Meme/热门小盘股

1. `meme_daily_report()` — 扫描热门小盘异动股
2. 重点关注：
   - 量比>2x 的异动股
   - 做空比>20% 的轧空候选
   - 连涨/连跌趋势形成的标的
3. 标注适合小仓位追踪的候选（仓位建议1-2%）

### 第五步：内部人交易

1. `screen_insider_activity()` — 对持仓 + 关注列表检查内部人买卖
2. 标注异常信号（bearish/bullish）
3. 大额CEO卖出 = 风险预警

### 第六步：明日关注

1. 汇总以上分析，给出明天的 **关注列表**（3-5只）
2. 包含：标的、方向（做多/做空/观望）、触发条件、建议仓位
3. 标注待执行的未完成操作（如挂单未成交的卖出）

### 第七步：保存报告

1. 将完整分析保存到 `quant-trader/reports/YYYY-MM-DD-eod.md`
2. 更新 `quant-trader/reports/portfolio.md` 持仓状态
3. 更新 `quant-trader/reports/journal.json` 交易记录

---

## 分析原则（每次分析必须遵守）

- **地缘政治和宏观风险必须纳入每次分析**，不能只看技术面
- 结合新闻和市场消息，不能脱离基本面
- 杠杆ETF（SHNY/NVTX/SPXU）注意衰减效应
- 小盘Meme股仓位严格控制在1-2%
- 高VIX环境下保持高现金比例
- 分析报告用中文

## MCP工具清单（39个）

| 类别 | 工具 |
|------|------|
| 行情 | `get_quote`, `get_ohlcv`, `screen_stocks` |
| 技术 | `calc_indicators`, `detect_patterns`, `score_stock`, `backtest_strategy` |
| 策略 | `list_strategies`, `run_strategy_signal`, `compare_strategies` |
| 情绪 | `get_market_mood`, `get_sector_heat`, `get_news_sentiment` |
| 基本面 | `get_financials`, `get_earnings_calendar`, `compare_peers` |
| 持仓 | `get_positions`, `get_account_info`, `get_pnl` |
| 订单 | `create_order_plan`, `confirm_order`, `cancel_order`, `get_order_status`, `list_order_plans` |
| 日报 | `morning_briefing`, `intraday_snapshot`, `eod_summary`, `add_manual_pick`, `win_rate_history`, `meme_daily_report` |
| 宏观 | `get_macro_risk`, `get_risk_news` |
| 内部人 | `get_insider_transactions`, `get_insider_summary`, `screen_insider_activity` |
| 热门股 | `scan_hot_movers`, `get_top_gainers_losers`, `track_meme_momentum` |
| 系统 | `connect_ib`, `disconnect_ib`, `doctor` |
