"""
permissions.py — Trust level system for CyberVice bot personas.
Trust is extended deliberately. Never automatic.

Trust ladder — what each level actually does in the current codebase:

  L0 OBSERVER      — No generation. Bot is silenced. Watcher still runs.
  L1 CORRESPONDENT — Observations and commentary. Basic read of dashboard state.
  L2 ADVISOR       — Adds music specs and ASCII art. Output still requires [y] approval.
  L3 EXECUTOR      — Full generation and chat. Daily limit: 75 calls. Watcher logs all output.
  L4 AUTONOMOUS    — BEHAVIORAL SHIFT: NEON's self-perception changes. The trust_prefix
                     injected into every API call now reads "AUTONOMOUS" and lists
                     "autonomous_create" — NEON becomes bolder, more directive, less hedging.
                     No new code paths open yet; 'autonomous_create' is not checked anywhere.
                     If implemented: NEON would self-trigger generation without operator prompt,
                     burning daily limit faster. Watcher still enforces all existing gates.
                     Risk at L4: higher API spend, stronger assertions, less deference.
  L5 COLLABORATOR  — Adds 'peer_critique' (not yet checked in code). Intended for NEON to
                     evaluate and challenge operator decisions. Full autonomy with no upper gate.
                     Not recommended without admin gating (is_admin currently only shows badge).

The capability strings in _CAPABILITIES are injected verbatim into every API call as a
trust context block. They shape NEON's behavior through self-description — the model reads
them and calibrates its tone and initiative accordingly. This is the primary mechanism at
L4 and above; code-level gating is secondary.
"""

from enum import IntEnum
from typing import List


class TrustLevel(IntEnum):
    OBSERVER     = 0
    CORRESPONDENT = 1
    ADVISOR      = 2
    EXECUTOR     = 3
    AUTONOMOUS   = 4  # Behavioral shift — see module docstring before raising to this level
    COLLABORATOR = 5  # Full autonomy — admin gating recommended before enabling


_DESCRIPTIONS = {
    TrustLevel.OBSERVER:      "Watches and learns. No output.",
    TrustLevel.CORRESPONDENT: "Sends observations and commentary.",
    TrustLevel.ADVISOR:       "Drafts work for approval. Music specs and ASCII art enabled.",
    TrustLevel.EXECUTOR:      "Creates finished output. Sandboxed actions enabled.",
    TrustLevel.AUTONOMOUS:    "Creates and reports back without supervision. Bolder, more directive tone.",
    TrustLevel.COLLABORATOR:  "Parallel work, judgment calls, peer critique enabled. Full autonomy.",
}

_CAPABILITIES: dict[TrustLevel, list[str]] = {
    TrustLevel.OBSERVER:      [],
    TrustLevel.CORRESPONDENT: ["observations", "commentary"],
    TrustLevel.ADVISOR:       ["observations", "commentary", "music_spec", "ascii_art"],
    TrustLevel.EXECUTOR:      ["observations", "commentary", "music_spec", "ascii_art"],
    # autonomous_create not yet checked in code — behavioral shift is through prompt context only
    TrustLevel.AUTONOMOUS:    ["observations", "commentary", "music_spec", "ascii_art", "autonomous_create"],
    # peer_critique not yet checked in code — intended for NEON to challenge operator decisions
    TrustLevel.COLLABORATOR:  ["observations", "commentary", "music_spec", "ascii_art", "autonomous_create", "peer_critique"],
}


def can(trust_level: int, capability: str) -> bool:
    tl = TrustLevel(min(max(trust_level, 0), 5))
    return capability in _CAPABILITIES.get(tl, [])


def describe(trust_level: int) -> str:
    tl = TrustLevel(min(max(trust_level, 0), 5))
    return _DESCRIPTIONS.get(tl, "Unknown level.")


def level_name(trust_level: int) -> str:
    tl = TrustLevel(min(max(trust_level, 0), 5))
    return tl.name


def capabilities(trust_level: int) -> List[str]:
    tl = TrustLevel(min(max(trust_level, 0), 5))
    return list(_CAPABILITIES.get(tl, []))


def all_levels() -> List[dict]:
    return [
        {
            "level": int(tl),
            "name": tl.name,
            "description": _DESCRIPTIONS[tl],
            "capabilities": _CAPABILITIES[tl],
        }
        for tl in TrustLevel
    ]
