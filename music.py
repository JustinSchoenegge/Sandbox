import json
import os
from datetime import datetime

from storage import atomic_save

from rich.console import Console
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.prompt import Prompt
from rich import box

console = Console()

MUSIC_FILE = "data/music.json"


def load_ideas():
    if not os.path.exists(MUSIC_FILE):
        return []
    try:
        with open(MUSIC_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_ideas(ideas):
    atomic_save(MUSIC_FILE, ideas)


def build_ideas_list(ideas):
    if not ideas:
        return Text("No ideas yet. Press a to capture one.", style="dim")

    lines = Text()
    for i, idea in enumerate(ideas, 1):
        generated = bool(idea.get("song"))
        lines.append(f"{i}. ", style="dim")
        lines.append(f"{idea['title']:<28}", style="bold white")
        lines.append(f"  {idea['vibe']}", style="dim")
        if generated:
            lines.append("  [written]", style="dim cyan")
        lines.append("\n")
    return lines


def show_idea_detail(idea, idx, ideas):
    while True:
        console.clear()
        has_song = bool(idea.get("song"))

        content = Text()
        content.append(f"{'Vibe':<14}", style="dim")
        content.append(f"{idea['vibe']}\n", style="white")
        content.append(f"{'Added':<14}", style="dim")
        content.append(f"{idea['timestamp']}\n", style="dim white")

        if has_song:
            content.append("\n")
            content.append(idea["song"], style="white")

        action = "q = back"

        console.print(Panel(
            Group(
                content,
                Rule(style="cyan dim"),
                Text(action, style="dim"),
            ),
            title=f"[bold cyan]{idea['title']}[/bold cyan]",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        choice = Prompt.ask("[cyan]  Select[/cyan]").strip().lower()

        if choice == "q":
            break


def show_music():
    message = ""
    while True:
        console.clear()
        ideas = load_ideas()
        count = len(ideas)

        hint = (
            f"1–{count} = view   a = add   q = back" if ideas
            else "a = add an idea   q = back"
        )

        console.print(Panel(
            Group(
                Text(f"{count} song idea{'s' if count != 1 else ''}", style="dim cyan"),
                Rule(style="cyan dim"),
                build_ideas_list(ideas),
                Rule(style="cyan dim"),
                Text.from_markup(message, justify="center") if message else Text(hint, style="dim"),
            ),
            title="[bold cyan]MUSIC[/bold cyan]",
            box=box.HEAVY,
            style="cyan",
            padding=(0, 1),
        ))

        choice = Prompt.ask("[cyan]  Select[/cyan]").strip().lower()

        if choice == "q":
            break
        elif choice == "a":
            title = Prompt.ask("[cyan]  Song title[/cyan]").strip()
            if not title:
                message = "[bold red]Title cannot be empty.[/bold red]"
            else:
                vibe = Prompt.ask("[cyan]  Vibe / mood[/cyan]").strip() or "open"
                ideas.append({
                    "title": title,
                    "vibe": vibe,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                    "song": None,
                })
                save_ideas(ideas)
                message = f"[bold green]'{title}' added.[/bold green]"
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(ideas):
                show_idea_detail(ideas[idx], idx, ideas)
                message = ""
            else:
                message = f"[bold red]Enter 1–{count}.[/bold red]"
        else:
            message = "[bold red]Press a number, a to add, or q.[/bold red]"
