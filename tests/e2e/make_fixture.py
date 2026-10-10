"""
Test-only company data for the browser tests. Writes clearly fake jobs
(example.com links, "Test Co" names) to tests/e2e/.fixture_ats_jobs.json, then
builds website-data/ from it. Never used for the deployed site.
Usage: python tests/e2e/make_fixture.py && python scripts/build_govt_data.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TITLES = ["SDE Intern", "Backend Developer", "Data Analyst", "Senior Staff Engineer", "ML Engineer", "Frontend Developer"]
CITIES = ["Hyderabad, India", "Bengaluru, India", "Remote - India", "Berlin, Germany", "Pune, India"]
COMPANIES = ["Sample Labs", "Acme Test Co", "Example Systems"]
jobs = []
for i in range(60):
    title = TITLES[i % len(TITLES)]
    city = CITIES[i % len(CITIES)]
    intern = "Intern" in title
    senior = "Senior" in title
    scope = "Remote-India" if city.startswith("Remote") else ("India" if "India" in city else "Other")
    jobs.append({
        "company": COMPANIES[i % len(COMPANIES)], "job_title": title, "job_id": str(1000 + i), "location_raw": city,
        # The <img onerror> payload checks that descriptions are sanitised.
        "job_description": "<p>Python, SQL, Docker. 0-2 years experience.</p><img src=x onerror=alert(1)>",
        "apply_url": f"https://example.com/jobs/{i}", "job_url": f"https://example.com/jobs/{i}",
        "status": "NEW" if i % 4 == 0 else "ACTIVE", "cse_relevant": i % 7 != 0,
        "date_posted": f"2026-10-{1 + i % 9:02d}", "first_seen": f"2026-10-{1 + i % 9:02d}", "source_website": "example.com",
        "employment_type": "Internship" if intern else "Full-time", "fresher_eligible": not senior, "country_scope": scope,
        "seniority": "Intern" if intern else ("Senior" if senior else "Entry"), "internship": intern,
        "skills_required": ["python", "sql", "docker"], "match_score": 40 + i % 50, "match_reasons": ["test fixture"],
    })
out = ROOT / "tests" / "e2e" / ".fixture_ats_jobs.json"
out.write_text(json.dumps(jobs), encoding="utf-8")
subprocess.run([sys.executable, str(ROOT / "generate_website_data.py"), "--input", str(out), "--out", str(ROOT / "website-data")], check=True)
print(f"fixture: {len(jobs)} fake company jobs")
