"""0.19: reader 6, text a form crops away, publishing details after the text has begun, and the title.

- A form (Form XObject) that holds a whole draft page and shows only a window of it (its /BBox), as MDPI's figures do:
  the hidden text is not read, the form is one figure with the box it shows and its caption, and the text round it
  is whole paragraphs again; a form in a form shows only what both windows show.
- Publishing details in the first page's footer, after the text has begun (e-mails, the DOI, the dates), are front
  matter; a numbered note there is a footnote; a paragraph that is only a link is front matter; "Received wisdom
  holds …" stays text.
- A journal's name set larger than the title is not the title; a title's last line that came apart joins it.
- A running head with the page number at the other end of its row is a running head on every page.
- Reader 6 is offered to PDFs read by reader 5 (it reads nothing else otherwise), with what it changes.
- Readers 2 to 5 read every new file as before (fingerprints taken with the code before reader 6), and a Word file,
  a web page and a text file read by reader 6 as by reader 5.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import pytest
from _fakedom import NODE
from test_reader5_reading_view import _src
from test_reader5_tables_figures import _whole, docx_with_image, html_with_image

from margin import ingest, pdfmake, reader

needs_pdfminer = pytest.mark.skipif(not reader.pdfminer_available(), reason="the pdfminer extra is not installed")

# fingerprints (`_whole`) of readers 2 to 5 reading the files below, taken with Margin's code before reader 6
# (commit 50c5dd2): a reader number is frozen
PINNED: dict[str, str] = {
    "cropped_form_2": "63f658a92231ff1c2bf046d25b740f9b98fd826f",
    "cropped_form_3": "63f658a92231ff1c2bf046d25b740f9b98fd826f",
    "cropped_form_4": "63f658a92231ff1c2bf046d25b740f9b98fd826f",
    "cropped_form_5": "2a3eaa50c63d84ee6bc75cc0b484d16436124aec",
    "nested_forms_2": "9c43a3d07ba9f5a34ce6a48e85fe6add5b5a16d3",
    "nested_forms_3": "9c43a3d07ba9f5a34ce6a48e85fe6add5b5a16d3",
    "nested_forms_4": "9c43a3d07ba9f5a34ce6a48e85fe6add5b5a16d3",
    "nested_forms_5": "9c43a3d07ba9f5a34ce6a48e85fe6add5b5a16d3",
    "publishing_details_2": "fe2727efa2219c4e25d446abe9fed1410c53466c",
    "publishing_details_3": "fe2727efa2219c4e25d446abe9fed1410c53466c",
    "publishing_details_4": "fe2727efa2219c4e25d446abe9fed1410c53466c",
    "publishing_details_5": "fe2727efa2219c4e25d446abe9fed1410c53466c",
}


# ------------------------------------------------------------------------------------------------------------------
# the files
# ------------------------------------------------------------------------------------------------------------------
_WORDS = "the survey counted nests of ground birds on four plots of heathland over three springs".split()


def _para(seed: int, n: int) -> list[str]:
    return [" ".join(_WORDS[(seed + i + k) % len(_WORDS)] for k in range(11)) for i in range(n)]


def _text(items) -> bytes:
    """A content stream that writes each (x, y, size, string) in Helvetica."""
    return b"BT\n" + b"\n".join(b"/F0 %d Tf 1 0 0 1 %d %d Tm (%s) Tj" % (s, x, y, t.encode()) for x, y, s, t in items) \
        + b"\nET"


def _raw_pdf(path: Path, page: bytes, forms: list[tuple[tuple, bytes, bool]]) -> Path:
    """A one-page PDF whose content is `page`, with forms /Im1, /Im2 … : (their /BBox, their content, whether it
    draws another form inside it)."""
    n_forms = len(forms)
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    xo = b" ".join(b"/Im%d %d 0 R" % (k + 1, 6 + k) for k in range(n_forms))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F0 4 0 R >> "
            b"/XObject << " + xo + b" >> >> /Contents 5 0 R >>", font,
            b"<< /Length %d >>\nstream\n" % len(page) + page + b"\nendstream"]
    for bbox, content, inner in forms:
        res = b"/Font << /F0 4 0 R >>" + (b" /XObject << " + xo + b" >>" if inner else b"")
        objs.append(b"<< /Type /XObject /Subtype /Form /BBox [%d %d %d %d] /Resources << %s >> /Length %d >>\nstream\n"
                    % (*bbox, res, len(content)) + content + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(bytes(out))
    return path


def pdf_with_cropped_form(path: Path) -> Path:
    """A page like MDPI's: its own running head, paragraphs and a caption, and a form that holds a whole draft page
    (a running head "FOR PEER REVIEW", paragraphs, a chart's labels and axes) of which only a window (its /BBox)
    shows, placed a little shifted."""
    draft = [(60, 800, 8, "Journal 2021, 13, x FOR PEER REVIEW")]
    draft += [(100, 760 - 13 * i, 10, s) for i, s in enumerate(_para(3, 16))]
    draft += [(120, 500, 8, "Nests per plot"), (120, 470, 8, "Plot A 12"), (120, 450, 8, "Plot B 30"),
              (120, 430, 8, "Plot C 7")]
    draft += [(100, 360 - 13 * i, 10, s) for i, s in enumerate(_para(7, 8))]
    form = _text(draft) + b"\n0.5 w 110 400 m 400 400 l S 110 400 m 110 510 l S"
    own = [(60, 800, 8, "Journal 2021, 13, 12351")]
    own += [(100, 770 - 13 * i, 10, s) for i, s in enumerate(_para(0, 17))]
    own += [(100, 360, 9, "Figure 1. Nests found on each of the plots.")]
    own += [(100, 330 - 13 * i, 10, s) for i, s in enumerate(_para(5, 14))]
    page = _text(own) + b"\nq 1 0 0 1 6 -9 cm /Im1 Do Q"
    return _raw_pdf(path, page, [((100, 380, 420, 520), form, False)])


def pdf_with_nested_forms(path: Path) -> Path:
    """A form whose window (x 100 to 300) holds a form with a wider window (x 50 to 500): only what both show is read."""
    inner = _text([(120, 450, 9, "Seen in both windows"), (350, 450, 9, "Hidden by the outer window"),
                   (120, 300, 9, "Hidden below the outer window")])
    outer = _text([(120, 480, 9, "Plot labels of the chart")]) + b"\n/Im2 Do"
    own = [(100, 770 - 13 * i, 10, s) for i, s in enumerate(_para(0, 20))]
    own += [(100, 380, 9, "Figure 1. Nests found on each of the plots.")]
    page = _text(own) + b"\n/Im1 Do"
    return _raw_pdf(path, page, [((100, 400, 300, 500), outer, True), ((50, 250, 500, 500), inner, False)])


HEAD = "Journal of Heathland Studies 7 (2024) 100070"
TITLE = ("Counting ground nests on heathland plots over three springs", "of walking")
BODY = ("The survey counted the nests of ground birds on four plots of heathland over three springs, walking each plot "
        "in lines a few metres apart and marking every nest that was found with a small flag. ")


def pdf_with_publishing_details(path: Path) -> Path:
    """An article set as Elsevier sets one: the journal's running head with the page number at the other end of its
    row, the journal's name in a banner larger than the title, a title over two lines, the introduction, and in the
    first page's footer the e-mails, the DOI and the dates, and a numbered note; on the second page a paragraph that
    starts "Received wisdom" and one that is only a link."""
    fl = pdfmake.Flow(columns=[(60, 475)], top=600, bottom=260, size=10)
    fl.heading("1. Introduction")
    for k in range(3):
        fl.paragraph(BODY * 3)
    fl.new_page()
    fl._y = 770
    fl.paragraph("Received wisdom holds that ground birds nest where the heather is oldest, and the counts of the "
                 "four plots were set against that view in every spring of the survey.")
    fl.paragraph("https://www.example.org/heathland-survey-data")
    for k in range(5):
        fl.paragraph(BODY * 3)
    for _ in range(2):
        fl.new_page()
        fl._y = 770
        for k in range(8):
            fl.paragraph(BODY * 3)
    pages = fl.pages
    for n, pg in enumerate(pages, 1):
        pg.text(HEAD if n == 1 else "A. Smith and B. Jones", 60, 806, "Helvetica", 8)
        if n > 1:
            pg.text(HEAD, 380, 806, "Helvetica", 8)
        pg.text(f"{n} of {len(pages)}", 500, 40, "Helvetica", 8)
    first = pages[0]
    first.text("Journal of Heathland Studies", 180, 750, "Helvetica-Bold", 18)
    first.text(TITLE[0], 60, 700, "Helvetica", 14)
    first.text(TITLE[1], 60, 683, "Helvetica", 14)
    first.text("Ann Smith, Bob Jones", 60, 655, "Helvetica", 11)
    # (each line a block of its own: further apart than the lines of a paragraph)
    first.text("1 The plots were walked in April and May, before the heather flowered.", 60, 205, "Times-Roman", 9)
    first.text("* Corresponding author.", 60, 183, "Times-Roman", 8)
    first.text("E-mail address: ann.smith@example.org (A. Smith).", 60, 161, "Times-Roman", 8)
    first.text("https://doi.org/10.1016/j.heath.2024.100070", 60, 139, "Times-Roman", 8)
    first.text("Received 16 May 2024; Received in revised form 9 August 2024; Accepted 18 September 2024", 60, 117,
               "Times-Roman", 8)
    first.text("Available online 19 September 2024", 60, 95, "Times-Roman", 8)
    pdfmake.write(pages, path)
    return path


def _read(path, r: int):
    return ingest.read_document(Path(path), reader=r)


def _files(folder: Path) -> dict[str, Path]:
    return {"cropped_form": pdf_with_cropped_form(folder / "cropped.pdf"),
            "nested_forms": pdf_with_nested_forms(folder / "nested.pdf"),
            "publishing_details": pdf_with_publishing_details(folder / "details.pdf")}


# ------------------------------------------------------------------------------------------------------------------
# frozen
# ------------------------------------------------------------------------------------------------------------------
def test_reader_6_is_the_current_reader():
    assert reader.READER == 6 and ingest.READER == 6


@needs_pdfminer
def test_readers_2_to_5_read_the_new_files_as_before(tmp_path):
    got = {f"{name}_{r}": _whole(_read(path, r)) for name, path in _files(tmp_path).items() for r in (2, 3, 4, 5)}
    assert got == PINNED


@needs_pdfminer
def test_other_kinds_of_file_read_by_reader_6_as_by_reader_5(tmp_path):
    text = tmp_path / "plain.txt"
    text.write_text("Received wisdom holds that ground birds nest in old heather.\n\nhttps://doi.org/10.1/abc\n\n"
                    + BODY * 4, encoding="utf-8")
    for path in (docx_with_image(tmp_path), html_with_image(tmp_path), text):
        assert _whole(_read(path, 6)) == _whole(_read(path, 5)), path.name


# ------------------------------------------------------------------------------------------------------------------
# text a form crops away
# ------------------------------------------------------------------------------------------------------------------
@needs_pdfminer
def test_text_a_form_crops_away_is_not_read(tmp_path):
    path = pdf_with_cropped_form(tmp_path / "cropped.pdf")
    before = _read(path, 5)
    assert sum(b.kind == "figure" for b in before.blocks) > 10 and "PEER REVIEW" in before.text   # what reader 5 read
    doc = _read(path, 6)
    assert "PEER REVIEW" not in doc.text and "PEER REVIEW" not in " ".join(b.text for b in doc.blocks)
    figs = [b for b in doc.blocks if b.kind == "figure"]
    assert len(figs) == 1
    fig = figs[0]
    # the box the form shows (its /BBox, shifted by 6 and -9), not the draft page: x 106 to 426, top 331 to 471
    assert fig.box is not None and all(abs(a - b) <= 3 for a, b in zip(fig.box, (106, 331, 426, 471)))
    assert fig.text.startswith("Nests per plot Plot A 12") and fig.caption == "Figure 1. Nests found on each of the plots."
    kinds = Counter(b.kind for b in doc.blocks)
    assert kinds["body"] == 2 and kinds["caption"] == 1
    assert doc.reading["figures"] == 1


@needs_pdfminer
def test_a_form_in_a_form_shows_only_what_both_windows_show(tmp_path):
    path = pdf_with_nested_forms(tmp_path / "nested.pdf")
    assert "Hidden by the outer window" in _read(path, 5).text
    doc = _read(path, 6)
    words = " ".join(b.text for b in doc.blocks)
    assert "Seen in both windows" in words and "Plot labels of the chart" in words
    assert "Hidden" not in words
    fig = next(b for b in doc.blocks if b.kind == "figure")
    assert fig.box is not None and fig.box[0] >= 99 and fig.box[2] <= 301


# ------------------------------------------------------------------------------------------------------------------
# publishing details, the title, running heads
# ------------------------------------------------------------------------------------------------------------------
@needs_pdfminer
def test_publishing_details_in_the_first_pages_footer_are_front_matter(tmp_path):
    path = pdf_with_publishing_details(tmp_path / "details.pdf")
    kind = {b.text: b.kind for b in _read(path, 6).blocks}

    def of(start: str) -> str:
        return next(k for t, k in kind.items() if t.startswith(start))

    for start in ("E-mail address", "https://doi.org/10.1016", "Received 16 May 2024", "Available online"):
        assert of(start) == "front", start
    assert of("* Corresponding author") in ("front", "footnote")
    assert of("1 The plots were walked") == "footnote"
    assert of("Received wisdom holds") == "body"   # on page 2, where a publishing detail is looked for
    assert of("https://www.example.org/heathland-survey-data") == "front"
    assert of("The survey counted") == "body"
    old = {b.text: b.kind for b in _read(path, 5).blocks}
    assert next(k for t, k in old.items() if t.startswith("Available online")) == "body"   # what reader 5 read


@needs_pdfminer
def test_the_journals_name_is_not_the_title(tmp_path):
    path = pdf_with_publishing_details(tmp_path / "details.pdf")
    assert next(b for b in _read(path, 5).blocks if b.kind == "title").text == "Journal of Heathland Studies"
    doc = _read(path, 6)
    titles = [b for b in doc.blocks if b.kind == "title"]
    assert [b.text for b in titles] == [" ".join(TITLE)]
    assert next(b for b in doc.blocks if b.text == "Journal of Heathland Studies").kind == "front"
    assert doc.title == " ".join(TITLE)


@needs_pdfminer
def test_a_running_head_with_the_page_number_on_its_row_is_a_running_head(tmp_path):
    path = pdf_with_publishing_details(tmp_path / "details.pdf")
    doc = _read(path, 6)
    heads = [b for b in doc.blocks if "Smith and B. Jones" in b.text or b.text == HEAD]
    n = len(doc.raw.pages)
    assert n >= 4 and len(heads) == 2 * n - 1 and all(b.kind == "furniture" for b in heads)   # one on page 1, two after
    assert any(b.kind != "furniture" for b in _read(path, 5).blocks if "Smith and B. Jones" in b.text)


# ------------------------------------------------------------------------------------------------------------------
# the offer
# ------------------------------------------------------------------------------------------------------------------
@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_reader_6_is_offered_to_pdfs_of_reader_5(tmp_path):
    m = re.search(r"^export function newReaderFor\(d, latest\) \{.*?^\}", _src("doc-shared.js"), re.S | re.M)
    assert m, "newReaderFor is gone from doc-shared.js"
    docs = [{"reader": r, "kind": k} for r in (1, 2, 3, 4, 5, 6) for k in ("pdf", "html", "text", "docx")]
    probe = tmp_path / "probe.mjs"
    probe.write_text(m.group(0) + f"\nconsole.log(JSON.stringify({json.dumps(docs)}.map((d) => newReaderFor(d, 6))));\n",
                     encoding="utf-8")
    r = subprocess.run([NODE, str(probe)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    offered = {(d["reader"], d["kind"]) for d, yes in zip(docs, json.loads(r.stdout)) if yes}
    every = {(r, k) for r in (1, 2, 3) for k in ("pdf", "html", "text", "docx")}
    assert offered == every | {(4, "pdf"), (4, "html"), (4, "docx"), (5, "pdf")}
    assert re.search(r"^export const reader = \{ latest: 6 \};", _src("doc-shared.js"), re.M)
    src = _src("sources.js", "doc-reading.js", "doc-shared.js")
    assert "const READER_6_NEWS = " in src and "`Read by the reader of Margin 0.18.1 to 0.19.0rc1. ${READER_6_NEWS}`" in src


# ------------------------------------------------------------------------------------------------------------------
# the rules one by one, on blocks made by hand (with sizes, and without them as pypdf and OCR give lines)
# ------------------------------------------------------------------------------------------------------------------
DIMS = [(595.0, 842.0)] * 3


def _block(text: str, page: int = 0, kind: str = "body", top: float | None = None, size: float | None = None,
           x0: float | None = 60.0, bold: bool = False):
    if top is None:
        x0 = None
    ln = reader.Line(page, text, x0, top, None if x0 is None else x0 + 300, None if top is None else top + (size or 10),
                     size, bold)
    b = reader.Block(page, [ln], kind=kind)
    b.text = text
    return b


def _details(blocks, body_size: float | None = 10.0) -> list[str]:
    from margin import reader6

    reader6.publishing_details(blocks, body_size, DIMS)
    return [b.kind for b in blocks]


def test_prose_in_the_first_pages_footer_stays_unless_it_names_publishing_details():
    foot = dict(top=600.0, size=8.0)
    kept = [_block("Results: Students at the university repaired fewer items than they brought to the repair cafe in "
                   "every month of the study.", kind="abstract", **foot),
            _block("Earlier studies published in this field have found that repair cafes reach people who seldom "
                   "repair anything at home.", **foot),
            _block("2. Methods", kind="heading", **foot),
            _block("It does seem odd that this attack should be coming just when the professionals in", **foot)]
    assert _details(kept) == ["abstract", "body", "heading", "body"]
    out = [_block("This is an open access article under the CC BY license (https://creativecommons.org/licenses/by/4.0/).",
                  **foot),
           _block("Funding was received from the university, and the paper is published open access under a "
                  "Creative Commons licence.", **foot),
           _block("View related articles", **foot),
           _block("1 The plots were walked in April and May, before the heather flowered.", **foot)]
    assert _details(out) == ["front", "front", "front", "footnote"]
    # the same prose higher on the page, or in the text's type, is not looked at
    assert _details([_block("View related articles", top=300.0, size=8.0),
                     _block("View related articles", top=600.0, size=10.0)]) == ["body", "body"]


@pytest.mark.parametrize("sized", [True, False])
def test_publishing_details_are_found_by_how_they_start_with_or_without_sizes(sized):
    where = dict(top=120.0, size=10.0) if sized else {}
    out = ["E-mail: ann.smith@example.org", "Correspondence: Ann Smith, Heath Institute",
           "Received 16 May 2024; Received in revised form 9 August 2024; Accepted 18 September 2024",
           "Received: September 01, 2024", "Available online 19 September 2024", "Published: 9 November 2021",
           "Published online: 2023-03-02", "https://doi.org/10.1016/j.heath.2024.100070",
           "Journal of Heathland Studies 2021, 13, 12351. https://doi.org/10.3390/su132212351",
           "ann.smith@example.org (A. Smith), bob.jones@example.org (B. Jones)"]
    kept = ["Received wisdom holds that ground birds nest where the heather is oldest.",
            "Available online repair guides were used by most visitors to the cafes we studied.",
            "Published 2019 figures show that most visitors repaired one item at each visit.",
            "Accepted 12 marks as the threshold for a repair counted as done, as in earlier work.",
            "Received in May, the forms were read by two of us."]
    for page in (0, 1):
        assert _details([_block(t, page, **where) for t in out], 10.0 if sized else None) == ["front"] * len(out)
        assert _details([_block(t, page, **where) for t in kept], 10.0 if sized else None) == ["body"] * len(kept)
    # after the first two pages only a paragraph that is nothing but a link or a DOI
    assert _details([_block(t, 2, **where) for t in out[:3]] + [_block("https://www.example.org/data", 2, **where)]) \
        == ["body", "body", "body", "front"]


def test_a_publishing_detail_inside_the_abstract_is_set_aside_and_the_abstract_stays():
    blocks = [_block("http://doi.org/10.1590/1809-43412023v20d911", kind="abstract", top=300.0, size=10.0),
              _block("The repairs were received well by the visitors, who came back in May 2023 with more of their "
                     "broken things.", kind="abstract", top=320.0, size=10.0),
              _block("Correspondence: Ann Smith, ann.smith@example.org", kind="abstract", top=360.0, size=10.0)]
    assert _details(blocks) == ["front", "abstract", "front"]


def _title_and(next_block, title_size: float = 14.0):
    t = _block("Counting ground nests on heathland plots over three springs", kind="title", top=130.0, size=title_size)
    return [t, next_block]


def test_a_titles_last_line_joins_it_and_nothing_else_does():
    from margin import reader6

    joined = reader6.join_title(_title_and(_block("of walking", kind="front", top=147.0, size=14.0)))
    assert len(joined) == 1 and [ln.text for ln in joined[0].lines][-1] == "of walking"
    for other in (_block("Ann Smith, Bob Jones", kind="front", top=147.0, size=11.0),       # other type: the authors
                  _block("of walking", kind="front", top=190.0, size=14.0),                # far below
                  _block("of walking", kind="front", top=147.0, size=14.0, x0=250.0),      # elsewhere on the line
                  _block("of walking", kind="front", top=147.0, size=14.0, bold=True),     # bold
                  _block("of walking", page=1, kind="front", top=147.0, size=14.0),        # on the next page
                  _block("of walking", kind="body", top=147.0, size=14.0),                 # text, not front matter
                  _block("ann.smith@example.org", kind="front", top=147.0, size=14.0)):    # an e-mail
        assert len(reader6.join_title(_title_and(other))) == 2, other.text


@needs_pdfminer
def test_a_report_whose_running_head_is_its_title_keeps_its_title(tmp_path):
    fl = pdfmake.Flow(columns=[(60, 475)], top=640, bottom=80, size=10, running_head="Repair Cafes in Hungary 2024")
    for k in range(14):
        fl.paragraph(BODY * 3)
    fl.pages[0].text("Repair Cafes in Hungary", 60, 700, "Helvetica-Bold", 18)
    path = tmp_path / "report.pdf"
    fl.write(path)
    doc = _read(path, 6)
    assert len(doc.raw.pages) >= 3
    assert [b.text for b in doc.blocks if b.kind == "title"] == ["Repair Cafes in Hungary"]
    assert all(b.kind == "furniture" for b in doc.blocks if b.text == "Repair Cafes in Hungary 2024")


@needs_pdfminer
def test_the_cue_pass_without_sizes(tmp_path, monkeypatch):
    """A PDF read without pdfminer (pypdf's lines: no sizes, no boxes): the publishing details are found by how
    they start, and the text stays."""
    path = pdf_with_publishing_details(tmp_path / "details.pdf")
    monkeypatch.setattr(reader, "pdfminer_available", lambda: False)
    doc = _read(path, 6)
    assert doc.reading["engine"] == "pypdf"
    kinds = {" ".join(b.text.split()): b.kind for b in doc.blocks}
    hits = {t: k for t, k in kinds.items() if t.startswith(("E-mail address", "Received 16 May", "Available online"))}
    assert hits and set(hits.values()) == {"front"}
    assert all(k == "body" for t, k in kinds.items() if t.startswith("Received wisdom"))
