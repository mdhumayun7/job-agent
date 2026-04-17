import json
import os
import time

from playwright.sync_api import sync_playwright

from config import (
    LINKEDIN_APPLY_LOG_FILE,
    LINKEDIN_COOKIE_FILE,
    PERSONAL_INFO,
    RESUME_PATH,
)

QUERIES = [
    "python developer fresher",
    "machine learning engineer fresher",
    "data scientist fresher",
    "software engineer fresher",
]

MY_PHONE = PERSONAL_INFO.get("phone", "")
MY_LOCATION = PERSONAL_INFO.get("location", "India")


def load_cookies():
    with open(LINKEDIN_COOKIE_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_log():
    if os.path.exists(LINKEDIN_APPLY_LOG_FILE):
        with open(LINKEDIN_APPLY_LOG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(log):
    with open(LINKEDIN_APPLY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def fill_form_fields(page):
    try:
        for inp in page.query_selector_all("input[type=text], input[type=tel]"):
            try:
                label = inp.get_attribute("id") or ""
                val = inp.input_value()
                if not val:
                    if "phone" in label.lower() or "mobile" in label.lower():
                        inp.fill(MY_PHONE)
                    elif "city" in label.lower() or "location" in label.lower():
                        inp.fill(MY_LOCATION)
            except Exception:
                continue
        for inp in page.query_selector_all("input[type=file]"):
            try:
                inp.set_input_files(RESUME_PATH)
            except Exception:
                continue
    except Exception:
        pass


def click_easy_apply(page):
    try:
        page.wait_for_timeout(2000)
        btn = page.query_selector(".jobs-apply-button")
        if btn:
            btn.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            btn.click()
            return True
        for button in page.query_selector_all("button"):
            try:
                text = button.inner_text().strip()
                if "Easy Apply" in text:
                    button.scroll_into_view_if_needed()
                    page.wait_for_timeout(500)
                    button.click()
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def submit_application(page):
    for step in range(15):
        try:
            page.wait_for_timeout(1500)
            fill_form_fields(page)
            submit = page.query_selector("button[aria-label='Submit application']")
            if submit:
                submit.scroll_into_view_if_needed()
                submit.click()
                page.wait_for_timeout(2000)
                return True
            review = page.query_selector("button[aria-label='Review your application']")
            if review:
                review.scroll_into_view_if_needed()
                review.click()
                continue
            nxt = page.query_selector("button[aria-label='Continue to next step']")
            if nxt:
                nxt.scroll_into_view_if_needed()
                nxt.click()
                continue
            unfollow = page.query_selector("label[for*=follow]")
            if unfollow:
                unfollow.click()
            dismiss = page.query_selector("button[aria-label='Dismiss']")
            if dismiss:
                dismiss.click()
        except Exception as e:
            print(f"    Step {step} error: {e}")
            break
    return False


def apply_to_job(page, job, log):
    applied_urls = [entry["url"] for entry in log]
    if job["url"] in applied_urls:
        print(f"  Skip (already applied): {job['title']}")
        return False
    try:
        print(f"  Opening: {job['title']} @ {job['company']}")
        page.goto(job["url"], timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)
        clicked = click_easy_apply(page)
        if not clicked:
            print("  No Easy Apply button")
            log.append({"title": job["title"], "company": job["company"], "url": job["url"], "status": "No Easy Apply"})
            save_log(log)
            return False
        print("  Easy Apply clicked! Filling form...")
        page.wait_for_timeout(2000)
        success = submit_application(page)
        if success:
            print("  APPLIED SUCCESSFULLY!")
            log.append({"title": job["title"], "company": job["company"], "url": job["url"], "status": "Applied"})
        else:
            print("  Could not submit")
            log.append({"title": job["title"], "company": job["company"], "url": job["url"], "status": "Failed"})
        save_log(log)
        return success
    except Exception as e:
        print(f"  Error: {e}")
        log.append({"title": job["title"], "company": job["company"], "url": job["url"], "status": "Error"})
        save_log(log)
        return False


def get_jobs(page, query):
    jobs = []
    url = f"https://www.linkedin.com/jobs/search/?keywords={query.replace(chr(32), chr(37) + chr(50) + chr(48))}&location=India&f_LF=f_AL&f_E=1,2&sortBy=DD"
    page.goto(url, timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(4000)
    cards = page.query_selector_all(".scaffold-layout__list li")
    print(f"  Found {len(cards)} cards for: {query}")
    for card in cards:
        try:
            container = card.query_selector("[data-job-id]")
            if not container:
                continue
            jid = container.get_attribute("data-job-id")
            if not jid:
                continue
            link = f"https://www.linkedin.com/jobs/view/{jid}/"
            title_el = card.query_selector(".job-card-list__title--link")
            company_el = card.query_selector(".artdeco-entity-lockup__subtitle span")
            title = title_el.inner_text().strip() if title_el else "Job"
            company = company_el.inner_text().strip() if company_el else "Company"
            jobs.append({"title": title, "company": company, "url": link})
        except Exception:
            continue
    return jobs


def run(max_apply=20):
    print("LinkedIn Auto Apply starting...")
    log = load_log()
    already = sum(1 for entry in log if entry["status"] == "Applied")
    print(f"Already applied: {already} jobs")
    cookies = load_cookies()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()
        total = 0
        for query in QUERIES:
            if total >= max_apply:
                break
            print(f"\nSearching: {query}")
            try:
                jobs = get_jobs(page, query)
            except Exception as e:
                print(f"  Search error: {e}")
                continue
            for job in jobs:
                if total >= max_apply:
                    break
                success = apply_to_job(page, job, log)
                if success:
                    total += 1
                time.sleep(3)
        browser.close()
    applied = sum(1 for entry in log if entry["status"] == "Applied")
    print(f"\nDone! Applied: {total} jobs today | Total ever: {applied}")


if __name__ == "__main__":
    run(max_apply=20)
