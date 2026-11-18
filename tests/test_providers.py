"""Cloud providers other than Claude, stage 1 (providers.py): consent per document and per provider.

- R2/R4: a model server that is not on this computer is a cloud provider: a known one by its address (OpenAI, Mistral…)
  or `other`; it may read only the documents that allow it (Anthropic alone by default);
- R3: a project without the new setting means what it meant: "Claude may read it" is Anthropic only;
- R4: the work split and the queue follow the main route's provider; the ledger names the provider;
- R5: in a shared project only Anthropic may read, whatever this copy allows;
- R6: the cloud chat backend (key, HTTPS, quirks, plain errors, no key anywhere it should not be);
- R7: settings and keys.
"""
from __future__ import annotations

import pytest
from helpers_mixed_corpus import mixed_project

from margin import access, home, llm, tasks


@pytest.fixture
def mixed(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home.create_project("Mixed")
    ids = mixed_project(ws, tmp_path / "corpus")
    pid = {k: ws.scalar("SELECT passage_id FROM passages WHERE doc_id=? ORDER BY seq LIMIT 1", (v,)) for k, v in ids.items()}
    return ws, ids, pid


def _label(pid):
    return {"framework": "sdg", "passage_id": pid, "title": "t", "page": None, "text": "Green hydrogen and water.",
            "candidates": []}


def _insert(ws, tid, payload, kind="label"):
    with tasks.queueing(False):
        with ws.connect() as cx:
            tasks._insert_task(cx, tid, kind, "m", payload)
    return ws.query("SELECT * FROM tasks WHERE task_id=?", (tid,))[0]


# ---------------------------------------------------------------------------------------------
# R2/R4: the hole (written first, seen failing before the fix)
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "https://gpu.example.org/v1", "http://192.168.1.20:1234/v1"])
def test_a_cloud_address_in_the_local_server_field_may_not_read_claude_only_documents(mixed, url):
    ws, ids, pid = mixed
    row = _insert(ws, "label:sdg:" + pid["cloud"], _label(pid["cloud"]))
    assert row["access"] == "cloud"   # "Claude may read it": Anthropic only
    with pytest.raises(access.AccessError):
        access.require(llm.LocalBackend(base_url=url), row, ws)
    access.require(llm.LocalBackend(base_url="http://localhost:1234/v1"), row, ws)  # control: this computer


def test_which_provider_each_backend_is():
    from margin.llm import ClaudeCodeBackend, CloudBackend

    assert llm.LocalBackend(base_url="https://api.openai.com/v1").provider == "openai"
    assert llm.LocalBackend(base_url="https://api.mistral.ai/v1").provider == "mistral"
    assert llm.LocalBackend(base_url="https://gpu.example.org/v1").provider == "other"
    assert llm.LocalBackend(base_url="http://localhost:1234/v1").provider is None
    assert llm.OllamaBackend(base_url="http://192.168.1.20:11434").provider == "other"
    assert llm.OllamaBackend(base_url="http://127.0.0.1:11434").provider is None
    assert ClaudeCodeBackend().provider == "anthropic" and llm.BaselineBackend().provider is None
    assert CloudBackend("mistral", "k").provider == "mistral"
    # a stand-in without the attribute: by its name or its address
    assert access.provider_of(type("B", (), {"name": "anthropic"})()) == "anthropic"
    assert access.provider_of(type("B", (), {"name": "ollama", "base_url": "http://gpu.example.org:1"})()) == "other"


# ---------------------------------------------------------------------------------------------
# R3: a project without the new setting means what it meant
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("route", ["claude_code", "anthropic"])
def test_an_existing_project_behaves_as_before_on_claude(mixed, route):
    ws, ids, pid = mixed
    home.update_settings({"allow_cloud": True, "backend": route})
    assert "ai_providers_default" not in ws.config
    assert ws.scalar("SELECT COUNT(*) FROM documents WHERE ai_providers IS NOT NULL") == 0
    assert access.levels(ws) == access.levels(ws, provider=None)   # Anthropic reads what "Claude may read it" said
    assert access.levels(ws) == {ids["cloud"]: "cloud", ids["local"]: "local", ids["none"]: "none"}
    view = access.documents_view(ws)
    assert view[ids["cloud"]]["providers"] == ["anthropic"] and view[ids["cloud"]]["providers_own"] is None
    assert "sent_by" not in view[ids["cloud"]]
    with tasks.queueing(True):
        with ws.connect() as cx:
            tasks._insert_task(cx, "label:sdg:a", "label", "haiku", _label(pid["cloud"]))
    from margin import taskqueue

    got = taskqueue.next_tasks(ws, "label", taken_by="test")
    assert [t["task_id"] for t in got["tasks"]] == ["label:sdg:a"]
    assert ws.query("SELECT DISTINCT COALESCE(provider, 'anthropic') AS p FROM ai_sent")[0]["p"] == "anthropic"


# ---------------------------------------------------------------------------------------------
# R4: the work split, the ledger, the queue
# ---------------------------------------------------------------------------------------------
@pytest.fixture
def openai_server():
    import fake_servers

    srv, url = fake_servers.start("openai")
    try:
        yield srv, url + "/v1"
    finally:
        srv.shutdown()
        srv.server_close()


def _use_openai(ws=None):
    home.update_settings({"allow_cloud": True, "backend": "cloud_api", "cloud_provider": "openai",
                          "cloud_model": "fake-model:latest", **({"project": ws.root.name} if ws else {})})


@pytest.mark.parametrize("local_model", [True, False])
def test_a_check_sends_the_openai_route_only_what_allows_openai(mixed, openai_server, monkeypatch, local_model):
    from helpers_mixed_corpus import LOCAL_MARK, Local, use_local_model

    from margin import claimcheck
    from margin.llm import CloudBackend

    ws, ids, pid = mixed
    srv, base = openai_server
    a, b = ids["cloud"], ids["local"]
    access.set_documents(ws, [b], "cloud")                  # B: "Claude may read it" (Anthropic only), marked text
    access.set_documents(ws, [a], allow=["anthropic", "openai"])
    _use_openai()
    local = Local()
    use_local_model(monkeypatch, local if local_model else None)
    be = CloudBackend("openai", "good-key", base_url=base)
    hid = claimcheck.check_hypothesis(ws, "Green hydrogen production can increase water stress in arid regions.",
                                      be, "fake-model:latest", k=12, per_doc=4)
    sent = "\n".join(str(r[1]) for r in srv.requests if r[1]).lower()
    assert sent and LOCAL_MARK.lower() not in sent          # B never reached OpenAI
    if local_model:
        assert LOCAL_MARK.lower() in local.text()           # B was read by the local model
    else:                                                   # or waits for a person
        assert ws.scalar("SELECT COUNT(*) FROM verifications WHERE doc_id=? AND model='person'", (b,)) > 0
    rows = ws.query("SELECT DISTINCT doc_id, provider, route FROM ai_sent")
    assert rows and {r["doc_id"] for r in rows} == {a}
    assert {r["provider"] for r in rows} == {"openai"} and {r["route"] for r in rows} == {"OpenAI"}
    assert access.documents_view(ws)[a]["sent_by"]["openai"] > 0
    assert hid


def test_changing_the_route_or_a_documents_providers_relabels_the_queue(mixed):
    ws, ids, pid = mixed
    home.update_settings({"project": ws.root.name})
    access.set_documents(ws, [ids["local"]], "cloud")
    access.set_documents(ws, [ids["cloud"]], allow=["anthropic", "openai"])
    with tasks.queueing(True):
        with ws.connect() as cx:
            tasks._insert_task(cx, "label:a", "label", "haiku", _label(pid["cloud"]))   # allows OpenAI
            tasks._insert_task(cx, "label:b", "label", "haiku", _label(pid["local"]))   # Anthropic only
    q = lambda: {r["task_id"]: (r["access"], r["queued"]) for r in ws.query("SELECT * FROM tasks")}  # noqa: E731
    assert q() == {"label:a": ("cloud", 1), "label:b": ("cloud", 1)}
    _use_openai(ws)            # the main route is OpenAI now: B's task may not go to it
    assert q()["label:b"] == ("local", 0) and q()["label:a"][0] == "cloud"
    home.update_settings({"backend": "claude_code"})
    assert q()["label:b"][0] == "cloud"
    access.set_documents(ws, [ids["cloud"]], allow=["openai"])   # A no longer allows Anthropic
    assert q()["label:a"] == ("local", 0)
    # the Claude Code queue reads as Anthropic whatever the main route: never a task of a document it may not read
    from margin import taskqueue

    with ws.connect() as cx:
        cx.execute("UPDATE tasks SET queued=1, access='cloud'")   # a stale label
    _use_openai(ws)
    with ws.connect() as cx:
        cx.execute("UPDATE tasks SET queued=1, access='cloud'")
    got = taskqueue.next_tasks(ws, "label", taken_by="test")
    assert "label:a" not in [t["task_id"] for t in got["tasks"]]


def test_the_connector_and_the_file_queue_read_as_anthropic(mixed):
    ws, ids, pid = mixed
    access.set_documents(ws, [ids["cloud"]], allow=["openai"])
    _use_openai()
    assert access.levels(ws, [ids["cloud"]], provider="openai") == {ids["cloud"]: "cloud"}     # OpenAI's reading
    assert access.levels(ws, [ids["cloud"]], provider="anthropic") == {ids["cloud"]: "local"}  # Claude may not read it
    assert access.levels(ws, [ids["cloud"]]) == {ids["cloud"]: "cloud"}   # by default: as the person chose it
    # the connector shows Claude nothing of it
    from margin import docrole, mcp_server

    assert mcp_server.CLAUDE == "anthropic" and docrole is not None
    # the file queue writes nothing of it
    _insert(ws, "label:sdg:fq", _label(pid["cloud"]))
    tasks.export(ws, "label")
    assert ws.scalar("SELECT COUNT(*) FROM ai_sent WHERE task_id='label:sdg:fq'") == 0


# ---------------------------------------------------------------------------------------------
# R5: shared projects allow Anthropic only
# ---------------------------------------------------------------------------------------------
def test_a_shared_project_lets_only_anthropic_read(mixed, tmp_path):
    from margin.sync.folder import FOLDER

    ws, ids, pid = mixed
    access.set_documents(ws, [ids["cloud"]], allow=["anthropic", "openai"])   # allowed before it was shared
    access._write_config(ws, {FOLDER: str(tmp_path / "team")})
    assert access.is_shared(ws._conn(), ws)
    _use_openai()
    assert access.levels(ws, [ids["cloud"]], provider="openai") == {ids["cloud"]: "local"}
    assert access.levels(ws, [ids["cloud"]], provider="anthropic") == {ids["cloud"]: "cloud"}
    assert access.levels(ws, [ids["cloud"]]) == {ids["cloud"]: "cloud"}   # as the person chose it
    with pytest.raises(ValueError, match="colleagues have not agreed"):
        access.set_providers_default(ws, ["anthropic", "openai"])
    with pytest.raises(ValueError, match="colleagues have not agreed"):
        access.set_documents(ws, [ids["cloud"]], allow=["openai"])
    info = access.project_info(ws)
    assert info["shared"] and "colleagues have not agreed" in info["providers_note"]
    row = _insert(ws, "label:sdg:s", _label(pid["cloud"]))
    from margin.llm import CloudBackend

    with pytest.raises(access.AccessError, match="OpenAI may not read"):
        access.require(CloudBackend("openai", "k"), row, ws)


# ---------------------------------------------------------------------------------------------
# R6: the cloud chat backend
# ---------------------------------------------------------------------------------------------
def test_the_cloud_backend_sends_the_key_and_only_documented_fields(openai_server):
    from margin.llm import CloudBackend

    srv, base = openai_server
    be = CloudBackend("openai", "good-key", base_url=base)
    out = be.complete("expand", "SYS", "Claim: water stress", "fake-model:latest", {})
    assert out
    path, body, headers = srv.requests[-1]
    assert path.endswith("/v1/chat/completions") and headers.get("Authorization") == "Bearer good-key"
    assert body["max_completion_tokens"] and "max_tokens" not in body and body["seed"] == 42
    assert set(body) <= {"model", "messages", "stream", "temperature", "max_completion_tokens", "seed", "response_format"}
    assert be.inventory()["models"] == ["fake-model:latest", "fake-second:latest"]
    assert be.digest("fake-model:latest") == "name:openai/fake-model:latest"
    assert not [p for p, *_ in srv.requests if "/api/v0" in p]   # no LM Studio calls
    prov = llm.provenance(be, "fake-model:latest")
    assert prov["settings"]["provider"] == "openai" and prov["settings"]["route"] == "OpenAI"
    assert "good-key" not in repr(prov) and "good-key" not in repr(be)


def test_mistral_gets_random_seed_and_a_refused_field_is_left_out(openai_server):
    from margin.llm import CloudBackend

    srv, base = openai_server
    srv.forbidden = {"seed", "max_completion_tokens"}       # Mistral refuses fields it does not know
    be = CloudBackend("mistral", "good-key", base_url=base)
    assert be.complete("expand", "SYS", "Claim: water stress", "fake-model:latest", {})
    body = srv.requests[-1][1]
    assert body["random_seed"] == 42 and "seed" not in body and body["max_tokens"]
    # a model that takes no temperature of 0 (OpenAI's reasoning models): asked again without it
    srv.no_temperature = True
    be = CloudBackend("openai", "good-key", base_url=base)
    srv.forbidden = set()
    assert be.complete("expand", "SYS", "Claim: water stress", "fake-model:latest", {})
    assert "temperature" not in srv.requests[-1][1] and "temperature" in be.dropped("fake-model:latest")
    assert "temperature" not in llm.provenance(be, "fake-model:latest")["settings"]
    # Gemini documents no seed: none is sent or recorded
    srv.no_temperature = False
    be = CloudBackend("gemini", "good-key", base_url=base)
    be.complete("expand", "SYS", "Claim", "fake-model:latest", {})
    assert "seed" not in srv.requests[-1][1] and llm.provenance(be, "m")["seed"] is None


def test_azure_sends_its_api_key_header_to_the_resource_address(openai_server):
    from margin import providers
    from margin.llm import CloudBackend

    srv, base = openai_server
    assert providers.base_url("azure", "https://my-res.openai.azure.com") == "https://my-res.openai.azure.com/openai/v1"
    assert providers.base_url("azure", "my-res") == "https://my-res.openai.azure.com/openai/v1"
    with pytest.raises(ValueError):
        providers.base_url("azure", "")
    be = CloudBackend("azure", "good-key", base_url=base)
    be.complete("expand", "SYS", "Claim", "my-deployment", {})
    headers = {k.lower(): v for k, v in srv.requests[-1][2].items()}
    assert headers.get("api-key") == "good-key" and "authorization" not in headers
    assert be.models() == [] and be.check("my-deployment")["model_available"]   # Azure lists no deployments


def test_the_cloud_backend_needs_https_and_says_errors_plainly(openai_server, capsys, caplog):
    from margin.llm import BackendError, CloudBackend

    srv, base = openai_server
    with pytest.raises(BackendError, match="HTTPS"):
        CloudBackend("openai", "k", base_url="http://api.example.org/v1")
    with pytest.raises(BackendError, match="No API key"):
        CloudBackend("openai", "")
    secret = "sk-proj-SECRETSECRET1234567890"
    with pytest.raises(BackendError) as e:
        CloudBackend("openai", secret, base_url=base).complete("expand", "SYS", "Claim", "m", {})
    assert "OpenAI refused the key" in str(e.value) and secret not in str(e.value)
    with pytest.raises(BackendError) as e:
        CloudBackend("openai", secret, base_url=base).models()
    assert secret not in str(e.value)
    srv.status = 429
    with pytest.raises(BackendError, match="OpenAI: the limit of this key is reached"):
        CloudBackend("openai", "good-key", base_url=base).complete("expand", "SYS", "Claim", "m", {})
    out = capsys.readouterr()
    assert secret not in out.out + out.err and secret not in caplog.text


def test_the_key_is_kept_in_the_keychain_only(mixed, tmp_path):
    import zipfile

    from margin import bundle

    ws, ids, pid = mixed
    secret = "sk-proj-KEEPMEHERE0987654321"
    home.set_cloud_key("openai", secret)
    _use_openai()
    assert home.cloud_key("openai") == secret and home.cloud_keys()["openai"] is True
    settings_text = (home.home() / "settings.json").read_text()
    assert secret not in settings_text and '"cloud_provider": "openai"' in settings_text
    zpath = tmp_path / "move.zip"
    bundle.export_all(zpath)
    with zipfile.ZipFile(zpath) as zf:
        everything = b"".join(zf.read(n) for n in zf.namelist())
        manifest = zf.read(bundle.MOVE_MANIFEST).decode()
    assert secret.encode() not in everything
    assert "cloud_provider" not in manifest and '"backend": "cloud_api"' not in manifest
    be, model = home.make_backend(home.load_settings())
    assert be.provider == "openai" and model == "fake-model:latest" and secret not in repr(be)
    home.forget_cloud_key("openai")
    assert home.cloud_keys()["openai"] is False and home.cloud_key("openai") == ""


# ---------------------------------------------------------------------------------------------
# R7, R8: settings and routing
# ---------------------------------------------------------------------------------------------
def test_cloud_api_needs_allow_cloud_and_is_refused_on_a_local_only_computer(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    with pytest.raises(ValueError, match="Allow cloud models first: with OpenAI"):
        home.update_settings({"backend": "cloud_api", "cloud_provider": "openai"})
    with pytest.raises(ValueError, match="Choose which cloud provider"):
        home.update_settings({"backend": "cloud_api", "allow_cloud": True})
    with pytest.raises(ValueError):
        home.update_settings({"cloud_provider": "anthropic"})
    _use_openai()
    assert not home.main_reads_local(home.load_settings())
    assert access.route_provider(home.load_settings()) == "openai"
    monkeypatch.setenv("MARGIN_LOCAL_ONLY", "1")
    assert home.load_settings()["backend"] == "auto"           # switched off for good
    with pytest.raises(ValueError, match="switched off"):
        home.update_settings({"backend": "cloud_api"})
    with pytest.raises(ValueError, match="switched off"):
        home.set_cloud_key("openai", "sk-x")
    with pytest.raises(llm.BackendError, match="switched off"):
        home._make_backend({**home.load_settings(), "backend": "cloud_api", "cloud_provider": "openai",
                            "allow_cloud": True, "cloud_model": "m"})


def test_the_cloud_models_follow_the_ladder_with_the_recommendation_where_none_is_chosen():
    """Minor 2 of stage 2: another provider's API gets the three tiers of the Claude routes (labels small, checks
    middle, second opinions strong), each the person's model or else the provider's recommended one."""
    from margin import providers, routing

    s = {"backend": "cloud_api", "cloud_provider": "mistral", "cloud_model": "mistral-large-latest",
         "task_models": {"local": {"label": "qwen3:8b"}}}
    r = routing.from_settings(s)
    assert r.route == "cloud_api" and r.call_model("check") == "mistral-large-latest"
    # a local model's name is never sent to the provider: the small tier is Mistral's recommendation
    assert r.call_model("label") == providers.recommended("mistral")["small"] != "qwen3:8b"
    r = routing.from_settings({**s, "cloud_small_model": "mistral-small-latest"})
    assert r.call_model("label") == "mistral-small-latest" and r.call_model("link") == "mistral-small-latest"
    assert r.call_model("check") == "mistral-large-latest"
    assert r.api_id(r.step_up("label")) == "mistral-large-latest"
    # nothing chosen: the recommended line-up
    r = routing.from_settings({"backend": "cloud_api", "cloud_provider": "openai"})
    rec = providers.recommended("openai")
    assert (r.call_model("label"), r.call_model("check"), r.call_model("second")) == \
        (rec["small"], rec["middle"], rec["strong"])
    # Fable is Claude's only
    assert routing.from_settings({"backend": "cloud_api", "cloud_provider": "openai", "use_fable": True}) \
        .call_model("second") == rec["strong"]
    assert "cloud_api" in routing.OFF_COMPUTER and "cloud_api" not in routing.CLAUDE_ROUTES


def test_azure_has_no_recommendation_and_a_typed_deployment_serves_every_tier():
    from margin import routing

    r = routing.from_settings({"backend": "cloud_api", "cloud_provider": "azure", "cloud_model": "my-sol"})
    assert {r.call_model(k) for k in ("label", "check", "second")} == {"my-sol"}
    assert r.step_up("label") is None   # the same deployment: no step up


# ---------------------------------------------------------------------------------------------
# the app's API: keys (yes or no only), models, the allowance per document and per project
# ---------------------------------------------------------------------------------------------
@pytest.fixture
def app_api(mixed):
    import threading

    import test_app

    from margin.gui.server import make_server

    home.update_settings({"project": mixed[0].root.name})
    srv, app = make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield test_app.Api(f"http://127.0.0.1:{srv.server_address[1]}", app.token), mixed
    finally:
        srv.shutdown()
        srv.server_close()


def test_the_app_stores_a_key_and_says_only_whether_one_is_stored(app_api, openai_server, monkeypatch):
    import dataclasses

    from margin import providers

    api, (ws, ids, pid) = app_api
    srv, base = openai_server
    st, s = api("GET", "/api/state")
    assert s["providers"]["keys"]["openai"] is False and not s["providers"]["other_set_up"]
    assert [p["id"] for p in s["providers"]["list"]][0] == "anthropic"
    secret = "good-key"
    st, r = api("POST", "/api/settings/provider-key", {"provider": "openai", "key": secret})
    assert st == 200 and r["providers"]["keys"]["openai"] is True and secret not in str(r)
    st, s = api("GET", "/api/state")
    assert s["providers"]["other_set_up"] and s["providers"]["set_up"] == ["openai"] and secret not in str(s)
    monkeypatch.setitem(providers.TABLE, "openai", dataclasses.replace(providers.TABLE["openai"], base_url=base))
    st, r = api("GET", "/api/settings/provider-models?provider=openai")
    assert st == 200 and r["models"] == ["fake-model:latest", "fake-second:latest"]
    # none of OpenAI's line-up is in this key's list: the first candidate of each tier is recommended
    assert r["recommended"] == providers.recommended("openai")
    assert api("GET", "/api/settings/provider-models?provider=azure")[1] == {
        "models": [], "lists": False, "recommended": {"small": "gpt-6-luna", "middle": "gpt-6.2-sol",
                                                     "strong": "gpt-6.2-astra"}}
    st, r = api("PUT", "/api/settings", {"allow_cloud": True, "backend": "cloud_api", "cloud_provider": "openai",
                                         "cloud_model": "fake-model:latest"})
    assert st == 200 and r["backend_label"] == "OpenAI (API key) · fake-model:latest"
    st, r = api("POST", "/api/servers/test")
    assert st == 200 and r["message"].startswith("Connected to OpenAI") and r["model_available"]
    st, r = api("DELETE", "/api/settings/provider-key", {"provider": "openai"})
    assert st == 200 and r["providers"]["keys"]["openai"] is False
    assert api("POST", "/api/settings/provider-key", {"provider": "anthropic", "key": "x"})[0] == 400


def test_a_refused_key_is_told_apart_from_an_unreachable_provider(app_api, openai_server, monkeypatch):
    import dataclasses

    from margin import providers

    api, _ = app_api
    srv, base = openai_server
    monkeypatch.setitem(providers.TABLE, "openai", dataclasses.replace(providers.TABLE["openai"], base_url=base))
    api("POST", "/api/settings/provider-key", {"provider": "openai", "key": "wrong-key"})
    st, r = api("GET", "/api/settings/provider-models?provider=openai")
    # the stand-in answers 401: the key is wrong, and the key itself never comes back
    assert st == 200 and r["refused"] is True and "refused the key" in r["problem"] and "wrong-key" not in str(r)
    # the page then forgets it
    st, r = api("DELETE", "/api/settings/provider-key", {"provider": "openai"})
    assert r["providers"]["keys"]["openai"] is False
    # a provider out of reach is a problem, but the key is not called wrong
    api("POST", "/api/settings/provider-key", {"provider": "openai", "key": "good-key"})
    monkeypatch.setitem(providers.TABLE, "openai", dataclasses.replace(providers.TABLE["openai"], base_url="http://127.0.0.1:9/v1"))
    st, r = api("GET", "/api/settings/provider-models?provider=openai")
    assert st == 200 and r["problem"] and r["refused"] is False


def test_the_app_sets_the_providers_a_document_and_the_project_allow(app_api):
    api, (ws, ids, pid) = app_api
    st, r = api("PUT", f"/api/projects/{ws.root.name}/documents/ai-access",
                {"doc_ids": [ids["cloud"]], "providers": ["anthropic", "mistral"]})
    assert st == 200
    doc = next(d for d in r["documents"] if d["doc_id"] == ids["cloud"])
    assert doc["providers"] == ["anthropic", "mistral"] and doc["providers_own"] == ["anthropic", "mistral"]
    st, r = api("PUT", f"/api/projects/{ws.root.name}/documents/ai-access", {"doc_ids": [ids["cloud"]], "providers": None})
    assert next(d for d in r["documents"] if d["doc_id"] == ids["cloud"])["providers_own"] is None
    st, r = api("PUT", f"/api/projects/{ws.root.name}/ai-access", {"providers_default": ["openai"]})
    assert st == 200 and r["ai_access"]["providers_default"] == ["openai"]
    st, r = api("PUT", f"/api/projects/{ws.root.name}/ai-access", {"providers_default": []})
    assert st == 400 and "at least one" in r["error"]
    log = ws.query("SELECT text FROM research_log WHERE kind='ai-access' ORDER BY at")
    assert any("OpenAI" in r["text"] for r in log)


def test_a_server_on_another_computer_once_allowed_is_in_the_ledger(mixed):
    from helpers_mixed_corpus import Recorder

    ws, ids, pid = mixed
    access.set_providers_default(ws, ["anthropic", "other"])
    far = Recorder()
    far.name, far.base_url = "ollama", "http://gpu.example.org:11434"
    row = _insert(ws, "label:sdg:far", _label(pid["cloud"]))
    tasks.run_one(ws, row["task_id"], far, "m")
    assert far.sent
    rows = ws.query("SELECT DISTINCT provider, route FROM ai_sent WHERE task_id='label:sdg:far'")
    assert [(r["provider"], r["route"]) for r in rows] == [("other", "model server on another computer")]
