"""Private work between the two accounts of one person (16 November 2026), through a storage space only.

One researcher on two computers is two accounts in the team (*Use both computers*, `home.new_identity`), which the
owner can mark as one person (`ownership.set_same_as`). With this, such a person keeps their **private** work (what they
have not shared) the same on both computers, without sharing it with the team.

**Who decides.** Three words must hold at once; each copy checks them at every round:
1. the owner's: the two accounts are one person (`people.group`, by the owner's `same_as`);
2. each account's own, on its own computer: *Send my private work to my other account* names the other account, by
   its part of the space and its public keys as the roster shows them when it is turned on (`turn_on`). The copy keeps
   that in the space's description on this computer (`config.json`, `shared_space.self_sync`) and writes it, as a
   numbered *statement*, in its own part of the space (`parts/<part>/m/pair.json`): sealed with the project's key and
   signed by the account like every file of a part, so every member's copy reads it with the part's other small
   files (`space._pull_part`, which checks the signature against the roster) and none can forge it;
3. the roster's: both accounts are members now, with the keys their statements name.
While all three hold (`_pairs_verified`), each copy sends its person's private items to the other and takes the
other's in. Either side turns it off at any time (`turn_off`): that copy stops at once (nothing is sent outside a
round, and a round checks first), the other copy at its next round, when it reads the statement that says so. What
already arrived stays.

**What travels.** Every item of `sharing.KINDS` made by either account that is private here (no mark: this copy's own;
a mark "private" whose owner is one of the two), whole as `sharing.rows_of` defines it, with its mark; and the removal
of such an item (checks, sets of themes, notes and research log entries are removed in the other copy too, unless they
changed there since; a codebook or a link between terms is not). Each item goes when it changed since it was last
sent or received (`state["self_sync"]["sent"]`, its fingerprint as `folder.item_fp` makes it). Work under way (a check
still running) waits, as in the shared folder.

A *private bundle* is laid out as a bundle of the shared folder (bundle.json, rows.sqlite, frameworks/; format
`margin-private`), sealed for the other account alone: encrypted and signed as every sealed file (`seal.seal`), but
with a key made for that file only, which is sealed to the other account's own key (`seal.seal_key`, X25519), not to
the project's. It is stored in the sender's own part, in an area of its own, `parts/<part>/p/<stream>.<number>`: the
name says nothing of what is in it. Other members' copies never list that area (copies before this version did not
either), and could not open a file there. The receiving copy merges it through the normal merge (`merge._Merge`), so
every rule of a merge holds (a check both accounts changed is kept twice, as a sync-clash copy), and the items stay
private there: their marks say "private" and name their maker, so neither a zip for a colleague (`sharing.strip`) nor
the shared folder's writer (only items marked shared, checked by `folder._leaks`) passes them on. The sender deletes a
file once the other copy says (its statement's `read`) that it took it in, and every file when it stops sending. How
far a copy read is kept when it stops; a copy whose record was lost goes on from the first file there, and a sender
that sees the other's reading go backwards starts a new stream with everything (`_restart_if_read_again`).

**One owner for two accounts.** In the two copies an item made by either account is "mine" (`partner`): a note or a
research log entry can be edited, and the other account's newer version, in a file known to be its own (a storage
space's signed file, a private bundle: `merge._Merge.first_hand`), takes the place of this copy's
(`merge._may_replace`, `notes.merge`, `researchlog.merge`). *Share* or *Unshare* of an item the other account made is
*asked* of that account's copy (`ask`, carried in the next private bundle), which carries it out as the item's maker
(`_carry_out`); *Unshare* also stops sending it from here at once. So only an item's maker ever writes its mark, and
every copy, an older one too, reads each mark as its owner's. The pairs a copy verified are kept in the project's
`meta` on this computer only (`pairs`), for this very database and the space its config.json names now.

**Threat model** (what each threat meets):
- *A malicious owner* links a member's account to an account the owner controls (`same_as` alone): nothing is sent,
  because the member's own statement, made on their own computer, must name that account. The Team page shows its
  name, when it joined, and a check code made of both accounts' public keys, to compare on both computers first.
- *The keeper*, who signs the roster, puts keys of its own in it for an account (and writes that account's statement
  with them): each copy makes its own half of the check code from its own real keys (never the roster's word for
  them), so the codes on the two computers differ; and a copy whose own roster entry is not its real keys pairs with
  nobody, sends and takes in nothing, and says so on the card (`_roster_holds_me`). A roster that changes the other
  account's keys after it was turned on stops the sending too (each statement pins the keys it named).
- *A forged mark* (Share) for an item, written by any member into their own file: a private item of someone else's held
  here changes its state only by a mark in its owner's own file (`sharing.receive`, `sender`), and only an item's maker
  writes its mark; so no third person's file can publish the other account's private work, nor this account's.
- *A member, or the storage service, writes into someone else's part* (a forged statement, a forged private file):
  a file of a part counts only when it is signed by that part's member, as the roster says, for that very place
  (`seal.open_sealed`); otherwise it is set aside. A private file must also open with this account's own key.
- *Other members, or the storage service, read private files*: they are sealed to the other account's own key, with a
  key made for that file alone. The project's key does not open them, so a member who holds it (or held it before
  they were removed) cannot.
- *An old statement put back* after its account withdrew: statements are numbered (the number never goes down, a
  clock in milliseconds), each copy remembers the latest of each part and ignores an older one. And sending follows
  the sender's own switch, taking in the receiver's own: an old statement of the other account can never make a copy
  take anything in, nor send to anyone but that account's own key.
- *A removed member, or someone who joins again as a new account*: a removed member is not in the roster, so nothing is
  sealed to their key again and this copy deletes its private files; a new account is another part with other keys,
  which no statement names, until the person turns it on for it (and the owner links it).
- *Private work passed on by mistake*: what came from the other account keeps its "private" mark naming its maker;
  each private bundle is checked before it is sealed to hold nothing but items of the two (`_check`). An item that
  comes in under a mark this copy did not take is noted as its maker's and private, never as this copy's own.
- *A copy of the project folder, or a project moved to another space*: the pairs are tied to this database file and
  to the space it names, so the exceptions above stop there until a round verifies them again.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import sqlite3
import struct
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

from .. import __version__, people, sharing
from ..store import Workspace, now, scratch as scratch_settings
from . import folder, formats, seal
from .common import _rows
from .seal import SealProblem

FILE = "pair.json"          # the statement, in a member's m/ (space._M_FILES)
CONFIG = "self_sync"        # this copy's own word, in the space's description (config.json `shared_space`)
META = "self_sync_pairs"    # the pairs this copy verified (meta, this computer only): {"space", "installation", "db", "pairs"}
ASKS = "self_sync_asks"     # Share or Unshare of an item the other account made, for its copy to carry out (meta)
FORMAT = "margin-private"
MAGIC = b"Margin-PRIVATE-1\n"
REMOVED_WHY = "Removed on your other computer."
_NAME = re.compile(r"([0-9a-f]{12})\.(\d{6,})")
_STREAM = re.compile(r"[0-9a-f]{12}")
_CAP = seal.MAX_SEALED + 64 * 1024
_KEYS = ("part", "person", "sign", "box")


class _Wait(Exception):
    """A private bundle that cannot be taken in now (newer format, damaged): reading stops there until next round."""


# ---------------------------------------------------------------------------------------------
# the pairs this copy verified, as the rest of the app asks for them
# ---------------------------------------------------------------------------------------------
def pairs(cx: sqlite3.Connection) -> dict[str, str]:
    """{person: their other account} of every pair this copy verified at its last round of the storage space (both
    statements, both members), still linked by the owner now; {} in most projects (no row: nothing is read)."""
    try:
        row = cx.execute("SELECT value FROM meta WHERE key=?", (META,)).fetchone()
    except sqlite3.OperationalError:
        return {}
    if not row:
        return {}
    try:
        v = json.loads(row[0])
    except (TypeError, ValueError):
        return {}
    from ..home import installation_id

    if not isinstance(v, dict) or v.get("installation") != installation_id():   # (a copy of the project moved here)
        return {}
    where = _here(cx)   # (this very copy, still in that space: a copy of its folder, or a move, holds no pair)
    if where is None or v.get("db") != where[0] or v.get("space") != where[1]:
        return {}
    out: dict[str, str] = {}
    for p in v.get("pairs") or []:
        if not (isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) and people.ID_RE.fullmatch(x) for x in p)
                and p[0] != p[1]):
            continue
        if p[1] in people.group(cx, p[0]):   # the owner's link, as it is now
            out[p[0]], out[p[1]] = p[1], p[0]
    return out


_CFG: dict[str, tuple[tuple, str | None]] = {}


def _here(cx: sqlite3.Connection) -> tuple[str, str | None] | None:
    """(this database's file, the id of the storage space its project's config.json names now), or None."""
    try:
        f = next((r[2] for r in cx.execute("PRAGMA database_list") if r[1] == "main"), None)
    except sqlite3.Error:
        return None
    if not f:
        return None
    db = Path(f).resolve()
    cfg = db.parent / "config.json"
    try:
        st = cfg.stat()
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        return str(db), None
    had = _CFG.get(str(cfg))
    if had is None or had[0] != stamp:
        try:
            sp = (json.loads(cfg.read_text(encoding="utf-8")) or {}).get("shared_space")
            sid = sp.get("id") if isinstance(sp, dict) and isinstance(sp.get("id"), str) else None
        except (OSError, ValueError, AttributeError):
            sid = None
        had = _CFG[str(cfg)] = (stamp, sid)
    return str(db), had[1]


def partner(cx: sqlite3.Connection, me: str | None = None) -> str | None:
    """This person's other account, while both send their private work to each other; None otherwise."""
    return pairs(cx).get(me or people.me())


def forget(ws: Workspace) -> None:
    """The project leaves its storage space: no pair holds any more."""
    with ws.connect() as cx:
        cx.execute("DELETE FROM meta WHERE key=?", (META,))


# ---------------------------------------------------------------------------------------------
# statements
# ---------------------------------------------------------------------------------------------
def ask(cx: sqlite3.Connection, kind: str, key: str, state: str) -> None:
    """*Share* (`state` "shared") or *Unshare* ("withdrawn") of an item the other account made, kept here (in `cx`'s
    transaction) until a private bundle carries it to that account's copy, which carries it out as its maker
    (`_carry_out`). Only the maker's copy ever writes an item's mark, so older copies, and copies that know nothing of
    the pair, read every mark as its owner's."""
    row = cx.execute("SELECT value FROM meta WHERE key=?", (ASKS,)).fetchone()
    try:
        asks = json.loads(row[0]) if row else {}
    except (TypeError, ValueError):
        asks = {}
    asks = asks if isinstance(asks, dict) else {}
    asks[f"{kind}/{key}"] = {"kind": kind, "key": key, "state": state, "at": sharing._at()}
    cx.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (ASKS, json.dumps(asks)))


def _asks(cx: sqlite3.Connection) -> dict[str, dict]:
    row = cx.execute("SELECT value FROM meta WHERE key=?", (ASKS,)).fetchone()
    try:
        v = json.loads(row[0]) if row else {}
    except (TypeError, ValueError):
        v = {}
    return {k: a for k, a in (v.items() if isinstance(v, dict) else ()) if isinstance(a, dict)
            and a.get("kind") in sharing.KINDS and isinstance(a.get("key"), str) and a.get("state") in ("shared",
                                                                                                          "withdrawn")}


def _carry_out(ws: Workspace, asks: list[Any]) -> None:
    """The other account's *Share* or *Unshare* of items this account made, carried out here as this account's own
    mark (so every copy, an older one too, sees it by the item's owner), when the item is still this account's and
    nothing later was decided here."""
    me = people.me()
    for a in asks:
        if not isinstance(a, dict) or a.get("kind") not in sharing.KINDS or not isinstance(a.get("key"), str) or \
                a.get("state") not in ("shared", "withdrawn"):
            continue
        cx = ws._conn()
        if not sharing.exists(cx, ws.root, a["kind"], a["key"]):
            continue
        s = sharing.state(cx, a["kind"], a["key"], me)
        if s["owner"] != me or s["state"] == a["state"] or str(s.get("at") or "") >= str(a.get("at") or ""):
            continue
        item = [{"kind": a["kind"], "key": a["key"]}]
        try:
            if a["state"] == "shared":
                sharing.share(ws, item, why="Asked on your other computer.")
            elif s["state"] == "shared":
                sharing.unshare(ws, item, why="Asked on your other computer.")
        except (KeyError, PermissionError, ValueError):
            continue


def _pin(w: Any) -> dict | None:
    return {k: w.get(k) for k in _KEYS} if isinstance(w, dict) else None


def _shape(obj: Any) -> bool:
    if not isinstance(obj, dict) or obj.get("v") != 1 or not isinstance(obj.get("space"), str):
        return False
    if not isinstance(obj.get("part"), str) or not people.ID_RE.fullmatch(str(obj.get("person") or "")):
        return False
    if not isinstance(obj.get("seq"), int) or isinstance(obj.get("seq"), bool):
        return False
    w = obj.get("with")
    return w is None or (isinstance(w, dict) and all(isinstance(w.get(k), str) for k in _KEYS))


def _st(ctx) -> dict:
    return ctx.state.setdefault("self_sync", {})


def _config(desc: dict) -> dict:
    c = desc.get(CONFIG)
    return c if isinstance(c, dict) else {}


def _statements(ctx) -> dict[str, dict]:
    """The latest statement of each member's part (one never older than one this copy read before), this copy's own
    from its own word."""
    from .space import _active

    seen = _st(ctx).setdefault("seen", {})
    active = _active(ctx.roster)
    for part, m in active.items():
        if part == ctx.desc["part"]:
            continue
        obj = folder._json(ctx.team / m["person"] / FILE)
        if not _shape(obj) or obj["part"] != part or obj["person"] != m["person"] or obj["space"] != ctx.id:
            continue
        old = seen.get(part)
        if not isinstance(old, dict) or obj["seq"] > int(old.get("seq") or 0):
            seen[part] = obj
    for part in [p for p in seen if p not in active]:
        seen.pop(part)
    out = {p: s for p, s in seen.items() if (active.get(p) or {}).get("person") == s.get("person")}
    c = _config(ctx.desc)
    if c:
        out[ctx.desc["part"]] = {"part": ctx.desc["part"], "person": ctx.me, "with": _pin(c.get("with"))}
    return out


def _names_each_other(a: dict, b: dict, active: dict[str, dict]) -> bool:
    """Statements `a` and `b` name each other, with the keys the roster gives each part now."""
    ma, mb = active.get(a.get("part")), active.get(b.get("part"))
    if not ma or not mb or ma.get("person") != a.get("person") or mb.get("person") != b.get("person"):
        return False
    return _pin(a.get("with")) == {"part": b["part"], "person": b["person"], "sign": mb.get("sign"),
                                   "box": mb.get("box")} and \
        _pin(b.get("with")) == {"part": a["part"], "person": a["person"], "sign": ma.get("sign"), "box": ma.get("box")}


def _pairs_verified(ctx, cx: sqlite3.Connection) -> list[list[str]]:
    """[[person, person]] of every pair whose three words hold now, as this copy reads the space."""
    from .space import _active

    stmts, active = _statements(ctx), _active(ctx.roster)
    _st(ctx)["me"] = ctx.ident.public()   # (for `status`: this copy's own half of the check code)
    if not _roster_holds_me(ctx.desc, active, ctx.ident.public()):
        stmts.pop(ctx.desc["part"], None)   # the roster gives this account other keys: it pairs with nobody
    out = set()
    for pa, a in stmts.items():
        pb = (a.get("with") or {}).get("part")
        b = stmts.get(pb) if isinstance(pb, str) else None
        if b is None or pa >= pb or a["person"] == b["person"]:
            continue
        if _names_each_other(a, b, active) and b["person"] in people.group(cx, a["person"]):
            out.add(tuple(sorted((a["person"], b["person"]))))
    return [list(p) for p in sorted(out)]


def _roster_holds_me(desc: dict, active: dict[str, dict], mine: dict | None) -> bool:
    """Whether the roster (signed by the keeper) gives this copy's part this copy's real public keys. A keeper who put
    other keys there could read what is sealed to "this account": such a roster pairs this account with nobody."""
    m = active.get(desc.get("part")) or {}
    return bool(mine) and m.get("sign") == mine.get("sign") and m.get("box") == mine.get("box")


def note_pairs(ctx) -> None:
    """After the space was read, before the folder's round merges anything: the pairs this copy verified, for the
    rules of sharing (`pairs`). Written only when they changed (an idle round writes nothing)."""
    from ..home import installation_id

    cx = ctx.ws._conn()
    found = _pairs_verified(ctx, cx)
    want = {"space": ctx.id, "installation": installation_id(), "db": str(Path(ctx.ws.db_path).resolve()),
            "pairs": found}
    row = cx.execute("SELECT value FROM meta WHERE key=?", (META,)).fetchone()
    try:
        have = json.loads(row[0]) if row else None
    except (TypeError, ValueError):
        have = None
    if have == want or (have is None and not found):
        return
    with ctx.ws.connect() as w:
        if found:
            ctx.ws.set_meta(META, want, w)
        else:
            w.execute("DELETE FROM meta WHERE key=?", (META,))


def _other(ctx) -> dict | None:
    """The other account this copy sends to and takes from now: its pinned part, person and keys, when the three
    words hold; None otherwise."""
    w = _pin(_config(ctx.desc).get("with"))
    if not w:
        return None
    if sorted((ctx.me, w["person"])) not in _pairs_verified(ctx, ctx.ws._conn()):
        return None
    return w


def _seq_next(prev: Any) -> int:
    try:
        p = int(prev or 0)
    except (TypeError, ValueError):
        p = 0
    return max(p + 1, int(time.time() * 1000))


def _write_statement(ctx) -> None:
    """This copy's statement in its own part of the mirror (`space._push` seals and sends it), when what it says
    changed: whom it names, the stream it writes, how far it read the other's. A copy never turned on writes none."""
    c = _config(ctx.desc)
    if not c:
        return
    st = _st(ctx)
    w = _pin(c.get("with"))
    body = {"v": 1, "space": ctx.id, "part": ctx.desc["part"], "person": ctx.me, "with": w,
            "stream": st.get("stream") if w else None, "read": st.get("read") if w else None}
    sig = json.dumps(body, sort_keys=True)
    f = ctx.team / ctx.me / FILE
    if st.get("wrote") == sig and f.is_file():
        return
    c["seq"] = _seq_next(c.get("seq"))
    c["at"] = now()
    ctx.desc[CONFIG] = c
    ctx.changed_desc = True
    f.parent.mkdir(parents=True, exist_ok=True)
    folder._put_json(f, {**body, "seq": c["seq"], "at": c["at"]})
    st["wrote"] = sig


# ---------------------------------------------------------------------------------------------
# the round's private part
# ---------------------------------------------------------------------------------------------
def exchange(ctx) -> dict:
    """In a round of the storage space, after the folder's round and before `space._push`: take in the other
    account's private bundles, send this account's, delete what the other took in; or, when the three words do not
    hold (any more), delete every private file this copy wrote. Then this copy's statement. Returns {"sent",
    "received"} (items)."""
    out = {"sent": 0, "received": 0}
    other = _other(ctx)
    if other is None:
        _stop(ctx)
    else:
        out["received"] = _take_in(ctx, other)
        _restart_if_read_again(ctx, other)
        out["sent"] = _send(ctx, other)
        _prune(ctx, other)
    _write_statement(ctx)
    return out


def _mine(ctx) -> str:
    return f"parts/{ctx.desc['part']}/p/"


def _stop(ctx) -> None:
    """Sending stops: every private file this copy wrote goes, and what it sent is forgotten (turned on again, it sends
    everything once more). How far it read the other's stays (`read`): the other copy has deleted what it read, and
    reading goes on from there."""
    st = _st(ctx)
    if not (st.get("stream") or st.get("sent") or st.get("files")):
        return
    for name in ctx.store.list(_mine(ctx)):
        ctx.store.delete(name)
    for k in ("stream", "seq", "sent", "files", "read_max"):
        st.pop(k, None)
    st["stopped_at"] = now()


def _restart_if_read_again(ctx, other: dict) -> None:
    """When the other copy's statement says it read less of this copy's stream than it said before (its record was
    lost, or reset), this copy starts a new stream with everything: nothing it deleted as read is missed."""
    st = _st(ctx)
    stream = st.get("stream")
    if not stream:
        return
    theirs = _statements(ctx).get(other["part"]) or {}
    read = theirs.get("read") if isinstance(theirs.get("read"), dict) else {}
    upto = int(read.get("last") or 0) if read.get("stream") == stream else 0
    most = int(st.get("read_max") or 0)
    if upto >= most:
        st["read_max"] = upto
        return
    for name in st.get("files") or []:
        ctx.store.delete(name)
    for k in ("stream", "seq", "sent", "files", "read_max"):
        st.pop(k, None)


def _prune(ctx, other: dict) -> None:
    """The private files the other copy took in (its statement's `read`), and those of an earlier stream, go."""
    st = _st(ctx)
    theirs = _statements(ctx).get(other["part"]) or {}
    read = theirs.get("read") if isinstance(theirs.get("read"), dict) else {}
    stream = st.get("stream")
    upto = int(read.get("last") or 0) if read.get("stream") == stream else 0
    gone = []
    for name in st.get("files") or []:
        m = _NAME.fullmatch(name.rsplit("/", 1)[-1])
        if m is None or m.group(1) != stream or int(m.group(2)) <= upto:
            ctx.store.delete(name)
            gone.append(name)
    if gone:
        st["files"] = [n for n in st.get("files") or [] if n not in gone]


# ---------------------------------------------------------------------------------------------
# sending
# ---------------------------------------------------------------------------------------------
def _private_items(ws: Workspace, cx: sqlite3.Connection, me: str, them: str) -> dict[tuple[str, str], dict]:
    """{(kind, key): its mark as it goes} of every item made by either account that is private here."""
    have = sharing.rows(cx)
    out = {}
    for kind, keys in sharing.items(cx, ws.root).items():
        for key, title in keys.items():
            r = have.get((kind, key))
            if r is None:
                out[(kind, key)] = {"state": "private", "owner": me, "by": me, "at": None, "title": (title or "")[:200]}
            elif r["state"] == "private" and r["owner"] in (me, them):
                out[(kind, key)] = {"state": "private", "owner": r["owner"], "by": r["by"], "at": r["at"],
                                    "title": r["title"] or (title or "")[:200]}
    return out


def _fp_now(ws: Workspace, cx: sqlite3.Connection, kind: str, key: str, mark: dict) -> str:
    files = folder._codebook_files(ws, key) if kind == "codebook" else {}
    return folder.item_fp(kind, key, sharing.rows_of(cx, kind, key), mark, files)


def _send(ctx, other: dict) -> int:
    ws, st, me = ctx.ws, _st(ctx), ctx.me
    sent = st.setdefault("sent", {})
    rcx = folder._reader_cx(ws)
    try:
        now_items = _private_items(ws, rcx, me, other["person"])
        go = []
        for (kind, key), mark in sorted(now_items.items()):
            got = sharing.rows_of(rcx, kind, key)
            if folder._busy(kind, got):
                continue   # work under way: it goes once done
            files = folder._codebook_files(ws, key) if kind == "codebook" else {}
            fp = folder.item_fp(kind, key, got, mark, files)
            if sent.get(f"{kind}/{key}") != fp:
                go.append({"kind": kind, "key": key, "fp": fp, "rows": got, "files": files, "mark": mark})
        removed = []
        for k in sorted(sent):
            kind, _, key = k.partition("/")
            if (kind, key) in now_items:
                continue
            if kind in sharing.KINDS and not sharing.exists(rcx, ws.root, kind, key):
                removed.append({"kind": kind, "key": key, "rows": sharing.rows_of(rcx, kind, key)})
            else:
                sent.pop(k)   # shared since, or no longer one of the two's: not this channel's any more
        asks = _asks(rcx)
        if not go and not removed and not asks:
            return 0
        if not _STREAM.fullmatch(str(st.get("stream") or "")):
            st["stream"], st["seq"], st["files"] = uuid.uuid4().hex[:12], 0, []
        seq = int(st.get("seq") or 0) + 1
        data = _bundle(ws, rcx, go, removed, me, st["stream"], seq, list(asks.values()))
    finally:
        rcx.rollback()
        rcx.close()
    name = f"{_mine(ctx)}{st['stream']}.{seq:06d}"
    ctx.store.put(name, _seal_for(ctx, other, data, st["stream"], seq))
    st["seq"] = seq
    st.setdefault("files", []).append(name)
    for it in go:
        sent[f"{it['kind']}/{it['key']}"] = it["fp"]
    for it in removed:
        sent.pop(f"{it['kind']}/{it['key']}", None)
    if asks:   # (sent: forgotten here, unless asked again meanwhile)
        with ws.connect() as cx:
            left = {k: a for k, a in _asks(cx).items() if asks.get(k) != a}
            if left:
                cx.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (ASKS, json.dumps(left)))
            else:
                cx.execute("DELETE FROM meta WHERE key=?", (ASKS,))
    st["sent_at"], st["sent_n"] = now(), int(st.get("sent_n") or 0) + len(go) + len(removed)
    return len(go) + len(removed)


def _stubs(ws: Workspace, cx: sqlite3.Connection, named: set[str]) -> list[dict]:
    """The documents the rows name, each by a stub (the other copy holds them through the shared folder)."""
    levels = folder.ai_settings(ws, cx)
    out = []
    docs = {r["doc_id"]: r for r in _rows(cx, "SELECT doc_id, sha1, text_fp, old_fps, title, ai_budget, sent_share, "
                                              "reader FROM documents")}
    removed = {r["key"]: r for r in _rows(cx, "SELECT key, title, fp FROM sync_removed WHERE kind='document' AND fp "
                                              "IS NOT NULL")}
    absent = {r["doc_id"]: r for r in _rows(cx, "SELECT * FROM sync_folder_docs")}
    for d in sorted(named):
        if d in docs:
            r = docs[d]
            out.append({**r, "ai_access": levels.get(d) or "none", "kept_out": False, "reading": None, "file": None,
                        "name": None})
        elif d in removed:
            out.append({"doc_id": d, "text_fp": removed[d]["fp"], "title": removed[d]["title"], "removed": True})
        elif d in absent:
            a = absent[d]
            out.append({"doc_id": d, "sha1": a["sha1"], "text_fp": a["text_fp"], "title": a["title"], "heard": True,
                        "kept_out": bool(a["kept_out"]), "reading": None, "file": None, "name": None})
    return out


def _check(bcx: sqlite3.Connection, keys: set[tuple[str, str]]) -> str | None:
    """A last look at a private bundle before it is sealed: every item in it is one of those meant to go, and every
    mark says "private" (a second line of defence: `_private_items` chose them)."""
    from ..frameworks import BUNDLED

    found = {"check": {r[0] for r in bcx.execute("SELECT hyp_id FROM hypotheses")},
             "themes": {r[0] for r in bcx.execute("SELECT run_id FROM theme_runs")},
             "note": {r[0] for r in bcx.execute("SELECT note_id FROM notes")},
             "log": {r[0] for r in bcx.execute("SELECT entry_id FROM research_log WHERE kind='entry'")},
             "codebook": {r[0] for r in bcx.execute("SELECT DISTINCT framework FROM labels")} - set(BUNDLED),
             "link": {f"{a}|{b}" for a, b in bcx.execute("SELECT a, b FROM concept_links WHERE source IN ('person', "
                                                         "'model')")}}
    for kind, got in found.items():
        extra = {k for k in got if (kind, k) not in keys}
        if extra:
            return f"a {sharing.WORDS[kind][0]} that is not among your private work was among what was to go."
    if bcx.execute("SELECT 1 FROM shares WHERE state != 'private'").fetchone():
        return "the mark of an item that is not private was among what was to go."
    return None


def _bundle(ws: Workspace, cx: sqlite3.Connection, go: list[dict], removed: list[dict], me: str, stream: str,
            seq: int, asks: list[dict] = ()) -> bytes:
    tmp = Path(tempfile.mkdtemp(prefix="margin-private-"))
    try:
        db = Workspace.create(tmp / "b", scratch=True).db_path
        bcx = scratch_settings(sqlite3.connect(db))
        bcx.execute("PRAGMA journal_mode=MEMORY")
        known = {r[0] for r in cx.execute("SELECT doc_id FROM documents")} | \
            {r[0] for r in cx.execute("SELECT key FROM sync_removed WHERE kind='document'")} | \
            {r[0] for r in cx.execute("SELECT doc_id FROM sync_folder_docs")}
        named: set[str] = set()
        try:
            with bcx:
                for it in go + removed:
                    for table, got in it["rows"].items():
                        folder._insert(bcx, table, got)
                        named |= folder._doc_tokens(got, known)
                for it in go:
                    m = it["mark"]
                    bcx.execute("INSERT OR REPLACE INTO shares(kind, key, state, owner, by, at, title) VALUES "
                                "(?,?,?,?,?,?,?)", (it["kind"], it["key"], "private", m["owner"], m["by"], m["at"],
                                                    m["title"]))
            problem = _check(bcx, {(it["kind"], it["key"]) for it in go + removed})
            if problem:
                raise ValueError("Margin stopped before sending your private work to your other account: " + problem
                                 + " Nothing was sent. Please report this.")
            bcx.execute("VACUUM")
        finally:
            bcx.close()
        meta = {"format": FORMAT, **formats.stamp(needs=folder.NEEDS), "version": __version__,
                "project_uid": ws.project_uid(), "from": {"id": me, "name": people.my_name()}, "stream": stream,
                "seq": seq, "at": now(),
                "items": [{"kind": it["kind"], "key": it["key"], "state": "private", "fp": it["fp"]} for it in go],
                "removed": [{"kind": it["kind"], "key": it["key"]} for it in removed], "asks": list(asks),
                "documents": _stubs(ws, cx, named)}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            zf.writestr("bundle.json", json.dumps(meta, indent=1, ensure_ascii=False, default=str))
            zf.write(db, "rows.sqlite")
            for it in go:
                for n, data in sorted(it["files"].items()):
                    zf.writestr(n, data)
        return buf.getvalue()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _key_context(space_id: str, by: str, to: str, stream: str, seq: int) -> str:
    return f"{space_id} private {by} to {to} stream {stream} file {seq}"


def _path(person: str, stream: str, seq: int) -> str:
    return f"{person}/private/{stream}/{seq:06d}"


def _seal_for(ctx, other: dict, data: bytes, stream: str, seq: int) -> bytes:
    """`data` for the other account alone: sealed and signed with a key made for this file, that key sealed to the
    other account's own key (the one its statement and this copy's both name)."""
    key = seal.new_key()
    inner = seal.seal(data, path=_path(ctx.me, stream, seq), by=ctx.desc["part"], epoch=0, key=key, ident=ctx.ident)
    head = seal.canonical({"v": 1, "to": other["part"], "stream": stream, "seq": seq,
                           "k": seal.seal_key(other["box"], key,
                                              _key_context(ctx.id, ctx.desc["part"], other["part"], stream, seq))})
    return MAGIC + struct.pack(">I", len(head)) + head + inner


def _open(ctx, blob: bytes, other: dict, stream: str, seq: int) -> bytes:
    """A private file of the other account's, checked: signed by them (the key the roster and both statements name),
    for this very place, and sealed to this account's own key. Raises SealProblem."""
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 4:
        raise SealProblem("A private file in the storage space is not one Margin sealed.", "format")
    (n,) = struct.unpack(">I", blob[len(MAGIC):len(MAGIC) + 4])
    if n > 64 * 1024 or len(MAGIC) + 4 + n > len(blob):
        raise SealProblem("A private file in the storage space is damaged.", "damaged")
    try:
        head = json.loads(blob[len(MAGIC) + 4:len(MAGIC) + 4 + n])
        sealed_key = str(head["k"])
    except (ValueError, KeyError, TypeError) as e:
        raise SealProblem("A private file in the storage space is damaged.", "damaged") from e
    inner = blob[len(MAGIC) + 4 + n:]
    h = seal.verify(inner, other["sign"])
    key = seal.open_key(ctx.ident, sealed_key, _key_context(ctx.id, other["part"], ctx.desc["part"], stream, seq))
    return seal.open_sealed(inner, path=_path(other["person"], stream, seq), by=other["part"], sign_pub=other["sign"],
                            keys={0: key}, h=h)


# ---------------------------------------------------------------------------------------------
# taking in
# ---------------------------------------------------------------------------------------------
def _take_in(ctx, other: dict) -> int:
    """The other account's private bundles not taken in yet, in order (a gap: next round)."""
    from .storage import NOT_FOUND, StorageProblem

    st = _st(ctx)
    theirs = _statements(ctx).get(other["part"]) or {}
    stream = theirs.get("stream")
    if not isinstance(stream, str) or not _STREAM.fullmatch(stream):
        return 0
    read = st.get("read") if isinstance(st.get("read"), dict) else {}
    last = int(read.get("last") or 0) if read.get("stream") == stream else 0
    prefix = f"parts/{other['part']}/p/"
    listed = ctx.store.list(prefix)
    files = {}
    for name, o in listed.items():
        m = _NAME.fullmatch(name[len(prefix):]) if name.startswith(prefix) else None
        if m and m.group(1) == stream:
            files[int(m.group(2))] = (name, o.etag)
    if files and last + 1 not in files and min(files) > last + 1:
        # the next one is gone: the other copy deleted it as read (this copy's record of how far it read was lost),
        # or the storage lost it. Go on from the first one there; say so when this copy had read some already
        if last > 0:
            ctx.problem("self_sync", f"{min(files) - last - 1} private file(s) of your other account were no longer in "
                                     "the storage space when this computer looked for them; Margin went on with the "
                                     "next. Turn the option off and on again on either computer to send everything "
                                     "once more.")
        last = min(files) - 1
    n = 0
    while last + 1 in files:
        name, etag = files[last + 1]
        aside = ctx.state["aside"].get(name)
        if aside and aside.get("etag") == etag:
            break
        try:
            blob = ctx.store.get(name, max_size=_CAP)
            data = _open(ctx, blob, other, stream, last + 1)
            n += _merge(ctx, data, other, stream, last + 1)
        except StorageProblem as e:
            if e.kind == NOT_FOUND:
                break
            if e.kind == "too_large":
                ctx.set_aside(name, etag, other["part"], "too_large", "A private file of your other account is larger "
                                                                      "than Margin reads.")
                break
            raise
        except SealProblem as e:
            ctx.set_aside(name, etag, other["part"], e.why, str(e))
            break
        except _Wait as e:
            ctx.problem("self_sync", str(e))
            break
        last += 1
        st["read"] = {"stream": stream, "last": last}
        st["received_at"] = now()
        ctx.state["aside"].pop(name, None)
    if n:
        st["received_n"] = int(st.get("received_n") or 0) + n
    return n


def _merge(ctx, data: bytes, other: dict, stream: str, seq: int) -> int:
    """One private bundle into this copy, by the normal merge. Returns how many items it held."""
    from . import _backup, log_bring_in
    from .merge import _Merge

    ws = ctx.ws
    who = (ctx.state.get("names") or {}).get(other["person"]) or _name(ws, other["person"])
    tmp = Path(tempfile.mkdtemp(prefix="margin-private-in-"))
    scratch = None
    try:
        f = tmp / "p.zip"
        f.write_bytes(data)
        try:
            with zipfile.ZipFile(f) as zf:
                with zf.open(folder._member(zf, "bundle.json", folder._MAX_META, who, seq, "a description")) as src:
                    meta = json.loads(src.read())
        except (zipfile.BadZipFile, KeyError, ValueError, OSError, folder._Stop) as e:
            raise _Wait("A private file of your other account cannot be read; it waits.") from e
        if not isinstance(meta, dict) or meta.get("format") != FORMAT or meta.get("project_uid") != ws.project_uid() \
                or (meta.get("from") or {}).get("id") != other["person"] or meta.get("stream") != stream \
                or meta.get("seq") != seq:
            raise _Wait("A private file of your other account is not what its name says; it waits.")
        newer = formats.problem(meta, "Your private work from your other account", "and the next round brings it in")
        if newer:
            raise _Wait(newer)
        try:
            folder._unpack(f, tmp / "u", who, seq)
        except folder._Stop as e:
            raise _Wait(e.message) from e
        scratch = Workspace.create(tmp / "work", scratch=True)
        stubs: dict[str, dict] = {}
        with scratch.connect() as scx:
            scratch.set_meta("project_uid", ws.project_uid(), scx)
            folder._apply_bundle(scx, scratch, tmp / "u", meta)
            for s in meta.get("documents") or []:
                s = folder._clean_stub(s)
                if s is not None:
                    folder._put_stub(scx, s)
                    stubs[s["doc_id"]] = s
        info = {"from": {"id": other["person"], "name": who}, "name": Path(ws.root).name,
                "version": meta.get("version"), "sync_format": formats.of(meta)[0], "stubs": stubs, "canon_ai": {},
                "first_hand": True}
        _backup(ws)
        report = _Merge(ws, scratch, info).run()
        report["via"] = "self"
        with ws.connect() as cx:
            log_bring_in(cx, report, " from your other account (your private work)")
        items = [(it.get("kind"), it.get("key")) for it in meta.get("items") or [] if isinstance(it, dict)]
        gone = [(it.get("kind"), it.get("key")) for it in meta.get("removed") or [] if isinstance(it, dict)]
        _came_in(ctx, other, [i for i in items if i[0] in sharing.KINDS and isinstance(i[1], str)],
                 [i for i in gone if i[0] in sharing.KINDS and isinstance(i[1], str)])
        _carry_out(ws, meta.get("asks") or [])
        return len(items) + len(gone)
    finally:
        if scratch is not None:
            scratch.close_all()
        shutil.rmtree(tmp, ignore_errors=True)


def _came_in(ctx, other: dict, items: list[tuple[str, str]], gone: list[tuple[str, str]]) -> None:
    """After a merge: what came in is not sent back (its state here is recorded as sent), and the items the other
    account removed go here too, unless they changed here since they were last sent or received."""
    ws, sent = ctx.ws, _st(ctx).setdefault("sent", {})
    cx = ws._conn()
    now_items = _private_items(ws, cx, ctx.me, other["person"])
    for kind, key in items:
        mark = now_items.get((kind, key))
        if mark is not None:
            sent[f"{kind}/{key}"] = _fp_now(ws, cx, kind, key, mark)
    for kind, key in gone:
        k = f"{kind}/{key}"
        mark = now_items.get((kind, key))
        if mark is None:
            sent.pop(k, None)
            continue
        if kind in ("codebook", "link") or sent.get(k) != _fp_now(ws, cx, kind, key, mark):
            continue   # changed here since: it stays, and goes to the other account again
        _remove(ws, kind, key)
        sent.pop(k, None)


def _remove(ws: Workspace, kind: str, key: str) -> None:
    if kind == "check":
        from ..judgements import delete_hypothesis

        delete_hypothesis(ws, key, why=REMOVED_WHY)
    elif kind == "themes":
        from ..themes import delete_run

        delete_run(ws, key, why=REMOVED_WHY)
    elif kind in ("note", "log"):
        table, col, text = ("notes", "note_id", "quote") if kind == "note" else ("research_log", "entry_id", "text")
        with ws.connect() as cx:
            row = cx.execute(f"SELECT {text}, person_id FROM {table} WHERE {col}=?", (key,)).fetchone()
            if row is None:
                return
            cx.execute(f"DELETE FROM {table} WHERE {col}=?", (key,))
            cx.execute("INSERT OR REPLACE INTO sync_removed(kind, key, title, at, person_id) VALUES (?,?,?,?,?)",
                       (kind, key, (row[0] or "")[:80], now(), row[1]))


# ---------------------------------------------------------------------------------------------
# the switch, and what the Team page shows
# ---------------------------------------------------------------------------------------------
def _name(ws: Workspace, pid: str | None, state: dict | None = None) -> str:
    from .space import _member_name

    return _member_name(ws, pid, state)


def _state_of(ws: Workspace) -> dict:
    from .space import mirror_of

    base = mirror_of(ws)
    try:
        return json.loads((base / ".space-state.json").read_text(encoding="utf-8")) if base else {}
    except (OSError, ValueError):
        return {}


def code(sign_a: str | None, sign_b: str | None) -> str | None:
    """A check code of two accounts' public keys: the same on both computers when each sees the other's real keys."""
    if not sign_a or not sign_b:
        return None
    h = hashlib.sha256("|".join(sorted((sign_a, sign_b))).encode("utf-8")).hexdigest()[:12].upper()
    return f"{h[:4]} {h[4:8]} {h[8:]}"


def _log(ws: Workspace, text: str, data: dict) -> None:
    """The research log says so: an entry about this copy only (kind "sync", `sharing.LOCAL_LOG_KINDS`: never sent)."""
    from .. import researchlog

    with ws.connect() as cx:
        researchlog.record(cx, "sync", text, data={"self_sync": data})


def turn_on(ws: Workspace, person: str) -> dict:
    """*Send my private work to my other account*: this account's own word, naming the other account `person` (one the
    owner marked as this person, a member of the storage space now). Its part and keys are pinned as the roster shows
    them now. Raises SpaceProblem in words. Returns `status`."""
    from .space import SpaceProblem, _active, _locked, _save, configured

    me = people.me()
    with _locked(ws):
        desc = configured(ws)
        if desc is None:
            raise SpaceProblem("Sending your private work to your other account needs a storage space: on a shared "
                               "folder it is not offered.", "no_space")
        if not people.ID_RE.fullmatch(str(person or "")) or person == me:
            raise SpaceProblem("Choose your other account.", "request")
        if person not in people.group(ws._conn(), me):
            raise SpaceProblem("The owner has not marked that account as you. Ask the owner to mark both accounts as "
                               "the same person (Team page, People) first.", "not_linked")
        state = _state_of(ws)
        active = _active(state.get("roster") or {})
        part = next((p for p, m in active.items() if m.get("person") == person), None)
        if part is None or desc.get("part") not in active:
            raise SpaceProblem("That account is not in the storage space now (or this copy has not read who is yet). "
                               "Try again after the next round.", "not_member")
        if not _roster_holds_me(desc, active, _own_keys(desc)):
            raise SpaceProblem(KEYS_DIFFER, "keys_differ")
        m = active[part]
        name = _name(ws, person, state)
        c = dict(_config(desc))
        c["with"] = {"part": part, "person": person, "sign": m.get("sign"), "box": m.get("box"), "name": name,
                     "since": m.get("since")}
        c["on_at"] = now()
        _save(ws, {**desc, CONFIG: c})
    _log(ws, f"Started sending your private work to your other account, {name} (in the team since "
             f"{str(m.get('since') or '')[:10] or 'an unknown day'}). Nothing goes before that account turns it on "
             "too.", {"on": True, "person": person})
    return status(ws)


def turn_off(ws: Workspace) -> dict:
    """Stop sending private work to the other account (and taking it in from it). What already arrived stays; the next
    round deletes this copy's private files in the space. Returns `status`."""
    from .space import _locked, _save, configured

    with _locked(ws):
        desc = configured(ws)
        c = dict(_config(desc or {}))
        w = c.get("with") if isinstance(c.get("with"), dict) else None
        if desc is None or w is None:
            return status(ws)
        c["with"], c["off_at"] = None, now()
        _save(ws, {**desc, CONFIG: c})
    _log(ws, f"Stopped sending your private work to your other account, {w.get('name') or 'your other account'}. "
             "What already arrived stays on both computers.", {"on": False, "person": w.get("person")})
    return status(ws)


KEYS_DIFFER = ("The team's list of members gives this account other keys than this computer's own: someone else (the "
               "owner's copy signs that list) could read what is sent to it. Nothing is sent or taken in. Tell the "
               "owner; you may need a new invite.")


def _own_keys(desc: dict) -> dict:
    """This copy's real public keys in the space (from the keychain), {} when they are not on this computer."""
    from .space import _secret_name, keychain

    raw = keychain.get(_secret_name(desc["id"], "me")) if desc and desc.get("id") else None
    try:
        return seal.Identity.load(raw).public() if raw else {}
    except (ValueError, KeyError, TypeError):
        return {}


def status(ws: Workspace) -> dict | None:
    """What the Team page shows (None: nothing to show, no account is marked as this person): {"needs_space": True,
    "linked": [{"person", "name"}]} on a shared folder; in a storage space {"needs_space": False, "candidates":
    [{"person", "name", "part", "since", "code"}] (accounts the owner marked as this person, members now), "on": {"person",
    "name", "since", "at"} | None (this account's own word), "theirs" (the other account turned it on, naming this
    one), "active" (both, the owner's link and the roster hold: private work goes both ways), "why" (in words, when it
    is on and not active), "code", "sent_at", "received_at", "sent", "received"}."""
    from . import space

    me = people.me()
    try:
        linked = sorted(people.group(ws._conn(), me) - {me})
    except sqlite3.OperationalError:
        linked = []
    desc = space.configured(ws)
    c = _config(desc or {})
    w = c.get("with") if isinstance(c.get("with"), dict) else None
    if desc is None:
        if not linked:
            return None
        return {"needs_space": True, "linked": [{"person": p, "name": _name(ws, p)} for p in linked]}
    if not linked and w is None:
        return None
    state = _state_of(ws)
    active = space._active(state.get("roster") or {})
    st = state.get("self_sync") or {}
    # this copy's own half of the check code: its real keys (as its rounds noted them, or from the keychain), never
    # the roster's word for them, which the keeper signs and could have changed
    mine = st.get("me") if isinstance(st.get("me"), dict) else _own_keys(desc)
    keys_differ = desc.get("part") in active and bool(mine) and not _roster_holds_me(desc, active, mine)
    candidates = [{"person": m["person"], "name": _name(ws, m["person"], state), "part": p, "since": m.get("since"),
                   "code": code(mine.get("sign"), m.get("sign"))}
                  for p, m in sorted(active.items(), key=lambda x: str(x[1].get("since") or ""))
                  if m.get("person") in linked and p != desc.get("part")]
    out: dict[str, Any] = {"needs_space": False, "candidates": candidates, "on": None, "theirs": False,
                           "keys_differ": keys_differ,
                           "warning": KEYS_DIFFER if keys_differ else None,
                           "active": False, "why": None, "code": None, "sent_at": st.get("sent_at"),
                           "received_at": st.get("received_at"), "sent": st.get("sent_n") or 0,
                           "received": st.get("received_n") or 0}
    if w is None:
        return out
    out["on"] = {"person": w.get("person"), "name": _name(ws, w.get("person"), state) or w.get("name"),
                 "since": w.get("since"), "at": c.get("on_at")}
    theirs = (st.get("seen") or {}).get(w.get("part")) or {}
    out["theirs"] = _pin(theirs.get("with")) == {"part": desc.get("part"), "person": me, "sign": mine.get("sign"),
                                                 "box": mine.get("box")}
    m = active.get(w.get("part")) or {}
    keys_same = m.get("person") == w.get("person") and m.get("sign") == w.get("sign") and m.get("box") == w.get("box")
    out["code"] = code(mine.get("sign"), w.get("sign"))
    if keys_differ:
        out["why"] = KEYS_DIFFER
    elif w.get("person") not in linked:
        out["why"] = "The owner no longer marks that account as you: nothing is sent."
    elif not keys_same:
        out["why"] = ("That account is no longer in the storage space with the keys it had when you turned this on: "
                      "nothing is sent. If it is still yours, turn this off and on again.")
    elif not out["theirs"]:
        out["why"] = ("Waiting for your other account: turn this on there too (Team page, People). Nothing is sent "
                      "before both have.")
    else:
        out["active"] = True
    return out
