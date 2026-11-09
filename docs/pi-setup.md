# Setting up the Pi, start to finish

Every step from an unopened box to the hub running on `https://hub.home`, in order. Expect
about an hour. Commands marked **laptop** run on your own computer (PowerShell on Windows,
Terminal on macOS), the rest run on the Pi over SSH.

## Hardware checklist

- Raspberry Pi 5, 8 GB
- Official 27 W USB-C power supply (a weaker supply throttles the Pi and can't power an SSD)
- Active Cooler (or a case with a fan)
- NVMe SSD on an M.2 HAT (recommended) or a good A2 microSD card to start
- A microSD card reader for your laptop
- Ethernet cable to the router if possible (faster and steadier than Wi-Fi for a server)

## 0. Make an SSH key on your laptop

The Pi will only accept logins from this key, never a password. **Laptop:**

```bash
ssh-keygen -t ed25519 -C "laptop"      # press Enter for the default path, set a passphrase
cat ~/.ssh/id_ed25519.pub              # Windows: type $HOME\.ssh\id_ed25519.pub
```

Skip the first line if you already have a key. The `.pub` line is what you paste into the
Imager next.

## 1. Flash the OS

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on the laptop and put
   the microSD card in.
2. Choose device **Raspberry Pi 5**, OS **Raspberry Pi OS (other) → Raspberry Pi OS Lite
   (64-bit)** (no desktop: the hub doesn't need one), and the SD card.
3. When it asks about OS customisation, choose **Edit settings**:
   - **General:** hostname `hub`; a username (e.g. `nils`) and a password (only used for
     `sudo`); Wi-Fi name and password if you're not using Ethernet; your time zone and
     keyboard layout.
   - **Services:** enable SSH, **Allow public-key authentication only**, and paste the `.pub`
     line from step 0.
4. Write the card, put it in the Pi, plug in Ethernet, then power. The first boot takes a
   couple of minutes.

Using an NVMe SSD to boot from? The simplest route is an SSD-to-USB enclosure: flash the SSD
from the laptop exactly as above, fit it on the HAT and leave the SD card out. The Pi 5 boots
from NVMe when no card is in (on an old bootloader, boot once from SD and run
`sudo rpi-eeprom-update -a` first). No enclosure? Start on the SD card; you can move later.

No SD card yet? A USB stick works to get started: flash it exactly as above (pick the stick
as the storage), plug it into a **blue** USB 3 port and power on with no card in. The Pi 5
tries SD, then NVMe, then USB, so it boots from the stick on its own. Treat it as temporary:
sticks are slow (the first build takes much longer) and wear out under the database and
Docker's writes, so keep `data/` backed up and move to an SD card or SSD when you can.

## 2. First login and hardening

**Laptop:**

```bash
ssh nils@hub.local
```

Answer `yes` to the fingerprint question. If `hub.local` isn't found, look up the Pi's IP in
your router's admin page (connected devices) and use `ssh nils@<ip>`.

Optional, so `ssh hub` is enough from now on. Add this to `~/.ssh/config` on the laptop
(Windows: `$HOME\.ssh\config`):

```
Host hub
    HostName hub.local
    User nils
```

**On the Pi:** update everything and turn on the firewall and automatic security updates.

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y ufw unattended-upgrades fail2ban git
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
sudo dpkg-reconfigure -plow unattended-upgrades     # answer Yes
```

Make sure SSH can never fall back to passwords (the weekly check looks for this):

```bash
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n' \
  | sudo tee /etc/ssh/sshd_config.d/hub.conf
sudo systemctl restart ssh
```

Keep your current SSH window open and check that a **new** `ssh hub` still gets in before you
close it.

Note: Docker publishes ports by editing iptables directly, bypassing ufw rules for published
ports. Only `web` publishes ports in `compose.yml`, on purpose.

## 3. Give the Pi a fixed address

In your router's admin page, find the Pi in the list of connected devices and add a **DHCP
reservation** (sometimes called a static lease or fixed IP) for it. Write down that IP: the
next steps call it `<Pi IP>`. Reboot the Pi (`sudo reboot`) so it picks it up.

## 4. Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
exit                               # log out and back in so the group applies
```

Back in with `ssh hub`, check it works: `docker run --rm hello-world`.

## 5. Run the hub

```bash
git clone https://github.com/NilsB44/blueberry-home.git ~/hub && cd ~/hub
cp .env.example .env
docker compose up -d --build
```

The first build takes a while on the Pi (around 10 to 15 minutes: it compiles the poker engine
and the web app). `docker compose ps` should then show `web` and `api` as running, and
`docker compose logs -f` shows what they're doing (Ctrl+C to stop watching).

The defaults in `.env` are right for the Pi. If you have an SSD, point shared files at it
(`HUB_FILES_PATH=/mnt/ssd/files`) and run `docker compose up -d` again.

## 6. Make `hub.home` resolve

Pick one:
- In your router's admin page, add a local DNS entry `hub.home → <Pi IP>` (not every router
  can; look under LAN, DHCP or DNS settings).
- Or run Pi-hole on the Pi and add a local DNS record there: see [pi-hole.md](pi-hole.md).
- For now, add `<Pi IP> hub.home` to the hosts file on each device that has one: `/etc/hosts`
  on macOS and Linux, `C:\Windows\System32\drivers\etc\hosts` on Windows (open Notepad as
  administrator). Phones have no hosts file, so they need one of the first two options.

## 7. Trust the local certificate

Caddy creates its own certificate authority. Copy its root certificate off the Pi:

```bash
docker compose cp web:/data/caddy/pki/authorities/local/root.crt ./hub-root.crt
```

Then **laptop:** `scp hub:hub/hub-root.crt .`

Install `hub-root.crt` as a trusted root on each device (macOS Keychain → "Always trust";
Windows: double-click → Install Certificate → Local Machine → "Trusted Root Certification
Authorities"; iOS: AirDrop it, install the profile, then enable it under Settings → General →
About → Certificate Trust Settings; Android: Settings → Security → Install certificate → CA).

## 8. Open the hub, from your phone first

Open `https://hub.home`. **The first device that opens the hub becomes its owner**, the only
one that sees the Security page, so make that your own phone. Add it to the home screen
(Share → Add to Home Screen) to use it like an app. Moving ownership later is possible from
the Pi: see [security.md](security.md).

## 9. Weekly security check and the device scan

```bash
cd ~/hub
sudo scripts/install-security-check.sh    # Security page: checks the Pi every Sunday
sudo scripts/install-network-scan.sh      # Network page: lists devices on the Wi-Fi
```

Never forward ports on the router. To reach the hub while you're out, set up Tailscale and
use the away access switch on the Security page: see [security.md](security.md).

## 10. Working on the Pi with Claude

Code changes don't happen on the Pi. Claude makes them as pull requests on GitHub, and once
they're merged the Pi picks them up:

```bash
~/hub/scripts/update-hub.sh      # pull the latest main and rebuild
```

To have Claude look at the Pi itself (logs, a container that won't start, a new script),
install Claude Code there and use it over your SSH session:

```bash
curl -fsSL https://claude.ai/install.sh | bash
cd ~/hub && claude
```

The first run prints a sign-in link: open it on your laptop or phone and log in with your
Claude account. From then on, `ssh hub` then `cd ~/hub && claude` gets you a Claude session
on the Pi. To drive that session from the Claude app instead of a terminal, type
`/remote-control` in it: it connects out to Claude, so no port is opened.

Two habits keep this safe:
- Don't use `--dangerously-skip-permissions` on the Pi. Your user is in the `docker` group,
  which is as powerful as root, so read what Claude asks to run.
- Don't give the Pi a GitHub login that can push. Let changes go through pull requests, and
  the Pi only ever pulls from the public repo.

## When something's off

- **`ssh: Could not resolve hostname hub.local`:** use the IP from the router instead, or give
  it a minute after boot.
- **`Permission denied (publickey)`:** the key in the Imager doesn't match the one on this
  laptop. Re-flash with the right `.pub` line, or log in from the laptop that made it.
- **`permission denied ... docker.sock`:** you didn't log out and back in after step 4.
- **Browser says the connection isn't private:** the certificate from step 7 isn't installed
  and trusted on that device yet.
- **`hub.home` doesn't load at all:** check the name points at the Pi (`ping hub.home`) and that
  `docker compose ps` shows both containers running.
- **Network page says the Pi is throttled or under-voltage:** use the official 27 W supply.
