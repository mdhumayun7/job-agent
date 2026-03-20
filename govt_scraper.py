import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from utils.helpers import log, polite_wait
from config import GOVT_SITES, HEADLESS, REQUEST_DELAY

RECRUITMENT_KEYWORDS = [
    "recruitment", "vacancy", "apply", "notification",
    "junior research fellow", "jrf", "scientist", "engineer",
    "technical assistant", "research associate", "walk-in",
    "interview", "application", "advt"
]


def scrape_govt_sites():
    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        for org_name, url in GOVT_SITES.items():
            try:
                log.info(f"[Govt] Checking {org_name}: {url}")
                page.goto(url, timeout=30000)
                page.wait_for_timeout(3000)

                all_links = page.query_selector_all("a")
                for link in all_links:
                    try:
                        text = link.inner_text().strip().lower()
                        href = link.get_attribute("href") or ""

                        is_job = any(kw in text for kw in RECRUITMENT_KEYWORDS)
                        is_job = is_job or any(kw in href.lower() for kw in ["recruit", "career", "vacancy", "job"])

                        if is_job and len(text) > 5:
                            full_url = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                            jobs.append({
                                "title":       link.inner_text().strip()[:120],
                                "company":     org_name,
                                "location":    "India",
                                "experience":  "Fresher / Graduate",
                                "salary":      "As per govt norms",
                                "posted_date": "",
                                "apply_url":   full_url,
                                "source":      f"Govt-{org_name}",
                                "keyword_used": "government recruitment",
                            })
                    except Exception:
                        continue

                log.info(f"[Govt] {org_name}: done")
                polite_wait(REQUEST_DELAY)

            except PWTimeout:
                log.warning(f"[Govt] Timeout: {org_name}")
            except Exception as e:
                log.error(f"[Govt] {org_name} error: {e}")

        browser.close()

    seen_urls = set()
    unique_jobs = []
    for job in jobs:
        if job["apply_url"] not in seen_urls:
            seen_urls.add(job["apply_url"])
            unique_jobs.append(job)

    log.info(f"[Govt] Total: {len(unique_jobs)}")
    return unique_jobs