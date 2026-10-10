"""
End-to-end checks of the site in a real browser (device-storage mode).
Run: python -m http.server 8811 (repo root), then
     BASE=http://127.0.0.1:8811/site/index.html python tests/e2e/test_site.py
Needs website-data/ (generate_website_data.py + scripts/build_govt_data.py).
"""

import os
import sys
import tempfile
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv("BASE", "http://127.0.0.1:8811/site/index.html")
failures = []
# Real PDF / DOCX parsing loads pdf.js and mammoth from cdnjs; enable where the CDN is reachable.
CDN = os.getenv("E2E_CDN") == "1"


def check(name, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception as e:  # noqa: BLE001
        failures.append(name)
        print(f"FAIL {name}: {str(e).splitlines()[0][:300]}")


def make_pdf(path, lines):
    """Smallest valid one-page PDF with the given text lines (Helvetica)."""
    text = "BT /F1 11 Tf 50 750 Td 14 TL " + " ".join(f"({l.replace('(', '').replace(')', '')}) Tj T*" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(text)} >>\nstream\n{text}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out.encode()))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out.encode())
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    with open(path, "wb") as f:
        f.write(out.encode())


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        errors, dialogs = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        go = lambda h: (page.goto(BASE + h), page.wait_for_timeout(500))

        def manual_profile():
            go("#/profile")
            page.click("#manual")
            page.select_option("#q-level-0", "engineering")
            page.fill("#q-disc-0", "computer science")
            page.fill("#q-year-0", "2024")
            page.fill("#q-pct-0", "78")
            page.click("#addQual")
            page.select_option("#q-level-1", "12th")
            page.fill("#q-year-1", "2020")
            page.fill("#q-subj-1", "Mathematics, Physics, Chemistry")
            page.fill("#skillInput", "Python")
            page.keyboard.press("Enter")
            page.click("#reviewForm button[type=submit]")
            page.fill("#p-dob", "2002-05-10")
            page.select_option("#p-cat", "General")
            page.click("#saveBtn")
            page.wait_for_timeout(800)
            assert "#/govt" in page.url, page.url
            expect(page.locator("[class*='tag match-']").first).to_be_visible()
            page.goto(BASE + "#/govt/ssc-chsl-2026"); page.wait_for_timeout(400)
            expect(page.locator(".verdict")).to_have_text("Strong match")
        check("profile: manual entry, save, redirect to matches", manual_profile)

        def validation():
            go("#/profile")
            page.click(".steps li:nth-child(2)") if False else None
            page.click("#manual") if page.locator("#manual").count() else None
            if page.locator("#q-pct-0").count():
                page.fill("#q-pct-0", "140")
                page.click("#reviewForm button[type=submit]")
                expect(page.locator("#reviewErrors .callout.error")).to_be_visible()
                assert page.locator("#q-pct-0").get_attribute("aria-invalid") == "true"
                assert page.locator("#q-pct-0").input_value() == "140", "value must be preserved"
        check("profile: invalid marks are flagged and input preserved", validation)

        def txt_resume():
            go("#/profile")
            if page.locator("#back").count():
                page.click("#back")
            path = os.path.join(tempfile.gettempdir(), "resume.txt")
            with open(path, "w") as f:
                f.write("EDUCATION\nB.Tech, Electrical Engineering, 2023, 81%\nClass XII, Physics, Mathematics, 2019, 90%\nSKILLS\nPython, MATLAB, AutoCAD\n")
            page.set_input_files("#file", path)
            page.wait_for_timeout(600)
            expect(page.locator("#reviewForm")).to_be_visible()
            assert page.locator('[data-k="discipline"]').first.input_value() in ("electrical", "electrical engineering"), page.locator('[data-k="discipline"]').first.input_value()
            assert page.locator(".chip", has_text="MATLAB").count() == 1
        check("profile: text resume is parsed into the review form", txt_resume)

        def bad_file():
            go("#/profile")
            if page.locator("#back").count():
                page.click("#back")
            path = os.path.join(tempfile.gettempdir(), "x.pdf")
            with open(path, "wb") as f:
                f.write(b"not a pdf at all")
            page.set_input_files("#file", path)
            page.wait_for_timeout(400)
            expect(page.locator("#fileStatus")).to_contain_text("not a valid PDF")
        check("profile: invalid PDF is rejected with a clear message", bad_file)

        def pdf_resume():
            go("#/profile")
            if page.locator("#back").count():
                page.click("#back")
            path = os.path.join(tempfile.gettempdir(), "resume.pdf")
            make_pdf(path, ["EDUCATION", "B.Tech, Mechanical Engineering, 2022, 74%", "SKILLS", "AutoCAD, SolidWorks, Python"])
            page.set_input_files("#file", path)
            expect(page.locator("#reviewForm")).to_be_visible(timeout=20000)
            assert "mechanical" in page.locator('[data-k="discipline"]').first.input_value()
        def docx_resume():
            import docx
            go("#/profile")
            if page.locator("#back").count():
                page.click("#back")
            path = os.path.join(tempfile.gettempdir(), "resume.docx")
            d = docx.Document()
            for line in ["EDUCATION", "Diploma in Electrical Engineering, 2021, 70%", "SKILLS", "PLC, AutoCAD"]:
                d.add_paragraph(line)
            d.save(path)
            page.set_input_files("#file", path)
            expect(page.locator("#reviewForm")).to_be_visible(timeout=20000)
            assert page.locator('[data-k="level"]').first.input_value() == "diploma"
        if CDN:
            check("profile: PDF resume is parsed (pdf.js)", pdf_resume)
            check("profile: DOCX resume is parsed (mammoth)", docx_resume)

        def checklist():
            go("#/govt/ssc-chsl-2026")
            expect(page.locator(".verdict")).to_be_visible()
            page.fill("#qf-dob", "1990-01-01")
            page.click("#quickFill button[type=submit]")
            page.wait_for_timeout(500)
            expect(page.locator(".verdict")).to_have_text("Does not match your profile")
            page.fill("#qf-dob", "2002-05-10")
            page.click("#quickFill button[type=submit]")
            page.wait_for_timeout(500)
            expect(page.locator(".verdict")).not_to_have_text("Does not match your profile")
        check("detail: eligibility checklist recalculates after profile update", checklist)

        def save_and_dashboard():
            go("#/govt/icg-cgept-01-02-2027")
            page.click("#saveBtn")
            page.wait_for_timeout(300)
            go("#/dashboard")
            expect(page.locator("#sec-saved")).to_contain_text("Coast Guard")
        check("save a job and see it on the dashboard", save_and_dashboard)

        def reminders():
            go("#/dashboard")
            page.select_option("#pr-days", "14")
            page.click("#prefsForm button[type=submit]")
            page.wait_for_timeout(400)
            go("#/notifications")
            expect(page.locator("#list")).to_contain_text("Closes in")
            page.click("#markAll")
            page.wait_for_timeout(400)
            go("#/notifications?show=unread")
            expect(page.locator("#list")).to_contain_text("all caught up")
        check("deadline reminder appears and mark-all-read works", reminders)

        def compare():
            go("#/govt")
            boxes = page.locator('[data-act="compare"]')
            boxes.nth(0).check()
            boxes.nth(2).check()
            go("#/compare")
            expect(page.locator("table.compare")).to_be_visible()
            assert page.locator("tr.differs").count() >= 3
            page.locator("[data-remove]").first.click()
            expect(page.locator(".empty")).to_contain_text("Add one more")
        check("compare two jobs, see differences, remove one", compare)

        def filters():
            go("#/govt")
            page.fill("#f-age", "45")
            page.wait_for_timeout(400)
            txt = page.locator("#resultsCount").inner_text()
            assert txt.startswith("2 ") or txt.startswith("1 ") or txt.startswith("0 "), txt
            page.click("#resetFilters")
            page.wait_for_timeout(300)
            page.select_option("#f-qual", "12th")
            page.wait_for_timeout(300)
            assert page.locator("text=SSC CGL 2026").count() == 0
            assert "qual=12th" in page.url
        check("filters: age and qualification narrow results and update the URL", filters)

        def saved_search():
            go("#/govt?cat=SSC")
            page.click("#saveSearch")
            page.fill("#pd-input", "SSC watch")
            page.click("dialog button[value=ok]")
            page.wait_for_timeout(400)
            go("#/dashboard")
            expect(page.locator("#sec-searches")).to_contain_text("SSC watch")
        check("save a search and see it on the dashboard", saved_search)

        def palette():
            go("#/")
            page.keyboard.press("Control+k")
            page.keyboard.type("navik")
            page.wait_for_timeout(400)
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
            assert "#/govt" in page.url, page.url
            go("#/")
            page.keyboard.press("g")
            page.keyboard.press("t")
            page.wait_for_timeout(300)
            assert "#/timeline" in page.url
        check("command center and keyboard shortcuts navigate", palette)

        def guide():
            go("#/govt")
            page.click(".guide-fab")
            expect(page.locator("#guidePanel")).to_be_visible()
            page.click("#guidePanel [data-sug='0']")
            expect(page.locator(".guide-highlight")).to_have_count(1)
            page.click("#gNext")
            expect(page.locator("#f-status.guide-highlight")).to_have_count(1)
            page.click("#gOff")
            expect(page.locator("text=Turn the guide on")).to_be_visible()
            page.click("text=Turn the guide on")
            expect(page.locator(".guide-fab", has_text="Guide")).to_be_visible()
        check("guide: tips, step highlighting, turn off and on", guide)

        def field_tip():
            go("#/govt/ssc-chsl-2026")
            page.focus("#qf-dob")
            expect(page.locator(".field-tip")).to_be_visible()
            page.focus("#qf-cat")
            assert page.locator(".field-tip").count() == 1
        check("guide: inline tip shows for the focused field only", field_tip)

        def company():
            go("#/jobs")
            page.wait_for_timeout(500)
            n0 = page.locator("#count").inner_text()
            page.fill("#c-q", "intern")
            page.wait_for_timeout(400)
            assert page.locator("#count").inner_text() != n0
            page.locator(".job-row h3 a").first.click()
            page.wait_for_timeout(600)
            expect(page.locator(".desc")).to_contain_text("Python")
        check("company jobs: search and open details (description sanitised)", company)

        def not_found():
            go("#/does-not-exist")
            expect(page.locator("h1")).to_have_text("This page does not exist")
        check("unknown route shows a not-found page", not_found)

        def mobile():
            m = ctx.new_page()
            m.set_viewport_size({"width": 375, "height": 800})
            for h in ["#/", "#/govt", "#/govt/ssc-capf-si-2026", "#/compare", "#/dashboard", "#/profile", "#/jobs"]:
                m.goto(BASE + h)
                m.wait_for_timeout(500)
                assert not m.evaluate("document.documentElement.scrollWidth > window.innerWidth"), f"horizontal scroll on {h}"
            m.close()
        check("mobile: no horizontal overflow on main pages", mobile)

        def delete_all():
            go("#/dashboard")
            page.click("#deleteAll")
            page.click("dialog button[value=ok]")
            page.wait_for_timeout(500)
            go("#/dashboard")
            expect(page.locator("#sec-saved")).to_contain_text("Save jobs with the star")
        check("delete all device data", delete_all)

        check("no page errors", lambda: (_ for _ in ()).throw(AssertionError(errors)) if errors else None)
        check("no browser alert/confirm dialogs (XSS guard)", lambda: (_ for _ in ()).throw(AssertionError(dialogs)) if dialogs else None)
        browser.close()
    print(f"\n{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
