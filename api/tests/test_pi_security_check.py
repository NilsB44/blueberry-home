"""The Pi-side check (scripts/pi-security-check.py) parses command output; test the parsing."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pi-security-check.py"
spec = importlib.util.spec_from_file_location("pi_security_check", SCRIPT)
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)


def test_listening_ports_skip_loopback_and_vpn_addresses():
    ss = """LISTEN 0 4096 0.0.0.0:443 0.0.0.0:*
LISTEN 0 4096 0.0.0.0:80 0.0.0.0:*
LISTEN 0 128 0.0.0.0:22 0.0.0.0:*
LISTEN 0 128 127.0.0.1:631 0.0.0.0:*
LISTEN 0 128 [::1]:631 [::]:*
LISTEN 0 4096 100.101.102.103:51234 0.0.0.0:*
LISTEN 0 4096 [fd7a:115c:a1e0::1]:51234 [::]:*
LISTEN 0 4096 *:11434 *:*
LISTEN 0 128 [::]:22 [::]:*"""
    assert pi.listening_ports(ss) == [
        (22, "0.0.0.0"),
        (22, "[::]"),
        (80, "0.0.0.0"),
        (443, "0.0.0.0"),
        (11434, "*"),
    ]


def test_sshd_settings():
    s = pi.sshd_settings("port 22\npasswordauthentication no\nPermitRootLogin prohibit-password\n")
    assert s["passwordauthentication"] == "no"
    assert s["permitrootlogin"] == "prohibit-password"


def test_failed_ssh_logins_by_address():
    journal = """Failed password for nils from 192.168.1.5 port 5000 ssh2
Invalid user admin from 45.33.32.156 port 4000
Failed password for invalid user root from 45.33.32.156 port 4001 ssh2
Accepted publickey for nils from 192.168.1.5 port 5001 ssh2
Failed publickey for nils from 192.168.1.5 port 5002 ssh2"""
    assert pi.failed_ssh_logins(journal) == {"192.168.1.5": 2, "45.33.32.156": 2}


def test_funnel_detection():
    assert pi.funnel_on('{"AllowFunnel": {"hub.tail1234.ts.net:443": true}}')
    assert not pi.funnel_on('{"TCP": {"443": {"HTTPS": true}}}')
    assert not pi.funnel_on("")
    assert not pi.funnel_on("No serve config")


def test_image_ages():
    out = "hub-api:latest\t2026-09-01 10:00:00 +0000 UTC\nbad line\n"
    now = datetime(2026, 10, 16, tzinfo=UTC)
    assert pi.image_ages(out, now) == [("hub-api:latest", 44)]
