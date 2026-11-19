"""Routes of the 0.19 series that no other test calls: Judge it myself, Run again, the local panel's status, the test
notification and the label plan's local model.

Each goes through the local API as the page does (the `api` client of tests/test_app.py, with the app object kept for
setting up jobs the page cannot start by itself).
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

from helpers_mixed_corpus import use_local_model
from test_app import Api, home  # noqa: F401  (fixture)
from test_local_memory import GB, Watched, _queued_check_answered, mixed  # noqa: F401  (fixture)

from margin import access, claimcheck, llm, tasks
from margin.verdicts import WAITING_LOCAL

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def served(home):  # noqa: F811
    """The app's server and the app object behind it (the `api` fixture keeps the app to itself)."""
    from margin.gui.server import make_server

    srv, app = make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield Api(f"http://127.0.0.1:{srv.server_address[1]}", app.token), app
    srv.shutdown()
    srv.server_close()


def _wait_job(job, timeout=30):
    t0 = time.monotonic()
    while job.state in ("queued", "running"):
        if time.monotonic() - t0 > timeout:
            raise AssertionError("the job did not end")
        time.sleep(0.01)
    return job


# ---------------------------------------------------------------------------------------------
# A1: Judge it myself (0.19.8)
# ---------------------------------------------------------------------------------------------
def test_judge_it_myself_through_the_app(mixed, served, monkeypatch):  # noqa: F811
    ws, ids = mixed
    api, app = served
    use_local_model(monkeypatch, Watched(need=int(8.1 * GB), free=int(6.5 * GB)))
    hid = _queued_check_answered(ws)
    before = api("GET", f"/api/projects/Mixed/hypotheses/{hid}")[1]
    n = before["waiting_local"]
    assert n > 0 and before["status_text"] == WAITING_LOCAL
    assert ws.scalar("SELECT queue FROM hypotheses WHERE hyp_id=?", (hid,)) == "waiting"

    st, r = api("POST", "/api/projects/Mixed/hypotheses/nothing-here/judge-local", {})
    assert st == 404 and "hypothesis" in r["error"]

    # while the local model reads these excerpts, the person cannot take them
    from margin.gui.api_common import Job

    reading = Job("read-local", "Your local model reads the excerpts", "Mixed")
    reading.scope, reading.state = hid, "running"
    with app.jobs.lock:
        app.jobs.jobs[reading.id] = reading
    st, r = api("POST", f"/api/projects/Mixed/hypotheses/{hid}/judge-local", {})
    assert st == 409 and "Stop it first" in r["error"]
    assert api("GET", f"/api/projects/Mixed/hypotheses/{hid}")[1]["waiting_local"] == n   # nothing was handed over
    reading.state = "done"

    st, r = api("POST", f"/api/projects/Mixed/hypotheses/{hid}/judge-local", {})
    assert st == 200 and r == {"hyp_id": hid, "excerpts": n}
    after = api("GET", f"/api/projects/Mixed/hypotheses/{hid}")[1]
    assert after["waiting_local"] == 0 and after["status_text"] != WAITING_LOCAL
    mine = [x for part in after["parts"] for x in part["passages"] if x["doc_id"] == ids["local"]]
    assert mine and all(x["waiting_for_you"] and x["by_choice"] for x in mine)
    # the queue moved on: the check no longer waits for anything but the person
    assert not claimcheck.local_waiting(ws, [hid], retry_failed=True)
    assert ws.scalar("SELECT queue FROM hypotheses WHERE hyp_id=?", (hid,)) != "waiting"
    assert api("POST", f"/api/projects/Mixed/hypotheses/{hid}/judge-local", {})[1]["excerpts"] == 0


def test_judge_it_myself_leaves_the_ai_mix_tasks_to_the_models(mixed, served, monkeypatch):  # noqa: F811
    """A task the AI mix gives the local model first (Mostly local) is not an excerpt of a document marked Only a
    local AI: Claude Code answers it when no local model does, so the person is not handed it."""
    ws, ids = mixed
    api, app = served
    use_local_model(monkeypatch, Watched(need=int(8.1 * GB), free=int(6.5 * GB)))
    hid = _queued_check_answered(ws)
    from margin import home as home_mod

    s = {**home_mod.load_settings(), "backend": "claude_code", "ai_mix": "mostly_local",
         "restricted_server": "ollama", "restricted_model": "local-model"}
    monkeypatch.setattr(home_mod, "load_settings", lambda strict=False: dict(s))
    cid = ws.scalar("SELECT claim_id FROM user_claims WHERE hyp_id=? LIMIT 1", (hid,))
    picked = [dict(r) for r in ws.query("SELECT p.passage_id, p.doc_id, d.title, p.page, p.text FROM passages p "
                                        "JOIN documents d ON d.doc_id=p.doc_id WHERE p.doc_id=? LIMIT 2",
                                        (ids["cloud"],))]
    with ws.connect() as cx, tasks.queueing(True):
        tasks._insert_task(cx, "check:mixed-in", "check", "sonnet",
                           claimcheck._payload(ws, cid, "Hydrogen needs water.", None, None, picked))
    waiting = claimcheck.local_waiting(ws, [hid], retry_failed=True)
    assert any(r.get("mix") for r in waiting) and any(not r.get("mix") for r in waiting)

    st, r = api("POST", f"/api/projects/Mixed/hypotheses/{hid}/judge-local", {})
    assert st == 200 and r["excerpts"] > 0
    row = ws.query("SELECT status, model FROM tasks WHERE task_id='check:mixed-in'")[0]
    assert row["status"] == "pending" and row["model"] == "sonnet"   # still the models' work, not the person's


# ---------------------------------------------------------------------------------------------
# A2: Run again / Start it anyway (0.19.4)
# ---------------------------------------------------------------------------------------------
def test_a_job_refused_for_memory_runs_again_through_the_app(served):
    api, app = served
    seen: list[bool] = []

    def name_themes(job):
        readers = access.Readers(None, "")
        seen.append(readers.check_memory)
        if readers.check_memory:
            raise llm.MemoryShort("qwen3.5:9b", int(8.1 * GB), int(6.9 * GB))
        return {"named": 3}

    first = _wait_job(app.jobs.start("theme-names", "The AI names the themes", None, name_themes, uses_model=True))
    assert first.error_kind == "memory"

    st, r = api("POST", f"/api/jobs/{first.id}/again", {})
    assert st == 200 and r["job"]["id"] != first.id and r["job"]["title"] == "The AI names the themes"
    again = api.wait(r["job"]["id"])
    assert again["state"] == "error" and again["error_kind"] == "memory"   # the memory was checked again

    st, r = api("POST", f"/api/jobs/{again['id']}/again", {"force": True})
    anyway = api.wait(r["job"]["id"])
    assert st == 200 and anyway["state"] == "done" and anyway["result"] == {"named": 3}
    assert seen == [True, True, False]

    other = _wait_job(app.jobs.start("x", "Other", None, lambda job: {"ok": 1}, uses_model=False))
    st, r = api("POST", f"/api/jobs/{other.id}/again", {"force": True})
    assert st == 409 and "can run again" in r["error"]
    st, r = api("POST", "/api/jobs/000000000000/again", {})
    assert st == 404 and "No such job" in r["error"]


# ---------------------------------------------------------------------------------------------
# A3: the local panel's status (0.19.4)
# ---------------------------------------------------------------------------------------------
def test_the_local_status_route_says_the_model_and_its_memory(served, monkeypatch):
    api, _app = served
    use_local_model(monkeypatch, None)
    st, r = api("GET", "/api/local-status")
    assert st == 200 and r["model"] is None and "No local model is chosen" in r["problem"]

    local = Watched(need=8 * GB, free=2 * GB)
    local.memory_status = lambda m: {"loaded": False, "need": 8 * GB, "free": 2 * GB, "short": True}
    use_local_model(monkeypatch, local)
    st, r = api("GET", "/api/local-status")
    assert st == 200 and r["model"] == "local-model" and r["server"] == "ollama"
    assert r["memory"] == {"loaded": False, "need": 8 * GB, "free": 2 * GB, "short": True}
    assert local.sent == []   # nothing was started to find out


# ---------------------------------------------------------------------------------------------
# A4: notifications (after 0.19.7)
# ---------------------------------------------------------------------------------------------
def test_the_test_notification_is_sent_when_notifications_are_on(served, monkeypatch):
    from margin.gui import notify

    api, app = served
    monkeypatch.delenv("MARGIN_NO_NOTIFY", raising=False)
    sent: list[tuple] = []

    def send_note(title, text, url="", **kw):
        sent.append((title, text, url))
        return {"sent": True, "how": "stand-in", "problem": ""}

    monkeypatch.setattr(notify, "send_note", send_note)
    st, r = api("POST", "/api/notify/test", {})
    assert st == 200 and r["sent"] is True and r["how"] == "stand-in" and r["problem"] == ""
    assert r["note"] == notify.where_to_allow()
    assert [t for t, _x, _u in sent] == ["Notifications work"]
    assert "has finished" in sent[0][1] and sent[0][2].startswith("http://127.0.0.1:") and app.token in sent[0][2]


def test_a_job_that_ends_reaches_the_notifications(served, monkeypatch):
    """The app hands every job that ends to notify.job_ended (server.App wires it): without that, no notification."""
    from margin.gui import notify

    _api, app = served
    heard: list[tuple] = []
    monkeypatch.setattr(notify, "job_ended", lambda a, job: heard.append((a, job.id, job.state)))
    job = _wait_job(app.jobs.start("x", "Some long work", None, lambda job: {"ok": 1}, uses_model=False))
    t0 = time.monotonic()
    while not heard and time.monotonic() - t0 < 10:
        time.sleep(0.01)
    assert heard == [(app, job.id, "done")]


# ---------------------------------------------------------------------------------------------
# A5: the label plan names the local model (0.19.4)
# ---------------------------------------------------------------------------------------------
def test_the_label_plan_says_what_the_local_model_reads(mixed, served, monkeypatch):  # noqa: F811
    ws, ids = mixed
    api, app = served
    local = Watched(need=8 * GB, free=2 * GB)
    local.memory_status = lambda m: {"loaded": False, "need": 8 * GB, "free": 2 * GB, "short": True}
    use_local_model(monkeypatch, local)
    monkeypatch.setattr(type(app), "backend", lambda self, kinds=None: (local, "main-model"))
    st, plan = api("GET", "/api/projects/Mixed/profile/plan?framework=sdg&all=1")
    assert st == 200, plan
    n_local = ws.scalar("SELECT COUNT(*) FROM passages WHERE section='body' AND doc_id=?", (ids["local"],))
    n_none = ws.scalar("SELECT COUNT(*) FROM passages WHERE section='body' AND doc_id=?", (ids["none"],))
    assert plan["local"] == n_local > 0 and plan["no_ai"] == n_none > 0
    assert plan["local_model"]["model"] == "local-model" and plan["local_model"]["memory"]["short"] is True
    assert local.sent == []

    # only documents Claude may read: no local model to speak of
    st, plan = api("GET", f"/api/projects/Mixed/profile/plan?framework=sdg&all=1&docs={ids['cloud']}")
    assert st == 200 and plan["local"] == 0 and "local_model" not in plan
