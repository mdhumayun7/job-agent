import * as store from "../store.js";
import * as state from "../state.js";
import { govt, companyIndex, companyScore } from "../data.js";
import { evaluate, verdictRank } from "../eligibility.js";
import { describeFilters, CATEGORY_LIST } from "../govt-filter.js";
import { computeNotifications } from "../notify.js";
import { esc, breadcrumb, setTitle, fmtDate, toast, confirmDialog, relDays, statusTag } from "../ui.js";

const SECTIONS = {
  recommended: "Recommended government jobs",
  deadlines: "Upcoming deadlines",
  saved: "Saved jobs",
  updates: "Recent updates",
  searches: "Saved searches",
  company: "Company jobs for your skills",
  recent: "Recently viewed",
};
const DEFAULT_ORDER = Object.keys(SECTIONS);

export async function render(app) {
  setTitle("Dashboard", "Your recommended jobs, saved jobs, deadlines and saved searches.");
  const prefs = state.prefs();
  const order = (prefs.sections || DEFAULT_ORDER).filter((k) => SECTIONS[k]);
  DEFAULT_ORDER.forEach((k) => { if (!order.includes(k)) order.push(k); });
  const hidden = new Set(prefs.hidden_sections || []);
  const u = store.user();

  app.innerHTML = `<div class="page">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Dashboard" }])}
    <div class="page-head" style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-end">
      <div><h1>Dashboard</h1><p>${u ? `Signed in as ${esc(u.email)}.` : store.accountsAvailable()
        ? `You are not signed in, so everything is saved on this device. <a href="#/signin">Sign in</a> to keep it across devices.`
        : "Everything is saved on this device."}</p></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn" href="#/profile">${state.hasProfile() ? "Edit profile" : "Set up profile"}</a>
        <button class="btn" type="button" id="customize" aria-expanded="false" aria-controls="customizePanel">Customise dashboard</button></div>
    </div>
    <section class="panel" id="customizePanel" hidden aria-label="Customise dashboard"></section>
    ${state.hasProfile() ? "" : `<div class="callout">Add your education to get recommendations and eligibility checks. <a href="#/profile">Set up your profile</a>.</div>`}
    <div class="dash-grid" id="dash">${order.filter((k) => !hidden.has(k)).map((k) =>
      `<section class="panel ${["recommended", "saved"].includes(k) ? "wide" : ""}" id="sec-${k}" aria-labelledby="h-${k}"><h2 id="h-${k}">${SECTIONS[k]}</h2><div class="sec-body"><div class="skeleton" style="width:70%"></div><div class="skeleton" style="width:50%"></div></div></section>`).join("")}</div>
    <div class="grid-2" style="margin-top:16px">
      <section class="panel" aria-labelledby="h-alerts"><h2 id="h-alerts">Alerts and preferences</h2><form id="prefsForm"></form></section>
      <section class="panel" aria-labelledby="h-account"><h2 id="h-account">Your data</h2><div id="accountBox"></div></section>
    </div></div>`;

  const customize = document.getElementById("customize");
  customize.addEventListener("click", () => {
    const panel = document.getElementById("customizePanel");
    const open = panel.hidden;
    panel.hidden = !open;
    customize.setAttribute("aria-expanded", String(open));
    if (open) drawCustomize(panel, order, hidden);
  });

  drawPrefs(prefs, u);
  drawAccount(u);

  let govtData = null;
  try { govtData = await govt(); } catch { /* sections show their own message */ }
  const jobs = govtData?.jobs || [];
  const byId = Object.fromEntries(jobs.map((j) => [j.id, j]));
  const profile = state.profile();
  const body = (k) => document.querySelector(`#sec-${k} .sec-body`);

  if (body("recommended")) {
    if (!state.hasProfile()) body("recommended").innerHTML = `<p class="muted">Set up your profile to see recruitments you may be eligible for.</p>`;
    else {
      const recs = jobs.filter((j) => j.status !== "closed").map((j) => ({ j, r: evaluate(j, profile) }))
        .filter((x) => x.r.verdict !== "no").sort((a, b) => verdictRank(a.r.verdict) - verdictRank(b.r.verdict) || (a.j.days_left ?? 999) - (b.j.days_left ?? 999)).slice(0, 8);
      body("recommended").innerHTML = recs.length ? `<ul class="mini-list">${recs.map(({ j, r }) =>
        `<li><div><a href="#/govt/${esc(j.id)}">${esc(j.short_title || j.title)}</a><div class="meta">${esc(r.label)}${j.dates?.application_end ? `. Last date ${fmtDate(j.dates.application_end)}` : ""}</div></div>${statusTag(j.status)}</li>`).join("")}</ul>
        <p class="small" style="margin:8px 0 0"><a href="#/govt?match=possible">All matches</a></p>`
        : `<p class="muted">No open or upcoming recruitment matches your profile right now. <a href="#/explorer">Explore what your qualification is commonly accepted for</a>.</p>`;
    }
  }

  const saved = state.saved();
  if (body("saved")) {
    body("saved").innerHTML = saved.length ? `<ul class="mini-list">${saved.map((s) => {
      const live = s.job_kind === "govt" ? byId[s.job_key] : null;
      const snap = s.snapshot || {};
      const changed = live && snap.application_end && live.dates?.application_end && snap.application_end !== live.dates.application_end;
      const href = s.job_kind === "govt" ? `#/govt/${esc(s.job_key)}` : `#/jobs/${encodeURIComponent(s.job_key)}`;
      const meta = s.job_kind === "govt"
        ? (live ? `${live.status === "closed" ? "Closed" : live.dates?.application_end ? `Last date ${fmtDate(live.dates.application_end)}` : "Dates not recorded"}${changed ? ` (changed from ${fmtDate(snap.application_end)})` : ""}` : "No longer listed")
        : `${esc(snap.org || "")}${snap.location ? `, ${esc(snap.location)}` : ""}`;
      return `<li><div><a href="${href}">${esc(snap.title || s.job_key)}</a><div class="meta">${s.job_kind === "govt" ? "Government" : "Company"}. ${meta}</div></div>
        <button class="btn btn-small btn-quiet" type="button" data-unsave="${esc(s.job_kind)}|${esc(s.job_key)}">Remove</button></li>`;
    }).join("")}</ul>` : `<p class="muted">Save jobs with the star button to track their deadlines here.</p>`;
    body("saved").querySelectorAll("[data-unsave]").forEach((b) => b.addEventListener("click", async () => {
      const [kind, key] = b.dataset.unsave.split("|");
      try { await store.unsaveJob(kind, key); await state.load(); b.closest("li").remove(); toast("Removed from saved jobs."); }
      catch (e) { toast(`Could not remove: ${e.message}`, { error: true }); }
    }));
  }

  if (body("deadlines")) {
    const ids = new Set(saved.filter((s) => s.job_kind === "govt").map((s) => s.job_key));
    const recIds = state.hasProfile() ? new Set(jobs.filter((j) => ["strong", "possible"].includes(evaluate(j, profile).verdict)).map((j) => j.id)) : new Set();
    const soon = jobs.filter((j) => j.status === "open" && (ids.has(j.id) || recIds.has(j.id)) && j.days_left != null && j.days_left <= 30)
      .sort((a, b) => a.days_left - b.days_left).slice(0, 8);
    body("deadlines").innerHTML = soon.length ? `<ul class="mini-list">${soon.map((j) =>
      `<li><div><a href="#/govt/${esc(j.id)}">${esc(j.short_title || j.title)}</a><div class="meta">${ids.has(j.id) ? "Saved" : "Recommended"}</div></div><strong class="num" style="color:${j.days_left <= 3 ? "var(--seal)" : "inherit"}">${fmtDate(j.dates.application_end, { noYear: true })}</strong></li>`).join("")}</ul>`
      : `<p class="muted">No saved or recommended job closes in the next 30 days.</p>`;
  }

  if (body("updates")) {
    try {
      const { items } = await computeNotifications();
      const top = items.filter((n) => n.kind !== "announcement").slice(0, 5);
      body("updates").innerHTML = top.length ? `<ul class="mini-list">${top.map((n) => `<li><div><a href="${esc(n.href)}">${esc(n.title)}</a>${n.body ? `<div class="meta">${esc(n.body)}</div>` : ""}</div></li>`).join("")}</ul>
        <p class="small" style="margin:8px 0 0"><a href="#/notifications">All notifications</a></p>` : `<p class="muted">No new updates.</p>`;
    } catch { body("updates").innerHTML = `<p class="muted">Updates could not be computed.</p>`; }
  }

  if (body("searches")) {
    const searches = await store.listSearches().catch(() => []);
    body("searches").innerHTML = searches.length ? `<ul class="mini-list">${searches.map((s) =>
      `<li><div><a href="${s.scope === "govt" ? "#/govt" : "#/jobs"}?${new URLSearchParams(Object.fromEntries(Object.entries(s.query || {}).filter(([k]) => k !== "saved_at"))).toString()}">${esc(s.name)}</a>
        <div class="meta">${s.scope === "govt" ? esc(describeFilters(s.query || {})) : "Company jobs"}</div></div>
        <span style="display:flex;gap:6px;align-items:center">${s.scope === "govt" ? `<label class="check small"><input type="checkbox" data-notify="${esc(s.id)}" ${s.notify ? "checked" : ""}> Alerts</label>` : ""}
        <button class="btn btn-small btn-quiet" type="button" data-del="${esc(s.id)}">Delete</button></span></li>`).join("")}</ul>`
      : `<p class="muted">Use "Save search" on the job lists to keep your filters and get alerts for new notices.</p>`;
    body("searches").querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
      try { await store.deleteSearch(b.dataset.del); b.closest("li").remove(); toast("Search deleted."); } catch (e) { toast(e.message, { error: true }); }
    }));
    body("searches").querySelectorAll("[data-notify]").forEach((c) => c.addEventListener("change", async () => {
      try { await store.updateSearch(c.dataset.notify, { notify: c.checked }); toast(c.checked ? "Alerts on for this search." : "Alerts off for this search."); } catch (e) { toast(e.message, { error: true }); }
    }));
  }

  if (body("recent")) {
    const recent = await store.listRecent().catch(() => []);
    body("recent").innerHTML = recent.length ? `<ul class="mini-list">${recent.slice(0, 8).map((r) =>
      `<li><div><a href="${r.job_kind === "govt" ? `#/govt/${esc(r.job_key)}` : `#/jobs/${encodeURIComponent(r.job_key)}`}">${esc(r.snapshot?.title || r.job_key)}</a><div class="meta">Viewed ${esc(relDays(String(r.viewed_at).slice(0, 10)))}</div></div></li>`).join("")}</ul>
      <button class="btn btn-small btn-quiet" type="button" id="clearRecent">Clear history</button>` : `<p class="muted">Jobs you open appear here.</p>`;
    document.getElementById("clearRecent")?.addEventListener("click", async () => { await store.clearRecent(); body("recent").innerHTML = `<p class="muted">History cleared.</p>`; });
  }

  if (body("company")) {
    if (!(profile.skills || []).length) body("company").innerHTML = `<p class="muted">Add skills to your profile to rank company jobs for you.</p>`;
    else {
      body("company").innerHTML = `<p class="muted small">Loading company jobs...</p>`;
      try {
        const idx = await companyIndex();
        const top = idx.filter((j) => j.country_scope === "India" || j.country_scope === "Remote-India")
          .map((j) => ({ j, s: companyScore(j, profile) })).sort((a, b) => b.s.score - a.s.score).slice(0, 6);
        body("company").innerHTML = `<ul class="mini-list">${top.map(({ j, s }) => `<li><div><a href="#/jobs/${encodeURIComponent(j.key)}">${esc(j.job_title)}</a><div class="meta">${esc(j.company)}, ${esc(j.location_raw || "")}</div></div><span class="score ${s.score >= 70 ? "hi" : "mid"}">${s.score}</span></li>`).join("")}</ul>
          <p class="small" style="margin:8px 0 0"><a href="#/jobs">All company jobs</a></p>`;
      } catch (e) { body("company").innerHTML = `<p class="muted">Company jobs could not be loaded.</p>`; }
    }
  }
}

function drawCustomize(panel, order, hidden) {
  panel.innerHTML = `<h2>Customise dashboard</h2><p class="small muted">Choose which sections to show and their order.</p>
    <ul class="mini-list" id="secList">${order.map((k, i) => `<li data-k="${k}"><label class="check"><input type="checkbox" ${hidden.has(k) ? "" : "checked"}> ${SECTIONS[k]}</label>
      <span><button class="btn btn-small btn-quiet" type="button" data-up="${i}" ${i === 0 ? "disabled" : ""} aria-label="Move ${SECTIONS[k]} up">Up</button>
      <button class="btn btn-small btn-quiet" type="button" data-down="${i}" ${i === order.length - 1 ? "disabled" : ""} aria-label="Move ${SECTIONS[k]} down">Down</button></span></li>`).join("")}</ul>
    <div style="display:flex;gap:8px;margin-top:10px"><button class="btn btn-primary" type="button" id="saveLayout">Save layout</button><button class="btn" type="button" id="resetLayout">Reset to default</button></div>`;
  const move = (i, d) => { const a = [...order]; [a[i], a[i + d]] = [a[i + d], a[i]]; order.splice(0, order.length, ...a); drawCustomize(panel, order, hidden); };
  panel.querySelectorAll("[data-up]").forEach((b) => b.addEventListener("click", () => move(Number(b.dataset.up), -1)));
  panel.querySelectorAll("[data-down]").forEach((b) => b.addEventListener("click", () => move(Number(b.dataset.down), 1)));
  panel.querySelectorAll("#secList input").forEach((c) => c.addEventListener("change", () => {
    const k = c.closest("li").dataset.k; if (c.checked) hidden.delete(k); else hidden.add(k);
  }));
  document.getElementById("saveLayout").addEventListener("click", async () => {
    try { await store.savePreferences({ ...state.prefs(), sections: order, hidden_sections: [...hidden] }); await state.load(); toast("Dashboard layout saved."); location.hash = "#/dashboard?r=" + Date.now(); }
    catch (e) { toast(e.message, { error: true }); }
  });
  document.getElementById("resetLayout").addEventListener("click", async () => {
    const p = { ...state.prefs() }; delete p.sections; delete p.hidden_sections;
    await store.savePreferences(p); await state.load(); toast("Dashboard reset."); location.hash = "#/dashboard?r=" + Date.now();
  });
}

function drawPrefs(prefs, u) {
  const form = document.getElementById("prefsForm");
  const cats = new Set(prefs.categories || []);
  const emailPossible = Boolean(u);
  form.innerHTML = `
    <div class="field"><label for="pr-days">Remind me before a saved job's last date</label>
      <select id="pr-days">${[3, 7, 14].map((d) => `<option value="${d}" ${Number(prefs.reminder_days ?? 7) === d ? "selected" : ""}>${d} days before</option>`).join("")}</select></div>
    <fieldset style="border:0;padding:0;margin:0 0 12px"><legend class="small" style="font-weight:500;margin-bottom:6px">Recruitment types I care about</legend>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr))">${CATEGORY_LIST.map((c) => `<label class="check small"><input type="checkbox" name="cat" value="${c}" ${cats.has(c) ? "checked" : ""}> ${c}</label>`).join("")}</div></fieldset>
    <label class="check"><input type="checkbox" id="pr-email" ${prefs.email_alerts ? "checked" : ""} ${emailPossible ? "" : "disabled"}> Email me deadline reminders and new matches</label>
    <p class="small muted" style="margin:2px 0 12px">${emailPossible ? "Sent once a day at most, only for jobs you saved or that match your profile. You can turn this off anytime." : "Email alerts need an account. In-site notifications work without one."}</p>
    <div style="display:flex;gap:8px"><button class="btn btn-primary" type="submit">Save preferences</button><button class="btn" type="button" id="prReset">Reset preferences</button></div>`;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const next = { ...state.prefs(), reminder_days: Number(document.getElementById("pr-days").value),
      categories: [...form.querySelectorAll('input[name="cat"]:checked')].map((x) => x.value),
      email_alerts: emailPossible && document.getElementById("pr-email").checked };
    try { await store.savePreferences(next); await state.load(); toast("Preferences saved."); } catch (err) { toast(err.message, { error: true }); }
  });
  document.getElementById("prReset").addEventListener("click", async () => {
    if (!(await confirmDialog("Reset preferences?", "Reminder timing, categories, alerts and dashboard layout go back to defaults.", "Reset"))) return;
    await store.savePreferences({}); await state.load(); toast("Preferences reset."); location.hash = "#/dashboard?r=" + Date.now();
  });
}

function drawAccount(u) {
  const box = document.getElementById("accountBox");
  box.innerHTML = `<p class="small">Your profile, saved jobs, searches and notification settings are stored ${u ? "in your account, protected so only you can read them" : "in this browser only"}. <a href="#/privacy">How your data is used</a>.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap">${u ? `<button class="btn" type="button" id="signOut">Sign out</button>` : ""}
    <button class="btn btn-danger" type="button" id="deleteAll">${u ? "Delete my account and data" : "Delete all data on this device"}</button></div>`;
  document.getElementById("signOut")?.addEventListener("click", async () => { await store.signOut(); await state.load(); toast("Signed out."); location.hash = "#/"; });
  document.getElementById("deleteAll").addEventListener("click", async () => {
    const ok = await confirmDialog(u ? "Delete your account?" : "Delete all data on this device?",
      u ? "Your account, profile, saved jobs, searches and notification settings will be permanently deleted." : "Your profile, saved jobs, searches and settings on this device will be removed.", "Delete permanently", true);
    if (!ok) return;
    try { await store.deleteAllData(); await state.load(); toast(u ? "Your account and data were deleted." : "All data on this device was deleted."); location.hash = "#/"; }
    catch (e) { toast(`Could not delete: ${e.message}`, { error: true }); }
  });
}
