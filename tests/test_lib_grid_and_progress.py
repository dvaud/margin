"""The heat grid's code names, the job line of a local model and the page saying it is in front, run in Node with
tests/_views.py: names wrapped a column each while they fit and slanted once they do not, short codes as they were
(0.19.3, lib.js heatGrid); tokens, speed, reading the prompt, gone quiet and time left (0.19.6, views/progress.js
modelDetail, timeLeft, MiniJob); X-Margin-Seen only while the tab is visible and focused (0.19.9, lib.js api).
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
// ---- the heat grid ------------------------------------------------------------------------------------------
const NAMES3 = ["Public trust in medical AI", "Repair as care", "Practice-arrangement bundle"];
const NAMES30 = Array.from({ length: 30 }, (_, i) => `Code name number ${i + 1}`);
const MARKS30 = Array.from({ length: 30 }, (_, i) => (i % 2 ? `${i + 1}.${i % 7}` : `SDG ${i + 1}`));
// a grid of `codes` in a frame `size.wrap` pixels wide, each name `size.text` pixels long on its widest line
function grid(t, codes, size, desc = {}) {
  const { h, heatGrid, heatHead, heatCell } = t.LIB;
  const table = h("table", { class: "map-table" },
    h("thead", {}, h("tr", {}, h("th", {}, "Document"), ...codes.map((c) => heatHead(c, { title: desc[c] ? `${c}: ${desc[c]}` : c })))),
    h("tbody", {}, h("tr", {}, h("th", {}, "Repair report"), ...codes.map((c, i) => heatCell(i % 3, 3, c, "tm", () => {})))));
  const box = heatGrid(table, { label: "Themes by code", unit: "codes" });
  document.getElementById("view").appendChild(box);
  t.layout((el) => (el.classList.contains("map-wrap") ? { top: 0, left: 0, width: size.wrap, height: 300, clientWidth: size.wrap, scrollWidth: size.wrap }
    : el.classList.contains("heat-head-text") ? { top: 0, left: 0, width: size.text, height: 16, offsetWidth: size.text } : null));
  return table;
}
const setting = (table) => ({ named: table.classList.contains("heat-named"), slant: table.classList.contains("heat-slant"),
  height: table.tHead.rows[0].style.height || "" });

await scenario("names that fit", async (t) => {
  const table = grid(t, NAMES3, { wrap: 1000, text: 150 }, { "Repair as care": "Fixing things as an act of care" });
  await t.resize({ wait: 20 });
  return { ...setting(table), heads: table.querySelectorAll("thead .heat-head").map((x) => [t.text(x), x.getAttribute("title")]) };
});

await scenario("names that no longer fit, and fit again", async (t) => {
  const size = { wrap: 1000, text: 150 };
  const table = grid(t, NAMES3, size);
  await t.resize({ wait: 20 });
  const wide = setting(table);
  size.wrap = 300;
  await t.resize({ wait: 20 });
  const narrow = setting(table);
  size.wrap = 1000;
  await t.resize({ wait: 20 });
  return { wide, narrow, again: setting(table) };
});

await scenario("thirty names", async (t) => {
  const table = grid(t, NAMES30, { wrap: 1400, text: 150 });
  await t.resize({ wait: 20 });
  return setting(table);
});

await scenario("thirty short codes", async (t) => {
  const table = grid(t, MARKS30, { wrap: 300, text: 30 });
  await t.resize({ wait: 20 });
  return setting(table);
});

await scenario("the column under the pointer", async (t) => {
  const table = grid(t, NAMES3, { wrap: 1000, text: 150 });
  await t.resize({ wait: 20 });
  const marked = () => table.querySelectorAll("thead .heat-head").filter((x) => x.hasAttribute("data-at")).map((x) => t.text(x));
  const cells = table.querySelectorAll("tbody td.map-cell");
  cells[1].dispatchEvent(new Event("mouseover", { bubbles: true }));
  const over = marked();
  cells[2].querySelector("button").dispatchEvent(new Event("focusin", { bubbles: true }));
  const focus = marked();
  table.dispatchEvent(new Event("mouseleave", { bubbles: false }));
  return { over, focus, left: marked() };
});

await scenario("which codes are names", async (t) => {
  const f = t.LIB.codesAreNames;
  return { marks: f(["3.4", "SDG 12", "12.5"]), ten: f(["abcdefghij"]), eleven: f(["abcdefghijk"]), mixed: f(["3.4", "Repair as care"]), none: f([]) };
});

// ---- the job line of a local model --------------------------------------------------------------------------
const T0 = 1_700_000_000_000;
const realNow = Date.now;
const atClock = (t) => { Date.now = () => T0 + t.clock.now; };

await scenario("model detail", async (t) => {
  t.state({ settings: { backend: "claude_code" } });
  atClock(t);
  const { modelDetail } = await t.module("views/progress.js");
  const one = (m) => modelDetail(m, { made: -1, at: 0 });
  const out = {
    loading: one({ who: "local", phase: "waiting", prompt_tokens: 5234, seconds: 12 }),
    loadingNoFigures: one({ who: "local", phase: "waiting" }),
    loadingLong: one({ who: "local", phase: "waiting", prompt_tokens: 900, seconds: 75 }),
    claudeLoadingLong: one({ who: "claude", phase: "waiting", seconds: 75 }),
    thinking: one({ who: "local", phase: "thinking", thinking_tokens: 1200, rate: 14.26 }),
    writing: one({ who: "local", phase: "writing", thinking_tokens: 1200, answer_tokens: 340, rate: 12, budget_reached: true }),
    writingNoFigures: one({ who: "local", phase: "writing" }),
    none: [one(null), one({}), one({ phase: "queue" }), one({ phase: "done" }), one({ phase: "refused" })],
  };
  t.state({ settings: { backend: "ollama" } });
  out.ollamaMain = one({ phase: "thinking", thinking_tokens: 10 });
  Date.now = realNow;
  return out;
});

await scenario("gone quiet", async (t) => {
  t.state({ settings: { backend: "ollama" } });
  atClock(t);
  const { modelDetail } = await t.module("views/progress.js");
  const seen = { made: -1, at: 0 };
  const m = { who: "local", phase: "thinking", thinking_tokens: 500, rate: 8 };
  const out = { first: modelDetail(m, seen) };
  await t.settle(19000);
  out.at19 = modelDetail(m, seen);
  await t.settle(6000);
  out.at25 = modelDetail(m, seen);
  out.moved = modelDetail({ ...m, thinking_tokens: 520 }, seen);
  // nothing written yet: a long silence while it reads is not "gone quiet"
  const fresh = { made: -1, at: 0 };
  modelDetail({ who: "local", phase: "thinking" }, fresh);
  await t.settle(60000);
  out.nothingYet = modelDetail({ who: "local", phase: "thinking" }, fresh);
  Date.now = realNow;
  return out;
});

await scenario("time left", async (t) => {
  const { timeLeft } = await t.module("views/progress.js");
  return {
    eight: timeLeft(120, 2, 10), underAMinute: timeLeft(30, 3, 4), longer: timeLeft(3000, 1, 4),
    minus: timeLeft(120, 2, 10, 100), spent: timeLeft(120, 2, 10, 600),
    noneYet: timeLeft(0, 0, 10), noTime: timeLeft(0, 2, 10), allDone: timeLeft(100, 10, 10),
  };
});

await scenario("the job's line", async (t) => {
  t.state({ settings: { backend: "claude_code" } });
  atClock(t);
  const { MiniJob } = await t.module("views/progress.js");
  const mj = new MiniJob({ title: "Naming themes" });
  document.getElementById("view").appendChild(mj.el);
  const tail = "word ".repeat(80) + "the last words it wrote";
  const job = (model, state = "running") => ({ id: "j1", state, seconds: 40, progress: { elapsed: 40, model } });
  // 0.19.12: the line is the local side of the job's AI run panel: its words, its tail and its figures
  const read = () => ({ msg: t.text(mj.msg), side: t.text(mj.el.querySelector(".ar-local")) });
  const out = {};
  mj.update(job({ who: "local", model: "qwen3.5:9b", phase: "waiting", prompt_tokens: 3100, seconds: 4 }));
  out.loading = read();
  mj.update(job({ who: "local", model: "qwen3.5:9b", phase: "thinking", thinking_tokens: 800, rate: 9.5, tail }));
  out.thinking = read();
  await t.settle(25000);
  mj.update(job({ who: "local", model: "qwen3.5:9b", phase: "thinking", thinking_tokens: 800, rate: 9.5, tail }));
  out.quiet = read();
  mj.update(job({ who: "local", model: "qwen3.5:9b", phase: "writing", thinking_tokens: 800, answer_tokens: 60, rate: 9.5, tail }));
  out.writing = read();
  mj.update(job({ who: "local", model: "qwen3.5:9b", phase: "done" }, "done"));
  out.done = read();
  Date.now = realNow;
  return out;
});

// ---- the page says when it is in front (0.19.9) -------------------------------------------------------------
await scenario("in front", async (t) => {
  t.answer("GET /api/ping", {});
  const seen = async () => { await t.LIB.api("GET", "/api/ping"); const c = t.calls[t.calls.length - 1]; return c.headers["X-Margin-Seen"] || null; };
  const out = { front: await seen() };
  document.visibilityState = "hidden";
  out.hidden = await seen();
  document.visibilityState = "visible";
  const focus = document.hasFocus;
  document.hasFocus = () => false;
  out.unfocused = await seen();
  document.hasFocus = focus;
  out.back = await seen();
  out.token = "X-Margin-Token" in t.calls[0].headers;
  return out;
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("grid_progress"))


# ---- the heat grid -------------------------------------------------------------------------------------------
@needs_node
def test_names_that_fit_a_column_each_are_wrapped_upright(page):
    g = page["names that fit"]
    assert g["named"] is True and g["slant"] is False and g["height"] == ""


@needs_node
def test_each_name_shows_whole_and_hovering_says_the_code_with_its_description(page):
    heads = page["names that fit"]["heads"]
    assert [h[0] for h in heads] == ["Public trust in medical AI", "Repair as care", "Practice-arrangement bundle"]
    assert heads[1][1] == "Repair as care: Fixing things as an act of care"
    assert heads[0][1] == "Public trust in medical AI"


@needs_node
def test_names_are_slanted_once_a_column_each_no_longer_fits_and_upright_again_when_it_does(page):
    g = page["names that no longer fit, and fit again"]
    assert g["wide"] == {"named": True, "slant": False, "height": ""}
    # the header row is as tall as the longest name at 45° plus its two lines' room: 150·√½ + 2.3·16 = 142.9
    assert g["narrow"] == {"named": True, "slant": True, "height": "143px"}
    assert g["again"] == {"named": True, "slant": False, "height": ""}


@needs_node
def test_thirty_names_on_a_wide_window_are_slanted(page):
    assert page["thirty names"] == {"named": True, "slant": True, "height": "143px"}


@needs_node
def test_short_codes_such_as_sdg_targets_stay_upright_marks_however_many(page):
    assert page["thirty short codes"] == {"named": False, "slant": False, "height": ""}


@needs_node
def test_the_head_of_the_column_under_the_pointer_or_the_focus_is_marked_and_unmarked_on_leaving(page):
    p = page["the column under the pointer"]
    assert p["over"] == ["Repair as care"]
    assert p["focus"] == ["Practice-arrangement bundle"]
    assert p["left"] == []


@needs_node
def test_codes_longer_than_ten_characters_make_a_codebook_of_names(page):
    assert page["which codes are names"] == {"marks": False, "ten": False, "eleven": True, "mixed": True, "none": False}


# ---- the job line of a local model ---------------------------------------------------------------------------
@needs_node
def test_while_loading_the_line_says_where_it_runs_how_long_the_prompt_is_and_how_long_so_far(page):
    d = page["model detail"]
    assert d["loading"] == "On this computer · reading a prompt of about 5,234 tokens · 12 s so far"
    assert d["loadingNoFigures"] == "On this computer · reading the prompt"
    assert d["loadingLong"] == ("On this computer · reading a prompt of about 900 tokens · 75 s so far · "
                                "a model on this computer can take a few minutes to start")


@needs_node
def test_a_model_that_is_not_on_this_computer_is_not_said_to_be(page):
    assert page["model detail"]["claudeLoadingLong"] == "reading the prompt · 75 s so far"


@needs_node
def test_while_it_writes_the_line_counts_its_tokens_and_speed(page):
    d = page["model detail"]
    assert d["thinking"] == "On this computer · 1,200 tokens of reasoning · 14.3 a second"
    assert d["writing"] == ("On this computer · 1,200 tokens of reasoning · 340 of its answer · 12.0 a second · "
                            "its reasoning budget is used up, so it answers from its notes now")
    assert d["writingNoFigures"] == "On this computer"


@needs_node
def test_a_local_model_of_settings_is_on_this_computer_without_being_told(page):
    assert page["model detail"]["ollamaMain"] == "On this computer · 10 tokens of reasoning"


@needs_node
def test_no_line_while_it_waits_its_turn_has_finished_or_was_refused(page):
    assert page["model detail"]["none"] == [None, None, None, None, None]


@needs_node
def test_after_twenty_seconds_without_a_new_token_the_line_says_it_has_gone_quiet(page):
    q = page["gone quiet"]
    assert q["first"] == "On this computer · 500 tokens of reasoning · 8.0 a second"
    assert q["at19"] == q["first"]
    assert q["at25"] == q["first"] + " · nothing new for 25 s; it may still be working"
    assert q["moved"] == "On this computer · 520 tokens of reasoning · 8.0 a second"   # a new token: no longer quiet
    assert q["nothingYet"] == "On this computer"


@needs_node
def test_time_left_is_reckoned_from_the_items_done_and_left_out_when_it_cannot_be(page):
    t = page["time left"]
    assert t["eight"] == "about 8 min left"
    assert t["underAMinute"] == "less than a minute left"
    assert t["longer"] == "about 2 h 30 min left"
    assert t["minus"] == "about 7 min left"                    # the time on the current item counts
    assert t["spent"] is None                                  # the estimate has run out
    assert t["noneYet"] is None and t["noTime"] is None and t["allDone"] is None


@needs_node
def test_the_jobs_line_names_the_local_model_and_shows_its_numbers_and_latest_words(page):
    j = page["the job's line"]
    assert j["loading"]["msg"] == "Naming themes…"
    assert j["loading"]["side"] == ("On this computer At work\nqwen3.5:9b is loading and reading\n4.0 s\n"
                                    "reading a prompt of about 3,100 tokens · 4.0 s so far")
    assert "qwen3.5:9b is thinking it over" in j["thinking"]["side"]
    assert j["thinking"]["side"].endswith("the last words it wrote▍\n800 tokens of reasoning · 9.5 a second")
    assert "Nothing new for 25 s; it may still be working." in j["quiet"]["side"]
    assert "qwen3.5:9b is writing its answer" in j["writing"]["side"]
    assert j["writing"]["side"].endswith("800 tokens of reasoning · 60 of its answer · 9.5 a second")
    assert j["done"]["msg"] == "Done." and j["done"]["side"] == "On this computer Done\nqwen3.5:9b has read its part"


# ---- in front ------------------------------------------------------------------------------------------------
@needs_node
def test_the_page_says_it_is_in_front_only_while_visible_and_focused(page):
    s = page["in front"]
    assert s["front"] == "1" and s["back"] == "1"
    assert s["hidden"] is None
    assert s["unfocused"] is None
    assert s["token"] is True
