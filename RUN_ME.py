r"""
=============================================================================
 ILLINOIS LOTTERY FASTPLAY JACKPOTS  ---  just double-click this file.
=============================================================================

What it does, with ZERO setup from you:
  1. Installs what it needs the first time (one-time, ~1-2 min).
  2. Opens a browser behind the scenes and reads the current progressive
     jackpot for every game listed below.
  3. Pops open a results page in your browser with all the numbers + a
     "Copy as CSV" button you can paste into a spreadsheet for your EV math.

The ONLY thing you need installed first is Python:
  - Windows: get it from https://www.python.org/downloads/  (during install,
    TICK the box "Add Python to PATH"). Then double-click this file.
  - Mac: it usually comes with Python; just double-click, or run it from
    Terminal with:  python3 RUN_ME.py
=============================================================================
"""

import importlib
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

# ---- The games to check. Add/remove lines here if you ever want to. ---------
# Each is (Display name, URL slug at illinoislottery.com/games/fpg/<slug>)
GAMES = [
    ("Cash Castle",             "cash-castle"),
    ("Ultimate Diamond Jackpot","ultimate-diamond-jackpot"),
    ("Twenty 20s",              "twenty-20s"),
    ("Illinois Super Jackpot",  "illinois-super-jackpot"),
    ("Luxury Loot",             "luxury-loot"),
    ("Illinois Jackpot",        "illinois-jackpot"),
    ("$10 Quick Spot",          "quick-spot-10"),
    ("Big Number Knockout",     "big-number-knockout"),
    ("Going Pro",               "going-pro"),
    ("Blackjack",               "blackjack"),
    ("Fiesta Fever",            "fiesta-fever"),
    ("Booming Bucks",           "booming-bucks"),
]
BASE = "https://www.illinoislottery.com/games/fpg/{slug}"
HERE = Path(__file__).resolve().parent

# ============================================================================
#  EV ENGINE
#  For each game we know the ticket price, the jackpot's odds (1 in N), and the
#  full table of NON-jackpot prize tiers as (prize, odds 1-in) from the rules PDF.
#
#    fixed_EV          = sum(prize / odds) over the non-jackpot tiers
#    break-even jackpot = (price - fixed_EV) * jackpot_odds   # EV == $0 here
#    notify threshold   = break-even * (1 + NOTIFY_MARGIN)    # your cushion
#    EV at jackpot J    = fixed_EV + J/jackpot_odds - price
#
#  A game flags BUY when the live scraped jackpot >= its notify threshold.
#  (EV ignores taxes and the small chance of splitting a jackpot — see README.)
# ============================================================================
NOTIFY_MARGIN = 0.40  # 40% above break-even before we shout "BUY"

GAME_DATA = {
    # ---- filled from the rules PDFs (batch 1 of 3) -------------------------
    "booming-bucks": {
        "price": 2.00, "jackpot_odds": 120000.0,
        "fixed_prizes": [
            (2, 12), (3, 16), (4, 20), (5, 40), (6, 60), (8, 120), (10, 160),
            (12, 320), (15, 400), (20, 480), (25, 585.37), (30, 960), (40, 2400),
            (50, 3000), (60, 6000), (75, 8000), (80, 12000), (100, 16000),
            (150, 24000), (500, 48000),
        ],
    },
    "fiesta-fever": {
        "price": 5.00, "jackpot_odds": 60000.0,
        "fixed_prizes": [
            (5, 6.25), (10, 19.20), (15, 22.86), (20, 54.24), (30, 100),
            (50, 203.39), (100, 500), (500, 20000),
        ],
    },
    "blackjack": {
        "price": 5.00, "jackpot_odds": 60000.0,
        "fixed_prizes": [
            (5, 6.86), (10, 16), (15, 32), (25, 48), (50, 120), (100, 309.68),
        ],
    },
    "going-pro": {
        "price": 5.00, "jackpot_odds": 60000.0,
        "fixed_prizes": [
            (5, 7.50), (10, 12.97), (15, 15), (50, 150), (100, 480),
            (200, 4800), (500, 24000), (570, 48000),
        ],
    },
    "big-number-knockout": {
        "price": 5.00, "jackpot_odds": 80000.0,
        "fixed_prizes": [
            (5, 6.91), (10, 17.78), (15, 24), (20, 40), (25, 117.07), (30, 228.57),
            (40, 448.60), (50, 393.44), (60, 2000), (80, 3000), (100, 2400),
            (200, 16000), (500, 20000), (1000, 60000),
        ],
    },
    # ---- filled from the rules PDFs (batch 2 of 3) -------------------------
    "quick-spot-10": {
        "price": 10.00, "jackpot_odds": 60000.0,
        "fixed_prizes": [
            (10, 6), (50, 23), (100, 75), (250, 240), (500, 600),
        ],
    },
    "illinois-jackpot": {
        "price": 10.00, "jackpot_odds": 60000.0,
        "fixed_prizes": [
            (10, 6.86), (15, 10.91), (20, 13.33), (50, 40), (100, 240),
            (500, 1500), (1000, 8000), (2500, 20000), (5000, 34285.71),
        ],
    },
    "luxury-loot": {
        "price": 10.00, "jackpot_odds": 80000.0,
        "fixed_prizes": [
            (10, 7.27), (20, 13.33), (50, 26.67), (75, 82.76), (100, 296.30),
            (150, 4285.71), (200, 10909.09), (250, 15000), (300, 34285.71),
            (500, 60000), (1000, 60000),
        ],
    },
    "illinois-super-jackpot": {
        "price": 20.00, "jackpot_odds": 120000.0,
        "fixed_prizes": [
            (20, 7.62), (30, 10.91), (40, 13.33), (100, 40), (200, 240),
            (1000, 1500), (2000, 8000), (5000, 20000), (10000, 34285.71),
        ],
    },
    "twenty-20s": {
        "price": 20.00, "jackpot_odds": 80000.0,
        "fixed_prizes": [
            (20, 6.86), (30, 12), (50, 19.67), (100, 48), (500, 240),
            (1000, 2400), (10000, 24000),
        ],
    },
    # ---- filled from the rules PDFs (batch 3 of 3) -------------------------
    "cash-castle": {
        "price": 30.00, "jackpot_odds": 240000.0,
        "fixed_prizes": [
            (40, 8.17), (50, 13.71), (60, 18.46), (70, 50), (100, 96), (150, 96),
            (200, 120), (300, 240), (350, 480), (375, 685.71), (400, 1714.29),
            (500, 685.71), (600, 6000), (1000, 8000), (1200, 12000), (1600, 24000),
            (10000, 60000),
        ],
    },
    "ultimate-diamond-jackpot": {
        "price": 30.00, "jackpot_odds": 240000.0,
        "fixed_prizes": [
            (30, 8.21), (40, 11.43), (50, 10.43), (100, 18.18), (150, 116.79),
            (250, 400), (500, 963.86), (1000, 9230.77), (10000, 120000),
        ],
    },
}


def fixed_ev(g):
    return sum(prize / odds for prize, odds in g["fixed_prizes"])


def breakeven_jackpot(g):
    return (g["price"] - fixed_ev(g)) * g["jackpot_odds"]


def ev_at_jackpot(g, jackpot):
    return fixed_ev(g) + jackpot / g["jackpot_odds"] - g["price"]


def evaluate(slug, jackpot_value):
    """Return EV facts for a game, or None if we don't have its odds yet."""
    g = GAME_DATA.get(slug)
    if not g:
        return None
    be = breakeven_jackpot(g)
    thr = be * (1 + NOTIFY_MARGIN)
    out = {"breakeven": be, "threshold": thr, "price": g["price"]}
    if jackpot_value is None:
        out["status"] = "no-jackpot"
        return out
    out["ev"] = ev_at_jackpot(g, jackpot_value)
    out["edge_pct"] = 100.0 * out["ev"] / g["price"]
    if jackpot_value >= thr:
        out["status"] = "BUY"
    elif jackpot_value >= be:
        out["status"] = "POSITIVE"   # +EV but below your 40% cushion
    else:
        out["status"] = "WAIT"
    return out



# ---- Step 1: make sure the tools are installed (only does work first run) ----
def ensure_setup():
    def pip(*args):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *args])

    try:
        importlib.import_module("playwright")
    except ImportError:
        print("First-time setup: installing the browser tool (one time only)...")
        pip("playwright")

    # Make sure the actual Chromium browser binary is present.
    from playwright._impl._driver import compute_driver_executable  # noqa
    print("Making sure the browser is ready...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                   check=False)


# ---- Step 2: the scraping ---------------------------------------------------
import re  # noqa: E402  (after setup so it's clearly grouped)

JACKPOT_LABEL = re.compile(
    r"(?:progressive\s+(?:jackpot|top\s+prize)|estimated\s+jackpot|current\s+jackpot|jackpot)"
    r"[^$]{0,40}?\$\s*([\d,]+(?:\.\d{2})?)", re.IGNORECASE)
ANY_BIG_DOLLAR = re.compile(r"\$\s*([\d,]{4,}(?:\.\d{2})?)")
JACKPOT_KEY = re.compile(r"jackpot|progressive|top.?prize", re.IGNORECASE)


def num(raw):
    try:
        return float(str(raw).replace(",", "").replace("$", "").strip())
    except (ValueError, AttributeError):
        return None


def fmt(v):
    return f"${int(v):,}" if v == int(v) else f"${v:,.2f}"


def json_jackpot(obj):
    best = [None]

    def consider(v):
        if v >= 100 and (best[0] is None or v > best[0]):
            best[0] = v

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if JACKPOT_KEY.search(str(k)):
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        consider(float(v))
                    elif isinstance(v, str):
                        m = re.search(r"[\d,]+(?:\.\d+)?", v)
                        if m and num(m.group(0)) is not None:
                            consider(num(m.group(0)))
                walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(obj)
    return best[0]


def text_jackpot(text):
    m = JACKPOT_LABEL.search(text)
    if m:
        return num(m.group(1))
    cands = [num(x) for x in ANY_BIG_DOLLAR.findall(text)]
    cands = [c for c in cands if c is not None]
    return max(cands) if cands else None


def scrape():
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    profile = HERE / ".browser_profile"
    profile.mkdir(exist_ok=True)
    results = []
    print("\nOpening the lottery site and reading jackpots...\n")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=True,
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
            locale="en-US", timezone_id="America/Chicago",
            viewport={"width": 1366, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for i, (name, slug) in enumerate(GAMES, 1):
            url = BASE.format(slug=slug)
            value, source, err = None, "", None
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except PWTimeout:
                    pass
                page.wait_for_timeout(2500)  # let the jackpot render

                # 1) Authoritative: a jackpot figure embedded in the page's HTML
                #    (the SPA stashes its data as JSON inside the page source).
                value = html_jackpot(page.content())
                if value is not None:
                    source = "site data"
                # 2) Fallback: the dollar amount visible in the rendered text.
                if value is None:
                    value = text_jackpot(page.inner_text("body"))
                    if value is not None:
                        source = "page text"
            except Exception as e:  # noqa: BLE001
                err = str(e).splitlines()[0][:80]

            if value is not None:
                print(f"  [{i}/{len(GAMES)}] {name:<28} {fmt(value)}")
                results.append((name, slug, fmt(value), value, source, ""))
            else:
                print(f"  [{i}/{len(GAMES)}] {name:<28} (could not read){' - ' + err if err else ''}")
                results.append((name, slug, "", None, "", err or "not found"))
        ctx.close()
    return results


# Find a jackpot figure inside raw page HTML, e.g.  "jackpot":786049  or
# "progressiveJackpotAmount":"$786,049". Takes the largest such match.
HTML_JACKPOT = re.compile(
    r"(?:jackpot|progressive|top.?prize)[A-Za-z]*\"?\s*[:=]\s*\"?\$?\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE)


def html_jackpot(html):
    best = None
    for raw in HTML_JACKPOT.findall(html):
        v = num(raw)
        if v is not None and v >= 100 and (best is None or v > best):
            best = v
    return best


# ---- Step 3: score EV, write + open a results page, and alert ---------------
STATUS_STYLE = {
    "BUY":      ("#0b8a0b", "#e3f6e8", "🔔 BUY"),
    "POSITIVE": ("#b8860b", "#fdf4d6", "+EV"),
    "WAIT":     ("#888",    "#f2f2f5", "wait"),
    "no-jackpot": ("#c0392b", "#fdecea", "no jackpot read"),
    "no-data":  ("#888",    "#f2f2f5", "need odds PDF"),
}


def report(results):
    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = ""
    buys = []
    csv_lines = ["Game,Jackpot,JackpotValue,BreakEven,BuyThreshold(+40%),EV_per_ticket,Edge_%,Status,Source"]

    for name, slug, disp, val, source, err in results:
        ev = evaluate(slug, val)
        # Decide status + the numbers to show.
        if ev is None:
            status = "no-data"
            be_s = thr_s = ev_s = edge_s = "—"
        else:
            status = ev["status"] if disp else "no-jackpot"
            be_s = fmt(ev["breakeven"])
            thr_s = fmt(ev["threshold"])
            ev_s = (f'{"+" if ev.get("ev",0)>=0 else ""}${ev["ev"]:,.2f}') if "ev" in ev else "—"
            edge_s = (f'{ev["edge_pct"]:+.1f}%') if "edge_pct" in ev else "—"

        color, bg, label = STATUS_STYLE.get(status, STATUS_STYLE["WAIT"])
        amount = disp if disp else f'<span style="color:#c0392b">{err or "—"}</span>'
        if status == "BUY":
            buys.append((name, disp, thr_s, edge_s))
        rowbg = "background:#eafbe8;" if status == "BUY" else ""
        rows += (
            f'<tr style="{rowbg}"><td>{name}</td>'
            f'<td class=amt>{amount}</td>'
            f'<td class=amt>{be_s}</td>'
            f'<td class=amt>{thr_s}</td>'
            f'<td class=amt>{ev_s}</td>'
            f'<td class=amt>{edge_s}</td>'
            f'<td><span class=pill style="color:{color};background:{bg}">{label}</span></td></tr>'
        )
        csv_lines.append(
            f'"{name}","{disp}","{val if val is not None else ""}",'
            f'"{be_s}","{thr_s}","{ev_s}","{edge_s}","{status}","{source}"'
        )

    csv = "\\n".join(csv_lines).replace('"', '\\"')

    if buys:
        items = "".join(f"<li><b>{n}</b> — jackpot {d}, buy-threshold {t} (edge {e})</li>"
                        for n, d, t, e in buys)
        banner = (f'<div class="banner buy"><div class="big">🔔 {len(buys)} '
                  f'+EV BUY SIGNAL{"S" if len(buys)!=1 else ""}</div><ul>{items}</ul></div>')
    else:
        banner = ('<div class="banner none">No games are 40% above break-even right now — '
                  'nothing to buy.</div>')

    html = f"""<!doctype html><meta charset=utf-8>
<title>Illinois FastPlay Jackpots</title>
<style>
 body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#1b0738;color:#fff;margin:0;padding:24px}}
 h1{{font-size:1.4rem;margin:0 0 4px}} .sub{{opacity:.8;font-size:.85rem;margin-bottom:16px}}
 .banner{{max-width:900px;border-radius:12px;padding:14px 18px;margin-bottom:18px}}
 .banner.buy{{background:#0b8a0b;color:#fff}} .banner.none{{background:rgba(255,255,255,.1);color:#fff;opacity:.85}}
 .banner .big{{font-size:1.2rem;font-weight:800;margin-bottom:6px}} .banner ul{{margin:6px 0 0 18px}}
 table{{width:100%;max-width:900px;border-collapse:collapse;background:#fff;color:#1a1a2e;border-radius:12px;overflow:hidden}}
 th,td{{padding:10px 12px;border-bottom:1px solid #eee;text-align:left;font-size:.9rem}}
 th{{background:#f4f1fa;font-size:.68rem;text-transform:uppercase;color:#666}}
 td.amt{{text-align:right;font-variant-numeric:tabular-nums}}
 .pill{{font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap}}
 button{{margin-top:16px;padding:10px 18px;border:0;border-radius:8px;background:#16a0e0;color:#fff;font-weight:600;cursor:pointer}}
</style>
<h1>🎰 Illinois Lottery FastPlay — +EV Tracker</h1>
<div class=sub>Scraped {when}. Break-even = jackpot where EV is $0. Buy-threshold = {int(NOTIFY_MARGIN*100)}% above that. Re-run any time to refresh.</div>
{banner}
<table><thead><tr>
 <th>Game</th><th style=text-align:right>Jackpot</th><th style=text-align:right>Break-even</th>
 <th style=text-align:right>Buy @ (+{int(NOTIFY_MARGIN*100)}%)</th><th style=text-align:right>EV / ticket</th>
 <th style=text-align:right>Edge</th><th>Status</th>
</tr></thead><tbody>{rows}</tbody></table>
<button onclick="navigator.clipboard.writeText('{csv}');this.textContent='Copied!'">Copy as CSV</button>
"""
    out = HERE / "jackpots.html"
    out.write_text(html, encoding="utf-8")
    (HERE / "jackpots.csv").write_text("\n".join(csv_lines), encoding="utf-8")
    print(f"\nResults saved to {out}")

    # ---- the actual "notify me" part ----
    if buys:
        print("\n" + "!" * 60)
        print(f"  {len(buys)} +EV BUY SIGNAL(S):")
        for n, d, t, e in buys:
            print(f"   >> {n}: jackpot {d}  (buy at {t}, edge {e})")
        print("!" * 60)
        try:  # audible alert on Windows; silently skipped elsewhere
            import winsound
            for _ in range(len(buys)):
                winsound.Beep(880, 220)
        except Exception:
            print("\a", end="")  # terminal bell fallback
    else:
        print("\nNo +EV buy signals right now.")

    webbrowser.open(out.as_uri())


VERSION = "build-7 (+EV engine, all 12 games loaded)"


def main():
    print("=" * 60)
    print("  Illinois FastPlay Jackpots  —  " + VERSION)
    print("=" * 60)
    try:
        ensure_setup()
        results = scrape()
        report(results)
        ok = sum(1 for r in results if r[2])
        print(f"\nDone — {ok}/{len(results)} jackpots read. A results page just opened in your browser.")
    except Exception as e:  # noqa: BLE001
        import traceback
        print("\nSomething went wrong:")
        traceback.print_exc()
    finally:
        try:
            input("\nPress Enter to close this window...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
