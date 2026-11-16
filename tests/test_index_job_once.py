"""0.17: Set up search by meaning is one job per project. A second press (or a second tab, or a reload while it
runs) gets the job that runs, not a second one embedding the same excerpts; the Documents page shows the running job
in place of the button."""
import threading
from pathlib import Path

from test_app import Api, api, home  # noqa: F401  (fixtures)

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"


def _settings(api):
    # a model is chosen, at an address where nothing listens: no real model is ever loaded
    st, _ = api("PUT", "/api/settings", {"embed_backend": "ollama", "embed_model": "stub-embed",
                                         "embed_url": "http://127.0.0.1:9"})
    assert st == 200


def test_a_second_start_returns_the_running_index_job(api, monkeypatch):
    from margin import embed

    release, started, calls = threading.Event(), threading.Event(), []

    def slow_build(ws, emb, progress=None, should_stop=None, **kw):
        calls.append(1)
        progress(3, 10)
        started.set()
        release.wait(20)
        return {"embedded": 10}

    monkeypatch.setattr(embed, "build", slow_build)
    _settings(api)
    assert api("POST", "/api/projects", {"name": "P"})[0] == 200
    assert api("POST", "/api/projects", {"name": "Q"})[0] == 200
    try:
        st, first = api("POST", "/api/projects/P/index")
        assert st == 200
        assert started.wait(10)
        st, second = api("POST", "/api/projects/P/index")
        assert st == 200
        assert second["job"]["id"] == first["job"]["id"]
        assert second["job"]["kind"] == "index" and second["job"]["state"] in ("queued", "running")
        assert len(calls) == 1                                    # nothing was started twice
        # another project is its own business
        other = api("POST", "/api/projects/Q/index")[1]["job"]["id"]
        assert other != first["job"]["id"]
        # the running job is what /api/jobs lists, once for P
        mine = [j for j in api("GET", "/api/jobs")[1]["jobs"] if j["project"] == "P" and j["kind"] == "index"]
        assert [j["id"] for j in mine] == [first["job"]["id"]]
    finally:
        release.set()
    assert api.wait(first["job"]["id"])["state"] == "done"
    # once it has finished, a new press starts a new job
    release.set()
    again = api("POST", "/api/projects/P/index")[1]["job"]["id"]
    assert again != first["job"]["id"]
    api.wait(again)
    api.wait(other)


def test_the_documents_page_follows_the_running_job():
    js = (STATIC / "views" / "sources.js").read_text(encoding="utf-8")
    draw = js[js.index("function drawIndex(search)"):js.index("// ----------------------------------------------------------------- documents")]
    # the card consults the running job: heading, counts from its progress, a disabled button, no active one
    assert "if (indexJob)" in draw
    assert "Setting up search by meaning…" in draw and "indexJob.progress" in draw
    running = draw[draw.index("if (indexJob)"):draw.index("s.embedded ?")]
    assert "disabled: true" in running and "Set up search by meaning" not in running
    # on and complete, nothing needs you: one quiet line, no card (and never while a job runs)
    settled = draw[draw.index("if (settled)"):draw.index("const indexCard = card(")]
    assert "!indexJob" in draw[:draw.index("if (settled)")]
    assert "docs-index-line" in settled and "Search by meaning is on" in settled and "return;" in settled
    assert "Search by meaning is on" not in draw[draw.index("const indexCard = card("):]
    # started here: the job is kept for the card; found after a reload: the same
    assert js.count("followIndex(") >= 3
    assert "indexJob = indexing" in js
    # when it ends, the counts are read again
    follow = js[js.index("function followIndex"):js.index("function drawIndex(search)")]
    assert "indexJob = null" in follow and "reloadDocs()" in follow


def test_the_sidebar_does_not_call_the_index_job_claude():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    # (0.18: a round of the shared folder and a new reading run on this computer too; 0.19: the server says where)
    assert 'here: { icon: "house", label: "This computer"' in js and "where: j.where || null" in js
    assert "WHERE_CHIP[w.where]" in js and "LOCAL_JOB_KINDS" not in js


def test_cloud_work_has_its_own_shape_in_the_sidebar():
    """0.19.13 (the AI run panel's row): work that sends passages to Claude has the cloud at the box's right end, work
    of the model on this computer the house at its left end, and the split bar along its top; never a colour of its own."""
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "components.css").read_text(encoding="utf-8")
    assert 'j.where == null && App.privacy().where === "cloud"' in js   # the AI of Settings, when Claude
    assert 'w = { kind: "running", where: "cloud", main: "Claude Code is working"' in js and 'cloudHalf: "run"' in js
    # the engine with no work keeps its seat, a dashed tile, at its end (BUILD: every single-engine panel, the row too)
    assert 'replace(box, bar, w.local ? tile("local") : ai ? seat("local") : null, mid || main, mid ? null : act, w.cloudHalf ? tile("cloud") : ai ? seat("cloud") : null);' in js
    # its button under the words (no state word cut between the two tiles), the status area a line taller then
    assert 'const mid = ai && act ? h("div", { class: "work-mid" }, main, act) : null;' in js
    assert ".status-area:has(> .work-box.ab-row:not([hidden])) { height: auto; min-height: 66px; }" in css
    assert ".work-box.ab-row {" in css and ".ab-rowbar {" in css and ".work-rail" not in css
    assert "--accent" not in css[css.index(".work-box.ab-row {"):css.index(".sidebar-app {")]


def test_the_server_says_which_jobs_run_on_this_computer():
    """0.19: the dry run before a new reading was called "Claude" in the sidebar: every job that reads no document
    with the AI says where it runs, and the two jobs of kind "reread" are told apart by their lane."""
    from margin.gui.api_common import Job, job_where

    def job(kind, lane=None):
        j = Job(kind, "t", "p")
        j.lane = lane
        return j

    for kind in ("new_reader_preview", "new_reader", "index", "ingest", "folder-sync", "keywords", "terms", "themes",
                 "theme-new", "codebook-try", "bibliography", "read-local", "queue-local-mix", "queue-local-limit"):
        assert job_where(job(kind)) == "here", kind
    assert job_where(job("reread", "reader")) == "here"       # one document moved to the new reader
    assert job_where(job("reread")) is None                   # one excerpt read again by the AI
    assert job_where(job("check")) is None and job_where(job("label")) is None
    assert job_where(job("retractions")) == "crossref"
    assert job_where(job("claude-install")) == "none"
    assert job("new_reader_preview").view(full=False)["where"] == "here"
