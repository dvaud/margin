"""Providers stage 2 (B): one way to set up anything outside Margin, in the page (views/outside-setup.js,
provider-setup.js, agent-setup.js, settings.js), run in Node (tests/_views.py):

- the shared dialog of guided steps: its main button waits for the last step, the step is remembered for the window,
  "Stop the set-up?" once something is typed, and a done step that says what is left;
- each provider's key set-up has its own steps from the checked facts (OpenAI's credit, Gemini's free-tier terms,
  Mistral's plan, Azure's deployments, OpenRouter's second company, the Claude platform's keys page);
- Settings → AI: "Subscription" holds Claude Code, Codex and Antigravity; choosing Codex asks first and a no puts the
  choice back; Codex's checklist card opens the agent set-up at the first step not done, the sign-in step moves on by
  itself once Codex says it is signed in, and the done step shows the models applied for the plan; without the
  agent-setup API the card says it could not be read.
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const REC = { small: "gpt-6-luna", middle: "gpt-6.2-sol", strong: "gpt-6.2-astra" };
const P = (id, title, company, more = {}) => ({ id, title, company, lists_models: id !== "azure", signup: `https://${id}.example/signup`,
  keys_url: `https://${id}.example/keys`, billing_url: `https://${id}.example/billing`, recommended: REC, ...more });
const LIST = [P("anthropic", "Anthropic (Claude)", "Anthropic"), P("openai", "OpenAI", "OpenAI"), P("gemini", "Google Gemini", "Google"),
  P("mistral", "Mistral", "Mistral AI"), P("azure", "Azure OpenAI", "Microsoft"), P("openrouter", "OpenRouter", "OpenRouter (and the model's own provider)")];
const NONE = { list: LIST, keys: {}, route: "anthropic", set_up: [], other_set_up: false };
const titles = (t, d) => d.querySelectorAll(".guided-step-title").map((x) => t.text(x).replace(/^Step \d of \d(, done)?: /, ""));
const openStep = (t, d) => t.text(d.querySelector(".guided-step[data-state=current]"));
const goOn = (t, d) => t.click(d.querySelector(".guided-step[data-state=current] .guided-step-next"));

await scenario("the shared dialog", async (t) => {
  t.state({ settings: {}, providers: NONE });
  const m = await t.module("views/outside-setup.js");
  const f = m.pasteField("Key", { id: "k" });
  let sent = null;
  const done = m.outsideSetup({ title: "Set up a thing", id: "s", rememberKey: "thing-step",
    steps: [m.addressStep({ title: "Make an account", href: "https://thing.example/sign-up", id: "addr", next: "I have an account" }),
      { title: "Paste it", next: false, body: [f] }],
    read: () => ({ key: f.input.value.trim() }), missing: (b) => (!b.key ? "Paste the key." : ""),
    mainText: "Store it", submit: async (b) => { sent = b; return { ok: 1 }; },
    after: () => ({ title: "It is set up", body: [document.createTextNode("Left to do: press Save.")] }) });
  await t.settle(10);
  const d = t.dialog();
  const out = { titles: titles(t, d), waits: !!d.querySelector("#dlg-confirm").disabled, address: t.text(d.querySelector("#addr")),
    copyButton: t.buttons(d.querySelector("#addr")) };
  await goOn(t, d);
  out.remembered = sessionStorage.getItem("margin.thing-step");
  out.open = !d.querySelector("#dlg-confirm").disabled;
  await t.click("Store it", { within: d.querySelector(".dialog-actions") });
  out.missing = t.text(d.querySelector(".field-error"));
  await t.type(d.querySelector("#k"), "secret");
  await t.press("Escape");
  out.asked = t.dialogs().map((x) => t.text(x.querySelector("h2")));
  await t.click("Cancel", { within: t.dialog().querySelector(".dialog-actions") });   // keep going
  await t.click("Store it", { within: d.querySelector(".dialog-actions") });
  await t.settle(10);
  out.sent = sent;
  out.done = openStep(t, d);
  out.button = t.text(d.querySelector("#dlg-confirm"));
  out.forgot = sessionStorage.getItem("margin.thing-step");
  await t.click("Done", { within: d.querySelector(".dialog-actions") });
  out.result = await done;
  return out;
});

await scenario("each provider's steps", async (t) => {
  t.state({ settings: {}, providers: NONE });
  const m = await t.module("views/provider-setup.js");
  const out = {};
  for (const p of LIST.slice(1)) {
    const done = m.providerSetup(p, {});
    await t.settle(10);
    const d = t.dialog();
    out[p.id] = { titles: titles(t, d), text: "" };
    const n = d.querySelectorAll(".guided-step").length - 1;
    const words = [];
    for (let i = 0; i < n; i++) { words.push(openStep(t, d)); if (i < n - 1) await goOn(t, d); }
    out[p.id].text = words.join(" | ");
    out[p.id].fields = d.querySelectorAll(".guided-step[data-state=current] input").map((x) => [x.id, x.getAttribute("type"), x.value]);
    if (p.id === "azure") {
      out[p.id].dep_placeholders = ["small", "middle", "strong"].map((k) => d.querySelector(`#key-azure-dep-${k}`).getAttribute("placeholder"));
      out[p.id].fold_open = !!d.querySelector("#key-azure-other-names").open;
    }
    await t.click("Cancel", { within: d.querySelector(".dialog-actions") });
    const ask = t.dialog(); if (ask && ask !== d) await t.click("Stop the set-up", { within: ask.querySelector(".dialog-actions") });
    await done;
  }
  const ck = m.claudeKeySetup({ at: "paste" });
  await t.settle(10);
  const d = t.dialog();
  out.claude = { titles: titles(t, d), open: openStep(t, d) };
  t.answer("POST /api/settings/key", (b) => ({ key: { session: true, env: false, stored: b.remember } }));
  await t.type(d.querySelector("#key-anthropic"), "sk-ant-1");
  await t.click("Store the key", { within: d.querySelector(".dialog-actions") });
  await t.settle(10);
  out.claude.done = openStep(t, d);
  out.claude.post = t.calls.filter((c) => c.path === "/api/settings/key").map((c) => c.body);
  await t.click("Done", { within: d.querySelector(".dialog-actions") });
  await ck;
  return out;
});

await scenario("the fixes of the final review", async (t) => {
  // keys kept in Margin's own file where there is no keychain: the words say so
  t.state({ settings: {}, providers: { ...NONE, keychain: "file" } });
  const ps = await t.module("views/provider-setup.js");
  const os = await t.module("views/outside-setup.js");
  const steps = ps.providerSteps(LIST[3]);   // Mistral
  const box = document.createElement("div");
  steps.steps.forEach((x) => box.append(...[].concat(x.body)));
  const out = { kept: t.text(box.querySelector("#key-mistral").closest(".field")), mistralBilling: t.text(box.querySelector("#key-mistral-billing")),
    articles: [os.article("OpenAI"), os.article("Mistral"), os.article("Azure OpenAI")] };
  out.one = t.text(ps.appliedLine({ small: "gemini-3.8-flash", middle: "gemini-3.8-flash", strong: "gemini-3.8-flash" }, "Applied: "));
  out.noAllow = os.allowLine("Study");   // ai-access.js without providerAllowLine (before builder A's merge): nothing
  return out;
});

await scenario("a shared project in the consent", async (t) => {
  await settingsPage(t, { backend: "claude_code", allow_claude_code: true }, { shared: true });
  await t.click(t.view.querySelector('#agent-choice [data-value="antigravity"]'));
  await t.settle(50);
  const d = t.dialog();
  const out = { says: t.text(d.querySelector(".dialog-body")) };
  await t.click(d.querySelector("#dlg-safe"));
  return out;
});

await scenario("a shared project with the owner's limit in the consent", async (t) => {
  await settingsPage(t, { backend: "claude_code", allow_claude_code: true }, { shared: true, limit: ["anthropic"] });
  await t.click(t.view.querySelector('#agent-choice [data-value="antigravity"]'));
  await t.settle(50);
  const d = t.dialog();
  const out = { says: t.text(d.querySelector(".dialog-body")) };
  await t.click(d.querySelector("#dlg-safe"));
  return out;
});

await scenario("Antigravity's sign-in and what is added", async (t) => {
  t.state({ settings: {}, providers: NONE });
  const m = await t.module("views/agent-setup.js");
  const ad = m.cliAdapter("antigravity");
  let st = { found: true, signed_in: false, connector: false, ready: false };
  ad.read = async () => ({ status: st, installer: ad.installer, docs: ad.docs });
  let opened = 0;
  ad.signIn = async () => { opened += 1; return { opened: true, window: "Terminal", command: "agy" }; };
  const done = m.agentSetupDialog(ad, { status: st }, { project: "Study" });
  await t.settle(10);
  const d = t.dialog();
  const out = { intro: t.text(d.querySelector(".guided-step[data-state=current]")) };
  const btn = d.querySelector("#agent-sign-in-antigravity");
  await t.click(btn);
  await t.settle(10);
  out.disabled = !!btn.disabled;
  out.words = t.text(d.querySelector(".guided-step[data-state=current]"));
  out.againEarly = t.hidden(d.querySelector("#agent-sign-in-again-antigravity").parentNode);
  await t.settle(3000);
  st = { ...st, signed_in: true };
  await t.settle(28000);
  out.adds = t.text(d.querySelector(".agent-adds"));
  out.opened = opened;
  await t.click("Cancel", { within: d.querySelector(".dialog-actions") });
  await done;
  return out;
});

await scenario("the first run offers Codex and Antigravity", async (t) => {
  t.state({ settings: { backend: "claude_code", allow_claude_code: true }, providers: NONE, projects: [] });
  t.answer("GET /api/claude-setup", { status: { found: false } });
  t.answer("GET /api/projects/Study", { ai_access: {} });
  t.answer("GET /api/agent-setup?*", { route: "codex", status: { found: false }, recommended: REC });
  await t.render("views/setup.js", "renderSetup", []);
  await t.settle(100);
  const out = { others: t.view.querySelectorAll(".su-others-body [data-agent]").map((x) => x.dataset.agent), text: "" };
  await t.click(t.view.querySelector("summary"));
  out.text = t.text(t.view.querySelector(".su-others-body"));
  let put = null;
  t.answer("PUT /api/settings", (b) => { put = b; return { settings: { backend: "codex", allow_codex: true }, backend_label: "Codex", providers: NONE }; });
  t.answer("GET /api/state", { settings: { backend: "codex", allow_codex: true }, providers: NONE, projects: [] });
  await t.click(t.view.querySelector("#setup-use-codex"));
  await t.settle(50);
  const d = t.dialog();
  out.asked = d ? t.text(d.querySelector("h2")) : "";
  if (d) await t.click("Use Codex", { within: d });
  await t.settle(100);
  out.put = put;
  // an unready Codex gets the agent's step, not the local model's
  t.state({ settings: { backend: "codex", allow_codex: true }, providers: NONE, projects: [] });
  document.getElementById("view").replaceChildren();
  await t.render("views/setup.js", "renderSetup", []);
  await t.settle(100);
  out.codexStep = t.text(t.view.querySelector(".card"));
  return out;
});

const CODEX = (status) => ({ route: "codex", title: "Codex", company: "OpenAI", installer: { line: "curl -fsSL https://chatgpt.com/codex/install.sh | sh", docs: "https://learn.chatgpt.com/docs/auth" },
  status, recommended: REC, lineup_in_use: { ...REC, middle: "gpt-6.1-sol" }, manual: ["codex login"] });

async function settingsPage(t, settings, extra = {}) {
  t.state({ settings, providers: NONE, ...extra });
  t.answer("GET /api/servers", { servers: [], suggested: [] });
  t.answer("GET /api/claude-setup", { status: { found: true, signed_in: true, installed: true, ready: true } });
  t.answer("GET /api/local-status", {});
  t.answer("GET /api/projects/Study/queue", { kinds: [], waiting: 0 });
  t.answer("GET /api/projects/Study/agreement/plan?*", { kinds: [], problem: null, kept: [], plan: null });
  t.answer("GET /api/projects/Study", { ai_access: { shared: !!extra.shared, team_limit: extra.limit ? { providers: extra.limit } : null,
    providers_note: extra.limit ? "The team uses Anthropic only (set by Anna)." : null } });
  t.answer("PUT /api/settings", (b) => ({ settings: { ...settings, ...b }, backend_label: "x", providers: NONE }));
  await t.render("views/settings.js", "renderSettings", ["model"]);
  await t.settle(200);
}

await scenario("Subscription: Claude Code, Codex or Antigravity", async (t) => {
  let st = { found: false, signed_in: null, connector: null, ready: false };
  t.answer("GET /api/agent-setup?*", () => CODEX(st));
  await settingsPage(t, { backend: "claude_code", allow_claude_code: true });
  const out = { cards: t.view.querySelectorAll(".route-cards input[type=radio]").map((r) => [r.value, !!r.checked]),
    choice: t.view.querySelectorAll("#agent-choice [role=radio]").map((b) => [b.dataset.value, b.getAttribute("aria-checked")]),
    words: t.text(t.view.querySelector("#agent-choice")), inset: !!t.view.querySelector(".agent-choice-box #agent-choice"),
    label: t.text(t.view.querySelector(".agent-choice-box .field-label")), routeWords: t.text(t.view.querySelector(".route-cards")),
    tags: t.view.querySelectorAll("#agent-choice [role=radio]").map((c) => { const g = c.querySelector(".option-card-head .chip"); return g ? t.text(g) : ""; }) };
  await t.click(t.view.querySelector('#agent-choice [data-value="codex"]'));
  let d = t.dialog();
  out.asked = t.text(d.querySelector("h2"));
  out.says = t.text(d.querySelector(".dialog-body"));
  out.refusal = t.text(d.querySelector("#dlg-safe"));
  await t.click(d.querySelector("#dlg-safe"));
  await t.settle(50);
  out.back = t.view.querySelector("#agent-choice [aria-checked=true]").dataset.value;
  await t.click(t.view.querySelector('#agent-choice [data-value="codex"]'));
  let redrawn = 0;
  window.addEventListener("hashchange", () => { redrawn += 1; });
  await t.click("Use Codex", { within: t.dialog() });
  await t.settle(100);
  out.redrawn = redrawn;   // the whole page is drawn again once the route is saved (the app's router does it)
  document.getElementById("view").replaceChildren();
  await t.render("views/settings.js", "renderSettings", ["model"]);
  await t.settle(200);
  out.queueWords = t.text(t.view);
  // the consent is the decision: the route and its allow are saved at once
  out.putAtOnce = t.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").map((c) => c.body);
  const box = t.view.querySelector(".set-agent-box");
  out.card = t.text(box.querySelector(".cc-card"));
  out.models = t.text(box.querySelector("#s-cli-models"));
  out.order = [...box.children].map((c) => c.id || c.className.split(" ")[0]);
  // the set-up: opens at the first step not done (Codex is found, not signed in)
  st = { found: true, version: "1.4.2", signed_in: false, connector: false, ready: false };
  await t.click(box.querySelector(".cc-card .btn-row button"));
  await t.settle(50);
  // (the card read the first status before: its button opened the dialog at install; go on to the sign-in)
  d = t.dialog();
  out.steps = titles(t, d);
  out.first = t.text(d.querySelector(".guided-step[data-state=current] .guided-step-title"));
  // "I have installed it" checks, then moves on by itself once the program is found
  await t.click("I have installed it", { within: d });
  await t.settle(50);
  t.answer("POST /api/agent-setup/sign-in", { opened: true, window: "", command: "codex login" });
  await t.click("Open the sign-in", { within: d });
  out.waiting = openStep(t, d);
  st = { ...st, signed_in: true, account: "you@uni.nl" };
  await t.settle(4100);
  out.moved = t.text(d.querySelector(".guided-step[data-state=current] .guided-step-title"));
  out.ready = !d.querySelector("#dlg-confirm").disabled;
  // found and signed in, Margin not added: the card says what is left, not that Codex is ready
  out.cardMid = t.text(t.view.querySelector(".set-agent-box .cc-card"));
  out.cardButton = t.text(t.view.querySelector(".set-agent-box .cc-card .btn-row button"));
  out.modelsMid = t.text(t.view.querySelector("#s-cli-models"));
  t.answer("POST /api/agent-setup", () => { st = { ...st, connector: true, ready: true }; return { steps: [{ step: "connector", ok: true, text: "" }], status: st }; });
  await t.click("Add Margin to Codex", { within: d.querySelector(".dialog-actions") });
  await t.settle(50);
  out.done = openStep(t, d);
  await t.click("Done", { within: d.querySelector(".dialog-actions") });
  await t.settle(50);
  out.after = t.text(t.view.querySelector(".set-agent-box .cc-card"));
  out.modelsAfter = t.text(t.view.querySelector("#s-cli-models"));
  out.optionAfter = t.text(t.view.querySelector("#m-codex-middle option"));
  t.answer("PUT /api/settings", (b) => ({ settings: { ...b }, backend_label: "Codex", providers: NONE }));
  await t.click("Save");
  out.put = t.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").map((c) => c.body).pop() || null;
  return out;
});

await scenario("the agent-setup API is not there", async (t) => {
  t.answer("GET /api/agent-setup?*", t.fail(404, "No such API endpoint"));
  await settingsPage(t, { backend: "antigravity", allow_antigravity: true });
  return { card: t.text(t.view.querySelector(".set-agent-box .cc-card")), buttons: t.buttons(t.view.querySelector(".set-agent-box .cc-card")),
    sub: t.view.querySelector('.route-cards input[value="subscription"]').checked };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("outside_setup_views"))


@needs_node
def test_the_shared_dialog_is_the_storage_spaces_way(page):
    r = page["the shared dialog"]
    assert r["titles"] == ["Make an account", "Paste it", "What Margin applied"]
    assert r["waits"] is True and r["address"].startswith("thing.example/sign-up") and "Copy" in r["copyButton"][0]["label"]
    assert r["remembered"] == "1" and r["open"] is True
    assert r["missing"] == "Paste the key."
    assert r["asked"][-1] == "Stop the set-up?"
    assert r["sent"] == {"key": "secret"} and r["forgot"] is None
    assert "It is set up" in r["done"] and "Left to do: press Save." in r["done"] and r["button"] == "Done"
    assert r["result"] == {"ok": 1}


@needs_node
def test_each_provider_has_its_own_checked_steps(page):
    r = page["each provider's steps"]
    assert r["openai"]["titles"] == ["Make an account on OpenAI’s API platform", "Add credit", "Make a key for Margin", "Paste the key here", "What Margin applied"]
    assert "A ChatGPT plan does not pay for the API" in r["openai"]["text"] and "close this set-up and choose" in r["openai"]["text"] and "Subscription" in r["openai"]["text"] and "choose Codex above" not in r["openai"]["text"]
    assert "OpenAI shows the key only once" in r["openai"]["text"]
    assert "Dashboard › API Keys" in r["gemini"]["text"] and "Create API key" in r["gemini"]["text"]
    assert "except in the EEA, Switzerland and the UK" in r["gemini"]["text"]
    assert "a plan that includes API access and add a payment method" in r["mistral"]["text"] and "New key" in r["mistral"]["text"]
    assert "open the Model catalog" in r["azure"]["text"] and "Build ›" not in r["azure"]["text"] and "Keep the model’s name as the deployment’s name" in r["azure"]["text"]
    # the endpoint and the key only; the deployments' names are a closed fold at the deploying step
    assert [f[0] for f in r["azure"]["fields"]] == ["key-azure-address", "key-azure"]
    assert "I gave a deployment another name" in r["azure"]["text"] and r["azure"]["dep_placeholders"] == ["gpt-6-luna", "gpt-6.2-sol", "gpt-6.2-astra"]
    assert r["azure"]["fold_open"] is False
    assert "on to the model’s own provider" in r["openrouter"]["text"]
    for pid in ("openai", "gemini", "mistral", "openrouter"):
        assert r[pid]["fields"][0][1] == "password"
    c = r["claude"]
    assert c["titles"][:3] == ["Sign in to the Claude platform", "Make a key for Margin", "Paste the key here"]
    assert "Paste the key here" in c["open"] and "console.anthropic" not in str(r)
    assert c["post"] == [{"key": "sk-ant-1", "remember": True}]
    assert "Claude Haiku for labels and links" in c["done"]


@needs_node
def test_subscription_holds_the_agents_and_codex_is_set_up_in_steps(page):
    r = page["Subscription: Claude Code, Codex or Antigravity"]
    assert r["cards"] == [["subscription", True], ["local", False], ["baseline", False], ["anthropic", False], ["cloud_api", False]]
    assert r["choice"] == [["claude_code", "true"], ["codex", "false"], ["antigravity", "false"]]
    assert "The passages go to OpenAI" in r["words"] and "The passages go to Google" in r["words"]
    assert r["tags"] == ["Recommended", "", "Recommended on a free plan"]
    assert "Free: every task on Gemini 3.8 Flash" in r["words"]
    assert r["inset"] is True and r["label"] == "Subscription: whose plan" and "a plan you already have" in r["routeWords"]
    assert "may train its models on Plus or Pro unless you switch that off" in r["words"]
    assert "may improve its products from it while Telemetry is on" in r["words"]
    assert r["asked"] == "Let Codex read the excerpts, on your ChatGPT plan?"
    assert "sent to OpenAI" in r["says"] and "Only documents that allow OpenAI are sent" in r["says"]
    assert "On ChatGPT Plus or Pro, OpenAI may use what Codex reads to improve its models unless Improve the model for everyone is off in ChatGPT’s Data controls; Business, Edu and Enterprise plans are not used for that by default." in r["says"]
    assert r["refusal"] == "Stay with Claude Code" and r["back"] == "claude_code"
    assert r["putAtOnce"] == [{"backend": "codex", "allow_codex": True}]
    assert r["redrawn"] == 1
    assert "Built from Codex’s documentation and not yet tried with real accounts, nor measured with Margin." in r["says"]
    assert "Built from Codex’s documentation and not yet tried with real accounts, nor measured with Margin." in r["queueWords"]
    assert "At your plan's usage limit" in r["queueWords"] and "When Codex stops because your plan's usage limit is reached" in r["queueWords"]
    assert "The mix of local and" not in r["queueWords"]   # only beside a local model
    assert "Set up Codex (once)" in r["card"] and "Not on this computer yet" in r["card"]
    # until Codex is signed in, one line instead of the rows; the models come first, then thought, then helpers
    assert "Recommended models, applied automatically" in r["models"] and "Margin picks them once Codex is signed in." in r["models"]
    assert "gpt-6.2-sol" not in r["models"] and r["order"][1:4] == ["s-cli-models", "s-thought", "s-speed"]
    assert "Finish the set-up" in r["cardMid"] and "Codex is ready" not in r["cardMid"] and r["cardButton"] == "Add Margin to Codex…"
    assert "From Codex’s recommendations for your plan" in r["modelsMid"] and "In use" not in r["modelsMid"]
    assert r["optionAfter"] == "Recommended (gpt-6.2-sol)"
    assert r["steps"] == ["Install Codex", "Sign in", "Add Margin to Codex", "What Margin applied"] and r["first"].endswith("Install Codex")
    assert "Codex opens its sign-in page in your browser" in r["waiting"] and "Waiting for you to sign in" in r["waiting"]
    assert r["moved"].endswith("Add Margin to Codex") and r["ready"] is True
    assert "Codex is ready" in r["done"] and "$margin-run" in r["done"]
    assert "gpt-6.1-sol for judging excerpts" in r["done"]
    assert "Codex is ready" in r["after"]
    put = r["put"]
    assert put["backend"] == "codex" and put["allow_codex"] is True
    assert put["cli_models"] == {"codex": {"small": "", "middle": "", "strong": ""}}


@needs_node
def test_without_the_agent_setup_api_the_card_says_so(page):
    r = page["the agent-setup API is not there"]
    assert r["sub"] is True
    assert "could not be read" in r["card"] and [b["label"] for b in r["buttons"]] == ["Try again"]


@needs_node
def test_the_fixes_of_the_final_review(page):
    r = page["the fixes of the final review"]
    assert "Kept in a file in Margin’s folder that only you can read" in r["kept"] and "keychain" not in r["kept"]
    assert r["mistralBilling"].startswith("mistral.example/billing")
    assert r["articles"] == ["an", "a", "an"]
    assert "every task uses gemini-3.8-flash; a second opinion then comes from the same model." in r["one"].replace(" ;", ";")
    assert r["noAllow"] is None
    r = page["a shared project in the consent"]
    # I7 stage 3: the provider is the person's own choice in a shared project; the owner's limit, when set, is named
    assert "This project is shared with a team: the provider is your own choice, for your copy." in r["says"]
    assert "AI log" in r["says"]
    lim = page["a shared project with the owner's limit in the consent"]["says"]
    assert "The team uses Anthropic only (set by Anna). So Antigravity reads none of this project’s documents." in lim
    assert "the Enable Telemetry setting is on (in Antigravity’s settings)" in r["says"] and "Only documents that allow Google Gemini are sent" in r["says"]
    r = page["Antigravity's sign-in and what is added"]
    assert "switch off Enable Telemetry in Antigravity’s settings, under AI credits and feedback" in r["intro"]
    assert r["disabled"] is True and r["againEarly"] is True and r["opened"] == 1
    assert "under AI credits and feedback" in r["words"]
    assert "Margin’s own empty work folder, marked as trusted, where it starts Antigravity" in r["adds"]


@needs_node
def test_the_first_run_offers_codex_and_antigravity(page):
    r = page["the first run offers Codex and Antigravity"]
    assert r["others"] == ["codex", "antigravity"]
    assert "Codex (a ChatGPT plan)" in r["text"] and "Antigravity (a free Google account)" in r["text"]
    assert r["asked"] == "Let Codex read the excerpts, on your ChatGPT plan?"
    assert r["put"] == {"backend": "codex", "allow_codex": True}
    assert "The AI: Codex, on your ChatGPT plan" in r["codexStep"] and "Set up Codex" in r["codexStep"]
