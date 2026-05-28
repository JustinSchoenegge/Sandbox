"""vitals.py — system stats for the Dark Hour vitals bar."""

import re
import shutil
import subprocess
from typing import Optional


def _run(cmd, timeout=2):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _thermal_state() -> Optional[str]:
    """Read NSProcessInfo.thermalState via objc runtime — no sudo, works on Apple Silicon."""
    try:
        import ctypes, ctypes.util
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        lib.objc_getClass.restype = ctypes.c_void_p
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.objc_msgSend.restype = ctypes.c_long
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cls  = lib.objc_getClass(b"NSProcessInfo")
        proc = lib.objc_msgSend(cls, lib.sel_registerName(b"processInfo"))
        idx  = int(lib.objc_msgSend(proc, lib.sel_registerName(b"thermalState")))
        return ["nom", "fair", "srs!", "CRIT"][max(0, min(3, idx))]
    except Exception:
        return None


def _get_temp() -> Optional[str]:
    # osx-cpu-temp works on Intel; on Apple Silicon it returns 0.0°C
    if shutil.which("osx-cpu-temp"):
        val = _run(["osx-cpu-temp"])
        if val and not val.startswith("0.0"):
            return val

    if shutil.which("istats"):
        val = _run(["istats", "cpu", "--value-only"])
        if val:
            return f"{val}°C"

    # Apple Silicon fallback: battery temperature from IORegistry.
    # Unit is 0.1 K (e.g. 2995 → 299.5 K → 26.4°C). Sanity-checked to 5–60°C.
    try:
        out = _run(["ioreg", "-rn", "AppleSmartBattery"], timeout=3)
        m = re.search(r'"Temperature"\s*=\s*(\d+)', out)
        if m:
            celsius = int(m.group(1)) / 10.0 - 273.15
            if 5 <= celsius <= 60:
                return f"{celsius:.0f}°C"
    except Exception:
        pass

    return None


def _get_fan() -> Optional[str]:
    if shutil.which("osx-cpu-temp"):
        val = _run(["osx-cpu-temp", "-f"])
        # Intel: "1225 RPM" lines
        rpm_vals = re.findall(r'(\d+)\s*RPM', val, re.IGNORECASE)
        if rpm_vals:
            # Show average RPM across all fans
            avg = sum(int(r) for r in rpm_vals) // len(rpm_vals)
            count = len(rpm_vals)
            return f"{count}x {avg} RPM"
        # Apple Silicon: tool reports count but can't read speeds
        num_m = re.search(r'Num fans:\s*(\d+)', val)
        if num_m:
            n = num_m.group(1)
            state = _thermal_state()
            return f"{n}x · {state}" if state else f"{n} fans"

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
