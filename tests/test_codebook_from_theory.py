"""0.18.1 (roadmap K2 part 2, Part A, A4): a codebook from a theory document, Level 0 (no model).

The candidate concepts come from the theory's own structure and words (terms it defines, its headings, its frequent
phrases), each with a definition quoted from it with its page; examples come only from the evidence documents and are
kept only when ticked; the result is an ordinary codebook."""
from __future__ import annotations

import pytest

from margin import codebooks, docrole, ingest, pdfmake, theorycodes
from margin.store import Workspace

THEORY_PAGES = [
    ["1. Stocks and flows",
     "A stock is the memory of the history of changing flows within the system. Stocks change only through flows.",
     "A flow is the rate at which a stock is filled or drained. Flows can be seen as actions or decisions."],
    ["2. Feedback",
     "By a reinforcing loop we mean a loop that amplifies whatever happens in it. A reinforcing loop can make "
     "a stock grow faster the larger it already is.",
     "A balancing loop is defined as a loop that keeps a stock near a goal. A delay in a balancing loop makes a "
     "system overshoot. The delay matters, and every delay in a balancing loop is worth looking for."],
    ["3. Leverage points",
     "Leverage points refer to places in a system where a small shift produces large changes in everything. "
     "Leverage points are seldom where people look for them. A delay hides the effect of a shift for a while."],
]
EVIDENCE = ("Staff interviews in the care home\n\n"
            "The staff said that when a resident failed at the game once, they switched it on less, and so the "
            "resident grew less sure of it: a reinforcing loop nobody had planned.\n\n"
            "A delay between ordering the table and its delivery meant that the team lost interest before it "
            "arrived. Managers kept a balancing loop going by asking each week how often it was used.\n")


def _theory_pdf(path) -> None:
    """The theory as a PDF of three pages: a bold heading on each, then its paragraphs (pdfmake)."""
    pages = []
    for n, (head, *paras) in enumerate(THEORY_PAGES):
        pg = pdfmake.Page()
        y = 770
        if n == 0:
            pg.text("Thinking in systems", 72, y, "Helvetica-Bold", 18)
            y -= 36
        pg.text(head, 72, y, "Helvetica-Bold", 13)
        y -= 26
        for para in paras:
            for line in pdfmake.wrap(para, 451, "Times-Roman", 11):
                pg.text(line, 72, y, "Times-Roman", 11)
                y -= 14
            y -= 10
        pages.append(pg)
    pdfmake.write(pages, path, title="Thinking in systems")


@pytest.fixture
def project(tmp_path):
    ws = Workspace.create(tmp_path / "proj")
    d = tmp_path / "docs"
    d.mkdir()
    _theory_pdf(d / "meadows.pdf")
    (d / "carehome.txt").write_text(EVIDENCE, encoding="utf-8")
    ingest.ingest(ws, [d])
    theory = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%memory of the history%'")
    evidence = ws.scalar("SELECT doc_id FROM documents WHERE doc_id != ?", (theory,))
    docrole.set_role(ws, theory, "theory")
    yield ws, theory, evidence
    ws.close_all()


def _by_term(cands: dict) -> dict[str, dict]:
    return {c["term"].lower(): c for c in cands["concepts"]}


def test_defined_terms_come_first_with_their_definition_quoted_from_the_theory(project):
    ws, theory, _ev = project
    cands = theorycodes.candidates(ws, theory)
    got = _by_term(cands)
    for term in ("stock", "flow", "reinforcing loop", "balancing loop", "leverage points"):
        assert term in got, (term, sorted(got))
        assert got[term]["how"] == "defined", (term, got[term]["how"])
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (theory,))
    for term in ("stock", "balancing loop", "reinforcing loop"):
        d = got[term]["definition"]
        assert d and " ".join(text[d["start"]:d["end"]].split()) == d["quote"]    # quote-checked: the document's words
        assert d["quote"] in got[term]["code"]["description"]
        assert "Thinking in systems" in got[term]["code"]["description"]
    defined = [c["how"] for c in cands["concepts"]]
    assert defined[:5] == ["defined"] * 5                                         # best first


def test_a_definition_carries_its_page(project):
    ws, theory, _ev = project
    if ws.scalar("SELECT kind FROM documents WHERE doc_id=?", (theory,)) != "pdf":
        pytest.skip("the theory was written as text: it has no pages")
    got = _by_term(theorycodes.candidates(ws, theory))
    assert got["stock"]["definition"]["page"] == 1
    assert got["balancing loop"]["definition"]["page"] == 2
    assert ", p. 2)" in got["balancing loop"]["code"]["description"]


def test_headings_and_frequent_phrases_are_offered_too(project):
    ws, theory, _ev = project
    got = _by_term(theorycodes.candidates(ws, theory))
    hows = {c["how"] for c in got.values()}
    assert "delay" in got                       # frequent (in three sentences), never defined
    assert hows <= {"defined", "heading", "frequent"}
    assert not any(t in got for t in ("the", "is", "a stock is"))


def test_examples_are_offered_only_from_the_evidence_and_start_unticked(project):
    ws, theory, ev = project
    got = _by_term(theorycodes.candidates(ws, theory))
    sug = got["reinforcing loop"]["suggested"]
    assert sug and {e["doc_id"] for e in sug} == {ev}
    assert all("reinforcing loop" in e["quote"].lower() for e in sug)
    assert all(not c["code"]["examples"] for c in got.values())                 # none kept until ticked


def test_the_ticked_concepts_become_an_ordinary_codebook_without_theory_examples(project):
    ws, theory, ev = project
    got = _by_term(theorycodes.candidates(ws, theory))
    keep = []
    for term in ("reinforcing loop", "balancing loop", "delay"):
        c = dict(got[term]["code"])
        c["examples"] = list(got[term]["suggested"][:1])
        keep.append(c)
    # an example from the theory, smuggled in, is dropped
    keep[2]["examples"].append({"quote": "The delay matters", "doc_id": theory, "title": "Thinking in systems",
                                "page": 2, "start": 0, "end": 17})
    cb = codebooks.create(ws, "systems", "Systems codes", start="theory", source={"codes": keep, "doc_id": theory})
    codes = {c["code"]: c for c in cb["codes"]}
    assert set(codes) == {"Reinforcing loop", "Balancing loop", "Delay"}
    assert all(e["doc_id"] == ev for c in codes.values() for e in c["examples"])
    assert "Thinking in systems" in codes["Balancing loop"]["description"]
    log = ws.query("SELECT text FROM research_log WHERE kind='codebook-added'")
    assert log and "3 concepts of the theory document" in log[0][0]
    with pytest.raises(ValueError):
        codebooks.create(ws, "empty", "Nothing", start="theory", source={"codes": [], "doc_id": theory})


SECOND_THEORY = ("Practice theory\n\n"
                 "A practice is a routinised way in which bodies move, objects are handled and the world is "
                 "understood. A delay is the time a practice needs before a new tool becomes part of its routine.\n")


def test_a_codebook_from_several_theory_documents(project, tmp_path):
    """0.19: the concepts of several theories in one codebook, a group of codes for each document, the log naming
    them all; an example never comes from any of the chosen documents, even one not marked as theory."""
    ws, meadows, ev = project
    d = tmp_path / "more"
    d.mkdir()
    (d / "practice.txt").write_text(SECOND_THEORY, encoding="utf-8")
    ingest.ingest(ws, [d])
    practice = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%routinised way%'")
    a, b = _by_term(theorycodes.candidates(ws, meadows)), _by_term(theorycodes.candidates(ws, practice))
    assert a["delay"]["code"]["source_doc"] == meadows and b["delay"]["code"]["source_doc"] == practice
    # the editor gives both "Delay"s their document's title (pickTheory), as here
    keep = [dict(a["stock"]["code"]), {**a["delay"]["code"], "code": "Delay (Thinking in systems)"},
            dict(b["practice"]["code"]), {**b["delay"]["code"], "code": "Delay (Practice theory)"}]
    # a sentence of the other chosen theory, offered as an example, is dropped (it is not marked as theory)
    keep[0]["examples"] = [{"quote": "A practice is a routinised way", "doc_id": practice, "title": "Practice theory"}]
    cb = codebooks.create(ws, "lenses", "Two lenses", start="theory",
                          source={"codes": keep, "doc_ids": [meadows, practice]})
    codes = {c["code"]: c for c in cb["codes"]}
    assert set(codes) == {"Stock", "Delay (Thinking in systems)", "Practice", "Delay (Practice theory)"}
    assert codes["Stock"]["examples"] == []
    groups = {g["group"]: g["group_name"] for g in cb["groups"]}
    assert codes["Stock"]["group"] == codes["Delay (Thinking in systems)"]["group"] != codes["Practice"]["group"]
    assert groups[codes["Practice"]["group"]] == "Practice theory"
    assert "Thinking in systems" in groups[codes["Stock"]["group"]]
    log = ws.query("SELECT text FROM research_log WHERE kind='codebook-added'")[0][0]
    assert "4 concepts of 2 theory documents" in log and "Practice theory" in log and "Thinking in systems" in log
    # two ticked but concepts kept from one: no groups, and the log names only the document they come from
    one = codebooks.create(ws, "one", "One lens", start="theory",
                           source={"codes": keep[2:3], "doc_ids": [meadows, practice]})
    assert {c["group"] for c in one["codes"]} == {""}
    log = ws.query("SELECT text FROM research_log WHERE kind='codebook-added' AND subject_id='one'")[0][0]
    assert "of the theory document “Practice theory”" in log and "Thinking in systems" not in log
    with pytest.raises(ValueError):
        codebooks.create(ws, "bad", "Bad", start="theory", source={"codes": keep[2:3], "doc_ids": practice})


def test_the_routes(api, tmp_path):  # noqa: F811
    from margin import home

    assert api("POST", "/api/projects", {"name": "Lens"})[0] == 200
    d = tmp_path / "in"
    d.mkdir()
    (d / "meadows.txt").write_text("Thinking in systems\n\n" + "\n\n".join("\n\n".join(p) for p in THEORY_PAGES),
                                   encoding="utf-8")
    (d / "carehome.txt").write_text(EVIDENCE, encoding="utf-8")
    ws = Workspace.open(home.project_path("Lens"))
    try:
        ingest.ingest(ws, [d])
        theory = ws.scalar("SELECT doc_id FROM documents WHERE text LIKE '%memory of the history%'")
        docrole.set_role(ws, theory, "theory")
    finally:
        ws.close_all()
    st, body = api("GET", "/api/projects/Lens/codebook-theory")
    assert st == 200 and body["documents"][0] == {"doc_id": theory, "title": body["documents"][0]["title"], "theory": True}
    st, body = api("GET", f"/api/projects/Lens/codebook-theory/{theory}")
    assert st == 200 and body["concepts"] and body["role"] == "theory"
    assert api("GET", "/api/projects/Lens/codebook-theory/nope")[0] == 404


# ---- a book, not a few pages: its glossary, and what is not the theory's own prose ---------------------------------
_PLACES = ("mill", "ferry", "orchard", "quarry", "harbour", "market", "chapel", "smithy", "tannery", "bakery")
_FOLK = ("carters", "weavers", "millers", "shepherds", "masons", "coopers", "fishers", "tailors")


def _filler(n: int, word: str) -> list[str]:
    """`n` paragraphs that define nothing, no two alike."""
    return [f"The {word} at the {_PLACES[i % 10]} went on as before among the {_FOLK[(i // 10) % 8]}. Nobody wrote "
            f"about what happened that season." for i in range(n)]


def _page(n: int, *paras: str) -> list[str]:
    """A page as a book's file often holds it: a running head first, a printer's mark last."""
    return ["THINKING IN SYSTEMS", *paras, f"TIS final pgs {n} 5/2/09 10:37:{n:02d}"]


BOOK = "\n\n".join(sum([
    ["Thinking in systems", "Contents", "1.1 The basics 3 1.2 Feedback 9 1.3 Traps 21", "Glossary 40"],
    _page(1, "1. The basics",
          "A stock is the memory of the history of changing flows within the system. Stocks change only through flows.",
          "All it takes is a click in the mind. Say you are a young boy who wants to grow up. This behavior is an "
          "example of how a stock changes.",
          "A tree is a system. Its inflow is the growth of the trees."),
    _page(2, *_filler(12, "work")),
    _page(3, "2. Feedback and Delays",
          "A feedback loop is a closed chain of causal connections from a stock and back again to the stock.",
          "Feedback loops can hold a stock near a goal. Without a feedback loop a stock drifts. Every feedback loop "
          "takes time to act.",
          "Delays are everywhere in systems. A delay in a feedback loop makes a system overshoot its goal."),
    _page(4, *_filler(12, "trade")),
    _page(5, "3. Policy Resistance—Fixes that Fail",
          "Policy resistance comes from the different goals of the actors in a system. When policy resistance is "
          "strong, everybody pulls hard and the stock stays where nobody wants it.",
          "Inflow: heating = discrepancy x 10%",
          "The way out of policy resistance is to let go."),
    _page(6, *_filler(12, "craft")),
    _page(7, "Glossary",
          "Feedback loop: The mechanism that allows a change in a stock to affect a flow into or out of that same stock.",
          "Resilience: The ability of a system to recover from perturbation. Stock: An accumulation of material or "
          "information that has built up in a system over time.",
          "Suboptimization: The behavior resulting from a subsystem’s goals dominating at the expense of the total "
          "system’s goals."),
    ["Summary of principles", "Resilience keeps a system going when it is hit, and a system without resilience breaks. "
     "Suboptimization is what happens when a part wins and the whole loses."],
], [])) + "\n"


@pytest.fixture
def book(tmp_path):
    ws = Workspace.create(tmp_path / "proj")
    d = tmp_path / "docs"
    d.mkdir()
    (d / "book.txt").write_text(BOOK, encoding="utf-8")
    ingest.ingest(ws, [d])
    doc = ws.scalar("SELECT doc_id FROM documents")
    docrole.set_role(ws, doc, "theory")
    yield ws, doc
    ws.close_all()


def test_the_entries_of_the_documents_own_glossary_come_first_and_only_they_are_ticked(book):
    ws, doc = book
    cands = theorycodes.candidates(ws, doc)
    got = _by_term(cands)
    assert [c["term"] for c in cands["concepts"]][:4] == ["Stock", "Feedback loop", "Resilience", "Suboptimization"]
    assert all(got[t]["how"] == "glossary" and got[t]["ticked"] for t in ("stock", "feedback loop", "resilience"))
    # the definition is the entry's own, quoted from the glossary (not the first sentence that uses the word), and an
    # entry that shares a line with the one before it ("… perturbation. Stock: An accumulation …") is found too
    assert got["stock"]["definition"]["quote"] == ("An accumulation of material or information that has built up in a "
                                                   "system over time.")
    assert got["resilience"]["definition"]["quote"] == "The ability of a system to recover from perturbation."
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (doc,))
    for c in cands["concepts"]:
        d = c["definition"]
        assert d and " ".join(text[d["start"]:d["end"]].split()) == d["quote"], c["term"]   # the document's words
    # a document that says itself which its concepts are: nothing else is ticked
    assert {c["term"] for c in cands["concepts"] if c["ticked"]} == {"Stock", "Feedback loop", "Resilience",
                                                                    "Suboptimization"}
    assert "policy resistance" in got and not got["policy resistance"]["ticked"]


def test_what_is_not_the_theorys_prose_is_never_a_concept(book):
    ws, doc = book
    got = _by_term(theorycodes.candidates(ws, doc))
    # a sentence that only starts like a definition ("All it takes is a …", "Say you are a …", "This behavior is an
    # …", "Its inflow is the …"), and an example the text calls a system once ("A tree is a system")
    assert not {"takes", "say", "behavior", "inflow", "tree", "click"} & set(got)
    # running heads and printer's marks (the same line on page after page, numbers aside), the table of contents, a
    # model's equations
    words = {w for t in got for w in t.split()}
    assert not {"thinking", "tis", "pgs", "final", "heating", "discrepancy", "traps", "contents"} & words
    for c in got.values():
        q = c["definition"]["quote"]
        assert "TIS final" not in q and "THINKING IN SYSTEMS" not in q and " = " not in q and "1.2" not in q, q


BOOK_PAGES = [
    ["Resilience, Self-Organization, and Hierarchy",
     "Resilience keeps a system working when it is hit. Self-organization lets a system make new structure of its "
     "own. Hierarchy arranges systems inside larger systems.",
     "A system needs resilience more than it needs speed, and self-organization more than order. Hierarchy serves "
     "the parts when it works well."],
    ["A: Growth",
     "The first panel shows growth over a hundred years, and the second panel shows what follows it."],
    ["The content and structure of the book",
     "The content of the chapters follows the order of the lectures, and the structure of the book is plain."],
    ["Policy Resistance—Fixes that Fail",
     "Policy resistance comes from the different goals of the actors. The way out of policy resistance is to let go."],
]


def test_a_headings_terms_are_offered_one_by_one_and_a_label_or_a_phrase_is_not(tmp_path):
    ws = Workspace.create(tmp_path / "proj")
    try:
        d = tmp_path / "docs"
        d.mkdir()
        pages = []
        for head, *paras in BOOK_PAGES:
            pg = pdfmake.Page()
            pg.text(head, 72, 770, "Helvetica-Bold", 13)
            y = 744
            for para in paras:
                for line in pdfmake.wrap(para, 451, "Times-Roman", 11):
                    pg.text(line, 72, y, "Times-Roman", 11)
                    y -= 14
                y -= 10
            pages.append(pg)
        pdfmake.write(pages, d / "book.pdf", title="A book")
        ingest.ingest(ws, [d])
        doc = ws.scalar("SELECT doc_id FROM documents")
        heads = [r[0] for r in ws.query("SELECT text FROM headings WHERE doc_id=?", (doc,))]
        if "Resilience, Self-Organization, and Hierarchy" not in heads:
            pytest.skip("the reader did not find the headings")
        got = _by_term(theorycodes.candidates(ws, doc))
        # "Resilience, Self-Organization, and Hierarchy": three terms; "Policy Resistance—Fixes that Fail": the term
        for t in ("resilience", "self-organization", "hierarchy", "policy resistance"):
            assert t in got and got[t]["how"] in ("heading", "defined"), (t, sorted(got))
        assert got["policy resistance"]["definition"]["quote"].startswith("Policy resistance comes from")
        # a figure's panel ("A: Growth") and a heading that is a phrase, not a list of terms, give none
        assert not any(c["how"] == "heading" and c["term"].lower() in ("growth", "content", "structure of the book",
                                                                      "content and structure of the book")
                       for c in got.values())
    finally:
        ws.close_all()


def _one_text(tmp_path, text: str):
    ws = Workspace.create(tmp_path / "proj")
    d = tmp_path / "docs"
    d.mkdir()
    (d / "theory.txt").write_text(text, encoding="utf-8")
    ingest.ingest(ws, [d])
    return ws, ws.scalar("SELECT doc_id FROM documents")


def test_a_paragraph_with_figures_or_a_formula_in_it_is_still_prose(tmp_path):
    """Only a line of a table of contents or of a model's equations is left out: a paragraph that says "from 2.5 to
    3.7 percent" or "with r = 0.02" is the theory's prose, and what it defines is found."""
    ws, doc = _one_text(tmp_path, "Growth and limits\n\n"
                        "A doubling time is the time a stock needs to grow to twice its size. When the birth rate "
                        "rose from 2.5 to 3.7 percent, the doubling time fell from 28 to 19 years.\n\n"
                        "A carrying capacity is the largest population a place can keep, and with r = 0.02 the stock "
                        "reaches the carrying capacity within a lifetime.\n\n"
                        "1.1 Growth 3 1.2 Limits 9\n\n"
                        "Inflow: births = population x fertility\n")
    try:
        got = _by_term(theorycodes.candidates(ws, doc))
        assert got["doubling time"]["definition"]["quote"].startswith("A doubling time is the time a stock needs")
        assert got["carrying capacity"]["definition"]["quote"].startswith("A carrying capacity is the largest")
        assert not {"fertility", "births"} & {w for t in got for w in t.split()}       # the equation is not prose
        # and the AI is sent both paragraphs
        sent = " ".join(p["text"] for part in theorycodes.ai_payloads(ws, doc) for p in part["passages"])
        assert "from 2.5 to 3.7 percent" in sent and "with r = 0.02" in sent
    finally:
        ws.close_all()


def test_a_glossary_entry_too_short_to_define_anything_is_left_out_not_added_to_the_one_before(tmp_path):
    ws, doc = _one_text(tmp_path, "A primer\n\nGlossary\n\n"
                        "Flow: Material or information that enters or leaves a stock over a period of time.\n\n"
                        "Stock: An accumulation.\n\n"
                        "Delay: The time between a change and its effect on the stock it changes.\n\n"
                        "Feedback loop: A closed chain of causal connections from a stock and back to it.\n\n"
                        "Hierarchy: Systems organized in such a way as to create a larger system.\n")
    try:
        cands = theorycodes.candidates(ws, doc)
        if not any(c["how"] == "glossary" for c in cands["concepts"]):
            pytest.skip("the reader did not find the glossary's heading")
        got = _by_term(cands)
        assert got["flow"]["definition"]["quote"] == ("Material or information that enters or leaves a stock over a "
                                                     "period of time.")
        assert got["delay"]["how"] == "glossary" and got["hierarchy"]["how"] == "glossary"
        assert "stock" not in got or got["stock"]["how"] != "glossary"
    finally:
        ws.close_all()


def test_a_term_named_with_we_call_this_ends_where_the_sentence_goes_on(tmp_path):
    ws, doc = _one_text(tmp_path, "Loops\n\n"
                        "Growth feeds more growth. We call this a reinforcing loop because it grows on itself. "
                        "A reinforcing loop runs until something stops it.\n")
    try:
        got = _by_term(theorycodes.candidates(ws, doc))
        assert got["reinforcing loop"]["how"] == "defined", sorted(got)
        assert not any("because" in t for t in got)
    finally:
        ws.close_all()


def test_words_of_any_script_are_words(tmp_path):
    """Hungarian "ő" and "ű" lie outside Latin-1: a term with them is found whole (it was cut at the letter)."""
    ws, doc = _one_text(tmp_path, "Rendszerek\n\n"
                        "A visszacsatolási hurok is a closed chain of causes. Every visszacsatolási hurok takes time. "
                        "A késleltetés is the time a visszacsatolási hurok needs. The erőforrás is a stock, and "
                        "the erőforrás of a művelődési ház is its people.\n")
    try:
        got = _by_term(theorycodes.candidates(ws, doc))
        assert "visszacsatolási hurok" in got and "késleltetés" in got, sorted(got)
        assert not any(t in got for t in ("er", "forrás", "m", "vel", "dési"))
    finally:
        ws.close_all()


from test_app import api, home  # noqa: E402,F401  (fixtures)
