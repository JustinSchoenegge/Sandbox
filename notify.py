"""
notify.py — fire-and-forget iMessage notifications via AppleScript.
Phone number is read from config.json notify_phone field.
"""

import json
import os
import subprocess

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _get_phone() -> str:
    try:
        with open(_CONFIG_FILE) as f:
            return json.load(f).get("notify_phone", "")
    except Exception:
        return ""


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', "'")


def notify(message: str) -> None:
    """Send an iMessage to the configured phone number. Non-blocking."""
    phone = _get_phone()
    if not phone:
        return
    script = (
        'tell application "Messages"\n'
        '    set targetService to 1st service whose service type = iMessage\n'
        f'    set targetBuddy to buddy "{_escape(phone)}" of targetService\n'
        f'    send "{_escape(message)}" to targetBuddy\n'
        'end tell'
    )
    subprocess.Popen(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
