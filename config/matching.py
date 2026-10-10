"""
Job classification and personal match scoring.

Adds to every job dict:
  country_scope     India | Remote-India | Remote | Abroad | Unknown
  seniority         Intern | Entry | Mid | Senior | Unknown        (from the title)
  skills_required   canonical skills found in title + description
  fresher_eligible  True / False / None -- refined using seniority and experience
  match_score       0-100 against config/profile.json
  match_reasons     human-readable list explaining the score

Rules are deterministic and every flag is backed by text in the posting;
nothing is guessed. Unknown stays None / "Unknown".
"""

import json
import re
from datetime import date, datetime
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parent / "profile.json"

INDIA_CITIES = [
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "mumbai", "navi mumbai",
    "gurgaon", "gurugram", "noida", "new delhi", "delhi", "kolkata", "ahmedabad", "kochi", "cochin",
    "trivandrum", "thiruvananthapuram", "coimbatore", "mysore", "mysuru", "jaipur", "chandigarh",
    "mohali", "vadodara", "surat", "nagpur", "indore", "bhubaneswar", "visakhapatnam", "vizag",
    "lucknow", "goa", "panjim", "mangalore", "madurai", "karnataka", "telangana", "maharashtra",
    "tamil nadu", "haryana", "uttar pradesh", "gujarat", "kerala", "west bengal", "rajasthan",
]
INDIA_RE = re.compile(r"\b(" + "|".join(re.escape(c) for c in INDIA_CITIES) + r")\b|(?-i:\bIND\b)", re.I)
REMOTE_RE = re.compile(r"\bremote\b|\bwork from home\b|\banywhere\b", re.I)

SENIOR_RE = re.compile(r"\b(senior|sr\.?|staff|principal|principle|lead|manager|director|head|vp|vice president|"
                       r"architect|distinguished|fellow|expert|specialist ii+|engineer i{2,}|iii|iv|"
                       r"l[5-9]\b|ic[4-9]\b|level [3-9])\b", re.I)
STRONG_ENTRY_RE = re.compile(r"\b(new grad(uate)?s?|graduate|fresher|freshers|trainee|apprentice|campus|"
                             r"university grad|entry[\s-]level|early career|career accelerator)\b", re.I)
MID_RE = re.compile(r"\b(sde|engineer|developer|scientist|analyst|consultant|specialist)[\s-]*(ii|2)\b|"
                    r"\b(level|grade)\s*2\b|\bmid[\s-]level\b", re.I)
ENTRY_RE = re.compile(r"\b(junior|jr\.?|associate|graduate|new grad|fresher|trainee|apprentice|entry[\s-]level|"
                      r"engineer i\b|sde[\s-]?(i|1)\b|developer i\b|analyst i\b|early career|campus|"
                      r"career accelerator|university)\b", re.I)
INTERN_RE = re.compile(r"\bintern(ship)?s?\b|\bco-op\b|\bsummer analyst\b", re.I)

# canonical skill -> regex (word-bounded; tuned to avoid substrings like "go" in "good")
SKILLS = {
    "python": r"\bpython\b", "java": r"\bjava\b(?!script)", "c++": r"c\+\+", "c#": r"c#|\.net\b",
    "golang": r"\bgolang\b|\bgo\s+(language|lang)\b", "rust": r"\brust\b", "javascript": r"\bjavascript\b|\bjs\b",
    "typescript": r"\btypescript\b", "react": r"\breact(\.js|js)?\b", "node.js": r"\bnode(\.js|js)\b",
    "angular": r"\bangular\b", "flask": r"\bflask\b", "django": r"\bdjango\b", "fastapi": r"\bfastapi\b",
    "spring": r"\bspring( boot)?\b", "sql": r"\bsql\b|\bmysql\b|\bpostgres(ql)?\b", "nosql": r"\bnosql\b|\bmongodb\b",
    "machine learning": r"\bmachine learning\b|\bml\b", "deep learning": r"\bdeep learning\b",
    "pytorch": r"\bpytorch\b", "tensorflow": r"\btensorflow\b", "scikit-learn": r"\bscikit[- ]learn\b|\bsklearn\b",
    "computer vision": r"\bcomputer vision\b", "opencv": r"\bopencv\b", "nlp": r"\bnlp\b|natural language processing",
    "llm": r"\bllms?\b|large language model", "generative ai": r"\bgen(erative)?\s?ai\b",
    "pandas": r"\bpandas\b", "numpy": r"\bnumpy\b", "spark": r"\b(apache )?spark\b", "kafka": r"\bkafka\b",
    "aws": r"\baws\b|amazon web services", "azure": r"\bazure\b", "gcp": r"\bgcp\b|google cloud",
    "docker": r"\bdocker\b", "kubernetes": r"\bkubernetes\b|\bk8s\b", "terraform": r"\bterraform\b",
    "linux": r"\blinux\b|\bunix\b", "git": r"\bgit\b", "ci/cd": r"\bci/?cd\b|\bjenkins\b",
    "microservices": r"\bmicroservices?\b", "rest api": r"\brest(ful)?\s?apis?\b",
    "data structures": r"\bdata structures?\b", "algorithms": r"\balgorithms?\b",
    "networking": r"\bnetworking\b|\btcp/ip\b", "network security": r"\bnetwork security\b|\bfirewalls?\b",
    "cybersecurity": r"\bcyber\s?security\b|\binformation security\b|\binfosec\b",
    "intrusion detection": r"\bintrusion detection\b|\bids/ips\b|\bsiem\b", "cryptography": r"\bcryptograph",
    "embedded c": r"\bembedded\b", "verilog": r"\bverilog\b|\bsystemverilog\b", "rtos": r"\brtos\b",
    "selenium": r"\bselenium\b", "tableau": r"\btableau\b|\bpower ?bi\b",
}
SKILL_RES = {k: re.compile(v, re.I) for k, v in SKILLS.items()}

_profile_cache = None


def load_profile(path=PROFILE_PATH):
    global _profile_cache
    if _profile_cache is None:
        _profile_cache = json.loads(Path(path).read_text(encoding="utf-8"))
    return _profile_cache


def _strip_html(text):
    return re.sub(r"<[^>]+>", " ", text or "")


GLOBAL_REMOTE_RE = re.compile(r"\b(anywhere|global|worldwide|apac|asia)\b", re.I)
N_LOCATIONS_RE = re.compile(r"^\s*\d+\s+locations?\s*$", re.I)


def classify_location(job):
    loc = " ".join(str(job.get(k) or "") for k in ("location_raw", "city", "state_region", "country"))
    work_mode = str(job.get("work_mode") or "")
    india = bool(INDIA_RE.search(loc))
    remote = bool(REMOTE_RE.search(loc) or REMOTE_RE.search(work_mode))
    if india and remote:
        return "Remote-India"
    if india:
        return "India"
    raw = str(job.get("location_raw") or "").strip()
    if remote:
        # "United States - Remote" is remote *within another country*.
        rest = re.sub(r"remote|work from home|[-,;/()|\s]+", " ", raw, flags=re.I).strip()
        if not rest or GLOBAL_REMOTE_RE.search(rest):
            return "Remote"
        return "Abroad"
    if not raw or raw.lower() in ("not specified", "none") or N_LOCATIONS_RE.match(raw):
        return "Unknown"
    return "Abroad"


def classify_seniority(title):
    t = title or ""
    if INTERN_RE.search(t):
        return "Intern"
    if STRONG_ENTRY_RE.search(t):  # "Associate Product Manager (New Grad)" is entry-level
        return "Entry"
    if SENIOR_RE.search(t):  # before weak entry words so "Associate Director" is senior
        return "Senior"
    if MID_RE.search(t):
        return "Mid"
    if ENTRY_RE.search(t):
        return "Entry"
    return "Unknown"


def extract_skills(title, description):
    text = f"{title or ''} {_strip_html(description)}"
    return [k for k, rx in SKILL_RES.items() if rx.search(text)]


def refine_fresher(job, seniority):
    """Returns (value, evidence). True only with explicit evidence; False
    when the title or stated experience rules a fresher out; else None."""
    # The title states what the role is; it outranks incidental description text.
    if seniority in ("Intern", "Entry"):
        return True, f"{seniority.lower()}-level title"
    if seniority == "Senior":
        return False, "senior-level title"
    if seniority == "Mid":
        return False, "level II / mid-level title"
    exp_min, exp_max = job.get("experience_min"), job.get("experience_max")
    if exp_min is not None and exp_min >= 3:
        return False, f"requires {exp_min}+ years"
    if job.get("fresher_eligible"):
        return True, "fresher wording in description"
    if exp_min is not None and exp_min <= 1 and (exp_max is None or exp_max <= 3):
        return True, f"experience {job.get('experience_raw')}"
    return None, None


def _days_old(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00")[:25]).date()
    except ValueError:
        try:
            d = date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
    return (date.today() - d).days


def score_job(job, profile=None):
    p = profile or load_profile()
    title = (job.get("job_title") or "").lower()
    reasons, score = [], 0

    if any(k in title for k in p.get("exclude_title_keywords", [])):
        return 0, ["excluded role type (title)"]

    if job.get("cse_relevant"):
        score += 25
        reasons.append("CSE/IT role")
    role = next((r for r in p.get("target_roles", []) if r in title), None)
    if role:
        score += 20
        reasons.append(f"target role: {role}")

    weights = p.get("skills", {})
    matched = [s for s in job.get("skills_required") or [] if s in weights]
    if matched:
        pts = min(25, sum(weights[s] for s in matched))
        score += pts
        reasons.append("skills: " + ", ".join(matched[:6]))

    seniority = job.get("seniority")
    if job.get("internship"):
        if p.get("accept_internships", True):
            score += 15
            reasons.append("internship")
    elif job.get("fresher_eligible") is True:
        score += 15
        reasons.append("fresher / entry level")
    elif seniority == "Mid":
        score -= 15
        reasons.append("mid-level (II) role")
    elif job.get("fresher_eligible") is False or seniority == "Senior":
        score -= 30
        reasons.append("needs experience")

    scope = job.get("country_scope")
    prefs = p.get("preferred_locations", [])
    if scope in prefs:
        score += 10
        reasons.append(f"location: {scope}")
    elif scope == "Remote":
        score += 3
    elif scope == "Abroad" and prefs:
        score -= 25
        reasons.append("outside India")

    age = _days_old(job.get("date_posted"))
    if age is not None and age <= 7:
        score += 5
        reasons.append("posted this week")

    return max(0, min(100, score)), reasons


def apply_matching(job, profile=None):
    title = job.get("job_title") or ""
    desc = job.get("job_description") or ""
    job["country_scope"] = classify_location(job)
    job["seniority"] = classify_seniority(title)
    if job.get("experience_min") is None:
        try:
            from parsers import extract_experience
            exp = extract_experience(title)
            if exp.get("experience_min") is not None:
                job.update(exp)
        except ImportError:
            pass
    # Internship is decided by the title / employment type only; a description
    # that merely mentions an internship programme does not make a role one.
    job["internship"] = bool(job["seniority"] == "Intern"
                             or re.search(r"intern", str(job.get("employment_type") or ""), re.I)) or None
    if not job.get("skills_required"):
        job["skills_required"] = extract_skills(title, desc)
    fresher, evidence = refine_fresher(job, job["seniority"])
    job["fresher_eligible"] = fresher
    job["fresher_evidence"] = evidence
    job["match_score"], job["match_reasons"] = score_job(job, profile)
    return job


def top_matches(jobs, profile=None, limit=None):
    p = profile or load_profile()
    threshold = p.get("top_match_threshold", 55)
    picked = [j for j in jobs if j.get("status") != "CLOSED" and (j.get("match_score") or 0) >= threshold]
    picked.sort(key=lambda j: (-(j.get("match_score") or 0), j.get("status") != "NEW", j.get("company") or ""))
    return picked[:limit] if limit else picked


def selftest():
    profile = {"target_roles": ["software engineer", "machine learning"], "skills": {"python": 4, "pytorch": 3},
               "preferred_locations": ["India", "Remote-India"], "accept_internships": True,
               "exclude_title_keywords": ["sales"], "top_match_threshold": 55}
    base = {"cse_relevant": True, "status": "NEW", "date_posted": date.today().isoformat()}

    j = apply_matching({**base, "job_title": "Software Engineer I", "location_raw": "Bengaluru, Karnataka, India",
                        "job_description": "Python and PyTorch. 0-2 years experience.", "fresher_eligible": True}, profile)
    assert j["country_scope"] == "India" and j["seniority"] == "Entry" and j["fresher_eligible"] is True, j
    assert {"python", "pytorch"} <= set(j["skills_required"]), j["skills_required"]
    assert j["match_score"] >= 80, j

    s = apply_matching({**base, "job_title": "Senior Staff Software Engineer", "location_raw": "San Francisco, CA",
                        "job_description": "Python. 8+ years"}, profile)
    assert s["seniority"] == "Senior" and s["fresher_eligible"] is False and s["country_scope"] == "Abroad", s
    assert s["match_score"] < 40, s

    r = apply_matching({**base, "job_title": "Software Engineer", "location_raw": "India Remote", "job_description": ""}, profile)
    assert r["country_scope"] == "Remote-India", r

    x = apply_matching({**base, "job_title": "Sales Development Representative", "location_raw": "Pune"}, profile)
    assert x["match_score"] == 0

    i = apply_matching({**base, "job_title": "Machine Learning Intern", "location_raw": "Hyderabad"}, profile)
    assert i["internship"] is True and i["seniority"] == "Intern" and i["match_score"] >= 55, i

    assert classify_location({"location_raw": "Bengaluru, IND-29, IND, 560035"}) == "India"
    assert classify_location({"location_raw": "Fort Wayne, IN"}) == "Abroad"  # Indiana, not India
    assert classify_seniority("Associate Director, Strategy") == "Senior"
    assert classify_seniority("Associate Software Engineer") == "Entry"
    assert extract_skills("Golang dev", "good communication") == ["golang"]
    assert "java" not in extract_skills("", "JavaScript only")
    assert classify_seniority("Associate Product Manager (New Grad)") == "Entry"
    assert classify_seniority("SDE II, Amazon Ads") == "Mid"
    assert classify_seniority("Data Scientist II-3") == "Mid"
    assert classify_seniority("Principle AI Research Engineer") == "Senior"
    assert classify_location({"location_raw": "United States - Remote"}) == "Abroad"
    assert classify_location({"location_raw": "Remote"}) == "Remote"
    assert classify_location({"location_raw": "2 Locations"}) == "Unknown"
    assert classify_location({"location_raw": "2 Locations", "country": "India"}) == "India"
    m = apply_matching({**base, "job_title": "Manager II, Risk", "location_raw": "Pune",
                        "job_description": "freshers welcome", "fresher_eligible": True}, profile)
    assert m["fresher_eligible"] is False, m
    t = apply_matching({**base, "job_title": "Software Engineer (5-7 years, Firmware)", "location_raw": "Pune",
                        "job_description": ""}, profile)
    assert t["experience_min"] == 5 and t["fresher_eligible"] is False, t
    d = apply_matching({**base, "job_title": "SDE", "location_raw": "Pune", "employment_type": "Full-time",
                        "job_description": "We also run an internship programme.", "internship": True}, profile)
    assert not d["internship"], d
    print("matching self-test passed")


if __name__ == "__main__":
    selftest()
