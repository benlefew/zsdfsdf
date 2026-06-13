# Illinois Lottery FastPlay — +EV Tracker

Scrapes the **current progressive jackpot** for the Illinois Lottery FastPlay
games you care about, compares each to its **break-even jackpot**, and tells you
when one is **+EV enough to buy** — all from one double-click.

## The easy way: `RUN_ME.py` (one file)

1. Make sure **Python** is installed once (Windows: [python.org/downloads](https://www.python.org/downloads/),
   tick **"Add Python to PATH"**; Mac usually already has it).
2. Double-click **`RUN_ME.py`**.

It installs the browser tool on first run, reads every game's jackpot, scores the
EV, and opens a results page in your browser. BUY signals are highlighted, listed
in a green banner, printed in the console, and beep. A `jackpots.csv` is written
next to the file for your spreadsheet.

> The first lines printed show the build version, e.g.
> `build-7 (+EV engine, all 12 games loaded)`. If you don't see a recent build,
> you're running an old downloaded copy — delete it and re-download.

## How the EV math works

For each game we know the ticket **price**, the **jackpot odds** (1 in N), and the
full table of **non-jackpot prize tiers** `(prize, odds)` taken from that game's
official Fast Play rules PDF. Then:

```
fixed_EV          = Σ (prize ÷ odds)         over the non-jackpot tiers
break-even jackpot = (price − fixed_EV) × jackpot_odds      # pre-tax EV == $0
buy threshold      = break-even × (1/(1−TAX_RATE)) × (1+SAFETY_CUSHION)
EV at jackpot J    = fixed_EV + J ÷ jackpot_odds − price    # pre-tax
```

A game flags **BUY** when its live scraped jackpot ≥ its buy threshold,
**+EV** when it's above (pre-tax) break-even but below your threshold,
otherwise **wait**.

**Two independent buffers** (stacked multiplicatively):

- **`TAX_RATE` (default 0.42):** tax takes its cut off the *whole* jackpot, so we
  **gross up** by `1/(1−tax)` — *not* the same as adding the tax rate. 0.42 ≈
  37% federal top bracket + 4.95% Illinois → a 1.72× factor.
- **`SAFETY_CUSHION` (default 0.20):** an extra 20% buffer for variance /
  jackpot-split risk, on top of the tax gross-up.

Combined factor = `1.72 × 1.20 = 2.07×` above the pre-tax break-even.

### Break-even reference (current odds tables)

`Break-even` is pre-tax (EV = $0). `Buy @ 2.07×` covers ~42% tax + 20% safety.

| Game | Price | Jackpot odds | Break-even | Buy @ 2.07× |
|---|---|---|---|---|
| Booming Bucks | $2 | 1 in 120,000 | $98,250 | $203,276 |
| Fiesta Fever | $5 | 1 in 60,000 | $113,006 | $233,806 |
| Blackjack | $5 | 1 in 60,000 | $115,018 | $237,969 |
| Going Pro | $5 | 1 in 60,000 | $116,777 | $241,607 |
| Big Number Knockout | $5 | 1 in 80,000 | $150,035 | $310,416 |
| $10 Quick Spot | $10 | 1 in 60,000 | $177,065 | $366,342 |
| Illinois Jackpot | $10 | 1 in 60,000 | $196,271 | $406,078 |
| Luxury Loot | $10 | 1 in 80,000 | $312,149 | $645,826 |
| Twenty 20s | $20 | 1 in 80,000 | $563,408 | $1,165,673 |
| Illinois Super Jackpot | $20 | 1 in 120,000 | $819,977 | $1,696,504 |
| Cash Castle | $30 | 1 in 240,000 | $2,037,379 | $4,215,267 |
| Ultimate Diamond Jackpot | $30 | 1 in 240,000 | $2,383,721 | $4,931,837 |

### Caveats (read before betting real money)

- **Taxes** are approximated by the 72% buy margin (≈42% jackpot tax), applied
  only to the jackpot. Tax on the small prizes you collect along the way is *not*
  modeled, so the true after-tax break-even is a touch higher still.
- **Jackpot splitting** is ignored — EV assumes the winner takes 100% (true for
  these games' rules, but two tickets hitting near-simultaneously is a tail risk).
- Odds are taken from the rules PDFs as written; if the lottery revises a game,
  update its numbers in `GAME_DATA` inside `RUN_ME.py`.

### Tuning

- **Change the buffers:** edit `TAX_RATE` and `SAFETY_CUSHION` near the top of
  `RUN_ME.py`. The buy threshold is `break-even × (1/(1−TAX_RATE)) × (1+SAFETY_CUSHION)`.
- **Fix odds / add a game:** edit the `GAME_DATA` dict (and the `GAMES` list for
  scraping) in `RUN_ME.py`.

## The advanced way: web app

`app.py` + `scraper.py` provide the same scrape behind a local web button with
JSON/CSV download. See `requirements.txt`; run `python app.py` and open
<http://127.0.0.1:5000>. (The EV scoring lives in `RUN_ME.py`; the web app
currently shows raw jackpots.)

## Why a real browser?

`illinoislottery.com` is JavaScript-rendered and behind Akamai-style bot
protection — plain HTTP requests get a 403. Both tools drive a real Chromium
browser via Playwright and read the jackpot from the rendered page.
