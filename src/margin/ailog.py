"""The AI log (I7 stage 3): who ran which AI work in a project, with which provider and model, when, about what, and
how many excerpts left the computer for it.

It is read from the ledger every cloud sending writes (`ai_sent`, access.record_sent): one row per passage sent, now
with the person who sent it (`person_id`, this installation's id) and the model (`model`, else the task's). One sending
(the passages of one task handed out at one moment, or one chat's search) is one row of the log. A colleague's rows
come with the sync like the rest of the ledger (sync/merge.py `_ai_work`), for the documents this copy holds; a row a
file brings in this person's own name that this copy does not hold names nobody (the same merge).

Rows written before (or by an older Margin) name no person: in a project never worked on with others they are this
person's; in a team the log says *not recorded*. Nothing here is a setting: the page is a record, reached from the
Research log's line under its title (#/log/ai), and it never sends anything.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import providers
from .store import Workspace

UNKNOWN = "unknown"   # the filter value for rows that name nobody
EXTRA_KINDS = {"search": "Search (a Claude chat)", "concept": "Concept (a Claude chat)",
               "profile": "Profile (a Claude chat)"}
SUBJECT_WORD = {"check": "Hypothesis", "codebook": "Codebook", "themes": "Themes", "document": "Document",
                "private": "About"}


def kind_words(feature: str | None) -> str:
    """The kind of task in plain words ("Check", "Profile (AI pass) (compare labels)")."""
    from .access import FEATURES

    f = (feature or "").strip()
    if not f:
        return "AI task"
    if f in FEATURES:
        return FEATURES[f]
    if f in EXTRA_KINDS:
        return EXTRA_KINDS[f]
    base, sep, rest = f.partition(" (")
    if sep and base in FEATURES:
        return f"{FEATURES[base]} ({rest}"
    return f[:1].upper() + f[1:]


def _grouped(cx: sqlite3.Connection) -> list[dict]:
    try:
        cur = cx.execute(
            "SELECT s.task_id, s.sent_at, s.route, COALESCE(s.provider, 'anthropic') AS prov, s.person_id, "
            "MAX(s.model) AS model, MAX(s.feature) AS feature, COUNT(DISTINCT s.passage_id) AS n, "
            "COUNT(DISTINCT s.doc_id) AS docs, MIN(s.doc_id) AS doc FROM ai_sent s "
            "GROUP BY s.task_id, s.sent_at, s.route, prov, s.person_id ORDER BY s.sent_at DESC, s.task_id")
    except sqlite3.OperationalError:  # a database not opened by this version yet (no person, no model)
        cur = cx.execute(
            "SELECT s.task_id, s.sent_at, s.route, COALESCE(s.provider, 'anthropic') AS prov, NULL AS person_id, "
            "NULL AS model, MAX(s.feature) AS feature, COUNT(DISTINCT s.passage_id) AS n, "
            "COUNT(DISTINCT s.doc_id) AS docs, MIN(s.doc_id) AS doc FROM ai_sent s "
            "GROUP BY s.task_id, s.sent_at, s.route, prov ORDER BY s.sent_at DESC, s.task_id")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


class _Lookup:
    """What the rows name, each looked up once: tasks, hypotheses, documents, theme runs, codebooks."""

    def __init__(self, ws: Workspace, cx: sqlite3.Connection):
        self.ws, self.cx = ws, cx
        self._fws: dict | None = None
        self._cache: dict[tuple, Any] = {}

    def _one(self, key: tuple, sql: str, args: tuple):
        if key not in self._cache:
            try:
                self._cache[key] = self.cx.execute(sql, args).fetchone()
            except sqlite3.Error:
                self._cache[key] = None
        return self._cache[key]

    def task(self, tid: str):
        return self._one(("task", tid), "SELECT kind, model, payload_json FROM tasks WHERE task_id=?", (tid,))

    def answered(self, tid: str) -> bool:
        return bool(self._one(("res", tid), "SELECT 1 FROM results WHERE task_id=? AND valid=1 LIMIT 1", (tid,)))

    def hypothesis(self, cid: str):
        got = self._one(("hyp", cid), "SELECT h.hyp_id, h.text FROM hypotheses h WHERE h.hyp_id=? UNION ALL "
                                      "SELECT h.hyp_id, h.text FROM user_claims c JOIN hypotheses h ON "
                                      "h.hyp_id=c.hyp_id WHERE c.claim_id=? LIMIT 1", (cid, cid))
        return got

    def document(self, doc_id: str):
        return self._one(("doc", doc_id), "SELECT doc_id, title FROM documents WHERE doc_id=?", (doc_id,))

    def theme_run(self, run_id: str):
        return self._one(("run", run_id), "SELECT run_id, created_at FROM theme_runs WHERE run_id=?", (run_id,))

    def codebook(self, name: str):
        if self._fws is None:
            try:
                from .frameworks import available

                self._fws = available(self.ws)
            except Exception:  # noqa: BLE001 - the codebook is named without a link
                self._fws = {}
        return self._fws.get(name)


def _subject(look: _Lookup, task_id: str | None, docs: int, doc: str | None) -> dict | None:
    """{"kind", "id", "title", "href"} of what a sending was about, from its task's id (and payload), or its one
    document; `href` only when the item is in this copy."""
    if task_id == "private":   # a colleague's work they have not shared: its task is masked (sharing._masked)
        return {"kind": "private", "id": None, "title": "work not shared with the team", "href": None}
    parts = (task_id or "").split(":")
    if parts and parts[0] == "second" and len(parts) > 2 and parts[1] == "check":
        parts = parts[1:]
    head = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else ""
    if head in ("check", "expand", "reread", "decompose") and arg:
        h = look.hypothesis(arg.split(";")[0])
        if h:
            return {"kind": "check", "id": h[0], "title": h[1] or "", "href": f"#/h/{h[0]}"}
        return {"kind": "check", "id": arg, "title": "", "href": None}
    if head == "label" and arg:
        fw = look.codebook(arg)
        return {"kind": "codebook", "id": arg, "title": fw.title if fw else arg,
                "href": f"#/codebooks/{arg}" if fw else None}
    if head == "theme" and arg:
        run = look.theme_run(arg)
        return {"kind": "themes", "id": arg, "title": "", "href": f"#/themes/{arg}" if run else None}
    if head in ("theory_codes", "resolve", "read_again") and arg:
        d = look.document(arg)
        return {"kind": "document", "id": arg, "title": d[1] if d else "", "href": f"#/doc/{arg}" if d else None}
    t = look.task(task_id) if task_id else None
    if t and t[2]:
        try:
            payload = json.loads(t[2])
        except ValueError:
            payload = {}
        fw_name = payload.get("framework") if isinstance(payload, dict) else None
        if isinstance(fw_name, str) and fw_name:
            fw = look.codebook(fw_name)
            return {"kind": "codebook", "id": fw_name, "title": fw.title if fw else fw_name,
                    "href": f"#/codebooks/{fw_name}" if fw else None}
    if docs == 1 and doc:
        d = look.document(doc)
        return {"kind": "document", "id": doc, "title": d[1] if d else "", "href": f"#/doc/{doc}" if d else None}
    return None


def entries(ws: Workspace, person: str | None = None, provider: str | None = None, offset: int = 0,
            limit: int = 200) -> dict:
    """The AI log, newest first: {"rows": [...], "total", "people": [{"id", "name", "me", "n"}],
    "providers": [{"id", "title", "n"}], "team"}. `person`: a person id, "me", or "unknown" (rows that name nobody);
    `provider`: a provider id. Each row: {"at", "person" ({"id", "name", "me"} | None), "provider", "provider_title",
    "route", "model", "kind", "kind_words", "excerpts", "documents", "subject" ({"kind", "word", "id", "title",
    "href"} | None; kind "private": a colleague's work they have not shared, whose task is masked), "task_id",
    "answered"}."""
    from . import people
    from .access import is_shared

    cx = ws._conn()
    me = people.me()
    names = people.names(ws)
    team = is_shared(cx, ws)
    look = _Lookup(ws, cx)
    rows = []
    for g in _grouped(cx):
        pid = g["person_id"] or (None if team else me)   # see the module's notes
        rows.append({**g, "pid": pid})
    count_people: dict[str, int] = {}
    count_prov: dict[str, int] = {}
    for r in rows:
        count_people[r["pid"] or UNKNOWN] = count_people.get(r["pid"] or UNKNOWN, 0) + 1
        count_prov[r["prov"]] = count_prov.get(r["prov"], 0) + 1
    want_person = me if person == "me" else person
    picked = [r for r in rows if (not want_person or (r["pid"] or UNKNOWN) == want_person)
              and (not provider or r["prov"] == provider)]
    out = []
    for r in picked[offset:offset + limit]:
        t = look.task(r["task_id"]) if r["task_id"] else None
        feature = r["feature"] or (t[0] if t else None)
        sub = _subject(look, r["task_id"], int(r["docs"] or 0), r["doc"])
        if sub is not None:
            sub["word"] = SUBJECT_WORD.get(sub["kind"], "")
        pid = r["pid"]
        out.append({"at": r["sent_at"] or "", "task_id": r["task_id"] or "",
                    "person": {"id": pid, "name": "you" if pid == me else names.get(pid, "a colleague"),
                               "me": pid == me} if pid else None,
                    "provider": r["prov"], "provider_title": providers.title(r["prov"]), "route": r["route"] or "",
                    "model": r["model"] or (t[1] if t else None) or "", "kind": feature or "",
                    "kind_words": kind_words(feature), "excerpts": int(r["n"] or 0),
                    "documents": int(r["docs"] or 0), "subject": sub,
                    "answered": bool(r["task_id"]) and look.answered(r["task_id"])})
    plist = sorted(count_people.items(), key=lambda kv: (kv[0] != me, kv[0] == UNKNOWN, names.get(kv[0], kv[0])))
    return {"rows": out, "total": len(picked), "team": team,
            "people": [{"id": k, "name": "you" if k == me else ("not named" if k == UNKNOWN else
                                                                names.get(k, "a colleague")),
                        "me": k == me, "n": n} for k, n in plist],
            "providers": [{"id": k, "title": providers.title(k), "n": n}
                          for k, n in sorted(count_prov.items(), key=lambda kv: -kv[1])]}
