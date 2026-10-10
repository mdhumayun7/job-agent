import { govt } from "../data.js";
import * as state from "../state.js";
import { evaluate } from "../eligibility.js";
import { qualSummary } from "./home.js";
import { esc, safeUrl, breadcrumb, setTitle, fmtDate, statusTag, verifyTag, emptyState } from "../ui.js";

const ROWS = [
  ["Organisation", (j) => esc(j.organization)],
  ["Status", (j) => statusTag(j.status)],
  ["Verification", (j) => verifyTag(j)],
  ["Last date to apply", (j) => (j.dates?.application_end ? fmtDate(j.dates.application_end) : "Not recorded")],
  ["Examination", (j) => (j.dates?.exam ? fmtDate(j.dates.exam) : esc(j.dates?.exam_note || "Not recorded"))],
  ["Vacancies", (j) => (j.vacancies?.total ? `${j.vacancies.total.toLocaleString("en-IN")}${j.vacancies.tentative ? " (tentative)" : ""}` : "Not recorded")],
  ["Qualification", (j) => esc(qualSummary(j) || "Not recorded")],
  ["Age limit", (j) => (j.age?.min != null ? `${j.age.min}-${j.age.max} years${j.age.as_on ? ` (as on ${fmtDate(j.age.as_on)})` : ""}` : j.age?.born_not_before ? `Born ${fmtDate(j.age.born_not_before)} to ${fmtDate(j.age.born_not_after)}` : "Not recorded")],
  ["Application fee", (j) => (j.fee?.amount != null ? `Rs ${j.fee.amount}${j.fee.exempt?.length ? `; no fee for ${esc(j.fee.exempt.join(", "))}` : ""}` : "Not recorded")],
  ["Pay", (j) => esc(j.pay || "Not recorded")],
  ["Selection process", (j) => (j.selection_process?.length ? `<ol style="margin:0;padding-left:18px">${j.selection_process.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : "Not recorded")],
  ["Physical standards", (j) => (j.physical_standards ? "Yes" : "None recorded")],
];

export async function render(app) {
  setTitle("Compare jobs", "Compare government recruitments side by side: dates, qualification, age, fee, pay and selection process.");
  const ids = state.compareList();
  const { jobs } = await govt();
  const list = ids.map((id) => jobs.find((j) => j.id === id)).filter(Boolean);
  const head = `${breadcrumb([{ label: "Home", href: "#/" }, { label: "Government jobs", href: "#/govt" }, { label: "Compare" }])}
    <div class="page-head"><h1>Compare jobs</h1><p>Rows where the jobs differ are highlighted. Values come from each official notice.</p></div>`;
  if (list.length < 2) {
    app.innerHTML = `<div class="page">${head}${emptyState(list.length ? "Add one more job to compare" : "Nothing to compare yet",
      "Tick Compare on two to four government listings, then come back here.", `<a class="btn btn-primary" href="#/govt">Choose jobs</a>`)}</div>`;
    return;
  }
  const profile = state.profile();
  const evals = state.hasProfile() ? list.map((j) => evaluate(j, profile)) : null;
  const rows = ROWS.map(([label, fn]) => {
    const cells = list.map(fn);
    const differs = new Set(cells.map((c) => c.replace(/<[^>]+>/g, ""))).size > 1;
    return `<tr class="${differs ? "differs" : ""}"><th scope="row">${esc(label)}${differs ? '<span class="sr-only"> (differs)</span>' : ""}</th>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`;
  });
  if (evals) {
    rows.push(`<tr><th scope="row">Your profile</th>${evals.map((r) => `<td><strong>${esc(r.label)}</strong><ul style="margin:6px 0 0;padding-left:18px">${r.checks.slice(0, 3).map((c) => `<li class="small">${esc(c.label)}: ${{ match: "matches", no: "does not match", verify: "check" }[c.status]}</li>`).join("")}</ul></td>`).join("")}</tr>`);
  }
  rows.push(`<tr><th scope="row">Official links</th>${list.map((j) => `<td>${safeUrl(j.links?.notification_pdf) ? `<a href="${safeUrl(j.links.notification_pdf)}" target="_blank" rel="noopener">Notice</a><br>` : ""}${safeUrl(j.links?.apply) ? `<a href="${safeUrl(j.links.apply)}" target="_blank" rel="noopener">Apply</a>` : ""}</td>`).join("")}</tr>`);
  app.innerHTML = `<div class="page">${head}
    ${evals ? "" : `<p class="callout"><a href="#/profile">Add your education</a> to see which requirements match your profile.</p>`}
    <div class="compare-wrap"><table class="compare">
      <thead><tr><th scope="col"><span class="sr-only">Field</span></th>${list.map((j) => `<th scope="col"><a href="#/govt/${esc(j.id)}">${esc(j.short_title || j.title)}</a><br>
        <button class="btn btn-small btn-quiet" type="button" data-remove="${esc(j.id)}">Remove</button></th>`).join("")}</tr></thead>
      <tbody>${rows.join("")}</tbody></table></div>
    <p style="margin-top:14px"><a href="#/govt">Back to listings</a></p></div>`;
  app.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => {
    state.setCompare(state.compareList().filter((x) => x !== b.dataset.remove));
    render(app);
  }));
}
