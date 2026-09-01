import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE, CITIES


def scrape_linkedin():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for city in CITIES[:4]:
            for keyword in SEARCH_KEYWORDS[:3]:
                try:
                    kw_enc   = keyword.replace(" ", "%20")
                    city_enc = f"{city}%2C%20India"
                    url = (
                        f"https://www.linkedin.com/jobs/search/"
                        f"?keywords={kw_enc}"
                        f"&location={city_enc}"
                        f"&f_E=1,2"
                        f"&sortBy=DD"
                    )
                    log.info(f"[LinkedIn] {keyword} | {city}")
                    page.goto(url, timeout=30000)
                    page.wait_for_timeout(3000)

                    # Scroll to load
                    for _ in range(2):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(1500)

                    cards = (
                        page.query_selector_all(".jobs-search__results-list li") or
                        page.query_selector_all("ul.jobs-search__results-list > li") or
                        page.query_selector_all("div.base-card")
                    )

                    log.info(f"[LinkedIn] {len(cards)} cards")

                    for card in cards[:MAX_JOBS_PER_SITE // 4]:
                        try:
                            title_el   = (card.query_selector("h3.base-search-card__title") or
                                          card.query_selector("span.sr-only") or
                                          card.query_selector("h3"))
                            company_el = (card.query_selector("h4.base-search-card__subtitle") or
                                          card.query_selector("a.hidden-nested-link"))
                            loc_el     = (card.query_selector("span.job-search-card__location") or
                                          card.query_selector("span[class*='location']"))
                            link_el    = (card.query_selector("a.base-card__full-link") or
                                          card.query_selector("a[data-tracking-control-name]"))
                            date_el    = card.query_selector("time")

                            title   = title_el.inner_text().strip()            if title_el   else ""
                            company = company_el.inner_text().strip()           if company_el else ""
                            loc     = loc_el.inner_text().strip()               if loc_el     else city
                            link    = link_el.get_attribute("href")             if link_el    else ""
                            posted  = date_el.get_attribute("datetime")         if date_el    else ""

                            if not title or not company:
                                continue

                            # Clean LinkedIn tracking params
                            if "?" in link:
                                link = link.split("?")[0]

                            jobs.append({
                                "title":        title,
                                "company":      company,
                                "location":     loc,
                                "experience":   "Entry Level",
                                "salary":       "",
                                "posted_date":  posted,
                                "apply_url":    link,
                                "source":       "LinkedIn",
                                "keyword_used": keyword,
                                "easy_apply":   True,
                            })
                        except Exception as e:
                            log.debug(f"[LinkedIn] Card error: {e}")
                            continue

                    polite_wait(REQUEST_DELAY)

                except PWTimeout:
                    log.warning(f"[LinkedIn] Timeout: {keyword} | {city}")
                except Exception as e:
                    log.error(f"[LinkedIn] Error: {e}")

        browser.close()
    log.info(f"[LinkedIn] Total: {len(jobs)}")
    return jobs
