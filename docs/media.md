# Movies on the Pi

A plan for keeping movies on the Pi and watching them on the laptop or a projector. It uses
one disk, an NVMe SSD that also holds the OS and the hub. It reuses what the hub already has
(the Files page and the optional Samba share) and adds one optional container, Jellyfin, for
the projector. The hub itself does not change.

## What to buy

One **1–2 TB NVMe SSD** on an M.2 board under the Pi. The Pi boots from it, and the hub and the
movies live on it too. 1 TB holds roughly 200 movies at 1080p (about 5 GB each) or 50 4K
remuxes. Rough prices, so check Prisjakt before buying:

| Part | Rough price | Notes |
|---|---|---|
| M.2 board: official **M.2 HAT+** | 150 kr | Fits only short SSDs (2230 or 2242), which cost more per TB. |
| M.2 board: **Pimoroni NVMe Base** (or similar) | 200 kr | Also fits normal 2280 SSDs, so a wider choice of cheap 1–2 TB drives. **Recommended.** |
| 1 TB NVMe SSD (2280) | 600–900 kr | Any mainstream drive. The Pi uses only PCIe 2/3 x1, so a fast one is wasted money. |
| 2 TB NVMe SSD (2280) | 1 100–1 500 kr | Only if you expect more than ~200 movies. |

- **Power.** Use the official 27 W supply. The SSD is powered by the Pi, and a weaker supply
  makes it drop out under load.
- **Speed is not the limit.** A 4K Blu-ray remux peaks around 100 Mbit/s. The SSD does many
  times that; Wi-Fi is the slower link. Put the Pi on Ethernet.
- **Cooling.** The Active Cooler sits on top and the SSD board underneath, so they don't clash.

If the disk ever fills up, a USB disk can be added later without changing anything below except
the path.

## Set up the disk

Follow [pi-setup.md](pi-setup.md) and flash Raspberry Pi OS straight onto the NVMe (Imager can
write to it through a USB M.2 adapter, or flash a microSD first and copy it over with the
built-in SD Card Copier). Then make a folder for the hub's files and point the hub at it:

```sh
sudo mkdir -p /srv/hub-files/shared/Movies
sudo chown -R 1000:1000 /srv/hub-files
```

```sh
# .env
HUB_FILES_PATH=/srv/hub-files
```

```sh
docker compose up -d
```

The Shared folder's `Movies` is now the movie library.

**One disk means a full disk stops everything,** including the hub's database. The Files page
already refuses uploads when the disk is nearly full, but Samba and rsync don't check. Keep at
least 50 GB free; the Network page shows how full the disk is.

## Getting movies onto it

All three already work with no new code:

- **Files page:** upload to Shared → Movies from the laptop or phone (up to 8 GB per file by
  default; raise `HUB_MAX_UPLOAD_MB` for bigger ones).
- **Samba:** the share in [files.md](files.md) shows Shared as a network drive, so you can drag
  whole folders in from Finder or Explorer. The easiest way for a large library.
- **rsync** from a laptop: `rsync -avP Movies/ pi@hub.home:/srv/hub-files/shared/Movies/`

Name them `Movies/Title (Year)/Title (Year).mkv` so Jellyfin finds the right poster and info.

## Watching

**On the laptop** nothing new is needed: open the Samba share and play the file in VLC. The
Files page can also play videos in the browser, though only formats the browser supports
(usually MP4 with H.264).

**On the projector** it depends on what the projector can run:

| Projector | How |
|---|---|
| Has Android TV / Google TV / Fire TV built in | Install the Jellyfin app on it. |
| HDMI only | Plug in a streaming stick (Chromecast with Google TV, Fire TV Stick, ~400–600 kr) and install the Jellyfin app on it. |
| HDMI only, no stick | Plug the laptop in with HDMI and play from Samba in VLC. No Jellyfin needed. |

### Jellyfin (only for the projector)

Jellyfin is a free media server with apps for TVs, sticks, phones and the browser. Add it to
`compose.yml` the same way as Samba (off by default, not covered by CI, so treat it as a
starting point):

```yaml
  jellyfin:
    image: jellyfin/jellyfin:10.10.7
    profiles: ["media"]
    restart: unless-stopped
    user: "1000:1000"
    network_mode: host          # so the projector or stick can find it on the Wi-Fi
    volumes:
      - ./data/jellyfin/config:/config
      - ./data/jellyfin/cache:/cache
      - ${HUB_FILES_PATH:-./data/files}/shared/Movies:/media/movies:ro
```

Then `docker compose --profile media up -d`, open `http://hub.home:8096`, create the admin
user and add `/media/movies` as a Movies library. The library is mounted read-only, so
Jellyfin can never delete or change your files. Once it runs, a dashboard tile that links to it
is a small follow-up.

**The one real limit: the Pi 5 can't convert video on the fly.** It has no hardware video
encoder, and its CPU manages at most one 1080p stream in software (4K not at all). So every
file has to play as it is ("direct play"). In practice:

- Use H.264 or H.265 (HEVC) video in MKV or MP4. Streaming sticks play both.
- Prefer AAC, AC3 or EAC3 audio. DTS and TrueHD make some devices ask for conversion.
- Use text subtitles (SRT) rather than image ones (PGS from Blu-rays), which have to be burned
  into the picture.
- In the Jellyfin app, set the quality to Maximum so it never asks the Pi to shrink a stream.
- If something stutters, Jellyfin's dashboard shows whether it is transcoding and why.

Jellyfin has its own logins, separate from the hub, and is reachable on the home network only.
Away from home it works over Tailscale like the rest of the hub; don't open a port for it on
the router.

## Backups

The movies are not backed up: they can be found again, and backing them up would need a second
disk. The nightly backup in [plan.md](plan.md) keeps covering the hub's database and the files
you'd miss. Keep anything that can't be replaced (photos, documents) outside `Shared/Movies` so
the backup can include it and skip the movies.

## Shopping list

1. A Pimoroni NVMe Base (or the official M.2 HAT+ with a 2230/2242 SSD).
2. A 1 TB NVMe SSD, or 2 TB if you expect more than ~200 movies.
3. The official 27 W power supply, if it didn't come with the Pi.
4. For the projector, only if it has no smart-TV system: a streaming stick.
