"""0.11.3: a Start Claude Code button left unpressed while work waits asks for attention (it pulses after a few
seconds, and its line says that nothing runs until it is pressed), and a follow-up on a result that waits for
Claude Code carries the button too. The page decides from the queue's own state, so the tests hold that state to
what the page reads: work waits, nothing answers it, nothing started from Margin runs."""
from __future__ import annotations

import re
from pathlib import Path

from test_subscription_first import _queued_labels, _waiting, fake_claude  # noqa: F401  (fixture)
from test_app import api, home  # noqa: F401  (fixtures)

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"


def idle(q: dict) -> bool:
    """The page's idleQueue(q) (lib.js): when the button nudges."""
    return bool(q.get("route") == "claude_code" and q.get("can_start") and not (q.get("runner") or {}).get("running")
                and q.get("waiting") and not q.get("being_answered"))


def test_the_queue_says_when_work_waits_unanswered(api, corpus, monkeypatch, fake_claude):  # noqa: F811
    from margin import home as core
    from margin import taskqueue

    ws = _queued_labels(core, corpus)
    st, q = api("GET", "/api/projects/Q/queue")
    assert st == 200 and q["waiting"] == _waiting(ws) > 0
    assert idle(q), q  # work waits and nothing answers it: the button nudges
    # Claude Code started some other way (typed in a terminal) takes a batch: no nudge then
    claim = taskqueue.next_tasks(ws, n=1)
    assert claim["claim"]
    q = api("GET", "/api/projects/Q/queue")[1]
    assert q["being_answered"] >= 1 and not idle(q)
    taskqueue.release(ws, claim["claim"])
    assert idle(api("GET", "/api/projects/Q/queue")[1])
    # started from Margin: no nudge while it runs
    monkeypatch.setenv("FAKE_CLAUDE_DELAY", "30")
    try:
        assert api("POST", "/api/projects/Q/queue/claude-code", {})[0] == 200
        q = api("GET", "/api/projects/Q/queue")[1]
        assert q["runner"]["running"] is True and not idle(q)
    finally:
        # the run's record is kept per project name for the process: leave none behind for later tests of "Q"
        api("POST", "/api/projects/Q/queue/claude-code/stop", {})
        fake_claude._RUNS.pop("Q", None)


def test_nothing_to_nudge_when_claude_code_is_not_the_route(api, corpus, fake_claude):  # noqa: F811
    from margin import home as core

    _queued_labels(core, corpus)
    api("PUT", "/api/settings", {"backend": "baseline", "embed_backend": "off"})
    q = api("GET", "/api/projects/Q/queue")[1]
    assert q["waiting"] > 0 and not idle(q)


def test_the_page_nudges_and_follow_ups_carry_the_button():
    lib = (STATIC / "lib.js").read_text()
    # the page's rule is the one above, and the time counts per project (the sidebar and a waiting result redraw)
    rule = re.search(r"const idleQueue = \(q\) => (.+);", lib).group(1)
    for part in ('q.route === "claude_code"', "q.can_start", "!(q.runner || {}).running", "q.waiting", "!q.being_answered"):
        assert part in rule
    assert "const WAIT_SINCE = new Map();" in lib and "NUDGE_AFTER = 5000" in lib
    assert "Nothing runs until you press it." in lib and '"Stop Claude Code"' in lib
    # the nudge changes the button in place: a class, never a new button under the pointer
    nudge = lib[lib.index("  box.nudge = () => {"):lib.index("  if (o.nudge) {")]
    assert 'b.classList.add("ar-nudge")' in nudge and "replace(" not in nudge
    # 0.19.13: it takes the AI run panel's slow breath (5 s), in step with the clock (inStep: --ar-sync), and stands
    # still with a ring under reduced motion. Reads the cascade (tests/_static.py rule()), not the release's sheet
    from _static import all_css, rule

    assert "@keyframes ar-nudge" in all_css() and "inStep(b)" in nudge
    # the nudge is a state of the button component (components.css, 4.1), not of one page
    assert rule(".btn.ar-nudge", media="(prefers-reduced-motion: reduce)")["animation"] == "none"
    assert "5s" in rule(".btn.ar-nudge")["animation"] and "var(--ar-sync" in rule(".btn.ar-nudge")["animation-delay"]
    # a follow-up on a result (a stronger model, a second opinion, reading again) that waits for Claude Code: the
    # panel draws Claude's live side, with Start Claude Code
    progress = (STATIC / "views" / "progress.js").read_text()
    assert 'aiSide({ where: "cloud", live: true' in progress and "export class MiniJob extends AiRun" in progress
