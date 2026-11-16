"""More of the framework draft (theoryframe.py): fitting the frame to a local model's context, the ways a reading ends
short, the evidence found by meaning, a second reading merged into what the person made, saving, looking a term up
and the codebook's descriptions.

Uses the project, stand-in model and frames of tests/test_theory_framework.py.
"""
from __future__ import annotations

import json

import pytest

from test_codebook_from_theory import _one_text
from test_hypotheses import HashEmbedder
from test_theory_framework import FakeModel, _by_name, _started, project  # noqa: F401  (fixture)

from margin import access, docrole, embed, ingest, taskqueue, theorycodes, theoryframe
from margin import home as ehome
from margin.llm import BackendError


class LocalModel(FakeModel):
    """The same answers from a model server on this computer, with a context length."""

    name = "ollama"
    base_url = "http://127.0.0.1:11434"

    def __init__(self, num_ctx: int, frames=(None,)):
        super().__init__(frames)
        self.num_ctx = num_ctx


def _settings(**kw):
    ehome.save_settings({**ehome.load_settings(), **kw})


def _drafts(doc: str, n: int) -> list[dict]:
    """`n` drafts of one document, best first, each with a long quote."""
    return [{"doc_id": doc, "title": f"Title {doc}", "passage_id": f"{doc}:{i:04d}", "name": f"concept {doc} {i}",
             "how": "ai", "quote": f"Concept {i} of {doc} is " + "a long explanation of what it means " * 12,
             "start": i * 500, "end": i * 500 + 400, "page": 1} for i in range(n)]


# ---------------------------------------------------------------------------------------------
# C1: the frame fitted to a local model's context length
# ---------------------------------------------------------------------------------------------
def test_the_frame_payload_is_cut_to_fit_the_room_there_is():
    from margin import prompts

    def size(p):
        return len(prompts.user_prompt(theoryframe.KIND, p))

    docs = [{"doc_id": "a", "title": "Title a"}, {"doc_id": "b", "title": "Title b"}]
    by_doc = [_drafts("a", 10), _drafts("b", 10)]
    whole, sent = theoryframe.fit_payload(docs, ["Interviews"], "care", by_doc, None)
    assert len(sent) == 20 and max(len(d["quote"]) for d in whole["drafts"]) > theoryframe.SHORT_QUOTE_CHARS
    assert theoryframe.fit_payload(docs, ["Interviews"], "care", by_doc, size(whole))[0] == whole   # it fits

    # a little less room: every draft, with short quotes
    short, sent = theoryframe.fit_payload(docs, ["Interviews"], "care", by_doc, size(whole) - 1)
    assert len(sent) == 20 and size(short) <= size(whole) - 1
    assert all(len(d["quote"]) <= theoryframe.SHORT_QUOTE_CHARS + 2 for d in short["drafts"])

    # less still: fewer drafts of each document, the best ones kept, both documents still said
    room = size(short) * 2 // 3
    fewer, sent = theoryframe.fit_payload(docs, ["Interviews"], "care", by_doc, room)
    assert size(fewer) <= room and 6 <= len(sent) < 20
    for doc, lst in (("a", by_doc[0]), ("b", by_doc[1])):
        mine = [d["name"] for d in sent if d["doc_id"] == doc]
        assert mine == [d["name"] for d in lst[:len(mine)]] and len(mine) >= 3
    assert [x["doc_id"] for x in fewer["documents"]] == ["a", "b"]
    assert [d["n"] for d in fewer["drafts"]] == list(range(1, len(sent) + 1))

    # not even three drafts of a document fit: said in words
    with pytest.raises(ValueError, match="context length of the model on this computer is too small"):
        theoryframe.fit_payload(docs, ["Interviews"], "care", by_doc, 500)


def test_the_room_for_the_frame_follows_the_context_length_and_the_reasoning():
    s = {**ehome.DEFAULTS, "think": "off"}
    assert theoryframe._room(FakeModel(), {**s, "num_ctx": 8192}) is None        # Claude: no limit here
    small, big = LocalModel(12000), LocalModel(32768)
    r_small = theoryframe._room(small, {**s, "num_ctx": 12000})
    r_big = theoryframe._room(big, {**s, "num_ctx": 32768})
    assert 0 < r_small < r_big and small.num_ctx == 12000          # a length the person set is kept
    thinking = LocalModel(32768)
    assert theoryframe._room(thinking, {**s, "num_ctx": 32768, "think": "on"}) < r_big   # reasoning takes room
    auto = LocalModel(4096)
    assert theoryframe._room(auto, {**s, "num_ctx": "auto"}) > 0 and auto.num_ctx > 4096   # automatic: raised


def test_a_local_model_too_small_for_the_frame_says_so_and_keeps_the_drafts(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _settings(num_ctx=8192, think="off")
    _started(ws, meadows, practice)
    be = LocalModel(8192)
    r = theoryframe.read(ws, be, "qwen3.5:9b")
    assert be.calls["theory_codes"] >= 2 and be.calls["theory_frame"] == 0   # the parts fit; the frame did not
    assert not r["ok"] and r["state"] == "read"
    d = theoryframe.load(ws)
    assert any("could not put the framework together" in p and "context length" in p and "16,384" in p
               for p in d["reading"]["problems"]), d["reading"]["problems"]
    assert d["groups"] == [] and "stock" in _by_name(d)                # the drafts, ungrouped


# ---------------------------------------------------------------------------------------------
# C2: a reading that ends short
# ---------------------------------------------------------------------------------------------
def test_a_reading_without_a_draft_is_refused(project):  # noqa: F811
    ws, _m, _p, _ev = project
    with pytest.raises(ValueError, match="start one first"):
        theoryframe.read(ws, FakeModel(), "claude-sonnet-5-5")


def test_a_document_removed_since_the_draft_began_is_said(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    ws.remove_document(practice)
    be = FakeModel()
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    assert "A document of this draft is no longer in the project." in r["problems"]
    assert be.calls["theory_codes"] >= 1 and all(practice not in json.dumps(p) for p in be.payloads)


def test_a_context_too_small_for_one_part_is_said_per_document(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _settings(num_ctx=6000, think="off")
    _started(ws, meadows, practice)
    be = LocalModel(6000)
    r = theoryframe.read(ws, be, "qwen3.5:9b")
    assert be.calls == {"theory_codes": 0, "theory_frame": 0}
    titles = {x["doc_id"]: x["title"] for x in ws.query("SELECT doc_id, title FROM documents")}
    for d in (meadows, practice):
        assert any(p.startswith(f"{titles[d]}: The context length") for p in r["problems"]), r["problems"]


def test_stop_ends_the_reading_and_keeps_what_the_draft_had(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    before = theoryframe.load(ws)
    be = FakeModel()
    r = theoryframe.read(ws, be, "claude-sonnet-5-5", should_stop=lambda: True)
    assert r["stopped"] and not r["ok"] and r["state"] == "none" and r["problems"] == []
    assert be.calls == {"theory_codes": 0, "theory_frame": 0}
    after = theoryframe.load(ws)
    assert after["concepts"] == before["concepts"] and after["reading"]["state"] == "none"

    # a framework read before stays when a second reading (another focus) is stopped
    assert theoryframe.read(ws, FakeModel(), "claude-sonnet-5-5")["ok"]
    groups = theoryframe.load(ws)["groups"]
    theoryframe.save(ws, {"focus": "something else entirely"})
    r = theoryframe.read(ws, FakeModel(), "claude-sonnet-5-5", should_stop=lambda: True)
    assert r["stopped"] and r["state"] == "read"
    d = theoryframe.load(ws)
    assert d["reading"]["state"] == "read" and d["groups"] == groups


class ClaudeCode:
    """Claude Code as the app waits for it: each task waits in the queue (taskqueue.wait_for), and `on_wait` is
    called at every look (what other programs do meanwhile); `stop` is the job's Stop."""

    name = "claude_code"
    progress = None

    def __init__(self, on_wait=lambda: None, stop=lambda: False):
        self.on_wait, self.stop = on_wait, stop

    def should_stop(self):
        self.on_wait()
        return self.stop()


def test_a_part_taken_back_from_the_queue_says_so(project):  # noqa: F811
    """Another job's Stop, or a document's setting changed while it waited, takes a part back from the queue: the
    reading ends and says why (unlike a Stop the person asked for, which is quiet)."""
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)

    def another_jobs_stop():
        taskqueue.withdraw(ws, kinds=["theory_codes"])

    r = theoryframe.read(ws, ClaudeCode(on_wait=another_jobs_stop), "sonnet")
    assert r["withdrawn"] and not r["stopped"] and r["state"] == "failed"
    assert r["problems"] == [theorycodes.WITHDRAWN]
    assert theoryframe.load(ws)["reading"]["problems"] == [theorycodes.WITHDRAWN]
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND status!='done'") == 0


def test_stop_while_claude_code_has_the_frame_takes_it_back_from_the_queue(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    assert theoryframe.read(ws, FakeModel(), "sonnet")["ok"]       # the parts are answered and kept
    theoryframe.save(ws, {"focus": "something else entirely"})       # so the frame is asked again

    def frame_waits():
        return bool(ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_frame' AND status!='done'"))

    with pytest.raises(BackendError):
        theoryframe.read(ws, ClaudeCode(stop=frame_waits), "sonnet", should_stop=frame_waits)
    # the frame no longer waits for Claude Code: nobody would ever take its answer
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_frame' AND status!='done'") == 0
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_frame'") == 1        # the first one is kept


def test_a_document_stricter_when_its_parts_are_sent_stays_out_of_the_frame(project, monkeypatch):  # noqa: F811
    """Its setting is worked out again as the text is about to leave: a document marked No AI by then (here: while
    the reading began from an older setting) sends nothing, and nothing of it goes to the frame either."""
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    access.set_documents(ws, [practice], "none")
    real = theorycodes._level
    monkeypatch.setattr(theorycodes, "_level", lambda w, d: "cloud" if d == practice else real(w, d))
    be = FakeModel()
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    title = ws.scalar("SELECT title FROM documents WHERE doc_id=?", (practice,))
    assert f"{title}: {theorycodes.NO_AI}" in r["problems"]
    assert all(practice not in json.dumps(p) for p in be.payloads) and be.calls["theory_frame"] == 1


def test_a_setting_changed_before_the_frame_is_sent_stops_the_frame(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)

    class ChangesItsMind(FakeModel):
        def complete(self, kind, system, user, model, payload):
            out = super().complete(kind, system, user, model, payload)
            left = ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND status!='done'")
            if kind == "theory_codes" and left <= 1:      # the last part: the person marks a document No AI
                access.set_documents(ws, [practice], "none")
            return out

    be = ChangesItsMind()
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    assert be.calls["theory_frame"] == 0 and not r["ok"]
    assert any("a document's AI setting changed" in p for p in r["problems"]), r["problems"]


# ---------------------------------------------------------------------------------------------
# C3: the evidence
# ---------------------------------------------------------------------------------------------
def test_evidence_without_words_or_an_index_offers_nothing(project, monkeypatch):  # noqa: F811
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    assert theoryframe.evidence(ws, {"name": "—", "words": ["…", "  "]}) == []
    from margin import search

    def no_index(*a, **kw):
        raise FileNotFoundError("no passage index yet")

    monkeypatch.setattr(search, "rank_passages", no_index)
    assert theoryframe.evidence(ws, {"name": "reinforcing loop", "words": ["reinforcing loop"]}) == []


def test_evidence_by_meaning_fills_what_the_words_leave_empty(project, tmp_path):  # noqa: F811
    ws, meadows, practice, ev = project
    d = tmp_path / "more"
    d.mkdir()
    same = ("The staff said that the residents grew less sure of the game, and the staff switched it on less every "
            "week in the care home.\n")
    (d / "fieldwork.txt").write_text("Working notes\n\n" + same, encoding="utf-8")
    (d / "chosen.txt").write_text("Field diary\n\n" + same.replace("every week", "each week"), encoding="utf-8")
    ingest.ingest(ws, [d])
    working = ws.scalar("SELECT doc_id FROM documents WHERE path LIKE '%fieldwork.txt'")
    chosen = ws.scalar("SELECT doc_id FROM documents WHERE path LIKE '%chosen.txt'")
    assert working and chosen
    docrole.set_role(ws, working, "working")
    # a document the draft was started from is never its own evidence, whatever its role
    theoryframe.start(ws, "Systems and practices", "lenses", "project", [meadows, practice, chosen], "")
    emb = HashEmbedder()
    embed.build(ws, emb)
    concept = {"name": "self-doubt", "words": ["zqxnothing"],
               "meaning": "The staff said the resident grew less sure of the game in the care home; a stock is "
                          "the memory of the history of changing flows; a practice is a routinised way."}
    assert theoryframe.evidence(ws, concept, k=3) == []             # the words find nothing
    got = theoryframe.evidence(ws, concept, k=3, embedder=emb)
    assert got and all(p["found_by"] == "meaning" and p["matched"] == [] for p in got)
    assert {p["doc_id"] for p in got} == {ev}   # never a theory document, a working one, or one of the draft's
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (ev,))
    assert all(" ".join(text[p["start"]:p["end"]].split()) == p["quote"] for p in got)


# ---------------------------------------------------------------------------------------------
# C4: a second reading into what the person made; saving; looking up; the codebook's descriptions
# ---------------------------------------------------------------------------------------------
def test_a_second_reading_keeps_the_persons_groups_and_sets_aside_what_does_not_fit(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    theoryframe.read(ws, FakeModel(), "claude-sonnet-5-5")
    d = theoryframe.load(ws)
    practices = next(g["key"] for g in d["groups"] if g["name"] == "Practices")
    groups = d["groups"] + [{"key": "mine", "name": "My lens", "about": "What I look for."}]
    own = [{"name": "Repair", "meaning": "Mending things.", "keep": True, "group": "mine"},
           {"name": "Habit", "meaning": "What is done without thinking.", "keep": True, "group": practices},
           {"name": "Loose", "meaning": "In no group any more.", "keep": True, "group": "gone"}]
    own += [{"name": f"Own concept {i}", "meaning": "One of mine.", "keep": True} for i in range(58 - len(own))]
    d = theoryframe.save(ws, {"groups": groups, "concepts": own})
    assert len(d["concepts"]) == 58
    theoryframe.save(ws, {"focus": "how care homes take up new technology"})   # another input: read again

    be = FakeModel()
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    assert r["ok"] and be.calls["theory_frame"] == 1
    d = theoryframe.load(ws)
    got = _by_name(d)
    by_key = {g["key"]: g["name"] for g in d["groups"]}
    assert by_key[got["repair"]["group"]] == "My lens"                  # the person's group is kept
    assert by_key[got["habit"]["group"]] == "Practices"                 # found again by its name
    assert got["loose"]["group"] == ""                                  # its group is gone
    # the person's 58 first, then the framework's 3 make 61: the one that does not fit is set aside, not dropped
    assert len(d["concepts"]) == theoryframe.MAX_CONCEPTS and list(got)[:58] == [
        theorycodes._norm(c["name"]) for c in own]
    framework = {"stock", "reinforcing loop", "practice"}
    in_draft = framework & set(got)
    aside = {theorycodes._norm(x["name"]) for x in d["left_out"]}
    assert len(in_draft) == 2 and (framework - in_draft) <= aside
    assert len({c["key"] for c in d["concepts"]}) == len(d["concepts"])   # every key once


def test_saving_refuses_what_is_no_draft_change(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    with pytest.raises(LookupError):
        theoryframe.save(ws, {"title": "x"})
    d = _started(ws, meadows, practice)
    with pytest.raises(ValueError, match="as an object"):
        theoryframe.save(ws, ["not", "a", "dict"])
    with pytest.raises(theoryframe.Stale):
        theoryframe.save(ws, {"rev": "an older one", "title": "x"})
    with pytest.raises(ValueError, match="groups as a list"):
        theoryframe.save(ws, {"groups": "one"})
    with pytest.raises(ValueError, match="concepts as a list"):
        theoryframe.save(ws, {"concepts": "one"})
    with pytest.raises(ValueError, match=f"at most {theoryframe.MAX_GROUPS} groups"):
        theoryframe.save(ws, {"groups": [{"key": f"g{i}", "name": f"G{i}"} for i in range(13)]})
    # a key the page made up badly, or twice, is given a free one; a name is always there
    got = theoryframe.save(ws, {"rev": d.get("rev"), "groups": [{"key": "g2", "name": "Two"},
                                                                {"key": "bad key!", "name": "Bad"},
                                                                {"key": "g2", "name": ""}]})["groups"]
    assert [g["name"] for g in got] == ["Two", "Bad", "Group"]
    assert got[0]["key"] == "g2" and len({g["key"] for g in got}) == 3 and "bad key!" not in {g["key"] for g in got}


GLOSSARY_TEXT = ("A primer\n\nFlow\n\n"
                 "The flow of water fills the tank. A flow can also drain it again. Every flow has a rate. "
                 "The flow we measure is a flow per hour. Nobody sees a flow directly.\n\n"
                 "Glossary\n\n"
                 "Flow: Material or information that enters or leaves a stock over a period of time.\n\n"
                 "Delay: The time between a change and its effect on the stock it changes.\n\n"
                 "Hierarchy: Systems organized in such a way as to create a larger system.\n")


def test_looking_a_term_up_finds_the_glossary_entry_first(tmp_path):
    ws, doc = _one_text(tmp_path, GLOSSARY_TEXT)
    try:
        got = theoryframe.lookup(ws, [doc, "not-a-document"], "flow")
        assert [s["doc_id"] for s in got["sources"]] == [doc]        # a document not in the project is passed over
        src = got["sources"][0]
        first = src["options"][0]
        assert first["score"] == 10 and first["quote"].startswith("Material or information that enters")
        assert src["uses"] >= 5 and len(src["options"]) == 3
    finally:
        ws.close_all()
    (tmp_path / "heading").mkdir()
    ws, doc = _one_text(tmp_path / "heading", "A primer\n\nFlow\n\nThe flow of water fills the tank. Tanks "
                          "are made of steel and of concrete. They stand on a hill above the old town.\n")
    try:   # a heading that names the term is no definition of it
        src = theoryframe.lookup(ws, [doc], "flow")["sources"][0]
        assert [o["quote"] for o in src["options"]] == ["The flow of water fills the tank."]
    finally:
        ws.close_all()


@pytest.mark.xfail(strict=True, reason="lookup offers a glossary entry twice: the line 'Flow: Material …' starts "
                                       "before the entry it holds, and only a start inside an option is checked")
def test_looking_a_term_up_offers_each_sentence_once(tmp_path):
    ws, doc = _one_text(tmp_path, GLOSSARY_TEXT)
    try:
        src = theoryframe.lookup(ws, [doc], "flow")["sources"][0]
        spans = sorted((o["start"], o["end"]) for o in src["options"])
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), src["options"]   # no option inside another
    finally:
        ws.close_all()


def test_a_concept_without_a_quote_is_described_by_its_meaning_or_use(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    titles = [ws.scalar("SELECT title FROM documents WHERE doc_id=?", (x,)) for x in (meadows, practice)]
    theoryframe.save(ws, {"concepts": [
        {"name": "Repair", "meaning": "Mending things.", "keep": True},
        {"name": "Waiting", "when_to_use": "When a passage tells of waiting.", "keep": True},
        {"name": "Bare", "keep": True}]})
    cb = theoryframe.make(ws)
    desc = {c["code"]: c["description"] for c in cb["codes"]}
    assert desc["Repair"] == "Mending things."
    assert desc["Waiting"] == "When a passage tells of waiting."
    assert desc["Bare"] == f"A concept of {titles[0]} and {titles[1]}."
