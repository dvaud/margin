"""0.19.13: starting Claude and starting the local model are two separate clicks.

The owner's decision for the AI run panel (option B, "two sides"): in a job that also sends work to Claude, the local
model (documents marked Only a local AI, and the AI mix's share) no longer starts by itself. Each job has a local gate
(`margin.localgate`): it waits for the local side's own Start (POST /api/jobs/<id>/local/start), nothing loads
the model meanwhile, Stop on the local side puts it back to waiting after the item in hand, and a memory refusal waits
again with the numbers (Start it anyway: `force`). An all-local job started by its own button needs no second click;
at the plan's limit with "local model takes over" the page offers the Start instead of starting it.
"""
from __future__ import annotations

import threading
import time

import pytest
from helpers_mixed_corpus import Cloud, mixed_project, use_local_model
from test_app import Api, home  # noqa: F401  (fixtures)
from test_local_memory import GB, HYP, Watched, _queued_check_answered

from margin import access, claimcheck, home as home_mod, llm, profile, taskqueue, terms, themes
from margin.gui import server
from margin.gui.api_common import Jobs
from margin.gui.app_queue import QueueMixin
from margin.gui.progress import LOCAL_PHASE, Tracker
from margin.localgate import GATE, LocalGate


def _until(cond, timeout: float = 30, step: float = 0.02) -> None:
    t0 = time.monotonic()
    while not cond():
        if time.monotonic() - t0 > timeout:
            raise AssertionError("the condition was not met in time")
        time.sleep(step)


def _ended(job) -> bool:
    # the job's end state is set before its `finally` ends the gate and stamps `finished`: wait for all of it (a CI
    # runner once read the state "error" while the gate had not ended yet)
    return job.state in ("done", "error", "cancelled") and job.finished is not None


@pytest.fixture
def mixed(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home_mod.create_project("Mixed")
    ids = mixed_project(ws, tmp_path / "corpus")
    profile.ensure_pass1(ws, "sdg")
    return ws, ids


def _labelled(ws, doc_id: str) -> int:
    return int(ws.scalar("SELECT COUNT(*) FROM tasks t JOIN passages p ON t.task_id = 'label:sdg:' || p.passage_id "
                         "WHERE t.kind='label' AND t.status='done' AND p.doc_id=?", (doc_id,)) or 0)


# ---------------------------------------------------------------------------------------------------------------------
# the gate itself
# ---------------------------------------------------------------------------------------------------------------------
def test_the_gate_waits_until_its_start():
    g = LocalGate()
    g.mixed()
    assert g.public == "wait" and g.view() is None   # no local work said yet: no local part in the job's view
    got: list[bool] = []
    t = threading.Thread(target=lambda: got.append(g.wait_open()))
    t.start()
    time.sleep(0.3)
    assert got == []                                   # still waiting: nothing may load the model
    g.open()
    t.join(5)
    assert got == [True] and g.state == "go"


def test_an_all_local_gate_waits_for_its_start_too():
    """0.20.1: a job whose only reader is the local model waits for its own Start as well (before, the button that
    asked for the work started it). A request nobody counted counts as one, so the panel offers the Start."""
    alone = LocalGate()
    got: list[bool] = []
    t = threading.Thread(target=lambda: got.append(alone.wait_open()))
    t.start()
    _until(lambda: alone.state == "wait")
    time.sleep(0.2)
    assert got == [] and alone.waiting == 1
    alone.open()
    t.join(5)
    assert got == [True] and alone.state == "go" and alone.waiting == 0
    both = LocalGate()
    both.mixed()
    stop = threading.Event()
    t = threading.Thread(target=lambda: both.wait_open(stop.is_set))
    t.start()
    time.sleep(0.3)
    assert both.state == "wait"
    stop.set()
    t.join(5)
    assert not t.is_alive() and both.state == "wait"  # stopped while it waited: still nothing started


def test_start_it_anyway_and_the_memory_refusal():
    g = LocalGate()
    g.mixed()
    g.involve(waiting=4, noun="passage")
    g.open()
    g.refused(llm.MemoryShort("qwen3.5:9b", 8 * GB, 2 * GB))
    v = g.view()
    assert v["gate"] == "wait" and v["memory"] == {"need": 8 * GB, "free": 2 * GB, "short": True}
    assert v["model"] == "qwen3.5:9b" and v["waiting"] == 4 and v["noun"] == "passage" and v["problem"] is None
    g.open(force=True)
    assert g.view()["gate"] == "force" and g.view()["memory"]["short"] is False


def test_stop_on_the_local_side_waits_after_the_item_in_hand():
    g = LocalGate()
    in_hand, go_on = threading.Event(), threading.Event()
    ran: list[int] = []

    def first():
        in_hand.set()
        go_on.wait(5)
        ran.append(1)

    g.later(first, noun="theme", mixed=True)
    g.later(lambda: ran.append(2), noun="theme", mixed=True)
    assert g.view()["waiting"] == 2 and g.view()["gate"] == "wait"
    g.open()
    assert in_hand.wait(5)
    g.close()            # pressed while the first one is read
    go_on.set()
    _until(lambda: ran == [1] and g.waiting == 1)
    time.sleep(0.3)
    assert ran == [1] and g.state == "wait"   # the second waits for Start again
    g.open()
    g.drain()
    assert ran == [1, 2] and g.waiting == 0


def test_an_item_refused_for_memory_is_read_again_after_start_it_anyway():
    g = LocalGate()
    tries: list[bool] = []

    def item():
        tries.append(g.state == "force")
        if g.state != "force":
            raise llm.MemoryShort("m", 8 * GB, 1 * GB)

    g.later(item, n=3, noun="excerpt", mixed=True)
    g.open()
    _until(lambda: g.refusals == 1 and g.state == "wait")
    assert g.waiting == 3 and g.view()["memory"]["short"] is True
    g.open(force=True)
    g.drain()
    assert tries == [False, True] and g.waiting == 0


# ---------------------------------------------------------------------------------------------------------------------
# in jobs: labels (local passages beside Claude's)
# ---------------------------------------------------------------------------------------------------------------------
def _labels_job(jobs, ws, cloud):
    def run(job):
        job.progress = {}
        cloud.progress = lambda info: job.progress.update(model={**info, "at": time.time()})
        return profile.run_labels(ws, "sdg", cloud, "claude-haiku", all_passages=True, should_stop=job.cancel.is_set)

    return jobs.start("label", "The AI labels passages (sdg)", "Mixed", run, uses_model=True)


def test_labels_wait_for_the_local_start_while_claude_reads(mixed, monkeypatch):
    ws, ids = mixed
    local, cloud = Watched(free=64 * GB), Cloud()
    use_local_model(monkeypatch, local)
    jobs = Jobs()
    job = _labels_job(jobs, ws, cloud)
    _until(lambda: _labelled(ws, ids["cloud"]) > 0 and job.gate.involved and job.gate.busy())
    time.sleep(0.3)
    v = job.view()
    assert job.state == "running" and local.sent == [] and _labelled(ws, ids["local"]) == 0
    assert v["local"]["gate"] == "wait" and v["local"]["waiting"] > 0 and v["local"]["noun"] == "passage"
    assert v["local"]["model"] == "local-model" and v["local"]["problem"] is None
    assert v["progress"]["model"]["who"] == "local" and v["progress"]["model"]["phase"] == "ready"
    assert "local_model" not in v   # nothing reads on this computer yet
    # the job does not hold the model's turn while it waits for the person: another job of the model runs
    other = jobs.start("x", "Other", "P2", lambda j: {"ok": 1}, uses_model=True)
    _until(lambda: _ended(other))
    job.gate.open()
    _until(lambda: _ended(job))
    assert job.state == "done", job.error
    assert local.sent and _labelled(ws, ids["local"]) > 0
    assert job.result["local_waiting"] == 0 and job.result["local_read"] > 0
    assert job.view()["local"]["gate"] == "go" and job.view()["local"]["waiting"] == 0


def test_a_memory_refusal_waits_for_start_it_anyway(mixed, monkeypatch):
    ws, ids = mixed
    local, cloud = Watched(need=8 * GB, free=2 * GB), Cloud()
    use_local_model(monkeypatch, local)
    job = _labels_job(Jobs(), ws, cloud)
    _until(lambda: job.gate.involved and job.gate.busy() and _labelled(ws, ids["cloud"]) > 0)
    job.gate.open()   # Start: refused, as this computer has too little memory free
    _until(lambda: job.gate.refusals > 0)
    v = job.view()
    assert job.state == "running" and v["local"]["gate"] == "wait"
    assert v["local"]["memory"] == {"need": 8 * GB, "free": 2 * GB, "short": True}
    assert _labelled(ws, ids["local"]) == 0
    job.gate.open(force=True)   # Start it anyway
    _until(lambda: _ended(job))
    assert job.state == "done", job.error
    assert _labelled(ws, ids["local"]) > 0 and job.result["local_waiting"] == 0


def test_stopping_the_job_leaves_the_local_passages_waiting(mixed, monkeypatch):
    ws, ids = mixed
    local, cloud = Watched(free=64 * GB), Cloud()
    use_local_model(monkeypatch, local)
    jobs = Jobs()
    job = _labels_job(jobs, ws, cloud)
    _until(lambda: job.gate.involved and job.gate.busy() and _labelled(ws, ids["cloud"]) > 0)
    jobs.cancel(job)
    _until(lambda: _ended(job))
    assert local.sent == [] and _labelled(ws, ids["local"]) == 0 and _labelled(ws, ids["cloud"]) > 0
    assert job.result is None or job.result["local_waiting"] > 0


def test_an_all_local_job_waits_for_the_local_start(mixed, monkeypatch):
    """0.20.1: labels of documents only the local model may read, asked for by Label passages, load nothing until the
    local model's own Start; a job started by that Start (local_start="go") reads at once."""
    ws, ids = mixed
    local, cloud = Watched(free=64 * GB), Cloud()
    use_local_model(monkeypatch, local)

    def run(job):
        return profile.run_labels(ws, "sdg", cloud, "claude-haiku", doc_ids=[ids["local"]], all_passages=True,
                                  should_stop=job.cancel.is_set)

    jobs = Jobs()
    job = jobs.start("label", "Labels", "Mixed", run, uses_model=True)
    _until(lambda: job.gate.involved and job.gate.public == "wait" and job.gate.waiting > 0)
    time.sleep(0.3)
    v = job.view()["local"]
    assert job.state == "running" and local.sent == [] and cloud.sent == [] and v["gate"] == "wait"
    job.gate.open()
    _until(lambda: _ended(job))
    assert job.state == "done", job.error
    assert cloud.sent == [] and local.sent and _labelled(ws, ids["local"]) > 0
    again = jobs.start("label", "Labels", "Mixed", run, uses_model=True, local_start="go")
    _until(lambda: _ended(again))
    assert again.state == "done" and again.gate.state == "go"


def test_naming_themes_only_the_local_model_may_read_waits_for_its_start(mixed, monkeypatch):
    """The owner's video of 18 November 2026: Name the themes, every theme of documents marked Only a local AI, started
    qwen3.5:4b at once. It now waits for the local model's own Start, and the page's AI line names the local model."""
    ws, ids = mixed
    local, cloud = Watched(free=64 * GB), Cloud()
    use_local_model(monkeypatch, local)
    terms.ensure(ws)
    run_id = themes.run(ws, k=3, mode="words")
    settings = {"backend": "claude_code"}
    access.set_documents(ws, [ids["cloud"]], "local")   # every document an AI may read: only on this computer
    assert themes.readers(ws, run_id, settings) == {"main": 0, "local": 3, "none": 0, "local_model": "local-model"}
    job = Jobs().start("theme-names", "Names", "Mixed",
                       lambda j: themes.name_with_model(ws, run_id, cloud, "claude-sonnet",
                                                        should_stop=j.cancel.is_set), uses_model=True)
    _until(lambda: job.gate.involved and job.gate.public == "wait" and job.gate.waiting > 0)
    time.sleep(0.3)
    v = job.view()["local"]
    assert job.state == "running" and local.sent == [] and cloud.sent == []
    assert v["gate"] == "wait" and v["waiting"] == 3 and v["noun"] == "theme"
    job.gate.open()
    _until(lambda: _ended(job))
    assert job.state == "done", job.error
    assert local.sent and cloud.sent == []


def test_the_themes_ai_line_counts_who_names_them(mixed, monkeypatch):
    ws, ids = mixed
    use_local_model(monkeypatch, Watched(free=64 * GB))
    terms.ensure(ws)
    run_id = themes.run(ws, k=3, mode="words")
    got = themes.readers(ws, run_id, {"backend": "claude_code"})
    assert got["main"] + got["local"] + got["none"] == 3 and got["main"] > 0
    assert themes.readers(ws, run_id, {"backend": "baseline"}) is None   # a model on this computer reads them all
    access.set_documents(ws, [ids["cloud"]], "local")
    monkeypatch.setattr(home_mod, "make_restricted_backend", lambda s: None)   # chosen, but not on this computer
    got = themes.readers(ws, run_id, {"backend": "claude_code"})
    assert got["main"] == 0 and got["local"] == 0 and got["none"] == 3 and "not on this computer" in got["local_problem"]
    use_local_model(monkeypatch, None)
    assert themes.readers(ws, run_id, {"backend": "claude_code"}) == {"main": 0, "local": 0, "none": 3,
                                                                      "local_model": None}


def test_outside_the_app_the_local_model_reads_at_once(mixed, monkeypatch):
    """The command line and the connector have no person to press Start: no gate, as before."""
    ws, ids = mixed
    local, cloud = Watched(free=64 * GB), Cloud()
    use_local_model(monkeypatch, local)
    assert GATE.get() is None and access.Readers(cloud, "x").gate is None
    res = profile.run_labels(ws, "sdg", cloud, "claude-haiku", all_passages=True)
    assert local.sent and res["local_waiting"] == 0


# ---------------------------------------------------------------------------------------------------------------------
# in jobs: a check by queue (Claude Code) whose local excerpts wait
# ---------------------------------------------------------------------------------------------------------------------
def _follow_job(jobs, ws, hid):
    app = server.App.__new__(server.App)  # follow_queued needs nothing else of the app

    def run(job):
        job.tracker = Tracker()
        app.follow_queued(job, ws, [hid], job.tracker, poll=0.01)
        return {"hyp_id": hid}

    return jobs.start("check", HYP, "Mixed", run, uses_model=False)


def test_a_check_by_queue_waits_for_the_local_start(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home_mod.create_project("Mixed")
    mixed_project(ws, tmp_path / "corpus")
    local = Watched(free=64 * GB)
    use_local_model(monkeypatch, local)
    monkeypatch.setattr(llm, "total_memory", lambda: 16 * GB)
    hid = _queued_check_answered(ws)
    jobs = Jobs()
    job = _follow_job(jobs, ws, hid)
    _until(lambda: job.gate.involved and (job.tracker.state()["model"] or {}).get("phase") == "ready")
    v = job.view()
    assert local.sent == [] and job.state == "running"
    assert v["local"]["gate"] == "wait" and v["local"]["noun"] == "excerpt" and v["local"]["waiting"] > 0
    assert v["progress"]["model"]["who"] == "local" and v["progress"]["model"]["phase"] == "ready"
    # the head and the step say the local model waits, not Claude Code (Claude's part is done)
    assert v["progress"]["message"] == LOCAL_PHASE["ready"]
    grade = [s for p in v["progress"]["parts"] for s in p["steps"] if s["key"] == "grade" and s["state"] == "running"]
    assert grade and all(s["detail"] == LOCAL_PHASE["ready"] for s in grade)
    # Stop: Claude Code's part is done, so the check is kept and its local excerpts wait (Read them now)
    jobs.cancel(job)
    _until(lambda: _ended(job))
    assert ws.scalar("SELECT 1 FROM hypotheses WHERE hyp_id=?", (hid,))
    assert job.state == "cancelled" and job.view()["result"]["kept"] == [hid]   # the page says what was kept
    assert job.view()["result"]["waiting_local"] > 0
    assert claimcheck.local_waiting(ws, [hid]) and local.sent == []
    # followed again, then started: the local model reads them, and the check is complete
    again = _follow_job(jobs, ws, hid)
    _until(lambda: again.gate.involved)
    again.gate.open()
    _until(lambda: _ended(again))
    assert again.state == "done", again.error
    assert local.sent and claimcheck.hypothesis_result(ws, hid)["waiting_local"] == 0
    # once read, none wait any more (it said 3 waiting after the end before)
    assert again.view()["local"]["waiting"] == 0 and again.view()["local"]["noun"] == "excerpt"


# ---------------------------------------------------------------------------------------------------------------------
# the endpoints
# ---------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def app_api(home):  # noqa: F811
    from margin.gui.server import make_server

    srv, app = make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield app, Api(f"http://127.0.0.1:{srv.server_address[1]}", app.token)
    srv.shutdown()
    srv.server_close()


def test_local_start_and_stop_endpoints(app_api):
    app, api = app_api
    ran: list[int] = []

    def run(job):
        g = GATE.get()
        g.later(lambda: ran.append(1), n=2, noun="excerpt", mixed=True)
        g.later(lambda: ran.append(2), n=1, noun="excerpt", mixed=True)
        g.drain(job.cancel.is_set)
        return {"ran": len(ran)}

    plain = app.jobs.start("x", "No local work", None, lambda job: time.sleep(0.5) or {}, uses_model=False)
    st, body = api("POST", f"/api/jobs/{plain.id}/local/start", {})
    assert st == 409 and "no work for the local model" in body["error"]
    assert api("GET", f"/api/jobs/{plain.id}")[1]["local"] is None

    job = app.jobs.start("check", "Mixed", None, run, uses_model=False)
    _until(lambda: job.gate.waiting == 3)   # both parts queued (involved turns true after the first)
    st, j = api("GET", f"/api/jobs/{job.id}")
    assert j["local"] == {"gate": "wait", "waiting": 3, "noun": "excerpt", "model": None, "memory": None,
                          "problem": None}
    assert any(x["id"] == job.id and x["local"]["gate"] == "wait" for x in api("GET", "/api/jobs")[1]["jobs"])
    st, body = api("POST", f"/api/jobs/{job.id}/local/stop")
    assert st == 200 and body["job"]["local"]["gate"] == "wait" and ran == []
    st, body = api("POST", f"/api/jobs/{job.id}/local/start", {"force": True})
    assert st == 200 and body["job"]["local"]["gate"] == "force"
    done = api.wait(job.id)
    assert done["state"] == "done" and done["result"] == {"ran": 2} and done["local"]["waiting"] == 0
    st, body = api("POST", f"/api/jobs/{job.id}/local/start", {})
    assert st == 409   # the job has ended


# ---------------------------------------------------------------------------------------------------------------------
# at the plan's limit with "local model takes over": an offer, never a start
# ---------------------------------------------------------------------------------------------------------------------
class _App(QueueMixin):
    def __init__(self, ws, settings):
        self.jobs, self._ws, self._s, self.started = Jobs(), ws, settings, []

    def settings(self):
        return self._s

    def ws(self, name):
        return self._ws

    def agent_runner(self, name):   # stage 2: the main route's agent run (Claude Code's here)
        from margin import claude_setup

        return claude_setup.run_state(name)

    def queue_mode(self):
        return True

    def _local_queue_job(self, name, what, kinds=None, background=False):
        self.started.append((what, background))


def test_at_limit_local_offers_the_start_and_never_starts_it(mixed, monkeypatch):
    ws, _ids = mixed
    from margin import claude_setup

    runner = {"running": False, "started_at": 123.0, "report": "You've hit your limit · resets 3pm"}
    monkeypatch.setattr(taskqueue, "status", lambda ws, name, **k: {"waiting": 5})
    monkeypatch.setattr(claude_setup, "run_state", lambda name: runner)
    app = _App(ws, {**home_mod.DEFAULTS, "at_limit": "local", "restricted_server": "ollama",
                    "restricted_model": "qwen3.5:9b"})
    out = app._at_limit("Mixed", ws, runner)
    assert out["choice"] == "local" and out["local_possible"] and out["offer_local"] is True
    assert out["started"] is False and app.started == []
    assert app._at_limit("Mixed", ws, runner)["offer_local"] is True   # offered until it is pressed
    app.start_queue_run("Mixed", {"local": "limit"})                     # the local side's Start
    assert app.started == [("limit", False)]
    assert app._at_limit("Mixed", ws, runner)["offer_local"] is False
    # "wait" offers nothing
    app._s["at_limit"] = "wait"
    ws.set_meta("limit_handled", "")
    assert app._at_limit("Mixed", ws, runner)["offer_local"] is False


# ---------------------------------------------------------------------------------------------------------------------
# found in review: Start it anyway through the memory check, a job that ends with an error, the AI mix
# ---------------------------------------------------------------------------------------------------------------------
def test_start_it_anyway_reads_a_check_by_queue_on_a_computer_short_of_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home_mod.create_project("Mixed")
    mixed_project(ws, tmp_path / "corpus")
    local = Watched(need=8 * GB, free=2 * GB)
    use_local_model(monkeypatch, local)
    monkeypatch.setattr(llm, "total_memory", lambda: 16 * GB)
    hid = _queued_check_answered(ws)
    job = _follow_job(Jobs(), ws, hid)
    _until(lambda: job.gate.involved)
    job.gate.open()   # Start: refused by the memory check before anything is sent
    _until(lambda: job.gate.refusals > 0 and job.gate.state == "wait")
    assert local.sent == [] and job.view()["local"]["memory"]["short"] is True and job.state == "running"
    # a short head (the local side has the numbers and Start it anyway), not the paragraph about Read them now
    _until(lambda: job.view()["progress"]["message"] == server.LOCAL_SHORT)
    assert not any("Read them now" in n for n in job.view()["progress"]["notes"])
    job.gate.open(force=True)   # Start it anyway
    _until(lambda: _ended(job))
    assert job.state == "done", job.error
    assert local.sent and claimcheck.hypothesis_result(ws, hid)["waiting_local"] == 0


def test_a_job_that_fails_stops_its_local_part():
    ran: list[int] = []

    def run(job):
        GATE.get().later(lambda: ran.append(1), noun="theme", mixed=True)
        raise ValueError("Claude failed")

    job = Jobs().start("theme-names", "Names", "P", run, uses_model=True)
    _until(lambda: _ended(job))
    assert job.state == "error" and job.gate.ended
    _until(lambda: not job.gate.busy(), timeout=5)
    job.gate.open()
    time.sleep(0.3)
    assert ran == []   # nothing reads for a job that has ended


def test_the_ai_mix_waits_for_its_start_and_start_it_anyway(mixed):
    ws, _ids = mixed
    from margin import tasks

    class Small:
        memory_guard = True

        def check_memory(self, model):
            if self.memory_guard:
                raise llm.MemoryShort(model, 8 * GB, 1 * GB)

    be, seen = Small(), []
    gate = LocalGate()

    def answer():
        token = GATE.set(gate)
        try:
            with tasks._mix_gate(ws, {"kind": "label"}, None, (be, "small")):
                seen.append(be.memory_guard)
        finally:
            GATE.reset(token)

    t = threading.Thread(target=answer)
    t.start()
    _until(lambda: gate.involved)
    time.sleep(0.3)
    assert seen == [] and gate.public == "wait" and gate.noun == "task"   # the mix's share never starts by itself
    gate.open()
    _until(lambda: gate.refusals == 1 and gate.state == "wait")
    assert seen == [] and gate.view()["memory"]["short"] is True        # refused: waits again, not sent to Claude
    gate.open(force=True)
    t.join(5)
    assert seen == [False] and be.memory_guard is True                   # this answer only


# ---------------------------------------------------------------------------------------------------------------------
# found in the panel's review: the local items of a mixed run are counted from the start, and a read counts down
# ---------------------------------------------------------------------------------------------------------------------
def test_mixed_theme_naming_hands_its_local_themes_to_the_gate_before_claude_answers(mixed, monkeypatch):
    """The local side said "no model works in this job" until the loop reached the local themes, after each of
    Claude's answers before them."""
    ws, _ids = mixed
    local = Watched(free=64 * GB)
    use_local_model(monkeypatch, local)
    terms.ensure(ws)
    run_id = themes.run(ws, k=3, mode="words")
    make = themes.make_name_tasks

    def make_local(ws_, rid, model, *a, **k):   # the last theme only the local model may name
        out = make(ws_, rid, model, *a, **k)
        with ws_.connect() as cx:
            last = cx.execute("SELECT MAX(task_id) FROM tasks WHERE kind='theme' AND task_id LIKE ?",
                              (f"theme:{rid}:%",)).fetchone()[0]
            cx.execute("UPDATE tasks SET access='local' WHERE task_id=?", (last,))
        return out

    monkeypatch.setattr(themes, "make_name_tasks", make_local)
    held, go = threading.Event(), threading.Event()

    class Slow(Cloud):
        def complete(self, kind, system, user, model, payload=None):
            held.set()
            go.wait(10)   # Claude's first answer takes its time
            return super().complete(kind, system, user, model, payload)

    job = Jobs().start("theme-names", "Names", "Mixed",
                       lambda j: themes.name_with_model(ws, run_id, Slow(), "claude-sonnet",
                                                        should_stop=j.cancel.is_set), uses_model=True)
    _until(lambda: held.is_set())
    _until(lambda: job.gate.involved, timeout=5)
    v = job.view()["local"]
    assert v["gate"] == "wait" and v["waiting"] == 1 and v["noun"] == "theme"   # before Claude's first answer
    go.set()
    job.gate.open()
    _until(lambda: _ended(job))
    assert job.state == "done", job.error
    assert job.view()["local"]["waiting"] == 0


def test_reading_the_local_excerpts_counts_down_and_says_excerpts(tmp_path, monkeypatch):
    """Read them now (the result page's read-local job): its local side counts excerpts, not "tasks", and says none
    wait once they are read."""
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home_mod.create_project("Mixed")
    mixed_project(ws, tmp_path / "corpus")
    local = Watched(free=64 * GB)
    use_local_model(monkeypatch, local)
    monkeypatch.setattr(llm, "total_memory", lambda: 16 * GB)
    hid = _queued_check_answered(ws)
    n = sum(r["passages"] for r in claimcheck.local_waiting(ws, [hid]))
    seen: list[int] = []

    def run(job):
        readers = access.Readers(None, "", should_stop=job.cancel.is_set)
        real = local.complete

        def complete(*a, **k):
            seen.append(job.gate.waiting)
            return real(*a, **k)

        local.complete = complete
        return {"n": claimcheck.run_local_parts(ws, [hid], readers)}

    job = Jobs().start("read-local", "Reading", "Mixed", run, uses_model=True, local_start="go")
    _until(lambda: _ended(job))
    assert job.state == "done", job.error
    assert n > 0 and seen and seen[0] == n
    v = job.view()["local"]
    assert v["noun"] == "excerpt" and v["waiting"] == 0


def test_the_local_panels_own_start_is_the_jobs_one_start(monkeypatch):
    """0.20.1 (review): the Profile page's local panel ("Start qwen…", every passage left is the local model's) started
    a labelling job whose gate then waited for a second Start. The panel's press reaches the job as its own Start."""
    app = server.App.__new__(server.App)
    app.jobs = Jobs()
    monkeypatch.setattr(server.App, "queue_mode", lambda self: False)
    monkeypatch.setattr(server.App, "backend", lambda self, *a, **k: (Cloud(), "x"), raising=False)
    monkeypatch.setattr(server.App, "_wire", lambda self, job, be: None, raising=False)
    monkeypatch.setattr(server.App, "_ws_or_none", lambda self, name: None, raising=False)
    for start, state in ((None, "auto"), ("go", "go"), ("force", "force")):
        job = app.start_queued_job("label", "Labels", None, lambda job, be, model, prog: {"ok": 1}, local_start=start)
        _until(lambda: _ended(job))
        assert job.gate.state == state
    from pathlib import Path

    js = (Path(server.__file__).parent / "static" / "views" / "profile.js").read_text(encoding="utf-8")
    assert 'onStart: (force) => start(startBtn, force, true)' in js and 'payload.local = force ? "force" : "go"' in js
