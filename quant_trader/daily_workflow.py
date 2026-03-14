from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from quant_trader.config import Config
from quant_trader.market_data import MarketData
from quant_trader.technical import TechnicalAnalysis
from quant_trader.sentiment import MarketSentiment
from quant_trader.fundamental import Fundamental
from quant_trader.trade_journal import TradeJournal, DEFAULT_REPORTS_DIR

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quant_trader.macro_risk import MacroRisk
    from quant_trader.hot_stocks import HotStocks
    from quant_trader.insider import InsiderTrading

SCORE_THRESHOLD = 70  # Multi-factor score >= 70 to recommend


class DailyWorkflow:
    def __init__(
        self,
        config: Config,
        market_data: MarketData,
        technical: TechnicalAnalysis,
        sentiment: MarketSentiment,
        fundamental: Fundamental,
        journal: TradeJournal,
        reports_dir: Path = DEFAULT_REPORTS_DIR,
        macro_risk: MacroRisk | None = None,
        hot_stocks: HotStocks | None = None,
        insider: InsiderTrading | None = None,
    ) -> None:
        self._cfg = config
        self._md = market_data
        self._ta = technical
        self._sent = sentiment
        self._fund = fundamental
        self._journal = journal
        self._dir = reports_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._macro = macro_risk
        self._hot = hot_stocks
        self._insider = insider

    # ── Morning Briefing ─────────────────────────────────────────────────────

    def morning_briefing(
        self,
        watchlist: list[str] | None = None,
        date_str: str | None = None,
    ) -> dict:
        """Pre-market briefing with mood, sectors, scores, recommendations."""
        today = date_str or date.today().isoformat()
        wl = watchlist or list(self._cfg.watchlist)
        mood = self._sent.get_market_mood()
        sectors = self._sent.get_sector_heat()[:3]
        picks_summary: list[dict] = []
        recommendations: list[dict] = []

        # Macro risk assessment (when available)
        macro_assessment: dict | None = None
        if self._macro is not None:
            try:
                macro_assessment = self._macro.assess_risk()
            except Exception:
                macro_assessment = None

        for sym in wl:
            try:
                quote = self._md.get_quote(sym)
                price = quote.get("price", 0) or 0
                df = self._md.get_ohlcv(sym, period="3mo")
                fin = self._fund.get_financials(sym)
                news = self._sent.get_news_sentiment(sym, max_items=3)

                sector_chg = 0.0
                for s in sectors:
                    if s.get("sector") == fin.get("sector"):
                        sector_chg = s["change_pct"]
                        break

                score = self._ta.score_stock(
                    df,
                    news_sentiment=0.5,
                    pe_ratio=fin.get("pe_ratio"),
                    sector_heat=sector_chg,
                )

                entry = {
                    "symbol": sym,
                    "price": price,
                    "score": score,
                    "top_news": news[0]["title"] if news else "",
                    "pe_ratio": fin.get("pe_ratio"),
                    "is_recommended": score >= SCORE_THRESHOLD,
                }
                picks_summary.append(entry)

                if score >= SCORE_THRESHOLD:
                    targets = self._ta.calc_atr_targets(df, price)
                    rec = {
                        **entry,
                        "entry": price,
                        "target": targets["take_profit"],
                        "stop_loss": targets["stop_loss"],
                        "atr": targets.get("atr"),
                        "reason": f"多因子评分 {score:.1f}",
                    }
                    recommendations.append(rec)
                    self._journal.add_pick(
                        today,
                        sym,
                        price,
                        targets["take_profit"],
                        targets["stop_loss"],
                        rec["reason"],
                    )
            except Exception as e:
                picks_summary.append({"symbol": sym, "error": str(e)})

        result = {
            "date": today,
            "mood": mood,
            "hot_sectors": sectors,
            "watchlist_analysis": picks_summary,
            "recommendations": recommendations,
        }
        if macro_assessment is not None:
            result["macro_risk"] = {
                "level": macro_assessment["level"],
                "risk_score": macro_assessment["risk_score"],
                "max_total_position": macro_assessment["max_total_position"],
                "factors": macro_assessment["factors"],
                "recommendation": macro_assessment["recommendation"],
            }
        self._write_morning_md(today, result)
        return result

    def _write_morning_md(self, date_str: str, data: dict) -> None:
        mood = data["mood"]
        lines = [
            f"# {date_str} 开市早报",
            "",
        ]
        # Macro risk section (if available)
        macro = data.get("macro_risk")
        if macro:
            level_emoji = {
                "extreme": "EXTREME",
                "high": "HIGH",
                "medium": "MEDIUM",
                "low": "LOW",
            }
            lines += [
                "## 宏观风险评估",
                (
                    f"- 风险等级: **{level_emoji.get(macro['level'], macro['level'])}**"
                    f"  |  风险分: {macro['risk_score']}"
                    f"  |  建议最大仓位: {macro['max_total_position']:.0%}"
                ),
                f"- {macro['recommendation']}",
            ]
            if macro["factors"]:
                lines.append("- 风险因子:")
                for f in macro["factors"]:
                    lines.append(f"  - {f}")
            lines.append("")
        lines += [
            "## 大盘情绪",
            (
                f"- VIX: **{mood['vix']}**  |  情绪: **{mood['fear_greed']}**"
                f"  |  SPY: {mood['spy_change_pct']:+.2f}%"
            ),
            "",
            "## 热门板块 Top3",
        ]
        for s in data["hot_sectors"]:
            lines.append(
                f"- {s['sector']} ({s.get('etf', '')}): {s['change_pct']:+.2f}%"
            )
        lines += ["", "## 建议关注股"]
        for r in data["recommendations"]:
            lines += [
                f"### {r['symbol']}  @${r['price']}  (评分: {r['score']:.1f})",
                f"- 理由: {r['reason']}",
                f"- 入场: ${r['entry']}  目标: ${r['target']}  止损: ${r['stop_loss']}",
                f"- ATR: {r.get('atr', 'N/A')}",
                f"- 新闻: {r.get('top_news', '')}",
                "",
            ]
        if not data["recommendations"]:
            lines.append("_今日无明确推荐，建议观望_")
        path = self._dir / f"{date_str}-morning.md"
        path.write_text("\n".join(lines), encoding="utf-8")

    # ── Intraday Snapshot ────────────────────────────────────────────────────

    def intraday_snapshot(self, date_str: str | None = None) -> dict:
        """Intraday P&L snapshot for open picks with hold/profit/stop suggestions."""
        today = date_str or date.today().isoformat()
        picks = self._journal.get_picks(today)
        snapshot: list[dict] = []
        for pick in picks:
            if pick["result"] != "open":
                continue
            sym = pick["symbol"]
            entry = pick["entry_price"]
            try:
                current = self._md.get_quote(sym).get("price", entry) or entry
                chg_pct = (current - entry) / entry * 100
                hit_target = current >= pick["target"]
                hit_stop_loss = current <= pick["stop_loss"]
                if hit_target:
                    suggestion = "考虑止盈"
                elif hit_stop_loss:
                    suggestion = "考虑止损"
                else:
                    suggestion = "持有"
                snapshot.append({
                    "symbol": sym,
                    "entry": entry,
                    "current": current,
                    "change_pct": round(chg_pct, 2),
                    "hit_target": hit_target,
                    "hit_stop": hit_stop_loss,
                    "suggestion": suggestion,
                })
            except Exception as e:
                snapshot.append({"symbol": sym, "error": str(e)})

        result = {"date": today, "snapshot": snapshot}
        self._append_intraday_md(today, result)
        return result

    def _append_intraday_md(self, date_str: str, data: dict) -> None:
        path = self._dir / f"{date_str}-intraday.md"
        ts = datetime.now().strftime("%H:%M")
        lines = [f"\n## 盘中快照 {ts}\n"]
        for s in data["snapshot"]:
            if "error" in s:
                lines.append(f"- {s['symbol']}: {s['error']}")
            else:
                marker = (
                    "TARGET"
                    if s["hit_target"]
                    else ("STOP" if s["hit_stop"] else "HOLD")
                )
                lines.append(
                    f"- [{marker}] **{s['symbol']}** 入场${s['entry']}"
                    f" 现价${s['current']}"
                    f" ({s['change_pct']:+.2f}%) -> {s['suggestion']}"
                )
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ── EOD Summary ──────────────────────────────────────────────────────────

    def eod_summary(
        self,
        date_str: str | None = None,
        outcomes: list[dict] | None = None,
    ) -> dict:
        """End-of-day summary with win rate, avg P&L, and per-stock recap."""
        today = date_str or date.today().isoformat()
        picks = self._journal.get_picks(today)

        if outcomes is None:
            outcomes = []
            for pick in picks:
                if pick["result"] == "open":
                    try:
                        price = (
                            self._md.get_quote(pick["symbol"]).get("price")
                            or pick["entry_price"]
                        )
                        hit = price >= pick["target"]
                        outcomes.append({
                            "symbol": pick["symbol"],
                            "exit_price": price,
                            "hit_target": hit,
                        })
                    except Exception:
                        pass

        for o in outcomes:
            self._journal.record_outcome(
                today, o["symbol"], o["exit_price"], o["hit_target"]
            )

        stats = self._journal.win_rate_stats(today)
        picks_final = self._journal.get_picks(today)
        self._write_eod_md(today, picks_final, stats)
        return stats

    def _write_eod_md(
        self, date_str: str, picks: list[dict], stats: dict
    ) -> None:
        lines = [
            f"# {date_str} 收盘总结",
            "",
            "## 胜率统计",
            (
                f"- 总推荐: {stats['total_picks']} 只  |"
                f"  胜: {stats['wins']}  |  负: {stats['losses']}"
            ),
            (
                f"- **胜率: {stats['win_rate']:.1%}**  |"
                f"  平均盈亏: {stats['avg_pnl_pct']:+.2f}%"
            ),
            "",
            "## 逐只复盘",
        ]
        for p in picks:
            result_label = {
                "win": "[WIN]",
                "loss": "[LOSS]",
                "open": "[OPEN]",
            }.get(p["result"], "")
            lines.append(
                f"- {result_label} **{p['symbol']}** 入场${p['entry_price']}"
                f" 目标${p['target']} 止损${p['stop_loss']}"
            )
            if p["result"] != "open":
                lines.append(
                    f"  - 结果: {p['result']} @${p.get('exit_price', '-')}"
                    f" ({p.get('pnl_pct', 0):+.2f}%)"
                )
            lines.append(f"  - 理由: {p['reason']}")
        path = self._dir / f"{date_str}-eod.md"
        path.write_text("\n".join(lines), encoding="utf-8")

    # ── Meme / Hot Stock Daily Report ──────────────────────────────────────

    def meme_daily_report(
        self,
        symbols: list[str] | None = None,
        lookback_days: int = 5,
        date_str: str | None = None,
    ) -> dict:
        """Daily hot/meme stock scan with momentum tracking and insider signals."""
        today = date_str or date.today().isoformat()

        result: dict = {"date": today, "hot_movers": [], "momentum": [],
                        "gainers": [], "losers": [], "insider_flags": []}

        if self._hot is None:
            result["error"] = "HotStocks module not configured"
            return result

        # 1. Scan for hot movers (volume + price anomalies)
        #    Use relaxed thresholds: any significant volume OR price move qualifies
        hot_movers = self._hot.scan_hot_movers(
            symbols=symbols, lookback_days=lookback_days,
            min_volume_ratio=1.2, min_price_change=2.0,
        )
        result["hot_movers"] = hot_movers

        # 2. Today's gainers/losers
        gl = self._hot.get_top_gainers_losers(symbols=symbols, top_n=10)
        result["gainers"] = gl.get("gainers", [])
        result["losers"] = gl.get("losers", [])

        # 3. Multi-day momentum for hot movers
        momentum_syms = [m["symbol"] for m in hot_movers[:10]]
        if momentum_syms:
            result["momentum"] = self._hot.track_meme_momentum(
                momentum_syms, days=lookback_days,
            )

        # 4. Insider flags for hot movers (if InsiderTrading available)
        if self._insider is not None and momentum_syms:
            for sym in momentum_syms[:5]:
                try:
                    summary = self._insider.get_insider_summary(sym)
                    if summary.get("signal") not in ("no_data", "neutral"):
                        result["insider_flags"].append(summary)
                except Exception:
                    continue

        self._write_meme_md(today, result)
        return result

    def _write_meme_md(self, date_str: str, data: dict) -> None:
        lines = [
            f"# {date_str} 热门Meme股日报",
            "",
        ]

        # Gainers / Losers
        lines += ["## 今日涨跌排行", ""]
        lines.append("| 标的 | 价格 | 涨跌 | 量比 |")
        lines.append("|------|------|------|------|")
        for g in data.get("gainers", [])[:5]:
            lines.append(
                f"| {g['symbol']} | ${g['price']} | "
                f"{g['change_pct']:+.1f}% | {g['volume_ratio']:.1f}x |"
            )
        if data.get("losers"):
            lines.append("| --- | --- | --- | --- |")
            for lo in data.get("losers", [])[:5]:
                lines.append(
                    f"| {lo['symbol']} | ${lo['price']} | "
                    f"{lo['change_pct']:+.1f}% | {lo['volume_ratio']:.1f}x |"
                )
        lines.append("")

        # Hot movers detail
        lines += ["## 量价异动股", ""]
        for m in data.get("hot_movers", [])[:10]:
            lines += [
                f"### {m['symbol']}  ${m['price']}  ({m['signal']})",
                f"- 5日涨跌: {m['change_pct']:+.1f}%  |  量比: {m['volume_ratio']:.1f}x  |  市值: {m.get('market_cap_label', 'N/A')}",
            ]
            for d in m.get("recent_days", []):
                lines.append(
                    f"  - {d['date']}  ${d['close']}  {d['change_pct']:+.1f}%  vol={d['volume']:,}"
                )
            lines.append("")

        # Momentum tracking
        if data.get("momentum"):
            lines += ["## 多日动量追踪", ""]
            lines.append("| 标的 | 价格 | 累计涨跌 | 趋势 | 做空比 |")
            lines.append("|------|------|----------|------|--------|")
            for mo in data["momentum"]:
                si = mo.get("short_interest")
                si_str = f"{si*100:.1f}%" if si else "N/A"
                lines.append(
                    f"| {mo['symbol']} | ${mo['current_price']} | "
                    f"{mo['cumulative_change_pct']:+.1f}% | "
                    f"{mo['pattern']} | {si_str} |"
                )
            lines.append("")

        # Insider flags
        if data.get("insider_flags"):
            lines += ["## 内部人异动警示", ""]
            for ins in data["insider_flags"]:
                lines.append(
                    f"- **{ins['symbol']}** [{ins['signal']}] "
                    f"买入${ins.get('buy_value', 0):,.0f} / "
                    f"卖出${ins.get('sell_value', 0):,.0f} — {ins.get('reason', '')}"
                )
            lines.append("")

        path = self._dir / f"{date_str}-meme.md"
        path.write_text("\n".join(lines), encoding="utf-8")
