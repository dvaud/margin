"""I6, local model tiers chosen for you; no model is loaded anywhere here (stand-ins answer for Ollama).

- the small tier's short answer form `point` (pointing.py): numbered sentences, the schema bounded by the task, the
  marks cleaned, Margin cutting the quote; K2's real answers from the bench replayed (tests/data/k2_pointer_replay.json);
- suggestions only: a check a local model read waits for the person, whose judgements alone set its status, in the
  result, the checks list and the Excel rows; a local reading of before I6 keeps counting, and the result says so;
- the memory guard of long runs (fake /api/ps readings), the job's end letting go of an MLX model;
- what made each answer: the engine (runner, quantisation, Ollama's version), the Engine column and the note in "How
  these results were made", `repeatable` saying "not guaranteed" for MLX without asking the model;
- the result page's card for a suggestion (Node, tests/_views.py).
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse

import pytest

from _views import needs_node, run_views
from margin import claimcheck, llm, pointing, runs, schema, tasks
from margin.llm import AnswerError, OllamaBackend

GB = 1 << 30
K2, QWEN = "ifm/k2-horizon:0.9b", "qwen3.5:4b"
REAL_LET_GO = llm.let_go   # taken before the conftest's stand-in replaces it for each test
REPLAY = json.loads((Path(__file__).parent / "data" / "k2_pointer_replay.json").read_text(encoding="utf-8"))["checks"]


# ---------------------------------------------------------------------------------------------- a stand-in Ollama
class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Stream:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self.lines)

    def close(self):
        pass


class FakeOllama:
    """Answers OllamaBackend's requests like Ollama 0.40.16 on this Mac (18 November 2026): /api/tags with each model's
    runner and quantisation, /api/ps with the memory each loaded model holds, /api/version, /api/show; /api/chat
    streams `answer` (and loads the model: it is then listed by /api/ps); /api/generate with keep_alive 0 unloads."""

    MODELS = {K2: {"size": int(1.07 * GB), "runner": "llamacpp", "quantization_level": "Q8_0", "format": "gguf"},
              QWEN: {"size": int(3.7 * GB), "runner": "mlx", "quantization_level": "nvfp4", "format": "safetensors"}}

    def __init__(self):
        self.calls: list[tuple[str, dict | None]] = []
        self.held: dict[str, int] = {}
        self.grow = 0            # what each answer adds to the model's memory (the MLX prompt cache)
        self.ps_down = False
        self.answer = '{"marks": []}'
        self.done_reason = "stop"
        self.logprobs = None

    def paths(self, path):
        return [b for p, b in self.calls if p == path]

    def __call__(self, req, timeout=None):
        path = urlparse(req.full_url).path
        body = json.loads(req.data.decode()) if req.data else None
        self.calls.append((path, body))
        if path == "/api/tags":
            return _Resp(json.dumps({"models": [
                {"name": n, "model": n, "size": m["size"], "digest": f"sha-{n}",
                 "details": {"runner": m["runner"], "quantization_level": m["quantization_level"], "format": m["format"]}}
                for n, m in self.MODELS.items()]}).encode())
        if path == "/api/ps":
            if self.ps_down:
                raise URLError("connection refused")
            return _Resp(json.dumps({"models": [{"name": n, "model": n, "size": s, "size_vram": s}
                                                for n, s in self.held.items()]}).encode())
        if path == "/api/version":
            return _Resp(b'{"version": "0.40.16"}')
        if path == "/api/show":
            return _Resp(b'{"capabilities": ["completion"]}')
        if path == "/api/generate":
            assert body["keep_alive"] == 0, "only an unload is asked here"
            self.held.pop(body["model"], None)
            return _Resp(b"{}")
        if path == "/api/chat":
            m = body["model"]
            self.held[m] = self.held.get(m, int(self.MODELS[m]["size"] * 1.1)) + (self.grow if m in self.held else 0)
            if not body.get("stream"):   # p_yes: one token with its log-probabilities
                return _Resp(json.dumps({"message": {"content": "yes"}, "logprobs": self.logprobs or []}).encode())
            lines = [json.dumps({"message": {"content": self.answer}}).encode() + b"\n",
                     json.dumps({"done": True, "done_reason": self.done_reason, "eval_count": 9,
                                 "prompt_eval_count": 50}).encode() + b"\n"]
            return _Stream(lines)
        raise AssertionError(f"unexpected request {path}")


def _passages(n, sentences=3):
    return [{"passage_id": f"d{i}:0001", "doc_id": f"d{i}", "title": f"Report {i}", "page": 1,
             "text": " ".join(f"Sentence {j} of passage {i} says something." for j in range(1, sentences + 1))}
            for i in range(1, n + 1)]


# ---------------------------------------------------------------------------------------------- the pointer form
def test_sentences_are_numbered_with_the_app_splitter_and_run_on_sentences_are_cut():
    text = "Short one. " + "A clause about water use, " * 20 + "and the end; then another long part, " * 6 + "done."
    spans = pointing.sentences(text)
    assert text[spans[0][0]:spans[0][1]] == "Short one."
    assert all(b - a <= pointing.LONG_SENTENCE + 40 for a, b in spans[1:])   # a run-on PDF paragraph is cut
    assert "".join(text[a:b] for a, b in spans).replace(" ", "") == text.replace(" ", "")   # nothing lost, in order
    user = pointing.user_prompt({"claim": "Water use rises.", "passages": [{"text": "One. Two here."}]})
    assert user == "CLAIM: Water use rises.\n\nP1\n<s1> One. <s2> Two here."   # never [1]: citations look like that


def test_the_schema_is_bounded_by_the_task_and_the_cap_by_its_excerpts():
    payload = {"passages": _passages(8, sentences=3) + [{"text": "One here. Two here. Three. Four here. Five."}]}
    s = schema.output_schema("point", payload)
    marks = s["properties"]["marks"]
    assert marks["maxItems"] == 9 and marks["items"]["properties"]["p"]["enum"] == list(range(1, 10))
    assert marks["items"]["properties"]["s"]["maximum"] == 5 and marks["items"]["required"] == ["p", "s"]
    assert schema.output_schema("point")["properties"]["marks"]["maxItems"] == pointing.MAX_PASSAGES
    # the cap follows k: the schema allows a mark for every excerpt, so 20 or 40 excerpts are not cut off
    assert pointing.cap(8) == 24 + 14 * 8 == 136 and pointing.cap(40) == 584 and pointing.cap(60) == pointing.OUTPUT_CAP
    # every tier: the search words are bounded too (the prompt says "at most 20")
    terms = schema.output_schema("expand")["properties"]["terms"]
    assert terms["maxItems"] == 20 and terms["items"]["maxLength"] == 60


def test_marks_out_of_range_or_repeated_are_dropped_and_the_reading_order_follows_the_model():
    payload = {"passages": _passages(4)}
    got = pointing.marks({"marks": [{"p": 3, "s": 2}, {"p": 9, "s": 1}, {"p": 1, "s": 7}, {"p": 3, "s": 1},
                                    {"p": 2, "s": 1}, {"p": "x", "s": 1}]}, payload)
    assert [(m["passage"], m["sentence"], m["rank"]) for m in got] == [(2, 1, 1), (1, 0, 2)]
    assert got[0]["quote"] == "Sentence 2 of passage 3 says something."
    assert payload["passages"][2]["text"][got[0]["start"]:got[0]["end"]] == got[0]["quote"]
    assert pointing.reading_order(4, got) == [2, 1, 0, 3]
    assert pointing.marks({"evidence": []}, payload) == [] and pointing.marks(None, payload) == []


def test_the_lean_is_off_and_follows_its_thresholds_once_measured():
    assert pointing.LEAN is False   # until handhold_lp.py has run with opposites written by the model (roadmap I6)
    assert pointing.lean(0.8, 0.6) == "may support" and pointing.lean(0.5, 0.65) == "may contradict"
    assert pointing.lean(0.55, 0.5) is None and pointing.lean(None, 0.2) is None


@pytest.mark.parametrize("check", REPLAY, ids=[c["id"] for c in REPLAY])
def test_k2s_real_pointer_answers_from_the_bench_become_quotes_in_the_excerpt(check):
    """K2 pointed at one sentence per excerpt in the bench; numbered by Margin's own splitter, each becomes a mark
    whose quote Margin cuts from the excerpt itself: in the excerpt by construction, the sentence K2 chose."""
    norm = lambda s: " ".join(s.split())  # noqa: E731
    payload = {"claim": check["claim"], "passages": check["passages"]}
    answer = {"marks": []}
    for row in check["k2"]:
        spans = pointing.sentences(check["passages"][row["p"] - 1]["text"])
        text = check["passages"][row["p"] - 1]["text"]
        s = next(i for i, (a, b) in enumerate(spans, 1) if norm(row["k2_sentence"])[:40] in norm(text[a:b]))
        answer["marks"].append({"p": row["p"], "s": s})
    got = pointing.marks(answer, payload)
    assert len(got) == len(check["k2"])
    for m, row in zip(got, check["k2"]):
        assert m["quote"] in check["passages"][m["passage"]]["text"]
        assert norm(row["k2_sentence"])[:40] in norm(m["quote"])
    # its answer is short: about 12 tokens a mark, well inside the cap that cut its check answers off
    assert llm.estimate_tokens(json.dumps(answer)) <= pointing.cap(len(check["passages"]))


def test_the_backend_sends_the_bounded_schema_and_the_tight_cap_and_a_cut_answer_is_asked_again():
    fake = FakeOllama()
    be = OllamaBackend("http://localhost:11434", num_ctx=8192, opener=fake, think=False)
    payload = {"claim": "Water use rises.", "passages": _passages(8)}
    fake.answer = '{"marks": [{"p": 2, "s": 1}]}'
    text = be.complete("point", pointing.system_prompt(), pointing.user_prompt(payload), K2, payload)
    assert json.loads(text) == {"marks": [{"p": 2, "s": 1}]}
    body = fake.paths("/api/chat")[-1]
    assert body["options"]["num_predict"] == 24 + 14 * 8 and body["format"] == pointing.schema(payload)
    assert body["options"]["temperature"] == 0 and body["options"]["seed"] == 42
    fake.done_reason = "length"
    with pytest.raises(AnswerError):
        be.complete("point", pointing.system_prompt(), pointing.user_prompt(payload), K2, payload)


def test_p_yes_reads_the_probability_of_yes_from_the_first_tokens_log_probabilities():
    fake = FakeOllama()
    fake.logprobs = [{"token": "yes", "top_logprobs": [{"token": "yes", "logprob": math.log(0.6)},
                                                       {"token": " No", "logprob": math.log(0.2)},
                                                       {"token": "maybe", "logprob": math.log(0.1)}]}]
    be = OllamaBackend("http://localhost:11434", opener=fake)
    assert be.p_yes(K2, "Does this passage say that water use rises?") == pytest.approx(0.75)
    body = fake.paths("/api/chat")[-1]
    assert body["options"]["num_predict"] == 1 and body["logprobs"] is True and body["think"] is False
    assert "format" not in body and body["stream"] is False
    fake.logprobs = []
    assert be.p_yes(K2, "Does it?") is None


# ---------------------------------------------------------------------------------------------- suggestions only
class LocalStandIn:
    """A model on this computer (its route is "local model server"), answering checks as it is asked: in the check
    form with a lean for the first excerpt, or (the small tier) in the point form."""

    name = "ollama"
    base_url = "http://localhost:11434"
    seed = 42

    def __init__(self, marks=None):
        self.kinds: list[str] = []
        self.marks = marks

    def digest(self, model):
        return f"sha-{model}"

    def complete(self, kind, system, user, model, payload):
        self.kinds.append(kind)
        if kind == "point":
            return json.dumps({"marks": self.marks if self.marks is not None else [{"p": 2, "s": 1}]})
        if kind in ("check", "reread"):
            words = " ".join(payload["passages"][0]["text"].split()[:6])
            return json.dumps({"evidence": [{"passage": 1, "verdict": "supports", "confidence": 0.95, "quote": words,
                                             "scope_note": None, "refers_to": None}], "rationale": "One supports it."})
        return json.dumps({"terms": ["water"]})


CLAIM = "Green hydrogen production can increase water stress in arid regions."


def _row(ws, hid):
    return next(h for h in claimcheck.history(ws) if h["hyp_id"] == hid)


def test_a_check_read_by_the_local_model_waits_for_you_and_your_judgements_alone_decide(loaded):
    be = LocalStandIn()
    cid = claimcheck.check_claim(loaded, CLAIM, be, QWEN, k=3, expand=False)
    assert be.kinds == ["check"]
    r = claimcheck.result(loaded, cid)
    # the local model suggested "supports" for one excerpt: shown, no confidence, counting for nothing
    assert r["status"] == "not_checked" and r["status_text"] == claimcheck.WAITING_YOU
    assert r["suggestions"] == len(r["passages"]) == r["waiting_for_you"] and r["local_counted"] == 0
    lean = [x for x in r["passages"] if x["suggestion"]["lean"]]
    assert len(lean) == 1 and lean[0]["ai_verdict"] == "supports" and lean[0]["confidence"] is None
    assert lean[0]["certainty"] == "" and not lean[0]["counted"] and lean[0]["verdict"] is None
    assert lean[0]["quote"] and lean[0]["quote_start"] is not None   # its highlight is shown as now
    assert r["balance"]["docs_counted"] == 0
    # the checks list, the Excel rows and the overview say the same
    row = _row(loaded, cid)
    assert row["status"] == "not_checked" and row["status_text"] == claimcheck.WAITING_YOU
    assert (row["supports"], row["docs_supporting"]) == (0, 0)
    xl = [x for x in claimcheck.export_table(loaded) if x["Hypothesis"] == CLAIM]
    assert xl and all(x["Judged by"] == "nobody yet" and x["Judgement"] == "Not judged yet" for x in xl)
    assert any("it suggests supports" in x["AI's own judgement"] for x in xl)
    assert claimcheck.evidence_map(loaded)["cells"].get(cid, {}) == {}
    # the person agrees: now it counts, as their own judgement
    claimcheck.set_judgement(loaded, cid, lean[0]["passage_id"], "supports")
    r = claimcheck.result(loaded, cid)
    assert r["status"] == "supported" and r["suggestions"] == len(r["passages"]) - 1
    assert _row(loaded, cid)["status"] == "supported"
    # a person's "not about this" on the others settles them: nothing waits any more
    for x in r["passages"]:
        if not x["user_verdict"]:
            claimcheck.set_judgement(loaded, cid, x["passage_id"], "not_relevant")
    r = claimcheck.result(loaded, cid)
    assert r["status"] == "supported" and r["waiting_for_you"] == 0 and r["suggestions"] == 0


def test_a_local_reading_of_before_i6_keeps_counting_and_the_result_says_so(loaded):
    cid = claimcheck.check_claim(loaded, CLAIM, LocalStandIn(), QWEN, k=3, expand=False)
    with loaded.connect() as cx:   # as a project made before I6 holds it: no suggestion mark
        cx.execute("UPDATE verifications SET suggestion_json=NULL WHERE subject_id=?", (cid,))
    r = claimcheck.result(loaded, cid)
    assert r["status"] == "supported" and r["local_counted"] == 1 and r["suggestions"] == 0   # not changed in silence
    x = next(p for p in r["passages"] if p["local_counted"])
    claimcheck.set_judgement(loaded, cid, x["passage_id"], "supports")       # reviewed: it is the person's now
    assert claimcheck.result(loaded, cid)["local_counted"] == 0


def test_claude_reading_a_suggestion_again_makes_it_count(loaded):
    cid = claimcheck.check_claim(loaded, CLAIM, LocalStandIn(), QWEN, k=3, expand=False)
    t = loaded.query("SELECT * FROM tasks WHERE task_id=?", (f"check:{cid}",))[0]
    payload = json.loads(t["payload_json"])
    words = " ".join(payload["passages"][0]["text"].split()[:6])
    raw = json.dumps({"evidence": [{"passage": 1, "verdict": "supports", "confidence": 0.9, "quote": words}]})
    with loaded.connect() as cx:
        cx.execute("UPDATE tasks SET status='pending' WHERE task_id=?", (t["task_id"],))
    ok, errs = tasks.ingest_result(loaded, t["task_id"], raw, model="sonnet", route="Claude Code")
    assert ok, errs
    r = claimcheck.result(loaded, cid)
    assert r["status"] == "supported" and r["local_counted"] == 0


def test_a_pre_i6_notice_never_names_a_row_claude_read_again(loaded):
    cid = claimcheck.check_claim(loaded, CLAIM, LocalStandIn(), QWEN, k=3, expand=False)
    with loaded.connect() as cx:   # made before I6: the local model's readings counted
        cx.execute("UPDATE verifications SET suggestion_json=NULL WHERE subject_id=?", (cid,))
    assert claimcheck.result(loaded, cid)["local_counted"] == 1
    t = loaded.query("SELECT * FROM tasks WHERE task_id=?", (f"check:{cid}",))[0]
    words = " ".join(json.loads(t["payload_json"])["passages"][0]["text"].split()[:6])
    with loaded.connect() as cx:   # a stronger model (Claude) reads the same search again
        cx.execute("UPDATE tasks SET again=1, step=1 WHERE task_id=?", (t["task_id"],))
    ok, errs = tasks.ingest_result(loaded, t["task_id"], json.dumps({"evidence": [
        {"passage": 1, "verdict": "supports", "confidence": 0.9, "quote": words}]}), model="sonnet", route="Claude Code")
    assert ok, errs
    r = claimcheck.result(loaded, cid)
    assert r["status"] == "supported" and r["local_counted"] == 0


def test_a_check_answered_again_from_a_kept_local_answer_stays_a_suggestion(loaded):
    be = LocalStandIn()
    first = claimcheck.check_claim(loaded, CLAIM, be, QWEN, k=3, expand=False)
    second = claimcheck.check_claim(loaded, CLAIM, be, QWEN, k=3, expand=False)
    assert be.kinds == ["check"]                                              # the second came from the kept answer
    routes = [r["route"] for r in loaded.query("SELECT route FROM results WHERE task_id=?", (f"check:{second}",))]
    assert routes == ["local model server (kept answer)"]
    for cid in (first, second):
        r = claimcheck.result(loaded, cid)
        assert r["status"] == "not_checked" and r["suggestions"] == len(r["passages"]) and r["local_counted"] == 0
        assert {x["read_by"] for x in r["passages"]} == {"local"}
    with loaded.connect() as cx:   # as if made before I6: the kept local answer is known as the local model's
        cx.execute("UPDATE verifications SET suggestion_json=NULL WHERE subject_id=?", (second,))
    assert claimcheck.result(loaded, second)["local_counted"] == 1


@pytest.mark.parametrize("model,asked", [(QWEN, "check"), (K2, "point")])
def test_under_the_ai_mix_claude_reads_every_local_check_again(loaded, model, asked):
    """Mostly local: the local model reads first (in its own form), its reading stays a suggestion, and the check always
    goes up to Claude, whose reading counts; the local reading is kept in the excerpt's history, counting for nothing."""
    from margin.llm import BaselineBackend

    cid = claimcheck.check_claim(loaded, CLAIM, BaselineBackend(), "baseline", k=3, expand=False)
    tid = f"check:{cid}"
    with loaded.connect() as cx:
        cx.execute("UPDATE tasks SET status='pending', attempts=0, step=0, again=0 WHERE task_id=?", (tid,))
    be = LocalStandIn(marks=[{"p": 1, "s": 1}])
    assert tasks.answer_locally_first(loaded, tid, be, model) == "again" and be.kinds == [asked]
    t = loaded.query("SELECT status, step, again, queued FROM tasks WHERE task_id=?", (tid,))[0]
    assert (t["status"], t["step"], t["again"], t["queued"]) == ("done", 1, 1, 1)
    r = claimcheck.result(loaded, cid)
    assert r["suggestions"] == len(r["passages"]) and r["status"] == "not_checked"
    words = " ".join(json.loads(loaded.scalar("SELECT payload_json FROM tasks WHERE task_id=?", (tid,)))["passages"][0]
                     ["text"].split()[:6])
    ok, errs = tasks.ingest_result(loaded, tid, json.dumps({"evidence": [
        {"passage": 1, "verdict": "supports", "confidence": 0.9, "quote": words}]}), model="sonnet", route="Claude Code")
    assert ok, errs
    r = claimcheck.result(loaded, cid)
    assert r["status"] == "supported" and r["suggestions"] == 0 and r["local_counted"] == 0
    hist = [json.loads(v["ai_history_json"] or "[]") for v in
            loaded.query("SELECT ai_history_json FROM verifications WHERE subject_id=?", (cid,))]
    assert all(h and h[-1].get("suggestion") for h in hist)
    # the answer before the stronger model is what the suggestions gave: nothing counted yet
    assert r["status_first"] == "not_checked"
    row = next(h for h in claimcheck.history(loaded) if h["hyp_id"] == cid)
    assert row["status"] == "supported" and row["status_before_stronger"] == "not_checked"


def test_a_first_reading_that_was_a_suggestion_counts_for_nothing():
    from margin import verdicts

    v = {"verdict": "supports", "confidence": 0.9, "user_verdict": None, "model": "sonnet", "suggestion_json": None,
         "doc_id": "d", "ai_history_json": json.dumps([{"verdict": "refutes", "confidence": 0.95, "model": QWEN,
                                                        "why": "stepped up", "suggestion": '{"by": "local"}'}])}
    f = verdicts.first_reading(v)
    assert verdicts.effective(f)["verdict"] == "not_enough_info" and verdicts._waits_for_person(f)
    assert verdicts.claim_status([verdicts.effective(f)], 0.6) == "not_checked"


def test_validation_leaves_out_pointers_and_marks_suggestions_shown_first(loaded):
    from margin import validation

    qwen = claimcheck.check_claim(loaded, CLAIM, LocalStandIn(), QWEN, k=3, expand=False)
    k2 = claimcheck.check_claim(loaded, "Electrolysers need much fresh water.", LocalStandIn(marks=[{"p": 1, "s": 1}]),
                                K2, k=3, expand=False)
    for cid in (qwen, k2):
        x = next(p for p in claimcheck.result(loaded, cid)["passages"] if (p["suggestion"] or {}).get("marked"))
        claimcheck.set_judgement(loaded, cid, x["passage_id"], "refutes")
    rec = validation.collect_person(loaded, "Pilot")
    assert rec["checks_pointed"] == 1 and len(rec["checks"]) == 1 and rec["checks"][0]["shown_first"] is True
    md = validation.person_markdown([rec])
    assert "only pointed at by the small local model" in md and "not independent" in md


def test_the_small_tier_answers_a_check_by_pointing_and_judges_nothing(loaded):
    be = LocalStandIn(marks=[{"p": 2, "s": 1}, {"p": 1, "s": 1}, {"p": 2, "s": 2}, {"p": 7, "s": 1}])
    cid = claimcheck.check_claim(loaded, CLAIM, be, K2, k=3, expand=False)
    assert be.kinds == ["point"]                                             # never the long check form
    res = loaded.query("SELECT kind, prompt_version, valid FROM results WHERE task_id=?", (f"check:{cid}",))
    assert [tuple(x) for x in res] == [("point", "point-v1", 1)]
    vs = {v["passage_id"]: v for v in loaded.query("SELECT * FROM verifications WHERE subject_id=?", (cid,))}
    assert all(v["verdict"] == "not_enough_info" and v["confidence"] is None for v in vs.values())
    r = claimcheck.result(loaded, cid)
    assert r["status"] == "not_checked" and r["status_text"] == claimcheck.WAITING_YOU
    payload = json.loads(loaded.scalar("SELECT payload_json FROM tasks WHERE task_id=?", (f"check:{cid}",)))
    order = [p["passage_id"] for p in payload["passages"]]
    marked = [x for x in r["passages"] if x["suggestion"]["marked"]]
    # the marked excerpts first, in the model's order; each quote is a sentence Margin cut from its excerpt
    assert [x["passage_id"] for x in marked] == [order[1], order[0]]
    assert [x["passage_id"] for x in r["passages"]][:2] == [order[1], order[0]]
    for x in marked:
        assert x["suggestion"]["form"] == "point" and x["suggestion"]["lean"] is None and x["ai_verdict"] is None
        assert x["quote_by"] == "the local model" and x["text"][x["quote_start"]:x["quote_end"]] == x["quote"]
    # judging one keeps the highlight, and is not a change of anything the model judged
    claimcheck.set_judgement(loaded, cid, marked[0]["passage_id"], "partially_supports")
    y = next(x for x in claimcheck.result(loaded, cid)["passages"] if x["passage_id"] == marked[0]["passage_id"])
    assert y["verdict"] == "partially_supports" and y["counted"] and not y["changed"] and y["quote"] == marked[0]["quote"]


def test_a_check_read_by_claude_is_unchanged(loaded):
    """Claude's (and the demo's) judgements still decide, as before I6."""
    from margin.llm import BaselineBackend

    cid = claimcheck.check_claim(loaded, CLAIM, BaselineBackend(), "baseline", k=3, expand=False)
    r = claimcheck.result(loaded, cid)
    assert r["suggestions"] == 0 and all(not x["suggestion"] for x in r["passages"])
    assert loaded.scalar("SELECT COUNT(*) FROM verifications WHERE suggestion_json IS NOT NULL") == 0


# ---------------------------------------------------------------------------------------------- the memory guard
@pytest.fixture
def mac16(monkeypatch):
    monkeypatch.setattr(llm, "total_memory", lambda: 16 * GB)
    monkeypatch.setattr(llm, "free_memory", lambda: 8 * GB)


def _guarded(fake):
    be = OllamaBackend("http://localhost:11434", num_ctx=16384, opener=fake, think=False)
    be.memory_watch = True
    return be


def test_the_guard_frees_a_grown_mlx_model_at_its_threshold_and_not_before(mac16):
    fake = FakeOllama()
    be = _guarded(fake)
    assert be._guard(QWEN) is False and not fake.paths("/api/generate")      # not loaded: nothing to free, nothing loaded
    fake.held[QWEN] = int(4.13 * GB)
    assert be._guard(QWEN) is False                                           # its first reading
    for gb in (4.3, 4.9, 5.6):                                                # below 4.13 + 1.6 GB
        fake.held[QWEN] = int(gb * GB)
        assert be._guard(QWEN) is False
    fake.held[QWEN] = int(5.8 * GB)
    assert be._guard(QWEN) is True and be.freed == 1
    assert [b["model"] for b in fake.paths("/api/generate")] == [QWEN] and QWEN not in fake.held
    fake.held[QWEN] = int(4.1 * GB)                                           # reloaded by the next request
    assert be._guard(QWEN) is False


def test_through_a_long_run_the_guard_frees_about_every_tenth_check(mac16):
    fake = FakeOllama()
    fake.grow = int(0.17 * GB)
    be = _guarded(fake)
    payload = {"claim": "x", "passages": _passages(2)}
    fake.answer = '{"evidence": [], "rationale": ""}'
    # +0.17 GB an answer (the bench's MLX growth): past 1.6 GB after the 11th answer, and again ten answers after reloading
    for _ in range(22):
        be.complete("check", "s", "u", QWEN, payload)
    assert len(fake.paths("/api/generate")) == 1
    be.complete("check", "s", "u", QWEN, payload)
    assert len(fake.paths("/api/generate")) == 2


def test_the_guard_never_frees_a_model_ollama_does_not_list_and_falls_back_to_a_count_on_mlx(mac16):
    fake = FakeOllama()
    be = _guarded(fake)
    fake.held = {"other:1b": GB}
    assert be._guard(QWEN) is False and not fake.paths("/api/generate")
    fake.ps_down = True
    be._requests = 20
    assert be._guard(K2) is False                                             # llama.cpp does not grow
    assert be._guard(QWEN) is True                                            # every 20th request on MLX
    be._requests = 21
    assert be._guard(QWEN) is False


def test_low_free_memory_frees_only_a_grown_mlx_model_and_the_guard_is_off_unless_the_app_turns_it_on(monkeypatch):
    monkeypatch.setattr(llm, "total_memory", lambda: 16 * GB)
    monkeypatch.setattr(llm, "free_memory", lambda: int(2.5 * GB))           # under a fifth
    fake = FakeOllama()
    fake.held = {K2: int(1.2 * GB), QWEN: int(4.1 * GB)}
    off = OllamaBackend("http://localhost:11434", opener=fake)
    assert off.memory_watch is False and off._guard(QWEN) is False
    be = _guarded(fake)
    # a llama.cpp build does not grow: unloading it frees nothing that would come back, so short memory leaves it
    for _ in range(3):
        fake.held[K2] += int(0.6 * GB)
        assert be._guard(K2) is False and K2 in fake.held
    # an MLX model only once it has grown past its first reading by half a GB
    assert be._guard(QWEN) is False                                           # its first reading
    fake.held[QWEN] = int(4.4 * GB)
    assert be._guard(QWEN) is False
    fake.held[QWEN] = int(4.7 * GB)
    assert be._guard(QWEN) is True and QWEN not in fake.held


def test_after_a_free_the_guard_waits_a_few_requests_before_it_frees_again(monkeypatch):
    monkeypatch.setattr(llm, "total_memory", lambda: 16 * GB)
    monkeypatch.setattr(llm, "free_memory", lambda: int(2.0 * GB))           # still short after the free
    fake = FakeOllama()
    fake.grow = int(0.6 * GB)
    be = _guarded(fake)
    payload = {"claim": "x", "passages": _passages(2)}
    fake.answer = '{"evidence": [], "rationale": ""}'
    for _ in range(12):
        be.complete("check", "s", "u", QWEN, payload)
    frees = [i for i, (p, _b) in enumerate(fake.calls) if p == "/api/generate"]
    chats_between = [sum(1 for p, _b in fake.calls[a:b] if p == "/api/chat") for a, b in zip(frees, frees[1:])]
    assert frees and all(n >= llm.GUARD_COOLDOWN for n in chats_between)   # never a reload for every request


def test_the_apps_backend_has_the_guard_on():
    from margin import home

    be = home._ollama({"think": "off", "num_ctx": "auto", "k": 8}, "http://localhost:11434", QWEN, False)
    assert be.memory_watch is True


def test_let_go_with_a_runner_frees_only_those_models(monkeypatch):
    fake = FakeOllama()
    fake.held = {QWEN: 5 * GB, K2: GB}
    real = REAL_LET_GO
    monkeypatch.setattr(llm, "OllamaBackend", lambda base_url=None, timeout=10: OllamaBackend(base_url, opener=fake))
    assert real({("http://localhost:11434", QWEN), ("http://localhost:11434", K2)}, runner="mlx") == [QWEN]
    assert K2 in fake.held and QWEN not in fake.held


# ---------------------------------------------------------------------------------------------- what made it
def test_provenance_records_the_engine_and_repeatable_says_not_guaranteed_for_mlx_without_asking():
    fake = FakeOllama()
    be = OllamaBackend("http://localhost:11434", opener=fake, think=False)
    prov = llm.provenance(be, QWEN)
    assert prov["digest"] == f"sha-{QWEN}" and prov["seed"] == 42
    assert {k: prov["settings"][k] for k in ("runner", "quantization", "ollama")} == {
        "runner": "mlx", "quantization": "nvfp4", "ollama": "0.40.16"}
    assert llm.provenance(be, K2)["settings"]["runner"] == "llamacpp"
    rep = llm.repeatable(be, QWEN)
    assert rep["repeatable"] is False and rep["runner"] == "mlx" and "6 times in 10" in rep["note"]
    assert not fake.paths("/api/chat")                                        # the model was not asked (nor loaded)


def test_how_these_results_were_made_has_the_engine_and_the_note_for_local_answers_only(loaded):
    cid = claimcheck.check_claim(loaded, CLAIM, LocalStandIn(), QWEN, k=3, expand=False)
    with loaded.connect() as cx:
        cx.execute("UPDATE results SET settings_json=? WHERE task_id=?",
                   (json.dumps({"backend": "ollama", "route": "local model server", "runner": "mlx",
                                "quantization": "nvfp4", "ollama": "0.40.16", "num_ctx": 16384}), f"check:{cid}"))
    table = runs.provenance_table(loaded, [f"check:{cid}"])
    assert table[0]["Engine"] == "Ollama 0.40.16, MLX, nvfp4"
    notes = [r["Step"] for r in table if r["Step"].startswith("Note:")]
    assert len(notes) == 1 and "decide nothing" in notes[0] and "6 times in 10" in notes[0]
    # a Claude-only check: no such note
    from margin.llm import BaselineBackend

    other = claimcheck.check_claim(loaded, "Electrolysers need much fresh water.", BaselineBackend(), "baseline", k=3,
                                   expand=False)
    assert not any("Suggestions from the model" in r["Step"] for r in runs.provenance_table(loaded, [f"check:{other}"]))


def test_the_plan_of_a_run_says_when_the_engine_changed(loaded):
    fake = FakeOllama()
    be = OllamaBackend("http://localhost:11434", opener=fake, think=False)
    rid = runs.start(loaded, "label", "sdg", be, QWEN, 3)
    runs.finish(loaded, rid, 3)
    assert runs.plan(loaded, "label", "sdg", OllamaBackend("http://localhost:11434", opener=fake, think=False),
                     QWEN)["changed"] == []
    FakeOllama.MODELS = {**FakeOllama.MODELS, QWEN: {**FakeOllama.MODELS[QWEN], "runner": "llamacpp"}}
    try:
        changed = runs.plan(loaded, "label", "sdg", OllamaBackend("http://localhost:11434", opener=FakeOllama(),
                                                                   think=False), QWEN)["changed"]
    finally:
        FakeOllama.MODELS = {**FakeOllama.MODELS, QWEN: {**FakeOllama.MODELS[QWEN], "runner": "mlx"}}
    assert {"field": "runner", "was": "mlx", "now": "llamacpp"} in changed


# ---------------------------------------------------------------------------------------------- the result page
PROBE = r"""
const PX = (o) => ({ passage_id: "p1", doc_id: "d1", title: "Repair report", text: "Volunteers fix toasters for free. They meet monthly.",
  quote: "Volunteers fix toasters for free.", quote_start: 0, quote_end: 33, verdict: null, ai_verdict: "supports", confidence: null,
  certainty: "", counted: false, read_by: "local", waiting_for_you: true, ai_read: true, in_corpus: true, page: 3, round: 1,
  found_by: "keywords", suggestion: { form: "check", lean: "supports", marked: true, order: 1 }, ...o });
const RESULT = (passages) => ({ hyp_id: "h1", text: "Repair cafés build community", status: "not_checked", status_text: "Waiting for your judgement",
  threshold: 0.6, options: {}, decomposed: false, model: "qwen3.5:4b", suggestions: passages.length,
  parts: [{ claim_id: "c1", part: 1, claim: "Repair cafés build community", status: "not_checked", passages, rounds_info: [], model: "qwen3.5:4b" }] });
const H = "/api/projects/Study/hypotheses/h1";
async function result(t, answer) {
  t.state({ settings: { threshold: 0.6 } });
  t.answer("GET /api/projects/Study/retractions", { by_doc: {} });
  t.answer("GET /api/projects/Study/sharing/check/h1", { shared: false });
  t.answer(/^GET \/api\/projects\/Study\/documents\/[^/]+\/file\?check=1$/, t.fail(404, "no file"));
  t.answer(`GET ${H}/unread`, { documents: [] });
  t.answer("GET /api/servers", { servers: [] });
  t.answer("GET /api/projects/Study/shared-folder", { folder: null });
  t.answer("GET /api/projects/Study/sync-poller", t.fail(404, "none"));
  t.answer("GET /api/local-status", { running: false, models: [] });
  t.answer(`GET ${H}?*`, () => answer);
  await t.render("views/result.js", "renderResult", ["h1"], {});
}
const card = (t, id) => t.view.querySelector(`[data-passage="${id}"]`);

await scenario("suggestions", async (t) => {
  await result(t, RESULT([PX(), PX({ passage_id: "p2", title: "Interview", ai_verdict: null, quote: "They meet monthly.", quote_start: 34, quote_end: 52,
    suggestion: { form: "point", lean: null, marked: true, order: 2 } })]));
  t.answer("PUT /api/projects/Study/claims/c1/judgements/p1", { moved: null });
  const out = { heads: t.view.querySelectorAll(".evidence-head").map((x) => t.text(x)), top1: t.text(card(t, "p1").querySelector(".ev-top")),
    top2: t.text(card(t, "p2").querySelector(".ev-top")), buttons1: t.buttons(card(t, "p1")), buttons2: t.buttons(card(t, "p2")),
    mark1: t.text(card(t, "p1").querySelector("mark") || card(t, "p1")) };
  await t.click("Agree", { within: card(t, "p1") });
  out.put = t.calls.find((c) => c.method === "PUT").body;
  out.buttons1 = out.buttons1.map((b) => b.label); out.buttons2 = out.buttons2.map((b) => b.label);
  return out;
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("tiers"))


@needs_node
def test_the_card_shows_the_local_models_suggestion_before_your_judgement_with_no_number(page):
    a = page["suggestions"]
    assert any(h.startswith("Awaiting manual review: 2 excerpts\nThe local model on this computer read these") and
               "only your judgements count" in h for h in a["heads"])
    assert a["top1"] == "Awaiting manual review The local model suggests: supports"
    assert a["top2"] == "Awaiting manual review The local model points at the highlighted sentence"
    assert "%" not in a["top1"] + a["top2"] and "Certainty" not in a["top1"]
    assert "Agree" in a["buttons1"] and "Not about this" in a["buttons1"]     # a lean to agree with, in one press
    assert "Agree" not in a["buttons2"]                                        # a pointer judges nothing: judge it yourself
    assert a["put"]["verdict"] == "supports"
