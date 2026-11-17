"""0.20: the AI's draft name for a concept-map group (task kind `group_name`) is this copy's own.

The names and their quotes are local tables (`concept_group_names`, `concept_group_quotes`), but the task that made
a name, and its result (the draft and its quote), are rows too. They never leave this copy (a zip for a colleague, the
shared folder's rows) and never come in from a colleague (a merged zip): else a colleague's name would answer here,
and their failed task would show on this map. A finished task of another kind outside checks and theme runs is still
carried: it says how an answer was made.
"""
from __future__ import annotations

import json
import sqlite3
import zipfile

from test_shared_projects import anna_and_ben  # noqa: F401  (fixture)

from margin import bundle, groupnames, sharing, sync

OTHER = "label"  # a finished task outside checks and theme runs: carried


def _add(ws) -> None:
    """One finished `group_name` task with its result, one failed one, and a control of another kind."""
    pid, doc = ws.query("SELECT passage_id, doc_id FROM passages LIMIT 1")[0]
    with ws.connect() as cx:
        for tid, kind, status in (("group_name:done1", groupnames.KIND, "done"),
                                  ("group_name:failed1", groupnames.KIND, "failed"),
                                  ("control:done1", OTHER, "done")):
            cx.execute("INSERT INTO tasks(task_id, kind, model, prompt_version, payload_json, status, attempts, "
                       "created_at, access) VALUES (?,?,?,?,?,?,1,'2026-11-17T00:00:00+00:00','cloud')",
                       (tid, kind, "claude-sonnet-5-5", "v1", json.dumps({"passages": [pid], "doc": doc}), status))
            cx.execute("INSERT INTO results(task_id, attempt, kind, model, prompt_version, raw_json, valid, "
                       "errors_json, received_at) VALUES (?,1,?,?,?,?,?,'[]','2026-11-17T00:00:00+00:00')",
                       (tid, kind, "claude-sonnet-5-5", "v1", json.dumps({"name": "Water and power"}),
                        int(status == "done")))


def _db(zip_path, tmp_path) -> sqlite3.Connection:
    with zipfile.ZipFile(zip_path) as zf:
        (tmp_path / "got.sqlite").write_bytes(zf.read("enlens.sqlite"))
    return sqlite3.connect(tmp_path / "got.sqlite")


def _ids(cx, table="tasks") -> set[str]:
    return {r[0] for r in cx.execute(f"SELECT task_id FROM {table} WHERE task_id LIKE 'group_name:%' OR "
                                     "task_id LIKE 'control:%'")}


def test_a_zip_for_a_colleague_carries_no_group_name_task_or_result(loaded, tmp_path):
    _add(loaded)
    shared, whole = tmp_path / "shared.zip", tmp_path / "whole.zip"
    bundle.export_project(loaded, shared, scope="shared")
    bundle.export_project(loaded, whole, scope="all")
    db = _db(shared, tmp_path)
    assert db.execute("SELECT COUNT(*) FROM tasks WHERE kind=?", (groupnames.KIND,)).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM results WHERE kind=?", (groupnames.KIND,)).fetchone()[0] == 0
    assert not {t for t in _ids(db) if t.startswith("group_name:")} and not {
        t for t in _ids(db, "results") if t.startswith("group_name:")}
    db.close()
    # the whole-project zip (moving your own project) keeps them
    db = _db(whole, tmp_path)
    assert {"group_name:done1", "group_name:failed1"} <= _ids(db)
    db.close()


def test_the_shared_folder_rows_carry_no_group_name_task_or_result(loaded):
    _add(loaded)
    with loaded.connect() as cx:
        rows = sharing.ProjectRows(cx, loaded.root)
        where = {t: w for t, w, _c in rows.tables()}
        kept = {r[0] for r in cx.execute(f"SELECT task_id FROM tasks WHERE {where['tasks']}")}
        kept_results = {r[0] for r in cx.execute("SELECT task_id FROM results")} if where["results"] == "1" else None
    assert not any(t.startswith("group_name:") for t in kept), kept
    assert "control:done1" in kept
    # a result is shared only with its task: the rows' own filter
    if kept_results is not None:
        with loaded.connect() as cx:
            via = {r["task_id"] for r in sharing.ProjectRows(cx, loaded.root)._light("results", where["results"])}
        assert not any(t.startswith("group_name:") for t in via), via


def test_a_colleagues_group_name_task_does_not_come_in(anna_and_ben, tmp_path):  # noqa: F811
    anna, ben = anna_and_ben
    with anna:
        _add(anna.ws)
        f = tmp_path / "anna-all.zip"
        bundle.export_project(anna.ws, f, scope="all")  # (a copy from before the fix: the tasks are in it)
    r = ben.bring_in(f)
    assert r is not None
    with ben:
        assert not ben.ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind=?", (groupnames.KIND,))
        assert not ben.ws.scalar("SELECT COUNT(*) FROM results WHERE task_id LIKE 'group_name:%'")
        assert ben.ws.scalar("SELECT COUNT(*) FROM tasks WHERE task_id='control:done1'") == 1
        assert not groupnames._failures(ben.ws) if hasattr(groupnames, "_failures") else True


def test_the_local_kinds_name_the_group_name_task_and_no_item_kind():
    assert groupnames.KIND in sharing.LOCAL_TASK_KINDS
    assert not set(sharing.LOCAL_TASK_KINDS) & set(sharing.ITEM_TASK_KINDS)
