#!/usr/bin/env bash
# Pulls the latest version from GitHub and rebuilds the hub with fresh base images, so it
# picks up both new features and upstream security fixes. Run from anywhere on the Pi.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

git pull --ff-only
docker compose build --pull
docker compose up -d
# The local language model's server is a ready-made image, not built here: pull its latest
# release too, if it's running.
if [ -n "$(docker compose --profile llm ps -q ollama 2>/dev/null)" ]; then
	docker compose --profile llm pull ollama
	docker compose --profile llm up -d ollama
fi
docker image prune -f
echo "Blueberry Home is up to date: $(git log -1 --format='%h %s')"
