// Small DOM helpers shared by every view.

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);

// Only http(s) links from third-party data are rendered as links.
export const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : null);

export function $(sel, root = document) { return root.querySelector(sel); }
export function $$(sel, root = document) { return [...root.querySelectorAll(sel)]; }

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function fmtDate(iso, opts = {}) {
  if (!iso) return "";
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  if (isNaN(d)) return esc(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}${opts.noYear ? "" : ` ${d.getFullYear()}`}`;
}

export function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function daysBetween(fromIso, toIso) {
  const a = new Date(`${fromIso}T00:00:00`), b = new Date(`${toIso}T00:00:00`);
  return Math.round((b - a) / 86400000);
}

export function relDays(iso) {
  if (!iso) return "";
  const n = daysBetween(todayISO(), String(iso).slice(0, 10));
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  if (n === -1) return "yesterday";
  return n > 0 ? `in ${n} days` : `${-n} days ago`;
}

// The deadline stamp: day + month of the last date to apply, coloured by urgency.
export function stamp(job) {
  const end = job.dates?.application_end;
  if (!end) {
    const exam = job.dates?.exam;
    if (exam) {
      const d = new Date(`${exam}T00:00:00`);
      return `<div class="stamp none" title="No application window on record; exam date shown"><span class="m">Exam</span><span class="d" style="font-size:1rem;padding:0">${d.getDate()} ${MONTHS[d.getMonth()]}</span></div>`;
    }
    return `<div class="stamp none" title="Last date not recorded"><span class="d">No date</span></div>`;
  }
  const d = new Date(`${end}T00:00:00`);
  const left = daysBetween(todayISO(), end);
  const cls = left < 0 ? "closed" : left <= 3 ? "urgent" : left <= 10 ? "soon" : "";
  const label = left < 0 ? `Closed on ${fmtDate(end)}` : `Last date ${fmtDate(end)}, ${relDays(end)}`;
  return `<div class="stamp ${cls}" title="${esc(label)}" aria-label="${esc(label)}"><span class="d">${d.getDate()}</span><span class="m">${MONTHS[d.getMonth()]}</span><span class="y">${d.getFullYear()}</span></div>`;
}

export function statusTag(status) {
  const text = { open: "Applications open", upcoming: "Opening soon", closed: "Closed", unknown: "Dates not recorded" }[status] || status;
  return `<span class="tag ${esc(status)}">${text}</span>`;
}

export function verifyTag(job) {
  const v = job.verification?.status;
  if (v === "verified") return `<span class="tag verified" title="Checked against the official notice on ${esc(fmtDate(job.verification.checked_on))}">Checked against official notice</span>`;
  if (v === "revised") return `<span class="tag awaiting">Revised, re-check pending</span>`;
  return `<span class="tag awaiting" title="${esc(job.verification?.method || "")}">Awaiting verification</span>`;
}

export function verdictTag(result) {
  if (!result) return "";
  return `<span class="tag match-${result.verdict}">${esc(result.label)}</span>`;
}

let toastRegion;
export function toast(message, { error = false, action = null, timeout = 4500 } = {}) {
  toastRegion ||= document.getElementById("toasts");
  const el = document.createElement("div");
  el.className = `toast${error ? " error" : ""}`;
  el.setAttribute("role", error ? "alert" : "status");
  el.innerHTML = `<span>${esc(message)}</span>`;
  if (action) {
    const b = document.createElement("button");
    b.textContent = action.label;
    b.addEventListener("click", () => { action.run(); el.remove(); });
    el.appendChild(b);
  }
  toastRegion.appendChild(el);
  setTimeout(() => el.remove(), timeout);
}

export function skeletonRows(n = 5) {
  return `<ul class="notice-list" aria-busy="true" aria-label="Loading">${Array.from({ length: n }, () =>
    `<li class="notice-skeleton"><div class="skeleton" style="width:60%"></div><div class="skeleton" style="width:40%"></div><div class="skeleton" style="width:80%"></div></li>`).join("")}</ul>`;
}

export function emptyState(title, body, actionHtml = "") {
  return `<div class="empty"><h2>${esc(title)}</h2><p>${esc(body)}</p>${actionHtml}</div>`;
}

export function breadcrumb(items) {
  return `<nav class="breadcrumb" aria-label="Breadcrumb"><ol>${items.map((it, i) =>
    i === items.length - 1 ? `<li aria-current="page">${esc(it.label)}</li>` : `<li><a href="${esc(it.href)}">${esc(it.label)}</a></li>`).join("")}</ol></nav>`;
}

export function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export const ICONS = {
  star: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>',
  starFilled: '<svg class="icon" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>',
  search: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>',
  bell: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 8a6 6 0 1112 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 003.4 0"/></svg>',
  user: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0116 0"/></svg>',
  doc: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z"/><path d="M14 3v6h6"/></svg>',
  external: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/></svg>',
  flag: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 21V4h11l-2 4 2 4H5"/></svg>',
  compare: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 4v16M15 4v16M4 8h5M15 16h5"/></svg>',
  theme: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>',
  guide: '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 114 2c-1 .7-1.5 1.2-1.5 2.5"/><path d="M12 17h.01"/></svg>',
};

export function confirmDialog(title, body, confirmLabel = "Confirm", danger = false) {
  return new Promise((resolve) => {
    const d = document.createElement("dialog");
    d.setAttribute("aria-labelledby", "cd-title");
    d.innerHTML = `<div class="dialog-body"><h2 id="cd-title">${esc(title)}</h2><p>${esc(body)}</p></div>
      <div class="dialog-actions"><button class="btn" value="cancel">Cancel</button><button class="btn ${danger ? "btn-danger" : "btn-primary"}" value="ok">${esc(confirmLabel)}</button></div>`;
    document.body.appendChild(d);
    d.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { d.close(b.value); }));
    d.addEventListener("close", () => { resolve(d.returnValue === "ok"); d.remove(); });
    d.showModal();
  });
}

export function setTitle(title, description) {
  document.title = title ? `${title} | Job Agent` : "Job Agent: government and company jobs for students";
  const m = document.querySelector('meta[name="description"]');
  if (m && description) m.setAttribute("content", description);
}

export function promptDialog(title, label, value = "", confirmLabel = "Save") {
  return new Promise((resolve) => {
    const d = document.createElement("dialog");
    d.setAttribute("aria-labelledby", "pd-title");
    d.innerHTML = `<form method="dialog"><div class="dialog-body"><h2 id="pd-title">${esc(title)}</h2>
      <div class="field"><label for="pd-input">${esc(label)}</label><input id="pd-input" type="text" maxlength="80" required value="${esc(value)}"></div></div>
      <div class="dialog-actions"><button class="btn" value="cancel" formnovalidate>Cancel</button><button class="btn btn-primary" value="ok">${esc(confirmLabel)}</button></div></form>`;
    document.body.appendChild(d);
    const input = d.querySelector("input");
    d.addEventListener("close", () => { resolve(d.returnValue === "ok" ? input.value.trim() : null); d.remove(); });
    d.showModal();
    input.select();
  });
}
