"""Fixes from the review of the ENLENS 0.16 to 0.19.3 sync: what was written in ENLENS is yours in Margin, a label's
practice and element follow a renamed code, and a project copied from ENLENS loses ENLENS's triggers."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from margin import codebooks, home, ingest, notes, researchlog
from margin.store import Workspace

DEMO = Path(__file__).resolve().parent.parent / "tools" / "demo_corpus"


def _ws(tmp_path) -> Workspace:
    ws = Workspace.create(tmp_path / "p")
    ingest.ingest(ws, [DEMO / "commuting_emissions_report.txt"])
    return ws


def test_a_note_and_a_log_entry_written_in_enlens_are_yours(tmp_path):
    ws = _ws(tmp_path)
    eid = researchlog.add(ws, "Decided to leave out the pilot interviews.")["entry_id"]
    with ws.connect() as cx:
        cx.execute("UPDATE research_log SET person_id='pabc123' WHERE entry_id=?", (eid,))
    e = researchlog.entry(ws, eid)
    assert e["mine"] and e["can_edit"]
    assert researchlog.update(ws, eid, text="Decided to keep them.")["text"] == "Decided to keep them."
    doc, text = ws.query("SELECT doc_id, text FROM documents")[0]
    words = " ".join(text.split()[:4])
    i = text.find(words)
    n = notes.add(ws, doc, i, i + len(words), None, "look here")
    with ws.connect() as cx:
        cx.execute("UPDATE notes SET person_id='pabc123' WHERE note_id=?", (n["note_id"],))
    assert notes.update(ws, n["note_id"], text="changed")["text"] == "changed"
    assert len(notes.search(ws, mine=True)["notes"]) == 1


def test_a_copied_enlens_project_loses_its_triggers(tmp_path):
    ws = _ws(tmp_path)
    with ws.connect() as cx:
        cx.execute("CREATE TABLE sync_changes(n INTEGER)")
        cx.execute("CREATE TRIGGER margin_changes_notes AFTER INSERT ON notes BEGIN INSERT INTO sync_changes VALUES (1); END")
    target = tmp_path / "copy"
    home._copy_project(ws.root, target)
    cx = sqlite3.connect(target / home.DB_FILE)
    try:
        assert cx.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0] == 0
        assert cx.execute("SELECT count(*) FROM documents").fetchone()[0] == 1
    finally:
        cx.close()
