"""
MakeMyTrip custom career-site adapter.
Confirmed real, public, unauthenticated JSON endpoint (checked directly,
live data seen 2026-09-20): https://careers.makemytrip.com/api/jobs
Not Greenhouse/Lever/SmartRecruiters -- MakeMyTrip's own in-house API.
This adapter is specific to MakeMyTrip's exact field names; it is not
a generic "custom company" adapter -- another company's in-house API
would need its own field mapping, even if the pattern (one big JSON
blob, no auth) looks similar.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))

import requests
from datetime import datetime, timezone
from job_schema import Job, NOT_SPECIFIED

API_URL = "https://careers.makemytrip.com/api/jobs"
TIMEOUT = 15


def fetch_makemytrip_jobs(company_display_name: str = "MakeMyTrip", max_retries: int = 3) -> list:
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(API_URL, timeout=TIMEOUT, headers={
                "User-Agent": "job-agent-bot/2.0 (+https://github.com/mdhumayun7/job-agent)"
            })
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            last_error = e
            print(f"[makemytrip] attempt {attempt}/{max_retries} failed: {e}")
    else:
        print(f"[makemytrip] giving up after {max_retries} attempts: {last_error}")
        raise RuntimeError(f"makemytrip fetch failed after {max_retries} attempts: {last_error}")

    jobs = []
    for raw in data.get("allJobs", []):
        if raw.get("post_on_careers_page") != 1:
            continue  # internal-only postings, not meant to be public

        locations = raw.get("location_city") or []
        location_str = ", ".join(locations) if locations else NOT_SPECIFIED

        exp_from = raw.get("experience_from") or ""
        exp_to = raw.get("experience_to") or ""
        if exp_from and exp_to:
            experience_raw = f"{exp_from}-{exp_to} years"
        elif exp_from or exp_to:
            experience_raw = f"{exp_from or exp_to}+ years"
        else:
            experience_raw = NOT_SPECIFIED

        date_posted = _parse_mmt_date(raw.get("job_created_timestamp"))

        job = Job(
            company=company_display_name,
            job_title=raw.get("job_title", NOT_SPECIFIED),
            job_id=raw.get("job_id"),
            requisition_id=raw.get("job_code"),
            job_url=f"https://careers.makemytrip.com/#!/job-view/{raw.get('job_id', '')}",
            apply_url=f"https://careers.makemytrip.com/#!/job-view/{raw.get('job_id', '')}",
            location_raw=location_str,
            experience_raw=experience_raw,
            experience_min=int(exp_from) if str(exp_from).isdigit() else None,
            experience_max=int(exp_to) if str(exp_to).isdigit() else None,
            technology_domain=raw.get("department", NOT_SPECIFIED),
            date_posted=date_posted,
            job_description="",  # not provided by this endpoint -- never fabricated
            source_website="careers.makemytrip.com",
            source_type="makemytrip_custom_api",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
        jobs.append(job.to_dict())

    print(f"[makemytrip] {company_display_name}: {len(jobs)} jobs fetched")
    return jobs


def _parse_mmt_date(ts: str):
    """MMT uses DD-MM-YYYY HH:MM:SS. Returns ISO date or None if unparseable."""
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%d-%m-%Y %H:%M:%S").date().isoformat()
    except ValueError:
        return None


if __name__ == "__main__" and "--selftest" not in sys.argv:
    results = fetch_makemytrip_jobs()
    print(f"Fetched {len(results)} jobs")
    if results:
        print(results[0]["job_title"], "-", results[0]["location_raw"], "-", results[0]["experience_raw"])

def _selftest():
    # Real structure, trimmed sample -- copied from an actual live
    # response fetched on 2026-09-20, not invented.
    sample_response = {
        "allJobs": [
            {"job_id": "a68e641568b99a", "job_code": "JOB_1755", "job_title": "Senior Software Engineer I (Frontend)",
             "department": "Technology", "location_city": ["Bangalore"], "location_country": "India",
             "post_on_careers_page": 1, "job_created_timestamp": "08-10-2025 16:17:50",
             "experience_to": "4", "experience_from": "2"},
            {"job_id": "a6a572309619e1", "job_code": "JOB_2086", "job_title": "Revenue Management - Flights",
             "department": "Domestic+International Flighs", "location_city": ["Gurgaon"], "location_country": "India",
             "post_on_careers_page": 1, "job_created_timestamp": "15-07-2026 11:34:57",
             "experience_to": "4", "experience_from": "2"},
            {"job_id": "internal_only_job", "job_code": "JOB_9999", "job_title": "Should be excluded",
             "department": "Internal", "location_city": ["Delhi"], "location_country": "India",
             "post_on_careers_page": 0, "job_created_timestamp": "01-01-2026 00:00:00",
             "experience_to": "", "experience_from": ""},
        ]
    }

    import unittest.mock as mock
    with mock.patch("requests.get") as mock_get:
        mock_resp = mock.Mock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: sample_response
        mock_get.return_value = mock_resp

        jobs = fetch_makemytrip_jobs("MakeMyTrip")

    assert len(jobs) == 2, f"FAIL: expected 2 jobs (1 excluded for post_on_careers_page=0), got {len(jobs)}"
    print("PASS: internal-only posting correctly excluded")

    j1 = jobs[0]
    assert j1["job_title"] == "Senior Software Engineer I (Frontend)"
    assert j1["location_raw"] == "Bangalore", f"FAIL: got {j1['location_raw']}"
    assert j1["experience_raw"] == "2-4 years", f"FAIL: got {j1['experience_raw']}"
    assert j1["experience_min"] == 2 and j1["experience_max"] == 4
    assert j1["date_posted"] == "2025-10-08", f"FAIL: date parsing wrong, got {j1['date_posted']}"
    assert j1["job_id"] == "a68e641568b99a"
    print("PASS: field mapping correct (title, location, experience, date)")

    assert j1["job_description"] == "", "FAIL: should be empty string, not fabricated"
    print("PASS: no description fabricated (API doesn't provide one)")

    print("\nALL SELF-TESTS PASSED")


if __name__ == "__main__" and "--selftest" in sys.argv:
    _selftest()
