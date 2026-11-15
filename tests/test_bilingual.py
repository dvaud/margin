"""0.19: a document in two languages (a side-by-side translation): keep one, and reader 6 keeps them apart.

- `languages.survey` finds a document's two languages; `block_languages` says each block's, a title printed in both
  is *mixed*, a block that does not tell takes the language of the blocks on either side when they agree;
- *Keep only English* (`PUT …/language`) leaves the Spanish blocks out, kept as the block choice `lang:en`; a block the
  person restores keeps their choice; *Count both again* takes it back; the research log says so;
- reader 6 never puts both languages into one passage (reader 5 did, where a Spanish column ended without a full stop
  and the English one went on in lower case); a document in one language reads exactly as reader 5 read it;
- a document reader 5 read is offered the new reader only when one of its passages holds both languages;
- between copies, one language is kept, never two, and a proposal says which.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from margin import ingest, languages, measure, pdfmake, reader, reread
from margin.store import Workspace

from test_app import Api, api, home  # noqa: F401  (fixtures)
from margin import home as margin_home

ES = [
    "Los huertos comunitarios son espacios donde los vecinos cultivan alimentos juntos y comparten las tareas del "
    "cuidado. En este artículo estudiamos cómo se organizan los voluntarios de tres huertos de la ciudad, qué problemas "
    "encuentran y por qué algunos proyectos desaparecen después de pocos años, a pesar del entusiasmo de sus fundadores.",
    "Durante seis meses observamos las jornadas de trabajo de los sábados y realizamos doce entrevistas con voluntarios "
    "y coordinadores. Las notas de campo y las transcripciones se analizaron de forma temática, y los temas se "
    "discutieron en sesiones de datos con todo el equipo de investigación.",
    "Los coordinadores miden el éxito de cada temporada contando las cosechas y el número de personas que participan "
    "en las jornadas de trabajo. Uno de ellos lo explicó así:",
    "La falta de tiempo es el problema más citado. Los voluntarios trabajan durante la semana y solo pueden venir los "
    "fines de semana, cuando también tienen otras obligaciones con sus familias y con el barrio.",
    "Otro problema es el acceso al agua. En dos de los huertos el agua llega por una sola manguera, y los vecinos tienen "
    "que esperar su turno para regar las parcelas durante los meses más secos del verano.",
    # ends without a full stop, as "(Participante 12)" in the article that showed the problem
    "Vemos que mucha gente nos está esperando con las regaderas, así que intentamos que cada uno riegue rápido y deje "
    "la manguera al siguiente (Participante 4)",
]
EN = [
    "Community gardens are places where neighbours grow food together and share the work of caring for them. In this "
    "paper we study how the volunteers of three gardens in the city organise themselves, which problems they meet and "
    "why some projects disappear after a few years, despite the early enthusiasm of the people who founded them.",
    "Over six months we observed the Saturday work sessions and held twelve interviews with volunteers and "
    "coordinators. The fieldnotes and transcripts were analysed thematically, and the themes were discussed in data "
    "sessions with the whole research team.",
    # the third paragraph runs on to the next page's English column, which starts in lower case
    "The coordinators measure the success",
    "of each season by counting the harvests and the number of people who take part in the work sessions. One of them "
    "put it like this:",
    "Lack of time is the problem most often mentioned. The volunteers work during the week and can only come at "
    "weekends, when they also have other duties to their families and to the neighbourhood.",
    "Another problem is access to water. In two of the gardens the water comes through a single hose, and the "
    "neighbours have to wait their turn to water the plots during the driest months of the summer.",
    "We do see a lot of people waiting for us with their watering cans, so we try to make sure that each one waters "
    "quickly and passes the hose on to the next. (Participant 4)",
]
TITLE = ["Los huertos comunitarios como espacios para el cuidado del barrio",
         "Community gardens as places for the care of the neighbourhood"]


def _column(page: pdfmake.Page, paras: list[str], x: float, top: float) -> None:
    y = top
    for p in paras:
        for ln in pdfmake.wrap(p, 230, "Times-Roman", 10):
            page.text(ln, x, y, "Times-Roman", 10)
            y -= 12.5
        y -= 9


def side_by_side(folder: Path) -> Path:
    """Two pages, Spanish in the left column and English in the right, a title in both across the top."""
    one, two = pdfmake.Page(), pdfmake.Page()
    one.text(TITLE[0], 60, 800, "Helvetica-Bold", 12)   # one title in both languages, on two lines
    one.text(TITLE[1], 60, 785, "Helvetica-Bold", 12)
    _column(one, ES[:3], 60, 750)
    _column(one, EN[:3], 305, 750)
    _column(two, ES[3:], 60, 770)
    _column(two, EN[3:], 305, 770)
    path = folder / "huertos.pdf"
    pdfmake.write([one, two], path, "Huertos comunitarios")
    return path


@pytest.fixture(scope="module")
def pdf(tmp_path_factory) -> Path:
    return side_by_side(tmp_path_factory.mktemp("bilingual"))


def _items(doc) -> list[tuple[str, str]]:
    return [(doc.text[b.start:b.end], b.kind) for b in doc.blocks]


def _passage_langs(doc) -> list[set]:
    items = _items(doc)
    langs = languages.block_languages(items, languages.survey(items)["two"])
    return [{c for b, c in zip(doc.blocks, langs) if c in ("en", "es") and b.start < p.end and b.end > p.start}
            for p in doc.passages]


# ---- languages ------------------------------------------------------------------------------------------------------
def test_the_two_languages_and_each_blocks(pdf):
    doc = reader.build_document(ingest.read_file(pdf), version=5)
    items = _items(doc)
    s = languages.survey(items)
    assert set(s["two"]) == {"en", "es"} and s["v"] == languages.VERSION
    langs = dict(zip((t for t, _k in items), languages.block_languages(items, s["two"])))
    for p in ES:
        assert any(langs[t] == "es" for t in langs if p[:40] in t), p[:40]
    for p in EN[:2] + EN[3:]:   # (EN[2], six words at the foot of a column, does not tell: it is kept)
        assert any(langs[t] == "en" for t in langs if p[:30] in t), p[:30]
    assert languages.pair_language(f"{TITLE[0]}: {TITLE[1]}", "en", "es") == languages.MIXED
    title = next(t for t in langs if TITLE[0][:20] in t)
    assert TITLE[1][:20] in title and langs[title] == languages.MIXED   # kept whichever language is kept
    # words both languages write ("no", "me", "final", "general") and "et al." tell nothing
    assert languages.pair_language("The final concern was a general assumption about the time taken to fix them.",
                                   "en", "es") == "en"
    assert languages.pair_language("Pueden decir no, no, me quedo con eso, como dicen Forti et al. y los demás.",
                                   "en", "es") == "es"
    assert languages.pair_language("150", "en", "es") is None


def test_one_language_or_a_short_quote_is_not_two():
    en = [(p, "body") for p in EN] * 3
    assert languages.survey(en)["two"] is None
    assert languages.survey(en + [(ES[0], "body")])["two"] is None   # a Spanish quote in an English paper: too little
    assert languages.survey([(p, "references") for p in ES] + en)["two"] is None   # only what is read counts
    assert languages.keep_mask(en, "en") == [True] * len(en)


def test_a_block_that_does_not_tell_follows_its_neighbours_only_when_they_agree():
    items = [(ES[0], "body"), ("Juan Pérez", "body"), (ES[1], "body"), ("150", "body"), (EN[0], "body"),
             ("María Gómez", "body"), (EN[1], "body"), (ES[3], "body"), (ES[4], "body"), (EN[4], "body"),
             (EN[5], "body"), (ES[5], "body"), (EN[6], "body")]
    langs = languages.block_languages(items, ["en", "es"])
    assert langs[1] == "es" and langs[3] is None and langs[5] == "en"
    assert languages.keep_mask(items, "en")[3] is True   # unknown: kept


# ---- reader 6 -------------------------------------------------------------------------------------------------------
def test_reader_5_put_both_languages_into_one_passage_and_reader_6_does_not(pdf):
    raw = ingest.read_file(pdf)
    d5, d6 = reader.build_document(raw, version=5), reader.build_document(raw, version=6)
    assert d5.text == d6.text
    assert any(len(s) == 2 for s in _passage_langs(d5))       # "…al siguiente (Participante 4)" + "of each season…"
    assert not any(len(s) == 2 for s in _passage_langs(d6))
    assert d5.reading["languages"]["mixed_passages"] >= 1 and d6.reading["languages"]["mixed_passages"] == 0
    assert reader.READER == ingest.READER == 6


def test_a_document_in_one_language_reads_as_reader_5_read_it(tmp_path):
    for make in (measure._make_a, measure._make_b):
        case = make(tmp_path)
        raw = ingest.read_file(case.path)
        d5, d6 = reader.build_document(raw, version=5), reader.build_document(raw, version=6)
        assert d5.text == d6.text and d5.layout.paragraphs == d6.layout.paragraphs
        assert [(p.start, p.end, p.section) for p in d5.passages] == [(p.start, p.end, p.section) for p in d6.passages]
        assert d6.reading["languages"]["two"] is None


# ---- keeping one language -------------------------------------------------------------------------------------------
def test_choose_inclusion_keeps_one_language_and_a_persons_own_choice_wins(pdf):
    doc = reader.build_document(ingest.read_file(pdf))
    items = _items(doc)
    plain = reader.choose_inclusion(items, {})
    assert plain == reader.choose_inclusion(items, {reader.block_fp(items[0][0]): plain[0]})
    kept = reader.choose_inclusion(items, {"lang:en": 1})
    langs = languages.block_languages(items, languages.survey(items)["two"])
    assert all(not k for k, c in zip(kept, langs) if c == "es")
    assert all(k == p for k, p, c in zip(kept, plain, langs) if c != "es")
    es = next(i for i, c in enumerate(langs) if c == "es")
    again = reader.choose_inclusion(items, {"lang:en": 1, reader.block_fp(items[es][0]): 1})
    assert again[es] == 1                                   # restored by the person: counts
    assert reader.choose_inclusion(items, {"lang:xx": 1}) == plain   # no such language: nothing changes


@pytest.fixture
def project(api, tmp_path, pdf):  # noqa: F811
    assert api("POST", "/api/projects", {"name": "Dos"})[0] == 200
    ws = Workspace.open(margin_home.project_path("Dos"))
    try:
        ingest.ingest(ws, [pdf])
        doc = ws.scalar("SELECT doc_id FROM documents")
    finally:
        ws.close_all()
    return doc


def _sections(doc_id: str) -> dict[str, str]:
    ws = Workspace.open(margin_home.project_path("Dos"))
    try:
        return {r[0]: r[1] for r in ws.query("SELECT text, section FROM passages WHERE doc_id=?", (doc_id,))}
    finally:
        ws.close_all()


def test_keep_only_english_and_count_both_again(api, project):  # noqa: F811
    doc = project
    base = f"/api/projects/Dos/documents/{doc}"
    st, d = api("GET", f"{base}?view=blocks&limit=200")
    assert st == 200 and set(d["languages"]["two"]) == {"en", "es"} and d["languages"]["kept"] is None
    assert d["languages"]["names"]["es"] == "Spanish" and d["new_reader_changes"] is False
    before = _sections(doc)
    assert any(s == "body" and ES[0][:30] in t for t, s in before.items())

    st, r = api("PUT", f"{base}/language", {"keep": "en"})
    assert st == 200 and r["keep"] == "en" and r["left_out"] >= len(ES) and r["restored"] == 0
    assert all(b["lang_out"] == {"language": "Spanish", "kept": "English"} for b in r["blocks"] if not b["included"])
    now = _sections(doc)
    assert all(s != "body" for t, s in now.items() if any(p[:30] in t for p in ES))
    assert all(s == "body" for t, s in now.items() if any(p[:30] in t for p in EN[:2]))
    st, d = api("GET", f"{base}?view=blocks&limit=200")
    assert d["languages"]["kept"] == "en"

    # a Spanish block the person restores counts, and keeps its own mark
    es = next(b for b in d["blocks"] if ES[1][:30] in b["text"])
    st, r = api("PUT", f"{base}/blocks/{es['n']}", {"included": True})
    assert st == 200
    st, d = api("GET", f"{base}?view=blocks&limit=200")
    b = next(x for x in d["blocks"] if x["n"] == es["n"])
    assert b["included"] and "lang_out" not in b

    assert api("PUT", f"{base}/language", {"keep": "fr"})[0] == 400
    assert api("PUT", f"{base}/language", {"keep": 3})[0] == 400
    assert api("PUT", "/api/projects/Dos/documents/nope/language", {"keep": "en"})[0] == 404
    st, r = api("PUT", f"{base}/language", {"keep": None})
    assert st == 200 and r["keep"] is None and r["restored"] >= len(ES) - 1
    assert _sections(doc) == before | {t: s for t, s in _sections(doc).items() if ES[1][:30] in t}
    ws = Workspace.open(margin_home.project_path("Dos"))
    try:
        log = [r[0] for r in ws.query("SELECT text FROM research_log WHERE kind='document-language' ORDER BY rowid")]
        assert len(log) == 2 and "Kept only the English" in log[0] and "Both languages" in log[1]
        assert not ws.scalar("SELECT COUNT(*) FROM block_choices WHERE fp LIKE 'lang:%'")
    finally:
        ws.close_all()


def test_the_choice_holds_when_the_document_is_read_again(tmp_path, monkeypatch, pdf):
    ws = Workspace.create(tmp_path / "ws")
    try:
        with monkeypatch.context() as mp:
            mp.setattr(ingest, "READER", 5)
            ingest.ingest(ws, [pdf], ai_access="cloud")
        doc = ws.scalar("SELECT doc_id FROM documents")
        with ws.connect() as cx:
            cx.execute("INSERT INTO block_choices(doc_id, fp, included, kind, person_id, at) VALUES (?,?,1,'lang',?,?)",
                       (doc, "lang:en", "me", "2026-11-13T00:00:00Z"))
            reader.apply_choices(cx, doc)
        mixed = [r[0] for r in ws.query("SELECT text FROM passages WHERE doc_id=? AND section='body'", (doc,))
                 if "(Participante 4)" in r[0]]
        assert mixed, "reader 5 kept the Spanish of the passage that holds both"
        langs = languages.summary_for(ws._conn(), doc)
        assert langs["mixed_passages"] >= 1 and languages.new_reader_changes(5, langs)
        assert reread.check(ws, doc)["ok"]
        reread.move(ws, doc)
        assert ws.scalar("SELECT reader FROM documents") == 6
        assert not [r[0] for r in ws.query("SELECT text FROM passages WHERE doc_id=? AND section='body'", (doc,))
                    if "Participante" in r[0] or ES[0][:30] in r[0]]
        assert languages.summary_for(ws._conn(), doc)["mixed_passages"] == 0
    finally:
        ws.close_all()


def test_a_reader_5_document_in_one_language_is_offered_the_new_reader_only_as_a_pdf(tmp_path, monkeypatch):
    """0.19: reader 6 is reader6.py's PDF rules and the two languages kept apart: a one-language PDF reader 5 read is
    offered it, a one-language document of another kind is not (reader 6 reads it as reader 5 did)."""
    from margin import runs, sources

    ws = Workspace.create(tmp_path / "ws")
    try:
        case = measure._make_b(tmp_path)
        txt = tmp_path / "repair-cafe.txt"
        txt.write_text("Field notes from the repair café.\n\nVolunteers fixed a kettle and two lamps in an "
                       "afternoon. Smart devices were harder: their parts were glued and their apps had gone.\n",
                       encoding="utf-8")
        with monkeypatch.context() as mp:
            mp.setattr(ingest, "READER", 5)
            ingest.ingest(ws, [case.path, txt], ai_access="cloud")
        kinds = {r[1]: r[0] for r in ws.query("SELECT doc_id, kind FROM documents")}
        pdf_doc, txt_doc = kinds["pdf"], kinds["text"]
        langs = languages.summary_for(ws._conn(), pdf_doc)
        assert langs["two"] is None
        assert languages.new_reader_changes(5, langs, "pdf") and not languages.new_reader_changes(5, langs, "text")
        assert languages.new_reader_changes(4, None, "pdf") and not languages.new_reader_changes(6, None, "pdf")
        # reader 5 read a plain text file as reader 4 did: reader 6 changes it only when it mixes two languages
        assert not languages.new_reader_changes(4, None, "text")
        assert languages.new_reader_changes(4, {"mixed_passages": 1}, "text")
        assert reread.check(ws, pdf_doc)["ok"]
        c = reread.check(ws, txt_doc)
        assert not c["ok"] and "reads this document as it is read now" in c["reason"]
        older = {(d["reader"], d["older"]): d["n"] for d in runs.made_with(ws)["documents"]}
        changes = {d["doc_id"]: d["new_reader_changes"] for d in sources.document_overview(ws)}
        assert changes == {pdf_doc: True, txt_doc: False}
        assert older == {(5, True): 1, (5, False): 1} and runs.made_with(ws)["older"]
    finally:
        ws.close_all()


def test_a_reading_before_its_languages_were_kept_gets_them_without_waiting(tmp_path, monkeypatch, pdf):
    """A reading report of 0.18.5 has no languages: the list of documents makes them as the project stands, and keeps
    them only when the database is free (a move or a merge holding it is never waited for)."""
    import json
    import sqlite3
    import time

    from margin import sources

    ws = Workspace.create(tmp_path / "ws")
    try:
        with monkeypatch.context() as mp:
            mp.setattr(ingest, "READER", 5)
            ingest.ingest(ws, [pdf], ai_access="cloud")
        doc = ws.scalar("SELECT doc_id FROM documents")
        with ws.connect() as cx:   # as 0.18.5 stored it
            rep = json.loads(cx.execute("SELECT reading_json FROM documents").fetchone()[0])
            rep.pop("languages")
            cx.execute("UPDATE documents SET reading_json=?", (json.dumps(rep),))
        other = sqlite3.connect(ws.db_path, isolation_level=None, timeout=1)
        other.execute("BEGIN IMMEDIATE")
        try:
            t0 = time.time()
            assert sources.document_overview(ws)[0]["new_reader_changes"] is True
            assert languages.summary(ws, doc)["mixed_passages"] >= 1
            assert time.time() - t0 < 5
            assert languages.from_report(ws.scalar("SELECT reading_json FROM documents")) is None   # not kept: busy
        finally:
            other.execute("ROLLBACK")
            other.close()
        assert sources.document_overview(ws)[0]["new_reader_changes"] is True
        assert languages.from_report(ws.scalar("SELECT reading_json FROM documents"))["mixed_passages"] >= 1
    finally:
        ws.close_all()


# ---- between copies -------------------------------------------------------------------------------------------------
def test_one_language_is_kept_never_two_and_a_proposal_says_which():
    from margin import ownership

    base = {"abc": [0, "body"], "lang:en": [1, "lang"]}
    out = ownership._apply_delta(base, {"lang:es": [1, "lang"]})
    assert out == {"abc": [0, "body"], "lang:es": [1, "lang"]}
    w = ownership._delta_words({"lang:en": None, "lang:es": [1, "lang"]})
    assert w["language"] == "es" and w["language_name"] == "Spanish" and w["restored"] == 0 and w["undone"] == 0
    w = ownership._delta_words({"lang:es": [1, "lang"], "lang:en": None})
    assert w["language"] == "es"
    assert ownership._delta_words({"lang:en": None})["language"] == "both"
