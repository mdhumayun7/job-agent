// Notification center: computed from the published data and the visitor's own
// saved jobs, saved searches and profile. Each notification has a stable key, so
// it is shown once, can be marked read, and is never duplicated.
import * as store from "./store.js";
import * as state from "./state.js";
import { govt } from "./data.js";
import { buildNotifications } from "./notify-core.js";

export { ANNOUNCEMENTS } from "./notify-core.js";

let cached = { items: [], unread: 0 };
export const unreadCount = () => cached.unread;

export async function computeNotifications() {
  const [{ jobs }, readState, searches] = await Promise.all([govt(), store.notifState().catch(() => ({})), store.listSearches().catch(() => [])]);
  const unique = buildNotifications({ jobs, saved: state.saved(), profile: state.profile(), prefs: state.prefs(), searches });
  unique.forEach((n) => { const st = readState[n.key]; n.read = Boolean(st?.read_at); n.dismissed = Boolean(st?.dismissed); });
  const visible = unique.filter((n) => !n.dismissed);
  visible.sort((a, b) => Number(a.read) - Number(b.read) || String(b.date || "").localeCompare(String(a.date || "")));
  cached = { items: visible, unread: visible.filter((n) => !n.read).length };
  return cached;
}

export async function refreshNotifications() {
  try { await computeNotifications(); window.dispatchEvent(new CustomEvent("notif:computed")); }
  catch (e) { console.warn("notifications unavailable", e); }
}

window.addEventListener("store:change", (e) => { if (["saved", "profile", "searches", "notif", "auth", "prefs"].includes(e.detail)) refreshNotifications(); });
