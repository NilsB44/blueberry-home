# Pi-hole on the hub's Pi

Pi-hole blocks ads and trackers for every device on the Wi-Fi by being the home network's DNS
server. It also gives `hub.home` a name without touching the router's hosts settings. It runs
next to the hub on the same Pi; the hub doesn't know or care that it's there.

Do this after the hub is running ([pi-setup.md](pi-setup.md), steps 1–6).

## How it fits

| Port | Who | Reachable from |
|------|-----|----------------|
| 80, 443 | Caddy (the hub) | LAN |
| 53 (TCP and UDP) | Pi-hole DNS | LAN |
| 8080 | Pi-hole admin page | LAN |

Pi-hole is installed **natively**, not in Docker:

- Docker-published ports skip ufw (see pi-setup.md). Native Pi-hole stays behind ufw, so port 53
  is only open to the LAN rule you add below.
- It keeps the hub's `compose.yml` and `scripts/update-hub.sh` about the hub only. Pi-hole
  updates itself with `pihole -up`.
- Its admin page moves to 8080 so it never fights Caddy for 80/443.

The weekly security check expects ports 53 and 8080 once `pihole-FTL` is installed, and still
warns about them on a Pi without Pi-hole.

## 1. Install

The Pi needs a fixed IP first (DHCP reservation in the router), which you already set up for
`hub.home`. Read the installer before running it:

```bash
curl -sSL https://install.pi-hole.net -o pihole-install.sh
less pihole-install.sh
sudo bash pihole-install.sh
```

Pick any upstream DNS (Quad9 or Cloudflare are fine). The installer finds 80/443 taken by Caddy
and carries on. Then move the admin page to 8080 and set its password:

```bash
sudo pihole-FTL --config webserver.port '8080'
sudo systemctl restart pihole-FTL
sudo pihole setpassword
```

Open the LAN to DNS and the admin page (use your own subnet):

```bash
sudo ufw allow from 192.168.1.0/24 to any port 53
sudo ufw allow from 192.168.1.0/24 to any port 8080 proto tcp
```

The admin page is now at `http://<Pi's IP>:8080/admin`.

## 2. Local names

In the admin page, **Settings → Local DNS Records**: add `hub.home → <Pi's IP>`. You can then
drop the router entry or hosts-file line from pi-setup.md step 5.

Then **Settings → DNS → Conditional forwarding**: turn it on with your subnet, the router's IP
and its domain (often `lan`). Without it, Pi-hole can't ask the router for device names, so the
Network page's device list ([network.md](network.md)) and Pi-hole's own query log show bare IPs.

## 3. Try it on one device first

Before switching the whole house, set DNS by hand to the Pi's IP on your own phone or laptop
for a few days (Wi-Fi settings → DNS → manual). If a site you need breaks, allow-list it in the
admin page.

## 4. Switch the router

In the router's DHCP/LAN settings, set the DNS server handed to devices to the Pi's IP.

- Don't add a second, public DNS server: devices use either one at random and skip the blocking.
- If the router also hands out an IPv6 DNS server, devices can use that and skip Pi-hole. Turn
  that off, or set it to the Pi's IPv6 address.
- If the router doesn't let you change DNS (some ISP boxes), turn on Pi-hole's DHCP server
  (**Settings → DHCP**) and turn the router's off. Only one DHCP server may be on.

Devices pick up the change when they reconnect or renew their lease.

## If the Pi is down

Every device in the house uses the Pi for DNS, so when it's off nothing can find any website.
To undo, set the router's DNS back to automatic. It's worth knowing where that setting is
before you need it.

## Upkeep

```bash
sudo pihole -up       # update Pi-hole
pihole status         # is it running and blocking?
```
