"""0.19.17: Stop resets a further round of a check.

The owner's report: a document added as "Only a local AI" was read with *Read it*; the job's local side waited for its
Start, the job was stopped, and the document was then switched to "Claude may read it". The local model's panel stayed
on the result ("waits for your local model", Start, Judge them myself) and *Read it* never came back, so Claude could
not read the document. The rule now: Stop takes back what no model read in a further round (Read it, Read these, Read
more excerpts, Search with other words), so the page shows the button that asked for it again; clicked again, the
document's setting at that moment decides who reads it.
"""
from __future__ import annotations

import time

import pytest
from helpers_mixed_corpus import LOCAL_MARK, Cloud, _doc, mixed_project, use_local_model
from test_local_memory import GB, HYP, Watched

from margin import access, claimcheck, home as home_mod, ingest
from margin.gui.api_common import Jobs


def _until(cond, timeout: float = 30, step: float = 0.02) -> None:
    t0 = time.monotonic()
    while not cond():
        if time.monotonic() - t0 > timeout:
            raise AssertionError("the condition was not met in time")
        time.sleep(step)


def _ended(job) -> bool:
    return job.state in ("done", "error", "cancelled") and job.finished is not None


def _tasks(ws, hid: str) -> list[str]:
    cids = [r[0] for r in ws.query("SELECT claim_id FROM user_claims WHERE hyp_id=?", (hid,))]
    return sorted(t["task_id"] for c in cids for t in claimcheck._check_tasks(ws, c))


@pytest.fixture
def checked(tmp_path, monkeypatch):
    """A check of the mixed project read in full, then a new document only the local model may read."""
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home_mod.create_project("Mixed")
    mixed_project(ws, tmp_path / "corpus")
    local, cloud = Watched(free=64 * GB), Cloud()
    use_local_model(monkeypatch, local)
    hid = claimcheck.check_hypothesis(ws, HYP, cloud, "claude-opus", k=12, per_doc=4)  # no job: no gate, read at once
    assert not claimcheck.local_waiting(ws, [hid])
    time.sleep(1.1)  # added_at has whole seconds
    (tmp_path / "new").mkdir()
    (tmp_path / "new" / "later_study.txt").write_text(_doc("Later study on hydrogen and water", LOCAL_MARK))
    ingest.ingest(ws, [tmp_path / "new"], ai_access="cloud")
    new = ws.scalar("SELECT doc_id FROM documents WHERE title LIKE 'Later study%'")
    access.set_documents(ws, [new], "local")
    assert [d["doc_id"] for d in claimcheck.new_documents(ws, hid) if d["matching"]] == [new]
    local.sent.clear()
    cloud.sent.clear()
    return ws, hid, new, local, cloud


def _read_new(jobs, ws, hid, cloud):
    def run(job):
        return claimcheck.read_new_documents(ws, hid, cloud, "claude-opus", k=4, should_stop=job.cancel.is_set)

    return jobs.start("read-new", "Reading the new documents", "Mixed", run, uses_model=True)


def test_stop_while_the_local_side_waits_brings_read_it_back(checked):
    ws, hid, new, local, cloud = checked
    before = _tasks(ws, hid)
    jobs = Jobs()
    job = _read_new(jobs, ws, hid, cloud)
    _until(lambda: job.gate.involved and job.gate.busy())
    assert claimcheck.local_waiting(ws, [hid])            # the round's local part waits for the local Start
    jobs.cancel(job)
    _until(lambda: _ended(job))
    assert job.state == "cancelled", job.error
    assert local.sent == []
    # reset: no round left behind, no panel that waits for the local model, and Read it is back
    assert _tasks(ws, hid) == before
    assert not claimcheck.local_waiting(ws, [hid])
    assert claimcheck.hypothesis_result(ws, hid)["waiting_local"] == 0
    assert [d["doc_id"] for d in claimcheck.new_documents(ws, hid) if d["matching"]] == [new]


def test_after_the_reset_a_loosened_document_goes_to_claude(checked):
    ws, hid, new, local, cloud = checked
    jobs = Jobs()
    job = _read_new(jobs, ws, hid, cloud)
    _until(lambda: job.gate.involved and job.gate.busy())
    jobs.cancel(job)
    _until(lambda: _ended(job))
    access.set_documents(ws, [new], "cloud")              # the person lets Claude read it after all
    again = _read_new(jobs, ws, hid, cloud)                # Read it, once more
    _until(lambda: _ended(again))
    assert again.state == "done", again.error
    assert local.sent == [] and LOCAL_MARK.lower() in cloud.text()
    assert not claimcheck.local_waiting(ws, [hid])
    assert claimcheck.new_documents(ws, hid) == []
    assert not any(t.endswith(":local") and ":r" in t for t in _tasks(ws, hid))


def test_the_local_start_still_reads_and_nothing_is_reset(checked):
    ws, hid, new, local, cloud = checked
    jobs = Jobs()
    job = _read_new(jobs, ws, hid, cloud)
    _until(lambda: job.gate.involved and job.gate.busy())
    job.gate.open()
    _until(lambda: _ended(job))
    assert job.state == "done", job.error
    assert local.sent and not claimcheck.local_waiting(ws, [hid])
    assert claimcheck.new_documents(ws, hid) == []


def test_claudes_part_stays_and_only_the_waiting_local_part_goes(checked, tmp_path):
    ws, hid, new, local, cloud = checked
    cid = ws.scalar("SELECT claim_id FROM user_claims WHERE hyp_id=?", (hid,))
    (tmp_path / "open").mkdir()   # excerpts Claude may read that the check has not read yet
    (tmp_path / "open" / "open_note.txt").write_text(_doc("Open note on hydrogen and water", None))
    ingest.ingest(ws, [tmp_path / "open"], ai_access="cloud")
    # a round of both: Claude's part read, the local part still waiting (as after a Stop before the local Start)
    r = claimcheck.more_passages(ws, cid, k=8, model="claude-opus", main_levels=("cloud",), local_reader=True)
    parts = r["parts"]
    assert {"main", "local"} <= set(parts)
    from margin import tasks

    tasks.run_one(ws, parts["main"], cloud, "claude-opus")
    assert claimcheck._undo_unread(ws, cid, parts)
    ids = _tasks(ws, hid)
    assert parts["main"] in ids and parts["local"] not in ids
    assert not claimcheck.local_waiting(ws, [hid])
    # nothing left to take back the second time
    assert not claimcheck._undo_unread(ws, cid, parts)


def test_other_words_stopped_take_their_search_words_back(checked):
    ws, hid, new, local, cloud = checked
    cid = ws.scalar("SELECT claim_id FROM user_claims WHERE hyp_id=?", (hid,))
    terms_before = ws.scalar("SELECT terms_json FROM user_claims WHERE claim_id=?", (cid,))
    jobs = Jobs()

    def run(job):
        return claimcheck.continue_check(ws, cid, cloud, "claude-opus", k=8, terms=["groundwater", "electrolysis"],
                                         should_stop=job.cancel.is_set, doc_ids=[new])

    job = jobs.start("more", "Reading more passages", "Mixed", run, uses_model=True)
    _until(lambda: job.gate.involved and job.gate.busy())
    jobs.cancel(job)
    _until(lambda: _ended(job))
    assert job.state == "cancelled", job.error
    assert not claimcheck.local_waiting(ws, [hid])
    assert ws.scalar("SELECT terms_json FROM user_claims WHERE claim_id=?", (cid,)) == terms_before
