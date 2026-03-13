from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from quant_trader.config import Config
from quant_trader.market_data import MarketData
from quant_trader.technical import TechnicalAnalysis
from quant_trader.sentiment import MarketSentiment
from quant_trader.fundamental import Fundamental
from quant_trader.trade_journal import TradeJournal, DEFAULT_REPORTS_DIR

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
    ) -> None:
        self._cfg = config
        self._md = market_data
        self._ta = technical
        self._sent = sentiment
        self._fund = fundamental
        self._journal = journal
        self._dir = reports_dir
        self._dir.mkdir(parents=True, exist_ok=True)

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
        self._write_morning_md(today, result)
        return result

    def _write_morning_md(self, date_str: str, data: dict) -> None:
        mood = data["mood"]
        lines = [
            f"# {date_str} 开市早报",
            "",
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
