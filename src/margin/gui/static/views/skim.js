// Skim (Margin): a one-page report on one document, made on this computer without AI. What it is, its abstract,
// what it sets out to do and what it says it found, the sentences that carry its key terms, the statements it makes
// with and without a citation, its sections, key terms, the works it cites most and its codes. Every item opens the
// document at its place. A quick look (one file, no project to set up) lands here.
import { App, api, h, icon, replace, showError, fmt, pageHead, P, plural, emptyState, download, downloadLinks, shortTitle, KIND_TEXT } from "../lib.js";
import { featureEyebrow } from "../features.js";
import { quickLookButton } from "./quicklook.js";

const at = (docId, it) => `#/doc/${encodeURIComponent(docId)}?q=${it.start}-${it.end}&src=skim`;

function where(docId, it) {
  const bits = [it.page ? `p. ${it.page}` : null, it.section ? shortTitle(it.section, 48) : null].filter(Boolean);
  return h("a", { class: "sk-where", href: at(docId, it), title: "Open the document at this place" }, icon("arrow-right", { size: 12 }), bits.join(" · ") || "Show in the text");
}

function sentenceList(docId, items, extra) {
  return h("ul", { class: "sk-list" }, items.map((it) => h("li", {},
    h("p", { class: "sk-text serif" }, it.text),
    h("div", { class: "sk-foot" }, extra ? extra(it) : null, where(docId, it)))));
}

function card(title, sub, body, opts = {}) {
  return h("section", { class: "card sk-card" + (opts.class ? ` ${opts.class}` : ""), "aria-labelledby": opts.id || null },
    h("div", { class: "sk-card-head" }, h("h2", { id: opts.id || null }, opts.icon ? icon(opts.icon, { size: 16 }) : null, title), opts.aside || null),
    sub ? h("p", { class: "muted small sk-sub" }, sub) : null, body);
}

function tile(n, label, help) {
  return h("div", { class: "sk-tile", title: help || null }, h("span", { class: "sk-tile-n" }, n), h("span", { class: "sk-tile-label" }, label));
}

// ------------------------------------------------------------------------------------------------------------------
// #/skim: choose a document of the project, or skim a file without adding it
// ------------------------------------------------------------------------------------------------------------------
export async function renderSkimIndex(view) {
  const project = App.project;
  const r = await api("GET", `/api/projects/${P(project)}/documents`);
  const docs = r.documents || [];
  if (docs.length === 1) { location.replace(`#/skim/${encodeURIComponent(docs[0].doc_id)}`); return; }  // no back-loop
  view.append(pageHead("Skim", {
    eyebrow: featureEyebrow("skim"),
    sub: "A one-page report on one document: what it sets out to do, what it says it found, its key sentences, the claims it makes without a citation and the works it cites most. Made on this computer, without AI.",
    actions: [quickLookButton({ class: "btn", text: "Skim a file not in this project" })],
  }));
  if (!docs.length) {
    view.append(emptyState("eye", "No documents in this project yet", "Skim a file at once, without adding it to a project: it is read into a quick look of its own.", quickLookButton({ class: "btn btn-primary", text: "Choose a file to skim" })));
    return;
  }
  view.append(h("div", { class: "card sk-pick" }, h("ul", { class: "sk-docs" }, docs.map((d) => h("li", {},
    h("a", { href: `#/skim/${encodeURIComponent(d.doc_id)}` }, icon("file-text", { size: 15 }), h("span", { class: "grow serif" }, d.title || d.file),
      h("span", { class: "muted small nowrap" }, [KIND_TEXT[d.kind] || d.kind, d.pages ? `${d.pages} pages` : null].filter(Boolean).join(" · "))))))));
}

// ------------------------------------------------------------------------------------------------------------------
// #/skim/<doc>: the report
// ------------------------------------------------------------------------------------------------------------------
export async function renderSkim(view, [docId]) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/documents/${P(docId)}/skim`;
  let r;
  try { r = await api("GET", base); }
  catch (e) {
    if (e.status === 404) { view.append(emptyState("search-x", "No such document", "It was removed from the project.", h("a", { class: "btn", href: "#/skim" }, "Choose another document"))); return; }
    throw e;
  }
  const f = r.facts;
  const one = r.documents_in_project <= 1;
  const meta = [r.file, KIND_TEXT[r.kind] || r.kind, f.pages ? plural(f.pages, "page") : null, plural(f.words, "word"), `about ${f.minutes} min to read`].filter(Boolean);
  const head = pageHead(r.title, {
    titleClass: "serif",
    eyebrow: [featureEyebrow("skim"), one ? null : h("a", { href: "#/skim", class: "it sk-back" }, icon("arrow-left", { size: 12 }), "Other documents")],
    actions: [
      h("a", { class: "btn btn-primary", href: `#/doc/${encodeURIComponent(docId)}` }, icon("book-open", { size: 14 }), "Read the document"),
      downloadLinks([{ text: "Markdown (.md)", title: "This report as notes to keep", onClick: () => download(`${base}.md`).catch(showError) }]),
    ],
  });
  head.querySelector(".page-head-main").append(h("div", { class: "result-meta sk-meta" },
    meta.map((m, i) => [i ? h("span", { class: "sep" }, "·") : null, h("span", {}, m)]),
    r.doi ? [h("span", { class: "sep" }, "·"), h("a", { href: `https://doi.org/${r.doi}`, target: "_blank", rel: "noopener noreferrer", title: "Opens the publisher's page in your browser" }, `doi ${r.doi}`)] : null));
  view.append(head);

  const c = r.claims, ci = r.cited;
  view.append(h("div", { class: "sk-tiles" },
    tile(`${f.minutes} min`, "to read", `${fmt.num(f.words)} words in the text before the reference list, at ${230} words a minute`),
    tile(fmt.num(r.outline.length), r.outline.length === 1 ? "section" : "sections", "Headings found when the document was read"),
    tile(fmt.num(ci.works), ci.works === 1 ? "work cited" : "works cited", `${plural(ci.markers, "citation")} in the text`),
    tile(fmt.num(c.uncited), c.uncited === 1 ? "claim without a citation" : "claims without a citation", "Statements of the kinds that usually need a source, outside its own abstract, data and results")));

  const main = h("div", { class: "sk-main" });
  const side = h("div", { class: "sk-side" });
  view.append(h("div", { class: "sk-grid" }, main, side));

  // ---- the main column: the document's own words
  if (r.abstract) main.append(card("Abstract", null, h("div", {}, h("p", { class: "sk-text serif sk-abstract" }, r.abstract.text), h("div", { class: "sk-foot" }, where(docId, r.abstract))), { icon: "note", id: "sk-abstract" }));
  if (r.aims.length || r.findings.length) {
    main.append(card("What it sets out to do, and what it says it found", "Sentences in its own voice (“we”, “this study”, “our results”), found by rules.", h("div", { class: "stack" },
      r.aims.length ? [h("h3", { class: "sk-h3" }, "It sets out to"), sentenceList(docId, r.aims)] : null,
      r.findings.length ? [h("h3", { class: "sk-h3" }, "It says it found"), sentenceList(docId, r.findings)] : null), { icon: "flask", id: "sk-own" }));
  }
  if (r.key_sentences.length) {
    main.append(card("Key sentences", "The sentences that carry most of its key terms, from different sections, in reading order: a summary in its own words.",
      sentenceList(docId, r.key_sentences, (it) => h("span", { class: "sk-terms muted small" }, it.terms.slice(0, 4).join(", "))), { icon: "highlighter", id: "sk-key" }));
  }
  main.append(claimsCard(docId, c));
  if (!r.abstract && !r.aims.length && !r.findings.length && !r.key_sentences.length && !c.total) {
    main.prepend(h("div", { class: "notice notice-info" }, icon("info"), h("p", {}, "Little could be read from this document's text: it may be very short, a scan without text, or not written in full sentences. ", h("a", { href: `#/doc/${encodeURIComponent(docId)}` }, "Read it"), " to see what Margin has.")));
  }

  // ---- the side column: its shape
  if (r.outline.length) {
    const max = Math.max(...r.outline.map((s) => s.words), 1);
    side.append(card("Sections", null, h("ol", { class: "sk-outline" }, r.outline.map((s) => h("li", { class: s.references ? "sk-refs" : null },
      h("a", { href: at(docId, s), title: `${plural(s.words, "word")}${s.page ? `, from page ${s.page}` : ""}` },
        h("span", { class: "sk-o-title" }, shortTitle(s.title, 60)), h("span", { class: "sk-o-n muted small" }, fmt.num(s.words))),
      h("span", { class: "sk-bar", "aria-hidden": "true" }, h("span", { style: { width: `${Math.max(2, Math.round((s.words / max) * 100))}%` } }))))), { icon: "list-checks", id: "sk-sections", aside: h("span", { class: "muted small" }, "words") }));
  }
  if (r.key_terms.terms.length) {
    side.append(card("Key terms", r.key_terms.basis === "document" ? "Weighed by how far each runs through the document: there is no other document to compare it with." : `Compared with the other ${plural(r.documents_in_project - 1, "document")} of the project.`,
      h("div", { class: "chips" }, r.key_terms.terms.map((k) => h("a", { class: "chip chip-term", href: `#/doc/${encodeURIComponent(docId)}?tab=search&find=${encodeURIComponent(k.label)}`, title: `${plural(k.mentions, "mention")}: find them in the document` }, k.label, h("span", { class: "muted" }, ` ${k.mentions}`)))), { icon: "network", id: "sk-terms" }));
  }
  side.append(citedCard(docId, ci));
  if (r.codes) {
    side.append(card(`Codes: ${r.codes.framework_title}`, `The codes with most passages${r.codes.total > r.codes.codes.length ? ` (${r.codes.codes.length} of ${r.codes.total})` : ""}.`,
      h("ul", { class: "sk-codes" }, r.codes.codes.map((x) => h("li", {}, h("a", { href: x.start != null ? at(docId, x) : `#/doc/${encodeURIComponent(docId)}?tab=codes` }, h("span", { class: "chip chip-code" }, x.code), h("span", { class: "grow" }, x.description)), h("span", { class: "muted small nowrap" }, plural(x.passages, "passage"))))), { icon: "tag", id: "sk-codes" }));
  }
  if (one) {
    side.append(card("Ask it something", null, h("div", { class: "stack" },
      h("p", { class: "small", style: { margin: 0 } }, "Check a statement against this document, with the exact quotes for you to judge. This one uses the AI."),
      h("div", { class: "btn-row" }, h("a", { class: "btn btn-sm", href: "#/check" }, icon("flask", { size: 13 }), "Check a statement"), h("a", { class: "btn btn-sm", href: "#/search" }, icon("text-search", { size: 13 }), "Search it"))), { icon: "help", id: "sk-ask" }));
  }
}

function claimsCard(docId, c) {
  const body = h("div");
  const KEYS = [
    ["uncited", "No citation", (x) => !x.cited && !x.own, c.uncited],
    ["cited", "Cited", (x) => x.cited && !x.own, c.cited],
    ["own", "Its own results", (x) => x.own, c.own],
    ["all", "All", () => true, c.total],
  ];
  let on = c.uncited ? "uncited" : c.cited ? "cited" : "all";
  const seg = h("div", { class: "lit-seg sk-seg", role: "group", "aria-label": "Which claims" });
  function draw() {
    replace(seg, KEYS.map(([k, label, , n]) => h("button", { class: "lit-seg-btn" + (on === k ? " on" : ""), type: "button", "aria-pressed": on === k ? "true" : "false", onClick: () => { on = k; draw(); } }, `${label} (${fmt.num(n)})`)));
    const [, , keep] = KEYS.find(([k]) => k === on);
    const items = c.items.filter(keep);
    replace(body, items.length ? sentenceList(docId, items, (it) => h("span", { class: "chip" + (it.cited ? " chip-counted" : "") }, it.why))
      : h("p", { class: "muted small" }, on === "uncited" ? "Every such statement outside its own data and results comes with a citation." : "None."),
      c.cut ? h("p", { class: "muted small" }, `The first ${c.items.length} are listed; the counts cover all ${c.total}.`) : null);
  }
  if (!c.total) return card("Claims about the world", "No statements of the kinds that usually need a source were found (numbers, causes and effects, comparisons, what research found, general claims).", null, { icon: "quote", id: "sk-claims" });
  draw();
  return card("Claims about the world", `${plural(c.total, "statement")} of the kinds that usually need a source, by the rules of Check a draft. ${c.own ? `${fmt.num(c.own)} are in its own abstract, data or results, where a number is its evidence; of the other ${fmt.num(c.others)}, ` : ""}${c.cited ? `${fmt.num(c.cited)} come with a citation` : `${c.own ? "none" : "None"} comes with a citation`}.`,
    h("div", { class: "stack" }, seg, body), { icon: "quote", id: "sk-claims" });
}

function citedCard(docId, ci) {
  if (!ci.markers) {
    return card("Works it cites", ci.references_at != null ? "It has a reference list, but no citation in its text could be read (perhaps numbered citations without a numbered list)." : "No citations were found in its text.", null, { icon: "library", id: "sk-cited" });
  }
  const note = [`${plural(ci.markers, "citation")} of ${plural(ci.works, "work")} in the text`,
    ci.references_at != null ? `the reference list starts ${ci.references_page ? `on page ${ci.references_page}` : "after the text"}` : null,
    ci.dois ? `${plural(ci.dois, "DOI")} in it` : null].filter(Boolean).join("; ") + ".";
  return card("Works it cites most", note, h("div", { class: "stack" },
    h("ol", { class: "sk-cited" }, ci.top.map((w) => h("li", {}, h("a", { href: at(docId, w), title: "Open the document at the first citation" }, h("span", { class: "grow" }, w.label)), h("span", { class: "muted small nowrap" }, `${w.count}×`)))),
    ci.dois ? h("p", { class: "small", style: { margin: 0 } }, h("a", { href: "#/literature?tab=citations", class: "it" }, icon("link", { size: 13 }), "Follow its citations"), h("span", { class: "muted" }, ": the works it cites and the works citing it (asks OpenAlex)")) : null),
    { icon: "library", id: "sk-cited" });
}
