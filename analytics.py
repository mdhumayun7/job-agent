import json
from collections import Counter, defaultdict
from pathlib import Path

from config import ANALYTICS_OUTPUT_FILE, JOBS_FILE


def load_jobs():
    with open(JOBS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def build_analytics(jobs):
    source_counter = Counter()
    city_counter = Counter()
    company_counter = Counter()
    skill_counter = Counter()
    status_counter = Counter()
    salary_jobs = []
    source_score_totals = defaultdict(list)

    for job in jobs:
        source = job.get("source_group") or job.get("source") or "Other"
        location = job.get("location") or "Unknown"
        company = job.get("company") or "Unknown"
        status = job.get("status") or "Saved"
        score = job.get("match_score", 0)
        source_counter[source] += 1
        city_counter[location] += 1
        company_counter[company] += 1
        status_counter[status] += 1
        source_score_totals[source].append(score)

        for skill in job.get("matched_skills", []):
            skill_counter[skill] += 1

        salary = (job.get("salary") or "").strip()
        if salary:
            salary_jobs.append(
                {
                    "title": job.get("title", ""),
                    "company": company,
                    "salary": salary,
                    "source": source,
                    "apply_url": job.get("apply_url", ""),
                }
            )

    best_sources = []
    for source, scores in source_score_totals.items():
        avg_score = round(sum(scores) / max(1, len(scores)), 2)
        best_sources.append({"source": source, "average_score": avg_score, "jobs": len(scores)})
    best_sources.sort(key=lambda item: (-item["average_score"], -item["jobs"]))

    return {
        "total_jobs": len(jobs),
        "sources": dict(source_counter.most_common()),
        "top_cities": [{"city": city, "jobs": count} for city, count in city_counter.most_common(10)],
        "top_companies": [{"company": company, "jobs": count} for company, count in company_counter.most_common(10)],
        "top_skills": [{"skill": skill, "jobs": count} for skill, count in skill_counter.most_common(15)],
        "status_breakdown": dict(status_counter.most_common()),
        "best_sources": best_sources[:10],
        "salary_jobs": salary_jobs[:20],
    }


def save_analytics(summary):
    output_path = Path(ANALYTICS_OUTPUT_FILE)
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
    print(f"Analytics saved: {output_path}")


def main():
    jobs = load_jobs()
    summary = build_analytics(jobs)
    save_analytics(summary)


if __name__ == "__main__":
    main()
