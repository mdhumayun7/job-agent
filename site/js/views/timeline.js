import { govt } from "../data.js";
import * as state from "../state.js";
import { esc, breadcrumb, setTitle, fmtDate, todayISO, toast, MONTHS, ICONS } from "../ui.js";

const KIND = { application_start: "Applications open", application_end: "Last date to apply", fee_end: "Last date for fee",
  correction_start: "Correction window opens", correction_end: "Correction window closes", exam: "Examination", exam_end: "Examination ends",
  admit_card: "Admit card", result: "Result", answer_key: "Answer key" };

export function collectEvents(jobs) {
  const out = [];
  for (const j of jobs) {
    for (const [k, v] of Object.entries(j.dates || {})) {
      if (KIND[k] && v && /^\d{4}-\d{2}-\d{2}$/.test(v)) out.push({ date: v, kind: k, label: KIND[k], j });
    }
    for (const e of j.events || []) if (e.date) out.push({ date: e.date, kind: e.type, label: `${KIND[e.type] || "Update"}: ${e.title}`, j, url: e.url });
  }
  return out.sort((a, b) => a.date.localeCompare(b.date));
}

export async function render(app, { params }) {
  setTitle("Deadlines and exam dates", "Upcoming application deadlines, examination dates, admit cards and results from official notices.");
  const show = params.get("show") || "upcoming";
  const mine = params.get("mine") === "1";
  app.innerHTML = `<div class="page">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Deadlines and exam dates" }])}
    <div class="page-head"><h1>Deadlines and exam dates</h1>
      <p>Only dates stated in official notices are shown. Tentative schedules ("to be notified", month ranges) are listed on each job page, not here.</p></div>
    <div class="toolbar">
      <div role="group" aria-label="Which events" style="display:flex;gap:6px;flex-wrap:wrap">
        ${[["upcoming", "Upcoming"], ["active", "Applications open now"], ["past", "Completed"]].map(([v, l]) =>
          `<a class="btn btn-small" href="#/timeline?show=${v}${mine ? "&mine=1" : ""}" ${show === v ? 'aria-current="page" style="border-color:var(--ink);color:var(--ink)"' : ""}>${l}</a>`).join("")}
      </div>
      <label class="check small"><input type="checkbox" id="mineOnly" ${mine ? "checked" : ""}> Only jobs I saved</label>
    </div>
    <div id="tl"></div></div>`;
  document.getElementById("mineOnly").addEventListener("change", (e) => { location.hash = `#/timeline?show=${show}${e.target.checked ? "&mine=1" : ""}`; });

  const { jobs } = await govt();
  const today = todayISO();
  let events = collectEvents(jobs);
  if (mine) events = events.filter((e) => state.isSaved("govt", e.j.id));
  if (show === "upcoming") events = events.filter((e) => e.date >= today);
  else if (show === "past") events = events.filter((e) => e.date < today).reverse();
  else events = events.filter((e) => e.j.status === "open" && e.kind === "application_end");

  const el = document.getElementById("tl");
  if (!events.length) {
    el.innerHTML = `<div class="empty"><h2>No dates to show</h2><p>${mine ? "None of your saved jobs have dates in this range." : "There are no events in this range in the current listings."}</p><a class="btn" href="#/govt">Browse government jobs</a></div>`;
    return;
  }
  const groups = new Map();
  for (const e of events) {
    const k = e.date.slice(0, 7);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(e);
  }
  el.innerHTML = [...groups.entries()].map(([ym, evs]) => {
    const [y, m] = ym.split("-").map(Number);
    return `<section class="timeline-month" aria-label="${MONTHS[m - 1]} ${y}"><h2>${MONTHS[m - 1]} ${y}</h2>
      <div class="panel" style="padding:0">${evs.map((e) => {
        const saved = state.isSaved("govt", e.j.id);
        return `<div class="event ${e.date < today ? "done" : ""}">
          <span class="when">${fmtDate(e.date, { noYear: true })}</span>
          <span><strong>${esc(e.label)}</strong><br><a href="#/govt/${esc(e.j.id)}">${esc(e.j.short_title || e.j.title)}</a> <span class="small muted">${esc(e.j.org_short || "")}</span></span>
          <button class="btn btn-small" type="button" data-save="${esc(e.j.id)}" aria-pressed="${saved}" title="Save the job to get reminders">${saved ? ICONS.starFilled : ICONS.star}<span>${saved ? "Saved" : "Remind me"}</span></button>
        </div>`;
      }).join("")}</div></section>`;
  }).join("");
  el.querySelectorAll("[data-save]").forEach((b) => b.addEventListener("click", async () => {
    const j = jobs.find((x) => x.id === b.dataset.save);
    try {
      const now = await state.toggleSave("govt", j.id, state.govtSnapshot(j));
      el.querySelectorAll(`[data-save="${CSS.escape(j.id)}"]`).forEach((x) => {
        x.setAttribute("aria-pressed", String(now));
        x.innerHTML = `${now ? ICONS.starFilled : ICONS.star}<span>${now ? "Saved" : "Remind me"}</span>`;
      });
      toast(now ? "Saved. Reminders appear in your notifications before the last date." : "Removed from saved jobs");
    } catch (e) { toast(`Could not save: ${e.message}`, { error: true }); }
  }));
}
