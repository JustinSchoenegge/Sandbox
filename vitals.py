"""vitals.py — system stats for the Dark Hour vitals bar."""

import shutil
import subprocess


def _run(cmd, timeout=2):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _get_temp():
    if shutil.which("osx-cpu-temp"):
        val = _run(["osx-cpu-temp"])
        if val:
            return val
    if shutil.which("istats"):
        val = _run(["istats", "cpu", "--value-only"])
        if val:
            return f"{val}°C"
    return None


def _get_fan():
    if shutil.which("osx-cpu-temp"):
        val = _run(["osx-cpu-temp", "-f"])
        if val:
            return val
    if shutil.which("istats"):
        val = _run(["istats", "fan", "--value-only"])
        if val:
            return f"{val} RPM"
    return None


def gather():
    """Return a dict of current system vitals. All fields may be None on failure."""
    stats = {}

    try:
        import psutil

        stats["cpu"] = psutil.cpu_percent(interval=0.2)

        m = psutil.virtual_memory()
        stats["ram_pct"] = m.percent
        stats["ram_used_gb"] = round(m.used / 1024 ** 3, 1)
        stats["ram_total_gb"] = round(m.total / 1024 ** 3, 1)

        b = psutil.sensors_battery()
        if b:
            stats["batt_pct"] = round(b.percent)
            stats["batt_plugged"] = b.power_plugged

        # macOS splits root (system) from user data volume — check data volume
        import os
        disk_path = "/System/Volumes/Data" if os.path.exists("/System/Volumes/Data") else "/"
        d = psutil.disk_usage(disk_path)
        stats["disk_pct"] = d.percent
        stats["disk_used_gb"] = round(d.used / 1024 ** 3, 1)
        stats["disk_total_gb"] = round(d.total / 1024 ** 3, 1)
    except Exception:
        pass

    stats["temp"] = _get_temp()
    stats["fan"] = _get_fan()
    return stats
