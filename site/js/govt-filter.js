// Shared filtering / sorting for government records (list page, saved searches, notifications).
import { evaluate, verdictRank, LEVELS } from "./eligibility.js";

export const CATEGORY_LIST = ["Central", "State", "Banking", "SSC", "UPSC", "Railways", "Teaching", "Defence", "Police", "PSU", "Research", "Other"];
export const CATEGORY_HELP = {
  Central: "Ministries and central departments", State: "State public service commissions and departments",
  Banking: "IBPS, SBI, RBI and other banks", SSC: "Staff Selection Commission examinations",
  UPSC: "Union Public Service Commission examinations", Railways: "Railway Recruitment Boards",
  Teaching: "Teacher eligibility and recruitment", Defence: "Armed forces and paramilitary",
  Police: "Police and armed police forces", PSU: "Public sector undertakings", Research: "Research organisations such as ISRO and C-DAC",
  Other: "Other public bodies",
};

export const FILTER_KEYS = ["q", "cat", "status", "qual", "state", "age", "deadline", "type", "fresher", "pct", "match", "verified", "sort"];

export function readFilters(params) {
  const f = {};
  for (const k of FILTER_KEYS) { const v = params.get(k); if (v) f[k] = v; }
  return f;
}

function minLevel(job) {
  const opts = job.qualification?.options || [];
  if (!opts.length) return null;
  return opts.reduce((a, o) => ((LEVELS[o.level] ?? 9) < (LEVELS[a] ?? 9) ? o.level : a), opts[0].level);
}

function ageBounds(job) {
  const a = job.age;
  if (!a) return null;
  let min = a.min, max = a.max;
  if ((min == null || max == null) && a.born_not_before && a.born_not_after) {
    const ref = new Date(a.as_on || Date.now());
    max ??= ref.getFullYear() - new Date(a.born_not_before).getFullYear();
    min ??= ref.getFullYear() - new Date(a.born_not_after).getFullYear();
  }
  return { min, max };
}

export function applyFilters(jobs, f, profile) {
  const q = (f.q || "").trim().toLowerCase();
  const terms = q ? q.split(/\s+/) : [];
  const withEval = profile && Object.keys(profile).length;
  let out = jobs.filter((j) => {
    if (terms.length && !terms.every((t) => j._search.includes(t))) return false;
    if (f.cat && j.category !== f.cat) return false;
    if (f.status && f.status !== "all" && j.status !== f.status) return false;
    if (f.qual) {
      const ml = minLevel(j);
      if (ml && (LEVELS[ml] ?? 0) > (LEVELS[f.qual] ?? 0)) return false;
    }
    if (f.state) {
      if (f.state === "all-india") { if (j.state) return false; }
      else if (j.state && j.state !== f.state) return false;
    }
    if (f.age) {
      const b = ageBounds(j);
      const age = Number(f.age);
      if (b && ((b.min != null && age < b.min) || (b.max != null && age > b.max))) return false;
    }
    if (f.deadline) {
      if (j.status !== "open" || j.days_left == null || j.days_left > Number(f.deadline)) return false;
    }
    if (f.type && (j.employment_type || "").toLowerCase() !== f.type) return false;
    if (f.fresher === "1" && j.experience_years) return false;
    if (f.pct && j.qualification?.min_percentage != null && j.qualification.min_percentage > Number(f.pct)) return false;
    if (f.verified === "1" && j.verification?.status !== "verified") return false;
    return true;
  });
  if (withEval) out.forEach((j) => { j._eval = evaluate(j, profile); });
  else out.forEach((j) => { delete j._eval; });
  if (f.match && withEval) out = out.filter((j) => (f.match === "strong" ? j._eval.verdict === "strong" : ["strong", "possible"].includes(j._eval.verdict)));
  const sort = f.sort || "deadline";
  const order = { open: 0, upcoming: 1, unknown: 2, closed: 3 };
  if (sort === "newest") out.sort((a, b) => String(b.notice_date || "").localeCompare(String(a.notice_date || "")));
  else if (sort === "match" && withEval) out.sort((a, b) => verdictRank(a._eval.verdict) - verdictRank(b._eval.verdict) || order[a.status] - order[b.status]);
  else out.sort((a, b) => order[a.status] - order[b.status] || (a.days_left ?? 9999) - (b.days_left ?? 9999));
  return out;
}

export function describeFilters(f) {
  const parts = [];
  if (f.q) parts.push(`"${f.q}"`);
  if (f.cat) parts.push(f.cat);
  if (f.status && f.status !== "all") parts.push({ open: "open", upcoming: "opening soon", closed: "closed", unknown: "no dates" }[f.status] || f.status);
  if (f.qual) parts.push(`up to ${f.qual} level`);
  if (f.state) parts.push(f.state === "all-india" ? "all-India" : f.state);
  if (f.age) parts.push(`age ${f.age}`);
  if (f.deadline) parts.push(`closing in ${f.deadline} days`);
  if (f.match) parts.push(f.match === "strong" ? "strong matches" : "matches");
  return parts.join(", ") || "All government jobs";
}
