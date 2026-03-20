import json
import time
import hashlib
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from config import YOUR_SKILLS, OUTPUT_FILE, EXCEL_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler("logs/scraper.log"), logging.StreamHandler()])
log = logging.getLogger(__name__)

def score_job(job):
    score = 0
    text = f"{job.get('title','')} {job.get('description','')}".lower()
    for skill in YOUR_SKILLS:
        if skill.lower() in text: score += 10
    for kw in ["fresher","entry level","0-1","graduate","trainee","intern","m.tech","mtech"]:
        if kw in text: score += 5
    for kw in ["senior","lead","manager","5+ years","7+ years"]:
        if kw in text: score -= 15
    return max(0, min(score, 100))

def make_job_id(job):
    key = f"{job.get('title','')}-{job.get('company','')}-{job.get('source','')}".lower()
    return hashlib.md5(key.encode()).hexdigest()[:10]

def deduplicate(jobs):
    seen = {}
    for job in jobs:
        jid = make_job_id(job)
        if jid not in seen: seen[jid] = job
    log.info(f"Dedup: {len(jobs)} -> {len(seen)} unique jobs")
    return list(seen.values())

def save_results(jobs):
    Path("output").mkdir(exist_ok=True)
    for job in jobs:
        job["match_score"] = score_job(job)
        job["scraped_at"] = datetime.now().isoformat()
    jobs.sort(key=lambda x: x["match_score"], reverse=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    log.info(f"Saved {len(jobs)} jobs to {OUTPUT_FILE}")
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Jobs Found"
        headers = ["Score", "Type", "Title", "Company", "Rating", "Stars", "Review", "Work Environment", "Location", "Eligibility", "Salary/Stipend", "Source", "Posted Date", "Days Ago", "Deadline", "Apply Link"]
        header_fill = PatternFill("solid", fgColor="4F46E5")
        header_font = Font(color="FFFFFF", bold=True)
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for row, job in enumerate(jobs, 2):
            score = job.get("match_score", 0)
            posted = job.get("posted_date", "")
            days_ago = ""
            deadline = "Check on site"
            try:
                if posted and len(posted) >= 10:
                    post_date = datetime.fromisoformat(posted[:10]).date()
                    days_ago = (date.today() - post_date).days
                    deadline = str(post_date + timedelta(days=30))
                elif posted:
                    days_ago = posted
            except: pass
            import re
            title_text = job.get("title","").lower()
            desc_text = job.get("description","").lower()
            duration = ""
            dur_match = re.search(r"(\d+)\s*(?:month|months|mon)", title_text + " " + desc_text)
            if dur_match:
                duration = f" ({dur_match.group(1)} months)"
            if any(x in title_text for x in ["intern", "internship", "trainee", "apprentice"]):
                job_type = f"Internship{duration}" if duration else "Internship"
                type_color = "C7D2FE"
            elif any(x in title_text for x in ["fresher", "junior", "entry", "graduate", "associate"]):
                job_type = "Full Time"
                type_color = "BBF7D0"
            else:
                job_type = "Full Time"
                type_color = "BBF7D0"
            from scrapers.company_ratings import get_company_rating
            company_name = job.get("company","")
            cr = get_company_rating(company_name)
            ws.cell(row=row, column=1, value=score)
            type_cell = ws.cell(row=row, column=2, value=job_type)
            type_cell.fill = PatternFill("solid", fgColor=type_color)
            type_cell.font = Font(bold=True)
            ws.cell(row=row, column=3, value=job.get("title",""))
            ws.cell(row=row, column=4, value=job.get("company",""))
            rating_val = cr["rating"]
            rating_cell = ws.cell(row=row, column=5, value=rating_val if rating_val > 0 else "N/A")
            if rating_val >= 4.5: rating_cell.fill = PatternFill("solid", fgColor="86EFAC")
            elif rating_val >= 4.0: rating_cell.fill = PatternFill("solid", fgColor="BBF7D0")
            elif rating_val >= 3.5: rating_cell.fill = PatternFill("solid", fgColor="FDE68A")
            elif rating_val > 0: rating_cell.fill = PatternFill("solid", fgColor="FCA5A5")
            ws.cell(row=row, column=6, value=cr["stars"])
            ws.cell(row=row, column=7, value=cr["review"])
            ws.cell(row=row, column=8, value=cr["environment"])
            ws.cell(row=row, column=9, value=job.get("location",""))
            ws.cell(row=row, column=10, value=job.get("eligibility","B.Tech/M.Tech"))
            ws.cell(row=row, column=11, value=job.get("salary","Not mentioned"))
            ws.cell(row=row, column=12, value=job.get("source",""))
            ws.cell(row=row, column=13, value=posted)
            ws.cell(row=row, column=14, value=days_ago)
            ws.cell(row=row, column=15, value=deadline)
            ws.cell(row=row, column=16, value=job.get("apply_url",""))
            if score >= 60: ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor="86EFAC")
            elif score >= 30: ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor="FDE68A")
            if isinstance(days_ago, int) and days_ago <= 3: ws.cell(row=row, column=14).fill = PatternFill("solid", fgColor="86EFAC")
            elif isinstance(days_ago, int) and days_ago <= 7: ws.cell(row=row, column=14).fill = PatternFill("solid", fgColor="FDE68A")
        for col in ws.columns:
            max_len = max((len(str(c.value or "")) for c in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)
        wb.save(EXCEL_FILE)
        log.info(f"Saved Excel to {EXCEL_FILE}")
    except Exception as e:
        log.error(f"Excel save error: {e}")

def polite_wait(seconds=2):
    time.sleep(seconds)
