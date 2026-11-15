"""The codebook chosen for document profiles is one setting for the whole app, but a codebook made in a project is
only in that project. Chosen in one project, it must not leave another with an unknown codebook: there the pages, the
endpoints and the jobs have none chosen (Margin has no default codebook; ENLENS falls back to the SDG targets), and
the first project keeps its choice."""
from __future__ import annotations

import re
from pathlib import Path

from margin import frameworks, home as home_mod

from test_app import Api, api, home  # noqa: F401  (fixtures)

STATIC = Path(__file__).resolve().parents[1] / "src" / "margin" / "gui" / "static"


def test_a_codebook_of_one_project_chosen_there_leaves_the_others_with_none_chosen(api):  # noqa: F811
    for name in ("Alpha", "Beta"):
        assert api("POST", "/api/projects", {"name": name})[0] == 200
    assert api("PUT", "/api/settings", {"project": "Alpha"})[0] == 200
    st, r = api("POST", "/api/projects/Alpha/codebooks", {"name": "remote", "title": "Remote work", "start": "fresh",
                                                          "where": "project"})
    assert st == 200 and r["codebook"]["where"] == "project"
    assert api("PUT", "/api/settings", {"profile_framework": "remote"})[0] == 200

    # in its own project the choice holds
    st, s = api("GET", "/api/state")
    assert st == 200 and s["project"] == "Alpha" and s["profile_framework"] == "remote"
    assert api("GET", "/api/projects/Alpha/profile")[1]["framework"] == "remote"

    # in the other project: none chosen (Margin has no default codebook), with no "Unknown framework" anywhere
    assert api("PUT", "/api/settings", {"project": "Beta"})[0] == 200
    st, s = api("GET", "/api/state")
    assert s["project"] == "Beta" and s["profile_framework"] == ""
    assert s["settings"]["profile_framework"] == "remote"  # the setting itself is kept for Alpha
    st, r = api("GET", "/api/projects/Beta/profile")
    assert st == 409 and "Choose a codebook first" in r["error"]   # asked to choose, not "Unknown framework"
    st, r = api("GET", "/api/projects/Beta/codebooks")
    assert st == 200 and [c["name"] for c in r["codebooks"] if c["profile_default"]] == []
    st, r = api("GET", "/api/projects/Beta/overview")
    assert st == 200
    st, r = api("POST", "/api/projects/Beta/profile/keywords", {})
    assert st == 409 and "Choose a codebook first" in r["error"], r
    st, r = api("GET", "/api/projects/Beta/suggest?text=Remote+work+lowers+commuting+emissions+in+cities")
    assert st == 200 and r == {"codes": []}, r   # (it was an "Unknown framework" error)

    # back in the first project, the choice is still there
    assert api("PUT", "/api/settings", {"project": "Alpha"})[0] == 200
    assert api("GET", "/api/state")[1]["profile_framework"] == "remote"


def test_chosen_falls_back_only_when_the_project_lacks_the_codebook(home):  # noqa: F811
    home_mod.create_project("Gamma")
    ws = home_mod.open_project("Gamma")
    assert frameworks.chosen(None, ws) == ""        # Margin: no default codebook
    assert frameworks.chosen("sdg_goals", ws) == "sdg_goals"
    assert frameworks.chosen("elsewhere", ws) == ""
    (Path(ws.root) / "frameworks").mkdir(exist_ok=True)
    (Path(ws.root) / "frameworks" / "elsewhere.csv").write_text("code,description\nA,Something to code.\n",
                                                                encoding="utf-8")
    assert frameworks.chosen("elsewhere", ws) == "elsewhere"


def test_the_pages_take_the_codebook_the_server_chose_for_this_project():
    """The Themes, Codes, document and Settings pages ask App.framework() (from /api/state), not the bare setting."""
    for f in sorted((STATIC / "views").glob("*.js")):
        if f.name == "concepts.js":   # Margin: it looks the setting up in this project's own list of codebooks
            continue
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"settings\(\)\.profile_framework\s*\|\|", text), f.name
