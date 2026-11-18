// Settings: model service, embeddings, check defaults, frameworks, model test, data folder.
import { store, saveBlob, App, api, h, icon, tabs, replace, clear, toast, showError, fmt, pageHead, watchJob, P, field, switchControl, rangeControl, confirmDialog, dialog, download, VERSION, TERMINAL, strictness, statusBadge, copyLine, tesseractHelp, helpMark, rememberClaude, claudeAccount, appName, Updates, checkUpdate, speedPicker, saveSpeed, thoughtPicker, saveThought, choice, planTier, button, card, fold, link, notice, downloadButton, input as fieldInput, select as selectField, tag, optionCards, readsLine, stopButton, inset, workState, aiWhere, myLink, WhatsNew, loadWhatsNew, showWhatsNew, whatsNewLink, aiButton, setBusy, aiSide, aiSides } from "../lib.js";
import { withAI } from "../features.js";
import { aiRun } from "./progress.js";
import { remoteServerLine, restrictedModelCard, termsPanel } from "./ai-access.js";
import { localModelHelp } from "./local-model.js";
import { queueSection } from "./queue.js";
import { providerSetup, claudeKeySetup, TIERS, plainProblem } from "./provider-setup.js";
import { agentSetupDialog, cliAdapter, AGENTS } from "./agent-setup.js";
import { allowLine, article } from "./outside-setup.js";
import { storedWhere } from "./provider-setup.js";

// Providers stage 2: Margin's three tiers of work, as Settings names them (providers.TIER_TITLES)
const TIER_TITLE = { small: "Small tasks (labels, links, search words)", middle: "Judging excerpts", strong: "Second opinions and hard cases" };
// how much thought, in its help mark: on Claude's own models, and on another provider's three tiers
const THOUGHT_ABOUT = "Balanced uses the recommended model for each kind of task (labels on Haiku, checks on Sonnet, second opinions on Opus). Energy efficient starts each kind one model lower (never below Sonnet for judging excerpts), Intelligence one higher, and asks the helpers for low or high effort. An unsure answer always goes to a stronger model.";
const THOUGHT_ABOUT_OTHER = "Balanced uses the recommended model for each kind of task (the small one for labels and links, the middle one for judging excerpts, the strong one for second opinions). Energy efficient starts each kind one model lower (never below the middle one for judging excerpts), Intelligence one higher, and asks for low or high reasoning effort where the model takes one. An unsure answer always goes to a stronger model.";
// each cloud provider's one line on its option card
const PROVIDER_TEXT = {
  openai: "GPT models, from OpenAI’s API platform. A ChatGPT plan does not pay for it.",
  gemini: "Gemini models, from Google AI Studio. A free tier to start, with Google’s terms for it.",
  mistral: "Mistral’s own models, from a French company. Needs a plan with API access.",
  azure: "OpenAI’s models in your institution’s Microsoft Azure subscription.",
  openrouter: "Many companies’ models with one key and one balance of credits.",
};

const rerender = () => window.dispatchEvent(new HashChangeEvent("hashchange"));

// Providers stage 2: the agents on a person's own plan, as the Subscription card and the first run offer them. `box`:
// the provider's name as the Documents page's tick boxes show it. Claude Code is the recommendation; Antigravity the
// one for a person without a paid plan (Claude Code is not offered on Claude's free plan; Antigravity runs on a free
// personal Google account, on Gemini 3.8 Flash only).
export const AGENT_CHOICE = {
  claude_code: { title: "Claude Code", plan: "Your Claude plan (Pro, Max, Ultra, Team or Enterprise)", company: "Anthropic", box: "Anthropic (Claude)", tag: "Recommended" },
  codex: { title: "Codex", plan: "Your ChatGPT plan (Plus, Pro, Business)", company: "OpenAI", box: "OpenAI",
    // what its maker does with the text on that kind of account (checked on its pages, 18 November 2026)
    terms: "On ChatGPT Plus or Pro, OpenAI may use what Codex reads to improve its models unless Improve the model for everyone is off in ChatGPT’s Data controls; Business, Edu and Enterprise plans are not used for that by default.",
    foot: "may train its models on Plus or Pro unless you switch that off" },
  antigravity: { title: "Antigravity", plan: "Your Google account, free or paid. Free: every task on Gemini 3.8 Flash.", company: "Google", box: "Google Gemini", tag: "Recommended on a free plan",
    terms: "On a personal Google account, Google may use what Antigravity reads to improve its products while the Enable Telemetry setting is on (in Antigravity’s settings). Switch it off before you use it for research documents: the set-up says where.",
    foot: "may improve its products from it while Telemetry is on" },
};
// the honest state of the agent CLIs (docs/manual/other-agents.md says the same)
const untried = (title) => `Built from ${title}’s documentation and not yet tried with real accounts, nor measured with Margin.`;

// Whether the open project is shared with a team: only Anthropic may read a shared project's documents (privacy.md)
async function projectShared() {
  if (!App.project) return false;
  try { const r = await api("GET", `/api/projects/${P(App.project)}`); return !!((r && r.ai_access) || {}).shared; } catch (_) { return false; }
}
const sharedLine = (who) => h("p", { class: "small", id: "consent-shared" }, `This project is shared with a team: only Anthropic may read its documents, so ${who} reads none of them here.`);

// The yes-first dialog of Codex or Antigravity (as Claude Code's): what is sent where, the maker's terms, which
// documents, the honest state. `stay`: the words of the way out. Resolves true for yes. Used by Settings and the first run.
export async function agentConsent(key, { stay = "Keep the AI on this computer" } = {}) {
  const a = AGENTS[key], c = AGENT_CHOICE[key];
  const shared = await projectShared();
  return !!(await dialog({
    title: `Let ${a.title} read the excerpts, on ${a.plan}?`,
    body: h("div", {}, h("p", {}, `The AI buttons of Margin then prepare tasks; ${a.title} answers them, started by Margin when you press Start ${a.title}.`),
      h("p", {}, h("strong", {}, `The passages inside the tasks ${a.title} takes are sent to ${a.company}.`), " Your documents, results and reviews stay on this computer, and every answer is checked here against the text."),
      h("p", {}, h("strong", {}, c.terms)),
      h("p", {}, h("strong", {}, `Only documents that allow ${c.box} are sent.`), ` Every document allows Anthropic only until you tick ${c.box} for it on the Documents page; the others wait for another AI, or for you.`),
      shared ? sharedLine(a.title) : null,
      h("p", { class: "muted small" }, `Margin never sees your login and never runs on anyone else’s plan. ${untried(a.title)}`)),
    actions: [{ text: stay, value: false, id: "dlg-safe" }, { text: `Use ${a.title}`, value: true, primary: true }],
  }));
}

// 0.9: Settings as five flat tabs (no section folded inside another). Old links to a section (#/settings/second,
// #/settings/calibration…) open its tab and scroll to it.
// the AI tab wears the icon of the sidebar's AI line (where text goes): the chip is the AI mark's only (DESIGN.md 3.3)
const TABS = [["model", "AI", "cloud"], ["basics", "Checking", "flask"], ["explore", "Exploring", "network"], ["documents", "Documents", "book-open"], ["advanced", "Technical", "sliders"]];
const TAB_OF = { model: "model", ai: "model", speed: "model", queue: "model", basics: "basics", calibration: "basics", notify: "basics", explore: "explore", frameworks: "explore", documents: "documents", ocr: "documents", embeddings: "documents",
  advanced: "advanced", routing: "advanced", second: "advanced", context: "advanced", repeatable: "advanced", test: "advanced", updates: "advanced", data: "advanced", link: "advanced" };

export async function renderSettings(view, [section]) {
  const s = { ...App.settings() };
  const tab = TAB_OF[section] || "model";
  const watchers = [];   // the jobs this page follows (the model test, installing Claude Code): stopped when it is left
  let servers = [], info = { servers: [], suggested: [] };
  if (tab === "model" || tab === "advanced" || tab === "documents") {
    try { info = await api("GET", "/api/servers"); servers = info.servers || []; } catch (_) { servers = []; }
  }
  // the version is a link (to Updates): it sits in the line under the title, since a page head's right holds only
  // actions (docs/DESIGN.md 4.14)
  view.appendChild(pageHead("Settings", { sub: [{
    model: "Which AI reads your documents: an AI on a plan you already have (Claude Code, Codex or Antigravity), a model on this computer, or none.",
    basics: "How strict a check is, how new checks start, and when you hear that work has finished.",
    explore: "The defaults of the Profile and Themes pages, and your codebooks.",
    documents: "Reading scanned PDFs, and search by meaning.",
    advanced: "For whoever installs the app. Most people never change anything here.",
  }[tab], " ", versionTag()] }));
  view.appendChild(tabs({ label: "Settings", current: tab,
    items: TABS.map(([id, label, ic]) => [id, label, `#/settings/${id}`, id === "model" ? App.privacy().icon || ic : ic]) }));
  const main = h("div", { class: "stack set-main" });
  view.appendChild(main);
  if (tab === "model") {
    main.append(modelSection(s, servers, watchers, info));
    // 0.11: who reads the documents marked Only a local AI, and what happens to the text Claude reads
    if (!(App.state && App.state.local_only)) main.append(restrictedModelCard(s, servers, save, info));
    if (s.backend === "anthropic") main.append(sectionCard("terms", "Your Claude account and your documents", "", termsPanel({ account: "commercial" })));
    main.append(queueSection());   // 0.17.0: what waits for Claude Code (the sidebar's status area links here)
  }
  else if (tab === "basics") main.append(basicsSection(s), notifySection(s));
  else if (tab === "explore") main.append(exploreSection(s), frameworksSection());
  else if (tab === "documents") main.append(sectionCard("ocr", "Reading scanned PDFs", "", ocrBlock(s)), embedSection(s, servers, info));
  else {
    // a local model's own settings (second model, context length) only when a local model answers
    const local = ["auto", "ollama", "openai"].includes(s.backend || "auto");
    main.append(...[routingSection(s, servers), local ? secondModelSection(s, servers) : null, local ? contextSection(s) : null, reproSection(s), testSection(s, watchers), ledgerSection(), updatesSection(), linkSection(), dataSection()].filter(Boolean));
    if (!local) main.appendChild(h("p", { class: "muted small" }, icon("info", { size: 13 }), " The settings of a model on this computer (the model for second opinions, the context length) show here when a local model is chosen under AI."));
  }
  // a link to one setting (#/settings/speed): it comes into view clear of the top bar, and its control takes the focus
  if (section && section !== tab) setTimeout(() => {
    const t = document.getElementById(`s-${section}`); if (!t) return;
    t.scrollIntoView({ block: "start" });
    const c = t.querySelector('[aria-checked="true"]') || t.querySelector("input, select, textarea, button"); if (c) c.focus({ preventScroll: true });
  }, 80);
  return () => watchers.forEach((w) => w.stop());
}

// ---------------------------------------------------------------------------------------------
function basicsSection(s) {
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const strictState = h("span", { class: "save-state", "aria-live": "polite" });
  const thr = rangeControl("How sure the AI must be before a judgement counts", { min: 0.3, max: 0.95, step: 0.05, value: s.threshold ?? 0.6, format: (v) => `${strictness(v)} (${Math.round(Number(v) * 100)}%)`, ends: ["relaxed", "strict"], help: "The AI says how sure it is of each judgement; 60% means it said it was at least 60% sure. Judgements below this are shown but not counted. Your own judgements always count. Changing this updates all results, old and new." });
  const changes = h("div", { "aria-live": "polite" });
  async function reportChanges(oldT, newT) {
    if (!App.project) return;
    try {
      const [a, b] = await Promise.all([api("GET", `/api/projects/${P(App.project)}/hypotheses?threshold=${oldT}`), api("GET", `/api/projects/${P(App.project)}/hypotheses?threshold=${newT}`)]);
      const before = new Map((a.hypotheses || []).map((x) => [x.hyp_id, x]));
      const rows = (b.hypotheses || []).filter((x) => before.has(x.hyp_id));
      const counts = (x) => `${x.supports || 0} support, ${x.partly || 0} partly, ${x.refutes || 0} contradict, ${x.uncounted || 0} too uncertain`;
      const answerDiff = rows.filter((x) => before.get(x.hyp_id).status !== x.status);
      const countDiff = rows.filter((x) => before.get(x.hyp_id).status === x.status && counts(before.get(x.hyp_id)) !== counts(x));
      const item = (x, withStatus) => h("li", {}, link({ kind: "title", serif: true, href: `#/h/${encodeURIComponent(x.hyp_id)}` }, x.text || x.claim), " ",
        withStatus ? [statusBadge(before.get(x.hyp_id).status, { short: true }), " → ", statusBadge(x.status, { short: true }), " "] : null,
        h("span", { class: "muted small" }, `(${counts(before.get(x.hyp_id))} → ${counts(x)})`));
      const bits = [];
      if (answerDiff.length) bits.push(h("p", {}, h("strong", {}, `${answerDiff.length} ${answerDiff.length === 1 ? "answer" : "answers"} changed:`)), h("ul", { class: "changes-list" }, answerDiff.map((x) => item(x, true))));
      else bits.push(h("p", {}, h("strong", {}, "No answer changed"), countDiff.length ? `, but in ${countDiff.length} ${countDiff.length === 1 ? "result" : "results"} a different number of excerpts counts now:` : "."));
      if (countDiff.length) bits.push(answerDiff.length ? h("p", { class: "set-count-diff" }, `In ${countDiff.length} more ${countDiff.length === 1 ? "result" : "results"} the answer stayed, but a different number of excerpts counts now:`) : null, h("ul", { class: "changes-list" }, countDiff.map((x) => item(x, false))));
      replace(changes, notice({ kind: answerDiff.length ? "info" : "done", class: "set-changes-notice" }, bits));
    } catch (e) { showError(e); }
  }
  // strictness saves on release and reports what changed
  let savingStrict = false;
  async function saveStrict(newT) {
    if (savingStrict) return;
    savingStrict = true;
    const oldT = App.settings().threshold ?? 0.6;
    try {
      if (Math.abs(oldT - newT) > 1e-9) {
        await save({ threshold: newT }, strictState);
        strictState.textContent = `Saved: all results now count judgements the AI was at least ${Math.round(newT * 100)}% sure of.`;
        await reportChanges(oldT, newT);
        loadCalibration();
      } else strictState.textContent = "Saved.";
    } catch (_) { /* shown */ }
    savingStrict = false;
  }
  thr.input.addEventListener("change", () => saveStrict(thr.input.valueAsNumber));
  const backBtn = button({ sm: true, onClick: () => { thr.input.value = 0.6; thr.input.dispatchEvent(new Event("input", { bubbles: true })); saveStrict(0.6); } }, "Back to normal (60%)");
  const k = rangeControl("How many excerpts the AI reads per check", { min: 1, max: 20, step: 1, value: s.k ?? 8, help: "More finds more evidence but takes longer." });
  const perDoc = rangeControl("At most this many from one document", { min: 1, max: 10, step: 1, value: s.per_doc ?? 2 });
  const expand = switchControl("Also search for other words (synonyms)", !!s.expand, { help: "The AI suggests other words your documents might use." });
  const decompose = switchControl("Check each part of a hypothesis separately", !!s.decompose, { help: "For hypotheses with several claims in one sentence." });
  const calibration = h("div", { class: "calibration", id: "s-calibration", "aria-live": "polite" });
  const useSuggestion = (t) => { thr.input.value = t; thr.input.dispatchEvent(new Event("input", { bubbles: true })); saveStrict(t); };
  const strictForm = h("div", {},
    thr,
    notice({ kind: "attention", class: "set-certainty-note" }, "The AI's certainty is its own estimate, not a check of whether it is right. A stricter setting counts fewer judgements, but can still count wrong ones. Reading the excerpts and judging them yourself is the reliable check."),
    h("div", { class: "save-row" }, backBtn, h("span", { class: "muted small" }, "Saved as soon as you let go of the slider."), strictState),
    changes,
    calibration);
  const loadCalibration = async () => {
    if (!App.project) { clear(calibration); return; }
    try { replace(calibration, calibrationBlock(await api("GET", `/api/projects/${P(App.project)}/calibration`), useSuggestion)); }
    catch (e) { clear(calibration); }
    // linked to from a result ("how often you agree"): the block is loaded after the page, so scroll to it now
    if (/#\/settings\/calibration$/.test(location.hash)) { calibration.scrollIntoView({ block: "start" }); const t = calibration.querySelector(".cal-title"); if (t) { t.setAttribute("tabindex", "-1"); t.focus(); } }
  };
  loadCalibration();
  const saveDefaults = async () => { try { await save({ k: k.input.valueAsNumber, per_doc: perDoc.input.valueAsNumber, expand: expand.input.checked, decompose: decompose.input.checked }, state); } catch (_) { /* shown */ } };
  for (const c of [k.input, perDoc.input, expand.input, decompose.input]) c.addEventListener("change", saveDefaults);
  const form = h("div", {},
    h("div", { class: "fields-2" }, h("div", {}, expand, decompose), h("div", {}, k, perDoc)),
    h("div", { class: "save-row" }, h("span", { class: "muted small" }, "Saved as soon as you change something. New checks start with these; each check can still change them under More options."), state));
  return sectionCard("basics", "Checking hypotheses", "",
    h("h3", { class: "set-strict-title" }, "Strictness"),
    strictForm,
    h("h3", { class: "set-start-title" }, "How new checks start"),
    form);
}

// After 0.19.7: a notification from the computer when work the person started has finished (gui/notify.py), so the
// browser can be closed while a local model works. Saved when picked; a test sends one now.
function notifySection(s) {
  const name = appName();
  const st = h("span", { class: "save-state", "aria-live": "polite" });
  const pick = async (v) => { try { await save({ notify: v }, st); s.notify = v; } catch (_) { /* shown */ } };
  const when = choice({ sm: true, label: "When to tell you", value: s.notify || "away",
    options: [["away", `When ${name} is not in front`], ["always", "Always"], ["off", "Never"]], onPick: pick });
  const out = h("div", { "aria-live": "polite" });
  const test = button({ sm: true, icon: "bell" }, "Send a test notification");
  test.addEventListener("click", async () => {
    test.disabled = true;
    replace(out, h("p", { class: "muted small" }, "Sending…"));
    try {
      const r = await api("POST", "/api/notify/test");
      replace(out, r.sent
        ? h("p", { class: "small" }, icon("check", { size: 14 }), " Sent. ", r.note)
        : notice({ kind: "attention" }, h("p", {}, h("strong", {}, "The notification could not be sent.")),
          h("p", { class: "small" }, r.problem || ""), h("p", { class: "small" }, r.note)));
    } catch (e) { clear(out); showError(e); }
    test.disabled = false;
  });
  return sectionCard("notify", "When work has finished", `Work you started that took more than 20 seconds (a check, documents being added, your local model answering the queue) can tell you when it has finished, or stopped with a problem, in your computer's own notifications. So you can close the browser while it runs: ${name} keeps working, and a click on the notification opens it again.`,
    h("div", { class: "field" }, h("div", { class: "field-label" }, "Tell me"), h("div", { class: "row" }, when, st),
      h("div", { class: "field-help" }, `When ${name} is not in front: only when no ${name} tab is the one you are looking at (the browser closed, or another window in front). Work ${name} does by itself, such as looking in a shared folder, never sends one.`)),
    h("div", { class: "save-row" }, test), out);
}

// Calibration: how often the person agreed with the AI, by the AI's certainty, as a small bar chart with a text
// equivalent; and the suggested strictness with its reason, when there is enough data.
function calibrationBlock(c, useSuggestion) {
  const bins = c.bins || [];
  const total = c.total || 0;
  const pct = (x) => `${Math.round(x * 100)}%`;
  const box = inset({ class: "cal-box" });
  box.appendChild(h("h4", { class: "cal-title" }, icon("scale", { size: 14 }), " How often you agreed with the AI, by its certainty"));
  if (!total) {
    box.appendChild(h("p", { class: "muted small set-calibration-empty" }, "Nothing to show yet: when you review excerpts (agree with the AI or judge them differently), this shows how often you agreed, for each level of the AI's certainty, and suggests a strictness. ", c.note || ""));
    return box;
  }
  // the chart: one column per band, height = agreement rate; an empty band is drawn as a dashed outline
  const chart = h("div", { class: "cal-chart", role: "img", "aria-label": `Agreement with the AI by its certainty: ${bins.map((b) => `${pct(b.from)} to ${pct(b.to)}: ${b.judged ? `${b.agreed} of ${b.judged} (${pct(b.rate || 0)})` : "none judged"}`).join("; ")}.` });
  const current = c.threshold ?? 0.6;
  for (const b of bins) {
    const rate = b.judged ? (b.rate ?? b.agreed / b.judged) : null;
    const counted = b.from >= current - 1e-9;
    const col = h("div", { class: "cal-col" + (counted ? " cal-counted" : "") },
      h("span", { class: "cal-val" }, rate === null ? "–" : pct(rate)),
      h("div", { class: "cal-bar-wrap" },
        rate === null ? h("div", { class: "cal-bar cal-empty" }) : h("div", { class: "cal-bar", style: { height: `${Math.max(3, Math.round(rate * 100))}%` } })),
      h("div", { class: "cal-lab" }, `${pct(b.from)}–${pct(b.to)}`),
      h("div", { class: "cal-n" }, b.judged ? `${b.agreed} of ${b.judged}` : "none"));
    chart.appendChild(col);
  }
  box.appendChild(chart);
  box.appendChild(h("p", { class: "muted small cal-foot" }, `From the ${total} AI judgements for or against that you reviewed: you agreed with ${c.agreed || 0} (${pct(total ? (c.agreed || 0) / total : 0)}). Bands at or above your strictness (${pct(current)}) are shaded; the number under each bar is how many you agreed with of those you judged.`));
  // text equivalent for screen readers and for anyone who prefers a table
  box.appendChild(fold({}, "As a table",
    h("table", { class: "table cal-table" }, h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "AI certainty"), h("th", { scope: "col", class: "num" }, "You judged"), h("th", { scope: "col", class: "num" }, "You agreed"), h("th", { scope: "col", class: "num" }, "Agreement"))),
      h("tbody", {}, bins.map((b) => h("tr", {}, h("td", {}, `${pct(b.from)} to ${pct(b.to)}`), h("td", { class: "num" }, String(b.judged)), h("td", { class: "num" }, String(b.agreed)), h("td", { class: "num" }, b.judged ? pct(b.rate ?? b.agreed / b.judged) : "–")))))));
  if (c.suggestion && c.suggestion.threshold !== undefined) {
    const t = Number(c.suggestion.threshold);
    const same = Math.abs(t - current) < 1e-9;
    box.appendChild(notice({ kind: same ? "done" : "info", class: "set-suggest-notice" }, h("p", {}, h("strong", {}, same ? `Your strictness (${pct(t)}) fits your reviews. ` : `Suggested strictness: ${pct(t)}. `), c.suggestion.reason || ""),
      same ? null : button({ kind: "main", sm: true, class: "set-suggest-btn", onClick: () => useSuggestion(t) }, `Use ${pct(t)}`)));
  } else if (c.note) {
    box.appendChild(h("p", { class: "muted small set-calibration-note" }, icon("info", { size: 12 }), " ", c.note));
  }
  return box;
}

// Reading scanned PDFs: on/off and the languages, with what the computer can do.
function ocrBlock(s) {
  const st = (App.state && App.state.ocr) || {};
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const on = switchControl("Read scanned PDF pages (text recognition)", (s.ocr || "auto") !== "off", { help: "A scanned PDF is a picture of the pages. With text recognition (OCR) the app reads the text on them, on this computer, slowly and with some errors; the Documents page says which documents were read this way." });
  const lang = fieldInput({ type: "text", value: s.ocr_lang || "eng", placeholder: "eng", maxlength: 60, class: "set-lang" });
  const installed = st.languages && st.languages.length ? st.languages : [];
  const langField = field("Languages of the scanned documents", lang, { help: `Three-letter codes, joined with +, for example eng+nld for English and Dutch.${installed.length ? ` Installed on this computer: ${installed.join(", ")}.` : ""}` });
  const saveOcr = async () => { try { await save({ ocr: on.input.checked ? "auto" : "off", ocr_lang: lang.value.trim() || "eng" }, state); } catch (_) { /* shown */ } };
  on.input.addEventListener("change", saveOcr);
  lang.addEventListener("change", saveOcr);
  const box = h("div", {});
  if (st.available === false) {
    box.appendChild(notice({ kind: "attention", class: "set-ocr-notice" }, h("p", {}, h("strong", {}, "To read scanned PDFs, install Tesseract."), " Until then, scanned pages stay without text and a wholly scanned PDF cannot be added."),
      st.install ? tesseractHelp(st) : h("p", { class: "small" }, "What is missing is listed under Settings → Technical.")));
  } else if (st.available) {
    box.appendChild(h("p", { class: "muted small set-ocr-ok" }, icon("check", { size: 13 }), " Text recognition is installed on this computer."));
  }
  box.append(on, langField, h("div", { class: "save-row" }, h("span", { class: "muted small" }, "Saved as soon as you change something. Applies to documents added from now on."), state));
  return box;
}

// A plain reading of the model test, with the technical lines folded away.
export function plainTestResult(r) {
  const ok = r.ok && r.model_available;
  const emb = r.embedding;
  return h("div", { class: "stack set-test-result" },
    notice({ kind: ok ? "done" : "attention" }, h("p", {}, h("strong", {}, ok ? "Working. " : "Not quite. "), ok ? "The AI model answered. Checks can run." : (r.model_available === false ? "The service runs, but the chosen model is not installed on it." : "The AI model did not answer as expected.")),
      emb ? h("p", { class: "small" }, emb.ok ? "Search by meaning is working too." : "Search by meaning is not working: documents are searched by their words only.") : null,
      r.warning ? h("p", { class: "small" }, r.warning) : null,
      fold({}, "Technical details", testResult(r))));
}

function sectionCard(id, title, lead, ...children) {
  return card({ class: "settings-section", id: `s-${id}`, "aria-labelledby": `s-${id}-h` },
    h("h2", { id: `s-${id}-h`, tabindex: "-1" }, title), lead ? h("p", { class: "lead" }, lead) : null, ...children);
}

async function save(changes, stateEl) {
  if (stateEl) stateEl.textContent = "Saving…";
  try {
    const r = await api("PUT", "/api/settings", changes);
    App.state.settings = r.settings;
    App.state.backend_label = r.backend_label;
    if (r.providers) App.state.providers = r.providers;   // which cloud providers are set up (the Documents page's words)
    for (const fn of App.listeners) fn(App.state);
    if (stateEl) stateEl.textContent = "Saved.";
    return r;
  } catch (e) {
    if (stateEl) stateEl.textContent = "";
    showError(e);
    throw e;
  }
}

// ---------------------------------------------------------------------------------------------
function modelSection(s, servers, watchers, info = { servers }) {
  const localOnly = !!(App.state && App.state.local_only);
  let allowCC = !!s.allow_claude_code;
  const allowAgent = Object.fromEntries(Object.keys(AGENTS).map((r) => [r, !!s[`allow_${r}`]]));   // Codex, Antigravity
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const detail = h("div", {});
  let backend = s.backend || "auto";
  const isLocal = (b) => ["auto", "ollama", "openai"].includes(b);
  const allowCloud = switchControl("Allow cloud models", !!s.allow_cloud, { help: "" });
  const cloudBox = inset({ class: "cloud-box" }, allowCloud, aiWhere("With the Claude API the hypothesis and the excerpts read leave this computer and are billed to the key.", "cloud"));

  // 0.9: subscription first. Providers stage 2 (the owner's layout, 18 November 2026): two rows, "Subscription" and
  // "Local model" half wide, then the three others. "Subscription" holds the agents on the person's own plan (Claude
  // Code, Codex, Antigravity), chosen inside its detail; the saved backend stays the agent's route.
  const AGENT_ROUTES = ["claude_code", "codex", "antigravity"];
  // the agent the Subscription card stands for: the saved one, else the one last chosen here, else Claude Code
  let agent = AGENT_ROUTES.includes(backend) ? backend : (AGENT_ROUTES.includes(store("settings-agent")) ? store("settings-agent") : "claude_code");
  const ROUTES = [
    ["subscription", "Subscription", "cloud", "Recommended", "An AI on a plan you already have: Claude Code, Codex or Antigravity. Margin prepares the work, starts it for you and checks every quote.", "Only the passages inside the tasks go to the company of the plan you choose"],
    ["local", "Local model", "house", "", "Ollama, LM Studio, llama.cpp, Jan or vLLM. Free and fully private; needs a capable computer and judges less well than Claude.", "Nothing leaves this computer"],
    ["baseline", "No AI (demo)", "eye-off", "", "A word-overlap stand-in, to see how the app works. Search, keyword profiles, the glossary and themes work fully without AI.", "Nothing leaves this computer"],
    ["anthropic", "Claude API (team key)", "key", "", "For a shared installation: the Claude API with the team's key, billed per use.", "The excerpts read go to Anthropic"],
    ["cloud_api", "Another cloud provider (API key)", "key", "", "OpenAI, Google Gemini, Mistral, Azure OpenAI or OpenRouter, with your own API key, billed per use. Not yet measured with Margin.", "The excerpts read go to the provider you choose"],
  ];
  const CLOUD_ROUTES = ["subscription", "anthropic", "cloud_api"];
  const routeOf = (b) => (isLocal(b) ? "local" : AGENT_ROUTES.includes(b) ? "subscription" : b);
  // which AI: option cards holding real radio inputs (docs/DESIGN.md 4.7); a pick that needs a yes first goes back
  // to the previous card when the answer is no
  let radiosWrap = null;
  const select = (key) => radiosWrap.set(key);
  // an agent on the person's plan asks first, once (allow_claude_code, allow_codex, allow_antigravity): true when it may
  async function askAgent(key) {
    // the way out says where the AI stays: with the agent in use, if another one is, else on this computer
    const safe = { text: AGENT_ROUTES.includes(backend) && backend !== key ? `Stay with ${AGENT_CHOICE[backend].title}` : "Keep the AI on this computer", value: false, id: "dlg-safe" };
    if (key === "claude_code" && !allowCC) {
      const ok = await dialog({
        title: "Let Claude Code read the excerpts, on your own Claude plan?",
        body: h("div", {}, h("p", {}, "The AI buttons of Margin then prepare tasks; Claude Code answers them, started by Margin when you press Start Claude Code, or by you with /margin-run."),
          h("p", {}, h("strong", {}, "The passages inside the tasks Claude Code takes are sent to Anthropic."), " Your documents, results and reviews stay on this computer, and every answer is checked here against the text."),
          h("p", { class: "muted small" }, "Margin never sees your Claude login and never runs on anyone else's plan.")),
        actions: [safe, { text: "Use Claude Code", value: true, primary: true }],
      });
      if (!ok) return false;
      allowCC = true;
    }
    // Providers stage 2: Codex and Antigravity ask first, as Claude Code does (allow_codex, allow_antigravity)
    if (AGENTS[key] && !allowAgent[key]) {
      if (!(await agentConsent(key, { stay: safe.text }))) return false;
      allowAgent[key] = true;
    }
    return true;
  }
  // The consent is the decision: once an agent may read, the route and its allow are saved at once, so the sidebar and
  // every Start follow (no "ready" beside a route that is not saved yet). false when it could not be saved.
  async function useAgent(key) {
    try {
      await save({ backend: key, [`allow_${key}`]: true }, state);
      Object.assign(s, App.settings());
    } catch (_) { return false; }   // shown by save()
    backend = agent = key;
    store("settings-agent", key);
    return true;
  }
  const onRoute = async (key) => {
    const prev = routeOf(backend);
    if (key === "subscription") {
      if (!(await askAgent(agent))) { select(prev); return; }
      if (!(await useAgent(agent))) { select(prev); return; }
      rerender();   // the whole page: the queue's section and every word below follow the saved agent
      return;
    }
    if (key === "anthropic" && prev !== "anthropic") {
      const ok = await dialog({
        title: "Use the Claude API with a team key?",
        body: h("div", {}, h("p", {}, "With the Claude API, the hypothesis and the excerpts of your documents that the AI reads are sent to Anthropic's servers, and the use is billed to an account key."),
          h("p", { class: "muted small" }, "For one researcher, Claude Code on your own plan is simpler. Nothing is sent before you also switch on “Allow cloud models”, enter a key and save.")),
        actions: [{ text: "Back", value: false, primary: true, id: "dlg-safe" }, { text: "Continue with the Claude API", value: true }],
        onOpen(dlg) { const b = dlg.querySelector("#dlg-safe"); if (b) b.focus(); },
      });
      if (!ok) { select(prev); return; }
    }
    if (key === "cloud_api" && prev !== "cloud_api") {
      const shared = await projectShared();
      const ok = await dialog({
        title: "Use another cloud provider with your API key?",
        body: h("div", {}, h("p", {}, "The hypothesis and the excerpts the AI reads are then sent to the provider you choose below (OpenAI, Google, Mistral, Microsoft or OpenRouter), and the use is billed to your key."),
          h("p", {}, h("strong", {}, "Only documents that allow that provider are sent."), " Every document allows Anthropic only until you tick another provider for it on the Documents page; the others are read by your local model, or wait for you."),
          shared ? sharedLine("that provider") : null,
          h("p", { class: "muted small" }, "Nothing is sent before you also switch on “Allow cloud models”, store a key and save. Margin's models and settings were measured with Claude only.")),
        actions: [{ text: "Back", value: false, primary: true, id: "dlg-safe" }, { text: "Continue with another provider", value: true }],
        onOpen(dlg) { const b = dlg.querySelector("#dlg-safe"); if (b) b.focus(); },
      });
      if (!ok) { select(prev); return; }
    }
    backend = key === "local" ? (isLocal(s.backend) ? s.backend : "auto") : key;
    drawDetail();
  };
  radiosWrap = optionCards({ name: "route", class: localOnly ? "route-cards route-cards-few" : "route-cards", label: "Which AI reads the documents", value: routeOf(backend), onPick: onRoute,
    options: ROUTES.filter(([key]) => !(localOnly && CLOUD_ROUTES.includes(key))).map(([key, title, ic, badge, sub, where]) => ({
      value: key, title, icon: ic, tag: badge || null, text: sub,
      foot: [icon(CLOUD_ROUTES.includes(key) ? "cloud" : "house", { size: 12 }), where] })) });
  const lockedLine = localOnly ? h("p", { class: "muted small" }, icon("house", { size: 13 }), " Cloud models are switched off on this computer by whoever installed Margin.") : null;
  // which local server (the three local routes of 0.8, as one choice)
  const localKind = () => {
    const sel = selectField({}, [["auto", "Automatic: the first server found"], ["ollama", "Ollama"], ["openai", "LM Studio, llama.cpp, Jan, vLLM (OpenAI-compatible)"]].map(([v, t]) => h("option", { value: v, selected: backend === v }, t)));
    sel.addEventListener("change", () => { backend = sel.value; drawDetail(); });
    return field("Local model server", sel);
  };

  const ollamaSrv = servers.find((x) => x.kind === "ollama");
  const openaiSrv = servers.find((x) => x.kind !== "ollama");
  const fields = {};
  const modelPicker = (id, current, models, placeholder) => {
    const wrap = h("div", { class: "field" });
    const sel = selectField({ id });
    const txt = fieldInput({ type: "text", id: id + "-txt", value: current || "", placeholder, "aria-label": "Chat model, typed" });
    if (models && models.length) {
      sel.appendChild(h("option", { value: "" }, "Choose a model…"));
      for (const m of models) sel.appendChild(h("option", { value: m, selected: m === current }, m));
      if (current && !models.includes(current)) sel.appendChild(h("option", { value: current, selected: true }, `${current} (not installed)`));
      sel.appendChild(h("option", { value: "__other" }, "Other (type a name)…"));
      sel.addEventListener("change", () => { txt.hidden = sel.value !== "__other"; if (sel.value === "__other") txt.focus(); });
      txt.hidden = true;
      wrap.append(h("label", { class: "field-label", for: id }, "Chat model"), sel, txt);
      wrap.value = () => (sel.value === "__other" ? txt.value.trim() : sel.value);
    } else {
      wrap.append(h("label", { class: "field-label", for: id + "-txt" }, "Chat model"), txt, h("div", { class: "field-help" }, "No server answered just now, so the installed models could not be listed. Type the model name."));
      wrap.value = () => txt.value.trim();
    }
    return wrap;
  };

  function serverList() {
    // 0.13.7: no model yet: how to get Ollama (noticed when it starts), or one button that downloads a model into it
    const help = localModelHelp(info, {
      use: "ai",   // chosen by the app when the download is done
      onFound: rerender,
      onReady: async (r) => {
        try { await App.refresh(); } catch (_) { /* shown on the page */ }
        toast(r.chosen ? `${r.chat} reads your documents now, on this computer.` : `${r.chat} is downloaded: choose it below.`, "ok");
        rerender();
      },
    });
    const list = servers.length ? h("div", { class: "server-list" }, servers.map((sv) => inset({ class: "server small" }, icon("check", { size: 14 }),
      h("div", {}, h("strong", {}, sv.kind === "ollama" ? `Ollama ${sv.version || ""}` : `OpenAI-compatible server`), h("span", { class: "muted" }, ` at ${sv.url}`),
        h("div", { class: "sv-models" }, `Chat: ${(sv.chat_models || []).join(", ") || "none"} · Embedding: ${(sv.embedding_models || []).join(", ") || "none"}`))))) : null;
    return help ? h("div", { class: "stack" }, list, help) : list;
  }

  function drawDetail() {
    clear(detail);
    fields.ollama_url = fieldInput({ mono: true, type: "url", value: s.ollama_url || "", placeholder: "http://localhost:11434" });
    fields.openai_url = fieldInput({ mono: true, type: "url", value: s.openai_url || "", placeholder: "http://localhost:1234/v1" });
    fields.anthropic_model = fieldInput({ mono: true, type: "text", value: s.anthropic_model || "", placeholder: "claude-opus-5-5" });
    fields.think = selectField({}, [["off", "Off (fastest)"], ["judging", "Only when judging excerpts"], ["on", "On for every step"], ["default", "Model's default"]].map(([v, t]) => h("option", { value: v, selected: (s.think || "default") === v }, t)));
    fields.think_budget = fieldInput({ type: "number", min: 0, max: 16384, step: 250, value: s.think_budget ?? 1500, "aria-label": "Reasoning budget in tokens" });
    const budgetHelp = () => {
      const n = Number(fields.think_budget.value) || 0;
      return n ? `The AI reasons for at most about ${n.toLocaleString()} tokens, then answers from its notes: at 20 tokens a second that is about ${Math.round(n / 20 / 60 * 10) / 10 || "<1"} min of reasoning per call. 0 = no limit (can take very long).` : "No limit: a reasoning model can take many minutes per call.";
    };
    const budgetNote = h("div", { class: "field-help" }, budgetHelp());
    fields.think_budget.addEventListener("input", () => { budgetNote.textContent = budgetHelp(); });
    const thinkRow = () => h("div", { class: "fields-2" },
      field("Reasoning (thinking models only)", fields.think, { help: "Reasoning can make judgements more careful but makes each check slower. “Only when judging excerpts” reasons where it can help and not for search words or splitting a hypothesis. Test it before relying on it (Test a model, with reasoning on and off)." }),
      h("div", { class: "field" }, h("label", { class: "field-label" }, "Reasoning budget (tokens)", fields.think_budget), budgetNote));
    if (isLocal(backend)) detail.append(localKind());
    // a model server on another computer: it reads only the documents allowed to it (one line, no pop-up)
    if (isLocal(backend) && backend === (s.backend || "auto") && remoteServerLine(null)) {
      const farBox = h("div", {}, remoteServerLine(null));
      detail.append(farBox);
      const project = App.state && App.state.project;
      if (project) api("GET", `/api/projects/${encodeURIComponent(project)}`).then((r) => {
        const line = remoteServerLine(project, (r && r.ai_access) || {}, () => replace(farBox, remoteServerLine(project, { providers_default: [...((r.ai_access || {}).providers_default || ["anthropic"]), App.state.providers.route] })));
        if (line) replace(farBox, line);
      }).catch(() => { /* the line without the button stays */ });
    }
    if (backend === "auto") {
      detail.append(serverList(), h("p", { class: "muted small" }, "The first server found is used. If a chat model is named below for Ollama or an OpenAI-compatible server, it is preferred when that server has it."),
        fields.ollamaModel = modelPicker("m-ollama", s.ollama_model, ollamaSrv ? ollamaSrv.chat_models : [], "e.g. qwen3:8b"), thinkRow());
      fields.ollamaModel.querySelector(".field-label").textContent = "Preferred Ollama model";
    } else if (backend === "ollama") {
      detail.append(serverList(), h("div", { class: "fields-2" }, field("Ollama address", fields.ollama_url), fields.ollamaModel = modelPicker("m-ollama", s.ollama_model, ollamaSrv ? ollamaSrv.chat_models : [], "e.g. qwen3:8b")),
        thinkRow(), h("p", { class: "muted small" }, "Context length: set automatically; see Settings → Technical."));
    } else if (backend === "openai") {
      detail.append(serverList(), h("div", { class: "fields-2" }, field("Server address", fields.openai_url, { help: "The /v1 base URL of LM Studio, llama.cpp, Jan, vLLM…" }), fields.openaiModel = modelPicker("m-openai", s.openai_model, openaiSrv ? openaiSrv.chat_models : [], "leave empty for the first model listed")));
    } else if (backend === "anthropic") {
      detail.append(cloudBox, claudeApiCard(), field("Stronger model", fields.anthropic_model, { help: "For example claude-opus-5-5: a task an AI model was unsure of goes to it once. Checks start on Sonnet; each kind of task has its own model (“AI model per task” under Technical)." }),
        thoughtField("Which Claude models answer each kind of task, and how hard they think. ", THOUGHT_ABOUT), fableSwitch(), agreeBox());
    } else if (backend === "cloud_api") {
      detail.append(cloudProviderBox());
    } else if (backend === "claude_code") {
      detail.append(agentChoice(), claudeCodeBox(), fableSwitch());
    } else if (AGENTS[backend]) {
      detail.append(agentChoice(), agentBox(backend));
    } else {
      detail.append(notice({ kind: "info" }, h("p", {}, "The offline demo grades passages by word overlap, without a model. It shows how the app works; its results are not findings.")));
    }
  }

  // Which agent of the Subscription card: Claude Code (the default), Codex or Antigravity, each naming where the passages
  // go. Codex and Antigravity ask first, as Claude Code does; a no puts the choice back.
  function agentChoice() {
    const cards = optionCards({ class: "agent-choice", id: "agent-choice", label: "Subscription: whose plan", value: backend,
      options: AGENT_ROUTES.map((r) => ({ value: r, title: AGENT_CHOICE[r].title, text: AGENT_CHOICE[r].plan, tag: AGENT_CHOICE[r].tag || null,
        foot: [icon("cloud", { size: 12 }), `The passages go to ${AGENT_CHOICE[r].company}${AGENT_CHOICE[r].foot ? `, which ${AGENT_CHOICE[r].foot}` : ""}`] })),
      onPick: async (v) => {
        if (v === backend) return;
        if (!(await askAgent(v)) || !(await useAgent(v))) { cards.set(backend); return; }
        rerender();   // the whole page follows the saved agent: the queue section, its Start, /margin-run
      } });
    // an inset under the route picker, so it reads as part of the Subscription card and not as a second picker
    return inset({ class: "set-agent-choice agent-choice-box" }, h("div", { class: "field-label" }, "Subscription: whose plan"), cards);
  }

  function fableSwitch() {
    const free = s.backend === "claude_code" && planTier(s) === "free";  // 0.13.10: no Opus or Fable on a Free plan
    fields.use_fable = switchControl("Let the auditor use Fable", !!s.use_fable, { help: [free ? "On your Free plan the auditor runs on Sonnet, so this changes nothing there." : "It runs on Opus unless this is on; Fable can be billed from usage credits.",   // 0.13.3: one line, the rest in its help mark
      helpMark("About the auditor", "The auditor gives second opinions (shown for comparison only) and is the stronger model that reads the hard cases again (unsure judgements, rejected quotes, “Ask a stronger model”; its reading replaces the first). It runs on Opus unless this is on. In Claude Code, Fable can be billed from usage credits instead of your plan's limits; the model picker then says “Requires usage credits”.")] });
    // 0.14.3: this switch saves when it is changed, like the speed picker beside it (it looked saved and was not)
    const sw = fields.use_fable, st = h("span", { class: "save-state", "aria-live": "polite" });
    sw.appendChild(st);
    sw.input.addEventListener("change", async () => {
      const on = sw.input.checked;
      try { await save({ use_fable: on }, st); s.use_fable = on; }
      catch (_) { sw.input.checked = !on; sw.input.setAttribute("aria-checked", sw.input.checked ? "true" : "false"); }
    });
    return sw;
  }

  // Claude Code (0.9): a checklist of what is ready, one button that sets up what is not, and how a run starts.
  // 0.13.10: how fast it works (helpers at once), saved when picked, as beside every Start Claude Code.
  function claudeCodeBox() {
    const st = h("span", { class: "save-state", "aria-live": "polite" });
    const speed = speedPicker(s.claude_speed, undefined, async (v) => {
      st.textContent = "Saving…";
      try { await saveSpeed(v); s.claude_speed = v; st.textContent = "Saved."; } catch (e) { st.textContent = ""; throw e; }
    }, { label: null });
    return h("div", { class: "stack set-claude-code-box" }, claudeSetupCard({ watchers, kind: "standard" }),
      // 0.18.1 (N2): how much thought, also beside every Start Claude Code (the same kept setting)
      thoughtField("Which Claude models answer each kind of task, and how hard they think. It is also beside every Start Claude Code. Models you choose per task below come first; a local model keeps its own choice. ", THOUGHT_ABOUT),
      h("div", { class: "field", id: "s-speed" }, h("div", { class: "field-label" }, "Helpers at once"), h("div", { class: "row" }, speed, st),
        h("div", { class: "field-help" }, "How many helpers Claude Code starts at once when you press Start Claude Code. More is done sooner and uses your plan's limits faster. ",
          helpMark("About the helpers", "Claude Code hands the work to helpers, each for one kind of task on its own model. Slower runs one at a time, Normal two, Faster four. Beside Start Claude Code, “Choose the helpers for this run” sets how many of each helper work at once, for one run."))),
      mixBox(), agreeBox());
  }

  // How much thought (0.18.1, N2): one kept setting for every route on the haiku/sonnet/opus ladder (Claude Code, the
  // Claude API, Codex, Antigravity, another cloud provider: providers stage 2). Saved when picked.
  function thoughtField(help, about) {
    const st2 = h("span", { class: "save-state", "aria-live": "polite" });
    const thought = thoughtPicker(s.claude_thought, async (v) => {
      st2.textContent = "Saving…";
      try { await saveThought(v); s.claude_thought = v; st2.textContent = "Saved."; } catch (e) { st2.textContent = ""; throw e; }
    }, { label: null });
    return h("div", { class: "field", id: "s-thought" }, h("div", { class: "field-label" }, "How much thought"), h("div", { class: "row" }, thought, st2),
      h("div", { class: "field-help" }, help, helpMark("About how much thought", about)));
  }

  // Three rows, one per tier (small tasks, judging excerpts, second opinions): the model in use, and whether it is the
  // recommendation or the person's choice. A select from `models` with "Recommended (<id>)" first (its value is empty:
  // the recommendation, so a newer Margin brings newer ones by itself) and "Other (type a name)…" last; `typed`: three
  // text fields instead (Azure's deployment names). `.value()`: {small, middle, strong}.
  const MODELS_LABEL = "Recommended models, applied automatically";
  function modelRows({ id, recommended = {}, chosen = {}, models = [], typed = false }) {
    const ctl = {};
    const rows = TIERS.map((t) => {
      const rec = recommended[t] || "";
      const cur = String(chosen[t] || "").trim();
      const state = h("div", { class: "field-help model-row-state" });
      const txt = fieldInput({ mono: true, sm: !typed, id: `${id}-${t}-txt`, value: cur, placeholder: rec || "a model’s name", "aria-label": `${TIER_TITLE[t]}, typed`, autocomplete: "off", spellcheck: "false" });
      let value, control;
      if (typed) {
        txt.setAttribute("aria-label", TIER_TITLE[t]);
        value = () => txt.value.trim();
        control = txt;
      } else {
        const list = [...new Set(models.filter(Boolean))];
        const sel = selectField({ id: `${id}-${t}`, "aria-label": TIER_TITLE[t] },
          h("option", { value: "", selected: !cur }, rec ? `Recommended (${rec})` : "Recommended"),
          ...list.map((m) => h("option", { value: m, selected: m === cur }, m)),
          ...(cur && !list.includes(cur) ? [h("option", { value: cur, selected: true }, `${cur} (not in the list)`)] : []),
          h("option", { value: "__other" }, "Other (type a name)…"));
        txt.hidden = true;
        sel.addEventListener("change", () => { txt.hidden = sel.value !== "__other"; if (sel.value === "__other") txt.focus(); show(); });
        txt.addEventListener("input", () => show());
        value = () => (sel.value === "__other" ? txt.value.trim() : sel.value);
        control = h("div", { class: "model-row-pick" }, sel, txt);
      }
      const show = () => {
        const v = value();
        // the select says what is in use; only a choice of the person's own is called one
        state.replaceChildren(...[].concat(typed ? (v ? [] : "Empty: another tier’s deployment answers it.") : v ? "Your choice" : []));
      };
      if (typed) txt.addEventListener("input", () => show());
      show();
      ctl[t] = value;
      return h("div", { class: "field model-row" }, h("label", { class: "field-label", for: typed ? `${id}-${t}-txt` : `${id}-${t}` }, TIER_TITLE[t]), control, state);
    });
    const wrap = h("div", { class: "model-rows", id }, rows);
    wrap.pick = () => Object.fromEntries(TIERS.map((t) => [t, ctl[t]()]));
    return wrap;
  }

  // Providers stage 2 (B4): Codex or Antigravity. Its checklist card (found, signed in, Margin added) whose button opens
  // the set-up's guided steps; the helpers at once and how much thought (both kept, as for Claude Code); the models in
  // use per tier, applied from the CLI's recommendations for the plan (GET /api/agent-setup's lineup_in_use; a choice
  // is kept in cli_models when Save is pressed); and that it is not measured yet.
  function agentBox(route) {
    const a = AGENTS[route];
    const modelsHolder = h("div", { class: "field", id: "s-cli-models" });
    const drawModels = (info) => {
      const known = ((App.state && App.state.clis) || []).find((c) => c.id === route) || {};
      const rec = (info && info.recommended) || known.recommended || {};
      if (!Object.values(rec).some(Boolean)) { fields.cliRows = null; replace(modelsHolder); return; }
      const label = h("div", { class: "field-label" }, MODELS_LABEL);
      // the plan decides which models there are: until the program is signed in, Margin has nothing to pick from
      if (!(info && info.status && info.status.signed_in === true)) {
        fields.cliRows = null;
        replace(modelsHolder, label, h("div", { class: "field-help", id: "cli-models-wait" }, `Margin picks them once ${a.title} is signed in.`));
        return;
      }
      const avail = info.status.models_available || [];
      const inUse = info.lineup_in_use || rec;
      const one = TIERS.every((t) => inUse[t]) && new Set(TIERS.map((t) => inUse[t])).size === 1;
      fields.cliRows = modelRows({ id: `m-${route}`, recommended: rec, chosen: (s.cli_models || {})[route] || {}, models: avail.length ? avail : Object.values(rec) });
      fields.cliRoute = route;
      replace(modelsHolder, label,
        h("div", { class: "field-help" }, `From ${a.title}’s recommendations for your plan${avail.length ? ", among the models it lists" : ""}. A newer Margin brings newer ones by itself; choose another only if you need to. Saved with Save.`,
          route === "antigravity" ? " On a free Google account every task uses Gemini 3.8 Flash; Google AI Pro adds Gemini 4 Argon and Hydrogen, Ultra also Gemini 4 Carbon." : ""),
        one ? h("p", { class: "small", id: "cli-models-one" }, "Every task uses ", h("code", {}, inUse.small), "; a second opinion then comes from the same model.") : null,
        fields.cliRows);
    };
    drawModels(null);
    const st = h("span", { class: "save-state", "aria-live": "polite" });
    const speed = speedPicker(s.claude_speed, undefined, async (v) => {
      st.textContent = "Saving…";
      try { await saveSpeed(v); s.claude_speed = v; st.textContent = "Saved."; } catch (e) { st.textContent = ""; throw e; }
    }, { label: null });
    // the order of every AI box: the card, the models, how much thought, the helpers at once
    return h("div", { class: "stack set-claude-code-box set-agent-box" }, agentSetupCard(route, { onInfo: drawModels }),
      modelsHolder,
      thoughtField(`Which ${a.title} models answer each kind of task, and how hard they think. `, THOUGHT_ABOUT_OTHER),
      h("div", { class: "field", id: "s-speed" }, h("div", { class: "field-label" }, "Helpers at once"), h("div", { class: "row" }, speed, st),
        h("div", { class: "field-help" }, `How many helpers Margin starts at once when you press Start ${a.title}. More is done sooner and uses your plan’s limits faster.`)),
      mixBox(a.title),
      allowLine(App.project),
      h("p", { class: "muted small", id: "agent-untried" }, untried(a.title)));
  }

  // 0.18.1 (I5): the local model and Claude answer the same sample of this project's tasks of one kind, and Cohen's
  // kappa says whether the local model is good enough for it. On request only (it uses the plan). Roadmap I5: each
  // finished comparison is kept in the project (this copy only), listed under the box, and set beside the next one.
  function agreeBox() {
    if (!(s.restricted_server && s.restricted_model && (s.backend === "claude_code" || s.backend === "anthropic"))) return null;
    const box = h("div", { class: "field", id: "s-agreement" }, h("div", { class: "field-label" }, "Agreement between routes"));
    const help = h("div", { class: "field-help" }, "Your local model and Claude answer the same sample of your own answered tasks of one kind, and kappa (1 is full agreement, 0 is chance) shows whether the local model is good enough for it. An answer a task already has is reused, so only what is missing is asked. Only documents Claude may read are used. Each finished comparison is kept, dated, in the project on this computer (it does not travel to colleagues), so a later sample can be compared with it. ",
      helpMark("About agreement", "Kappa from 0.8 on is good, from 0.6 fair, below that poor. Agreement is not correctness: Claude is not always right either. Themes, search words, hypothesis splits and term resolutions have no decision to compare, so they are left out."));
    if (!App.project) { box.append(h("p", { class: "muted small" }, "Open a project first: the sample is taken from its answered tasks."), help); return box; }
    const out = h("div", { "aria-live": "polite", class: "set-test-out" });
    const kindSel = selectField({ "aria-label": "Kind of task" });
    const n = fieldInput({ type: "number", min: 10, max: 100, step: 5, value: 30, "aria-label": "Tasks to compare" });
    const planLine = h("p", { class: "small" });
    const start = aiButton({ sm: true }, "Compare the routes");
    const body = h("div", { class: "stack" });
    const base = `/api/projects/${P(App.project)}/agreement`;
    let kinds = [];
    let kept = [];
    const keptBox = h("div", { class: "agree-kept" });
    const kindName = (k) => (kinds.find((x) => x.kind === k) || {}).name || k;
    const num = (v) => (v === null || v === undefined ? "–" : v.toFixed(2));
    function keptLine(r) {
      return h("li", {}, `${fmt.dateShort(r.at)} · ${kindName(r.kind)} · ${r.compared} compared · kappa ${num(r.kappa)} · ${r.agree === null || r.agree === undefined ? "–" : `${Math.round(r.agree * 100)}%`} agree · ${r.local_model || "local model"} and ${r.claude_model || "Claude"} `,
        h("span", { class: "muted small" }, [reusedNote(r), r.app_version ? `Margin ${r.app_version}` : ""].filter(Boolean).join(" · ")));
    }
    // answers a task already had are reused: say how many, since they may come from an earlier local model
    function reusedNote(r) {
      if (r.asked_local === null || r.asked_local === undefined) return "";
      const reused = Math.max(0, (r.compared || 0) - r.asked_local);
      return reused ? `${reused} local ${reused === 1 ? "answer" : "answers"} reused` : "";
    }
    function showKept() {
      if (!kept.length) { clear(keptBox); return; }
      const SHOWN = 8, list = (rows) => h("ul", { class: "plain-steps" }, rows.map(keptLine));
      replace(keptBox, h("p", { class: "small" }, h("strong", {}, "Earlier comparisons")), list(kept.slice(0, SHOWN)),
        kept.length > SHOWN ? fold({ sm: true }, `${kept.length - SHOWN} more`, list(kept.slice(SHOWN))) : null);
    }
    const size = () => Math.min(100, Math.max(10, Math.round(n.valueAsNumber) || 30));
    async function showPlan() {
      start.disabled = true;
      try {
        const r = await api("GET", `${base}/plan?kind=${encodeURIComponent(kindSel.value)}&n=${size()}`);
        const p = r.plan, k = kinds.find((x) => x.kind === p.kind) || {};
        if (!p.n) { planLine.textContent = "No answered task of this kind is on documents Claude may read, so there is nothing to compare."; return; }
        const uses = s.backend === "claude_code" ? "uses your plan" : "uses your API credit";
        planLine.textContent = `${p.n} ${k.noun || "tasks"}: ${p.ask_local} asked of your local model, ${p.ask_claude} asked of Claude${p.ask_claude ? ` (${uses})` : ""}` + (p.left_out ? `; ${p.left_out} left out, Claude may not read their documents.` : ".");
        start.disabled = false;
      } catch (e) { planLine.textContent = e.message || "The plan could not be made."; }
    }
    start.addEventListener("click", async () => {
      start.disabled = true;
      try { follow((await api("POST", base, { kind: kindSel.value, n: size() })).job.id); }
      catch (e) { showError(e); start.disabled = false; }
    });
    function follow(jobId) {
      const stop = stopButton({ onClick: () => api("POST", `/api/jobs/${P(jobId)}/cancel`).catch(showError) });
      const pb = h("div", { class: "pb" });
      const holder = card({ as: "div", title: "Comparing", level: "h3", action: stop }, pb);
      replace(out, holder);
      // 0.19.13: both engines on purpose: the AI run panel with both sides at work
      const run = aiRun({ size: "compact", stop: false, engines: ["local", "cloud"], noun: "task",
        label: (job) => { const p = job.progress || {}; return p.total ? `Task ${Math.min((p.done || 0) + 1, p.total)} of ${p.total}` : "Starting…"; } });
      replace(pb, run.el);
      const watcher = watchJob(jobId, (job) => {
        run.update(job);
        if (TERMINAL.has(job.state)) stop.hidden = true;
      });
      watchers.push(watcher);
      watcher.promise.then((job) => {
        start.disabled = false;
        if (job.state === "done") {
          const r = job.result || {};
          const prev = r.previous, was = prev && prev.kappa !== null && prev.kappa !== undefined ? prev.kappa : null;
          if (r.kept) { kept = [r.kept, ...kept.filter((x) => x.run_id !== r.kept.run_id)]; showKept(); }
          replace(pb, h("p", {}, h("strong", {}, r.verdict || "")),
            was !== null && r.kappa !== null && r.kappa !== undefined ? h("p", { class: "small" }, `Kappa ${was.toFixed(2)} on ${fmt.dateShort(prev.at)} → ${r.kappa.toFixed(2)} now`) : null,
            h("div", { class: "kv" }, h("dt", {}, "Kappa"), h("dd", {}, r.kappa === null || r.kappa === undefined ? "–" : r.kappa.toFixed(2))),
            h("div", { class: "kv" }, h("dt", {}, "Same decision"), h("dd", {}, r.agree === null || r.agree === undefined ? "–" : `${Math.round(r.agree * 100)}% of ${r.decisions}`)),
            h("p", { class: "muted small" }, `${r.compared} of ${r.n} tasks compared. Asked now: ${r.asked.local} of your local model, ${r.asked.claude} of Claude.` + (r.failed ? ` ${r.failed} could not be compared.` : "")));
        } else if (job.state === "error") replace(pb, notice({ kind: "error" }, h("p", {}, job.error || "The comparison failed.")));
        else replace(pb, h("p", { class: "muted" }, "Stopped."));
      }).catch((e) => { start.disabled = false; showError(e); });
    }
    kindSel.addEventListener("change", showPlan);
    n.addEventListener("change", showPlan);
    box.append(body, keptBox, help);
    api("GET", `${base}/plan`).then((r) => {
      kinds = r.kinds || [];
      kept = r.kept || [];
      showKept();
      if (r.problem) { body.append(h("p", { class: "muted small" }, r.problem)); return; }
      if (!kinds.length) { body.append(h("p", { class: "muted small" }, "No task with a decision to compare is answered yet in this project (checks, second readings, labels and links have one).")); return; }
      kindSel.append(...kinds.map((k) => h("option", { value: k.kind }, `${k.name[0].toUpperCase()}${k.name.slice(1)} (${k.answered} answered)`)));
      body.append(h("div", { class: "fields-2" }, field("Kind of task", kindSel), field("Tasks to compare (10 to 100)", n)), planLine, h("div", { class: "row" }, withAI(start)),
        aiWhere(`Your local model (${s.restricted_model}) reads the sample on this computer.`, "local"), readsLine("the same sample"), out);
      showPlan();
    }).catch((e) => body.append(h("p", { class: "muted small" }, e.message || "Could not load the plan.")));
    return box;
  }

  // 0.18.1 (I1, I2, I4): which route answers each kind of task when Claude and a local model are both set, and what
  // happens at the plan's usage limit. Saved when picked.
  // `who`: the agent on the plan (Claude Code's words when none is given: "Claude"); the mix is shown only beside a local
  // model for an agent CLI, the usage limit always.
  function mixBox(who) {
    const local = !!(s.restricted_server && s.restricted_model);
    const W = who || "Claude", prog = who || "Claude Code";
    const st = h("span", { class: "save-state", "aria-live": "polite" });
    const pick = (key) => async (v) => { st.textContent = "Saving…"; try { await save({ [key]: v }, st); s[key] = v; } catch (e) { st.textContent = ""; throw e; } };
    const mix = choice({ sm: true, label: `The mix of local and ${W}`, value: s.ai_mix || "best",
      options: [["mostly_local", "Mostly local"], ["balanced", "Balanced"], ["best", "Best quality"]], onPick: pick("ai_mix") });
    const limit = choice({ sm: true, label: "At your plan's usage limit", value: s.at_limit || "wait",
      options: [["wait", "Wait and continue later"], ["local", "Carry on with the local model"]], onPick: pick("at_limit") });
    const mixField = who && !local ? null : h("div", { class: "field" }, h("div", { class: "field-label" }, `The mix of local and ${W}`), h("div", { class: "row" }, mix, st),
        h("div", { class: "field-help" }, local ? `Mostly local: your local model answers every kind of task but second opinions. Balanced: it answers labels, links, search words, theme names and references; ${W} judges excerpts. Best quality: ${W} answers everything (your local model reads only documents marked Only a local AI). An answer your local model is unsure of, that fails the quote check, or that judges an excerpt as contradicting goes to ${W}, only for documents ${W} may read. Can change results. `
          : `Choose a local model for documents marked Only a local AI (under AI model) to share the work between it and ${W}. `,
          helpMark("About the mix", `The local model answers first, on this computer; its answer counts unless it goes up to ${W}, which then reads the task again. Each answer records which model gave it (Technical details, and the Excel file's How these results were made).${who ? "" : " Settings › AI › Agreement between routes shows, on your own documents, how often the two agree."}`)));
    return h("div", { class: "stack", id: "s-mix" }, mixField,
      h("div", { class: "field" }, h("div", { class: "field-label" }, "At your plan's usage limit"), h("div", { class: "row" }, limit, who && !local ? st : null),
        h("div", { class: "field-help" }, `When ${prog} stops because your plan's usage limit is reached: wait (the queue keeps the work; start ${prog} again when the limit resets), or let your local model answer what waits, where it may.`)));
  }

  // Another cloud provider (stage 1; stage 2, B3): the providers as option cards (the storage spaces' way, team-setup.js),
  // each with its key's state; for the chosen one a status card whose button opens the key's set-up in guided steps
  // (provider-setup.js): "Set up OpenAI…" without a key, "Change the key…" and "Forget the key" with one (only
  // "stored: yes or no" ever comes back). Under it the recommended models, applied automatically: one row per tier,
  // empty = the provider's recommendation resolved against the key's list (Azure: the deployments' names, typed),
  // how much thought, and that it is not measured yet. The line under "Allow cloud models" names where the text goes.
  function cloudProviderBox() {
    const pst = () => (App.state && App.state.providers) || {};
    const list = (pst().list || []).filter((p) => p.id !== "anthropic");
    if (!list.length) return notice({ kind: "attention" }, h("p", {}, "No cloud provider is known to this copy of Margin."));
    let pid = list.some((p) => p.id === s.cloud_provider) ? s.cloud_provider : list[0].id;
    let azureDeps = null;   // the deployments named in Azure's set-up (kept in the settings too)
    const refused = {};     // provider id → the provider answered that the stored key is wrong (seen when the models were asked)
    const info = () => list.find((p) => p.id === pid) || {};
    const have = (id) => !!(pst().keys || {})[id];
    const where = h("div", {});
    const cardsHolder = h("div", {}), statusHolder = h("div", {}), modelsHolder = h("div", {}), measured = h("p", { class: "muted small" });
    fields.cloud_provider = { get value() { return pid; } };
    fields.azure_url = fieldInput({ mono: true, type: "url", id: "azure-url", value: s.azure_url || "", placeholder: "https://my-resource.openai.azure.com" });
    const azure = field("Endpoint of your Azure OpenAI resource", fields.azure_url, { help: "From the Azure portal: your Azure OpenAI resource › Keys and Endpoint. The set-up fills it in." });
    // what the done step's main button still does once a key is stored: allow cloud models and use this provider
    // (null when that is so already). Pressing it saves at once; "Not now" leaves it for Save.
    const offer = () => {
      const saved = App.settings(), p = info();
      if (saved.backend === "cloud_api" && saved.cloud_provider === p.id && saved.allow_cloud) return null;
      return {
        text: saved.allow_cloud ? `Use ${p.title}` : `Allow cloud models and use ${p.title}`,
        line: `Then ${p.title} reads your documents: the excerpts go to ${p.company}, only for documents that allow ${p.title}.`,
        run: async () => {
          await save({ allow_cloud: true, backend: "cloud_api", cloud_provider: p.id }, state);
          Object.assign(s, App.settings());
          allowCloud.input.checked = true; allowCloud.input.setAttribute("aria-checked", "true");
          backend = "cloud_api";
        },
      };
    };
    const drawCards = () => replace(cardsHolder, optionCards({ name: "cloud-provider", class: "provider-cards", label: "Which cloud provider", value: pid,
      options: list.map((p) => ({ value: p.id, icon: "key", title: p.title, text: PROVIDER_TEXT[p.id] || "", tag: have(p.id) ? (refused[p.id] ? "Key refused" : "Key stored") : null,
        foot: [icon("cloud", { size: 12 }), `${p.company} · billed per use${have(p.id) ? "" : " · not set up"}`] })),
      onPick: (v) => { pid = v; azureDeps = null; draw(); } }));
    const chosenNow = () => (fields.cloudRows ? fields.cloudRows.pick() : {});
    const setUp = async (at) => {
      const p = info();
      const r = await providerSetup(p, { at, chosen: chosenNow(), offer });
      Object.assign(s, App.settings());   // the set-up may have saved (Azure's names; the main button of the done step)
      if (!r) { drawCards(); drawStatus(); return; }
      delete refused[p.id];
      if (r.azure_url) fields.azure_url.value = r.azure_url;
      if (r.deployments) azureDeps = r.deployments;
      draw();
    };
    const drawStatus = () => {
      const p = info();
      const ok = have(p.id);
      const forget = async () => {
        try { App.state.providers = (await api("DELETE", "/api/settings/provider-key", { provider: p.id })).providers; delete refused[p.id]; toast(`${p.title} key forgotten.`, "ok"); draw(); }
        catch (e) { showError(e); }
      };
      replace(statusHolder, card({ as: "div", class: "set-key provider-status" },
        h("div", { class: "field-label" }, `${p.title} API key`),
        ok ? (refused[p.id]
            ? notice({ kind: "attention", class: "set-key-notice", id: "cloud-key-refused" }, h("p", {}, `${p.title} refused the stored key. Copy it again from the keys page, or make a new one.`))
            : notice({ kind: "done", class: "set-key-notice" }, h("p", {}, `Key stored ${storedWhere()}.`)))
          : h("p", { class: "muted small" }, `Not set up yet. The set-up shows you, step by step, where to get ${article(p.title)} ${p.title} key, and keeps it ${storedWhere()}.`),
        h("div", { class: "btn-row" }, ok
          ? [button({ sm: true, icon: "key", id: "cloud-key-change", onClick: () => setUp("paste") }, "Change the key…"), button({ kind: "quiet", sm: true, id: "cloud-key-forget", onClick: forget }, "Forget the key")]
          : button({ icon: "key", id: "cloud-key-setup", onClick: () => setUp() }, `Set up ${p.title}…`))));
    };
    const drawModels = async () => {
      const p = info();
      let models = [], problem = "", rec = p.recommended || {};
      if (p.lists_models && have(p.id)) {
        try {
          const r = await api("GET", `/api/settings/provider-models?provider=${encodeURIComponent(p.id)}`);
          models = r.models || []; problem = r.problem || ""; if (r.recommended) rec = r.recommended;
          if (!!r.refused !== !!refused[p.id]) { refused[p.id] = !!r.refused; if (p.id === pid) { drawCards(); drawStatus(); } }
        } catch (e) { problem = e.message; }
      }
      if (p.id !== pid) return;   // another provider was picked meanwhile
      const mine = pid === s.cloud_provider;
      const chosen = azureDeps || (mine ? { small: s.cloud_small_model, middle: s.cloud_model, strong: s.cloud_strong_model } : {});
      const typed = p.id === "azure";
      fields.cloudRows = modelRows({ id: "m-cloud", recommended: rec, chosen, models: models.length ? models : Object.values(rec), typed });
      replace(modelsHolder, h("div", { class: "field", id: "s-cloud-models" },
        h("div", { class: "field-label" }, typed ? "Your deployments" : MODELS_LABEL),
        h("div", { class: "field-help" }, typed ? `The names of your three deployments. Deploy these models and keep their names: ${TIERS.map((t) => rec[t]).filter(Boolean).join(", ")}. The set-up fills them in.`
          : `From ${p.company}’s own advice${models.length ? ", among the models your key may use" : ""}. A newer Margin brings newer ones by itself; choose another only if you need to. Saved with Save.`),
        // the refused key has its own notice above; any other problem is said here, without words that point to this page
        problem && !refused[p.id] ? h("p", { class: "muted small" }, plainProblem(problem)) : null,
        fields.cloudRows));
    };
    const draw = () => {
      const p = info();
      replace(where, aiWhere(`With ${p.title} the hypothesis and the excerpts read leave this computer for ${p.company} and are billed to your key. Only documents that allow ${p.title} are sent.`, "cloud"));
      azure.hidden = pid !== "azure";
      measured.textContent = `${p.title} is not yet measured with Margin: its models and settings were measured with Claude only. Check its answers before you rely on them.`;
      drawCards(); drawStatus(); drawModels();
    };
    draw();
    return h("div", { class: "stack cloud-provider" }, inset({ class: "cloud-box" }, allowCloud, where),
      h("div", { class: "field" }, h("div", { class: "field-label", id: "cloud-provider-label" }, "Cloud provider"), cardsHolder),
      statusHolder, azure, modelsHolder,
      thoughtField("Which of the three models answers each kind of task, and how hard it thinks. ", THOUGHT_ABOUT_OTHER),
      s.backend === "cloud_api" ? allowLine(App.project) : null,
      measured);
  }

  // The Claude API's key (the anthropic route): the same status card and set-up as another provider's key
  // (provider-setup.js claudeKeySetup), instead of a bare key field.
  function claudeApiCard() {
    const holder = h("div", {});
    const offer = () => {
      const saved = App.settings();
      if (saved.backend === "anthropic" && saved.allow_cloud) return null;
      return {
        text: saved.allow_cloud ? "Use the Claude API" : "Allow cloud models and use the Claude API",
        line: "Then the Claude API reads your documents: the excerpts go to Anthropic, billed to this key.",
        run: async () => {
          await save({ allow_cloud: true, backend: "anthropic" }, state);
          Object.assign(s, App.settings());
          allowCloud.input.checked = true; allowCloud.input.setAttribute("aria-checked", "true");
          backend = "anthropic";
        },
      };
    };
    const draw = () => {
      const k = (App.state && App.state.key) || {};
      const have = k.env ? "from the environment variable ANTHROPIC_API_KEY" : k.stored ? "saved on this computer" : k.session ? "kept until you close Margin" : "";
      const setUp = async (at) => { await claudeKeySetup({ at, offer }); Object.assign(s, App.settings()); draw(); };
      const forget = async () => {
        try { App.state.key = (await api("DELETE", "/api/settings/key")).key; toast("Key forgotten.", "ok"); draw(); } catch (e) { showError(e); }
      };
      replace(holder, card({ as: "div", class: "set-key provider-status" },
        h("div", { class: "field-label" }, "Claude API key"),
        have ? notice({ kind: "done", class: "set-key-notice" }, h("p", {}, `A key is set (${have}).`))
          : h("p", { class: "muted small" }, "Not set up yet. The set-up shows you, step by step, where to get a key on the Claude platform. Without a key, cloud checks fail."),
        h("div", { class: "btn-row" }, have
          ? [k.env ? null : button({ sm: true, icon: "key", id: "claude-key-change", onClick: () => setUp("paste") }, "Change the key…"),
            k.session || k.stored ? button({ kind: "quiet", sm: true, id: "claude-key-forget", onClick: forget }, "Forget the key") : null]
          : button({ icon: "key", id: "claude-key-setup", onClick: () => setUp() }, "Set up the Claude API…"))));
    };
    draw();
    return holder;
  }

  const saveBtn = button({ kind: "main", type: "submit" }, icon("check", { size: 14 }), "Save");
  const testBtn = button({}, icon("zap", { size: 14 }), "Save and test");
  const testOut = h("div", { class: "test-result", "aria-live": "polite" });

  const collect = () => {
    const c = { backend, allow_cloud: allowCloud.input.checked };
    if (backend === "claude_code") c.allow_claude_code = allowCC;
    if (AGENTS[backend]) {
      c[`allow_${backend}`] = allowAgent[backend];
      if (fields.cliRows && fields.cliRoute === backend) c.cli_models = { ...(s.cli_models || {}), [backend]: fields.cliRows.pick() };
    }
    if (fields.use_fable && (backend === "claude_code" || backend === "anthropic")) c.use_fable = fields.use_fable.input.checked;
    if (fields.ollama_url) c.ollama_url = fields.ollama_url.value.trim();
    if (fields.openai_url) c.openai_url = fields.openai_url.value.trim();
    if (fields.ollamaModel) c.ollama_model = fields.ollamaModel.value();
    if (fields.openaiModel) c.openai_model = fields.openaiModel.value();
    if (fields.anthropic_model) c.anthropic_model = fields.anthropic_model.value.trim();
    if (backend === "cloud_api" && fields.cloud_provider) {
      c.cloud_provider = fields.cloud_provider.value;
      if (fields.cloudRows) {
        const m = fields.cloudRows.pick();
        Object.assign(c, { cloud_small_model: m.small, cloud_model: m.middle, cloud_strong_model: m.strong });
      }
      if (c.cloud_provider === "azure") c.azure_url = fields.azure_url.value.trim();
    }
    if (fields.think && (backend === "ollama" || backend === "auto")) {
      c.think = fields.think.value;
      c.think_budget = Math.max(0, Math.round(Number(fields.think_budget.value) || 0));
    }
    return c;
  };
  const form = h("form", { onSubmit: async (e) => { e.preventDefault(); try { await save(collect(), state); Object.assign(s, App.settings()); toast(`AI: ${App.state.backend_label}`, "ok"); } catch (_) { /* shown */ } } },
    radiosWrap, lockedLine, detail, h("div", { class: "save-row" }, saveBtn, testBtn, state));
  // 0.14.3: what is changed here and not saved yet says so (leaving the page dropped it without a word)
  form.addEventListener("change", (e) => { if (!fields.use_fable || e.target !== fields.use_fable.input) state.textContent = "Not saved yet: press Save."; });
  form.addEventListener("input", (e) => { if (e.target.matches("input[type=text], input[type=url], input[type=number], input:not([type]), select")) state.textContent = "Not saved yet: press Save."; });
  testBtn.addEventListener("click", async () => {
    testBtn.disabled = true;
    replace(testOut, notice({ kind: "info", icon: false }, h("span", { class: "spinner" }, icon("loader")), h("p", {}, "Testing the model service…")));
    try {
      await save(collect(), state);
      Object.assign(s, App.settings());
      const r = await api("POST", "/api/servers/test");
      replace(testOut, testResult(r));
    } catch (e) {
      replace(testOut, notice({ kind: "error", live: false }, h("p", {}, e.message), e.kind === "backend" ? h("p", { class: "small" }, "Is the server running? For Ollama: open the Ollama app; a model can be downloaded above.") : null));
    }
    testBtn.disabled = false;
  });
  drawDetail();
  return sectionCard("model", "Which AI reads your documents", "", form, testOut);
}

export function testResult(r) {
  const bits = [];
  const d = r.details || {};
  bits.push(notice({ kind: r.model_available ? "done" : "attention" }, h("p", {}, r.message || (r.ok ? "The model answers." : "Problem")),
    d.trained_context ? h("p", { class: "small" }, `Trained for ${fmt.num(d.trained_context)} tokens of context.`) : null));
  if (r.warning) bits.push(notice({ kind: "attention" }, h("p", {}, r.warning)));
  if (r.embedding) {
    bits.push(r.embedding.ok ? notice({ kind: "done" }, h("p", {}, `Embedding model ${r.embedding.model} answers (${r.embedding.dimensions} dimensions).`))
      : notice({ kind: "attention" }, h("p", {}, `Embedding model ${r.embedding.model}: ${r.embedding.error}`)));
  }
  return h("div", { class: "stack set-test-result" }, bits);
}

// ---------------------------------------------------------------------------------------------
// 0.8: the model of each kind of task, and when a task goes up to a stronger one.
function routingSection(s, servers) {
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const body = h("div", {}, h("p", { class: "muted small" }, "Loading…"));
  const chat = [...new Set(servers.flatMap((x) => x.chat_models || []))];
  async function draw() {
    let r;
    try { r = await api("GET", "/api/routing"); } catch (e) { replace(body, h("p", { class: "muted small" }, e.message)); return; }
    const claude = r.route === "claude_code" || r.route === "anthropic";
    const chosen = ((App.settings().task_models || {})[claude ? "claude" : "local"]) || {};
    const selects = {};
    const rows = r.rows.map((row) => {
      let ctl;
      if (row.row === "second" && !claude) ctl = h("span", { class: "muted small" }, "Set under “Model for second opinions” below.");
      else if (claude) {
        ctl = selectField({ sm: true, "aria-label": `Model for ${row.title}` }, h("option", { value: "" }, `${row.recommended} (recommended)`),
          r.aliases.map((a) => h("option", { value: a, selected: chosen[row.row] === a }, a)));
        selects[row.row] = ctl;
      } else {
        ctl = fieldInput({ sm: true, mono: true, type: "text", list: "routing-models", value: chosen[row.row] || "", placeholder: row.recommended === "small" ? "the small model" : "the main model", "aria-label": `Model for ${row.title}` });
        selects[row.row] = ctl;
      }
      const up = !row.step_up ? "none" : (r.route === "claude_code" && ["check", "split", "verify"].includes(row.row) ? `${row.step_up} (auditor)` : row.step_up);
      return h("tr", {}, h("td", {}, h("strong", {}, row.title)), h("td", { class: "mono small fact", "data-label": "Model" }, row.model || "the main model"), h("td", { class: "mono small fact", "data-label": "Steps up to" }, up),
        r.route === "claude_code" ? h("td", { class: "mono small fact", "data-label": "Helper" }, row.helper || "") : null, h("td", { "data-label": "Your choice" }, ctl));
    });
    const small = fieldInput({ mono: true, type: "text", list: "routing-models", value: r.local_small_model || "", placeholder: "none: the main model does everything" });
    const one = switchControl("Use the model of each task (recommended)", r.routing, { help: "Off: one model for everything, as in Margin 0.7." });
    const saveBtn = button({ kind: "main", sm: true, onClick: async () => {
      const mine = {};
      for (const [k, el] of Object.entries(selects)) if (el.value && el.value.trim()) mine[k] = el.value.trim();
      const all = { ...(App.settings().task_models || {}) };
      if (Object.keys(mine).length) all[claude ? "claude" : "local"] = mine; else delete all[claude ? "claude" : "local"];
      const changes = { task_models: all, routing: one.input.checked };
      if (!claude) changes.local_small_model = small.value.trim();
      try { await save(changes, state); draw(); } catch (_) { /* shown */ }
    } }, icon("check", { size: 13 }), "Save");
    const resetBtn = button({ sm: true, onClick: async () => {
      const all = { ...(App.settings().task_models || {}) };
      delete all[claude ? "claude" : "local"];
      try { await save({ task_models: all, routing: true }, state); draw(); toast("The recommended models are used again.", "ok"); } catch (_) { /* shown */ }
    } }, icon("refresh", { size: 13 }), "Use the recommended models");
    replace(body,
      h("p", { class: "small" }, `Route now: ${r.route_name}. ${claude ? (r.route === "claude_code" ? "Each kind of task starts on the model recommended for your Claude plan and goes up one step on its own when it is hard." : "Each kind of task starts on the cheapest model that is good enough and goes up one step on its own when it is hard.") : "With a small model chosen, labels and links start on it and go up to the main model when they are hard; without one the main model does everything, as in 0.7."}`),
      r.route === "claude_code" ? planField(r.plan || {}) : null,
      h("div", { class: "table-wrap" }, h("table", { class: "table table-responsive routing-table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Task"), h("th", { scope: "col" }, "Model"), h("th", { scope: "col" }, "Steps up to"), r.route === "claude_code" ? h("th", { scope: "col" }, "Helper") : null, h("th", { scope: "col" }, "Your choice"))),
        h("tbody", {}, rows))),
      h("datalist", { id: "routing-models" }, chat.map((m) => h("option", { value: m }))),
      claude ? null : field("Small model (labels and links)", small, { help: "A smaller local model for the many label and link tasks. Leave it empty to use the main model for everything." }),
      h("p", { class: "muted small" }, icon("info", { size: 13 }), ` A task goes up to the stronger model once: when its answer's certainty is under ${Math.round(r.step_up_below * 100)}%, when two answers in a row were rejected (a quote not found), or when you press “Ask a stronger model” on a result. Both answers are kept; the stronger model's counts, and the answer shows a small mark with what it was at first. A second opinion is different: it is only shown beside the first reading and never changes the answer.`),
      r.route === "claude_code" ? null : one,
      h("p", { class: "muted small" }, r.route === "claude_code" ? "On a Pro plan the recommended models are the starting points of Margin 0.8, which the team's runs on the pilot set (" : "The recommended models are the starting points of Margin 0.8; the team's runs on the pilot set them (", h("code", {}, "margin acceptance score --apply"), ")."),
      h("div", { class: "save-row" }, saveBtn, resetBtn, state));
  }
  // 0.13.10: the Claude plan the recommendations follow: found in the background, or set here by hand
  function planField(plan) {
    const titles = plan.titles || { free: "Free", pro: "Pro", max: "Max, Team or Enterprise" };
    const found = plan.detected ? titles[plan.detected] : "";
    const sel = selectField({ sm: true, id: "routing-plan" },
      h("option", { value: "auto", selected: (plan.chosen || "auto") === "auto" }, found ? `Your plan, as Claude Code says: ${found}` : "Your plan, as Claude Code says (not known yet)"),
      ["free", "pro", "max"].map((t) => h("option", { value: t, selected: plan.chosen === t }, titles[t])));
    sel.addEventListener("change", async () => { try { await save({ claude_plan: sel.value }, state); draw(); } catch (_) { /* shown */ } });
    const what = {
      free: "No Opus or Fable: Haiku for most tasks, Sonnet for judging excerpts.",
      pro: "Sonnet for most tasks, Haiku for the many labels and links, Opus for second opinions and the hard cases.",
      max: "Opus for most tasks; Haiku and Sonnet only for the many labels, links and references, where speed matters.",
    }[plan.tier] || "Until Claude Code says which plan you have, the recommendations for Pro are used.";
    return h("div", { class: "field" }, h("label", { class: "field-label", for: "routing-plan" }, "The recommendations follow"), sel,
      h("div", { class: "field-help" }, `${what} Margin finds your plan by itself; the models you choose below come first.`));
  }
  draw();
  return sectionCard("routing", "AI model per task", "Which model answers each kind of task. Most people never change this.", body);
}

// ---------------------------------------------------------------------------------------------
// A second local chat model for "Get a second opinion" on results.
function secondModelSection(s, servers) {
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const main = (s.backend === "openai" ? s.openai_model : s.ollama_model) || "";
  const models = [...new Set(servers.flatMap((x) => x.chat_models || []))].filter((m) => m !== main);
  const current = s.second_model || "";
  const sel = selectField({ id: "second-model" }, h("option", { value: "" }, "None (no second opinions)"),
    models.map((m) => h("option", { value: m, selected: m === current }, m)),
    current && !models.includes(current) ? h("option", { value: current, selected: true }, `${current} (not installed now)`) : null);
  const txt = fieldInput({ mono: true, type: "text", placeholder: "or type a model name", value: "", "aria-label": "Model for second opinions, typed" });
  const saveBtn = button({ kind: "main", sm: true, onClick: async () => {
    const v = txt.value.trim() || sel.value;
    if (v && v === main) { toast("That is the main model. Choose a different one for second opinions.", "warn"); return; }
    try { await save({ second_model: v }, state); txt.value = ""; toast(v ? `Model for second opinions: ${v}` : "Model for second opinions: none", "ok", { ttl: 2500 }); } catch (_) { /* shown */ }
  } }, icon("check", { size: 13 }), "Save");
  return sectionCard("second", "Model for second opinions", "For “Get a second opinion” on a result: another chat model on the same server reads the same excerpts, and its judgements are shown beside the main model's, for comparison only. Where the two differ, the excerpt deserves a careful read. A second opinion never changes an answer (a stronger model, asked for with “Ask a stronger model”, does).",
    h("div", { class: "fields-2" }, field("Model for second opinions", sel, { help: models.length ? `Chat models on the server now, apart from the main one (${main || "none chosen"}).` : "No server answered just now, so the installed models could not be listed." }), field("Not listed?", txt, { help: "Type its name as the server knows it, e.g. llama3.1:8b." })),
    h("p", { class: "muted small" }, icon("info", { size: 13 }), " Only one model is kept in memory at a time: the main model is unloaded before the second one reads, and the second one is unloaded when it is done. So a second opinion takes a while, and is best asked for several results at once (on the Hypotheses page, under its answers)."),
    h("div", { class: "save-row" }, saveBtn, state));
}

// The context length the model is given, and the second sorting pass: for whoever installs the app.
function contextSection(s) {
  const st = App.state || {};
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const ctxLine = h("div", { class: "set-context-line" });
  const drawCtx = () => {
    const c = (App.state && App.state.context) || {};
    const n = c.num_ctx ? fmt.num(c.num_ctx) : "?";
    const k = App.settings().k ?? 8;
    const auto = String(c.setting ?? App.settings().num_ctx ?? "auto").toLowerCase() === "auto";
    replace(ctxLine, notice({ kind: c.too_small ? "attention" : "done", icon: c.too_small ? undefined : "info" },
      h("p", {}, h("strong", {}, auto ? "Automatic: " : "Fixed: "), `${n} tokens, ${c.too_small ? "which is " : ""}${c.too_small ? "too small for" : "enough for"} ${k} excerpts per check${c.needed ? ` (the largest task needs about ${fmt.num(c.needed)} tokens${c.thinking_allowance ? ", including room for reasoning" : ""})` : ""}.`),
      c.too_small ? h("p", { class: "small" }, "Part of the prompt would be cut off. Choose Automatic, a larger number, or fewer excerpts per check.") : null));
  };
  drawCtx();
  const isAuto = String(s.num_ctx ?? "auto").toLowerCase() === "auto";
  const mode = selectField({ id: "ctx-mode" }, h("option", { value: "auto", selected: isAuto }, "Automatic (recommended)"), h("option", { value: "number", selected: !isAuto }, "A fixed number of tokens"));
  const num = fieldInput({ type: "number", id: "ctx-num", min: 2048, max: 262144, step: 1024, value: isAuto ? 16384 : Number(s.num_ctx), hidden: isAuto });
  const numLabel = h("label", { class: "field-label", for: "ctx-num", hidden: isAuto }, "Tokens");
  const saveCtx = async () => {
    const v = mode.value === "auto" ? "auto" : Math.max(2048, Number(num.value) || 16384);
    try { await save({ num_ctx: v }, state); await App.refresh(); drawCtx(); } catch (_) { /* shown */ }
  };
  mode.addEventListener("change", () => { num.hidden = numLabel.hidden = mode.value !== "number"; if (mode.value === "auto") saveCtx(); else num.focus(); });
  num.addEventListener("change", saveCtx);
  const secondPass = switchControl("Sort the best excerpts again by wording", !!s.second_pass, { help: "After the search, the best candidates are sorted once more by how closely they word the hypothesis (no AI involved). Off by default: on the pilot it did slightly worse, bringing a few fewer excerpts from the cited sources into the top 8 (147 against 154 of 178)." });
  secondPass.input.addEventListener("change", async () => { try { await save({ second_pass: secondPass.input.checked }, state); } catch (_) { /* shown */ } });
  return sectionCard("context", "Context length and search order", "How much text the local model is given at once, and an optional extra sorting step. The defaults suit most computers.",
    ctxLine,
    h("div", { class: "fields-2" }, field("Context length", mode, { help: "Ollama reloads the model when this changes, so it is kept the same between requests. Automatic leaves the most memory to the model: 8,192, 12,288, 16,384 or 32,768 tokens, whichever is the smallest that fits." }), h("div", { class: "field" }, numLabel, num)),
    secondPass,
    h("div", { class: "save-row" }, h("span", { class: "muted small" }, "Saved as soon as you change something."), state));
}

// ---------------------------------------------------------------------------------------------
function embedSection(s, servers, info = { servers }) {
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const kind = selectField({}, [["ollama", "Ollama"], ["openai", "OpenAI-compatible server"], ["off", "Off (keywords only)"]].map(([v, t]) => h("option", { value: v, selected: (s.embed_backend || "ollama") === v }, t)));
  const all = [...new Set(servers.flatMap((x) => x.embedding_models || []))];
  const model = fieldInput({ mono: true, type: "text", value: s.embed_model || "", placeholder: "e.g. nomic-embed-text", list: "embed-models" });
  const datalist = h("datalist", { id: "embed-models" }, all.map((m) => h("option", { value: m })));
  const url = fieldInput({ mono: true, type: "url", value: s.embed_url || "", placeholder: "optional" });
  const row = h("div", { class: "fields-3" }, field("Server kind", kind), field("Embedding model", model, { help: all.length ? `Installed: ${all.join(", ")}` : "None installed yet." }), field("Address (optional)", url, { help: "Leave empty to use the chat server's address." }));
  // 0.13.7: Ollama without an embedding model: one button downloads one, and it is chosen here
  const pull = localModelHelp(info, { only: "embed", use: "embed", onReady: async (r) => {
    try { await App.refresh(); } catch (_) { /* shown on the page */ }
    toast(r.chosen ? `${r.embed} is chosen for search by meaning. Set it up per project under Documents.` : `${r.embed} is downloaded.`, "ok");
    rerender();
  } });
  const toggle = () => { row.querySelectorAll(".field")[1].hidden = row.querySelectorAll(".field")[2].hidden = kind.value === "off"; };
  kind.addEventListener("change", toggle); toggle();
  const form = h("form", { onSubmit: async (e) => { e.preventDefault(); try { await save({ embed_backend: kind.value, embed_model: model.value.trim(), embed_url: url.value.trim() }, state); toast("Saved. If needed, set up search by meaning on the project’s Documents page.", "ok"); } catch (_) { /* shown */ } } },
    row, datalist, pull, h("div", { class: "save-row" }, button({ kind: "main", type: "submit" }, icon("check", { size: 14 }), "Save"), state));
  return sectionCard("embeddings", "Search by meaning (embeddings)", "With an embedding model, excerpts are found by meaning as well as by shared words. It is set up per project, on the project’s Documents page.", form);
}

// ---------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------
// 0.16 (K1): codebooks have a page of their own (Codebooks, in the sidebar): made, changed, copied and removed there
function frameworksSection() {
  return sectionCard("frameworks", "Codebooks", "Your own codebooks, and the SDG targets that ship with Margin, are on a page of their own: make one fresh or from the themes found, change its codes, try it without AI, and go back to an earlier version.",
    link({ kind: "next", href: "#/codebooks" }, "Open Codebooks"));
}

// ---------------------------------------------------------------------------------------------
// 0.7: the defaults of document profiles and themes
function exploreSection(s) {
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const shortFw = (f) => (f.title && /\(\d+ \w+\)/.test(f.title) ? f.title : `${f.title || f.name} (${f.codes} codes)`);
  const fwSel = selectField({ id: "set-profile-fw" }, h("option", { value: s.profile_framework || "sdg", selected: true }, s.profile_framework || "sdg"));
  // team codebooks (teamcodebooks.py): the open project's owner chose a default codebook for every copy of it
  const team = App.project && App.state && App.state.profile_framework_team;
  (async () => {
    if (!App.project) return;
    try {
      const fws = (await api("GET", `/api/projects/${P(App.project)}/frameworks`)).frameworks || [];
      // team codebooks: with the project's default, the select still shows this computer's own setting
      const mine = team ? (s.profile_framework || "sdg") : App.framework();
      replace(fwSel, ...fws.map((f) => h("option", { value: f.name, selected: f.name === mine }, shortFw(f))));
    } catch (_) { /* keep the saved name */ }
  })();
  fwSel.addEventListener("change", async () => { try { await save({ profile_framework: fwSel.value }, state); } catch (_) { /* shown */ } });
  const k = rangeControl("Themes per set", { min: 2, max: 60, step: 1, value: s.themes_k ?? 20 });
  k.input.addEventListener("change", async () => { try { await save({ themes_k: k.input.valueAsNumber }, state); } catch (_) { /* shown */ } });
  return sectionCard("explore", "Exploring the documents", "The defaults of the Profile and Themes pages. You can change both on those pages too.",
    h("div", { class: "stack set-context-form" },
      field("Codebook of the profiles", fwSel, { help: team
        ? `This project uses the team’s default: “${team.title}” (set by the owner). This setting still applies to your other projects.`
        : "Which codes the Profile page and the Codes panel of a document look for, and which codes new documents get when they are added." }),
      h("div", {}, k, h("p", { class: "field-help" }, "How many themes a new set looks for. A small project gets fewer: about three passages a theme at least."))),
    h("div", { class: "save-row" }, h("span", { class: "muted small" }, "Saved as soon as you change something."), state));
}

// the seed that keeps model answers repeatable, and a test of whether the server honours it
function reproSection(s) {
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const seed = fieldInput({ mono: true, type: "number", id: "set-seed", min: 0, max: 2147483647, step: 1, value: s.seed ?? 42 });
  seed.addEventListener("change", async () => {
    const v = Math.round(Number(seed.value));
    if (!Number.isFinite(v) || v < 0 || v > 2147483647) { toast("The seed is a whole number from 0 to 2,147,483,647.", "warn"); return; }
    try { await save({ seed: v }, state); } catch (_) { /* shown */ }
  });
  const out = h("div", { "aria-live": "polite" });
  const test = aiButton({ sm: true }, "Test whether answers repeat");
  test.addEventListener("click", async () => {
    setBusy(test, true);
    // one call: the AI run panel's compact look, its one engine at work, then the result
    const p = App.privacy();
    const what = "Asking the model the same short question twice";
    replace(out, p.where === "local" ? aiSides(aiSide({ where: "local", model: String(p.detail || "").split(" · ").pop() || null, running: { phase: "waiting" }, compact: true }), null, { compact: true })
      : p.where === "cloud" ? aiSides(null, aiSide({ where: "cloud", state: "run", what }), { compact: true })
      : h("p", { class: "muted small" }, `${what}…`));
    try {
      const r = await api("POST", "/api/servers/repeatable", {});
      replace(out, notice({ kind: r.repeatable ? "done" : "attention" },
        h("p", {}, h("strong", {}, r.repeatable ? "Repeatable" : "Not guaranteed"), r.model ? ` · ${r.model}` : ""),
          h("p", { class: "small" }, r.note || ""),
          h("p", { class: "small muted" }, `Tested: the same request (search words for a short hypothesis) sent twice, with seed ${App.settings().seed ?? 42} and temperature 0.${r.digest ? ` Exact version: ${String(r.digest).slice(0, 19)}…` : ""} It says whether this server repeats itself; the version and settings behind each result are in “How these results were made” in every Excel download and under Technical details on the Profile page.`)));
    } catch (e) { replace(out); showError(e); }
    setBusy(test, false);
  });
  return sectionCard("repeatable", "Repeatable results", "Every model request is sent with a fixed seed and temperature 0, and every result records the model and, when the server reports it, its exact version (the digest), so the same documents and settings give the same answers. Whether a server honours the seed differs: test it here.",
    h("div", { class: "fields-2" },
      field("Seed", seed, { help: "Any whole number. Changing it can change the answers; it is shown in “How these results were made”." })),
    h("div", { class: "save-row" }, withAI(test), state),
    readsLine("a short test question, twice"),
    out);
}

// ---------------------------------------------------------------------------------------------
function testSection(s, watchers) {
  const ref = fieldInput({ mono: true, type: "text", value: s.benchmark_reference || "", placeholder: "/path/to/pilot" });
  const n = rangeControl("Tasks per kind", { min: 5, max: 50, step: 5, value: 10 });
  const kVerify = h("input", { type: "checkbox", checked: true, id: "k-verify" });
  const kExtract = h("input", { type: "checkbox", id: "k-extract" });
  const kLabel = h("input", { type: "checkbox", id: "k-label" });
  const out = h("div", { "aria-live": "polite", class: "set-test-out" });
  const run = aiButton({ sm: true }, "Run the test");
  run.addEventListener("click", async () => {
    const kinds = [kVerify.checked && "verify_set", kExtract.checked && "extract", kLabel.checked && "label"].filter(Boolean);
    if (!ref.value.trim() || !kinds.length) { toast("Give the reference folder and tick at least one task kind.", "warn"); return; }
    run.disabled = true;
    try {
      const r = await api("POST", "/api/benchmark", { reference: ref.value.trim(), kinds, n: n.input.valueAsNumber });
      follow(r.job.id);
    } catch (e) { showError(e); run.disabled = false; }
  });
  function follow(jobId) {
    const stop = stopButton({ onClick: () => api("POST", `/api/jobs/${P(jobId)}/cancel`).catch(showError) });
    const pb = h("div", { class: "pb" });
    const holder = card({ as: "div", title: "Testing", level: "h3", action: stop }, pb);
    replace(out, holder);
    // the panel (not `run`: that is the button, which comes back once the test has ended)
    const panel = aiRun({ size: "compact", stop: false, noun: "task",
      label: (job) => { const p = job.progress || {}; return p.total ? `Task ${Math.min((p.done || 0) + 1, p.total)} of ${p.total}${p.task ? " · " + p.task : ""}` : "Starting…"; } });
    replace(pb, panel.el);
    const watcher = watchJob(jobId, (job) => {
      panel.update(job);
      if (TERMINAL.has(job.state)) stop.hidden = true;
    });
    watchers.push(watcher);
    watcher.promise.then((job) => {
      run.disabled = false;
      if (job.state === "done") drawResult(holder, job.result || {});
      else if (job.state === "error") replace(holder.querySelector(".pb"), notice({ kind: "error" }, h("p", {}, job.error || "The test failed.")));
      else replace(holder.querySelector(".pb"), h("p", { class: "muted" }, "Stopped."));
    }).catch((e) => { run.disabled = false; showError(e); });
  }
  function drawResult(holder, r) {
    const cols = r.table && r.table.length ? Object.keys(r.table[0]).filter((c) => c !== "measure") : [];
    replace(holder.querySelector(".pb"),
      h("p", {}, h("strong", {}, `${r.model || ""}`), h("span", { class: "muted" }, ` (${r.backend || ""})`)),
      h("ul", { class: "plain-steps" }, (r.verdict || []).map((l) => h("li", {}, l))),
      cols.length ? h("div", { class: "table-wrap" }, h("table", { class: "table table-responsive bench-table" }, h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Measure"), cols.map((c) => h("th", { scope: "col", class: "num" }, c)))),
        h("tbody", {}, (r.table || []).map((row) => h("tr", {}, h("td", {}, row.measure), cols.map((c) => h("td", { class: "num", "data-label": c }, String(row[c] ?? "–")))))))) : null,
      h("div", { class: "btn-row set-result-actions" }, downloadButton({ onClick: () => {
        const blob = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
        saveBlob(blob, `benchmark_${(r.model || "model").replace(/[^A-Za-z0-9_-]/g, "_")}.json`);
      } }, "Download the full result")));
  }
  return sectionCard("test", "Test a model before trusting it", "For technical users. It compares the AI model of Settings › AI with reference answers saved in a project (for the pilot, those were made earlier with Claude Opus 5.5). Nothing is stored, and the test tasks go only where that model reads: a model on this computer keeps them here; the Claude API is sent one call per task, and billed for it. This measures agreement with the reference, not correctness.",
    field("Reference workspace folder", ref, { help: "For example the pilot folder that ships with the package." }),
    h("div", { class: "fields-2" }, n, h("div", { class: "field" }, h("span", { class: "field-label" }, "Tasks"), h("label", { class: "it", for: "k-verify" }, kVerify, " Checking claims"), h("label", { class: "it", for: "k-extract" }, kExtract, " Extracting claims"), h("label", { class: "it", for: "k-label" }, kLabel, " Labelling with codes"))),
    h("div", { class: "save-row" }, withAI(run)),
    readsLine("the test tasks"),
    out);
}

// 0.10.1: the version, on every Settings tab; it opens Technical → Where your data is, which says how this copy was
// installed and how to update it
function versionTag() {
  const st = App.state || {};
  const v = st.version || VERSION;
  if (!v) return null;
  // 0.10.2: updated while it ran: the newer version waits for a restart (the banner above the page says how)
  const now = st.installed_version && st.installed_version !== v ? st.installed_version : null;
  // 0.17.0 (design guide): the version is words with a link to Updates, not a pill; a newer one installed is a fact that
  // needs you (an attention tag)
  // After 0.17.2: then What's new, always here (a note in the corner no longer shows it by itself)
  return h("span", { class: "version-tag" },
    link({ href: "#/settings/updates", title: now ? `Margin ${now} is installed: restart Margin to use it` : "Check for updates, and how Margin was installed (Technical)" },
      "Version ", v),
    whatsNewLink(),
    now ? tag({ kind: "attention" }, `${now} installed: restart to use it`) : null);
}

// 0.10: how this copy was installed, and how it is updated
function installedWith(inst) {
  if (!inst || !inst.kind) return null;
  const how = { git: ["from a git copy", "Update: margin update"], script: ["with the one-line install", "Update: run the install line again (or margin update)"],
    package: ["from the download for this system", "Update: download the newest version"], pip: ["with pip", "Update: pip install --upgrade, or switch to the one-line install"] }[inst.kind];
  return h("div", { class: "muted small" }, `Installed ${how[0]}. ${how[1]}.`);
}

// 0.13.6: Check for updates. The sidebar's Update button shows only when there is one (the page looks every two
// minutes); here the person can look now, and read why a look failed (offline, a git copy edited by hand).
function updatesSection() {
  const st = App.state || {};
  const name = appName();
  const out = h("div", { "aria-live": "polite" });
  const btn = button({}, icon("refresh", { size: 14 }), "Check for updates");
  const at = (t) => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const show = (info, err, when) => {
    if (err) {
      replace(out, notice({ kind: "attention" },
        h("p", {}, h("strong", {}, "Could not look for updates.")), h("p", { class: "small" }, err.message || String(err))));
      return;
    }
    if (!info) { clear(out); return; }
    if (!info.available) {
      replace(out, h("p", { class: "small" }, icon("check", { size: 14 }), ` ${name} ${info.version} is the newest version.`,
        when ? h("span", { class: "muted" }, ` Looked at ${at(when)}.`) : null));
      return;
    }
    const what = info.on_disk ? `${name} ${info.latest} is installed, but ${info.version} is still running.`
      : info.latest ? `${name} ${info.candidate ? "release candidate " : ""}${info.latest} is available (you have ${info.version}).`
      : `${info.changes} new change${info.changes === 1 ? " is" : "s are"} waiting for this copy of ${name} (version ${info.version}).`;
    replace(out, notice({ kind: "info", icon: "arrow-up" },
      h("p", {}, h("strong", {}, what)),
        st.can_restart
          ? h("p", {}, button({ kind: "main", sm: true, onClick: () => Updates.install() }, icon("arrow-up", { size: 13 }), info.on_disk ? "Restart now" : "Update and restart"))
          : h("p", { class: "small" }, "This copy cannot restart itself (it was not started from its icon or with margin-gui): run ", h("code", {}, "margin update"), ` in a terminal, then start ${name} again.`)));
  };
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    replace(out, h("p", { class: "muted small" }, "Looking for a newer version…"));
    try { show(await checkUpdate(true), null, Date.now()); } catch (e) { show(null, e); }
    btn.disabled = false;
  });
  if (Updates.info || Updates.error) show(Updates.info, Updates.error, Updates.at);  // what the last look found
  // After 0.17.2: what is new in this version, here as well (Find comes here for it)
  const changes = h("span", {});
  loadWhatsNew().then(() => {
    if (WhatsNew.changes) replace(changes, button({ kind: "quiet", sm: true, icon: "sparkles", "aria-haspopup": "dialog", onClick: () => showWhatsNew() }, `What's new in ${WhatsNew.changes.version}`));
  });
  return sectionCard("updates", "Updates", st.can_restart
    ? `${name} looks for a new version when it opens and every two minutes after. When there is one, it says so in a pop-up, and an Update button appears at the bottom of the sidebar until you install it. Your projects and results are kept.`
    : `Look for a new version of ${name}. Your projects and results are kept when you update.`,
    channelField(st), h("div", { class: "save-row" }, btn, changes), out, problemRow(),
    // 0.17.0: while an update waits, its button takes Quit's place at the foot of the sidebar: Quit is here too
    st.can_quit && Updates.quit ? h("div", { class: "save-row" }, button({ onClick: () => Updates.quit() }, icon("power", { size: 14 }), `Quit ${name}`),
      h("span", { class: "muted small" }, "Stops the app on this computer; your projects and results are kept.")) : null);
}

// 0.17.2: the link that opens Margin (the page itself carries no key: lib.js ensureToken), for a bookmark. It holds
// this run's key, so it works until Margin stops, and it opens Margin for whoever has it.
function linkSection() {
  const name = appName();
  const btn = button({}, icon("link", { size: 14 }), "Copy my link");
  const box = h("div", {});
  btn.addEventListener("click", async () => {
    const url = myLink();
    try { await navigator.clipboard.writeText(url); toast("Copied. Keep it to yourself.", "ok", { ttl: 2500 }); }
    catch (_) { replace(box, h("code", { class: "copy-code" }, url)); toast("Select the link and copy it with Ctrl+C (or Cmd+C).", "info"); }
  });
  return sectionCard("link", `Your link to ${name}`, `${name} opens with a key in its link, so no one else on this computer can use it. Its icon (or margin-gui) opens that link for you; the address alone shows how to open ${name}.`,
    notice({ kind: "attention" }, h("p", {}, h("strong", {}, `The link opens ${name} for whoever has it`), `, with all your projects, while ${name} runs. Do not share it or post it.`)),
    h("div", { class: "save-row" }, btn, h("span", { class: "muted small" }, `For a bookmark. It works until ${name} stops; after it starts again, copy it again.`)), box);
}

// 0.15: which versions the update check offers. A git copy follows main and has no choice.
function channelField(st) {
  if (st.installation && st.installation.kind === "git")
    return h("p", { class: "muted small" }, icon("info", { size: 13 }), ` This copy of ${appName()} is a git copy: it follows the main branch, so there is no choice of versions here.`);
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const sel = selectField({ id: "update-channel" },
    [["stable", "Stable (recommended)"], ["early", "Try new versions early"]].map(([v, t]) => h("option", { value: v, selected: ((st.settings || {}).update_channel || "stable") === v }, t)));
  sel.addEventListener("change", async () => {
    try { await save({ update_channel: sel.value }, state); checkUpdate(true).catch(() => {}); } catch (_) { /* shown */ }
  });
  return h("div", {}, field("Which new versions to offer", sel, { help: "From 0.16 on, a release candidate (a try-out of the next version) comes out at least a week before each new version, so you can try it on your own projects. Try it on a project you do not share with colleagues: going back to the stable version can show sync clashes (nothing is lost)." }), state);
}

// 0.15: a problem report without knowing GitHub: the technical details to paste, and the form to paste them in.
// After 0.18.0rc2: the repository itself too, for the code, the releases and the roadmap.
const REPO_URL = "https://github.com/dvaud/margin";
function problemRow() {
  const btn = button({}, icon("copy", { size: 14 }), "Copy technical details");
  btn.addEventListener("click", async () => {
    try {
      const r = await api("GET", "/api/technical-details");
      try { await navigator.clipboard.writeText(r.text); toast("Copied. Paste it in your problem report.", "ok", { ttl: 2500 }); }
      catch (_) { replace(box, h("pre", { class: "mono small tech-details" }, r.text)); toast("Select the text and copy it with Ctrl+C (or Cmd+C).", "info"); }
    } catch (e) { showError(e); }
  });
  const box = h("div", {});
  return h("div", {}, h("p", { class: "muted small set-problem-help" }, "Something does not work? Copy the technical details (the version, the system and the AI route: no file names, project names or keys) and paste them in a report."),
    h("div", { class: "save-row" }, btn,
      link({ kind: "external", href: `${REPO_URL}/issues/new?template=problem.yml` }, "Report a problem (on GitHub)"),
      link({ kind: "external", href: REPO_URL }, "Source code (on GitHub)")), box);
}

// 0.11: every passage sent to Claude, as a table for records such as a data management plan
function ledgerSection() {
  const project = App.project;
  return sectionCard("ledger", "What was sent to Claude", "Margin writes down every passage it sends to Claude (Claude Code, the Claude API, or a Claude chat through the connector) at the moment it leaves: when, by which route, for which feature. The Documents page shows the share of each document; here is the whole list as a spreadsheet file.",
    project ? downloadButton({ onClick: () => download(`/api/projects/${P(project)}/ai-sent.csv`).catch(showError) }, `Download the list for “${project}” (CSV)`)
      : h("p", { class: "muted small" }, "Open a project first."));
}

// ---------------------------------------------------------------------------------------------
function dataSection() {
  const st = App.state || {};
  const ocr = st.ocr || {};
  return sectionCard("data", "Where your data is", "Everything the app keeps lives in one folder on this computer.",
    h("dl", { class: "kv-grid" },
      h("div", { class: "kv" }, h("dt", {}, "Data folder"), h("dd", {}, h("code", { class: "path", title: st.home || "" }, ...String(st.home || "").split(/(?<=[\/\\])/).flatMap((seg) => [seg, h("wbr")])))),
      h("div", { class: "kv" }, h("dt", {}, "Projects"), h("dd", {}, `${(st.projects || []).length}`, " · ", h("a", { href: "#/projects" }, "manage"))),
      h("div", { class: "kv" }, h("dt", {}, "Version"), h("dd", {}, `Margin ${st.version || VERSION}`, installedWith(st.installation))),
      h("div", { class: "kv" }, h("dt", {}, "Network"), h("dd", {}, "This computer only · nothing is loaded from the internet")),
      h("div", { class: "kv" }, h("dt", {}, "Text recognition (OCR) for scanned PDFs"), h("dd", {}, ocr.available ? `installed (Tesseract${ocr.languages && ocr.languages.length ? `, languages: ${ocr.languages.join(", ")}` : ""})`
        : ["not available", ocr.missing && ocr.missing.length ? h("div", { class: "muted small" }, `Missing: ${ocr.missing.map((m) => ({ tesseract: "the Tesseract program (tesseract-ocr)", pypdfium2: "the Python package pypdfium2", pillow: "the Python package pillow" }[m] || m)).join("; ")}.${ocr.missing.includes("tesseract") ? " How to get Tesseract: Settings → Documents." : ""}${ocr.missing.some((m) => m !== "tesseract") ? " The Python parts: pip install 'margin[ocr]', then restart the app." : ""}`) : null]))),
    h("p", { class: "muted small set-data-note" }, "Each project is a folder with a database, the added files and the settings. Removed projects go to a trash folder inside the data folder."));
}

// ---------------------------------------------------------------------------------------------
// 0.9: setting up Claude Code, as a checklist: Claude Code found, signed in, the Margin plugin added.
// 0.10: one button, "Set up Claude", does every step it can, in order, and skips what is done: it installs Claude Code
// with Anthropic's installer (after the person has seen and confirmed the command), opens a window where the person
// signs in with their Claude plan (Margin never sees the login) and waits for it, then adds the plugin. Doing it by
// hand stays one fold below. Used in Settings → AI and on the first-run page.
// Providers stage 2: the button opens the steps in a dialog (agent-setup.js, the way a storage space or an API key is
// set up), shared with Codex and Antigravity; the checklist card stays. The install step shows the command and its own
// button is the confirmation.
// 0.13.4: the account Claude Code is signed in to, as it says it ("you@uni.nl · Team plan · Uni"); the kinds of plan
// when it does not say.
function accountText(st) {
  const acc = claudeAccount(st);
  if (!acc || !acc.email) return acc && acc.plan ? acc.plan : "Pro, Max, Team or Enterprise";
  return [acc.email, acc.plan, acc.org].filter(Boolean).join(" · ");
}

// One line of a set-up's checklist: done (a tick), still to do (the triangle, in amber) or not known yet (?).
const checkStep = (ok, title, text) => h("li", { class: "cc-step", "data-state": ok === true ? "done" : ok === false ? "todo" : null },
  h("span", { class: "cc-mark", "aria-hidden": "true" }, ok === true ? icon("check", { size: 12 }) : ok === false ? icon("alert-triangle", { size: 14 }) : "?"),
  h("div", {}, h("strong", {}, title), text ? h("span", { class: "small" }, text) : null));

// Providers stage 2 (B4): an agent's checklist card, the same for Claude Code, Codex and Antigravity: found, signed in,
// Margin added, and one button. The button opens the set-up's guided steps in a dialog (agent-setup.js), which opens at
// the first step not done; once all is ready it reads the state again. `ad`: the agent's adapter; `ad.cardWords(st)`
// may give the card's own words. opts: kind (the button's kind while not ready: "main" on the first-run page,
// "standard" in Settings, whose card's main action is Save), onReady(), onInfo(info) after every reading, extra(info,
// ready) for lines under the button. When the set-up cannot be read (a Margin that does not know the agent yet, or
// a failed answer), the card says so and offers Try again.
function agentCard(ad, opts = {}) {
  const box = card({ as: "div", class: "cc-card", dataset: { agent: ad.route } }, h("p", { class: "muted small" }, `Looking for ${ad.title} on this computer…`));
  let info = null, failed = "";
  const got = (i) => { info = i; failed = ""; if (opts.onInfo) opts.onInfo(i); draw(); };
  const read = async (refresh) => {
    try { got(await ad.read(refresh)); } catch (e) { failed = e.message || String(e); if (opts.onInfo) opts.onInfo(info); draw(); }
  };
  const open = async () => {
    await agentSetupDialog(ad, info || {}, { project: App.project, onChange: got });
    await read(true);
  };
  function draw() {
    if (!info) {
      replace(box, h("div", { class: "field-label" }, `Set up ${ad.title}`),
        notice({ kind: "attention", class: "cc-now" }, h("p", {}, `The set-up of ${ad.title} could not be read${failed ? `: ${failed}` : "."}`),
          h("p", { class: "small" }, "This copy of Margin may not know it yet, or it did not answer. Try again in a moment.")),
        h("div", { class: "btn-row" }, button({ sm: true, icon: "refresh", onClick: () => read(true) }, "Try again")));
      return;
    }
    const st = info.status || {};
    const ready = !!st.ready && st.signed_in !== false;
    if (ready && opts.onReady) opts.onReady();
    const w = (ad.cardWords || cliCardWords)(st, ad);
    const btn = button({ kind: ready ? "standard" : opts.kind || "main", sm: ready, onClick: () => (ready ? read(true) : open()) },
      icon(ready ? "refresh" : "zap", { size: 14 }), ready ? "Check again" : w.button);
    replace(box,
      h("div", { class: "field-label" }, ready ? w.ready : w.head),
      h("ol", { class: "cc-steps" }, w.rows.map(([ok, title, text]) => checkStep(ok, title, text))),
      h("div", { class: "btn-row" }, btn),
      ...(opts.extra ? [].concat(opts.extra(info, ready)) : []).filter(Boolean));
  }
  read(false);
  return box;
}

// The checklist's words for an agent CLI (Codex, Antigravity)
function cliCardWords(st, ad) {
  const finish = st.found && st.signed_in === true && st.connector === false;
  return {
    // found and signed in, Margin not added: only the last step is left, and the button opens the set-up there
    head: finish ? "Finish the set-up" : `Set up ${ad.title} (once)`, ready: `${ad.title} is ready`, button: finish ? `Add Margin to ${ad.title}…` : `Set up ${ad.title}…`,
    rows: [
      [st.found ? true : false, `${ad.title} on this computer`, st.found ? (st.version || "found") : `Not on this computer yet. The set-up installs it with ${ad.company}’s installer (it shows you the command first).`],
      [st.signed_in === true ? true : st.signed_in === false ? false : null, `Signed in with ${ad.account}`,
        st.signed_in === true ? (st.account || "") : st.signed_in === false ? "Not yet. The set-up opens the sign-in for you." : `${ad.title} asks you to sign in once; the set-up opens the sign-in for you.`],
      [st.connector === true ? true : st.found ? false : null, `Margin added to ${ad.title}`,
        st.connector === true ? "Its connector, its skill and its helpers." : `The set-up adds Margin’s connector, skill and helpers (nothing else in ${ad.title} is changed).`],
    ],
  };
}

// lines to type, when the person sets it up by hand
const manualFold = (lines, docs, title) => fold({}, "Set it up yourself instead",
  h("ol", { class: "cc-manual small" },
    docs ? h("li", {}, "Follow ", h("a", { href: docs, target: "_blank", rel: "noopener" }, `${title}’s set-up page`), ".") : null,
    (lines || []).map((l) => h("li", {}, copyLine(l, "Copy", "a terminal")))));

// Codex or Antigravity's card in Settings → AI
export function agentSetupCard(route, opts = {}) {
  const ad = cliAdapter(route);
  return agentCard(ad, { kind: "standard", ...opts,
    extra: (info) => [
      h("p", { class: "muted small set-claude-code-hint" }, "Then press ", h("strong", {}, `Start ${ad.title}`), " wherever work waits (or in the sidebar): Margin starts it in the background on this project’s work, and the results appear as they come in."),
      (info.manual || []).length ? manualFold(info.manual, info.docs, ad.title) : null] });
}

// Claude Code's adapter for the shared set-up (agent-setup.js), on /api/claude-setup. What it reads is the sidebar's
// too (the account on its "Claude, on your plan" card).
function claudeAdapter() {
  const DOCS = "https://code.claude.com/docs/en/setup";
  const finish = (st) => st.found && st.signed_in === true && st.installed === false;   // only the plugin is left
  return {
    route: "claude_code", title: "Claude Code", company: "Anthropic", program: "claude", account: "your Claude plan",
    installer: "curl -fsSL https://claude.ai/install.sh | bash", docs: DOCS,
    read: async (refresh) => {
      const r = await api("GET", refresh ? "/api/claude-setup?refresh=1" : "/api/claude-setup");
      const st = rememberClaude(r.status || {});
      return { ...r, status: { ...st, connector: st.installed }, installer: r.installer || "curl -fsSL https://claude.ai/install.sh | bash", docs: r.docs || DOCS };
    },
    install: async () => (await api("POST", "/api/claude-setup/claude-code", {})).job,
    signIn: () => api("POST", "/api/claude-setup/sign-in", {}),
    addMargin: () => api("POST", "/api/claude-setup", {}),
    installWhy: () => h("div", { class: "stack set-install-body" },
      h("p", {}, "Claude Code is the program that lets Claude work on your own Claude plan. Margin runs Anthropic's installer for it, which downloads Claude Code from claude.ai and puts it in your user folder. It needs no administrator rights and takes a minute or two."),
      // the place a program is kept does not limit what it can open: the folder it starts in and its permissions do
      h("p", { class: "small" }, icon("house", { size: 13 }), " Where the program is kept does not decide what it can read. Margin starts Claude Code only in an empty folder of its own, with its tools for reading files, running commands and browsing switched off, so it cannot look through your computer: it sees only the passages in Margin's tasks.")),
    signInIntro: ["Press the button: a window opens with Claude Code, in an empty folder of Margin, away from your files. Sign in there with your Claude plan.",
      "Sign in in the window that opens; close it when it shows its prompt."],
    signInWords: (opened) => (opened.opened
      ? h("p", {}, `A ${opened.window} window opened with Claude Code. Sign in there with your Claude plan (it opens a page in your browser), then close that window. This step moves on by itself.`)
      : h("div", {}, h("p", {}, "Sign in to Claude Code once: open a terminal (Terminal on a Mac, PowerShell on Windows), type the line below, and follow the steps. It starts Claude Code in an empty folder of Margin, away from your files."), copyLine(opened.command || "claude", "Copy", "a terminal"))),
    adds: ["the Margin connector, through which Claude Code takes the tasks and sends back its answers", ["the command ", h("code", {}, "/margin-run")], "its helpers, one for each kind of task"],
    afterWords: (project) => [
      h("p", {}, "Press ", h("strong", {}, "Start Claude Code"), " wherever work waits (or in the sidebar): Margin starts Claude Code in the background on this project's work, and the results appear as they come in."),
      h("p", { class: "muted small" }, "You can also type ", h("code", {}, `/margin-run ${project || "<project>"}`), " in Claude Code yourself.")],
    applied: () => h("p", { class: "provider-applied" }, "Applied automatically: Haiku for labels and links, Sonnet for judging excerpts and Opus for second opinions. How much thought, in Settings → AI, moves each one step lighter or stronger."),
    cardWords: (st) => ({
      head: finish(st) ? "Finish the set-up" : "Set up Claude (once)", ready: "Claude is ready", button: finish(st) ? "Add Margin to Claude Code…" : "Set up Claude…",
      rows: [
        [st.found ? true : false, "Claude Code on this computer", st.found ? (st.version || "found") : "Not on this computer yet. The set-up installs it with Anthropic's installer (it shows you the command first)."],
        [st.signed_in === true ? true : st.signed_in === false ? false : null, "Signed in with your Claude plan",
          st.signed_in === true ? accountText(st) : st.signed_in === false ? "Not yet. The set-up opens a window where you sign in once." : "Claude Code asks you to sign in once; the set-up opens the window for it."],
        [st.installed === true ? true : st.found ? false : null, "The Margin plugin added to Claude Code",
          st.installed ? "It adds /margin-run, its helpers and the Margin connector." : "The set-up adds it (nothing else in Claude Code is changed)."],
      ] }),
  };
}

export function claudeSetupCard(opts = {}) {
  return agentCard(claudeAdapter(), { ...opts,
    extra: (info, ready) => {
      const st = info.status || {};
      return [
        ready || st.signed_in ? termsPanel({ account: st.account || "", detected: st.plan ? `${st.plan[0].toUpperCase()}${st.plan.slice(1)}` : null, kind: st.account }) : null,
        h("p", { class: "muted small set-claude-code-hint" }, "Then press ", h("strong", {}, "Start Claude Code"), " wherever work waits (or in the sidebar): Margin starts Claude Code in the background on this project's work, and the results appear as they come in. You can also type ", h("code", {}, `/margin-run ${App.project || "<project>"}`), " in Claude Code yourself."),
        fold({}, "Set it up yourself instead",
          h("ol", { class: "cc-manual small" },
            h("li", {}, "Install Claude Code (", h("a", { href: info.docs, target: "_blank", rel: "noopener" }, "Anthropic's set-up page"), "), in a terminal:", info.installer ? copyLine(info.installer, "Copy", "a terminal") : null),
            h("li", {}, "Sign in once: type ", h("code", {}, "claude"), " in a terminal and follow the steps."),
            (info.commands || []).length ? h("li", {}, "Add the Margin plugin with these two lines in a terminal, then restart Claude Code:", info.commands.map((c) => copyLine(c, "Copy", "a terminal"))) : null)),
      ];
    } });
}
