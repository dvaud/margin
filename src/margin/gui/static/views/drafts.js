// Margin 0.1: check a draft. The researcher's own writing, with the statements that need a source marked in it, and
// for each the documents of the project that support or contradict it. Two steps: find the claims (the AI, or rules
// without AI; the person keeps, drops, rewords and adds claims by selecting a sentence), then check them against
// the documents (each claim is a hypothesis of its own, with its full result page).
// Margin 0.3: the person decides on each claim (supported, refuted, dismissed): its card folds to what matters and its
// highlight in the draft says a source should be cited there; the claims scroll on their own beside the draft, and a
// click anywhere on a card shows its sentence in the draft.
import { featureEyebrow } from "../features.js";
import { App, api, h, icon, replace, clear, toast, showError, fmt, pageHead, watchJob, P, emptyState, statusBadge, confirmDialog, dialog, download, TERMINAL, runningJob, plural, session, queueNotice, navigate } from "../lib.js";
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
const SIDES = [["supports", "Supports it", "circle-check", "ok"], ["partly", "Partly supports it", "circle-half", "partly"], ["refutes", "Contradicts it", "circle-x", "bad"]];
const FILTERS = [["all", "All"], ["open", "To decide"], ["you_supported", "You: supported"], ["you_refuted", "You: refuted"], ["unchecked", "Not checked"], ["supported", "Supported"], ["partially_supported", "Partly supported"], ["contested", "Mixed evidence"], ["contradicted", "Contradicted"], ["unsupported", "No evidence"], ["no_passages", "Nothing matched"], ["uncertain", "Uncertain"], ["waiting", "Waiting"], ["skip", "Dismissed"]];
// the person's decisions on a claim (Margin 0.3); `side` is the evidence the folded card names as what to cite
const DECIDE = {
  supported: { label: "Claim supported", short: "You: supported", icon: "circle-check", side: "supports", cite: "Cite a source here", none: "Cite the source that supports it here." },
  refuted: { label: "Claim refuted", short: "You: refuted", icon: "circle-x", side: "refutes", cite: "Cite or revise here", none: "Cite the source that contradicts it, or revise the sentence." },
  dismissed: { label: "Dismiss claim", short: "Dismissed", icon: "x", title: "Not a claim that needs a source" },
};

const statusOf = (c) => (c.skip ? "skip" : c.status || "unchecked");
const decided = (c) => c.decision === "supported" || c.decision === "refuted";
const matches = (c, k) => (k === "all" ? true : k === "open" ? !c.decision : k === "you_supported" ? c.decision === "supported"
  : k === "you_refuted" ? c.decision === "refuted" : statusOf(c) === k);

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
  view.appendChild(h("ol", { class: "draft-steps-intro" },
    h("li", {}, h("strong", {}, "Find the claims. "), "Numbers, causes and effects, comparisons, what research found: each marked in your text, with the exact sentence."),
    h("li", {}, h("strong", {}, "Keep the ones you want checked. "), "Drop, reword, or select a sentence to add one."),
    h("li", {}, h("strong", {}, "Check them. "), "Each gets the documents that support or contradict it, with quotes checked against the source.")));

  let level = res.default && levels().includes(res.default) ? res.default : levels()[0];
  const choice = accessChoice({ value: level, name: "draft-access", many: false, onChange: (v) => { level = v; } });
  choice.querySelector("legend").textContent = "Who may read this draft with AI?";
  for (const lv of levels()) { const el = choice.querySelector(`.access-${lv} .muted`); if (el) el.textContent = SUB[lv]; }

  const title = h("input", { class: "input", id: "draft-title", placeholder: "For example: Chapter 2, literature review", maxlength: 200 });
  const ta = h("textarea", { class: "textarea draft-input", id: "draft-text", rows: 10, placeholder: "Paste a section, a chapter or the whole paper…" });
  ta.value = session("draftText") || "";
  ta.addEventListener("input", () => { session("draftText", ta.value); goBtn.disabled = ta.value.trim().length < 40; });
  const goBtn = h("button", { class: "btn btn-primary", type: "button", disabled: ta.value.trim().length < 40 }, icon("sparkles", { size: 14 }), "Find the claims");
  const fileInput = h("input", { type: "file", accept: ".docx,.pdf,.txt,.md,.html,.htm", class: "visually-hidden", id: "draft-file" });
  const fileBtn = h("label", { class: "btn", for: "draft-file", tabindex: "0", onKeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } } }, icon("upload", { size: 14 }), "Load a file", fileInput);
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

  view.appendChild(h("section", { class: "card draft-new", "aria-label": "A new draft" },
    h("div", { class: "card-head" }, h("h2", {}, "A new draft")),
    h("div", { class: "field" }, h("label", { class: "field-label", for: "draft-title" }, "Title ", h("span", { class: "muted small" }, "(optional)")), title),
    h("div", { class: "field" }, h("label", { class: "field-label", for: "draft-text" }, "Your text"), ta,
      h("div", { class: "hint-row" }, h("span", {}, "Or load a Word file, a PDF, a text or Markdown file. Your draft is kept apart from the documents: it is never used as evidence."))),
    choice,
    h("div", { class: "btn-row", style: { marginTop: "14px" } }, goBtn, fileBtn, status)));

  const list = res.drafts || [];
  view.appendChild(h("section", { class: "section", "aria-label": "Your drafts" },
    h("div", { class: "section-title" }, h("h2", {}, "Your drafts"), h("span", { class: "muted" }, list.length ? plural(list.length, "draft", "drafts") : "none yet")),
    list.length ? h("ul", { class: "draft-list" }, list.map((d) => h("li", {},
      h("a", { class: "draft-row", href: `#/drafts/${encodeURIComponent(d.draft_id)}` },
        icon("file-pen", { size: 16 }),
        h("span", { class: "grow" }, h("span", { class: "draft-row-title" }, d.title),
          h("span", { class: "muted small" }, [fmt.dateShort(d.created_at), d.file_name, `${fmt.num(Math.round(d.chars / 6))} words`].filter(Boolean).join(" · "))),
        h("span", { class: "muted small draft-row-counts" }, d.claims ? `${plural(d.claims, "claim", "claims")} · ${d.checked} checked` : d.found_at ? "no claims found" : "not read yet"),
        accessBadge(d.ai_access)))))
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
    if (e.status === 404) { view.appendChild(emptyState("search-x", "This draft no longer exists", "It was removed, or it belongs to another project.", h("a", { class: "btn", href: "#/drafts" }, "All drafts"))); return; }
    throw e;
  }
  let filter = "all";
  let picked = null;
  const unfolded = new Set();  // decided claims shown in full for now
  let watchers = [];
  let refreshTimer = null;
  let alive = true;

  const head = h("div");
  const setting = h("div", { class: "draft-setting" });
  const steps = h("section", { class: "card draft-steps", "aria-label": "Steps" });
  const stepsBody = h("div");
  const jobBox = h("div", { class: "draft-job", hidden: true });
  steps.append(stepsBody, jobBox);
  const chips = h("div", { class: "draft-filter", role: "toolbar", "aria-label": "Show claims" });
  const textBox = h("div", { class: "draft-text", id: "draft-text-view" });
  const markBtn = h("button", { class: "btn btn-sm btn-primary draft-mark-btn", type: "button", hidden: true }, icon("plus", { size: 13 }), "Mark as a claim");
  const textWrap = h("div", { class: "draft-text-wrap" }, textBox, markBtn);
  const list = h("div", { class: "draft-claims" });
  const board = h("div", { class: "draft-board" },
    h("section", { class: "draft-col draft-col-text", "aria-label": "Your draft" },
      h("div", { class: "section-title" }, h("h2", {}, "Your draft"), h("span", { class: "muted" }, "select a sentence to mark it as a claim")), textWrap),
    h("section", { class: "draft-col draft-col-claims", "aria-label": "Claims" },
      h("div", { class: "section-title" }, h("h2", {}, "Claims"), h("span", { class: "muted draft-claims-count" })), chips, list));
  view.append(head, setting, steps, board);

  async function reload() {
    try { data = await api("GET", base); } catch (e) { if (e.status !== 404) showError(e); return; }
    if (!alive) return;
    drawAll();
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
    const xlsx = h("button", { class: "btn btn-sm", type: "button", disabled: !data.claims.length, onClick: () => download(`${base}/export.xlsx`).catch(showError) }, icon("download", { size: 14 }), "Excel");
    const csv = h("button", { class: "btn btn-sm btn-ghost", type: "button", disabled: !data.claims.length, onClick: () => download(`${base}/export.csv`).catch(showError) }, "CSV");
    const rename = h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: renameDialog }, "Rename");
    const del = h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: removeDraft }, icon("trash", { size: 14 }), "Remove");
    replace(head, pageHead(d.title, {
      eyebrow: h("a", { href: "#/drafts", class: "it" }, icon("arrow-left", { size: 12 }), "All drafts"),
      sub: [`${fmt.num(d.words)} words`, `added ${fmt.dateShort(d.created_at)}`, d.file_name ? `from ${d.file_name}` : null].filter(Boolean).join(" · "),
      actions: [xlsx, csv, rename, del],
    }));
  }

  async function renameDialog() {
    const input = h("input", { class: "input", value: data.draft.title, maxlength: 200, "aria-label": "Title" });
    const t = await dialog({
      title: "Rename the draft", body: h("label", { class: "field" }, h("span", { class: "field-label" }, "Title"), input),
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
    const sel = h("select", { class: "select select-sm access-select", "aria-label": "Who may read this draft with AI", "data-level": d.ai_access },
      levels().map((lv) => h("option", { value: lv, selected: d.ai_access === lv }, LEVEL[lv].title)));
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
    const findBtn = h("button", { class: `btn ${d.found_at || c.claims ? "btn-sm btn-ghost" : "btn-primary"}`, type: "button", disabled: running }, icon(d.found_at ? "refresh" : "sparkles", { size: 14 }), d.found_at ? "Find again" : "Find the claims");
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
        f.failed ? h("details", { class: "fold small" }, h("summary", {}, `${plural(f.failed, "part", "parts")} of the draft could not be read; find again to try once more`),
          h("ul", { class: "mono small" }, (f.errors || []).map((e) => h("li", {}, e)))) : null),
      findBtn);
    const docs = data.documents || 0;
    const checkBtn = h("button", { class: "btn btn-primary", type: "button", disabled: running || !c.to_check || !docs }, icon("play", { size: 14 }), c.to_check ? `Check ${c.to_check === 1 ? "this claim" : `${c.to_check} claims`}` : "Check the claims");
    checkBtn.addEventListener("click", () => startJob("check", {}));
    const step2 = h("div", { class: "draft-step" },
      h("span", { class: `draft-step-n ${c.checked && !c.to_check ? "done" : ""}` }, c.checked && !c.to_check ? icon("check", { size: 14 }) : "2"),
      h("div", { class: "grow" },
        h("h3", {}, "Check them against your documents"),
        h("p", { class: "muted small" }, !docs ? h("span", {}, "This project has no documents yet. ", h("a", { href: "#/sources" }, "Add the documents your draft draws on"), ", then check the claims.")
          : !c.claims ? "Find the claims first, or select a sentence in your draft to mark one."
          : c.to_check ? `${plural(c.to_check, "claim waits", "claims wait")} to be checked; ${c.checked} checked so far. Each is checked like a hypothesis, against all ${plural(docs, "document", "documents")}.`
          : doneText(c))),
      c.to_check || !c.checked ? checkBtn : null);
    replace(stepsBody, step1, step2);
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
        else toast(`Checked ${plural((r.checked || []).length, "claim", "claims")}${(r.errors || []).length ? `; ${r.errors.length} could not be checked` : ""}.`, (r.errors || []).length ? "warn" : "ok");
        jobBox.hidden = true;
      }
    };
    let watcher;
    if (job.kind === "draft-find") {
      watcher = jobCard(jobBox, job.id, "Finding the claims", (p, j) => (p.total ? `${p.message || "Reading your draft"} (${Math.min(p.done + 1, p.total)} of ${p.total})` : p.message || (j.queue ? "Waiting for Claude Code" : "Reading your draft…")), done, { small: true, plain: true, stoppedText: "Stopped. The claims found so far are kept." });
    } else {
      const panel = new ProgressPanel({ title: "Checking the claims", batchWords: { doing: "checking claim", done: "claims checked" } });
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

  function drawText(claims) {
    clear(textBox);
    const text = data.text;
    let pos = 0;
    for (const c of claims) {
      const s = Math.max(c.start, pos);
      if (s >= c.end) continue;
      if (s > pos) textBox.append(document.createTextNode(text.slice(pos, s)));
      const st = statusOf(c);
      const you = decided(c) ? DECIDE[c.decision] : null;
      const cite = you ? (c.cited ? "cited" : "cite here") : null;
      const said = st === "unchecked" ? "not checked yet" : st === "skip" ? "dismissed" : App.statusText(st) || st;
      const m = h("mark", { class: `dm dm-${st}${you ? ` dm-you dm-you-${c.decision}` : ""}${picked === c.claim_id ? " dm-picked" : ""}`, "data-n": String(c.n), "data-id": c.claim_id, "data-cite": cite, tabindex: "0", role: "button",
        "aria-label": you ? `Claim ${c.n}: ${c.decision === "supported" ? "you marked it supported" : "you marked it refuted"}; ${c.cited ? "your draft cites a source here" : "a source should be cited here"}` : `Claim ${c.n}: ${said}`,
        title: you ? `Claim ${c.n}: ${c.cited ? "your draft cites a source here" : you.cite.toLowerCase()}` : `Claim ${c.n}` }, text.slice(s, c.end));
      m.addEventListener("click", () => pick(c.claim_id, "card"));
      m.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(c.claim_id, "card"); } });
      textBox.append(m);
      pos = c.end;
    }
    if (pos < text.length) textBox.append(document.createTextNode(text.slice(pos)));
  }

  function drawChips(claims) {
    const count = (k) => claims.filter((c) => matches(c, k)).length;
    clear(chips);
    for (const [k, label] of FILTERS) {
      const n = count(k);
      if (k !== "all" && !n) continue;
      if (k === "open" && n === claims.length) continue;  // nothing decided yet: the same as All
      chips.appendChild(h("button", { class: `chip-btn draft-chip dm-chip-${k}`, type: "button", "aria-pressed": String(filter === k), onClick: () => { filter = k; drawBoard(); } }, `${label} `, h("span", { class: "count" }, String(n))));
    }
    if (filter !== "all" && !count(filter)) filter = "all";
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

  function claimCard(c) {
    const st = statusOf(c);
    const card = h("article", { class: `dc-card dc-${st}${c.decision ? ` dc-you-${c.decision}` : ""}${picked === c.claim_id ? " dc-picked" : ""}`, "data-id": c.claim_id },
      h("div", { class: "dc-head" },
        h("button", { class: `dc-n dm-${st}`, type: "button", title: "Show it in the draft", "aria-label": `Show claim ${c.n} in the draft`, onClick: () => pick(c.claim_id, "text") }, String(c.n)),
        h("span", { class: "dc-kind" }, c.kind_text),
        c.cited ? h("span", { class: "chip dc-chip", title: "Your draft already gives a source for this" }, icon("quote", { size: 11 }), "cited in your draft") : null,
        c.source !== "ai" ? h("span", { class: "chip dc-chip" }, c.source === "person" ? "marked by you" : "found by rules") : null,
        h("span", { class: "grow" }),
        c.status ? statusBadge(c.status, { short: true }) : h("span", { class: "muted small" }, c.skip ? "Dismissed" : "Not checked yet")),
      h("p", { class: "dc-claim" }, c.claim),
      differs(c) ? h("p", { class: "dc-quote muted small" }, "In your draft: ", h("q", {}, c.quote.replace(/\s+/g, " "))) : null,
      c.status ? evidence(c) : c.why && !c.skip ? h("p", { class: "muted small dc-why" }, c.why) : null,
      decide(c),
      foot(c));
    return clickToShow(card, c);
  }

  // A claim decided on: folded to its number, the decision, the claim and what to cite (Margin 0.3).
  function foldedCard(c) {
    const st = statusOf(c), you = DECIDE[c.decision];
    const docs = you.side ? ((c.evidence || {})[you.side] || []) : [];
    const cite = !you.side ? null
      : c.cited ? h("p", { class: "dc-cite small" }, icon("quote", { size: 12 }), "Your draft cites a source here.")
      : h("p", { class: "dc-cite small" }, icon("quote", { size: 12 }), docs.length
        ? [h("span", {}, "Cite: "), ...docs.slice(0, 3).flatMap((e, i) => [i ? h("span", { class: "muted" }, " · ") : null, h("a", { href: `#/doc/${encodeURIComponent(e.doc_id)}`, class: "dc-doc" }, e.title)].filter(Boolean)),
          docs.length > 3 ? h("span", { class: "muted" }, ` and ${docs.length - 3} more`) : null].filter(Boolean)
        : you.none);
    const card = h("article", { class: `dc-card dc-folded dc-${st} dc-you-${c.decision}${picked === c.claim_id ? " dc-picked" : ""}`, "data-id": c.claim_id },
      h("div", { class: "dc-head" },
        h("button", { class: `dc-n dm-${st} dm-you-${c.decision}`, type: "button", title: "Show it in the draft", "aria-label": `Show claim ${c.n} in the draft`, onClick: () => pick(c.claim_id, "text") }, String(c.n)),
        h("span", { class: `dc-you dc-you-badge-${c.decision}` }, icon(you.icon, { size: 13 }), you.short),
        c.status && c.decision !== "dismissed" ? h("span", { class: "muted small dc-ai" }, `AI: ${(c.status_text || App.statusText(c.status) || "").toLowerCase()}`) : null,
        h("span", { class: "grow" }),
        h("button", { class: "btn btn-sm btn-ghost", type: "button", "aria-expanded": "false", title: "Show the whole card", onClick: () => { unfolded.add(c.claim_id); drawList(numbered()); } }, icon("chevron-down", { size: 13 }), "More"),
        h("button", { class: "btn btn-sm btn-ghost", type: "button", title: "Take the decision back", onClick: () => decideClaim(c, null) }, "Undo")),
      h("p", { class: "dc-claim" }, c.claim),
      cite);
    return clickToShow(card, c);
  }

  // The person's decision: three buttons; the one chosen is pressed, and pressing it again takes it back.
  function decide(c) {
    const row = h("div", { class: "dc-decide", role: "group", "aria-label": `Your decision on claim ${c.n}` },
      Object.entries(DECIDE).map(([k, d]) => h("button", { class: `btn btn-sm dc-decide-btn dc-decide-${k}`, type: "button", "aria-pressed": String(c.decision === k), title: d.title || null,
        onClick: () => decideClaim(c, c.decision === k ? null : k) }, icon(d.icon, { size: 13 }), d.label)));
    return row;
  }

  async function decideClaim(c, decision) {
    unfolded.delete(c.claim_id);
    picked = c.claim_id;
    await setClaim(c, { decision });
  }

  function evidence(c) {
    const ev = c.evidence || {};
    const sides = SIDES.filter(([k]) => (ev[k] || []).length).map(([k, label, ic, cls]) => h("div", { class: `dc-side dc-side-${cls}` },
      h("div", { class: "dc-side-label" }, icon(ic, { size: 13 }), label),
      h("ul", { class: "dc-docs" }, ev[k].map((e) => h("li", {},
        h("a", { href: `#/doc/${encodeURIComponent(e.doc_id)}`, class: "dc-doc" }, e.title),
        e.location ? h("span", { class: "muted small" }, ` · ${e.location}`) : null,
        e.excerpts > 1 ? h("span", { class: "muted small" }, ` · ${e.excerpts} excerpts`) : null,
        e.quote ? h("blockquote", { class: "dc-q" }, e.quote) : null)))));
    const advice = ADVICE[c.status] || "";
    return h("div", { class: "dc-evidence" }, sides,
      advice ? h("p", { class: "dc-advice small" }, advice) : null,
      c.waiting_for_you ? h("p", { class: "small dc-advice" }, icon("alert-circle", { size: 12 }), ` ${plural(c.waiting_for_you, "excerpt waits", "excerpts wait")} for your judgement on the result page.`) : null);
  }

  // the card's own buttons, and Fold at the end for a claim decided on
  function foot(c) {
    const row = actions(c) || (c.decision ? h("div", { class: "dc-actions" }) : null);
    if (c.decision) row.append(h("button", { class: "btn btn-sm btn-ghost dc-fold", type: "button", "aria-expanded": "true", title: "Fold the card again", onClick: () => { unfolded.delete(c.claim_id); drawList(numbered()); } }, icon("chevron-up", { size: 13 }), "Fold"));
    return row;
  }

  function actions(c) {
    const row = h("div", { class: "dc-actions" });
    if (c.hyp_id) {
      row.append(h("a", { class: "btn btn-sm", href: `#/h/${encodeURIComponent(c.hyp_id)}` }, "Open the result", icon("arrow-right", { size: 13 })));
      row.append(h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: () => removeClaim(c) }, "Remove"));
      return row;
    }
    if (c.skip) return c.source === "person" ? (row.append(h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: () => removeClaim(c) }, "Remove")), row) : null;
    const docs = data.documents || 0;
    row.append(h("button", { class: "btn btn-sm", type: "button", disabled: watchers.length > 0 || !docs, onClick: () => startJob("check", { claim_ids: [c.claim_id] }) }, icon("play", { size: 13 }), "Check this one"));
    row.append(h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: () => reword(c, row) }, "Reword"));
    if (c.source === "person") row.append(h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: () => removeClaim(c) }, "Remove"));
    return row;
  }

  function reword(c, row) {
    const ta = h("textarea", { class: "textarea dc-edit", rows: 3, "aria-label": `New wording of claim ${c.n}` });
    ta.value = c.claim;
    const save = h("button", { class: "btn btn-sm btn-primary", type: "button" }, "Save");
    const cancel = h("button", { class: "btn btn-sm btn-ghost", type: "button", onClick: () => drawBoard() }, "Cancel");
    save.addEventListener("click", () => setClaim(c, { claim: ta.value }));
    replace(row, h("div", { class: "stack", style: { gap: "6px", width: "100%" } },
      h("p", { class: "muted small", style: { margin: 0 } }, "Write it as one sentence a source could support or contradict: what is checked is this wording, not your draft's."),
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

  // a job of this draft that is running (or the one this page was opened with)
  const active = query.job ? await api("GET", `/api/jobs/${P(query.job)}`).catch(() => null) : null;
  const running = active && !TERMINAL.has(active.state) ? active : await runningJob(project, ["draft-find", "draft-check"], (j) => j.scope === draftId);
  if (running && alive) follow(running);

  return () => {
    alive = false;
    for (const w of watchers) w.stop();
    clearInterval(refreshTimer);
    document.removeEventListener("selectionchange", selListener);
  };
}
