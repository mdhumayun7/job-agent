import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright
from helpers import log, polite_wait
from config import SEARCH_KEYWORDS, HEADLESS, REQUEST_DELAY, MAX_JOBS_PER_SITE

def scrape_shine():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        for keyword in SEARCH_KEYWORDS[:3]:
            try:
                q = keyword.replace(" ", "-")
                url = f"https://www.shine.com/job-search/{q}-jobs?experience=0-1"
                log.info(f"[Shine] {keyword}")
                page.goto(url, timeout=40000)
                page.wait_for_timeout(4000)
                for _ in range(2):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1500)

                # Get all job links directly from page
                all_links = page.query_selector_all("a[href*='/job-search/'], a[href*='/jobs/']")
                log.info(f"[Shine] {len(all_links)} links found")

                seen = set()
                for link_el in all_links[:MAX_JOBS_PER_SITE]:
                    try:
                        href = link_el.get_attribute("href") or ""
                        if not href or href in seen: continue
                        seen.add(href)
                        title = link_el.inner_text().strip()
                        if not title or len(title) < 5: continue
                        full_link = href if href.startswith("http") else "https://www.shine.com" + href

                        # Get parent card for company/location
                        parent = link_el.evaluate("el => el.closest('li') || el.closest('div.jobCard') || el.parentElement")
                        company, loc = "Company", "India"
                        try:
                            siblings = page.evaluate("""el => {
                                const p = el.closest('li') || el.closest('article') || el.parentElement.parentElement;
                                if (!p) return [];
                                return Array.from(p.querySelectorAll('span, p')).map(e => e.innerText.trim()).filter(t => t.length > 0);
                            }""", link_el)
                            if siblings and len(siblings) > 0: company = siblings[0][:80]
                            for s in siblings:
                                if any(c in s for c in ["Bangalore","Mumbai","Delhi","Hyderabad","Pune","Chennai","Remote","India","Noida"]):
                                    loc = s[:60]
                                    break
                        except:
                            pass

                        jobs.append({
                            "title": title, "company": company, "location": loc,
                            "experience": "0-1 years", "salary": "", "posted_date": "",
                            "apply_url": full_link, "source": "Shine", "keyword_used": keyword
                        })
                    except Exception as e:
                        log.debug(f"[Shine] Link error: {e}")

                polite_wait(REQUEST_DELAY)
            except Exception as e:
                log.error(f"[Shine] Error: {e}")
        browser.close()
    log.info(f"[Shine] Total: {len(jobs)}")
    return jobs
