import json
import os

from storage import atomic_save
from rich.console import Console
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.prompt import Prompt
from rich import box

from stocks import STOCKS, SECTOR_GOAL_MAP, TIERS, TIER_STYLES

console = Console()

PORTFOLIO_FILE = "data/portfolio.json"
BAR_WIDTH = 22

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


def calculate_weights(holdings):
    rows = []
    for h in holdings:
        price = get_stock_price(h["ticker"]) or h["avg_cost"]
        value = price * h["shares"]
        rows.append({**h, "current_price": price, "value": value})

    total = sum(r["value"] for r in rows) or 1
    for r in rows:
        r["weight"] = r["value"] / total
    return sorted(rows, key=lambda r: r["weight"], reverse=True)


def build_bar(weight):
    filled = round(weight * BAR_WIDTH)
    empty = BAR_WIDTH - filled
    return "█" * filled + "░" * empty


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


def build_chart(holdings, goals):
    if not holdings:
        return Text("No holdings yet. Press a to add your first stock.", style="dim")

    rows = calculate_weights(holdings)
    total_value = sum(r["value"] for r in rows)

    lines = Text()
    lines.append(f"{'TICKER':<6}  {'ALLOCATION':<{BAR_WIDTH + 2}}  {'WEIGHT':>6}  TIER\n", style="dim cyan")

    for r in rows:
        tier = r.get("tier", "B")
        tier_style = TIER_STYLES.get(tier, "white")
        bar = build_bar(r["weight"])
        pct = f"{r['weight']*100:.1f}%"

        lines.append(f"{r['ticker']:<6}  ", style="bold white")
        lines.append(bar, style="cyan")
        lines.append(f"  {pct:>6}  ", style="dim white")
        lines.append(f"{tier}\n", style=tier_style)

    lines.append(f"\nTotal: {len(rows)} position(s)  •  Est. value based on ~prices", style="dim")
    return lines


def add_stock_flow(portfolio):
    ticker = Prompt.ask("[cyan]  Ticker (e.g. AAPL)[/cyan]").strip().upper()

    known = next((s for s in STOCKS if s["ticker"] == ticker), None)
    if known:
        name = known["name"]
        sector = known["sector"]
        console.print(f"[dim]Found: {name} — {sector}[/dim]")
    else:
        name = Prompt.ask("[cyan]  Company name[/cyan]").strip()
        sector = Prompt.ask("[cyan]  Sector[/cyan]").strip()

    shares_raw = Prompt.ask("[cyan]  Shares owned[/cyan]").strip()
    cost_raw = Prompt.ask("[cyan]  Avg cost per share ($)[/cyan]").strip()

    if not shares_raw.replace(".", "").isdigit() or not cost_raw.replace(".", "").isdigit():
        return "[bold red]Invalid shares or cost — stock not added.[/bold red]"

    tier = Prompt.ask("[cyan]  Your tier[/cyan]", choices=TIERS)

    portfolio["holdings"].append({
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "shares": float(shares_raw),
        "avg_cost": float(cost_raw),
        "tier": tier,
    })
    save_portfolio(portfolio)
    return f"[bold green]{ticker} added to your portfolio.[/bold green]"


def edit_goals_flow(portfolio):
    current = ", ".join(portfolio["goals"])
    console.print(f"[dim]Current goals: {current}[/dim]")
    raw = Prompt.ask("[cyan]  New goals (comma separated)[/cyan]").strip()
    if raw:
        portfolio["goals"] = [g.strip() for g in raw.split(",") if g.strip()]
        save_portfolio(portfolio)
        return "[bold green]Goals updated.[/bold green]"
    return "[bold red]No changes made.[/bold red]"


def show_portfolio():
    message = ""
    while True:
        console.clear()
        portfolio = load_portfolio()
        goals = portfolio["goals"]
        holdings = portfolio["holdings"]

        console.print(Panel(
            Group(
                Text("Goals: " + "  •  ".join(goals), style="bold cyan"),
                Rule(style="cyan dim"),
                build_chart(holdings, goals),
                Rule(style="cyan dim"),
                Text.from_markup(message, justify="center") if message else Text("a = add stock   g = edit goals   q = back", style="dim"),
            ),
            title="[bold cyan]PORTFOLIO[/bold cyan]",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        choice = Prompt.ask("[cyan]  Select[/cyan]").strip().lower()

        if choice == "q":
            break
        elif choice == "a":
            message = add_stock_flow(portfolio)
        elif choice == "g":
            message = edit_goals_flow(portfolio)
        else:
            message = "[bold red]Press a to add, g for goals, or q to go back.[/bold red]"
