# Files

The Files module is the hub's own file sharing: open **Files** on any device, upload from the
phone (photos, videos, PDFs, anything), and pick them up on the laptop, or the other way round.

- **Shared** is visible to everyone with an account on the hub.
- **My files** is private to your account.
- Images, video and audio open in a viewer (video can be scrubbed); PDFs and text files open in
  a new tab; everything else downloads.
- Uploads go straight to disk, one file at a time, with a progress bar. A file that already
  exists is never overwritten: the new one becomes `photo (1).jpg`.
- On a laptop you can drag files onto the page.
- Delete is permanent. The nightly backup (see `pi-setup.md`) is the safety net.

## Where files live

On disk under `HUB_FILES_PATH` (default `./data/files` next to `compose.yml`):

```
files/
  shared/          the Shared tab
  home/1/          My files for user 1, home/2/ for user 2, ...
```

They're ordinary files and folders, so you can copy them with `scp`, back them up with `restic`,
or expose the same folders through other tools. On the Pi, put them on the SSD:

```
# .env
HUB_FILES_PATH=/mnt/ssd/files
```

## Safety

- Every path is resolved and checked to stay inside your space, so `../` tricks and symlinks
  pointing outside are refused.
- Files that could run code in the browser (HTML, SVG, ...) always download rather than open,
  and every file is served with `Content-Security-Policy: sandbox`.
- Uploads are capped at `HUB_MAX_UPLOAD_MB` (8 GB by default) and refused when the disk is
  nearly full.

## Optional: a network drive for laptops (Samba)

If you'd also like the shared folder to show up in Finder / Explorer as a network drive, run
Samba next to the hub and point it at the same folder. Add this to `compose.yml` (not enabled
by default and not covered by CI, so treat it as a starting point):

```yaml
  samba:
    image: ghcr.io/servercontainers/samba:latest
    profiles: ["samba"]
    restart: unless-stopped
    network_mode: host
    environment:
      ACCOUNT_nils: ${SAMBA_PASSWORD:?set SAMBA_PASSWORD in .env}
      UID_nils: "1000"
      SAMBA_VOLUME_CONFIG_shared: "[Shared]; path=/shares/shared; valid users = nils; guest ok = no; read only = no; browseable = yes"
    volumes:
      - ${HUB_FILES_PATH:-./data/files}/shared:/shares/shared
```

Then `docker compose --profile samba up -d` and connect to `smb://hub.home/Shared`
(macOS: Finder → Go → Connect to Server; Windows: `\\hub.home\Shared`).

For automatic phone photo backup, Syncthing is the better tool; it can sync into
`files/home/<your id>/` so the photos also appear under My files.
