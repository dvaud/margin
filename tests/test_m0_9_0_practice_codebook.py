"""Margin 0.9: social practice theory as built-in codebooks (`practice`, `change_framing`), and what a codebook of
analytical codes needs: the keywords, include, exclude and source columns; the whole codebook sent with every
passage when it is small; its own words for the directions; the practice and the element a label names, with a
grid of practices by code; and links between the elements of a practice."""
import json
import re
from pathlib import Path

import pytest

from test_app import Api, api, home  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "margin" / "gui" / "static"

NOTES = """When the night nurse left, nobody switched the table on again and the games stayed in the cupboard. The residents
asked about it for a week and then stopped asking.

Every morning after breakfast Anna sets up the interactive table in the lounge. She says she just does it, it is
second nature by now, and the residents gather round before she has finished.

The new manager wrote a protocol for the interactive table: staff must log each session on the tablet and report the
numbers to the regional office every month.

The national dementia strategy expects smart devices to reduce agitation in care homes once the roll-out is
complete; the technology will enable more activity with fewer staff.
"""


def _load(ws, folder: Path) -> None:
    """Each note in a file of its own, so that each is a passage of its own."""
    from margin import ingest

    folder.mkdir()
    for i, note in enumerate(NOTES.split("\n\n"), 1):
        (folder / f"care_home_fieldnote_{i}.txt").write_text(" ".join(note.split()) + "\n")
    got = ingest.ingest(ws, [folder])
    assert got["added"] == 4, got


@pytest.fixture
def project(home, tmp_path):
    ws = home.create_project("Fieldnotes")
    _load(ws, tmp_path / "fieldnotes")
    return ws


def _passage(ws, words: str) -> dict:
    rows = [dict(r) for r in ws.query("SELECT * FROM passages WHERE section='body'") if words in r["text"]]
    assert rows, words
    return rows[0]


# ---------------------------------------------------------------------------------------------
# the codebooks
# ---------------------------------------------------------------------------------------------
def test_the_practice_codebooks_are_built_in_after_your_own_and_before_the_sdgs(home):
    from margin import frameworks

    ws = home.create_project("P")
    frameworks.save(ws, "remote", "code,description\nR1,Working from home\n")
    assert list(frameworks.available(ws)) == ["remote", "practice", "change_framing", "sdg", "sdg_goals"]
    p = frameworks.get("practice", ws)
    assert len(p.codes) == 25 and p.source == "bundled" and p.directional and p.practice_and_element
    assert {c.group for c in p.codes.values()} == {"EL", "PF", "KN", "RP", "DY", "NX"}
    assert p.direction_words["helps"] == "holds together" and p.direction_words["hinders"] == "pulls apart"
    assert "Shove" in p.direction_note and "eclecticism" in p.stance and len(p.sources) == 4
    el1 = p.codes["EL1"]
    assert "cupboard" not in el1.keywords and "equipment" in el1.keywords
    assert el1.include and "DY4" in el1.exclude and el1.ref.startswith("Shove et al. 2012: 23")
    cf = frameworks.get("change_framing", ws)
    assert len(cf.codes) == 4 and cf.one_main and not cf.directional and not cf.practice_and_element
    info = p.info(with_codes=True)
    assert info["send_all"] and info["direction_words"]["hinders"] == "pulls apart" and info["sources"]
    assert info["items"][0]["keywords"] and info["items"][0]["source"]
    # their names are taken, and they cannot be removed
    for name in ("practice", "change_framing"):
        with pytest.raises(ValueError):
            frameworks.save(ws, name, "code,description\nX,y\n")
        with pytest.raises(KeyError):
            frameworks.delete(ws, name)


def test_the_built_in_files_are_what_the_builder_writes(tmp_path):
    import subprocess
    import sys

    subprocess.run([sys.executable, str(ROOT / "tools" / "make_practice_codebooks.py"), str(tmp_path)], check=True,
                   capture_output=True)
    shipped = ROOT / "src" / "margin" / "data" / "codebooks"
    for f in ("practice.csv", "practice.json", "change_framing.csv", "change_framing.json"):
        same = [x.read_bytes().replace(b"\r\n", b"\n") for x in (tmp_path / f, shipped / f)]  # any checkout
        assert same[0] == same[1], f
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert '"data/codebooks/*"' in pyproject  # shipped in the wheel


def test_the_new_columns_are_read_and_old_codebooks_still_load(home):
    from margin import frameworks

    codes = frameworks.parse_csv("code,description,group,group_name,keywords,include,exclude,source\n"
                                 'A1,"An app",G,Group,"app; know how ; ;second  nature",Use it,"Not this: A2",Me 2020: 3\n')
    a = codes["A1"]
    assert a.keywords == ("app", "know how", "second nature") and a.include == "Use it"
    assert a.exclude == "Not this: A2" and a.ref == "Me 2020: 3"
    old = frameworks.parse_csv("code,description\nH1,Remote work\n")["H1"]
    assert old.keywords == () and old.include == old.exclude == old.ref == ""
    fw = frameworks.Framework("t", "T", "code", codes)
    # keywords count as whole words only, and their words join the text a code is matched by
    assert fw.keyword_hits("There is an app for that, and I know  how to use it.") == {"A1": ["app", "know how"]}
    assert fw.keyword_hits("A happy application") == {}
    assert "second nature" in fw.code_text("A1") and "Use it" in fw.code_text("A1")
    # a codebook's own JSON: malformed values keep the defaults
    ws = home.create_project("P")
    folder = Path(ws.root) / "frameworks"
    folder.mkdir()
    (folder / "mine.csv").write_text("code,description\nM1,Something\n")
    (folder / "mine.json").write_text(json.dumps({"directional": True, "direction_labels": {"helps": "  makes  it ",
                                                                                           "hinders": 5},
                                                  "sources": "not a list", "one_main": 1}))
    m = frameworks.get("mine", ws)
    assert m.direction_words == {"helps": "makes it", "hinders": "5", "mixed": "mixed", "not_stated": "not stated"}
    assert m.sources == () and m.one_main
    (folder / "mine.json").write_text(json.dumps({"direction_labels": ["no"]}))
    assert frameworks.get("mine", ws).direction_words == frameworks.DIRECTION_WORDS


def test_small_codebooks_go_whole_to_the_ai_and_it_reads_every_passage(project):
    from margin import frameworks, profile

    ws = project
    assert frameworks.get("practice", ws).send_all and not frameworks.get("sdg", ws).send_all
    # the 17 SDGs are small too, but their keyword search is strong (a lexicon): only passages with candidates
    assert profile.reads_every_passage(frameworks.get("practice", ws))
    assert not profile.reads_every_passage(frameworks.get("sdg_goals", ws))
    profile.keyword_pass(ws, "practice")
    plan = profile.label_plan(ws, "practice")
    n_body = int(ws.scalar("SELECT COUNT(*) FROM passages WHERE section='body'"))
    assert plan["all_passages"] and plan["to_read"] == n_body
    assert not profile.label_plan(ws, "practice", all_passages=False)["all_passages"]


def test_keywords_find_candidates_a_word_count_misses(project):
    from margin import profile

    ws = project
    profile.keyword_pass(ws, "practice")
    p = _passage(ws, "second nature")
    cands = {c["code"]: c for c in profile.candidates_of(ws, "practice", p["passage_id"])}
    assert "KN1" in cands and cands["KN1"]["confidence"] >= profile.KEYWORD_HIT
    reason = ws.scalar("SELECT reason FROM labels WHERE framework='practice' AND passage_id=? AND code='KN1'",
                       (p["passage_id"],))
    assert "keywords of this code: second nature" in reason


def _label_task(ws, framework: str, words: str):
    from margin import profile

    profile.keyword_pass(ws, framework)
    p = _passage(ws, words)
    profile.make_label_tasks(ws, framework, [p["passage_id"]], "test-model")
    tid = f"label:{framework}:{p['passage_id']}"
    return tid, p, json.loads(ws.scalar("SELECT payload_json FROM tasks WHERE task_id=?", (tid,)))


def test_the_label_task_carries_the_whole_codebook_with_its_notes_and_words(project):
    from margin import prompts, tasks

    ws = project
    tid, p, payload = _label_task(ws, "practice", "night nurse")
    assert payload["whole_codebook"] and len(payload["candidates"]) == 25
    el1 = next(c for c in payload["candidates"] if c["code"] == "EL1")
    assert el1["include"] and el1["exclude"] and el1["source"] and "found" in el1
    assert payload["direction_words"]["hinders"] == "pulls apart" and payload["practice_and_element"]
    t = ws.query("SELECT * FROM tasks WHERE task_id=?", (tid,))[0]
    system, user = tasks.render(ws, t)
    assert t["prompt_version"] == "label-v2" and prompts.VERSIONS["label"] == "label-v2"
    assert "THE WHOLE CODEBOOK" in user and "Use when:" in user and "Not when:" in user and "Source:" in user
    assert "hinders = pulls apart" in user and "practice and element" in user and "eclecticism" in user
    assert "practice and element" in system
    # a large codebook keeps its candidates and the plain words
    tid2, _p, sdg = _label_task(ws, "sdg", "night nurse")
    assert not sdg.get("whole_codebook") and "direction_words" not in sdg and len(sdg["candidates"]) <= 8


def test_labels_name_the_practice_and_the_element_and_both_are_checked(project):
    from margin import profile, tasks

    ws = project
    tid, p, payload = _label_task(ws, "practice", "night nurse")
    bad = {"labels": [{"code": "DY3", "relevance": "main", "direction": "hinders", "confidence": 0.9,
                       "quote": "nobody switched the table on again", "reason": "the practice stopped",
                       "practice": "playing bingo", "element": "the games"}]}
    ok, errors = tasks.ingest_result(ws, tid, json.dumps(bad), model="test-model")
    assert not ok and any("practice must be words of the passage" in e for e in errors)
    good = {"labels": [
        {"code": "DY3", "relevance": "main", "direction": "hinders", "confidence": 0.9,
         "quote": "nobody switched the table on again", "reason": "the practice stopped",
         "practice": "switched the table on", "element": None},
        {"code": "EL1", "relevance": "mentioned", "direction": "hinders", "confidence": 0.8,
         "quote": "the games stayed in the cupboard", "reason": "the games lie unused",
         "practice": "switched the table on", "element": "the games"},
        {"code": "DY6", "relevance": "mentioned", "direction": "hinders", "confidence": 0.7,
         "quote": "the night nurse left", "reason": "the person carrying it left",
         "practice": "switched the table on", "element": "night nurse"}]}
    ok, errors = tasks.ingest_result(ws, tid, json.dumps(good), model="test-model")
    assert ok, errors
    labs = {r["code"]: r for r in profile.effective(ws, "practice", passage_ids=[p["passage_id"]])}
    assert labs["EL1"]["element"] == "the games" and labs["DY3"]["practice"] == "switched the table on"
    assert labs["DY3"]["element"] is None
    # a person corrects the element, the profile and the table show the codebook's words
    profile.set_label(ws, labs["EL1"]["label_id"], "change", element="games")
    doc = profile.doc_profile(ws, "practice", p["doc_id"])
    assert doc["direction_words"]["hinders"] == "pulls apart" and doc["practice_and_element"]
    item = next(i for c in doc["codes"] if c["code"] == "EL1" for i in c["items"])
    assert item["element"] == "games" and item["practice"] == "switched the table on"
    rows = [r for r in profile.labels_table(ws, "practice") if r["Code"] == "EL1"]
    assert rows[0]["Direction"] == "pulls apart" and rows[0]["Element"] == "games" and "Practice" in rows[0]
    assert "Practice" not in profile.labels_table(ws, "sdg")[0] if profile.labels_table(ws, "sdg") else True
    # answering again replaces the parts with the labels
    ok, _ = tasks.ingest_result(ws, tid, json.dumps({"labels": []}), model="test-model")
    assert ok and not ws.scalar("SELECT COUNT(*) FROM label_parts WHERE label_id=?", (labs["EL1"]["label_id"],))


def test_one_main_framing_per_passage(project):
    from margin import tasks

    ws = project
    tid, p, payload = _label_task(ws, "change_framing", "national dementia strategy")
    assert payload["one_main"] and payload["whole_codebook"] and "direction_words" not in payload
    two = {"labels": [{"code": "CF4", "relevance": "main", "confidence": 0.9, "quote": "smart devices",
                       "reason": "technology by itself"},
                      {"code": "CF3", "relevance": "main", "confidence": 0.5, "quote": "national dementia strategy",
                       "reason": "a strategy"}]}
    ok, errors = tasks.ingest_result(ws, tid, json.dumps(two), model="test-model")
    assert not ok and any("one main code" in e for e in errors)
    two["labels"][1]["relevance"] = "mentioned"
    ok, errors = tasks.ingest_result(ws, tid, json.dumps(two), model="test-model")
    assert ok, errors


def test_the_grid_by_practice_and_labels_of_your_own(project):
    from margin import profile

    ws = project
    profile.keyword_pass(ws, "practice")
    a = _passage(ws, "Every morning")
    b = _passage(ws, "new manager")
    profile.add_label(ws, "practice", a["passage_id"], "DY2", "Every morning after breakfast", "main", "helps",
                      practice="Setting up the interactive table", element="interactive table")
    profile.add_label(ws, "practice", a["passage_id"], "KN1", "second nature", "main", "helps",
                      practice="setting up the interactive table")
    profile.add_label(ws, "practice", b["passage_id"], "NX3", "report the numbers to the regional office",
                      "main", "not_stated", practice="the setting up the interactive table")
    profile.add_label(ws, "practice", b["passage_id"], "RP1", "a protocol", "main", "not_stated")
    g = profile.grid(ws, "practice", level="practice")
    assert g["rows"] == "practices" and g["unnamed"] >= 1
    row = g["documents"][0]
    assert row["title"].lower().endswith("setting up the interactive table") and row["passages"] == 2
    assert row["elements"] == ["interactive table"]
    key = row["doc_id"]
    assert g["cells"][key] == {"DY2": 1, "KN1": 1, "NX3": 1}
    assert g["directions"][key]["DY2"] == {"helps": 1}
    assert [c["code"] for c in g["codes"]] == ["DY2", "KN1", "NX3"]  # in the codebook's (natural) order
    assert "Practice" in profile.grid_table(g)[0]
    # the codebook keeps the practice only where it asks for it
    lid = profile.add_label(ws, "change_framing", b["passage_id"], "CF1", None, practice="logging")
    assert not ws.scalar("SELECT 1 FROM label_parts WHERE label_id=?", (lid,))
    # removing the document removes the parts too
    assert ws.scalar("SELECT COUNT(*) FROM label_parts WHERE doc_id=?", (a["doc_id"],)) == 2
    ws.remove_document(a["doc_id"])
    assert not ws.scalar("SELECT COUNT(*) FROM label_parts WHERE doc_id=?", (a["doc_id"],))
    assert ws.scalar("SELECT COUNT(*) FROM label_parts") == 1  # the other document's


def test_concept_cards_show_the_labels_that_name_them(project):
    from margin import profile

    ws = project
    profile.keyword_pass(ws, "practice")
    a = _passage(ws, "Every morning")
    profile.add_label(ws, "practice", a["passage_id"], "EL1", "the interactive table", "mentioned", "helps",
                      element="the interactive table", practice="setting up")
    got = profile.labels_naming(ws, ["interactive table"])
    assert got and got[0]["code"] == "EL1" and got[0]["role"] == "element" and got[0]["passages"] == 1
    assert got[0]["examples"] == ["the interactive table"]
    assert profile.labels_naming(ws, ["table tennis"]) == []
    assert profile.labels_naming(ws, ["interact"]) == []  # whole words only
    assert profile.labels_naming(ws, ["interactive tables"])[0]["code"] == "EL1"  # as the glossary compares words


# ---------------------------------------------------------------------------------------------
# links between the elements of a practice
# ---------------------------------------------------------------------------------------------
def test_element_relations_in_the_link_task(project):
    from margin import prompts, tasks, terms

    ws = project
    # four short notes are too few for the glossary: two terms by hand, where their words occur
    with ws.connect() as cx:
        for tid, label in (("t0table", "interactive table"), ("t1protocol", "protocol")):
            cx.execute("INSERT INTO terms VALUES (?,?,?,?,?,?,?,?)", (tid, label, label, len(label.split()), 1, 1, 1, 1.0))
            for r in cx.execute("SELECT passage_id, doc_id, start, text FROM passages").fetchall():
                i = r["text"].find(label)
                if i >= 0:
                    cx.execute("INSERT INTO term_mentions VALUES (?,?,?,?,?)",
                               (tid, r["passage_id"], r["doc_id"], r["start"] + i, r["start"] + i + len(label)))
    a, b = "t0table", "t1protocol"
    tid = terms.make_link_task(ws, a, b, "test-model", relations="elements")
    assert tid.endswith(":elements")
    t = ws.query("SELECT * FROM tasks WHERE task_id=?", (tid,))[0]
    payload = json.loads(t["payload_json"])
    assert payload["relations"] == "elements" and t["prompt_version"] == "link-v2" == prompts.VERSIONS["link"]
    system, user = tasks.render(ws, t)
    assert "element_of" in system and "as elements of a practice" in user
    sa, sb = payload["terms"][0]["snippets"][0]["text"], payload["terms"][1]["snippets"][0]["text"]
    qa, qb = (" ".join(x.split()[:4]) for x in (sa, sb))  # quotes are whole words (ENLENS 0.14.3)
    word = {"relations": [{"a": 1, "b": 2, "relation": "broader", "confidence": 0.9, "quote_a": qa,
                           "quote_b": qb}]}
    ok, errors = tasks.ingest_result(ws, tid, json.dumps(word), model="test-model")
    assert not ok and any("relations asked for" in e for e in errors)
    # b requires a: stored from the smaller id, turned round
    ans = {"relations": [{"a": 2, "b": 1, "relation": "needs", "confidence": 0.8, "quote_a": qb,
                          "quote_b": qa}]}
    ok, errors = tasks.ingest_result(ws, tid, json.dumps(ans), model="test-model")
    assert ok, errors
    row = ws.query("SELECT a, b, relation FROM concept_links WHERE source='model'")[0]
    assert (row["a"], row["b"], row["relation"]) == (a, b, "required_by")
    # a person can add an element relation too, and it is turned round the same way
    terms.set_link(ws, b, a, "add", "element_of")
    assert ws.scalar("SELECT relation FROM concept_links WHERE source='person'") == "has_element"
    with pytest.raises(ValueError):
        terms.set_link(ws, a, b, "add", "eats")


# ---------------------------------------------------------------------------------------------
# the app
# ---------------------------------------------------------------------------------------------
def test_api_profile_by_practice_plan_default_and_element_judging(api, home, tmp_path):
    ws = home.create_project("Notes")
    _load(ws, tmp_path / "fieldnotes")
    st, fws = api("GET", "/api/projects/Notes/frameworks")
    assert st == 200
    names = [f["name"] for f in fws["frameworks"]]
    assert names.index("practice") < names.index("sdg")
    st, _ = api("POST", "/api/projects/Notes/profile/keywords", {"framework": "practice"})
    assert st == 200
    import time
    for _ in range(100):
        st, prof = api("GET", "/api/projects/Notes/profile?framework=practice&level=practice")
        if prof.get("pass1", {}).get("done"):
            break
        time.sleep(0.05)
    assert st == 200 and prof["grid"]["rows"] == "practices"
    st, plan = api("GET", "/api/projects/Notes/profile/plan?framework=practice")
    assert st == 200 and plan["all_passages"] is True
    st, plan = api("GET", "/api/projects/Notes/profile/plan?framework=practice&all=0")
    assert plan["all_passages"] is False
    st, body = api("GET", "/api/projects/Notes/profile?framework=practice&level=nonsense")
    assert st == 400
    st, body = api("POST", "/api/projects/Notes/concepts/judge", {"relations": "vibes"})
    assert st == 400 and "words or elements" in body["error"]
    p = _passage(ws, "Every morning")
    st, body = api("POST", "/api/projects/Notes/labels", {"framework": "practice", "passage_id": p["passage_id"],
                                                          "code": "DY2", "direction": "helps",
                                                          "practice": "setting up the table", "element": "table"})
    assert st == 200
    st, doc = api("GET", f"/api/projects/Notes/documents/{p['doc_id']}/profile?framework=practice")
    assert st == 200
    item = next(i for c in doc["codes"] if c["code"] == "DY2" for i in c["items"])
    assert item["practice"] == "setting up the table" and doc["direction_words"]["helps"] == "holds together"


def test_the_page_uses_the_codebooks_words():
    profile_js = (STATIC / "views" / "profile.js").read_text()
    sources_js = (STATIC / "views" / "sources.js").read_text()
    concepts_js = (STATIC / "views" / "concepts.js").read_text()
    assert "direction_words" in profile_js and "directionWords(prof)" in sources_js
    assert '"practice"' in profile_js and "practice_and_element" in sources_js
    assert "element_of" in concepts_js and "relations: \"elements\"" in concepts_js and "in_labels" in concepts_js
