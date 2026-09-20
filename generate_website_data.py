"""
Turns output/ats_jobs.json into website-data/:
  - website-data/index.json       lightweight, for listing/search/filter pages
  - website-data/jobs/<key>.json  one file per job, full detail (fetched on demand)
  - website-data/stats.json       real aggregate counts -- never hardcoded
  - website-data/companies.json   per-company summary

Never invents a field: every value here is either copied straight from
the job dict or computed by counting/aggregating real values.
"""

import json
import re
from pathlib import Path
from collections import Counter, defaultdict

OUTPUT_DIR = Path("website-data")

INDEX_FIELDS = [
    "company", "job_title", "job_id", "location_raw", "work_mode",
    "employment_type", "experience_raw", "salary_raw", "deadline_status",
    "application_deadline", "date_posted", "fresher_eligible", "internship",
    "cse_relevant", "status",
]


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "untitled"


def make_job_key(job: dict) -> str:
    """URL-safe unique key: company-title-jobid, matching spec's
    /jobs/company-title-id URL pattern (section 45)."""
    company = slugify(job.get("company", "company"))
    title = slugify(job.get("job_title", "role"))
    job_id = job.get("job_id") or "0"
    return f"{company}-{title}-{job_id}"


def build_index(jobs: list) -> list:
    index = []
    for job in jobs:
        entry = {f: job.get(f) for f in INDEX_FIELDS}
        entry["key"] = make_job_key(job)
        index.append(entry)
    return index


def write_job_details(jobs: list, jobs_dir: Path):
    jobs_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for job in jobs:
        key = make_job_key(job)
        (jobs_dir / f"{key}.json").write_text(
            json.dumps(job, indent=2, default=str), encoding="utf-8"
        )
        written += 1
    return written


def build_stats(jobs: list) -> dict:
    return {
        "total_jobs": len(jobs),
        "new_jobs": sum(1 for j in jobs if j.get("status") == "NEW"),
        "companies": len(set(j.get("company") for j in jobs)),
        "fresher_opportunities": sum(1 for j in jobs if j.get("fresher_eligible")),
        "internships": sum(1 for j in jobs if j.get("internship")),
        "cse_jobs": sum(1 for j in jobs if j.get("cse_relevant")),
        "closing_soon": sum(1 for j in jobs if j.get("deadline_status") == "Closing Soon"),
        "jobs_with_salary_disclosed": sum(
            1 for j in jobs if j.get("salary_raw") not in (None, "Not disclosed")
        ),
    }


def build_companies(jobs: list) -> list:
    by_company = defaultdict(list)
    for job in jobs:
        by_company[job.get("company", "Unknown")].append(job)

    result = []
    for company, company_jobs in sorted(by_company.items()):
        result.append({
            "company": company,
            "active_jobs": len(company_jobs),
            "fresher_jobs": sum(1 for j in company_jobs if j.get("fresher_eligible")),
            "internships": sum(1 for j in company_jobs if j.get("internship")),
            "cse_jobs": sum(1 for j in company_jobs if j.get("cse_relevant")),
            "career_website": next(
                (j.get("source_website") for j in company_jobs if j.get("source_website")), None
            ),
        })
    return result


def generate(jobs_json_path="output/ats_jobs.json", output_dir=OUTPUT_DIR):
    jobs = json.loads(Path(jobs_json_path).read_text(encoding="utf-8"))
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    index = build_index(jobs)
    (output_dir / "index.json").write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")

    detail_count = write_job_details(jobs, output_dir / "jobs")

    stats = build_stats(jobs)
    (output_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    companies = build_companies(jobs)
    (output_dir / "companies.json").write_text(json.dumps(companies, indent=2, default=str), encoding="utf-8")

    return {
        "index_entries": len(index),
        "detail_files": detail_count,
        "stats": stats,
        "companies": len(companies),
    }


if __name__ == "__main__":
    import tempfile
    import shutil

    sample_jobs = [
        {"company": "Stripe", "job_title": "Software Engineer", "job_id": "1", "location_raw": "SF",
         "work_mode": "Hybrid", "employment_type": "Full-time", "experience_raw": "2-4 years",
         "salary_raw": "Not disclosed", "deadline_status": "Open", "application_deadline": None,
         "date_posted": "2026-09-01", "fresher_eligible": None, "internship": None,
         "cse_relevant": True, "status": "NEW", "source_website": "boards.greenhouse.io/stripe",
         "job_description": "Full description text here."},
        {"company": "Stripe", "job_title": "SDE Intern", "job_id": "2", "location_raw": "NYC",
         "work_mode": "Remote", "employment_type": "Internship", "experience_raw": "0 years",
         "salary_raw": "Not disclosed", "deadline_status": "Closing Soon", "application_deadline": "2026-10-01",
         "date_posted": "2026-09-10", "fresher_eligible": True, "internship": True,
         "cse_relevant": True, "status": "UNCHANGED", "source_website": "boards.greenhouse.io/stripe",
         "job_description": "Intern description text here."},
        {"company": "Anthropic", "job_title": "Sales Manager", "job_id": "3", "location_raw": "Remote",
         "work_mode": "Remote", "employment_type": "Full-time", "experience_raw": "5+ years",
         "salary_raw": "$150K-$200K", "deadline_status": "Deadline Not Specified", "application_deadline": None,
         "date_posted": "2026-09-05", "fresher_eligible": None, "internship": None,
         "cse_relevant": False, "status": "NEW", "source_website": "boards.greenhouse.io/anthropic",
         "job_description": "Sales role description."},
    ]

    tmp_dir = Path(tempfile.mkdtemp())
    jobs_path = tmp_dir / "ats_jobs.json"
    jobs_path.write_text(json.dumps(sample_jobs), encoding="utf-8")
    out_dir = tmp_dir / "website-data"

    result = generate(jobs_path, out_dir)
    print("generate() returned:", result)

    assert result["index_entries"] == 3, f"FAIL: expected 3 index entries, got {result['index_entries']}"
    assert result["detail_files"] == 3, f"FAIL: expected 3 detail files, got {result['detail_files']}"
    assert result["stats"]["total_jobs"] == 3
    assert result["stats"]["cse_jobs"] == 2, f"FAIL: expected 2 CSE jobs, got {result['stats']['cse_jobs']}"
    assert result["stats"]["fresher_opportunities"] == 1
    assert result["stats"]["closing_soon"] == 1
    assert result["companies"] == 2, f"FAIL: expected 2 companies, got {result['companies']}"

    index_data = json.loads((out_dir / "index.json").read_text())
    assert "job_description" not in index_data[0], "FAIL: index.json should NOT contain full descriptions (keep it light)"
    print("PASS: index.json is lightweight (no descriptions)")

    detail_files = list((out_dir / "jobs").glob("*.json"))
    assert len(detail_files) == 3, f"FAIL: expected 3 detail files on disk, got {len(detail_files)}"
    sample_detail = json.loads(detail_files[0].read_text())
    assert "job_description" in sample_detail, "FAIL: per-job detail file should contain the full description"
    print("PASS: per-job detail files contain full description")

    companies_data = json.loads((out_dir / "companies.json").read_text())
    stripe_entry = next(c for c in companies_data if c["company"] == "Stripe")
    assert stripe_entry["active_jobs"] == 2, f"FAIL: Stripe should show 2 active jobs, got {stripe_entry['active_jobs']}"
    print("PASS: per-company counts are correct")

    shutil.rmtree(tmp_dir)
    print("\nALL SELF-TESTS PASSED")
