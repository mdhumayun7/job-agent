import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from utils.helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, CITIES
import re

def scrape_naukri():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        for city in CITIES:
            for keyword in SEARCH_KEYWORDS[:3]:
                try:
                    url = f"https://www.naukri.com/{keyword.replace(' ', '-')}-jobs-in-{city.lower().replace(' ', '-')}"
                    log.info(f"[Naukri] {keyword} | {city}")
                    page.goto(url, timeout=30000)
                    page.wait_for_timeout(2000)
                    cards = page.query_selector_all("article.jobTuple")
                    if not cards:
                        cards = page.query_selector_all(".cust-job-tuple")
                    for card in cards[:10]:
                        try:
                            t = card.query_selector("a.title") or card.query_selector(".jobtitle")
                            c = card.query_selector("a.subTitle")
                            sal = card.query_selector(".salary")
                            exp = card.query_selector(".expwdth")
                            loc = card.query_selector(".locWdth")
                            date_el = card.query_selector(".freshness")
                            title = t.inner_text().strip() if t else ""
                            company = c.inner_text().strip() if c else ""
                            salary = sal.inner_text().strip() if sal else "Not mentioned"
                            experience = exp.inner_text().strip() if exp else "0-1 years"
                            location = loc.inner_text().strip() if loc else city
                            posted = date_el.inner_text().strip() if date_el else ""
                            link = t.get_attribute("href") if t else ""
                            eligibility = "B.Tech/M.Tech/BE"
                            if "data scien" in title.lower() or "ml" in title.lower() or "machine learn" in title.lower():
                                eligibility = "B.Tech/M.Tech CS/IT"
                            elif "full stack" in title.lower() or "react" in title.lower():
                                eligibility = "B.Tech/BE CS/IT"
                            if not title or not company:
                                continue
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "experience": experience,
                                "salary": salary,
                                "eligibility": eligibility,
                                "posted_date": posted,
                                "apply_url": link,
                                "source": "Naukri",
                                "keyword_used": keyword,
                            })
                        except Exception as e:
                            log.debug(f"[Naukri] Card error: {e}")
                            continue
                    polite_wait(REQUEST_DELAY)
                except Exception as e:
                    log.error(f"[Naukri] Error: {e}")
        browser.close()
    log.info(f"[Naukri] Total: {len(jobs)}")
    return jobs
