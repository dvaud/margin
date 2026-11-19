"""0.19.17: a second opinion compares with a first reading, so it is never asked of excerpts no model has read yet.

The owner's report: "second opinion differs on 7" in the Hypotheses list and "judged 7 differently" on the result,
but no card on the page showed where. All seven were excerpts of a new document still waiting for the local model:
Claude's second opinion had read them (the document had been switched to "Claude may read it"), there was no first
reading to compare with, so each counted as a difference, and such excerpts are not drawn as cards.
"""
from __future__ import annotations

import time

import pytest
from helpers_mixed_corpus import LOCAL_MARK, Cloud, _doc, mixed_project, use_local_model
from test_local_memory import GB, HYP, Watched

from margin import access, claimcheck, home as home_mod, ingest


@pytest.fixture
def waiting(tmp_path, monkeypatch):
    """A check read in full, then a further round of a new local document whose local part waits; the document is
    then switched to Claude may read it."""
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home_mod.create_project("Mixed")
    mixed_project(ws, tmp_path / "corpus")
    use_local_model(monkeypatch, Watched(free=64 * GB))
    cloud = Cloud()
    hid = claimcheck.check_hypothesis(ws, HYP, cloud, "claude-opus", k=12, per_doc=4)
    time.sleep(1.1)
    (tmp_path / "new").mkdir()
    (tmp_path / "new" / "later_study.txt").write_text(_doc("Later study on hydrogen and water", LOCAL_MARK))
    ingest.ingest(ws, [tmp_path / "new"], ai_access="cloud")
    new = ws.scalar("SELECT doc_id FROM documents WHERE title LIKE 'Later study%'")
    access.set_documents(ws, [new], "local")
    cid = ws.scalar("SELECT claim_id FROM user_claims WHERE hyp_id=?", (hid,))
    r = claimcheck.more_passages(ws, cid, k=8, model="claude-opus", doc_ids=[new], main_levels=("cloud",),
                                 local_reader=True)
    assert set(r["parts"]) == {"local"}
    access.set_documents(ws, [new], "cloud")
    return ws, hid, cid, r["parts"]["local"], cloud


def test_a_second_opinion_is_not_asked_of_a_part_not_read_yet(waiting):
    ws, hid, cid, local_tid, cloud = waiting
    out = claimcheck.second_opinion(ws, [hid], cloud, "claude-opus", "claude-sonnet")
    assert out["rounds"] >= 1   # the first round, read, has its second opinion
    assert ws.scalar("SELECT 1 FROM tasks WHERE task_id=?", (f"second:{local_tid}:claude-sonnet",)) is None
    assert LOCAL_MARK.lower() not in cloud.text()


def test_a_second_reading_of_an_excerpt_not_read_yet_is_no_difference(waiting):
    ws, hid, cid, local_tid, cloud = waiting
    import json

    pids = [p["passage_id"] for p in json.loads(ws.scalar("SELECT payload_json FROM tasks WHERE task_id=?",
                                                          (local_tid,)))["passages"]]
    with ws.connect() as cx:   # as an earlier version left it: the second opinion read the waiting excerpts
        for pid in pids:
            cx.execute("INSERT INTO second_opinions(subject_id, passage_id, model, verdict, confidence, at) "
                       "VALUES (?,?,?,?,?,?)", (cid, pid, "claude-sonnet", "supports", 0.9, "2026-11-17T18:54:10"))
    res = claimcheck.hypothesis_result(ws, hid)
    waiting_items = [x for p in res["parts"] for x in p["passages"] if x["passage_id"] in pids]
    assert waiting_items and all(x["second"] is None for x in waiting_items)
    assert res["disagreements"] == 0
    assert next(h for h in claimcheck.history(ws) if h["hyp_id"] == hid)["disagreements"] == 0
