"""0.19.6: the local model could never name a theme, a rerun did nothing, and the failure was told only in a toast.

1. The JSON schema sent for constrained decoding (Ollama's `format`) lost every field called "description" (it was
   stripped with the schema's own descriptions), so a theme's description could not be written and every local answer
   was rejected three times ("description: Field required").
2. Asking again left those tasks failed, and a failed task is never asked again: the run ended at once.
3. The Themes page now says which themes the AI could not name, and why, from the view (`naming_failed`).
"""
from __future__ import annotations

import json

import pytest
from helpers_mixed_corpus import Cloud, Local, mixed_project, use_local_model

from margin import access, home, schema, themes


# ---------------------------------------------------------------------------------------------
# the schema for constrained decoding keeps every field of the answer
# ---------------------------------------------------------------------------------------------
def _fields(node, path="") -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        for name, sub in (node.get("properties") or {}).items():
            out.add(f"{path}.{name}")
            out |= _fields(sub, f"{path}.{name}")
        if "items" in node:
            out |= _fields(node["items"], f"{path}[]")
        for k in ("anyOf", "oneOf", "allOf"):
            for x in node.get(k, []):
                out |= _fields(x, path)
    return out


def _resolved(model, **kw) -> dict:
    s = model.model_json_schema(**kw)
    defs = s.get("$defs", {})

    def walk(n):
        if isinstance(n, dict):
            if "$ref" in n:
                return walk(defs[n["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in n.items() if k != "$defs"}
        if isinstance(n, list):
            return [walk(x) for x in n]
        return n
    return walk(s)


KINDS = {"split": schema.SplitOut, "verify": schema.VerifyOut, "verify_set": schema.VerifySetOut,
         "check": schema.CheckOut, "expand": schema.ExpandOut, "decompose": schema.DecomposeOut,
         "label": schema.LabelOut, "link": schema.LinkOut, "theme": schema.ThemeOut, "resolve": schema.ResolveOut,
         "theory_codes": schema.TheoryCodesOut, "code_definition": schema.CodeDefinitionOut}


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_the_output_schema_keeps_every_field_of_the_answer(kind):
    want = _fields(_resolved(KINDS[kind]))
    assert want and want <= _fields(schema.output_schema(kind))


def test_a_themes_description_may_be_written_and_is_asked_for():
    s = schema.output_schema("theme")
    assert "description" in s["properties"] and "description" in s["required"]
    assert s["properties"]["description"].get("type") == "string"
    # the schema's own descriptions and titles are still left out
    assert "title" not in s and "title" not in s["properties"]["name_quote"]
    assert "description" not in s["properties"]["description"]


# ---------------------------------------------------------------------------------------------
# a local model that writes only what the schema allows (as Ollama's constrained decoding does)
# ---------------------------------------------------------------------------------------------
class Constrained(Local):
    """The local model as Ollama runs it with `format`: a key the schema does not name is never written."""

    def complete(self, kind, system, user, model, payload=None):
        out = json.loads(super().complete(kind, system, user, model, payload))
        allowed = schema.output_schema(kind).get("properties", {})
        return json.dumps({k: v for k, v in out.items() if k in allowed})


class LeavesOutDescription(Local):
    def complete(self, kind, system, user, model, payload=None):
        out = json.loads(super().complete(kind, system, user, model, payload))
        out.pop("description", None)
        return json.dumps(out)


@pytest.fixture
def local_only(tmp_path, monkeypatch):
    """A project whose documents only a local AI may read (and one no AI may): the main AI is Claude, so every theme
    is named by the local model."""
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    ws = home.create_project("Local only")
    ids = mixed_project(ws, tmp_path / "corpus")
    access.set_documents(ws, [ids["cloud"]], "local")
    rid = themes.run(ws, k=3, mode="words")
    return ws, rid, monkeypatch


def _named(ws, rid) -> int:
    return sum(t["name_source"] == "model" for t in themes.view(ws, rid)["themes"])


def test_a_local_model_under_the_schema_names_the_themes(local_only):
    ws, rid, mp = local_only
    local = Constrained()
    use_local_model(mp, local)
    cloud = Cloud()
    res = themes.name_with_model(ws, rid, cloud, "claude-sonnet")
    assert local.sent and not cloud.sent
    assert res["failed"] == 0 and res["named"] == res["themes"] > 0
    assert _named(ws, rid) == res["named"]
    assert all(t["description"] for t in themes.view(ws, rid)["themes"] if t["name_source"] == "model")


def test_a_failed_naming_is_shown_on_the_page_and_asking_again_asks_the_model(local_only):
    ws, rid, mp = local_only
    bad = LeavesOutDescription()
    use_local_model(mp, bad)
    res = themes.name_with_model(ws, rid, Cloud(), "claude-sonnet")
    n = res["themes"]
    assert n > 0 and res["failed"] == n and res["named"] == 0
    assert len(bad.sent) == 3 * n
    # each try after the first tells the model what was wrong with its last answer
    assert sum("YOUR PREVIOUS ANSWER HAD THESE PROBLEMS" in s and "description" in s for s in bad.sent) == 2 * n
    v = themes.view(ws, rid)
    failed = [t["naming_failed"] for t in v["themes"] if t["naming_failed"]]
    assert len(failed) == n
    assert failed[0]["reason"] == "its answer left out the description"
    assert failed[0]["model"] == "local-model" and failed[0]["problems"]
    # the page of one theme says it too
    one = v["themes"][0]["theme_id"]
    assert themes.view(ws, rid, only=one)["themes"][0]["naming_failed"]

    # asking again is a new request: the model is asked again (before 0.19.6 the run ended at once)
    good = Local()
    use_local_model(mp, good)
    res2 = themes.name_with_model(ws, rid, Cloud(), "claude-sonnet")
    assert good.sent, "the model was not asked again"
    assert res2["named"] == n and res2["failed"] == 0
    assert not any(t["naming_failed"] for t in themes.view(ws, rid)["themes"])


def test_a_theme_you_named_yourself_is_not_marked_as_failed(local_only):
    ws, rid, mp = local_only
    use_local_model(mp, LeavesOutDescription())
    themes.name_with_model(ws, rid, Cloud(), "claude-sonnet")
    tid = themes.view(ws, rid)["themes"][0]["theme_id"]
    themes.edit(ws, rid, "rename", tid, "My own name")
    t = next(x for x in themes.view(ws, rid)["themes"] if x["theme_id"] == tid)
    assert t["name_source"] == "person" and t["naming_failed"] is None


@pytest.mark.parametrize("errors, words", [
    (["description: Field required"], "its answer left out the description"),
    (["description: Field required", "name_quote: Field required"],
     "its answer left out the description and the quote for the name"),
    (["name_quote: quote not found in passage P1: 'x'"], "its quotes were not found word for word in the passages"),
    (["description_quote: there is no passage P9"], "it quoted a passage it was not given"),
    (["qwen's answer was cut off at 4,000 tokens"], "its answer was cut off before it was finished"),
    (["no JSON object in the response"], "its answer was not in the form asked for"),
    ([], "its answer did not pass the checks"),
])
def test_why_a_theme_was_not_named_in_plain_words(errors, words):
    assert themes.naming_reason(errors) == words
