import json
import os

from storage import atomic_save
from stocks import STOCKS, SECTOR_GOAL_MAP
from prices import cached_price

PORTFOLIO_FILE = "data/portfolio.json"

DEFAULT_PORTFOLIO = {
    "goals": ["AI", "Tech Growth", "Streaming"],
    "holdings": [],
}


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return DEFAULT_PORTFOLIO.copy()
    try:
        with open(PORTFOLIO_FILE) as f:
            data = json.load(f)
        return {**DEFAULT_PORTFOLIO, **data}
    except json.JSONDecodeError:
        return DEFAULT_PORTFOLIO.copy()


def save_portfolio(portfolio):
    atomic_save(PORTFOLIO_FILE, portfolio)


def get_stock_price(ticker):
    for s in STOCKS:
        if s["ticker"] == ticker:
            return s["price"]
    return None


def safe_pnl(current_price: float, avg_cost: float) -> float:
    """Return P&L % or 0.0 if avg_cost is zero to avoid ZeroDivisionError."""
    return (current_price - avg_cost) / avg_cost * 100 if avg_cost else 0.0


def calculate_weights(holdings):
    rows = []
    for h in holdings:
        ticker = h["ticker"]
        # Use is-not-None so a cached price of 0.0 isn't skipped (falsy-zero bug)
        live = cached_price(ticker)
        price = live if live is not None else (get_stock_price(ticker) or h["avg_cost"])
        value = price * h["shares"]
        rows.append({**h, "current_price": price, "value": value})
    total = sum(r["value"] for r in rows) or 1
    for r in rows:
        r["weight"] = r["value"] / total
    return sorted(rows, key=lambda r: r["weight"], reverse=True)


def check_alignment(sector, goals):
    sector_keywords = SECTOR_GOAL_MAP.get(sector, [])
    user_keywords = [g.lower() for g in goals]
    matches = sum(1 for k in sector_keywords if any(k in g for g in user_keywords))
    score = matches / max(len(sector_keywords), 1)
    if score >= 0.6:
        return ("Strong fit", "bold green")
    elif score >= 0.3:
        return ("Partial fit", "bold yellow")
    else:
        return ("Not aligned", "dim red")
