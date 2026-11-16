"""Four sync defects the long random runs found (0.19.0, seeds 1, 2, 10, 13, 15, 16 and 25), each as a small fixed test.

`tests/test_owner_random.py` found them in the nightly run of 2026-11-15; commits c0f176f (defects 1 to 3) and 3b8bfb0
(defect 4) fixed them. That run is marked `heavy` and left out of a local run of the whole suite, so each defect is kept
here too, as one owner (Anna) and two collaborators (Ben, Carol) working through one shared folder:
1. the owner's own new reading of a document she removed and added again, after accepting a colleague's new reading
   of it, reaches the project;
2. in the same case a collaborator's new reading is proposed again (their earlier, accepted proposal is spent);
3. a check with an excerpt on a document one person removed (waiting for the owner) while the others read it with a
   newer reader is not copied as a sync clash at every round: the team goes quiet;
4. reading a document again when a colleague's results on it already name the new reading's passages keeps every
   excerpt and judgement, without a database error (reduced from seed 16: the rows a copy that kept the document out
   took in from a colleague's newer reading are written into the copy, as that seed left them).
Each test fails with its fix reverted. One more test, marked `xfail(strict=True)`, keeps what remains of defect 3.
"""
from __future__ import annotations

import pytest

from margin import claimcheck, ingest, reread, sharing
from margin.llm import BaselineBackend
from margin.sync import folder
from owner_helpers import accept, add_doc, has, move, proposals, reader_of, sync
from owner_more_helpers import canon_of, results_of, waiting
from test_owner_more import _trio

# a short field report that reader 1 reads as one passage and today's reader as three (as the random run's reports)
REPORT = ("Field report: the harbour and the pipeline\n\n"
          "The pipeline near the coast needed a new permit before the harbour lease could be signed. Operators said "
          "the permit cost less than the lease once the pipeline was in place. Local people asked who would pay for "
          "the harbour after 2031.\n\n"
          "In 2024 the brine output doubled while the membrane stayed as it was, the report says of the reservoir. "
          "A study of twelve sites found that the salinity mattered more than the subsidy for the reservoir. "
          "Operators said the tariff cost less than the turbine once the subsidy was in place.\n\n"
          "Fishermen said the welders were hard to find in the first year of the pipeline. The cooperative trained "
          "apprentices from the town, and the harbour hired most of them. The report counts forty local hires.\n")
WELDERS = "Welders were hard to find for the pipeline."


@pytest.fixture
def trio(tmp_path, monkeypatch):
    shared = tmp_path / "Közös mappa"
    shared.mkdir()
    return _trio(tmp_path, monkeypatch, shared)


def _accepted_new_reading_then_out_and_in(trio, tmp_path) -> str:
    """Ben reads the interview (reader 1) with the new reader, Anna accepts it, every copy follows; then Anna removes
    the document and adds the same file again, read by reader 1: the project reads it with the older reader again
    (Ben's and Carol's copies fetch it back as the folder holds it, read by the new reader)."""
    anna, ben, carol = trio
    doc = add_doc(anna, tmp_path, "interview", reader=1)
    sync(anna, ben, carol)
    move(ben, doc)
    sync(ben, anna)
    (p,) = proposals(anna, state="waiting", kind="reread")
    accept(anna, p["id"])
    sync(anna, ben, carol, rounds=2)
    assert all(reader_of(x, doc) == ingest.READER for x in (anna, ben, carol))
    with anna:
        anna.ws.remove_document(doc)
    sync(anna, ben, carol)
    assert add_doc(anna, tmp_path, "interview", reader=1) == doc
    sync(anna, ben, carol, rounds=2)
    assert [canon_of(x)[doc][:2] for x in (anna, ben, carol)] == [("in", 1)] * 3
    assert reader_of(anna, doc) == 1
    return doc


def test_the_owners_own_new_reading_of_a_document_added_again_reaches_every_copy(trio, tmp_path):
    anna, ben, carol = trio
    doc = _accepted_new_reading_then_out_and_in(trio, tmp_path)
    move(anna, doc)                                               # now the owner reads it with the new reader herself
    sync(anna, ben, carol, rounds=2)
    for p in (anna, ben, carol):                                  # the project reads it so, by the owner's word
        assert canon_of(p)[doc][1] == ingest.READER, p.name
        assert reader_of(p, doc) == ingest.READER, p.name


def test_a_collaborators_new_reading_of_a_document_added_again_is_proposed_again(trio, tmp_path):
    anna, ben, carol = trio
    doc = _accepted_new_reading_then_out_and_in(trio, tmp_path)
    assert reader_of(ben, doc) == ingest.READER                   # the same new reading as he proposed before
    sync(ben, anna)
    p = [q for q in proposals(anna, state="waiting", kind="reread") if q["doc"] == doc]
    assert len(p) == 1 and p[0]["by"]["id"] == ben.id, p
    accept(anna, p[0]["id"])
    sync(anna, ben, carol, rounds=2)
    for p in (anna, ben, carol):
        assert canon_of(p)[doc][1] == ingest.READER, p.name
        assert reader_of(p, doc) == ingest.READER, p.name


# ---- 3. a check on a document one person removed, while the others read it with a newer reader ---------------------
def _check_on(p, doc: str, text: str = WELDERS) -> str:
    with p:
        hid = claimcheck.check_hypothesis(p.ws, text, BaselineBackend(), "baseline", k=1, per_doc=1, doc_ids=[doc])
        sharing.share(p.ws, [{"kind": "check", "key": hid}])
    return hid


def _excerpts(p, hid: str) -> list[tuple[str, str]]:
    with p:
        return sorted(tuple(r) for r in p.ws.query(
            "SELECT c.hyp_id, v.passage_id FROM verifications v JOIN user_claims c ON c.claim_id=v.subject_id WHERE "
            "v.subject_kind='user_claim' AND c.hyp_id LIKE ?", (hid + "%",)))


def _judgements(p, hid: str) -> list[tuple[str, str, str]]:
    """(passage, person, verdict) of every judgement on the check's parts, in this copy."""
    with p:
        return sorted(tuple(r) for r in p.ws.query(
            "SELECT j.passage_id, j.person_id, j.verdict FROM judgements j JOIN user_claims c ON c.claim_id=j.claim_id "
            "WHERE c.hyp_id=?", (hid,)))


def _judge(p, hid: str, verdict: str) -> None:
    """This person's judgement of the check's first excerpt."""
    with p:
        cid, pid = p.ws.query("SELECT v.subject_id, v.passage_id FROM verifications v JOIN user_claims c ON "
                              "c.claim_id=v.subject_id WHERE c.hyp_id=? ORDER BY v.rowid", (hid,))[0]
        claimcheck.set_judgement(p.ws, cid, pid, verdict, note="mine")


def _removed_by_its_maker_while_read_anew(trio, tmp_path) -> tuple[str, str]:
    """Ben's shared check has its excerpt on the report (reader 1: one passage) in every copy; Ben removes the report
    (his removal waits for the owner); Anna reads it with the new reader (its passages are three now) and Carol's copy
    follows. Returns (doc, hid)."""
    anna, ben, carol = trio
    doc = add_doc(anna, tmp_path, "report", reader=1, text=REPORT)
    sync(anna, ben, carol)
    hid = _check_on(ben, doc)
    sync(ben, anna, carol)
    with ben:
        ben.ws.remove_document(doc)
    sync(ben, anna)
    assert [q["kind"] for q in waiting(anna)] == ["remove"]
    move(anna, doc)
    sync(anna, carol)
    assert reader_of(anna, doc) == reader_of(carol, doc) == ingest.READER and not has(ben, doc)
    return doc, hid


def _rounds(people, n: int = 4) -> list[list[str]]:
    """`n` rounds of the folder for these copies, in this order: what each round wrote, by every copy."""
    out = []
    for _ in range(n):
        wrote = []
        for p in people:
            with p:
                wrote += [x["key"] for x in folder.sync_now(p.ws)["wrote"]["items"]]
        out.append(wrote)
    return out


def test_a_check_on_a_document_its_maker_removed_while_the_others_read_it_anew_is_not_copied_at_every_round(
        trio, tmp_path):
    anna, ben, carol = trio
    doc, hid = _removed_by_its_maker_while_read_anew(trio, tmp_path)
    mine = results_of(ben, [hid])
    wrote = _rounds((ben, anna, carol))
    assert wrote[1:] == [[], [], []], wrote                       # the team goes quiet (before: a new copy each round)
    for p in (anna, ben, carol):
        versions = {h for h, _pid in _excerpts(p, hid)}
        assert len(versions) <= 2 and all(h.count("-") <= 1 for h in versions), (p.name, versions)  # no copy of a copy
    assert results_of(ben, [hid]) == mine
    assert [q["kind"] for q in waiting(anna)] == ["remove"]


@pytest.mark.xfail(strict=True, reason="Another reading of a document its maker removed (waiting for the owner) "
                                       "still makes one sync-clash copy of the maker's own unchanged check, which "
                                       "then reaches every copy, when the excerpt's passage id changes with the "
                                       "new reading")
def test_a_check_on_a_document_its_maker_removed_while_the_others_read_it_anew_makes_no_clash_copy(trio, tmp_path):
    anna, ben, carol = trio
    doc, hid = _removed_by_its_maker_while_read_anew(trio, tmp_path)
    assert _rounds((ben, anna, carol)) == [[], [], [], []]
    for p in (anna, ben, carol):
        assert {h for h, _pid in _excerpts(p, hid)} == {hid}, p.name


# ---- 4. reading a document again when a colleague's results already name the new reading's passages ----------------
@pytest.fixture
def on_old_reading(trio, tmp_path):
    """Ben's shared check has its excerpt on the one passage reader 1 made of the report, with his judgement; Carol's
    copy holds it, still at reader 1. Returns (ben, carol, doc, hid, the new reading's passage with the quote)."""
    anna, ben, carol = trio
    doc = add_doc(anna, tmp_path, "report", reader=1, text=REPORT)
    sync(anna, ben, carol)
    hid = _check_on(ben, doc)
    _judge(ben, hid, "supports")
    sync(ben, carol)
    assert _excerpts(carol, hid) == [(hid, f"{doc}:0000")]
    assert _judgements(carol, hid) == [(f"{doc}:0000", ben.id, "supports")]
    return ben, carol, doc, hid, f"{doc}:0002"                    # the welders' paragraph, by today's reader


def _bring(p, table: str, where: str, new_pid: str, **change) -> None:
    """A row of `table` (the one `where` names) also as a colleague's newer reading names it: on `new_pid` (what a
    copy that keeps the document out takes in from a colleague's bundle as it is, as in seed 16)."""
    with p:
        with p.ws.connect() as cx:
            cur = cx.execute(f"SELECT * FROM {table} WHERE {where}")
            cols = [c[0] for c in cur.description]
            row = dict(zip(cols, cur.fetchone()))
            row.update(passage_id=new_pid, **change)
            cx.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                       [row[c] for c in cols])


def test_reading_again_keeps_both_judgements_of_one_person_when_one_names_the_new_reading_already(on_old_reading):
    ben, carol, doc, hid, new = on_old_reading
    _bring(carol, "judgements", f"passage_id='{doc}:0000'", new, verdict="refutes", note="on the new reading")
    with carol:
        out = reread.move(carol.ws, doc, carol.id)                # before: UNIQUE constraint failed: judgements...
    assert out["moved"] and reader_of(carol, doc) == ingest.READER
    js = _judgements(carol, hid)
    assert sorted(v for _p, who, v in js if who == ben.id) == ["refutes", "supports"]   # nothing of Ben's is lost
    assert (new, ben.id, "refutes") in js                         # the one already there keeps its place
    assert any(reread.is_tombstone(pid) for pid, _w, v in js if v == "supports")        # the other kept as a record


def test_reading_again_joins_an_excerpt_to_the_same_one_already_on_the_new_reading(on_old_reading):
    ben, carol, doc, hid, new = on_old_reading
    _bring(carol, "verifications", f"passage_id='{doc}:0000'", new, ver_id="v-from-a-newer-reading")
    with carol:
        out = reread.move(carol.ws, doc, carol.id)                # before: UNIQUE on judgements, or a second excerpt
    assert out["moved"] and reader_of(carol, doc) == ingest.READER
    live = [pid for _h, pid in _excerpts(carol, hid) if not reread.is_tombstone(pid)]
    assert live == [new]                                          # one excerpt on the passage, the one already there
    assert len(_excerpts(carol, hid)) == 2                        # the moved row stays, as a record
    assert _judgements(carol, hid) == [(new, ben.id, "supports")]  # Ben's verdict joins it and stays live
