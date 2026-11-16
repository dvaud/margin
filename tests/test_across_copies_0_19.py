"""0.19 features between copies of one project: each through a real round of the shared folder, not in one copy alone.

Anna owns a small project whose documents Claude may read; Ben and Carol, Members, have copies and work through one
shared folder (`trio`, as in `test_owner_more.py`). The features were tested in one copy, or by calling a helper;
here they travel:
- the working-document role (N3): the owner's mark holds in a colleague's copy, a Member's is a proposal, and theory
  changed to working replaces the role in every copy (one role per document);
- a check started from a draft marked Only a local AI: its origin travels with it, the draft's setting still keeps
  its words from a cloud model and from a Claude chat in a colleague's copy, and a copy without the draft counts it
  as No AI;
- *Keep only English* of a document in two languages: the owner's choice leaves the other language out of a
  colleague's passages; a Member's is a proposal;
- a renamed document: the new title stays in the copy that gave it and does not travel (not yet done, CHANGELOG);
- *Documents behind no answer* leaves out a working document (one copy is enough).
"""
from __future__ import annotations

import pytest

from margin import access, bibliography, claimcheck, docrole, ingest, sharing
from margin.llm import BaselineBackend
from owner_helpers import accept, add_doc, has, level, proposals, sync, view
from test_owner_more import _trio
from test_working_documents import DRAFT


@pytest.fixture
def trio(tmp_path, monkeypatch):
    shared = tmp_path / "Közös mappa"
    shared.mkdir()
    return _trio(tmp_path, monkeypatch, shared, ai="cloud")      # (Claude may read the evidence)


def _role(p, doc: str) -> str | None:
    with p:
        return docrole.role_of(p.ws, doc)


def _set_role(p, doc: str, role: str | None) -> None:
    with p:
        docrole.set_role(p.ws, doc, role)
    view(p)          # the next look at the copy makes it the project's (the owner) or a proposal (a Member)


# ---- the working-document role (N3) ----------------------------------------------------------------------------------
def test_the_owners_working_mark_holds_in_a_colleagues_copy_and_a_members_is_a_proposal(trio, tmp_path):
    anna, ben, carol = trio
    draft = add_doc(anna, tmp_path, "draft", text=DRAFT)
    other = add_doc(anna, tmp_path, "interview")
    sync(anna, ben, carol)
    _set_role(anna, draft, "working")
    sync(anna, ben, carol, rounds=2)
    assert [_role(p, draft) for p in (anna, ben, carol)] == ["working"] * 3
    with ben:
        assert docrole.working_docs(ben.ws._conn()) == {draft}
    _set_role(ben, other, "working")                              # Ben, a Member: a proposal
    props = proposals(ben, state="waiting", kind="blocks")
    assert [(p["doc"], p["detail"].get("role")) for p in props] == [(other, "working")]
    sync(ben, anna, carol, rounds=2)
    assert _role(anna, other) is None and _role(carol, other) is None   # not the project's until she accepts
    accept(anna, proposals(anna, state="waiting", kind="blocks")[0]["id"])
    sync(anna, ben, carol, rounds=2)
    assert [_role(p, other) for p in (anna, ben, carol)] == ["working"] * 3


def test_theory_changed_to_working_replaces_the_role_in_every_copy(trio, tmp_path):
    anna, ben, carol = trio
    draft = add_doc(anna, tmp_path, "draft", text=DRAFT)
    sync(anna, ben, carol)
    _set_role(anna, draft, "theory")
    sync(anna, ben, carol, rounds=2)
    assert [_role(p, draft) for p in (anna, ben, carol)] == ["theory"] * 3
    _set_role(anna, draft, "working")
    sync(anna, ben, carol, rounds=2)
    for p in (anna, ben, carol):
        assert _role(p, draft) == "working", p.name
        with p:
            assert docrole.theory_docs(p.ws._conn()) == set(), p.name
            assert p.ws.scalar("SELECT COUNT(*) FROM block_choices WHERE doc_id=? AND fp LIKE 'role:%'",
                               (draft,)) == 1, p.name                   # one role per document
    _set_role(anna, draft, None)                                  # and evidence again, everywhere
    sync(anna, ben, carol, rounds=2)
    assert [_role(p, draft) for p in (anna, ben, carol)] == [None] * 3


# ---- a check started from a draft marked Only a local AI (N3, docrole.origin_floor) ----------------------------------
WORDS = "Electrolyser plants create local jobs that last beyond the construction phase."


def _second_opinion(p, hid: str):
    from helpers_mixed_corpus import Cloud

    cloud = Cloud()
    with p:
        out = claimcheck.second_opinion(p.ws, [hid], cloud, "claude-opus", "claude-sonnet")
    return out, cloud


def test_a_check_from_a_draft_kept_to_a_local_ai_keeps_its_floor_in_a_colleagues_copy(trio, tmp_path, monkeypatch):
    from helpers_mixed_corpus import Cloud, Local, use_local_model

    anna, ben, carol = trio
    local = Local()
    use_local_model(monkeypatch, local)                           # the words are judged on this computer
    draft = add_doc(anna, tmp_path, "draft", text=DRAFT, ai="local")
    _set_role(anna, draft, "working")
    sync(anna, ben, carol)
    with anna:                                                    # *Check against the corpus* on a sentence of it
        hid = claimcheck.check_hypothesis(anna.ws, WORDS, Cloud(), "claude-opus", k=3,
                                          origin=docrole.ORIGIN, origin_id=draft)
        sharing.share(anna.ws, [{"kind": "check", "key": hid}])
    with carol:                                                   # Carol's copy will not hold the draft
        carol.ws.remove_document(draft)
    sync(anna, ben, carol, rounds=2)
    assert has(ben, draft) and not has(carol, draft) and level(ben, draft) == "local"
    for p in (ben, carol):
        with p:
            assert tuple(p.ws.query("SELECT origin, origin_id FROM hypotheses WHERE hyp_id=?", (hid,))[0]) == \
                (docrole.ORIGIN, draft), p.name                   # it still says which document it came from
    with ben:
        cx = ben.ws._conn()
        cid = cx.execute("SELECT claim_id FROM user_claims WHERE hyp_id=?", (hid,)).fetchone()[0]
        assert docrole.origin_floor(cx, {"hyp_id": hid}) == "local"
        assert access.label_payload(cx, {"subject_kind": "user_claim", "subject_id": cid}) == "local"
        assert hid in access.hidden_hypotheses(ben.ws)            # a Claude chat is not shown it
    out, cloud = _second_opinion(ben, hid)                        # nor is a cloud model given it
    assert cloud.sent == [] and out["rounds"] == 0 and out["restricted"] > 0
    with ben:                                                     # (a check of the same words from nowhere would be)
        free = claimcheck.check_hypothesis(ben.ws, WORDS, Cloud(), "claude-opus", k=3)
    out, cloud = _second_opinion(ben, free)
    assert cloud.sent and out["rounds"] > 0, out
    with carol:                                                   # no draft here: its words count as No AI
        cx = carol.ws._conn()
        assert docrole.origin_floor(cx, {"hyp_id": hid}) == "none"
        assert hid in access.hidden_hypotheses(carol.ws)
    assert "check" in local.kinds                                 # (Anna's copy judged its excerpts on this computer)


# ---- *Keep only English* of a document in two languages --------------------------------------------------------------
def _keep(p, doc: str, keep: str | None) -> dict:
    """*Keep only …* on the document's page (`PUT …/language`), in this person's copy."""
    from margin.gui.server import App

    app = App()
    app.ws = lambda name: p.ws
    with p:
        out = app.set_language("project", doc, keep)
    view(p)
    return out


def _body(p, doc: str) -> list[str]:
    """The text of the passages a search and a check read (the body), in this person's copy."""
    with p:
        return [r[0] for r in p.ws.query("SELECT text FROM passages WHERE doc_id=? AND section='body'", (doc,))]


def _holds(texts: list[str], paras: list[str]) -> bool:
    return any(x[:30] in t for t in texts for x in paras)


def test_the_owners_keep_only_english_reaches_a_colleagues_passages_and_a_members_choice_is_a_proposal(
        trio, tmp_path):
    from test_bilingual import EN, ES, side_by_side

    anna, ben, carol = trio
    d = tmp_path / "two-languages"
    d.mkdir()
    with anna:
        ingest.ingest(anna.ws, [side_by_side(d)], ai_access="cloud")
        doc = anna.ws.scalar("SELECT doc_id FROM documents WHERE path LIKE '%huertos%'")
    sync(anna, ben, carol)
    assert has(ben, doc) and _holds(_body(ben, doc), ES) and _holds(_body(ben, doc), EN)
    assert _keep(anna, doc, "en")["left_out"] >= len(ES)          # the owner keeps only the English
    sync(anna, ben, carol, rounds=2)
    for p in (anna, ben, carol):
        assert not _holds(_body(p, doc), ES), p.name              # the Spanish is left out in every copy
        assert _holds(_body(p, doc), EN), p.name
    _keep(carol, doc, "es")                                       # Carol, a Member, would keep the Spanish
    props = proposals(carol, state="waiting", kind="blocks")
    assert [(q["doc"], q["detail"].get("language")) for q in props] == [(doc, "es")]
    sync(carol, anna, ben, rounds=2)
    for p in (anna, ben):                                         # not the project's: English still, elsewhere
        assert not _holds(_body(p, doc), ES) and _holds(_body(p, doc), EN), p.name
    (q,) = proposals(anna, state="waiting", kind="blocks")
    assert q["detail"].get("language") == "es" and q["by"]["id"] == carol.id


# ---- a renamed document (0.19.1): the title is the copy's own --------------------------------------------------------
def _title(p, doc: str) -> tuple[str, str | None]:
    with p:
        r = p.ws.query("SELECT title, own_title FROM documents WHERE doc_id=?", (doc,))[0]
    return r[0], r[1]


def _rename(p, doc: str, title: str | None) -> None:
    with p:
        bibliography.set_title(p.ws, doc, title)


def test_a_new_title_stays_in_the_copy_that_gave_it_and_does_not_travel(trio, tmp_path):
    anna, ben, carol = trio
    doc = add_doc(anna, tmp_path, "interview")
    sync(anna, ben, carol)
    plain = _title(ben, doc)[0]
    _rename(anna, doc, "Plant manager, March")                    # the owner renames a document every copy holds
    _rename(ben, doc, "Welders interview")                        # and Ben, a Member, the same one in his copy
    sync(anna, ben, carol, rounds=2)
    assert _title(anna, doc) == ("Plant manager, March", "Plant manager, March")
    assert _title(ben, doc) == ("Welders interview", "Welders interview")   # each keeps their own
    assert _title(carol, doc) == (plain, None)                    # and nothing of either travels
    assert not proposals(ben) and not proposals(carol)            # nor is it a change of the project
    _rename(anna, doc, None)                                      # given back: the title it had before
    sync(anna, ben, carol)
    assert _title(anna, doc) == (plain, None) and _title(ben, doc)[0] == "Welders interview"


@pytest.mark.xfail(strict=True, reason="A document renamed before a colleague's copy first holds it arrives there "
                                       "with the renamer's title as the colleague's own (sync/merge.py copies "
                                       "`title` and `own_title` of a new document's row; it resets only `role` and "
                                       "`nonscientific`)")
def test_a_document_renamed_before_it_reaches_a_colleague_arrives_with_its_title_from_the_file(trio, tmp_path):
    anna, ben, carol = trio
    doc = add_doc(anna, tmp_path, "interview")
    plain = _title(anna, doc)[0]
    _rename(anna, doc, "Plant manager, March")
    sync(anna, ben, carol, rounds=2)
    assert has(carol, doc)
    assert _title(carol, doc) == (plain, None)


# ---- *Documents behind no answer* (N5) leaves out a working document (one copy) -------------------------------------
def test_documents_behind_no_answer_leave_out_a_working_document(trio, tmp_path):
    anna, _ben, _carol = trio
    draft = add_doc(anna, tmp_path, "draft", text=DRAFT)
    _set_role(anna, draft, "working")
    with anna:                                                    # a check that reads one excerpt, never the draft
        hid = claimcheck.check_hypothesis(anna.ws, WORDS, BaselineBackend(), "baseline", k=1, per_doc=1,
                                          expand=False, terms=[])
        assert draft not in {x["doc_id"] for x in claimcheck.result(anna.ws, hid)["passages"]}
        u = claimcheck.unread_documents(anna.ws, hid)
        listed = {d["doc_id"] for d in u["matching"] + u["no_word"]}
        assert u["checked"] and draft not in listed
        n = u["considered"]
        docrole.set_role(anna.ws, draft, None)                    # evidence again: it is behind no answer now
        u = claimcheck.unread_documents(anna.ws, hid)
        assert u["considered"] == n + 1 and draft in {d["doc_id"] for d in u["matching"]}
