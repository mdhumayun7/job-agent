import json
import os
import re
import time
from pathlib import Path
from config import ENRICHED_OUTPUT_FILE, JOBS_FILE, PERSONAL_INFO, PROFILE_SUMMARY, YOUR_SKILLS

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
BATCH_SIZE = 5

def load_jobs():
    path = Path(JOBS_FILE)
    if not path.exists():
        print(f"Jobs file not found: {JOBS_FILE}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_profile():
    name = PERSONAL_INFO.get("name", "Candidate")
    exp  = PERSONAL_INFO.get("experience", "0")
    return f"Name: {name}\nExperience: {exp} years\nSkills: {', '.join(YOUR_SKILLS)}\nProfile: {PROFILE_SUMMARY}"

def enrich_batch_groq(jobs_batch):
    try:
        import urllib.request
        profile = build_profile()
        jobs_text = ""
        for i, job in enumerate(jobs_batch):
            desc = (job.get("description") or job.get("title",""))[:300]
            jobs_text += f"Job {i+1}:\n  Title: {job.get('title','')}\n  Company: {job.get('company','')}\n  Location: {job.get('location','')}\n  Description: {desc}\n  Salary: {job.get('salary','Not mentioned')}\n\n"

        prompt = f"""Analyze these jobs for this candidate and return JSON array.

CANDIDATE:
{profile}

JOBS:
{jobs_text}

Return JSON array with one object per job:
- ai_match_score: integer 0-100
- fit_reason: string (1-2 sentences)
- matched_skills: array of strings
- missing_skills: array of strings
- cover_letter_opening: string (1 sentence)
- interview_difficulty: "Easy", "Medium", or "Hard"
- interview_focus_topics: array of 4 strings
- urgency: "High", "Normal", or "Low"
- growth_potential: "High", "Medium", or "Low"

Respond ONLY with valid JSON array. No markdown."""

        payload = json.dumps({
            "model": "llama3-8b-8192",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        raw = data["choices"][0]["message"]["content"].strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)
        if isinstance(result, list) and len(result) == len(jobs_batch):
            return result
        return []
    except Exception as e:
        print(f"  Groq error: {e}")
        return []

def enrich_fallback(job):
    title = job.get("title", "")
    text  = f"{title} {job.get('description', '')}".lower()
    matched = [s for s in YOUR_SKILLS if s.lower() in text]
    missing = [s for s in ["python","sql","react","aws","docker","git","linux"] if s in text and s not in [m.lower() for m in matched]][:4]
    score = min(100, job.get("match_score", 0) + len(matched) * 8)
    urgency = "High" if any(w in text for w in ["urgent","immediate","walk-in"]) else "Normal"
    return {
        "ai_match_score": score,
        "fit_reason": f"Matches {len(matched)} skills: {', '.join(matched[:3])}." if matched else "Relevant opportunity.",
        "matched_skills": matched,
        "missing_skills": missing,
        "cover_letter_opening": f"I am excited to apply for the {title} role at {job.get('company','')}, where my skills in {', '.join(matched[:2]) if matched else 'software development'} align well.",
        "interview_difficulty": "Medium" if score >= 50 else "Easy",
        "interview_focus_topics": matched[:4] or ["DSA","OOPs","SQL","System Design"],
        "urgency": urgency,
        "growth_potential": "Medium",
        "enrichment_method": "keyword"
    }

def enrich_jobs(jobs, use_ai=True, top_n=100):
    print(f"\n{'='*50}")
    print(f"  Phase 2: Enrichment | {len(jobs)} jobs")
    print(f"  Mode: {'Groq AI' if use_ai and GROQ_API_KEY else 'Keyword'}")
    print(f"{'='*50}\n")

    use_ai = use_ai and bool(GROQ_API_KEY)
    sorted_jobs = sorted(jobs, key=lambda j: j.get("match_score",0), reverse=True)
    ai_jobs  = sorted_jobs[:top_n] if use_ai else []
    kw_jobs  = sorted_jobs[top_n:] if use_ai else sorted_jobs

    results = []

    if ai_jobs:
        print(f"  AI enriching top {len(ai_jobs)} jobs...")
        for i in range(0, len(ai_jobs), BATCH_SIZE):
            batch = ai_jobs[i:i+BATCH_SIZE]
            print(f"  Batch {i//BATCH_SIZE+1}: {len(batch)} jobs", end=" ... ")
            enrichments = enrich_batch_groq(batch)
            for j_idx, job in enumerate(batch):
                enriched = dict(job)
                if j_idx < len(enrichments):
                    enriched.update(enrichments[j_idx])
                    enriched["enrichment_method"] = "groq_ai"
                else:
                    enriched.update(enrich_fallback(job))
                enriched["profile_summary"] = PROFILE_SUMMARY
                results.append(enriched)
            print("done")
            if i + BATCH_SIZE < len(ai_jobs):
                time.sleep(1)

    for job in kw_jobs:
        enriched = dict(job)
        enriched.update(enrich_fallback(job))
        enriched["profile_summary"] = PROFILE_SUMMARY
        results.append(enriched)

    results.sort(key=lambda j: j.get("ai_match_score", j.get("match_score",0)), reverse=True)
    ai_count = sum(1 for j in results if j.get("enrichment_method")=="groq_ai")
    print(f"\n  Done! {len(results)} enriched ({ai_count} via Groq AI)")
    return results

def save_enriched(jobs):
    out = Path(ENRICHED_OUTPUT_FILE)
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {out}")

def main():
    jobs = load_jobs()
    if not jobs:
        print("No jobs found. Run main.py first.")
        return
    enriched = enrich_jobs(jobs, use_ai=True, top_n=100)
    save_enriched(enriched)

if __name__ == "__main__":
    main()
