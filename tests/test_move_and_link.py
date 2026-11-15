"""The move zip is looked at before anything comes in (always a plain move, as the same person); a folder linked as a
project is cleaned as a project from a zip is. (ENLENS also asks who this computer is; Margin has one person.)"""
from __future__ import annotations

import json
import sqlite3
import threading
import zipfile
from pathlib import Path

import pytest

from margin import bundle, home
from margin.store import Workspace


def _move_zip(tmp: Path, monkeypatch, settings: dict | None = None) -> Path:
    """This computer's one project and `export_all`; the home is then pointed at a computer of its own."""
    monkeypatch.setenv("MARGIN_HOME", str(tmp / "old-computer"))
    home.create_project("Shared")
    if settings:
        home.update_settings(settings)
    out = tmp / "move.zip"
    bundle.export_all(out)
    return out


def _at(tmp: Path, monkeypatch, name: str) -> Path:
    h = tmp / f"computer-{name}"
    monkeypatch.setenv("MARGIN_HOME", str(h))
    return h


# ---- the move zip -------------------------------------------------------------------------------------------
def test_peek_says_what_comes_before_anything_comes(tmp_path, monkeypatch):
    out = _move_zip(tmp_path, monkeypatch, settings={"themes_k": 17, "ollama_url": "http://10.0.0.5:11434",
                                                     "openai_url": "http://localhost:1234/v1"})
    _at(tmp_path, monkeypatch, "new")
    m = bundle.peek_move(out)
    assert m["fresh"] is True and "person" not in m
    assert [p["name"] for p in m["projects"]] == ["Shared"]
    assert m["settings"]["themes_k"] == 17
    assert not {"project", "ollama_url"} & set(m["settings"])
    servers = {s["key"]: s for s in m["servers"]}
    assert servers["ollama_url"]["here"] is False and servers["openai_url"]["here"] is True
    assert home.list_projects() == [] and home.load_settings()["themes_k"] != 17
    with zipfile.ZipFile(out) as zf:
        sent = json.loads(zf.read(bundle.MOVE_MANIFEST))["settings"]
    assert "installation_id" not in sent and "installation_place" not in sent  # never in a move zip


def test_a_move_takes_the_projects_and_the_settings_only_when_asked(tmp_path, monkeypatch):
    out = _move_zip(tmp_path, monkeypatch, settings={"themes_k": 17})
    _at(tmp_path, monkeypatch, "new")
    r = bundle.import_all(out)
    assert [p["name"] for p in r["projects"]] == ["Shared"] and "person" not in r and "mode" not in r
    assert home.list_projects() == ["Shared"]
    assert r["settings"] is True and home.load_settings()["themes_k"] == 17  # a computer with no project takes them
    _at(tmp_path, monkeypatch, "used")
    home.create_project("Mine")
    assert bundle.peek_move(out)["fresh"] is False
    r = bundle.import_all(out)
    assert r["settings"] is False and home.load_settings()["themes_k"] != 17  # one in use keeps its own
    assert sorted(home.list_projects()) == ["Mine", "Shared"]


def test_addresses_not_on_this_computer_come_only_when_ticked(tmp_path, monkeypatch):
    out = _move_zip(tmp_path, monkeypatch, settings={"ollama_url": "http://10.0.0.5:11434", "backend": "ollama",
                                                     "ollama_model": "llama3", "openai_url": "http://127.0.0.1:9999/v1",
                                                     "themes_k": 9})
    _at(tmp_path, monkeypatch, "a")
    bundle.import_all(out, settings=True)
    s = home.load_settings()
    assert s["themes_k"] == 9 and s["openai_url"] == "http://127.0.0.1:9999/v1"  # on this computer: taken
    assert s["ollama_url"] == home.DEFAULTS["ollama_url"]  # another computer's: not without a tick
    assert s["backend"] == home.DEFAULTS["backend"] and s["ollama_model"] == ""  # left without its address
    _at(tmp_path, monkeypatch, "b")
    bundle.import_all(out, settings=True, servers=["ollama_url"])
    s = home.load_settings()
    assert s["ollama_url"] == "http://10.0.0.5:11434" and s["backend"] == "ollama"


def test_the_app_asks_before_a_move_zip_comes_in(tmp_path, monkeypatch):
    from margin.gui.server import make_server
    from test_app import Api

    out = _move_zip(tmp_path, monkeypatch)
    _at(tmp_path, monkeypatch, "new")
    srv, app = make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    call = Api(f"http://127.0.0.1:{srv.server_address[1]}", app.token)
    try:
        st, r = call("POST", "/api/projects/import", raw=out.read_bytes(), headers={"Content-Type": "application/zip"})
        assert st == 200 and r["move"]["fresh"] is True and r["token"] and "moved" not in r
        assert "person" not in r["move"]
        assert home.list_projects() == []  # nothing yet
        st, done = call("POST", "/api/move", {"token": r["token"]})
        assert st == 200 and done["moved"]["projects"][0]["name"] == "Shared"
        st, _again = call("POST", "/api/move", {"token": r["token"]})
        assert st == 410  # the upload went once it was brought in
    finally:
        srv.shutdown()
        srv.server_close()


# ---- linking a folder -----------------------------------------------------------------------------------------
def _trigger(root: Path) -> None:
    cx = sqlite3.connect(root / "enlens.sqlite")
    cx.execute("CREATE TRIGGER evil AFTER UPDATE ON documents BEGIN UPDATE documents SET ai_access='cloud'; END")
    cx.execute("CREATE VIEW sneaky AS SELECT * FROM documents")
    cx.commit()
    cx.close()


def test_linking_ones_own_folder_drops_triggers_and_cleans_its_config(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    ws = Workspace.create(tmp_path / "pilot")
    ws.close_all()
    _trigger(ws.root)
    cfg = json.loads(ws.config_path.read_text(encoding="utf-8"))
    cfg.update({"thresholds": "nonsense"})
    ws.config_path.write_text(json.dumps(cfg), encoding="utf-8")
    rep = bundle.check_linked(ws.root)
    assert rep["triggers"] == 1 and rep["views"] == 1 and rep["config"] == ["thresholds"]
    assert home.link_existing(str(ws.root), "pilot") == "pilot"
    cx = sqlite3.connect(ws.root / "enlens.sqlite")
    assert not cx.execute("SELECT name FROM sqlite_master WHERE type IN ('trigger', 'view') AND name IN "
                          "('evil', 'sneaky')").fetchall()
    cx.close()
    new = json.loads(ws.config_path.read_text(encoding="utf-8"))
    assert isinstance(new["thresholds"], dict)
    assert (ws.root / "config.json.before-linking").is_file()


def test_a_virtual_table_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    ws = Workspace.create(tmp_path / "odd")
    ws.close_all()
    cx = sqlite3.connect(ws.root / "enlens.sqlite")
    cx.execute("CREATE TABLE gen(a INT, b INT GENERATED ALWAYS AS (a + 1))")
    cx.commit()
    cx.close()
    with pytest.raises(ValueError, match="more than a project's rows"):
        home.link_existing(str(ws.root), "odd")
    assert "odd" not in home.list_projects()


def test_the_link_route_links_and_cleans(tmp_path, monkeypatch):
    from margin.gui.api_documents import DocumentsApi

    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    ws = Workspace.create(tmp_path / "pilot")
    ws.close_all()
    _trigger(ws.root)

    class Fake(DocumentsApi):
        def __init__(self, body):
            self.body = body
            self.app = type("A", (), {"project_summary": lambda _s, n: {"name": n}})()

        def _body(self):
            return self.body

    assert Fake({"path": str(ws.root), "name": "Pilot"}).post_link({})["project"]["name"] == "Pilot"
    cx = sqlite3.connect(ws.root / "enlens.sqlite")
    assert not cx.execute("SELECT name FROM sqlite_master WHERE name IN ('evil', 'sneaky')").fetchall()
    cx.close()
