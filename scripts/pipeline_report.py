"""
Summarise a pipeline run (output/ats_jobs.json + output/company_run_stats.json)
into probe_results.json, for checking classification and scoring on real data.
"""

import json
import random
from collections import Counter
from pathlib import Path

jobs = json.loads(Path("output/ats_jobs.json").read_text(encoding="utf-8"))
stats = json.loads(Path("output/company_run_stats.json").read_text(encoding="utf-8"))
top = json.loads(Path("output/top_matches.json").read_text(encoding="utf-8"))
random.seed(7)


def brief(j):
    return {k: j.get(k) for k in ("match_score", "company", "job_title", "location_raw", "country_scope",
                                  "seniority", "fresher_eligible", "fresher_evidence", "internship",
                                  "skills_required", "match_reasons", "status", "date_posted")}


report = {
    "total": len(jobs),
    "status": Counter(j.get("status") for j in jobs),
    "country_scope": Counter(j.get("country_scope") for j in jobs),
    "seniority": Counter(j.get("seniority") for j in jobs),
    "fresher": Counter(str(j.get("fresher_eligible")) for j in jobs),
    "internship": sum(1 for j in jobs if j.get("internship")),
    "with_description": sum(1 for j in jobs if j.get("job_description")),
    "with_skills": sum(1 for j in jobs if j.get("skills_required")),
    "top_matches": len(top),
    "top_by_company": Counter(j["company"] for j in top).most_common(40),
    "company_stats": stats,
    "top_sample": [brief(j) for j in top[:60]],
    "india_sample": [brief(j) for j in random.sample([j for j in jobs if j.get("country_scope") == "India"], 25)],
    "abroad_sample": [brief(j) for j in random.sample([j for j in jobs if j.get("country_scope") == "Abroad"], 25)],
    "unknown_scope_sample": [brief(j) for j in jobs if j.get("country_scope") == "Unknown"][:25],
    "fresher_true_sample": [brief(j) for j in random.sample([j for j in jobs if j.get("fresher_eligible")],
                                                             min(30, sum(1 for j in jobs if j.get("fresher_eligible"))))],
}
Path("probe_results.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if not k.endswith("sample") and k != "company_stats"}, default=str))
