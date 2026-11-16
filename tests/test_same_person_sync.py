"""One person, two accounts (16 November 2026, sync/selfsync.py): private work goes between them through the storage
space only when the owner linked them and both turned it on, sealed to the other account's own key; nobody else gets
it, and what arrives stays private. Anna owns the project; Carol uses two computers (Carol and Carol on the laptop)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from margin import bundle, ownership, people, sharing
from margin.sync import folder, seal, selfsync, space
from test_shared_projects import Person, anna_and_ben  # noqa: F401  (fixture)
from test_storage_space import _check, _has, _join_new, _round, owner, store_dir  # noqa: F401  (fixtures)


@pytest.fixture
def carols(owner, tmp_path, monkeypatch):
    """Anna (owner, keeper of the space), Carol and Carol's laptop, each a member; the owner marked both Carols as one
    person."""
    anna = owner
    carol, laptop = Person(tmp_path, "Carol", monkeypatch), Person(tmp_path, "Carol laptop", monkeypatch)
    for p in (carol, laptop):
        with anna:
            inv = space.invite(anna.ws, p.name)
        _join_new(p, inv["link"])
    for p in (anna, carol, laptop, anna, carol, laptop):
        _round(p)
    with anna:
        ownership.set_same_as(anna.ws, laptop.id, carol.id)
    for p in (anna, carol, laptop):
        _round(p)
    with carol:
        assert people.group(carol.ws._conn(), carol.id) == {carol.id, laptop.id}
    return anna, carol, laptop


def _space_dir(p: Person, store: Path) -> Path:
    with p:
        return store / space.configured(p.ws)["prefix"]


def _private_files(p: Person, store: Path) -> list[Path]:
    with p:
        part = space.configured(p.ws)["part"]
    d = _space_dir(p, store) / "parts" / part / "p"
    return sorted(f for f in d.glob("*") if f.is_file()) if d.is_dir() else []


def _on(p: Person, other: Person) -> dict:
    with p:
        return selfsync.turn_on(p.ws, other.id)


def test_private_work_goes_only_when_both_accounts_consent(carols, store_dir):
    anna, carol, laptop = carols
    hc = _check(carol, "Electrolysers create local jobs.")
    # the owner's link alone sends nothing
    for p in (carol, laptop):
        _round(p)
    assert not _private_files(carol, store_dir)
    with laptop:
        assert not _has(laptop.ws, hc)
        st = selfsync.status(laptop.ws)
    assert st["on"] is None and [c["name"] for c in st["candidates"]] == ["Carol"]
    # one side's word sends nothing either
    st = _on(carol, laptop)
    assert st["on"]["name"] == "Carol laptop" and not st["active"] and "Waiting" in st["why"]
    for p in (carol, laptop, carol):
        _round(p)
    assert not _private_files(carol, store_dir)
    with laptop:
        assert not _has(laptop.ws, hc)
    # both: it goes, and stays Carol's and private on the laptop
    st = _on(laptop, carol)
    with carol:
        code = selfsync.status(carol.ws)["code"]
    assert code and st["code"] == code   # the same check code on both computers
    for p in (laptop, carol, laptop):
        _round(p)
    with laptop:
        assert _has(laptop.ws, hc)
        s = sharing.state(laptop.ws._conn(), "check", hc)
        assert s["state"] == "private" and s["owner"] == carol.id and s["mine"]
        assert selfsync.status(laptop.ws)["active"]
    # the laptop's own private work goes the other way
    hl = _check(laptop, "Hydrogen storage is cheap.")
    for p in (laptop, carol):
        _round(p)
    with carol:
        assert _has(carol.ws, hl)
    # a third member gets nothing, and cannot open the private files
    _round(anna)
    with anna:
        assert not _has(anna.ws, hc) and not _has(anna.ws, hl)
        # Anna's copy verified the pair itself (both statements, her own link, the roster): it knows them as one
        assert selfsync.pairs(anna.ws._conn()) == {carol.id: laptop.id, laptop.id: carol.id}
        ident = seal.Identity.load(space.keychain.get(space._secret_name(space.configured(anna.ws)["id"], "me")))
        names, epochs = space._keys(space.configured(anna.ws)["id"])
    files = _private_files(laptop, store_dir) + _private_files(carol, store_dir)
    assert _private_files(laptop, store_dir)   # (the laptop deletes it at its next round, once Carol's copy read it)
    for f in _private_files(laptop, store_dir):
        assert f.read_bytes().startswith(selfsync.MAGIC) and b"Hydrogen" not in f.read_bytes()
        inner = f.read_bytes()
        n = int.from_bytes(inner[len(selfsync.MAGIC):len(selfsync.MAGIC) + 4], "big")
        blob = inner[len(selfsync.MAGIC) + 4 + n:]
        with pytest.raises(seal.SealProblem):   # the project's key does not open it
            seal.open_unverified(blob, epochs)
        head = json.loads(inner[len(selfsync.MAGIC) + 4:len(selfsync.MAGIC) + 4 + n])
        with pytest.raises(seal.SealProblem):   # nor Anna's own key the file's key
            seal.open_key(ident, head["k"], "anything")
    assert all(f.parent.name == "p" for f in files)
    # what came from the other account never goes to colleagues: not in a zip for them, not in the shared folder
    out = laptop.files / "for-colleagues.zip"
    with laptop:
        bundle.export_project(laptop.ws, out, scope="shared")
    with zipfile.ZipFile(out) as zf:
        zf.extract("enlens.sqlite", laptop.files)
        cfg = json.loads(zf.read("config.json"))
    import sqlite3

    zcx = sqlite3.connect(laptop.files / "enlens.sqlite")
    try:
        assert not zcx.execute("SELECT 1 FROM hypotheses WHERE hyp_id IN (?, ?)", (hc, hl)).fetchone()
        assert not zcx.execute("SELECT 1 FROM shares WHERE key IN (?, ?)", (hc, hl)).fetchone()
    finally:
        zcx.close()
    assert "self_sync" not in (cfg.get("shared_space") or {})
    for p in (laptop, anna):
        _round(p)
    with anna:
        assert not _has(anna.ws, hc)
    # either account can share what the other made: the laptop asks, Carol's copy shares it as its maker, so every
    # copy (an older one, one that knows nothing of the pair) sees Carol's own mark
    with laptop:
        got = sharing.share(laptop.ws, [{"kind": "check", "key": hc}])
        assert sharing.state(laptop.ws._conn(), "check", hc)["state"] == "private"   # not before Carol's copy says so
    assert not got["shared"] and [x["key"] for x in got["asked"]] == [hc]
    _round(laptop)
    _round(anna)
    with anna:
        assert not _has(anna.ws, hc)
    for p in (carol, carol, anna, laptop):   # (Carol's copy shares it at one round, writes it for the team at the next)
        _round(p)
    with anna:
        assert _has(anna.ws, hc)
        s = sharing.state(anna.ws._conn(), "check", hc)
        assert s["state"] == "shared" and s["owner"] == carol.id and s["by"] == carol.id
    for p in (carol, laptop):
        with p:
            assert sharing.state(p.ws._conn(), "check", hc)["state"] == "shared"
    # Unshare from the laptop: it stops going from the laptop at once, and Carol's copy takes it back as its maker
    with laptop:
        got = sharing.unshare(laptop.ws, [{"kind": "check", "key": hc}])
    assert [x["key"] for x in got["asked"]] == [hc]
    for p in (laptop, carol, carol, anna):
        _round(p)
    with anna:
        s = sharing.state(anna.ws._conn(), "check", hc)
        assert s["state"] == "withdrawn" and s["by"] == carol.id
    # withdrawn consent stops sending at once: Carol's private files go, and her new work stays with her
    with carol:
        assert selfsync.turn_off(carol.ws)["on"] is None
    h2 = _check(carol, "Fuel cells need platinum.")
    _round(carol)
    assert not _private_files(carol, store_dir)
    for p in (laptop, carol, laptop):
        _round(p)
    with laptop:
        assert not _has(laptop.ws, h2)
        assert not selfsync.status(laptop.ws)["active"]
        assert sharing.state(laptop.ws._conn(), "check", hc)["owner"] == carol.id   # what arrived stays
        assert _has(laptop.ws, hl)


def test_removing_an_account_stops_the_sending(carols, store_dir):
    anna, carol, laptop = carols
    _on(carol, laptop)
    _on(laptop, carol)
    for p in (carol, laptop, carol, laptop):
        _round(p)
    with carol:
        assert selfsync.status(carol.ws)["active"]
    with anna:
        part = next(m["part"] for m in folder.status(anna.ws)["space"]["members"] if m["person"] == laptop.id)
        space.remove_member(anna.ws, part)
    _round(anna)
    h = _check(carol, "Fuel cells need platinum.")
    _round(carol)
    assert not _private_files(carol, store_dir)   # nothing sealed to the removed account's key, and the old files gone
    with carol:
        st = selfsync.status(carol.ws)
        assert not st["active"] and st["why"]
        assert selfsync.partner(carol.ws._conn()) is None
    _round(laptop)
    with laptop:
        assert not _has(laptop.ws, h)


def test_the_owners_link_without_the_storage_space_offers_nothing(anna_and_ben, tmp_path):
    """On a plain shared folder the option is not offered: the Team page says it needs a storage space."""
    anna, ben = anna_and_ben
    shared = tmp_path / "Shared"
    shared.mkdir()
    for p in (anna, ben):
        with p:
            folder.set_folder(p.ws, str(shared))
    for p in (anna, ben, anna):
        _round(p)
    with anna:
        ownership.set_same_as(anna.ws, ben.id, anna.id)
    _round(anna)
    _round(ben)
    with ben:
        st = selfsync.status(ben.ws)
        assert st["needs_space"] and [x["person"] for x in st["linked"]] == [anna.id]
        with pytest.raises(space.SpaceProblem) as e:
            selfsync.turn_on(ben.ws, anna.id)
    assert e.value.kind == "no_space"


def test_an_old_statement_put_back_changes_nothing(carols, store_dir):
    """A withdrawn statement put back in the space (by the storage, or a member who can write there) is older than the
    one the laptop read: the laptop goes on treating Carol's account as off, and sends nothing."""
    _anna, carol, laptop = carols
    _on(carol, laptop)
    _on(laptop, carol)
    for p in (carol, laptop, carol, laptop):
        _round(p)
    with carol:
        part = space.configured(carol.ws)["part"]
    f = _space_dir(carol, store_dir) / "parts" / part / "m" / "pair.json"
    old = f.read_bytes()
    with carol:
        selfsync.turn_off(carol.ws)
    for p in (carol, laptop):
        _round(p)
    with laptop:
        assert not selfsync.status(laptop.ws)["active"]
    f.write_bytes(old)   # the statement that said "on", signed by Carol: put back
    hl = _check(laptop, "Hydrogen storage is cheap.")
    _round(laptop)
    with laptop:
        mirrored = space.mirror_of(laptop.ws) / folder.team_name(laptop.ws) / carol.id / selfsync.FILE
        assert json.loads(mirrored.read_text(encoding="utf-8"))["with"]   # the old statement did come in…
        st = selfsync.status(laptop.ws)
        assert not st["active"] and not st["theirs"]                     # …and counts for nothing
        assert selfsync.partner(laptop.ws._conn()) is None
    assert not _private_files(laptop, store_dir)
    _round(carol)
    with carol:
        assert not _has(carol.ws, hl)


def _active_pair(carol: Person, laptop: Person) -> None:
    _on(carol, laptop)
    _on(laptop, carol)
    for p in (carol, laptop, carol, laptop):
        _round(p)
    with carol:
        assert selfsync.status(carol.ws)["active"]


def test_a_forged_mark_in_a_third_members_file_publishes_nothing(carols, store_dir):
    """A mark is data in whichever file carries it. Anna (a member, here also the owner) writes into her own bundle
    marks that say the laptop shared its private check, and that the laptop shared Carol's own private check, both
    dated in the future: Carol's copy takes neither, and writes neither for the team."""
    anna, carol, laptop = carols
    _active_pair(carol, laptop)
    hl = _check(laptop, "Hydrogen storage is cheap.")
    hc = _check(carol, "Electrolysers create local jobs.")
    for p in (laptop, carol, laptop):
        _round(p)
    with carol:
        assert _has(carol.ws, hl) and sharing.state(carol.ws._conn(), "check", hl)["state"] == "private"
    with anna:
        with anna.ws.connect() as cx:
            for key, owner in ((hl, laptop.id), (hc, carol.id)):
                cx.execute("INSERT OR REPLACE INTO shares(kind, key, state, owner, by, at, title) VALUES "
                           "('check', ?, 'shared', ?, ?, '2099-01-01T00:00:00+00:00', 'x')", (key, owner, laptop.id))
    for p in (anna, carol, anna):
        _round(p)
    with carol:
        for key in (hl, hc):
            assert sharing.state(carol.ws._conn(), "check", key)["state"] == "private", key
    with anna:
        assert not _has(anna.ws, hl) and not _has(anna.ws, hc)


def test_a_roster_that_swaps_an_accounts_keys_shows_other_codes_and_sends_nothing(carols, store_dir):
    """The keeper (who signs the roster) gives the laptop's part keys of its own: the check codes on the two computers
    differ, the laptop's copy refuses to pair and says why, and nothing is sent."""
    anna, carol, laptop = carols
    with anna:
        desc = space.configured(anna.ws)
        ctx = space._Ctx(anna.ws, desc)
        roster = json.loads(json.dumps(ctx.roster))
        part = next(p for p, m in roster["members"].items() if m["person"] == laptop.id)
        roster["members"][part].update(seal.Identity.new().public())
        space._write_roster(ctx, roster, rekey=False)
        ctx.save()
    for p in (carol, laptop):
        _round(p, ok_kinds=("documents", "set_aside"))
    with carol:
        code_carol = selfsync.status(carol.ws)["candidates"][0]["code"]
        selfsync.turn_on(carol.ws, laptop.id)   # (Carol pins the keys the roster shows: the keeper's)
    with laptop:
        st = selfsync.status(laptop.ws)
        assert st["keys_differ"] and st["warning"]
        assert st["candidates"][0]["code"] != code_carol
        with pytest.raises(space.SpaceProblem) as e:
            selfsync.turn_on(laptop.ws, carol.id)
    assert e.value.kind == "keys_differ"
    _check(carol, "Electrolysers create local jobs.")
    for p in (carol, laptop, carol):
        _round(p, ok_kinds=("documents", "set_aside"))
    assert not _private_files(carol, store_dir)


def test_taking_in_goes_on_after_off_and_on_or_a_lost_record(carols, store_dir):
    anna, carol, laptop = carols
    _active_pair(carol, laptop)
    h1 = _check(carol, "Electrolysers create local jobs.")
    for p in (carol, laptop, carol):
        _round(p)
    with laptop:
        assert _has(laptop.ws, h1)
    # off and on again on the laptop between two of Carol's rounds: Carol has deleted file 1 as read
    with laptop:
        selfsync.turn_off(laptop.ws)
    _round(laptop)
    _on(laptop, carol)
    _round(laptop)
    h2 = _check(carol, "Fuel cells need platinum.")
    for p in (carol, laptop):
        _round(p)
    with laptop:
        assert _has(laptop.ws, h2)
    # the laptop's record of how far it read is lost: it goes on from the first file there
    with laptop:
        f = space.mirror_of(laptop.ws) / ".space-state.json"
    state = json.loads(f.read_text(encoding="utf-8"))
    state["self_sync"].pop("read")
    f.write_text(json.dumps(state), encoding="utf-8")
    h3 = _check(carol, "Hydrogen storage is cheap.")
    for p in (carol, laptop):
        _round(p)
    with laptop:
        assert _has(laptop.ws, h3)
    # lost again, with nothing left to read: Carol's copy sees the laptop's reading went backwards and sends
    # everything once more, in a new stream
    for p in (carol, laptop):
        _round(p)
    with carol:
        before = json.loads((space.mirror_of(carol.ws) / ".space-state.json").read_text())["self_sync"]["stream"]
    state = json.loads(f.read_text(encoding="utf-8"))
    state["self_sync"].pop("read")
    f.write_text(json.dumps(state), encoding="utf-8")
    for p in (laptop, carol, laptop, carol):
        _round(p)
    with carol:
        after = json.loads((space.mirror_of(carol.ws) / ".space-state.json").read_text())["self_sync"]["stream"]
    assert after != before
    assert not _private_files(carol, store_dir)   # all read, all deleted: nothing piles up


def test_verified_pairs_hold_only_for_this_copy_in_this_space(carols, tmp_path):
    import shutil
    import sqlite3

    _anna, carol, laptop = carols
    _active_pair(carol, laptop)
    with carol:
        assert selfsync.partner(carol.ws._conn()) == laptop.id
        carol.ws.close_all()
        copy = tmp_path / "copy-of-carols-project"
        copy.mkdir()
        for n in ("enlens.sqlite", "config.json"):
            shutil.copy2(Path(carol.ws.root) / n, copy / n)
        cx = sqlite3.connect(copy / "enlens.sqlite")
        try:
            assert selfsync.partner(cx, carol.id) is None   # a copy of the project folder: no pair
        finally:
            cx.close()
        desc = space.configured(carol.ws)
        folder._set_config(carol.ws, shared_space={**desc, "id": "0123456789abcdef"})   # another space
        assert selfsync.partner(carol.ws._conn()) is None
        folder._set_config(carol.ws, shared_space=desc)
        assert selfsync.partner(carol.ws._conn()) == laptop.id
