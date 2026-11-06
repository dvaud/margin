"""Skim one document (Margin): a one-page report on a single document, made on this computer without AI (Level 0).

For the times a publication is only to be skimmed: what it is (pages, words, reading time), its abstract, the
sections and how long each is, the sentences that carry most of its key terms, what it sets out to do and what it says
it found, the statements about the world it makes with and without a citation, the works it cites most, and the codes
it addresses. Nothing here needs the other documents of the project, so it works in a quick look (a project of one
document) as well as on any document of a larger project.

Where a test of the other pages compares documents, a single-document version is used: key terms are weighed by how
far a term runs through the document when there is no other document to contrast it with (`terms.key_terms`), and the
author's own aims and findings, which "Check a draft" leaves out on purpose, are what a skim looks for first.
"""
from __future__ import annotations

import bisect
import math
import re
from collections import defaultdict

from . import citations, drafts, terms
from .references import opens_with_pronoun
from .store import Workspace
from .textutil import find_dois, split_sentences

READ_WPM = 230          # words a minute, for the reading time
KEY_SENTENCES = 6
MAX_LIST = 60           # the most claims listed (the counts cover them all)
MAX_OWN = 8             # aims, and findings
MAX_SECTIONS = 40
MAX_CITED = 10
SENT_WORDS = (12, 60)   # a key sentence's length in words

_ABSTRACT_HEAD = re.compile(r"^\W*(?:abstract|summary|executive summary|zusammenfassung|résumé|resumen|"
                            r"összefoglal[óá]s?|kivonat)\W*$", re.I)
_ABSTRACT_INLINE = re.compile(r"(?im)^[ \t]*(abstract|summary)\b[ \t]*[:.—–-]?[ \t]*")
_ABSTRACT_END = re.compile(r"(?im)^[ \t]*(?:key ?words|index terms|jel(?: classification)?|(?:1\.?|i\.)?[ \t]*"
                           r"introduction|highlights)\b")
# the sections where a paper reports its own data and results: a number there is its evidence, not a claim to source
_OWN_SECTIONS = re.compile(r"\b(?:abstract|summary|highlights|results?|findings|data|methods?|methodology|materials|"
                           r"analysis|estimation|empirical|experiments?|case stud(?:y|ies)|sample)\b", re.I)
_LEAD_SECTIONS = re.compile(r"\b(?:introduction|conclu\w*|discussion|summary|results|findings|implications)\b", re.I)

_OWN = r"(?:we|our (?:study|paper|article|analysis|research|work|results|findings|data|model|estimates)|" \
       r"this (?:study|paper|article|analysis|research|work|report|chapter|thesis|review)|" \
       r"the (?:present|current) (?:study|paper|article|analysis|research|work)|here,? we|in this (?:study|paper|" \
       r"article|analysis|research|work|report|chapter|thesis|review),? we)"
_AIM = re.compile(
    rf"\b{_OWN}\b[^.;]{{0,80}}?\b(?:aims?|seeks?|sets? out|intends?|asks?|investigat(?:e|es|ed)|examin(?:e|es|ed)|"
    r"explor(?:e|es|ed)|analy[sz](?:e|es|ed)|address(?:es|ed)?|stud(?:y|ies|ied)|assess(?:es|ed)?|evaluat(?:e|es|ed)|"
    r"propos(?:e|es|ed)|develop(?:s|ed)?|introduc(?:e|es|ed)|focus(?:es|ed)? on|consider(?:s|ed)?)\b|"
    r"\b(?:the )?(?:aim|purpose|goal|objective)s? of (?:this|the present|our)\b|\bresearch questions?\b|"
    r"\bwe ask (?:whether|how|why|what)\b", re.I)
_FINDING = re.compile(
    rf"\b(?:{_OWN}|the (?:results|findings|analysis|estimates|data)|results|findings)\b[^.;]{{0,80}}?\b(?:find|finds|"
    r"found|show|shows|showed|shown|demonstrat(?:e|es|ed)|suggest(?:s|ed)?|indicat(?:e|es|ed)|reveal(?:s|ed)?|"
    r"conclud(?:e|es|ed)|observ(?:e|es|ed)|confirm(?:s|ed)?|identif(?:y|ies|ied)|document(?:s|ed)?|"
    r"provid(?:e|es|ed) evidence|highlight(?:s|ed)?|establish(?:es|ed)?|point(?:s|ed)? to)\b", re.I)
# "In conclusion, …" says it is a finding; "Overall, …" only in a conclusion or discussion
_CONCLUDING = re.compile(r"^\W*(?:in conclusion|to conclude|to sum up|taken together)\b,?", re.I)
_SUMMING = re.compile(r"^\W*(?:overall|in sum|in summary|in short|altogether)\b,", re.I)
_CLOSING_SECTIONS = re.compile(r"\b(?:conclu\w*|discussion|summary|synthesis|key (?:findings|messages))\b", re.I)
_FUTURE = re.compile(r"\b(?:will|would|aims?|seeks?|sets? out|intend|purpose|objective|research questions?|we ask|"
                     r"in (?:section|chapter) \d|the (?:next|following) section)\b", re.I)
_LEADERS = re.compile(r"(?:\.\s?){4,}|…{2,}|_{4,}")
_CAPTION = re.compile(r"^\W*(?:figure|fig\.|table|box|chart|map|annex|appendix)\s+[\dA-Z]+(?:[.\-]\d+)*\b", re.I)
_CAPTION_IN = re.compile(r"\b(?:FIGURE|TABLE|BOX)\s+\d")
_SHOUT_LEAD = re.compile(r"^\W*(?:[A-Z][A-Z0-9&'’.-]+\s+){3,}")
_FOOTNOTE_LEAD = re.compile(r"\d{1,3}\s+(?=[A-Z][a-z])")
_NOT_AUTHORS = re.compile(r"^(?:USD|EUR|GBP|US\$|CO2|GW|MW|kW|TWh|GWh|MWh|kWh|Mt|Gt|GDP|PPP|PES|NDC)s?$", re.I)
_URL = re.compile(r"https?://|www\.|\bdoi\.org/|\bdoi:\s*10\.", re.I)
_SURNAME_NOISE = re.compile(r"\bet al\.?|[.,'’]", re.I)


# ------------------------------------------------------------------------------------------------------------------
# the document's text: sentences that do not run across a heading or a paragraph
# ------------------------------------------------------------------------------------------------------------------
def _flatten(text: str, breaks: set[int]) -> str:
    """The text with a line break exactly where a paragraph or a heading begins or ends (`breaks`, from the layout
    the document was read with) and nowhere else, at the same length so offsets stay: a PDF's lines are broken where
    the page was full, not where a sentence ends, and a text file is stored with its breaks as spaces."""
    chars = list(text)
    for i, c in enumerate(chars):
        if c == "\n" and i not in breaks and not ((i > 0 and text[i - 1] == "\n")
                                                   or (i + 1 < len(text) and text[i + 1] == "\n")):
            chars[i] = " "
    for i in breaks:
        if 0 <= i < len(chars) and chars[i] in " \t":
            chars[i] = "\n"
    return "".join(chars)


def _sentences(flat: str, a: int, b: int) -> list[tuple[int, int]]:
    out = []
    for m in re.finditer(r"[^\n]+", flat[a:b]):
        out.extend(split_sentences(m.group(0), a + m.start()))
    return out


def _junk(s: str) -> bool:
    """A line of a contents page, a list of figures, a table or a running head rather than a sentence."""
    letters = [c for c in s if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) > 0.5 * len(letters):
        return True                                            # SHOUTED headings and running heads
    if _LEADERS.search(s) or _CAPTION.match(s) or _CAPTION_IN.search(s) or " | " in s or _SHOUT_LEAD.match(s):
        return True                                            # a caption, or a running head glued to the text
    toks = s.split()
    return len(toks) >= 6 and sum(bool(re.fullmatch(r"[\d.,%–-]+", t)) for t in toks) > 0.3 * len(toks)


def _text_sentences(d: "_Doc") -> list[tuple[int, int]]:
    out = []
    for a, b in _sentences(d.flat, 0, d.body_end):
        m = _FOOTNOTE_LEAD.match(d.flat, a, b)
        if m:
            a = m.end()                                        # "93 Furthermore, …": a footnote's number
        if b - a > 0 and d.in_text(a, b) and not _junk(d.flat[a:b]):
            out.append((a, b))
    return out


def _show(text: str, a: int, b: int) -> str:
    s = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text[a:b])  # a word broken at the end of a line
    return " ".join(s.split())


def _words(s: str) -> int:
    return len(re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", s))


class _Doc:
    """One document as the skim reads it: text, flattened text, pages, headings, where the reference list starts."""

    def __init__(self, ws: Workspace, doc_id: str):
        rows = ws.query("SELECT doc_id, title, path, kind, n_pages, doi, text FROM documents WHERE doc_id=?", (doc_id,))
        if not rows:
            raise KeyError(doc_id)
        d = rows[0]
        self.doc_id, self.title, self.kind, self.n_pages, self.doi = doc_id, d["title"], d["kind"], d["n_pages"], d["doi"]
        self.file = re.sub(r".*[/\\]", "", d["path"] or "")
        self.text = d["text"] or ""
        self.page_starts = [r["start"] for r in ws.query("SELECT start FROM pages WHERE doc_id=? ORDER BY page", (doc_id,))]
        self.heads = [dict(r) for r in ws.query("SELECT start, end, text FROM headings WHERE doc_id=? ORDER BY start",
                                                (doc_id,))]
        breaks: set[int] = set()
        for h in self.heads:
            breaks.update({h["start"] - 1, h["end"]})
        for r in ws.query("SELECT start FROM paragraphs WHERE doc_id=?", (doc_id,)):
            breaks.add(r["start"] - 1)
        breaks.update(s - 1 for s in self.page_starts)
        self.flat = _flatten(self.text, breaks)
        self.refs_at = citations.references_start(self.flat)
        # the passages the reading marked as not text (a reference list without a heading, unreadable lines)
        other = [(r["start"], r["end"], r["section"]) for r in ws.query(
            "SELECT start, end, section FROM passages WHERE doc_id=? AND section != 'body' ORDER BY start", (doc_id,))]
        if self.refs_at is None:
            late = [a for a, _b, sec in other if sec == "references" and a >= len(self.text) * 0.3]
            self.refs_at = late[0] if late else None
        self._other = [(a, b) for a, b, _sec in other]
        self._other_starts = [a for a, _b in self._other]
        self.body_end = self.refs_at if self.refs_at is not None else len(self.text)
        self._head_starts = [h["start"] for h in self.heads]

    def in_text(self, a: int, b: int) -> bool:
        """A span of the text itself: not in a passage marked as references or unreadable, and with no web address
        (a title page's DOI line, a reference)."""
        i = bisect.bisect_right(self._other_starts, a) - 1
        if i >= 0 and a < self._other[i][1]:
            return False
        return not _URL.search(self.flat[a:b])

    def page(self, off: int) -> int | None:
        if not self.page_starts:
            return None
        return max(1, bisect.bisect_right(self.page_starts, off))

    def section(self, off: int) -> str | None:
        i = bisect.bisect_right(self._head_starts, off) - 1
        return " ".join(self.heads[i]["text"].split()) if i >= 0 else None

    def item(self, a: int, b: int, **extra) -> dict:
        return {"start": a, "end": b, "text": _show(self.text, a, b), "page": self.page(a), "section": self.section(a),
                **extra}


# ------------------------------------------------------------------------------------------------------------------
# the parts of the report
# ------------------------------------------------------------------------------------------------------------------
def _outline(d: _Doc) -> list[dict]:
    """The headings with the words under each, up to the next heading (the reference list is marked)."""
    out = []
    total = max(1, _words(d.text))
    title = " ".join((d.title or "").split()).lower()
    for i, h in enumerate(d.heads[:MAX_SECTIONS]):
        end = d.heads[i + 1]["start"] if i + 1 < len(d.heads) else len(d.text)
        if " ".join(h["text"].split()).lower() == title and _words(d.text[h["end"]:end]) == 0:
            continue  # the document's title, read as a heading
        w = _words(d.text[h["end"]:end])
        out.append({"title": " ".join(h["text"].split()), "start": h["start"], "end": h["end"], "page": d.page(h["start"]),
                    "words": w, "share": round(w / total, 4),
                    "references": d.refs_at is not None and h["start"] <= d.refs_at < end})
    return out


def _abstract(d: _Doc) -> dict | None:
    """The abstract: under a heading 'Abstract' (or 'Summary'), else a line starting with the word, near the start."""
    a = b = None
    for i, h in enumerate(d.heads):
        if h["start"] > max(12000, len(d.text) * 0.25):
            break
        if _ABSTRACT_HEAD.match(h["text"].strip()):
            a = h["end"]
            b = d.heads[i + 1]["start"] if i + 1 < len(d.heads) else len(d.text)
            break
    if a is None:
        m = _ABSTRACT_INLINE.search(d.flat[:12000])
        if m:
            a = m.end()
            nxt = [x for x in d._head_starts if x > a + 100]
            b = nxt[0] if nxt else len(d.text)
    if a is None:
        return None
    m = _ABSTRACT_END.search(d.flat, a + 100, b)
    if m:
        b = m.start()
    b = min(b, a + 3000)
    while a < b and d.text[a].isspace():
        a += 1
    while b > a and d.text[b - 1].isspace():
        b -= 1
    if b - a < 150:
        return None
    return d.item(a, b)


def _key_sentences(d: _Doc, sents: list[tuple[int, int]], kt: list[dict], ws: Workspace,
                   skip: tuple[int, int] | None, n: int = KEY_SENTENCES) -> list[dict]:
    """The sentences that carry most of the document's key terms, spread over its sections, in reading order: an
    extractive summary (no AI). A sentence that opens with "it" or "they" is less likely to be chosen: out of its
    context the reader cannot tell what it refers to."""
    weight = {k["term_id"]: k["score"] for k in kt}
    if not weight or not sents:
        return []
    q = ",".join("?" * len(weight))
    starts = [s for s, _e in sents]
    has: dict[int, set[str]] = defaultdict(set)
    for r in ws.query(f"SELECT term_id, start FROM term_mentions WHERE doc_id=? AND term_id IN ({q})",
                      (d.doc_id, *weight)):
        i = bisect.bisect_right(starts, r["start"]) - 1
        if i >= 0 and r["start"] < sents[i][1]:
            has[i].add(r["term_id"])
    scored = []
    for i, ts in has.items():
        a, b = sents[i]
        if skip and a < skip[1] and b > skip[0]:
            continue  # shown as the abstract already
        s = _show(d.text, a, b)
        w = _words(s)
        if not SENT_WORDS[0] <= w <= SENT_WORDS[1] or not re.search(r"[.!]$", s) or s.endswith("?"):
            continue
        score = sum(weight[t] for t in ts) / math.sqrt(w)
        sec = d.section(a) or ""
        if _LEAD_SECTIONS.search(sec):
            score *= 1.25
        if opens_with_pronoun(s):
            score *= 0.5
        scored.append((score, a, i, ts, sec))
    scored.sort(key=lambda x: (-x[0], x[1]))
    picked: list[tuple] = []
    per_section: dict[str, int] = defaultdict(int)
    for sc in scored:
        _score, _a, _i, ts, sec = sc
        if per_section[sec] >= 2:
            continue
        if any(len(ts & p[3]) / len(ts | p[3]) >= 0.5 for p in picked):
            continue  # says much the same as one already chosen
        picked.append(sc)
        per_section[sec] += 1
        if len(picked) >= n:
            break
    label = {k["term_id"]: k["label"] for k in kt}
    return [d.item(sents[i][0], sents[i][1], terms=sorted((label[t] for t in ts), key=str.lower))
            for _s, _a, i, ts, _sec in sorted(picked, key=lambda x: x[1])]


def _own_voice(d: _Doc, sents: list[tuple[int, int]]) -> tuple[list[dict], list[dict]]:
    """What the document sets out to do, and what it says it found, in its own words (we, this study…)."""
    aims, finds, seen = [], [], set()
    for a, b in sents:
        s = _show(d.text, a, b)
        w = _words(s)
        if w < 8 or w > 90 or s.endswith("?") and not _AIM.search(s):
            continue
        key = re.sub(r"\W+", " ", s.lower()).strip()
        if key in seen:
            continue
        is_aim = _AIM.search(s)
        is_find = (_FINDING.search(s) or _CONCLUDING.match(s)
                   or (_SUMMING.match(s) and _CLOSING_SECTIONS.search(d.section(a) or "")))
        if is_find and not _FUTURE.search(s):
            if len(finds) < MAX_OWN:
                finds.append(d.item(a, b))
                seen.add(key)
        elif is_aim:
            if len(aims) < MAX_OWN:
                aims.append(d.item(a, b))
                seen.add(key)
    return aims, finds


def _claims(d: _Doc, own: list[dict]) -> dict:
    """The statements about the world the document makes (numbers, causes, comparisons, what research found, general
    claims), by the rules of "Check a draft", each marked cited or not."""
    taken = [(o["start"], o["end"]) for o in own]
    found: list[dict] = []
    for a, b in drafts.parts(d.flat[:d.body_end]):
        chunk = d.flat[a:b]
        cur = 0
        for c in drafts.rule_claims(chunk):
            i = chunk.find(c["quote"], cur)
            if i < 0:
                i = chunk.find(c["quote"])
                if i < 0:
                    continue
            cur = i + len(c["quote"])
            s, e = a + i, a + i + len(c["quote"])
            if not d.in_text(s, e) or any(s < y and e > x for x, y in taken):
                continue
            it = d.item(s, e, kind=c["kind"], why=c["why"], cited=bool(c["cited"]))
            it["own"] = bool(_OWN_SECTIONS.search(it["section"] or ""))
            found.append(it)
    by_kind: dict[str, int] = defaultdict(int)
    for c in found:
        by_kind[c["kind"]] += 1
    others = [c for c in found if not c["own"]]
    cited = sum(1 for c in others if c["cited"])
    # the ones without a citation outside its own data and results first: those are what a skim reader weighs
    shown = sorted(found, key=lambda c: (c["own"] or c["cited"], c["start"]))[:MAX_LIST]
    return {"total": len(found), "own": len(found) - len(others), "others": len(others), "cited": cited,
            "uncited": len(others) - cited, "by_kind": dict(by_kind), "kinds": drafts._WHY,
            "items": sorted(shown, key=lambda c: c["start"]), "cut": len(found) > MAX_LIST}


def _cited(d: _Doc) -> dict:
    """The works the document cites in its text, the most cited first, and the DOIs in its reference list."""
    entries = citations.numbered_list(d.flat, d.refs_at)
    markers = citations.find_markers(d.flat, d.body_end, entries)
    works: dict[tuple, dict] = {}
    for mk in markers:
        for r in mk["refs"]:
            if "number" in r:
                key = ("n", r["number"])
                label = f"[{r['number']}] {' '.join(r['entry'].split())[:200]}"
            else:
                if _NOT_AUTHORS.match((r["author"].replace("\xa0", " ").split() or [""])[-1].strip(",")):
                    continue                                   # "USD (2019)": a currency and its year
                who = " ".join(_SURNAME_NOISE.sub(" ", r["author"]).replace("&", "and").split()).lower()
                key = ("a", who, r["year"])
                label = f"{' '.join(r['author'].split()).rstrip(',')} ({r['year']})"
            w = works.setdefault(key, {"label": label, "count": 0, "start": mk["start"], "end": mk["end"],
                                       "page": d.page(mk["start"])})
            w["count"] += 1
    top = sorted(works.values(), key=lambda w: (-w["count"], w["start"]))[:MAX_CITED]
    dois = find_dois(d.flat[d.refs_at:]) if d.refs_at is not None else []
    return {"markers": len(markers), "works": len(works), "numbered_entries": len(entries), "top": top,
            "dois": len(set(dois)), "references_at": d.refs_at,
            "references_page": d.page(d.refs_at) if d.refs_at is not None else None}


def _codes(ws: Workspace, doc_id: str, framework: str | None) -> dict | None:
    if not framework:
        return None
    from . import profile

    try:
        p = profile.doc_profile(ws, framework, doc_id)
    except Exception:  # noqa: BLE001  (a codebook that is gone: the report goes on without codes)
        return None
    if not p["codes"]:
        return None
    out = []
    for c in p["codes"][:6]:
        first = next((i for i in c["items"] if i.get("start") is not None), None)
        out.append({"code": c["code"], "description": c["description"], "passages": c["passages"], "share": c["share"],
                    "start": first["start"] if first else None, "end": first["end"] if first else None})
    return {"framework": p["framework"], "framework_title": p["framework_title"], "codes": out,
            "total": len(p["codes"])}


def skim(ws: Workspace, doc_id: str, framework: str | None = None) -> dict:
    """The whole report on one document (see the module's docstring)."""
    terms.ensure(ws)
    d = _Doc(ws, doc_id)
    n_docs = int(ws.scalar("SELECT COUNT(*) FROM documents") or 0)
    body_words = _words(d.text[:d.body_end])
    abstract = _abstract(d)
    sents = _text_sentences(d)
    kt = terms.key_terms(ws, doc_id=doc_id, n=20)
    aims, finds = _own_voice(d, sents)
    return {
        "doc_id": doc_id, "title": d.title or d.file, "file": d.file, "kind": d.kind, "doi": d.doi,
        "facts": {"pages": d.n_pages, "words": body_words, "minutes": max(1, round(body_words / READ_WPM)),
                  "sections": len(d.heads), "sentences": len(sents)},
        "documents_in_project": n_docs,
        "abstract": abstract,
        "outline": _outline(d),
        "key_terms": {"basis": "document" if n_docs <= 1 else "corpus", "terms": kt[:15]},
        "key_sentences": _key_sentences(d, sents, kt, ws, (abstract["start"], abstract["end"]) if abstract else None),
        "aims": aims, "findings": finds,
        "claims": _claims(d, aims + finds),
        "cited": _cited(d),
        "codes": _codes(ws, doc_id, framework),
    }


# ------------------------------------------------------------------------------------------------------------------
# Markdown, to keep with one's notes
# ------------------------------------------------------------------------------------------------------------------
def _where(it: dict) -> str:
    bits = [f"p. {it['page']}" if it.get("page") else None, it.get("section")]
    return " · ".join(b for b in bits if b)


def to_markdown(r: dict) -> str:
    f = r["facts"]
    out = [f"# {r['title']}", ""]
    meta = [r["file"], f"{f['pages']} pages" if f.get("pages") else None, f"{f['words']:,} words",
            f"about {f['minutes']} min to read", f"doi {r['doi']}" if r.get("doi") else None]
    out += [" · ".join(m for m in meta if m), ""]
    if r["abstract"]:
        out += ["## Abstract", "", r["abstract"]["text"], ""]
    if r["aims"]:
        out += ["## What it sets out to do", ""] + [f"- {a['text']} ({_where(a)})" for a in r["aims"]] + [""]
    if r["findings"]:
        out += ["## What it says it found", ""] + [f"- {a['text']} ({_where(a)})" for a in r["findings"]] + [""]
    if r["key_sentences"]:
        out += ["## Key sentences", ""] + [f"- {a['text']} ({_where(a)})" for a in r["key_sentences"]] + [""]
    if r["key_terms"]["terms"]:
        out += ["## Key terms", "", ", ".join(f"{k['label']} ({k['mentions']})" for k in r["key_terms"]["terms"]), ""]
    if r["outline"]:
        out += ["## Sections", ""] + [f"- {s['title']}" + (f" (p. {s['page']}" if s.get("page") else " (")
                                      + f"{', ' if s.get('page') else ''}{s['words']:,} words)" for s in r["outline"]] + [""]
    c = r["claims"]
    if c["total"]:
        out += ["## Claims about the world", "",
                f"{c['total']} statements of the kinds that usually need a source"
                + (f": {c['own']} in its own abstract, data or results; of the other {c['others']}, " if c["own"] else "; ")
                + f"{c['cited']} come with a citation and {c['uncited']} do not.",
                ""]
        un = [x for x in c["items"] if not x["cited"] and not x["own"]]
        if un:
            out += ["Without a citation:", ""] + [f"- {x['text']} ({_where(x)}; {x['why'].lower()})" for x in un] + [""]
    ci = r["cited"]
    if ci["top"]:
        out += ["## Works it cites most", ""] + [f"- {w['label']}: {w['count']}×" for w in ci["top"]] + [""]
    if r["codes"]:
        out += [f"## Codes ({r['codes']['framework_title']})", ""] + [
            f"- {x['code']} {x['description']}: {x['passages']} passages" for x in r["codes"]["codes"]] + [""]
    out += ["---", "", "Skimmed by Margin on this computer, without AI: rules, counts and the document's own words."]
    return "\n".join(out).rstrip() + "\n"
