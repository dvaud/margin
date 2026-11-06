"""Skim one document (Margin): a one-page report made without AI, and the quick look that lands on it.

The report: facts and reading time, the abstract, sections, key sentences, the author's own aims and findings, the
statements about the world with and without a citation (its own data and results kept apart), the works it cites most,
codes, and a Markdown copy. Single-document versions: key terms weighed by how far a term runs through the document
when there is no other document; the line breaks of a PDF or a text file rebuilt from the layout."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from test_app import api, home  # noqa: F401  (fixtures)

from margin import ingest, skim, terms

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "margin" / "gui" / "static"

PAPER = """# Heat pumps in rental housing: who pays and who gains

## Abstract

This paper examines how heat pump retrofits in rental housing divide costs and savings between landlords and tenants. Using a panel of 2,400 rented homes in three cities, we find that tenants save on average 31 per cent on heating bills after a retrofit, while landlords recover their investment through higher rents within nine years. The split incentive problem is smaller than often assumed, but it persists where rents are regulated.

Keywords: heat pumps, rental housing, split incentives

## 1. Introduction

Residential heating accounts for a large share of household energy use in Europe (Eurostat, 2021). Heat pumps are widely regarded as the main technology for decarbonising heating (IEA, 2022). Yet adoption in rental housing lags far behind owner-occupied homes. The split incentive problem explains part of this gap: landlords pay for the heat pump while tenants receive the lower bills (Gillingham et al., 2012). Earlier studies found that energy efficiency investments are lower in rented dwellings than in owner-occupied ones (Davis, 2012; Gillingham et al., 2012).

The aim of this study is to measure how the costs and savings of heat pump retrofits are shared in practice. We ask whether landlords recover their investment, and how much tenants save on heating bills. In Section 2 we will describe the data.

## 2. Data and methods

The panel covers 2,400 rented homes in three cities, observed between 2015 and 2023. Retrofits were identified from installation records held by the municipal energy agencies. Heating bills come from the utility companies, and rents from the tenancy registers. We compare retrofitted homes with similar homes that kept gas boilers, using a difference-in-differences design (Angrist and Pischke, 2009).

## 3. Results

Our results show that heating bills fell by 31 per cent on average in the first full year after a heat pump retrofit. Rents rose by 4 per cent more in retrofitted homes than in comparable homes. The investment was recovered within nine years in most cases. Savings were higher in poorly insulated homes, because the heat pumps replaced old and inefficient boilers. Tenants on low incomes gained most from the lower bills.

## 4. Discussion

We conclude that the split incentive problem is smaller than often assumed. Overall, landlords do recover their investment through rents, but slowly where rents are regulated. Rent regulation therefore reduces the incentive to install heat pumps. This finding is consistent with Davis (2012) and with the review by Gillingham et al. (2012). Subsidies aimed at landlords of regulated dwellings could close the remaining gap.

## References

Angrist, J. D., and Pischke, J.-S. (2009). Mostly harmless econometrics. Princeton University Press.

Davis, L. W. (2012). Evaluating the slow adoption of energy efficient investments. https://doi.org/10.7208/chicago/9780226921983.003.0008

Eurostat (2021). Energy consumption in households.

Gillingham, K., Harding, M., and Rapson, D. (2012). Split incentives in residential energy consumption. Energy Journal 33(2). https://doi.org/10.5547/01956574.33.2.3

IEA (2022). The future of heat pumps. International Energy Agency.
"""


@pytest.fixture
def paper(home, tmp_path):
    f = tmp_path / "heat_pumps.md"
    f.write_text(PAPER, encoding="utf-8")
    ws = home.create_project("S")
    ingest.ingest(ws, [f])
    return ws, ws.scalar("SELECT doc_id FROM documents")


def _texts(items):
    return [i["text"] for i in items]


def test_the_report_reads_a_paper(paper):
    ws, did = paper
    r = skim.skim(ws, did)
    assert r["title"].startswith("Heat pumps in rental housing")
    f = r["facts"]
    assert 400 < f["words"] < 520 and f["minutes"] == 2   # the text before the reference list
    # the abstract, without the keywords after it
    a = r["abstract"]["text"]
    assert a.startswith("This paper examines") and a.endswith("where rents are regulated.") and "Keywords" not in a
    # the author's own aims and findings; "we will describe" is a plan, not a finding
    assert any(t.startswith("The aim of this study") for t in _texts(r["aims"]))
    assert any(t.startswith("We ask whether") for t in _texts(r["aims"]))
    found = _texts(r["findings"])
    assert any(t.startswith("Our results show") for t in found) and any(t.startswith("We conclude") for t in found)
    assert not any("will describe" in t for t in found + _texts(r["aims"]))
    # no sentence runs across a heading (a text file is stored with its breaks as spaces)
    every = r["aims"] + r["findings"] + r["key_sentences"] + r["claims"]["items"]
    assert not any(re.match(r"^\d\. |^(Abstract|Results|Discussion|References)\b", t) for t in _texts(every))
    # each item has its place, and its text is the document's
    text = ws.scalar("SELECT text FROM documents")
    for it in every:
        assert " ".join(text[it["start"]:it["end"]].split()) == it["text"] and it["section"]


def test_key_sentences_are_spread_and_in_order(paper):
    ws, did = paper
    r = skim.skim(ws, did)
    ks = r["key_sentences"]
    assert 3 <= len(ks) <= skim.KEY_SENTENCES
    assert [k["start"] for k in ks] == sorted(k["start"] for k in ks)
    ab = r["abstract"]
    assert not any(ab["start"] <= k["start"] < ab["end"] for k in ks)    # shown as the abstract already
    per = {}
    for k in ks:
        per[k["section"]] = per.get(k["section"], 0) + 1
        assert k["terms"]
    assert max(per.values()) <= 2 and len(per) >= 3


def test_claims_keep_its_own_results_apart(paper):
    ws, did = paper
    c = skim.skim(ws, did)["claims"]
    by = {i["text"]: i for i in c["items"]}
    rr = next(i for t, i in by.items() if t.startswith("Rents rose by 4 per cent"))
    assert rr["own"] and rr["kind"] == "statistic"                      # its own result: evidence, not a claim to source
    rent = next(i for t, i in by.items() if t.startswith("Rent regulation therefore reduces"))
    assert not rent["own"] and not rent["cited"] and rent["kind"] == "causal"
    assert any(i["cited"] and not i["own"] for i in c["items"])        # "… (Gillingham et al., 2012)."
    assert not any("Angrist" in t or "Princeton" in t for t in by)      # nothing from the reference list
    assert c["total"] == c["own"] + c["others"] and c["others"] == c["cited"] + c["uncited"]
    assert c["uncited"] >= 1


def test_works_cited_and_the_reference_list(paper):
    ws, did = paper
    r = skim.skim(ws, did)
    ci = r["cited"]
    assert ci["top"][0]["label"] == "Gillingham et al. (2012)" and ci["top"][0]["count"] == 3
    labels = [w["label"] for w in ci["top"]]
    assert "Davis (2012)" in labels and "Angrist and Pischke (2009)" in labels
    assert not any("Princeton" in x or "Rapson" in x for x in labels)    # nothing read from the reference list itself
    assert ci["dois"] == 2 and ci["references_at"] is not None
    # the sections: the title is not one; the reference list is marked
    titles = [s["title"] for s in r["outline"]]
    assert titles[0] == "Abstract" and titles[-1] == "References"
    assert [s["references"] for s in r["outline"]] == [False] * (len(titles) - 1) + [True]
    assert all(s["words"] > 0 for s in r["outline"])


def test_line_breaks_are_rebuilt_from_the_layout():
    # a PDF's line broken mid-sentence is joined; a paragraph start and a heading keep theirs; same length
    text = "Results\nHeat pumps cut the\nbills by a third. They\nwork.\n\nNext part"
    flat = skim._flatten(text, {7})
    assert len(flat) == len(text)
    assert flat.startswith("Results\nHeat pumps cut the bills by a third. They work.\n\nNext part")
    # a text file stored with spaces gets its breaks back where the layout says
    flat = skim._flatten("Results Heat pumps cut bills.", {7})
    assert flat == "Results\nHeat pumps cut bills."


def test_key_terms_of_one_document_favour_what_runs_through_it(home, tmp_path):
    # "district heating" four times in one paragraph; "heat pump" four times, once in each of four parts
    filler = ("The survey covered many households across the region and asked about their homes, their bills and "
              "their plans for the coming years in some detail. ") * 6
    paras = [f"A heat pump was installed here. {filler}" for _ in range(4)]
    paras.insert(1, "District heating, district heating, district heating and district heating were named. " + filler)
    f = tmp_path / "one.txt"
    f.write_text("\n\n".join(paras), encoding="utf-8")
    ws = home.create_project("K")
    ingest.ingest(ws, [f])
    terms.ensure(ws)
    did = ws.scalar("SELECT doc_id FROM documents")
    kt = {k["label"]: k for k in terms.key_terms(ws, doc_id=did, n=30)}
    pump = next(k for label, k in kt.items() if label.startswith("heat pump"))
    assert pump["mentions"] == kt["district heating"]["mentions"] == 4
    assert pump["score"] > 2 * kt["district heating"]["score"]
    assert skim.skim(ws, did)["key_terms"]["basis"] == "document"
    # with a second document, the corpus contrast is back
    g = tmp_path / "two.txt"
    g.write_text("Another report about wind turbines and offshore cables. " * 30, encoding="utf-8")
    ingest.ingest(ws, [g])
    assert skim.skim(ws, did)["key_terms"]["basis"] == "corpus"


def test_a_document_with_little_text(home, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("Meeting notes from the Tuesday group. Please bring the slides and the printed handouts with you. "
                 "Lunch is in the small room on the second floor after the session ends. " * 3, encoding="utf-8")
    ws = home.create_project("N")
    ingest.ingest(ws, [f])
    did = ws.scalar("SELECT doc_id FROM documents")
    r = skim.skim(ws, did)
    assert r["abstract"] is None and r["aims"] == [] and r["findings"] == [] and r["cited"]["markers"] == 0
    assert r["outline"] == [] and r["codes"] is None
    assert "# " in skim.to_markdown(r)


def test_markdown_copy(paper):
    ws, did = paper
    md = skim.to_markdown(skim.skim(ws, did))
    assert md.startswith("# Heat pumps in rental housing")
    for head in ("## Abstract", "## What it sets out to do", "## What it says it found", "## Key sentences",
                 "## Key terms", "## Sections", "## Claims about the world", "## Works it cites most"):
        assert head in md
    assert "Rent regulation therefore reduces" in md and "Rents rose by 4 per cent" not in md.split("Without a citation")[1]
    assert "without AI" in md


def test_api_and_quick_look_land_on_skim(api, home, tmp_path):  # noqa: F811
    assert api("PUT", "/api/settings", {"backend": "baseline"})[0] == 200
    st, r = api("POST", "/api/quicklook?name=heat_pumps.md", raw=PAPER.encode())
    assert st == 200 and r["project"]["temporary"]
    name = r["project"]["name"]
    job = api.wait(r["job"]["id"])
    assert job["state"] == "done"
    did = job["result"]["documents_added"][0]["doc_id"]
    st, s = api("GET", f"/api/projects/{name}/documents/{did}/skim")
    assert st == 200 and s["documents_in_project"] == 1 and s["findings"] and s["cited"]["top"]
    assert json.dumps(s)  # plain JSON
    st, body = api("GET", f"/api/projects/{name}/documents/{did}/skim.md")
    assert st == 200 and body.decode().startswith("# Heat pumps")
    assert api("GET", f"/api/projects/{name}/documents/nothing/skim")[0] == 404


def test_page_files_and_docs():
    feats = (STATIC / "features.js").read_text()
    assert re.search(r'skim: \{\s*section: "explore", title: "Skim", icon: "eye", href: "#/skim", ai: "none"', feats)
    app = (STATIC / "app.js").read_text()
    assert 'from "./views/skim.js"' in app and '"skim", renderSkim]' in app and '"skim", renderSkimIndex]' in app
    assert 'href="#/skim" data-route="skim"' in (STATIC / "index.html").read_text()
    ql = (STATIC / "views" / "quicklook.js").read_text()
    assert "navigate(`#/skim/${encodeURIComponent(added[0].doc_id)}`)" in ql
    assert "#/skim/${encodeURIComponent(docId)}" in (STATIC / "views" / "sources.js").read_text()
    page = (STATIC / "views" / "skim.js").read_text()
    assert "/skim.md" in page or "`${base}.md`" in page
    css = (STATIC / "margin.css").read_text()
    assert ".sk-grid" in css and "@media (max-width: 600px)" in css.split("==== skim")[1]
    assert "/skim" in (ROOT / "docs" / "API.md").read_text()
    assert "Skim" in (ROOT / "docs" / "MANUAL.md").read_text()
    from margin.gui.server import ROUTES
    names = {r[2] for r in ROUTES}
    assert {"get_document_skim", "get_document_skim_md"} <= names


def test_a_pdf_without_headings_leaves_out_its_references(home, corpus):  # noqa: F811
    # the suite's three-page PDF: no headings, a reference list without a heading, the DOI on the title line
    ws = home.create_project("P")
    ingest.ingest(ws, [corpus / "paper_a.pdf"])
    did = ws.scalar("SELECT doc_id FROM documents")
    r = skim.skim(ws, did)
    every = r["key_sentences"] + r["aims"] + r["findings"] + r["claims"]["items"]
    assert every and not any("doi.org" in t or "http" in t for t in _texts(every))
    assert not any(re.search(r"\d{4};\d+\(\d\)", t) for t in _texts(every))   # "J Hydrogen 2020;12(3):45-60."
    assert any("water stress" in t for t in _texts(r["claims"]["items"]))
    assert all(i["page"] for i in every)


def test_lines_that_are_not_sentences_are_left_out():
    # found on the pilot's 300-page reports: contents pages, captions, running heads, tables
    for s in ("FIGURE 5.20 Distributional index under the 1.5°C Scenario, by indicator ........ 241",
              "TACKLING THE ENERGY ACCESS DEFICIT IN AFRICA THE WAY FORWARD 06 07",
              "WORLD ENERGY TRANSITIONS OUTLOOK FIGURE 5.20 Distributional index under the scenario.",
              "Chapter 4 | Implications of a sustainable African energy system 197 alone by 2030.",
              "2015 2016 2017 2018 2019 2020 12.4 13.1 14.0 15.2 of the total."):
        assert skim._junk(s), s
    for s in ("Our results show that heating bills fell by 31 per cent.",
              "By 2050, the Energy Transition Welfare Index is 11% higher under the 1.5°C Scenario."):
        assert not skim._junk(s), s
    assert skim._NOT_AUTHORS.match("USD") and not skim._NOT_AUTHORS.match("UNDP")
