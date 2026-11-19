"""0.16 (roadmap F4): the research log.

- the app writes an entry by itself when something is decided: documents added (one entry a batch) and removed (with
  the reason), who may read documents with AI, a check made and removed (with the reason), themes found, a theme
  removed, renamed or merged, a set of themes removed; a check the app takes back before it was made leaves nothing;
- a person adds, edits and removes entries of their own and says why beside any entry of theirs; the app's entries
  keep their words and cannot be removed; a colleague's entries cannot be changed here;
- the log filters by group and words, and goes out as Markdown (oldest first, a heading a day) and Excel;
- entries travel with the project: a colleague's come in under their name, yours are never changed, an entry you
  removed does not come back, and one its author removed goes here too.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from margin import access, claimcheck, ingest, researchlog, store, themes
from margin.store import Workspace

from test_app import Api, api, home  # noqa: F401  (fixtures)

DEMO = Path(__file__).resolve().parents[1] / "tools" / "demo_corpus"


def _kinds(ws: Workspace) -> list[str]:
    return [e["kind"] for e in researchlog.entries(ws, oldest_first=True)["entries"]]


@pytest.fixture
def demo(tmp_path) -> Workspace:
    ws = Workspace.create(tmp_path / "ws")
    ingest.ingest(ws, [DEMO])
    return ws


def test_documents_added_and_removed_are_written_down(demo):
    e = researchlog.entries(demo)["entries"]
    assert [x["kind"] for x in e] == ["documents-added"]
    assert e[0]["text"].startswith("Added 6 documents: “") and "and 1 more" in e[0]["text"]
    assert len(e[0]["data"]["documents"]) == 6 and e[0]["mine"] and e[0]["who"] == "you"
    doc, title = demo.query("SELECT doc_id, title FROM documents ORDER BY doc_id LIMIT 1")[0]
    demo.remove_document(doc, why="a duplicate of the panel study")
    last = researchlog.entries(demo)["entries"][0]
    assert last["kind"] == "document-removed" and title[:40] in last["text"] and last["why"] == "a duplicate of the panel study"
    assert last["subject_kind"] == "document" and last["subject_id"] == doc


def test_a_check_made_and_dropped_with_its_reason_and_one_taken_back_leaves_nothing(demo):
    hid = claimcheck.create_hypothesis(demo, "Remote work lowers commuting emissions.")
    claimcheck.new_claim(demo, "Remote work lowers commuting emissions.", hyp_id=hid)
    claimcheck.delete_hypothesis(demo, hid, why="reworded as two hypotheses")
    e = researchlog.entries(demo, group="checks", oldest_first=True)["entries"]
    assert [x["kind"] for x in e] == ["check-added", "check-removed"]
    assert e[1]["why"] == "reworded as two hypotheses" and "commuting emissions" in e[1]["text"]
    # a check the app takes back (stopped, withdrawn, a look before checking) never was: no line about it
    hid2 = claimcheck.create_hypothesis(demo, "Hybrid work raises productivity for most workers.")
    claimcheck.delete_hypothesis(demo, hid2, unmade=True)
    assert not researchlog.entries(demo, subject_id=hid2)["entries"]
    # removing the last part of a check removes the check: written down once
    hid3 = claimcheck.create_hypothesis(demo, "Rush hour traffic came back after the pandemic.")
    cid = claimcheck.new_claim(demo, "Rush hour traffic came back after the pandemic.", hyp_id=hid3)
    claimcheck.delete_claim(demo, cid)
    assert [x["kind"] for x in researchlog.entries(demo, subject_id=hid3)["entries"]] == ["check-removed", "check-added"]


def test_who_may_read_documents_with_ai_is_written_down(demo):
    docs = [r[0] for r in demo.query("SELECT doc_id FROM documents ORDER BY doc_id")]
    access.set_documents(demo, docs[:1], "none")
    access.set_documents(demo, docs[:3], "local")
    access.set_documents(demo, docs[:3], "local")  # no change: no line
    e = researchlog.entries(demo, group="documents")["entries"]
    assert [x["kind"] for x in e[:2]] == ["ai-access", "ai-access"]
    assert e[1]["text"].startswith("Who may read “") and e[1]["text"].endswith("no AI may read it.")
    assert e[0]["text"] == "Who may read 3 documents with AI: only a local AI may read them."
    access.set_default(demo, "cloud")
    access.set_default(demo, "local")
    assert researchlog.entries(demo, group="documents")["entries"][0]["text"] == \
        "New documents of this project: only a local AI may read them (before: Claude may read them)."


def test_themes_found_removed_renamed_and_merged_are_written_down_with_the_state_before(demo):
    rid = themes.run(demo, k=4)
    v = themes.view(demo, rid)
    a, b, c = (t["theme_id"] for t in v["themes"][:3])
    themes.edit(demo, rid, "rename", a, "Commuting")
    themes.edit(demo, rid, "merge", b, a)
    themes.edit(demo, rid, "merge", b, None)
    themes.edit(demo, rid, "remove", c, True, reason="boilerplate of the policy brief")
    themes.edit(demo, rid, "remove", c, False)
    e = researchlog.entries(demo, group="themes", oldest_first=True)["entries"]
    assert [x["kind"] for x in e] == ["themes-found", "theme-renamed", "theme-merged", "theme-separated",
                                      "theme-removed", "theme-restored"]
    assert e[0]["text"].startswith("Found 4 themes by words in ")
    assert e[1]["text"].endswith("to “Commuting”.") and e[2]["text"].endswith("into “Commuting”.")
    assert e[4]["why"] == "boilerplate of the policy brief"
    assert all(x["has_version"] for x in e[1:])  # each change names the state before it (history.py)
    themes.delete_run(demo, rid, why="found again with more themes")
    last = researchlog.entries(demo)["entries"][0]
    assert last["kind"] == "themes-removed" and last["why"] == "found again with more themes"


def test_your_own_entries_and_reasons_and_what_cannot_be_changed(demo):
    e = researchlog.add(demo, "Decided to code the interviews before the reports.\nSecond line.")
    assert e["kind"] == "entry" and e["can_edit"] and e["group"] == "entries"
    with pytest.raises(ValueError, match="Write the entry"):
        researchlog.add(demo, "   ")
    e2 = researchlog.update(demo, e["entry_id"], text="Decided to code the interviews first.", why="they are shorter")
    assert e2["text"] == "Decided to code the interviews first." and e2["why"] == "they are shorter" and e2["edited_at"]
    auto = researchlog.entries(demo, group="documents")["entries"][0]
    with pytest.raises(ValueError, match="keep their words"):
        researchlog.update(demo, auto["entry_id"], text="something else")
    with pytest.raises(ValueError, match="cannot be removed"):
        researchlog.remove(demo, auto["entry_id"])
    assert researchlog.update(demo, auto["entry_id"], why="the first batch")["why"] == "the first batch"
    assert researchlog.update(demo, auto["entry_id"], why="")["why"] is None
    researchlog.remove(demo, e["entry_id"])
    assert not demo.scalar("SELECT 1 FROM research_log WHERE entry_id=?", (e["entry_id"],))  # Margin: no sync_removed
    # Margin: an entry written in ENLENS (under its own person id) is yours
    with demo.connect() as cx:
        other = researchlog.record(cx, "entry", "Written in ENLENS", person_id="p0123456789ab")
    assert researchlog.update(demo, other, why="mine now")["why"] == "mine now"
    researchlog.remove(demo, other)


def test_the_log_filters_searches_and_goes_out_as_markdown_and_excel(demo):
    researchlog.add(demo, "Field note: the panel study uses self-reported hours.")
    hid = claimcheck.create_hypothesis(demo, "Remote work lowers commuting emissions.")
    claimcheck.delete_hypothesis(demo, hid, why="too broad")
    r = researchlog.entries(demo)
    assert r["total"] == 4 and r["groups"] == {"documents": 1, "entries": 1, "checks": 2}
    assert [x["kind"] for x in researchlog.entries(demo, q="SELF-REPORTED")["entries"]] == ["entry"]
    assert [x["kind"] for x in researchlog.entries(demo, q="too broad")["entries"]] == ["check-removed"]  # the reason
    assert researchlog.entries(demo, q="100%_")["total"] == 0  # LIKE wildcards are words here
    with pytest.raises(ValueError):
        researchlog.entries(demo, group="nonsense")
    md = researchlog.markdown(demo, "Demo")
    assert md.startswith("# Research log: Demo\n") and md.count("\n## ") == 1
    assert md.index("Added 6 documents") < md.index("Field note") < md.index("Removed the check")
    assert "  *Why:* too broad" in md
    rows = researchlog.table(demo)
    # a file goes to other people: a person's entry is an "Entry" there, never "Your own entries" (Who says whose)
    assert [r["What"] for r in rows] == ["Documents", "Entry", "Checks", "Checks"] and rows[3]["Why"] == "too broad"


def test_the_log_page_has_one_menu_per_row_and_no_button_under_an_entry():
    """0.19.7: the page was mostly buttons (Say why on a line of its own under every entry, Edit, Remove, Compare).
    Each row's actions are one More menu at its end; the chips are a Show list; the downloads are in the head."""
    js = (Path(__file__).resolve().parents[1] / "src" / "margin" / "gui" / "static" / "views" / "log.js").read_text(encoding="utf-8")
    row = js[js.index("  function entryRow(e) {"):js.index("  async function editWhy(e) {")]
    assert "menu({" in row and "button(" not in row and "log-actions" not in js
    for words in ('"Say why"', '"Change why"', '"Edit"', '"Compare with before"', '"Remove…"'):
        assert words in row
    assert row.index('"sep"') < row.index('"Remove…"') and "danger: true" in row
    assert 'pageHead("Research log"' in js and "actions: downloadLinks(" in js and "viewTabs" not in js
    assert "choice(" not in js and 'select({ sm: true, id: "log-show" })' in js
    assert 'h("label", { class: "log-show-label", for: "log-show" }, "Show")' in js      # its word is in view
    assert 'title: "Ctrl/⌘ + Enter adds it"' in js and "card(" not in js


def test_the_log_through_the_app(api, tmp_path):  # noqa: F811
    assert api("POST", "/api/projects", {"name": "Demo"})[0] == 200
    st, r = api("POST", "/api/projects/Demo/log", {"text": "First entry of the project."})
    assert st == 200 and r["entry"]["kind"] == "entry"
    eid = r["entry"]["entry_id"]
    assert api("POST", "/api/projects/Demo/log", {"text": " "})[0] == 400
    st, r = api("PUT", f"/api/projects/Demo/log/{eid}", {"why": "to start the log"})
    assert st == 200 and r["entry"]["why"] == "to start the log"
    st, r = api("GET", "/api/projects/Demo/log?group=entries")
    assert st == 200 and r["total"] == 1 and r["group_names"]["entries"] == "Your own entries"
    st, body = api("GET", "/api/projects/Demo/log.md")
    assert st == 200 and b"First entry of the project." in body
    st, body = api("GET", "/api/projects/Demo/log.xlsx")
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(body))
    assert wb.sheetnames[0] == "Research log" and wb.active["D2"].value == "First entry of the project."
    assert api("DELETE", f"/api/projects/Demo/log/{eid}")[0] == 200
    assert api("DELETE", f"/api/projects/Demo/log/{eid}")[0] == 404
    from margin import home as home_mod

    ws = home_mod.open_project("Demo")
    with ws.connect() as cx:
        other = researchlog.record(cx, "entry", "A colleague's", person_id="p0123456789ab")
    st, r = api("PUT", f"/api/projects/Demo/log/{other}", {"text": "mine"})
    assert st == 200 and "mine" in str(r)  # Margin: an entry written in ENLENS is yours
