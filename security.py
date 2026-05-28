"""security.py — macOS security checks and maintenance tasks."""

import os
import subprocess
from datetime import datetime
from pathlib import Path


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


def run_checks():
    """Return list of (label, status_str, is_good: bool)."""
    results = []

    # System Integrity Protection
    out = _run(["csrutil", "status"])
    good = "enabled" in out.lower()
    results.append(("System Integrity Protection", "ENABLED" if good else "DISABLED", good))

    # FileVault
    out = _run(["fdesetup", "status"])
    good = out.lower().startswith("filevault is on")
    results.append(("FileVault Encryption", "ON" if good else "OFF", good))

    # Firewall
    out = _run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"])
    good = "enabled" in out.lower()
    results.append(("Application Firewall", "ENABLED" if good else "DISABLED", good))

    # Gatekeeper
    out = _run(["spctl", "--status"])
    good = "enabled" in out.lower()
    results.append(("Gatekeeper", "ENABLED" if good else "DISABLED", good))

    # Screen lock on wake
    out = _run(["defaults", "read", "com.apple.screensaver", "askForPassword"])
    good = out.strip() == "1"
    results.append(("Screen Lock on Wake", "ENABLED" if good else "DISABLED", good))

    # Remote Login (SSH) — OFF is the safe state
    out = _run(["launchctl", "list", "com.openssh.sshd"])
    ssh_active = "pid" in out.lower()
    # also check via systemsetup
    out2 = _run(["systemsetup", "-getremotelogin"], timeout=3)
    if "on" in out2.lower():
        ssh_active = True
    results.append(("Remote Login (SSH)", "ACTIVE ⚠" if ssh_active else "OFF", not ssh_active))

    # Remote Desktop (ARD)
    out = _run(["launchctl", "list", "com.apple.screensharing"])
    ard_active = "pid" in out.lower()
    results.append(("Screen Sharing / ARD", "ACTIVE ⚠" if ard_active else "OFF", not ard_active))

    # Automatic software updates — newer macOS uses AutomaticDownload instead of AutomaticCheckEnabled
    out = _run(["defaults", "read", "/Library/Preferences/com.apple.SoftwareUpdate", "AutomaticCheckEnabled"])
    if out.strip() == "1":
        good = True
    else:
        out2 = _run(["defaults", "read", "/Library/Preferences/com.apple.SoftwareUpdate", "AutomaticDownload"])
        good = out2.strip() == "1"
    results.append(("Auto Update Check", "ENABLED" if good else "DISABLED", good))

    return results


# ── Maintenance tasks ─────────────────────────────────────────────────────────

def empty_trash() -> tuple[bool, str]:
    """Empty macOS Trash via AppleScript. Returns (success, message)."""
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "Finder" to empty trash'],
            capture_output=True, timeout=10,
        )
        return True, "Trash emptied."
    except Exception as e:
        return False, f"Failed: {str(e)[:60]}"


def archive_desktop() -> tuple[bool, str]:
    """Move all non-hidden, non-system files from Desktop to Desktop/Archive/YYYY-MM-DD/."""
    desktop = Path.home() / "Desktop"
    archive = desktop / "Archive" / datetime.now().strftime("%Y-%m-%d")
    archive.mkdir(parents=True, exist_ok=True)
    moved, skipped = 0, []
    for item in desktop.iterdir():
        if item.name.startswith(".") or item.name in {"Archive"} or item.suffix == ".command":
            continue
        try:
            item.rename(archive / item.name)
            moved += 1
        except Exception:
            skipped.append(item.name)
    if moved == 0:
        return True, "Desktop already clean."
    if skipped:
        return True, f"Archived {moved} items. Skipped: {', '.join(skipped[:2])}"
    return True, f"Archived {moved} items → Archive/{archive.name}"


def check_api_key_age() -> tuple[int, str]:
    """Return (days_old, message). days_old = -1 if undetermined."""
    env_path = Path(__file__).parent / ".env"
    try:
        mtime = os.path.getmtime(env_path)
        days = int((datetime.now().timestamp() - mtime) / 86400)
        if days > 90:
            return days, f"Key is {days}d old — rotation overdue."
        if days > 30:
            return days, f"Key is {days}d old — consider rotating."
        return days, f"Key is {days}d old — OK."
    except Exception:
        return -1, "Cannot determine key age."


def open_key_rotation() -> None:
    """Open Anthropic console in the browser."""
    subprocess.Popen(["open", "https://console.anthropic.com/settings/keys"])


def get_open_ports():
    """Return sorted list of local listening TCP port numbers."""
    try:
        r = subprocess.run(["netstat", "-an", "-p", "tcp"], capture_output=True, text=True, timeout=5)
        ports = set()
        for line in r.stdout.splitlines():
            if "LISTEN" in line:
                parts = line.split()
                if len(parts) >= 4:
                    addr = parts[3]
                    port_str = addr.rsplit(".", 1)[-1]
                    if port_str.isdigit():
                        ports.add(int(port_str))
        return sorted(ports)
    except Exception:
        return []
