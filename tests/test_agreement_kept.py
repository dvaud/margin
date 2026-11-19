"""Agreement between routes, kept (roadmap I5): each finished comparison is stored in the project, listed newest first,
and a new one is shown beside the last of its kind. Stand-ins only (the local model and Claude of
test_agreement_between_routes.py); nothing is loaded or sent."""
from __future__ import annotations

import pytest

from margin import access, benchmark, home as home_mod, ingest
from test_agreement_between_routes import Claude, Local, _answer, _task, two_pids  # noqa: F401  (fixture)
from test_app import api, home  # noqa: F401  (fixtures)
from _views import needs_node, run_views


def _run(ws, grades=None, kind="check"):
    return benchmark.agreement(ws, kind, 30, (Local(grades), "small-model"), Claude(), claude_model="sonnet")


def _tasks(ws, pids, names=("C1", "C2")):
    for n in names:
        _task(ws, n, pids, claude=_answer(("supports", "refutes")))


def test_a_run_names_its_two_models(loaded, two_pids):
    _tasks(loaded, two_pids)
    out = _run(loaded)
    assert out["local_model"] == "small-model"                 # asked now
    assert out["claude_model"] == "m"                          # Claude's answers were already there (by model "m")


def test_a_reused_local_answer_is_named_by_the_model_that_gave_it(loaded, two_pids):
    _tasks(loaded, two_pids, ("C1",))
    with loaded.connect() as cx:                               # C1's local answer came from an earlier local model
        cx.execute("INSERT INTO results(task_id, attempt, kind, model, raw_json, valid, route) VALUES (?,?,?,?,?,1,?)",
                   ("check:C1", 3, "check", "old-model", _answer(("supports", "refutes")), "local model server"))
    _tasks(loaded, two_pids, ("C2",))
    out = _run(loaded)
    assert out["local_model"] == "old-model, small-model" and out["asked"]["local"] == 1
    row = benchmark.keep_agreement(loaded, out)
    assert row["asked_local"] == 1 and row["local_model"] == "old-model, small-model"


def test_a_run_with_nothing_compared_is_never_the_one_beside(loaded, two_pids):
    _tasks(loaded, two_pids)
    a = benchmark.keep_agreement(loaded, _run(loaded))
    empty = benchmark.keep_agreement(loaded, {**_run(loaded), "compared": 0, "kappa": None, "agree": None})
    c = benchmark.keep_agreement(loaded, _run(loaded))
    assert benchmark.previous_agreement(loaded, "check", c["run_id"])["run_id"] == a["run_id"] != empty["run_id"]


def test_keeping_a_run_stores_its_row(loaded, two_pids):
    _tasks(loaded, two_pids)
    out = _run(loaded)
    row = benchmark.keep_agreement(loaded, out)
    assert row["kind"] == "check" and row["n"] == 2 and row["compared"] == 2 and row["failed"] == 0
    assert row["kappa"] == out["kappa"] and row["agree"] == out["agree"] and row["decisions"] == 4
    assert row["local_model"] == "small-model" and row["claude_model"] == "m"
    assert row["app_version"] and row["at"] and row["run_id"]
    assert benchmark.kept_agreements(loaded) == [row]


def test_kept_runs_come_newest_first_and_previous_is_of_the_same_kind(loaded, two_pids):
    _tasks(loaded, two_pids)
    a = benchmark.keep_agreement(loaded, _run(loaded))
    _task(loaded, "R1", two_pids, kind="reread", claude=_answer(("supports", "refutes")))
    b = benchmark.keep_agreement(loaded, _run(loaded, kind="reread"))
    c = benchmark.keep_agreement(loaded, _run(loaded, {"C1": ("refutes", "refutes")}))
    assert [r["run_id"] for r in benchmark.kept_agreements(loaded)] == [c["run_id"], b["run_id"], a["run_id"]]
    assert [r["run_id"] for r in benchmark.kept_agreements(loaded, limit=2)] == [c["run_id"], b["run_id"]]
    assert benchmark.previous_agreement(loaded, "check", c["run_id"])["run_id"] == a["run_id"]
    assert benchmark.previous_agreement(loaded, "check", a["run_id"]) is None
    assert benchmark.previous_agreement(loaded, "reread", b["run_id"]) is None


def test_failed_tasks_inside_a_finished_run_are_kept_as_failed(loaded, two_pids):
    _tasks(loaded, two_pids, ("C1",))
    _task(loaded, "Bad", two_pids, claude="not json at all")
    out = _run(loaded)
    row = benchmark.keep_agreement(loaded, out)
    assert out["failed"] == row["failed"] and row["compared"] == out["compared"]


def _ready(api, home, corpus, monkeypatch):  # noqa: F811
    ws = home.create_project("A")
    ingest.ingest(ws, [corpus])
    pids = [r[0] for r in ws.query("SELECT passage_id FROM passages ORDER BY passage_id LIMIT 2")]
    for n in ("C1", "C2", "C3"):
        _task(ws, n, pids, claude=_answer(("supports", "refutes")))
    home.update_settings({"allow_cloud": True, "backend": "anthropic", "restricted_server": "ollama",
                          "restricted_model": "small"})
    local, claude = Local(), Claude()
    monkeypatch.setattr(access.Readers, "local", lambda self: (local, "small"))
    monkeypatch.setattr(home_mod, "make_backend", lambda s, key=None, kinds=(): (claude, "stub"))
    return ws


def test_the_routes_keep_and_list(api, home, corpus, monkeypatch):  # noqa: F811
    ws = _ready(api, home, corpus, monkeypatch)
    assert api("GET", "/api/projects/A/agreement/plan")[1]["kept"] == []
    st, r = api("POST", "/api/projects/A/agreement", {"kind": "check", "n": 10})
    first = api.wait(r["job"]["id"])
    assert first["state"] == "done", first
    res = first["result"]
    assert res["previous"] is None and res["kept"]["kind"] == "check" and res["kept"]["kappa"] == res["kappa"]
    assert res["local_model"] == "small" and res["claude_model"]
    st, r = api("POST", "/api/projects/A/agreement", {"kind": "check", "n": 10})
    second = api.wait(r["job"]["id"])["result"]
    assert second["previous"]["run_id"] == res["kept"]["run_id"]
    assert second["kept"]["run_id"] != res["kept"]["run_id"]
    kept = api("GET", "/api/projects/A/agreement/plan")[1]["kept"]
    assert [k["run_id"] for k in kept] == [second["kept"]["run_id"], res["kept"]["run_id"]]
    assert ws.scalar("SELECT COUNT(*) FROM agreement_runs") == 2


def test_a_run_stopped_with_stop_is_not_kept(api, home, corpus, monkeypatch):  # noqa: F811
    ws = _ready(api, home, corpus, monkeypatch)
    real = benchmark.agreement

    def with_stop(*a, progress=None, should_stop=None, **kw):
        should_stop.__self__.set()   # Stop is pressed: the job's cancel Event is set, and the loop ends
        return real(*a, progress=progress, should_stop=should_stop, **kw)

    monkeypatch.setattr(benchmark, "agreement", with_stop)
    st, r = api("POST", "/api/projects/A/agreement", {"kind": "check", "n": 10})
    job = api.wait(r["job"]["id"])
    assert job["state"] in ("done", "cancelled")
    assert ws.scalar("SELECT COUNT(*) FROM agreement_runs") == 0
    assert not (job.get("result") or {}).get("kept")


# ---- the Settings box ---------------------------------------------------------------------------------------
PROBE = r"""
const KINDS = [{ kind: "check", answered: 5, name: "checking claims", noun: "checks" }, { kind: "label", answered: 5, name: "labels", noun: "labels" }];
const run = (n, kind, kappa, at) => ({ run_id: `r${n}`, at, kind, n: 30, compared: 28, failed: 2, decisions: 90, kappa, agree: 0.91,
  local_model: "qwen3:8b", claude_model: "sonnet", app_version: "0.19.15" });
async function settings(t, kept, result = null) {
  t.state({ settings: { backend: "claude_code", restricted_server: "ollama", restricted_model: "qwen3:8b" } });
  t.answer("GET /api/servers", { servers: [], suggested: [] });
  t.answer("GET /api/claude-setup", {});
  t.answer("GET /api/local-status", {});
  t.answer("GET /api/routing", { route: "claude_code", route_name: "Claude Code", rows: [], aliases: [], step_up_below: 0.6, plan: {} });
  t.answer("GET /api/whats-new", {});
  t.answer("GET /api/projects/Study/queue", { kinds: [], waiting: 0 });
  t.answer("GET /api/projects/Study/agreement/plan?*", { kinds: KINDS, problem: null, claude: "claude_code", kept,
    plan: { kind: "check", n: 28, ask_local: 0, ask_claude: 0, left_out: 0 } });
  t.answer("POST /api/projects/Study/agreement", { job: { id: "j1" } });
  t.answer("GET /api/jobs/j1", { id: "j1", state: "done", progress: {}, result });
  // the Settings rework: agreement between routes is a card of the Technical tab
  // the card is folded on Technical until a link to it (#/settings/agreement) opens it
  await t.render("views/settings.js", "renderSettings", ["agreement"]);
  await t.settle(1000);
  return document.getElementById("s-agreement");
}

await scenario("a few earlier comparisons", async (t) => {
  const box = await settings(t, [run(2, "label", 0.71, "2026-11-10T09:00:00+00:00"), run(1, "check", 0.62, "2025-11-03T09:00:00+00:00")]);
  return { text: t.text(box), items: box.querySelectorAll(".agree-kept li").map((x) => t.text(x)), folds: box.querySelectorAll(".agree-kept details").length };
});

await scenario("many earlier comparisons fold", async (t) => {
  const kept = Array.from({ length: 11 }, (_, i) => run(i, "check", 0.5, "2026-11-01T09:00:00+00:00"));
  const box = await settings(t, kept);
  const fold = box.querySelector(".agree-kept details");
  return { shown: box.querySelectorAll(".agree-kept > ul > li").length, summary: t.text(fold.querySelector("summary")), inFold: fold.querySelectorAll("li").length };
});

await scenario("none yet", async (t) => {
  const box = await settings(t, []);
  return { has: box.querySelectorAll(".agree-kept li").length, text: t.text(box) };
});

await scenario("a new comparison beside the last one", async (t) => {
  const before = run(1, "check", 0.62, "2025-11-03T09:00:00+00:00");
  const now = run(2, "check", 0.71, "2026-11-17T09:00:00+00:00");
  const box = await settings(t, [before], { kind: "check", n: 30, compared: 28, failed: 2, kappa: 0.71, agree: 0.93, decisions: 90, verdict: "Fair for checking claims.",
    asked: { local: 1, claude: 2 }, kept: now, previous: before });
  await t.click("Compare the routes", { within: box });
  await t.settle(1500);
  return { text: t.text(box), items: box.querySelectorAll(".agree-kept li").length, toasts: t.toasts() };
});

await scenario("a new comparison with nothing before it", async (t) => {
  const now = run(2, "check", 0.71, "2026-11-17T09:00:00+00:00");
  const box = await settings(t, [], { kind: "check", n: 30, compared: 28, failed: 0, kappa: 0.71, agree: 0.93, decisions: 90, verdict: "Fair.",
    asked: { local: 1, claude: 2 }, kept: now, previous: null });
  await t.click("Compare the routes", { within: box });
  await t.settle(1500);
  return { text: t.text(box), items: box.querySelectorAll(".agree-kept li").length };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("agree_kept"))


@needs_node
def test_the_help_says_the_comparisons_are_kept_here(page):
    text = page["a few earlier comparisons"]["text"]
    assert "kept, dated, in the project on this computer" in text
    assert "Nothing is stored" not in text


@needs_node
def test_earlier_comparisons_are_listed_quietly(page):
    p = page["a few earlier comparisons"]
    assert p["folds"] == 0 and len(p["items"]) == 2
    assert p["items"][0].startswith("10 Nov") and "Labels" not in p["items"][0] and "labels" in p["items"][0]
    assert "28 compared" in p["items"][0] and "kappa 0.71" in p["items"][0] and "91% agree" in p["items"][0]
    assert "qwen3:8b and sonnet" in p["items"][0] and "Margin 0.19.15" in p["items"][0]
    assert p["items"][1].startswith("3 Nov 2025") and "checking claims" in p["items"][1]


@needs_node
def test_more_than_eight_fold_away(page):
    p = page["many earlier comparisons fold"]
    assert p["shown"] == 8 and p["summary"] == "3 more" and p["inFold"] == 3


@needs_node
def test_no_list_before_the_first_comparison(page):
    assert page["none yet"]["has"] == 0 and "Earlier comparisons" not in page["none yet"]["text"]


@needs_node
def test_a_new_result_shows_the_last_kappa_of_the_kind_beside_it(page):
    p = page["a new comparison beside the last one"]
    assert "Kappa 0.62 on 3 Nov 2025 → 0.71 now" in p["text"]
    assert p["items"] == 2 and p["toasts"] == []


@needs_node
def test_a_first_result_has_nothing_to_set_beside(page):
    p = page["a new comparison with nothing before it"]
    assert "→" not in p["text"] and p["items"] == 1


def test_a_kept_run_goes_with_a_whole_project_zip(loaded, two_pids, tmp_path):
    import sqlite3
    import zipfile

    from margin import bundle

    _tasks(loaded, two_pids)
    benchmark.keep_agreement(loaded, _run(loaded))
    z = tmp_path / "all.zip"
    bundle.export_project(loaded, z)
    with zipfile.ZipFile(z) as zf:
        (tmp_path / "all.sqlite").write_bytes(zf.read("enlens.sqlite"))
    cx = sqlite3.connect(tmp_path / "all.sqlite")
    try:
        assert cx.execute("SELECT COUNT(*) FROM agreement_runs").fetchone()[0] == 1
    finally:
        cx.close()


def test_a_new_project_has_the_table(home):  # noqa: F811
    ws = home.create_project("Fresh")
    assert benchmark.kept_agreements(ws) == []
