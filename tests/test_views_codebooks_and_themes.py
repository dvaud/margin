"""Codebooks and themes run in Node with tests/_views.py: an AI-drafted definition and where its words were read, a
waiting framework draft, the editor's AI-draft line (0.19.2), and themes the AI could not name (0.19.6).
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
// ---- the Codebooks list ------------------------------------------------------------------------------------
const CB = "/api/projects/Study/codebooks";
const LIST = { codebooks: [{ name: "sdg", title: "SDG targets", where: "bundled", codes: 169, label: "target" },
  { name: "repair", title: "Repair", where: "project", codes: 4, label: "code" }], problems: [] };
for (const waiting of [true, false]) {
  await scenario(`codebooks list, draft ${waiting}`, async (t) => {
    t.answer(`GET ${CB}`, LIST);
    t.answer("GET /api/projects/Study/codebook-theory/draft", { draft: waiting ? { title: "Repair theory", concepts: [{ keep: true }, { keep: false }, { keep: true }] } : null });
    await t.render("views/codebooks.js", "renderCodebooks");
    const n = t.view.querySelector(".cb-draft-notice");
    return { notice: n ? t.text(n) : null, link: n ? n.querySelector("a").getAttribute("href") : null };
  });
}

// ---- the codebook editor -----------------------------------------------------------------------------------
const CODE = (o) => ({ uid: "u1", code: "Mending", description: "Fixing things together", group: "1", include: "", exclude: "", keywords: ["mend"],
  examples: [{ quote: "we mend chairs", doc_id: "d1", start: 1 }, { quote: "mending is social", doc_id: "d2", start: 5 }], ...o });
async function editor(t, codes) {
  t.state({ settings: { backend: "claude_code" } });
  t.answer(`GET ${CB}/repair`, { codebook: { name: "repair", title: "Repair", label: "code", where: "project", editable: true, directional: false,
    used: { labels: 0, checks: 0 }, groups: [{ group: "1", group_name: "Practice" }], codes } });
  t.answer("GET /api/projects/Study/codebooks/repair/offer", { offer: null });
  t.answer("GET /api/projects/Study/sharing/codebook/repair", { shared: false });
  t.answer("GET /api/projects/Study/shared-folder", { folder: null });          // the sharing bar asks for the team
  t.answer("GET /api/projects/Study/sync-poller", t.fail(404, "none"));
  await t.render("views/codebooks.js", "renderCodebook", ["repair"]);
}
await scenario("editor head, AI draft", async (t) => {
  await editor(t, [CODE({ description: "Fixing things together", ai_draft: { description: "Fixing things together", model: "claude-sonnet" } }), CODE({ uid: "u2", code: "Sharing", description: "mine" })]);
  const note = t.view.querySelector(".cb-dl-note");
  const h1 = t.view.querySelector("h1");
  return { note: t.hidden(note) ? null : t.text(note), inHead: !!note.closest(".page-head"),
    afterTitle: t.text(t.view.querySelector(".page-head")).split("\n").indexOf(t.text(note)) > t.text(t.view.querySelector(".page-head")).split("\n").indexOf("Repair") };
});
await scenario("editor head, own words", async (t) => {
  await editor(t, [CODE({ ai_draft: { description: "Something the AI said", model: "claude-sonnet" } })]);
  return t.hidden(t.view.querySelector(".cb-dl-note"));
});
for (const reader of ["local", "claude"]) {
  await scenario(`definition drafted by ${reader}`, async (t) => {
    await editor(t, [CODE({ description: "" })]);
    t.answer(`POST ${CB}/repair/define/offer`, { offered: true, passages: 2, reader });
    t.answer(`POST ${CB}/repair/define`, { job: { id: "jd" } });
    t.answer("GET /api/jobs/jd", { id: "jd", state: "done", result: { ok: true, reader, draft: { description: "Repairing objects as a group", model: reader === "local" ? "qwen3:8b" : "claude-sonnet" } } });
    await t.click(/^Mending/);
    const line = t.text(t.view.querySelector(".cb-define"));
    await t.click("Draft from the examples");
    const panel = t.view.querySelector(".cb-draft");
    return { line, panel: t.text(panel), sent: t.calls.find((c) => c.path.endsWith("/define")).body };
  });
}

// ---- themes the AI could not name ---------------------------------------------------------------------------
const TH = "/api/projects/Study/themes";
async function themes(t, list, readers) {
  t.state({ settings: { backend: "claude_code" } });
  t.answer(`GET ${TH}`, { runs: [{ run_id: "r1" }], frameworks: [] });
  t.answer("GET /api/projects/Study/outlines", { outlines: [] });   // Margin: the Outline button looks for one made from these themes
  t.answer(`GET ${TH}/r1?*`, { run: { run_id: "r1", created_at: "2026-11-15T10:00:00Z", passages: 40, mode: "meaning" }, documents: [{ doc_id: "d1" }], themes: list, removed: [], readers });
  t.answer("GET /api/projects/Study/frameworks", { frameworks: [] });
  t.answer("GET /api/projects/Study/sharing/themes/r1", { shared: false });
  t.answer("GET /api/projects/Study/shared-folder", { folder: null });
  t.answer("GET /api/projects/Study/sync-poller", t.fail(404, "none"));
  await t.render("views/themes.js", "renderThemes", [], {});
}
const THEME = (o) => ({ theme_id: 1, name: "repair · tools", name_source: "terms", size: 10, terms: ["repair", "tools"], passages: [], docs: 1, ...o });
await scenario("themes not named, one reason", async (t) => {
  await themes(t, [THEME({ naming_failed: { reason: "the model answered with no name", model: "qwen3:8b" } }),
    THEME({ theme_id: 2, naming_failed: { reason: "the model answered with no name", model: "qwen3:8b" } }), THEME({ theme_id: 3, name: "Cafés", name_source: "model" })]);
  t.answer(`POST ${TH}/r1/name`, { job: { id: "jn" } });
  t.answer("GET /api/jobs/jn", { id: "jn", state: "running", progress: {} });
  const n = t.view.querySelector(".th-not-named-notice");
  const out = { notice: t.text(n), local: !!n.querySelector(".icon-house") };
  await t.click("Name them again", { within: n });
  out.posts = t.calls.filter((c) => c.method === "POST").map((c) => c.path);
  return out;
});
await scenario("themes not named, several reasons", async (t) => {
  await themes(t, [THEME({ naming_failed: { reason: "no answer", model: "claude-haiku" } }), THEME({ theme_id: 2, naming_failed: { reason: "a quote not in the passage", model: "claude-haiku" } })]);
  return t.text(t.view.querySelector(".th-not-named-notice"));
});
await scenario("themes all named", async (t) => {
  await themes(t, [THEME({ name: "Cafés", name_source: "model" })]);
  return t.view.querySelector(".th-not-named-notice") === null;
});
// 0.20.1: the head's AI line says who names the themes, as their documents allow
const READERS = { claude: { main: 3, local: 0, none: 0, local_model: "qwen3.5:4b" },
  local: { main: 0, local: 3, none: 0, local_model: "qwen3.5:4b" },
  both: { main: 2, local: 1, none: 1, local_model: "qwen3.5:4b" },
  nobody: { main: 0, local: 0, none: 3, local_model: null }, absent: undefined };
for (const [k, rd] of Object.entries(READERS)) {
  await scenario(`themes ai line, ${k}`, async (t) => {
    await themes(t, [THEME({ name: "Cafés", name_source: "model" })], rd);
    const line = t.view.querySelector(".page-head .ai-where");
    return { line: t.text(line), local: !!line.querySelector(".icon-house") };
  });
}
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("codebooks"))


@needs_node
def test_the_codebooks_list_says_when_a_framework_draft_is_waiting(page):
    w = page["codebooks list, draft true"]
    assert w["notice"].startswith("A codebook from theory is being drafted: “Repair theory”, 2 concepts in the codebook.")
    assert "Continue the draft" in w["notice"] and w["link"] == "#/codebooks/draft/theory"
    assert page["codebooks list, draft false"]["notice"] is None


@needs_node
def test_the_editors_head_says_under_the_title_that_codes_still_hold_the_ai_draft(page):
    e = page["editor head, AI draft"]
    assert e["note"] == "1 code still holds the AI’s draft. A downloaded file does not carry that mark: say so to whoever you send it to."
    assert e["inHead"] is True and e["afterTitle"] is True
    assert page["editor head, own words"] is True          # rewritten: no line


@needs_node
def test_a_definition_drafted_by_the_local_model_says_where_it_was_read_and_asks_for_a_rewrite(page):
    d = page["definition drafted by local"]
    assert "The AI on this computer reads the 2 passages that hold this code’s examples, and its name: the text never leaves it." in d["line"]
    assert d["panel"].startswith("AI draft Drafted by qwen3:8b from the passages that hold this code’s examples.")
    assert "The AI on this computer read these passages." in d["panel"] and "rewrite them if they give away what these documents say" in d["panel"]
    assert d["sent"]["code"] == "Mending" and [x["quote"] for x in d["sent"]["examples"]] == ["we mend chairs", "mending is social"]


@needs_node
def test_a_definition_drafted_by_claude_does_not_say_it_was_read_on_this_computer(page):
    d = page["definition drafted by claude"]
    assert d["panel"].startswith("AI draft Drafted by claude-sonnet from the passages")
    assert "The AI on this computer" not in d["panel"]
    assert "Claude, on your plan, reads the 2 passages that hold this code’s examples, and its name." in d["line"]


@needs_node
def test_themes_the_ai_could_not_name_are_counted_with_the_reason_and_name_them_again(page):
    t = page["themes not named, one reason"]
    assert t["notice"].startswith("The AI (qwen3:8b) could not name 2 themes after three tries: the model answered with no name. "
                                  "They keep their key terms as a name. Name them again, or rename them yourself.")
    assert "Your local model (qwen3:8b) reads their passages on this computer" in t["notice"] and t["local"] is True
    assert t["posts"] == ["/api/projects/Study/themes/r1/name"]


@needs_node
def test_themes_not_named_for_several_reasons_say_each_says_why_below(page):
    t = page["themes not named, several reasons"]
    assert t.startswith("The AI (claude-haiku) could not name 2 themes after three tries: each says why below.")
    assert "on this computer" not in t


@needs_node
def test_no_notice_when_every_theme_is_named(page):
    assert page["themes all named"] is True


@needs_node
def test_the_themes_ai_line_names_the_ai_that_names_them(page):
    """0.20.1 (the owner's video of 18 November 2026): every theme only the local model may read, and the line said
    "Claude, on your plan, reads the passages of each theme"."""
    assert page["themes ai line, claude"]["line"] == "Claude, on your plan, reads the passages of each theme."
    assert page["themes ai line, absent"]["line"] == "Claude, on your plan, reads the passages of each theme."
    local = page["themes ai line, local"]
    assert local["line"] == ("The AI on this computer (qwen3.5:4b) reads the passages of each theme: their documents may "
                             "only be read on this computer. It starts when you press its own Start.")
    assert local["local"] is True and "Claude" not in local["line"]
    assert page["themes ai line, both"]["line"] == (
        "Claude, on your plan, reads the passages of 2 themes. The AI on this computer (qwen3.5:4b) reads the other 1 "
        "theme once you press its own Start. 1 theme may be read by no AI and keeps the name of its key terms.")
    assert page["themes ai line, nobody"]["line"] == ("No AI may read the passages of these themes: they keep the names of "
                                                      "their key terms.")
