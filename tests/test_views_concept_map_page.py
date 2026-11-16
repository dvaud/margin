"""The concept map's page run in Node with tests/_views.py (0.19.0, D1; views/concept-map.js): the filters made once,
with a Code select only once a codebook is chosen; the legend of groups and links; the map as lists and a pair's
passages; and what the page says with no glossary, with nothing to draw and with few passages.
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const OPTIONS = { documents: [{ doc_id: "d1", title: "Repair report" }, { doc_id: "d2", title: "Interviews" }],
  themes: { run_id: "r1", themes: [{ theme_id: 1, name: "Community" }] },
  codebooks: [{ name: "sdg", title: "SDGs", codes: [{ code: "12.5", description: "Reduce waste" }, { code: "11.3", description: "" }] }], years: [2020, 2021] };
const MAP = { built: true, nodes: [
    { id: "a", label: "repair", passages: 20, group: 1, x: 0.2, y: 0.3 }, { id: "b", label: "community", passages: 12, group: 1, x: 0.5, y: 0.5 },
    { id: "c", label: "waste", passages: 8, group: 11, x: 0.8, y: 0.2 }, { id: "e", label: "landfill", passages: 4, group: 12, x: 0.9, y: 0.6 },
    { id: "d", label: "café", passages: 3, group: 0, x: 0.6, y: 0.9 }],
  edges: [{ a: "a", b: "b", together: 6, pmi: 1.5 }], links: [{ a: "a", b: "c", types: [{ relation: "effect", source: "model" }, { relation: "related", source: "person" }] }],
  groups: [{ group: 1, names: ["repair", "community"], size: 2 }, { group: 11, names: ["waste"], size: 1 }, { group: 12, names: ["landfill"], size: 1 }],
  passages: 120, concepts_in_scope: 40, links_off_map: 2 };
const EDGE = { a: { node: "a", label: "repair" }, b: { node: "b", label: "community" }, together: 6, pmi: 1.5, links: [],
  passages: [{ doc_id: "d1", title: "Repair report", text: "Repair brings the community together.", start: 40, page: 3 }] };
const BASE = "/api/projects/Study/concept-map";
async function page(t, map = MAP, query = {}) {
  t.answer(`GET ${BASE}/options`, OPTIONS);
  t.answer(`GET ${BASE}?*`, typeof map === "function" ? map : () => map);
  t.answer(`GET ${BASE}/edge?*`, EDGE);
  await t.render("views/concept-map.js", "renderConceptMap", [], query);
}
const maps = (t) => t.calls.filter((c) => c.path.startsWith(`${BASE}?`)).map((c) => c.path.slice(BASE.length + 1));
const fields = (t) => t.view.querySelectorAll(".cm-filters select").map((s) => labelOfField(t, s));
const labelOfField = (t, s) => { const l = s.closest("label") || s.parentNode; return t.text(l).split("\n")[0]; };

await scenario("the filters", async (t) => {
  await page(t);
  const before = fields(t);
  const docSel = t.view.querySelectorAll(".cm-filters select")[0];
  const cbSel = t.view.querySelectorAll(".cm-filters select")[2];
  await t.type(cbSel, "sdg");
  const withCodebook = fields(t);
  const codeSel = t.view.querySelectorAll(".cm-filters select")[3];
  const codes = codeSel.querySelectorAll("option").map((o) => t.allText(o));
  await t.type(codeSel, "12.5");
  await t.type(docSel, "d2");
  const same = t.view.querySelectorAll(".cm-filters select")[0] === docSel && t.view.querySelectorAll(".cm-filters select")[2] === cbSel;
  await t.type(cbSel, "");
  return { before, withCodebook, codes, same, after: fields(t), maps: maps(t) };
});

await scenario("a link from another project", async (t) => {
  await page(t, MAP, { doc: "zz", framework: "nope", code: "1.1", theme: "r9:4", year_from: "2020" });
  return maps(t);
});

await scenario("the legend", async (t) => {
  await page(t);
  return { facts: t.text(t.view.querySelector(".cm-facts")), keys: t.view.querySelectorAll(".cm-key").map((k) => t.text(k)),
    how: t.text(t.view.querySelector(".cm-how")),
    marks: t.view.querySelectorAll("a.cm-node").map((a) => a.getAttribute("aria-label")) };
});

await scenario("the map as lists", async (t) => {
  await page(t);
  await t.click("The map as lists");
  const fold = t.view.querySelector("details.section");
  const out = { groups: fold.querySelectorAll(".cm-groups tbody tr").map((r) => t.text(r)),
    pairs: fold.querySelectorAll(".cm-pairs tbody tr").map((r) => t.text(r)),
    links: fold.querySelectorAll(".cm-link-list li").map((r) => t.text(r)) };
  await t.click("Show the passages", { within: fold.querySelector(".cm-pairs") });
  out.asked = t.calls.filter((c) => c.path.startsWith(`${BASE}/edge`)).map((c) => c.path);
  out.detail = t.text(t.view.querySelector(".cm-detail"));
  return out;
});

await scenario("no glossary", async (t) => {
  await page(t, { built: false, nodes: [], edges: [], links: [], groups: [] });
  return { text: t.text(t.view.querySelector(".cm-map")), filters: t.hidden(t.view.querySelector(".cm-filters")) };
});

await scenario("nothing to draw", async (t) => {
  await page(t, (_b, path) => ({ built: true, nodes: [], edges: [], links: [], groups: [], passages: 0, concepts_in_scope: 0 }));
  const plain = t.text(t.view.querySelector(".cm-map"));
  await t.type(t.view.querySelectorAll(".cm-filters select")[0], "d1");
  return { plain, filtered: t.text(t.view.querySelector(".cm-map")) };
});

await scenario("few passages, no lines", async (t) => {
  await page(t, { ...MAP, passages: 12 });
  const few = t.view.querySelectorAll(".cm-note").map((n) => t.text(n));
  return { few };
});

await scenario("no lines at all", async (t) => {
  await page(t, { ...MAP, edges: [], links: [], nodes: MAP.nodes.slice(0, 2) });
  return { notes: t.view.querySelectorAll(".cm-note").map((n) => t.text(n)), facts: t.text(t.view.querySelector(".cm-facts")) };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("concept_map"))


@needs_node
def test_the_filters_offer_a_code_only_once_a_codebook_is_chosen(page):
    f = page["the filters"]
    assert f["before"] == ["Documents", "Theme", "Codebook", "Published from", "Published until", "Concepts on the map"]
    assert f["withCodebook"] == ["Documents", "Theme", "Codebook", "Code", "Published from", "Published until", "Concepts on the map"]
    assert f["codes"] == ["Choose a code", "12.5 Reduce waste", "11.3"]
    assert f["after"] == f["before"]                            # no codebook: no Code


@needs_node
def test_each_choice_counts_the_map_again_with_the_filters_and_keeps_the_controls(page):
    f = page["the filters"]
    assert f["maps"] == ["", "framework=sdg", "framework=sdg&code=12.5", "doc=d2&framework=sdg&code=12.5", "doc=d2"]
    assert f["same"] is True                                    # the selects were not made again


@needs_node
def test_filters_of_a_link_from_another_project_are_dropped(page):
    assert page["a link from another project"] == ["year_from=2020"]


@needs_node
def test_the_facts_say_how_many_concepts_of_how_many_and_the_links_off_the_map(page):
    assert page["the legend"]["facts"] == ("The 5 of 40 concepts mentioned in the most passages, counted in 120 passages. "
                                           "Theory and working documents are left out. 2 links of the glossary join a "
                                           "concept on the map to one that is not on it.")


@needs_node
def test_the_legend_names_each_own_group_then_the_smallest_together_then_no_group(page):
    keys = page["the legend"]["keys"]
    assert keys == ["Group 1 (filled circle) repair, community",
                    "Groups 11 to 12 (grey star) the 2 smallest groups, drawn alike: the lists below say which concepts each holds",
                    "In no group (grey dashed circle)"]
    assert "(leads to, is related to)" in page["the legend"]["how"]


@needs_node
def test_each_concept_on_the_map_is_a_link_that_says_its_passages_group_and_joins(page):
    assert page["the legend"]["marks"] == ["repair: 20 passages, group 1, joined to 2 concepts",
                                           "community: 12 passages, group 1, joined to 1 concept",
                                           "waste: 8 passages, group 11, joined to 1 concept",
                                           "landfill: 4 passages, group 12", "café: 3 passages, in no group"]


@needs_node
def test_the_map_as_lists_gives_the_groups_the_pairs_and_the_links(page):
    p = page["the map as lists"]
    # the mark of each group in words (read out; the picture shows the mark)
    assert p["groups"] == ["Group 1 (filled circle)\nrepair 20 , community 12",
                           "Group 11 (grey star, as every group from 11 on)\nwaste 8",
                           "Group 12 (grey star, as every group from 11 on)\nlandfill 4",
                           "In no group (grey dashed circle)\ncafé 3"]
    assert p["pairs"] == ["repair and community\n6\n2.8\nShow the passages"]
    assert p["links"] == ["repair leads to waste · judged by the AI ; repair is related to waste · added or accepted by you Show the passages"]


@needs_node
def test_show_the_passages_opens_what_joins_a_pair(page):
    p = page["the map as lists"]
    assert p["asked"] == ["/api/projects/Study/concept-map/edge?a=a&b=b"]
    assert p["detail"].startswith("repair and community\nMentioned together in 6 passages, 2.8 times as often as by chance.")
    assert "“Repair brings the community together.” Repair report, p. 3" in p["detail"]


@needs_node
def test_without_a_glossary_the_page_points_to_it_and_hides_the_filters(page):
    p = page["no glossary"]
    assert p["text"].startswith("No glossary yet")
    assert "Make the glossary on the Glossary tab" in p["text"]
    assert p["filters"] is True


@needs_node
def test_nothing_to_draw_says_whether_fewer_filters_would_help(page):
    p = page["nothing to draw"]
    assert p["plain"] == "Nothing to draw\nNo concept of the glossary is mentioned in two passages or more."
    assert p["filtered"] == ("Nothing to draw\nNo concept is mentioned in two passages or more within these filters. "
                             "Choose fewer filters.")


@needs_node
def test_few_passages_are_said_to_be_little_to_rest_lines_on(page):
    assert page["few passages, no lines"]["few"] == [
        "Only 12 passages are counted, so the lines rest on very little: two concepts that share two or three of them can "
        "look strongly joined by chance."]


@needs_node
def test_no_lines_at_all_is_said(page):
    p = page["no lines at all"]
    assert p["notes"] == ["No two of these concepts are mentioned together often enough to be joined (in two passages or "
                          "more, more often than by chance)."]
    assert p["facts"].startswith("The 2 of 40 concepts")
