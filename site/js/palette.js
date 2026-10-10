// Command center: one search box for pages, actions, categories, jobs and saved
// searches (Ctrl+K or "/"), plus two-key shortcuts such as "g g".
import { govt } from "./data.js";
import * as store from "./store.js";
import { CATEGORY_LIST } from "./govt-filter.js";
import { esc } from "./ui.js";

const PAGES = [
  ["Home", "#/"], ["Government jobs", "#/govt"], ["Company jobs", "#/jobs"], ["Deadlines and exam dates", "#/timeline"],
  ["Career explorer", "#/explorer"], ["Your profile and resume", "#/profile"], ["Dashboard", "#/dashboard"],
  ["Notifications", "#/notifications"], ["Compare jobs", "#/compare"], ["Privacy and your data", "#/privacy"], ["How the data is collected", "#/about"],
];
const ACTIONS = [
  ["Find government jobs I may be eligible for", "#/govt?match=possible&status=open"],
  ["Upload or update my resume", "#/profile"],
  ["Applications closing this week", "#/govt?status=open&deadline=7"],
  ["View application deadlines", "#/timeline?show=active"],
  ["My saved jobs", "#/dashboard"],
  ["Search company jobs in India for freshers", "#/jobs?fresher=1&region=india"],
];
const SHORTCUTS = { h: "#/", g: "#/govt", j: "#/jobs", t: "#/timeline", e: "#/explorer", p: "#/profile", d: "#/dashboard", n: "#/notifications", c: "#/compare" };

let dialog, input, listEl, items = [], sel = 0;

function contextual() {
  const h = location.hash;
  const m = h.match(/^#\/govt\/([a-z0-9-]+)/);
  if (m) {
    return [
      { group: "On this page", label: "Open the official notification", run: () => { const a = document.getElementById("noticeLink") || document.getElementById("applyLink"); if (a) a.click(); } },
      { group: "On this page", label: "Go to my eligibility checklist", run: () => document.getElementById("checklistPanel")?.scrollIntoView({ behavior: "smooth" }) },
      { group: "On this page", label: "Compare with other jobs", href: "#/compare" },
    ];
  }
  if (h.startsWith("#/govt")) return [{ group: "On this page", label: "Jump to filters", run: () => document.getElementById("f-q")?.focus() }];
  return [];
}

async function build(q) {
  const ql = q.trim().toLowerCase();
  const match = (s) => !ql || s.toLowerCase().includes(ql);
  const out = [];
  if (!ql) out.push(...contextual());
  out.push(...ACTIONS.filter(([l]) => match(l)).map(([label, href]) => ({ group: "Actions", label, href })));
  out.push(...PAGES.filter(([l]) => match(l)).map(([label, href]) => ({ group: "Pages", label, href })));
  if (store.isStaff()) out.push(...[["Admin: records", "#/admin/records"], ["Admin: reports", "#/admin/reports"]].filter(([l]) => match(l)).map(([label, href]) => ({ group: "Pages", label, href })));
  if (ql) {
    out.push(...CATEGORY_LIST.filter((c) => match(c)).map((c) => ({ group: "Recruitment types", label: `${c} jobs`, href: `#/govt?cat=${encodeURIComponent(c)}` })));
    try {
      const { jobs } = await govt();
      const terms = ql.split(/\s+/);
      out.push(...jobs.filter((j) => terms.every((t) => j._search.includes(t))).slice(0, 6)
        .map((j) => ({ group: "Government jobs", label: j.short_title || j.title, hint: j.status === "open" ? "open" : j.status, href: `#/govt/${j.id}` })));
    } catch { /* offline */ }
    try {
      const searches = await store.listSearches();
      out.push(...searches.filter((s) => match(s.name)).slice(0, 4).map((s) => ({ group: "Saved searches", label: s.name,
        href: `${s.scope === "govt" ? "#/govt" : "#/jobs"}?${new URLSearchParams(Object.fromEntries(Object.entries(s.query || {}).filter(([k]) => k !== "saved_at")))}` })));
    } catch { /* ignore */ }
    out.push({ group: "Search", label: `Search government jobs for "${q.trim()}"`, href: `#/govt?q=${encodeURIComponent(q.trim())}` });
    out.push({ group: "Search", label: `Search company jobs for "${q.trim()}"`, href: `#/jobs?q=${encodeURIComponent(q.trim())}` });
  }
  return out;
}

function draw() {
  let lastGroup = "";
  listEl.innerHTML = items.length ? items.map((it, i) => {
    const g = it.group !== lastGroup ? `<li class="group" role="presentation">${esc(it.group)}</li>` : "";
    lastGroup = it.group;
    return `${g}<li role="option" id="pal-${i}" aria-selected="${i === sel}" data-i="${i}"><span>${esc(it.label)}</span>${it.hint ? `<span class="kind">${esc(it.hint)}</span>` : ""}</li>`;
  }).join("") : `<li class="group" role="presentation">No results. Try fewer words.</li>`;
  input.setAttribute("aria-activedescendant", items.length ? `pal-${sel}` : "");
  listEl.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
}

async function refresh() {
  const q = input.value;
  const res = await build(q);
  if (input.value !== q) return;
  items = res; sel = 0; draw();
}

function choose(i) {
  const it = items[i];
  if (!it) return;
  dialog.close();
  if (it.run) setTimeout(it.run, 50);
  else location.hash = it.href;
}

export function openPalette() {
  if (dialog.open) return;
  input.value = "";
  dialog.showModal();
  input.focus();
  refresh();
}

function showShortcuts() {
  const d = document.createElement("dialog");
  d.setAttribute("aria-labelledby", "sc-title");
  d.innerHTML = `<div class="dialog-body"><h2 id="sc-title">Keyboard shortcuts</h2><table class="kv">
    <tr><th>Search everything</th><td><kbd>Ctrl</kbd> <kbd>K</kbd> or <kbd>/</kbd></td></tr>
    ${Object.entries({ h: "Home", g: "Government jobs", j: "Company jobs", t: "Deadlines", e: "Career explorer", p: "Profile", d: "Dashboard", n: "Notifications", c: "Compare" })
      .map(([k, l]) => `<tr><th>${l}</th><td><kbd>g</kbd> then <kbd>${k}</kbd></td></tr>`).join("")}
    <tr><th>Open the guide</th><td><kbd>Alt</kbd> <kbd>G</kbd></td></tr><tr><th>This list</th><td><kbd>?</kbd></td></tr></table></div>
    <div class="dialog-actions"><button class="btn" type="button">Close</button></div>`;
  document.body.appendChild(d);
  d.querySelector("button").addEventListener("click", () => d.close());
  d.addEventListener("close", () => d.remove());
  d.showModal();
}

export function initPalette() {
  dialog = document.createElement("dialog");
  dialog.className = "palette";
  dialog.setAttribute("aria-label", "Search pages, actions and jobs");
  dialog.innerHTML = `<input type="text" role="combobox" aria-expanded="true" aria-controls="palList" aria-autocomplete="list" placeholder="Search jobs, pages and actions" autocomplete="off">
    <ul id="palList" role="listbox" aria-label="Results"></ul>
    <div class="palette-foot"><span><kbd>Up</kbd> <kbd>Down</kbd> to move</span><span><kbd>Enter</kbd> to open</span><span><kbd>Esc</kbd> to close</span><span><kbd>?</kbd> all shortcuts</span></div>`;
  document.body.appendChild(dialog);
  input = dialog.querySelector("input");
  listEl = dialog.querySelector("ul");
  let t;
  input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(refresh, 80); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(items.length - 1, sel + 1); draw(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(0, sel - 1); draw(); }
    else if (e.key === "Enter") { e.preventDefault(); choose(sel); }
  });
  listEl.addEventListener("click", (e) => { const li = e.target.closest("[data-i]"); if (li) choose(Number(li.dataset.i)); });
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });

  let pendingG = 0;
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); return; }
    if (typing || e.ctrlKey || e.metaKey || e.altKey || document.querySelector("dialog[open]")) return;
    if (e.key === "/") { e.preventDefault(); openPalette(); return; }
    if (e.key === "?") { e.preventDefault(); showShortcuts(); return; }
    if (e.key === "g") { pendingG = Date.now(); return; }
    if (pendingG && Date.now() - pendingG < 1200 && SHORTCUTS[e.key]) { e.preventDefault(); location.hash = SHORTCUTS[e.key]; }
    pendingG = 0;
  });
}
