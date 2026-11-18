"""Team codebooks: two settings of the project's owner about codebooks (People and settings, the *Codebooks* card).
(I7 stage 3: a third setting of the owner, the cloud providers the team may use, travels in the same table by the same
rules: teamproviders.py.)

1. **Codebooks made in this project are shared with the team** (`SHARE`): on by default in a team project. While it is
   on, a codebook kept in the project's `frameworks/` folder is shared as soon as it is made (fresh, from themes, from
   theory, a copy, a CSV file, a REFI-QDA file, this project's copy of one kept with all projects), by its maker's own
   copy, with an entry in the research log that says the team's setting shared it (`made`: every place that makes a
   project codebook calls it). Codebooks made before stay as they are: private until shared is still a promise, and
   their maker is only offered to share them (`private_mine`, one quiet line on the Codebooks page). Anyone may still
   Unshare one of their own (sharing.unshare, logged as ever). Turned off, nothing is taken back; new codebooks are
   private again. Codebooks kept with all projects (the home folder) are not covered.
2. **Default codebook for this project** (`DEFAULT`): the codebook the pages use when none is named (the Profile page, a
   document's Codes panel, the codes new documents get). Set, it takes the place of each computer's own setting
   (`profile_framework`) in this project (`frameworks.chosen` asks `default_name`); not set, or its codebook not in
   this copy (yet), the computer's setting holds, then the SDG targets, without an error. The choices are the codebooks
   that ship with Margin and the project's codebooks that are shared; the owner's own private one may be picked and is
   then shared (`set_default`).

**How they travel, and why a Member cannot set them.** Each setting is a row of `team_settings` (key, by, owner_seq, n,
value_json, at), one per setting and writer, the same shape and the same merge as `roles` (sync/owner_merge.py
`_own_rows`: one row per key and writer, the higher number stays; a row a file brings in this copy's own name is not
taken, is recorded in `sync_refused` and answered with this copy's own row, `settle`). Which row counts is worked out
when it is read, alike in every copy (`_counting`): a row counts only when its writer was the owner of the place it
names in the chain of owners this copy follows (`ownership.chain`, never a clock); of those, the latest place's, then
the highest number, then the smaller digest. So a Member's row, written in their own name, counts for nothing anywhere;
an owner's word holds after a hand-over until the new owner changes it, and the new owner's copy writes the settings
again once under its own place (`settle`), so a former owner's late row never counts. A project never exchanged has no
chain yet: its maker is its owner (`ownership.is_owner`), writes place 1, and the record of place 1 that names them is
written when the project first leaves the computer. Known limit, as for roles (ownership.py's notes): files are not
signed yet, so a file that says the owner wrote a row is believed by third copies until the owner's copy answers it.

The table is new, and a copy of an older Margin leaves a table it does not know aside (sync/merge.py `_other_tables`,
sync/folder.py): it merges nothing wrongly, so the sync format does not change (sync/formats.py's notes); such a copy
only goes on using each computer's own setting.
"""
from __future__ import annotations

import json
import sqlite3
import traceback
from pathlib import Path
from typing import Any

SHARE = "share_codebooks"
DEFAULT = "default_codebook"
PROVIDERS = "team_providers"   # I7 stage 3 (teamproviders.py): the cloud providers the team may use; null: no limit
KEYS = (SHARE, DEFAULT, PROVIDERS)
TABLE = "team_settings"
STEP = 2 ** 32  # an answer is not written above a number this far over what this copy holds (owner_merge.STEP)
WHY_SETTING = "The team's setting: codebooks made in this project are shared with the team."
WHY_DEFAULT = "The project's default codebook: the team uses it."


# ---------------------------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------------------------
def has_table(cx: sqlite3.Connection) -> bool:
    return bool(cx.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone())


def _my_id() -> str:
    """This installation's person id, read and never made (`frameworks.chosen` asks on every page)."""
    from .home import load_settings

    return load_settings().get("person_id") or ""


def _owners(cx: sqlite3.Connection, me: str | None = None) -> dict[int, str]:
    """{place: its owner} by the chain this copy follows; a project never exchanged and without a chain: its maker
    owns place 1 (the record that says so is written when it first leaves the computer)."""
    from . import ownership, sharing

    if not ownership._has_tables(cx):
        return {}
    ch = ownership.chain(cx)
    if ch:
        return {r["seq"]: r["owner"] for r in ch}
    me = me if me is not None else _my_id()
    return {1: me} if me and not sharing.exchanged(cx, me) else {}


def _value(key: str, raw: str | None) -> tuple[bool, Any]:
    """(valid, value) of a row: SHARE a boolean, DEFAULT a codebook's short name; null for both: no word (the default
    holds)."""
    from .frameworks import NAME_RE

    try:
        v = json.loads(raw) if raw is not None else None
    except (TypeError, ValueError):
        return False, None
    if v is None:
        return True, None
    if key == SHARE:
        return isinstance(v, bool), v
    if key == DEFAULT:
        return isinstance(v, str) and bool(NAME_RE.match(v)), v
    if key == PROVIDERS:   # a list of providers.ALLOWABLE, at least one, in the table's order
        from .providers import clean_list

        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return False, None
        try:
            got = clean_list(v)
        except ValueError:
            return False, None
        return got == v, v
    return False, None


def _counting(cx: sqlite3.Connection, owners: dict[int, str] | None = None) -> dict[str, dict]:
    """{key: {"value", "by", "owner_seq", "n", "at"}} of the rows that count (see the module's notes)."""
    from .ownership import _digest, _num

    if not has_table(cx):
        return {}
    owners = _owners(cx) if owners is None else owners
    if not owners:
        return {}
    best: dict[str, dict] = {}
    for key, by, seq, n, raw, at in cx.execute(f"SELECT key, by, owner_seq, n, value_json, at FROM {TABLE}"):
        if key not in KEYS or not isinstance(seq, int) or owners.get(seq) != by or not (_num(n) or 0) >= 1:
            continue
        ok, v = _value(key, raw)
        if not ok:
            continue
        r = {"value": v, "by": by, "owner_seq": seq, "n": n, "at": at}
        cur = best.get(key)
        if cur is None or (seq, n) > (cur["owner_seq"], cur["n"]) or \
                ((seq, n) == (cur["owner_seq"], cur["n"]) and _digest(r) < _digest(cur)):
            best[key] = r
    return best


def is_team(cx: sqlite3.Connection, ws=None) -> bool:
    """Whether the project is worked on by a team: it has an owner's chain, it was exchanged with a colleague, or
    (`ws` given) this copy has a shared folder or a storage space (before its first round)."""
    from . import ownership, sharing

    if bool(ownership._has_tables(cx) and ownership.chain(cx)) or sharing.exchanged(cx):
        return True
    if ws is None:
        return False
    try:
        from .sync.folder import FOLDER
        from .sync.space import configured

        return bool(ws.config.get(FOLDER)) or configured(ws) is not None
    except (OSError, ValueError, AttributeError):
        return False


def share_on(cx: sqlite3.Connection, ws=None) -> bool:
    """Whether codebooks made in this project are shared at once: the owner's word, else on in a team project."""
    r = _counting(cx).get(SHARE)
    if r is not None and r["value"] is not None:
        return bool(r["value"])
    return is_team(cx, ws)


def default_name(ws) -> str | None:
    """The project's default codebook as the owner set it (whether this copy holds it or not), or None. Never raises:
    a page still works with each computer's own setting."""
    try:
        cx = ws._conn()
        r = _counting(cx).get(DEFAULT)
        return r["value"] if r else None
    except (sqlite3.Error, OSError, ValueError, AttributeError):
        return None


def default_info(ws) -> dict | None:
    """{"name", "title"} of the project's default codebook when this copy holds it, else None (for Settings and the
    Profile page)."""
    from . import frameworks

    name = default_name(ws)
    if not name:
        return None
    try:
        fw = frameworks.available(ws).get(name)
    except (OSError, ValueError):
        return None
    return {"name": name, "title": fw.title} if fw else None


# ---------------------------------------------------------------------------------------------
# a codebook made in this project
# ---------------------------------------------------------------------------------------------
def _project_codebooks(ws) -> list[str]:
    from .frameworks import NAME_RE

    folder = Path(ws.root) / "frameworks"
    return sorted(p.stem for p in folder.glob("*.csv") if NAME_RE.match(p.stem)) if folder.is_dir() else []


def made(ws, name: str) -> dict | None:
    """A codebook was just made in this project (kept in its `frameworks/` folder): shared at once when the team's
    setting is on (`SHARE`), by this copy, with the reason in the research log. Returns what `sharing.share` returned,
    or None when nothing was shared. Never raises: making the codebook does not fail because of this."""
    from . import sharing

    try:
        if not (Path(ws.root) / "frameworks" / f"{name}.csv").is_file():
            return None  # kept with all projects (or not there): not covered
        cx = ws._conn()
        if not sharing.has_table(cx) or not share_on(cx, ws):
            return None
        return sharing.share(ws, [{"kind": "codebook", "key": name}], why=WHY_SETTING)
    except Exception:  # noqa: BLE001 - the codebook is made; it stays private, as without the setting
        traceback.print_exc()
        return None


def private_mine(ws) -> list[dict]:
    """This person's codebooks kept in this project that are private (never shared): [{"key", "title"}]."""
    from . import frameworks, people, sharing

    cx = ws._conn()
    if not sharing.has_table(cx):
        return []
    me = people.me()
    fws = frameworks.available(ws)
    out = []
    for n in _project_codebooks(ws):
        s = sharing.state(cx, "codebook", n, me)
        if s["mine"] and s["state"] == "private":
            out.append({"key": n, "title": fws[n].title if n in fws else n})
    return out


def codebooks_line(ws) -> dict:
    """What the Codebooks page says about the team: {"team", "share_codebooks", "private_mine": [{"key", "title"}]}
    (the private ones only while the team's setting is on: then a quiet line offers to share them)."""
    cx = ws._conn()
    team = is_team(cx, ws)
    on = team and share_on(cx, ws)
    return {"team": team, "share_codebooks": on, "private_mine": private_mine(ws) if on else []}


# ---------------------------------------------------------------------------------------------
# the owner sets them
# ---------------------------------------------------------------------------------------------
def _own_n(cx: sqlite3.Connection, me: str) -> int:
    from .ownership import _num

    return max([_num(r[0]) or 0 for r in cx.execute(f"SELECT n FROM {TABLE} WHERE by=?", (me,))] + [0])


def _write(cx: sqlite3.Connection, key: str, me: str, seq: int, n: int, value: Any) -> None:
    from .store import now

    cx.execute(f"INSERT OR REPLACE INTO {TABLE}(key, by, owner_seq, n, value_json, at) VALUES (?,?,?,?,?,?)",
               (key, me, seq, n, json.dumps(value), now()))


def _place(cx: sqlite3.Connection) -> int:
    from . import ownership

    ch = ownership.chain(cx)
    return ch[-1]["seq"] if ch else 1


def _owner_only(ws, cx: sqlite3.Connection, what: str) -> None:
    from . import ownership

    if not ownership.is_owner(ws, cx):
        raise ownership.NotAllowed(f"Only the owner sets {what}.")


def set_share(ws, on: bool) -> dict:
    """The owner turns *Codebooks made in this project are shared with the team* on or off (NotAllowed otherwise).
    Nothing made before changes either way. Returns `view`."""
    from . import people, researchlog

    me = people.me()
    with ws.connect() as cx:
        _owner_only(ws, cx, "whether codebooks made in this project are shared with the team")
        if share_on(cx, ws) == bool(on) and SHARE in _counting(cx):
            return view(ws)
        _write(cx, SHARE, me, _place(cx), _own_n(cx, me) + 1, bool(on))
        researchlog.record(cx, "owner", "Codebooks made in this project are now shared with the team as soon as they "
                                        "are made. Codebooks made before stay as they are." if on else
                           "Codebooks made in this project are private again until their maker shares them. Nothing "
                           "shared was taken back.", data={"setting": SHARE, "on": bool(on)})
    return view(ws)


def set_default(ws, name: str | None) -> dict:
    """The owner sets the project's default codebook (None: none, each computer's own setting holds). One that ships
    with Margin or a codebook of the project that is shared; the owner's own private one is shared first. KeyError:
    no such codebook here; ValueError: one that cannot be the team's (a colleague's private one, one kept with all
    projects). Returns `view`."""
    from . import frameworks, people, researchlog, sharing

    me = people.me()
    title = None
    if name is not None:
        if not isinstance(name, str) or not frameworks.NAME_RE.match(name):
            raise KeyError(name)
        fws = frameworks.available(ws)
        if name not in fws:
            raise KeyError(name)
        fw = fws[name]
        title = fw.title
        if fw.source == "home":
            raise ValueError(f"“{title}” is kept with all projects, so your colleagues do not have it: take this "
                             "project's own copy of it first (on the codebook's page), then choose that.")
        if fw.source == "project":
            with ws.connect() as cx:
                _owner_only(ws, cx, "the project's default codebook")
                s = sharing.state(cx, "codebook", name, me)
            if s["state"] != "shared":
                if not s["mine"]:
                    who = sharing.names_of(ws._conn()).get(s["owner"]) or "a colleague"
                    raise ValueError(f"“{title}” is {who}'s and not shared: only they can share it.")
                sharing.share(ws, [{"kind": "codebook", "key": name}], why=WHY_DEFAULT)
    with ws.connect() as cx:
        _owner_only(ws, cx, "the project's default codebook")
        cur = _counting(cx).get(DEFAULT)
        if (cur["value"] if cur else None) == name and (cur is not None or name is None):
            return view(ws)
        _write(cx, DEFAULT, me, _place(cx), _own_n(cx, me) + 1, name)
        if name is None:
            researchlog.record(cx, "owner", "This project has no default codebook any more: each computer's own "
                                            "setting applies again.", data={"setting": DEFAULT, "name": None})
        else:
            researchlog.record(cx, "owner", f"Made {researchlog.quoted(title, 80)} this project's default codebook: "
                                            "the pages use it when none is named, in every copy of the project.",
                               data={"setting": DEFAULT, "name": name})  # (no subject: it travels to the team)
    return view(ws)


# ---------------------------------------------------------------------------------------------
# after a merge (ownership.settle)
# ---------------------------------------------------------------------------------------------
def settle(cx: sqlite3.Connection, me: str, ch: list[dict]) -> None:
    """Called by `ownership.settle` in its transaction. (1) A row a file brought in this person's name and that was not
    taken (`sync_refused`, kind `team_settings`): when it would count (it names a place this person owned), this copy
    writes its own word again above it, so third copies replace it. (2) A new owner (place 2 or later) writes the
    settings once under their own place, as they count now, so a former owner's late row never counts."""
    from .ownership import _json, _num

    if not has_table(cx) or not ch:
        return
    owners = {r["seq"]: r["owner"] for r in ch}
    for key, what_json in cx.execute("SELECT key, what_json FROM sync_refused WHERE state='new' AND kind=?",
                                     (TABLE,)).fetchall():
        r = _json(what_json, {})
        seq, n = r.get("owner_seq"), _num(r.get("n")) or 0
        if key not in KEYS or not isinstance(seq, int) or owners.get(seq) != me:
            continue  # it counts nowhere: nothing to answer
        mine = cx.execute(f"SELECT n, value_json FROM {TABLE} WHERE key=? AND by=?", (key, me)).fetchone()
        top = _own_n(cx, me)
        if (mine and (mine[0] or 0) > n) or n > top + STEP:
            continue
        value = _value(key, mine[1])[1] if mine else None
        _write(cx, key, me, seq, max(n, top) + 1, value)
    seq = ch[-1]["seq"]
    if ch[-1]["owner"] != me or seq <= 1 or \
            cx.execute(f"SELECT 1 FROM {TABLE} WHERE by=? AND owner_seq=? LIMIT 1", (me, seq)).fetchone():
        return
    cur = _counting(cx, owners)
    if not cur:
        return  # nothing was ever set: nothing a former owner's word could hold
    n = _own_n(cx, me)
    for key in KEYS:
        n += 1
        _write(cx, key, me, seq, n, (cur.get(key) or {}).get("value"))


# ---------------------------------------------------------------------------------------------
# the view
# ---------------------------------------------------------------------------------------------
def view(ws) -> dict:
    """For the *Codebooks* card of People and settings and the API (GET …/owner/codebooks):
    {"team", "can_set" (this person is the owner), "share_codebooks": {"on", "set", "by", "at"},
     "default": {"name", "title", "here", "by", "at"} | None,
     "choices": [{"name", "title", "source" (bundled | project), "state", "mine"}] (what the owner may pick),
     "private_mine": [{"key", "title"}] (this person's private codebooks of the project)}."""
    from . import frameworks, ownership, people, sharing

    me = people.me()
    cx = ws._conn()
    names = people.names(ws)
    who = lambda pid: ownership._person(names, me, pid)  # noqa: E731
    cur = _counting(cx)
    s = cur.get(SHARE)
    d = cur.get(DEFAULT)
    fws = frameworks.available(ws)
    choices = [{"name": n, "title": fw.title, "source": "bundled", "state": "shared", "mine": False}
               for n, fw in fws.items() if fw.source == "bundled"]
    if sharing.has_table(cx):
        for n in _project_codebooks(ws):
            if n not in fws or fws[n].source != "project":
                continue
            st = sharing.state(cx, "codebook", n, me)
            if st["state"] == "shared" or st["mine"]:
                choices.append({"name": n, "title": fws[n].title, "source": "project", "state": st["state"],
                                "mine": st["mine"]})
    dname = d["value"] if d else None
    return {"team": is_team(cx, ws), "can_set": ownership.is_owner(ws, cx),
            "share_codebooks": {"on": share_on(cx, ws), "set": bool(s and s["value"] is not None),
                                "by": who(s["by"]) if s else None, "at": s["at"] if s else None},
            "default": {"name": dname, "title": fws[dname].title if dname in fws else dname, "here": dname in fws,
                        "by": who(d["by"]), "at": d["at"]} if dname else None,
            "choices": choices, "private_mine": private_mine(ws)}
