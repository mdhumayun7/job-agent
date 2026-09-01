import json, smtplib, os
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from collections import Counter

# Load .env
_env = Path(".env")
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1)
            os.environ.setdefault(k.strip(),v.strip())

EMAIL_ID       = os.getenv("EMAIL_ID","")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD","")
NOTIFY_EMAIL   = os.getenv("NOTIFY_EMAIL", EMAIL_ID)
ENRICHED_FILE  = "output/jobs_enriched.json"
JOBS_FILE      = "output/jobs_found.json"

def load_jobs():
    src = ENRICHED_FILE if Path(ENRICHED_FILE).exists() else JOBS_FILE
    with open(src,"r",encoding="utf-8") as f: return json.load(f)

def score_color(s):
    if s>=60: return "#22c55e"
    elif s>=40: return "#6366f1"
    elif s>=20: return "#f59e0b"
    return "#ef4444"

def send_alert(top_n=15):
    if not EMAIL_ID or not EMAIL_PASSWORD:
        print("Set EMAIL_ID and EMAIL_PASSWORD in .env first!")
        print("Gmail: Use App Password from myaccount.google.com/security")
        return

    jobs = load_jobs()
    top  = sorted(jobs, key=lambda j: j.get("ai_match_score",j.get("match_score",0)), reverse=True)[:top_n]
    today = datetime.now().strftime("%d %B %Y")
    name  = os.getenv("APPLICANT_NAME","Candidate")

    cards = ""
    for i,job in enumerate(top,1):
        sc  = job.get("ai_match_score",job.get("match_score",0))
        col = score_color(sc)
        fit = job.get("fit_reason","")
        matched = ", ".join(job.get("matched_skills",[])[:4]) if isinstance(job.get("matched_skills",[]),list) else ""
        cards += f"""
<div style="background:#1e293b;border-left:4px solid {col};border-radius:8px;padding:16px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <div style="font-size:1rem;font-weight:700;color:#e2e8f0">{i}. {job.get('title','')}</div>
      <div style="color:#64748b;font-size:0.85rem;margin-top:4px">{job.get('company','')} &bull; {job.get('location','')} &bull; {job.get('source_group',job.get('source',''))}</div>
      <div style="color:#64748b;font-size:0.82rem;margin-top:4px">Salary: {job.get('salary','Not mentioned')}</div>
      {f'<div style="color:#94a3b8;font-size:0.82rem;font-style:italic;margin-top:6px">{fit}</div>' if fit else ''}
      {f'<div style="color:#22c55e;font-size:0.82rem;margin-top:4px">Skills: {matched}</div>' if matched else ''}
    </div>
    <div style="background:{col}22;color:{col};border:2px solid {col};font-weight:900;font-size:1.1rem;padding:8px 12px;border-radius:10px;flex-shrink:0">{sc}</div>
  </div>
  {f'<a href="{job.get("apply_url","")}" style="display:inline-block;margin-top:10px;background:#6366f1;color:white;padding:6px 16px;border-radius:6px;text-decoration:none;font-size:0.85rem;font-weight:600">Apply Now</a>' if job.get('apply_url') else ''}
</div>"""

    sources = Counter(j.get("source_group",j.get("source","")) for j in jobs)
    src_rows = "".join([f"<tr><td style='padding:6px 12px;color:#e2e8f0'>{s}</td><td style='padding:6px 12px;color:#818cf8;font-weight:700'>{c}</td></tr>" for s,c in sources.most_common()])

    html = f"""<!DOCTYPE html>
<html><body style="background:#050816;color:#e2e8f0;font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px">
<div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:16px;padding:24px;text-align:center;margin-bottom:24px">
  <h1 style="color:white;margin:0;font-size:1.6rem">Job Alert — {today}</h1>
  <p style="color:#c7d2fe;margin:8px 0 0">Hi {name}! Here are your top {top_n} job matches today.</p>
</div>
<div style="display:flex;gap:12px;margin-bottom:24px">
  <div style="flex:1;background:#1e293b;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:1.8rem;font-weight:800;color:#818cf8">{len(jobs)}</div>
    <div style="color:#64748b;font-size:0.85rem">Total Jobs</div>
  </div>
  <div style="flex:1;background:#1e293b;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:1.8rem;font-weight:800;color:#22c55e">{sum(1 for j in jobs if j.get('ai_match_score',j.get('match_score',0))>=60)}</div>
    <div style="color:#64748b;font-size:0.85rem">Excellent Matches</div>
  </div>
  <div style="flex:1;background:#1e293b;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:1.8rem;font-weight:800;color:#6366f1">{len(sources)}</div>
    <div style="color:#64748b;font-size:0.85rem">Platforms</div>
  </div>
</div>
<h2 style="font-size:1.1rem;font-weight:700;border-left:4px solid #6366f1;padding-left:12px;margin-bottom:16px">Top {top_n} Matches</h2>
{cards}
<h2 style="font-size:1rem;font-weight:700;border-left:4px solid #8b5cf6;padding-left:12px;margin:24px 0 12px">Platform Summary</h2>
<table style="width:100%;background:#1e293b;border-radius:10px;border-collapse:collapse">
  <tr style="background:#334155"><th style="padding:8px 12px;text-align:left;color:#94a3b8">Platform</th><th style="padding:8px 12px;text-align:left;color:#94a3b8">Jobs</th></tr>
  {src_rows}
</table>
<div style="text-align:center;margin-top:24px;color:#334155;font-size:0.8rem">
  Job Agent Pro &bull; {today} &bull; Auto-generated
</div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Job Alert {today} — {len(jobs)} jobs, top score {top[0].get('ai_match_score',top[0].get('match_score',0)) if top else 0}/100"
    msg["From"]    = EMAIL_ID
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html,"html"))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com",465)
        server.login(EMAIL_ID, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ID, NOTIFY_EMAIL, msg.as_string())
        server.quit()
        print(f"Email sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"Email error: {e}")
        print("Fix: Gmail > Security > 2FA on > App Passwords > Generate")

if __name__ == "__main__":
    send_alert(top_n=15)
