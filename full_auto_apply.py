# -*- coding: utf-8 -*-
import json, time, os
from playwright.sync_api import sync_playwright

COOKIE_FILE = r"C:\Users\HP\Desktop\job_agent\browser_data\linkedin_cookies.json"
RESUME = r"C:\Users\HP\Desktop\job_agent\resume\MD_Humayun_Resume.pdf"
LOG_FILE = r"C:\Users\HP\Desktop\job_agent\output\linkedin_apply_log.json"
MY_PHONE = "8789350894"
MY_LOCATION = "Surat, Gujarat"

QUERIES = [
    "python developer fresher",
    "machine learning engineer fresher",
    "data scientist fresher",
    "software engineer fresher",
]

def load_cookies():
    with open(COOKIE_FILE) as f: return json.load(f)

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f: return json.load(f)
    return []

def save_log(log):
    with open(LOG_FILE, "w") as f: json.dump(log, f, indent=2)

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
            except: continue
        for inp in page.query_selector_all("input[type=file]"):
            try: inp.set_input_files(RESUME)
            except: continue
    except: pass

def click_easy_apply(page):
    try:
        page.wait_for_timeout(2000)
        btn = page.query_selector(".jobs-apply-button")
        if btn:
            btn.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            btn.click()
            return True
        btns = page.query_selector_all("button")
        for b in btns:
            try:
                txt = b.inner_text().strip()
                if "Easy Apply" in txt:
                    b.scroll_into_view_if_needed()
                    page.wait_for_timeout(500)
                    b.click()
                    return True
            except: continue
        return False
    except: return False

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
            if unfollow: unfollow.click()
            dismiss = page.query_selector("button[aria-label='Dismiss']")
            if dismiss: dismiss.click()
        except Exception as e:
            print(f"    Step {step} error: {e}")
            break
    return False

def apply_to_job(page, job, log):
    applied_urls = [l["url"] for l in log]
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
            print(f"  No Easy Apply button")
            log.append({"title": job["title"], "company": job["company"], "url": job["url"], "status": "No Easy Apply"})
            save_log(log)
            return False
        print(f"  Easy Apply clicked! Filling form...")
        page.wait_for_timeout(2000)
        success = submit_application(page)
        if success:
            print(f"  APPLIED SUCCESSFULLY!")
            log.append({"title": job["title"], "company": job["company"], "url": job["url"], "status": "Applied"})
        else:
            print(f"  Could not submit")
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
    url = f"https://www.linkedin.com/jobs/search/?keywords={query.replace(chr(32), chr(37)+chr(50)+chr(48))}&location=India&f_LF=f_AL&f_E=1,2&sortBy=DD"
    page.goto(url, timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(4000)
    cards = page.query_selector_all(".scaffold-layout__list li")
    print(f"  Found {len(cards)} cards for: {query}")
    for card in cards:
        try:
            container = card.query_selector("[data-job-id]")
            if not container: continue
            jid = container.get_attribute("data-job-id")
            if not jid: continue
            link = f"https://www.linkedin.com/jobs/view/{jid}/"
            t = card.query_selector(".job-card-list__title--link")
            c = card.query_selector(".artdeco-entity-lockup__subtitle span")
            title = t.inner_text().strip() if t else "Job"
            company = c.inner_text().strip() if c else "Company"
            jobs.append({"title": title, "company": company, "url": link})
        except: continue
    return jobs

def run(max_apply=20):
    print("LinkedIn Auto Apply starting...")
    log = load_log()
    already = sum(1 for l in log if l["status"] == "Applied")
    print(f"Already applied: {already} jobs")
    cookies = load_cookies()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()
        total = 0
        for query in QUERIES:
            if total >= max_apply: break
            print(f"\nSearching: {query}")
            try:
                jobs = get_jobs(page, query)
            except Exception as e:
                print(f"  Search error: {e}")
                continue
            for job in jobs:
                if total >= max_apply: break
                success = apply_to_job(page, job, log)
                if success: total += 1
                time.sleep(3)
        browser.close()
    applied = sum(1 for l in log if l["status"] == "Applied")
    print(f"\nDone! Applied: {total} jobs today | Total ever: {applied}")

if __name__ == "__main__":
    run(max_apply=20)
