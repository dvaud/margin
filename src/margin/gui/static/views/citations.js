// 0.13.7: Check citations. A text (your draft, pasted or from a file, or a document of the project) is read for its
// citations; each cited work of the bibliography whose document is in the project is checked against that document
// only, with the claim's sentences as context. "Source accurate", or a notice: only partly supported, not found in
// the source, the source says otherwise. Each answer opens on the result page, where a person can overrule it.
// Margin: a text you paste or choose is kept as a draft (Check a draft), and every draft's citations are listed here;
// a draft's text links back to its draft, and its name and AI setting are the draft's.
import { featureEyebrow } from "../features.js";
import { App, api, h, icon, replace, clear, toast, showError, fmt, pageHead, watchJob, P, confirmDialog, emptyState,
  session, download, plural, statusBadge, helpMark, downloadLinks, navigate, runningJob, TERMINAL,
  button, fileButton, link, notice, tag, fold, field, input as inputEl, textarea as textareaEl, select as selectEl, choice,
  card as makeCard, withAI, readsLine, aiWhere, inset, listGroup, judgementIcon } from "../lib.js";
import { ProgressPanel } from "./progress.js";
import { accessChoice, accessBadge, LEVEL, levels } from "./ai-access.js";

const NOTICES = ["contradicted", "partly", "mixed", "not_found", "unsure", "failed"];
const BLOCKED = ["ambiguous", "no_work", "no_document", "to_confirm", "same_document"];
const LEFT_OUT = ["contrast", "ignored"];
const FILE_TYPES = ".docx,.pdf,.txt,.md,.html,.htm";

export async function renderCitations(view, [textId], query) {
  return textId ? renderText(view, textId, query) : renderList(view);
}

// ---------------------------------------------------------------------------------------------------- the texts
async function renderList(view) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/citations`;
  view.appendChild(pageHead("Check citations", {
    eyebrow: featureEyebrow("citations"),
    sub: "Whether each source you cite says what your text says it does.",
  }));
  let data;
  try { data = await api("GET", base); } catch (e) { showError(e); return; }
  if (!data.has_bibliography) {
    view.appendChild(notice({ kind: "info", icon: "library", class: "cite-notice" },
      h("p", {}, h("strong", {}, "Bring in your bibliography first. "), "Each citation is matched with a work of your Zotero library, and checked against that work’s document in this project."),
      h("p", {}, link({ kind: "next", href: "#/bibliography" }, "Open the Bibliography"))));
  }
  const texts = data.texts || [];
  if (texts.length) {
    view.appendChild(h("section", { class: "section", "aria-label": "Your texts" },
      h("div", { class: "section-title" }, h("h2", {}, "Your texts")),
      makeCard({ class: "cite-texts-card" }, listGroup(null, ...texts.map(textRow)))));
  }
  view.appendChild(addCard(project, base, data, !texts.length));
}

function countsLine(c, t) {
  const notices = NOTICES.reduce((n, k) => n + (c[k] || 0), 0);
  const blocked = BLOCKED.reduce((n, k) => n + (c[k] || 0), 0);
  return [
    `${plural(t.citations, "citation", "citations")}`,
    c.accurate ? `${c.accurate} source accurate` : null,
    notices ? `${notices} to look at` : null,
    c.checking ? `${c.checking} being checked` : null,
    c.ready ? `${c.ready} not checked yet` : null,
    blocked ? `${blocked} cannot be checked yet` : null,
  ].filter(Boolean).join(" · ");
}

// One text of the list: its name is the link; under it where it came from and what its citations say
function textRow(t) {
  const c = t.counts || {};
  const notices = NOTICES.reduce((n, k) => n + (c[k] || 0), 0);
  return h("li", { class: "list-row cite-text-row" },
    h("div", { class: "list-row-main" },
      link({ kind: "title", serif: true, href: `#/citations/${encodeURIComponent(t.text_id)}` }, t.title),
      h("span", { class: "list-row-sub" }, `${t.draft_id ? "Your draft" : t.source_text}${t.file_name ? ` (${t.file_name})` : ""} · added ${fmt.dateShort(t.created_at)}`),
      h("span", { class: "list-row-sub" }, countsLine(c, t))),
    h("span", { class: "list-row-actions" }, notices ? tag({ kind: "attention" }, plural(notices, "notice", "notices")) : null));
}

function addCard(project, base, data, open) {
  const dflt = (data.ai_access && data.ai_access.default) || "cloud";
  let mode = session("cite-mode") || "paste";
  const titleIn = inputEl({ id: "cite-title", placeholder: "For example: Chapter 2, draft of 5 November", maxlength: 200 });
  const ta = textareaEl({ id: "cite-text", rows: 10, spellcheck: "false",
    placeholder: "Paste your text with its citations, for example:\n\nHybrid workers commute fewer hours a week (Verhoeven & Okafor, 2025). According to Lindqvist et al. (2025), loneliness rises among young employees." });
  ta.value = session("cite-draft") || "";
  ta.addEventListener("input", () => session("cite-draft", ta.value));
  const fileIn = h("input", { type: "file", id: "cite-file", accept: FILE_TYPES });
  const fileName = h("span", { class: "muted small" }, "No file chosen");
  fileIn.addEventListener("change", () => { fileName.textContent = fileIn.files && fileIn.files[0] ? fileIn.files[0].name : "No file chosen"; });
  const docSel = selectEl({ id: "cite-doc" }, h("option", { value: "" }, "Loading the documents…"));
  const ai = accessChoice({ value: dflt, many: false, name: "cite-ai" });
  const legend = ai.querySelector("legend");
  if (legend) legend.textContent = "Who may read your text with AI?";
  const aiNote = h("p", { class: "muted small", hidden: true }, icon("shield", { size: 12 }), " The document keeps its own AI setting (Documents page).");
  const go = button({ kind: "main", type: "submit", icon: "search" }, "Find the citations");
  const note = h("span", { class: "muted small" }, "No AI is used to find them; nothing is checked yet.");

  const panes = {
    paste: h("div", { class: "cite-pane" }, field("Your text", ta)),
    file: h("div", { class: "cite-pane" }, field("Your file", h("div", { class: "row" }, fileButton({ kind: "standard", icon: "upload" }, fileIn, "Choose a file"), fileName),
      { help: "Word, PDF, text or Markdown. Read on this computer and kept as a draft; it is not added to your documents." })),
    document: h("div", { class: "cite-pane" }, field("A document of this project", docSel)),
  };
  const where = choice({ label: "Where the text is", class: "cite-seg", value: mode,
    options: [["paste", [icon("type", { size: 13 }), "Paste your text"]], ["file", [icon("upload", { size: 13 }), "Choose a file"]], ["document", [icon("book-open", { size: 13 }), "A document of this project"]]],
    onPick: (k) => { mode = k; session("cite-mode", k); show(); } });
  const form = h("form", { class: "stack", onSubmit: (e) => { e.preventDefault(); submit(); } },
    where, panes.paste, panes.file, panes.document,
    field(["Name ", h("span", { class: "muted" }, "(optional)")], titleIn),
    ai, aiNote,
    h("div", { class: "btn-row" }, go, note));
  const card = makeCard({ class: "cite-add", title: "A text to check", titleId: "cite-add-h" },
    h("p", { class: "muted cite-add-intro" },
      "Paste your draft, choose its file, or pick a document of this project. Margin finds citations such as (Smith, 2020), Smith et al. (2020) and [3] with a numbered reference list, and the claim each one stands for. ",
      "Your text is kept as a draft, so ", link({ href: "#/drafts" }, "Check a draft"), " can also show which of its statements still need a source; the citations of every draft are listed above."),
    fold({ open: open || null, class: "cite-add-fold" }, open ? "Check a text" : "Check another text", form));

  function show() {
    for (const [k, el] of Object.entries(panes)) el.hidden = k !== mode;
    where.set(mode);
    ai.hidden = mode === "document";
    aiNote.hidden = mode !== "document";
  }
  show();

  api("GET", `/api/projects/${P(project)}/documents`).then((r) => {
    const docs = r.documents || [];
    replace(docSel, docs.length ? [h("option", { value: "" }, "Choose a document…"), ...docs.map((d) => h("option", { value: d.doc_id }, d.title || d.file || d.doc_id))]
      : h("option", { value: "" }, "This project has no documents yet"));
  }).catch(() => replace(docSel, h("option", { value: "" }, "The documents could not be listed")));

  async function submit() {
    const body = { title: titleIn.value.trim() || null };
    if (mode !== "document") body.ai_access = ai.value || dflt;
    go.disabled = true;
    replace(go, icon("loader", { size: 14 }), "Reading…");
    try {
      if (mode === "paste") {
        if (!ta.value.trim()) throw new Error("Paste your text first.");
        body.text = ta.value;
      } else if (mode === "file") {
        const f = fileIn.files && fileIn.files[0];
        if (!f) throw new Error("Choose a file first.");
        const batch = `cite-${Date.now().toString(36)}`;
        await api("POST", `/api/projects/${P(project)}/uploads?batch=${batch}&name=${encodeURIComponent(f.name)}`, f);
        body.upload = { batch, name: f.name };
      } else {
        if (!docSel.value) throw new Error("Choose a document first.");
        body.doc_id = docSel.value;
      }
      const v = await api("POST", base, body);
      if (mode === "paste") session("cite-draft", null);
      toast(`${plural(v.citations, "citation", "citations")} found.${v.draft ? " Your text is kept as a draft." : ""}`, "ok", { ttl: 3000 });
      navigate(`#/citations/${encodeURIComponent(v.text.text_id)}`);
    } catch (e) {
      showError(e);
      go.disabled = false;
      replace(go, icon("search", { size: 14 }), "Find the citations");
    }
  }
  return card;
}

// ---------------------------------------------------------------------------------------------------- one text
async function renderText(view, textId, query) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/citations/${P(textId)}`;
  const head = h("div");
  const top = h("div");
  const progressBox = h("section", { class: "section", hidden: true, "aria-label": "Progress of the checks" });
  const body = h("div", { class: "cite-body" });
  view.append(head, top, progressBox, body);
  let data = null;
  let watcher = null;
  let following = null;
  let poll = null;

  async function load() {
    try { data = await api("GET", base); }
    catch (e) {
      if (e.status === 404) { replace(view, emptyState("search-x", "This text is no longer here", "It was removed, or belongs to another project.", link({ kind: "next", href: "#/citations" }, "All texts"))); return; }
      showError(e); return;
    }
    draw();
  }

  function draw() {
    const t = data.text;
    const draft = data.draft;  // Margin: the citations of one of your drafts
    replace(head, pageHead(t.title, {
      display: true,
      back: draft ? { href: `#/drafts/${encodeURIComponent(draft.draft_id)}`, text: "Back to your draft" } : { href: "#/citations", text: "All texts" },
      facts: [`${draft ? "Your draft" : t.source_text}${t.file_name ? ` (${t.file_name})` : ""}`, `${plural(data.citations, "citation", "citations")} of ${plural(data.works, "work", "works")} from your bibliography`],
    }));
    replace(top, summaryCard());
    drawGroups();
    const target = query.ref && body.querySelector(`[data-ref="${CSS.escape(query.ref)}"]`);
    if (target && !draw.scrolled) { draw.scrolled = true; target.classList.add("cite-card-target"); setTimeout(() => target.scrollIntoView({ block: "center" }), 60); }
    clearTimeout(poll);
    if (data.checking && !following) poll = setTimeout(load, 5000);  // checks waiting for Claude Code: look again
  }

  function summaryCard() {
    const t = data.text;
    const c = data.counts || {};
    const notices = data.notices || 0;
    const ready = data.ready || 0;
    const tiles = [
      ["notices", "To look at", notices, () => icon("eye", { size: 13 })],
      ["accurate", "Source accurate", c.accurate || 0, () => judgementIcon("supports", 13)],
      ["blocked", "Cannot be checked yet", BLOCKED.reduce((n, k) => n + (c[k] || 0), 0), () => judgementIcon("none", 13)],
      ["ready", c.checking ? "Being checked" : "Not checked yet", ready + (c.checking || 0), () => icon(c.checking ? "loader" : "clock", { size: 13 })],
    ];
    const level = data.draft ? t.level : t.ai_access;
    const run = ready ? button({ kind: "main", icon: "play", onClick: () => start({}) }, `Check ${ready === 1 ? "this citation" : `${ready} citations`}`) : null;
    const levelSel = t.doc_id ? null : selectEl({ sm: true, id: "cite-level", "aria-label": "Who may read this text with AI" },
      ...levels().map((lv) => h("option", { value: lv, selected: lv === level }, LEVEL[lv].title)));
    if (levelSel) levelSel.addEventListener("change", async () => {
      try { data = await api("PUT", base, { ai_access: levelSel.value }); toast("Saved.", "ok", { ttl: 1500 }); draw(); } catch (e) { showError(e); }
    });
    return makeCard({ class: "cite-summary", "aria-label": "Summary" },
      h("div", { class: "cite-tiles" }, tiles.map(([k, label, n, ic]) => inset({ class: `cite-tile cite-tile-${k}` },
        h("span", { class: "cite-tile-n" }, fmt.num(n)),
        link({ kind: "jump", class: "cite-tile-label", onClick: () => { const g = body.querySelector(`[data-group="${k}"]`); if (g) g.scrollIntoView({ block: "start", behavior: "smooth" }); } }, ic(), label)))),
      h("div", { class: "cite-run" },
        level === "none" ? run : withAI(run),
        h("p", { class: "muted small grow" }, ready
          ? "Each claim is checked against its source’s document only. It takes a minute or two per citation."
          : notices || c.accurate ? "Every citation that can be checked has been checked. Open one to read its excerpts or to overrule the answer." : "Nothing can be checked yet: see below what each citation needs.")),
      !ready || level === "none" ? null
        : level === "local" ? aiWhere("Only a model on this computer reads the claim, the sentences around it and excerpts of the source.", "local")
        : readsLine("the claim, the sentences around it and excerpts of the source"),
      h("div", { class: "cite-foot small" },
        h("span", { class: "it" }, icon("shield", { size: 12 }), "Your text: ", t.doc_id ? [accessBadge(t.level, { long: true }), h("span", { class: "muted" }, " (the document’s own setting)")] : levelSel),
        downloadLinks([{ text: "Excel (.xlsx)", onClick: () => download(`${base}/export.xlsx`, `citations.xlsx`) }]),
        data.draft ? link({ class: "it", href: `#/drafts/${encodeURIComponent(data.draft.draft_id)}` }, icon("file-pen", { size: 12 }), "Open your draft")
          : button({ kind: "danger", sm: true, icon: "trash", onClick: remove }, "Remove this text")),
      data.text.numeric_unread ? notice({ kind: "attention", class: "cite-warn" }, h("p", {}, `${plural(data.text.numeric_unread, "numbered citation", "numbered citations")} ([1], [2]…) could not be read: the text has no numbered reference list. Paste the text with its reference list.`)) : null,
      data.text.cut ? notice({ kind: "attention", class: "cite-warn" }, h("p", {}, "Only the first 500 citations were read. Split a longer text into parts.")) : null);
  }

  function drawGroups() {
    clear(body);
    const refs = data.refs || [];
    const by = (keys) => refs.filter((r) => keys.includes(r.state === "checked" ? r.verdict : r.state));
    const groups = [
      ["notices", "To look at", "The source does not say all of what the sentence says, or says otherwise.", by(NOTICES), cardFull],
      ["ready", "Being checked", null, by(["checking"]), cardFull],
      ["ready", "Not checked yet", null, by(["ready"]), cardSmall],
      ["blocked", "Cannot be checked yet", "Each needs a work of your bibliography whose document is in this project.", by(BLOCKED), cardBlocked],
      ["accurate", "Source accurate", "An excerpt of the source says what the sentence says.", by(["accurate"]), cardAccurate],
    ];
    let any = false;
    for (const [key, title, sub, list, draw1] of groups) {
      if (!list.length) continue;
      any = true;
      body.appendChild(h("section", { class: "section cite-group", "data-group": key, "aria-label": title },
        h("div", { class: "section-title" }, h("h2", {}, title, " ", tag({ kind: "count" }, String(list.length))), sub ? h("span", { class: "muted" }, sub) : null),
        h("ul", { class: "cite-list" }, list.map((r) => h("li", { "data-ref": r.ref_id }, draw1(r))))));
    }
    const left = by(LEFT_OUT);
    if (left.length) {
      body.appendChild(fold({ class: "cite-left" }, `Left out (${left.length})`,
        h("ul", { class: "cite-list" }, left.map((r) => h("li", { "data-ref": r.ref_id }, cardLeft(r))))));
    }
    if (!any && !left.length) body.appendChild(emptyState("quote", "No citations", "No citation was found in this text."));
  }

  // -------- the pieces of a card
  function sentence(r, withBefore) {
    const s = r.sentence || "";
    const at = r.claim_at;
    const parts = at ? [s.slice(0, at[0]), h("mark", { class: "cite-claim" }, s.slice(at[0], at[1])), s.slice(at[1])] : [s];
    return h("p", { class: "cite-sentence serif" },
      withBefore && r.before ? h("span", { class: "cite-before" }, `…${r.before.length > 220 ? r.before.slice(-220) : r.before} `) : null,
      parts);
  }

  function workLine(r) {
    const w = r.work;
    if (!w) return null;
    return h("p", { class: "cite-work small" }, icon("library", { size: 12 }), h("strong", {}, w.cite || "A work"), " ", h("span", { class: "muted" }, w.title || ""),
      r.how === "person" ? h("span", { class: "muted" }, " · you chose it") : null);
  }

  function meta(r) {
    return h("span", { class: "cite-meta muted small" }, r.page ? `page ${r.page} of your text · ` : "", h("span", { class: "mono" }, r.raw));
  }

  function quote(r) {
    const q = r.quote;
    if (!q) return null;
    return h("blockquote", { class: "cite-quote" }, h("span", { class: "serif" }, `“${q.quote}”`),
      h("span", { class: "muted small" }, ` ${[q.page ? `page ${q.page}` : null, q.title].filter(Boolean).join(", ")}`));
  }

  function verdict(r) {
    return h("span", { class: "it" }, statusBadge(r.status, { text: r.verdict_text }), r.verdict_help ? helpMark("What this means", r.verdict_help) : null,
      r.corrected ? h("span", { class: "muted small" }, "· you changed a judgement") : null);
  }

  const entry = (r, extra, ...kids) => makeCard({ as: "article", sm: true, class: `cite-card${extra ? ` ${extra}` : ""}` }, ...kids);

  function cardFull(r) {
    return entry(r, "",
      h("div", { class: "cite-head" }, verdict(r), meta(r)),
      sentence(r, true), workLine(r), quote(r),
      r.hyp_id ? h("div", { class: "cite-actions small" },
        link({ href: `#/h/${encodeURIComponent(r.hyp_id)}` }, "See the excerpts and judge them"),
        r.verdict === "failed" ? withAI(button({ kind: "quiet", sm: true, onClick: () => start({ ref_ids: [r.ref_id], again: true }) }, "Check again")) : null) : null,
      r.hyp_id && r.verdict === "failed" ? readsLine("the claim, the sentences around it and excerpts of the source") : null);
  }

  function cardSmall(r) {
    return entry(r, "", h("div", { class: "cite-head" }, meta(r)), sentence(r, false), workLine(r));
  }

  function cardAccurate(r) {
    return entry(r, "",
      h("div", { class: "cite-head" }, verdict(r), meta(r)), sentence(r, false), workLine(r),
      h("div", { class: "cite-actions small" }, link({ href: `#/h/${encodeURIComponent(r.hyp_id)}` }, "See the excerpts")));
  }

  function cardLeft(r) {
    return entry(r, "",
      h("div", { class: "cite-head" }, tag({}, r.state_text), meta(r)), sentence(r, false),
      h("div", { class: "cite-actions small" }, button({ kind: "quiet", sm: true, onClick: () => setRef(r, { ignored: false }) }, "Put it back")));
  }

  function cardBlocked(r) {
    const actions = h("div", { class: "cite-actions small" });
    if (r.state === "no_work" || r.state === "ambiguous") {
      const cands = r.candidates || [];
      const sel = selectEl({ sm: true, "aria-label": `Which work ${r.raw} is` },
        h("option", { value: "" }, r.state === "ambiguous" ? "Which of them?" : cands.length ? "Did you mean…" : "Choose the work…"),
        cands.length ? h("optgroup", { label: r.state === "ambiguous" ? "Works that match" : "Close: the same author, another year" }, cands.map((w) => h("option", { value: w.key }, `${w.cite} · ${w.title}`))) : null,
        h("optgroup", { label: "Your bibliography" }, (data.bibliography_works || []).filter((w) => !cands.some((c) => c.key === w.key)).map((w) => h("option", { value: w.key }, `${w.cite} · ${w.title}`))));
      sel.addEventListener("change", () => { if (sel.value) setRef(r, { item_key: sel.value }); });
      actions.append(sel, button({ kind: "quiet", sm: true, onClick: () => setRef(r, { ignored: true }) }, "Not a citation"));
    } else if (r.state === "no_document") {
      actions.append(h("span", { class: "muted" }, "Add its document on the ", link({ href: "#/bibliography" }, "Bibliography page"), " (To find)."));
    } else if (r.state === "to_confirm") {
      actions.append(h("span", { class: "muted" }, "Confirm its document on the ", link({ href: "#/bibliography" }, "Bibliography page"), "."));
    }
    if (r.how === "person") actions.append(button({ kind: "quiet", sm: true, onClick: () => setRef(r, { item_key: null }) }, "Undo my choice"));
    return entry(r, "",
      h("div", { class: "cite-head" }, tag({}, r.state_text), meta(r)),
      sentence(r, false), workLine(r), actions);
  }

  // -------- actions
  async function setRef(r, change) {
    try { data = await api("PUT", `${base}/refs/${P(r.ref_id)}`, change); draw(); }
    catch (e) { showError(e); }
  }

  async function remove() {
    const ok = await confirmDialog({ title: "Remove this text?", message: `“${data.text.title}”, its citations and their checks are removed from the project. Your file and your documents are not touched.`, confirmText: "Remove" });
    if (!ok) return;
    try { await api("DELETE", base); toast("Removed.", "ok", { ttl: 2000 }); navigate("#/citations"); } catch (e) { showError(e); }
  }

  async function start(change) {
    try {
      const r = await api("POST", `${base}/check`, change);
      follow(r.job.id);
    } catch (e) { showError(e); }
  }

  function follow(jobId) {
    if (watcher) watcher.stop();
    following = jobId;
    clearTimeout(poll);
    const panel = new ProgressPanel({ title: "Checking the citations", batchWords: { doing: "checking citation", done: "citations checked" } });
    replace(progressBox, h("div", { class: "section-title" }, h("h2", {}, "Checking"), h("span", { class: "muted" }, "you can leave this page; the checks continue")), panel.el);
    progressBox.hidden = false;
    let n = 0;
    watcher = watchJob(jobId, (job) => {
      panel.update(job);
      if (++n % 10 === 0) load();  // the answers appear as they come
    });
    watcher.promise.then((job) => {
      following = null;
      progressBox.hidden = true;
      const r = job.result || {};
      if (job.state === "done") toast(`${plural((r.checked || []).length, "citation", "citations")} checked${(r.errors || []).length ? `; ${r.errors.length} could not be` : ""}.`, (r.errors || []).length ? "warn" : "ok");
      else if (job.state === "error") showError(new Error(job.error || "The checks could not continue."));
      load();
    }).catch((e) => { following = null; showError(e); });
  }

  await load();
  const active = query.job ? { id: query.job } : await runningJob(project, ["citations"], (j) => j.scope === textId).catch(() => null);
  if (active && active.id) {
    try {
      const job = await api("GET", `/api/jobs/${P(active.id)}`);
      if (job.kind === "citations" && !TERMINAL.has(job.state)) follow(job.id);
    } catch (_) { /* gone */ }
  }
  return () => { if (watcher) watcher.stop(); clearTimeout(poll); };
}
