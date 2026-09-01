import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import sync_playwright
from helpers import log

def scrape_naukri():
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        try:
            url = "https://www.naukri.com/python-developer-jobs?experience=0"
            log.info(f"[Naukri] Opening browser...")
            page.goto(url, timeout=40000)
            page.wait_for_timeout(6000)

            # Debug: print all class names found
            html = page.content()
            import re
            classes = re.findall(r'class="([^"]{5,50})"', html)
            unique = list(set(classes))[:40]
            log.info(f"[Naukri] Classes found: {unique}")

            # Try every possible card selector
            selectors = [
                "article.jobTuple", "article.job-tuple", "div.cust-job-tuple",
                "div[class*='srp-jobtuple']", "div[class*='jobTuple']",
                "div[class*='job-card']", "div[class*='JobCard']",
                "li[class*='job']", "div.job", "article"
            ]
            for sel in selectors:
                cards = page.query_selector_all(sel)
                if cards:
                    log.info(f"[Naukri] FOUND with selector '{sel}': {len(cards)} cards")

            page.wait_for_timeout(5000)
        except Exception as e:
            log.error(f"[Naukri] Error: {e}")
        finally:
            browser.close()
    return jobs

if __name__ == "__main__":
    scrape_naukri()
