# Setting up the Pi, start to finish

Every step from an unopened box to the hub running on `https://hub.home`, in order. Expect
about an hour. Commands marked **laptop** run on your own computer (PowerShell on Windows,
Terminal on macOS), the rest run on the Pi over SSH.

## Hardware checklist

- Raspberry Pi 5, 8 GB
- Official 27 W USB-C power supply (a weaker supply throttles the Pi and can't power an SSD)
- Active Cooler (or a case with a fan)
- A good microSD card (A2 rated, 32 GB or more) that stays in the Pi, or an NVMe SSD on an M.2
  HAT
- Ethernet cable to the router (needed for step 1, and steadier than Wi-Fi for a server)
- For step 1, either a screen with a micro-HDMI cable and a USB keyboard, or a USB stick
  (8 GB or more) to start from: see the end of step 1.

## 0. Make SSH keys for the devices you'll log in from

The Pi will only accept logins from keys, never a password. Make one key on **each** device
you want to reach the Pi from, so you're not tied to one computer. **Laptop:**

```bash
ssh-keygen -t ed25519 -C "laptop"      # press Enter for the default path, set a passphrase
cat ~/.ssh/id_ed25519.pub              # Windows: type $HOME\.ssh\id_ed25519.pub
```

Skip the first line if you already have a key. **Phone:** an SSH app such as Termius can make
a key and show its public half. Each `.pub` line goes onto the Pi in step 2.

Claude doesn't need a key. Code changes are made as pull requests on GitHub (from the Claude
app, wherever you are), and the Pi pulls them with one command: see step 10.

## 1. Install the OS onto the microSD card

The Pi 5 can install its own OS over the internet (Network Install), so no card reader is
needed. It needs Ethernet: Wi-Fi doesn't work for this.

1. Put the microSD card in the slot on the underside of the Pi. Plug in Ethernet, the screen
   (the micro-HDMI port next to the power socket) and the keyboard, then the power.
2. With a new, empty card the Pi shows a boot screen. **Hold Shift** until it starts
   downloading. After a few minutes Raspberry Pi Imager opens on the screen.
3. Imager walks you through a few screens in order:
   - **Device:** Raspberry Pi 5.
   - **OS:** Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)**. No desktop: the hub
     doesn't need one.
   - **Storage:** the microSD card (check the size, e.g. 64 GB). Everything on it is erased.
   - **Customisation:**
     - Hostname: `pils` (the Pi's own name; the hub's web address stays `hub.home`).
     - Localisation: the capital of the country the Pi is in (it sets the Wi-Fi country), your
       time zone (change it later with `sudo timedatectl set-timezone Asia/Singapore`) and
       keyboard layout (it only matters with a keyboard plugged into the Pi).
     - User: a username (e.g. `nils`) and a password.
     - Wi-Fi: skip it, you're on Ethernet.
     - Remote access: enable SSH with **password authentication** for now. Typing a key by hand
       here is impractical; step 2 adds your keys and switches passwords off.
     - Raspberry Pi Connect: leave it off. SSH is all you need.
4. Write the card. When it's done the Pi restarts from the card; the first boot takes a couple
   of minutes. Then unplug the screen and keyboard: from here on it's all over SSH.

Booting from an NVMe SSD instead? Pick the SSD as the storage in Imager and leave the card out
afterwards. On an old bootloader run `sudo rpi-eeprom-update -a` once a system is up.

### No screen and no card reader: go through a USB stick

The Pi boots from the stick first, then copies that system onto the card. No extra hardware.

1. On your computer, install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and
   write the same OS to the **USB stick** with the same settings, except under Remote access
   choose **public-key authentication** and paste the laptop's `.pub` line.
2. Leave the empty microSD card in the Pi. Plug the stick into a **blue** USB 3 port, plug in
   Ethernet, then power. The Pi 5 tries the SD card first, finds nothing to boot and moves on
   to USB, so it starts from the stick.
3. Log in (`ssh nils@pils.local`, see step 2) and copy the running system onto the card with
   [rpi-clone](https://github.com/geerlingguy/rpi-clone):

   ```bash
   lsblk                                  # the card is mmcblk0 (~64 GB), the stick is sda
   curl -fsSL https://raw.githubusercontent.com/geerlingguy/rpi-clone/master/install -o rpi-clone-install
   sudo bash rpi-clone-install && rm rpi-clone-install
   sudo rpi-clone mmcblk0                 # answer yes; the label question can be left empty
   sudo poweroff
   ```

   It sets up the card's partitions, copies everything and points the card's boot settings at
   the card.
4. Unplug the power, take the stick out, power on. The Pi now boots from the card with the same
   settings and key. Carry on with step 2. The `ssh` warning that the host key changed won't
   appear: it's the same system.

## 2. First login and hardening

**Laptop:**

```bash
ssh nils@pils.local
```

Answer `yes` to the fingerprint question and type the password from step 1 (USB stick route:
no password, your key is already there). If `pils.local` isn't found, look up the Pi's IP in
your router's admin page (connected devices) and use `ssh nils@<ip>`.

Optional, so `ssh hub` is enough from now on. Add this to `~/.ssh/config` on the laptop
(Windows: `$HOME\.ssh\config`):

```
Host hub
    HostName pils.local
    User nils
```

**On the Pi:** update everything and turn on the firewall and automatic security updates.

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y ufw unattended-upgrades fail2ban python3-systemd git
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
sudo dpkg-reconfigure -plow unattended-upgrades     # answer Yes
sudo reboot                                         # load the new kernel; ssh back in after a minute
```

Raspberry Pi OS keeps logs in the systemd journal, not `/var/log/auth.log`, so tell fail2ban
to read SSH logins from there and to ban through ufw, then check it's watching (the pause gives
the server time to start; without it the check says "Failed to access socket path"):

```bash
printf '[sshd]\nenabled = true\nbackend = systemd\nbanaction = ufw\n' | sudo tee /etc/fail2ban/jail.d/hub.conf
sudo systemctl restart fail2ban; sleep 3; sudo fail2ban-client status sshd
```

It should list `Journal matches: _SYSTEMD_UNIT=ssh.service + _COMM=sshd` and 0 banned.

Add the `.pub` line of every device from step 0, one per line:

```bash
mkdir -p ~/.ssh && nano ~/.ssh/authorized_keys     # paste, then Ctrl+O, Enter, Ctrl+X
chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
```

From a **new** terminal on the laptop, check `ssh hub` gets in without asking for the Pi's
password (it may ask for your key's passphrase). Only then make sure SSH can never fall back
to passwords (the weekly check looks for this). The file name starts with `00-` so it wins over
a `50-cloud-init.conf` that Imager's password setting can leave behind:

```bash
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n' \
  | sudo tee /etc/ssh/sshd_config.d/00-hub.conf
sudo systemctl restart ssh
sudo sshd -T | grep -i -E '^(passwordauthentication|kbdinteractiveauthentication) '   # both "no"
```

Keep your current SSH window open and check that a **new** `ssh hub` still gets in before you
close it. Adding a device later: append its `.pub` line to `~/.ssh/authorized_keys` from one
that already works.

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

Optional: to share some bandwidth for small payouts (EarnApp and Pawns.app), see
[bandwidth-sharing/README.md](../bandwidth-sharing/README.md).

## 10. Working on the Pi with Claude

Code changes don't happen on the Pi. Ask Claude in the Claude app (from anywhere): it makes
them as pull requests on GitHub, and once they're merged the Pi picks them up with one command,
from the laptop or from the SSH app on your phone:

```bash
ssh hub ~/hub/scripts/update-hub.sh      # pull the latest main and rebuild
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

- **`ssh: Could not resolve hostname pils.local`:** use the IP from the router instead, or give
  it a minute after boot.
- **No "hold Shift" screen in step 1:** check the screen is on the micro-HDMI port next to the
  power socket and Ethernet is plugged in. A card that already has an OS on it boots that
  instead; let it, or wipe the card first.
- **`Permission denied (publickey)`:** this device's `.pub` line isn't in
  `~/.ssh/authorized_keys` on the Pi. Add it from a device that can log in.
- **The Pi doesn't boot (no `pils.local`, green light not blinking):** re-seat the microSD card,
  and re-flash it if needed. Make sure the card is pushed fully into the slot under the board.
- **`permission denied ... docker.sock`:** you didn't log out and back in after step 4.
- **Browser says the connection isn't private:** the certificate from step 7 isn't installed
  and trusted on that device yet.
- **`hub.home` doesn't load at all:** check the name points at the Pi (`ping hub.home`) and that
  `docker compose ps` shows both containers running.
- **Network page says the Pi is throttled or under-voltage:** use the official 27 W supply.
