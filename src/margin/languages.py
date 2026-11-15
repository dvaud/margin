"""Documents in two languages (0.19): a side-by-side translation, an abstract printed in two languages.

A journal that prints each article in Spanish and English, column beside column, gives Margin every finding twice:
search by meaning finds both, a check may quote the Spanish, codes and themes count each point twice. The reader reads
the columns one after the other, so nearly every block is in one language; what was missing is a way to keep one.

1. **The languages of a document** (`survey`): each block that counts by its kind (a paragraph, a heading, a title,
   an abstract, a caption) is read by the common words of the 58 languages of `stopwords.detect`. A document is *in
   two languages* when its second language holds at least a fifth of the characters whose language is known and at
   least five blocks. Nothing is stored for it but this summary in the reading report.
2. **Each block's language within that pair** (`block_languages`): its words are weighed for the two languages only,
   so Spanish is never taken for Portuguese or Galician. A block with a fair share of both (a title printed in both
   languages, "recibido: … • received: …") is *mixed*; a block that does not tell (a name, "150") takes the language
   of the blocks on either side of it when they agree. Mixed blocks and those still unknown are always kept.
3. **Keep one language** (`keep_mask`): a person's choice, kept among the document's block choices under the reserved
   key `lang:<code>` (as `role:theory`, docrole.py), so it travels, merges and is proposed exactly as *Leave out* is.
   `reader.choose_inclusion` applies it after the kinds and the start and end of the text, before the person's own
   choice of a block, which still wins. Without the key nothing here runs, so no other document reads otherwise.
4. **Reader 6** (`reader.read_blocks(raw, version=6)`) keeps a passage from holding both languages of such a document:
   a paragraph is not carried on from one language into the other (a column ending without a full stop, the next
   starting lower-case), and short blocks of the two languages are not put together into one passage. A document a
   reader before 6 read is offered the new reader only when one of its passages holds both (`mixed_passages`).

Everything here depends on the text alone (and on the word lists that come with Margin), so the same file reads the
same on every computer.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Iterable, Sequence

from . import stopwords
from .textutil import token_spans

MIN_SHARE = 0.2    # the second language's share of the characters whose language is known
MIN_BLOCKS = 5     # and how many blocks it has at least
MIXED_RATIO = 0.4   # a block whose fewer different words of one language are this share of the other's is mixed
MIXED_WORDS = 2     # and at least this many different words of each (a title printed in two languages has few)
KEY = "lang:"      # the prefix of the block choice that keeps one language
COUNTED = ("body", "heading", "title", "abstract", "caption")   # reader.INCLUDED: the kinds a document is read by
MIXED = "mixed"
VERSION = 1        # of the summary kept in a reading report ("languages"): a newer one is made again


def key(code: str) -> str:
    return KEY + code


def kept_language(choices: dict) -> str | None:
    """The language a person chose to keep ({key: included or [included, kind]}), or None."""
    k = next((k for k in choices if isinstance(k, str) and k.startswith(KEY)), None)
    code = k[len(KEY):] if k else None
    return code if code in stopwords.NAMES else None


def name(code: str | None) -> str:
    return stopwords.NAMES.get(code or "", code or "")


def _words(text: str) -> list[str]:
    return [t[3] for t in token_spans(text, keep_stop=True)]


CITATION = frozenset(("et", "al"))   # "et al." is in every language's references


_FULL: dict[str, frozenset[str]] = {}


def _full(code: str) -> frozenset[str]:
    """A language's common words: English's own (`stopwords._EN_DETECT`: search's list holds other languages' words
    too), or the language's whole list without the words that are English words too ("final", "general", "door":
    `english_too`, as `stopwords.detect` reads them)."""
    s = _FULL.get(code)
    if s is None:
        if code == "en":
            s = stopwords._EN_DETECT
        else:
            too = {x for x in (stopwords._word(w) for w in stopwords._data().get("english_too") or ()) if x}
            s = stopwords.lists().get(code, frozenset()) - too
        s = _FULL[code] = frozenset(s)
    return s


def _pair_hits(words: Iterable[str], a: str, b: str) -> tuple[int, int, int, int]:
    """(hits of a, hits of b, different words of a, different words of b): a word speaks for a language when it is
    one of its common words and not one of the other's ("no", "me" and "de" speak for neither English nor Spanish)."""
    fa, fb = _full(a), _full(b)
    ha = hb = 0
    da: set[str] = set()
    db: set[str] = set()
    for w in words:
        if len(w) < 2 or not w.isalpha() or w in CITATION:
            continue
        ina, inb = w in fa and w not in fb, w in fb and w not in fa
        if ina:
            ha += 1
            da.add(w)
        elif inb:
            hb += 1
            db.add(w)
    return ha, hb, len(da), len(db)


def pair_language(text: str, a: str, b: str) -> str | None:
    """A block's language when its document is in languages a and b: a, b, MIXED (a fair share of both), or None
    (it does not tell)."""
    ha, hb, da, db = _pair_hits(_words(text), a, b)
    if da >= MIXED_WORDS and db >= MIXED_WORDS and min(da, db) >= MIXED_RATIO * max(da, db):
        return MIXED
    if da >= 2 and ha > 1.5 * hb:
        return a
    if db >= 2 and hb > 1.5 * ha:
        return b
    return None


def survey(items: Sequence[tuple[str, str]]) -> dict:
    """The languages of a document, from its blocks as (text, kind) in reading order: {"shares": {code: share of the
    characters whose language is known}, "blocks": {code: blocks}, "two": [first, second] | None, "v": VERSION}."""
    chars: Counter[str] = Counter()
    blocks: Counter[str] = Counter()
    for text, kind in items:
        if kind not in COUNTED or not text.strip():
            continue
        code = stopwords.detect(_words(text))
        if code:
            chars[code] += len(text)
            blocks[code] += 1
    known = sum(chars.values())
    shares = {c: round(n / known, 3) for c, n in chars.most_common()} if known else {}
    two = None
    top = [c for c, _n in chars.most_common(2)]
    if len(top) == 2 and chars[top[1]] >= MIN_SHARE * known and blocks[top[1]] >= MIN_BLOCKS:
        two = top
    return {"shares": shares, "blocks": dict(blocks.most_common()), "two": two, "v": VERSION}


def block_languages(items: Sequence[tuple[str, str]], two: Sequence[str] | None) -> list[str | None]:
    """Each block's language when the document is in the languages `two` (else all None): one of the two, MIXED, or
    None. Blocks of other kinds than those a document is read by are None. A block that does not tell takes the
    language of the nearest blocks before and after it that tell, when both are the same language."""
    if not two or len(two) != 2:
        return [None] * len(items)
    a, b = two
    out: list[str | None] = [pair_language(t, a, b) if k in COUNTED and t.strip() else None for t, k in items]
    told = [i for i, c in enumerate(out) if c in (a, b)]
    if not told:
        return out
    filled = list(out)
    j = 0   # the first told block after i
    for i, c in enumerate(out):
        while j < len(told) and told[j] <= i:
            j += 1
        if c is not None or items[i][1] not in COUNTED:
            continue
        before = out[told[j - 1]] if j > 0 else None
        after = out[told[j]] if j < len(told) else None
        if before is not None and before == after:
            filled[i] = before
    return filled


def keep_mask(items: Sequence[tuple[str, str]], keep: str) -> list[bool]:
    """Whether each block may count when a person keeps the language `keep`: False for a block of the document's
    other language, True for every other block (the kept language, mixed, unknown, or a document not in two
    languages, or not in `keep` at all)."""
    two = survey(items)["two"]
    if not two or keep not in two:
        return [True] * len(items)
    langs = block_languages(items, two)
    return [not (c is not None and c != MIXED and c != keep) for c in langs]


def mixed_passages(items: Sequence[tuple[str, str, int, int]], passages: Iterable[tuple[int, int]],
                   two: Sequence[str] | None) -> int:
    """How many passages hold blocks of both languages of a document in two (`items`: its blocks as (text, kind,
    start, end); `passages`: (start, end)). A reader before 6 put them together; reader 6 keeps them apart."""
    if not two:
        return 0
    langs = block_languages([(t, k) for t, k, _a, _z in items], two)
    spans = [(a, z, c) for (_t, _k, a, z), c in zip(items, langs) if c in two]
    n = 0
    for p0, p1 in passages:
        seen = {c for a, z, c in spans if a < p1 and z > p0}
        if len(seen) == 2:
            n += 1
    return n


def _make(query, doc_id: str) -> dict | None:
    """A document's languages made from its stored blocks and passages (`query(sql, args)` gives rows), or None for a
    document without blocks (read before 0.15)."""
    row = query("SELECT text FROM documents WHERE doc_id=?", (doc_id,))
    blocks = query("SELECT start, end, kind FROM blocks WHERE doc_id=? ORDER BY n", (doc_id,))
    if not row or not blocks:
        return None
    text = row[0][0] or ""
    items = [(text[a:z], k, a, z) for a, z, k in blocks]
    out = survey([(t, k) for t, k, _a, _z in items])
    passages = query("SELECT start, end FROM passages WHERE doc_id=?", (doc_id,))
    out["mixed_passages"] = mixed_passages(items, passages, out["two"])
    return out


_KEEP_SQL = ("UPDATE documents SET reading_json=json_set(reading_json, '$.languages', json(?)) "
             "WHERE doc_id=? AND json_valid(reading_json)")


def summary_for(cx, doc_id: str, keep: bool = True) -> dict | None:
    """A document's languages as its reading report keeps them (`survey` with "mixed_passages"), made from its stored
    blocks when the report has none yet (readings before 0.19) and then kept there (`keep`: `cx` is in a transaction
    that may write, `Workspace.connect`). None for a document without blocks (read before 0.15)."""
    row = cx.execute("SELECT reading_json FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    if row is None:
        return None
    have = from_report(row[0])
    if have is not None:
        return have
    out = _make(lambda sql, args: cx.execute(sql, args).fetchall(), doc_id)
    if out is not None and keep:
        cx.execute(_KEEP_SQL, (json.dumps(out), doc_id))
    return out


def from_report(raw: str | None) -> dict | None:
    """The languages a stored reading report holds (None: not made yet, or no report)."""
    try:
        rep = json.loads(raw) if raw else {}
    except ValueError:
        return None
    have = rep.get("languages") if isinstance(rep, dict) else None
    return have if isinstance(have, dict) and have.get("v") == VERSION else None


def _keep(ws, made: dict[str, dict]) -> None:
    """Keep languages made in their documents' reading reports, only if the project's database is free right now: a
    page that shows them never waits for other work (a move, a merge); they are made again at the next look."""
    import sqlite3

    if not made:
        return
    cx = sqlite3.connect(ws.db_path, timeout=0, isolation_level=None)
    try:
        cx.execute("BEGIN IMMEDIATE")
        cx.executemany(_KEEP_SQL, [(json.dumps(v), d) for d, v in made.items()])
        cx.execute("COMMIT")
    except sqlite3.OperationalError:   # busy: next time
        try:
            cx.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
    finally:
        cx.close()


def summary(ws, doc_id: str) -> dict | None:
    """`summary_for` without waiting: read as the project stands, kept only when the database is free."""
    rows = ws.query("SELECT reading_json FROM documents WHERE doc_id=?", (doc_id,))
    if not rows:
        return None
    have = from_report(rows[0][0])
    if have is not None:
        return have
    out = _make(ws.query, doc_id)
    if out is not None and rows[0][0]:
        _keep(ws, {doc_id: out})
    return out


def of_documents(ws, readers: Sequence[int] = (4, 5)) -> dict[str, dict]:
    """{doc_id: languages} of the documents read by one of `readers` (those the new reader may leave as they are):
    from their reading reports, made for those whose report has none yet (kept when the database is free). Never
    waits for other work on the project."""
    q = ",".join("?" * len(readers))
    out: dict[str, dict] = {}
    made: dict[str, dict] = {}
    for doc_id, raw in ws.query(f"SELECT doc_id, reading_json FROM documents WHERE reader IN ({q})", tuple(readers)):
        have = from_report(raw)
        if have is None:
            have = _make(ws.query, doc_id)
            if have is not None and raw:
                made[doc_id] = have
        if have is not None:
            out[doc_id] = have
    _keep(ws, made)
    return out


def new_reader_changes(reader: int, langs: dict | None, kind: str | None = None, latest: int | None = None) -> bool:
    """Whether the newest reader would read a document otherwise than the reader that read it, so it is offered:
    every document a reader before 5 read (a plain text file of reader 4 aside: reader 5 reads it as reader 4 did),
    a PDF reader 5 read (reader6.py reads PDFs only), and any other document reader 5 read (or that text file) only
    when one of its passages holds both of its languages (reader 6 changes nothing else)."""
    from .ingest import READER

    latest = READER if latest is None else latest
    if reader >= latest:
        return False
    if latest == 6 and (reader == 5 or (reader == 4 and kind == "text")):
        return (reader == 5 and kind == "pdf") or bool(langs and langs.get("mixed_passages"))
    return True
