// K2, rebuilt (2026-11-15): a codebook from theory documents, shaped on a page of its own (theoryframe.py). The first
// version listed each document's terms in a dialog of tick boxes, and a researcher got 81 codes that were words, not
// concepts. Here the draft is a framework: groups of concepts, each with the theory's own words (quoted with document
// and page), a definition to code with, when to use it in *your* documents and when not, the words those documents
// use for it, and passages of them that may show it, to keep as examples. It starts from what the texts define
// outright (no AI); *Read the theory* lets the AI read them whole and put the framework together (a job that may take
// minutes, so it is a page, not a dialog: DESIGN.md 4.16). The labels are the codebook editor's, so nothing is renamed
// when *Make the codebook* turns the concepts in the codebook into codes. Every change is kept in the draft as you work.
import { forgetFrameworks } from "./options.js";
import { aiRun } from "./progress.js";
import { App, api, h, icon, replace, clear, toast, showError, failedLoad, fmt, pageHead, P, plural, confirmDialog, dialog, field, watchJob, emptyState, shortTitle, session, debounce, button, setButtonKind, iconButton, stopButton, link, notice, card, tag, inset, input, select, textarea, choice, fold, readsLine, aiWhere, ownStartNote, workState, withAI, aiTag, foundWords, searchHref, setBusy, spinner, cap, aiButton, jobFailed } from "../lib.js";

const MAX_CONCEPTS = 60;   // theoryframe.MAX_CONCEPTS
const MAX_EXAMPLES = 8;    // a code keeps at most this many examples (codebooks.MAX_EXAMPLES)
const AI_FIELDS = ["meaning", "when_to_use", "when_not"];
const FIELD_LABEL = { meaning: "the definition", when_to_use: "when to use it", when_not: "when not to use it" };
const flat = (v) => String(v || "").split(/\s+/).filter(Boolean).join(" ");
const norm = (t) => flat(t).toLowerCase();
const listWords = (xs) => (xs.length < 2 ? (xs[0] || "") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
// the fields of a concept still in the AI's words (the editor's AI draft mark, compared as the server's make() does)
const aiFields = (c) => (c.ai ? AI_FIELDS.filter((f) => flat(c.ai[f]) && flat(c.ai[f]) === flat(c[f])) : []);
// a key the server keeps (theoryframe._KEY): "c" and ten hex digits
function newKey() {
  const a = new Uint8Array(5);
  crypto.getRandomValues(a);
  return "c" + Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
}
// the document opened at that place, as the app's other "in the text" links address one
const docHref = (s) => `#/doc/${encodeURIComponent(s.doc_id)}${Number.isInteger(s.start) && Number.isInteger(s.end) ? `?q=${s.start}-${s.end}` : ""}`;
const sameSource = (a, b) => a.doc_id === b.doc_id && a.start === b.start;
const sameExample = (a, b) => a.doc_id === b.doc_id && flat(a.quote) === flat(b.quote);

// A quote with the words found in it marked as found by matching (soft teal, never the quote's yellow: DESIGN.md
// 4.23). `marks`: where the search found them, [start, end] pairs counted in characters as the app's server counts
// them (so the page never matches the words a second way, and marks what was matched: "diagnosing" for "diagnose").
function marked(quote, marks) {
  const chars = Array.from(quote);
  const out = [];
  let at = 0;
  for (const [a, z] of marks || []) {
    if (!(Number.isInteger(a) && Number.isInteger(z)) || a < at || z <= a || z > chars.length) continue;
    if (a > at) out.push(chars.slice(at, a).join(""));
    out.push(foundWords(chars.slice(a, z).join("")));
    at = z;
  }
  out.push(chars.slice(at).join(""));
  return out;
}

export async function renderTheoryDraft(view) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/codebook-theory/draft`;
  let data;
  try { data = await api("GET", base); } catch (e) { failedLoad(view, e); return; }
  if (!data.draft) {
    view.appendChild(emptyState("book-marked", "No codebook is being drafted from theory",
      "Start one with New codebook, From theory documents: the concepts of your theory documents are shaped here before they become codes.",
      link({ kind: "next", href: "#/codebooks" }, "Start one on the Codebooks page")));
    return;
  }
  let draft = data.draft, offer = data.offer;
  let open = session(`td-open:${project}`) || null;            // the one concept open (a reload returns to it)
  let filter = session(`td-filter:${project}`) || "all";
  let job = null, watch = null, runEls = null;                  // the reading, while it runs
  let pending = false, saving = null, failed = false, gone = false;
  let nameProblem = "";                                         // the short name is taken: said in Draft settings
  let lookedUp = null;                                          // Add a concept by name: {term, r, ticked: Set}
  const evid = new Map();                                       // a concept's passages: key -> state (`ev`)
  let kept = new Map();                                         // each concept as the server last had it (key -> JSON)
  const keptNow = () => { kept = new Map(draft.concepts.map((c) => [c.key, JSON.stringify(c)])); };
  keptNow();
  let counts = null;                                            // {documents, counts: {key: n}}: the rows' documents
  let countSeq = 0;
  async function askCounts() {
    const seq = ++countSeq;
    try {
      const r = await api("GET", `${base}/counts`);
      if (seq !== countSeq || !view.isConnected) return;
      counts = r;
      for (const c of draft.concepts) refreshRow(c);
    } catch (_) { /* the rows go without their counts */ }
  }
  const askCountsSoon = debounce(askCounts, 1500);
  const head = h("div"), settingsBox = h("div"), theoryBox = h("div");
  // while the AI reads, the framework cannot be changed: one disabled fieldset holds it (its controls with it)
  const frame = h("fieldset", { class: "td-frame" });
  const bar = h("div", { class: "cb-savebar td-bar", role: "region", "aria-label": "The codebook to be made" });
  view.append(head, settingsBox, theoryBox, frame, bar);
  const running = () => draft.reading.state === "running";

  // ---- saving: every change is sent a moment later, whole (the groups and the concepts), one request at a time
  const saveSoon = debounce(() => { flush(); }, 800);
  function changed() { pending = true; saveSoon(); drawBar(); }
  async function flush() {
    saveSoon.cancel();
    while (saving) await saving.catch(() => {});
    if (!pending || gone) return !failed;
    pending = false;
    // while the AI reads, the reading's end writes the framework: only the title and the question are sent then
    const body = running() ? { title: draft.title, focus: draft.focus || "" }
      : { title: draft.title, focus: draft.focus || "", name: draft.name, where: draft.where, groups: draft.groups, concepts: draft.concepts };
    if (draft.rev !== undefined) body.rev = draft.rev;
    const sent = body.concepts ? new Map(body.concepts.map((c) => [c.key, JSON.stringify(c)])) : null;
    saving = api("PUT", base, body);
    try {
      const r = await saving;
      if (r.draft && r.draft.rev !== undefined) draft.rev = r.draft.rev;
      if (r.draft && r.draft.reading) draft.reading.stale = r.draft.reading.stale;
      if (sent) kept = sent;
      failed = false;
      return true;
    } catch (e) {
      if (e.status === 409) {
        // the draft changed since this page loaded it (a reading ended, another tab): it is loaded again, and the
        // concepts changed here since the last save are put into it, so nothing typed is lost
        const mine = running() ? [] : draft.concepts.filter((c) => kept.get(c.key) !== JSON.stringify(c));
        saving = null;
        await reload();
        if (mine.length && !gone && !running()) {
          for (const c of mine) { const i = draft.concepts.findIndex((x) => x.key === c.key); if (i >= 0) draft.concepts[i] = c; else draft.concepts.push(c); }
          drawAll();
          changed();
          toast(`The draft changed elsewhere. It is shown as it is now, with your last ${mine.length === 1 ? "change" : "changes"} put into it.`, "info");
        } else toast("The draft changed elsewhere: it is shown as it is now.", "info");
        return false;
      }
      if (e.status === 400 && /called|name/i.test(e.message || "")) { nameProblem = e.message; drawSettings(true); }
      if (e.status === 404) { gone = true; toast("The draft is gone (made into a codebook, or discarded elsewhere).", "info"); location.hash = "#/codebooks"; return false; }
      pending = true;
      failed = true;
      toast(`The draft could not be kept: ${e.message} It is tried again at your next change.`, "error");
      return false;
    } finally { saving = null; drawBar(); }
  }
  async function reload() {
    let d;
    try { d = await api("GET", base); } catch (e) { showError(e); return; }
    if (!view.isConnected) return;
    if (!d.draft) { gone = true; location.hash = "#/codebooks"; return; }
    data = d; draft = d.draft; offer = d.offer; pending = false; failed = false;
    keptNow();
    evid.clear();
    askCounts();
    drawAll();
    follow();
  }

  function drawAll() { drawHead(); drawSettings(); drawTheory(); drawFrame(); drawBar(); }

  // ---- the head
  function drawHead() {
    replace(head, pageHead([draft.title, " ", tag({}, "Draft")], {
      back: { href: "#/codebooks", text: "All codebooks" },
      facts: [`From ${plural(draft.doc_ids.length, "theory document")}`, "not made yet", aiTag("optional")],
      actions: button({ kind: "danger", sm: true, icon: "trash", onClick: discardDraft }, "Discard the draft"),
    }));
  }
  async function discardDraft() {
    if (!(await confirmDialog({ title: "Discard the draft?", message: "The draft and what you changed in it are removed. What the AI read is kept, so reading again costs nothing.", confirmText: "Discard the draft" }))) return;
    saveSoon.cancel();
    gone = true;
    try { await api("DELETE", base); } catch (e) { gone = false; showError(e); return; }
    toast("The draft is discarded.", "ok");
    location.hash = "#/codebooks";
  }

  // ---- Draft settings (folded, like the editor's Codebook settings). The short name and where it is kept were chosen
  // when the draft began; the server keeps them as they are.
  function drawSettings(openIt) {
    const titleIn = input({ value: draft.title, maxlength: 200 });
    titleIn.addEventListener("input", () => { const v = titleIn.value.trim(); if (v) { draft.title = v; changed(); drawHead(); } });
    const nameIn = input({ value: draft.name, maxlength: 40 });
    const nameErr = h("div", { class: "field-error", role: "alert" }, nameProblem);
    nameIn.addEventListener("input", () => { const v = nameIn.value.trim(); if (v) { draft.name = v; nameProblem = ""; nameErr.textContent = ""; changed(); } });
    const whereSel = choice({ label: "Kept", value: draft.where, options: [["project", "With this project"], ["home", "With all my projects"]],
      onPick: (w) => { draft.where = w; changed(); } });
    const titles = new Map((data.documents || []).map((d) => [d.doc_id, d.title]));
    const was = settingsBox.querySelector("details");
    const box = card({ as: "details", class: "cb-settings" }, h("summary", {}, icon("sliders", { size: 14 }), "Draft settings"),
      h("div", { class: "fields-2" }, field("Title", titleIn),
        field("Short name", nameIn, { help: "letters, digits, - and _ (the codebook’s file)" })),
      nameErr,
      h("div", { class: "field" }, h("span", { class: "field-label" }, "Kept"), whereSel),
      h("div", { class: "field" }, h("span", { class: "field-label" }, "Theory documents"),
        h("ul", { class: "td-docs" }, draft.doc_ids.map((id) => h("li", {}, link({ kind: "title", serif: true, href: `#/doc/${encodeURIComponent(id)}` }, titles.get(id) || "a document no longer in the project"))))),
      h("p", { class: "muted small" }, "To draw on other documents, start again from New codebook on the ", link({ href: "#/codebooks" }, "Codebooks page"), "."));
    if (openIt || (was && was.open)) box.open = true;
    replace(settingsBox, box);
  }

  // ---- The theory: the reading, in one of four states
  const offered = () => (offer ? offer.documents.filter((d) => d.offered) : []);
  const readsWhat = () => {
    const n = offered().length, parts = offer ? offer.parts : 0;
    return `${n === 1 ? "this whole document" : `these ${n} whole documents`}${parts > 1 ? `, in ${parts} parts` : ""}`;
  };
  const localLine = () => `The AI on this computer reads ${readsWhat()}: the text never leaves it.${ownStartNote()}`;
  // the documents no AI may read, one line each
  const docLines = () => (offer ? offer.documents.filter((d) => !d.offered).map((d) => h("p", { class: "muted small" },
    d.level === "none" ? `“${d.title}” is marked No AI: only the terms it defines outright are used.` : `“${d.title}”: ${d.why}`)) : []);
  function focusField() {
    const ta = textarea({ rows: 2, maxlength: 500, placeholder: "e.g. How do repair cafés make repairing a shared, everyday practice again?" });
    ta.value = draft.focus || "";
    ta.addEventListener("input", () => { draft.focus = ta.value; changed(); });
    return field(["What do you want to find out? ", h("span", { class: "muted" }, "(optional)")], ta,
      { help: "A sentence or two about your study. The concepts are then put in its words." });
  }
  function drawTheory() {
    runEls = null;
    const st = draft.reading.state;
    replace(theoryBox, st === "running" ? theoryRunning() : st === "read" ? theoryRead() : st === "failed" ? theoryFailed() : theoryNotRead());
  }
  function theoryNotRead() {
    const found = draft.concepts.filter((c) => c.how !== "own").length;
    const kids = [h("p", {}, found ? `Below ${found === 1 ? "is the one term" : `are the ${found} terms`} your theory documents define outright, found without AI: a start, not a framework.`
      : "Your theory documents define no term outright, so nothing was found without AI.")];
    if (offer && offer.offered) {
      const btn = aiButton({ kind: "main", onClick: (e) => readTheory(e.currentTarget) }, "Read the theory");
      kids.push(h("p", {}, "Let the AI read the documents whole. It joins what the authors share into one framework, and says in plain words what each concept means and when to use it in your documents."),
        focusField(), h("div", { class: "btn-row" }, withAI(btn)),
        offer.reader === "local" ? aiWhere(localLine(), "local") : readsLine(readsWhat()));
    } else if (offer && offer.why) {
      kids.push(h("p", { class: "muted" }, offer.why));
    }
    return card({ title: "The theory", class: "td-theory" }, kids, docLines());
  }
  // 0.19.13: the reading's AI run panel (aiRun, full): its head with Stop, and the two sides (this computer for the
  // documents only a local AI may read, Claude for the others), each with its own Start while its part waits
  function theoryRunning() {
    runEls = { run: aiRun({ size: "full", title: "Reading the theory", noun: "document",
      label: (j) => { const p = j.progress || {}; return j.waiting_for ? j.waiting_for.message : p.total ? `Reading the theory: ${p.done || 0} of ${plural(p.total, "step")} done` : "Reading the theory"; } }) };
    const c = card({ title: "The theory", class: "td-theory" }, runEls.run.el,
      h("p", { class: "muted small" }, "You can leave this page: the reading goes on and the draft waits here."));
    tickRunning();
    return c;
  }
  function tickRunning() {
    if (!runEls || !job) return;
    runEls.run.update(job);
  }
  function theoryRead() {
    const r = draft.reading;
    const ai = draft.concepts.filter((c) => c.how === "ai").length;
    const btn = aiButton({ onClick: (e) => readTheory(e.currentTarget) }, "Read again");
    const aside = (draft.left_out || []).length;
    const sentence = `Read by ${r.model || "the AI"}${r.at ? ` on ${fmt.date(r.at)}` : ""}, in ${plural(r.parts_read || r.parts || 0, "part")}. Its ${plural(r.drafted || 0, "draft")} of concepts, many of them the same idea from two documents, became ${plural(ai, "concept")}${draft.groups.length ? ` in ${plural(draft.groups.length, "group")}` : ", not grouped"}${aside ? `; ${aside} ${aside === 1 ? "is" : "are"} set aside` : ""}.`;
    return card({ title: "The theory", class: "td-theory" },
      h("p", {}, workState("done", sentence)),
      (r.problems || []).length ? notice({ kind: "attention" }, (r.problems.length === 1 ? h("p", {}, r.problems[0]) : h("ul", {}, r.problems.map((x) => h("li", {}, x))))) : null,
      r.stale ? h("p", { class: "small" }, "Your question changed since this reading: read again to put the concepts in its words.") : null,
      fold({ open: !!r.stale }, "Your question, and reading again", focusField(),
        offer && offer.offered ? [h("div", { class: "btn-row" }, withAI(btn)),
          offer.reader === "local" ? aiWhere(localLine(), "local") : readsLine(readsWhat()),
          h("p", { class: "muted small" }, "Reading again keeps every concept you changed, marked as done, added or kept examples for. The rest is replaced by the new reading.")]
          : h("p", { class: "muted small" }, offer ? offer.why : "")),
      docLines());
  }
  function theoryFailed() {
    const r = draft.reading;
    const why = (r.problems || []).length ? r.problems[r.problems.length - 1] : "The reading did not work.";
    const btn = aiButton({ sm: true, onClick: (e) => readTheory(e.currentTarget) }, "Read it again");
    return card({ title: "The theory", class: "td-theory" },
      notice({ kind: "error" }, h("p", {}, why), offer && offer.offered ? h("div", { class: "btn-row" }, withAI(btn)) : null),
      offer && offer.offered ? (offer.reader === "local" ? aiWhere(localLine(), "local") : readsLine(readsWhat())) : null,
      fold({}, "Your question", focusField()),
      docLines());
  }
  async function readTheory(btn) {
    setBusy(btn, true);
    try {
      await flush();
      const r = await api("POST", `${base}/read`);
      job = r.job;
      // the draft now says the reading runs, under a new revision: loaded again, so a later save is not refused
      await reload();
    } catch (e) { showError(e); if (btn.isConnected) setBusy(btn, false); }
  }
  // watch the reading (also one found running after a reload); when it ends, the draft is loaded again
  function follow() {
    if (!running() || watch || !draft.reading.job) return;
    watch = watchJob(draft.reading.job, (j) => { job = j; tickRunning(); });
    watch.promise.then((j) => { watch = null; afterReading(j); }, () => { watch = null; reload(); });
  }
  async function afterReading(j) {
    if (!view.isConnected) return;
    const res = j.result || {};
    job = null;
    await reload();
    if (j.state === "error") jobFailed(j, () => reload());   // memory: the local side, whose Start reads it again (followed after the reload)
    else if (j.state !== "done" || res.stopped) toast("The reading is stopped. The draft is as it was.", "info");
    else if (res.withdrawn) toast("The request was taken back before the AI answered. Read again.", "warn");
    else if (res.ok) toast(`The theory is read: ${plural(res.concepts || 0, "concept")} in ${plural(res.groups || 0, "group")}. Open each to check its words.`, "ok");
    else if (res.state === "read") toast("The AI could not put the framework together: the concepts are each document’s, not grouped. The card above says why.", "warn");
  }

  // ---- The framework
  const groupKeys = () => new Set(draft.groups.map((g) => g.key));
  const inGroup = (g) => {
    const keys = groupKeys();
    return draft.concepts.filter((c) => (g ? c.group === g.key : !keys.has(c.group)));
  };
  // the page's order: each group's concepts in the codebook, then the rest; the concepts without a group last
  function pageOrder() {
    const out = [];
    for (const g of [...draft.groups, null]) { const cs = inGroup(g); out.push(...cs.filter((c) => c.keep), ...cs.filter((c) => !c.keep)); }
    return out;
  }
  function drawFrame() {
    clear(frame);
    frame.disabled = running();
    const all = draft.concepts, nIn = all.filter((c) => c.keep).length;
    const sec = h("section", { class: "td-framework", "aria-labelledby": "td-fw-h" });
    sec.appendChild(h("h2", { id: "td-fw-h", class: "cb-h2" }, "The framework"));
    if (running()) sec.appendChild(h("p", { class: "muted small" }, "The framework can be changed again when the reading is done."));
    if (all.length) {
      sec.append(h("p", { class: "muted" }, `${plural(all.length, "concept")}${draft.groups.length ? ` in ${plural(draft.groups.length, "group")}` : ""}, ${nIn} in the codebook. Open a concept to see the theory’s words and the passages of your documents.`),
        choice({ filter: true, label: "Which concepts", class: "td-filter", value: filter,
          options: [["all", "All", all.length], ["in", "In the codebook", nIn], ["out", "Not in the codebook", all.length - nIn]],
          onPick: (v) => { filter = v; session(`td-filter:${project}`, v); drawFrame(); } }));
      if (draft.groups.length > 1) {
        sec.appendChild(h("p", { class: "td-jumps small" }, draft.groups.map((g, i) => {
          const cs = inGroup(g);
          return [i ? h("span", { class: "muted", "aria-hidden": "true" }, " · ") : null,
            link({ kind: "jump", onClick: () => { const el = frame.querySelector(`[data-group="${g.key}"]`); if (el) el.scrollIntoView({ block: "start" }); } },
              `${g.name} `, h("span", { class: "muted" }, `${cs.filter((c) => c.keep).length} of ${cs.length}`))];
        })));
      }
    } else {
      sec.appendChild(h("p", { class: "muted" }, "No concept yet. Let the AI read the theory, or add a concept by name below."));
    }
    frame.appendChild(sec);
    for (const g of [...draft.groups, null]) { const c = groupCard(g); if (c) frame.appendChild(c); }
    frame.appendChild(h("div", { class: "btn-row cb-foot td-foot" }, button({ sm: true, icon: "plus", onClick: addGroup }, "Add a group")));
    const aside = asideCard();
    if (aside) frame.appendChild(aside);
    frame.appendChild(addCard());
    drawBar();
  }
  function groupCard(g) {
    const cs = inGroup(g), ins = cs.filter((c) => c.keep), outs = cs.filter((c) => !c.keep);
    const showIn = filter === "out" ? [] : ins, showOut = filter === "in" ? [] : outs;
    if (!showIn.length && !showOut.length && (!g || filter !== "all")) return null;
    const sec = card({ as: "section", class: "cb-group", dataset: { group: g ? g.key : "" } });
    let name;
    if (g) {
      name = input({ value: g.name, maxlength: 60, class: "td-group-input", "aria-label": "Group name" });
      name.addEventListener("input", () => { const v = name.value.trim(); if (v) { g.name = v; changed(); } });
      name.addEventListener("change", () => drawFrame());   // the jump links and the Group fields take the new name
    } else {
      name = h("h2", { class: "cb-group-name" }, "Concepts without a group");
    }
    sec.appendChild(h("div", { class: "cb-group-head" }, name, h("span", { class: "muted small" }, `${ins.length} of ${cs.length} in the codebook`),
      g && !cs.length ? button({ kind: "quiet", sm: true, onClick: () => { draft.groups = draft.groups.filter((x) => x !== g); changed(); drawFrame(); } }, "Remove the group") : null));
    if (g && g.about) sec.appendChild(h("p", { class: "muted small td-about" }, g.about));
    if (!cs.length) sec.appendChild(h("p", { class: "muted small" }, "No concept in it yet: choose this group in a concept’s Group field."));
    const ul = h("ul", { class: "cb-codes" });
    showIn.forEach((c) => ul.appendChild(row(c)));
    if (showIn.length && showOut.length) ul.appendChild(h("li", { class: "td-divider muted small" }, "Also in the theory, not in the codebook"));
    showOut.forEach((c) => ul.appendChild(row(c)));
    if (cs.length) sec.appendChild(ul);
    return sec;
  }
  function addGroup() {
    const keys = groupKeys();
    let i = draft.groups.length + 1;
    while (keys.has(`g${i}`)) i++;
    draft.groups.push({ key: `g${i}`, name: "New group", about: "" });
    changed();
    drawFrame();
    const el = frame.querySelector(`[data-group="g${i}"] input`);
    if (el) { el.focus(); el.select(); }
  }

  // ---- a concept's row
  function summaryLine(c) {
    if (flat(c.meaning)) return shortTitle(flat(c.meaning), 160);
    if (c.sources.length) return h("span", { class: "serif" }, `“${shortTitle(flat(c.sources[0].quote), 150)}”`);
    return h("em", { class: "muted" }, "no definition yet");
  }
  function badges(c) {
    const docs = new Set(c.sources.map((x) => x.doc_id)).size;
    const n = counts && counts.counts ? counts.counts[c.key] : undefined;
    return h("span", { class: "cb-code-badges" },
      docs > 1 ? tag({ icon: "book-open", title: `${docs} of your theory documents say what it means` }, `${docs} theory documents`) : null,
      n !== undefined && (c.words || []).length ? tag({ icon: "file-text", title: n ? `Its words are found in ${n} of your ${plural(counts.documents, "document")}` : "None of your documents uses its words: try other words, or leave it out" },
        n ? `in ${plural(n, "document")}` : "in no document") : null,
      c.examples.length ? tag({ icon: "quote", title: "Examples kept from your documents" }, plural(c.examples.length, "example")) : null,
      c.checked ? tag({ icon: "check", title: "You have looked it over" }, "Done") : null);
  }
  function keepButton(c) {
    return c.keep ? button({ kind: "quiet", sm: true, title: `Take “${cap(c.name)}” out of the codebook`, onClick: () => setKeep(c, false) }, "Take out")
      : button({ sm: true, icon: "plus", title: `Add “${cap(c.name)}” to the codebook`, onClick: () => setKeep(c, true) }, "Add");
  }
  function row(c) {
    const isOpen = open === c.key;
    const li = h("li", { class: "cb-code td-concept" + (isOpen ? " cb-open" : ""), dataset: { key: c.key } });
    const sum = h("button", { class: "cb-code-sum", type: "button", "aria-expanded": isOpen ? "true" : "false", onClick: () => toggle(c) },
      h("span", { class: "cb-code-name serif" }, cap(c.name)),
      h("span", { class: "cb-code-desc" }, summaryLine(c)),
      badges(c),
      icon(isOpen ? "chevron-up" : "chevron-down", { size: 15 }));
    li.appendChild(h("div", { class: "cb-code-row td-row" }, sum, keepButton(c)));
    if (isOpen) li.appendChild(detail(c));
    return li;
  }
  // a typed change shows in the closed line at once, without drawing the page again (the field keeps its focus)
  function refreshRow(c) {
    const li = frame.querySelector(`li[data-key="${c.key}"]`);
    if (!li) return;
    const name = li.querySelector(".cb-code-name"), desc = li.querySelector(".cb-code-desc"), b = li.querySelector(".cb-code-badges");
    if (name) name.textContent = cap(c.name);
    if (desc) replace(desc, summaryLine(c));
    if (b) b.replaceWith(badges(c));
    drawBar();
  }
  function setKeep(c, keep) { c.keep = keep; changed(); drawFrame(); }
  function toggle(c) {
    open = open === c.key ? null : c.key;
    session(`td-open:${project}`, open);
    drawFrame();
    if (open) showOpen();
  }
  function showOpen(focus = false) {
    const li = open && frame.querySelector(`li[data-key="${open}"]`);
    if (!li) return;
    li.scrollIntoView({ block: focus ? "start" : "nearest" });
    if (focus) { const s = li.querySelector(".cb-code-sum"); if (s) s.focus({ preventScroll: true }); }
  }
  function openConcept(c) {
    open = c.key;
    session(`td-open:${project}`, open);
    if (filter !== "all" && (filter === "in") !== !!c.keep) { filter = "all"; session(`td-filter:${project}`, filter); }
    drawFrame();
    showOpen(true);
  }

  // ---- an open concept: the theory, the code, the evidence (the eye goes from the theory to the code to the passages)
  function detail(c) {
    return h("div", { class: "cb-detail td-detail" }, theoryPart(c), codePart(c), evidencePart(c), footRow(c));
  }
  function theoryPart(c) {
    const list = h("div", { class: "td-quotes" });
    const drawList = () => replace(list, c.sources.length ? c.sources.map((s, i) => inset({ class: "td-quote" },
      h("p", { class: "serif td-quote-text" }, `“${flat(s.quote)}”`),
      h("p", { class: "small td-where" }, link({ kind: "title", serif: true, href: docHref(s), title: "Open the document at this place" }, s.title || "untitled"),
        s.page ? h("span", { class: "muted" }, ` p. ${s.page}`) : null,
        iconButton({ icon: "x", sm: true, label: "Remove this quote", onClick: () => { c.sources.splice(i, 1); changed(); drawList(); drawMore(); refreshRow(c); } }))))
      : h("p", { class: "muted small" }, "No sentence of the theory is chosen yet."));
    drawList();
    // Look for more in the theory: the term's best sentences in each theory document (no AI)
    const more = h("div", { class: "td-more", "aria-live": "polite" });
    let got = null;
    const lookBtn = button({ sm: true, icon: "search", onClick: async () => {
      setBusy(lookBtn, true);
      try { got = await api("GET", `${base}/lookup?term=${encodeURIComponent(c.name)}`); drawMore(); }
      catch (e) { showError(e); } finally { setBusy(lookBtn, false); }
    } }, "Look for more in the theory");
    function drawMore() {
      if (!got) return;
      replace(more, got.sources.map((s) => {
        const left = s.options.filter((o) => !c.sources.some((x) => sameSource(x, { ...o, doc_id: s.doc_id })));
        return h("div", { class: "td-more-doc" },
          h("p", { class: "small" }, h("strong", {}, s.title || "untitled"),
            !s.options.length ? h("span", { class: "muted" }, ` does not use “${got.term}”.`)
              : !left.length ? h("span", { class: "muted" }, ": its best sentences are chosen already.") : null),
          left.length ? h("ul", { class: "td-options" }, left.map((o) => h("li", {},
            h("span", { class: "serif" }, `“${flat(o.quote)}”`), o.page ? h("span", { class: "muted small" }, ` p. ${o.page}`) : null,
            button({ kind: "quiet", sm: true, icon: "plus", onClick: () => {
              c.sources.push({ doc_id: s.doc_id, title: s.title, quote: o.quote, start: o.start, end: o.end, page: o.page });
              changed(); drawList(); drawMore(); refreshRow(c);
            } }, "Add this quote")))) : null);
      }));
    }
    return h("div", { class: "td-part" }, h("h3", { class: "td-h3" }, "In the theory"), list, h("div", { class: "btn-row" }, lookBtn), more);
  }
  function codePart(c) {
    const nameIn = input({ value: c.name, maxlength: 60 });
    nameIn.addEventListener("input", () => { const v = nameIn.value.trim(); if (v) { c.name = v; changed(); refreshRow(c); } });
    const groupSel = select({ "aria-label": "Group" }, h("option", { value: "", selected: !groupKeys().has(c.group) }, "No group"),
      draft.groups.map((g) => h("option", { value: g.key, selected: g.key === c.group }, g.name)));
    groupSel.addEventListener("change", () => { c.group = groupSel.value; changed(); drawFrame(); showOpen(true); });
    const mark = h("div", { class: "cb-draft-mark", "aria-live": "polite" });
    const drawMark = () => {
      const f = aiFields(c);
      replace(mark, f.length ? h("p", { class: "small" }, tag({ icon: "sparkles" }, "AI draft"), " ",
        `${cap(listWords(f.map((k) => FIELD_LABEL[k])))} ${f.length === 1 ? "is" : "are"} still the AI’s words${c.ai.model ? ` (${c.ai.model})` : ""}, drafted from your theory documents. Rewrite ${f.length === 1 ? "it" : "them"} in your own words; the mark goes when you do.`) : null);
    };
    drawMark();
    // a box as tall as its text (by its rows: a field half the page's width holds about 45 letters a line)
    const fit = (t, perLine, least) => { t.rows = Math.min(10, Math.max(least, Math.ceil(t.value.length / perLine) + t.value.split("\n").length - 1)); };
    const area = (key, least, max, perLine) => {
      const t = textarea({ rows: least, maxlength: max });
      t.value = c[key] || "";
      fit(t, perLine, least);
      t.addEventListener("input", () => { c[key] = t.value; fit(t, perLine, least); changed(); drawMark(); refreshRow(c); });
      return t;
    };
    const words = textarea({ rows: 2, maxlength: 1200 });
    words.value = (c.words || []).join(", ");
    fit(words, 95, 2);
    words.addEventListener("input", () => {
      c.words = [...new Map(words.value.split(/[,;\n]/).map(flat).filter(Boolean).map((w) => [w.toLowerCase(), w])).values()];
      fit(words, 95, 2);
      changed();
      askSoon(c);
      askCountsSoon();
    });
    return h("div", { class: "td-part" }, h("h3", { class: "td-h3" }, "The code"),
      h("div", { class: "fields-2" }, field("Name", nameIn), field("Group", groupSel)),
      field("Definition", area("meaning", 2, 1200, 95), { help: c.sources.length
        ? "What the concept means, in plain words. The AI reads it when it labels. In the codebook the theory’s first quote above follows it, with its document and page."
        : "What the concept means, in plain words. The AI reads it when it labels." }),
      h("div", { class: "fields-2" }, field("When to use it", area("when_to_use", 3, 1000, 45)), field("When not to use it", area("when_not", 3, 800, 45))),
      mark,
      field("Words it is matched by", words, { help: "The words your documents use for it, separated by commas. They find the passages below." }));
  }

  // ---- In your documents: passages that may show the concept, found by its words (no AI), to keep as examples
  const ev = (c) => {
    if (!evid.has(c.key)) evid.set(c.key, { passages: [], hidden: new Set(), shown: new Set(), asked: null, loading: false, error: null, none: false, seq: 0 });
    return evid.get(c.key);
  };
  const wordsKey = (c) => (c.words || []).map(norm).join("|");
  const askSoon = debounce((c) => { ev(c).shown.clear(); askEvidence(c); }, 700);
  async function askEvidence(c, more = false) {
    const e = ev(c);
    if (!(c.words || []).length) { e.passages = []; e.asked = ""; drawEvidence(c); return; }
    const my = ++e.seq;
    e.loading = true;
    drawEvidence(c);
    const skip = [...e.hidden, ...(more ? e.shown : [])];
    try {
      const r = await api("POST", `${base}/evidence`, { concept: { name: c.name, meaning: c.meaning || "", when_to_use: c.when_to_use || "", words: c.words }, skip, k: 4 });
      if (my !== e.seq) return;
      const fresh = r.passages.filter((p) => !c.examples.some((x) => sameExample(x, p)));
      fresh.forEach((p) => e.shown.add(p.passage_id));
      e.none = more && !fresh.length;   // asked for others and there were none: the shown ones stay
      if (!e.none) e.passages = fresh;
      e.asked = wordsKey(c);
      e.error = null;
    } catch (err) { if (my === e.seq) e.error = err.message; }
    finally { if (my === e.seq) { e.loading = false; drawEvidence(c); } }
  }
  function evidencePart(c) {
    const part = h("div", { class: "td-part", dataset: { evidence: c.key } }, h("h3", { class: "td-h3" }, "In your documents"),
      h("p", { class: "muted small" }, "Passages that may show it, found by its words, without AI. Keep the ones that do: they go into the codebook as examples."),
      h("div", { class: "td-kept" }), h("div", { class: "td-found", "aria-live": "polite" }));
    // drawn once it is on the page (drawEvidence finds its boxes there)
    setTimeout(() => {
      const e = ev(c);
      if (e.asked !== wordsKey(c) && !e.loading) askEvidence(c); else drawEvidence(c);
    }, 0);
    return part;
  }
  const whereLine = (x) => h("p", { class: "small td-where" },
    link({ kind: "title", serif: true, href: docHref(x), title: "Open the document at this place" }, shortTitle(x.title || "untitled", 90)),
    x.page ? h("span", { class: "muted" }, ` p. ${x.page}`) : null);
  function drawEvidence(c) {
    const part = frame.querySelector(`[data-evidence="${c.key}"]`);
    if (!part) return;
    const e = ev(c), words = c.words || [];
    const full = c.examples.length >= MAX_EXAMPLES;
    replace(part.querySelector(".td-kept"), c.examples.map((x, i) => inset({ class: "td-passage" }, whereLine(x),
      h("p", { class: "serif td-quote-text" }, flat(x.quote)),
      h("div", { class: "btn-row" }, h("span", { class: "small td-kept-mark" }, icon("check", { size: 13 }), " Kept as an example"),
        button({ kind: "quiet", sm: true, onClick: () => { c.examples.splice(i, 1); changed(); drawEvidence(c); refreshRow(c); } }, "Take back")))),
      full ? h("p", { class: "muted small" }, `It has ${MAX_EXAMPLES} examples, as many as a code keeps. Take one back to keep another.`) : null);
    const box = part.querySelector(".td-found");
    if (!words.length) { replace(box, h("p", { class: "muted small" }, "Type the words your documents use for it above: its passages show here.")); return; }
    if (e.loading && !e.passages.length) { replace(box, spinner("Looking for passages…")); return; }
    if (e.error) { replace(box, h("p", { class: "muted small" }, `The passages could not be looked for: ${e.error}`)); return; }
    const shown = e.passages.filter((p) => !c.examples.some((x) => sameExample(x, p)));
    replace(box,
      shown.length ? shown.map((p) => {
        const nodes = marked(p.quote, p.marks), found = p.matched || [];
        return inset({ class: "td-passage" }, whereLine(p), h("p", { class: "serif td-quote-text" }, nodes),
          found.length ? h("p", { class: "muted small" }, `Matched: ${found.join(", ")}`) : p.found_by === "meaning" ? h("p", { class: "muted small" }, "Found by its meaning") : null,
          h("div", { class: "btn-row" },
            button({ sm: true, icon: "check", disabled: full, onClick: () => {
              c.examples.push({ quote: p.quote, doc_id: p.doc_id, title: p.title, page: p.page, start: p.start, end: p.end, project: p.project });
              changed(); drawEvidence(c); refreshRow(c);
            } }, "Keep as an example"),
            button({ kind: "quiet", sm: true, icon: "eye-off", onClick: () => { e.hidden.add(p.passage_id); e.passages = e.passages.filter((x) => x !== p); drawEvidence(c); } }, "Hide this passage")));
      }) : e.asked !== null ? h("p", { class: "muted small" }, e.passages.length || c.examples.length ? "No other passage uses these words." : "No passage of your documents uses these words. Try other words.") : null,
      e.none ? h("p", { class: "muted small" }, "No other passage uses these words.") : null,
      h("div", { class: "btn-row td-ev-foot" },
        e.asked !== null && shown.length ? button({ kind: "quiet", sm: true, icon: "refresh", disabled: e.loading, onClick: () => askEvidence(c, true) }, "Show other passages") : null,
        link({ href: searchHref(words.join(" ")) }, "Every place these words occur, in Search")));
  }

  // ---- the open concept's foot: checked, next, merge, in or out, remove
  function footRow(c) {
    const order = pageOrder();
    const next = order.slice(order.indexOf(c) + 1).find((x) => x.keep);
    const others = draft.concepts.filter((x) => x !== c);
    const mergeSel = select({ sm: true, class: "cb-merge", "aria-label": `Merge ${cap(c.name)} into another concept` },
      h("option", { value: "" }, "Merge into…"), others.map((x) => h("option", { value: x.key }, cap(x.name))));
    mergeSel.addEventListener("change", () => { const t = others.find((x) => x.key === mergeSel.value); if (t) merge(c, t); });
    return h("div", { class: "btn-row cb-code-actions" },
      c.checked ? [h("span", { class: "small td-kept-mark" }, icon("check", { size: 13 }), " Checked"),
        button({ kind: "quiet", sm: true, onClick: () => { c.checked = false; changed(); drawFrame(); } }, "Undo")]
        : button({ kind: "quiet", sm: true, icon: "check", onClick: () => { c.checked = true; changed(); drawFrame(); } }, "Mark as done"),
      next ? button({ kind: "quiet", sm: true, icon: "arrow-right", onClick: () => openConcept(next) }, "Next concept") : null,
      others.length ? mergeSel : null,
      keepButton(c),
      c.how === "own" ? button({ kind: "danger", sm: true, icon: "trash", onClick: () => removeConcept(c) }, "Remove from the draft") : null);
  }
  function merge(c, into) {
    const before = JSON.stringify(draft.concepts);
    for (const s of c.sources) if (!into.sources.some((x) => sameSource(x, s))) into.sources.push(s);
    for (const x of c.examples) if (into.examples.length < MAX_EXAMPLES && !into.examples.some((y) => sameExample(x, y))) into.examples.push(x);
    for (const w of c.words || []) if (!into.words.some((y) => norm(y) === norm(w))) into.words.push(w);
    draft.concepts = draft.concepts.filter((x) => x !== c);
    open = into.key;
    session(`td-open:${project}`, open);
    evid.delete(into.key);
    changed();
    drawFrame();
    showOpen(true);
    toast(`“${cap(c.name)}” is merged into “${cap(into.name)}”: its quotes, examples and words are there now.`, "ok", { button: { text: "Undo", onClick: () => {
      draft.concepts = JSON.parse(before);
      open = c.key;
      session(`td-open:${project}`, open);
      evid.delete(into.key);
      changed();
      drawFrame();
    } } });
  }
  async function removeConcept(c) {
    if (!(await confirmDialog({ title: `Remove “${cap(c.name)}” from the draft?`, message: "Its quotes, its words and the examples kept for it go with it.", confirmText: "Remove" }))) return;
    draft.concepts = draft.concepts.filter((x) => x !== c);
    if (open === c.key) { open = null; session(`td-open:${project}`, null); }
    changed();
    drawFrame();
  }
  function addConcept(c) {
    if (draft.concepts.length >= MAX_CONCEPTS) { toast(`A draft holds at most ${MAX_CONCEPTS} concepts. Merge some first.`, "info"); return false; }
    draft.concepts.push({ key: newKey(), group: "", meaning: "", when_to_use: "", when_not: "", core: false, keep: true, checked: false, examples: [], ai: null, ...c });
    openConcept(draft.concepts[draft.concepts.length - 1]);
    changed();
    return true;
  }

  // ---- the drafts the AI set aside: one row a name (the server may list a name once for each document)
  function asideCard() {
    if (draft.reading.state !== "read") return null;
    const have = new Set(draft.concepts.map((c) => norm(c.name)));
    const seen = new Set(), rows = [];
    for (const d of draft.left_out || []) {
      const k = norm(d.name);
      if (!k || seen.has(k) || have.has(k)) continue;
      seen.add(k);
      rows.push(d);
    }
    if (!rows.length) return null;
    return card({ class: "td-aside" }, fold({}, `${plural(rows.length, "concept")} set aside by the AI`,
      h("p", { class: "muted small" }, "Drafted from the documents and left out of the framework: methods of the authors, schools of thought, sentences that define nothing. Add any you miss."),
      h("ul", { class: "td-aside-list" }, rows.map((d) => h("li", {},
        h("span", { class: "serif td-aside-name" }, cap(d.name)),
        h("span", { class: "muted small td-aside-where" }, `${shortTitle(d.title || "untitled", 40)}${d.page ? `, p. ${d.page}` : ""}`),
        h("span", { class: "small td-aside-quote", title: flat(d.quote) }, flat(d.quote)),
        button({ sm: true, icon: "plus", onClick: () => addConcept({ name: d.name, how: "ai", words: [norm(d.name)],
          sources: [{ doc_id: d.doc_id, title: d.title, quote: d.quote, start: d.start, end: d.end, page: d.page }] }) }, "Add"))))));
  }

  // ---- Add a concept by name: its sentences in the theory documents, to tick (no AI)
  function addCard() {
    const inp = input({ maxlength: 60, placeholder: "e.g. recruitment, habitus", "aria-label": "The concept’s name", value: lookedUp ? lookedUp.term : "" });
    const res = h("div", { class: "td-lookup", "aria-live": "polite" });
    const go = button({ icon: "search", onClick: () => lookUp() }, "Look it up");
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); lookUp(); } });
    async function lookUp() {
      const term = flat(inp.value);
      if (!term) { inp.focus(); return; }
      setBusy(go, true);
      try { lookedUp = { term, r: await api("GET", `${base}/lookup?term=${encodeURIComponent(term)}`), ticked: new Set() }; drawLookup(); }
      catch (e) { showError(e); } finally { setBusy(go, false); }
    }
    function drawLookup() {
      if (!lookedUp) { clear(res); return; }
      const { term, r, ticked } = lookedUp;
      const using = r.sources.filter((s) => s.options.length);
      const there = draft.concepts.find((c) => norm(c.name) === norm(term));
      const aside = (draft.left_out || []).some((d) => norm(d.name) === norm(term));
      const optKey = (s, o) => `${s.doc_id}:${o.start}`;
      replace(res,
        h("p", { class: "small" }, using.length
          ? `${plural(using.length, "theory document")} of ${r.sources.length} ${using.length === 1 ? "uses" : "use"} “${r.term}”. Tick the sentences that say what it means: they go with the concept as the theory’s words.`
          : `None of the ${plural(r.sources.length, "theory document")} uses “${r.term}”.`),
        there ? h("p", { class: "small" }, `“${cap(there.name)}” is in the draft already. `, link({ kind: "jump", onClick: () => openConcept(there) }, "Show it")) : null,
        aside && !there ? h("p", { class: "muted small" }, "The AI drafted it too, and set it aside.") : null,
        r.sources.map((s) => h("div", { class: "td-more-doc" },
          h("p", { class: "small" }, h("strong", {}, s.title || "untitled"), s.options.length ? h("span", { class: "muted" }, ` · ${plural(s.uses, "sentence")} ${s.uses === 1 ? "uses" : "use"} it`) : h("span", { class: "muted" }, ` does not use “${r.term}”.`)),
          s.options.length ? h("ul", { class: "td-options" }, s.options.map((o) => {
            const cb = h("input", { type: "checkbox", checked: ticked.has(optKey(s, o)) });
            cb.addEventListener("change", () => { if (cb.checked) ticked.add(optKey(s, o)); else ticked.delete(optKey(s, o)); });
            return h("li", {}, h("label", { class: "td-pick" }, cb, h("span", {}, h("span", { class: "serif" }, `“${flat(o.quote)}”`), o.page ? h("span", { class: "muted small" }, ` p. ${o.page}`) : null)));
          })) : null)),
        h("div", { class: "btn-row" }, button({ icon: "plus", onClick: () => {
          const sources = [];
          for (const s of r.sources) for (const o of s.options) if (ticked.has(optKey(s, o))) sources.push({ doc_id: s.doc_id, title: s.title, quote: o.quote, start: o.start, end: o.end, page: o.page });
          const key = newKey();
          // the passages the look-up found are the new concept's first ones
          evid.set(key, { passages: r.passages || [], hidden: new Set(), shown: new Set((r.passages || []).map((p) => p.passage_id)), asked: norm(term), loading: false, error: null, none: false, seq: 0 });
          lookedUp = null;
          if (!addConcept({ key, name: term, how: "own", words: [term.toLowerCase()], sources })) evid.delete(key);
        } }, `Add “${cap(term)}”`), h("span", { class: "muted small" }, "None ticked is fine: you can write its definition yourself.")));
    }
    drawLookup();
    return card({ title: "Add a concept by name", class: "td-add" },
      h("div", { class: "td-add-row" }, inp, go), h("p", { class: "muted small" }, "No AI reads anything for this."), res);
  }

  // ---- the bar: what the codebook will hold, and Make the codebook
  const barCount = h("span", { class: "td-bar-count" });
  const barNote = h("span", { class: "muted small td-bar-note" });
  const barWhy = h("span", { class: "muted small" });
  const makeBtn = button({ icon: "check", onClick: (e) => make(e.currentTarget) }, "Make the codebook");
  bar.append(barCount, barNote, barWhy, makeBtn);
  function drawBar() {
    const ins = draft.concepts.filter((c) => c.keep);
    replace(barCount, h("strong", {}, plural(ins.length, "concept")), ` in the codebook · ${ins.filter((c) => c.checked).length} done · ${ins.filter((c) => c.examples.length).length} with examples`);
    barNote.textContent = failed ? "Not kept yet: it is tried again at your next change." : "The draft is kept as you work.";
    // the page's main button: Read the theory before a reading (when the AI may read), Make the codebook after
    setButtonKind(makeBtn, draft.reading.state === "read" || !(offer && offer.offered) ? "main" : "standard");
    makeBtn.disabled = !ins.length || running() || makeBtn.getAttribute("aria-busy") === "true";
    barWhy.textContent = running() ? "Wait until the reading is done." : !ins.length ? "Add a concept first." : "";
    barWhy.hidden = !barWhy.textContent;
    barNote.hidden = !barWhy.hidden && !failed;   // one line beside the counts: why it cannot be made comes first
  }
  async function make(btn) {
    // said before it is made: what becomes of the rest, and how much is still as the AI wrote it
    const ins = draft.concepts.filter((c) => c.keep), outs = draft.concepts.length - ins.length, aside = (draft.left_out || []).length;
    const asAI = ins.filter((c) => aiFields(c).length && !c.checked).length;
    const rest = outs + aside;
    const ok = await dialog({ title: "Make the codebook?", body: h("div", { class: "stack" },
      h("p", {}, `The ${ins.length === 1 ? "concept" : `${ins.length} concepts`} in the codebook ${ins.length === 1 ? "becomes a code" : "become codes"} of “${draft.title}”, in ${ins.length === 1 ? "its group" : "their groups"}. You go on in the codebook’s editor.`),
      asAI ? h("p", {}, `${asAI === ins.length ? (asAI === 1 ? "It is" : `All ${asAI} are`) : `${asAI} of them ${asAI === 1 ? "is" : "are"}`} still as the AI drafted ${asAI === 1 ? "it" : "them"}, not marked as done. ${asAI === 1 ? "It keeps its" : "They keep their"} AI draft mark in the codebook, so you can look ${asAI === 1 ? "it" : "them"} over there too.`) : null,
      rest ? h("p", { class: "muted small" }, `The draft ends here: the ${plural(rest, "concept")} not in the codebook ${rest === 1 ? "is" : "are"} not kept. What the AI read is kept, so a new draft from the same documents gives the framework again at once.`) : null),
      actions: [{ text: "Not yet", value: null }, { text: "Make the codebook", value: true, primary: true }] });
    if (!ok) return;
    setBusy(btn, true);
    try {
      if (!(await flush())) return;
      const r = await api("POST", `${base}/make`);
      gone = true;
      forgetFrameworks();
      toast("Codebook made. The research log says so.", "ok");
      location.hash = `#/codebooks/${encodeURIComponent(r.codebook.name)}`;
    } catch (e) { showError(e); }
    finally { if (btn.isConnected) { setBusy(btn, false); drawBar(); } }
  }

  drawAll();
  follow();
  askCounts();
  if (open) setTimeout(() => showOpen(true), 0);
  const onUnload = (e) => { if (pending || saving) { flush(); e.preventDefault(); e.returnValue = ""; } };
  window.addEventListener("beforeunload", onUnload);
  return () => {
    window.removeEventListener("beforeunload", onUnload);
    if (watch) watch.stop();
    askSoon.cancel();
    askCountsSoon.cancel();
    if (pending && !gone) flush();   // leaving the page: what was changed is kept
  };
}
