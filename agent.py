"""
agent.py — Claude API calls for alignment, song generation, and note questions.

DATA SENT TO ANTHROPIC API — know before you call:
  prefetch_alignments : sector names + user-defined investment goals
  generate_song       : song title + vibe string
  generate_questions  : sanitized note text only (no timestamps, no tags,
                        truncated to _NOTE_CHAR_LIMIT chars per note,
                        capped at _NOTE_COUNT_LIMIT most recent notes)

Add a # → ANTHROPIC API comment to any new function that makes an outbound call.
"""

import json
import os

import anthropic

NOTES_FILE = "data/notes.json"

_NOTE_CHAR_LIMIT = 200    # max chars per note sent to the API
_NOTE_COUNT_LIMIT = 20    # max number of notes sent per call

_client = None
_cache = {}               # tag → questions string (process-scoped)
_alignment_cache = {}     # (frozenset(goals), sector) → (label, style)


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


# internal alias so existing callers in this module don't break
_get_client = get_client


def get_all_tags(notes):
    tags = set()
    for note in notes:
        tags.update(note.get("tags", []))
    return sorted(tags)


def get_notes_by_tag(notes, tag):
    return [n for n in notes if tag in n.get("tags", [])]


def get_alignment(sector, goals):
    """Return cached (label, style) for this sector+goals pair, or None if not yet classified."""
    return _alignment_cache.get((frozenset(goals), sector))


def _sanitize_notes_for_api(notes: list) -> str:
    """Strip timestamps and tags; truncate long notes; cap count.
    Only plain note text leaves the process — no metadata."""
    recent = notes[-_NOTE_COUNT_LIMIT:]
    lines = []
    for n in recent:
        text = n.get("text", "")
        if len(text) > _NOTE_CHAR_LIMIT:
            text = text[:_NOTE_CHAR_LIMIT] + "…"
        lines.append(f"- {text}")
    return "\n".join(lines)


def prefetch_alignments(sectors, goals):  # → ANTHROPIC API
    """Batch-classify all sectors in one Haiku call. Safe to call on every render — no-ops if cached."""
    goals_key = frozenset(goals)
    missing = [s for s in sectors if (goals_key, s) not in _alignment_cache]
    if not missing:
        return

    goals_text = "\n".join(f"- {g}" for g in goals)
    sector_list = "\n".join(f"- {s}" for s in missing)

    try:
        response = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=[{
                "type": "text",
                "text": (
                    "You are an investment advisor. Classify whether investment sectors "
                    "align with stated goals. Respond with valid JSON only, no explanation."
                ),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": (
                    f"Investment goals:\n{goals_text}\n\n"
                    f"Classify each sector as exactly \"Strong fit\", \"Partial fit\", or \"Not aligned\".\n"
                    f"Sectors:\n{sector_list}\n\n"
                    f"Return JSON: {{\"SectorName\": \"classification\"}}"
                ),
            }],
        )
        style_map = {
            "Strong fit": "bold green",
            "Partial fit": "bold yellow",
            "Not aligned": "dim red",
        }
        result = json.loads(response.content[0].text.strip())
        for s, label in result.items():
            _alignment_cache[(goals_key, s)] = (label, style_map.get(label, "dim red"))
    except Exception:
        pass  # Caller falls back to keyword matching


def generate_song(title, vibe):  # → ANTHROPIC API
    """Generate complete song lyrics, structure, and chords for a given title and vibe."""
    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": (
                "You are a talented songwriter and musician. "
                "Create complete, authentic songs with clear structure and evocative lyrics. "
                "Be specific with musical details — key, tempo, chords — not generic."
            ),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                f"Create a complete song from this idea:\n\n"
                f"Title: {title}\n"
                f"Vibe/mood: {vibe}\n\n"
                "Include:\n"
                "1. Key and tempo (e.g., A minor, 85 BPM)\n"
                "2. Song structure (e.g., Verse – Chorus – Verse – Chorus – Bridge – Chorus)\n"
                "3. Full lyrics for each section, clearly labeled\n"
                "4. Chord progression for verse and chorus\n\n"
                "Be concise but complete. Make it feel real."
            ),
        }],
    )
    return response.content[0].text.strip()


def generate_questions(tag, tagged_notes):  # → ANTHROPIC API
    """Return (questions_str, from_cache). Calls Claude Sonnet if not cached."""
    if tag in _cache:
        return _cache[tag], True

    notes_text = _sanitize_notes_for_api(tagged_notes)

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=[{
            "type": "text",
            "text": (
                "You are a thoughtful personal productivity assistant. "
                "Help users reflect deeply on their notes and identify concrete "
                "next steps, unresolved questions, and areas for deeper thinking."
            ),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                f"The user captured these notes tagged with {tag}:\n\n"
                f"{notes_text}\n\n"
                "Generate 3–5 specific, actionable follow-up questions to help "
                "the user think more deeply or take next steps. "
                "Return only the numbered questions, no preamble."
            ),
        }],
    )

    questions = response.content[0].text.strip()
    _cache[tag] = questions
    return questions, False
