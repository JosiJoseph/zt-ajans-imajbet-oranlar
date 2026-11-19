"""Read-only site inspection. Never promotes unverifiable odds as live."""
import asyncio, json, re, pathlib
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

DATA = pathlib.Path("data/latest.json")
CANDIDATES = ["imajbet1660.com", "imajbet1661.com", "imajbet1662.com"]
ODD = re.compile(r"(?<!\d)(\d{1,3}[.,]\d{2})(?!\d)")
DATE = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
def norm(s): return re.sub(r"\s+", " ", s or "").strip()

async def main():
    old = json.loads(DATA.read_text())
    async with async_playwright() as browser_api:
        browser = await browser_api.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True, locale="tr-TR", user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        for domain in CANDIDATES:
            page = await ctx.new_page()
            try:
                await page.goto(f"https://{domain}/tr/sport/bet/main", wait_until="domcontentloaded", timeout=22000)
                await page.wait_for_timeout(8000)
                title = (await page.title()).lower()
                body = await page.locator("body").inner_text(timeout=7000)
                if "imajbet" not in title and "imajbet" not in body.lower():
                    continue
                # Panels must contain their labels and at least one complete price-bearing record.
                special = re.search(r"(?:Pazartesinin|Salının|Çarşambanın|Perşembenin|Cumanın|Cumartesinin|Pazarın) Özel Bahisleri[^\n]*", body, re.I)
                bomb = re.search(r"(?:Pazartesinin|Salının|Çarşambanın|Perşembenin|Cumanın|Cumartesinin|Pazarın) Bomba Oranları[^\n]*", body, re.I)
                if not special or not bomb:
                    continue
                # The site's precise DOM selectors have not yet been verified.
                # Do not guess at row boundaries or publish unrelated market odds.
                print(f"Potential panels on {domain}; manual selector validation required")
            except Exception as exc:
                print(f"{domain}: {type(exc).__name__}")
            finally:
                await page.close()
        await browser.close()
    # A successful website response is NOT proof of current odds.
    # Retain last verified snapshot until matching row-level extraction is validated.
    print("No validated row-level data; existing snapshot preserved.")

if __name__ == "__main__":
    asyncio.run(main())
