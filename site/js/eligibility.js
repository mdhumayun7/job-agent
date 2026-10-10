// Profile-based eligibility estimate for government recruitments.
//
// This is an estimate from the user's own profile, never a decision. Every
// criterion returns one of:
//   "match"   the profile satisfies the stated requirement
//   "no"      the profile clearly does not satisfy it
//   "verify"  needs checking in the official notice or missing profile data
// and a plain-language reason. Nothing is assumed: missing date of birth,
// category, domicile or experience stays "verify".

export const LEVELS = { "10th": 1, "12th": 2, "iti": 2, "diploma": 3, "graduate": 4, "engineering": 4, "postgraduate": 5, "phd": 6 };
export const LEVEL_LABELS = {
  "10th": "10th / Matriculation", "12th": "12th / Higher Secondary", "iti": "ITI", "diploma": "Diploma",
  "graduate": "Bachelor's degree", "engineering": "B.E. / B.Tech", "postgraduate": "Master's degree", "phd": "PhD",
};
export const CATEGORIES = ["General", "EWS", "OBC", "SC", "ST"];

const rank = (lvl) => LEVELS[lvl] ?? 0;
const lc = (s) => String(s || "").toLowerCase();

function parseDate(s) {
  if (!s) return null;
  const d = new Date(`${String(s).slice(0, 10)}T00:00:00Z`);
  return isNaN(d) ? null : d;
}

function addYears(date, years) {
  const d = new Date(date.getTime());
  d.setUTCFullYear(d.getUTCFullYear() + years);
  return d;
}

function fmt(date) {
  return date.toISOString().slice(0, 10);
}

// ---- education -------------------------------------------------------------

function checkOption(option, quals, cutoff, minPct) {
  const need = option.level;
  const candidates = quals.filter((q) => rank(q.level) >= rank(need));
  if (!candidates.length) {
    const highest = quals.reduce((a, q) => (rank(q.level) > rank(a?.level) ? q : a), null);
    return { status: "no", reason: `Requires ${LEVEL_LABELS[need] || need}; your highest listed qualification is ${highest ? LEVEL_LABELS[highest.level] || highest.level : "not provided"}.` };
  }
  let best = null;
  for (const q of candidates) {
    const notes = [];
    let status = "match";
    const higher = rank(q.level) > rank(need);
    if (higher && (need === "diploma" || need === "iti")) {
      status = "verify";
      notes.push(`you hold a higher qualification (${LEVEL_LABELS[q.level]}); the notice decides whether it is accepted in place of a ${LEVEL_LABELS[need]}`);
    }
    if (option.disciplines?.length) {
      const disc = lc(q.discipline);
      if (!disc) { status = "verify"; notes.push("add your discipline / specialisation to check the subject requirement"); }
      else if (!option.disciplines.some((d) => disc.includes(lc(d)))) {
        if (higher && rank(need) <= 2) { /* school-level option: discipline irrelevant */ }
        else return { status: "no", reason: `Requires ${option.disciplines.join(" / ")}; your ${LEVEL_LABELS[q.level]} is in ${q.discipline}.`, qual: q };
      }
    }
    if (option.subjects?.length) {
      const have = (q.subjects || []).map(lc);
      const level12 = quals.find((x) => x.level === "12th");
      const subj = have.length ? have : (level12?.subjects || []).map(lc);
      if (!subj.length) { status = status === "no" ? "no" : "verify"; notes.push(`confirm you studied ${option.subjects.join(" and ")}`); }
      else if (!option.subjects.every((s) => subj.some((h) => h.includes(lc(s))))) {
        return { status: "no", reason: `Requires ${option.subjects.join(" and ")} as subjects.`, qual: q };
      }
    }
    if (q.status === "pursuing") {
      status = "verify";
      notes.push("you are still pursuing this qualification; it must be completed by the notice's cut-off date");
    } else if (cutoff && q.year) {
      const cut = parseDate(cutoff);
      if (cut && Number(q.year) > cut.getUTCFullYear()) {
        return { status: "no", reason: `Must be completed by ${cutoff}; your passing year is ${q.year}.`, qual: q };
      }
    }
    if (minPct != null) {
      if (q.percentage == null) { status = "verify"; notes.push(`notice requires at least ${minPct}% marks; add your percentage`); }
      else if (Number(q.percentage) < minPct) return { status: "no", reason: `Requires at least ${minPct}% marks; you entered ${q.percentage}%.`, qual: q };
    }
    const reason = status === "match"
      ? `${LEVEL_LABELS[q.level]}${q.discipline ? ` (${q.discipline})` : ""} meets the ${LEVEL_LABELS[need]} requirement.`
      : `${LEVEL_LABELS[q.level]}${q.discipline ? ` (${q.discipline})` : ""}: ${notes.join("; ")}.`;
    const res = { status, reason, qual: q };
    if (!best || (best.status !== "match" && status === "match")) best = res;
  }
  return best;
}

export function checkEducation(job, profile) {
  const q = job.qualification;
  if (!q || !q.options?.length) return { key: "education", label: "Education", status: "verify", reason: "The qualification is not recorded for this notice; read the official notice." };
  const quals = (profile?.qualifications || []).filter((x) => x && x.level);
  if (!quals.length) return { key: "education", label: "Education", status: "verify", reason: "Add your qualifications to your profile to check this.", missing: true };
  const results = q.options.map((opt) => ({ opt, r: checkOption(opt, quals, q.cutoff_date, q.min_percentage) }));
  const order = { match: 0, verify: 1, no: 2 };
  results.sort((a, b) => order[a.r.status] - order[b.r.status]);
  const top = results[0];
  const label = q.options.length > 1 && top.opt.label ? `Education (${top.opt.label})` : "Education";
  return { key: "education", label, status: top.r.status, reason: top.r.reason, clause: q.notes || null };
}

// ---- age -------------------------------------------------------------------

export function relaxationYears(age, profile) {
  const rel = age?.relaxation || {};
  const cat = profile?.category;
  const pwbd = !!profile?.pwbd;
  if (pwbd) {
    if ((cat === "SC" || cat === "ST") && rel["PwBD-SC/ST"] != null) return rel["PwBD-SC/ST"];
    if (cat === "OBC" && rel["PwBD-OBC"] != null) return rel["PwBD-OBC"];
    if (rel.PwBD != null) return rel.PwBD;
  }
  if (cat && rel[cat] != null) return rel[cat];
  return 0;
}

export function checkAge(job, profile) {
  const age = job.age;
  const base = { key: "age", label: "Age" };
  if (!age || (age.min == null && age.max == null && !age.born_not_before && !age.born_not_after)) {
    return { ...base, status: "verify", reason: "Age limits are not recorded for this notice; read the official notice." };
  }
  const dob = parseDate(profile?.dob);
  if (!dob) return { ...base, status: "verify", reason: "Add your date of birth to check the age limit.", missing: true };

  const asOn = parseDate(age.as_on);
  let earliest = parseDate(age.born_not_before);
  const latest = parseDate(age.born_not_after);
  if (!earliest && asOn && age.max != null) earliest = addYears(asOn, -(age.max + 1));
  const latestDob = latest || (asOn && age.min != null ? addYears(asOn, -age.min) : null);

  if (latestDob && dob > latestDob) {
    return { ...base, status: "no", reason: `You must be born on or before ${fmt(latestDob)} (minimum age).` };
  }
  if (earliest && dob < earliest) {
    const years = relaxationYears(age, profile);
    const relaxed = addYears(earliest, -years);
    if (years > 0 && dob >= relaxed) {
      return { ...base, status: "match", reason: `Within the upper age limit after the ${years}-year relaxation for ${profile.pwbd ? "PwBD" : ""}${profile.pwbd && profile.category ? " / " : ""}${profile.category || ""}. Keep your certificate ready.` };
    }
    if (!profile?.category) {
      return { ...base, status: "verify", reason: `Above the general upper age limit (born before ${fmt(earliest)}). Add your category to check age relaxation.`, missing: true };
    }
    return { ...base, status: "no", reason: `Above the upper age limit${years ? ` even with the ${years}-year relaxation` : ""}: candidates must be born on or after ${fmt(relaxed)}.` };
  }
  const note = age.note ? ` Note: ${age.note}` : "";
  return { ...base, status: "match", reason: `Your date of birth is within the stated range${asOn ? ` (age reckoned on ${age.as_on})` : ""}.${note}` };
}

// ---- other criteria ---------------------------------------------------------

export function checkOther(job, profile) {
  const out = [];
  if (job.experience_years) {
    const have = profile?.experience_years;
    out.push(have == null
      ? { key: "experience", label: "Experience", status: "verify", reason: `Requires ${job.experience_years} year(s) of experience; add yours to check.`, missing: true }
      : have >= job.experience_years
        ? { key: "experience", label: "Experience", status: "match", reason: `You entered ${have} year(s); ${job.experience_years} required.` }
        : { key: "experience", label: "Experience", status: "no", reason: `Requires ${job.experience_years} year(s); you entered ${have}.` });
  }
  if (job.state) {
    out.push(!profile?.state
      ? { key: "domicile", label: "State / domicile", status: "verify", reason: `State recruitment (${job.state}); add your state and check domicile rules in the notice.`, missing: true }
      : lc(profile.state) === lc(job.state)
        ? { key: "domicile", label: "State / domicile", status: "match", reason: `Your state matches (${job.state}). Domicile proof may be required.` }
        : { key: "domicile", label: "State / domicile", status: "verify", reason: `State recruitment for ${job.state}; candidates from other states may be restricted. Check the notice.` });
  }
  if (job.physical_standards) {
    out.push({ key: "physical", label: "Physical / medical standards", status: "verify", reason: "This recruitment has physical and medical standards that cannot be checked from a profile." });
  }
  out.push({ key: "nationality", label: "Nationality and other conditions", status: "verify", reason: "Nationality, documents and any post-specific conditions must be checked in the official notice." });
  return out;
}

export function evaluate(job, profile) {
  const checks = [checkEducation(job, profile), checkAge(job, profile), ...checkOther(job, profile)];
  const edu = checks[0];
  const ageC = checks[1];
  let verdict;
  if (checks.some((c) => c.status === "no")) verdict = "no";
  else if (edu.missing || ageC.missing) verdict = "info";
  else if (edu.status === "match" && ageC.status === "match" &&
           checks.filter((c) => c.status === "verify" && !["physical", "nationality"].includes(c.key)).length === 0) verdict = "strong";
  else verdict = "possible";
  const labels = { strong: "Strong match", possible: "Possible match", info: "More information required", no: "Does not match your profile" };
  return { verdict, label: labels[verdict], checks };
}

export function verdictRank(v) {
  return { strong: 0, possible: 1, info: 2, no: 3 }[v] ?? 4;
}

// ---- recruitment status -----------------------------------------------------

export function recruitmentStatus(job, today = new Date()) {
  const t = parseDate(new Date(today).toISOString());
  const start = parseDate(job.dates?.application_start);
  const end = parseDate(job.dates?.application_end);
  if (end && t > end) return "closed";
  if (start && t < start) return "upcoming";
  if (end || start) return "open";
  return "unknown";
}

export function daysLeft(job, today = new Date()) {
  const end = parseDate(job.dates?.application_end);
  if (!end) return null;
  const t = parseDate(new Date(today).toISOString());
  return Math.round((end - t) / 86400000);
}
