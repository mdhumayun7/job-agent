import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { evaluate, checkAge, checkEducation, recruitmentStatus, daysLeft } from "../site/js/eligibility.js";

const jobs = JSON.parse(readFileSync(new URL("../data/govt_jobs.json", import.meta.url))).jobs;
const byId = Object.fromEntries(jobs.map((j) => [j.id, j]));
const chsl = byId["ssc-chsl-2026"], cpo = byId["ssc-capf-si-2026"], icg = byId["icg-cgept-01-02-2027"];

const grad = { qualifications: [{ level: "engineering", discipline: "computer science", year: 2024, status: "completed" },
                                { level: "12th", year: 2020, subjects: ["Mathematics", "Physics"] }],
               dob: "2002-05-10", category: "General" };

test("graduate within age is a strong education+age match for CHSL", () => {
  const r = evaluate(chsl, grad);
  assert.equal(r.checks[0].status, "match");
  assert.equal(r.checks[1].status, "match");
  assert.equal(r.verdict, "strong");
});

test("missing DOB gives 'more information required'", () => {
  const r = evaluate(chsl, { qualifications: grad.qualifications });
  assert.equal(r.verdict, "info");
  assert.equal(r.checks[1].status, "verify");
});

test("over-age general candidate fails, OBC relaxation passes", () => {
  const old = { ...grad, dob: "1998-01-01" }; // CHSL earliest 1999-08-02, OBC +3 -> 1996-08-02
  assert.equal(checkAge(chsl, old).status, "no");
  assert.equal(checkAge(chsl, { ...old, category: "OBC" }).status, "match");
  assert.equal(checkAge(chsl, { ...old, category: undefined }).status, "verify");
});

test("too young fails", () => {
  assert.equal(checkAge(chsl, { ...grad, dob: "2009-01-01" }).status, "no");
});

test("12th-only candidate does not meet graduate requirement", () => {
  const r = checkEducation(cpo, { qualifications: [{ level: "12th", year: 2021 }] });
  assert.equal(r.status, "no");
});

test("physical standards are always flagged for verification", () => {
  const r = evaluate(cpo, { ...grad, dob: "2003-01-01" });
  assert.ok(r.checks.some((c) => c.key === "physical" && c.status === "verify"));
  assert.notEqual(r.verdict, "no");
});

test("coast guard: 12th with maths+physics matches Navik GD option", () => {
  const r = checkEducation(icg, { qualifications: [{ level: "12th", year: 2025, subjects: ["Mathematics", "Physics"] }] });
  assert.equal(r.status, "match");
});

test("diploma requirement with B.Tech in same field needs verification", () => {
  const job = { qualification: { options: [{ level: "diploma", disciplines: ["mechanical"] }] } };
  const r = checkEducation(job, { qualifications: [{ level: "engineering", discipline: "mechanical engineering", year: 2023 }] });
  assert.equal(r.status, "verify");
});

test("wrong discipline does not match", () => {
  const job = { qualification: { options: [{ level: "diploma", disciplines: ["mechanical"] }] } };
  const r = checkEducation(job, { qualifications: [{ level: "diploma", discipline: "civil", year: 2023 }] });
  assert.equal(r.status, "no");
});

test("passing year after cut-off fails; pursuing needs verification", () => {
  const job = { qualification: { options: [{ level: "graduate" }], cutoff_date: "2026-08-01" } };
  assert.equal(checkEducation(job, { qualifications: [{ level: "graduate", year: 2027 }] }).status, "no");
  assert.equal(checkEducation(job, { qualifications: [{ level: "graduate", status: "pursuing" }] }).status, "verify");
});

test("recruitment status and days left", () => {
  const job = { dates: { application_start: "2026-10-06", application_end: "2026-10-21" } };
  assert.equal(recruitmentStatus(job, new Date("2026-10-11")), "open");
  assert.equal(recruitmentStatus(job, new Date("2026-10-22")), "closed");
  assert.equal(recruitmentStatus(job, new Date("2026-10-01")), "upcoming");
  assert.equal(daysLeft(job, new Date("2026-10-11")), 10);
  assert.equal(recruitmentStatus({ dates: {} }), "unknown");
});
