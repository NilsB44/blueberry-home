#!/usr/bin/env python3
"""Lists the devices on the home Wi-Fi, for the hub's Network page.

The hub runs in a container and can't see the home network's neighbours itself, so this runs on
the Pi from a systemd timer every few minutes (see scripts/install-network-scan.sh). It wakes
every address on the Pi's own network with a ping, then reads the Pi's neighbour (ARP) table.
Writes a small JSON file the hub reads. Standard library only.

    sudo python3 scripts/pi-network-scan.py --output data/api/network-scan.json
"""

import argparse
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

# Bigger networks than this (a /22) are only read from the neighbour table, not pinged.
MAX_SWEEP = 1024
HOSTNAME_TIMEOUT = 1.0


def run(*cmd: str, timeout: int = 30) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def default_route() -> tuple[str, str] | None:
    """(interface, gateway) of the IPv4 default route, from `ip -j route`."""
    out = run("ip", "-j", "-4", "route", "show", "default")
    for route in json.loads(out or "[]"):
        if route.get("dev") and route.get("gateway"):
            return route["dev"], route["gateway"]
    return None


def interface_network(dev: str) -> tuple[ipaddress.IPv4Interface, str | None] | None:
    """The Pi's own address on dev, with its network, and the interface's MAC."""
    out = run("ip", "-j", "-4", "addr", "show", "dev", dev)
    for link in json.loads(out or "[]"):
        for a in link.get("addr_info", []):
            if a.get("family") == "inet":
                return ipaddress.IPv4Interface(f"{a['local']}/{a['prefixlen']}"), link.get(
                    "address"
                )
    return None


def sweep(network: ipaddress.IPv4Network, own: ipaddress.IPv4Address) -> None:
    """Ping every address once so devices that were quiet show up in the neighbour table."""
    if network.num_addresses > MAX_SWEEP or not shutil.which("ping"):
        return
    hosts = [str(h) for h in network.hosts() if h != own]

    def ping(ip: str) -> None:
        run("ping", "-c", "1", "-W", "1", "-q", ip, timeout=3)

    with ThreadPoolExecutor(max_workers=64) as pool:
        list(pool.map(ping, hosts))


def neighbours(dev: str, network: ipaddress.IPv4Network) -> dict[str, str]:
    """MAC -> IPv4 address for every device the Pi has heard from on dev."""
    out = run("ip", "-j", "-4", "neigh", "show", "dev", dev)
    found: dict[str, str] = {}
    for n in json.loads(out or "[]"):
        mac, ip, state = n.get("lladdr"), n.get("dst"), n.get("state") or []
        if not mac or not ip or "FAILED" in state or "INCOMPLETE" in state:
            continue
        try:
            if ipaddress.ip_address(ip) not in network:
                continue
        except ValueError:
            continue
        found[mac.lower()] = ip
    return found


def hostname(ip: str) -> str:
    """What the router's DNS calls the device, e.g. "Nils-iPhone.lan" -> "Nils-iPhone"."""
    socket.setdefaulttimeout(HOSTNAME_TIMEOUT)
    try:
        name = socket.gethostbyaddr(ip)[0]
    except OSError:
        return ""
    name = name.split(".")[0]
    return "" if name == ip.split(".")[0] else name[:64]


def scan() -> dict:
    route = default_route()
    if route is None:
        raise SystemExit("No IPv4 default route: is the Pi on the network?")
    dev, gateway = route
    found = interface_network(dev)
    if found is None:
        raise SystemExit(f"{dev} has no IPv4 address")
    iface, own_mac = found
    sweep(iface.network, iface.ip)
    table = neighbours(dev, iface.network)
    if own_mac:
        table[own_mac.lower()] = str(iface.ip)
    with ThreadPoolExecutor(max_workers=16) as pool:
        names = dict(zip(table, pool.map(hostname, table.values()), strict=True))
    devices = [
        {"mac": mac, "ip": ip, "hostname": names[mac], "is_pi": mac == (own_mac or "").lower()}
        for mac, ip in sorted(table.items(), key=lambda kv: ipaddress.ip_address(kv[1]))
    ]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "interface": dev,
        "network": str(iface.network),
        "gateway": gateway,
        "devices": devices,
    }


def write(report: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # Write next to the target and rename, so the hub never reads half a file.
    fd, tmp = tempfile.mkstemp(dir=output.parent, prefix=".network-scan.")
    with os.fdopen(fd, "w") as f:
        json.dump(report, f, indent=1)
    os.chmod(tmp, 0o644)
    os.replace(tmp, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("data/api/network-scan.json"))
    args = parser.parse_args()
    report = scan()
    write(report, args.output)
    print(f"{len(report['devices'])} devices on {report['network']} -> {args.output}")


if __name__ == "__main__":
    main()
