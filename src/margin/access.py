"""Who may read each document with AI (0.11): per-document AI settings, the guard on every task, and the ledger of
what was sent to Claude.

Every document has one of three settings (`documents.ai_access`; NULL: the project's default, `ai_access_default` in
the project's config):

- ``cloud``  "Claude may read it": the chosen route (Claude Code, the Claude API, or a local model);
- ``local``  "Only a local AI": a model server on this computer, or a person;
- ``none``   "No AI": a person only (search, the keyword profile, concepts and themes without AI still work).

The setting is enforced in code where every AI task passes, never by an instruction in a prompt:

1. `label_payload` (called by `tasks._insert_task`) gives each task the most restricted setting of the documents its
   payload names (any `passage_id` or `doc_id`, at any depth), stored in `tasks.access`;
2. `require` (called by `tasks.run_one` before any backend is asked) refuses a `local` task on a route that leaves
   this computer and a `none` task on any route; the queue for Claude Code only ever hands out `cloud` tasks;
3. the features split their work so that each task is all-cloud or all-local (`Readers` picks the reader of each
   level), and the guard catches a feature that forgets to.

Every passage that leaves for a cloud model is written to `ai_sent` at that moment (`record_sent`), so the Documents
page can show how much of each document Claude has read. An optional cap per document (`documents.ai_budget`, a
percentage) treats a document as `local` for new tasks once Claude has read that share of it.

Cloud providers other than Claude (stage 1, providers.py): a `cloud` document may be read by the cloud providers it
allows (`documents.ai_providers`, a JSON list; NULL: the project's `ai_providers_default`, absent: Anthropic only, as
"Claude may read it" always meant). The rule is applied only where a caller names the provider that reads
(`provider=`): for it, a `cloud` document that does not allow it counts as `local`, as a reached cap does. Without a
provider every function gives the setting as the person chose it (what is stored, synced, shared and shown). The
decision points name theirs: the work split (`Readers.provider`, the backend's own), the guard (`require`, `may_read`),
the queue for Claude Code, the file queue and the connector (Anthropic), a remote embedder (its address). A model server
on this computer is no provider (None). In a shared project only Anthropic may read.

The stored setting of a task (`tasks.access`) is the one for the provider the project's tasks are labelled for
(`labels_provider`, the main route's; meta `ai_labels_for`, absent: Anthropic, as before), so that the queue, the waits
and the features' split of a job's tasks keep working from the column. A change of main route relabels a project the
next time the app opens it (`sync_labels`): stricter or looser, nothing stays strict. The queue for Claude Code holds
only tasks Anthropic may read, whatever the labels are for.
"""
from __future__ import annotations

import contextvars
import json
import sqlite3
from typing import Any, Callable, Iterable

from . import providers, routing
from .store import Workspace, now

LEVELS = ("cloud", "local", "none")
RANK = {"cloud": 0, "local": 1, "none": 2}
LABEL = {"cloud": "Claude may read it", "local": "Only a local AI", "none": "No AI"}
WHO = {"cloud": "The chosen route: Claude Code, the Claude API, or a local model",
       "local": "A local model server on this computer, or a person",
       "none": "A person only. Search, keyword Profile, Concepts and Themes without AI still work"}
OFF_COMPUTER = routing.OFF_COMPUTER  # one table for every module (0.11.1)
ROUTE_NAMES = routing.ROUTE_NAMES
PROMISE = ("Documents you mark as local stay on this computer. Margin never sends their text to Claude, in any "
           "feature, and shows you how much of every other document it has sent.")
_KEEP = object()
ANTHROPIC = providers.ANTHROPIC
SHARED_ONLY_ANTHROPIC = ("Other providers come to shared projects later: your colleagues have not agreed to them. "
                         "Only Anthropic may read this project's documents.")


# ---------------------------------------------------------------------------------------------
# which cloud provider reads (stage 1 of other cloud providers)
# ---------------------------------------------------------------------------------------------
_SCOPE = object()    # the default: the provider `reading_for` set around the code (the add-ons' floors), else none
_LABELS = object()   # the provider the project's stored task settings are for (`labels_provider`)
_UNSET = object()
ROUTE_PROVIDER: contextvars.ContextVar = contextvars.ContextVar("margin_route_provider", default=None)
LABELS_KEY = "ai_labels_for"
_AUTO: dict = {"url": None}   # the server the automatic local route chose last (home._make_backend)


def auto_chose(url: str | None) -> None:
    """The automatic local route chose this server (its provider is the route's, not an address left unused)."""
    _AUTO["url"] = url


def route_provider(settings: dict) -> str | None:
    """The provider of the main route the settings describe: Anthropic for Claude Code and the Claude API, the chosen
    one for another cloud provider, None for a model server on this computer (or the offline demo), the provider of
    its address for a server on another computer (`other` when it is none of the table's)."""
    b = settings.get("backend", "auto")
    if b in providers.ROUTE_PROVIDER:
        return providers.ROUTE_PROVIDER[b]
    if b == providers.CLOUD_ROUTE:
        p = settings.get("cloud_provider") or ""
        return p if p in providers.CLOUD_IDS else providers.OTHER
    if b == "baseline":
        return None
    if b == "openai":
        return providers.of_url(settings.get("openai_url") or "")
    if b == "ollama":
        return providers.of_url(settings.get("ollama_url") or "")
    # auto: the server it chose (on this computer unless an address set in Settings answered first)
    return providers.of_url(_AUTO["url"]) if _AUTO["url"] else None


def route_address(settings: dict) -> str | None:
    """The address of the main route's server when it is on another computer (for the line that says it reads only
    the documents allowed to it), else None."""
    b = settings.get("backend", "auto")
    url = {"openai": settings.get("openai_url"), "ollama": settings.get("ollama_url")}.get(b, _AUTO["url"] if b == "auto"
                                                                                          else None)
    return url if url and not providers.on_this_computer(url) else None


def labels_provider(cx) -> str | None:
    """The provider the project's stored task settings are for (Anthropic until `sync_labels` says otherwise)."""
    try:
        row = cx.execute("SELECT value FROM meta WHERE key=?", (LABELS_KEY,)).fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        return ANTHROPIC
    try:
        return json.loads(row[0]) or None
    except (ValueError, TypeError):
        return ANTHROPIC


def sync_labels(ws: Workspace, provider) -> int:
    """Give the project's open tasks their settings for `provider` (the main route's), once per change of it: looser
    or stricter. Returns the number of tasks changed. Only reads, unless the provider changed (it is asked on every
    request of the app: it never waits for other work on the database)."""
    if labels_provider(ws._conn()) == provider:
        return 0
    with ws.connect() as cx:
        if labels_provider(cx) == provider:
            return 0
        return relabel(cx, provider=provider)


def _resolve(provider, cx=None):
    if provider is _SCOPE:
        return ROUTE_PROVIDER.get()
    if provider is _LABELS:
        return labels_provider(cx) if cx is not None else ANTHROPIC
    return provider


class reading_for:
    """`with access.reading_for(provider):` the functions inside that are not told a provider work out the settings for
    this one (used around the add-ons' floors, which are asked without one)."""

    def __init__(self, provider):
        self.provider = provider

    def __enter__(self):
        self._token = ROUTE_PROVIDER.set(self.provider)
        return self

    def __exit__(self, *exc):
        ROUTE_PROVIDER.reset(self._token)
        return False


def provider_of(backend) -> str | None:
    """The provider a backend is (None: it reads on this computer). Backends say it themselves (llm.py); a stand-in
    without it is known by its name (Claude's routes) or its address."""
    if backend is None:
        return None
    p = getattr(backend, "provider", _UNSET)
    if p is not _UNSET:
        return p
    name = getattr(backend, "name", "") or ""
    if name in providers.ROUTE_PROVIDER:
        return providers.ROUTE_PROVIDER[name]
    if name == "baseline":
        return None
    url = getattr(backend, "base_url", None)
    if url is not None:
        return providers.of_url(url)
    if name in OFF_COMPUTER:
        return providers.OTHER
    return None


def providers_default(ws: Workspace) -> list[str]:
    """The cloud providers that may read the project's `cloud` documents without their own choice (Anthropic only
    until the person allows more)."""
    v = ws.config.get("ai_providers_default")
    if v is None:
        return list(providers.DEFAULT_ALLOWED)
    try:
        return providers.clean_list(v)
    except ValueError:
        return list(providers.DEFAULT_ALLOWED)


_WS_FOR_PATH: dict = {}   # a Workspace per project folder, so its own config cache serves the lookups from a connection


def _ws_of(cx) -> Workspace | None:
    from pathlib import Path

    try:
        path = cx.execute("PRAGMA database_list").fetchone()[2]
    except (sqlite3.Error, TypeError):
        path = ""
    if not path:
        return None
    root = str(Path(path).parent)
    ws = _WS_FOR_PATH.get(root)
    if ws is None:
        if len(_WS_FOR_PATH) > 64:
            _WS_FOR_PATH.clear()
        ws = _WS_FOR_PATH[root] = Workspace(root)
    return ws


def is_shared(cx, ws: Workspace | None = None) -> bool:
    """Whether the project is worked on with colleagues (teamcodebooks.is_team: an owner's chain, an exchange, a
    shared folder or a storage space). When that cannot be said: shared (only Anthropic reads)."""
    try:
        from .teamcodebooks import is_team

        return bool(is_team(cx, ws))
    except Exception:  # noqa: BLE001
        return True


def _own_list(raw) -> list[str] | None:
    """A document's own list of providers (None: the project's). One that cannot be read allows none."""
    if raw in (None, ""):
        return None
    try:
        got = json.loads(raw) if isinstance(raw, str) else raw
        return [p for p in got if p in providers.ALLOWABLE] if isinstance(got, list) else []
    except (ValueError, TypeError):
        return []


class _Allow:
    """Whether a `cloud` document allows the provider that reads, looked up once per call: the project's default and
    whether it is shared are read only when needed."""

    def __init__(self, cx, ws: Workspace | None, provider: str):
        self.cx, self.ws, self.provider = cx, ws, provider
        self._dflt: list[str] | None = None
        self._shared: bool | None = None

    def _ws(self) -> Workspace | None:
        if self.ws is None and self.cx is not None:
            self.ws = _ws_of(self.cx)
        return self.ws

    def default(self) -> list[str]:
        if self._dflt is None:
            ws = self._ws()
            self._dflt = providers_default(ws) if ws is not None else list(providers.DEFAULT_ALLOWED)
        return self._dflt

    def shared(self) -> bool:
        if self._shared is None:
            self._shared = is_shared(self.cx, self._ws())
        return self._shared

    def allows(self, raw) -> bool:
        own = _own_list(raw)
        if self.provider not in (own if own is not None else self.default()):
            return False
        return self.provider == ANTHROPIC or not self.shared()


class AccessError(RuntimeError):
    """A task was about to be handed to a model its documents' settings do not allow (a bug in a feature: the guard
    stops it before anything is sent)."""


def clean(value: Any, allow_empty: bool = False) -> str | None:
    v = str(value or "").strip().lower()
    if not v and allow_empty:
        return None
    aliases = {"claude": "cloud", "local_only": "local", "local-only": "local", "no_ai": "none", "no-ai": "none",
               "person": "none"}
    v = aliases.get(v, v)
    if v not in LEVELS:
        raise ValueError("The AI setting must be cloud (Claude may read it), local (only a local AI) or none (no AI).")
    return v


def most(levels: Iterable[str | None]) -> str:
    """The most restricted of these settings (cloud when there are none)."""
    out = "cloud"
    for lv in levels:
        if lv and RANK.get(lv, 2) > RANK[out]:
            out = lv if lv in RANK else "none"
    return out


# ---------------------------------------------------------------------------------------------
# the project's default and the settings of documents
# ---------------------------------------------------------------------------------------------
def _local_only() -> bool:
    from .home import local_only

    return local_only()


def default_chosen(ws: Workspace) -> bool:
    """Whether the project's default has been chosen (a new project asks once, with nothing preselected)."""
    return ws.config.get("ai_access_default") in LEVELS


def default(ws: Workspace) -> str:
    """The setting of documents without their own: the project's choice; before it is made, as 0.10 did (Claude
    may read them), or `local` on an installation without cloud models."""
    v = ws.config.get("ai_access_default")
    if v == "cloud" and _local_only():
        return "local"
    if v in LEVELS:
        return v
    return "local" if _local_only() else "cloud"


def _write_config(ws: Workspace, changes: dict) -> None:
    try:
        cfg = json.loads(ws.config_path.read_text(encoding="utf-8")) if ws.config_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        cfg = {}
    cfg.update(changes)
    ws.config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    ws._config_cache = None
    held = _WS_FOR_PATH.get(str(ws.root))
    if held is not None:
        held._config_cache = None


def set_default(ws: Workspace, value: str) -> str:
    v = clean(value)
    if v == "cloud" and _local_only():
        raise ValueError("Cloud models are switched off on this computer by whoever installed Margin: documents can be "
                         "read by a local AI or by you only.")
    before = default(ws) if default_chosen(ws) else None
    _write_config(ws, {"ai_access_default": v, "ai_access_ask": False})
    with ws.connect() as cx:
        relabel(cx)
        if before is not None and before != v:  # 0.16: a decision about privacy goes into the research log
            from . import researchlog

            researchlog.record(cx, "ai-access", f"New documents of this project: {researchlog.access_words(v, True)} "
                                                f"(before: {researchlog.access_words(before, True)}).",
                               data={"default": v})
    try:  # 0.18 L2: a looser default opens no document of the project to more AI than its owner accepted
        from .ownership import settle

        settle(ws, apply=False)
    except ImportError:
        pass
    return v


def shares(cx_or_ws, doc_ids: Iterable[str] | None = None, by_provider: bool = False) -> dict[str, dict]:
    """How much of each document Claude has read: {doc_id: {"sent_chars", "chars", "share" (0..1), "passages"}}. The
    cap counts what every cloud provider read. `by_provider`: also "by" ({provider: share}; a ledger row without a
    provider, written before stage 1 or by an older copy of a colleague, was Claude's)."""
    q = cx_or_ws.execute if isinstance(cx_or_ws, sqlite3.Connection) else cx_or_ws._conn().execute
    ids = list(doc_ids) if doc_ids is not None else [r[0] for r in q("SELECT doc_id FROM documents")]
    out: dict[str, dict] = {}
    if not ids:
        return out
    marks = ",".join("?" * len(ids))
    total = {r[0]: int(r[1] or 0) for r in q(f"SELECT doc_id, SUM(LENGTH(text)) FROM passages WHERE doc_id IN ({marks}) "
                                              "GROUP BY doc_id", ids)}
    sent: dict[str, tuple[int, int]] = {}
    by_prov: dict[str, dict[str, int]] = {}
    if by_provider:   # one pass over the ledger: each passage once in all, and once per provider that read it
        try:
            rows = q(f"SELECT p.doc_id, p.passage_id, s.prov, LENGTH(p.text) FROM passages p JOIN (SELECT DISTINCT "
                     f"passage_id, COALESCE(provider, 'anthropic') AS prov FROM ai_sent WHERE doc_id IN ({marks})) s "
                     f"ON s.passage_id=p.passage_id", ids).fetchall()
        except sqlite3.OperationalError:  # a database without the column
            rows = [(d, p, ANTHROPIC, n) for d, p, n in q(
                f"SELECT p.doc_id, p.passage_id, LENGTH(p.text) FROM passages p JOIN (SELECT DISTINCT passage_id FROM "
                f"ai_sent WHERE doc_id IN ({marks})) s ON s.passage_id=p.passage_id", ids).fetchall()]
        seen: set[str] = set()
        for d, pid, prov, n in rows:
            by_prov.setdefault(d, {})
            by_prov[d][prov] = by_prov[d].get(prov, 0) + int(n or 0)
            if pid not in seen:
                seen.add(pid)
                c, k = sent.get(d, (0, 0))
                sent[d] = (c + int(n or 0), k + 1)
    else:
        sent = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in q(
            f"SELECT p.doc_id, SUM(LENGTH(p.text)), COUNT(*) FROM passages p JOIN (SELECT DISTINCT passage_id FROM "
            f"ai_sent WHERE doc_id IN ({marks})) s ON s.passage_id=p.passage_id GROUP BY p.doc_id", ids)}
    # 0.15: a document read again with the new reader (reread.py): the share Claude had read of passages that have
    # no place in the new reading (their ledger rows name no passage now) still counts, on top of what it reads now
    try:
        before = {r[0]: float(r[1]) for r in q(f"SELECT doc_id, sent_share FROM documents WHERE doc_id IN ({marks}) "
                                               "AND sent_share IS NOT NULL", ids)}
    except sqlite3.OperationalError:  # a database without the column
        before = {}
    for d in ids:
        chars = total.get(d, 0)
        sc, n = sent.get(d, (0, 0))
        share = (sc / chars if chars else 0.0) + before.get(d, 0.0)
        out[d] = {"sent_chars": sc, "chars": chars, "passages": n, "share": round(min(1.0, share), 4)}
        if by_provider:
            out[d]["by"] = {p: round(min(1.0, c / chars), 4) for p, c in by_prov.get(d, {}).items()} if chars else {}
    return out


def levels(cx_or_ws, doc_ids: Iterable[str] | None = None, budget: bool = True,
           dflt: str | None = None, provider=_SCOPE, _allow: "_Allow | None" = None) -> dict[str, str]:
    """The setting that applies to each document now: its own, else the project's default; a `cloud` document whose
    cap is reached counts as `local` (with `budget`). `dflt` is the project's default when the caller has it already
    (a loop over many tasks: finding it means reading the project's config). 0.14.3: a colleague's reading of a file
    you have too (a sync-clash copy of a document) is at least as restricted as your document of that file, so making
    yours stricter makes the copy stricter too. Stage 1 of other cloud providers: with a `provider` (the one that
    reads), a `cloud` document that does not allow it counts as `local`; without one (None: a model on this computer,
    or the setting as the person chose it, which is what is stored, synced and shown) it stays `cloud`."""
    if isinstance(cx_or_ws, sqlite3.Connection):
        cx = cx_or_ws
        ws = None
        q = cx.execute
    else:
        ws = cx_or_ws
        cx = ws._conn()
        q = cx.execute
    if dflt is None:
        dflt = default(ws) if ws is not None else _default_from_cx(cx)
    ids = list(dict.fromkeys(doc_ids)) if doc_ids is not None else None
    if ids is not None and not ids:
        return {}
    copies: dict[str, str] = {}
    if ids is None or any("-" in d for d in ids):  # a copy's id is "<id of the file>-<mark>" (sync.py)
        try:
            copies = {k: o for k, o in q("SELECT key, of_key FROM sync_copies WHERE kind='document'").fetchall()
                      if ids is None or k in ids}
        except sqlite3.OperationalError:  # a database without the table (not opened by 0.14 yet)
            copies = {}
    wanted = ids if ids is None else ids + [o for o in copies.values() if o not in ids]
    where = f" WHERE doc_id IN ({','.join('?' * len(wanted))})" if wanted is not None else ""
    try:
        rows = q("SELECT doc_id, ai_access, ai_budget, ai_providers FROM documents" + where, wanted or []).fetchall()
    except sqlite3.OperationalError:  # a database without the column (not opened by this version yet)
        rows = [(*r, None) for r in q("SELECT doc_id, ai_access, ai_budget FROM documents" + where,
                                       wanted or []).fetchall()]
    out: dict[str, str] = {}
    capped = []
    only_local = _local_only()
    prov = _resolve(provider, cx)
    allow = None if prov is None else (_allow if _allow is not None and _allow.provider == prov
                                       else _Allow(cx, ws, prov))
    for r in rows:
        lv = r[1] if r[1] in LEVELS else dflt
        if lv == "cloud" and only_local:
            lv = "local"
        if lv == "cloud" and allow is not None and not allow.allows(r[3]):
            lv = "local"   # this provider may not read it: as Only a local AI, for this route
        out[r[0]] = lv
        if budget and lv == "cloud" and r[2] is not None:
            capped.append((r[0], float(r[2])))
    if capped:
        sh = shares(cx, [d for d, _b in capped])
        for d, b in capped:
            if sh[d]["share"] * 100 >= b:
                out[d] = "local"
    for k, o in copies.items():
        if k in out and o in out:
            out[k] = most([out[k], out[o]])
    if ids is not None:
        out = {d: out[d] for d in ids if d in out}  # not the originals looked up for their copies
        for d in ids:  # a document removed since: what was read from it stays as it was; nothing new is sent
            out.setdefault(d, "none")
    return out


def _default_from_cx(cx: sqlite3.Connection) -> str:
    """The project's default when only a connection is at hand (inside a transaction)."""
    from pathlib import Path

    path = cx.execute("PRAGMA database_list").fetchone()[2]
    return default(Workspace(Path(path).parent)) if path else ("local" if _local_only() else "cloud")


def doc_of_passages(cx, passage_ids: Iterable[str]) -> dict[str, str]:
    ids = list(dict.fromkeys(passage_ids))
    out: dict[str, str] = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        for r in cx.execute(f"SELECT passage_id, doc_id FROM passages WHERE passage_id IN ({','.join('?' * len(chunk))})",
                            chunk):
            out[r[0]] = r[1]
    return out


def _walk(obj: Any, pids: set, dids: set) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "passage_id" and isinstance(v, str):
                pids.add(v)
            elif k == "doc_id" and isinstance(v, str):
                dids.add(v)
            else:
                _walk(v, pids, dids)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk(v, pids, dids)


def ids_in(payload: Any) -> tuple[set[str], set[str]]:
    """The passage ids and document ids a payload names, at any depth."""
    pids: set[str] = set()
    dids: set[str] = set()
    _walk(payload, pids, dids)
    return pids, dids


# ---------------------------------------------------------------------------------------------
# 0.13.6: hooks for add-ons (docs/EXTENDING.md). They only ever restrict more: a floor raises the setting a task must
# keep, and hidden hypotheses are left out of the connector. local_only() and the documents' own settings still
# decide; an add-on cannot loosen them.
# ---------------------------------------------------------------------------------------------
_FLOORS: list[Callable] = []
_HIDDEN: list[Callable] = []


def register_floor(fn: Callable) -> Callable:
    """`fn(cx, payload, dflt)` says how far a task's text may go because of what the add-on knows about it ("cloud",
    "local" or "none"; None: nothing to say), for instance text the add-on manages that has an AI setting of its
    own. The task keeps the most restricted of that and its documents' settings. Returns `fn`; registering it again
    changes nothing."""
    if fn not in _FLOORS:
        _FLOORS.append(fn)
    return fn


def register_hidden(fn: Callable) -> Callable:
    """`fn(ws)` returns the ids of hypotheses the connector (a Claude chat) must not show or open. Returns `fn`."""
    if fn not in _HIDDEN:
        _HIDDEN.append(fn)
    return fn


def _core_hooks() -> None:
    """0.19.0 (N3): Margin's own floor and hidden rule, by the same hooks: the words of a check started from a
    document's text (`hypotheses.origin` "document") keep that document's AI setting, and the connector does not
    show such a check when the document is not `cloud` (docrole.origin_floor, docrole.kept_here)."""
    from . import docrole

    register_floor(docrole.origin_floor)
    register_hidden(docrole.kept_here)


_core_hooks()


def _hooks(kind: list) -> list[Callable]:
    from .addons import load

    load()  # an add-on package registers its hooks when it is imported: never decide before that
    return list(kind)


def floor(cx, payload: Any, dflt: str | None = None, provider=_SCOPE) -> str:
    """The most restricted setting the add-ons' floors give a payload (`cloud`: none restricts it). A floor that
    fails counts as `none`: when in doubt, the text stays on this computer and no AI reads it. The floors are asked
    for `provider`'s reading (`reading_for` around them: a floor that looks at a document's setting asks for it)."""
    prov = _resolve(provider, cx)
    out = []
    for fn in _hooks(_FLOORS):
        try:
            with reading_for(prov):
                lv = fn(cx, payload, dflt)
        except Exception:  # noqa: BLE001
            lv = "none"
        if lv is not None:
            out.append(lv if lv in LEVELS else "none")
    return most(out) if out else "cloud"


def hidden_hypotheses(ws: Workspace) -> set[str]:
    """The hypotheses the add-ons keep out of the connector."""
    out: set[str] = set()
    for fn in _hooks(_HIDDEN):
        try:
            out |= set(fn(ws) or ())
        except Exception:  # noqa: BLE001 - a hook that fails hides every hypothesis it could be about: all of them
            return {r[0] for r in ws.query("SELECT hyp_id FROM hypotheses")}
    return out


def label_payload(cx, payload: Any, dflt: str | None = None, budget: bool = True, provider=_SCOPE) -> str:
    """The most restricted setting of the documents a task's payload names (`cloud` for a task without document
    text, such as the search words of a hypothesis). A passage no longer in the project counts as its document.
    0.13.6: and of the add-ons' floors for it. Without `budget`, a document's cap is left out (the setting a person
    chose for it alone). `provider`: whose reading it is (see `levels`)."""
    prov = _resolve(provider, cx)
    fl = floor(cx, payload, dflt, prov)
    out = _label_docs(cx, payload, dflt, budget, prov)
    return most([fl, out]) if fl != "cloud" else out


def _label_docs(cx, payload: Any, dflt: str | None = None, budget: bool = True, provider=_SCOPE) -> str:
    pids, dids = ids_in(payload)
    if not pids and not dids:
        return "cloud"
    by_p = doc_of_passages(cx, pids)
    docs = set(dids) | set(by_p.values())
    missing = pids - set(by_p)
    lv = levels(cx, docs, budget=budget, dflt=dflt, provider=provider) if docs else {}
    out = most(lv.values())
    if missing and not docs:
        return "none"  # passages of a removed document, and nothing else to go by: keep them here
    return out


class _Known:
    """`label_payload` for many tasks in one transaction: each document's setting (`levels` of that document alone,
    as `_label_docs` asks for it) and each passage's document are looked up once, the passages of many tasks in one
    query (`prefetch`)."""

    def __init__(self, cx, dflt: str, provider=_LABELS):
        self.cx, self.dflt = cx, dflt
        self.provider = _resolve(provider, cx)
        self.queue_allow = _Allow(cx, None, ANTHROPIC)
        self.allow = _Allow(cx, None, self.provider) if self.provider is not None else None
        self.level: dict[str, str] = {}
        self.doc_of: dict[str, str | None] = {}

    def prefetch(self, pids: Iterable[str]) -> None:
        new = [p for p in dict.fromkeys(pids) if p not in self.doc_of]
        if new:
            got = doc_of_passages(self.cx, new)
            self.doc_of.update({p: got.get(p) for p in new})

    def label(self, payload: Any) -> str:
        fl = floor(self.cx, payload, self.dflt, self.provider)
        pids, dids = ids_in(payload)
        if not pids and not dids:
            out = "cloud"
        else:
            self.prefetch(pids)
            by_p = {p: self.doc_of[p] for p in pids if self.doc_of[p] is not None}
            docs = set(dids) | set(by_p.values())
            if pids - set(by_p) and not docs:
                out = "none"  # passages of a removed document, and nothing else to go by: keep them here
            else:
                for d in docs:
                    if d not in self.level:
                        self.level[d] = levels(self.cx, [d], dflt=self.dflt, provider=self.provider,
                                               _allow=self.allow)[d]
                out = most(self.level[d] for d in docs)
        return most([fl, out]) if fl != "cloud" else out


def relabel(cx, task_ids: Iterable[str] | None = None, provider=_LABELS) -> int:
    """Give the tasks not answered yet the setting of their documents now (after a setting changed). A task that is
    no longer `cloud` is taken out of the queue for Claude Code (a batch already handed out has left). Returns the
    number of tasks whose setting changed.

    Every open task is worked out again, not only those whose text names a changed document: an add-on's floor may
    look at any document through its own tables, and a task labelled before its document's cap was reached is
    corrected here too. What the tasks share is looked up once per call instead (each document's setting, each
    passage's document): nothing a task's setting depends on changes while this runs. The settings are those for the
    provider the project's tasks are labelled for (`labels_provider`); given another one, the project's tasks are
    labelled for it from now on (`sync_labels`). A task in the queue that the queue's provider may not read leaves
    it, whatever the labels are for (stage 2: the queue is the main route's when that is an agent route, Codex's for
    OpenAI, else Claude Code's, for Anthropic)."""
    from .taskqueue import OPEN, queue_provider

    sql = f"SELECT task_id, payload_json, access FROM tasks WHERE {OPEN}"
    args: list = []
    if task_ids is not None:
        ids = list(task_ids)
        if not ids:
            return 0
        sql += f" AND task_id IN ({','.join('?' * len(ids))})"
        args = ids
    n = 0
    dflt = _default_from_cx(cx)  # once, not per task (0.11.1: a settings change on a big project took seconds)
    known = _Known(cx, dflt, provider)
    try:
        known.queue_provider = queue_provider()
    except Exception:  # noqa: BLE001 - settings that cannot be read this moment: the queue as before stage 2
        known.queue_provider = ANTHROPIC
    if provider is not _LABELS and task_ids is None:
        cx.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (LABELS_KEY, json.dumps(known.provider or "")))
    sql = sql.replace("SELECT task_id, payload_json, access", "SELECT task_id, payload_json, access, queued")
    rows = cx.execute(sql, args).fetchall()
    for i in range(0, len(rows), 500):  # a chunk's passages in one query, then its tasks
        chunk = []
        for r in rows[i:i + 500]:
            try:
                chunk.append((r, json.loads(r["payload_json"] or "{}")))
            except (ValueError, TypeError):
                chunk.append((r, None))
        known.prefetch(p for _r, pl in chunk for p in ids_in(pl)[0])
        for r, payload in chunk:
            n += _relabel_one(cx, r, known, payload)
    return n


def _relabel_one(cx, r, known: _Known, payload: Any) -> int:
    try:
        lv = known.label(payload) if payload is not None else "none"
    except (ValueError, TypeError):
        lv = "none"
    queue_lv = lv
    qp = getattr(known, "queue_provider", ANTHROPIC)
    if lv == "cloud" and known.provider != qp and r["queued"]:   # the queue's provider's reading (Claude Code: Anthropic)
        try:
            queue_lv = label_payload(cx, payload, known.dflt, provider=qp)
        except (ValueError, TypeError):
            queue_lv = "none"
    if queue_lv != "cloud":
        cx.execute("UPDATE tasks SET queued=0, queued_at=NULL, claimed_by=NULL, claimed_at=NULL WHERE task_id=? "
                   "AND COALESCE(queued, 0)=1", (r["task_id"],))
    if lv != (r["access"] or "cloud"):
        cx.execute("UPDATE tasks SET access=? WHERE task_id=?", (lv, r["task_id"]))
        return 1
    return 0


def _all_sent(cx, payload: Any) -> bool:
    """Whether Claude has read every passage this payload would show (with the passages shown as their context):
    sending it again adds nothing to the share a cap counts."""
    pids, _dids = ids_in(payload)
    if not pids:
        return False
    pids = _with_context(cx, payload, pids)
    ids = sorted(pids)
    seen: set[str] = set()
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        seen |= {r[0] for r in cx.execute(f"SELECT DISTINCT passage_id FROM ai_sent WHERE passage_id IN "
                                          f"({','.join('?' * len(chunk))})", chunk)}
    return seen >= pids


def recheck(cx, task_id: str, dflt: str | None = None, budget: bool = True, provider=_LABELS) -> str | None:
    """The setting of a task at the moment its text is about to leave, worked out again from its payload instead of
    trusted from `tasks.access` (a path that brings a task back and forgets to relabel it, or a cap reached by the
    tasks sent just before it in the same batch). It is never looser than the stored one: only `relabel`, after a
    person changed a setting, loosens a task. A stricter one is written to the task, which then leaves the queue for
    Claude Code (as `relabel` does). With `budget`, a document's cap counts too, unless Claude has read all this task
    would show already (a second attempt, or the stronger model's reading, adds nothing to what it has read).
    Returns None when the task is gone. Runs in the caller's transaction, per task sent. `provider`: whose reading
    it is (the queue for Claude Code: Anthropic; a backend: its own); a stricter setting for a provider the project's
    tasks are not labelled for is returned and not written."""
    row = cx.execute("SELECT access, payload_json FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        return None
    labels = labels_provider(cx)
    prov = labels if provider is _LABELS else provider
    stored, lv = _level_now(cx, row, dflt, budget, prov)
    if lv != (row[0] if row[0] in LEVELS else "cloud") and prov == labels:
        cx.execute("UPDATE tasks SET access=? WHERE task_id=?", (lv, task_id))
        if lv != "cloud":
            cx.execute("UPDATE tasks SET queued=0, queued_at=NULL WHERE task_id=? AND COALESCE(queued, 0)=1",
                       (task_id,))
    return lv


def would_leave(cx, task_id: str, dflt: str | None = None, provider=ANTHROPIC) -> bool:
    """Whether the task's text would leave for a cloud model now, as `recheck` would find it, without writing
    anything (the preview of what Claude Code is sent: Anthropic's reading)."""
    row = cx.execute("SELECT access, payload_json FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    return row is not None and _level_now(cx, row, dflt, True, provider)[1] == "cloud"


def _level_now(cx, row, dflt: str | None, budget: bool, provider=None) -> tuple[str, str]:
    """(the stored setting, the setting worked out again) of a task row (access, payload_json): see `recheck`. For a
    provider the project's tasks are not labelled for, the stored setting counts only when it is No AI (its Only a
    local AI may be the labels' provider's alone)."""
    stored = row[0] if row[0] in LEVELS else "cloud"
    if stored == "local" and provider != labels_provider(cx):
        stored = "cloud"
    lv = stored
    if stored != "none":
        try:
            payload = json.loads(row[1] or "{}")
        except (ValueError, TypeError):
            payload, lv = None, "none"
        if payload is not None:
            lv = most([stored, label_payload(cx, payload, dflt=dflt, budget=False, provider=provider)])
            if budget and lv == "cloud":
                capped = _label_docs(cx, payload, dflt, budget=True, provider=provider)
                if capped != "cloud" and not _all_sent(cx, payload):
                    lv = capped
    return stored, lv


def _check_allowance(ws: Workspace, plist: list[str]) -> None:
    """A list of providers other than Anthropic is refused in a shared project (R5: the allowance does not travel with
    a team yet, so colleagues have not agreed to it)."""
    if any(p != ANTHROPIC for p in plist) and is_shared(ws._conn(), ws):
        raise ValueError(SHARED_ONLY_ANTHROPIC)


def _providers_words(plist: list[str] | None) -> str:
    if plist is None:
        return "the project's choice"
    return ", ".join(providers.title(p) for p in plist)


def set_providers_default(ws: Workspace, value) -> list[str]:
    """The cloud providers that may read the project's `cloud` documents without their own choice. Takes effect for
    every task not answered yet; goes into the research log."""
    plist = providers.clean_list(value)
    _check_allowance(ws, plist)
    before = providers_default(ws)
    _write_config(ws, {"ai_providers_default": plist})
    with ws.connect() as cx:
        relabel(cx)
        if before != plist:
            from . import researchlog

            researchlog.record(cx, "ai-access", f"Cloud providers that may read documents marked Cloud AI may read it: "
                                                f"{_providers_words(plist)} (before: {_providers_words(before)}).",
                               data={"providers_default": plist})
    return plist


def set_documents(ws: Workspace, doc_ids: list[str], setting: Any = _KEEP, note: Any = _KEEP,
                  budget: Any = _KEEP, allow: Any = _KEEP) -> dict:
    """Change the AI setting (and/or the note, the cap, the cloud providers it allows: `allow`, a list, or None for
    the project's choice) of documents. `setting` None returns them to the project's default. Takes effect for every
    task not answered yet."""
    if not doc_ids:
        raise ValueError("Choose at least one document.")
    plist = None
    if allow is not _KEEP and allow is not None:
        plist = providers.clean_list(allow)
        _check_allowance(ws, plist)
    lv = None
    if setting is not _KEEP:
        lv = clean(setting, allow_empty=True)
        if lv == "cloud" and _local_only():
            raise ValueError("Cloud models are switched off on this computer by whoever installed Margin.")
    if budget is not _KEEP and budget not in (None, ""):
        try:
            budget = float(budget)
        except (TypeError, ValueError):
            raise ValueError("The cap must be a percentage from 1 to 100, or empty for none.") from None
        if not 1 <= budget <= 100:
            raise ValueError("The cap must be a percentage from 1 to 100, or empty for none.")
    elif budget == "":
        budget = None
    with ws.connect() as cx:
        found = {r[0] for r in cx.execute(f"SELECT doc_id FROM documents WHERE doc_id IN ({','.join('?' * len(doc_ids))})",
                                          list(doc_ids))}
        unknown = [d for d in doc_ids if d not in found]
        if unknown:
            raise KeyError(unknown[0])
        held: dict[str, str] = {}
        if setting is not _KEEP:
            try:  # 0.18 L2: in a collaborator's copy a setting looser than the project's is proposed to the owner
                from .ownership import hold_loosening

                held = hold_loosening(ws, cx, doc_ids, lv)
            except ImportError:  # an app without shared projects
                pass
        if setting is not _KEEP:  # 0.16: a decision about privacy goes into the research log
            was = {r[0]: r[1] for r in cx.execute(f"SELECT doc_id, ai_access FROM documents WHERE doc_id IN "
                                                  f"({','.join('?' * len(doc_ids))})", list(doc_ids))}
            moved = [d for d in doc_ids if was.get(d) != lv and d not in held]
            if moved:
                from . import researchlog

                titles = {r[0]: r[1] for r in cx.execute(f"SELECT doc_id, title FROM documents WHERE doc_id IN "
                                                         f"({','.join('?' * len(moved))})", moved)}
                one = len(moved) == 1
                what = researchlog.access_words(lv, not one) if lv else "the project's setting for new documents"
                researchlog.record(cx, "ai-access", (f"Who may read {researchlog.quoted(titles.get(moved[0]), 80)} "
                                                     if one else f"Who may read {len(moved)} documents ")
                                   + f"with AI: {what}.",
                                   "document" if one else "documents", moved[0] if one else None,
                                   titles.get(moved[0]) if one else None,
                                   data={"documents": moved, "setting": lv})
        for d in doc_ids:
            if d in held:  # no looser than the project's setting until the owner accepts
                now_lv = levels(cx, [d], budget=False).get(d) or "cloud"
                if RANK[now_lv] > RANK[held[d]]:
                    cx.execute("UPDATE documents SET ai_access=? WHERE doc_id=?", (held[d], d))
            elif setting is not _KEEP:
                cx.execute("UPDATE documents SET ai_access=? WHERE doc_id=?", (lv, d))
            if note is not _KEEP:
                cx.execute("UPDATE documents SET ai_note=? WHERE doc_id=?", ((str(note or "").strip()[:300] or None), d))
            if budget is not _KEEP:
                cx.execute("UPDATE documents SET ai_budget=? WHERE doc_id=?", (budget, d))
            if allow is not _KEEP:
                cx.execute("UPDATE documents SET ai_providers=? WHERE doc_id=?",
                           (json.dumps(plist) if plist is not None else None, d))
        if allow is not _KEEP:
            from . import researchlog

            one = len(doc_ids) == 1
            title = cx.execute("SELECT title FROM documents WHERE doc_id=?", (doc_ids[0],)).fetchone()[0] if one else None
            researchlog.record(cx, "ai-access", (f"Cloud providers that may read {researchlog.quoted(title, 80)}"
                                                 if one else f"Cloud providers that may read {len(doc_ids)} documents")
                               + f": {_providers_words(plist)}.", "document" if one else "documents",
                               doc_ids[0] if one else None, title, data={"documents": list(doc_ids), "providers": plist})
        changed = relabel(cx)
    return {"documents": len(doc_ids), "tasks_changed": changed, "proposed": sorted(held)}


def documents_view(ws: Workspace) -> dict[str, dict]:
    """Per document: its setting (`ai_access`: the one that applies; `own`: its own or None), note, cap and the
    share Claude has read. Stage 1 of other cloud providers: `providers` (the cloud providers that may read it,
    `providers_own`: its own list or None for the project's) and `sent_by` ({provider: share}, only when a provider
    other than Anthropic has read some of it)."""
    lv = levels(ws, provider=None)   # the setting as the person chose it: a provider's allowance is shown apart
    raw = {r[0]: r for r in ws.query("SELECT doc_id, ai_access, ai_note, ai_budget, ai_providers FROM documents")}
    sh = shares(ws, by_provider=True)
    dflt_p = providers_default(ws)
    out = {}
    for d, r in raw.items():
        own = r[1] if r[1] in LEVELS else None
        eff = lv.get(d, default(ws))
        own_p = _own_list(r[4])
        out[d] = {"ai_access": eff, "own": own, "note": r[2] or "", "budget": r[3],
                  "budget_reached": eff == "local" and (own or default(ws)) == "cloud" and r[3] is not None,
                  "sent": sh.get(d, {}).get("share", 0.0), "sent_passages": sh.get(d, {}).get("passages", 0),
                  "providers": own_p if own_p is not None else dflt_p, "providers_own": own_p}
        by = sh.get(d, {}).get("by") or {}
        if any(p != ANTHROPIC for p in by):
            out[d]["sent_by"] = by
    return out


def restricted_titles(ws: Workspace) -> dict[str, str]:
    """Documents marked "No AI" by their place: {doc_id: "Restricted document 3"} (a title can name a person, so the
    connector shows this instead)."""
    lv = levels(ws, budget=False, provider=None)
    out = {}
    n = 0
    for (d,) in ws.query("SELECT doc_id FROM documents ORDER BY added_at, rowid"):
        if lv.get(d) == "none":
            n += 1
            out[d] = f"Restricted document {n}"
    return out


# ---------------------------------------------------------------------------------------------
# which model may read what
# ---------------------------------------------------------------------------------------------
def on_this_computer(url: str) -> bool:
    """Whether an address is this computer (localhost, 127.x, ::1)."""
    return providers.on_this_computer(url)


def backend_levels(backend) -> set[str]:
    """The settings a backend may read: Claude (Claude Code, the Claude API) only `cloud`; a model server on this
    computer (or the offline demo) `cloud` and `local`; a model server on another computer only `cloud`."""
    if backend is None:
        return set()
    name = getattr(backend, "name", "") or ""
    if name in OFF_COMPUTER:
        return {"cloud"}
    if name == "baseline":
        return {"cloud", "local"}
    url = getattr(backend, "base_url", None)
    if url is not None and on_this_computer(url):
        return {"cloud", "local"}
    return {"cloud"}


def is_cloud(backend) -> bool:
    """Whether the text a backend reads leaves this computer (Claude's routes, another cloud provider, a model server
    on another computer): what it is sent goes into the ledger."""
    return (getattr(backend, "name", "") or "") in OFF_COMPUTER or provider_of(backend) is not None


def route_name(backend) -> str:
    """How the ledger and the results name a backend's route: "Claude Code", "Claude API", the provider's name for
    another cloud provider."""
    name = getattr(backend, "name", "") or ""
    if name == providers.CLOUD_ROUTE:
        return providers.title(provider_of(backend))
    if name not in OFF_COMPUTER and provider_of(backend) is not None:
        return "model server on another computer"
    return ROUTE_NAMES.get(name, name)


def require(backend, task, where=None) -> None:
    """Refuse to hand a task to a model its setting does not allow (before anything is sent). With `where` (the
    workspace, or a connection inside the caller's transaction) the setting is worked out again from the task's
    payload (`recheck`), so a stored setting that went stale cannot let text through. The cap is not counted here:
    the task was labelled with it when it was made, and the runs that send several tasks in a row count it per task
    (`recheck` with the cap); a second attempt at the same task must not be refused half-way.

    Stage 1 of other cloud providers: the setting is worked out for the backend's own provider (`provider_of`), so a
    `cloud` task whose documents do not all allow that provider is refused (an OpenAI address typed into the local
    server field reads no document that allows Anthropic only)."""
    try:
        lv = task["access"] or "cloud"
    except (KeyError, IndexError):
        lv = "cloud"
    prov = provider_of(backend)
    if where is not None:
        if isinstance(where, Workspace):
            with where.connect() as cx:  # committed before the refusal below: the task stays out of the queue
                now_lv = recheck(cx, task["task_id"], budget=False, provider=prov)
        else:
            now_lv = recheck(where, task["task_id"], budget=False, provider=prov)
        lv = most([lv, now_lv]) if now_lv is not None else lv
    if lv == "none":
        raise AccessError(f"Task {task['task_id']} holds text of a document marked No AI: no model may read it.")
    if lv not in backend_levels(backend):
        if prov is not None and prov != ANTHROPIC and _as_chosen(where, task) == "cloud":
            raise AccessError(f"Task {task['task_id']} holds text of a document that {providers.title(prov)} may not "
                              "read: its AI setting allows other providers only.")
        raise AccessError(f"Task {task['task_id']} holds text of a document marked Only a local AI: "
                          f"{route_name(backend) or 'this model'} may not read it.")


def _as_chosen(where, task) -> str | None:
    """The task's setting as the person chose it, without any provider's allowance (to say why a task is refused)."""
    if where is None:
        return None
    try:
        if isinstance(where, Workspace):
            with where.connect() as cx:
                row = cx.execute("SELECT access, payload_json FROM tasks WHERE task_id=?", (task["task_id"],)).fetchone()
                return label_payload(cx, json.loads(row[1] or "{}"), budget=False, provider=None) if row else None
        row = where.execute("SELECT access, payload_json FROM tasks WHERE task_id=?", (task["task_id"],)).fetchone()
        return label_payload(where, json.loads(row[1] or "{}"), budget=False, provider=None) if row else None
    except Exception:  # noqa: BLE001 - only the wording of the refusal depends on it
        return None


# 0.19.4: "Start it anyway" for a job the local model was refused in for memory: the job runs again with this set
# (gui/api_common.Jobs.again), and the local model for documents marked Only a local AI starts whatever memory is free
FORCE_LOCAL: contextvars.ContextVar[bool] = contextvars.ContextVar("margin_force_local", default=False)


_FROM_JOB = object()


class _Gated:
    """0.19.13: the local model of a job of the app, asked only once the job's local gate opens
    (`Readers.before_local`): nothing loads the model while the gate waits. Everything else is the model's own
    (attributes read and set)."""

    def __init__(self, be, readers: "Readers"):
        object.__setattr__(self, "_be", be)
        object.__setattr__(self, "_readers", readers)

    def __getattr__(self, name: str):
        return getattr(self._be, name)

    def __setattr__(self, name: str, value) -> None:
        setattr(self._be, name, value)

    def check_memory(self, model: str) -> None:
        """The memory check before the model starts: none after Start it anyway (the gate's "force")."""
        g = self._readers.gate
        if g is not None and g.state == "force":
            if hasattr(self._be, "memory_guard"):
                self._be.memory_guard = False
            return
        check = getattr(self._be, "check_memory", None)
        if check is not None:
            check(model)

    def complete(self, *a, **k):
        from .llm import MemoryShort, local_urlopen

        self._readers.before_local()
        g = self._readers.gate
        # 0.19.15: what is in hand, so that Stop on the local side lets go of the model's memory once it is put down
        # (only Ollama on its real connection can let go: a test's stand-in or another server is never asked)
        model = a[3] if len(a) > 3 else k.get("model")
        url = getattr(self._be, "base_url", None) if (hasattr(self._be, "unload")
                                                      and getattr(self._be, "opener", None) is local_urlopen) else None
        if g is not None:
            g.hand(url, model)
        try:
            return self._be.complete(*a, **k)
        except MemoryShort as e:
            self._readers.memory_short = e   # the gate waits again, with the numbers
            raise
        finally:
            if g is not None:
                g.put_down()


class Readers:
    """The model that reads each setting: the main one where it may, the local model for restricted documents for
    `local` when the main one is Claude, nobody for `none`.

    0.19.13: in a job of the app the local model starts only when its gate opens (`localgate`): every request of it
    waits for the job's gate first, and the features with work for Claude too hand it their local items (`later`)."""

    def __init__(self, backend, model: str, settings: dict | None = None, progress=None, should_stop=None,
                 check_memory: bool | None = None, gate=_FROM_JOB):
        from .localgate import GATE

        self.backend, self.model = backend, model
        self.gate = GATE.get() if gate is _FROM_JOB else gate   # None outside the app's jobs: no gate
        self._short = None
        self._short_epoch = 0
        self._settings = settings
        self._local: tuple | None = None
        self._local_tried = False
        self._report = None                    # 0.19.4: how the local model reports to the page (_wire)
        self.local_problem: str | None = None
        # 0.13.11: the local model's reports while it reads (info dicts, marked "who": "local") and the job's Stop;
        # without them, those of the main backend are used
        self.progress, self.should_stop = progress, should_stop
        # False: the person chose "Start it anyway" (by default: unless the job runs again for it, FORCE_LOCAL)
        self.check_memory = (not FORCE_LOCAL.get()) if check_memory is None else check_memory
        self.memory_short = None               # the MemoryShort that kept the local model from starting (see below)
        self.read = 0                          # the parts the local model for restricted documents has read
        # 0.18.1 (I1, I2): the AI mix's tasks the local model answered itself, and those that went to Claude Code
        # (no local model, or no answer of it passed)
        self.mix_read = 0
        self.to_claude = 0

    @property
    def used(self) -> bool:
        return self.read > 0 or self.mix_read > 0

    @property
    def memory_short(self):
        """The MemoryShort that kept the local model from starting, or None. 0.19.13: it tells the job's gate (which
        waits again, with the numbers), and it is past once the gate has opened again since (Start, or Start it
        anyway): the features that wait on it then try again."""
        if self._short is not None and self.gate is not None and self.gate.epoch != self._short_epoch:
            self._short = None
        return self._short

    @memory_short.setter
    def memory_short(self, e) -> None:
        told = self._short is e
        self._short = e
        if self.gate is not None:
            self._short_epoch = self.gate.epoch
            if e is not None and not told:
                self.gate.refused(e)

    @property
    def main_levels(self) -> set[str]:
        return backend_levels(self.backend)

    @property
    def provider(self) -> str | None:
        """The cloud provider the main model is (None: on this computer): every split of a job's work asks for it."""
        return provider_of(self.backend)

    def level_of(self, ws: Workspace, task_id: str) -> str:
        """A task's setting for the main model's provider: the stored one when the project's tasks are labelled for it,
        else worked out for it (nothing written), so a task it may not read goes to the local model or the person."""
        with ws.connect() as cx:
            row = cx.execute("SELECT access, payload_json FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                return "none"
            prov = self.provider
            if prov == labels_provider(cx):
                return row[0] or "cloud"
            return _level_now(cx, row, None, False, prov)[1]

    def settings(self) -> dict:
        if self._settings is None:
            from .home import load_settings

            self._settings = load_settings()
        return self._settings

    def local(self):
        """(backend, model) of the local model for restricted documents, or None."""
        if "local" in self.main_levels:
            return self.backend, self.model
        if not self._local_tried:
            self._local_tried = True
            from .home import make_restricted_backend
            from .llm import BackendError

            try:
                self._local = make_restricted_backend(self.settings())
            except BackendError as e:
                self._local, self.local_problem = None, str(e)
            if self._local is not None and "local" not in backend_levels(self._local[0]):
                self._local, self.local_problem = None, "The local model for restricted documents is not on this computer."
            if self._local is not None:
                self._wire(self._local[0])
                if not self.check_memory and hasattr(self._local[0], "memory_guard"):
                    self._local[0].memory_guard = False
                if self.gate is not None:  # 0.19.13: every request of it passes the job's gate first
                    self._local = (_Gated(self._local[0], self), self._local[1])
            elif self.gate is not None:  # 0.19.13: the job's local part has no model to start (the panel says why)
                self.gate.problem = self.local_problem or ("No local model is chosen for documents marked Only a "
                                                           "local AI (Settings → AI).")
        return self._local

    # -- 0.19.13: the job's local gate --------------------------------------------------------------------------------
    def _reporter(self):
        report = (self.progress or getattr(self.backend, "local_progress", None)
                  or getattr(self.backend, "progress", None))
        return report

    def look(self) -> dict:
        """The local model's name, memory and why it cannot be used, for the job's local panel, without starting it."""
        try:
            st = local_status(self.settings())
        except Exception:  # noqa: BLE001 - what the panel shows never stops the work
            st = {}
        mem = st.get("memory") or {}
        return {"model": st.get("model") or (self._local[1] if self._local else None),
                "memory": ({k: mem[k] for k in ("need", "free", "short")} if "need" in mem else None),
                "problem": st.get("problem")}

    def before_local(self, waiting: int | None = None, noun: str | None = None) -> None:
        """Wait for the job's gate before the local model is asked (raises "Stopped." when the job is stopped
        meanwhile). Outside a job, or when the main model reads local documents itself, nothing waits."""
        from .llm import BackendError

        g = self.gate
        if g is None or "local" in self.main_levels:
            return
        g.involve(waiting=waiting, noun=noun, look=self.look, report=self._reporter())
        if not g.wait_open(self.stopped):
            raise BackendError("Stopped.")
        if g.state == "force" and self._local is not None and hasattr(self._local[0], "memory_guard"):
            self._local[0].memory_guard = False

    def mixed(self) -> None:
        """The job has work for Claude as well as the local model: its local part waits for its own Start."""
        if self.gate is not None:
            self.gate.mixed()

    def defers(self) -> bool:
        """Whether the local items of this job go to the gate's worker (`later`): a job of the app, a local model that
        can be used, and not the main model itself."""
        return self.gate is not None and "local" not in self.main_levels and self.local() is not None

    def later(self, fn, n: int = 1, noun: str = "task", mixed: bool = True, ws=None) -> None:
        """Read an item with the local model when the job's gate opens, beside the job's own work (see localgate)."""
        self.gate.involve(look=self.look, report=self._reporter())
        self.gate.later(fn, n, noun, mixed, ws)

    def drain(self) -> None:
        """Wait for the local items handed to the gate (they are read once the person starts the local model)."""
        if self.gate is not None:
            self.gate.drain(self.stopped)

    def _wire(self, be) -> None:
        """0.13.11: let the local model show what it does and see Stop (it read in silence while the page said only
        "Waiting for Claude Code")."""
        report = (self.progress or getattr(self.backend, "local_progress", None)
                  or getattr(self.backend, "progress", None))
        stop = (self.should_stop or getattr(self.backend, "local_should_stop", None)
                or getattr(self.backend, "should_stop", None))
        self._report = report
        if report is not None and hasattr(be, "progress"):
            be.progress = lambda info, _r=report: _r({**info, "who": "local"})
        if stop is not None and hasattr(be, "should_stop"):
            be.should_stop = stop

    def local_ended(self, refused=None) -> None:
        """0.19.4: tell the page the local model reads nothing more in this job (phase "done"), or that it was not
        started (phase "refused", with why: a MemoryShort gives its numbers too), so its panel does not go on saying
        it is loading."""
        report = getattr(self, "_report", None)
        if report is None or self._local is None:
            return
        info = {"who": "local", "model": self._local[1], "phase": "refused" if refused else "done"}
        if refused:
            info["error"] = str(refused)
            if hasattr(refused, "need"):
                info["memory"] = {"need": refused.need, "free": refused.free, "short": True}
        try:
            report(info)
        except Exception:  # noqa: BLE001 - a display problem must never stop the work
            pass

    def stopped(self) -> bool:
        """Whether the job was stopped (a local model's "Stopped." is not a model that cannot be reached)."""
        stop = (self.should_stop or getattr(self.backend, "local_should_stop", None)
                or getattr(self.backend, "should_stop", None))
        try:
            return bool(stop and stop())
        except Exception:  # noqa: BLE001
            return False

    def free_memory(self) -> bool:
        """0.13.11: let go of the local model for restricted documents once it has read, when it takes much of this
        computer's memory (more than a third), instead of holding it for Ollama's next 15 minutes. Returns whether it
        was let go."""
        if not self.used or self._local is None or self._local[0] is self.backend:
            return False
        be, model = self._local
        if not hasattr(be, "unload") or not hasattr(be, "memory_need"):
            return False
        from .llm import total_memory

        need, total = be.memory_need(model), total_memory()
        if not need or not total or need * 3 < total:
            return False
        return bool(be.unload(model))

    def local_configured(self) -> bool:
        """Whether a local model is chosen for restricted documents (without starting it)."""
        if "local" in self.main_levels:
            return True
        from .home import restricted_choice

        return bool(restricted_choice(self.settings()))

    def for_level(self, level: str):
        """(backend, model) that reads tasks of this setting, or None (a person)."""
        if level == "none":
            return None
        if level in self.main_levels:
            return self.backend, self.model
        if level == "local":
            return self.local()
        return None

    def for_task(self, ws: Workspace, task_id: str):
        return self.for_level(self.level_of(ws, task_id))


def local_status(settings: dict) -> dict:
    """0.19.4: the local model that reads documents marked Only a local AI, for the local panel, without starting it:
    {"model", "server", "memory": {"loaded"} or {"need", "free", "short"}} (memory only where the server says enough),
    {"model", "problem"} when it cannot be used, {"same_as_main": True} when the main model reads them itself, or
    {"model": None, "problem"} when none is chosen."""
    from .home import make_restricted_backend, restricted_choice
    from .llm import BackendError

    choice = restricted_choice(settings)
    if not choice:
        return {"model": None, "problem": "No local model is chosen for documents marked Only a local AI "
                                          "(Settings → AI)."}
    if choice.get("same_as_main"):
        return {"same_as_main": True}
    try:
        got = make_restricted_backend(settings)
    except BackendError as e:
        return {"model": choice.get("model"), "server": choice.get("server"), "problem": str(e)}
    if got is None:
        return {"model": None, "problem": "No local model is chosen for documents marked Only a local AI."}
    be, model = got
    out: dict = {"model": model, "server": choice.get("server")}
    st = be.memory_status(model) if hasattr(be, "memory_status") else None
    if st:
        out["memory"] = st
    return out


def allowed_docs(ws: Workspace, allowed: set[str], provider=None) -> set[str]:
    """The documents whose setting is one of `allowed` (for `provider`'s reading, see `levels`)."""
    return {d for d, lv in levels(ws, provider=provider).items() if lv in allowed}


# ---------------------------------------------------------------------------------------------
# the ledger
# ---------------------------------------------------------------------------------------------
def _with_context(cx, payload: Any, pids: set[str]) -> set[str]:
    """Also the passage shown before an excerpt as its context (the text before it, same document)."""
    extra: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("passage_id"), str) and (o.get("context") or o.get("prev")):
                r = cx.execute("SELECT q.passage_id FROM passages p JOIN passages q ON q.doc_id=p.doc_id AND "
                               "q.seq=p.seq - 1 WHERE p.passage_id=?", (o["passage_id"],)).fetchone()
                if r:
                    extra.add(r[0])
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(payload)
    return pids | extra


_ANTHROPIC_ROUTES = {"Claude Code", "Claude API", "Claude app (connector)", "Claude", "file queue"}


def record_sent(cx, task_id: str | None, payload: Any, route: str, feature: str | None = None,
                context: bool = True, provider: str | None = None) -> int:
    """Write one ledger row per passage (and, with `context`, the passage shown before it) of this payload, as it
    leaves for a cloud model. A Claude chat is shown the excerpts without their context (`context=False`).
    `provider`: who receives it (stage 1 of other cloud providers; by default Anthropic for Claude's routes)."""
    if provider is None:
        provider = ANTHROPIC if route in _ANTHROPIC_ROUTES else providers.OTHER
    pids, _dids = ids_in(payload)
    if not pids:
        return 0
    if context:
        pids = _with_context(cx, payload, pids)
    docs = doc_of_passages(cx, pids)
    from .reread import is_tombstone

    for p in pids - set(docs):  # 0.15: an excerpt kept from an earlier reading of its document, by a tombstone id
        if is_tombstone(p):     # ("<doc_id>:r1-0005", see reread.py): it is still that document's text that leaves
            docs[p] = p.rsplit(":", 1)[0]
    at = now()
    rows = [(p, docs[p], route, task_id, at, feature, provider) for p in sorted(pids) if p in docs]
    cx.executemany("INSERT INTO ai_sent(passage_id, doc_id, route, task_id, sent_at, feature, provider) VALUES "
                   "(?,?,?,?,?,?,?)", rows)
    return len(rows)


def record_passages(ws: Workspace, passage_ids: Iterable[str], route: str, feature: str, task_id: str | None = None,
                    provider: str | None = None) -> int:
    with ws.connect() as cx:
        return record_sent(cx, task_id, [{"passage_id": p} for p in passage_ids], route, feature, provider=provider)


FEATURES = {"check": "Check", "reread": "Read again", "second": "Second opinion", "label": "Profile (AI pass)",
            "theme": "Theme names", "link": "Concept links", "resolve": "References", "extract": "SDG pack",
            "split": "SDG pack", "verify": "SDG pack", "verify_set": "SDG pack", "expand": "Search words",
            "decompose": "Parts of a hypothesis", "theory_codes": "Codes from a theory document",
            "code_definition": "A code's definition from its examples",
            "group_name": "Names of groups of concepts",
            "theory_frame": "A framework from theory documents"}


def ledger(ws: Workspace, doc_id: str | None = None) -> list[dict]:
    """The rows of the ledger, newest first: passage, document, page, route, feature, task, when."""
    sql = ("SELECT s.passage_id, s.doc_id, d.title, p.page, s.route, COALESCE(s.feature, t.kind) AS feature, s.task_id, "
           "s.sent_at, COALESCE(s.provider, 'anthropic') AS provider FROM ai_sent s LEFT JOIN documents d ON d.doc_id=s.doc_id LEFT JOIN passages p ON "
           "p.passage_id=s.passage_id LEFT JOIN tasks t ON t.task_id=s.task_id")
    args: list = []
    if doc_id:
        sql += " WHERE s.doc_id=?"
        args.append(doc_id)
    rows = ws.query(sql + " ORDER BY s.sent_at DESC, s.rowid DESC", args)
    return [{"passage_id": r["passage_id"], "doc_id": r["doc_id"], "title": r["title"] or "", "page": r["page"],
             "route": r["route"] or "", "feature": FEATURES.get(r["feature"] or "", r["feature"] or ""),
             "task_id": r["task_id"] or "", "sent_at": r["sent_at"] or "", "provider": r["provider"]} for r in rows]


def document_ledger(ws: Workspace, doc_id: str) -> dict:
    """The passages of one document Claude has read: each passage once, with when and for what."""
    seen: dict[str, dict] = {}
    for r in ledger(ws, doc_id):
        x = seen.setdefault(r["passage_id"], {"passage_id": r["passage_id"], "page": r["page"], "times": 0,
                                              "first": r["sent_at"], "last": r["sent_at"], "features": [], "routes": []})
        x["times"] += 1
        x["first"] = min(x["first"], r["sent_at"])
        x["last"] = max(x["last"], r["sent_at"])
        if r["feature"] and r["feature"] not in x["features"]:
            x["features"].append(r["feature"])
        if r["route"] and r["route"] not in x["routes"]:
            x["routes"].append(r["route"])
    items = sorted(seen.values(), key=lambda x: x["last"], reverse=True)
    if items:
        seqs = {r[0]: (r[1], r[2]) for r in ws.query(
            f"SELECT passage_id, seq, substr(text, 1, 160) FROM passages WHERE passage_id IN "
            f"({','.join('?' * len(items))})", [x["passage_id"] for x in items])}
        for x in items:
            s = seqs.get(x["passage_id"])
            x["seq"], x["preview"] = (s[0], s[1]) if s else (None, "")
    sh = shares(ws, [doc_id]).get(doc_id, {})
    return {"doc_id": doc_id, "share": sh.get("share", 0.0), "passages": items,
            "since": ws.meta("ai_sent_since") or None}


# ---------------------------------------------------------------------------------------------
# a project made before 0.11
# ---------------------------------------------------------------------------------------------
def upgrade(ws: Workspace) -> dict:
    """Once, when a project made before 0.11 is opened: its default becomes what it was (Claude may read every
    document; `local` on an installation without cloud models), the tasks not answered yet get their setting (a
    queued one that is no longer `cloud` leaves the queue), and the answers given on a Claude route (from their
    recorded provenance) enter the ledger with the time of the answer."""
    if not default_chosen(ws):
        _write_config(ws, {"ai_access_default": "local" if _local_only() else "cloud", "ai_access_banner": True})
    out = {"relabelled": 0, "backfilled": 0}
    with ws.connect() as cx:
        if cx.execute("SELECT value FROM meta WHERE key='ai_access_upgraded'").fetchone():
            return out
        out["relabelled"] = relabel(cx)
        cx.execute("UPDATE tasks SET access='cloud' WHERE access IS NULL")
        rows = cx.execute("SELECT r.task_id, MIN(r.received_at) AS at, r.route, t.payload_json, t.kind FROM results r "
                          "JOIN tasks t ON t.task_id=r.task_id WHERE r.route IN ('Claude Code', 'Claude API') OR "
                          "r.route IS NULL AND (r.model LIKE 'claude%' OR r.model IN ('opus', 'sonnet', 'haiku', 'fable')) "
                          "GROUP BY r.task_id").fetchall()
        for r in rows:
            try:
                payload = json.loads(r["payload_json"] or "{}")
            except ValueError:
                continue
            pids, _d = ids_in(payload)
            pids = _with_context(cx, payload, pids)
            docs = doc_of_passages(cx, pids)
            route = r["route"] or "Claude"
            cx.executemany("INSERT INTO ai_sent(passage_id, doc_id, route, task_id, sent_at, feature) VALUES "
                           "(?,?,?,?,?,?)", [(p, docs[p], route, r["task_id"], r["at"], r["kind"]) for p in sorted(pids)
                                             if p in docs])
            out["backfilled"] += 1
        cx.execute("INSERT OR REPLACE INTO meta VALUES ('ai_access_upgraded', ?)", (json.dumps(now()),))
        cx.execute("INSERT OR REPLACE INTO meta VALUES ('ai_sent_since', ?)", (json.dumps(now()),))
    return out


def dismiss_banner(ws: Workspace) -> None:
    _write_config(ws, {"ai_access_banner": False})


def project_info(ws: Workspace) -> dict:
    """What the Documents page needs about the project: its default, whether it was chosen, the banner."""
    lv = levels(ws, provider=None)   # as the person chose them (a provider's allowance is shown apart)
    counts = {k: sum(1 for v in lv.values() if v == k) for k in LEVELS}
    shared = is_shared(ws._conn(), ws)
    return {"default": default(ws), "chosen": default_chosen(ws), "banner": bool(ws.config.get("ai_access_banner")),
            "ask": not default_chosen(ws) and (bool(ws.config.get("ai_access_ask")) or bool(lv)),
            "counts": counts, "labels": LABEL, "who": WHO, "local_only": _local_only(), "promise": PROMISE,
            "ledger_since": ws.meta("ai_sent_since") or None,
            # stage 1 of other cloud providers: who may read the `cloud` documents without their own choice, and
            # why a shared project allows Anthropic only
            "providers_default": providers_default(ws), "shared": shared,
            "providers_note": SHARED_ONLY_ANTHROPIC if shared else None, **_route_allows(ws, lv)}


def _route_allows(ws: Workspace, chosen: dict[str, str]) -> dict:
    """Stage 2: the main route's provider (Codex: OpenAI) and how many of the documents marked for cloud AI allow it,
    for the line "Codex reads only documents that allow OpenAI: 0 of 3 do" (views/ai-access.js providerAllowLine).
    {} when the main route reads on this computer, or cannot be known."""
    try:
        from .home import load_settings

        prov = route_provider(load_settings())
    except Exception:  # noqa: BLE001 - the page then shows no such line
        return {}
    if prov is None:
        return {}
    cloud = [d for d, v in chosen.items() if v == "cloud"]
    mine = levels(ws, cloud, provider=prov, budget=False) if cloud else {}
    return {"route_provider": prov, "route_allowed": sum(1 for v in mine.values() if v == "cloud"),
            "route_cloud": len(cloud)}


def may_read(ws: Workspace, payload: Any, backend) -> bool:
    """Whether this backend may read this payload now (for the tools that send an answered task again: the label
    comparison, the model test), for the backend's own provider."""
    with ws.connect() as cx:
        return label_payload(cx, payload, provider=provider_of(backend)) in backend_levels(backend)


def sending(ws: Workspace, payload: Any, backend, feature: str, task_id: str | None = None) -> None:
    """Before a tool sends a payload to a backend itself (not through a task): the guard, and the ledger."""
    if not may_read(ws, payload, backend):
        raise AccessError("This text comes from a document this model may not read.")
    if is_cloud(backend):
        with ws.connect() as cx:
            record_sent(cx, task_id, payload, route_name(backend), feature, provider=provider_of(backend))
