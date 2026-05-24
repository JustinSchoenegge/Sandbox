import random
import json
import os

from rich.console import Console
from rich.panel import Panel
from rich.console import Group
from rich.rule import Rule
from rich.text import Text
from rich.prompt import Prompt
from rich import box
from datetime import datetime

console = Console()

SCORES_FILE = "scores.txt"
PRICES_AS_OF = "May 2026"

STOCKS = [
    {
        "name": "Apple",
        "ticker": "AAPL",
        "sector": "Technology",
        "price": 210,
        "hint": "$100 – $500",
        "fact": "Apple was the first US company to hit a $3 trillion market cap.",
    },
    {
        "name": "NVIDIA",
        "ticker": "NVDA",
        "sector": "Semiconductors",
        "price": 130,
        "hint": "$100 – $500",
        "fact": "NVIDIA's GPUs power most of the world's AI model training.",
    },
    {
        "name": "Tesla",
        "ticker": "TSLA",
        "sector": "Electric Vehicles",
        "price": 250,
        "hint": "$100 – $500",
        "fact": "Tesla delivers over 1.8 million vehicles per year globally.",
    },
    {
        "name": "Amazon",
        "ticker": "AMZN",
        "sector": "E-Commerce / Cloud",
        "price": 220,
        "hint": "$100 – $500",
        "fact": "Amazon Web Services generates more profit than the entire retail business.",
    },
    {
        "name": "Microsoft",
        "ticker": "MSFT",
        "sector": "Technology",
        "price": 430,
        "hint": "$100 – $500",
        "fact": "Microsoft invested $13 billion into OpenAI, the company behind ChatGPT.",
    },
    {
        "name": "Meta",
        "ticker": "META",
        "sector": "Social Media",
        "price": 590,
        "hint": "$500 – $1000",
        "fact": "Meta's apps — Facebook, Instagram, WhatsApp — reach over 3 billion daily users.",
    },
    {
        "name": "Netflix",
        "ticker": "NFLX",
        "sector": "Streaming",
        "price": 1100,
        "hint": "$500+",
        "fact": "Netflix has over 300 million paid subscribers across 190 countries.",
    },
    {
        "name": "Google",
        "ticker": "GOOGL",
        "sector": "Technology",
        "price": 170,
        "hint": "$100 – $500",
        "fact": "Google processes over 8.5 billion searches per day.",
    },
    {
        "name": "Palantir",
        "ticker": "PLTR",
        "sector": "AI / Defense",
        "price": 120,
        "hint": "Under $200",
        "fact": "Palantir's AI platform is used by the US Army and dozens of intelligence agencies.",
    },
    {
        "name": "Spotify",
        "ticker": "SPOT",
        "sector": "Music Streaming",
        "price": 640,
        "hint": "$500 – $1000",
        "fact": "Spotify has over 600 million monthly active users and 240 million paid subscribers.",
    },
    {
        "name": "AMD",
        "ticker": "AMD",
        "sector": "Semiconductors",
        "price": 110,
        "hint": "Under $200",
        "fact": "AMD's EPYC chips now power a significant share of major cloud data centers.",
    },
    {
        "name": "Coinbase",
        "ticker": "COIN",
        "sector": "Crypto Exchange",
        "price": 240,
        "hint": "$100 – $500",
        "fact": "Coinbase is the largest regulated crypto exchange in the United States.",
    },
]


def save_score(name, ticker, attempts):
    with open(SCORES_FILE, "a") as f:
        f.write(f"{name} guessed {ticker} in {attempts} attempt(s)\n")


def get_guess(hint):
    while True:
        raw = Prompt.ask("[cyan]  Your guess $[/cyan]").strip()
        if raw.lower() == "q":
            return None
        if raw.isdigit():
            return int(raw)
        console.print("[bold red]Enter a whole number or q to quit.[/bold red]")


def play_round(name):
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
            Text("Type q to quit this round.", style="dim"),
        ),
        title="[bold cyan]STOCK GUESSER[/bold cyan]",
        box=box.HEAVY,
        style="cyan",
        padding=(0, 1),
    ))

    while True:
        guess = get_guess(stock["hint"])
        if guess is None:
            console.print("\n[dim]Round abandoned.[/dim]\n")
            return None

        attempts += 1
        diff = abs(guess - stock["price"])
        pct_off = diff / stock["price"]

        if pct_off <= 0.05:
            console.print(Panel(
                Group(
                    Text(f"Close enough! Actual price: ${stock['price']}", style="bold green"),
                    Text(f"You got it in {attempts} attempt(s).", style="dim white"),
                    Rule(style="cyan dim"),
                    Text(f"Did you know? {stock['fact']}", style="italic white"),
                ),
                title="[bold green]CORRECT[/bold green]",
                box=box.HEAVY,
                style="green",
                padding=(0, 1),
            ))
            save_score(name, stock["ticker"], attempts)
            return attempts
        elif guess < stock["price"]:
            console.print(f"[bold yellow]Too low![/bold yellow]  (you guessed ${guess})")
        else:
            console.print(f"[bold yellow]Too high![/bold yellow]  (you guessed ${guess})")


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
