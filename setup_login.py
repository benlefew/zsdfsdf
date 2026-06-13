"""
Optional one-time setup. FastPlay jackpot pages are public, so you usually do
NOT need this. But if the site ever shows a geolocation wall or login gate, run:

    python setup_login.py

It opens a real browser window using the same persistent profile the scraper
uses. Do whatever the site asks (confirm you're in Illinois, log in, dismiss
cookie banners), then close the window. Those cookies persist, so future
scrapes reuse them.
"""

from playwright.sync_api import sync_playwright
from scraper import PROFILE_DIR, USER_AGENT, load_config

if __name__ == "__main__":
    cfg = load_config()
    url = cfg["base_url"].rstrip("/") + cfg.get("hub_path", "/games/fpg")
    PROFILE_DIR.mkdir(exist_ok=True)
    print(f"Opening {url}")
    print("Complete any login / location / cookie prompts, then close the window.")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            user_agent=USER_AGENT,
            locale="en-US",
            timezone_id="America/Chicago",
            viewport={"width": 1366, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url)
        input("Press Enter here once you've finished and want to close the browser... ")
        ctx.close()
