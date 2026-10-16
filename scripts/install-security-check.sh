#!/usr/bin/env bash
# Installs the Pi's weekly security check as a systemd timer (Sundays 03:00, an hour before
# the hub's own check reads it). Run once from the hub folder:  sudo scripts/install-security-check.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	echo "Run with sudo: it reads SSH settings, the system log and the firewall." >&2
	exit 1
fi

HUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$HUB_DIR/data/api/host-security.json"

cat >/etc/systemd/system/hub-security-check.service <<UNIT
[Unit]
Description=Blueberry Home: weekly security check of the Pi
After=network-online.target docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $HUB_DIR/scripts/pi-security-check.py --output $REPORT
UNIT

cat >/etc/systemd/system/hub-security-check.timer <<UNIT
[Unit]
Description=Blueberry Home: run the Pi security check every Sunday

[Timer]
OnCalendar=Sun *-*-* 03:00:00
# Catch up after the Pi was off at that time.
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now hub-security-check.timer
systemctl start hub-security-check.service
echo "Installed. First report: $REPORT"
systemctl list-timers hub-security-check.timer --no-pager
