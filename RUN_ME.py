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
            captured = []
            page.on("response", lambda r: _grab(r, captured))
            value, source, err = None, "", None
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except PWTimeout:
                    pass
                page.wait_for_timeout(2000)
                for blob in captured:
                    v = json_jackpot(blob)
                    if v is not None and (value is None or v > value):
                        value, source = v, "site data"
                if value is None:
                    value = text_jackpot(page.inner_text("body"))
                    if value is not None:
                        source = "page text"
            except Exception as e:  # noqa: BLE001
                err = str(e).splitlines()[0][:80]
            finally:
                page.remove_listener("response", lambda r: _grab(r, captured))

            if value is not None:
                print(f"  [{i}/{len(GAMES)}] {name:<28} {fmt(value)}")
                results.append((name, fmt(value), value, source, ""))
            else:
                print(f"  [{i}/{len(GAMES)}] {name:<28} (could not read){' - ' + err if err else ''}")
                results.append((name, "", "", "", err or "not found"))
        ctx.close()
    return results


def _grab(resp, bucket):
    try:
        if "json" in (resp.headers or {}).get("content-type", "").lower():
            bucket.append(resp.json())
    except Exception:
        pass


# ---- Step 3: write + open a nice results page -------------------------------
def report(results):
    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = ""
    csv_lines = ["Game,Jackpot,Value,Source"]
    for name, disp, val, source, err in results:
        amount = disp if disp else f'<span style="color:#c0392b">{err or "—"}</span>'
        rows += (f"<tr><td>{name}</td><td class=amt>{amount}</td>"
                 f"<td class=src>{source}</td></tr>")
        csv_lines.append(f'"{name}","{disp}","{val}","{source}"')
    csv = "\\n".join(csv_lines).replace('"', '\\"')

    html = f"""<!doctype html><meta charset=utf-8>
<title>Illinois FastPlay Jackpots</title>
<style>
 body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#1b0738;color:#fff;margin:0;padding:24px}}
 h1{{font-size:1.4rem;margin:0 0 4px}} .sub{{opacity:.8;font-size:.9rem;margin-bottom:18px}}
 table{{width:100%;max-width:680px;border-collapse:collapse;background:#fff;color:#1a1a2e;border-radius:12px;overflow:hidden}}
 th,td{{padding:11px 14px;border-bottom:1px solid #eee;text-align:left}}
 th{{background:#f4f1fa;font-size:.72rem;text-transform:uppercase;color:#666}}
 td.amt{{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}}
 td.src{{font-size:.75rem;color:#888}}
 button{{margin-top:16px;padding:10px 18px;border:0;border-radius:8px;background:#16a0e0;color:#fff;font-weight:600;cursor:pointer}}
</style>
<h1>🎰 Illinois Lottery FastPlay Jackpots</h1>
<div class=sub>Scraped {when}. Re-run the file any time to refresh.</div>
<table><thead><tr><th>Game</th><th style=text-align:right>Progressive Jackpot</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody></table>
<button onclick="navigator.clipboard.writeText('{csv}');this.textContent='Copied!'">Copy as CSV</button>
"""
    out = HERE / "jackpots.html"
    out.write_text(html, encoding="utf-8")
    (HERE / "jackpots.csv").write_text("\n".join(csv_lines), encoding="utf-8")
    print(f"\nResults saved to {out}")
    webbrowser.open(out.as_uri())


def main():
    try:
        ensure_setup()
        results = scrape()
        report(results)
        ok = sum(1 for r in results if r[1])
        print(f"\nDone — {ok}/{len(results)} jackpots read. A results page just opened in your browser.")
    except Exception as e:  # noqa: BLE001
        print("\nSomething went wrong:\n  " + str(e))
    finally:
        try:
            input("\nPress Enter to close this window...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
