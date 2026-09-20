"""
Tracks job status across daily runs using the company+job_id dedup key
from job_schema.unique_key(). Requires data/ats_job_history.json to
actually persist between runs (the GitHub Actions workflow must commit
this file back -- see the "Persist history" step added to daily.yml).

Status logic:
  - key not in history at all           -> NEW
  - key in history, deadline/title changed -> UPDATED
  - key in history, nothing changed     -> UNCHANGED
  - key was in yesterday's history but NOT in today's fetch -> CLOSED
    (these are added back into the output list so the XLSX can show them)
"""

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "config"))

from datetime import datetime, timezone
from job_schema import unique_key

HISTORY_FILE = Path("data/ats_job_history.json")

# Fields whose change counts as "UPDATED" rather than "UNCHANGED"
WATCHED_FIELDS = ["job_title", "application_deadline", "salary_raw", "location_raw"]


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_history(history: dict):
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, default=str), encoding="utf-8")


def apply_history(jobs: list, history: dict = None) -> list:
    """
    Mutates each job's status/first_seen/last_seen in place based on
    the history file, then returns (possibly extended with CLOSED
    entries for jobs seen yesterday but not today).
    Also returns the updated history dict the caller should save.
    """
    if history is None:
        history = load_history()

    now = datetime.now(timezone.utc).isoformat()
    seen_today = set()
    new_history = dict(history)  # don't mutate caller's dict in place

    for job in jobs:
        key = unique_key(job)
        seen_today.add(key)
        prev = history.get(key)

        if prev is None:
            job["status"] = "NEW"
            job["first_seen"] = now
        else:
            changed = any(
                str(job.get(f)) != str(prev.get(f)) for f in WATCHED_FIELDS
            )
            job["status"] = "UPDATED" if changed else "UNCHANGED"
            job["first_seen"] = prev.get("first_seen", now)

        job["last_seen"] = now
        new_history[key] = {
            "first_seen": job["first_seen"],
            "last_seen": now,
            **{f: job.get(f) for f in WATCHED_FIELDS},
        }

    # Anything in history but not seen today = CLOSED
    closed_jobs = []
    for key, prev in history.items():
        if key not in seen_today:
            closed_jobs.append({
                "company": key.split("::")[0],
                "job_title": prev.get("job_title", "Not specified"),
                "location_raw": prev.get("location_raw", "Not specified"),
                "status": "CLOSED",
                "first_seen": prev.get("first_seen"),
                "last_seen": prev.get("last_seen"),
                "job_id": None, "job_url": "", "apply_url": "",
                "cse_relevant": None, "fresher_eligible": None, "internship": None,
            })
            # Keep CLOSED jobs in history too, so they don't flicker
            # back to "NEW" if they briefly reappear.
            new_history[key] = prev

    return jobs + closed_jobs, new_history


if __name__ == "__main__":
    # Self-test with synthetic data, no network needed.
    import tempfile

    original_path = HISTORY_FILE
    HISTORY_FILE = Path(tempfile.mktemp(suffix=".json"))

    # Day 1: two jobs seen for the first time
    day1 = [
        {"company": "Stripe", "job_id": "1", "job_title": "Backend Engineer", "location_raw": "SF",
         "application_deadline": None, "salary_raw": "Not disclosed"},
        {"company": "Stripe", "job_id": "2", "job_title": "Data Scientist", "location_raw": "NYC",
         "application_deadline": None, "salary_raw": "Not disclosed"},
    ]
    result1, hist1 = apply_history(day1, history={})
    assert all(j["status"] == "NEW" for j in result1), f"FAIL day1: {[j['status'] for j in result1]}"
    print("PASS: day 1, both jobs NEW")
    save_history(hist1)

    # Day 2: job 1 unchanged, job 2 title changed, job 3 is new, job... wait job 1 missing = CLOSED
    day2 = [
        {"company": "Stripe", "job_id": "1", "job_title": "Backend Engineer", "location_raw": "SF",
         "application_deadline": None, "salary_raw": "Not disclosed"},
        {"company": "Stripe", "job_id": "3", "job_title": "ML Engineer", "location_raw": "Remote",
         "application_deadline": None, "salary_raw": "Not disclosed"},
    ]
    hist_loaded = load_history()
    result2, hist2 = apply_history(day2, history=hist_loaded)

    statuses = {f"{j['company']}::{j.get('job_id')}": j["status"] for j in result2 if j.get("job_id")}
    closed = [j for j in result2 if j["status"] == "CLOSED"]

    assert statuses.get("Stripe::1") == "UNCHANGED", f"FAIL: job 1 should be UNCHANGED, got {statuses.get('Stripe::1')}"
    print("PASS: unchanged job correctly marked UNCHANGED")

    assert statuses.get("Stripe::3") == "NEW", f"FAIL: job 3 should be NEW, got {statuses.get('Stripe::3')}"
    print("PASS: newly appeared job correctly marked NEW")

    assert len(closed) == 1 and closed[0]["job_title"] == "Data Scientist", f"FAIL: expected job 2 to show as CLOSED, got {closed}"
    print("PASS: job missing from today's fetch correctly marked CLOSED")

    HISTORY_FILE.unlink(missing_ok=True)
    HISTORY_FILE = original_path
    print("\nALL SELF-TESTS PASSED")
