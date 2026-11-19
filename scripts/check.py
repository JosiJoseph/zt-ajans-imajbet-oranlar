"""Read public SPOR widgets. Publish only complete, same-day, validated records."""
import asyncio
import json
import os
import pathlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

DATA = pathlib.Path("data/latest.json")
CANDIDATES = ("imajbet1660.com", "imajbet1661.com", "imajbet1662.com")
TZ = ZoneInfo("Europe/Istanbul")
ODD = re.compile(r"^\d{1,3}[.,]\d{1,2}$")
DAY = re.compile(r"(\d{1,2})/(\d{1,2})")
MONTHS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()

def matching_day(group, today):
    m = DAY.search(group)
    return bool(m and int(m.group(1)) == today.day and int(m.group(2)) == today.month)

def odds(value):
    value = clean(value).replace(",", ".")
    if not ODD.fullmatch(value):
        raise ValueError("invalid odds")
    number = float(value)
    if number <= 1 or number > 1000:
        raise ValueError("odds outside accepted range")
    return f"{number:.2f}"

def split_selection(value):
    match, separator, condition = clean(value).partition(",")
    if not separator or len(match) < 8 or len(condition) < 5:
        raise ValueError("missing match or selection")
    return match, condition

async def inspect(page, today):
    result = await page.evaluate("""() => {
      const txt = (e) => (e?.textContent || '').replace(/\\s+/g, ' ').trim();
      const specials = [...document.querySelectorAll('div.market-item')]
        .map(e => ({group:txt(e.querySelector('h5.teams')),
          selection:txt(e.querySelector('p.selection')),
          odd:e.querySelector('button[data-odd]')?.getAttribute('data-odd')}));
      const bombs = [...document.querySelectorAll('div.event-item.regular-view')]
        .map(e => ({group:txt(e.querySelector('h4.teams')),
          selection:txt(e.querySelector('p.selection')),
          previous:txt(e.querySelector('.event-was-content .rate')),
          current:txt(e.querySelector('.event-now-content .bet-rate'))}));
      return {title:document.title, specials, bombs};
    }""")
    if "imajbet" not in result["title"].replace("İ", "I").lower():
        raise ValueError("brand could not be verified")
    specials, bombs = [], []
    for row in result["specials"]:
        if not (matching_day(row["group"], today) and "Özel Bahisleri" in row["group"]):
            continue
        match, condition = split_selection(row["selection"])
        specials.append({"group":row["group"], "match":match, "condition":condition, "odd":odds(row["odd"])})
    for row in result["bombs"]:
        if not (matching_day(row["group"], today) and "Bomba Oranları" in row["group"]):
            continue
        match, condition = split_selection(row["selection"])
        bombs.append({"group":row["group"], "match":match, "condition":condition,
                      "previous":odds(row["previous"]), "current":odds(row["current"])})
    if not specials or not bombs:
        raise ValueError(f"incomplete same-day widgets (special={len(specials)}, bomb={len(bombs)})")
    keys1 = {(x["group"], x["match"], x["condition"]) for x in specials}
    keys2 = {(x["group"], x["match"], x["condition"]) for x in bombs}
    if len(keys1) != len(specials) or len(keys2) != len(bombs):
        raise ValueError("duplicate records")
    return specials, bombs

async def main():
    now = datetime.now(TZ)
    original = json.loads(DATA.read_text(encoding="utf-8"))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width":390,"height":844},
            is_mobile=True,has_touch=True,locale="tr-TR",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        )
        for host in CANDIDATES:
            page = await context.new_page()
            url = f"https://{host}/tr/sport/bet/main"
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=22000)
                if not response or response.status != 200:
                    raise ValueError(f"HTTP {response.status if response else 'no response'}")
                if not (page.url.startswith(f"https://{host}/")):
                    raise ValueError("unexpected redirect")
                await page.locator("div.market-item h5.teams").first.wait_for(timeout=16000)
                await page.locator("div.event-item.regular-view h4.teams").first.wait_for(timeout=16000)
                specials,bombs = await inspect(page,now)
                original.update({
                    "date":now.strftime("%Y-%m-%d"),
                    "status":"live",
                    "source":host,
                    "source_url":url,
                    "checked_at":now.isoformat(timespec="seconds"),
                    "message":"",
                    "candidates":list(CANDIDATES),
                    "specials":specials,"bombs":bombs,
                })
                DATA.parent.mkdir(parents=True,exist_ok=True)
                temporary = DATA.with_suffix(".tmp")
                temporary.write_text(json.dumps(original,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                os.replace(temporary,DATA)
                print(f"VERIFIED {host}: {len(specials)} specials, {len(bombs)} bombs")
                return
            except Exception as exc:
                print(f"REJECT {host}: {type(exc).__name__}: {str(exc)[:140]}")
            finally:
                await page.close()
        await browser.close()
    # No source has been verified: do not overwrite the last valid snapshot.
    print("ALL SOURCES UNAVAILABLE; snapshot retained")
if __name__ == "__main__":
    asyncio.run(main())
