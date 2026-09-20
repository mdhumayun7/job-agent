"""
Extraction parsers. Every function takes raw job text and returns either
a real value pulled from that text, or None / "Not specified" -- never
a guess. Each function is independently testable (see tests below).
"""

import re
from job_schema import NOT_SPECIFIED, NOT_DISCLOSED

CSE_KEYWORDS = [
    "software engineer", "software developer", "software development engineer",
    "development engineer", "sde", "sdet",
    "backend", "frontend", "full stack", "fullstack", "web developer",
    "application developer", "mobile developer", "android developer", "ios developer",
    "machine learning", "ml engineer", "ai engineer", "data scientist",
    "data analyst", "data engineer", "deep learning", "nlp engineer",
    "computer vision", "generative ai", "research engineer", "applied scientist",
    "cybersecurity", "security engineer", "soc analyst", "security analyst",
    "penetration tester", "information security",
    "cloud engineer", "devops", "site reliability", "sre", "platform engineer",
    "infrastructure engineer", "kubernetes",
    "systems engineer", "network engineer", "database engineer",
    "distributed systems", "embedded software", "firmware engineer",
    "compiler engineer", "operating systems engineer",
    "blockchain developer", "web3", "mlops", "qa automation", "test engineer",
]

FRESHER_PATTERNS = [
    r"\b0\s*[-–—]\s*\d\s*years?\b", r"\b0\s*to\s*\d\s*years?\b",
    r"\bfresher(s)?\b", r"\bentry[\s-]level\b", r"\bnew grad(uate)?s?\b",
    r"\bcampus hir(e|ing)\b", r"\bgraduate program\b", r"\btrainee\b", r"\bapprentice\b",
]

INTERNSHIP_PATTERNS = [r"\bintern(ship)?\b", r"\bco-op\b"]

EXPERIENCE_RANGE_RE = re.compile(
    r"(\d+)\s*[-–—to]{1,4}\s*(\d+)\s*\+?\s*years?", re.IGNORECASE
)
EXPERIENCE_PLUS_RE = re.compile(r"(\d+)\s*\+\s*years?", re.IGNORECASE)
EXPERIENCE_MIN_ONLY_RE = re.compile(r"\bminimum\s*(\d+)\s*years?", re.IGNORECASE)

SALARY_RE = re.compile(
    r"(₹|Rs\.?|INR)\s?([\d,]+(?:\.\d+)?)\s?(LPA|lakhs?)|"
    r"(\$|USD)\s?([\d,]+(?:\.\d+)?)\s?(K|k)?|"
    r"(₹|Rs\.?|INR)\s?([\d,]+)\s?[-–—]\s?(₹|Rs\.?|INR)?\s?([\d,]+)\s?(LPA|lakhs?)",
    re.IGNORECASE
)

DEGREE_KEYWORDS = {
    "B.Tech": [r"\bb\.?\s?tech\b"],
    "B.E.": [r"\bb\.?\s?e\.?\b(?!\w)"],
    "M.Tech": [r"\bm\.?\s?tech\b"],
    "MCA": [r"\bmca\b"],
    "BCA": [r"\bbca\b"],
    "M.Sc": [r"\bm\.?\s?sc\b"],
    "B.Sc": [r"\bb\.?\s?sc\b"],
    "PhD": [r"\bph\.?d\b"],
}

BRANCH_KEYWORDS = {
    "Computer Science": [r"computer science", r"\bcse\b"],
    "Information Technology": [r"information technology", r"\bit\b(?!\w)"],
    "Data Science": [r"data science"],
    "Artificial Intelligence": [r"artificial intelligence", r"\bai\b(?!\w)"],
    "Electronics": [r"electronics"],
    "Related technical field": [r"related (technical )?field", r"or equivalent"],
}


def detect_cse_relevance(title: str, description: str):
    """Returns (is_relevant: bool, evidence: str|None).

    Checks the TITLE only, not the full description. Full-text matching
    was tried first and produced false positives (e.g. "Abuse Investigator"
    matched because the description mentioned "our engineering team" in
    unrelated boilerplate). A role's title is what its function actually
    is; incidental mentions of "engineer" elsewhere in the posting are not
    evidence the role itself is CSE-relevant.
    """
    text = title.lower()
    for kw in CSE_KEYWORDS:
        if kw in text:
            return True, kw
    return False, None


def detect_fresher_eligible(description: str):
    text = description.lower()
    for pattern in FRESHER_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return True, m.group(0)
    return False, None


def detect_internship(title: str, description: str):
    text = f"{title} {description}".lower()
    for pattern in INTERNSHIP_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return True, m.group(0)
    return False, None


def extract_experience(description: str):
    """Returns dict: experience_min, experience_max, experience_raw."""
    m = EXPERIENCE_RANGE_RE.search(description)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return {"experience_min": lo, "experience_max": hi, "experience_raw": m.group(0)}
    m = EXPERIENCE_PLUS_RE.search(description)
    if m:
        lo = int(m.group(1))
        return {"experience_min": lo, "experience_max": None, "experience_raw": m.group(0)}
    m = EXPERIENCE_MIN_ONLY_RE.search(description)
    if m:
        lo = int(m.group(1))
        return {"experience_min": lo, "experience_max": None, "experience_raw": m.group(0)}
    if re.search(r"\bfresher(s)?\b|\bentry[\s-]level\b", description, re.IGNORECASE):
        return {"experience_min": 0, "experience_max": None, "experience_raw": NOT_SPECIFIED}
    return {"experience_min": None, "experience_max": None, "experience_raw": NOT_SPECIFIED}


def extract_salary(description: str):
    """Returns dict: salary_raw, currency, salary_min, salary_max.
    NEVER guesses -- if no explicit figure is in the text, returns
    'Not disclosed' for everything."""
    m = SALARY_RE.search(description)
    if not m:
        return {"salary_raw": NOT_DISCLOSED, "currency": None, "salary_min": None, "salary_max": None}
    raw = m.group(0)
    currency = "INR" if any(c in raw for c in ("₹", "Rs", "INR", "LPA", "lakh")) else "USD"
    numbers = re.findall(r"[\d,]+(?:\.\d+)?", raw)
    numbers = [float(n.replace(",", "")) for n in numbers]
    if len(numbers) >= 2:
        return {"salary_raw": raw, "currency": currency, "salary_min": min(numbers), "salary_max": max(numbers)}
    if len(numbers) == 1:
        return {"salary_raw": raw, "currency": currency, "salary_min": numbers[0], "salary_max": numbers[0]}
    return {"salary_raw": raw, "currency": currency, "salary_min": None, "salary_max": None}


def extract_degree(description: str):
    found = []
    for degree, patterns in DEGREE_KEYWORDS.items():
        if any(re.search(p, description, re.IGNORECASE) for p in patterns):
            found.append(degree)
    return found


def extract_branch(description: str):
    found = []
    for branch, patterns in BRANCH_KEYWORDS.items():
        if any(re.search(p, description, re.IGNORECASE) for p in patterns):
            found.append(branch)
    return found


def enrich_job(job: dict) -> dict:
    """Takes a raw Job dict (from an adapter) and fills in the
    extraction fields in place. Never overwrites job_url/company/etc --
    only adds/fills the classification and eligibility fields."""
    title = job.get("job_title", "")
    desc = job.get("job_description", "") or ""

    cse, cse_evidence = detect_cse_relevance(title, desc)
    fresher, fresher_evidence = detect_fresher_eligible(desc)
    internship, _ = detect_internship(title, desc)

    job["cse_relevant"] = cse
    job["cse_relevance_evidence"] = cse_evidence
    job["fresher_eligible"] = fresher if fresher else None
    job["internship"] = internship if internship else None
    job.update(extract_experience(desc))
    job.update(extract_salary(desc))
    job["education_required"] = extract_degree(desc)
    job["branch_required"] = extract_branch(desc)

    return job


if __name__ == "__main__":
    # Self-tests with known inputs -- run this before trusting the module.
    tests_passed = 0
    tests_failed = 0

    def check(label, actual, expected):
        global tests_passed, tests_failed
        ok = actual == expected
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got {actual!r}" + ("" if ok else f", expected {expected!r}"))
        tests_passed += ok
        tests_failed += not ok

    print("Running parser self-tests...\n")

    check("cse: SDE title", detect_cse_relevance("Software Development Engineer", "")[0], True)
    check("cse: sales role", detect_cse_relevance("Regional Sales Manager", "drives revenue")[0], False)
    check("cse: non-eng title with eng boilerplate in body",
          detect_cse_relevance("Abuse Investigator",
                                "You'll partner closely with our engineering team and software platform to review cases.")[0],
          False)

    check("fresher: 0-2 years", detect_fresher_eligible("Looking for candidates with 0-2 years experience")[0], True)
    check("fresher: senior role", detect_fresher_eligible("Minimum 8 years of experience required")[0], False)

    check("experience range", extract_experience("Requires 2-4 years of experience"),
          {"experience_min": 2, "experience_max": 4, "experience_raw": "2-4 years"})

    check("salary LPA", extract_salary("Compensation: ₹6-10 LPA")["currency"], "INR")
    check("salary not disclosed", extract_salary("Great team culture and benefits")["salary_raw"], NOT_DISCLOSED)

    check("degree B.Tech", "B.Tech" in extract_degree("Requires B.Tech or equivalent degree"), True)
    check("branch CSE", "Computer Science" in extract_branch("Computer Science and Engineering preferred"), True)

    print(f"\n{tests_passed} passed, {tests_failed} failed")
