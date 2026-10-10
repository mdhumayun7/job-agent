import * as store from "../store.js";
import * as state from "../state.js";
import { parseResumeText, SKILLS, DISCIPLINES } from "../resume-parse.js";
import { LEVEL_LABELS, CATEGORIES } from "../eligibility.js";
import { esc, breadcrumb, setTitle, toast, todayISO, confirmDialog } from "../ui.js";

const MAX_BYTES = 5 * 1024 * 1024;
const TYPES = {
  "application/pdf": "pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx", "text/plain": "txt",
};
const STATES = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
  "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"];

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = src; s.async = true; s.crossOrigin = "anonymous";
    s.onload = resolve; s.onerror = () => reject(new Error("Could not load the document reader. Check your connection."));
    document.head.appendChild(s);
  });
}

async function readFileText(file) {
  const kind = TYPES[file.type] || (file.name.match(/\.(pdf|docx|txt)$/i)?.[1].toLowerCase());
  if (!kind) throw new Error("Use a PDF, Word (.docx) or plain text file.");
  if (file.size > MAX_BYTES) throw new Error("The file is larger than 5 MB. Export a smaller PDF and try again.");
  const buf = await file.arrayBuffer();
  if (kind === "txt") return new TextDecoder().decode(buf);
  if (kind === "pdf") {
    if (new TextDecoder().decode(buf.slice(0, 5)) !== "%PDF-") throw new Error("This file is not a valid PDF.");
    await loadScript("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js");
    const lib = window.pdfjsLib;
    lib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    const pdf = await lib.getDocument({ data: buf, isEvalSupported: false }).promise;
    let text = "";
    for (let p = 1; p <= Math.min(pdf.numPages, 8); p++) {
      const page = await pdf.getPage(p);
      const content = await page.getTextContent();
      text += content.items.map((it) => it.str + (it.hasEOL ? "\n" : " ")).join("") + "\n";
    }
    if (text.trim().length < 40) throw new Error("No text was found. If the resume is a scanned image, type your details below instead.");
    return text;
  }
  await loadScript("https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/mammoth.browser.min.js");
  const r = await window.mammoth.extractRawText({ arrayBuffer: buf });
  return r.value;
}

function qualRow(q, i) {
  return `<div class="qual-row" data-row="${i}">
    <div class="field"><label for="q-level-${i}">Level</label><select id="q-level-${i}" data-k="level">${Object.entries(LEVEL_LABELS).map(([v, l]) => `<option value="${v}" ${q.level === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
    <div class="field" data-tip="Your stream or subject, e.g. computer science, mechanical, commerce."><label for="q-disc-${i}">Discipline</label><input id="q-disc-${i}" data-k="discipline" list="disciplines" value="${esc(q.discipline || "")}"></div>
    <div class="field" data-tip="Year you passed or will pass, e.g. 2025."><label for="q-year-${i}">Year</label><input id="q-year-${i}" data-k="year" type="number" min="1970" max="2040" inputmode="numeric" value="${esc(q.year ?? "")}"></div>
    <div class="field" data-tip="Percentage of marks. If you have CGPA, enter the percentage your university's conversion gives."><label for="q-pct-${i}">Marks %</label><input id="q-pct-${i}" data-k="percentage" type="number" min="0" max="100" step="0.01" value="${esc(q.percentage ?? "")}"></div>
    <div class="field"><label for="q-status-${i}">Status</label><select id="q-status-${i}" data-k="status"><option value="completed" ${q.status !== "pursuing" ? "selected" : ""}>Completed</option><option value="pursuing" ${q.status === "pursuing" ? "selected" : ""}>Pursuing</option></select></div>
    <button class="btn btn-quiet btn-small" type="button" data-remove="${i}" aria-label="Remove this qualification">Remove</button>
    ${q.level === "12th" ? `<div class="field" style="grid-column:1/-1" data-tip="Some posts need specific 12th subjects, e.g. Mathematics and Physics."><label for="q-subj-${i}">12th subjects</label><input id="q-subj-${i}" data-k="subjects" value="${esc((q.subjects || []).join(", "))}" placeholder="Mathematics, Physics, Chemistry"></div>` : ""}
  </div>`;
}

export async function render(app) {
  setTitle("Your profile", "Add your education once, from a resume or by typing it, to check eligibility on every listing.");
  let draft = JSON.parse(JSON.stringify(state.profile() || {}));
  draft.qualifications ||= [];
  draft.skills ||= [];
  draft.certifications ||= [];
  let step = draft.qualifications.length ? 2 : 1;
  const where = store.mode() === "account" ? "your account" : "this device only";

  function stepsHtml() {
    const s = [["Add resume", 1], ["Review education and skills", 2], ["Personal details (optional)", 3]];
    return `<ol class="steps" aria-label="Progress">${s.map(([l, n]) => `<li ${n === step ? 'aria-current="step"' : ""} class="${n < step ? "done" : ""}">${l}</li>`).join("")}</ol>`;
  }

  function draw() {
    app.innerHTML = `<div class="page">
      ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Your profile" }])}
      <div class="page-head"><h1>Your profile</h1>
        <p>Used to check eligibility and rank jobs. Saved to ${where}. Your resume file is read inside your browser and is never uploaded or stored; only the details you confirm below are saved.</p></div>
      ${stepsHtml()}
      <div id="stepBody"></div>
      <datalist id="disciplines">${DISCIPLINES.map((d) => `<option value="${esc(d)}">`).join("")}</datalist>
      <section class="panel" style="margin-top:24px"><h2>Delete your profile data</h2>
        <p class="small muted">Removes your education, skills and personal details${store.mode() === "account" ? " from your account" : " from this device"}. Saved jobs are kept; use the dashboard to remove them, or delete your whole account there.</p>
        <button class="btn btn-danger" type="button" id="deleteProfile">Delete profile data</button></section></div>`;
    document.getElementById("deleteProfile").addEventListener("click", async () => {
      if (!(await confirmDialog("Delete your profile data?", "Your education, skills and personal details will be removed. This cannot be undone.", "Delete", true))) return;
      try { await store.saveProfile({}); await state.load(); toast("Profile data deleted."); render(app); }
      catch (e) { toast(`Could not delete: ${e.message}`, { error: true }); }
    });
    if (step === 1) drawUpload(); else if (step === 2) drawReview(); else drawPersonal();
  }

  function drawUpload() {
    const el = document.getElementById("stepBody");
    el.innerHTML = `<div class="panel">
      <h2>Add your resume</h2>
      <div class="dropzone" id="drop" data-guide="Drop a PDF or Word resume. It is read in your browser; nothing is uploaded.">
        <p><strong>Drop your resume here</strong> or choose a file</p>
        <p class="small muted">PDF, Word (.docx) or text, up to 5 MB. Scanned images cannot be read.</p>
        <label class="btn btn-primary" for="file">Choose file</label>
        <input id="file" type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" class="sr-only">
        <p id="fileStatus" class="small" role="status" style="margin-top:10px"></p>
      </div>
      <p style="margin-top:14px"><button class="btn" type="button" id="manual">Type my details instead</button></p></div>`;
    const status = document.getElementById("fileStatus");
    const handle = async (file) => {
      if (!file) return;
      status.textContent = `Reading ${file.name}...`;
      try {
        const text = await readFileText(file);
        const parsed = parseResumeText(text);
        const keep = (draft.qualifications || []).filter((q) => !parsed.qualifications.some((p) => p.level === q.level));
        draft.qualifications = [...parsed.qualifications.map(({ source_line, ...q }) => q), ...keep];
        draft.skills = [...new Set([...(draft.skills || []), ...parsed.skills])];
        draft.certifications = [...new Set([...(draft.certifications || []), ...parsed.certifications])];
        if (parsed.experience_years != null && draft.experience_years == null) draft.experience_years = parsed.experience_years;
        toast(`Found ${parsed.qualifications.length} qualification${parsed.qualifications.length === 1 ? "" : "s"} and ${parsed.skills.length} skills. Check them before saving.`);
        step = 2; draw();
      } catch (e) {
        status.textContent = e.message;
        status.style.color = "var(--seal)";
      }
    };
    document.getElementById("file").addEventListener("change", (e) => handle(e.target.files[0]));
    const drop = document.getElementById("drop");
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("drag"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
    drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("drag"); handle(e.dataTransfer.files[0]); });
    document.getElementById("manual").addEventListener("click", () => {
      if (!draft.qualifications.length) draft.qualifications.push({ level: "graduate", status: "completed" });
      step = 2; draw();
    });
  }

  function collectQuals() {
    return [...document.querySelectorAll(".qual-row")].map((row) => {
      const q = {};
      row.querySelectorAll("[data-k]").forEach((inp) => {
        const k = inp.dataset.k;
        let v = inp.value.trim();
        if (k === "year" || k === "percentage") v = v === "" ? null : Number(v);
        if (k === "subjects") v = v ? v.split(",").map((s) => s.trim()).filter(Boolean) : [];
        if (k === "discipline" && !v) v = null;
        q[k] = v;
      });
      return q;
    });
  }

  function validateQuals(quals) {
    const errors = [];
    const thisYear = new Date().getFullYear();
    quals.forEach((q, i) => {
      if (q.year != null && (q.year < 1970 || q.year > thisYear + 6)) errors.push([`q-year-${i}`, "Enter a year between 1970 and " + (thisYear + 6) + "."]);
      if (q.year != null && q.year > thisYear && q.status !== "pursuing") errors.push([`q-status-${i}`, "A future passing year means you are still pursuing it."]);
      if (q.percentage != null && (q.percentage < 0 || q.percentage > 100)) errors.push([`q-pct-${i}`, "Marks must be between 0 and 100."]);
    });
    return errors;
  }

  function drawReview() {
    const el = document.getElementById("stepBody");
    el.innerHTML = `<form class="panel" id="reviewForm" novalidate>
      <h2>Check your education</h2>
      <p class="small muted">Correct anything the resume reader got wrong. Only your highest qualification and any 12th subjects usually matter for eligibility.</p>
      <div id="quals">${draft.qualifications.map(qualRow).join("")}</div>
      <button class="btn btn-small" type="button" id="addQual" style="margin-top:10px">Add qualification</button>
      <h2 style="margin-top:24px">Skills</h2>
      <div class="chips" id="skillChips">${draft.skills.map((s) => `<span class="chip">${esc(s)}<button type="button" data-skill="${esc(s)}" aria-label="Remove ${esc(s)}">&times;</button></span>`).join("") || '<span class="muted small">No skills yet.</span>'}</div>
      <div class="field" style="margin-top:10px;max-width:420px" data-tip="Type a skill and press Enter, e.g. Python, SQL, Tally."><label for="skillInput">Add a skill</label><input id="skillInput" list="skillList" placeholder="Type a skill and press Enter"><datalist id="skillList">${Object.keys(SKILLS).map((s) => `<option value="${esc(s)}">`).join("")}</datalist></div>
      <h2 style="margin-top:24px">Certifications</h2>
      <div class="field"><label for="certs">One per line</label><textarea id="certs" rows="4">${esc(draft.certifications.join("\n"))}</textarea></div>
      <div class="field" style="max-width:240px" data-tip="Full years of paid work experience. Internships usually do not count; check each notice."><label for="exp">Work experience (years)</label><input id="exp" type="number" min="0" max="50" value="${esc(draft.experience_years ?? "")}"></div>
      <div id="reviewErrors" role="alert"></div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><button class="btn" type="button" id="back">Back</button><button class="btn btn-primary" type="submit">Continue</button></div></form>`;
    const sync = () => { draft.qualifications = collectQuals(); };
    document.getElementById("addQual").addEventListener("click", () => { sync(); draft.qualifications.push({ level: "12th", status: "completed" }); drawReview(); });
    el.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => { sync(); draft.qualifications.splice(Number(b.dataset.remove), 1); drawReview(); }));
    el.querySelectorAll('[data-k="level"]').forEach((s) => s.addEventListener("change", () => { sync(); drawReview(); }));
    el.querySelectorAll("[data-skill]").forEach((b) => b.addEventListener("click", () => { sync(); draft.skills = draft.skills.filter((s) => s !== b.dataset.skill); drawReview(); }));
    document.getElementById("skillInput").addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      const v = e.target.value.trim();
      if (v && !draft.skills.includes(v)) { sync(); draft.skills.push(v.slice(0, 40)); drawReview(); document.getElementById("skillInput").focus(); }
    });
    document.getElementById("back").addEventListener("click", () => { sync(); step = 1; draw(); });
    document.getElementById("reviewForm").addEventListener("submit", (e) => {
      e.preventDefault();
      sync();
      draft.certifications = document.getElementById("certs").value.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 20);
      const exp = document.getElementById("exp").value;
      draft.experience_years = exp === "" ? null : Math.max(0, Math.min(50, Number(exp)));
      el.querySelectorAll("[aria-invalid]").forEach((x) => x.removeAttribute("aria-invalid"));
      const errors = validateQuals(draft.qualifications);
      if (errors.length) {
        errors.forEach(([id]) => document.getElementById(id)?.setAttribute("aria-invalid", "true"));
        document.getElementById("reviewErrors").innerHTML = `<div class="callout error"><strong>Fix ${errors.length} field${errors.length === 1 ? "" : "s"}:</strong><ul style="margin:6px 0 0">${errors.map(([, m]) => `<li>${esc(m)}</li>`).join("")}</ul></div>`;
        document.getElementById(errors[0][0])?.focus();
        return;
      }
      if (!draft.qualifications.length) {
        document.getElementById("reviewErrors").innerHTML = `<div class="callout error">Add at least one qualification to check eligibility.</div>`;
        return;
      }
      step = 3; draw();
    });
  }

  function drawPersonal() {
    const el = document.getElementById("stepBody");
    el.innerHTML = `<form class="panel" id="personalForm" novalidate>
      <h2>Personal details (optional)</h2>
      <p class="small muted">Only used to compare with age limits, relaxations and state rules in notices. Leave anything blank; those checks will then say "needs verification".</p>
      <div class="grid-2">
        <div class="field" data-tip="Needed for age limits. Format: day, month, year."><label for="p-dob">Date of birth</label><input id="p-dob" type="date" max="${todayISO()}" value="${esc(draft.dob || "")}"><span class="error" id="dobErr"></span></div>
        <div class="field" data-tip="Used only to apply the age relaxation stated in each notice."><label for="p-cat">Category</label><select id="p-cat"><option value="">Prefer not to say</option>${CATEGORIES.map((c) => `<option ${draft.category === c ? "selected" : ""}>${c}</option>`).join("")}</select></div>
        <div class="field"><label for="p-state">State of domicile</label><select id="p-state"><option value="">Prefer not to say</option>${STATES.map((s) => `<option ${draft.state === s ? "selected" : ""}>${s}</option>`).join("")}</select></div>
        <label class="check" style="align-self:center"><input type="checkbox" id="p-pwbd" ${draft.pwbd ? "checked" : ""}> Person with benchmark disability (PwBD)</label>
      </div>
      <h2 style="margin-top:12px">Review</h2>
      <ul class="small" id="reviewList">${draft.qualifications.map((q) => `<li>${esc(LEVEL_LABELS[q.level] || q.level)}${q.discipline ? `, ${esc(q.discipline)}` : ""}${q.year ? `, ${q.year}` : ""}${q.percentage != null ? `, ${q.percentage}%` : ""}${q.status === "pursuing" ? " (pursuing)" : ""}</li>`).join("")}
        <li>${draft.skills.length} skills, ${draft.certifications.length} certifications, ${draft.experience_years ?? 0} years of experience</li></ul>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><button class="btn" type="button" id="back">Back</button><button class="btn btn-primary" type="submit" id="saveBtn">Save profile</button></div></form>`;
    document.getElementById("back").addEventListener("click", () => { step = 2; draw(); });
    document.getElementById("personalForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const dob = document.getElementById("p-dob").value;
      const err = document.getElementById("dobErr");
      err.textContent = "";
      if (dob && (dob > todayISO() || dob < "1950-01-01")) { err.textContent = "Enter a date of birth between 1950 and today."; document.getElementById("p-dob").setAttribute("aria-invalid", "true"); return; }
      draft.dob = dob || null;
      draft.category = document.getElementById("p-cat").value || null;
      draft.state = document.getElementById("p-state").value || null;
      draft.pwbd = document.getElementById("p-pwbd").checked;
      draft.updated = new Date().toISOString();
      const btn = document.getElementById("saveBtn");
      btn.setAttribute("aria-busy", "true"); btn.disabled = true;
      try {
        await store.saveProfile(draft);
        await state.load();
        toast("Profile saved. Each government listing now shows how it compares with your profile.");
        location.hash = "#/govt?sort=match";
      } catch (e2) {
        toast(`Could not save your profile: ${e2.message}`, { error: true });
        btn.removeAttribute("aria-busy"); btn.disabled = false;
      }
    });
  }

  draw();
}
