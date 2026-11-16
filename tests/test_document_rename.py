"""0.19.1: a person renames a document, from its opened row in the Documents list or from its page. The title they
give is used everywhere (list, page, Search, the bibliography's view) and stays when the bibliography links, relinks
or unlinks the document; *Use the title it had before* gives back the work's title, else the file's. The research log
says who renamed what. Also: the theory dialog has its own Start Claude Code while the AI's draft waits for it (the
dialog covers the sidebar's Start)."""
from __future__ import annotations

from pathlib import Path

from test_bibliography import _library, zotero  # noqa: F401  (fixture)
from test_app import api, home  # noqa: F401  (fixtures)
from test_zotero_titles import DRAFT, OFFICE, _titles, _with_draft

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "margin" / "gui" / "static"
MINE = "Moreau 2023: why people go back to the office"


def test_a_title_of_ones_own_wins_and_can_be_given_back(zotero, ws, tmp_path):  # noqa: F811
    from margin import bibliography as b
    from margin import ingest, search

    docs = _with_draft(tmp_path / "docs")
    _library(zotero, tmp_path / "Zotero" / "storage", docs / "download (3).pdf")
    ingest.ingest(ws, [docs], ai_access="cloud")
    ids = {Path(r["path"]).name: r["doc_id"] for r in ws.query("SELECT doc_id, path FROM documents")}
    paper, brief = ids["paper_final.txt"], ids["brief.txt"]
    own_brief = _titles(ws)["brief.txt"][0]
    works, src = b.pull_zotero("user")
    b.save(ws, works, src)
    assert _titles(ws)["paper_final.txt"] == (OFFICE, DRAFT)
    before = search.passage_index(ws)
    corpus = ws.corpus_version()

    # renamed: its title everywhere; the file's own title is kept; nothing else counts it as a change of the corpus
    got = b.set_title(ws, paper, f"  {MINE}\n ")
    assert got == {"doc_id": paper, "title": MINE, "named": True, "changed": True}
    assert _titles(ws)["paper_final.txt"] == (MINE, DRAFT)
    assert ws.corpus_version() == corpus
    after = search.passage_index(ws)
    assert after is not before and {r["title"] for r in after.rows if r["doc_id"] == paper} == {MINE}
    # the same title again: no change
    assert b.set_title(ws, paper, MINE)["changed"] is False
    # the bibliography saved again, unlinked, linked again: the person's title stays
    b.save(ws, works, src)
    assert _titles(ws)["paper_final.txt"] == (MINE, DRAFT)
    b.decide(ws, "zotero:user:OFFICEL1", paper, "different")
    assert _titles(ws)["paper_final.txt"][0] == MINE
    b.decide(ws, "zotero:user:OFFICEL1", paper, "same")
    assert _titles(ws)["paper_final.txt"][0] == MINE
    # given back: the work's title (it is linked), the file's kept as before
    back = b.set_title(ws, paper, "")
    assert back["named"] is False and back["title"] == OFFICE
    assert _titles(ws)["paper_final.txt"] == (OFFICE, DRAFT)

    # a document no work is linked to: renamed, then given back its own title from the file
    b.set_title(ws, brief, "Staff survey (short)")
    assert _titles(ws)["brief.txt"] == ("Staff survey (short)", own_brief)
    assert b.file_title(ws.query("SELECT title, file_title FROM documents WHERE doc_id=?", (brief,))[0]) == own_brief
    b.set_title(ws, brief, None)
    assert _titles(ws)["brief.txt"] == (own_brief, None)
    # a very long title is cut; an unknown document is a KeyError
    assert len(b.set_title(ws, brief, "x" * 500)["title"]) == b.MAX_TITLE
    try:
        b.set_title(ws, "nope", "A")
        raise AssertionError("an unknown document was renamed")
    except KeyError:
        pass

    # the research log: one entry per rename, with the title before and after
    log = ws.query("SELECT subject_id, title, text, data_json FROM research_log WHERE kind='document-title' "
                   "ORDER BY at, rowid")
    assert [r["subject_id"] for r in log][:2] == [paper, paper]
    assert log[0]["text"] == f"Renamed from “{OFFICE}” to “{MINE}”." and log[0]["title"] == MINE
    assert log[1]["text"].startswith("Its own title is back: “" + OFFICE)


def test_the_app_renames_a_document(api, tmp_path):  # noqa: F811
    from margin import home as core
    from margin import ingest

    docs = _with_draft(tmp_path / "docs")
    ws = core.create_project("T")
    ingest.ingest(ws, [docs], ai_access="cloud")
    listed = {d["file"]: d for d in api("GET", "/api/projects/T/documents")[1]["documents"]}
    doc = listed["paper_final.txt"]
    assert doc["named"] is False and doc["title"] == DRAFT
    st, r = api("PUT", f"/api/projects/T/documents/{doc['doc_id']}/title", {"title": MINE})
    assert st == 200 and r["title"] == MINE and r["named"] is True
    listed = {d["file"]: d for d in api("GET", "/api/projects/T/documents")[1]["documents"]}
    assert listed["paper_final.txt"]["title"] == MINE and listed["paper_final.txt"]["named"] is True
    one = api("GET", f"/api/projects/T/documents/{doc['doc_id']}?view=blocks&offset=0&limit=5")[1]
    assert one["title"] == MINE and one["named"] is True and one["file_title"] == DRAFT
    st, found = api("GET", "/api/projects/T/search?q=informal+learning")
    assert st == 200 and [d["title"] for d in found["per_doc"]] == [MINE]
    assert api("PUT", f"/api/projects/T/documents/{doc['doc_id']}/title", {"title": 3})[0] == 400
    assert api("PUT", "/api/projects/T/documents/nope/title", {"title": "A"})[0] == 404
    st, r = api("PUT", f"/api/projects/T/documents/{doc['doc_id']}/title", {"title": ""})
    assert st == 200 and r["title"] == DRAFT and r["named"] is False


def _js(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_rename_stands_in_the_opened_row_and_on_the_page():
    shared = _js("views/doc-shared.js")
    assert "export async function renameDocument(project, d)" in shared
    assert "/documents/${P(d.doc_id)}/title`" in shared and '"Use the title it had before"' in shared
    src = _js("views/sources.js")
    foot = src[src.index('h("div", { class: "doc-detail-foot" }'):src.index('"Remove…")))')]
    assert "renameDocument(project, d)" in foot and '"Rename…")' in foot and "rowFor(d)" in foot
    page = _js("views/doc-page.js")
    assert "actions: [renameBtn, copyBtn, moreSlot] }));" in page
    assert "named: d.named" in page


def test_the_theory_draft_page_can_start_claude_code_itself():
    # the dialog whose backdrop covered the sidebar's Start is gone: a codebook from theory is drafted on a page of
    # its own, and while its reading waits for Claude Code the card shows the queue's notice with Start Claude Code
    assert "draftWithAI" not in _js("views/codebooks.js")
    js = _js("views/theory-draft.js")
    tick = js[js.index("function tickRunning("):js.index("function theoryRead(")]
    assert "runEls.run.update(job)" in tick and 'aiRun({ size: "full", title: "Reading the theory"' in js   # 0.19.13: the AI run panel
