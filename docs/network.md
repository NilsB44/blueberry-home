# Network page

The Network tile shows four things:

- **Internet:** the hub opens a connection to 1.1.1.1, 8.8.8.8 or 9.9.9.9 once a minute. Two
  failed minutes in a row count as an outage. You get the response time, uptime over the last
  24 hours and 7 days, a bar per hour for the last two days, and a list of outages. Checks are
  added up per hour in memory and written every 15 minutes, so the Pi's disk barely notices.
- **Speed:** every 6 hours the Pi downloads 25 MB and uploads 8 MB from Cloudflare's speed test
  server (`speed.cloudflare.com`). Admins can also run one by hand. Change the interval with
  `HUB_NETWORK_SPEEDTEST_HOURS` in `.env` (0 = only by hand).
- **The Pi:** CPU temperature, how busy it is, memory, disk space, uptime, and whether the
  firmware saw under-voltage or throttling (a weak power supply is the classic Pi problem).
  Read from `/proc` and `/sys`, which the container shares with the Pi.
- **On the Wi-Fi:** every device the Pi can see on the home network, by MAC address. Everyone
  sees how many are online; only admins see the list, name devices, or forget them.

## New-device alerts

The first scan is the starting point: everything on the Wi-Fi then is assumed to be yours.
After that, a device the Pi hasn't seen before shows as **New** on the Network page and as a
banner on the dashboard (admins only) until you press **I know this one**. If you don't
recognise one, change the Wi-Fi password on the router: that's the only thing that keeps a
device off your network, since the hub can't block it.

Phones and laptops use a *private* MAC address per Wi-Fi network (iOS, Android, Windows and
macOS all do by default). It stays the same on your network, but a phone that's reset or told
to "forget this network" comes back as a new device.

Refused visits to the hub itself are counted on the Security page; the Network page only links
there.

## Setting up the device scan on the Pi

The hub runs in a container, which can't see the other devices on your network. A small script
on the Pi does that every 5 minutes: it pings each address on the Pi's network once, reads the
Pi's neighbour (ARP) table, asks the router's DNS for names, and writes
`data/api/network-scan.json`. It runs as your normal user, not root, and only needs `ip` and
`ping`, which Raspberry Pi OS has.

```bash
cd ~/blueberry-home
sudo scripts/install-network-scan.sh
```

To check it ran: `systemctl status hub-network-scan.service`. To remove it:

```bash
sudo systemctl disable --now hub-network-scan.timer
sudo rm /etc/systemd/system/hub-network-scan.{service,timer}
```

Devices that never answer pings and stay silent (some smart plugs) may only show up when they
next talk on the network.
