import test from "node:test";
import assert from "node:assert/strict";
import { parseResumeText } from "../site/js/resume-parse.js";

const sample = `MD Example
Email: someone@example.com | +91 98765 43210 | DOB: 01/01/2000
EDUCATION
M.Tech in Computer Science and Engineering, SVNIT Surat
2025 - 2027 (pursuing) CGPA 8.4/10
B.Tech, Computer Science, ABC Institute of Technology, 2021 - 2025, 78.5%
Class XII (CBSE), Physics, Chemistry, Mathematics, 2021, 88%
Class 10 (CBSE), 2019, 92%
SKILLS
Python, PyTorch, TensorFlow, SQL, Docker, Linux, Git
CERTIFICATIONS
NPTEL Deep Learning - Elite
AWS Certified Cloud Practitioner
EXPERIENCE
2 years of experience as teaching assistant`;

test("extracts qualifications with level, discipline, year and marks", () => {
  const r = parseResumeText(sample);
  const by = Object.fromEntries(r.qualifications.map((q) => [q.level, q]));
  assert.equal(by.postgraduate.status, "pursuing");
  assert.equal(by.postgraduate.discipline, "computer science");
  assert.equal(by.postgraduate.cgpa, 8.4);
  assert.equal(by.engineering.year, 2025);
  assert.equal(by.engineering.percentage, 78.5);
  assert.deepEqual(by["12th"].subjects.sort(), ["Chemistry", "Mathematics", "Physics"]);
  assert.equal(by["10th"].percentage, 92);
});

test("extracts skills, certifications and experience, not contact data", () => {
  const r = parseResumeText(sample);
  for (const s of ["Python", "PyTorch", "TensorFlow", "SQL", "Docker", "Linux", "Git"]) assert.ok(r.skills.includes(s), s);
  assert.ok(r.certifications.some((c) => c.includes("AWS Certified")));
  assert.equal(r.experience_years, 2);
  const json = JSON.stringify(r);
  assert.ok(!json.includes("@example.com") && !json.includes("98765") && !json.includes("01/01/2000"));
});
