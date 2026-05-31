"""vitals.py — system stats for the Dark Hour vitals bar."""

import platform
import re
import shutil
import subprocess
from typing import Optional

_SYSTEM = platform.system()


def _run(cmd, timeout=2):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _thermal_state() -> Optional[str]:
    """Read NSProcessInfo.thermalState via objc runtime — macOS / Apple Silicon only."""
    if _SYSTEM != "Darwin":
        return None
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
    if _SYSTEM == "Darwin":
        if shutil.which("osx-cpu-temp"):
            val = _run(["osx-cpu-temp"])
            if val and not val.startswith("0.0"):
                return val
        if shutil.which("istats"):
            val = _run(["istats", "cpu", "--value-only"])
            if val:
                return f"{val}°C"
        # Apple Silicon fallback via IORegistry (unit: 0.1 K)
        try:
            out = _run(["ioreg", "-rn", "AppleSmartBattery"], timeout=3)
            m = re.search(r'"Temperature"\s*=\s*(\d+)', out)
            if m:
                celsius = int(m.group(1)) / 10.0 - 273.15
                if 5 <= celsius <= 60:
                    return f"{celsius:.0f}°C"
        except Exception:
            pass

    elif _SYSTEM == "Linux":
        # Prefer `sensors` (lm-sensors package) for a clean reading
        if shutil.which("sensors"):
            val = _run(["sensors"])
            m = re.search(r'(?:Core 0|Package id 0|CPU):\s*\+?([\d.]+)°C', val)
            if m:
                return f"{m.group(1)}°C"
        # Fallback: read first thermal zone from sysfs
        import glob
        for zone in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
            try:
                raw = int(open(zone).read().strip())
                celsius = raw / 1000.0
                if 5 <= celsius <= 110:
                    return f"{celsius:.0f}°C"
            except Exception:
                continue

    return None


def _get_fan() -> Optional[str]:
    if _SYSTEM == "Darwin":
        if shutil.which("osx-cpu-temp"):
            val = _run(["osx-cpu-temp", "-f"])
            rpm_vals = re.findall(r'(\d+)\s*RPM', val, re.IGNORECASE)
            if rpm_vals:
                avg = sum(int(r) for r in rpm_vals) // len(rpm_vals)
                return f"{len(rpm_vals)}x {avg} RPM"
            num_m = re.search(r'Num fans:\s*(\d+)', val)
            if num_m:
                n = num_m.group(1)
                state = _thermal_state()
                return f"{n}x · {state}" if state else f"{n} fans"
        if shutil.which("istats"):
            val = _run(["istats", "fan", "--value-only"])
            if val:
                return f"{val} RPM"

    elif _SYSTEM == "Linux":
        if shutil.which("sensors"):
            val = _run(["sensors"])
            rpm_vals = re.findall(r'(\d{3,5})\s*RPM', val)
            if rpm_vals:
                avg = sum(int(r) for r in rpm_vals) // len(rpm_vals)
                return f"{len(rpm_vals)}x {avg} RPM"

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
