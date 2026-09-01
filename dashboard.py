import json, sqlite3, subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
import streamlit as st
from config import DB_FILE, ENRICHED_OUTPUT_FILE, JOBS_FILE, TRACKER_FILE

st.set_page_config(page_title="Job Agent Pro", page_icon="JA", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
* { font-family: 'Inter', sans-serif !important; }
.stApp { background: #050816 !important; }
.main .block-container { padding: 1.5rem 2rem !important; max-width: 1400px; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#0d1117,#0a0f1e) !important; border-right: 1px solid rgba(99,102,241,0.2) !important; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stRadio"] label { background: rgba(99,102,241,0.05) !important; border: 1px solid rgba(99,102,241,0.15) !important; border-radius: 10px !important; padding: 10px 16px !important; margin: 4px 0 !important; cursor: pointer !important; display: block !important; }
[data-testid="stRadio"] label:hover { background: rgba(99,102,241,0.15) !important; border-color: rgba(99,102,241,0.4) !important; }
[data-testid="metric-container"] { background: linear-gradient(135deg,rgba(99,102,241,0.1),rgba(139,92,246,0.05)) !important; border: 1px solid rgba(99,102,241,0.25) !important; border-radius: 16px !important; padding: 20px !important; }
[data-testid="metric-container"] label { color: #94a3b8 !important; font-size: 0.8rem !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; }
[data-testid="metric-container"] [data-testid="metric-value"] { color: #e2e8f0 !important; font-size: 2rem !important; font-weight: 800 !important; }
.stSelectbox > div > div, .stMultiSelect > div > div { background: rgba(15,23,42,0.8) !important; border: 1px solid rgba(99,102,241,0.3) !important; border-radius: 10px !important; color: #e2e8f0 !important; }
.stTextInput > div > div > input { background: rgba(15,23,42,0.8) !important; border: 1px solid rgba(99,102,241,0.3) !important; border-radius: 10px !important; color: #e2e8f0 !important; }
.streamlit-expanderHeader { background: rgba(15,23,42,0.6) !important; border: 1px solid rgba(99,102,241,0.2) !important; border-radius: 12px !important; color: #e2e8f0 !important; font-weight: 600 !important; }
.streamlit-expanderContent { background: rgba(10,15,30,0.8) !important; border: 1px solid rgba(99,102,241,0.15) !important; border-top: none !important; border-radius: 0 0 12px 12px !important; }
.stButton > button { background: linear-gradient(135deg,#6366f1,#8b5cf6) !important; color: white !important; border: none !important; border-radius: 10px !important; font-weight: 600 !important; }
.stLinkButton > a { background: linear-gradient(135deg,#6366f1,#8b5cf6) !important; color: white !important; border: none !important; border-radius: 10px !important; font-weight: 600 !important; text-decoration: none !important; }
.stSuccess { background: rgba(34,197,94,0.1) !important; border: 1px solid rgba(34,197,94,0.3) !important; border-radius: 10px !important; }
.stInfo { background: rgba(99,102,241,0.1) !important; border: 1px solid rgba(99,102,241,0.3) !important; border-radius: 10px !important; }
.stWarning { background: rgba(245,158,11,0.1) !important; border: 1px solid rgba(245,158,11,0.3) !important; border-radius: 10px !important; }
.stNumberInput > div > div > input { background: rgba(15,23,42,0.8) !important; border: 1px solid rgba(99,102,241,0.3) !important; border-radius: 10px !important; color: #e2e8f0 !important; }
.stCaption { color: #64748b !important; }
hr { border-color: rgba(99,102,241,0.2) !important; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_json(path, fallback=None):
    p = Path(path)
    if not p.exists(): return fallback if fallback is not None else []
    with open(p,"r",encoding="utf-8") as f: return json.load(f)

def load_jobs():
    return load_json(ENRICHED_OUTPUT_FILE, load_json(JOBS_FILE, []))

def load_history():
    return load_json("data/score_history.json", [])

def load_blacklist():
    return load_json("data/blacklist.json", [])

def save_blacklist(bl):
    Path("data").mkdir(exist_ok=True)
    with open("data/blacklist.json","w") as f: json.dump(bl, f, indent=2)

def update_status_db(job_id, status):
    if not Path(DB_FILE).exists(): return
    try:
        ts = datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE jobs SET status=?, applied_date=CASE WHEN ?='Applied' THEN ? ELSE applied_date END WHERE job_id=?",
                        (status,status,ts,job_id))
            conn.commit()
    except: pass

def update_excel_status(job_id, status):
    try:
        import openpyxl
        if not Path(TRACKER_FILE).exists(): return
        wb = openpyxl.load_workbook(TRACKER_FILE)
        ws = wb.active
        for row in ws.iter_rows(min_row=2):
            if str(row[0].value) == str(job_id):
                row[7].value = status
                if status == "Applied":
                    row[8].value = datetime.now().strftime("%Y-%m-%d")
                break
        wb.save(TRACKER_FILE)
    except: pass

def mark_applied(job_id, status="Applied"):
    update_status_db(job_id, status)
    update_excel_status(job_id, status)

def score_color(s):
    if s>=60: return "#22c55e","#052e16"
    elif s>=40: return "#6366f1","#1e1b4b"
    elif s>=20: return "#f59e0b","#1c1400"
    return "#ef4444","#1c0a0a"

def score_grade(s):
    if s>=60: return "Excellent"
    elif s>=40: return "Good"
    elif s>=20: return "Fair"
    return "Low"

def status_badge(status):
    c = {"Saved":"#94a3b8","Applied":"#60a5fa","Interview":"#34d399",
         "Rejected":"#f87171","Offer":"#4ade80","Follow Up":"#fbbf24"}.get(status,"#94a3b8")
    return f'<span style="color:{c};border:1px solid {c}55;background:{c}18;padding:3px 12px;border-radius:20px;font-size:11px;font-weight:700">{status.upper()}</span>'

def card(job):
    sc=job.get("ai_match_score",job.get("match_score",0))
    c,bg=score_color(sc)
    t=job.get("title",""); co=job.get("company",""); lo=job.get("location","")
    src=job.get("source_group",job.get("source","")); st2=job.get("status","Saved")
    fit=job.get("fit_reason",""); matched=job.get("matched_skills",[])
    sal=job.get("salary",""); jt=job.get("job_type","Full Time"); url=job.get("apply_url","")
    diff=job.get("interview_difficulty",""); grow=job.get("growth_potential","")
    tags="".join([f'<span style="background:rgba(99,102,241,0.15);color:#818cf8;border:1px solid rgba(99,102,241,0.3);padding:2px 8px;border-radius:6px;font-size:11px;margin:2px;display:inline-block">{s}</span>' for s in matched[:5]])
    meta=[]
    if sal and sal not in ["Not mentioned","Not disclosed",""]: meta.append(f"Salary: {sal}")
    if diff: meta.append(f"Interview: {diff}")
    if grow: meta.append(f"Growth: {grow}")
    meta_html=" &nbsp;|&nbsp; ".join([f'<span style="color:#64748b;font-size:12px">{m}</span>' for m in meta])
    apply_btn=f'<a href="{url}" target="_blank" style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:6px 16px;border-radius:8px;font-size:12px;font-weight:600;text-decoration:none;margin-left:8px">Apply Now</a>' if url else ""
    return f"""<div style="background:linear-gradient(135deg,rgba(15,23,42,0.95),rgba(10,15,30,0.98));border:1px solid rgba(99,102,241,0.2);border-radius:16px;padding:20px;margin-bottom:12px;box-shadow:0 4px 24px rgba(0,0,0,0.4)">
<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
<div style="flex:1">
<div style="font-size:1.05rem;font-weight:700;color:#e2e8f0;margin-bottom:4px">{t}</div>
<div style="color:#64748b;font-size:0.85rem;margin-bottom:6px"><span style="color:#94a3b8">{co}</span> &nbsp;|&nbsp; {lo} &nbsp;|&nbsp; <span style="color:#6366f1">{src}</span> &nbsp;|&nbsp; <span style="color:#8b5cf6">{jt}</span></div>
<div>{meta_html}</div>
{f'<div style="color:#94a3b8;font-size:0.82rem;margin-top:8px;font-style:italic">AI Insight: {fit}</div>' if fit else ""}
{f'<div style="margin-top:8px">{tags}</div>' if matched else ""}
</div>
<div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex-shrink:0">
<div style="background:{bg};border:2px solid {c};color:{c};font-size:1.3rem;font-weight:900;padding:8px 14px;border-radius:12px;min-width:56px;text-align:center;box-shadow:0 0 20px {c}40">{sc}</div>
<div style="font-size:10px;color:{c};font-weight:600">{score_grade(sc)}</div>
</div>
</div>
<div style="display:flex;align-items:center;margin-top:14px;gap:8px">{status_badge(st2)}{apply_btn}</div>
</div>"""

def bar_row(label, cnt, color, max_val):
    pct = cnt/max(1,max_val)*100
    return f"""<div style="margin-bottom:12px">
<div style="display:flex;justify-content:space-between;margin-bottom:5px">
<span style="color:#e2e8f0;font-size:0.85rem">{str(label)[:35]}</span>
<span style="color:{color};font-weight:700;font-size:0.85rem">{cnt}</span>
</div>
<div style="background:rgba(255,255,255,0.05);border-radius:6px;height:6px">
<div style="width:{pct:.0f}%;background:{color};height:6px;border-radius:6px"></div>
</div></div>"""

def section(text, color="#6366f1"):
    st.markdown(f'<div style="font-size:1rem;font-weight:700;color:#e2e8f0;border-left:3px solid {color};padding-left:12px;margin:16px 0 14px">{text}</div>', unsafe_allow_html=True)

def parse_salary_lpa(sal_str):
    import re
    if not sal_str: return 0,0
    nums = re.findall(r"\d+\.?\d*", str(sal_str).replace(",",""))
    if not nums: return 0,0
    nums = [float(n) for n in nums]
    if max(nums) > 200: nums = [n/100000 for n in nums]
    return min(nums), max(nums)

# ── Load Data ─────────────────────────────────────────────────────────────────
jobs_all_raw = load_jobs()
blacklist    = [c.lower() for c in load_blacklist()]
jobs_all     = [j for j in jobs_all_raw if j.get("company","").lower() not in blacklist]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style="text-align:center;padding:20px 0 10px">
<div style="font-size:1.4rem;font-weight:900;color:#818cf8;letter-spacing:0.05em">JOB AGENT</div>
<div style="font-size:1rem;font-weight:700;color:#e2e8f0;margin-top:4px">Pro Dashboard</div>
<div style="font-size:0.75rem;color:#64748b;margin-top:4px">AI-Powered Job Search</div>
</div><hr style="border-color:rgba(99,102,241,0.2);margin:10px 0 20px"/>""", unsafe_allow_html=True)

    page = st.radio("Navigation",
        ["Dashboard","Browse Jobs","Smart Filters","Tracker","Analytics","Score History","Blacklist","Resume Parser","Job Details","Insights"],
        label_visibility="collapsed")

    st.markdown("<hr style='border-color:rgba(99,102,241,0.15);margin:16px 0'/>", unsafe_allow_html=True)
    st.markdown('<div style="color:#94a3b8;font-size:0.75rem;font-weight:600;letter-spacing:0.08em;margin-bottom:10px">QUICK FILTERS</div>', unsafe_allow_html=True)

    all_src  = sorted({j.get("source_group",j.get("source","Other")) for j in jobs_all})
    all_st   = sorted({j.get("status","Saved") for j in jobs_all})
    all_type = sorted({j.get("job_type","Full Time") for j in jobs_all})

    sel_src  = st.multiselect("Source",  all_src,  default=all_src)
    sel_st   = st.multiselect("Status",  all_st,   default=all_st)
    sel_type = st.multiselect("Type",    all_type, default=all_type)
    min_sc   = st.slider("Min Score", 0, 100, 0)
    sq       = st.text_input("Search", placeholder="Title or company...")

    st.markdown("<hr style='border-color:rgba(99,102,241,0.15);margin:16px 0'/>", unsafe_allow_html=True)
    st.markdown(f'<div style="color:#64748b;font-size:0.75rem;text-align:center">Total: <b style="color:#6366f1">{len(jobs_all)}</b> jobs loaded</div>', unsafe_allow_html=True)
    if blacklist:
        st.markdown(f'<div style="color:#64748b;font-size:0.75rem;text-align:center;margin-top:4px">Blacklisted: <b style="color:#ef4444">{len(blacklist)}</b> companies</div>', unsafe_allow_html=True)

def filt(jobs):
    q=sq.lower()
    return [j for j in jobs
            if j.get("source_group",j.get("source","Other")) in sel_src
            and j.get("status","Saved") in sel_st
            and j.get("job_type","Full Time") in sel_type
            and j.get("ai_match_score",j.get("match_score",0)) >= min_sc
            and (not q or q in j.get("title","").lower() or q in j.get("company","").lower())]

jobs = filt(jobs_all)

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown('<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:4px">Dashboard</div><div style="color:#64748b;font-size:0.9rem;margin-bottom:24px">Your job search overview at a glance</div>', unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    applied    = sum(1 for j in jobs_all if j.get("status") in ["Applied","Interview","Offer"])
    interviews = sum(1 for j in jobs_all if j.get("status")=="Interview")
    offers     = sum(1 for j in jobs_all if j.get("status")=="Offer")
    avg_sc     = round(sum(j.get("ai_match_score",j.get("match_score",0)) for j in jobs_all)/max(1,len(jobs_all)),1)
    with c1: st.metric("Total Jobs", len(jobs_all))
    with c2: st.metric("Applied", applied)
    with c3: st.metric("Interviews", interviews)
    with c4: st.metric("Offers", offers)
    with c5: st.metric("Avg Score", f"{avg_sc}")

    st.markdown("<br>", unsafe_allow_html=True)
    cl, cr = st.columns([3,2])

    with cl:
        section("Top Matched Jobs","#6366f1")
        for job in sorted(jobs, key=lambda j: j.get("ai_match_score",j.get("match_score",0)), reverse=True)[:8]:
            st.markdown(card(job), unsafe_allow_html=True)

    with cr:
        section("Source Breakdown","#8b5cf6")
        src_c = Counter(j.get("source_group",j.get("source","Other")) for j in jobs)
        src_colors = {"Shine":"#6366f1","Naukri":"#8b5cf6","Internshala":"#06b6d4","LinkedIn":"#0ea5e9","Indeed":"#f59e0b","Government":"#22c55e"}
        mv = max(src_c.values()) if src_c else 1
        for src,cnt in src_c.most_common():
            st.markdown(bar_row(src,cnt,src_colors.get(src,"#94a3b8"),mv), unsafe_allow_html=True)

        section("Application Pipeline","#06b6d4")
        sc_cnt = Counter(j.get("status","Saved") for j in jobs_all)
        for s,c_ in [("Saved","#94a3b8"),("Applied","#60a5fa"),("Interview","#34d399"),("Offer","#4ade80")]:
            cnt=sc_cnt.get(s,0)
            st.markdown(f"""<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:12px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
<span style="color:{c_};font-weight:600;font-size:0.9rem">{s}</span>
<span style="background:{c_}22;color:{c_};padding:2px 12px;border-radius:20px;font-weight:700;font-size:0.85rem">{cnt}</span>
</div>""", unsafe_allow_html=True)

        if st.button("Generate Daily Report"):
            import subprocess
            result = subprocess.run("python report_generator.py --top 20", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                st.success("Report generated! Check output/ folder.")
            else:
                st.error("Error generating report.")

# ══════════════════════════════════════════════════════════════════════════════
# BROWSE JOBS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Browse Jobs":
    st.markdown(f'<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:4px">Browse Jobs</div><div style="color:#64748b;margin-bottom:20px"><span style="color:#6366f1;font-weight:700">{len(jobs)}</span> jobs match your filters</div>', unsafe_allow_html=True)

    c1,c2 = st.columns([3,1])
    with c1: sort_by=st.selectbox("Sort by",["Score (High to Low)","Company A-Z","Posted Date"],label_visibility="collapsed")
    with c2: ps=st.selectbox("Per page",[10,20,50],index=1,label_visibility="collapsed")

    smap={"Score (High to Low)":lambda j:j.get("ai_match_score",j.get("match_score",0)),"Company A-Z":lambda j:j.get("company",""),"Posted Date":lambda j:j.get("posted_date","")}
    rev=sort_by!="Company A-Z"
    sj=sorted(jobs,key=smap[sort_by],reverse=rev)
    tp=max(1,(len(sj)-1)//ps+1)
    pg=st.number_input(f"Page (1 of {tp})",1,tp,1,label_visibility="collapsed")
    pj=sj[(pg-1)*ps:pg*ps]
    st.caption(f"Showing {(pg-1)*ps+1} to {min(pg*ps,len(sj))} of {len(sj)} jobs")

    for job in pj:
        sc2=job.get("ai_match_score",job.get("match_score",0))
        matched=", ".join(job.get("matched_skills",[])[:4])
        missing=", ".join(job.get("missing_skills",[])[:3])
        job_id=job.get("job_id","")
        with st.expander(f"[{sc2}/100]  {job.get('title','')}  |  {job.get('company','')}  |  {job.get('location','')}"):
            c1,c2,c3=st.columns(3)
            with c1:
                st.markdown(f"**Source:** {job.get('source_group',job.get('source',''))}")
                st.markdown(f"**Type:** {job.get('job_type','Full Time')}")
                st.markdown(f"**Salary:** {job.get('salary','Not mentioned')}")
            with c2:
                st.markdown(f"**Posted:** {job.get('posted_date','N/A')}")
                st.markdown(f"**Difficulty:** {job.get('interview_difficulty','N/A')}")
                st.markdown(f"**Growth:** {job.get('growth_potential','N/A')}")
            with c3:
                cur=job.get("status","Saved"); sts=["Saved","Applied","Interview","Rejected","Offer","Follow Up"]
                ns=st.selectbox("Update Status",sts,index=sts.index(cur) if cur in sts else 0,key=f"s_{job_id}{sc2}")
                if ns!=cur:
                    update_status_db(job_id,ns)
                    update_excel_status(job_id,ns)
                    st.success("Status updated in DB and Excel!")

            # ONE-CLICK APPLY BUTTON
            col_a, col_b = st.columns(2)
            with col_a:
                if job.get("status","Saved") == "Saved":
                    if st.button("Mark as Applied", key=f"apply_{job_id}"):
                        mark_applied(job_id,"Applied")
                        st.success("Marked Applied in DB and Excel!")
            with col_b:
                if job.get("apply_url"):
                    st.link_button("Open Job Link", job["apply_url"])

            if job.get("fit_reason"): st.info(f"AI Insight: {job['fit_reason']}")
            if matched: st.success(f"Matched Skills: {matched}")
            if missing: st.warning(f"Missing Skills: {missing}")
            if job.get("interview_focus_topics"): st.markdown(f"**Study Topics:** {', '.join(job['interview_focus_topics'])}")
            if job.get("cover_letter_opening"):
                st.markdown(f"""<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:10px;padding:12px 16px;margin-top:8px">
<div style="color:#818cf8;font-size:0.75rem;font-weight:600;margin-bottom:6px">COVER LETTER OPENER</div>
<div style="color:#c7d2fe;font-size:0.9rem;font-style:italic">{job['cover_letter_opening']}</div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SMART FILTERS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Smart Filters":
    st.markdown('<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:20px">Smart Filters</div>', unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    with c1:
        section("Job Type","#6366f1")
        show_fulltime  = st.toggle("Full Time",  value=True)
        show_internship = st.toggle("Internship", value=True)
    with c2:
        section("Location","#8b5cf6")
        all_locs = sorted({j.get("location","India") for j in jobs_all if j.get("location")})
        sel_locs = st.multiselect("Select Locations", all_locs, default=all_locs[:8] if len(all_locs)>8 else all_locs)
    with c3:
        section("Score Range","#06b6d4")
        score_range = st.slider("Score Range", 0, 100, (0,100))

    section("Salary Filter (LPA)","#22c55e")
    salary_filter = st.slider("Min Salary LPA", 0, 30, 0)

    section("Source Filter","#f59e0b")
    src_cols = st.columns(5)
    src_names = sorted({j.get("source_group",j.get("source","Other")) for j in jobs_all})
    sel_srcs_sf = []
    for i,src in enumerate(src_names):
        with src_cols[i % 5]:
            if st.checkbox(src, value=True, key=f"sf_{src}"):
                sel_srcs_sf.append(src)

    # Apply smart filters
    smart_filtered = []
    for j in jobs_all:
        jtype = j.get("job_type","Full Time")
        if jtype=="Full Time" and not show_fulltime: continue
        if jtype=="Internship" and not show_internship: continue
        loc = j.get("location","")
        if sel_locs and not any(sl.lower() in loc.lower() for sl in sel_locs): continue
        sc = j.get("ai_match_score",j.get("match_score",0))
        if not (score_range[0] <= sc <= score_range[1]): continue
        src = j.get("source_group",j.get("source","Other"))
        if src not in sel_srcs_sf: continue
        if salary_filter > 0:
            lo,hi = parse_salary_lpa(j.get("salary",""))
            if hi > 0 and hi < salary_filter: continue
        smart_filtered.append(j)

    smart_filtered = sorted(smart_filtered, key=lambda j: j.get("ai_match_score",j.get("match_score",0)), reverse=True)

    st.markdown(f"""<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:12px;padding:16px;margin:16px 0;text-align:center">
<span style="color:#818cf8;font-size:1.2rem;font-weight:800">{len(smart_filtered)}</span>
<span style="color:#64748b;font-size:0.9rem"> jobs match your smart filters</span>
</div>""", unsafe_allow_html=True)

    for job in smart_filtered[:20]:
        st.markdown(card(job), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Tracker":
    st.markdown('<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:20px">Application Tracker</div>', unsafe_allow_html=True)
    fn={"Saved":0,"Applied":0,"Interview":0,"Offer":0}
    for j in jobs_all:
        s=j.get("status","Saved")
        if s in fn: fn[s]+=1
    cols=st.columns(4); clrs=["#94a3b8","#60a5fa","#34d399","#4ade80"]
    for col,(lbl,cnt),clr in zip(cols,fn.items(),clrs):
        with col:
            st.markdown(f"""<div style="background:linear-gradient(135deg,rgba(15,23,42,0.9),rgba(10,15,30,0.95));border:1px solid {clr}40;border-radius:16px;padding:20px;text-align:center">
<div style="font-size:1.8rem;font-weight:900;color:{clr}">{cnt}</div>
<div style="color:#64748b;font-size:0.85rem;margin-top:4px;font-weight:600">{lbl}</div>
</div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Conversion rate
    total_applied = fn["Applied"] + fn["Interview"] + fn["Offer"]
    if total_applied > 0:
        interview_rate = round(fn["Interview"]/total_applied*100,1)
        offer_rate = round(fn["Offer"]/max(1,fn["Interview"])*100,1)
        r1,r2 = st.columns(2)
        with r1: st.metric("Interview Rate", f"{interview_rate}%", help="Interviews / Applied")
        with r2: st.metric("Offer Rate", f"{offer_rate}%", help="Offers / Interviews")

    tracked=[j for j in jobs_all if j.get("status","Saved")!="Saved"]
    if not tracked:
        st.markdown("""<div style="text-align:center;padding:60px;color:#64748b">
<div style="font-size:1.2rem;font-weight:600;margin-bottom:8px">No Applications Tracked Yet</div>
<div style="font-size:0.85rem">Go to Browse Jobs and click "Mark as Applied"</div>
</div>""", unsafe_allow_html=True)
    else:
        st.dataframe([{
            "Score": j.get("ai_match_score",j.get("match_score",0)),
            "Title": j.get("title",""), "Company": j.get("company",""),
            "Source": j.get("source_group",""), "Status": j.get("status",""),
            "Applied": j.get("applied_date",""), "Link": j.get("apply_url","")
        } for j in sorted(tracked,key=lambda j:j.get("ai_match_score",0),reverse=True)],
        use_container_width=True, height=500)

# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Analytics":
    st.markdown('<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:20px">Analytics</div>', unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        section("Top Locations","#6366f1")
        lc=Counter(j.get("location","Unknown") for j in jobs)
        mv=max(lc.values()) if lc else 1
        for loc,cnt in lc.most_common(8): st.markdown(bar_row(loc,cnt,"#6366f1",mv),unsafe_allow_html=True)
    with c2:
        section("Top Companies","#8b5cf6")
        cc=Counter(j.get("company","Unknown") for j in jobs)
        mv=max(cc.values()) if cc else 1
        for comp,cnt in cc.most_common(8): st.markdown(bar_row(comp,cnt,"#8b5cf6",mv),unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    c3,c4=st.columns(2)
    with c3:
        section("In-Demand Skills","#06b6d4")
        sk=Counter()
        [sk.update(j.get("matched_skills",[])) for j in jobs]
        mv=max(sk.values()) if sk else 1
        for skill,cnt in sk.most_common(10): st.markdown(bar_row(skill,cnt,"#06b6d4",mv),unsafe_allow_html=True)
    with c4:
        section("Score Distribution","#22c55e")
        ranges=[("Excellent (60-100)",60,101,"#22c55e"),("Good (40-59)",40,60,"#6366f1"),
                ("Fair (20-39)",20,40,"#f59e0b"),("Low (0-19)",0,20,"#ef4444")]
        for lbl,lo,hi,clr in ranges:
            cnt=sum(1 for j in jobs if lo<=j.get("ai_match_score",j.get("match_score",0))<hi)
            pct=cnt/max(1,len(jobs))*100
            st.markdown(f"""<div style="background:rgba(255,255,255,0.03);border:1px solid {clr}30;border-radius:10px;padding:12px 16px;margin-bottom:8px">
<div style="display:flex;justify-content:space-between;margin-bottom:6px">
<span style="color:{clr};font-weight:600;font-size:0.85rem">{lbl}</span>
<span style="color:{clr};font-weight:700">{cnt} jobs ({pct:.0f}%)</span>
</div>
<div style="background:rgba(255,255,255,0.05);border-radius:4px;height:6px">
<div style="width:{pct:.0f}%;background:{clr};height:6px;border-radius:4px"></div>
</div></div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SCORE HISTORY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Score History":
    st.markdown('<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:20px">Score History</div>', unsafe_allow_html=True)
    history = load_history()

    if not history:
        st.info("No history yet. Run python history_tracker.py after each scrape to track progress.")
    else:
        # Summary cards
        latest = history[-1]
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Today's Jobs", latest.get("total",0))
        with c2: st.metric("Avg Score", latest.get("avg_score",0))
        with c3: st.metric("Excellent Matches", latest.get("excellent",0))
        with c4: st.metric("Days Tracked", len(history))

        st.markdown("<br>",unsafe_allow_html=True)
        section("Daily Job Count (Last 30 Days)","#6366f1")

        # Draw history chart using HTML
        if len(history) > 1:
            max_total = max(h.get("total",0) for h in history)
            bars = ""
            for h in history:
                date = h.get("date","")[-5:]  # MM-DD
                total = h.get("total",0)
                avg = h.get("avg_score",0)
                exc = h.get("excellent",0)
                pct = total/max(1,max_total)*100
                bars += f"""<div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex:1">
<div style="color:#818cf8;font-size:10px;font-weight:700">{total}</div>
<div style="width:100%;background:rgba(255,255,255,0.05);border-radius:4px;height:80px;display:flex;align-items:flex-end">
<div style="width:100%;height:{pct:.0f}%;background:linear-gradient(180deg,#6366f1,#8b5cf6);border-radius:4px 4px 0 0;min-height:4px"></div>
</div>
<div style="color:#64748b;font-size:9px;transform:rotate(-45deg);white-space:nowrap">{date}</div>
</div>"""
            st.markdown(f"""<div style="background:rgba(15,23,42,0.8);border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:20px">
<div style="display:flex;gap:4px;align-items:flex-end;height:130px">{bars}</div>
</div>""", unsafe_allow_html=True)

        section("Detailed History","#8b5cf6")
        st.dataframe([{
            "Date": h.get("date",""),
            "Total Jobs": h.get("total",0),
            "Avg Score": h.get("avg_score",0),
            "Excellent (60+)": h.get("excellent",0),
            "Good (40-59)": h.get("good",0),
        } for h in reversed(history)], use_container_width=True)

        if st.button("Save Today to History"):
            import subprocess
            subprocess.run("python history_tracker.py", shell=True)
            st.success("History updated!")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# BLACKLIST
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Blacklist":
    st.markdown('<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:20px">Company Blacklist</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#64748b;margin-bottom:20px">Hide companies you are not interested in. Blacklisted companies will not appear in any page.</div>', unsafe_allow_html=True)

    current_bl = load_blacklist()

    c1,c2 = st.columns([3,1])
    with c1:
        new_company = st.text_input("Add company to blacklist", placeholder="e.g. Some Company Ltd")
    with c2:
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("Add to Blacklist"):
            if new_company.strip():
                if new_company.strip().lower() not in [c.lower() for c in current_bl]:
                    current_bl.append(new_company.strip())
                    save_blacklist(current_bl)
                    st.success(f"Added '{new_company}' to blacklist!")
                    st.rerun()
                else:
                    st.warning("Already in blacklist!")

    # Quick add from job list
    section("Quick Add from Job List","#ef4444")
    all_companies = sorted({j.get("company","") for j in jobs_all_raw if j.get("company","")})
    quick_add = st.selectbox("Select company to blacklist", ["-- Select --"] + all_companies)
    if quick_add != "-- Select --":
        if st.button(f"Blacklist '{quick_add}'"):
            if quick_add.lower() not in [c.lower() for c in current_bl]:
                current_bl.append(quick_add)
                save_blacklist(current_bl)
                st.success(f"Blacklisted '{quick_add}'!")
                st.rerun()

    # Show current blacklist
    if current_bl:
        section(f"Currently Blacklisted ({len(current_bl)} companies)","#94a3b8")
        for i,company in enumerate(current_bl):
            col1,col2 = st.columns([4,1])
            with col1:
                st.markdown(f'<div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);border-radius:8px;padding:10px 16px;color:#f87171">{company}</div>', unsafe_allow_html=True)
            with col2:
                if st.button("Remove", key=f"rm_{i}"):
                    current_bl.remove(company)
                    save_blacklist(current_bl)
                    st.success("Removed!")
                    st.rerun()
    else:
        st.info("No companies blacklisted yet.")

# ══════════════════════════════════════════════════════════════════════════════
# INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Insights":
    st.markdown('<div style="font-size:1.8rem;font-weight:800;color:#e2e8f0;margin-bottom:20px">AI Insights</div>', unsafe_allow_html=True)
    section("Best Fit Jobs (Score 20 and above)","#6366f1")
    best=sorted([j for j in jobs if j.get("ai_match_score",j.get("match_score",0))>=20],
                key=lambda j:j.get("ai_match_score",j.get("match_score",0)),reverse=True)[:15]
    if not best: st.info("No high-scoring jobs yet. Run phase2_enrichment.py first.")
    else:
        for job in best: st.markdown(card(job),unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    section("Skills Gap Analysis","#f59e0b")
    miss=Counter()
    [miss.update(j.get("missing_skills",[])) for j in jobs]
    if miss:
        for skill,cnt in miss.most_common(10):
            pct=cnt/max(1,len(jobs))*100
            st.markdown(f"""<div style="background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.2);border-radius:10px;padding:12px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
<span style="color:#fbbf24;font-weight:600">{skill}</span>
<span style="color:#64748b;font-size:0.82rem">needed in <b style="color:#f59e0b">{cnt}</b> jobs ({pct:.0f}%)</span>
</div>""", unsafe_allow_html=True)
    else:
        st.success("No major skill gaps detected!")


