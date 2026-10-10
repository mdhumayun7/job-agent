import * as store from "../store.js";
import { breadcrumb, setTitle } from "../ui.js";

export async function render(app, { match }) {
  if (match[1] === "privacy") return privacy(app);
  return about(app);
}

function privacy(app) {
  setTitle("Privacy and your data", "What this site stores, why, and how to delete it.");
  app.innerHTML = `<div class="page" style="max-width:760px">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "Privacy and your data" }])}
    <h1>Privacy and your data</h1>
    <h2>Your resume</h2>
    <p>When you add a resume, the file is opened and read inside your browser. It is never uploaded to a server and never stored. We keep only the details you review and confirm: qualifications, skills, certifications and years of experience. Contact details and date of birth are not read from the resume.</p>
    <h2>What is stored</h2>
    <ul>
      <li>Profile: education, skills, certifications, experience, and optionally date of birth, category, state and disability status.</li>
      <li>Saved jobs, saved searches, recently viewed jobs, notification read state and dashboard preferences.</li>
      <li>Reports you send about a listing.</li>
    </ul>
    <p>${store.accountsAvailable() ? "If you are signed in, this is stored in your account database, where row-level security lets only you read your rows. If you are not signed in, it is stored in this browser only." : "All of it is stored in this browser only."}</p>
    <h2>How it is used</h2>
    <p>Only to show eligibility checks, recommendations, reminders and your dashboard. It is not sold, shared, or used to train models. Optional personal details (date of birth, category, state, disability) are used only to compare with age limits, relaxations and state rules in notices.</p>
    <h2>Email alerts</h2>
    <p>Off by default. If you turn them on, at most one email a day lists deadlines for jobs you saved and new matches for your profile.</p>
    <h2>Deleting your data</h2>
    <p>Delete your profile from the <a href="#/profile">profile page</a>, or everything (including your account) from the <a href="#/dashboard">dashboard</a>. Deletion is immediate and permanent.</p>
  </div>`;
}

function about(app) {
  setTitle("How the data is collected", "Where government and company listings come from, how they are checked, and the limits of eligibility estimates.");
  app.innerHTML = `<div class="page" style="max-width:760px">
    ${breadcrumb([{ label: "Home", href: "#/" }, { label: "How the data is collected" }])}
    <h1>How the data is collected</h1>
    <p>Job Agent is an independent student project. It is not affiliated with, endorsed by, or acting for any government body, recruitment board or company.</p>
    <h2>Government recruitments</h2>
    <p>Each record is read from the official notice or the organisation's official recruitment page, and links back to it. Records show one of two states:</p>
    <ul><li><strong>Checked against official notice</strong>: an editor read the notice and entered the dates, eligibility, fees and vacancies. The check date is shown on the listing.</li>
      <li><strong>Awaiting verification</strong>: collected automatically from an official page (for example ISRO and C-DAC). The title, dates and link come from that page; eligibility and fees have not been reviewed.</li></ul>
    <p>Nothing is copied from other job portals, and vacancies, dates or rules are never estimated. When a value is not in the notice, the listing says "Not recorded".</p>
    <h2>Company jobs</h2>
    <p>Collected daily from companies' own career sites and public job-board feeds. Apply links go to the company's site.</p>
    <h2>Eligibility checks</h2>
    <p>Checks compare your profile with the conditions recorded for a notice. They are estimates, not decisions: equivalent qualifications, relaxations for special categories, physical standards and documents are decided by the recruiting body. Always read the official notice before applying.</p>
    <h2>Corrections</h2>
    <p>Use "Report a problem" on any listing. Reports go to an editor, who checks them against the official notice.</p>
  </div>`;
}

export async function renderNotFound(app) {
  setTitle("Page not found");
  app.innerHTML = `<div class="page"><div class="empty"><h1 style="font-size:1.4rem">This page does not exist</h1>
    <p>The link may be mistyped or the page may have moved.</p>
    <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap"><a class="btn btn-primary" href="#/govt">Government jobs</a><a class="btn" href="#/jobs">Company jobs</a><a class="btn" href="#/">Home</a></div></div></div>`;
}
