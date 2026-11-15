// Margin 0.1: check a draft. The researcher's own writing, with the statements that need a source marked in it, and
// for each the documents of the project that support or contradict it. Two steps: find the claims (the AI, or rules
// without AI; the person keeps, drops, rewords and adds claims by selecting a sentence), then check them against
// the documents (each claim is a hypothesis of its own, with its full result page).
// Margin 0.3: the person decides on each claim (supported, refuted, dismissed): its card folds to what matters and its
// highlight in the draft says a source should be cited there; the claims scroll on their own beside the draft, and a
// click anywhere on a card shows its sentence in the draft.
// Margin 0.5: with a bibliography (Zotero, or an exported file), each document to cite has its APA 7 in-text
// citation on a button that copies it, "(Verhoeven & Okafor, 2025)", ready to paste into the text; several in one.
// With ENLENS 0.13.7's Check citations: the draft's own citations are found when it is added (no AI), and a third
// step checks each against the cited work's document only. A citation is underlined in the draft by its answer, and
// the claim it stands for shows it: what the documents say (step 2) and whether your own source says it (step 3).
// Margin: the draft read against itself, without AI (consistency.py): where it may contradict itself, what is
// inconsistent (numbers, abbreviations, spelling) and what may confuse a reader, each with its places in the draft.
import { featureEyebrow } from "../features.js";
import { App, api, h, icon, replace, clear, toast, showError, fmt, pageHead, watchJob, P, emptyState, statusBadge, confirmDialog, dialog, download, TERMINAL, runningJob, plural, session, queueNotice, navigate,
  button, downloadLinks, fileButton, link, notice, tag, fold as foldEl, field, input as inputEl, textarea as textareaEl, select as selectEl, choice as pickOne,
  card as makeCard, listGroup, listRow, withAI, readsLine, aiWhere, judgementIcon, workState } from "../lib.js";
import { ProgressPanel, jobCard } from "./progress.js";
import { LEVEL, levels, accessBadge, accessChoice } from "./ai-access.js";

const SUB = {
  cloud: "Claude (or the AI you chose) reads it to find the claims and checks them. Each part it reads is recorded.",
  local: "Only a model on this computer reads it; without one, rules find the claims. Never sent to Claude.",
  none: "No AI reads it: rules find the likely claims, and you judge the excerpts found for each.",
};
const ADVICE = {
  supported: "Your documents back this: cite them.",
  partially_supported: "Your documents back part of it: read the excerpts and check your wording.",
  contested: "Your documents disagree: cite both sides, or qualify the claim.",
  contradicted: "Your documents say otherwise: revise the claim, or say why your source differs.",
  uncertain: "Only weak evidence: read the excerpts and judge them yourself.",
  unsupported: "Nothing read backs this: cite another source, soften the claim, or look for more evidence on the result page.",
  no_passages: "No document uses words close to this: cite another source, or add the document it comes from.",
  failed: "The check did not work: open the result to try again.",
  waiting: "Waiting for Claude Code to read the excerpts.",
  not_checked: "",
};
const SIDES = [["supports", "Supports it", "supports", "ok"], ["partly", "Partly supports it", "partially_supports", "partly"], ["refutes", "Contradicts it", "refutes", "bad"]];   // [evidence key, words, judgement, look]
const FILTERS = [["all", "All"], ["open", "To decide"], ["you_supported", "You: supported"], ["you_refuted", "You: refuted"], ["cite_notice", "Citation to look at"], ["unchecked", "Not checked"], ["supported", "Supported"], ["partially_supported", "Partly supported"], ["contested", "Mixed evidence"], ["contradicted", "Contradicted"], ["unsupported", "No evidence"], ["no_passages", "Nothing matched"], ["uncertain", "Uncertain"], ["waiting", "Waiting"], ["skip", "Dismissed"]];
// the person's decisions on a claim (Margin 0.3); `side` is the evidence the folded card names as what to cite
const DECIDE = {
  supported: { label: "Claim supported", seg: "Supported", short: "You: supported", side: "supports", cite: "Cite a source here", none: "Cite the source that supports it here." },
  refuted: { label: "Claim refuted", seg: "Refuted", short: "You: refuted", side: "refutes", cite: "Cite or revise here", none: "Cite the source that contradicts it, or revise the sentence." },
  dismissed: { label: "Dismiss claim", seg: "Dismiss", short: "Dismissed", title: "Not a claim that needs a source" },
};

const ALT_CLICK = /Mac|iPhone|iPad/.test(navigator.platform || "") ? "Option-click" : "Alt-click";

const statusOf = (c) => (c.skip ? "skip" : c.status || "unchecked");
const decided = (c) => c.decision === "supported" || c.decision === "refuted";
const matches = (c, k) => (k === "all" ? true : k === "open" ? !c.decision : k === "you_supported" ? c.decision === "supported"
  : k === "you_refuted" ? c.decision === "refuted" : k === "cite_notice" ? citeNotice(c) : statusOf(c) === k);

// the draft's citations (step 3): the answer of each cited work, in Check citations' groups, as a look in the draft
const CITE_NOTICES = ["contradicted", "mixed", "partly", "not_found", "unsure", "failed"];
const CITE_LOOK = { accurate: "ok", contradicted: "bad", mixed: "bad", partly: "partly", not_found: "partly", unsure: "partly", failed: "partly",
  checking: "wait", ready: "wait", ignored: "off", contrast: "off" };  // anything else cannot be checked yet: "blocked"
const CITE_ORDER = ["contradicted", "mixed", "partly", "not_found", "failed", "unsure", "checking", "ready", "accurate"];
const citeLook = (g) => CITE_LOOK[g] || "blocked";
const citesOf = (c) => (c.citations || []).filter((r) => !r.ignored);
const citeNotice = (c) => citesOf(c).some((r) => CITE_NOTICES.includes(r.group));
const citeName = (r) => r.work || (r.raw.length > 60 ? `${r.raw.slice(0, 57)}…` : r.raw);
// the draft read against itself: its groups, how each opens, and the short name of each kind of notice on a claim
const SELF_GROUPS = [["contradiction", "split", true], ["inconsistency", "layers", false], ["unclear", "help", false]];
const SELF_KIND = { opposite: "may contradict", numbers: "gives another number than", same_passage: "may contradict", answers_differ: "got another answer than",
  pronoun: "Opens with “This …”", strength: "Careful and absolute at once", overloaded: "Several claims in one sentence" };
const clip = (s, n = 140) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

// The AI of a draft, by its own setting (docs/DESIGN.md 4.4): a button that sends text to the AI carries the mark, and the
// card says once who reads. "No AI": rules do the work, so there is neither mark nor line.
const withAIFor = (level, ...buttons) => (level === "none" ? buttons : withAI(...buttons));
function aiLine(level, what) {
  if (level === "none") return null;
  if (level === "local") return aiWhere(`Only a model on this computer reads ${what}; without one, rules find the claims and you judge the excerpts.`, "local");
  return readsLine(what);
}

// ---------------------------------------------------------------------------------------------
// the list of drafts, and a new one
// ---------------------------------------------------------------------------------------------
export async function renderDrafts(view) {
  const project = App.project;
  let res;
  try { res = await api("GET", `/api/projects/${P(project)}/drafts`); } catch (e) { showError(e); res = { drafts: [], default: "cloud" }; }
  view.appendChild(pageHead("Check a draft", {
    eyebrow: featureEyebrow("drafts"),
    sub: "Paste or load what you are writing. The AI marks the statements a reader would want a source for, then checks each one against the documents of this project: which support it, which contradict it, and what you could cite.",
  }));
  view.appendChild(h("ol", { class: "plain-steps muted draft-steps-intro" },
    h("li", {}, h("strong", {}, "Find the claims. "), "Numbers, causes and effects, comparisons, what research found: each marked in your text, with the exact sentence."),
    h("li", {}, h("strong", {}, "Keep the ones you want checked. "), "Drop, reword, or select a sentence to add one."),
    h("li", {}, h("strong", {}, "Check them. "), "Each gets the documents that support or contradict it, with quotes checked against the source."),
    h("li", {}, h("strong", {}, "Check your citations. "), "Each source your draft cites, such as (Smith, 2020), is checked against its own document: does it say what your sentence says?")));

  let level = res.default && levels().includes(res.default) ? res.default : levels()[0];
  const aiBox = h("div", { class: "draft-ai-line" });
  const aiFor = (lv) => replace(aiBox, aiLine(lv, "the parts of your draft it needs to find the claims, and the excerpts to check them"));
  const accessPick = accessChoice({ value: level, name: "draft-access", many: false, onChange: (v) => { level = v; aiFor(v); } });
  accessPick.querySelector("legend").textContent = "Who may read this draft with AI?";
  for (const lv of levels()) { const el = accessPick.querySelector(`.option-card[data-value="${lv}"] .option-card-sub`); if (el) el.textContent = SUB[lv]; }
  aiFor(level);

  const title = inputEl({ id: "draft-title", placeholder: "For example: Chapter 2, literature review", maxlength: 200 });
  const ta = textareaEl({ class: "draft-input", id: "draft-text", rows: 10, placeholder: "Paste a section, a chapter or the whole paper…" });
  ta.value = session("draftText") || "";
  ta.addEventListener("input", () => { session("draftText", ta.value); goBtn.disabled = ta.value.trim().length < 40; });
  const goBtn = button({ kind: "main", disabled: ta.value.trim().length < 40 }, "Find the claims");
  const fileInput = h("input", { type: "file", accept: ".docx,.pdf,.txt,.md,.html,.htm", id: "draft-file" });
  const fileBtn = fileButton({ kind: "standard", sm: false, icon: "upload" }, fileInput, "Load a file");
  const status = h("span", { class: "muted small", role: "status" });

  async function start(draft) {
    session("draftText", null);
    try {
      const r = await api("POST", `/api/projects/${P(project)}/drafts/${P(draft.draft_id)}/find`, {});
      navigate(`#/drafts/${encodeURIComponent(draft.draft_id)}?job=${encodeURIComponent(r.job.id)}`);
    } catch (e) { showError(e); navigate(`#/drafts/${encodeURIComponent(draft.draft_id)}`); }
  }
  goBtn.addEventListener("click", async () => {
    goBtn.disabled = true;
    try {
      const r = await api("POST", `/api/projects/${P(project)}/drafts`, { text: ta.value, title: title.value.trim() || null, ai_access: level });
      await start(r.draft);
    } catch (e) { showError(e); goBtn.disabled = false; }
  });
  fileInput.addEventListener("change", async () => {
    const f = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!f) return;
    status.textContent = `Reading ${f.name}…`;
    try {
      const q = `name=${encodeURIComponent(f.name)}&ai_access=${encodeURIComponent(level)}${title.value.trim() ? `&title=${encodeURIComponent(title.value.trim())}` : ""}`;
      const r = await api("POST", `/api/projects/${P(project)}/drafts/upload?${q}`, f);
      await start(r.draft);
    } catch (e) { status.textContent = ""; showError(e); }
  });

  view.appendChild(makeCard({ class: "draft-new", title: "A new draft", titleId: "draft-new-h" },
    field(["Title ", h("span", { class: "muted small" }, "(optional)")], title),
    field("Your text", ta, { help: "Or load a Word file, a PDF, a text or Markdown file. Your draft is kept apart from the documents: it is never used as evidence." }),
    accessPick,
    h("div", { class: "btn-row draft-new-go" }, withAIFor(level, goBtn), fileBtn, status),
    aiBox));

  const list = res.drafts || [];
  view.appendChild(h("section", { class: "section", "aria-label": "Your drafts" },
    h("div", { class: "section-title" }, h("h2", {}, "Your drafts"), h("span", { class: "muted" }, list.length ? plural(list.length, "draft", "drafts") : "none yet")),
    list.length ? makeCard({ class: "draft-list" }, listGroup(null, ...list.map((d) => listRow({
      title: d.title, href: `#/drafts/${encodeURIComponent(d.draft_id)}`, serif: true, time: fmt.dateShort(d.created_at),
      sub: [d.file_name, `${fmt.num(Math.round(d.chars / 6))} words`,
        d.claims ? `${plural(d.claims, "claim", "claims")} · ${d.checked} checked` : d.found_at ? "no claims found" : "not read yet",
        d.citations ? plural(d.citations, "citation", "citations") : null].filter(Boolean).join(" · "),
      actions: [accessBadge(d.ai_access)] }))))
      : emptyState("file-pen", "No draft yet", "Paste a section of what you are writing above: it takes a minute to see which claims your documents back.")));
}

// ---------------------------------------------------------------------------------------------
// one draft
// ---------------------------------------------------------------------------------------------
export async function renderDraft(view, [draftId], query) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/drafts/${P(draftId)}`;
  let data;
  try { data = await api("GET", base); }
  catch (e) {
    if (e.status === 404) { view.appendChild(emptyState("search-x", "This draft no longer exists", "It was removed, or it belongs to another project.", link({ kind: "next", href: "#/drafts" }, "All drafts"))); return; }
    throw e;
  }
  let filter = "all";
  let picked = null;
  const unfolded = new Set();  // decided claims shown in full for now
  let watchers = [];
  let refreshTimer = null;
  let alive = true;
  let inner = null;           // the draft read against itself (GET …/consistency)
  let showAside = false;     // the notices set aside, shown again
  const openSelf = new Set(SELF_GROUPS.filter(([, , open]) => open).map(([g]) => g));

  const head = h("div");
  const setting = h("div", { class: "draft-setting" });
  const steps = makeCard({ class: "draft-steps", "aria-label": "Steps" });
  const stepsBody = h("div");
  const jobBox = h("div", { class: "draft-job", hidden: true });
  steps.append(stepsBody, jobBox);
  const chips = h("div", { class: "draft-filter" });
  const textBox = h("div", { class: "draft-text", id: "draft-text-view" });
  const markBtn = button({ sm: true, icon: "plus", hidden: true, class: "draft-mark-btn" }, "Mark as a claim");
  const textWrap = h("div", { class: "draft-text-wrap" }, textBox, markBtn);
  const list = h("div", { class: "draft-claims" });
  const board = h("div", { class: "draft-board" },
    h("section", { class: "draft-col draft-col-text", "aria-label": "Your draft" },
      h("div", { class: "section-title" }, h("h2", {}, "Your draft"), h("span", { class: "muted" }, "select a sentence to mark it as a claim")), textWrap),
    h("section", { class: "draft-col draft-col-claims", "aria-label": "Claims" },
      h("div", { class: "section-title" }, h("h2", {}, "Claims"), h("span", { class: "muted draft-claims-count" })), chips, list));
  const selfBox = h("div", { class: "draft-self-host", hidden: true });
  view.append(head, setting, steps, selfBox, board);

  async function reload() {
    try { data = await api("GET", base); } catch (e) { if (e.status !== 404) showError(e); return; }
    if (!alive) return;
    drawAll();
    loadSelf();
  }

  // --- the draft read against itself (no AI)
  async function loadSelf() {
    try { inner = await api("GET", `${base}/consistency`); } catch (_) { return; }
    if (!alive) return;
    drawSelf();
    drawList(numbered());
  }

  const claimNo = (id) => data.claims.findIndex((c) => c.claim_id === id) + 1;

  function drawSelf() {
    if (!inner) return;
    selfBox.hidden = false;
    const open = inner.notices.filter((n) => !n.dismissed);
    const shown = showAside ? inner.notices : open;
    const intro = h("p", { class: "muted small ds-intro" }, `Without AI: where it may contradict itself, what is inconsistent, and what may confuse a reader. Read ${plural(inner.read.sentences, "sentence", "sentences")}${inner.read.checked ? ` and the checks of ${plural(inner.read.checked, "claim", "claims")}` : ""}. Each notice is a prompt to look, not a verdict.`);
    const groups = SELF_GROUPS.map(([g, ic]) => {
      const items = shown.filter((n) => n.group === g);
      if (!items.length) return null;
      const n = inner.counts[g] || 0;
      const box = foldEl({ open: openSelf.has(g), class: `ds-group ds-${g}` },
        [icon(ic, { size: 14 }), h("span", { class: "ds-group-name" }, inner.groups[g]), tag({ kind: g === "contradiction" ? "attention" : "count" }, String(n))],
        h("div", { class: "ds-list" }, items.map(noteRow)));
      box.addEventListener("toggle", () => { if (box.open) openSelf.add(g); else openSelf.delete(g); });
      return box;
    }).filter(Boolean);
    const aside = inner.dismissed ? button({ kind: "quiet", sm: true, class: "ds-aside", "aria-pressed": String(showAside), onClick: () => { showAside = !showAside; drawSelf(); } },
      showAside ? "Hide the notices set aside" : `Show ${plural(inner.dismissed, "notice", "notices")} set aside`) : null;
    replace(selfBox, makeCard({ class: "draft-self", title: "Your draft against itself", titleId: "draft-self-h", action: open.length ? tag({ kind: "count" }, plural(open.length, "notice", "notices")) : null },
      intro,
      groups.length ? h("div", { class: "ds-groups" }, groups)
        : notice({ kind: "done", class: "ds-none" }, h("p", {}, "Nothing found: no contradictions, inconsistencies or unclear sentences that these rules can see.")),
      aside));
  }

  function noteRow(n) {
    const places = n.places.map((p, i) => {
      const no = p.claim_id ? claimNo(p.claim_id) : 0;
      const b = button({ kind: "quiet", sm: true, wrap: true, class: "ds-place", title: "Show it in the draft" },
        h("span", { class: "ds-place-n" }, no ? `Claim ${no}` : n.places.length > 1 ? `Place ${i + 1}` : "In the draft"),
        h("q", {}, clip(p.quote)));
      b.addEventListener("click", () => showPlaces(n, i));
      return b;
    });
    const btn = n.dismissed
      ? button({ kind: "quiet", sm: true, onClick: () => setAside(n, false) }, "Show again")
      : button({ kind: "quiet", sm: true, icon: "x", title: "Set this notice aside: it stays aside while these sentences are the same", onClick: () => setAside(n, true) }, "Not a problem");
    return h("article", { class: `ds-note${n.dismissed ? " ds-dismissed" : ""}`, "data-key": n.key },
      h("p", { class: "ds-text" }, n.text), h("div", { class: "ds-places" }, places), h("div", { class: "btn-row ds-actions" }, btn));
  }

  async function setAside(n, dismissed) {
    try {
      await api("PUT", `${base}/notices/${P(n.key)}`, { dismissed });
      n.dismissed = dismissed;
      inner.dismissed += dismissed ? 1 : -1;
      if (inner.counts[n.group] != null) inner.counts[n.group] += dismissed ? -1 : 1;
      drawSelf();
      drawList(numbered());
    } catch (e) { showError(e); }
  }

  // The places of a notice, highlighted in the draft; the one clicked is scrolled to (a claim's is also picked).
  function rangeAt(start, end) {
    const walker = document.createTreeWalker(textBox, NodeFilter.SHOW_TEXT);
    const r = document.createRange();
    let pos = 0, started = false;
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const len = node.data.length;
      if (!started && start <= pos + len) { r.setStart(node, Math.max(0, start - pos)); started = true; }
      if (started && end <= pos + len) { r.setEnd(node, Math.max(0, end - pos)); return r; }
      pos += len;
    }
    return started ? r : null;
  }

  function showPlaces(n, i) {
    const ranges = n.places.map((p) => rangeAt(p.start, p.end)).filter(Boolean);
    const target = rangeAt(n.places[i].start, n.places[i].end);
    if (!target) return;
    if (window.CSS && CSS.highlights && window.Highlight) CSS.highlights.set("draft-self", new Highlight(...ranges));
    else { const sel = document.getSelection(); sel.removeAllRanges(); sel.addRange(target); }
    const id = n.places[i].claim_id;
    if (id) {  // its claim card is picked too, without moving the claims
      picked = id;
      for (const m of textBox.querySelectorAll("mark.dm")) m.classList.toggle("dm-picked", m.dataset.id === id);
      for (const el of list.querySelectorAll(".dc-card")) el.classList.toggle("dc-picked", el.dataset.id === id);
    }
    reveal(textBox, { getBoundingClientRect: () => target.getBoundingClientRect(),
      scrollIntoView: (o) => window.scrollBy({ top: target.getBoundingClientRect().top - innerHeight / 2, behavior: o.behavior }) });
  }

  // On a claim's card: the notices it is in (the other claim it may contradict, or why it may confuse a reader).
  function selfLine(c) {
    if (!inner) return null;
    const mine = inner.notices.filter((n) => !n.dismissed && n.places.some((p) => p.claim_id === c.claim_id));
    if (!mine.length) return null;
    return h("div", { class: "ds-on-claim small" }, mine.slice(0, 3).map((n) => {
      const other = n.places.find((p) => p.claim_id !== c.claim_id);
      const label = n.group === "unclear" ? SELF_KIND[n.kind]
        : n.group === "contradiction" ? `${SELF_KIND[n.kind][0].toUpperCase()}${SELF_KIND[n.kind].slice(1)} ${other && other.claim_id ? `claim ${claimNo(other.claim_id)}` : "another sentence of your draft"}`
        : n.text.split(". ")[0];
      return link({ kind: "jump", title: n.text, onClick: () => showNote(n) },
        icon(n.group === "unclear" ? "help" : n.group === "contradiction" ? "split" : "layers", { size: 12 }), label);
    }));
  }

  function showNote(n) {
    openSelf.add(n.group);
    drawSelf();
    const el = selfBox.querySelector(`.ds-note[data-key="${CSS.escape(n.key)}"]`);
    if (el) { el.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); el.classList.add("ds-flash"); setTimeout(() => el.classList.remove("ds-flash"), 1600); }
    showPlaces(n, 0);
  }

  function drawAll() {
    drawHead();
    drawSetting();
    drawSteps();
    drawBoard();
  }

  // --- head
  function drawHead() {
    const d = data.draft;
    const files = data.claims.length ? downloadLinks([
      { text: "Excel (.xlsx)", onClick: () => download(`${base}/export.xlsx`).catch(showError) },
      { text: "CSV", onClick: () => download(`${base}/export.csv`).catch(showError) }]) : null;
    replace(head, pageHead(d.title, {
      display: true,
      back: { href: "#/drafts", text: "All drafts" },
      facts: [`${fmt.num(d.words)} words`, `added ${fmt.dateShort(d.created_at)}`, d.file_name ? `from ${d.file_name}` : null].filter(Boolean),
      actions: [files, button({ kind: "quiet", sm: true, onClick: renameDialog }, "Rename"), button({ kind: "danger", sm: true, icon: "trash", onClick: removeDraft }, "Remove")].filter(Boolean),
    }));
  }

  async function renameDialog() {
    const input = inputEl({ value: data.draft.title, maxlength: 200 });
    const t = await dialog({
      title: "Rename the draft", body: field("Title", input),
      actions: [{ text: "Cancel", value: null }, { text: "Rename", primary: true, onClick: () => { if (!input.value.trim()) return false; return true; }, value: "ok" }],
      onOpen: () => { input.focus(); input.select(); input.addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.closest("dialog").querySelector(".btn-primary").click(); }); },
    });
    if (t !== "ok") return;
    try { await api("PUT", base, { title: input.value.trim() }); await reload(); } catch (e) { showError(e); }
  }

  async function removeDraft() {
    const n = data.counts.checked;
    const ok = await confirmDialog({ title: "Remove this draft?", message: `The draft, its ${plural(data.counts.claims, "claim", "claims")}${n ? ` and the ${plural(n, "check", "checks")} of them under Results` : ""} are removed. Your documents are not touched.`, confirmText: "Remove" });
    if (!ok) return;
    try { await api("DELETE", base); toast("The draft was removed.", "ok"); navigate("#/drafts"); } catch (e) { showError(e); }
  }

  // --- the AI setting, and what Claude has read
  function drawSetting() {
    const d = data.draft;
    const sel = selectEl({ sm: true, "aria-label": "Who may read this draft with AI", "data-level": d.ai_access },
      ...levels().map((lv) => h("option", { value: lv, selected: d.ai_access === lv }, LEVEL[lv].title)));
    sel.addEventListener("change", async () => {
      sel.disabled = true;
      try { await api("PUT", base, { ai_access: sel.value }); toast(`${LEVEL[sel.value].title}: this applies to the finding and to every check of this draft not answered yet.`, "ok"); await reload(); }
      catch (e) { showError(e); sel.disabled = false; }
    });
    const s = data.sent || {};
    const bits = [s.parts_read ? `${plural(s.parts_read, "part", "parts")} of it to find the claims` : null,
      s.claims_read ? `${plural(s.claims_read, "claim", "claims")} to check ${s.claims_read === 1 ? "it" : "them"}` : null].filter(Boolean);
    const read = s.times && bits.length ? `Claude has read ${bits.join(" and ")}; last ${fmt.date(s.last)}.`
      : d.ai_access !== "cloud" ? "This draft is never sent to Claude."
      : ["claude_code", "anthropic"].includes(App.settings().backend) ? "Claude has not read this draft yet."
      : "The AI runs on this computer: nothing of this draft has left it.";
    replace(setting, h("label", { class: "it" }, icon(LEVEL[d.ai_access].icon, { size: 14 }), h("span", { class: "muted small" }, "Who may read it with AI:"), sel),
      h("span", { class: "muted small" }, read));
  }

  // --- the two steps
  function drawSteps() {
    const c = data.counts, f = data.finding || {}, d = data.draft;
    const running = watchers.length > 0;
    const docs = data.documents || 0;
    // one main button in the card: the step that is next
    const ct = data.citations;
    const next = !d.found_at && !c.claims ? 1 : c.to_check && docs ? 2 : ct && ct.ready ? 3 : 0;
    const level = d.ai_access;
    const findAgain = !!(d.found_at || c.claims);
    const findBtn = button({ kind: next === 1 ? "main" : findAgain ? "quiet" : "standard", sm: findAgain, icon: d.found_at ? "refresh" : null, disabled: running }, d.found_at ? "Find again" : "Find the claims");
    findBtn.addEventListener("click", async () => {
      if (d.found_at && !(await confirmDialog({ title: "Find the claims again?", message: "The claims you have not checked, decided on, reworded or dismissed are found anew. The others, and the ones you marked, stay.", confirmText: "Find again", danger: false }))) return;
      startJob("find", {});
    });
    const by = d.found_by === "rules" ? "by rules (no AI)" : "by the AI";
    const step1 = h("div", { class: "draft-step" },
      h("span", { class: `draft-step-n ${d.found_at ? "done" : ""}` }, d.found_at ? icon("check", { size: 14 }) : "1"),
      h("div", { class: "grow" },
        h("h3", {}, "Find the claims that need a source"),
        f.waiting && !running ? queueNotice({ text: `Waiting for Claude Code: ${plural(f.waiting, "part of the draft", "parts of the draft")} to read`, command: data.queue_command })
          : h("p", { class: "muted small" }, d.found_at ? `${plural(c.claims, "claim", "claims")} found ${by}, ${fmt.date(d.found_at)}${c.cited ? `; ${c.cited} already cited in your draft` : ""}.` : SUB[d.ai_access]),
        f.failed ? foldEl({ sm: true }, `${plural(f.failed, "part", "parts")} of the draft could not be read; find again to try once more`,
          h("ul", { class: "mono small" }, (f.errors || []).map((e) => h("li", {}, e)))) : null),
      h("div", { class: "draft-step-act" }, withAIFor(level, findBtn)));
    const checkBtn = button({ kind: next === 2 ? "main" : "standard", icon: "play", disabled: running || !c.to_check || !docs }, c.to_check ? `Check ${c.to_check === 1 ? "this claim" : `${c.to_check} claims`}` : "Check the claims");
    checkBtn.addEventListener("click", () => startJob("check", {}));
    const step2 = h("div", { class: "draft-step" },
      h("span", { class: `draft-step-n ${c.checked && !c.to_check ? "done" : ""}` }, c.checked && !c.to_check ? icon("check", { size: 14 }) : "2"),
      h("div", { class: "grow" },
        h("h3", {}, "Check them against your documents"),
        h("p", { class: "muted small" }, !docs ? h("span", {}, "This project has no documents yet. ", link({ href: "#/sources" }, "Add the documents your draft draws on"), ", then check the claims.")
          : !c.claims ? "Find the claims first, or select a sentence in your draft to mark one."
          : c.to_check ? `${plural(c.to_check, "claim waits", "claims wait")} to be checked; ${c.checked} checked so far. Each is checked like a hypothesis, against all ${plural(docs, "document", "documents")}.`
          : doneText(c))),
      c.to_check || !c.checked ? h("div", { class: "draft-step-act" }, withAIFor(level, checkBtn)) : null);
    replace(stepsBody, step1, step2, citeStep(running, next === 3), aiLine(level, "the parts of your draft, the claims and the excerpts they need"));
  }

  // Step 3: the draft's own citations, each checked against the document of the work it cites (Check citations).
  function citeStep(running, isNext) {
    const ct = data.citations;
    if (!ct) return null;
    const done = !ct.ready && !ct.checking && (ct.accurate || ct.notices);
    const said = [ct.accurate ? `${ct.accurate} source accurate` : null, ct.notices ? `${ct.notices} to look at` : null,
      ct.checking ? `${ct.checking} being checked` : null, ct.ready ? `${ct.ready} not checked yet` : null,
      ct.blocked ? `${ct.blocked} cannot be checked yet` : null].filter(Boolean);
    const line = `${plural(ct.citations, "citation", "citations")} in your draft${ct.works ? `, of ${plural(ct.works, "work", "works")} in your bibliography` : ""}${said.length ? `: ${said.join(", ")}` : ""}.`;
    const help = !ct.has_bibliography ? h("span", {}, " Bring in your ", link({ href: "#/bibliography" }, "bibliography"), " first: each citation is matched with its work, and checked against that work’s document.")
      : ct.ready ? " Each is checked against its own source’s document only: does it say what your sentence says?"
      : !ct.accurate && !ct.notices && ct.blocked ? " Each needs a work of your bibliography whose document is in this project." : null;
    const btn = button({ kind: isNext ? "main" : "standard", icon: "play", disabled: running }, ct.ready === 1 ? "Check this citation" : `Check ${ct.ready} citations`);
    btn.addEventListener("click", () => startCitations({}));
    return h("div", { class: "draft-step draft-step-cite" },
      h("span", { class: `draft-step-n ${done ? "done" : ""}` }, done ? icon("check", { size: 14 }) : "3"),
      h("div", { class: "grow" },
        h("h3", {}, "Check your citations against their sources"),
        h("p", { class: "muted small" }, line, help),
        ct.numeric_unread ? h("p", { class: "muted small" }, icon("info", { size: 12 }), ` ${plural(ct.numeric_unread, "numbered citation", "numbered citations")} ([1], [2]…) could not be read: the draft has no numbered reference list at its end.`) : null,
        h("p", { class: "small draft-cite-link" }, link({ href: `#/citations/${encodeURIComponent(ct.text_id)}` }, "Review every citation"),
          h("span", { class: "muted" }, " · choose the work of a citation, or leave one out"))),
      ct.ready ? h("div", { class: "draft-step-act" }, withAIFor(data.draft.ai_access, btn)) : null);
  }

  async function startCitations(body) {
    try {
      const r = await api("POST", `/api/projects/${P(project)}/citations/${P(data.citations.text_id)}/check`, body);
      follow(r.job);
    } catch (e) { showError(e); }
  }

  function doneText(c) {
    const own = data.claims.filter((x) => decided(x) && !x.hyp_id).length;
    const bits = [c.checked ? `${c.checked} checked` : null, own ? `${own} decided by you without a check` : null, c.claims - c.kept ? `${c.claims - c.kept} dismissed` : null].filter(Boolean);
    return `Nothing left to check${bits.length ? `: ${bits.join(", ")}` : ""}.${c.checked ? " Every result is also under Results." : ""}`;
  }

  async function startJob(kind, body) {
    try {
      const r = await api("POST", `${base}/${kind === "find" ? "find" : "check"}`, body);
      follow(r.job);
    } catch (e) { showError(e); }
  }

  function follow(job) {
    const done = async (j) => {
      watchers = watchers.filter((w) => w !== watcher);
      clearInterval(refreshTimer);
      await reload();
      if (!alive) return;
      if (j.state === "done") {
        const r = j.result || {};
        if (j.kind === "draft-find") toast(r.note ? r.note : `Found ${plural(r.found || 0, "claim", "claims")}${r.failed ? `; ${plural(r.failed, "part", "parts")} could not be read` : ""}.`, r.failed ? "warn" : "ok", { ttl: r.note ? 7000 : 3500 });
        else if (j.kind === "citations") toast(`Checked ${plural((r.checked || []).length, "citation", "citations")}${(r.errors || []).length ? `; ${r.errors.length} could not be checked` : ""}.`, (r.errors || []).length ? "warn" : "ok");
        else toast(`Checked ${plural((r.checked || []).length, "claim", "claims")}${(r.errors || []).length ? `; ${r.errors.length} could not be checked` : ""}.`, (r.errors || []).length ? "warn" : "ok");
        jobBox.hidden = true;
      }
    };
    let watcher;
    if (job.kind === "draft-find") {
      watcher = jobCard(jobBox, job.id, "Finding the claims", (p, j) => (p.total ? `${p.message || "Reading your draft"} (${Math.min(p.done + 1, p.total)} of ${p.total})` : p.message || (j.queue ? "Waiting for Claude Code" : "Reading your draft…")), done, { small: true, plain: true, stoppedText: "Stopped. The claims found so far are kept." });
    } else {
      const panel = job.kind === "citations"
        ? new ProgressPanel({ title: "Checking the citations", batchWords: { doing: "checking citation", done: "citations checked" } })
        : new ProgressPanel({ title: "Checking the claims", batchWords: { doing: "checking claim", done: "claims checked" } });
      replace(jobBox, panel.el);
      jobBox.hidden = false;
      watcher = watchJob(job.id, (j) => panel.update(j));
      watcher.promise.then(done).catch((e) => { watchers = watchers.filter((w) => w !== watcher); showError(e); });
      refreshTimer = setInterval(() => { if (alive) reloadQuiet(); }, 5000);  // the answers appear as they come in
    }
    watchers.push(watcher);
    drawSteps();
  }

  async function reloadQuiet() {
    try { data = await api("GET", base); } catch (_) { return; }
    if (alive) { drawSetting(); drawBoard(); }
  }

  // --- the draft and its claims
  function numbered() {
    return data.claims.map((c, i) => ({ ...c, n: i + 1 }));
  }

  function drawBoard() {
    const claims = numbered();
    drawText(claims);
    drawChips(claims);
    drawList(claims);
  }

  // The citations of the draft, one per place (a citation of two works takes the answer that needs a look first).
  function citeMarks() {
    const by = new Map();
    for (const r of (data.citations || {}).refs || []) {
      if (r.start == null) continue;
      const m = by.get(r.cite_id) || { start: r.start, end: r.end, refs: [] };
      m.refs.push(r);
      by.set(r.cite_id, m);
    }
    const rank = (g) => { const i = CITE_ORDER.indexOf(g); return i < 0 ? CITE_ORDER.length : i; };
    return [...by.values()].map((m) => ({ ...m, group: m.refs.map((r) => r.group).sort((a, b) => rank(a) - rank(b))[0] }))
      .sort((a, b) => a.start - b.start);
  }

  // text[a:b] with its citations underlined by their answer (the claim's mark stays around them)
  function pieces(a, b, marks) {
    const text = data.text;
    const out = [];
    let pos = a;
    for (const m of marks) {
      if (m.end <= pos || m.start >= b) continue;
      const s = Math.max(m.start, pos), e = Math.min(m.end, b);
      if (s > pos) out.push(document.createTextNode(text.slice(pos, s)));
      out.push(h("span", { class: `dcit dcit-${citeLook(m.group)}`, title: m.refs.map((r) => `${citeName(r)}: ${r.text}`).join("\n") }, text.slice(s, e)));
      pos = e;
    }
    if (pos < b) out.push(document.createTextNode(text.slice(pos, b)));
    return out;
  }

  function drawText(claims) {
    clear(textBox);
    const text = data.text;
    const marks = citeMarks();
    let pos = 0;
    for (const c of claims) {
      const s = Math.max(c.start, pos);
      if (s >= c.end) continue;
      if (s > pos) textBox.append(...pieces(pos, s, marks));
      const st = statusOf(c);
      const you = decided(c) ? DECIDE[c.decision] : null;
      const cite = you ? (c.cited ? "cited" : "cite here") : null;
      const said = st === "unchecked" ? "not checked yet" : st === "skip" ? "dismissed" : App.statusText(st) || st;
      const m = h("mark", { class: `dm dm-${st}${you ? ` dm-you dm-you-${c.decision}` : ""}${picked === c.claim_id ? " dm-picked" : ""}`, "data-n": String(c.n), "data-id": c.claim_id, "data-cite": cite, tabindex: "0", role: "button",
        "aria-label": you ? `Claim ${c.n}: ${c.decision === "supported" ? "you marked it supported" : "you marked it refuted"}; ${c.cited ? "your draft cites a source here" : "a source should be cited here"}` : `Claim ${c.n}: ${said}`,
        title: you ? `Claim ${c.n}: ${c.cited ? "your draft cites a source here" : you.cite.toLowerCase()}` : `Claim ${c.n}` }, ...pieces(s, c.end, marks));
      m.addEventListener("click", () => pick(c.claim_id, "card"));
      m.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(c.claim_id, "card"); } });
      textBox.append(m);
      pos = c.end;
    }
    if (pos < text.length) textBox.append(...pieces(pos, text.length, marks));
  }

  function drawChips(claims) {
    const count = (k) => claims.filter((c) => matches(c, k)).length;
    if (filter !== "all" && !count(filter)) filter = "all";
    const options = FILTERS.map(([k, label]) => [k, label, count(k)])
      .filter(([k, , n]) => (k === "all" || n) && !(k === "open" && n === claims.length));  // nothing decided yet: "To decide" is the same as All
    replace(chips, pickOne({ filter: true, label: "Show claims", options, value: filter, onPick: (k) => { filter = k; drawBoard(); } }));
    const cnt = view.querySelector(".draft-claims-count");
    const nd = claims.filter((c) => c.decision).length;
    if (cnt) cnt.textContent = claims.length ? `${plural(claims.length, "claim", "claims")}, in the order of the draft${nd ? `; ${nd} decided` : ""}` : "";
  }

  function drawList(claims) {
    clear(list);
    if (!claims.length) {
      list.appendChild(emptyState("file-pen", data.draft.found_at ? "No claims found" : "No claims yet",
        data.draft.found_at ? "Nothing in this draft looked like a claim that needs a source. Select a sentence in your draft to mark one." : "Press Find the claims above, or select a sentence in your draft to mark one."));
      return;
    }
    for (const c of claims) {
      if (!matches(c, filter)) continue;
      list.appendChild(c.decision && !unfolded.has(c.claim_id) ? foldedCard(c) : claimCard(c));
    }
  }

  function pick(id, scrollTo) {
    picked = id;
    for (const m of textBox.querySelectorAll("mark.dm")) m.classList.toggle("dm-picked", m.dataset.id === id);
    for (const el of list.querySelectorAll(".dc-card")) el.classList.toggle("dc-picked", el.dataset.id === id);
    const target = scrollTo === "card" ? list.querySelector(`.dc-card[data-id="${CSS.escape(id)}"]`) : textBox.querySelector(`mark.dm[data-id="${CSS.escape(id)}"]`);
    if (!target && scrollTo === "card" && filter !== "all") { filter = "all"; drawBoard(); return pick(id, scrollTo); }
    if (target) reveal(scrollTo === "card" ? list : textBox, target);
  }

  // Scroll only the pane that holds `el` (the draft, or the claims), so the other pane stays where it is. When the
  // panes are stacked (a narrow window) the claims are not a pane of their own: the page scrolls instead.
  function reveal(pane, el) {
    const smooth = matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    if (pane.scrollHeight <= pane.clientHeight + 1 || !/(auto|scroll)/.test(getComputedStyle(pane).overflowY)) {
      el.scrollIntoView({ block: "center", behavior: smooth });
      return;
    }
    const pr = pane.getBoundingClientRect(), er = el.getBoundingClientRect();
    const top = pane.scrollTop + (er.top - pr.top) - Math.max(12, (pane.clientHeight - er.height) / 2);
    pane.scrollTo({ top: Math.max(0, top), behavior: smooth });
    if (pr.top < 0 || pr.bottom > innerHeight) pane.scrollIntoView({ block: "nearest", behavior: smooth });
  }

  // A click anywhere on a card (not on its buttons, links or a text being selected) shows its sentence in the draft.
  function clickToShow(card, c) {
    card.addEventListener("click", (e) => {
      if (e.target.closest("button, a, input, textarea, select, label, summary")) return;
      const sel = document.getSelection();
      if (sel && !sel.isCollapsed && card.contains(sel.anchorNode)) return;
      pick(c.claim_id, "text");
    });
    return card;
  }

  const differs = (c) => norm(c.claim) !== norm(c.quote);
  const norm = (s) => (s || "").replace(/\s+/g, " ").replace(/\s*[([]\w[^)\]]*[)\]]/g, "").trim().toLowerCase();

  // The APA 7 in-text citation of a document (or of several, `all`) on a button that copies it; Alt-click copies the
  // narrative form, "Verhoeven and Okafor (2025)".
  function apaButton(cite, opts = {}) {
    const narrative = !opts.all && cite.narrative;
    const btn = button({ kind: "quiet", sm: true, wrap: true, icon: "copy", class: `dc-apa${opts.all ? " dc-apa-all" : ""}`,
      title: `Copy ${cite.text} to paste into your text${narrative ? `. ${ALT_CLICK}: ${cite.narrative}` : ""}`,
      "aria-label": `Copy the APA citation ${cite.text}` }, h("span", { class: "dc-apa-text" }, cite.text));
    btn.addEventListener("click", async (e) => {
      const alt = e.altKey && narrative;
      const text = alt ? cite.narrative : cite.text, html = alt ? cite.narrative_html : cite.html;
      if (await copyCitation(text, html)) toast(`Copied ${text}. Paste it into your text.`, "ok", { ttl: 2500 });
      else toast("Could not copy: select the citation and copy it with Ctrl+C (or Cmd+C).", "warn");
    });
    return btn;
  }

  // Documents of the side that are not linked to a work of the bibliography have no citation to copy.
  function notLinked(n, total) {
    if (!n || !data.bibliography) return null;
    return h("p", { class: "dc-cite-line dc-cite-docs muted" }, n === total ? `${n === 1 ? "This document is" : "These documents are"} not linked to a work of your bibliography, so there is no citation to copy. `
      : `${plural(n, "document is", "documents are")} not linked to a work of your bibliography. `, link({ href: "#/bibliography" }, "Bibliography"));
  }

  function claimCard(c) {
    const st = statusOf(c);
    const el = makeCard({ as: "article", sm: true, class: `dc-card dc-${st}${c.decision ? ` dc-you-${c.decision}` : ""}${picked === c.claim_id ? " dc-picked" : ""}`, "data-id": c.claim_id },
      h("div", { class: "dc-head" },
        h("button", { class: `dc-n dm-${st}`, type: "button", title: "Show it in the draft", "aria-label": `Show claim ${c.n} in the draft`, onClick: () => pick(c.claim_id, "text") }, String(c.n)),
        h("span", { class: "dc-kind" }, c.kind_text),
        c.cited ? tag({ icon: "quote", title: "Your draft already gives a source for this" }, "cited in your draft") : null,
        c.source !== "ai" ? tag({}, c.source === "person" ? "marked by you" : "found by rules") : null,
        h("span", { class: "grow" }),
        c.status ? statusBadge(c.status, { short: true }) : h("span", { class: "muted small" }, c.skip ? "Dismissed" : "Not checked yet")),
      h("p", { class: "dc-claim" }, c.claim),
      differs(c) ? h("p", { class: "dc-quote muted small" }, "In your draft: ", h("q", {}, c.quote.replace(/\s+/g, " "))) : null,
      selfLine(c),
      c.status ? evidence(c) : c.why && !c.skip ? h("p", { class: "muted small dc-why" }, c.why) : null,
      citeBlock(c),
      h("div", { class: "dc-foot" }, decide(c), actions(c)));
    return clickToShow(el, c);
  }

  // A claim decided on: folded to its number, the decision, the claim and what to cite (Margin 0.3).
  function foldedCard(c) {
    const st = statusOf(c), you = DECIDE[c.decision];
    const docs = you.side ? ((c.evidence || {})[you.side] || []) : [];
    const all = you.side ? (c.cite || {})[you.side] : null;  // the documents to cite, in one APA citation
    const copyAll = all ? apaButton(all, { all: true }) : null;
    const own = citesOf(c);
    const cite = !you.side ? null
      : own.length ? h("p", { class: "dc-cite small dc-cite-own" }, icon("quote", { size: 12 }), "Your draft cites ",
        ...own.flatMap((r, i) => [i ? h("span", { class: "muted" }, " · ") : null, h("span", { class: "dc-cite-name" }, citeName(r)), " ", citeBadge(r)].filter(Boolean)))
      : c.cited ? h("p", { class: "dc-cite small" }, icon("quote", { size: 12 }), "Your draft cites a source here.", copyAll)
      : h("div", { class: "dc-cite small" }, docs.length
        ? [copyAll ? h("p", { class: "dc-cite-line" }, icon("quote", { size: 12 }), h("span", {}, "Cite: "), copyAll) : null,
          h("p", { class: `dc-cite-line${copyAll ? " dc-cite-docs" : ""}` }, copyAll ? null : icon("quote", { size: 12 }), copyAll ? null : h("span", {}, "Cite: "),
            ...docs.slice(0, 3).flatMap((e, i) => [i ? h("span", { class: "muted" }, " · ") : null, link({ kind: "title", serif: true, href: `#/doc/${encodeURIComponent(e.doc_id)}`, class: "dc-doc" }, e.title)].filter(Boolean)),
            docs.length > 3 ? h("span", { class: "muted" }, ` and ${docs.length - 3} more`) : null),
          notLinked(all ? all.missing : data.bibliography ? docs.length : 0, docs.length)].filter(Boolean)
        : h("p", { class: "dc-cite-line" }, icon("quote", { size: 12 }), you.none));
    const el = makeCard({ as: "article", sm: true, class: `dc-card dc-folded dc-${st} dc-you-${c.decision}${picked === c.claim_id ? " dc-picked" : ""}`, "data-id": c.claim_id },
      h("div", { class: "dc-head" },
        h("button", { class: `dc-n dm-${st} dm-you-${c.decision}`, type: "button", title: "Show it in the draft", "aria-label": `Show claim ${c.n} in the draft`, onClick: () => pick(c.claim_id, "text") }, String(c.n)),
        tag({ icon: "user" }, you.short),
        c.status && c.decision !== "dismissed" ? h("span", { class: "muted small dc-ai" }, `AI: ${(c.status_text || App.statusText(c.status) || "").toLowerCase()}`) : null,
        h("span", { class: "grow" }),
        button({ kind: "quiet", sm: true, toggle: true, title: "Show the whole card", onClick: () => { unfolded.add(c.claim_id); drawList(numbered()); } }, "More"),
        button({ kind: "quiet", sm: true, title: "Take the decision back", onClick: () => decideClaim(c, null) }, "Undo")),
      h("p", { class: "dc-claim" }, c.claim),
      cite);
    return clickToShow(el, c);
  }

  // What the claim's own citations say (step 3): for each cited work, whether its source says it, and the way on.
  function citeBadge(r) {
    return r.status ? h("span", { class: `dc-cite-badge dcit-badge-${citeLook(r.group)}` }, statusBadge(r.status, { text: r.text }))
      : tag({ class: `dcit-badge-${citeLook(r.group)}` }, r.text);
  }

  function citeBlock(c) {
    const own = citesOf(c);
    if (!own.length) return null;
    const tid = data.citations.text_id;
    const running = watchers.length > 0;
    return h("div", { class: "dc-cites" },
      h("div", { class: "dc-side-label" }, icon("quote", { size: 13 }), own.length === 1 ? "Your citation" : "Your citations",
        h("span", { class: "muted dc-cites-sub" }, "· does the source you cite say it?")),
      h("ul", { class: "dc-cite-list" }, own.map((r) => h("li", { class: `dc-cite-item dcit-item-${citeLook(r.group)}` },
        h("div", { class: "dc-cite-row" },
          h("span", { class: "dc-cite-name", title: r.raw }, citeName(r)), citeBadge(r),
          r.help && CITE_NOTICES.includes(r.group) ? h("p", { class: "muted small dc-cite-help" }, r.help) : null),
        r.quote && r.group !== "accurate" ? h("blockquote", { class: "dc-q" }, r.quote) : null,
        h("div", { class: "dc-cite-actions small" },
          r.hyp_id ? link({ href: `#/h/${encodeURIComponent(r.hyp_id)}` }, CITE_NOTICES.includes(r.group) ? "See the excerpts and judge them" : "See the excerpts")
            : r.state === "ready" ? withAIFor(data.draft.ai_access, button({ kind: "quiet", sm: true, icon: "play", disabled: running, onClick: () => startCitations({ ref_ids: [r.ref_id] }) }, "Check this citation"))
            : link({ href: `#/citations/${encodeURIComponent(tid)}?ref=${encodeURIComponent(r.ref_id)}` }, "What it needs"))))));
  }

  // The person's decision: one switch of three; the one chosen is pressed, and pressing it again takes it back.
  function decide(c) {
    return h("div", { class: "dc-decide" },
      h("span", { class: "dc-decide-label muted small", "aria-hidden": "true" }, "Your verdict"),
      pickOne({ filter: true, sm: true, label: `Your verdict on claim ${c.n}`, value: c.decision || null,
        options: Object.entries(DECIDE).map(([k, d]) => [k, d.seg, undefined,
          `${d.label}${d.title ? `: ${d.title.toLowerCase()}` : ""}${c.decision === k ? " (press again to take it back)" : ""}`]),
        onPick: (k) => decideClaim(c, c.decision === k ? null : k) }));
  }

  async function decideClaim(c, decision) {
    unfolded.delete(c.claim_id);
    picked = c.claim_id;
    await setClaim(c, { decision });
  }

  function evidence(c) {
    const ev = c.evidence || {};
    const sides = SIDES.filter(([k]) => (ev[k] || []).length).map(([k, label, ic, cls]) => h("div", { class: `dc-side dc-side-${cls}` },
      h("div", { class: "dc-side-label" }, judgementIcon(ic, 13), label),
      h("ul", { class: "dc-docs" }, ev[k].map((e) => h("li", {},
        link({ kind: "title", serif: true, href: `#/doc/${encodeURIComponent(e.doc_id)}`, class: "dc-doc" }, e.title),
        e.apa ? apaButton(e.apa) : null,
        e.location ? h("span", { class: "muted small" }, ` · ${e.location}`) : null,
        e.excerpts > 1 ? h("span", { class: "muted small" }, ` · ${e.excerpts} excerpts`) : null,
        e.quote ? h("blockquote", { class: "dc-q" }, e.quote) : null)))));
    const advice = ADVICE[c.status] || "";
    return h("div", { class: "dc-evidence" }, sides,
      advice ? h("p", { class: "dc-advice small" }, advice) : null,
      c.waiting_for_you ? h("p", { class: "small dc-advice" }, workState("attention", `${plural(c.waiting_for_you, "excerpt waits", "excerpts wait")} for your judgement on the result page.`)) : null);
  }

  // Margin: a claim no document supports can be taken to Find literature (a draft kept on this computer cannot send its
  // words, so the link opens the page without them: the person types their own)
  function literatureLink(c) {
    if (c.skip || c.decision === "dismissed" || !["unsupported", "no_passages", "uncertain"].includes(c.status)) return null;
    const ok = data.draft.ai_access === "cloud";
    return link({ class: "it", href: ok ? `#/literature?draft=${encodeURIComponent(draftId)}&claim=${encodeURIComponent(c.claim_id)}` : "#/literature",
      title: ok ? "Search OpenAlex for works to cite. You see and edit the search words before anything is sent." : "This draft's AI setting keeps its words on this computer, so the search starts without them." }, icon("search", { size: 13 }), "Find literature");
  }

  // The card's ways on, as quiet links under the verdict: the result and Find literature (or Check this one and Reword
  // for a claim not checked yet), then Fold and Remove at the far end.
  function actions(c) {
    const row = h("div", { class: "dc-actions" });
    if (c.hyp_id) {
      const lit = literatureLink(c);
      if (lit) row.append(lit);
      row.append(link({ href: `#/h/${encodeURIComponent(c.hyp_id)}` }, "Open the result"));
    } else if (!c.skip) {
      const docs = data.documents || 0;
      row.append(...withAIFor(data.draft.ai_access, button({ sm: true, icon: "play", disabled: watchers.length > 0 || !docs, onClick: () => startJob("check", { claim_ids: [c.claim_id] }) }, "Check this one")));
      row.append(button({ kind: "quiet", sm: true, icon: "file-pen", onClick: () => reword(c, row) }, "Reword"));
    }
    const end = [
      c.decision ? button({ kind: "quiet", sm: true, icon: "chevron-up", "aria-expanded": "true", title: "Fold the card again", onClick: () => { unfolded.delete(c.claim_id); drawList(numbered()); } }, "Fold") : null,
      c.hyp_id || c.source === "person" ? button({ kind: "danger", sm: true, icon: "trash", title: "Remove this claim", onClick: () => removeClaim(c) }, "Remove") : null,
    ].filter(Boolean);
    if (end.length) row.append(h("span", { class: "dc-actions-end" }, end));
    return row.childNodes.length ? row : null;
  }

  function reword(c, row) {
    const ta = textareaEl({ class: "dc-edit", rows: 3, "aria-label": `New wording of claim ${c.n}` });
    ta.value = c.claim;
    const save = button({ kind: "main", sm: true }, "Save");
    const cancel = button({ kind: "quiet", sm: true, onClick: () => drawBoard() }, "Cancel");
    save.addEventListener("click", () => setClaim(c, { claim: ta.value }));
    replace(row, h("div", { class: "stack dc-reword" },
      h("p", { class: "muted small" }, "Write it as one sentence a source could support or contradict: what is checked is this wording, not your draft's."),
      ta, h("div", { class: "btn-row" }, save, cancel)));
    ta.focus();
  }

  async function setClaim(c, body) {
    try { await api("PUT", `${base}/claims/${P(c.claim_id)}`, body); await reload(); } catch (e) { showError(e); }
  }

  async function removeClaim(c) {
    if (c.hyp_id && !(await confirmDialog({ title: "Remove this claim?", message: "The claim and its check (under Results) are removed. You can mark the sentence again later.", confirmText: "Remove" }))) return;
    try { await api("DELETE", `${base}/claims/${P(c.claim_id)}`); await reload(); } catch (e) { showError(e); }
  }

  // --- marking a sentence as a claim (select it in the draft)
  function selectionOffsets() {
    const sel = document.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    const r = sel.getRangeAt(0);
    if (!textBox.contains(r.startContainer) || !textBox.contains(r.endContainer)) return null;
    const pre = document.createRange();
    pre.setStart(textBox, 0);
    pre.setEnd(r.startContainer, r.startOffset);
    const start = pre.toString().length;
    const end = start + r.toString().length;
    if (end - start < 10) return null;
    return { start, end, rect: r.getBoundingClientRect() };
  }
  function onSelection() {
    const o = selectionOffsets();
    if (!o) { markBtn.hidden = true; return; }
    const box = textWrap.getBoundingClientRect();
    markBtn.hidden = false;
    markBtn.style.top = `${Math.max(0, o.rect.bottom - box.top + 6)}px`;
    markBtn.style.left = `${Math.min(Math.max(0, o.rect.left - box.left), Math.max(0, box.width - 170))}px`;
    markBtn.dataset.start = String(o.start);
    markBtn.dataset.end = String(o.end);
  }
  let selTimer = null;
  const selListener = () => { clearTimeout(selTimer); selTimer = setTimeout(onSelection, 120); };
  document.addEventListener("selectionchange", selListener);
  markBtn.addEventListener("mousedown", (e) => e.preventDefault());  // keep the selection while the button is pressed
  markBtn.addEventListener("click", async () => {
    const start = Number(markBtn.dataset.start), end = Number(markBtn.dataset.end);
    markBtn.hidden = true;
    try {
      const r = await api("POST", `${base}/claims`, { start, end });
      document.getSelection().removeAllRanges();
      await reload();
      pick(r.claim_id, "card");
      toast("Marked as a claim. Check it, or reword it first.", "ok", { ttl: 2500 });
    } catch (e) { showError(e); }
  });

  drawAll();
  loadSelf();

  // a job of this draft that is running (or the one this page was opened with)
  const active = query.job ? await api("GET", `/api/jobs/${P(query.job)}`).catch(() => null) : null;
  const citeText = data.citations && data.citations.text_id;
  const running = active && !TERMINAL.has(active.state) ? active
    : await runningJob(project, ["draft-find", "draft-check", "citations"], (j) => j.scope === draftId || (!!citeText && j.scope === citeText));
  if (running && alive) follow(running);

  return () => {
    alive = false;
    for (const w of watchers) w.stop();
    clearInterval(refreshTimer);
    document.removeEventListener("selectionchange", selListener);
    if (window.CSS && CSS.highlights) CSS.highlights.delete("draft-self");
  };
}

// Copy a citation. Plain text, which takes the font of the text it is pasted into; also as HTML only when it has a
// title in italics (a book or report without an author), so the italics come along.
async function copyCitation(text, html) {
  try {
    if (html && html.includes("<i>") && window.ClipboardItem && navigator.clipboard.write) {
      await navigator.clipboard.write([new ClipboardItem({ "text/plain": new Blob([text], { type: "text/plain" }), "text/html": new Blob([html], { type: "text/html" }) })]);
    } else await navigator.clipboard.writeText(text);
    return true;
  } catch (_) {
    const ta = h("textarea", { class: "visually-hidden", "aria-hidden": "true" });
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
    ta.remove();
    return ok;
  }
}
