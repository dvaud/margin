"""The Team page run in Node with tests/_views.py (0.19.7): its set-up without a team, joining, the step-by-step
storage-space dialog, and the two views of a team (views/team.js, team-setup.js, team-space.js, team-entry.js).
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const FOLDER = "/api/projects/Study/shared-folder";
// the Team page's reads; `status` is GET …/shared-folder
function team(t, status, o = {}) {
  t.state({ settings: { your_name: "Anna" } });
  t.answer(`GET ${FOLDER}`, status);
  t.answer("GET /api/projects/Study/sharing", { items: [] });
  t.answer("GET /api/projects/Study/together", { history: [] });
  t.answer("GET /api/projects/Study/sync-poller", t.fail(404, "no poller"));
  t.answer("GET /api/projects/Study/owner", { owner: null, people: [] });
  // team codebooks (after 0.19.10): the Codebooks card of People and settings asks for the owner's two settings
  t.answer("GET /api/projects/Study/owner/codebooks", { team: true, can_set: false,
    share_codebooks: { on: false, set: false, by: null, at: null }, default: null, choices: [], private_mine: [] });
  t.answer("GET /api/cloud-folders", { folders: [{ name: "OneDrive", path: "/Users/anna/OneDrive" }], picker: false });
  t.answer(`GET ${FOLDER}/find`, { found: o.found || [] });
  t.answer("GET /api/space/links", { b2_signup: "https://example.org/b2" });
}
const headings = (t) => t.view.querySelectorAll(".team-h, h2.team-h, .team-section > h2, .team-section > h3").map((x) => t.text(x));
const NO_TEAM = { folder: null, space: null, me: { name: "Anna" } };
const step = (t) => { const s = t.dialog().querySelector(".guided-step[data-state='current'] .guided-step-title"); return s ? t.text(s) : null; };
const main = (t) => { const b = t.dialog().querySelector("#dlg-confirm"); return { disabled: b.disabled, title: b.getAttribute("title") }; };

await scenario("no team", async (t) => {
  team(t, NO_TEAM, { found: ["/Users/anna/OneDrive/Study"] });
  await t.render("views/team.js", "renderTeam", [], {});
  await t.settle();
  const cards = t.view.querySelectorAll("#team-where [role=radio]").map((c) => ({ title: t.text(c.querySelector(".option-card-title")), on: c.getAttribute("aria-checked") }));
  const go1 = t.text(t.view.querySelector("#team-start-go"));
  await t.click(t.view.querySelectorAll("#team-where [role=radio]")[1]);
  return { headings: headings(t), cards, go1, go2: t.text(t.view.querySelector("#team-start-go")),
    found: t.text(t.view.querySelector(".team-sec-found")), tabs: t.find("Activity") !== null,
    downloads: t.text(t.view.querySelector(".team-sec-downloads")) };
});

await scenario("no team, no colleague's folder", async (t) => {
  team(t, NO_TEAM);
  await t.render("views/team.js", "renderTeam", [], {});
  return headings(t);
});

await scenario("join into this project", async (t) => {
  team(t, NO_TEAM);
  t.answer("POST /api/space/peek", { service: "b2" });
  t.answer("POST /api/projects/Study/space/join", { ok: true });
  t.answer(`POST ${FOLDER}/sync`, { job: null });
  await t.render("views/team.js", "renderTeam", [], {});
  await t.click("Join with an invite link…");
  const d = t.dialog();
  const where = d.querySelectorAll("#space-join-where [role=radio]").map((c) => [t.text(c.querySelector(".option-card-title")), c.getAttribute("aria-checked")]);
  const focus = t.focused();
  await t.type("The invite link your colleague sent", "margin://join#abc", { wait: 100 });
  await t.click(d.querySelectorAll("#space-join-where [role=radio]")[1]);
  await t.click("Join", { within: d });
  return { title: t.text(d.querySelector("h2")), where, focus,
    posts: t.calls.filter((c) => c.method === "POST").map((c) => [c.path, c.body]), open: t.dialogs().length, navs: t.navs };
});

await scenario("join as a new project", async (t) => {
  team(t, NO_TEAM);
  t.answer("POST /api/space/peek", { service: "b2" });
  t.answer("POST /api/join-team", { project: "Team study" });
  await t.render("views/team.js", "renderTeam", [], {});
  await t.click("Join with an invite link…");
  const d = t.dialog();
  await t.click("Join", { within: d });
  const empty = t.text(d.querySelector(".field-error"));
  await t.type("The invite link your colleague sent", "margin://join#abc", { wait: 100 });
  await t.click("Join", { within: d });
  return { empty, joins: t.calls.filter((c) => c.path === "/api/join-team").map((c) => c.body), navs: t.navs, toasts: t.toasts() };
});

await scenario("set-up, one step at a time", async (t) => {
  team(t, NO_TEAM);
  await t.render("views/team.js", "renderTeam", [], {});
  await t.click("Set up at Backblaze…");
  const d = t.dialog();
  const out = { title: t.text(d.querySelector("h2")), steps: d.querySelectorAll(".guided-step-title").map((x) => t.text(x)) };
  out.s1 = { step: step(t), main: main(t), focus: t.focused(), shown: t.text(d.querySelector(".guided-steps")) };
  await t.click("I have an account", { within: d });
  out.s2 = { step: step(t), main: main(t), back: t.find("Back", { within: d }) !== null };
  await t.click("I see the key", { within: d });
  out.s3 = { step: step(t), main: main(t), focus: t.focused() };
  await t.click("Set up the storage space", { within: d });
  out.missing = t.text(d.querySelector(".field-error"));
  return out;
});

await scenario("set-up, Escape before anything is done", async (t) => {
  team(t, NO_TEAM);
  await t.render("views/team.js", "renderTeam", [], {});
  await t.click("Set up at Backblaze…");
  await t.press("Escape");
  return { open: t.dialogs().map((d) => t.text(d.querySelector("h2"))) };
});

await scenario("set-up, Escape once begun, and back again", async (t) => {
  team(t, NO_TEAM);
  await t.render("views/team.js", "renderTeam", [], {});
  await t.click("Set up at Backblaze…");
  let d = t.dialog();
  await t.click("I have an account", { within: d });
  await t.click("I see the key", { within: d });
  await t.type("keyID", "K001");
  await t.type("applicationKey", "SECRET-app-key");
  await t.press("Escape");
  const asked = t.dialogs().map((x) => t.text(x.querySelector("h2")));
  await t.click("Cancel", { within: t.dialog() });
  const kept = t.dialogs().map((x) => t.text(x.querySelector("h2")));
  const stillTyped = t.field("applicationKey").value;
  await t.press("Escape");
  await t.click("Stop the set-up", { within: t.dialog() });
  const closed = t.dialogs().length;
  await t.click("Set up at Backblaze…");
  d = t.dialog();
  return { asked, kept, stillTyped, closed, again: step(t), main: main(t),
    key: t.field("keyID").value, secret: t.field("applicationKey").value, noSecret: !t.allText(d).includes("SECRET") };
});

await scenario("activity, the only one", async (t) => {
  team(t, { folder: "/space/x", me: { name: "Anna" }, people: [],
    space: { service: "b2", keeper: true, where: "b2://bucket", members: [{ name: "Anna", me: true, part: "p1", person: "a" }], invites: [] } });
  await t.render("views/team.js", "renderTeam", [], {});
  return { tabs: t.view.querySelectorAll("[role=tab], .view-tabs a, .settings-tabs a").map((x) => [t.text(x), x.getAttribute("aria-current") || x.getAttribute("aria-selected")]),
    headings: headings(t), invite: t.buttons(t.view.querySelector(".team-sec-first-invite")) };
});

await scenario("activity, with a colleague", async (t) => {
  team(t, { folder: "/space/x", me: { name: "Anna" }, people: [{ name: "Ben", id: "b" }],
    space: { service: "b2", keeper: true, where: "b2://bucket", invites: [],
      members: [{ name: "Anna", me: true, part: "p1", person: "a" }, { name: "Ben", part: "p2", person: "b" }] } });
  await t.render("views/team.js", "renderTeam", [], {});
  return { headings: headings(t), summary: t.text(t.view.querySelector(".team-summary")) };
});

await scenario("people and settings", async (t) => {
  team(t, { folder: "/space/x", me: { name: "Anna" }, people: [{ name: "Ben", id: "b" }],
    space: { service: "b2", keeper: true, where: "b2://bucket", invites: [],
      members: [{ name: "Anna", me: true, part: "p1", person: "a" }, { name: "Ben", part: "p2", person: "b" }] } });
  await t.render("views/team.js", "renderTeam", ["settings"], {});
  return { headings: headings(t), people: t.text(t.view.querySelector(".team-sec-people")) };
});

await scenario("the sidebar's Team entry", async (t) => {
  const m = await t.module("views/team-entry.js");
  const a = document.createElement("a"); a.id = "team-entry"; a.setAttribute("aria-current", "page"); a.textContent = "Team";
  document.body.appendChild(a);
  m.initTeamEntry();
  const read = () => { const e = document.getElementById("team-entry"); return [t.text(e), e.getAttribute("aria-label"), e.getAttribute("data-kind")]; };
  const send = (type, detail) => window.dispatchEvent(new CustomEvent(type, { detail }));
  const out = { before: read(), current: document.getElementById("team-entry").getAttribute("aria-current") };
  send("margin-sync-state", { project: "Study", folder: "/x", state: "idle", came_in: { count: 3 } });
  out.news = read();
  send("margin-sync-state", { project: "Other", folder: "/y", state: "offline" });
  out.otherProject = read();
  send("margin-sync-state", { project: "Study", folder: "/x", state: "offline", came_in: { count: 3 } });
  out.offline = read();
  send("margin-sync-state", { project: "Study", folder: "/x", state: "idle", came_in: { count: 0 } });
  m.setTeamPageCount(5);
  out.pageCount = read();
  m.setTeamPageCount(null);
  out.pageClosed = read();
  m.teamFoundOnPage("Study", false);
  out.left = read();
  return out;
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("team"))


@needs_node
def test_without_a_team_the_page_offers_a_colleagues_folder_first_then_start_join_and_a_file(page):
    p = page["no team"]
    assert p["headings"] == ["Your colleague’s shared folder is on this computer", "Start a team for this project",
                             "Join a colleague’s team", "Send it once, as a file"]
    assert "Study" in p["found"] and "Use this folder…" in p["found"]
    assert p["tabs"] is False                                # no view tabs before there is a team


@needs_node
def test_the_four_places_for_the_shared_work_are_choices_and_the_button_says_what_it_starts(page):
    p = page["no team"]
    assert [c["title"] for c in p["cards"]] == ["A storage space at Backblaze", "Your institution’s drive",
                                                "A storage space at Cloudflare", "A folder you already share"]
    assert [c["on"] for c in p["cards"]] == ["true", "false", "false", "false"]
    assert p["go1"] == "Set up at Backblaze…"
    assert p["go2"] == "Set up in your institution’s drive…"


@needs_node
def test_without_a_colleagues_folder_on_this_computer_the_page_starts_with_start_a_team(page):
    assert page["no team, no colleague's folder"][0] == "Start a team for this project"


@needs_node
def test_joining_asks_a_new_project_or_this_one_and_this_one_joins_here(page):
    j = page["join into this project"]
    assert j["title"] == "Join a team"
    assert j["where"] == [["A new project", "true"], ["This project (Study)", "false"]]
    assert j["focus"]["label"].startswith("The invite link your colleague sent")
    paths = [p for p, _ in j["posts"]]
    assert "/api/projects/Study/space/join" in paths and "/api/join-team" not in paths
    assert dict(j["posts"])["/api/projects/Study/space/join"]["link"] == "margin://join#abc"
    assert paths[-1] == "/api/projects/Study/shared-folder/sync"        # the first round starts
    assert j["open"] == 0 and j["navs"] == []


@needs_node
def test_joining_as_a_new_project_needs_the_link_then_makes_the_project_and_opens_its_overview(page):
    j = page["join as a new project"]
    assert j["empty"] == "Paste the invite link first."
    assert j["joins"] == [{"link": "margin://join#abc"}]
    assert j["navs"] == ["#/overview"]
    assert any("“Team study” fills in with the next rounds" in x for x in j["toasts"])


@needs_node
def test_the_set_up_shows_the_whole_way_and_opens_one_step_at_a_time(page):
    s = page["set-up, one step at a time"]
    assert s["title"] == "Set up a storage space at Backblaze"
    assert [x.split(": ", 1)[1] for x in s["steps"]] == ["Make a free Backblaze account", "Make a key for Margin",
                                                         "Paste the key here", "Afterwards: cancel the key you pasted"]
    assert s["s1"]["step"].startswith("Step 1 of 4: ")
    assert "EU Central" in s["s1"]["shown"] and "Generate New Master" not in s["s1"]["shown"]   # only step 1 is open
    assert s["s2"]["step"].startswith("Step 2 of 4: ") and s["s2"]["back"] is True
    assert s["s3"]["step"].startswith("Step 3 of 4: ")
    assert s["s3"]["focus"]["label"] == "keyID"                 # the opened step's first field


@needs_node
def test_the_set_ups_main_button_waits_until_the_last_step_that_asks_for_something(page):
    s = page["set-up, one step at a time"]
    waits = "Waits for the last step: go through the steps above first."
    assert s["s1"]["main"] == {"disabled": True, "title": waits}
    assert s["s2"]["main"] == {"disabled": True, "title": waits}
    assert s["s3"]["main"] == {"disabled": False, "title": None}
    assert s["missing"] == "Paste both the keyID and the applicationKey."


@needs_node
def test_escape_closes_a_set_up_not_yet_begun_without_asking(page):
    assert page["set-up, Escape before anything is done"]["open"] == []


@needs_node
def test_escape_asks_before_closing_a_begun_set_up_and_cancel_keeps_it(page):
    s = page["set-up, Escape once begun, and back again"]
    assert s["asked"] == ["Set up a storage space at Backblaze", "Stop the set-up?"]
    assert s["kept"] == ["Set up a storage space at Backblaze"]
    assert s["stillTyped"] == "SECRET-app-key" and s["closed"] == 0


@needs_node
def test_the_set_up_opens_again_at_the_step_left_and_never_with_the_pasted_key(page):
    s = page["set-up, Escape once begun, and back again"]
    assert s["again"].startswith("Step 3 of 4: ") and s["again"].endswith("Paste the key here")
    assert s["main"]["disabled"] is False
    assert s["key"] == "" and s["secret"] == "" and s["noSecret"] is True


@needs_node
def test_a_team_has_activity_and_people_and_settings_and_the_invite_card_while_you_are_alone(page):
    a = page["activity, the only one"]
    assert [x[0] for x in a["tabs"]] == ["Activity", "People and settings"]
    assert a["headings"][0] == "Invite a colleague" and "Sync" in a["headings"]
    assert a["invite"] == [{"label": "Invite a colleague…", "disabled": False}]


@needs_node
def test_with_a_colleague_the_invite_card_is_gone_and_the_team_is_summed_up(page):
    a = page["activity, with a colleague"]
    assert "Invite a colleague" not in a["headings"]
    assert a["summary"].startswith("Backblaze · 2 people")


@needs_node
def test_people_and_settings_lists_the_people(page):
    p = page["people and settings"]
    assert p["headings"][0].startswith("People")
    assert "Anna (you)" in p["people"] and "Ben" in p["people"]


@needs_node
def test_the_sidebars_team_entry_says_the_teams_state_and_the_open_pages_count(page):
    e = page["the sidebar's Team entry"]
    assert e["before"] == ["Team", "Team", "none"] and e["current"] == "page"
    assert e["news"] == ["Team 3 new", "Team, 3 new", "ok"]
    assert e["otherProject"] == e["news"]                      # another project's state is not this one's
    assert e["offline"] == ["Team offline", "Team, offline", "attention"]
    assert e["pageCount"] == ["Team 5 new", "Team, 5 new", "ok"]    # the Team page's own count, while it is open
    assert e["pageClosed"] == ["Team no round yet", "Team, no round yet", "ok"]   # the poller's count again: none
    assert e["left"] == ["Team", "Team", "none"]                # the page found no team: nothing more is said
