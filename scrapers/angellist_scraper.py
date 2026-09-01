import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE

def scrape_angellist():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        urls = [
            "https://wellfound.com/jobs/india/software-engineer",
            "https://wellfound.com/jobs/india/machine-learning-engineer",
            "https://wellfound.com/jobs/india/data-scientist",
        ]
        for url in urls:
            try:
                log.info(f"[Wellfound] {url}")
                page.goto(url, timeout=40000)
                page.wait_for_timeout(5000)
                for _ in range(4):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)

                cards = (
                    page.query_selector_all("div[class*='JobListing']") or
                    page.query_selector_all("div[class*='job-listing']") or
                    page.query_selector_all("a[href*='/jobs/']")
                )
                log.info(f"[Wellfound] {len(cards)} cards")

                for card in cards[:MAX_JOBS_PER_SITE // 3]:
                    try:
                        t  = (card.query_selector("h2") or card.query_selector("h3") or
                              card.query_selector("span[class*='title']"))
                        co = (card.query_selector("a[class*='company']") or
                              card.query_selector("span[class*='company']") or
                              card.query_selector("div[class*='startup']"))
                        lo = card.query_selector("span[class*='location']")
                        a  = card.query_selector("a[href*='/jobs/']") or card if card.tag_name == "a" else None

                        title   = t.inner_text().strip()  if t  else ""
                        company = co.inner_text().strip() if co else ""
                        loc     = lo.inner_text().strip() if lo else "India"
                        href    = ""
                        if a:
                            href = a.get_attribute("href") or ""
                        link = href if href.startswith("http") else "https://wellfound.com" + href

                        if not title: continue
                        jobs.append({
                            "title": title, "company": company, "location": loc,
                            "experience": "0-2 years", "salary": "", "posted_date": "",
                            "apply_url": link, "source": "AngelList/Wellfound", "keyword_used": "startup"
                        })
                    except Exception as e:
                        log.debug(f"[Wellfound] Card error: {e}")
                polite_wait(REQUEST_DELAY)
            except Exception as e:
                log.error(f"[Wellfound] Error: {e}")
        browser.close()
    log.info(f"[Wellfound] Total: {len(jobs)}")
    return jobs
