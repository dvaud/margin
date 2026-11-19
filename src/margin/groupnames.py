"""The names of the concept map's groups (roadmap D1, the rest).

Every group of the map (`conceptmap.concept_map`) has a name, always, from one of four sources:

- `concepts`: made here, with no AI, from the group's two most central concepts (*Office days and team days*; one
  concept alone when the two pass `MAX_NAME` characters). Made again on every map; never stored.
- `person`: typed by the researcher (*Rename*).
- `ai_draft`: drafted by the AI (*Name the groups*); shown as the name at once, always marked, until it is used or
  renamed.
- `ai`: the AI's draft, used by the researcher (*Use this name*).

**Kept names.** A name that is not made from the concepts is a row of `concept_group_names`, with the concepts of its
group (term ids, as the map hands them out, and their labels), and the filters and number of concepts it was given
under. When the groups are found again (another visit, new documents, other filters), a group takes a kept name when
it holds most of that name's concepts that are on this map (and at least two of them, or all when the name has
fewer), and no other kept name fits it better (more of its concepts shared, over all the concepts of both; then the
newer; then the id): the same answer every time. A name that no group takes is listed apart (`names_elsewhere`) and
comes back with its group.

**Changed.** On the map with the same filters and size as when the name was given, a group that took its name but lost
or gained a third or more of its concepts is `changed`, with what left and what joined. *Keep the name* gives the name
the group as it is now. Under other filters or another size nothing is flagged: there the group differs because the
view does.

**Who and when.** Each kept name holds who gave it (`person_id`), who changed it last and when (`changed_by`,
`updated_at`: its version), and the versions that change replaced (`history_json`). ENLENS merges the names of a team
by these; Margin is for one person, so they only date the changes (`clock`).

**The AI's drafts** (Level 2 or 3, on request only). *Name the groups* sends one request, which only puts tasks in the
queue (one per group, kind `group_name`) and makes a job that waits for its own Start, as every AI job does: nothing
starts a model while the page is drawn. Each task holds a few passages in which several of the group's concepts are
mentioned together (`MAX_PASSAGES`, spread over the documents), only from documents whose AI setting lets this reader
read them: a passage of a document marked *No AI* is never sent, one marked *Only a local AI* only to the local model.
A group with no such passage is not asked, and the job's result says how many. The AI answers a name and a quote that
shows it; the quote check sends a quote that is not there back to be fixed (three tries, as for every kind), and a
group the AI could not name keeps the name made from its concepts (`naming_failed` says why). The AI never overwrites
a name the researcher gave.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from typing import Callable

from .store import Workspace, now

KIND = "group_name"
MAX_NAME = 60            # characters
MAX_PASSAGES = 6         # passages per group sent to the AI
MAX_CANDIDATES = 200     # passages looked at for them, those where most of the group's concepts meet first
PER_DOC = 2              # at most this many from one document, while others have some
MAX_CHARS = 6000         # and at most this much text
MAX_CONCEPTS = 12        # concepts named to the AI
MIN_QUOTE_WORDS = 3
SOURCES = ("concepts", "person", "ai_draft", "ai")
RANK = {"person": 2, "ai": 2, "ai_draft": 1}   # a person's decision (typed, or the AI's draft used) beats a draft
REMOVED = "group_name"   # the kind of a removed name in `sync_removed`

_T_OK = "temp.d1_name_docs"   # the documents the reader may read (_passages_of)
NONE_MAY_READ = "No AI may read these documents, so the groups can only be named by you."


def _h(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def _clean(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def concepts_name(labels: list[str]) -> str:
    """The name made from a group's two most central concepts: "Office days and team days" (first letter a capital),
    one concept alone when the two together pass `MAX_NAME` characters."""
    ls = [_clean(x, 200) for x in labels if _clean(x, 200)]
    if not ls:
        return ""
    two = f"{ls[0]} and {ls[1]}" if len(ls) > 1 else ls[0]
    name = two if len(two) <= MAX_NAME else ls[0]
    if len(name) > MAX_NAME:
        name = name[:MAX_NAME - 1].rstrip() + "…"
    return name[:1].upper() + name[1:]


# ---- the kept names ----------------------------------------------------------------------------------------------
def _rows(ws: Workspace) -> list[dict]:
    out = []
    quotes = {r["name_id"]: dict(r) for r in ws.query("SELECT * FROM concept_group_quotes")}
    for r in ws.query("SELECT * FROM concept_group_names ORDER BY created_at, name_id"):
        d = _parsed(dict(r))
        if d is None:          # a row no Margin wrote (merge checks what comes in): left out, not a broken map
            continue
        q = quotes.get(d["name_id"])
        d["quote"] = {k: q[k] for k in ("quote", "doc_id", "passage_id", "page", "start", "end")} if q else None
        out.append(d)
    return out


def _parsed(d: dict) -> dict | None:
    """A stored row with its JSON read (concepts: a list of ids, labels and filters: objects), or None when it is not
    what Margin writes."""
    try:
        concepts = json.loads(d.pop("concepts_json") or "[]")
        labels = json.loads(d.pop("labels_json") or "{}")
        filters = json.loads(d.pop("filters_json") or "{}")
        d.pop("history_json", None)
    except (TypeError, ValueError):
        return None
    if (not isinstance(concepts, list) or not all(isinstance(c, str) for c in concepts) or not isinstance(labels, dict)
            or not isinstance(filters, dict) or not isinstance(d.get("name"), str)):
        return None
    d.update(concepts=concepts, labels={str(k): str(v) for k, v in labels.items()}, filters=filters)
    return d


def _same_view(rec: dict, filters: dict, n: int) -> bool:
    return json.dumps(rec["filters"], sort_keys=True) == json.dumps(filters, sort_keys=True) and int(rec["n"] or 0) == n


def order_key(rec: dict) -> tuple:
    """How DIFFERENT kept names that fit one group are ranked, the first first, the same on every copy: a person's
    decision before an AI draft; then the later; then the larger id of who changed it; then the id. (Two versions of
    the SAME name are settled by `merge`: the later change, whatever its kind.)"""
    return (-RANK.get(rec.get("source"), 0), _neg_time(rec.get("updated_at")),
            _neg_time(rec.get("changed_by") or rec.get("person_id")), rec.get("name_id") or "")


def match_all(records: list[dict], groups: list[list[str]], on_map: set[str]) -> dict[int, list[dict]]:
    """{group index: every kept name that fits it, the one it takes first} (see the module's notes): a name fits a group
    that holds most of the name's concepts on this map (and at least two, or all of them when the name has fewer). Of
    several, `order_key` decides: it never depends on how well each fits, which differs from copy to copy (each finds
    its groups from its own counts), so every copy shows the same name for the same group. Deterministic."""
    sets = [set(g) for g in groups]
    cands: dict[int, list[dict]] = {}
    for rec in records:
        rc = set(rec["concepts"])
        on = rc & on_map
        if not on:
            continue
        for gi, gs in enumerate(sets):
            k = len(rc & gs)
            if k * 2 > len(on) and k >= min(2, len(rc)):
                cands.setdefault(gi, []).append(rec)
                break      # most of its concepts: in one group at most
    return {gi: sorted(cs, key=order_key) for gi, cs in cands.items()}


def match(records: list[dict], groups: list[list[str]], on_map: set[str]) -> dict[int, dict]:
    """{group index: the kept name it takes} (`match_all`, its first)."""
    return {gi: cs[0] for gi, cs in match_all(records, groups, on_map).items()}


def _neg_time(at: str | None) -> str:
    """A key that sorts newer times first."""
    return "".join(chr(0x10FFFF - ord(c)) for c in (at or ""))


def changed(rec: dict, members: list[str], labels: dict[str, str], filters: dict, n: int) -> dict | None:
    """{"left", "joined"} (labels) when, under the same filters and size it was named with, the group lost or gained a
    third or more of the name's concepts; else None."""
    if not _same_view(rec, filters, n):
        return None
    rc, gs = set(rec["concepts"]), set(members)
    left, joined = [x for x in rec["concepts"] if x not in gs], [x for x in members if x not in rc]
    third = len(rc) / 3
    if not rc or (len(left) < third and len(joined) < third):
        return None
    lab = lambda x: labels.get(x) or rec["labels"].get(x) or x  # noqa: E731
    return {"left": [lab(x) for x in left], "joined": [lab(x) for x in joined]}


def _failures(ws: Workspace) -> list[tuple[set[str], dict]]:
    """The groups the AI could not name (their task failed after its tries): (their concepts, {"reason", "model"})."""
    from .themes import naming_reason

    out = []
    for r in ws.query("SELECT t.payload_json, (SELECT errors_json FROM results x WHERE x.task_id=t.task_id ORDER BY "
                      "x.attempt DESC LIMIT 1) AS errors, (SELECT model FROM results x WHERE x.task_id=t.task_id ORDER "
                      "BY x.attempt DESC LIMIT 1) AS model FROM tasks t WHERE t.kind=? AND t.status='failed'", (KIND,)):
        try:
            p = json.loads(r["payload_json"] or "{}")
            errors = [str(e) for e in json.loads(r["errors"] or "[]")]
        except ValueError:
            continue
        out.append((set(p.get("concept_ids") or []), {"reason": naming_reason(errors), "model": r["model"]}))
    return out


def attach(ws: Workspace, out: dict, members: list[list[str]], labels: dict[str, str], filters: dict, n: int,
           docs_in_scope: set[str] | None, settings: dict | None = None) -> None:
    """Give each of the map's groups its name ({"name", "name_source", "name_id", "model", "quote", "changed",
    "naming_failed", "concepts"}), and the map `names_elsewhere` and `can_name`. `members`: each group's term ids,
    the most central first; `labels`: {term id: label}."""
    try:
        records = _rows(ws)
    except Exception:  # noqa: BLE001 - a project opened by an older Margin: no table yet, no kept names
        records = []
    on_map = set(labels)
    fitting = match_all(records, members, on_map)
    took = {gi: cs[0] for gi, cs in fitting.items()}
    fails = _failures(ws) if any(gi not in took or took[gi]["source"] != "person" for gi in range(len(members))) else []
    used = set()
    who = _people(ws) if records else {}
    for gi, gr in enumerate(out["groups"]):
        ms = members[gi]
        gr["concepts"] = ms
        rec = took.get(gi)
        gr["also_named"] = []
        if rec is None:
            gr.update(name=concepts_name([labels[x] for x in ms[:2]]), name_source="concepts", name_id=None,
                      model=None, quote=None, changed=None, by=None, named_at=None)
        else:
            used.update(x["name_id"] for x in fitting[gi])
            gr.update(name=rec["name"], name_source=rec["source"], name_id=rec["name_id"],
                      model=rec["model"] if rec["source"] in ("ai", "ai_draft") else None,
                      quote=_quote_view(ws, rec["quote"]) if rec["source"] in ("ai", "ai_draft") else None,
                      changed=changed(rec, ms, labels, filters, n),
                      by=who.get(rec.get("person_id") or "", "you" if not rec.get("person_id") else "a colleague"),
                      named_at=rec.get("updated_at"))
            # the other names a person gave this group (on this copy or another): shown with it, never lost
            seen = {rec["name"].lower()}
            for x in fitting[gi][1:]:
                if x["source"] == "ai_draft" or x["name"].lower() in seen:
                    continue
                seen.add(x["name"].lower())
                gr["also_named"].append({"id": x["name_id"], "name": x["name"], "name_source": x["source"],
                                         "by": who.get(x.get("person_id") or "", "a colleague"),
                                         "at": x.get("updated_at")})
        gr["naming_failed"] = None
        if gr["name_source"] != "person":         # named by its concepts, or by the AI before ("Name the groups again")
            gs = set(ms)
            for cs, why in fails:
                if cs and len(cs & gs) * 2 > len(cs):
                    gr["naming_failed"] = why
                    break
    out["names_elsewhere"] = [{"id": r["name_id"], "name": r["name"], "name_source": r["source"],
                               "concepts": [r["labels"].get(x) or x for x in r["concepts"]][:6],
                               "more": max(0, len(r["concepts"]) - 6)}
                              for r in records if r["name_id"] not in used]
    out["can_name"] = offer(ws, docs_in_scope, settings) if out["groups"] else {"offered": False, "why": None,
                                                                               "reader": None}


def _people(ws: Workspace) -> dict[str, str]:
    """{person id: name} for the names' "by" ("you" for this computer's person)."""
    from . import solo as people  # Margin: one person

    try:
        return people.names(ws)
    except Exception:  # noqa: BLE001 - no settings to read (a test's bare project): only "you"
        return {}


def _quote_view(ws: Workspace, q: dict | None) -> dict | None:
    if not q:
        return None
    title = ws.scalar("SELECT title FROM documents WHERE doc_id=?", (q["doc_id"],)) if q.get("doc_id") else None
    return {**q, "title": title or ""}


# ---- what a person does with a name ------------------------------------------------------------------------------
def _clean_ids(xs) -> list[str]:
    return [str(x) for x in (xs or []) if isinstance(x, (str, int)) and str(x)][:200]


def _forget_failures(cx, concepts: list[str], statuses: tuple[str, ...] = ("failed",)) -> None:
    """A group renamed, named by the AI, its name used or kept, or named by its concepts again: the AI's failed tries
    for it are no longer the page's news. With `statuses` ("failed", "done"), its answered tasks go too: a draft the
    researcher turned down (*Use its concepts as the name*) is not handed back unasked by the next *Name the groups*,
    which would find the same task done, or its kept answer."""
    cs = set(concepts)
    for tid, payload in cx.execute(f"SELECT task_id, payload_json FROM tasks WHERE kind=? AND status IN "
                                   f"({','.join('?' * len(statuses))})", (KIND, *statuses)).fetchall():
        try:
            got = set(json.loads(payload or "{}").get("concept_ids") or [])
        except ValueError:
            continue
        if got and len(got & cs) * 2 > len(got):
            if "done" in statuses:     # and the kept answer (tasks.answer_from_cache) that would bring it back
                cx.execute("DELETE FROM ai_cache WHERE kind=? AND raw_json IN (SELECT raw_json FROM results WHERE "
                           "task_id=?)", (KIND, tid))
            cx.execute("DELETE FROM results WHERE task_id=?", (tid,))
            cx.execute("DELETE FROM tasks WHERE task_id=?", (tid,))


def save(ws: Workspace, action: str, body: dict) -> dict:
    """One change to the names, as the page sends it ({"action", …}); returns {"record": the name as it is now, or
    the one forgotten, or null}. Actions:

    - `rename` {name_id?, name, concepts, labels, filters, n}: the researcher's own name (`person`) for the group as it
      is now; an empty name is refused.
    - `use_concepts` {name_id, concepts}: the group is named by its concepts again (the kept name is removed).
    - `accept` {name_id | items: [{name_id, concepts, labels}], concepts, labels, filters, n}: the AI's draft used
      (`ai`), with the group as it is now; the answer adds `before`, each name as it was. `unaccept` {before}: each
      name put back as it was (Undo), while it is still the used name; {name_id | items}: back to a draft only.
    - `keep` {name_id, concepts, labels, filters, n}: the name now goes with the group as it is (a changed group).
    - `forget` {name_id}: a kept name no group takes, removed; `restore` {record}: put back (Undo).
    Raises KeyError for a name that is not there, ValueError for a request that cannot be done."""
    from . import solo as people  # Margin: one person

    me = people.me()
    at = now()   # this copy's clock, read in the transaction below (`clock`)
    filters = body.get("filters") if isinstance(body.get("filters"), dict) else {}
    filters = {str(k): v for k, v in filters.items() if isinstance(v, (str, int, list))}
    n = int(body.get("n") or 0) if str(body.get("n") or "0").isdigit() else 0
    concepts = _clean_ids(body.get("concepts"))
    labels = body.get("labels") if isinstance(body.get("labels"), dict) else {}
    labels = {str(k): _clean(v, 200) for k, v in labels.items() if str(k) in set(concepts)}
    nid = str(body.get("name_id") or "") or None

    def get(cx, i):
        r = cx.execute("SELECT * FROM concept_group_names WHERE name_id=?", (i,)).fetchone()
        if r is None:
            raise KeyError(i)
        return r

    def group_now(cx, i, conc, labs, author=True, **more):
        # the name with its group as it is now. `author`: the name becomes this person's (a rename, a draft used); not
        # for Keep the name, which keeps who gave it (it is still their name; `changed_by` says who kept it)
        _change(cx, i, at, me, concepts_json=json.dumps(conc), labels_json=json.dumps(labs, ensure_ascii=False),
                filters_json=json.dumps(filters, sort_keys=True), n=n, **({"person_id": me} if author else {}), **more)

    with ws.connect() as cx:
        at = clock(cx)
        fill_people(cx, me)
        if action == "rename":
            name = _clean(body.get("name"), MAX_NAME)
            if not name:
                raise ValueError("Give the group a name.")
            if not concepts:
                raise ValueError("Say which concepts the group holds.")
            if nid:
                get(cx, nid)
                cx.execute("DELETE FROM concept_group_quotes WHERE name_id=?", (nid,))
            else:
                nid = uuid.uuid4().hex[:16]
            group_now(cx, nid, concepts, labels, name=name, source="person", model=None)
            _forget_failures(cx, concepts)
        elif action == "use_concepts":
            if nid:
                r = get(cx, nid)
                cx.execute("DELETE FROM concept_group_names WHERE name_id=?", (nid,))
                cx.execute("DELETE FROM concept_group_quotes WHERE name_id=?", (nid,))
                _note_removed(cx, nid, r["name"], at, me)
            _forget_failures(cx, concepts, ("failed", "done"))
            return {"record": None}
        elif action == "unaccept" and isinstance(body.get("before"), list):
            # Undo of Use this name: each name as it was before (its group, filters and size, and its source). An
            # Undo is a new change: this copy's clock and this person, so every copy takes it (review, 18 Nov 2026)
            cols = ("name", "source", "model", "concepts_json", "labels_json", "filters_json", "n")
            done = []
            for row in body["before"]:
                if not isinstance(row, dict) or not row.get("name_id") or row.get("source") not in ("ai_draft", "ai"):
                    raise ValueError("Nothing to put back.")
                r = get(cx, str(row["name_id"]))
                if r["source"] == "ai":       # still the used name (not renamed meanwhile)
                    _change(cx, r["name_id"], at, me, person_id=me,
                            **{c: (row.get(c) if c in row else r[c]) for c in cols})
                done.append(str(row["name_id"]))
            if len(done) != 1:
                return {"record": None}
            nid = done[0]
        elif action in ("accept", "unaccept"):
            items = body.get("items") if isinstance(body.get("items"), list) else [
                {"name_id": nid, "concepts": concepts, "labels": labels}]
            before = []
            for it in items:
                if not isinstance(it, dict) or not it.get("name_id"):
                    raise ValueError("Say which name.")
                r = get(cx, str(it["name_id"]))
                if action == "accept" and r["source"] in ("ai_draft", "ai"):
                    before.append(dict(r))
                    conc = _clean_ids(it.get("concepts")) or json.loads(r["concepts_json"] or "[]")
                    labs = it.get("labels") if isinstance(it.get("labels"), dict) else {}
                    group_now(cx, r["name_id"], conc, {str(k): _clean(v, 200) for k, v in labs.items()} or
                              json.loads(r["labels_json"] or "{}"), source="ai")
                    _forget_failures(cx, conc)
                elif action == "unaccept" and r["source"] == "ai":
                    _change(cx, r["name_id"], at, me, source="ai_draft", person_id=me)
            if len(items) != 1:
                return {"record": None, "before": before} if action == "accept" else {"record": None}
            nid = str(items[0]["name_id"])
        elif action == "keep":
            get(cx, nid)
            if not concepts:
                raise ValueError("Say which concepts the group holds.")
            group_now(cx, nid, concepts, labels, author=False)
            _forget_failures(cx, concepts)
        elif action == "forget":
            r = get(cx, nid)
            q = cx.execute("SELECT * FROM concept_group_quotes WHERE name_id=?", (nid,)).fetchone()
            cx.execute("DELETE FROM concept_group_names WHERE name_id=?", (nid,))
            cx.execute("DELETE FROM concept_group_quotes WHERE name_id=?", (nid,))
            _note_removed(cx, nid, r["name"], at, me)
            return {"record": {"row": dict(r), "quote": dict(q) if q else None}}
        elif action == "restore":
            rec = body.get("record") if isinstance(body.get("record"), dict) else {}
            row = rec.get("row") if isinstance(rec.get("row"), dict) else None
            if not row or not row.get("name_id") or row.get("source") not in SOURCES[1:]:
                raise ValueError("Nothing to put back.")
            # put back as a new change (Undo): this copy's clock, later than the removal it undoes on every copy that
            # heard of it, and this person as who changed it; the name is still its author's
            cols = ("name", "source", "model", "concepts_json", "labels_json", "filters_json", "n", "created_at",
                    "person_id")
            _change(cx, str(row["name_id"]), at, me, **{c: row.get(c) for c in cols},
                    history_json=json.dumps((_history(row) + [stamp(row)])[-HISTORY:]))
            q = rec.get("quote") if isinstance(rec.get("quote"), dict) else None
            if q and q.get("name_id") == row["name_id"]:
                qc = ("name_id", "doc_id", "passage_id", "page", "start", "end", "quote")
                # only while its document is still here (a document removed meanwhile takes its text with it)
                if cx.execute("SELECT 1 FROM documents WHERE doc_id=?", (q.get("doc_id"),)).fetchone():
                    cx.execute(f"INSERT OR REPLACE INTO concept_group_quotes({', '.join(qc)}) VALUES "
                               f"({','.join('?' * len(qc))})", tuple(q.get(c) for c in qc))
            nid = row["name_id"]
        else:
            raise ValueError(f"Unknown action {action!r}.")
    recs = [r for r in _rows(ws) if r["name_id"] == nid]
    if action == "accept":         # what Use this name overwrote, for its Undo (`unaccept` {before})
        return {"record": recs[0] if recs else None, "before": before}
    return {"record": recs[0] if recs else None}


# ---- with a team (the module's notes) --------------------------------------------------------------------------------
NAME_COLS = ("name_id", "name", "source", "model", "concepts_json", "labels_json", "filters_json", "n", "created_at",
             "updated_at", "person_id", "changed_by", "history_json")
QUOTE_COLS = ("name_id", "doc_id", "passage_id", "page", "start", "end", "quote")
FUTURE = 600          # seconds: a name or removal dated further ahead of this computer's clock is not taken (yet)
HISTORY = 20          # the versions a name remembers it replaced (`history_json`)


def _iso(at) -> str | None:
    """A time as this module writes it (UTC, to the second, `store.now()`'s form), or None when it is not a time."""
    import datetime as _dt

    try:
        t = _dt.datetime.fromisoformat(str(at))
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        return None
    return t.astimezone(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _plus(at: str, seconds: int) -> str:
    import datetime as _dt

    return (_dt.datetime.fromisoformat(at) + _dt.timedelta(seconds=seconds)).isoformat()


def clock(cx) -> str:
    """The time of a change made on this copy: now, or one second after the newest name or removal this copy holds
    when that is later (a hybrid logical clock: a change made after seeing another is always later than it, whatever
    this computer's clock says, so a slow clock cannot undo a colleague's rename)."""
    t = now()
    got = [x for x in (cx.execute("SELECT MAX(updated_at) FROM concept_group_names").fetchone()[0],) if x]
    newest = max((x for x in (_iso(g) for g in got) if x), default=None)
    return _plus(newest, 1) if newest and newest >= t else t


def stamp(row: dict) -> str:
    """A version of a name: when it was changed and by whom."""
    return f"{row.get('updated_at') or ''}|{row.get('changed_by') or row.get('person_id') or ''}"


def _history(row: dict) -> list[str]:
    try:
        h = json.loads(row.get("history_json") or "[]")
    except (TypeError, ValueError):
        return []
    return [x for x in h if isinstance(x, str)][-HISTORY:] if isinstance(h, list) else []


def _change(cx, nid: str, at: str, me: str, **fields) -> None:
    """A change made on this copy: written at `at` (`clock`) with this person as who changed it, the version it
    replaced added to its history, so another copy can tell a later change from one made at the same time."""
    old = cx.execute("SELECT * FROM concept_group_names WHERE name_id=?", (nid,)).fetchone()
    if old is None:
        row = {c: None for c in NAME_COLS}
        row.update(name_id=nid, created_at=at, person_id=me, history_json="[]")
    else:
        row = dict(old)
        row["history_json"] = json.dumps((_history(row) + [stamp(row)])[-HISTORY:])
    row.update(fields)
    row.update(name_id=nid, updated_at=at, changed_by=me, created_at=row.get("created_at") or at)
    cx.execute(f"INSERT OR REPLACE INTO concept_group_names({', '.join(NAME_COLS)}) VALUES "
               f"({','.join('?' * len(NAME_COLS))})", tuple(row.get(c) for c in NAME_COLS))


def fill_people(cx, me: str) -> None:
    """Names from before they travelled (no person) are this copy's person's, as reviews are (people.adopt)."""
    cx.execute("UPDATE concept_group_names SET person_id=? WHERE person_id IS NULL", (me,))
    cx.execute("UPDATE concept_group_names SET changed_by=person_id WHERE changed_by IS NULL")


def _note_removed(cx, name_id: str, name: str | None, at: str, person_id: str) -> None:
    """A kept name removed. ENLENS notes it so that a colleague's copy does not bring it back; Margin has no colleagues
    (and no `sync_removed` table), so there is nothing to note."""
    return None


def _fork_id(name_id: str, person_id: str | None, at: str | None) -> str:
    """The id of a person's version of a name kept as a name of its own: the same on every copy."""
    return "f" + _h(name_id, person_id or "", at or "")[:15]


def _local_reader(settings: dict) -> bool:
    from . import home

    return bool(home.main_reads_local(settings) or home.restricted_choice(settings))


def offer(ws: Workspace, docs: set[str] | None, settings: dict | None = None) -> dict:
    """Whether the AI may be asked to name the groups: {"offered", "why", "reader": "claude" | "local" | "main" |
    None}. From the documents in scope and their AI settings only; nothing is asked of a model."""
    from . import access, home
    from .routing import AUDITOR_ROUTES

    s = settings if settings is not None else home.load_settings()
    lv = access.levels(ws, sorted(docs), provider=access.route_provider(s)) if docs else {}
    dflt = access.default(ws)
    kinds = {lv.get(d) or dflt for d in (docs or ())}
    local_ok = _local_reader(s)
    if "cloud" not in kinds and not ("local" in kinds and local_ok):
        why = NONE_MAY_READ if "local" not in kinds else (
            "Only a local AI may read these documents, and none is chosen (Settings → AI), so the groups can only "
            "be named by you.")
        return {"offered": False, "why": why, "reader": None}
    if "cloud" not in kinds or home.main_reads_local(s):
        reader = "local" if "cloud" not in kinds else "main"
    else:
        reader = "claude" if (s.get("backend") or "auto") in AUDITOR_ROUTES else "main"
    return {"offered": True, "why": None, "reader": reader}


def _passages_of(ws: Workspace, f, nodes: list[str], g, allowed: set[str], lv: dict[str, str], dflt: str) -> list[dict]:
    """A few passages in scope where several of these concepts (node ids) are mentioned together, the most of them
    first, spread over the documents, only from documents of the `allowed` settings."""
    from .conceptmap import _T_PI, _Scope

    docs = [r[0] for r in ws.query("SELECT doc_id FROM documents") if (lv.get(r[0]) or dflt) in allowed]
    if not docs:
        return []
    with _Scope(ws, g, f) as sc:
        if sc.empty() or not sc.total():
            return []
        sc._index(nodes)
        # the documents this reader may read, before the limit: a group whose most-shared passages are all in
        # documents it may not read still finds the ones it may
        sc.cx.execute(f"DROP TABLE IF EXISTS {_T_OK}")
        sc.cx.execute(f"CREATE TABLE {_T_OK}(doc_id TEXT PRIMARY KEY) WITHOUT ROWID")
        sc.cx.executemany(f"INSERT INTO {_T_OK} VALUES (?)", [(d,) for d in docs])
        try:
            rows = sc.cx.execute(
                f"SELECT x.passage_id, COUNT(*) AS k, GROUP_CONCAT(x.i) AS ii FROM {_T_PI} x JOIN passages p ON "
                f"p.passage_id=x.passage_id JOIN {_T_OK} o ON o.doc_id=p.doc_id GROUP BY x.passage_id HAVING "
                f"COUNT(*) >= 2 ORDER BY k DESC, x.passage_id LIMIT ?", (MAX_CANDIDATES,)).fetchall()
        finally:
            sc.cx.execute(f"DROP TABLE IF EXISTS {_T_OK}")
    if not rows:
        return []
    ids = [r[0] for r in rows]
    info = {}
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        for r in ws.query(f"SELECT passage_id, doc_id, page, start, end, text FROM passages WHERE passage_id IN "
                          f"({','.join('?' * len(chunk))})", chunk):
            info[r["passage_id"]] = dict(r)
    cands = []
    for pid, k, ii in rows:
        p = info.get(pid)
        if p and (lv.get(p["doc_id"]) or dflt) in allowed:
            cands.append({**p, "k": int(k), "nodes": sorted({int(x) for x in str(ii).split(",")})})
    picked, per_doc, size = [], {}, 0
    for limit in (PER_DOC, MAX_PASSAGES):           # spread over the documents first, then fill
        for p in cands:
            if len(picked) >= MAX_PASSAGES:
                break
            if p in picked or per_doc.get(p["doc_id"], 0) >= limit:
                continue
            if picked and size + len(p["text"] or "") > MAX_CHARS:
                continue
            picked.append(p)
            per_doc[p["doc_id"]] = per_doc.get(p["doc_id"], 0) + 1
            size += len(p["text"] or "")
    return picked


def payloads(ws: Workspace, f, n: int, which: str, allowed: set[str], settings: dict | None = None) -> dict:
    """The tasks *Name the groups* asks for, from the map as it is now: {"tasks": [(group, payload)], "skipped":
    groups with no passage the reader may read, "person": groups named by the researcher (never asked)}. `which`:
    "unnamed" (the groups still named by their concepts, and those the AI could not name) or "again" (every group
    but those named by the researcher, each for a new draft)."""
    from . import access
    from .conceptmap import concept_map
    from .conceptpaths import _Graph

    m = concept_map(ws, f, n, settings=settings)
    g = _Graph(ws)
    lab = {x["id"]: x["label"] for x in m["nodes"]}
    from . import home

    s = settings if settings is not None else home.load_settings()
    lv = access.levels(ws, provider=access.route_provider(s))   # for the main route's provider
    dflt = access.default(ws)
    out: dict = {"tasks": [], "skipped": 0, "person": 0, "map": m}
    for gr in m["groups"]:
        if gr["name_source"] == "person":
            out["person"] += 1
            continue
        if which != "again" and gr["name_source"] != "concepts" and not gr.get("naming_failed"):
            continue
        ms = gr["concepts"]
        nodes = [g.node(t) for t in ms]
        ps = _passages_of(ws, f, nodes, g, allowed, lv, dflt)
        if not ps:
            out["skipped"] += 1
            continue
        payload = {"concepts": [lab[t] for t in ms[:MAX_CONCEPTS]], "concept_ids": ms,
                   "labels": {t: lab[t] for t in ms},
                   "docs": sorted({p["doc_id"] for p in ps}), "filters": m["filters"], "n": m["n"],
                   "name_id": gr["name_id"],
                   "before": gr["name"] if gr["name_source"] in ("ai", "ai_draft") else None,
                   # the whole map's groups (term ids) and this one's place: `apply` finds the name this group has on
                   # the map, never one another group holds (a name whose concepts span two groups)
                   "map_groups": [x["concepts"] for x in m["groups"]], "group_index": m["groups"].index(gr),
                   "passages": [{"n": k, "passage_id": p["passage_id"], "page": p["page"], "text": p["text"],
                                 "concepts": [lab[ms[i]] for i in p["nodes"] if i < len(ms)][:8]}
                                for k, p in enumerate(ps, 1)]}
        out["tasks"].append((gr, payload))
    return out


def make_task(ws: Workspace, payload: dict, model: str) -> str:
    """A group's task, one per input: the same concepts, passages, prompt version and model give the same task (a
    failed one is asked anew). Returns its id."""
    from . import prompts
    from .tasks import replace_task

    key = {k: payload.get(k) for k in ("concept_ids", "passages", "before")}
    tid = f"{KIND}:" + _h(json.dumps(key, sort_keys=True, ensure_ascii=False), prompts.VERSIONS.get(KIND) or "",
                          model or "")[:16]
    with ws.connect() as cx:
        replace_task(cx, tid, KIND, model, payload)
    return tid


def _words(q: str) -> int:
    return len(re.findall(r"\w+", q or ""))


def store_answer(cx, t, payload: dict, obj: dict, model: str) -> tuple[bool, list[str]]:
    """Check the AI's name (group-name-v1): a quote of at least three whole words, found in the passage it names; a
    name that is only the list of the group's concepts is sent back. The answer is kept with the task (`results`);
    `apply` writes it as the group's name."""
    from .schema import GroupNameOut
    from .textutil import find_quote, grade_quote_problem, partial_word_hint

    out = GroupNameOut.model_validate(obj)
    ps = payload.get("passages") or []
    errors = []
    ev = out.name_quote
    if ev.passage < 1 or ev.passage > len(ps):
        errors.append(f"name_quote: there is no passage P{ev.passage}")
    elif grade_quote_problem(ev.quote) or _words(ev.quote) < MIN_QUOTE_WORDS:
        errors.append(f"name_quote: the quote {' '.join(ev.quote.split())[:80]!r} is too short: quote at least "
                      f"{MIN_QUOTE_WORDS} whole words, copied exactly")
    else:
        text = ps[ev.passage - 1]["text"]
        if not find_quote(text, ev.quote):
            errors.append(f"name_quote: quote not found in passage P{ev.passage}: {ev.quote[:80]!r}"
                          + partial_word_hint(text, ev.quote) + ". Copy it character for character, or quote a "
                          "shorter contiguous piece of it.")
    if payload.get("before") and _clean(out.name, MAX_NAME).lower() == _clean(payload["before"], MAX_NAME).lower():
        errors.append("name: it is the name drafted before, which the researcher asked to replace: give another")
    return not errors, errors


def apply(ws: Workspace, task_id: str) -> dict | None:
    """Write a task's accepted answer as its group's name (`ai_draft`), unless the researcher has named the group
    meanwhile. Returns the name's record, or None."""
    from .schema import GroupNameOut
    from .tasks import parse_json
    from .textutil import find_quote

    t = ws.query("SELECT payload_json, status FROM tasks WHERE task_id=?", (task_id,))
    if not t or t[0]["status"] != "done":
        return None
    r = ws.query("SELECT raw_json, model FROM results WHERE task_id=? AND valid=1 ORDER BY attempt DESC LIMIT 1",
                 (task_id,))
    if not r:
        return None
    payload = json.loads(t[0]["payload_json"])
    a = GroupNameOut.model_validate(parse_json(r[0]["raw_json"]))
    name = _clean(a.name, MAX_NAME).strip(" .\"“”'")
    if not name:
        return None
    name = name[:1].upper() + name[1:]
    p = payload["passages"][a.name_quote.passage - 1]
    hit = find_quote(p["text"], a.name_quote.quote)
    from . import solo as people  # Margin: one person

    me = people.me()   # the draft is the person's who asked for it
    concepts, labels = payload.get("concept_ids") or [], payload.get("labels") or {}
    with ws.connect() as cx:
        at = clock(cx)
        # the name the group has now: the one the task was asked for, or one given since to the same concepts
        recs = [dict(x) for x in cx.execute("SELECT name_id, source, concepts_json, updated_at FROM concept_group_names")]
        for x in recs:
            x["concepts"] = json.loads(x["concepts_json"] or "[]")
        nid = payload.get("name_id") if any(x["name_id"] == payload.get("name_id") for x in recs) else None
        groups, gi = payload.get("map_groups"), payload.get("group_index")
        if nid is None and isinstance(groups, list) and isinstance(gi, int) and 0 <= gi < len(groups):
            # a name given since to this group, as the map stood when the task was made: one another group of that map
            # takes (it shares a few concepts with this one) is that group's, and stays as it is
            groups = [[str(c) for c in x] for x in groups if isinstance(x, list)]
            took = match(recs, groups, {c for x in groups for c in x})
            nid = took[gi]["name_id"] if gi in took else None
        if nid and next(x for x in recs if x["name_id"] == nid)["source"] == "person":
            return None          # the researcher named it meanwhile: never overwritten
        nid = nid or uuid.uuid4().hex[:16]
        _change(cx, nid, at, me, name=name, source="ai_draft", model=r[0]["model"],
                concepts_json=json.dumps(concepts), labels_json=json.dumps(labels, ensure_ascii=False),
                filters_json=json.dumps(payload.get("filters") or {}, sort_keys=True), n=int(payload.get("n") or 0),
                person_id=me)
        cx.execute("DELETE FROM concept_group_quotes WHERE name_id=?", (nid,))
        _forget_failures(cx, concepts)        # named now: an earlier failure for it is no longer the page's news
        if hit:
            doc, start = cx.execute("SELECT doc_id, start FROM passages WHERE passage_id=?",
                                    (p["passage_id"],)).fetchone() or (None, None)
            if doc:
                cx.execute("INSERT INTO concept_group_quotes(name_id, doc_id, passage_id, page, start, end, quote) "
                           "VALUES (?,?,?,?,?,?,?)", (nid, doc, p["passage_id"], p.get("page"),
                                                      (start or 0) + hit[0], (start or 0) + hit[1],
                                                      " ".join(p["text"][hit[0]:hit[1]].split())))
    return {"name_id": nid, "name": name}


def name_groups(ws: Workspace, f, n: int, which: str, backend, model: str, progress: Callable | None = None,
                should_stop: Callable[[], bool] | None = None, settings: dict | None = None) -> dict:
    """The AI drafts a name for each group asked for (see `payloads`), as one job. Returns {"named", "failed",
    "groups", "skipped", "stopped", "model", "failures": [{"concepts", "reason"}]}. Written to the research log."""
    from . import access, home, researchlog, tasks
    from . import runs as runs_mod
    from .llm import BackendError

    s = settings if settings is not None else home.load_settings()
    readers = access.Readers(backend, model, settings=s, should_stop=should_stop)
    allowed = set(readers.main_levels) | ({"local"} if readers.local_configured() else set())
    got = payloads(ws, f, n, which, allowed, s)
    todo = [(gr, make_task(ws, p, model)) for gr, p in got["tasks"]]
    rid = runs_mod.start(ws, KIND, "concept map", backend, model, len(todo))
    done = failed = 0
    failures: list[dict] = []
    tally = threading.Lock()
    seen = [0]
    dflt = access.default(ws)
    level = {tid: readers.level_of(ws, tid) for _g, tid in todo}   # for the main model's provider
    local_ids = {tid for _g, tid in todo if level[tid] == "local" and "local" not in readers.main_levels}
    gated = bool(local_ids) and readers.defers()
    used_models: set[str] = set()

    def one(gr: dict, tid: str) -> None:
        nonlocal done, failed
        if should_stop and should_stop():
            return
        with tally:
            seen[0] += 1
        if progress:
            progress(min(seen[0], len(todo)), len(todo))
        with ws.connect() as cx:
            if access.recheck(cx, tid, dflt) is None:
                return
        rd = readers.for_task(ws, tid)
        if rd is None:
            return
        try:
            ok, errs = tasks.run_one(ws, tid, rd[0], rd[1])
        except BackendError:
            if should_stop and should_stop():
                return
            raise
        rec = apply(ws, tid) if ok else None
        last = ws.query("SELECT model FROM results WHERE task_id=? ORDER BY attempt DESC LIMIT 1", (tid,))
        with tally:
            if last and last[0]["model"]:
                used_models.add(last[0]["model"])
            if ok and rec:
                done += 1
            elif not ok and ws.scalar("SELECT status FROM tasks WHERE task_id=?", (tid,)) == "failed":
                failed += 1
                from .themes import naming_reason

                failures.append({"concepts": gr["concepts"], "reason": naming_reason(errs)})

    if gated:
        for gr, tid in todo:
            if tid in local_ids:
                readers.later(lambda gr=gr, tid=tid: one(gr, tid), noun="group", mixed=len(local_ids) < len(todo),
                              ws=ws)
    for gr, tid in todo:
        if should_stop and should_stop():
            break
        if gated and tid in local_ids:
            continue
        one(gr, tid)
    if gated:
        readers.drain()
    runs_mod.finish(ws, rid, done + failed)
    stopped = bool(should_stop and should_stop())
    used = ", ".join(sorted(used_models)) or model
    if done or failed:
        with ws.connect() as cx:
            text = (f"The AI ({used}) drafted names for {done} group{'s' if done != 1 else ''} of the concept map"
                    + (f"; {failed} could not be named" if failed else "")
                    + ". Each is a draft until it is used or renamed.")
            researchlog.record(cx, "concept-groups-named", text, "concept-map", "groups", "Concept map",
                               data={"model": used, "named": done, "failed": failed, "kind": KIND})
    return {"named": done, "failed": failed, "groups": len(todo), "skipped": got["skipped"], "stopped": stopped,
            "model": used, "failures": failures}


def demo_answer(payload: dict) -> dict:
    """The offline demo's name: the group's first two concepts and the start of its first passage, not read."""
    ps = payload.get("passages") or []
    words = ((ps[0]["text"] if ps else "") or "").split()
    quote = " ".join(words[:6]) if len(words) >= MIN_QUOTE_WORDS else "offline demo text"
    cs = payload.get("concepts") or ["these concepts"]
    words = concepts_name(cs[:2]).split()[:5]     # at most six words with "Demo:"
    return {"name": _clean("Demo: " + " ".join(words), MAX_NAME),
            "name_quote": {"passage": 1, "quote": quote}, "note": "Offline demo: no AI read the passages."}


def prompt_size(k: int, max_chars: int) -> int:
    """The longest prompt of a group's task, in characters (home.prompt_tokens)."""
    return 1500 + MAX_CHARS
