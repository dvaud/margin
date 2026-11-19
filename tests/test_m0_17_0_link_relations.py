"""Margin 0.17.0: Margin's elements of a practice (0.9) beside ENLENS's link-v2 kinds.

The two lists share two meanings: elements say *requires* and *clashes with*, link-v2 says *needs* and *clashes*. An
answer is read in the list its task asked for (tasks._store_link), so a link of a words task is stored in link-v2's
words and a link of an elements task in Margin's, whichever of the two words the model used. No AI.
"""
from __future__ import annotations

import pytest

from margin import prompts, tasks
from margin.schema import ELEMENT_RELATIONS, LINK_RELATIONS
from test_link_v2 import PAYLOAD, QA, QB, _answer, _stored, cx  # noqa: F401  (fixture)

ELEMENTS = {**PAYLOAD, "relations": "elements"}


@pytest.mark.parametrize("said, stored", [("needs", "needs"), ("requires", "needs"), ("clashes", "clashes"),
                                          ("clashes_with", "clashes"), ("shapes", "shapes")])
def test_a_words_task_stores_link_v2s_words(cx, said, stored):  # noqa: F811
    ok, errors = tasks._store_link(cx, None, PAYLOAD, _answer(said), "m")
    assert ok and errors == []
    assert _stored(cx) == [("t1", "t2", stored, "model", QA, QB)]


@pytest.mark.parametrize("said, stored", [("requires", "requires"), ("needs", "requires"), ("clashes_with", "clashes_with"),
                                          ("clashes", "clashes_with"), ("shapes", "shapes"), ("element_of", "element_of")])
def test_an_elements_task_stores_margins_words(cx, said, stored):  # noqa: F811
    ok, errors = tasks._store_link(cx, None, ELEMENTS, _answer(said), "m")
    assert ok and errors == []
    assert _stored(cx) == [("t1", "t2", stored, "model", QA, QB)]


def test_each_task_refuses_the_other_lists_own_kinds(cx):  # noqa: F811
    ok, errors = tasks._store_link(cx, None, ELEMENTS, _answer("broader"), "m")
    assert not ok and "use one of the relations asked for" in errors[0]
    ok, errors = tasks._store_link(cx, None, PAYLOAD, _answer("element_of"), "m")
    assert not ok and "use one of the relations asked for" in errors[0]
    assert _stored(cx) == []


def test_both_lists_are_offered():
    assert {"needs", "shapes", "clashes"} <= set(LINK_RELATIONS)
    assert ELEMENT_RELATIONS == ("requires", "shapes", "replaces", "element_of", "clashes_with")
    user = prompts.user_prompt("link", {**ELEMENTS, "terms": [{**t, "snippets": t["snippets"]} for t in PAYLOAD["terms"]]})
    assert "as elements of a practice" in user and "(needs and shapes" not in user
    assert "(needs and shapes: turned round" in prompts.user_prompt("link", PAYLOAD)
