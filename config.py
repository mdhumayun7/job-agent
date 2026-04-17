import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
RESUME_DIR = BASE_DIR / "resume"
BROWSER_DATA_DIR = BASE_DIR / "browser_data"


def _csv_env(name, default):
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


SEARCH_KEYWORDS = _csv_env(
    "SEARCH_KEYWORDS",
    [
        "python developer fresher",
        "machine learning fresher",
        "data scientist fresher",
        "software engineer fresher",
    ],
)
LOCATION = os.getenv("LOCATION", "India")
EXPERIENCE_YEARS = int(os.getenv("EXPERIENCE_YEARS", "0"))
MAX_JOBS_PER_SITE = int(os.getenv("MAX_JOBS_PER_SITE", "50"))
MIN_SALARY_LPA = int(os.getenv("MIN_SALARY_LPA", "0"))
YOUR_SKILLS = _csv_env(
    "YOUR_SKILLS",
    ["python", "tensorflow", "opencv", "pandas", "numpy", "react", "flask", "git", "linux"],
)
CITIES = _csv_env(
    "CITIES",
    ["Bangalore", "Hyderabad", "Pune", "Mumbai", "Chennai", "Delhi", "Ahmedabad", "Remote"],
)
OUTPUT_FILE = str(OUTPUT_DIR / "jobs_found.json")
EXCEL_FILE = str(OUTPUT_DIR / "jobs_found.xlsx")
GOVT_SITES = {
    "ISRO": "https://www.isro.gov.in/Careers.html",
    "DRDO": "https://www.drdo.gov.in/jobs",
    "BARC": "https://www.barc.gov.in/recruitment/",
    "BEL": "https://bel-india.in/recruitment/",
    "NPCIL": "https://www.npcilcareers.co.in/",
    "ECIL": "https://www.ecil.co.in/jobs.html",
    "NIELIT": "https://www.nielit.gov.in/recruitments",
    "CDAC": "https://careers.cdac.in/",
    "HAL": "https://hal-india.co.in/career",
}
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
REQUEST_DELAY = int(os.getenv("REQUEST_DELAY", "2"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMAIL_ID = os.getenv("EMAIL_ID", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", EMAIL_ID)

PERSONAL_INFO = {
    "name": os.getenv("APPLICANT_NAME", "MD Humayun"),
    "email": os.getenv("APPLICANT_EMAIL", EMAIL_ID),
    "phone": os.getenv("APPLICANT_PHONE", ""),
    "location": os.getenv("APPLICANT_LOCATION", "India"),
    "college": os.getenv("APPLICANT_COLLEGE", ""),
    "degree": os.getenv("APPLICANT_DEGREE", ""),
    "cgpa": os.getenv("APPLICANT_CGPA", ""),
    "experience": os.getenv("APPLICANT_EXPERIENCE", "0"),
    "linkedin": os.getenv("APPLICANT_LINKEDIN", ""),
    "github": os.getenv("APPLICANT_GITHUB", ""),
}

RESUME_PATH = str(Path(os.getenv("RESUME_PATH", RESUME_DIR / "resume.pdf")))
JOBS_FILE = str(OUTPUT_DIR / "jobs_found.json")
APPLY_LOG_FILE = str(OUTPUT_DIR / "apply_log.xlsx")
LINKEDIN_COOKIE_FILE = str(BROWSER_DATA_DIR / "linkedin_cookies.json")
LINKEDIN_APPLY_LOG_FILE = str(OUTPUT_DIR / "linkedin_apply_log.json")
