#!/usr/bin/env bash
# Installs the Wi-Fi device scan as a systemd timer (every 5 minutes). It runs as the owner of
# the hub's data folder, not root: pinging and reading the neighbour table need no privileges.
# Run once from the hub folder:  sudo scripts/install-network-scan.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	echo "Run with sudo: it installs a systemd timer." >&2
	exit 1
fi

HUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HUB_DIR/data/api"
OWNER="$(stat -c %U "$HUB_DIR/data/api")"
if [[ $OWNER == root ]]; then
	OWNER="${SUDO_USER:-root}"
	chown "$OWNER" "$HUB_DIR/data/api"
fi
SCAN="$HUB_DIR/data/api/network-scan.json"

cat >/etc/systemd/system/hub-network-scan.service <<UNIT
[Unit]
Description=Blueberry Home: list the devices on the Wi-Fi
After=network-online.target

[Service]
Type=oneshot
User=$OWNER
ExecStart=/usr/bin/python3 $HUB_DIR/scripts/pi-network-scan.py --output $SCAN
# Lets ping work on systems that only allow raw sockets.
AmbientCapabilities=CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_RAW
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$HUB_DIR/data/api
PrivateTmp=true
UNIT

cat >/etc/systemd/system/hub-network-scan.timer <<UNIT
[Unit]
Description=Blueberry Home: scan the Wi-Fi every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now hub-network-scan.timer
systemctl start hub-network-scan.service
echo "Installed. Latest scan: $SCAN"
systemctl list-timers hub-network-scan.timer --no-pager
