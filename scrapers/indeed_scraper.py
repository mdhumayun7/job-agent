import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, LOCATION, MAX_JOBS_PER_SITE, HEADLESS, REQUEST_DELAY


def scrape_indeed():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        for keyword in SEARCH_KEYWORDS[:4]:
            try:
                q = keyword.replace(" ", "+")
                l = LOCATION.replace(" ", "+")
                url = f"https://in.indeed.com/jobs?q={q}&l={l}&explvl=entry_level&sort=date"
                log.info(f"[Indeed] {keyword}")
                page.goto(url, timeout=30000)
                page.wait_for_timeout(3000)

                cards = (
                    page.query_selector_all("div.job_seen_beacon") or
                    page.query_selector_all("div[class*='jobCard']") or
                    page.query_selector_all("li.css-5lfssm")
                )

                log.info(f"[Indeed] {len(cards)} cards")

                for card in cards[:MAX_JOBS_PER_SITE // 4]:
                    try:
                        title_el   = (card.query_selector("h2.jobTitle a") or
                                      card.query_selector("a[class*='jcs-JobTitle']") or
                                      card.query_selector("span[title]"))
                        company_el = (card.query_selector("[data-testid='company-name']") or
                                      card.query_selector("span.companyName") or
                                      card.query_selector("a[data-testid='company-name']"))
                        loc_el     = (card.query_selector("[data-testid='text-location']") or
                                      card.query_selector("div.companyLocation"))
                        sal_el     = (card.query_selector(".salary-snippet-container") or
                                      card.query_selector("div[class*='salary']"))
                        date_el    = card.query_selector(".date")

                        title   = title_el.inner_text().strip()   if title_el   else ""
                        company = company_el.inner_text().strip()  if company_el else ""
                        loc     = loc_el.inner_text().strip()      if loc_el     else LOCATION
                        sal     = sal_el.inner_text().strip()      if sal_el     else ""
                        date    = date_el.inner_text().strip()     if date_el    else ""
                        href    = title_el.get_attribute("href")   if title_el   else ""
                        link    = f"https://in.indeed.com{href}"   if href       else ""

                        if not title or not company:
                            continue

                        jobs.append({
                            "title":        title,
                            "company":      company,
                            "location":     loc,
                            "experience":   "Entry Level",
                            "salary":       sal,
                            "posted_date":  date,
                            "apply_url":    link,
                            "source":       "Indeed",
                            "keyword_used": keyword,
                        })
                    except Exception as e:
                        log.debug(f"[Indeed] Card error: {e}")
                        continue

                polite_wait(REQUEST_DELAY)

            except PWTimeout:
                log.warning(f"[Indeed] Timeout: {keyword}")
            except Exception as e:
                log.error(f"[Indeed] Error: {e}")

        browser.close()
    log.info(f"[Indeed] Total: {len(jobs)}")
    return jobs
