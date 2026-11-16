"""0.19.12: on an excerpt awaiting manual review, selecting words highlights them, as the AI's quote is highlighted;
and the way back from "Judge it myself": "Let the local model read them".

Asked by the user after 0.19.8: judging an excerpt by hand, they wanted to mark the words that matter as the AI does
(the way to it was "Quote another sentence … Use it", for replacing the AI's quote); and they wanted to change their
mind after choosing to judge the excerpts themselves, and run the local model after all.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers_mixed_corpus import use_local_model
from test_local_memory import GB, Watched, _queued_check_answered, mixed  # noqa: F401 (the fixture)

from margin import access, claimcheck
from margin.gui import server
from margin.verdicts import WAITING_LOCAL

STATIC = Path(server.__file__).parent / "static"
NODE = shutil.which("node")


def _local_items(res: dict, doc_id: str) -> list[dict]:
    return [{**x, "claim_id": part["claim_id"]} for part in res["parts"] for x in part["passages"]
            if x["doc_id"] == doc_id]


def test_changed_my_mind_the_local_model_reads_them_after_all(mixed, monkeypatch):
    ws, ids = mixed
    local = Watched(need=4 * GB, free=64 * GB)
    use_local_model(monkeypatch, local)
    hid = _queued_check_answered(ws)
    n = claimcheck.judge_local_yourself(ws, hid)
    items = _local_items(claimcheck.hypothesis_result(ws, hid), ids["local"])
    assert n > 1 and all(x["by_choice"] for x in items)
    judged = items[0]   # one judged by hand before changing one's mind, with words highlighted
    claimcheck.set_judgement(ws, judged["claim_id"], judged["passage_id"], "supports",
                             quote=" ".join(judged["text"].split()[:4]))

    assert claimcheck.local_again(ws, hid) == n
    res = claimcheck.hypothesis_result(ws, hid)
    assert res["waiting_local"] == n and res["status_text"] == WAITING_LOCAL
    back = {x["passage_id"]: x for x in _local_items(res, ids["local"])}
    assert not any(x["by_choice"] or x["waiting_for_you"] for x in back.values())
    assert back[judged["passage_id"]]["user_verdict"] == "supports"   # what you judged meanwhile stays
    assert claimcheck.local_again(ws, hid) == 0   # a second press does nothing

    # the local model reads them; your judgement still counts over its own, with no made-up "read again"
    assert claimcheck.run_local_parts(ws, [hid], access.Readers(None, "", check_memory=False), retry_failed=True)
    assert local.sent
    after = {x["passage_id"]: x for x in _local_items(claimcheck.hypothesis_result(ws, hid), ids["local"])}
    assert all(x["read_by"] == "local" and x["ai_read"] for x in after.values())
    mine = after[judged["passage_id"]]
    assert mine["user_verdict"] == "supports" and mine["verdict"] == "supports" and mine["quote_by"] == "you"
    assert not any(x.get("reread") for x in after.values())


def test_excerpts_no_model_may_read_are_not_handed_back(mixed, monkeypatch):
    ws, ids = mixed
    use_local_model(monkeypatch, Watched(free=64 * GB))
    hid = _queued_check_answered(ws)
    for r in claimcheck.local_waiting(ws, [hid]):   # the local model could not be reached: to the person
        claimcheck._to_person(ws, r["task_id"])
    assert claimcheck.local_again(ws, hid) == 0
    assert all(x["waiting_for_you"] for x in _local_items(claimcheck.hypothesis_result(ws, hid), ids["local"]))


def test_highlighting_words_of_an_excerpt_you_judge(mixed, monkeypatch):
    """Words selected across a line end and cutting a word are kept whole and shown as your highlight."""
    ws, ids = mixed
    use_local_model(monkeypatch, Watched(free=64 * GB))
    hid = _queued_check_answered(ws)
    claimcheck.judge_local_yourself(ws, hid)
    x = _local_items(claimcheck.hypothesis_result(ws, hid), ids["local"])[0]
    words = x["text"].split()
    sel = " ".join(words[1:5])[1:]   # the selection cuts the first word
    claimcheck.set_judgement(ws, x["claim_id"], x["passage_id"], "partially_supports", quote=sel)
    y = _local_items(claimcheck.hypothesis_result(ws, hid), ids["local"])[0]
    assert y["quote_by"] == "you" and " ".join(y["quote"].split()) == " ".join(words[1:5])
    assert x["text"][y["quote_start"]:y["quote_end"]] == y["quote"]


def test_the_page_highlights_on_selection_and_offers_the_way_back():
    js = (STATIC / "views" / "result.js").read_text(encoding="utf-8")
    assert "/local-again" in js and "Let the local model read them" in js and "startReadLocal(false)" in js
    assert 'if (p.read_by === "you") {' in js and 'passageEl.addEventListener("mouseup"' in js
    assert "Highlight the words that show it" in js and "selectionPlace(p.text" in js
    assert any(r[2] == "post_local_again" for r in server.ROUTES)


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_selection_place_finds_the_words_whole():
    js = (STATIC / "views" / "result.js").read_text(encoding="utf-8")
    fn = js.split("export function selectionPlace", 1)[1].split("\n}\n", 1)[0]
    text = "The poor live near landfills; the rich do not. And in countries\nlike the United States,  where racism"
    cases = ["d in countries like the", "the rich do not.", "nothing here", "States, where rac", "(a"]
    script = (f"function selectionPlace{fn}\n}}\nconst t = {json.dumps(text)};\n"
              f"console.log(JSON.stringify({json.dumps(cases)}.map((q) => {{ const r = selectionPlace(t, q); "
              "return r && t.slice(r[0], r[1]); })));")
    out = json.loads(subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out == ["And in countries\nlike the", "the rich do not.", None, "States,  where racism", None]
