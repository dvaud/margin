"""0.18.0rc2 (M8): a local model that works without a terminal.

- `modeladvice.advise` suggests the models that fit THIS computer: one recommended, a smaller and quicker and a larger and
  more careful one beside it, only when they fit the memory and the disk with room to spare; made-up computers here;
- after Ollama is installed on Windows and the installer did not start it, Margin starts it itself and waits;
- Ollama on the computer but not running is started by the card by itself (once, not twice), then the model is offered;
- `GET /api/servers` gives the advice and the suggested models that fit; the page shows the choices.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import fake_servers
from margin import modeladvice, ollama_setup
from test_app import Api, api, home  # noqa: F401  (fixtures)

GB = 1 << 30
STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"


def pc(memory=16, disk=200, system="windows", unified=False, gpu=None):
    return {"memory": memory * GB, "disk_free": disk * GB, "system": system, "unified": unified,
            "gpu": gpu * GB if gpu else None}


def names(ladder):
    return [o["name"] for o in ladder["options"]]


S, M, L = modeladvice.SMALL_MODEL, modeladvice.MEDIUM_MODEL, modeladvice.LARGE_MODEL


def test_the_tiers_are_one_constant_each_and_the_qwen_builds_are_the_benched_ones():
    # I6: switching to the GGUF builds after their bench is a one-line change; not now
    assert (S, M, L) == ("ifm/k2-horizon:0.9b", "qwen3.5:4b", "qwen3.5:9b")
    assert [t["name"] for t in modeladvice.CHAT] == [S, M, L]
    assert modeladvice.answer_form(S) == "point" and modeladvice.answer_form(M) == "check"
    assert modeladvice.answer_form("ifm/k2-horizon:latest") == "point" and modeladvice.answer_form("qwen3:8b") == "check"


def test_a_16_gb_mac_gets_the_4b_tier_with_the_small_one_beside_it_in_plain_words():
    a = modeladvice.advise(pc(16, system="mac", unified=True))
    chat = a["chat"]
    assert chat["pick"]["name"] == M and chat["pick"]["role"] == "recommended" and chat["pick"]["answers"] == "suggestions"
    assert chat["smaller"]["name"] == S and chat["larger"] is None          # 9B needs ~10.7 GB here: not offered
    assert chat["pick"]["runner"] == "mlx" and chat["pick"]["speed"] == "quick"
    for o in chat["options"]:                                               # plain words for each, no model name
        assert o["size"].startswith("about ") and o["good_for"] and o["speed_text"]
        assert "qwen" not in o["good_for"].lower() and "k2" not in o["good_for"].lower()
    assert a["tier"] == {"tier": "medium", "answers": "suggestions", "words": "The local model", "size": chat["pick"]["size"],
                         "what": "It suggests a judgement for each excerpt it reads, for you to decide."}
    assert "16 GB of memory" in a["computer"]["words"] and "only your judgements count" in a["what_is_a_model"]


def test_memory_reckoning_counts_the_load_overhead_the_context_and_the_mlx_cache_up_to_the_guard():
    # I6 research section 2: 16 GB with qwen3.5:4b is about 7 GB (file 3.7 + overhead 0.4 + 16k context 1.0 + the guard's
    # 1.6 GB of growth on MLX); on llama.cpp (no Apple silicon) there is no growth
    mac = modeladvice.advise(pc(16, system="mac", unified=True))["chat"]["pick"]
    assert 6.5 * GB < mac["need"] < 7.0 * GB and mac["num_ctx"] == 16384
    win = modeladvice.advise(pc(16, gpu=12))["chat"]["pick"]
    assert win["name"] == M and win["runner"] == "llamacpp" and win["need"] < mac["need"] - 1.5 * GB
    small = modeladvice.advise(pc(8, system="mac", unified=True))["chat"]["pick"]
    assert small["name"] == S and small["need"] < 2 * GB and small["num_ctx"] == 8192
    # without the guard the MLX cache grows to 8 GiB, so the guard is what lets 24 GB take the 9B model
    big = next(t for t in modeladvice.CHAT if t["name"] == L)
    facts = pc(24, system="mac", unified=True)
    assert modeladvice._need(big, "chat", facts) < 0.5 * facts["memory"]
    assert modeladvice._need(big, "chat", facts) - modeladvice.growth(big, facts) + modeladvice.MLX_CACHE > 0.65 * facts["memory"]


def test_8_gb_gets_the_small_tier_and_never_one_that_does_not_fit():
    chat = modeladvice.advise(pc(8, system="mac", unified=True))["chat"]
    assert chat["pick"]["name"] == S and chat["pick"]["answers"] == "explorer" and names(chat) == [S]
    assert modeladvice.advise(pc(8, system="mac", unified=True))["tier"]["words"] == "The small local model"


def test_24_and_32_gb_get_the_9b_tier_with_the_4b_as_the_quicker_one():
    for mem in (24, 32):
        chat = modeladvice.advise(pc(mem, system="mac", unified=True))["chat"]
        assert chat["pick"]["name"] == L and chat["smaller"]["name"] == M and chat["larger"] is None


def test_no_graphics_card_gets_the_small_tier_and_a_card_the_larger_ones():
    plain = modeladvice.advise(pc(16))["chat"]
    carded = modeladvice.advise(pc(16, gpu=12))["chat"]
    assert plain["pick"]["name"] == S and plain["larger"]["name"] == M        # offered under Technical, not picked
    assert carded["pick"]["name"] == M and carded["pick"]["speed"] == "quick"
    assert "graphics card" in carded["pick"]["speed_text"]
    assert "graphics card with 12 GB" in modeladvice.advise(pc(16, gpu=12))["computer"]["words"]
    assert modeladvice.advise(pc(32, system="linux"))["chat"]["pick"]["name"] == S


def test_low_disk_space_steps_down_and_then_says_why():
    low = modeladvice.advise(pc(32, disk=6, system="mac", unified=True))["chat"]
    assert low["pick"]["name"] == S and M not in names(low)                  # 3.7 GB + room needs more than 6 GB
    none = modeladvice.advise(pc(32, disk=3))["chat"]
    assert none["pick"] is None and none["options"] == [] and "free disk space" in none["reason"]
    tiny = modeladvice.advise(pc(2, disk=100))["chat"]
    assert tiny["pick"] is None and "too little" in tiny["reason"] and "Claude" in tiny["reason"]


def test_search_by_meaning_starts_with_the_small_model_and_offers_the_multilingual_one():
    emb = modeladvice.advise(pc(16))["embed"]
    assert emb["pick"]["name"] == "nomic-embed-text" and emb["larger"]["name"] == "bge-m3"
    assert "many languages" in emb["larger"]["good_for"]
    assert modeladvice.advise(pc(4, disk=50))["embed"]["pick"]["name"] == "nomic-embed-text"
    assert modeladvice.advise(pc(16, disk=2))["embed"]["pick"] is None             # not even 0.3 GB of room to spare


def test_a_computer_that_cannot_be_read_is_not_refused_and_gets_the_small_tier():
    a = modeladvice.advise({"memory": None, "disk_free": None, "system": "linux", "unified": False, "gpu": None})
    assert a["chat"]["pick"] is not None and a["computer"]["words"] == ""
    # memory that cannot be read never picks a larger tier (everything would "fit")
    mac = modeladvice.advise({"memory": None, "disk_free": None, "system": "mac", "unified": True, "gpu": None})
    assert mac["chat"]["pick"]["name"] == S


def test_an_intel_mac_counts_as_no_graphics_card():
    assert modeladvice.advise(pc(16, system="mac", unified=False))["chat"]["pick"]["name"] == S


def test_the_older_model_offer_downloads_for_the_use_the_older_model_has(api, monkeypatch):
    monkeypatch.setattr(modeladvice, "computer", lambda *a, **k: pc(16, system="mac", unified=True))
    # Claude Code reads the documents; the old model reads those marked Only a local AI: the offer is for that use
    api("PUT", "/api/settings", {"backend": "claude_code", "allow_claude_code": True, "ollama_model": "",
                                 "restricted_server": "ollama", "restricted_model": "qwen3:8b"})
    older = api("GET", "/api/servers")[1]["older_model"]
    assert older == {"chosen": "qwen3:8b", "offer": M, "size": older["size"], "use": "restricted"}
    api("PUT", "/api/settings", {"backend": "ollama", "ollama_model": "qwen3:8b"})
    assert api("GET", "/api/servers")[1]["older_model"]["use"] == "ai"
    js = (STATIC / "views" / "settings.js").read_text(encoding="utf-8")
    assert 'use: older.use || "ai"' in js


def test_an_older_model_keeps_working_and_the_tier_is_offered_beside_it():
    adv = modeladvice.advise(pc(16, system="mac", unified=True))
    assert modeladvice.older_model("qwen3:8b", adv) == {"chosen": "qwen3:8b", "offer": M, "size": adv["chat"]["pick"]["size"]}
    assert modeladvice.older_model(M, adv) is None and modeladvice.older_model("", adv) is None


def test_suggested_keeps_the_old_shape_and_falls_back(monkeypatch):
    sug = modeladvice.suggested(modeladvice.advise(pc(16, system="mac", unified=True)))
    assert sug == [{"name": M, "use": "chat", "size": "about 3.7 GB"},
                   {"name": "nomic-embed-text", "use": "embed", "size": "about 0.3 GB"}]
    assert [m["use"] for m in modeladvice.suggested(modeladvice.advise(pc(1, disk=100)))] == ["embed"]
    monkeypatch.setattr(modeladvice, "computer", lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    from margin import llm
    assert modeladvice.suggested() == [dict(m) for m in llm.SUGGESTED_MODELS]


def test_the_app_reads_the_computer_cheaply_and_a_graphics_card_only_where_nvidia_smi_is(monkeypatch):
    monkeypatch.setattr(modeladvice.shutil, "which", lambda n: None)
    modeladvice._FACTS.clear()
    f = modeladvice.computer("/tmp")
    assert f["gpu"] is None and f["memory"] and f["system"] in ("mac", "windows", "linux")
    calls = []
    monkeypatch.setattr(modeladvice.shutil, "which", lambda n: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(modeladvice.subprocess, "run", lambda *a, **k: calls.append(a) or type("R", (), {"stdout": "8192\n12288\n"})())
    assert modeladvice._gpu_memory("windows") == 12288 * (1 << 20) and len(calls) == 1
    assert modeladvice._gpu_memory("mac") is None                                   # never probed on a Mac


# ---------------------------------------------------------------------------------------------- starting Ollama itself
def test_windows_install_starts_ollama_itself_when_the_installer_did_not(site_free, monkeypatch, tmp_path):
    started, state = [], {"up": False}
    monkeypatch.setattr(ollama_setup, "check_windows", lambda f: "")
    monkeypatch.setattr(ollama_setup, "_install_windows", lambda f: tmp_path / "ollama app.exe")
    monkeypatch.setattr(ollama_setup, "start", lambda name=None: started.append(name) or state.update(up=True) or {"started": True})
    monkeypatch.setattr(ollama_setup.time, "sleep", lambda s: None)
    clock = iter(range(0, 10_000, 8))
    monkeypatch.setattr(ollama_setup.time, "time", lambda: next(clock))
    r = ollama_setup.install(sys_name="windows", is_running=lambda: state["up"])
    assert started == ["windows"] and r["running"] is True and r["started_by_margin"] is True


def test_windows_install_leaves_it_alone_when_the_installer_started_it(site_free, monkeypatch, tmp_path):
    monkeypatch.setattr(ollama_setup, "check_windows", lambda f: "")
    monkeypatch.setattr(ollama_setup, "_install_windows", lambda f: tmp_path / "ollama app.exe")
    monkeypatch.setattr(ollama_setup, "start", lambda name=None: pytest.fail("a second copy was started"))
    r = ollama_setup.install(sys_name="windows", is_running=lambda: True)
    assert r == {"path": str(tmp_path / "ollama app.exe"), "running": True}


def test_start_once_does_not_start_twice_or_when_it_answers(monkeypatch, tmp_path):
    app = tmp_path / "Ollama.app"
    app.mkdir()
    monkeypatch.setattr(ollama_setup, "app_path", lambda s=None: app)
    started = []
    monkeypatch.setattr(ollama_setup, "start", lambda name=None: started.append(1) or {"started": True, "path": str(app), "serve": False})
    monkeypatch.setattr(ollama_setup, "answers", lambda url=None: bool(answering))
    ollama_setup._STARTED["at"] = 0.0
    answering = False
    assert ollama_setup.start_once()["started"] is True and len(started) == 1
    again = ollama_setup.start_once()                                  # the card is drawn again while it starts
    assert again == {"started": False, "running": False, "starting": True} and len(started) == 1
    answering = True
    assert ollama_setup.start_once() == {"started": False, "running": True}
    monkeypatch.setattr(ollama_setup, "app_path", lambda s=None: None)
    with pytest.raises(ValueError, match="not on this computer"):
        ollama_setup.start_once()


@pytest.fixture
def site_free(monkeypatch, tmp_path):
    """The download is not asked for: a stand-in file in the downloads folder is what `_download` hands back."""
    monkeypatch.setattr(ollama_setup, "_download", lambda url, dest, on_progress, should_stop: dest.write_bytes(b"MZ") or True)
    monkeypatch.setattr(ollama_setup, "app_path", lambda s=None: None)
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "margin"))
    yield


# ---------------------------------------------------------------------------------------------- the API and the page
def test_the_servers_call_gives_the_advice_and_the_suggested_models(api, monkeypatch):
    monkeypatch.setattr(modeladvice, "computer", lambda *a, **k: pc(8))
    srv, url = fake_servers.start("ollama")
    try:
        api("PUT", "/api/settings", {"ollama_url": url})
        st, r = api("GET", "/api/servers")
        assert st == 200
        assert r["advice"]["chat"]["pick"]["name"] == S and r["advice"]["tier"]["answers"] == "explorer"
        assert [m["name"] for m in r["suggested"]] == [S, "nomic-embed-text"]
        assert r["advice"]["computer"]["words"].startswith("This computer has 8 GB")
        assert "older_model" in r
    finally:
        srv.shutdown()


def test_the_start_call_starts_nothing_when_ollama_answers(api, monkeypatch, tmp_path):
    srv, url = fake_servers.start("ollama")
    try:
        api("PUT", "/api/settings", {"ollama_url": url})
        app = tmp_path / "Ollama.app"
        app.mkdir()
        monkeypatch.setattr(ollama_setup, "app_path", lambda s=None: app)
        monkeypatch.setattr(ollama_setup, "start", lambda name=None: pytest.fail("started although it answers"))
        st, r = api("POST", "/api/ollama/start", {})
        assert st == 200 and r == {"started": False, "running": True}
    finally:
        srv.shutdown()


def test_the_page_waits_for_start_ollama_and_offers_the_choices():
    js = (STATIC / "views" / "local-model.js").read_text(encoding="utf-8")
    # 0.19.15: installed but not answering: the card offers Start Ollama and starts nothing by itself (0.18.0rc2 did)
    assert "startByItself(area, btn0)" not in js and "Margin is starting it" not in js and "Start Ollama" in js
    # after an install that did not answer: started again, nothing for the person to open
    assert "installed, but it did not answer yet" not in js and "Open it from" not in js
    # the choices: recommended, smaller and quicker, larger and more careful, from the advice
    assert "info.advice" in js and "Smaller and quicker" in js and "Larger and more careful" in js
    assert "advice.what_is_a_model" in js and "advice.computer.words" in js and "advice.chat.reason" in js
    # I6: one Set up button in plain words; the names of the other models only under a Technical fold
    assert "Set up the local model" in js and "Technical: choose another model" in js
    assert "model-choices" in (STATIC / "views.css").read_text(encoding="utf-8")
