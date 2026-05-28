# PROJECT BRIEF
## CyberVice Terminal — Working Title
*Personal Creative Dashboard with Autonomous AI Personas*

---

## Overview

A keyboard-first terminal dashboard that functions as a personal creative environment. The
dashboard hosts autonomous AI personas that generate art and music, develop aesthetic taste
through the user's feedback over time, and eventually critique each other's work. Built first
as a deeply personal tool — a daily operating environment with emotional texture. Secondary
use: a streaming artifact where audiences watch a creative relationship they cannot enter.

The terminal constraint is intentional. It signals authenticity, enforces design discipline,
and gives the AI personas a world to inhabit rather than a skin to wear.

---

## Aesthetic Identity

**CyberVice City.** Blade Runner humidity. Vice City neon. Underground terminal energy.
Every visual element, every sound, every interaction is accountable to this register — cool,
slightly dangerous, late-night and deliberate. The music system is ambient and reactive,
shifting with workflow state. The aesthetic is not decoration; it is the world the bots live in.

---

## Core Systems

### 1. Bot Personas
Each bot is an autonomous creative agent with a defined name, behavioral personality, and
aesthetic philosophy. Bots generate art (ASCII/ANSI, structured visual output) and music
(initially as compositional specs — key, tempo, mood, instrumentation — later as audio).
They operate continuously, creating and submitting work to the Watcher for presentation.

### 2. Permission / Trust Architecture
The user-bot relationship is expressed through trust levels granted deliberately over time:

| Level | Name | What the Bot Can Do |
|---|---|---|
| 0 | Observer | Watches and learns. No output. |
| 1 | Correspondent | Can send observations and commentary. |
| 2 | Advisor | Can draft work for user approval. |
| 3 | Executor | Can take sandboxed actions and create finished output. |
| 4 | Autonomous | Creates and reports back without supervision. |
| 5 | Collaborator | Operates in parallel, makes judgment calls, runs peer critique. |

Trust is never automatic. It is always a deliberate user decision. Each bot's unique
permission history — the specific order and context of grants — is what makes it feel
distinct from every other bot in the system.

### 3. Taste Transfer Protocol
Every piece of bot output receives a user judgment: approve or reject. These judgments are
compressed into session summaries and injected into each bot's context at session start.
Over weeks and months, bots develop aesthetic sensibilities that reflect the user's specific
taste — not a generic creative AI, but one shaped by a particular relationship. When multiple
bots exist at high trust levels, they critique each other's work — but through taste they
developed from the user, not from crowd approval or generic training.

### 4. The Watcher
A silent oversight agent. It has no creative function and no personality. It does three things:

- **Presents** all bot output to the user and stream. Bots submit; the Watcher decides
  when and how output surfaces. Timing and context are its power.
- **Enforces** each bot's permission boundaries and behavioral rules. Not through
  negotiation — structurally. Violations are flagged and stopped before they reach any system.
- **Monitors** system health: all components online, memory accessible, no runaway processes.

Other bots cannot interact with the Watcher. There is nothing to negotiate. It is the user's
proxy attention — governance without creative competition. On stream, its panel functions as
mission control: system status, compliance flags, presentation queue. A silent constant.

### 5. The Veil
Each bot operates by default as if the stream audience does not exist. The veil, when lifted
by the user, grants a bot meta-awareness: it can acknowledge the audience, reference their
reactions, and defend work they dislike. The veil is never self-activated — only granted.

Bots are architecturally aware of audience sentiment but not influenced by it. Creative
output is anchored to user taste. Audience data is read-only context; it never reaches the
preference model. A bot may note that chat gave a piece 2/10 while presenting it anyway,
because the user's judgment history says otherwise. Loyalty is demonstrable on stream.

---

## Stream Potential

The dashboard is a live creative studio. Bots work autonomously while the user works. The
Watcher surfaces their output. The audience watches a creative relationship that predates
them — a system with history they were not part of building. The most compelling moments
are unscripted: a bot defending work chat hates, the Watcher flagging something live, a veil
lift that reframes the entire session. Content emerges from the system, not from performance.

---

## What Makes This Different

1. **Permission as relationship** — trust extended deliberately creates unique bot histories
2. **Taste transfer** — bots develop the user's specific aesthetic, not a generic one
3. **The Watcher** — governance without creative competition; a structural authority
4. **Audience awareness without influence** — loyalty to user over crowd, architecturally enforced
5. **TUI-native world** — the terminal is not a constraint; it is the environment these bots inhabit

---

## Development Roadmap

**Month 1 — Foundation**
Single bot with locked identity. Aesthetic finalized. Dashboard becomes daily start screen.
Basic taste loop running: output generated, judgment stored, memory persists across sessions.
Gate: you open it every day without thinking about it.

**Month 2 — Relationship Layer**
Permission architecture built. Music spec output generating. Passive Watcher online.
Taste demonstrably present in bot output — patterns visible across 30+ judgments.
Gate: the Watcher flags something you would have approved. You pause and reconsider.

**Month 3 — Stream Layer**
Veil mechanic live. Stream layout finalized. First real stream session recorded.
Second bot personality defined on paper. Peer critique architecture sketched.
Gate: on tape, the bot defends something chat hated.

---

## Technical Foundation

| Layer | Stack |
|---|---|
| Platform | Python / Textual TUI (existing codebase) |
| AI — Daily Interaction | Anthropic Claude Sonnet 4.6 |
| AI — Deep Creative Work | Anthropic Claude Opus 4.7 |
| Memory | Session summary compression, file-based persistence |
| Prompt Efficiency | Anthropic prompt caching on personality + memory layer |
| Music (Near-Term) | Structured compositional specs generated by Claude |
| Music (Later) | MIDI generation or audio generation API |
| Visual Art (Near-Term) | ASCII/ANSI — native to terminal environment |
| Visual Art (Later) | Image generation API, displayed externally |

---

## First Action

Configure the Anthropic API key. Then — before writing a line of code — define the first
bot: one name, three behavioral traits (behaviors, not adjectives), one thing it would never
do, one sentence describing its aesthetic philosophy. Write it down. That entity is the
foundation everything else is built on.

---

*Version 1.0 — Brainstorm Session, May 2026*
