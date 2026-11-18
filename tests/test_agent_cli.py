"""Stage 2 of other cloud providers: Codex and Antigravity on the queue (agentcli.py, taskqueue's route and provider).

- the queue reads for the agent route's provider: a document allowing only OpenAI is handed to Codex's connector and
  never to Claude's; one allowing only Anthropic never reaches Codex; switching the route relabels the open tasks;
- finding, status, installing, signing in and adding Margin to each CLI, against the stand-ins (fake_codex_cli.py,
  fake_agy_cli.py), never the real programs;
- the runner: one CLI process per helper on the provider's own model, a usage limit ends the run with the queue's
  "limit" words, Stop ends it and leaves the work waiting; Antigravity runs with a home and settings of its own,
  never the person's, is refused without its sandbox switch, and a tool it refused is reported.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from test_app import Api, api, home  # noqa: F401  (fixtures)

HERE = Path(__file__).resolve().parent
CODEX = str(HERE / "fake_codex_cli.py")
AGY = str(HERE / "fake_agy_cli.py")
INSTALLER = str(HERE / "fake_agent_installer.py")


@pytest.fixture
def clis(monkeypatch):
    """The stand-ins found, and a runner that looks often (the tests do not wait two seconds a round)."""
    monkeypatch.setenv("MARGIN_CODEX", CODEX)
    monkeypatch.setenv("MARGIN_AGY", AGY)
    from margin import agentcli

    monkeypatch.setattr(agentcli, "POLL", 0.2)
    monkeypatch.setattr(agentcli, "IDLE_ROUNDS", 3)
    agentcli.forget_status()
    return agentcli


def _project(corpus, route, allow=("anthropic", "openai", "gemini")):
    """Project Q with the corpus read, the main route `route` (allowed), and its label tasks in the queue."""
    from margin import access, home, ingest, profile, tasks

    if route != "claude_code":
        home.update_settings({f"allow_{route}": True, "backend": route})
    ws = home.create_project("Q")
    home.update_settings({"project": "Q"})
    access.sync_labels(ws, access.route_provider(home.load_settings()))   # as the app does on each request
    ingest.ingest(ws, [corpus])
    if allow is not None:
        access.set_providers_default(ws, list(allow))
    profile.keyword_pass(ws, "sdg")
    plan = profile.label_plan(ws, "sdg", all_passages=True)
    with tasks.queueing():
        profile.make_label_tasks(ws, "sdg", plan["passage_ids"], "haiku", all_passages=True)
    return ws


def _waiting(ws):
    return ws.scalar("SELECT COUNT(*) FROM tasks WHERE COALESCE(queued, 0)=1 AND status IN ('pending', 'retry')")


def _doc_of(ws, task_id):
    payload = json.loads(ws.scalar("SELECT payload_json FROM tasks WHERE task_id=?", (task_id,)))
    pid = payload.get("passage_id") or (payload.get("passages") or [{}])[0].get("passage_id")
    return ws.scalar("SELECT doc_id FROM passages WHERE passage_id=?", (pid,))


def _wait_done(agentcli, route, project="Q", seconds=60):
    for _ in range(int(seconds / 0.1)):
        st = agentcli.run_state(route, project)
        if not st["running"]:
            return st
        time.sleep(0.1)
    raise AssertionError(f"the run did not end: {st}")


# -- A1: the queue reads for the route's provider ------------------------------------------------------------------
def test_a_document_for_openai_only_goes_to_codex_and_not_to_claude(corpus):
    from margin import access, home, taskqueue

    ws = _project(corpus, "codex", allow=("anthropic", "openai"))
    docs = [r[0] for r in ws.query("SELECT doc_id FROM documents ORDER BY doc_id")]
    access.set_documents(ws, docs[:1], allow=["openai"])          # only OpenAI may read the first document
    access.set_documents(ws, docs[1:], allow=["anthropic", "openai"])
    queued = [r[0] for r in ws.query("SELECT task_id FROM tasks WHERE queued=1")]
    only_openai = {t for t in queued if _doc_of(ws, t) == docs[0]}
    assert only_openai, "the first document has label tasks in the queue"
    # Claude's connector (no MARGIN_ROUTE) never gets them, and they stay in Codex's queue
    seen = set()
    while True:
        got = taskqueue.next_tasks(ws, "label", route="claude_code")
        if not got.get("claim"):
            break
        seen |= {t["task_id"] for t in got["tasks"]}
    assert not seen & only_openai
    assert all(ws.scalar("SELECT queued FROM tasks WHERE task_id=?", (t,)) == 1 for t in only_openai)
    # Codex's connector gets them, recorded for OpenAI under Codex's name
    got = taskqueue.next_tasks(ws, "label", route="codex", n=50)
    assert {t["task_id"] for t in got["tasks"]} >= only_openai
    sent = {(r[0], r[1]) for r in ws.query("SELECT provider, route FROM ai_sent WHERE task_id IN (%s)"
                                           % ",".join("?" * len(only_openai)), list(only_openai))}
    assert sent == {("openai", "Codex")}
    assert ws.scalar("SELECT route FROM task_claims WHERE claim_id=?", (got["claim"],)) == "Codex"
    assert home.load_settings()["backend"] == "codex"


def test_a_document_for_anthropic_only_never_reaches_codex_and_a_switch_relabels(corpus):
    from margin import access, home, taskqueue

    ws = _project(corpus, "claude_code", allow=("anthropic", "openai"))
    docs = [r[0] for r in ws.query("SELECT doc_id FROM documents ORDER BY doc_id")]
    access.set_documents(ws, docs[:1], allow=["anthropic"])
    queued = [r[0] for r in ws.query("SELECT task_id FROM tasks WHERE queued=1")]
    claude_only = {t for t in queued if _doc_of(ws, t) == docs[0]}
    assert claude_only
    # a Codex connector started while the queue is Claude Code's: never those tasks, and they stay queued for Claude
    got = taskqueue.next_tasks(ws, "label", route="codex", n=50)
    assert not {t["task_id"] for t in got.get("tasks") or []} & claude_only
    assert all(ws.scalar("SELECT queued FROM tasks WHERE task_id=?", (t,)) == 1 for t in claude_only)
    # the main route becomes Codex: the open tasks are labelled for OpenAI, and those leave the queue
    home.update_settings({"allow_codex": True, "backend": "codex"})
    assert access.labels_provider(ws._conn()) == "openai"
    for t in claude_only:
        row = ws.query("SELECT queued, access FROM tasks WHERE task_id=?", (t,))[0]
        if row["access"] == "cloud":   # answered by the codex batch above: not open any more
            continue
        assert row["queued"] == 0
    assert taskqueue.queue_route() == "codex" and taskqueue.queue_provider() == "openai"


def test_the_queue_names_its_agent(corpus):
    from margin import taskqueue

    ws = _project(corpus, "codex")
    st = taskqueue.status(ws, "Q")
    assert st["agent_route"] == "codex" and st["agent_title"] == "Codex"
    assert st["command"] == "$margin-run Q" and "to OpenAI" in st["privacy"]
    info = taskqueue.queue_info(ws, "label")
    assert info["text"].startswith("Waiting for Codex") and info["agent_title"] == "Codex"
    assert taskqueue.limit_reached({"running": False, "limit": "Codex reached your plan's usage limit."}) \
        == "Codex reached your plan's usage limit."
    # Claude Code's words are as they were
    assert taskqueue.privacy_line("claude_code") == taskqueue.PRIVACY_LINE
    assert taskqueue.run_command("claude_code", "My project") == '/margin-run "My project"'


def test_the_connector_reads_for_its_route(monkeypatch):
    from margin import mcp_server

    assert mcp_server.route() == "claude_code" and mcp_server.reader() == "anthropic"
    monkeypatch.setenv("MARGIN_ROUTE", "codex")
    assert mcp_server.route() == "codex" and mcp_server.reader() == "openai"
    monkeypatch.setenv("MARGIN_ROUTE", "antigravity")
    assert mcp_server.reader() == "gemini"
    monkeypatch.setenv("MARGIN_ROUTE", "something-else")
    assert mcp_server.route() == "claude_code"


# -- A2: finding, status, installing, signing in, adding Margin ----------------------------------------------------
def test_not_found_and_status(clis, monkeypatch, tmp_path):
    monkeypatch.setenv("MARGIN_CODEX", str(tmp_path / "nothing"))
    st = clis.status("codex", refresh=True)
    assert st["found"] is False and st["ready"] is False and st["signed_in"] is None
    monkeypatch.setenv("MARGIN_CODEX", CODEX)
    st = clis.status("codex", refresh=True)
    assert st["found"] and st["signed_in"] is True and "researcher@example.org" in st["account"]
    # Margin is not added yet: the set-up is not finished (ready), though the app can start it (can_start)
    assert st["connector"] is False and st["ready"] is False and st["can_start"] is True
    assert st["version"].startswith("codex-cli")
    monkeypatch.setenv("FAKE_AGY_PLAN", "ultra")
    st = clis.status("antigravity", refresh=True)
    assert st["signed_in"] is True and "gemini-4-carbon-high" in st["models_available"]
    assert st["connector"] is False


def test_signed_out_is_said_and_a_start_is_refused(clis, monkeypatch, corpus):
    monkeypatch.setenv("FAKE_CODEX_LOGGED_OUT", "1")
    monkeypatch.setenv("FAKE_AGY_LOGGED_OUT", "1")
    assert clis.status("codex", refresh=True)["signed_in"] is False
    assert clis.status("antigravity", refresh=True)["signed_in"] is False
    _project(corpus, "codex")
    with pytest.raises(ValueError, match="not signed in"):
        clis.start_run("codex", "Q")


def test_codex_signs_in_in_the_background(clis, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_LOGGED_OUT", "1")
    r = clis.open_sign_in("codex")
    assert r == {"opened": True, "window": "", "command": "codex login"}
    proc = clis._LOGIN["codex"]
    proc.wait(30)
    assert clis.status("codex", refresh=True)["signed_in"] is True


def test_antigravity_signs_in_in_a_window(clis, monkeypatch):
    import subprocess
    import sys

    monkeypatch.setenv("FAKE_AGY_LOGGED_OUT", "1")
    opened = []

    def window(script):   # the "window": run what the script runs (the stand-in signs in)
        opened.append(script.read_text(encoding="utf-8"))
        subprocess.run([sys.executable, AGY], capture_output=True, check=True)
        return "Terminal (stand-in)"

    monkeypatch.setattr(clis, "_open_window", window)
    r = clis.open_sign_in("antigravity")
    assert r["opened"] and r["window"] == "Terminal (stand-in)" and r["command"].rstrip('"').endswith("agy")   # Windows: in a child PowerShell
    assert "antigravity-sign-in" in opened[0] and "Google account" in opened[0]
    assert clis.status("antigravity", refresh=True)["signed_in"] is True


def test_installer_lines_and_the_stand_in_installer(clis, monkeypatch, tmp_path):
    assert clis.installer_command("codex", "macos")["line"] == "curl -fsSL https://chatgpt.com/codex/install.sh | sh"
    assert "install.ps1" in clis.installer_command("codex", "windows")["line"]
    assert clis.installer_command("antigravity", "linux")["args"][:2] == ["/bin/bash", "-c"]
    assert clis.installer_command("antigravity", "windows")["line"] == "irm https://antigravity.google/cli/install.ps1 | iex"
    target = tmp_path / "bin" / "codex.py"
    monkeypatch.setenv("MARGIN_CODEX", str(target))
    monkeypatch.setenv("MARGIN_CODEX_INSTALLER", INSTALLER)
    assert not clis.find("codex")
    r = clis.install_cli("codex")
    assert r["ok"] and r["status"]["found"] and "installed" in r["text"]
    monkeypatch.setenv("FAKE_INSTALLER_FAIL", "1")
    monkeypatch.setenv("MARGIN_AGY", str(tmp_path / "bin" / "agy.py"))
    monkeypatch.setenv("MARGIN_AGY_INSTALLER", INSTALLER)
    r = clis.install_cli("antigravity")
    assert not r["ok"] and "Could not resolve host" in r["text"]


def test_adding_margin_to_codex(clis, monkeypatch):
    from margin import home

    r = clis.set_up("codex")
    assert all(s["ok"] for s in r["steps"]), r["steps"]
    assert r["status"]["connector"] is True and r["status"]["ready"] is True
    fake = json.loads((home.home() / "fake-codex.json").read_text())
    mcp = fake["mcp"]["margin"]
    assert mcp["env"] == {"MARGIN_HOME": str(home.home()), "MARGIN_ROUTE": "codex"}
    assert mcp["args"] == ["-m", "margin.mcp_server"]
    skill = clis.codex_skill_path().read_text()
    assert skill.startswith("---\nname: margin-run") and "$margin-run" in skill and "Margin" not in skill
    checker = (clis.codex_home() / "agents" / "margin-checker.toml").read_text()
    assert 'model = "gpt-6.2-sol"' in checker and "developer_instructions" in checker
    assert 'model = "gpt-6-luna"' in (clis.codex_home() / "agents" / "margin-labeller.toml").read_text()
    try:   # tomllib is Python 3.11+; Margin supports 3.10, where the words above are checked instead
        import tomllib
    except ModuleNotFoundError:
        tomllib = None
    if tomllib is not None:
        parsed = tomllib.loads(checker)
        assert parsed["name"] == "margin-checker" and "submit_answers" in parsed["developer_instructions"]
    # an earlier Margin's connector of the same name is replaced
    monkeypatch.setenv("FAKE_CODEX_MCP_DUPLICATE", "1")
    r = clis.set_up("codex")
    assert all(s["ok"] for s in r["steps"]), r["steps"]
    assert clis.stale("codex") == ""


def test_adding_margin_to_antigravity_leaves_the_persons_settings_alone(clis):
    """Margin's Antigravity has a home folder of its own: the set-up writes Margin's settings there and never touches
    the person's own (an earlier Margin merged a permission line into them)."""
    from margin import home

    p = clis.agy_settings_path()
    p.parent.mkdir(parents=True)
    before = json.dumps({"theme": "dark", "permissions": {"allow": ["read(*)"], "deny": ["shell(rm *)"]},
                         "trustedWorkspaces": ["/somewhere/else"]})
    p.write_text(before)
    r = clis.set_up("antigravity")
    assert all(s["ok"] for s in r["steps"]), r["steps"]
    assert p.read_text() == before and not p.with_name("settings.json.bak").exists()
    own = json.loads(clis.margin_agy_settings_path().read_text())
    assert own["permissions"] == {"allow": ["mcp(margin/*)"]}
    assert own["trustedWorkspaces"] == [str(clis.agy_work_folder())]
    assert clis.margin_agy_settings_path().is_relative_to(home.home())
    plug = clis.agy_plugin_folder()
    assert json.loads((plug / "plugin.json").read_text())["name"] == "margin-run"
    cfg = json.loads((plug / "mcp_config.json").read_text())["mcpServers"]["margin"]
    assert cfg["env"]["MARGIN_ROUTE"] == "antigravity" and cfg["enabledTools"] == list(clis.QUEUE_TOOLS)
    assert cfg["env"]["PYTHONUSERBASE"]   # the connector still finds a Margin installed in the person's user folder
    assert "model: flash" in (plug / "agents" / "margin-labeller.md").read_text()
    assert "model: pro" in (plug / "agents" / "margin-auditor.md").read_text()
    assert r["status"]["connector"] is True
    assert json.loads((home.home() / "fake-agy.json").read_text())["plugin"]["path"] == str(plug)


def test_margin_own_antigravity_settings_hold_only_what_is_safe(clis):
    """Whatever the person's own settings or an earlier window put in Margin's settings, they allow only Margin's
    connector, run nothing unasked and spend no AI credits; the person's telemetry choice is carried over."""
    p = clis.agy_settings_path()
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"toolPermission": "always-proceed", "permissions": {"allow": ["read_file(*)"]},
                             "useG1Credits": True, "enableTelemetry": False, "theme": "dark"}))
    mine = clis.margin_agy_settings_path()
    mine.parent.mkdir(parents=True)
    mine.write_text(json.dumps({"toolPermission": "always-proceed", "useAiCredits": True,
                                "permissions": {"allow": ["shell(*)"], "deny": ["mcp(margin/*)"]},
                                "trustedWorkspaces": ["/"], "editorFont": "mono"}))
    clis.prepare_agy_home()
    own = json.loads(mine.read_text())
    assert own == {"editorFont": "mono", "enableTelemetry": False, "permissions": {"allow": ["mcp(margin/*)"]},
                   "trustedWorkspaces": [str(clis.agy_work_folder())]}
    # an "off" of the person's wins on every call; an "on", or a telemetry object that logs prompts somewhere, never
    # comes over, and connectors or approvals written into Margin's file by anyone are dropped
    p.write_text(json.dumps({"telemetry": {"enabled": True, "logPrompts": True, "otlpEndpoint": "https://c.example"},
                             "improveProducts": True, "usageStatisticsEnabled": False}))
    mine.write_text(json.dumps({"usageStatisticsEnabled": True, "mcpServers": {"x": {"command": "x"}},
                                "autoAcceptEdits": True, "telemetry": {"enabled": False, "outfile": "/tmp/log"}}))
    clis.prepare_agy_home()
    own = json.loads(mine.read_text())
    assert own["usageStatisticsEnabled"] is False and own["telemetry"] == {"enabled": False}
    assert "improveProducts" not in own and "mcpServers" not in own and "autoAcceptEdits" not in own
    # a file agy is writing this very moment is left for the next call, never written from nothing
    mine.write_text('{"enableTelemetry": fal')
    clis.prepare_agy_home()
    assert mine.read_text() == '{"enableTelemetry": fal'
    assert clis.always_proceeds() is False
    env = clis.agy_env()
    assert env["HOME"] == env["USERPROFILE"] == str(clis.agy_home()) and env["XDG_CONFIG_HOME"] is None
    import sys

    if sys.platform == "darwin":   # the login keychain is found through $HOME/Library/Keychains
        link = clis.agy_home() / "Library" / "Keychains"
        assert link.is_symlink() and Path(link.readlink()) == clis.user_home() / "Library" / "Keychains"


def test_the_lines_an_earlier_margin_wrote_are_offered_and_removed(clis, api):
    from margin import home

    p = clis.agy_settings_path()
    p.parent.mkdir(parents=True)
    work = str(home.home() / "claude-runs" / "agy-work")
    p.write_text(json.dumps({"theme": "dark", "permissions": {"allow": ["read(*)", "mcp(margin/*)"]},
                             "trustedWorkspaces": ["/somewhere/else", work, "/tmp/margin-dev-1/claude-runs/agy-work"]}))
    st, body = api("GET", "/api/agent-setup?route=antigravity")
    assert st == 200 and len(body["own_leftovers"]) == 3 and body["own_settings"] == str(p)
    assert 'the permission line "mcp(margin/*)"' in body["own_leftovers"]
    st, body = api("POST", "/api/agent-setup/tidy", {"route": "antigravity"})
    assert st == 200 and len(body["removed"]) == 3 and body["own_leftovers"] == []
    assert json.loads(p.read_text()) == {"theme": "dark", "permissions": {"allow": ["read(*)"]},
                                         "trustedWorkspaces": ["/somewhere/else"]}
    assert "mcp(margin/*)" in p.with_name("settings.json.margin-tidy.bak").read_text()
    # only Margin's lines: a file with only those loses the keys it then has no use for; a private file stays private
    p.write_text(json.dumps({"permissions": {"allow": ["mcp(margin/*)"]}, "trustedWorkspaces": [work]}))
    import os
    import stat

    os.chmod(p, 0o600)
    assert clis.tidy_own_agy_settings()["removed"] and json.loads(p.read_text()) == {}
    if os.name != "nt":
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert clis.tidy_own_agy_settings() == {"removed": []}
    st, body = api("POST", "/api/agent-setup/tidy", {"route": "codex"})
    assert st == 400
    # settings that are not JSON are left alone, and said so
    p.write_text("{not json")
    with pytest.raises(ValueError, match="left them as they are"):
        clis.tidy_own_agy_settings()
    assert p.read_text() == "{not json"


def test_a_sign_in_kept_in_the_home_folder_is_asked_for_margin_own(clis, monkeypatch):
    """Where Antigravity keeps its sign-in under the home folder, Margin's copy says it is signed out, and its sign-in
    window runs with Margin's home, so the sign-in lands where Margin's runs look."""
    import os
    import subprocess
    import sys

    monkeypatch.setenv("FAKE_AGY_LOGIN_IN_HOME", "1")
    monkeypatch.setenv("FAKE_AGY_LOGGED_OUT", "1")
    assert clis.status("antigravity", refresh=True)["signed_in"] is False
    scripts = []

    def window(script):
        scripts.append(script.read_text(encoding="utf-8"))
        subprocess.run([sys.executable, AGY], capture_output=True, check=True,
                       env={**os.environ, "HOME": str(clis.agy_home()), "USERPROFILE": str(clis.agy_home())})
        return "Terminal (stand-in)"

    monkeypatch.setattr(clis, "_open_window", window)
    r = clis.open_sign_in("antigravity")
    assert str(clis.agy_home()) in scripts[0] and str(clis.agy_home()) in r["command"]
    assert clis.status("antigravity", refresh=True)["signed_in"] is True


def test_repair_writes_again_when_margin_changed(clis):
    from margin import home

    assert clis.repair() == {}            # never added: nothing to do
    clis.set_up("codex")
    rec = json.loads((home.home() / "agent-clis.json").read_text())
    rec["codex"]["version"] = "0.0.1"
    (home.home() / "agent-clis.json").write_text(json.dumps(rec))
    assert "0.0.1" in clis.stale("codex")
    r = clis.repair()
    assert r["codex"]["repaired"] and clis.stale("codex") == ""


# -- A3: the runner ------------------------------------------------------------------------------------------------
def test_start_codex_answers_the_queue_on_openais_models(clis, corpus):
    from margin import home

    ws = _project(corpus, "codex")
    assert _waiting(ws) > 0
    st = clis.start_run("codex", "Q")
    assert st["running"] and st["title"] == "Codex"
    st = _wait_done(clis, "codex")
    assert st["exit_code"] == 0, st
    assert "batch" in st["report"] and "answered by Codex" in st["report"]
    assert _waiting(ws) == 0
    assert {r[0] for r in ws.query("SELECT DISTINCT provider FROM ai_sent")} == {"openai"}
    assert {r[0] for r in ws.query("SELECT DISTINCT route FROM results")} == {"Codex"}
    prov = json.loads(ws.scalar("SELECT settings_json FROM results LIMIT 1"))
    assert prov["provider"] == "openai" and prov["model_id"] == "gpt-6-luna"
    fake = json.loads((home.home() / "fake-codex.json").read_text())
    argv = fake["execs"][0]["argv"]
    assert argv[argv.index("-m") + 1] == "gpt-6-luna" and argv[argv.index("-s") + 1] == "read-only"
    assert "--ignore-user-config" in argv and "--ephemeral" in argv and "--json" in argv
    assert 'mcp_servers.margin.enabled_tools=["next_tasks", "submit_answers", "release"]' in argv
    assert "features.shell_tool=false" in argv and 'approval_policy="never"' in argv
    assert argv[-1].startswith(clis.MARKER) and 'taken_by="margin-labeller in Codex"' in argv[-1]
    assert Path(fake["execs"][0]["cwd"]).name.startswith("codex-Q")
    assert not list(clis.runs_folder().glob("codex-*.run.json"))   # the record goes with the run


def test_the_thought_asks_codex_for_an_effort(clis, corpus):
    from margin import home

    _project(corpus, "codex")
    home.update_settings({"claude_thought": "intelligence"})
    clis.start_run("codex", "Q")
    assert _wait_done(clis, "codex")["exit_code"] == 0
    argv = json.loads((home.home() / "fake-codex.json").read_text())["execs"][0]["argv"]
    assert 'model_reasoning_effort="high"' in argv
    # Intelligence moves labels up the ladder: the middle tier's model
    assert argv[argv.index("-m") + 1] == "gpt-6.2-sol"


def test_start_antigravity_in_its_work_folder_on_the_plans_model(clis, corpus, monkeypatch):
    from margin import home

    monkeypatch.setenv("FAKE_AGY_PLAN", "ultra")
    ws = _project(corpus, "antigravity")
    clis.start_run("antigravity", "Q")
    st = _wait_done(clis, "antigravity")
    assert st["exit_code"] == 0, st
    assert _waiting(ws) == 0
    assert {r[0] for r in ws.query("SELECT DISTINCT provider FROM ai_sent")} == {"gemini"}
    run = json.loads((home.home() / "fake-agy.json").read_text())["runs"][0]
    argv = run["argv"]
    assert argv[argv.index("--model") + 1] == "gemini-3.8-flash"
    assert "--sandbox" in argv and "--disable-slash-commands" in argv and "--output-format" in argv
    assert Path(run["cwd"]) == clis.agy_work_folder()
    assert sorted(p.name for p in clis.agy_work_folder().iterdir()) == [".agents"]
    # its own home and settings: the one permission line, written on the first start; the person's never touched
    assert run["home"] == str(clis.agy_home()) and run["xdg"] is None
    assert run["settings"]["permissions"] == {"allow": ["mcp(margin/*)"]}
    assert not clis.agy_settings_path().exists()


def test_the_model_slug_antigravity_lists(clis):
    listed = ["gemini-3.8-flash", "gemini-4-hydrogen-high", "gemini-4-hydrogen-low", "gemini-4-argon"]
    assert clis._resolve_agy_model("gemini-3.8-flash", "high", listed) == ("gemini-3.8-flash", "high")
    assert clis._resolve_agy_model("gemini-4-hydrogen", None, listed) == ("gemini-4-hydrogen-high", None)
    assert clis._resolve_agy_model("gemini-4-hydrogen", "low", listed) == ("gemini-4-hydrogen-low", None)
    assert clis._resolve_agy_model("gemini-4-carbon", "high", listed) == ("gemini-4-carbon", "high")
    assert clis._resolve_agy_model("gemini-4-carbon", None, []) == ("gemini-4-carbon", None)
    assert clis.parse_models("gemini-4-carbon-high   Gemini 4 Carbon (High)\nModels on your plan:\n") \
        == ["gemini-4-carbon-high"]


def test_a_usage_limit_ends_the_run_with_the_queues_words(clis, corpus, monkeypatch):
    from margin import taskqueue

    monkeypatch.setenv("FAKE_CODEX_LIMIT", "1")
    ws = _project(corpus, "codex")
    n = _waiting(ws)
    clis.start_run("codex", "Q")
    st = _wait_done(clis, "codex")
    assert st["exit_code"] == 1 and st["limit"] == "Codex reached your plan's usage limit (it resets 3:00 PM)."
    assert taskqueue.limit_reached(st) == st["limit"]
    assert _waiting(ws) == n
    monkeypatch.delenv("FAKE_CODEX_LIMIT")
    monkeypatch.setenv("FAKE_AGY_LIMIT", "1")
    from margin import home

    home.update_settings({"allow_antigravity": True, "backend": "antigravity"})
    clis.start_run("antigravity", "Q")
    st = _wait_done(clis, "antigravity")
    assert st["limit"].startswith("Antigravity reached your plan's usage limit (it resets 15:00")


def test_stop_ends_the_helpers_and_the_work_waits(clis, corpus, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_DELAY", "60")   # each helper waits before it takes anything
    ws = _project(corpus, "codex")
    n = _waiting(ws)
    clis.start_run("codex", "Q")
    for _ in range(100):
        if clis.run_state("codex", "Q").get("helpers_running"):
            break
        time.sleep(0.1)
    rec = json.loads(next(clis.runs_folder().glob("codex-*.run.json")).read_text())
    assert rec["route"] == "codex" and rec["pids"]
    st = clis.stop_run("codex", "Q")
    assert st["running"] is False and st["stopped"] is True and "stopped" in st["report"]
    assert _waiting(ws) == n
    assert not any(clis._pid_is_helper(p) for p in rec["pids"])


def test_the_persons_own_permissions_never_reach_margin_runs(clis, corpus, monkeypatch):
    """A person whose own Antigravity runs every tool unasked, allows reading files and spends credits: Margin's runs
    see none of it (an earlier Margin refused to start instead), and the person's file stays as they set it."""
    monkeypatch.setenv("XDG_CONFIG_HOME", "/somewhere/the/persons/config")
    monkeypatch.setenv("GEMINI_API_KEY", "the-persons-own-key")   # never billed for Margin's runs
    from margin import home

    ws = _project(corpus, "antigravity")
    p = clis.agy_settings_path()
    p.parent.mkdir(parents=True)
    mine = {"toolPermission": "always-proceed", "permissions": {"allow": ["read_file(*)"]}, "useG1Credits": True}
    p.write_text(json.dumps(mine))
    clis.start_run("antigravity", "Q")
    assert _wait_done(clis, "antigravity")["exit_code"] == 0
    assert _waiting(ws) == 0
    for run in json.loads((home.home() / "fake-agy.json").read_text())["runs"]:
        if "-p" in run["argv"]:
            assert run["settings"] == {"permissions": {"allow": ["mcp(margin/*)"]},
                                       "trustedWorkspaces": [str(clis.agy_work_folder())]}
            assert run["xdg"] is None and run["gemini_key"] is None
    assert json.loads(p.read_text()) == mine


def test_an_antigravity_without_its_sandbox_is_refused(clis, corpus, monkeypatch):
    _project(corpus, "antigravity")
    monkeypatch.setenv("FAKE_AGY_OPTIONS", "-p --output-format --model --disable-slash-commands")
    with pytest.raises(ValueError, match=r"--sandbox"):
        clis.start_run("antigravity", "Q")
    clis._OPTIONS.clear()   # the help is read once per program file
    monkeypatch.setenv("FAKE_AGY_OPTIONS", "none")   # its help says nothing Margin knows: not started either
    with pytest.raises(ValueError, match="could not read the options"):
        clis.start_run("antigravity", "Q")


def test_a_tool_antigravity_refused_is_written_in_the_report(clis, corpus, monkeypatch):
    """A helper only needs Margin's tools: one Antigravity refused (denied_actions) is said, as a possible prompt
    injection, and the run goes on."""
    monkeypatch.setenv("FAKE_AGY_DENY", "read_file")
    ws = _project(corpus, "antigravity")
    clis.start_run("antigravity", "Q")
    st = _wait_done(clis, "antigravity")
    assert st["exit_code"] == 0 and _waiting(ws) == 0
    assert "tried to use ReadFile, and Antigravity refused it" in st["report"]
    assert st["refused"] and st["refused"][0]["tools"] == ["ReadFile"]
    o = clis.read_outcome("antigravity", json.dumps({"status": "SUCCESS", "response": "", "denied_actions": [
        {"action": "read_file", "display_name": "ReadFile"}, {"action": "run_command"}]}), 0)
    assert o["ok"] and o["refused"] == ["ReadFile", "run_command"]
    for odd in ("read_file", 2, None, {"x": 1}):   # a shape agy might use instead: never a run-ending error
        assert clis.read_outcome("antigravity", json.dumps({"status": "SUCCESS", "denied_actions": odd}), 0)["refused"] == []


def test_a_codex_without_settings_on_its_command_line_is_refused(clis, corpus, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_OPTIONS", "--json --model")
    _project(corpus, "codex")
    with pytest.raises(ValueError, match=r"\(-c\)"):
        clis.start_run("codex", "Q")


def test_a_helper_that_never_takes_a_batch_ends_the_run(clis, corpus, monkeypatch):
    """A CLI that ignores the Margin tools (Antigravity soft-denies a tool it would have to ask about) ends the run
    after a few helpers in a row, with what it said, instead of starting helpers for ever."""
    monkeypatch.setenv("FAKE_AGY_OPTIONS", "-p --output-format --model --sandbox")
    from margin import agentcli

    _project(corpus, "antigravity")
    real = agentcli.helper_prompt
    monkeypatch.setattr(agentcli, "helper_prompt", lambda *a: real(*a).replace("next_tasks(", "next_task_s("))
    clis.start_run("antigravity", "Q")
    st = _wait_done(clis, "antigravity")
    assert st["exit_code"] == 1 and "did not answer the queue" in st["report"]


def test_stop_all_runs_ends_every_agents_run(clis, corpus, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_DELAY", "60")
    _project(corpus, "codex")
    clis.start_run("codex", "Q")
    for _ in range(100):
        if clis.run_state("codex", "Q").get("helpers_running"):
            break
        time.sleep(0.1)
    stopped = clis.stop_all_runs()
    assert [(r["route"], r["project"]) for r in stopped] == [("codex", "Q")]
    assert clis.run_state("codex", "Q")["running"] is False
    assert clis.stop_all_runs() == []


# -- A4: the API ---------------------------------------------------------------------------------------------------
def test_agent_setup_endpoints(clis, api, monkeypatch):
    st, body = api("GET", "/api/agent-setup?route=nothing")
    assert st == 400 and "Choose an agent" in body["error"]
    st, body = api("GET", "/api/agent-setup?route=codex&refresh=1")
    assert st == 200 and body["title"] == "Codex" and body["company"] == "OpenAI"
    assert body["status"]["found"] and body["status"]["connector"] is False and body["installer"]["line"]
    assert body["adds"] and body["local_only"] is False
    st, body = api("POST", "/api/agent-setup", {"route": "codex"})
    assert st == 200 and all(x["ok"] for x in body["steps"]) and body["status"]["connector"] is True
    # already on this computer: nothing to install
    st, body = api("POST", "/api/agent-setup/install", {"route": "codex"})
    assert st == 409 and "already" in body["error"]
    monkeypatch.setenv("FAKE_CODEX_LOGGED_OUT", "1")
    st, body = api("POST", "/api/agent-setup/sign-in", {"route": "codex"})
    assert st == 200 and body["opened"] and body["command"] == "codex login"
    clis._LOGIN["codex"].wait(30)


def test_agent_install_endpoint_runs_a_job(clis, api, monkeypatch, tmp_path):
    monkeypatch.setenv("MARGIN_CODEX", str(tmp_path / "bin" / "codex.py"))
    monkeypatch.setenv("MARGIN_CODEX_INSTALLER", INSTALLER)
    st, body = api("POST", "/api/agent-setup/install", {"route": "codex"})
    assert st == 200
    job = api.wait(body["job"]["id"])
    assert job["state"] == "done", job
    assert clis.find("codex")


def test_state_names_the_agent_and_queue_agent_starts_and_stops_it(clis, api, corpus):
    from margin import home

    _project(corpus, "codex")
    st, state = api("GET", "/api/state")
    assert st == 200 and state["agent"]["route"] == "codex" and state["agent"]["start"] == "Start Codex"
    assert state["agent"]["company"] == "OpenAI" and state["clis"]
    st, body = api("POST", "/api/projects/Q/queue/agent", {})
    assert st == 200 and body["running"] and body["title"] == "Codex"
    assert _wait_done(clis, "codex")["exit_code"] == 0
    st, body = api("POST", "/api/projects/Q/queue/agent/stop", {})
    assert st == 200 and body["running"] is False
    # a route that has no queue agent is told so
    home.update_settings({"backend": "claude_code"})
    st, body = api("POST", "/api/projects/Nothing/queue/agent", {})
    assert st == 404
