"""Stage 1 of other cloud providers in the page (views/ai-access.js, views/settings.js), run in Node (tests/_views.py):

- the Documents page keeps "Claude may read it" while no provider but Anthropic is set up, and says "Cloud AI may read
  it" with tick boxes of providers once one is (project default and per document);
- a shared project offers Anthropic only, and says why in one line;
- Settings → AI has one "API key" card (Claude first, then the other providers): a confirmation that names where the text goes, the provider,
  its key (only "stored: yes or no"), its models and "not yet measured".
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const LIST = [{ id: "anthropic", title: "Anthropic (Claude)", company: "Anthropic", lists_models: true },
  { id: "openai", title: "OpenAI", company: "OpenAI", lists_models: true, key_hint: "platform.openai.com → API keys", placeholder: "sk-…" },
  { id: "mistral", title: "Mistral", company: "Mistral AI", lists_models: true, key_hint: "console.mistral.ai → API keys" },
  { id: "azure", title: "Azure OpenAI", company: "Microsoft", lists_models: false, needs_address: true, recommended: { small: "gpt-6-luna", middle: "gpt-6.2-sol", strong: "gpt-6.2-astra" } }];
const NONE = { list: LIST, keys: { openai: false, mistral: false, azure: false }, route: "anthropic", set_up: [], other_set_up: false };
const OPENAI = { ...NONE, keys: { ...NONE.keys, openai: true }, set_up: ["openai"], other_set_up: true };
const DOC = { doc_id: "d1", title: "Field notes", file: "d1.pdf", ai_access: "cloud", own: null, note: "", budget: null, sent: 0.2,
  providers: ["anthropic"], providers_own: null, sent_by: { anthropic: 0.1, openai: 0.12 } };

await scenario("only Claude is set up", async (t) => {
  t.state({ settings: {}, providers: NONE });
  const m = await t.module("views/ai-access.js");
  return { title: m.LEVEL.cloud.title, many: m.LEVEL.cloud.many, short: m.LEVEL.cloud.short,
    card: m.providersDefaultCard("Study", { providers_default: ["anthropic"] }) === null, byLine: m.sentByLine({ sent_by: { anthropic: 0.3 } }) };
});

await scenario("OpenAI is set up: the project's choice", async (t) => {
  t.state({ settings: {}, providers: OPENAI });
  const m = await t.module("views/ai-access.js");
  t.answer("PUT /api/projects/Study/ai-access", (b) => ({ ai_access: { providers_default: b.providers_default } }));
  const card = m.providersDefaultCard("Study", { providers_default: ["anthropic"] }, () => {});
  document.getElementById("view").appendChild(card);
  const out = { title: m.LEVEL.cloud.title, summary: t.text(card.querySelector("summary")) };
  await t.click(card.querySelector("summary"));
  out.boxes = card.querySelectorAll("input[type=checkbox]").map((b) => [b.value, !!b.checked, !!b.disabled]);
  out.labels = card.querySelectorAll("label").map((l) => t.text(l));
  await t.click(card.querySelector('input[value="openai"]'));
  await t.click("Save", { within: card });
  out.put = t.calls.filter((c) => c.method === "PUT").map((c) => c.body);
  out.byLine = m.sentByLine(DOC);
  return out;
});

// I7 stage 3: in a shared project the person ticks their own; the owner's limit turns the others off and says why
await scenario("a shared project: your own choice, within the owner's limit", async (t) => {
  t.state({ settings: {}, providers: OPENAI });
  const m = await t.module("views/ai-access.js");
  const free = m.providersDefaultCard("Study", { providers_default: ["anthropic"], shared: true, team_limit: null }, () => {});
  const card = m.providersDefaultCard("Study", { providers_default: ["anthropic", "openai"], shared: true,
    team_limit: { providers: ["anthropic"] }, providers_note: "The team uses Anthropic only (set by Anna)." }, () => {});
  document.getElementById("view").append(free, card);
  await t.click(free.querySelector("summary"));
  await t.click(card.querySelector("summary"));
  const boxes = (c) => c.querySelectorAll("input[type=checkbox]").map((b) => [b.value, !!b.checked, !!b.disabled]);
  return { free: boxes(free), freeText: t.text(free), boxes: boxes(card), text: t.text(card) };
});

await scenario("one document's own providers", async (t) => {
  t.state({ settings: {}, providers: OPENAI });
  const m = await t.module("views/ai-access.js");
  t.answer("GET /api/projects/Study/documents/d1/ai-sent", { passages: [], share: 0.2 });
  t.answer("PUT /api/projects/Study/documents/ai-access", (b) => ({ documents: [], ai_access: {} }));
  const done = m.docAccessDialog("Study", DOC, "cloud", () => {}, { providers_default: ["anthropic"] });
  await t.settle(50);
  const d = t.dialog();
  const out = { options: d.querySelectorAll(".access-options input").length, text: t.text(d),
    boxes: d.querySelectorAll(".provider-checks input").map((b) => [b.value, !!b.checked]) };
  await t.click(d.querySelector('.provider-checks input[value="openai"]'));
  await t.click("Save", { within: d.querySelector(".dialog-actions") });
  await done;
  out.put = t.calls.filter((c) => c.method === "PUT").map((c) => c.body);
  return out;
});

await scenario("one document while only Claude is set up", async (t) => {
  t.state({ settings: {}, providers: NONE });
  const m = await t.module("views/ai-access.js");
  t.answer("GET /api/projects/Study/documents/d1/ai-sent", { passages: [], share: 0.2 });
  m.docAccessDialog("Study", { ...DOC, sent_by: undefined }, "cloud", () => {}, { providers_default: ["anthropic"] });
  await t.settle(50);
  const d = t.dialog();
  return { checks: d.querySelectorAll(".provider-checks").length, text: t.text(d) };
});

const FAR = { ...NONE, route: "other", route_address: "https://gpu.example.org/v1", set_up: ["other"], other_set_up: true };

await scenario("a server on another computer: the Documents page's line", async (t) => {
  t.state({ settings: { backend: "openai" }, providers: FAR });
  const m = await t.module("views/ai-access.js");
  t.answer("PUT /api/projects/Study/ai-access", (b) => ({ ai_access: { providers_default: b.providers_default } }));
  let saved = null;
  const line = m.remoteServerLine("Study", { providers_default: ["anthropic"] }, (r) => { saved = r; });
  document.getElementById("view").appendChild(line);
  const out = { text: t.text(line), dialogs: t.dialogs().length };
  await t.click("Allow it for this project", { within: line });
  out.put = t.calls.filter((c) => c.method === "PUT").map((c) => c.body);
  out.saved = !!saved;
  out.allowed = t.text(m.remoteServerLine("Study", { providers_default: ["anthropic", "other"] }));
  out.shared = t.text(m.remoteServerLine("Study", { providers_default: ["anthropic"], shared: true }));
  out.limited = t.text(m.remoteServerLine("Study", { providers_default: ["anthropic"], shared: true, team_limit: { providers: ["anthropic"] },
    providers_note: "The team uses Anthropic only (set by Anna)." }));
  t.state({ settings: {}, providers: NONE });
  out.claude = m.remoteServerLine("Study", {}) === null;
  return out;
});

await scenario("allowances that differ show the tick boxes while only Claude is set up", async (t) => {
  t.state({ settings: {}, providers: NONE });
  const m = await t.module("views/ai-access.js");
  t.answer("GET /api/projects/Study/documents/d1/ai-sent", { passages: [], share: 0 });
  const card = m.providersDefaultCard("Study", { providers_default: ["anthropic", "openai"] }, () => {});
  const byDoc = m.providersDefaultCard("Study", { providers_default: ["anthropic"] }, () => {}, [{ ...DOC, providers_own: ["mistral"] }]);
  m.docAccessDialog("Study", { ...DOC, providers: ["anthropic", "mistral"], providers_own: ["anthropic", "mistral"], sent_by: undefined }, "cloud", () => {}, { providers_default: ["anthropic"] });
  await t.settle(50);
  const d = t.dialog();
  return { card: card !== null, byDoc: byDoc !== null, boxes: d.querySelectorAll(".provider-checks input").map((b) => [b.value, !!b.checked]) };
});

await scenario("Settings: a server on another computer says what it reads", async (t) => {
  t.answer("GET /api/projects/Study", { ai_access: { providers_default: ["anthropic"] } });
  await settingsPage(t, { backend: "openai", openai_url: "https://gpu.example.org/v1" }, FAR);
  await t.settle(100);
  const line = t.view.querySelector(".remote-server-line");
  return { text: line ? t.text(line) : "", dialogs: t.dialogs().length };
});

async function settingsPage(t, settings, providers) {
  t.state({ settings, providers });
  t.answer("GET /api/servers", { servers: [], suggested: [] });
  t.answer("GET /api/claude-setup", {});
  t.answer("GET /api/local-status", {});
  t.answer("GET /api/projects/Study/queue", { kinds: [], waiting: 0 });
  t.answer("GET /api/projects/Study", { ai_access: { providers_default: ["anthropic"] } });
  t.answer("GET /api/projects/Study/agreement/plan?*", { kinds: [], problem: null, kept: [], plan: null });
  t.answer("GET /api/settings/provider-models?*", (b, path) => (path.includes("openai")
    ? { models: ["gpt-a", "gpt-b", "gpt-6-luna"], lists: true, recommended: { small: "gpt-6-luna", middle: "gpt-a", strong: "gpt-a" } }
    : { models: [], lists: false, recommended: { small: "gpt-6-luna", middle: "gpt-6.2-sol", strong: "gpt-6.2-astra" } }));
  await t.render("views/settings.js", "renderSettings", ["model"]);
  await t.settle(200);
}

await scenario("Settings: choosing another cloud provider", async (t) => {
  // the Settings rework: one API key card; picking it, and a provider inside it, asks first and the yes saves
  let saved = { backend: "claude_code", allow_claude_code: true };
  t.answer("PUT /api/settings", (b) => { saved = { ...saved, ...b }; return { settings: saved, backend_label: "x" }; });
  await settingsPage(t, saved, NONE);
  const out = { cards: t.view.querySelectorAll(".route-cards input[type=radio]").map((r) => r.value) };
  await t.click(t.view.querySelector('.route-cards input[value="apikey"]'));
  let d = t.dialog();
  out.askedClaude = t.text(d.querySelector("h2"));
  await t.click("Use the Claude API", { within: d });
  await t.settle(100);
  const redraw = async () => { document.getElementById("view").replaceChildren(); await t.render("views/settings.js", "renderSettings", ["model"]); await t.settle(200); };
  await redraw();
  out.claudeCard = t.text(t.view.querySelector(".cloud-provider"));
  await t.click(t.view.querySelector('.provider-cards input[value="openai"]'));
  d = t.dialog();
  out.asked = t.text(d.querySelector("h2"));
  out.says = t.text(d.querySelector(".dialog-body"));
  out.safe = t.text(d.querySelector("#dlg-safe"));
  await t.click("Use OpenAI", { within: d });
  await t.settle(100);
  await redraw();
  const box = t.view.querySelector(".cloud-provider");
  out.text = t.text(box);
  out.providers = box.querySelectorAll(".provider-cards input[type=radio]").map((r) => r.value);
  out.keyFields = box.querySelectorAll("input[type=password]").length;
  // the key's set-up: guided steps in a dialog, the key stored at the last one, the models applied as the done step
  t.answer("POST /api/settings/provider-key", (b) => ({ providers: OPENAI }));
  await t.click(box.querySelector("#cloud-key-setup"));
  await t.settle(10);
  const s = t.dialog();
  out.steps = s.querySelectorAll(".guided-step-title").map((x) => t.text(x).replace(/^Step \d of \d(, done)?: /, ""));
  out.waits = !!s.querySelector("#dlg-confirm").disabled;
  for (let i = 0; i < 3; i++) await t.click(s.querySelector(".guided-step[data-state=current] .guided-step-next"));
  out.keyType = s.querySelector("#key-openai").getAttribute("type");
  await t.type(s.querySelector("#key-openai"), "sk-secret-123");
  await t.click("Store the key", { within: s.querySelector(".dialog-actions") });
  await t.settle(100);
  out.done = t.text(s.querySelector(".guided-step[data-state=current]"));
  out.button = t.text(s.querySelector("#dlg-confirm"));
  await t.click(out.button, { within: s.querySelector(".dialog-actions") });
  await t.settle(100);
  out.after = t.text(t.view.querySelector(".cloud-provider"));
  out.keyPost = t.calls.filter((c) => c.path === "/api/settings/provider-key").map((c) => c.body);
  out.puts = t.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").map((c) => c.body);
  // Technical › the provider's models: saved as soon as one is chosen
  document.getElementById("view").replaceChildren();
  t.answer("GET /api/routing", { route: "cloud_api", route_name: "OpenAI", rows: [], aliases: [], step_up_below: 0.6, plan: {} });
  t.answer("GET /api/whats-new", {});
  await t.render("views/settings.js", "renderSettings", ["advanced"]);
  await t.settle(200);
  const models = t.view.querySelector("#s-cloud-models");
  out.modelsText = t.text(models);
  out.models = models.querySelectorAll("#m-cloud-middle option").map((o) => o.value);
  await t.type(models.querySelector("#m-cloud-middle"), "gpt-b");
  await t.settle(50);
  out.state = t.text(models);
  out.put = t.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").map((c) => c.body).pop() || null;
  return out;
});

// a key the provider refuses is not kept, and the dialog stays at the paste step
await scenario("Settings: a refused key", async (t) => {
  await settingsPage(t, { backend: "cloud_api", allow_cloud: true, cloud_provider: "openai" }, NONE);
  t.answer("POST /api/settings/provider-key", (b) => ({ providers: OPENAI }));
  t.answer("GET /api/settings/provider-models?*", { models: [], lists: true, problem: "OpenAI refused the key (401).", refused: true, recommended: {} });
  t.answer("DELETE /api/settings/provider-key", () => ({ providers: NONE }));
  const box = t.view.querySelector(".cloud-provider");
  await t.click(box.querySelector("#cloud-key-setup"));
  await t.settle(10);
  const s = t.dialog();
  for (let i = 0; i < 3; i++) await t.click(s.querySelector(".guided-step[data-state=current] .guided-step-next"));
  await t.type(s.querySelector("#key-openai"), "sk-wrong");
  await t.click("Store the key", { within: s.querySelector(".dialog-actions") });
  await t.settle(100);
  const out = { error: t.text(s.querySelector(".field-error")), at: t.text(s.querySelector(".guided-step[data-state=current] .guided-step-title")),
    deletes: t.calls.filter((c) => c.method === "DELETE").map((c) => c.body), button: t.text(s.querySelector("#dlg-confirm")), open: s.open !== false };
  await t.click("Cancel", { within: s.querySelector(".dialog-actions") });
  const ask = t.dialog(); if (ask && ask !== s) await t.click("Stop the set-up", { within: ask.querySelector(".dialog-actions") });
  return out;
});

// the provider could not be reached: the key is stored, and the done step says it was not checked
await scenario("Settings: a key that could not be checked", async (t) => {
  await settingsPage(t, { backend: "cloud_api", allow_cloud: false, cloud_provider: "openai" }, NONE);
  t.answer("POST /api/settings/provider-key", (b) => ({ providers: OPENAI }));
  t.answer("GET /api/settings/provider-models?*", { models: [], lists: true, problem: "Could not reach OpenAI. Check the internet connection.", refused: false, recommended: {} });
  const box = t.view.querySelector(".cloud-provider");
  await t.click(box.querySelector("#cloud-key-setup"));
  await t.settle(10);
  const s = t.dialog();
  for (let i = 0; i < 3; i++) await t.click(s.querySelector(".guided-step[data-state=current] .guided-step-next"));
  await t.type(s.querySelector("#key-openai"), "sk-ok");
  await t.click("Store the key", { within: s.querySelector(".dialog-actions") });
  await t.settle(100);
  const out = { done: t.text(s.querySelector(".guided-step[data-state=current]")), deletes: t.calls.filter((c) => c.method === "DELETE").length };
  t.answer("PUT /api/settings", (b) => ({ settings: { ...b }, backend_label: "OpenAI (API key)", providers: OPENAI }));
  out.button = t.text(s.querySelector("#dlg-confirm"));
  await t.click(out.button, { within: s.querySelector(".dialog-actions") });   // the main button saves the route at once
  await t.settle(100);
  out.put = t.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").map((c) => c.body);
  return out;
});

// a key stored earlier that the provider now refuses: said in the status card and on the provider's card
await scenario("Settings: a stored key that is refused later", async (t) => {
  t.answer("GET /api/settings/provider-models?*", { models: [], lists: true, problem: "OpenAI refused the key (401).", refused: true, recommended: {} });
  await settingsPage(t, { backend: "cloud_api", allow_cloud: true, cloud_provider: "openai" }, OPENAI);
  // settingsPage answers the models with a list: the provider refuses the key from now on, and the page is drawn again
  t.answer("GET /api/settings/provider-models?*", { models: [], lists: true, problem: "OpenAI refused the key (401).", refused: true, recommended: {} });
  document.getElementById("view").replaceChildren();
  await t.render("views/settings.js", "renderSettings", ["model"]);
  await t.settle(200);
  const box = t.view.querySelector(".cloud-provider");
  const out = { status: t.text(box.querySelector(".provider-status")), cards: t.text(box.querySelector(".provider-cards")) };
  document.getElementById("view").replaceChildren();
  t.answer("GET /api/routing", { route: "cloud_api", route_name: "OpenAI", rows: [], aliases: [], step_up_below: 0.6, plan: {} });
  t.answer("GET /api/whats-new", {});
  await t.render("views/settings.js", "renderSettings", ["advanced"]);
  await t.settle(200);
  out.models = t.text(t.view.querySelector("#s-cloud-models"));
  return out;
});

await scenario("Settings: Azure asks for its address and the deployments' names", async (t) => {
  await settingsPage(t, { backend: "cloud_api", allow_cloud: true, cloud_provider: "azure", cloud_model: "my-dep" }, NONE);
  const box = t.view.querySelector(".cloud-provider");
  const out = { address: !!box.querySelector("#azure-url") && !t.hidden(box.querySelector("#azure-url")) };
  // the deployments' names are under Technical › the provider's models
  document.getElementById("view").replaceChildren();
  t.answer("GET /api/routing", { route: "cloud_api", route_name: "Azure OpenAI", rows: [], aliases: [], step_up_below: 0.6, plan: {} });
  t.answer("GET /api/whats-new", {});
  await t.render("views/settings.js", "renderSettings", ["advanced"]);
  await t.settle(200);
  const m = t.view.querySelector("#s-cloud-models");
  return { ...out, text: t.text(m), model: m.querySelector("#m-cloud-middle-txt").value,
    small: m.querySelector("#m-cloud-small-txt").value, lists: m.querySelectorAll("#m-cloud-middle option").length };
});

await scenario("Settings on a local-only computer", async (t) => {
  t.state({ settings: { backend: "auto" }, providers: NONE, local_only: true });
  t.answer("GET /api/servers", { servers: [], suggested: [] });
  t.answer("GET /api/local-status", {});
  t.answer("GET /api/projects/Study/queue", { kinds: [], waiting: 0 });
  t.answer("GET /api/projects/Study/agreement/plan?*", { kinds: [], problem: null, kept: [], plan: null });
  await t.render("views/settings.js", "renderSettings", ["model"]);
  await t.settle(200);
  return { cards: t.view.querySelectorAll(".route-cards input[type=radio]").map((r) => r.value) };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("providers_views"))


@needs_node
def test_the_words_stay_claude_until_another_provider_is_set_up(page):
    r = page["only Claude is set up"]
    assert (r["title"], r["many"], r["short"]) == ("Claude may read it", "Claude may read them", "Claude")
    assert r["card"] is True and r["byLine"] == ""          # no tick boxes, no per-provider line
    r = page["OpenAI is set up: the project's choice"]
    assert r["title"] == "Cloud AI may read it"
    assert r["summary"] == "Cloud AI may read it: Anthropic (Claude)"
    assert r["boxes"] == [["anthropic", True, False], ["openai", False, False]]   # Anthropic and what is set up
    assert r["put"] == [{"providers_default": ["anthropic", "openai"]}]
    assert r["byLine"] == "Claude 10% · OpenAI 12%"


@needs_node
def test_a_shared_project_offers_your_own_choice_within_the_owners_limit(page):
    r = page["a shared project: your own choice, within the owner's limit"]
    assert r["free"] == [["anthropic", True, False], ["openai", False, False]]
    assert "This is your own choice: each person in the team chooses theirs" in r["freeText"]
    assert r["boxes"] == [["anthropic", True, False], ["openai", True, True]]   # given before: kept, off now
    assert "The team uses Anthropic only (set by Anna)." in r["text"]


@needs_node
def test_a_documents_own_providers_are_ticked_in_its_dialog(page):
    r = page["one document's own providers"]
    assert "Cloud AI may read it" in r["text"] and "Read by each cloud provider: Claude 10% · OpenAI 12%" in r["text"]
    assert r["boxes"] == [["anthropic", True], ["openai", False]]
    assert r["put"] == [{"doc_ids": ["d1"], "note": "", "budget": "", "providers": ["anthropic", "openai"]}]
    r = page["one document while only Claude is set up"]
    assert r["checks"] == 0 and "Claude may read it" in r["text"] and "Cloud AI" not in r["text"]


@needs_node
def test_settings_offers_another_cloud_provider_with_a_key_kept_out_of_the_page(page):
    r = page["Settings: choosing another cloud provider"]
    # the Settings rework: 2 × 2, one API key card holding Claude (first) and the other providers
    assert r["cards"] == ["subscription", "apikey", "local", "baseline"]
    assert r["askedClaude"] == "Let the Claude API read the excerpts, billed to your key?"
    assert "Not set up yet: nothing is sent until a key is stored" in r["claudeCard"] and "Recommended" in r["claudeCard"]
    assert r["asked"] == "Let OpenAI read the excerpts, billed to your key?" and r["safe"] == "Stay with the Claude API"
    assert "Only documents that allow OpenAI are sent" in r["says"] and "allows Anthropic only" in r["says"]
    assert "OpenAI’s servers" in r["says"] and "billed to the API key you store" in r["says"] and "not yet measured" in r["says"]
    assert r["providers"] == ["anthropic", "openai", "mistral", "azure"] and r["keyFields"] == 0   # no bare key field on the page
    assert "Not set up yet: nothing is sent until a key is stored" in r["text"] and "not yet measured" in r["text"] and "Set up OpenAI…" in r["text"]
    assert r["steps"] == ["Make an account on OpenAI’s API platform", "Add credit", "Make a key for Margin", "Paste the key here", "What Margin applied"]
    assert r["waits"] is True and r["keyType"] == "password"
    assert r["keyPost"] == [{"provider": "openai", "key": "sk-secret-123"}]
    assert "OpenAI is set up" in r["done"] and "OpenAI accepted it" in r["done"]
    assert "gpt-6-luna for labels and links, gpt-a for judging excerpts and gpt-a for second opinions" in r["done"]
    assert r["button"] == "Done" and "Left to do" not in r["done"]   # the yes of the dialog had saved the route already
    assert r["puts"] == [{"allow_cloud": True, "backend": "anthropic"}, {"allow_cloud": True, "backend": "cloud_api", "cloud_provider": "openai"}]
    assert "Key stored in this computer’s keychain" in r["after"] and "Key stored" in r["after"] and "sk-secret" not in r["after"]
    assert "OpenAI’s models" in r["modelsText"] and "In use" not in r["modelsText"]
    assert r["models"][:4] == ["", "gpt-a", "gpt-b", "gpt-6-luna"] and r["models"][-1] == "__other"
    assert "Your choice" in r["state"] and "In use" not in r["state"]
    assert r["put"] == {"cloud_small_model": "", "cloud_model": "gpt-b", "cloud_strong_model": ""}
    assert "sk-secret" not in str(r["puts"])


@needs_node
def test_azure_and_local_only(page):
    r = page["Settings: Azure asks for its address and the deployments' names"]
    assert r["address"] and r["model"] == "my-dep" and r["small"] == "" and r["lists"] == 0
    assert "Your deployments" in r["text"] and "gpt-6-luna, gpt-6.2-sol, gpt-6.2-astra" in r["text"]
    assert page["Settings on a local-only computer"]["cards"] == ["local", "baseline"]


@needs_node
def test_a_server_on_another_computer_says_so_in_place_with_a_button(page):
    r = page["a server on another computer: the Documents page's line"]
    assert "A server on another computer (https://gpu.example.org/v1) reads only documents you allow it to." in r["text"]
    assert r["dialogs"] == 0                                          # no pop-up
    assert r["put"] == [{"providers_default": ["anthropic", "other"]}] and r["saved"]
    assert "This project allows it." in r["allowed"]
    assert "Allow it for this project" in r["shared"]   # I7 stage 3: a shared project allows it as any other
    assert "The team uses Anthropic only (set by Anna)." in r["limited"] and "Allow it" not in r["limited"]
    assert r["claude"] is True                                        # on Claude's routes: no line
    r = page["Settings: a server on another computer says what it reads"]
    assert "reads only documents you allow it to" in r["text"] and "Allow it for this project" in r["text"]
    assert r["dialogs"] == 0


@needs_node
def test_differing_allowances_show_the_tick_boxes_without_another_provider(page):
    r = page["allowances that differ show the tick boxes while only Claude is set up"]
    assert r["card"] and r["byDoc"]
    assert r["boxes"] == [["anthropic", True], ["mistral", True]]


@needs_node
def test_a_refused_key_stays_at_the_paste_step_and_is_forgotten(page):
    r = page["Settings: a refused key"]
    assert r["error"] == "OpenAI refused this key. Copy it again from the keys page."
    assert r["at"].endswith("Paste the key here") and r["button"] == "Store the key"
    assert r["deletes"] == [{"provider": "openai"}]


@needs_node
def test_a_key_that_could_not_be_checked_says_so_and_the_main_button_saves_the_route(page):
    r = page["Settings: a key that could not be checked"]
    assert "The key is stored, not checked yet" in r["done"] and "could not be asked whether it works" in r["done"]
    assert "Settings → AI" not in r["done"] and r["deletes"] == 0
    assert r["button"] == "Allow cloud models and use OpenAI"
    assert r["put"] == [{"allow_cloud": True, "backend": "cloud_api", "cloud_provider": "openai"}]


@needs_node
def test_a_stored_key_the_provider_refuses_later_is_flagged(page):
    r = page["Settings: a stored key that is refused later"]
    assert "OpenAI refused the stored key" in r["status"] and "Key refused" in r["cards"]
    assert "refused the stored key" in r["models"]   # Technical › the provider's models says so too
