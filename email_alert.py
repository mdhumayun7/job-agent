import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import EMAIL_ID, EMAIL_PASSWORD, JOBS_FILE, NOTIFY_EMAIL


def send_job_alert(top_n=10):
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        print("No jobs file found!")
        return

    top_jobs = sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)[:top_n]
    today = datetime.now().strftime("%d %B %Y")

    html = f"""
    <html><body style="font-family:Arial;max-width:700px;margin:auto">
    <div style="background:#4F46E5;padding:20px;border-radius:10px 10px 0 0">
        <h1 style="color:white;margin:0">Job Alert - {today}</h1>
        <p style="color:#C7D2FE;margin:5px 0">Top {top_n} jobs found for you today</p>
    </div>
    <div style="padding:20px;background:#F8FAFC">
    """

    for i, job in enumerate(top_jobs, 1):
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

    html += """
    </div>
    <div style="background:#4F46E5;padding:12px;border-radius:0 0 10px 10px;text-align:center">
        <p style="color:#C7D2FE;margin:0">Job Agent email summary</p>
    </div>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Job Alert {today} - {len(top_jobs)} jobs found!"
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
