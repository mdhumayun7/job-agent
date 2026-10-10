// In-memory view of the visitor's data, refreshed from the store when it changes.
import * as store from "./store.js";

const state = { profile: {}, prefs: {}, saved: [], loaded: false };
const savedKey = (kind, key) => `${kind}:${key}`;
let savedSet = new Set();

export async function load() {
  try {
    const [p, saved] = await Promise.all([store.getProfile(), store.listSaved()]);
    state.profile = p.data || {};
    state.prefs = p.preferences || {};
    state.saved = saved || [];
  } catch (e) {
    console.error(e);
  }
  savedSet = new Set(state.saved.map((r) => savedKey(r.job_kind, r.job_key)));
  state.loaded = true;
  return state;
}

store.onChange(async (what) => {
  if (["auth", "profile", "prefs", "saved", "all"].includes(what)) await load();
});

export const profile = () => state.profile;
export const prefs = () => state.prefs;
export const saved = () => state.saved;
export const isSaved = (kind, key) => savedSet.has(savedKey(kind, key));
export const hasProfile = () => Boolean((state.profile.qualifications || []).length || (state.profile.skills || []).length);

export async function toggleSave(kind, key, snapshot) {
  if (isSaved(kind, key)) { await store.unsaveJob(kind, key); return false; }
  await store.saveJob(kind, key, snapshot);
  return true;
}

// Compare list lives on the device only (it is a short-lived working set).
export function compareList() { return store.local.get("compare", []); }
export function setCompare(ids) {
  store.local.set("compare", ids.slice(0, 4));
  window.dispatchEvent(new CustomEvent("compare:change"));
}
export function toggleCompare(id) {
  const ids = compareList();
  if (ids.includes(id)) setCompare(ids.filter((x) => x !== id));
  else if (ids.length >= 4) return false;
  else setCompare([...ids, id]);
  return true;
}

export function govtSnapshot(j) {
  return { title: j.short_title || j.title, org: j.org_short || j.organization, application_end: j.dates?.application_end || null,
           exam: j.dates?.exam || null, status: j.status, url: j.links?.apply || null };
}
export function companySnapshot(j) {
  return { title: j.job_title, org: j.company, location: j.location_raw, url: j.apply_url || j.job_url || null, date_posted: j.date_posted || null };
}
