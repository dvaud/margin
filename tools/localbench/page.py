"""The bench's results page: one self-contained HTML file built from data/report.json (+ data/findings.json)."""
from __future__ import annotations

import json
from pathlib import Path

PAGE = r"""<title>Local Model Bench</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* Layout: one reading column; a scorecard table that scrolls inside itself; two figures below it. */
:root {
  --bg: #f7f8f7; --surface: #ffffff; --fg: #17201e; --fg2: #4d5856; --muted: #75807e; --line: #dde3e1;
  --accent: #0f766e; --good: #15803d; --bad: #b42318; --warn: #a15c07;
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #6250d6; --ref: #8a9391;
  --seq0: #eef3f2; --seq1: #cfe3e0; --seq2: #9fcac4; --seq3: #5fa8a0; --seq4: #2b7f77; --seq5: #0d5650;
  --font-ui: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #141917; --surface: #1b2220; --fg: #e9eeec; --fg2: #b6c0bd; --muted: #8b9693; --line: #2e3836;
  --accent: #4fb3a9; --good: #4ade80; --bad: #f87171; --warn: #fbbf24;
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #9085e9; --ref: #7d8785;
  --seq0: #1f2826; --seq1: #1f4440; --seq2: #23615b; --seq3: #2f8279; --seq4: #4fb3a9; --seq5: #9be0d8;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #141917; --surface: #1b2220; --fg: #e9eeec; --fg2: #b6c0bd; --muted: #8b9693; --line: #2e3836;
  --accent: #4fb3a9; --good: #4ade80; --bad: #f87171; --warn: #fbbf24;
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #9085e9; --ref: #7d8785;
  --seq0: #1f2826; --seq1: #1f4440; --seq2: #23615b; --seq3: #2f8279; --seq4: #4fb3a9; --seq5: #9be0d8;
  color-scheme: dark; }
body { background: var(--bg); color: var(--fg); font: 15px/1.55 var(--font-ui); }
main { max-width: 980px; margin: 0 auto; padding-block: 32px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 40px; }
h1 { font: 600 2rem/1.15 var(--font-serif); margin: 0; text-wrap: balance; }
h2 { font: 600 1.3rem/1.25 var(--font-serif); margin: 0 0 6px; text-wrap: balance; }
h3 { font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 0; }
p { margin: 0; max-width: 68ch; }
.lede { color: var(--fg2); font-size: 1.05rem; }
.meta { color: var(--muted); font: .82rem var(--font-mono); display: flex; flex-wrap: wrap; gap: 4px 18px; }
section { display: grid; gap: 14px; min-width: 0; }
.findings { display: grid; gap: 10px; padding: 0; margin: 0; list-style: none; }
.findings li { padding: 12px 14px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; max-width: 72ch; }
.findings b { font-weight: 600; }
.scroll { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; font-size: .9rem; }
th, td { padding: 7px 12px; text-align: right; border-bottom: 1px solid var(--line); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; white-space: normal; min-width: 220px; }
thead th { font-weight: 600; vertical-align: bottom; position: sticky; top: 0; background: var(--surface); }
tr.group td { background: var(--bg); font-weight: 600; text-transform: uppercase; letter-spacing: .05em; font-size: .75rem; color: var(--fg2); }
td .hint { display: block; color: var(--muted); font-size: .78rem; white-space: normal; }
td.ref, th.ref { color: var(--muted); }
.key { display: inline-flex; align-items: center; gap: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex: none; }
.good { color: var(--good); } .bad { color: var(--bad); } .warn { color: var(--warn); }
figure { margin: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px; display: grid; gap: 10px; min-width: 0; }
figcaption { color: var(--fg2); font-size: .88rem; max-width: 72ch; }
svg text { fill: var(--fg2); font: 11px var(--font-ui); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: .85rem; color: var(--fg2); }
.tip { position: fixed; pointer-events: none; background: var(--fg); color: var(--bg); font-size: .8rem; padding: 6px 9px; border-radius: 6px; max-width: 320px; z-index: 5; }
.heat { display: grid; gap: 2px; font-size: .72rem; overflow-x: auto; }
.heat .row { display: grid; grid-template-columns: 48px 132px repeat(var(--n), minmax(56px, 1fr)); gap: 2px; align-items: stretch; }
.heat .cell { height: 22px; border-radius: 3px; display: grid; place-items: center; font-variant-numeric: tabular-nums; }
.heat .lab { color: var(--fg2); align-self: center; font-family: var(--font-mono); white-space: nowrap; }
.heat .head { color: var(--fg2); font-weight: 600; text-align: center; align-self: end; font-size: .72rem; line-height: 1.2; }
.ramp { display: flex; gap: 2px; align-items: center; font-size: .78rem; color: var(--fg2); flex-wrap: wrap; }
.ramp span.sw { width: 26px; height: 14px; border-radius: 3px; display: inline-block; }
details { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; }
details summary { cursor: pointer; font-weight: 600; }
details div { display: grid; gap: 10px; margin-top: 10px; color: var(--fg2); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
<main>
  <header style="display:grid;gap:10px">
    <h3>Margin · green hydrogen pilot</h3>
    <h1>Local Model Bench</h1>
    <p class="lede" id="lede"></p>
    <div class="meta" id="meta"></div>
  </header>
  <section><h2>What the runs show</h2><ul class="findings" id="findings"></ul></section>
  <section>
    <h2>Scorecard</h2>
    <p class="lede" style="font-size:.95rem">Each column is one model on the same 45 items. The grey Opus column is the
    reference. Its overconfidence numbers are circular, because the gold answers come from Opus.</p>
    <div class="scroll"><table id="score"></table></div>
  </section>
  <section>
    <h2>Does the stated confidence mean anything?</h2>
    <figure>
      <div class="legend" id="callegend"></div>
      <div id="cal"></div>
      <figcaption>Each point is a group of passages the model graded, placed by the confidence it stated (across) and by
      the share that gold also grades in the same direction (up). On the diagonal, a model's confidence is honest.
      Below it, the model is surer than it is right. Dot size shows how many passages are in the group.</figcaption>
    </figure>
  </section>
  <section>
    <h2>Item by item: right, and the same every time?</h2>
    <figure>
      <div class="ramp" id="ramp"></div>
      <div class="heat" id="heat"></div>
      <figcaption>Each row is one item; each cell is how many of a model's runs gave the gold status (the app's own
      settings, the same again, passages reshuffled, and four samples at temperature 0.7). Dark means right every time.
      Pale means wrong every time, so the model is sure but wrong. The middle shades mean the model changes its mind.
      Planted controls: <b>planted</b> (a paraphrase of the claim slipped into one passage), <b>flip</b> (the claim
      turned into its opposite) and <b>irrel</b> (passages from another goal).</figcaption>
    </figure>
  </section>
  <section>
    <h2>How it was measured</h2>
    <details><summary>Items, gold answers, runs and measures</summary><div id="method"></div></details>
  </section>
</main>
<div class="tip" id="tip" hidden></div>
<script>
const D = __DATA__;
const $ = s => document.querySelector(s);
const pct = v => v == null ? "–" : Math.round(v * 100) + "%";
const num = (v, d = 2) => v == null ? "–" : (+v).toFixed(d);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const models = D.order.filter(t => D.models[t]);
const locals = models.filter(t => !t.startsWith("opus"));
const colour = {}; locals.forEach((t, i) => colour[t] = `var(--s${i + 1})`);
const label = t => (D.labels && D.labels[t]) || t;

$("#lede").textContent = D.lede || "";
$("#meta").innerHTML = (D.meta || []).map(esc).map(s => `<span>${s}</span>`).join("");
$("#findings").innerHTML = (D.findings || []).map(f => `<li>${f}</li>`).join("") || "<li>Runs still going.</li>";
$("#method").innerHTML = (D.method || []).map(p => `<p>${p}</p>`).join("");

// scorecard
const rows = [
  ["Performance"],
  ["Right status", r => pct(r.status_acc), "supported, partly, contradicted or nothing, as gold says", "status_acc"],
  ["Right status, real items only", r => pct(r.status_acc_real), "the 30 items without a planted control"],
  ["…a model that always says “nothing”", r => pct(r.always_nothing_acc), "the bar a guesser clears for free"],
  ["Grounded or not (kappa)", r => num(r.grounded_kappa), "1 = agrees with gold beyond chance; 0 = chance"],
  ["Planted sentence found", r => pct((r.controls || {}).planted), "5 items"],
  ["Opposite claim seen as contradicted", r => pct((r.controls || {}).flip), "5 items"],
  ["Opposite claim still called supported", r => pct(r.flip_still_supported), "reading words, not meaning"],
  ["Unrelated passages left alone", r => pct((r.controls || {}).irrel), "5 items"],
  ["Gold passages found", r => pct(r.passage_recall), "at confidence 0.6 or more"],
  ["Overconfidence"],
  ["Mean stated confidence", r => pct(r.mean_conf), "over every passage it graded"],
  ["…of which gold agrees (same direction)", r => pct(r.grade_acc_lenient), ""],
  ["Grades that count (≥ 0.6): stated confidence", r => pct(r.counting_mean_conf), "what the app shows"],
  ["Grades that count: share right", r => pct(r.counting_precision), ""],
  ["Gap (stated − right)", r => r.counting_overconfidence == null ? "–" : (r.counting_overconfidence > 0 ? "+" : "") + Math.round(r.counting_overconfidence * 100) + " pts", "positive = surer than right"],
  ["Calibration error (ECE)", r => num(r.ece_lenient), "0 = honest confidence"],
  ["Passages graded that bear on nothing", r => r.false_positives_counting ?? "–", "confidence ≥ 0.6, over 45 items"],
  ["Reliability"],
  ["Same status, same settings again", r => pct(r.determinism), "temperature 0, seed 42 (the app)"],
  ["Same answer word for word", r => pct(r.identical_raw), ""],
  ["Same status, passages reshuffled", r => pct(r.order_stable), "a reader would not care about the order"],
  ["Same status in all runs", r => pct(r.all_runs_same), "app run + 4 samples at temperature 0.7"],
  ["Right when it never changes its mind", r => pct(r.acc_when_settled), ""],
  ["Right when it changes its mind", r => pct(r.acc_when_unsettled), ""],
  ["Right by majority of runs", r => pct(r.acc_majority_vote), "5 runs, the most frequent status"],
  ["Speed and hardware"],
  ["Seconds per task (median)", r => num(r.sec_median, 1), "a claim against 6 passages"],
  ["Seconds per task (slowest 10%)", r => num(r.sec_p90, 1), ""],
  ["Reading speed (tokens/s)", r => num(r.prompt_tok_s, 0), "the prompt"],
  ["Writing speed (tokens/s)", r => num(r.output_tok_s, 0), "the answer"],
  ["Memory while loaded (GB)", r => num(r.memory_gb, 1), "Ollama, 16k context"],
  ["Free memory, lowest (%)", r => r.mem_free_pct_min ?? "–", "macOS memory pressure"],
  ["Swap in use, highest (GB)", r => r.swap_mb_max == null ? "–" : (r.swap_mb_max / 1024).toFixed(1), ""],
  ["Answers usable first time", r => pct(r.usable), "valid JSON, every quote found"],
];
const head = `<thead><tr><th></th>${models.map(t => `<th class="${t.startsWith("opus") ? "ref" : ""}">${
  t.startsWith("opus") ? esc(label(t)) : `<span class="key"><span class="dot" style="background:${colour[t]}"></span>${esc(label(t))}</span>`}</th>`).join("")}</tr></thead>`;
$("#score").innerHTML = head + "<tbody>" + rows.map(row => row.length === 1
  ? `<tr class="group"><td colspan="${models.length + 1}">${row[0]}</td></tr>`
  : `<tr><td>${row[0]}${row[2] ? `<span class="hint">${row[2]}</span>` : ""}</td>${models.map(t =>
      `<td class="${t.startsWith("opus") ? "ref" : ""}">${row[1](D.models[t])}</td>`).join("")}</tr>`).join("") + "</tbody>";

// calibration chart
(function () {
  const W = 640, H = 360, m = {l: 48, r: 16, t: 12, b: 40};
  const x = v => m.l + v * (W - m.l - m.r), y = v => H - m.b - v * (H - m.t - m.b);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Stated confidence against share right">`;
  for (const g of [0, .25, .5, .75, 1]) {
    s += `<line x1="${x(0)}" x2="${x(1)}" y1="${y(g)}" y2="${y(g)}" stroke="var(--line)"/>`;
    s += `<text x="${m.l - 8}" y="${y(g) + 4}" text-anchor="end">${g * 100}%</text>`;
    s += `<text x="${x(g)}" y="${H - m.b + 18}" text-anchor="middle">${g.toFixed(2)}</text>`;
  }
  s += `<line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="var(--muted)" stroke-dasharray="4 4"/>`;
  s += `<text x="${x(.5)}" y="${H - 4}" text-anchor="middle">stated confidence</text>`;
  s += `<text transform="translate(12 ${y(.5)}) rotate(-90)" text-anchor="middle">share right</text>`;
  for (const t of locals) {
    const pts = (D.models[t].reliability_lenient || []).filter(b => b.n >= 2);
    if (pts.length > 1) s += `<polyline fill="none" stroke="${colour[t]}" stroke-width="2" points="${pts.map(b => `${x(b.conf)},${y(b.acc)}`).join(" ")}"/>`;
    for (const b of pts) s += `<circle cx="${x(b.conf)}" cy="${y(b.acc)}" r="${Math.min(11, 4 + Math.sqrt(b.n))}" fill="${colour[t]}" stroke="var(--surface)" stroke-width="2"
      data-tip="${esc(label(t))}: ${b.n} passages stated ${pct(b.conf)} sure; gold agrees on ${pct(b.acc)}"/>`;
  }
  $("#cal").innerHTML = s + "</svg>";
  $("#callegend").innerHTML = locals.map(t => `<span class="key"><span class="dot" style="background:${colour[t]}"></span>${esc(label(t))}</span>`).join("")
    + `<span class="key"><svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke="var(--muted)" stroke-dasharray="4 4"/></svg>honest confidence</span>`;
})();

// item heat grid
(function () {
  const H = D.heat; if (!H) return;
  const cols = H.models.filter(t => models.includes(t));
  const shade = (k, n) => n ? `var(--seq${Math.round(k / n * 5)})` : "var(--bg)";
  let s = `<div class="row" style="--n:${cols.length}"><span class="head">item</span><span class="head">kind · gold</span>${cols.map(t => `<span class="head">${esc(label(t))}</span>`).join("")}</div>`;
  for (const it of H.items) {
    s += `<div class="row" style="--n:${cols.length}"><span class="lab">${it.id}</span><span class="lab">${it.origin} · ${it.gold}</span>`;
    for (const t of cols) {
      const c = (it.cells || {})[t];
      if (!c) { s += `<span class="cell" style="background:var(--bg)">·</span>`; continue; }
      const dark = c.right / c.n > .55;
      s += `<span class="cell" tabindex="0" style="background:${shade(c.right, c.n)};color:${dark ? "var(--bg)" : "var(--fg)"}"
        data-tip="${esc(label(t))} on ${it.id} (${it.origin}, gold ${it.gold}): right in ${c.right} of ${c.n} runs. Answers: ${esc(c.statuses.join(", "))}">${c.right}/${c.n}</span>`;
    }
    s += `</div>`;
  }
  $("#heat").innerHTML = s;
  $("#ramp").innerHTML = "right in none of the runs " + [0,1,2,3,4,5].map(i => `<span class="sw" style="background:var(--seq${i})"></span>`).join("") + " right in every run";
})();

// tooltips
const tip = $("#tip");
const show = (e, el) => { tip.textContent = el.dataset.tip; tip.hidden = false;
  const r = el.getBoundingClientRect(); tip.style.left = Math.min(innerWidth - 330, Math.max(8, r.left)) + "px"; tip.style.top = (r.bottom + 6) + "px"; };
document.addEventListener("pointerover", e => { const el = e.target.closest("[data-tip]"); el ? show(e, el) : tip.hidden = true; });
document.addEventListener("focusin", e => { const el = e.target.closest("[data-tip]"); if (el) show(e, el); });
document.addEventListener("focusout", () => tip.hidden = true);
</script>
"""

SHORT = {"supported": "supp", "partially_supported": "partly", "contradicted": "contra", "unsupported": "nothing", None: "–"}


def build(data_dir: Path, out: Path) -> Path:
    rep = json.loads((data_dir / "report.json").read_text())
    extra = json.loads((data_dir / "findings.json").read_text()) if (data_dir / "findings.json").exists() else {}
    items = [json.loads(x) for x in (data_dir / "items.jsonl").read_text().splitlines() if x.strip()]
    gold = {g["id"]: g for g in (json.loads(x) for x in (data_dir / "gold.jsonl").read_text().splitlines() if x.strip())}
    order = extra.get("order") or sorted(rep["models"], key=lambda t: (not t.startswith("opus"), t))
    heat_models = [t for t in order if not t.startswith("opus")]
    rows = {}
    for t in heat_models:
        p = data_dir / "runs" / f"{t}.jsonl"
        if p.exists():
            for line in p.read_text().splitlines():
                r = json.loads(line)
                rows.setdefault(t, {}).setdefault(r["id"], []).append(r.get("status"))
    heat_items = []
    for it in sorted(items, key=lambda i: (i["origin"] != "real", i["origin"], gold[i["id"]]["status"] or "", i["id"])):
        g = gold[it["id"]]["status"]
        cells = {t: {"n": len(rows[t][it["id"]]), "right": sum(s == g for s in rows[t][it["id"]]),
                     "statuses": [SHORT.get(s, s) for s in rows[t][it["id"]]]}
                 for t in heat_models if it["id"] in rows.get(t, {})}
        heat_items.append({"id": it["id"], "origin": it["origin"], "gold": SHORT[g], "cells": cells})
    data = {"models": rep["models"], "order": order, "labels": extra.get("labels", {}), "lede": extra.get("lede"),
            "meta": extra.get("meta", []), "findings": extra.get("findings", []), "method": extra.get("method", []),
            "heat": {"models": heat_models, "items": heat_items}}
    for m in data["models"].values():
        m.pop("sessions", None)
        m.pop("confusion", None)
    out.write_text(PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    return out
