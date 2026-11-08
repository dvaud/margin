"""Margin 0.14 (roadmap C4): an outline from a research question and hypotheses, with no AI.

Each hypothesis becomes a section holding the themes that bear on it most: the passages its check counts for or
against it first, then the key terms it shares (rarer words weigh more; a concept's other wordings count), then - only
when asked, with an embedding model on this computer - closeness by meaning. Themes that bear only on the question go
under Background; the others stay out. A hypothesis section is linked to its check by its wording, so a check made
later shows up; hypotheses can be added afterwards and take themes from Background, never from another hypothesis."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from test_0_14_0_remove_themes import topic_of, topics_corpus
from test_app import api, home  # noqa: F401  (fixtures)
from test_m0_10_0_outline import _app_project, _flat, _Local

from margin import claimcheck, embed, ingest, outline, themes
from margin.llm import BaselineBackend

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "margin" / "gui" / "static"


@pytest.fixture
def project(home, tmp_path):
    ws = home.create_project("Q")
    ingest.ingest(ws, [topics_corpus(tmp_path / "topics")])
    return ws


@pytest.fixture
def run(project):
    return themes.run(project, k=6, seed=0, mode="words")


def _themes_by_topic(ws, run_id) -> dict[str, int]:
    """{topic: theme id}: the topic most of a theme's passages are about."""
    r = outline._Run(ws, run_id)
    tops = topic_of(ws)
    out = {}
    for tid, ms in r.members.items():
        if tid not in r.info:
            continue
        counts: dict[str, int] = {}
        for _s, pid, _d in ms:
            counts[tops.get(pid, "")] = counts.get(tops.get(pid, ""), 0) + 1
        out[max(counts, key=counts.get)] = tid
    return out


def _term(ws, run_id, topic) -> str:
    """A key term of the topic's theme whose words no other theme's key terms use."""
    r = outline._Run(ws, run_id)
    rel = outline._Relevance(ws, r)
    tid = _themes_by_topic(ws, run_id)[topic]
    for lab, st in rel.terms[tid]:
        if st and all(rel.df[s] == 1 for s in st):
            return lab
    raise AssertionError(f"no distinctive key term for {topic}")


def _sections_of(v, kind):
    return [n for n in _flat(v) if n["kind"] == kind]


def _theme_ids(node):
    return [c["themes"][0]["theme_id"] for c in node["children"] if c["kind"] == "theme"]


# ---------------------------------------------------------------------------------------------
# placing the themes
# ---------------------------------------------------------------------------------------------
def test_a_checked_hypothesis_holds_the_themes_its_evidence_is_in(project, run):
    by = _themes_by_topic(project, run)
    text = "Desalination depends on brine disposal and groundwater."
    hid = claimcheck.check_hypothesis(project, text, BaselineBackend(), "baseline", k=6, per_doc=2)
    assert claimcheck.hypothesis_result(project, hid)["status"] == "supported"
    r = outline.create_from_question(project, run, "What limits water supply in the region?", [text])
    v = outline.view(project, r["outline_id"])
    assert v["outline"]["question"] == "What limits water supply in the region?"
    assert v["outline"]["title"] == "What limits water supply in the region?"
    h = v["sections"][0]
    assert h["kind"] == "hypothesis" and h["title"] == text and h["title_source"] == "hypothesis"
    assert h["hypothesis"]["checked"] and h["hypothesis"]["hyp_id"] == hid and h["hypothesis"]["status"] == "supported"
    assert h["hypothesis"]["evidence"] > 0 and h["hypothesis"]["sides"]["supports"] and h["documents"] == 2
    assert by["water"] in _theme_ids(h)
    water = next(c for c in h["children"] if c["themes"][0]["theme_id"] == by["water"])
    assert water["relevance"]["to"] == "hypothesis" and water["relevance"]["evidence"] > 0 and water["relevance"]["related"]
    assert not [g for g in h["gaps"] if g["kind"] in ("unchecked", "no-themes")]
    # themes about nothing asked stay out, and say what they share with the question
    out_ids = {a["theme_id"] for a in v["available_themes"]}
    assert by["birds"] in out_ids and by["finance"] in out_ids and r["left_out"] == len(out_ids)
    assert all("shares" in a and "bears_on" in a for a in v["available_themes"])


def test_an_unchecked_hypothesis_is_placed_by_its_words_and_finds_its_check_later(project, run):
    by = _themes_by_topic(project, run)
    term = _term(project, run, "health")
    text = f"More {term} would improve care."
    r = outline.create_from_question(project, run, "What shapes care in the region?", [text])
    v = outline.view(project, r["outline_id"])
    h = v["sections"][0]
    assert not h["hypothesis"]["checked"] and h["hypothesis"]["hyp_id"] is None
    assert [g["kind"] for g in h["gaps"]][:1] == ["unchecked"]
    assert _theme_ids(h) == [by["health"]]
    rel = h["children"][0]["relevance"]
    assert rel["evidence"] == 0 and term in rel["terms"]
    # checked later with the same wording (case, spaces and the full stop aside): the outline shows the check
    hid = claimcheck.check_hypothesis(project, f"  more {term} would   improve care", BaselineBackend(), "baseline", k=6)
    h = outline.view(project, r["outline_id"])["sections"][0]
    assert h["hypothesis"]["checked"] and h["hypothesis"]["hyp_id"] == hid
    assert outline.find_check(project, text.upper()) == hid and outline.find_check(project, "something else") is None


def test_without_hypotheses_the_question_picks_the_themes(project, run):
    by = _themes_by_topic(project, run)
    q = f"How do {_term(project, run, 'water')} and {_term(project, run, 'jobs')} matter?"
    r = outline.create_from_question(project, run, q)
    v = outline.view(project, r["outline_id"])
    top = v["sections"]
    assert {s["themes"][0]["theme_id"] for s in top} == {by["water"], by["jobs"]}
    assert all(s["kind"] == "theme" and s["relevance"]["to"] == "question" for s in top)
    assert not _sections_of(v, "hypothesis") and r["placed"] == 2
    with pytest.raises(ValueError, match="No theme shares a key term"):
        outline.create_from_question(project, run, "Why do volcanoes erupt?")
    with pytest.raises(ValueError, match="research question"):
        outline.create_from_question(project, run, "   ")
    with pytest.raises(ValueError, match="at most 12"):
        outline.create_from_question(project, run, q, [f"Hypothesis {i}" for i in range(13)])
    with pytest.raises(KeyError):
        outline.create_from_question(project, run + "x", q)


def test_themes_of_the_question_only_go_under_background(project, run):
    by = _themes_by_topic(project, run)
    hyp = f"{_term(project, run, 'water')} is scarce."
    q = f"How do {_term(project, run, 'transport')} and water matter?"
    v = outline.view(project, outline.create_from_question(project, run, q, [hyp])["outline_id"])
    assert [s["kind"] for s in v["sections"]] == ["hypothesis", "own"]
    back = v["sections"][1]
    assert back["title"] == outline.BACKGROUND and _theme_ids(back) == [by["transport"]]
    assert back["children"][0]["relevance"]["to"] == "question"
    assert _theme_ids(v["sections"][0]) == [by["water"]]


def test_each_theme_goes_to_the_hypothesis_it_bears_on_most_and_names_the_others(project, run):
    by = _themes_by_topic(project, run)
    w = _term(project, run, "water")
    j = _term(project, run, "jobs")
    h1 = f"{w} matters for {j}."           # bears on both by its words
    hid = claimcheck.check_hypothesis(project, "Desalination depends on brine disposal and groundwater.",
                                      BaselineBackend(), "baseline", k=6, per_doc=2)
    h2 = claimcheck.hypothesis_result(project, hid)["text"]       # bears on water by its evidence too
    v = outline.view(project, outline.create_from_question(project, run, "Water and work?", [h1, h2])["outline_id"])
    a, b = v["sections"]
    assert by["water"] in _theme_ids(b) and by["jobs"] in _theme_ids(a)          # evidence weighs most
    water = next(c for c in b["children"] if c["themes"][0]["theme_id"] == by["water"])
    assert [x["number"] for x in water["relevance"]["also"]] == ["1"]


def test_rarer_words_weigh_more_and_concepts_count_their_other_wordings(project, run):
    r = outline._Run(project, run)
    rel = outline._Relevance(project, r)
    by = _themes_by_topic(project, run)
    term = _term(project, run, "birds")
    got = rel.of(f"The {term}.")
    assert got[by["birds"]]["related"] and term in got[by["birds"]]["terms"] and got[by["birds"]]["words"] >= 1.0
    common = max(rel.df, key=rel.df.get)          # a word in the key terms of many themes
    assert rel.df[common] > 1
    shared = rel.of(common)
    assert all(x["words"] < outline.WORDS_RELATED for x in shared.values())
    # a concept: a word of the hypothesis joined by a 'same' link to a key term of the health theme
    target = _term(project, run, "health")
    with project.connect() as cx:
        cx.execute("INSERT INTO terms(term_id, label, stems, n_words, df, tf, passages, cvalue) "
                   "VALUES ('tx', 'medical care', 'medic care', 2, 1, 1, 1, 1)")
        tid = project.scalar("SELECT term_id FROM terms WHERE label=?", (target,))
        cx.execute("INSERT INTO concepts VALUES ('cx', 'care')")
        cx.executemany("INSERT INTO concept_terms VALUES ('cx', ?, 'person')", [("tx",), (tid,)])
    got = outline._Relevance(project, r).of("Medical care is short.")
    assert got[by["health"]]["related"] and target in got[by["health"]]["terms"]


def test_closeness_by_meaning_only_when_asked_and_with_a_local_model(project, run, monkeypatch):
    from margin import home as home_

    fake = _Local()
    settings = {"embed_backend": "ollama", "embed_model": fake.model}
    monkeypatch.setattr(home_, "make_embedder", lambda s: fake if s.get("embed_backend") != "off" else None)
    by = _themes_by_topic(project, run)
    q = "Which patients need hospitals and clinics?"     # one-hot 'health' for the fake model
    r = outline.create_from_question(project, run, q, meaning=True, settings=settings)
    assert r["meaning"] == {"used": False, "why": r["meaning"]["why"]} and "no vectors" in r["meaning"]["why"]
    with project.connect() as cx:
        for p in project.query("SELECT passage_id, text FROM passages WHERE section='body'"):
            cx.execute("INSERT INTO embeddings VALUES (?,?,?)",
                       (fake.model, p["passage_id"], embed._unit(fake.embed([p["text"]])[0]).tobytes()))
    fake.calls = 0
    r = outline.create_from_question(project, run, "Which care matters most?", [q], meaning=True, settings=settings)
    assert r["meaning"]["used"] and fake.calls == 2
    h = outline.view(project, r["outline_id"])["sections"][0]
    assert by["health"] in _theme_ids(h)
    node = next(c for c in h["children"] if c["themes"][0]["theme_id"] == by["health"])
    assert node["relevance"]["meaning"] > 0.9
    fake.calls = 0
    outline.create_from_question(project, run, q, settings=settings)
    assert fake.calls == 0                                   # not asked: nothing embedded
    fake.base_url = "https://embeddings.example.com/v1"
    far = outline.create_from_question(project, run, q, meaning=True, settings=settings)
    assert not far["meaning"]["used"] and "another computer" in far["meaning"]["why"] and fake.calls == 0


# ---------------------------------------------------------------------------------------------
# changing it
# ---------------------------------------------------------------------------------------------
def test_adding_a_hypothesis_takes_themes_from_background_and_the_unplaced_only(project, run):
    by = _themes_by_topic(project, run)
    w, t, hl = (_term(project, run, x) for x in ("water", "transport", "health"))
    oid = outline.create_from_question(project, run, f"How do {t} and water matter?", [f"{w} is scarce."])["outline_id"]
    got = outline.add_hypothesis(project, oid, f"{t} and {hl} and {w} go together.")
    assert got["themes"] == 2                                # transport from Background, health from outside
    v = outline.view(project, oid)
    kinds = [(s["kind"], s["title"]) for s in v["sections"]]
    assert [k for k, _t in kinds] == ["hypothesis", "hypothesis", "own"]      # before Background
    new = v["sections"][1]
    assert set(_theme_ids(new)) == {by["transport"], by["health"]}
    assert by["water"] in _theme_ids(v["sections"][0])        # never taken from another hypothesis
    assert v["sections"][2]["children"] == []
    with pytest.raises(ValueError, match="already"):
        outline.add_hypothesis(project, oid, f"{w.upper()} is scarce")
    with pytest.raises(ValueError, match="Write the hypothesis"):
        outline.add_hypothesis(project, oid, " ")
    plain = outline.create(project, run)
    with pytest.raises(ValueError, match="research question"):
        outline.add_hypothesis(project, plain, "Anything.")
    with pytest.raises(ValueError, match="all the themes"):
        outline.update(project, plain, question="Why?")
    outline.update(project, oid, question=f"How do {t} and {hl} matter?")
    assert outline.view(project, oid)["outline"]["question"] == f"How do {t} and {hl} matter?"


def test_hypothesis_sections_cannot_be_merged_or_split_and_reordering_keeps_your_order(project, run):
    w, j = _term(project, run, "water"), _term(project, run, "jobs")
    oid = outline.create_from_question(project, run, "Water and work?", [f"{w} first.", f"{j} second."])["outline_id"]
    v = outline.view(project, oid)
    a, b = v["sections"]
    with pytest.raises(ValueError, match="cannot be joined"):
        outline.merge(project, oid, a["section_id"], b["section_id"])
    with pytest.raises(ValueError, match="hypothesis section holds"):
        outline.split(project, oid, a["section_id"])
    # a theme joined into a hypothesis section keeps it a hypothesis section
    outline.merge(project, oid, b["children"][0]["section_id"], a["section_id"])
    assert outline.view(project, oid)["sections"][0]["kind"] == "hypothesis"
    outline.move(project, oid, b["section_id"], None, 0)
    outline.reorder(project, oid)
    assert [s["title"] for s in outline.view(project, oid)["sections"]] == [f"{j} second.", f"{w} first."]
    outline.update_section(project, oid, a["section_id"], title="")       # a hypothesis heading comes back
    assert any(s["title"] == f"{w} first." for s in outline.view(project, oid)["sections"])


def test_the_downloads_carry_the_question_the_checks_and_why_each_theme_is_there(project, run):
    text = "Desalination depends on brine disposal and groundwater."
    claimcheck.check_hypothesis(project, text, BaselineBackend(), "baseline", k=6, per_doc=2)
    oid = outline.create_from_question(project, run, "What limits water supply?", [text, "Nobody knows."])["outline_id"]
    md = outline.to_markdown(outline.document(project, oid))
    assert "**Research question:** What limits water supply?" in md
    assert f"## 1 {text}" in md and "**Check:** Supported by your documents" in md and "- Supported by: " in md
    assert "**Check:** Not checked yet." in md and re.search(r"\*\*Why here:\*\* \d+ passages? of the check", md)
    assert "Research question" not in outline.to_markdown(outline.document(project, outline.create(project, run)))
    assert "Check:" not in outline.to_markdown(outline.document(project, oid, include=("terms",)))


def test_an_old_project_gains_the_new_columns(project):
    cols = {r[1] for r in project.query("PRAGMA table_info(outline_sections)")}
    assert {"hypothesis", "basis_json"} <= cols
    assert "question" in {r[1] for r in project.query("PRAGMA table_info(outlines)")}


# ---------------------------------------------------------------------------------------------
# the app
# ---------------------------------------------------------------------------------------------
def test_the_api(api, tmp_path):
    _app_project(api, tmp_path)
    base = "/api/projects/P/outlines"
    rid = api.wait(api("POST", "/api/projects/P/themes", {"k": 6})[1]["job"]["id"])["result"]["run_id"]
    st, r = api("POST", base, {"run_id": rid, "question": "Why do volcanoes erupt?"})
    assert st == 400 and "No theme shares" in r["error"]
    assert api("POST", base, {"run_id": rid, "question": "Water?", "hypotheses": "one"})[0] == 400
    st, r = api("POST", base, {"run_id": rid, "question": "Where does water come from?",
                               "hypotheses": ["Groundwater and aquifer depletion matter.", "Wages follow unions."]})
    assert st == 200 and r["placed"] >= 1 and r["meaning"] is None
    oid = r["outline_id"]
    st, v = api("GET", f"{base}/{oid}")
    assert st == 200 and v["outline"]["question"] == "Where does water come from?"
    assert [s["kind"] for s in v["sections"]][:2] == ["hypothesis", "hypothesis"]
    assert v["sections"][0]["hypothesis"]["checked"] is False
    st, r = api("POST", f"{base}/{oid}/hypotheses", {"text": "Hospitals need nurses."})
    assert st == 200 and "section_id" in r and "themes" in r
    assert api("POST", f"{base}/{oid}/hypotheses", {"text": ""})[0] == 400
    assert api("POST", f"{base}/nope/hypotheses", {"text": "x"})[0] == 404
    assert api("PUT", f"{base}/{oid}", {"question": "Where does the water go?"})[0] == 200
    st, r = api("POST", base, {"run_id": rid, "question": "Water?", "hypotheses": ["Anything."], "meaning": True})
    assert st == 200 and r["meaning"]["used"] is False                       # search by meaning is off here
    st, md = api("GET", f"{base}/{oid}/export.md?include=checks")
    assert st == 200 and b"Research question" in md and b"Not checked yet" in md
    plain = api("POST", base, {"run_id": rid})[1]["outline_id"]           # without a question: as before
    assert api("GET", f"{base}/{plain}")[1]["outline"]["question"] is None
    assert api("PUT", f"{base}/{plain}", {"question": "Why?"})[0] == 400


def test_the_page_offers_it():
    view = (STATIC / "views" / "outline.js").read_text(encoding="utf-8")
    for text in ("From a research question", "From all the themes", "Research question", "Add a hypothesis",
                 "Check it", "Why here", "Background", "Also bears on", "Add one you checked", "/hypotheses"):
        assert text in view, text
    assert "#/check?text=" in view
    css = (STATIC / "margin.css").read_text(encoding="utf-8")
    assert ".ol-question" in css and ".ol-item.ol-hyp" in css
    features = (STATIC / "features.js").read_text(encoding="utf-8")
    assert "research question" in features.split("outline: {")[1].split("},")[0]
    manual = (ROOT / "docs" / "MANUAL.md").read_text(encoding="utf-8")
    assert "From a research question" in manual
    assert "/hypotheses {text}" in (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
