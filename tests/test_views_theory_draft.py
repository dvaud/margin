"""The framework draft page (views/theory-draft.js, 0.19.2), run in Node with tests/_views.py: what it draws, what it sends.

Each scenario renders the real page from a canned answer of GET …/codebook-theory/draft and acts as a person would.
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const BASE = "/api/projects/Study/codebook-theory/draft";
const C = (o) => ({ group: "", meaning: "", when_to_use: "", when_not: "", keep: true, checked: false, how: "found",
  sources: [], examples: [], words: [], ai: null, ...o });
const DRAFT = (o = {}) => ({ title: "Repair theory", name: "repair", where: "project", doc_ids: ["d1", "d2"], focus: "", rev: 3,
  reading: { state: "none", job: null, problems: [] }, left_out: [],
  groups: [{ key: "g1", name: "Practice", about: "How people repair together" }, { key: "g2", name: "Materials", about: "" }],
  concepts: [
    C({ key: "c1", name: "habitus", group: "g1", meaning: "Lasting dispositions that shape action", words: [] }),
    C({ key: "c2", name: "competence", group: "g1", meaning: "Know-how of a practice", keep: false }),
    C({ key: "c3", name: "tool", group: "g2", meaning: "A thing used to repair" }),
    C({ key: "c4", name: "care", group: "", meaning: "" , sources: [{ doc_id: "d1", title: "Caring", quote: "Care is   maintenance of the world", start: 1, end: 9, page: 4 }] }),
  ], ...o });
const OFFER = (o = {}) => ({ offered: true, reader: "claude", parts: 3, why: "",
  documents: [{ doc_id: "d1", title: "Practice theory", level: "cloud", parts: 2, offered: true, why: "" },
              { doc_id: "d2", title: "Caring", level: "cloud", parts: 1, offered: true, why: "" }], ...o });
async function open(t, draft = DRAFT(), offer = OFFER(), settings = { backend: "claude_code" }) {
  t.state({ settings });
  t.answer(`GET ${BASE}`, { draft, offer, documents: [{ doc_id: "d1", title: "Practice theory" }, { doc_id: "d2", title: "Caring" }] });
  t.answer(`GET ${BASE}/counts`, { documents: 12, counts: { c1: 5, c3: 0 } });
  t.answer(`PUT ${BASE}`, (body) => ({ draft: { rev: (body.rev || 0) + 1, reading: { stale: false } } }));
  await t.render("views/theory-draft.js", "renderTheoryDraft");
}
const puts = (t) => t.calls.filter((c) => c.method === "PUT");

await scenario("drawn", async (t) => {
  const d = DRAFT();
  d.concepts[0].words = ["habitus"]; d.concepts[2].words = ["tool"];   // a row says in how many documents its words are
  await open(t, d);
  const groups = t.view.querySelectorAll(".cb-group").map((g) => ({
    name: g.querySelector(".td-group-input") ? g.querySelector(".td-group-input").value : t.text(g.querySelector(".cb-group-name")),
    rows: g.querySelectorAll("li.td-concept").map((li) => t.text(li.querySelector(".cb-code-name"))),
    text: t.text(g) }));
  const bar = t.text(t.view.querySelector(".td-bar"));
  return { groups, bar, make: t.buttons().find((b) => b.label === "Make the codebook"), text: t.text() };
});

await scenario("edit a definition", async (t) => {
  const d = DRAFT();
  d.concepts[0].ai = { meaning: "Lasting dispositions that shape action", model: "claude-sonnet" };
  await open(t, d);
  await t.click(/^Habitus /);
  const markBefore = t.text(t.view.querySelector(".cb-draft-mark"));
  await t.type("Definition", "Ways of acting learnt over a life");
  const before = puts(t).length;            // nothing is sent while the person types
  await t.settle(900);
  const sent = puts(t);
  return { markBefore, markAfter: t.text(t.view.querySelector(".cb-draft-mark")), before, sent,
    row: t.text(t.view.querySelector('li[data-key="c1"] .cb-code-desc')) };
});

await scenario("take out", async (t) => {
  const d = DRAFT();
  d.concepts = [d.concepts[0]];
  await open(t, d);
  await t.click("Take out");
  await t.settle(900);
  const p = puts(t).pop();
  return { kept: p.body.concepts.map((c) => [c.key, c.keep]), bar: t.text(t.view.querySelector(".td-bar")),
    make: t.buttons().find((b) => b.label === "Make the codebook") };
});

await scenario("discard, then not", async (t) => {
  await open(t);
  await t.click("Discard the draft");
  const asked = t.text(t.dialog());
  await t.click("Cancel", { within: t.dialog() });
  return { asked, deletes: t.calls.filter((c) => c.method === "DELETE").length, navs: t.navs, open: t.dialogs().length };
});

await scenario("discard", async (t) => {
  await open(t);
  t.answer(`DELETE ${BASE}`, { ok: true });
  await t.click("Discard the draft");
  await t.click("Discard the draft", { within: t.dialog() });
  return { deletes: t.calls.filter((c) => c.method === "DELETE").map((c) => c.path), navs: t.navs, toasts: t.toasts() };
});

await scenario("set aside", async (t) => {
  const d = DRAFT({ reading: { state: "read", model: "claude-opus", parts: 3, parts_read: 3, drafted: 9, problems: [] },
    left_out: [{ name: "Field", doc_id: "d1", title: "Practice theory", quote: "A field is a space of positions.", start: 10, end: 40, page: 7 },
               { name: "field", doc_id: "d2", title: "Caring", quote: "the field", start: 1, end: 3, page: 1 },
               { name: "Habitus", doc_id: "d2", title: "Caring", quote: "habitus again", start: 5, end: 9, page: 2 }] });
  await open(t, d);
  t.answer(`POST ${BASE}/evidence`, { passages: [] });
  const fold = t.view.querySelector(".td-aside summary");
  const summary = t.text(fold);
  await t.click(fold);
  const rows = t.view.querySelectorAll(".td-aside-list li").map((li) => t.text(li));
  await t.click("Add", { within: t.view.querySelector(".td-aside") });
  await t.settle(900);
  const added = puts(t).pop().body.concepts.find((c) => c.name === "Field");
  return { summary, rows, added, open: t.text(t.view.querySelector("li.cb-open .cb-code-name")),
    asideAfter: t.view.querySelector(".td-aside") ? t.text(t.view.querySelector(".td-aside summary")) : null };
});

await scenario("reads line, Claude", async (t) => {
  await open(t);
  return t.text(t.view.querySelector(".td-theory .ai-where"));
});

await scenario("reads line, local", async (t) => {
  const offer = OFFER({ reader: "local", parts: 1, documents: [
    { doc_id: "d1", title: "Practice theory", level: "local", parts: 1, offered: true, why: "" },
    { doc_id: "d2", title: "Caring", level: "none", parts: 0, offered: false, why: "" },
    { doc_id: "d3", title: "Scan", level: "cloud", parts: 0, offered: false, why: "Its text could not be read." }] });
  await open(t, DRAFT({ doc_ids: ["d1", "d2", "d3"] }), offer, { backend: "claude_code" });
  return { line: t.text(t.view.querySelector(".td-theory .ai-where")), local: !!t.view.querySelector(".td-theory .icon-house"),
    docs: t.view.querySelectorAll(".td-theory p.muted.small").map((p) => t.text(p)) };
});

await scenario("no AI may read", async (t) => {
  await open(t, DRAFT(), OFFER({ offered: false, reader: null, why: "Every theory document is marked No AI." }));
  return { text: t.text(t.view.querySelector(".td-theory")), read: t.find("Read the theory") !== null,
    make: t.buttons().find((b) => b.label === "Make the codebook"), main: t.find("Make the codebook").className };
});

await scenario("problems of a reading", async (t) => {
  await open(t, DRAFT({ reading: { state: "read", model: "claude-opus", parts: 2, parts_read: 2, drafted: 6,
    problems: ["Part 2 was cut short.", "Two quotes were not in the text."] } }));
  return t.view.querySelectorAll(".td-theory .notice li").map((li) => t.text(li));
});

await scenario("a reading that failed", async (t) => {
  await open(t, DRAFT({ reading: { state: "failed", problems: ["First problem", "Claude Code did not answer."] } }));
  const n = t.view.querySelector(".td-theory .notice-error");
  return { notice: t.text(n), retry: t.find("Read it again", { within: n }) !== null };
});

await scenario("read the theory", async (t) => {
  await open(t);
  t.answer(`POST ${BASE}/read`, { job: { id: "j7", state: "running" } });
  const running = DRAFT({ reading: { state: "running", job: "j7", problems: [] } });
  t.answer(`GET ${BASE}`, { draft: running, offer: OFFER(), documents: [] });
  t.answer("GET /api/jobs/j7", { id: "j7", state: "running", progress: { done: 1, total: 3 } });
  await t.type("What do you want to find out? (optional)", "How do repair cafés work?");
  await t.click("Read the theory");
  const order = t.calls.filter((c) => c.method !== "GET").map((c) => `${c.method} ${c.path}`);
  return { order, focus: t.calls.find((c) => c.method === "PUT").body.focus, theory: t.text(t.view.querySelector(".td-theory")),
    frame: t.view.querySelector("fieldset.td-frame").disabled, make: t.buttons().find((b) => b.label === "Make the codebook"),
    why: t.text(t.view.querySelector(".td-bar")) };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("theory_draft"))


@needs_node
def test_the_page_draws_each_group_with_its_concepts_and_those_without_a_group_last(page):
    groups = page["drawn"]["groups"]
    assert [g["name"] for g in groups] == ["Practice", "Materials", "Concepts without a group"]
    assert groups[0]["rows"] == ["Habitus", "Competence"]        # in the codebook first, then the rest
    assert "Also in the theory, not in the codebook" in groups[0]["text"]
    assert "How people repair together" in groups[0]["text"] and "1 of 2 in the codebook" in groups[0]["text"]
    assert groups[2]["rows"] == ["Care"]
    assert "“Care is maintenance of the world”" in groups[2]["text"]   # no definition: the theory's first quote
    assert "in 5 documents" in groups[0]["text"] and "in no document" in groups[1]["text"]


@needs_node
def test_the_bar_counts_the_concepts_in_the_codebook_and_offers_make_the_codebook(page):
    d = page["drawn"]
    assert "3 concepts in the codebook · 0 done · 0 with examples" in d["bar"]
    assert "The draft is kept as you work." in d["bar"]
    assert d["make"] == {"label": "Make the codebook", "disabled": False}
    assert "4 concepts in 2 groups, 3 in the codebook." in d["text"]


@needs_node
def test_a_changed_definition_is_saved_whole_a_moment_later_with_the_drafts_revision(page):
    e = page["edit a definition"]
    assert e["before"] == 0
    assert len(e["sent"]) == 1
    put = e["sent"][0]
    assert put["path"] == "/api/projects/Study/codebook-theory/draft"
    body = put["body"]
    assert body["rev"] == 3 and body["title"] == "Repair theory" and body["name"] == "repair"
    assert [g["key"] for g in body["groups"]] == ["g1", "g2"]
    c1 = next(c for c in body["concepts"] if c["key"] == "c1")
    assert c1["meaning"] == "Ways of acting learnt over a life"
    assert e["row"] == "Ways of acting learnt over a life"     # the closed line follows at once


@needs_node
def test_the_ai_draft_mark_names_the_model_and_goes_when_the_definition_is_rewritten(page):
    e = page["edit a definition"]
    assert e["markBefore"].startswith("AI draft The definition is still the AI’s words (claude-sonnet)")
    assert "Rewrite it in your own words" in e["markBefore"]
    assert e["markAfter"] == ""


@needs_node
def test_take_out_saves_the_concept_out_of_the_codebook_and_make_then_waits(page):
    t = page["take out"]
    assert t["kept"] == [["c1", False]]
    assert "0 concepts in the codebook" in t["bar"] and "Add a concept first." in t["bar"]
    assert t["make"]["disabled"] is True


@needs_node
def test_discarding_asks_first_and_cancel_keeps_the_draft(page):
    d = page["discard, then not"]
    assert "Discard the draft?" in d["asked"] and "What the AI read is kept" in d["asked"]
    assert d == {**d, "deletes": 0, "navs": [], "open": 0}


@needs_node
def test_discarding_deletes_the_draft_and_goes_back_to_the_codebooks(page):
    d = page["discard"]
    assert d["deletes"] == ["/api/projects/Study/codebook-theory/draft"]
    assert d["navs"] == ["#/codebooks"]
    assert any("The draft is discarded." in x for x in d["toasts"])


@needs_node
def test_the_concepts_the_ai_set_aside_are_listed_once_a_name_and_one_can_be_added(page):
    s = page["set aside"]
    assert s["summary"] == "1 concept set aside by the AI"       # "field" twice, "Habitus" is in the draft already
    assert len(s["rows"]) == 1 and s["rows"][0].startswith("Field Practice theory, p. 7")
    a = s["added"]
    assert a["how"] == "ai" and a["keep"] is True and a["words"] == ["field"]
    assert a["sources"] == [{"doc_id": "d1", "title": "Practice theory", "quote": "A field is a space of positions.",
                             "start": 10, "end": 40, "page": 7}]
    assert s["open"] == "Field" and s["asideAfter"] is None     # opened, and no longer set aside


@needs_node
def test_the_line_under_read_the_theory_says_who_reads_how_much(page):
    assert page["reads line, Claude"] == "Claude, on your plan, reads these 2 whole documents, in 3 parts."


@needs_node
def test_a_document_only_a_local_ai_may_read_is_read_on_this_computer_and_the_others_say_why(page):
    r = page["reads line, local"]
    assert r["line"] == ("The AI on this computer reads this whole document: the text never leaves it. It starts when you "
                         "press its own Start.")   # 0.20.1: Claude is the main AI here
    assert r["local"] is True
    assert "“Caring” is marked No AI: only the terms it defines outright are used." in r["docs"]
    assert "“Scan”: Its text could not be read." in r["docs"]


@needs_node
def test_without_a_document_the_ai_may_read_the_page_says_why_and_make_is_the_main_button(page):
    r = page["no AI may read"]
    assert "Every theory document is marked No AI." in r["text"] and r["read"] is False
    assert r["make"]["disabled"] is False and "btn-primary" in r["main"]


@needs_node
def test_each_problem_of_a_reading_is_a_line_of_its_own(page):
    assert page["problems of a reading"] == ["Part 2 was cut short.", "Two quotes were not in the text."]


@needs_node
def test_a_reading_that_failed_says_its_last_problem_and_offers_read_it_again(page):
    f = page["a reading that failed"]
    assert f["notice"].splitlines()[0] == "Claude Code did not answer."
    assert "First problem" not in f["notice"] and f["retry"] is True


@needs_node
def test_read_the_theory_saves_the_question_first_then_starts_the_reading_and_the_framework_waits(page):
    r = page["read the theory"]
    assert r["order"] == ["PUT /api/projects/Study/codebook-theory/draft", "POST /api/projects/Study/codebook-theory/draft/read"]
    assert r["focus"] == "How do repair cafés work?"
    assert "Reading the theory: 1 of 3 steps done" in r["theory"]
    assert r["frame"] is True and r["make"]["disabled"] is True
    assert "Wait until the reading is done." in r["why"]
