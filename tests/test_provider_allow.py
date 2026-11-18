"""Stage 2 fix round: a check by queue whose documents do not allow the agent's company (a project allows Anthropic
only, and Codex answers) no longer waits in silence.

- the check's job says why (progress phase "held": "Codex reads only documents that allow OpenAI…"), its excerpts are
  not counted as waiting for Codex, and once OpenAI is allowed for the project the same job goes on and finishes;
- the project's AI access counts the documents that allow the main route's company (GET …/ai-access);
- views/ai-access.js providerAllowLine: "Codex reads only documents that allow OpenAI: 0 of 3 do.", with its Allow
  button, the shared project's note instead, and nothing when every document allows it or the route is Claude's;
- the names follow the agent: the status "waiting", the steps of a check by queue.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from _views import needs_node, run_views
from test_app import api, home  # noqa: F401  (fixtures)

HERE = Path(__file__).resolve().parent


@pytest.fixture
def codex(monkeypatch):
    monkeypatch.setenv("MARGIN_CODEX", str(HERE / "fake_codex_cli.py"))
    from margin import agentcli

    monkeypatch.setattr(agentcli, "POLL", 0.2)
    monkeypatch.setattr(agentcli, "IDLE_ROUNDS", 3)
    agentcli.forget_status()
    return agentcli


def _job(api, jid):  # noqa: F811
    return api("GET", f"/api/jobs/{jid}")[1]


def _until(fn, seconds=60, every=0.2):
    t0 = time.time()
    while time.time() - t0 < seconds:
        got = fn()
        if got:
            return got
        time.sleep(every)
    raise AssertionError("it did not happen in time")


def _run_agent(api, codex):  # noqa: F811
    st, r = api("POST", "/api/projects/Q/queue/agent", {})
    assert st == 200, r
    _until(lambda: not codex.run_state("codex", "Q")["running"])


def test_a_check_held_for_its_company_says_why_and_goes_on_once_allowed(api, home, corpus, codex):  # noqa: F811
    from margin import ingest, taskqueue, verdicts

    ws = home.create_project("Q")
    ingest.ingest(ws, [corpus])          # the project allows Anthropic only (the default)
    home.update_settings({"allow_codex": True, "backend": "codex", "project": "Q"})
    st, info = api("GET", "/api/projects/Q/ai-access")
    assert st == 200 and info["ai_access"]["route_provider"] == "openai"
    assert info["ai_access"]["route_allowed"] == 0 and info["ai_access"]["route_cloud"] == 3
    assert verdicts.STATUS_TEXT["waiting"] == "Waiting for Codex"
    st, r = api("POST", "/api/projects/Q/checks", {"text": "Electrolysers need large amounts of fresh water."})
    assert st == 200, r
    jid = r["job"]["id"]
    # the search words have no document text: Codex answers them
    _until(lambda: taskqueue.status(ws, "Q")["waiting"])
    steps = [s["detail"] for p in (_job(api, jid)["progress"] or {}).get("parts", []) for s in p["steps"]]
    assert "Waiting for Codex to propose other words" in steps
    _run_agent(api, codex)
    # the excerpts: held, said in plain words, and not waiting for Codex
    job = _until(lambda: (lambda j: j if ((j.get("progress") or {}).get("model") or {}).get("phase") == "held"
                          else None)(_job(api, jid)))
    m = job["progress"]["model"]
    assert m["plain"].startswith("Codex reads only documents that allow OpenAI") and m["company"] == "OpenAI"
    assert m["excerpts"] > 0 and job["state"] == "running"
    listed = next(j for j in api("GET", "/api/jobs")[1]["jobs"] if j["id"] == jid)
    assert listed["on_hold"] is False          # not "1 task waiting · Start": nothing would start
    assert taskqueue.status(ws, "Q")["waiting"] == 0
    # OpenAI allowed for the project: the same job goes on, Codex reads, and it finishes
    st, r = api("PUT", "/api/projects/Q/ai-access", {"providers_default": ["anthropic", "openai"]})
    assert st == 200 and r["ai_access"]["route_allowed"] == 3
    _until(lambda: taskqueue.status(ws, "Q")["waiting"])
    _run_agent(api, codex)
    job = _until(lambda: (lambda j: j if j["state"] in ("done", "failed", "cancelled") else None)(_job(api, jid)))
    assert job["state"] == "done", job.get("error")
    assert {r[0] for r in ws.query("SELECT DISTINCT provider FROM ai_sent")} == {"openai"}
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='check' AND task_id LIKE '%:person'") == 0


def test_a_shared_project_cannot_allow_it_and_the_check_finishes_with_the_reason(api, home, corpus, codex,  # noqa: F811
                                                                                 monkeypatch):
    from margin import access, claimcheck, ingest

    ws = home.create_project("Q")
    ingest.ingest(ws, [corpus])
    home.update_settings({"allow_codex": True, "backend": "codex", "project": "Q"})
    monkeypatch.setattr(access, "is_shared", lambda *a, **k: True)
    st, r = api("POST", "/api/projects/Q/checks", {"text": "Electrolysers need large amounts of fresh water."})
    jid = r["job"]["id"]
    _until(lambda: api("GET", "/api/projects/Q/queue")[1]["waiting"])
    _run_agent(api, codex)
    job = _until(lambda: (lambda j: j if j["state"] in ("done", "failed") else None)(_job(api, jid)))
    assert job["state"] == "done"
    notes = str(job.get("progress"))
    assert "Codex may not read this shared project's documents" in notes
    assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='check' AND model=?", (claimcheck.PERSON,)) >= 1


PROBE = r"""
const LIST = [{ id: "anthropic", title: "Anthropic (Claude)", company: "Anthropic" },
  { id: "openai", title: "OpenAI", company: "OpenAI" }, { id: "gemini", title: "Google Gemini", company: "Google" }];
const CODEX = { list: LIST, keys: {}, route: "openai", set_up: ["openai"], other_set_up: true };
const INFO = { providers_default: ["anthropic"], route_provider: "openai", route_allowed: 0, route_cloud: 3, counts: { cloud: 3 } };

await scenario("Codex: the line, its counts and its button", async (t) => {
  t.state({ settings: { backend: "codex" }, providers: CODEX });
  const m = await t.module("views/ai-access.js");
  t.answer("PUT /api/projects/Study/ai-access", (b) => ({ ai_access: { ...INFO, providers_default: b.providers_default, route_allowed: 3 } }));
  let saved = null;
  const line = m.providerAllowLine("Study", INFO, (r) => { saved = r; });
  document.getElementById("view").appendChild(line);
  const out = { text: t.text(line), buttons: t.buttons(line) };
  await t.click("Allow OpenAI for this project", { within: line });
  out.put = t.calls.filter((c) => c.method === "PUT").map((c) => c.body);
  out.saved = !!saved;
  out.allowed = m.providerAllowLine("Study", { ...INFO, route_allowed: 3 }) === null;
  out.shared = t.text(m.providerAllowLine("Study", { ...INFO, shared: true, providers_note: "Only Anthropic may read a shared project's documents." }));
  out.sharedButtons = t.buttons(m.providerAllowLine("Study", { ...INFO, shared: true }));
  t.state({ settings: { backend: "claude_code" }, providers: { ...CODEX, route: "anthropic" } });
  out.claude = m.providerAllowLine("Study", INFO) === null;
  return out;
});

await scenario("it fetches the project's AI access itself", async (t) => {
  t.state({ settings: { backend: "antigravity" }, providers: { ...CODEX, route: "gemini" } });
  const m = await t.module("views/ai-access.js");
  t.answer("GET /api/projects/Study/ai-access", { ai_access: { ...INFO, route_provider: "gemini", route_allowed: 1 } });
  const slot = m.providerAllowLine("Study", null);
  document.getElementById("view").appendChild(slot);
  const before = t.hidden(slot);
  await t.settle(50);
  return { before, text: t.text(slot) };
});
"""


@pytest.fixture(scope="module")
def views(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("provider_allow"))


@needs_node
def test_the_line_names_the_agent_its_company_and_the_counts(views):
    r = views["Codex: the line, its counts and its button"]
    assert r["text"].startswith("Codex reads only documents that allow OpenAI: 0 of 3 do.")
    assert [b["label"] for b in r["buttons"]] == ["Allow OpenAI for this project"]
    assert r["put"] == [{"providers_default": ["anthropic", "openai"]}] and r["saved"]
    assert r["allowed"] is True and r["claude"] is True
    assert "Only Anthropic may read a shared project's documents." in r["shared"] and r["sharedButtons"] == []


@needs_node
def test_the_line_fetches_what_it_needs(views):
    r = views["it fetches the project's AI access itself"]
    assert r["before"] is True
    assert r["text"].startswith("Antigravity reads only documents that allow Google: 1 of 3 do.")
