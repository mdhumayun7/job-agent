import hashlib
import json
import logging
import re
import sqlite3
import time
from collections import OrderedDict
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from config import (
    ALLOWED_JOB_TYPES,
    DB_FILE,
    EXCEL_FILE,
    FILTER_KEYWORDS,
    JOBS_FILE,
    MAX_EXCEL_JOBS_PER_SOURCE,
    MIN_MATCH_SCORE,
    OUTPUT_FILE,
    PREFERRED_CITIES,
    PREFERRED_SOURCES,
    REMOTE_ONLY,
    STATUS_COLORS,
    TRACKER_FILE,
    YOUR_SKILLS,
)

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "scraper.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def normalize_source_name(source):
    source_text = (source or "").strip()
    source_lower = source_text.lower()
    if "linkedin" in source_lower:
        return "LinkedIn"
    if "indeed" in source_lower:
        return "Indeed"
    if "naukri" in source_lower:
        return "Naukri"
    if "angel" in source_lower or "wellfound" in source_lower:
        return "Wellfound"
    if "govt" in source_lower or source_text.isupper():
        return "Government"
    return source_text or "Other"


def infer_job_type(job):
    title_text = job.get("title", "").lower()
    desc_text = job.get("description", "").lower()
    joined = f"{title_text} {desc_text}"
    if any(x in joined for x in ["intern", "internship", "trainee", "apprentice"]):
        return "Internship"
    return "Full Time"


def score_job(job):
    score = 0
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    for skill in YOUR_SKILLS:
        if skill.lower() in text:
            score += 10
    for kw in ["fresher", "entry level", "0-1", "graduate", "trainee", "intern", "m.tech", "mtech"]:
        if kw in text:
            score += 5
    for kw in ["senior", "lead", "manager", "5+ years", "7+ years"]:
        if kw in text:
            score -= 15
    return max(0, min(score, 100))


def make_job_id(job):
    key = f"{job.get('title', '')}-{job.get('company', '')}-{normalize_source_name(job.get('source', ''))}".lower()
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _similarity(left, right):
    return SequenceMatcher(None, _normalize_text(left), _normalize_text(right)).ratio()


def deduplicate(jobs):
    unique_jobs = []
    seen_urls = set()
    for job in jobs:
        job["source_group"] = normalize_source_name(job.get("source", ""))
        job["job_type"] = infer_job_type(job)
        job["job_id"] = make_job_id(job)

        url = job.get("apply_url", "").strip()
        if url and url in seen_urls:
            continue

        duplicate_found = False
        for existing in unique_jobs:
            same_company = _similarity(job.get("company", ""), existing.get("company", "")) >= 0.92
            same_title = _similarity(job.get("title", ""), existing.get("title", "")) >= 0.88
            same_source = job["source_group"] == existing.get("source_group")
            if same_company and same_title and same_source:
                if (job.get("match_score", 0), len(job.get("description", ""))) > (
                    existing.get("match_score", 0),
                    len(existing.get("description", "")),
                ):
                    existing.update(job)
                duplicate_found = True
                break

        if not duplicate_found:
            unique_jobs.append(job)
            if url:
                seen_urls.add(url)

    log.info(f"Dedup: {len(jobs)} -> {len(unique_jobs)} unique jobs")
    return unique_jobs


def apply_filters(jobs):
    filtered_jobs = []
    preferred_cities = {city.lower() for city in PREFERRED_CITIES}
    preferred_sources = {source.lower() for source in PREFERRED_SOURCES}
    allowed_job_types = {job_type.lower() for job_type in ALLOWED_JOB_TYPES}
    filter_keywords = [keyword.lower() for keyword in FILTER_KEYWORDS]

    for job in jobs:
        title = job.get("title", "")
        description = job.get("description", "")
        location = job.get("location", "")
        source_group = job.get("source_group", normalize_source_name(job.get("source", "")))
        job_type = job.get("job_type", infer_job_type(job))
        score = job.get("match_score", 0)
        salary_text = (job.get("salary", "") or "").lower()
        search_blob = f"{title} {description}".lower()

        if score < MIN_MATCH_SCORE:
            continue
        if allowed_job_types and job_type.lower() not in allowed_job_types:
            continue
        if preferred_sources and source_group.lower() not in preferred_sources:
            continue
        if filter_keywords and source_group != "Government" and not any(keyword in search_blob for keyword in filter_keywords):
            continue
        if REMOTE_ONLY and source_group != "Government" and "remote" not in location.lower():
            continue
        if (
            preferred_cities
            and source_group != "Government"
            and not any(city in location.lower() for city in preferred_cities)
            and "remote" not in location.lower()
        ):
            continue
        if MIN_MATCH_SCORE > 0:
            pass
        if "lpa" in salary_text and MIN_MATCH_SCORE >= 0:
            salary_numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", salary_text)]
            if salary_numbers:
                max_salary = max(salary_numbers)
                try:
                    from config import MIN_SALARY_LPA
                    if MIN_SALARY_LPA and max_salary < MIN_SALARY_LPA:
                        continue
                except Exception:
                    pass
        filtered_jobs.append(job)

    log.info(f"Filter: {len(jobs)} -> {len(filtered_jobs)} jobs after profile filters")
    return filtered_jobs


def init_database():
    Path(DB_FILE).parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                source TEXT,
                source_group TEXT,
                salary TEXT,
                apply_url TEXT,
                posted_date TEXT,
                match_score INTEGER,
                job_type TEXT,
                status TEXT,
                notes TEXT,
                applied_date TEXT,
                interview_date TEXT,
                follow_up_date TEXT,
                scraped_at TEXT,
                raw_json TEXT
            )
            """
        )
        conn.commit()


def save_jobs_to_db(jobs):
    init_database()
    with sqlite3.connect(DB_FILE) as conn:
        for job in jobs:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, title, company, location, source, source_group, salary, apply_url,
                    posted_date, match_score, job_type, status, notes, applied_date, interview_date,
                    follow_up_date, scraped_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    title=excluded.title,
                    company=excluded.company,
                    location=excluded.location,
                    source=excluded.source,
                    source_group=excluded.source_group,
                    salary=excluded.salary,
                    apply_url=excluded.apply_url,
                    posted_date=excluded.posted_date,
                    match_score=excluded.match_score,
                    job_type=excluded.job_type,
                    scraped_at=excluded.scraped_at,
                    raw_json=excluded.raw_json
                """,
                (
                    job.get("job_id"),
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("source", ""),
                    job.get("source_group", ""),
                    job.get("salary", ""),
                    job.get("apply_url", ""),
                    job.get("posted_date", ""),
                    job.get("match_score", 0),
                    job.get("job_type", ""),
                    job.get("status", "Saved"),
                    job.get("notes", ""),
                    job.get("applied_date", ""),
                    job.get("interview_date", ""),
                    job.get("follow_up_date", ""),
                    job.get("scraped_at", ""),
                    json.dumps(job, ensure_ascii=False),
                ),
            )
        conn.commit()
    log.info(f"Saved {len(jobs)} jobs to DB: {DB_FILE}")


def export_tracker(jobs):
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    tracker_path = Path(TRACKER_FILE)
    tracker_path.parent.mkdir(exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Apply Tracker"
    headers = [
        "Job ID",
        "Date Added",
        "Job Title",
        "Company",
        "Location",
        "Salary",
        "Source",
        "Status",
        "Applied Date",
        "Interview Date",
        "Follow Up Date",
        "Notes",
        "Apply Link",
    ]
    hf = PatternFill("solid", fgColor="1E293B")
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = hf
        cell.font = Font(color="FFFFFF", bold=True)

    for row_index, job in enumerate(jobs, 2):
        ws.cell(row=row_index, column=1, value=job.get("job_id"))
        ws.cell(row=row_index, column=2, value=datetime.now().strftime("%d-%m-%Y"))
        ws.cell(row=row_index, column=3, value=job.get("title", ""))
        ws.cell(row=row_index, column=4, value=job.get("company", ""))
        ws.cell(row=row_index, column=5, value=job.get("location", ""))
        ws.cell(row=row_index, column=6, value=job.get("salary", "Not mentioned"))
        ws.cell(row=row_index, column=7, value=job.get("source_group", ""))
        status_cell = ws.cell(row=row_index, column=8, value=job.get("status", "Saved"))
        status_cell.fill = PatternFill("solid", fgColor=STATUS_COLORS.get(job.get("status", "Saved"), "E2E8F0"))
        ws.cell(row=row_index, column=9, value=job.get("applied_date", ""))
        ws.cell(row=row_index, column=10, value=job.get("interview_date", ""))
        ws.cell(row=row_index, column=11, value=job.get("follow_up_date", ""))
        ws.cell(row=row_index, column=12, value=job.get("notes", ""))
        ws.cell(row=row_index, column=13, value=job.get("apply_url", ""))

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    wb.save(TRACKER_FILE)
    log.info(f"Saved tracker to {TRACKER_FILE}")


def _build_sheet(ws, jobs, title):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from company_ratings import get_company_rating

    ws.title = title[:31]
    headers = [
        "Score",
        "Type",
        "Title",
        "Company",
        "Rating",
        "Stars",
        "Review",
        "Location",
        "Salary",
        "Source",
        "Status",
        "Posted Date",
        "Days Ago",
        "Apply Link",
    ]
    header_fill = PatternFill("solid", fgColor="4F46E5")
    header_font = Font(color="FFFFFF", bold=True)
    for col, heading in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=heading)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row, job in enumerate(jobs, 2):
        score = job.get("match_score", 0)
        posted = job.get("posted_date", "")
        days_ago = ""
        try:
            if posted and len(posted) >= 10:
                post_date = datetime.fromisoformat(posted[:10]).date()
                days_ago = (date.today() - post_date).days
            elif posted:
                days_ago = posted
        except Exception:
            pass

        cr = get_company_rating(job.get("company", ""))
        ws.cell(row=row, column=1, value=score)
        type_cell = ws.cell(row=row, column=2, value=job.get("job_type", "Full Time"))
        type_cell.fill = PatternFill("solid", fgColor="C7D2FE" if job.get("job_type") == "Internship" else "BBF7D0")
        ws.cell(row=row, column=3, value=job.get("title", ""))
        ws.cell(row=row, column=4, value=job.get("company", ""))
        ws.cell(row=row, column=5, value=cr["rating"] if cr["rating"] > 0 else "N/A")
        ws.cell(row=row, column=6, value=cr["stars"])
        ws.cell(row=row, column=7, value=cr["review"])
        ws.cell(row=row, column=8, value=job.get("location", ""))
        ws.cell(row=row, column=9, value=job.get("salary", "Not mentioned"))
        ws.cell(row=row, column=10, value=job.get("source_group", ""))
        status_cell = ws.cell(row=row, column=11, value=job.get("status", "Saved"))
        status_cell.fill = PatternFill("solid", fgColor=STATUS_COLORS.get(job.get("status", "Saved"), "E2E8F0"))
        ws.cell(row=row, column=12, value=posted)
        ws.cell(row=row, column=13, value=days_ago)
        ws.cell(row=row, column=14, value=job.get("apply_url", ""))

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)


def export_excel(jobs):
    import openpyxl

    wb = openpyxl.Workbook()
    summary_ws = wb.active
    _build_sheet(summary_ws, jobs, "All Jobs")

    grouped = OrderedDict()
    for job in jobs:
        grouped.setdefault(job.get("source_group", "Other"), []).append(job)

    for source_name, source_jobs in grouped.items():
        ws = wb.create_sheet()
        _build_sheet(ws, source_jobs[:MAX_EXCEL_JOBS_PER_SOURCE], source_name)

    tracker_ws = wb.create_sheet()
    _build_sheet(tracker_ws, jobs, "Tracker Snapshot")

    wb.save(EXCEL_FILE)
    log.info(f"Saved Excel to {EXCEL_FILE}")


def save_results(jobs):
    Path("output").mkdir(exist_ok=True)
    processed_jobs = []
    for job in jobs:
        job["match_score"] = score_job(job)
        job["scraped_at"] = datetime.now().isoformat()
        job["source_group"] = normalize_source_name(job.get("source", ""))
        job["job_type"] = infer_job_type(job)
        job["status"] = job.get("status", "Saved")
        job["notes"] = job.get("notes", "")
        job["job_id"] = job.get("job_id", make_job_id(job))
        processed_jobs.append(job)

    processed_jobs = deduplicate(processed_jobs)
    processed_jobs = apply_filters(processed_jobs)
    processed_jobs.sort(key=lambda x: x["match_score"], reverse=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(processed_jobs, f, ensure_ascii=False, indent=2)
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(processed_jobs, f, ensure_ascii=False, indent=2)

    log.info(f"Saved {len(processed_jobs)} jobs to {OUTPUT_FILE}")
    save_jobs_to_db(processed_jobs)
    export_excel(processed_jobs)
    export_tracker(processed_jobs)
    return processed_jobs


def polite_wait(seconds=2):
    time.sleep(seconds)
