// Entry point: boots the shell, routes the hash, keeps the sidebar (project, jobs, privacy, theme) current.
import { App, api, h, icon, setButtonKind, menu, plural, emptyState, Connection, replace, clear, toast, showError, store, navigate, parseQuery, onJobsChanged, fmt, TERMINAL, confirmDialog, P, watchJob, startClaudeNow, claudeStatus, claudeSeenNow, rememberClaude, rememberAgent, agentStatus, agentSeenNow, claudeAccount, brand, appName, Updates, checkUpdate, onUpdateSeen, UPDATE_EVERY, button, iconButton, link, notice , cancelJob, ensureToken, keyWasStale, copyLine, WhatsNew, loadWhatsNew, showWhatsNew, markWhatsNewRead, isAgent, agentRoute, agentTitle, agentPlan, agentCompany } from "./lib.js";
import { FEATURES, SECTIONS, PLACES, aiTag } from "./features.js";
import { PAGE_ROUTES, applyExtensions, jobRow } from "./registry.js";
import { quietRound, quietRoundAgainIn, nextSyncLook } from "./views/team-state.js";   // 0.18 stage 5
import localExtensions from "./extensions.js";
import { renderResult } from "./views/result.js";
import { renderSources, renderDocument } from "./views/sources.js";
import { renderSettings } from "./views/settings.js";
import { renderSetup } from "./views/setup.js";
import { renderProjects, newProjectDialog } from "./views/projects.js";
import { joinDialog } from "./views/team-space.js";   // the project menu's Join a team… (a new project from an invite link)
import { renderMap } from "./views/map.js";
import { renderSearch } from "./views/search.js";
import { renderProfile } from "./views/profile.js";
import { renderConcepts, renderConcept } from "./views/concepts.js";
import { renderConceptMap } from "./views/concept-map.js";   // D1
import { renderThemes, renderThemeRun, renderTheme } from "./views/themes.js";
import { quickLookBanner } from "./views/quicklook.js";
import { renderOverview } from "./views/overview.js";
import { renderBibliography } from "./views/bibliography.js";
import { renderLog } from "./views/log.js";
import { renderNotes } from "./views/notes.js";
import { renderCodebooks, renderCodebook } from "./views/codebooks.js";
import { renderTheoryDraft } from "./views/theory-draft.js";
import { renderHypotheses } from "./views/hypotheses.js";
import { openFinder } from "./finder.js";
import { renderDesign } from "./views/design.js";   // 0.17.0: the design guide's live reference, unlisted
import { initLogDrawer } from "./views/logdrawer.js";
import { initTeamLine } from "./views/team-line.js";   // the team line under the project's name and the team's state at its end

// [pattern, the sidebar place it lights (features.js PLACES, or an add-on's feature key), render]. Nine places (the
// Research log is a place of the Project group; the Team is the team line under the project's name); the old addresses stay and open their new home
// (#/check, #/batch and #/history: Hypotheses; #/profile: Codes).
const ROUTES = [
  [/^\/?$/, "overview", renderOverview],
  [/^\/overview$/, "overview", renderOverview],
  [/^\/log$/, "researchlog", renderLog],                  // the Research log (the drawer hides on it)
  [/^\/sources$/, "documents", renderSources],
  [/^\/doc\/([^/]+)$/, "documents", renderDocument],
  [/^\/notes$/, "documents", renderNotes],                 // Documents › Notes
  [/^\/bibliography$/, "documents", renderBibliography],   // Documents › Bibliography
  [/^\/search$/, "search", renderSearch],
  [/^\/profile$/, "codes", renderProfile],                 // Codes › By document
  [/^\/codebooks\/draft\/theory$/, "codes", renderTheoryDraft],   // K2: a codebook from theory, drafted (before a codebook's name)
  [/^\/codebooks$/, "codes", renderCodebooks],             // Codes › Codebooks
  [/^\/codebooks\/([^/]+)$/, "codes", renderCodebook],
  [/^\/concepts$/, "concepts", renderConcepts],
  [/^\/concept-map$/, "concepts", renderConceptMap],     // Concepts › Map (D1)
  [/^\/concepts\/([^/]+)$/, "concepts", renderConcept],
  [/^\/themes$/, "themes", renderThemes],
  [/^\/themes\/([^/]+)$/, "themes", renderThemeRun],
  [/^\/themes\/([^/]+)\/([^/]+)$/, "themes", renderTheme],
  [/^\/hypotheses$/, "hypotheses", renderHypotheses],     // checking one or several, and the answers
  [/^\/check$/, "hypotheses", renderHypotheses],
  [/^\/batch$/, "hypotheses", renderHypotheses],
  [/^\/history$/, "hypotheses", renderHypotheses],
  [/^\/map$/, "hypotheses", renderMap],                    // Hypotheses › Evidence map
  [/^\/h\/([^/]+)$/, "hypotheses", renderResult],
  [/^\/settings(?:\/([^/]+))?$/, "settings", renderSettings],
  [/^\/setup$/, "", renderSetup],
  [/^\/projects$/, "", renderProjects],
  // the Team place (views/team.js, loaded when first opened): Activity, and People and settings (#/team/settings);
  // without a team, the set-up
  [/^\/team(?:\/(settings))?$/, "team", (view, params, query) => import("./views/team.js").then((m) => m.renderTeam(view, params, query))],
  [/^\/design$/, "", renderDesign],                       // not in the sidebar or Find: docs/DESIGN.md points to it
];

// The window's title: the view's own name when the address is one of a place's views, else the place's name.
function pageTitle(nav, pathPart) {
  if (nav === "settings") return "Settings";
  if (nav === "team" && pathPart === "/team") return "Team";   // Activity, or the set-up in a project without a team
  const place = PLACES[nav];
  if (place) {
    const v = place.views.find(([, , href]) => href === `#${pathPart}`);
    return v && v[1] !== place.title ? `${v[1]} · ${place.title}` : place.title;
  }
  return { "/setup": "Set up", "/projects": "Projects", "/design": "Design reference" }[pathPart] || (FEATURES[nav] && FEATURES[nav].title) || "";
}

let cleanup = null;
let lastHash = null;
let renderSeq = 0;

async function route() {
  const hash = location.hash.replace(/^#/, "") || "/overview";
  const [pathPart, qs] = hash.split("?");
  const query = parseQuery(qs);
  const view = document.getElementById("view");
  if (!App.state) {
    try { await App.refresh(); } catch (e) { replace(view, notice({ kind: "error" }, h("p", {}, e.message))); return; }
  }
  // First run: no project yet -> the setup pages.
  const noProject = !App.state.projects.length;
  if (noProject && !/^\/(setup|settings|projects)/.test(pathPart)) { navigate("#/setup"); return; }
  if (!noProject && !App.project && !/^\/(setup|settings|projects)/.test(pathPart)) {
    // projects exist but none is current: pick the first
    try { await api("PUT", "/api/settings", { project: App.state.projects[0].name }); await App.refresh(); } catch (e) { showError(e); }
  }
  let match = null, nav = "", render = null;
  for (const [rx, n, r] of [...ROUTES, ...PAGE_ROUTES]) {  // 0.13.6: an add-on's pages come after the core ones
    const m = rx.exec(pathPart);
    if (m) { match = m; nav = n; render = r; break; }
  }
  if (cleanup) { try { cleanup(); } catch (e) { console.error(e); } cleanup = null; }
  setNav(nav);
  closeDrawer();
  for (const d of document.querySelectorAll("#project-switch details[open]")) d.open = false;
  const pageName = pageTitle(nav, pathPart);
  document.title = pageName ? `${pageName} · ${appName()}` : appName();
  quickLookBanner(document.getElementById("quicklook-banner"));
  // Each page renders into its own container: a render still in flight when the hash changes again writes into a
  // detached element and cannot disturb the new page.
  const seq = ++renderSeq;
  const page = h("div", { class: "page" });
  replace(view, page);
  view.setAttribute("aria-busy", "true");
  if (!render) {
    replace(page, emptyState("search-x", "No such page", "The address does not match a page of the app.", link({ kind: "back", href: "#/overview" }, "Go to the overview")));
    view.setAttribute("aria-busy", "false");
    return;
  }
  const params = match.slice(1).map((x) => (x === undefined ? undefined : decodeURIComponent(x)));
  try {
    const r = await render(page, params, query);
    if (seq !== renderSeq) { if (typeof r === "function") r(); return; }
    if (typeof r === "function") cleanup = r;
  } catch (e) {
    if (seq !== renderSeq) return;
    console.error(e);
    replace(page, notice({ kind: "error" }, h("div", {}, h("p", {}, e.message || String(e)),
      e.kind === "backend" ? h("a", { href: "#/settings" }, "Open Settings") : null)));
  }
  view.setAttribute("aria-busy", "false");
  // Focus the page title on navigation (not on the first load).
  if (lastHash !== null && lastHash !== hash) {
    const t = document.getElementById("page-title");
    if (t) t.focus({ preventScroll: false });
    window.scrollTo(0, 0);
  }
  lastHash = hash;
}

function setNav(name) {
  // 0.10.1: Settings sits at the foot of the sidebar, with Theme and Quit, outside the list of features
  for (const a of document.querySelectorAll("#nav a, #nav-foot a, #team-line")) {
    if (a.dataset.route === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
}

// ---------------------------------------------------------------------------------------------
// sidebar
// ---------------------------------------------------------------------------------------------
function renderProjectSwitch() {
  const box = document.getElementById("project-switch");
  const projects = App.state.projects || [];
  const current = projects.find((p) => p.name === App.project);
  const top = document.getElementById("topbar-project");
  top.textContent = current ? current.name : ""; top.title = current ? current.name : "";
  // the menu component (docs/DESIGN.md 4.17) with the switch's own summary: a field-like box with the project's name
  const items = projects.map((p) => ({ text: p.name, icon: p.linked ? "link" : "folder", current: p.name === App.project,
    meta: `${plural(p.documents, "document")} · ${plural(p.hypotheses, "answer")}`, title: p.ok ? null : "This project could not be opened.",
    onClick: () => switchProject(p.name) }));
  const details = menu({ label: "Project: " + (current ? current.name : "none"), title: current ? current.name : "", listClass: "ps-menu",
    trigger: [icon("folder", { size: 16 }),
      h("span", { class: "ps-name" }, h("span", { class: "ps-label" }, "Project"), h("span", { class: "ps-name-text" }, current ? current.name : "No project")),
      icon("chevron-down", { size: 14 })],
    // Join a team… makes a new project from a colleague's invite link (the current project's team is the team line
    // under the switch)
    items: [...items, items.length ? "sep" : null, { text: "New project…", icon: "plus", onClick: () => newProjectDialog() },
      { text: "Join a team…", icon: "link", onClick: () => joinDialog(null) },
      { text: "Manage projects", icon: "sliders", href: "#/projects" }].filter(Boolean) });
  // the team line (views/team-line.js) is the switch's second row: kept across redraws, hidden while there is no project
  const line = document.getElementById("team-line");
  if (line) line.hidden = !current;
  replace(box, details, line);
}

export async function switchProject(name) {
  if (name === App.project) return;
  try {
    await api("PUT", "/api/settings", { project: name });
    await App.refresh();
    toast(`Project: ${name}`, "ok", { ttl: 2000 });
    if (/^#\/(h|doc|themes|concepts|codebooks)\//.test(location.hash)) navigate("#/overview"); else route();
  } catch (e) { showError(e); }
}


// 0.13.4: hovering the line (or reaching it with the keyboard) opens a small card with what the tooltip said and, on
// Claude Code, the account it is signed in to. Escape closes it; it stays open while the pointer is on it. Stage 2: so
// on Codex and Antigravity.
function renderPrivacy() {
  const box = document.getElementById("privacy-indicator");
  const p = App.privacy();
  const plan = isAgent();
  const route = agentRoute();
  const card = h("div", { class: "privacy-card", id: "privacy-card", role: "tooltip" });
  // 0.17.0 (design guide): an AI chosen in Settings that cannot run yet (an Ollama without a model, the Claude API
  // without a key), and Demo mode, take the attention look: the triangle, amber
  const unset = p.where !== "none" && !App.modelConfigured();
  const a = h("a", { class: `privacy privacy-${p.where}${unset || p.where === "none" ? " privacy-setup" : ""}`, href: unset ? "#/settings/model" : "#/settings", "aria-describedby": "privacy-card" },
    icon(unset || p.where === "none" ? "alert-triangle" : p.icon, { size: 16 }),
    h("div", {}, h("strong", {}, unset ? "No AI model set up yet" : p.label), h("span", { class: "privacy-sub" }, unset ? "Exploring works; checking needs one" : p.short || p.plain)));
  const wrap = h("div", { class: "privacy-wrap" }, a, card);
  const fill = () => replace(card,
    plan ? accountPart(agentSeenNow(route), route) : null,
    h("p", {}, p.plain),
    plan ? null : h("p", { class: "privacy-card-muted" }, `AI model: ${p.detail}`),
    h("p", { class: "privacy-card-muted" }, "Change it in Settings."));
  fill();
  if (plan) {
    // 0.17.0: not ready yet (the Overview's AI box said so, with a button): the line itself says what to do
    const sub = a.querySelector(".privacy-sub");
    const ask = () => agentStatus(route).then((st) => {
      if (st && st.ready === false && !st.unknown) {
        // set-up not finished: the attention look, the triangle in place of the cloud (docs/DESIGN.md 5.2)
        sub.textContent = st.found ? "Finish the set-up" : `Set up ${agentTitle()}`; a.href = "#/settings/model"; a.classList.add("privacy-setup");
        a.firstElementChild.replaceWith(icon("alert-triangle", { size: 16 }));
      }
      if (card.isConnected) fill();
    }).catch(() => {
      if (!agentSeenNow(route)) {
        if (route === "claude_code") rememberClaude({ unknown: true });
        else rememberAgent(route, { unknown: true }, false);
        fill();
      }
    });
    ask();  // the card is ready before the first hover; a hover a minute later asks again
    wrap.addEventListener("mouseenter", ask);
    a.addEventListener("focus", ask);
  }
  const quiet = (on) => wrap.classList.toggle("privacy-quiet", on);
  a.addEventListener("keydown", (e) => { if (e.key === "Escape") quiet(true); });
  wrap.addEventListener("mouseleave", () => quiet(false));
  a.addEventListener("blur", () => quiet(false));
  replace(box, wrap);
}

// Which account Claude Code uses, for the card: what it says, or what is still to set up. Stage 2: Codex and
// Antigravity say it in their own words (status.account), or nothing.
function accountPart(st, route = "claude_code") {
  if (route !== "claude_code") {
    const t = agentTitle();
    if (st && st.signed_in && st.account) {
      return h("div", { class: "privacy-account" }, h("span", { class: "privacy-card-muted" }, `Signed in to ${t}`), h("strong", {}, st.account));
    }
    const say = !st ? `Asking ${t} which account it uses…`
      : st.unknown ? `Could not ask ${t} which account it uses.`
      : !st.found ? `${t} is not on this computer yet: Settings → AI sets it up.`
      : st.signed_in === false ? `${t} is not signed in yet: Settings → AI signs you in.`
      : st.signed_in ? `${t} is signed in; it does not say which account.` : `${t} does not say whether it is signed in.`;
    return h("div", { class: "privacy-account" }, h("span", {}, say));
  }
  const acc = claudeAccount(st);
  if (acc) {
    return h("div", { class: "privacy-account" },
      h("span", { class: "privacy-card-muted" }, "Signed in to Claude Code as"),
      h("strong", {}, acc.email || "an account it does not name"),
      acc.plan ? h("span", { class: "privacy-card-muted" }, acc.plan + (acc.org ? ` · ${acc.org}` : "")) : null);
  }
  const say = !st ? "Asking Claude Code which account it uses…"
    : st.unknown ? "Could not ask Claude Code which account it uses."
    : !st.found ? "Claude Code is not on this computer yet: Settings → AI sets it up."
    : st.signed_in === false ? "Claude Code is not signed in yet: Settings → AI signs you in."
    : "Claude Code does not say which account it is signed in to.";
  return h("div", { class: "privacy-account" }, h("span", {}, say));
}

// A wheel or touchpad turn over the sidebar never scrolls the page behind it: it scrolls the part of the sidebar under
// the pointer that can still move that way (the list of features, an open panel, the project menu), or nothing.
// (A box with nothing left to scroll hands the turn on to the page, and CSS alone cannot stop that everywhere.)
function sidebarScrollInit() {
  const sb = document.getElementById("sidebar");
  if (!sb) return;
  const canMove = (el, dy) => {
    if (el.scrollHeight <= el.clientHeight + 1) return false;
    const oy = getComputedStyle(el).overflowY;
    if (oy !== "auto" && oy !== "scroll") return false;
    return dy < 0 ? el.scrollTop > 0 : el.scrollTop + el.clientHeight < el.scrollHeight - 1;
  };
  sb.addEventListener("wheel", (e) => {
    if (e.ctrlKey || !e.deltaY) return;  // a pinch zooms the page; a sideways turn is left alone
    for (let el = e.target; el && el !== sb.parentElement; el = el.parentElement) {
      if (el.nodeType === 1 && canMove(el, e.deltaY)) return;
    }
    e.preventDefault();
  }, { passive: false });
}

// ---------------------------------------------------------------------------------------------
// 0.17.0: the status area at the foot of the sidebar. One area of a fixed size: normally where text goes (the AI
// line); while work runs or waits, the work takes its place and says only what matters: what runs and for how long,
// what waits, and the one thing to do (Start Claude Code when nothing answers). It never opens a panel: the work's own
// page has the details, and Settings › AI › "Work waiting for Claude Code" orders, holds or removes what waits.
// (It replaces the jobs and queue panels of 0.8–0.15.)
// ---------------------------------------------------------------------------------------------
let statusTimer = null;
let statusBusy = false, statusAgain = false;
let statusFailures = 0;   // looks at /api/jobs that failed in a row (the computer slept, the app was busy): each waits longer
const HIDDEN_LOOK = 15000;   // a tab nobody sees looks this seldom; it looks at once when it comes back (visibilitychange, focus)
let statusKey = "";  // what the box drawn last shows, all but the seconds (a redraw under the pointer kept its tooltip)
async function renderStatus() {
  if (statusBusy) { statusAgain = true; return; }
  statusBusy = true;
  try { await drawStatus(); } finally { statusBusy = false; }
  if (statusAgain) { statusAgain = false; renderStatus(); }
}
// where a job's work goes, as the server says (job.where, WHERE_OF_KIND in api_common.py): a chip under the work box's
// words; a job that uses the AI of Settings (no `where`) gets that AI's name and icon
const WHERE_CHIP = {
  here: { icon: "house", label: "This computer", get tip() { return `This runs on this computer; nothing is sent to ${agentCompany()}.`; } },
  crossref: { icon: "network", label: "Crossref", tip: "Only DOIs are sent to Crossref, and for a work without one its title, first author’s family name and year; no text of your documents leaves this computer." },
};
// 0.19.13: the AI run panel's row (docs/DESIGN.md 4.21, 5.2): this computer's house at the box's left end, Claude's
// cloud at its right end, and the split bar along its top (each engine's half), so it reads at a glance and in greyscale
// stage 2: to the company of the agent that answers (Anthropic, OpenAI, Google); "Claude" or the agent's name
const cloudTip = () => `Your documents stay here; only the passages inside the AI's tasks go to ${agentCompany()}.`;
const cloudWho = () => (agentRoute() === "claude_code" ? "Claude" : agentTitle());
const tasksWord = (n) => `${n.toLocaleString()} ${n === 1 ? "task" : "tasks"}`;
async function drawStatus() {
  const box = document.getElementById("work-indicator");
  const privacy = document.getElementById("privacy-indicator");
  if (!box || !privacy) return;
  clearTimeout(statusTimer);
  let jobs = [];
  try { jobs = (await api("GET", "/api/jobs")).jobs || []; statusFailures = 0; }
  catch (_) {   // look again later, a little longer each time, so one failed request does not end the sidebar’s status
    statusTimer = setTimeout(renderStatus, Math.min(60000, 5000 * 2 ** Math.min(statusFailures++, 4)));
    return;
  }
  const s = App.settings();
  const summary = (App.state && App.state.queue) || {};
  let q = null;
  if (App.project && (isAgent(s) || summary.waiting)) {
    try { q = await api("GET", `/api/projects/${P(App.project)}/queue`); } catch (_) { q = null; }
  }
  const active = jobs.filter((j) => !TERMINAL.has(j.state) && !quietRound(j));   // 0.18 (L3): the poller's own rounds stay quiet, unless one takes long
  const going = active.filter((j) => !j.on_hold);
  const hold = active.filter((j) => j.on_hold);
  const runner = !!(q && q.runner && q.runner.running);
  const waiting = q ? (q.waiting || 0) : 0;
  const answering = q ? (q.being_answered || 0) : 0;
  // what to show: [kind, main words, the line under them, link, the one action]
  let w = null;
  // 0.19.13: a job whose part for the local model waits for its Start (job.local.gate "wait")
  const localWait = active.find((j) => j.local && j.local.gate === "wait" && (j.local.waiting || 0) > 0 && !j.local.problem);
  // stage 2: only tasks really in the queue count, and only when something can start them: a job on hold whose work
  // its agent may not read (its company not allowed for the project) is no task waiting, and Start would start nothing
  const cloudStalled = !runner && !!(q && waiting && !answering && (isAgent(s) || hold.length));
  const t = agentTitle(s);
  if (localWait && cloudStalled) {   // both wait: two starts do not fit the row; it opens the job's page, where both are
    const v = jobRow(localWait), n = waiting;
    w = { kind: "stalled", icon: "pause", main: "Not running", sub: `${fmt.num(localWait.local.waiting)} here · ${fmt.num(n)} for ${cloudWho()}`, href: v.href || "#/settings/queue",
      tip: `Two parts wait for you: one for the model on this computer, one for ${t}. Open the work to start them.`, act: "open-job", local: "need", cloudHalf: "need", job: localWait.id };
  } else if (localWait && !cloudStalled && !going.some((j) => j !== localWait && !j.local)) {
    const v = jobRow(localWait), L = localWait.local;
    // the job's work for Claude (being answered, or done): its tile and half, not the empty seat
    const cloudToo = !!localWait.queue || localWait.where === "cloud";
    w = { kind: "stalled", icon: "pause", main: "Not running", sub: `${plural(L.waiting, L.noun || "passage")} ${L.waiting === 1 ? "waits" : "wait"}${cloudToo ? " here" : ""}`, href: v.href,
      tip: `Nothing reads this yet: it waits for you to start ${L.model || "your local model"}.`, act: L.memory && L.memory.short ? "open-job" : "start-local", local: "need", job: localWait.id,
      cloudHalf: cloudToo ? (runner || answering ? "run" : "done") : undefined };
  } else if (cloudStalled) {
    const n = waiting;
    w = { kind: "stalled", icon: "pause", main: q && q.paused ? "Paused" : "Not running", sub: `${tasksWord(n)} waiting`,
      href: "#/settings/queue", tip: `Nothing answers this work yet: ${tasksWord(n)} ${n === 1 ? "waits" : "wait"} for ${t}. Start it and the work runs.`,
      act: q && q.can_start && !q.paused ? "start" : "open", cloudHalf: "need" };
  } else if (going.length) {
    const j = going[0], v = jobRow(j);
    const more = going.length - 1;
    w = { kind: "running", where: j.where || null, localModel: j.local_model || "", main: v.text, time: j.state === "running" ? fmt.secs(j.seconds) : "", href: v.href, tip: v.tooltip,
      sub: j.waiting_for ? j.waiting_for.message : j.state === "queued" ? "waiting its turn" : more ? `and ${more} more running` : waiting + answering ? `${(waiting + answering).toLocaleString()} for ${t}` : "running",
      act: j.waiting_for ? "cancel" : undefined, job: j.id };   // 0.18 queued jobs: what it waits for, with Cancel
    const mainLocal = ["ollama", "openai", "auto"].includes(s.backend);
    const localRuns = !!(j.local_model !== undefined && j.local_model !== null) || (mainLocal && j.where == null);
    if (localRuns) w.local = "run";
    else if (j.local && (j.local.waiting || 0) > 0) w.local = j.local.gate === "wait" ? "need" : "run";
    if (j.queue || j.where === "cloud" || (j.where == null && App.privacy().where === "cloud")) w.cloudHalf = runner || answering ? "run" : waiting ? "need" : "wait";
    if (w.cloudHalf === "need" && w.local === "run") w.sub = `Reads here · ${fmt.num(waiting)} for ${cloudWho()}`;
  } else if (runner) {
    w = { kind: "running", where: "cloud", main: `${t} is working`, sub: `${(waiting + answering).toLocaleString()} to go`, href: "#/settings/queue", tip: `${t} answers the work waiting for it, ${agentPlan(s)}.`, cloudHalf: "run" };
  } else if (q && waiting) {
    w = { kind: "stalled", icon: "inbox", main: `${tasksWord(waiting)} waiting`, sub: `for ${t}`, href: "#/settings/queue", tip: `Work prepared for ${t}: answer it there, or with the AI model of Settings.`, act: "open", cloudHalf: "need" };
  }
  privacy.hidden = !!w;
  box.hidden = !w;
  document.getElementById("status-area").classList.toggle("status-busy", !!w);
  if (!w) { replace(box); statusKey = ""; }
  else {
    // where text goes stays in view while work runs (it took the AI line's place): the AI's name, with its icon
    const p = App.privacy();
    const cloud = w.kind === "running" && (w.where === "cloud" || (w.where == null && p.where === "cloud"));
    const cloudTipNow = w.where === "cloud" ? cloudTip() : p.plain;
    const key = JSON.stringify([App.project, w.kind, w.where, w.localModel, cloud, w.main, w.sub, w.href, w.act, w.act === "cancel" || w.act === "start-local" ? w.job : "", w.local, w.cloudHalf]);
    if (key === statusKey && box.firstChild) {
      const t = box.querySelector(".work-time"); if (t && w.time) t.textContent = w.time;   // only the seconds changed
    } else {
      statusKey = key;
      // 0.17: work that runs on this computer says so, not "Claude"; 0.19: the server says where each job runs
      const chip = WHERE_CHIP[w.where];
      // 0.19.13: the AI's work has its seats (the house at the left end, the cloud at the right end) in place of the chip
      const ai = !!(w.local || w.cloudHalf);
      const who = ai || w.kind !== "running" || w.where === "none" ? null   // nothing is sent while it waits; an install reads no document
        : chip ? h("span", { class: "work-who", title: chip.tip }, icon(chip.icon, { size: 12 }), chip.label)
        : h("span", { class: "work-who", title: p.plain }, icon(p.icon, { size: 12 }), (p.label || "").split(",")[0]);
      const half = (where, st) => h("span", { class: `ab-half ab-s-${st || "none"}${st === "run" ? " ab-indet" : ""}` }, h("i"));
      const bar = ai ? h("span", { class: "ab-rowbar", "aria-hidden": "true" }, half("local", w.local), half("cloud", w.cloudHalf)) : null;
      const tile = (where) => h("span", { class: `ab-rowtile ar-${where}`, title: where === "cloud" ? cloudTipNow : w.localModel ? `Your local model, ${w.localModel}, reads on this computer; what it reads is not sent to ${agentCompany()}.` : `This runs on this computer; nothing is sent to ${agentCompany()}.` },
        h("span", { class: "ar-tile", "aria-hidden": "true" }, icon(where === "cloud" ? "cloud" : "house", { size: 13 })),
        h("span", { class: "visually-hidden" }, where === "cloud" ? `To ${cloudWho()}` : "On this computer"));
      const main = h("a", { class: "work-main", href: w.href, title: w.tip },   // a round goes to the Team page
        h("span", { class: "work-line" }, w.kind === "running" ? h("span", { class: "running-dot", "aria-hidden": "true" }) : icon(w.icon, { size: 14 }),
          h("strong", { class: "work-text" }, w.main), w.time ? h("span", { class: "work-time" }, w.time) : null),
        h("span", { class: "work-sub" }, h("span", { class: "work-sub-text" }, w.sub), who));
      let act = null;
      if (w.act === "start") {
        act = button({ kind: "main", sm: true, class: "work-act", onClick: async () => {
          act.disabled = true;
          try { await startClaudeNow(App.project); toast(`${t} started. You can keep working; the results appear as they come in.`, "ok"); }
          catch (e) { showError(e); }
          act.disabled = false; renderStatus();
        } }, icon("play", { size: 12 }), "Start");
      } else if (w.act === "start-local") {   // 0.19.13: the local model's part of one job (job.local), started here
        act = button({ kind: "main", sm: true, class: "work-act", onClick: async () => {
          act.disabled = true;
          try { await api("POST", `/api/jobs/${P(w.job)}/local/start`, { force: false }); toast("Started. You can keep working; the results appear as they come in.", "ok"); }
          catch (e) { showError(e); }
          act.disabled = false; renderStatus();
        } }, icon("play", { size: 12 }), "Start");
      } else if (w.act === "open-job") {   // 0.19.13: both engines wait (two starts do not fit here): the job's page has both
        act = button({ sm: true, class: "work-act", onClick: () => navigate(w.href) }, "Open");
      } else if (w.act === "cancel") {   // 0.18 queued jobs: a small quiet Cancel after the waiting state (docs/DESIGN.md 4.21, its row Queued; a running job's Stop is stopButton())
        act = button({ kind: "quiet", sm: true, class: "work-act", onClick: async () => {
          act.disabled = true;
          try { await cancelJob(w.job); } catch (e) { showError(e); }
          act.disabled = false; renderStatus();
        } }, "Cancel");
      }   // 0.17.0 (design guide): no "Open" button: the box's words are the link to where the work shows
      box.className = `work-box work-${w.kind}${ai ? ` ab-row ab-row-${w.local ? "local" : "cloud"}` : ""}`;
      // the engine with no work in this job keeps its seat: a dashed tile (said in words to a screen reader)
      const seat = (where) => h("span", { class: `ab-rowtile ab-rowseat ar-${where}`, title: where === "cloud" ? `Nothing in this work goes to ${cloudWho()}` : "No model on this computer works in this" },
        h("span", { class: "ar-tile", "aria-hidden": "true" }, icon(where === "cloud" ? "cloud" : "house", { size: 13 })),
        h("span", { class: "visually-hidden" }, where === "cloud" ? `Nothing in this work goes to ${cloudWho()}.` : "No model on this computer works in this."));
      // between its two tiles the row has no room for its words and a button side by side: the button goes under the
      // words (the status area grows a line), so no state word is ever cut
      const mid = ai && act ? h("div", { class: "work-mid" }, main, act) : null;
      replace(box, bar, w.local ? tile("local") : ai ? seat("local") : null, mid || main, mid ? null : act, w.cloudHalf ? tile("cloud") : ai ? seat("cloud") : null);
    }
  }
  let again = active.length ? 2000 : q && (waiting || answering || runner) ? 5000 : isAgent(s) ? 15000 : 0;
  // 0.18 stage 5: a quiet round of the poller is looked at again when it reaches 20 s, so a long one shows then (with
  // nothing else running, no look was due, and it never showed)
  const quietIn = quietRoundAgainIn(jobs);
  if (quietIn !== null) again = again ? Math.min(again, quietIn) : quietIn;
  if (again && document.hidden) again = Math.max(again, HIDDEN_LOOK);
  if (again) statusTimer = setTimeout(renderStatus, again);
}

// 0.14.2: the theme is a small icon beside Settings (it was a row of its own). The icon shows the theme in use;
// a click goes on to the next one, and the tooltip says which.
function themeInit() {
  const btn = document.getElementById("theme-btn");
  const apply = (mode) => {
    if (mode === "light" || mode === "dark") document.documentElement.setAttribute("data-theme", mode);
    else document.documentElement.removeAttribute("data-theme");
    const names = { system: ["monitor", "Theme: follows this computer", "Click for light."], light: ["sun", "Theme: light", "Click for dark."], dark: ["moon", "Theme: dark", "Click to follow this computer."] };
    const [ic, label, next] = names[mode] || names.system;
    replace(btn, icon(ic, { size: 17 }), h("span", { class: "visually-hidden" }, label));
    btn.title = `${label}. ${next}`;
  };
  let mode = store("theme") || "system";
  apply(mode);
  btn.addEventListener("click", () => {
    mode = mode === "system" ? "light" : mode === "light" ? "dark" : "system";
    store("theme", mode === "system" ? null : mode);
    apply(mode);
  });
}

// 0.17.0: "Find a feature or page" opens the feature finder (finder.js); the key it shows is this computer's
function findInit() {
  const btn = document.getElementById("find-btn");
  if (!btn) return;
  const mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
  const key = document.getElementById("find-key");
  if (key) key.textContent = mac ? "⌘K" : "Ctrl K";
  btn.title = `Find any place, view or action by name (${mac ? "⌘K" : "Ctrl+K"})`;
  btn.addEventListener("click", () => openFinder());
}

// "Quit Margin": stops the app (started from the Margin icon, there is no terminal to close)
function quitInit() {
  const btn = document.getElementById("quit-btn");
  if (!btn || !App.state || !App.state.can_quit) return;
  replace(btn, icon("power", { size: 13 }), h("span", {}, "Quit"));
  btn.title = `Quit ${appName()} (asks first)`;
  btn.hidden = !!(Updates.info && Updates.info.available);   // 0.17.0: an update takes Quit's place
  btn.addEventListener("click", () => quitApp());
  Updates.quit = () => quitApp();   // Settings › Technical, while Update is in Quit's place
}

// 0.13.1, "Update Margin": installs the newest version (the latest GitHub release, or the branch a git copy follows)
// and restarts into it; the page reloads by itself once the new version answers.
// 0.13.6: the button shows only when there is something to install. The page looks when it opens and every two
// minutes (checkUpdate in lib.js); a new version also pops up once, in the corner. Without one, Settings → Technical
// has Check for updates. A failed look (offline, a git copy edited by hand) stays quiet here: Settings says why.
function updateInit() {
  const btn = document.getElementById("update-btn");
  Updates.install = () => updateApp(btn);
  if (!btn || !App.state || !App.state.can_restart) return;
  btn.addEventListener("click", () => updateApp(btn));
  onUpdateSeen((info) => showUpdate(btn, info));
  const look = () => checkUpdate().catch(() => {});
  look();
  setInterval(look, UPDATE_EVERY);
  // a computer that slept, or a tab left in the background, looks again when it is back in front
  document.addEventListener("visibilitychange", () => { if (!document.hidden && Date.now() - Updates.at > UPDATE_EVERY) look(); });
}

// what a look found: the button (with the version), and the pop-up once per version
function showUpdate(btn, info) {
  if (btn.disabled) return;  // updating now: the button says so
  const quit = document.getElementById("quit-btn");
  if (!info || !info.available) { btn.hidden = true; if (quit && App.state && App.state.can_quit) quit.hidden = false; return; }
  if (quit) quit.hidden = true;   // 0.17.0: the update takes Quit's place, the same size; Quit is in Settings › Technical
  const to = "Update";
  const rc = info.candidate ? "release candidate " : "";
  replace(btn, icon("arrow-up", { size: 13 }), h("span", {}, to));
  setButtonKind(btn, "main");   // an update waits: the one thing to do here, the main kind
  btn.setAttribute("aria-label", info.latest ? `Update to ${info.latest}` : `Update ${appName()}`);
  btn.title = info.on_disk ? `${appName()} ${info.latest} is installed: restart to use it`
    : info.latest ? `${appName()} ${rc}${info.latest} is ready (you have ${info.version})`
    : `${info.changes} new change${info.changes === 1 ? "" : "s"} for this copy of ${appName()}`;
  btn.title += `. To quit ${appName()} without updating: Settings › Technical.`;
  btn.hidden = false;
  if (!info.on_disk) updatePopup(info);  // a version already on disk has the banner above the page
}

// the pop-up: in the corner until it is answered. "Later" keeps it away for this version; the button stays.
function updatePopup(info) {
  const box = document.getElementById("toasts");
  const key = info.latest || `changes-${info.changes}`;
  if (!box || box.querySelector(".update-popup") || store("update-later") === key) return;
  if (document.querySelector(".release-note-problem")) return;  // 0.15.4: the note says what to do; the button stays
  const later = () => { store("update-later", key); t.remove(); };
  const t = h("div", { class: "toast toast-info update-popup", role: "status" }, icon("arrow-up"),
    h("div", { class: "toast-body" },
      h("div", {}, h("strong", {}, info.latest ? `${appName()} ${info.candidate ? "release candidate " : ""}${info.latest} is available.` : `An update for ${appName()} is available.`),
        ` You have ${info.version}. Updating restarts ${appName()}; your projects and results are kept.`,
        // 0.15: what a candidate is, said where it is offered
        info.candidate ? ` A release candidate is a try-out of the next version: use it on a project you do not share with colleagues.` : null),
      h("div", { class: "update-popup-actions" },
        button({ kind: "main", sm: true, onClick: () => { t.remove(); Updates.install(); } }, "Update and restart"),
        button({ kind: "quiet", sm: true, onClick: later }, "Later"))),
    iconButton({ icon: "x", label: "Later", onClick: later }));
  box.appendChild(t);
}

async function runningJobs() {
  return (App.state.jobs || []).length || (await api("GET", "/api/jobs").then((r) => r.jobs.filter((j) => !TERMINAL.has(j.state)).length).catch(() => 0));
}

const RUNNING_NOTE = "Something is still running (a check, or documents being added). Restarting stops it; a check that is stopped leaves nothing behind. ";

async function updateApp(btn) {
  if (btn.disabled) return;
  const label = btn.lastChild && btn.lastChild.textContent;
  btn.disabled = true;
  if (btn.lastChild) btn.lastChild.textContent = "Looking for updates…";
  let info;
  try { info = await checkUpdate(); } catch (e) { showError(e); return done(); }
  if (!info.available) { toast(`${appName()} ${info.version} is the newest version.`, "ok"); done(); btn.hidden = true; return; }
  const running = await runningJobs();
  const what = info.on_disk ? `${appName()} ${info.latest} is installed already; ${appName()} restarts to use it.`
    : info.latest ? `${appName()} ${info.candidate ? "release candidate " : ""}${info.latest} is ready (you have ${info.version}). ${appName()} downloads it, installs it and restarts.`
    : `${info.changes} new change${info.changes === 1 ? " is" : "s are"} waiting (you have ${info.version}). ${appName()} fetches ${info.changes === 1 ? "it" : "them"} and restarts.`;
  const ok = await confirmDialog({
    title: info.on_disk ? `Restart ${appName()}?` : `Update ${appName()}?`,
    message: `${what} ${running ? RUNNING_NOTE : ""}Your projects and results are kept.`,
    confirmText: info.on_disk ? "Restart" : "Update and restart", danger: !!running,
  });
  if (!ok) return done();
  if (btn.lastChild) btn.lastChild.textContent = info.on_disk ? "Restarting…" : "Updating…";
  let r;
  try { r = await api("POST", "/api/update", {}); } catch (e) { showError(e); return done(); }
  if (!r.restarting) { toast(`${appName()} ${r.version} is the newest version.`, "ok"); done(); btn.hidden = true; return; }
  waitForRestart(r.version, r.handover);

  function done() { btn.disabled = false; if (btn.lastChild && label) btn.lastChild.textContent = label; }
}

// the restart: a page that says so, then the new version once it answers (0.17.2: the new copy keeps the token,
// which this tab keeps too; it is known by its run, the page's margin-run)
async function restartApp(version) {
  const running = await runningJobs();
  const ok = await confirmDialog({
    title: `Restart ${appName()}?`,
    message: `${appName()} ${version} starts in place of ${App.state.version}. ${running ? RUNNING_NOTE : ""}Your projects and results are kept.`,
    confirmText: "Restart", danger: !!running,
  });
  if (!ok) return;
  try { await api("POST", "/api/restart", {}); } catch (e) { showError(e); return; }
  waitForRestart(version);
}

// `handover` (0.15.4, Windows): the app quits and the new version is installed before it starts again, which takes
// longer than a restart
function waitForRestart(version, handover = false) {
  const meta = (name) => (document.querySelector(`meta[name="${name}"]`) || {}).content || "";
  const oldRun = meta("margin-run");
  const status = h("p", { class: "muted" }, handover
    ? `${appName()} closes while Windows installs the new version, then opens again by itself. This page follows in a minute or two.`
    : "This page opens the new version by itself in a moment.");
  document.title = `${appName()} is ${handover ? "updating" : "restarting"}`;
  replace(document.body, h("main", { class: "stopped-page", id: "main" },
    h("img", { src: brand().logo, alt: "", width: 48, height: 48 }),
    h("h1", {}, `${handover ? "Installing" : "Starting"} ${appName()} ${version || ""}…`),
    h("p", {}, "Your projects and results are kept."),
    status));
  const t0 = Date.now();
  let wentDown = false;
  const poll = async () => {
    try {
      const res = await fetch("/", { cache: "no-store" });
      const page = res.ok ? await res.text() : "";
      const run = (page.match(/name="margin-run" content="([^"]*)"/) || [])[1];
      if (page.includes('name="margin-version"') && (wentDown || (run !== undefined && run !== oldRun))) {
        location.reload();
        return;
      }
    } catch (_) { wentDown = true; }
    if (Date.now() - t0 > (handover ? 300000 : 90000)) {
      replace(status, App.state.launcher
        ? `${appName()} did not come back. Open it again from its icon (on your Desktop, or in Applications).`
        : `${appName()} did not come back. Start it again the way you started it before (for example with margin-gui).`);
      return;
    }
    setTimeout(poll, 800);
  };
  setTimeout(poll, 1200);
}

// `reason`: 0.10.2, why the person is asked to quit (a newer version is installed), shown in the dialog
async function quitApp(reason = "") {
  {
    const running = await runningJobs();
    const ok = await confirmDialog({
      title: `Quit ${appName()}?`,
      message: reason + (running
        ? "Something is still running (a check, or documents being added). Quitting stops it; a check that is stopped leaves nothing behind. Your projects and results are kept."
        : `${appName()} stops on this computer. Your projects and results are kept.`),
      confirmText: `Quit ${appName()}`, danger: !!running,
    });
    if (!ok) return;
    try { await api("POST", "/api/quit", {}); } catch (e) { showError(e); return; }
    const again = App.state.launcher
      ? `To open it again, double-click the ${appName()} icon (on your Desktop, or in Applications).`
      : "To open it again, start it the way you started it before (for example with margin-gui).";
    document.title = `${appName()} has stopped`;
    replace(document.body, h("main", { class: "stopped-page", id: "main" },
      h("img", { src: brand().logo, alt: "", width: 48, height: 48 }),
      h("h1", {}, `${appName()} has stopped`),
      h("p", {}, "You can close this tab. Your projects and results are kept."),
      h("p", { class: "muted" }, again)));
  }
}

// 0.10.2: Margin was updated while this copy kept running (the page files are new, the program is not): say so on
// every page, with the way to start the new version. The Margin icon also does this by itself when nothing runs.
function renderUpdateBanner() {
  const box = document.getElementById("update-banner");
  if (!box) return;
  const st = App.state || {};
  const now = st.installed_version;
  if (!now || !st.version || now === st.version) { clear(box); return; }
  // 0.13.1: a restart, where this copy can restart itself; quitting otherwise
  const how = st.can_restart ? "Restart it to use the new version."
    : st.can_quit ? `Choose Quit ${appName()}, then open ${appName()} again${st.launcher ? " from its icon" : ""}.`
    : "Stop it and start it again.";
  replace(box, notice({ kind: "info", icon: "refresh", class: "update-banner", role: "status" },
    h("div", {}, h("p", {}, h("strong", {}, `${appName()} ${now} is installed, but ${st.version} is still running.`), ` ${how}`)),
    st.can_restart ? button({ sm: true, onClick: () => restartApp(now) }, icon("refresh", { size: 13 }), "Restart now")
    : st.can_quit ? button({ sm: true, onClick: () => quitApp(`${appName()} ${now} starts when you open it again. `) }, icon("power", { size: 13 }), `Quit ${appName()}`) : null));
}

function closeDrawer() {
  const sb = document.getElementById("sidebar");
  const sc = document.getElementById("scrim");
  const mb = document.getElementById("menu-btn");
  delete sb.dataset.open;
  const main = document.getElementById("main"); if (main) main.inert = false;
  sc.hidden = true;
  mb.setAttribute("aria-expanded", "false");
}

function drawerInit() {
  const sb = document.getElementById("sidebar");
  const sc = document.getElementById("scrim");
  const mb = document.getElementById("menu-btn");
  replace(mb, icon("menu", { size: 20 }));
  mb.addEventListener("click", () => {
    const open = sb.dataset.open !== "true";
    if (open) sb.dataset.open = "true"; else delete sb.dataset.open;
    sc.hidden = !open;
    // 0.14.3: while the phone menu is open the page behind it cannot be reached (Tab stayed on it)
    const main = document.getElementById("main"); if (main) main.inert = open;
    mb.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) { const first = sb.querySelector("summary, a, button"); if (first) first.focus(); }
  });
  sc.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sb.dataset.open === "true") { closeDrawer(); mb.focus(); } });
}

// 0.17.0: the sidebar's groups say once whether their places use the AI, with the one AI mark (features.js aiTag):
// Explore "AI on request", Check "Uses the AI"; Project has none. The places themselves carry no marks and no counts
// (the team's state is said by the team line under the project's name, views/team-line.js); each has a tooltip.
const GROUP_AI = { explore: "optional", check: "uses" };
function sectionOf(key) {
  return PLACES[key] ? PLACES[key].section : (FEATURES[key] || {}).section;
}
// 0.13.6: an add-on's feature with `nav` gets a sidebar entry, after the last entry of its group (or under a new group
// heading for a section of its own). Each entry is decorated once.
function addonNav() {
  const nav = document.getElementById("nav");
  if (!nav) return;
  for (const [key, f] of Object.entries(FEATURES)) {
    if (!f.nav || nav.querySelector(`a[data-route="${CSS.escape(key)}"]`)) continue;
    const a = h("a", { href: f.href, "data-route": key }, h("span", { class: "nav-icon", "data-icon": f.icon || "circle" }), h("span", {}, f.title));
    const same = [...nav.querySelectorAll("a[data-route]")].filter((x) => sectionOf(x.dataset.route) === f.section);
    if (same.length) same[same.length - 1].after(a);
    else {
      nav.appendChild(h("span", { class: "nav-group", role: "presentation", "data-section": f.section }, (SECTIONS[f.section] || {}).short || (SECTIONS[f.section] || {}).title || ""));
      nav.appendChild(a);
    }
  }
  navIcons();
}

function navIcons() {
  for (const span of document.querySelectorAll(".nav-icon[data-icon]")) { replace(span, icon(span.dataset.icon, { size: 18 })); span.removeAttribute("data-icon"); }
  for (const a of document.querySelectorAll("#nav a[data-route]")) {
    if (a.dataset.marked) continue;
    a.dataset.marked = "1";
    const what = (PLACES[a.dataset.route] || FEATURES[a.dataset.route] || {}).what;
    if (what) a.title = what;
  }
  for (const g of document.querySelectorAll("#nav .nav-group[data-section]")) {
    const level = GROUP_AI[g.dataset.section];
    if (level && !g.querySelector(".ai-tag")) g.appendChild(aiTag(level));
  }
}

// 0.13.6: the page modules of add-ons: the fork's static/extensions.js (empty in Margin), then each add-on package's
// (GET /api/state "addon_pages"). One that fails is left out; the page still works.
async function loadExtensions() {
  const into = { FEATURES, SECTIONS };
  try { applyExtensions(localExtensions, into); } catch (e) { console.error(e); }
  for (const url of App.state.addon_pages || []) {
    try { applyExtensions((await import(url)).default, into); } catch (e) { console.error(`The add-on page ${url} could not be loaded`, e); }
  }
  addonNav();
}

// 0.13.5: the app's name, words and logo come from brand.json (and add-ons): index.html keeps Margin's as a
// fallback for the moment before the state arrives, and is never edited to rename the app.
function applyBrand() {
  const b = brand();
  for (const a of document.querySelectorAll("a.brand")) a.setAttribute("aria-label", `${b.name} home`);
  for (const img of document.querySelectorAll("a.brand img")) img.setAttribute("src", b.logo);
  const big = document.querySelector(".sidebar .brand-text");
  if (big) big.querySelector("strong").textContent = b.name;   // 0.17.0: no tagline under the name (the Overview says it)
  const small = document.querySelector(".brand-small span");
  if (small) small.textContent = b.name;
  const fav = document.querySelector('link[rel="icon"]');
  if (fav) fav.setAttribute("href", b.logo);
  let meta = document.querySelector('meta[name="description"]');
  if (!meta) { meta = document.createElement("meta"); meta.name = "description"; document.head.appendChild(meta); }
  meta.content = b.description || "";
}

// 0.14.3: "Skip to content" moves focus to the page; its address (#main) is not a page of the app
function skipLinkInit() {
  const link = document.querySelector(".skip-link");
  if (!link) return;
  link.addEventListener("click", (e) => {
    e.preventDefault();
    const t = document.getElementById("main");
    if (t) t.focus();
  });
}

// 0.14.3: one banner across the app while it cannot be reached (it was stopped, or the computer slept), so no page
// has to say it by itself. It clears when the app answers again.
function connectionInit() {
  const box = document.getElementById("stopped-banner");
  const draw = () => {
    if (!Connection.down) { clear(box); return; }
    replace(box, notice({ kind: "error", class: "stopped-banner" },
      h("div", {}, h("p", {}, h("strong", {}, `${appName()} has stopped answering.`), " Start it again the way you started it before, then reload this page. Nothing you see below is up to date."),
        button({ sm: true, onClick: () => location.reload() }, icon("refresh", { size: 13 }), "Reload this page"))));
  };
  window.addEventListener("margin-connection", draw);
  // a quiet look every few seconds while it is down, so the banner goes by itself when the app is back
  setInterval(() => { if (Connection.down) api("GET", "/api/state").catch(() => {}); }, 5000);
}

// 0.15.1: what is new, after an update, in a small note in the corner. After 0.18.0rc1 the note holds only the
// version's title and subtitle and *Read what's new*, which opens the points in a dialog (lib.js showWhatsNew;
// Settings, beside the version, has it always). It stays until it is read or closed (x or Escape): either marks it
// read, so it comes once.
// 0.15.4: or why an update on Windows did not finish (`note`, `kind: "problem"`), with what to do, in full.
async function whatsNewInit() {
  const r = await loadWhatsNew();
  const note = r && r.note;
  const problem = !!(note && note.kind === "problem" && Array.isArray(note.points) && note.points.length);
  if (!problem && !WhatsNew.unread) return;
  const n = WhatsNew.changes;
  const onKey = (ev) => { if (ev.key === "Escape") close(); };
  const remove = () => { document.removeEventListener("keydown", onKey); window.removeEventListener("margin-whats-new-read", remove); card.remove(); };
  const close = () => { if (!problem && WhatsNew.unread) markWhatsNewRead(); remove(); };
  const card = h("div", { class: problem ? "release-note release-note-problem" : "release-note", role: "status",
    "aria-live": "polite", "aria-label": problem ? "The update did not finish" : "What is new" },
    h("div", { class: "release-note-head" },
      problem ? icon("alert-triangle", { size: 15 }) : null,
      h("p", { class: "release-note-title" }, problem ? note.title : `${n.version}: ${n.title}`),
      iconButton({ icon: "x", size: 14, label: "Close", class: "release-note-close", onClick: close })),
    problem ? [note.subtitle ? h("p", { class: "release-note-sub" }, note.subtitle) : null,
      h("ul", { class: "release-note-list" }, ...note.points.map((t) => h("li", {}, t)))]
      : [n.subtitle ? h("p", { class: "release-note-sub" }, n.subtitle) : null,
        button({ kind: "quiet", sm: true, class: "release-note-read", "aria-haspopup": "dialog", onClick: () => { remove(); showWhatsNew(); } }, "Read what's new")]);
  document.addEventListener("keydown", onKey);
  if (problem) document.querySelectorAll(".update-popup").forEach((el) => el.remove());  // the same corner
  else window.addEventListener("margin-whats-new-read", remove);   // read from Settings: the note goes
  document.body.appendChild(card);
}

// 0.18 (L3) what came in: a light look at the open project's poller every 30 s. When a round the app started by itself
// brought something in, a small toast says so; when the count of what came in grows, the window event
// "margin-sync-news" (detail: the poller's state) lets the Team page and the team line show it. After every look the
// window event "margin-sync-state" carries the poller's state (null when it could not look), which the team line under
// the project's name follows (views/team-line.js); a change of project looks at once, so the line follows it without
// waiting 30 s.
// 0.18 stage 5: it also looks just after the next round is due (nextSyncLook), and while a round runs it redraws the
// sidebar's work box, which shows a round the app started by itself once it has run 20 s (drawStatus).
function syncNewsInit() {
  let project = null, round = null, count = null, timer = null, lookedFor;
  const look = async () => {
    clearTimeout(timer);
    lookedFor = App.project;
    let s = null;
    try { s = await lookOnce(); } finally {
      clearTimeout(timer);   // a look started meanwhile (a new project) set one too: one timer at a time
      timer = setTimeout(look, nextSyncLook(s));
      window.dispatchEvent(new CustomEvent("margin-sync-state", { detail: s }));
    }
  };
  App.onChange(() => { if (App.project !== lookedFor) look(); });
  const lookOnce = async () => {
    const p = App.project;
    if (!p || Connection.down || document.hidden) return null;
    let s;
    try { s = await api("GET", `/api/projects/${P(p)}/sync-poller`); } catch (_) { return null; }
    if (s.folder && s.round) renderStatus();
    const r = s.folder ? s.last_round : null;
    const n = s.folder ? s.came_in.count : 0;
    if (p === project) {
      if (r && r.job !== round && r.background && r.came_in > 0) {
        const line = ((s.came_in.rounds[0] || {}).lines || [])[0];
        toast(line || "New work from colleagues came in through the shared folder.", "info", { group: "sync-news", small: true });
      }
      if (count !== null && n > count) window.dispatchEvent(new CustomEvent("margin-sync-news", { detail: s }));
    }
    project = p; round = r ? r.job : null; count = n;
    return s;
  };
  look();
}

// 0.17.2: a tab without Margin's key (the bare address, a bookmark, or a key from before Margin started again): how to
// open it. The page carries no key, so that no one else on this computer can use Margin (lib.js ensureToken).
function renderNoKey(stale) {
  const name = appName();
  document.title = `Open ${name} from its icon`;
  replace(document.body, h("main", { class: "stopped-page", id: "main" },
    h("img", { src: brand().logo, alt: "", width: 48, height: 48 }),
    emptyState("key", `Open ${name} from its icon`,
      stale ? `${name} has started again since this tab was opened, so the tab's key no longer works. Double-click the ${name} icon (on your Desktop, or in Applications), or run margin-gui in a terminal.`
        : `${name} opens with a key in its link, so no one else on this computer can use it, and this address on its own has none. Double-click the ${name} icon (on your Desktop, or in Applications), or run margin-gui in a terminal.`,
      copyLine("margin-gui", "Copy", "a terminal")),
    h("p", { class: "muted small" }, `Your projects and results are kept. A bookmark of this address does not open ${name}; Settings › Technical › Your link to ${name} copies one that does, until ${name} stops.`)));
}

async function boot() {
  // 0.17.2: the key first: without it nothing below can load
  if (!(await ensureToken())) { renderNoKey(keyWasStale()); return; }
  skipLinkInit();
  connectionInit();
  themeInit();
  drawerInit();
  sidebarScrollInit();
  navIcons();
  initTeamLine();
  App.onChange(() => { renderProjectSwitch(); renderPrivacy(); renderStatus(); renderUpdateBanner(); });
  onJobsChanged(() => renderStatus());
  window.addEventListener("hashchange", route);
  try {
    await App.refresh();
  } catch (e) {
    if (e.status === 401) { renderNoKey(true); return; }
    replace(document.getElementById("view"), notice({ kind: "error" }, h("p", {}, e.message)));
    return;
  }
  applyBrand();
  await loadExtensions();
  renderStatus();
  updateInit();
  quitInit();
  route();
  whatsNewInit();
  initLogDrawer();
  findInit();
  syncNewsInit();   // 0.18 (L3)
  // 0.17.0: Find (Ctrl+K, or ⌘K on a Mac) opens the feature finder from any page
  document.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "k") { e.preventDefault(); openFinder(); } });
  // keep the sidebar fresh when the window regains focus
  window.addEventListener("focus", () => renderStatus());
  document.addEventListener("visibilitychange", () => { if (!document.hidden) renderStatus(); });
}

boot();
