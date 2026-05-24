import random

from rich.console import Console
from rich.panel import Panel
from rich.console import Group
from rich.rule import Rule
from rich.text import Text
from rich.prompt import Prompt
from rich import box

from stocks import STOCKS, PRICES_AS_OF, TIER_STYLES
from portfolio import load_portfolio, check_alignment

console = Console()

SCORES_FILE = "scores.txt"


def save_score(name, ticker, attempts):
    with open(SCORES_FILE, "a") as f:
        f.write(f"{name} guessed {ticker} in {attempts} attempt(s)\n")


def build_alignment_panel(stock, portfolio):
    sector = stock["sector"]
    goals = portfolio["goals"]
    holdings = portfolio["holdings"]

    owned = next((h for h in holdings if h["ticker"] == stock["ticker"]), None)
    lines = Text()

    if owned:
        tier = owned.get("tier", "?")
        tier_style = TIER_STYLES.get(tier, "white")
        lines.append("You own this stock\n", style="bold cyan")
        lines.append(f"  Shares: {owned['shares']}   Avg cost: ${owned['avg_cost']:.2f}   Tier: ", style="dim white")
        lines.append(f"{tier}\n", style=tier_style)
    else:
        label, style = check_alignment(sector, goals)
        lines.append("Portfolio fit: ", style="dim white")
        lines.append(f"{label}\n", style=style)
        lines.append(f"  Sector: {sector}   Your goals: {', '.join(goals)}", style="dim")

    return lines


def play_round(name):
    portfolio = load_portfolio()
    stock = random.choice(STOCKS)
    attempts = 0

    console.clear()
    console.print(Panel(
        Group(
            Text(f"{stock['name']}  ({stock['ticker']})", style="bold cyan"),
            Text(f"Sector: {stock['sector']}", style="dim white"),
            Text(f"Price hint: {stock['hint']}", style="dim yellow"),
            Rule(style="cyan dim"),
            Text(f"Prices approximate as of {PRICES_AS_OF}.", style="dim"),
            Text("Guess within 5% to win. Type q to quit.", style="dim"),
        ),
        title="[bold cyan]STOCK GUESSER[/bold cyan]",
        box=box.HEAVY,
        style="cyan",
        padding=(0, 1),
    ))

    while True:
        raw = Prompt.ask("[cyan]  Your guess $[/cyan]").strip()
        if raw.lower() == "q":
            console.print("\n[dim]Round abandoned.[/dim]\n")
            return None

        if not raw.isdigit():
            console.print("[bold red]Enter a whole number or q to quit.[/bold red]")
            continue

        guess = int(raw)
        attempts += 1
        diff = abs(guess - stock["price"])
        pct_off = diff / stock["price"]

        if pct_off <= 0.05:
            console.print(Panel(
                Group(
                    Text(f"Actual price: ${stock['price']}  —  got it in {attempts} attempt(s).", style="bold green"),
                    Rule(style="green dim"),
                    Text(f"{stock['fact']}", style="italic white"),
                    Rule(style="green dim"),
                    build_alignment_panel(stock, portfolio),
                ),
                title="[bold green]CORRECT[/bold green]",
                box=box.HEAVY,
                style="green",
                padding=(0, 1),
            ))
            save_score(name, stock["ticker"], attempts)
            return attempts
        elif guess < stock["price"]:
            console.print(f"[bold yellow]Too low![/bold yellow]  (guessed ${guess})")
        else:
            console.print(f"[bold yellow]Too high![/bold yellow]  (guessed ${guess})")


def main(name="Player"):
    while True:
        console.clear()
        console.print(Panel(
            Text("Guess the stock price to within 5% to win.\nPrices are approximate.", style="dim white", justify="center"),
            title="[bold cyan]STOCK GUESSER[/bold cyan]",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        play_round(name)

        again = Prompt.ask("\n[cyan]  Play again[/cyan]", choices=["y", "n"])
        if again != "y":
            break
