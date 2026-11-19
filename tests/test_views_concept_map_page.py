"""The concept map's page run in Node with tests/_views.py (0.19.0, D1; views/concept-map.js): the filters made once,
with a Code select only once a codebook is chosen; the legend of named groups and of lines; the lines as lists and a
pair's passages; and what the page says with no glossary, with nothing to draw and with few passages.

D1, the rest (the design's view test plan): (a) each kind of link ends in its own head, named in the legend; (b) every
group has a name, in the legend, on the map and in the Groups section under it, where it is renamed, used, kept and
asked of the AI (one request that only queues; nothing presses a Start); (c) the map downloads as a picture that
stands alone.
"""
from __future__ import annotations

import re

import pytest

from _views import needs_node, run_views

PROBE = r"""
const OPTIONS = { documents: [{ doc_id: "d1", title: "Repair report" }, { doc_id: "d2", title: "Interviews" }],
  themes: { run_id: "r1", themes: [{ theme_id: 1, name: "Community" }] },
  codebooks: [{ name: "sdg", title: "SDGs", codes: [{ code: "12.5", description: "Reduce waste" }, { code: "11.3", description: "" }] }], years: [2020, 2021] };
const G = (o) => ({ name_source: "concepts", name_id: null, model: null, quote: null, changed: null, naming_failed: null, ...o });
const MAP = { built: true, n: 60, filters: {}, nodes: [
    { id: "a", label: "repair", passages: 20, group: 1, x: 0.2, y: 0.3 }, { id: "b", label: "community", passages: 12, group: 1, x: 0.3, y: 0.45 },
    { id: "c", label: "waste", passages: 8, group: 11, x: 0.8, y: 0.2 }, { id: "e", label: "landfill", passages: 4, group: 12, x: 0.9, y: 0.6 },
    { id: "d", label: "café", passages: 3, group: 0, x: 0.6, y: 0.9 }],
  edges: [{ a: "a", b: "b", together: 6, pmi: 1.5 }], links: [{ a: "a", b: "c", types: [{ relation: "effect", source: "model" }, { relation: "related", source: "person" }] }],
  groups: [G({ group: 1, names: ["repair", "community"], size: 2, concepts: ["a", "b"], name: "Repair and community" }),
    G({ group: 11, names: ["waste"], size: 1, concepts: ["c"], name: "Waste" }), G({ group: 12, names: ["landfill"], size: 1, concepts: ["e"], name: "Landfill" })],
  names_elsewhere: [], can_name: { offered: true, why: null, reader: "claude" },
  passages: 120, concepts_in_scope: 40, links_off_map: 2 };
// the seven kinds, a node each pair, in one group so that every line is drawn
const KN = ["p", "q", "r", "s2", "t", "u", "v", "w", "x", "y", "z", "zz", "zy", "zx"].map((id, i) => ({ id, label: id, passages: 5, group: 2, x: (i % 7) / 7, y: i < 7 ? 0.1 : 0.9 }));
const L = (a, b, relation, source = "pattern") => ({ a, b, types: [{ relation, source }] });
const KINDS = { ...MAP, nodes: KN, edges: [{ a: "p", b: "w", together: 3, pmi: 1 }],
  links: [L("p", "q", "needs"), L("r", "s2", "needed_by"), L("t", "u", "clashes"), L("v", "w", "related"), L("x", "y", "shapes"),
    L("z", "zz", "effect"), L("zy", "zx", "narrower"), L("q", "r", "replaces")],
  groups: [G({ group: 2, names: [], size: 14, concepts: KN.map((n) => n.id), name: "Kinds" })] };
const EDGE = { a: { node: "a", label: "repair" }, b: { node: "b", label: "community" }, together: 6, pmi: 1.5, links: [],
  passages: [{ doc_id: "d1", title: "Repair report", text: "Repair brings the community together.", start: 40, page: 3 }] };
const BASE = "/api/projects/Study/concept-map";
async function page(t, map = MAP, query = {}) {
  t.state({ settings: { backend: "claude_code" }, version: "0.19.16" });
  t.answer(`GET ${BASE}/options`, OPTIONS);
  t.answer(`GET ${BASE}?*`, typeof map === "function" ? map : () => map);
  t.answer(`GET ${BASE}/edge?*`, EDGE);
  t.answer("GET /api/jobs", { jobs: [] });
  await t.render("views/concept-map.js", "renderConceptMap", [], query);
}
const maps = (t) => t.calls.filter((c) => c.path.startsWith(`${BASE}?`)).map((c) => c.path.slice(BASE.length + 1));
const fields = (t) => t.view.querySelectorAll(".cm-filters select").map((s) => labelOfField(t, s));
const labelOfField = (t, s) => { const l = s.closest("label") || s.parentNode; return t.text(l).split("\n")[0]; };
const aiCalls = (t) => t.calls.filter((c) => c.method !== "GET" && /name-groups|start|claude|local/.test(c.path)).map((c) => `${c.method} ${c.path}`);
const groupsSec = (t) => t.view.querySelector(".cm-groups-section");
const rowsOf = (t) => groupsSec(t).querySelectorAll(".cm-groups tbody tr").map((r) => t.text(r));

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
  return { facts: t.text(t.view.querySelector(".cm-facts")), keys: t.view.querySelectorAll(".cm-key").map((k) => t.allText(k).replace(/\s+/g, " ").replace(/ ,/g, ",").trim()),
    how: t.text(t.view.querySelector(".cm-how")),
    marks: t.view.querySelectorAll("a.cm-node").map((a) => a.getAttribute("aria-label")),
    titles: t.view.querySelectorAll("a.cm-node title").map((x) => x.textContent),
    rel: t.view.querySelectorAll(".cm-rel").map((x) => ({ text: x.textContent, hidden: x.getAttribute("data-hidden") })),
    heads: t.view.querySelectorAll(".cm-links .cm-pair").map((g) => g.querySelectorAll("path, circle").map((x) => x.getAttribute("class"))),
    markers: t.view.querySelectorAll("marker").length,
    gnames: t.view.querySelectorAll(".cm-gname").map((x) => x.textContent) };
});

await scenario("the seven kinds", async (t) => {
  await page(t, KINDS);
  const pair = (a, b) => t.view.querySelector(`.cm-links .cm-pair[data-a="${a}"][data-b="${b}"]`);
  const heads = (g) => g.querySelectorAll("g[transform]").map((x) => ({ cls: x.firstElementChild.getAttribute("class"), t: x.getAttribute("transform") }));
  const lineEnds = (g) => { const l = g.querySelector(".cm-link"); return [+l.getAttribute("x1"), +l.getAttribute("x2")]; };
  const out = {};
  for (const [a, b] of [["p", "q"], ["r", "s2"], ["t", "u"], ["v", "w"], ["x", "y"], ["z", "zz"], ["zy", "zx"], ["q", "r"]]) {
    const g = pair(a, b);
    out[`${a}-${b}`] = { heads: heads(g).map((x) => x.cls), title: g.querySelector(".cm-hit title").textContent };
  }
  // needs at b's end (its tip at b, the line's angle), needed_by at a's (turned round)
  out.needsAt = heads(pair("p", "q"))[0].t;
  out.neededByAt = heads(pair("r", "s2"))[0].t;
  out.lines = t.view.querySelectorAll('.cm-keys[aria-label="Lines"] .cm-key').map((k) => t.allText(k).replace(/\s+/g, " ").replace(/ ,/g, ",").trim());
  out.swatches = t.view.querySelectorAll('.cm-keys[aria-label="Lines"] svg.cm-key-line').length;
  out.how = t.text(t.view.querySelector(".cm-how"));
  await t.click("The lines as lists");
  out.links = t.view.querySelectorAll(".cm-link-list li").map((r) => t.text(r));
  return out;
});

await scenario("the lines as lists", async (t) => {
  await page(t);
  await t.click("The lines as lists");
  const fold = t.view.querySelector("details.section");
  const out = { headings: fold.querySelectorAll("h3").map((x) => t.text(x)),
    pairs: fold.querySelectorAll(".cm-pairs tbody tr").map((r) => t.text(r)),
    links: fold.querySelectorAll(".cm-link-list li").map((r) => t.text(r)) };
  await t.click("Show the passages", { within: fold.querySelector(".cm-pairs") });
  out.asked = t.calls.filter((c) => c.path.startsWith(`${BASE}/edge`)).map((c) => c.path);
  out.detail = t.text(t.view.querySelector(".cm-detail"));
  return out;
});

await scenario("no glossary", async (t) => {
  await page(t, { built: false, nodes: [], edges: [], links: [], groups: [] });
  return { text: t.text(t.view.querySelector(".cm-map")), filters: t.hidden(t.view.querySelector(".cm-filters")),
    downloads: t.hidden(t.view.querySelector(".cm-downloads")) };
});

await scenario("nothing to draw", async (t) => {
  await page(t, (_b, path) => ({ built: true, nodes: [], edges: [], links: [], groups: [], passages: 0, concepts_in_scope: 0 }));
  const plain = t.text(t.view.querySelector(".cm-map"));
  await t.type(t.view.querySelectorAll(".cm-filters select")[0], "d1");
  return { plain, filtered: t.text(t.view.querySelector(".cm-map")), downloads: t.hidden(t.view.querySelector(".cm-downloads")) };
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

// ---- (b) the names --------------------------------------------------------------------------------------------
const NAMED = { ...MAP, nodes: [...MAP.nodes, { id: "f", label: "tools", passages: 6, group: 2, x: 0.6, y: 0.3 }, { id: "g", label: "bikes", passages: 5, group: 2, x: 0.7, y: 0.35 },
    { id: "h", label: "chairs", passages: 5, group: 3, x: 0.4, y: 0.8 }, { id: "i", label: "lamps", passages: 4, group: 3, x: 0.45, y: 0.85 },
    { id: "j", label: "skills", passages: 4, group: 4, x: 0.1, y: 0.8 }, { id: "k", label: "time", passages: 3, group: 4, x: 0.15, y: 0.85 }],
  groups: [G({ group: 1, size: 2, concepts: ["a", "b"], name: "Mending together", name_source: "person", name_id: "n1" }),
    G({ group: 2, size: 2, concepts: ["f", "g"], name: "Tools for bikes", name_source: "ai_draft", name_id: "n2", model: "claude-haiku-5-5",
      quote: { quote: "we lend tools for bikes", doc_id: "d1", title: "Repair report", page: 4, start: 10 } }),
    G({ group: 3, size: 2, concepts: ["h", "i"], name: "Furniture", name_source: "ai", name_id: "n3", model: "claude-haiku-5-5",
      quote: { quote: "chairs and lamps come in", doc_id: "d2", title: "Interviews", page: 2, start: 5 },
      changed: { left: ["mortgage", "city centre"], joined: ["lamps"] } }),
    G({ group: 4, size: 2, concepts: ["j", "k"], name: "Skills and time" }),
    G({ group: 11, size: 1, concepts: ["c"], name: "Waste" }), G({ group: 12, size: 1, concepts: ["e"], name: "Landfill" })],
  names_elsewhere: [{ id: "n9", name: "Energy bills", name_source: "person", concepts: ["heating", "winter"], more: 0 }] };

await scenario("named groups", async (t) => {
  await page(t, NAMED);
  const sec = groupsSec(t);
  return { keys: t.view.querySelectorAll('.cm-keys[aria-label="Groups"] .cm-key').map((k) => t.allText(k).replace(/\s+/g, " ").replace(/ ,/g, ",").trim()),
    gnames: t.view.querySelectorAll(".cm-gname").map((x) => x.textContent),
    marks: t.view.querySelectorAll("a.cm-node").map((a) => a.getAttribute("aria-label")).slice(0, 2),
    head: t.text(sec.querySelector(".section-title")), lead: t.text(sec.querySelector(".cm-groups-lead")),
    ask: t.text(sec.querySelector(".cm-groups-ask")), aiLine: t.text(sec.querySelector(".ai-where")),
    askThenLine: !!(sec.querySelector(".ai-where") && sec.querySelector(".ai-where").previousSibling === sec.querySelector(".cm-groups-ask")),
    note: t.text(sec.querySelector(".cm-groups-note")),
    rows: rowsOf(t), kept: t.allText(sec.querySelector(".cm-groups-kept")).replace(/\s+/g, " ").trim(),
    ai: aiCalls(t), lists: t.text(t.view.querySelectorAll("details.section").pop()) };
});

await scenario("narrow map", async (t) => {
  t.layout(() => ({ clientWidth: 390 }));
  await page(t, NAMED);
  return t.view.querySelectorAll(".cm-gname").length;
});

await scenario("ask wordings", async (t) => {
  const words = [];
  for (const groups of [[G({ group: 1, size: 2, concepts: ["a", "b"], name: "x" })],
    [G({ group: 1, size: 2, concepts: ["a", "b"], name: "x", name_source: "ai" }), G({ group: 2, size: 2, concepts: ["f", "g"], name: "y" }), G({ group: 3, size: 2, concepts: ["h", "i"], name: "z" })],
    [G({ group: 1, size: 2, concepts: ["a", "b"], name: "x", name_source: "ai_draft", name_id: "n" })]]) {
    await page(t, { ...MAP, groups });
    words.push(t.text(groupsSec(t).querySelector(".cm-groups-ask")));
  }
  return words;
});

await scenario("name the groups", async (t) => {
  let jobState = "queued";
  t.answer(`POST ${BASE}/names`, { record: {} });
  t.answer(`POST ${BASE}/name-groups?*`, { job: { id: "jg", kind: "group-names" } });
  t.answer("GET /api/jobs/jg", () => ({ id: "jg", kind: "group-names", state: jobState, progress: { done: 0, total: 2 },
    result: jobState === "done" ? { named: 2, failed: 0, groups: 2, skipped: 0 } : null }));
  let named = false;
  await page(t, () => (named ? { ...MAP, groups: [G({ group: 1, size: 2, concepts: ["a", "b"], name: "Mending", name_source: "ai_draft", name_id: "n1", model: "m" }),
    G({ group: 11, size: 1, concepts: ["c"], name: "Rubbish", name_source: "ai_draft", name_id: "n2", model: "m" }), MAP.groups[2]] } : MAP));
  const drawnAsked = aiCalls(t).length;
  await t.click("Name the groups");
  const btn = groupsSec(t).querySelector(".cm-groups-ask button");
  const out = { drawnAsked, sent: t.calls.filter((c) => c.path.includes("name-groups")).map((c) => ({ path: c.path, body: c.body })),
    busy: btn.getAttribute("aria-busy"), panel: !!groupsSec(t).querySelector(".cm-groups-job .ab, .cm-groups-job [class*='ab-']"),
    help: t.text(groupsSec(t).querySelector(".cm-groups-job-help")) };
  out.pressedStart = t.calls.filter((c) => c.method === "POST" && /start|claude|local/.test(c.path)).map((c) => c.path);
  named = true; jobState = "done";
  await t.settle(5000);
  out.after = { panel: t.hidden(groupsSec(t).querySelector(".cm-groups-job")), note: t.text(groupsSec(t).querySelector(".cm-groups-note")),
    toasts: t.toasts(), busy: groupsSec(t).querySelector(".cm-groups-ask button").getAttribute("aria-busy") };
  await t.click("Use all 2 names");
  out.useAll = t.calls.filter((c) => c.path === `${BASE}/names`).map((c) => c.body);
  return out;
});

await scenario("use this name", async (t) => {
  let used = false;
  t.answer(`POST ${BASE}/names`, (body) => { used = body.action === "accept"; return { record: {} }; });
  await page(t, () => (used ? { ...NAMED, groups: NAMED.groups.map((g) => (g.group === 2 ? { ...g, name_source: "ai" } : g)) } : NAMED));
  await t.click("Use this name");
  const row = groupsSec(t).querySelectorAll(".cm-groups tbody tr")[1];
  return { sent: t.calls.filter((c) => c.path === `${BASE}/names`).map((c) => c.body), row: t.text(row), toasts: t.toasts(),
    focused: (t.focused() || {}).label };
});

await scenario("rename", async (t) => {
  t.answer(`POST ${BASE}/names`, { record: {} });
  await page(t, NAMED);
  await t.click("Rename the group “Mending together”");
  const d = t.dialog();
  const out = { title: t.text(d.querySelector("h2")), field: d.querySelector("input").value, text: t.text(d), buttons: t.buttons(d).map((b) => b.label) };
  await t.click("Cancel", { within: d });
  out.cancelSent = t.calls.filter((c) => c.path === `${BASE}/names`).length;
  await t.click("Rename the group “Skills and time”");
  out.plainButtons = t.buttons(t.dialog()).map((b) => b.label);
  await t.click("Cancel", { within: t.dialog() });
  await t.click("Rename the group “Mending together”");
  await t.type(t.dialog().querySelector("input"), "Repair cafés");
  await t.click("Save", { within: t.dialog() });
  out.sent = t.calls.filter((c) => c.path === `${BASE}/names`).map((c) => c.body);
  out.toasts = t.toasts();
  return out;
});

await scenario("keep the name", async (t) => {
  t.answer(`POST ${BASE}/names`, { record: {} });
  await page(t, NAMED);
  await t.click("Keep the name");
  return t.calls.filter((c) => c.path === `${BASE}/names`).map((c) => c.body.action);
});

await scenario("not named", async (t) => {
  t.answer(`POST ${BASE}/name-groups?*`, { job: { id: "jf" } });
  t.answer("GET /api/jobs/jf", { id: "jf", state: "running", progress: {} });
  const fail = { reason: "its quotes were not found word for word in the passages", model: "claude-haiku-5-5" };
  await page(t, { ...MAP, groups: [G({ ...MAP.groups[0], naming_failed: fail }), G({ ...MAP.groups[1], naming_failed: fail }), MAP.groups[2]] });
  const note = groupsSec(t).querySelector(".cm-groups-note");
  const out = { note: t.text(note), alert: note.getAttribute("role") };
  await t.click("Name them again", { within: note });
  out.sent = t.calls.filter((c) => c.path.includes("name-groups")).map((c) => c.body);
  return out;
});

// review: asked to name the groups again, the AI could not name two groups it had named before: the note says why
await scenario("not named again", async (t) => {
  const fail = { reason: "its quotes were not found word for word in the passages", model: "claude-haiku-5-5" };
  const ai = (g, name) => G({ ...g, name, name_source: "ai_draft", name_id: `n${g.group}`, model: "claude-haiku-5-5", naming_failed: fail });
  await page(t, { ...MAP, groups: [ai(MAP.groups[0], "Mending"), ai(MAP.groups[1], "Rubbish"), MAP.groups[2]] });
  return t.text(groupsSec(t).querySelector(".cm-groups-note"));
});

// review: Undo of Use this name sends back what it overwrote
await scenario("use this name and undo", async (t) => {
  const before = [{ name_id: "n2", name: "Tools for bikes", source: "ai_draft", n: 30 }];
  t.answer(`POST ${BASE}/names`, (body) => (body.action === "accept" ? { record: {}, before } : { record: {} }));
  await page(t, NAMED);
  await t.click("Use this name");
  await t.click("Undo");
  return t.calls.filter((c) => c.path === `${BASE}/names`).map((c) => c.body);
});

await scenario("no group", async (t) => {
  await page(t, { ...MAP, groups: [], nodes: MAP.nodes.map((n) => ({ ...n, group: 0 })), edges: [], links: [] });
  return { text: t.text(groupsSec(t)), table: !!groupsSec(t).querySelector("table"), button: !!groupsSec(t).querySelector("button") };
});

await scenario("no AI may read", async (t) => {
  await page(t, { ...MAP, can_name: { offered: false, why: "No AI may read these documents, so the groups can only be named by you.", reader: null } });
  const sec = groupsSec(t);
  return { why: t.text(sec.querySelector(".cm-groups-why")), ask: !!sec.querySelector(".cm-groups-ask"), aiLine: !!sec.querySelector(".ai-where") };
});

await scenario("forget a name", async (t) => {
  t.answer(`POST ${BASE}/names`, (body) => ({ record: body.action === "forget" ? { row: { name_id: "n9" } } : {} }));
  await page(t, NAMED);
  await t.click("1 name kept for a group that is not on this map");
  await t.click("Forget this name");
  const toast = t.toasts();
  const undo = document.querySelector("#toasts .toast-btn");
  undo.click();
  await t.settle();
  return { sent: t.calls.filter((c) => c.path === `${BASE}/names`).map((c) => c.body), toast };
});

// ---- (c) the picture -----------------------------------------------------------------------------------------
async function saved(t, map, query = {}) {
  const files = [];
  const realSave = URL.createObjectURL;
  URL.createObjectURL = (blob) => { files.push({ blob }); return "blob:x"; };
  const click = Element.prototype.click;
  Element.prototype.click = function () { if (this.getAttribute("download")) files[files.length - 1].name = this.getAttribute("download"); else click.call(this); };
  try {
    await page(t, map, query);
    const head = t.text(t.view.querySelector(".page-head"));
    await t.click("SVG");
    await t.settle(100);
    return { head, name: files[0] && files[0].name, text: files[0] ? await files[0].blob.text() : null };
  } finally { URL.createObjectURL = realSave; Element.prototype.click = click; }
}
await scenario("download plain", async (t) => saved(t, NAMED));
await scenario("download filtered", async (t) => saved(t, { ...KINDS, passages: 12, filters: { doc: ["d1"] } }, { doc: "d1", year_from: "2020" }));
// a stand-in for the browser's computed style that follows the page's rules for a group's name on the map: they come
// through the classes of the text's group (.cm-gname text, .cm-gname .cm-gdraft), as in views.css
await scenario("download keeps the look of the group names", async (t) => {
  const real = globalThis.getComputedStyle;
  const classes = (el) => { const out = []; for (let x = el; x && x.getAttribute; x = x.parentNode) out.push(...String(x.getAttribute("class") || "").split(/\s+/)); return out; };
  globalThis.getComputedStyle = (el) => {
    const cs = classes(el), tag = el.localName || el.tagName || "";
    const v = {};
    if (cs.includes("cm-gname") && /^(text|tspan)$/i.test(tag)) Object.assign(v, { "font-weight": "650", fill: "rgb(68, 64, 60)", stroke: "rgb(255, 253, 248)", "paint-order": "stroke", "font-size": "13px" });
    if (cs.includes("cm-gdraft")) Object.assign(v, { "font-weight": "400", fill: "rgb(120, 113, 108)" });
    return { getPropertyValue: (k) => v[k] || "", display: "block" };
  };
  try {
    const got = await saved(t, NAMED);
    const m = /<text[^>]*>Tools for bikes<tspan[^>]*>[^<]*<\/tspan><\/text>/.exec(got.text || "");
    return { text: m ? m[0] : null };
  } finally { globalThis.getComputedStyle = real; }
});

// ---- D1, the last part: names from a team, and the zoom -------------------------------------------------------------
const TEAM = { ...NAMED, groups: NAMED.groups.map((g) => (g.group === 1 ? { ...g, by: "Anna", named_at: "2026-11-12T09:00:00+00:00",
    also_named: [{ id: "f1", name: "Hybrid work", name_source: "person", by: "Ben", at: "2026-11-10T09:00:00+00:00" }] }
  : g.group === 3 ? { ...g, by: "Ben" } : g)) };
await scenario("team names", async (t) => {
  t.answer(`POST ${BASE}/names`, { record: {} });
  await page(t, TEAM);
  const out = { rows: rowsOf(t).slice(0, 3) };
  await t.click("Rename the group “Mending together”");
  const d = t.dialog();
  out.dialog = t.text(d.querySelector(".cm-also-list"));
  await t.click("Use “Hybrid work” as the new name", { within: d });
  out.field = d.querySelector("input").value;
  await t.click("Save", { within: d });
  out.sent = t.calls.filter((c) => c.path === `${BASE}/names`).map((c) => ({ action: c.body.action, name: c.body.name, name_id: c.body.name_id }));
  return out;
});

// review 5: the other name can be removed, with Undo
await scenario("remove the other name", async (t) => {
  t.answer(`POST ${BASE}/names`, (body) => ({ record: body.action === "forget" ? { row: { name_id: "f1" } } : {} }));
  await page(t, TEAM);
  await t.click("Remove the other name “Hybrid work”");
  const toast = t.toasts();
  document.querySelector("#toasts .toast-btn").click();
  await t.settle();
  return { sent: t.calls.filter((c) => c.path === `${BASE}/names`).map((c) => c.body), toast };
});

// review 8: a touch drag, then a press that is a click; a second finger never takes over a drag; two fingers pinch
await scenario("touch", async (t) => {
  await page(t, NAMED);
  const wrap = () => t.view.querySelector(".cm-svg-wrap");
  const vb = () => t.view.querySelector("svg.cm-svg").getAttribute("viewBox");
  const ev = (type, id, x, y) => { const e = new Event(type, { pointerId: id, clientX: x, clientY: y, button: 0 }); wrap().dispatchEvent(e); return e; };
  await t.click("Zoom in");
  const start = vb();
  ev("pointerdown", 1, 100, 100); ev("pointermove", 1, 160, 100); ev("pointerup", 1, 160, 100);   // a touch drag: no click
  const dragged = vb();
  // back to the whole map, then a press on a concept: it opens (before the fix the drag's mark stayed and ate it)
  await t.press("0", wrap());
  ev("pointerdown", 1, 10, 10); ev("pointerup", 1, 10, 10);
  const click = new Event("click", {});
  t.view.querySelector("a.cm-node").dispatchEvent(click);
  const clickAfterDrag = click.defaultPrevented;
  await t.click("Zoom in");
  // one finger drags; a second finger's moves alone do nothing to it
  const before = vb();
  ev("pointerdown", 1, 100, 100);
  ev("pointermove", 7, 400, 400);
  const hijack = vb();
  ev("pointerup", 1, 100, 100);
  // a pinch: two fingers going apart zoom in
  ev("pointerdown", 1, 100, 100); ev("pointerdown", 2, 200, 100);
  ev("pointermove", 2, 300, 100);
  const pinched = { vb: vb(), status: t.text(t.view.querySelector(".cm-zoom-status")) };
  ev("pointerup", 2, 300, 100); ev("pointerup", 1, 100, 100);
  return { start, dragged, clickAfterDrag, before, hijack, pinched };
});

await scenario("zoom", async (t) => {
  t.answer(`POST ${BASE}/names`, { record: {} });
  await page(t, NAMED);
  const svg = () => t.view.querySelector("svg.cm-svg");
  const wrap = () => t.view.querySelector(".cm-svg-wrap");
  const vb = () => svg().getAttribute("viewBox");
  const bar = () => t.view.querySelector(".cm-zoom");
  const state = () => ({ vb: vb(), status: t.text(bar().querySelector(".cm-zoom-status")),
    disabled: t.buttons(bar()).filter((b) => b.disabled).map((b) => b.label), font: svg().style.fontSize || "",
    zoomed: svg().getAttribute("data-zoomed"), near: svg().getAttribute("data-zoom") });
  const out = { bar: { role: bar().getAttribute("role"), label: bar().getAttribute("aria-label"), buttons: t.buttons(bar()).map((b) => b.label) },
    wrap: { tab: wrap().getAttribute("tabindex"), label: wrap().getAttribute("aria-label") }, start: state() };
  await t.click("Zoom in");
  out.in1 = state();
  wrap().focus();
  await t.press("+", wrap());
  out.in2 = state();
  await t.press("ArrowRight", wrap());
  out.right = vb();
  await t.press("+", wrap(), { ctrl: true });                 // the browser's own zoom: left alone
  out.ctrlPlus = vb();
  await t.press("0", wrap());
  out.fit = state();
  await t.press("-", wrap());
  out.outAtOne = vb();
  const plain = new Event("wheel", { deltaY: -100, clientX: 0, clientY: 0 });
  wrap().dispatchEvent(plain);
  out.plainWheel = { vb: vb(), prevented: plain.defaultPrevented };
  const pinch = new Event("wheel", { deltaY: -100, ctrlKey: true, clientX: 0, clientY: 0 });
  wrap().dispatchEvent(pinch);
  out.pinch = { vb: vb(), prevented: pinch.defaultPrevented };
  for (let i = 0; i < 8 && !t.find("Zoom in").disabled; i++) await t.click("Zoom in");
  out.max = state();
  // a rename draws the map again: the zoom stays
  await t.click("Rename the group “Mending together”");
  await t.type(t.dialog().querySelector("input"), "Repair cafés");
  await t.click("Save", { within: t.dialog() });
  out.afterRedraw = vb();
  return out;
});

await scenario("zoom and download", async (t) => {
  const files = [];
  const realSave = URL.createObjectURL;
  URL.createObjectURL = (blob) => { files.push({ blob }); return "blob:x"; };
  const click = Element.prototype.click;
  Element.prototype.click = function () { if (this.getAttribute("download")) files[files.length - 1].name = this.getAttribute("download"); else click.call(this); };
  try {
    await page(t, NAMED);
    await t.click("Zoom in");
    await t.click("Zoom in");
    await t.click("SVG");
    await t.settle(100);
    const text = files[0] ? await files[0].blob.text() : "";
    return { live: t.view.querySelector("svg.cm-svg").getAttribute("viewBox"), file: (/<svg[^>]*viewBox="([^"]*)"/i.exec(text) || [])[1] || null, head: text.slice(0, 300), n: files.length };
  } finally { URL.createObjectURL = realSave; Element.prototype.click = click; }
});

await scenario("zoom resets with other filters", async (t) => {
  await page(t);
  await t.click("Zoom in");
  const zoomed = t.view.querySelector("svg.cm-svg").getAttribute("viewBox");
  await t.type(t.view.querySelectorAll(".cm-filters select")[0], "d2");
  return { zoomed, after: t.view.querySelector("svg.cm-svg").getAttribute("viewBox") };
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
def test_the_legend_names_each_group_then_the_smallest_together_then_no_group_then_the_lines(page):
    """Plan 1 and 9: the groups by their names (no "Group 1"), the smallest together, then the lines: mentioned
    together, then only the kinds on this map, in KIND_ORDER, each with its hidden words."""
    keys = page["the legend"]["keys"]
    assert keys == ["Repair and community (filled circle) 2 concepts",
                    "The 2 smallest groups (grey star), drawn alike: Groups, under the map, names each.",
                    "In no group (grey dashed circle)",
                    "mentioned together more often than by chance (the thicker, the more)",
                    "leads to (a line that ends in a filled arrow)",
                    "is related to (a plain line)"]
    assert not any(k.startswith("Group 1") for k in keys)
    assert page["the legend"]["how"] == ("A darker line is a link of the glossary (one you accepted or added, one the AI is "
                                         "confident of, or an abbreviation); its end says what kind. Choose a concept to "
                                         "open it; choose a line to see the passages that join the two. Rename the groups "
                                         "under the map .")


@needs_node
def test_each_concept_on_the_map_is_a_link_that_says_its_passages_group_and_joins(page):
    """Plan 11: a concept's label names its group by its name."""
    assert page["the legend"]["marks"] == ["repair: 20 passages, in the group “Repair and community”, joined to 2 concepts",
                                           "community: 12 passages, in the group “Repair and community”, joined to 1 concept",
                                           "waste: 8 passages, in the group “Waste”, joined to 1 concept",
                                           "landfill: 4 passages, in the group “Landfill”", "café: 3 passages, in no group"]
    assert page["the legend"]["titles"][0] == "repair · 20 passages · Repair and community"


@needs_node
def test_a_pair_with_two_kinds_is_one_line_with_the_ends_of_its_first_kind_and_all_its_words(page):
    """Plan 5 and 6: no <marker>; leads to comes before is related to, so the line ends in a filled arrow, and its words
    name both, shown even without room."""
    lg = page["the legend"]
    assert lg["markers"] == 0
    assert lg["heads"] == [["cm-arrow"]]
    assert lg["rel"] == [{"text": "leads to · is related to", "hidden": None}]


@needs_node
def test_each_kind_of_link_ends_in_its_own_head(page):
    """Plan 2, 3, 4 and 7."""
    k = page["the seven kinds"]
    assert k["p-q"]["heads"] == ["cm-head-ring"] and k["r-s2"]["heads"] == ["cm-head-ring"]
    # needs: the ring at b's end (the line's own angle); needed_by: at a's end, turned round
    assert k["needsAt"].startswith("translate(") and "rotate(0.0)" in k["needsAt"]
    assert "rotate(180.0)" in k["neededByAt"]
    assert k["t-u"]["heads"] == ["cm-head-bar", "cm-head-bar"]
    assert k["v-w"]["heads"] == []
    assert k["x-y"]["heads"] == ["cm-head-open"] and k["z-zz"]["heads"] == ["cm-arrow"]
    assert k["zy-zx"]["heads"] == ["cm-head-diamond"] and k["q-r"]["heads"] == ["cm-head-cross"]
    assert k["p-q"]["title"] == "p needs q (found in the text, accepted)"
    assert k["r-s2"]["title"] == "s2 needs r (found in the text, accepted)"
    assert k["t-u"]["title"] == "t clashes with u (found in the text, accepted)"
    assert "p needs q · found in the text, accepted Show the passages" in k["links"]
    assert k["lines"] == ["mentioned together more often than by chance (the thicker, the more)",
                          "is part of (a line that ends in a diamond)", "leads to (a line that ends in a filled arrow)",
                          "shapes (a line that ends in an open arrow)", "needs (a line that ends in a ring)",
                          "is used instead of (a line that ends in a cross)", "clashes with (a line with a bar across each end)",
                          "is related to (a plain line)"]
    assert k["swatches"] == 8


@needs_node
def test_the_lines_as_lists_give_the_pairs_and_the_links(page):
    p = page["the lines as lists"]
    assert p["headings"] == ["Mentioned together", "Links"]
    assert p["pairs"] == ["repair and community\n6\n2.8\nShow the passages"]
    assert p["links"] == ["repair leads to waste · judged by the AI ; repair is related to waste · added or accepted by you Show the passages"]


@needs_node
def test_show_the_passages_opens_what_joins_a_pair(page):
    p = page["the lines as lists"]
    assert p["asked"] == ["/api/projects/Study/concept-map/edge?a=a&b=b"]
    assert p["detail"].startswith("repair and community\nMentioned together in 6 passages, 2.8 times as often as by chance.")
    assert "“Repair brings the community together.” Repair report, p. 3" in p["detail"]


@needs_node
def test_without_a_glossary_the_page_points_to_it_and_hides_the_filters_and_downloads(page):
    p = page["no glossary"]
    assert p["text"].startswith("No glossary yet")
    assert "Make the glossary on the Glossary tab" in p["text"]
    assert p["filters"] is True and p["downloads"] is True


@needs_node
def test_nothing_to_draw_says_whether_fewer_filters_would_help(page):
    p = page["nothing to draw"]
    assert p["plain"] == "Nothing to draw\nNo concept of the glossary is mentioned in two passages or more."
    assert p["filtered"] == ("Nothing to draw\nNo concept is mentioned in two passages or more within these filters. "
                             "Choose fewer filters.")
    assert p["downloads"] is True


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


# ---- (b) -------------------------------------------------------------------------------------------------------
@needs_node
def test_the_legend_marks_a_draft_and_a_changed_group(page):
    """Plan 9."""
    keys = page["named groups"]["keys"]
    assert keys[:4] == ["Mending together (filled circle) 2 concepts", "Tools for bikes (filled square) 2 concepts AI draft",
                        "Furniture (filled diamond) 2 concepts changed", "Skills and time (filled triangle) 2 concepts"]


@needs_node
def test_names_stand_on_a_wide_map_and_not_on_a_narrow_one(page):
    """Plan 10."""
    g = page["named groups"]["gnames"]
    assert "Mending together" in g and "Tools for bikes (AI draft)" in g
    assert page["narrow map"] == 0


@needs_node
def test_the_groups_section_says_where_each_name_comes_from(page):
    """Plan 12, 13, 18, 21: the four sources' tags, the ask button with Uses the AI and the AI line under its row, a
    changed group's sentence and Keep the name, and the names kept for groups not on this map."""
    n = page["named groups"]
    assert n["head"] == "Groups\n6 groups on this map"
    assert n["lead"].startswith("Each group is named by its two most central concepts until you rename it.")
    assert n["ask"] == "Name the other 3 groups Uses the AI" and n["askThenLine"] is True
    assert n["aiLine"] == "Claude, on your plan, reads a few passages of each group, where its concepts are mentioned together."
    assert n["note"] == ("1 name is the AI’s draft, and is marked so on the map and in a downloaded picture. Use it, or "
                         "rename it.")
    rows = n["rows"]
    assert rows[0].startswith("Mending together (filled circle)\nnamed by you\n") and rows[0].endswith("Rename")
    assert rows[1].startswith("Tools for bikes (filled square)\nAI draft\nWhat the AI’s name rests on") and "Use this name Rename" in rows[1]
    assert rows[2].startswith("Furniture (filled diamond)\nnamed by the AI, accepted by you changed since it was named\n"
                              "Since then 2 concepts left it (mortgage, city centre) and 1 joined (lamps).")
    assert "Keep the name Rename" in rows[2]
    assert rows[3].startswith("Skills and time (filled triangle)\nnamed by its concepts\n")
    assert rows[-1].startswith("In no group") and "Rename" not in rows[-1]
    assert n["kept"] == ("1 name kept for a group that is not on this map No group on this map holds most of their concepts. "
                         "A name comes back when its group does: with other filters, or when the documents change. "
                         "Energy bills heating, winter Forget this name")
    assert n["lists"].startswith("The lines as lists")


@needs_node
def test_drawing_the_page_asks_no_ai(page):
    """Plan 14, first half."""
    assert page["named groups"]["ai"] == []


@needs_node
def test_the_ask_button_has_three_wordings(page):
    """Plan 13."""
    assert page["ask wordings"] == ["Name the groups Uses the AI", "Name the other 2 groups Uses the AI",
                                    "Name the groups again Uses the AI"]


@needs_node
def test_naming_sends_one_request_presses_no_start_and_offers_the_drafts(page):
    """Plan 14 and 15: one request, which only queues; the button busy and the compact panel while it runs; then the
    panel goes and the note offers Use all 2 names, which sends the accept for each."""
    n = page["name the groups"]
    assert n["drawnAsked"] == 0
    assert n["sent"] == [{"path": "/api/projects/Study/concept-map/name-groups?", "body": {"which": "unnamed"}}]
    assert n["pressedStart"] == []
    assert n["busy"] == "true" and n["panel"] is True
    assert n["help"].startswith("The AI reads a few passages of each group and drafts a short name")
    a = n["after"]
    assert a["panel"] is True and a["busy"] is None
    assert a["note"] == ("2 names are the AI’s drafts, and are marked so on the map and in a downloaded picture. Use or "
                         "rename each one.\nUse all 2 names")
    assert any("The AI drafted names for 2 groups." in x for x in a["toasts"])
    assert n["useAll"][0]["action"] == "accept" and [x["name_id"] for x in n["useAll"][0]["items"]] == ["n1", "n2"]


@needs_node
def test_use_this_name_sends_the_accept_and_the_row_says_so(page):
    """Plan 16."""
    u = page["use this name"]
    assert u["sent"][0]["action"] == "accept" and u["sent"][0]["name_id"] == "n2" and u["sent"][0]["concepts"] == ["f", "g"]
    assert "named by the AI, accepted by you" in u["row"]
    assert any(x.startswith("Name used.") for x in u["toasts"])
    assert u["focused"] == "Rename the group “Tools for bikes”"


@needs_node
def test_the_rename_dialog(page):
    """Plan 17."""
    r = page["rename"]
    assert r["title"] == "Rename the group" and r["field"] == "Mending together"
    assert "Its concepts: repair, community" in r["text"]
    assert [b for b in r["buttons"] if b in ("Cancel", "Use its concepts as the name", "Save")] == ["Cancel", "Use its concepts as the name", "Save"]
    assert r["cancelSent"] == 0
    assert "Use its concepts as the name" not in r["plainButtons"]
    assert r["sent"] == [{"action": "rename", "name_id": "n1", "concepts": ["a", "b"], "labels": {"a": "repair", "b": "community"},
                          "filters": {}, "n": 60, "name": "Repair cafés"}]
    assert any(x.startswith("Group renamed.") for x in r["toasts"])


@needs_node
def test_keep_the_name(page):
    """Plan 18."""
    assert page["keep the name"] == ["keep"]


@needs_node
def test_groups_the_ai_could_not_name_say_why_with_name_them_again(page):
    """Plan 19."""
    n = page["not named"]
    assert n["note"].startswith("The AI (claude-haiku-5-5) could not name 2 groups after three tries: its quotes were not "
                                "found word for word in the passages. They keep the names made from their concepts. Name "
                                "them again, or rename them yourself.")
    assert n["alert"] is None and n["sent"] == [{"which": "unnamed"}]


@needs_node
def test_after_name_the_groups_again_the_note_says_the_groups_keep_the_ais_earlier_names(page):
    """Review: the toast's "the page says why" holds when the groups the AI could not name had AI names before."""
    assert page["not named again"].startswith(
        "The AI (claude-haiku-5-5) could not name 2 groups after three tries: its quotes were not found word for word in "
        "the passages. They keep the names the AI gave them before. Name them again, or rename them yourself.")


@needs_node
def test_undo_of_use_this_name_sends_back_what_it_overwrote(page):
    sent = page["use this name and undo"]
    assert [x["action"] for x in sent] == ["accept", "unaccept"]
    assert sent[1]["name_id"] == "n2"
    assert sent[1]["before"] == [{"name_id": "n2", "name": "Tools for bikes", "source": "ai_draft", "n": 30}]


@needs_node
def test_no_group_and_no_ai_may_read(page):
    """Plan 20."""
    g = page["no group"]
    assert g["text"] == "Groups\nNo two concepts on this map are mentioned together often enough to form a group."
    assert g["table"] is False and g["button"] is False
    a = page["no AI may read"]
    assert a["why"] == "No AI may read these documents, so the groups can only be named by you."
    assert a["ask"] is False and a["aiLine"] is False


@needs_node
def test_forget_a_name_and_undo(page):
    """Plan 21."""
    f = page["forget a name"]
    assert [x["action"] for x in f["sent"]] == ["forget", "restore"]
    assert f["sent"][1]["record"] == {"row": {"name_id": "n9"}}
    assert any(x.startswith("Forgotten.") for x in f["toast"])


# ---- (c) -------------------------------------------------------------------------------------------------------
@needs_node
def test_the_head_offers_the_picture_only_with_a_map(page):
    """Plan 22."""
    assert "Download the map PNG SVG" in page["download plain"]["head"]
    assert page["no glossary"]["downloads"] is True


@needs_node
def test_the_svg_is_named_for_the_project_and_the_day(page):
    """Plan 23."""
    assert re.fullmatch(r"study-concept-map-\d{4}-\d{2}-\d{2}\.svg", page["download plain"]["name"])
    assert re.fullmatch(r"study-concept-map-filtered-\d{4}-\d{2}-\d{2}\.svg", page["download filtered"]["name"])


@needs_node
def test_the_picture_stands_alone_and_says_what_it_is(page):
    """Plan 24 and 25."""
    t = page["download plain"]["text"]
    words = " ".join(re.sub(r"<[^>]+>", " ", t).split())
    assert t.startswith('<svg xmlns="http://www.w3.org/2000/svg"') and 'role="img"' in t
    assert "<title>Concept map of Study</title>" in t
    assert "<desc>The 11 of 40 concepts mentioned in the most passages, in 6 groups, counted in 120 passages." in t
    for name in ("Mending together", "Tools for bikes", "Furniture", "Skills and time", "The 2 smallest groups", "In no group"):
        assert name in words, name
    assert "Tools for bikes (AI draft)" in words
    assert "(AI draft): a name the AI drafted (claude-haiku-5-5), not yet checked by the researcher." in words
    assert "leads to" in words and "is related to" in words and "mentioned together more often than by chance" in words
    for bad in ("class=", "var(", "<a", "<marker", "data-"):
        assert bad not in t, bad
    assert "Counted only in" not in t and "Only 120" not in t
    assert "Made with Margin 0.19.16 on " in words
    f = " ".join(re.sub(r"<[^>]+>", " ", page["download filtered"]["text"]).split())
    assert "Counted only in: the document “Repair report” · documents published from 2020" in f
    assert "Only 12 passages are counted, so the lines rest on very little." in f
    for words in ("is part of", "shapes", "needs", "is used instead of", "clashes with"):
        assert words in f, words
    assert "(AI draft)" not in f
    assert "its end says what kind" in f


@needs_node
def test_the_picture_keeps_the_look_of_the_group_names_on_the_map(page):
    """Review: every element's computed look is read while the classes are still there (a group's name takes its rules
    through its group's class), and only then are the classes removed: strong, --text-2, with the paper's halo; the
    "(AI draft)" mark regular and muted."""
    t = page["download keeps the look of the group names"]["text"]
    assert t, "no group name in the picture"
    head, draft = re.match(r"<text([^>]*)>Tools for bikes<tspan([^>]*)>", t).groups()
    for k, v in (("font-weight", "650"), ("fill", "rgb(68, 64, 60)"), ("stroke", "rgb(255, 253, 248)"),
                 ("paint-order", "stroke"), ("font-size", "13px")):
        assert f'{k}="{v}"' in head, (k, head)
    # its own regular weight, though SVG's default: it would take the name's strong weight otherwise
    assert 'fill="rgb(120, 113, 108)"' in draft and 'font-weight="400"' in draft, draft
    assert "stroke=" not in draft and "font-size=" not in draft      # the same as its text's: inherited, not repeated


# ---- D1, the last part ------------------------------------------------------------------------------------------------
@needs_node
def test_a_name_from_the_team_says_who_gave_it_and_the_other_name_given(page):
    """Names travel with a team: a group named by a colleague says so, and the other name a person gave the same group
    stands under it and in the rename dialog, where one press puts it in the field."""
    r = page["team names"]
    assert r["rows"][0].startswith("Mending together (filled circle)\nnamed by Anna\nAlso named “Hybrid work” by Ben, 10 Nov 2026")
    assert "named by the AI, accepted by Ben" in r["rows"][2]
    assert r["dialog"].startswith("Also named “Hybrid work” by Ben, 10 Nov 2026") and "Use this one" in r["dialog"]
    assert r["field"] == "Hybrid work"
    assert r["sent"] == [{"action": "rename", "name": "Hybrid work", "name_id": "n1"}]


def _box(vb: str) -> list[float]:
    return [float(x) for x in vb.split()]


@needs_node
def test_the_map_zooms_by_its_buttons_keys_and_pinch_and_moves_when_zoomed_in(page):
    z = page["zoom"]
    assert z["bar"] == {"role": "toolbar", "label": "Zoom the map", "buttons": ["Zoom out", "Zoom in", "Whole map"]}
    assert z["wrap"]["tab"] == "0" and "Plus and minus zoom" in z["wrap"]["label"]
    s0 = z["start"]
    x0, y0, w0, h0 = _box(s0["vb"])
    assert (x0, y0) == (0, 0) and s0["status"] == "The whole map" and s0["disabled"] == ["Zoom out", "Whole map"]
    assert s0["font"] == "" and s0["zoomed"] is None
    _, _, w1, _ = _box(z["in1"]["vb"])
    assert abs(w1 - w0 / 1.5) < 0.2 and z["in1"]["status"] == "Zoomed in 150 %" and z["in1"]["disabled"] == []
    assert z["in1"]["zoomed"] == "true" and z["in1"]["near"] is None and z["in1"]["font"].startswith("calc(var(--fs-xs) / 1.22")
    _, _, w2, _ = _box(z["in2"]["vb"])                                   # + on the map
    assert abs(w2 - w0 / 2.25) < 0.2 and z["in2"]["near"] == "near"      # from twice the size on, every name shows
    assert _box(z["right"])[0] > _box(z["in2"]["vb"])[0]                  # the arrow keys move it
    assert z["ctrlPlus"] == z["right"]                                    # Ctrl + is the browser's
    assert z["fit"]["vb"] == s0["vb"] and z["fit"]["status"] == "The whole map" and z["fit"]["font"] == ""
    assert z["outAtOne"] == s0["vb"]
    assert z["plainWheel"] == {"vb": s0["vb"], "prevented": False}       # a plain wheel scrolls the page
    assert z["pinch"]["prevented"] is True and _box(z["pinch"]["vb"])[2] < w0
    assert z["max"]["status"] == "Zoomed in 400 %" and z["max"]["disabled"] == ["Zoom in"]
    assert abs(_box(z["max"]["vb"])[2] - w0 / 4) < 0.2
    assert z["afterRedraw"] == z["max"]["vb"]                            # a redraw keeps the zoom


@needs_node
def test_a_zoomed_map_still_downloads_whole(page):
    d = page["zoom and download"]
    assert _box(d["live"])[0:2] != [0, 0] or _box(d["live"])[2] < 1000
    assert d["file"] and _box(d["file"])[0:3] == [0, 0, 1200], (d["n"], d["head"])


@needs_node
def test_other_filters_show_the_whole_map_again(page):
    r = page["zoom resets with other filters"]
    assert _box(r["zoomed"])[2] < _box(r["after"])[2] and _box(r["after"])[0:2] == [0, 0]


@needs_node
def test_the_other_name_can_be_removed_with_undo(page):
    r = page["remove the other name"]
    assert r["sent"][0] == {"action": "forget", "name_id": "f1"}
    assert r["sent"][1] == {"action": "restore", "record": {"row": {"name_id": "f1"}}}
    assert any(x.startswith("The other name is removed.") for x in r["toast"])


@needs_node
def test_touch_a_drag_leaves_the_next_click_alone_one_finger_drags_and_two_pinch(page):
    r = page["touch"]
    assert _box(r["dragged"])[0] < _box(r["start"])[0]                    # dragged to the right: the view moved left
    assert r["clickAfterDrag"] is False                                   # a later press is a click again
    assert r["hijack"] == r["before"]                                     # another pointer does not move the drag
    assert _box(r["pinched"]["vb"])[2] < _box(r["start"])[2] and r["pinched"]["status"] == "Zoomed in 300 %"
