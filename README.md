# Dark Hour Dashboard

A keyboard-first terminal dashboard built as a personal creative environment. Hosts an autonomous AI persona (NEON) that observes your daily data, generates content, and develops aesthetic taste through your feedback over time.

Built on Python + Textual. Aesthetic: dark navy, amber gold, Vice City neon.

---

## What It Does

- **Habits** — daily tracking with streaks, 30-day trend analysis, quick-mark shortcuts
- **Tasks** — daily reset task list with completion tracking
- **Notes** — tagged note capture with inline `#tag` highlighting
- **Portfolio** — stock positions with weight, P&L, tier, and goal alignment
- **Music** — song idea capture with vibe metadata
- **NEON** — AI persona (Claude Sonnet 4.6) that observes your dashboard, chats, generates content, and remembers your taste across sessions
- **Security** — macOS security check panel with auto-scan and maintenance actions
- **Vitals** — live CPU, RAM, battery, disk, temp in the status bar

---

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com)
- macOS (security and vitals modules use macOS-specific commands)

---

## Setup

```bash
git clone https://github.com/JustinSchoenegge/Sandbox.git
cd Sandbox
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your API key:
```
ANTHROPIC_API_KEY=your-key-here
```

Optionally set an admin passphrase (grants `[ADMIN]` badge):
```
DARK_HOUR_ADMIN=your-name-here
```

Run it:
```bash
python3 tui.py
```

Or add an alias to your shell profile:
```bash
alias darkhour="python3 /path/to/Sandbox/tui.py"
```

---

## Navigation

```
[1] Habits    [2] Tasks     [3] Notes
[4] Game      [5] Portfolio [6] Music
[7] Bots      [8] Security  [m] Mute  [q] Quit
```

Every screen shows its available keys at the bottom.

---

## NEON — The AI Persona

NEON runs on Claude Sonnet 4.6. On first launch it generates a morning brief based on your dashboard state. From the Bots screen:

| Key | Action |
|-----|--------|
| `[c]` | Chat with NEON |
| `[o]` | Generate an observation |
| `[u]` | UX review of the dashboard |
| `[y]` | Approve output (saves to notes) |
| `[s]` | Save last chat reply to notes |
| `[p]` | Edit NEON's persona |
| `[+/-]` | Adjust trust level (double-press to confirm) |

Prefix any chat message with `?` to run in sandbox mode — no memory written, no watcher logging.

### Trust Levels

| Level | Name | Capabilities |
|-------|------|-------------|
| 0 | Observer | No output |
| 1 | Correspondent | Observations, commentary |
| 2 | Advisor | Music specs, art |
| 3 | Executor | Full generation + chat |
| 4 | Autonomous | Unrestricted generation |
| 5 | Collaborator | All capabilities |

---

## Customizing for Yourself

**Your name:** Set during first run, stored in `data/` (gitignored).

**NEON's identity:** Edit via `[p]` on the Bots screen — name, philosophy, constraint, traits. Or edit `data/bot_config.json` directly.

**Habits list:** Edit via `[a]` / `[r]` on the Habits screen.

**Task templates:** Edit `TEMPLATES` in `tasks.py` to match your daily recurring tasks.

**Color scheme:** Edit `tui.tcss`.

---

## Architecture

```
tui.py          — Textual TUI app (screens, widgets, navigation)
bot.py          — NEON AI persona (generation, multi-turn chat, trust)
watcher.py      — Oversight agent (compliance, health monitoring)
memory.py       — Session compression and taste memory
permissions.py  — Trust level capability definitions
security.py     — macOS security checks and maintenance
vitals.py       — System metrics (CPU, RAM, battery, disk)
storage.py      — Atomic file writes (all data/ files)
config.py       — First-run setup and admin check
```

All persistent data lives in `data/` (gitignored). The app is safe to fork and push without exposing personal data.

---

## Data Files (gitignored)

```
data/habits.json        — habit list + completion logs
data/tasks.json         — task list + done flags
data/notes.json         — notes with tags and timestamps
data/portfolio.json     — stock positions
data/music.json         — song ideas
data/bot_memory.json    — NEON's taste memory across sessions
data/bot_config.json    — NEON's persona definition
```

---

*Built as a daily operating environment. Fork it, make it yours.*
