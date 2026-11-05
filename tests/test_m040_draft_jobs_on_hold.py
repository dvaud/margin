"""Margin: ENLENS 0.12's "not running" state covers Margin's own draft jobs. Finding the claims of a draft and checking
them wait in the queue for Claude Code like a check does, so the sidebar says they are not running while nothing
answers, and running once Claude Code takes their work."""
from __future__ import annotations

import time

from test_08_queue import _project
from test_app import api, home  # noqa: F401  (fixtures)

DRAFT = ("Remote work raised the productivity of software engineers by about 13 percent, according to recent "
         "studies. Hybrid arrangements reduce the rate at which staff quit their jobs.")


def _job(api, job_id):
    return next(j for j in api("GET", "/api/jobs")[1]["jobs"] if j["id"] == job_id)


def _until(fn, seconds=15.0):
    end = time.time() + seconds
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.2)
    return fn()


def _on_hold_until_claude_code_takes_it(api, jid, kind):
    from margin import home as core
    from margin import taskqueue

    try:
        assert _until(lambda: _job(api, jid)["on_hold"]), _job(api, jid)
        assert _job(api, jid)["kind"] == kind and _job(api, jid)["queue"] is True
        assert [j["on_hold"] for j in api("GET", "/api/state")[1]["jobs"] if j["id"] == jid] == [True]
        ws = core.open_project("P")
        claim = taskqueue.next_tasks(ws, n=1)
        assert claim["claim"]
        assert _job(api, jid)["on_hold"] is False   # Claude Code took a batch: running
        taskqueue.release(ws, claim["claim"])
        assert _job(api, jid)["on_hold"] is True    # given back unanswered: not running again
    finally:
        api("POST", f"/api/jobs/{jid}/cancel")
        api.wait(jid)
    assert not any(j["on_hold"] for j in api("GET", "/api/jobs")[1]["jobs"])


def test_finding_a_draft_s_claims_is_not_running_while_nothing_answers(api, corpus):  # noqa: F811
    _project(api, corpus)
    did = api("POST", "/api/projects/P/drafts", {"text": DRAFT, "title": "Chapter 2", "ai_access": "cloud"})[1]
    jid = api("POST", f"/api/projects/P/drafts/{did['draft']['draft_id']}/find", {})[1]["job"]["id"]
    _on_hold_until_claude_code_takes_it(api, jid, "draft-find")


def test_checking_a_draft_s_claims_is_not_running_while_nothing_answers(api, corpus):  # noqa: F811
    _project(api, corpus)
    did = api("POST", "/api/projects/P/drafts", {"text": DRAFT, "title": "Chapter 2", "ai_access": "cloud"})[1]
    did = did["draft"]["draft_id"]
    end = DRAFT.index("studies.") + len("studies.")
    st, body = api("POST", f"/api/projects/P/drafts/{did}/claims", {"start": 0, "end": end})
    assert st == 200, body
    jid = api("POST", f"/api/projects/P/drafts/{did}/check", {"k": 3})[1]["job"]["id"]
    _on_hold_until_claude_code_takes_it(api, jid, "draft-check")
