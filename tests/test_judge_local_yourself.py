"""0.19.8: "Judge it myself" beside Start <local model>.

Found in a user test: one excerpt of a document marked Only a local AI waited for qwen3.5:9b, which needed 8.1 GB of
memory with 6.5 GB free. The panel offered only Start and Start it anyway, side by side; the person did not want to
start a model for one excerpt. Now "Judge it myself" takes the place of Start it anyway: the excerpts wait for the
person, tagged Awaiting manual review, and no model reads them.
"""
from __future__ import annotations

from pathlib import Path

from helpers_mixed_corpus import use_local_model
from test_local_memory import GB, Watched, _queued_check_answered, mixed  # noqa: F401 (the fixture)

from margin import access, claimcheck
from margin.check_exports import not_read_text
from margin.gui import server
from margin.verdicts import WAITING_LOCAL


def _local_items(res: dict, doc_id: str) -> list[dict]:
    return [x for part in res["parts"] for x in part["passages"] if x["doc_id"] == doc_id]


def test_judge_it_myself_hands_the_excerpts_to_the_person(mixed, monkeypatch):
    ws, ids = mixed
    local = Watched(need=int(8.1 * GB), free=int(6.5 * GB))
    use_local_model(monkeypatch, local)
    hid = _queued_check_answered(ws)
    before = claimcheck.hypothesis_result(ws, hid)
    n = before["waiting_local"]
    assert n > 0 and before["status_text"] == WAITING_LOCAL

    assert claimcheck.judge_local_yourself(ws, hid) == n
    res = claimcheck.hypothesis_result(ws, hid)
    assert res["waiting_local"] == 0 and res["status_text"] != WAITING_LOCAL
    items = _local_items(res, ids["local"])
    assert items and all(x["read_by"] == "you" and x["waiting_for_you"] and x["by_choice"] for x in items)
    assert res["waiting_for_you"] >= len(items)
    assert not_read_text(items[0]).startswith("Not read by an AI: you chose to judge it yourself")
    # the excerpts of the other documents are not touched
    assert not any(x["by_choice"] for x in res["parts"][0]["passages"] if x["doc_id"] != ids["local"])

    # no model reads them afterwards, not even "Start it anyway"
    assert claimcheck.local_waiting(ws, [hid]) == []
    assert claimcheck.run_local_parts(ws, [hid], access.Readers(None, "", check_memory=False), retry_failed=True) == 0
    assert local.sent == []
    assert claimcheck.judge_local_yourself(ws, hid) == 0   # a second press does nothing

    # the person's judgement counts, and the excerpt keeps where it came from
    x = items[0]
    claimcheck.set_judgement(ws, x.get("claim_id") or res["parts"][0]["claim_id"], x["passage_id"], "supports")
    after = _local_items(claimcheck.hypothesis_result(ws, hid), ids["local"])[0]
    assert after["user_verdict"] == "supports" and not after["waiting_for_you"] and after["by_choice"]


def test_excerpts_no_model_may_read_are_not_by_choice(mixed, monkeypatch):
    """Without a local model, the excerpts go to the person as before: Awaiting manual review, for its own reason."""
    ws, ids = mixed
    use_local_model(monkeypatch, Watched(free=64 * GB))
    hid = _queued_check_answered(ws)
    for r in claimcheck.local_waiting(ws, [hid]):   # the local model could not be reached: to the person
        claimcheck._to_person(ws, r["task_id"])
    items = _local_items(claimcheck.hypothesis_result(ws, hid), ids["local"])
    assert items and all(x["waiting_for_you"] and not x["by_choice"] for x in items)


def test_the_page_offers_judge_it_myself_in_place_of_start_it_anyway():
    static = Path(server.__file__).parent / "static"
    lib = (static / "lib.js").read_text(encoding="utf-8")
    assert "short && !yourself" in lib and '"Judge it myself"' in lib
    result = (static / "views" / "result.js").read_text(encoding="utf-8")
    assert "/judge-local" in result and "Awaiting manual review" in result and "p.by_choice" in result
    assert ("POST", r"/api/projects/([^/]+)/hypotheses/([^/]+)/judge-local", "post_judge_local") in server.ROUTES or \
        any(r[2] == "post_judge_local" for r in server.ROUTES)


def test_no_more_link_when_the_card_shows_the_whole_excerpt():
    """0.19.8: "more…"/"less" only when the folded card leaves part of the excerpt out; otherwise the ways into the
    document are under Details (a "less" that changed nothing was confusing)."""
    js = (Path(server.__file__).parent / "static" / "views" / "result.js").read_text(encoding="utf-8")
    assert "const moreText = !!folded;" in js and "    if (moreText) {" in js
    assert "!moreText && p.in_corpus ? docLinks() : null" in js


def test_the_thinking_line_stays_inside_its_side():
    # 0.19.13: the latest words on one line inside the side (the newest at the right, the older fading out on the
    # left): the line is clipped by its own box, which never grows past the side (0.19.8: it pushed the box out)
    css = (Path(server.__file__).parent / "static" / "components.css").read_text(encoding="utf-8")
    rule = css.split(".ar-tail {", 1)[1].split("}", 1)[0]
    assert "overflow: hidden" in rule and "align-self: stretch" in rule and "mask-image" in rule
    assert ".ab-side > * { max-width: 100%; }" in css and "min-width: 0; padding: 10px 14px 12px;" in css
