import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE

def scrape_timesjobs():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        for keyword in SEARCH_KEYWORDS[:4]:
            try:
                q = keyword.replace(" ", "%20")
                url = f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={q}&txtLocation=India&cboWorkExp1=0&cboWorkExp2=1"
                log.info(f"[TimesJobs] {keyword}")
                page.goto(url, timeout=40000)
                page.wait_for_timeout(4000)
                for _ in range(2):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1500)
                cards = (
                    page.query_selector_all("li.clearfix.job-bx") or
                    page.query_selector_all("li[class*='job-bx']") or
                    page.query_selector_all("div.job-bx") or
                    page.query_selector_all("article.job-bx")
                )
                log.info(f"[TimesJobs] {len(cards)} cards")
                for card in cards[:MAX_JOBS_PER_SITE // 4]:
                    try:
                        t  = (card.query_selector("h2 a") or card.query_selector("h3 a") or
                              card.query_selector("a.job-title"))
                        co = (card.query_selector("h3.joblist-comp-name") or
                              card.query_selector("span.comp-name"))
                        lo = (card.query_selector("span.srp-skills") or
                              card.query_selector("ul.top-jd-dtl li"))
                        sa = card.query_selector("span.salary")
                        title   = t.inner_text().strip()  if t  else ""
                        company = co.inner_text().strip() if co else ""
                        loc     = lo.inner_text().strip() if lo else "India"
                        sal     = sa.inner_text().strip() if sa else ""
                        href    = t.get_attribute("href")  if t  else ""
                        if not title or not company: continue
                        jobs.append({"title":title,"company":company,"location":loc,
                                     "experience":"0-1 years","salary":sal,"posted_date":"",
                                     "apply_url":href,"source":"TimesJobs","keyword_used":keyword})
                    except Exception as e:
                        log.debug(f"[TimesJobs] Card error: {e}")
                polite_wait(REQUEST_DELAY)
            except Exception as e:
                log.error(f"[TimesJobs] Error: {e}")
        browser.close()
    log.info(f"[TimesJobs] Total: {len(jobs)}")
    return jobs
