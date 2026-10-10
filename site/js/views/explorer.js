import { govt } from "../data.js";
import * as state from "../state.js";
import { checkEducation, LEVEL_LABELS } from "../eligibility.js";
import { noticeRow } from "./home.js";
import { wireNoticeActions } from "../govt-actions.js";
import { esc, breadcrumb, setTitle } from "../ui.js";
import { setQuery } from "../app.js";

// Typical routes by qualification. These describe common patterns, not the
// rules of any specific vacancy; each recruitment's notice is what counts.
const PATHS = {
  "10th": [
    ["Constable and rifleman posts", "Central armed police forces and Assam Rifles (SSC GD Constable).", "Defence"],
    ["Multi-tasking staff", "Group C non-technical posts in central offices (SSC MTS).", "SSC"],
    ["Railway Level-1 posts", "Track maintainer, helper and similar posts through the Railway Recruitment Boards.", "Railways"],
    ["Navy and Coast Guard sailor entries", "Some entries such as Coast Guard Navik (Domestic Branch) accept 10th.", "Defence"],
  ],
  "12th": [
    ["Clerical and data entry posts", "LDC / JSA and data entry operator (SSC CHSL), stenographer (SSC Steno).", "SSC"],
    ["Defence entries after 12th", "NDA (UPSC), Coast Guard Navik (GD, needs Maths and Physics), Agniveer entries with subject rules.", "Defence"],
    ["Railway non-technical (12th level)", "Clerk and ticket clerk posts through the Railway Recruitment Boards.", "Railways"],
  ],
  iti: [
    ["Railway technical posts", "Assistant loco pilot and technician posts usually ask for ITI in specified trades.", "Railways"],
    ["Apprenticeships", "PSUs and research organisations take trade apprentices through official notices.", "PSU"],
  ],
  diploma: [
    ["Junior engineer posts", "SSC JE and railway JE posts in civil, mechanical and electrical streams (the notice lists accepted qualifications).", "SSC"],
    ["Technician and technical assistant", "ISRO centres, DRDO labs and PSUs recruit diploma holders as technical assistants.", "Research"],
    ["Coast Guard Yantrik", "Diploma in electrical, mechanical or electronics engineering.", "Defence"],
  ],
  graduate: [
    ["Graduate-level SSC posts", "Inspector, assistant section officer and similar posts (SSC CGL); sub-inspector posts (SSC CPO).", "SSC"],
    ["Banking", "Probationary officer and clerk recruitments through IBPS and bank notices.", "Banking"],
    ["Civil services and defence officer entries", "UPSC civil services, CDS and AFCAT accept graduates (age and subject rules apply).", "UPSC"],
    ["State public service commissions", "State-level administrative and subordinate services.", "State"],
  ],
  engineering: [
    ["Engineering services", "UPSC Engineering Services (ESE) for B.E. / B.Tech in civil, mechanical, electrical and electronics.", "UPSC"],
    ["Scientist / engineer posts", "ISRO and DRDO recruit graduate engineers (Scientist / Engineer 'SC' and similar).", "Research"],
    ["PSU engineer trainees", "Many PSUs recruit engineering graduates using GATE scores; each PSU publishes its own notice.", "PSU"],
    ["Project engineer (contract)", "C-DAC and research labs recruit project engineers on contract.", "Research"],
  ],
  postgraduate: [
    ["Research fellowships", "Junior research fellow and project positions at research organisations and institutes.", "Research"],
    ["Translator and specialist posts", "Some SSC posts need a master's degree in a specific subject (for example Hindi Translator).", "SSC"],
    ["Teaching", "College teaching posts generally require NET / SET as per UGC rules; check each notice.", "Teaching"],
  ],
  phd: [
    ["Scientist and faculty posts", "Research organisations and institutes recruit PhD holders for scientist and faculty positions.", "Research"],
  ],
};
const ORDER = ["10th", "12th", "iti", "diploma", "graduate", "engineering", "postgraduate", "phd"];

export async function render(app, { params }) {
  setTitle("Career explorer", "See which kinds of government recruitment commonly accept your qualification, and which current listings you may qualify for.");
  const prof = state.profile();
  const highest = (prof.qualifications || []).reduce((a, q) => (ORDER.indexOf(q.level) > ORDER.indexOf(a?.level) ? q : a), null);
  const level = params.get("level") || highest?.level || "graduate";
  const discipline = params.get("discipline") ?? highest?.discipline ?? "";
  app.innerHTML = `<div class="page">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Career explorer" }])}
    <div class="page-head"><h1>Career explorer</h1>
      <p>Pick a qualification to see the kinds of recruitment that commonly accept it, then the current listings whose education rule it meets. Common patterns are not guarantees; each notice sets its own conditions.</p></div>
    <form class="panel" id="exForm" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;align-items:end">
      <div class="field" style="margin:0"><label for="ex-level">Qualification</label><select id="ex-level">${ORDER.map((l) => `<option value="${l}" ${l === level ? "selected" : ""}>${LEVEL_LABELS[l]}</option>`).join("")}</select></div>
      <div class="field" style="margin:0" data-tip="Your stream or subject, for example computer science, mechanical or commerce."><label for="ex-disc">Discipline (optional)</label><input id="ex-disc" type="text" value="${esc(discipline)}" placeholder="e.g. electrical"></div>
    </form>
    <div class="grid-2" style="margin-top:16px;align-items:start">
      <section class="panel"><h2>Commonly open to this qualification</h2><div id="paths"></div></section>
      <section class="panel"><h2>Current listings your education may meet</h2><p class="small muted">Education rule only. Age, category and other conditions are checked on each job page.</p><div id="matches"></div></section>
    </div></div>`;

  const { jobs } = await govt();
  const byId = Object.fromEntries(jobs.map((j) => [j.id, j]));
  const draw = () => {
    if (!document.getElementById("ex-level")) return;
    const lv = document.getElementById("ex-level").value;
    const disc = document.getElementById("ex-disc").value.trim();
    setQuery(new URLSearchParams({ level: lv, ...(disc ? { discipline: disc } : {}) }));
    const idx = ORDER.indexOf(lv);
    const own = PATHS[lv] || [];
    const lower = ORDER.slice(0, idx).filter((l) => l !== "iti" || lv === "iti").flatMap((l) => (PATHS[l] || []).slice(0, 1).map((p) => [...p, l]));
    document.getElementById("paths").innerHTML = `<ul class="mini-list">${own.map(([t, d, cat]) =>
      `<li><div><strong>${esc(t)}</strong><div class="meta">${esc(d)}</div></div><a class="btn btn-small" href="#/govt?cat=${encodeURIComponent(cat)}">${esc(cat)} listings</a></li>`).join("")}</ul>
      ${lower.length ? `<h3 style="margin-top:16px">Lower-level routes that are usually also open</h3><p class="small muted">Many notices accept a higher qualification for posts that ask for a lower one, but some do not. Check each notice.</p>
      <ul class="mini-list">${lower.map(([t, , cat, l]) => `<li><span>${esc(t)} <span class="meta">(${LEVEL_LABELS[l]})</span></span><a class="btn btn-small" href="#/govt?cat=${encodeURIComponent(cat)}">${esc(cat)}</a></li>`).join("")}</ul>` : ""}`;
    const profile = { qualifications: [{ level: lv, discipline: disc || null, status: "completed" }] };
    const hits = jobs.filter((j) => j.status !== "closed" && checkEducation(j, profile).status !== "no");
    const el = document.getElementById("matches");
    el.innerHTML = hits.length ? `<ul class="notice-list">${hits.slice(0, 10).map((j) => noticeRow(j, { showEval: false })).join("")}</ul>${hits.length > 10 ? `<p style="margin-top:8px"><a href="#/govt?qual=${lv}">See all ${hits.length}</a></p>` : ""}`
      : `<p class="muted">No open or upcoming listing currently accepts this qualification. <a href="#/govt?status=closed">Past recruitments</a> show what to expect next cycle.</p>`;
    wireNoticeActions(el, byId);
  };
  document.getElementById("exForm").addEventListener("input", draw);
  document.getElementById("exForm").addEventListener("submit", (e) => e.preventDefault());
  draw();
}
