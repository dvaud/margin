"""0.18.4 (roadmap K2 part 2, the optional AI part): the AI drafts a theory document's concepts.

One `theory_codes` task per draft, given the document's Level-0 candidates and the passages where they are defined or
used most. Each concept comes back with a definition quoted exactly from the theory (the quote check sends a quote
that is not there back to be fixed), and joins the dialog's list unticked and marked as the AI's, without the Level-0
candidates already there. The document's own AI setting picks the reader (Claude, the local model, or none: no task);
a draft asked again with the same input reuses its answer (H4); examples still come only from the evidence."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

import pytest

import fake_claude_code as fcc
from margin import access, codebooks, docrole, ingest, taskqueue, tasks, theorycodes
from margin import home as ehome
from margin.llm import ClaudeCodeBackend
from test_codebook_from_theory import EVIDENCE, _theory_pdf

ROOT = Path(__file__).resolve().parent.parent
# a concept the theory defines that Level 0 does not offer under this name, and one it does ("Stock")
NEW_CONCEPT = ("Changing flows", "the memory of the history of changing flows")
SAME_CONCEPT = ("Stocks", "A stock is the memory of the history")


def _blocks(prompt: str) -> list[tuple[int, str]]:
    return [(int(n), " ".join(t.split())) for n, t in
            re.findall(r"^P(\d+)(?: \(page [^)]*\))?\n(.+?)(?=\n\nP\d+[ \n(]|\Z)", prompt, re.S | re.M)]


def _answer(prompt: str, concepts=(NEW_CONCEPT, SAME_CONCEPT)) -> dict:
    """What a helper answers: each concept with the passage its quote is in."""
    out = []
    for name, quote in concepts:
        n = next((n for n, t in _blocks(prompt) if quote.lower() in t.lower()), 1)
        out.append({"name": name, "definition": {"passage": n, "quote": quote}, "reason": "The theory defines it."})
    return {"concepts": out, "note": None}


class FakeModel:
    """A model server that drafts as `_answer` does and counts its calls. `local`: one on this computer."""

    def __init__(self, local: bool = False):
        self.name = "ollama" if local else "anthropic"
        if local:
            self.base_url = "http://127.0.0.1:11434"
        self.calls = 0

    def complete(self, kind, system, user, model, payload):
        assert kind == "theory_codes" and system.startswith("You draft the concepts of a theory document")
        self.calls += 1
        return json.dumps(_answer(user))


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    ehome.save_settings({**ehome.load_settings(), "backend": "anthropic", "allow_cloud": True, "embed_backend": "off"})
    ws = ehome.create_project("T")
    d = tmp_path / "docs"
    d.mkdir()
    _theory_pdf(d / "meadows.pdf")
    (d / "carehome.txt").write_text(EVIDENCE, encoding="utf-8")
    ingest.ingest(ws, [d])
    theory = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%memory of the history%'")
    evidence = ws.scalar("SELECT doc_id FROM documents WHERE doc_id != ?", (theory,))
    docrole.set_role(ws, theory, "theory")
    yield ws, theory, evidence
    ws.close_all()


def _ai_tasks(ws) -> list:
    return ws.query("SELECT * FROM tasks WHERE kind='theory_codes'")


def test_the_kind_is_registered_with_its_prompt_helper_and_row():
    from margin import prompts, routing, schema

    assert prompts.VERSIONS["theory_codes"] == "theory-codes-v2"
    assert routing.HELPERS["theory_codes"] == "margin-namer" and routing.CLAUDE_DEFAULTS["theory_codes"] == ("sonnet", "opus")
    assert routing.LOCAL_DEFAULTS["theory_codes"] == "large" and routing.ROW_OF["theory_codes"] == "theory_codes"
    assert "theory_codes" in taskqueue.ORDER and taskqueue.BATCH["theory_codes"] == 1
    assert set(schema.output_schema("theory_codes")["properties"]) == {"concepts", "note"}
    namer = (ROOT / "src/margin/claude_plugin/agents/margin-namer.md").read_text(encoding="utf-8")
    assert "theory_codes" in namer and "three whole words" in namer
    assert "theory_codes" in (ROOT / "src/margin/claude_plugin/SKILL.md").read_text(encoding="utf-8")


def test_a_task_for_a_cloud_theory_document_goes_to_claude_code_and_a_wrong_quote_comes_back(project):
    ws, theory, _ev = project
    ehome.save_settings({**ehome.load_settings(), "backend": "claude_code", "allow_claude_code": True})
    assert theorycodes.ai_offer(ws, theory) == {"offered": True, "why": None, "reader": "claude", "level": "cloud",
                                                "parts": 1}
    got: dict = {}

    def draft():
        with tasks.queueing(True):
            got["r"] = theorycodes.draft_with_ai(ws, theory, ClaudeCodeBackend(), "sonnet")

    th = threading.Thread(target=draft, daemon=True)
    th.start()
    for _ in range(200):  # until the task waits in the queue
        if ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND queued=1"):
            break
        th.join(0.05)
    t = _ai_tasks(ws)
    assert len(t) == 1 and t[0]["access"] == "cloud" and t[0]["queued"] == 1
    payload = json.loads(t[0]["payload_json"])
    assert payload["doc_id"] == theory and "Stock" in payload["candidates"]
    assert payload["part"] == payload["parts"] == 1 and payload["passages"]   # a short document: one part, all of it
    assert {ws.scalar("SELECT doc_id FROM passages WHERE passage_id=?", (p["passage_id"],)) for p in payload["passages"]} \
        == {theory}
    cc = fcc.FakeClaudeCode(fcc.DirectTools(), answer=lambda kind, system, prompt, model: _answer(prompt))
    cc.run("T")
    th.join(20)
    assert not th.is_alive()
    entry = next(e for e in cc.log if e["kind"] == "theory_codes")
    assert entry["helper"] == "margin-namer" and entry["model"] == "sonnet"
    assert entry["problems"] == 1 and entry["stored"] == 1  # the spoiled quote came back and was fixed
    r = got["r"]
    assert r["ok"] and [c["term"] for c in r["concepts"]] == ["Changing flows"]
    rows = ws.query("SELECT valid, errors_json, route, helper FROM results WHERE kind='theory_codes' ORDER BY attempt")
    assert [x["valid"] for x in rows] == [0, 1] and "quote not found" in rows[0]["errors_json"]
    assert rows[1]["route"] == "Claude Code" and rows[1]["helper"] == "margin-namer"


def test_a_quote_not_in_the_theory_or_too_short_is_rejected(project):
    ws, theory, _ev = project
    tid = theorycodes.make_ai_task(ws, theory, "claude-sonnet-5-5")
    bad = {"concepts": [{"name": "Stock", "definition": {"passage": 1, "quote": "a stock is a pile of money"},
                         "reason": "x"},
                        {"name": "Flow", "definition": {"passage": 1, "quote": "stock"}, "reason": "x"},
                        {"name": "Delay", "definition": {"passage": 99, "quote": "a delay in a balancing loop"},
                         "reason": "x"}]}
    ok, errors = tasks.ingest_result(ws, tid, json.dumps(bad), model="claude-sonnet-5-5")
    assert not ok and len(errors) == 3
    assert "quote not found in passage P1" in errors[0]
    assert "too short to define the concept" in errors[1]
    assert "there is no passage P99" in errors[2]
    assert ws.scalar("SELECT status FROM tasks WHERE task_id=?", (tid,)) == "retry"
    assert theorycodes.ai_drafts(ws, tid) == []


def test_a_model_that_never_quotes_the_theory_drafts_nothing(project):
    ws, theory, _ev = project

    class Wrong(FakeModel):
        def complete(self, kind, system, user, model, payload):
            self.calls += 1
            return json.dumps(_answer(user, (("Stock", "a stock is a pile of money"),)))

    model = Wrong()
    r = theorycodes.draft_with_ai(ws, theory, model, "claude-sonnet-5-5")
    assert r["ok"] is False and r["stopped"] is False and r["concepts"] == [] and model.calls == 3
    assert "quote not found" in r["problems"][0]
    log = ws.query("SELECT text FROM research_log WHERE kind='codebook-drafted'")
    assert len(log) == 1 and "could not draft" in log[0]["text"]


def test_no_task_for_a_document_marked_no_ai(project):
    ws, theory, _ev = project
    access.set_documents(ws, [theory], "none")
    offer = theorycodes.ai_offer(ws, theory)
    assert offer["offered"] is False and offer["why"] == theorycodes.NO_AI
    model = FakeModel()
    with pytest.raises(ValueError, match="marked No AI"):
        theorycodes.draft_with_ai(ws, theory, model, "claude-sonnet-5-5")
    assert model.calls == 0 and _ai_tasks(ws) == []


def test_only_a_local_ai_uses_the_local_model_and_never_claude(project, monkeypatch):
    ws, theory, _ev = project
    access.set_documents(ws, [theory], "local")
    cloud, local = FakeModel(), FakeModel(local=True)
    # without a local model chosen, the AI part is not offered, and says why
    assert theorycodes.ai_offer(ws, theory)["why"] == theorycodes.NO_LOCAL
    with pytest.raises(ValueError, match="no local AI is chosen"):
        theorycodes.draft_with_ai(ws, theory, cloud, "claude-sonnet-5-5")
    s = {**ehome.load_settings(), "restricted_server": "ollama", "restricted_model": "big",
         "ollama_url": "http://127.0.0.1:11434"}
    ehome.save_settings(s)
    monkeypatch.setattr(ehome, "make_restricted_backend", lambda settings: (local, "big"))
    assert theorycodes.ai_offer(ws, theory)["reader"] == "local"
    r = theorycodes.draft_with_ai(ws, theory, cloud, "claude-sonnet-5-5")
    assert r["ok"] and r["model"] == "big" and cloud.calls == 0 and local.calls == 1
    assert _ai_tasks(ws)[0]["access"] == "local"
    assert ws.scalar("SELECT route FROM results WHERE kind='theory_codes' AND valid=1") == "local model server"
    assert not access.ledger(ws, theory)  # nothing of it was sent off this computer


def test_a_repeat_with_the_same_input_reuses_the_kept_answer(project):
    ws, theory, _ev = project
    model = FakeModel()
    first = theorycodes.draft_with_ai(ws, theory, model, "claude-sonnet-5-5")
    assert first["ok"] and not first["reused"] and model.calls == 1
    again = theorycodes.draft_with_ai(ws, theory, model, "claude-sonnet-5-5")
    assert again["reused"] and model.calls == 1 and again["concepts"] == first["concepts"]
    assert len(_ai_tasks(ws)) == 1
    # the task gone (as when its id changes), the same question is answered from the kept answer (H4)
    with ws.connect() as cx:
        cx.execute("DELETE FROM results WHERE kind='theory_codes'")
        cx.execute("DELETE FROM tasks WHERE kind='theory_codes'")
    third = theorycodes.draft_with_ai(ws, theory, model, "claude-sonnet-5-5")
    assert third["reused"] and model.calls == 1 and [c["term"] for c in third["concepts"]] == ["Changing flows"]
    assert tasks.avoided(ws).get("theory_codes") == 1
    # each draft is in the research log, the kept ones said so
    log = ws.query("SELECT text, subject_id FROM research_log WHERE kind='codebook-drafted' ORDER BY at, rowid")
    assert len(log) == 3 and all(x["subject_id"] == theory for x in log)
    assert "kept from the same request before" in log[1]["text"] and "Changing flows" not in log[0]["text"]


def test_drafts_come_back_unticked_marked_and_without_the_level_0_candidates(project):
    ws, theory, evidence = project
    r = theorycodes.draft_with_ai(ws, theory, FakeModel(), "claude-sonnet-5-5")
    level0 = {c["term"] for c in theorycodes.candidates(ws, theory)["concepts"]}
    assert "Stock" in level0 and [c["term"] for c in r["concepts"]] == ["Changing flows"]  # "Stocks" is "Stock"
    c = r["concepts"][0]
    assert c["ai"] is True and c["how"] == "ai" and c["reason"] == "The theory defines it."
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (theory,))
    d = c["definition"]
    assert " ".join(text[d["start"]:d["end"]].split()).lower() == NEW_CONCEPT[1] and d["page"] == 1
    assert c["code"]["description"].startswith(f"“{d['quote']}” (Thinking in systems, p. 1)")
    assert c["ticked"] is False
    # the dialog: AI drafts are never ticked (only the terms Level 0 says are: `ticked`), and are marked "AI draft"
    js = (ROOT / "src/margin/gui/static/views/codebooks.js").read_text(encoding="utf-8")
    assert 'c.how === "defined") && !c.ai' in js and "c.ticked" in js and '"AI draft"' in js and '"Draft with AI"' in js


def test_examples_still_come_only_from_the_evidence(project):
    ws, theory, evidence = project
    r = theorycodes.draft_with_ai(ws, theory, FakeModel(), "claude-sonnet-5-5")
    answer = ws.scalar("SELECT raw_json FROM results WHERE kind='theory_codes' AND valid=1")
    assert "example" not in answer.lower()  # the AI gives none
    for c in r["concepts"]:
        assert not c["code"]["examples"] and all(e["doc_id"] == evidence for e in c["suggested"])
    # an AI draft kept with an example from the evidence keeps it; one from the theory, smuggled in, is dropped
    good = theorycodes.suggest_examples(ws, "reinforcing loop")
    assert good and all(e["doc_id"] == evidence for e in good)
    code = {**theorycodes._draft_code("Reinforcing loop", None, "Thinking in systems"),
            "examples": [good[0], {"quote": "A reinforcing loop can make a stock grow", "doc_id": theory,
                                   "title": "Thinking in systems", "page": 2, "start": 0, "end": 10}]}
    cb = codebooks.create(ws, "from_ai", "From the AI", start="theory", source={"doc_id": theory, "codes": [code]})
    assert [e["doc_id"] for c in cb["codes"] for e in c["examples"]] == [evidence]


def test_the_routes_offer_it_and_run_it_as_a_job(api, tmp_path):  # noqa: F811
    from margin.store import Workspace

    from test_codebook_from_theory import THEORY_PAGES

    assert api("PUT", "/api/settings", {"backend": "baseline", "embed_backend": "off"})[0] == 200
    assert api("POST", "/api/projects", {"name": "Lens"})[0] == 200
    d = tmp_path / "in"
    d.mkdir()
    (d / "meadows.txt").write_text("Thinking in systems\n\n" + "\n\n".join("\n\n".join(p) for p in THEORY_PAGES),
                                   encoding="utf-8")
    (d / "carehome.txt").write_text(EVIDENCE, encoding="utf-8")
    ws = Workspace.open(ehome.project_path("Lens"))
    try:
        ingest.ingest(ws, [d])
        theory = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%memory of the history%'")
        evidence = ws.scalar("SELECT doc_id FROM documents WHERE doc_id != ?", (theory,))
        docrole.set_role(ws, theory, "theory")
    finally:
        ws.close_all()
    base = f"/api/projects/Lens/codebook-theory/{theory}/ai"
    st, offer = api("GET", base)
    assert st == 200 and offer["offered"] is True and offer["why"] is None
    st, r = api("POST", base)
    assert st == 200 and r["job"]["kind"] == "theory-codes"
    job = api.wait(r["job"]["id"])
    assert job["state"] == "done", job
    got = job["result"]
    # the offline demo offers the Level-0 candidates the passages use: the terms the theory defines itself are left
    # out as repeats (a heading or a frequent word may come back with the sentence the draft chose)
    assert got["ok"] and got["model"] and all(c["ai"] and c["how"] == "ai" for c in got["concepts"])
    assert got["parts"] == got["parts_read"] == 1 and offer["parts"] == 1
    level0 = {c["term"].lower() for c in api("GET", f"/api/projects/Lens/codebook-theory/{theory}")[1]["concepts"]
              if c["how"] in ("glossary", "defined")}
    assert level0 and not {c["term"].lower() for c in got["concepts"]} & level0
    assert all(e["doc_id"] == evidence for c in got["concepts"] for e in c["suggested"])
    # a document marked No AI: not offered, and the draft is refused in one line
    ws = Workspace.open(ehome.project_path("Lens"))
    try:
        access.set_documents(ws, [theory], "none")
    finally:
        ws.close_all()
    st, offer = api("GET", base)
    assert st == 200 and offer == {"offered": False, "why": theorycodes.NO_AI, "reader": None, "level": "none"}
    st, body = api("POST", base)
    assert st == 400 and "No AI" in json.dumps(body)
    assert api("GET", "/api/projects/Lens/codebook-theory/nope/ai")[0] == 404


from test_app import api, home  # noqa: E402,F401  (fixtures)


def test_a_definition_needs_three_whole_words_and_more_than_the_name(project):
    """Review of 0.18.4: two long words passed the judgement rule (3 words or 15 characters); a definition needs words."""
    ws, theory, _ev = project
    tid = theorycodes.make_ai_task(ws, theory, "claude-sonnet-5-5")
    ps = [" ".join(p["text"].split()) for p in theorycodes.ai_payload(ws, theory)["passages"]]
    n, two = next((i + 1, f"{a} {b}") for i, t in enumerate(ps) for a, b in zip(t.split(), t.split()[1:])
                  if len(f"{a} {b}") >= 15)
    bad = {"concepts": [{"name": "Long words", "definition": {"passage": n, "quote": two}, "reason": "x"},
                        {"name": "memory of the history", "definition": {"passage": 1, "quote": "memory of the history"},
                         "reason": "x"}]}
    ok, errors = tasks.ingest_result(ws, tid, json.dumps(bad), model="claude-sonnet-5-5")
    assert not ok and len(errors) == 2
    assert "at least 3 whole words" in errors[0]
    assert "only repeats the concept's name" in errors[1]


def test_a_draft_taken_back_says_so_and_a_stop_stays_quiet(project, monkeypatch):
    ws, theory, _ev = project
    monkeypatch.setattr(tasks, "run_one", lambda *a, **k: (False, ["taken back from the queue"]))
    r = theorycodes.draft_with_ai(ws, theory, FakeModel(), "claude-sonnet-5-5")
    assert r["ok"] is False and r["stopped"] is False and r["withdrawn"] is True and r["why"] == theorycodes.WITHDRAWN
    r = theorycodes.draft_with_ai(ws, theory, FakeModel(), "claude-sonnet-5-5", should_stop=lambda: True)
    assert r["stopped"] is True and r["withdrawn"] is False and r["why"] is None
    assert ws.query("SELECT 1 FROM research_log WHERE kind='codebook-drafted'") == []


# ---- theory-codes-v2: the whole document is read, a part at a time -------------------------------------------------
_PLACES = ("mill", "ferry", "orchard", "quarry", "harbour", "market", "chapel", "smithy", "tannery", "bakery",
           "vineyard", "pasture", "granary", "sawmill", "pottery", "brewery", "dairy", "foundry", "nursery", "wharf")
_FOLK = ("carters", "weavers", "millers", "shepherds", "masons", "coopers", "fishers", "tailors", "farriers", "glaziers")


def _filler(n: int, word: str) -> str:
    """`n` paragraphs of plain prose that define nothing, no two alike (a line repeated is taken for a running head)."""
    return "\n\n".join(f"The {word} at the {_PLACES[i % 20]} went on as before among the {_FOLK[(i // 20) % 10]}, and "
                        f"nobody wrote about what happened that season or why the harvest came late again."
                        for i in range(n))


LONG_THEORY = ("A long theory\n\n"
               "A stock is the memory of the history of changing flows within the system.\n\n"
               + _filler(190, "work") + "\n\n"
               "Bounded rationality means that people decide reasonably on the little they know.\n\n"
               + _filler(95, "trade") + "\n\n"
               "The commons is the ground that everyone may use and nobody owns.\n\n"
               + _filler(95, "craft") + "\n\n"
               "In the end bounded rationality is what makes each actor do the sensible thing for himself.\n\n"
               "A leverage point is a place in a system where a small shift changes a great deal.\n")
LONG_CONCEPTS = (("Bounded rationality", "Bounded rationality means that people decide reasonably on the little they know"),
                 ("bounded rationality", "bounded rationality is what makes each actor do the sensible thing"),
                 ("Leverage point", "A leverage point is a place in a system where a small shift changes a great deal"),
                 ("Commons", "The commons is the ground that everyone may use and nobody owns"))


@pytest.fixture
def long_project(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    ehome.save_settings({**ehome.load_settings(), "backend": "anthropic", "allow_cloud": True, "embed_backend": "off"})
    ws = ehome.create_project("Long")
    d = tmp_path / "docs"
    d.mkdir()
    (d / "long.txt").write_text(LONG_THEORY, encoding="utf-8")
    (d / "carehome.txt").write_text(EVIDENCE, encoding="utf-8")
    ingest.ingest(ws, [d])
    theory = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%Bounded rationality means%'")
    docrole.set_role(ws, theory, "theory")
    yield ws, theory
    ws.close_all()


class PartModel(FakeModel):
    """Drafts, from each part, the concepts of LONG_CONCEPTS whose quotes that part holds; `spoil`: the parts (by
    number) whose quotes it gets wrong every time."""

    def __init__(self, spoil=()):
        super().__init__()
        self.spoil = set(spoil)
        self.parts = []

    def complete(self, kind, system, user, model, payload):
        self.calls += 1
        self.parts.append(payload["part"])
        here = [(n, q) for n, q in LONG_CONCEPTS if any(q.lower() in " ".join(t.split()).lower() for _n, t in _blocks(user))]
        ans = _answer(user, here)
        if payload["part"] in self.spoil:
            for c in ans["concepts"]:
                c["definition"]["quote"] = "words that are nowhere in the theory at all"
        return json.dumps(ans)


def test_a_long_document_is_read_whole_in_parts_and_the_drafts_are_put_together(long_project):
    ws, theory = long_project
    payloads = theorycodes.ai_payloads(ws, theory)
    n = len(payloads)
    assert n >= 3 and [p["part"] for p in payloads] == list(range(1, n + 1)) and {p["parts"] for p in payloads} == {n}
    assert all(sum(len(x["text"]) for x in p["passages"]) <= theorycodes.AI_MAX_CHARS for p in payloads)
    # every body passage of the document is in one part, once, in order
    sent = [x["passage_id"] for p in payloads for x in p["passages"]]
    body = [r[0] for r in ws.query("SELECT passage_id FROM passages WHERE doc_id=? AND section='body' ORDER BY start",
                                   (theory,))]
    assert sent == body and theorycodes.ai_offer(ws, theory)["parts"] == n
    from margin import prompts
    assert f"(part 2 of {n})" in prompts.user_prompt("theory_codes", payloads[1])
    model = PartModel()
    seen = []
    r = theorycodes.draft_with_ai(ws, theory, model, "claude-sonnet-5-5", progress=lambda a, b: seen.append((a, b)))
    assert r["ok"] and r["parts"] == r["parts_read"] == n and len(r["task_ids"]) == n and model.parts == list(range(1, n + 1))
    assert seen[0] == (0, n) and seen[-1] == (n, n)
    got = {c["term"]: c for c in r["concepts"]}
    # drafted from two parts: offered once, the most central first, with the sentence that defines it
    assert list(got)[0] == "Bounded rationality" and len(got["Bounded rationality"]["parts"]) == 2
    assert got["Bounded rationality"]["definition"]["quote"].startswith("Bounded rationality means")
    # "Stock" the document defines itself: not offered again; the others are, each once
    assert set(got) == {"Bounded rationality", "Leverage point", "Commons"}
    log = ws.query("SELECT text FROM research_log WHERE kind='codebook-drafted'")[0][0]
    assert f"in {n} parts" in log and "drafted 3 concepts" in log
    # asked again: every part's answer is kept, no model is called
    again = theorycodes.draft_with_ai(ws, theory, model, "claude-sonnet-5-5")
    assert again["reused"] and model.calls == n and [c["term"] for c in again["concepts"]] == list(got)


def test_a_part_whose_quotes_are_never_found_is_left_out_and_said(long_project):
    ws, theory = long_project
    n = len(theorycodes.ai_payloads(ws, theory))
    last = n   # the last part holds "leverage point" and the second sentence on bounded rationality
    r = theorycodes.draft_with_ai(ws, theory, PartModel(spoil={last}), "claude-sonnet-5-5")
    assert r["ok"] and r["parts"] == n and r["parts_read"] == n - 1 and r["problems"]
    assert "Leverage point" not in {c["term"] for c in r["concepts"]}
    assert "Bounded rationality" in {c["term"] for c in r["concepts"]}
    log = ws.query("SELECT text FROM research_log WHERE kind='codebook-drafted'")[0][0]
    assert f"1 of the {n} parts could not be read" in log


def test_every_part_waits_in_the_claude_code_queue_at_once(long_project):
    ws, theory = long_project
    ehome.save_settings({**ehome.load_settings(), "backend": "claude_code", "allow_claude_code": True})
    n = len(theorycodes.ai_payloads(ws, theory))
    got: dict = {}
    th = threading.Thread(target=lambda: got.update(r=theorycodes.draft_with_ai(ws, theory, ClaudeCodeBackend(), "sonnet")),
                          daemon=True)
    th.start()
    for _ in range(200):
        if ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND queued=1") == n:
            break
        th.join(0.05)
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND queued=1") == n   # before any is answered
    cc = fcc.FakeClaudeCode(fcc.DirectTools(), answer=lambda kind, system, prompt, model: _answer(
        prompt, [(a, q) for a, q in LONG_CONCEPTS if q.lower() in " ".join(prompt.split()).lower()]))
    cc.run("Long")
    th.join(30)
    assert not th.is_alive() and got["r"]["ok"] and got["r"]["parts_read"] == n
    assert "Bounded rationality" in {c["term"] for c in got["r"]["concepts"]}


def test_a_part_fits_the_context_length_of_a_model_on_this_computer(long_project):
    """The app sizes a local model's automatic context length for a check's excerpts (8,192 tokens): a part of a book
    does not fit it, and the first version's draft failed there. Automatic: raised to hold a whole part. Set by the
    person: the parts are made to fit; too small for any part: said in one line."""
    ws, theory = long_project

    class Local:
        name = "ollama"
        num_ctx = 8192

    auto = {**ehome.load_settings(), "num_ctx": "auto", "think": "default"}
    be = Local()
    assert theorycodes._part_chars(be, auto) == theorycodes.AI_MAX_CHARS and be.num_ctx == 16384
    assert theorycodes._part_chars(object(), auto) == theorycodes.AI_MAX_CHARS      # Claude: no context length to fit
    # a context length the person set, reasoning off: smaller parts, more of them, every passage still read once
    be = Local()
    fixed = {**auto, "num_ctx": 8192, "think": "off"}
    small = theorycodes._part_chars(be, fixed)
    assert be.num_ctx == 8192 and theorycodes.AI_MIN_CHARS <= small < theorycodes.AI_MAX_CHARS
    few, many = theorycodes.ai_payloads(ws, theory), theorycodes.ai_payloads(ws, theory, small)
    assert len(many) > len(few)
    assert [x["passage_id"] for p in many for x in p["passages"]] == [x["passage_id"] for p in few for x in p["passages"]]
    from margin import prompts
    from margin.llm import OUTPUT_CAP, estimate_tokens
    for p in many:   # as the local backend counts it: the prompt, a retry's problems and the answer fit
        need = estimate_tokens(prompts.system_prompt("theory_codes")) + estimate_tokens(prompts.user_prompt("theory_codes", p)) \
            + estimate_tokens("x" * 1600) + OUTPUT_CAP["theory_codes"]
        assert need <= 8192, need
    # with room kept for a reasoning model nothing fits 8,192 tokens: one line that says what to change
    with pytest.raises(ValueError, match="too small to read a theory document"):
        theorycodes._part_chars(Local(), {**fixed, "think": "default"})


def test_a_stop_while_a_part_waits_for_claude_code_takes_the_other_parts_out_of_the_queue(long_project):
    """Stop arrives inside the wait for a part (the wait raises): the parts not read must not stay in the queue for
    the helpers to go on answering."""
    from margin.llm import BackendError

    ws, theory = long_project
    ehome.save_settings({**ehome.load_settings(), "backend": "claude_code", "allow_claude_code": True})
    n = len(theorycodes.ai_payloads(ws, theory))
    stop = threading.Event()
    be = ClaudeCodeBackend()
    be.should_stop = stop.is_set
    raised: list = []

    def draft():
        try:
            theorycodes.draft_with_ai(ws, theory, be, "sonnet", should_stop=stop.is_set)
        except BackendError as e:
            raised.append(str(e))

    th = threading.Thread(target=draft, daemon=True)
    th.start()
    for _ in range(200):
        if ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND queued=1") == n:
            break
        th.join(0.05)
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND queued=1") == n
    stop.set()
    th.join(20)
    assert not th.is_alive() and raised == ["Stopped."]
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND queued=1") == 0


def test_a_concept_named_in_another_script_does_not_break_the_draft(project):
    """The name comes as the document writes it: one without a Latin letter must not stop the drafts being put
    together (it did: the search for the name in the text had no word to look for)."""
    ws, theory, _ev = project
    model = FakeModel()
    model.complete = lambda kind, system, user, m, payload: json.dumps(_answer(user, (
        ("Обратная связь", "the memory of the history of changing flows"), ("反馈回路", "Stocks change only through flows"),
        NEW_CONCEPT)))
    r = theorycodes.draft_with_ai(ws, theory, model, "claude-sonnet-5-5")
    assert r["ok"] and {c["term"] for c in r["concepts"]} == {"Обратная связь", "反馈回路", "Changing flows"}
    assert theorycodes._term_rx("…").search("anything") is None
