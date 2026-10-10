import { companyIndex, companyScore } from "../data.js";
import * as state from "../state.js";
import * as store from "../store.js";
import { esc, safeUrl, breadcrumb, setTitle, skeletonRows, emptyState, debounce, toast, relDays, ICONS, promptDialog } from "../ui.js";
import { setQuery } from "../app.js";

const PAGE = 25;

export function companyRow(j, scored) {
  const s = scored?.score;
  const cls = s >= 70 ? "hi" : s >= 50 ? "mid" : "";
  const saved = state.isSaved("company", j.key);
  return `<li class="job-row">
    <div>
      <h3><a href="#/jobs/${encodeURIComponent(j.key)}">${esc(j.job_title)}</a></h3>
      <div class="muted small">${esc(j.company)}, ${esc(j.location_raw || "Location not specified")}</div>
      <div class="facts">
        ${j.employment_type && j.employment_type !== "Not specified" ? `<span>${esc(j.employment_type)}</span>` : ""}
        ${j.experience_raw && j.experience_raw !== "Not specified" ? `<span>Experience ${esc(j.experience_raw)}</span>` : ""}
        ${j.date_posted || j.first_seen ? `<span>Posted ${esc(relDays((j.date_posted || j.first_seen).slice(0, 10)))}</span>` : ""}
      </div>
      <div class="tags">
        ${j.status === "NEW" ? '<span class="tag open">New today</span>' : ""}
        ${j.fresher_eligible ? '<span class="tag">Fresher</span>' : ""}${j.internship ? '<span class="tag">Internship</span>' : ""}
        ${j.country_scope && j.country_scope !== "Unknown" ? `<span class="tag">${esc(j.country_scope)}</span>` : ""}
        ${j.seniority === "Senior" ? '<span class="tag">Senior</span>' : ""}
      </div>
    </div>
    <div class="notice-actions">
      ${s != null ? `<div class="score ${cls}" title="${esc(scored.reasons.join(", "))}" aria-label="Match score ${s} of 100">${s}</div>` : ""}
      <button class="btn btn-small" type="button" data-save="${esc(j.key)}" aria-pressed="${saved}">${saved ? ICONS.starFilled : ICONS.star}<span class="sr-only">${saved ? "Saved" : "Save"}</span></button>
      ${safeUrl(j.apply_url) ? `<a class="btn btn-small" href="${safeUrl(j.apply_url)}" target="_blank" rel="noopener noreferrer">Apply</a>` : ""}
    </div>
  </li>`;
}

export async function render(app, { params }) {
  setTitle("Company jobs", "CSE and IT openings from company career sites, ranked for your skills, with India, fresher and internship filters.");
  const get = (k) => params.get(k) || "";
  app.innerHTML = `<div class="page">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Company jobs" }])}
    <div class="page-head"><h1>Company jobs</h1>
      <p>Openings collected every day from company career sites. ${state.hasProfile() ? "The score compares each job with the skills in your profile." : `<a href="#/profile">Add your skills</a> to rank jobs for you.`}</p></div>
    <div class="with-rail">
      <aside class="rail" id="rail" data-collapsed="true" aria-label="Filters">
        <div style="display:flex;justify-content:space-between;align-items:center"><h2 style="margin:0">Filters</h2>
          <button class="btn btn-small rail-toggle" type="button" id="railToggle" aria-expanded="false">Show filters</button></div>
        <form class="rail-body" id="railBody" style="margin-top:12px">
          <div class="field"><label for="c-q">Keyword</label><input id="c-q" name="q" type="search" value="${esc(get("q"))}" placeholder="Title, company, skill or city"></div>
          <div class="field"><label for="c-region">Region</label><select id="c-region" name="region">
            <option value="india" ${get("region") !== "all" && get("region") !== "remote" ? "selected" : ""}>India and remote India</option>
            <option value="remote" ${get("region") === "remote" ? "selected" : ""}>Remote (any)</option><option value="all" ${get("region") === "all" ? "selected" : ""}>All regions</option></select></div>
          <div class="field"><label for="c-company">Company</label><select id="c-company" name="company"><option value="">All companies</option></select></div>
          <label class="check"><input type="checkbox" name="fresher" value="1" ${get("fresher") ? "checked" : ""}> Open to freshers</label>
          <label class="check"><input type="checkbox" name="intern" value="1" ${get("intern") ? "checked" : ""}> Internships</label>
          <label class="check"><input type="checkbox" name="cse" value="1" ${get("cse") ? "checked" : ""}> CSE / IT roles only</label>
          <label class="check"><input type="checkbox" name="nosenior" value="1" ${get("nosenior") ? "checked" : ""}> Hide senior roles</label>
          <label class="check"><input type="checkbox" name="new" value="1" ${get("new") ? "checked" : ""}> New since yesterday</label>
          <div style="display:flex;gap:8px;margin-top:10px"><button class="btn btn-small" type="reset">Reset filters</button><button class="btn btn-small" type="button" id="saveSearch">Save search</button></div>
        </form>
      </aside>
      <section>
        <div class="toolbar"><span class="count" id="count" aria-live="polite">Loading company jobs</span>
          <label class="small" style="display:flex;gap:8px;align-items:center">Sort <select id="c-sort" style="width:auto">
            <option value="match" ${get("sort") !== "newest" && get("sort") !== "company" ? "selected" : ""}>Best match</option>
            <option value="newest" ${get("sort") === "newest" ? "selected" : ""}>Newest</option><option value="company" ${get("sort") === "company" ? "selected" : ""}>Company A-Z</option></select></label></div>
        <div id="list">${skeletonRows(6)}</div>
        <nav class="pagination" id="pager" aria-label="Pages"></nav>
      </section>
    </div></div>`;

  const rail = document.getElementById("rail");
  document.getElementById("railToggle").addEventListener("click", (e) => {
    const open = rail.dataset.collapsed === "true";
    rail.dataset.collapsed = String(!open);
    e.currentTarget.setAttribute("aria-expanded", String(open));
    e.currentTarget.textContent = open ? "Hide filters" : "Show filters";
  });

  let jobs;
  try { jobs = await companyIndex(); } catch (e) {
    document.getElementById("list").innerHTML = `<div class="callout error">Company listings could not be loaded: ${esc(e.message)}.</div>`;
    return;
  }
  const profile = state.profile();
  const scores = new Map(jobs.map((j) => [j.key, companyScore(j, profile)]));
  const companies = [...new Set(jobs.map((j) => j.company))].sort();
  const sel = document.getElementById("c-company");
  sel.innerHTML += companies.map((c) => `<option ${get("company") === c ? "selected" : ""}>${esc(c)}</option>`).join("");
  const form = document.getElementById("railBody");
  let page = Number(get("page") || 1);

  const filtersNow = () => {
    const out = {};
    for (const [k, v] of new FormData(form).entries()) if (v) out[k] = v;
    const sort = document.getElementById("c-sort").value;
    if (sort !== "match") out.sort = sort;
    return out;
  };

  function draw() {
    if (!form.isConnected) return; // the user navigated away before a delayed redraw
    const f = filtersNow();
    const terms = (f.q || "").toLowerCase().split(/\s+/).filter(Boolean);
    let list = jobs.filter((j) => {
      if (terms.length) {
        const hay = `${j.job_title} ${j.company} ${j.location_raw} ${(j.skills_required || []).join(" ")}`.toLowerCase();
        if (!terms.every((t) => hay.includes(t))) return false;
      }
      if (f.region === "india" && !(j.country_scope === "India" || j.country_scope === "Remote-India")) return false;
      if (f.region === "remote" && !(j.country_scope === "Remote" || j.country_scope === "Remote-India")) return false;
      if (f.company && j.company !== f.company) return false;
      if (f.fresher && !j.fresher_eligible) return false;
      if (f.intern && !j.internship) return false;
      if (f.cse && !j.cse_relevant) return false;
      if (f.nosenior && j.seniority === "Senior") return false;
      if (f.new && j.status !== "NEW") return false;
      return true;
    });
    if (f.sort === "newest") list.sort((a, b) => String(b.date_posted || b.first_seen || "").localeCompare(String(a.date_posted || a.first_seen || "")));
    else if (f.sort === "company") list.sort((a, b) => a.company.localeCompare(b.company) || a.job_title.localeCompare(b.job_title));
    else list.sort((a, b) => scores.get(b.key).score - scores.get(a.key).score);
    const pages = Math.max(1, Math.ceil(list.length / PAGE));
    page = Math.min(page, pages);
    const params2 = new URLSearchParams(f);
    if (page > 1) params2.set("page", page);
    setQuery(params2);
    document.getElementById("count").textContent = `${list.length.toLocaleString("en-IN")} job${list.length === 1 ? "" : "s"}`;
    const el = document.getElementById("list");
    if (!list.length) {
      el.innerHTML = emptyState("No jobs match these filters", "Try another keyword, or switch the region to all regions.");
      document.getElementById("pager").innerHTML = "";
      return;
    }
    el.innerHTML = `<ul class="notice-list">${list.slice((page - 1) * PAGE, page * PAGE).map((j) => companyRow(j, scores.get(j.key))).join("")}</ul>`;
    el.querySelectorAll("[data-save]").forEach((b) => b.addEventListener("click", async () => {
      const j = jobs.find((x) => x.key === b.dataset.save);
      try {
        const now = await state.toggleSave("company", j.key, state.companySnapshot(j));
        b.setAttribute("aria-pressed", String(now));
        b.innerHTML = `${now ? ICONS.starFilled : ICONS.star}<span class="sr-only">${now ? "Saved" : "Save"}</span>`;
        toast(now ? `Saved ${j.job_title}` : "Removed from saved jobs");
      } catch (e) { toast(`Could not save: ${e.message}`, { error: true }); }
    }));
    const pager = document.getElementById("pager");
    const start = Math.max(1, page - 3), end = Math.min(pages, start + 6);
    pager.innerHTML = pages > 1 ? `<button class="btn btn-small" data-page="${page - 1}" ${page === 1 ? "disabled" : ""}>Previous</button>` +
      Array.from({ length: end - start + 1 }, (_, i) => start + i).map((p) => `<button class="btn btn-small" data-page="${p}" ${p === page ? 'aria-current="page"' : ""}>${p}</button>`).join("") +
      `<button class="btn btn-small" data-page="${page + 1}" ${page === pages ? "disabled" : ""}>Next</button>` : "";
    pager.querySelectorAll("[data-page]").forEach((b) => b.addEventListener("click", () => { page = Number(b.dataset.page); draw(); window.scrollTo(0, 0); }));
  }

  const redraw = debounce(() => { page = 1; draw(); }, 150);
  form.addEventListener("input", redraw);
  form.addEventListener("change", redraw);
  form.addEventListener("submit", (e) => e.preventDefault());
  form.addEventListener("reset", () => setTimeout(() => { page = 1; draw(); }, 0));
  document.getElementById("c-sort").addEventListener("change", () => { page = 1; draw(); });
  document.getElementById("saveSearch").addEventListener("click", async () => {
    const name = await promptDialog("Save this search", "Name", (filtersNow().q || "Company jobs").slice(0, 80), "Save search");
    if (!name) return;
    try { await store.saveSearch({ name, scope: "company", query: filtersNow(), notify: false }); toast(`Saved "${name}".`); }
    catch (e) { toast(`Could not save: ${e.message}`, { error: true }); }
  });
  draw();
}
