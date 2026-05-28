# Dark Hour Dashboard

This is a personal operating environment. Not a productivity app. Not a chatbot wrapper. A single place where an AI that knows your specific data — your habits, your money, your tasks, your creative work — reflects your life back to you and develops genuine taste through your feedback over time.

You own everything. Your data stays on your machine. Your API key goes directly to Anthropic. Nobody profits from you using it. The AI you interact with has been shaped by your choices, not an average user's.

Built on Python + Textual. Aesthetic: dark navy, amber gold, Vice City neon.

---

## What It Is

Most interfaces are built to keep you engaged. This one is built to make you more aware. The difference is that it synthesizes — habits + money + tasks + notes simultaneously — and the AI that does that synthesis is yours to define, calibrate, and extend trust to over time.

**NEON** is the AI persona at the center of it. It runs on Claude Sonnet 4.6, sees all your dashboard data at once, and remembers what you've approved and rejected across sessions. Every judgment you make trains it toward your specific aesthetic. Over months it becomes calibrated to how you actually think — not to some average user profile.

The **Watcher** runs alongside NEON, logging everything it says and enforcing permission boundaries. You can see its flags. You can review what got approved. The oversight is visible, not hidden.

The **trust level system** lets you decide how much autonomy NEON has — from silent observer to full autonomous generation. You extend trust deliberately, based on whether it's earned.

---

## Screens

- **Habits** — daily tracking with streaks, 30-day trend analysis, quick-mark shortcuts
- **Tasks** — daily reset task list with completion tracking
- **Notes** — tagged note capture with inline `#tag` highlighting
- **Portfolio** — stock positions with weight, P&L, tier, and goal alignment
- **Music** — song idea capture with vibe metadata
- **Bots** — NEON: chat, observe, generate, review, calibrate trust
- **Security** — macOS security check panel with auto-scan and maintenance actions
- **Vitals** — live CPU, RAM, battery, disk, temp in the status bar

---

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com) — see cost notes below
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

NEON generates a morning brief on first launch based on your dashboard state. From the Bots screen:

| Key | Action |
|-----|--------|
| `[c]` | Chat with NEON |
| `[o]` | Generate an observation |
| `[u]` | UX review of the dashboard |
| `[y]` | Approve output (saves to notes) |
| `[s]` | Save last chat reply to notes |
| `[p]` | Edit NEON's persona — start here |
| `[+/-]` | Adjust trust level (double-press to confirm) |

**Start with `[p]`.** NEON's identity — name, philosophy, constraint, traits — is what makes it yours rather than a generic assistant. Define it before you start generating.

Prefix any chat message with `?` to run in sandbox mode — no memory written, no watcher logging. Good for testing or sensitive questions.

### Trust Levels

Trust is extended deliberately. NEON earns it through output you approve.

| Level | Name | What changes |
|-------|------|-------------|
| 0 | Observer | Silent. Watcher still runs. |
| 1 | Correspondent | Observations and commentary |
| 2 | Advisor | Adds music specs and art |
| 3 | Executor | Full generation and chat |
| 4 | Autonomous | Bolder, more directive tone. Fewer qualifiers. |
| 5 | Collaborator | Full autonomy, peer critique |

The capability strings at each level are injected into every API call — NEON reads them and calibrates its behavior accordingly. Raising trust changes how NEON presents itself, not just what it's allowed to do.

---

## Customizing for Yourself

**NEON's identity:** Edit via `[p]` on the Bots screen. Name, philosophy, constraint, traits. This is the most important customization — it determines the voice you'll be talking to.

**Your name:** Set during first run, stored in `data/` (gitignored).

**Habits list:** Edit via `[a]` / `[r]` on the Habits screen.

**Task templates:** Edit `TEMPLATES` in `tasks.py` to match your daily recurring tasks.

**Color scheme:** Edit `tui.tcss`.

---

## API Cost

You pay Anthropic directly — no subscription, no middleman. The cost is yours and visible. Add credit at [console.anthropic.com](https://console.anthropic.com).

**What each interaction costs** (approximate):

| Action | Cost |
|--------|------|
| Morning brief (auto on launch) | ~$0.004 |
| One observation | ~$0.004 |
| One chat turn | ~$0.006 |
| Music spec or art | ~$0.005 |

**Daily use estimates:**

| Usage | Calls/day | Daily cost | $20 lasts |
|-------|-----------|------------|-----------|
| Light (brief + a few chats) | ~10 | ~$0.05 | 15+ months |
| Regular | ~15 | ~$0.07 | ~9 months |
| Heavy (near daily limit) | ~75 | ~$0.30 | ~2 months |

The app enforces a **daily call limit** (default: 75) visible in the status bar as `CALLS: X/75`. It hard-stops at that number and resets at midnight. You can lower it in `data/bot_config.json` under `"daily_call_limit"`.

$5–$20 in API credit is enough for most people to run this for several months of regular daily use. The software is free. The model access costs a few dollars.

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

*Your data. Your AI. Your rules. Fork it, make it yours.*
