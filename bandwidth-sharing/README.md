# Bandwidth sharing

Optional. Shares some of the home connection for small payouts, next to the hub on the same Pi
and separate from it:

- **EarnApp** runs natively as a systemd service, installed by its official script.
- **Pawns.app** runs in Docker (`compose.yml`, project `bandwidth`), pinned to one version.

No Honeygain (no native arm64 image) and no Watchtower (it needs the Docker socket; updates
here are by hand). Both apps are capped at half a CPU core and 256 MB of RAM so the hub always
comes first, and container logs rotate at 3 × 10 MB.

Both only make outbound connections and publish no ports. Your ISP and the sites traffic goes
to see your home IP, so read each service's terms before you start.

## Set up

Do this after the hub runs ([docs/pi-setup.md](../docs/pi-setup.md), steps 0 to 5).

```bash
~/hub/bandwidth-sharing/setup.sh      # first run creates .env and stops
nano ~/hub/bandwidth-sharing/.env     # Pawns.app email, password, device name
~/hub/bandwidth-sharing/setup.sh      # installs EarnApp, starts Pawns
```

EarnApp's installer asks you to accept its terms. At the end the script prints an EarnApp
URL: open it while logged in to your EarnApp account to link the Pi. Re-running the script is
safe: it skips EarnApp once installed and only recreates the container if something changed.

## Check it

```bash
earnapp status                                              # EarnApp: enabled and running
docker compose -f ~/hub/bandwidth-sharing/compose.yml ps    # Pawns: running
docker compose -f ~/hub/bandwidth-sharing/compose.yml logs --tail 50
docker stats --no-stream                                    # CPU/RAM against the limits
systemctl status earnapp | grep -E 'Memory|CPU'              # EarnApp's CPU/RAM
curl -s https://ifconfig.me; echo                           # the Pi's public IP
```

Compare that public IP with the WAN address on your router's status page. If they differ, or
the WAN address is a private one (`10.`, `172.16`–`31.`, `192.168.` or `100.64`–`127.`), you're
behind carrier-grade NAT: sharing can still work but usually earns less.

## Update

EarnApp updates itself (`earnapp_upgrader`). For Pawns, check the newest version on
[Docker Hub](https://hub.docker.com/r/iproyal/pawns-cli/tags), change the tag in
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

Remove the device from both dashboards as well.
