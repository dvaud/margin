"""Margin without ENLENS's SDG baggage: no codebook until one is chosen, the SDG codebooks as built-in examples
listed last, and the SDG pack left out of what a Margin user sees (Settings, the command line, the plugin, the page).
The pack's code stays, so ENLENS's work still merges in and a project copied from ENLENS still opens."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_app import Api, api, home  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "margin"
STATIC = SRC / "gui" / "static"
CSV = "code,description,group,group_name\nR1,Working from home reduces commuting,C,Commuting\nR2,Offices close,C,Commuting\n"


def test_no_codebook_by_default_and_an_old_sdg_default_is_dropped(home):
    assert home.load_settings()["profile_framework"] == ""
    # a settings file written before 0.8 had "sdg" as everyone's default: read as no codebook, once
    (home.home() / "settings.json").write_text(json.dumps({"_version": 2, "profile_framework": "sdg"}))
    assert home.load_settings()["profile_framework"] == ""
    # chosen again after 0.8, it stays
    home.update_settings({"profile_framework": "sdg"})
    assert home.load_settings()["profile_framework"] == "sdg"
    assert home.update_settings({"profile_framework": ""})["profile_framework"] == ""
    with pytest.raises(ValueError):
        home.update_settings({"profile_framework": "Not a name!"})


def test_own_codebooks_come_before_the_built_in_ones(home):
    from margin import frameworks

    ws = home.create_project("P")
    frameworks.save(ws, "remote", CSV)
    assert list(frameworks.available(ws)) == ["remote", "practice", "change_framing", "sdg", "sdg_goals"]
    assert frameworks.get("sdg", ws).codes  # still there, by name


def test_the_app_without_a_codebook(api, tmp_path):
    assert api("PUT", "/api/settings", {"embed_backend": "off"})[0] == 200
    assert api("POST", "/api/projects", {"name": "P"})[0] == 200
    f = tmp_path / "notes.txt"
    f.write_text("Working from home reduces commuting and offices close in the city centre.\n\n" * 6)
    assert api("POST", f"/api/projects/P/uploads?batch=b1&name={f.name}", raw=f.read_bytes())[0] == 200
    job = api.wait(api("POST", "/api/projects/P/ingest", {"batch": "b1"})[1]["job"]["id"])
    # adding documents skips the codes step: no codebook, no codes (and no error)
    assert job["state"] == "done" and "codes" not in job["result"] and "codes_error" not in job["result"]
    ov = api("GET", "/api/projects/P/overview")[1]
    assert ov["profile"]["framework"] == "" and ov["profile"]["labels"] == 0
    # what needs a codebook says to choose one
    for method, path, body in [("GET", "/api/projects/P/profile", None),
                               ("POST", "/api/projects/P/profile/keywords", {}),
                               ("GET", "/api/projects/P/profile/plan", None),
                               ("POST", "/api/projects/P/profile/label", {})]:
        st, r = api(method, path, body)
        assert st == 409 and "Choose a codebook first" in r["error"], (path, st, r)
    assert api("GET", "/api/projects/P/suggest?text=Working+from+home+cuts+commuting")[1] == {"codes": []}
    # a codebook named, or chosen, works as before
    assert api("POST", "/api/projects/P/frameworks", {"name": "remote", "csv": CSV})[0] == 200
    names = [x["name"] for x in api("GET", "/api/projects/P/frameworks")[1]["frameworks"]]
    assert names == ["remote", "practice", "change_framing", "sdg", "sdg_goals"]
    assert api("GET", "/api/projects/P/profile?framework=remote")[0] == 200
    assert api("PUT", "/api/settings", {"profile_framework": "remote"})[0] == 200
    assert api("GET", "/api/projects/P/profile")[1]["framework"] == "remote"
    assert api("GET", "/api/projects/P/overview")[1]["profile"]["framework"] == "remote"


def test_settings_model_table_has_no_sdg_pack_rows(home):
    from margin import routing

    rows = routing.from_settings(home.load_settings()).table()
    assert {"label", "check", "second"} <= {r["row"] for r in rows}
    assert not {"extract", "split", "verify"} & {r["row"] for r in rows}
    assert next(r for r in rows if r["row"] == "second")["title"] == "Second opinion"
    assert not any("SDG" in r["title"] for r in rows)


def test_the_command_line_lists_no_sdg_pack_commands_and_needs_a_codebook(home, tmp_path):
    from margin import cli

    run = lambda *a: subprocess.run([sys.executable, "-m", "margin.cli", *a], capture_output=True, text=True,  # noqa: E731
                                    env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    out = run("--help").stdout
    listed = re.search(r"\{([^}]+)\}", out).group(1).split(",")
    assert not set(listed) & cli.SDG_PACK_COMMANDS and {"check", "profile", "search", "themes"} <= set(listed)
    assert "SDG" not in out and "value chain" not in out
    assert run("load-vca", "--help").returncode == 0  # still runs when typed
    ws = tmp_path / "ws"
    assert run("--ws", str(ws), "init").returncode == 0
    r = run("--ws", str(ws), "profile", "--keywords-only")
    assert r.returncode == 1 and "choose a codebook" in r.stderr


def test_the_connector_uses_the_chosen_codebook(home):
    from margin import mcp_server

    with pytest.raises(ValueError, match="No codebook is chosen"):
        mcp_server._codebook(None)
    assert mcp_server._codebook("sdg_goals") == "sdg_goals"
    home.update_settings({"profile_framework": "sdg"})
    assert mcp_server._codebook(None) == "sdg"
    assert "169 SDG targets" not in (SRC / "mcp_server.py").read_text()


def test_the_plugin_has_no_sdg_pack():
    from margin import claude_setup

    assert "margin-extractor" not in claude_setup.HELPERS
    assert not (SRC / "claude_plugin" / "agents" / "margin-extractor.md").exists()
    for p in (SRC / "claude_plugin").rglob("*"):
        if p.is_file() and p.suffix in (".md", ".json"):
            assert not re.search(r"SDG|VCA|extractor", p.read_text()), p


def test_the_page_offers_no_sdg_default_nor_the_pack():
    js = {p.name: p.read_text(encoding="utf-8") for p in (STATIC / "views").glob("*.js")}
    js["features.js"] = (STATIC / "features.js").read_text(encoding="utf-8")
    for name, text in js.items():
        assert '|| "sdg"' not in text and '?? "sdg"' not in text, name
    assert "testSection(s, watchers)" not in js["settings.js"].split("function testSection")[0]
    assert "flexiconc" not in js["projects.js"].lower()
    assert "sdg:6.4" not in js["search.js"] and "SDG" not in js["features.js"]
    assert "export function codebookChooser" in js["profile.js"]
    for name in ("sources.js", "themes.js"):
        assert "codebookChooser(" in js[name], name


def test_the_manual_and_readme_have_no_sdg_pack():
    from helpers import manual_text

    manual = manual_text()
    assert not (ROOT / "docs" / "manual" / "sdg-pack.md").exists()
    assert "The SDG pack:" not in manual and "load-vca" not in manual
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "optional pack" not in readme and "export-flexiconc" not in readme
