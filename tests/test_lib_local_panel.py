"""The local model's panel run in Node with tests/_views.py (lib.js localPanel, memoryRefused, jobFailed): Judge it
myself first and Start second (0.19.8), Start it anyway only once memory is short or Start was refused (0.19.4), and a
run refused for memory showing the panel in place of a toast, under the page's buttons or in a small window (0.19.5).
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const GiB = 1 << 30;
const SHORT = { need: 8.7 * GiB, free: 3.1 * GiB, short: true };
const ROOMY = { need: 4.2 * GiB, free: 12 * GiB, short: false };
const MODEL = "qwen3.5:9b";
// what a person sees of a panel's buttons: their words in order, and which is the main one
const row = (t, el) => [...el.querySelectorAll("button")].filter((b) => !t.hidden(b))
  .map((b) => [t.text(b), b.classList.contains("btn-primary") ? "main" : "other"]);
// the local side's state (0.19.12 AI run panel): "need" asks for attention, "wait" waits for the person's press
const kind = (el) => ({ need: "attention", wait: "waiting" }[el.querySelector(".ab-side").dataset.state] || el.querySelector(".ab-side").dataset.state);
function put(el) { document.getElementById("view").appendChild(el); return el; }

await scenario("judge it myself, memory short", async (t) => {
  const said = [];
  const p = put(t.LIB.localPanel({ count: 3, noun: "excerpt", model: MODEL, memory: SHORT, blocking: true,
    onStart: (force) => { said.push(["start", force]); }, onYourself: () => { said.push(["yourself"]); },
    yourselfText: "Judge them myself", yourselfNote: "They then wait for your judgement, marked Awaiting manual review; no model reads them." }));
  const out = { buttons: row(t, p), text: t.text(p), kind: kind(p) };
  await t.click("Judge them myself");
  out.afterYourself = { said: [...said], disabled: t.find("Judge them myself") ? t.find("Judge them myself").disabled : null };
  await t.click(`Start ${MODEL}`);   // with Judge it myself and too little memory, Start asks first
  out.dialogs = t.dialogs().length;
  out.asked = t.dialog() ? t.text(t.dialog().querySelector("h2")) : null;
  out.saidBeforeConfirm = [...said];
  await t.click("Start it anyway", { within: t.dialog() });
  out.said = said;
  return out;
});

await scenario("judge it myself, memory enough", async (t) => {
  const p = put(t.LIB.localPanel({ count: 1, noun: "excerpt", model: MODEL, memory: ROOMY, blocking: true,
    onStart: () => {}, onYourself: () => {} }));
  return { buttons: row(t, p), text: t.text(p) };
});

await scenario("judge it myself fails", async (t) => {
  const p = put(t.LIB.localPanel({ count: 2, model: MODEL, onStart: () => {}, onYourself: async () => { throw new Error("The excerpts could not be moved."); } }));
  await t.click("Judge it myself");
  return { toasts: t.toasts(), enabled: !t.find("Judge it myself").disabled };
});

await scenario("start only, memory enough", async (t) => {
  const said = [];
  const p = put(t.LIB.localPanel({ count: 33, model: MODEL, memory: ROOMY, onStart: (f) => { said.push(f); } }));
  const out = { buttons: row(t, p), text: t.text(p), kind: kind(p) };
  await t.click(`Start ${MODEL}`);
  out.said = said;
  out.startDisabled = t.find(`Start ${MODEL}`).disabled;
  return out;
});

await scenario("start only, memory short", async (t) => {
  const said = [];
  const p = put(t.LIB.localPanel({ count: 33, model: MODEL, memory: SHORT, onStart: (f) => { said.push(f); } }));
  const out = { buttons: row(t, p), text: t.text(p), kind: kind(p) };
  await t.click("Start it anyway");
  const d = t.dialog();
  out.asked = d ? t.text(d.querySelector("h2")) : null;
  out.askedButtons = d ? t.buttons(d.querySelector(".dialog-actions")).map((b) => b.label) : null;
  await t.click("Start it anyway", { within: d });
  out.said = said;
  return out;
});

await scenario("start it anyway, cancelled", async (t) => {
  const said = [];
  put(t.LIB.localPanel({ count: 33, model: MODEL, memory: SHORT, onStart: (f) => { said.push(f); } }));
  await t.click("Start it anyway");
  await t.click("Cancel", { within: t.dialog() });
  return { said, open: t.dialogs().length };
});

await scenario("while it reads", async (t) => {
  const p = put(t.LIB.localPanel({ model: MODEL, running: { phase: "thinking" }, onStart: () => {}, onYourself: () => {} }));
  return { buttons: row(t, p), text: t.text(p) };
});

await scenario("a problem in place of a start", async (t) => {
  const p = put(t.LIB.localPanel({ count: 2, problem: "No local model is chosen yet.", onStart: () => {} }));
  return { buttons: row(t, p), text: t.text(p), kind: kind(p), links: [...p.querySelectorAll("a")].map((a) => [t.text(a), a.getAttribute("href")]) };
});

// ---- a run refused for memory --------------------------------------------------------------------------------
const REFUSED = { id: "j7", title: "Naming themes", state: "error", error_kind: "memory", can_run_again: true,
  error: `${MODEL} was not started: it needs about 8.7 GB of memory, and 3.1 GB is free.`, memory: { model: MODEL, ...SHORT } };
function refusedAnswers(t) {
  t.answer("GET /api/local-status", { same_as_main: false, model: MODEL, memory: SHORT });
  t.answer("POST /api/jobs/j7/again", (body) => ({ job: { id: "j8", title: "Naming themes" } }));
}

await scenario("refused, in the page's place", async (t) => {
  refusedAnswers(t);
  const box = put(document.createElement("div")); box.hidden = true;
  const started = [];
  t.LIB.jobFailed(REFUSED, (j) => started.push(j.id), box);
  await t.settle();
  const out = { shown: !t.hidden(box), buttons: row(t, box), text: t.text(box), toasts: t.toasts(), dialogs: t.dialogs().length };
  await t.click("Start it anyway");
  out.asked = t.dialog() ? t.text(t.dialog().querySelector("h2")) : null;
  await t.click("Start it anyway", { within: t.dialog() });
  out.posts = t.calls.filter((c) => c.method === "POST").map((c) => [c.path, c.body]);
  out.started = started;
  return out;
});

await scenario("refused, start again checks again", async (t) => {
  refusedAnswers(t);
  const box = put(document.createElement("div")); box.hidden = true;
  const started = [];
  t.LIB.jobFailed(REFUSED, (j) => started.push(j.id), box);
  await t.settle();
  await t.click(`Start ${MODEL}`);
  return { posts: t.calls.filter((c) => c.method === "POST").map((c) => [c.path, c.body]), started, dialogs: t.dialogs().length };
});

await scenario("refused, in a small window", async (t) => {
  refusedAnswers(t);
  t.LIB.jobFailed(REFUSED);
  await t.settle();
  const d = t.dialog();
  const out = { title: d ? t.text(d.querySelector("h2")) : null, buttons: d ? row(t, d.querySelector(".dialog-body")) : null,
    text: d ? t.text(d.querySelector(".dialog-body")) : null, toasts: t.toasts() };
  await t.click("Start it anyway", { within: d });
  out.afterAnyway = { open: t.dialogs().length, posts: t.calls.filter((c) => c.method === "POST").map((c) => [c.path, c.body]), toasts: t.toasts() };
  return out;
});

await scenario("refused, cannot run again", async (t) => {
  t.LIB.jobFailed({ ...REFUSED, can_run_again: false });
  await t.settle();
  return { toasts: t.toasts(), dialogs: t.dialogs().length };
});

await scenario("another failure", async (t) => {
  const box = put(document.createElement("div")); box.hidden = true;
  t.LIB.jobFailed({ id: "j9", title: "Naming themes", state: "error", error_kind: "request", error: "The codebook was deleted meanwhile." }, null, box);
  await t.settle();
  return { toasts: t.toasts(), dialogs: t.dialogs().length, boxHidden: t.hidden(box), boxText: t.text(box) };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("local_panel"))


@needs_node
def test_with_judge_it_myself_it_is_the_first_and_main_button_and_start_comes_second(page):
    p = page["judge it myself, memory short"]
    assert p["buttons"] == [["Judge them myself", "main"], ["Start qwen3.5:9b", "other"]]
    assert "Start it anyway" not in p["text"]                  # Judge it myself takes its place
    assert "They then wait for your judgement, marked Awaiting manual review" in p["text"]
    assert "Needs about 8.7 GB of memory · 3.1 GB free now · 5.6 GB short" in p["text"]
    assert p["kind"] == "attention"                            # a blocking panel short of memory asks for attention


@needs_node
def test_judge_it_myself_hands_the_excerpts_over_and_start_starts_without_force(page):
    p = page["judge it myself, memory short"]
    assert p["afterYourself"]["said"] == [["yourself"]]
    assert p["afterYourself"]["disabled"] is True              # pressed once: not twice
    # too little memory: Start asks first (0.19.12) and starts, forced, only once confirmed
    assert p["dialogs"] == 1 and p["asked"] == "Start qwen3.5:9b anyway?"
    assert p["saidBeforeConfirm"] == [["yourself"]]
    assert p["said"] == [["yourself"], ["start", True]]


@needs_node
def test_judge_it_myself_stays_first_with_memory_enough(page):
    p = page["judge it myself, memory enough"]
    assert p["buttons"] == [["Judge it myself", "main"], ["Start qwen3.5:9b", "other"]]
    assert "Needs about 4.2 GB of memory · 12.0 GB free now" in p["text"]


@needs_node
def test_a_failed_judge_it_myself_says_why_and_can_be_pressed_again(page):
    p = page["judge it myself fails"]
    assert any("The excerpts could not be moved." in x for x in p["toasts"])
    assert p["enabled"] is True


@needs_node
def test_without_judge_it_myself_start_is_the_main_button_and_says_where_it_runs(page):
    p = page["start only, memory enough"]
    assert p["buttons"] == [["Start qwen3.5:9b", "main"]]
    assert "33 passages wait for qwen3.5:9b" in p["text"]
    assert "Nothing runs until you press it." in p["text"]
    assert "Start it anyway" not in p["text"]                  # memory enough: nothing to force
    assert p["kind"] == "waiting"
    assert p["said"] == [False] and p["startDisabled"] is True


@needs_node
def test_with_memory_short_start_it_anyway_comes_after_start_and_asks_first(page):
    p = page["start only, memory short"]
    assert p["buttons"] == [["Start qwen3.5:9b", "main"], ["Start it anyway", "other"]]
    assert "Close other programs, or choose a smaller model in Settings › AI." in p["text"]
    assert p["asked"] == "Start qwen3.5:9b anyway?"
    assert p["askedButtons"] == ["Cancel", "Start it anyway"]
    assert p["said"] == [True]                                 # forced, once confirmed


@needs_node
def test_start_it_anyway_cancelled_starts_nothing(page):
    assert page["start it anyway, cancelled"] == {"said": [], "open": 0}


@needs_node
def test_while_the_model_reads_the_panel_says_so_and_offers_no_button(page):
    p = page["while it reads"]
    assert p["buttons"] == []
    assert "qwen3.5:9b is thinking it over" in p["text"]
    assert "Change it in Settings" not in p["text"]           # the model's row is left out while it reads


@needs_node
def test_a_problem_takes_the_place_of_start_and_points_to_settings(page):
    p = page["a problem in place of a start"]
    assert p["buttons"] == []                                  # no Start of a model that cannot be used
    assert "No local model is chosen yet." in p["text"]
    assert p["kind"] == "attention"
    assert p["links"] == [["Choose one in Settings › AI", "#/settings/model"]]


@needs_node
def test_a_run_refused_for_memory_shows_the_panel_in_the_pages_place_not_a_toast(page):
    p = page["refused, in the page's place"]
    assert p["shown"] is True and p["toasts"] == [] and p["dialogs"] == 0
    assert p["buttons"] == [["Start qwen3.5:9b", "main"], ["Start it anyway", "other"]]
    assert "qwen3.5:9b was not started, so “Naming themes” waits for it" in p["text"]
    assert "Needs about 8.7 GB of memory · 3.1 GB free now" in p["text"]


@needs_node
def test_start_it_anyway_runs_the_refused_job_again_with_force(page):
    p = page["refused, in the page's place"]
    assert p["asked"] == "Start qwen3.5:9b anyway?"
    assert p["posts"] == [["/api/jobs/j7/again", {"force": True}]]
    assert p["started"] == ["j8"]                              # the page follows the new job


@needs_node
def test_start_after_a_refusal_runs_the_job_again_without_force(page):
    p = page["refused, start again checks again"]
    assert p["posts"] == [["/api/jobs/j7/again", {}]]
    assert p["started"] == ["j8"] and p["dialogs"] == 0


@needs_node
def test_without_a_place_on_the_page_the_panel_opens_in_a_small_window(page):
    p = page["refused, in a small window"]
    assert p["title"] == "Too little memory free for your local model"
    assert p["buttons"] == [["Start qwen3.5:9b", "main"], ["Start it anyway", "other"]]
    assert p["toasts"] == []
    # in the small window, Start it anyway asks nothing more: it starts, the window closes and the page says so
    a = p["afterAnyway"]
    assert a["posts"] == [["/api/jobs/j7/again", {"force": True}]]
    assert a["open"] == 0
    assert any("Started again: Naming themes" in x for x in a["toasts"])


@needs_node
def test_a_refusal_that_cannot_run_again_is_told_as_an_error(page):
    p = page["refused, cannot run again"]
    assert p["dialogs"] == 0
    assert any("qwen3.5:9b was not started" in x for x in p["toasts"])


@needs_node
def test_any_other_failure_still_shows_the_error_and_leaves_the_place_empty(page):
    p = page["another failure"]
    assert any("The codebook was deleted meanwhile." in x for x in p["toasts"])
    assert p["dialogs"] == 0 and p["boxHidden"] is True and p["boxText"] == ""
