import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from utils.helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, CITIES

def scrape_linkedin():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page = context.new_page()
        for city in CITIES:
            for keyword in SEARCH_KEYWORDS[:3]:
                try:
                    url = (
                        f"https://www.linkedin.com/jobs/search/"
                        f"?keywords={keyword.replace(chr(32), chr(37)+chr(50)+chr(48))}"
                        f"&location={city}%2C%20India"
                        f"&f_E=1,2"
                        f"&f_LF=f_AL"
                    )
                    log.info(f"[LinkedIn] {keyword} | {city}")
                    page.goto(url, timeout=30000)
                    page.wait_for_timeout(2000)
                    cards = page.query_selector_all(".jobs-search__results-list li")
                    for card in cards[:10]:
                        try:
                            t = card.query_selector("h3.base-search-card__title")
                            c = card.query_selector("h4.base-search-card__subtitle")
                            l = card.query_selector("a.base-card__full-link")
                            loc = card.query_selector("span.job-search-card__location")
                            date_el = card.query_selector("time")
                            title = t.inner_text().strip() if t else ""
                            company = c.inner_text().strip() if c else ""
                            link = l.get_attribute("href") if l else ""
                            location = loc.inner_text().strip() if loc else city
                            posted = date_el.get_attribute("datetime") if date_el else ""
                            if not title or not company: continue
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "experience": "Entry Level",
                                "salary": "",
                                "posted_date": posted,
                                "apply_url": link,
                                "source": "LinkedIn",
                                "keyword_used": keyword,
                                "easy_apply": True,
                            })
                        except Exception as e:
                            log.debug(f"[LinkedIn] Card error: {e}")
                            continue
                    polite_wait(REQUEST_DELAY)
                except Exception as e:
                    log.error(f"[LinkedIn] Error: {e}")
        browser.close()
    log.info(f"[LinkedIn] Total: {len(jobs)}")
    return jobs
