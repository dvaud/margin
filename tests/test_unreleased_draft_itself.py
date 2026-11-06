"""Your draft against itself (Margin, no AI): where a draft may contradict itself, what is inconsistent in it, and the
claims a reader may find confusing, from its own sentences and what Margin already has for it (the claims found, their
checks, the person's decisions). Each rule is careful: contrasts the draft draws on purpose are left out, a PDF's
stray spaces and line-break hyphens are not spelling, and a notice set aside stays aside."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from test_app import api, home  # noqa: F401  (fixtures)
from margin_static import section, sections

from margin import claimcheck, consistency, drafts
from margin.llm import BaselineBackend

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"


def _review(ws, text, rules=True):
    did = drafts.new_draft(ws, text, ai_access="none")
    if rules:
        drafts.find_by_rules(ws, did)
    return did, consistency.review(ws, did)


def _kinds(r, kind):
    return [n for n in r["notices"] if n["kind"] == kind]


def test_sentences_that_go_opposite_ways(ws):
    text = ("Green hydrogen production costs in Europe fell sharply between 2020 and 2023. Electrolysers need "
            "large amounts of water. Public acceptance of hydrogen pipelines is high among rural households. "
            "Ammonia is a likely carrier for shipping. Green hydrogen production costs in Europe rose sharply between "
            "2020 and 2023. Public acceptance of hydrogen pipelines is not high among rural households. Subsidies are "
            "effective for early electrolyser projects. Many ports plan terminals. Subsidies are ineffective for "
            "early electrolyser projects.")
    did, r = _review(ws, text)
    opp = _kinds(r, "opposite")
    quotes = [{p["quote"][:40] for p in n["places"]} for n in opp]
    assert len(opp) == 3, quotes
    assert all(n["group"] == "contradiction" and len(n["places"]) == 2 for n in opp)
    texts = " ".join(n["text"] for n in opp)
    assert "opposite way" in texts and "“not”" in texts and "“ineffective”" in texts
    # each place is where the sentence is in the draft
    for n in opp:
        for p in n["places"]:
            assert " ".join(text[p["start"]:p["end"]].split()) == p["quote"]
    assert r["counts"]["contradiction"] == 3 and r["open"] == len(r["notices"])


@pytest.mark.parametrize("second", [
    "However, green hydrogen production costs in Europe rose sharply between 2020 and 2023.",  # a contrast drawn
    "Some argue that green hydrogen production costs in Europe rose sharply between 2020 and 2023.",  # a view reported
    "Green hydrogen production costs in Japan rose sharply between 2020 and 2023.",  # about something else
])
def test_contrasts_drawn_on_purpose_are_left_out(ws, second):
    text = f"Green hydrogen production costs in Europe fell sharply between 2020 and 2023. {second}"
    assert not _kinds(_review(ws, text)[1], "opposite")


def test_two_works_cited_for_two_sides_is_a_debate_not_a_contradiction(ws):
    text = ("Green hydrogen production costs in Europe fell sharply after 2020 (Smith, 2021). Green hydrogen "
            "production costs in Europe rose sharply after 2020 (Jones, 2022).")
    assert not _kinds(_review(ws, text)[1], "opposite")


def test_the_same_thing_with_two_numbers(ws):
    text = ("Electrolyser capacity in the European Union grew by 40% over the same period. Prices of electricity "
            "matter most. Electrolyser capacity in the European Union grew by 25% over the same period. "
            "Electrolyser capacity in the European Union grew by 10% in 2021. Electrolyser capacity in the European "
            "Union grew by 30% in 2022.")
    nums = _kinds(_review(ws, text)[1], "numbers")
    assert len(nums) == 1 and "40%" in nums[0]["text"] and "25%" in nums[0]["text"]  # two years: two moments


def test_page_numbers_and_captions_are_not_numbers_that_differ(ws):
    text = ("12 RENEWABLE ENERGY MARKET ANALYSIS AFRICA AND ITS REGIONS Africa is at a crossroads.\n"
            "48 RENEWABLE ENERGY MARKET ANALYSIS AFRICA AND ITS REGIONS Africa is at a crossroads.\n"
            "Figure 3 Hydrogen demand in industry in 2030 by region (Mt).\n"
            "Figure 4 Hydrogen demand in industry in 2030 by region (Mt).\n"
            "Hydrogen demand grows steadily in every scenario considered here.")
    r = _review(ws, text)[1]
    assert not _kinds(r, "numbers") and not _kinds(r, "opposite")


def test_abbreviations_used_early_or_spelt_out_two_ways(ws):
    text = ("Countries report on the SDG targets every year. The Sustainable Development Goals (SDGs) frame this "
            "chapter.\n\nTHE ROLE OF LNG IN EXPORT MARKETS\n\nThe levelised cost of hydrogen (LCOH) is the main "
            "measure used here. Shipping relies on liquefied natural gas (LNG) today. Later, liquified natural gas "
            "(LNG) terminals may be converted. The International Energy Agency (IEA) and the International E nergy "
            "Agency (IEA) agree.")
    r = _review(ws, text)[1]
    late = _kinds(r, "abbrev_late")
    assert [n["text"].split("”")[0].strip("“") for n in late] == ["SDG"]  # not LNG: its use is in a heading
    assert "Sustainable Development Goals" in late[0]["text"] and late[0]["group"] == "inconsistency"
    twice = _kinds(r, "abbrev_twice")
    assert len(twice) == 1 and "liquified" in twice[0]["text"] and "liquefied" in twice[0]["text"]  # IEA: one form


def test_one_word_written_two_ways(ws):
    text = ("The organisation of the market matters, and the organization of grids matters too. We used a data set "
            "of 40 plants; the dataset is public, and the data were cleaned. Each set of plants was weighed. "
            "Large-scale projects differ from projects on a large scale. The World Health Organization reports "
            "on air quality, and the organisation of grids is regional. Smart meters measure use in metres of pipe.\n\n"
            "References\n\nSmith, J. (2021). The organization of hydrogen markets. Energy Policy, 12, 1-9.\n")
    r = _review(ws, text)[1]
    sp = {tuple(sorted(n["text"].split("”")[i].split("“")[-1] for i in (0, 1))) for n in _kinds(r, "spelling")}
    assert sp == {("organisation", "organization"), ("data set", "dataset")}, sp
    org = next(n for n in _kinds(r, "spelling") if "organisation" in n["text"])
    assert "(twice)" in org["text"] and "organization” (once)" in org["text"]  # not the name, not the reference list


def test_pdf_artefacts_are_not_spelling(ws):
    text = ("Early-stage projects need support, and early-stage firms need loans; one earlystage fund helps. "
            + "The energy system changes. " * 30 + "The ene rgy system changes too. Energy matters, ene rgy too. "
            "Rgy is not a word. Ene is not a word.")
    assert not _kinds(_review(ws, text)[1], "spelling")


def test_claims_a_reader_may_find_confusing(ws):
    text = ("Hydrogen demand will grow by 2030 in most markets. This shows that subsidies are the main driver of "
            "demand in Europe. It is unclear whether costs will fall further by 2030. Electrolysers will probably "
            "and certainly become cheaper than steam reforming by 2030. Studies show that hydrogen raises local "
            "water stress, which leads to conflicts over water, while costs fall faster than expected and exports "
            "grow more than forecast because ports compete for buyers in Asia, Europe and North America, so that "
            "most of the planned projects in deserts depend on desalination, which in turn is the largest share of "
            "the cost of water in every export region studied so far.")
    r = _review(ws, text)[1]
    kinds = {n["kind"]: n for n in r["notices"] if n["group"] == "unclear"}
    assert set(kinds) == {"pronoun", "strength", "overloaded"}, kinds
    assert kinds["pronoun"]["places"][0]["quote"].startswith("This shows")  # "It is unclear whether": not one
    assert "“probably”" in kinds["strength"]["text"] and "“certainly”" in kinds["strength"]["text"]
    # on the draft's claims: a notice names the claim it is about
    assert any(n["places"][0]["claim_id"] for n in kinds.values())


def test_without_claims_the_sentences_rules_pick_are_read(ws):
    text = "Hydrogen demand will grow by 2030 in most markets. This shows that subsidies drove 40% of the demand."
    r = _review(ws, text, rules=False)[1]
    assert r["read"]["claims"] == 0 and _kinds(r, "pronoun") and _kinds(r, "pronoun")[0]["places"][0]["claim_id"] is None


def test_two_claims_with_opposite_decisions(ws):
    text = ("Green hydrogen exports from deserts need large amounts of desalinated water (Smith, 2021). Other "
            "things are discussed in between. Green hydrogen exports from deserts need large amounts of desalinated "
            "water in practice (Smith, 2021).")
    did = drafts.new_draft(ws, text, ai_access="none")
    a = drafts.add_claim(ws, did, 0, text.index(" Other"))
    s = text.index("Green", 10)
    b = drafts.add_claim(ws, did, s, len(text))
    drafts.update_claim(ws, did, a, decision="supported")
    drafts.update_claim(ws, did, b, decision="refuted")
    r = consistency.review(ws, did)
    n = _kinds(r, "answers_differ")
    assert len(n) == 1 and {p["claim_id"] for p in n[0]["places"]} == {a, b} and "you marked" in n[0]["text"]


def test_one_passage_supports_one_claim_and_contradicts_another(loaded):
    text = ("Electrolysis needs about 9 litres of water for every kilogram of hydrogen. Other things come in "
            "between. Electrolysis needs little water for every kilogram of hydrogen in arid regions.")
    did = drafts.new_draft(loaded, text, ai_access="none")
    a = drafts.add_claim(loaded, did, 0, text.index(" Other"))
    b = drafts.add_claim(loaded, did, text.index("Electrolysis", 10), len(text))
    out = drafts.check_claims(loaded, did, BaselineBackend(), "baseline", k=4, per_doc=2)
    assert len(out["checked"]) == 2
    rows = {r["claim_id"]: r["hyp_id"] for r in loaded.query("SELECT claim_id, hyp_id FROM draft_claims "
                                                              "WHERE draft_id=?", (did,))}

    def passages(hid):
        res = claimcheck.hypothesis_result(loaded, hid)
        return res["parts"][0]["claim_id"], [x["passage_id"] for x in res["parts"][0]["passages"]]

    ca, pa = passages(rows[a])
    cb, pb = passages(rows[b])
    shared = next(p for p in pa if p in pb)
    claimcheck.set_judgement(loaded, ca, shared, "supports")
    claimcheck.set_judgement(loaded, cb, shared, "refutes")
    n = _kinds(consistency.review(loaded, did), "same_passage")
    assert len(n) == 1 and {p["claim_id"] for p in n[0]["places"]} == {a, b}
    assert "supports the first and contradicts the second" in n[0]["text"]


def test_setting_a_notice_aside(ws):
    text = ("Subsidies are effective for early electrolyser projects. Subsidies are ineffective for early "
            "electrolyser projects.")
    did, r = _review(ws, text)
    key = r["notices"][0]["key"]
    consistency.set_dismissed(ws, did, key)
    again = consistency.review(ws, did)
    assert again["notices"][0]["dismissed"] and again["dismissed"] == 1 and again["open"] == len(again["notices"]) - 1
    assert again["notices"][0]["key"] == key  # the same notice, found again
    consistency.set_dismissed(ws, did, key, False)
    assert not consistency.review(ws, did)["dismissed"]
    with pytest.raises(ValueError):
        consistency.set_dismissed(ws, did, "../x")
    with pytest.raises(KeyError):
        consistency.set_dismissed(ws, "dnothing", key)
    consistency.set_dismissed(ws, did, key)
    drafts.delete(ws, did)
    assert not ws.query("SELECT 1 FROM draft_notices WHERE draft_id=?", (did,))


def test_a_long_draft_is_read_quickly(ws):
    words = ["hydrogen", "water", "cost", "port", "export", "solar", "wind", "grid", "ammonia", "steel", "policy",
             "tariff", "storage", "pipeline", "demand", "supply", "region", "market", "price", "loan"]
    sents = [f"The {words[i % 20]} {words[(i * 7) % 20]} of {words[(i * 3) % 20]} rose by {i % 50}% near "
             f"{words[(i * 11) % 20]} {words[(i * 13) % 20]} sites." for i in range(2500)]
    text = "\n\n".join(" ".join(sents[i:i + 5]) for i in range(0, len(sents), 5))
    did = drafts.new_draft(ws, text[:drafts.MAX_CHARS], ai_access="none")
    t = time.time()
    r = consistency.review(ws, did)
    assert time.time() - t < 20 and r["read"]["sentences"] > 1000
    assert all(sum(1 for n in r["notices"] if n["kind"] == k) <= consistency.MAX_PER_KIND for k in consistency.KINDS)


def test_the_api(api, ws):  # noqa: F811
    assert api("POST", "/api/projects", {"name": "P"})[0] == 200
    text = ("Subsidies are effective for early electrolyser projects. Subsidies are ineffective for early "
            "electrolyser projects.")
    st, r = api("POST", "/api/projects/P/drafts", {"text": text, "ai_access": "none"})
    did = r["draft"]["draft_id"]
    st, c = api("GET", f"/api/projects/P/drafts/{did}/consistency")
    assert st == 200 and c["counts"]["contradiction"] == 1 and set(c["groups"]) == set(consistency.GROUPS)
    key = c["notices"][0]["key"]
    st, out = api("PUT", f"/api/projects/P/drafts/{did}/notices/{key}", {"dismissed": True})
    assert st == 200 and out["dismissed"] is True
    assert api("GET", f"/api/projects/P/drafts/{did}/consistency")[1]["dismissed"] == 1
    assert api("PUT", f"/api/projects/P/drafts/{did}/notices/nonsense", {})[0] == 400
    assert api("GET", "/api/projects/P/drafts/dnothing/consistency")[0] == 404
    assert "/consistency" in (Path(__file__).resolve().parent.parent / "docs" / "API.md").read_text()


def test_the_page_files():
    js = (STATIC / "views" / "drafts.js").read_text()
    assert "/consistency" in js and "/notices/" in js and "Your draft against itself" in js
    assert "Not a problem" in js and 'CSS.highlights.set("draft-self"' in js and 'CSS.highlights.delete("draft-self")' in js
    order = sections()
    assert order.index("self") < order.index("m020")  # Margin's look still comes after it
    css = section("self")
    assert "::highlight(draft-self)" in css and "@media (max-width: 600px)" in css
    assert not any(ch in css for ch in ("rgb(", "#fff", "#000"))
