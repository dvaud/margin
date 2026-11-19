"""D1 rest (the optional AI part): the `group_name` kind, a short name for a group of concepts on the concept map.

The kind is registered with its helper and models, its prompt shows the concepts and the numbered passages, its answer
needs a quote and at most six words, and a task of it goes with a document its payload names."""
from __future__ import annotations

import json

import pytest

from margin import ingest, prompts, routing, schema, tasks, taskkinds
from margin import home as ehome

PAYLOAD = {"concepts": ["remote work", "commuting"], "concept_ids": ["c1", "c2"], "docs": [], "filters": {}, "n": 60,
           "name_id": None, "round": 0,
           "passages": [{"n": 1, "passage_id": "p1", "page": 3, "text": "Remote work cut the commuting time.",
                         "concepts": ["remote work", "commuting"]},
                        {"n": 2, "passage_id": "p2", "page": None, "text": "Commuting was the main cost.",
                         "concepts": ["commuting"]}]}


def test_the_kind_is_registered_with_the_namer_and_haiku_first():
    k = taskkinds.get("group_name")
    assert k.helper == "margin-namer" and k.claude[0] == "haiku" and k.prompt_version == "group-name-v1"
    assert routing.HELPERS["group_name"] == "margin-namer"
    assert routing.CLAUDE_DEFAULTS["group_name"] == ("haiku", "sonnet")


def test_the_prompt_names_the_rules_and_shows_the_concepts_and_passages():
    system = prompts.system_prompt("group_name")
    assert "two to six words" in system and "at least three whole words" in system
    user = prompts.user_prompt("group_name", PAYLOAD)
    assert "GROUP OF CONCEPTS: remote work, commuting" in user
    assert "P1 (page 3)" in user and "CONCEPTS IN IT: remote work, commuting" in user and "P2\n" in user


def test_the_answer_needs_at_most_six_words():
    good = {"name": "  Remote   work and commuting ", "name_quote": {"passage": 1, "quote": "cut the commuting time"}}
    assert schema.GroupNameOut.model_validate(good).name == "Remote work and commuting"
    with pytest.raises(ValueError, match="at most six words"):
        schema.GroupNameOut.model_validate({**good, "name": "one two three four five six seven"})
    assert "name_quote" in schema.output_schema("group_name")["properties"]


def test_a_task_of_the_kind_goes_with_its_document(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    ehome.save_settings({**ehome.load_settings(), "embed_backend": "off"})
    ws = ehome.create_project("T")
    try:
        d = tmp_path / "docs"
        d.mkdir()
        (d / "a.txt").write_text("Staff notes\n\n" + " ".join(["Remote work cut the commuting time of the staff in many ways."] * 6), encoding="utf-8")
        ingest.ingest(ws, [d])
        doc = ws.scalar("SELECT doc_id FROM documents LIMIT 1")
        with ws.connect() as cx, tasks.queueing(True):
            tasks.replace_task(cx, "group_name:t1", "group_name", "haiku", {**PAYLOAD, "docs": [doc]})
        assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='group_name'") == 1
        ws.remove_document(doc)
        assert ws.scalar("SELECT COUNT(*) FROM tasks WHERE kind='group_name'") == 0
        assert json.dumps(doc) not in json.dumps(ws.query("SELECT payload_json FROM tasks"))
    finally:
        ws.close_all()
