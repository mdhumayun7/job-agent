import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE

def scrape_naukri():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        for keyword in SEARCH_KEYWORDS[:4]:
            try:
                q = keyword.replace(" ", "-")
                url = f"https://www.naukri.com/{q}-jobs?experience=0&jobAge=7"
                log.info(f"[Naukri] {keyword}")
                page.goto(url, timeout=40000)
                page.wait_for_timeout(6000)
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)

                cards = page.query_selector_all("div.cust-job-tuple")
                log.info(f"[Naukri] {len(cards)} cards for '{keyword}'")

                for card in cards[:MAX_JOBS_PER_SITE // 4]:
                    try:
                        t  = (card.query_selector("a.title") or
                              card.query_selector("a[class*='title']") or
                              card.query_selector(".title"))
                        co = (card.query_selector("a.comp-name") or
                              card.query_selector("a[class*='comp-name']") or
                              card.query_selector(".comp-name"))
                        lo = (card.query_selector("span.locWdth") or
                              card.query_selector("li[class*='loc']") or
                              card.query_selector(".loc-wrap"))
                        sa = (card.query_selector("span.sal-wrap") or
                              card.query_selector("li[class*='sal']") or
                              card.query_selector(".sal-wrap"))
                        ex = (card.query_selector("span.expwdth") or
                              card.query_selector("li[class*='exp']") or
                              card.query_selector(".exp-wrap"))

                        title   = t.inner_text().strip()  if t  else ""
                        company = co.inner_text().strip() if co else ""
                        loc     = lo.inner_text().strip() if lo else "India"
                        sal     = sa.inner_text().strip() if sa else ""
                        exp     = ex.inner_text().strip() if ex else "0-1 years"
                        href    = t.get_attribute("href") if t  else ""

                        if not title: continue
                        jobs.append({
                            "title": title, "company": company, "location": loc,
                            "experience": exp, "salary": sal, "posted_date": "",
                            "apply_url": href, "source": "Naukri", "keyword_used": keyword
                        })
                    except Exception as e:
                        log.debug(f"[Naukri] Card error: {e}")
                polite_wait(REQUEST_DELAY)
            except Exception as e:
                log.error(f"[Naukri] Error: {e}")
        browser.close()
    log.info(f"[Naukri] Total: {len(jobs)}")
    return jobs
