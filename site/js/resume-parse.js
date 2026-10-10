// Extracts education, skills, certifications and experience from resume text.
// Runs entirely in the browser. Contact details and date of birth are never
// extracted; the user enters date of birth themselves if they want age checks.

export const SKILLS = {
  "Python": /\bpython\b/i, "Java": /\bjava\b(?!script)/i, "C++": /c\+\+/i, "C": /\bc\b(?=\s*(,|\/|\bprogramming|\blanguage))/i,
  "JavaScript": /\bjavascript\b/i, "TypeScript": /\btypescript\b/i, "React": /\breact(\.js|js)?\b/i, "Node.js": /\bnode(\.js|js)\b/i,
  "SQL": /\bsql\b|\bmysql\b|\bpostgres(ql)?\b/i, "MongoDB": /\bmongodb\b/i, "HTML/CSS": /\bhtml5?\b|\bcss3?\b/i,
  "Flask": /\bflask\b/i, "Django": /\bdjango\b/i, "Spring": /\bspring( boot)?\b/i,
  "Machine learning": /\bmachine learning\b/i, "Deep learning": /\bdeep learning\b/i, "PyTorch": /\bpytorch\b/i,
  "TensorFlow": /\btensorflow\b/i, "scikit-learn": /\bscikit[- ]learn\b|\bsklearn\b/i, "Computer vision": /\bcomputer vision\b|\bopencv\b/i,
  "NLP": /\bnlp\b|natural language processing/i, "LLMs": /\bllms?\b|large language model/i, "Pandas": /\bpandas\b/i, "NumPy": /\bnumpy\b/i,
  "Data analysis": /\bdata analy(sis|tics)\b/i, "Power BI / Tableau": /\bpower ?bi\b|\btableau\b/i, "Excel": /\b(ms )?excel\b/i,
  "AWS": /\baws\b|amazon web services/i, "Azure": /\bazure\b/i, "GCP": /\bgcp\b|google cloud/i, "Docker": /\bdocker\b/i,
  "Kubernetes": /\bkubernetes\b|\bk8s\b/i, "Linux": /\blinux\b|\bunix\b/i, "Git": /\bgit(hub)?\b/i,
  "Networking": /\bnetworking\b|\btcp\/ip\b|\bccna\b/i, "Cybersecurity": /\bcyber ?security\b|\binformation security\b|\bethical hacking\b/i,
  "Embedded systems": /\bembedded\b|\bmicrocontroller\b|\barduino\b|\besp32\b/i, "MATLAB": /\bmatlab\b/i, "AutoCAD": /\bautocad\b/i,
  "Typing (English / Hindi)": /\btyping\b/i, "Stenography": /\bstenograph/i, "Tally": /\btally\b/i,
};

export const DISCIPLINES = [
  "computer science", "information technology", "electronics and communication", "electronics", "electrical and electronics",
  "electrical", "mechanical", "civil", "chemical", "instrumentation", "telecommunication", "biotechnology", "aerospace",
  "data science", "artificial intelligence", "cyber security", "information security", "mathematics", "physics", "chemistry",
  "statistics", "commerce", "economics", "english", "hindi", "history", "political science", "biology", "pharmacy",
  "agriculture", "law", "management", "science", "arts",
];

const QUAL_PATTERNS = [
  ["phd", /\b(ph\.?\s?d|doctor of philosophy)\b/i],
  ["postgraduate", /\b(m\.?\s?tech|m\.e\.|mca|m\.?\s?sc|mba|m\.?\s?com|m\.a\.|master(?:'s)? (of|in)|post[- ]?graduat)/i],
  ["engineering", /\b(b\.?\s?tech|b\.e\.|bachelor of (engineering|technology))\b/i],
  ["graduate", /\b(b\.?\s?sc|bca|b\.?\s?com|b\.a\.|bba|b\.?\s?pharm|bachelor(?:'s)? (of|in)|graduat(e|ion))\b/i],
  ["diploma", /\bdiploma\b|\bpolytechnic\b/i],
  ["iti", /\b(i\.t\.i\.?|iti)\b/i],
  ["12th", /\b(12th|xii|hsc|h\.s\.c|higher secondary|intermediate|senior secondary|class 12|\+2)\b/i],
  ["10th", /\b(10th|ssc|s\.s\.c|matriculation|secondary school|class 10|high school)\b/i],
];

const SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology", "Computer Science", "English", "Hindi", "Commerce"];

function windowText(lines, i) {
  return [lines[i], lines[i + 1] || "", lines[i + 2] || ""].join(" ");
}

export function extractQualifications(text) {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const found = [];
  const seen = new Set();
  const thisYear = new Date().getUTCFullYear();
  lines.forEach((line, i) => {
    for (const [level, rx] of QUAL_PATTERNS) {
      if (!rx.test(line)) continue;
      if (level === "10th" && /\bssc\b/i.test(line) && /staff selection/i.test(line)) continue;
      const win = windowText(lines, i);
      const lw = win.toLowerCase();
      const discipline = DISCIPLINES.find((d) => lw.includes(d)) || null;
      const years = (win.match(/\b(19[89]\d|20[0-4]\d)\b/g) || []).map(Number);
      const year = years.length ? Math.max(...years) : null;
      const pct = win.match(/(\d{2}(?:\.\d{1,2})?)\s?%/);
      const cgpa = win.match(/\b(\d(?:\.\d{1,2})?)\s?(?:\/\s?10)?\s*(?:cgpa|gpa|cpi|sgpa)\b|\b(?:cgpa|gpa|cpi)\s*[:\-]?\s*(\d(?:\.\d{1,2})?)/i);
      const pursuing = /pursuing|expected|ongoing|present|currently/i.test(win) || (year && year > thisYear);
      const subjects = level === "12th" || level === "graduate" ? SUBJECTS.filter((s) => lw.includes(s.toLowerCase())) : [];
      const key = `${level}|${discipline}|${year}`;
      if (seen.has(key)) break;
      seen.add(key);
      found.push({
        level, discipline, year,
        percentage: pct ? Number(pct[1]) : null,
        cgpa: cgpa ? Number(cgpa[1] || cgpa[2]) : null,
        status: pursuing ? "pursuing" : "completed",
        subjects,
        source_line: line.slice(0, 140),
      });
      break; // one qualification per line
    }
  });
  // keep the best entry per level
  const byLevel = new Map();
  for (const q of found) {
    const prev = byLevel.get(q.level);
    if (!prev || (q.year || 0) > (prev.year || 0)) byLevel.set(q.level, q);
  }
  return [...byLevel.values()];
}

export function extractSkills(text) {
  return Object.entries(SKILLS).filter(([, rx]) => rx.test(text)).map(([k]) => k);
}

export function extractCertifications(text) {
  const out = [];
  const lines = text.split(/\r?\n/).map((l) => l.trim());
  let inSection = false;
  for (const line of lines) {
    if (/^(certifications?|courses|licen[cs]es)\b/i.test(line)) { inSection = true; continue; }
    if (inSection && /^(education|experience|projects|skills|achievements|publications|internships?)\b/i.test(line)) inSection = false;
    if ((inSection && line.length > 4) || /\bcertif(ied|icate|ication)\b/i.test(line)) {
      const clean = line.replace(/^[\-•*·•\s]+/, "").slice(0, 120);
      if (clean && !out.includes(clean)) out.push(clean);
    }
  }
  return out.slice(0, 15);
}

export function extractExperienceYears(text) {
  const m = text.match(/(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:work\s+|professional\s+|industry\s+)?experience/i);
  return m ? Number(m[1]) : null;
}

export function parseResumeText(text) {
  const t = String(text || "");
  return {
    qualifications: extractQualifications(t),
    skills: extractSkills(t),
    certifications: extractCertifications(t),
    experience_years: extractExperienceYears(t),
  };
}
