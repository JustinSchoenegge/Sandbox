"""
notify.py — fire-and-forget iMessage notifications.
Phone number read from NOTIFY_PHONE env var (lives in .env, never committed).

Injection safety: phone and message are passed as osascript argv arguments,
never interpolated into the script source. The script is static code.
Any string — including newlines, AppleScript keywords, shell commands — is
treated as a literal value by the runtime, not as code.
"""

import os
import subprocess

# Static script — user data never appears here.
_SCRIPT = b"""\
on run argv
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy (item 1 of argv) of targetService
        send (item 2 of argv) to targetBuddy
    end tell
end run
"""


def notify(message: str) -> None:
    """Send an iMessage to NOTIFY_PHONE. Non-blocking fire-and-forget.

    Safe to call from any agent or thread — subprocess is detached immediately.
    No-ops silently if NOTIFY_PHONE is not set.
    """
    phone = os.environ.get("NOTIFY_PHONE", "")
    if not phone:
        return
    proc = subprocess.Popen(
        ["osascript", "-", phone, message],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc.stdin.write(_SCRIPT)
    proc.stdin.close()
