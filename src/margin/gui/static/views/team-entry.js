// The sidebar's Team entry (docs/DESIGN.md 5.1): the link to the Team place (#/team), always there, and in a project
// with a team the team's state at its end in fixed words (lib.js teamEntry().set()). It follows the window events
// app.js fires after each look at the project's poller ("margin-sync-state", "margin-sync-news"); while the Team page
// is open, the page's own count of what is new (teamPanel({ onCount }), setTeamPageCount()) takes the poller's place.
import { App, teamEntry } from "../lib.js";
import { whenText } from "./team-state.js";

// What the Team entry says, from the poller's answer (GET …/sync-poller) and what is new: the first that holds of a
// round running, offline, the last round not working, paused, what is new, when the last round was; and before the
// first round since Margin started (the poller knows only its own rounds, so it cannot say when the copies were last in
// step), when the next one comes: "no round yet" would read as never, beside a Team page that says when.
export function teamWords(s, count = 0, now = new Date()) {
  const r = s && s.round;
  if (!s) return { kind: "ok", words: "no round yet" };
  if ((r && (r.state === "running" || r.state === "queued")) || s.state === "due") return { kind: "running", words: "syncing now…" };
  if (s.state === "offline" || s.offline) return { kind: "attention", words: "offline" };
  if (s.last_round && s.last_round.state === "error") return { kind: "attention", words: "round did not work" };
  if (s.paused || s.paused_all) return { kind: "ok", words: "paused" };
  if (count > 0) return { kind: "ok", count: `${count} new` };
  if (s.last_round) return { kind: "ok", words: syncedWords(s.last_round.finished_at, now) };
  if (typeof s.next_round_in === "number") return { kind: "ok", words: s.next_round_in < 60 ? "round in a moment" : `round in ${Math.ceil(s.next_round_in / 60)} min` };
  return { kind: "ok", words: "no round yet" };
}
// "synced 15:44" (today), "synced yesterday", "synced 12 Nov" (from whenText's "Today 15:44", "Yesterday …", "12 Nov …")
function syncedWords(t, now) {
  const w = whenText(t, now);
  if (!w) return "synced";
  if (w.startsWith("Today ")) return `synced ${w.slice(6)}`;
  if (w.startsWith("Yesterday ")) return "synced yesterday";
  return `synced ${w.slice(0, w.lastIndexOf(" "))}`;
}

let entry = null;        // the entry (lib.js teamEntry()), in place of index.html's plain one
let sync = null;         // the poller's last answer for this project, or null (no team, not read yet)
let pollCount = 0;       // what came in and was not seen, as the poller counts it
let pageCount = null;    // … as the open Team page counts it (with what waits for your word), or null
let countFor = null;     // the project the counts are of

function draw() {
  if (!entry) return;
  if (!sync || !sync.folder) { entry.set(); return; }
  entry.set(teamWords(sync, pageCount !== null ? pageCount : pollCount));
}

// The Team page's own count while it is open (null when it closes: the poller's count again)
export function setTeamPageCount(n) {
  pageCount = n === null || n === undefined ? null : Number(n) || 0;
  draw();
}

// The Team page read the project's state and found no team (left just now, or never had one): the entry says nothing
// more, without waiting for the poller's next look
export function teamFoundOnPage(project, has) {
  if (project !== App.project || has) return;
  sync = null; pollCount = 0;
  draw();
}

export function initTeamEntry() {
  if (entry) return;
  const plain = document.getElementById("team-entry");
  if (!plain) return;
  entry = teamEntry({ id: "team-entry" });
  const current = plain.getAttribute("aria-current");
  if (current) entry.setAttribute("aria-current", current);
  entry.dataset.marked = "1";   // app.js navIcons: its tooltip is its own (it says the state)
  plain.replaceWith(entry);
  countFor = App.project;
  // after each look (null when it could not look): the state of a project with a team; none without
  window.addEventListener("margin-sync-state", (e) => {
    const s = e.detail;
    if (!s || s.project !== App.project) return;
    sync = s;
    pollCount = s.folder ? (s.came_in || {}).count || 0 : 0;
    draw();
  });
  window.addEventListener("margin-sync-news", (e) => {
    const s = e.detail;
    if (!s || s.project !== App.project) return;
    pollCount = (s.came_in || {}).count || 0;
    draw();
  });
  // another project: nothing of the last one is said until its own state arrives
  App.onChange(() => {
    if (App.project === countFor) return;
    countFor = App.project;
    sync = null; pollCount = 0; pageCount = null;
    draw();
  });
  draw();
}
