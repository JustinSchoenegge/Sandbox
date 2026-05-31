"""
context.py — Shared dashboard context for NEON.

Builds the structured dict that BotsScreen passes to every bot API call
and provides a compact string summary for chat/brief seeding.
The 30-second cache means a 10-message conversation reads files once.
"""

from datetime import datetime, timedelta
from typing import Optional

from habits import load_habits, is_done_today, calculate_streak
from tasks import load_tasks
from notes import get_notes_meta
from portfolio import load_portfolio, calculate_weights, safe_pnl
from music import load_ideas
from prices import cached_changes

_ctx_cache: dict = {}
_ctx_cache_time: Optional[datetime] = None
_CTX_CACHE_TTL = 30  # seconds


def invalidate_context_cache() -> None:
    """Call after any data write so the next NEON call sees fresh state."""
    global _ctx_cache_time
    _ctx_cache_time = None


def build_context_dict() -> dict:
    """Build and cache the full structured context dict."""
    global _ctx_cache, _ctx_cache_time
    now = datetime.now()
    if _ctx_cache_time and (now - _ctx_cache_time).total_seconds() < _CTX_CACHE_TTL:
        return _ctx_cache

    ctx: dict = {}
    try:
        data = load_habits()
        habits = data["habits"]
        logs = data["logs"]
        ctx["habits_done"]  = sum(1 for h in habits if is_done_today(logs.get(h, [])))
        ctx["habits_total"] = len(habits)
        ctx["habits_list"]  = habits[:8]
        today_dt = now.date()
        last_30  = {(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)}
        last_14  = {(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14)}
        prior_14 = {(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14, 28)}
        trend_data = []
        for h in habits:
            log_set = set(logs.get(h, []))
            days_30 = len(log_set & last_30)
            recent  = len(log_set & last_14)
            prior   = len(log_set & prior_14)
            trend   = "↑" if recent > prior else ("↓" if recent < prior else "→")
            trend_data.append({"habit": h, "pct_30": round(days_30 / 30 * 100), "days_30": days_30, "trend": trend})
        ctx["habit_trends"] = trend_data
        if trend_data:
            ctx["habit_avg_30"] = round(
                sum(t["days_30"] for t in trend_data) / (len(trend_data) * 30) * 100
            )
        endangered = [
            {"habit": h, "streak": calculate_streak(logs.get(h, []))}
            for h in habits
            if calculate_streak(logs.get(h, [])) >= 5 and not is_done_today(logs.get(h, []))
        ]
        if endangered:
            ctx["endangered_streaks"] = endangered
    except Exception:
        pass
    try:
        tasks = load_tasks()
        remaining = [t["name"] for t in tasks if not t["done"]]
        ctx["tasks_remaining"] = len(remaining)
        ctx["tasks_open"] = remaining[:5]
        ctx["tasks_done_count"] = sum(1 for t in tasks if t["done"])
    except Exception:
        pass
    try:
        meta = get_notes_meta()
        ctx["notes_count"] = meta.get("count", 0)
    except Exception:
        pass
    try:
        portfolio = load_portfolio()
        holdings = portfolio.get("holdings", [])
        if holdings:
            rows = calculate_weights(holdings)
            total = sum(r["value"] for r in rows)
            ctx["portfolio_value"] = round(total, 2)
            ctx["portfolio_positions"] = len(rows)
            today = now.date()
            port_holdings = []
            for r in rows:
                direction = r.get("direction", "long").lower()
                pnl_pct = round(safe_pnl(r["current_price"], r["avg_cost"]), 1)
                multiplier = 1 if direction == "long" else -1
                pnl_dollars = round(multiplier * (r["current_price"] - r["avg_cost"]) * r.get("shares", 0), 2)
                days_held = None
                opened_str = r.get("opened_date", "")
                if opened_str:
                    try:
                        from datetime import date as _date
                        opened = _date.fromisoformat(opened_str)
                        days_held = (today - opened).days
                    except ValueError:
                        pass
                entry = {
                    "ticker": r["ticker"],
                    "name": r.get("name", r["ticker"]),
                    "shares": r.get("shares", 0),
                    "direction": direction,
                    "current_price": round(r["current_price"], 2),
                    "avg_cost": round(r.get("avg_cost", 0), 2),
                    "value": round(r["value"], 2),
                    "weight": round(r["weight"] * 100, 1),
                    "pnl": pnl_pct,
                    "pnl_dollars": pnl_dollars,
                }
                if days_held is not None:
                    entry["days_held"] = days_held
                port_holdings.append(entry)
            ctx["portfolio_holdings"] = port_holdings
            ctx["portfolio_top"] = port_holdings[:4]
            ctx["portfolio_goals"] = portfolio.get("goals", [])
            changes = cached_changes()
            movers = [
                {"ticker": h["ticker"], "change": changes[h["ticker"]]}
                for h in holdings
                if h["ticker"] in changes
            ]
            if movers:
                ctx["price_movers"] = sorted(movers, key=lambda x: abs(x["change"]), reverse=True)
    except Exception:
        pass
    try:
        ideas = load_ideas()
        if ideas:
            ctx["music_count"] = len(ideas)
            ctx["music_ideas"] = [
                {"title": i["title"], "vibe": i.get("vibe", "")}
                for i in ideas
            ]
    except Exception:
        pass

    _ctx_cache = ctx
    _ctx_cache_time = now
    return ctx


def summarize(ctx: dict) -> str:
    """Compact one-line summary of context for prompt seeding and chat threading."""
    parts = []
    if ctx.get("habits_done") is not None:
        parts.append(f"habits today {ctx['habits_done']}/{ctx.get('habits_total', '?')}")
    if ctx.get("habit_avg_30") is not None:
        parts.append(f"30-day habit avg {ctx['habit_avg_30']}%")
        trends = ctx.get("habit_trends", [])
        if trends:
            worst = min(trends, key=lambda x: x["pct_30"])
            parts.append(f"worst habit {worst['habit']}:{worst['pct_30']}%{worst['trend']}")
    if ctx.get("endangered_streaks"):
        names = [f"{e['habit']}({e['streak']}d)" for e in ctx["endangered_streaks"]]
        parts.append(f"ENDANGERED STREAKS: {', '.join(names)}")
    if ctx.get("tasks_remaining") is not None:
        done = ctx.get("tasks_done_count", 0)
        total = ctx["tasks_remaining"] + done
        open_t = ctx.get("tasks_open", [])
        label = f" ({', '.join(open_t[:2])})" if open_t else ""
        parts.append(f"tasks {done}/{total} done{label}")
    if ctx.get("notes_count"):
        parts.append(f"{ctx['notes_count']} notes")
    if ctx.get("portfolio_value"):
        parts.append(f"portfolio ${ctx['portfolio_value']:,.0f}")
    if ctx.get("portfolio_holdings"):
        pos_parts = []
        for h in ctx["portfolio_holdings"][:4]:
            pnl = h.get("pnl", 0)
            sign = "+" if pnl >= 0 else ""
            direction = "S" if h.get("direction") == "short" else "L"
            days = f" {h['days_held']}d" if h.get("days_held") is not None else ""
            pos_parts.append(f"{h['ticker']}[{direction}]{days} {sign}{pnl:.1f}%")
        parts.append("positions: " + "  ".join(pos_parts))
    if ctx.get("portfolio_goals"):
        goals = [
            g if isinstance(g, str) else (g.get("goal", str(g)) if isinstance(g, dict) else str(g))
            for g in ctx["portfolio_goals"][:2]
        ]
        parts.append(f"goals: {'; '.join(goals)}")
    if ctx.get("price_movers"):
        m = ctx["price_movers"][:3]
        parts.append("movers: " + " ".join(
            f'{x["ticker"]} {"↑" if x["change"] > 0 else "↓"}{abs(x["change"]):.1f}%'
            for x in m
        ))
    return ", ".join(parts)
