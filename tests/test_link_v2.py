"""D1, the last part: the AI's link tasks (`link`, prompt link-v2) propose the three kinds the text patterns and a
person could already give: *needs*, *shapes* and *clashes with*. Each is stored as the AI's proposal (source
`model`, with both quotes), from the smaller term id with the relation turned round as the other links are, so the
Concepts page and the map show it, and a person accepts, changes or rejects it, as before."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from margin import benchmark, prompts, tasks
from margin.llm import BaselineBackend
from margin.schema import LinkOut, output_schema
from margin.store import Workspace

PAYLOAD = {"terms": [
    {"n": 1, "term_id": "t1", "label": "hydrogen production",
     "snippets": [{"passage_id": "d1:0001", "title": "Report", "text": "Hydrogen production needs water in large amounts."}]},
    {"n": 2, "term_id": "t2", "label": "water",
     "snippets": [{"passage_id": "d1:0002", "title": "Report", "text": "Water is scarce in arid regions of the south."}]}]}
QA, QB = "Hydrogen production needs water", "Water is scarce in arid regions"


@pytest.fixture
def cx(tmp_path):
    ws = Workspace.create(tmp_path / "p")
    with ws.connect() as c:
        yield c
    ws.close_all()


def _answer(rel, a=1, b=2, qa=QA, qb=QB):
    return {"relations": [{"a": a, "b": b, "relation": rel, "confidence": 0.8, "quote_a": qa, "quote_b": qb}]}


def _stored(cx):
    return [tuple(r) for r in cx.execute("SELECT a, b, relation, source, quote_a, quote_b FROM concept_links")]


def test_the_prompt_is_link_v2_and_names_the_three_kinds():
    assert prompts.VERSIONS["link"] == "link-v2"
    sp = prompts.system_prompt("link")
    for words in ("- needs: the first term (a) requires or depends on the second (b);",
                  "- shapes: the first term (a) influences or determines the second (b);",
                  "- clashes: the two are at odds or in conflict (the same from both ends);",
                  "same|broader|narrower|needs|shapes|clashes|related|different", "(a: 2, b: 1)"):
        assert words in sp, words
    assert "turned round" in prompts.user_prompt("link", PAYLOAD)
    enum = json.dumps(output_schema("link"))
    for k in ("needs", "shapes", "clashes", "needed_by", "shaped_by"):
        assert f'"{k}"' in enum


@pytest.mark.parametrize("said, kind", [("needs", "needs"), ("requires", "needs"), ("depends on", "needs"),
                                        ("shapes", "shapes"), ("influences", "shapes"), ("clashes with", "clashes"),
                                        ("conflicts", "clashes"), ("needed by", "needed_by"), ("shaped_by", "shaped_by")])
def test_the_answer_takes_the_three_kinds_in_other_words(said, kind):
    assert LinkOut.model_validate(_answer(said)).relations[0].relation == kind


def test_an_unknown_kind_is_still_refused():
    with pytest.raises(ValidationError):
        LinkOut.model_validate(_answer("loves"))


@pytest.mark.parametrize("rel", ["needs", "shapes", "clashes"])
def test_each_new_kind_is_stored_as_the_ais_proposal_with_its_quotes(cx, rel):
    ok, errors = tasks._store_link(cx, None, PAYLOAD, _answer(rel), "claude-haiku-5-5")
    assert ok and errors == []
    assert _stored(cx) == [("t1", "t2", rel, "model", QA, QB)]


@pytest.mark.parametrize("rel, stored", [("needs", "needed_by"), ("shapes", "shaped_by"), ("clashes", "clashes")])
def test_a_pair_turned_round_is_stored_from_the_smaller_id_with_its_relation_turned_round(cx, rel, stored):
    """"Water needs hydrogen production" (a: 2, b: 1): stored as t1 needed_by t2, the quotes swapped with it."""
    ok, _ = tasks._store_link(cx, None, PAYLOAD, _answer(rel, a=2, b=1, qa=QB, qb=QA), "m")
    assert ok
    assert _stored(cx) == [("t1", "t2", stored, "model", QA, QB)]


def test_a_quote_not_in_the_terms_passages_is_sent_back(cx):
    ok, errors = tasks._store_link(cx, None, PAYLOAD, _answer("needs", qa="words nobody wrote"), "m")
    assert not ok and "quote_a not found in the passages of term 1" in errors[0]
    # the quotes are checked against the term each side names: turned round, quote_a is term 2's
    ok, errors = tasks._store_link(cx, None, PAYLOAD, _answer("needs", a=2, b=1), "m")
    assert not ok and any("quote_a not found in the passages of term 2" in e for e in errors)
    assert _stored(cx) == []


def test_the_offline_demo_proposes_a_kind_the_passages_state():
    got = BaselineBackend()._link(PAYLOAD)["relations"][0]
    assert (got["a"], got["b"], got["relation"]) == (1, 2, "needs")
    back = {"terms": [{**PAYLOAD["terms"][0], "label": "water", "snippets": PAYLOAD["terms"][1]["snippets"]},
                      {**PAYLOAD["terms"][1], "label": "hydrogen production", "snippets": PAYLOAD["terms"][0]["snippets"]}]}
    got = BaselineBackend()._link(back)["relations"][0]
    assert (got["a"], got["b"], got["relation"]) == (2, 1, "needs")      # said of term 2: the pair turned round
    plain = {"terms": [{**t, "snippets": [{"passage_id": "x", "title": "", "text": "Nothing joins these words here."}]}
                       for t in PAYLOAD["terms"]]}
    assert BaselineBackend()._link(plain)["relations"][0]["relation"] in ("related", "different")


def test_a_pair_turned_round_is_the_same_decision_when_two_routes_are_compared():
    lnk = {"terms": [{}, {}]}
    assert benchmark._decisions("link", lnk, _answer("needs", a=2, b=1)) == {"1-2": "needed_by"}
    assert benchmark._decisions("link", lnk, _answer("needed_by")) == {"1-2": "needed_by"}


def test_comparing_two_runs_reads_a_pair_turned_round_as_the_same_decision(tmp_path):
    """Review 7: evaluation._decision reads each pair from its smaller term number."""
    from margin import evaluation

    ws = Workspace.create(tmp_path / "e")
    with ws.connect() as c:
        for tid, ans in (("x1", _answer("needs", a=2, b=1)), ("x2", _answer("needed_by")), ("x3", _answer("needs"))):
            c.execute("INSERT INTO results(task_id, attempt, kind, model, prompt_version, raw_json, valid, errors_json, "
                      "received_at) VALUES (?,1,'link','m','link-v2',?,1,'[]','2026-11-18T00:00:00+00:00')",
                      (tid, json.dumps(ans)))
    d = {t: evaluation._decision(ws, t, "link") for t in ("x1", "x2", "x3")}
    ws.close_all()
    assert d["x1"] == d["x2"] == ((1, 2, "needed_by"),) and d["x3"] == ((1, 2, "needs"),)
