# -*- coding: utf-8 -*-
import json
from playwright.sync_api import sync_playwright

cookie_file = r"C:\Users\HP\Desktop\job_agent\browser_data\linkedin_cookies.json"
with open(cookie_file, "r") as cf:
    cookies = json.load(cf)

url = "https://www.linkedin.com/jobs/search/?keywords=python+developer+fresher&location=India&f_E=1,2"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    context.add_cookies(cookies)
    page = context.new_page()
    page.goto(url, timeout=30000)
    page.wait_for_timeout(4000)
    buttons = page.query_selector_all("button")
    print("Buttons found:")
    for btn in buttons:
        try:
            text = btn.inner_text().strip()
            cls = btn.get_attribute("class") or ""
            if text and len(text) < 50:
                print(text + " | " + cls[:60])
        except:
            continue
    input("ENTER dabao: ")
    browser.close()
