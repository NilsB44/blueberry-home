#!/usr/bin/env bash
# Installs EarnApp natively and starts Pawns.app and Honeygain in Docker. Safe to re-run.
# Run from anywhere on the Pi:  bandwidth-sharing/setup.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v docker >/dev/null; then
	echo "Docker isn't installed: follow docs/pi-setup.md step 4 first." >&2
	exit 1
fi

if [[ ! -f .env ]]; then
	cp .env.example .env
	echo "Created bandwidth-sharing/.env: fill in your Pawns.app and Honeygain logins, then run this again."
	exit 1
fi

# EarnApp: the official installer (it asks you to accept EarnApp's terms).
if ! command -v earnapp >/dev/null; then
	installer="$(mktemp)"
	trap 'rm -f "$installer"' EXIT
	curl -fsSL https://brightdata.com/static/earnapp/install.sh -o "$installer"
	sudo bash "$installer"
fi

# Keep EarnApp from starving the hub, like the Pawns container's limits, and count its traffic
# for the hub's Earn apps page.
if systemctl list-unit-files earnapp.service >/dev/null 2>&1; then
	sudo mkdir -p /etc/systemd/system/earnapp.service.d
	printf '[Service]\nCPUQuota=50%%\nMemoryMax=256M\nIPAccounting=yes\n' |
		sudo tee /etc/systemd/system/earnapp.service.d/limits.conf >/dev/null
	sudo systemctl daemon-reload
	sudo systemctl restart earnapp
fi

if ! grep -qw memory /sys/fs/cgroup/cgroup.controllers; then
	echo "Warning: memory limits are off until you enable them: docs/pi-setup.md step 4." >&2
fi

docker compose up -d --remove-orphans

# Status for the hub's Earn apps page, every 5 minutes.
sudo ../scripts/install-earn-status.sh >/dev/null

echo
echo "Link this Pi to your EarnApp account by opening this link (once is enough):"
echo "https://earnapp.com/r/$(earnapp showid)"
