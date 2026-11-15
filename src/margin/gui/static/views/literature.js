// Margin: Find literature. Three things on one page, none of them AI: search for works to cite (for a claim no document
// supports, or for words you type), follow what your documents cite and who cites them, and keep searches that say what
// is new. Words go to OpenAlex (and, if you choose, Crossref or Semantic Scholar) only after you have seen them, never
// when cloud services are off for good, and never from a draft or document whose AI setting keeps it on this computer.
// Works you choose go to Zotero (its connector on this computer) or download as RIS or BibTeX.
import { featureEyebrow } from "../features.js";
import { App, api, h, icon, replace, clear, toast, showError, fmt, pageHead, P, plural, session, spinner, emptyState, field,
  confirmDialog, shortTitle, button, downloadButton, link, notice, tag, fold, workState, switchControl, input as inputEl, textarea as textareaEl, select as selectEl,
  choice, optionCards, tabs as tabsOf, card as makeCard } from "../lib.js";

const TABS = [["search", "Search", "search"], ["citations", "Follow citations", "link"], ["alerts", "Saved searches", "clock"]];
const STATUS_CHIP = { unsupported: "Nothing backs it", no_passages: "No document is close", uncertain: "Only weak evidence" };
const STALE_HOURS = 6;

const ago = (iso) => {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!(s >= 0)) return fmt.dateShort(iso);
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} minutes ago`;
  if (s < 86400) return `${Math.round(s / 3600)} hours ago`;
  return fmt.dateShort(iso);
};
const staleSearch = (s) => !s.last_checked_at || (Date.now() - new Date(s.last_checked_at).getTime()) > STALE_HOURS * 3600 * 1000;

function authorsLine(w) {
  const a = w.authors || [];
  if (!a.length) return "";
  return a.length > 3 ? `${a.slice(0, 3).join("; ")}; et al.` : a.join("; ");
}

// How close a work is, in words, relative to the closest one found (the number itself means little).
function closeWord(w, max) {
  if (w.closeness === undefined || !max) return null;
  const r = w.closeness / max;
  return r >= 0.66 ? "Very close" : r >= 0.33 ? "Close" : "Loosely related";
}

// A choice of works: what is ticked in lists that come and go, kept by the work's key.
class Chosen {
  constructor(onChange) { this.map = new Map(); this.onChange = onChange; }
  has(w) { return this.map.has(w.key); }
  toggle(w, on) { if (on) this.map.set(w.key, w); else this.map.delete(w.key); this.onChange(); }
  list() { return [...this.map.values()]; }
  clear() { this.map.clear(); this.onChange(); }
}

function errorNotice(e, again) {
  return notice({ kind: "attention", icon: e.kind === "rate_limited" ? "clock" : null, live: "alert" },
    h("p", {}, e.message || String(e)), again ? button({ kind: "quiet", sm: true, icon: "refresh", onClick: again }, "Try again") : null);
}

export async function renderLiterature(view, _params, query) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/literature`;
  view.appendChild(pageHead("Find literature", {
    eyebrow: featureEyebrow("literature"),
    sub: "Search for works to cite, follow what your documents cite, and keep an eye on new work on a topic. No AI is used; you see every word before it is sent.",
  }));
  let info;
  try { info = await api("GET", base); } catch (e) { showError(e); return; }
  const wide = h("div", { class: "lit" });
  view.appendChild(wide);
  wide.appendChild(privacyCard(info));
  if (info.local_only) {
    wide.appendChild(emptyState("shield", "Online lookups are switched off here", "Cloud services are off for good on this computer, so Margin sends no words to OpenAlex or any other service. Your saved searches are kept for a computer that may."));
    return;
  }

  // ---- the works chosen (one choice for the page: Zotero and the downloads act on it) ----------------------------------
  const bar = actionBar(info);
  const chosen = new Chosen(() => bar.update(chosen.list()));
  bar.chosen = chosen;

  // ---- tabs --------------------------------------------------------------------------------------------------------------
  const tabKey = `lit-tab:${project}`;
  let tab = TABS.some(([k]) => k === query.tab) ? query.tab : query.draft ? "search" : session(tabKey) || "search";
  const panels = {};
  for (const [k] of TABS) panels[k] = h("div", { class: "lit-panel", "data-panel": k, hidden: true });
  const panelBox = h("div", { class: "lit-panels" }, panels.search, panels.citations, panels.alerts);
  const nav = tabsOf({ label: "Find literature", class: "lit-tabs", items: TABS.map(([key, label, ic]) => ({ key, label, icon: ic })), current: tab, panel: panelBox, onTab: (k) => show(k) });
  wide.append(nav, panelBox, bar.el);
  function show(k) {
    tab = k;
    session(tabKey, k);
    for (const [key] of TABS) panels[key].hidden = key !== k;
  }
  const alerts = alertsPanel(panels.alerts, { base, info, chosen, setBadge: (n) => nav.setCount("alerts", n ? `${n} new` : "") });
  searchPanel(panels.search, { base, info, chosen, query, onSaved: () => alerts.reload() });
  citationsPanel(panels.citations, { base, info, chosen });
  show(tab);
  nav.setCount("alerts", ((n) => (n ? `${n} new` : ""))((info.searches || []).reduce((n, s) => n + (s.new || 0), 0)));
  alerts.autoCheck();
  return () => { alerts.stop(); };
}

// ---------------------------------------------------------------------------------------------
// what goes out, in words
// ---------------------------------------------------------------------------------------------
function privacyCard(info) {
  const mail = info.email;
  return notice({ kind: "info", icon: "shield", class: "lit-privacy", "aria-label": "What goes online" },
    info.local_only
      ? h("p", {}, h("strong", {}, "Nothing is sent. "), "Cloud services are switched off for good on this computer.")
      : [h("p", {}, h("strong", {}, "Only words you have seen leave this computer. "),
        "A search sends its search words to OpenAlex (openalex.org), a free index of scholarly works; following citations sends the DOIs of your documents. A draft or document whose AI setting keeps it on this computer is never used."),
      h("p", { class: "muted small" }, mail
        ? `Your e-mail address (${mail}) goes along with lookups to OpenAlex, Crossref and Unpaywall, so they can reach you if you ask for much. `
        : "No e-mail address is sent. OpenAlex works without one; Unpaywall, which finds more open copies, needs one. ",
      link({ href: "#/settings/literature" }, mail ? "Change it in Settings" : "Add one in Settings if you wish"), ".")]);
}

function sentLine(info, source, words, when = "you press Search") {
  const s = info.sources.find((x) => x.id === source) || info.sources[0];
  const w = (words || "").trim();
  // what goes online (not to an AI): a notice that follows the words as they are typed, read when the reader is free
  return notice({ kind: "info", icon: "external-link", class: "lit-sent", live: "status" }, h("p", {},
    w ? ["Only these words go to ", h("strong", {}, s.name), ` (${s.site}): `, h("strong", { class: "lit-words-sent" }, w), ". "] : `Type search words: they go to ${s.name} (${s.site}) when ${when}. `,
    info.email && source !== "semanticscholar" ? `Your address (${info.email}) goes with them.` : ""));
}

// ---------------------------------------------------------------------------------------------
// a work, and the bar for what to do with the works chosen
// ---------------------------------------------------------------------------------------------
function workCard(w, chosen, opts = {}) {
  const c = chosen.has(w);
  const box = h("input", { type: "checkbox", class: "lit-check", checked: c, "aria-label": `Choose: ${shortTitle(w.title, 90)}` });
  box.addEventListener("change", () => { chosen.toggle(w, box.checked); li.toggleAttribute("data-chosen", box.checked); });
  const href = w.url || (w.doi ? `https://doi.org/${w.doi}` : null);
  const title = href ? link({ kind: "external", href, title: "Opens the publisher's or index's page in a new tab" }, w.title) : w.title;
  const meta = [authorsLine(w), w.year, w.venue].filter(Boolean).join(" · ");
  const chips = [];
  const cw = closeWord(w, opts.maxClose);
  if (cw) chips.push(tag({ title: opts.closeNote || "How close this work is to what you searched for" }, cw));
  if (opts.themes && w.theme && w.theme_close) chips.push(tag({ icon: "shapes", title: `Closest of your themes: ${w.theme}` }, shortTitle(w.theme, 28)));
  if (w.have) chips.push(tag({ icon: "check", title: w.have.title || "" }, w.have.where === "documents" ? "Already in your documents" : "Already in your bibliography"));
  if (w.n_docs) chips.push(tag({ icon: "link", title: (w.doc_titles || []).join("\n") }, `Connects ${w.n_docs} of your documents`));
  chips.push(tag({}, `Cited ${fmt.num(w.cited_by || 0)}×`));
  const open = w.open;
  const openLink = open && (open.pdf_url || open.url)
    ? link({ kind: "external", class: "lit-open", href: open.pdf_url || open.url, title: `Found by ${open.found_by || "an open-access index"}${open.license ? ` · licence ${open.license}` : ""}` }, open.pdf_url ? "Open PDF" : "Open copy")
    : h("span", { class: "lit-noopen muted small", "data-doi": w.doi || "" }, "No open copy found");
  const li = makeCard({ as: "li", sm: true, class: "lit-work", "data-key": w.key, "data-chosen": c ? "true" : null },
    box,
    h("div", { class: "lit-main" },
      h("h3", { class: "lit-title" }, title),
      meta ? h("p", { class: "lit-meta muted small" }, meta) : null,
      h("div", { class: "lit-chips" }, chips, openLink),
      w.abstract ? fold({ sm: true, class: "lit-abstract" }, "Abstract", h("p", {}, w.abstract)) : null,
      opts.docs && (w.doc_titles || []).length ? fold({ sm: true, class: "lit-abstract" }, "Which of your documents",
        h("ul", { class: "lit-doclist" }, w.doc_titles.map((t) => h("li", {}, t)))) : null));
  li.workRef = w;
  return li;
}

function workList(works, chosen, opts = {}) {
  const max = Math.max(0, ...works.map((w) => w.closeness || 0));
  return h("ol", { class: "lit-works" }, works.map((w) => workCard(w, chosen, { ...opts, maxClose: max })));
}

function actionBar(info) {
  const attach = switchControl("Let Zotero fetch the open PDFs too (Zotero itself downloads them)", true);
  const count = h("span", { class: "lit-bar-count" });
  const note = h("p", { class: "lit-bar-note muted small", "aria-live": "polite" });
  const zotero = button({ kind: "main", sm: true, icon: "library" }, "Send to Zotero");
  const ris = downloadButton({}, "RIS");
  const bib = downloadButton({}, "BibTeX");
  const clearBtn = button({ kind: "quiet", sm: true }, "Clear");
  const el = makeCard({ as: "div", sm: true, class: "lit-bar", hidden: true, role: "region", "aria-label": "Works you chose" },
    h("div", { class: "lit-bar-row" }, count, h("div", { class: "btn-row" }, zotero, h("span", { class: "lit-bar-dl muted small" }, "or download"), ris, bib, clearBtn)),
    attach, note);
  const out = { el, chosen: null, target: null };
  let busy = false;
  async function target() {
    if (out.target) return out.target;
    try { out.target = await api("GET", "/api/literature/zotero"); } catch (_) { out.target = { state: "not_running" }; }
    out.targetAt = Date.now();
    return out.target;
  }
  out.update = async (list) => {
    el.hidden = !list.length;
    count.textContent = list.length ? `${plural(list.length, "work")} chosen` : "";
    if (!list.length) { note.textContent = ""; return; }
    if (Date.now() - (out.targetAt || 0) > 15000) out.target = null;   // Zotero may be opened or closed meanwhile
    const t = await target();
    note.textContent = t.state === "ready"
      ? `Zotero is open${t.collection ? `: the works go into “${t.collection}”${t.library ? ` (${t.library})` : ""}, the collection selected in Zotero.` : "."}`
      : "Zotero is not open. Open it and choose a collection to send there, or download a file to import.";
  };
  const works = () => out.chosen.list().map(({ have, closeness, theme, theme_close, n_docs, docs, doc_titles, ...w }) => w);
  zotero.addEventListener("click", async () => {
    if (busy) return;
    busy = true; zotero.disabled = true;
    try {
      const r = await api("POST", "/api/literature/zotero", { works: works(), attach_pdf: attach.input.checked });
      toast(`${plural(r.sent, "work")} sent to Zotero${r.collection ? `, into “${r.collection}”` : ""}.`, "ok");
      note.textContent = `Sent. They are in Zotero${r.collection ? ` in “${r.collection}”` : ""}; update your bibliography here to match them with your documents.`;
    } catch (e) {
      replace(note, e.kind === "zotero_not_running" ? workState("attention", e.message) : e.message);
      if (e.kind !== "zotero_not_running") showError(e);
    } finally { busy = false; zotero.disabled = false; }
  });
  const dl = (fmtName, ext) => async () => {
    try {
      const res = await api("POST", "/api/literature/export", { works: works(), format: fmtName }, { raw: true });
      const url = URL.createObjectURL(await res.blob());
      const a = h("a", { href: url, download: `Margin - works found.${ext}` });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (e) { showError(e); }
  };
  ris.addEventListener("click", dl("ris", "ris"));
  bib.addEventListener("click", dl("bibtex", "bib"));
  clearBtn.addEventListener("click", () => { for (const li of document.querySelectorAll(".lit-work[data-chosen]")) { li.removeAttribute("data-chosen"); li.querySelector(".lit-check").checked = false; } out.chosen.clear(); });
  return out;
}

// ---------------------------------------------------------------------------------------------
// E1: search
// ---------------------------------------------------------------------------------------------
function searchPanel(panel, { base, info, chosen, query, onSaved }) {
  const drafts = (info.drafts || []).filter((d) => d.claims > 0);
  let mode = query.draft && drafts.some((d) => d.draft_id === query.draft) ? "draft" : "words";
  let draftData = null, claimText = "", draftId = "";
  const modeSel = selectEl({ id: "lit-mode" }, h("option", { value: "words", selected: mode === "words" }, "Words I type"),
    drafts.length ? h("option", { value: "draft", selected: mode === "draft" }, "A claim in one of my drafts") : null);
  const draftSel = selectEl({ id: "lit-draft" }, drafts.map((d) => h("option", { value: d.draft_id, selected: d.draft_id === query.draft },
    `${shortTitle(d.title, 50)}${d.ai_access !== "cloud" ? " (stays on this computer)" : ""}`)));
  const claimBox = h("div", { class: "lit-claims" });
  const draftBox = h("div", { class: "lit-draftbox", hidden: mode !== "draft" }, field("Draft", draftSel), claimBox);
  const words = inputEl({ class: "lit-words", id: "lit-words", maxlength: 300, placeholder: "for example: “remote work” wellbeing parents", autocomplete: "off" });
  const source = selectEl({ id: "lit-source" }, info.sources.map((s) => h("option", { value: s.id }, s.name)));
  const year = inputEl({ sm: true, id: "lit-year", type: "number", min: 1900, max: 2100, placeholder: "any", class: "lit-year" });
  const oa = switchControl("Only works with an open copy", false);
  const sent = h("div", {});
  const resultBox = h("div", { class: "lit-results", "aria-live": "polite" });
  const go = button({ kind: "main", icon: "search" }, "Search");
  const saveBtn = button({ icon: "clock", title: "Keep this search and see what is new on it later" }, "Save as an alert");
  const refresh = () => replace(sent, sentLine(info, source.value, words.value));

  panel.append(
    makeCard({ class: "lit-form", title: "What are you looking for?", titleId: "lit-form-h" },
      h("div", { class: "lit-row" }, field("Start from", modeSel)),
      draftBox,
      field("Search words", words, { help: "Search words are made on this computer from the claim and the key terms of your documents. Change them as you like: these are the words that are sent." }),
      h("div", { class: "lit-row lit-options" }, field("Search in", source), field("Published from", year), oa),
      sent,
      h("div", { class: "btn-row" }, go, saveBtn)),
    resultBox);
  refresh();
  for (const el of [words, source]) el.addEventListener("input", refresh);
  words.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); search(); } });

  modeSel.addEventListener("change", () => { mode = modeSel.value; draftBox.hidden = mode !== "draft"; if (mode === "draft") loadDraft(); else { draftId = ""; claimText = ""; } });
  draftSel.addEventListener("change", loadDraft);

  async function loadDraft() {
    draftId = draftSel.value;
    replace(claimBox, h("p", { class: "muted small" }, spinner("Loading"), " Looking at the claims of this draft…"));
    try { draftData = await api("GET", `${base}/draft/${P(draftId)}`); } catch (e) { replace(claimBox, errorNotice(e)); return; }
    drawClaims();
  }
  function drawClaims() {
    const d = draftData;
    const parts = [];
    if (!d.searchable) {
      draftId = "";
      parts.push(notice({ kind: "info", icon: "shield" }, h("p", {}, d.why_not), h("p", { class: "small" }, "You can still type your own search words above: those are yours, not the draft's.")));
    }
    if (!d.claims.length) parts.push(h("p", { class: "muted" }, "No claim of this draft is waiting for a source: every one is backed by a document or dismissed. Check the draft first, or type search words."));
    else {
      const byId = new Map(d.claims.map((c) => [c.claim_id, c]));
      parts.push(optionCards({ label: "A claim to search for", class: "lit-claimlist",
        options: d.claims.map((c) => ({ value: c.claim_id, title: `${c.n}. ${c.claim}`, tag: STATUS_CHIP[c.status] || c.status_text || c.status, disabled: !d.searchable })),
        onPick: (id) => pickClaim(byId.get(id)) }));
    }
    replace(claimBox, parts);
    const first = query.claim && d.claims.find((c) => c.claim_id === query.claim);
    if (first) {
      claimBox.querySelector(".option-cards").set(first.claim_id);
      pickClaim(first, true);
    }
  }
  function pickClaim(c, quiet) {
    claimText = c.claim;
    words.value = c.words;
    refresh();
    if (!quiet) words.focus();
  }

  async function search(fresh) {
    const w = words.value.trim();
    if (!w) { words.focus(); toast("Type some search words first.", "warn"); return; }
    replace(resultBox, h("p", { class: "lit-wait" }, spinner("Searching"), ` Asking ${source.selectedOptions[0].textContent}…`));
    go.disabled = true;
    try {
      const r = await api("POST", `${base}/search`, { words: w, source: source.value, from_year: year.value || null, oa_only: oa.input.checked,
        claim: claimText || null, draft_id: draftId || null, fresh: !!fresh });
      drawResults(r);
    } catch (e) { replace(resultBox, errorNotice(e, () => search(fresh))); } finally { go.disabled = false; }
  }
  go.addEventListener("click", () => search(false));

  function drawResults(r) {
    const works = r.works || [];
    if (!works.length) { replace(resultBox, emptyState("search-x", "Nothing found", `${r.service} has no work for these words${oa.input.checked ? " with an open copy" : ""}. Try fewer or different words.`)); return; }
    const need = works.filter((x) => !x.open && x.doi);
    const how = r.ranked_by === "meaning" ? "closeness of meaning (with your local embedding model)" : "the words they share with " + (claimText ? "the claim" : "your words");
    const copies = h("div", { class: "lit-copies" });
    if (need.length) {
      if (info.email) {
        const b = button({ sm: true, icon: "book-open" }, `Look for open copies of ${plural(need.length, "work")}`);
        b.addEventListener("click", async () => {
          b.disabled = true;
          try {
            const o = await api("POST", `${base}/open-copies`, { dois: need.map((x) => x.doi) });
            let found = 0;
            for (const x of need) { const c = o.copies[x.doi]; if (c) { x.open = c; found++; } }
            drawResults(r);
            toast(found ? `Unpaywall has an open copy of ${plural(found, "work")}.` : "Unpaywall has no open copy of these.", found ? "ok" : "info");
          } catch (e) { showError(e); b.disabled = false; }
        });
        copies.append(b, h("span", { class: "muted small" }, ` Sends the DOIs of the works without an open copy (${need.slice(0, 25).length}) to Unpaywall (unpaywall.org).`));
      } else {
        copies.appendChild(h("p", { class: "muted small" }, icon("info", { size: 12 }), " Unpaywall can find open copies of the other works, but asks for an e-mail address. ", link({ href: "#/settings/literature" }, "Add yours in Settings"), "; Margin never fills it in by itself."));
      }
    }
    replace(resultBox,
      h("div", { class: "lit-results-head" }, h("h2", {}, `${plural(works.length, "work")} found`),
        h("p", { class: "muted small" }, `From ${r.service}, ordered by ${how}. `, r.note || "", " ",
          button({ kind: "quiet", sm: true, title: "Ask the service again instead of using what Margin kept", onClick: () => search(true) }, "Ask again"))),
      copies, workList(works, chosen, { closeNote: `Closeness by ${r.ranked_by === "meaning" ? "meaning" : "shared words"}` }));
  }

  saveBtn.addEventListener("click", async () => {
    const w = words.value.trim();
    if (!w) { words.focus(); toast("Type some search words first.", "warn"); return; }
    try {
      await api("POST", `${base}/searches`, { words: w, title: w, from_year: year.value || null, oa_only: oa.input.checked, draft_id: draftId || null });
      toast("Saved. Margin looks for new works on it when you open this page; nothing was sent now.", "ok");
      onSaved();
    } catch (e) { showError(e); }
  });

  if (mode === "draft") loadDraft().then(() => { if (query.claim) words.scrollIntoView({ block: "nearest" }); });
}

// ---------------------------------------------------------------------------------------------
// E2: follow citations
// ---------------------------------------------------------------------------------------------
function citationsPanel(panel, { base, info, chosen }) {
  const intro = h("div", { class: "lit-intro" });
  const resultBox = h("div", { class: "lit-results", "aria-live": "polite" });
  panel.append(intro, resultBox);
  let plan = null, data = null, side = "cited", hideHave = false;

  (async () => {
    try { plan = await api("GET", `${base}/citations`); } catch (e) { replace(intro, errorNotice(e)); return; }
    drawIntro();
  })();

  function drawIntro() {
    const out = [];
    const left = [];
    if (plan.not_allowed) left.push(`${plural(plan.not_allowed, "document")} left out because ${plan.not_allowed === 1 ? "its" : "their"} AI setting keeps ${plan.not_allowed === 1 ? "it" : "them"} on this computer`);
    if (plan.no_doi) left.push(`${plural(plan.no_doi, "document")} without a DOI (add your Zotero library on the Bibliography page to give more of them one)`);
    const go = button({ kind: "main", icon: "link", disabled: !plan.dois.length }, "Look up citations");
    go.addEventListener("click", () => run(false));
    out.push(
      h("p", {}, "Finds the works your documents cite and the works that cite them, and ranks them by how many of your documents they connect to, then by how close they are to your themes."),
      plan.dois.length
        ? notice({ kind: "info", icon: "external-link", class: "lit-sent" }, h("p", {}, "Only the ", h("strong", {}, plural(plan.dois.length, "DOI")), ` of ${plural(plan.included, "document")} go to `, h("strong", {}, "OpenAlex"), " (openalex.org). No text of any document is sent."))
        : notice({ kind: "info" }, h("p", {}, "No document with a DOI may be looked up yet. Add documents that carry a DOI, or bring in your Zotero library on the Bibliography page.")),
      left.length ? h("ul", { class: "muted small lit-left" }, left.map((t) => h("li", {}, t))) : null,
      plan.dois.length ? fold({ sm: true }, "Show exactly what is sent",
        h("ul", { class: "lit-doclist" }, plan.documents.filter((d) => d.included).map((d) => h("li", {}, h("strong", {}, shortTitle(d.title, 70)), " · ", h("span", { class: "mono small" }, d.dois.join(", ")))))) : null,
      h("div", { class: "btn-row" }, go));
    replace(intro, makeCard({ class: "lit-form", title: "The works around your documents", titleId: "lit-around-h" }, ...out));
  }

  async function run(fresh) {
    replace(resultBox, h("p", { class: "lit-wait" }, spinner("Looking up"), " Asking OpenAlex… this can take up to a minute for many documents."));
    try { data = await api("POST", `${base}/citations`, { fresh: !!fresh }); } catch (e) { replace(resultBox, errorNotice(e, () => run(fresh))); return; }
    drawResults();
  }

  function drawResults() {
    const lists = { cited: data.cited, citing: data.citing };
    let works = lists[side].filter((w) => !(hideHave && w.have));
    const seg = choice({ filter: true, label: "Which works", class: "lit-seg", value: side,
      options: [["cited", "Cited by your documents", lists.cited.length], ["citing", "Cite your documents", lists.citing.length]], onPick: (k) => { side = k; drawResults(); } });
    const have = switchControl("Hide works I already have", hideHave);
    have.input.addEventListener("change", () => { hideHave = have.input.checked; drawResults(); });
    const notes = [];
    if (data.partial) notes.push("It took too long, so these are the works found so far.");
    if (data.cited_cap && side === "cited") notes.push(`Only the ${data.cited_cap} works shared by most documents are shown.`);
    if (data.found_in_openalex < data.dois) notes.push(`OpenAlex knows ${data.found_in_openalex} of the ${data.dois} DOIs.`);
    replace(resultBox,
      h("div", { class: "lit-results-head" }, seg, have,
        h("p", { class: "muted small" }, `Ordered by how many of your documents they connect to, then by closeness to your themes${data.closeness_by === "meaning" ? " (by meaning)" : data.closeness_by === "words" ? " (by shared words)" : " (you have no themes yet, so this is not used)"}. `, notes.join(" "), " ",
          button({ kind: "quiet", sm: true, onClick: () => run(true) }, "Ask again"))),
      works.length ? workList(works, chosen, { themes: true, docs: true, closeNote: "Closeness to your themes" })
        : emptyState("search-x", "Nothing here", side === "cited" ? "OpenAlex lists no references for these documents, or you hide the ones you have." : "No work in OpenAlex cites these documents yet."));
  }
}

// ---------------------------------------------------------------------------------------------
// E3: saved searches
// ---------------------------------------------------------------------------------------------
function alertsPanel(panel, { base, info, chosen, setBadge }) {
  let searches = info.searches || [];
  let open = null;                    // the search whose new works are shown
  let works = [];                     // those works
  const busy = new Set();
  let stopped = false;
  const list = h("div", { class: "lit-alerts" });
  const addBox = h("div", { class: "lit-add" });
  panel.append(h("div", { class: "lit-results-head" },
    h("p", { class: "muted" }, "Saved searches tell you what is new since you last looked. Margin looks when you open this page, or when you press a button: nothing runs in the background.")), list, addBox);
  drawAdd();
  draw();

  function total() { return searches.reduce((n, s) => n + (s.new || 0), 0); }
  function put(s) { const i = searches.findIndex((x) => x.search_id === s.search_id); if (i >= 0) searches[i] = s; else searches.unshift(s); }

  function draw() {
    setBadge(total());
    if (!searches.length) { replace(list, emptyState("clock", "No saved searches yet", "Search on the first tab and press “Save as an alert”, or add a research question below.")); return; }
    const checkAll = button({ sm: true, icon: "refresh", onClick: () => checkAllNow() }, "Check all now");
    replace(list, h("div", { class: "btn-row lit-checkall" }, checkAll), searches.map(card));
  }

  function filtersText(s) {
    const f = s.filters || {};
    return [f.from_year ? `published from ${f.from_year}` : null, f.oa_only ? "open copies only" : null].filter(Boolean).join(" · ");
  }

  function card(s) {
    const isOpen = open === s.search_id;
    const checking = busy.has(s.search_id);
    const status = checking ? workState("running", "Asking OpenAlex…")
      : s.error ? workState("failed", s.error)
      : s.last_checked_at ? h("span", { class: "muted small" }, `Checked ${ago(s.last_checked_at)}`) : h("span", { class: "muted small" }, "Not checked yet");
    const showBtn = s.new || isOpen ? button({ kind: "quiet", sm: true, toggle: true, "aria-expanded": String(isOpen), onClick: () => toggle(s) }, isOpen ? "Hide new works" : "Show new works") : null;
    return makeCard({ as: "article", class: "lit-alert", "data-new": s.new ? "true" : null, level: "h3", title: s.title,
      action: s.new ? tag({ kind: "count", title: "Works found since you last marked this search as seen" }, `${s.new} new`) : h("span", { class: "muted small" }, "Nothing new") },
      h("p", { class: "lit-alert-meta muted small" }, h("span", { class: "mono" }, s.words), filtersText(s) ? ` · ${filtersText(s)}` : "", s.draft_id ? " · from a draft" : "", ` · since ${fmt.dateShort(s.since)}`),
      status,
      h("div", { class: "btn-row" },
        button({ sm: true, icon: "refresh", disabled: checking, onClick: () => checkOne(s) }, "Check now"),
        showBtn,
        s.new ? button({ kind: "quiet", sm: true, icon: "check", onClick: () => seen(s) }, "Mark as seen") : null,
        button({ kind: "danger", sm: true, icon: "trash", onClick: () => remove(s) }, "Delete")),
      isOpen ? h("div", { class: "lit-alert-works" }, works.length ? workList(works, chosen) : h("p", { class: "muted" }, "Nothing new to show.")) : null);
  }

  async function checkOne(s, quiet) {
    if (busy.has(s.search_id) || stopped) return;
    busy.add(s.search_id); draw();
    try {
      const r = await api("POST", `${base}/searches/${P(s.search_id)}/check`);
      put(r.search);
      if (open === s.search_id) works = r.works;
      if (!quiet) toast(r.search.new ? `${plural(r.search.new, "new work")} on “${shortTitle(s.title, 40)}”.` : `Nothing new on “${shortTitle(s.title, 40)}”.`, r.search.new ? "ok" : "info");
    } catch (e) {
      if (!quiet) showError(e);
      try { put((await api("GET", `${base}/searches/${P(s.search_id)}`)).search); } catch (_) { /* keep as it was */ }
    } finally { busy.delete(s.search_id); if (!stopped) draw(); }
  }
  async function checkAllNow() { for (const s of [...searches]) await checkOne(s, true); }

  async function toggle(s) {
    if (open === s.search_id) { open = null; works = []; draw(); return; }
    try { const r = await api("GET", `${base}/searches/${P(s.search_id)}`); works = r.works; open = s.search_id; draw(); } catch (e) { showError(e); }
  }
  async function seen(s) {
    try { const r = await api("POST", `${base}/searches/${P(s.search_id)}/seen`); put(r.search); if (open === s.search_id) { open = null; works = []; } draw(); } catch (e) { showError(e); }
  }
  async function remove(s) {
    if (!(await confirmDialog({ title: "Delete this saved search?", message: `“${shortTitle(s.title, 60)}” and the works found on it are removed from this project. Nothing in Zotero changes.`, confirmText: "Delete" }))) return;
    try { await api("DELETE", `${base}/searches/${P(s.search_id)}`); searches = searches.filter((x) => x.search_id !== s.search_id); if (open === s.search_id) { open = null; works = []; } draw(); } catch (e) { showError(e); }
  }

  function drawAdd() {
    const q = textareaEl({ id: "lit-question", rows: 2, maxlength: 400, placeholder: "for example: Does working from home make young employees lonelier?" });
    const wordsIn = inputEl({ class: "lit-words", id: "lit-qwords", maxlength: 300, placeholder: "search words, made from the question" });
    const make = button({ sm: true, icon: "tag" }, "Make search words from the question");
    const save = button({ kind: "main", sm: true, icon: "check" }, "Save this research question");
    const sent = h("div", {});
    const refresh = () => replace(sent, sentLine(info, "openalex", wordsIn.value, "the search is checked"));
    wordsIn.addEventListener("input", refresh);
    make.addEventListener("click", async () => {
      if (!q.value.trim()) { q.focus(); return; }
      try { const r = await api("POST", `${base}/words`, { text: q.value }); wordsIn.value = r.words; refresh(); wordsIn.focus(); } catch (e) { showError(e); }
    });
    save.addEventListener("click", async () => {
      const w = wordsIn.value.trim();
      if (!w) { if (q.value.trim()) make.click(); else q.focus(); return; }
      try {
        const r = await api("POST", `${base}/searches`, { words: w, title: q.value.trim() || w, kind: q.value.trim() ? "question" : "search" });
        put(r.search); q.value = ""; wordsIn.value = ""; refresh(); draw();
        toast("Saved. Press Check now to look for works.", "ok");
      } catch (e) { showError(e); }
    });
    replace(addBox, makeCard({ class: "lit-form", title: "Add a research question", titleId: "lit-add-h" },
      h("p", { class: "muted" }, "Write a question you care about. Margin makes search words from it on this computer, you change them as you like, and it keeps an eye on new work."),
      field("Your question", q), h("div", { class: "btn-row" }, make),
      field("Search words", wordsIn, { help: "These are the words that are sent when the search is checked." }), sent, h("div", { class: "btn-row" }, save)));
    refresh();
  }

  return {
    reload: async () => { try { searches = (await api("GET", `${base}/searches`)).searches; draw(); } catch (e) { showError(e); } },
    // when the page opens: a search not looked at lately is looked at now, one after the other
    autoCheck: async () => { for (const s of [...searches]) { if (stopped) return; if (staleSearch(s)) await checkOne(s, true); } },
    stop: () => { stopped = true; },
  };
}

// Settings → Exploring: the e-mail address for lookups (Margin never fills it in).
export function literatureSettings(s, save, sectionCard) {
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const email = inputEl({ id: "set-contact-email", type: "email", value: s.contact_email || "", placeholder: "name@example.org", autocomplete: "email", maxlength: 200, class: "lit-email" });
  email.addEventListener("change", async () => { try { await save({ contact_email: email.value.trim() }, state); } catch (_) { /* shown */ } });
  return sectionCard("literature", "Looking up literature online", "Find literature asks OpenAlex, Crossref, Semantic Scholar and Unpaywall for works. An e-mail address is optional: it lets OpenAlex and Crossref reach you if you ask for a great deal, and Unpaywall asks for one. It is sent with those lookups only, and never filled in by Margin.",
    field("Your e-mail address (optional)", email, { help: "Leave it empty to send none. OpenAlex's own open-access links need no address; Unpaywall's extra open copies do." }),
    h("div", { class: "save-row" }, h("span", { class: "muted small" }, "Saved as soon as you change it."), state));
}
