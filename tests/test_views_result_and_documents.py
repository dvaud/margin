"""The result page, a document's page and the Documents page, run in Node with tests/_views.py (views/result.js,
doc-page.js, doc-leave-out.js, doc-reading.js, sources.js): where the screen and the focus are after a judgement, the
excerpts awaiting manual review, Judge it myself and "more…" only when there is more (0.19.8); Check against the corpus
on a working document's selection, Documents grouped by role (0.19.0); "N together" and the two-language box.
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
// ---- the result page ----------------------------------------------------------------------------------------
const LONG = "Repair cafés bring neighbours together. ".repeat(30) + "Volunteers fix toasters for free and teach others how. " + "The evenings end with coffee. ".repeat(30);
const PX = (o) => ({ passage_id: "p1", doc_id: "d1", title: "Repair report", text: "Volunteers fix toasters for free.", quote: "Volunteers fix toasters",
  quote_start: 0, quote_end: 23, verdict: "supports", ai_verdict: "supports", confidence: 0.9, counted: true, read_by: "claude-sonnet",
  in_corpus: true, page: 3, round: 1, found_by: "keywords", ...o });
const LONG_P = (o) => PX({ passage_id: "p2", title: "Long report", text: LONG, quote_start: LONG.indexOf("Volunteers"), quote_end: LONG.indexOf("Volunteers") + 23, ...o });
const WAITING = (o) => PX({ passage_id: "p3", title: "Interview notes", verdict: null, ai_verdict: null, counted: false, read_by: "you", waiting_for_you: true, confidence: null, ...o });
const RESULT = (passages, o = {}, part = {}) => ({ hyp_id: "h1", text: "Repair cafés build community", status: "supported", threshold: 0.6, options: {},
  decomposed: false, model: "claude-sonnet",
  parts: [{ claim_id: "c1", part: 1, claim: "Repair cafés build community", status: "supported", passages, rounds_info: [], model: "claude-sonnet", ...part }], ...o });
const H = "/api/projects/Study/hypotheses/h1";
// `result` is what GET …/hypotheses/h1 answers now (a function: it may change as the test goes on)
async function result(t, answer, settings = {}) {
  t.state({ settings: { threshold: 0.6, ...settings } });
  t.answer("GET /api/projects/Study/retractions", { by_doc: {} });
  t.answer("GET /api/projects/Study/sharing/check/h1", { shared: false });
  t.answer(/^GET \/api\/projects\/Study\/documents\/[^/]+\/file\?check=1$/, t.fail(404, "no file"));
  t.answer(`GET ${H}/unread`, { documents: [] });
  t.answer("GET /api/servers", { servers: [] });
  t.answer("GET /api/projects/Study/shared-folder", { folder: null });
  t.answer("GET /api/projects/Study/sync-poller", t.fail(404, "none"));
  t.answer("GET /api/local-status", { running: false, models: [] });
  t.answer(`GET ${H}?*`, typeof answer === "function" ? answer : () => answer);
  await t.render("views/result.js", "renderResult", ["h1"], {});
}
const card = (t, id) => t.view.querySelector(`[data-passage="${id}"]`);

await scenario("judged: the screen stays", async (t) => {
  let now = RESULT([PX(), LONG_P(), PX({ passage_id: "p4", title: "Third report" })]);
  await result(t, () => now);
  // where the cards are: the one judged sat at 300 px; moved into "not about this" it would be at 900 px
  // (its judging row 150 px below the card's top)
  const cardTop = (el) => (el.closest(".also-read") ? 900 : 300);
  t.layout((el) => (el.classList.contains("moved-ph") ? { top: 300, left: 0, width: 600, height: 40 }
    : el.classList.contains("ev") ? { top: cardTop(el), left: 0, width: 600, height: 200 }
    : el.classList.contains("judge") ? { top: cardTop(el) + 150, left: 0, width: 600, height: 30 } : null));
  t.answer("PUT /api/projects/Study/claims/c1/judgements/p1", (body) => {
    now = RESULT([PX({ verdict: null, user_verdict: "not_relevant", my_verdict: "not_relevant", changed: true, counted: false, reviewed: true }), LONG_P(), PX({ passage_id: "p4", title: "Third report" })]);
    return { moved: null };
  });
  const scrollsBefore = t.scrolls.length;
  await t.click("Not about this", { within: card(t, "p1") });
  const put = t.calls.find((c) => c.method === "PUT");
  const ph = t.view.querySelector(".moved-ph");
  const out = { put: put.body, focus: t.focused(), placeholder: ph ? t.text(ph) : null,
    scrolled: t.scrolls.slice(scrollsBefore).filter((s) => s.window), cardNote: t.text(card(t, "p1").querySelector(".ev-moved")) };
  const into = t.scrolls.length;
  await t.click("Show it", { within: ph });
  out.showIt = t.scrolls.slice(into).filter((s) => s.into);
  return out;
});

await scenario("awaiting manual review, chosen", async (t) => {
  await result(t, RESULT([PX(), WAITING({ by_choice: true, access: "local" })]));
  return { head: t.text(t.view.querySelector(".evidence-head:last-of-type, .evidence-head")), heads: t.view.querySelectorAll(".evidence-head").map((x) => t.text(x)),
    top: t.text(card(t, "p3").querySelector(".ev-top")) };
});

await scenario("awaiting manual review, no AI may read", async (t) => {
  await result(t, RESULT([PX(), WAITING({ by_choice: false, access: "none" }), WAITING({ passage_id: "p5", by_choice: false, access: "local" })]));
  return { heads: t.view.querySelectorAll(".evidence-head").map((x) => t.text(x)),
    tops: ["p3", "p5"].map((id) => t.text(card(t, id).querySelector(".ev-top"))) };
});

await scenario("judge it myself", async (t) => {
  let now = RESULT([PX(), PX({ passage_id: "p6", title: "Local notes", verdict: null, ai_verdict: null, counted: false, read_by: "waiting", waiting_local: true, confidence: null })],
    { waiting_local: 1 }, { waiting_local: 1 });
  await result(t, () => now, { restricted_model: "qwen3:8b" });
  const panel = t.view.querySelector(".wait-local");
  const before = { text: t.text(panel), buttons: t.buttons(panel) };
  t.answer(`POST ${H}/judge-local`, () => {
    now = RESULT([PX(), WAITING({ passage_id: "p6", title: "Local notes", by_choice: true, access: "local" })]);
    return { ok: true, n: 1 };
  });
  await t.click("Judge it myself", { within: panel });
  return { before, posts: t.calls.filter((c) => c.method === "POST").map((c) => [c.path, c.body]), toasts: t.toasts(),
    panelAfter: !!t.view.querySelector(".wait-local"), top: t.text(card(t, "p6").querySelector(".ev-top")) };
});

await scenario("more and less", async (t) => {
  await result(t, RESULT([PX(), LONG_P()]));
  const short = card(t, "p1"), long = card(t, "p2");
  const out = { shortMore: t.find(/^(More|Less) context$/, { within: short }) !== null, longFolded: t.text(long.querySelector(".passage")),
    shortDetails: t.allText(short.querySelector(".ev-more-panel")).includes("Open the whole document at this place") };
  await t.click("More context", { within: long });
  const again = card(t, "p2");
  out.longWhole = t.text(again.querySelector(".passage"));
  out.links = t.text(again).includes("Open the whole document at this place");
  out.focus = t.focused();
  await t.click("Less context", { within: again });
  out.folded = t.text(card(t, "p2").querySelector(".passage"));
  return out;
});

// ---- a document's page --------------------------------------------------------------------------------------
const DOC = "/api/projects/Study/documents/d1";
const PARA = "Repair cafés make repairing an everyday practice again. ";
async function docPage(t, role, long = false, more = {}, blockMore = {}) {
  const text = long ? PARA.repeat(20) : PARA;   // a paragraph of 1,120 characters, to select more than 1,000 of
  t.state({ settings: {} });
  t.answer(`GET ${DOC}?*`, { doc_id: "d1", title: "My draft", kind: "md", total_blocks: 2, ...more,
    blocks: [{ n: 0, kind: "heading", text: "Draft", start: 0, end: 5 }, { n: 1, kind: "paragraph", text, start: 6, end: 6 + text.length, ...blockMore }] });
  t.answer(/^GET \/api\/projects\/Study\/documents\/d1\/role/, { role });
  t.answer(`GET ${DOC}/nonscientific-suggestion`, { suggested: false });
  t.answer(`GET ${DOC}/notes`, { notes: [] });
  await t.render("views/doc-page.js", "renderDocument", ["d1"], {});
}
const textNode = (root, words) => { const walk = (n) => { for (const c of n.childNodes) { if (c instanceof Text && c.data.includes(words)) return c; const f = c.childNodes && walk(c); if (f) return f; } return null; }; return walk(root); };
async function selectAndLook(t, words, len) {
  const node = textNode(t.view, words);
  const at = node.data.indexOf(words);
  const said = t.select(node, at, at + len);
  node.parentNode.dispatchEvent(new Event("mouseup", { bubbles: true }));
  await t.settle(10);
  const bar = t.view.querySelector(".dv-selbar, [class*=selbar]");
  return { said, bar: bar && !t.hidden(bar) ? t.buttons(bar).map((b) => b.label) : null };
}
for (const [role, len] of [["working", 30], ["evidence", 30], ["working", 1000], ["working", 1010]]) {
  await scenario(`${len} characters selected in a ${role} document`, async (t) => {
    await docPage(t, role, len > 100);
    const r = await selectAndLook(t, "Repair cafés make", len);
    if (r.bar && r.bar.includes("Check against the corpus")) await t.click("Check against the corpus");
    return { ...r, length: r.said.trim().length, navs: t.navs };
  });
}

await scenario("leave out, together", async (t) => {
  await docPage(t, "evidence", false, {}, { together: 2 });
  const shown = (n) => t.view.querySelectorAll(`#block-${n} .dv-act button`).map((b) => [b.getAttribute("aria-label"), t.text(b)]);
  return { alone: shown(0), together: shown(1) };
});
await scenario("two languages", async (t) => {
  await docPage(t, "evidence", false, { reader: 6, languages: { two: ["en", "nl"], names: { en: "English", nl: "Dutch" }, shares: { en: 0.52, nl: 0.48 } } });
  t.answer(`PUT ${DOC}/language`, { keep: "en", left_out: 7, languages: { kept: "en" } });
  await t.click("Reading");
  const box = t.view.querySelector(".dv-languages");
  const before = t.text(box);
  await t.click("Keep only English", { within: box });
  return { before, put: t.calls.find((c) => c.method === "PUT"), after: t.text(t.view.querySelector(".dv-languages")), focus: t.focused(), toasts: t.toasts() };
});
await scenario("documents by role", async (t) => {
  t.state({ settings: {} });
  const D = (id, title) => ({ doc_id: id, title, file: `${id}.pdf`, kind: "pdf", ai_access: "cloud", added_at: "2026-11-01" });
  t.answer("GET /api/projects/Study", { search: null, passages: 30 });
  t.answer(/^GET \/api\/projects\/Study\/documents(\?.*)?$/, { documents: [D("d1", "Field notes"), D("d2", "Bourdieu, Distinction"), D("d3", "My chapter draft"), D("d4", "Survey report")] });
  t.answer(/^GET \/api\/projects\/Study\/document-roles/, { roles: { d2: "theory", d3: "working" }, nonscientific: [] });
  t.answer("GET /api/projects/Study/nonscientific-suggestions", { suggested: {} });
  t.answer("GET /api/projects/Study/map/documents?*", t.fail(404, "no answers yet"));
  await t.render("views/sources.js", "renderSources");
  await t.click("Role", { within: t.view.querySelector(".docs-group-by") });
  const groups = t.view.querySelectorAll(".doc-group").map((g) => ({ key: g.getAttribute("data-group"), text: t.text(g) }));
  return { groups, kept: localStorage.getItem("margin.docs-group:Study"), calls: t.calls.map((c) => `${c.method} ${c.path}`) };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("result"))


# ---- the result page -----------------------------------------------------------------------------------------
@needs_node
def test_a_judgement_is_saved_for_the_excerpt_with_the_strictness_shown(page):
    assert page["judged: the screen stays"]["put"] == {"verdict": "not_relevant", "note": "", "threshold": 0.6}


@needs_node
def test_after_a_judgement_moves_the_card_the_screen_stays_at_its_old_place(page):
    j = page["judged: the screen stays"]
    assert j["placeholder"] == "Moved to “not about this hypothesis” · Show it"
    assert [s["by"] for s in j["scrolled"] if "by" in s] == [[0, 0]]   # not the 600 px down to the card's new place
    assert j["cardNote"].startswith("Moved here, to the excerpts that are not about this: your judgement is now “Not about this”.")


@needs_node
def test_after_a_judgement_the_keyboard_goes_on_from_show_it(page):
    j = page["judged: the screen stays"]
    assert j["focus"]["label"] == "Show it"
    assert j["showIt"] == [{"into": {"tag": "article", "label": "Not about this: Repair report", "cls": j["showIt"][0]["into"]["cls"]},
                            "how": {"behavior": "smooth", "block": "center"}}]


@needs_node
def test_an_excerpt_you_chose_to_judge_says_awaiting_manual_review_and_why(page):
    a = page["awaiting manual review, chosen"]
    assert a["top"] == "Awaiting manual review you chose to judge it instead of the local model"
    assert any(h.startswith("Awaiting manual review: 1 excerpt\nYou chose to judge this one yourself rather than start the local model.")
               for h in a["heads"])


@needs_node
def test_an_excerpt_no_ai_may_read_says_awaiting_manual_review_with_its_documents_mark(page):
    a = page["awaiting manual review, no AI may read"]
    assert a["tops"] == ["Awaiting manual review its document is marked No AI",
                         "Awaiting manual review its document is marked Only a local AI, and no local model is chosen"]
    assert any(h.startswith("Awaiting manual review: 2 excerpts\nNo AI may read these") for h in a["heads"])


@needs_node
def test_judge_it_myself_comes_first_posts_to_judge_local_and_the_excerpt_then_waits_for_you(page):
    j = page["judge it myself"]
    labels = [b["label"] for b in j["before"]["buttons"]]
    assert labels[0] == "Judge it myself" and any(x.startswith("Start") for x in labels[1:])
    assert "It then waits for your judgement, marked Awaiting manual review" in j["before"]["text"]
    assert j["posts"] == [["/api/projects/Study/hypotheses/h1/judge-local", {}]]
    assert any("The excerpt waits for your judgement" in x for x in j["toasts"])
    assert j["panelAfter"] is False
    assert j["top"] == "Awaiting manual review you chose to judge it instead of the local model"


@needs_node
def test_more_shows_only_when_the_folded_card_leaves_text_out(page):
    m = page["more and less"]
    assert m["shortMore"] is False and m["shortDetails"] is True     # its ways into the document are under Details
    assert m["longFolded"].startswith("…") and m["longFolded"].endswith("more…")
    assert m["longWhole"].endswith("less") and m["longWhole"].count("Repair cafés bring neighbours together.") == 30
    assert m["links"] is True and m["focus"]["label"] == "Less context"
    assert m["folded"] == m["longFolded"]


# ---- a document's page ---------------------------------------------------------------------------------------
@needs_node
def test_a_selection_in_a_working_document_offers_check_against_the_corpus_and_goes_to_hypotheses(page):
    w = page["30 characters selected in a working document"]
    assert w["bar"][-1] == "Check against the corpus"
    assert w["navs"] == ["#/hypotheses?text=Repair%20caf%C3%A9s%20make%20repairing%20an&from=d1"]


@needs_node
def test_a_selection_in_an_evidence_document_does_not_offer_check_against_the_corpus(page):
    e = page["30 characters selected in a evidence document"]
    assert e["bar"] and "Highlight" in e["bar"] and "Check against the corpus" not in e["bar"]
    assert e["navs"] == []


@needs_node
def test_check_against_the_corpus_takes_a_selection_of_at_most_1000_characters(page):
    at = page["1000 characters selected in a working document"]
    assert at["length"] == 1000 and "Check against the corpus" in at["bar"]
    assert at["navs"][0].startswith("#/hypotheses?text=Repair") and at["navs"][0].endswith("&from=d1")
    over = page["1010 characters selected in a working document"]
    assert over["length"] > 1000 and "Highlight" in over["bar"] and "Check against the corpus" not in over["bar"]
    assert over["navs"] == []


@needs_node
def test_a_block_read_together_with_others_says_how_many_go_when_it_is_left_out(page):
    b = page["leave out, together"]
    assert b["together"] == [["Leave out 3 blocks: text", "Leave out 3 together"]]
    assert b["alone"] == [["Leave out: text", "Leave out"]]


@needs_node
def test_a_document_in_two_languages_offers_to_keep_one_and_says_which_counts(page):
    lang = page["two languages"]
    assert lang["before"].startswith("In two languages: English 52 %, Dutch 48 %.")
    assert lang["before"].endswith("Keep only English Keep only Dutch")
    assert lang["put"]["body"] == {"keep": "en"}
    assert lang["after"] == "Only the English counts: the Dutch is left out of searches, codes, themes and checks. Count both again"
    assert lang["focus"]["label"] == "Count both again"
    assert any("7 paragraphs left out" in x for x in lang["toasts"])


# ---- the Documents page --------------------------------------------------------------------------------------
@needs_node
def test_documents_grouped_by_role_show_evidence_theory_and_working_documents_apart(page):
    r = page["documents by role"]
    assert [(g["key"], g["text"].splitlines()[0]) for g in r["groups"]] == [
        ("evidence", "Evidence 2 documents"), ("theory", "Theory 1 document"), ("working", "Your working documents 1 document")]
    assert r["groups"][0]["text"].endswith("Field notes\nSurvey report")
    assert r["groups"][1]["text"].endswith("Bourdieu, Distinction") and r["groups"][2]["text"].endswith("My chapter draft")
    assert r["kept"] == "role"                                 # the choice is kept for the project
