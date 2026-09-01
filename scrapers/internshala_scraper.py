import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE

def scrape_internshala():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        urls = []
        for kw in SEARCH_KEYWORDS[:2]:
            slug = kw.replace(" ", "-")
            urls.append((f"https://internshala.com/internships/{slug}-internship", kw, "Internship"))
            urls.append((f"https://internshala.com/jobs/{slug}-jobs", kw, "Full Time"))
        for url, keyword, jtype in urls:
            try:
                log.info(f"[Internshala] {keyword} | {jtype}")
                page.goto(url, timeout=30000)
                page.wait_for_timeout(3000)
                cards = (page.query_selector_all("div.internship_meta") or
                         page.query_selector_all("div[class*='individual_internship']"))
                log.info(f"[Internshala] {len(cards)} cards")
                for card in cards[:MAX_JOBS_PER_SITE // 4]:
                    try:
                        t  = card.query_selector("h3.job-internship-name") or card.query_selector("a.job-title-href")
                        co = card.query_selector("p.company-name") or card.query_selector("div.company_name a")
                        lo = card.query_selector("span.location_link") or card.query_selector("div[class*='location']")
                        st = card.query_selector("span.stipend") or card.query_selector("div.salary span")
                        li = card.query_selector("a.job-title-href") or card.query_selector("h3 a")
                        title   = t.inner_text().strip()  if t  else ""
                        company = co.inner_text().strip() if co else ""
                        loc     = lo.inner_text().strip() if lo else "India"
                        stip    = st.inner_text().strip() if st else ""
                        href    = li.get_attribute("href") if li else ""
                        link    = href if href.startswith("http") else "https://internshala.com" + href
                        if not title or not company: continue
                        jobs.append({"title": title, "company": company, "location": loc,
                                     "experience": "0 years", "salary": stip, "posted_date": "",
                                     "apply_url": link, "source": "Internshala", "job_type": jtype,
                                     "keyword_used": keyword})
                    except Exception as e:
                        log.debug(f"[Internshala] Card error: {e}")
                polite_wait(REQUEST_DELAY)
            except Exception as e:
                log.error(f"[Internshala] Error: {e}")
        browser.close()
    log.info(f"[Internshala] Total: {len(jobs)}")
    return jobs
