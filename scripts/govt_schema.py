"""
Validation rules for government recruitment records (data/govt_jobs.json and
the Supabase govt_jobs table share this shape). Used by the build, by CI and
by scripts/validate_govt_jobs.py.
"""

import re
from datetime import date

CATEGORIES = ["Central", "State", "Banking", "SSC", "UPSC", "Railways", "Teaching", "Defence", "Police", "PSU", "Research", "Other"]
LEVELS = ["10th", "12th", "iti", "diploma", "graduate", "engineering", "postgraduate", "phd"]
VERIFICATION = ["verified", "awaiting", "revised"]
DATE_KEYS = ["application_start", "application_end", "fee_end", "correction_start", "correction_end", "exam", "exam_end"]
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")


def _is_date(v):
    try:
        date.fromisoformat(str(v))
        return True
    except ValueError:
        return False


def _is_url(v):
    return isinstance(v, str) and re.match(r"^https?://[^\s]+$", v) is not None


def validate_job(j: dict) -> tuple:
    """Returns (errors, warnings) for one record."""
    e, w = [], []
    jid = j.get("id") or "?"
    p = f"[{jid}]"
    if not ID_RE.match(str(j.get("id") or "")):
        e.append(f"{p} id must be lowercase letters, digits and dashes")
    for k in ("title", "organization"):
        if not (j.get(k) or "").strip():
            e.append(f"{p} {k} is required")
    if j.get("category") not in CATEGORIES:
        e.append(f"{p} category must be one of {CATEGORIES}")
    src = j.get("source") or {}
    if not _is_url(src.get("url")):
        e.append(f"{p} source.url must be an http(s) URL of the official notice or page")
    ver = j.get("verification") or {}
    if ver.get("status") not in VERIFICATION:
        e.append(f"{p} verification.status must be one of {VERIFICATION}")
    if not _is_date(ver.get("checked_on")):
        e.append(f"{p} verification.checked_on must be an ISO date")
    dates = j.get("dates") or {}
    for k in DATE_KEYS:
        if dates.get(k) is not None and not _is_date(dates[k]):
            e.append(f"{p} dates.{k} is not an ISO date: {dates[k]!r}")
    if _is_date(dates.get("application_start")) and _is_date(dates.get("application_end")):
        if dates["application_start"] > dates["application_end"]:
            e.append(f"{p} application_start is after application_end")
    for k, v in (j.get("links") or {}).items():
        if v is not None and not _is_url(v):
            e.append(f"{p} links.{k} must be an http(s) URL")
    for ev in j.get("events") or []:
        if ev.get("date") and not _is_date(ev["date"]):
            e.append(f"{p} event date is not an ISO date: {ev['date']!r}")
        if ev.get("url") and not _is_url(ev["url"]):
            e.append(f"{p} event url must be http(s)")
    q = j.get("qualification") or {}
    for o in q.get("options") or []:
        if o.get("level") not in LEVELS:
            e.append(f"{p} qualification level {o.get('level')!r} must be one of {LEVELS}")
    age = j.get("age") or {}
    for k in ("as_on", "born_not_before", "born_not_after"):
        if age.get(k) is not None and not _is_date(age[k]):
            e.append(f"{p} age.{k} is not an ISO date")
    if ver.get("status") == "verified":
        if not (j.get("links") or {}).get("apply") and not (j.get("links") or {}).get("notification_pdf"):
            w.append(f"{p} verified record has neither an apply link nor a notification PDF")
        if not dates.get("application_end") and not dates.get("exam"):
            w.append(f"{p} verified record has no application end date or exam date")
    return e, w


def validate_all(jobs: list) -> tuple:
    errors, warnings = [], []
    seen_ids, seen_titles = set(), {}
    for j in jobs:
        e, w = validate_job(j)
        errors += e
        warnings += w
        jid = j.get("id")
        if jid in seen_ids:
            errors.append(f"[{jid}] duplicate id")
        seen_ids.add(jid)
        key = (str(j.get("organization", "")).lower().strip(), re.sub(r"\W+", " ", str(j.get("title", "")).lower()).strip())
        if key in seen_titles:
            warnings.append(f"[{jid}] possible duplicate of [{seen_titles[key]}] (same organisation and title)")
        else:
            seen_titles[key] = jid
    return errors, warnings


def recruitment_status(j: dict, today: date = None) -> str:
    today = today or date.today()
    d = j.get("dates") or {}
    start = date.fromisoformat(d["application_start"]) if d.get("application_start") else None
    end = date.fromisoformat(d["application_end"]) if d.get("application_end") else None
    if end and today > end:
        return "closed"
    if start and today < start:
        return "upcoming"
    if start or end:
        return "open"
    return "unknown"
