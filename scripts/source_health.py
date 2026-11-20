#!/usr/bin/env python3
"""Bounded diagnostic checks; no bypassing access challenges or claiming live odds."""
import asyncio, datetime, json, re
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data/latest.json'
NOW=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
URLS=[
    'https://imajbet1660.com/tr/sport/bet/main',
    'https://m.imajbet858.com/sportsbet/main',
    *[f'https://imajbet{n}.com/tr/sport/bet/main' for n in range(1661,1666)]
]
async def inspect(browser,url):
    page=await browser.new_page(locale='tr-TR',timezone_id='Europe/Istanbul')
    try:
        response=await page.goto(url,wait_until='domcontentloaded',timeout=9000)
        await page.wait_for_timeout(900)
        body=(await page.locator('body').inner_text(timeout=3000))[:100000]
        sections=bool(re.search('özel bahisler',body,re.I) and re.search('bomba oran',body,re.I))
        challenge=bool(re.search('captcha|verify you are human|checking your browser|authentication challenge|access denied',body,re.I))
        return dict(url=url,http=response.status if response else None,final_url=page.url,sections_found=sections,challenge=challenge,verified_live_odds=False)
    except Exception as e:
        return dict(url=url,verified_live_odds=False,error=str(e)[:240])
    finally:
        await page.close()
async def main():
    data=json.loads(DATA.read_text())
    async with async_playwright() as p:
        browser=await p.chromium.launch(args=['--no-sandbox'])
        results=[]
        for url in URLS:
            results.append(await inspect(browser,url))
            if results[-1].get('sections_found'):break
        await browser.close()
    report={'checked_at':NOW.isoformat(),'results':results,'verified_live_odds':False}
    (ROOT/'data/source-health.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if data.get('status')=='live':
        data['status']='stale'
        data.pop('checked_at',None)
        data['message']='Canlı oran doğrulanamadı; son kayıt gösteriliyor.'
        DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
