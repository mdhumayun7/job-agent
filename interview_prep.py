import json
import re
import sys
sys.path.insert(0, r"C:\Users\HP\Desktop\job_agent")

with open(r"C:\Users\HP\Desktop\job_agent\config.py", "r") as cf:
    _cfg = cf.read()
_match = re.search(r'GITHUB_TOKEN = "(.+?)"', _cfg)
GITHUB_TOKEN = _match.group(1) if _match else ""

from openai import OpenAI
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN
)

MY_PROFILE = """
Name: MD Humayun
Education: M.Tech CS (Info Security) SVNIT CPI 8.90, B.Tech CS CGPA 8.51
Skills: Python, C++, TensorFlow, Keras, OpenCV, React, Flask, SQL, Git, Linux
Projects: Face Emotion Detection 92%, Plant Disease Prediction 95%, Sign Language Detection
Experience: Salesforce Intern, Freelance Digital Marketer, YouTube 12k subscribers
"""

def generate_interview_prep(job_title, company, job_description=""):
    print(f"Generating interview prep for: {job_title} @ {company}")
    prompt = f"""You are an expert interview coach.

Candidate Profile:
{MY_PROFILE}

Job: {job_title} at {company}
Description: {job_description[:500]}

Generate interview preparation in EXACTLY this format with NO markdown:

TECHNICAL_QUESTIONS:
1. [question]
2. [question]
3. [question]
4. [question]
5. [question]

HR_QUESTIONS:
1. [question]
2. [question]
3. [question]

SUGGESTED_ANSWERS:
Q1: [answer for technical question 1]
Q2: [answer for technical question 2]

TOPICS_TO_STUDY:
1. [topic]
2. [topic]
3. [topic]

STRENGTHS_TO_HIGHLIGHT:
1. [strength]
2. [strength]
3. [strength]

DIFFICULTY: [Easy/Medium/Hard]
PREPARATION_DAYS: [number of days needed]
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error: {e}")
        return ""

def save_prep_excel(job_title, company, prep_text):
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Interview Prep"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 80

    header = ws.cell(row=1, column=1, value=f"Interview Prep: {job_title} @ {company}")
    header.font = Font(bold=True, size=14, color="FFFFFF")
    header.fill = PatternFill("solid", fgColor="4F46E5")
    ws.merge_cells("A1:B1")

    sections = {
        "TECHNICAL_QUESTIONS": ("Technical Questions", "BFDBFE"),
        "HR_QUESTIONS": ("HR Questions", "BBF7D0"),
        "SUGGESTED_ANSWERS": ("Suggested Answers", "FEF08A"),
        "TOPICS_TO_STUDY": ("Topics to Study", "FDE68A"),
        "STRENGTHS_TO_HIGHLIGHT": ("Strengths to Highlight", "86EFAC"),
        "DIFFICULTY": ("Difficulty Level", "FCA5A5"),
        "PREPARATION_DAYS": ("Days Needed", "E9D5FF"),
    }

    current_row = 2
    current_section = None
    section_content = {}

    for line in prep_text.split("\n"):
        line = line.strip()
        if not line: continue
        matched = False
        for key in sections:
            if line.startswith(key + ":"):
                current_section = key
                section_content[key] = []
                matched = True
                break
            elif line == key:
                current_section = key
                section_content[key] = []
                matched = True
                break
        if not matched and current_section:
            section_content[current_section].append(line)

    for key, (label, color) in sections.items():
        content = section_content.get(key, [])
        if not content: continue
        sec_cell = ws.cell(row=current_row, column=1, value=label)
        sec_cell.font = Font(bold=True, color="FFFFFF")
        sec_cell.fill = PatternFill("solid", fgColor="1E293B")
        ws.merge_cells(f"A{current_row}:B{current_row}")
        current_row += 1
        for item in content:
            ws.cell(row=current_row, column=1, value="")
            c = ws.cell(row=current_row, column=2, value=item)
            c.fill = PatternFill("solid", fgColor=color)
            c.alignment = Alignment(wrap_text=True)
            ws.row_dimensions[current_row].height = 30
            current_row += 1

    path = r"C:\Users\HP\Desktop\job_agent\output\interview_prep.xlsx"
    wb.save(path)
    print(f"Saved: {path}")

def prep_for_job(job_title, company, job_description=""):
    prep = generate_interview_prep(job_title, company, job_description)
    print("\n" + prep)
    save_prep_excel(job_title, company, prep)

if __name__ == "__main__":
    prep_for_job("Scientist/Engineer SC", "ISRO", "M.Tech CS preferred, Python ML required")
