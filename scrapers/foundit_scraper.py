import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE

def scrape_foundit():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        for keyword in SEARCH_KEYWORDS[:3]:
            try:
                q = keyword.replace(" ", "+")
                url = f"https://www.foundit.in/srp/results?query={q}&experience=0"
                log.info(f"[Foundit] {keyword}")
                page.goto(url, timeout=40000)
                page.wait_for_timeout(4000)
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                cards = (
                    page.query_selector_all("div.card-apply-content") or
                    page.query_selector_all("div.jobCard") or
                    page.query_selector_all("div[class*='card-body']") or
                    page.query_selector_all("div[class*='jobCard']") or
                    page.query_selector_all("div[class*='CardContainer']") or
                    page.query_selector_all("article") or
                    page.query_selector_all("div[class*='result']")
                )
                log.info(f"[Foundit] {len(cards)} cards")
                for card in cards[:MAX_JOBS_PER_SITE // 3]:
                    try:
                        t  = (card.query_selector("h3") or card.query_selector("h2") or
                              card.query_selector("a[class*='title']") or card.query_selector("div[class*='title']"))
                        co = (card.query_selector("span[class*='company']") or
                              card.query_selector("div[class*='company']") or card.query_selector("p[class*='company']"))
                        lo = (card.query_selector("span[class*='location']") or
                              card.query_selector("div[class*='location']"))
                        a  = card.query_selector("a[href*='/job']") or card.query_selector("a")
                        title   = t.inner_text().strip()  if t  else ""
                        company = co.inner_text().strip() if co else ""
                        loc     = lo.inner_text().strip() if lo else "India"
                        href    = a.get_attribute("href") if a  else ""
                        link    = href if href.startswith("http") else "https://www.foundit.in" + href
                        if not title or not company: continue
                        jobs.append({"title": title, "company": company, "location": loc,
                                     "experience": "0-1 years", "salary": "", "posted_date": "",
                                     "apply_url": link, "source": "Foundit", "keyword_used": keyword})
                    except Exception as e:
                        log.debug(f"[Foundit] Card error: {e}")
                polite_wait(REQUEST_DELAY)
            except Exception as e:
                log.error(f"[Foundit] Error: {e}")
        browser.close()
    log.info(f"[Foundit] Total: {len(jobs)}")
    return jobs
