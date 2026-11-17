#!/usr/bin/env python3
"""Reports how the bandwidth-sharing apps are doing, for the hub's Earn apps page.

The hub runs in a container without access to systemd or Docker, on purpose, so this runs on the
Pi from a systemd timer every 5 minutes (see scripts/install-earn-status.sh). For EarnApp (a
systemd service) and Pawns.app (a container) it records whether it runs, its traffic and its
latest log lines. Traffic counters reset when an app restarts, so totals are kept in the output
file across runs. Earnings aren't available on the Pi. Standard library only.

    sudo python3 scripts/pi-earn-status.py --output data/api/earn-status.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

PAWNS_CONTAINER = "bandwidth-pawns-1"
LOG_LINES = 20
LOG_LINE_MAX = 300
# Pawns writes its messages without a newline, so `docker logs --timestamps` runs them together.
DOCKER_TIMESTAMP = re.compile(r"(?<=.)(?=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z )")


def run(*cmd: str) -> tuple[int, str]:
    """Exit code and output (stdout and stderr together); 127 if the command isn't there."""
    if not shutil.which(cmd[0]):
        return 127, ""
    try:
        out = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return out.returncode, out.stdout


def log_tail(text: str) -> list[str]:
    lines = [line[:LOG_LINE_MAX] for line in text.splitlines() if line.strip()]
    return lines[-LOG_LINES:]


def systemd_props(text: str) -> dict[str, str]:
    """`systemctl show -p A,B` prints A=...\\nB=..."""
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def net_dev_bytes(text: str) -> int:
    """Received plus sent bytes on every interface but loopback, from /proc/<pid>/net/dev."""
    total = 0
    for line in text.splitlines()[2:]:
        name, _, fields = line.partition(":")
        values = fields.split()
        if name.strip() != "lo" and len(values) >= 9:
            total += int(values[0]) + int(values[8])
    return total


def earnapp() -> dict:
    code, out = run(
        "systemctl",
        "show",
        "earnapp.service",
        "-p",
        "LoadState,ActiveState,SubState,IPIngressBytes,IPEgressBytes",
    )
    props = systemd_props(out) if code == 0 else {}
    if props.get("LoadState") != "loaded":
        return {"installed": False, "running": False, "state": "not installed", "counter": None}
    try:
        # "[not set]" until IP accounting is on (bandwidth-sharing/setup.sh turns it on).
        counter = int(props["IPIngressBytes"]) + int(props["IPEgressBytes"])
    except (KeyError, ValueError):
        counter = None
    _, journal = run(
        "journalctl", "-u", "earnapp", "-n", str(LOG_LINES), "--no-pager", "-o", "short-iso"
    )
    return {
        "installed": True,
        "running": props.get("ActiveState") == "active",
        "state": props.get("SubState") or props.get("ActiveState", "unknown"),
        "counter": counter,
        "log": log_tail(journal),
    }


def pawns() -> dict:
    code, out = run("docker", "inspect", "--format", "{{json .State}}", PAWNS_CONTAINER)
    if code != 0:
        return {"installed": False, "running": False, "state": "not installed", "counter": None}
    state = json.loads(out)
    counter = None
    if state.get("Running") and state.get("Pid"):
        try:
            counter = net_dev_bytes(Path(f"/proc/{state['Pid']}/net/dev").read_text())
        except OSError:
            pass
    _, logs = run("docker", "logs", "--tail", str(LOG_LINES), "--timestamps", PAWNS_CONTAINER)
    return {
        "installed": True,
        "running": bool(state.get("Running")),
        "state": state.get("Status", "unknown"),
        "counter": counter,
        "log": log_tail(DOCKER_TIMESTAMP.sub("\n", logs)),
    }


def add_traffic(app: dict, previous: dict, today: date) -> dict:
    """Adds today's and the running total from the counter, carrying totals over restarts."""
    counter, last = app["counter"], previous.get("counter")
    if counter is None:
        delta = 0
    elif last is None or counter < last:
        # First reading, or the app restarted and its counter started again from zero.
        delta = counter
    else:
        delta = counter - last
    same_day = previous.get("day") == today.isoformat()
    return app | {
        "day": today.isoformat(),
        "today_bytes": (previous.get("today_bytes", 0) if same_day else 0) + delta,
        "total_bytes": previous.get("total_bytes", 0) + delta,
        "counted_since": previous.get("counted_since") or (today.isoformat() if delta else None),
    }


def report(previous: dict, today: date) -> dict:
    apps = {"earnapp": earnapp(), "pawns": pawns()}
    old = previous.get("apps", {})
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "apps": {k: add_traffic(v, old.get(k, {}), today) for k, v in apps.items()},
    }


def read_previous(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write(data: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # Write next to the target and rename, so the hub never reads half a file.
    fd, tmp = tempfile.mkstemp(dir=output.parent, prefix=".earn-status.")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1)
    # Readable only by the owner of the hub's data folder (the hub's app user): the log lines
    # may hold account details.
    folder = output.parent.stat()
    if os.geteuid() == 0:
        os.chown(tmp, folder.st_uid, folder.st_gid)
    os.chmod(tmp, 0o600)
    os.replace(tmp, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("data/api/earn-status.json"))
    args = parser.parse_args()
    data = report(read_previous(args.output), date.today())
    write(data, args.output)
    print(", ".join(f"{k}: {v['state']}" for k, v in data["apps"].items()), "->", args.output)


if __name__ == "__main__":
    main()
