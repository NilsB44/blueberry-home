#!/usr/bin/env python3
"""The Pi's weekly look at itself, for the hub's Security page.

Runs on the Pi (not in a container) as root from a systemd timer: see docs/security.md and
scripts/install-security-check.sh. Writes a JSON report that the hub reads into its own
weekly check. Standard library only, so it runs on a fresh Raspberry Pi OS.

    sudo python3 scripts/pi-security-check.py --output data/api/host-security.json
"""

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

# TCP ports the Pi is expected to listen on beyond loopback: SSH and the web (Caddy). Pi-hole
# would add 53 later. Addresses only your own VPN devices can reach (Tailscale's) don't count.
EXPECTED_TCP_PORTS = {22, 80, 443}
VPN_NETWORKS = [ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48")]
IMAGE_MAX_AGE_DAYS = 30


def run(*cmd: str, timeout: int = 60) -> subprocess.CompletedProcess | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def check(id: str, title: str, status: str, summary: str, details=()) -> dict:
    return {
        "id": id,
        "title": title,
        "status": status,
        "summary": summary,
        "details": [str(d)[:300] for d in list(details)[:50]],
    }


def _private_to_pi(addr: str) -> bool:
    """Loopback or VPN-only addresses, which nothing on the Wi-Fi or internet can reach."""
    addr = addr.strip("[]").split("%")[0]
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_loopback or any(ip in net for net in VPN_NETWORKS if net.version == ip.version)


def listening_ports(ss_output: str) -> list[tuple[int, str]]:
    """(port, address) for every TCP socket listening beyond loopback, from `ss -Htln`."""
    found = set()
    for line in ss_output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        addr, _, port = parts[3].rpartition(":")
        if not port.isdigit() or _private_to_pi(addr):
            continue
        found.add((int(port), addr))
    return sorted(found)


def check_ports() -> dict:
    title = "Open ports"
    out = run("ss", "-Htln")
    if out is None or out.returncode != 0:
        return check("ports", title, "unknown", "Couldn't list listening ports (ss missing).")
    unexpected = [
        f"port {port} on {addr}"
        for port, addr in listening_ports(out.stdout)
        if port not in EXPECTED_TCP_PORTS
    ]
    if unexpected:
        return check(
            "ports",
            title,
            "warn",
            "Something besides SSH and the hub is listening on the network. Check you know "
            "what each one is; anything on 8000 or 11434 means the API or Ollama is exposed "
            "past Caddy.",
            unexpected,
        )
    return check("ports", title, "ok", "Only SSH and the hub are listening on the network.")


def sshd_settings(text: str) -> dict[str, str]:
    settings = {}
    for line in text.splitlines():
        key, _, value = line.strip().partition(" ")
        if key:
            settings[key.lower()] = value.strip().lower()
    return settings


def check_ssh() -> dict:
    title = "SSH settings"
    out = run("sshd", "-T")
    if out is None:
        return check("ssh", title, "ok", "SSH server isn't installed.")
    if out.returncode != 0:
        return check("ssh", title, "unknown", "Couldn't read the SSH settings (run as root).")
    s = sshd_settings(out.stdout)
    problems = []
    if s.get("passwordauthentication") != "no":
        problems.append("PasswordAuthentication is on: anyone who can reach SSH can guess.")
    if s.get("kbdinteractiveauthentication") == "yes":
        problems.append("KbdInteractiveAuthentication is on: another way to type a password.")
    if s.get("permitrootlogin") not in {"no", "prohibit-password", "without-password"}:
        problems.append("PermitRootLogin allows root with a password.")
    if problems:
        return check(
            "ssh",
            title,
            "fail",
            "SSH accepts passwords. Use keys only: set PasswordAuthentication no in "
            "/etc/ssh/sshd_config.d/hub.conf and restart ssh.",
            problems,
        )
    return check("ssh", title, "ok", "Keys only; no passwords and no root password login.")


def failed_ssh_logins(journal: str) -> Counter:
    pattern = re.compile(r"(?:Failed \S+ for (?:invalid user )?\S+|Invalid user \S+) from (\S+)")
    return Counter(m.group(1) for m in pattern.finditer(journal))


def check_ssh_attempts() -> dict:
    title = "Failed SSH logins"
    out = run(
        "journalctl",
        "--since",
        "-7days",
        "--no-pager",
        "-o",
        "cat",
        "-t",
        "sshd",
        "-t",
        "sshd-session",
    )
    if out is None or out.returncode != 0:
        return check("ssh-attempts", title, "unknown", "Couldn't read the system log.")
    by_ip = failed_ssh_logins(out.stdout)
    details = [f"{ip}: {n}" for ip, n in by_ip.most_common(20)]
    public = [ip for ip in by_ip if _is_global(ip)]
    if public:
        return check(
            "ssh-attempts",
            title,
            "fail",
            f"{len(public)} internet address(es) tried to log in over SSH: SSH is reachable "
            "from outside. Remove any port forward for port 22 on the router.",
            details,
        )
    total = sum(by_ip.values())
    if total:
        return check(
            "ssh-attempts",
            title,
            "warn",
            f"{total} failed SSH logins from inside the network this week.",
            details,
        )
    return check("ssh-attempts", title, "ok", "No failed SSH logins this week.")


def _is_global(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr).is_global
    except ValueError:
        return False


def check_firewall() -> dict:
    title = "Firewall"
    out = run("ufw", "status")
    if out is None:
        return check("firewall", title, "warn", "ufw isn't installed (docs/pi-setup.md, step 2).")
    if "Status: active" in out.stdout:
        return check("firewall", title, "ok", "ufw is on.")
    return check("firewall", title, "warn", "ufw is installed but off: sudo ufw enable.")


def check_updates() -> dict:
    title = "System updates"
    auto = Path("/etc/apt/apt.conf.d/20auto-upgrades")
    auto_on = auto.exists() and re.search(
        r'Unattended-Upgrade\s+"1"', auto.read_text(errors="replace")
    )
    out = run("apt", "list", "--upgradable", timeout=120)
    pending = (
        [line for line in out.stdout.splitlines() if "/" in line] if out and out.stdout else []
    )
    security = [line.split("/")[0] for line in pending if "-security" in line]
    details = [f"Security update waiting: {p}" for p in security]
    if os.path.exists("/var/run/reboot-required"):
        details.insert(0, "A reboot is needed to finish installing updates.")
    if not auto_on:
        return check(
            "updates",
            title,
            "warn",
            "Automatic security updates are off: sudo dpkg-reconfigure -plow unattended-upgrades.",
            details,
        )
    if security:
        return check(
            "updates",
            title,
            "warn",
            f"{len(security)} security update(s) are waiting. They usually install "
            "overnight; if this repeats, run sudo apt full-upgrade.",
            details,
        )
    summary = "Automatic security updates are on and nothing urgent is waiting."
    if details:
        return check("updates", title, "warn", summary + " A reboot is pending.", details)
    return check("updates", title, "ok", summary, [f"{len(pending)} other updates available"])


def check_tailscale() -> dict:
    title = "Tailscale"
    out = run("tailscale", "status", "--json")
    if out is None:
        return check(
            "tailscale",
            title,
            "ok",
            "Not installed. That's fine: away access can't work without it, and nothing "
            "else is exposed.",
        )
    try:
        state = json.loads(out.stdout).get("BackendState", "unknown")
    except json.JSONDecodeError:
        state = "unknown"
    serve = run("tailscale", "serve", "status", "--json")
    funnel = bool(serve and serve.returncode == 0 and funnel_on(serve.stdout))
    if funnel:
        return check(
            "tailscale",
            title,
            "fail",
            "Tailscale Funnel is on, which publishes the Pi to the whole internet. Turn it "
            "off: sudo tailscale funnel reset.",
        )
    return check("tailscale", title, "ok", f"Connected ({state}); Funnel is off.")


def funnel_on(serve_status: str) -> bool:
    """Whether `tailscale serve status --json` shows anything published with Funnel."""
    try:
        config = json.loads(serve_status or "{}")
    except json.JSONDecodeError:
        return False
    allow = config.get("AllowFunnel") if isinstance(config, dict) else None
    return isinstance(allow, dict) and any(allow.values())


def image_ages(docker_output: str, now: datetime) -> list[tuple[str, int]]:
    ages = []
    for line in docker_output.splitlines():
        name, _, created = line.partition("\t")
        try:
            when = datetime.strptime(created[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            continue
        ages.append((name, (now - when).days))
    return ages


def check_images(now: datetime) -> dict:
    title = "Container images"
    out = run("docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}\t{{.CreatedAt}}")
    if out is None or out.returncode != 0:
        return check("images", title, "unknown", "Couldn't list Docker images.")
    ages = [
        (n, d)
        for n, d in image_ages(out.stdout, now)
        if n.startswith(("hub-", "ollama/", "caddy")) and not n.endswith(":<none>")
    ]
    old = [f"{n}: built {d} days ago" for n, d in ages if d > IMAGE_MAX_AGE_DAYS]
    if old:
        return check(
            "images",
            title,
            "warn",
            "Some images haven't been rebuilt in a month, so they miss recent security fixes. "
            "Run scripts/update-hub.sh.",
            old,
        )
    return check("images", title, "ok", "The hub's images were built in the last month.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    now = datetime.now(UTC)
    report = {
        "generated_at": now.isoformat(),
        "hostname": socket.gethostname()[:64],
        "checks": [
            check_ports(),
            check_ssh(),
            check_ssh_attempts(),
            check_firewall(),
            check_updates(),
            check_tailscale(),
            check_images(now),
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Write then rename, so the hub never reads half a report.
    fd, tmp = tempfile.mkstemp(dir=args.output.parent, prefix=".host-security-")
    with os.fdopen(fd, "w") as f:
        json.dump(report, f, indent=2)
    os.chmod(tmp, 0o644)
    os.replace(tmp, args.output)
    worst = max(
        (c["status"] for c in report["checks"]),
        key=["ok", "unknown", "warn", "fail"].index,
    )
    print(f"Pi security check: {worst}. Report written to {args.output}")


if __name__ == "__main__":
    main()
