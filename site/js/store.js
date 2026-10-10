// Persistence for everything a visitor does: profile, saved jobs, searches,
// notification read state, reports, and admin operations.
//
// Two backends with one interface:
//   - "device": browser localStorage (guests, or when Supabase is not configured)
//   - "account": Supabase (signed-in users), protected by row level security
// On first sign-in, anything saved on the device is moved into the account.

import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js";

const PREFIX = "ja:";
const mem = new Map();
const ls = {
  get(k, fallback) {
    try { const v = localStorage.getItem(PREFIX + k); return v == null ? (mem.has(k) ? mem.get(k) : fallback) : JSON.parse(v); }
    catch { return mem.has(k) ? mem.get(k) : fallback; }
  },
  set(k, v) { mem.set(k, v); try { localStorage.setItem(PREFIX + k, JSON.stringify(v)); } catch { /* storage blocked */ } },
  del(k) { mem.delete(k); try { localStorage.removeItem(PREFIX + k); } catch { /* ignore */ } },
};

export const backendConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
let sb = null;
let currentUser = null;
let currentRole = "user";
const listeners = new Set();

function emit(what) {
  listeners.forEach((fn) => { try { fn(what); } catch (e) { console.error(e); } });
  window.dispatchEvent(new CustomEvent("store:change", { detail: what }));
}
export function onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }

export async function init() {
  if (!backendConfigured) return;
  try {
    const { createClient } = await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm");
    sb = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { persistSession: true, autoRefreshToken: true } });
    const { data } = await sb.auth.getSession();
    await setUser(data.session?.user || null);
    sb.auth.onAuthStateChange((_e, session) => { setUser(session?.user || null); });
  } catch (e) {
    console.error("Supabase failed to load; continuing with device storage", e);
    sb = null;
  }
}

async function setUser(user) {
  const changed = (user?.id || null) !== (currentUser?.id || null);
  currentUser = user;
  currentRole = "user";
  if (user && sb) {
    const { data } = await sb.from("profiles").select("role").eq("id", user.id).maybeSingle();
    currentRole = data?.role || "user";
    if (changed) await migrateDeviceData();
  }
  if (changed) emit("auth");
}

export const mode = () => (sb && currentUser ? "account" : "device");
export const user = () => currentUser;
export const role = () => currentRole;
export const isStaff = () => currentRole === "editor" || currentRole === "admin";
export const accountsAvailable = () => Boolean(sb);

function need(res) {
  if (res.error) throw new Error(res.error.message || "Request failed");
  return res.data;
}

// ---------------------------------------------------------------- auth
export async function signIn(email, password) {
  need(await sb.auth.signInWithPassword({ email, password }));
}
export async function signUp(email, password) {
  const data = need(await sb.auth.signUp({ email, password, options: { emailRedirectTo: location.href.split("#")[0] + "#/dashboard" } }));
  return { needsConfirmation: !data.session };
}
export async function magicLink(email) {
  need(await sb.auth.signInWithOtp({ email, options: { emailRedirectTo: location.href.split("#")[0] + "#/dashboard" } }));
}
export async function signOut() {
  if (sb) await sb.auth.signOut();
  await setUser(null);
}

// ---------------------------------------------------------------- profile
const EMPTY_PROFILE = { data: {}, preferences: {} };

export async function getProfile() {
  if (mode() === "account") {
    const row = need(await sb.from("profiles").select("data, preferences, display_name, role").eq("id", currentUser.id).maybeSingle());
    return row || EMPTY_PROFILE;
  }
  return { data: ls.get("profile", {}), preferences: ls.get("prefs", {}) };
}
export async function saveProfile(data) {
  if (mode() === "account") need(await sb.from("profiles").update({ data }).eq("id", currentUser.id));
  else ls.set("profile", data);
  emit("profile");
}
export async function savePreferences(preferences) {
  if (mode() === "account") need(await sb.from("profiles").update({ preferences }).eq("id", currentUser.id));
  else ls.set("prefs", preferences);
  emit("prefs");
}

// ---------------------------------------------------------------- saved jobs / recent views
export async function listSaved() {
  if (mode() === "account") return need(await sb.from("saved_jobs").select("*").order("created_at", { ascending: false }));
  return ls.get("saved", []);
}
export async function saveJob(job_kind, job_key, snapshot) {
  const row = { job_kind, job_key, snapshot, created_at: new Date().toISOString() };
  if (mode() === "account") need(await sb.from("saved_jobs").upsert({ job_kind, job_key, snapshot }));
  else ls.set("saved", [row, ...ls.get("saved", []).filter((r) => !(r.job_kind === job_kind && r.job_key === job_key))]);
  emit("saved");
}
export async function unsaveJob(job_kind, job_key) {
  if (mode() === "account") need(await sb.from("saved_jobs").delete().match({ job_kind, job_key }));
  else ls.set("saved", ls.get("saved", []).filter((r) => !(r.job_kind === job_kind && r.job_key === job_key)));
  emit("saved");
}
export async function addRecent(job_kind, job_key, snapshot) {
  try {
    if (mode() === "account") await sb.from("recent_views").upsert({ job_kind, job_key, snapshot, viewed_at: new Date().toISOString() });
    else {
      const rows = ls.get("recent", []).filter((r) => !(r.job_kind === job_kind && r.job_key === job_key));
      ls.set("recent", [{ job_kind, job_key, snapshot, viewed_at: new Date().toISOString() }, ...rows].slice(0, 30));
    }
  } catch { /* history is best-effort */ }
}
export async function listRecent() {
  if (mode() === "account") return need(await sb.from("recent_views").select("*").order("viewed_at", { ascending: false }).limit(30));
  return ls.get("recent", []);
}
export async function clearRecent() {
  if (mode() === "account") need(await sb.from("recent_views").delete().eq("user_id", currentUser.id));
  else ls.set("recent", []);
  emit("recent");
}

// ---------------------------------------------------------------- saved searches
export async function listSearches() {
  if (mode() === "account") return need(await sb.from("saved_searches").select("*").order("created_at", { ascending: false }));
  return ls.get("searches", []);
}
export async function saveSearch({ name, scope, query, notify = false }) {
  const row = { name, scope, query: { ...query, saved_at: new Date().toISOString() }, notify };
  if (mode() === "account") need(await sb.from("saved_searches").insert(row));
  else ls.set("searches", [{ id: crypto.randomUUID(), created_at: new Date().toISOString(), ...row }, ...ls.get("searches", [])]);
  emit("searches");
}
export async function updateSearch(id, patch) {
  if (mode() === "account") need(await sb.from("saved_searches").update(patch).eq("id", id));
  else ls.set("searches", ls.get("searches", []).map((s) => (s.id === id ? { ...s, ...patch } : s)));
  emit("searches");
}
export async function deleteSearch(id) {
  if (mode() === "account") need(await sb.from("saved_searches").delete().eq("id", id));
  else ls.set("searches", ls.get("searches", []).filter((s) => s.id !== id));
  emit("searches");
}

// ---------------------------------------------------------------- notification read state
export async function notifState() {
  if (mode() === "account") {
    const rows = need(await sb.from("notification_state").select("*"));
    return Object.fromEntries(rows.map((r) => [r.notif_key, r]));
  }
  return ls.get("notif", {});
}
export async function setNotifState(keys, patch) {
  const list = Array.isArray(keys) ? keys : [keys];
  if (mode() === "account") {
    need(await sb.from("notification_state").upsert(list.map((notif_key) => ({ notif_key, ...patch }))));
  } else {
    const s = ls.get("notif", {});
    list.forEach((k) => { s[k] = { ...(s[k] || {}), ...patch }; });
    ls.set("notif", s);
  }
  emit("notif");
}

// ---------------------------------------------------------------- reports
export async function report(job_kind, job_key, reason, details) {
  if (!sb || !currentUser) throw new Error("Sign in to send a report, so the team can follow up.");
  need(await sb.from("reports").insert({ job_kind, job_key, reason, details: details || null }));
}

// ---------------------------------------------------------------- delete everything
export async function deleteAllData() {
  if (mode() === "account") {
    need(await sb.rpc("delete_my_account"));
    await sb.auth.signOut();
    await setUser(null);
  }
  ["profile", "prefs", "saved", "recent", "searches", "notif", "compare", "guide"].forEach((k) => ls.del(k));
  emit("all");
}

// ---------------------------------------------------------------- device-only conveniences
export const local = ls;

async function migrateDeviceData() {
  const profile = ls.get("profile", {});
  const saved = ls.get("saved", []);
  const searches = ls.get("searches", []);
  if (!Object.keys(profile).length && !saved.length && !searches.length) return;
  try {
    const remote = await getProfile();
    if (!Object.keys(remote.data || {}).length && Object.keys(profile).length) await saveProfile(profile);
    if (saved.length) need(await sb.from("saved_jobs").upsert(saved.map(({ job_kind, job_key, snapshot }) => ({ job_kind, job_key, snapshot }))));
    if (searches.length) need(await sb.from("saved_searches").insert(searches.map(({ name, scope, query, notify }) => ({ name, scope, query, notify }))));
    ["profile", "saved", "searches"].forEach((k) => ls.del(k));
    window.dispatchEvent(new CustomEvent("store:migrated"));
  } catch (e) {
    console.error("Could not move device data into the account", e);
  }
}

// ---------------------------------------------------------------- admin (staff only; enforced by RLS)
export const admin = {
  async list() { return need(await sb.from("govt_jobs").select("id, data, published, archived, source_kind, updated_at").order("updated_at", { ascending: false })); },
  async upsert(id, data, flags = {}) { need(await sb.from("govt_jobs").upsert({ id, data, ...flags })); },
  async setFlags(id, flags) { need(await sb.from("govt_jobs").update(flags).eq("id", id)); },
  async remove(id) { need(await sb.from("govt_jobs").delete().eq("id", id)); },
  async reports(status = "open") { return need(await sb.from("reports").select("*").eq("status", status).order("created_at", { ascending: false })); },
  async resolve(id, status, note) {
    need(await sb.from("reports").update({ status, resolution_note: note || null, resolved_by: currentUser.id, resolved_at: new Date().toISOString() }).eq("id", id));
  },
  async audit(limit = 100) { return need(await sb.from("audit_log").select("id, row_id, action, actor, at").order("at", { ascending: false }).limit(limit)); },
  async linkChecks() { return need(await sb.from("link_checks").select("*").eq("ok", false).order("checked_at", { ascending: false })); },
};
