"""0.19.13, the AI run panel's review: what the panel does while both engines run.

1. Claude's side was drawn again on every poll while both engines ran (the job's queue words flipped with a stripped
   copy whenever the local model's report was the newer one), so Stop Claude Code was replaced under the pointer.
3. This computer's count was one off and never moved ("waiting + 1"); it is now the most that waited at once, less
   what still waits.
4. Stop <model> pressed while it reads: the side says it stops after what it has in hand.

Node runs the real panel (views/progress.js and lib.js) in the small stand-in document of `_fakedom`, with a few more
of the DOM's methods the panel uses, and a stand-in for the app's answers. The rest is read as text.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from _fakedom import NODE, STATIC, run

needs_node = pytest.mark.skipif(not NODE, reason="node is not installed")

# what the panel needs of the DOM besides _fakedom's: moving nodes, a connected tree, and simple selectors
MORE_DOM = r"""
const P0 = Node.prototype;
const kids = (n) => n.childNodes.filter((c) => c instanceof Element);
P0.append = function (...ns) { for (const n of ns) this.appendChild(typeof n === "string" ? new Text(n) : n); };
P0.insertBefore = function (n, ref) {
  if (!ref) return this.appendChild(n);
  if (n.parentNode) n.parentNode.removeChild(n);
  n.parentNode = this; this.childNodes.splice(this.childNodes.indexOf(ref), 0, n); return n;
};
P0.before = function (...ns) { for (const n of ns) this.parentNode.insertBefore(n, this); };
P0.after = function (...ns) { const p = this.parentNode, i = p.childNodes.indexOf(this); const next = p.childNodes[i + 1] || null; for (const n of ns) p.insertBefore(n, next); };
P0.replaceWith = function (n) { const p = this.parentNode; if (!p || n === this) return; p.insertBefore(n, this); p.removeChild(this); };
P0.remove = function () { if (this.parentNode) this.parentNode.removeChild(this); };
Object.defineProperty(P0, "isConnected", { get() { let n = this; while (n.parentNode) n = n.parentNode; return n === document.body; } });
Object.defineProperty(P0, "previousElementSibling", { get() { if (!this.parentNode) return null; const k = kids(this.parentNode); return k[k.indexOf(this) - 1] || null; } });
Object.defineProperty(P0, "lastChild", { get() { return this.childNodes[this.childNodes.length - 1] || null; } });
Object.defineProperty(P0, "firstElementChild", { get() { return kids(this)[0] || null; } });
Object.defineProperty(P0, "childElementCount", { get() { return kids(this).length; } });
const one = (el, sel) => sel.split(".").filter(Boolean).every((c) => el.classList.contains(c)) && (!/^[a-z]/i.test(sel) || el.tagName === sel.split(".")[0].toUpperCase());
function all(root, sel) {
  const scoped = sel.startsWith(":scope >");
  const parts = sel.replace(":scope >", "").trim().split(/\s+/);
  const out = [];
  const walk = (n, depth) => { for (const c of kids(n)) { out.push([c, depth]); walk(c, depth + 1); } };
  walk(root, 0);
  return out.filter(([el, d]) => {
    if (scoped && d !== 0) return false;
    if (!one(el, parts[parts.length - 1])) return false;
    if (parts.length === 1) return true;
    for (let a = el.parentNode; a && a !== root.parentNode; a = a.parentNode) if (a instanceof Element && one(a, parts[0])) return true;
    return false;
  }).map(([el]) => el);
}
P0.querySelector = function (sel) { return all(this, sel)[0] || null; };
P0.querySelectorAll = function (sel) { return all(this, sel); };
Element.prototype.querySelector = P0.querySelector; Element.prototype.querySelectorAll = P0.querySelectorAll;
Element.prototype.matches = function (sel) { return one(this, sel); };
const mk = document.createElement;
document.createElement = (t) => { const e = mk(t); e.style.setProperty = function (k, v) { this[k] = v; }; e.classList.toggle = function (c, on) {
  const has = this.contains(c); const want = on === undefined ? !has : !!on; if (want && !has) this.add(c); if (!want && has) this.remove(c); return want; }; return e; };
document.hasFocus = () => false;
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
// the app's answers: the project's queue (Claude Code at work)
const QUEUE = { route: "claude_code", can_start: true, waiting: 2, being_answered: 1, command: "/margin-run p", privacy: null,
  runner: { running: true, seconds: 30, parallel: 2 }, claude: { found: true, signed_in: true },
  speed: { chosen: "normal", options: { normal: 2 }, helpers: [{ helper: "checker", name: "checker", models: ["m"], kinds: ["check"], waiting: 2 }] } };
globalThis.fetch = async (url) => ({ ok: true, status: 200, text: async () => JSON.stringify(String(url).includes("/queue") ? QUEUE : {}) });
const tick = () => new Promise((r) => setTimeout(r, 0));
const walk = (n, f) => { f(n); for (const c of n.childNodes || []) walk(c, f); };
const find = (root, text) => { let got = null; walk(root, (n) => { if (!got && n.tagName === "BUTTON" && n.textContent.includes(text)) got = n; }); return got; };
"""

PROBE = r"""
const L = await import(LIB);
const { aiRun } = await import(LIB.replace(/lib\.js$/, "views/progress.js"));
L.App.state = { settings: { backend: "claude_code", restricted_model: "qwen" }, project: "p" };
L.App.project = "p";
const qWords = { waiting: 2, being_answered: 1, estimate: "about 2 min", command: "/margin-run p", privacy: null };
// a poll whose newest report is the queue's (Claude Code), and one whose newest is the local model's
const fromQueue = (local) => ({ id: "j1", kind: "check", state: "running", seconds: 5, queue: true, local,
  progress: { queue: { ...qWords, at: 100 }, model: { phase: "queue", queue: qWords, at: 100 } } });
const fromLocal = (local, at, phase = "thinking") => ({ id: "j1", kind: "check", state: "running", seconds: 6, queue: true, local,
  progress: { queue: { ...qWords, at: 100 }, model: { who: "local", phase, at, seconds: 2, thinking_tokens: 40, tail: "so the plant" } } });
const local = (waiting, gate = "go") => ({ gate, waiting, noun: "excerpt", model: "qwen", memory: null, problem: null });

const panel = aiRun({ size: "compact", title: "Checking", noun: "excerpt" });
document.body.appendChild(panel.el);
panel.update(fromQueue(local(3))); await tick(); await tick();
const cloud = panel.sides.cloud;
const stopClaude = find(cloud, "Stop Claude Code");
const out = { stopClaude: !!stopClaude, counts: [], sameStop: [], sameLocalStop: [] };
let n = 3, at = 200;
let stopLocal = null;
for (const poll of [fromLocal(local(3), at++), fromQueue(local(3)), fromLocal(local(2), at++), fromQueue(local(2)), fromLocal(local(1), at++)]) {
  panel.update(poll); await tick(); await tick();
  out.sameStop.push(panel.sides.cloud === cloud && find(panel.sides.cloud, "Stop Claude Code") === stopClaude && stopClaude.isConnected);
  const c = panel.sides.local.querySelector(".ab-count");
  out.counts.push(c ? c.textContent : null);
  const s = find(panel.sides.local, "Stop qwen");
  if (stopLocal) out.sameLocalStop.push(s === stopLocal);
  stopLocal = stopLocal || s;
}
// Claude's queue empties while it works (no helper listed any more): its side looks again by itself (every 4 s)
QUEUE.waiting = 0; QUEUE.speed.helpers = [];
await new Promise((r) => setTimeout(r, 4600));
out.keptAfterQueueEmptied = find(panel.sides.cloud, "Stop Claude Code") === stopClaude && stopClaude.isConnected;
out.countNow = (panel.sides.cloud.querySelector(".ab-count") || {}).textContent || "";
// Stop qwen pressed (the gate waits) while the model still reads: it says when it stops, and offers no Stop
panel.update(fromLocal(local(1, "wait"), at++));
out.stopping = panel.sides.local.textContent.includes("Stops after the excerpts in hand");
out.stopGone = !find(panel.sides.local, "Stop qwen");
// a job that never said how many: no count
const plain = aiRun({ size: "compact", title: "Reading", noun: "excerpt" });
document.body.appendChild(plain.el);
plain.update({ id: "j2", kind: "read-local", state: "running", seconds: 1, progress: { model: { who: "local", phase: "thinking", at: 1, seconds: 1 } } });
const pc = plain.sides.local.querySelector(".ab-count");
out.noCount = pc ? pc.textContent : "";
console.log(JSON.stringify(out));
process.exit(0);
"""


@needs_node
def test_both_engines_at_work_replace_no_button_and_count_right(tmp_path):
    out = run(MORE_DOM + PROBE, tmp_path)
    assert out["stopClaude"], out
    # Claude's side and its Stop stay the same element through polls that flip between the two reports
    assert out["sameStop"] == [True] * 5, out
    assert out["sameLocalStop"] and all(out["sameLocalStop"]), out
    # the count: the most that waited (3), less what still waits; it moves as they are read
    assert out["counts"][0].startswith("0 of 3 excerpts done"), out
    assert out["counts"][2].startswith("1 of 3 excerpts done") and out["counts"][4].startswith("2 of 3 excerpts done"), out
    assert out["keptAfterQueueEmptied"] and "still waiting" not in out["countNow"], out   # its count, written in place
    assert out["stopping"] and out["stopGone"], out
    assert "of" not in out["noCount"], out


def _js(rel: str) -> str:
    return (STATIC / rel).read_text(encoding="utf-8")


def test_the_benchmark_panel_does_not_hide_its_button():
    """16: `const run = aiRun(...)` shadowed the button `run`, so Run the test stayed disabled after the test."""
    js = _js("views/settings.js")
    js = js[js.index('"Run the test"'):]
    follow = js[js.index("  function follow(jobId) {"):]
    follow = follow[:follow.index("\n  function drawResult")]
    assert "const run = aiRun" not in follow and "const panel = aiRun(" in follow and "run.disabled = false" in follow


def test_the_start_beside_judge_it_myself_asks_only_when_it_says_so():
    """7: "Starting it now asks first" was said whenever Judge it myself was offered, and Start asked nothing."""
    lib = _js("lib.js")
    side = lib[lib.index("function localSide(o, el) {"):lib.index("// ---- Claude's side")]
    assert 'asks ? " Starting it now asks first' in side
    assert "if (!(yourself && short)) return go(row.start, false);" in side and "go(row.start, true)" in side
    assert side.count('confirmIcon: "play"') == 2   # both Start it anyway dialogs: the play icon on the confirming button
    assert 'role: "status"' not in side             # the panel has its one live region


def test_a_non_ai_job_is_not_drawn_as_the_ai_panel():
    """22: the AI run panel only ever means AI: finding a new theme (no AI) has the plain bar."""
    themes = _js("views/themes.js")
    follow = themes[themes.index("  function followNew(jobId, name) {"):]
    follow = follow[:follow.index("\n  }\n")]
    assert "MiniJob" not in follow and "engines: []" not in follow and "simpleProgress(job" in follow


def test_ask_buttons_of_the_showcase_and_the_result_page_follow_the_rule():
    """11: play first, a verb and what it works on, never an engine."""
    design, result = _js("views/design.js"), _js("views/result.js")
    assert 'icon: "flask" }, "Check 3"' not in design and 'icon: "eye" }, "Look before checking"' not in design
    assert 'aiButton({ kind: "main" }, "Check 3")' in design
    assert "Let the local model read" not in result and '"Read it again" : "Read them again"' in result
