import random
from datetime import datetime

from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

QUOTES = [
    "The secret of getting ahead is getting started. — Mark Twain",
    "Small daily improvements lead to stunning results. — Robin Sharma",
    "An investment in knowledge pays the best interest. — Benjamin Franklin",
    "The body achieves what the mind believes.",
    "Discipline is the bridge between goals and accomplishment. — Jim Rohn",
    "You don't have to be great to start, but you have to start to be great.",
    "The people who are crazy enough to think they can change the world are the ones who do. — Steve Jobs",
    "Push yourself, because no one else is going to do it for you.",
    "Wake up with determination. Go to bed with satisfaction.",
    "Do something today that your future self will thank you for.",
]


def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    return "Good evening"


def render_header():
    now = datetime.now()
    date_str = now.strftime("%A, %B %d %Y")
    time_str = now.strftime("%I:%M %p")
    greeting = get_greeting()

    header = Text()
    header.append(f"{greeting}, Justin\n", style="bold cyan")
    header.append(f"{date_str}  •  {time_str}", style="dim white")

    console.print(Panel(header, box=box.SIMPLE_HEAVY, style="cyan"))


def render_quote():
    today = datetime.now().strftime("%Y-%m-%d")
    random.seed(today)
    quote = random.choice(QUOTES)
    random.seed()
    console.print(Panel(
        Text(f'"{quote}"', style="italic white", justify="center"),
        title="[bold yellow]Daily Spark[/bold yellow]",
        box=box.ROUNDED,
        style="yellow",
    ))


def show_dashboard():
    console.clear()
    render_header()
    render_quote()
    console.print()
