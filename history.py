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


def apply_history(jobs: list, history: dict = None, fetched_companies: set = None) -> list:
    """
    Mutates each job's status/first_seen/last_seen in place based on
    the history file, then returns (possibly extended with CLOSED
    entries for jobs seen yesterday but not today).

    fetched_companies: set of lowercased company names that were
    SUCCESSFULLY fetched this run (no exception raised). If provided,
    a history entry for a company NOT in this set is left completely
    untouched -- never marked CLOSED -- because its absence from
    today's jobs might just mean its fetch failed, not that it closed.
    If None (not provided), falls back to checking every company in
    history, which is only safe when the caller is certain every
    company was actually attempted this run.
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
            "company": job.get("company"),  # preserve real casing for CLOSED-job display later
            **{f: job.get(f) for f in WATCHED_FIELDS},
        }

    # Anything in history but not seen today = CLOSED -- but only for
    # companies we actually, successfully fetched today. A company
    # whose fetch failed must not have its jobs silently marked closed.
    closed_jobs = []
    for key, prev in history.items():
        if key in seen_today:
            continue
        company_part = key.split("::")[0]
        if fetched_companies is not None and company_part not in fetched_companies:
            new_history[key] = prev  # leave untouched, don't even re-timestamp
            continue
        closed_jobs.append({
            "company": prev.get("company", company_part),  # real casing if we have it, else the lowercase key part
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

    # Day 3: simulate Stripe's fetch FAILING this run (e.g. network error).
    # Day 2 already resolved job 2 as closed; only jobs 1 and 3 remain live in history.
    # If Stripe is excluded from fetched_companies, none of its jobs should
    # be marked CLOSED even though day3 has an empty jobs list for it.
    hist_loaded_2 = load_history()
    day3 = []  # Stripe's fetch failed -- no jobs came back at all
    result3, hist3 = apply_history(day3, history=hist_loaded_2, fetched_companies=set())
    closed_on_failure = [j for j in result3 if j["status"] == "CLOSED"]
    assert len(closed_on_failure) == 0, f"FAIL: a failed fetch must not mark jobs CLOSED, got {closed_on_failure}"
    print("PASS: failed fetch (company not in fetched_companies) does NOT mark its jobs closed")

    # Confirm job 1 is still intact in history afterward (not silently dropped)
    assert "stripe::1" in hist3, "FAIL: job 1 should still be in history after a failed fetch, untouched"
    print("PASS: history entries for a failed company are preserved untouched")

    # Day 4: confirm a CLOSED job shows its real-cased company name,
    # not the lowercase dedup-key fragment. This was a real bug found
    # on live data (company count was inflated by duplicate lower/proper
    # casing entries in the website's Companies page).
    hist4_seed = {}
    day_a = [{"company": "MongoDB", "job_id": "9", "job_title": "Backend Engineer", "location_raw": "NYC",
              "application_deadline": None, "salary_raw": "Not disclosed"}]
    _, hist_a = apply_history(day_a, history=hist4_seed, fetched_companies={"mongodb"})
    day_b = []  # MongoDB's one job disappears -- should show as CLOSED with proper casing
    result_b, _ = apply_history(day_b, history=hist_a, fetched_companies={"mongodb"})
    closed_b = [j for j in result_b if j["status"] == "CLOSED"]
    assert len(closed_b) == 1 and closed_b[0]["company"] == "MongoDB", \
        f"FAIL: closed job should show 'MongoDB' (proper case), got {closed_b[0]['company'] if closed_b else None!r}"
    print("PASS: CLOSED job displays proper-cased company name, not lowercase dedup key")

    HISTORY_FILE.unlink(missing_ok=True)
    HISTORY_FILE = original_path
    print("\nALL SELF-TESTS PASSED")
