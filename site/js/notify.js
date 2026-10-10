// Notification center: computed from the published data and the visitor's own
// saved jobs, saved searches and profile. Each notification has a stable key, so
// it is shown once, can be marked read, and is never duplicated.
import * as store from "./store.js";
import * as state from "./state.js";
import { govt } from "./data.js";
import { evaluate } from "./eligibility.js";
import { applyFilters, describeFilters } from "./govt-filter.js";
import { fmtDate } from "./ui.js";

export const ANNOUNCEMENTS = [
  { key: "ann:2026-10-govt-launch", date: "2026-10-11", title: "Government jobs section added",
    body: "Recruitments are read from official notices. Each listing shows when it was last checked; automatically collected notices are marked as awaiting verification.", href: "#/about" },
];

let cached = { items: [], unread: 0 };
export const unreadCount = () => cached.unread;

export async function computeNotifications() {
  const prefs = state.prefs();
  const reminderDays = Number(prefs.reminder_days ?? 7);
  const [{ jobs }, readState, searches] = await Promise.all([govt(), store.notifState().catch(() => ({})), store.listSearches().catch(() => [])]);
  const byId = Object.fromEntries(jobs.map((j) => [j.id, j]));
  const items = [];

  for (const s of state.saved().filter((r) => r.job_kind === "govt")) {
    const j = byId[s.job_key];
    const snap = s.snapshot || {};
    if (!j) {
      items.push({ key: `removed:${s.job_key}`, kind: "update", title: `${snap.title || s.job_key} is no longer listed`,
        body: "The record was withdrawn or archived. Check the official site for its status.", date: null, href: "#/dashboard" });
      continue;
    }
    const end = j.dates?.application_end;
    if (snap.application_end && end && snap.application_end !== end) {
      items.push({ key: `changed:${j.id}:${end}`, kind: "update", title: `Last date changed: ${j.short_title || j.title}`,
        body: `Now ${fmtDate(end)} (was ${fmtDate(snap.application_end)}).`, date: j.updated_at || null, href: `#/govt/${j.id}` });
    }
    if (j.status === "open" && j.days_left != null && j.days_left <= reminderDays) {
      items.push({ key: `deadline:${j.id}:${end}`, kind: "deadline", title: `Closes ${j.days_left === 0 ? "today" : `in ${j.days_left} day${j.days_left === 1 ? "" : "s"}`}: ${j.short_title || j.title}`,
        body: `Last date ${fmtDate(end)}. Apply on the official site before then.`, date: end, href: `#/govt/${j.id}` });
    }
    if (snap.status && snap.status !== "closed" && j.status === "closed") {
      items.push({ key: `closed:${j.id}`, kind: "update", title: `Applications closed: ${j.short_title || j.title}`, body: "", date: end, href: `#/govt/${j.id}` });
    }
    for (const ev of j.events || []) {
      items.push({ key: `event:${j.id}:${ev.type}:${ev.date}`, kind: "update", title: `${j.short_title || j.title}: ${ev.title}`, body: "", date: ev.date, href: `#/govt/${j.id}` });
    }
  }

  const profile = state.profile();
  if (state.hasProfile()) {
    for (const j of jobs) {
      if (j.status !== "open" && j.status !== "upcoming") continue;
      const r = evaluate(j, profile);
      if (r.verdict === "strong" || r.verdict === "possible") {
        items.push({ key: `match:${j.id}`, kind: "match", title: `${r.label}: ${j.short_title || j.title}`,
          body: j.dates?.application_end ? `Last date ${fmtDate(j.dates.application_end)}.` : "", date: j.notice_date, href: `#/govt/${j.id}` });
      }
    }
  }

  for (const s of searches.filter((x) => x.notify && x.scope === "govt")) {
    const since = s.query?.saved_at || s.created_at;
    const fresh = applyFilters(jobs, s.query || {}, profile).filter((j) => j.notice_date && since && j.notice_date >= since.slice(0, 10)).slice(0, 10);
    for (const j of fresh) {
      items.push({ key: `search:${s.id}:${j.id}`, kind: "search", title: `New for "${s.name}": ${j.short_title || j.title}`,
        body: describeFilters(s.query || {}), date: j.notice_date, href: `#/govt/${j.id}` });
    }
  }

  for (const a of ANNOUNCEMENTS) items.push({ ...a, kind: "announcement" });

  const seen = new Set();
  const unique = items.filter((n) => (seen.has(n.key) ? false : seen.add(n.key)));
  unique.forEach((n) => { const st = readState[n.key]; n.read = Boolean(st?.read_at); n.dismissed = Boolean(st?.dismissed); });
  const visible = unique.filter((n) => !n.dismissed);
  visible.sort((a, b) => Number(a.read) - Number(b.read) || String(b.date || "").localeCompare(String(a.date || "")));
  cached = { items: visible, unread: visible.filter((n) => !n.read).length };
  return cached;
}

export async function refreshNotifications() {
  try { await computeNotifications(); window.dispatchEvent(new CustomEvent("notif:computed")); }
  catch (e) { console.warn("notifications unavailable", e); }
}

window.addEventListener("store:change", (e) => { if (["saved", "profile", "searches", "notif", "auth", "prefs"].includes(e.detail)) refreshNotifications(); });
