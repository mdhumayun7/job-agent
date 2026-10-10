"""
Email alerts for signed-in users who turned them on (dashboard > Email me
deadline reminders and new matches).

At most one email per user per run (the daily 09:00 IST run). Each item has a
stable key and is recorded in email_log, so nothing is sent twice. The items are
computed by scripts/alerts/compute_alerts.mjs with the same rules as the site's
notification center.

Needs: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (service role, CI secret only),
       EMAIL_ID, EMAIL_PASSWORD (Gmail app password), optional SITE_URL.
Usage: python scripts/send_user_alerts.py [--dry-run]
"""

import argparse
import html
import json
import os
import smtplib
import subprocess
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = (os.getenv("SITE_URL") or "https://mdhumayun7.github.io/job-agent").rstrip("/")
MAX_ITEMS = 20
KIND_ORDER = {"deadline": 0, "update": 1, "match": 2, "search": 3}


class Supabase:
    def __init__(self, url, key):
        self.url, self.h = url.rstrip("/"), {"apikey": key, "Authorization": f"Bearer {key}"}

    def get(self, path, params=None):
        r = requests.get(f"{self.url}/rest/v1/{path}", params=params, headers=self.h, timeout=30)
        r.raise_for_status()
        return r.json()

    def insert(self, table, rows):
        r = requests.post(f"{self.url}/rest/v1/{table}", json=rows, timeout=30,
                          headers={**self.h, "Content-Type": "application/json", "Prefer": "resolution=ignore-duplicates,return=minimal"})
        r.raise_for_status()

    def user_email(self, uid):
        r = requests.get(f"{self.url}/auth/v1/admin/users/{uid}", headers=self.h, timeout=30)
        if r.status_code != 200:
            return None
        u = r.json()
        return u.get("email") if u.get("email_confirmed_at") else None


def in_list(ids):
    return "in.(" + ",".join(ids) + ")"


def render(items):
    rows_txt, rows_html = [], []
    for n in items:
        link = f"{SITE_URL}/site/{n['href']}"
        rows_txt.append(f"- {n['title']}\n  {n.get('body') or ''}\n  {link}".rstrip())
        rows_html.append(f'<li style="margin-bottom:10px"><a href="{html.escape(link)}">{html.escape(n["title"])}</a>'
                         f'{"<br><span style=color:#555>" + html.escape(n["body"]) + "</span>" if n.get("body") else ""}</li>')
    footer = (f"Eligibility notes are estimates; always read the official notice before applying.\n"
              f"Turn these emails off on your dashboard: {SITE_URL}/site/#/dashboard\n"
              "Job Agent is an independent student project, not affiliated with any government body.")
    text = "Updates for your saved jobs and profile:\n\n" + "\n\n".join(rows_txt) + "\n\n" + footer
    body = (f'<div style="font-family:Arial,sans-serif;max-width:620px;color:#1a1f2b"><p>Updates for your saved jobs and profile:</p>'
            f'<ul style="padding-left:18px">{"".join(rows_html)}</ul>'
            f'<p style="color:#555;font-size:13px">{"<br>".join(html.escape(x) for x in footer.splitlines())}</p></div>')
    return text, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    sender, password = os.getenv("EMAIL_ID", ""), os.getenv("EMAIL_PASSWORD", "")
    if not (url and key):
        print("Supabase is not configured; user email alerts skipped")
        return 0
    if not (sender and password) and not args.dry_run:
        print("EMAIL_ID / EMAIL_PASSWORD not set; user email alerts skipped")
        return 0
    govt_file = ROOT / "website-data" / "govt.json"
    if not govt_file.exists():
        print("website-data/govt.json missing; run scripts/build_govt_data.py first")
        return 1
    sb = Supabase(url, key)
    profiles = sb.get("profiles", {"select": "id,data,preferences", "preferences->>email_alerts": "eq.true"})
    if not profiles:
        print("no users have email alerts turned on")
        return 0
    ids = [p["id"] for p in profiles]
    saved = sb.get("saved_jobs", {"select": "user_id,job_kind,job_key,snapshot", "user_id": in_list(ids), "job_kind": "eq.govt"})
    searches = sb.get("saved_searches", {"select": "id,user_id,name,scope,query,notify,created_at", "user_id": in_list(ids), "notify": "eq.true"})
    sent_log = sb.get("email_log", {"select": "user_id,notif_key", "user_id": in_list(ids)})
    already = {(r["user_id"], r["notif_key"]) for r in sent_log}

    payload = {"jobs": json.loads(govt_file.read_text(encoding="utf-8"))["jobs"],
               "users": [{"id": p["id"], "profile": p.get("data") or {}, "prefs": p.get("preferences") or {},
                          "saved": [s for s in saved if s["user_id"] == p["id"]],
                          "searches": [s for s in searches if s["user_id"] == p["id"]]} for p in profiles]}
    res = subprocess.run(["node", str(ROOT / "scripts" / "alerts" / "compute_alerts.mjs")], input=json.dumps(payload),
                         capture_output=True, text=True, check=True)
    per_user = json.loads(res.stdout)

    server = None
    sent = 0
    try:
        for uid, items in per_user.items():
            fresh = [n for n in items if (uid, n["key"]) not in already]
            fresh.sort(key=lambda n: (KIND_ORDER.get(n["kind"], 9), str(n.get("date") or "")))
            fresh = fresh[:MAX_ITEMS]
            if not fresh:
                continue
            to = sb.user_email(uid)
            if not to:
                print(f"user {uid[:8]}: no confirmed email, skipped")
                continue
            text, body = render(fresh)
            deadlines = sum(n["kind"] == "deadline" for n in fresh)
            subject = (f"{deadlines} deadline{'s' if deadlines != 1 else ''} coming up" if deadlines else "New updates") + " - Job Agent"
            if args.dry_run:
                print(f"--- would send to user {uid[:8]}: {subject}\n{text}\n")
                continue
            if server is None:
                server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
                server.login(sender, password)
            msg = MIMEMultipart("alternative")
            msg["Subject"], msg["From"], msg["To"] = subject, sender, to
            msg.attach(MIMEText(text, "plain", "utf-8"))
            msg.attach(MIMEText(body, "html", "utf-8"))
            server.sendmail(sender, [to], msg.as_string())
            sb.insert("email_log", [{"user_id": uid, "notif_key": n["key"]} for n in fresh])
            sent += 1
    finally:
        if server is not None:
            server.quit()
    print(f"user alerts: {sent} email(s) sent to {len(profiles)} opted-in user(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
