"""Margin 0.1: check a draft. The claims of a draft that need a source (found by the AI with the quote check, or by
rules), the person's changes, the checks of the claims against the documents, the draft's own AI setting (enforced
on every task that holds its text), what Claude read of it, the connector, and the app's API and page."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import fake_servers
from test_app import api, home  # noqa: F401  (fixtures)

from margin import access, claimcheck, drafts, taskqueue, tasks
from margin.llm import BaselineBackend

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"

DRAFT = """Hydrogen and water

Electrolysis needs about 9 litres of water for every kilogram of hydrogen (Smith et al., 2021). It also raises local water stress in arid regions.

Studies show that desalination adds little to the cost of green hydrogen. Most export projects are planned in deserts.

We interviewed 12 planners in two ministries. This paper argues that water should be priced. Is this realistic?
"""


class Cloudy:
    """A stand-in for a cloud model (the Claude API): it must never be asked anything in these tests."""
    name = "anthropic"
    router = None

    def __init__(self):
        self.asked = []

    def complete(self, kind, system, user, model, payload):
        self.asked.append((kind, user))
        raise AssertionError(f"a cloud model was asked a {kind} task")


# ---------------------------------------------------------------------------------------------
# finding the claims
# ---------------------------------------------------------------------------------------------
def test_rules_find_the_claims_a_reader_would_want_a_source_for():
    got = drafts.rule_claims(DRAFT)
    texts = [c["claim"] for c in got]
    assert any("9 litres" in t for t in texts)
    assert any(t.startswith("Studies show") for t in texts)
    assert any(t.startswith("Most export projects") for t in texts)
    # not the author's own work, a question or a heading
    assert not any(t.startswith(("We interviewed", "This paper", "Is this", "Hydrogen and water")) for t in texts)
    first = next(c for c in got if "9 litres" in c["claim"])
    assert first["cited"] is True and first["kind"] == "statistic" and "(Smith" not in first["claim"]
    assert all(c["quote"] in DRAFT for c in got)


def test_parts_are_whole_paragraphs_and_cover_the_draft():
    text = "\n\n".join(f"Paragraph {i}. " + "Words and more words. " * 40 for i in range(12))
    spans = drafts.parts(text, size=2000)
    assert len(spans) > 1 and spans[0][0] == 0 and spans[-1][1] == len(text)
    for a, b in spans:
        assert b - a <= 2000 and text[a:b].startswith("Paragraph")
    long = "One sentence here. " * 400
    assert all(b - a <= 1000 for a, b in drafts.parts(long, size=1000))


def test_a_draft_is_kept_apart_from_the_documents(loaded):
    n_docs = loaded.scalar("SELECT COUNT(*) FROM documents")
    did = drafts.new_draft(loaded, DRAFT, "Water chapter")
    assert loaded.scalar("SELECT COUNT(*) FROM documents") == n_docs
    assert drafts.summary(loaded, did)["title"] == "Water chapter"
    with pytest.raises(ValueError, match="too short"):
        drafts.new_draft(loaded, "Too short.")


def test_without_a_model_the_rules_find_the_claims(loaded):
    did = drafts.new_draft(loaded, DRAFT)
    r = drafts.find_claims(loaded, did, BaselineBackend(), "baseline")
    assert r["by"] == "rules" and r["found"] >= 3 and "rules" in r["note"]
    v = drafts.view(loaded, did)
    assert v["draft"]["found_by"] == "rules" and all(c["source"] == "rules" for c in v["claims"])
    for c in v["claims"]:
        assert v["text"][c["start"]:c["end"]] == c["quote"]  # the place in the draft is exact


def test_the_ai_s_claims_go_through_the_quote_check(loaded):
    did = drafts.new_draft(loaded, DRAFT)
    tid = drafts.plan(loaded, did, "m")[0]
    payload = json.loads(loaded.scalar("SELECT payload_json FROM tasks WHERE task_id=?", (tid,)))
    assert payload["draft_id"] == did and payload["text"] in DRAFT
    bad = {"claims": [{"quote": "Electrolysis needs a lot of water.", "claim": "Electrolysis needs a lot of water.",
                       "kind": "statistic", "cited": False, "why": "x"}]}
    ok, errs = tasks.ingest_result(loaded, tid, bad, model="m")
    assert not ok and "not found in the passage" in errs[0]
    assert not loaded.scalar("SELECT COUNT(*) FROM draft_claims WHERE draft_id=?", (did,))
    good = {"claims": [{"quote": "It also raises local water stress in arid regions.",
                        "claim": "Electrolysis raises local water stress in arid regions.", "kind": "cause",
                        "cited": "no", "why": "an effect"}], "note": None}
    ok, errs = tasks.ingest_result(loaded, tid, good, model="m")
    assert ok, errs
    c = drafts.view(loaded, did)["claims"][0]
    assert c["claim"].startswith("Electrolysis raises") and c["kind"] == "causal" and c["cited"] is False
    assert DRAFT[c["start"]:c["end"]] == "It also raises local water stress in arid regions."


def test_the_person_keeps_drops_rewords_and_marks_claims(loaded):
    did = drafts.new_draft(loaded, DRAFT)
    drafts.find_by_rules(loaded, did)
    claims = drafts.view(loaded, did)["claims"]
    drafts.update_claim(loaded, did, claims[0]["claim_id"], skip=True)
    drafts.update_claim(loaded, did, claims[1]["claim_id"], claim="Desalination adds little to the cost of hydrogen.")
    s = DRAFT.index("We interviewed")
    mine = drafts.add_claim(loaded, did, s, s + len("We interviewed 12 planners in two ministries."))
    with pytest.raises(ValueError):
        drafts.add_claim(loaded, did, s, s + 3)
    todo = drafts.to_check(loaded, did)
    assert claims[0]["claim_id"] not in {c["claim_id"] for c in todo} and mine in {c["claim_id"] for c in todo}
    # finding again keeps what the person touched
    drafts.find_by_rules(loaded, did)
    after = {c["claim_id"]: c for c in drafts.view(loaded, did)["claims"]}
    assert after[claims[0]["claim_id"]]["skip"] and after[mine]["source"] == "person"
    assert after[claims[1]["claim_id"]]["claim"].startswith("Desalination adds little")


# ---------------------------------------------------------------------------------------------
# checking the claims
# ---------------------------------------------------------------------------------------------
def test_each_claim_is_checked_as_a_hypothesis_of_the_draft(loaded):
    did = drafts.new_draft(loaded, DRAFT)
    drafts.find_by_rules(loaded, did)
    out = drafts.check_claims(loaded, did, BaselineBackend(), "baseline", k=4, per_doc=2, expand=True)
    assert out["checked"] and not out["errors"]
    v = drafts.view(loaded, did)
    assert v["counts"]["checked"] == len(out["checked"]) and v["counts"]["to_check"] == 0
    for hid in out["checked"]:
        r = claimcheck.hypothesis_result(loaded, hid)
        assert r["draft_id"] == did and r["batch_id"] == v["draft"]["batch_id"] and not r["decomposed"]
    c = next(c for c in v["claims"] if c["hyp_id"])
    assert c["status"] and set(c["evidence"]) == {"supports", "partly", "refutes"}
    rows = drafts.export_rows(loaded, did)
    assert rows[0]["Sentence in the draft"] and "Supporting documents" in rows[0]
    # the results list knows the draft; removing the draft removes its checks
    assert any(h["draft_id"] == did for h in claimcheck.history(loaded))
    drafts.delete(loaded, did)
    assert not loaded.scalar("SELECT COUNT(*) FROM hypotheses WHERE draft_id=?", (did,))
    assert not loaded.scalar("SELECT COUNT(*) FROM draft_claims")


def test_a_draft_kept_from_claude_never_reaches_it(loaded, home):  # noqa: F811
    did = drafts.new_draft(loaded, DRAFT, ai_access="local")
    cloud = Cloudy()
    # finding: no local model is chosen, so rules, and the cloud model is not asked
    r = drafts.find_claims(loaded, did, cloud, "opus")
    assert r["by"] == "rules" and not cloud.asked
    # checking: no search words from the AI; every excerpt waits for the person (no local model), none for Claude
    out = drafts.check_claims(loaded, did, cloud, "opus", k=4, per_doc=2, expand=True)
    assert out["checked"] and not cloud.asked
    for hid in out["checked"]:
        rows = loaded.query("SELECT task_id, access FROM tasks WHERE task_id LIKE ?", (f"%{hid}%",))
        assert rows and all(r["access"] != "cloud" for r in rows)
        assert not any(r["task_id"].startswith("expand:") for r in rows)
    assert not loaded.scalar("SELECT COUNT(*) FROM draft_sent")
    # the guard itself: a task naming the draft, or a claim of it, is labelled with its setting
    with loaded.connect() as cx:
        assert access.label_payload(cx, {"draft_id": did, "text": "x"}) == "local"
        assert access.label_payload(cx, {"subject_kind": "user_claim", "subject_id": out["checked"][0],
                                         "claim": "x", "passages": []}) == "local"
    assert out["checked"][0] in access.restricted_hypotheses(loaded)
    # changing the setting relabels the tasks not answered yet
    tid = drafts.plan(loaded, did, "sonnet")[0]
    assert loaded.scalar("SELECT access FROM tasks WHERE task_id=?", (tid,)) == "local"
    drafts.update(loaded, did, ai_access="cloud")
    assert loaded.scalar("SELECT access FROM tasks WHERE task_id=?", (tid,)) == "cloud"
    drafts.update(loaded, did, ai_access="none")
    assert loaded.scalar("SELECT access FROM tasks WHERE task_id=?", (tid,)) == "none"


def test_by_queue_claude_code_reads_the_draft_and_it_is_recorded(loaded, home):  # noqa: F811
    did = drafts.new_draft(loaded, DRAFT, ai_access="cloud")
    ids = drafts.queue_find(loaded, did, taskqueue.router(loaded))
    assert ids and all(loaded.scalar("SELECT queued FROM tasks WHERE task_id=?", (t,)) == 1 for t in ids)
    batch = taskqueue.next_tasks(loaded, kind="claims", taken_by="test")
    assert batch["claim"] and batch["system"].startswith("You read part of a researcher's own draft")
    assert "PASSAGE:" in batch["tasks"][0]["prompt"]
    text = json.loads(loaded.scalar("SELECT payload_json FROM tasks WHERE task_id=?", (batch["tasks"][0]["task_id"],)))["text"]
    answers = [{"task_id": t["task_id"], "answer": {"claims": drafts.rule_claims(text)}} for t in batch["tasks"]]
    r = taskqueue.submit(loaded, batch["claim"], answers)
    assert r["stored"] == len(answers)
    sent = access.draft_ledger(loaded, did)
    assert sent["times"] >= 1 and sent["parts_read"] >= 1 and sent["routes"] == ["Claude Code"]
    assert drafts.finding(loaded, did)["waiting"] == 0 and drafts.view(loaded, did)["claims"]
    # a draft Claude may not read is never handed out
    other = drafts.new_draft(loaded, DRAFT, ai_access="local")
    drafts.queue_find(loaded, other)
    assert taskqueue.next_tasks(loaded, kind="claims")["claim"] is None


def test_the_offline_demo_and_the_prompt_know_the_task():
    out = json.loads(BaselineBackend().complete("claims", "", "", "baseline", {"text": DRAFT}))
    assert out["claims"] and all(c["quote"] in DRAFT for c in out["claims"])
    from margin import prompts, routing, schema

    assert prompts.VERSIONS["claims"] == "claims-v1" and "need a source" in prompts.system_prompt("claims")
    assert schema.output_schema("claims")["properties"]["claims"]
    assert routing.HELPERS["claims"] == "margin-reader" and "claims" in taskqueue.ORDER


# ---------------------------------------------------------------------------------------------
# the app
# ---------------------------------------------------------------------------------------------
def test_the_api_of_drafts(api, corpus):  # noqa: F811
    srv, url = fake_servers.start("ollama")
    try:
        assert api("PUT", "/api/settings", {"backend": "ollama", "ollama_url": url,
                                            "ollama_model": fake_servers.FAKE_MODEL, "embed_backend": "off"})[0] == 200
        assert api("POST", "/api/projects", {"name": "P"})[0] == 200
        for f in sorted(corpus.iterdir()):
            assert api("POST", f"/api/projects/P/uploads?batch=b1&name={f.name}", raw=f.read_bytes())[0] == 200
        st, r = api("POST", "/api/projects/P/ingest", {"batch": "b1"})
        assert api.wait(r["job"]["id"])["state"] == "done"

        st, r = api("POST", "/api/projects/P/drafts", {"text": DRAFT, "title": "Ch. 3", "ai_access": "cloud"})
        assert st == 200, r
        did = r["draft"]["draft_id"]
        st, up = api("POST", "/api/projects/P/drafts/upload?name=notes.md", raw=DRAFT.encode())
        assert st == 200 and up["draft"]["file_name"] == "notes.md"
        assert api("POST", "/api/projects/P/drafts/upload?name=x.exe", raw=b"MZ")[0] == 400
        assert len(api("GET", "/api/projects/P/drafts")[1]["drafts"]) == 2

        st, r = api("POST", f"/api/projects/P/drafts/{did}/find", {})
        job = api.wait(r["job"]["id"])
        assert job["state"] == "done" and job["result"]["by"] == "ai" and job["result"]["found"] >= 3, job
        st, v = api("GET", f"/api/projects/P/drafts/{did}")
        assert st == 200 and v["documents"] == 3 and all(c["source"] == "ai" for c in v["claims"])

        first = v["claims"][0]["claim_id"]
        assert api("PUT", f"/api/projects/P/drafts/{did}/claims/{first}", {"skip": True})[1]["skip"] is True
        s = DRAFT.index("This paper argues")
        st, m = api("POST", f"/api/projects/P/drafts/{did}/claims", {"start": s, "end": s + 40})
        assert st == 200 and m["claim_id"]

        st, r = api("POST", f"/api/projects/P/drafts/{did}/check", {"k": 3})
        job = api.wait(r["job"]["id"], timeout=120)
        assert job["state"] == "done" and job["result"]["checked"], job
        st, v = api("GET", f"/api/projects/P/drafts/{did}")
        assert v["counts"]["to_check"] == 0 and any(c["status"] for c in v["claims"])
        assert api("POST", f"/api/projects/P/drafts/{did}/check", {})[0] == 400  # nothing left to check
        st, x = api("GET", f"/api/projects/P/drafts/{did}/export.xlsx")
        assert st == 200 and x[:2] == b"PK"
        st, c = api("GET", f"/api/projects/P/drafts/{did}/export.csv")
        assert st == 200 and b"Sentence in the draft" in c
        hid = next(c["hyp_id"] for c in v["claims"] if c["hyp_id"])
        assert api("GET", f"/api/projects/P/hypotheses/{hid}")[1]["draft_id"] == did

        assert api("PUT", f"/api/projects/P/drafts/{did}", {"ai_access": "none"})[1]["draft"]["ai_access"] == "none"
        assert api("GET", "/api/projects/P/overview")[1]["drafts"] == 2
        assert api("DELETE", f"/api/projects/P/drafts/{did}")[1]["checks"] >= 1
        assert api("GET", f"/api/projects/P/drafts/{did}")[0] == 404
    finally:
        srv.shutdown()


def test_the_page_files(api):  # noqa: F811
    index = (STATIC / "index.html").read_text()
    assert "/static/m010.css" in index and 'data-route="drafts"' in index
    css = (STATIC / "m010.css").read_text()
    assert "#" not in css.split("*/", 1)[1]  # colour tokens only, no fixed colours
    js = (STATIC / "views" / "drafts.js").read_text()
    assert "export async function renderDrafts(" in js and "export async function renderDraft(" in js
    assert "./views/drafts.js" in (STATIC / "app.js").read_text()
    assert "drafts:" in (STATIC / "features.js").read_text()
    for f in ("/static/m010.css", "/static/views/drafts.js"):
        assert api("GET", f, token=False)[0] == 200, f


def test_a_draft_can_come_from_a_pdf(tmp_path, loaded):
    from helpers import make_pdf

    p = make_pdf(tmp_path / "chapter.pdf", ["Electrolysis needs about 9 litres of water per kilogram of hydrogen.",
                                            "Studies show that desalination adds little to the cost."], title="Ch. 4")
    text, title = drafts.read_file(p)
    assert "9 litres" in text and "desalination" in text and title in (None, "Ch. 4")
    did = drafts.new_draft(loaded, text, title, "chapter.pdf")
    assert drafts.find_by_rules(loaded, did) == 2
    with pytest.raises(ValueError, match="Word file"):
        drafts.read_file(tmp_path / "x.exe")


# ---------------------------------------------------------------------------------------------
# ENLENS's projects, brought over
# ---------------------------------------------------------------------------------------------
def _enlens(tmp_path, monkeypatch):
    from margin.store import Workspace

    src = tmp_path / "enlens-home"
    a = Workspace.create(src / "projects" / "Alpha")
    a.set_meta("from", "enlens")
    Workspace.create(src / "projects" / "Beta")
    elsewhere = Workspace.create(tmp_path / "elsewhere" / "Gamma")
    (src / "links.json").write_text(json.dumps({"Gamma": str(elsewhere.root)}))
    (src / "frameworks").mkdir()
    (src / "frameworks" / "mycodes.csv").write_text("code,description\nA,Something\n")
    (src / "settings.json").write_text(json.dumps({"k": 13, "project": "Beta", "unknown": 1}))
    monkeypatch.setenv("ENLENS_HOME", str(src))
    return src


def test_enlens_projects_are_copied_and_enlens_keeps_its_own(home, tmp_path, monkeypatch):  # noqa: F811
    src = _enlens(tmp_path, monkeypatch)
    before = sorted(str(p.relative_to(src)) for p in src.rglob("*"))
    info = home.enlens_projects()
    assert info["projects"] == ["Alpha", "Beta", "Gamma"] and info["linked"] == ["Gamma"] and info["here"] == 0
    r = home.import_enlens()
    assert r["copied"] == ["Alpha", "Beta"] and r["linked"] == ["Gamma"] and r["codebooks"] == 1 and r["settings"]
    assert home.list_projects() == ["Alpha", "Beta", "Gamma"]
    assert home.open_project("Alpha").meta("from") == "enlens"          # the database came along
    assert home.project_path("Gamma") == tmp_path / "elsewhere" / "Gamma"  # linked, not copied
    s = home.load_settings()
    assert s["k"] == 13 and s["project"] == "Beta"
    assert (home.home() / "frameworks" / "mycodes.csv").exists()
    assert sorted(str(p.relative_to(src)) for p in src.rglob("*")) == before  # ENLENS's folder untouched
    assert home.enlens_projects()["projects"] == []
    assert home.import_enlens()["copied"] == []  # a second time: nothing new


def test_no_enlens_is_looked_for_in_a_chosen_data_folder(home, monkeypatch):  # noqa: F811
    monkeypatch.delenv("ENLENS_HOME", raising=False)
    assert home.enlens_projects() is None  # MARGIN_HOME is set (as in every test): the real ~/enlens is not read
    with pytest.raises(ValueError, match="No ENLENS"):
        home.import_enlens()


def test_the_api_brings_enlens_projects_over(api, tmp_path, monkeypatch):  # noqa: F811
    _enlens(tmp_path, monkeypatch)
    st, s = api("GET", "/api/state")
    assert st == 200 and s["enlens"]["projects"] == ["Alpha", "Beta", "Gamma"]
    st, r = api("POST", "/api/import-enlens", {"names": ["Alpha"]})
    assert st == 200 and r["copied"] == ["Alpha"]
    st, s = api("GET", "/api/state")
    assert [p["name"] for p in s["projects"]] == ["Alpha"] and s["enlens"]["projects"] == ["Beta", "Gamma"]
    assert api("POST", "/api/import-enlens", {"names": "Alpha"})[0] == 400
    page = (STATIC / "views" / "projects.js").read_text()
    assert "export function enlensCard(" in page and "enlensCard" in (STATIC / "views" / "setup.js").read_text()
