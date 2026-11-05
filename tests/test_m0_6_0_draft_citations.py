"""Margin 0.6, with ENLENS 0.13.7's Check citations: a draft's own citations, checked against the sources they cite.

A draft's citations are found (without AI) when it is added, as an ENLENS text linked to the draft; drafts from before
are linked when their page or Check citations opens. The draft page shows them as a third step, each underlined in the
draft and on the claim it stands for; a text pasted or chosen on Check citations is kept as a draft. The draft's name
and AI setting are its citations' too, its tasks keep the draft's setting, and removing the draft removes them. The
model is a stand-in that records what it is sent: no real Claude, Zotero or network.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from helpers_0110 import Local, use_local_model
from test_0_13_7_citations import DRAFT, PRIVATE_DRAFT, SECRET, Reader, _project
from test_app import Api, api, home  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "margin" / "gui" / "static"


@pytest.fixture
def project(tmp_path, monkeypatch):
    from margin import home as core

    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = core.create_project("Drafts")
    return ws, _project(ws, tmp_path / "sources")


def _span(text: str, words: str) -> tuple[int, int]:
    a = text.index(words)
    return a, a + len(words)


def _claim(v: dict, start: str) -> dict:
    return next(c for c in v["claims"] if c["quote"].startswith(start))


# ---------------------------------------------------------------------------------------------
# a draft and its citations
# ---------------------------------------------------------------------------------------------
def test_a_new_draft_finds_its_citations_at_once(project):
    from margin import citations, drafts

    ws, _docs = project
    did = drafts.new_draft(ws, DRAFT, "Chapter 2", ai_access="local")
    tid = drafts.citation_text(ws, did)
    assert tid and ws.scalar("SELECT cite_text_id FROM drafts WHERE draft_id=?", (did,)) == tid
    v = citations.view(ws, tid)
    # the same text, so a citation's place is its place in the draft; the draft's name and setting
    assert ws.scalar("SELECT body FROM cite_texts WHERE text_id=?", (tid,)) == drafts.view(ws, did)["text"]
    assert v["text"]["title"] == "Chapter 2" and v["text"]["level"] == "local" and v["citations"] == 8
    assert drafts.of_text(ws, tid) == {"draft_id": did, "title": "Chapter 2"}
    assert drafts.summary(ws, did)["citations"] == 7  # cited works, "but see" aside ("(Figure 3, 2020)" is none)
    # renaming the draft or changing its setting changes its citations' (NULL: the project's default, as the draft)
    drafts.update(ws, did, title="Chapter 2, v2", ai_access="none")
    assert citations.view(ws, tid)["text"]["title"] == "Chapter 2, v2" and citations.view(ws, tid)["text"]["level"] == "none"
    drafts.update(ws, did, ai_access="")
    assert ws.scalar("SELECT ai_access FROM cite_texts WHERE text_id=?", (tid,)) is None
    assert citations.view(ws, tid)["text"]["level"] == "cloud"
    # a draft without citations: looked for once, nothing kept
    plain = drafts.new_draft(ws, "Hydrogen needs water. Deserts are dry and water there is scarce and costly.")
    assert drafts.citation_text(ws, plain) is None
    assert ws.scalar("SELECT cite_text_id FROM drafts WHERE draft_id=?", (plain,)) == ""
    assert drafts.view(ws, plain)["citations"] is None
    assert ws.scalar("SELECT COUNT(*) FROM cite_texts") == 1


def test_a_draft_from_before_is_linked_when_opened(project):
    from margin import drafts

    ws, _docs = project
    did = drafts.new_draft(ws, DRAFT)
    with ws.connect() as cx:  # as a draft added before Margin read citations
        cx.execute("DELETE FROM cite_texts")
        cx.execute("UPDATE drafts SET cite_text_id=NULL")
    drafts.link_all(ws)
    assert drafts.citation_text(ws, did, create=False)
    with ws.connect() as cx:
        cx.execute("DELETE FROM cite_texts")
        cx.execute("UPDATE drafts SET cite_text_id=NULL")
    assert drafts.view(ws, did)["citations"]["citations"] == 8  # its page links it too


def test_each_citation_is_shown_on_the_claim_it_stands_for(project):
    from margin import drafts

    ws, _docs = project
    did = drafts.new_draft(ws, DRAFT)
    text = drafts.view(ws, did)["text"]
    # a claim right before its citation; one whose citation stands before it in the same sentence ("According to
    # X (2025), …"); one just after another sentence's citation (not its own); one with its citation inside
    drafts.add_claim(ws, did, *_span(text, "Hybrid workers commute fewer hours a week"))
    drafts.add_claim(ws, did, *_span(text, "loneliness rises among young employees."))
    drafts.add_claim(ws, did, *_span(text, "Costs fell"))
    drafts.add_claim(ws, did, *_span(text, "Mueller (2018) found that hybrid schedules reduce sick leave"))
    with ws.connect() as cx:  # the AI's guess said "not cited"; the citation found says otherwise
        cx.execute("UPDATE draft_claims SET cited=0")
    v = drafts.view(ws, did)
    hyb = _claim(v, "Hybrid workers")
    assert [r["raw"] for r in hyb["citations"]] == ["Verhoeven & Okafor, 2025"] and hyb["cited"] is True
    assert hyb["citations"][0]["group"] == "ready" and hyb["citations"][0]["text"] == "Not checked yet"
    assert [r["raw"] for r in _claim(v, "loneliness")["citations"]] == ["Lindqvist et al. (2025)"]
    assert [r["raw"] for r in _claim(v, "Costs fell")["citations"]] == ["Smith, 2019"]
    mueller = _claim(v, "Mueller")
    assert [r["raw"] for r in mueller["citations"]] == ["Mueller (2018)"]
    assert mueller["citations"][0]["group"] == "no_document"  # its work has no document in the project
    # every citation has its place in the draft, as written there
    for r in v["citations"]["refs"]:
        assert text[r["start"]:r["end"]] == r["marker"]
    c = v["citations"]
    assert c["text_id"] and c["citations"] == 8 and c["ready"] == 4 and c["has_bibliography"] is True
    assert c["blocked"] >= 2 and v["counts"]["cited"] == 4


def test_a_citation_never_goes_to_the_next_sentences_claim(project):
    from margin import drafts

    ws, _docs = project
    did = drafts.new_draft(ws, DRAFT)
    text = drafts.view(ws, did)["text"]
    # "… a week (Verhoeven & Okafor, 2025). Commuting emissions …": that citation is the sentence before's
    drafts.add_claim(ws, did, *_span(text, "Commuting emissions fall by a third"))
    c = drafts.view(ws, did)["claims"][0]
    assert [r["raw"] for r in c["citations"]] == ["Rivermouth Mobility Institute, 2024"]


# ---------------------------------------------------------------------------------------------
# checking a draft's citations
# ---------------------------------------------------------------------------------------------
def test_checking_a_drafts_citations(project):
    from margin import access, citations, drafts

    ws, docs = project
    did = drafts.new_draft(ws, DRAFT, "Chapter 2")
    text = drafts.view(ws, did)["text"]
    drafts.add_claim(ws, did, *_span(text, "Hybrid workers commute fewer hours a week"))
    drafts.add_claim(ws, did, *_span(text, "while productivity doubles"))
    tid = drafts.citation_text(ws, did)
    model = Reader()
    out = citations.check(ws, citations.plan(ws, tid), model, "claude-sonnet", k=8, per_doc=2)
    assert len(out["checked"]) == 4
    v = drafts.view(ws, did)
    hyb, prod = _claim(v, "Hybrid"), _claim(v, "while productivity")
    r = hyb["citations"][0]
    assert r["group"] == "accurate" and r["text"] == "Source accurate" and r["hyp_id"] and r["status"] == "supported"
    assert "Hybrid workers commute" in r["quote"]
    p = prod["citations"][0]
    assert p["group"] == "not_found" and p["text"] == "Not found in the source" and p["help"]
    assert v["citations"]["accurate"] == 2 and v["citations"]["notices"] == 2 and v["citations"]["ready"] == 0
    # the checks of a draft's citations stay its citations' (not its claims' checks, not among the Results)
    assert hyb["hyp_id"] is None and v["counts"]["checked"] == 0
    # the claims' table says what each claim's own source says
    rows = {row["Sentence in the draft"]: row for row in drafts.export_rows(ws, did)}
    assert rows["Hybrid workers commute fewer hours a week"]["Your citations"] == "Verhoeven & Okafor, 2025"
    assert rows["Hybrid workers commute fewer hours a week"]["What the cited source says"] == \
        "Verhoeven & Okafor, 2025: Source accurate"
    # a cloud model read them: recorded as the draft's (Claude has read part of it)
    assert access.draft_ledger(ws, did)["claims_read"] >= 4
    # removing the draft removes its citations and their checks
    drafts.delete(ws, did)
    assert not ws.scalar("SELECT COUNT(*) FROM cite_texts") and not ws.scalar("SELECT COUNT(*) FROM cite_refs")
    assert not ws.scalar("SELECT COUNT(*) FROM hypotheses WHERE origin='citation'")


def test_a_drafts_citations_keep_the_drafts_setting(project, monkeypatch):
    from margin import access, citations, drafts

    ws, _docs = project
    cloud, local = Reader(), Local()
    use_local_model(monkeypatch, local)
    did = drafts.new_draft(ws, PRIVATE_DRAFT, ai_access="local")
    tid = drafts.citation_text(ws, did)
    out = citations.check(ws, citations.plan(ws, tid), cloud, "claude-sonnet", k=8, per_doc=2)
    assert len(out["checked"]) == 2
    assert not any(SECRET.lower() in s.lower() for s in cloud.sent)  # nothing of the draft reached Claude
    assert not any("Hybrid workers commute fewer" in s for s in cloud.sent)
    assert set(out["checked"]) <= access.hidden_hypotheses(ws)  # never shown to a Claude chat
    with ws.connect() as cx:  # every task of them is the draft's, so the draft's rule applies to it too
        for (payload,) in cx.execute("SELECT payload_json FROM tasks WHERE payload_json LIKE '%citing%'"):
            assert access.draft_of(cx, json.loads(payload)) == did
    assert {r[0] for r in ws.query("SELECT access FROM tasks WHERE payload_json LIKE '%citing%'")} == {"local"}
    assert access.draft_ledger(ws, did)["times"] == 0


def test_a_new_setting_of_the_draft_reaches_its_citations_tasks_at_once(project):
    from margin import access, citations, drafts, tasks

    ws, _docs = project
    did = drafts.new_draft(ws, DRAFT, ai_access="cloud")
    tid = drafts.citation_text(ws, did)
    with tasks.queueing():  # prepared for Claude Code, not answered yet
        hids, errors = citations.queue(ws, citations.plan(ws, tid), None, expand=False, k=8, per_doc=2)
    assert len(hids) == 4 and not errors
    waiting = "SELECT access, queued FROM tasks WHERE kind='check' AND status IN ('pending', 'retry')"
    assert {(r[0], r[1]) for r in ws.query(waiting)} == {("cloud", 1)}
    assert not access.hidden_hypotheses(ws) & set(hids)
    drafts.update(ws, did, ai_access="none")  # changed on the draft page (or on Check citations: the same)
    assert {r[0] for r in ws.query(waiting)} == {"none"}
    assert set(hids) <= access.hidden_hypotheses(ws)


# ---------------------------------------------------------------------------------------------
# through the app
# ---------------------------------------------------------------------------------------------
def test_draft_citations_through_the_app(api, tmp_path, monkeypatch):  # noqa: F811
    from margin import home as core
    from margin.gui import server

    ws = core.create_project("P")
    _project(ws, tmp_path / "sources")
    reader = Reader()
    monkeypatch.setattr(server.App, "queue_mode", lambda self: False)
    monkeypatch.setattr(server.App, "backend", lambda self, kinds=None, k=None: (reader, "claude-sonnet"))
    # a draft added on Check a draft has its citations on its page, and in Check citations
    st, r = api("POST", "/api/projects/P/drafts", {"text": DRAFT, "title": "Chapter 2", "ai_access": "cloud"})
    assert st == 200, r
    did = r["draft"]["draft_id"]
    assert r["draft"]["citations"] == 7 and r["draft"]["cite_text_id"]
    v = api("GET", f"/api/projects/P/drafts/{did}")[1]
    tid = v["citations"]["text_id"]
    assert v["citations"]["ready"] == 4 and len(v["citations"]["refs"]) == 8
    texts = api("GET", "/api/projects/P/citations")[1]["texts"]
    assert [(t["text_id"], t["draft_id"]) for t in texts] == [(tid, did)]
    c = api("GET", f"/api/projects/P/citations/{tid}")[1]
    assert c["draft"] == {"draft_id": did, "title": "Chapter 2"}
    # checked from the draft page (the citations' own endpoint); the answers come back on the draft
    st, r = api("POST", f"/api/projects/P/citations/{tid}/check", {})
    assert st == 200 and r["job"]["kind"] == "citations" and r["job"]["scope"] == tid
    done = api.wait(r["job"]["id"], timeout=60)
    assert done["state"] == "done" and len(done["result"]["checked"]) == 4, done
    v = api("GET", f"/api/projects/P/drafts/{did}")[1]
    assert v["citations"]["accurate"] == 2 and v["citations"]["notices"] == 2
    # the name and setting from Check citations are the draft's
    st, c = api("PUT", f"/api/projects/P/citations/{tid}", {"title": "Chapter 2, v2", "ai_access": "local"})
    assert st == 200 and c["text"]["title"] == "Chapter 2, v2" and c["text"]["level"] == "local"
    d = api("GET", f"/api/projects/P/drafts/{did}")[1]["draft"]
    assert d["title"] == "Chapter 2, v2" and d["ai_access"] == "local"
    # a draft's citations are removed with the draft, not on their own
    st, r = api("DELETE", f"/api/projects/P/citations/{tid}", {})
    assert st == 409 and "remove the draft" in r["error"]
    # a text pasted on Check citations is kept as a draft; one without citations is not kept
    n = len(api("GET", "/api/projects/P/drafts")[1]["drafts"])
    st, c2 = api("POST", "/api/projects/P/citations", {"text": PRIVATE_DRAFT, "title": "Notes", "ai_access": "none"})
    assert st == 200 and c2["draft"]["title"] == "Notes"
    ds = api("GET", "/api/projects/P/drafts")[1]["drafts"]
    assert len(ds) == n + 1 and ds[0]["ai_access"] == "none" and ds[0]["cite_text_id"] == c2["text"]["text_id"]
    st, r = api("POST", "/api/projects/P/citations", {"text": "No citation in this text, only plain words here, and more."})
    assert st == 400 and "Check a draft" in r["error"]
    assert len(api("GET", "/api/projects/P/drafts")[1]["drafts"]) == n + 1
    # removing the draft removes its citations' checks
    assert api("DELETE", f"/api/projects/P/drafts/{did}", {})[0] == 200
    assert api("GET", f"/api/projects/P/citations/{tid}")[0] == 404
    assert not ws.scalar("SELECT COUNT(*) FROM hypotheses WHERE origin='citation' AND origin_id LIKE ?", (tid + "-%",))


# ---------------------------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------------------------
def test_the_page_files():
    from margin_static import section, sections

    js = (STATIC / "views" / "drafts.js").read_text(encoding="utf-8")
    for s in ("Check your citations against their sources", "Review every citation", "function citeBlock(c)",
              "Your citation", "Check this citation", '["cite_notice", "Citation to look at"]', "What it needs",
              '"citations"], (j) => j.scope === draftId', "/check`, body)", "class: `dcit dcit-"):
        assert s in js, s
    view = (STATIC / "views" / "citations.js").read_text(encoding="utf-8")
    for s in ("Back to your draft", "Open your draft", "Your text is kept as a draft", 'href: "#/drafts" }, "Check a draft")'):
        assert s in view, s
    features = (STATIC / "features.js").read_text(encoding="utf-8")
    assert 'section: "write", title: "Check citations"' in features
    order = sections()  # its section of margin.css: after the APA citations', before Margin's look
    assert order.index("m050") < order.index("m060") < order.index("m020")
    css = section("m060")
    assert ".dcit-bad" in css and ".dc-cites" in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", css)  # colour tokens only: light and dark both work
