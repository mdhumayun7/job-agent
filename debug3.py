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
    page.goto("https://www.linkedin.com/jobs/search/?keywords=python+developer+fresher&location=India&f_LF=f_AL&f_E=1,2", timeout=30000)
    page.wait_for_timeout(4000)
    cards = page.query_selector_all(".scaffold-layout__list li")
    print(f"Total cards: {len(cards)}")
    card = cards[0]
    print("\nFirst card HTML:")
    print(card.inner_html()[:2000])
    print("\nAll links in card:")
    links = card.query_selector_all("a")
    for a in links:
        href = a.get_attribute("href") or ""
        txt = a.inner_text().strip()[:50]
        print(f"  href: {href[:80]} | text: {txt}")
    input("ENTER dabao: ")
    browser.close()
