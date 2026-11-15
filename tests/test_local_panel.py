"""0.19.4: the local model gets its own panel, and labelling no longer stops when it cannot start.

Found in a user test: on the Codes page with Claude Code as the AI, two documents fell back to the project's default
"Only a local AI". "Let the AI label 25 passages" read two passages, then the whole job stopped with "qwen3.5:9b was
not started: it needs about 8.1 GB of memory…", although Claude could have read every other passage, and the page had
said only "Claude, on your plan, reads the passages it labels". Now the local model's passages wait (with Start it
anyway), Claude's are read, and the page knows the local model, its memory and what this computer has free.
"""
from __future__ import annotations

import pytest
from helpers_mixed_corpus import Cloud, mixed_project, use_local_model
from test_local_memory import GB, Watched, _Opener

from margin import access, home, llm, profile
from margin.llm import OllamaBackend


@pytest.fixture
def mixed(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home.create_project("Mixed")
    ids = mixed_project(ws, tmp_path / "corpus")
    profile.ensure_pass1(ws, "sdg")
    return ws, ids


def _labelled(ws, doc_id: str) -> int:
    return int(ws.scalar("SELECT COUNT(*) FROM tasks t JOIN passages p ON t.task_id = 'label:sdg:' || p.passage_id "
                         "WHERE t.kind='label' AND t.status='done' AND p.doc_id=?", (doc_id,)) or 0)


def test_no_room_for_the_local_model_claude_still_labels_the_rest(mixed, monkeypatch):
    ws, ids = mixed
    local = Watched(need=8 * GB, free=2 * GB)
    use_local_model(monkeypatch, local)
    cloud = Cloud()
    res = profile.run_labels(ws, "sdg", cloud, "claude-haiku", all_passages=True)
    # the job ends normally: Claude read its passages, the local model's wait, and the result says why
    assert cloud.sent and _labelled(ws, ids["cloud"]) > 0
    assert local.sent == [] and _labelled(ws, ids["local"]) == 0
    assert res["local_waiting"] > 0 and res["local_read"] == 0 and res["local_model"] == "local-model"
    assert res["memory_short"].startswith("local-model was not started: it needs about 8.0 GB")
    assert res["local_problem"] is None
    # the numbers, for the panel's one sentence
    assert res["memory"] == {"need": 8 * GB, "free": 2 * GB, "short": True}
    # "Start it anyway": only the waiting passages are left, and the local model reads them
    again = profile.run_labels(ws, "sdg", cloud, "claude-haiku", all_passages=True, force=True)
    assert local.sent and _labelled(ws, ids["local"]) > 0
    assert again["local_waiting"] == 0 and again["memory_short"] is None and again["local_read"] > 0


def test_the_local_model_reads_first(mixed, monkeypatch):
    """Its passages come first, so it reads here while Claude Code answers its own from the queue."""
    ws, ids = mixed
    order: list[str] = []
    local = Watched(free=64 * GB)
    cloud = Cloud()
    for who, be in (("local", local), ("cloud", cloud)):
        orig = be.complete
        be.complete = lambda *a, _w=who, _o=orig, **k: (order.append(_w), _o(*a, **k))[1]
    use_local_model(monkeypatch, local)
    res = profile.run_labels(ws, "sdg", cloud, "claude-haiku", all_passages=True)
    assert "local" in order and "cloud" in order
    assert order.index("cloud") > max(i for i, w in enumerate(order) if w == "local")
    assert res["local_waiting"] == 0 and res["local_read"] > 0


def test_a_local_model_that_cannot_be_reached_leaves_its_passages_waiting(mixed, monkeypatch):
    ws, ids = mixed

    class Down(Watched):
        def complete(self, *a, **k):
            raise llm.BackendError("The model server at http://localhost:11434 is not answering.")

    use_local_model(monkeypatch, Down(free=64 * GB))
    cloud = Cloud()
    res = profile.run_labels(ws, "sdg", cloud, "claude-haiku", all_passages=True)
    assert _labelled(ws, ids["cloud"]) > 0 and res["local_waiting"] > 0
    assert res["memory_short"] is None and "not answering" in res["local_problem"]


def test_memory_status_says_need_and_free(monkeypatch):
    opener = _Opener({"qwen3.5:9b": int(7.6e9)})
    be = OllamaBackend("http://localhost:11434", num_ctx=16384, opener=opener, think=False)
    monkeypatch.setattr(llm, "free_memory", lambda: int(6.2 * GB))
    st = be.memory_status("qwen3.5:9b")
    assert st["short"] is True and st["loaded"] is False
    assert st["need"] == int(7.6e9) + 16384 * llm.KV_BYTES_PER_TOKEN and st["free"] == int(6.2 * GB)
    monkeypatch.setattr(llm, "free_memory", lambda: 16 * GB)
    assert be.memory_status("qwen3.5:9b")["short"] is False
    opener.loaded = ["qwen3.5:9b"]
    assert be.memory_status("qwen3.5:9b") == {"loaded": True, "short": False}
    opener.loaded = []
    monkeypatch.setattr(llm, "free_memory", lambda: None)
    assert be.memory_status("qwen3.5:9b") is None   # the computer does not say: nothing is claimed
    assert "/api/chat" not in opener.paths           # nothing was loaded to find out


def test_local_status_for_the_panel(monkeypatch):
    s = {**home.DEFAULTS, "backend": "claude_code"}
    use_local_model(monkeypatch, None)
    assert access.local_status(s)["model"] is None and "Settings" in access.local_status(s)["problem"]
    local = Watched(need=8 * GB, free=2 * GB)
    local.memory_status = lambda m: {"loaded": False, "need": 8 * GB, "free": 2 * GB, "short": True}
    use_local_model(monkeypatch, local)
    st = access.local_status(s)
    assert st["model"] == "local-model" and st["memory"]["short"] is True

    def missing(_s):
        raise llm.BackendError("The local model for restricted documents, qwen3.5:9b, is not installed.")

    monkeypatch.setattr(home, "make_restricted_backend", missing)
    st = access.local_status(s)
    assert st["model"] == "local-model" and "not installed" in st["problem"]


def test_the_page_hears_when_the_local_model_was_refused(mixed, monkeypatch):
    """Its panel must not go on saying "is loading": the job's progress says it was not started, with the numbers."""
    ws, ids = mixed
    local = Watched(need=8 * GB, free=2 * GB)
    use_local_model(monkeypatch, local)
    cloud = Cloud()
    heard: list[dict] = []
    cloud.progress = heard.append   # as the app's job wires its backend (start_queued_job)
    profile.run_labels(ws, "sdg", cloud, "claude-haiku", all_passages=True)
    last = [x for x in heard if x.get("who") == "local"][-1]
    assert last["phase"] == "refused" and last["memory"]["short"] is True and "was not started" in last["error"]
    heard.clear()
    profile.run_labels(ws, "sdg", cloud, "claude-haiku", all_passages=True, force=True)
    assert [x for x in heard if x.get("who") == "local"][-1]["phase"] == "done"


def test_the_local_panel_is_built_like_the_claude_code_panel():
    from pathlib import Path

    static = Path(profile.__file__).parent / "gui" / "static"
    lib = (static / "lib.js").read_text(encoding="utf-8")
    body = lib[lib.index("function localPanelBody("):lib.index("// 0.13.10: how fast Claude Code works")]
    # the house in every state, Start it anyway behind a confirmation, the memory sentence, the house line
    assert 'icon("house"' in body and "On this computer" in body and "confirmDialog(" in body
    assert "Start it anyway" in body and "of memory;" in body and 'aiWhere(' in body and '"local")' in body
    assert 'local: "notice notice-local"' in lib
    css = (static / "components.css").read_text(encoding="utf-8")
    assert ".notice-local {" in css
    for page in ("profile.js", "progress.js", "result.js"):
        assert "localPanel(" in (static / "views" / page).read_text(encoding="utf-8"), page


# -- 0.19.4, after the release: any job the local model was refused in runs again from its panel ----------------------
def test_a_job_refused_for_memory_runs_again_and_can_start_it_anyway():
    """Found on the Themes page: naming the themes stopped with the memory message in a toast, and nothing on the
    page could start the model. Now the job keeps the numbers, and runs again (checked again, or Start it anyway)."""
    import time

    from margin.gui.api_common import Jobs

    seen: list[bool] = []

    def name_themes(job):
        readers = access.Readers(None, "")
        seen.append(readers.check_memory)
        if readers.check_memory:
            raise llm.MemoryShort("qwen3.5:9b", int(8.1 * GB), int(6.9 * GB))
        return {"named": 3}

    def wait(job):
        for _ in range(200):
            if job.state in ("done", "error", "cancelled"):
                return job
            time.sleep(0.01)
        raise AssertionError("the job did not end")

    jobs = Jobs()
    first = wait(jobs.start("theme-names", "The AI names the themes", "P", name_themes, uses_model=True))
    v = first.view()
    assert v["error_kind"] == "memory" and v["can_run_again"] is True
    assert v["memory"] == {"need": int(8.1 * GB), "free": int(6.9 * GB), "short": True, "model": "qwen3.5:9b"}
    # run again as it was: the memory is checked again (and still too little)
    again = wait(jobs.again(first))
    assert again.error_kind == "memory" and again.title == first.title and again.kind == first.kind
    # Start it anyway: this run only starts the model whatever memory is free
    anyway = wait(jobs.again(again, force_local=True))
    assert anyway.state == "done" and anyway.result == {"named": 3}
    assert seen == [True, True, False]
    assert access.FORCE_LOCAL.get() is False   # nothing leaks out of the job's run
    # a job that did not stop for memory does not run again from here
    other = wait(jobs.start("x", "Other", "P", lambda job: {"ok": 1}, uses_model=False))
    with pytest.raises(ValueError):
        jobs.again(other)


def test_start_it_anyway_turns_the_guard_off_for_the_restricted_model(monkeypatch):
    s = {**home.DEFAULTS, "num_ctx": 8192, "think": "off", "backend": "claude_code",
         "restricted_server": "ollama", "restricted_model": "qwen3.5:9b"}
    monkeypatch.setattr(home, "_make_backend", lambda st, key, kinds: (
        home._ollama(st, st["ollama_url"], st["ollama_model"], False), st["ollama_model"]))
    assert home.make_restricted_backend(s)[0].memory_guard is True
    token = access.FORCE_LOCAL.set(True)
    try:
        assert home.make_restricted_backend(s)[0].memory_guard is False
        assert access.Readers(None, "").check_memory is False
        assert access.Readers(None, "", check_memory=True).check_memory is True   # an explicit choice stands
    finally:
        access.FORCE_LOCAL.reset(token)


def test_pages_show_the_local_panel_not_a_toast_for_a_refused_model():
    from pathlib import Path

    static = Path(profile.__file__).parent / "gui" / "static"
    lib = (static / "lib.js").read_text(encoding="utf-8")
    assert "export function jobFailed(" in lib and "export function memoryRefused(" in lib and "/again`" in lib
    themes = (static / "views" / "themes.js").read_text(encoding="utf-8")
    assert "jobFailed(job, (j) => followNames(j.id), nameJob)" in themes
    assert 'error_kind === "memory" && job.can_run_again' in (static / "views" / "progress.js").read_text(encoding="utf-8")
    for page in ("concepts.js", "hypotheses.js", "history.js", "search.js", "result.js", "themes.js"):
        js = (static / "views" / page).read_text(encoding="utf-8")
        assert "showError({ message: job.error, kind: job.error_kind })" not in js.replace(
            'if (job.error_kind !== "memory") { showError({ message: job.error, kind: job.error_kind }); return; }', ""), page
