"""A document's page opens with less on it (docs/DESIGN.md 4.12, 4.14, 4.17).

- The head says each thing once: the file's name and the work's name in the bibliography only when they say more than
  the title; the way to the original is the last of the facts, not a row of its own.
- The marks (theory, your working document, non-scientific) are rows of More at the head's right, so a document with
  no mark shows no row of mark buttons, and a notice holds one action: the one that takes its mark back.
- A menu is as wide as its longest row; the project switch keeps the sidebar's width.
- One item's actions stand on the back link's line, so its title has the head's whole width (4.14, changed with the
  owner's word on 2026-11-15); a narrow head still stacks: the back link, the title and its lines, the actions.
"""
from __future__ import annotations

import pytest

from _fakedom import NODE, STATIC, run
from _static import rule


def _js(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_a_name_that_only_repeats_the_title_is_left_out(tmp_path):
    out = run(f"""
const {{ repeatsTitle }} = await import({(STATIC / "views" / "doc-shared.js").as_uri()!r});
const t = "About Repair Café - Repairing for a Sustainable Future";
console.log(JSON.stringify([
  repeatsTitle("About Repair Café - Repairing for a Sustainable Future.html", t),
  repeatsTitle("about_repair_café__repairing_for_a_sustainable_future.HTML", t),
  repeatsTitle(t, t),
  repeatsTitle("paper_a.pdf", "Water footprint of electrolytic hydrogen"),
  repeatsTitle("Haddad and Okafor (2023)", "Water footprint of electrolytic hydrogen"),
  repeatsTitle("birds.html", "birds.html"),
  repeatsTitle("", t), repeatsTitle("anything", ""),
]));
""", tmp_path)
    assert out == [True, True, True, False, False, True, False, False]


def test_the_head_says_each_thing_once():
    js = _js("views/doc-page.js")
    assert "facts: [fileSaysMore ? d.file : null," in js and "const fileSaysMore = d.file && !repeatsTitle(d.file, title);" in js
    assert 'bibName && !repeatsTitle(bibName, title) ? [": ", h("strong", {}, bibName)] : null' in js
    # the way to the original is the last of the facts; the highlighted copy and More are the head's actions
    facts = js[js.index("facts: [fileSaysMore"):js.index("    meta: [")]
    assert facts.rstrip().endswith('"Open the original" })],') and 'class: "dv-orig"' in facts
    assert "actions: [renameBtn, copyBtn, " in js and ", moreSlot] }));" in js and "dv-head-row" not in js   # Margin adds Skim between
    assert "dv-head-row" not in _js("views.css")


def test_the_marks_are_rows_of_more_and_a_notice_holds_one_action():
    role = _js("views/doc-role.js")
    box = role[role.index("export async function roleBox"):]
    assert "items: [...roleMenuItems(project, doc, r.role, draw), nonsciMenuItem(project, doc, ns, draw)]" in box
    assert "label: `More for ${title}`" in box
    assert "doc-role-row" not in role
    assert box.count('h("div", { class: "btn-row" }, toEvidence)') == 2
    assert box.count('h("div", { class: "btn-row" }, toScientific)') == 1
    assert box.count('class: "btn-row"') == 3
    # with no answer from the server the box and the menu are both empty
    assert "box.replaceChildren(); if (more) more.replaceChildren(); return;" in box


def test_the_suggestion_sets_its_answers_apart():
    role = _js("views/doc-role.js")
    line = role[role.index("export function suggestLine"):role.index("export function suggestAgainLine")]
    assert 'h("span", { class: "btn-row" },' in line
    r = rule(".doc-nonsci-suggest")
    assert r["display"] == "flex" and r["flex-wrap"] == "wrap" and r["gap"] == "var(--space-2)"
    assert rule(".doc-role-box:empty")["display"] == "none"


def test_a_menu_is_as_wide_as_its_longest_row():
    r = rule(".menu > .menu-list")
    assert r["width"] == "max-content" and r["max-width"] == "min(340px, calc(100vw - 32px))"
    ps = rule(".project-switch .ps-menu")   # it fills the sidebar's width (docs/DESIGN.md 5.1)
    assert ps["width"] == "auto" and ps["max-width"] == "none" and ps["left"] == "0" and ps["right"] == "0"


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_one_items_actions_stand_on_the_back_links_line(tmp_path):
    out = run(r"""
const { pageHead, button } = await import(LIB);
const shape = (hd) => ({ cls: hd.className, parts: hd.children.map((c) => c.className.split(" ")[0]),
  main: hd.children.find((c) => c.className === "page-head-main").children.map((c) => c.tagName === "H1" ? "h1" : c.className.split(" ")[0]) });
const back = { href: "#/sources", text: "All documents" };
console.log(JSON.stringify({
  item: shape(pageHead("A long title", { back, display: true, facts: ["web page"], actions: [button({ sm: true }, "More")] })),
  two: shape(pageHead("T", { back: [{ href: "#/h/1", text: "Back to the result" }, back], class: "own", actions: [button({ sm: true }, "More")] })),
  noActions: shape(pageHead("A hypothesis", { back, display: true, facts: ["Checked today"] })),
  place: shape(pageHead("Hypotheses", { eyebrow: "Project", sub: "Check a hypothesis.", actions: [button({ sm: true }, "CSV")] })),
}));
""", tmp_path)
    # the back link's line is the head's own first part; the page's order stays: back link, title and lines, actions
    assert out["item"] == {"cls": "page-head page-head-item", "parts": ["eyebrow", "page-head-main", "page-head-actions"],
                           "main": ["h1", "page-facts"]}
    assert out["two"]["cls"] == "page-head page-head-item own" and out["two"]["parts"][0] == "eyebrow"
    # a head with no actions (a result), and a place's head, are as they were
    assert out["noActions"] == {"cls": "page-head", "parts": ["page-head-main"], "main": ["eyebrow", "h1", "page-facts"]}
    assert out["place"] == {"cls": "page-head", "parts": ["page-head-main", "page-head-actions"], "main": ["eyebrow", "h1", "page-sub"]}


def test_one_items_head_is_two_lines_wide_and_stacks_narrow():
    head = rule(".page-head-item")
    assert head["display"] == "grid" and head["grid-template-columns"] == "auto minmax(0, 1fr)"
    assert head["align-items"] == "last baseline"   # the back link on the line of the actions' words
    assert rule(".page-head-item > .eyebrow")["grid-row"] == "1"
    acts = rule(".page-head-item > .page-head-actions")
    assert acts["grid-row"] == "1" and acts["grid-column"] == "2" and acts["justify-content"] == "flex-end"
    assert rule(".page-head-item > .page-head-main")["grid-column"] == "1 / -1"
    narrow = "@container page-head (max-width: 699px)"
    stacked = rule(".page-head-item > .page-head-actions", media=narrow)
    assert stacked["grid-column"] == "1 / -1" and stacked["grid-row"] == "3" and stacked["justify-content"] == "flex-start"
    assert rule(".page-head-item > .eyebrow", media=narrow)["grid-column"] == "1 / -1"
    guide = (STATIC.parents[3] / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "**One item's actions stand on the back link's line**" in guide
