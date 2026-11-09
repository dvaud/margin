"""Roadmap C: an outline from the corpus's themes, with no AI.

C1: each theme of a run becomes a section (key terms, best passages, documents to cite with APA citations, codes and
concepts) in an order that reads as a path (themes that share documents and key terms are neighbours); sections are
moved, nested, merged, split, renamed and added; each shows disagreement (from the checks), gaps and the person's
decisions; the outline is stored in the project and outlives its themes.
C2: beside a draft, how much of each section it covers and what is unused; by meaning only with a local embedding
model that is already built.
C3: Markdown and Word (.docx written with zipfile)."""
from __future__ import annotations

import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.dom import minidom

import pytest

from test_0_14_0_remove_themes import TOPICS, topic_of, topics_corpus
from test_app import api, home  # noqa: F401  (fixtures)

from margin import claimcheck, drafts, ingest, outline, themes
from margin.llm import BaselineBackend
from margin.store import Workspace

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "margin" / "gui" / "static"


@pytest.fixture
def project(home, tmp_path):
    ws = home.create_project("T")
    ingest.ingest(ws, [topics_corpus(tmp_path / "topics")])
    return ws


@pytest.fixture
def run(project):
    return themes.run(project, k=6, seed=0, mode="words")


def _flat(v):
    out = []

    def walk(ns):
        for n in ns:
            out.append(n)
            walk(n["children"])
    walk(v["sections"])
    return out


def _titles(ws, oid):
    return [(n["number"], n["title"]) for n in _flat(outline.view(ws, oid))]


def _own(ws, oid, title):
    return outline.add_section(ws, oid, title)


# ---------------------------------------------------------------------------------------------
# the order
# ---------------------------------------------------------------------------------------------
def _item(docs, words):
    return {"docs": Counter(docs), "words": set(words.split())}


def test_themes_that_share_documents_and_terms_are_neighbours():
    items = {1: _item({"a": 9, "b": 4}, "water brine aquifer"), 2: _item({"c": 8, "d": 3}, "wages unions skills"),
             3: _item({"a": 5, "b": 5}, "water aquifer desalination"), 4: _item({"c": 4, "d": 6}, "wages payroll skills"),
             5: _item({"z": 3}, "birds nesting")}
    order = outline.similarity_order(items)
    assert sorted(order) == [1, 2, 3, 4, 5]
    pos = {k: i for i, k in enumerate(order)}
    assert abs(pos[1] - pos[3]) == 1 and abs(pos[2] - pos[4]) == 1
    assert order[0] == 1                       # it starts with the theme that has most passages
    assert outline.similarity_order(items) == order     # the same input, the same order
    assert outline.similarity_order({}) == [] and outline.similarity_order({7: _item({"a": 1}, "x")}) == [7]


def test_two_opt_never_makes_the_path_worse():
    import random

    rng = random.Random(3)
    words = "alpha beta gamma delta epsilon zeta eta theta iota kappa".split()
    items = {i: _item({f"d{rng.randrange(6)}": rng.randrange(1, 9), f"d{rng.randrange(6)}": rng.randrange(1, 9)},
                      " ".join(rng.sample(words, 3))) for i in range(14)}
    order = outline.similarity_order(items)

    def total(o):
        return sum(outline.pair_similarity(items[a], items[b]) for a, b in zip(o, o[1:]))
    greedy = [sorted(items, key=lambda k: (-sum(items[k]["docs"].values()), str(k)))[0]]
    left = [k for k in items if k != greedy[0]]
    while left:
        nxt = max(left, key=lambda k: outline.pair_similarity(items[greedy[-1]], items[k]))
        greedy.append(nxt)
        left.remove(nxt)
    assert total(order) >= total(greedy) - 1e-9 and sorted(order) == sorted(items)


# ---------------------------------------------------------------------------------------------
# C1: the outline
# ---------------------------------------------------------------------------------------------
def test_an_outline_has_a_section_for_each_theme_with_what_to_write(project, run):
    v0 = themes.view(project, run)
    oid = outline.create(project, run)
    v = outline.view(project, oid)
    secs = v["sections"]
    assert len(secs) == len(v0["themes"]) and [s["number"] for s in secs] == [str(i) for i in range(1, len(secs) + 1)]
    assert sorted(t["theme_id"] for s in secs for t in s["themes"]) == sorted(t["theme_id"] for t in v0["themes"])
    by_theme = {t["theme_id"]: t for t in v0["themes"]}
    for s in secs:
        t = by_theme[s["themes"][0]["theme_id"]]
        assert s["passages"] == t["size"] and s["documents"] == len(t["documents"])
        assert s["terms"] == t["terms"][:12] and s["title_source"] == "terms" and s["title"] and s["state"] == "shown"
        reps = s["representatives"]
        assert 1 <= len(reps) <= outline.REPS and len({r["doc_id"] for r in reps}) == min(len(reps), s["documents"])
        assert all(r["text"] and r["title"] and r["location"] for r in reps)
        assert {d["doc_id"] for d in s["sources"]} == {d["doc_id"] for d in t["documents"]}
        assert s["codes"] is None and s["disagreements"] == [] and s["decisions"] == []
    # the path: a section says what it shares with the next
    assert all("link_to_next" in s for s in secs[:-1]) and "link_to_next" not in secs[-1]
    assert v["run"]["run_id"] == run and v["available_themes"] == []


def test_the_documents_of_a_topic_end_up_in_one_section_and_neighbours_share_documents(project, run):
    oid = outline.create(project, run)
    for s in outline.view(project, oid)["sections"]:
        topics = {topic_of(project)[p["passage_id"]] for p in s["representatives"]}
        assert len(topics) == 1            # a section is about one topic (the corpus has six, two documents each)


def test_the_outline_is_kept_in_the_project_and_several_are_fine(project, run):
    a = outline.create(project, run)
    b = outline.create(project, run, title="Second plan", order="size")
    assert [o["title"] for o in outline.list_outlines(project)] == ["Second plan", outline.view(project, a)["outline"]["title"]]
    _own(project, a, "Introduction")
    reopened = Workspace(project.root)
    assert outline.view(reopened, a)["outline"]["sections"] == len(themes.view(project, run)["themes"]) + 1
    assert [s["themes"][0]["theme_id"] for s in outline.view(reopened, b)["sections"]] == \
        [t["theme_id"] for t in themes.view(project, run)["themes"]]      # order="size": as the themes are listed
    outline.update(project, b, title="Renamed")
    assert outline.view(project, b)["outline"]["title"] == "Renamed"
    outline.delete(project, a)
    assert [o["outline_id"] for o in outline.list_outlines(project)] == [b]
    with pytest.raises(KeyError):
        outline.view(project, a)
    with pytest.raises(KeyError):
        outline.create(project, "no-such-run")
    with pytest.raises(ValueError):
        outline.create(project, run, order="alphabetical")


def test_reordering_nesting_and_the_limit_on_depth(project, run):
    oid = outline.create(project, run)
    ids = [s["section_id"] for s in outline.view(project, oid)["sections"]]
    outline.move(project, oid, ids[0], None, 2)                    # reorder
    assert [s["section_id"] for s in outline.view(project, oid)["sections"]][2] == ids[0]
    outline.move(project, oid, ids[1], ids[2])                     # nest
    v = outline.view(project, oid)
    parent = next(s for s in v["sections"] if s["section_id"] == ids[2])
    assert [c["section_id"] for c in parent["children"]] == [ids[1]] and parent["children"][0]["number"].startswith(parent["number"] + ".")
    outline.move(project, oid, ids[3], ids[1])                     # three levels
    with pytest.raises(ValueError, match="three levels"):
        outline.move(project, oid, ids[4], ids[3])
    with pytest.raises(ValueError, match="inside itself"):
        outline.move(project, oid, ids[2], ids[3])                 # a section into its own descendant
    with pytest.raises(ValueError, match="three levels"):
        outline.move(project, oid, ids[5], ids[3]) if len(ids) > 5 else outline.move(project, oid, ids[4], ids[3])
    outline.move(project, oid, ids[1], None, 0)                    # taking a section out takes its own inside it along
    v = outline.view(project, oid)
    assert v["sections"][0]["section_id"] == ids[1] and v["sections"][0]["children"][0]["section_id"] == ids[3]
    assert [s["index"] for s in v["sections"]] == list(range(len(v["sections"])))
    with pytest.raises(KeyError):
        outline.move(project, oid, "nope", None)


def test_your_own_sections_notes_and_titles(project, run):
    oid = outline.create(project, run)
    first = outline.view(project, oid)["sections"][0]
    intro = outline.add_section(project, oid, "  Introduction ", note="Say why this matters.\r\n\r\nThen the question.", index=0)
    methods = outline.add_section(project, oid, "Methods")
    v = outline.view(project, oid)
    assert v["sections"][0]["title"] == "Introduction" and v["sections"][-1]["title"] == "Methods"
    assert v["sections"][0]["kind"] == "own" and v["sections"][0]["note"] == "Say why this matters.\n\nThen the question."
    assert v["sections"][0]["documents"] == 0 and v["sections"][0]["gaps"] == [] and v["sections"][0]["state"] == "own"
    with pytest.raises(ValueError, match="title"):
        outline.add_section(project, oid, "  ")
    with pytest.raises(ValueError, match="title"):
        outline.update_section(project, oid, intro, title="")
    # a theme section keeps its theme's heading until renamed, and gets it back with an empty title
    outline.update_section(project, oid, first["section_id"], title="The big picture", note="Start here.")
    s = next(x for x in outline.view(project, oid)["sections"] if x["section_id"] == first["section_id"])
    assert (s["title"], s["title_source"], s["note"], s["default_title"]) == ("The big picture", "you", "Start here.", first["title"])
    outline.update_section(project, oid, first["section_id"], title="")
    assert next(x for x in outline.view(project, oid)["sections"] if x["section_id"] == first["section_id"])["title"] == first["title"]
    outline.update_section(project, oid, methods, title="Method and data")
    assert outline.view(project, oid)["sections"][-1]["title"] == "Method and data"
    with pytest.raises(ValueError, match="nested"):          # three levels only
        a = outline.add_section(project, oid, "A", parent_id=methods)
        b = outline.add_section(project, oid, "B", parent_id=a)
        outline.add_section(project, oid, "C", parent_id=b)


def test_merging_and_splitting_sections(project, run):
    oid = outline.create(project, run)
    v = outline.view(project, oid)
    a, b, c = (s["section_id"] for s in v["sections"][:3])
    docs_a, docs_b = v["sections"][0]["documents"], v["sections"][1]["documents"]
    outline.update_section(project, oid, a, note="About A.")
    outline.update_section(project, oid, b, note="About B.")
    kid = outline.add_section(project, oid, "Inside B", parent_id=b)
    outline.merge(project, oid, b, a)
    v = outline.view(project, oid)
    assert len(v["sections"]) == len(themes.view(project, run)["themes"]) - 1
    m = next(s for s in v["sections"] if s["section_id"] == a)
    assert len(m["themes"]) == 2 and m["documents"] == docs_a + docs_b and m["note"] == "About A.\n\nAbout B."
    assert [c_["section_id"] for c_ in m["children"]] == [kid]      # the sections inside come along
    assert m["can_split"] and all(s["section_id"] != b for s in v["sections"])
    with pytest.raises(ValueError, match="different"):
        outline.merge(project, oid, a, a)
    with pytest.raises(ValueError, match="inside"):
        outline.merge(project, oid, a, kid)
    # splitting a section of two themes gives each its own again (the first keeps its place, notes and title)
    new = outline.split(project, oid, a)
    v = outline.view(project, oid)
    assert len(new) == 1 and len(v["sections"]) == len(themes.view(project, run)["themes"])
    assert [s["section_id"] for s in v["sections"]][:2] == [a, new[0]] and len(v["sections"][0]["themes"]) == 1
    with pytest.raises(ValueError, match="own"):
        outline.split(project, oid, kid)


def test_splitting_one_theme_by_documents(project, run):
    oid = outline.create(project, run)
    s = outline.view(project, oid)["sections"][0]
    docs = [d["doc_id"] for d in s["sources"]]
    assert len(docs) == 2 and s["can_split"]
    for bad in (None, [], docs, ["nope"]):
        with pytest.raises(ValueError, match="Choose some"):
            outline.split(project, oid, s["section_id"], bad)
    (new,) = outline.split(project, oid, s["section_id"], [docs[1]])
    v = outline.view(project, oid)
    one, two = v["sections"][0], v["sections"][1]
    assert two["section_id"] == new and one["title"].endswith("(part 1)") and two["title"].endswith("(part 2)")
    assert [d["doc_id"] for d in one["sources"]] == [docs[0]] and [d["doc_id"] for d in two["sources"]] == [docs[1]]
    assert one["passages"] + two["passages"] == s["passages"] and one["split_by_documents"] and two["split_by_documents"]
    assert {r["doc_id"] for r in two["representatives"]} == {docs[1]}
    assert set(one["terms"]) <= set(s["terms"]) and one["gaps"][0]["kind"] == "one-source"
    assert not one["can_split"]                                       # one document: nothing to split
    # joining them again makes the theme whole
    outline.merge(project, oid, new, one["section_id"])
    j = outline.view(project, oid)["sections"][0]
    assert j["passages"] == s["passages"] and j["documents"] == 2


def test_taking_a_section_out_and_bringing_its_theme_back(project, run):
    oid = outline.create(project, run)
    v = outline.view(project, oid)
    a, b = v["sections"][0], v["sections"][1]
    kid = outline.add_section(project, oid, "Inside", parent_id=a["section_id"])
    outline.delete_section(project, oid, a["section_id"])
    v2 = outline.view(project, oid)
    assert v2["sections"][0]["section_id"] == kid and v2["sections"][1]["section_id"] == b["section_id"]    # it moved up
    assert [t["theme_id"] for t in v2["available_themes"]] == [a["themes"][0]["theme_id"]]
    new = outline.add_section(project, oid, theme_id=a["themes"][0]["theme_id"])
    again = next(s for s in outline.view(project, oid)["sections"] if s["section_id"] == new)
    assert again["themes"][0]["theme_id"] == a["themes"][0]["theme_id"] and outline.view(project, oid)["available_themes"] == []
    with pytest.raises(ValueError, match="themes shown"):
        outline.add_section(project, oid, theme_id=99999)


def test_suggesting_the_order_again_leaves_your_own_sections_in_place(project, run):
    oid = outline.create(project, run)
    suggested = [s["section_id"] for s in outline.view(project, oid)["sections"]]
    intro = outline.add_section(project, oid, "Introduction", index=0)
    for i, sid in enumerate(reversed(suggested)):
        outline.move(project, oid, sid, None, 1 + i)
    assert outline.reorder(project, oid) > 0
    got = [s["section_id"] for s in outline.view(project, oid)["sections"]]
    assert got == [intro] + suggested
    assert outline.reorder(project, oid) == 0                 # already in that order


def test_the_outline_outlives_its_themes_and_follows_what_you_did_to_them(project, run):
    v0 = themes.view(project, run)
    # a theme merged into another on the Themes page: its section shows the theme that took its place
    gone, keep = v0["themes"][1]["theme_id"], v0["themes"][0]["theme_id"]
    oid = outline.create(project, run)
    themes.edit(project, run, "merge", gone, keep)
    v = outline.view(project, oid)
    merged = {s["parts"][0]["theme"]: s for s in v["sections"]}
    assert merged[gone]["passages"] == merged[keep]["passages"] > 0 and merged[gone]["state"] == "shown"
    assert all(t["theme_id"] != gone for t in v["available_themes"])
    assert merged[gone]["themes"][0]["theme_id"] == keep               # it shows the theme that took its place
    themes.edit(project, run, "merge", gone, None)
    # a theme removed: its section says so; deleting the whole set keeps titles and notes
    third = v0["themes"][2]["theme_id"]
    themes.edit(project, run, "remove", third, True)
    sec = next(s for s in outline.view(project, oid)["sections"] if s["parts"][0]["theme"] == third)
    assert sec["state"] == "removed" and sec["passages"] == 0 and sec["gaps"][0]["kind"] == "none"
    outline.update_section(project, oid, sec["section_id"], note="Keep this.")
    themes.delete_run(project, run)
    v = outline.view(project, oid)
    assert v["run"] is None and len(v["sections"]) == len(v0["themes"]) and v["available_themes"] == []
    assert all(s["state"] == "gone" and s["passages"] == 0 for s in v["sections"])
    assert next(s for s in v["sections"] if s["section_id"] == sec["section_id"])["note"] == "Keep this."
    assert [o["run_exists"] for o in outline.list_outlines(project)] == [False]
    with pytest.raises(ValueError, match="deleted"):
        outline.reorder(project, oid)
    assert "Keep this." in outline.to_markdown(outline.document(project, oid))


# ---------------------------------------------------------------------------------------------
# checks, decisions, gaps, APA, codes and concepts
# ---------------------------------------------------------------------------------------------
def _water_check(ws, draft_text="Studies of groundwater and aquifer depletion show that desalination depends on brine "
                                "disposal, according to many studies."):
    did = drafts.new_draft(ws, "Water\n\n" + draft_text)
    drafts.find_by_rules(ws, did)
    cid = drafts.view(ws, did)["claims"][0]["claim_id"]
    out = drafts.check_claims(ws, did, BaselineBackend(), "baseline", claim_ids=[cid], k=6, per_doc=2)
    return did, cid, out["checked"][0]


def _link_bibliography(ws, doc_id, last, year, key, title=None):
    with ws.connect() as cx:
        cx.execute("INSERT INTO bib_items(item_key, item_type, title, creators_json, year, seq) VALUES (?,?,?,?,?,?)",
                   (key, "journalArticle", title or f"Work {key}", json.dumps([{"last": last, "first": "A.", "role": "author"}]),
                    year, 1))
        cx.execute("INSERT INTO bib_links(item_key, doc_id, status, method, score) VALUES (?,?,?,?,?)",
                   (key, doc_id, "confirmed", "test", 1.0))


def test_disagreements_decisions_gaps_and_apa_citations(project, run):
    did, cid, hid = _water_check(project)
    res = claimcheck.hypothesis_result(project, hid)
    docs = [w["doc_id"] for w in res["who"]]
    assert len(docs) == 2 and {w["side"] for w in res["who"]} == {"supports"}
    # you read an excerpt of one document and judge it the other way: the documents now disagree
    part = project.scalar("SELECT claim_id FROM user_claims WHERE hyp_id=?", (hid,))
    pid = project.scalar("SELECT passage_id FROM verifications WHERE subject_id=? AND doc_id=? AND verdict='supports'", (part, docs[0]))
    claimcheck.set_judgement(project, part, pid, "refutes")
    drafts.update_claim(project, did, cid, decision="supported")
    _link_bibliography(project, docs[0], "Haugen", "2024", "K1")
    _link_bibliography(project, docs[1], "Okafor", "2023", "K2")
    oid = outline.create(project, run)
    v = outline.view(project, oid)
    water = [s for s in v["sections"] if set(docs) & {d["doc_id"] for d in s["sources"]}]
    assert len(water) == 1
    s = water[0]
    assert s["cite"]["text"] == "(Haugen, 2024; Okafor, 2023)" and s["cite"]["missing"] == 0 and v["outline"]["bibliography"]
    assert all(d["apa"] for d in s["sources"]) and all(r["apa"] for r in s["representatives"])
    dis = s["disagreements"]
    assert len(dis) == 1 and dis[0]["tier"] == "inside" and dis[0]["hyp_id"] == hid
    assert [x["doc_id"] for x in dis[0]["refutes"]] == [docs[0]] and docs[1] in [x["doc_id"] for x in dis[0]["supports"]]
    assert dis[0]["refutes"][0]["apa"] == "(Haugen, 2024)" and dis[0]["refutes"][0]["inside"]
    assert [d["decision"] for d in s["decisions"]] == ["supported"] and s["decisions"][0]["draft_id"] == did
    # sections that touch none of these documents show neither
    assert all(not x["disagreements"] and not x["decisions"] for x in v["sections"] if x is not s)
    # a gap is named: two documents only
    assert s["gaps"] and s["gaps"][0]["kind"] == "few" and "Only two sources" in s["gaps"][0]["text"]
    # no bibliography: the documents are named by title, the citation says what is missing
    other = next(x for x in v["sections"] if x is not s)
    assert other["cite"]["text"] is None and other["cite"]["missing"] == len(other["sources"])


def test_gaps_name_one_source_and_a_theme_that_is_mostly_one_source(project, run):
    v = outline.view(project, outline.create(project, run))
    s = v["sections"][0]
    assert outline._gaps("theme", 20, Counter({"a": 20}), {"a": "Only paper"})[0]["text"] == "One source only: Only paper."
    mostly = outline._gaps("theme", 10, Counter({"a": 9, "b": 1, "c": 1}), {"a": "Big", "b": "x", "c": "y"})
    assert [g["kind"] for g in mostly] == ["mostly-one"] and "90%" in mostly[0]["text"]
    assert outline._gaps("theme", 3, Counter({"a": 1, "b": 1, "c": 1}), {})[0]["kind"] == "thin"
    assert outline._gaps("own", 0, Counter(), {}) == [] and s["gaps"][0]["kind"] == "few"


def test_codes_and_concepts_of_a_section(project, run):
    from margin import frameworks, profile

    assert frameworks.get("sdg", project)
    pid = next(iter(themes.theme_passages(project, run, themes.view(project, run)["themes"][0]["theme_id"])["passages"]))["passage_id"]
    profile.add_label(project, "sdg", pid, "6.4")
    oid = outline.create(project, run, framework="sdg")
    first = next(s for s in outline.view(project, oid)["sections"] if any(r["passage_id"] == pid for r in s["representatives"]) or s["codes"])
    assert first["codes"] and first["codes"][0]["code"] == "6.4" and first["codes"][0]["passages"] >= 1
    assert outline.view(project, oid, framework="")["sections"][0]["codes"] is None       # no codebook: no codes
    outline.update(project, oid, framework="nonexistent")
    v = outline.view(project, oid)
    assert v["framework_missing"] and all(s["codes"] is None for s in v["sections"])
    # a concept: two of the section's key terms joined by a 'same' link
    t = themes.view(project, run)["themes"][0]
    a, b = t["terms"][0], t["terms"][1]
    ids = {r["label"]: r["term_id"] for r in project.query("SELECT term_id, label FROM terms WHERE label IN (?,?)", (a, b))}
    with project.connect() as cx:
        cx.execute("INSERT INTO concepts VALUES ('c1', ?)", (a,))
        cx.executemany("INSERT INTO concept_terms VALUES ('c1', ?, 'group')", [(i,) for i in ids.values()])
    sec = outline.view(project, outline.create(project, run))["sections"][0]
    assert sec["concepts"] and sec["concepts"][0]["label"] == a and set(sec["concepts"][0]["wordings"]) == {a, b}


# ---------------------------------------------------------------------------------------------
# C2: beside a draft
# ---------------------------------------------------------------------------------------------
def test_beside_a_draft_what_is_covered_and_what_is_unused(project, run):
    v = outline.view(project, outline.create(project, run))
    oid = v["outline"]["outline_id"]
    water = next(s for s in v["sections"] if topic_of(project)[s["representatives"][0]["passage_id"]] == "water")
    jobs = next(s for s in v["sections"] if topic_of(project)[s["representatives"][0]["passage_id"]] == "jobs")
    terms = water["terms"][:6]
    text = ("Water in the region\n\nThe literature discusses " + ", ".join(terms) + " at length, and it returns to "
            + ", ".join(terms[:3]) + " later.\n\nThe cited work is Haugen (2024).\n")
    did = drafts.new_draft(project, text)
    cmp = outline.compare(project, oid, did)
    c = cmp["sections"][water["section_id"]]
    assert c["terms_used"] >= 5 and c["terms_total"] == len(water["terms"]) and c["level"] in ("partly", "little", "well")
    assert [t["label"] for t in c["terms"] if t["mentions"]][:3] == terms[:3] and c["where"] and c["where"]["paragraph"] == 2          # the title is paragraph 1
    assert cmp["sections"][jobs["section_id"]]["level"] == "none" and cmp["sections"][jobs["section_id"]]["terms_used"] <= 1
    assert cmp["order"] == [s["section_id"] for s in _flat(v)] and cmp["meaning"] is None
    assert cmp["draft"]["cited_documents"] == 0 and len(cmp["notes"]) == 1       # it says why no source counts as used
    assert ("No citations were read" in cmp["notes"][0]) == (cmp["draft"]["citations"] == 0)
    assert c["unused_sources"] and c["sources_used"] == 0           # nothing cited yet: every source is unused
    # a draft that cites one of the documents: it counts as used, the other is still to cite
    doc = water["sources"][0]["doc_id"]
    _link_bibliography(project, doc, "Haugen", "2024", "K1")
    did2 = drafts.new_draft(project, text)
    c2 = outline.compare(project, oid, did2)
    assert c2["draft"]["citations"] >= 1 and c2["draft"]["cited_documents"] == 1
    s2 = c2["sections"][water["section_id"]]
    assert [u["doc_id"] for u in s2["used_sources"]] == [doc] and doc not in [u["doc_id"] for u in s2["unused_sources"]]
    assert s2["sources_used"] == 1 and s2["unused_points"] and all(p["doc_id"] != doc for p in s2["unused_points"])
    assert s2["score"] > c["score"] or c["level"] == s2["level"]
    # an own section has nothing to cover
    own = outline.add_section(project, oid, "Methods")
    assert outline.compare(project, oid, did)["sections"][own]["level"] == "none"
    with pytest.raises(KeyError):
        outline.compare(project, oid, "no-such-draft")


class _Local:
    """An embedding model on this computer: a one-hot vector for the topic a text is about."""
    model = "fake-embed"
    base_url = "http://localhost:11434"

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        out = []
        for t in texts:
            v = [0.0] * len(TOPICS)
            for i, words in enumerate(TOPICS.values()):
                v[i] = sum(1.0 for w in words if re.search(rf"\b{w}\b", t))
            out.append(v if any(v) else [1.0] + [0.0] * (len(TOPICS) - 1))
        return out


def test_closeness_by_meaning_only_with_a_local_model_that_is_already_built(project, run, monkeypatch):
    from margin import embed, home as home_

    fake = _Local()
    oid = outline.create(project, run)
    did = drafts.new_draft(project, "Housing\n\nHospitals and patients and vaccination clinics matter most.\n\n"
                                    "Groundwater and aquifer depletion and desalination come second.\n")
    settings = {"embed_backend": "ollama", "embed_model": fake.model}
    monkeypatch.setattr(home_, "make_embedder", lambda s: fake if s.get("embed_backend") != "off" else None)
    # no vectors built yet: it says so and embeds nothing
    m = outline.compare(project, oid, did, meaning=True, settings=settings)["meaning"]
    assert m["available"] is False and "no vectors" in m["why"] and fake.calls == 0
    with project.connect() as cx:
        for r in project.query("SELECT passage_id, text FROM passages WHERE section='body'"):
            cx.execute("INSERT INTO embeddings VALUES (?,?,?)", (fake.model, r["passage_id"], embed._unit(fake.embed([r["text"]])[0]).tobytes()))
    off = outline.compare(project, oid, did, meaning=True, settings={"embed_backend": "off"})["meaning"]
    assert off["available"] is False and "not set up" in off["why"]
    fake.calls = 0
    cmp = outline.compare(project, oid, did, meaning=True, settings=settings)
    assert cmp["meaning"]["available"] is True and fake.calls == 2           # the draft's two paragraphs
    health = next(s for s in outline.view(project, oid)["sections"] if topic_of(project)[s["representatives"][0]["passage_id"]] == "health")
    water = next(s for s in outline.view(project, oid)["sections"] if topic_of(project)[s["representatives"][0]["passage_id"]] == "water")
    ch, cw = cmp["sections"][health["section_id"]], cmp["sections"][water["section_id"]]
    assert ch["closeness"] > 0.9 and ch["closest"]["paragraph"] == 2 and "Hospitals" in ch["closest"]["excerpt"]
    assert cw["closest"]["paragraph"] == 3
    # without the option nothing is embedded; an embedding model on another computer is never given the draft
    fake.calls = 0
    assert outline.compare(project, oid, did, settings=settings)["meaning"] is None and fake.calls == 0
    fake.base_url = "https://embeddings.example.com/v1"
    far = outline.compare(project, oid, did, meaning=True, settings=settings)["meaning"]
    assert far["available"] is False and "another computer" in far["why"] and fake.calls == 0


# ---------------------------------------------------------------------------------------------
# C3: the document
# ---------------------------------------------------------------------------------------------
def test_markdown_has_headings_notes_quotes_with_their_place_and_citations(project, run):
    did, cid, hid = _water_check(project)
    docs = [w["doc_id"] for w in claimcheck.hypothesis_result(project, hid)["who"]]
    _link_bibliography(project, docs[0], "Haugen", "2024", "K1")
    _link_bibliography(project, docs[1], "Okafor", "2023", "K2")
    oid = outline.create(project, run, title="Water & jobs <plan>")
    first = outline.view(project, oid)["sections"][0]
    outline.update_section(project, oid, first["section_id"], note="Argue this first.\n\nThen that.")
    kid = outline.add_section(project, oid, "Introduction", parent_id=first["section_id"])
    md = outline.to_markdown(outline.document(project, oid))
    lines = md.splitlines()
    assert lines[0] == "# Water & jobs <plan>"
    assert re.search(r"^## 1 ", md, re.M) and re.search(r"^### 1\.1 Introduction$", md, re.M)
    assert "Argue this first.\n\nThen that." in md and "**Key terms:** " in md
    q = re.search(r"^> (.+)\n> — (.+)$", md, re.M)
    assert q and re.search(r"paragraphs? \d", q.group(2))              # the quote with its place
    sec_with_apa = [m for m in re.findall(r"^\*\*Cite:\*\* (.+)$", md, re.M)]
    assert "(Haugen, 2024; Okafor, 2023)" in sec_with_apa
    assert "## Sources named in this outline" in md and "(Haugen, 2024)" in md
    # what to include is chosen: no quotes, no key terms, no sources
    plain = outline.to_markdown(outline.document(project, oid, include=("gaps",)))
    assert not re.search(r"^> ", plain, re.M) and "Key terms" not in plain and "Cite" not in plain and "Gaps" in plain
    assert "Sources named" not in plain
    del kid


def test_word_document_is_a_valid_package_with_heading_styles(project, run):
    oid = outline.create(project, run, title="A & B <c>")
    first = outline.view(project, oid)["sections"][0]
    outline.update_section(project, oid, first["section_id"], note="Bell \x07 & <tag> “quotes” é\nsecond line")
    outline.add_section(project, oid, "Methods", parent_id=first["section_id"])
    raw = outline.to_docx(outline.document(project, oid))
    z = zipfile.ZipFile(io.BytesIO(raw))
    assert z.testzip() is None
    assert set(z.namelist()) == {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/_rels/document.xml.rels",
                                 "word/styles.xml", "docProps/core.xml"}
    for name in z.namelist():
        minidom.parseString(z.read(name))                                  # every part is well-formed XML
    doc = z.read("word/document.xml").decode()
    styles = z.read("word/styles.xml").decode()
    assert 'w:pStyle w:val="Title"' in doc and 'w:pStyle w:val="Heading1"' in doc and 'w:pStyle w:val="Heading2"' in doc
    for sid in ("Title", "Heading1", "Heading2", "Heading3", "Quote", "ListBullet", "Normal"):
        assert f'w:styleId="{sid}"' in styles
    assert "A &amp; B &lt;c&gt;" in doc and "&amp; &lt;tag&gt;" in doc and "\x07" not in doc and "“quotes” é" in doc
    assert "<w:t xml:space=\"preserve\">1 " in doc and "Methods" in doc
    assert b"A &amp; B &lt;c&gt;" in z.read("docProps/core.xml")
    ct = z.read("[Content_Types].xml").decode()
    assert "wordprocessingml.document.main+xml" in ct and "wordprocessingml.styles+xml" in ct


# ---------------------------------------------------------------------------------------------
# the app: API and page
# ---------------------------------------------------------------------------------------------
def _app_project(api, tmp_path):
    assert api("PUT", "/api/settings", {"embed_backend": "off"})[0] == 200
    assert api("POST", "/api/projects", {"name": "P"})[0] == 200
    for f in sorted(topics_corpus(tmp_path / "topics").iterdir()):
        assert api("POST", f"/api/projects/P/uploads?batch=b1&name={f.name}", raw=f.read_bytes())[0] == 200
    assert api.wait(api("POST", "/api/projects/P/ingest", {"batch": "b1"})[1]["job"]["id"])["state"] == "done"


def test_the_api(api, tmp_path):
    _app_project(api, tmp_path)
    base = "/api/projects/P/outlines"
    st, r = api("POST", base, {})
    assert st == 409 and "themes" in r["error"]                       # nothing to make it from yet
    job = api.wait(api("POST", "/api/projects/P/themes", {"k": 5})[1]["job"]["id"])
    rid = job["result"]["run_id"]
    st, r = api("GET", base)
    assert st == 200 and r["outlines"] == [] and r["runs"][0]["run_id"] == rid and "framework" in r
    st, r = api("POST", base, {"run_id": rid, "title": "Plan"})
    assert st == 200
    oid = r["outline_id"]
    assert api("POST", base, {"run_id": "nope"})[0] == 404
    st, v = api("GET", f"{base}/{oid}")
    assert st == 200 and v["outline"]["title"] == "Plan" and len(v["sections"]) == 5 and v["max_depth"] == 3
    assert api("GET", f"{base}/nope")[0] == 404
    ids = [s["section_id"] for s in v["sections"]]
    assert api("PUT", f"{base}/{oid}", {"title": "Renamed plan"})[0] == 200
    assert api("PUT", f"{base}/{oid}", {"framework": "no-such-codebook"})[0] in (400, 404)
    st, r = api("POST", f"{base}/{oid}/sections", {"title": "Introduction", "index": 0, "note": "Why"})
    intro = r["section_id"]
    assert st == 200 and api("GET", f"{base}/{oid}")[1]["sections"][0]["section_id"] == intro
    assert api("POST", f"{base}/{oid}/sections", {"title": ""})[0] == 400
    assert api("PUT", f"{base}/{oid}/sections/{intro}", {"title": "Opening", "note": "Why it matters"})[0] == 200
    assert api("POST", f"{base}/{oid}/sections/{ids[1]}/move", {"parent_id": ids[0], "index": None})[0] == 200
    st, r = api("POST", f"{base}/{oid}/sections/{ids[0]}/move", {"parent_id": ids[1]})
    assert st == 400 and "inside itself" in r["error"]
    assert api("POST", f"{base}/{oid}/sections/{ids[2]}/merge", {"into": ids[2]})[0] == 400
    assert api("POST", f"{base}/{oid}/sections/{ids[2]}/merge", {"into": ids[3]})[0] == 200
    st, r = api("POST", f"{base}/{oid}/sections/{ids[3]}/split", {})
    assert st == 200 and len(r["sections"]) == 1
    docs = [d["doc_id"] for d in api("GET", f"{base}/{oid}")[1]["sections"][-1]["sources"]]
    assert api("POST", f"{base}/{oid}/sections/{ids[4]}/split", {"doc_ids": "x"})[0] == 400
    st, r = api("POST", f"{base}/{oid}/order", {})
    assert st == 200 and "moved" in r
    st, r = api("POST", f"{base}/{oid}/sections/{ids[4]}/rotate", {})
    assert st == 404 or st == 405
    # beside a draft
    st, d = api("POST", "/api/projects/P/drafts", {"text": "Water\n\nGroundwater and aquifer depletion matter.", "ai_access": "none"})
    did = d["draft"]["draft_id"]
    st, c = api("GET", f"{base}/{oid}/draft/{did}")
    assert st == 200 and c["draft"]["draft_id"] == did and c["meaning"] is None and len(c["sections"]) >= 5
    st, c = api("GET", f"{base}/{oid}/draft/{did}?meaning=1")
    assert st == 200 and c["meaning"]["available"] is False
    assert api("GET", f"{base}/{oid}/draft/nope")[0] == 404
    # downloads
    st, md = api("GET", f"{base}/{oid}/export.md")
    assert st == 200 and md.decode().startswith("# Renamed plan") and "## 1 Opening" in md.decode()
    st, docx = api("GET", f"{base}/{oid}/export.docx")
    assert st == 200 and zipfile.ZipFile(io.BytesIO(docx)).testzip() is None
    st, only = api("GET", f"{base}/{oid}/export.md?include=gaps,terms")
    assert st == 200 and b"Key terms" in only and b"> " not in only
    assert api("GET", f"{base}/{oid}/export.md?include=lunch")[0] == 400
    assert api("GET", f"{base}/{oid}/export.docx?token={api.token}", token=False)[0] == 200     # a plain link works
    assert api("GET", f"{base}/{oid}", token=False)[0] == 401
    assert api("DELETE", f"{base}/{oid}/sections/{intro}")[0] == 200
    assert api("GET", f"{base}/{oid}")[1]["sections"][0]["section_id"] != intro
    assert api("DELETE", f"{base}/{oid}")[0] == 200
    assert api("GET", base)[1]["outlines"] == []
    del docs


def test_the_page_files_wire_the_feature_in():
    features = (STATIC / "features.js").read_text(encoding="utf-8")
    m = re.search(r"\n  outline: \{[^}]*?section: \"(\w+)\", title: \"Outline\", icon: \"([\w-]+)\", href: \"#/outline\", ai: \"(\w+)\"", features)
    assert m and m.group(1) == "write" and m.group(3) in ("none", "optional")
    assert re.search(rf'\n  {m.group(2)!r}'.replace("'", '"') + r"?:|\n  \"?" + re.escape(m.group(2)) + r"\"?: \[", (STATIC / "icons.js").read_text(encoding="utf-8"))
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'import { renderOutlines, renderOutline } from "./views/outline.js"' in app
    assert '[/^\\/outline$/, "outline", renderOutlines]' in app and '[/^\\/outline\\/([^/]+)$/, "outline", renderOutline]' in app
    assert 'data-route="outline"' in (STATIC / "index.html").read_text(encoding="utf-8")
    themes_js = (STATIC / "views" / "themes.js").read_text(encoding="utf-8")
    assert 'import { outlineButton } from "./outline.js"' in themes_js and "outlineButton(project, runId)" in themes_js
    view = (STATIC / "views" / "outline.js").read_text(encoding="utf-8")
    assert "Make an outline" in view and "/export.${" in view and '"docx"' in view and '"md"' in view and "draggable" in view
    for label in ("Move up", "Move down", "Put inside the section above", "Take out of its section"):
        assert label in view                                              # the keyboard and button way to move
    css = (STATIC / "margin.css").read_text(encoding="utf-8")
    assert ".ol-item" in css and ".ol-bar.ol-drop-before" in css
    assert not list(STATIC.glob("*outline*.css"))                         # no new CSS file
    for name in ("outline-", "ol-"):
        assert not (STATIC / f"{name}.css").exists()


def test_the_documentation_describes_every_route():
    api_md = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    from margin.gui.server import ROUTES

    mine = [(m, rx.pattern) for m, rx, name in ROUTES if "outline" in name]
    assert len(mine) == 13                 # 0.14 added POST …/hypotheses
    for path in ("/outlines", "/outlines/<outline>", "outlines/<outline>/order", "outlines/<outline>/sections",
                 "sections/<section>", "sections/<section>/move", "sections/<section>/merge", "sections/<section>/split",
                 "outlines/<outline>/draft/<draft>", "outlines/<outline>/export.docx", "export.md"):
        assert path in api_md, path
    assert "Outline" in (ROOT / "docs" / "manual" / "outline.md").read_text(encoding="utf-8")
