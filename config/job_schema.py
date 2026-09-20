"""
Canonical Job data model.

Every scraper/adapter must return dicts matching this shape.
Fields with no source-supported value MUST be None (for numeric/date fields)
or "Not specified" / "Not disclosed" (for text fields) -- never guessed.
See config/companies.json for the per-company source configuration.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime

NOT_SPECIFIED = "Not specified"
NOT_DISCLOSED = "Not disclosed"


@dataclass
class Job:
    # Identity
    company: str
    job_title: str
    job_id: Optional[str] = None
    requisition_id: Optional[str] = None
    job_url: str = ""
    apply_url: str = ""

    # Location
    location_raw: str = NOT_SPECIFIED
    city: Optional[str] = None
    state_region: Optional[str] = None
    country: Optional[str] = None
    work_mode: str = NOT_SPECIFIED  # Remote / Hybrid / On-site / Not specified

    # Role
    employment_type: str = NOT_SPECIFIED  # Full-time / Internship / Contract / ...
    technology_domain: str = NOT_SPECIFIED

    # Dates
    date_posted: Optional[str] = None      # ISO 8601 if known
    last_updated: Optional[str] = None
    application_deadline: Optional[str] = None
    deadline_status: str = "Deadline Not Specified"  # Open/Closing Soon/Deadline Passed/Deadline Not Specified/Unknown

    # Compensation
    salary_raw: str = NOT_DISCLOSED
    currency: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None

    # Eligibility
    experience_raw: str = NOT_SPECIFIED
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None
    education_required: List[str] = field(default_factory=list)
    branch_required: List[str] = field(default_factory=list)
    branch_relation: str = "Not Specified"  # Required/Preferred/Related/Not Specified
    graduation_year: Optional[str] = None
    eligibility_criteria: List[str] = field(default_factory=list)

    # Skills
    skills_required: List[str] = field(default_factory=list)
    skills_preferred: List[str] = field(default_factory=list)

    # Content
    job_description: str = ""

    # Classification flags -- every one of these MUST be backed by
    # something found in job_description / eligibility_criteria.
    fresher_eligible: Optional[bool] = None
    internship: Optional[bool] = None
    graduate_role: Optional[bool] = None
    entry_level: Optional[bool] = None
    trainee: Optional[bool] = None
    apprentice: Optional[bool] = None
    cse_relevant: Optional[bool] = None
    cse_relevance_evidence: Optional[str] = None  # the phrase that justified the flag above

    # Provenance -- required for every record
    source_website: str = ""
    source_type: str = ""       # "greenhouse_api" / "lever_api" / "custom_scraper" / "unsupported"
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "NEW"         # NEW / UPDATED / UNCHANGED / CLOSED
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def unique_key(job: dict) -> str:
    """Company + Job ID is the preferred dedup key; falls back to
    company + normalized title + normalized location."""
    company = (job.get("company") or "").strip().lower()
    job_id = job.get("job_id")
    if job_id:
        return f"{company}::{job_id}"
    title = "".join(ch for ch in (job.get("job_title") or "").lower() if ch.isalnum() or ch == " ").strip()
    loc = "".join(ch for ch in (job.get("location_raw") or "").lower() if ch.isalnum())
    return f"{company}::{title}::{loc}"
