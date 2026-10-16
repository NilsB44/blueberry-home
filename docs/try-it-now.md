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
cp .env.example .env          # Windows PowerShell: copy .env.example .env
```

> **Before the open pull requests are merged**, the newest features live on their branches.
> Each branch builds on the one before (French → poker → Mandarin → files), so checking out
> the last one gets you everything: `git checkout file-sharing`. Once they're merged into
> `main`, skip this step.

Edit `.env` (on Windows: `notepad .env`) and switch to plain HTTP (no certificates to
install while testing). Change the `HUB_HOSTNAME` line and add the cookie line:

```
HUB_HOSTNAME=:80
HUB_COOKIE_SECURE=false
```

Then:

```bash
docker compose up -d --build
```

The first build takes a few minutes. Open <http://localhost>: there's no account to create, your
laptop just gets a name you can change under your name in the top bar.

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

Audio in the lessons uses the phone's built-in voices, so turn the ringer on. On iPhone you
can pick nicer voices under Settings → Accessibility → Spoken Content → Voices → French and
→ Chinese.

## 4. Take a tour

Everything below works from the phone; the laptop is just the server.

- **Poker → Pre-flop chart:** tap any hand (AKs, 72o, ...) to see its equity against 1–9
  opponents. **Calculator:** pick your two cards, optionally a board and other players' hands,
  and get win/tie odds. **Home games:** start a game, add players and rebuys, enter final
  stacks, and press Settle to get who-pays-whom. Try it at the next poker night with everyone
  on their own phone.
- **French** and **Mandarin:** do the first lesson of each. In Mandarin you can type `ni3 hao3`
  or `nǐ hǎo` (or the characters), and you'll draw 你 and 好 with your finger. Finished
  lessons feed the Review queue, which comes back over the following days.
- **Files:** upload a photo from the phone under Shared, then open it on the laptop. My files
  is private to you.
- **People:** the first device to open the hub is the admin. Open it on another phone and it
  becomes a second person with its own progress and private files; both show up under **People**.
- **Assistant** needs the local model: `docker compose --profile llm up -d` then
  `docker compose exec ollama ollama pull qwen3:4b` (a few GB; slower on a laptop without a GPU).

## 5. Updating and stopping

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
and device cookies are marked secure.
