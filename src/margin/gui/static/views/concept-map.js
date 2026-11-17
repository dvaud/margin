// D1: the concept map, a view of Concepts (Glossary | Map). The concepts mentioned in the most passages, joined when
// the documents mention two together more often than by chance (PMI, not raw counts), in groups found from those
// joins, with the glossary's links (yours, the AI's confident ones, abbreviations) drawn in their type: the end of a
// link's line says its kind. Filters (documents, a theme, a code, years) narrow the passages counted. A concept opens
// its page; a line shows the passages that join its two concepts. D1, the rest: every group has a name (made from its
// two most central concepts, yours, or the AI's draft on request, marked until used), kept in the Groups section
// under the map; the map downloads as a picture (SVG or PNG), always light. The lines are given as lists under it
// (docs/DESIGN.md 8). Rules and layout: conceptmap.py, groupnames.py; routes: gui/api_corpus.py.
import { featureEyebrow, viewTabs } from "../features.js";
import { App, api, h, P, replace, clear, showError, failedLoad, noDocuments, addDocumentsFirst, fmt, pageHead, emptyState, plural, shortTitle, button, link, notice, card, select, field, fold, spinner,
  tag, input, dialog, toast, setBusy, aiButton, withAI, readsLine, aiWhere, watchJob, runningJob, jobFailed, downloadLinks, saveBlob } from "../lib.js";
import { MiniJob, isStopped, timeLeft } from "./progress.js";

const NS = "http://www.w3.org/2000/svg";
const ASPECT = 1.6;                        // conceptmap.ASPECT: the layout's width over its height
const FEW_PASSAGES = 30;                   // conceptmap.FEW_PASSAGES: under this, the lines rest on very little
// Groups 1 to 5: a filled shape each, in its colour; groups 6 to 10: the same five shapes outlined, in the same five
// colours; groups 11 and on (the smallest) share one mark, a grey star; a concept in no group is a grey dashed circle.
// So every mark differs from every other by its shape or its fill, never by colour alone.
const SHAPES = ["circle", "square", "diamond", "triangle", "hexagon"];
const OWN_MARKS = 10;                      // groups with a mark of their own
// a link as drawn: its kind, and whether it runs from a to b (false: from b to a)
const REL = { narrower: ["part", true], broader: ["part", false], effect: ["leads", true], effect_of: ["leads", false],
  replaces: ["replaces", true], replaced_by: ["replaces", false], related: ["related", true],
  needs: ["needs", true], needed_by: ["needs", false], shapes: ["shapes", true], shaped_by: ["shapes", false],
  clashes: ["clashes", true] };
const REL_WORDS = { part: "is part of", leads: "leads to", shapes: "shapes", needs: "needs",
  replaces: "is used instead of", clashes: "clashes with", related: "is related to" };
const KIND_ORDER = ["part", "leads", "shapes", "needs", "replaces", "clashes", "related"];   // the legend's order
// D1 rest: the end of a link's line says its kind (never a colour or a dash). kind -> [shape, how far the line stops
// before the tip]; a kind in BOTH_ENDS has its end at both ends
const HEAD = { part: ["diamond", 12], leads: ["arrow", 9], shapes: ["open", 1], needs: ["ring", 8],
  replaces: ["cross", 9], clashes: ["bar", 1], related: [null, 0] };
const BOTH_ENDS = new Set(["clashes"]);
const HEAD_WORDS = { part: "a line that ends in a diamond", leads: "a line that ends in a filled arrow",
  shapes: "a line that ends in an open arrow", needs: "a line that ends in a ring", replaces: "a line that ends in a cross",
  clashes: "a line with a bar across each end", related: "a plain line" };
const SOURCE_WORDS = { person: "added or accepted by you", meaning: "accepted by you", model: "judged by the AI",
  abbreviation: "an abbreviation in the documents", pattern: "found in the text, accepted" };
const NAMED_BY = { concepts: "named by its concepts", person: "named by you", ai: "named by the AI, accepted by you" };
const TOGETHER_WORDS = "mentioned together more often than by chance (the thicker, the more)";
const SIZES = [30, 60, 100, 150];
const FILTER_KEYS = ["doc", "theme", "framework", "code", "year_from", "year_to", "n"];
const EXPORT_W = 1200, EXPORT_PAD = 32;    // the downloaded picture: 1,200 units wide, the map laid out for 1,136

const conceptHref = (id) => `#/concepts/${encodeURIComponent(id)}`;
const docHref = (b) => `#/doc/${encodeURIComponent(b.doc_id)}?q=${b.start}-${b.start + 1}`;
const times = (pmi) => (2 ** pmi).toFixed(pmi < 3.33 ? 1 : 0);   // PMI in base 2 as "times as often as by chance"
const firstSix = (xs) => (xs.length > 6 ? `${xs.slice(0, 6).join(", ")} and ${xs.length - 6} more` : xs.join(", "));

// an SVG element (h() makes HTML ones)
function s(tag_, attrs = {}, ...kids) {
  const el = document.createElementNS(NS, tag_);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, String(v));
  }
  for (const c of kids.flat()) if (c !== null && c !== undefined && c !== false) el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}

// how a group's concepts are drawn: {key (the same for groups drawn alike), shape, fill, cls (a class of views.css, from
// the --group-* tokens), words (said to a screen reader and in the lists)}
export function groupMark(g) {
  if (!g) return { key: "none", shape: "circle", fill: "dashed", cls: "cm-none", words: "grey dashed circle" };
  if (g > OWN_MARKS) return { key: "other", shape: "star", fill: "filled", cls: "cm-other", words: "grey star" };
  const k = (g - 1) % SHAPES.length;
  const fill = g <= SHAPES.length ? "filled" : "outlined";
  return { key: `${fill} ${SHAPES[k]}`, shape: SHAPES[k], fill, cls: `${fill === "filled" ? "cm-g" : "cm-o"}${k + 1}`, words: `${fill} ${SHAPES[k]}` };
}

// a group's mark: its colour and fill (a class of views.css) and its shape
export function mark(g, x, y, r) {
  const gm = groupMark(g);
  const cls = `cm-mark ${gm.cls}`;
  const shape = gm.shape;
  if (shape === "star") return s("polygon", { class: cls, points: [...Array(10).keys()].map((i) => { const rr = r * (i % 2 ? 0.6 : 1.35), t = Math.PI / 5 * i - Math.PI / 2; return `${(x + rr * Math.cos(t)).toFixed(1)},${(y + rr * Math.sin(t)).toFixed(1)}`; }).join(" ") });
  if (shape === "square") { const a = r * 0.9; return s("rect", { class: cls, x: x - a, y: y - a, width: 2 * a, height: 2 * a, rx: 1.5 }); }
  const poly = (pts) => s("polygon", { class: cls, points: pts.map(([px, py]) => `${(x + px).toFixed(1)},${(y + py).toFixed(1)}`).join(" ") });
  if (shape === "diamond") return poly([[0, -r * 1.25], [r * 1.25, 0], [0, r * 1.25], [-r * 1.25, 0]]);
  if (shape === "triangle") return poly([[0, -r * 1.3], [r * 1.15, r * 0.75], [-r * 1.15, r * 0.75]]);
  if (shape === "hexagon") return poly([0, 1, 2, 3, 4, 5].map((i) => [r * 1.1 * Math.cos(Math.PI / 3 * i), r * 1.1 * Math.sin(Math.PI / 3 * i)]));
  return s("circle", { class: cls, cx: x, cy: y, r });
}
const swatch = (g) => s("svg", { class: "cm-swatch", viewBox: "0 0 16 16", width: 16, height: 16, "aria-hidden": "true" }, mark(g, 8, 8, 5));

// a link's head drawn as plain shapes, not a <marker> (the legend reuses it, and a drawing program keeps it): its tip
// at (x, y), pointing along `deg` (the line's angle; + 180 at the line's start)
export function headShape(shape, x, y, deg) {
  const g = s("g", { transform: `translate(${x.toFixed(1)},${y.toFixed(1)}) rotate(${deg.toFixed(1)})` });
  if (shape === "arrow") g.appendChild(s("path", { class: "cm-arrow", d: "M-12,-5 L0,0 L-12,5 z" }));
  else if (shape === "open") g.appendChild(s("path", { class: "cm-head-open", d: "M-9,-5 L0,0 L-9,5" }));
  else if (shape === "ring") g.appendChild(s("circle", { class: "cm-head-ring", cx: -4, cy: 0, r: 4 }));
  else if (shape === "bar") g.appendChild(s("path", { class: "cm-head-bar", d: "M-1,-6 L-1,6" }));
  else if (shape === "diamond") g.appendChild(s("path", { class: "cm-head-diamond", d: "M-12,0 L-6,-4.5 L0,0 L-6,4.5 z" }));
  else if (shape === "cross") g.appendChild(s("path", { class: "cm-head-cross", d: "M-8,-4.5 L-1,4.5 M-1,-4.5 L-8,4.5" }));
  return g;
}

// The types of a pair's link, each seen from its a: [{relation, source, kind, forward}] (two wordings joined into one
// concept, or two sources, can give one pair two types)
const linkTypes = (lk) => (lk.types && lk.types.length ? lk.types : lk.relation ? [lk] : [])
  .map((t) => { const [kind, forward] = REL[t.relation] || ["related", true]; return { ...t, kind, forward }; });
// the kind a pair's line shows at its ends: its first kind in KIND_ORDER (never a mix of two kinds' ends)
const firstKind = (types) => KIND_ORDER.map((k) => types.find((t) => t.kind === k)).find(Boolean) || null;
// which ends of a line of this type carry its head: {a, b}
function headEnds(t) {
  if (!t || !HEAD[t.kind][0]) return { a: false, b: false };
  if (BOTH_ENDS.has(t.kind)) return { a: true, b: true };
  return { a: !t.forward, b: !!t.forward };
}

// One link's line from (x1,y1) to (x2,y2) with the ends of its first kind: [line, heads…]. The line stops each head's
// distance before its tip, so no line shows through a hollow head; a line shorter than 16 draws no head.
export function linkLine(x1, y1, x2, y2, types, attrs = {}) {
  const dx = x2 - x1, dy = y2 - y1, d = Math.hypot(dx, dy) || 1, ux = dx / d, uy = dy / d;
  const deg = (Math.atan2(dy, dx) * 180) / Math.PI;
  const t = firstKind(types);
  const ends = d < 16 ? { a: false, b: false } : headEnds(t);
  const cut = t ? HEAD[t.kind][1] : 0;
  const cA = ends.a ? cut : 0, cB = ends.b ? cut : 0;
  const out = [s("line", { class: "cm-link", x1: (x1 + ux * cA).toFixed(1), y1: (y1 + uy * cA).toFixed(1), x2: (x2 - ux * cB).toFixed(1), y2: (y2 - uy * cB).toFixed(1), ...attrs })];
  if (ends.b) out.push(headShape(HEAD[t.kind][0], x2, y2, deg));
  if (ends.a) out.push(headShape(HEAD[t.kind][0], x1, y1, deg + 180));
  return out;
}

// the legend's swatch of a sort of line: "together" (mentioned together) or a kind of link
export function lineSwatch(kind) {
  const svg = s("svg", { class: "cm-key-line", viewBox: "0 0 36 14", width: 36, height: 14, "aria-hidden": "true" });
  if (kind === "together") svg.append(s("line", { class: "cm-edge", x1: 1, y1: 7, x2: 35, y2: 7, "stroke-width": 2.6 }));
  else svg.append(...linkLine(BOTH_ENDS.has(kind) ? 3 : 1, 7, 33, 7, [{ kind, forward: true }]));
  return svg;
}

// Marks that overlap on the page are pushed apart, a little at a time, in the marks' order and a fixed number of rounds
// (the same picture every time), and kept inside the picture: a small mark is never hidden under a larger one.
// marks: [{x, y, r}], moved in place.
const GOLDEN = Math.PI * (3 - Math.sqrt(5));
export function spreadMarks(marks, W, H, gap = 2, rounds = 40) {
  const keep = (A) => { A.x = Math.min(W - A.r - 2, Math.max(A.r + 2, A.x)); A.y = Math.min(H - A.r - 2, Math.max(A.r + 2, A.y)); };
  for (let k = 0; k < rounds; k++) {
    let moved = false;
    for (let i = 0; i < marks.length; i++) {
      for (let j = i + 1; j < marks.length; j++) {
        const A = marks[i], B = marks[j];
        let dx = B.x - A.x, dy = B.y - A.y, d = Math.hypot(dx, dy);
        const want = A.r + B.r + gap;
        if (d >= want) continue;
        if (d < 1e-6) { dx = Math.cos(j * GOLDEN); dy = Math.sin(j * GOLDEN); d = 1; }   // one on the other: a fixed way
        const push = (want - Math.min(d, want)) / 2;
        A.x -= dx / d * push; A.y -= dy / d * push;
        B.x += dx / d * push; B.y += dy / d * push;
        keep(A); keep(B);
        moved = true;
      }
    }
    if (!moved) break;
  }
  return marks;
}

// Where each concept's mark goes on a page `wrapW` wide: {W, H, marks: [{x, y, r}] in the nodes' order}. The map is
// laid out ASPECT times as wide as high; a narrow page turns it a quarter round when that makes it taller, and its
// height follows what it holds, so the groups stay round and no band is left empty. One concept, or concepts in one
// row, sit in the middle of a picture as tall as what is drawn. A narrow screen keeps the distances shorter, so its
// marks are smaller; marks that still overlap are pushed apart (spreadMarks). D1 rest: a wide map keeps 44 px at the top
// and the bottom, so a group's name fits over the top group and under the bottom one.
export function placeMarks(nodes, wrapW) {
  const narrow = wrapW < 600;
  const W = wrapW;
  const padX = narrow ? 24 : 56;
  const span = (k) => Math.max(...nodes.map((n) => n[k])) - Math.min(...nodes.map((n) => n[k]));
  const turn = narrow && span("x") * ASPECT > span("y");   // only when turning makes it taller
  const pts = nodes.map((n) => (turn ? [n.y, n.x * ASPECT] : [n.x * ASPECT, n.y]));
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), y0 = Math.min(...ys);
  const xr = Math.max(...xs) - x0, yr = Math.max(...ys) - y0;
  const padY = narrow || !yr ? 28 : 44;
  let scale = xr ? (W - 2 * padX) / xr : Infinity;
  const H = yr ? Math.round(Math.min(yr * scale + 2 * padY, W * (narrow ? 2.2 : 0.9))) : 2 * padY + 32;
  if (yr) scale = Math.min(scale, (H - 2 * padY) / yr);
  if (!Number.isFinite(scale)) scale = 0;
  const offX = (W - xr * scale) / 2, offY = (H - yr * scale) / 2;
  const maxP = Math.max(...nodes.map((n) => n.passages));
  const [r0, r1] = narrow ? [3, 6] : [4, 8];
  const marks = nodes.map((n, i) => ({ x: offX + (pts[i][0] - x0) * scale, y: offY + (pts[i][1] - y0) * scale, r: r0 + r1 * Math.sqrt(n.passages / maxP) }));
  return { W, H, marks: spreadMarks(marks, W, H) };
}

const LINKS_WORDS = "a link of the glossary (one you accepted or added, one the AI is confident of, or an abbreviation)";
const groupOf = (m, g) => (m.groups || []).find((x) => x.group === g) || null;
const groupName = (gr) => (gr && gr.name) || (gr ? `Group ${gr.group}` : "");

function passageItem(b) {
  return h("li", {}, h("span", { class: "serif" }, "“", shortTitle(b.text || b.quote || "", 260), "” "),
    b.doc_id ? link({ href: docHref(b), class: "small" }, `${b.title || "a document"}${b.location ? `, ${b.location}` : b.page ? `, p. ${b.page}` : ""}`) : null);
}

// The map drawn `wrapW` wide: {svg, unnamed (concepts drawn without their name), namesLeft (groups' names with no
// room)}. opts.interactive (the page): each concept a link, each line a hit line that calls opts.onEdge(a, b), the
// pointer dims what a concept is not joined to. Without it (the downloaded picture): no links, no hit lines, and a name
// with no room is left out rather than hidden. Group names stand on a map 600 px wide or more (opts.names !== false).
export function drawMap(m, wrapW, opts = {}) {
  const live = opts.interactive !== false;
  const { W, H, marks } = placeMarks(m.nodes, wrapW);
  const narrow = wrapW < 600;
  const maxPmi = Math.max(1, ...m.edges.map((e) => e.pmi));
  const at = {};
  m.nodes.forEach((n, i) => { at[n.id] = { ...marks[i], i, n }; });
  const taken = m.nodes.map((n) => { const A = at[n.id]; return [A.x - A.r - 1, A.y - A.r - 1, A.x + A.r + 1, A.y + A.r + 1]; });
  const free = (b, own) => b[0] >= 2 && b[2] <= W - 2 && b[1] >= 2 && b[3] <= H - 2 &&
    taken.every((t, k) => k === own || b[2] <= t[0] || b[0] >= t[2] || b[3] <= t[1] || b[1] >= t[3]);
  const near = {};   // node id -> set of ids joined to it
  const join = (a, b) => { (near[a] = near[a] || new Set()).add(b); (near[b] = near[b] || new Set()).add(a); };
  m.edges.forEach((e) => join(e.a, e.b));
  m.links.forEach((lk) => join(lk.a, lk.b));

  const svg = s("svg", { class: "cm-svg", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: live ? "group" : null,
    "aria-label": live ? `A map of ${plural(m.nodes.length, "concept")} in ${plural(m.groups.length, "group")}. The same map is given as lists below it.` : null });
  const edgesG = s("g", { class: "cm-edges" }), linksG = s("g", { class: "cm-links" }), nodesG = s("g", { class: "cm-nodes" }), namesG = s("g", { class: "cm-gnames" });
  svg.append(edgesG, linksG, nodesG, namesG);

  // the groups' names first, so the concepts' names go round them: over the group's marks, else under them; left out
  // when neither has room (the legend has it)
  let namesLeft = 0;
  if (!narrow && opts.names !== false) {
    for (const g of m.groups.filter((x) => x.group <= OWN_MARKS)) {
      const ms = m.nodes.filter((n) => n.group === g.group).map((n) => at[n.id]);
      if (!ms.length) continue;
      const x0 = Math.min(...ms.map((A) => A.x - A.r)), x1 = Math.max(...ms.map((A) => A.x + A.r));
      const y0 = Math.min(...ms.map((A) => A.y - A.r)), y1 = Math.max(...ms.map((A) => A.y + A.r));
      const text = shortTitle(groupName(g), 30), draft = g.name_source === "ai_draft" ? " (AI draft)" : "";
      const w = text.length * 7.3 + draft.length * 6.6 + 16, cx = Math.max(w / 2 + 4, Math.min(W - w / 2 - 4, (x0 + x1) / 2));
      const ways = [{ y: y0 - 12, box: [cx - w / 2, y0 - 26, cx + w / 2, y0 - 7] }, { y: y1 + 22, box: [cx - w / 2, y1 + 8, cx + w / 2, y1 + 27] }];
      const way = ways.find((c) => free(c.box, -1));
      if (!way) { namesLeft++; continue; }
      taken.push(way.box);
      namesG.appendChild(s("g", { class: "cm-gname", "aria-hidden": "true" }, mark(g.group, cx - w / 2 + 6, way.y - 4.5, 4.5),
        s("text", { x: (cx - w / 2 + 16).toFixed(1), y: way.y.toFixed(1) }, text, draft ? s("tspan", { class: "cm-gdraft" }, draft) : null)));
    }
  }
  // where each concept's name goes: beside its mark, else on its left, above or below it, wherever it overlaps no other
  // name and no mark; the concepts in the most passages first. A name with no room is hidden until its concept is
  // pointed at or focused. (Widths are guessed from the number of letters: no text is measured.)
  const labels = [];
  for (const n of m.nodes) {
    const A = at[n.id];
    const text = shortTitle(n.label, 28);
    const w = text.length * 6.6 + 2, hh = 13;
    const ways = [
      { x: A.x + A.r + 4, y: A.y + 4, anchor: "start", box: [A.x + A.r + 3, A.y - hh / 2 - 1, A.x + A.r + 4 + w, A.y + hh / 2 + 1] },
      { x: A.x - A.r - 4, y: A.y + 4, anchor: "end", box: [A.x - A.r - 4 - w, A.y - hh / 2 - 1, A.x - A.r - 3, A.y + hh / 2 + 1] },
      { x: A.x, y: A.y - A.r - 5, anchor: "middle", box: [A.x - w / 2, A.y - A.r - 4 - hh, A.x + w / 2, A.y - A.r - 2] },
      { x: A.x, y: A.y + A.r + 13, anchor: "middle", box: [A.x - w / 2, A.y + A.r + 2, A.x + w / 2, A.y + A.r + 4 + hh] },
    ];
    const way = ways.find((c) => free(c.box, A.i));
    if (way) taken.push(way.box);
    labels[A.i] = { ...(way || ways[0]), text, shown: !!way };
  }
  // room(box): whether a link's words fit there too (then they take it)
  const room = (b) => { if (!free(b, -1)) return false; taken.push(b); return true; };

  // a line from the edge of one mark to the edge of the other: 4 px clear at an end with a head, 2 at one without
  const ends = (a, b, gapA = 2, gapB = 2) => {
    const A = at[a], B = at[b];
    const dx = B.x - A.x, dy = B.y - A.y, d = Math.hypot(dx, dy) || 1;
    return { x1: A.x + dx / d * (A.r + gapA), y1: A.y + dy / d * (A.r + gapA), x2: B.x - dx / d * (B.r + gapB), y2: B.y - dy / d * (B.r + gapB) };
  };
  const linked = new Set(m.links.map((lk) => [lk.a, lk.b].sort().join("|")));
  for (const e of m.edges) {
    if (linked.has([e.a, e.b].sort().join("|"))) continue;   // the link is drawn instead, and says both
    const p = ends(e.a, e.b);
    const title = `${at[e.a].n.label} and ${at[e.b].n.label}: mentioned together in ${plural(e.together, "passage")}, ${times(e.pmi)} times as often as by chance`;
    edgesG.appendChild(s("g", { class: "cm-pair", "data-a": live ? e.a : null, "data-b": live ? e.b : null },
      s("line", { class: "cm-edge", ...p, "stroke-width": (0.8 + 2.7 * e.pmi / maxPmi).toFixed(2) }),
      live ? s("line", { class: "cm-hit", ...p, onClick: () => opts.onEdge && opts.onEdge(e.a, e.b) }, s("title", {}, title)) : s("title", {}, title)));
  }
  for (const lk of m.links) {
    // one line per pair, with the ends of its first kind and the words of every kind it has
    const types = linkTypes(lk);
    const he = headEnds(firstKind(types));
    const p = ends(lk.a, lk.b, he.a ? 4 : 2, he.b ? 4 : 2);
    const kinds = [...new Set(types.map((t) => t.kind))];
    const words = KIND_ORDER.filter((k) => kinds.includes(k)).map((k) => REL_WORDS[k]).join(" · ");
    const title = types.map((t) => { const [x, y] = t.forward ? [lk.a, lk.b] : [lk.b, lk.a]; return `${at[x].n.label} ${REL_WORDS[t.kind]} ${at[y].n.label} (${SOURCE_WORDS[t.source] || t.source})`; }).join("; ");
    const mx = (p.x1 + p.x2) / 2, my = (p.y1 + p.y2) / 2;
    // the words of a pair with two kinds are always shown: its ends tell only one of them
    const shown = room([mx - words.length * 3.1, my - 15, mx + words.length * 3.1, my - 1]) || kinds.length > 1;
    linksG.appendChild(s("g", { class: "cm-pair", "data-a": live ? lk.a : null, "data-b": live ? lk.b : null },
      ...linkLine(p.x1, p.y1, p.x2, p.y2, types),
      (shown || live) ? s("text", { class: "cm-rel", x: mx.toFixed(1), y: (my - 4).toFixed(1), "text-anchor": "middle", "data-hidden": shown ? null : "true" }, words) : null,
      live ? s("line", { class: "cm-hit", ...p, onClick: () => opts.onEdge && opts.onEdge(lk.a, lk.b) }, s("title", {}, title)) : s("title", {}, title)));
  }
  const focus = (id) => {
    if (!id) { delete svg.dataset.focus; svg.querySelectorAll("[data-near]").forEach((el) => el.removeAttribute("data-near")); return; }
    svg.dataset.focus = "true";
    const ns = near[id] || new Set();
    nodesG.querySelectorAll(".cm-node").forEach((el) => { if (el.dataset.id === id || ns.has(el.dataset.id)) el.dataset.near = "true"; else el.removeAttribute("data-near"); });
    svg.querySelectorAll(".cm-pair").forEach((el) => { if (el.dataset.a === id || el.dataset.b === id) el.dataset.near = "true"; else el.removeAttribute("data-near"); });
  };
  // the larger marks first, so a smaller one lies on top of any it still touches
  let unnamed = 0;
  for (const n of m.nodes) {
    const A = at[n.id];
    const gr = n.group ? groupOf(m, n.group) : null;
    const inWords = n.group ? `in the group “${groupName(gr)}”` : "in no group";
    const lab = labels[A.i];
    if (!lab.shown) unnamed++;
    const kids = [s("title", {}, `${n.label} · ${plural(n.passages, "passage")} · ${n.group ? groupName(gr) : "in no group"}`),
      mark(n.group, A.x, A.y, A.r),
      (lab.shown || live) ? s("text", { class: "cm-label", x: lab.x.toFixed(1), y: lab.y.toFixed(1), "text-anchor": lab.anchor, "data-hidden": lab.shown ? null : "true" }, lab.text) : null];
    if (!live) { nodesG.appendChild(s("g", { class: "cm-node" }, ...kids)); continue; }
    const a = s("a", { class: "cm-node", href: conceptHref(n.id), "data-id": n.id,
      "aria-label": `${n.label}: ${plural(n.passages, "passage")}, ${inWords}${(near[n.id] || new Set()).size ? `, joined to ${plural(near[n.id].size, "concept")}` : ""}` }, ...kids);
    a.addEventListener("mouseenter", () => focus(n.id));
    a.addEventListener("mouseleave", () => focus(null));
    a.addEventListener("focus", () => focus(n.id));
    a.addEventListener("blur", () => focus(null));
    nodesG.appendChild(a);
  }
  return { svg, W, H, unnamed, namesLeft };
}

// ---- the map as a picture (D1 rest, c) -------------------------------------------------------------------------------
// The file's name: <project>-concept-map[-filtered]-<year>-<month>-<day>.<ext>, the date as the computer's own day. The
// project's part: its name in lower case, every run of characters that is neither a letter nor a digit one "-", none at
// either end, at most 40 characters, "project" when nothing is left.
export function mapFileName(project, filtered, ext, when = new Date()) {
  const slug = String(project || "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "") || "project";
  const pad = (x) => String(x).padStart(2, "0");
  return `${slug}-concept-map${filtered ? "-filtered" : ""}-${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}.${ext}`;
}

// what each element of the picture keeps from the page's own rules, written on it
const STYLE_PROPS = ["fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "stroke-linejoin", "opacity",
  "paint-order"];
const TEXT_PROPS = ["font-family", "font-size", "font-weight", "text-anchor"];   // on text only
// SVG's own defaults: not written, so the file stays small
const SVG_DEFAULTS = { "stroke-dasharray": "none", "stroke-linecap": "butt", "stroke-linejoin": "miter", opacity: "1",
  "paint-order": "normal", "text-anchor": "start", "font-weight": "400" };
const esc = (v, attr) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(attr ? /"/g : /$^/, "&quot;");
// an SVG element as text, with no class (the picture stands alone: no stylesheet)
export function svgText(el) {
  const names = el.getAttributeNames ? el.getAttributeNames() : Object.keys(el.attributes || {});
  const attrs = names.filter((k) => k !== "class" && !k.startsWith("data-") && !k.startsWith("aria-")).map((k) => ` ${k}="${esc(el.getAttribute(k), true)}"`).join("");
  const kids = [...el.childNodes].map((c) => (c.nodeType === 3 ? esc(c.textContent) : c.nodeType === 1 ? svgText(c) : "")).join("");
  const tagName = el.localName || String(el.tagName).toLowerCase();
  return `<${tagName}${attrs}${kids ? `>${kids}</${tagName}>` : "/>"}`;
}

// lines of at most `n` letters, broken between words
function wrapWords(text, n) {
  const out = [];
  let line = "";
  for (const w of String(text).split(/\s+/).filter(Boolean)) {
    if (line && line.length + 1 + w.length > n) { out.push(line); line = w; } else line = line ? `${line} ${w}` : w;
  }
  if (line) out.push(line);
  return out;
}

// The downloaded picture as SVG text: a title, what was counted, the filters, the legend, the map, a foot. Always the
// light theme on --paper, whatever theme the app is in; every value written on its element, copied from what the
// page's own rules compute while the light theme is set (the colours still come from tokens.css). parts: {title,
// facts, filters, few, version, when}.
export function pictureSvg(m, parts) {
  const W = EXPORT_W, pad = EXPORT_PAD;
  const map = drawMap(m, W - 2 * pad, { interactive: false });
  const kinds = KIND_ORDER.filter((k) => m.links.some((lk) => linkTypes(lk).some((t) => t.kind === k)));
  const root = document.documentElement;
  const before = root.getAttribute("data-theme");
  const host = h("div", { class: "cm-export-host", "aria-hidden": "true", style: { position: "absolute", left: "-99999px", top: "0", width: `${W}px` } });
  document.body.appendChild(host);
  try {
    root.setAttribute("data-theme", "light");
    const css = getComputedStyle(root);
    const remPx = parseFloat(css.fontSize) || 16;
    // a token's value; a size in rem as pixels (a drawing program reads no rem)
    const tok = (k) => { const v = (css.getPropertyValue(k) || "").trim(); return /^[\d.]+rem$/.test(v) ? `${+(parseFloat(v) * remPx).toFixed(2)}px` : v; };
    const paper = tok("--paper");
    // the halo round every label and the fill of every hollow mark and head take the picture's ground
    if (paper) host.style.setProperty("--surface", paper);
    const font = (getComputedStyle(document.body).fontFamily || "").trim();
    const txt = (x, y, size, color, weight, ...kids) => s("text", { x, y, "font-size": tok(size) || null, fill: tok(color) || null, "font-weight": weight || null, "font-family": font || null }, ...kids);
    const top = s("g", {});
    let y = 54;
    top.append(txt(pad, y, "--fs-lead", "--text", tok("--fw-strong") || "600", parts.title));
    y += 30;
    for (const line of wrapWords(parts.facts, 170)) { top.append(txt(pad, y, "--fs-xs", "--text-2", null, line)); y += 18; }
    for (const extra of [parts.filters, parts.few].filter(Boolean)) for (const line of wrapWords(extra, 170)) { top.append(txt(pad, y, "--fs-xs", "--text-2", null, line)); y += 18; }
    // the groups, in three columns
    y += 14;
    const col = (W - 2 * pad) / 3;
    const own = m.groups.filter((g) => g.group <= OWN_MARKS), rest = m.groups.filter((g) => g.group > OWN_MARKS);
    const keys = own.map((g) => ({ g: g.group, name: groupName(g), draft: g.name_source === "ai_draft", count: plural(g.size, "concept") }));
    if (rest.length) keys.push({ g: rest[0].group, name: `The ${rest.length} smallest groups`, count: "drawn alike" });
    if (m.nodes.some((n) => !n.group)) keys.push({ g: 0, name: "In no group" });
    keys.forEach((k, i) => {
      const x = pad + (i % 3) * col, yy = y + Math.floor(i / 3) * 22;
      top.append(mark(k.g, x + 6, yy - 4, 5.5), txt(x + 18, yy, "--fs-small", "--text", null, shortTitle(k.name, 40),
        k.draft ? s("tspan", { fill: tok("--muted") || null }, " (AI draft)") : null, k.count ? s("tspan", { fill: tok("--muted") || null }, ` · ${k.count}`) : null));
    });
    y += Math.ceil(keys.length / 3) * 22 + 8;
    // the lines, on one row that wraps
    const lines = [...(m.edges.length ? [["together", TOGETHER_WORDS]] : []), ...kinds.map((k) => [k, REL_WORDS[k]])];
    let lx = pad;
    lines.forEach(([k, words]) => {
      const w = 36 + 8 + words.length * 6.4 + 22;
      if (lx + w > W - pad && lx > pad) { lx = pad; y += 22; }
      const g = s("g", { transform: `translate(${lx},${y - 11})` });
      if (k === "together") g.append(s("line", { class: "cm-edge", x1: 1, y1: 7, x2: 35, y2: 7, "stroke-width": 2.6 }));
      else g.append(...linkLine(BOTH_ENDS.has(k) ? 3 : 1, 7, 33, 7, [{ kind: k, forward: true }]));
      top.append(g, txt(lx + 44, y, "--fs-small", "--text", null, words));
      lx += w;
    });
    const mapY = y + (lines.length ? 22 : 0);
    const rule = (yy) => s("line", { x1: pad, y1: yy, x2: W - pad, y2: yy, stroke: tok("--border") || null, "stroke-width": 1 });
    const foot = [];
    if (kinds.length) foot.push("A darker line is a link of the glossary: accepted or added by the researcher, judged by the AI with confidence, or an abbreviation; its end says what kind.");
    const drafts = m.groups.filter((g) => g.name_source === "ai_draft");
    if (drafts.length) {
      const models = [...new Set(drafts.map((g) => g.model).filter(Boolean))];
      foot.push(`(AI draft): a name the AI drafted${models.length ? ` (${models.join(", ")})` : ""}, not yet checked by the researcher.`);
    }
    if (map.unnamed) foot.push(`${plural(map.unnamed, "concept")} ${map.unnamed === 1 ? "is" : "are"} drawn without ${map.unnamed === 1 ? "its" : "their"} name, for want of room.`);
    if (map.namesLeft) foot.push(`The ${map.namesLeft === 1 ? "name of 1 group is" : `names of ${map.namesLeft} groups are`} left out of the map for want of room; the legend has ${map.namesLeft === 1 ? "it" : "them"}.`);
    foot.push(`Made with Margin${parts.version ? ` ${parts.version}` : ""} on ${parts.when}.`);
    const footLines = wrapWords(foot.join(" "), 190);
    const footY = mapY + map.H + 28;
    const H = footY + footLines.length * 16 + 18;
    const pic = s("svg", { xmlns: NS, viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-labelledby": null },
      s("title", {}, parts.title), s("desc", {}, parts.facts),
      s("rect", { x: 0, y: 0, width: W, height: H, fill: paper || null }),
      top, rule(mapY - 6), s("g", { transform: `translate(${pad},${mapY})` }, ...[...map.svg.childNodes]), rule(footY - 18),
      footLines.map((line, i) => txt(pad, footY + i * 16, "--fs-xs", "--muted", null, line)));
    host.appendChild(pic);
    // every element takes what the page's rules compute for it, written on it; only then do the classes go, in a
    // second pass (a group's name on the map has no class of its own: its rules come through its group's, so a class
    // removed early would take its look with it)
    const all = [];
    const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
    walk(pic);
    // a tspan inherits from its text what is written on it, so it takes each value that differs from its text's (a
    // draft mark's regular weight inside a strong name), not only those that differ from SVG's defaults
    const looks = [];
    for (const el of all) {
      const tag = el.localName || el.tagName;
      if (/^(title|desc|g|svg)$/i.test(tag)) continue;
      const cs = getComputedStyle(el);
      const isText = /^(text|tspan)$/i.test(tag);
      const up = /^tspan$/i.test(tag) && el.parentNode ? getComputedStyle(el.parentNode) : null;
      for (const k of isText ? [...STYLE_PROPS, ...TEXT_PROPS] : STYLE_PROPS) {
        if (el.hasAttribute(k)) continue;
        const v = (cs.getPropertyValue(k) || "").trim();
        if (!v || v.includes("var(")) continue;
        if (up ? (up.getPropertyValue(k) || "").trim() !== v : SVG_DEFAULTS[k] !== v) looks.push([el, k, v]);
      }
    }
    for (const [el, k, v] of looks) el.setAttribute(k, v);
    for (const el of all) el.removeAttribute("class");
    return svgText(pic);
  } finally {
    if (before === null) root.removeAttribute("data-theme"); else root.setAttribute("data-theme", before);
    host.remove();
  }
}

// the picture drawn twice as large, as a PNG (2,400 pixels wide), in the page
async function pngOf(svgTextValue) {
  // a data: address (the page's own rules let pictures come from the app and from data: only)
  const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgTextValue)}`;
  {
    const img = new Image();
    await new Promise((ok, bad) => { img.onload = ok; img.onerror = () => bad(new Error("The picture could not be made.")); img.src = url; });
    const w = img.width || EXPORT_W, hh = img.height || EXPORT_W;
    const c = document.createElement("canvas");
    c.width = w * 2; c.height = hh * 2;
    const ctx = c.getContext("2d");
    ctx.scale(2, 2);
    ctx.drawImage(img, 0, 0, w, hh);
    return await new Promise((ok, bad) => c.toBlob((b) => (b ? ok(b) : bad(new Error("The picture could not be made."))), "image/png"));
  }
}

export async function renderConceptMap(view, params, query) {
  const project = App.project;
  const base = `/api/projects/${P(project)}`;
  // the downloads stand at the head's right, only while a map is drawn (D1 rest, c)
  const pngBtnHolder = h("span", { class: "cm-downloads", hidden: true });
  view.appendChild(pageHead("Concepts", { eyebrow: featureEyebrow("concepts"), sub: "The concepts the documents mention together more often than by chance, in groups, with the links between them.", actions: [pngBtnHolder] }));
  view.appendChild(viewTabs("concepts", "conceptmap"));
  if (noDocuments()) { view.appendChild(addDocumentsFirst("The concept map")); return; }

  const f = {};
  for (const k of FILTER_KEYS) if (query[k]) f[k] = String(query[k]);
  const filtersBox = h("div", { class: "cm-filters", role: "group", "aria-label": "What the map counts" });
  const factsBox = h("div");
  const loadBox = h("div", { "aria-live": "polite" });
  const mapBox = h("div", { class: "cm-map", "aria-busy": "false" });
  const detailBox = h("div", { "aria-live": "polite" });
  const groupsBox = h("div");
  const listBox = h("div");
  view.append(filtersBox, factsBox, loadBox, mapBox, detailBox, groupsBox, listBox);
  // the AI's work on the names: one box that stays through redraws of the Groups section
  const jobBox = h("div", { class: "cm-groups-job" });
  jobBox.hidden = true;
  const watchers = [];

  let opts;
  try { opts = await api("GET", `${base}/concept-map/options`); } catch (e) { failedLoad(mapBox, e); return; }

  // a filter whose value is not in this project (a link from another project) is dropped
  const docIds = new Set(opts.documents.map((d) => d.doc_id));
  if (f.doc && !f.doc.split(",").every((d) => docIds.has(d))) delete f.doc;
  const themeIds = new Set((opts.themes.themes || []).map((t) => `${opts.themes.run_id}:${t.theme_id}`));
  if (f.theme && !themeIds.has(f.theme)) delete f.theme;
  const fws = new Map(opts.codebooks.map((c) => [c.name, c]));
  if (f.framework && !fws.has(f.framework)) { delete f.framework; delete f.code; }

  function keepUrl() {
    const q = new URLSearchParams();
    for (const k of FILTER_KEYS) if (f[k]) q.set(k, f[k]);
    const qs = q.toString();
    history.replaceState(null, "", "#/concept-map" + (qs ? "?" + qs : ""));
  }
  const qs = () => { const q = new URLSearchParams(); for (const k of FILTER_KEYS) if (f[k]) q.set(k, f[k]); return q.toString(); };

  // ---- the filters: made once; a choice redraws the map, not the controls (a keyboard keeps its place in them), and
  // only the Code select is made again, when the codebook changes ----
  function opt(value, words, chosen) { return h("option", { value, selected: chosen }, words); }
  let codeField = null;
  function makeCodeField() {
    const cb = fws.get(f.framework);
    if (!cb) return null;
    const codeSel = select({}, opt("", "Choose a code", !f.code), cb.codes.map((c) => opt(c.code, shortTitle(c.description ? `${c.code} ${c.description}` : c.code, 60), f.code === c.code)));
    codeSel.addEventListener("change", onPick("code"));
    return field("Code", codeSel);
  }
  function onPick(key, extra) {
    return (e) => { const v = e.currentTarget.value; if (v) f[key] = v; else delete f[key]; if (extra) extra(v); keepUrl(); load(); };
  }
  function drawFilters() {
    clear(filtersBox);
    // a link may name several documents (?doc=a,b): the select says so rather than "All documents"
    const several = f.doc && f.doc.includes(",") ? opt(f.doc, `These ${f.doc.split(",").length} documents`, true) : null;
    const docSel = select({}, opt("", "All documents", !f.doc), several, opts.documents.map((d) => opt(d.doc_id, shortTitle(d.title || d.doc_id, 60), f.doc === d.doc_id)));
    docSel.addEventListener("change", onPick("doc"));
    filtersBox.appendChild(field("Documents", docSel));
    if (opts.themes.themes.length) {
      const thSel = select({}, opt("", "Every passage", !f.theme), opts.themes.themes.map((t) => opt(`${opts.themes.run_id}:${t.theme_id}`, shortTitle(t.name, 50), f.theme === `${opts.themes.run_id}:${t.theme_id}`)));
      thSel.addEventListener("change", onPick("theme"));
      filtersBox.appendChild(field("Theme", thSel));
    }
    if (opts.codebooks.length) {
      const cbSel = select({}, opt("", "No code", !f.framework), opts.codebooks.map((c) => opt(c.name, shortTitle(c.title, 40), f.framework === c.name)));
      const cbField = field("Codebook", cbSel);
      cbSel.addEventListener("change", onPick("framework", () => {
        delete f.code;
        if (codeField) codeField.remove();
        codeField = makeCodeField();
        if (codeField) cbField.after(codeField);
      }));
      filtersBox.appendChild(cbField);
      codeField = makeCodeField();
      if (codeField) filtersBox.appendChild(codeField);
    }
    if (opts.years.length) {
      const yFrom = select({}, opt("", "Any year", !f.year_from), opts.years.map((y) => opt(String(y), String(y), f.year_from === String(y))));
      yFrom.addEventListener("change", onPick("year_from"));
      const yTo = select({}, opt("", "Any year", !f.year_to), opts.years.map((y) => opt(String(y), String(y), f.year_to === String(y))));
      yTo.addEventListener("change", onPick("year_to"));
      filtersBox.append(field("Published from", yFrom), field("Published until", yTo));
    }
    const nSel = select({}, SIZES.map((n) => opt(String(n), `${n} concepts`, (Number(f.n) || 60) === n)));
    nSel.addEventListener("change", (e) => { f.n = e.currentTarget.value === "60" ? "" : e.currentTarget.value; if (!f.n) delete f.n; keepUrl(); load(); });
    filtersBox.appendChild(field("Concepts on the map", nSel));
  }

  // ---- the map ----
  let m = null;
  let seq = 0;
  let edgeSeq = 0;   // the latest line asked for: an older answer arriving late is dropped
  let lastWidth = 0;
  let refocus = null;   // after a change to a name: the row whose Rename takes the focus again (its first concept)
  // while a map is counted (seconds on a large project), a line says so and the map before it stays, dimmed
  let loadTimer = null;
  const loading = (on) => {
    clearTimeout(loadTimer);
    mapBox.setAttribute("aria-busy", on ? "true" : "false");
    for (const b of pngBtnHolder.querySelectorAll("button")) { b.disabled = !!on; b.title = on ? "The map is being drawn again." : b.dataset.title || ""; }
    if (!on) { clear(loadBox); return; }
    loadTimer = setTimeout(() => replace(loadBox, h("p", { class: "it muted cm-loading" }, spinner("Drawing the map"), m ? " Drawing the map again…" : " Drawing the map…")), 250);
  };
  async function load() {
    const my = ++seq;
    edgeSeq++;       // (a line of the previous map no longer applies)
    loading(true);
    let r;
    try { r = await api("GET", `${base}/concept-map?${qs()}`); }
    catch (e) { if (my === seq) { loading(false); failedLoad(mapBox, e); } return; }
    if (my !== seq) return;
    loading(false);
    m = r;
    clear(detailBox);
    draw();
  }

  const filtered = () => ["doc", "theme", "code", "year_from", "year_to"].some((k) => f[k]);
  const factsSentence = (withGroups) => `${m.nodes.length < m.concepts_in_scope ? `The ${m.nodes.length} of ${fmt.num(m.concepts_in_scope)} concepts mentioned in the most passages` : plural(m.nodes.length, "concept")}${withGroups ? `, in ${plural(m.groups.length, "group")}` : ""}, counted in ${plural(m.passages, "passage")}${filtered() ? " within these filters" : ""}. Theory and working documents are left out.`;
  function draw() {
    clear(factsBox); clear(mapBox); clear(listBox); clear(groupsBox);
    pngBtnHolder.hidden = true;
    if (!m.built) {
      filtersBox.hidden = true;
      mapBox.appendChild(emptyState("network", "No glossary yet", "The map is drawn from the glossary: the terms your documents use, grouped into concepts. Make the glossary first; it is made on this computer and nothing is sent anywhere.",
        link({ kind: "next", href: "#/concepts" }, "Make the glossary on the Glossary tab")));
      return;
    }
    filtersBox.hidden = false;
    if (!m.nodes.length) {
      mapBox.appendChild(emptyState("search-x", "Nothing to draw", filtered()
        ? "No concept is mentioned in two passages or more within these filters. Choose fewer filters."
        : "No concept of the glossary is mentioned in two passages or more."));
      return;
    }
    m.groups = m.groups || [];
    pngBtnHolder.hidden = false;
    factsBox.appendChild(h("p", { class: "muted small cm-facts" }, factsSentence(false),
      m.links_off_map ? ` ${plural(m.links_off_map, "link")} of the glossary ${m.links_off_map === 1 ? "joins" : "join"} a concept on the map to one that is not on it.` : ""));
    if (m.edges.length && m.passages < FEW_PASSAGES) {
      factsBox.appendChild(notice({ kind: "info", class: "cm-note" }, h("p", {}, `Only ${plural(m.passages, "passage")}${filtered() ? " within these filters" : ""} ${m.passages === 1 ? "is" : "are"} counted, so the lines rest on very little: two concepts that share two or three of them can look strongly joined by chance.`)));
    }
    if (!m.edges.length && !m.links.length) {
      factsBox.appendChild(notice({ kind: "info", class: "cm-note" }, h("p", {}, "No two of these concepts are mentioned together often enough to be joined (in two passages or more, more often than by chance).")));
    }
    mapBox.appendChild(card({ class: "section cm-card", "aria-label": "The concept map" }, legend(), h("div", { class: "cm-svg-wrap" }, svgMap())));
    drawGroups();
    drawLists();
    if (refocus) {
      const b = groupsBox.querySelector(`button[data-rename="${CSS.escape(refocus)}"]`) || groupsBox.querySelector(".cm-groups-ask button");
      refocus = null;
      if (b) b.focus();
    }
  }

  // the tags of where a name comes from (DESIGN 4.10): words, never colour alone
  const draftTag = (g) => tag({ icon: "sparkles", title: `Drafted by the AI${g.model ? ` (${g.model})` : ""}. It is a draft until you use it or rename it.` }, "AI draft");
  const sourceTag = (g) => (g.name_source === "ai_draft" ? draftTag(g) : tag({ icon: g.name_source === "concepts" ? null : "user" }, NAMED_BY[g.name_source] || NAMED_BY.concepts));

  function legend() {
    const kinds = KIND_ORDER.filter((k) => m.links.some((lk) => linkTypes(lk).some((t) => t.kind === k)));
    const own = m.groups.filter((g) => g.group <= OWN_MARKS), rest = m.groups.filter((g) => g.group > OWN_MARKS);
    const jump = m.groups.length ? link({ kind: "jump", onClick: () => { const hd = groupsBox.querySelector("#cm-groups-h"); if (hd) { hd.scrollIntoView({ block: "start", behavior: "smooth" }); hd.focus(); } } }, "Rename the groups under the map") : null;
    return h("div", { class: "cm-legend" },
      h("ul", { class: "cm-keys", "aria-label": "Groups" },
        own.map((g) => h("li", { class: "cm-key" }, swatch(g.group),
          h("span", {}, h("span", { class: "serif" }, groupName(g)), h("span", { class: "visually-hidden" }, ` (${groupMark(g.group).words})`),
            h("span", { class: "muted" }, ` ${plural(g.size, "concept")}`)),
          g.name_source === "ai_draft" ? draftTag(g) : null,
          g.changed ? tag({ kind: "attention", title: "This group changed since it was named: see Groups, under the map." }, "changed") : null)),
        rest.length ? h("li", { class: "cm-key" }, swatch(rest[0].group),
          h("span", {}, h("strong", {}, `The ${rest.length} smallest groups`), h("span", { class: "visually-hidden" }, ` (${groupMark(rest[0].group).words})`),
            h("span", { class: "muted" }, ", drawn alike: Groups, under the map, names each."))) : null,
        m.nodes.some((n) => !n.group) ? h("li", { class: "cm-key" }, swatch(0), h("span", { class: "muted" }, "In no group"), h("span", { class: "visually-hidden" }, ` (${groupMark(0).words})`)) : null),
      m.edges.length || kinds.length ? h("ul", { class: "cm-keys", "aria-label": "Lines" },
        m.edges.length ? h("li", { class: "cm-key" }, lineSwatch("together"), h("span", {}, TOGETHER_WORDS)) : null,
        kinds.map((k) => h("li", { class: "cm-key" }, lineSwatch(k), h("span", {}, REL_WORDS[k]), h("span", { class: "visually-hidden" }, ` (${HEAD_WORDS[k]})`)))) : null,
      h("p", { class: "muted small cm-how" }, kinds.length ? "A darker line is a link of the glossary (one you accepted or added, one the AI is confident of, or an abbreviation); its end says what kind. " : "",
        "Choose a concept to open it; choose a line to see the passages that join the two.", jump ? [" ", jump, "."] : null));
  }

  function svgMap() {
    const wrapW = Math.max(320, Math.min(1200, mapBox.clientWidth || view.clientWidth || 900));
    lastWidth = wrapW;
    return drawMap(m, wrapW, { onEdge: showEdge }).svg;
  }

  // ---- one line of the map: its link, how often together, the passages ----
  async function showEdge(a, b) {
    const q = new URLSearchParams(qs());
    q.set("a", a); q.set("b", b);
    const my = ++edgeSeq;
    let r;
    try { r = await api("GET", `${base}/concept-map/edge?${q}`); } catch (e) { if (my === edgeSeq) showError(e); return; }
    if (my !== edgeSeq) return;
    const A = link({ kind: "title", serif: true, href: conceptHref(r.a.node) }, r.a.label);
    const B = link({ kind: "title", serif: true, href: conceptHref(r.b.node) }, r.b.label);
    const linkLines = linkTypes({ types: r.links || (r.link ? [r.link] : []) }).map((t) => {
      const [x, y] = t.forward ? [r.a.label, r.b.label] : [r.b.label, r.a.label];
      return h("div", { class: "cm-detail-part" }, h("p", {}, h("strong", {}, `${x} ${REL_WORDS[t.kind]} ${y}`), h("span", { class: "muted" }, ` · ${SOURCE_WORDS[t.source] || t.source}`)),
        (t.sentences || []).length ? h("ul", { class: "ct-quotes" }, t.sentences.map(passageItem)) : null);
    });
    const together = r.together
      ? h("p", {}, `Mentioned together in ${plural(r.together, "passage")}${filtered() ? " within these filters" : ""}`, r.pmi !== null && r.pmi > 0 ? `, ${times(r.pmi)} times as often as by chance` : r.pmi !== null ? ", no more often than by chance" : "", ".")
      : h("p", { class: "muted" }, `No passage${filtered() ? " within these filters" : ""} mentions both.`);
    replace(detailBox, card({ class: "section cm-detail", title: h("span", {}, A, " and ", B), titleId: "cm-detail-h", level: "h2" },
      linkLines, together,
      r.passages.length ? h("ul", { class: "ct-quotes" }, r.passages.map(passageItem)) : null,
      r.together > r.passages.length ? h("p", { class: "muted small" }, `The first ${r.passages.length} of ${r.together}, by document.`) : null));
    detailBox.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  // ---- the groups and their names (D1 rest, b) ----
  const nodeOf = () => Object.fromEntries(m.nodes.map((n) => [n.id, n]));
  const groupBody = (g, extra = {}) => {
    const by = nodeOf();
    return { name_id: g.name_id, concepts: g.concepts || [], labels: Object.fromEntries((g.concepts || []).map((t) => [t, (by[t] || {}).label || t])), filters: m.filters || {}, n: m.n, ...extra };
  };
  async function names(body) { return api("POST", `${base}/concept-map/names`, body); }
  async function act(body, words, opts2 = {}) {
    refocus = opts2.refocus || null;
    let r;
    try { r = await names(body); } catch (e) { showError(e); refocus = null; return null; }
    toast(words, "ok", { small: true, ...(opts2.undo ? { button: { text: "Undo", onClick: async () => { try { await names(opts2.undo(r)); toast("Undone.", "ok", { small: true, ttl: 2500 }); await load(); } catch (e) { showError(e); } } } } : {}) });
    await load();
    return r;
  }
  async function rename(g) {
    const nameIn = input({ value: groupName(g), maxlength: 60 });
    const by = nodeOf();
    const labs = (g.concepts || []).map((t) => by[t]).filter(Boolean).sort((a, b) => b.passages - a.passages).map((n) => n.label);
    const actions = [{ text: "Cancel", value: null }];
    if (g.name_source !== "concepts") actions.push({ text: "Use its concepts as the name", value: "" });
    actions.push({ text: "Save", value: "save", primary: true });
    const r = await dialog({ title: "Rename the group",
      body: h("div", {}, h("label", { class: "field" }, h("span", { class: "field-label" }, "New name"), nameIn),
        labs.length ? h("p", { class: "muted small" }, `Its concepts: ${firstSix(labs)}`) : null),
      actions, onOpen: () => { nameIn.select(); nameIn.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); nameIn.closest("dialog").querySelector(".btn-primary").click(); } }); } });
    const back = () => { const b = groupsBox.querySelector(`button[data-rename="${CSS.escape((g.concepts || [""])[0])}"]`); if (b) b.focus(); };
    if (r === null || r === undefined) { back(); return; }
    if (r === "") { await act({ action: "use_concepts", name_id: g.name_id, concepts: g.concepts || [] }, "The group is named by its concepts again.", { refocus: (g.concepts || [])[0] }); return; }
    const name = nameIn.value.trim();
    if (!name || name === g.name) { back(); return; }
    await act({ action: "rename", ...groupBody(g, { name }) }, "Group renamed.", { refocus: (g.concepts || [])[0] });
  }

  let naming = null;   // the job of the AI that names the groups, while it runs
  function askWords() {
    const anyAI = m.groups.some((g) => g.name_source === "ai" || g.name_source === "ai_draft");
    const byConcepts = m.groups.filter((g) => g.name_source === "concepts").length;
    if (!anyAI) return ["Name the groups", "unnamed"];
    if (byConcepts) return [`Name the other ${plural(byConcepts, "group")}`, "unnamed"];
    return ["Name the groups again", "again"];
  }
  async function askNames(btn, which) {
    setBusy(btn, true);
    let r;
    try { r = await api("POST", `${base}/concept-map/name-groups?${qs()}`, { which }); }
    catch (e) { showError(e); setBusy(btn, false); return; }
    followNames(r.job.id);
  }
  function followNames(jobId) {
    const mj = new MiniJob({ title: "The AI names the groups", noun: "group" });
    naming = jobId;
    jobBox.hidden = false;
    replace(jobBox, mj.el, h("p", { class: "muted small cm-groups-job-help" }, "The AI reads a few passages of each group and drafts a short name, with a quote that is checked against the passage. Names you gave yourself are kept. Each name is a draft until you use it or rename it."));
    for (const b of groupsBox.querySelectorAll(".cm-groups-ask button, .cm-groups-note button")) setBusy(b, true);
    let lastAt = 0, atSecs = 0;
    const w = watchJob(jobId, (job) => {
      mj.update(job);
      const p = job.progress || {};
      // the count while the AI works (not while the work waits for a Start or its turn)
      if (p.total && !mj.waiting && (job.state === "running" || job.state === "queued") && mj.elapsed) {
        const at = Math.min(p.done || 0, p.total);
        if (at !== lastAt) { lastAt = at; atSecs = job.seconds || 0; }
        const left = timeLeft(atSecs, Math.max(0, at - 1), p.total, (job.seconds || 0) - atSecs);
        mj.elapsed.textContent = `group ${at} of ${p.total}${left ? ` · ${left}` : ""} · ${mj.elapsed.textContent}`;
      }
    });
    watchers.push(w);
    w.promise.then(async (job) => {
      naming = null;
      clear(jobBox);
      jobBox.hidden = true;
      if (job.state === "error") jobFailed(job, (j) => followNames(j.id), jobBox);
      else if (isStopped(job) || job.state !== "done") toast("Stopped. The names drafted so far are kept.", "info", { small: true });
      else {
        const res = job.result || {};
        const skipped = res.skipped ? ` ${plural(res.skipped, "group")} ${res.skipped === 1 ? "has" : "have"} no passage the AI may read, so ${res.skipped === 1 ? "it keeps its name" : "they keep their names"}.` : "";
        if (res.failed) toast(`The AI drafted names for ${plural(res.named || 0, "group")}; ${res.failed} could not be named: the page says why.${skipped}`, "warn");
        else if (!res.groups) toast(`There was no group for the AI to name: names you gave yourself are kept.${skipped}`, "info");
        else toast(`The AI drafted names for ${plural(res.named || 0, "group")}.${skipped}`, "ok");
      }
      await load();
    }).catch(showError);
  }

  // the groups the AI could not name (it stays until they are named or renamed); its Name them again stands under the
  // Groups section's AI line (drawGroups)
  // what the groups the AI could not name are called meanwhile: the name made from their concepts, or (asked to name
  // them again) the name the AI drafted before
  function keeps(failed) {
    const one = failed.length === 1;
    const byConcepts = failed.every((g) => g.name_source === "concepts");
    const byAI = failed.every((g) => g.name_source === "ai" || g.name_source === "ai_draft");
    const what = byConcepts ? (one ? "It keeps the name made from its concepts." : "They keep the names made from their concepts.")
      : byAI ? (one ? "It keeps the name the AI gave it before." : "They keep the names the AI gave them before.")
        : (one ? "It keeps the name it had." : "They keep the names they had.");
    return `${what} ${one ? "Name it again, or rename it yourself." : "Name them again, or rename them yourself."}`;
  }
  function failedNote(failed, can) {
    const why = failed[0].naming_failed;
    const again = aiButton({ sm: true, onClick: (e) => askNames(e.currentTarget, "unnamed") }, "Name them again");
    if (naming) setBusy(again, true);
    return notice({ kind: "error", live: false, class: "cm-groups-note" },
      h("p", {}, `The AI${why.model ? ` (${why.model})` : ""} could not name ${plural(failed.length, "group")} after three tries: ${why.reason}. ${keeps(failed)}`),
      can.offered ? h("div", { class: "btn-row" }, withAI(again)) : null);
  }

  function drawGroups() {
    const head = h("div", { class: "section-title" }, h("h2", { id: "cm-groups-h", tabindex: "-1" }, "Groups"),
      m.groups.length ? h("span", { class: "muted" }, `${plural(m.groups.length, "group")} on this map`) : null);
    const section = h("section", { class: "section cm-groups-section", "aria-labelledby": "cm-groups-h" }, head);
    groupsBox.appendChild(section);
    if (!m.groups.length) {
      section.appendChild(h("p", { class: "muted cm-groups-lead" }, "No two concepts on this map are mentioned together often enough to form a group."));
      return;
    }
    section.appendChild(h("p", { class: "muted cm-groups-lead" }, "Each group is named by its two most central concepts until you rename it. A name stays with its group between visits, and when the groups are found again, as long as the group still holds most of the same concepts."));
    const can = m.can_name || { offered: false };
    if (can.offered) {
      const [words, which] = askWords();
      const ask = aiButton({ sm: true, onClick: (e) => askNames(e.currentTarget, which) }, words);
      if (naming) setBusy(ask, true);
      section.append(h("div", { class: "btn-row cm-groups-ask" }, withAI(ask)),
        can.reader === "local" ? aiWhere("The AI on this computer reads a few passages of each group: the text never leaves it.", "local")
          : readsLine("a few passages of each group, where its concepts are mentioned together"));
    } else if (can.why) section.appendChild(h("p", { class: "muted small cm-groups-why" }, can.why));
    section.appendChild(jobBox);
    // one notice: the groups the AI could not name, else the drafts that wait
    const failed = m.groups.filter((g) => g.naming_failed);
    const drafts = m.groups.filter((g) => g.name_source === "ai_draft");
    if (failed.length) section.appendChild(failedNote(failed, can));
    else if (drafts.length && !naming) {
      section.appendChild(notice({ kind: "info", icon: "sparkles", class: "cm-groups-note" },
        h("p", {}, drafts.length === 1 ? "1 name is the AI’s draft, and is marked so on the map and in a downloaded picture. Use it, or rename it."
          : `${drafts.length} names are the AI’s drafts, and are marked so on the map and in a downloaded picture. Use or rename each one.`),
        drafts.length > 1 ? button({ sm: true, onClick: async () => {
          const items = drafts.map((g) => ({ name_id: g.name_id, concepts: g.concepts, labels: groupBody(g).labels }));
          await act({ action: "accept", items, filters: m.filters, n: m.n }, `${drafts.length} names used.`,
            { refocus: "__ask", undo: (r) => ({ action: "unaccept", items: items.map((x) => ({ name_id: x.name_id })), before: (r && r.before) || undefined }) });
        } }, `Use all ${drafts.length} names`) : null));
    }
    // the table
    const by = nodeOf();
    const nameLink = (id) => link({ kind: "title", serif: true, href: conceptHref(id) }, (by[id] || {}).label || id);
    const conceptsCell = (ids) => h("td", { "data-label": "Concepts" }, ids.map((id, i) => [i ? ", " : null, nameLink(id), h("span", { class: "muted small" }, ` ${fmt.num((by[id] || {}).passages || 0)}`)]));
    const rows = m.groups.map((g) => {
      const ids = (g.concepts && g.concepts.length ? g.concepts : m.nodes.filter((n) => n.group === g.group).map((n) => n.id));
      const ordered = [...ids].sort((a, b) => ((by[b] || {}).passages || 0) - ((by[a] || {}).passages || 0));
      const first = ids[0] || "";
      const draft = g.name_source === "ai_draft";
      const ch = g.changed;
      const changeLine = ch ? h("p", { class: "muted small cm-group-change" }, "Since then ",
        [ch.left.length ? `${plural(ch.left.length, "concept")} left it (${firstSix(ch.left)})` : null,
          ch.joined.length ? `${ch.left.length ? ch.joined.length : plural(ch.joined.length, "concept")} joined (${firstSix(ch.joined)})` : null].filter(Boolean).join(" and "), ".") : null;
      const q = g.quote;
      const rests = (g.name_source === "ai" || draft) && q ? fold({ sm: true }, "What the AI’s name rests on",
        h("ul", { class: "ct-quotes" }, h("li", {}, h("span", { class: "serif" }, "“", shortTitle(q.quote, 260), "” "),
          q.doc_id ? link({ href: docHref(q), class: "small" }, `${q.title || "a document"}${q.page ? `, p. ${q.page}` : ""}`) : null))) : null;
      const acts = h("div", { class: "btn-row cm-group-acts" },
        draft ? button({ sm: true, icon: "check", onClick: () => act({ action: "accept", ...groupBody(g) }, "Name used.", { refocus: first, undo: (r) => ({ action: "unaccept", name_id: g.name_id, before: (r && r.before) || undefined }) }) }, "Use this name") : null,
        ch && !draft ? button({ sm: true, icon: "check", onClick: () => act({ action: "keep", ...groupBody(g) }, "Kept. The name now goes with the group as it is.", { refocus: first }) }, "Keep the name") : null,
        button({ kind: "quiet", sm: true, icon: "type", "data-rename": first, "aria-label": `Rename the group “${groupName(g)}”`, onClick: () => rename(g) }, "Rename"));
      return h("tr", {},
        h("td", { "data-label": "Group" }, h("div", { class: "cm-group-cell" },
          h("div", { class: "cm-group-title" }, swatch(g.group), h("span", { class: "serif cm-group-words" }, groupName(g)), h("span", { class: "visually-hidden" }, ` (${groupMark(g.group).words}${g.group > OWN_MARKS ? `, as every group from ${OWN_MARKS + 1} on` : ""})`)),
          h("div", { class: "cm-group-facts" }, sourceTag(g), ch ? tag({ kind: "attention" }, "changed since it was named") : null),
          changeLine, rests)),
        conceptsCell(ordered),
        h("td", {}, acts));
    });
    const alone = m.nodes.filter((n) => !n.group);
    if (alone.length) {
      rows.push(h("tr", {}, h("td", { "data-label": "Group" }, h("div", { class: "cm-group-title" }, swatch(0), h("span", { class: "muted" }, "In no group"), h("span", { class: "visually-hidden" }, ` (${groupMark(0).words})`))),
        conceptsCell(alone.map((n) => n.id)), h("td", {})));
    }
    section.appendChild(h("div", { class: "table-wrap" }, h("table", { class: "table table-responsive cm-groups" },
      h("caption", { class: "visually-hidden" }, "The groups of concepts, with their names"),
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Group"), h("th", { scope: "col" }, "Concepts, with their passages"), h("th", { scope: "col" }, h("span", { class: "visually-hidden" }, "Actions")))),
      h("tbody", {}, rows))));
    // b.6: names kept for groups that are not on this map
    const elsewhere = m.names_elsewhere || [];
    if (elsewhere.length) {
      section.appendChild(fold({ sm: true, class: "cm-groups-kept" }, elsewhere.length === 1 ? "1 name kept for a group that is not on this map" : `${elsewhere.length} names kept for groups that are not on this map`,
        h("p", { class: "muted small" }, "No group on this map holds most of their concepts. A name comes back when its group does: with other filters, or when the documents change."),
        h("ul", { class: "cm-kept-list" }, elsewhere.map((x) => h("li", {}, h("span", { class: "serif" }, x.name),
          h("span", { class: "muted small" }, `${x.concepts.join(", ")}${x.more ? ` and ${x.more} more` : ""}`),
          button({ kind: "quiet", sm: true, onClick: () => act({ action: "forget", name_id: x.id }, "Forgotten.", { undo: (r) => ({ action: "restore", record: r.record }) }) }, "Forget this name"))))));
    }
  }

  // ---- the lines as lists (docs/DESIGN.md 8) ----
  function drawLists() {
    const lab = Object.fromEntries(m.nodes.map((n) => [n.id, n.label]));
    const nameLink = (id) => link({ kind: "title", serif: true, href: conceptHref(id) }, lab[id]);
    const pairButton = (a, b) => button({ sm: true, kind: "quiet", onClick: () => showEdge(a, b) }, "Show the passages");
    const pairsTable = m.edges.length ? h("div", { class: "table-wrap" }, h("table", { class: "table table-responsive cm-pairs" },
      h("caption", { class: "visually-hidden" }, "Concepts mentioned together more often than by chance"),
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Concepts"), h("th", { scope: "col", class: "num" }, "Passages together"), h("th", { scope: "col", class: "num" }, "Times as often as by chance"), h("th", { scope: "col" }, h("span", { class: "visually-hidden" }, "Passages")))),
      h("tbody", {}, m.edges.map((e) => h("tr", {},
        h("td", { "data-label": "Concepts" }, nameLink(e.a), " and ", nameLink(e.b)),
        h("td", { class: "num", "data-label": "Passages together" }, fmt.num(e.together)),
        h("td", { class: "num", "data-label": "Times as often as by chance" }, times(e.pmi)),
        h("td", {}, pairButton(e.a, e.b))))))) : h("p", { class: "muted" }, "No two concepts are mentioned together often enough to be joined.");
    const linksList = m.links.length ? h("ul", { class: "cm-link-list" }, m.links.map((lk) => h("li", {},
      linkTypes(lk).map((t, i) => {
        const [x, y] = t.forward ? [lk.a, lk.b] : [lk.b, lk.a];
        return [i ? "; " : null, nameLink(x), ` ${REL_WORDS[t.kind]} `, nameLink(y), h("span", { class: "muted small" }, ` · ${SOURCE_WORDS[t.source] || t.source}`)];
      }), " ", pairButton(lk.a, lk.b))))
      : h("p", { class: "muted" }, "No link of the glossary joins two concepts on the map. Accept or add links on a concept’s page.");
    listBox.appendChild(fold({ class: "section", open: false }, "The lines as lists",
      h("h3", { class: "cm-list-h" }, "Mentioned together"), pairsTable,
      h("h3", { class: "cm-list-h" }, "Links"),
      h("p", { class: "muted small" }, `Each is ${LINKS_WORDS}.`), linksList));
  }

  // ---- the map as a picture (D1 rest, c): made in the page, nothing sent anywhere ----
  function filtersSentence() {
    if (!filtered()) return null;
    const parts = [];
    if (f.doc) {
      const ids = f.doc.split(",");
      const d = ids.length === 1 ? opts.documents.find((x) => x.doc_id === ids[0]) : null;
      parts.push(d ? `the document “${shortTitle(d.title || d.doc_id, 60)}”` : plural(ids.length, "document"));
    }
    if (f.theme) {
      const t = (opts.themes.themes || []).find((x) => `${opts.themes.run_id}:${x.theme_id}` === f.theme);
      parts.push(`the theme “${shortTitle(t ? t.name : f.theme, 60)}”`);
    }
    if (f.code) {
      const cb = fws.get(f.framework);
      const c = cb ? cb.codes.find((x) => x.code === f.code) : null;
      parts.push(`passages with the code ${f.code}${c && c.description ? ` ${shortTitle(c.description, 60)}` : ""}${cb ? ` (${shortTitle(cb.title, 40)})` : ""}`);
    }
    if (f.year_from || f.year_to) parts.push(`documents published ${f.year_from ? `from ${f.year_from}` : ""}${f.year_from && f.year_to ? " " : ""}${f.year_to ? `until ${f.year_to}` : ""}`);
    return `Counted only in: ${parts.join(" · ")}`;
  }
  function pictureText() {
    const title = `Concept map of ${shortTitle(project, 80)}`;
    return pictureSvg(m, { title, facts: factsSentence(true), filters: filtersSentence(),
      few: m.edges.length && m.passages < FEW_PASSAGES ? `Only ${plural(m.passages, "passage")} ${m.passages === 1 ? "is" : "are"} counted, so the lines rest on very little.` : null,
      version: (App.state && App.state.version) || "", when: fmt.date(new Date().toISOString()) });
  }
  async function saveMap(btn, ext) {
    setBusy(btn, true);
    try {
      const text = pictureText();
      const blob = ext === "svg" ? new Blob([text], { type: "image/svg+xml" }) : await pngOf(text);
      saveBlob(blob, mapFileName(project, filtered(), ext));
    } catch (e) { showError(e); } finally { setBusy(btn, false); }
  }
  const dl = downloadLinks([
    { text: "PNG", title: "A picture for slides and documents: 2,400 pixels wide, on white", onClick: (e) => saveMap(e.currentTarget, "png") },
    { text: "SVG", title: "A picture that stays sharp at any size and can be changed in a drawing program", onClick: (e) => saveMap(e.currentTarget, "svg") },
  ], { label: "Download the map" });
  for (const b of dl.querySelectorAll("button")) b.dataset.title = b.title || "";
  pngBtnHolder.appendChild(dl);

  drawFilters();
  await load();
  const running = await runningJob(project, ["group-names"]);
  if (running && !naming) followNames(running.id);
  // a new width draws the map again (the marks keep their size, so a narrow window gets a taller map)
  let timer = null;
  const ro = new ResizeObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (!m || !m.nodes || !m.nodes.length) return;
      const w = mapBox.clientWidth;
      if (Math.abs(w - lastWidth) < 40) return;
      const wrap = mapBox.querySelector(".cm-svg-wrap");
      if (wrap) replace(wrap, svgMap());
    }, 200);
  });
  ro.observe(mapBox);
  return () => { ro.disconnect(); clearTimeout(timer); clearTimeout(loadTimer); watchers.forEach((w) => w.stop()); };
}
