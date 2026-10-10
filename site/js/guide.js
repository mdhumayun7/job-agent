// Guide: contextual help for the current page.
//  - A help button (all devices) opens tips and "show me" walkthroughs that
//    highlight the real element on the page.
//  - On devices with a mouse, an optional pointer companion follows the cursor
//    and shows a short tip when hovering anything marked with data-guide.
//  - Focused form fields with data-tip show an inline hint below the field.
// Nothing typed into fields is read or stored. Respects reduced motion, and
// can be switched off (preference kept on this device).
import { local } from "./store.js";
import { ICONS, esc } from "./ui.js";

const DEFAULTS = { enabled: true, follow: true };
let settings = { ...DEFAULTS, ...(local.get("guide", {}) || {}) };
const save = () => local.set("guide", settings);
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
const finePointer = matchMedia("(pointer: fine)");
let route = "#/";
let panel, fab, follower, tipEl;

const PAGES = [
  [/^#\/?$/, "Home", ["Search by exam, post or organisation in the search box.", "The dated blocks show each recruitment's last date to apply; red means three days or less.", "Add your education once to see eligibility on every listing."],
    [{ label: "Find jobs I may be eligible for", href: "#/govt?match=possible&status=open" }, { label: "Upload your resume", href: "#/profile" }, { label: "View application deadlines", href: "#/timeline?show=active" }]],
  [/^#\/govt\/[a-z0-9-]+/, "Recruitment details", ["Important dates come first; past dates are struck through.", "Your eligibility checklist compares each condition with your profile. Yellow means check it in the notice.", "Always apply through the official links on this page."],
    [{ label: "Show me the key parts of this page", steps: [
      { sel: "#h-dates", text: "Start with the last date to apply and the exam date." },
      { sel: "#checklistPanel", text: "Check which conditions you meet. Fill missing details here to recheck." },
      { sel: "#officialLinks", text: "Read the official notice before you apply. The portal link opens the official site." }] },
     { label: "Open official notification", run: () => (document.getElementById("noticeLink") || document.getElementById("applyLink"))?.click(), needs: "#noticeLink, #applyLink" },
     { label: "Compare with other jobs", href: "#/compare" }]],
  [/^#\/govt/, "Government jobs", ["Combine filters on the left; the count updates as you type.", "\"Awaiting verification\" listings came from official pages automatically and have not been reviewed yet.", "Save a search to get notified about new matching notices."],
    [{ label: "Show me how to filter", steps: [
      { sel: "#f-q", text: "Type a post or exam name, for example Navik or CHSL." },
      { sel: "#f-status", text: "Choose applications open now, opening soon, or closed." },
      { sel: "#f-qual", text: "Pick your highest qualification to hide posts that need more." },
      { sel: "#saveSearch", text: "Save these filters to get alerts for new notices." }] },
     { label: "Applications closing this week", href: "#/govt?status=open&deadline=7" }, { label: "Upload your resume", href: "#/profile" }]],
  [/^#\/jobs/, "Company jobs", ["The score compares each job with the skills in your profile.", "Region defaults to India and remote India; switch it in the filters.", "Apply buttons open the company's own careers site."],
    [{ label: "Show me the filters", steps: [{ sel: "#c-q", text: "Search by title, company, skill or city." }, { sel: "#c-region", text: "Choose where the job is." }] }, { label: "Add skills to my profile", href: "#/profile" }]],
  [/^#\/profile/, "Your profile", ["Your resume is read in this browser and is never uploaded.", "Check every detail the reader found; you can edit or remove anything.", "Personal details are optional and only used for age and state rules."],
    [{ label: "Show me what to fill", steps: [{ sel: "#drop, #quals, #personalForm", text: "Add or check your education here." }] }]],
  [/^#\/dashboard/, "Dashboard", ["Recommended jobs come from your profile; saved jobs show live deadlines.", "Use Customise dashboard to hide or reorder sections.", "Alerts and reminder timing are under Alerts and preferences."],
    [{ label: "Show me the dashboard settings", steps: [{ sel: "#customize", text: "Hide or reorder sections." }, { sel: "#prefsForm", text: "Set reminder timing and alerts." }] }, { label: "Open notifications", href: "#/notifications" }]],
  [/^#\/timeline/, "Deadlines and exam dates", ["Only confirmed dates from notices are listed.", "Use Remind me to save a job and get a reminder before its last date."], [{ label: "Only jobs I saved", href: "#/timeline?show=upcoming&mine=1" }]],
  [/^#\/explorer/, "Career explorer", ["Pick a qualification to see common routes and current listings.", "Common routes are general patterns; each notice sets its own rules."], [{ label: "Use my profile", href: "#/profile" }]],
  [/^#\/compare/, "Compare", ["Highlighted rows differ between the selected jobs.", "Remove a job with the button under its name."], [{ label: "Choose more jobs", href: "#/govt" }]],
  [/^#\/notifications/, "Notifications", ["Deadline reminders come from jobs you saved.", "Dismiss removes a notification; Mark read keeps it."], [{ label: "Change reminder timing", href: "#/dashboard" }]],
];

function pageInfo() {
  return PAGES.find(([rx]) => rx.test(route)) || ["This page", ["Press Ctrl K to search pages, actions and jobs."], []];
}

function clearHighlight() { document.querySelectorAll(".guide-highlight").forEach((el) => el.classList.remove("guide-highlight")); }

function runSteps(steps, i = 0) {
  clearHighlight();
  const step = steps[i];
  const el = step && document.querySelector(step.sel);
  const box = panel.querySelector("#guideStep");
  if (!step || !el) {
    box.innerHTML = step ? `<p class="small">That part is not on the page right now.</p>` : "";
    return;
  }
  el.classList.add("guide-highlight");
  el.scrollIntoView({ behavior: reduced.matches ? "auto" : "smooth", block: "center" });
  box.innerHTML = `<p style="margin:8px 0"><strong>Step ${i + 1} of ${steps.length}.</strong> ${esc(step.text)}</p>
    <div style="display:flex;gap:6px">${i < steps.length - 1 ? '<button class="btn btn-small btn-primary" type="button" id="gNext">Next</button>' : ""}<button class="btn btn-small" type="button" id="gDone">Done</button></div>`;
  box.querySelector("#gNext")?.addEventListener("click", () => runSteps(steps, i + 1));
  box.querySelector("#gDone").addEventListener("click", () => { clearHighlight(); box.innerHTML = ""; });
  box.querySelector("#gNext, #gDone").focus();
}

function drawPanel() {
  const [, title, tips, suggestions] = pageInfo();
  const usable = suggestions.filter((s) => !s.needs || document.querySelector(s.needs));
  panel.innerHTML = `<h2 id="guideTitle">Help: ${esc(title)}</h2>
    <ul>${tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
    ${usable.length ? `<div class="suggestions">${usable.map((s, i) => s.href
      ? `<a class="btn btn-small" href="${esc(s.href)}">${esc(s.label)}</a>`
      : `<button class="btn btn-small" type="button" data-sug="${i}">${esc(s.label)}</button>`).join("")}</div>` : ""}
    <div id="guideStep" aria-live="polite"></div>
    <hr style="border:0;border-top:1px solid var(--line);margin:12px 0">
    ${finePointer.matches && !reduced.matches ? `<label class="check small"><input type="checkbox" id="gFollow" ${settings.follow ? "checked" : ""}> Show tips next to my pointer</label>` : ""}
    <div style="display:flex;justify-content:space-between;gap:8px;margin-top:6px;flex-wrap:wrap">
      <button class="btn btn-small btn-quiet" type="button" id="gOff">Turn the guide off</button>
      <button class="btn btn-small" type="button" id="gClose">Close</button></div>
    <p class="small muted" style="margin:8px 0 0"><kbd>Alt</kbd> <kbd>G</kbd> opens this panel. <kbd>Ctrl</kbd> <kbd>K</kbd> searches everything.</p>`;
  panel.querySelectorAll("[data-sug]").forEach((b) => b.addEventListener("click", () => {
    const s = usable[Number(b.dataset.sug)];
    if (s.steps) runSteps(s.steps); else if (s.run) s.run();
  }));
  panel.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => togglePanel(false)));
  panel.querySelector("#gFollow")?.addEventListener("change", (e) => { settings.follow = e.target.checked; save(); applyFollower(); });
  panel.querySelector("#gOff").addEventListener("click", () => { settings.enabled = false; save(); togglePanel(false); mount(); });
  panel.querySelector("#gClose").addEventListener("click", () => togglePanel(false));
}

function togglePanel(open) {
  if (!panel) return;
  const show = open ?? panel.hidden;
  panel.hidden = !show;
  fab.setAttribute("aria-expanded", String(show));
  if (show) { drawPanel(); panel.querySelector("h2").focus?.(); }
  else clearHighlight();
}

// ---- pointer companion --------------------------------------------------
let raf = 0, tx = -100, ty = -100, x = -100, y = -100, hoverTimer, typingUntil = 0;
function loop() {
  x += (tx - x) * 0.25; y += (ty - y) * 0.25;
  const flip = tx > innerWidth - 300;
  follower.style.transform = `translate(${Math.round(flip ? x - 290 : x + 18)}px, ${Math.round(y + 18)}px)`;
  follower.style.flexDirection = flip ? "row-reverse" : "row";
  raf = Math.abs(tx - x) + Math.abs(ty - y) > 0.5 ? requestAnimationFrame(loop) : 0;
}
function onMove(e) {
  tx = e.clientX; ty = e.clientY;
  const overField = e.target.closest?.("input, textarea, select, [contenteditable]");
  follower.style.opacity = overField || Date.now() < typingUntil ? "0" : "1";
  if (!raf) raf = requestAnimationFrame(loop);
  const target = e.target.closest?.("[data-guide]");
  clearTimeout(hoverTimer);
  if (target && !overField) hoverTimer = setTimeout(() => { tipEl.textContent = target.dataset.guide; tipEl.classList.add("show"); }, 350);
  else tipEl.classList.remove("show");
}
const onLeave = () => { follower.style.opacity = "0"; tipEl.classList.remove("show"); };
const onKey = () => { typingUntil = Date.now() + 1500; follower.style.opacity = "0"; tipEl.classList.remove("show"); };

function applyFollower() {
  const want = settings.enabled && settings.follow && finePointer.matches && !reduced.matches;
  if (want && !follower) {
    follower = document.createElement("div");
    follower.className = "guide-cursor";
    follower.setAttribute("aria-hidden", "true");
    follower.innerHTML = `<span class="guide-dot">?</span><span class="guide-tip"></span>`;
    follower.style.transform = "translate(-100px, -100px)";
    tipEl = follower.querySelector(".guide-tip");
    document.body.appendChild(follower);
    document.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    document.addEventListener("keydown", onKey);
  } else if (!want && follower) {
    document.removeEventListener("pointermove", onMove);
    document.documentElement.removeEventListener("pointerleave", onLeave);
    document.removeEventListener("keydown", onKey);
    cancelAnimationFrame(raf); raf = 0;
    follower.remove(); follower = null;
  }
}

// ---- inline field tips (keyboard and touch friendly) ---------------------
function onFocusIn(e) {
  if (!settings.enabled) return;
  const host = e.target.closest?.("[data-tip]");
  if (!host || host.querySelector(".field-tip")) return;
  const tip = document.createElement("div");
  tip.className = "field-tip";
  tip.id = `tip-${Math.random().toString(36).slice(2, 8)}`;
  tip.textContent = host.dataset.tip;
  host.appendChild(tip);
  e.target.setAttribute("aria-describedby", [e.target.getAttribute("aria-describedby"), tip.id].filter(Boolean).join(" "));
}
function onFocusOut(e) {
  const host = e.target.closest?.("[data-tip]");
  const tip = host?.querySelector(".field-tip");
  if (!tip) return;
  e.target.setAttribute("aria-describedby", (e.target.getAttribute("aria-describedby") || "").replace(tip.id, "").trim());
  if (!e.target.getAttribute("aria-describedby")) e.target.removeAttribute("aria-describedby");
  tip.remove();
}

function mount() {
  const root = document.getElementById("guideRoot");
  root.innerHTML = "";
  applyFollower();
  if (!settings.enabled) {
    const on = document.createElement("button");
    on.className = "btn btn-small btn-quiet guide-fab";
    on.type = "button";
    on.textContent = "Turn the guide on";
    on.addEventListener("click", () => { settings.enabled = true; save(); mount(); });
    root.appendChild(on);
    panel = null;
    return;
  }
  fab = document.createElement("button");
  fab.className = "btn guide-fab";
  fab.type = "button";
  fab.setAttribute("aria-expanded", "false");
  fab.setAttribute("aria-controls", "guidePanel");
  fab.innerHTML = `${ICONS.guide}<span>Guide</span>`;
  fab.addEventListener("click", () => togglePanel());
  panel = document.createElement("section");
  panel.className = "guide-panel";
  panel.id = "guidePanel";
  panel.hidden = true;
  panel.setAttribute("aria-labelledby", "guideTitle");
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") { togglePanel(false); fab.focus(); } });
  root.append(panel, fab);
}

export function guideRouteChanged(path) {
  route = path;
  clearHighlight();
  if (panel && !panel.hidden) drawPanel();
}

export function initGuide() {
  mount();
  document.addEventListener("focusin", onFocusIn);
  document.addEventListener("focusout", onFocusOut);
  document.addEventListener("keydown", (e) => {
    if (e.altKey && e.key.toLowerCase() === "g") { e.preventDefault(); if (!settings.enabled) { settings.enabled = true; save(); mount(); } togglePanel(); }
  });
  reduced.addEventListener?.("change", applyFollower);
}
