import random
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import box

console = Console()

QUOTES = [
    "The secret of getting ahead is getting started. — Mark Twain",
    "Small daily improvements lead to stunning results. — Robin Sharma",
    "An investment in knowledge pays the best interest. — Benjamin Franklin",
    "The body achieves what the mind believes.",
    "Discipline is the bridge between goals and accomplishment. — Jim Rohn",
    "You don't have to be great to start, but you have to start to be great.",
    "Push yourself, because no one else is going to do it for you.",
    "Wake up with determination. Go to bed with satisfaction.",
    "Do something today that your future self will thank you for.",
]


def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Morning"
    elif hour < 17:
        return "Afternoon"
    return "Evening"


def get_quote():
    today = datetime.now().strftime("%Y-%m-%d")
    random.seed(today)
    quote = random.choice(QUOTES)
    random.seed()
    return quote


def show_dashboard():
    console.clear()
    now = datetime.now()
    date_str = now.strftime("%a %b %d")
    time_str = now.strftime("%I:%M %p")

    content = Text()
    content.append(f"{get_greeting()}, Justin", style="bold cyan")
    content.append(f"   {date_str}  {time_str}\n", style="dim white")
    content.append(f'"{get_quote()}"', style="italic dim white")

    console.print(Panel(content, title="[bold cyan]DASHBOARD[/bold cyan]", box=box.HEAVY, style="cyan", padding=(0, 1)))
