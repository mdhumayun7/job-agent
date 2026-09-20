"""
Greenhouse ATS adapter.

Uses Greenhouse's PUBLIC job board API -- documented, no auth needed,
intended for external consumption. This is not scraping in the sense
your other rules worry about; it's a published API.

Docs: https://developers.greenhouse.io/job-board.html
Endpoint: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))

import requests
from datetime import datetime, timezone
from job_schema import Job, NOT_SPECIFIED, NOT_DISCLOSED

API_BASE = "https://boards-api.greenhouse.io/v1/boards"
TIMEOUT = 15


def fetch_greenhouse_jobs(board_token: str, company_display_name: str, max_retries: int = 3) -> list:
    """
    board_token: the slug in boards.greenhouse.io/<slug>
    Returns a list of Job dicts. Returns [] and logs on failure --
    never fabricates data if the board_token is wrong or the API is down.
    """
    url = f"{API_BASE}/{board_token}/jobs?content=true"
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers={
                "User-Agent": "job-agent-bot/2.0 (+https://github.com/mdhumayun7/job-agent)"
            })
            if resp.status_code == 404:
                print(f"[greenhouse] '{board_token}' is not a valid Greenhouse board token (404). "
                      f"Verify the slug at boards.greenhouse.io/{board_token}")
                return []
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            last_error = e
            print(f"[greenhouse] attempt {attempt}/{max_retries} failed for '{board_token}': {e}")
    else:
        print(f"[greenhouse] giving up on '{board_token}' after {max_retries} attempts: {last_error}")
        return []

    jobs = []
    for raw in data.get("jobs", []):
        job = Job(
            company=company_display_name,
            job_title=raw.get("title", NOT_SPECIFIED),
            job_id=str(raw.get("id")) if raw.get("id") else None,
            requisition_id=raw.get("requisition_id"),
            job_url=raw.get("absolute_url", ""),
            apply_url=raw.get("absolute_url", ""),
            location_raw=(raw.get("location") or {}).get("name", NOT_SPECIFIED),
            date_posted=raw.get("updated_at"),
            last_updated=raw.get("updated_at"),
            job_description=raw.get("content", ""),
            source_website=f"boards.greenhouse.io/{board_token}",
            source_type="greenhouse_api",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
        jobs.append(job.to_dict())

    print(f"[greenhouse] {company_display_name}: {len(jobs)} jobs fetched")
    return jobs


if __name__ == "__main__":
    # Quick manual test: python adapter_greenhouse.py stripe "Stripe"
    import sys
    token = sys.argv[1] if len(sys.argv) > 1 else "stripe"
    name = sys.argv[2] if len(sys.argv) > 2 else token
    results = fetch_greenhouse_jobs(token, name)
    print(f"Fetched {len(results)} jobs for {name}")
    if results:
        print(results[0]["job_title"], "-", results[0]["location_raw"])
