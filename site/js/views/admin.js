import * as store from "../store.js";
import { recruitmentStatus } from "../eligibility.js";
import { CATEGORY_LIST } from "../govt-filter.js";
import { invalidateGovt } from "../data.js";
import { esc, safeUrl, breadcrumb, setTitle, fmtDate, toast, todayISO, confirmDialog, promptDialog } from "../ui.js";

const TABS = [["records", "Records"], ["edit", "Add record"], ["reports", "Reports"], ["links", "Broken links"], ["audit", "Audit history"]];
const LEVELS = ["10th", "12th", "iti", "diploma", "graduate", "engineering", "postgraduate", "phd"];
const isDate = (v) => /^\d{4}-\d{2}-\d{2}$/.test(v || "");
const isUrl = (v) => /^https?:\/\/\S+$/.test(v || "");

// Mirrors scripts/govt_schema.py so editors see the same errors CI would raise.
export function validateRecord(r) {
  const e = [];
  if (!/^[a-z0-9][a-z0-9-]{2,80}$/.test(r.id || "")) e.push("ID: lowercase letters, digits and dashes (3-81 characters).");
  if (!r.title?.trim()) e.push("Title is required.");
  if (!r.organization?.trim()) e.push("Organisation is required.");
  if (!CATEGORY_LIST.includes(r.category)) e.push("Choose a recruitment type.");
  if (!isUrl(r.source?.url)) e.push("Source URL must be the official notice or page (http or https).");
  if (!["verified", "awaiting", "revised"].includes(r.verification?.status)) e.push("Choose a verification status.");
  if (!isDate(r.verification?.checked_on)) e.push("Last checked date is required.");
  for (const [k, v] of Object.entries(r.dates || {})) if (v && k !== "exam_note" && !isDate(v)) e.push(`Date "${k}" must be YYYY-MM-DD.`);
  if (r.dates?.application_start && r.dates?.application_end && r.dates.application_start > r.dates.application_end) e.push("Applications cannot open after the last date.");
  for (const [k, v] of Object.entries(r.links || {})) if (v && !isUrl(v)) e.push(`Link "${k}" must start with http:// or https://.`);
  for (const o of r.qualification?.options || []) if (!LEVELS.includes(o.level)) e.push(`Qualification level "${o.level}" is not one of ${LEVELS.join(", ")}.`);
  return e;
}

export async function render(app, { match, params }) {
  setTitle("Admin");
  const tab = match[1] || "records";
  const head = `${breadcrumb([{ label: "Home", href: "#/" }, { label: "Admin" }])}<h1>Admin</h1>`;
  if (!store.accountsAvailable()) {
    app.innerHTML = `<div class="page" style="max-width:760px">${head}
      <p>The admin tools need the account database (Supabase), which is not connected on this site yet.</p>
      <p>Until then, government records are edited in <code>data/govt_jobs.json</code> in the repository. Every change goes through a pull request, CI runs <code>scripts/validate_govt_jobs.py</code>, and the history of the file is the audit trail.</p></div>`;
    return;
  }
  if (!store.user()) { app.innerHTML = `<div class="page">${head}<p>Sign in with an editor account.</p><a class="btn btn-primary" href="#/signin">Sign in</a></div>`; return; }
  if (!store.isStaff()) { app.innerHTML = `<div class="page">${head}<p>Your account does not have editor access. An administrator can grant it.</p></div>`; return; }

  app.innerHTML = `<div class="page">${head}
    <nav aria-label="Admin sections" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px">${TABS.map(([k, l]) =>
      `<a class="btn btn-small" href="#/admin/${k}" ${tab === k ? 'aria-current="page" style="border-color:var(--ink);color:var(--ink)"' : ""}>${l}</a>`).join("")}</nav>
    <div id="adminBody"><div class="skeleton" style="width:60%"></div></div></div>`;
  const body = document.getElementById("adminBody");
  try {
    if (tab === "records") await records(body, params);
    else if (tab === "edit") await editor(body, params.get("id"));
    else if (tab === "reports") await reports(body, params.get("status") || "open");
    else if (tab === "links") await links(body);
    else if (tab === "audit") await audit(body);
  } catch (e) {
    body.innerHTML = `<div class="callout error">${esc(e.message)}</div>`;
  }
}

async function records(body, params) {
  const rows = await store.admin.list();
  const view = params.get("view") || "all";
  const key = (r) => `${(r.data.organization || "").toLowerCase()}|${(r.data.title || "").toLowerCase().replace(/\W+/g, " ").trim()}`;
  const counts = {};
  rows.forEach((r) => { counts[key(r)] = (counts[key(r)] || 0) + 1; });
  const enriched = rows.map((r) => ({ ...r, status: recruitmentStatus(r.data), dup: counts[key(r)] > 1 }));
  const views = {
    all: ["All", () => true], drafts: ["Drafts to review", (r) => !r.published && !r.archived], published: ["Published", (r) => r.published && !r.archived],
    awaiting: ["Awaiting verification", (r) => r.data.verification?.status !== "verified" && !r.archived],
    expired: ["Closed but still published", (r) => r.published && !r.archived && r.status === "closed"],
    duplicates: ["Possible duplicates", (r) => r.dup], archived: ["Archived", (r) => r.archived],
  };
  const list = enriched.filter(views[view]?.[1] || views.all[1]);
  body.innerHTML = `<div class="toolbar"><div style="display:flex;gap:6px;flex-wrap:wrap">${Object.entries(views).map(([k, [l, f]]) =>
    `<a class="btn btn-small" href="#/admin/records?view=${k}" ${view === k ? 'aria-current="page" style="border-color:var(--ink);color:var(--ink)"' : ""}>${l} (${enriched.filter(f).length})</a>`).join("")}</div>
    <a class="btn btn-primary btn-small" href="#/admin/edit">Add record</a></div>
    ${list.length ? `<div class="compare-wrap"><table class="compare" style="min-width:760px"><thead><tr><th>Title</th><th>Status</th><th>Verification</th><th>Last date</th><th>Updated</th><th>Actions</th></tr></thead><tbody>
    ${list.map((r) => `<tr><td><a href="#/admin/edit?id=${esc(r.id)}">${esc(r.data.short_title || r.data.title)}</a><div class="small muted">${esc(r.id)}${r.source_kind === "automated" ? ", automated" : ""}${r.dup ? ", possible duplicate" : ""}</div></td>
      <td>${r.archived ? "Archived" : r.published ? "Published" : "Draft"}<div class="small muted">${esc(r.status)}</div></td>
      <td>${esc(r.data.verification?.status || "")}<div class="small muted">${fmtDate(r.data.verification?.checked_on)}</div></td>
      <td>${fmtDate(r.data.dates?.application_end) || "-"}</td><td class="small">${fmtDate(String(r.updated_at).slice(0, 10))}</td>
      <td style="white-space:nowrap">${r.archived ? `<button class="btn btn-small" data-flag="${esc(r.id)}" data-v='{"archived":false}'>Restore</button>`
        : `${r.published ? `<button class="btn btn-small" data-flag="${esc(r.id)}" data-v='{"published":false}'>Unpublish</button>` : `<button class="btn btn-small" data-flag="${esc(r.id)}" data-v='{"published":true}'>Publish</button>`}
        <button class="btn btn-small btn-quiet" data-flag="${esc(r.id)}" data-v='{"archived":true,"published":false}'>Archive</button>`}</td></tr>`).join("")}</tbody></table></div>`
    : `<p class="muted">No records in this view.</p>`}`;
  body.querySelectorAll("[data-flag]").forEach((b) => b.addEventListener("click", async () => {
    const flags = JSON.parse(b.dataset.v);
    if (flags.published) {
      const r = rows.find((x) => x.id === b.dataset.flag);
      const errs = validateRecord({ ...r.data, id: r.id });
      if (errs.length) { toast(`Fix before publishing: ${errs[0]}`, { error: true }); return; }
    }
    try { await store.admin.setFlags(b.dataset.flag, flags); invalidateGovt(); toast("Updated."); await records(body, params); }
    catch (e) { toast(e.message, { error: true }); }
  }));
}

function parseJSON(id, fallback) {
  const v = document.getElementById(id).value.trim();
  if (!v) return fallback;
  return JSON.parse(v);
}

async function editor(body, id) {
  let row = null;
  if (id) row = (await store.admin.list()).find((r) => r.id === id) || null;
  const d = row?.data || { verification: { status: "awaiting", checked_on: todayISO() }, dates: {}, links: {}, source: {} };
  const dd = d.dates || {};
  const f = (k, label, v, type = "text", hint = "") => `<div class="field"><label for="e-${k}">${label}</label><input id="e-${k}" type="${type}" value="${esc(v ?? "")}">${hint ? `<span class="hint">${hint}</span>` : ""}</div>`;
  body.innerHTML = `<form class="stack" id="editForm" novalidate>
    ${row ? `<p class="muted">Editing <strong>${esc(row.id)}</strong> (${row.archived ? "archived" : row.published ? "published" : "draft"}). Every save is recorded in the audit history.</p>` : `<p class="muted">New record. It is saved as a draft until you publish it.</p>`}
    <section class="panel"><h2>Notice</h2><div class="grid-2">
      ${f("id", "ID", row?.id || d.id || "", "text", "Lowercase, dashes, e.g. ssc-chsl-2026. Cannot change after publishing.")}
      ${f("title", "Official title", d.title)}${f("short_title", "Short title", d.short_title)}${f("organization", "Organisation", d.organization)}
      ${f("org_short", "Organisation short name", d.org_short)}
      <div class="field"><label for="e-category">Recruitment type</label><select id="e-category"><option value="">Choose</option>${CATEGORY_LIST.map((c) => `<option ${d.category === c ? "selected" : ""}>${c}</option>`).join("")}</select></div>
      <div class="field"><label for="e-level">Level</label><select id="e-level"><option ${d.level === "Central" ? "selected" : ""}>Central</option><option ${d.level === "State" ? "selected" : ""}>State</option></select></div>
      ${f("state", "State (state recruitments only)", d.state)}${f("notification_no", "Notification number", d.notification_no)}${f("notice_date", "Notice date", d.notice_date, "date")}
      ${f("employment_type", "Position type", d.employment_type, "text", "Permanent or Contract")}${f("pay", "Pay", d.pay)}
      ${f("vac_total", "Total vacancies", d.vacancies?.total, "number")}<label class="check"><input type="checkbox" id="e-vac_tent" ${d.vacancies?.tentative ? "checked" : ""}> Vacancies are tentative</label>
    </div></section>
    <section class="panel"><h2>Dates</h2><div class="grid-3">
      ${f("d_application_start", "Applications open", dd.application_start, "date")}${f("d_application_end", "Last date to apply", dd.application_end, "date")}${f("d_fee_end", "Fee last date", dd.fee_end, "date")}
      ${f("d_correction_start", "Correction opens", dd.correction_start, "date")}${f("d_correction_end", "Correction closes", dd.correction_end, "date")}${f("d_exam", "Exam date (confirmed only)", dd.exam, "date")}
      ${f("d_exam_end", "Exam end date", dd.exam_end, "date")}</div>
      ${f("d_exam_note", "Schedule note (tentative wording from the notice)", dd.exam_note)}
      <div class="field"><label for="e-events">Updates: admit cards, answer keys, results (JSON list)</label><textarea id="e-events" rows="3" placeholder='[{"type":"result","date":"2026-12-01","title":"Tier-I result","url":"https://..."}]'>${esc(d.events?.length ? JSON.stringify(d.events, null, 1) : "")}</textarea></div></section>
    <section class="panel"><h2>Eligibility</h2>
      <div class="field"><label for="e-qual">Qualification (JSON)</label><textarea id="e-qual" rows="6" placeholder='{"options":[{"level":"graduate","disciplines":[],"subjects":[]}],"cutoff_date":"2026-08-01","min_percentage":null,"notes":"Exact wording from the notice"}'>${esc(d.qualification ? JSON.stringify(d.qualification, null, 1) : "")}</textarea><span class="hint">Levels: ${LEVELS.join(", ")}. Put the notice wording in "notes".</span></div>
      <div class="field"><label for="e-age">Age (JSON)</label><textarea id="e-age" rows="4" placeholder='{"min":18,"max":27,"as_on":"2026-08-01","born_not_before":"1999-08-02","born_not_after":"2008-08-01","relaxation":{"SC":5,"ST":5,"OBC":3,"PwBD":10}}'>${esc(d.age ? JSON.stringify(d.age, null, 1) : "")}</textarea></div>
      <div class="grid-2">${f("exp", "Experience required (years)", d.experience_years, "number")}<label class="check"><input type="checkbox" id="e-phys" ${d.physical_standards ? "checked" : ""}> Physical / medical standards apply</label></div></section>
    <section class="panel"><h2>Posts, fee and selection</h2>
      <div class="field"><label for="e-posts">Posts (one per line)</label><textarea id="e-posts" rows="3">${esc((d.posts || []).join("\n"))}</textarea></div>
      <div class="field"><label for="e-fee">Fee (JSON)</label><textarea id="e-fee" rows="2" placeholder='{"amount":100,"exempt":["Women","SC","ST"],"note":null}'>${esc(d.fee ? JSON.stringify(d.fee) : "")}</textarea></div>
      <div class="field"><label for="e-sel">Selection process (one stage per line, in order)</label><textarea id="e-sel" rows="4">${esc((d.selection_process || []).join("\n"))}</textarea></div></section>
    <section class="panel"><h2>Official links and verification</h2><div class="grid-2">
      ${f("l_pdf", "Official notice PDF", d.links?.notification_pdf, "url")}${f("l_apply", "Official application portal", d.links?.apply, "url")}
      ${f("src", "Source (official notice or page)", d.source?.url, "url")}
      <div class="field"><label for="e-vstatus">Verification</label><select id="e-vstatus">
        <option value="verified" ${d.verification?.status === "verified" ? "selected" : ""}>Checked against the official notice</option>
        <option value="awaiting" ${d.verification?.status !== "verified" && d.verification?.status !== "revised" ? "selected" : ""}>Awaiting verification</option>
        <option value="revised" ${d.verification?.status === "revised" ? "selected" : ""}>Revised notice, re-check pending</option></select></div>
      ${f("vdate", "Last checked on", d.verification?.checked_on || todayISO(), "date")}${f("vmethod", "How it was checked", d.verification?.method)}</div></section>
    <div id="editErrors" role="alert"></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" type="submit" data-publish="false">Save as draft</button><button class="btn btn-primary" type="submit" data-publish="true">Save and publish</button>
      ${row && store.role() === "admin" ? `<button class="btn btn-danger" type="button" id="del">Delete permanently</button>` : ""}<a class="btn btn-quiet" href="#/admin/records">Cancel</a></div>
  </form>`;

  const val = (k) => document.getElementById(`e-${k}`).value.trim() || null;
  const form = document.getElementById("editForm");
  let publish = false;
  form.querySelectorAll("[data-publish]").forEach((b) => b.addEventListener("click", () => { publish = b.dataset.publish === "true"; }));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errBox = document.getElementById("editErrors");
    let rec;
    try {
      rec = {
        ...d, id: val("id"), title: val("title"), short_title: val("short_title"), organization: val("organization"), org_short: val("org_short"),
        category: val("category"), level: val("level"), state: val("state"), notification_no: val("notification_no"), notice_date: val("notice_date"),
        employment_type: val("employment_type"), pay: val("pay"),
        vacancies: val("vac_total") ? { total: Number(val("vac_total")), tentative: document.getElementById("e-vac_tent").checked, note: d.vacancies?.note || null } : null,
        dates: Object.fromEntries(["application_start", "application_end", "fee_end", "correction_start", "correction_end", "exam", "exam_end", "exam_note"].map((k) => [k, val(`d_${k}`)])),
        events: parseJSON("e-events", []), qualification: parseJSON("e-qual", null), age: parseJSON("e-age", null), fee: parseJSON("e-fee", null),
        experience_years: val("exp") == null ? null : Number(val("exp")), physical_standards: document.getElementById("e-phys").checked,
        posts: document.getElementById("e-posts").value.split("\n").map((s) => s.trim()).filter(Boolean),
        selection_process: document.getElementById("e-sel").value.split("\n").map((s) => s.trim()).filter(Boolean),
        links: { notification_pdf: val("l_pdf"), apply: val("l_apply") }, source: { url: val("src"), type: d.source?.type || "official_notice" },
        verification: { status: val("vstatus"), checked_on: val("vdate"), method: val("vmethod") || "" },
      };
    } catch (err) {
      errBox.innerHTML = `<div class="callout error">One of the JSON fields is not valid JSON: ${esc(err.message)}</div>`;
      return;
    }
    const errors = validateRecord(rec);
    if (errors.length) { errBox.innerHTML = `<div class="callout error"><strong>Fix before saving:</strong><ul style="margin:6px 0 0">${errors.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`; return; }
    if (row && row.id !== rec.id) { errBox.innerHTML = `<div class="callout error">The ID cannot be changed. Create a new record instead.</div>`; return; }
    try {
      const { id: rid, ...data } = rec;
      await store.admin.upsert(rid, data, { published: publish, archived: false, source_kind: row?.source_kind || "manual" });
      invalidateGovt();
      toast(publish ? "Saved and published." : "Saved as draft.");
      location.hash = `#/admin/edit?id=${encodeURIComponent(rid)}&r=${Date.now()}`;
    } catch (err) { errBox.innerHTML = `<div class="callout error">Could not save: ${esc(err.message)}</div>`; }
  });
  document.getElementById("del")?.addEventListener("click", async () => {
    if (!(await confirmDialog("Delete this record permanently?", "Archiving keeps it in history; deleting removes it. The audit log keeps a copy.", "Delete", true))) return;
    try { await store.admin.remove(row.id); invalidateGovt(); toast("Deleted."); location.hash = "#/admin/records"; } catch (e) { toast(e.message, { error: true }); }
  });
}

async function reports(body, status) {
  const list = await store.admin.reports(status);
  body.innerHTML = `<div class="toolbar"><div style="display:flex;gap:6px">${["open", "resolved", "dismissed"].map((s) =>
    `<a class="btn btn-small" href="#/admin/reports?status=${s}" ${s === status ? 'aria-current="page" style="border-color:var(--ink);color:var(--ink)"' : ""}>${s[0].toUpperCase() + s.slice(1)}</a>`).join("")}</div></div>
    ${list.length ? `<div class="panel" style="padding:0">${list.map((r) => `<div class="notif"><span class="dot" aria-hidden="true"></span>
      <div><strong>${esc(r.reason.replace("_", " "))}</strong>: <a href="${r.job_kind === "govt" ? `#/govt/${esc(r.job_key)}` : `#/jobs/${encodeURIComponent(r.job_key)}`}">${esc(r.job_key)}</a>
        <div class="small">${esc(r.details || "No details given.")}</div><div class="small muted">${fmtDate(String(r.created_at).slice(0, 10))}${r.resolution_note ? `. Note: ${esc(r.resolution_note)}` : ""}</div></div>
      ${status === "open" ? `<div style="display:flex;gap:6px;flex-wrap:wrap"><button class="btn btn-small" data-res="${esc(r.id)}" data-s="resolved">Resolve</button><button class="btn btn-small btn-quiet" data-res="${esc(r.id)}" data-s="dismissed">Dismiss</button></div>` : "<span></span>"}</div>`).join("")}</div>`
      : `<p class="muted">No ${status} reports.</p>`}`;
  body.querySelectorAll("[data-res]").forEach((b) => b.addEventListener("click", async () => {
    let note = "";
    if (b.dataset.s === "resolved") {
      note = await promptDialog("Resolve report", "What did you change?", "", "Resolve");
      if (note == null) return;
    }
    try { await store.admin.resolve(b.dataset.res, b.dataset.s, note); toast(`Report ${b.dataset.s}.`); await reports(body, status); } catch (e) { toast(e.message, { error: true }); }
  }));
}

async function links(body) {
  const list = await store.admin.linkChecks();
  body.innerHTML = list.length ? `<div class="compare-wrap"><table class="compare"><thead><tr><th>Record</th><th>URL</th><th>HTTP status</th><th>Checked</th></tr></thead><tbody>
    ${list.map((l) => `<tr><td><a href="#/admin/edit?id=${esc(l.job_id || "")}">${esc(l.job_id || "")}</a></td><td style="word-break:break-all">${safeUrl(l.url) ? `<a href="${safeUrl(l.url)}" target="_blank" rel="noopener">${esc(l.url)}</a>` : esc(l.url)}</td><td>${esc(l.status ?? "no response")}</td><td>${fmtDate(String(l.checked_at).slice(0, 10))}</td></tr>`).join("")}</tbody></table></div>`
    : `<p class="muted">No broken official links in the last check. Links are checked daily by the build workflow.</p>`;
}

async function audit(body) {
  const list = await store.admin.audit(150);
  body.innerHTML = list.length ? `<div class="compare-wrap"><table class="compare"><thead><tr><th>When</th><th>Record</th><th>Action</th><th>By</th></tr></thead><tbody>
    ${list.map((a) => `<tr><td>${esc(new Date(a.at).toLocaleString())}</td><td><a href="#/admin/edit?id=${esc(a.row_id)}">${esc(a.row_id)}</a></td><td>${esc(a.action)}</td><td class="small">${esc(a.actor || "automation")}</td></tr>`).join("")}</tbody></table></div>`
    : `<p class="muted">No changes recorded yet.</p>`;
}
