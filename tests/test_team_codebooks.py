"""Team codebooks (teamcodebooks.py): the owner's two settings about codebooks.

- *Codebooks made in this project are shared with the team*: on by default in a team project; a codebook made then is
  shared at once by its maker's copy, with the reason in the research log; codebooks made before stay private (and are
  offered); turned off, nothing is taken back and new ones are private again;
- *Default codebook for this project*: takes the place of the computer's setting in `frameworks.chosen`; a codebook
  missing in a copy falls back to the computer's setting, then the SDG targets;
- only the owner sets them; they reach a member's copy through a merge; a member's own rows count for nothing, and a
  row forged in the owner's name is refused by the owner's copy and answered, so the member's copy follows the owner
  again.

Two people exchanging zips of a small text project (no shared folder): light on the disk.
"""
from __future__ import annotations

import json

import pytest

from margin import codebooks, frameworks, ownership, sharing, teamcodebooks
from margin.gui import server
from owner_more_helpers import join_zip, small_project, zips
from test_app import api, home  # noqa: F401  (fixtures)
from test_shared_projects import Person

CSV = "code,description\nA,Alpha\nB,Beta\n"


@pytest.fixture
def team(tmp_path, monkeypatch):
    """Anna's small project, with one codebook she made while she worked alone ("solo"); Ben's copy from her zip;
    Anna has heard of Ben."""
    anna = Person(tmp_path, "Anna", monkeypatch)
    small_project(anna, tmp_path / "anna-project", keys=("desalination", "jobs"))
    with anna:
        assert not teamcodebooks.share_on(anna.ws._conn())  # alone: not a team project yet
        codebooks.create(anna.ws, "solo", "Made alone")
    ben = Person(tmp_path, "Ben", monkeypatch)
    join_zip(ben, anna, tmp_path / "ben-project")
    zips(ben, anna)
    return anna, ben


def _state(p: Person, name: str) -> dict:
    with p:
        return sharing.state(p.ws._conn(), "codebook", name, p.id)


def _log(p: Person, kind: str) -> list[dict]:
    with p:
        return [dict(r) for r in p.ws.query("SELECT kind, subject_id, text, why, person_id FROM research_log WHERE "
                                            "kind=? ORDER BY at", (kind,))]


def _counting(p: Person) -> dict:
    with p:
        return teamcodebooks._counting(p.ws._conn())


def test_on_by_default_in_a_team_and_a_new_codebook_is_shared_at_once_with_its_reason(team):
    anna, ben = team
    for p in (anna, ben):
        with p:
            assert teamcodebooks.share_on(p.ws._conn())
            assert teamcodebooks.view(p.ws)["share_codebooks"] == {"on": True, "set": False, "by": None, "at": None}
    with ben:  # a Member's codebook too: shared by the maker's own copy
        codebooks.create(ben.ws, "energy", "Energy transitions")
    st = _state(ben, "energy")
    assert st["state"] == "shared" and st["owner"] == ben.id and st["by"] == ben.id
    entry = [e for e in _log(ben, "shared") if e["subject_id"] == "energy"]
    assert len(entry) == 1 and entry[0]["why"] == teamcodebooks.WHY_SETTING and entry[0]["person_id"] == ben.id
    # every way a project codebook is made: from a CSV file, through the older framework route
    with anna:
        codebooks.create(anna.ws, "fromcsv", "From a file", start="csv", source={"csv": CSV})
        frameworks.save(anna.ws, "oldroute", CSV, title="Older route")
        frameworks.save(anna.ws, "oldroute", CSV, title="Older route, again")  # replaced, not made: shared once
    assert _state(anna, "fromcsv")["state"] == "shared" and _state(anna, "oldroute")["state"] == "shared"
    assert len([e for e in _log(anna, "shared") if e["subject_id"] == "oldroute"]) == 1
    # one kept with all projects is not covered, and this project's copy of it is (made here)
    with anna:
        codebooks.create(anna.ws, "everywhere", "For all projects", where="home")
    assert _state(anna, "everywhere")["state"] == "private"
    with anna:
        codebooks.copy_here(anna.ws, "everywhere")
    assert _state(anna, "everywhere")["state"] == "shared"
    # it reaches Ben with the next file
    zips(anna, ben)
    with ben:
        assert {"fromcsv", "oldroute", "everywhere"} <= set(frameworks.available(ben.ws))


def test_codebooks_made_before_stay_private_and_their_maker_is_offered_to_share_them(team):
    anna, ben = team
    assert _state(anna, "solo")["state"] == "private"
    with anna:
        line = teamcodebooks.codebooks_line(anna.ws)
    assert line["team"] and line["share_codebooks"] and line["private_mine"] == [{"key": "solo", "title": "Made alone"}]
    with ben:  # not Ben's: nothing to offer him
        assert teamcodebooks.codebooks_line(ben.ws)["private_mine"] == []
    with anna:
        sharing.share(anna.ws, [{"kind": "codebook", "key": "solo"}])
        assert teamcodebooks.codebooks_line(anna.ws)["private_mine"] == []


def test_turned_off_nothing_is_taken_back_and_new_codebooks_are_private_again(team):
    anna, ben = team
    with anna:
        codebooks.create(anna.ws, "before", "Before")
        v = teamcodebooks.set_share(anna.ws, False)
        assert v["share_codebooks"]["on"] is False and v["share_codebooks"]["set"]
        codebooks.create(anna.ws, "after", "After")
        assert teamcodebooks.codebooks_line(anna.ws)["private_mine"] == []  # no offer while it is off
    assert _state(anna, "before")["state"] == "shared"
    assert _state(anna, "after")["state"] == "private"
    log = _log(anna, "owner")
    assert any("private again until their maker shares them" in e["text"] for e in log)
    # anyone may still take one of their own back, as before
    with anna:
        sharing.unshare(anna.ws, [{"kind": "codebook", "key": "before"}])
    assert _state(anna, "before")["state"] == "withdrawn"


def test_a_member_cannot_set_either_setting(team):
    anna, ben = team
    with ben:
        with pytest.raises(ownership.NotAllowed):
            teamcodebooks.set_share(ben.ws, False)
        with pytest.raises(ownership.NotAllowed):
            teamcodebooks.set_default(ben.ws, "sdg_goals")
        assert teamcodebooks.view(ben.ws)["can_set"] is False
        assert not ben.ws.query("SELECT 1 FROM team_settings")


def test_the_default_codebook_takes_the_computers_place_and_falls_back_without_an_error(team):
    anna, ben = team
    with anna:
        teamcodebooks.set_share(anna.ws, False)
        codebooks.create(anna.ws, "lens", "The team's lens", start="csv", source={"csv": CSV})
        assert _state(anna, "lens")["state"] == "private"
        assert frameworks.chosen("sdg", anna.ws) == "sdg"
        v = teamcodebooks.set_default(anna.ws, "lens")  # her own private one: shared, so the team has it
    assert v["default"]["name"] == "lens" and v["default"]["here"]
    assert _state(anna, "lens")["state"] == "shared"
    assert [e["why"] for e in _log(anna, "shared") if e["subject_id"] == "lens"] == [teamcodebooks.WHY_DEFAULT]
    with anna:
        assert frameworks.chosen("sdg", anna.ws) == "lens" and frameworks.chosen(None, anna.ws) == "lens"
        assert teamcodebooks.default_info(anna.ws) == {"name": "lens", "title": "The team's lens"}
        assert frameworks.chosen("sdg_goals") == "sdg_goals"  # (no project: the computer's setting)
    with ben:  # not here yet: the computer's setting, then the SDG targets
        assert teamcodebooks.default_name(ben.ws) is None
    zips(anna, ben)
    with ben:
        assert teamcodebooks.default_name(ben.ws) == "lens"
        assert frameworks.chosen("sdg_goals", ben.ws) == "lens"
        assert teamcodebooks.view(ben.ws)["default"]["by"]["id"] == anna.id
        for ext in ("csv", "json"):
            (ben.ws.root / "frameworks" / f"lens.{ext}").unlink(missing_ok=True)
        assert frameworks.chosen("sdg_goals", ben.ws) == "sdg_goals"
        assert frameworks.chosen("nothing_here", ben.ws) == "sdg"
        assert teamcodebooks.default_info(ben.ws) is None
    with anna:  # no default: each computer's own setting again
        teamcodebooks.set_default(anna.ws, None)
        assert frameworks.chosen("sdg_goals", anna.ws) == "sdg_goals"
        with pytest.raises(KeyError):
            teamcodebooks.set_default(anna.ws, "no_such_codebook")
        codebooks.create(anna.ws, "homebook", "Kept with all projects", where="home")
        with pytest.raises(ValueError):
            teamcodebooks.set_default(anna.ws, "homebook")


def test_a_colleagues_private_codebook_cannot_be_the_default(team):
    anna, ben = team
    with anna:
        teamcodebooks.set_share(anna.ws, False)
    zips(anna, ben)
    with ben:
        codebooks.create(ben.ws, "bens", "Ben's own")
    assert _state(ben, "bens")["state"] == "private"
    zips(ben, anna, scope="all")  # Ben's whole project: his private codebook comes, and stays his
    with anna:
        assert "bens" in frameworks.available(anna.ws)
        assert "bens" not in [c["name"] for c in teamcodebooks.view(anna.ws)["choices"]]
        with pytest.raises(ValueError):
            teamcodebooks.set_default(anna.ws, "bens")


def test_the_settings_reach_a_member_through_a_merge(team):
    anna, ben = team
    with anna:
        teamcodebooks.set_share(anna.ws, False)
        teamcodebooks.set_default(anna.ws, "sdg_goals")
    zips(anna, ben)
    with ben:
        assert not teamcodebooks.share_on(ben.ws._conn())
        assert teamcodebooks.default_name(ben.ws) == "sdg_goals"
        assert frameworks.chosen("sdg", ben.ws) == "sdg_goals"
        codebooks.create(ben.ws, "later", "Later")
    assert _state(ben, "later")["state"] == "private"
    # the owner's log entries about the settings travel too
    texts = [e["text"] for e in _log(ben, "owner")]
    assert any("default codebook" in t for t in texts) and any("private again" in t for t in texts)


def test_a_members_own_rows_count_for_nothing_anywhere(team):
    anna, ben = team
    with ben:
        with ben.ws.connect() as cx:  # Ben's copy writes the settings in his own name (a changed app, say)
            teamcodebooks._write(cx, teamcodebooks.SHARE, ben.id, 1, 50, False)
            teamcodebooks._write(cx, teamcodebooks.DEFAULT, ben.id, 1, 51, "sdg_goals")
        assert teamcodebooks._counting(ben.ws._conn()) == {}
        assert teamcodebooks.share_on(ben.ws._conn()) and teamcodebooks.default_name(ben.ws) is None
    zips(ben, anna)
    with anna:
        assert len(anna.ws.query("SELECT 1 FROM team_settings WHERE by=?", (ben.id,))) == 2  # kept, never counted
        assert teamcodebooks.share_on(anna.ws._conn()) and teamcodebooks.default_name(anna.ws) is None
        assert frameworks.chosen("sdg", anna.ws) == "sdg"


def test_a_row_forged_in_the_owners_name_is_refused_and_answered(team):
    anna, ben = team
    with anna:
        teamcodebooks.set_default(anna.ws, "sdg_goals")
    zips(anna, ben)
    with ben:
        with ben.ws.connect() as cx:  # Ben's file says Anna chose no default, with a higher number
            teamcodebooks._write(cx, teamcodebooks.DEFAULT, anna.id, 1, 40, None)
        assert teamcodebooks.default_name(ben.ws) is None  # (his own copy believes it: files are not signed yet)
    zips(ben, anna)
    with anna:
        row = anna.ws.query("SELECT n, value_json FROM team_settings WHERE key=? AND by=?",
                            (teamcodebooks.DEFAULT, anna.id))[0]
        assert json.loads(row["value_json"]) == "sdg_goals" and row["n"] > 40  # not taken, and answered above it
        refused = [r for r in ownership.refused(anna.ws._conn()) if r["kind"] == "team_settings"]
        assert len(refused) == 1 and "in your name" in refused[0]["text"]
        assert teamcodebooks.default_name(anna.ws) == "sdg_goals"
    zips(anna, ben)
    with ben:  # Anna's answer replaces the forged row: Ben's copy follows the owner again
        assert teamcodebooks.default_name(ben.ws) == "sdg_goals"


def test_a_new_owner_writes_the_settings_again_under_their_own_place(team):
    anna, ben = team
    with anna:
        teamcodebooks.set_share(anna.ws, False)
        teamcodebooks.set_default(anna.ws, "sdg_goals")
        ownership.hand_over(anna.ws, ben.id)
    zips(anna, ben)
    with ben:
        ownership.settle(ben.ws)
        cur = teamcodebooks._counting(ben.ws._conn())
        assert {k: (r["by"], r["value"]) for k, r in cur.items()} == {
            teamcodebooks.SHARE: (ben.id, False), teamcodebooks.DEFAULT: (ben.id, "sdg_goals"),
            teamcodebooks.PROVIDERS: (ben.id, None)}   # I7 stage 3: the providers' limit too (none: no limit)
        assert teamcodebooks.view(ben.ws)["can_set"]
    with anna:  # the former owner may no longer set them
        with pytest.raises(ownership.NotAllowed):
            teamcodebooks.set_share(anna.ws, True)


# ---------------------------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------------------------
def test_the_routes_are_there():
    for method in ("GET", "PUT"):
        hits = [n for m, rx, n in server.ROUTES if m == method and rx.match("/api/projects/Demo/owner/codebooks")]
        assert hits == [f"{method.lower()}_owner_codebooks"]


def test_the_owner_sets_both_through_the_api(api):  # noqa: F811
    assert api("POST", "/api/projects", {"name": "Demo"})[0] == 200
    code, v = api("GET", "/api/projects/Demo/owner/codebooks")
    assert code == 200 and v["can_set"] and v["default"] is None
    assert {"sdg", "sdg_goals"} <= {c["name"] for c in v["choices"]}
    assert api("PUT", "/api/projects/Demo/owner/codebooks", {})[0] == 400
    assert api("PUT", "/api/projects/Demo/owner/codebooks", {"share": "yes"})[0] == 400
    assert api("PUT", "/api/projects/Demo/owner/codebooks", {"default": "no_such"})[0] == 404
    code, v = api("PUT", "/api/projects/Demo/owner/codebooks", {"share": False, "default": "sdg_goals"})
    assert code == 200 and v["share_codebooks"]["on"] is False and v["default"]["name"] == "sdg_goals"
    code, state = api("GET", "/api/state")
    assert code == 200
    if state.get("project") == "Demo":
        assert state["profile_framework"] == "sdg_goals"
        assert state["profile_framework_team"] == {"name": "sdg_goals", "title": v["default"]["title"]}
    code, cbs = api("GET", "/api/projects/Demo/codebooks")
    assert code == 200 and cbs["team"] == {"team": False, "share_codebooks": False, "private_mine": []}
