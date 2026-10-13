# Try it now, before the Pi arrives

Your laptop can play the Pi's role: it runs the exact same containers, and your phone
connects to it over Wi-Fi. When the Pi arrives, you run the same commands there.

## 1. Install Docker

- **macOS / Windows:** install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  and start it.
- **Linux:** `curl -fsSL https://get.docker.com | sh`

## 2. Start the hub

```bash
git clone https://github.com/NilsB44/blueberry-home.git
cd blueberry-home
cp .env.example .env
```

Edit `.env` and switch to plain HTTP (no certificates to install while testing):

```
HUB_HOSTNAME=:80
HUB_COOKIE_SECURE=false
```

Then:

```bash
docker compose up -d --build
```

The first build takes a few minutes. Open <http://localhost> and create your account.

## 3. Open it on your phone

1. Make sure the phone is on the same Wi-Fi as the laptop.
2. Find the laptop's local IP address:
   - macOS: `ipconfig getifaddr en0`
   - Windows: `ipconfig` → "IPv4 Address" under your Wi-Fi adapter
   - Linux: `hostname -I`
3. On the phone, open `http://<that address>`, e.g. `http://192.168.1.23`.
4. If nothing loads, allow incoming connections for Docker in the laptop's firewall
   (macOS asks the first time; on Windows allow "Docker Desktop Backend" on private networks).
5. In the phone browser's menu, choose **Add to Home Screen** to get an app icon.

Audio in the French lessons uses the phone's built-in French voice, so turn the ringer on.
On iPhone you can pick a nicer voice under Settings → Accessibility → Spoken Content → Voices
→ French.

## 4. Updating and stopping

```bash
git pull && docker compose up -d --build   # get the latest version
docker compose down                        # stop (your data stays in ./data)
```

## Without Docker

For working on the code itself, run the API and web dev servers directly; see the
README's "Develop on your laptop" section. The web dev server listens on all interfaces, so the phone can open
`http://<laptop IP>:5173`.

## Plain HTTP is for testing only

On the Pi, keep the default `HUB_HOSTNAME=hub.home` so traffic on your Wi-Fi is encrypted
and login cookies are marked secure.
