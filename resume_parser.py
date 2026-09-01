import re
import json
from pathlib import Path

SKILL_KEYWORDS = [
    "python","java","javascript","typescript","react","angular","vue","nodejs","django","flask",
    "fastapi","sql","mysql","postgresql","mongodb","redis","aws","gcp","azure","docker",
    "kubernetes","git","linux","bash","tensorflow","pytorch","keras","scikit-learn","sklearn",
    "pandas","numpy","matplotlib","opencv","nlp","deep learning","machine learning",
    "data analysis","data science","html","css","bootstrap","tailwind","rest","api",
    "graphql","microservices","ci/cd","jenkins","kafka","spark","hadoop","tableau",
    "power bi","selenium","playwright","c++","c#","golang","rust","php","ruby",
    "swift","kotlin","flutter","react native","android","ios","excel","git","linux",
]

def extract_text(file_bytes, filename):
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        try:
            import pdfplumber, io
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return " ".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            try:
                import fitz, io
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                return " ".join(page.get_text() for page in doc)
            except ImportError:
                return ""
    elif ext in [".docx"]:
        try:
            from docx import Document
            import io
            doc = Document(io.BytesIO(file_bytes))
            return " ".join(p.text for p in doc.paragraphs)
        except ImportError:
            return ""
    elif ext == ".txt":
        return file_bytes.decode("utf-8", errors="ignore")
    return ""

def parse_resume_text(text):
    text_lower = text.lower()
    found_skills = list(dict.fromkeys([s for s in SKILL_KEYWORDS if s in text_lower]))
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    phones = re.findall(r"[\+]?[0-9]{10,13}", text)
    exp_matches = re.findall(r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)", text_lower)
    experience = max([int(e) for e in exp_matches], default=0)
    edu = [k for k in ["b.tech","m.tech","btech","mtech","b.e","m.e","bsc","msc","phd","bachelor","master"] if k in text_lower]
    return {
        "skills": found_skills,
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "experience": experience,
        "education": edu[:2],
    }
