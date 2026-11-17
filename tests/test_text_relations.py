"""0.18.1 (roadmap D2, Part A, A5): relations found from the text, without AI, only between terms the glossary knows.

"X such as Y" and "Y and other X" (broader and narrower), "X, also called Y" / "X (also known as Y)" (the same), "X
leads to / causes / reduces Y" (an effect), "X instead of Y" (replaces). Each proposal carries its sentences and is
accepted or rejected as other links are."""
from __future__ import annotations

import re

import pytest

from margin import ingest, terms, textrelations
from margin.store import Workspace

TERMS = ("renewable energy", "solar power", "wind power", "hydropower", "heat pumps", "heating systems",
         "carbon tax", "emissions", "remote work", "telework", "commuting", "gas boilers", "energy poverty")


def pairs(sentence: str) -> set[tuple[str, str, str]]:
    """The relations `_pairs` finds in a sentence whose known terms are TERMS (each mention found by its words)."""
    ms = []
    for t in TERMS:
        for m in re.finditer(r"\b" + re.escape(t) + r"\b", sentence, re.I):
            ms.append((m.start(), m.end(), t))
    return set(textrelations._pairs(sentence, ms))


def test_such_as_and_a_list_after_it():
    assert pairs("Renewable energy such as solar power is cheaper every year.") == \
        {("renewable energy", "solar power", "broader")}
    assert pairs("We compared renewable energy, such as solar power, wind power and hydropower, with coal.") == \
        {("renewable energy", t, "broader") for t in ("solar power", "wind power", "hydropower")}


def test_and_other_with_the_items_before_it():
    assert pairs("Solar power and other renewable energy sources grew.") == \
        {("solar power", "renewable energy", "narrower")}
    assert pairs("Solar power, wind power and other renewable energy grew.") == \
        {("wind power", "renewable energy", "narrower"), ("solar power", "renewable energy", "narrower")}


def test_also_called_and_also_known_as_are_the_same():
    assert pairs("Remote work, also called telework, spread after 2020.") == {("remote work", "telework", "same")}
    assert pairs("Remote work (also known as telework) spread after 2020.") == {("remote work", "telework", "same")}


def test_effects_and_replacements():
    assert pairs("A carbon tax reduces emissions in every sector studied.") == {("carbon tax", "emissions", "effect")}
    assert pairs("Remote work can lead to less commuting.") == set()       # "less" stands between: not stated plainly
    assert pairs("Remote work can lead to commuting at odd hours.") == {("remote work", "commuting", "effect")}
    assert pairs("Households chose heat pumps instead of gas boilers.") == {("heat pumps", "gas boilers", "replaces")}


def test_negatives():
    # inside quotation marks: someone's words, a title
    assert pairs("The report is called “Renewable energy such as solar power”.") == set()
    assert pairs('She wrote "a carbon tax reduces emissions" in 2019.') == set()
    # other words between the two terms
    assert pairs("Renewable energy, a sector such as no other, needs solar power.") == set()
    assert pairs("A carbon tax, unlike subsidies, reduces emissions.") == set()
    # a list without a pattern says nothing
    assert pairs("Solar power, wind power and hydropower were compared.") == set()
    # a sentence break between them
    assert pairs("We studied renewable energy. Such as solar power, it varies.") == set()
    # one term only
    assert pairs("Renewable energy such as the sun is free.") == set()


def test_stored_from_the_smaller_id_with_the_relation_turned_round():
    assert textrelations._INV["effect"] == "effect_of" and textrelations._INV["replaces"] == "replaced_by"
    for rel in ("effect", "effect_of", "replaces", "replaced_by"):
        assert rel in terms.LINK_RELATIONS and terms._INVERSE[terms._INVERSE[rel]] == rel


# ---- with the glossary -------------------------------------------------------------------------------------------
TEXT = ("Heating in cold regions\n\n"
        "Households replace heating systems slowly. Heating systems such as heat pumps are subsidised in the region. "
        "Most households chose heat pumps instead of gas boilers once the subsidy came.\n\n"
        "Gas boilers and other heating systems are still sold. Heat pumps are quiet. Heat pumps lower energy poverty "
        "where the subsidy is large, and energy poverty is a risk for older households with gas boilers.\n\n"
        "Heating systems differ by region. Heat pumps need electricity; gas boilers need gas. Energy poverty "
        "remains where gas boilers are kept. Heat pumps instead of gas boilers was the advice of the agency.\n")


@pytest.fixture
def built(tmp_path):
    ws = Workspace.create(tmp_path / "p")
    d = tmp_path / "docs"
    d.mkdir()
    (d / "heating.txt").write_text(TEXT, encoding="utf-8")
    (d / "heating2.txt").write_text(TEXT.replace("Heating in cold regions", "Heating in warm regions"), encoding="utf-8")
    ingest.ingest(ws, [d])
    terms.build(ws)
    yield ws
    ws.close_all()


def _term(ws, label: str) -> str:
    t = terms.find_term(ws, label)
    assert t, (label, [r[0] for r in ws.query("SELECT label FROM terms ORDER BY tf DESC LIMIT 40")])
    return t


def test_the_glossary_proposes_them_with_their_sentences_and_a_person_decides(built):
    ws = built
    hp, gb, hs = _term(ws, "heat pumps"), _term(ws, "gas boilers"), _term(ws, "heating systems")
    got = {(r["a"], r["b"]): r for r in ws.query("SELECT * FROM concept_links WHERE source='pattern'")}
    a, b = sorted((hp, gb))
    assert (a, b) in got and got[(a, b)]["relation"] == ("replaces" if a == hp else "replaced_by")
    a2, b2 = sorted((hs, hp))
    assert (a2, b2) in got and got[(a2, b2)]["relation"] == ("broader" if a2 == hs else "narrower")
    s = textrelations.sentences(ws._conn(), hp, gb)
    assert s and all("instead of" in x["quote"] for x in s) and {x["title"] for x in s}
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (s[0]["doc_id"],))
    assert " ".join(text[s[0]["start"]:s[0]["end"]].split()) == s[0]["quote"]
    # proposed, never confirmed by itself
    lk = next(x for x in terms.links(ws) if (x["a"], x["b"]) == (a, b) and x["source"] == "pattern")
    assert not lk["confirmed"]
    # the concept page shows it with its sentences, seen from the concept
    rel = terms._related(ws, [hp], terms.links(ws))
    mine = next(x for x in rel["links"] if x["term_id"] == gb)
    assert mine["relation"] == "replaces" and mine["sentences"] and mine["state"] == "proposed"
    # accepted as any link
    terms.set_link(ws, a, b, "accept")
    lk = next(x for x in terms.links(ws) if (x["a"], x["b"]) == (a, b) and x["source"] == "pattern")
    assert lk["confirmed"]
    # the decision holds when the glossary is made again
    terms.build(ws)
    lk = next(x for x in terms.links(ws) if (x["a"], x["b"]) == (a, b) and x["source"] == "pattern")
    assert lk["confirmed"]


def test_a_pair_with_a_link_already_gets_no_pattern_link(built):
    """A person's decision is kept by the pair: a pattern link beside a meaning link of the same pair would take that
    decision too (accepting "such as" would join the two as the same concept)."""
    ws = built
    hp, gb = terms.find_term(ws, "heat pumps"), terms.find_term(ws, "gas boilers")
    a, b = sorted((hp, gb))
    with ws.connect() as cx:
        cx.execute("INSERT OR REPLACE INTO concept_links VALUES (?,?,'same','meaning',0.7,NULL,NULL,NULL,'2026')", (a, b))
    terms.build(ws)
    assert ws.query("SELECT source FROM concept_links WHERE a=? AND b=?", (a, b)) and \
        not ws.query("SELECT 1 FROM concept_links WHERE a=? AND b=? AND source='pattern'", (a, b))


# ---- D1 rest: needs, shapes, clashes ---------------------------------------------------------------------------
def test_needs_shapes_and_clashes_by_their_verb_forms():
    for verb in ("requires", "required", "requiring", "needs", "needed", "depends on", "depended on", "relies on",
                 "relying on", "can depend on", "is dependent on", "are reliant on", "often needs the"):
        assert pairs(f"Remote work {verb} commuting.") == {("remote work", "commuting", "needs")}, verb
    for verb in ("shapes", "shaped", "shaping", "influences", "influenced", "influencing", "affects", "affected",
                 "affecting", "determines", "determined", "determining", "may influence"):
        assert pairs(f"A carbon tax {verb} emissions.") == {("carbon tax", "emissions", "shapes")}, verb
    for verb in ("conflicts with", "conflicted with", "clashes with", "clashed with", "is at odds with",
                 "was at odds with", "are at odds with"):
        assert pairs(f"Solar power {verb} wind power.") == {("solar power", "wind power", "clashes")}, verb
    assert pairs("Solar power needs the wind power.") == {("solar power", "wind power", "needs")}


def test_undermines_is_an_effect_not_a_clash():
    for verb in ("undermines", "undermined", "undermining"):
        assert pairs(f"A carbon tax {verb} emissions.") == {("carbon tax", "emissions", "effect")}, verb


def test_needs_to_and_quotation_marks_propose_nothing():
    assert pairs("A carbon tax needs to cut emissions.") == set()
    assert pairs("Remote work needs to reduce commuting.") == set()
    assert pairs('She wrote "remote work requires commuting" in 2019.') == set()
    assert pairs("The book “Solar power conflicts with wind power” was read.") == set()
    assert pairs("Solar power at odds with wind power was rare.") == set()


def test_the_new_relations_are_turned_round_with_the_pair():
    assert textrelations._INV["needs"] == "needed_by" and textrelations._INV["needed_by"] == "needs"
    assert textrelations._INV["shapes"] == "shaped_by" and textrelations._INV["shaped_by"] == "shapes"
    assert textrelations._INV.get("clashes", "clashes") == "clashes"
    for rel in ("needs", "needed_by", "shapes", "shaped_by", "clashes"):
        assert rel in terms.LINK_RELATIONS
    assert "clashes" not in terms._INVERSE
    for rel in ("needs", "needed_by", "shapes", "shaped_by"):
        assert terms._INVERSE[terms._INVERSE[rel]] == rel


def test_a_person_adds_the_new_links_and_sees_them_from_the_other_end(built):
    ws = built
    ep, gb, hs = _term(ws, "energy poverty"), _term(ws, "gas boilers"), _term(ws, "heating systems")
    a, b = sorted((ep, gb))   # pairs the sentences state nothing about
    terms.set_link(ws, a, b, "add", "needs")
    from_a = next(x for x in terms._related(ws, [a], terms.links(ws))["links"] if x["term_id"] == b)
    from_b = next(x for x in terms._related(ws, [b], terms.links(ws))["links"] if x["term_id"] == a)
    assert from_a["relation"] == "needs" and from_b["relation"] == "needed_by"
    # given from the larger id, it is stored from the smaller one, turned round
    terms.set_link(ws, b, a, "change", "shapes")
    assert next(x for x in terms.links(ws) if (x["a"], x["b"]) == (a, b))["relation_effective"] == "shaped_by"
    # clashes is the same from both ends
    c, d = sorted((ep, hs))
    terms.set_link(ws, d, c, "add", "clashes")
    assert next(x for x in terms._related(ws, [c], terms.links(ws))["links"] if x["term_id"] == d)["relation"] == "clashes"
    assert next(x for x in terms._related(ws, [d], terms.links(ws))["links"] if x["term_id"] == c)["relation"] == "clashes"
    with pytest.raises(ValueError):
        terms.set_link(ws, a, b, "add", "nonsense")


# ---- review finding: false links from longer terms, questions and negations ---------------------------------------
def _pairs_with(sentence: str, terms_: tuple[str, ...]) -> set[tuple[str, str, str]]:
    ms = [(m.start(), m.end(), t) for t in terms_ for m in re.finditer(r"\b" + re.escape(t) + r"\b", sentence, re.I)]
    return set(textrelations._pairs(sentence, ms))


def test_a_longer_known_term_around_the_verb_is_not_a_link():
    nt = ("training", "assessment", "training needs assessment")
    assert _pairs_with("The firm ran a training needs assessment last year.", nt) == set()
    # a separate pair of terms still links
    assert _pairs_with("Training needs the assessment.", nt) == {("training", "assessment", "needs")}


def test_a_question_or_a_negation_before_the_first_term_is_not_a_link():
    assert pairs("The study asks whether remote work affects emissions.") == set()
    assert pairs("We do not know if remote work affects emissions.") == set()
    assert pairs("Nothing in remote work conflicts with commuting.") == set()
    assert pairs("Whether or not remote work influences commuting is unclear.") == set()
    assert pairs("There is no sign that a carbon tax reduces emissions.") == set()
    assert pairs("Heat pumps never replace anything, nor gas boilers.") == set()
    assert pairs("A carbon tax without remote work needs commuting.") == set()
    # the true positives next to them
    assert pairs("Remote work affects commuting.") == {("remote work", "commuting", "shapes")}
    assert pairs("The study shows remote work conflicts with commuting.") == {("remote work", "commuting", "clashes")}
    assert pairs("Remote work needs commuting.") == {("remote work", "commuting", "needs")}
    assert pairs("The study asked a question, and remote work affects commuting.") == \
        {("remote work", "commuting", "shapes")}
    assert pairs("Whether it works is unclear, but a carbon tax reduces emissions.") == \
        {("carbon tax", "emissions", "effect")}
    assert pairs("Households chose heat pumps instead of gas boilers.") == {("heat pumps", "gas boilers", "replaces")}
    assert pairs("Nothing here: households chose heat pumps instead of gas boilers.") == \
        {("heat pumps", "gas boilers", "replaces")}


def test_negation_does_not_touch_broader_narrower_or_same():
    assert pairs("Not all renewable energy such as solar power is cheap.") == \
        {("renewable energy", "solar power", "broader")}
    assert pairs("No remote work, also called telework, was allowed.") == {("remote work", "telework", "same")}
