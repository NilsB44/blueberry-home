# Setting up the Pi

## Hardware checklist

- Raspberry Pi 5, 8 GB
- Official 27 W USB-C power supply (a weaker supply throttles the Pi and can't power an SSD)
- Active Cooler (or a case with a fan)
- NVMe SSD on an M.2 HAT (recommended) or a good A2 microSD card to start
- Ethernet cable to the router if possible

## 1. Flash the OS

Use Raspberry Pi Imager → **Raspberry Pi OS Lite (64-bit)**. In the Imager settings:
set hostname `hub`, create your user, enable SSH with **public-key only**, and set Wi-Fi if not
using Ethernet.

## 2. First login and hardening

```bash
ssh you@hub.local
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y ufw unattended-upgrades fail2ban git
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
sudo dpkg-reconfigure -plow unattended-upgrades
```

Note: Docker publishes ports by editing iptables directly, bypassing ufw rules for published
ports. Only `web` publishes ports in `compose.yml`, on purpose.

## 3. Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # log out and back in
```

## 4. Run the hub

```bash
git clone <repo> ~/hub && cd ~/hub
cp .env.example .env
docker compose up -d
```

## 5. Make `hub.home` resolve

Pick one:
- In your router's admin page, add a DNS entry / static lease `hub.home → <Pi's IP>`.
- Or (Phase 3) run Pi-hole / AdGuard Home on the Pi and add a local DNS record there.
- For a quick test, add `<Pi's IP> hub.home` to your laptop's hosts file.

Give the Pi a fixed IP (DHCP reservation in the router) either way.

## 6. Trust the local certificate

Caddy creates its own certificate authority. Copy its root certificate off the Pi:

```bash
docker compose cp web:/data/caddy/pki/authorities/local/root.crt ./hub-root.crt
```

Install `hub-root.crt` as a trusted root on each device (macOS Keychain → "Always trust";
iOS: AirDrop it, install the profile, then enable it under Settings → General → About →
Certificate Trust Settings; Android: Settings → Security → Install certificate → CA).

## 7. Weekly security check and away access

```bash
sudo scripts/install-security-check.sh
```

Never forward ports on the router. To reach the hub while you're out, set up Tailscale and
use the away access switch on the Security page: see [security.md](security.md).

To update later: `scripts/update-hub.sh`.

## 8. Local model (optional)

```bash
docker compose --profile llm up -d
docker compose exec ollama ollama pull qwen3:4b
```

See [local-llm.md](local-llm.md) for model choices.
