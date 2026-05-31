"""security.py — macOS security checks and maintenance tasks."""

import json
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

_SYSTEM = platform.system()

CACHE_FILE = "data/security_cache.json"


def save_scan_cache(checks: list, ports: list) -> None:
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "checks": [{"label": l, "status": s, "is_good": g} for l, s, g in checks],
            "ports": ports,
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def load_scan_cache() -> tuple:
    """Return (checks, ports, iso_timestamp) or (None, None, None) on miss."""
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        checks = [(d["label"], d["status"], d["is_good"]) for d in data["checks"]]
        return checks, data["ports"], data["timestamp"]
    except Exception:
        return None, None, None


def cache_age_hours() -> float:
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        ts = datetime.fromisoformat(data["timestamp"])
        return (datetime.now() - ts).total_seconds() / 3600
    except Exception:
        return float("inf")


def count_api_keys() -> int:
    """Count non-placeholder API keys/tokens in .env."""
    env_path = Path(__file__).parent / ".env"
    count = 0
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if any(s in key.upper() for s in ("_KEY", "_TOKEN", "_SECRET")):
                    if value and "your-key" not in value.lower() and len(value) > 8:
                        count += 1
    except Exception:
        pass
    return count


def update_api_key(new_key: str, key_name: str = "ANTHROPIC_API_KEY") -> tuple:
    """Rewrite key_name in .env and reload into os.environ. Returns (ok, msg)."""
    env_path = Path(__file__).parent / ".env"
    try:
        lines = env_path.read_text().splitlines(keepends=True) if env_path.exists() else []
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key_name}="):
                new_lines.append(f"{key_name}={new_key}\n")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"{key_name}={new_key}\n")
        env_path.write_text("".join(new_lines))
        os.environ[key_name] = new_key
        return True, f"{key_name} updated — active immediately."
    except Exception as e:
        return False, f"Failed: {str(e)[:60]}"


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


def run_checks():
    """Return list of (label, status_str, is_good: bool)."""
    if _SYSTEM != "Darwin":
        return []
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

    # Screen lock on wake — macOS Ventura+ stores this via sysadminctl, not defaults
    out = _run(["sysadminctl", "-screenLock", "status"])
    if "delay is" in out:
        good = "immediate" in out or ("off" not in out.lower() and "not set" not in out.lower())
    else:
        # Fallback for older macOS
        out = _run(["defaults", "-currentHost", "read", "com.apple.screensaver", "askForPassword"])
        if not out:
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
    """Empty system Trash. macOS uses AppleScript; Linux uses gio or trash-cli."""
    if _SYSTEM == "Darwin":
        try:
            r = subprocess.run(
                ["osascript", "-e", 'tell application "Finder" to empty trash'],
                capture_output=True, timeout=10,
            )
            if r.returncode != 0:
                err = (r.stderr or r.stdout).strip()[:80]
                return False, f"Trash could not be emptied: {err or 'unknown error'}"
            return True, "Trash emptied."
        except Exception as e:
            return False, f"Failed: {str(e)[:60]}"
    if _SYSTEM == "Linux":
        import shutil
        for cmd in (["gio", "trash", "--empty"], ["trash-empty"]):
            if shutil.which(cmd[0]):
                try:
                    r = subprocess.run(cmd, capture_output=True, timeout=10)
                    return (True, "Trash emptied.") if r.returncode == 0 else (False, "Trash empty failed.")
                except Exception as e:
                    return False, f"Failed: {str(e)[:60]}"
        return False, "No trash utility found (install gio or trash-cli)."
    return False, f"Empty Trash not supported on {_SYSTEM}."


def archive_desktop() -> tuple[bool, str]:
    """Move all non-hidden, non-system files from Desktop to Desktop/Archive/YYYY-MM-DD/."""
    desktop = Path.home() / "Desktop"
    archive = desktop / "Archive" / datetime.now().strftime("%Y-%m-%d")
    archive.mkdir(parents=True, exist_ok=True)
    moved, skipped = 0, []
    for item in desktop.iterdir():
        if item.name.startswith(".") or item.name in {"Archive"} or item.suffix == ".command":
            continue
        dest = archive / item.name
        if dest.exists():
            skipped.append(item.name)
            continue
        try:
            item.rename(dest)
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
    """Open Anthropic console in the default browser."""
    url = "https://console.anthropic.com/settings/keys"
    opener = {"Darwin": "open", "Linux": "xdg-open", "Windows": "start"}.get(_SYSTEM, "xdg-open")
    subprocess.Popen([opener, url])


def get_open_ports():
    """Return sorted list of local listening TCP port numbers."""
    ports = set()
    try:
        if _SYSTEM == "Darwin":
            r = subprocess.run(["netstat", "-an", "-p", "tcp"], capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if "LISTEN" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        port_str = parts[3].rsplit(".", 1)[-1]
                        if port_str.isdigit():
                            ports.add(int(port_str))
        elif _SYSTEM == "Linux":
            import shutil
            if shutil.which("ss"):
                r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
                import re
                for m in re.finditer(r":(\d+)\s", r.stdout):
                    ports.add(int(m.group(1)))
            else:
                r = subprocess.run(["netstat", "-tlnp"], capture_output=True, text=True, timeout=5)
                import re
                for m in re.finditer(r":(\d+)\s", r.stdout):
                    ports.add(int(m.group(1)))
    except Exception:
        pass
    return sorted(ports)
