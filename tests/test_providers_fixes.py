"""Stage 1 of other cloud providers, the fix round after two reviews: the provider rule applies only where a caller
names the provider that reads, so nothing provider-specific is stored, synced or shared, and every route reads only
what allows it.
"""
from __future__ import annotations

import json

import pytest
from helpers_mixed_corpus import mixed_project
from test_shared_projects import Person, anna_and_ben  # noqa: F401  (the fixture)

from margin import access, embed, home, llm, providers, tasks


@pytest.fixture
def mixed(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home.create_project("Mixed")
    ids = mixed_project(ws, tmp_path / "corpus")
    pid = {k: ws.scalar("SELECT passage_id FROM passages WHERE doc_id=? ORDER BY seq LIMIT 1", (v,)) for k, v in ids.items()}
    return ws, ids, pid


@pytest.fixture
def openai_server():
    import fake_servers

    srv, url = fake_servers.start("openai")
    try:
        yield srv, url + "/v1"
    finally:
        srv.shutdown()
        srv.server_close()


def _openai_route():
    home.update_settings({"allow_cloud": True, "backend": "cloud_api", "cloud_provider": "openai",
                          "cloud_model": "m"})


# 1. a colleague's merge sees the levels as stored, whatever the main route is
def test_a_merge_keeps_the_stored_settings_under_another_providers_main_route(anna_and_ben):  # noqa: F811
    anna, ben = anna_and_ben
    with ben:
        docs = [r[0] for r in ben.ws.query("SELECT doc_id FROM documents ORDER BY doc_id")]
    d1, d2 = docs[0], docs[1]
    for p in (anna, ben):
        with p:
            _openai_route()   # every document allows Anthropic only: for OpenAI's reading they would count as local
    with anna:
        access.set_documents(anna.ws, [d1], "cloud")
        access.set_documents(anna.ws, [d2], "local")
        from margin import ingest

        extra = anna.home.parent / "extra"
        extra.mkdir()
        (extra / "new_report.txt").write_text("A new report on hydrogen and water.\n\n" + "Electrolysis needs fresh "
                                              "water for every kilogram of hydrogen it makes. " * 20)
        ingest.ingest(anna.ws, [extra], ai_access="cloud")
        d3 = anna.ws.scalar("SELECT doc_id FROM documents WHERE path LIKE '%new_report%'")
    with ben:
        access.set_documents(ben.ws, [d1], "cloud")
        access.set_documents(ben.ws, [d2], "cloud")
    ben.bring_in(anna.send())
    with ben:
        stored = {r[0]: r[1] for r in ben.ws.query("SELECT doc_id, ai_access FROM documents")}
    assert stored[d1] == "cloud" and stored[d2] == "local"   # d1 as both said; a colleague's stricter d2 still wins
    assert stored[d3] == "cloud"   # a document new here comes with its stored setting, not OpenAI's reading of it
    anna.bring_in(ben.send())
    with anna:
        stored = {r[0]: r[1] for r in anna.ws.query("SELECT doc_id, ai_access FROM documents WHERE doc_id IN (?, ?)",
                                                     (d1, d2))}
        assert access.levels(anna.ws, [d1, d2]) == {d1: "cloud", d2: "local"}
    assert stored == {d1: "cloud", d2: "local"}


# 2. a remote embedder reads only what allows its provider
@pytest.mark.parametrize("url, prov", [("https://api.openai.com/v1", "openai"), ("https://gpu.example.org/v1", "other")])
def test_a_remote_embedder_reads_only_documents_that_allow_its_provider(mixed, url, prov):
    ws, ids, pid = mixed

    class Far:
        model = "far-embed"
        base_url = url

        def __init__(self):
            self.seen = []

        def embed(self, texts):
            self.seen += texts
            return [[1.0, 0.0] for _ in texts]

    home.update_settings({"backend": "claude_code"})
    far = Far()
    r = embed.build(ws, far)
    assert not far.seen and r["restricted_not_embedded"] > 0   # the open document allows Anthropic only
    access.set_documents(ws, [ids["cloud"]], allow=["anthropic", prov])
    far2 = Far()
    far2.model = "far-embed-2"
    embed.build(ws, far2)
    assert far2.seen and not any("zqx" in t.lower() for t in far2.seen)


# 3. the add-ons' floors answer for the provider asked
def test_the_file_queue_exports_nothing_of_a_working_document_claude_may_not_read(mixed):
    from margin import docrole

    ws, ids, pid = mixed
    access.set_documents(ws, [ids["cloud"]], allow=["openai"])
    with ws.connect() as cx:
        cx.execute("INSERT INTO hypotheses(hyp_id, text, created_at, origin, origin_id) VALUES ('h1', 'Water stress "
                   "rises.', '2026-11-17', ?, ?)", (docrole.ORIGIN, ids["cloud"]))
    _openai_route()
    access.sync_labels(ws, "openai")   # the project's tasks are labelled for OpenAI's reading
    with tasks.queueing(False):
        with ws.connect() as cx:
            tasks._insert_task(cx, "expand:h1", "expand", "m", {"claim": "Water stress rises.", "hyp_id": "h1"})
    assert ws.scalar("SELECT access FROM tasks WHERE task_id='expand:h1'") == "cloud"   # OpenAI may read it
    with ws.connect() as cx:
        assert access.label_payload(cx, {"hyp_id": "h1"}, provider="anthropic") == "local"
    tasks.export(ws, "expand")
    assert ws.scalar("SELECT COUNT(*) FROM ai_sent WHERE task_id='expand:h1'") == 0
    assert not list((ws.root / "tasks" / "expand").glob("*.jsonl")) or "h1" not in "".join(
        f.read_text() for f in (ws.root / "tasks" / "expand").glob("*.jsonl"))


# 4. a changed project default is seen at once, also through a connection
def test_a_changed_project_default_is_seen_at_once(mixed):
    ws, ids, pid = mixed
    for allowed, gemini in ((["anthropic", "openai"], "local"), (["anthropic", "gemini"], "cloud"),
                            (["anthropic", "openai"], "local")):
        access.set_providers_default(ws, allowed)
        with ws.connect() as cx:
            assert access.levels(cx, [ids["cloud"]], provider="gemini")[ids["cloud"]] == gemini


# 5a. the automatic route is the server it chose, not an address left unused
def test_the_automatic_routes_provider_is_the_server_it_chose():
    s = {"backend": "auto", "ollama_url": "http://localhost:11434", "openai_url": "https://gpu.example.org/v1"}
    access.auto_chose(None)
    assert access.route_provider(s) is None and access.route_address(s) is None
    access.auto_chose("http://127.0.0.1:11434")
    assert access.route_provider(s) is None
    access.auto_chose("https://gpu.example.org/v1")
    try:
        assert access.route_provider(s) == "other" and access.route_address(s) == "https://gpu.example.org/v1"
    finally:
        access.auto_chose(None)


# 7. no redirect is followed; nothing is listed on a local-only computer
def test_the_cloud_backend_follows_no_redirect(openai_server):
    import fake_servers

    srv, base = openai_server
    other, other_url = fake_servers.start("openai")
    try:
        srv.redirect = other_url + "/v1/chat/completions"
        with pytest.raises(llm.BackendError, match="redirect") as e:
            llm.CloudBackend("openai", "good-key", base_url=base).complete("expand", "S", "U", "m", {})
        assert "good-key" not in str(e.value)
        assert other.requests == []                      # the key went nowhere else
    finally:
        other.shutdown()
        other.server_close()


def test_the_model_list_is_refused_on_a_local_only_computer(mixed, monkeypatch):
    import threading

    import test_app

    from margin.gui.server import make_server

    srv, app = make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        api = test_app.Api(f"http://127.0.0.1:{srv.server_address[1]}", app.token)
        monkeypatch.setenv("MARGIN_LOCAL_ONLY", "1")
        st, body = api("GET", "/api/settings/provider-models?provider=openai")
        assert st == 403 and "switched off" in body["error"]
    finally:
        srv.shutdown()
        srv.server_close()


# 8. labelling tasks reads no settings; the provider is worked out once per job
def test_labelling_many_tasks_reads_no_settings(mixed, monkeypatch):
    ws, ids, pid = mixed
    calls = []
    real = home.load_settings
    monkeypatch.setattr(home, "load_settings", lambda *a, **k: calls.append(1) or real(*a, **k))
    with tasks.queueing(True):
        with ws.connect() as cx:
            for i in range(30):
                tasks._insert_task(cx, f"label:x:{i}", "label", "m",
                                   {"framework": "sdg", "passage_id": pid["cloud"], "candidates": [], "n": i})
            access.relabel(cx)
    assert calls == []


# should-fix: Gemini's errors, per-model drops, the recorded seed, Azure's address
def test_gemini_errors_drops_per_model_and_azure_addresses(openai_server):
    srv, base = openai_server
    srv.error_body = [{"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                                 "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}]
    with pytest.raises(llm.BackendError, match="Google Gemini refused the key"):
        llm.CloudBackend("gemini", "bad", base_url=base).complete("expand", "S", "U", "gemini-x", {})
    srv.error_body = None
    srv.no_temperature = True
    be = llm.CloudBackend("openai", "good-key", base_url=base)
    be.complete("expand", "S", "U", "o-model", {})
    assert be.dropped("o-model") == {"temperature"} and be.dropped("gpt-model") == set()
    srv.no_temperature = False
    be.complete("expand", "S", "U", "gpt-model", {})
    assert srv.requests[-1][1]["temperature"] == 0             # another model keeps it
    srv.forbidden = {"seed"}
    srv.requests.clear()
    be.complete("expand", "S", "U", "picky", {})
    assert "seed" in be.dropped("picky") and llm.provenance(be, "picky")["seed"] is None
    assert llm.provenance(be, "gpt-model")["seed"] == 42
    for given in ("https://res.openai.azure.com/openai/deployments/dep/chat/completions?api-version=2024-10-21",
                  "https://res.openai.azure.com/", "res"):
        assert providers.base_url("azure", given) == "https://res.openai.azure.com/openai/v1"
    with pytest.raises(ValueError):
        providers.base_url("azure", "https://user@evil.example/openai/v1")
