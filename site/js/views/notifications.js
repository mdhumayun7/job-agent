import * as store from "../store.js";
import { computeNotifications, refreshNotifications } from "../notify.js";
import { esc, breadcrumb, setTitle, fmtDate, toast } from "../ui.js";

const GROUPS = [
  ["deadline", "Deadlines"], ["match", "New matches"], ["update", "Changes to saved jobs"], ["search", "Saved search results"], ["announcement", "Site announcements"],
];

export async function render(app, { params }) {
  setTitle("Notifications", "Deadline reminders, new matching jobs and changes to jobs you saved.");
  const filter = params.get("show") || "all";
  app.innerHTML = `<div class="page">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Dashboard", href: "#/dashboard" }, { label: "Notifications" }])}
    <div class="page-head" style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-end">
      <div><h1>Notifications</h1><p>Recruitment updates come from official data and your saved jobs and searches. Site announcements are listed separately.</p></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" type="button" id="markAll">Mark all as read</button><a class="btn" href="#/dashboard">Notification settings</a></div>
    </div>
    <div class="toolbar"><div style="display:flex;gap:6px;flex-wrap:wrap" role="group" aria-label="Show">
      ${[["all", "All"], ["unread", "Unread"]].map(([v, l]) => `<a class="btn btn-small" href="#/notifications?show=${v}" ${filter === v ? 'aria-current="page" style="border-color:var(--ink);color:var(--ink)"' : ""}>${l}</a>`).join("")}</div></div>
    <div id="list"><div class="skeleton" style="width:60%"></div></div></div>`;

  const draw = async () => {
    const { items } = await computeNotifications();
    const shown = filter === "unread" ? items.filter((n) => !n.read) : items;
    const el = document.getElementById("list");
    if (!shown.length) {
      el.innerHTML = `<div class="empty"><h2>${filter === "unread" ? "You are all caught up" : "No notifications yet"}</h2>
        <p>Save jobs, save a search with alerts, or add your education to get reminders and new matches here.</p><a class="btn" href="#/govt">Browse government jobs</a></div>`;
      return;
    }
    el.innerHTML = GROUPS.map(([kind, label]) => {
      const g = shown.filter((n) => n.kind === kind);
      if (!g.length) return "";
      return `<section style="margin-top:18px" aria-labelledby="g-${kind}"><h2 id="g-${kind}" style="font-size:1rem">${label}</h2>
        <div class="panel" style="padding:0">${g.map((n) => `<div class="notif ${n.read ? "read" : ""}">
          <span class="dot" aria-hidden="true"></span>
          <div><a href="${esc(n.href)}" data-open="${esc(n.key)}"><strong>${esc(n.title)}</strong></a>${n.body ? `<div class="small muted">${esc(n.body)}</div>` : ""}${n.date ? `<div class="small muted">${fmtDate(String(n.date).slice(0, 10))}</div>` : ""}<span class="sr-only">${n.read ? "Read" : "Unread"}</span></div>
          <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">
            <button class="btn btn-small btn-quiet" type="button" data-toggle="${esc(n.key)}" data-read="${n.read}">${n.read ? "Mark unread" : "Mark read"}</button>
            <button class="btn btn-small btn-quiet" type="button" data-dismiss="${esc(n.key)}" aria-label="Dismiss">Dismiss</button></div>
        </div>`).join("")}</div></section>`;
    }).join("");
    el.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", async () => {
      const read = b.dataset.read === "true";
      try { await store.setNotifState(b.dataset.toggle, { read_at: read ? null : new Date().toISOString() }); await draw(); } catch (e) { toast(e.message, { error: true }); }
    }));
    el.querySelectorAll("[data-dismiss]").forEach((b) => b.addEventListener("click", async () => {
      try { await store.setNotifState(b.dataset.dismiss, { dismissed: true, read_at: new Date().toISOString() }); await draw(); toast("Notification dismissed."); } catch (e) { toast(e.message, { error: true }); }
    }));
    el.querySelectorAll("[data-open]").forEach((a) => a.addEventListener("click", () => {
      store.setNotifState(a.dataset.open, { read_at: new Date().toISOString() }).catch(() => {});
    }));
  };
  document.getElementById("markAll").addEventListener("click", async () => {
    const { items } = await computeNotifications();
    const keys = items.filter((n) => !n.read).map((n) => n.key);
    if (!keys.length) { toast("Nothing unread."); return; }
    try { await store.setNotifState(keys, { read_at: new Date().toISOString() }); await draw(); refreshNotifications(); toast(`Marked ${keys.length} as read.`); }
    catch (e) { toast(e.message, { error: true }); }
  });
  await draw();
}
