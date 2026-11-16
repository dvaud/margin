"""See what is sent run in Node with tests/_views.py (0.19.3; lib.js queueAiLine, showSent, sentParts): the button
under the queue's AI line, the dialog with the instruction and each task with its documents, Show the batch after,
the connector's raw reply, and the notes when nothing waits or nothing ever leaves the computer.
"""
from __future__ import annotations

import json

import pytest

from _views import needs_node, run_views

SYSTEM = "You label passages with the codes of a codebook. Quote exactly."
TASKS = [
    {"task_id": "t1", "prompt": "Passage p1: Volunteers fix toasters for free.",
     "documents": [{"doc_id": "d1", "title": "Repair report", "pages": [3, 4]}]},
    {"task_id": "t2", "prompt": "Passage p2: The evenings end with coffee.",
     "documents": [{"doc_id": "d2", "title": "Interview notes", "pages": [7]}, {"doc_id": "d3", "title": "Field diary", "pages": []}]},
    {"task_id": "t3", "prompt": "Passage p3: Neighbours meet monthly.",
     "documents": [{"doc_id": "d1", "title": "Repair report", "pages": [9]}]},
]


def _batch(start, tasks, more):
    """An answer of GET …/queue/preview in the shape taskqueue.preview gives it."""
    raw = {"claim": "(made when the batch is taken)", "kind": "label", "model": "haiku", "helper": "margin-labeller",
           "system": SYSTEM, "tasks": [{"task_id": t["task_id"], "prompt": t["prompt"]} for t in tasks]}
    return {"kind": "label", "title": "Labelling passages", "model": "haiku", "helper": "margin-labeller", "system": SYSTEM,
            "tasks": tasks, "raw": json.dumps(raw, ensure_ascii=False, indent=1), "waiting": 1204, "being_answered": 2,
            "start": start, "more": more}


FIRST, AFTER = _batch(0, TASKS[:2], True), _batch(2, TASKS[2:], False)

PROBE = r"""
const FIRST = __FIRST__, AFTER = __AFTER__;
const PREVIEW = "GET /api/projects/Study/queue/preview?*";
const line = (t, project = "Study", kind = "label") => { const l = t.LIB.queueAiLine(null, project, kind); document.getElementById("view").appendChild(l); return l; };
const body = (t) => t.dialog().querySelector(".dialog-body");
const asked = (t) => t.calls.filter((c) => c.path.includes("/queue/preview")).map((c) => c.path);

await scenario("the AI line", async (t) => {
  const withBtn = line(t);
  const without = t.LIB.queueAiLine("Claude Code sends what it reads to Anthropic.", null, "label");
  document.getElementById("view").appendChild(without);
  return { with: t.text(withBtn), buttons: t.buttons(withBtn).map((b) => b.label), without: t.text(without), none: t.buttons(without) };
});

await scenario("the next batch", async (t) => {
  t.answer(PREVIEW, (_b, path) => (new URL(path, "http://x").searchParams.get("start") === "0" ? FIRST : AFTER));
  line(t);
  await t.click("See what is sent");
  const d = t.dialog();
  const out = { title: t.text(d.querySelector("h2")), asked: asked(t), text: t.text(body(t)),
    heads: body(t).querySelectorAll(".sent-task h3").map((x) => t.text(x)),
    actions: t.buttons(d.querySelector(".dialog-actions")).map((b) => b.label) };
  await t.click(/^The instruction/, { within: d });
  out.instruction = t.text(body(t)).includes(FIRST.system);
  await t.click("Show the batch after", { within: d });
  out.after = { asked: asked(t), heads: body(t).querySelectorAll(".sent-task h3").map((x) => t.text(x)), text: t.text(body(t)),
    actions: t.buttons(d.querySelector(".dialog-actions")).map((b) => b.label), open: t.dialogs().length };
  await t.click("Close", { within: d.querySelector(".dialog-actions") });
  out.closed = t.dialogs().length;
  return out;
});

await scenario("the raw reply", async (t) => {
  t.answer(PREVIEW, FIRST);
  line(t);
  await t.click("See what is sent");
  const d = t.dialog();
  const before = t.text(body(t)).includes('"claim": "(made when the batch is taken)"');
  await t.click(/^As Claude Code receives it/, { within: d });
  const after = t.text(body(t)).includes('"claim": "(made when the batch is taken)"');
  await t.click("Copy it", { within: d });
  return { before, after, clipboard: t.clipboard, toasts: t.toasts() };
});

await scenario("nothing waits", async (t) => {
  t.answer(PREVIEW, { kind: null, note: "Nothing waits for Claude Code now, so nothing is about to be sent." });
  line(t, "Study", "");
  await t.click("See what is sent");
  const d = t.dialog();
  return { text: t.text(body(t)), actions: t.buttons(d.querySelector(".dialog-actions")).map((b) => b.label), asked: asked(t) };
});

await scenario("only a local model", async (t) => {
  t.answer(PREVIEW, { kind: null, note: "This installation keeps everything on this computer: nothing is sent to Claude Code." });
  line(t);
  await t.click("See what is sent");
  return { text: t.text(body(t)), actions: t.buttons(t.dialog().querySelector(".dialog-actions")).map((b) => b.label) };
});

await scenario("the preview fails", async (t) => {
  t.answer(PREVIEW, t.fail(500, "The queue could not be read."));
  line(t);
  await t.click("See what is sent");
  return { text: t.text(body(t)), toasts: t.toasts() };
});
""".replace("__FIRST__", json.dumps(FIRST)).replace("__AFTER__", json.dumps(AFTER))


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("sent"))


@needs_node
def test_the_ai_line_of_the_queue_has_see_what_is_sent_after_its_sentence(page):
    a = page["the AI line"]
    assert a["with"] == "Claude Code sends the passages inside the tasks it takes to Anthropic. See what is sent"
    assert a["buttons"] == ["See what is sent"]
    assert a["without"] == "Claude Code sends what it reads to Anthropic." and a["none"] == []   # no project: no button


@needs_node
def test_see_what_is_sent_opens_the_next_batch_of_its_kind_from_the_start(page):
    p = page["the next batch"]
    assert p["title"] == "What Claude Code is sent"
    assert p["asked"] == ["/api/projects/Study/queue/preview?kind=label&start=0"]
    assert p["text"].startswith("The next 2 tasks of Labelling passages, word for word as Claude Code's helper receives them")
    assert "1,204 waiting · 2 being answered now · margin-labeller on haiku." in p["text"]
    assert p["actions"] == ["Show the batch after", "Close"]


@needs_node
def test_each_task_shows_its_documents_and_pages_and_its_text(page):
    p = page["the next batch"]
    assert p["heads"] == ["Task 1 · Repair report, pp. 3, 4", "Task 2 · Interview notes, p. 7; Field diary"]
    assert "Passage p1: Volunteers fix toasters for free." in p["text"]
    assert "Passage p2: The evenings end with coffee." in p["text"]


@needs_node
def test_the_instruction_is_folded_once_above_the_tasks_and_opens(page):
    p = page["the next batch"]
    assert "The instruction (the same for every task of the batch)" in p["text"]
    assert SYSTEM not in p["text"]                                # folded at first
    assert p["instruction"] is True                               # shown once opened


@needs_node
def test_show_the_batch_after_asks_from_where_this_one_ends_and_shows_it_in_the_same_window(page):
    a = page["the next batch"]["after"]
    assert a["asked"][-1] == "/api/projects/Study/queue/preview?kind=label&start=2"
    assert a["heads"] == ["Task 3 · Repair report, p. 9"]
    assert a["text"].startswith("Tasks 3 to 3 of Labelling passages")
    assert "Volunteers fix toasters" not in a["text"]             # the batch before is gone
    assert a["open"] == 1
    assert a["actions"] == ["Close"]                              # nothing more waits: no batch after
    assert page["the next batch"]["closed"] == 0


@needs_node
def test_the_connectors_reply_is_folded_and_can_be_copied_whole(page):
    r = page["the raw reply"]
    assert r["before"] is False and r["after"] is True
    assert r["clipboard"] == [FIRST["raw"]]
    assert any(x.startswith("Copied.") for x in r["toasts"])


@needs_node
def test_with_nothing_waiting_the_window_says_so_and_offers_no_batch_after(page):
    n = page["nothing waits"]
    assert n["text"] == "Nothing waits for Claude Code now, so nothing is about to be sent."
    assert n["actions"] == ["Close"]
    assert n["asked"] == ["/api/projects/Study/queue/preview?kind=&start=0"]   # no kind: the first that waits


@needs_node
def test_an_installation_with_only_a_local_model_says_nothing_is_sent(page):
    n = page["only a local model"]
    assert n["text"] == "This installation keeps everything on this computer: nothing is sent to Claude Code."
    assert n["actions"] == ["Close"]


@needs_node
def test_a_preview_that_fails_says_so_in_the_window_and_why_in_a_toast(page):
    f = page["the preview fails"]
    assert f["text"] == "The preview could not be built."
    assert any("The queue could not be read." in x for x in f["toasts"])
