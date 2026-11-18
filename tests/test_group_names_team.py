"""D1, the last part: the names of the concept map's groups travel with a team (groupnames.merge, sync/merge.py).

A kept name holds its group's concepts, who last changed it and when. On another copy it goes to the group there that
holds most of its concepts (the groups are found from each copy's own counts); one that fits no group is kept, not
drawn. One name changed on two copies: a person's decision beats an AI draft, the later of two decisions wins on
every copy, and the other person's words stay as a name of their own. Two names for one group: the later is shown,
the other beside it. A removed name does not come back, unless it was changed after the removal.
"""
from __future__ import annotations

import json

import pytest

from margin import groupnames, people, sharing
from margin.store import Workspace
from margin.sync import common
from test_shared_projects import anna_and_ben  # noqa: F401  (fixture)

ANNA, BEN, CLARA = "p" + "a" * 12, "p" + "b" * 12, "p" + "c" * 12
T1, T2, T3 = "2026-11-01T09:00:00+00:00", "2026-11-01T10:00:00+00:00", "2026-11-01T11:00:00+00:00"


def row(nid, name, source="person", person=ANNA, at=T1, concepts=("a", "b", "c"), by=None, after=()):
    """A kept name; `by`: who changed it last (default its author); `after`: the versions it replaced ("time|person")."""
    return {"name_id": nid, "name": name, "source": source, "model": "claude-haiku-5-5" if source != "person" else None,
            "concepts_json": json.dumps(list(concepts)), "labels_json": json.dumps({c: c.upper() for c in concepts}),
            "filters_json": "{}", "n": 30, "created_at": T1, "updated_at": at, "person_id": person,
            "changed_by": by or person, "history_json": json.dumps(list(after))}


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    w = Workspace.create(tmp_path / "p")
    yield w
    w.close_all()


def put(ws, *rows):
    with ws.connect() as cx:
        for r in rows:
            cx.execute(f"INSERT OR REPLACE INTO concept_group_names({', '.join(groupnames.NAME_COLS)}) VALUES "
                       f"({','.join('?' * len(groupnames.NAME_COLS))})", tuple(r.get(c) for c in groupnames.NAME_COLS))


def merge(ws, names=(), removed=(), quotes=(), sender=ANNA, me=BEN, doc_here=lambda q: q):
    with ws.connect() as cx:
        return groupnames.merge(cx, list(names), list(quotes), list(removed), sender, me, doc_here)


def names(ws) -> dict[str, tuple]:
    return {r["name_id"]: (r["name"], r["source"], r["person_id"]) for r in
            ws.query("SELECT name_id, name, source, person_id FROM concept_group_names")}


def test_the_tables_travel_and_are_merged_by_their_own_rules():
    for t in ("concept_group_names", "concept_group_quotes"):
        assert t not in common.LOCAL_ONLY and t in common.OWN_RULES and t not in sharing._LOCAL_TABLES
    assert groupnames.KIND in sharing.LOCAL_TASK_KINDS          # the AI's tasks still stay where they were run


def test_the_shared_folder_carries_the_names_and_their_removals(proj):
    with proj.connect() as cx:
        where = {t: w for t, w, _c in sharing.ProjectRows(cx, proj.root).tables()}
    assert where["concept_group_names"] == "1" and where["concept_group_quotes"] == "1"
    assert "'group_name'" in where["sync_removed"]


def test_two_people_change_one_name_the_later_wins_on_both_copies_and_the_other_is_kept(proj, tmp_path):
    """Ben's copy has his rename; Anna's later one comes in. Anna's copy has hers; Ben's earlier one comes in. Both end
    with Anna's name for the group and Ben's words as a name of their own, under the same id."""
    put(proj, row("n1", "Hybrid work", person=BEN, at=T1))
    assert merge(proj, [row("n1", "Remote work", person=ANNA, at=T2)], sender=ANNA, me=BEN) == 2
    bens = names(proj)
    other = Workspace.create(tmp_path / "anna")
    put(other, row("n1", "Remote work", person=ANNA, at=T2))
    merge(other, [row("n1", "Hybrid work", person=BEN, at=T1)], sender=BEN, me=ANNA)
    annas = names(other)
    other.close_all()
    assert bens == annas
    assert bens["n1"] == ("Remote work", "person", ANNA)
    (fork,) = [k for k in bens if k != "n1"]
    assert bens[fork] == ("Hybrid work", "person", BEN)
    # the same file again changes nothing
    assert merge(proj, [row("n1", "Remote work", person=ANNA, at=T2)], sender=ANNA, me=BEN) == 0


def test_the_same_time_is_settled_by_the_person_id_on_every_copy(proj):
    put(proj, row("n1", "Hybrid work", person=BEN, at=T2))
    merge(proj, [row("n1", "Remote work", person=CLARA, at=T2)], sender=CLARA, me=BEN)
    assert names(proj)["n1"][0] == "Remote work"            # the larger id: Clara's (pccc… > pbbb…)


@pytest.mark.parametrize("draft_later", [True, False])
def test_a_persons_name_is_shown_before_an_ai_draft_made_at_the_same_time(proj, draft_later):
    """Review 1: two versions of ONE name made apart are settled by the later change, whatever their kind (so every
    copy ends the same); a person's name that lost stays as a name of its own, and the map shows it before the draft."""
    put(proj, row("n1", "Talk of solar", source="ai_draft", person=BEN, at=T3 if draft_later else T1))
    merge(proj, [row("n1", "Solar parks", person=ANNA, at=T2)])
    got = names(proj)
    if draft_later:
        assert got["n1"] == ("Talk of solar", "ai_draft", BEN) and ("Solar parks", "person", ANNA) in got.values()
    else:
        assert got == {"n1": ("Solar parks", "person", ANNA)}       # a draft that lost is not kept beside it
    g = _attach(proj, [["a", "b", "c"], ["x", "y"]])["groups"][0]
    assert (g["name"], g["name_source"]) == ("Solar parks", "person")


def test_back_to_a_draft_reaches_every_copy(proj, tmp_path):
    """Review 1: Anna used the AI's draft (ai), Ben has it; Anna puts it back to a draft (later, after the used one).
    Ben's copy takes the draft, and Ben's file, which still holds the used name in Anna's name, changes nothing at
    Anna's: both show the draft."""
    used = row("n1", "Talk of solar", source="ai", person=ANNA, at=T1)
    put(proj, used)                                                # Ben's copy
    draft = row("n1", "Talk of solar", source="ai_draft", person=ANNA, at=T2, after=[f"{T1}|{ANNA}"])
    merge(proj, [draft], sender=ANNA, me=BEN)
    assert names(proj)["n1"][1] == "ai_draft"
    annas = Workspace.create(tmp_path / "anna")
    put(annas, draft)
    merge(annas, [used], sender=BEN, me=ANNA)
    assert names(annas)["n1"][1] == "ai_draft"
    annas.close_all()


def test_a_rename_of_a_colleagues_name_replaces_it_without_a_copy(proj):
    """Review 5: Ben renamed Anna's name after seeing it (her version is in his history): it replaces hers on every
    copy that holds it, and no "Also named" copy is left; a copy that holds a version neither knows keeps it apart."""
    put(proj, row("n1", "Remote work", person=ANNA, at=T1))           # Clara's copy holds Anna's version
    merge(proj, [row("n1", "Hybrid work", person=BEN, at=T2, after=[f"{T1}|{ANNA}"])], sender=BEN, me=CLARA)
    assert names(proj) == {"n1": ("Hybrid work", "person", BEN)}
    # Anna's version again (from a file that still has it): already replaced here
    merge(proj, [row("n1", "Remote work", person=ANNA, at=T1)], sender=ANNA, me=CLARA)
    assert names(proj) == {"n1": ("Hybrid work", "person", BEN)}
    # a chain: two renames after it, the copy holding the first sees both in the history
    put(proj, row("n2", "One", person=ANNA, at=T1))
    merge(proj, [row("n2", "Three", person=BEN, at=T3, after=[f"{T1}|{ANNA}", f"{T2}|{ANNA}"])], sender=BEN, me=CLARA)
    assert names(proj)["n2"] == ("Three", "person", BEN) and len(names(proj)) == 2


def test_an_ai_name_used_by_a_person_counts_as_their_decision(proj):
    put(proj, row("n1", "Talk of solar", source="ai", person=BEN, at=T1))
    merge(proj, [row("n1", "Solar parks", person=ANNA, at=T2)])
    got = names(proj)
    assert got["n1"] == ("Solar parks", "person", ANNA)
    assert ("Talk of solar", "ai", BEN) in got.values()


def test_a_removed_name_stays_removed_unless_changed_after(proj):
    put(proj, row("n1", "Old name", person=BEN, at=T1))
    with proj.connect() as cx:
        cx.execute("DELETE FROM concept_group_names")
        groupnames._note_removed(cx, "n1", "Old name", T2, BEN)
    merge(proj, [row("n1", "Old name", person=ANNA, at=T1)])
    assert names(proj) == {}
    merge(proj, [row("n1", "Renamed since", person=ANNA, at=T3)])      # renamed after the removal: it counts
    assert names(proj) == {"n1": ("Renamed since", "person", ANNA)}
    # a removal that comes in: a name changed here before it goes, one changed after it stays
    put(proj, row("n2", "Gone", person=BEN, at=T1), row("n3", "Kept", person=BEN, at=T3))
    merge(proj, removed=[{"kind": "group_name", "key": k, "title": "x", "at": T2, "person_id": ANNA} for k in ("n2", "n3")])
    assert set(names(proj)) == {"n1", "n3"}
    assert proj.scalar("SELECT COUNT(*) FROM sync_removed WHERE kind='group_name' AND key IN ('n2', 'n3')") == 2


def test_a_name_in_your_own_name_from_someone_elses_file_is_not_taken(proj):
    merge(proj, [row("n1", "Mine?", person=BEN, at=T3)], sender=ANNA, me=BEN)
    assert names(proj) == {}
    # what counts is who changed it last: Anna kept Ben's name (still his), so it comes in
    merge(proj, [row("n2", "His, kept by her", person=BEN, by=ANNA, at=T3)], sender=ANNA, me=BEN)
    assert names(proj) == {"n2": ("His, kept by her", "person", BEN)}


@pytest.mark.parametrize("bad", [
    {"concepts_json": "5"}, {"concepts_json": "[]"}, {"concepts_json": "not json"}, {"concepts_json": "[1, 2]"},
    {"labels_json": "[]"}, {"labels_json": "{bad"}, {"filters_json": "7"}, {"name": ""}, {"name": 5},
    {"source": "boss"}, {"person_id": "anna"}, {"changed_by": "x" * 13}, {"updated_at": "yesterday"},
    {"updated_at": "9999-01-01T00:00:00+00:00"}, {"name_id": "../x"}, {"name_id": None}])
def test_a_crafted_row_is_left_out_and_the_map_still_draws(proj, bad):
    """Review 4: every incoming row is checked; one Margin could not have written, or dated far ahead, stays out."""
    assert merge(proj, [{**row("n1", "Broken", at=T2), **bad}]) == 0
    assert names(proj) == {}
    _attach(proj, [["a", "b", "c"]])


def test_what_comes_in_is_cut_to_size_and_a_broken_stored_row_does_not_break_the_map(proj):
    merge(proj, [{**row("n1", "x" * 500, at=T2), "n": "lots", "model": 7,
                  "labels_json": json.dumps({"a": "y" * 900, "zz": "not a concept of it"})}])
    r = proj.query("SELECT * FROM concept_group_names")[0]
    assert len(r["name"]) == groupnames.MAX_NAME and r["n"] == 0 and r["model"] is None
    assert json.loads(r["labels_json"]) == {"a": "y" * 200}
    put(proj, {**row("n2", "Bad", at=T2), "concepts_json": "5"}, {**row("n3", "Bad too", at=T2), "labels_json": "[]"})
    out = _attach(proj, [["a", "b", "c"]])                          # no exception, the good name is used
    assert out["groups"][0]["name"] == "x" * groupnames.MAX_NAME


def test_a_name_dated_ahead_waits_and_a_change_made_after_seeing_it_is_later(proj):
    """Review 3: a fast clock or a crafted date does not win for ever: more than ten minutes ahead, it waits; within
    them it comes in, and a change made here afterwards is dated after it (the clock moves past what it has seen)."""
    from margin.store import now

    soon = groupnames._plus(now(), 300)
    far = groupnames._plus(now(), groupnames.FUTURE + 120)
    merge(proj, [row("n1", "Ahead", at=far)])
    assert names(proj) == {}
    merge(proj, [row("n1", "Ahead", at=soon)])
    assert names(proj)["n1"][0] == "Ahead"
    groupnames.save(proj, "rename", {"name_id": "n1", "name": "Mine now", "concepts": ["a", "b", "c"], "labels": {},
                                     "filters": {}, "n": 30})
    r = proj.query("SELECT updated_at, history_json FROM concept_group_names WHERE name_id='n1'")[0]
    assert r["updated_at"] > soon and json.loads(r["history_json"])[-1] == f"{soon}|{ANNA}"
    # a removal dated far ahead waits too
    merge(proj, removed=[{"kind": "group_name", "key": "n1", "title": "x", "at": far, "person_id": ANNA}])
    assert "n1" in names(proj)


def test_undo_keep_and_restore_are_new_changes(proj):
    """Review 2 and 9: Undo of Use this name and the Undo of Forget are changes made now by this person (so every copy,
    the author's too, takes them); Keep the name keeps who gave it."""
    me = people.me()
    put(proj, row("n1", "Talk of solar", source="ai_draft", person=ANNA, at=T1))
    r = groupnames.save(proj, "accept", {"name_id": "n1", "concepts": ["a", "b", "c"], "labels": {}, "filters": {}, "n": 30})
    groupnames.save(proj, "unaccept", {"before": r["before"]})
    got = proj.query("SELECT * FROM concept_group_names WHERE name_id='n1'")[0]
    assert got["source"] == "ai_draft" and got["changed_by"] == me and got["person_id"] == me and got["updated_at"] > T1
    assert len(json.loads(got["history_json"])) == 2               # the draft, then the used name
    put(proj, row("n2", "Anna's", person=ANNA, at=T1))
    groupnames.save(proj, "keep", {"name_id": "n2", "concepts": ["a", "b", "d"], "labels": {}, "filters": {}, "n": 30})
    got = proj.query("SELECT * FROM concept_group_names WHERE name_id='n2'")[0]
    assert (got["person_id"], got["changed_by"]) == (ANNA, me)
    rec = groupnames.save(proj, "forget", {"name_id": "n2"})["record"]
    groupnames.save(proj, "restore", {"record": rec})
    got = proj.query("SELECT * FROM concept_group_names WHERE name_id='n2'")[0]
    assert (got["person_id"], got["changed_by"]) == (ANNA, me) and got["updated_at"] > rec["row"]["updated_at"]
    assert proj.scalar("SELECT COUNT(*) FROM sync_removed WHERE key='n2'") == 0


def test_names_from_before_they_travelled_are_this_persons(proj):
    """Review 6: a name with no person (made before they travelled) is filled with this copy's person, as reviews are."""
    with proj.connect() as cx:
        cx.execute("INSERT INTO concept_group_names(name_id, name, source, concepts_json, labels_json, filters_json, n, "
                   "created_at, updated_at) VALUES ('old', 'Old name', 'person', '[\"a\", \"b\"]', '{}', '{}', 30, ?, ?)",
                   (T1, T1))
        people.adopt(cx, BEN)
    assert proj.query("SELECT person_id, changed_by FROM concept_group_names")[0][:] == (BEN, BEN)


def test_an_ai_names_quote_comes_in_only_for_a_document_here(proj):
    q = {"name_id": "n1", "doc_id": "d1", "passage_id": "d1:0001", "page": 2, "start": 5, "end": 20, "quote": "solar parks need land"}
    merge(proj, [row("n1", "Solar parks", source="ai", at=T2)], quotes=[q], doc_here=lambda x: None)
    assert proj.scalar("SELECT COUNT(*) FROM concept_group_quotes") == 0
    merge(proj, [row("n2", "Land use", source="ai", at=T2)], quotes=[{**q, "name_id": "n2"}])
    assert proj.scalar("SELECT quote FROM concept_group_quotes WHERE name_id='n2'") == "solar parks need land"


# ---- how a copy shows the names: its own groups -------------------------------------------------------------------
def _attach(ws, members, labels=None):
    labels = labels or {c: c.upper() for g in members for c in g}
    out = {"groups": [{"group": i + 1} for i in range(len(members))]}
    groupnames.attach(ws, out, members, labels, {}, 30, None, settings={})
    return out


def test_two_names_for_one_group_the_later_is_shown_and_the_other_beside_it(proj):
    with proj.connect() as cx:
        people.remember(cx, ANNA, "Anna")
        people.remember(cx, CLARA, "Clara")
    put(proj, row("n1", "Hybrid work", person=CLARA, at=T1, concepts=("a", "b", "c")),
        row("n2", "Remote work", person=ANNA, at=T2, concepts=("a", "b", "d")),
        row("n3", "Talk of offices", source="ai_draft", person=ANNA, at=T3, concepts=("a", "b")))
    g = _attach(proj, [["a", "b", "c", "d"], ["e", "f"]])["groups"][0]
    assert (g["name"], g["by"]) == ("Remote work", "Anna")
    assert [(x["name"], x["by"], x["at"]) for x in g["also_named"]] == [("Hybrid work", "Clara", T1)]   # no draft
    assert _attach(proj, [["a", "b", "c", "d"], ["e", "f"]])["names_elsewhere"] == []


def test_a_group_that_differs_between_copies_takes_the_name_whose_concepts_it_mostly_holds(proj):
    put(proj, row("n1", "Energy prices", at=T1, concepts=("a", "b", "c", "d")))
    # this copy found other groups: most of the name's concepts are in its second
    out = _attach(proj, [["x", "d"], ["a", "b", "c", "y"]])
    assert [g["name_source"] for g in out["groups"]] == ["concepts", "person"]
    assert out["groups"][1]["name"] == "Energy prices"
    # split half and half: no group holds most of them; the name is kept, listed apart, not drawn
    out = _attach(proj, [["a", "b", "x"], ["c", "d", "y"]])
    assert [g["name_source"] for g in out["groups"]] == ["concepts", "concepts"]
    assert [x["name"] for x in out["names_elsewhere"]] == ["Energy prices"]


def test_a_name_that_fits_no_group_here_is_kept_and_not_drawn(proj):
    merge(proj, [row("n1", "Water stress", at=T2, concepts=("w", "v"))])
    out = _attach(proj, [["a", "b"], ["c", "d"]])
    assert all(g["name_source"] == "concepts" for g in out["groups"])
    assert [x["name"] for x in out["names_elsewhere"]] == ["Water stress"]
    assert names(proj) == {"n1": ("Water stress", "person", ANNA)}


# ---- through a colleague's file (sync.bring_in) ---------------------------------------------------------------------
def test_a_name_and_its_change_travel_both_ways_through_a_file(anna_and_ben):  # noqa: F811
    anna, ben = anna_and_ben
    cs = ["t1", "t2", "t3"]
    body = lambda name, nid=None: {"name_id": nid, "name": name, "concepts": cs, "labels": {c: c for c in cs},  # noqa: E731
                                   "filters": {}, "n": 30}

    def rows(p):
        with p:
            return {r["name_id"]: (r["name"], r["person_id"]) for r in
                    p.ws.query("SELECT name_id, name, person_id FROM concept_group_names")}

    with anna:
        nid = groupnames.save(anna.ws, "rename", body("Water and arid land"))["record"]["name_id"]
    rep = ben.bring_in(anna.send())
    assert rep["group_names"] == 1 and any("of the concept map" in x for x in rep["lines"])
    assert rows(ben) == {nid: ("Water and arid land", anna.id)}
    # Ben renames it after seeing it: it replaces Anna's at Anna's, with no other copy left
    with ben:
        groupnames.save(ben.ws, "rename", body("Arid regions", nid))
    anna.bring_in(ben.send())
    assert rows(anna) == {nid: ("Arid regions", ben.id)}
    # both rename it, apart: the later change counts on both copies, the other stays as a name of its own
    with anna:
        groupnames.save(anna.ws, "rename", body("Dry land", nid))
    with ben:
        groupnames.save(ben.ws, "rename", body("Desert", nid))
    anna.bring_in(ben.send())
    ben.bring_in(anna.send())
    assert rows(anna) == rows(ben)
    assert sorted(v for v in rows(anna).values()) == sorted([("Dry land", anna.id), ("Desert", ben.id)])
    # Ben forgets the name: the removal travels; the other name stays
    with ben:
        groupnames.save(ben.ws, "forget", {"name_id": nid})
    anna.bring_in(ben.send())
    assert nid not in rows(anna) and len(rows(anna)) == 1
