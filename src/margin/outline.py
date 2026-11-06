"""An outline from the corpus's themes (roadmap C): a writing plan made from a set of themes, without any AI.

**C1 · the outline.** Each theme of a run becomes a section with its key terms, the passages that represent it best,
the documents to cite (APA 7 in-text citations from the bibliography, when the documents are linked to it), the codes
of a codebook and the concepts its key terms belong to. The sections come in a suggested order made from the themes
themselves: themes that share documents and key terms sit next to each other (a greedy nearest-neighbour path over
that similarity, improved by 2-opt), so the outline reads as a path rather than a list. A person reorders, nests,
merges, splits, renames and adds sections of their own (introduction, methods). Each section also shows where its
documents disagree (the checks already made: support and contradiction side by side), the gaps (few documents, one
source only) and what the person decided about the claims it touches (decisions on a draft's claims).

**C2 · the outline beside a draft.** For a draft: how much of each section the draft covers (its key terms, found in
its words, and its sources, found among the documents its citations name), and which sources and points are still
unused. With a local embedding model that is already built, the closeness by meaning of the draft's paragraphs to a
section as well (`meaning=True`; nothing leaves this computer).

**C3 · the outline as a document.** Markdown and Word (.docx, written here with `zipfile`: no library): headings,
notes, quotes with their place, citations.

The outline is stored in the project (`outlines`, `outline_sections`), keeps working when its set of themes is deleted
(the sections keep their titles and notes), and several outlines per project are fine. A theme section holds *parts*
(a theme, and optionally only some of its documents), so merging adds parts together and splitting takes them apart.
"""
from __future__ import annotations

import io
import json
import math
import re
import uuid
import zipfile
from collections import Counter, defaultdict
from xml.sax.saxutils import escape

from .store import Workspace, now

MAX_DEPTH = 3          # sections nest three levels deep at most
REPS = 4               # the passages that represent a section best
MAX_CITED = 10         # documents named in a section's citation
MAX_CHECKS = 300       # the latest checks read for disagreements and decisions
MAX_SHOWN = 6          # disagreements shown with a section
OWN_SUGGESTIONS = ("Introduction", "Methods", "Discussion", "Conclusion")
INCLUDE = ("terms", "sources", "quotes", "codes", "concepts", "disagreements", "gaps")
TITLE_CHARS = 200
NOTE_CHARS = 20_000

COVER_WORDS = (("none", "Not covered yet"), ("little", "Touched on"), ("partly", "Partly covered"),
               ("well", "Well covered"))


def _id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


# ---------------------------------------------------------------------------------------------
# the suggested order: a path through the themes
# ---------------------------------------------------------------------------------------------
def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(n * b.get(k, 0) for k, n in a.items())
    na = math.sqrt(sum(n * n for n in a.values()))
    nb = math.sqrt(sum(n * n for n in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _words(labels: list[str]) -> set[str]:
    return {w for lab in labels for w in re.findall(r"[^\W_]{3,}", lab.lower())}


def pair_similarity(a: dict, b: dict) -> float:
    """How much two themes (or sections) belong together: half the cosine of their documents' passage counts, half
    the share of key-term words they have in common (0 to 1)."""
    ta, tb = a["words"], b["words"]
    jac = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    return 0.5 * _cosine(a["docs"], b["docs"]) + 0.5 * jac


def similarity_order(items: dict) -> list:
    """The keys of `items` ({key: {"docs": Counter, "words": set}}) as a path: it starts with the theme that has the
    most passages, goes on to the most similar one not used yet each time, and is then improved by reversing stretches
    that lead to a larger total similarity between neighbours (2-opt, the first stays). The same input gives the same
    order."""
    keys = sorted(items, key=lambda k: (-sum(items[k]["docs"].values()), items[k].get("rank", 0), str(k)))
    if len(keys) < 3:
        return keys
    sim = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            sim[(a, b)] = sim[(b, a)] = pair_similarity(items[a], items[b])
    order = [keys[0]]
    left = keys[1:]
    while left:
        nxt = max(left, key=lambda k: (sim[(order[-1], k)], -keys.index(k)))
        order.append(nxt)
        left.remove(nxt)
    n = len(order)
    for _ in range(25):
        better = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b, c = order[i - 1], order[i], order[j]
                d = order[j + 1] if j + 1 < n else None
                old = sim[(a, b)] + (sim[(c, d)] if d is not None else 0.0)
                new = sim[(a, c)] + (sim[(b, d)] if d is not None else 0.0)
                if new > old + 1e-9:
                    order[i:j + 1] = reversed(order[i:j + 1])
                    better = True
        if not better:
            break
    return order


# ---------------------------------------------------------------------------------------------
# the set of themes an outline is made from
# ---------------------------------------------------------------------------------------------
class _Run:
    """A run with the person's edits applied: the themes shown and removed, and each theme's passages."""

    def __init__(self, ws: Workspace, run_id: str):
        from . import themes

        self.ws, self.run_id = ws, run_id
        row = ws.query("SELECT run_key, created_at, mode FROM theme_runs WHERE run_id=?", (run_id,))
        self.exists = bool(row)
        self.info: dict[int, dict] = {}
        self.removed: dict[int, dict] = {}
        self.members: dict[int, list[tuple[float, str, str]]] = defaultdict(list)
        self.merges: dict[int, int] = {}
        self.created_at = row[0]["created_at"] if row else None
        self.mode = row[0]["mode"] if row else None
        if not self.exists:
            return
        v = themes.view(ws, run_id)
        self.view = v
        self.info = {t["theme_id"]: t for t in v["themes"]}
        self.removed = {t["theme_id"]: t for t in v["removed"]}
        ed = themes._edits(ws, row[0]["run_key"])
        self.merges = ed["merges"]
        self._final = lambda t: themes._final(ed["merges"], t)
        for m in ws.query("SELECT m.theme_id, m.passage_id, m.similarity, p.doc_id FROM theme_members m "
                          "JOIN passages p ON p.passage_id=m.passage_id WHERE m.run_id=?", (run_id,)):
            moved = ed["moves"].get(m["passage_id"])
            tid = self._final(moved if moved is not None else m["theme_id"])
            self.members[tid].append((float(m["similarity"] or 0), m["passage_id"], m["doc_id"]))

    def final(self, tid: int) -> int:
        return self._final(tid) if self.exists else tid

    def theme(self, tid: int) -> tuple[dict | None, str]:
        """(the theme now standing for `tid`, its state: 'shown', 'removed' or 'gone')."""
        t = self.final(tid)
        if t in self.info:
            return self.info[t], "shown"
        if t in self.removed:
            return self.removed[t], "removed"
        return None, "gone"


def _item(run: _Run, parts: list[dict]) -> dict:
    """What orders a section: its documents (passage counts) and the words of its key terms."""
    docs: Counter = Counter()
    labels: list[str] = []
    for p in parts:
        t, state = run.theme(p["theme"])
        if state != "shown":
            continue
        want = set(p["docs"]) if p.get("docs") else None
        for d in t["documents"]:
            if want is None or d["doc_id"] in want:
                docs[d["doc_id"]] += d["passages"]
        labels += t["terms"]
    # `rank` breaks ties the same way whatever order the sections are given in: the smallest theme id of the section
    return {"docs": docs, "words": _words(labels), "rank": min((p["theme"] for p in parts), default=0)}


# ---------------------------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------------------------
def _outline_row(ws: Workspace, oid: str) -> dict:
    r = ws.query("SELECT * FROM outlines WHERE outline_id=?", (oid,))
    if not r:
        raise KeyError(oid)
    return dict(r[0])


def _sections(ws: Workspace, oid: str) -> list[dict]:
    out = []
    for r in ws.query("SELECT * FROM outline_sections WHERE outline_id=? ORDER BY seq, rowid", (oid,)):
        d = dict(r)
        d["parts"] = json.loads(d.pop("parts_json") or "[]")
        out.append(d)
    return out


def _section(ws: Workspace, oid: str, sid: str) -> dict:
    for s in _sections(ws, oid):
        if s["section_id"] == sid:
            return s
    raise KeyError(sid)


def _touch(cx, oid: str) -> None:
    cx.execute("UPDATE outlines SET updated_at=? WHERE outline_id=?", (now(), oid))


def _clean_title(title, required: bool = True) -> str | None:
    t = " ".join(str(title or "").split())[:TITLE_CHARS]
    if required and not t:
        raise ValueError("Give the section a title.")
    return t or None


def _clean_note(note) -> str:
    return "\n".join(line.rstrip() for line in str(note or "").replace("\r\n", "\n").split("\n")).strip()[:NOTE_CHARS]


def _part(theme: int, docs=None) -> dict:
    return {"theme": int(theme), "docs": sorted(docs) if docs else None}


def _put_order(cx, oid: str, parent: str | None, ids: list[str]) -> None:
    for i, sid in enumerate(ids):
        cx.execute("UPDATE outline_sections SET parent_id=?, seq=? WHERE outline_id=? AND section_id=?",
                   (parent, i, oid, sid))


def _siblings(cx, oid: str, parent: str | None) -> list[str]:
    q = ("SELECT section_id FROM outline_sections WHERE outline_id=? AND parent_id IS NULL ORDER BY seq, rowid"
         if parent is None else
         "SELECT section_id FROM outline_sections WHERE outline_id=? AND parent_id=? ORDER BY seq, rowid")
    return [r[0] for r in cx.execute(q, (oid,) if parent is None else (oid, parent))]


# ---------------------------------------------------------------------------------------------
# making and changing an outline
# ---------------------------------------------------------------------------------------------
def create(ws: Workspace, run_id: str, title: str | None = None, framework: str | None = None,
           order: str = "similarity") -> str:
    """An outline with one section per theme shown in the run. `order`: 'similarity' (the suggested path) or
    'size' (the largest theme first, as the Themes page lists them)."""
    run = _Run(ws, run_id)
    if not run.exists:
        raise KeyError(run_id)
    shown = [t["theme_id"] for t in run.view["themes"]]
    if not shown:
        raise ValueError("This set of themes has no theme shown. Bring one back, or find the themes again.")
    if order not in ("similarity", "size"):
        raise ValueError("order must be similarity or size.")
    keys = (similarity_order({t: _item(run, [_part(t)]) for t in shown}) if order == "similarity" else shown)
    oid = _id("o")
    title = _clean_title(title, required=False) or f"Outline of {len(shown)} themes, {(run.created_at or now())[:10]}"
    stamp = now()
    with ws.connect() as cx:
        cx.execute("INSERT INTO outlines(outline_id, title, run_id, framework, created_at, updated_at) "
                   "VALUES (?,?,?,?,?,?)", (oid, title, run_id, framework or None, stamp, stamp))
        for i, t in enumerate(keys):
            cx.execute("INSERT INTO outline_sections(section_id, outline_id, parent_id, seq, kind, parts_json, title, "
                       "note, created_at) VALUES (?,?,NULL,?,'theme',?,NULL,'',?)",
                       (_id("s"), oid, i, json.dumps([_part(t)]), stamp))
    return oid


def update(ws: Workspace, oid: str, title=None, framework=None) -> None:
    """Rename an outline, or choose the codebook its sections show the codes of ('' for none)."""
    _outline_row(ws, oid)
    with ws.connect() as cx:
        if title is not None:
            cx.execute("UPDATE outlines SET title=? WHERE outline_id=?", (_clean_title(title), oid))
        if framework is not None:
            cx.execute("UPDATE outlines SET framework=? WHERE outline_id=?", (str(framework) or None, oid))
        _touch(cx, oid)


def delete(ws: Workspace, oid: str) -> None:
    _outline_row(ws, oid)
    with ws.connect() as cx:
        cx.execute("DELETE FROM outline_sections WHERE outline_id=?", (oid,))
        cx.execute("DELETE FROM outlines WHERE outline_id=?", (oid,))


def _depth(rows: dict[str, dict], sid: str | None) -> int:
    """How many sections are above `sid` (0 for a top-level section; -1 for the outline itself)."""
    d = -1
    while sid is not None and sid in rows:
        d += 1
        sid = rows[sid]["parent_id"]
    return d


def _height(rows: dict[str, dict], sid: str) -> int:
    kids = [r["section_id"] for r in rows.values() if r["parent_id"] == sid]
    return 1 + max((_height(rows, k) for k in kids), default=-1) if kids else 0


def _inside(rows: dict[str, dict], sid: str, outer: str) -> bool:
    """Whether `sid` is `outer` or one of the sections below it."""
    seen = set()
    while sid is not None and sid in rows and sid not in seen:
        if sid == outer:
            return True
        seen.add(sid)
        sid = rows[sid]["parent_id"]
    return False


def add_section(ws: Workspace, oid: str, title: str | None = None, note: str = "", parent_id: str | None = None,
                index: int | None = None, theme_id: int | None = None) -> str:
    """A section of your own (an introduction, the methods), or - with `theme_id` - a theme of the set that the
    outline does not hold (any more). Placed in `parent_id` (None: top level) at `index` (None: last)."""
    o = _outline_row(ws, oid)
    rows = {s["section_id"]: s for s in _sections(ws, oid)}
    if parent_id is not None and parent_id not in rows:
        raise KeyError(parent_id)
    if _depth(rows, parent_id) + 1 > MAX_DEPTH - 1:
        raise ValueError("Sections can be nested three levels deep at most.")
    if theme_id is not None:
        run = _Run(ws, o["run_id"])
        if not run.exists or int(theme_id) not in run.info:
            raise ValueError("Choose one of the themes shown in the set the outline comes from.")
        kind, parts, title = "theme", [_part(theme_id)], _clean_title(title, required=False)
    else:
        kind, parts, title = "own", [], _clean_title(title)
    sid = _id("s")
    with ws.connect() as cx:
        cx.execute("INSERT INTO outline_sections(section_id, outline_id, parent_id, seq, kind, parts_json, title, note, "
                   "created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (sid, oid, parent_id, 10 ** 6, kind, json.dumps(parts), title, _clean_note(note), now()))
        sibs = [x for x in _siblings(cx, oid, parent_id) if x != sid]
        sibs.insert(len(sibs) if index is None else max(0, min(int(index), len(sibs))), sid)
        _put_order(cx, oid, parent_id, sibs)
        _touch(cx, oid)
    return sid


def update_section(ws: Workspace, oid: str, sid: str, title=None, note=None) -> None:
    """Rename a section ('' for a theme section: back to its theme's own heading) or change its note."""
    s = _section(ws, oid, sid)
    with ws.connect() as cx:
        if title is not None:
            cx.execute("UPDATE outline_sections SET title=? WHERE section_id=?",
                       (_clean_title(title, required=s["kind"] == "own"), sid))
        if note is not None:
            cx.execute("UPDATE outline_sections SET note=? WHERE section_id=?", (_clean_note(note), sid))
        _touch(cx, oid)


def delete_section(ws: Workspace, oid: str, sid: str) -> None:
    """Take a section out; the sections inside it move up into its place. A theme can be added again."""
    s = _section(ws, oid, sid)
    with ws.connect() as cx:
        sibs = _siblings(cx, oid, s["parent_id"])
        kids = _siblings(cx, oid, sid)
        at = sibs.index(sid)
        cx.execute("DELETE FROM outline_sections WHERE section_id=?", (sid,))
        _put_order(cx, oid, s["parent_id"], sibs[:at] + kids + sibs[at + 1:])
        _touch(cx, oid)


def move(ws: Workspace, oid: str, sid: str, parent_id: str | None, index: int | None = None) -> None:
    """Put a section (with the sections inside it) under `parent_id` (None: top level) at position `index`
    (None: last). Reordering, nesting and un-nesting are all this."""
    rows = {s["section_id"]: s for s in _sections(ws, oid)}
    if sid not in rows:
        raise KeyError(sid)
    if parent_id is not None:
        if parent_id not in rows:
            raise KeyError(parent_id)
        if _inside(rows, parent_id, sid):
            raise ValueError("A section cannot go inside itself.")
    if _depth(rows, parent_id) + 1 + _height(rows, sid) > MAX_DEPTH - 1:
        raise ValueError("Sections can be nested three levels deep at most.")
    old = rows[sid]["parent_id"]
    with ws.connect() as cx:
        if old != parent_id:
            _put_order(cx, oid, old, [x for x in _siblings(cx, oid, old) if x != sid])
        sibs = [x for x in _siblings(cx, oid, parent_id) if x != sid]
        sibs.insert(len(sibs) if index is None else max(0, min(int(index), len(sibs))), sid)
        _put_order(cx, oid, parent_id, sibs)
        _touch(cx, oid)


def merge(ws: Workspace, oid: str, sid: str, into: str) -> None:
    """Join a section to another: the other keeps its title and position, gains this one's themes (parts), notes and
    the sections inside it."""
    rows = {s["section_id"]: s for s in _sections(ws, oid)}
    if sid not in rows:
        raise KeyError(sid)
    if into not in rows:
        raise KeyError(into)
    if sid == into:
        raise ValueError("Choose two different sections.")
    if _inside(rows, into, sid):
        raise ValueError("Choose a section that is not inside this one.")
    a, b = rows[sid], rows[into]
    if _depth(rows, into) + _height(rows, sid) > MAX_DEPTH - 1:
        raise ValueError("Sections can be nested three levels deep at most.")
    parts = list(b["parts"])
    for p in a["parts"]:
        if p not in parts:
            parts.append(p)
    note = "\n\n".join(x for x in (b["note"], a["note"]) if x)
    with ws.connect() as cx:
        kids = _siblings(cx, oid, sid)
        cx.execute("UPDATE outline_sections SET parts_json=?, note=?, kind=? WHERE section_id=?",
                   (json.dumps(parts), note[:NOTE_CHARS], "theme" if parts else "own", into))
        _put_order(cx, oid, a["parent_id"], [x for x in _siblings(cx, oid, a["parent_id"]) if x != sid])
        cx.execute("DELETE FROM outline_sections WHERE section_id=?", (sid,))
        _put_order(cx, oid, into, _siblings(cx, oid, into) + kids)
        _touch(cx, oid)


def split(ws: Workspace, oid: str, sid: str, doc_ids: list[str] | None = None) -> list[str]:
    """Take a section apart. One made of several themes becomes one section per theme (the first stays where it is,
    the others follow it). A section of one theme is split by documents: `doc_ids` go to a new section after it."""
    o = _outline_row(ws, oid)
    s = _section(ws, oid, sid)
    if not s["parts"]:
        raise ValueError("A section of your own has no themes to split.")
    new_ids = []
    stamp = now()
    if len(s["parts"]) >= 2:
        groups = [[p] for p in s["parts"]]
    else:
        run = _Run(ws, o["run_id"])
        t, state = run.theme(s["parts"][0]["theme"])
        if state != "shown":
            raise ValueError("Its theme is not shown any more, so its documents cannot be told apart.")
        part = s["parts"][0]
        have = {d["doc_id"] for d in t["documents"] if not part["docs"] or d["doc_id"] in part["docs"]}
        pick = set(doc_ids or [])
        if not pick or not pick <= have or pick == have:
            raise ValueError("Choose some of the section's documents, but not all of them, for the new section.")
        groups = [[_part(part["theme"], have - pick)], [_part(part["theme"], pick)]]
    with ws.connect() as cx:
        cx.execute("UPDATE outline_sections SET parts_json=? WHERE section_id=?", (json.dumps(groups[0]), sid))
        sibs = _siblings(cx, oid, s["parent_id"])
        at = sibs.index(sid) + 1
        for g in groups[1:]:
            nid = _id("s")
            cx.execute("INSERT INTO outline_sections(section_id, outline_id, parent_id, seq, kind, parts_json, title, "
                       "note, created_at) VALUES (?,?,?,?,?,?,NULL,'',?)",
                       (nid, oid, s["parent_id"], 10 ** 6, "theme", json.dumps(g), stamp))
            sibs.insert(at, nid)
            at += 1
            new_ids.append(nid)
        _put_order(cx, oid, s["parent_id"], sibs)
        _touch(cx, oid)
    if len(groups) == 2 and len(s["parts"]) == 1:   # two halves of one theme need telling apart
        run = _Run(ws, o["run_id"])
        name = _heading(run.theme(s["parts"][0]["theme"])[0])[0]
        with ws.connect() as cx:
            if not s["title"]:
                cx.execute("UPDATE outline_sections SET title=? WHERE section_id=?", (f"{name} (part 1)", sid))
            cx.execute("UPDATE outline_sections SET title=? WHERE section_id=?", (f"{name} (part 2)", new_ids[0]))
    return new_ids


def reorder(ws: Workspace, oid: str) -> int:
    """Suggest the order again: the theme sections at the top level take the places of the theme sections there, in
    the order of the similarity path; sections of your own and nested sections stay where they are. Returns how many
    sections moved."""
    o = _outline_row(ws, oid)
    run = _Run(ws, o["run_id"])
    if not run.exists:
        raise ValueError("The set of themes was deleted, so there is nothing to order by.")
    rows = _sections(ws, oid)
    top = [s for s in rows if s["parent_id"] is None]
    movable = [s for s in top if s["parts"] and all(run.theme(p["theme"])[1] == "shown" for p in s["parts"])]
    if len(movable) < 2:
        return 0
    items = {s["section_id"]: _item(run, s["parts"]) for s in movable}
    path = similarity_order(items)
    slots = [i for i, s in enumerate(top) if s in movable]
    new = [s["section_id"] for s in top]
    for i, sid in zip(slots, path):
        new[i] = sid
    changed = sum(1 for a, b in zip([s["section_id"] for s in top], new) if a != b)
    with ws.connect() as cx:
        _put_order(cx, oid, None, new)
        _touch(cx, oid)
    return changed


# ---------------------------------------------------------------------------------------------
# what a section shows
# ---------------------------------------------------------------------------------------------
def _heading(t: dict | None) -> tuple[str, str]:
    """A theme's heading and where it comes from: the AI's name or a person's rename when there is one, else its
    first key terms written out ("Electrolysis, hydrogen and cost")."""
    if not t:
        return "A theme that is gone", "gone"
    if t.get("name_source") in ("model", "person"):
        return t["name"], t["name_source"]
    words = [w for w in (t.get("terms") or [])[:3] if w]
    if not words:
        return t["name"], "terms"
    text = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    return text[0].upper() + text[1:], "terms"


def _passage_rows(ws: Workspace, ids: list[str]) -> dict[str, dict]:
    from .claimcheck import locate

    if not ids:
        return {}
    where = locate(ws, [(p, p, None) for p in ids])
    out = {}
    for p in ws.query(f"SELECT p.passage_id, p.doc_id, p.page, p.text, p.start, p.end, d.title FROM passages p JOIN "
                      f"documents d ON d.doc_id=p.doc_id WHERE p.passage_id IN ({','.join('?' * len(ids))})", ids):
        out[p["passage_id"]] = {"passage_id": p["passage_id"], "doc_id": p["doc_id"], "title": p["title"] or "",
                                "page": p["page"], "text": p["text"], "start": p["start"], "end": p["end"],
                                "location": (where.get(p["passage_id"]) or {}).get("span") or ""}
    return out


def _pick(passages: list[tuple[float, str, str]], n: int) -> list[str]:
    """The n passages nearest the heart of the section, one per document first."""
    ranked = sorted(passages, key=lambda x: (-x[0], x[1]))
    chosen, seen = [], set()
    for sim, pid, doc in ranked:
        if doc not in seen:
            seen.add(doc)
            chosen.append(pid)
        if len(chosen) >= n:
            return chosen
    for sim, pid, doc in ranked:
        if pid not in chosen:
            chosen.append(pid)
        if len(chosen) >= n:
            break
    return chosen


def _concepts(ws: Workspace, labels: list[str]) -> list[dict]:
    """The concepts (terms joined by 'same' links) that the key terms belong to, with the other wordings."""
    if not labels:
        return []
    ids = {r["term_id"]: r["label"] for r in ws.query(
        f"SELECT term_id, label FROM terms WHERE label IN ({','.join('?' * len(labels))})", labels)}
    if not ids:
        return []
    cid = {r["term_id"]: r["concept_id"] for r in ws.query(
        f"SELECT term_id, concept_id FROM concept_terms WHERE term_id IN ({','.join('?' * len(ids))})", list(ids))}
    out, seen = [], set()
    for lab in labels:
        tid = next((t for t, l in ids.items() if l == lab and t in cid), None)
        if tid is None or cid[tid] in seen:
            continue
        seen.add(cid[tid])
        c = ws.query("SELECT label FROM concepts WHERE concept_id=?", (cid[tid],))
        wordings = [r["label"] for r in ws.query(
            "SELECT t.label FROM concept_terms ct JOIN terms t ON t.term_id=ct.term_id WHERE ct.concept_id=? "
            "ORDER BY t.tf DESC", (cid[tid],))]
        out.append({"concept_id": cid[tid], "term_id": tid, "label": c[0]["label"] if c else lab,
                    "wordings": wordings[:6]})
    return out[:6]


class _Checks:
    """The checks already made, read once: for each hypothesis its answer, who is on each side, and (when it is a
    claim of a draft) the person's decision. Only the latest MAX_CHECKS that touch the outline's documents."""

    def __init__(self, ws: Workspace, docs: set[str], cites: dict, threshold: float | None):
        from . import claimcheck, drafts

        self.items: list[dict] = []
        if not docs:
            return
        cache = claimcheck.ResultCache(ws, threshold)
        ids = [r[0] for r in ws.query(
            "SELECT uc.hyp_id FROM verifications v JOIN user_claims uc ON uc.claim_id=v.subject_id "
            "JOIN hypotheses h ON h.hyp_id=uc.hyp_id WHERE v.subject_kind='user_claim' AND v.doc_id IN "
            f"({','.join('?' * len(docs))}) AND COALESCE(v.user_verdict, v.verdict) IN "
            "('supports','partially_supports','refutes') AND COALESCE(h.origin, '') != 'citation' "
            "GROUP BY uc.hyp_id ORDER BY MAX(h.created_at) DESC LIMIT ?", [*docs, MAX_CHECKS])]
        claim_of = {}
        if ids:
            for r in ws.query("SELECT dc.hyp_id, dc.claim_id, dc.draft_id, dc.decision, dc.claim, dc.quote, d.title "
                              "FROM draft_claims dc JOIN drafts d ON d.draft_id=dc.draft_id WHERE dc.hyp_id IN "
                              f"({','.join('?' * len(ids))})", ids):
                claim_of[r["hyp_id"]] = dict(r)
        for hid in ids:
            try:
                res = cache.result(hid)
            except KeyError:
                continue
            ev = drafts._evidence(res, cites)
            sides = {k: {e["doc_id"] for e in v} for k, v in ev.items()}
            self.items.append({"hyp_id": hid, "res": res, "ev": ev, "sides": sides, "draft": claim_of.get(hid)})

    def for_section(self, docs: set[str]) -> tuple[list[dict], list[dict]]:
        """(where the section's documents disagree, what the person decided about claims they touch)."""
        from . import drafts

        dis, dec = [], []
        for it in self.items:
            s = it["sides"]
            pro, con = s["supports"] | s["partly"], s["refutes"]
            if not (docs & (pro | con)):
                continue
            inside = bool(docs & pro) and bool(docs & con)
            across = not inside and ((docs & pro and con) or (docs & con and pro))
            d = it["draft"]
            if inside or across:
                res = it["res"]

                def side(entries):
                    return [{"doc_id": e["doc_id"], "title": e["title"], "location": e["location"] or
                             (e["locations"][0] if e["locations"] else ""), "quote": e["quote"],
                             "apa": (e["apa"] or {}).get("text"), "inside": e["doc_id"] in docs} for e in entries]

                dis.append({"hyp_id": it["hyp_id"], "claim": d["claim"] if d and d["claim"] else res["text"],
                            "status": res["status"], "status_text": res["status_text"],
                            "tier": "inside" if inside else "across",
                            "supports": side(it["ev"]["supports"] + it["ev"]["partly"]),
                            "refutes": side(it["ev"]["refutes"])})
            if d and d["decision"]:
                dec.append({"hyp_id": it["hyp_id"], "claim_id": d["claim_id"], "draft_id": d["draft_id"],
                            "draft": d["title"], "claim": d["claim"] or d["quote"], "decision": d["decision"],
                            "decision_text": drafts.DECISION_TEXT.get(d["decision"], d["decision"]),
                            "status_text": it["res"]["status_text"]})
        dis.sort(key=lambda x: (x["tier"] != "inside", x["hyp_id"]))
        return dis[:MAX_SHOWN], dec[:MAX_SHOWN]


def _gaps(kind: str, passages: int, docs: Counter, titles: dict) -> list[dict]:
    if kind == "own":
        return []
    n = len(docs)
    out = []
    if n == 0:
        out.append({"kind": "none", "text": "No document stands behind this section."})
    elif n == 1:
        out.append({"kind": "one-source", "text": f"One source only: {titles.get(next(iter(docs)), 'a document')}."})
    elif n == 2:
        out.append({"kind": "few", "text": "Only two sources."})
    if n >= 3:
        top, cnt = docs.most_common(1)[0]
        if cnt / max(1, passages) >= 0.8:
            out.append({"kind": "mostly-one", "text": f"Mostly one source: {titles.get(top, 'a document')} "
                                                       f"({round(100 * cnt / passages)}% of the passages)."})
    if 0 < passages < 5:
        out.append({"kind": "thin", "text": f"Few passages ({passages})."})
    return out


def _build(ws: Workspace, o: dict, rows: list[dict], framework: str | None, threshold: float | None) -> tuple:
    from . import bibliography, frameworks, profile

    run = _Run(ws, o["run_id"])
    cites = bibliography.apa_citations(ws) if bibliography.has(ws) else {}
    titles = {r["doc_id"]: r["title"] or "" for r in ws.query("SELECT doc_id, title FROM documents")}
    fw_name = framework if framework is not None else (o["framework"] or "")
    codes_of: dict[str, list[dict]] | None = None
    fw = None
    if fw_name:
        try:
            fw = frameworks.get(fw_name, ws)
            by_pid: dict[str, list[str]] = defaultdict(list)
            for lb in profile.effective(ws, fw_name):
                by_pid[lb["passage_id"]].append(lb["code"])
            codes_of = by_pid
        except (KeyError, ValueError):
            fw, codes_of = None, None
    desc = {c.code: c.description for c in fw.sorted_codes()} if fw else {}

    built: dict[str, dict] = {}
    all_docs: set[str] = set()
    for s in rows:
        passages: dict[str, tuple[float, str, str]] = {}
        labels: list[str] = []
        names, states = [], []
        for p in s["parts"]:
            t, state = run.theme(p["theme"])
            states.append(state)
            if t is None:
                names.append({"theme_id": p["theme"], "name": "A theme that is gone", "state": state})
                continue
            names.append({"theme_id": t["theme_id"], "name": t["name"], "state": state,
                          "only_documents": len(p["docs"]) if p["docs"] else None})
            if state != "shown":
                continue
            want = set(p["docs"]) if p["docs"] else None
            for m in run.members.get(t["theme_id"], []):
                if want is None or m[2] in want:
                    passages[m[1]] = m
            labels += [w for w in t["terms"] if w not in labels]
        docs = Counter(m[2] for m in passages.values())
        all_docs |= set(docs)
        built[s["section_id"]] = {"passages": passages, "labels": labels, "docs": docs, "names": names,
                                  "states": states, "row": s}

    checks = _Checks(ws, all_docs, cites, threshold)
    reps = _passage_rows(ws, [pid for b in built.values() for pid in _pick(list(b["passages"].values()), REPS)])
    out: dict[str, dict] = {}
    for sid, b in built.items():
        s = b["row"]
        docs: Counter = b["docs"]
        first, state = (run.theme(s["parts"][0]["theme"]) if s["parts"] else (None, "own"))
        default, source = (_heading(first) if s["parts"] else ("", "own"))
        if s["parts"] and len(s["parts"]) > 1 and first is None:
            default, source = "Themes that are gone", "gone"
        title = s["title"] or default
        # key terms: those of the theme(s); a part of a theme keeps the terms found in its documents
        labels = b["labels"]
        if any(p["docs"] for p in s["parts"]) and labels:
            from . import terms as terms_

            ids = {r["term_id"]: r["label"] for r in ws.query(
                f"SELECT term_id, label FROM terms WHERE label IN ({','.join('?' * len(labels))})", labels)}
            there = terms_.terms_in_docs(ws, list(ids), docs)
            kept = [lab for lab in labels if any(t in there for t, l in ids.items() if l == lab)]
            labels = kept or labels
        top = _pick(list(b["passages"].values()), REPS)
        sources = []
        for d, n in docs.most_common():
            a = cites.get(d) or {}
            sources.append({"doc_id": d, "title": titles.get(d, ""), "passages": n, "apa": a.get("text"),
                            "narrative": a.get("narrative")})
        cited = [cites[x["doc_id"]] for x in sources[:MAX_CITED] if x["doc_id"] in cites]
        together = bibliography.apa_together(cited)
        dset = set(docs)
        dis, dec = checks.for_section(dset) if dset else ([], [])
        n_pass = len(b["passages"])
        codes = None
        if codes_of is not None:
            c: Counter = Counter()
            for pid in b["passages"]:
                c.update(set(codes_of.get(pid, ())))
            codes = [{"code": k, "description": desc.get(k, ""), "passages": n} for k, n in c.most_common(8)]
        out[sid] = {
            "section_id": sid, "kind": s["kind"], "title": title, "title_source": "you" if s["title"] else source,
            "default_title": default, "note": s["note"], "themes": b["names"], "state": (
                "own" if not s["parts"] else "gone" if all(x == "gone" for x in b["states"]) else
                "removed" if "removed" in b["states"] and "shown" not in b["states"] else "shown"),
            "passages": n_pass, "documents": len(docs), "terms": labels[:12],
            "representatives": [{**reps[p], "similarity": round(b["passages"][p][0], 3),
                                 "apa": (cites.get(reps[p]["doc_id"]) or {}).get("text")}
                                for p in top if p in reps],
            "sources": sources, "cite": ({"text": together["text"], "html": together["html"],
                                          "count": together["count"],
                                          "more": max(0, len(sources) - MAX_CITED),
                                          "missing": sum(1 for x in sources[:MAX_CITED] if not x["apa"])}
                                         if together else
                                         ({"text": None, "missing": min(len(sources), MAX_CITED), "more": 0}
                                          if sources else None)),
            "codes": codes, "concepts": _concepts(ws, labels), "disagreements": dis, "decisions": dec,
            "gaps": _gaps(s["kind"], n_pass, docs, titles),
            "parts": s["parts"], "split_by_documents": any(p["docs"] for p in s["parts"]),
            "can_split": bool(s["parts"]) and (len(s["parts"]) > 1 or len(docs) > 1),
            "_docs": dset, "_words": _words(labels)}
    return run, out, cites, titles


def view(ws: Workspace, oid: str, framework: str | None = None, threshold: float | None = None) -> dict:
    """The outline as a tree of sections for its page and its downloads. `framework`: the codebook whose codes each
    section shows (default: the outline's own choice)."""
    o = _outline_row(ws, oid)
    rows = _sections(ws, oid)
    run, built, cites, titles = _build(ws, o, rows, framework, threshold)
    by_parent: dict[str | None, list[dict]] = defaultdict(list)
    ids = {s["section_id"] for s in rows}
    for s in rows:
        by_parent[s["parent_id"] if s["parent_id"] in ids else None].append(s)

    def tree(parent, prefix, depth):
        out = []
        sibs = by_parent.get(parent, [])
        for i, s in enumerate(sorted(sibs, key=lambda x: x["seq"])):
            b = dict(built[s["section_id"]])
            num = f"{prefix}{i + 1}"
            b.update(number=num, depth=depth, parent_id=parent, index=i, siblings=len(sibs))
            b["children"] = tree(s["section_id"], num + ".", depth + 1)
            out.append(b)
        return out

    top = tree(None, "", 0)

    def link(nodes):   # what a section shares with the one after it: the path from one to the next
        for a, b in zip(nodes, nodes[1:]):
            if a["_docs"] and b["_docs"]:
                a["link_to_next"] = {"documents": len(a["_docs"] & b["_docs"]),
                                     "terms": sorted(a["_words"] & b["_words"])[:5]}
        for n in nodes:
            link(n["children"])
    link(top)

    def strip(nodes):
        for n in nodes:
            n.pop("_docs", None)
            n.pop("_words", None)
            strip(n["children"])
    flat_ids: set[int] = set()

    def count(nodes):
        for n in nodes:
            for t in n["themes"]:
                flat_ids.add(run.final(t["theme_id"]))
            count(n["children"])
    count(top)
    strip(top)
    available = [{"theme_id": t["theme_id"], "name": _heading(t)[0], "size": t["size"],
                  "documents": len(t["documents"])} for t in (run.view["themes"] if run.exists else [])
                 if t["theme_id"] not in flat_ids]
    n_sections = len(rows)
    return {"outline": {"outline_id": oid, "title": o["title"], "run_id": o["run_id"], "framework": o["framework"] or "",
                        "created_at": o["created_at"], "updated_at": o["updated_at"], "sections": n_sections,
                        "bibliography": bool(cites)},
            "run": ({"run_id": o["run_id"], "created_at": run.created_at, "mode": run.mode,
                     "stale": run.view["run"]["stale"]} if run.exists else None),
            "sections": top, "available_themes": available, "own_suggestions": list(OWN_SUGGESTIONS),
            "max_depth": MAX_DEPTH, "framework_missing": bool(o["framework"]) and all(
                s["codes"] is None for s in built.values()) and bool(built)}


def list_outlines(ws: Workspace) -> list[dict]:
    out = []
    for r in ws.query("SELECT o.*, (SELECT COUNT(*) FROM outline_sections s WHERE s.outline_id=o.outline_id) AS n, "
                      "(SELECT created_at FROM theme_runs t WHERE t.run_id=o.run_id) AS run_created "
                      "FROM outlines o ORDER BY o.updated_at DESC, o.rowid DESC"):
        out.append({"outline_id": r["outline_id"], "title": r["title"], "run_id": r["run_id"], "sections": r["n"],
                    "created_at": r["created_at"], "updated_at": r["updated_at"], "run_exists": bool(r["run_created"]),
                    "run_created_at": r["run_created"]})
    return out


# ---------------------------------------------------------------------------------------------
# C2: the outline beside a draft
# ---------------------------------------------------------------------------------------------
def _stems(text: str) -> list[str]:
    from .textutil import token_spans

    return [t[2] for t in token_spans(text, keep_stop=True)]   # stop words stay: the glossary's terms hold them


def _grams(stems: list[str], sizes: set[int]) -> Counter:
    c: Counter = Counter()
    for n in sizes:
        for i in range(len(stems) - n + 1):
            c[" ".join(stems[i:i + n])] += 1
    return c


def _paragraphs(text: str) -> list[tuple[int, int]]:
    """The blocks of the draft (separated by blank lines), numbered 1, 2, … as a reader counts them."""
    return [(m.start(), m.end()) for m in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, re.S)]


def _long(text: str, span: tuple[int, int]) -> bool:
    """Headings and one-line blocks say too little to be compared with a section."""
    return len(text[span[0]:span[1]].split()) >= 4


def _draft_sources(ws: Workspace, draft_id: str) -> tuple[set[str], int]:
    """The documents the draft's own citations name (a citation of a work of the bibliography that is a document of
    the project), and how many citations were read."""
    from . import drafts

    tid = drafts.citation_text(ws, draft_id, create=False)
    if not tid:
        return set(), 0
    n = int(ws.scalar("SELECT COUNT(*) FROM citations WHERE text_id=?", (tid,)) or 0)
    docs = {r[0] for r in ws.query(
        "SELECT DISTINCT l.doc_id FROM cite_refs r JOIN bib_links l ON l.item_key=r.item_key WHERE r.text_id=? AND "
        "r.ignored=0 AND l.status IN ('auto','confirmed')", (tid,))}
    return docs, n


def _meaning(ws: Workspace, draft_text: str, paras: list[tuple[int, int]], sections: dict[str, list[str]],
             settings: dict | None) -> dict:
    """Level 1, only when asked: the closeness of each section's passages (their vectors' mean) to the draft's
    paragraphs, with the embedding model that built the project's vectors, when it is on this computer."""
    from . import embed, home

    out: dict = {"available": False, "why": ""}
    emb = home.make_embedder(settings or home.load_settings())
    if emb is None:
        out["why"] = "Search by meaning is not set up: choose an embedding model under Settings."
        return out
    if embed.remote(emb):
        out["why"] = "The embedding model is on another computer, so the draft is not sent to it."
        return out
    vs = embed.vectors(ws, emb.model)
    if vs is None:
        out["why"] = "The documents have no vectors from this model yet: build the index for search by meaning first."
        return out
    numbered = [(i + 1, sp) for i, sp in enumerate(paras) if _long(draft_text, sp)][:300]
    if not numbered:
        out["why"] = "The draft has no paragraphs to read."
        return out
    _q, dprefix = embed.prefixes(emb.model)
    chosen = [sp for _n, sp in numbered]
    vecs = []
    for i in range(0, len(chosen), 32):
        vecs += [embed._unit(v) for v in emb.embed([dprefix + draft_text[a:b][:2000] for a, b in chosen[i:i + 32]])]
    res = {}
    for sid, pids in sections.items():
        idx = [vs.pos[p] for p in pids if p in vs.pos]
        if not idx:
            continue
        if vs.np is not None:
            c = vs.matrix[idx].mean(axis=0)
            c = c / (float((c * c).sum()) ** 0.5 or 1.0)
            sims = [float(vs.np.dot(c, vs.np.asarray(v, dtype=vs.np.float32))) for v in vecs]
        else:
            rows = [vs.rows[i] for i in idx]
            c = [sum(r[k] for r in rows) / len(rows) for k in range(len(rows[0]))]
            nrm = math.sqrt(sum(x * x for x in c)) or 1.0
            sims = [sum(x / nrm * y for x, y in zip(c, v)) for v in vecs]
        best = max(range(len(sims)), key=lambda i: sims[i])
        res[sid] = {"closeness": round(max(0.0, sims[best]), 3), "paragraph": numbered[best][0],
                    "excerpt": draft_text[chosen[best][0]:chosen[best][1]][:240]}
    return {"available": True, "model": emb.model, "sections": res}


def compare(ws: Workspace, oid: str, draft_id: str, meaning: bool = False, settings: dict | None = None,
            threshold: float | None = None) -> dict:
    """The outline beside a draft: for each section how much of it the draft covers, and what is still unused."""
    from . import drafts

    d = drafts._row(ws, draft_id)
    v = view(ws, oid, threshold=threshold)
    text = d["text"]
    stems = _stems(text)
    cited, n_cites = _draft_sources(ws, draft_id)
    flat: list[dict] = []

    def walk(nodes):
        for n in nodes:
            flat.append(n)
            walk(n["children"])
    walk(v["sections"])
    # the stems of every key term (the glossary's own when the term is in it)
    labels = sorted({lab for n in flat for lab in n["terms"]})
    stem_of = {}
    if labels:
        for r in ws.query(f"SELECT label, stems FROM terms WHERE label IN ({','.join('?' * len(labels))})", labels):
            stem_of.setdefault(r["label"], r["stems"])
    for lab in labels:
        stem_of.setdefault(lab, " ".join(_stems(lab)))
    sizes = {len(s.split()) for s in stem_of.values() if s} or {1}
    grams = _grams(stems, {n for n in sizes if 1 <= n <= 6})
    paras = _paragraphs(text)
    pgrams = [_grams(_stems(text[a:b]), {n for n in sizes if 1 <= n <= 6}) if _long(text, (a, b)) else Counter()
              for a, b in paras]
    sections_out = {}
    pids_of: dict[str, list[str]] = {}
    run = _Run(ws, _outline_row(ws, oid)["run_id"])
    for n in flat:
        used_t = [{"label": lab, "mentions": grams.get(stem_of.get(lab, ""), 0)} for lab in n["terms"]]
        in_text = [t for t in used_t if t["mentions"]]
        src_used = [s for s in n["sources"] if s["doc_id"] in cited]
        src_left = [s for s in n["sources"] if s["doc_id"] not in cited]
        ratios = []
        if used_t:
            ratios.append(len(in_text) / len(used_t))
        if n["sources"] and cited:
            ratios.append(len(src_used) / len(n["sources"]))
        elif n["sources"] and n_cites:
            ratios.append(0.0)
        score = sum(ratios) / len(ratios) if ratios else 0.0
        level = "none" if not ratios or score < 0.1 else "little" if score < 0.4 else "partly" if score < 0.7 else "well"
        best, hits = None, 0
        for (a, b), pg in zip(paras, pgrams):
            h = sum(1 for t in used_t if pg.get(stem_of.get(t["label"], ""), 0))
            if h > hits:
                best, hits = (a, b), h
        unused_passages = [r for r in n["representatives"] if r["doc_id"] not in cited][:2]
        sections_out[n["section_id"]] = {
            "section_id": n["section_id"], "number": n["number"], "title": n["title"], "kind": n["kind"],
            "score": round(score, 3), "level": level, "level_text": dict(COVER_WORDS)[level],
            "terms_used": len(in_text), "terms_total": len(used_t),
            "sources_used": len(src_used), "sources_total": len(n["sources"]),
            "terms": used_t, "used_sources": [{k: s[k] for k in ("doc_id", "title", "apa")} for s in src_used],
            "unused_sources": [{k: s[k] for k in ("doc_id", "title", "apa", "passages")} for s in src_left],
            "unused_terms": [t["label"] for t in used_t if not t["mentions"]],
            "unused_points": [{"doc_id": r["doc_id"], "title": r["title"], "location": r["location"],
                               "text": r["text"][:400], "apa": r["apa"]} for r in unused_passages],
            "where": ({"hits": hits, "excerpt": text[best[0]:best[1]][:240],
                       "paragraph": paras.index(best) + 1} if best else None)}
        if n["kind"] == "theme":
            ids = []
            for p in n["parts"]:
                t, state = run.theme(p["theme"])
                if state == "shown":
                    want = set(p["docs"]) if p["docs"] else None
                    ids += [m[1] for m in run.members.get(t["theme_id"], []) if want is None or m[2] in want]
            pids_of[n["section_id"]] = ids
    answer = {"outline": v["outline"], "draft": {"draft_id": draft_id, "title": d["title"],
                                                   "words": len(text.split()), "cited_documents": len(cited),
                                                   "citations": n_cites},
              "sections": sections_out, "order": [n["section_id"] for n in flat], "meaning": None}
    answer["notes"] = []
    if not n_cites:
        answer["notes"].append("No citations were read from this draft, so the sources it uses cannot be told: "
                               "the key terms alone say how much it covers.")
    elif not cited:
        answer["notes"].append("None of the draft's citations is a document of this project linked to the "
                               "bibliography, so no source counts as used yet.")
    if meaning:
        answer["meaning"] = _meaning(ws, text, paras, pids_of, settings)
        if answer["meaning"].get("available"):
            for sid, m in answer["meaning"]["sections"].items():
                sections_out[sid]["closeness"] = m["closeness"]
                sections_out[sid]["closest"] = {"paragraph": m["paragraph"], "excerpt": m["excerpt"]}
    return answer


# ---------------------------------------------------------------------------------------------
# C3: the outline as a document
# ---------------------------------------------------------------------------------------------
def _clip(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def document(ws: Workspace, oid: str, include=INCLUDE, framework: str | None = None) -> dict:
    """The outline as blocks for a writer: ("title", text) · ("heading", level, text) · ("text", paragraph) ·
    ("field", label, text) · ("quote", text, source) · ("bullet", text) · ("small", text). Markdown and Word are both
    made from these."""
    inc = set(include or ())
    v = view(ws, oid, framework=framework)
    o = v["outline"]
    blocks: list[tuple] = [("title", o["title"])]
    run = v["run"]
    blocks.append(("small", f"Made with Margin from {len(v['sections'])} top-level sections"
                            + (f" of the themes found on {run['created_at'][:10]}" if run else "")
                            + f"; outline kept {(o['updated_at'] or '')[:10]}."))
    used_docs: dict[str, dict] = {}

    def write(nodes):
        for n in nodes:
            blocks.append(("heading", min(n["depth"] + 1, 5), f"{n['number']} {n['title']}"))
            for para in [p for p in (n["note"] or "").split("\n\n") if p.strip()]:
                blocks.append(("text", para.strip()))
            if "terms" in inc and n["terms"]:
                blocks.append(("field", "Key terms", "; ".join(n["terms"])))
            if "sources" in inc and n["cite"] and n["cite"].get("text"):
                more = f" and {n['cite']['more']} more" if n["cite"].get("more") else ""
                blocks.append(("field", "Cite", n["cite"]["text"] + more))
            if "sources" in inc:
                for s in n["sources"][:MAX_CITED]:
                    used_docs[s["doc_id"]] = s
            if "concepts" in inc and n["concepts"]:
                blocks.append(("field", "Concepts", "; ".join(
                    c["label"] + (f" (also: {', '.join(w for w in c['wordings'] if w != c['label'][:len(w)])[:80]})"
                                  if len(c["wordings"]) > 1 else "") for c in n["concepts"])))
            if "codes" in inc and n["codes"]:
                blocks.append(("field", "Codes", "; ".join(f"{c['code']} ({c['passages']})" for c in n["codes"])))
            if "quotes" in inc:
                for r in n["representatives"]:
                    src = ", ".join(x for x in (r["title"], r["location"]) if x)
                    if r["apa"]:
                        src += f" {r['apa']}"
                    blocks.append(("quote", _clip(r["text"], 600), src))
            if "disagreements" in inc and n["disagreements"]:
                blocks.append(("field", "Where the sources disagree", ""))
                for d in n["disagreements"]:
                    pro = "; ".join(x["apa"] or x["title"] for x in d["supports"]) or "no document"
                    con = "; ".join(x["apa"] or x["title"] for x in d["refutes"]) or "no document"
                    blocks.append(("bullet", f"{_clip(d['claim'], 200)} Supported by {pro}; contradicted by {con}."))
            if "disagreements" in inc and n["decisions"]:
                blocks.append(("field", "What you decided", ""))
                for d in n["decisions"]:
                    blocks.append(("bullet", f"{_clip(d['claim'], 200)}: {d['decision_text']}."))
            if "gaps" in inc and n["gaps"]:
                blocks.append(("field", "Gaps", " ".join(g["text"] for g in n["gaps"])))
            write(n["children"])
    write(v["sections"])
    if used_docs:
        blocks.append(("heading", 1, "Sources named in this outline"))
        for s in sorted(used_docs.values(), key=lambda s: ((s["apa"] or s["title"]).lower(), s["title"].lower())):
            blocks.append(("bullet", f"{s['title'] or 'Untitled'}" + (f" {s['apa']}" if s["apa"] else "")))
    return {"title": o["title"], "blocks": blocks, "outline": o}


def to_markdown(doc: dict) -> str:
    out: list[str] = []
    prev_bullet = False
    for b in doc["blocks"]:
        kind = b[0]
        if kind != "bullet" and prev_bullet:
            out.append("")
        prev_bullet = kind == "bullet"
        if kind == "title":
            out += [f"# {b[1]}", ""]
        elif kind == "heading":
            out += [f"{'#' * (b[1] + 1)} {b[2]}", ""]
        elif kind == "text":
            out += [b[1], ""]
        elif kind == "field":
            out += [f"**{b[1]}:** {b[2]}" if b[2] else f"**{b[1]}**", ""]
        elif kind == "quote":
            out += [f"> {b[1]}", f"> — {b[2]}" if b[2] else ">", ""]
        elif kind == "bullet":
            out.append(f"- {b[1]}")
        elif kind == "small":
            out += [f"*{b[1]}*", ""]
    return "\n".join(out).rstrip() + "\n"


_XML_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def _t(text: str) -> str:
    return escape(_XML_BAD.sub("", text))


def _run(text: str, bold=False, italic=False) -> str:
    props = ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "")
    return (f"<w:r>{f'<w:rPr>{props}</w:rPr>' if props else ''}"
            f"<w:t xml:space=\"preserve\">{_t(text)}</w:t></w:r>")


def _para(runs: str, style: str | None = None, ppr: str = "") -> str:
    pr = (f"<w:pStyle w:val=\"{style}\"/>" if style else "") + ppr
    return f"<w:p>{f'<w:pPr>{pr}</w:pPr>' if pr else ''}{runs}</w:p>"


_NS = ("xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
       "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"")


def _styles() -> str:
    def style(sid, name, based="Normal", nxt="Normal", ppr="", rpr="", extra=""):
        return (f"<w:style w:type=\"paragraph\" w:styleId=\"{sid}\"><w:name w:val=\"{name}\"/>"
                f"<w:basedOn w:val=\"{based}\"/><w:next w:val=\"{nxt}\"/>{extra}<w:qFormat/>"
                f"{f'<w:pPr>{ppr}</w:pPr>' if ppr else ''}{f'<w:rPr>{rpr}</w:rPr>' if rpr else ''}</w:style>")

    heads = "".join(
        style(f"Heading{i}", f"heading {i}", ppr=f"<w:keepNext/><w:spacing w:before=\"{360 - 40 * i}\" w:after=\"120\"/>"
              f"<w:outlineLvl w:val=\"{i - 1}\"/>", rpr=f"<w:b/><w:sz w:val=\"{34 - 4 * i}\"/>",
              extra="<w:uiPriority w:val=\"9\"/>") for i in range(1, 6))
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            f"<w:styles {_NS}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii=\"Calibri\" w:hAnsi=\"Calibri\" "
            "w:cs=\"Calibri\" w:eastAsia=\"Calibri\"/><w:sz w:val=\"22\"/><w:szCs w:val=\"22\"/><w:lang "
            "w:val=\"en-GB\"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after=\"120\" w:line=\"264\" "
            "w:lineRule=\"auto\"/></w:pPr></w:pPrDefault></w:docDefaults>"
            "<w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\"><w:name w:val=\"Normal\"/><w:qFormat/>"
            "</w:style>"
            + style("Title", "Title", ppr="<w:spacing w:after=\"200\"/>", rpr="<w:b/><w:sz w:val=\"44\"/>",
                    extra="<w:uiPriority w:val=\"10\"/>")
            + heads
            + style("Quote", "Quote", ppr="<w:ind w:left=\"567\" w:right=\"567\"/><w:spacing w:after=\"40\"/>",
                    rpr="<w:i/>", extra="<w:uiPriority w:val=\"29\"/>")
            + style("QuoteSource", "Quote source", ppr="<w:ind w:left=\"567\" w:right=\"567\"/>",
                    rpr="<w:sz w:val=\"19\"/><w:color w:val=\"595959\"/>")
            + style("ListBullet", "List Bullet", ppr="<w:tabs><w:tab w:val=\"left\" w:pos=\"567\"/></w:tabs>"
                    "<w:ind w:left=\"567\" w:hanging=\"283\"/><w:spacing w:after=\"40\"/>",
                    extra="<w:uiPriority w:val=\"36\"/>")
            + "</w:styles>")


def to_docx(doc: dict) -> bytes:
    """A Word document (WordprocessingML) with Title and Heading 1 to 5 styles, written with zipfile."""
    body: list[str] = []
    for b in doc["blocks"]:
        kind = b[0]
        if kind == "title":
            body.append(_para(_run(b[1]), "Title"))
        elif kind == "heading":
            body.append(_para(_run(b[2]), f"Heading{max(1, min(5, b[1]))}"))
        elif kind == "text":
            body.append(_para(_run(b[1])))
        elif kind == "field":
            body.append(_para(_run(b[1] + (": " if b[2] else ""), bold=True) + (_run(b[2]) if b[2] else "")))
        elif kind == "quote":
            body.append(_para(_run("“" + b[1] + "”"), "Quote"))
            if b[2]:
                body.append(_para(_run("— " + b[2]), "QuoteSource"))
        elif kind == "bullet":
            body.append(_para(_run("•") + "<w:r><w:tab/></w:r>" + _run(b[1]), "ListBullet"))
        elif kind == "small":
            body.append(_para(_run(b[1], italic=True)))
    sect = ("<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" "
            "w:bottom=\"1440\" w:left=\"1440\" w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/></w:sectPr>")
    document_xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    f"<w:document {_NS}><w:body>{''.join(body)}{sect}</w:body></w:document>")
    stamp = now()
    core = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
            "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" "
            "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
            f"<dc:title>{_t(doc['title'])}</dc:title><dc:creator>Margin</dc:creator>"
            f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{stamp}</dcterms:created>"
            f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{stamp}</dcterms:modified></cp:coreProperties>")
    parts = {
        "[Content_Types].xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
            "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
            "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
            "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document.main+xml\"/>"
            "<Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument."
            "wordprocessingml.styles+xml\"/>"
            "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package."
            "core-properties+xml\"/></Types>"),
        "_rels/.rels": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
            "officeDocument\" Target=\"word/document.xml\"/>"
            "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/"
            "core-properties\" Target=\"docProps/core.xml\"/></Relationships>"),
        "word/_rels/document.xml.rels": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
            "styles\" Target=\"styles.xml\"/></Relationships>"),
        "word/document.xml": document_xml,
        "word/styles.xml": _styles(),
        "docProps/core.xml": core,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return buf.getvalue()
