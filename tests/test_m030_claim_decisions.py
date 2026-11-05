"""Margin 0.3: the person's decision on each claim of a draft (supported, refuted, dismissed). A decision is kept when
the claims are found again, keeps a claim out of the bulk check, is exported, never changes the answer of the claim's
check, and the draft page folds the card, marks where to cite, scrolls the claims on their own and opens a claim from
anywhere on its card."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_app import api, home  # noqa: F401  (fixtures)
from test_m010_drafts import DRAFT

from margin import claimcheck, drafts
from margin.llm import BaselineBackend
from margin_static import section, sections

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"


def _draft(ws):
    did = drafts.new_draft(ws, DRAFT)
    drafts.find_by_rules(ws, did)
    return did, [c["claim_id"] for c in drafts.view(ws, did)["claims"]]


def test_the_three_decisions_and_taking_one_back(loaded):
    did, ids = _draft(loaded)
    assert drafts.update_claim(loaded, did, ids[0], decision="supported")["decision"] == "supported"
    drafts.update_claim(loaded, did, ids[1], decision="refuted")
    row = drafts.update_claim(loaded, did, ids[2], decision="dismissed")
    assert row["skip"] == 1 and row["decided_at"]
    with pytest.raises(ValueError):
        drafts.update_claim(loaded, did, ids[0], decision="maybe")
    v = drafts.view(loaded, did)
    by = {c["claim_id"]: c for c in v["claims"]}
    assert [by[i]["decision"] for i in ids[:3]] == ["supported", "refuted", "dismissed"]
    assert not by[ids[0]]["skip"] and by[ids[2]]["skip"]
    assert v["counts"]["decided"] == {"supported": 1, "refuted": 1, "dismissed": 1}
    # taking a decision back: the claim is open again (a dismissed one is kept again)
    row = drafts.update_claim(loaded, did, ids[2], decision=None)
    assert row["decision"] is None and row["skip"] == 0 and row["decided_at"] is None


def test_dismissing_is_dropping(loaded):
    did, ids = _draft(loaded)
    assert drafts.update_claim(loaded, did, ids[0], skip=True)["decision"] == "dismissed"
    assert drafts.update_claim(loaded, did, ids[0], skip=False)["decision"] is None
    # keeping a claim does not take back a supported or refuted decision
    drafts.update_claim(loaded, did, ids[1], decision="refuted")
    assert drafts.update_claim(loaded, did, ids[1], skip=False)["decision"] == "refuted"
    # a claim dropped before 0.3 (skip, no decision) shows as dismissed
    with loaded.connect() as cx:
        cx.execute("UPDATE draft_claims SET skip=1, decision=NULL WHERE claim_id=?", (ids[2],))
    assert next(c for c in drafts.view(loaded, did)["claims"] if c["claim_id"] == ids[2])["decision"] == "dismissed"


def test_decided_claims_stay_when_found_again_and_wait_out_of_the_bulk_check(loaded):
    did, ids = _draft(loaded)
    drafts.update_claim(loaded, did, ids[0], decision="supported")
    drafts.update_claim(loaded, did, ids[1], decision="refuted")
    drafts.find_by_rules(loaded, did)
    after = {c["claim_id"]: c for c in drafts.view(loaded, did)["claims"]}
    assert after[ids[0]]["decision"] == "supported" and after[ids[1]]["decision"] == "refuted"
    todo = {c["claim_id"] for c in drafts.to_check(loaded, did)}
    assert ids[0] not in todo and ids[1] not in todo and ids[3] in todo
    assert drafts.view(loaded, did)["counts"]["to_check"] == len(todo)
    # asked for by its id, a decided claim is checked
    assert [c["claim_id"] for c in drafts.to_check(loaded, did, [ids[0]])] == [ids[0]]


def test_a_decision_never_changes_the_check_and_is_exported(loaded):
    did, ids = _draft(loaded)
    out = drafts.check_claims(loaded, did, BaselineBackend(), "baseline", claim_ids=[ids[0]], k=4, per_doc=2)
    hid = out["checked"][0]
    before = claimcheck.hypothesis_result(loaded, hid)["status"]
    drafts.update_claim(loaded, did, ids[0], decision="refuted" if before == "supported" else "supported")
    assert claimcheck.hypothesis_result(loaded, hid)["status"] == before
    rows = drafts.export_rows(loaded, did)
    assert rows[0]["Your decision"] in ("supported", "refuted") and rows[1]["Your decision"] == ""
    drafts.update_claim(loaded, did, ids[1], decision="dismissed")
    assert drafts.export_rows(loaded, did)[1]["Checked"] == "dismissed"


def test_the_api_takes_a_decision(api):  # noqa: F811
    st, r = api("POST", "/api/projects", {"name": "D"})
    assert st == 200
    st, r = api("POST", "/api/projects/D/drafts", {"text": DRAFT, "ai_access": "none"})
    did = r["draft"]["draft_id"]
    st, r = api("POST", f"/api/projects/D/drafts/{did}/find", {})
    assert api.wait(r["job"]["id"])["state"] == "done"
    cid = api("GET", f"/api/projects/D/drafts/{did}")[1]["claims"][0]["claim_id"]
    st, r = api("PUT", f"/api/projects/D/drafts/{did}/claims/{cid}", {"decision": "supported"})
    assert st == 200 and r["decision"] == "supported" and r["skip"] is False
    st, r = api("PUT", f"/api/projects/D/drafts/{did}/claims/{cid}", {"decision": "dismissed"})
    assert r["decision"] == "dismissed" and r["skip"] is True
    assert api("PUT", f"/api/projects/D/drafts/{did}/claims/{cid}", {"decision": "perhaps"})[0] == 400
    st, r = api("PUT", f"/api/projects/D/drafts/{did}/claims/{cid}", {"decision": None})
    assert r["decision"] is None and r["skip"] is False
    v = api("GET", f"/api/projects/D/drafts/{did}")[1]
    assert v["claims"][0]["decision"] is None and "decided" in v["counts"]


def test_the_page_files():
    # after the draft page's styles (m010), before Margin's look (m020), which comes last (sections of margin.css)
    order = sections()
    assert order.index("m010") < order.index("m030") < order.index("m020")
    css = section("m030")
    assert "#" not in css.split("*/", 1)[1]  # colour tokens only
    assert "overflow-y: auto" in css and "position: sticky" in css  # the claims scroll on their own
    assert "attr(data-cite)" in css  # the tag where a source should be cited
    js = (STATIC / "views" / "drafts.js").read_text()
    for label in ("Claim supported", "Claim refuted", "Dismiss claim", "cite here"):
        assert label in js, label
    assert "function foldedCard(" in js and "function reveal(" in js and "function clickToShow(" in js
    assert '"Drop"' not in js  # dismissing took its place
