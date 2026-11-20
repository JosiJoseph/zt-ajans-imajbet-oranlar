#!/usr/bin/env python3
"""Check candidate source domains without falsely claiming verified live odds."""
import asyncio, datetime, json, re
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data/latest.json'
NOW=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
async def inspect(browser,host):
    page=await browser.new_page(locale='tr-TR',timezone_id='Europe/Istanbul')
    try:
        response=await page.goto('https://'+host+'/tr/sport/bet/main',wait_until='domcontentloaded',timeout=12000)
        await page.wait_for_timeout(1500)
        txt=await page.locator('body').inner_text(timeout=4000)
        sections=bool(re.search('özel bahisler',txt,re.I) and re.search('bomba oran',txt,re.I))
        protected=bool(re.search('captcha|verify you are human|checking your browser|access denied',txt,re.I))
        return dict(host=host,http=response.status if response else None,final_url=page.url,sections_found=sections,verified_live_odds=False,reason='Full odds extraction is not yet verified' if sections else 'Required source sections missing or blocked')
    except Exception as e:
        return dict(host=host,verified_live_odds=False,error=str(e)[:180])
    finally:
        await page.close()
async def main():
    data=json.loads(DATA.read_text())
    old=re.search(r'imajbet(\d+)\.com',data.get('source',''))
    nums=list(range(1660,1691))
    if old and int(old.group(1)) in nums:
        nums.remove(int(old.group(1)));nums.insert(0,int(old.group(1)))
    checks=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(args=['--no-sandbox'])
        for n in nums:
            outcome=await inspect(browser,f'imajbet{n}.com')
            checks.append(outcome)
            if outcome.get('sections_found'):break
        await browser.close()
    report=dict(checked_at=NOW.isoformat(),candidates_checked=checks,verified_live_odds=False)
    (ROOT/'data/source-health.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    data['status']='stale'
    data['message']='Canlı oran doğrulanamadı. Son kayıt gösteriliyor.'
    data.pop('checked_at',None)
    DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
