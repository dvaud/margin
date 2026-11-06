// Margin: Find literature. Three things on one page, none of them AI: search for works to cite (for a claim no document
// supports, or for words you type), follow what your documents cite and who cites them, and keep searches that say what
// is new. Words go to OpenAlex (and, if you choose, Crossref or Semantic Scholar) only after you have seen them, never
// when cloud services are off for good, and never from a draft or document whose AI setting keeps it on this computer.
// Works you choose go to Zotero (its connector on this computer) or download as RIS or BibTeX.
import { featureEyebrow } from "../features.js";
import { App, api, h, icon, replace, clear, toast, showError, fmt, pageHead, P, plural, session, spinner, emptyState, field,
  confirmDialog, shortTitle } from "../lib.js";

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
  return r >= 0.66 ? ["Very close", "ok"] : r >= 0.33 ? ["Close", "partly"] : ["Loosely related", "none"];
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
  return h("div", { class: "notice notice-warn", role: "alert" }, icon(e.kind === "rate_limited" ? "clock" : "alert-triangle"),
    h("div", {}, h("p", {}, e.message || String(e)), again ? h("button", { class: "btn btn-sm", type: "button", onClick: again }, icon("refresh", { size: 13 }), "Try again") : null));
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
  const panels = {}, tabBtns = {};
  const nav = h("div", { class: "lit-tabs", role: "tablist", "aria-label": "Find literature" });
  for (const [k, label, ic] of TABS) {
    tabBtns[k] = h("button", { class: "lit-tab", type: "button", role: "tab", id: `lit-tab-${k}`, "aria-controls": `lit-panel-${k}`, onClick: () => show(k) },
      icon(ic, { size: 15 }), h("span", {}, label), h("span", { class: "lit-badge", hidden: true }));
    panels[k] = h("section", { class: "lit-panel", role: "tabpanel", id: `lit-panel-${k}`, "aria-labelledby": `lit-tab-${k}`, hidden: true });
    nav.appendChild(tabBtns[k]);
  }
  wide.append(nav, panels.search, panels.citations, panels.alerts, bar.el);
  function show(k) {
    tab = k;
    session(tabKey, k);
    for (const [key] of TABS) {
      const on = key === k;
      panels[key].hidden = !on;
      tabBtns[key].setAttribute("aria-selected", on ? "true" : "false");
      tabBtns[key].classList.toggle("on", on);
    }
  }
  const alerts = alertsPanel(panels.alerts, { base, info, chosen, setBadge: (n) => badge(tabBtns.alerts, n) });
  searchPanel(panels.search, { base, info, chosen, query, onSaved: () => alerts.reload() });
  citationsPanel(panels.citations, { base, info, chosen });
  show(tab);
  badge(tabBtns.alerts, (info.searches || []).reduce((n, s) => n + (s.new || 0), 0));
  alerts.autoCheck();
  return () => { alerts.stop(); };
}

function badge(btn, n) {
  const b = btn.querySelector(".lit-badge");
  b.hidden = !n;
  b.textContent = n ? `${n} new` : "";
}

// ---------------------------------------------------------------------------------------------
// what goes out, in words
// ---------------------------------------------------------------------------------------------
function privacyCard(info) {
  const mail = info.email;
  return h("section", { class: "lit-privacy", "aria-label": "What goes online" },
    icon("shield", { size: 16 }),
    h("div", {}, info.local_only
      ? h("p", {}, h("strong", {}, "Nothing is sent. "), "Cloud services are switched off for good on this computer.")
      : [h("p", {}, h("strong", {}, "Only words you have seen leave this computer. "),
        "A search sends its search words to OpenAlex (openalex.org), a free index of scholarly works; following citations sends the DOIs of your documents. A draft or document whose AI setting keeps it on this computer is never used."),
      h("p", { class: "muted small" }, mail
        ? `Your e-mail address (${mail}) goes along with lookups to OpenAlex, Crossref and Unpaywall, so they can reach you if you ask for much. `
        : "No e-mail address is sent. OpenAlex works without one; Unpaywall, which finds more open copies, needs one. ",
      h("a", { href: "#/settings/literature" }, mail ? "Change it in Settings" : "Add one in Settings if you wish"), ".")]));
}

function sentLine(info, source, words, when = "you press Search") {
  const s = info.sources.find((x) => x.id === source) || info.sources[0];
  const w = (words || "").trim();
  return h("p", { class: "lit-sent", "aria-live": "polite" }, icon("cloud", { size: 14 }), h("span", {},
    w ? ["Only these words go to ", h("strong", {}, s.name), ` (${s.site}): `, h("strong", { class: "lit-words-sent" }, w), ". "] : `Type search words: they go to ${s.name} (${s.site}) when ${when}. `,
    info.email && source !== "semanticscholar" ? `Your address (${info.email}) goes with them.` : ""));
}

// ---------------------------------------------------------------------------------------------
// a work, and the bar for what to do with the works chosen
// ---------------------------------------------------------------------------------------------
function workCard(w, chosen, opts = {}) {
  const c = chosen.has(w);
  const box = h("input", { type: "checkbox", class: "lit-check", checked: c, "aria-label": `Choose: ${shortTitle(w.title, 90)}` });
  box.addEventListener("change", () => { chosen.toggle(w, box.checked); li.classList.toggle("chosen", box.checked); });
  const href = w.url || (w.doi ? `https://doi.org/${w.doi}` : null);
  const title = href ? h("a", { href, target: "_blank", rel: "noopener noreferrer", title: "Opens the publisher's or index's page in a new tab" }, w.title) : w.title;
  const meta = [authorsLine(w), w.year, w.venue].filter(Boolean).join(" · ");
  const chips = [];
  const cw = closeWord(w, opts.maxClose);
  if (cw) chips.push(h("span", { class: `lit-chip lit-chip-${cw[1]}`, title: opts.closeNote || "How close this work is to what you searched for" }, cw[0]));
  if (opts.themes && w.theme && w.theme_close) chips.push(h("span", { class: "lit-chip", title: `Closest of your themes: ${w.theme}` }, icon("shapes", { size: 11 }), shortTitle(w.theme, 28)));
  if (w.have) chips.push(h("span", { class: "lit-chip lit-chip-have", title: w.have.title || "" }, icon("circle-check", { size: 11 }), w.have.where === "documents" ? "Already in your documents" : "Already in your bibliography"));
  if (w.n_docs) chips.push(h("span", { class: "lit-chip lit-chip-docs", title: (w.doc_titles || []).join("\n") }, icon("link", { size: 11 }), `Connects ${w.n_docs} of your documents`));
  chips.push(h("span", { class: "lit-chip lit-chip-cited" }, `Cited ${fmt.num(w.cited_by || 0)}×`));
  const open = w.open;
  const openLink = open && (open.pdf_url || open.url)
    ? h("a", { class: "lit-open", href: open.pdf_url || open.url, target: "_blank", rel: "noopener noreferrer", title: `Found by ${open.found_by || "an open-access index"}${open.license ? ` · licence ${open.license}` : ""}` }, icon("book-open", { size: 13 }), open.pdf_url ? "Open PDF" : "Open copy")
    : h("span", { class: "lit-noopen muted small", "data-doi": w.doi || "" }, "No open copy found");
  const li = h("li", { class: "lit-work" + (c ? " chosen" : ""), "data-key": w.key },
    box,
    h("div", { class: "lit-main" },
      h("h3", { class: "lit-title" }, title),
      meta ? h("p", { class: "lit-meta muted small" }, meta) : null,
      h("div", { class: "lit-chips" }, chips, openLink),
      w.abstract ? h("details", { class: "fold lit-abstract" }, h("summary", {}, "Abstract"), h("p", {}, w.abstract)) : null,
      opts.docs && (w.doc_titles || []).length ? h("details", { class: "fold lit-abstract" }, h("summary", {}, "Which of your documents"),
        h("ul", { class: "lit-doclist" }, w.doc_titles.map((t) => h("li", {}, t)))) : null));
  li.workRef = w;
  return li;
}

function workList(works, chosen, opts = {}) {
  const max = Math.max(0, ...works.map((w) => w.closeness || 0));
  return h("ol", { class: "lit-works" }, works.map((w) => workCard(w, chosen, { ...opts, maxClose: max })));
}

function actionBar(info) {
  const attach = h("input", { type: "checkbox", id: "lit-attach", checked: true });
  const count = h("span", { class: "lit-bar-count" });
  const note = h("p", { class: "lit-bar-note muted small", "aria-live": "polite" });
  const zotero = h("button", { class: "btn btn-primary btn-sm", type: "button" }, icon("library", { size: 14 }), "Send to Zotero");
  const ris = h("button", { class: "btn btn-sm", type: "button" }, icon("download", { size: 13 }), "RIS");
  const bib = h("button", { class: "btn btn-sm", type: "button" }, icon("download", { size: 13 }), "BibTeX");
  const clearBtn = h("button", { class: "btn btn-sm btn-ghost", type: "button" }, "Clear");
  const el = h("div", { class: "lit-bar", hidden: true, role: "region", "aria-label": "Works you chose" },
    h("div", { class: "lit-bar-row" }, count, h("div", { class: "btn-row" }, zotero, h("span", { class: "lit-bar-dl muted small" }, "or download", ), ris, bib, clearBtn)),
    h("label", { class: "lit-attach small", for: "lit-attach" }, attach, " Let Zotero fetch the open PDFs too (Zotero itself downloads them)"), note);
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
      const r = await api("POST", "/api/literature/zotero", { works: works(), attach_pdf: attach.checked });
      toast(`${plural(r.sent, "work")} sent to Zotero${r.collection ? `, into “${r.collection}”` : ""}.`, "ok");
      note.textContent = `Sent. They are in Zotero${r.collection ? ` in “${r.collection}”` : ""}; update your bibliography here to match them with your documents.`;
    } catch (e) {
      replace(note, e.kind === "zotero_not_running" ? [icon("alert-triangle", { size: 13 }), " ", e.message] : e.message);
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
  clearBtn.addEventListener("click", () => { for (const li of document.querySelectorAll(".lit-work.chosen")) { li.classList.remove("chosen"); li.querySelector(".lit-check").checked = false; } out.chosen.clear(); });
  return out;
}

// ---------------------------------------------------------------------------------------------
// E1: search
// ---------------------------------------------------------------------------------------------
function searchPanel(panel, { base, info, chosen, query, onSaved }) {
  const drafts = (info.drafts || []).filter((d) => d.claims > 0);
  let mode = query.draft && drafts.some((d) => d.draft_id === query.draft) ? "draft" : "words";
  let draftData = null, claimText = "", draftId = "";
  const modeSel = h("select", { class: "select", id: "lit-mode" }, h("option", { value: "words", selected: mode === "words" }, "Words I type"),
    drafts.length ? h("option", { value: "draft", selected: mode === "draft" }, "A claim in one of my drafts") : null);
  const draftSel = h("select", { class: "select", id: "lit-draft" }, drafts.map((d) => h("option", { value: d.draft_id, selected: d.draft_id === query.draft },
    `${shortTitle(d.title, 50)}${d.ai_access !== "cloud" ? " (stays on this computer)" : ""}`)));
  const claimBox = h("div", { class: "lit-claims" });
  const draftBox = h("div", { class: "lit-draftbox", hidden: mode !== "draft" }, field("Draft", draftSel), claimBox);
  const words = h("input", { class: "input lit-words", id: "lit-words", type: "text", maxlength: 300, placeholder: "for example: “remote work” wellbeing parents", autocomplete: "off" });
  const source = h("select", { class: "select", id: "lit-source" }, info.sources.map((s) => h("option", { value: s.id }, s.name)));
  const year = h("input", { class: "input input-sm", id: "lit-year", type: "number", min: 1900, max: 2100, placeholder: "any", style: { width: "6.5em" } });
  const oa = h("input", { type: "checkbox", id: "lit-oa" });
  const sent = h("div", {});
  const resultBox = h("div", { class: "lit-results", "aria-live": "polite" });
  const go = h("button", { class: "btn btn-primary", type: "button" }, icon("search", { size: 15 }), "Search");
  const saveBtn = h("button", { class: "btn", type: "button", title: "Keep this search and see what is new on it later" }, icon("clock", { size: 14 }), "Save as an alert");
  const refresh = () => replace(sent, sentLine(info, source.value, words.value));

  panel.append(
    h("section", { class: "card lit-form" },
      h("div", { class: "card-head" }, h("h2", {}, "What are you looking for?")),
      h("div", { class: "lit-row" }, field("Start from", modeSel)),
      draftBox,
      field("Search words", words, { help: "Search words are made on this computer from the claim and the key terms of your documents. Change them as you like: these are the words that are sent." }),
      h("div", { class: "lit-row lit-options" }, field("Search in", source), field("Published from", year), h("label", { class: "lit-oa", for: "lit-oa" }, oa, " Only works with an open copy")),
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
      parts.push(h("div", { class: "notice notice-info" }, icon("shield"), h("div", {}, h("p", {}, d.why_not), h("p", { class: "small" }, "You can still type your own search words above: those are yours, not the draft's."))));
    }
    if (!d.claims.length) parts.push(h("p", { class: "muted" }, "No claim of this draft is waiting for a source: every one is backed by a document or dismissed. Check the draft first, or type search words."));
    parts.push(h("ul", { class: "lit-claimlist" }, d.claims.map((c) => {
      const b = h("button", { class: "lit-claim", type: "button", disabled: !d.searchable, "aria-pressed": "false", onClick: () => pickClaim(c, b) },
        h("span", { class: "dc-n dm-" + c.status }, String(c.n)), h("span", { class: "lit-claim-text" }, c.claim),
        h("span", { class: "chip dc-chip" }, STATUS_CHIP[c.status] || c.status_text || c.status));
      b.dataset.id = c.claim_id;
      return h("li", {}, b);
    })));
    replace(claimBox, parts);
    const first = query.claim && d.claims.find((c) => c.claim_id === query.claim);
    if (first) pickClaim(first, claimBox.querySelector(`[data-id="${CSS.escape(first.claim_id)}"]`), true);
  }
  function pickClaim(c, btn, quiet) {
    for (const b of claimBox.querySelectorAll(".lit-claim")) b.setAttribute("aria-pressed", String(b === btn));
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
      const r = await api("POST", `${base}/search`, { words: w, source: source.value, from_year: year.value || null, oa_only: oa.checked,
        claim: claimText || null, draft_id: draftId || null, fresh: !!fresh });
      drawResults(r);
    } catch (e) { replace(resultBox, errorNotice(e, () => search(fresh))); } finally { go.disabled = false; }
  }
  go.addEventListener("click", () => search(false));

  function drawResults(r) {
    const works = r.works || [];
    if (!works.length) { replace(resultBox, emptyState("search-x", "Nothing found", `${r.service} has no work for these words${oa.checked ? " with an open copy" : ""}. Try fewer or different words.`)); return; }
    const need = works.filter((x) => !x.open && x.doi);
    const how = r.ranked_by === "meaning" ? "closeness of meaning (with your local embedding model)" : "the words they share with " + (claimText ? "the claim" : "your words");
    const copies = h("div", { class: "lit-copies" });
    if (need.length) {
      if (info.email) {
        const b = h("button", { class: "btn btn-sm", type: "button" }, icon("book-open", { size: 13 }), `Look for open copies of ${plural(need.length, "work")}`);
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
        copies.appendChild(h("p", { class: "muted small" }, icon("info", { size: 12 }), " Unpaywall can find open copies of the other works, but asks for an e-mail address. ", h("a", { href: "#/settings/literature" }, "Add yours in Settings"), "; Margin never fills it in by itself."));
      }
    }
    replace(resultBox,
      h("div", { class: "lit-results-head" }, h("h2", {}, `${plural(works.length, "work")} found`),
        h("p", { class: "muted small" }, `From ${r.service}, ordered by ${how}. `, r.note || "", " ",
          h("button", { class: "link-btn", type: "button", title: "Ask the service again instead of using what Margin kept", onClick: () => search(true) }, "Ask again"))),
      copies, workList(works, chosen, { closeNote: `Closeness by ${r.ranked_by === "meaning" ? "meaning" : "shared words"}` }));
  }

  saveBtn.addEventListener("click", async () => {
    const w = words.value.trim();
    if (!w) { words.focus(); toast("Type some search words first.", "warn"); return; }
    try {
      await api("POST", `${base}/searches`, { words: w, title: w, from_year: year.value || null, oa_only: oa.checked, draft_id: draftId || null });
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
  const intro = h("section", { class: "card lit-form" });
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
    const go = h("button", { class: "btn btn-primary", type: "button", disabled: !plan.dois.length }, icon("link", { size: 15 }), "Look up citations");
    go.addEventListener("click", () => run(false));
    out.push(h("div", { class: "card-head" }, h("h2", {}, "The works around your documents")),
      h("p", {}, "Finds the works your documents cite and the works that cite them, and ranks them by how many of your documents they connect to, then by how close they are to your themes."),
      plan.dois.length
        ? h("p", { class: "lit-sent" }, icon("cloud", { size: 14 }), h("span", {}, "Only the ", h("strong", {}, plural(plan.dois.length, "DOI")), ` of ${plural(plan.included, "document")} go to `, h("strong", {}, "OpenAlex"), " (openalex.org). No text of any document is sent."))
        : h("div", { class: "notice notice-info" }, icon("info"), h("p", {}, "No document with a DOI may be looked up yet. Add documents that carry a DOI, or bring in your Zotero library on the Bibliography page.")),
      left.length ? h("ul", { class: "muted small lit-left" }, left.map((t) => h("li", {}, t))) : null,
      plan.dois.length ? h("details", { class: "fold" }, h("summary", {}, "Show exactly what is sent"),
        h("ul", { class: "lit-doclist" }, plan.documents.filter((d) => d.included).map((d) => h("li", {}, h("strong", {}, shortTitle(d.title, 70)), " · ", h("span", { class: "mono small" }, d.dois.join(", ")))))) : null,
      h("div", { class: "btn-row", style: { marginTop: "12px" } }, go));
    replace(intro, out);
  }

  async function run(fresh) {
    replace(resultBox, h("p", { class: "lit-wait" }, spinner("Looking up"), " Asking OpenAlex… this can take up to a minute for many documents."));
    try { data = await api("POST", `${base}/citations`, { fresh: !!fresh }); } catch (e) { replace(resultBox, errorNotice(e, () => run(fresh))); return; }
    drawResults();
  }

  function drawResults() {
    const lists = { cited: data.cited, citing: data.citing };
    let works = lists[side].filter((w) => !(hideHave && w.have));
    const seg = h("div", { class: "lit-seg", role: "group", "aria-label": "Which works" }, [["cited", "Cited by your documents"], ["citing", "Cite your documents"]].map(([k, label]) =>
      h("button", { class: "lit-seg-btn" + (side === k ? " on" : ""), type: "button", "aria-pressed": String(side === k), onClick: () => { side = k; drawResults(); } }, `${label} (${lists[k].length})`)));
    const have = h("input", { type: "checkbox", id: "lit-hide", checked: hideHave });
    have.addEventListener("change", () => { hideHave = have.checked; drawResults(); });
    const notes = [];
    if (data.partial) notes.push("It took too long, so these are the works found so far.");
    if (data.cited_cap && side === "cited") notes.push(`Only the ${data.cited_cap} works shared by most documents are shown.`);
    if (data.found_in_openalex < data.dois) notes.push(`OpenAlex knows ${data.found_in_openalex} of the ${data.dois} DOIs.`);
    replace(resultBox,
      h("div", { class: "lit-results-head" }, seg,
        h("div", { class: "lit-filter" }, h("label", { for: "lit-hide" }, have, " Hide works I already have")),
        h("p", { class: "muted small" }, `Ordered by how many of your documents they connect to, then by closeness to your themes${data.closeness_by === "meaning" ? " (by meaning)" : data.closeness_by === "words" ? " (by shared words)" : " (you have no themes yet, so this is not used)"}. `, notes.join(" "), " ",
          h("button", { class: "link-btn", type: "button", onClick: () => run(true) }, "Ask again"))),
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
  const addBox = h("section", { class: "card lit-form" });
  panel.append(h("div", { class: "lit-results-head" },
    h("p", { class: "muted" }, "Saved searches tell you what is new since you last looked. Margin looks when you open this page, or when you press a button: nothing runs in the background.")), list, addBox);
  drawAdd();
  draw();

  function total() { return searches.reduce((n, s) => n + (s.new || 0), 0); }
  function put(s) { const i = searches.findIndex((x) => x.search_id === s.search_id); if (i >= 0) searches[i] = s; else searches.unshift(s); }

  function draw() {
    setBadge(total());
    if (!searches.length) { replace(list, emptyState("clock", "No saved searches yet", "Search on the first tab and press “Save as an alert”, or add a research question below.")); return; }
    const checkAll = h("button", { class: "btn btn-sm", type: "button", onClick: () => checkAllNow() }, icon("refresh", { size: 13 }), "Check all now");
    replace(list, h("div", { class: "btn-row", style: { marginBottom: "10px" } }, checkAll), searches.map(card));
  }

  function filtersText(s) {
    const f = s.filters || {};
    return [f.from_year ? `published from ${f.from_year}` : null, f.oa_only ? "open copies only" : null].filter(Boolean).join(" · ");
  }

  function card(s) {
    const isOpen = open === s.search_id;
    const checking = busy.has(s.search_id);
    const status = checking ? h("span", { class: "muted small" }, spinner("Checking"), " Asking OpenAlex…")
      : s.error ? h("span", { class: "lit-err small" }, icon("alert-triangle", { size: 12 }), " ", s.error)
      : s.last_checked_at ? h("span", { class: "muted small" }, `Checked ${ago(s.last_checked_at)}`) : h("span", { class: "muted small" }, "Not checked yet");
    return h("article", { class: "card lit-alert" + (s.new ? " has-new" : "") },
      h("div", { class: "lit-alert-head" },
        h("div", { class: "grow" },
          h("h3", {}, icon(s.kind === "question" ? "help" : "search", { size: 15 }), " ", s.title),
          h("p", { class: "muted small" }, h("span", { class: "mono" }, s.words), filtersText(s) ? ` · ${filtersText(s)}` : "", s.draft_id ? " · from a draft" : "", ` · since ${fmt.dateShort(s.since)}`),
          status),
        s.new ? h("span", { class: "lit-new", title: "Works found since you last marked this search as seen" }, `${s.new} new`) : h("span", { class: "muted small" }, "Nothing new")),
      h("div", { class: "btn-row" },
        h("button", { class: "btn btn-sm", type: "button", disabled: checking, onClick: () => checkOne(s) }, icon("refresh", { size: 13 }), "Check now"),
        s.new || isOpen ? h("button", { class: "btn btn-sm", type: "button", "aria-expanded": String(isOpen), onClick: () => toggle(s) }, icon(isOpen ? "chevron-up" : "chevron-down", { size: 13 }), isOpen ? "Hide new works" : "Show new works") : null,
        s.new ? h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: () => seen(s) }, icon("check", { size: 13 }), "Mark as seen") : null,
        h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: () => remove(s) }, icon("trash", { size: 13 }), "Delete")),
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
    const q = h("textarea", { class: "textarea", id: "lit-question", rows: 2, maxlength: 400, placeholder: "for example: Does working from home make young employees lonelier?" });
    const wordsIn = h("input", { class: "input lit-words", id: "lit-qwords", type: "text", maxlength: 300, placeholder: "search words, made from the question" });
    const make = h("button", { class: "btn btn-sm", type: "button" }, icon("tag", { size: 13 }), "Make search words from the question");
    const save = h("button", { class: "btn btn-primary btn-sm", type: "button" }, icon("check", { size: 13 }), "Save this research question");
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
    replace(addBox, h("div", { class: "card-head" }, h("h2", {}, "Add a research question")),
      h("p", { class: "muted" }, "Write a question you care about. Margin makes search words from it on this computer, you change them as you like, and it keeps an eye on new work."),
      field("Your question", q), h("div", { class: "btn-row" }, make),
      field("Search words", wordsIn, { help: "These are the words that are sent when the search is checked." }), sent, h("div", { class: "btn-row" }, save));
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
  const email = h("input", { class: "input", id: "set-contact-email", type: "email", value: s.contact_email || "", placeholder: "name@example.org", autocomplete: "email", maxlength: 200, style: { maxWidth: "24em" } });
  email.addEventListener("change", async () => { try { await save({ contact_email: email.value.trim() }, state); } catch (_) { /* shown */ } });
  return sectionCard("literature", "Looking up literature online", "Find literature asks OpenAlex, Crossref, Semantic Scholar and Unpaywall for works. An e-mail address is optional: it lets OpenAlex and Crossref reach you if you ask for a great deal, and Unpaywall asks for one. It is sent with those lookups only, and never filled in by Margin.",
    field("Your e-mail address (optional)", email, { help: "Leave it empty to send none. OpenAlex's own open-access links need no address; Unpaywall's extra open copies do." }),
    h("div", { class: "save-row" }, h("span", { class: "muted small" }, "Saved as soon as you change it."), state));
}
