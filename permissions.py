"""
permissions.py — Trust level system for CyberVice bot personas.
Trust is extended deliberately. Never automatic.
"""

from enum import IntEnum
from typing import List


class TrustLevel(IntEnum):
    OBSERVER     = 0
    CORRESPONDENT = 1
    ADVISOR      = 2
    EXECUTOR     = 3
    AUTONOMOUS   = 4
    COLLABORATOR = 5


_DESCRIPTIONS = {
    TrustLevel.OBSERVER:      "Watches and learns. No output.",
    TrustLevel.CORRESPONDENT: "Sends observations and commentary.",
    TrustLevel.ADVISOR:       "Drafts work for approval. Music specs and ASCII art enabled.",
    TrustLevel.EXECUTOR:      "Creates finished output. Sandboxed actions enabled.",
    TrustLevel.AUTONOMOUS:    "Creates and reports back without supervision.",
    TrustLevel.COLLABORATOR:  "Parallel work, judgment calls, peer critique enabled.",
}

_CAPABILITIES: dict[TrustLevel, list[str]] = {
    TrustLevel.OBSERVER:      [],
    TrustLevel.CORRESPONDENT: ["observations", "commentary"],
    TrustLevel.ADVISOR:       ["observations", "commentary", "music_spec", "ascii_art"],
    TrustLevel.EXECUTOR:      ["observations", "commentary", "music_spec", "ascii_art", "file_write"],
    TrustLevel.AUTONOMOUS:    ["observations", "commentary", "music_spec", "ascii_art", "file_write", "autonomous_create"],
    TrustLevel.COLLABORATOR:  ["observations", "commentary", "music_spec", "ascii_art", "file_write", "autonomous_create", "peer_critique"],
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
