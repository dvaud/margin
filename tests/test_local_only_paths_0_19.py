"""Documents only a local AI may read, in the 0.19 series: the framework draft, See what is sent, and what goes with a
removed theory document or with Remove everything.

A document marked "Only a local AI" must never reach Claude: not in a framework Claude puts together, not in the
preview of the next batch. And the AI's drafts that quote a document's passages go when the document goes.
"""
from __future__ import annotations

import json

from test_app import home  # noqa: F401  (fixture)
from test_queue import _queued_labels
from test_theory_framework import FakeModel, _started, project  # noqa: F401  (fixture)

from margin import access, routing, taskkinds, taskqueue, tasks, theoryframe


# ---------------------------------------------------------------------------------------------
# B1: the framework draft leaves a local document out of Claude's framework
# ---------------------------------------------------------------------------------------------
def test_a_theory_document_marked_local_is_left_out_of_claudes_framework(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    access.set_documents(ws, [practice], "local")   # and no local model is chosen
    _started(ws, meadows, practice)
    title = ws.scalar("SELECT title FROM documents WHERE doc_id=?", (practice,))
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (practice,))
    be = FakeModel()
    r = theoryframe.read(ws, be, "claude-sonnet-5-5")
    assert r["ok"] and be.calls["theory_frame"] == 1
    assert any(p == f"{title}: left out of the framework (only a local AI may read it, and the framework is put "
                    "together by Claude)." for p in r["problems"]), r["problems"]
    # neither its id nor a sentence of it is in what Claude was sent, nor in a task kept for Claude Code
    sentence = "A stock is the store of habits"
    assert sentence in text
    for p in be.payloads:
        assert practice not in json.dumps(p) and sentence not in json.dumps(p, ensure_ascii=False)
    for t in ws.query("SELECT payload_json FROM tasks"):
        assert practice not in t["payload_json"] and sentence not in t["payload_json"]
    # its own defined term is still the person's to use, outside the AI's groups
    d = theoryframe.load(ws)
    assert any(p.startswith(f"{title}: left out of the framework") for p in d["reading"]["problems"])
    grouped = {c for g in d["groups"] for c in g.get("concepts", [])}
    own = [c for c in d["concepts"] if any(s["doc_id"] == practice for s in c.get("sources", []))
           and all(s["doc_id"] == practice for s in c["sources"])]
    assert own and not any(c.get("id") in grouped or c.get("name") in grouped for c in own)


# ---------------------------------------------------------------------------------------------
# B2: See what is sent
# ---------------------------------------------------------------------------------------------
def test_see_what_is_sent_never_shows_a_document_marked_local(home, corpus):  # noqa: F811
    ws, _pids = _queued_labels(home, corpus, "L")
    pv = taskqueue.preview(ws, "label")
    first_doc = pv["tasks"][0]["documents"][0]["doc_id"]
    first_text = ws.scalar("SELECT text FROM passages WHERE doc_id=? ORDER BY seq LIMIT 1", (first_doc,))
    access.set_documents(ws, [first_doc], "local")
    again = taskqueue.preview(ws, "label")
    assert again["tasks"] and all(first_doc not in {d["doc_id"] for d in t["documents"]} for t in again["tasks"])
    assert first_text[:60] not in again["raw"]
    # its tasks still wait (for the local model), they are just not Claude Code's to be sent
    held = ws.scalar("SELECT COUNT(*) FROM tasks t JOIN passages p ON t.task_id = 'label:sdg:' || p.passage_id "
                     "WHERE p.doc_id=? AND t.status IN ('pending','retry')", (first_doc,))
    assert held > 0
    # a setting that reached the database without its tasks being labelled again (as a colleague's round writes
    # it): the preview reads each task's documents again, so this one is not shown either
    second = next(d["doc_id"] for t in again["tasks"] for d in t["documents"])
    with ws.connect() as cx:
        cx.execute("UPDATE documents SET ai_access='local' WHERE doc_id=?", (second,))
    third = taskqueue.preview(ws, "label")
    assert all(second not in {d["doc_id"] for d in t["documents"]} for t in third["tasks"])
    # past the last batch: nothing more of this kind
    after = taskqueue.preview(ws, "label", start=10 ** 6)
    assert after["tasks"] == [] and after["more"] is False and after["note"] == "Nothing more of this kind waits."


def test_see_what_is_sent_keeps_a_batch_within_what_claude_code_takes(home, corpus, monkeypatch):  # noqa: F811
    ws, _pids = _queued_labels(home, corpus, "B")
    whole = taskqueue.preview(ws, "label")
    assert len(whole["tasks"]) > 1
    monkeypatch.setattr(taskqueue, "TOKEN_BUDGET", 1)   # room for one task: the batch stops at the first
    one = taskqueue.preview(ws, "label")
    assert [t["task_id"] for t in one["tasks"]] == [whole["tasks"][0]["task_id"]] and one["more"] is True


def test_see_what_is_sent_on_an_installation_that_keeps_everything_here(home, corpus, monkeypatch):  # noqa: F811
    ws, _pids = _queued_labels(home, corpus, "K")
    monkeypatch.setenv("MARGIN_LOCAL_ONLY", "1")
    pv = taskqueue.preview(ws, "label")
    assert pv["kind"] is None and "tasks" not in pv
    assert pv["note"] == "This installation keeps everything on this computer: nothing is sent to Claude Code."


# ---------------------------------------------------------------------------------------------
# B3: what goes with a removed theory document, and with Remove everything
# ---------------------------------------------------------------------------------------------
def test_removing_a_theory_document_removes_the_framework_that_quotes_it(project):  # noqa: F811
    ws, meadows, practice, _ev = project
    _started(ws, meadows, practice)
    assert theoryframe.read(ws, FakeModel(), "claude-sonnet-5-5")["ok"]
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_frame'") == 1
    assert ws.scalar("SELECT COUNT(*) FROM results WHERE kind='theory_frame'") >= 1
    ws.remove_document(practice)
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_frame'") == 0
    assert ws.scalar("SELECT COUNT(*) FROM results WHERE kind='theory_frame'") == 0
    # the other theory document's own drafts stay
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='theory_codes' AND instr(task_id, ?) > 0",
                     (meadows,)) > 0


def test_remove_everything_removes_every_ai_task_that_holds_passages(loaded):
    """Remove everything (Workspace.reset_corpus) keeps the VCA and its split justifications, and nothing else the AI
    was given: a task of every kind that reads the corpus goes. The kinds are a written list in reset_corpus, so a
    new kind of task left off it fails here."""
    ws = loaded
    kinds = [n for n in routing.KINDS if taskkinds.get(n).core and taskkinds.get(n).task]
    assert {"label", "check", "theory_frame", "code_definition", "group_name"} <= set(kinds)
    passage = dict(ws.query("SELECT passage_id, doc_id, text FROM passages LIMIT 1")[0])
    with ws.connect() as cx, tasks.queueing(True):
        for k in kinds:
            tasks._insert_task(cx, f"{k}:reset-test", k, "sonnet", {"passages": [passage], "text": passage["text"]})
    ws.reset_corpus()
    left = {r[0] for r in ws.query("SELECT kind FROM tasks WHERE task_id LIKE '%:reset-test'")}
    # the split justifications are the VCA's, not the corpus's: they stay with it
    assert left == {"split"}, f"tasks left after Remove everything: {sorted(left)}"
