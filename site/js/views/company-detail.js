import { companyJob, companyScore } from "../data.js";
import * as state from "../state.js";
import * as store from "../store.js";
import { reportButton } from "../govt-actions.js";
import { reportDialog } from "./govt-detail.js";
import { esc, safeUrl, breadcrumb, setTitle, fmtDate, ICONS, toast } from "../ui.js";

// Descriptions come from third-party feeds: parse them in an inert document
// (no scripts, no image loads) and keep only the text.
function text(html) {
  const doc = new DOMParser().parseFromString(String(html || "").replace(/<(br|\/p|\/li|\/h\d)>/gi, "\n$&"), "text/html");
  return (doc.body.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
}

export async function render(app, { match }) {
  const key = decodeURIComponent(match[1]);
  let j;
  try { j = await companyJob(key); } catch {
    setTitle("Job not found");
    app.innerHTML = `<div class="page"><div class="empty"><h2>This job is no longer listed</h2><p>It was probably filled or removed by the company.</p><a class="btn btn-primary" href="#/jobs">Browse company jobs</a></div></div>`;
    return;
  }
  j.key = key;
  setTitle(`${j.job_title} at ${j.company}`, `${j.job_title} at ${j.company}, ${j.location_raw}. Apply on the official careers site.`);
  store.addRecent("company", key, state.companySnapshot(j));
  const sc = companyScore(j, state.profile());
  const saved = state.isSaved("company", key);
  const rows = [
    ["Location", j.location_raw], ["Work mode", j.work_mode], ["Employment type", j.employment_type], ["Experience", j.experience_raw],
    ["Salary", j.salary_raw], ["Posted", j.date_posted ? fmtDate(String(j.date_posted).slice(0, 10)) : null],
    ["Education", (j.education_required || []).join(", ")], ["Branch", (j.branch_required || []).join(", ")],
  ].filter(([, v]) => v && v !== "Not specified" && v !== "Not disclosed");
  app.innerHTML = `<div class="page">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Company jobs", href: "#/jobs" }, { label: j.company, href: `#/jobs?company=${encodeURIComponent(j.company)}` }, { label: j.job_title }])}
    <div class="detail-head"><div><h1>${esc(j.job_title)}</h1><p class="muted" style="margin:0">${esc(j.company)}</p>
      <div class="tags">${j.fresher_eligible ? '<span class="tag">Fresher</span>' : ""}${j.internship ? '<span class="tag">Internship</span>' : ""}${j.country_scope ? `<span class="tag">${esc(j.country_scope)}</span>` : ""}${j.seniority && j.seniority !== "Unknown" ? `<span class="tag">${esc(j.seniority)}</span>` : ""}</div></div>
      <div class="detail-actions">${safeUrl(j.apply_url || j.job_url) ? `<a class="btn btn-primary" href="${safeUrl(j.apply_url || j.job_url)}" target="_blank" rel="noopener noreferrer">${ICONS.external}Apply on company site</a>` : ""}
        <button class="btn" type="button" id="saveBtn" aria-pressed="${saved}">${saved ? ICONS.starFilled : ICONS.star}<span>${saved ? "Saved" : "Save"}</span></button></div></div>
    <div class="grid-2" style="margin-top:16px;align-items:start">
      <section class="panel"><h2>Job description</h2><div class="desc">${esc(text(j.job_description) || "The company did not publish a description in its feed. Open the company site for details.")}</div></section>
      <div class="stack">
        <section class="panel"><h2>Match for your profile</h2><p><strong>${sc.score}/100</strong>${sc.reasons.length ? `: ${esc(sc.reasons.join(", "))}` : ""}</p>
          ${state.hasProfile() ? "" : `<p class="small muted"><a href="#/profile">Add your skills</a> for a personal score.</p>`}
          ${(j.skills_required || []).length ? `<h3 style="margin-top:12px">Skills mentioned</h3><div class="chips">${j.skills_required.map((s) => `<span class="chip" style="padding-right:10px">${esc(s)}</span>`).join("")}</div>` : ""}</section>
        <section class="panel"><h2>Details</h2><table class="kv">${rows.map(([k, v]) => `<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`).join("")}</table>
          <p class="small muted" style="margin-top:10px">Source: ${esc(j.source_website || "company careers site")}. First seen ${fmtDate(String(j.first_seen || "").slice(0, 10)) || "recently"}.</p>
          ${reportButton("company", key)}</section>
      </div></div></div>`;
  document.getElementById("saveBtn").addEventListener("click", async (e) => {
    try {
      const now = await state.toggleSave("company", key, state.companySnapshot(j));
      e.currentTarget.setAttribute("aria-pressed", String(now));
      e.currentTarget.innerHTML = `${now ? ICONS.starFilled : ICONS.star}<span>${now ? "Saved" : "Save"}</span>`;
    } catch (err) { toast(`Could not save: ${err.message}`, { error: true }); }
  });
  app.querySelector("[data-report]").addEventListener("click", () => reportDialog("company", key));
}
