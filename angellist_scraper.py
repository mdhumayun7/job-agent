import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from utils.helpers import log, polite_wait
from config import LOCATION, MAX_JOBS_PER_SITE, HEADLESS, REQUEST_DELAY


def scrape_angellist():
    jobs = []

    search_urls = [
        "https://wellfound.com/jobs?role=engineer&location=india&experience=0",
        "https://wellfound.com/jobs?role=data-scientist&location=india",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()

        for url in search_urls:
            try:
                log.info(f"[AngelList] Fetching: {url}")
                page.goto(url, timeout=30000)
                page.wait_for_timeout(4000)

                for _ in range(4):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1500)

                cards = page.query_selector_all("[data-test='JobListing']")
                if not cards:
                    cards = page.query_selector_all("div[class*='jobListing']")

                log.info(f"[AngelList] {len(cards)} cards")

                for card in cards[:MAX_JOBS_PER_SITE // 2]:
                    try:
                        title_el   = card.query_selector("a[data-test='job-title']") or \
                                     card.query_selector("h2 a")
                        company_el = card.query_selector("[data-test='company-name']") or \
                                     card.query_selector("a[class*='company']")
                        loc_el     = card.query_selector("[data-test='location']")
                        sal_el     = card.query_selector("[data-test='compensation']")

                        title   = title_el.inner_text().strip()   if title_el   else ""
                        company = company_el.inner_text().strip()  if company_el else ""
                        loc     = loc_el.inner_text().strip()      if loc_el     else "India"
                        sal     = sal_el.inner_text().strip()      if sal_el     else ""
                        link    = title_el.get_attribute("href")   if title_el   else ""
                        if link and not link.startswith("http"):
                            link = "https://wellfound.com" + link

                        if not title or not company:
                            continue

                        jobs.append({
                            "title":        title,
                            "company":      company,
                            "location":     loc,
                            "experience":   "0-1 years",
                            "salary":       sal,
                            "posted_date":  "",
                            "apply_url":    link,
                            "source":       "AngelList/Wellfound",
                            "keyword_used": "software engineer",
                        })
                    except Exception as e:
                        log.debug(f"[AngelList] Card error: {e}")
                        continue

                polite_wait(REQUEST_DELAY)

            except PWTimeout:
                log.warning(f"[AngelList] Timeout")
            except Exception as e:
                log.error(f"[AngelList] Error: {e}")

        browser.close()

    log.info(f"[AngelList] Total: {len(jobs)}")
    return jobs