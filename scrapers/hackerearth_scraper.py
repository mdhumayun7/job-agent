import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE

def scrape_hackerearth():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        urls = [
            "https://www.hackerearth.com/jobs/",
            "https://www.hackerearth.com/jobs/?experience=fresher",
        ]
        for url in urls:
            try:
                log.info(f"[HackerEarth] {url}")
                page.goto(url, timeout=40000)
                page.wait_for_timeout(5000)
                for _ in range(4):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                cards = (
                    page.query_selector_all("div.job-card") or
                    page.query_selector_all("div[class*='job-card']") or
                    page.query_selector_all("div[class*='JobCard']") or
                    page.query_selector_all("article[class*='job']")
                )
                log.info(f"[HackerEarth] {len(cards)} cards")
                for card in cards[:MAX_JOBS_PER_SITE // 2]:
                    try:
                        t  = (card.query_selector("h3") or card.query_selector("h2") or
                              card.query_selector("a[class*='title']"))
                        co = (card.query_selector("span[class*='company']") or
                              card.query_selector("div[class*='company']"))
                        lo = card.query_selector("span[class*='location']")
                        a  = card.query_selector("a[href*='/jobs/']") or card.query_selector("a")
                        title   = t.inner_text().strip()  if t  else ""
                        company = co.inner_text().strip() if co else ""
                        loc     = lo.inner_text().strip() if lo else "India"
                        href    = a.get_attribute("href")  if a  else ""
                        link    = href if href.startswith("http") else "https://www.hackerearth.com" + href
                        if not title: continue
                        jobs.append({"title":title,"company":company,"location":loc,
                                     "experience":"0-2 years","salary":"","posted_date":"",
                                     "apply_url":link,"source":"HackerEarth","keyword_used":"fresher"})
                    except Exception as e:
                        log.debug(f"[HackerEarth] Card error: {e}")
                polite_wait(REQUEST_DELAY)
            except Exception as e:
                log.error(f"[HackerEarth] Error: {e}")
        browser.close()
    log.info(f"[HackerEarth] Total: {len(jobs)}")
    return jobs
