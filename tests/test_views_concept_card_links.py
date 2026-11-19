"""The concept card's links run in Node with tests/_views.py (D1 rest): the headings of links that need, are needed,
shape, are shaped and clash; the fourteen relations a person can pick; and a proposed link found in the text.
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const BASE = "/api/projects/Study";
const link = (id, label, relation, extra = {}) => ({ term_id: id, label, relation, source: "person", state: "confirmed", confidence: null,
  quote_a: null, quote_b: null, a: "t1", b: id, decision: null, this_term: "t1", ...extra });
const SENTENCES = [{ doc_id: "d1", title: "Repair report", page: 3, start: 10, end: 60, quote: "Repair needs spare parts to work." }];
function card(links) {
  return { term_id: "t1", label: "repair", mentions: 5, passages: 4, documents: [], wordings: [{ term_id: "t1", label: "repair", mentions: 5, documents: 1, joins: [] }],
    lines: [], related: { links, together: [] }, suggested_wordings: [], stale: false };
}
async function page(t, links) {
  t.answer(`GET ${BASE}/concepts/t1?*`, card(links));
  t.answer(`GET ${BASE}/sharing?*`, { items: [] });
  t.answer(`PUT ${BASE}/concepts/links`, {});
  await t.render("views/concepts.js", "renderConcept", ["t1"], {});
}
const headings = (t) => t.view.querySelectorAll(".ct-group").map((g) => ({ h: t.text(g.querySelector("h3")), help: t.text(g.querySelector("p")),
  rows: g.querySelectorAll("li.ct-link").map((li) => t.text(li.querySelector(".ct-link-name"))) }));

await scenario("the groups", async (t) => {
  await page(t, [link("t2", "spare parts", "needs"), link("t3", "volunteers", "needed_by"), link("t4", "culture", "shapes"),
    link("t5", "rules", "shaped_by"), link("t6", "waste", "clashes"), link("t7", "cafe", "related")]);
  return headings(t);
});

await scenario("the choices", async (t) => {
  await page(t, []);
  const sel = t.view.querySelector(".ct-add select");
  return sel.querySelectorAll("option").map((o) => ({ value: o.getAttribute("value"), text: t.allText(o) }));
});

await scenario("a proposed needs link", async (t) => {
  await page(t, [link("t2", "spare parts", "needs", { source: "pattern", state: "proposed", sentences: SENTENCES })]);
  const row = t.view.querySelector("li.ct-link");
  const out = { text: t.allText(row), buttons: t.buttons(row), folds: row.querySelectorAll("details").map((d) => t.text(d.querySelector("summary"))) };
  await t.click("Yes, right");
  out.puts = t.calls.filter((c) => c.method === "PUT").map((c) => ({ path: c.path, body: c.body }));
  return out;
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("concept_card_links"))


@needs_node
def test_the_five_new_kinds_of_link_have_their_headings_in_order(page):
    g = page["the groups"]
    by = {x["h"]: x for x in g}
    assert by["What it shapes"] == {"h": "What it shapes", "rows": ["culture"],
                                    "help": "The documents say this concept shapes or influences these."}
    assert by["What shapes it"]["rows"] == ["rules"] and by["What shapes it"]["help"] == \
        "The documents say these shape or influence this concept."
    assert by["What it needs"]["rows"] == ["spare parts"] and by["What it needs"]["help"] == \
        "The documents say this concept needs, requires or depends on these."
    assert by["What needs it"]["rows"] == ["volunteers"] and by["What needs it"]["help"] == \
        "The documents say these need, require or depend on this concept."
    assert by["What it clashes with"]["rows"] == ["waste"] and by["What it clashes with"]["help"] == \
        "The documents say this concept and these conflict or work against each other."
    order = [x["h"] for x in g]
    assert order == ["Related to it", "What it shapes", "What shapes it", "What it needs", "What needs it",
                     "What it clashes with"]


@needs_node
def test_a_link_yourself_offers_the_fourteen_relations_in_order(page):
    opts = page["the choices"]
    assert [o["text"] for o in opts] == [
        "is the same as", "is broader than (includes)", "is narrower than (is part of)", "is related to", "leads to",
        "is an effect of", "shapes", "is shaped by", "needs", "is needed by", "replaces", "is replaced by",
        "clashes with", "is different from"]
    assert [o["value"] for o in opts] == ["same", "broader", "narrower", "related", "effect", "effect_of", "shapes",
                                          "shaped_by", "needs", "needed_by", "replaces", "replaced_by", "clashes",
                                          "different"]


@needs_node
def test_a_proposed_needs_link_is_not_confirmed_folds_its_sentence_and_is_accepted(page):
    r = page["a proposed needs link"]
    assert "not confirmed" in r["text"] and "found in the text" in r["text"]
    assert "The sentence it was found in" in r["folds"]
    labels = [b["label"] for b in r["buttons"]]
    assert "Yes, right" in labels and "No" in labels
    assert r["puts"] == [{"path": "/api/projects/Study/concepts/links",
                          "body": {"a": "t1", "b": "t2", "decision": "accept"}}]
