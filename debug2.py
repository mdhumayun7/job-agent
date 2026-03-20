# -*- coding: utf-8 -*-
import json
from playwright.sync_api import sync_playwright

with open(r"C:\Users\HP\Desktop\job_agent\browser_data\linkedin_cookies.json") as f:
    cookies = json.load(f)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    context.add_cookies(cookies)
    page = context.new_page()
    url = "https://www.linkedin.com/jobs/search/?keywords=python+developer+fresher&location=India&f_LF=f_AL&f_E=1,2"
    page.goto(url, timeout=30000)
    page.wait_for_timeout(5000)
    for _ in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
    selectors = [
        ".jobs-search__results-list li",
        ".scaffold-layout__list li",
        ".jobs-search-results__list li",
        "li.jobs-search-results__list-item",
        ".job-card-container",
    ]
    for sel in selectors:
        cards = page.query_selector_all(sel)
        print(f"Selector: {sel!r} -> {len(cards)} cards")
    input("Browser dekho — ENTER dabao: ")
    browser.close()
