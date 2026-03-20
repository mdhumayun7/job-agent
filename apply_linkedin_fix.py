# -*- coding: utf-8 -*-
import json, time, sys
from playwright.sync_api import sync_playwright

COOKIE_FILE = r"C:\Users\HP\Desktop\job_agent\browser_data\linkedin_cookies.json"
RESUME = r"C:\Users\HP\Desktop\job_agent\resume\MD_Humayun_Resume.pdf"

def load_cookies():
    with open(COOKIE_FILE, "r") as f:
        return json.load(f)

def apply_easy_apply(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies(load_cookies())
        page = context.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_timeout(3000)
        btn = page.query_selector(".jobs-apply-button")
        if not btn:
            btn = page.query_selector("button.jobs-apply-button--top-card")
        if not btn:
            btns = page.query_selector_all("button")
            for b in btns:
                try:
                    if "Easy Apply" in b.inner_text():
                        btn = b
                        break
                except: continue
        if not btn:
            print("Easy Apply button nahi mila!")
            input("Manual check karo — ENTER dabao: ")
            browser.close()
            return False
        print("Easy Apply button mila! Click kar raha hoon...")
        btn.click()
        page.wait_for_timeout(2000)
        for step in range(15):
            print(f"Step {step+1}...")
            try:
                phone = page.query_selector("input[id*=phoneNumber]")
                if phone and not phone.input_value(): phone.fill("8789350894")
                resume = page.query_selector("input[type=file]")
                if resume: resume.set_input_files(RESUME)
                submit = page.query_selector("button[aria-label='Submit application']")
                if submit:
                    print("Submit button mila!")
                    submit.click()
                    page.wait_for_timeout(2000)
                    print("APPLIED SUCCESSFULLY!")
                    browser.close()
                    return True
                review = page.query_selector("button[aria-label='Review your application']")
                if review: review.click()
                next_btn = page.query_selector("button[aria-label='Continue to next step']")
                if next_btn: next_btn.click()
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"Step error: {e}")
                break
        input("Manual check karo — ENTER dabao band karne ke liye: ")
        browser.close()
        return False

if __name__ == "__main__":
    url = input("LinkedIn job URL paste karo: ")
    apply_easy_apply(url)
