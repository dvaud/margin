"""0.19.6: the sidebar names the local model while it reads, and a short job's line says what it is doing.

Found in a user test on the Themes page, with Claude Code as the AI: naming the themes was refused for memory, the
local panel's Start ran it again, and qwen3.5:9b named the themes from documents marked Only a local AI. The sidebar's
work box said "to Claude" all the while, because a job of a kind that uses the AI of Settings was named after Settings.
The job's line said only "the AI is thinking it over", with nothing to show that a slow local model was getting on.
"""
from __future__ import annotations

import time
from pathlib import Path

from margin import profile
from margin.gui.api_common import Job, Jobs, job_where, latest_report, local_reader
from margin.gui.app_library import LibraryMixin

STATIC = Path(profile.__file__).parent / "gui" / "static"


def _running(kind: str = "theme-names", progress: dict | None = None) -> Job:
    j = Job(kind, "The AI names the themes", "P")
    j.state = "running"
    j.progress = progress or {}
    return j


def test_a_job_of_settings_ai_is_here_while_the_local_model_reads():
    m = {"who": "local", "model": "qwen3.5:9b", "phase": "thinking", "at": 2.0}
    j = _running(progress={"done": 1, "total": 3, "model": m})
    j.queue = True   # Claude Code is the AI of Settings
    v = j.view(full=False)
    assert v["where"] == "here" and v["local_model"] == "qwen3.5:9b"
    assert job_where(j) == "here" and not j.waits_on_queue()
    # between two themes ("done") it still reads: the sidebar does not flicker back to Claude
    j.progress["model"] = {**m, "phase": "done"}
    assert local_reader(j) == "qwen3.5:9b"
    # a later report from Claude Code's queue: the work waits for Claude now
    j.progress["queue"] = {"phase": "queue", "waiting": 2, "at": 3.0}
    v = j.view(full=False)
    assert v["where"] is None and "local_model" not in v and j.waits_on_queue()
    assert latest_report(j)["phase"] == "queue"
    # and the local model again, later still
    j.progress["model"] = {**m, "at": 4.0}
    assert job_where(j) == "here" and not j.waits_on_queue()


def test_no_local_model_no_change():
    # the main model's own reports (no "who"), a refused local model, a job that has ended, a job of a fixed place
    assert job_where(_running(progress={"model": {"phase": "thinking", "model": "qwen3.5:9b"}})) is None
    assert job_where(_running(progress={"model": {"who": "local", "phase": "refused", "model": "q"}})) is None
    ended = _running(progress={"model": {"who": "local", "phase": "thinking", "model": "q"}})
    ended.state = "done"
    assert job_where(ended) is None and "local_model" not in ended.view(full=False)
    assert job_where(_running("retractions", {"model": {"who": "local", "phase": "thinking"}})) == "crossref"
    # a queue report alone (no stamp, as before 0.19.6) still means the work waits for Claude Code
    q = _running(progress={"queue": {"phase": "queue", "waiting": 1}})
    q.queue = True
    assert q.waits_on_queue() and job_where(q) is None


def test_a_queued_job_stamps_each_report_so_the_later_one_wins():
    """start_queued_job keeps the model's report and the queue's apart; each now carries its time."""

    class Backend:
        progress = None
        should_stop = None

    be = Backend()
    jobs = Jobs()
    seen: dict = {}

    class App(LibraryMixin):
        def backend(self):
            return be, "claude"

        def _wire(self, job, b):
            pass

        def _ws_or_none(self, name):
            return None

        def start_job(self, kind, title, name, run, withdraw=(), ws=None):
            j = jobs.start(kind, title, name, run, uses_model=False)
            j.queue = True
            return j

    def fn(job, b, model, prog):
        b.progress({"phase": "queue", "waiting": 3})
        time.sleep(0.01)
        b.progress({"who": "local", "model": "qwen3.5:9b", "phase": "thinking", "thinking_tokens": 40})
        seen["local"] = job.view(full=False)
        time.sleep(0.01)
        b.progress({"phase": "queue", "waiting": 2})
        seen["claude"] = job.view(full=False)
        return {"named": 1}

    job = App().start_queued_job("theme-names", "The AI names the themes", "P", fn)
    for _ in range(300):
        if job.state in ("done", "error", "cancelled"):
            break
        time.sleep(0.01)
    assert job.state == "done", job.error
    assert seen["local"]["where"] == "here" and seen["local"]["local_model"] == "qwen3.5:9b"
    assert seen["claude"]["where"] is None and "local_model" not in seen["claude"]
    assert job.progress["model"]["at"] < job.progress["queue"]["at"]


def test_the_sidebar_and_the_short_job_line_use_it():
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "localModel: j.local_model" in app and "w.localModel" in app
    prog = (STATIC / "views" / "progress.js").read_text(encoding="utf-8")
    assert "export function modelDetail(" in prog and "export function timeLeft(" in prog
    # 0.19.13: the running model's figures and latest words, written in place in this computer's side
    assert "sideFigures(side, localNow ? modelFigures(m, this.seen) : null)" in prog
    # a queue report older than the model's does not make the panel say it waits for Claude Code
    assert "(m.at || 0) > (p.queue.at || 0)" in prog
    lib = (STATIC / "lib.js").read_text(encoding="utf-8")
    assert 'h("p", { class: "ar-tail", "aria-hidden": "true" }' in lib and 'h("span", { class: "ar-spark", "aria-hidden": "true"' in lib
    themes = (STATIC / "views" / "themes.js").read_text(encoding="utf-8")
    assert "timeLeft(atSecs, " in themes and "m.waiting ? null" in themes
    css = (STATIC / "components.css").read_text(encoding="utf-8")
    assert ".ar-fine {" in css and ".ar-tail {" in css


def test_a_local_done_is_not_this_computer_when_the_main_ai_reports_nothing():
    """The Claude API reports nothing while it reads: after the local model's "done" it may be Claude reading."""
    j = _running(progress={"model": {"who": "local", "model": "q", "phase": "done", "at": 1.0}})
    assert job_where(j) is None
    j.queue = True   # Claude Code: its queue reports as soon as it has work, so "done" still means the local model
    assert job_where(j) == "here"


def test_a_job_run_again_keeps_its_queue():
    import time as _t

    from margin import llm

    calls = []

    def fn(job):
        calls.append(1)
        if len(calls) == 1:
            raise llm.MemoryShort("qwen3.5:9b", 8, 2)
        return {}

    jobs = Jobs()
    first = jobs.start("theme-names", "The AI names the themes", "P", fn, uses_model=True)
    first.queue = True
    for _ in range(300):
        if first.state in ("done", "error", "cancelled"):
            break
        _t.sleep(0.01)
    assert first.error_kind == "memory"
    assert jobs.again(first).queue is True
