"""A codebook from a theory document (0.18.1, roadmap K2 part 2, Level 0: no model).

A third way to start in the codebook editor, beside *Start fresh* and *From the themes*: *From a theory document*. The
codes are the theory's own concepts (from Meadows: stock, flow, reinforcing loop, delay, leverage point…), each with a
**definition quoted from the theory, with its page**, so the codebook says where each code comes from. Its examples
come **only from the evidence documents** (never from a theory document), offered by keyword match and kept only when
the researcher ticks them: the labeller then learns what a reinforcing loop looks like in a care home, not in Meadows'
fishery.

The candidates, from the document's own structure and words, best first (rewritten for 0.19.0: the first version
offered every sentence that starts "X is a …" as a definition, ticked, so a book gave "Takes", "Say" and "Tree" beside
its printer's marks):

1. **its glossary**: the entries under a heading that says so ("Glossary", "Definitions", "Key terms"), each "Term:
   definition" or "Term — definition", the definition quoted. A document with a glossary says itself which its
   concepts are: only its entries are ticked (without one the defined terms are, unless a long text defines fewer
   than three);
2. **defined in the text**: a sentence that starts with the term and says what it is: "X is defined as …", "X refers
   to …", "by X we mean …", "we call this X", "X (also called Y) is …", and "X is a …" when X is a phrase, a heading,
   or defined so twice (alone, "A tree is a system" names an example). The subject must be a term: not "This
   behavior", "Its inflow", "All it takes";
3. **headings**: the terms a heading names ("Stocks, Flows, and Dynamic Equilibrium": three; "Policy Resistance—Fixes
   that Fail": the first), numbering taken off, when prose follows the heading (a table of contents, a chapter's
   number and a figure's label have none) and the text uses the term;
4. **frequent phrases**: words and phrases of up to four words the document uses often and the evidence documents do
   not (a word every document of the project uses is not the theory's own), at most MAX_FREQUENT.

A term must come back in the text to count (more often in a book than in a few pages). The definition of a term that
is not a glossary entry is the sentence that best says what it means among those that use it (`_defining_score`),
never a heading. Lines that are not the theory's prose are left out first: lines repeated on page after page (running
heads, printer's marks), tables of contents, equations.

Every quote is a span of the document's own text (checked by finding it again, as quotes are everywhere). Words set in
italics are not offered: the readers do not keep fonts' slant (only boldness). The rules are English ("is defined
as"); a document in another language still gives its glossary, headings and frequent phrases.

0.18.4: **the optional AI draft** (Level 2 or 3, `ai_offer`, `draft_with_ai`). 0.19.0 (theory-codes-v2): the AI reads
**the whole document**, a part at a time (`_ai_parts`: its body passages in order, at most AI_MAX_CHARS a part, fewer
for a local model whose context length the person set smaller, `_part_chars`; v1 read twelve passages of it, 5% of a
book, and a local model's automatic context length did not hold even those). Each part is one `theory_codes` task, given the Level-0 candidates as hints
and the part's passages, and drafts the concepts that part defines or explains: each a short name, a definition quoted
exactly from the document (at least three whole words; the quote check sends a quote that is not there back to be
fixed, as for every kind) and a one-line reason; a part without a concept gives none. The parts' drafts are put
together (`ai_drafts`): a concept drafted from several parts is offered once, with the quote that best defines it, the
most central first. The document's own AI setting picks the reader (Claude, a local AI, or none: then no draft is
offered). The drafts join the list unticked and marked as the AI's, without the terms the document defines itself
(its glossary's and the defined ones); a heading or a frequent word the AI drafts too is offered with the AI's
definition. Their examples still come only from the evidence (`suggest_examples`), never from the AI. A draft asked
again with the same input reuses its answers, part by part.

0.19: **several theory documents at once** (a framework built from five authors). The editor asks for each document's
candidates (and its AI draft) separately; each draft code says which document it comes from (`source_doc`), and
`codebooks.create` makes one group of codes per document and keeps no example from any of them.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import re
from collections import Counter
from typing import Callable, Iterable

from .store import Workspace
from .textutil import split_sentences

MAX_TERM_WORDS = 4
MAX_CANDIDATES = 40
MAX_EXAMPLES = 3
_W = r"[^\W\d_][\w'’-]*"     # a word of any script (0.19.0: "[A-Za-zÀ-ÿ]" cut Hungarian "ő" and all of Cyrillic)
_TERM = rf"((?:{_W}\s+){{0,{MAX_TERM_WORDS - 1}}}{_W})"
# a term at the start of a sentence (an article before it allowed), then the defining words
_SUBJECT = rf"^(?:(?:A|An|The)\s+)?{_TERM}"
_DEFINES = [
    re.compile(rf"{_SUBJECT}\s+(?:is|are|can\s+be|may\s+be)\s+(?:defined|understood|conceived)\s+as\s+", re.I),
    re.compile(rf"{_SUBJECT}\s+(?:refers?|refer)\s+to\s+", re.I),
    re.compile(rf"\bby\s+(?:(?:a|an|the)\s+)?{_TERM},?\s+(?:we|I)\s+mean\b", re.I),
    re.compile(rf"\b(?:we|I)\s+call\s+(?:this|these|it|them|such\s+\w+)\s+(?:(?:a|an|the)\s+)?{_TERM}\b", re.I),
    re.compile(rf"{_SUBJECT}\s*\((?:also\s+(?:called|known\s+as)|or)\s+[^)]{{1,60}}\)\s+(?:is|are)\s+", re.I),
    re.compile(rf"{_SUBJECT}\s+(?:is|are)\s+(?:a|an|the)\s+", re.I),       # the plain one, last: see _WEAK_AT
]
_WEAK_AT = len(_DEFINES) - 1   # "X is a …" alone does not make X a concept ("A tree is a system")
_CALL_AT = 3                   # "we call this X": the term is followed by any words, not by a verb that ends it
_NUMBERING = re.compile(r"^\s*(?:(?:chapter|part|section)\s+)?(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.)\s+", re.I)


def _stop() -> frozenset[str]:
    from .stopwords import ENGLISH, STOPWORDS_V1

    return frozenset(STOPWORDS_V1 | ENGLISH | {"chapter", "section", "figure", "table", "example", "page", "part"})


def _norm(term: str) -> str:
    t = term.lower().strip(" .,:;'\"’()")
    return t[:-1] if len(t) > 4 and t.endswith("s") and not t.endswith("ss") else t


MIN_DEFINITION_WORDS = 3


def _words(quote: str) -> int:
    """Whole words in a quote; in a script written without spaces (Chinese, Thai…) a character counts as a word."""
    from .textutil import _unspaced

    n = 0
    for tok in quote.split():
        u = sum(1 for c in tok if _unspaced(c))
        n += u + any(c.isalnum() and not _unspaced(c) for c in tok) if u else 1
    return n


def _clean_term(term: str, stop: frozenset[str]) -> str | None:
    words = term.strip(" .,:;'\"’()").split()
    while words and words[0].lower() in stop:
        words = words[1:]
    while words and words[-1].lower() in stop:
        words = words[:-1]
    if not words or len(words) > MAX_TERM_WORDS or all(w.lower() in stop for w in words):
        return None
    t = " ".join(words)
    return t if 3 <= len(t) <= 60 and not t.isdigit() else None


def _page(ws: Workspace, doc_id: str, at: int) -> int | None:
    r = ws.query("SELECT page FROM pages WHERE doc_id=? AND start<=? AND ?<end", (doc_id, at, at))
    return r[0]["page"] if r else None


def _quote(ws: Workspace, doc_id: str, text: str, a: int, z: int) -> dict:
    q = " ".join(text[a:z].split())
    return {"quote": q, "start": a, "end": z, "page": _page(ws, doc_id, a)}


def _body_lines(ws: Workspace, doc_id: str, text: str) -> list[tuple[int, int]]:
    """The lines of the document's body passages (what the reader counts as its text), in order: a heading and the
    paragraph under it share a passage, and each is a line of its own."""
    out: list[tuple[int, int]] = []
    for a, z in ws.query("SELECT start, end FROM passages WHERE doc_id=? AND section='body' ORDER BY start", (doc_id,)):
        at = a
        for line in re.split(r"(\n+)", text[a:z]):
            if line.strip() and not line.startswith("\n"):
                out.append((at, at + len(line)))
            at += len(line)
    return out


def _line_key(line: str) -> str:
    """A line with its numbers masked: a running head or a printer's mark is the same line on every page but for the
    page number, the date and the time."""
    return re.sub(r"\d+", "#", " ".join(line.lower().split()))


# a section's number before its title ("1.3 Practice theories"), not a figure in a sentence ("from 2.5 to 3.7 percent")
_SECTION_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)+\s+[^\W\d_a-z]")
_ENDS_IN_PAGE = re.compile(r"\s\d{1,4}$")
_SENTENCE_END_INSIDE = re.compile(r"[.!?]['”\")]?\s")


def _contents_like(line: str) -> bool:
    """A line of a table of contents or a list of figures: several numbered titles ("1.2 Feedback 9 1.3 Traps 21"),
    or a short line without a sentence in it that ends in a page number. A paragraph with figures in it is prose."""
    s = line.strip()
    if len(_SECTION_NUMBER.findall(s)) >= 2:
        return True
    return len(s) <= 160 and bool(_ENDS_IN_PAGE.search(s)) and not _SENTENCE_END_INSIDE.search(s)


def _equation(line: str) -> bool:
    """A line of a model's equations ("Inflow: heating = discrepancy x 10%"): short, or one sign after another. A
    paragraph that holds a formula ("with r = 0.02 the stock doubles …") is prose."""
    n = line.count(" = ")
    return n >= 3 or (n >= 1 and len(line.strip()) <= 120)


def _clean_lines(lines: list[tuple[int, int]], text: str) -> tuple[list[tuple[int, int]], set[str]]:
    """The body's lines without what is not the theory's own prose: lines repeated on page after page (running heads,
    printer's marks: the same line three times or more, numbers aside), tables of contents, equations, and lines
    without a word.
    Returns the lines kept and the keys of the repeated lines (a heading that is one of them is no heading)."""
    seen = Counter(_line_key(text[a:z]) for a, z in lines if z - a <= 160)
    repeated = {k for k, n in seen.items() if n >= 3}
    kept = []
    for a, z in lines:
        s = text[a:z]
        if not re.search(_W, s) or _line_key(s) in repeated or _contents_like(s) or _equation(s):
            continue
        kept.append((a, z))
    return kept, repeated


def _sentences(lines: list[tuple[int, int]], text: str) -> list[tuple[int, int]]:
    """The sentences of these lines, in order. A sentence never runs over a line break, so "A stock is …" starts its
    own sentence after the heading "1. Stocks and flows"."""
    out: list[tuple[int, int]] = []
    for a, z in lines:
        out += split_sentences(text[a:z], a)
    return out


# ---- what a term may be -----------------------------------------------------------------------------------------
# words a sentence may start with that are never the subject a definition names ("This behavior is an example of…",
# "All it takes is a click", "Say you are a young boy…")
_NOT_SUBJECT = frozenset("""it this that these those there here its their our my his her your one another each every
some such what which who whom whose all both first second third fourth fifth last next other others then thus so and
or but if when while as say perhaps especially maybe now today yet still even also only just many much most more less
few several he she they we you i people someone something anything everything nothing no not any how why where
two three four five six seven eight nine ten eleven twelve""".split())
_INNER = frozenset({"of", "the", "and", "to", "in", "for", "a", "an", "on"})   # may stand inside a term, never at its ends
# small words that join words and are part of no term (the search's stop words are few: these stand beside them)
_FUNCTION = frozenset("""before after among amongst between through throughout across during within without toward
towards upon via whether although though because since until unless above below against along beyond around about
over under into onto from with by at as than then also very too not no nor yet so if when while where which who whom
whose what that this these those there here its their our my his her your it they we you he she i is are was were be
been being am has have had do does did will would shall should can could may might must""".split())
# headings that name a part of the book, not a concept of the theory
_STRUCTURE = frozenset("""introduction conclusion conclusions appendix appendices preface foreword contents
bibliography references index acknowledgements acknowledgments notes note summary abstract glossary epilogue prologue
afterword overview discussion background method methods results figures tables interlude definitions basics part
chapter section one two three four five six seven eight nine ten eleven twelve""".split())
# general English words every book uses often: never offered for their frequency alone (a word of these that the text
# defines, lists in its glossary or sets as a heading is still offered)
_GENERIC = frozenset("""example examples way ways time times people thing things kind kinds part parts point points
case cases fact facts world year years number numbers place places use uses new old good bad great little big small
long short high low different same important possible likely real whole true hard easy simple make makes made take
takes taken give gives given get gets come comes go goes see seen know known think say said want need needs work
works find found look looks keep kept turn put set show shows shown mean means book chapter page question questions
answer answers problem problems idea ideas word words term terms sense reason reasons result results end side level
form forms course matter man men woman women person human humans life lives day days today study studies approach
approaches view views author authors reader readers rather often usually simply perhaps however therefore indeed
within without another others something anything everything nothing always never sometimes through across
among between around toward towards upon via whether although though because since until unless during before after
above below against along beyond""".split())
_GENERIC_KEYS = _GENERIC | frozenset(_norm(w) for w in _GENERIC)
_STRUCTURE_KEYS = _STRUCTURE | frozenset(_norm(w) for w in _STRUCTURE)
_SPLIT_DASH = re.compile(r"\s*(?:[—–:•;]|\s-\s)\s*")                    # "Policy Resistance—Fixes that Fail"
_SPLIT_LIST = re.compile(r"\s*(?:,\s*and\s+|,|\s+and\s+|\s+&\s+|/)\s*")     # "Stocks, Flows, and Dynamic Equilibrium"
_PANEL = re.compile(r"^[A-Za-z]\)?[:.)]\s")                                 # a figure's panel: "A: Growth"
MAX_HEADING_WORDS = 6
MAX_FREQUENT = 12       # words offered for their frequency alone, after the defined terms and the headings
_GLOSSARY_HEAD = re.compile(r"\b(glossary|definitions|key\s+(?:terms|concepts)|terminology)\b", re.I)
_ENTRY_TERM = rf"{_W}(?: {_W}){{0,4}}"
_ENTRY = re.compile(rf"^\s*(?:[•*·]\s*)?({_ENTRY_TERM})\s*(?::|\s[—–-]\s|—)\s*(?=\S)")
# a second entry on the same line ("… of its components. Feedback loop: The mechanism …")
_ENTRY_INLINE = re.compile(rf"(?<=[.!?”\"’])\s+(?=[^\W\d_a-z][\w'’-]*(?: {_W}){{0,4}}:\s+\S)")
MAX_GLOSSARY_CHARS = 60000


def _subject(raw: str, stop: frozenset[str]) -> str | None:
    """The term a defining sentence starts with, or None when its subject is no term: every word of it a content
    word, but for the small words a term may hold inside ("tragedy of the commons")."""
    words = raw.strip(" .,:;'\"’()").split()
    if not words or len(words) > MAX_TERM_WORDS:
        return None
    low = [w.lower() for w in words]
    no = stop | _NOT_SUBJECT | _FUNCTION
    if low[0] in no or low[-1] in no or any(w in no and w not in _INNER for w in low[1:-1]):
        return None
    t = " ".join(words)
    return t if 3 <= len(t) <= 60 and not t.isdigit() else None


def _glossary(lines: list[tuple[int, int]], text: str, headings: list) -> list[tuple[str, tuple[int, int]]]:
    """The entries of the document's own glossary, when it has one: [(term, (start, end) of its definition)]. A
    glossary is the lines under a heading that says so ("Glossary", "Definitions", "Key terms"), up to the next
    heading, each "Term: definition" or "Term — definition"; several entries may share a line. Fewer than three
    entries, or entries on fewer than half of the lines, is no glossary."""
    best: list[tuple[str, tuple[int, int]]] = []
    for i, h in enumerate(headings):
        title = " ".join((h["text"] or text[h["start"]:h["end"]]).split())
        if not _GLOSSARY_HEAD.search(title) or len(title.split()) > 8:
            continue
        end = next((n["start"] for n in headings[i + 1:] if n["start"] >= h["end"]
                    and not _ENTRY.match(text[n["start"]:n["end"]])), len(text))
        end = min(end, h["end"] + MAX_GLOSSARY_CHARS)
        entries: list[tuple[str, tuple[int, int]]] = []
        n_lines = 0
        open_entry = False
        for a, z in lines:
            if a < h["end"] or a >= end:
                continue
            n_lines += 1
            cuts = [0] + [m.end() for m in _ENTRY_INLINE.finditer(text[a:z])] + [z - a]
            for ca, cz in zip(cuts, cuts[1:]):
                piece = text[a + ca:a + cz]
                m = _ENTRY.match(piece)
                if m:
                    open_entry = len(piece[m.end():].split()) >= MIN_DEFINITION_WORDS
                    if open_entry:      # (an entry too short to define anything is left out, not added to the last)
                        entries.append((m.group(1).strip(), (a + ca + m.end(), a + ca + len(piece.rstrip()))))
                elif entries and open_entry and piece.strip() and not text[entries[-1][1][1]:a + ca].strip():
                    # the entry before it runs on: only on the very next line (a running head between two pages of
                    # the glossary ends it)
                    t, (da, _dz) = entries[-1]
                    entries[-1] = (t, (da, a + ca + len(piece.rstrip())))
                else:
                    open_entry = False
        if len(entries) >= 3 and len(entries) * 2 >= n_lines and len(entries) > len(best):
            best = entries
    return best


def _term_rx(term: str) -> re.Pattern:
    """The term in running text, in the singular or the plural, across a line break or a hyphen."""
    words = re.findall(_W, term)
    if not words:
        return re.compile(r"(?!)")           # no word in it: found nowhere
    last = words[-1]
    stem = last[:-1] if len(last) > 4 and last.lower().endswith("s") and not last.lower().endswith("ss") else last
    return re.compile(r"(?<![\w'’-])" + r"[\s\-]+".join([re.escape(w) for w in words[:-1]] + [re.escape(stem)])
                      + r"(?:e?s)?(?![\w'’-])", re.I)


_DEFINED_AS = re.compile(r"\s+(?:(?:is|are|can\s+be|may\s+be)\s+(?:defined|understood|conceived)\s+as|refers?\s+to|"
                         r"(?:means?|denotes?))\b", re.I)
_ALSO_CALLED = re.compile(r"\s*\((?:also\s+(?:called|known\s+as)|or)\s+[^)]{1,60}\)\s+(?:is|are)\b", re.I)
_IS_A = re.compile(r"\s+(?:is|are)\s+(?:a|an|the)\b", re.I)
_IS = re.compile(r"\s+(?:is|are)\b", re.I)
_APPOSITION = re.compile(r"\s*(?:[—–:]|,\s+(?:that\s+is|i\.e\.))", re.I)
_NAMED = re.compile(r"\b(?:call(?:ed|s)?|termed|known\s+as|notion\s+of|concept\s+of|the\s+term)\s+"
                    r"(?:(?:a|an|the|this|these|it|them)\s+)?[“\"‘']?$", re.I)


def _defining_score(s: str, m: re.Match) -> int:
    """How well a sentence that uses a term says what it means (the higher the better; 6 or more: it defines it)."""
    lead, after = s[:m.start()], s[m.end():]
    at_start = re.sub(r"^\s*(?:\d+[.)]|[•*·])\s*", "", lead).strip().lower() in ("", "a", "an", "the")
    score = 0
    if at_start:
        if _DEFINED_AS.match(after):
            score = 8
        elif _ALSO_CALLED.match(after):
            score = 7
        elif _IS_A.match(after):
            score = 6
        elif _IS.match(after) or _APPOSITION.match(after):
            score = 3
        else:
            score = 2
    elif _NAMED.search(lead):
        score = 3
    elif _APPOSITION.match(after):
        score = 4
    if not s[:1].isupper() and not s[:1] in "“\"‘'":
        score -= 2                       # a piece of a list or of a broken line, not a sentence
    n = len(s.split())
    score += -4 if n < 6 else 1 if n <= 45 else -1 if n <= 70 else -3
    if s.rstrip().endswith("?"):
        score -= 6
    elif s.rstrip()[-1:] not in ".!”\"’')":
        score -= 2                       # cut off: a line that broke before its sentence ended
    if re.match(r"(?:[A-Z][\w'’—–-]*\s+(?:(?:of|the|to|and|in|a|for)\s+)*){3}[A-Z]", s):
        score -= 3                       # a heading run into the sentence under it
    return score


def _best_definition(term: str, where: list[int], sents: list[tuple[int, int]], text: str,
                     skip: frozenset[int] = frozenset()) -> tuple[int, int] | None:
    """The sentence that best says what a term means, among those that use it (the earliest of the best). `skip`: the
    sentences that are headings, never a definition."""
    rx = _term_rx(term)
    best, best_score = None, -99
    for i in where[:400]:
        if i in skip:
            continue
        a, z = sents[i]
        s = text[a:z]
        m = rx.search(s)
        if not m:
            continue
        sc = _defining_score(s.strip(), rx.search(s.strip()) or m)
        if sc > best_score:
            best, best_score = (a + (len(s) - len(s.lstrip())), z), sc
    return best


def _evidence_words(ws: Workspace, skip: str, cap: int = 3_000_000) -> tuple[Counter, int]:
    """How often each word occurs in the evidence documents (never a theory or a working document, nor `skip`), read
    up to `cap` characters: what the theory's words are compared with, so that words every document of the project
    uses are not offered as the theory's own."""
    from .docrole import not_evidence_docs

    out: Counter = Counter()
    left = cap
    skipped = not_evidence_docs(ws._conn()) | {skip}
    for r in ws.query("SELECT doc_id, text FROM documents ORDER BY doc_id"):
        if r["doc_id"] in skipped or not r["text"]:
            continue
        t = r["text"][:left]
        out.update(_norm(w) for w in re.findall(_W, t))
        left -= len(t)
        if left <= 0:
            break
    return out, sum(out.values())


def candidates(ws: Workspace, doc_id: str, limit: int = MAX_CANDIDATES, with_examples: bool = True) -> dict:
    """The candidate concepts of a theory document as draft codes: {"doc_id", "title", "role", "concepts": [{"term",
    "how" ("glossary" | "defined" | "heading" | "frequent"), "ticked" (offered ticked: its glossary's entries and the
    terms it defines), "count" (the sentences that use it), "definition": {"quote", "start", "end", "page"} | None,
    "code": {code, description, described, group, keywords, include, exclude, examples: []}, "suggested": [examples
    from the evidence documents, to tick]}]}. `with_examples` False: no examples looked for (0.18.4: the candidates
    the AI draft is given)."""
    row = ws.query("SELECT title, text, role FROM documents WHERE doc_id=?", (doc_id,))
    if not row:
        raise KeyError(doc_id)
    title, text, role = row[0]["title"] or "", row[0]["text"] or "", row[0]["role"]
    stop = _stop()
    lines, repeated = _clean_lines(_body_lines(ws, doc_id, text), text)
    sents = _sentences(lines, text)
    # a term must come back to count as one of the theory's: more often in a book than in a few pages
    need = 1 if len(sents) < 60 else 2 if len(sents) < 400 else 3 if len(sents) < 2000 else 5

    # every run of one to four words that starts and ends with a content word, with the sentences that use it
    where: dict[str, list[int]] = {}
    for i, (a, z) in enumerate(sents):
        low = [w.lower() for w in re.findall(_W, text[a:z])]
        seen_here = set()
        for n in range(1, MAX_TERM_WORDS + 1):
            for j in range(len(low) - n + 1):
                g = low[j:j + n]
                if g[0] in stop or g[-1] in stop or len(g[0]) < 3 or len(g[-1]) < 3 or g[0] in _FUNCTION \
                        or g[-1] in _FUNCTION:
                    continue
                if any((w in stop or w in _FUNCTION) and w not in _INNER for w in g[1:-1]):
                    continue
                k = _norm(" ".join(g))
                if k in seen_here:
                    continue
                seen_here.add(k)
                where.setdefault(k, []).append(i)

    used_by: dict[str, list[int]] = {}

    def uses(term: str) -> list[int]:
        k = _norm(term)
        if k in where or len(term.split()) <= MAX_TERM_WORDS:
            return where.get(k, [])
        if k not in used_by:
            # a long heading ("shifting the burden to the intervenor"): looked for only in the sentences that use
            # the rarest of its words
            rx = _term_rx(term)
            near = min((where.get(_norm(w.lower()), []) for w in re.findall(_W, term)
                        if w.lower() not in stop and w.lower() not in _FUNCTION and len(w) >= 3), key=len, default=[])
            used_by[k] = [i for i in near if rx.search(text[sents[i][0]:sents[i][1]])]
        return used_by[k]

    def form_of(term: str) -> str | None:
        """The way the text writes a term most often (a capital that only starts a sentence does not count)."""
        rx = _term_rx(term)
        seen: Counter = Counter()
        for i in uses(term)[:200]:
            for m in rx.finditer(text[sents[i][0]:sents[i][1]]):
                f = " ".join(m.group(0).split())
                seen[f if f[1:] != f[1:].lower() else f.lower()] += 1
        return seen.most_common(1)[0][0] if seen else None

    def shown(term: str, k: str) -> str:
        f = form_of(term)
        t = f or term
        ws_ = t.split()
        if len(ws_) > 1 and all(w[:1].isupper() or w.lower() in stop for w in ws_) or t.isupper() and not f:
            # a heading's capitals: "Seeking the Wrong Goal" as running text writes it (an abbreviation keeps its own)
            t = " ".join(w if w.isupper() and 1 < len(w) <= 5 and not t.isupper() else w.lower() for w in ws_)
        return t[0].upper() + t[1:] if t[:1].islower() else t

    def inside(k: str, o: str) -> bool:
        """Whether the words of `k` stand together inside the longer term `o` ("feedback" in "feedback loop")."""
        a_, b_ = k.split(), o.split()
        return len(a_) < len(b_) and any([_norm(w) for w in b_[i:i + len(a_)]] == [_norm(w) for w in a_]
                                        for i in range(len(b_) - len(a_) + 1))

    found: dict[str, dict] = {}

    skip: frozenset[int] = frozenset()

    def add(term: str | None, how: str, span: tuple[int, int] | None = None) -> None:
        if not term:
            return
        k = _norm(term)
        if not k or k in found:
            return
        used = uses(term)
        if span is None:
            span = _best_definition(term, used, sents, text, skip)
        # a term the text defines keeps the form it is defined in ("Leverage points refer to …")
        found[k] = {"term": shown(term, k) if how in ("heading", "frequent") else term[0].upper() + term[1:], "how": how,
                    "ticked": how in ("glossary", "defined"), "count": len(used),
                    "definition": _quote(ws, doc_id, text, *span) if span else None}

    headings = ws.query("SELECT start, end, text FROM headings WHERE doc_id=? ORDER BY start", (doc_id,))
    # a sentence that is a heading is never a definition
    head_at = sorted((h["start"], h["end"]) for h in headings)
    is_heading: set[int] = set()
    hi = 0
    for i, (a, _z) in enumerate(sents):
        while hi < len(head_at) and head_at[hi][1] <= a:
            hi += 1
        if hi < len(head_at) and head_at[hi][0] <= a:
            is_heading.add(i)
    skip = frozenset(is_heading)
    # 1. the document's own glossary
    glossary = _glossary(lines, text, headings)
    for term, span in glossary:
        t = _clean_term(term, stop)
        if t and span[1] - span[0] <= 1200:
            add(t, "glossary", span)
    # the terms its headings name ("Stocks, Flows, and Dynamic Equilibrium": three of them), in the document's order.
    # A heading counts when prose follows it (a line of a table of contents, a chapter's number or a figure's label
    # has none), and a part of it when it is a term by itself: no number in it, no small word at either end.
    starts = [a for a, _z in sents]
    heading_terms: list[str] = []

    def heading_term(part: str) -> str | None:
        words = part.strip(" .,:;'\"’()").split()
        if words and words[0].lower() in ("a", "an", "the"):
            words = words[1:]
        low = [w.lower() for w in words]
        if not words or len(words) > MAX_HEADING_WORDS or low[0] in stop or low[0] in _NOT_SUBJECT or low[-1] in stop \
                or low[-1] in _NOT_SUBJECT or all(w in _STRUCTURE_KEYS or _norm(w) in _STRUCTURE_KEYS for w in low):
            return None
        t = " ".join(words)
        return t if len(t) >= 3 and re.fullmatch(rf"{_W}(?: {_W})*", t) else None

    def prose_after(n: int) -> bool:
        r = headings[n]
        until = headings[n + 1]["start"] if n + 1 < len(headings) else len(text)
        first = bisect.bisect_left(starts, r["end"])
        return any(len(text[a:z].split()) >= 12 or (len(text[a:z].split()) >= 6 and text[a:z].rstrip()[-1:] in ".!?”\"")
                   for a, z in sents[first:first + 6] if a < until)

    prose = [prose_after(n) for n in range(len(headings))]
    for n, r in enumerate(headings):
        raw = " ".join((r["text"] or text[r["start"]:r["end"]]).split())
        h = _NUMBERING.sub("", raw)
        if _line_key(raw) in repeated or _contents_like(raw) or re.search(r"\d|=", h) or _PANEL.match(h) \
                or h.rstrip().endswith("?"):
            continue
        if not prose[n]:
            # a chapter's title over its first section's has no prose of its own; a table of contents is a long run
            # of headings without any
            run = next((i for i in range(n, len(headings)) if prose[i]), len(headings)) - n
            back = n - next((i for i in range(n, -1, -1) if prose[i]), -1)
            if run + back - 1 > 4 or n + run >= len(headings):
                continue
        for piece in _SPLIT_DASH.split(h):
            parts = [x for x in _SPLIT_LIST.split(piece) if x]
            if len(parts) > 1:
                # a list of terms ("Stocks, Flows, and Dynamic Equilibrium"), not a phrase with "and" in it ("The
                # content and structure of the book"): every part short and a term by itself
                listed = [heading_term(x) for x in parts]
                if all(listed) and all(len(x.split()) <= 3 for x in listed):
                    heading_terms += listed
                continue
            t = heading_term(piece)
            if t:
                heading_terms.append(t)
    in_heading = {_norm(t) for t in heading_terms}
    # 2. defined in the text: a sentence that starts with the term and says what it is
    strong: dict[str, str] = {}
    weak: dict[str, list[str]] = {}
    for a, z in sents:
        s = text[a:z].strip()
        for n_rx, rx in enumerate(_DEFINES):
            m = rx.search(s)
            if not m:
                continue
            t = _subject(m.group(1), stop)
            if not t and n_rx == _CALL_AT:
                # "we call this a reinforcing loop because it grows": the words up to the first that joins
                ws_ = m.group(1).split()
                t = next((x for x in (_subject(" ".join(ws_[:n]), stop) for n in range(len(ws_) - 1, 0, -1)) if x), None)
            if t:
                if n_rx == _WEAK_AT:
                    weak.setdefault(_norm(t), []).append(t)
                else:
                    strong.setdefault(_norm(t), t)
            break
    def qualified(k: str) -> bool:
        """"Serious chronic heart failure" beside "chronic heart failure": the same term with a word before it."""
        return any(o != k and k.endswith(" " + o) and len(where.get(o, ())) > len(where.get(k, ()))
                   for o in list(strong) + list(weak))

    for k, t in strong.items():
        if len(where.get(k, ())) >= need and not qualified(k):
            add(t, "defined")
    for k, ts in weak.items():
        # "A tree is a system" names an example, not a concept: a single word counts as defined only when the text
        # says so twice or sets it as a heading; a phrase ("feedback loop") when it comes back often enough
        # (in a few pages every definition counts)
        if len(where.get(k, ())) >= need and (" " in k or k in in_heading or len(ts) >= 2 or need == 1) \
                and not (" " not in k and k in _GENERIC_KEYS and k not in in_heading) and not qualified(k):
            add(ts[0], "defined")
    named = [k for k, c in found.items() if c["how"] in ("glossary", "defined")]
    # 3. its headings
    for t in heading_terms:
        k = _norm(t)
        # not a piece of a term already there ("balancing feedback" beside "balancing feedback loop"), and only with
        # a sentence of the text that uses it
        if len(uses(t)) >= max(1, need) and not any(inside(k, o) for o in named):
            add(t, "heading")
            if k in found and found[k]["how"] == "heading" and not found[k]["definition"]:
                del found[k]
    # 4. frequent words and phrases: those the theory uses far more than the evidence does, a phrase before the words
    # it is made of ("feedback loop" beats "feedback" when it is nearly as frequent)
    ev, ev_total = _evidence_words(ws, doc_id) if len(sents) >= 60 else (Counter(), 0)
    total = sum(len(re.findall(_W, text[a:z])) for a, z in sents) or 1
    ranked = []
    for k, v in where.items():
        n = len(v)
        if n < max(3, need) or k in found or any(inside(k, o) for o in named):
            continue
        if " " not in k:
            if k in _GENERIC_KEYS or len(k) < 4:
                continue
            if ev_total >= 20000 and (n / total) < 3 * ((ev.get(k, 0) + 1) / ev_total):
                continue            # the evidence uses the word about as much: not the theory's own
        ranked.append((-n * (1 + 0.6 * k.count(" ")), k))
    # how often the most frequent phrase with a word in it comes
    in_phrase: dict[str, int] = {}
    for o, v in where.items():
        if " " in o and len(v) >= 3:
            for w in set(o.split()):
                if len(v) > in_phrase.get(w, 0):
                    in_phrase[w] = len(v)
    n_frequent = 0
    for _score, k in sorted(ranked):
        if n_frequent >= MAX_FREQUENT or len(found) >= limit:
            break
        n = len(where[k])
        if " " not in k and in_phrase.get(k, 0) >= 0.6 * n:
            continue
        if any(o != k and (o in k.split() or k in o.split() or o in k or k in o) and found[o]["how"] == "frequent"
               for o in found):
            continue                # one of "practice theory" and "practice theories", not both
        t = form_of(k) or k
        if _clean_term(t, stop):
            before = len(found)
            add(t, "frequent")
            n_frequent += len(found) - before
    if glossary:
        # the document says itself which its concepts are: only those are ticked, the rest is offered
        for c in found.values():
            c["ticked"] = c["how"] == "glossary"
    elif need > 1 and sum(1 for c in found.values() if c["how"] == "defined") < 3:
        # a long text that defines one or two things outright argues instead of defining, and what it does define is
        # as likely its case as its theory ("Chronic heart failure is a …"): nothing is ticked for the person
        for c in found.values():
            c["ticked"] = False
    order = {"glossary": 0, "defined": 1, "heading": 2, "frequent": 3}
    # among its headings a phrase ("policy resistance") before a single word ("behavior")
    picked = sorted(found.values(), key=lambda c: (order[c["how"]], c["how"] == "heading" and " " not in c["term"],
                                                   -c["count"], c["term"].lower()))[:limit]
    out = [{**c, "code": _draft_code(c["term"], c["definition"], title, doc_id),
            "suggested": suggest_examples(ws, c["term"], exclude_doc=doc_id) if with_examples else []} for c in picked]
    return {"doc_id": doc_id, "title": title, "role": role, "concepts": out}


def _draft_code(term: str, d: dict | None, title: str, doc_id: str = "") -> dict:
    """A draft code: the term as its name, its definition quoted with the document and page as its description.
    `source_doc` (0.19: a codebook may start from several theory documents) says which theory it comes from, so
    `codebooks.create` can group the codes by theory; it is not written to the codebook itself."""
    page = f", p. {d['page']}" if d and d.get("page") else ""
    desc = f"“{d['quote']}” ({title}{page})" if d else f"A concept of {title}."
    return {"code": term[:40], "description": desc[:2000], "described": bool(d), "group": "",
            "keywords": [term.lower()], "include": "", "exclude": "", "examples": [], "source_doc": doc_id}


def suggest_examples(ws: Workspace, term: str, k: int = MAX_EXAMPLES, exclude_doc: str | None = None) -> list[dict]:
    """Up to `k` sentences of the evidence documents that use the term (its words, by keyword), to offer as examples:
    never from a theory document. Each {"quote", "doc_id", "title", "page", "start", "end", "project"}."""
    from .docrole import not_evidence_docs
    from .search import rank_passages

    # never from a theory or (N3) a working document, nor from the theory itself (review 16)
    theory = not_evidence_docs(ws._conn()) | ({exclude_doc} if exclude_doc else set())
    words = [w.lower() for w in re.findall(_W, term)]
    if not words:
        return []
    try:
        found = rank_passages(ws, term, words, k=k * 3, per_doc=1, require_terms=True, evidence_only=True)
    except Exception:  # noqa: BLE001 - no index yet: nothing to offer
        return []
    out = []
    rx = re.compile(r"\b" + r"\W+".join(re.escape(w) for w in words), re.I)
    for p in found:
        if p["doc_id"] in theory:
            continue
        r = ws.query("SELECT p.page, p.start, p.text, d.title FROM passages p JOIN documents d ON d.doc_id=p.doc_id "
                     "WHERE p.passage_id=?", (p["passage_id"],))
        if not r:
            continue
        t = r[0]["text"]
        m = rx.search(t)
        if not m:
            continue
        a, z = next(((a, z) for a, z in split_sentences(t) if a <= m.start() < z), (0, len(t)))
        out.append({"quote": " ".join(t[a:z].split())[:400], "doc_id": p["doc_id"], "title": r[0]["title"],
                    "page": r[0]["page"], "start": r[0]["start"] + a, "end": r[0]["start"] + z,
                    "project": ws.project_uid()})
        if len(out) >= k:
            break
    return out


def keep_evidence_examples(ws: Workspace, codes: list[dict], sources: Iterable[str] = ()) -> list[dict]:
    """The codes a person kept, with any example from a theory document taken out (the rule of K2: examples come only
    from the evidence). `sources`: the documents the codes were drafted from, left out too even when one is not marked
    as theory (with several theories, one theory's sentence must not become an example of another's concept)."""
    from .docrole import not_evidence_docs

    theory = not_evidence_docs(ws._conn()) | {str(d) for d in sources if d}   # N3: nor from a working document
    out = []
    for c in codes:
        if not isinstance(c, dict):
            continue
        ex = [e for e in (c.get("examples") or []) if isinstance(e, dict) and e.get("doc_id") not in theory]
        out.append({**c, "examples": ex})
    return out



# ---------------------------------------------------------------------------------------------
# 0.18.4 (K2 part 2, Level 2 or 3): the optional AI draft
# ---------------------------------------------------------------------------------------------
AI_KIND = "theory_codes"
AI_MAX_CANDIDATES = 30   # the Level-0 candidates the AI is given as hints
AI_MAX_CHARS = 22000     # one part of the document: what the AI reads at once (with the answer and a reasoning
#                          model's room it fits a context length of 16,384 tokens, see `_part_chars`)
AI_MAX_PARTS = 60        # the parts of one document it reads (about 1.3 million characters; of a longer one, the parts
#                          that use the candidates most)
AI_PART_CONCEPTS = 12    # the concepts it may draft from one part
AI_MAX_CONCEPTS = 40     # and the concepts offered from the whole document

NO_AI = "This document is marked No AI, so no AI drafts its concepts."
WITHDRAWN = ("The request was taken back before the AI answered (the document's AI setting changed, or a draft "
             "was stopped). Nothing was drafted: try again.")
NO_LOCAL = ("Only a local AI may read this document, and no local AI is chosen (Settings, AI: the local model for "
            "documents kept on this computer).")


def _h(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def _level(ws: Workspace, doc_id: str) -> str:
    from . import access

    return access.levels(ws, [doc_id]).get(doc_id) or access.default(ws)


def ai_offer(ws: Workspace, doc_id: str, settings: dict | None = None) -> dict:
    """Whether the AI may draft this document's concepts, and who would read it: {"offered", "why" (one line when
    not), "reader": "claude" | "local" | "main" | None, "parts" (when offered: the parts it reads the document in)}. The document's own AI setting decides, as everywhere: Claude
    may read it (the main AI), only a local AI (the local model, or the main one when it runs on this computer), or no
    AI (not offered)."""
    from . import home

    if not ws.scalar("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)):
        raise KeyError(doc_id)
    s = settings if settings is not None else home.load_settings()
    lv = _level(ws, doc_id)
    if lv == "none":
        return {"offered": False, "why": NO_AI, "reader": None, "level": lv}
    from .routing import OFF_COMPUTER

    claude = (s.get("backend") or "auto") in OFF_COMPUTER
    # the parts the AI would read the document in (theory-codes-v2: the whole document, a part at a time)
    parts = len(_ai_parts(ws, doc_id, []))
    if lv == "local":
        if home.main_reads_local(s) or home.restricted_choice(s):
            return {"offered": True, "why": None, "reader": "local", "level": lv, "parts": parts}
        return {"offered": False, "why": NO_LOCAL, "reader": None, "level": lv}
    return {"offered": True, "why": None, "reader": "claude" if claude else "main", "level": lv, "parts": parts}


AI_MIN_CHARS = 3000      # a part smaller than this is not worth a request: the reader's context length is too small
_PASSAGE_HEAD = 24       # "P12 (page 345)" and the blank lines around a passage, in the prompt
TOO_SMALL = ("The context length of the model on this computer ({n:,} tokens) is too small to read a theory document "
             "a part at a time. Set it to automatic in Settings, or to 16,384 or more.")


def _part_chars(be, settings: dict) -> int:
    """The characters of the document one part may hold for this reader. Claude reads AI_MAX_CHARS. A model on this
    computer has a context length (`num_ctx`): set to automatic, it is raised here to hold a whole part (the
    app sizes it for a check's few excerpts, and a part of a book is longer); set by the person, the part is made to
    fit it. Raises ValueError when not even AI_MIN_CHARS fit."""
    n = getattr(be, "num_ctx", None)
    if not n:
        return AI_MAX_CHARS
    from . import home, prompts
    from .llm import CONTEXT_MARGIN, OUTPUT_CAP, THINK_ALLOWANCE, estimate_tokens

    if str(settings.get("num_ctx", "auto")).lower() == "auto":
        be.num_ctx = max(int(n), home.context_plan(settings, (AI_KIND,))["num_ctx"])
    think, only, budget = home.thinking(settings)
    reasons = think is not False and (only is None or AI_KIND in only)   # unknown ("default") counts as reasoning
    room = int(be.num_ctx) - estimate_tokens(prompts.system_prompt(AI_KIND)) - OUTPUT_CAP.get(AI_KIND, 2000) \
        - ((2 * budget + 64 if budget else THINK_ALLOWANCE) if reasons else 0) - CONTEXT_MARGIN
    # tokens to characters as `estimate_tokens` counts them, less the title, the candidates and a retry's problems
    chars = min(AI_MAX_CHARS, int(room * 3.5) - (prompt_size(0, 0) - AI_MAX_CHARS) - 1600)
    if chars < AI_MIN_CHARS:
        raise ValueError(TOO_SMALL.format(n=int(be.num_ctx)))
    return chars


def _ai_parts(ws: Workspace, doc_id: str, terms: list[str], max_chars: int = AI_MAX_CHARS) -> list[list[dict]]:
    """The whole document as the AI reads it: its body passages in order, in parts of at most `max_chars` each with
    their headers (a passage is never cut), without the passages that hold no prose (running heads, a table of
    contents, equations).
    Each part: [{"n", "passage_id", "page", "text"}], numbered from 1. A document of more than AI_MAX_PARTS parts:
    the parts that use the candidate concepts most."""
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (doc_id,)) or ""
    rows = ws.query("SELECT passage_id, start, end, page, text FROM passages WHERE doc_id=? AND section='body' "
                    "ORDER BY start", (doc_id,)) or \
        ws.query("SELECT passage_id, start, end, page, text FROM passages WHERE doc_id=? ORDER BY start", (doc_id,))
    if not rows:
        return []
    lines = []
    for r in rows:
        at = r["start"]
        for line in re.split(r"(\n+)", text[r["start"]:r["end"]]):
            if line.strip() and not line.startswith("\n"):
                lines.append((at, at + len(line)))
            at += len(line)
    kept, _rep = _clean_lines(lines, text)
    starts = sorted(a for a, _z in kept)
    def prose(r) -> bool:
        i = bisect.bisect_left(starts, r["start"])
        return i < len(starts) and starts[i] < r["end"]

    parts: list[list] = [[]]
    size = 0
    for r in rows:
        if kept and not prose(r):
            continue
        n = len(r["text"] or "") + _PASSAGE_HEAD
        if parts[-1] and size + n > max_chars:
            parts.append([])
            size = 0
        parts[-1].append(r)
        size += n
    parts = [p for p in parts if p]
    if len(parts) > AI_MAX_PARTS:
        rxs = [_term_rx(t) for t in terms if re.findall(_W, t)]
        score = [sum(1 for rx in rxs if any(rx.search(r["text"] or "") for r in p)) for p in parts]
        keep = sorted(sorted(range(len(parts)), key=lambda i: (-score[i], i))[:AI_MAX_PARTS])
        parts = [parts[i] for i in keep]
    return [[{"n": k, "passage_id": r["passage_id"], "page": r["page"], "text": r["text"]}
             for k, r in enumerate(p, 1)] for p in parts]


def ai_payloads(ws: Workspace, doc_id: str, max_chars: int = AI_MAX_CHARS, found: dict | None = None) -> list[dict]:
    """What the AI is given, one payload for each part of the document: its title, its Level-0 candidates (names
    only, as hints), the part's number and the part's passages. `max_chars`: what one part may hold (`_part_chars`);
    `found`: the document's candidates when the caller has them already."""
    c = found or candidates(ws, doc_id, with_examples=False)
    terms = [x["term"] for x in c["concepts"]][:AI_MAX_CANDIDATES]
    parts = _ai_parts(ws, doc_id, terms, max_chars)
    return [{"doc_id": doc_id, "title": c["title"], "candidates": terms, "part": i, "parts": len(parts),
             "passages": p} for i, p in enumerate(parts, 1)]


def ai_payload(ws: Workspace, doc_id: str) -> dict:
    """The first part's payload (a short document has one part)."""
    got = ai_payloads(ws, doc_id)
    return got[0] if got else {"doc_id": doc_id, "title": "", "candidates": [], "part": 1, "parts": 0, "passages": []}


def make_ai_tasks(ws: Workspace, doc_id: str, model: str, max_chars: int = AI_MAX_CHARS,
                  found: dict | None = None) -> list[str]:
    """The draft's tasks, one for each part of the document (made once per input: the same text, candidates, prompt
    version and model give the same task, so a draft asked again reuses its answers). Returns their ids, in the
    document's order."""
    from . import prompts
    from .tasks import replace_task

    payloads = ai_payloads(ws, doc_id, max_chars, found)
    if not payloads:
        raise ValueError("This document has no text to read: read it again first.")
    tids = []
    with ws.connect() as cx:
        for payload in payloads:
            tid = f"{AI_KIND}:{doc_id}:" + _h(json.dumps(payload, sort_keys=True, ensure_ascii=False),
                                               prompts.VERSIONS.get(AI_KIND) or "", model or "")[:12]
            replace_task(cx, tid, AI_KIND, model, payload)
            tids.append(tid)
    return tids


def make_ai_task(ws: Workspace, doc_id: str, model: str) -> str:
    """The task of the document's first part (a short document has one part)."""
    return make_ai_tasks(ws, doc_id, model)[0]


def store_ai_draft(cx, t, payload: dict, obj: dict, model: str) -> tuple[bool, list[str]]:
    """Check the AI's draft of one part (theory-codes-v2): every definition a quote of at least three whole words, found in the
    passage it names. The answer itself is kept with the task (`results`), and `ai_drafts` reads it."""
    from .schema import TheoryCodesOut
    from .textutil import find_quote, grade_quote_problem, partial_word_hint

    out = TheoryCodesOut.model_validate(obj)
    ps = payload.get("passages") or []
    errors = []
    for i, c in enumerate(out.concepts):
        ev = c.definition
        if ev.passage > len(ps):
            errors.append(f"concepts[{i}] ({c.name}): there is no passage P{ev.passage}")
            continue
        short = grade_quote_problem(ev.quote)
        if short or _words(ev.quote) < MIN_DEFINITION_WORDS:  # a definition needs words: 15 characters are not enough
            errors.append(f"concepts[{i}] ({c.name}): the quote {' '.join(ev.quote.split())[:80]!r} is too short to "
                          f"define the concept: quote at least {MIN_DEFINITION_WORDS} whole words, copied exactly")
            continue
        if _norm(ev.quote) == _norm(c.name):
            errors.append(f"concepts[{i}] ({c.name}): the quote only repeats the concept's name: quote the sentence "
                          "or part of it that says what the concept is")
            continue
        text = ps[ev.passage - 1]["text"]
        if not find_quote(text, ev.quote):
            errors.append(f"concepts[{i}] ({c.name}): quote not found in passage P{ev.passage}: {ev.quote[:80]!r}"
                          + partial_word_hint(text, ev.quote) + ". Copy it character for character, or quote a "
                          "shorter contiguous piece of it.")
    return not errors, errors


def _part_concepts(ws: Workspace, task_id: str) -> list[dict]:
    """The concepts of one part's accepted answer, in the AI's order: [{"name", "reason", "definition": {"quote",
    "start", "end", "page"}, "model", "part"}], each quote found again in its passage."""
    from .schema import TheoryCodesOut
    from .tasks import parse_json
    from .textutil import find_quote

    t = ws.query("SELECT payload_json, status FROM tasks WHERE task_id=?", (task_id,))
    if not t or t[0]["status"] != "done":
        return []
    r = ws.query("SELECT raw_json, model FROM results WHERE task_id=? AND valid=1 ORDER BY attempt DESC LIMIT 1",
                 (task_id,))
    if not r:
        return []
    payload = json.loads(t[0]["payload_json"])
    doc_id = payload["doc_id"]
    out_ = TheoryCodesOut.model_validate(parse_json(r[0]["raw_json"]))
    starts = {p["passage_id"]: s for p in payload["passages"]
              for s in [ws.scalar("SELECT start FROM passages WHERE passage_id=?", (p["passage_id"],))]}
    out = []
    for c in out_.concepts:
        if not _norm(c.name) or c.definition.passage > len(payload["passages"]):
            continue
        p = payload["passages"][c.definition.passage - 1]
        hit = find_quote(p["text"], c.definition.quote)
        if not hit:
            continue
        base = starts.get(p["passage_id"])
        a, z = (base + hit[0], base + hit[1]) if base is not None else (None, None)
        d = {"quote": " ".join(p["text"][hit[0]:hit[1]].split()), "start": a, "end": z,
             "page": (_page(ws, doc_id, a) if a is not None else None) or p.get("page")}
        out.append({"name": c.name, "reason": c.reason, "definition": d, "model": r[0]["model"],
                    "part": payload.get("part") or 1})
    return out


def ai_drafts(ws: Workspace, task_ids: str | list[str], skip: set[str] | None = None) -> list[dict]:
    """The concepts of a draft's accepted answers (one task for each part of the document), put together and shaped as
    `candidates` shapes them (each "how": "ai", "ai": True, with its "reason"), without those whose normalised name is
    in `skip`. A concept drafted from several parts is offered once, with the quote that best says what it means; the
    concepts come the most central first (drafted from the most parts, high in each part's list, used most in the
    document), at most AI_MAX_CONCEPTS. Their examples are offered from the evidence documents only
    (`suggest_examples`), as for every candidate."""
    tids = [task_ids] if isinstance(task_ids, str) else list(task_ids)
    by: dict[str, list[dict]] = {}
    rank: dict[str, float] = {}
    doc_id = title = None
    for tid in tids:
        got = _part_concepts(ws, tid)
        if got and doc_id is None:
            payload = json.loads(ws.scalar("SELECT payload_json FROM tasks WHERE task_id=?", (tid,)))
            doc_id, title = payload["doc_id"], payload.get("title") or ""
        seen_here = set()
        for i, c in enumerate(got):
            k = _norm(c["name"])
            if k in (skip or ()) or k in seen_here:
                continue
            seen_here.add(k)
            by.setdefault(k, []).append(c)
            rank[k] = rank.get(k, 0.0) + 3 + 2 / (1 + i)       # a part that drafts it, and how early in its list
    if not by:
        return []
    text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (doc_id,)) or ""
    out = []
    # (how often the text uses a concept only settles the order among those the parts rank near the top)
    for k in sorted(by, key=lambda k: -rank[k])[:3 * AI_MAX_CONCEPTS]:
        cs = by[k]
        rx = _term_rx(cs[0]["name"])
        uses = len(rx.findall(text))

        def says(c: dict, rx=rx) -> int:
            q = c["definition"]["quote"]
            m = rx.search(q)
            return _defining_score(q, m) if m else 0

        best = max(cs, key=lambda c: (says(c), -c["part"]))
        name = Counter(c["name"] for c in cs).most_common(1)[0][0]
        term = name[0].upper() + name[1:] if name[:1].islower() else name
        out.append((-(rank[k] + math.log2(1 + uses)), best["part"],
                    {"term": term, "how": "ai", "ai": True, "ticked": False, "reason": best["reason"], "count": uses,
                     "parts": sorted({c["part"] for c in cs}), "definition": best["definition"],
                     "code": _draft_code(term, best["definition"], title, doc_id), "model": best["model"]}))
    out.sort(key=lambda x: x[:2])
    picked = [c for _s, _p, c in out[:AI_MAX_CONCEPTS]]
    for c in picked:
        c["suggested"] = suggest_examples(ws, c["term"], exclude_doc=doc_id)
    return picked


def draft_with_ai(ws: Workspace, doc_id: str, backend, model: str, progress: Callable | None = None,
                  should_stop: Callable[[], bool] | None = None, readers=None) -> dict:
    """The AI drafts the concepts of a theory document: it reads the whole document, one task for each part of it (see
    the module's notes), and the parts' drafts are put together. The reader is the one the document's AI setting
    allows (`access.Readers`: Claude, or the local model for a document only a local AI may read); a document marked
    No AI is never sent. Written to the research log. Returns {"doc_id", "title", "task_id" (the first part's),
    "task_ids", "parts", "parts_read", "ok" (a part at least was read), "stopped", "problems", "reused", "model",
    "concepts": [drafts, unticked, without the terms the document defines itself]}."""
    from . import access, researchlog
    from . import runs as runs_mod
    from . import tasks

    title = ws.scalar("SELECT title FROM documents WHERE doc_id=?", (doc_id,))
    if title is None:
        raise KeyError(doc_id)
    lv = _level(ws, doc_id)
    if lv == "none":
        raise ValueError(NO_AI)
    readers = readers or access.Readers(backend, model, should_stop=should_stop)
    got = readers.for_level(lv)
    if got is None:
        raise ValueError(NO_LOCAL if lv == "local" else NO_AI)
    be, call = got
    found = candidates(ws, doc_id, with_examples=False)      # once for the draft: the hints, and what is its own
    tids = make_ai_tasks(ws, doc_id, call, _part_chars(be, readers.settings()), found)
    n = len(tids)
    if progress:
        progress(0, n)
    with ws.connect() as cx:  # worked out again as the text is about to leave (an add-on's floor may hold it back)
        for tid in tids:
            now_lv = access.recheck(cx, tid)
            if now_lv is None or now_lv not in access.backend_levels(be):
                raise ValueError(NO_AI if now_lv == "none" else "This document may not be sent to this AI.")
        if getattr(be, "name", "") == "claude_code":
            tasks.mark_queued(cx, tids)        # every part waits in the queue at once: the helpers share them
    before = {tid: ws.scalar("SELECT status FROM tasks WHERE task_id=?", (tid,)) for tid in tids}
    rid = runs_mod.start(ws, AI_KIND, doc_id, be, call, n)
    read: list[str] = []
    problems: list[str] = []
    used, reused, halted = call, True, None
    try:
        for i, tid in enumerate(tids):
            if should_stop and should_stop():
                halted = "stopped"
                break
            ok, errs = tasks.run_one(ws, tid, be, call)
            if progress:
                progress(i + 1, n)
            last = ws.query("SELECT model, route FROM results WHERE task_id=? AND valid=1 ORDER BY attempt DESC LIMIT 1",
                            (tid,))
            if ok:
                read.append(tid)
                used = last[0]["model"] if last else used
                reused = reused and (before[tid] == "done" or bool(last and "kept answer" in (last[0]["route"] or "")))
            elif ws.scalar("SELECT status FROM tasks WHERE task_id=?", (tid,)) != "failed":
                # stopped, or taken back from the queue. Only a stop the person asked for is quiet; a task taken back
                # for another reason (another draft's job stopped, or the document's AI setting changed while it
                # waited) says so.
                halted = "stopped" if should_stop and should_stop() else "withdrawn"
                problems = errs
                break
            else:
                problems += [f"part {i + 1}: {e}" for e in errs[:2]]
    finally:
        runs_mod.finish(ws, rid, len(read))
        if len(read) < n and (halted == "stopped" or (halted is None and should_stop and should_stop())):
            # stopped between two parts, or while one waited (Claude Code's wait raises): the parts not read leave
            # the queue with the draft, so no helper goes on answering them (the parts read are kept)
            from . import taskqueue

            taskqueue.withdraw(ws, task_ids=[t for t in tids if t not in read])
    if halted:
        return {"doc_id": doc_id, "title": title, "task_id": tids[0], "task_ids": tids, "parts": n,
                "parts_read": len(read), "ok": False, "stopped": halted == "stopped",
                "withdrawn": halted == "withdrawn", "why": None if halted == "stopped" else WITHDRAWN,
                "problems": problems[:5], "reused": False, "model": used, "concepts": []}
    ok = bool(read)
    reused = ok and reused
    # the terms the document defines itself stay as they are; a heading or a frequent word the AI drafts too is
    # offered with the AI's definition (the page replaces its row)
    own = {_norm(c["term"]) for c in found["concepts"] if c["how"] in ("glossary", "defined")}
    concepts = ai_drafts(ws, read, own) if ok else []
    in_parts = f" in {n} parts" if n > 1 else ""
    missed = f" ({n - len(read)} of the {n} parts could not be read: the AI’s quotes were not found in them)" \
        if ok and len(read) < n else ""
    with ws.connect() as cx:
        if ok:
            text = (f"The AI ({used}) read the theory document {researchlog.quoted(title, 80)}{in_parts} and drafted "
                    f"{len(concepts)} concept{'s' if len(concepts) != 1 else ''} for a codebook, each with its "
                    f"definition quoted from it" + (" (the answers kept from the same request before)" if reused else "")
                    + missed + ". They are drafts, offered unticked: none is a code until you tick it.")
        else:
            text = (f"The AI ({used}) could not draft the concepts of the theory document "
                    f"{researchlog.quoted(title, 80)}: its quotes were not found in the text.")
        researchlog.record(cx, "codebook-drafted", text, "document", doc_id, title,
                           data={"task_id": tids[0], "task_ids": tids, "parts": n, "parts_read": len(read),
                                 "model": used, "concepts": [c["term"] for c in concepts], "reused": reused, "ok": ok})
    return {"doc_id": doc_id, "title": title, "task_id": tids[0], "task_ids": tids, "parts": n,
            "parts_read": len(read), "ok": ok, "stopped": False, "problems": problems[:5], "reused": reused,
            "model": used, "concepts": concepts}


def demo_answer(payload: dict) -> dict:
    """The offline demo's draft: each candidate the passages use, with the first sentence that uses it (no reading)."""
    out = []
    for term in payload.get("candidates") or []:
        rx = re.compile(r"\b" + re.escape(term), re.I)
        for p in payload["passages"]:
            m = rx.search(p["text"])
            if not m:
                continue
            a, z = next(((a, z) for a, z in split_sentences(p["text"]) if a <= m.start() < z), (0, len(p["text"])))
            q = " ".join(p["text"][a:z].split())
            if len(q.split()) >= 3 and len(q) <= 600:
                out.append({"name": " ".join(term.split()[:6]), "definition": {"passage": p["n"], "quote": q},
                            "reason": "Offline demo: a candidate the passages use, not read."})
            break
        if len(out) >= 10:
            break
    return {"concepts": out, "note": "Offline demo: the candidates found without AI, with a sentence that uses each."}


def prompt_size(k: int, max_chars: int) -> int:
    """The longest prompt of a draft, in characters (home.prompt_tokens)."""
    return 1800 + AI_MAX_CHARS + AI_MAX_CANDIDATES * 40
