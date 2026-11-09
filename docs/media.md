# Movies on the Pi

A plan for keeping movies on a disk attached to the Pi and watching them on the TV, phone or
laptop. Nothing here is built yet. It reuses what the hub already has (the Files page and the
optional Samba share) and adds one container, Jellyfin. The hub itself does not change, apart
from an optional dashboard tile that links to Jellyfin.

## What to buy

The Pi already gets an NVMe SSD for the OS and the hub (see [plan.md](plan.md)). The movies go
on a second disk on a USB 3 port (the blue ones), so a full movie disk can never fill the disk
the hub runs on.

| Library size | Disk | Rough price | Notes |
|---|---|---|---|
| Under 400 GB | None: buy a 1 TB NVMe instead of 256–512 GB | +500 kr | Simplest, but movies and the hub share a disk. |
| **1–4 TB (recommended)** | 2.5" USB HDD (2–4 TB) or USB SSD (1–2 TB) | 900–1 500 kr | Powered by the Pi, one cable. An HDD is cheaper per TB and plenty fast for video. |
| Over 4 TB | 3.5" HDD in an enclosure with its own power supply | 2 500 kr and up | The only option that needs another plug. |

The prices are rough guesses, so check Prisjakt before buying. Things to get right:

- **Power.** Use the official 27 W supply. With it the Pi gives its USB ports up to 1.6 A in
  total, which runs one 2.5" HDD or USB SSD. A weaker supply caps USB at 0.6 A and the disk
  drops out when it spins up. Two bus-powered HDDs at once is asking for trouble; a 3.5" disk
  always needs its own supply.
- **Speed is not the limit.** A 4K Blu-ray remux peaks around 100 Mbit/s. An HDD does over
  1 000 Mbit/s and Wi-Fi is the slower link anyway. Put the TV on Ethernet if it can.
- **No RAID.** One disk is fine for movies (see Backups).

## Set up the disk

Once, after plugging it in (this wipes the disk):

```sh
lsblk                                   # find it, e.g. /dev/sda
sudo parted /dev/sda --script mklabel gpt mkpart media ext4 0% 100%
sudo mkfs.ext4 -L media /dev/sda1
sudo mkdir -p /mnt/media
echo 'LABEL=media /mnt/media ext4 defaults,noatime,nofail 0 2' | sudo tee -a /etc/fstab
sudo mount -a && sudo chown -R 1000:1000 /mnt/media
```

`nofail` means the Pi still boots, and the hub still runs, if the disk is unplugged.

Then move the hub's files onto it, so that anything uploaded on the Files page lands on the big
disk and the Shared folder's `Movies` becomes the movie library:

```sh
# .env
HUB_FILES_PATH=/mnt/media/files
```

```sh
mkdir -p /mnt/media/files/shared/Movies
docker compose up -d
```

## Getting movies onto it

All three already work with no new code:

- **Files page:** upload to Shared → Movies from the phone or laptop (up to 8 GB per file by
  default; raise `HUB_MAX_UPLOAD_MB` for bigger ones).
- **Samba:** the share in [files.md](files.md) shows Shared as a network drive, so you can drag
  whole folders in from Finder or Explorer. This is the easiest way for a large library.
- **scp/rsync** from a laptop: `rsync -avP Movies/ pi@hub.home:/mnt/media/files/shared/Movies/`

Name them `Movies/Title (Year)/Title (Year).mkv` so Jellyfin finds the right poster and info.

## Watching: Jellyfin

Jellyfin is a free media server with apps for Android TV, Google TV, Fire TV, LG, Samsung (via
sideloading), iOS, Android and the browser. Add it to `compose.yml` the same way as Samba (off by
default, not covered by CI, so treat it as a starting point):

```yaml
  jellyfin:
    image: jellyfin/jellyfin:10.10.7
    profiles: ["media"]
    restart: unless-stopped
    user: "1000:1000"
    network_mode: host          # so TVs can discover it on the Wi-Fi
    volumes:
      - ./data/jellyfin/config:/config
      - ./data/jellyfin/cache:/cache
      - ${HUB_FILES_PATH:-./data/files}/shared/Movies:/media/movies:ro
```

Then `docker compose --profile media up -d`, open `http://hub.home:8096`, create the admin
user and add `/media/movies` as a Movies library. The library is mounted read-only, so
Jellyfin can never delete or change your files.

**The one real limit: the Pi 5 can't convert video on the fly.** It has no hardware video
encoder, and its CPU manages at most one 1080p stream in software (4K not at all). So every
file has to play as it is ("direct play"). In practice:

- Use H.264 or H.265 (HEVC) video in MKV or MP4. Nearly all TVs and phones play both.
- Prefer AAC, AC3 or EAC3 audio. DTS and TrueHD make some TVs ask for conversion.
- Use text subtitles (SRT) rather than image ones (PGS from Blu-rays), which have to be burned
  into the picture.
- In each Jellyfin app, set the quality to Maximum so it never asks the Pi to shrink a stream.
- If something stutters, Jellyfin's dashboard shows whether it is transcoding and why.

Jellyfin has its own logins, separate from the hub. It is reachable on the home network only,
like the hub. Away from home, it works over Tailscale like the rest of the hub; don't open a
port for it on the router.

## Backups

The movie disk is not backed up: movies can be found again, and a second disk of the same size
doubles the cost. The nightly backup in [plan.md](plan.md) keeps covering the hub's database
and the files you'd miss. If the Shared folder ends up holding things that can't be replaced
(photos, documents), keep those outside `Shared/Movies` and include them in the backup.

## Shopping list

1. A 2–4 TB 2.5" USB 3 HDD (or a 1–2 TB USB SSD if you want it silent).
2. Nothing else, as long as the Pi uses the official 27 W supply.
