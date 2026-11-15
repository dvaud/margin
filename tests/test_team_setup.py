"""The Team page of a project without a team (views/team-setup.js) and the storage space's set-up as guided steps
(views/team-space.js, lib.js guidedSteps(), docs/DESIGN.md 4.28).

A new user who came to share a project read *A storage space (recommended)* as something else than starting a team,
could not tell what the buttons *Backblaze…* and *Cloudflare…* would do, and did not know what the folder was the
alternative to. So:
- the page's cards are named by what a person came to do (start a team, join one, send a file once);
- where the shared work is kept is an option card each, named by what it is, and the one main button says what it
  starts;
- joining says where the team's project goes, and a new project is the usual answer (as the invite's own words say);
- the set-up is one step at a time, the whole way in view, and its main button waits for the step that asks.
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "margin" / "gui" / "static"
SETUP = (STATIC / "views" / "team-setup.js").read_text(encoding="utf-8")
SPACE = (STATIC / "views" / "team-space.js").read_text(encoding="utf-8")
LIB = (STATIC / "lib.js").read_text(encoding="utf-8")
CSS = (STATIC / "components.css").read_text(encoding="utf-8")


def _fn(js: str, head: str) -> str:
    start = js.index(head)
    return js[start:js.index("\n}\n", start)]


def test_the_cards_say_what_a_person_came_to_do():
    keys = re.findall(r'\{ key: "([a-z-]+)", render: (\w+) \}', SETUP[SETUP.index("export const TEAM_SETUP_SECTIONS"):])
    assert keys == [("found", "foundSection"), ("space-setup", "startSection"), ("join", "joinSection"), ("downloads", "fileSection")]
    for title in ('"Start a team for this project"', '"Join a colleague’s team"', '"Send it once, as a file"'):
        assert title in SETUP
    # every one of them is the set-up only: nothing shows once the project has a team
    for fn in ("foundSection", "startSection", "joinSection", "fileSection"):
        assert "if (!noTeam(ctx)) return null;" in _fn(SETUP, f"function {fn}(ctx) {{"), fn
    assert "const noTeam = (ctx) => !ctx.status.folder && !ctx.status.space;" in SETUP


def test_where_the_work_is_kept_is_named_by_what_it_is():
    where = SETUP[SETUP.index("export const WHERE = ["):SETUP.index("const noTeam")]
    assert re.findall(r'value: "(\w+)"', where) == ["b2", "webdav", "r2", "folder"]
    titles = re.findall(r'title: "([^"]+)"', where)
    assert titles == ["A storage space at Backblaze", "Your institution’s drive", "A storage space at Cloudflare", "A folder you already share"]
    assert where.count('tag: "Recommended"') == 1 and where.index('tag: "Recommended"') < where.index('value: "webdav"')
    # no button is a company's name: the one main button says what it starts, in the chosen card's words
    assert re.findall(r'go: "([^"]+)"', where) == ["Set up at Backblaze…", "Set up in your institution’s drive…", "Set up at Cloudflare…", "Choose the folder…"]
    start = _fn(SETUP, "function startSection(ctx) {")
    assert 'optionCards({ label: "Where the team’s shared work is kept"' in start and 'kind: "main", id: "team-start-go"' in start
    assert start.count("button(") == 1
    assert 'if (w === "folder") folderDialog(ctx); else setupDialog(ctx, w);' in start
    # what will be kept there is said under the button, and a folder is not said to be locked
    assert "aiWhere(holds, \"folder\")" in start
    folder = where[where.index('value: "folder"'):]
    assert "locked" not in folder and "Your project’s database stays on this computer." in folder


def test_joining_says_where_the_teams_project_goes():
    join = _fn(SETUP, "function joinSection(ctx) {")
    assert '"Join with an invite link…"' in join and "joinDialog(ctx)" in join and "margin://join#" in join
    assert '"Choose the shared folder…"' in join and "folderDialog(ctx, { joining: true })" in join
    dlg = _fn(SPACE, "export async function joinDialog(ctx) {")
    assert "let newProject = true;" in dlg                     # the usual answer, as the invite's own message says
    assert 'title: "A new project", tag: "Usual"' in dlg and "title: `This project (${ctx.project})`" in dlg
    assert 'onPick: (v) => { newProject = v === "new"; }' in dlg
    assert 'api("POST", "/api/join-team"' in dlg and "`${S(ctx.project)}/join`" in dlg
    # from the project menu (no project in hand) nothing is asked: it is a new project
    assert "const into = ctx ? optionCards(" in dlg


def test_the_set_up_is_one_step_at_a_time():
    steps = _fn(SPACE, "function serviceSteps(service, L) {")
    b2 = steps[:steps.index('if (service === "r2")')]
    assert re.findall(r'\{ title: "([^"]+)"', b2) == ["Make a free Backblaze account", "Make a key for Margin", "Paste the key here",
                                                    "Afterwards: cancel the key you pasted"]
    # a new master key stops the one before it: said at the step that makes one
    assert "A new master key stops the one before it working." in b2
    # what cannot be undone is a notice, not a clause in a sentence
    assert 'notice({ kind: "attention", role: "note" }, h("p", {}, "On the sign-up form, choose ", h("strong", {}, "EU Central")' in b2
    assert "It cannot be changed afterwards." in b2
    assert 'title: "Paste the key here", next: false' in b2 and "back: false" in b2
    r2 = steps[steps.index('if (service === "r2")'):steps.index("const address = input(")]
    assert re.findall(r'\{ title: "([^"]+)"', r2) == ["Make a Cloudflare account", "Switch on R2 storage", "Make a token and paste it here"]
    dav = steps[steps.index("const address = input("):]
    assert re.findall(r'\{ title: "([^"]+)"', dav) == ["Find your drive’s WebDAV address", "Make an app password for Margin"]
    assert "Never use your main password here." in dav
    dlg = _fn(SPACE, "export async function setupDialog(ctx, service, { move = false } = {}) {")
    assert "const way = guidedSteps({" in dlg and "who.el ? { title: \"Your name\", body: [who.el] } : null" in dlg
    # the main button waits for the step that asks, says what is missing and opens that step
    assert "if (b && !ready) hold(b, i < paste);" in dlg and "if (b) hold(b, way.at() < paste);" in dlg
    assert 'const WAITS = "Waits for the last step: go through the steps above first.";' in dlg     # and says why it waits
    # a slip of the hand does not lose the place: Escape or a click beside the dialog asks once something is begun,
    # and the step (never what was typed) is remembered for the window
    assert "onDismiss: async () => !begun() || (await confirmDialog({ title: \"Stop the set-up?\"" in dlg
    assert "const begun = () => !ready && (way.at() > first || Object.values(svc.read()).some(Boolean) || " in dlg
    assert "session(stepKey, i >= first ? i - first : null);" in dlg and dlg.count("session(stepKey, null);") == 2
    assert 'if (asking || (lock && lock.on)) return;' in LIB and 'dlg.addEventListener("cancel", (e) => { e.preventDefault(); dismiss(); });' in LIB
    assert "if (lacks) { err.textContent = lacks; way.go(" in dlg
    # Backblaze: once the space is ready the last step says what is left to do there, and the button says Done
    assert 'way.go(afterAt);' in dlg and 'btn.textContent = "Done";' in dlg and "if (ready) return true;" in dlg
    assert "!warnings.some((w) => /master key/.test(w))" in dlg      # not when Margin had to keep the pasted key
    assert "`Set up a storage space ${where}`" in dlg and "`Move the team to a storage space ${where}`" in dlg


def test_guided_steps_is_a_component():
    fn = _fn(LIB, "export function guidedSteps(opts = {}) {")
    assert 'const state = i < at ? "done" : i === at ? "current" : "todo";' in fn and "x.li.dataset.state = state;" in fn
    assert 'x.li.setAttribute("aria-current", "step")' in fn and "x.body.hidden = i !== at;" in fn
    assert "`Step ${i + 1} of ${parts.length}${state === \"done\" ? \", done\" : \"\"}: `" in fn
    assert "s.next !== false" in fn and "s.back !== false" in fn and 's.next || "Next step"' in fn
    # moving on puts the focus where the eyes are; a closed step's fields stay in the page for the form to read
    assert '.querySelector("input:not([type=hidden]), textarea, select") || parts[at].title).focus()' in fn
    sec = CSS[CSS.index("/* ==== 4.28 Guided steps */"):CSS.index("/* ==== 5.1 The sidebar */")]
    for rule in (".guided-step[data-state=\"current\"] .guided-step-mark", ".guided-step[data-state=\"todo\"] .guided-step-title",
                 ".guided-step-body[hidden] { display: none; }"):
        assert rule in sec, rule
    # its name and classes are its own: the progress panel's steps (4.21) are another thing
    assert not re.search(r"(?<![\w-])\.step(?![\w-])", sec)


# ---- the steps, run: lib.js builds the DOM, so Node runs it with the stand-in document of tests/_fakedom.py
PROBE = r"""
const { guidedSteps, h } = await import(LIB);
const moves = [];
const el = guidedSteps({ label: "Setting up", onStep: (i) => moves.push(i), steps: [
  { title: "Make an account", next: "I have an account", body: [h("p", {}, "one")] },
  { title: "Make a key", body: [h("p", {}, "two")] },
  { title: "Paste the key", next: false, body: [h("p", {}, "three")] },
  { title: "Afterwards", back: false, body: [h("p", {}, "four")] }] });
const items = () => el.children;
const state = () => items().map((li) => li.dataset.state);
const body = (li) => li.children[1].children[1];
const buttons = (li) => { const b = body(li); const row = b.children[b.children.length - 1]; return row && row.className.includes("guided-step-move") ? row.children.map((x) => x.textContent) : []; };
const press = (li, words) => { const b = body(li); b.children[b.children.length - 1].children.find((x) => x.textContent === words).click(); };
const out = { label: el.getAttribute("aria-label"), count: el.count };
out.start = { state: state(), open: items().map((li) => !body(li).hidden), buttons: items().map(buttons), current: items().map((li) => li.getAttribute("aria-current")) };
out.said = items().map((li) => li.children[1].children[0].textContent);
press(items()[0], "I have an account");
out.second = { state: state(), at: el.at(), focusOnTitle: document.activeElement === items()[1].children[1].children[0], mark: items()[0].children[0].textContent, said: items()[0].children[1].children[0].textContent };
press(items()[1], "Back");
out.back = el.at();
el.go(3);
out.last = { state: state(), at: el.at(), open: items().map((li) => !body(li).hidden) };
el.go(99); out.clamped = el.at();
out.moves = moves;
console.log(JSON.stringify(out));
"""


def test_the_steps_walk_one_at_a_time(tmp_path):
    import pytest

    from _fakedom import NODE, run
    if not NODE:
        pytest.skip("node is not installed")
    out = run(PROBE, tmp_path)
    assert out["label"] == "Setting up" and out["count"] == 4
    assert out["start"]["state"] == ["current", "todo", "todo", "todo"] and out["start"]["open"] == [True, False, False, False]
    assert out["start"]["current"] == ["step", None, None, None]
    # each open step goes on in its own words; the step the main button ends has no Next; the step after has no Back
    assert out["start"]["buttons"] == [["I have an account"], ["Next step", "Back"], ["Back"], []]
    assert out["said"] == ["Step 1 of 4: Make an account", "Step 2 of 4: Make a key", "Step 3 of 4: Paste the key", "Step 4 of 4: Afterwards"]
    assert out["second"]["state"] == ["done", "current", "todo", "todo"] and out["second"]["at"] == 1
    assert out["second"]["focusOnTitle"] is True and out["second"]["said"] == "Step 1 of 4, done: Make an account"
    assert out["second"]["mark"] == ""          # a tick (an icon), no number
    assert out["back"] == 0
    assert out["last"]["state"] == ["done", "done", "done", "current"] and out["last"]["open"] == [False, False, False, True]
    assert out["clamped"] == 3 and out["moves"] == [1, 0, 3, 3]
