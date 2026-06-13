# Illinois Lottery FastPlay Jackpot Scraper

Pulls the **current progressive jackpot totals** for the Illinois Lottery
FastPlay games you care about, at the click of a button. Use the output to
check which games are +EV.

Games tracked (edit `games.json` to change): Cash Castle, Ultimate Diamond
Jackpot, Twenty 20s, Illinois Super Jackpot, Luxury Loot, Illinois Jackpot,
$10 Quick Spot, Big Number Knockout, Going Pro, Blackjack, Fiesta Fever,
Booming Bucks.

## Why a real browser?

`illinoislottery.com` is JavaScript-rendered and behind Akamai-style bot
protection — plain `requests`/`curl` get an HTTP 403. So this tool drives a real
Chromium browser via **Playwright**. For each game it reads the jackpot from the
page's own backend JSON when available (the exact number shown on screen) and
falls back to the rendered page text otherwise.

## Setup (one time)

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Run — the one-click web app

```bash
python app.py
```

Open <http://127.0.0.1:5000>, click **Scrape Jackpots**. The table fills with
each game's current progressive jackpot, and you can **Download JSON / CSV**.
A full scrape takes roughly 30–60 seconds (it opens each game page in turn).

Tick **Show browser** if you want to watch it work (useful for debugging or if
the site shows a prompt).

## Run — command line (for automation / cron)

```bash
python scraper.py            # headless
python scraper.py --headed   # watch the browser
```

Writes timestamped files plus `output/latest.json` and `output/latest.csv`:

```json
{
  "scraped_at": "2026-06-13T22:59:00+00:00",
  "games": [
    { "name": "Cash Castle", "slug": "cash-castle",
      "jackpot": "$786,049", "jackpot_value": 786049.0,
      "source": "network-json", "ok": true, "error": null,
      "scraped_at": "2026-06-13T22:59:00+00:00" }
  ]
}
```

`jackpot_value` is the plain number — feed that straight into your EV math.

## If a game fails or the site shows a wall

FastPlay jackpot pages are public, but if you ever hit a geolocation/login/cookie
prompt, run this once to establish a persisted session (in Illinois):

```bash
python setup_login.py
```

It opens a browser using the same profile the scraper reuses. Clear any prompts,
close it, then scrape again.

## Tuning

- **Add/remove games or fix a slug:** edit `games.json`. Each game's page is
  `https://www.illinoislottery.com/games/fpg/<slug>`.
- **Page needs longer to render:** increase the settle time,
  e.g. `python scraper.py --settle-ms 4000`.
- The extraction logic (JSON keys + dollar-amount regexes) lives in
  `scraper.py`; the captured page data is the source of truth for the value.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask web app with the Scrape button |
| `scraper.py` | Playwright scraping + extraction, also a CLI |
| `setup_login.py` | Optional one-time login/geo session setup |
| `games.json` | The list of games and their URL slugs |
| `templates/index.html` | The button + results table UI |
