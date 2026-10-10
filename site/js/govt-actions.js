// Save / compare buttons for government notice rows.
import * as state from "./state.js";
import { ICONS, toast, esc } from "./ui.js";

export function wireNoticeActions(root, jobsById) {
  root.querySelectorAll(".notice-actions[data-id]").forEach((box) => {
    const j = jobsById[box.dataset.id];
    if (!j) return;
    const saved = state.isSaved("govt", j.id);
    const inCompare = state.compareList().includes(j.id);
    box.innerHTML = `
      <button class="btn btn-small" type="button" data-act="save" aria-pressed="${saved}" data-guide="Save to your watchlist. You get reminders before the last date and a notice if dates change.">${saved ? ICONS.starFilled : ICONS.star}<span>${saved ? "Saved" : "Save"}</span></button>
      <label class="check small" data-guide="Tick up to four jobs, then open Compare to see them side by side."><input type="checkbox" data-act="compare" ${inCompare ? "checked" : ""}> Compare</label>`;
    box.querySelector('[data-act="save"]').addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.setAttribute("aria-busy", "true");
      try {
        const now = await state.toggleSave("govt", j.id, state.govtSnapshot(j));
        btn.setAttribute("aria-pressed", String(now));
        btn.innerHTML = `${now ? ICONS.starFilled : ICONS.star}<span>${now ? "Saved" : "Save"}</span>`;
        toast(now ? `Saved ${j.short_title || j.title}` : "Removed from saved jobs", now ? { action: { label: "View saved", run: () => { location.hash = "#/dashboard"; } } } : {});
      } catch (err) {
        toast(`Could not save: ${err.message}`, { error: true });
      } finally { btn.removeAttribute("aria-busy"); }
    });
    box.querySelector('[data-act="compare"]').addEventListener("change", (e) => {
      if (!state.toggleCompare(j.id)) {
        e.target.checked = false;
        toast("You can compare up to four jobs. Remove one from the compare list first.");
      }
    });
  });
}

export function reportButton(kind, key) {
  return `<button class="btn btn-quiet btn-small" type="button" data-report="${esc(kind)}|${esc(key)}">${ICONS.flag}<span>Report a problem</span></button>`;
}
