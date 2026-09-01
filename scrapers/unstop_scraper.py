import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE

def scrape_unstop():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        urls = [
            "https://unstop.com/jobs?filters=true&oppurtunity=jobs&fresher=1",
            "https://unstop.com/internships?filters=true&oppurtunity=internships&fresher=1",
        ]
        for base_url in urls:
            try:
                log.info(f"[Unstop] Fetching: {base_url}")
                page.goto(base_url, timeout=40000)
                page.wait_for_timeout(5000)
                for _ in range(5):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                # Try all possible card selectors
                cards = (
                    page.query_selector_all("div.opportunity-card--main") or
                    page.query_selector_all("div[class*='opportunity-card']") or
                    page.query_selector_all("div.single-listing") or
                    page.query_selector_all("un-card") or
                    page.query_selector_all("div.card") or
                    page.query_selector_all("article") or
                    page.query_selector_all("div[class*='listing']")
                )
                log.info(f"[Unstop] {len(cards)} cards found")
                for card in cards[:MAX_JOBS_PER_SITE // 2]:
                    try:
                        # Try every possible title selector
                        t = (card.query_selector("div.name") or
                             card.query_selector("h2") or card.query_selector("h3") or
                             card.query_selector("a[class*='title']") or
                             card.query_selector("p.title") or
                             card.query_selector("span.title"))
                        co = (card.query_selector("div.org-name") or
                              card.query_selector("span.company") or
                              card.query_selector("p.company") or
                              card.query_selector("div[class*='company']"))
                        a = (card.query_selector("a[href*='/jobs/']") or
                             card.query_selector("a[href*='/internship']") or
                             card.query_selector("a[href*='/opportunity']") or
                             card.query_selector("a"))
                        title   = t.inner_text().strip()  if t  else ""
                        company = co.inner_text().strip() if co else "Company"
                        href    = a.get_attribute("href") if a  else ""
                        link    = href if href.startswith("http") else "https://unstop.com" + href
                        if not title or len(title) < 3: continue
                        jobs.append({"title": title, "company": company, "location": "India",
                                     "experience": "0-1 years", "salary": "", "posted_date": "",
                                     "apply_url": link, "source": "Unstop", "keyword_used": "fresher"})
                    except Exception as e:
                        log.debug(f"[Unstop] Card error: {e}")
                polite_wait(REQUEST_DELAY)
            except Exception as e:
                log.error(f"[Unstop] Error: {e}")
        browser.close()
    log.info(f"[Unstop] Total: {len(jobs)}")
    return jobs
