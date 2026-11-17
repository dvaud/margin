"""Roadmap J4.3, the rest (validation.py): a run answered by a local model is named after its model and reported
beside the Claude run; and a real project's judgements made by a person are the right answers the AI's answers in that
project are scored against (`margin validate person`), shown in the report beside the invented gold set. No AI."""
from __future__ import annotations

import json

import pytest

from margin import profile
from margin import validation as v
from margin.cli import main
from margin.store import Workspace
from margin.verdicts import PERSON
from test_validation_report import GOLD, _check, _label, _pass


def _local(p: dict, model: str = "qwen3.5:4b") -> dict:
    """The same pass, answered by a model on this computer (`queue run --backend ollama --model …`)."""
    p = json.loads(json.dumps(p))
    for it in p["checks"] + p["labels"]:
        for a in it["answers"]:
            a.update(route="local model server", model=model, models=[model] if a["models"] else [], helper=None)
    return p


# ---- a local model's run ------------------------------------------------------------------------------------------
def test_a_local_run_is_named_after_its_model(tmp_path):
    run = v.make_run([_local(_pass())], GOLD, date="2026-11-17")
    assert run["route"] == "qwen3-5-4b" and run["local"] is True
    assert run["models"] == {"check": {"qwen3.5:4b": 5}, "label": {"qwen3.5:4b": 5}}
    assert v.write_run(run, tmp_path).name == "2026-11-17-qwen3-5-4b.json"
    k2 = v.make_run([_local(_pass(), "ifm/k2-horizon:0.9b")], GOLD, date="2026-11-17")
    assert k2["route"] == "ifm-k2-horizon-0-9b"                  # two local models never share a name
    claude = v.make_run([_pass()], GOLD, date="2026-11-13")
    assert claude["route"] == "claude-code" and claude["local"] is False
    assert "(a model on this computer)" in v.to_markdown(run) and "(a model on this computer)" not in v.to_markdown(claude)


def test_the_report_sets_the_newest_run_of_each_route_side_by_side(tmp_path, capsys):
    runs = tmp_path / "runs"
    v.write_run(v.make_run([_pass()], GOLD, date="2026-11-13"), runs)
    v.write_run(v.make_run([_local(_pass(checks=[_check("H1", "supported", "contested")]))], GOLD,
                           date="2026-11-10"), runs)                              # an older local run: not shown
    v.write_run(v.make_run([_local(_pass())], GOLD, date="2026-11-17"), runs)
    v.write_run(v.make_run([_local(_pass(), "ifm/k2-horizon:0.9b")], GOLD, date="2026-11-16"), runs)
    got = [p.name for p in v.latest_runs(runs)]
    assert got == ["2026-11-17-qwen3-5-4b.json", "2026-11-16-ifm-k2-horizon-0-9b.json", "2026-11-13-claude-code.json"]
    out = tmp_path / "report.md"
    assert main(["validate", "report", "--latest", str(runs), "--out", str(out)]) == 0
    md = out.read_text("utf-8")
    assert md.startswith("# Validation report") and "## The routes side by side" in md
    table = md.split("## The routes side by side", 1)[1].split("\n## ", 1)[0]
    assert "| qwen3-5-4b (on this computer) | 2026-11-17 | qwen3.5:4b | 40% of 5 (4 finished) |" in table
    assert "| claude-code | 2026-11-13 | haiku, sonnet | 40% of 5 (4 finished) |" in table
    assert "2026-11-10" not in md
    assert md.count("## Limits") == 1 and md.index("## Limits") > md.index("## claude-code, 2026-11-13")
    assert "### Checks (hypotheses against the documents)" in md
    # one route only: the report is as it was
    one = tmp_path / "one"
    v.write_run(v.make_run([_pass()], GOLD, date="2026-11-13"), one)
    md1, _p = v.report(latest=one)
    assert "side by side" not in md1 and md1.count("## Limits") == 1


# ---- a real project's judgements, made by a person ----------------------------------------------------------------
@pytest.fixture
def real(tmp_path):
    """A project with excerpts judged by an AI, some of them then judged by a person; and codes of a codebook."""
    ws = Workspace.create(tmp_path / "Repair cafés")
    rows = [  # (ver_id, AI verdict, model, person's verdict, note)
        ("v1", "supports", "sonnet", "supports", None),               # agreed
        ("v2", "supports", "sonnet", "partially_supports", None),     # graded otherwise
        ("v3", "refutes", "qwen3.5:4b", "refutes", None),             # agreed, a local model
        ("v4", "not_enough_info", "sonnet", "not_relevant", None),    # agreed: not about it
        ("v5", "supports", "sonnet", None, "check the page"),         # a comment alone: no judgement
        ("v6", "partially_supports", "sonnet", None, None),           # left alone: no right answer
        ("v7", "not_enough_info", PERSON, "supports", None),          # only a person judged it: nothing to score
    ]
    with ws.connect() as cx:
        for vid, ai, model, uv, note in rows:
            cx.execute("INSERT INTO verifications(ver_id, subject_kind, subject_id, passage_id, doc_id, verdict, "
                       "confidence, quote, model, prompt_version, user_verdict, user_note, user_by) VALUES "
                       "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (vid, "user_claim", "c1", f"p{vid}", "d1", ai, 0.8, "a quote of the document's text", model,
                        "check-v5", uv, note, "anna" if uv else None))
        for lid, pid, code, source in [("l1", "d1:0001", "SKILLS", "model"), ("l2", "d1:0001", "WASTE", "model"),
                                       ("l3", "d1:0002", "SKILLS", "model"), ("l4", "d1:0002", "COMMUNITY", "model"),
                                       ("l5", "d1:0002", "LEARNING", "person"), ("l6", "d1:0009", "WASTE", "person"),
                                       ("l7", "d1:0003", "WASTE", "keywords")]:
            cx.execute("INSERT INTO labels(label_id, passage_id, doc_id, framework, code, relevance, direction, "
                       "quote, source, model, prompt_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (lid, pid, "d1", "repair", code, "main", "not_stated", "a quote", source,
                        "haiku" if source == "model" else None, "label-v1" if source == "model" else None))
        for pid in ("d1:0001", "d1:0002"):  # the AI labelled these two (real passage ids hold a colon); 0009 never
            cx.execute("INSERT INTO tasks(task_id, kind, model, status) VALUES (?,?,?,?)",
                       (f"label:repair:{pid}", "label", "haiku", "done"))
    profile.set_label(ws, "l1", "accept")
    profile.set_label(ws, "l2", "reject")
    profile.set_label(ws, "l3", "change", relevance="mentioned")
    profile.set_label(ws, "l7", "accept")          # a keyword label (no AI): not the AI's answer
    # l4: an AI code nobody decided on: not a right answer
    yield ws
    ws.close_all()


def test_only_what_a_person_decided_counts(real):
    rec = v.collect_person(real, "Repair cafés study")
    assert rec["kind"] == "person" and rec["project"] == "Repair cafés study"
    assert sorted((c["ai"], c["person"], c["model"]) for c in rec["checks"]) == [
        ("not_relevant", "not_relevant", "sonnet"), ("refutes", "refutes", "qwen3.5:4b"),
        ("supports", "partially_supports", "sonnet"), ("supports", "supports", "sonnet")]
    assert rec["checks_person_only"] == 1
    assert sorted((lb["kept"], lb["changed"]) for lb in rec["labels"]) == [(False, False), (True, False), (True, True)]
    assert rec["labels_added"] == [{"framework": "repair"}]      # LEARNING on d1:0002; WASTE on d1:0009 the AI never read
    assert rec["people"] >= 1
    sc = v.score_person(rec)
    assert sc["checks"]["n"] == 4 and sc["checks"]["accuracy"] == 0.75
    assert sc["checks"]["grounded_accuracy"] == 1.0
    assert set(sc["checks_by_model"]) == {"sonnet", "qwen3.5:4b"}
    assert sc["labels"] == {"n": 3, "kept": pytest.approx(0.667), "changed": 1, "added": 1}


def test_the_file_holds_no_text_and_names_the_project_as_asked(real, tmp_path):
    rec = v.collect_person(real)
    assert rec["project"] == "Repair cafés"                        # the folder's name when no label is given
    path = v.write_person(rec, tmp_path / "runs")
    assert path.parent.name == "person" and path.name.endswith("-repair-caf-s.json")
    raw = path.read_text("utf-8")
    assert "quote" not in raw and "a quote" not in raw and "check the page" not in raw and "d1:0001" not in raw
    assert v.latest_runs(tmp_path / "runs") == []                  # not a run of the gold set


def test_the_report_shows_a_persons_judgements_beside_the_gold_set(real, tmp_path, capsys):
    runs = tmp_path / "runs"
    v.write_run(v.make_run([_pass()], GOLD, date="2026-11-13"), runs)
    assert main(["--ws", str(real.root), "validate", "person", "--label", "Repair cafés study",
                 "--runs", str(runs)]) == 0
    said = json.loads(capsys.readouterr().out)
    assert said["excerpts"] == 4 and said["codes_decided"] == 3 and "no document text" in said["note"]
    md, _p = v.report(latest=runs)
    assert "## Right answers from a real project, labelled by a person" in md
    sec = md.split("## Right answers from a real project, labelled by a person", 1)[1]
    assert "### Repair cafés study (" in sec
    assert "the AI's grade was the person's for 75% of 4 excerpts" in sec
    assert "1 more excerpts were judged by the person with no AI answer" in sec
    assert "| Partly supports | 0 | 0 | 0 | 0 | 0% |" not in sec   # rows by the person's grade
    assert "| Partly supports | 1 | 0 | 0 | 0 | 0% |" in sec       # the AI said Supports where the person said Partly
    assert "kept 67% of the 3 codes" in sec and "added 1 codes" in sec
    assert "The person saw the AI's answer" in sec
    # a later file of the same project replaces it in the report; nothing at all: no section
    md0, _ = v.report(latest=tmp_path / "empty")
    assert md0 is None


def test_a_project_where_no_person_decided_anything(tmp_path):
    ws = Workspace.create(tmp_path / "Untouched")
    try:
        rec = v.collect_person(ws)
    finally:
        ws.close_all()
    assert rec["checks"] == [] and rec["labels"] == [] and rec["people"] == 0
    md = v.person_markdown([rec])
    assert "none that both an AI and a person judged" in md
