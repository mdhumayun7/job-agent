"""
Build website-data/govt.json -- the government recruitment data the site reads.

Sources
  1. Reviewed records: the Supabase `govt_jobs` table (published, not archived)
     when SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set; otherwise the
     seed file data/govt_jobs.json.
  2. Automatically collected official notices (C-DAC, ISRO) from the ATS run
     (output/ats_jobs.json, source_type == "govt_notice").
       - With Supabase: inserted as unpublished drafts for an admin to review
         (existing rows are never overwritten), and not shown until published.
       - Without Supabase: shown directly, labelled "awaiting verification".

Every record gets a computed status (open / upcoming / closed / unknown) and
days_left, and is validated; invalid records are dropped with an error log.
"""

import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from govt_schema import recruitment_status, validate_job  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "govt_jobs.json"
ATS = ROOT / "output" / "ats_jobs.json"
OUT = ROOT / "website-data" / "govt.json"

ORG_META = {
    "C-DAC": {"organization": "Centre for Development of Advanced Computing (C-DAC)", "category": "Research"},
    "ISRO": {"organization": "Indian Space Research Organisation (ISRO)", "category": "Research"},
}


def slug(text, extra=""):
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")
    h = hashlib.sha1((text + extra).encode()).hexdigest()[:6]
    return f"{base}-{h}"


def automated_records(today):
    if not ATS.exists():
        return []
    out = []
    for j in json.loads(ATS.read_text(encoding="utf-8")):
        if j.get("source_type") != "govt_notice" or j.get("status") == "CLOSED":
            continue
        meta = ORG_META.get(j.get("company"), {"organization": j.get("company"), "category": "Other"})
        url = j.get("apply_url") or j.get("job_url")
        centre = j.get("technology_domain") if j.get("technology_domain") not in (None, "Not specified") else None
        rec = {
            "id": slug(f"{j.get('company')} {j.get('job_title')}", url or ""),
            "title": j.get("job_title"),
            "short_title": None,
            "organization": meta["organization"] + (f" - {centre}" if centre else ""),
            "org_short": j.get("company"),
            "category": meta["category"],
            "level": "Central",
            "state": None,
            "notification_no": j.get("requisition_id"),
            "notice_date": j.get("date_posted"),
            "posts": [],
            "vacancies": None,
            "employment_type": None,
            "pay": None,
            "qualification": None,
            "age": None,
            "fee": None,
            "experience_years": None,
            "physical_standards": False,
            "selection_process": [],
            "dates": {"application_start": j.get("date_posted"), "application_end": j.get("application_deadline")},
            "events": [],
            "links": {"notification_pdf": url if url and url.lower().endswith(".pdf") else None, "apply": url},
            "source": {"url": j.get("source_website") or url, "type": "official_page_auto"},
            "verification": {"status": "awaiting", "checked_on": today.isoformat(),
                             "method": "Collected automatically from the official recruitment page. Eligibility, fees and vacancies have not been reviewed."},
            "automated": True,
        }
        if rec["dates"]["application_start"] and rec["dates"]["application_end"] and \
                rec["dates"]["application_start"] > rec["dates"]["application_end"]:
            rec["dates"]["application_start"] = None
        out.append(rec)
    return out


def supabase_conf():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        return url.rstrip("/"), {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    return None, None


def push_drafts(base, headers, drafts):
    if not drafts:
        return 0
    rows = [{"id": d["id"], "data": d, "published": False, "source_kind": "automated"} for d in drafts]
    r = requests.post(f"{base}/rest/v1/govt_jobs?on_conflict=id", json=rows, timeout=30,
                      headers={**headers, "Prefer": "resolution=ignore-duplicates,return=minimal"})
    r.raise_for_status()
    return len(rows)


def fetch_published(base, headers):
    r = requests.get(f"{base}/rest/v1/govt_jobs", timeout=30, headers=headers,
                     params={"select": "id,data,updated_at", "published": "eq.true", "archived": "eq.false"})
    r.raise_for_status()
    out = []
    for row in r.json():
        rec = dict(row["data"])
        rec["id"] = row["id"]
        rec["updated_at"] = row.get("updated_at")
        out.append(rec)
    return out


def build(today=None):
    today = today or date.today()
    auto = automated_records(today)
    base, headers = supabase_conf()
    if base:
        n = push_drafts(base, headers, auto)
        jobs = fetch_published(base, headers)
        mode = f"supabase ({len(jobs)} published, {n} automated drafts offered for review)"
    else:
        seed = json.loads(SEED.read_text(encoding="utf-8"))["jobs"]
        known = {u for s in seed for u in ((s.get("links") or {}).get("apply"), (s.get("source") or {}).get("url")) if u}
        jobs = seed + [a for a in auto if a["links"]["apply"] not in known]
        mode = f"seed file ({len(seed)} reviewed + {len(jobs) - len(seed)} automated, awaiting verification)"

    valid, dropped = [], 0
    for j in jobs:
        errors, _ = validate_job(j)
        if errors:
            dropped += 1
            print("dropped invalid record:", "; ".join(errors))
            continue
        j["status"] = recruitment_status(j, today)
        end = (j.get("dates") or {}).get("application_end")
        j["days_left"] = (date.fromisoformat(end) - today).days if end else None
        valid.append(j)

    order = {"open": 0, "upcoming": 1, "unknown": 2, "closed": 3}
    valid.sort(key=lambda j: (order[j["status"]], j["days_left"] if j["days_left"] is not None else 9999, j["title"]))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "source_mode": "supabase" if base else "seed",
        "jobs": valid,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"govt data: {len(valid)} records from {mode}; {dropped} dropped -> {OUT.relative_to(ROOT)}")
    return payload


if __name__ == "__main__":
    build()
