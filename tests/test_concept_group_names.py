"""D1, the rest: the names of the concept map's groups (groupnames.py).

Every group has a name: made from its two most central concepts (no AI), the researcher's own, or the AI's draft (on
request only, marked until used). A kept name stays with its group when the groups are found again, as long as the
group holds most of the same concepts; under the same filters and size, a group that changed by a third is flagged.
The AI reads only passages of documents it may read; drawing the map asks nothing of it."""
from __future__ import annotations

import json

import pytest

from margin import access, conceptmap, groupnames, ingest, terms, tasks
from margin import home as ehome
from margin.conceptmap import Filters
from margin.store import Workspace
from concept_corpus import write


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    ehome.save_settings({**ehome.load_settings(), "backend": "anthropic", "allow_cloud": True, "embed_backend": "off"})
    ws = ehome.create_project("T")
    ingest.ingest(ws, [write(tmp_path / "docs")["solar"].parent])
    terms.build(ws)
    yield ws
    ws.close_all()


class FakeModel:
    """A model server that names a group after its first concept, quoting the first words of passage 1."""

    name = "anthropic"

    def __init__(self, quote: str | None = None):
        self.calls, self.prompts, self.quote = 0, [], quote

    def complete(self, kind, system, user, model, payload):
        assert kind == "group_name" and system.startswith("You name one group of concepts")
        self.calls += 1
        self.prompts.append(user)
        words = payload["passages"][0]["text"].split()
        return json.dumps({"name": f"Talk of {payload['concepts'][0].split()[0]}",
                           "name_quote": {"passage": 1, "quote": self.quote or " ".join(words[:5])}, "note": None})


def _map(ws, f=None, n=30):
    return conceptmap.concept_map(ws, f or Filters(), n)


def _body(m, g, **kw):
    lab = {x["id"]: x["label"] for x in m["nodes"]}
    return {"name_id": g["name_id"], "concepts": g["concepts"], "labels": {t: lab[t] for t in g["concepts"]},
            "filters": m["filters"], "n": m["n"], **kw}


def _by_first(m) -> dict[str, dict]:
    return {g["concepts"][0]: g for g in m["groups"]}


def test_every_group_is_named_by_its_two_most_central_concepts(project):
    m = _map(project)
    assert m["groups"] and m["names_elsewhere"] == []
    lab = {x["id"]: x["label"] for x in m["nodes"]}
    for g in m["groups"]:
        assert g["name_source"] == "concepts" and g["name_id"] is None and g["changed"] is None
        assert g["name"] == groupnames.concepts_name([lab[t] for t in g["concepts"][:2]])
        assert sorted(g["concepts"]) == sorted(x["id"] for x in m["nodes"] if x["group"] == g["group"])
    assert m["can_name"] == {"offered": True, "why": None, "reader": "claude"}
    assert groupnames.concepts_name(["office days", "team days"]) == "Office days and team days"
    long = "a" * 40
    assert groupnames.concepts_name([long, "b" * 30]) == "A" + "a" * 39                # the two pass 60: one alone
    assert len(groupnames.concepts_name(["x" * 90])) == groupnames.MAX_NAME
    assert m["groups"][0]["name"] in conceptmap.as_text(m)


def test_drawing_the_map_asks_no_ai_and_makes_no_task(project):
    _map(project)
    _map(project, n=60)
    assert project.scalar("SELECT COUNT(*) FROM tasks") == 0


def test_a_name_given_stays_with_its_group_and_waits_while_its_group_is_off_the_map(project):
    m = _map(project)
    g = m["groups"][0]
    r = groupnames.save(project, "rename", _body(m, g, name="  Parking   and the pool "))
    assert r["record"]["name"] == "Parking and the pool" and r["record"]["source"] == "person"
    m2 = _map(project)
    got = _by_first(m2)[g["concepts"][0]]
    assert (got["name"], got["name_source"], got["changed"]) == ("Parking and the pool", "person", None)
    # another size of map: the group is found again with most of the same concepts, and keeps the name, unflagged
    m3 = _map(project, n=60)
    named = [x for x in m3["groups"] if x["name_source"] == "person"]
    assert [x["name"] for x in named] == ["Parking and the pool"] and named[0]["changed"] is None
    # a document filter that leaves none of its concepts: the name is listed apart, not lost
    solar = project.scalar("SELECT doc_id FROM documents WHERE title='Solar survey'")
    f = Filters(docs=[solar])
    f.applied = f.describe()
    m4 = conceptmap.concept_map(project, f, 30)
    assert m4["groups"] and all(x["name_source"] != "person" for x in m4["groups"])
    assert [x["name"] for x in m4["names_elsewhere"]] == ["Parking and the pool"]
    # the same again: an empty name is refused, and "Use its concepts as the name" removes it
    with pytest.raises(ValueError):
        groupnames.save(project, "rename", _body(m, g, name="   ", name_id=r["record"]["name_id"]))
    groupnames.save(project, "use_concepts", {"name_id": r["record"]["name_id"], "concepts": g["concepts"]})
    assert _by_first(_map(project))[g["concepts"][0]]["name_source"] == "concepts"


def test_matching_is_by_most_of_the_concepts_and_the_same_every_time():
    rec = lambda i, cs, at="2026-11-17": {"name_id": i, "concepts": cs, "updated_at": at}  # noqa: E731
    groups = [["a", "b", "c", "d"], ["e", "f", "g"]]
    on = set("abcdefg")
    # a, b, c of a, b, c, x: most of those on the map (x is not) -> group 0; e, z: only one on the map, too few
    got = groupnames.match([rec("n1", ["a", "b", "c", "x"]), rec("n2", ["e", "z"])], groups, on)
    assert {k: v["name_id"] for k, v in got.items()} == {0: "n1"}
    # two names for one group (D1, the last part: the same answer on every copy, whose groups differ, so never by how
    # well each fits): a person's decision before an AI draft; then the newer; then the id
    got = groupnames.match([rec("n1", ["a", "b"], "2026-11-10"), rec("n2", ["a", "b", "c", "d"], "2026-11-01")], groups, on)
    assert got[0]["name_id"] == "n1"
    got = groupnames.match([rec("n1", ["a", "b", "c"], "2026-11-01"), rec("n2", ["a", "b", "c"], "2026-11-10")],
                           groups, on)
    assert got[0]["name_id"] == "n2"
    got = groupnames.match([{**rec("n1", ["a", "b", "c"], "2026-11-01"), "source": "person"},
                            {**rec("n2", ["a", "b", "c"], "2026-11-10"), "source": "ai_draft"}], groups, on)
    assert got[0]["name_id"] == "n1"
    # half is not most
    assert groupnames.match([rec("n1", ["a", "b", "e", "f"])], groups, on) == {}


def test_a_group_that_changed_under_the_same_filters_is_flagged_until_kept(project):
    m = _map(project)
    g = m["groups"][0]
    lab = {x["id"]: x["label"] for x in m["nodes"]}
    groupnames.save(project, "rename", _body(m, g, name="Parking"))
    # the name was given when the group held two concepts more and k fewer, k a third of the name's concepts or more
    nid = project.scalar("SELECT name_id FROM concept_group_names")
    k = -(-(len(g["concepts"]) + 2) // 4)
    stored = g["concepts"][k:] + ["t-gone-1", "t-gone-2"]
    with project.connect() as cx:
        cx.execute("UPDATE concept_group_names SET concepts_json=?, labels_json=? WHERE name_id=?",
                   (json.dumps(stored), json.dumps({"t-gone-1": "mortgage", "t-gone-2": "city centre"}), nid))
    got = _by_first(_map(project))[g["concepts"][0]]
    assert got["name"] == "Parking"
    assert got["changed"] == {"left": ["mortgage", "city centre"], "joined": [lab[t] for t in g["concepts"][:k]]}
    # under another size the same difference is the view's: not flagged
    assert all(x["changed"] is None for x in _map(project, n=60)["groups"])
    m2 = _map(project)
    groupnames.save(project, "keep", _body(m2, _by_first(m2)[g["concepts"][0]]))
    assert _by_first(_map(project))[g["concepts"][0]]["changed"] is None


def test_the_ai_drafts_a_name_for_each_group_marked_until_used(project):
    model = FakeModel()
    m = _map(project)
    person = m["groups"][0]
    groupnames.save(project, "rename", _body(m, person, name="Mine"))
    r = groupnames.name_groups(project, Filters(), 30, "unnamed", model, "claude-haiku-5-5")
    assert r["named"] == len(m["groups"]) - 1 and r["failed"] == 0 and r["skipped"] == 0
    assert model.calls == len(m["groups"]) - 1
    # the prompt holds the group's concepts and passages where several of them meet, at most six
    assert model.prompts[0].startswith("GROUP OF CONCEPTS: ") and "\nP1" in model.prompts[0]
    assert model.prompts[0].count("CONCEPTS IN IT:") <= groupnames.MAX_PASSAGES
    m2 = _map(project)
    by = _by_first(m2)
    assert by[person["concepts"][0]]["name"] == "Mine"                    # a name the researcher gave: never touched
    drafts = [g for g in m2["groups"] if g["name_source"] == "ai_draft"]
    assert len(drafts) == len(m["groups"]) - 1
    d = drafts[0]
    assert d["name"].startswith("Talk of ") and d["model"] == "claude-haiku-5-5"
    assert d["quote"]["quote"] and d["quote"]["doc_id"] and d["quote"]["title"]
    # Use this name, and Undo
    groupnames.save(project, "accept", _body(m2, d))
    assert _by_first(_map(project))[d["concepts"][0]]["name_source"] == "ai"
    groupnames.save(project, "unaccept", {"name_id": d["name_id"]})
    assert _by_first(_map(project))[d["concepts"][0]]["name_source"] == "ai_draft"
    # all at once
    items = [{"name_id": g["name_id"], "concepts": g["concepts"]} for g in drafts]
    groupnames.save(project, "accept", {"items": items})
    assert {g["name_source"] for g in _map(project)["groups"]} == {"ai", "person"}
    # "again": a new draft for every group but the researcher's, told the name before
    r = groupnames.name_groups(project, Filters(), 30, "again", FakeModel(), "claude-haiku-5-5")
    assert r["groups"] == len(m["groups"]) - 1
    # (the fake gives the same name again, which the check sends back: none named, each failed after its tries)
    assert r["named"] == 0 and r["failed"] == len(m["groups"]) - 1
    log = project.query("SELECT text FROM research_log WHERE kind='concept-groups-named'")
    assert log and log[0]["text"].endswith("Each is a draft until it is used or renamed.")   # (and travels with the project)


def test_a_group_the_ai_could_not_name_keeps_its_concepts_and_says_why(project):
    r = groupnames.name_groups(project, Filters(), 30, "unnamed", FakeModel(quote="words that are nowhere here"),
                               "claude-haiku-5-5")
    assert r["named"] == 0 and r["failed"] == r["groups"] > 0
    m = _map(project)
    for g in m["groups"]:
        assert g["name_source"] == "concepts"
        assert g["naming_failed"]["reason"] == "its quotes were not found word for word in the passages"
        assert g["naming_failed"]["model"]
    # renamed: no longer the page's news
    g = m["groups"][0]
    groupnames.save(project, "rename", _body(m, g, name="Mine"))
    groupnames.save(project, "use_concepts", {"name_id": _by_first(_map(project))[g["concepts"][0]]["name_id"],
                                              "concepts": g["concepts"]})
    assert _by_first(_map(project))[g["concepts"][0]]["naming_failed"] is None


def test_documents_the_ai_may_not_read_are_never_sent(project):
    docs = [r[0] for r in project.query("SELECT doc_id, title FROM documents ORDER BY title")]
    council = project.scalar("SELECT doc_id FROM documents WHERE title='Council minutes'")
    access.set_documents(project, [council], "none")
    model = FakeModel()
    groupnames.name_groups(project, Filters(), 30, "unnamed", model, "claude-haiku-5-5")
    minutes = project.query("SELECT text FROM passages WHERE doc_id=?", (council,))
    for p in model.prompts:
        for row in minutes:
            assert " ".join(row["text"].split()) not in " ".join(p.split())
    # no document an AI may read: not offered, and the page says why; nothing is asked
    access.set_documents(project, docs, "none")
    m = _map(project)
    assert m["can_name"] == {"offered": False, "why": groupnames.NONE_MAY_READ, "reader": None}
    n = project.scalar("SELECT COUNT(*) FROM tasks")
    model2 = FakeModel()
    r = groupnames.name_groups(project, Filters(), 30, "unnamed", model2, "claude-haiku-5-5")
    assert model2.calls == 0 and r["groups"] == 0 and project.scalar("SELECT COUNT(*) FROM tasks") == n
    # only a local AI may read them, and none is chosen: said so
    access.set_documents(project, docs, "local")
    assert "Only a local AI may read" in _map(project)["can_name"]["why"]


def test_a_quote_goes_with_its_document_and_the_names_stay(project):
    groupnames.name_groups(project, Filters(), 30, "unnamed", FakeModel(), "claude-haiku-5-5")
    doc = project.scalar("SELECT doc_id FROM concept_group_quotes LIMIT 1")
    n = project.scalar("SELECT COUNT(*) FROM concept_group_names")
    project.remove_document(doc)
    assert project.scalar("SELECT COUNT(*) FROM concept_group_quotes WHERE doc_id=?", (doc,)) == 0
    assert project.scalar("SELECT COUNT(*) FROM concept_group_names") == n            # the names stay
    assert project.scalar("SELECT COUNT(*) FROM tasks WHERE kind='group_name' AND instr(payload_json, ?) > 0",
                          (json.dumps(doc),)) == 0


def test_forget_and_restore_a_name(project):
    m = _map(project)
    groupnames.save(project, "rename", _body(m, m["groups"][0], name="Gone soon"))
    nid = project.scalar("SELECT name_id FROM concept_group_names")
    rec = groupnames.save(project, "forget", {"name_id": nid})["record"]
    assert project.scalar("SELECT COUNT(*) FROM concept_group_names") == 0
    back = groupnames.save(project, "restore", {"record": rec})["record"]
    assert back["name"] == "Gone soon" and back["name_id"] == nid
    with pytest.raises(KeyError):
        groupnames.save(project, "forget", {"name_id": "nope"})
    with pytest.raises(ValueError):
        groupnames.save(project, "dance", {})


# ---- review findings ----------------------------------------------------------------------------------------------
def _insert_name(ws, name, source, concepts, labels=None):
    nid = f"n-{name[:6].lower()}"
    with ws.connect() as cx:
        cx.execute("INSERT INTO concept_group_names(name_id, name, source, model, concepts_json, labels_json, "
                   "filters_json, n, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (nid, name, source, "claude-haiku-5-5" if source != "person" else None, json.dumps(concepts),
                    json.dumps(labels or {}), "{}", 30, "2026-11-17T08:00:00+00:00", "2026-11-17T08:00:00+00:00"))
    return nid


@pytest.mark.parametrize("source", ["ai_draft", "ai", "person"])
def test_an_ai_draft_never_takes_the_name_another_group_holds(project, source):
    """A kept name whose concepts span two groups of the map (all of the big group's, and two of a smaller one's):
    the big group holds it. The smaller group's draft is its own new name; the big group's name is left as it was."""
    m = _map(project)
    big, small = sorted(m["groups"], key=lambda g: -len(g["concepts"]))[:2]
    assert len(big["concepts"]) > 2 and len(small["concepts"]) >= 2
    nid = _insert_name(project, "Kept for the big one", source, big["concepts"] + small["concepts"][:2])
    m = _map(project)
    by = _by_first(m)
    assert by[big["concepts"][0]]["name_id"] == nid and by[small["concepts"][0]]["name_source"] == "concepts"
    r = groupnames.name_groups(project, Filters(), 30, "unnamed", FakeModel(), "claude-haiku-5-5")
    assert r["failed"] == 0
    row = project.query("SELECT name, source FROM concept_group_names WHERE name_id=?", (nid,))[0]
    assert (row["name"], row["source"]) == ("Kept for the big one", source)          # never overwritten
    by = _by_first(_map(project))
    assert by[big["concepts"][0]]["name_id"] == nid
    got = by[small["concepts"][0]]
    assert got["name_source"] == "ai_draft" and got["name_id"] != nid and got["name"].startswith("Talk of ")


def test_after_name_the_groups_again_a_group_the_ai_could_not_name_says_why(project):
    """Asked again, a group named by the AI before keeps that name when the AI cannot name it anew, and the page
    says why (the toast promises it); Name them again ("unnamed") asks for it again, told the name before."""
    groupnames.name_groups(project, Filters(), 30, "unnamed", FakeModel(), "claude-haiku-5-5")
    m = _map(project)
    assert {g["name_source"] for g in m["groups"]} == {"ai_draft"}
    r = groupnames.name_groups(project, Filters(), 30, "again", FakeModel(), "claude-haiku-5-5")
    assert r["failed"] == len(m["groups"])
    m2 = _map(project)
    for g in m2["groups"]:
        assert g["name_source"] == "ai_draft" and g["naming_failed"], g
        assert g["naming_failed"]["reason"]
    got = groupnames.payloads(project, Filters(), 30, "unnamed", {"cloud"})
    assert len(got["tasks"]) == len(m["groups"])
    assert all(p["before"] == gr["name"] for gr, p in got["tasks"])
    # a new name for one of them: its failure is no longer the page's news
    class Other(FakeModel):
        def complete(self, kind, system, user, model, payload):
            obj = json.loads(super().complete(kind, system, user, model, payload))
            return json.dumps({**obj, "name": "Something else entirely"})
    groupnames.name_groups(project, Filters(), 30, "unnamed", Other(), "claude-haiku-5-5")
    assert all(g["naming_failed"] is None for g in _map(project)["groups"])


def test_a_draft_turned_down_is_not_handed_back_without_asking_the_ai(project):
    model = FakeModel()
    groupnames.name_groups(project, Filters(), 30, "unnamed", model, "claude-haiku-5-5")
    m = _map(project)
    d = m["groups"][0]
    assert d["name_source"] == "ai_draft"
    groupnames.save(project, "use_concepts", {"name_id": d["name_id"], "concepts": d["concepts"]})
    assert _by_first(_map(project))[d["concepts"][0]]["name_source"] == "concepts"
    model2 = FakeModel()
    r = groupnames.name_groups(project, Filters(), 30, "unnamed", model2, "claude-haiku-5-5")
    assert r["groups"] == 1 and model2.calls == 1                 # the AI is asked, not the old answer reused


def test_a_group_finds_the_passages_it_may_read_beyond_the_most_shared_ones(project, monkeypatch):
    """The passages where most of a group's concepts meet are taken only from documents the reader may read: a
    group whose most-shared passages are all in a document marked No AI still finds the others."""
    from margin.conceptpaths import _Graph

    m = _map(project)
    g = _Graph(project)
    lv, dflt = access.levels(project), access.default(project)
    def docs_of(x):
        nodes = [g.node(t) for t in x["concepts"]]
        return {p["doc_id"] for p in groupnames._passages_of(project, Filters(), nodes, g, {"cloud"}, lv, dflt)}

    gr = next(x for x in m["groups"] if len(docs_of(x)) >= 2)
    nodes = [g.node(t) for t in gr["concepts"]]
    monkeypatch.setattr(groupnames, "MAX_CANDIDATES", 1)
    top = groupnames._passages_of(project, Filters(), nodes, g, {"cloud"}, lv, dflt)[0]["doc_id"]
    access.set_documents(project, [top], "none")
    lv = access.levels(project)
    got = groupnames._passages_of(project, Filters(), nodes, g, {"cloud"}, lv, dflt)
    assert got and all(p["doc_id"] != top for p in got)


def test_undo_of_use_this_name_puts_back_what_it_overwrote(project):
    groupnames.name_groups(project, Filters(), 30, "unnamed", FakeModel(), "claude-haiku-5-5")
    m = _map(project)
    d = m["groups"][0]
    was = dict(project.query("SELECT * FROM concept_group_names WHERE name_id=?", (d["name_id"],))[0])
    # used under another size and with fewer concepts than it was drafted for
    r = groupnames.save(project, "accept", {**_body(m, d), "concepts": d["concepts"][:3], "n": 60})
    assert r["before"] and r["before"][0]["name_id"] == d["name_id"]
    assert project.scalar("SELECT n FROM concept_group_names WHERE name_id=?", (d["name_id"],)) == 60
    back = groupnames.save(project, "unaccept", {"name_id": d["name_id"], "before": json.loads(json.dumps(r["before"]))})
    assert back["record"]["source"] == "ai_draft"
    now = dict(project.query("SELECT * FROM concept_group_names WHERE name_id=?", (d["name_id"],))[0])
    # the name as it was; the Undo itself is a new change (its time, who made it, what it replaced: review of 18 Nov)
    stamps = ("updated_at", "changed_by", "history_json")
    assert {k: v for k, v in now.items() if k not in stamps} == {k: v for k, v in was.items() if k not in stamps}
    assert now["updated_at"] > was["updated_at"] and len(json.loads(now["history_json"])) == 2
    # all at once, and back
    items = [{"name_id": x["name_id"], "concepts": x["concepts"][:2]} for x in m["groups"]]
    r = groupnames.save(project, "accept", {"items": items, "filters": {}, "n": 90})
    assert len(r["before"]) == len(items)
    groupnames.save(project, "unaccept", {"items": items, "before": r["before"]})
    assert {x["n"] for x in project.query("SELECT n FROM concept_group_names")} == {30}
    assert {g["name_source"] for g in _map(project)["groups"]} == {"ai_draft"}


def test_passages_only_a_local_ai_may_read_never_go_into_a_task_for_claude(project, monkeypatch):
    """The binding rule: a document marked Only a local AI is never in a group_name task Claude reads, with no local
    model chosen (those passages are left out) and with one (its tasks go to the local model only)."""
    solar = project.scalar("SELECT doc_id FROM documents WHERE title='Solar report'")
    access.set_documents(project, [solar], "local")
    others = " ".join(" ".join(r["text"].split()) for r in project.query("SELECT text FROM passages WHERE doc_id!=?",
                                                                          (solar,)))
    # its passages' text that no other document holds (the corpus repeats a few sentences across documents)
    texts = [t for t in (" ".join(r["text"].split()) for r in project.query("SELECT text FROM passages WHERE doc_id=?",
                                                                             (solar,))) if t not in others]
    assert texts
    pids = {r["passage_id"] for r in project.query("SELECT passage_id FROM passages WHERE doc_id=?", (solar,))}

    def no_local_text(model):
        for p in model.prompts:
            flat = " ".join(p.split())
            assert not any(t in flat for t in texts)

    def cloud_tasks_clean():
        for r in project.query("SELECT payload_json, access FROM tasks WHERE kind='group_name'"):
            got = {x["passage_id"] for x in json.loads(r["payload_json"])["passages"]}
            if got & pids:
                assert r["access"] == "local", r["access"]

    cloud = FakeModel()
    groupnames.name_groups(project, Filters(), 30, "unnamed", cloud, "claude-haiku-5-5")
    assert cloud.calls
    assert all(not ({x["passage_id"] for x in json.loads(r["payload_json"])["passages"]} & pids)
               for r in project.query("SELECT payload_json FROM tasks WHERE kind='group_name'"))
    no_local_text(cloud)
    # a local model chosen: the passages of that document go only to it
    class Local(FakeModel):
        name = "ollama"
        base_url = "http://127.0.0.1:11434"
    local = Local()
    ehome.save_settings({**ehome.load_settings(), "restricted_server": "ollama", "restricted_model": "big"})
    monkeypatch.setattr(ehome, "make_restricted_backend", lambda settings: (local, "big"))
    cloud2 = FakeModel()
    with project.connect() as cx:
        cx.execute("DELETE FROM results WHERE task_id IN (SELECT task_id FROM tasks WHERE kind='group_name')")
        cx.execute("DELETE FROM tasks WHERE kind='group_name'")
        cx.execute("DELETE FROM concept_group_names")
    groupnames.name_groups(project, Filters(), 30, "unnamed", cloud2, "claude-haiku-5-5")
    no_local_text(cloud2)
    cloud_tasks_clean()
    assert local.calls >= 1 and any(any(t in " ".join(p.split()) for t in texts) for p in local.prompts)


def test_with_claude_code_name_the_groups_only_queues_until_start(api, tmp_path, monkeypatch):  # noqa: F811
    """No AI model starts until its own Start is pressed: with the Claude Code backend, Name the groups puts the
    tasks in the queue and waits; nothing is answered and Claude Code is not started."""
    from test_app import _wait_until

    from margin import claude_setup

    started = []
    monkeypatch.setattr(claude_setup, "start_run", lambda *a, **k: started.append(1) or {"running": True})
    st, r = api("PUT", "/api/settings", {"allow_claude_code": True, "backend": "claude_code", "embed_backend": "off"})
    assert st == 200, r
    assert api("POST", "/api/projects", {"name": "Q"})[0] == 200
    ws = Workspace.open(ehome.project_path("Q"))
    try:
        ingest.ingest(ws, [write(tmp_path / "docs")["solar"].parent])
        terms.build(ws)
        st, m = api("GET", "/api/projects/Q/concept-map?n=30")
        assert st == 200 and m["can_name"]["offered"] and m["can_name"]["reader"] == "claude", m["can_name"]
        st, r = api("POST", "/api/projects/Q/concept-map/name-groups?n=30", {"which": "unnamed"})
        assert st == 200, r
        n = len(m["groups"])
        _wait_until(lambda: ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='group_name' AND queued=1") == n)
        import time

        time.sleep(0.5)
        assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='group_name' AND status='pending'") == n
        assert ws.scalar("SELECT COUNT(*) FROM results") == 0
        assert ws.scalar("SELECT COUNT(*) FROM concept_group_names") == 0
        job = next(j for j in api("GET", "/api/jobs")[1]["jobs"] if j["id"] == r["job"]["id"])
        assert job["state"] in ("running", "queued"), job["state"]
        assert started == []
        api("POST", f"/api/jobs/{r['job']['id']}/cancel")
        api.wait(r["job"]["id"])
        assert ws.scalar("SELECT COUNT(*) FROM results") == 0 and started == []
    finally:
        ws.close_all()


def test_the_routes(api, tmp_path):  # noqa: F811
    assert api("PUT", "/api/settings", {"backend": "baseline", "embed_backend": "off"})[0] == 200
    assert api("POST", "/api/projects", {"name": "Map"})[0] == 200
    ws = Workspace.open(ehome.project_path("Map"))
    try:
        ingest.ingest(ws, [write(tmp_path / "docs")["solar"].parent])
        terms.build(ws)
    finally:
        ws.close_all()
    st, m = api("GET", "/api/projects/Map/concept-map?n=30")
    assert st == 200 and m["groups"][0]["name_source"] == "concepts" and m["can_name"]["offered"]
    g = m["groups"][0]
    st, r = api("POST", "/api/projects/Map/concept-map/names", {"action": "rename", **_body(m, g, name="Mine")})
    assert st == 200 and r["record"]["source"] == "person"
    assert api("POST", "/api/projects/Map/concept-map/names", {"action": "rename", **_body(m, g, name="")})[0] == 400
    assert api("POST", "/api/projects/Map/concept-map/names", {"action": "keep", "name_id": "nope",
                                                               "concepts": ["x"]})[0] == 404
    st, r = api("POST", "/api/projects/Map/concept-map/name-groups?n=30", {"which": "unnamed"})
    assert st == 200 and r["job"]["kind"] == "group-names"
    job = api.wait(r["job"]["id"])
    assert job["state"] == "done", job
    assert job["result"]["named"] == len(m["groups"]) - 1
    st, m2 = api("GET", "/api/projects/Map/concept-map?n=30")
    assert sorted(x["name_source"] for x in m2["groups"]) == sorted(["person"] + ["ai_draft"] * (len(m["groups"]) - 1))
    assert api("POST", "/api/projects/Map/concept-map/name-groups?theme=gone:1", {})[0] == 404


from test_app import api, home  # noqa: E402,F401  (fixtures)
