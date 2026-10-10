// Application shell: header, footer, router, compare bar, theme.
import * as store from "./store.js";
import * as state from "./state.js";
import { esc, ICONS, toast, setTitle } from "./ui.js";
import { initPalette, openPalette } from "./palette.js";
import { initGuide, guideRouteChanged } from "./guide.js";
import { unreadCount } from "./notify.js";

const NAV = [
  { href: "#/govt", label: "Government jobs", match: /^#\/govt/ },
  { href: "#/jobs", label: "Company jobs", match: /^#\/jobs/ },
  { href: "#/timeline", label: "Deadlines", match: /^#\/timeline/ },
  { href: "#/explorer", label: "Career explorer", match: /^#\/explorer/ },
  { href: "#/dashboard", label: "Dashboard", match: /^#\/(dashboard|notifications)/ },
];

const ROUTES = [
  [/^#\/?$/, () => import("./views/home.js")],
  [/^#\/govt\/([a-z0-9-]+)$/, () => import("./views/govt-detail.js")],
  [/^#\/govt$/, () => import("./views/govt-list.js")],
  [/^#\/jobs\/(.+)$/, () => import("./views/company-detail.js")],
  [/^#\/jobs$/, () => import("./views/company-list.js")],
  [/^#\/compare$/, () => import("./views/compare.js")],
  [/^#\/timeline$/, () => import("./views/timeline.js")],
  [/^#\/explorer$/, () => import("./views/explorer.js")],
  [/^#\/profile$/, () => import("./views/profile.js")],
  [/^#\/dashboard$/, () => import("./views/dashboard.js")],
  [/^#\/notifications$/, () => import("./views/notifications.js")],
  [/^#\/admin(?:\/([a-z]+))?$/, () => import("./views/admin.js")],
  [/^#\/signin$/, () => import("./views/signin.js")],
  [/^#\/(privacy|about)$/, () => import("./views/static.js")],
];

export function parseHash() {
  const raw = location.hash || "#/";
  const [path, qs] = raw.split("?");
  return { path: path === "#" ? "#/" : path, params: new URLSearchParams(qs || "") };
}

export function setQuery(params, { replace = true } = {}) {
  const { path } = parseHash();
  const q = params.toString();
  const url = `${location.pathname}${location.search}${path}${q ? `?${q}` : ""}`;
  if (replace) history.replaceState(null, "", url); else history.pushState(null, "", url);
}

function renderHeader() {
  const { path } = parseHash();
  document.getElementById("primaryNav").innerHTML = NAV.map((n) =>
    `<a href="${n.href}"${n.match.test(path) ? ' aria-current="page"' : ""}>${esc(n.label)}</a>`).join("");
  const u = store.user();
  const count = unreadCount();
  document.getElementById("headerActions").innerHTML = `
    <button class="search-trigger" id="openPalette" type="button" aria-label="Search jobs and pages (Ctrl+K)">${ICONS.search}<span class="label">Search</span><kbd>Ctrl K</kbd></button>
    <a class="btn btn-quiet icon-btn" href="#/notifications" aria-label="Notifications${count ? `, ${count} unread` : ""}" data-guide="Notifications: new matching jobs, deadline reminders and changes to jobs you saved." style="position:relative">${ICONS.bell}${count ? `<span class="badge-count" style="position:absolute;top:2px;right:0">${count > 9 ? "9+" : count}</span>` : ""}</a>
    <button class="btn btn-quiet icon-btn" id="themeToggle" type="button" aria-label="Switch light or dark theme">${ICONS.theme}</button>
    ${u ? `<a class="btn btn-small" href="#/dashboard" title="${esc(u.email)}">${ICONS.user}<span class="sr-only">Account</span></a>`
        : store.accountsAvailable() ? `<a class="btn btn-small" href="#/signin">Sign in</a>` : `<a class="btn btn-small" href="#/profile">My profile</a>`}`;
  document.getElementById("openPalette").addEventListener("click", openPalette);
  document.getElementById("themeToggle").addEventListener("click", toggleTheme);
}

function renderFooter() {
  document.getElementById("siteFooter").innerHTML = `<div class="footer-inner">
    <div><p><strong>Job Agent</strong></p>
      <p class="footer-note">An independent student project. It is not affiliated with any government body or company. Recruitment details are read from official notices; always confirm eligibility and dates in the official notice before applying.</p></div>
    <div><h2>Government</h2><ul>
      <li><a href="#/govt?status=open">Applications open</a></li><li><a href="#/timeline">Deadlines and exam dates</a></li>
      <li><a href="#/govt?cat=SSC">SSC</a></li><li><a href="#/govt?cat=Defence">Defence</a></li><li><a href="#/govt?cat=Research">Research organisations</a></li></ul></div>
    <div><h2>Your tools</h2><ul>
      <li><a href="#/profile">Profile and resume</a></li><li><a href="#/dashboard">Dashboard</a></li>
      <li><a href="#/compare">Compare jobs</a></li><li><a href="#/explorer">Career explorer</a></li></ul></div>
    <div><h2>About</h2><ul>
      <li><a href="#/about">How the data is collected</a></li><li><a href="#/privacy">Privacy and your data</a></li>
      <li><a href="https://github.com/mdhumayun7/job-agent" rel="noopener">Source code</a></li></ul></div>
  </div>`;
}

function renderCompareBar() {
  const ids = state.compareList();
  const bar = document.getElementById("compareBar");
  const { path } = parseHash();
  if (!ids.length || path === "#/compare") { bar.innerHTML = ""; document.body.classList.remove("has-compare-bar"); return; }
  document.body.classList.add("has-compare-bar");
  bar.innerHTML = `<div class="compare-bar" role="region" aria-label="Compare list">
    <span>${ids.length} selected to compare</span>
    <a class="btn btn-small" href="#/compare">Compare</a>
    <button class="btn btn-small btn-quiet" type="button" id="clearCompare" style="color:inherit;background:transparent;border-color:transparent">Clear</button></div>`;
  document.getElementById("clearCompare").addEventListener("click", () => state.setCompare([]));
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme") ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  store.local.set("theme", next);
}

let renderToken = 0;
async function route() {
  const token = ++renderToken;
  const { path, params } = parseHash();
  renderHeader();
  renderCompareBar();
  const app = document.getElementById("app");
  const hit = ROUTES.find(([rx]) => rx.test(path));
  try {
    if (!hit) {
      const mod = await import("./views/static.js");
      if (token === renderToken) await mod.renderNotFound(app);
    } else {
      const m = path.match(hit[0]);
      const mod = await hit[1]();
      if (token !== renderToken) return;
      await mod.render(app, { match: m, params, path });
    }
  } catch (e) {
    console.error(e);
    if (token === renderToken) {
      setTitle("Something went wrong");
      app.innerHTML = `<div class="page"><div class="callout error"><strong>This page could not be loaded.</strong> ${esc(e.message)}. Check your connection and <a href="${esc(location.hash)}" id="retry">try again</a>.</div></div>`;
    }
  }
  if (token === renderToken) {
    guideRouteChanged(path);
    if (!params.has("keepScroll")) window.scrollTo(0, 0);
    app.focus({ preventScroll: true });
  }
}

async function boot() {
  renderFooter();
  await store.init();
  await state.load();
  window.addEventListener("hashchange", route);
  window.addEventListener("compare:change", renderCompareBar);
  window.addEventListener("store:change", (e) => { if (["auth", "notif", "saved"].includes(e.detail)) renderHeader(); });
  window.addEventListener("notif:computed", renderHeader);
  window.addEventListener("store:migrated", () => toast("Your saved jobs and profile from this device were added to your account."));
  initPalette();
  initGuide();
  await route();
  import("./notify.js").then((m) => m.refreshNotifications()).catch(() => {});
}

boot();
