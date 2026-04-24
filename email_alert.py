import json
import smtplib
from collections import OrderedDict
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import EMAIL_ID, EMAIL_PASSWORD, NOTIFY_EMAIL

try:
    from config import JOBS_FILE
except ImportError:
    from config import OUTPUT_FILE as JOBS_FILE


def normalize_source(source):
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


def group_jobs_by_source(jobs, top_n):
    grouped = OrderedDict()
    preferred_order = ["LinkedIn", "Indeed", "Naukri", "Wellfound", "Government", "Other"]

    for job in sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True):
        source_name = normalize_source(job.get("source", ""))
        grouped.setdefault(source_name, [])
        if len(grouped[source_name]) < top_n:
            grouped[source_name].append(job)

    ordered_grouped = OrderedDict()
    for source_name in preferred_order:
        if source_name in grouped:
            ordered_grouped[source_name] = grouped[source_name]
    for source_name, source_jobs in grouped.items():
        if source_name not in ordered_grouped:
            ordered_grouped[source_name] = source_jobs
    return ordered_grouped


def send_job_alert(top_n=10):
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        print("No jobs file found!")
        return

    grouped_jobs = group_jobs_by_source(jobs, top_n)
    total_jobs_in_email = sum(len(source_jobs) for source_jobs in grouped_jobs.values())
    today = datetime.now().strftime("%d %B %Y")

    html = f"""
    <html><body style="font-family:Arial;max-width:700px;margin:auto">
    <div style="background:#4F46E5;padding:20px;border-radius:10px 10px 0 0">
        <h1 style="color:white;margin:0">Job Alert - {today}</h1>
        <p style="color:#C7D2FE;margin:5px 0">Top {top_n} jobs from each platform for today</p>
    </div>
    <div style="padding:20px;background:#F8FAFC">
    """

    for source_name, source_jobs in grouped_jobs.items():
        if not source_jobs:
            continue
        html += f"""
        <div style="margin-bottom:24px">
            <h2 style="margin:0 0 12px 0;color:#1E293B;border-bottom:2px solid #C7D2FE;padding-bottom:8px">
                {source_name} Top {len(source_jobs)} Jobs
            </h2>
        """
        for i, job in enumerate(source_jobs, 1):
            score = job.get("match_score", 0)
            if score >= 60:
                color = "#86EFAC"
            elif score >= 30:
                color = "#FDE68A"
            else:
                color = "#E2E8F0"
            html += f"""
            <div style="background:white;border-radius:8px;padding:16px;margin-bottom:12px;border-left:4px solid {color}">
                <div style="display:flex;justify-content:space-between">
                    <h3 style="margin:0;color:#1E293B">{i}. {job.get('title', '')}</h3>
                    <span style="background:{color};padding:4px 10px;border-radius:20px;font-weight:bold">{score}/100</span>
                </div>
                <p style="color:#64748B;margin:6px 0">{job.get('company', '')} | {job.get('location', '')}</p>
                <p style="color:#64748B;margin:4px 0">Salary: {job.get('salary', 'Not mentioned')} | Source: {job.get('source', '')}</p>
                <a href="{job.get('apply_url', '')}" style="background:#4F46E5;color:white;padding:8px 16px;border-radius:6px;text-decoration:none;display:inline-block;margin-top:8px">Apply Now</a>
            </div>
            """
        html += "</div>"

    html += """
    </div>
    <div style="background:#4F46E5;padding:12px;border-radius:0 0 10px 10px;text-align:center">
        <p style="color:#C7D2FE;margin:0">Job Agent email summary</p>
    </div>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Job Alert {today} - {total_jobs_in_email} jobs across platforms"
    msg["From"] = EMAIL_ID
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    if not EMAIL_ID or not EMAIL_PASSWORD or not NOTIFY_EMAIL:
        print("Email config is incomplete. Set EMAIL_ID, EMAIL_PASSWORD, and NOTIFY_EMAIL.")
        return

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_ID, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ID, NOTIFY_EMAIL, msg.as_string())
        server.quit()
        print(f"Email sent to {NOTIFY_EMAIL}!")
    except Exception as e:
        print(f"Email error: {e}")


if __name__ == "__main__":
    send_job_alert(top_n=10)
