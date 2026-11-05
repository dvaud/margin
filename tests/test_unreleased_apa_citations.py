"""Margin (unreleased): with a bibliography (Zotero, or an exported file), each document a draft's claim would cite
has its APA 7 in-text citation, ready to paste into the text: "(Verhoeven & Okafor, 2025)", the narrative form
"Verhoeven and Okafor (2025)", several works in one parenthesis, a and b for the same authors and year, as many names
as tell two "et al." apart, and the first words of the title for a work without an author. The tests never touch a
real Zotero."""
from __future__ import annotations

from pathlib import Path

from test_0130_bibliography import _library, zotero  # noqa: F401  (fixture)
from test_0133_zotero_titles import OFFICE, _with_draft
from test_app import api, home  # noqa: F401  (fixtures)

from margin import bibliography as b
from margin import drafts, ingest
from margin.llm import BaselineBackend

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"


def _a(*names):
    return [{"last": n, "first": "X.", "role": "author"} for n in names]


def _parts(*works):
    return b.apa_parts([{"key": str(i), **w} for i, w in enumerate(works)])


def test_one_two_and_more_authors():
    p = _parts({"creators": _a("Haugen"), "year": "2024", "title": "t"},
               {"creators": _a("Verhoeven", "Okafor"), "year": "2025", "title": "t"},
               {"creators": _a("Lindqvist", "Berg", "Moreau"), "year": "2025", "title": "t"},
               {"creators": [{"name": "World Health Organization", "role": "author"}], "year": "2022", "title": "t"})
    assert [p[k]["text"] for k in "0123"] == ["(Haugen, 2024)", "(Verhoeven & Okafor, 2025)", "(Lindqvist et al., 2025)",
                                              "(World Health Organization, 2022)"]
    assert [p[k]["narrative"] for k in "0123"] == ["Haugen (2024)", "Verhoeven and Okafor (2025)",
                                                   "Lindqvist et al. (2025)", "World Health Organization (2022)"]
    assert p["1"]["html"] == "(Verhoeven &amp; Okafor, 2025)"


def test_no_date_editors_and_translators():
    p = _parts({"creators": _a("Haugen"), "year": None, "title": "t"},
               {"creators": [{"last": "Kim", "role": "editor"}, {"last": "Park", "role": "editor"}], "year": "2019",
                "title": "t"},
               {"creators": [{"last": "Freud", "role": "author"}, {"last": "Strachey", "role": "translator"}],
                "year": "1955", "title": "t"},
               {"creators": [{"last": "Byrne", "role": "contributor"}], "year": "2020", "title": "t"})
    # editors stand in for missing authors ("Ed." is left out of the citation); a translator is never cited
    assert [p[k]["text"] for k in "0123"] == ["(Haugen, n.d.)", "(Kim & Park, 2019)", "(Freud, 1955)", "(Byrne, 2020)"]


def test_the_same_authors_and_year_get_letters_in_the_order_of_the_titles():
    p = _parts({"creators": _a("Haugen"), "year": "2024", "title": "The second study"},
               {"creators": _a("Haugen"), "year": "2024", "title": "A first look"},
               {"creators": _a("Haugen"), "year": "2023", "title": "Another year"},
               {"creators": _a("Haugen"), "year": "", "title": "B"}, {"creators": _a("Haugen"), "year": "", "title": "A"})
    # leading articles do not count: "first look" before "second study"
    assert [p[k]["text"] for k in "01234"] == ["(Haugen, 2024b)", "(Haugen, 2024a)", "(Haugen, 2023)",
                                               "(Haugen, n.d.-b)", "(Haugen, n.d.-a)"]


def test_et_al_that_would_read_the_same_names_as_many_authors_as_needed():
    p = _parts({"creators": _a("Kapoor", "Bloom", "Montez", "Ruiz", "Ito"), "year": "2017", "title": "a"},
               {"creators": _a("Kapoor", "Bloom", "Zucker", "Ruiz", "Ito"), "year": "2017", "title": "b"},
               {"creators": _a("Kapoor", "Bloom", "Zhang"), "year": "2017", "title": "c"},
               {"creators": _a("Kapoor", "Lee", "Park"), "year": "2018", "title": "d"})
    assert p["0"]["text"] == "(Kapoor, Bloom, Montez, et al., 2017)"
    assert p["1"]["text"] == "(Kapoor, Bloom, Zucker, et al., 2017)"
    # "et al." never stands for one name: all three are written
    assert p["2"]["text"] == "(Kapoor, Bloom, & Zhang, 2017)" and p["2"]["narrative"] == "Kapoor, Bloom, and Zhang (2017)"
    assert p["3"]["text"] == "(Kapoor et al., 2018)"  # another year: nothing to tell apart


def test_a_work_without_an_author_is_cited_by_its_title():
    p = _parts({"creators": [], "year": "2020", "title": "study finds water stress rising in arid regions: a survey",
                "type": "newspaperArticle"},
               {"creators": [], "year": "2021", "title": "The hydrogen handbook", "type": "book"},
               {"creators": [], "year": "", "title": "", "type": "book"})
    # part of something: in quotation marks, the comma inside them; a whole: in italics; title case, five words at most
    assert p["0"]["text"] == "(“Study Finds Water Stress Rising,” 2020)"
    assert p["0"]["narrative"] == "“Study Finds Water Stress Rising” (2020)"
    assert p["1"]["text"] == "(The Hydrogen Handbook, 2021)" and p["1"]["html"] == "(<i>The Hydrogen Handbook</i>, 2021)"
    assert "2" not in p  # nothing to cite it by


def test_several_works_in_one_parenthesis():
    p = _parts({"creators": _a("Verhoeven", "Okafor"), "year": "2025", "title": "t"},
               {"creators": _a("Haugen"), "year": "2024", "title": "t"},
               {"creators": _a("Haugen"), "year": "2023", "title": "t"},
               {"creators": _a("Haugen"), "year": "", "title": "t"},
               {"creators": [], "year": "2020", "title": "Water stress", "type": "webpage"})
    both = b.apa_together([p["0"], p["1"], p["2"], p["3"], p["4"], p["1"], None])
    # by author, the years of one author after one name (no date first), the same work once
    assert both["text"] == "(Haugen, n.d., 2023, 2024; Verhoeven & Okafor, 2025; “Water Stress,” 2020)"
    assert both["count"] == 5
    assert b.apa_together([]) is None and b.apa_together([None]) is None


def _checked_draft(ws, zotero, tmp_path):  # noqa: F811
    docs = _with_draft(tmp_path / "docs")
    _library(zotero, tmp_path / "Zotero" / "storage", docs / "download (3).pdf")
    ingest.ingest(ws, [docs], ai_access="cloud")
    did = drafts.new_draft(ws, "Working in an office again.\n\nShared office days strengthen ties between colleagues "
                               "and informal learning, as several studies found.\n")
    cid = drafts.add_claim(ws, did, 28, 116, "Shared office days strengthen ties between colleagues and informal "
                                             "learning.")
    drafts.check_claims(ws, did, BaselineBackend(), "baseline", claim_ids=[cid], k=5)
    return did, cid


def _office(v, cid):
    c = next(c for c in v["claims"] if c["claim_id"] == cid)
    return c, next(e for side in c["evidence"].values() for e in side if e["title"] == OFFICE)


def test_a_draft_shows_the_citation_of_each_document_linked_to_zotero(zotero, ws, tmp_path):  # noqa: F811
    did, cid = _checked_draft(ws, zotero, tmp_path)
    # without a bibliography: nothing to cite by, and the page says nothing about it
    v = drafts.view(ws, did)
    assert v["bibliography"] is False
    c = v["claims"][0]
    assert c["cite"] == {} and all(e["apa"] is None for side in c["evidence"].values() for e in side)

    works, src = b.pull_zotero("user")
    b.save(ws, works, src)
    v = drafts.view(ws, did)
    assert v["bibliography"] is True
    c, doc = _office(v, cid)
    assert doc["apa"]["text"] == "(Moreau, 2023)" and doc["apa"]["narrative"] == "Moreau (2023)"
    side = next(k for k, docs in c["evidence"].items() if doc in docs)
    assert "(Moreau, 2023" in c["cite"][side]["text"]
    assert c["cite"][side]["missing"] == sum(1 for e in c["evidence"][side] if not e["apa"])

    # the export: the citation of the side the person decided on (the supporting documents otherwise)
    drafts.update_claim(ws, did, cid, decision="supported")
    row = drafts.export_rows(ws, did)[0]
    assert row["Citation (APA 7)"] == (c["cite"].get("supports") or {}).get("text", "")

    # the link taken back on the Bibliography page: no citation for it any more
    with ws.connect() as cx:
        cx.execute("UPDATE bib_links SET status='rejected' WHERE doc_id=?", (doc["doc_id"],))
    assert _office(drafts.view(ws, did), cid)[1]["apa"] is None


def test_the_draft_api_carries_the_citations(api, zotero, tmp_path):  # noqa: F811
    from margin import home as core

    ws = core.create_project("T")
    did, cid = _checked_draft(ws, zotero, tmp_path)
    r = api("POST", "/api/projects/T/bibliography", {"zotero": {"library": "user", "collection": None}})[1]
    assert api.wait(r["job"]["id"])["state"] == "done"
    st, v = api("GET", f"/api/projects/T/drafts/{did}")
    assert st == 200 and v["bibliography"] is True
    assert _office(v, cid)[1]["apa"]["text"] == "(Moreau, 2023)"


def test_the_page_copies_the_citation():
    js = (STATIC / "views" / "drafts.js").read_text()
    # a button per document to cite, and one for all of them on a folded card
    assert "e.apa ? apaButton(e.apa) : null" in js and "apaButton(all, { all: true })" in js
    assert 'toast(`Copied ${text}. Paste it into your text.`' in js
    # plain text (it takes the font of the text it goes into); HTML only for a title in italics
    assert 'html && html.includes("<i>") && window.ClipboardItem' in js and 'document.execCommand("copy")' in js
    assert "ALT_CLICK" in js and "cite.narrative" in js
    # documents of the side without a work of the bibliography are named, with the way to link them
    assert 'h("a", { href: "#/bibliography" }, "Bibliography")' in js
    index = (STATIC / "index.html").read_text()
    assert index.index("/static/unreleased.css") < index.index("/static/m020.css")
    css = (STATIC / "unreleased.css").read_text()
    assert ".dc-apa:hover" in css and not __import__("re").search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", css)
