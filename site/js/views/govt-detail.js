import { govt, govtById } from "../data.js";
import * as state from "../state.js";
import * as store from "../store.js";
import { evaluate, CATEGORIES, LEVEL_LABELS } from "../eligibility.js";
import { reportButton } from "../govt-actions.js";
import { noticeRow, qualSummary } from "./home.js";
import { esc, safeUrl, breadcrumb, setTitle, fmtDate, statusTag, verifyTag, ICONS, toast, todayISO, relDays } from "../ui.js";

const STATES = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
  "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"];

export function reportDialog(kind, key) {
  if (!store.user()) {
    toast(store.accountsAvailable() ? "Sign in to report a problem, so the team can follow up." : "Reports need accounts, which are not enabled on this site yet.",
      store.accountsAvailable() ? { action: { label: "Sign in", run: () => { location.hash = "#/signin"; } } } : {});
    return;
  }
  const d = document.createElement("dialog");
  d.setAttribute("aria-labelledby", "rp-title");
  d.innerHTML = `<form method="dialog" id="rpForm"><div class="dialog-body"><h2 id="rp-title">Report a problem with this listing</h2>
    <div class="field"><label for="rp-reason">What is wrong?</label><select id="rp-reason" required>
      <option value="broken_link">A link does not work</option><option value="wrong_information">Information is wrong</option>
      <option value="outdated">Information is outdated</option><option value="duplicate">Listed twice</option><option value="other">Something else</option></select></div>
    <div class="field"><label for="rp-details">Details</label><textarea id="rp-details" maxlength="2000" placeholder="Which field is wrong, and what does the official notice say?"></textarea></div></div>
    <div class="dialog-actions"><button class="btn" value="cancel" formnovalidate>Cancel</button><button class="btn btn-primary" value="ok" id="rpSend">Send report</button></div></form>`;
  document.body.appendChild(d);
  d.addEventListener("close", async () => {
    if (d.returnValue === "ok") {
      try { await store.report(kind, key, d.querySelector("#rp-reason").value, d.querySelector("#rp-details").value.trim()); toast("Report sent. Thank you; an editor will check it against the official notice."); }
      catch (e) { toast(`Could not send the report: ${e.message}`, { error: true }); }
    }
    d.remove();
  });
  d.showModal();
}

function row(label, value) {
  return value == null || value === "" ? "" : `<tr><th scope="row">${esc(label)}</th><td>${value}</td></tr>`;
}

function datesTable(j) {
  const d = j.dates || {};
  const today = todayISO();
  const rows = [
    ["Notice published", j.notice_date],
    ["Applications open", d.application_start],
    ["Last date to apply", d.application_end, true],
    ["Last date for fee payment", d.fee_end],
    ["Correction window", d.correction_start ? `${fmtDate(d.correction_start)} to ${fmtDate(d.correction_end)}` : null, false, d.correction_end],
    ["Examination", d.exam ? `${fmtDate(d.exam)}${d.exam_end ? ` to ${fmtDate(d.exam_end)}` : ""}` : null, false, d.exam_end || d.exam],
    ...(j.events || []).map((e) => [({ admit_card: "Admit card", result: "Result", answer_key: "Answer key", exam: "Exam" }[e.type] || "Update"),
      `${fmtDate(e.date)}: ${esc(e.title)}${safeUrl(e.url) ? ` <a href="${safeUrl(e.url)}" rel="noopener" target="_blank">Official notice</a>` : ""}`, false, e.date]),
  ].filter((r) => r[1]);
  const body = rows.map(([label, v, key, endIso]) => {
    const iso = endIso || (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null);
    const past = iso && iso < today;
    const shown = /^\d{4}-\d{2}-\d{2}$/.test(v) ? `${fmtDate(v)} <span class="muted small">(${relDays(v)})</span>` : v;
    return `<tr class="${key ? "key" : ""}"><th scope="row">${esc(label)}</th><td class="${past ? "past" : ""}">${shown}</td></tr>`;
  }).join("");
  return `<table class="kv dates-table">${body}</table>${d.exam_note ? `<p class="small muted" style="margin-top:8px">${esc(d.exam_note)} Dates described as tentative are not confirmed.</p>` : ""}`;
}

function checklistHtml(j, profile) {
  const r = evaluate(j, profile);
  const word = { match: "Matches profile", no: "Does not match", verify: "Needs verification" };
  const mark = { match: "✓", no: "✕", verify: "?" };
  return `<div class="verdict ${r.verdict}" role="status">${esc(r.label)}</div>
    <p class="small muted">An estimate from your profile only. It is not a decision on eligibility; confirm every condition in the official notice.</p>
    <ul class="checklist">${r.checks.map((c) => `<li>
      <span class="mark s-${c.status}" aria-hidden="true">${mark[c.status]}</span>
      <div><span class="label">${esc(c.label)}</span><span class="status-word s-${c.status}">${word[c.status]}</span>
      <p>${esc(c.reason)}</p>${c.clause ? `<div class="clause">From the notice: ${esc(c.clause)}</div>` : ""}</div></li>`).join("")}</ul>`;
}

function quickFillHtml(profile) {
  return `<form class="quick-fill" id="quickFill" aria-label="Add missing details">
    <div class="field" data-tip="Used only to compare with age limits. Stored in your profile; you can delete it anytime."><label for="qf-dob">Date of birth</label><input id="qf-dob" type="date" value="${esc(profile.dob || "")}" max="${todayISO()}"></div>
    <div class="field" data-tip="Needed to apply the age relaxation in the notice. Leave blank if you prefer not to say."><label for="qf-cat">Category</label><select id="qf-cat"><option value="">Not provided</option>${CATEGORIES.map((c) => `<option ${profile.category === c ? "selected" : ""}>${c}</option>`).join("")}</select></div>
    <div class="field"><label for="qf-state">State of domicile</label><select id="qf-state"><option value="">Not provided</option>${STATES.map((s) => `<option ${profile.state === s ? "selected" : ""}>${s}</option>`).join("")}</select></div>
    <label class="check" style="align-self:end"><input type="checkbox" id="qf-pwbd" ${profile.pwbd ? "checked" : ""}> Person with benchmark disability</label>
    <div style="align-self:end"><button class="btn btn-primary" type="submit">Update and recheck</button></div>
  </form>`;
}

export async function render(app, { match }) {
  const id = match[1];
  const j = await govtById(id);
  if (!j) {
    setTitle("Recruitment not found");
    app.innerHTML = `<div class="page">${breadcrumb([{ label: "Home", href: "#/" }, { label: "Government jobs", href: "#/govt" }, { label: "Not found" }])}
      <div class="empty"><h2>This recruitment is not listed</h2><p>It may have been archived or the link is mistyped.</p><a class="btn btn-primary" href="#/govt">Browse government jobs</a></div></div>`;
    return;
  }
  setTitle(j.short_title || j.title, `${j.title} by ${j.organization}: last date, eligibility, age limit, fee and official notice.`);
  store.addRecent("govt", j.id, state.govtSnapshot(j));
  const profile = state.profile();
  const saved = state.isSaved("govt", j.id);
  const links = j.links || {};
  const age = j.age;
  const fee = j.fee;
  const relax = age?.relaxation ? Object.entries(age.relaxation).map(([k, v]) => `${esc(k)}: ${v} years`).join(", ") : null;
  const vac = j.vacancies?.total ? `${j.vacancies.total.toLocaleString("en-IN")}${j.vacancies.tentative ? " (tentative)" : ""}${j.vacancies.note ? `<div class="small muted">${esc(j.vacancies.note)}</div>` : ""}` : null;

  app.innerHTML = `<div class="page">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Government jobs", href: "#/govt" }, { label: j.category, href: `#/govt?cat=${encodeURIComponent(j.category)}` }, { label: j.short_title || j.title }])}
    <div class="detail-head">
      <div>
        <h1>${esc(j.title)}</h1>
        <p class="muted" style="margin:0">${esc(j.organization)}${j.notification_no ? `. Notice ${esc(j.notification_no)}` : ""}</p>
        <div class="tags">${statusTag(j.status)}${verifyTag(j)}<span class="tag">${esc(j.category)}</span>${j.level ? `<span class="tag">${esc(j.level)}${j.state ? `: ${esc(j.state)}` : ""}</span>` : ""}</div>
      </div>
      <div class="detail-actions">
        ${safeUrl(links.apply) ? (j.status === "closed"
          ? `<a class="btn" href="${safeUrl(links.apply)}" target="_blank" rel="noopener" id="applyLink">${ICONS.external}Official site</a>`
          : `<a class="btn btn-primary" href="${safeUrl(links.apply)}" target="_blank" rel="noopener" id="applyLink" data-guide="Opens the official application portal in a new tab. Read the notice first.">${ICONS.external}Apply on official site</a>`) : ""}
        <button class="btn" type="button" id="saveBtn" aria-pressed="${saved}">${saved ? ICONS.starFilled : ICONS.star}<span>${saved ? "Saved" : "Save"}</span></button>
        <button class="btn" type="button" id="cmpBtn">${ICONS.compare}<span>${state.compareList().includes(j.id) ? "In compare list" : "Compare"}</span></button>
      </div>
    </div>
    ${j.status === "closed" ? `<div class="callout warn" style="margin-top:12px">Applications closed on ${fmtDate(j.dates?.application_end)}. This page stays up for exam, admit card and result updates.</div>` : ""}
    <div class="verify-line ${j.verification?.status === "verified" ? "verified" : "awaiting"}">
      <strong>${j.verification?.status === "verified" ? "Checked" : "Awaiting verification"}</strong>
      <span>${esc(j.verification?.method || "")} Last checked ${fmtDate(j.verification?.checked_on)}. Source: <a href="${safeUrl(j.source?.url) || "#"}" rel="noopener" target="_blank">official ${j.source?.type === "official_page_auto" ? "page" : "notice"}</a>.</span>
    </div>
    <div class="grid-2" style="align-items:start">
      <div class="stack">
        <section class="panel" aria-labelledby="h-dates"><h2 id="h-dates">Important dates</h2>${datesTable(j)}</section>
        <section class="panel" aria-labelledby="h-elig" id="eligibilitySection"><h2 id="h-elig">Eligibility</h2>
          <table class="kv">
            ${row("Qualification", j.qualification?.options?.length ? esc(qualSummary(j)) : "Not recorded. Read the official notice.")}
            ${row("Qualification cut-off date", j.qualification?.cutoff_date ? fmtDate(j.qualification.cutoff_date) : null)}
            ${row("Minimum marks", j.qualification?.min_percentage != null ? `${j.qualification.min_percentage}%` : null)}
            ${row("Age limit", age ? `${age.min != null ? `${age.min} to ${age.max} years` : ""}${age.as_on ? ` as on ${fmtDate(age.as_on)}` : ""}${age.born_not_before ? `<div class="small muted">Born between ${fmtDate(age.born_not_before)} and ${fmtDate(age.born_not_after)}</div>` : ""}${age.note ? `<div class="small muted">${esc(age.note)}</div>` : ""}` : "Not recorded. Read the official notice.")}
            ${row("Upper age relaxation", relax)}
            ${row("Experience", j.experience_years ? `${j.experience_years} year(s)` : j.experience_years === 0 ? "Not required" : null)}
            ${row("Physical standards", j.physical_standards ? "Yes; height, chest and fitness tests apply (see notice)" : null)}
          </table>
          ${j.qualification?.notes ? `<div class="clause">From the notice: ${esc(j.qualification.notes)}</div>` : ""}
        </section>
        <section class="panel" aria-labelledby="h-post"><h2 id="h-post">Posts, vacancies and fee</h2>
          <table class="kv">
            ${row("Posts", j.posts?.length ? `<ul style="margin:0;padding-left:18px">${j.posts.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : null)}
            ${row("Vacancies", vac)}
            ${row("Pay", j.pay ? esc(j.pay) : null)}
            ${row("Position type", j.employment_type ? esc(j.employment_type) : null)}
            ${row("Application fee", fee ? `${fee.amount != null ? `Rs ${fee.amount}` : ""}${fee.exempt?.length ? `<div class="small muted">No fee: ${esc(fee.exempt.join(", "))}</div>` : ""}${fee.note ? `<div class="small muted">${esc(fee.note)}</div>` : ""}` : "Not recorded")}
          </table>
        </section>
        ${j.selection_process?.length ? `<section class="panel" aria-labelledby="h-sel"><h2 id="h-sel">Selection process</h2><ol style="margin:0;padding-left:20px">${j.selection_process.map((s) => `<li>${esc(s)}</li>`).join("")}</ol></section>` : ""}
      </div>
      <div class="stack">
        <section class="panel" aria-labelledby="h-check" id="checklistPanel" data-guide="Each condition is compared with your profile. Fill missing details below to recheck.">
          <h2 id="h-check">Your eligibility checklist</h2>
          <div id="checklist">${state.hasProfile() ? checklistHtml(j, profile) : `<p>Add your education to see which conditions you meet.</p><a class="btn btn-primary" href="#/profile">Add education or upload resume</a>`}</div>
          ${state.hasProfile() ? quickFillHtml(profile) : ""}
        </section>
        <section class="panel" aria-labelledby="h-links"><h2 id="h-links">Official links</h2>
          <div class="official-links" id="officialLinks">
            ${safeUrl(links.notification_pdf) ? `<a class="btn" href="${safeUrl(links.notification_pdf)}" target="_blank" rel="noopener" id="noticeLink">${ICONS.doc}Official notice (PDF)</a>` : ""}
            ${safeUrl(links.apply) ? `<a class="btn" href="${safeUrl(links.apply)}" target="_blank" rel="noopener">${ICONS.external}Application portal</a>` : ""}
            ${safeUrl(j.source?.url) && j.source.url !== links.notification_pdf ? `<a class="btn" href="${safeUrl(j.source.url)}" target="_blank" rel="noopener">${ICONS.external}Source page</a>` : ""}
          </div>
          <p class="small muted" style="margin-top:10px">This site is not affiliated with ${esc(j.org_short || j.organization)}. Apply only through the official portal.</p>
          <div style="margin-top:8px">${reportButton("govt", j.id)}</div>
        </section>
        <section class="panel" aria-labelledby="h-rel"><h2 id="h-rel">Related recruitments</h2><div id="related"></div></section>
      </div>
    </div></div>`;

  document.getElementById("saveBtn").addEventListener("click", async (e) => {
    try {
      const now = await state.toggleSave("govt", j.id, state.govtSnapshot(j));
      e.currentTarget.setAttribute("aria-pressed", String(now));
      e.currentTarget.innerHTML = `${now ? ICONS.starFilled : ICONS.star}<span>${now ? "Saved" : "Save"}</span>`;
      toast(now ? "Saved. You will get a reminder before the last date." : "Removed from saved jobs");
    } catch (err) { toast(`Could not save: ${err.message}`, { error: true }); }
  });
  document.getElementById("cmpBtn").addEventListener("click", (e) => {
    if (!state.toggleCompare(j.id)) { toast("You can compare up to four jobs."); return; }
    e.currentTarget.querySelector("span").textContent = state.compareList().includes(j.id) ? "In compare list" : "Compare";
  });
  app.querySelector("[data-report]").addEventListener("click", () => reportDialog("govt", j.id));

  const qf = document.getElementById("quickFill");
  if (qf) {
    qf.addEventListener("submit", async (e) => {
      e.preventDefault();
      const dob = document.getElementById("qf-dob").value;
      if (dob && dob > todayISO()) { toast("Date of birth cannot be in the future.", { error: true }); return; }
      const next = { ...state.profile(), dob: dob || null, category: document.getElementById("qf-cat").value || null,
        state: document.getElementById("qf-state").value || null, pwbd: document.getElementById("qf-pwbd").checked };
      try {
        await store.saveProfile(next);
        await state.load();
        document.getElementById("checklist").innerHTML = checklistHtml(j, state.profile());
        toast("Profile updated and checklist recalculated.");
      } catch (err) { toast(`Could not update your profile: ${err.message}`, { error: true }); }
    });
  }

  const { jobs } = await govt();
  const related = jobs.filter((x) => x.id !== j.id && (x.category === j.category || x.org_short === j.org_short) && x.status !== "closed").slice(0, 4);
  document.getElementById("related").innerHTML = related.length ? `<ul class="notice-list">${related.map((x) => noticeRow(x)).join("")}</ul>`
    : `<p class="muted">No other open recruitments in ${esc(j.category)} right now. <a href="#/govt?cat=${encodeURIComponent(j.category)}">See all ${esc(j.category)} listings</a>.</p>`;
}
