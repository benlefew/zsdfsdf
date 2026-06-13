"""
One-click local web app for scraping Illinois Lottery FastPlay jackpots.

Run:   python app.py      then open http://127.0.0.1:5000
Click "Scrape Jackpots" and the current progressive totals appear in a table,
ready to copy or download as JSON / CSV for your +EV analysis.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from scraper import scrape_games, load_config, ROOT

app = Flask(__name__)
OUTPUT_DIR = ROOT / "output"

# Guard so two clicks can't launch two browsers at once.
_lock = threading.Lock()


@app.route("/")
def index():
    cfg = load_config()
    return render_template("index.html", games=cfg["games"])


@app.route("/scrape", methods=["POST"])
def scrape():
    headed = bool(request.json and request.json.get("headed"))
    if not _lock.acquire(blocking=False):
        return jsonify({"error": "A scrape is already running. Please wait."}), 409
    try:
        results = scrape_games(headless=not headed)
        return jsonify({"games": results})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    finally:
        _lock.release()


@app.route("/latest")
def latest():
    path = OUTPUT_DIR / "latest.json"
    if not path.exists():
        return jsonify({"games": []})
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.route("/download/<fmt>")
def download(fmt: str):
    fname = {"json": "latest.json", "csv": "latest.csv"}.get(fmt)
    if not fname:
        return "Unknown format", 404
    path = OUTPUT_DIR / fname
    if not path.exists():
        return "No scrape has been run yet.", 404
    return send_file(path, as_attachment=True, download_name=fname)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
