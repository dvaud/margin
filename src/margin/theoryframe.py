"""A codebook from theory documents, as a framework draft (roadmap K2, rebuilt after the owner's first try).

The first version gave each theory document its own flat list of terms (its glossary, the sentences that define a
term, its headings and its frequent words) in a dialog of tick boxes. Five social-practice-theory texts gave 81 codes
("Involved", "Driving", "Packing", three *Agency* codes, one per document), each described by a sentence that merely
held the word, with no example: "the app throws some junk together and lets the user sift through it". What a person
codes with is a **framework**: groups of concepts, each concept with

- the theory's own words, quoted with document and page, from every document that defines it (`sources`);
- what it means, in plain words (`meaning`);
- when to use it in *the researcher's* documents, and when a neighbouring concept fits instead (`when_to_use`,
  `when_not`: what the AI labeller reads after "Use it when:", and the editor shows under *When to use it*);
- the words those documents use for it (`words`: the codebook's keywords; "volunteers" and "learned how to" find
  passages of a repair café report, "competence" finds none);
- passages of the researcher's documents that may show it, to keep as examples (`examples`, never from a theory or
  a working document).

**The draft** is one JSON file per project (`drafts/codebook-from-theory.json`, written whole and atomically; not the
`meta` table, which the shared folder's sync watches). A draft page edits it; *Make the codebook* turns the kept
concepts into codes (`make`) and the draft is gone.

Three pieces:

1. **Without AI** (`without_ai`, at `start`): what the texts define outright (glossary entries, defined terms, a
   heading's phrase that passes `theorycodes.candidates`), joined across documents by name: one concept, a source per
   document. Glossary entries start kept. The person adds concepts by name (`lookup` finds a term's defining sentences
   in the theory documents).
2. **The reading** (`read`, a job): every part of every document is drafted (`theory_codes`, as before, all parts
   queued at once for Claude Code), then one `theory_frame` task joins the drafts into groups and concepts with their
   meaning, when to use them and the evidence's words (measured on the owner's texts: 112 drafts gave 24 concepts in
   five groups). The same documents and focus reuse the kept answers (task ids are hashes of the input). If the frame
   step fails three times, the concepts fall back to the documents' drafts, ungrouped: a reading is never thrown away.
   What the person touched (kept or dropped by hand, edited, added, given examples) stays as it is.
3. **The meeting with the evidence** (`evidence`, no AI): a passage search with the concept's words and when to use
   it, of the evidence documents only, offering the sentence that holds most of the words.

Access: each document's own AI setting decides who reads its parts (Claude, a local AI, or nobody: a document marked
No AI is never in any payload, and only its own defined terms are used). The frame payload holds quotes of several
documents, each with its `doc_id` and `passage_id`, so `access` works out the strictest setting of them by itself;
the reader is the one for that setting, and a document that reader may not read is left out of the frame (and said).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
from collections import Counter
from typing import Any, Callable

from .store import Workspace, now

KIND = "theory_frame"
DRAFT_FILE = ("drafts", "codebook-from-theory.json")
VERSION = 1
MAX_CONCEPTS = 60          # in a draft
MAX_GROUPS = 12
MAX_EXAMPLES = 8           # a code keeps at most codebooks.MAX_EXAMPLES examples
MAX_DRAFTS = 150           # drafts in the frame payload (the highest-ranked of each document when there are more)
QUOTE_CHARS = 420          # a draft's quote in the frame payload, cut at a word
SHORT_QUOTE_CHARS = 200    # for a model on this computer whose context length does not hold the long ones
MAX_EVIDENCE_TITLES = 40
QUOTE_MAX = 400            # an evidence sentence offered as an example
MIN_SENTENCE_WORDS = 6

NO_DRAFT = "There is no codebook draft from theory documents in this project: start one first."
FRAME_FAILED = ("The AI could not put the framework together ({why}): the concepts are the drafts of each document, "
                "ungrouped.")

_lock = threading.Lock()   # a reading's end and a save from the page never write the draft at the same time
_KEY = re.compile(r"c[0-9a-f]{10}")
_GKEY = re.compile(r"[A-Za-z0-9_-]{1,20}")
_HOWS = ("ai", "glossary", "defined", "heading", "own")


def _h(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def _clean(v: Any, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def _norm(term: str) -> str:
    from .theorycodes import _norm as n

    return n(" ".join(str(term or "").split()))


def _new_key() -> str:
    return "c" + secrets.token_hex(5)


def _input_hash(doc_ids: list[str], focus: str) -> str:
    return _h(json.dumps(sorted(doc_ids)), focus or "")[:16]


# ---------------------------------------------------------------------------------------------
# the draft file
# ---------------------------------------------------------------------------------------------
def _path(ws: Workspace):
    return ws.root.joinpath(*DRAFT_FILE)


def _write(ws: Workspace, draft: dict) -> dict:
    p = _path(ws)
    p.parent.mkdir(parents=True, exist_ok=True)
    draft["rev"] = int(draft.get("rev") or 0) + 1   # every write: the page sends the one it loaded (`save`)
    part = p.with_name(p.name + f".{os.getpid()}.part")
    part.write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(part, p)
    return draft


def load(ws: Workspace) -> dict | None:
    """The project's draft, or None (none started, or a file that is not one)."""
    try:
        d = json.loads(_path(ws).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("version") == VERSION else None


def discard(ws: Workspace) -> None:
    with _lock:
        try:
            _path(ws).unlink()
        except FileNotFoundError:
            pass


def _titles(ws: Workspace, doc_ids: list[str]) -> dict[str, str]:
    if not doc_ids:
        return {}
    return {r["doc_id"]: r["title"] or "" for r in ws.query(
        f"SELECT doc_id, title FROM documents WHERE doc_id IN ({','.join('?' * len(doc_ids))})", list(doc_ids))}


def _empty_reading() -> dict:
    return {"state": "none", "job": None, "model": None, "at": None, "parts": 0, "parts_read": 0, "drafted": 0,
            "problems": [], "frame_task": None, "input": None}


def start(ws: Workspace, title: str, name: str, where: str, doc_ids: list[str], focus: str = "") -> dict:
    """A new draft from these theory documents (it replaces a draft that is there): the framework without AI
    (`without_ai`). `name` must be free for a codebook; `where`: "project" or "home". Raises ValueError (a plain
    sentence) or KeyError (a document that is not in the project)."""
    from . import codebooks

    if where not in ("project", "home"):
        raise ValueError("A codebook is kept with this project or with all projects.")
    if not isinstance(doc_ids, list) or not all(isinstance(d, str) for d in doc_ids):
        raise ValueError("Say the theory documents as a list (doc_ids).")
    ids = list(dict.fromkeys(d for d in doc_ids if d))
    if not ids:
        raise ValueError("Choose at least one theory document.")
    titles = _titles(ws, ids)
    missing = [d for d in ids if d not in titles]
    if missing:
        raise KeyError(missing[0])
    n = codebooks._free_name(ws, name)
    groups, concepts = without_ai(ws, ids)
    at = now()
    draft = {"version": VERSION, "title": _clean(title, 200) or n.replace("_", " ").capitalize(), "name": n,
             "where": where, "doc_ids": ids, "focus": _clean(focus, 500), "id": secrets.token_hex(8),
             "created_at": at, "updated_at": at,
             "reading": _empty_reading(), "groups": groups, "concepts": concepts, "left_out": []}
    with _lock:
        return _write(ws, draft)


_SPACED = re.compile(r"(?<!\w)(?:[^\W\d_]\s){3,}[^\W\d_]")           # "c o m m a n d"
_GLUED = re.compile(r"[a-z]{2,}[A-Z]{2,}[a-z]{2,}")                     # "witFTThose"


def _broken(quote: str) -> bool:
    """Whether a sentence is text the reader could not read cleanly (a scan's letters apart, words run together):
    not offered as a definition without AI, nor among the drafts set aside."""
    return bool(_SPACED.search(quote) or _GLUED.search(quote))


def _whole_sentence(text: str, a: int | None, z: int | None, limit: int = 500) -> tuple[int, int] | None:
    """The sentence (or sentences) of the document that hold the span a..z, when the span is a piece of them and they
    are not longer than `limit`: the AI often quotes the half of a sentence that names the concept, and a person reads
    a whole one. Within the span's own line only."""
    from .textutil import split_sentences

    if a is None or z is None or not (0 <= a < z <= len(text)) or "\n" in text[a:z]:
        return None
    la = text.rfind("\n", 0, a) + 1
    lz = text.find("\n", z)
    lz = len(text) if lz < 0 else lz
    spans = [(x, y) for x, y in split_sentences(text[la:lz], la) if x < z and y > a]
    if not spans:
        return None
    x, y = spans[0][0], spans[-1][1]
    x += len(text[x:y]) - len(text[x:y].lstrip())
    y = x + len(text[x:y].rstrip())
    m = re.match(r"\d{1,3}[.)]?\s+(?=[^\W\d_])", text[x:y])      # a footnote's number run into the sentence
    if m and x + m.end() <= a:
        x += m.end()
    # (a long lead-in before the AI's words buries the definition: "For the purposes of this chapter, which …, we")
    return (x, y) if (x, y) != (a, z) and x <= a and y >= z and y - x <= limit and a - x <= 60 else None


def _source(c: dict, doc_id: str, title: str) -> dict | None:
    d = c.get("definition")
    if not d or not d.get("quote"):
        return None
    return {"doc_id": doc_id, "title": title, "quote": d["quote"], "start": d.get("start"), "end": d.get("end"),
            "page": d.get("page")}


def _concept(name: str, how: str, keep: bool, sources: list[dict], **kw) -> dict:
    return {"key": kw.get("key") or "c" + _h(_norm(name))[:10], "group": kw.get("group", ""), "name": name,
            "meaning": kw.get("meaning", ""), "when_to_use": kw.get("when_to_use", ""),
            "when_not": kw.get("when_not", ""), "words": kw.get("words") or [name.lower()], "core": bool(kw.get("core")),
            "how": how, "keep": keep, "touched": False, "checked": False, "sources": sources, "examples": [],
            "ai": kw.get("ai")}


def without_ai(ws: Workspace, doc_ids: list[str]) -> tuple[list[dict], list[dict]]:
    """The framework a draft starts from without AI: what each document defines outright (its glossary's entries,
    the terms it defines, and the heading terms `theorycodes.candidates` offers), joined across documents by name
    (one concept, a source per document). No groups; glossary entries start kept, the rest not."""
    from . import theorycodes

    titles = _titles(ws, doc_ids)
    rank = {"glossary": 0, "defined": 1, "heading": 2}
    by: dict[str, dict] = {}
    for d in doc_ids:
        if d not in titles:
            continue
        for c in theorycodes.candidates(ws, d, with_examples=False)["concepts"]:
            if c["how"] not in rank:
                continue
            k = _norm(c["term"])
            src = _source(c, d, titles[d])
            if c["how"] != "glossary" and (src is None or _broken(src["quote"])):
                continue    # a sentence the reader could not read ("c o m m a nd", "witFTThose") defines nothing
            got = by.get(k)
            if got is None:
                by[k] = _concept(c["term"], c["how"], c["how"] == "glossary", [src] if src else [])
                continue
            if src and not any(s["doc_id"] == d for s in got["sources"]):
                got["sources"].append(src)
            if rank[c["how"]] < rank[got["how"]]:
                got["how"], got["keep"] = c["how"], got["keep"] or c["how"] == "glossary"
    out = sorted(by.values(), key=lambda c: (rank[c["how"]], -len(c["sources"])))
    return [], out[:MAX_CONCEPTS]


# ---------------------------------------------------------------------------------------------
# saving what the page sends
# ---------------------------------------------------------------------------------------------
def _clean_words(v: Any) -> list[str]:
    out: list[str] = []
    for w in (v if isinstance(v, list) else []):
        w = _clean(w, 60).replace(";", ",")
        if w and w.lower() not in [x.lower() for x in out]:
            out.append(w)
    return out[:20]


def _int_or_none(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _clean_sources(ws: Workspace, raw: Any, doc_ids: list[str], titles: dict[str, str], texts: dict,
                   was: list[dict] | None = None) -> list[dict]:
    """The quotes of a concept's theory documents, each a span of one of the draft's documents (checked: the page
    may move a source or attach one from `lookup`, never write one). A source the draft holds already (`was`) and
    the page sends back as it was is kept without a second look: a document read again since has other text, and
    its quotes must not fall out of every concept at the next save."""
    held = {(x.get("doc_id"), x.get("start"), x.get("end"), x.get("quote")): x for x in was or []}
    out: list[dict] = []
    for s in (raw if isinstance(raw, list) else [])[:12]:
        if not isinstance(s, dict) or s.get("doc_id") not in doc_ids:
            continue
        d, a, z = s["doc_id"], _int_or_none(s.get("start")), _int_or_none(s.get("end"))
        q = _clean(s.get("quote"), 2000)
        if any(x["doc_id"] == d and x["start"] == a for x in out):
            continue
        if (d, a, z, q) in held:
            out.append(held[(d, a, z, q)])
            continue
        if d not in texts:
            texts[d] = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (d,)) or ""
        if a is None or z is None or not (0 <= a < z <= len(texts[d])) or z - a > 2400 \
                or _clean(texts[d][a:z], 2000) != q or not q:
            continue
        out.append({"doc_id": d, "title": titles.get(d, ""), "quote": q, "start": a, "end": z,
                    "page": _int_or_none(s.get("page"))})
    return out


def _clean_examples(ws: Workspace, raw: Any, not_from: set[str], was: list[dict] | None = None,
                    texts: dict | None = None) -> list[dict]:
    """A concept's kept examples: spans of evidence documents only (never a theory or a working document, nor one of
    the draft's own documents), each checked as every quote is: its words are the document's text from `start` to
    `end` (as `evidence` gives them), and its title and page are the document's, never the page's say-so. An example
    the draft holds already (`was`) and the page sends back as it was is kept without a second look."""
    texts = {} if texts is None else texts
    held = {(e.get("doc_id"), e.get("start"), e.get("end"), e.get("quote")) for e in was or []}
    out: list[dict] = []
    for e in (raw if isinstance(raw, list) else []):
        if not isinstance(e, dict):
            continue
        q = _clean(e.get("quote"), 600)
        d = str(e.get("doc_id") or "")
        a, z = _int_or_none(e.get("start")), _int_or_none(e.get("end"))
        if not q or not d or d in not_from or q in [x["quote"] for x in out]:
            continue
        if (d, a, z, q) in held:
            out.append(next(x for x in was if (x.get("doc_id"), x.get("start"), x.get("end"), x.get("quote")) == (d, a, z, q)))
        else:
            if d not in texts:
                r = ws.query("SELECT text, title FROM documents WHERE doc_id=?", (d,))
                texts[d] = (r[0]["text"] or "", r[0]["title"] or "") if r else None
            if texts[d] is None or a is None or z is None or not (0 <= a < z <= len(texts[d][0])) or z - a > 4000 \
                    or _clean(texts[d][0][a:z], 600) != q:
                continue
            page = ws.scalar("SELECT page FROM pages WHERE doc_id=? AND start<=? AND ?<end", (d, a, a))
            out.append({"quote": q, "doc_id": d, "title": _clean(texts[d][1], 300), "page": page, "start": a, "end": z,
                        "project": ws.project_uid()})
        if len(out) >= MAX_EXAMPLES:
            break
    return out


_COMPARED = ("name", "meaning", "when_to_use", "when_not", "words", "keep", "group", "core", "checked", "sources",
             "examples")


class Stale(ValueError):
    """The page saved over a draft that changed since it loaded it (a reading ended, another tab saved)."""


def _comparable(c: dict) -> dict:
    return {k: ([(s.get("doc_id"), s.get("start")) for s in c.get(k) or []] if k == "sources" else
                [(e.get("doc_id"), e.get("quote")) for e in c.get(k) or []] if k == "examples" else c.get(k))
            for k in _COMPARED}


def save(ws: Workspace, patch: dict) -> dict:
    """Write what the page sends: {"title"?, "focus"?, "groups"?, "concepts"?}, each cleaned (lengths, types, at most
    MAX_CONCEPTS concepts and MAX_EXAMPLES examples a concept, each example a span of an evidence document). A
    concept is matched to the stored one by its key: what only the app writes (its `ai` words) stays, and a concept
    the page changed, or added, is marked `touched` (a reading then leaves it as it is). Raises ValueError (a plain
    sentence; nothing is written; `Stale` when the patch's "rev" is not the draft's) or LookupError when there is no
    draft."""
    from .docrole import not_evidence_docs

    if not isinstance(patch, dict):
        raise ValueError("Send the draft's changes as an object.")
    with _lock:
        draft = load(ws)
        if draft is None:
            raise LookupError(NO_DRAFT)
        if patch.get("rev") is not None and patch["rev"] != draft.get("rev"):
            # the whole lists are sent: an older page would write over what a reading or another tab put there
            raise Stale("The draft changed since this page loaded it: load it again.")
        if "title" in patch:
            draft["title"] = _clean(patch["title"], 200) or draft["title"]
        if "where" in patch:
            if patch["where"] not in ("project", "home"):
                raise ValueError("A codebook is kept with this project or with all projects.")
            draft["where"] = patch["where"]
        if "name" in patch and str(patch["name"] or "") != draft["name"]:
            from . import codebooks

            draft["name"] = codebooks._free_name(ws, str(patch["name"] or ""))
        if "focus" in patch:
            draft["focus"] = _clean(patch["focus"], 500)
        if "groups" in patch:
            if not isinstance(patch["groups"], list):
                raise ValueError("Send the groups as a list.")
            raw_groups = [g for g in patch["groups"] if isinstance(g, dict)]
            wanted = {str(g.get("key") or "") for g in raw_groups}
            groups, seen = [], set()
            for g in raw_groups:
                key = str(g.get("key") or "")
                if not _GKEY.fullmatch(key) or key in seen:
                    key = next(f"g{i}" for i in range(1, 10 ** 4) if f"g{i}" not in seen and f"g{i}" not in wanted)
                seen.add(key)
                groups.append({"key": key, "name": _clean(g.get("name"), 60) or "Group", "about": _clean(g.get("about"), 200)})
            if len(groups) > MAX_GROUPS:
                raise ValueError(f"A draft holds at most {MAX_GROUPS} groups.")
            draft["groups"] = groups
        if "concepts" in patch:
            if not isinstance(patch["concepts"], list):
                raise ValueError("Send the concepts as a list.")
            raw = [c for c in patch["concepts"] if isinstance(c, dict)]
            if len(raw) > MAX_CONCEPTS:
                raise ValueError(f"A draft holds at most {MAX_CONCEPTS} concepts: leave some out.")
            old = {c["key"]: c for c in draft["concepts"]}
            gkeys = {g["key"] for g in draft["groups"]}
            ids = draft["doc_ids"]
            titles = _titles(ws, ids)
            not_from = not_evidence_docs(ws._conn()) | set(ids)
            texts: dict = {}
            ex_texts: dict = {}
            out, keys = [], set()
            for i, c in enumerate(raw, 1):
                name = _clean(c.get("name"), 60)
                if not name:
                    raise ValueError(f"Concept {i} has no name.")
                key = str(c.get("key") or "")
                if not _KEY.fullmatch(key) or key in keys:
                    key = _new_key()
                keys.add(key)
                was = old.get(key)
                how = c.get("how") if c.get("how") in _HOWS else "own"
                group = str(c.get("group") or "")
                new = {"key": key, "group": group if group in gkeys else "", "name": name,
                       "meaning": _clean(c.get("meaning"), 1200), "when_to_use": _clean(c.get("when_to_use"), 1000),
                       "when_not": _clean(c.get("when_not"), 800), "words": _clean_words(c.get("words")),
                       "core": bool(c.get("core")), "how": was["how"] if was else how,
                       "keep": bool(c.get("keep")), "checked": bool(c.get("checked")),
                       "sources": _clean_sources(ws, c.get("sources"), ids, titles, texts,
                                                  was.get("sources") if was else None),
                       "examples": _clean_examples(ws, c.get("examples"), not_from,
                                                   was.get("examples") if was else None, ex_texts),
                       "ai": was.get("ai") if was else None}
                new["touched"] = was is None or bool(was.get("touched")) or _comparable(was) != _comparable(new)
                out.append(new)
            draft["concepts"] = out
        draft["updated_at"] = now()
        return _write(ws, draft)


# ---------------------------------------------------------------------------------------------
# whether the AI may read, and who
# ---------------------------------------------------------------------------------------------
def offer(ws: Workspace, doc_ids: list[str], settings: dict | None = None) -> dict:
    """Whether the AI may read these theory documents for the framework, and who would: {"offered" (one document at
    least), "why" (one line when not), "reader" ("claude" | "local" | "main" | None: the strictest of the documents
    offered), "parts" (in all), "documents": [{"doc_id", "title", "level", "parts", "offered", "why"}]}. A document
    marked No AI is left to the terms it defines itself, and says so."""
    from . import home, theorycodes

    s = settings if settings is not None else home.load_settings()
    titles = _titles(ws, doc_ids)
    docs = []
    for d in doc_ids:
        if d not in titles:
            continue
        o = theorycodes.ai_offer(ws, d, s)
        why = o["why"]
        if o.get("level") == "none":
            why = "This document is marked No AI: only the terms it defines itself are used."
        docs.append({"doc_id": d, "title": titles[d], "level": o.get("level"), "parts": o.get("parts") or 0,
                     "offered": o["offered"], "why": why, "reader": o.get("reader")})
    on = [x for x in docs if x["offered"]]
    reader = None
    if on:
        reader = "local" if any(x["reader"] == "local" for x in on) else on[0]["reader"]
    why = None
    if not on:
        why = (docs[0]["why"] if len(docs) == 1 else
               "No AI may read these documents: the framework is made of the terms they define themselves.") \
            if docs else "Choose at least one theory document."
    return {"offered": bool(on), "why": why, "reader": reader, "parts": sum(x["parts"] for x in on),
            "documents": [{k: x[k] for k in ("doc_id", "title", "level", "parts", "offered", "why")} for x in docs]}


# ---------------------------------------------------------------------------------------------
# the frame step: payload, prompt size, store check, offline demo
# ---------------------------------------------------------------------------------------------
def _cut(q: str, n: int) -> str:
    q = " ".join((q or "").split())
    return q if len(q) <= n else q[:n].rsplit(" ", 1)[0] + " …"


def _payload(documents: list[dict], evidence_titles: list[str], focus: str, by_doc: list[list[dict]],
             per_doc: int | None, chars: int) -> tuple[dict, list[dict]]:
    """The frame payload from each document's ranked drafts: at most `per_doc` of each (the highest-ranked), at most
    MAX_DRAFTS in all (taken in turn from each document), quotes cut to `chars`. Returns (payload, the drafts sent
    with their numbers)."""
    lists = [lst[:per_doc] if per_doc is not None else lst for lst in by_doc]
    picked: list[list[dict]] = [[] for _ in lists]
    n, i = 0, 0
    while n < MAX_DRAFTS and any(i < len(lst) for lst in lists):
        for j, lst in enumerate(lists):
            if i < len(lst) and n < MAX_DRAFTS:
                picked[j].append(lst[i])
                n += 1
        i += 1
    sent = []
    for lst in picked:
        for d in lst:
            sent.append({**d, "n": len(sent) + 1})
    payload = {"documents": [x for x in documents if any(d["doc_id"] == x["doc_id"] for d in sent)],
               "evidence_titles": evidence_titles, "focus": focus,
               "drafts": [{"n": d["n"], "doc_id": d["doc_id"], "passage_id": d["passage_id"], "title": d["title"],
                           "name": d["name"], "quote": _cut(d["quote"], chars), "how": d["how"]} for d in sent]}
    return payload, sent


def _room(be, settings: dict) -> int | None:
    """The characters the frame's user prompt may hold for this reader: None for Claude (no limit here); for a model
    on this computer, what its context length leaves after the instructions, the answer and its reasoning (as
    `theorycodes._part_chars` works it out)."""
    n = getattr(be, "num_ctx", None)
    if not n:
        return None
    from . import home, prompts
    from .llm import CONTEXT_MARGIN, OUTPUT_CAP, THINK_ALLOWANCE, estimate_tokens

    if str(settings.get("num_ctx", "auto")).lower() == "auto":
        be.num_ctx = max(int(n), home.context_plan(settings, (KIND,))["num_ctx"])
    think, only, budget = home.thinking(settings)
    reasons = think is not False and (only is None or KIND in only)
    room = int(be.num_ctx) - estimate_tokens(prompts.system_prompt(KIND)) - OUTPUT_CAP.get(KIND, 7000) \
        - ((2 * budget + 64 if budget else THINK_ALLOWANCE) if reasons else 0) - CONTEXT_MARGIN
    return int(room * 3.5) - 1600      # less a retry's problems


def fit_payload(documents, evidence_titles, focus, by_doc, room: int | None) -> tuple[dict, list[dict]]:
    """The frame payload that fits `room` characters of user prompt: long quotes, then short ones (SHORT_QUOTE_CHARS),
    then fewer drafts of each document (the highest-ranked kept). Raises ValueError when not even three drafts of a
    document fit."""
    from . import prompts

    def size(p: dict) -> int:
        return len(prompts.user_prompt(KIND, p))

    p, sent = _payload(documents, evidence_titles, focus, by_doc, None, QUOTE_CHARS)
    if room is None or size(p) <= room:
        return p, sent
    p, sent = _payload(documents, evidence_titles, focus, by_doc, None, SHORT_QUOTE_CHARS)
    per = max((len(x) for x in by_doc), default=0)
    while size(p) > room:
        if per <= 3:
            raise ValueError("The context length of the model on this computer is too small to put a framework "
                             "together. Set it to automatic in Settings, or to 16,384 or more.")
        per = max(3, int(per * 0.8))
        p, sent = _payload(documents, evidence_titles, focus, by_doc, per, SHORT_QUOTE_CHARS)
    return p, sent


def make_task(ws: Workspace, payload: dict, model: str) -> str:
    """The frame's task, one per input: the same drafts, documents, focus, prompt version and model give the same
    task, so a reading asked again reuses its answer."""
    from . import prompts
    from .tasks import replace_task

    tid = f"{KIND}:" + _h(json.dumps(payload, sort_keys=True, ensure_ascii=False), prompts.VERSIONS.get(KIND) or "",
                          model or "")[:16]
    with ws.connect() as cx:
        replace_task(cx, tid, KIND, model, payload)
    return tid


def store_frame(cx, t, payload: dict, obj: dict, model: str) -> tuple[bool, list[str]]:
    """Check the framework (theory-frame-v1): every number in `from` names a draft, no draft is in two concepts, no
    two concepts share a name. How many concepts are core (6 to 12 asked for) is never a reason to send it back. The
    answer itself is kept with the task (`results`), and `frame_of` reads it."""
    from .schema import TheoryFrameOut

    out = TheoryFrameOut.model_validate(obj)
    nums = {d["n"] for d in payload.get("drafts") or []}
    errors: list[str] = []
    where: dict[int, str] = {}
    names: dict[str, str] = {}
    for g in out.groups:
        for c in g.concepts:
            k = _norm(c.name)
            if k in names:
                errors.append(f"two concepts are called {c.name!r}: join them into one, or name them apart")
            names[k] = c.name
            for n in dict.fromkeys(c.from_):
                if n not in nums:
                    errors.append(f"{c.name}: there is no draft {n} (the drafts are numbered 1 to {len(nums)})")
                elif n in where:
                    errors.append(f"draft {n} is in two concepts ({where[n]} and {c.name}): a draft belongs to at "
                                  "most one concept")
                else:
                    where[n] = c.name
    return not errors, errors


def frame_of(ws: Workspace, task_id: str) -> tuple[Any, str] | None:
    """The accepted framework of a frame task and the model that gave it, or None."""
    from .schema import TheoryFrameOut
    from .tasks import parse_json

    if ws.scalar("SELECT status FROM tasks WHERE task_id=?", (task_id,)) != "done":
        return None
    r = ws.query("SELECT raw_json, model FROM results WHERE task_id=? AND valid=1 ORDER BY attempt DESC LIMIT 1",
                 (task_id,))
    if not r:
        return None
    return TheoryFrameOut.model_validate(parse_json(r[0]["raw_json"])), r[0]["model"]


def demo_answer(payload: dict) -> dict:
    """The offline demo's framework: one group with the first eight drafts (of different names), not read."""
    concepts, seen = [], set()
    for d in payload.get("drafts") or []:
        name = " ".join(str(d.get("name") or "").split()[:6])
        k = _norm(name)
        if len(name) < 2 or k in seen:
            continue
        seen.add(k)
        words = [name.lower()]
        for w in re.findall(r"[^\W\d_]{4,}", d.get("quote") or ""):
            if w.lower() not in words and len(words) < 5:
                words.append(w.lower())
        words += [w for w in ("offline", "demo", "not read") if w not in words][:max(0, 3 - len(words))]
        concepts.append({"name": name, "from": [d["n"]], "meaning": f"Offline demo: {name}, as the theory names it.",
                         "when_to_use": f"When a passage speaks of {name.lower()} (offline demo: not read).",
                         "not_when": None, "words": words, "core": len(concepts) < 6})
        if len(concepts) >= 8:
            break
    if not concepts:
        concepts = [{"name": "Offline demo", "from": [1], "meaning": "Offline demo: no drafts to read.",
                     "when_to_use": "When a passage (offline demo: not read).", "not_when": None,
                     "words": ["offline", "demo", "not read"], "core": True}]
    return {"groups": [{"name": "Concepts of the theory", "about": "Offline demo: the first drafts, not read.",
                        "concepts": concepts}], "note": "Offline demo: the drafts were not read."}


def prompt_size(k: int, max_chars: int) -> int:
    """The longest user prompt of a frame, in characters (home.prompt_tokens)."""
    return 1500 + MAX_EVIDENCE_TITLES * 150 + MAX_DRAFTS * (QUOTE_CHARS + 120)


# ---------------------------------------------------------------------------------------------
# the reading
# ---------------------------------------------------------------------------------------------
def _passage_at(ws: Workspace, doc_id: str, at: int | None) -> str | None:
    if at is None:
        return None
    return ws.scalar("SELECT passage_id FROM passages WHERE doc_id=? AND start<=? AND ?<end ORDER BY start DESC LIMIT 1",
                     (doc_id, at, at))


def _evidence_titles(ws: Workspace, skip: set[str], levels_ok: set[str], provider: str | None = None) -> list[str]:
    """The titles of the evidence documents the frame's reader may read (their titles only: no id, so they never make
    the payload's setting stricter), at most MAX_EVIDENCE_TITLES."""
    from . import access
    from .docrole import not_evidence_docs

    skip = skip | not_evidence_docs(ws._conn())
    rows = [r for r in ws.query("SELECT doc_id, title FROM documents ORDER BY title") if r["doc_id"] not in skip]
    lv = access.levels(ws, [r["doc_id"] for r in rows], provider=provider) if rows else {}
    dflt = access.default(ws)
    out = [_clean(r["title"], 140) or "untitled" for r in rows if (lv.get(r["doc_id"]) or dflt) in levels_ok]
    return out[:MAX_EVIDENCE_TITLES]


def mark_running(ws: Workspace, job_id: str) -> None:
    """The draft says a reading runs, with its job (so the page finds it again after a reload). Once per job: a
    reading that has already ended under this job is left as it is."""
    with _lock:
        d = load(ws)
        if d is None or d["reading"].get("job") == job_id:
            return
        was = d["reading"]
        before = was.get("before") if was.get("state") == "running" else was.get("state")   # (a job that died)
        d["reading"] = {**was, "before": before, "state": "running", "job": job_id}
        _write(ws, d)


def _same_draft(d: dict | None, ident: str) -> bool:
    """Whether a draft is the one a reading started on (its id; a draft from before ids: when it was made)."""
    return d is not None and (d.get("id") or d.get("created_at")) == ident


def _end_reading(ws: Workspace, created_at: str, reading: dict, apply: Callable[[dict], None] | None) -> dict | None:
    """Write a reading's end into the draft it was started for (a draft discarded or started again meanwhile is left
    alone), applying `apply` to it under the lock."""
    with _lock:
        d = load(ws)
        if not _same_draft(d, created_at):
            return None
        if apply:
            apply(d)
        d["reading"] = reading
        d["updated_at"] = now()
        return _write(ws, d)


def _drafts_of(ws: Workspace, doc_id: str, title: str, found: dict, read: list[str]) -> list[dict]:
    """One document's drafts, best first: its own glossary entries and defined terms, then the AI's drafts of its
    parts (`theorycodes.ai_drafts`, without those): each {"doc_id", "passage_id", "title", "name", "quote", "start",
    "end", "page", "how"}."""
    from . import theorycodes

    out, seen = [], set()
    for c in found["concepts"]:
        d = c.get("definition")
        if c["how"] in ("glossary", "defined") and d and d.get("quote"):
            seen.add(_norm(c["term"]))
            out.append({"doc_id": doc_id, "title": title, "name": c["term"], "how": c["how"], **_span(d),
                        "passage_id": _passage_at(ws, doc_id, d.get("start"))})
    if read:
        text = ws.scalar("SELECT text FROM documents WHERE doc_id=?", (doc_id,)) or ""
        for c in theorycodes.ai_drafts(ws, read, seen, with_examples=False):
            d = dict(c["definition"])
            whole = _whole_sentence(text, d.get("start"), d.get("end"))
            if whole:
                d.update(start=whole[0], end=whole[1], quote=" ".join(text[whole[0]:whole[1]].split()))
            out.append({"doc_id": doc_id, "title": title, "name": c["term"], "how": "ai", **_span(d),
                        "passage_id": _passage_at(ws, doc_id, d.get("start"))})
    return out


def _span(d: dict) -> dict:
    return {"quote": d["quote"], "start": d.get("start"), "end": d.get("end"), "page": d.get("page")}


def _src(d: dict) -> dict:
    return {"doc_id": d["doc_id"], "title": d["title"], "quote": d["quote"], "start": d.get("start"),
            "end": d.get("end"), "page": d.get("page")}


def _keeps(c: dict) -> bool:
    """A concept the person has made their own: kept or dropped by hand, edited, added, or given examples."""
    return bool(c.get("touched") or c.get("how") == "own" or c.get("examples") or c.get("checked"))


def _sources_of(drafts: list[dict]) -> list[dict]:
    """One source per document, the best draft of each (its glossary's entry, then a defined term, then the AI's)."""
    rank = {"glossary": 0, "defined": 1}
    best: dict[str, dict] = {}
    for d in drafts:
        b = best.get(d["doc_id"])
        if b is None or (rank.get(d["how"], 2), d["n"]) < (rank.get(b["how"], 2), b["n"]):
            best[d["doc_id"]] = d
    order = list(dict.fromkeys(d["doc_id"] for d in drafts))
    return [_src(best[x]) for x in order]


def _ident(d: dict) -> tuple:
    return d["doc_id"], d["name"], d.get("start")


def apply_frame(draft: dict, frame, model: str | None, sent: list[dict], drafts: list[dict], outside: set[str]) -> None:
    """Write a framework (`frame`, its drafts numbered as `sent`; or None: the `drafts`, joined by name, ungrouped)
    into the draft: groups, concepts and `left_out` (the drafts no concept is made of). A concept the person made
    their own stays as it is (its group found again by name). The quotes of documents the frame did not read
    (`outside`: marked No AI, or left out) are kept: a concept made only of them stays, and the sources of one join
    a concept of its name. Everything else is the framework's. Core concepts start kept."""
    mine = [c for c in draft["concepts"] if _keeps(c)]
    old_groups = {g["key"]: g for g in draft["groups"]}
    groups: list[dict] = []
    concepts: list[dict] = []
    used: set[tuple] = set()
    if frame is not None:
        by_n = {d["n"]: d for d in sent}
        for i, g in enumerate(frame.groups, 1):
            gk = f"g{i}"
            groups.append({"key": gk, "name": _clean(g.name, 60), "about": _clean(g.about, 200)})
            for c in g.concepts:
                ds = [by_n[n] for n in c.from_ if n in by_n]
                used |= {_ident(d) for d in ds}
                concepts.append(_concept(
                    c.name[:1].upper() + c.name[1:], "ai", bool(c.core), _sources_of(ds), group=gk, meaning=c.meaning,
                    when_to_use=c.when_to_use, when_not=c.not_when or "", words=list(c.words), core=c.core,
                    ai={"model": model, "meaning": c.meaning, "when_to_use": c.when_to_use,
                        "when_not": c.not_when or ""}))
    else:
        joined: dict[str, list[dict]] = {}
        for d in drafts:
            joined.setdefault(_norm(d["name"]), []).append(d)
        for ds in joined.values():
            how = ds[0]["how"] if ds[0]["how"] in ("glossary", "defined") else "ai"
            concepts.append(_concept(ds[0]["name"], how, how == "glossary", _sources_of(ds)))
            used |= {_ident(d) for d in ds}
    # what the person made their own wins over the framework's concept of the same name
    taken = {_norm(c["name"]) for c in mine}
    concepts = [c for c in concepts if _norm(c["name"]) not in taken]
    by_name = {_norm(c["name"]): c for c in concepts}
    for c in draft["concepts"]:
        k = _norm(c["name"])
        out_src = [x for x in c.get("sources") or [] if x["doc_id"] in outside]
        if _keeps(c) or k in taken or not out_src:
            continue
        if k in by_name:
            got = by_name[k]
            got["sources"] += [x for x in out_src if not any(y["doc_id"] == x["doc_id"] for y in got["sources"])]
        elif len(out_src) == len(c["sources"]):
            concepts.append({**c, "group": ""})
            by_name[k] = concepts[-1]
    gname = {_norm(g["name"]): g["key"] for g in groups}
    for c in mine:
        g = old_groups.get(c.get("group") or "")
        if g is None:
            c["group"] = ""
            continue
        k = _norm(g["name"])
        if k not in gname:
            have = {x["key"] for x in groups}
            key = next(f"g{i}" for i in range(len(groups) + 1, 10 ** 4) if f"g{i}" not in have)
            groups.append({**g, "key": key})
            gname[k] = key
        c["group"] = gname[k]
    keys: set[str] = set()
    for c in mine + concepts:
        if c["key"] in keys:
            c["key"] = _new_key()
        keys.add(c["key"])
    # the person's concepts keep their place first, then the framework's in its order
    draft["groups"] = groups
    over = (mine + concepts)[MAX_CONCEPTS:]
    draft["concepts"] = (mine + concepts)[:MAX_CONCEPTS]
    # the drafts no concept is made of, to add by hand: a name once (two documents, or two parts, drafted "zooming
    # in"), none the framework has under that name, none whose quote is a scrap of a sentence
    left, seen = [], {_norm(c["name"]) for c in draft["concepts"]}
    for c in over:      # a draft holds MAX_CONCEPTS: what does not fit is set aside, never dropped
        for x in c.get("sources") or []:
            if _norm(c["name"]) not in seen:
                seen.add(_norm(c["name"]))
                left.append({"name": c["name"], **{k: x.get(k) for k in ("doc_id", "title", "quote", "start", "end", "page")}})
    for d in (drafts if frame is not None else []):
        k = _norm(d["name"])
        if _ident(d) in used or k in seen or len(d["quote"].split()) < MIN_SENTENCE_WORDS or _broken(d["quote"]):
            continue
        seen.add(k)
        left.append({"name": d["name"], **_src(d)})
    draft["left_out"] = left


def _read_all(ws: Workspace, batches: list[dict], readers, prog: Callable, total: int,
              should_stop: Callable[[], bool] | None) -> str | None:
    """`theorycodes.read_parts` for every document. 0.19.13: in a job of the app, the documents only the local model
    may read wait for its own Start (when Claude reads others), and are read beside Claude's once it is pressed (the
    job's local gate); stopped before, they are not read (the reading counts as stopped)."""
    from . import theorycodes

    local = [b for b in batches if b["be"] is not readers.backend]
    if not local or not readers.defers():
        return theorycodes.read_parts(ws, batches, prog, should_stop)
    cloud = [b for b in batches if b["be"] is readers.backend]
    seen = {"cloud": 0, "local": 0}
    out: dict = {}

    def part(key: str) -> Callable:
        def report(done: int, _n: int) -> None:
            seen[key] = done
            prog(seen["cloud"] + seen["local"], total)
        return report

    def read_local() -> None:
        out["local"] = theorycodes.read_parts(ws, local, part("local"), should_stop)

    readers.later(read_local, n=len(local), noun="document", mixed=bool(cloud), ws=ws)
    halted = theorycodes.read_parts(ws, cloud, part("cloud"), should_stop) if cloud else None
    readers.drain()
    if "local" not in out:
        for b in local:  # never read: the job was stopped while the local part waited for its Start
            b.update(refused=None, read=[], problems=[], used=b["call"], reused=False)
        return halted or "stopped"
    return halted or out["local"]


def read(ws: Workspace, backend, model: str, progress: Callable | None = None,
         should_stop: Callable[[], bool] | None = None, readers=None, job: str | None = None) -> dict:
    """The reading of a draft's theory documents (a job): every part of every document the AI may read is drafted
    (`theory_codes`), the drafts are joined into a framework (one `theory_frame` task), and the framework is written
    into the draft (`apply_frame`). Written to the research log. Returns {"ok" (a framework was put together),
    "stopped", "withdrawn", "state" (the draft's reading now), "model", "parts", "parts_read", "drafted", "groups",
    "concepts", "problems", "reused", "frame_task", "discarded" (the draft was discarded or started again meanwhile:
    nothing written)}. `job`: the app's job id, kept in the draft while it runs."""
    from . import access, researchlog, theorycodes, tasks
    from . import runs as runs_mod

    draft = load(ws)
    if draft is None:
        raise ValueError(NO_DRAFT)
    if job:
        mark_running(ws, job)
    created, ids, focus = draft.get("id") or draft["created_at"], list(draft["doc_ids"]), draft.get("focus") or ""
    before = draft["reading"].get("before") if draft["reading"].get("state") == "running" else draft["reading"]["state"]
    readers = readers or access.Readers(backend, model, should_stop=should_stop)
    settings = readers.settings()
    titles = _titles(ws, ids)
    problems: list[str] = []
    batches, found, levels = [], {}, {}
    for d in ids:
        if d not in titles:
            problems.append("A document of this draft is no longer in the project.")
            continue
        lv = theorycodes._level(ws, d, readers.provider)
        levels[d] = lv
        if lv == "none":
            problems.append(f"{titles[d]}: marked No AI, so only the terms it defines itself are used.")
            continue
        got = readers.for_level(lv)
        if got is None:
            problems.append(f"{titles[d]}: {theorycodes.NO_LOCAL if lv == 'local' else theorycodes.NO_AI}")
            continue
        be, call = got
        found[d] = theorycodes.candidates(ws, d, with_examples=False)
        try:
            tids = theorycodes.make_ai_tasks(ws, d, call, theorycodes._part_chars(be, settings), found[d])
        except ValueError as e:
            problems.append(f"{titles[d]}: {e}")
            continue
        batches.append({"doc_id": d, "be": be, "call": call, "tids": tids})
    n_parts = sum(len(b["tids"]) for b in batches)
    total = n_parts + 1

    def prog(done: int, _n: int) -> None:
        if progress:
            progress(done, total)

    halted = _read_all(ws, batches, readers, prog, total, should_stop) if batches else None
    parts_read = sum(len(b.get("read") or []) for b in batches)
    reading = {**_empty_reading(), "job": job, "parts": n_parts, "parts_read": parts_read,
               "input": _input_hash(ids, focus), "at": now()}
    if halted:
        state = before if before == "read" else "none" if halted == "stopped" else "failed"
        why = None if halted == "stopped" else theorycodes.WITHDRAWN
        old = draft["reading"]
        _end_reading(ws, created, {**(old if before == "read" else reading), "state": state, "job": job,
                                   "problems": [why] if why else []}, None)
        return {"ok": False, "stopped": halted == "stopped", "withdrawn": halted == "withdrawn", "state": state,
                "model": None, "parts": n_parts, "parts_read": parts_read, "drafted": 0, "groups": 0, "concepts": 0,
                "problems": [why] if why else [], "reused": False, "frame_task": None, "discarded": False}
    outside = {d for d in ids if levels.get(d) == "none"}
    for b in batches:
        if b["refused"]:
            # its setting is stricter now than when the reading began: none of its text goes to the frame either
            problems.append(f"{titles[b['doc_id']]}: {b['refused']}")
            outside.add(b["doc_id"])
        problems += [f"{titles[b['doc_id']]}, {p}" for p in b["problems"][:2]]
    read_by = {b["doc_id"]: b["read"] for b in batches if not b["refused"]}
    # the drafts of each document an AI may see: its own defined terms, and its parts' drafts
    by_doc = [_drafts_of(ws, d, titles[d], found.get(d) or theorycodes.candidates(ws, d, with_examples=False),
                         read_by.get(d, [])) for d in ids if d in titles and d not in outside]
    by_doc = [x for x in by_doc if x]
    numbered = [{**dr, "n": i} for i, dr in enumerate((dr for x in by_doc for dr in x), 1)]
    # the frame's reader: the one for the strictest setting among the documents with drafts (else Claude's, and the
    # documents only a local AI may read are left out)
    frame, used, frame_task, sent, frame_problem, reused = None, None, None, [], None, False
    if by_doc:
        doc_lv = {x[0]["doc_id"]: levels[x[0]["doc_id"]] for x in by_doc}
        got = readers.for_level(access.most(doc_lv.values())) or readers.for_level("cloud")
        if got is None:
            frame_problem = "no AI may read these documents together"
        else:
            be, call = got
            ok_levels = access.backend_levels(be)
            left = [d for d, lv in doc_lv.items() if lv not in ok_levels]
            for d in left:
                problems.append(f"{titles[d]}: left out of the framework (only a local AI may read it, and the "
                                "framework is put together by Claude).")
            outside |= set(left)
            kept = [x for x in by_doc if x[0]["doc_id"] not in left]
            documents = [{"doc_id": x[0]["doc_id"], "title": titles[x[0]["doc_id"]]} for x in kept]
            try:
                payload, sent = fit_payload(documents, _evidence_titles(ws, set(ids), ok_levels, access.provider_of(be)), focus, kept,
                                            _room(be, settings)) if kept else (None, [])
            except ValueError as e:
                payload, frame_problem = None, str(e)
            if payload:
                frame_task = make_task(ws, payload, call)
                with ws.connect() as cx:
                    now_lv = access.recheck(cx, frame_task, provider=access.provider_of(be))
                    if now_lv is not None and now_lv in access.backend_levels(be) \
                            and getattr(be, "name", "") == "claude_code":
                        tasks.mark_queued(cx, [frame_task])
                if now_lv is None or now_lv not in access.backend_levels(be):
                    frame_problem = "a document's AI setting changed"
                else:
                    was = ws.scalar("SELECT status FROM tasks WHERE task_id=?", (frame_task,))
                    rid = runs_mod.start(ws, KIND, draft["name"], be, call, 1)
                    try:
                        ok, errs = tasks.run_one(ws, frame_task, be, call)
                    except Exception:
                        if should_stop and should_stop():
                            from . import taskqueue

                            taskqueue.withdraw(ws, task_ids=[frame_task])
                        raise
                    finally:
                        runs_mod.finish(ws, rid, 1)
                    if progress:
                        progress(total, total)
                    if should_stop and should_stop() and not ok:
                        # stopped while the frame was asked: the draft keeps what it had
                        state = before if before == "read" else "none"
                        _end_reading(ws, created, {**draft["reading"], "state": state, "job": job}, None)
                        return {"ok": False, "stopped": True, "withdrawn": False, "state": state, "model": None,
                                "parts": n_parts, "parts_read": parts_read, "drafted": len(numbered), "groups": 0,
                                "concepts": 0, "problems": [], "reused": False, "frame_task": frame_task,
                                "discarded": False}
                    got_frame = frame_of(ws, frame_task) if ok else None
                    if got_frame:
                        frame, used = got_frame
                        last = ws.query("SELECT route FROM results WHERE task_id=? AND valid=1 ORDER BY attempt DESC "
                                        "LIMIT 1", (frame_task,))
                        reused = was == "done" or bool(last and "kept answer" in (last[0]["route"] or ""))
                    else:
                        frame_problem = "; ".join(errs[:2]) or "its answer was not accepted"
    elif not problems:
        frame_problem = "the documents gave no drafts"
    if frame is None:
        if by_doc:
            problems.append(FRAME_FAILED.format(why=frame_problem or "no answer"))
        else:
            problems.append("Nothing was drafted from these documents: the concepts are the terms they define "
                            "themselves.")
    else:
        n_core = sum(1 for g in frame.groups for c in g.concepts if c.core)
        if not 6 <= n_core <= 12:
            problems.append(f"The AI put {n_core} concept{'s' if n_core != 1 else ''} in the codebook to start with "
                            "(6 to 12 were asked for): add or take out more yourself.")
    model_used = used or next((b["used"] for b in batches if b.get("read")), None)
    reading.update(state="read" if (frame is not None or numbered) else "failed", model=model_used,
                   drafted=len(numbered), problems=problems[:8], frame_task=frame_task)
    result: dict = {}

    def apply(d: dict) -> None:
        if frame is None and not numbered:
            return            # nothing read: the draft keeps its concepts
        apply_frame(d, frame, used, sent, numbered, outside)
        result.update(groups=len(d["groups"]), concepts=len(d["concepts"]))

    written = _end_reading(ws, created, reading, apply)
    n_docs = len(by_doc)
    named = [researchlog.quoted(titles[x[0]["doc_id"]], 60) for x in by_doc]
    docs_text = (named[0] if n_docs == 1 else f"{n_docs} theory documents ({', '.join(named[:-1])} and {named[-1]})"
                 if named else "no theory document")
    with ws.connect() as cx:
        if frame is not None:
            n_c = sum(len(g.concepts) for g in frame.groups)
            text = (f"The AI ({used}) read {docs_text} in {n_parts} part{'s' if n_parts != 1 else ''} for the codebook "
                    f"draft {researchlog.quoted(draft['title'], 60)}, drafted {len(numbered)} concepts and put "
                    f"together a framework of {n_c} concept{'s' if n_c != 1 else ''} in {len(frame.groups)} "
                    f"group{'s' if len(frame.groups) != 1 else ''}"
                    + (" (the answer kept from the same request before)" if reused else "")
                    + ". They are drafts: none is a code until you keep it and make the codebook.")
        elif numbered:
            text = (f"The AI ({model_used}) read {docs_text} for the codebook draft "
                    f"{researchlog.quoted(draft['title'], 60)} and drafted {len(numbered)} concepts, but could not put "
                    "them together into a framework: they are offered ungrouped, as drafts.")
        else:
            text = (f"The AI could not draft the concepts of {docs_text} for the codebook draft "
                    f"{researchlog.quoted(draft['title'], 60)}.")
        researchlog.record(cx, "codebook-drafted", text, "codebook", draft["name"], draft["title"],
                           data={"kind": KIND, "doc_ids": ids, "parts": n_parts, "parts_read": parts_read,
                                 "drafted": len(numbered), "frame_task": frame_task, "model": model_used,
                                 "ok": frame is not None, "reused": reused,
                                 "groups": len(frame.groups) if frame is not None else 0,
                                 "concepts": sum(len(g.concepts) for g in frame.groups) if frame is not None else 0})
    return {"ok": frame is not None, "stopped": False, "withdrawn": False, "state": reading["state"],
            "model": model_used, "parts": n_parts, "parts_read": parts_read, "drafted": len(numbered),
            "groups": result.get("groups", 0), "concepts": result.get("concepts", 0), "problems": reading["problems"],
            "reused": reused, "frame_task": frame_task, "discarded": written is None}


# ---------------------------------------------------------------------------------------------
# the meeting with the evidence, and a term looked up in the theory
# ---------------------------------------------------------------------------------------------
_WORD = r"[^\W\d_][\w'’-]*"
_CITED = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]|\(\s*[^\W\d_][\w’'-]+(?:\s+et al\.?|\s+(?:and|&)\s+[^\W\d_][\w’'-]+)?,?"
                    r"\s+(?:1[89]|20)\d\d[a-z]?")
EVIDENCE_POOL = 80         # the passages looked through for a concept's words
PAIR_CHARS = 480           # a sentence with the next one, when the two together hold more of the words


def _phrase_rx(phrase: str) -> re.Pattern | None:
    """A word or phrase of a concept as running text writes it: its words in order, the last with its endings
    ("skill" finds "skills", "repair knowledge" finds "repair knowledge", never "repair" alone)."""
    words = re.findall(_WORD, phrase.lower())
    if not words:
        return None
    last = words[-1]
    stem = last[:-1] if len(last) > 4 and last.endswith(("s", "e", "y")) else last
    return re.compile(r"(?<![\w'’-])" + r"[\s\-]+".join([re.escape(w) for w in words[:-1]]
                                                         + [re.escape(stem) + r"[\w'’-]{0,4}"]) + r"(?![\w'’-])", re.I)


def _poor_example(s: str) -> bool:
    """A sentence nobody would keep as an example of a concept: a question (an interview guide, a survey), a run of
    references or of a table's cells, a heading, a line of figures, a scrap."""
    w = s.split()
    if len(w) < 8 or "?" in s or s.lstrip()[:1].islower():      # (a small first letter: the tail of a sentence)
        return True
    if len(_CITED.findall(s)) >= 3 or s.count(";") >= 4 or s.count("•") >= 2 or "□" in s:
        return True
    if sum(c.isdigit() for c in s) > 0.12 * len(s) or s.rstrip()[-1:] not in ".!…”’\"')":
        return True         # figures, or a line that ends without a full stop (a table's row, a caption)
    said = Counter(x.lower().strip(".,;:()") for x in w if len(x) > 4)
    if said and said.most_common(1)[0][1] >= 4:
        return True         # a scale's cells ("Not a barrier Major barrier a barrier …")
    return sum(1 for x in w if x[:1].isupper()) > 0.6 * len(w)


def _best_span(text: str, rxs: list[tuple[str, re.Pattern]]) -> tuple[int, int, int, list[str]] | None:
    """Of a passage, the sentence (or two that follow each other) that holds the most of a concept's words:
    (score, start, end, the words found), a phrase counting double. None when no sentence that could be an example
    holds one."""
    from .textutil import split_sentences

    sents = split_sentences(text)
    best = None
    for i, (a, _z) in enumerate(sents):
        for j in (i, i + 1):
            if j >= len(sents):
                continue
            z = sents[j][1]
            s = text[a:z]
            if len(" ".join(s.split())) > (QUOTE_MAX if j == i else PAIR_CHARS) \
                    or any(_poor_example(text[x:y]) for x, y in sents[i:j + 1]):
                continue
            hit = [p for p, rx in rxs if rx.search(s)]
            score = sum(2 if " " in p else 1 for p in hit)
            if hit and (best is None or score > best[0] or (score == best[0] and z - a < best[2] - best[1])):
                best = (score, a + len(s) - len(s.lstrip()), a + len(s.rstrip()), hit)
    return best


def evidence(ws: Workspace, concept: dict, k: int = 4, skip=(), embedder=None) -> list[dict]:
    """Passages of the researcher's own documents that may show a concept, found by the words those documents use
    for it (`words`; without any, its name), no AI: of each passage the sentence that holds the most of the words,
    the passages with the most words first, one per document before a second from any, at most `k`. A word counts
    only as it is written in the field (a phrase as a phrase), and a sentence that could be no example (a question
    of an interview guide, a run of references, a table's cells) is passed over. Never from a theory or a working
    document, nor from the draft's own documents. Each {"quote", "doc_id", "title", "page", "start", "end" (in the
    document's text), "project", "passage_id", "matched" (the words found in the quote, as the field writes them),
    "marks" (where they stand in the quote: [start, end] pairs, in characters), "found_by"}. `skip`: passage ids not to offer again. With `embedder` (the project has vectors), passages found
    by meaning alone fill the places the words leave empty."""
    from .docrole import not_evidence_docs
    from .search import rank_passages

    words = _clean_words(concept.get("words")) or _clean_words([concept.get("name")])
    rxs = [(w, rx) for w in words for rx in [_phrase_rx(w)] if rx]
    if not rxs:
        return []
    draft = load(ws)
    never = not_evidence_docs(ws._conn()) | set(draft["doc_ids"] if draft else [])
    gone = {str(x) for x in skip or ()}
    try:
        found = rank_passages(ws, " ".join(words), words, k=EVIDENCE_POOL, per_doc=8, require_terms=True,
                              evidence_only=True, exclude=gone)
    except Exception:  # noqa: BLE001 - no index yet: nothing to offer
        return []
    project = ws.project_uid()

    def row(p: dict, a: int, z: int, hit: list[str], by: str) -> dict | None:
        r = ws.query("SELECT p.page, p.start, p.text, d.title FROM passages p JOIN documents d ON d.doc_id=p.doc_id "
                     "WHERE p.passage_id=?", (p["passage_id"],))
        if not r or r[0]["text"] != p["text"]:
            return None
        quote = " ".join(p["text"][a:z].split())
        # where the words stand in the quote (the page marks them: it must not match them a second way)
        marks = sorted({(m.start(), m.end()) for w, rx in rxs if w in hit for m in rx.finditer(quote)})
        marks = [list(x) for i, x in enumerate(marks) if not i or x[0] >= marks[i - 1][1]]
        return {"quote": quote, "doc_id": p["doc_id"], "title": r[0]["title"],
                "page": r[0]["page"], "start": r[0]["start"] + a, "end": r[0]["start"] + z, "project": project,
                "passage_id": p["passage_id"], "matched": hit, "marks": marks, "found_by": by}

    ranked = []
    for at, p in enumerate(found):
        if p["doc_id"] in never:
            continue
        best = _best_span(p["text"] or "", rxs)
        if best:
            ranked.append((-best[0], at, p, best))
    ranked.sort(key=lambda x: x[:2])
    out: list[dict] = []
    for second in (False, True):          # a document once, then a second passage of any
        per: set[str] = {x["doc_id"] for x in out} if not second else set()
        for _s, _at, p, (_score, a, z, hit) in ranked:
            if len(out) >= k:
                break
            if p["passage_id"] in {x["passage_id"] for x in out} or (not second and p["doc_id"] in per):
                continue
            r = row(p, a, z, hit, "keywords")
            if r:
                out.append(r)
                per.add(p["doc_id"])
    if len(out) < k and embedder is not None:
        # by meaning, where the words found too little: the definition as the question
        query = _clean(concept.get("meaning"), 1200) or _clean(concept.get("when_to_use"), 1000)
        try:
            near = rank_passages(ws, query, [], k=k * 3, per_doc=1, evidence_only=True, embedder=embedder,
                                 exclude=gone | {x["passage_id"] for x in out}) if query else []
        except Exception:  # noqa: BLE001 - its model is gone: the words' passages are what there is
            near = []
        from .textutil import split_sentences

        for p in near:
            if len(out) >= k:
                break
            if p["doc_id"] in never or p.get("found_by") == "keywords":
                continue
            t = p["text"] or ""
            first = next(((a, z) for a, z in split_sentences(t)
                          if not _poor_example(t[a:z]) and len(" ".join(t[a:z].split())) <= QUOTE_MAX), None)
            if first:
                s = t[first[0]:first[1]]
                r = row(p, first[0] + len(s) - len(s.lstrip()), first[0] + len(s.rstrip()), [], "meaning")
                if r:
                    out.append(r)
    return out


def evidence_counts(ws: Workspace, concepts: list[dict] | None = None) -> dict:
    """In how many of the researcher's own documents each concept's words are found, in a sentence that could be an
    example (as `evidence` finds them, no AI): {"documents": the evidence documents in all, "counts": {key: n}}. What
    a row of the draft says about a concept before it is opened: a concept nobody's documents speak of, and one
    they all do. `concepts`: the draft's when not given."""
    from .docrole import not_evidence_docs
    from .search import rank_passages

    draft = load(ws)
    if concepts is None:
        concepts = draft["concepts"] if draft else []
    never = not_evidence_docs(ws._conn()) | set(draft["doc_ids"] if draft else [])
    total = sum(1 for r in ws.query("SELECT doc_id FROM documents") if r["doc_id"] not in never)
    counts: dict[str, int] = {}
    for c in concepts:
        words = _clean_words(c.get("words")) or _clean_words([c.get("name")])
        rxs = [(w, rx) for w in words for rx in [_phrase_rx(w)] if rx]
        docs: set[str] = set()
        if rxs:
            try:
                found = rank_passages(ws, " ".join(words), words, k=max(EVIDENCE_POOL, 4 * total), per_doc=4,
                                      require_terms=True, evidence_only=True)
            except Exception:  # noqa: BLE001 - no index yet: nothing counted
                found = []
            for p in found:
                if p["doc_id"] not in never and p["doc_id"] not in docs and _best_span(p["text"] or "", rxs):
                    docs.add(p["doc_id"])
        counts[str(c.get("key") or "")] = len(docs)
    return {"documents": total, "counts": counts}


def lookup(ws: Workspace, doc_ids: list[str], term: str) -> dict:
    """A term in each theory document: how many of its sentences use it, and the three that best say what it means
    (`theorycodes._defining_score`; a glossary entry of that name first): {"term", "sources": [{"doc_id", "title",
    "uses", "options": [{"quote", "start", "end", "page", "score"}]}]}. Empty options: the document does not use it."""
    from . import theorycodes as tc

    term = _clean(term, 60)
    if not re.search(tc._W, term):
        raise ValueError("Say the term to look up.")
    rx = tc._term_rx(term)
    k = _norm(term)
    out = []
    for d in doc_ids:
        row = ws.query("SELECT title, text FROM documents WHERE doc_id=?", (d,))
        if not row:
            continue
        title, text = row[0]["title"] or "", row[0]["text"] or ""
        lines, _rep = tc._clean_lines(tc._body_lines(ws, d, text), text)
        sents = tc._sentences(lines, text)
        headings = ws.query("SELECT start, end, text FROM headings WHERE doc_id=? ORDER BY start", (d,))
        head_at = {(h["start"]) for h in headings}
        options = []
        for t, (a, z) in tc._glossary(lines, text, headings):
            if _norm(t) == k:
                options.append({**tc._quote(ws, d, text, a, z), "score": 10})
                break
        uses = 0
        scored = []
        for i, (a, z) in enumerate(sents):
            s = text[a:z]
            m = rx.search(s)
            if not m:
                continue
            uses += 1
            if a in head_at:
                continue
            st = s.strip()
            scored.append((-tc._defining_score(st, rx.search(st) or m), i, a + len(s) - len(s.lstrip()), z))
        for neg, _i, a, z in sorted(scored):
            if len(options) >= 3:
                break
            if any(o["start"] <= a < o["end"] for o in options):
                continue
            options.append({**tc._quote(ws, d, text, a, z), "score": -neg})
        out.append({"doc_id": d, "title": title, "uses": uses, "options": options})
    return {"term": term, "sources": out}


# ---------------------------------------------------------------------------------------------
# making the codebook
# ---------------------------------------------------------------------------------------------
def _page(s: dict) -> str:
    return f", p. {s['page']}" if s.get("page") else ""


def _description(c: dict, titles: list[str]) -> str:
    srcs = c.get("sources") or []
    also = ""
    if len(srcs) > 1:
        rest = [f"{s['title'] or 'untitled'} (p. {s['page']})" if s.get("page") else (s["title"] or "untitled")
                for s in srcs[1:]]
        also = " Also defined in " + (rest[0] if len(rest) == 1 else ", ".join(rest[:-1]) + " and " + rest[-1]) + "."
    if srcs:
        s = srcs[0]
        if c.get("meaning"):
            return f"{c['meaning']} In the theory: “{s['quote']}” ({s['title']}{_page(s)}).{also}"
        return f"“{s['quote']}” ({s['title']}{_page(s)}){'.' if also else ''}{also}"
    if c.get("meaning"):
        return c["meaning"]
    if c.get("when_to_use"):
        return c["when_to_use"]
    return "A concept of " + (titles[0] if len(titles) == 1 else ", ".join(titles[:-1]) + " and " + titles[-1]) + "."


def _code_name(name: str) -> str:
    n = _clean(name, 200)
    if len(n) > 40:
        cut = n[:40].rsplit(" ", 1)[0]
        n = cut if len(cut) >= 10 else n[:40]
    return n[:1].upper() + n[1:]


def make(ws: Workspace) -> dict:
    """The kept concepts as a codebook (`codebooks.create`, start "theory", with the framework's groups); the draft is
    then gone. Each code: its name with a capital, its meaning and the theory's words quoted with title and page as its
    description, when to use it as `include`, when not as `exclude`, the evidence's words as keywords, the kept
    examples, and an `ai_draft` mark on the fields that still hold the AI's words. Raises ValueError (a plain
    sentence) or LookupError when there is no draft."""
    from . import codebooks

    draft = load(ws)
    if draft is None:
        raise LookupError(NO_DRAFT)
    kept = [c for c in draft["concepts"] if c.get("keep")]
    if not kept:
        raise ValueError("Keep at least one concept to make the codebook.")
    names: dict[str, str] = {}
    for c in kept:
        n = _code_name(c["name"]).lower()
        if n in names:
            raise ValueError(f"Two kept concepts are called {_code_name(c['name'])!r}: give each its own name, or "
                             "leave one out.")
        names[n] = c["name"]
    titles = list(_titles(ws, draft["doc_ids"]).values()) or ["the theory"]
    groups = [{"group": g["key"], "group_name": g["name"]} for g in draft["groups"]
              if any(c.get("group") == g["key"] for c in kept)]
    at = draft["reading"].get("at") or now()
    codes = []
    for c in kept:
        desc = _description(c, titles)
        ai = c.get("ai") or {}
        drafted = {}
        if ai:
            if c.get("meaning") and c["meaning"] == ai.get("meaning"):
                drafted["description"] = desc
            if c.get("when_to_use") and c["when_to_use"] == ai.get("when_to_use"):
                drafted["include"] = c["when_to_use"]
            if c.get("when_not") and c["when_not"] == ai.get("when_not"):
                drafted["exclude"] = c["when_not"]
        code = {"code": _code_name(c["name"]), "description": desc, "group": c.get("group") or "",
                "include": c.get("when_to_use") or "", "exclude": c.get("when_not") or "",
                "keywords": list(c.get("words") or []), "examples": list(c.get("examples") or []),
                "source_docs": list(dict.fromkeys(s["doc_id"] for s in c.get("sources") or []))}
        if drafted:
            code["ai_draft"] = {"model": ai.get("model") or "", "at": at, "from": "theory", **drafted}
        codes.append(code)
    cb = codebooks.create(ws, draft["name"], draft["title"], draft["where"], "theory",
                          {"codes": codes, "doc_ids": draft["doc_ids"], "groups": groups})
    discard(ws)
    return cb
