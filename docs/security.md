# Security: reaching the hub from outside, and the weekly check

## The short version

- **Never forward ports on the router.** Not 80, not 443, not 22. Nothing on the internet
  should be able to open a connection to the Pi.
- **Away access goes through Tailscale**, a VPN where the Pi makes an *outgoing* connection and
  only your own signed-in devices can reach it. In the hub it's a switch on the Security page,
  **off by default**. Turn it on before a trip for a set time (4 hours to 30 days); it
  switches itself off when that runs out.
- **Only the owner controls security.** The owner is the hub's first device (you). Other
  people, admins included, can't see the Security page or touch the switch.
- **A security check runs every Sunday night** on both the hub and the Pi, and shows on the
  Security page. The dashboard shows a banner when something needs a look.
- **The Pi still has outgoing internet**, which it needs for updates, Tailscale, and looking up
  known vulnerabilities. Outgoing is fine; incoming is what attackers use.

## Why not cut the internet entirely?

You could, and the hub would keep working on the Wi-Fi. But you'd lose security updates (the
biggest single protection a Linux box has), plant checks and alerts while away, and the
vulnerability lookup. "No incoming connections, outgoing allowed, VPN for you" is the usual
home-server answer: the attack surface from the internet is zero, and you keep the useful parts.

## How away access works

1. Tailscale runs on the Pi and on your phone/laptop. They find each other through Tailscale's
   servers and connect directly, encrypted (WireGuard). Each device gets a `100.x.y.z` address.
2. The hub refuses those addresses unless away access is on. Even then:
   - only devices that **already joined on the home Wi-Fi** get in (their remembered cookie);
   - nobody can join, set up, or log in with a password from outside;
   - only the owner can turn the switch on, only from home, and only for a set time;
     it can be turned **off** from anywhere.
3. Every away visit is counted and shows in the weekly check.

## The owner, and what else the Security page does

- **Owner:** the first device that opened the hub. Ownership can only be moved from the Pi
  itself, so a phone on the Wi-Fi can never take it over:

  ```bash
  docker compose exec api python -m app.owner              # list people
  docker compose exec api python -m app.owner <username>   # make them the owner
  ```

  Use this if you replace your phone or clear its browser data.
- **Signed-in devices:** every device with access, when it was last seen and from which
  address. Sign out any you don't recognise. (On the Wi-Fi it could join again as a new
  person, so if a stranger keeps coming back, change the Wi-Fi password.)
- **Security log:** every change kept for a year: away access on/off/expired, devices signed
  out, logins paused, owner changes, checks run by hand.
- **Login lockout:** after 5 wrong passwords in 15 minutes from one address or for one
  username, logins pause for 15 minutes and the log says so.
- **Browser locks:** Caddy sends a Content-Security-Policy that only allows the hub's own
  files (no outside scripts, trackers or frames), plus headers that turn off camera,
  microphone and location access and block other sites from framing the hub.

### Setting up Tailscale

On the Pi:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Open the link it prints and sign in. Then install the Tailscale app on your phone and sign in
with the same account. In the Tailscale admin page:

- **Disable key expiry** for the Pi, so it doesn't drop off the VPN after 180 days.
- Leave **Funnel off**. Funnel publishes a device to the whole internet; the weekly check fails
  if it's ever on.

`hub.home` only resolves at home, so give the hub its Tailscale name too. With MagicDNS on
(the default), the Pi is `hub.<your-tailnet>.ts.net` (shown in the admin page). Add it to
`HUB_HOSTNAME` in `.env` and restart:

```
HUB_HOSTNAME="hub.home, hub.tail1234.ts.net"
```

```bash
docker compose up -d
```

Caddy then serves both names with its local certificate, which your devices already trust from
setup. While away, open `https://hub.tail1234.ts.net`.

## SSH

- **For you:** SSH stays key-only (set up in [pi-setup.md](pi-setup.md), step 1). From outside,
  use Tailscale SSH instead of forwarding port 22: `sudo tailscale set --ssh` on the Pi, then
  `ssh you@hub` from any of your devices on the tailnet.
- **For Claude improving the code:** it doesn't need SSH. Changes arrive as pull requests on
  GitHub, and the Pi picks them up with `scripts/update-hub.sh`. If you want Claude to work
  on the Pi itself, Claude Code's Remote Control runs there over an outgoing connection, so no
  port has to be opened for that either.

## The weekly check

Three parts, all reporting to the Security page or your inbox:

| Part | Runs | Looks at |
|---|---|---|
| The hub | Sunday 04:00 (inside the API) | Who counts as home, away access, refused visitors, wrong passwords, new devices, secure cookies, known vulnerabilities in the API's Python packages (osv.dev) |
| The Pi | Sunday 03:00 (systemd timer) | Open ports, SSH settings, failed SSH logins, firewall, pending security updates and reboots, Tailscale Funnel, how old the container images are |
| GitHub | Monday 05:00 (Actions) | `pip-audit`, `npm audit` and `cargo audit` over everything the hub is built from. GitHub emails you if it fails |

"Run the check now" on the Security page re-runs the hub part immediately and re-reads the Pi's
latest report.

### Install the Pi part

Once, from the hub folder on the Pi:

```bash
sudo scripts/install-security-check.sh
```

It installs a timer that writes `data/api/host-security.json`, which the hub reads. To run it
by hand: `sudo systemctl start hub-security-check`.

## What to do when something shows red

| Check | Meaning | Fix |
|---|---|---|
| Refused visitors (red) | An internet address reached the Pi | Router: remove port forwards, turn off UPnP. Check Tailscale Funnel is off |
| Failed SSH logins (red) | SSH is reachable from the internet | Remove the port 22 forward on the router |
| SSH settings | Passwords are allowed | `PasswordAuthentication no` in `/etc/ssh/sshd_config.d/hub.conf`, `sudo systemctl restart ssh` |
| Known vulnerabilities | A package the hub uses has a published flaw | `scripts/update-hub.sh`; if it stays red, the fix isn't released yet |
| Container images | Images over a month old | `scripts/update-hub.sh` |
| Tailscale | Funnel is on | `sudo tailscale funnel reset` |

## Keeping it up to date

```bash
scripts/update-hub.sh
```

Pulls the latest code, rebuilds with fresh base images (picking up their security fixes) and
restarts. Raspberry Pi OS updates itself through unattended-upgrades.

## One deliberate detail

`compose.yml` publishes ports 80 and 443 on IPv4 only. On IPv6, Docker relays connections
through its own proxy, so the hub would see them as coming from the Docker network, which it
treats as home. Pinning to IPv4 closes that gap even if the router lets IPv6 traffic in.
