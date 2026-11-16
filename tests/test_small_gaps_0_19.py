"""Smaller gaps of the 0.19 series: the concept map on the command line, the drive keeper's hourly check, Retry-After,
the AI's parts of a long theory, terms of any script, reader 6, two languages, S3's read caps, a figure left out
through a new reader, a codebook file's encodings, and the SDG codes of documents added to another project.
"""
from __future__ import annotations

import base64
import json
import sys
import time
from email.utils import formatdate
from pathlib import Path

import pytest

from concept_corpus import write as write_concept_corpus
from test_app import api, home  # noqa: F401  (fixtures)
from test_codebook_from_theory import _by_term, _one_text
from test_reader import _project as _reader_project
from test_shared_projects import anna_and_ben  # noqa: F401  (fixture)
from test_webdav_storage import USERS, _age, _round, _with_carol, drive  # noqa: F401  (fixture)

from margin import cli, conceptmap, ingest, languages, measure, pdfmake, qdc_import, reader, terms, theorycodes
from margin.store import Workspace
from margin.sync import _web, space

sys.path.insert(0, str(Path(__file__).parent))
import fake_s3  # noqa: E402

needs_pdfminer = pytest.mark.skipif(not reader.pdfminer_available(), reason="the pdfminer extra is not installed")


@pytest.fixture(autouse=True)
def _drive_over_plain_http(monkeypatch):
    from margin.sync.storage import TEST_PLAIN_HTTP

    monkeypatch.setattr(_web, "sleep", lambda s: None)
    monkeypatch.setenv(TEST_PLAIN_HTTP, "1")   # (the stand-in drive is on this computer, over plain http)


# ---------------------------------------------------------------------------------------------
# D1: the concept map on the command line
# ---------------------------------------------------------------------------------------------
@pytest.fixture
def mapped(tmp_path):
    w = Workspace.create(tmp_path / "p")
    ingest.ingest(w, [write_concept_corpus(tmp_path / "docs")["solar"].parent])
    terms.build(w)
    yield w
    w.close_all()


def test_the_concept_map_on_the_command_line(mapped, capsys):
    path = str(mapped.root)
    assert cli.main(["--ws", path, "concept-map", "--n", "12"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("12 of ") and "concepts, from" in out and "Group 1" in out
    assert "Mentioned together more often than by chance:" in out and "PMI" in out
    assert cli.main(["--ws", path, "concept-map", "--n", "12", "--json"]) == 0
    m = json.loads(capsys.readouterr().out)
    assert len(m["nodes"]) == 12 and m["built"] is True
    for args, said in ((["--theme", "bad"], "A theme is <run id>:<theme id>."),
                       (["--theme", ":1"], "A theme is <run id>:<theme id>."),
                       (["--theme", "gone:1"], "No such set of themes: see margin themes."),
                       (["--code", "7.2"], "Say the codebook of the code with --framework."),
                       (["--year-from", "0"], "A year is a number from 1 to 9999.")):
        assert cli.main(["--ws", path, "concept-map", *args]) == 1, args
        err = capsys.readouterr().err
        assert said in err, (args, err)


def test_the_concept_map_in_words(mapped, tmp_path):
    empty = Workspace.create(tmp_path / "empty")
    try:
        assert conceptmap.as_text(conceptmap.concept_map(empty)) == \
            "No glossary yet: make it first (margin terms build)."
    finally:
        empty.close_all()
    nothing = conceptmap.concept_map(mapped, conceptmap.Filters(year_from=1500, year_to=1501))
    assert conceptmap.as_text(nothing) == "No concept is mentioned in two passages within these filters."
    doc = mapped.scalar("SELECT doc_id FROM documents WHERE title='Solar report'")
    few = conceptmap.concept_map(mapped, conceptmap.Filters(docs=[doc]), 20)
    text = conceptmap.as_text(few)
    assert few["passages"] < conceptmap.FEW_PASSAGES and f"Only {few['passages']} passages are counted" in text
    lab = {x["id"]: x["label"] for x in few["nodes"]}
    e = few["edges"][0]
    assert f"  {lab[e['a']]} – {lab[e['b']]}: {e['together']} passages, PMI {e['pmi']}" in text.splitlines()


# ---------------------------------------------------------------------------------------------
# D2: the drive keeper's hourly look at shares left to stop; a new app password
# ---------------------------------------------------------------------------------------------
def _ocs_calls(drive, since: int) -> list[str]:  # noqa: F811
    return [c for c in drive.state.calls[since:] if "/ocs/" in c]


def test_a_share_left_to_stop_is_looked_at_once_an_hour_by_the_keeper(anna_and_ben, drive, tmp_path,  # noqa: F811
                                                                       monkeypatch):
    anna, _carol, _desc, cdesc = _with_carol(anna_and_ben, drive, tmp_path, monkeypatch)
    drive.state.fail["DELETE"] = 502
    with anna:
        out = space.remove_member(anna.ws, cdesc["part"])
    assert "could not stop sharing" in out["warnings"][0] and len(drive.state.shares) == 1
    # the next round: the drive still fails; the note stays, to be tried again
    _round(anna)
    with anna:
        left = space.status(anna.ws)["left_to_do"]
    assert len(left) == 1 and left[0]["check"] is True and len(drive.state.shares) == 1
    # the drive works again, but within the hour nothing is asked of it
    drive.state.fail.clear()
    n = len(drive.state.calls)
    _round(anna)
    assert _ocs_calls(drive, n) == [] and len(drive.state.shares) == 1
    # an hour later: the share is stopped and the note goes
    _age(anna, "left_checked_at", 3601)
    _round(anna)
    assert drive.state.shares == {}
    with anna:
        assert space.status(anna.ws)["left_to_do"] == []


def test_a_new_app_password_is_refused_in_words(anna_and_ben, drive, tmp_path):  # noqa: F811
    anna, ben = anna_and_ben
    with ben, pytest.raises(space.SpaceProblem) as e:
        space.set_drive_password(ben.ws, "ben", USERS["ben"])
    assert e.value.kind == "no_space"
    with anna:
        space.setup_webdav(anna.ws, drive.address("anna@uva.nl"), "anna@uva.nl", USERS["anna@uva.nl"])
        for user, pw in (("", "x"), ("anna@uva.nl", "  ")):
            with pytest.raises(space.SpaceProblem) as e:
                space.set_drive_password(anna.ws, user, pw)
            assert e.value.kind == "input" and "app password" in str(e.value)
        # the team's folder is no longer in the account's drive (renamed or moved away in the website)
        desc = space.configured(anna.ws)
        drive.state.dirs.discard(f"anna@uva.nl/{desc['folder']}")
        with pytest.raises(space.SpaceProblem) as e:
            space.set_drive_password(anna.ws, "anna@uva.nl", USERS["anna@uva.nl"])
        assert e.value.kind == "folder_not_found" and "is not in this account's drive" in str(e.value)
        assert space._get_secret(desc["id"], "access")["user"] == "anna@uva.nl"   # the old one is kept


# ---------------------------------------------------------------------------------------------
# D3: Retry-After
# ---------------------------------------------------------------------------------------------
def test_retry_after_in_seconds_as_a_date_or_not_at_all():
    def r(v=None):
        return _web.Reply(503, {"retry-after": v} if v is not None else {})

    assert _web.retry_after(r("120")) == 120.0
    soon = _web.retry_after(r(formatdate(time.time() + 90, usegmt=True)))
    assert soon is not None and 80 <= soon <= 91
    assert _web.retry_after(r(formatdate(time.time() - 600, usegmt=True))) == 0.0   # a date gone by: at once
    for rubbish in ("soon", "-5", "1.5", "Mon, 99 Foo 2026"):
        assert _web.retry_after(r(rubbish)) is None, rubbish
    assert _web.retry_after(r()) is None and _web.retry_after(r("  ")) is None


# ---------------------------------------------------------------------------------------------
# D4: theorycodes
# ---------------------------------------------------------------------------------------------
def test_a_long_theory_is_read_in_the_parts_that_use_its_concepts_most(tmp_path, monkeypatch):
    filler = "Gardens were visited on many days of the year and the visits were written down. "
    paras = []
    for i in range(12):
        if i in (3, 7, 10):
            paras.append("A feedback loop is a closed chain of causes. The feedback loop returns to where it began. "
                         "Every feedback loop takes time, and a delay is the time a feedback loop needs.")
        else:
            paras.append(filler * 3)
    ws, doc = _one_text(tmp_path, "Systems\n\n" + "\n\n".join(paras) + "\n")
    try:
        monkeypatch.setattr(theorycodes, "AI_MAX_PARTS", 3)
        every = theorycodes._ai_parts(ws, doc, ["feedback loop"], max_chars=300)
        assert len(every) == 3
        kept = [" ".join(p["text"] for p in part) for part in every]
        assert all("feedback loop" in t for t in kept)                          # the parts that use it
        starts = [ws.scalar("SELECT start FROM passages WHERE passage_id=?", (part[0]["passage_id"],))
                  for part in every]
        assert starts == sorted(starts)                                        # in the document's order
        payloads = theorycodes.ai_payloads(ws, doc, max_chars=300)
        assert len(payloads) == 3 and all(p["parts"] == 3 for p in payloads)
        monkeypatch.setattr(theorycodes, "AI_MAX_PARTS", 60)
        assert len(theorycodes._ai_parts(ws, doc, ["feedback loop"], max_chars=300)) > 3
    finally:
        ws.close_all()


def _long_text(defs: list[str]) -> str:
    """A text of more than sixty sentences that argues, with `defs` ("X is a …") among them."""
    s = [f"The visitors of the repair cafe brought their broken things on day {i} and talked about them."
         for i in range(70)]
    for k, d in enumerate(defs):
        s.insert(5 + 20 * k, d)
    return "Repair\n\n" + "\n\n".join(" ".join(s[i:i + 5]) for i in range(0, len(s), 5)) + "\n"


def test_a_long_text_that_defines_one_or_two_things_ticks_nothing(tmp_path):
    two = ["A repair cafe is a meeting where volunteers mend the things that neighbours bring.",
           "A repair pledge is a promise that a broken thing will be mended within a month. No repair pledge was "
           "broken."]
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    ws, doc = _one_text(tmp_path / "a", _long_text(two))
    try:
        got = _by_term(theorycodes.candidates(ws, doc))
        assert {"repair cafe", "repair pledge"} <= set(got) and got["repair pledge"]["how"] == "defined"
        assert not any(c["ticked"] for c in got.values())
    finally:
        ws.close_all()
    # three terms defined outright: those are ticked
    three = two + ["A tool library is a room where neighbours borrow tools for a week. Every tool library was busy."]
    ws, doc = _one_text(tmp_path / "b", _long_text(three))
    try:
        got = _by_term(theorycodes.candidates(ws, doc))
        assert all(got[t]["ticked"] for t in ("repair cafe", "repair pledge", "tool library"))
    finally:
        ws.close_all()


@pytest.mark.parametrize("term", ["обратная связь", "ανατροφοδότηση"])
def test_a_term_in_cyrillic_or_greek_is_found_whole(tmp_path, term):
    ws, doc = _one_text(tmp_path, "Systems\n\n"
                        f"The {term} is a closed chain of causes. Every {term} takes time. The {term} of a "
                        f"community centre is its people, and a {term} needs a stock to act on.\n")
    try:
        got = _by_term(theorycodes.candidates(ws, doc))
        assert term in got, sorted(got)
        assert got[term]["how"] == "defined" and got[term]["definition"]["quote"].startswith(f"The {term} is a")
    finally:
        ws.close_all()


# ---------------------------------------------------------------------------------------------
# D5: reader 6
# ---------------------------------------------------------------------------------------------
REF = ("Smith, A., Jones, B., {y}. Counting nests on heathland plots in spring {y}. Journal of Heathland Studies "
       "7 (2), 101-118. https://doi.org/10.1016/j.heath.{y}.100070")


def _pdf_with_references(path: Path) -> Path:
    """An article whose reference list runs over three pages, with the authors' names at the left of each page's
    running head and the journal and page number at the right."""
    from test_reader6 import BODY

    fl = pdfmake.Flow(columns=[(60, 475)], top=770, bottom=80, size=10)
    fl.heading("1. Introduction")
    for _ in range(14):
        fl.paragraph(BODY * 3)
    fl.heading("References")
    for i in range(70):
        fl.paragraph(REF.format(y=1950 + i))
    for n, pg in enumerate(fl.pages, 1):
        pg.text("A. Smith and B. Jones", 60, 806, "Helvetica", 8)
        pg.text(f"Journal of Heathland Studies 7 (2024) {100 + n}", 330, 806, "Helvetica", 8)
    pdfmake.write(fl.pages, path)
    return path


@needs_pdfminer
def test_a_reference_list_over_several_pages_is_left_out_whole(tmp_path):
    path = _pdf_with_references(tmp_path / "refs.pdf")
    doc = ingest.read_document(path, reader=6)
    refs = [b for b in doc.blocks if b.text.startswith("Smith, A., Jones, B.")]
    assert len({b.page for b in refs}) >= 3
    stray = [(b.page, b.kind) for b in refs if b.kind != "references"]
    assert refs and not stray, stray
    heads = [b for b in doc.blocks if "Smith and B. Jones" in b.text or b.text.startswith("Journal of Heathland")]
    assert heads and all(b.kind == "furniture" for b in heads)
    # reader 5 took the running heads for headings, and read most of the list as text
    old = [b for b in ingest.read_document(path, reader=5).blocks if b.text.startswith("Smith, A., Jones, B.")]
    assert sum(b.kind == "body" for b in old) > len(old) // 2


@needs_pdfminer
def test_a_byline_and_a_date_before_the_text_are_front_matter(tmp_path):
    from test_reader6 import BODY

    fl = pdfmake.Flow(columns=[(60, 475)], top=640, bottom=80, size=10)
    for _ in range(5):
        fl.paragraph(BODY * 3)
    first = fl.pages[0]
    first.text("By Ann Smith", 60, 725, "Helvetica", 10)
    first.text("May 8, 2012", 60, 708, "Helvetica", 10)
    pdfmake.write(fl.pages, tmp_path / "news.pdf")
    blocks = ingest.read_document(tmp_path / "news.pdf", reader=6).blocks
    kind = {b.text: b.kind for b in blocks}
    assert kind["By Ann Smith"] == "front" and kind["May 8, 2012"] == "front"
    assert all(b.kind == "body" for b in blocks if b.text.startswith("The survey counted"))


# ---------------------------------------------------------------------------------------------
# D6: two languages only when the second is a fifth of the document and has five blocks
# ---------------------------------------------------------------------------------------------
EN = ("The volunteers of the garden meet on Saturdays and they share the work of caring for the plots with "
      "the neighbours who come to help them")
ES = ("Los voluntarios del huerto se reúnen los sábados y comparten el trabajo de cuidar las parcelas con "
      "los vecinos que vienen a ayudarles")


def _blocks(n_en: int, n_es: int, es_len: int | None = None) -> list[tuple[str, str]]:
    n = max(len(EN), len(ES))
    en, es = EN.ljust(n), ES.ljust(es_len or n)
    return [(en, "body")] * n_en + [(es, "body")] * n_es


def test_the_second_language_at_the_limits():
    assert languages.stopwords.detect(languages._words(EN)) == "en"
    assert languages.stopwords.detect(languages._words(ES)) == "es"
    assert languages.survey(_blocks(20, 5))["two"] == ["en", "es"]          # a fifth exactly, five blocks
    assert languages.survey(_blocks(21, 5))["two"] is None                  # just under a fifth
    assert languages.survey(_blocks(10, 5))["two"] == ["en", "es"]
    assert languages.survey(_blocks(6, 4))["two"] is None                   # four blocks, however large
    n = max(len(EN), len(ES))
    big = _blocks(20, 0) + _blocks(0, 4, es_len=4 * n)
    s = languages.survey(big)
    assert s["shares"]["es"] > languages.MIN_SHARE and s["blocks"]["es"] == 4 and s["two"] is None


# ---------------------------------------------------------------------------------------------
# D7: S3 answers are read up to a cap
# ---------------------------------------------------------------------------------------------
def test_every_s3_answer_is_read_up_to_a_cap(monkeypatch):
    from margin.sync import storage

    keys = {"KEYRW": {"secret": "secret-rw", "bucket": "bkt", "prefix": None, "can_write": True}}
    srv, url = fake_s3.start(keys=keys, buckets=["bkt"])
    try:
        caps = []
        real = _web.send

        def send(method, url, headers=None, body=None, timeout=60.0, read_cap=None):
            caps.append((method, "list-type" in url, read_cap))
            return real(method, url, headers, body, timeout, read_cap)

        monkeypatch.setattr(_web, "send", send)
        s = storage.S3Storage(endpoint=url, region="eu-central-003", bucket="bkt", key_id="KEYRW", secret="secret-rw")
        s.put("space/x", b"x")
        assert s.get("space/x") == b"x"
        assert "space/x" in s.list("space/")
        s.delete("space/x")
        assert {m for m, _l, _c in caps} >= {"PUT", "GET", "DELETE"}
        assert all(c is not None for _m, _l, c in caps)
        assert [c for m, listing, c in caps if listing] == [storage._LIST_CAP]
        assert all(c <= storage._SMALL_ANSWER for m, _l, c in caps if m in ("PUT", "DELETE"))
    finally:
        fake_s3.stop(srv)


# ---------------------------------------------------------------------------------------------
# D8: a figure left out stays left out when its document moves to the new reader
# ---------------------------------------------------------------------------------------------
@needs_pdfminer
def test_a_figure_left_out_stays_left_out_with_the_new_reader(api, tmp_path, monkeypatch):  # noqa: F811
    case = next(c for c in measure.make_table_figure_texts(tmp_path / "known") if c.name == "j_figures")
    with monkeypatch.context() as mp:
        mp.setattr(ingest, "READER", 5)
        docs = _reader_project(api, tmp_path, [case.path])
    d = next(iter(docs.values()))
    assert d["reader"] == 5
    base = f"/api/projects/R/documents/{d['doc_id']}"
    figs = [b for b in api("GET", f"{base}?view=blocks&limit=500")[1]["blocks"] if b["kind"] == "figure"]
    assert len(figs) >= 2
    gone, kept = figs[0], figs[1]
    assert api("PUT", f"{base}/blocks/{gone['n']}", {"included": False})[0] == 200
    st, r = api("POST", f"{base}/reread", {})
    assert st == 200, r
    assert api.wait(r["job"]["id"])["state"] == "done"
    assert api("GET", "/api/projects/R/documents")[1]["documents"][0]["reader"] == ingest.READER
    now = [b for b in api("GET", f"{base}?view=blocks&limit=500")[1]["blocks"] if b["kind"] == "figure"]
    by_box = {(b["page"], tuple(round(v) for v in b["box"])): b for b in now}
    assert by_box[(gone["page"], tuple(round(v) for v in gone["box"]))]["hidden"] is True
    assert by_box[(kept["page"], tuple(round(v) for v in kept["box"]))]["hidden"] is False


# ---------------------------------------------------------------------------------------------
# D9: a codebook file's encodings, and where it comes from
# ---------------------------------------------------------------------------------------------
def _qdc(name: str, enc: str, declare: bool = True) -> bytes:
    head = f'<?xml version="1.0" encoding="{enc}"?>' if declare else ""
    return (head + '<CodeBook xmlns="urn:QDA-XML:codebook:1.0"><Codes>'
            f'<Code guid="g1" name="{name}" isCodable="true"/></Codes></CodeBook>').encode(enc)


def test_a_codebook_file_in_an_older_encoding_reads():
    # the encoding its declaration names (not UTF-8: "ő" is one byte in Latin-2)
    got = qdc_import.from_source({"file": base64.b64encode(_qdc("Erőforrás", "iso-8859-2")).decode()})
    assert [c["code"] for c in got["codes"]] == ["Erőforrás"]
    # no declaration, not UTF-8: Windows' Western European
    got = qdc_import.from_source({"file": base64.b64encode(_qdc("Élément", "cp1252", declare=False)).decode()})
    assert [c["code"] for c in got["codes"]] == ["Élément"]
    # a declaration naming an encoding there is none of
    data = _qdc("Élément", "cp1252", declare=False).replace(b"<CodeBook", b'<?xml version="1.0" encoding="no-such"?>'
                                                             b"<CodeBook", 1)
    with pytest.raises(ValueError, match="not text Margin can read"):
        qdc_import.from_source({"file": base64.b64encode(data).decode()})


def test_a_codebook_comes_as_a_file_or_as_its_text():
    xml = _qdc("Waiting", "utf-8").decode("utf-8")
    assert [c["code"] for c in qdc_import.from_source({"qdc": xml})["codes"]] == ["Waiting"]
    with pytest.raises(ValueError, match="Choose a .qdc or .qdpx file."):
        qdc_import.from_source({})
    with pytest.raises(ValueError, match="did not arrive whole"):
        qdc_import.from_source({"file": "abc"})


# ---------------------------------------------------------------------------------------------
# D10: documents added to another project get the SDG keyword codes
# ---------------------------------------------------------------------------------------------
def test_documents_added_to_another_project_get_the_sdg_codes(api, corpus):  # noqa: F811
    from margin import codebooks, home as ehome

    assert api("PUT", "/api/settings", {"backend": "baseline", "embed_backend": "off"})[0] == 200
    assert api("POST", "/api/projects", {"name": "First"})[0] == 200
    first = Workspace.open(ehome.project_path("First"))
    try:
        codebooks.create(first, "mine", "My codes")   # kept with the first project only
    finally:
        first.close_all()
    assert api("PUT", "/api/settings", {"profile_framework": "mine"})[0] == 200
    assert api("POST", "/api/projects", {"name": "Second"})[0] == 200
    for f in sorted(corpus.iterdir()):
        assert api("POST", f"/api/projects/Second/uploads?batch=b1&name={f.name}", raw=f.read_bytes())[0] == 200
    st, r = api("POST", "/api/projects/Second/ingest", {"batch": "b1"})
    job = api.wait(r["job"]["id"])
    assert job["state"] == "done", job
    assert "codes_error" not in job["result"], job["result"]
    second = Workspace.open(ehome.project_path("Second"))
    try:
        assert second.scalar("SELECT COUNT(*) FROM labels WHERE framework='sdg'") > 0
    finally:
        second.close_all()
