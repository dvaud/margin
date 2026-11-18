// 0.11: who may read each document with AI. The three settings, the question asked when documents are added (and
// once for a project that has none), the setting of each document on the Documents page, what Claude has read of a
// document, and the panel "What happens to the text Claude reads" (Set up Claude, Settings → AI).
import { App, api, h, icon, replace, toast, showError, fmt, P, dialog, button, iconButton, link, notice, card, choice, input, select, fold, tag, optionCards } from "../lib.js";  // eslint-disable-line no-unused-vars
import { localModelHelp } from "./local-model.js";

// Stage 1 of other cloud providers: while no provider but Anthropic is set up, "cloud" keeps its words ("Claude may
// read it"); once one is (a key stored, or the main route), it says "Cloud AI may read it", and which providers may
// read each document is ticked under it (project default and per document).
const providersState = () => (App.state && App.state.providers) || {};
export const othersSetUp = () => !!providersState().other_set_up && !(App.state && App.state.local_only);
const CLOUD_CLAUDE = { title: "Claude may read it", many: "Claude may read them", short: "Claude",
  sub: "Read by the AI you chose: Claude Code, the Claude API, or a local model." };
const CLOUD_ANY = { title: "Cloud AI may read it", many: "Cloud AI may read them", short: "Cloud AI",
  sub: "Read by the AI you chose, when its provider is ticked for the document: Claude, another cloud provider, or a local model." };
const cloudWords = () => (othersSetUp() ? CLOUD_ANY : CLOUD_CLAUDE);
// where the text read goes, in the words of the page: "Claude", or "cloud AI" once another provider is set up
export const sentToWords = () => (othersSetUp() ? "cloud AI" : "Claude");
const isDefault = (list) => !list || (list.length === 1 && list[0] === "anthropic");
// the provider tick boxes show once another provider is set up, or while any allowance differs from the default
export const providersInPlay = (info = {}, docs = []) => othersSetUp() || !isDefault(info.providers_default) || docs.some((d) => d.providers_own != null);

export const LEVEL = {
  cloud: { get title() { return cloudWords().title; }, get many() { return cloudWords().many; },
    get short() { return cloudWords().short; }, icon: "cloud", get sub() { return cloudWords().sub; } },
  local: { title: "Only a local AI", many: "Only a local AI", short: "Local AI", icon: "house",
    sub: "Read only by a model on this computer, or by you. Never sent to Claude." },
  none: { title: "No AI", many: "No AI", short: "No AI", icon: "eye-off",
    sub: "Only you judge its excerpts. Search, the keyword codes, concepts and themes still work." },
};
const CHECKED = "30 October 2026";
const DATA_USAGE = "https://code.claude.com/docs/en/data-usage";
const PRIVACY_SETTING = "https://claude.ai/settings/data-privacy-controls";

const localOnly = () => !!(App.state && App.state.local_only);
export const levels = () => (localOnly() ? ["local", "none"] : ["cloud", "local", "none"]);

export function accessBadge(level, opts = {}) {
  const L = LEVEL[level] || LEVEL.none;
  return tag({ class: `access-badge access-${level}`, title: L.title, icon: L.icon }, opts.long ? L.title : L.short,
    opts.count !== undefined ? `: ${opts.count} ${opts.count === 1 ? "document" : "documents"}` : null);   // a number says what it counts
}

// The question "Who may read these documents with AI?": three choices, one preselected (or none, the first time).
export function accessChoice({ value = null, name = "ai-access", many = true, onChange } = {}) {
  const wrap = h("fieldset", { class: "access-choice" },
    h("legend", { class: "field-label" }, many ? "Who may read these documents with AI?" : "Who may read this document with AI?"));
  wrap.value = value;
  // option cards holding real radio inputs (docs/DESIGN.md 4.7)
  wrap.appendChild(optionCards({ name, value, class: "access-options", label: many ? "Who may read these documents with AI?" : "Who may read this document with AI?",
    options: levels().map((lv) => ({ value: lv, icon: LEVEL[lv].icon, title: many ? LEVEL[lv].many : LEVEL[lv].title, text: LEVEL[lv].sub })),
    onPick: (lv) => { wrap.value = lv; if (onChange) onChange(lv); } }));
  return wrap;
}

// A project without a default (made before 0.11 and imported, or made through the connector): asked once.
export function accessAskCard(project, info, onDone) {
  let picked = null;
  const btn = button({ kind: "main", disabled: true }, icon("check", { size: 14 }), "Use this for the project");
  const pick = accessChoice({ name: "ask-default", onChange: (v) => { picked = v; btn.disabled = false; } });
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try { await api("PUT", `/api/projects/${P(project)}/ai-access`, { default: picked }); toast(`${LEVEL[picked].many}: this applies to every document without its own setting.`, "ok"); onDone(); }
    catch (e) { showError(e); btn.disabled = false; }
  });
  return card({ class: "access-ask", "aria-label": "Who may read these documents with AI" },
    h("h2", {}, icon("cloud", { size: 16 }), "Who may read this project's documents with AI?"),
    h("p", { class: "muted" }, "Say it once for the whole project; you can change single documents below. Until you choose, Claude may read them, as before."),
    pick, h("div", { class: "btn-row aia-actions" }, btn));
}

export function accessBanner(project, onDismiss) {
  const close = iconButton({ icon: "x", size: 14, label: "Dismiss", title: null, onClick: async () => {
    try { await api("PUT", `/api/projects/${P(project)}/ai-access`, { dismiss_banner: true }); } catch (_) { /* shown next time */ }
    onDismiss();
  } });
  return notice({ kind: "info", icon: "info", class: "access-banner", role: "status" },
    h("div", { class: "grow" }, h("p", {}, h("strong", {}, "New in 0.11: choose which documents Claude may read. "),
      "Mark a licensed PDF or an interview transcript as ", h("em", {}, "Only a local AI"), " or ", h("em", {}, "No AI"),
      " in a document's details: ", link({ kind: "jump", onClick: () => { const t = document.querySelector(".doc-toggle"); if (t) { t.scrollIntoView({ block: "center" }); t.focus(); } } }, "the arrow at the end of its row"),
      ". Everything else stays as it was.")), close);
}

// The cloud providers' names (Settings' table), the ones a person can tick (Anthropic, those set up, those allowed
// already) and a line of how much each has read.
export const providerTitle = (id) => (id === "other" ? "A server on another computer"
  : ((providersState().list || []).find((p) => p.id === id) || {}).title || id);
const tickable = (allowed = []) => {
  const st = providersState();
  const ids = new Set(["anthropic", ...(st.set_up || []), ...allowed]);
  const order = [...(st.list || []).map((p) => p.id), "other"];
  return order.filter((id) => ids.has(id));
};

// Checkboxes of the cloud providers that may read (a document, or the project's documents without their own choice).
// In a shared project only Anthropic may read: the others are off, and one line says why.
let checksMade = 0;
export function providerChecks({ value = ["anthropic"], shared = false, note = "", legend = "Which cloud providers may read it", onChange } = {}) {
  const wrap = h("fieldset", { class: "provider-checks" }, h("legend", { class: "field-label" }, legend));
  const boxes = [];
  const n = ++checksMade;
  for (const id of tickable(value)) {
    const off = shared && id !== "anthropic";
    const box = h("input", { type: "checkbox", id: `prov-${n}-${id}`, value: id, checked: value.includes(id) && !off, disabled: off });
    box.addEventListener("change", () => { if (onChange) onChange(wrap.picked()); });
    boxes.push(box);
    wrap.append(h("label", { class: "it small provider-check", for: box.id }, box, " ", providerTitle(id)));
  }
  if (shared) wrap.append(h("p", { class: "muted small" }, icon("info", { size: 13 }), " ", note || "Other providers come to shared projects later: your colleagues have not agreed to them."));
  wrap.picked = () => boxes.filter((b) => b.checked).map((b) => b.value);
  return wrap;
}

// How much each cloud provider has read of a document ("" when only Claude has): "Claude 12% · OpenAI 3%".
export function sentByLine(doc) {
  const by = doc.sent_by || {};
  const ids = Object.keys(by).filter((id) => by[id] > 0);
  if (!ids.some((id) => id !== "anthropic")) return "";
  const pct = (x) => { const v = Math.round(x * 1000) / 10; return v < 1 ? "less than 1%" : `${Math.round(v)}%`; };
  return ids.map((id) => `${id === "anthropic" ? "Claude" : providerTitle(id)} ${pct(by[id])}`).join(" · ");
}

// The project's choice of cloud providers, on the Documents page, once another provider is set up: who may read the
// documents marked Cloud AI may read it that have no choice of their own.
export function providersDefaultCard(project, info, onSaved, docs = []) {
  if (!providersInPlay(info, docs)) return null;
  let picked = info.providers_default || ["anthropic"];
  const st = h("span", { class: "save-state", "aria-live": "polite" });
  const btn = button({ sm: true, disabled: true }, icon("check", { size: 13 }), "Save");
  const checks = providerChecks({ value: picked, shared: !!info.shared, note: info.providers_note || "", legend: "Cloud providers that may read this project's documents",
    onChange: (v) => { picked = v; btn.disabled = !v.length; st.textContent = v.length ? "Not saved yet." : "Tick at least one, or mark the documents Only a local AI."; } });
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try { const r = await api("PUT", `/api/projects/${P(project)}/ai-access`, { providers_default: picked }); st.textContent = "Saved."; if (onSaved) onSaved(r); }
    catch (e) { showError(e); btn.disabled = false; }
  });
  const now = (info.providers_default || ["anthropic"]).map(providerTitle).join(", ");
  return fold({ class: "providers-default" }, `${CLOUD_ANY.title}: ${now}`,
    h("div", { class: "stack" }, h("p", { class: "muted small" }, "For the documents marked Cloud AI may read it without a choice of their own. A document not ticked for the AI you chose is read as Only a local AI. Change one document in its AI setting."),
      checks, h("div", { class: "row" }, btn, st)));
}

// A model server on another computer as the main route (stage 1 of other cloud providers): it reads only the documents
// allowed to it ("other", or the provider of its address). One line, and a button that allows it for the project; no
// pop-up. `onAllowed(res)` after the project's choice was saved.
export function remoteServerLine(project, info = {}, onAllowed) {
  const st = providersState();
  const route = st.route, address = st.route_address;
  if (!address || !route || route === "anthropic") return null;
  const allowed = (info.providers_default || ["anthropic"]).includes(route);
  const words = `A server on another computer (${address}) reads only documents you allow it to.`;
  if (!project) return notice({ kind: "info", class: "remote-server-line" }, h("p", {}, words, " Allow it for a project on its Documents page."));
  if (allowed) return notice({ kind: "info", class: "remote-server-line" }, h("p", {}, words, " This project allows it."));
  if (info.shared) return notice({ kind: "info", class: "remote-server-line" }, h("p", {}, words, " ", info.providers_note || "Other providers come to shared projects later: your colleagues have not agreed to them."));
  const btn = button({ sm: true, onClick: async () => {
    btn.disabled = true;
    try { const r = await api("PUT", `/api/projects/${P(project)}/ai-access`, { providers_default: [...(info.providers_default || ["anthropic"]), route] }); toast(`${providerTitle(route)} may read this project's documents marked ${CLOUD_ANY.title}.`, "ok"); if (onAllowed) onAllowed(r); }
    catch (e) { showError(e); btn.disabled = false; }
  } }, "Allow it for this project");
  return notice({ kind: "info", class: "remote-server-line" }, h("p", {}, words, " Until you do, its documents are read by your local model or wait for you."), h("div", { class: "row" }, btn));
}

// What Claude has read of a document, its note and its cap.
export async function docAccessDialog(project, doc, projectDefault, onSaved, info = {}) {
  let sent = { passages: [], share: doc.sent || 0 };
  try { sent = await api("GET", `/api/projects/${P(project)}/documents/${P(doc.doc_id)}/ai-sent`); } catch (e) { showError(e); }
  let level = doc.ai_access;
  const showProviders = providersInPlay(info, [doc]);
  const pick = accessChoice({ value: level, many: false, name: "doc-access", onChange: (v) => { level = v; capBox.hidden = v !== "cloud"; if (provBox) provBox.hidden = v !== "cloud"; } });
  // stage 1 of other cloud providers: which ones may read this document (its own choice, or the project's)
  const projectProviders = info.providers_default || ["anthropic"];
  let provs = doc.providers || projectProviders;
  const provBox = showProviders ? providerChecks({ value: provs, shared: !!info.shared, note: info.providers_note || "", onChange: (v) => { provs = v; } }) : null;
  if (provBox) provBox.hidden = level !== "cloud";
  const note = input({ maxlength: 300, value: doc.note || "", placeholder: "e.g. publisher licence, contains interview data", id: "acc-note" });
  const cap = input({ sm: true, type: "number", min: 1, max: 100, step: 1, value: doc.budget ?? "", placeholder: "none", id: "acc-cap", class: "aia-cap" });
  const capBox = h("div", { class: "field", hidden: level !== "cloud" },
    h("label", { class: "field-label", for: "acc-cap" }, `${othersSetUp() ? "Cloud AI" : "Claude"} may read at most`),
    h("div", { class: "row aia-cap-row" }, cap, h("span", {}, "% of this document")),
    h("div", { class: "field-help" }, `Optional. Once ${sentToWords()} has read that much (every cloud provider counts), the rest is treated as Only a local AI. A check that is running may go over by one round.`));
  const byLine = sentByLine(doc);
  const share = Math.round((sent.share || 0) * 1000) / 10;
  const list = sent.passages.length ? h("ul", { class: "sent-list" }, sent.passages.slice(0, 200).map((x) =>
    h("li", {}, h("a", { href: `#/doc/${encodeURIComponent(doc.doc_id)}` }, x.page ? `Page ${x.page}` : `Passage ${x.seq != null ? x.seq + 1 : ""}`),
      h("span", { class: "muted small" }, ` · ${x.features.join(", ")} · ${x.routes.join(", ")} · ${fmt.dateShort(x.last)}${x.times > 1 ? ` · ${x.times} times` : ""}`),
      x.preview ? h("div", { class: "small sent-preview" }, x.preview, "…") : null)))
    : h("p", { class: "muted small" }, `${othersSetUp() ? "No cloud AI" : "Claude"} has read nothing of this document` + (sent.since ? " since Margin began keeping this list." : "."));
  const body = h("div", { class: "stack aia-body" },
    pick, provBox,
    h("div", { class: "field" }, h("label", { class: "field-label", for: "acc-note" }, "Why (optional)"), note,
      h("div", { class: "field-help" }, "A note for your records, exported with the project. It changes nothing.")),
    capBox,
    h("div", {}, h("h3", { class: "h-small" }, `What ${sentToWords()} has read: ${share}%`), byLine ? h("p", { class: "small sent-by" }, `Read by each cloud provider: ${byLine}`) : null, list,
      sent.since ? h("p", { class: "muted small" }, `Since 0.11 (${fmt.dateShort(sent.since)}), plus the earlier results Margin recorded.`) : null));
  await dialog({ title: doc.title || doc.file, body, wide: true, actions: [{ text: "Cancel", value: null }, { text: "Save", primary: true, onClick: async () => {
    const changes = { doc_ids: [doc.doc_id], note: note.value.trim() };
    if (level !== doc.ai_access || (doc.own == null && level !== projectDefault)) changes.ai_access = level === projectDefault && doc.own == null ? null : level;
    if (level === "cloud") changes.budget = cap.value === "" ? "" : Number(cap.value);
    if (provBox && level === "cloud") {
      if (!provs.length) { showError(new Error("Tick at least one cloud provider, or mark the document Only a local AI.")); return false; }
      const same = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
      const was = doc.providers_own || null;
      const now = doc.providers_own == null && same(provs, projectProviders) ? null : provs;
      if (JSON.stringify(now) !== JSON.stringify(was)) changes.providers = now;
    }
    try { const r = await api("PUT", `/api/projects/${P(project)}/documents/ai-access`, changes); onSaved(r); return true; }
    catch (e) { showError(e); return false; }
  } }] });
}

// "What happens to the text Claude reads": in plain words, with the source and the date it was checked.
export function termsPanel(opts = {}) {
  const st = App.state || {};
  const said = opts.account || (st.settings || {}).account_type || "";
  const box = card({ as: "div", class: "terms-panel" });
  const draw = (kind) => {
    const choose = choice({ label: "Your kind of Claude account", class: "terms-pick", value: kind,
      options: [["personal", "Pro or Max (personal)"], ["commercial", "Team, Enterprise or the Claude API"]],
      onPick: async (k) => {
        try { const r = await api("PUT", "/api/settings", { account_type: k }); App.state.settings = r.settings; } catch (e) { showError(e); return; }
        draw(k);
      } });
    const facts = {
      personal: [h("p", {}, h("strong", {}, "Consumer terms apply. "), "Anthropic may use your chats and Claude Code sessions to train its models when your account's model-improvement setting is on, and then keeps that data for 5 years (30 days when it is off). ",
        h("strong", {}, "Turn that setting off before Claude reads licensed documents: "), h("a", { href: PRIVACY_SETTING, target: "_blank", rel: "noopener" }, "Claude privacy settings"), ".")],
      commercial: [h("p", {}, h("strong", {}, "Commercial terms apply. "), "Anthropic does not train its models on what Claude Code is sent, unless your organisation chose to share it, and keeps it for 30 days. Ask your organisation about a data processing agreement for personal data.")],
    }[kind];
    replace(box,
      h("h3", { class: "h-small" }, icon("cloud", { size: 14 }), "What happens to the text Claude reads"),
      h("p", { class: "small" }, "Only the excerpts inside the AI's tasks leave this computer, and only from documents Claude may read: documents marked Only a local AI or No AI are never sent."),
      opts.detected && kind ? h("p", { class: "small muted" }, `Claude Code says your plan is ${opts.detected}.`) : h("p", { class: "small muted" }, "Which kind of account do you use?"),
      opts.detected && kind ? null : choose,
      facts ? h("div", { class: "small" }, facts) : null,
      h("p", { class: "small" }, h("strong", {}, "Your documents must stay in the EU? "), "Mark them ", h("em", {}, "Only a local AI"), ": Claude processes data outside the EU."),
      h("p", { class: "muted small" }, "From ", h("a", { href: DATA_USAGE, target: "_blank", rel: "noopener" }, "Anthropic's Claude Code data-usage page"), `, checked on ${CHECKED}. The terms can change; that page is the authority. Margin decides nothing here: this helps you choose each document's setting.`));
  };
  draw(opts.kind || said || "");
  return box;
}

// Settings → AI: the local model that reads documents marked Only a local AI while Claude reads the rest.
export function restrictedModelCard(s, servers, save, info = { servers }) {
  const chosen = (App.state && App.state.restricted) || {};
  const sect = card({ class: "settings-section", id: "s-restricted", "aria-labelledby": "s-restricted-h" },
    h("h2", { id: "s-restricted-h", tabindex: "-1" }, "Local model for restricted documents"));
  if (chosen.same_as_main) {
    sect.append(h("p", { class: "lead" }, "The AI you chose runs on this computer, so it also reads the documents marked Only a local AI. Documents marked No AI wait for your own judgement."));
    return sect;
  }
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const options = [h("option", { value: "" }, "None: I judge those excerpts myself")];
  for (const srv of servers || []) {
    for (const m of srv.chat_models || []) options.push(h("option", { value: `${srv.kind}|${m}`, selected: s.restricted_server === srv.kind && s.restricted_model === m }, `${m} (${srv.kind === "ollama" ? "Ollama" : "local server"})`));
  }
  if (s.restricted_model && !options.some((o) => o.selected)) options.push(h("option", { value: `${s.restricted_server}|${s.restricted_model}`, selected: true }, `${s.restricted_model} (not running now)`));
  const sel = select({ id: "restricted-model" }, ...options);
  sel.addEventListener("change", async () => {
    const [server, model] = sel.value ? sel.value.split("|") : ["", ""];
    try { await save({ restricted_server: server, restricted_model: model }, state); const st = await api("GET", "/api/state"); App.state.restricted = st.restricted; toast(model ? `Documents marked Only a local AI are read by ${model}.` : "Excerpts from documents marked Only a local AI wait for your judgement.", "ok"); }
    catch (_) { /* shown */ }
  });
  sect.append(h("p", { class: "lead" }, `${s.backend === "cloud_api" ? "The cloud provider" : "Claude"} never reads documents marked Only a local AI. Choose a model on this computer to read their excerpts in a check, the Profile and the other features; without one, they wait for your own judgement.`),
    h("div", { class: "save-row" }, field2("Local model", sel, servers && servers.length ? "Chat models of the model servers running on this computer." : "No model server is running on this computer just now (Ollama, LM Studio…)."), state));
  // 0.13.7: no model on this computer yet: get Ollama, or download a model into it with one button
  const rerender = () => window.dispatchEvent(new HashChangeEvent("hashchange"));
  const help = localModelHelp(info, { embed: false, use: "restricted", onFound: rerender, onReady: async (r) => {
    try { await App.refresh(); } catch (_) { /* shown on the page */ }
    toast(r.chosen ? `Documents marked Only a local AI are read by ${r.chat}.` : `${r.chat} is downloaded: choose it above.`, "ok");
    rerender();
  } });
  // with no model server at all, the steps to get one stay folded: most people who use Claude never need them
  if (help) sect.append((servers || []).length ? help : fold({}, "Get a model on this computer (free, no terminal)", help));
  return sect;
}

function field2(label, control, help) {
  return h("div", { class: "field grow" }, h("label", { class: "field-label", for: control.id }, label), control, h("div", { class: "field-help" }, help));
}
