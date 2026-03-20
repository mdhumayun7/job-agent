import json
import re
import sys
sys.path.insert(0, r"C:\Users\HP\Desktop\job_agent")

with open(r"C:\Users\HP\Desktop\job_agent\config.py", "r") as cf:
    _cfg = cf.read()
_match = re.search(r'GITHUB_TOKEN = "(.+?)"', _cfg)
GITHUB_TOKEN = _match.group(1) if _match else ""

OUTPUT_FILE = r"C:\Users\HP\Desktop\job_agent\output\jobs_found.json"

from openai import OpenAI
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN
)

MY_RESUME = """
NAME: MD Humayun
EMAIL: humayunrahi739@gmail.com
EDUCATION:
- M.Tech CS (Info Security) - SVNIT, CPI: 8.90
- B.Tech CS - Bihar Engineering University, CGPA: 8.51
SKILLS:
- Python, C++, JavaScript, SQL, HTML, CSS, Bash
- TensorFlow, Keras, OpenCV, Pandas, NumPy, Scikit-learn
- React.js, Node.js, Flask, REST APIs, Bootstrap
- Git, Linux, Google Colab, Salesforce
PROJECTS:
- Face Emotion Detection CNN 92% accuracy
- Plant Disease Prediction ResNet50 95% accuracy
- Real-Time Sign Language Detection MediaPipe LSTM
CERTIFICATIONS:
- Python IIT Bombay, IoT IIT Roorkee, Ethical Hacking IIIT Allahabad
"""

def tailor_resume(job_title, company, job_description, job_source):
    print(f"  Tailoring: {job_title} @ {company}")
    prompt = f"""You are an expert resume writer.
Job: {job_title} at {company}
Description: {job_description[:800]}
My Resume: {MY_RESUME}
Reply EXACTLY in this format with NO bold or markdown:
OBJECTIVE: [3 line objective]
TOP_SKILLS: [skill1, skill2, skill3, skill4, skill5]
COVER_LETTER: [100 word letter]
MATCH_SCORE: [number only]
MISSING_SKILLS: [skill1, skill2, skill3]"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        text = response.choices[0].message.content
        result = {"objective":"","top_skills":"","cover_letter":"","ai_match_score":0,"missing_skills":""}
        for line in text.split("\n"):
            line = line.strip()
            if line.upper().startswith("OBJECTIVE:"): result["objective"] = line.split(":",1)[1].strip()
            elif line.upper().startswith("TOP_SKILLS:"): result["top_skills"] = line.split(":",1)[1].strip()
            elif line.upper().startswith("COVER_LETTER:"): result["cover_letter"] = line.split(":",1)[1].strip()
            elif line.upper().startswith("MATCH_SCORE:"):
                nums = re.findall(r"\d+", line)
                result["ai_match_score"] = int(nums[0]) if nums else 0
            elif line.upper().startswith("MISSING_SKILLS:"): result["missing_skills"] = line.split(":",1)[1].strip()
        return result
    except Exception as e:
        print(f"  Error: {e}")
        return {"objective":"","top_skills":"","cover_letter":"","ai_match_score":0,"missing_skills":""}

def tailor_top_jobs(top_n=10):
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    top_jobs = sorted(jobs, key=lambda x: x.get("match_score",0), reverse=True)[:top_n]
    print(f"Top {top_n} jobs ke liye tailor ho raha hai...")
    results = []
    for i, job in enumerate(top_jobs, 1):
        print(f"[{i}/{top_n}]")
        r = tailor_resume(
            job.get("title",""),
            job.get("company",""),
            job.get("description", job.get("title","")),
            job.get("source","")
        )
        job.update(r)
        results.append(job)
    save_tailored_excel(results)
    return results

def save_tailored_excel(jobs):
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tailored Resumes"
    headers = ["AI Score","Title","Company","Location","Salary","Source","Apply Link","Objective","Top Skills","Cover Letter","Missing Skills"]
    hf = PatternFill("solid", fgColor="7C3AED")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hf
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")
    for row, job in enumerate(jobs, 2):
        score = job.get("ai_match_score", 0)
        sc = ws.cell(row=row, column=1, value=score)
        if score >= 70: sc.fill = PatternFill("solid", fgColor="86EFAC")
        elif score >= 50: sc.fill = PatternFill("solid", fgColor="FDE68A")
        else: sc.fill = PatternFill("solid", fgColor="FCA5A5")
        ws.cell(row=row, column=2, value=job.get("title",""))
        ws.cell(row=row, column=3, value=job.get("company",""))
        ws.cell(row=row, column=4, value=job.get("location",""))
        ws.cell(row=row, column=5, value=job.get("salary",""))
        ws.cell(row=row, column=6, value=job.get("source",""))
        ws.cell(row=row, column=7, value=job.get("apply_url",""))
        ws.cell(row=row, column=8, value=job.get("objective",""))
        ws.cell(row=row, column=9, value=job.get("top_skills",""))
        cl = ws.cell(row=row, column=10, value=job.get("cover_letter",""))
        cl.alignment = Alignment(wrap_text=True)
        ws.cell(row=row, column=11, value=job.get("missing_skills",""))
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len+4, 60)
    path = r"C:\Users\HP\Desktop\job_agent\output\tailored_jobs.xlsx"
    wb.save(path)
    print(f"Saved: {path}")
