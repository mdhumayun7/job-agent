// Computes alert items for each user with the same rules the site uses
// (site/js/notify-core.js). Input on stdin:
//   { "jobs": [...govt records...], "users": [{ "id", "profile", "prefs", "saved", "searches" }] }
// Output on stdout: { "<user id>": [ { key, kind, title, body, date, href } ] }
import { finalize } from "../../site/js/data.js";
import { buildNotifications } from "../../site/js/notify-core.js";

const chunks = [];
for await (const c of process.stdin) chunks.push(c);
const input = JSON.parse(Buffer.concat(chunks).toString("utf8"));
const { jobs } = finalize(input.jobs || [], null, "alerts");
const out = {};
for (const u of input.users || []) {
  out[u.id] = buildNotifications({ jobs, saved: u.saved || [], profile: u.profile || {}, prefs: u.prefs || {},
    searches: u.searches || [], announcements: false })
    .filter((n) => n.kind !== "update" || n.key.startsWith("changed:") || n.key.startsWith("closed:"));
}
process.stdout.write(JSON.stringify(out));
