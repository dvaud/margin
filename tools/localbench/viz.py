"""The bench visualiser: every measured area as a scale, each local model in its own lane, Opus and Sonnet as
reference lanes switched on per scale. Built from data/report.json, the runs and data/claude_meta.json.

    python tools/localbench/viz.py      # -> data/bench-visualiser.html
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
LOCALS = {"qwen3.5_4b": "Qwen 3.5 4B", "ifm_k2-horizon_0.9b": "K2 Horizon 0.9B"}
REFS = {"opus": "Opus 5.5", "sonnet": "Sonnet 5.5"}


def _jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _pairwise(tag: str, variants: list[str]) -> float | None:
    by: dict[str, dict] = {}
    for r in _jl(DATA / "runs" / f"{tag}.jsonl"):
        by.setdefault(r["variant"], {})[r["id"]] = r.get("status")
    vs = [v for v in variants if v in by]
    pairs = [(a, b) for a, b in itertools.combinations(vs, 2)]
    same = [by[a][i] == by[b][i] for a, b in pairs for i in by[a] if i in by[b]]
    return sum(same) / len(same) if same else None


def _cross(tag_a: str, tag_b: str) -> float | None:
    a = {r["id"]: r.get("status") for r in _jl(DATA / "runs" / f"{tag_a}.jsonl")}
    b = {r["id"]: r.get("status") for r in _jl(DATA / "runs" / f"{tag_b}.jsonl")}
    c = [a[i] == b[i] for i in a if i in b]
    return sum(c) / len(c) if c else None


def _mean(*xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def collect() -> dict:
    rep = json.loads((DATA / "report.json").read_text())["models"]
    meta = json.loads((DATA / "claude_meta.json").read_text()) if (DATA / "claude_meta.json").exists() else {}
    out: dict = {"models": {}, "refs": {}, "labels": {**LOCALS, **REFS}}
    sampling = ["base", "t07_s1", "t07_s2", "t07_s3", "t07_s4"]
    for tag in LOCALS:
        m = rep.get(tag)
        if not m:
            continue
        c = m.get("controls", {})
        out["models"][tag] = {
            "status_acc": m.get("status_acc"), "kappa": m.get("grounded_kappa"), "baseline": m.get("always_nothing_acc"),
            "planted": c.get("planted"), "flip": c.get("flip"), "irrel": c.get("irrel"), "recall": m.get("passage_recall"),
            "stated": m.get("counting_mean_conf"), "right": m.get("counting_precision"), "ece": m.get("ece_lenient"),
            "false_pos": m.get("false_positives_counting"), "usable": m.get("usable"),
            "determinism": m.get("determinism"), "identical": m.get("identical_raw"), "order": m.get("order_stable"),
            "pairwise": _pairwise(tag, sampling), "settled_right": m.get("acc_when_settled"),
            "unsettled_right": m.get("acc_when_unsettled"), "seconds": m.get("sec_median"),
            "memory": m.get("memory_gb"), "tok_s": m.get("output_tok_s"), "reliability": m.get("reliability_lenient"),
        }
    for ref in REFS:
        a, b = rep.get(f"{ref}-A"), rep.get(f"{ref}-B")
        if not (a and b):
            continue
        avg = lambda k: _mean(a.get(k), b.get(k))
        ctl = lambda k: _mean(a.get("controls", {}).get(k), b.get("controls", {}).get(k))
        sec = meta.get(ref, {})
        out["refs"][ref] = {
            "status_acc": avg("status_acc"), "kappa": avg("grounded_kappa"), "planted": ctl("planted"),
            "flip": ctl("flip"), "irrel": ctl("irrel"), "recall": avg("passage_recall"),
            "stated": avg("counting_mean_conf"), "right": avg("counting_precision"), "ece": avg("ece_lenient"),
            "false_pos": avg("false_positives_counting"), "usable": avg("usable"),
            "pairwise": _cross(f"{ref}-A", f"{ref}-B"),
            "seconds": sec["ms"] / sec["items"] / 1000 if sec.get("items") else None,
            "reliability": a.get("reliability_lenient"), "reliability_b": b.get("reliability_lenient"),
            "upper_bound": ref == "opus",
        }
    return out


PAGE = r"""<title>Bench Visualiser</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* Layout: four areas, each a stack of scales; every scale shows one lane per model, reference lanes added on demand. */
:root {
  --bg: #f5f7f6; --surface: #ffffff; --fg: #16201d; --fg2: #4a5653; --muted: #78837f; --line: #dce3e0; --track: #e9eeec;
  --accent: #0f766e; --qwen: #2a78d6; --k2: #eb6834; --opus: #6250d6; --sonnet: #1baf7a; --base: #8a9391;
  --font-ui: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121715; --surface: #1a211f; --fg: #e8eeec; --fg2: #b4bfbc; --muted: #86918e; --line: #2c3633; --track: #253029;
  --accent: #4fb3a9; --qwen: #3987e5; --k2: #d95926; --opus: #9085e9; --sonnet: #199e70; --base: #7d8785; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #121715; --surface: #1a211f; --fg: #e8eeec; --fg2: #b4bfbc; --muted: #86918e; --line: #2c3633; --track: #253029;
  --accent: #4fb3a9; --qwen: #3987e5; --k2: #d95926; --opus: #9085e9; --sonnet: #199e70; --base: #7d8785; color-scheme: dark; }
body { background: var(--bg); color: var(--fg); font: 15px/1.5 var(--font-ui); }
main { max-width: 1040px; margin: 0 auto; padding-block: 28px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 30px; }
h1 { font: 600 1.9rem/1.15 var(--font-serif); margin: 0; }
h2 { font: 600 1.25rem/1.2 var(--font-serif); margin: 0; }
.eyebrow { font-size: .74rem; text-transform: uppercase; letter-spacing: .07em; color: var(--muted); font-weight: 600; }
p { margin: 0; max-width: 70ch; }
.lede { color: var(--fg2); }
.bar { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 4; background: var(--bg); padding-block: 10px;
  display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; border-bottom: 1px solid var(--line); }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--bg); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .85rem; color: var(--fg2); align-items: center; }
.key { display: inline-flex; gap: 6px; align-items: center; }
.sw { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
.sw.dia { border-radius: 2px; transform: rotate(45deg) scale(.85); }
.sw.sq { border-radius: 2px; }
.toggles { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }
button.tg { font: 600 .78rem var(--font-ui); border: 1px solid var(--line); background: var(--surface); color: var(--fg2);
  border-radius: 999px; padding: 4px 11px; cursor: pointer; display: inline-flex; gap: 6px; align-items: center; }
button.tg[aria-pressed="true"] { color: var(--fg); border-color: currentColor; }
button.tg[aria-pressed="true"].opus { color: var(--opus); } button.tg[aria-pressed="true"].sonnet { color: var(--sonnet); }
button.tg:disabled { opacity: .45; cursor: not-allowed; }
button.tg:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.area { display: grid; gap: 12px; }
.area-head { display: grid; gap: 4px; }
.scale { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px;
  display: grid; grid-template-columns: minmax(200px, 300px) 1fr; gap: 6px 18px; align-items: start; }
.scale .info { display: grid; gap: 3px; min-width: 0; }
.scale .name { font-weight: 600; }
.scale .hint { font-size: .8rem; color: var(--muted); }
.scale .row-tg { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.scale .plot { min-width: 0; }
.scale svg { width: 100%; display: block; overflow: visible; }
svg text { fill: var(--fg2); font: 11px var(--font-ui); }
svg text.val { fill: var(--fg); font-weight: 600; font-variant-numeric: tabular-nums; }
svg text.lane { fill: var(--muted); }
.note { font-size: .8rem; color: var(--muted); }
figure { margin: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 14px; display: grid; gap: 8px; }
figcaption { font-size: .85rem; color: var(--fg2); max-width: 72ch; }
@media (max-width: 640px) { .scale { grid-template-columns: 1fr; } .toggles { margin-left: 0; } }
@media (prefers-reduced-motion: no-preference) { .scale svg .mk { transition: opacity .2s; } }
</style>
<main>
  <nav class="tabs" aria-label="Pages"><a href="#bench">Bench</a><a href="#review">After review</a></nav>
<div id="view-bench" style="display:grid;gap:30px">
  <header style="display:grid;gap:8px">
    <span class="eyebrow">Margin · green hydrogen pilot · 45 items</span>
    <h1>Bench Visualiser</h1>
    <p class="lede">Each scale is one measure. Qwen 3.5 4B and K2 Horizon 0.9B each have a lane. Switch on Opus or Sonnet on any
    scale to see where Claude lands on the same items. Opus is an upper bound, because the gold answers come from
    two Opus passes. Sonnet answered blind and is scored like the local models.</p>
  </header>
  <div class="bar">
    <div class="legend">
      <span class="key"><span class="sw" style="background:var(--qwen)"></span>Qwen 3.5 4B</span>
      <span class="key"><span class="sw" style="background:var(--k2)"></span>K2 Horizon 0.9B</span>
      <span class="key"><span class="sw dia" style="background:var(--opus)"></span>Opus 5.5</span>
      <span class="key"><span class="sw sq" style="background:var(--sonnet)"></span>Sonnet 5.5</span>
    </div>
    <div class="toggles">
      <button class="tg opus" id="all-opus" aria-pressed="false">Opus on every scale</button>
      <button class="tg sonnet" id="all-sonnet" aria-pressed="false">Sonnet on every scale</button>
    </div>
  </div>
  <div id="areas" style="display:grid;gap:34px"></div>
  <section class="area">
    <div class="area-head"><span class="eyebrow">Overconfidence, in detail</span><h2>Stated confidence against share right</h2></div>
    <figure>
      <div class="row-tg" style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="tg opus" id="cal-opus" aria-pressed="false">Opus</button>
        <button class="tg sonnet" id="cal-sonnet" aria-pressed="false">Sonnet</button>
      </div>
      <div id="cal"></div>
      <figcaption>Each point is a group of graded passages, placed by the confidence the model stated (across) and the
      share that gold grades in the same direction (up). Points on the dashed diagonal are honest. Points below it
      mean the model is surer than it is right.</figcaption>
    </figure>
  </section>
  <p class="note" id="foot"></p>
</div>
<div id="view-review" hidden style="display:grid;gap:26px"></div>
</main>
<script>
const D = __DATA__;
const $ = s => document.querySelector(s);
const LOCAL = Object.keys(D.models), REF = Object.keys(D.refs);
const COL = { "qwen3.5_4b": "var(--qwen)", "ifm_k2-horizon_0.9b": "var(--k2)", opus: "var(--opus)", sonnet: "var(--sonnet)" };
const SHAPE = { opus: "dia", sonnet: "sq" };
const P = v => v == null ? "–" : Math.round(v * 100) + "%";
const N1 = v => v == null ? "–" : (+v).toFixed(1);
const N2 = v => v == null ? "–" : (+v).toFixed(2);

// fmt: value text; max: scale end (pct scales 1); unit for the axis; better: "up" | "down"; na: why Claude has no value
const AREAS = [
  { title: "Performance", eyebrow: "Is it right?", scales: [
    { k: "status_acc", name: "Right status", hint: "supported, partly, contradicted or nothing, as gold says", fmt: P, better: "up",
      base: ["baseline", "always “nothing”"] },
    { k: "kappa", name: "Grounded or not, beyond chance", hint: "kappa: 0 is chance, 1 is full agreement", fmt: N2, better: "up", min: -0.2, max: 1 },
    { k: "planted", name: "Hidden answer found", hint: "5 controls: a paraphrase of the claim slipped into one passage", fmt: P, better: "up" },
    { k: "flip", name: "Opposite claim caught", hint: "5 controls: a supported claim turned into its opposite", fmt: P, better: "up" },
    { k: "irrel", name: "Unrelated passages left alone", hint: "5 controls: passages from another SDG goal", fmt: P, better: "up" },
    { k: "recall", name: "Gold passages found", hint: "graded at 0.6 or more", fmt: P, better: "up" },
  ]},
  { title: "Overconfidence", eyebrow: "Does it know when it is wrong?", scales: [
    { k: "gap", name: "Stated confidence against share right", hint: "grades the app counts (0.6 or more): ○ stated, ● right", fmt: P, better: "gap", pair: ["stated", "right"] },
    { k: "ece", name: "Calibration error", hint: "ECE: 0 means its confidence is honest", fmt: N2, better: "down", max: 0.7 },
    { k: "false_pos", name: "Passages graded that bear on nothing", hint: "confidence 0.6 or more, over 45 items", fmt: v => v == null ? "–" : Math.round(v), better: "down", max: 140 },
    { k: "usable", name: "Answers usable first time", hint: "valid format, every quote found in its passage", fmt: P, better: "up" },
  ]},
  { title: "Reliability", eyebrow: "Does it say the same thing twice?", scales: [
    { k: "pairwise", name: "Two runs agree on the status", hint: "local: any two of 5 runs (the app's settings and 4 samples at temperature 0.7); Claude: pass 1 against pass 2", fmt: P, better: "up" },
    { k: "determinism", name: "Same settings, same status", hint: "temperature 0 and seed 42, as the app sends", fmt: P, better: "up", na: "Claude takes no seed or temperature here" },
    { k: "identical", name: "Same settings, same answer word for word", hint: "the whole answer, quotes included", fmt: P, better: "up", na: "Claude takes no seed or temperature here" },
    { k: "order", name: "Passages reshuffled, same status", hint: "the order should not matter to a reader", fmt: P, better: "up", na: "not measured for Claude" },
    { k: "settled", name: "Right when it never changes its mind, and when it does", hint: "● all 5 runs the same · ○ the runs disagree", fmt: P, better: "up", pair: ["unsettled_right", "settled_right"], na: "needs 5 runs; Claude has 2" },
  ]},
  { title: "Speed and hardware", eyebrow: "What does it cost to run?", scales: [
    { k: "seconds", name: "Seconds per check", hint: "median; Claude: wall time per item in Claude Code, in the cloud", fmt: v => v == null ? "–" : N1(v) + " s", better: "down", max: 15 },
    { k: "memory", name: "Memory while loaded", hint: "Ollama, 16k context; Qwen grew from 5.2 GB during the run", fmt: v => v == null ? "–" : N1(v) + " GB", better: "down", max: 16, na: "runs in the cloud, not on this laptop" },
    { k: "tok_s", name: "Writing speed", hint: "tokens per second while answering", fmt: v => v == null ? "–" : Math.round(v) + " tok/s", better: "up", max: 100, na: "not reported by Claude Code" },
  ]},
];
const state = {}; // scaleKey -> {opus: bool, sonnet: bool}

function lanes(sc) {
  const out = LOCAL.map(t => ({ t, label: D.labels[t], v: D.models[t] }));
  for (const r of REF) if (state[sc.k]?.[r] && !sc.na) out.push({ t: r, label: D.labels[r] + (D.refs[r].upper_bound ? " (upper bound)" : ""), v: D.refs[r], ref: true });
  return out;
}
function mark(t, x, y, filled = true) {
  const c = COL[t], sh = SHAPE[t];
  if (sh === "dia") return `<rect class="mk" x="${x - 5.5}" y="${y - 5.5}" width="11" height="11" rx="1.5" transform="rotate(45 ${x} ${y})" fill="${filled ? c : "var(--surface)"}" stroke="${c}" stroke-width="2"/>`;
  if (sh === "sq") return `<rect class="mk" x="${x - 5.5}" y="${y - 5.5}" width="11" height="11" rx="2" fill="${filled ? c : "var(--surface)"}" stroke="${c}" stroke-width="2"/>`;
  return `<circle class="mk" cx="${x}" cy="${y}" r="6.5" fill="${filled ? c : "var(--surface)"}" stroke="${filled ? "var(--surface)" : c}" stroke-width="2"/>`;
}
function draw(sc) {
  const L = lanes(sc), W = 640, lane = 30, top = 8, labelW = 128, right = sc.k === "gap" ? 190 : sc.pair ? 110 : 64;
  const H = top + L.length * lane + 22;
  const lo = sc.min ?? 0, hi = sc.max ?? 1;
  const x = v => labelW + (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * (W - labelW - right);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${sc.name}">`;
  const ticks = sc.max && sc.max > 1 ? [0, hi / 4, hi / 2, hi * 3 / 4, hi] : (lo < 0 ? [lo, 0, .25, .5, .75, 1] : [0, .25, .5, .75, 1]);
  for (const t of ticks) {
    s += `<line x1="${x(t)}" x2="${x(t)}" y1="${top}" y2="${H - 18}" stroke="var(--line)"/>`;
    s += `<text x="${x(t)}" y="${H - 4}" text-anchor="middle">${sc.max && sc.max > 1 ? Math.round(t) : (sc.fmt === P ? Math.round(t * 100) + "%" : t.toFixed(2))}</text>`;
  }
  if (sc.base) {
    const bv = D.models[LOCAL[0]][sc.base[0]];
    s += `<line x1="${x(bv)}" x2="${x(bv)}" y1="${top - 4}" y2="${H - 18}" stroke="var(--base)" stroke-dasharray="3 3" stroke-width="1.5"/>`;
    s += `<text x="${x(bv) + 4}" y="${top + 2}" style="fill:var(--muted)">${sc.base[1]} ${P(bv)}</text>`;
  }
  L.forEach((l, i) => {
    const y = top + i * lane + lane / 2 + 4;
    s += `<text class="lane" x="0" y="${y + 4}">${l.label}</text>`;
    s += `<line x1="${x(lo)}" x2="${x(hi)}" y1="${y}" y2="${y}" stroke="var(--track)" stroke-width="4" stroke-linecap="round"/>`;
    if (sc.pair) {
      const [a, b] = sc.pair, va = l.v[a], vb = l.v[b];
      if (va == null || vb == null) { s += `<text x="${x(lo)}" y="${y + 4}">–</text>`; return; }
      s += `<line x1="${x(va)}" x2="${x(vb)}" y1="${y}" y2="${y}" stroke="${COL[l.t]}" stroke-width="2.5"/>`;
      s += mark(l.t, x(va), y, false) + mark(l.t, x(vb), y, true);
      const gap = Math.round((va - vb) * 100), txt = sc.k === "gap" ? `${P(va)} sure · ${P(vb)} right · ${gap > 0 ? "+" : ""}${gap} pts` : `${P(vb)} vs ${P(va)}`;
      s += `<text class="val" x="${Math.max(x(va), x(vb)) + 12}" y="${y + 4}">${txt}</text>`;
    } else {
      const v = l.v[sc.k];
      if (v == null) { s += `<text x="${x(lo)}" y="${y + 4}">not measured</text>`; return; }
      s += mark(l.t, x(v), y, true);
      s += `<text class="val" x="${x(v) + 12}" y="${y + 4}">${sc.fmt(v)}</text>`;
    }
  });
  return s + `</svg>`;
}
function better(sc) {
  return sc.better === "up" ? "higher is better →" : sc.better === "down" ? "← lower is better" : "the closer the two marks, the more honest";
}
function renderScale(sc) {
  const el = document.getElementById("s-" + sc.k);
  el.querySelector(".plot").innerHTML = draw(sc);
  el.querySelectorAll("button.tg").forEach(b => b.setAttribute("aria-pressed", !!state[sc.k]?.[b.dataset.ref]));
}
function build() {
  $("#areas").innerHTML = AREAS.map(a => `<section class="area"><div class="area-head"><span class="eyebrow">${a.eyebrow}</span><h2>${a.title}</h2></div>` +
    a.scales.map(sc => `<div class="scale" id="s-${sc.k}"><div class="info"><span class="name">${sc.name}</span><span class="hint">${sc.hint}</span>
      <span class="hint">${better(sc)}</span><div class="row-tg">${REF.map(r => `<button class="tg ${r}" data-ref="${r}" data-k="${sc.k}" aria-pressed="false"
      ${sc.na ? `disabled title="${sc.na}"` : ""}>${sc.na ? D.labels[r].split(" ")[0] + ": " + sc.na : "vs " + D.labels[r].split(" ")[0]}</button>`).join("")}</div></div>
      <div class="plot"></div></div>`).join("") + `</section>`).join("");
  AREAS.forEach(a => a.scales.forEach(renderScale));
}
document.addEventListener("click", e => {
  const b = e.target.closest("button.tg[data-k]");
  if (!b || b.disabled) return;
  const k = b.dataset.k, r = b.dataset.ref;
  state[k] = state[k] || {}; state[k][r] = !state[k][r];
  renderScale(AREAS.flatMap(a => a.scales).find(s => s.k === k));
  syncAll();
});
function syncAll() {
  for (const r of REF) {
    const scs = AREAS.flatMap(a => a.scales).filter(s => !s.na);
    $("#all-" + r)?.setAttribute("aria-pressed", scs.every(s => state[s.k]?.[r]));
  }
}
for (const r of ["opus", "sonnet"]) {
  const b = $("#all-" + r);
  if (!REF.includes(r)) { b.disabled = true; b.title = "no data yet"; continue; }
  b.addEventListener("click", () => {
    const on = b.getAttribute("aria-pressed") !== "true";
    AREAS.forEach(a => a.scales.forEach(s => { if (!s.na) { state[s.k] = state[s.k] || {}; state[s.k][r] = on; } }));
    AREAS.forEach(a => a.scales.forEach(renderScale)); syncAll();
  });
}

// calibration chart
const calOn = {};
function drawCal() {
  const W = 640, H = 340, m = { l: 46, r: 16, t: 10, b: 38 };
  const x = v => m.l + v * (W - m.l - m.r), y = v => H - m.b - v * (H - m.t - m.b);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Stated confidence against share right">`;
  for (const g of [0, .25, .5, .75, 1]) {
    s += `<line x1="${x(0)}" x2="${x(1)}" y1="${y(g)}" y2="${y(g)}" stroke="var(--line)"/><text x="${m.l - 8}" y="${y(g) + 4}" text-anchor="end">${g * 100}%</text>`;
    s += `<text x="${x(g)}" y="${H - m.b + 17}" text-anchor="middle">${g.toFixed(2)}</text>`;
  }
  s += `<line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="var(--muted)" stroke-dasharray="4 4"/>`;
  s += `<text x="${x(.5)}" y="${H - 3}" text-anchor="middle">stated confidence</text><text transform="translate(12 ${y(.5)}) rotate(-90)" text-anchor="middle">share right</text>`;
  const series = LOCAL.map(t => [t, D.models[t].reliability]);
  for (const r of REF) if (calOn[r]) series.push([r, D.refs[r].reliability]);
  for (const [t, rel] of series) {
    const pts = (rel || []).filter(b => b.n >= 2);
    if (pts.length > 1) s += `<polyline fill="none" stroke="${COL[t]}" stroke-width="2" points="${pts.map(b => `${x(b.conf)},${y(b.acc)}`).join(" ")}"/>`;
    for (const b of pts) s += `<g><title>${D.labels[t]}: ${b.n} passages stated ${P(b.conf)} sure, ${P(b.acc)} right</title>${mark(t, x(b.conf), y(b.acc), true)}</g>`;
  }
  $("#cal").innerHTML = s + "</svg>";
}
for (const r of ["opus", "sonnet"]) {
  const b = $("#cal-" + r);
  if (!REF.includes(r)) { b.disabled = true; b.title = "no data yet"; continue; }
  b.addEventListener("click", () => { calOn[r] = !calOn[r]; b.setAttribute("aria-pressed", calOn[r]); drawCal(); });
}
build(); drawCal();
$("#foot").textContent = D.foot || "";
</script>
"""


def main() -> None:
    data = collect()
    data["foot"] = ("Gold: two blind Opus 5.5 passes, 6 disagreements settled by a third. Opus and Sonnet values are the "
                    "mean of their two passes; a measure Claude cannot take (seed, memory, writing speed) has its "
                    "toggle switched off. Claude's seconds are wall time per item in Claude Code, including its own "
                    "checks, so they are not comparable with this laptop's hardware.")
    out = DATA / "bench-visualiser.html"
    rs = DATA / "review_scores.json"
    data["review"] = json.loads(rs.read_text()) if rs.exists() else None
    page = PAGE + (HERE / "review_view.html").read_text()
    out.write_text(page.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    print(out)


if __name__ == "__main__":
    main()
