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

console = Console(style="on #060615")

SCORES_FILE = "scores.txt"

_AMBER  = "#e8a020"
_BLUE   = "#4a9eff"
_GREEN  = "#00c040"
_RED    = "#c03040"
_STEEL  = "#5f87af"
_DIM    = "#2a3a5a"
_BORDER = "#1e3a5f"


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
        direction = owned.get("direction", "long")
        dir_style = _BLUE if direction == "long" else _AMBER
        lines.append("You own this  ", style=f"bold {_BLUE}")
        lines.append(f"[{direction.upper()}]", style=f"bold {dir_style}")
        lines.append("\n")
        lines.append("  Shares: ", style=f"dim {_STEEL}")
        lines.append(f"{owned['shares']}", style="white")
        lines.append("   Avg cost: ", style=f"dim {_STEEL}")
        lines.append(f"${owned['avg_cost']:.2f}", style="white")
        lines.append("   Tier: ", style=f"dim {_STEEL}")
        lines.append(f"{tier}\n", style=tier_style)
    else:
        label, style = check_alignment(sector, goals)
        lines.append("Portfolio fit: ", style="dim white")
        lines.append(f"{label}\n", style=style)
        lines.append(f"  Sector: {sector}   Goals: {', '.join(goals)}", style="dim")

    return lines


def play_round(name):
    portfolio = load_portfolio()
    stock = random.choice(STOCKS)
    attempts = 0

    console.clear()
    console.print(Panel(
        Group(
            Text(f"  {stock['name']}  ({stock['ticker']})", style=f"bold {_AMBER}"),
            Text(f"  Sector:  {stock['sector']}", style=f"dim {_STEEL}"),
            Text(f"  Hint:    {stock['hint']}", style=f"dim {_BLUE}"),
            Rule(style=_BORDER),
            Text(f"  Prices approximate as of {PRICES_AS_OF}  ·  guess within 5% to win  ·  q to quit",
                 style=f"dim {_DIM}"),
        ),
        title=f"[bold {_AMBER}]═══  STOCK GUESSER  ═══[/bold {_AMBER}]",
        box=box.DOUBLE,
        style=_BORDER,
        padding=(0, 1),
    ))

    while True:
        raw = Prompt.ask(f"[bold {_AMBER}]  Your guess $[/bold {_AMBER}]").strip()
        if raw.lower() == "q":
            console.print(f"\n[dim {_STEEL}]  Round abandoned.[/dim {_STEEL}]\n")
            return None

        if not raw.isdigit():
            console.print(f"[bold {_RED}]  Enter a whole number or q to quit.[/bold {_RED}]")
            continue

        guess = int(raw)
        attempts += 1
        diff = abs(guess - stock["price"])
        pct_off = diff / stock["price"]

        if pct_off <= 0.05:
            correct_line = Text()
            correct_line.append("  Actual price: ", style=f"dim {_STEEL}")
            correct_line.append(f"${stock['price']}", style="bold white")
            correct_line.append("  —  ", style=f"dim {_STEEL}")
            correct_line.append(f"{attempts} attempt(s)", style=f"bold {_GREEN}")
            console.print(Panel(
                Group(
                    correct_line,
                    Rule(style=_BORDER),
                    Text(f"  {stock['fact']}", style=f"italic {_STEEL}"),
                    Rule(style=_BORDER),
                    build_alignment_panel(stock, portfolio),
                ),
                title=f"[bold {_GREEN}]  CORRECT  [/bold {_GREEN}]",
                box=box.DOUBLE,
                style=_GREEN,
                padding=(0, 1),
            ))
            save_score(name, stock["ticker"], attempts)
            return attempts
        elif guess < stock["price"]:
            console.print(f"[bold {_AMBER}]  Too low![/bold {_AMBER}]  guessed [white]${guess}[/white]")
        else:
            console.print(f"[bold {_AMBER}]  Too high![/bold {_AMBER}]  guessed [white]${guess}[/white]")


def main(name="Player"):
    while True:
        console.clear()
        console.print(Panel(
            Group(
                Text("  Guess the stock price to within 5% to win.", style=f"dim {_STEEL}"),
                Text("  Prices are approximate.", style=f"dim {_DIM}"),
            ),
            title=f"[bold {_AMBER}]═══  STOCK GUESSER  ═══[/bold {_AMBER}]",
            box=box.DOUBLE,
            style=_BORDER,
            padding=(0, 1),
        ))

        play_round(name)

        again = Prompt.ask(f"\n[bold {_AMBER}]  Play again[/bold {_AMBER}]", choices=["y", "n"])
        if again != "y":
            break
