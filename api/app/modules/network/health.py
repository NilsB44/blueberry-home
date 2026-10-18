"""How the Pi itself is doing: temperature, load, memory, disks and uptime.

Read from /proc and /sys, which a container shares with the host, so the numbers are the Pi's
own and not just the hub container's."""

import os
import shutil
from pathlib import Path

from pydantic import BaseModel

from app.config import get_settings

PROC = Path("/proc")
SYS = Path("/sys")
TEMP_WARN_C = 75
TEMP_HOT_C = 82
DISK_WARN = 0.9
MEMORY_WARN = 0.1

# Bits of the Pi firmware's get_throttled value: what's happening now, and since boot.
THROTTLE_NOW = {0: "under-voltage", 1: "CPU speed capped", 2: "throttled", 3: "temperature limit"}
THROTTLE_SINCE_BOOT = {
    16: "under-voltage",
    17: "CPU speed capped",
    18: "throttled",
    19: "temperature limit",
}


class Disk(BaseModel):
    label: str
    total_bytes: int
    free_bytes: int


class Health(BaseModel):
    status: str
    notes: list[str]
    uptime_seconds: float | None
    temperature_c: float | None
    load: list[float] | None
    cpus: int
    memory_total_bytes: int | None
    memory_available_bytes: int | None
    disks: list[Disk]
    # Power or heat problems the Pi firmware reported, e.g. "under-voltage".
    throttled_now: list[str]
    throttled_since_boot: list[str]


def _read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def uptime() -> float | None:
    text = _read(PROC / "uptime")
    return float(text.split()[0]) if text else None


def load() -> list[float] | None:
    text = _read(PROC / "loadavg")
    return [float(x) for x in text.split()[:3]] if text else None


def memory() -> tuple[int | None, int | None]:
    text = _read(PROC / "meminfo") or ""
    values = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) * 1024
    return values.get("MemTotal"), values.get("MemAvailable")


def temperature() -> float | None:
    """The CPU's temperature: the thermal zone named cpu-thermal on a Pi, else the first one."""
    zones = sorted((SYS / "class" / "thermal").glob("thermal_zone*"))
    readings = []
    for zone in zones:
        raw = _read(zone / "temp")
        if raw is None or not raw.strip().lstrip("-").isdigit():
            continue
        kind = (_read(zone / "type") or "").strip()
        readings.append((kind, int(raw) / 1000))
    for kind, celsius in readings:
        if "cpu" in kind:
            return round(celsius, 1)
    return round(readings[0][1], 1) if readings else None


def throttled() -> tuple[list[str], list[str]]:
    raw = _read(SYS / "devices" / "platform" / "soc" / "soc:firmware" / "get_throttled")
    try:
        value = int(raw.strip(), 16) if raw else 0
    except ValueError:
        value = 0
    now = [text for bit, text in THROTTLE_NOW.items() if value >> bit & 1]
    since = [text for bit, text in THROTTLE_SINCE_BOOT.items() if value >> bit & 1]
    return now, since


def disks() -> list[Disk]:
    settings = get_settings()
    url = settings.database_url
    db_dir = Path(url.removeprefix("sqlite:///")).parent if url.startswith("sqlite:///") else None
    found: list[Disk] = []
    seen: set[int] = set()
    for label, path in (("Hub data", db_dir), ("Shared files", settings.files_dir)):
        if path is None:
            continue
        try:
            device = os.stat(path).st_dev
            usage = shutil.disk_usage(path)
        except OSError:
            continue
        # The database and files usually share one disk until files move to an SSD.
        if device in seen:
            continue
        seen.add(device)
        found.append(Disk(label=label, total_bytes=usage.total, free_bytes=usage.free))
    return found


def read() -> Health:
    temp = temperature()
    total, available = memory()
    now, since = throttled()
    drives = disks()
    notes: list[str] = []
    status = "ok"

    def flag(level: str, note: str) -> None:
        nonlocal status
        notes.append(note)
        if level == "fail" or status == "ok":
            status = level

    if temp is not None and temp >= TEMP_HOT_C:
        flag("fail", f"Running hot at {temp:.0f} °C: it will slow itself down. Check the fan.")
    elif temp is not None and temp >= TEMP_WARN_C:
        flag("warn", f"Warm at {temp:.0f} °C. Fine for a while, but check the fan or case.")
    if "under-voltage" in now:
        flag("fail", "The power supply is too weak right now. Use the official 27 W one.")
    elif "under-voltage" in since:
        flag("warn", "The power dipped since the Pi started. A weak power supply or cable?")
    for d in drives:
        if d.total_bytes and d.free_bytes / d.total_bytes < 1 - DISK_WARN:
            flag("warn", f"{d.label}: the disk is over {DISK_WARN:.0%} full.")
    if total and available is not None and available / total < MEMORY_WARN:
        flag("warn", "Memory is nearly full. The assistant's model is the usual cause.")

    return Health(
        status=status,
        notes=notes,
        uptime_seconds=uptime(),
        temperature_c=temp,
        load=load(),
        cpus=os.cpu_count() or 1,
        memory_total_bytes=total,
        memory_available_bytes=available,
        disks=drives,
        throttled_now=now,
        throttled_since_boot=since,
    )
