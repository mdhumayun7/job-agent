import { govt, companyStats } from "../data.js";
import * as state from "../state.js";
import { evaluate } from "../eligibility.js";
import { CATEGORY_LIST, CATEGORY_HELP } from "../govt-filter.js";
import { wireNoticeActions } from "../govt-actions.js";
import { esc, stamp, statusTag, verifyTag, verdictTag, fmtDate, setTitle, skeletonRows } from "../ui.js";

export function noticeRow(j, { showEval = true } = {}) {
  const profile = state.profile();
  const ev = showEval && state.hasProfile() ? (j._eval || evaluate(j, profile)) : null;
  const facts = [];
  if (j.vacancies?.total) facts.push(`<span><strong>${j.vacancies.total.toLocaleString("en-IN")}</strong> posts${j.vacancies.tentative ? " (tentative)" : ""}</span>`);
  const opts = j.qualification?.options || [];
  if (opts.length) facts.push(`<span>Qualification: <strong>${esc(qualSummary(j))}</strong></span>`);
  if (j.age && (j.age.min != null || j.age.max != null)) facts.push(`<span>Age: <strong>${j.age.min ?? "?"}-${j.age.max ?? "?"}</strong></span>`);
  if (j.dates?.exam) facts.push(`<span>Exam: <strong>${fmtDate(j.dates.exam)}</strong></span>`);
  return `<li class="notice">
    ${stamp(j)}
    <div>
      <h3><a href="#/govt/${esc(j.id)}">${esc(j.short_title || j.title)}</a></h3>
      <div class="org">${esc(j.organization)}${j.state ? `, ${esc(j.state)}` : ""}</div>
      ${facts.length ? `<div class="facts">${facts.join("")}</div>` : ""}
      <div class="tags">${statusTag(j.status)}${verifyTag(j)}${ev ? verdictTag(ev) : ""}<span class="tag">${esc(j.category)}</span></div>
    </div>
    <div class="notice-actions" data-id="${esc(j.id)}"></div>
  </li>`;
}

export function qualSummary(j) {
  const labels = { "10th": "10th", "12th": "12th", iti: "ITI", diploma: "Diploma", graduate: "Graduate", engineering: "B.E./B.Tech", postgraduate: "Post-graduate", phd: "PhD" };
  const opts = j.qualification?.options || [];
  return [...new Set(opts.map((o) => labels[o.level] || o.level))].join(" / ");
}

export async function render(app) {
  setTitle(null, "Government recruitments read from official notices, and company openings, with deadline tracking and eligibility checks against your profile.");
  app.innerHTML = `
    <section class="home-hero">
      <div class="inner">
        <div>
          <h1>Find the openings you can apply for, before the last date.</h1>
          <p class="lead">Government recruitments read from official notices and CSE / IT openings from company career sites. Add your education once and every listing shows what you meet and what you still need to check.</p>
          <form class="hero-search" role="search" id="heroSearch" data-guide="Search by exam, post, organisation or qualification, for example: SSC, Navik, graduate.">
            <label class="sr-only" for="heroQ">Search government jobs</label>
            <input id="heroQ" type="search" name="q" placeholder="Search exams, posts, organisations" autocomplete="off">
            <button class="btn btn-primary" type="submit">Search</button>
          </form>
          <p class="small muted" style="margin-top:10px">${state.hasProfile()
            ? `Your profile is set up. <a href="#/govt?match=possible&status=open">See open jobs that match it</a>.`
            : `<a href="#/profile" data-guide="Upload a resume or type your education; it is read in your browser and used to check eligibility.">Add your education</a> to see which jobs you may be eligible for.`}</p>
        </div>
        <div class="closing-board" aria-labelledby="closingTitle">
          <h2 id="closingTitle">Closing soon</h2>
          <div id="closingSoon">${skeletonRows(3)}</div>
          <p class="small" style="margin:10px 0 0"><a href="#/timeline">All deadlines and exam dates</a></p>
        </div>
      </div>
    </section>
    <div class="page">
      <section class="section" style="margin-top:8px" aria-labelledby="catTitle">
        <div class="section-head"><h2 id="catTitle">Browse by recruitment type</h2><a href="#/govt">All government jobs</a></div>
        <div class="category-grid" id="catGrid"></div>
      </section>
      <section class="section" aria-labelledby="latestTitle">
        <div class="section-head"><h2 id="latestTitle">Latest notices</h2><a href="#/govt?sort=newest">See all</a></div>
        <div id="latest">${skeletonRows(4)}</div>
      </section>
      <section class="section" aria-labelledby="updatesTitle">
        <div class="section-head"><h2 id="updatesTitle">Exams, admit cards and results</h2><a href="#/timeline">Timeline</a></div>
        <div id="updates"></div>
      </section>
      <section class="section" aria-labelledby="companyTitle">
        <div class="section-head"><h2 id="companyTitle">Company jobs</h2><a href="#/jobs">Browse company jobs</a></div>
        <div class="grid-3" id="companyStats"></div>
      </section>
    </div>`;

  document.getElementById("heroSearch").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = document.getElementById("heroQ").value.trim();
    location.hash = q ? `#/govt?q=${encodeURIComponent(q)}` : "#/govt";
  });

  try {
    const { jobs } = await govt();
    const counts = Object.fromEntries(CATEGORY_LIST.map((c) => [c, jobs.filter((j) => j.category === c && j.status !== "closed").length]));
    document.getElementById("catGrid").innerHTML = CATEGORY_LIST.map((c) =>
      `<a class="category-link" href="#/govt?cat=${encodeURIComponent(c)}" title="${esc(CATEGORY_HELP[c])}"><span>${esc(c)}</span><span class="num">${counts[c] ? `${counts[c]} open or upcoming` : "None open now"}</span></a>`).join("");

    const closing = jobs.filter((j) => j.status === "open").sort((a, b) => (a.days_left ?? 999) - (b.days_left ?? 999)).slice(0, 4);
    document.getElementById("closingSoon").innerHTML = closing.length
      ? `<ul class="notice-list">${closing.map((j) => noticeRow(j, { showEval: false })).join("")}</ul>`
      : `<p class="muted">No applications are open in the current listings. <a href="#/govt?status=upcoming">See upcoming recruitments</a>.</p>`;

    const latest = [...jobs].filter((j) => j.notice_date).sort((a, b) => b.notice_date.localeCompare(a.notice_date)).slice(0, 6);
    document.getElementById("latest").innerHTML = latest.length ? `<ul class="notice-list">${latest.map((j) => noticeRow(j)).join("")}</ul>` : "";
    const byId = Object.fromEntries(jobs.map((j) => [j.id, j]));
    wireNoticeActions(app, byId);

    const events = [];
    for (const j of jobs) {
      if (j.dates?.exam) events.push({ date: j.dates.exam, label: "Exam", text: j.dates.exam_note || "Examination", j });
      for (const ev of j.events || []) events.push({ date: ev.date, label: { admit_card: "Admit card", result: "Result", answer_key: "Answer key", exam: "Exam" }[ev.type] || "Update", text: ev.title, j });
    }
    events.sort((a, b) => b.date.localeCompare(a.date));
    document.getElementById("updates").innerHTML = events.length
      ? `<ul class="notice-list">${events.slice(0, 5).map((e) => `<li class="event"><span class="when">${fmtDate(e.date)}</span><span><strong>${esc(e.label)}:</strong> <a href="#/govt/${esc(e.j.id)}">${esc(e.j.short_title || e.j.title)}</a><br><span class="small muted">${esc(e.text)}</span></span></li>`).join("")}</ul>`
      : `<p class="muted">No exam, admit card or result updates are on record yet.</p>`;
  } catch (e) {
    document.getElementById("closingSoon").innerHTML = `<p class="callout error">Government listings could not be loaded. ${esc(e.message)}</p>`;
    document.getElementById("latest").innerHTML = "";
  }

  try {
    const s = await companyStats();
    document.getElementById("companyStats").innerHTML = [
      [s.india_jobs, "openings in India", "#/jobs?region=india"],
      [s.fresher_opportunities, "open to freshers", "#/jobs?fresher=1"],
      [s.internships, "internships", "#/jobs?intern=1"],
    ].map(([n, l, h]) => `<a class="category-link" href="${h}"><span>${esc(l)}</span><span class="num">${(n || 0).toLocaleString("en-IN")}</span></a>`).join("") +
      `<p class="small muted" style="grid-column:1/-1;margin:0">From ${s.companies} company career sites, updated ${s.generated_at ? fmtDate(s.generated_at.slice(0, 10)) : "daily"}.</p>`;
  } catch {
    document.getElementById("companyStats").innerHTML = `<p class="muted">Company listings are not available right now.</p>`;
  }
}
