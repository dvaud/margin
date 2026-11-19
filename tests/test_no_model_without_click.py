"""0.19.15: no AI model starts, or is even loaded, until a person presses its Start.

- Margin no longer starts Ollama when it opens, nor when the Settings card that looks for a model server is drawn;
  Ollama starts at the first request of a model a person started (`ollama_setup.wake`).
- The job's Stop lets go of the local models the job asked, at once; Stop on the local side lets go of the local model
  once the request in hand is put down. Nothing is loaded to be unloaded: only models Ollama holds are let go of.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from margin import llm, ollama_setup
from margin.access import Readers, _Gated
from margin.gui import launcher
from margin.gui.api_common import Jobs
from margin.localgate import GO, LocalGate

SRC = Path(__file__).resolve().parents[1] / "src" / "margin"
REAL_LET_GO = llm.let_go   # conftest puts a stand-in in its place for every test


# -- Ollama starts on a click, never when Margin opens ---------------------------------------------------------------
def test_the_icon_no_longer_starts_ollama():
    launch = (SRC / "gui" / "launch.py").read_text(encoding="utf-8")
    assert "start_ollama" not in launch and "ollama_setup" not in launch.split("0.19.15", 1)[0]
    assert not hasattr(launcher, "start_ollama")
    js = (SRC / "gui" / "static" / "views" / "local-model.js").read_text(encoding="utf-8")
    assert "startByItself(area, btn0)" not in js   # the card no longer starts it when drawn


def test_wake_starts_ollama_only_on_this_computer_and_only_when_it_does_not_answer(monkeypatch):
    started, up = [], {"v": False}
    monkeypatch.setattr(ollama_setup, "app_path", lambda s=None: Path("/Applications/Ollama.app"))
    monkeypatch.setattr(ollama_setup, "answers", lambda url=None: up["v"])
    monkeypatch.setattr(ollama_setup, "start", lambda name=None: started.append(1) or up.update(v=True)
                        or {"started": True, "serve": False})
    monkeypatch.setattr(ollama_setup.time, "sleep", lambda s: None)
    assert ollama_setup.wake("http://10.0.0.5:11434") is False and started == []   # another computer's
    assert ollama_setup.wake("http://localhost:11434") is True and started == [1]
    assert ollama_setup.wake("http://localhost:11434") is True and started == [1]  # answers now: nothing more


def test_wake_starts_nothing_for_another_port(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr(ollama_setup, "answers", lambda url=None: False)
    monkeypatch.setattr(ollama_setup, "start_once", lambda url=None: pytest.fail("started for another server"))
    assert ollama_setup.wake("http://127.0.0.1:9") is False          # the dev server's "no Ollama here"
    assert ollama_setup.wake("http://localhost:1234/v1") is False    # LM Studio's
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:11500")
    monkeypatch.setattr(ollama_setup, "start_once", lambda url=None: {"started": False, "running": True})
    assert ollama_setup.wake("http://127.0.0.1:11500") is True       # where OLLAMA_HOST says it listens


def test_wake_is_false_when_ollama_is_not_on_this_computer(monkeypatch):
    monkeypatch.setattr(ollama_setup, "app_path", lambda s=None: None)
    monkeypatch.setattr(ollama_setup, "answers", lambda url=None: False)
    assert ollama_setup.wake() is False


def test_a_backend_wakes_ollama_once_at_its_first_request_and_never_with_a_stand_in(monkeypatch):
    woken = []
    monkeypatch.setattr(ollama_setup, "wake", lambda url=None, wait=30.0, should_stop=None: woken.append(url) or True)
    be = llm.OllamaBackend(base_url="http://localhost:11434")
    be.wake()
    be.wake()
    assert woken == ["http://localhost:11434"]
    llm.OllamaBackend(base_url="http://localhost:11434", opener=lambda *a, **k: None).wake()
    assert woken == ["http://localhost:11434"]


def test_a_start_that_failed_is_tried_again_at_the_next_request(monkeypatch):
    answers = iter([False, True])
    woken = []
    monkeypatch.setattr(ollama_setup, "wake", lambda url=None, wait=30.0, should_stop=None: woken.append(1)
                        or next(answers))
    be = llm.OllamaBackend(base_url="http://localhost:11434")
    be.wake()
    be.wake()
    be.wake()
    assert len(woken) == 2   # the first did not answer; the second did; the third asks nothing


def test_a_page_that_only_looks_never_wakes_ollama(monkeypatch, tmp_path):
    from margin import home
    from margin.gui.server import App

    woken = []
    monkeypatch.setattr(ollama_setup, "wake", lambda url=None, wait=30.0, should_stop=None: woken.append(url) or False)
    app = App()
    home.save_settings({**home.load_settings(), "backend": "auto", "ollama_url": "http://localhost:11434"})
    try:
        app.backend(("label",))          # the Profile page's plan: it only looks
    except Exception:  # noqa: BLE001 - no model server here: only whether it was woken matters
        pass
    assert woken == []
    try:
        app.backend(wake=True)           # an AI button that starts a job
    except Exception:  # noqa: BLE001
        pass
    assert woken == ["http://localhost:11434"]
    src = (SRC / "gui" / "app_queue.py").read_text(encoding="utf-8")
    assert 'self.backend(("label",))' in src   # label_plan (GET .../profile/plan) still asks without waking


# -- letting go of a model's memory -----------------------------------------------------------------------------------
class _FakeOllama:
    """Ollama's /api/ps and /api/generate (keep_alive 0) on the real connection's place."""

    def __init__(self, held):
        self.held, self.unloaded = list(held), []

    def __call__(self, req, timeout=None):
        import io

        url = getattr(req, "full_url", req)
        if url.endswith("/api/ps"):
            body = {"models": [{"name": m, "expires_at": "2099"} for m in self.held]}
        elif url.endswith("/api/generate"):
            sent = json.loads(req.data.decode())
            assert sent.get("keep_alive") == 0 and not sent.get("prompt")
            self.unloaded.append(sent["model"])
            body = {"done_reason": "unload"}
        else:
            raise AssertionError(f"not asked here: {url}")

        class R(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return R(json.dumps(body).encode())


def test_let_go_unloads_only_the_models_ollama_holds(monkeypatch):
    fake = _FakeOllama(["qwen3.5:4b"])
    monkeypatch.setattr(llm, "local_urlopen", fake)
    got = REAL_LET_GO({("http://localhost:11434", "qwen3.5:4b"), ("http://localhost:11434", "gemma4:12b")})
    assert got == ["qwen3.5:4b"] and fake.unloaded == ["qwen3.5:4b"]   # gemma4 is not loaded to be let go of


def _wait(cond, seconds=5.0):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_the_jobs_stop_lets_go_of_the_local_models_it_asked(monkeypatch):
    freed = []
    monkeypatch.setattr(llm, "let_go", lambda models: freed.append(set(models)) or [])
    jobs, began = Jobs(), threading.Event()

    def fn(job):
        llm.note_used("http://localhost:11434", "ifm/k2-horizon:0.9b")
        began.set()
        while not job.cancel.is_set():
            time.sleep(0.02)

    job = jobs.start("theme-names", "The AI names the themes", None, fn, uses_model=True)
    assert began.wait(5)
    job.cancel.set()
    assert _wait(lambda: freed)
    assert freed == [{("http://localhost:11434", "ifm/k2-horizon:0.9b")}]


def test_a_stop_keeps_a_model_another_job_still_uses(monkeypatch):
    freed = []
    monkeypatch.setattr(llm, "let_go", lambda models: freed.append(set(models)) or [])
    jobs, began = Jobs(), threading.Event()
    k2, qwen = ("http://localhost:11434", "ifm/k2-horizon:0.9b"), ("http://localhost:11434", "qwen3.5:4b")

    def other(job):
        llm.note_used(*k2)
        while not job.cancel.is_set():
            time.sleep(0.02)

    def mine(job):
        llm.note_used(*k2)
        llm.note_used(*qwen)
        began.set()
        while not job.cancel.is_set():
            time.sleep(0.02)

    a = jobs.start("labels", "Other", None, other, uses_model=False)
    assert _wait(lambda: a.used_models)
    b = jobs.start("theme-names", "Mine", None, mine, uses_model=False)
    assert began.wait(5)
    b.cancel.set()
    assert _wait(lambda: freed)
    assert freed == [{qwen}]          # k2 stays: the other job still reads with it
    a.cancel.set()
    assert _wait(lambda: len(freed) == 2) and freed[1] == {k2}


def test_a_job_that_ends_by_itself_keeps_its_model(monkeypatch):
    # I6: except an MLX model, whose prompt cache grows: only those are let go of (let_go's runner="mlx")
    freed = []
    monkeypatch.setattr(llm, "let_go", lambda models, runner=None: freed.append((set(models), runner)) or [])
    jobs = Jobs()
    job = jobs.start("theme-names", "The AI names the themes", None,
                     lambda job: llm.note_used("http://localhost:11434", "qwen3.5:4b"), uses_model=True)
    assert _wait(lambda: job.state == "done")
    time.sleep(0.1)
    assert freed == [({("http://localhost:11434", "qwen3.5:4b")}, "mlx")]
    assert job.used_models == {("http://localhost:11434", "qwen3.5:4b")}


def test_outside_a_job_nothing_is_noted():
    llm.note_used("http://localhost:11434", "qwen3.5:4b")   # the command line, the connector: no set, no error
    assert llm.USED.get() is None


class _Local:
    """A local model on Ollama's real connection that answers when told to."""

    base_url = "http://localhost:11434"

    def __init__(self):
        self.opener = llm.local_urlopen
        self.go_on = threading.Event()
        self.asked = threading.Event()

    def unload(self, model):
        return True

    def complete(self, kind, system, user, model, payload):
        self.asked.set()
        self.go_on.wait(5)
        return "{}"


def test_stop_on_the_local_side_lets_go_of_the_model_once_the_request_in_hand_is_put_down(monkeypatch):
    freed = []
    monkeypatch.setattr(llm, "let_go", lambda models: freed.append(set(models)) or [])
    gate = LocalGate(GO)
    readers = Readers(None, "", settings={}, gate=gate)
    be = _Local()
    gated = _Gated(be, readers)
    t = threading.Thread(target=gated.complete, args=("theme", "s", "u", "ifm/k2-horizon:0.9b", {}), daemon=True)
    t.start()
    assert be.asked.wait(5)
    gate.close()                       # the local side's Stop while a theme is in hand
    time.sleep(0.1)
    assert freed == []                 # it finishes the theme in hand first
    be.go_on.set()
    t.join(5)
    assert _wait(lambda: freed)
    assert freed == [{("http://localhost:11434", "ifm/k2-horizon:0.9b")}]


def test_stop_on_the_local_side_with_nothing_in_hand_lets_go_at_once(monkeypatch):
    freed = []
    monkeypatch.setattr(llm, "let_go", lambda models: freed.append(set(models)) or [])
    gate = LocalGate(GO)
    gate.hand("http://localhost:11434", "qwen3.5:4b")
    gate.put_down()
    assert freed == []                 # open: it may go on reading
    gate.close()
    assert _wait(lambda: freed)
    assert freed == [{("http://localhost:11434", "qwen3.5:4b")}]


def test_a_stand_in_backend_is_never_let_go_of(monkeypatch):
    freed = []
    monkeypatch.setattr(llm, "let_go", lambda models: freed.append(set(models)) or [])
    gate = LocalGate(GO)
    readers = Readers(None, "", settings={}, gate=gate)
    be = _Local()
    be.opener = lambda *a, **k: None   # a test's own connection: never asked to let go
    be.go_on.set()
    _Gated(be, readers).complete("theme", "s", "u", "m", {})
    gate.close()
    time.sleep(0.1)
    assert freed == []
