# Bandwidth sharing

Optional. Shares some of the home connection for small payouts, next to the hub on the same Pi
and separate from it:

- **EarnApp** runs natively as a systemd service, installed by its official script.
- **Pawns.app** and **Honeygain** run in Docker (`compose.yml`, project `bandwidth`), each
  pinned to one version. Honeygain's official image has run natively on arm64 since 0.8.1.

No Watchtower (it needs the Docker socket; updates here are by hand). Each app is capped at half
a CPU core and 256 MB of RAM so the hub always comes first, and container logs rotate at
3 × 10 MB. The containers drop all Linux capabilities, and Honeygain's image runs as a non-root
user, so they're more boxed in than EarnApp, which runs natively as root.

All three only make outbound connections and publish no ports. Your ISP and the sites traffic goes
to see your home IP, so read each service's terms before you start.

## Set up

Do this after the hub runs ([docs/pi-setup.md](../docs/pi-setup.md), steps 0 to 5).

```bash
~/hub/bandwidth-sharing/setup.sh      # first run creates .env and stops
nano ~/hub/bandwidth-sharing/.env     # Pawns.app and Honeygain logins, device name
~/hub/bandwidth-sharing/setup.sh      # installs EarnApp, starts Pawns and Honeygain
```

EarnApp's installer asks you to accept its terms. At the end the script prints an EarnApp
URL: open it while logged in to your EarnApp account to link the Pi. Re-running the script is
safe: it skips EarnApp once installed and only recreates the container if something changed.

## Guest network?

Keeping strangers' traffic off your home network is a fair worry, but don't move the Pi to the
guest Wi-Fi. A guest network is walled off from the main one, so your phones and laptops could
no longer reach `hub.home` (or Pi-hole), and the Network page would only see guests. Since the
earn apps share the Pi with the hub, they can't be on a different network from it.

Your options, best first:

1. **Keep the Pi on the main network, on Ethernet** (what [pi-setup.md](../docs/pi-setup.md)
   does). All the apps only connect out and publish no ports, are capped in CPU and RAM, and
   Pawns and Honeygain run with no privileges. Keep your router's admin password strong, and other devices' too.
2. **Run the earn apps on another device on the guest Wi-Fi** for full separation: EarnApp,
   Pawns and Honeygain all have Android apps, so an old phone left on a charger works. Turn them
   off on the Pi first (see [Turn it off](#turn-it-off)): they pay per home IP, so a second device behind it
   earns little or nothing extra.
3. **A VLAN**, only if your router supports it: you'd still need a second device, so it's the
   same as option 2 with more setup.

To set up option 2: in the router's admin page (often `192.168.0.1` or `192.168.1.1`, or the
router's own app) turn on the guest network and give it its own password. Make sure guests
can't reach the main network: a setting like "allow guests to access the local network" should
be off, or one called "isolation" on.
Join the phone to it, install EarnApp and Pawns from the Play Store, and log in with the same
accounts. The hub's Earn apps page then shows nothing, as it only watches the Pi.

## Check it

The hub's **Earn apps** page shows whether each app runs, its traffic today and in total, and its
latest log lines. `setup.sh` installs a small timer (`hub-earn-status`) that writes this every
5 minutes into `data/api/earn-status.json`; the hub only reads that file and gets no access to
Docker. Earnings and requests are only on each app's own dashboard. From the command line:

```bash
earnapp status                                              # EarnApp: enabled and running
docker compose -f ~/hub/bandwidth-sharing/compose.yml ps    # Pawns, Honeygain: running
docker compose -f ~/hub/bandwidth-sharing/compose.yml logs --tail 50
docker stats --no-stream                                    # CPU/RAM against the limits
systemctl status earnapp | grep -E 'Memory|CPU'              # EarnApp's CPU/RAM
curl -s https://ifconfig.me; echo                           # the Pi's public IP
```

Compare that public IP with the WAN address on your router's status page. If they differ, or
the WAN address is a private one (`10.`, `172.16`–`31.`, `192.168.` or `100.64`–`127.`), you're
behind carrier-grade NAT: sharing can still work but usually earns less.

## When something's off

- **Pawns shows `Restarting (1)`:** the app quit, usually on a failed login. Run it in the
  foreground to see why (Ctrl+C to stop), then fix `.env` and run `setup.sh` again:

  ```bash
  docker compose -f ~/hub/bandwidth-sharing/compose.yml run --rm pawns
  ```

  `authenticate user failed` means Pawns refused the email and password. Stop the container
  while you sort it out (`docker compose -f ~/hub/bandwidth-sharing/compose.yml stop`) so it
  doesn't keep retrying, and check you can log in to the Pawns dashboard with exactly those.
  An account made with Google sign-in has no password: set one in the Pawns dashboard first.
  If the password has a `$` in it, wrap it in single quotes in `.env`. Also stop Pawns on any
  other computer at home: a second device on the same IP earns nothing extra.
- **Honeygain keeps restarting:** run it in the foreground the same way to see why:

  ```bash
  docker compose -f ~/hub/bandwidth-sharing/compose.yml run --rm honeygain
  ```

  Check you can log in at dashboard.honeygain.com with exactly the email and password in
  `.env` (same tips as for Pawns above). Uninstall Honeygain on other computers at home: it
  counts one device per IP.
- **`Your kernel does not support memory limit capabilities`:** the memory limits aren't
  applied. Do the `cmdline.txt` part of [pi-setup.md](../docs/pi-setup.md) step 4 and reboot.

## Update

EarnApp updates itself (`earnapp_upgrader`). For Pawns and Honeygain, check the newest version
on Docker Hub ([Pawns](https://hub.docker.com/r/iproyal/pawns-cli/tags),
[Honeygain](https://hub.docker.com/r/honeygain/honeygain/tags)), change the tag in
`compose.yml`, then:

```bash
~/hub/bandwidth-sharing/setup.sh
docker image prune -f
```

## Turn it off

```bash
docker compose -f ~/hub/bandwidth-sharing/compose.yml down --rmi all
sudo earnapp uninstall
sudo rm -rf /etc/systemd/system/earnapp.service.d && sudo systemctl daemon-reload
```

Remove the device from each app's dashboard as well.
