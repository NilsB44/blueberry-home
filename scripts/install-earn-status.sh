#!/usr/bin/env bash
# Installs the bandwidth-sharing status report as a systemd timer (every 5 minutes), for the
# hub's Earn apps page. bandwidth-sharing/setup.sh runs this; to run it by hand, from the hub
# folder:  sudo scripts/install-earn-status.sh
# It runs as root because reading EarnApp's log and asking Docker about Pawns need it; the hub
# itself only reads the small JSON file it writes, so the hub gets no access to Docker.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	echo "Run with sudo: it installs a systemd timer." >&2
	exit 1
fi

HUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HUB_DIR/data/api"
STATUS="$HUB_DIR/data/api/earn-status.json"

cat >/etc/systemd/system/hub-earn-status.service <<UNIT
[Unit]
Description=Blueberry Home: status of the bandwidth-sharing apps
After=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $HUB_DIR/scripts/pi-earn-status.py --output $STATUS
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$HUB_DIR/data/api
PrivateTmp=true
UNIT

cat >/etc/systemd/system/hub-earn-status.timer <<UNIT
[Unit]
Description=Blueberry Home: check the bandwidth-sharing apps every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now hub-earn-status.timer
systemctl start hub-earn-status.service
echo "Installed. Latest status: $STATUS"
