"""
Scrapes current progressive jackpot totals for Illinois Lottery FastPlay games.

The illinoislottery.com site is JavaScript-rendered and protected by Akamai-style
bot detection (plain HTTP requests get a 403). So we drive a real Chromium browser
with Playwright. For each configured game we open its FastPlay page and read the
jackpot two ways, preferring whichever is most reliable:

  1. Network JSON  - the page fetches its own data from a backend API. We capture
                     those JSON responses and pull the jackpot value out of them.
                     This is the source of truth (it's the exact number the page
                     renders), so we use it when available.
  2. DOM text      - fallback. We read the rendered page text and regex out the
                     dollar amount next to a "Progressive Jackpot" style label.

A persistent browser profile is used so that any one-time login / Illinois
geolocation cookie survives between runs (see setup_login.py).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from playwright.sync_api import sync_playwright, Page, Response, TimeoutError as PWTimeout

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "games.json"
PROFILE_DIR = ROOT / ".browser_profile"        # persistent login / geo cookies
DEBUG_DIR = ROOT / "debug"                      # raw captures for troubleshooting

# A realistic desktop Chrome UA helps avoid the most basic bot blocks.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# Labels that precede a progressive jackpot amount on the rendered page.
JACKPOT_LABEL = re.compile(
    r"(?:progressive\s+(?:jackpot|top\s+prize)|estimated\s+jackpot|current\s+jackpot|jackpot)"
    r"[^$]{0,40}?\$\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE,
)
# Any dollar amount with at least 4 digits (skips $5/ticket style prices).
ANY_BIG_DOLLAR = re.compile(r"\$\s*([\d,]{4,}(?:\.\d{2})?)")
# JSON keys that hold a jackpot figure.
JACKPOT_KEY = re.compile(r"jackpot|progressive|top.?prize", re.IGNORECASE)


@dataclass
class GameResult:
    name: str
    slug: str
    url: str
    jackpot: Optional[str]          # formatted, e.g. "$786,049"
    jackpot_value: Optional[float]  # numeric, e.g. 786049.0
    source: str                     # "network-json" | "dom-text" | "none"
    ok: bool
    error: Optional[str]
    scraped_at: str                 # ISO-8601 UTC

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _to_float(raw: str) -> Optional[float]:
    try:
        return float(raw.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _format(value: float) -> str:
    # Whole-dollar jackpots render without cents; keep cents only if present.
    if value == int(value):
        return f"${int(value):,}"
    return f"${value:,.2f}"


def _walk_json_for_jackpot(obj: Any) -> Optional[float]:
    """Recursively find the largest jackpot-looking number in a JSON blob.

    On a single game's page the only big "jackpot" figure is that game's
    progressive total, so taking the largest match is safe here.
    """
    best: Optional[float] = None

    def consider(v: float) -> None:
        nonlocal best
        if v >= 100 and (best is None or v > best):
            best = v

    def recurse(node: Any, key_hint: bool = False) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                hit = bool(JACKPOT_KEY.search(str(k)))
                if hit and isinstance(v, (int, float)) and not isinstance(v, bool):
                    consider(float(v))
                elif hit and isinstance(v, str):
                    m = re.search(r"[\d,]+(?:\.\d+)?", v)
                    if m:
                        f = _to_float(m.group(0))
                        if f is not None:
                            consider(f)
                recurse(v, hit)
        elif isinstance(node, list):
            for item in node:
                recurse(item, key_hint)

    recurse(obj)
    return best


def _extract_from_text(text: str) -> Optional[float]:
    """Pull a jackpot dollar amount out of rendered page text."""
    m = JACKPOT_LABEL.search(text)
    if m:
        return _to_float(m.group(1))
    # Fallback: the biggest 4+ digit dollar figure on the page.
    candidates = [_to_float(x) for x in ANY_BIG_DOLLAR.findall(text)]
    candidates = [c for c in candidates if c is not None]
    return max(candidates) if candidates else None


def _scrape_one(page: Page, name: str, slug: str, url: str, settle_ms: int) -> GameResult:
    captured_json: list[Any] = []

    def on_response(resp: Response) -> None:
        ctype = (resp.headers or {}).get("content-type", "")
        if "json" not in ctype.lower():
            return
        try:
            captured_json.append(resp.json())
        except Exception:
            pass  # non-JSON body or already consumed; ignore

    page.on("response", on_response)
    now = datetime.now(timezone.utc).isoformat()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PWTimeout:
            pass  # some pages keep long-poll connections open; that's fine
        page.wait_for_timeout(settle_ms)

        # 1) Authoritative: jackpot from the page's own API responses.
        value: Optional[float] = None
        source = "none"
        for blob in captured_json:
            found = _walk_json_for_jackpot(blob)
            if found is not None and (value is None or found > value):
                value = found
                source = "network-json"

        # 2) Fallback: jackpot read from rendered page text.
        if value is None:
            text = page.inner_text("body")
            value = _extract_from_text(text)
            if value is not None:
                source = "dom-text"

        if value is None:
            return GameResult(name, slug, url, None, None, "none", False,
                              "No jackpot value found on page", now)
        return GameResult(name, slug, url, _format(value), value, source, True, None, now)
    except Exception as exc:  # noqa: BLE001 - report any failure per-game, keep going
        return GameResult(name, slug, url, None, None, "none", False, str(exc), now)
    finally:
        page.remove_listener("response", on_response)


def scrape_games(
    games: Optional[Iterable[dict]] = None,
    headless: bool = True,
    settle_ms: int = 2000,
    on_progress=None,
) -> list[dict]:
    """Scrape jackpots for the configured games. Returns a list of result dicts.

    `on_progress(done, total, result_dict)` is called after each game if given.
    """
    cfg = load_config()
    base = cfg["base_url"].rstrip("/")
    template = cfg.get("game_path_template", "/games/fpg/{slug}")
    targets = list(games) if games is not None else cfg["games"]
    total = len(targets)

    DEBUG_DIR.mkdir(exist_ok=True)
    PROFILE_DIR.mkdir(exist_ok=True)

    results: list[dict] = []
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            user_agent=USER_AGENT,
            locale="en-US",
            timezone_id="America/Chicago",
            viewport={"width": 1366, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for i, g in enumerate(targets, start=1):
                url = base + template.format(slug=g["slug"])
                res = _scrape_one(page, g["name"], g["slug"], url, settle_ms)
                results.append(res.to_dict())
                if on_progress:
                    on_progress(i, total, res.to_dict())
        finally:
            context.close()

    # Persist the latest run for the UI / downloads / auditing.
    _write_outputs(results)
    return results


def _write_outputs(results: list[dict]) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    payload = {"scraped_at": datetime.now(timezone.utc).isoformat(), "games": results}

    (out_dir / "latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / f"jackpots_{stamp}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # CSV
    lines = ["name,slug,jackpot_value,jackpot,source,ok,error,scraped_at"]
    for r in results:
        err = (r.get("error") or "").replace('"', "'")
        lines.append(
            f'"{r["name"]}","{r["slug"]}",{r.get("jackpot_value") or ""},'
            f'"{r.get("jackpot") or ""}","{r["source"]}",{r["ok"]},"{err}","{r["scraped_at"]}"'
        )
    csv_text = "\n".join(lines) + "\n"
    (out_dir / "latest.csv").write_text(csv_text, encoding="utf-8")
    (out_dir / f"jackpots_{stamp}.csv").write_text(csv_text, encoding="utf-8")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Scrape Illinois Lottery FastPlay progressive jackpots.")
    ap.add_argument("--headed", action="store_true", help="Show the browser window while scraping.")
    ap.add_argument("--settle-ms", type=int, default=2000, help="Extra wait after load for JS to render.")
    args = ap.parse_args()

    start = time.time()

    def progress(done, total, r):
        status = r["jackpot"] if r["ok"] else f"FAILED ({r['error']})"
        print(f"[{done}/{total}] {r['name']:<28} {status}")

    rows = scrape_games(headless=not args.headed, settle_ms=args.settle_ms, on_progress=progress)
    ok = sum(1 for r in rows if r["ok"])
    print(f"\nDone in {time.time() - start:.1f}s — {ok}/{len(rows)} jackpots scraped.")
    print("Wrote output/latest.json and output/latest.csv")
