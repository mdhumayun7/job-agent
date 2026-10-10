// Notification rules shared by the browser (notify.js) and the email job
// (scripts/alerts/compute_alerts.mjs), so both produce the same items and keys.
import { evaluate } from "./eligibility.js";
import { applyFilters, describeFilters } from "./govt-filter.js";
import { fmtDate } from "./ui.js";

export const ANNOUNCEMENTS = [
  { key: "ann:2026-10-govt-launch", date: "2026-10-11", title: "Government jobs section added",
    body: "Recruitments are read from official notices. Each listing shows when it was last checked; automatically collected notices are marked as awaiting verification.", href: "#/about" },
];

export const hasProfileData = (p) => Boolean((p?.qualifications || []).length || (p?.skills || []).length);

// jobs must already carry status and days_left (data.js finalize).
export function buildNotifications({ jobs, saved = [], profile = {}, prefs = {}, searches = [], announcements = true }) {
  const reminderDays = Number(prefs.reminder_days ?? 7);
  const byId = Object.fromEntries(jobs.map((j) => [j.id, j]));
  const items = [];

  for (const s of saved.filter((r) => r.job_kind === "govt")) {
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

  if (hasProfileData(profile)) {
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

  if (announcements) for (const a of ANNOUNCEMENTS) items.push({ ...a, kind: "announcement" });

  const seen = new Set();
  return items.filter((n) => (seen.has(n.key) ? false : seen.add(n.key)));
}
