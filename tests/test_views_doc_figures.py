"""A document's figures on its page, run in Node with tests/_views.py (0.19.3, reader 5; views/doc-page.js pictured,
shownFigure, leftFigure, figureThumb, figureGone): a figure shown as its picture where it stands, a figure left out
folded with a small picture of it, a picture that cannot be drawn folded as before, and earlier readers unchanged.
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const DOC = "/api/projects/Study/documents/d1";
const BLOCKS = [{ n: 0, kind: "paragraph", text: "Repair cafés open monthly.", start: 0, end: 26, page: 1, included: true },
  { n: 1, kind: "figure", text: "SALE 50%", box: [0.1, 0.1, 0.5, 0.4], page: 2, included: false },
  { n: 2, kind: "caption", text: "Figure 1: A repair café in Utrecht", start: 27, end: 61, page: 2, included: true },
  { n: 3, kind: "paragraph", text: "Volunteers fix toasters.", start: 62, end: 86, page: 2, included: true },
  { n: 4, kind: "figure", text: "", box: [0.1, 0.5, 0.5, 0.9], page: 2, included: false, hidden: true, changed: true }];
async function doc(t, more = {}) {
  t.state({ settings: {} });
  t.answer(`GET ${DOC}?*`, { doc_id: "d1", title: "Report", kind: "pdf", reader: 5, page_images: true, total_blocks: BLOCKS.length, blocks: BLOCKS, ...more });
  t.answer(`GET ${DOC}/file?check=1`, t.fail(404, "no file"));
  t.answer(/^GET \/api\/projects\/Study\/documents\/d1\/role/, { role: null });
  t.answer(`GET ${DOC}/nonscientific-suggestion`, { suggested: false });
  t.answer(`GET ${DOC}/notes`, { notes: [] });
  await t.render("views/doc-page.js", "renderDocument", ["d1"], {});
}
const pictures = (t) => t.view.querySelectorAll("img").map((i) => ({ src: i.getAttribute("src").replace(/&token=.*$/, ""), alt: i.getAttribute("alt"),
  where: i.closest("details") ? "folded" : "in the text" }));
const folds = (t) => t.view.querySelectorAll("details.dv-fold > summary").map((s) => t.text(s));

await scenario("reader 5", async (t) => {
  await doc(t);
  const fig = t.view.querySelector("figure.dv-figure");
  const out = { pictures: pictures(t), folds: folds(t), caption: t.text(fig.querySelector("figcaption")),
    figureActions: t.labels(fig), leaveOut: t.labels(t.view).filter((l) => l.startsWith("Leave out")) };
  await t.click("Words in the figure", { within: fig });
  out.words = t.text(fig.querySelector(".dv-figure-words"));
  await t.click(t.view.querySelector("details.dv-fold > summary"));
  out.inFold = t.labels(t.view.querySelector("details.dv-fold"));
  return out;
});

await scenario("a picture that cannot be drawn", async (t) => {
  await doc(t);
  const [shown, thumb] = t.view.querySelectorAll("img");
  shown.dispatchEvent(new Event("error", { bubbles: false }));
  thumb.dispatchEvent(new Event("error", { bubbles: false }));
  await t.settle();
  return { pictures: pictures(t), folds: folds(t), figures: t.view.querySelectorAll("figure").length };
});

await scenario("reader 4", async (t) => {
  await doc(t, { reader: 4 });
  return { pictures: pictures(t), folds: folds(t) };
});

await scenario("no page pictures", async (t) => {
  await doc(t, { page_images: false });
  return { pictures: pictures(t), folds: folds(t) };
});

await scenario("a figure without its place", async (t) => {
  await doc(t, { blocks: BLOCKS.map((b) => (b.n === 1 ? { ...b, box: null } : b)) });
  return { pictures: pictures(t), folds: folds(t) };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("doc_figures"))


@needs_node
def test_a_figure_shows_as_its_picture_where_it_stands_named_by_its_caption(page):
    p = page["reader 5"]
    assert p["pictures"][0] == {"src": "/api/projects/Study/documents/d1/figures/1.png?scale=1.5",
                                "alt": "Figure 1: A repair café in Utrecht", "where": "in the text"}
    assert p["caption"] == "Figure 1: A repair café in Utrecht"
    assert "Open the page" in p["figureActions"] and "Words in the figure" in p["figureActions"]
    assert "Leave out: figure, page 2" in p["leaveOut"]          # a shown figure can be left out like the text


@needs_node
def test_the_words_inside_a_figure_are_behind_a_small_fold(page):
    assert page["reader 5"]["words"] == "Words in the figure\nSALE 50%"


@needs_node
def test_a_figure_left_out_is_folded_with_a_small_picture_and_can_be_restored(page):
    p = page["reader 5"]
    assert p["pictures"][1] == {"src": "/api/projects/Study/documents/d1/figures/4.png?scale=1",
                                "alt": "Figure on page 2, left out", "where": "folded"}
    assert p["folds"] == ["Left out of the text: 1 figure"]        # a picture, not "text inside a figure"
    assert any(x.startswith("Restore") for x in p["inFold"])


@needs_node
def test_a_picture_that_cannot_be_drawn_is_folded_as_before_and_a_broken_thumbnail_goes(page):
    p = page["a picture that cannot be drawn"]
    assert p["pictures"] == []
    assert p["figures"] == 0
    assert p["folds"] == ["Left out of the text: 1 piece of text inside a figure", "Left out of the text: 1 figure"]


@needs_node
def test_an_earlier_reader_or_a_document_without_page_pictures_folds_figures_as_before(page):
    for name in ("reader 4", "no page pictures"):
        p = page[name]
        assert p["pictures"] == [], name
        assert p["folds"] == ["Left out of the text: 1 piece of text inside a figure",
                              "Left out of the text: 1 piece of text inside a figure"], name


@needs_node
def test_a_figure_without_its_place_on_the_page_is_folded(page):
    p = page["a figure without its place"]
    assert [x["src"].split("/")[-1] for x in p["pictures"]] == ["4.png?scale=1"]
    assert p["folds"][0] == "Left out of the text: 1 piece of text inside a figure"
