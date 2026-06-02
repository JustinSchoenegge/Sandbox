# Dark Hour Dashboard

This is a personal operating environment. Not a productivity app. Not a chatbot wrapper. A single place where an AI that knows your specific data — your habits, your money, your tasks, your creative work — reflects your life back to you and develops genuine taste through your feedback over time.

You own everything. Your data stays on your machine. Your API key goes directly to Anthropic. Nobody profits from you using it. The AI you interact with has been shaped by your choices, not an average user's.

Built on Python + Textual. Aesthetic: dark navy, amber gold, Vice City neon.

**The aim is a closed loop:** you input data → NEON reads all of it at once → you get signal → you act → repeat. Every interface fights for your attention; this one spends its intelligence reflecting your own life back at you so the next decision is better-informed. The loop getting tighter and more personal over time *is* the product.

---

## What It Is

Most interfaces are built to keep you engaged. This one is built to make you more aware. The difference is that it synthesizes — habits + money + tasks + notes simultaneously — and the AI that does that synthesis is yours to define, calibrate, and extend trust to over time.

**NEON** is the AI persona at the center of it. It runs on Claude Sonnet 4.6, sees all your dashboard data at once, and remembers what you've approved and rejected across sessions. Every judgment you make trains it toward your specific aesthetic. Over months it becomes calibrated to how you actually think — not to some average user profile.

The **Watcher** runs alongside NEON, logging everything it says and gating its output by trust level. You can see its flags. You can review what got approved. The oversight is visible, not hidden.

The **trust level system** lets you decide how much autonomy NEON has — from silent observer to full autonomous generation. You extend trust deliberately, based on whether it's earned.

### How NEON Learns Your Taste

Every output NEON produces, you judge. That judgment is the training signal — no fine-tuning, no cloud profile, just a loop that runs on your machine:

```
YOU JUDGE  →  STORED  →  COMPRESSED  →  INJECTED  →  NEON ADAPTS
approve/   →  saved to →  session    →  added to  →  next output
reject        record      summarized    next prompt   reflects your taste
```

The accountability loop closes the same way in the other direction: if the morning brief flags a habit, the next session checks whether you actually did it and NEON calls out the follow-through — by name, with the streak count.

---

## Scope: What's Built vs Where It's Going

This is an actively developed personal project, not a finished product. The line between what runs today and what's still vision is drawn deliberately — the loop has to work before the world gets built around it.

**Built and working today:**

- **One AI persona, NEON** (Claude Sonnet 4.6) — sees the whole dashboard at once; generates a morning brief on launch, plus observations, chat, UX reviews, music specs, and ASCII art on demand.
- **Taste memory across sessions** — approve/reject judgments are compressed and re-injected, so NEON drifts toward your aesthetic over time.
- **Accountability loop** — flagged habits are tracked session-to-session and called out by name.
- **Trust levels (0–5)** — shift NEON's tone and gate which kinds of output it's allowed to produce.
- **The Watcher** — gates output by trust level (silent at L0), logs everything NEON says, and monitors API-key, memory, and music health.
- **Streak tripwire** — texts you (iMessage) when a long streak is about to break.
- **Prompt caching** on the static persona/context layer, so daily use stays cheap.
- **Local-first dashboard** — Habits, Tasks, Notes, Portfolio, Music, Game, Security, Vitals. Your data never leaves `data/`; your key goes straight to Anthropic.

**On the roadmap (vision, not yet built):**

- **Live market data** — portfolio prices currently come from a cache, not a real-time feed.
- **Multiple bot personas with peer critique** — today there is one bot; the architecture anticipates more.
- **The Watcher as a real-time behavioral enforcer** — today it gates by trust and logs; deeper enforcement is planned.
- **The "veil" / streaming layer** — bots aware of an audience without being influenced by it, for a live-studio stream.
- **Weekly retrospective, calendar integration, and data-schema validation.**

If a feature isn't in the "built" list, treat it as intent, not a promise.

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
- macOS or Linux (Windows is untested)
- An [Anthropic API key](https://console.anthropic.com) — optional, see cost notes below
- **Linux audio:** install `mpv` for background music (`sudo apt install mpv` or `sudo dnf install mpv`)

**macOS-only features:** Security screen checks (SIP, FileVault, Firewall, etc.) and boot sound. Everything else — habits, tasks, notes, portfolio, NEON, music, vitals — runs on Linux.

---

## Setup

```bash
git clone https://github.com/JustinSchoenegge/Sandbox.git
cd Sandbox
./setup.sh
```

That's it. `setup.sh` handles the virtual environment, dependencies, API key prompt, and wires the `darkhour` alias into your shell profile. Open a new terminal tab and run:

```bash
darkhour
```

**The API key is optional.** The app runs fully without it — habits, tasks, notes, portfolio, and music all work locally. NEON goes silent until you add one. You can add or rotate a key later via `[r]` on the Security screen (no restart required).

To set an admin passphrase (grants `[ADMIN]` badge and unlocks the Security screen):
```
DARK_HOUR_ADMIN=your-name-here
```
Add that line to your `.env` file.

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
