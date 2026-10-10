// Loads published data. Government records come live from Supabase when it is
// configured (so admin edits appear immediately) and otherwise from the static
// file built by the daily workflow. Company jobs always come from static files.

import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js";
import { recruitmentStatus, daysLeft } from "./eligibility.js";

const BASE = new URL("../website-data/", import.meta.url.replace(/js\/data\.js.*$/, "")).href;
const cache = new Map();

async function getJSON(path) {
  if (cache.has(path)) return cache.get(path);
  const p = fetch(BASE + path, { cache: "no-cache" }).then((r) => {
    if (!r.ok) throw new Error(`Could not load ${path} (HTTP ${r.status})`);
    return r.json();
  });
  cache.set(path, p);
  p.catch(() => cache.delete(path));
  return p;
}

export function finalize(jobs, generatedAt, source) {
  const now = new Date();
  for (const j of jobs) {
    j.status = recruitmentStatus(j, now);
    j.days_left = daysLeft(j, now);
    j._search = [j.title, j.short_title, j.organization, j.org_short, j.category, j.state, j.notification_no,
      ...(j.posts || []), j.qualification?.notes].filter(Boolean).join(" ").toLowerCase();
  }
  const order = { open: 0, upcoming: 1, unknown: 2, closed: 3 };
  jobs.sort((a, b) => order[a.status] - order[b.status] || (a.days_left ?? 9999) - (b.days_left ?? 9999) || a.title.localeCompare(b.title));
  return { jobs, generated_at: generatedAt, source };
}

export async function govt() {
  if (cache.has("govt:final")) return cache.get("govt:final");
  const p = (async () => {
    if (SUPABASE_URL && SUPABASE_ANON_KEY) {
      try {
        const r = await fetch(`${SUPABASE_URL}/rest/v1/govt_jobs?select=id,data,updated_at&published=eq.true&archived=eq.false`, {
          headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${SUPABASE_ANON_KEY}` },
        });
        if (r.ok) {
          const rows = await r.json();
          return finalize(rows.map((row) => ({ ...row.data, id: row.id, updated_at: row.updated_at })), new Date().toISOString(), "live");
        }
      } catch (e) { console.warn("Live government data unavailable, using the published file", e); }
    }
    const d = await getJSON("govt.json");
    return finalize(d.jobs, d.generated_at, "file");
  })();
  cache.set("govt:final", p);
  p.catch(() => cache.delete("govt:final"));
  return p;
}

export async function govtById(id) {
  const { jobs } = await govt();
  return jobs.find((j) => j.id === id) || null;
}

export const companyIndex = () => getJSON("index.json");
export const companyStats = () => getJSON("stats.json");
export const companyList = () => getJSON("companies.json");
export const companyJob = (key) => getJSON(`jobs/${encodeURIComponent(key)}.json`);

export function invalidateGovt() { cache.delete("govt:final"); }

// ---- company job scoring for the visitor's own profile ---------------------
const SKILL_ALIASES = {
  "machine learning": "Machine learning", "deep learning": "Deep learning", "pytorch": "PyTorch", "tensorflow": "TensorFlow",
  "scikit-learn": "scikit-learn", "computer vision": "Computer vision", "opencv": "Computer vision", "nlp": "NLP", "llm": "LLMs",
  "pandas": "Pandas", "numpy": "NumPy", "sql": "SQL", "nosql": "MongoDB", "flask": "Flask", "django": "Django", "react": "React",
  "javascript": "JavaScript", "typescript": "TypeScript", "node.js": "Node.js", "python": "Python", "java": "Java", "c++": "C++",
  "aws": "AWS", "azure": "Azure", "gcp": "GCP", "docker": "Docker", "kubernetes": "Kubernetes", "linux": "Linux", "git": "Git",
  "networking": "Networking", "network security": "Cybersecurity", "cybersecurity": "Cybersecurity", "intrusion detection": "Cybersecurity",
  "embedded c": "Embedded systems", "spring": "Spring", "tableau": "Power BI / Tableau",
};

export function companyScore(job, profile) {
  const skills = new Set((profile?.skills || []).map((s) => s.toLowerCase()));
  let score = 0;
  const reasons = [];
  if (job.cse_relevant) { score += 25; reasons.push("CSE / IT role"); }
  const jobSkills = (job.skills_required || []).map((s) => (SKILL_ALIASES[s] || s).toLowerCase());
  const matched = jobSkills.filter((s) => skills.has(s));
  if (matched.length) { score += Math.min(35, matched.length * 9); reasons.push(`${matched.length} of your skills`); }
  const exp = profile?.experience_years ?? 0;
  if (job.internship || job.seniority === "Intern") { score += 15; reasons.push("internship"); }
  else if (job.fresher_eligible === true) { score += exp <= 2 ? 20 : 5; reasons.push("open to freshers"); }
  else if (job.seniority === "Senior") { score -= exp >= 5 ? 0 : 30; reasons.push("senior role"); }
  else if (job.seniority === "Mid") { score -= exp >= 2 ? 0 : 15; }
  if (job.country_scope === "India" || job.country_scope === "Remote-India") { score += 10; reasons.push("in India"); }
  else if (job.country_scope === "Abroad") score -= 20;
  const posted = job.date_posted || job.first_seen;
  if (posted && (Date.now() - new Date(posted)) / 86400000 <= 7) { score += 5; reasons.push("posted this week"); }
  return { score: Math.max(0, Math.min(100, score)), reasons };
}
