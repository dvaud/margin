"""K2, the framework draft (theoryframe.py): a codebook from theory documents as one framework, not a list per document.

A draft (one per project, a file of the project folder) starts from what the texts define outright, joined across
documents; the reading drafts every part of every document (`theory_codes`) and joins the drafts into groups and
concepts (`theory_frame`), leaving what the person touched as it is; the evidence is found by the concept's own words,
never in a theory document; *Make the codebook* turns the kept concepts into codes with the framework's groups."""
from __future__ import annotations

import json
import re

import pytest

from margin import access, codebooks, docrole, ingest, tasks, theorycodes, theoryframe
from margin import home as ehome
from margin.store import Workspace
from test_codebook_from_theory import EVIDENCE, _theory_pdf
from test_theory_codes_ai import _answer

# a second theory that defines a term the first one defines too ("stock"), and one of its own ("practice")
PRACTICE = ("Practice theory\n\n"
            "A stock is the store of habits that a practice keeps from one year to the next. A practice is a "
            "routinised way in which bodies move, objects are handled and the world is understood. Practices "
            "change when the stock of their habits changes.\n")


# what a helper drafts from each part: the concepts whose quote the part holds
DRAFTED = [("Changing flows", "the memory of the history of changing flows"),
           ("Stocks", "A stock is the memory of the history"),
           ("Reinforcing loop", "a loop that amplifies whatever happens in it"),
           ("Stock", "A stock is the store of habits"),
           ("Routine", "a routinised way in which bodies move")]


def _frame(payload: dict, bad: str | None = None) -> dict:
    """A framework as the AI gives it: the stock drafts of both documents joined, the reinforcing loop, practice; the
    rest left out. `bad`: "unknown" (a draft number that is not there) or "twice" (one draft in two concepts)."""
    def nums(*names):
        return [d["n"] for d in payload["drafts"] if theorycodes._norm(d["name"]) in names]

    stock, loop, practice = nums("stock"), nums("reinforcing loop"), nums("practice")
    if bad == "unknown":
        stock = stock + [999]
    if bad == "twice":
        practice = practice + stock[:1]
    concept = {"meaning": "What has built up over time in a system.", "not_when": None, "core": True,
               "words": ["kept", "built up", "store", "over the years"]}
    groups = [
        {"name": "Parts of a system", "about": "What a system is made of.", "concepts": [
            {**concept, "name": "stock", "from": stock, "when_to_use": "When a passage says what has built up.",
             "not_when": "When it is about how fast it changes, use reinforcing loop."},
            {**concept, "name": "reinforcing loop", "from": loop,
             "meaning": "A loop that makes whatever happens in it grow.",
             "when_to_use": "When a passage tells of something that feeds on itself.",
             "words": ["more and more", "less and less", "grew", "spiral"]}]},
        {"name": "Practices", "about": "How people do things.", "concepts": [
            {**concept, "name": "practice", "from": practice, "core": False,
             "meaning": "A routinised way of doing things.", "when_to_use": "When a passage describes a routine.",
             "words": ["routine", "every week", "the way we do it"]}]}]
    # a concept with no draft of its own is not in the framework (a document left out has none), nor an empty group
    groups = [{**g, "concepts": [c for c in g["concepts"] if c["from"]]} for g in groups]
    return {"groups": [g for g in groups if g["concepts"]], "note": "Left out the rest."}


class FakeModel:
    """Claude through the API: drafts each part as test_theory_codes_ai does, and answers the frame with `frames` in
    turn (the last one again after them). Counts its calls by kind and keeps the payloads it was sent."""

    name = "anthropic"

    def __init__(self, frames=(None,)):
        self.frames = list(frames)
        self.calls = {"theory_codes": 0, "theory_frame": 0}
        self.payloads: list[dict] = []

    def complete(self, kind, system, user, model, payload):
        self.calls[kind] += 1
        self.payloads.append(payload)
        if kind == "theory_codes":
            text = " ".join(user.split())
            return json.dumps(_answer(user, [c for c in DRAFTED if c[1] in text]))
        assert system.startswith("You build a coding framework") and "DRAFTED CONCEPTS:" in user
        bad = self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]
        return json.dumps(_frame(payload, bad))


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    ehome.save_settings({**ehome.load_settings(), "backend": "anthropic", "allow_cloud": True, "embed_backend": "off"})
    ws = ehome.create_project("T")
    d = tmp_path / "docs"
    d.mkdir()
    _theory_pdf(d / "meadows.pdf")
    (d / "practice.txt").write_text(PRACTICE, encoding="utf-8")
    (d / "carehome.txt").write_text(EVIDENCE, encoding="utf-8")
    ingest.ingest(ws, [d])
    meadows = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%memory of the history%'")
    practice = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%routinised way%'")
    evidence = ws.scalar("SELECT doc_id FROM documents WHERE doc_id NOT IN (?, ?)", (meadows, practice))
    docrole.set_role(ws, meadows, "theory")
    docrole.set_role(ws, practice, "theory")
    yield ws, meadows, practice, evidence
    ws.close_all()


def _by_name(draft: dict) -> dict[str, dict]:
    return {theorycodes._norm(c["name"]): c for c in draft["concepts"]}


def _started(ws, meadows, practice, focus=""):
    return theoryframe.start(ws, "Systems and practices", "lenses", "project", [meadows, practice], focus)


def test_a_draft_starts_from_what_the_texts_define_joined_across_documents(project):
    ws, meadows, practice, _ev = project
    d = _started(ws, meadows, practice)
    assert (ws.root / "drafts" / "codebook-from-theory.json").is_file() and theoryframe.load(ws) == d
    got = _by_name(d)
    # "stock", defined by both theories: one concept, a source in each document
    assert {s["doc_id"] for s in got["stock"]["sources"]} == {meadows, practice}
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (practice,))
    s = next(s for s in got["stock"]["sources"] if s["doc_id"] == practice)
    assert " ".join(text[s["start"]:s["end"]].split()) == s["quote"] and s["quote"].startswith("A stock is the store")
    assert "practice" in got and "reinforcing loop" in got
    # no frequent words, no groups, nothing kept (neither has a glossary), no meaning yet
    assert "delay" not in got and d["groups"] == [] and not any(c["keep"] for c in d["concepts"])
    assert all(c["meaning"] == "" and c["words"] == [c["name"].lower()] for c in d["concepts"])
    assert d["reading"]["state"] == "none" and d["name"] == "lenses" and d["where"] == "project"
    # a name taken by a codebook, or a document not in the project, is refused
    codebooks.create(ws, "taken", "Taken")
    with pytest.raises(ValueError):
        theoryframe.start(ws, "x", "taken", "project", [meadows])
    with pytest.raises(KeyError):
        theoryframe.start(ws, "x", "other", "project", ["nope"])


def test_the_reading_puts_a_framework_together_from_both_documents(project):
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice, focus="how care homes take up new technology")
    be = FakeModel()
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    assert r["ok"] and r["state"] == "read" and be.calls == {"theory_codes": 2, "theory_frame": 1}
    d = theoryframe.load(ws)
    assert [g["name"] for g in d["groups"]] == ["Parts of a system", "Practices"]
    got = _by_name(d)
    assert set(got) >= {"stock", "reinforcing loop", "practice"}
    stock = got["stock"]
    assert {s["doc_id"] for s in stock["sources"]} == {meadows, practice}
    assert stock["group"] == d["groups"][0]["key"] and stock["how"] == "ai" and stock["core"] and stock["keep"]
    assert not got["practice"]["keep"] and stock["when_to_use"].startswith("When a passage")
    assert stock["ai"] == {"model": "claude-sonnet-5-5", "meaning": stock["meaning"],
                           "when_to_use": stock["when_to_use"], "when_not": stock["when_not"]}
    # the drafts no concept is made of can be added later
    assert d["left_out"] and all(x["doc_id"] in (meadows, practice) and x["quote"] for x in d["left_out"])
    assert "Changing flows" in {x["name"] for x in d["left_out"]}
    reading = d["reading"]
    assert reading["parts"] == reading["parts_read"] == 2 and reading["drafted"] >= 4 and reading["frame_task"]
    # the frame payload: documents, the evidence's titles (never a theory's), the focus, drafts with their passages
    frame = next(p for p in be.payloads if "drafts" in p)
    assert {x["doc_id"] for x in frame["documents"]} == {meadows, practice}
    assert frame["focus"] == "how care homes take up new technology"
    titles = {r_["title"] for r_ in ws.query("SELECT title FROM documents WHERE doc_id IN (?, ?)", (meadows, practice))}
    assert frame["evidence_titles"] and not set(frame["evidence_titles"]) & titles
    assert all(x["passage_id"] and x["doc_id"] in (meadows, practice) and len(x["quote"]) <= 425
               for x in frame["drafts"])
    log = ws.query("SELECT text, data_json FROM research_log WHERE kind='codebook-drafted'")
    assert len(log) == 1 and "2 theory documents" in log[0]["text"] and "3 concepts in 2 groups" in log[0]["text"]
    assert json.loads(log[0]["data_json"])["kind"] == "theory_frame"


def test_what_the_person_touched_survives_a_second_reading(project):
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    be = FakeModel()
    theoryframe.read(ws, be, "claude-sonnet-5-5")
    d = theoryframe.load(ws)
    cs = d["concepts"]
    for c in cs:
        if c["name"].lower() == "practice":
            c["meaning"] = "My own words for a practice."
    cs.append({"name": "Repair", "meaning": "Mending things.", "keep": True, "words": ["fix", "mend"]})
    d = theoryframe.save(ws, {"concepts": cs})
    got = _by_name(d)
    assert got["practice"]["touched"] and got["repair"]["touched"] and got["repair"]["how"] == "own"
    assert not got["stock"]["touched"]
    # the same documents and focus: every answer is reused, nothing is asked again
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    assert r["ok"] and r["reused"] and be.calls == {"theory_codes": 2, "theory_frame": 1}
    got = _by_name(theoryframe.load(ws))
    assert got["practice"]["meaning"] == "My own words for a practice."
    assert got["repair"]["keep"] and got["repair"]["how"] == "own"
    assert got["stock"]["meaning"] == "What has built up over time in a system." and not got["stock"]["touched"]
    assert list(got).count("practice") == 1


def test_a_frame_with_an_unknown_draft_or_one_in_two_concepts_is_sent_back(project):
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    be = FakeModel(frames=["unknown", "twice", None])
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    assert r["ok"] and be.calls["theory_frame"] == 3
    rows = ws.query("SELECT valid, errors_json FROM results WHERE kind='theory_frame' ORDER BY attempt")
    assert [x["valid"] for x in rows] == [0, 0, 1]
    assert "there is no draft 999" in rows[0]["errors_json"] and "is in two concepts" in rows[1]["errors_json"]
    assert theoryframe.load(ws)["groups"]


def test_a_frame_that_fails_three_times_leaves_the_drafts_ungrouped(project):
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    r = theoryframe.read(ws, FakeModel(frames=["unknown"]), "claude-sonnet-5-5")
    assert not r["ok"] and r["state"] == "read"
    d = theoryframe.load(ws)
    assert d["groups"] == [] and d["left_out"] == []
    got = _by_name(d)
    assert "changing flow" in got and got["changing flow"]["how"] == "ai" and got["changing flow"]["meaning"] == ""
    assert {s["doc_id"] for s in got["stock"]["sources"]} == {meadows, practice}
    assert any("could not put the framework together" in p for p in d["reading"]["problems"])


def test_the_evidence_comes_only_from_the_evidence_documents_with_its_place(project):
    ws, meadows, practice, ev = project
    _started(ws, meadows, practice)
    got = theoryframe.evidence(ws, {"name": "reinforcing loop", "when_to_use": "When something feeds on itself.",
                                    "words": ["reinforcing loop", "balancing loop", "stock", "practice"]}, k=4)
    assert got and {p["doc_id"] for p in got} == {ev}
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (ev,))
    for p in got:
        assert " ".join(text[p["start"]:p["end"]].split()) == p["quote"] and len(p["quote"]) <= 400
        assert p["passage_id"] and p["project"] == ws.project_uid() and p["found_by"]
    assert any("reinforcing loop" in p["quote"].lower() for p in got)
    # a passage offered before is not offered again
    again = theoryframe.evidence(ws, {"name": "reinforcing loop", "words": ["reinforcing loop"]},
                                 skip=[p["passage_id"] for p in got])
    assert not {p["passage_id"] for p in again} & {p["passage_id"] for p in got}


def test_a_term_looked_up_finds_its_defining_sentence_first(project):
    ws, meadows, practice, _ev = project
    got = theoryframe.lookup(ws, [meadows, practice], "balancing loop")
    by = {s["doc_id"]: s for s in got["sources"]}
    assert by[meadows]["uses"] >= 2 and by[meadows]["options"][0]["quote"].startswith("A balancing loop is defined as")
    assert by[meadows]["options"][0]["page"] == 2 and len(by[meadows]["options"]) <= 3
    assert by[practice] == {"doc_id": practice, "title": by[practice]["title"], "uses": 0, "options": []}
    with pytest.raises(ValueError):
        theoryframe.lookup(ws, [meadows], "  ")


def test_the_kept_concepts_become_a_codebook_with_the_frameworks_groups(project):
    ws, meadows, practice, ev = project
    _started(ws, meadows, practice)
    theoryframe.read(ws, FakeModel(), "claude-sonnet-5-5")
    d = theoryframe.load(ws)
    ex = theoryframe.evidence(ws, {"name": "reinforcing loop", "words": ["reinforcing loop"]}, k=1)
    for c in d["concepts"]:
        if c["name"].lower() == "practice":
            c["keep"], c["when_to_use"] = True, "When a passage describes what staff do every week."
        if c["name"].lower() == "stock":
            c["examples"] = ex + [{"quote": "A stock is the memory", "doc_id": meadows, "title": "Thinking"}]
    theoryframe.save(ws, {"concepts": d["concepts"]})
    cb = theoryframe.make(ws)
    assert theoryframe.load(ws) is None and not (ws.root / "drafts" / "codebook-from-theory.json").exists()
    codes = {c["code"]: c for c in cb["codes"]}
    assert set(codes) == {"Stock", "Reinforcing loop", "Practice"}
    groups = {g["group"]: g["group_name"] for g in cb["groups"]}
    assert groups[codes["Stock"]["group"]] == "Parts of a system" and groups[codes["Practice"]["group"]] == "Practices"
    st = codes["Stock"]
    assert st["description"].startswith("What has built up over time in a system. In the theory: “")
    assert re.search(r"\(Thinking in systems, p\. 1\)\. Also defined in .+\.$", st["description"]), st["description"]
    assert st["include"] == "When a passage says what has built up."
    assert st["exclude"] == "When it is about how fast it changes, use reinforcing loop."
    assert st["keywords"] == ["kept", "built up", "store", "over the years"]
    assert [e["doc_id"] for e in st["examples"]] == [ev]          # the theory's own sentence was dropped
    # the AI's words keep their mark until rewritten: all three for Stock, not Practice's rewritten when to use
    state = codebooks.state_of(ws, "lenses")
    marks = {c["code"]: c.get("ai_draft") for c in state["codes"]}
    assert marks["Stock"]["from"] == "theory" and {"description", "include", "exclude"} <= set(marks["Stock"])
    assert "include" not in (marks["Practice"] or {}) and "description" in marks["Practice"]
    log = ws.query("SELECT text FROM research_log WHERE kind='codebook-added'")[0][0]
    assert "3 concepts of 2 theory documents" in log and "in 2 groups" in log


def test_nothing_kept_or_two_kept_concepts_of_one_name_are_refused(project):
    ws, meadows, practice, _ev = project
    d = _started(ws, meadows, practice)
    with pytest.raises(ValueError, match="Keep at least one concept"):
        theoryframe.make(ws)
    cs = d["concepts"][:2]
    for c in cs:
        c["keep"], c["name"] = True, "Same"
    theoryframe.save(ws, {"concepts": cs})
    with pytest.raises(ValueError, match="Two kept concepts are called 'Same'"):
        theoryframe.make(ws)


def test_saving_cleans_what_the_page_sends(project):
    ws, meadows, practice, ev = project
    d = _started(ws, meadows, practice)
    c = dict(d["concepts"][0])
    c["sources"] = c["sources"] + [{"doc_id": meadows, "quote": "made up", "start": 0, "end": 7}]
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (ev,))
    a = text.index("A delay between")
    z = text.index("arrived.") + len("arrived.")
    real = {"quote": " ".join(text[a:z].split()), "doc_id": ev, "start": a, "end": z, "title": "forged title", "page": 99}
    mtext = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (meadows,))
    c["examples"] = [{"quote": " ".join(mtext[:40].split()), "doc_id": meadows, "start": 0, "end": 40},   # the theory
                     {"quote": "Words nobody wrote in it", "doc_id": ev, "start": a, "end": z},        # not its text
                     {"quote": real["quote"], "doc_id": ev},                                           # no place
                     {"quote": "x", "doc_id": "nope", "start": 0, "end": 1},                           # no document
                     real]
    c["ai"] = {"model": "forged"}
    d = theoryframe.save(ws, {"concepts": [c], "focus": "  repair  ", "groups": [{"key": "g1", "name": "One"}]})
    got = d["concepts"][0]
    assert len(got["sources"]) == len(c["sources"]) - 1                 # a quote not in the text is dropped
    assert got["ai"] is None and d["focus"] == "repair"
    # an example is a span of an evidence document, with the document's own title and page
    assert [(e["doc_id"], e["start"], e["end"]) for e in got["examples"]] == [(ev, a, z)]
    assert got["examples"][0]["title"] != "forged title" and got["examples"][0]["page"] != 99
    # a theory document read again has other text: its quotes stay in the draft, and the concept is not "changed"
    before = [dict(x) for x in got["sources"]]
    assert before and not theoryframe.load(ws)["concepts"][0]["checked"]
    with ws.connect() as cx:
        cx.execute("UPDATE documents SET text = 'Read again. ' || text WHERE doc_id=?", (before[0]["doc_id"],))
    again = theoryframe.save(ws, {"concepts": d["concepts"], "title": "Renamed"})
    assert again["concepts"][0]["sources"] == before and again["title"] == "Renamed"
    # the short name can be changed (a codebook of the first name may have come since), to a free one only
    assert theoryframe.save(ws, {"name": "other_name", "where": "home"})["name"] == "other_name"
    codebooks.create(ws, "taken", "Taken")
    with pytest.raises(ValueError):
        theoryframe.save(ws, {"name": "taken"})
    with pytest.raises(ValueError):
        theoryframe.save(ws, {"where": "nowhere"})
    with pytest.raises(ValueError):
        theoryframe.save(ws, {"concepts": [{"name": ""}]})
    with pytest.raises(ValueError):
        theoryframe.save(ws, {"concepts": [{"name": f"c{i}"} for i in range(61)]})


def test_a_document_marked_no_ai_never_enters_a_payload(project):
    ws, meadows, practice, _ev = project
    access.set_documents(ws, [practice], "none")
    _started(ws, meadows, practice)
    off = theoryframe.offer(ws, [meadows, practice], ehome.load_settings())
    docs = {x["doc_id"]: x for x in off["documents"]}
    assert off["offered"] and not docs[practice]["offered"] and "No AI" in docs[practice]["why"]
    be = FakeModel()
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    assert r["ok"] and be.calls["theory_codes"] == 1
    for t in ws.query("SELECT payload_json FROM tasks"):
        assert practice not in t["payload_json"]
    assert all(practice not in json.dumps(p) for p in be.payloads)
    d = theoryframe.load(ws)
    got = _by_name(d)
    # its own defined term stays as it was (no AI read it), and its quote joins the framework's concept of that name
    assert got["practice"]["how"] == "defined" and {s["doc_id"] for s in got["practice"]["sources"]} == {practice}
    assert practice in {s["doc_id"] for s in got["stock"]["sources"]}
    assert any("No AI" in p for p in d["reading"]["problems"])


def test_a_word_counts_as_the_field_writes_it_and_a_question_is_no_example(project, tmp_path):
    ws, meadows, practice, ev = project
    d = tmp_path / "more"
    d.mkdir()
    (d / "guide.txt").write_text(
        "Interview guide\n\n"
        "Can you tell me about the repair knowledge you had before you first came to the repair evening here?\n\n"
        "Visitors said that the repair knowledge of the volunteers was the reason they came back every month.\n\n"
        "Repair is a niche [11]; parts are hard to get [43,51]; devices are glued shut [9]; repair costs more [67].\n",
        encoding="utf-8")
    ingest.ingest(ws, [d])
    _started(ws, meadows, practice)
    got = theoryframe.evidence(ws, {"name": "competence", "when_to_use": "When a passage says what visitors know.",
                                    "words": ["repair knowledge", "expertise"]}, k=8)
    quotes = [p["quote"] for p in got]
    assert any(q.startswith("Visitors said") for q in quotes)
    assert not any("?" in q or "[43,51]" in q for q in quotes)          # the guide's question, the run of references
    assert all(p["matched"] == ["repair knowledge"] for p in got)        # the phrase, never "repair" alone
    # words of when to use it ("visitors") find nothing by themselves, and without words the name is looked for
    assert theoryframe.evidence(ws, {"name": "habitus", "when_to_use": "When visitors say so.", "words": []}) == []


def test_a_save_from_an_older_page_is_refused_and_a_checked_concept_stays(project):
    ws, meadows, practice, ev = project
    d = _started(ws, meadows, practice)
    assert d["rev"] == 1 and d["concepts"][0]["checked"] is False
    c = {**d["concepts"][0], "checked": True}
    saved = theoryframe.save(ws, {"concepts": [c] + d["concepts"][1:], "rev": d["rev"]})
    assert saved["rev"] == 2 and saved["concepts"][0]["checked"] and saved["concepts"][0]["touched"]
    with pytest.raises(theoryframe.Stale):
        theoryframe.save(ws, {"focus": "late", "rev": d["rev"]})       # the page still holds the first one
    assert theoryframe.load(ws)["focus"] == ""
    assert theoryframe.save(ws, {"focus": "now"})["focus"] == "now"    # without a rev: written (the API's own callers)
    # the reading leaves the checked concept as it is
    theoryframe.read(ws, FakeModel(), "claude-sonnet-5-5")
    assert _by_name(theoryframe.load(ws))[theorycodes._norm(c["name"])]["checked"]


def test_what_is_set_aside_is_there_once_and_the_ais_half_sentence_is_made_whole(project):
    ws, meadows, practice, ev = project
    _started(ws, meadows, practice)
    theoryframe.read(ws, FakeModel(), "claude-sonnet-5-5")
    d = theoryframe.load(ws)
    names = [theorycodes._norm(x["name"]) for x in d["left_out"]]
    assert len(names) == len(set(names)) and not set(names) & set(_by_name(d))
    # "a routinised way in which bodies move" was all the AI quoted: the person reads the sentence it is from
    whole = [s["quote"] for c in d["concepts"] + d["left_out"] for s in (c.get("sources") or [c])
             if "routinised way in which bodies move" in s["quote"]]
    assert whole and all(q.startswith("A practice is a routinised way") and q.endswith("understood.") for q in whole)
    assert theoryframe._broken("refer to c o m m a nd over objects") and theoryframe._broken("connections witFTThose who")
    assert not theoryframe._broken("Agency refers to doing.")


def test_the_routes(api, tmp_path):  # noqa: F811
    from test_codebook_from_theory import THEORY_PAGES

    assert api("PUT", "/api/settings", {"backend": "baseline", "embed_backend": "off"})[0] == 200
    assert api("POST", "/api/projects", {"name": "Lens"})[0] == 200
    d = tmp_path / "in"
    d.mkdir()
    (d / "meadows.txt").write_text("Thinking in systems\n\n" + "\n\n".join("\n\n".join(p) for p in THEORY_PAGES),
                                   encoding="utf-8")
    (d / "practice.txt").write_text(PRACTICE, encoding="utf-8")
    (d / "carehome.txt").write_text(EVIDENCE, encoding="utf-8")
    ws = Workspace.open(ehome.project_path("Lens"))
    try:
        ingest.ingest(ws, [d])
        meadows = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%memory of the history%'")
        practice = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%routinised way%'")
        for x in (meadows, practice):
            docrole.set_role(ws, x, "theory")
    finally:
        ws.close_all()
    base = "/api/projects/Lens/codebook-theory/draft"
    st, body = api("GET", base)
    assert st == 200 and body["draft"] is None and body["offer"] is None and body["documents"][0]["theory"]
    st, body = api("POST", base, {"title": "Lenses", "name": "lenses", "where": "project",
                                  "doc_ids": [meadows, practice], "focus": "care homes"})
    assert st == 200 and body["draft"]["concepts"] and body["offer"]["offered"]
    assert api("POST", base, {"title": "x", "name": "y", "where": "project", "doc_ids": ["nope"]})[0] == 404
    st, body = api("POST", f"{base}/read")
    assert st == 200 and body["job"]["kind"] == "theory-frame" and body["job"]["scope"] == "theory-draft"
    job = api.wait(body["job"]["id"])
    assert job["state"] == "done", job
    st, body = api("GET", base)
    draft = body["draft"]
    assert st == 200 and draft["reading"]["state"] == "read" and draft["groups"][0]["name"] == "Concepts of the theory"
    assert any(c["keep"] for c in draft["concepts"])
    c = next(c for c in draft["concepts"] if c["group"])
    st, body = api("POST", f"{base}/evidence", {"concept": {"name": "reinforcing loop", "words": ["reinforcing loop"]}})
    assert st == 200 and body["passages"] and all(p["doc_id"] not in (meadows, practice) for p in body["passages"])
    st, body = api("GET", f"{base}/counts")
    assert st == 200 and body["documents"] == 1 and set(body["counts"]) == {x["key"] for x in draft["concepts"]}
    assert max(body["counts"].values()) == 1
    st, body = api("GET", f"{base}/lookup?term=balancing%20loop")
    assert st == 200 and body["term"] == "balancing loop" and len(body["sources"]) == 2 and "passages" in body
    c["examples"] = body["passages"][:1]
    assert api("PUT", base, {"focus": "old page", "rev": draft["rev"] - 1})[0] == 409
    st, body = api("PUT", base, {"concepts": draft["concepts"], "rev": draft["rev"]})
    assert st == 200 and body["draft"]["concepts"][0]["key"] == draft["concepts"][0]["key"]
    st, body = api("POST", f"{base}/make")
    assert st == 200 and body["codebook"]["codes"] and body["codebook"]["name"] == "lenses"
    assert api("GET", base)[1]["draft"] is None and api("POST", f"{base}/make")[0] == 404
    # discarding
    assert api("POST", base, {"title": "Again", "name": "again", "where": "project", "doc_ids": [meadows]})[0] == 200
    assert api("DELETE", base) == (200, {"ok": True}) and api("GET", base)[1]["draft"] is None
    # the old routes stay
    assert api("GET", f"/api/projects/Lens/codebook-theory/{meadows}")[0] == 200


from test_app import api, home  # noqa: E402,F401  (fixtures)
