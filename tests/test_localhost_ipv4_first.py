"""0.19.10: on Windows the card never saw an Ollama that ran.

Windows looks "localhost" up as ::1 first, Ollama listens on 127.0.0.1 only, and Windows reports the refused ::1
connection only after about two seconds. The quick look for running servers (0.6 s, joined after 3.1 s) gave up
before it reached 127.0.0.1, so after *Install Ollama* the card stayed on "Starting Ollama…" and, after a reload, on
"Ollama is starting…" until its minute ran out, while Ollama answered. Requests to model servers on localhost now go
to 127.0.0.1 first, and to localhost as given only when nothing listens on 127.0.0.1.
"""
from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.error import URLError

import pytest

from margin import embed, llm
from margin.gui.server import QuickServer

STATIC = Path(llm.__file__).parent / "gui" / "static"


class _Fake:
    """urllib.request.urlopen in place: records each request and answers as `answer(url)` says."""

    def __init__(self, answer):
        self.answer, self.seen = answer, []

    def __call__(self, req, *args, **kwargs):
        self.seen.append((req.full_url, req.get_method(), req.data, dict(req.header_items()), kwargs.get("timeout")))
        return self.answer(req.full_url)


def _refused(url):
    if "127.0.0.1" in url:
        raise URLError(ConnectionRefusedError(10061, "refused"))
    return "via localhost"


def test_localhost_goes_to_127_0_0_1_with_everything_kept(monkeypatch):
    fake = _Fake(lambda url: "answer")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    req = urllib.request.Request("http://localhost:11434/api/chat?x=1", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    assert llm.local_urlopen(req, timeout=7) == "answer"
    [(url, method, data, headers, timeout)] = fake.seen
    assert url == "http://127.0.0.1:11434/api/chat?x=1"
    assert (method, data, timeout) == ("POST", b"{}", 7)
    assert headers.get("Content-type") == "application/json"


def test_a_server_on_ipv6_only_is_still_reached(monkeypatch):
    fake = _Fake(_refused)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert llm.local_urlopen("http://localhost:1234/v1/models", timeout=1) == "via localhost"
    assert [s[0] for s in fake.seen] == ["http://127.0.0.1:1234/v1/models", "http://localhost:1234/v1/models"]


def test_a_timeout_is_not_tried_twice(monkeypatch):
    def slow(url):
        raise URLError(TimeoutError("timed out"))

    fake = _Fake(slow)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(URLError):
        llm.local_urlopen("http://localhost:11434/api/version", timeout=0.6)
    assert len(fake.seen) == 1


@pytest.mark.parametrize("url", ["http://127.0.0.1:11434/api/tags", "http://[::1]:11434/api/tags",
                                 "http://gpu-box.lan:11434/api/tags", "https://example.org/v1/models"])
def test_other_addresses_are_opened_as_they_are(monkeypatch, url):
    fake = _Fake(lambda u: "ok")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    llm.local_urlopen(url)
    assert fake.seen[0][0] == url


def test_the_model_servers_use_it_unless_given_another_opener():
    assert llm.OllamaBackend().opener is llm.local_urlopen
    assert llm.LocalBackend().opener is llm.local_urlopen
    assert embed.OllamaEmbedder("nomic-embed-text").opener is llm.local_urlopen
    assert embed.OpenAIEmbedder("m", "http://localhost:1234").opener is llm.local_urlopen
    mine = object()
    assert llm.OllamaBackend(opener=mine).opener is mine


@pytest.fixture
def ollama_on_ipv4():
    """A stand-in Ollama listening on 127.0.0.1 only, as the real one does."""

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = {"/api/version": {"version": "0.40.16"}, "/api/tags": {"models": [{"name": "qwen3:4b"}]},
                    "/api/ps": {"models": []}}.get(self.path)
            self.send_response(200 if body is not None else 404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body or {}).encode())

        def log_message(self, *a):
            pass

    srv = QuickServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_the_quick_look_finds_ollama_at_localhost(ollama_on_ipv4, monkeypatch):
    """The look the card makes every few seconds: what failed on Windows."""
    port = ollama_on_ipv4
    asked = []
    real = urllib.request.urlopen

    def recording(req, *a, **kw):
        asked.append(req.full_url if hasattr(req, "full_url") else req)
        return real(req, *a, **kw)

    monkeypatch.setattr(urllib.request, "urlopen", recording)
    monkeypatch.setattr(llm, "OPENAI_PORTS", ())
    llm._DETECTED.clear()
    assert llm.ollama_version(f"http://localhost:{port}", 0.6) == "0.40.16"
    found = llm.detect_local(ollama_url=f"http://localhost:{port}", cache_seconds=0)
    assert [(x["kind"], x["models"]) for x in found] == [("ollama", ["qwen3:4b"])]
    assert asked and all("127.0.0.1" in u for u in asked)   # never ::1 first
    llm._DETECTED.clear()


def test_the_card_leaves_the_starting_bar_when_ollama_answers():
    js = (STATIC / "views" / "local-model.js").read_text(encoding="utf-8")
    assert js.count("if (r.running) { answersAlready(area, btn); return; }") == 2   # Start button and by itself
    assert "Ollama is running. A moment…" in js
