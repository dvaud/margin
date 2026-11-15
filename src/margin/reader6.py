"""Reader 6 (Margin 0.19): text a form crops away, publishing details after the text has begun, and the title.

`reader.read_blocks(raw, version=6)` calls the rules here; `version=5` and below still read exactly as before. Only
PDFs read otherwise: a Word file, a web page or a text file reads as by reader 5. No model is used.

1. **Text a form crops away.** A PDF can place a whole page inside a form (a Form XObject) and show only a window of
   it: its /BBox. MDPI's papers do so with figures cut out of a draft page ("Sustainability 2021, 13, x FOR PEER
   REVIEW"). pdfminer gives every character of a form, seen or not, and reads the /BBox as x, y, width and height, so
   the hidden draft came out as dozens of one-line figure blocks between the lines of the real text. Reader 6 reads
   PDFs with a device (`ClippedAggregator`) that keeps only the characters whose centre lies inside the form's window
   (inside a form in a form: inside both), and gives the form the box it shows. Clipping by paths (`W n`) is not
   honoured: pdfminer does not give it.
2. **A form is a figure.** Reader 5 took a form full of words (more than 900 characters, paragraphs among its lines,
   rows of cells) for text set in a box. A form that shows a diagram of words is a figure all the same:
   for reader 6 those rules hold only for a cluster of drawings (`form_figure`).
3. **Publishing details after the text has begun** (`publishing_details`, after `reader.classify`). The front matter
   of a PDF ends at its first paragraph of text; a publisher that prints the e-mails, the DOI and the dates in the
   first page's footer (Elsevier) had them read as text. On the first page a block in the lower part, in smaller
   type than the text, is front matter (a footnote, if it starts with a footnote's mark), unless it reads as prose
   and names no publishing detail (an old paper sets its whole first page smaller); on the first two pages a
   short block that starts with a publishing detail ("E-mail address:", a doi.org link, "Received 5 May 2023",
   "Available online", ©, ISSN, "Correspondence:" …) is front matter; and anywhere a block that is only a link or a
   DOI. "Received" counts only with a date, so "Received wisdom holds …" stays text.
4. **The journal's name is not the title.** The title is the largest type near the top of the first page; a
   journal's banner can be larger. A title candidate whose words begin the first page's running head (the journal's
   name, its volume and year) is front matter when another candidate follows on the page, which is the title (a
   report whose running head is its own title keeps it). A cover page that names only the journal is not caught. A title's last line that came
   apart from it (in the same type, just under it) is part of the title (`join_title`), not front matter.
5. **A running head seen once.** A running head stands apart from the text (`reader.mark_furniture`); the line it
   was measured against could be the page number (or another running head) at the other end of its own row, so
   every other page kept its head as text. Reader 6 measures against the nearest line towards the middle of the page
   that is not a page number or running head on its row.
"""
from __future__ import annotations

import re

try:
    from pdfminer.converter import PDFPageAggregator
    from pdfminer.layout import LTChar
    from pdfminer.utils import apply_matrix_rect, mult_matrix
except Exception:  # noqa: BLE001 - without pdfminer a PDF is read with pypdf: only rules 3 and 4 apply
    PDFPageAggregator = object


# ------------------------------------------------------------------------------------------------------------------
# 1. text a form crops away
# ------------------------------------------------------------------------------------------------------------------
class ClippedAggregator(PDFPageAggregator):
    """pdfminer's page aggregator that honours a form's /BBox: a character whose centre lies outside the window of the
    form (or of any form it is in) is not kept, and the form's box is the window it shows."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._clips: list[tuple[float, float, float, float]] = []
        self._ctms: list = []

    def begin_figure(self, name, bbox, matrix) -> None:
        self._ctms.append(self.ctm)
        super().begin_figure(name, bbox, matrix)
        # the corners of the /BBox in the page's space (pdfminer reads it as x, y, width, height: its box was too large)
        x0, y0, x1, y1 = apply_matrix_rect(mult_matrix(matrix, self.ctm), tuple(float(v) for v in bbox))
        if self._clips:
            c = self._clips[-1]
            x0, y0, x1, y1 = max(x0, c[0]), max(y0, c[1]), min(x1, c[2]), min(y1, c[3])
        clip = (x0, y0, max(x0, x1), max(y0, y1))
        self._clips.append(clip)
        self.cur_item.set_bbox(clip)

    def end_figure(self, name) -> None:
        self._clips.pop()
        super().end_figure(name)
        # pdfminer leaves the form's own matrix as the device's: a form drawn straight after it (no q/Q, no cm
        # between) would be placed, and clipped, by the wrong one
        self.set_ctm(self._ctms.pop())

    def render_char(self, *a, **k) -> float:
        adv = super().render_char(*a, **k)
        if self._clips:
            objs = self.cur_item._objs
            if objs and isinstance(objs[-1], LTChar):
                ch, c = objs[-1], self._clips[-1]
                cx, cy = (ch.x0 + ch.x1) / 2, (ch.y0 + ch.y1) / 2
                if not (c[0] <= cx <= c[2] and c[1] <= cy <= c[3]):
                    objs.pop()   # outside the window: never shown
        return adv


def extract_pages(path, laparams=None):
    """`pdfminer.high_level.extract_pages` with `ClippedAggregator` for its device."""
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
    from pdfminer.pdfpage import PDFPage

    with open(path, "rb") as fp:
        rm = PDFResourceManager(caching=True)
        dev = ClippedAggregator(rm, laparams=laparams)
        interp = PDFPageInterpreter(rm, dev)
        for page in PDFPage.get_pages(fp, None, maxpages=0, password="", caching=True):
            interp.process_page(page)
            yield dev.get_result()


# ------------------------------------------------------------------------------------------------------------------
# 2. a form is a figure
# ------------------------------------------------------------------------------------------------------------------
def form_figure(box, rec) -> bool:
    """A figure candidate that is (mostly) a form, not an image nor a cluster of drawings: what reader 5 took for
    text in a box when it holds many words is a figure for reader 6."""
    from .reader5 import _area, _overlap

    return any(_overlap(box, f[:4]) >= 0.8 * max(1.0, _area(box)) for f in rec.figures if not f[4])


# ------------------------------------------------------------------------------------------------------------------
# 3. publishing details after the text has begun
# ------------------------------------------------------------------------------------------------------------------
_MONTH = (r"(january|february|march|april|may|june|july|august|september|october|november|december"
          r"|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\b\.?")
# a date with its day and month ("5 May 2023", "May 5, 2023", "05.05.2023", "2023-05-05"); a year alone is not one
# ("Published 2019 figures show …")
_DATE = (rf"(\d{{1,2}}(st|nd|rd|th)?\s+{_MONTH}|{_MONTH}\s+\d{{1,2}}\b|\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}"
         rf"|\d{{4}}-\d{{1,2}}-\d{{1,2}})")
# what a publishing detail starts with (after a mark or two: "*", "✉", a superscript letter)
CUE = re.compile(
    r"^\W{0,3}("
    r"e-?mails?(\s+address(es)?)?\s*[:：]|"
    r"https?://(dx\.)?doi\.org/|doi\s*:|"
    rf"received\s*:?\s*(in revised form|{_DATE})|revised\s*:?\s*{_DATE}|accepted\s*:?\s*{_DATE}|"
    rf"available online\s*:?\s*(on\s+|from\s+)?{_DATE}|published(\s+online)?\s*:?\s*(on\s+)?{_DATE}|"
    r"©|\(c\)\s*\d{4}|copyright\s*:?\s*©|issn\b|\d{4}-\d{3}[\dx]\s*/|"
    r"(to\s+)?cite this( article| paper)?\s*:?|citation\s*:|correspondence\s*:|\*?\s*corresponding authors?\b|"
    r"present address|this is an open access article)",
    re.I)
_DOI_LINK = re.compile(r"https?://(dx\.)?doi\.org/\S+", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_ONLY_LINK = re.compile(r"\(?\s*(https?://\S+|www\.\S+|doi\s*:\s*\S+|10\.\d{4,9}/\S+)\s*\)?[.;]?", re.I)
CHANGES = ("body", "abstract", "heading")
FOOTER_TOP = 0.55       # the first page's footer: below this share of the page's height
FOOTER_SMALLER = 0.6    # in type this many points smaller than the text's
CUE_SHORT = 300         # a publishing detail: shorter than this (characters)
DOI_SHORT = 160         # a line with a DOI's link in it ("Sustainability 2021, 13, 12351. https://doi.org/…")


def _cue(t: str) -> bool:
    return len(t) < CUE_SHORT and bool(CUE.match(t))


def _mostly_emails(t: str) -> bool:
    found = [m.group(0) for m in _EMAIL.finditer(t)]
    return bool(found) and len(t) < CUE_SHORT and sum(len(e) for e in found) >= 0.4 * len(t.replace(" ", ""))


def publishing_details(blocks: list, body_size: float | None, dims: list[tuple[float, float]]) -> int:
    """Blocks of the first pages that `reader.classify` read as text (or as the abstract, or a heading) but hold the
    article's publishing details: made front matter (or a footnote). Returns how many were changed."""
    from .reader import _FOOT_MARK, _FRONT, _FRONT_START, _is_section, _sentence_like

    changed = 0
    for b in blocks:
        if b.kind not in CHANGES:
            continue
        t = " ".join(b.text.split())
        if not t:
            continue
        ln = b.lines[0]
        h = dims[b.page][1] if b.page < len(dims) else None
        new = None
        footer = b.page == 0 and h and ln.top is not None and ln.size and body_size \
            and ln.top > FOOTER_TOP * h and ln.size <= body_size - FOOTER_SMALLER \
            and not (b.kind == "heading" and _is_section(t))
        # the first page's footer, in smaller type: a note, or publishing details. Prose there is set aside only when
        # it starts with a publishing detail or names two or more (an old paper sets its whole first page smaller;
        # an abstract can run into the lower half)
        if footer and _FOOT_MARK.match(t) and not _cue(t):
            new = "footnote"
        elif footer and (not _sentence_like(t) or _cue(t) or _FRONT_START.match(t)
                         or len({m.group(0).lower() for m in _FRONT.finditer(t)}) >= 2):
            new = "front"
        # a publishing detail on the first two pages, with sizes or without them (OCR, pypdf)
        elif b.page <= 1 and (_cue(t) or (len(t) < DOI_SHORT and _DOI_LINK.search(t)) or _mostly_emails(t)):
            new = "front"
        # anywhere: a paragraph that is only a link or a DOI
        elif b.kind == "body" and _ONLY_LINK.fullmatch(t):
            new = "front"
        if new is not None:
            b.kind = new
            changed += 1
    return changed


# ------------------------------------------------------------------------------------------------------------------
# 4. the journal's name is not the title
# ------------------------------------------------------------------------------------------------------------------
def _words(t: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", t.lower()))


def banner(bi: int, blocks: list, body_size: float | None, height: float | None) -> bool:
    """Whether the title candidate `blocks[bi]` on the first page is the journal's name: its words begin a running
    head of the first page ("Cleaner Production Letters" in "Cleaner Production Letters 7 (2024) 100070"), and
    another title candidate follows it on the page (a report whose running head is its own title keeps it)."""
    w = _words(" ".join(ln.text for ln in blocks[bi].lines))
    if len(w) < 4:
        return False
    named = False
    for b in blocks:
        if b.page > 0:
            break
        if b.lines[0].furniture == "head":
            head = _words(" ".join(x.text for x in b.lines))
            # the rest of the head is the volume, the year, the pages: a short title as the head of later pages is not
            if head.startswith(w + " ") and re.search(r"\d", head[len(w):]):
                named = True
                break
    return named and any(_candidate(b, body_size, height) for b in blocks[bi + 1:] if b.page == 0)


def _candidate(b, body_size: float | None, height: float | None) -> bool:
    """A block that `reader.classify` could take for the title: on the first page, a heading in type 2 points larger
    than the text, in the upper half."""
    from .reader import _heading_like

    ln = b.lines[0]
    return bool(not ln.furniture and not ln.figure and b.kind != "table" and body_size and ln.size
                and ln.size >= body_size + 2 and height and ln.top is not None and ln.top < 0.5 * height
                and _heading_like(b, body_size))


def join_title(blocks: list) -> list:
    """The title's lines that came apart from it: a block just under the title on the first page, in the same type,
    that `reader.classify` made front matter or a heading, joins the title block."""
    out: list = []
    title = None      # the title, while the next block may be its last line
    found = False
    for b in blocks:
        if title is not None and b.page == 0 and b.kind in ("front", "heading") \
                and _goes_on(title.lines[-1], b.lines[0]):
            title.lines.extend(b.lines)
            continue
        title = b if b.kind == "title" and not found else None
        found = found or b.kind == "title"
        out.append(b)
    return out


def _goes_on(last, ln) -> bool:
    """A line that goes on with the title: in its type, just under its last line, at its left edge."""
    return bool(last.size and ln.size and abs(last.size - ln.size) <= 0.3 and last.bold == ln.bold
                and None not in (last.top, ln.top, last.x0, ln.x0)
                and 0 <= ln.top - (last.bottom or last.top) <= 0.8 * ln.size and abs(ln.x0 - last.x0) <= 0.5 * ln.size
                and "@" not in ln.text)
