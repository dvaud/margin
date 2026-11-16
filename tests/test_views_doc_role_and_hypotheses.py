"""A document's role and a hypothesis from a working document, run in Node with tests/_views.py (0.19.0): the role
box with its notice, the More menu of the three roles and its dialogs, the bibliography's suggestion with Mark, No and
Suggest again (views/doc-role.js); and on the Hypotheses page, the words of a working document that say where the
check will be listed, untied by a list, an emptied box or a check, and the note when the document is gone
(views/hypotheses.js).
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
// ---- the role box (views/doc-role.js) -----------------------------------------------------------------------
const ROLE = "/api/projects/Study/documents/d1/role";
const SUGGEST = "/api/projects/Study/documents/d1/nonscientific-suggestion";
async function box(t, role, suggestion = () => ({ suggestion: null })) {
  t.answer(`GET ${ROLE}`, typeof role === "function" ? role : () => role);
  t.answer(`GET ${SUGGEST}`, suggestion);
  const m = await t.module("views/doc-role.js");
  const more = document.createElement("div");
  const roles = [];
  const b = await m.roleBox("Study", "d1", "Field notes", (r) => roles.push(r), more);
  document.getElementById("view").append(more, b);
  await t.settle();
  return { b, more, roles, m };
}
const menuItems = async (t, more) => { await t.click(more.querySelector("summary")); return more.querySelectorAll("[role=menuitem]").map((x) => t.text(x)); };

await scenario("evidence, with the bibliography's suggestion", async (t) => {
  let answered = null;
  t.answer(`POST ${SUGGEST}`, (body) => { answered = body.answer; return {}; });
  const { b, more, roles } = await box(t, { role: null, impact: {} },
    () => (answered === "no" ? { suggestion: null, answered_no: { may_suggest_again: true, by: ["you"] } } : { suggestion: { words: "a newspaper article" } }));
  const out = { roles: [...roles], text: t.text(b), buttons: t.buttons(b).map((x) => x.label), items: await menuItems(t, more) };
  await t.click("No", { within: b });
  out.afterNo = { text: t.text(b), toasts: t.toasts(), buttons: t.buttons(b).map((x) => x.label) };
  await t.click("Suggest again", { within: b });
  out.afterAgain = { text: t.text(b), posts: t.calls.filter((c) => c.method === "POST").map((c) => c.body) };
  return out;
});

await scenario("the suggestion's Mark", async (t) => {
  t.answer(`PUT /api/projects/Study/documents/d1/nonscientific`, { answers: [{ hyp_id: "h1" }] });
  const { b } = await box(t, { role: null, impact: { checks: [{ hyp_id: "h1", text: "x", excerpts: 2 }] } }, () => ({ suggestion: { words: "a blog post" } }));
  await t.click("Mark", { within: b });
  const d = t.dialog();
  const out = { title: t.text(d.querySelector("h2")), says: t.text(d.querySelector(".dialog-body")) };
  await t.click("Mark as non-scientific", { within: d });
  out.puts = t.calls.filter((c) => c.method === "PUT").map((c) => [c.path, c.body]);
  out.toasts = t.toasts();
  return out;
});

await scenario("theory, back to evidence", async (t) => {
  let role = "theory";
  t.answer(`PUT ${ROLE}`, (body) => { role = body.role; return { role }; });
  const { b, more, roles } = await box(t, () => ({ role, impact: role ? { themes: [{ passages: 12 }], checks: [{ hyp_id: "h1", text: "Repair cafés build community", excerpts: 3 }] } : {} }));
  const out = { text: t.text(b), items: await menuItems(t, more) };
  await t.click("Mark as evidence", { within: b });
  const d = t.dialog();
  out.asked = t.text(d.querySelector("h2"));
  out.says = t.text(d.querySelector(".dialog-body"));
  await t.click("Mark as evidence", { within: d.querySelector(".dialog-actions") });
  out.puts = t.calls.filter((c) => c.method === "PUT").map((c) => c.body);
  out.toasts = t.toasts();
  out.after = t.text(b);
  out.roles = roles;
  out.itemsAfter = await menuItems(t, more);
  return out;
});

await scenario("working, with its checks", async (t) => {
  const started = Array.from({ length: 10 }, (_, i) => ({ hyp_id: `h${i}`, text: `Claim ${i + 1}`, status: "supported", status_text: "Supported" }));
  const { b, more, roles } = await box(t, { role: "working", impact: {}, started });
  return { roles, text: t.text(b), shown: b.querySelectorAll(".doc-started li").filter((x) => !t.hidden(x)).length,
    items: await menuItems(t, more) };
});

await scenario("a role from the menu, then cancelled", async (t) => {
  const { more } = await box(t, { role: null, impact: {} });
  await menuItems(t, more);
  await t.click("Mark as my working document…");
  const d = t.dialog();
  const out = { asked: t.text(d.querySelector("h2")), says: t.text(d.querySelector(".dialog-body")) };
  await t.click("Cancel", { within: d });
  out.puts = t.calls.filter((c) => c.method === "PUT").length;
  return out;
});

await scenario("the role's words", async (t) => {
  const m = await t.module("views/doc-role.js");
  const tagOf = (r) => { const x = m.roleTag(r); return x ? [t.allText(x), x.getAttribute("title")] : null; };
  return { lines: [m.roleLine("theory"), m.roleLine("working"), m.roleLine(null), m.roleLine("evidence")],
    tags: [tagOf("theory"), tagOf("working"), tagOf(null), tagOf("evidence")],
    menus: [null, "theory", "working"].map((r) => m.roleMenuItems("Study", { doc_id: "d1", title: "Field notes" }, r, null).map((x) => x.text)) };
});

// ---- the Hypotheses page, words from a working document (views/hypotheses.js) --------------------------------
const WORDS = "Repair cafés build community among neighbours";
async function hyp(t, docs, o = {}) {
  t.state({ settings: { backend: "claude_code", threshold: 0.6 } });
  t.answer("GET /api/projects/Study", { frameworks: [], passages: 40 });
  t.answer("GET /api/projects/Study/documents", { documents: docs });
  t.answer("GET /api/projects/Study/hypotheses?*", { hypotheses: [] });
  t.answer("POST /api/projects/Study/hypotheses/similar", {});
  t.answer("POST /api/projects/Study/checks", o.check || { job: { id: "j1" } });
  t.answer("GET /api/jobs/j1", { id: "j1", state: "running", progress: {} });
  await t.render("views/hypotheses.js", "renderHypotheses", [], { text: WORDS, from: "d1" });
  await t.settle(1000);
}
const note = (t) => { const n = t.view.querySelector(".hyp-from-note"); return t.hidden(n) ? null : t.text(n); };
const checks = (t) => t.calls.filter((c) => c.method === "POST" && c.path.endsWith("/checks")).map((c) => c.body.from_doc ?? null);

await scenario("from a working document", async (t) => {
  await hyp(t, [{ doc_id: "d1", title: "My draft", ai_access: "local" }]);
  return note(t);
});

await scenario("from a document no AI reads", async (t) => {
  await hyp(t, [{ doc_id: "d1", file: "draft.docx", ai_access: "none" }]);
  return note(t);
});

await scenario("checked from the document", async (t) => {
  await hyp(t, [{ doc_id: "d1", title: "My draft", ai_access: "cloud" }]);
  const before = note(t);
  await t.click("Check");
  return { before, sent: checks(t), after: note(t) };
});

await scenario("the document is gone", async (t) => {
  await hyp(t, [{ doc_id: "d1", title: "My draft", ai_access: "cloud" }], { check: t.fail(400, "Unknown from_doc: d1") });
  await t.click("Check");
  const lost = note(t);
  await t.click("Check");
  return { lost, sent: checks(t), toasts: t.toasts() };
});

await scenario("a second line unties it", async (t) => {
  await hyp(t, [{ doc_id: "d1", title: "My draft", ai_access: "cloud" }]);
  t.answer("POST /api/projects/Study/batches/preview", { items: [{ text: WORDS }, { text: "Volunteers learn to repair" }] });
  await t.type("Your hypothesis", WORDS + "\nVolunteers learn to repair things");
  await t.settle(1000);
  const list = note(t);
  await t.type("Your hypotheses", WORDS);
  await t.settle(1000);
  return { list, single: note(t) };
});

await scenario("an emptied box unties it", async (t) => {
  await hyp(t, [{ doc_id: "d1", title: "My draft", ai_access: "cloud" }]);
  await t.type("Your hypothesis", "");
  await t.settle(500);
  const emptied = note(t);
  await t.type("Your hypothesis", WORDS);
  await t.settle(1000);
  return { emptied, retyped: note(t) };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("doc_role"))


# ---- the role box --------------------------------------------------------------------------------------------
@needs_node
def test_an_evidence_document_shows_no_notice_and_its_menu_offers_the_other_two_roles_and_non_scientific(page):
    p = page["evidence, with the bibliography's suggestion"]
    assert p["roles"] == [None]
    assert p["items"] == ["Mark as theory…", "Mark as my working document…", "Mark as non-scientific…"]


@needs_node
def test_the_bibliographys_suggestion_is_one_line_with_mark_and_no(page):
    p = page["evidence, with the bibliography's suggestion"]
    assert p["text"] == "Your bibliography lists this as a newspaper article. Mark it as non-scientific? Mark No"
    assert p["buttons"] == ["Mark", "No"]


@needs_node
def test_no_is_kept_and_can_be_taken_back_with_suggest_again(page):
    p = page["evidence, with the bibliography's suggestion"]
    assert any("Kept as scientific. It will not be suggested again." in x for x in p["afterNo"]["toasts"])
    assert p["afterNo"]["text"] == "You said No to the bibliography's suggestion to mark it as non-scientific. Suggest again"
    assert p["afterNo"]["buttons"] == ["Suggest again"]
    assert p["afterAgain"]["posts"] == [{"answer": "no"}, {"answer": "again"}]
    assert p["afterAgain"]["text"].startswith("Your bibliography lists this as a newspaper article.")


@needs_node
def test_the_suggestions_mark_asks_with_the_checks_it_changes_then_marks(page):
    p = page["the suggestion's Mark"]
    assert p["title"] == "Mark as non-scientific?"
    assert "Answers change at once: 1 check read an excerpt of it." in p["says"]
    assert p["puts"] == [["/api/projects/Study/documents/d1/nonscientific", {"nonscientific": True}]]
    assert any("Marked as non-scientific. 1 answer changed" in x for x in p["toasts"])


@needs_node
def test_a_theory_document_says_what_it_is_left_out_of_and_what_was_made_with_it(page):
    p = page["theory, back to evidence"]
    assert "The lens the research is read through, not evidence." in p["text"]
    assert "1 set of themes (12 passages of it in them). Make the themes again" in p["text"]
    assert "Repair cafés build community · 3 excerpts from it." in p["text"]
    assert p["items"] == ["Mark as evidence…", "Mark as my working document…", "Mark as non-scientific…"]


@needs_node
def test_marking_a_theory_document_as_evidence_asks_then_takes_the_mark_back(page):
    p = page["theory, back to evidence"]
    assert p["asked"] == "Mark as evidence again?"
    assert "“Field notes” then counts as evidence again" in p["says"]
    assert p["puts"] == [{"role": None}]
    assert any("Marked as evidence." in x for x in p["toasts"])
    assert p["after"] == ""                                     # no notice left
    assert p["roles"] == ["theory", None]                       # the page is told each time
    assert p["itemsAfter"] == ["Mark as theory…", "Mark as my working document…", "Mark as non-scientific…"]


@needs_node
def test_a_working_document_lists_the_newest_eight_checks_started_from_it_and_folds_the_rest(page):
    p = page["working, with its checks"]
    assert p["roles"] == ["working"]
    assert "select the sentence in the text and choose Check against the corpus" in p["text"]
    assert "The 10 checks started from it:" in p["text"]
    assert "Claim 1 · Supported" in p["text"] and "Claim 9" not in p["text"]
    assert "and 2 more checks" in p["text"]
    assert p["shown"] == 8
    assert p["items"] == ["Mark as evidence…", "Mark as theory…", "Mark as non-scientific…"]


@needs_node
def test_marking_as_a_working_document_asks_what_it_means_and_cancel_changes_nothing(page):
    p = page["a role from the menu, then cancelled"]
    assert p["asked"] == "Mark as your working document?"
    assert "“Field notes” is then your own draft or notes, never a source." in p["says"]
    assert "A colleague’s or another author’s draft you study is evidence" in p["says"]
    assert p["puts"] == 0


@needs_node
def test_each_role_has_its_line_tag_and_menu(page):
    p = page["the role's words"]
    assert p["lines"] == ["Theory: the lens the research is read through, not evidence",
                          "Working document: your own draft or notes, never a source", "Evidence", "Evidence"]
    assert p["tags"][0][0] == "Theory" and p["tags"][1][0] == "Working document"
    assert p["tags"][1][1].startswith("Working document: your own draft or notes")
    assert p["tags"][2] is None and p["tags"][3] is None        # evidence carries no tag
    assert p["menus"] == [["Mark as theory…", "Mark as my working document…"],
                          ["Mark as evidence…", "Mark as my working document…"],
                          ["Mark as evidence…", "Mark as theory…"]]


# ---- the Hypotheses page -------------------------------------------------------------------------------------
@needs_node
def test_words_from_a_working_document_say_where_the_check_is_listed_and_who_reads_them(page):
    assert page["from a working document"] == ("The check will be listed on the page of My draft. It is marked Only a local "
                                               "AI, so only a local model on this computer reads these words and the "
                                               "excerpts they are checked against; without one, you judge the excerpts yourself.")
    assert page["from a document no AI reads"].startswith("The check will be listed on the page of draft.docx. It is marked No AI")


@needs_node
def test_the_check_of_a_documents_words_carries_the_document_and_then_unties_the_box(page):
    p = page["checked from the document"]
    assert p["before"].startswith("The check will be listed on the page of My draft.")
    assert p["sent"] == ["d1"]
    assert p["after"] is None


@needs_node
def test_when_the_document_is_gone_the_page_says_so_and_the_next_check_is_any_hypothesis(page):
    p = page["the document is gone"]
    assert p["lost"] == ("The document these words came from is no longer in this project, so nothing was started. Start again "
                         "to check them as any hypothesis you type; the check will not be listed on a document's page.")
    assert p["toasts"] == []                                    # said in the page, not as an error
    assert p["sent"] == ["d1", None]


@needs_node
def test_a_list_unties_the_words_from_the_document_for_good(page):
    p = page["a second line unties it"]
    assert p["list"] is None and p["single"] is None


@needs_node
def test_an_emptied_box_is_a_new_hypothesis_not_the_documents_words(page):
    p = page["an emptied box unties it"]
    assert p["emptied"] is None and p["retyped"] is None
