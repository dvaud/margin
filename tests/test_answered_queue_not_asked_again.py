"""0.19.14: once Claude Code has answered its part, nothing asks for Claude Code again.

Reading one more excerpt of a check whose round had a part for documents marked Only a local AI: Claude Code answered
its part, then the local model read its own for two minutes. All that time the AI run panel showed Start Claude Code
(the job's last queue report, "1 waits", outvoted the project's empty queue), and the job counted as on hold for Claude
Code (that report stayed its newest word until the local model's first). Each press started a run that found nothing.

1. The wait in the queue says when it is over (taskqueue.QUEUE_END): the queue's last report is dropped, in a Tracker
   and in a job's progress that keeps it apart, and a job is no longer on hold.
2. The panel keeps the job's last queue words (so its buttons stay put) but marks them stale: the project's queue says
   whether anything still waits.
"""
from __future__ import annotations

import threading
import time

import pytest
from _fakedom import NODE, run
from test_ai_run_panel_fixes import MORE_DOM

from margin import taskqueue, tasks
from margin.gui.api_common import Job, latest_report, local_reader
from margin.gui.progress import Tracker

needs_node = pytest.mark.skipif(not NODE, reason="node is not installed")


def _queued_task(ws) -> str:
    with tasks.queueing(), ws.connect() as cx:
        tasks._insert_task(cx, "expand:h1", "expand", "opus", {"claim": "Repair cafés reduce waste."})
    return "expand:h1"


def _answer_later(ws, tid: str, after: float = 0.4) -> None:
    def answer():
        time.sleep(after)
        with ws.connect() as cx:
            cx.execute("UPDATE tasks SET status='done', attempts=1 WHERE task_id=?", (tid,))

    threading.Thread(target=answer, daemon=True).start()


def test_the_wait_says_it_is_over_and_the_job_is_not_on_hold_any_more(ws, monkeypatch):
    monkeypatch.setattr(taskqueue, "QUEUE_POLL", 0.05)
    tid = _queued_task(ws)
    tracker = Tracker(expand=False)
    job = Job("more", "Reading more passages", "p")
    job.queue, job.state, job.tracker = True, "running", tracker
    seen: list[dict] = []

    class Be:
        should_stop = None

        @staticmethod
        def progress(info):
            seen.append(info)
            tracker.model_report(info)

    # while it waits: the queue's report, and the job is on hold (nothing answers it)
    t = threading.Thread(target=lambda: seen.append({"result": taskqueue.wait_for(ws, tid, Be())}), daemon=True)
    t.start()
    deadline = time.time() + 5
    while not any(i.get("phase") == "queue" for i in seen) and time.time() < deadline:
        time.sleep(0.02)
    assert job.waits_on_queue()
    _answer_later(ws, tid, after=0.05)
    t.join(5)
    assert seen[-1] == {"result": (True, [])}
    assert seen[-2] == {"phase": taskqueue.QUEUE_END}
    # answered: the job's latest word is not Claude Code's queue any more, so it is not on hold for it
    assert latest_report(job) is None and not job.waits_on_queue()


def test_the_end_of_a_wait_leaves_the_local_models_report_alone():
    tracker = Tracker(expand=False)
    tracker.model_report({"phase": "thinking", "who": "local", "seconds": 3})
    tracker.model_report({"phase": taskqueue.QUEUE_END})
    assert tracker.model["phase"] == "thinking"


def test_a_job_that_keeps_the_queue_apart_drops_it_at_the_end(ws, monkeypatch):
    """The jobs of start_queued_job (and the benchmark) keep the queue's report under progress["queue"]."""
    monkeypatch.setattr(taskqueue, "QUEUE_POLL", 0.05)
    tid = _queued_task(ws)
    job = Job("label", "Labels", "p")
    # the AI mix: the local model answered the task before, and said so ("done")
    job.queue, job.state = True, "running"
    job.progress = {"done": 0, "total": 2, "model": {"phase": "done", "who": "local", "model": "qwen", "at": time.time()}}

    had_queue: list[bool] = []

    class Be:
        should_stop = None

        @staticmethod
        def progress(info):  # as app_library.start_queued_job wires it
            taskqueue.end_report(info, job.progress) or job.progress.update(
                **{"queue" if info.get("phase") == "queue" else "model": {**info, "at": time.time()}})
            had_queue.append("queue" in job.progress)

    _answer_later(ws, tid)
    assert taskqueue.wait_for(ws, tid, Be()) == (True, [])
    assert had_queue and had_queue[0], "the queue's report was never kept: the test proves nothing"
    assert job.progress["queue"]["phase"] == taskqueue.QUEUE_END
    # not on hold for Claude Code, and the local model's older "done" does not come back as reading
    assert latest_report(job) is None and not job.waits_on_queue() and local_reader(job) is None


def test_the_queue_end_is_wired_wherever_a_job_keeps_the_queue_apart():
    from pathlib import Path

    gui = Path(taskqueue.__file__).parent / "gui"
    for name in ("app_library.py", "app_queue.py"):
        text = (gui / name).read_text(encoding="utf-8")
        assert "end_report(info, job.progress)" in text, name


PROBE = r"""
const L = await import(LIB);
const { aiRun } = await import(LIB.replace(/lib\.js$/, "views/progress.js"));
L.App.state = { settings: { backend: "claude_code", restricted_model: "qwen" }, project: "p" };
L.App.project = "p";
// Claude Code is not running: one excerpt waits for it, in the job's words and in the project's queue
QUEUE.runner = { running: false };
QUEUE.waiting = 1; QUEUE.being_answered = 0;
const qWords = { waiting: 1, being_answered: 0, text: "Waiting for Claude Code: 1 excerpt to read", command: "/margin-run p", privacy: null };
const local = (waiting, gate = "go") => ({ gate, waiting, noun: "excerpt", model: "qwen", memory: null, problem: null });
const waiting = { id: "j1", kind: "more", state: "running", seconds: 5, queue: true, local: local(2, "wait"),
  progress: { model: { phase: "queue", queue: qWords } } };
const panel = aiRun({ size: "compact", title: "Reading more passages", noun: "excerpt" });
document.body.appendChild(panel.el);
panel.update(waiting); await tick(); await tick();
const out = { askedBefore: !!find(panel.sides.cloud, "Start Claude Code") };
// the local model reads first while Claude's part still waits: Start Claude Code stays, and stays put through polls
// whose newest report flips between the queue's and the local model's
const start = find(panel.sides.cloud, "Start Claude Code");
out.stillAskedWhileItWaits = [];
for (const poll of [
  { ...waiting, local: local(2), progress: { model: { who: "local", phase: "thinking", seconds: 2 } } },
  waiting,
  { ...waiting, local: local(2), progress: { model: { who: "local", phase: "thinking", seconds: 4 } } },
]) {
  panel.update(poll); await tick(); await tick();
  out.stillAskedWhileItWaits.push(find(panel.sides.cloud, "Start Claude Code") === start && start.isConnected);
}
// Claude Code has answered its part (the project's queue is empty); the local model reads its own
QUEUE.waiting = 0;
for (const poll of [
  { ...waiting, local: local(2), progress: { model: null } },                                            // the wait ended
  { ...waiting, local: local(2), progress: { model: { who: "local", phase: "thinking", seconds: 20 } } },  // it reads
]) {
  await new Promise((r) => setTimeout(r, 3200));   // the side's cached queue answer is older than 3 s: asked again
  panel.update(poll); await tick(); await tick(); await new Promise((r) => setTimeout(r, 20));
}
out.askedAfter = !!find(panel.sides.cloud, "Start Claude Code");
out.cloudText = panel.sides.cloud.textContent;
console.log(JSON.stringify(out));
process.exit(0);
"""


@needs_node
def test_the_panel_does_not_ask_for_claude_code_once_its_part_is_answered(tmp_path):
    out = run(MORE_DOM + PROBE, tmp_path)
    assert out["askedBefore"] and out["stillAskedWhileItWaits"] == [True] * 3, out
    assert not out["askedAfter"], out
    assert "Nothing waits for Claude Code" in out["cloudText"], out
