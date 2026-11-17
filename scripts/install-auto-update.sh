#!/usr/bin/env bash
# Installs the nightly auto-update as a systemd timer (around 05:00, after Sunday's checks). It
# runs scripts/update-hub.sh as the owner of the hub folder, not root, and logs to the journal:
#   journalctl -u hub-update        # what the last runs did
# Run once from the hub folder:  sudo scripts/install-auto-update.sh
# To turn it off again:          sudo systemctl disable --now hub-update.timer
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	echo "Run with sudo: it installs a systemd timer." >&2
	exit 1
fi

HUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER="$(stat -c %U "$HUB_DIR")"

cat >/etc/systemd/system/hub-update.service <<UNIT
[Unit]
Description=Blueberry Home: pull the latest main and rebuild
Wants=network-online.target
After=network-online.target docker.service

[Service]
Type=oneshot
User=$OWNER
ExecStart=$HUB_DIR/scripts/update-hub.sh
NoNewPrivileges=true
PrivateTmp=true
UNIT

cat >/etc/systemd/system/hub-update.timer <<UNIT
[Unit]
Description=Blueberry Home: update the hub every night

[Timer]
OnCalendar=*-*-* 05:00:00
# Spreads the start over half an hour so it doesn't hit GitHub and Docker Hub on the dot.
RandomizedDelaySec=30min
# Catch up after the Pi was off at that time.
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now hub-update.timer
echo "Installed. Runs as $OWNER; see what it did with: journalctl -u hub-update"
systemctl list-timers hub-update.timer --no-pager
