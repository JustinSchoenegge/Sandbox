import json
import os
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich import box

console = Console()

CONFIG_FILE = "config.json"

DEFAULTS = {
    "name": "User",
    "theme": "cyan",
    "created": "",
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return first_run()
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        return {**DEFAULTS, **config}
    except json.JSONDecodeError:
        return first_run()


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def first_run():
    console.clear()
    console.print(Panel(
        Text("Welcome! Let's get you set up.", style="bold white", justify="center"),
        title="[bold cyan]FIRST RUN[/bold cyan]",
        box=box.HEAVY,
        style="cyan",
        padding=(0, 1),
    ))

    name = Prompt.ask("[cyan]  What's your name[/cyan]").strip() or "User"
    config = {**DEFAULTS, "name": name, "created": datetime.now().strftime("%Y-%m-%d")}
    save_config(config)
    return config
