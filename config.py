import json
import os
from datetime import datetime

from storage import atomic_save
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich import box

console = Console()

CONFIG_FILE = "config.json"


def load_env():
    """Load key=value pairs from .env into os.environ (skips already-set keys)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

DEFAULTS = {
    "name": "User",
    "theme": "cyan",
    "created": "",
    "is_admin": False,
}

# Set DARK_HOUR_ADMIN=<your name> in .env to grant admin access.
_ADMIN_PASSPHRASE = os.environ.get("DARK_HOUR_ADMIN", "")


def _check_admin(config: dict) -> bool:
    return config.get("name") == _ADMIN_PASSPHRASE


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return first_run()
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        merged = {**DEFAULTS, **config}
        merged["is_admin"] = _check_admin(config)
        return merged
    except json.JSONDecodeError:
        return first_run()


def save_config(config):
    atomic_save(CONFIG_FILE, config)


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
