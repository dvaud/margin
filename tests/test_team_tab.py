"""0.18.0 (roadmap L4, with L3 and L5): working together, since the team-navigation rework one place of the sidebar,
Team (#/team: the set-up, or Activity and People and settings; views/team.js, views/team-state.js, the block "Working
together" of views.css). It was the Team tab of the right-hand panel and a Team page; the drawer is the research log
only now.

- the files and how they are wired: its look in 0.17.0's stylesheets (components from components.css, the page's own
  pieces placed in views.css), the drawer without a Team tab, team.js loaded the first time the page is opened, the
  sections of each view in order with room for L2, the page drawn again when the project gains or loses its team;
- the words the brief asks for (the set-up's promise, the switch, the two downloads, a colleague's switch);
- what the tab works out, run in Node when it is installed: the poller's state (the 3-poller contract, and the
  stand-in until it is merged), the sync line, what came in, what you shared, a colleague's line, a pasted path;
- the app's answers have the fields the tab reads (the shared folder and the sharing listing, through the API).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from _static import release_sheets
from test_app import api, home  # noqa: F401  (fixtures)

STATIC = Path(__file__).resolve().parents[1] / "src" / "margin" / "gui" / "static"
TEAM = (STATIC / "views" / "team.js").read_text(encoding="utf-8")
STATE = (STATIC / "views" / "team-state.js").read_text(encoding="utf-8")
SETUP = (STATIC / "views" / "team-setup.js").read_text(encoding="utf-8")   # the Team page of a project without a team
DRAWER = (STATIC / "views" / "logdrawer.js").read_text(encoding="utf-8")
VIEWS = (STATIC / "views.css").read_text(encoding="utf-8")
# 0.17.0 (design guide): team.css and the Team tab's part of navigation.css are folded into views.css, one block
CSS = VIEWS[VIEWS.index("/* ==== Working together */"):VIEWS.index("/* ==== Quick look */")]
COMPONENTS = (STATIC / "components.css").read_text(encoding="utf-8")


def _no_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


# ------------------------------------------------------------------ files and wiring
def test_the_team_tab_has_its_block_in_the_views_stylesheet():
    # 0.17.0 (design guide): no stylesheet of its own; the components look as everywhere (components.css), and the
    # tab's own pieces are placed in views.css's block "Working together"
    sheets = release_sheets()
    assert "/static/team.css" not in sheets and not (STATIC / "team.css").exists() and "/static/views.css" in sheets
    css = _no_comments(CSS)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css) and "rgb(" not in css and "hsl(" not in css  # tokens only
    for sel in re.findall(r"\.([a-z][\w-]*)", css):
        assert sel.split("-")[0] in {"team", "share", "owner", "page", "result", "field", "switch", "ai", "work", "input",
                                     "notice", "list", "chip", "warn"} or sel in {"team"}, sel


def test_the_drawer_has_no_team_tab():
    """The team-navigation rework: the Team tab left the drawer (nobody found it there, nor the way back); the team is
    the sidebar's Team place. The drawer has no tabs, does not load team.js, and nothing opens it on a tab."""
    assert "tabs:" not in DRAWER and "onTab" not in DRAWER and "team.js" not in DRAWER and "teamPanel" not in DRAWER
    assert "margin-drawer" not in DRAWER and "margin-sync" not in DRAWER and 'session("logdrawer-tab"' not in DRAWER
    for name in ("app.js", "registry.js", "views/share.js", "views/team.js", "views/owner.js", "views/owner-state.js"):
        assert "margin-drawer" not in (STATIC / name).read_text(encoding="utf-8"), name
    assert 'drawer({ id: "logdrawer", title: "Research log", icon: "notebook", control: which,' in DRAWER
    # a round in the sidebar's work box is a plain link to the Team page
    assert '"folder-sync": { icon: "users", text: "Working together", link: "#/team" },' in (STATIC / "registry.js").read_text(encoding="utf-8")
    # drawer() keeps its documented tabs (lib.js); nothing uses them now
    lib = (STATIC / "lib.js").read_text(encoding="utf-8")
    assert 'tabs({ class: "drawer-tabs", label: title, items: tabItems, current, panel: body, onTab:' in lib


def _keys(name):
    start = TEAM.index(f"export const {name} = [")
    return re.findall(r'\{ key: "([a-z-]+)", render: \w+ \}|^  ([A-Z_]+_SECTION),', TEAM[start:TEAM.index("];", start)], flags=re.M)


def test_the_sections_come_in_order_with_room_for_the_owner():
    # Activity keeps the day-to-day; roles (DESIGN-roles §5, mock-up B): a folder problem that stops this copy ("stop")
    # comes before everything else; the owner's sections are added before the first invite (owner.js)
    assert [a or b for a, b in _keys("TEAM_ACTIVITY_SECTIONS")] == ["stop", "first-invite", "state", "problems", "came-in", "shared", "not-here"]
    assert "export function addTeamSection" in TEAM and 'before: "first-invite"' in TEAM and "Waiting for your word" in TEAM
    assert (TEAM.index('addTeamSection(OWNER_SECTION, { before: "first-invite" });') < TEAM.index('addTeamSection(MINE_SECTION, { before: "first-invite" });')
            < TEAM.index('addTeamSection(REMOVED_SECTION, { before: "shared" });'))
    assert "export function teamPanel" in TEAM and "show()" in TEAM and "hide()" in TEAM
    # People and settings is the team itself: the people, where it is, the owner, the settings, leaving
    assert [a or b for a, b in _keys("TEAM_SETTINGS_SECTIONS")] == ["people", "SELF_SYNC_SECTION", "SPACE_SECTION", "folder", "ROLES_SECTION", "CODEBOOKS_SECTION",
                                                                     "keep-out",
                                                                     "often", "downloads", "leave"]
    # the set-up is its own file's list (views/team-setup.js, tests/test_team_setup.py), offered from here too
    assert 'import { TEAM_SETUP_SECTIONS } from "./team-setup.js";' in TEAM and "export { TEAM_SETUP_SECTIONS };" in TEAM
    assert "SPACE_SETUP_SECTION" not in TEAM and "function setupSection" not in TEAM
    assert "TEAM_SECTIONS" not in TEAM and "TEAM_PAGE_SECTIONS" not in TEAM and "tabSetupSection" not in TEAM
    assert "export async function renderTeam(view, params = [], query = {})" in TEAM
    assert ("sections: !withTeam ? TEAM_SETUP_SECTIONS : want === \"settings\" ? TEAM_SETTINGS_SECTIONS : TEAM_ACTIVITY_SECTIONS" in TEAM
            and "page: true, onCount: setTeamPageCount," in TEAM)
    assert "panel.destroy()" in TEAM and 'window.removeEventListener("margin-sync-news", news)' in TEAM
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'import("./views/team.js").then((m) => m.renderTeam(view, params, query))' in app   # loaded when first opened
    # Activity links to People and settings in one quiet line: "Backblaze · 3 people · People and settings"
    assert 'link({ href: "#/team/settings", id: "team-to-settings" }, "People and settings")' in TEAM and "teamSummary(st)" in TEAM
    assert "Manage the team" not in TEAM


def test_the_team_place_draws_itself_for_its_state():
    """No team: the set-up with no tabs; with one: the view tabs Activity | People and settings. Each state has its own
    line under the title; a refresh that finds the project gained or lost its team, or another project, draws the page
    again; the page's count goes to the team line while it is open."""
    fn = TEAM[TEAM.index("export async function renderTeam("):TEAM.index("// keepOut null: not touched here")]
    for key, words in (("setup", "Work on this project with colleagues. Each of you keeps your own copy on your own computer; Margin sends what you choose to share and brings in what they share."),
                       ("activity", "What your colleagues shared, what you shared, and whether your copies are in step."),
                       ("settings", "Who is in the team, where its shared work is kept, and how this copy takes part.")):
        assert f'  {key}: "{words}",' in TEAM, key
    assert 'const want = params[0] === "settings" ? "settings" : "activity";' in fn
    assert 'pageHead("Team", { eyebrow: featureEyebrow("together"), sub: HEAD_LINE[key] }), withTeam ? viewTabs("team", want) : null' in fn
    assert "const hasTeam = (st) => !!(st && (st.folder || st.space));" in TEAM
    assert "if (project === builtFor && hasTeam(st) === team) return true;" in fn and "build(hasTeam(st), true);" in fn
    assert "if (onStatus && onStatus(status, project) === false) return;" in TEAM     # the panel stops drawing
    assert "teamFoundOnPage(project, hasTeam(st));" in fn                              # no team: the entry says nothing
    assert "setTeamPageCount(null);" in fn                                             # the page goes: the poller's count
    # #/team?at=<section>: that section's heading, once drawn
    assert "let panel = null, team = null, builtFor = null, at = query.at || null, alive = true;" in fn
    assert "panel.focusSection(at).then((found) => { if (found && mine === panel) at = null; });" in fn
    assert '"#/team?at=shared"' in (STATIC / "views" / "share.js").read_text(encoding="utf-8")


def test_the_first_invite_while_you_are_the_only_one():
    fn = TEAM[TEAM.index("function firstInviteSection(ctx) {"):TEAM.index("function stateSection(ctx) {")]
    assert "if (!sp.keeper || others.length) return null;" in fn
    # with an invite waiting, the card says so and offers another (a small button: the first is the card's main one)
    assert "waiting to be used" in fn and 'id: "team-invite-another", onClick: () => inviteDialog(ctx) }, "Invite another colleague…")' in fn
    assert 'link({ href: "#/team/settings?at=people", id: "team-invites-waiting" }, "People and settings")' in fn
    assert "You are the only one in this team so far. Make an invite link and send it to a colleague: they join from it in a minute." in fn
    assert 'button({ kind: "main", sm: true, icon: "plus", id: "team-first-invite", onClick: () => inviteDialog(ctx) }, "Invite a colleague…")' in fn
    # a shared folder no colleague has used: one sentence and the way to the three steps
    assert "if ((st.people || []).length || st.reachable === false) return null;" in fn
    assert 'link({ href: "#/team/settings?at=people", id: "team-first-steps" }, "People and settings")' in fn
    space = (STATIC / "views" / "team-space.js").read_text(encoding="utf-8")
    assert "export async function inviteDialog(ctx) {" in space
    # the invites and Invite a colleague… stand with the people (the People card), not in the storage space's card
    assert "export function spaceInvites(ctx) {" in space and TEAM.count("...spaceInvites(ctx)") == 2
    people = TEAM[TEAM.index("function peopleSection(ctx) {"):TEAM.index("function sharedSection(ctx) {")]
    assert "listGroup(null, mine, ...rows, ...joined)), ...spaceInvites(ctx), gone, both, join);" in people
    card = space[space.index("function spaceSection(ctx) {"):space.index("export function spaceInvites(ctx) {")]
    assert "inviteDialog" not in card and "Invites not used yet" not in card


def test_activity_keeps_the_day_to_day_and_settings_the_team():
    """The owner's request (after 0.18.0rc3): joining a team is in the project menu, the team itself is in People and
    settings, and Activity says little: states, counts and buttons, the longer words behind help marks and folds."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    design = (STATIC / "views" / "design.js").read_text(encoding="utf-8")
    setup = (STATIC / "views" / "setup.js").read_text(encoding="utf-8")
    owner = (STATIC / "views" / "owner.js").read_text(encoding="utf-8")
    space = (STATIC / "views" / "team-space.js").read_text(encoding="utf-8")
    # the project menu: Join a team… right under New project…, above Manage projects; no Manage the team (the place is
    # in the sidebar)
    menu = app[app.index("function renderProjectSwitch()"):app.index("export async function switchProject")]
    assert (menu.index('"New project…"') < menu.index('{ text: "Join a team…", icon: "link", onClick: () => joinDialog(null) }')
            < menu.index('"Manage projects"'))
    assert "Manage the team" not in menu
    assert '{ text: "Join a team…", icon: "link" }' in design and '"Manage the team"' not in design   # the live reference
    assert "joinDialog(null)" in setup                                     # a first run can start from an invite
    # the tab: nothing waits, no section; empty states in two words; the switches and the set-up on the page
    assert "return null;   // nothing waits: no section" in owner and "if (v.is_owner) body.push(acceptAddsSwitch(ctx, v));" in owner
    assert owner.index("function rolesSection(") < owner.index("if (v.is_owner) body.push(acceptAddsSwitch(ctx, v));")
    assert 'helpMark("About accepting documents at once", ACCEPT_ADDS_HELP)' in owner
    # an empty card says how it fills (a page has the room for a sentence)
    assert '"Nothing yet. What your colleagues share shows here when a round brings it in."' in TEAM
    assert '"Nothing yet. Press Share on a check, a set of themes, a codebook, a note, a research log entry of yours or a link between terms."' in TEAM
    assert '{ label: "About documents that stay here", text: KEEP_OUT_HELP }' in TEAM
    assert 'helpMark("About documents not on this computer", NOT_HERE_HELP)' in TEAM
    assert '"Your colleague’s folder is not here yet?"' in SETUP          # the OneDrive how-to in a fold by the field
    # without a team the page says what a person came to do, not how the storage works (views/team-setup.js)
    assert '"Start a team for this project"' in SETUP and '"Join a colleague’s team"' in SETUP and '"Send it once, as a file"' in SETUP
    assert 'helpMark("How working together works", HOW_HELP)' in SETUP and "A storage space (recommended)" not in space + SETUP
    # the sync state in one line: its second line only when it needs you, else the tooltip
    assert 'const SAY_SUB = new Set(["running", "busy", "offline", "failed", "never"]);' in TEAM and "ws.title = s.sub;" in TEAM
    tab = TEAM[TEAM.index("function stateSection(ctx) {"):TEAM.index("// The Team page: how often rounds run")]
    assert "team-every" not in tab and "team-pause-all" not in tab and '"team-pause"' in tab and '"team-sync-now"' in tab


def test_no_inline_look_and_no_link_drawn_as_a_button():
    for name, js in (("team.js", TEAM), ("team-state.js", STATE), ("share.js", (STATIC / "views" / "share.js").read_text(encoding="utf-8"))):
        assert "style:" not in js and ".style." not in js, name
        assert not re.search(r'h\("a", \{[^}]*class: "btn', js), name


def test_the_words_of_the_brief():
    assert "The folder will hold the documents’ text and files, and only what you share of your own work. " in SETUP
    assert "Keep documents marked Only a local AI or No AI out of the shared folder" in STATE and "KEEP_OUT_LABEL" in TEAM and "KEEP_OUT_LABEL" in SETUP
    assert "It is on for the whole team because" in TEAM
    assert "Mark as seen" in TEAM and "Sync now" in TEAM and "Stop using this folder" in TEAM
    # a document not on this computer: absentDocument() (lib.js), with "Add its file", to the Documents page
    assert "absentDocument(d.title || d.doc_id, { onAdd: () => navigate(\"#/sources\") })" in TEAM
    assert '"Add its file"' in (STATIC / "lib.js").read_text(encoding="utf-8")
    assert "Pause" in TEAM and "Resume" in TEAM and "How often Margin looks" in TEAM
    assert "C:\\\\Users\\\\Anna" in SETUP and "/Users/anna/" in SETUP        # a path for Windows and for a Mac
    # the server's refusal is shown as it is, by the field
    assert "if (e.status === 400) showErr(e.message);" in SETUP and 'role: "alert", id: "team-folder-error"' in SETUP
    # (final check: choosing the folder again never turns the switch off by itself; untouched, it is not sent)
    assert ('keepOut === null ? { path: p } : { path: p, keep_out: keepOut }' in SETUP
            and 'switchControl(KEEP_OUT_LABEL, !!(st.keep_out || {}).mine' in SETUP and 'let keepOut = null;' in SETUP)
    assert 'api("DELETE", `/api/projects/${P(ctx.project)}/shared-folder`' in TEAM
    assert 'api("POST", `/api/projects/${P(ctx.project)}/shared-folder/sync`' in TEAM
    assert 'api("PUT", `/api/projects/${P(ctx.project)}/shared-folder/keep-out`, { keep_out: want })' in TEAM
    assert 'zipButton(project, "shared", { id: "team-zip-shared" })' in TEAM and 'zipButton(project, "all"' in TEAM


def test_the_panel_redraws_only_what_changed_and_keeps_the_place():
    """A redraw under a hand lost what was typed and moved the focus (the independent review): the panel draws again only
    when the app's answers changed, keeps what was typed in the set-up, finds the focus again by id, and follows only
    its own project's round."""
    assert "if (force || sig !== drawn) { drawn = sig; draw(); } else updateLine();" in TEAM
    # the set-up keeps the chosen place across a redraw; the folder form is a dialog, which no redraw reaches
    assert "typed.where = v;" in SETUP and 'title: joining ? "Join through a folder your colleague shared" : "Start with a folder you share"' in SETUP
    assert 'fa.matches("input[type=text], textarea, select")' in TEAM
    assert "document.getElementById(had.id)" in TEAM and "textContent.trim() === keep.text" not in TEAM
    assert "(j.project && j.project !== project)" in TEAM and "if (watching) { watching.w.stop(); watching = null; }" in TEAM
    assert "e.status === 404 ? null : prev" in TEAM                       # only a 404 means "no poller yet"
    assert 'role: "status", "aria-live": "polite"' in TEAM and '["offline", "paused", "failed"]' in TEAM
    for i in ("team-keep-out", "team-pause-all", "team-sync-now", "team-mark-seen", "team-leave"):
        assert f'"{i}"' in TEAM, i
    assert '"team-setup-keep-out"' in SETUP
    assert 'ctx.focusHeading("state")' in TEAM and 'ctx.focusHeading("space-setup")' in TEAM
    # another project: the page draws itself again with its own state and count
    assert "const off = App.onChange(() => panel.refresh());" in TEAM and "project === builtFor" in TEAM


def test_the_poller_is_read_through_its_announced_paths():
    for path in ("/api/projects/${p}/sync-poller", "/api/projects/${p}/sync-poller/seen", '"/api/sync-poller"'):
        assert path in STATE, path
    assert "POLLER_API.state(P(project))" in TEAM and "POLLER_API.seen(P(ctx.project))" in TEAM
    assert "every_minutes" in TEAM and "{ through: ctx.poll.newest_id }" in TEAM
    assert not re.search(r"^import ", STATE, flags=re.M)  # no imports: it runs in Node


# ------------------------------------------------------------------ what the tab works out (Node)
NODE = r"""
import * as T from "./team-state.js";
const NOW = Date.parse("2026-11-11T10:00:00Z");
const iso = (s) => new Date(NOW + s * 1000).toISOString();
const ben = { id: "p8ce2bc0af2e9", name: "Ben Okafor" };
const status = { folder: "/x", reachable: true, problems: [], people: [{ id: ben.id, name: "Ben Okafor", app_version: "0.18.0",
  waiting: 0, last_read_at: iso(-300) }], me: { last_written_at: iso(-600) }, job: null,
  last_round: { state: "done", finished_at: (NOW - 60000) / 1000, result: { at: iso(-60), read: [
    { id: ben.id, name: "Ben Okafor", report: { lines: ["From Ben Okafor: 1 new result."] } },
    { id: "pc0ffeec0ffee", name: "Chloé", report: { lines: ["Nothing new: this copy already has everything in Chloé's file."] } }] } } };
const history = [{ at: iso(-60), from: ben, lines: ["From Ben Okafor: 1 new result."] },
                 { at: iso(-7200), from: ben, lines: ["1 note of Ben Okafor's came in."] },
                 { at: iso(-9000), from: ben, lines: ["Nothing new: this copy already has everything in Ben Okafor's file."] }];
const poller = { project: "Demo", folder: true, paused: false, paused_all: false, state: "waiting", every_seconds: 120,
  next_round_at: iso(100), next_round_in: 100, offline: null, busy: null, round: null,
  last_round: { job: "j1", background: true, state: "done", finished_at: iso(-30), offline: false, problems: [], came_in: 2, error: null },
  came_in: { count: 2, seen_through: 4, rounds: [{ id: 5, at: iso(-30), from: ben, bundles: [3, 3], lines: ["From Ben Okafor: 1 new result."], count: 2 }] } };
const out = {};
// the stand-in: the round of this app, the project's history, what was seen in this browser
const s1 = T.pollerState(status, null, null, null);
out.standin = { live: s1.live, auto: s1.auto, last_at: s1.last_at, came: s1.came_in.map((c) => [c.from, c.lines, c.seen]), unseen: s1.unseen };
const s2 = T.pollerState(status, NOW - 3600000, history, null);
out.history = { came: s2.came_in.map((c) => [c.lines[0], c.seen]), unseen: s2.unseen };
const s3 = T.pollerState({ ...status, last_round: null }, null, null, null);
out.lastFromFolder = s3.last_at === NOW - 300000;
// the poller (3-poller's contract): what came in since you last looked, then what was seen before (the history)
const live = T.pollerState(status, null, history, poller);
out.live = { live: live.live, auto: live.auto, paused: live.paused, next_at: live.next_at, unseen: live.unseen, newest: live.newest_id,
  came: live.came_in.map((c) => [c.lines[0], c.seen]), every: live.every };
out.lines = {
  waiting: T.syncLine(status, live, NOW),
  offline: T.syncLine(status, T.pollerState(status, null, null, { ...poller, state: "offline", offline: { since: iso(-600), failures: 3, retry_seconds: 480 }, next_round_at: iso(470) }), NOW),
  offlineStandin: T.syncLine({ ...status, reachable: false, problems: [{ kind: "unreachable", message: "x" }] }, null, NOW),
  paused: T.syncLine(status, T.pollerState(status, null, null, { ...poller, state: "paused", paused: true }), NOW),
  pausedAll: T.syncLine(status, T.pollerState(status, null, null, { ...poller, state: "paused", paused_all: true }), NOW),
  busy: T.syncLine(status, T.pollerState(status, null, null, { ...poller, state: "busy", busy: { id: "j", kind: "read-new", title: "Reading", message: "Queued: starts when “Reading” has finished" } }), NOW),
  running: T.syncLine({ ...status, job: { id: "r", state: "running", progress: { message: "Reading Ben Okafor's work (1 of 1)" } } }, live, NOW),
  queued: T.syncLine(status, T.pollerState(status, null, null, { ...poller, state: "running", round: { id: "r", state: "queued", waiting_for: { message: "Queued: starts when “X” has finished" } } }), NOW),
  failed: T.syncLine({ ...status, last_round: { ...status.last_round, state: "error", error: "Disk full" } }, null, NOW),
  never: T.syncLine({ ...status, last_round: null, people: [], me: {} }, null, NOW),
};
out.shared = T.myShared({ items: [
  { kind: "check", key: "h1", state: "shared", mine: true, owner: { id: "me" }, here: true, at: "2026-11-11T09:00:00Z" },
  { kind: "check", key: "h2", state: "shared", mine: true, owner: { id: "me" }, here: true, at: "2026-11-11T09:30:00Z" },
  { kind: "check", key: "h3", state: "private", mine: true, owner: { id: "me" }, here: true },
  { kind: "note", key: "n1", state: "withdrawn", mine: true, owner: { id: "me" }, here: true },
  { kind: "check", key: "h9", state: "shared", mine: false, owner: { id: "ben" }, here: true },
  { kind: "log", key: "e1", state: "shared", mine: false, owner: null, here: true },
  { kind: "themes", key: "t1", state: "shared", mine: true, owner: { id: "me" }, here: false }] });
out.person = [T.personLine({ id: "a", app_version: "0.18.0", waiting: 0 }), T.personLine({ id: "a", waiting: 2 }),
  T.personLine({ id: "c", app_version: "0.19.0", waiting: 1 }, [{ kind: "newer_format", person: { id: "c" } }])];
out.paths = ['"C:\\Users\\Anna\\OneDrive\\Team"', "  /Users/anna/Dropbox/Team/ ", "C:\\", "'/Volumes/Team drive'"].map(T.cleanPath);
out.when = [T.whenText(iso(-60), new Date(NOW)), T.whenPhrase(iso(-60), new Date(NOW)), T.inText(iso(100), NOW), T.inText(iso(20), NOW)];
out.news = T.newsLines(["Nothing new: this copy already has everything in Ben's file.", "", "From Ben: 1 new result."]);
// two rounds of a colleague that read alike: the one not seen yet takes away one entry of the history only
const alike = [{ at: iso(-40), from: ben, lines: ["1 judgement of Ben Okafor's came in, under their name."] },
               { at: iso(-4000), from: ben, lines: ["1 judgement of Ben Okafor's came in, under their name."] }];
const one = T.pollerState(status, null, alike, { ...poller, came_in: { count: 1, rounds: [{ id: 9, at: iso(-30), from: ben, lines: alike[0].lines, count: 1 }] } });
out.alike = one.came_in.map((c) => [c.at, c.seen]);
// after a restart the poller has no last round: the last time work was read or written stands for it
out.restart = T.syncLine(status, T.pollerState(status, null, null, { ...poller, last_round: null }), NOW).text;
out.whose = [T.whoseWork(["Ben Okafor"]), T.whoseWork(["Ben", "Chloé"]), T.whoseWork([null])];
// checked against the real poller: a queued Sync now cancelled is the poller's last round, "cancelled"
out.stopped = T.syncLine(status, T.pollerState(status, null, null, { ...poller, last_round: { ...poller.last_round, state: "cancelled" } }), NOW);
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def node_out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("Node is not installed")
    d = tmp_path_factory.mktemp("team-node")
    (d / "package.json").write_text('{"type": "module"}')
    (d / "team-state.js").write_text(STATE, encoding="utf-8")
    (d / "run.mjs").write_text(NODE, encoding="utf-8")
    r = subprocess.run([shutil.which("node"), str(d / "run.mjs")], capture_output=True, text=True,
                       env={**os.environ, "TZ": "Europe/Amsterdam"})  # the times are read in Dutch local time
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


NOW_MS = 1794391200000  # 2026-11-11T10:00:00Z


def test_the_stand_in_reads_the_folder_and_the_history(node_out):
    s = node_out["standin"]
    assert s["live"] is False and s["auto"] is False and s["last_at"] == NOW_MS - 60000
    assert s["came"] == [["Ben Okafor", ["From Ben Okafor: 1 new result."], False]] and s["unseen"] == 1  # "Nothing new" left out
    h = node_out["history"]
    assert h["came"] == [["From Ben Okafor: 1 new result.", False], ["1 note of Ben Okafor's came in.", True]] and h["unseen"] == 1
    assert node_out["lastFromFolder"] is True


def test_the_poller_state_is_mapped_as_announced(node_out):
    live = node_out["live"]
    assert live["live"] is True and live["auto"] is True and live["paused"] is False and live["every"] == 120
    assert live["next_at"] == NOW_MS + 100000 and live["unseen"] == 2 and live["newest"] == 5
    # the round not seen yet, then what was seen before from the history (the same round is not listed twice)
    assert live["came"] == [["From Ben Okafor: 1 new result.", False], ["1 note of Ben Okafor's came in.", True]]


def test_the_sync_line_says_each_state(node_out):
    ln = node_out["lines"]
    assert ln["waiting"] == {"kind": "ok", "text": "Last round: Today 10:59", "sub": "Up to date; next round in about 2 min."}
    assert ln["offline"]["kind"] == "offline" and "tries again by itself in about 8 min" in ln["offline"]["sub"]
    assert ln["offlineStandin"]["kind"] == "offline" and "press Sync now" in ln["offlineStandin"]["sub"]
    assert ln["paused"]["text"] == "Paused" and "Sync now still works" in ln["paused"]["sub"]
    assert ln["pausedAll"]["text"] == "Paused for every project"
    assert ln["busy"] == {"kind": "busy", "text": "The next round waits", "sub": "Queued: starts when “Reading” has finished"}
    assert ln["running"] == {"kind": "running", "text": "Syncing now…", "sub": "Reading Ben Okafor's work (1 of 1)"}
    assert ln["queued"]["text"] == "A round waits its turn" and ln["queued"]["sub"].startswith("Queued:")
    assert ln["failed"]["kind"] == "failed" and ln["failed"]["sub"] == "Disk full"
    assert ln["never"] == {"kind": "never", "text": "No round yet", "sub": "Press Sync now for the first round."}


def test_what_you_shared_and_a_colleagues_line(node_out):
    sh = node_out["shared"]
    assert [i["key"] for i in sh["byKind"]["check"]] == ["h2", "h1"]  # newest first, not a colleague's, not private
    assert [i["key"] for i in sh["byKind"]["log"]] == ["e1"]           # maker not known: anyone may take it back
    assert "themes" not in sh["byKind"] and sh["withdrawn"] == 1 and sh["total"] == 3
    p = node_out["person"]
    assert p[0] == {"text": "Margin 0.18.0 · up to date", "warn": False}
    assert p[1]["text"] == "new work waiting (2 rounds): it comes in with the next round"
    assert p[2]["warn"] is True and "newer Margin" in p[2]["text"]


def test_rounds_that_read_alike_and_a_restart(node_out):
    assert node_out["alike"] == [[NOW_MS - 30000, False], [NOW_MS - 4000000, True]]
    assert node_out["restart"] == "Last round: Today 10:55"   # Ben's work read at 09:55 UTC
    assert node_out["whose"] == ["Ben Okafor’s work came in.", "Ben’s and Chloé’s work came in.", "A colleague’s work came in."]


def test_a_round_stopped_is_said_so(node_out):
    assert node_out["stopped"] == {"kind": "ok", "text": "Last round stopped: Today 10:59", "sub": "Next round in about 2 min."}


def test_what_the_real_poller_showed():
    """Found against the real poller (0.18 merge): a round due was shown as "Starting…" for 20 s (the tab now looks
    again within seconds); the focus fell off Sync now, Pause and the switches (Sync now is off with aria-disabled, the
    others get the focus back); offline, the people list said no colleague had used the folder."""
    assert "ctx.poll && ctx.poll.due ? SOON : EVERY" in TEAM and "const SOON = 4000;" in TEAM
    assert '"aria-disabled": running ? "true" : null, id: "team-sync-now"' in TEAM
    assert 'if (sync.getAttribute("aria-disabled") !== "true") ctx.startRound(sync);' in TEAM
    assert "const again = id && document.getElementById(id); if (again) again.focus();" in TEAM
    assert "Your colleagues show here again once the shared folder can be reached." in TEAM
    assert 'if (s.kind === "running" && loud(said)) return;' in TEAM


def test_a_pasted_path_and_the_times(node_out):
    assert node_out["paths"] == ["C:\\Users\\Anna\\OneDrive\\Team", "/Users/anna/Dropbox/Team", "C:\\", "/Volumes/Team drive"]
    assert node_out["when"] == ["Today 10:59", "today at 10:59", "in about 2 min", "in less than a minute"]
    assert node_out["news"] == ["From Ben: 1 new result."]


# ------------------------------------------------------------------ the app's answers have what the tab reads
def test_the_answers_have_the_fields_the_tab_reads(api, tmp_path):  # noqa: F811
    assert api("POST", "/api/projects", {"name": "Demo"})[0] == 200
    st, r = api("GET", "/api/projects/Demo/shared-folder")
    assert st == 200 and {"folder", "reachable", "keep_out", "me", "people", "problems", "not_here", "job", "last_round"} <= set(r)
    assert {"mine", "colleagues", "in_force"} <= set(r["keep_out"]) and {"name", "last_written_at"} <= set(r["me"])
    st, r = api("GET", "/api/projects/Demo/sharing")
    assert st == 200 and {"items", "counts", "me", "kinds"} <= set(r)
    st, r = api("GET", "/api/projects/Demo/together")
    assert st == 200 and isinstance(r["history"], list)
    shared = tmp_path / "Team folder"
    shared.mkdir()
    st, r = api("PUT", "/api/projects/Demo/shared-folder", {"path": str(shared)})
    assert st == 200 and r["folder"]
    st, r = api("POST", "/api/projects/Demo/shared-folder/sync", {})
    job = api.wait(r["job"]["id"])
    st, r = api("GET", "/api/projects/Demo/shared-folder")
    last = r["last_round"]
    assert last["state"] == "done" and isinstance(last["finished_at"], (int, float))
    assert {"wrote", "read", "problems"} <= set(last["result"]) and "waiting" in last["result"]["wrote"]
    assert job["id"] == last["id"]
    st, r = api("DELETE", "/api/projects/Demo/shared-folder", {})
    assert st == 200 and r["folder"] is None


def test_choosing_the_folder_again_keeps_the_switch(api, tmp_path):  # noqa: F811
    # final check: Stop using this folder, then Use this folder again, turned the keep-out switch off by itself, and
    # the next round wrote a No-AI document's reading and file into the folder
    assert api("POST", "/api/projects", {"name": "Demo"})[0] == 200
    shared = tmp_path / "Team folder"
    shared.mkdir()
    st, r = api("PUT", "/api/projects/Demo/shared-folder", {"path": str(shared), "keep_out": True})
    assert st == 200 and r["keep_out"]["mine"] is True
    assert api("DELETE", "/api/projects/Demo/shared-folder", {})[1]["keep_out"]["mine"] is True
    st, r = api("PUT", "/api/projects/Demo/shared-folder", {"path": str(shared)})        # the page sends no switch
    assert st == 200 and r["folder"] and r["keep_out"]["mine"] is True
    st, r = api("PUT", "/api/projects/Demo/shared-folder", {"path": str(tmp_path / "nowhere"), "keep_out": False})
    assert st == 400                                                                   # refused: the switch stays
    assert api("GET", "/api/projects/Demo/shared-folder")[1]["keep_out"]["mine"] is True
    st, r = api("PUT", "/api/projects/Demo/shared-folder", {"path": str(shared), "keep_out": False})
    assert st == 200 and r["keep_out"]["mine"] is False


def test_the_panel_brings_a_section_into_view():
    """team-share piece B: #/team?at=<section> names a section (See what you shared: "shared"); the panel focuses its
    heading once the refresh show() started has drawn, and brings it into view; it says whether the section is there."""
    assert "async focusSection(key) {" in TEAM
    fn = TEAM[TEAM.index("async focusSection(key) {"):TEAM.index("// the page's panel")]
    assert "await reading;" in fn and "focusHeading(key);" in fn and "scrollIntoView(" in fn
    assert "if (!head) return false;" in fn and "return true;" in fn
    assert "show() { shown = true; reading = refresh(); arm(); }," in TEAM


# ------------------------------------------------------------------ an item's sharing line: who gets it, and when (piece A)
BRIEF_NODE = r"""
import * as T from "./team-state.js";
const NOW = Date.parse("2026-11-11T10:00:00Z");
const iso = (s) => new Date(NOW + s * 1000).toISOString();
const m = (name, x = {}) => ({ person: name.toLowerCase(), name, ...x });
const folder = (people) => ({ folder: "/x", space: null, people: people.map((n) => ({ name: n })), me: { last_written_at: iso(-600) } });
const space = (members) => ({ folder: null, space: { members }, people: [], me: {} });
const poller = { state: "waiting", paused: false, paused_all: false, next_round_at: iso(100),
  last_round: { state: "done", finished_at: iso(-30) } };
const out = {};
out.names = [
  T.briefOf(space([m("Anna Smit", { me: true }), m("Ben Okafor")]), null).names,
  T.briefOf(space([m("Anna", { me: true }), m("Ben Okafor"), m("Chloé Martin"), m("Dan", { removed: "2026-11-10" })]), null).names,
  T.briefOf(folder(["Ben Okafor", "Chloé", "Dan Li", "Eva"]), null).names,
  T.briefOf(folder([]), null).names,
  T.briefOf(space([m("Anna", { me: true })]), null).names,
];
out.team = [T.briefOf(folder([]), null).team, T.briefOf(space([]), null).team, T.briefOf({ folder: null, space: null }, null).team,
  T.briefOf(null, poller).team];
out.times = [T.briefOf(folder(["Ben"]), poller), T.briefOf(folder(["Ben"]), { ...poller, paused: true, last_round: { state: "error", finished_at: iso(-30) } }),
  T.briefOf(folder(["Ben"]), { ...poller, paused_all: true, last_round: null }), T.briefOf(space([]), null)].map((b) => [b.nextAt, b.sentAt]);
// read for a project: both routes, a failed one counts as null, kept 15 s
const asked = [];
const get = async (path) => { asked.push(path); if (path.endsWith("/sync-poller")) throw new Error("404"); return folder(["Ben", "Chloé"]); };
const b1 = await T.teamBrief("Green hydrogen", get);
const b2 = await T.teamBrief("Green hydrogen", get);
T.forgetBrief("Green hydrogen");
await T.teamBrief("Green hydrogen", get);
out.read = { b1, same: b1 === b2, asked };
console.log(JSON.stringify(out));
"""


def test_the_brief_says_who_gets_a_shared_item_and_when(tmp_path):
    fn = STATE[STATE.index("export function briefOf("):]
    assert "const team = !!(status && (st.folder || st.space));" in fn
    assert "!m.me && !m.removed" in fn and "st.people" in fn
    assert "`your ${first.length} colleagues`" in fn and '"your team"' in fn
    assert "p.next_round_at" in fn and 'last.state === "done" && last.finished_at' in fn and "st.me.last_written_at" in fn
    rd = STATE[STATE.index("export async function teamBrief(project, get = null)"):]
    assert "`/api/projects/${p(project)}/shared-folder`" in rd and "POLLER_API.state(p(project))" in rd
    assert "const BRIEF_TTL = 15000;" in STATE and 'await import("../lib.js")' in rd
    if shutil.which("node") is None:
        pytest.skip("Node is not installed")
    (tmp_path / "package.json").write_text('{"type": "module"}')
    (tmp_path / "team-state.js").write_text(STATE, encoding="utf-8")
    (tmp_path / "run.mjs").write_text(BRIEF_NODE, encoding="utf-8")
    r = subprocess.run([shutil.which("node"), str(tmp_path / "run.mjs")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["names"] == ["Ben", "Ben and Chloé", "your 4 colleagues", "your team", "your team"]
    assert got["team"] == [True, True, False, False]
    t = "2026-11-11T09:59:30.000Z"
    assert got["times"] == [["2026-11-11T10:01:40.000Z", t], [None, "2026-11-11T09:50:00.000Z"],
                            [None, "2026-11-11T09:50:00.000Z"], [None, None]]
    assert got["read"]["b1"] == {"team": True, "names": "Ben and Chloé", "nextAt": None, "sentAt": "2026-11-11T09:50:00.000Z"}
    assert got["read"]["same"] is True
    assert got["read"]["asked"] == ["/api/projects/Green%20hydrogen/shared-folder", "/api/projects/Green%20hydrogen/sync-poller"] * 2
