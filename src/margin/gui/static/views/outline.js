// An outline from the themes (roadmap C). A set of themes becomes a writing plan: one section for each theme, in an
// order that reads as a path (themes that share documents and key terms sit next to each other). No AI is used. Each
// section shows its key terms, the passages that represent it best, the documents to cite (APA, with a bibliography),
// its codes and concepts, where its documents disagree, the gaps and what you decided about its claims. You move
// sections (drag, or the arrow buttons), nest them, merge, split, rename, add your own, and write notes. Beside a
// draft, each section says how much of it the draft covers and what is still unused. The outline downloads as Word or
// Markdown.
import { featureEyebrow } from "../features.js";
import { App, api, h, icon, replace, clear, toast, showError, fmt, pageHead, P, emptyState, dialog, confirmDialog, download, downloadLinks, plural, shortTitle, store, navigate, statusBadge, STATUS_SHORT,
  button, iconButton, link, notice, tag, inset, field, input as inputEl, textarea as textareaEl, select as selectEl, switchControl, fold,
  card as makeCard, menu as menuOf, listGroup, listRow, judgementIcon } from "../lib.js";

const searchHref = (q) => `#/search?q=${encodeURIComponent(q)}&mode=phrase`;
const docHref = (d, a, b) => `#/doc/${encodeURIComponent(d)}${Number.isInteger(a) && Number.isInteger(b) ? `?q=${a}-${b}` : ""}`;
const outlineHref = (id) => `#/outline/${encodeURIComponent(id)}`;
const checkHref = (text) => `#/hypotheses?text=${encodeURIComponent(text)}`;
const MAX_HYPOTHESES = 12;
const openState = new Map();   // outline id -> Set of the section ids shown open (kept while the app is open)

async function copy(text, what = "Copied.") {
  try { await navigator.clipboard.writeText(text); toast(what, "ok", { ttl: 1800 }); }
  catch (_) { toast("Select the text and copy it with Ctrl+C (or Cmd+C).", "info"); }
}

// ---------------------------------------------------------------------------------------------
// the button on a set of themes: make an outline, or open the one made already
// ---------------------------------------------------------------------------------------------
export function outlineButton(project, runId) {
  const slot = h("span", { class: "ol-slot" });
  const make = () => {
    const b = button({ sm: true, icon: "file-text", title: "A writing plan from these themes: one section for each, in an order that reads as a path. No AI." }, "Make an outline");
    b.addEventListener("click", async () => {
      b.disabled = true;
      try { const r = await api("POST", `/api/projects/${P(project)}/outlines`, { run_id: runId }); navigate(outlineHref(r.outline_id)); }
      catch (e) { b.disabled = false; showError(e); }
    });
    return b;
  };
  replace(slot, make());
  api("GET", `/api/projects/${P(project)}/outlines`).then((r) => {
    const mine = (r.outlines || []).filter((o) => o.run_id === runId);
    // moving to a page is a link, but this stands among the head's buttons: a button that goes there
    if (mine.length) replace(slot, button({ sm: true, icon: "file-text", title: mine.length > 1 ? `${mine.length} outlines were made from these themes; this is the latest.` : "The outline made from these themes.",
      onClick: () => navigate(outlineHref(mine[0].outline_id)) }, "Open the outline"));
  }).catch(() => {});
  return slot;
}

// ---------------------------------------------------------------------------------------------
// the list of outlines
// ---------------------------------------------------------------------------------------------
export async function renderOutlines(view) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/outlines`;
  const info = await api("GET", base);
  const box = h("div");
  view.append(pageHead("Outline", {
    eyebrow: featureEyebrow("outline"),
    sub: "A writing plan made from the themes of your documents, around your research question and hypotheses or from all the themes, with what to cite and where your sources disagree. Made on this computer, without AI.",
  }), box);

  // the hypotheses already checked, to pick from (latest first)
  let checked = [];
  api("GET", `/api/projects/${P(project)}/hypotheses?limit=200`).then((r) => {
    const seen = new Set();
    checked = (r.hypotheses || []).filter((x) => x.text && !seen.has(x.text) && seen.add(x.text));
    draw();
  }).catch(() => {});
  const qDraft = { question: store("outline.question") || "", hyps: store("outline.hypotheses") || "" };

  function questionCard(runs, sel) {
    const q = textareaEl({ rows: 2, maxlength: 1000, id: "ol-q", placeholder: "How does green hydrogen production affect water use in arid regions?" });
    q.value = qDraft.question;
    const hy = textareaEl({ rows: 3, id: "ol-hyps", placeholder: "One per line, for example:\nElectrolysis raises water stress where groundwater is scarce.\nDesalination makes the water demand manageable." });
    hy.value = qDraft.hyps;
    q.addEventListener("input", () => store("outline.question", q.value || null));
    hy.addEventListener("input", () => store("outline.hypotheses", hy.value || null));
    const lines = () => hy.value.split("\n").map((x) => x.trim()).filter(Boolean);
    const pick = checked.length ? selectEl({ sm: true, "aria-label": "Add a hypothesis you checked" },
      h("option", { value: "" }, `Add one you checked (${checked.length})…`),
      checked.map((x) => h("option", { value: x.text }, `${shortTitle(x.text, 90)}${STATUS_SHORT[x.status] ? ` · ${STATUS_SHORT[x.status]}` : ""}`))) : null;
    if (pick) pick.addEventListener("change", () => {
      if (!pick.value) return;
      if (!lines().includes(pick.value)) { hy.value = [...lines(), pick.value].join("\n"); store("outline.hypotheses", hy.value); }
      pick.value = "";
    });
    const semantic = App.settings().embed_backend && App.settings().embed_backend !== "off";
    const mean = semantic ? switchControl("Also by meaning", store("outline.qmeaning") === "1", { help: "Also places themes by meaning, using the embedding model on this computer. Nothing leaves it." }) : null;
    if (mean) mean.input.addEventListener("change", () => store("outline.qmeaning", mean.input.checked ? "1" : "0"));
    const go = button({ kind: "main", icon: "list-checks" }, "Make the outline");
    go.addEventListener("click", async () => {
      if (!q.value.trim()) { q.focus(); toast("Write the research question first.", "warn"); return; }
      if (lines().length > MAX_HYPOTHESES) { toast(`Give at most ${MAX_HYPOTHESES} hypotheses.`, "warn"); return; }
      go.disabled = true;
      try {
        const r = await api("POST", base, { run_id: sel.value || null, question: q.value, hypotheses: lines(), meaning: !!(mean && mean.input.checked) });
        store("outline.question", null); store("outline.hypotheses", null);
        if (r.meaning && !r.meaning.used) toast(`Placed without closeness by meaning: ${r.meaning.why}`, "info");
        navigate(outlineHref(r.outline_id));
      } catch (e) { go.disabled = false; showError(e); }
    });
    return makeCard({ class: "ol-make", title: "From a research question", titleId: "ol-q-h" },
      h("p", { class: "muted" }, "Each hypothesis becomes a section holding the themes that bear on it: first the themes where its check found evidence, then those that share its key terms or concepts. Themes that bear only on the question go under Background; the others stay out, so the outline is about your question."),
      field("Research question", q),
      field(["Hypotheses ", h("span", { class: "muted small" }, "(optional, one per line)")], hy),
      h("div", { class: "row ol-make-row" }, pick, runs.length > 1 ? sel : null, mean),
      h("div", { class: "btn-row" }, go),
      h("p", { class: "muted small" }, "A hypothesis you have not checked yet is placed by its words only; check it later and the outline shows its evidence."));
  }

  async function draw() {
    const { outlines, runs } = info;
    const parts = [];
    if (!runs.length) {
      parts.push(emptyState("shapes", "Find the themes first", "An outline is made from the themes of your documents.", link({ kind: "next", href: "#/themes" }, "Find the themes on the Themes page")));
    } else {
      const sel = selectEl({ sm: true, "aria-label": "The set of themes" },
        runs.map((r) => h("option", { value: r.run_id }, `${plural(r.themes_now, "theme")}, found ${fmt.date(r.created_at)}${r.stale ? " (before documents changed)" : ""}`)));
      const go = button({ icon: "file-text" }, "Make an outline");
      go.addEventListener("click", async () => {
        go.disabled = true;
        try { const r = await api("POST", base, { run_id: sel.value }); navigate(outlineHref(r.outline_id)); }
        catch (e) { go.disabled = false; showError(e); }
      });
      parts.push(questionCard(runs, sel));
      parts.push(makeCard({ title: "From all the themes", titleId: "ol-make-h" },
        h("p", { class: "muted" }, "Each theme becomes a section. Themes that share documents and key terms sit next to each other, so the outline reads as a path. You can then move, merge, split and add sections."),
        h("div", { class: "btn-row" }, go)));
    }
    if (outlines.length) {
      parts.push(h("section", { class: "section", "aria-labelledby": "ol-list-h" },
        h("div", { class: "section-title" }, h("h2", { id: "ol-list-h" }, "Your outlines")),
        makeCard({ class: "ol-list" }, listGroup(null, ...outlines.map((o) => {
          const del = iconButton({ icon: "trash", size: 15, label: `Delete the outline “${o.title}”`, title: "Delete this outline" });
          del.addEventListener("click", async () => {
            if (!(await confirmDialog({ title: "Delete this outline?", message: `“${o.title}” and the notes you wrote in it are removed. The themes stay.`, confirmText: "Delete" }))) return;
            try { await api("DELETE", `${base}/${P(o.outline_id)}`); info.outlines = info.outlines.filter((x) => x.outline_id !== o.outline_id); draw(); } catch (e) { showError(e); }
          });
          return listRow({ title: o.title, href: outlineHref(o.outline_id), serif: true,
            sub: `${plural(o.sections, "section")} · changed ${fmt.date(o.updated_at)}${o.run_exists ? "" : " · its themes were deleted"}`, actions: [del] });
        })))));
    }
    replace(box, ...parts);
  }
  draw();
}

// ---------------------------------------------------------------------------------------------
// one outline
// ---------------------------------------------------------------------------------------------
export async function renderOutline(view, [oid], query) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/outlines/${P(oid)}`;
  let v, drafts = [], frameworks = [], cmp = null, cmpError = "";
  try { v = await api("GET", base); }
  catch (e) {
    if (e.status === 404) {
      view.append(pageHead("Outline", { eyebrow: featureEyebrow("outline") }), emptyState("search-x", "No such outline", "It was deleted, or it belongs to another project.", link({ kind: "next", href: "#/outline" }, "Show the outlines")));
      return;
    }
    throw e;
  }
  api("GET", `/api/projects/${P(project)}/drafts`).then((r) => { drafts = r.drafts || []; chooseDraft(); drawTools(); }).catch(() => {});
  api("GET", `/api/projects/${P(project)}/frameworks`).then((r) => { frameworks = r.frameworks || []; drawTools(); }).catch(() => {});
  const open = openState.get(oid) || new Set();
  openState.set(oid, open);
  let draftId = query.draft || store("outline.draft") || "";
  let meaning = store("outline.meaning") === "1";
  let dragId = null;

  const head = h("div"), notes = h("div"), tools = h("div"), tree = h("div"), spare = h("div"), tech = h("div");
  view.append(head, notes, tools, tree, spare, tech);

  function chooseDraft() {
    if (draftId && !drafts.some((d) => d.draft_id === draftId)) draftId = "";
  }

  async function load({ keepScroll = true } = {}) {
    const y = window.scrollY;
    try {
      v = await api("GET", base);
      cmp = null; cmpError = "";
      if (draftId) {
        try { cmp = await api("GET", `${base}/draft/${P(draftId)}${meaning ? "?meaning=1" : ""}`); }
        catch (e) { cmpError = e.message || String(e); if (e.status === 404) { draftId = ""; store("outline.draft", null); } }
      }
    } catch (e) { showError(e); return; }
    draw();
    if (keepScroll) window.scrollTo(0, y);
  }

  const flat = () => { const out = []; (function walk(ns) { for (const n of ns) { out.push(n); walk(n.children); } })(v.sections); return out; };
  const find = (id) => flat().find((n) => n.section_id === id);
  async function act(method, path, body, after) {
    try { const r = await api(method, `${base}${path}`, body); if (after) after(r); await load(); } catch (e) { showError(e); await load(); }
  }

  // -- the head
  function drawHead() {
    const o = v.outline;
    const rename = button({ kind: "quiet", sm: true, icon: "note" }, "Rename");
    rename.addEventListener("click", async () => {
      const input = inputEl({ value: o.title, maxlength: 200, "aria-label": "Title of the outline" });
      const ok = await dialog({ title: "Rename the outline", body: input, actions: [{ text: "Cancel", value: null }, { text: "Save", value: true, primary: true }], onOpen: () => input.focus() });
      if (ok && input.value.trim()) act("PUT", "", { title: input.value });
    });
    const dl = (fmtName, label) => ({ text: label, onClick: () => download(`${base}/export.${fmtName}`).catch(showError) });
    const trash = button({ kind: "danger", sm: true, icon: "trash" }, "Delete");
    trash.addEventListener("click", async () => {
      if (!(await confirmDialog({ title: "Delete this outline?", message: `“${o.title}” and the notes you wrote in it are removed. The themes stay.`, confirmText: "Delete" }))) return;
      try { await api("DELETE", base); navigate("#/outline"); } catch (e) { showError(e); }
    });
    const nTop = v.sections.length;
    replace(head, pageHead(o.title, {
      display: true,
      back: { href: "#/outline", text: "All outlines" },
      sub: o.question
        ? `${plural(o.sections, "section")}${v.run ? `, made from the themes found on ${fmt.date(v.run.created_at)}` : ""}, around your research question. Each hypothesis holds the themes that bear on it most. Everything on this page is made on your computer, without AI.`
        : `${plural(o.sections, "section")}${v.run ? `, made from the themes found on ${fmt.date(v.run.created_at)}` : ""}. The order is a suggestion: themes that share documents and key terms are next to each other. Everything on this page is made on your computer, without AI.`,
      actions: [rename, downloadLinks([dl("docx", "Word (.docx)"), dl("md", "Markdown (.md)")]), trash],
    }));
    clear(notes);
    if (o.question) {
      const edit = button({ kind: "quiet", sm: true, icon: "note" }, "Reword");
      edit.addEventListener("click", async () => {
        const input = textareaEl({ rows: 3, maxlength: 1000, "aria-label": "Research question" });
        input.value = o.question;
        const ok = await dialog({ title: "Reword the research question", body: h("div", {}, input, h("p", { class: "muted small" }, "The sections stay where they are; the reasons each theme shows are read again from the new words.")), actions: [{ text: "Cancel", value: null }, { text: "Save", value: true, primary: true }], onOpen: () => input.focus() });
        if (ok && input.value.trim()) act("PUT", "", { question: input.value });
      });
      notes.appendChild(makeCard({ sm: true, as: "div", class: "ol-question" }, h("div", { class: "ol-fact-label" }, "Research question"), h("p", { class: "ol-question-text" }, o.question), edit));
    }
    if (!v.run) notes.appendChild(notice({ kind: "attention", class: "ol-notice" }, h("p", {}, "The set of themes this outline came from was deleted. The sections keep their titles and notes, but their passages, sources and key terms are gone.")));
    else if (v.run.stale) notes.appendChild(notice({ kind: "attention", class: "ol-notice" }, h("p", {}, "Documents were added or removed since these themes were found, so the outline leaves out the changes. Find the themes again and make a new outline; this one is kept.")));
    if (!nTop) notes.appendChild(emptyState("file-text", "This outline has no sections", "Add a section of your own below, or bring a theme back."));
  }

  // -- the tools: draft, add a section, order, codebook
  function drawTools() {
    const draftSel = selectEl({ sm: true, "aria-label": "Draft to put beside the outline" },
      h("option", { value: "" }, drafts.length ? "No draft" : "No draft yet"),
      drafts.map((d) => h("option", { value: d.draft_id, selected: d.draft_id === draftId }, shortTitle(d.title || "Untitled draft", 50))));
    draftSel.addEventListener("change", () => { draftId = draftSel.value; store("outline.draft", draftId || null); load(); });
    const semantic = App.settings().embed_backend && App.settings().embed_backend !== "off";
    const mean = semantic ? switchControl("Also by meaning", meaning, { help: "Compares the draft's paragraphs with each section by meaning, using the embedding model on this computer. Nothing leaves it." }) : null;
    if (mean) mean.input.addEventListener("change", () => { meaning = mean.input.checked; store("outline.meaning", meaning ? "1" : "0"); load(); });

    const where = selectEl({ sm: true, "aria-label": "Where to add the section" },
      h("option", { value: "end" }, "at the end"), h("option", { value: "start" }, "at the start"));
    const nameIn = inputEl({ sm: true, list: "ol-own", placeholder: "Introduction, Methods…", maxlength: 200, "aria-label": "Title of the new section", class: "ol-name-in" });
    const add = button({ sm: true, icon: "plus" }, "Add a section");
    const doAdd = () => {
      if (!nameIn.value.trim()) { nameIn.focus(); return; }
      const t = nameIn.value;
      act("POST", "/sections", { title: t, index: where.value === "start" ? 0 : null }, () => { nameIn.value = ""; });
    };
    add.addEventListener("click", doAdd);
    nameIn.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doAdd(); } });

    const reorderWhat = v.outline.question ? "The themes inside each hypothesis and in Background are put back in the order of the similarity path. The hypotheses keep your order." : "The theme sections at the top level are put back in the order of the similarity path. Sections of your own and nested sections stay where they are.";
    const reorder = button({ sm: true, icon: "refresh", title: reorderWhat }, "Suggest the order again");
    reorder.addEventListener("click", async () => {
      if (!(await confirmDialog({ title: "Suggest the order again?", message: reorderWhat, confirmText: "Reorder", danger: false }))) return;
      act("POST", "/order", {}, (r) => toast(r.moved ? `${plural(r.moved, "section")} moved.` : "They were in that order already.", "ok", { ttl: 2200 }));
    });
    const allOpen = flat().length && flat().every((n) => open.has(n.section_id));
    const foldAll = button({ kind: "quiet", sm: true, icon: allOpen ? "chevron-up" : "chevron-down" }, allOpen ? "Fold all" : "Open all");
    foldAll.addEventListener("click", () => { if (allOpen) open.clear(); else for (const n of flat()) open.add(n.section_id); drawTree(); drawTools(); });

    let fw = null;
    if (frameworks.length) {
      fw = h("label", { class: "row small ol-fw" }, h("span", { class: "muted" }, "Codes from"),
        selectEl({ sm: true, onChange: (e) => act("PUT", "", { framework: e.target.value }) },
          h("option", { value: "" }, "no codebook"), frameworks.map((f) => h("option", { value: f.name, selected: f.name === v.outline.framework }, f.title || f.name))));
    }
    let hypRow = null;
    if (v.outline.question) {
      const hIn = inputEl({ sm: true, maxlength: 1000, placeholder: "Another hypothesis…", "aria-label": "A hypothesis to add", class: "ol-hyp-in" });
      const hAdd = button({ sm: true, icon: "plus", title: "A section for this hypothesis. It takes the themes that bear on it from Background and from the themes not in the outline." }, "Add a hypothesis");
      const doH = () => {
        if (!hIn.value.trim()) { hIn.focus(); return; }
        act("POST", "/hypotheses", { text: hIn.value }, (r) => { hIn.value = ""; open.add(r.section_id); toast(r.themes ? `It took ${plural(r.themes, "theme")}.` : "No theme bears on it yet.", "ok", { ttl: 2400 }); });
      };
      hAdd.addEventListener("click", doH);
      hIn.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doH(); } });
      hypRow = h("div", { class: "ol-tool-row" }, hIn, hAdd);
    }
    replace(tools, makeCard({ class: "ol-tools", "aria-label": "Tools for the outline" }, hypRow,
      h("div", { class: "ol-tool-row" }, h("label", { class: "row small ol-fw" }, h("span", { class: "muted" }, "Beside a draft"), draftSel), mean,
        h("span", { class: "muted small ol-tool-hint" }, draftId ? "Each section says how much of it the draft covers." : "Pick a draft to see how much of each section it covers.")),
      h("div", { class: "ol-tool-row" }, nameIn, h("datalist", { id: "ol-own" }, (v.own_suggestions || []).map((s) => h("option", { value: s }))), where, add, reorder, fw, foldAll)));
  }

  // -- sections
  const chip = (text, opts = {}) => tag({ kind: opts.attention ? "attention" : "neutral", icon: opts.icon, title: opts.title || null, class: opts.class }, text);
  const termChip = (t) => link({ class: "ol-term", href: searchHref(t), title: "Search the documents for this" }, t);
  const group = (label, ...kids) => { const k = kids.flat().filter(Boolean); return k.length ? h("div", { class: "ol-fact" }, h("div", { class: "ol-fact-label" }, label), h("div", { class: "ol-fact-body" }, k)) : null; };

  function sources(s) {
    if (!s.sources.length) return null;
    const cite = s.cite && s.cite.text ? h("div", { class: "ol-cite" }, h("span", { class: "ol-cite-text" }, s.cite.text), s.cite.more ? h("span", { class: "muted small" }, ` and ${s.cite.more} more`) : null,
      button({ kind: "quiet", sm: true, icon: "copy", onClick: () => copy(s.cite.text, "Citation copied.") }, "Copy")) : null;
    const part = s.cite && s.cite.text && s.cite.missing ? h("p", { class: "muted small" }, `${plural(s.cite.missing, "document")} of these ${s.cite.missing === 1 ? "is" : "are"} not linked to the bibliography, so ${s.cite.missing === 1 ? "it is" : "they are"} left out of the citation.`) : null;
    const none = s.cite && !s.cite.text ? h("p", { class: "muted small" }, "These documents are not linked to a bibliography, so they have no APA citation yet. ", link({ href: "#/bibliography" }, "Link them on the Bibliography page"), ".") : null;
    const rows = s.sources.slice(0, 12).map((d) => h("li", {}, link({ kind: "title", serif: true, href: docHref(d.doc_id) }, shortTitle(d.title, 90)), " ", h("span", { class: "muted small" }, `${plural(d.passages, "passage")}${d.apa ? ` · ${d.apa}` : ""}`)));
    return group(`Cite (${plural(s.documents, "document")})`, cite, part, none, h("ul", { class: "ol-docs" }, rows, s.sources.length > 12 ? h("li", { class: "muted small" }, `and ${s.sources.length - 12} more`) : null));
  }

  function quotes(s) {
    if (!s.representatives.length) return null;
    return group("Best passages", s.representatives.map((r) => h("figure", { class: "ol-quote" },
      h("blockquote", {}, r.text.length > 520 ? r.text.slice(0, 520).replace(/\s+\S*$/, "") + "…" : r.text),
      h("figcaption", { class: "small muted" }, link({ href: docHref(r.doc_id, r.start, r.end) }, shortTitle(r.title, 70)), r.location ? ` · ${r.location}` : "", r.apa ? ` · ${r.apa}` : ""))));
  }

  function disagreements(s) {
    if (!s.disagreements.length) return null;
    const side = (list, empty) => h("ul", { class: "ol-side-list" }, list.length ? list.map((x) => h("li", { class: x.inside ? "" : "ol-outside", title: x.inside ? null : "A document outside this section" },
      link({ href: docHref(x.doc_id) }, shortTitle(x.title, 50)), x.apa ? ` ${x.apa}` : "", x.location ? h("span", { class: "muted small" }, ` · ${x.location}`) : null,
      x.quote ? h("div", { class: "ol-q small" }, `“${shortTitle(x.quote, 160)}”`) : null)) : [h("li", { class: "muted" }, empty)]);
    return group("Where the sources disagree", s.disagreements.map((d) => h("div", { class: "ol-dis" },
      h("div", { class: "ol-dis-claim" }, link({ kind: "title", serif: true, href: `#/h/${encodeURIComponent(d.hyp_id)}` }, shortTitle(d.claim, 160)), " ", h("span", { class: "muted small" }, d.status_text || ""),
        d.tier === "across" ? chip("other side from elsewhere", { title: "Only one side comes from this section's documents" }) : null),
      h("div", { class: "ol-sides" },
        inset({ class: "ol-side ol-side-pro" }, h("div", { class: "ol-side-h" }, judgementIcon("supports", 13), "Support"), side(d.supports, "No document")),
        inset({ class: "ol-side ol-side-con" }, h("div", { class: "ol-side-h" }, judgementIcon("refutes", 13), "Contradict"), side(d.refutes, "No document"))))));
  }

  function decisions(s) {
    if (!s.decisions.length) return null;
    return group("You decided", h("ul", { class: "ol-docs" }, s.decisions.map((d) => h("li", {}, h("strong", {}, d.decision_text), ": ", shortTitle(d.claim, 150), " ", link({ class: "small", href: `#/drafts/${encodeURIComponent(d.draft_id)}` }, d.draft)))));
  }

  function hypothesisBox(s) {
    const x = s.hypothesis;
    if (!x) return null;
    if (!x.checked) {
      return group("Check", h("p", { class: "muted ol-flat" }, "Not checked yet. Its themes are placed by the key terms it shares with them."),
        h("div", {}, link({ href: checkHref(x.text), title: "Opens Hypotheses with this wording. Keep the wording, so the outline finds the check." }, "Check it on the Hypotheses page")));
    }
    const side = (key, label, cls) => {
      const list = (x.sides || {})[key] || [];
      return list.length ? inset({ class: `ol-side ${cls}` }, h("div", { class: "ol-side-h" }, label),
        h("ul", { class: "ol-side-list" }, list.map((d) => h("li", {}, link({ href: docHref(d.doc_id) }, shortTitle(d.title, 60)), d.apa ? ` ${d.apa}` : "", d.quote ? h("div", { class: "ol-q small" }, `“${shortTitle(d.quote, 160)}”`) : null)))) : null;
    };
    const sides = [side("supports", "Supports", "ol-side-pro"), side("partly", "Partly supports", "ol-side-partly"), side("refutes", "Contradicts", "ol-side-con")].filter(Boolean);
    return group("Check", h("div", { class: "ol-hyp-status" }, statusBadge(x.status, { text: x.status_text }), link({ class: "small", href: `#/h/${encodeURIComponent(x.hyp_id)}` }, "Open the result"),
      h("span", { class: "muted small" }, `${plural(x.evidence || 0, "passage")} counted${x.parts > 1 ? ` over ${x.parts} parts` : ""}`)),
      sides.length ? h("div", { class: "ol-sides ol-sides-3" }, sides) : null);
  }

  function whyHere(s) {
    const r = s.relevance;
    if (!r) return null;
    const bits = [];
    if (r.evidence) bits.push(chip(`${plural(r.evidence, "passage")} of the check`, { icon: "flask" }));
    if (r.terms.length) bits.push(h("span", { class: "muted small" }, "shares "), ...r.terms.map(termChip));
    if (r.meaning != null) bits.push(h("span", { class: "muted small", title: "When the outline was made, with the embedding model on this computer" }, `close in meaning (${Math.round(r.meaning * 100)}%)`));
    if (!bits.length) bits.push(h("span", { class: "muted small" }, r.related ? "" : `It no longer shares a key term with the ${r.to}; you placed it here, or the wording changed.`));
    const also = r.also.length ? h("p", { class: "muted small ol-flat" }, "Also bears on ", r.also.map((a, i) => [i ? ", " : "", h("span", { title: a.text }, a.number)])) : null;
    return group("Why here", bits, also);
  }

  function draftBox(s) {
    const c = cmp && cmp.sections[s.section_id];
    if (!c) return null;
    const total = (a, b) => `${a} of ${b}`;
    const lines = [
      c.terms_total ? h("p", {}, h("strong", {}, "Key terms in the draft: "), total(c.terms_used, c.terms_total), c.unused_terms.length ? h("span", { class: "muted" }, ` · not yet: ${c.unused_terms.slice(0, 8).join(", ")}${c.unused_terms.length > 8 ? "…" : ""}`) : null) : null,
      c.sources_total ? h("p", {}, h("strong", {}, "Sources the draft cites: "), total(c.sources_used, c.sources_total)) : null,
      c.unused_sources.length ? h("div", {}, h("strong", {}, "Not cited yet: "), h("ul", { class: "ol-docs" }, c.unused_sources.slice(0, 6).map((d) => h("li", {}, link({ href: docHref(d.doc_id) }, shortTitle(d.title, 80)), d.apa ? ` ${d.apa}` : "")), c.unused_sources.length > 6 ? h("li", { class: "muted small" }, `and ${c.unused_sources.length - 6} more`) : null)) : null,
      c.unused_points.length ? h("div", {}, h("strong", {}, "Points from sources not cited yet"), c.unused_points.map((p) => h("figure", { class: "ol-quote" }, h("blockquote", {}, shortTitle(p.text, 260)), h("figcaption", { class: "small muted" }, shortTitle(p.title, 60), p.location ? ` · ${p.location}` : "")))) : null,
      c.where ? h("p", {}, h("strong", {}, `Where the draft touches it (paragraph ${c.where.paragraph}): `), h("span", { class: "muted" }, shortTitle(c.where.excerpt, 200))) : null,
      c.closeness != null ? h("p", {}, h("strong", {}, "Closest by meaning: "), `${Math.round(c.closeness * 100)}% (paragraph ${c.closest.paragraph})`) : null,
    ];
    return inset({ class: `ol-draft ol-cover-${c.level}` }, h("div", { class: "ol-draft-h" }, `In your draft: ${c.level_text.toLowerCase()}`), lines);
  }

  function body(s) {
    const note = textareaEl({ class: "ol-note", rows: 2, "aria-label": `Your notes for “${s.title}”`, placeholder: s.kind === "hypothesis" ? "What you expect, and what would change your mind." : s.kind === "own" ? "What this part of the text should say." : "What this section should argue, or what to remember when you write it." });
    note.value = s.note || "";
    let saved = s.note || "";
    note.addEventListener("blur", async () => {
      if (note.value === saved) return;
      try { await api("PUT", `${base}/sections/${P(s.section_id)}`, { note: note.value }); saved = note.value; toast("Note saved.", "ok", { ttl: 1200 }); } catch (e) { showError(e); }
    });
    const parts = s.themes.length > 1 || s.split_by_documents ? group(s.themes.length > 1 ? "Made of" : "Part of", s.themes.map((t) => chip(t.name.length > 60 ? t.name.slice(0, 58) + "…" : t.name, { title: t.state === "shown" ? null : "This theme is not shown any more" })), s.split_by_documents ? chip("some of its documents", { title: "This section holds only some of the documents of the theme" }) : null) : null;
    const stateNote = s.state === "gone" ? notice({ kind: "attention" }, h("p", {}, "Its theme is gone, so only the title and your notes are left.")) :
      s.state === "removed" ? notice({ kind: "attention" }, h("p", {}, "Its theme was removed from the set. Bring it back on the Themes page, or take this section out.")) : null;
    return h("div", { class: "ol-body" },
      h("label", { class: "ol-note-label small muted" }, "Your notes"), note, stateNote, hypothesisBox(s), whyHere(s), parts,
      group("Key terms", s.terms.map(termChip)),
      group("Concepts", s.concepts.map((c) => link({ class: "ol-term", href: `#/concepts/${encodeURIComponent(c.term_id)}`, title: c.wordings.length > 1 ? `Also written: ${c.wordings.filter((w) => w !== c.label).join(", ")}` : null }, c.label))),
      s.codes && s.codes.length ? group("Codes", s.codes.map((c) => tag({ kind: "code", title: c.description || null }, h("strong", {}, c.code), " ", h("span", { class: "muted" }, String(c.passages))))) : null,
      sources(s), quotes(s), disagreements(s), decisions(s),
      s.gaps.length ? group("Gaps", s.gaps.map((g) => tag({ kind: "attention", class: "ol-gap" }, g.text))) : null,
      draftBox(s));
  }

  function sectionNode(s) {
    const isOpen = open.has(s.section_id);
    const c = cmp && cmp.sections[s.section_id];
    const toggle = h("button", { class: "ol-title", type: "button", "aria-expanded": isOpen ? "true" : "false", "aria-controls": `ol-b-${s.section_id}` },
      icon(isOpen ? "chevron-down" : "chevron-right", { size: 15 }), h("span", { class: "ol-num" }, s.number), h("span", { class: "ol-name" }, s.title));
    const flags = [];
    if (s.kind === "hypothesis") {
      flags.push(s.hypothesis && s.hypothesis.checked ? statusBadge(s.hypothesis.status, { short: true }) : chip("not checked yet", { title: "Check it to place its themes by the passages that bear on it" }));
      const n = s.children.filter((c) => c.kind === "theme").length;
      flags.push(h("span", { class: "muted small ol-counts" }, plural(n, "theme")));
      if (s.gaps.some((g) => g.kind === "no-themes")) flags.push(chip("no theme", { attention: true, title: s.gaps.map((g) => g.text).join(" ") }));
    } else if (s.kind === "own") flags.push(chip("your own"));
    else {
      flags.push(h("span", { class: "muted small ol-counts" }, `${plural(s.documents, "document")} · ${plural(s.passages, "passage")}`));
      if (s.relevance && s.relevance.evidence) flags.push(chip(`${s.relevance.evidence} evidence`, { icon: "flask", title: `${plural(s.relevance.evidence, "passage")} that the check of the hypothesis counts are in this theme` }));
      if (s.disagreements.length) flags.push(chip(`${s.disagreements.length} disagree`, { attention: true, title: "Documents on both sides of a claim you checked" }));
      if (s.gaps.length) flags.push(chip(s.gaps[0].kind === "one-source" ? "one source" : "gap", { attention: true, title: s.gaps.map((g) => g.text).join(" ") }));
    }
    if (c) flags.push(chip(c.level_text, { title: `${c.terms_used} of ${c.terms_total} key terms · ${c.sources_used} of ${c.sources_total} sources` }));
    const sib = s.siblings, i = s.index;
    const btn = (ic, label, fn, disabled) => iconButton({ icon: ic, size: 15, class: "ol-ctl", label: `${label}: ${s.title}`, title: label, disabled: disabled || null, onClick: fn });
    const parent = s.parent_id ? find(s.parent_id) : null;
    const prev = i > 0 ? flat().find((n) => n.parent_id === s.parent_id && n.index === i - 1) : null;
    const height = (n) => (n.children.length ? 1 + Math.max(...n.children.map(height)) : 0);
    const canNest = !!prev && s.depth + 1 + height(s) <= v.max_depth - 1;
    const controls = h("div", { class: "ol-ctls" },
      btn("arrow-up", "Move up", () => act("POST", `/sections/${P(s.section_id)}/move`, { parent_id: s.parent_id, index: i - 1 }), i === 0),
      btn("arrow-down", "Move down", () => act("POST", `/sections/${P(s.section_id)}/move`, { parent_id: s.parent_id, index: i + 1 }), i >= sib - 1),
      btn("arrow-right", "Put inside the section above", () => { open.add(prev.section_id); act("POST", `/sections/${P(s.section_id)}/move`, { parent_id: prev.section_id, index: null }); }, !canNest),
      btn("arrow-left", "Take out of its section", () => act("POST", `/sections/${P(s.section_id)}/move`, { parent_id: parent ? parent.parent_id : null, index: parent ? parent.index + 1 : null }), !parent),
      menu(s));
    const handle = h("span", { class: "ol-grip", "aria-hidden": "true", title: "Drag to move" }, icon("grip", { size: 15 }));
    const bar = h("div", { class: "ol-bar" }, handle, toggle, h("div", { class: "ol-flags" }, flags), controls);
    const li = h("li", { class: `ol-item${s.state === "gone" || s.state === "removed" ? " ol-broken" : ""}${s.kind === "hypothesis" ? " ol-hyp" : ""}`, "data-id": s.section_id });
    const bodyEl = isOpen ? body(s) : null;
    if (bodyEl) bodyEl.id = `ol-b-${s.section_id}`;
    li.append(bar);
    if (bodyEl) li.append(bodyEl);
    if (s.children.length) li.append(h("ol", { class: "ol-tree" }, s.children.map(sectionNode)));
    toggle.addEventListener("click", () => { if (open.has(s.section_id)) open.delete(s.section_id); else open.add(s.section_id); drawTree(); drawTools(); });
    // drag and drop: the grip starts it; the top of a row drops before it, the bottom after it, the middle inside it
    handle.addEventListener("mousedown", () => { li.draggable = true; });
    li.addEventListener("dragstart", (e) => { if (e.target !== li) return; dragId = s.section_id; e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", s.section_id); li.classList.add("ol-dragging"); });
    li.addEventListener("dragend", () => { dragId = null; li.draggable = false; li.classList.remove("ol-dragging"); clearMarks(); });
    bar.addEventListener("dragover", (e) => {
      if (!dragId || dragId === s.section_id) return;
      e.preventDefault(); e.dataTransfer.dropEffect = "move";
      clearMarks(); bar.classList.add(`ol-drop-${zone(e, bar)}`);
    });
    bar.addEventListener("dragleave", () => bar.classList.remove("ol-drop-before", "ol-drop-after", "ol-drop-inside"));
    bar.addEventListener("drop", (e) => {
      if (!dragId || dragId === s.section_id) return;
      e.preventDefault();
      const z = zone(e, bar), mine = find(dragId);
      clearMarks();
      if (z === "inside") { open.add(s.section_id); return act("POST", `/sections/${P(dragId)}/move`, { parent_id: s.section_id, index: null }); }
      const same = mine && mine.parent_id === s.parent_id && mine.index < s.index ? 1 : 0;
      act("POST", `/sections/${P(dragId)}/move`, { parent_id: s.parent_id, index: s.index + (z === "after" ? 1 : 0) - same });
    });
    return li;
  }
  const zone = (e, el) => { const r = el.getBoundingClientRect(), f = (e.clientY - r.top) / Math.max(1, r.height); return f < 0.33 ? "before" : f > 0.67 ? "after" : "inside"; };
  const clearMarks = () => { for (const el of tree.querySelectorAll(".ol-drop-before, .ol-drop-after, .ol-drop-inside")) el.classList.remove("ol-drop-before", "ol-drop-after", "ol-drop-inside"); };

  // the menu of one section: rename, merge, split, take out
  function menu(s) {
    return menuOf({ label: `More for ${s.title}`, title: "More", class: "ol-more", items: [
      { icon: "note", text: "Rename", onClick: () => renameSection(s) },
      flat().length > 1 && s.kind !== "hypothesis" ? { icon: "layers", text: "Join to another section…", title: "Their themes, notes and inner sections become one section", onClick: () => mergeSection(s) } : null,
      s.can_split ? { icon: "split", text: s.themes.length > 1 ? "Split into its themes" : "Split by documents…", onClick: () => splitSection(s) } : null,
      s.kind === "hypothesis" && !(s.hypothesis && s.hypothesis.checked) ? { icon: "flask", text: "Check it", onClick: () => navigate(checkHref(s.hypothesis_text || s.title)) } : null,
      "sep",
      { icon: "trash", text: "Take out of the outline", danger: true, onClick: () => removeSection(s) },
    ].filter(Boolean) });
  }
  async function renameSection(s) {
    const input = inputEl({ value: s.title, maxlength: 200, "aria-label": "Title of the section" });
    const back = s.kind === "theme" && s.title_source === "you" ? h("p", { class: "muted small" }, `Leave it empty to use the theme's own heading: “${s.default_title}”.`) : null;
    const ok = await dialog({ title: "Rename the section", body: h("div", {}, input, back), actions: [{ text: "Cancel", value: null }, { text: "Save", value: true, primary: true }], onOpen: () => input.focus() });
    if (ok) act("PUT", `/sections/${P(s.section_id)}`, { title: input.value });
  }
  async function mergeSection(s) {
    const sel = selectEl({ "aria-label": "Join to" }, flat().filter((n) => n.section_id !== s.section_id && !isInside(n, s)).map((n) => h("option", { value: n.section_id }, `${n.number} ${shortTitle(n.title, 70)}`)));
    const ok = await dialog({ title: `Join “${shortTitle(s.title, 40)}” to another section`, body: h("div", { class: "stack" }, h("p", {}, "The other section keeps its title and place, and gains this one's themes, passages, notes and the sections inside it."), sel),
      actions: [{ text: "Cancel", value: null }, { text: "Join them", value: true, primary: true }] });
    if (ok && sel.value) act("POST", `/sections/${P(s.section_id)}/merge`, { into: sel.value });
  }
  const isInside = (n, outer) => outer.children.some((c) => c.section_id === n.section_id || isInside(n, c));
  async function splitSection(s) {
    if (s.themes.length > 1) {
      if (!(await confirmDialog({ title: "Split this section?", message: `It becomes ${s.themes.length} sections, one for each of its themes.`, confirmText: "Split", danger: false }))) return;
      return act("POST", `/sections/${P(s.section_id)}/split`, {});
    }
    const boxes = s.sources.map((d) => h("label", { class: "ol-check it" }, h("input", { type: "checkbox", value: d.doc_id }), h("span", {}, shortTitle(d.title, 80), h("span", { class: "muted small" }, ` · ${plural(d.passages, "passage")}`))));
    const ok = await dialog({ title: "Split by documents", wide: false, body: h("div", { class: "stack" }, h("p", {}, "Choose the documents that go to a new section after this one. The others stay."), h("div", { class: "ol-checks" }, boxes)),
      actions: [{ text: "Cancel", value: null }, { text: "Split", value: true, primary: true }] });
    if (!ok) return;
    const docs = boxes.map((b) => b.querySelector("input")).filter((i) => i.checked).map((i) => i.value);
    if (!docs.length || docs.length === s.sources.length) { toast("Choose some of the documents, but not all.", "warn"); return; }
    act("POST", `/sections/${P(s.section_id)}/split`, { doc_ids: docs }, () => open.add(s.section_id));
  }
  async function removeSection(s) {
    const kids = s.children.length ? ` The ${plural(s.children.length, "section")} inside it move up.` : "";
    if (!(await confirmDialog({ title: "Take this section out?", message: `“${shortTitle(s.title, 60)}” and its notes leave the outline.${kids}${s.kind === "theme" ? " You can bring its theme back from “Themes not in the outline”." : ""}`, confirmText: "Take out" }))) return;
    act("DELETE", `/sections/${P(s.section_id)}`);
  }

  function drawTree() {
    if (!v.sections.length) { clear(tree); return; }
    const sum = cmp ? coverSummary() : null;
    replace(tree, sum, cmpError ? notice({ kind: "attention" }, h("p", {}, cmpError)) : null,
      cmp && cmp.meaning && cmp.meaning.available === false ? h("p", { class: "muted small" }, icon("info", { size: 12 }), ` Closeness by meaning: ${cmp.meaning.why}`) : null,
      h("ol", { class: "ol-tree ol-root" }, v.sections.map(sectionNode)));
  }
  function coverSummary() {
    const all = Object.values(cmp.sections).filter((c) => c.kind === "theme");
    const by = (l) => all.filter((c) => c.level === l).length;
    return notice({ kind: "info", icon: "file-pen", class: "ol-summary" },
      h("div", {}, h("p", {}, h("strong", {}, cmp.draft.title || "The draft"), ` (${plural(cmp.draft.words, "word")}) beside the outline: `, `${by("well")} well covered, ${by("partly")} partly, ${by("little")} touched on, ${by("none")} not covered yet.`),
        ...(cmp.notes || []).map((t) => h("p", { class: "small" }, t))));
  }

  function drawSpare() {
    const a = v.available_themes || [];
    if (!a.length) { clear(spare); return; }
    replace(spare, fold({ class: "ol-spare" }, `Themes not in the outline (${a.length})`,
      v.outline.question ? h("p", { class: "muted small" }, "These themes share no key term with your question or hypotheses (or you took them out). Add one if it belongs.") : null,
      listGroup(null, ...a.map((t) => h("li", { class: "list-row" },
        h("div", { class: "list-row-main" }, h("strong", { class: "serif" }, t.name),
          h("span", { class: "list-row-sub" }, `${plural(t.documents, "document")}, ${plural(t.size, "passage")}${t.bears_on && t.bears_on.length ? ` · bears on ${t.bears_on.join(", ")}` : ""}`)),
        h("span", { class: "list-row-actions" }, button({ sm: true, icon: "plus", onClick: () => act("POST", "/sections", { theme_id: t.theme_id }) }, "Add")))))));
  }
  function drawTech() {
    replace(tech, fold({}, "Technical details",
      h("div", { class: "small" },
        h("p", {}, "The order is a path through the themes. It starts with the theme that has most passages and goes on to the most similar theme not used yet; then stretches of the path are reversed while that raises the total similarity between neighbours (2-opt). The similarity of two themes is half the cosine of their passage counts per document and half the share of key-term words they have in common. The same themes always give the same order."),
        v.outline.question ? h("p", {}, "In an outline from a research question, a theme bears on a hypothesis through the passages its check counts for or against it (they weigh most), and through the key terms they share: a term whose every word is in the hypothesis counts fully, one sharing some words half as much, and a word found in the key terms of many themes counts less. A key term of the same concept as a term of the hypothesis (Concepts) counts fully. Each theme goes to the hypothesis it bears on most; themes that bear only on the question go under Background; the rest stay out. A hypothesis section is linked to its check by its wording.") : null,
        h("p", {}, "Headings come from the themes: the name the AI gave (Themes → Let the AI name the themes), your own rename, or else the first key terms. The outline is stored in the project and survives a reload; it does not change when you find the themes again."),
        h("p", { class: "mono" }, `outline ${oid} · themes ${v.outline.run_id}`))));
  }

  function draw() { drawHead(); drawTools(); drawTree(); drawSpare(); drawTech(); }
  draw();
  if (draftId) load({ keepScroll: false });
  return () => {};
}
