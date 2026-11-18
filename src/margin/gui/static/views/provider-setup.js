// Providers stage 2 (B2): a cloud provider's API key, set up step by step (outside-setup.js, the storage space's way):
// OpenAI, Google Gemini, Mistral, Azure OpenAI, OpenRouter, and the Claude API. The pages and their menus were checked
// on the providers' own sites on 18 November 2026 (providers.py); a button whose name is not documented is not named.
// The last step stores the key (it goes to this computer's keychain; only "stored: yes or no" ever comes back), then
// lists the models the key may use and shows, as the done step, the recommended models Margin applied from that list
// (providers.recommended, resolved by GET /api/settings/provider-models). Used by Settings → AI (settings.js).
import { App, api, h, notice, input, field, fold } from "../lib.js";
import { outsideSetup, addressStep, typeAddress, pasteField, allowLine } from "./outside-setup.js";
import { keptIn } from "./team-space.js";

// the three tiers, in the words of a sentence ("gpt-6-luna for labels and links")
export const TIER_WORDS = { small: "labels and links", middle: "judging excerpts", strong: "second opinions" };
export const TIERS = ["small", "middle", "strong"];
// Claude's own ladder, as the routing table applies it on the Claude API
const CLAUDE_LADDER = { small: "Claude Haiku", middle: "Claude Sonnet", strong: "Claude Opus" };

// where the keys are kept on this computer: its keychain, or (where it has none) Margin's own file, readable by this
// person only (the storage space's words, team-space.js keptIn; the backend from the providers' state)
const keychainKind = () => ((App.state && App.state.providers) || {}).keychain;
export const keptWhere = () => keptIn(keychainKind());                              // "Kept in this computer’s keychain"
export const storedWhere = () => keptWhere().replace(/^Kept /, "");                  // "in this computer’s keychain"
const kept = () => `${keptWhere()}. Only whether a key is stored ever comes back to this page.`;
const once = (who) => notice({ kind: "attention", role: "note" }, h("p", {}, `${who} shows the key only once. Copy it before you leave that page.`));
const strong = (t) => h("strong", {}, t);

// Save settings from a dialog (as Settings' own save does: the app's copy and everything listening follow at once)
export async function putSettings(changes) {
  const r = await api("PUT", "/api/settings", changes);
  App.state.settings = r.settings;
  App.state.backend_label = r.backend_label;
  if (r.providers) App.state.providers = r.providers;
  for (const fn of App.listeners) fn(App.state);
  return r;
}

// A provider's problem said on a page that is not Settings → AI (its words point there)
export const plainProblem = (t) => String(t || "").replace(/\s*Check (?:it|the address) in Settings → AI[^.]*\./g, "").trim();

// "Applied automatically: a for labels and links, b for judging excerpts, c for second opinions." When every tier is
// the same model (a free plan that offers one), it says so once, and that a second opinion is the same model again.
export function appliedLine(lineup, lead = "Applied automatically: ") {
  const ids = TIERS.map((t) => lineup[t]).filter(Boolean);
  if (ids.length === TIERS.length && new Set(ids).size === 1) {
    return h("p", { class: "provider-applied" }, lead, "every task uses ", h("code", {}, ids[0]), "; a second opinion then comes from the same model.");
  }
  const parts = TIERS.filter((t) => lineup[t]).map((t) => [h("code", {}, lineup[t]), ` for ${TIER_WORDS[t]}`]);
  if (!parts.length) return null;
  const out = [lead];
  parts.forEach((p, i) => { out.push(...p); out.push(i < parts.length - 2 ? ", " : i === parts.length - 2 ? " and " : "."); });
  return h("p", { class: "provider-applied" }, ...out);
}

// What each provider's set-up asks, as guided steps: { steps, read(), missing(body), missingAt?(body) }. `p` is the
// provider as providers.summary() gives it (its pages and its recommendations).
export function providerSteps(p) {
  const rec = p.recommended || {};
  const key = pasteField("API key", { id: `key-${p.id}`, placeholder: p.placeholder || "", help: kept() });
  const paste = (more = []) => ({ title: "Paste the key here", next: false, body: [key, ...more] });
  const readKey = () => ({ key: key.input.value.trim() });
  const needKey = (b) => (!b.key ? `Paste the key ${p.company === "Microsoft" ? "from the Azure portal" : `${p.title} showed`}.` : "");
  if (p.id === "openai") {
    return {
      steps: [
        addressStep({ title: "Make an account on OpenAI’s API platform", href: p.signup, id: "key-openai-signup", next: "I have an account",
          more: h("p", { class: "muted small" }, "It is OpenAI’s platform for developers, apart from ChatGPT. Your ChatGPT login works there.") }),
        { title: "Add credit", next: "I have added credit", body: [
          h("p", {}, "The API is billed per use, from credit you add in advance. Open the billing page and add some:"),
          typeAddress(p.billing_url, "key-openai-billing"),
          notice({ kind: "info", role: "note" }, h("p", {}, "A ChatGPT plan does not pay for the API. To use your ChatGPT plan instead, with no key, close this set-up and choose ", strong("Subscription"), ", then ", strong("Codex"), "."))] },
        { title: "Make a key for Margin", next: "I have copied the key", body: [
          h("p", {}, "Open the keys page and make a new secret key. Name it Margin, so you know later what it is for."),
          typeAddress(p.keys_url, "key-openai-keys"),
          once("OpenAI")] },
        paste(),
      ],
      read: readKey, missing: needKey,
    };
  }
  if (p.id === "gemini") {
    return {
      steps: [
        addressStep({ title: "Sign in to Google AI Studio", href: p.signup, id: "key-gemini-signup", next: "I have signed in",
          more: h("p", { class: "muted small" }, "Sign in with your Google account. No payment card is needed to start.") }),
        { title: "Make a key for Margin", next: "I have copied the key", body: [
          h("p", {}, "In AI Studio, open ", strong("Dashboard › API Keys"), " and press ", strong("Create API key"), ". The keys page is also here:"),
          typeAddress(p.keys_url, "key-gemini-keys"),
          notice({ kind: "attention", role: "note", id: "key-gemini-terms" }, h("p", {}, "On the free tier Google may use what is sent to improve its products, except in the EEA, Switzerland and the UK, where its paid terms apply to all use. Elsewhere, choose ", strong("Set up billing"), " in AI Studio before your documents are read."))] },
        paste(),
      ],
      read: readKey, missing: needKey,
    };
  }
  if (p.id === "mistral") {
    return {
      steps: [
        addressStep({ title: "Make a Mistral account", href: p.signup, id: "key-mistral-signup", next: "I have an account" }),
        { title: "Choose a plan with API access", next: "I have a plan", body: [
          h("p", {}, "In Mistral’s console, choose a plan that includes API access and add a payment method. Without them, keys are refused. Billing is here:"),
          typeAddress(p.billing_url, "key-mistral-billing")] },
        { title: "Make a key for Margin", next: "I have copied the key", body: [
          h("p", {}, "Open ", strong("API Keys"), " and press ", strong("New key"), ". Name it Margin and choose when it expires."),
          typeAddress(p.keys_url, "key-mistral-keys"),
          once("Mistral")] },
        paste(),
      ],
      read: readKey, missing: needKey,
    };
  }
  if (p.id === "azure") {
    const address = pasteField("Endpoint (the resource’s address)", { id: "key-azure-address", plain: true, placeholder: "https://my-resource.openai.azure.com",
      help: "Copy it from Keys and Endpoint. Margin adds /openai/v1/ itself." });
    // empty = the recommended name (the placeholder shows it)
    const deps = Object.fromEntries(TIERS.map((t) => [t, input({ mono: true, id: `key-azure-dep-${t}`, autocomplete: "off", spellcheck: "false", value: "", placeholder: rec[t] || "" })]));
    const otherNames = fold({ sm: true, id: "key-azure-other-names" }, "I gave a deployment another name",
      h("p", { class: "field-help" }, "Type the name you gave it. Left empty, a deployment has the model’s own name."),
      ...TIERS.map((t) => field(`For ${TIER_WORDS[t]}`, deps[t])));
    return {
      steps: [
        addressStep({ title: "Sign in to Microsoft Foundry", href: p.signup, id: "key-azure-signup", next: "I am signed in",
          more: h("p", { class: "muted small" }, "With your institution’s Microsoft account. It needs an Azure subscription with Azure OpenAI; your IT department may hold one.") }),
        { title: "Deploy the three recommended models", next: "They are deployed", body: [
          h("p", {}, "In Foundry, open the ", strong("Model catalog"), ", choose each model below and press ", strong("Deploy"), ". Keep the model’s name as the deployment’s name."),
          h("ul", { class: "provider-models-list" }, TIERS.map((t) => h("li", {}, h("code", {}, rec[t] || ""), h("span", { class: "muted" }, ` for ${TIER_WORDS[t]}`)))),
          otherNames] },
        { title: "Find the key and the address", next: "I see them", body: [
          h("p", {}, "In the Azure portal, open your Azure OpenAI resource, then ", strong("Keys and Endpoint"), "."),
          typeAddress(p.keys_url, "key-azure-portal")] },
        { title: "Paste them here", next: false, body: [address, key] },
      ],
      read: () => ({ key: key.input.value.trim(), azure_url: address.input.value.trim(), deployments: Object.fromEntries(TIERS.map((t) => [t, deps[t].value.trim() || rec[t] || ""])) }),
      missing: (b) => (!b.azure_url ? "Paste the endpoint from Keys and Endpoint." : !/^https:\/\//i.test(b.azure_url) ? "The endpoint starts with https://." : needKey(b)),
    };
  }
  if (p.id === "openrouter") {
    return {
      steps: [
        addressStep({ title: "Make an OpenRouter account", href: p.signup, id: "key-openrouter-signup", next: "I have an account" }),
        { title: "Buy credits", next: "I have credits", body: [
          h("p", {}, "OpenRouter is paid from credits bought in advance. Open the credits page:"),
          typeAddress(p.billing_url, "key-openrouter-credits")] },
        { title: "Make a key for Margin", next: "I have copied the key", body: [
          h("p", {}, "Open the keys page and make a new key. Name it Margin."),
          typeAddress(p.keys_url, "key-openrouter-keys"),
          notice({ kind: "info", role: "note" }, h("p", {}, "What Margin sends goes to OpenRouter and on to the model’s own provider (OpenAI, Google and others)."))] },
        paste(),
      ],
      read: readKey, missing: needKey,
    };
  }
  return { steps: [paste()], read: readKey, missing: needKey };
}

// The done step of a key: stored, and the models applied. `r.problem`: the provider could not be reached to check the
// key (a refused key never gets here: the paste step says so and forgets it). `chosen`: the person's own choices per
// tier (they stay in place of the recommendation). `offer`: what the main button still does ({ text, line, run }),
// null when nothing is left.
function keyDone(p, r, { chosen = {}, offer } = {}) {
  const lineup = r.recommended || p.recommended || {};
  const own = TIERS.filter((t) => chosen[t]);
  const unchecked = !!r.problem;
  return {
    title: unchecked ? "The key is stored, not checked yet" : `${p.title} is set up`,
    main: offer ? { text: offer.text, run: async (res) => { await offer.run(); res.applied = true; } } : null,
    quiet: offer ? "Not now" : null,
    body: [
      unchecked
        ? notice({ kind: "attention", role: "note" }, h("p", {}, `The key is stored ${storedWhere()}, but ${p.title} could not be asked whether it works (${plainProblem(r.problem)}). If it is wrong, ${p.title} will refuse it when it is first used.`))
        : notice({ kind: "done", role: "note" }, h("p", {}, r.listed ? `The key is stored ${storedWhere()}, and ${p.title} accepted it.` : `The key is stored ${storedWhere()}.`)),
      p.id === "azure" ? appliedLine(r.deployments || lineup, "Your deployments: ")
        : appliedLine(lineup, r.listed ? `Applied automatically, from ${p.company}’s recommendations for the models your key may use: ` : "Applied automatically, from its recommendations: "),
      own.length ? h("p", { class: "muted small" }, `Your own choice for ${own.map((t) => TIER_WORDS[t]).join(" and ")} stays in place of the recommendation.`) : null,
      h("p", { class: "muted small" }, "You can change them under Recommended models, below the key."),
      offer && offer.line ? h("p", { class: "provider-left" }, offer.line) : null,
      allowLine(App.project),
    ],
  };
}

// Set up a cloud provider's key in a dialog. opts: at ("paste": open at the last step, to change the key), chosen
// (the person's own model choices), offer (a function: what the done step's main button still does, or null; see
// keyDone). Resolves with { stored, recommended, models, problem, azure_url, deployments, applied } or null.
export async function providerSetup(p, opts = {}) {
  const svc = providerSteps(p);
  return outsideSetup({
    title: `Set up ${p.title}`,
    label: `Setting up ${p.title}`,
    id: `provider-steps-${p.id}`,
    steps: svc.steps,
    read: svc.read, missing: svc.missing,
    start: opts.at === "paste" ? svc.steps.length - 1 : undefined,
    rememberKey: `provider-setup-step:${p.id}`,
    mainText: "Store the key",
    async submit(body, ui) {
      ui.progress("Storing the key…");
      const r = await api("POST", "/api/settings/provider-key", { provider: p.id, key: body.key });
      App.state.providers = r.providers;
      const out = { stored: true, recommended: p.recommended || {}, models: [], listed: false, problem: "" };
      if (p.id === "azure") {
        // nothing is lost without Settings' Save: the endpoint and the deployments' names are kept now
        const d = body.deployments;
        await putSettings({ azure_url: body.azure_url, cloud_small_model: d.small, cloud_model: d.middle, cloud_strong_model: d.strong });
        return { ...out, azure_url: body.azure_url, deployments: d };
      }
      ui.progress("Asking which models the key may use…");
      try {
        const m = await api("GET", `/api/settings/provider-models?provider=${encodeURIComponent(p.id)}`);
        if (m.refused) {
          // the provider answered that the key is wrong: it is forgotten, and the person pastes it again
          try { App.state.providers = (await api("DELETE", "/api/settings/provider-key", { provider: p.id })).providers; } catch (_) { /* shown by the next look */ }
          ui.progress("");
          ui.error(`${p.title} refused this key. Copy it again from the keys page.`);
          return false;
        }
        Object.assign(out, { models: m.models || [], listed: !!(m.models || []).length, problem: m.problem || "" });
        if (m.recommended) out.recommended = m.recommended;
      } catch (e) { out.problem = e.message || String(e); }
      return out;
    },
    after: (r) => keyDone(p, r, { chosen: opts.chosen, offer: typeof opts.offer === "function" ? opts.offer() : opts.offer }),
    doneWords: (r) => (r.problem ? `The ${p.title} key is stored.` : r.applied ? `${p.title} is set up and in use.` : `${p.title} is set up.`),
  });
}

// The Claude API's key, the same way (the anthropic route). Its models are Claude's own ladder.
export async function claudeKeySetup(opts = {}) {
  const k = (App.state && App.state.key) || {};
  const key = pasteField("API key", { id: "key-anthropic", placeholder: "sk-ant-…", help: "Only whether a key is set ever comes back to this page." });
  const remember = h("input", { type: "checkbox", id: "key-anthropic-remember", checked: k.stored !== false });
  const steps = [
    addressStep({ title: "Sign in to the Claude platform", href: "https://platform.claude.com", id: "key-anthropic-signup", next: "I have signed in",
      more: h("p", { class: "muted small" }, "With the account of your team or institution. The API is billed per use, apart from any Claude plan.") }),
    { title: "Make a key for Margin", next: "I have copied the key", body: [
      h("p", {}, "Open ", strong("Settings › API keys"), " and press ", strong("Create key"), ". Name it Margin."),
      typeAddress("https://platform.claude.com/settings/keys", "key-anthropic-keys")] },
    { title: "Paste the key here", next: false, body: [key,
      h("label", { class: "it small", for: "key-anthropic-remember" }, remember, " Remember on this computer (readable by your user only)"),
      h("p", { class: "muted small" }, "Not ticked: the key is kept until you close Margin.")] },
  ];
  return outsideSetup({
    title: "Set up the Claude API", label: "Setting up the Claude API", id: "provider-steps-anthropic",
    steps, start: opts.at === "paste" ? steps.length - 1 : undefined, rememberKey: "provider-setup-step:anthropic",
    read: () => ({ key: key.input.value.trim() }),
    missing: (b) => (!b.key ? "Paste the key the Claude platform showed." : ""),
    mainText: "Store the key",
    async submit(body, ui) {
      ui.progress("Storing the key…");
      const r = await api("POST", "/api/settings/key", { key: body.key, remember: remember.checked });
      App.state.key = r.key;
      return { stored: true, remembered: remember.checked };
    },
    after: (r) => { const offer = typeof opts.offer === "function" ? opts.offer() : opts.offer; return { title: "The Claude API is set up", body: [
      notice({ kind: "done", role: "note" }, h("p", {}, r.remembered ? "The key is kept on this computer." : "The key is kept until you close Margin.")),
      h("p", { class: "provider-applied" }, `Applied automatically: ${CLAUDE_LADDER.small} for labels and links, ${CLAUDE_LADDER.middle} for judging excerpts and ${CLAUDE_LADDER.strong} for second opinions. How much thought, below, moves each one step lighter or stronger.`),
      offer && offer.line ? h("p", { class: "provider-left" }, offer.line) : null],
      main: offer ? { text: offer.text, run: async (res) => { await offer.run(); res.applied = true; } } : null, quiet: offer ? "Not now" : null };
    },
    doneWords: (r) => (r.applied ? "The Claude API is set up and in use." : "The Claude API is set up."),
  });
}
