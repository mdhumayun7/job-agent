import { govt } from "../data.js";
import * as state from "../state.js";
import * as store from "../store.js";
import { applyFilters, readFilters, describeFilters, CATEGORY_LIST, CATEGORY_HELP } from "../govt-filter.js";
import { wireNoticeActions } from "../govt-actions.js";
import { noticeRow } from "./home.js";
import { esc, breadcrumb, setTitle, skeletonRows, emptyState, debounce, toast, fmtDate, promptDialog } from "../ui.js";
import { setQuery } from "../app.js";

const STATES = ["Andhra Pradesh", "Assam", "Bihar", "Delhi", "Gujarat", "Haryana", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
  "Odisha", "Punjab", "Rajasthan", "Tamil Nadu", "Telangana", "Uttar Pradesh", "Uttarakhand", "West Bengal"];
const PAGE = 20;

export async function render(app, { params }) {
  const f = readFilters(params);
  let page = Number(params.get("page") || 1);
  const catTitle = f.cat ? `${f.cat} jobs` : "Government jobs";
  setTitle(catTitle, f.cat ? `${f.cat} recruitments: ${CATEGORY_HELP[f.cat] || ""}. Official notices, last dates and eligibility.` : "Government recruitments read from official notices, with last dates and eligibility checks.");
  const hasProfile = state.hasProfile();

  app.innerHTML = `<div class="page">
    ${breadcrumb([{ label: "Home", href: "#/" }, ...(f.cat ? [{ label: "Government jobs", href: "#/govt" }, { label: f.cat }] : [{ label: "Government jobs" }])])}
    <div class="page-head">
      <h1>${esc(catTitle)}</h1>
      <p>${f.cat ? esc(CATEGORY_HELP[f.cat] || "") + ". " : ""}Every listing links to its official notice. Listings marked "awaiting verification" were collected automatically and have not been reviewed yet.</p>
    </div>
    <div class="with-rail">
      <aside class="rail" id="rail" data-collapsed="true" aria-label="Filters">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <h2 style="margin:0">Filters</h2>
          <button class="btn btn-small rail-toggle" type="button" id="railToggle" aria-expanded="false" aria-controls="railBody">Show filters</button>
        </div>
        <form class="rail-body" id="railBody" style="margin-top:12px">
          <div class="field" data-guide="Type words from the post, exam or organisation. All words must match."><label for="f-q">Keyword</label><input id="f-q" name="q" type="search" value="${esc(f.q || "")}" placeholder="e.g. Navik, CHSL, ISRO"></div>
          <div class="field"><label for="f-cat">Recruitment type</label><select id="f-cat" name="cat"><option value="">All types</option>${CATEGORY_LIST.map((c) => `<option ${f.cat === c ? "selected" : ""}>${c}</option>`).join("")}</select></div>
          <div class="field"><label for="f-status">Application status</label><select id="f-status" name="status">
            <option value="">Open, upcoming and closed</option><option value="open" ${f.status === "open" ? "selected" : ""}>Applications open</option>
            <option value="upcoming" ${f.status === "upcoming" ? "selected" : ""}>Opening soon</option><option value="closed" ${f.status === "closed" ? "selected" : ""}>Closed</option></select></div>
          <div class="field" data-guide="Shows posts whose minimum qualification is at or below the level you pick."><label for="f-qual">Your highest qualification</label><select id="f-qual" name="qual"><option value="">Any</option>
            ${[["10th", "10th"], ["12th", "12th"], ["iti", "ITI"], ["diploma", "Diploma"], ["graduate", "Graduate"], ["engineering", "B.E. / B.Tech"], ["postgraduate", "Post-graduate"]].map(([v, l]) => `<option value="${v}" ${f.qual === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
          <div class="field" data-guide="Hides recruitments whose recorded age range excludes you. Relaxations are checked on the job page."><label for="f-age">Your age</label><input id="f-age" name="age" type="number" min="14" max="70" inputmode="numeric" value="${esc(f.age || "")}"><span class="hint">Before category relaxation.</span></div>
          <div class="field"><label for="f-deadline">Last date within</label><select id="f-deadline" name="deadline"><option value="">Any time</option>
            ${[7, 15, 30].map((d) => `<option value="${d}" ${f.deadline === String(d) ? "selected" : ""}>${d} days</option>`).join("")}</select></div>
          <div class="field"><label for="f-state">State</label><select id="f-state" name="state"><option value="">All</option><option value="all-india" ${f.state === "all-india" ? "selected" : ""}>All-India (central) only</option>
            ${STATES.map((s) => `<option ${f.state === s ? "selected" : ""}>${s}</option>`).join("")}</select></div>
          <div class="field"><label for="f-type">Position type</label><select id="f-type" name="type"><option value="">Any</option>
            <option value="permanent" ${f.type === "permanent" ? "selected" : ""}>Permanent</option><option value="contract" ${f.type === "contract" ? "selected" : ""}>Contractual</option></select></div>
          <div class="field"><label for="f-pct">Your marks (%)</label><input id="f-pct" name="pct" type="number" min="0" max="100" value="${esc(f.pct || "")}"><span class="hint">Hides posts with a higher minimum percentage.</span></div>
          <label class="check"><input type="checkbox" name="fresher" value="1" ${f.fresher ? "checked" : ""}> No experience required</label>
          <label class="check"><input type="checkbox" name="verified" value="1" ${f.verified ? "checked" : ""}> Checked against official notice</label>
          ${hasProfile ? `<div class="field" style="margin-top:8px"><label for="f-match">Profile match</label><select id="f-match" name="match"><option value="">Show all</option>
            <option value="possible" ${f.match === "possible" ? "selected" : ""}>Strong and possible matches</option><option value="strong" ${f.match === "strong" ? "selected" : ""}>Strong matches only</option></select></div>`
            : `<p class="small muted"><a href="#/profile">Add your education</a> to filter by eligibility.</p>`}
          <div style="display:flex;gap:8px;margin-top:8px"><button class="btn btn-small" type="reset" id="resetFilters">Reset filters</button>
          <button class="btn btn-small" type="button" id="saveSearch" data-guide="Save these filters. With alerts on, new matching notices appear in your notifications.">Save search</button></div>
        </form>
      </aside>
      <section aria-labelledby="resultsCount">
        <div class="toolbar">
          <span class="count" id="resultsCount" aria-live="polite">Loading listings</span>
          <label class="small" style="display:flex;gap:8px;align-items:center">Sort
            <select id="f-sort" style="width:auto">
              <option value="deadline" ${!f.sort || f.sort === "deadline" ? "selected" : ""}>Nearest last date</option>
              <option value="newest" ${f.sort === "newest" ? "selected" : ""}>Newest notice</option>
              ${hasProfile ? `<option value="match" ${f.sort === "match" ? "selected" : ""}>Best eligibility match</option>` : ""}
            </select></label>
        </div>
        <div id="results">${skeletonRows(6)}</div>
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

  let data;
  try { data = await govt(); } catch (e) {
    document.getElementById("results").innerHTML = `<div class="callout error">Listings could not be loaded: ${esc(e.message)}. <a href="${esc(location.hash)}">Try again</a>.</div>`;
    return;
  }
  const byId = Object.fromEntries(data.jobs.map((j) => [j.id, j]));
  const form = document.getElementById("railBody");

  function current() {
    const fd = new FormData(form);
    const out = {};
    for (const [k, v] of fd.entries()) if (v) out[k] = v;
    const sort = document.getElementById("f-sort").value;
    if (sort && sort !== "deadline") out.sort = sort;
    return out;
  }

  function draw() {
    if (!form.isConnected) return; // the user navigated away before a delayed redraw
    const filters = current();
    const list = applyFilters(data.jobs, filters, hasProfile ? state.profile() : null);
    const pages = Math.max(1, Math.ceil(list.length / PAGE));
    page = Math.min(page, pages);
    const params = new URLSearchParams(filters);
    if (page > 1) params.set("page", page);
    setQuery(params);
    document.getElementById("resultsCount").textContent = `${list.length} recruitment${list.length === 1 ? "" : "s"}: ${describeFilters(filters)}`;
    const res = document.getElementById("results");
    if (!list.length) {
      res.innerHTML = emptyState("No recruitments match these filters",
        filters.match ? "None of the listings with these filters matches your profile right now. Remove the profile match filter to see them all, with the reason each one does not fit."
          : "Try removing the age or qualification filter, or include closed recruitments to see past notices.",
        `<button class="btn" type="button" id="emptyReset">Reset filters</button>`);
      document.getElementById("emptyReset").addEventListener("click", () => { location.hash = "#/govt"; });
      document.getElementById("pager").innerHTML = "";
      return;
    }
    const slice = list.slice((page - 1) * PAGE, page * PAGE);
    res.innerHTML = `<ul class="notice-list">${slice.map((j) => noticeRow(j)).join("")}</ul>
      <p class="small muted" style="margin-top:10px">Data ${data.source === "live" ? "loaded live from the reviewed database" : `published ${fmtDate((data.generated_at || "").slice(0, 10))}`}.</p>`;
    wireNoticeActions(res, byId);
    const pager = document.getElementById("pager");
    pager.innerHTML = pages > 1 ? Array.from({ length: pages }, (_, i) => i + 1).map((p) =>
      `<button class="btn btn-small" type="button" data-page="${p}" ${p === page ? 'aria-current="page"' : ""}>${p}</button>`).join("") : "";
    pager.querySelectorAll("[data-page]").forEach((b) => b.addEventListener("click", () => { page = Number(b.dataset.page); draw(); window.scrollTo(0, 0); }));
  }

  const redraw = debounce(() => { page = 1; draw(); }, 150);
  form.addEventListener("input", redraw);
  form.addEventListener("change", redraw);
  form.addEventListener("submit", (e) => e.preventDefault());
  form.addEventListener("reset", () => setTimeout(() => { page = 1; draw(); }, 0));
  document.getElementById("f-sort").addEventListener("change", () => draw());
  document.getElementById("saveSearch").addEventListener("click", async () => {
    const filters = current();
    const name = await promptDialog("Save this search", "Name", describeFilters(filters).slice(0, 80), "Save search");
    if (!name) return;
    try {
      await store.saveSearch({ name: name.trim().slice(0, 80), scope: "govt", query: filters, notify: true });
      toast(`Saved "${name}". New matching notices will appear in your notifications.`, { action: { label: "Manage", run: () => { location.hash = "#/dashboard"; } } });
    } catch (e) { toast(`Could not save the search: ${e.message}`, { error: true }); }
  });
  draw();
}
