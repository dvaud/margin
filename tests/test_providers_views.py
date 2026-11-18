"""Stage 1 of other cloud providers in the page (views/ai-access.js, views/settings.js), run in Node (tests/_views.py):

- the Documents page keeps "Claude may read it" while no provider but Anthropic is set up, and says "Cloud AI may read
  it" with tick boxes of providers once one is (project default and per document);
- a shared project offers Anthropic only, and says why in one line;
- Settings → AI has "Another cloud provider (API key)": a confirmation that names where the text goes, the provider,
  its key (only "stored: yes or no"), its models and "not yet measured".
"""
from __future__ import annotations

import pytest

from _views import needs_node, run_views

PROBE = r"""
const LIST = [{ id: "anthropic", title: "Anthropic (Claude)", company: "Anthropic", lists_models: true },
  { id: "openai", title: "OpenAI", company: "OpenAI", lists_models: true, key_hint: "platform.openai.com → API keys", placeholder: "sk-…" },
  { id: "mistral", title: "Mistral", company: "Mistral AI", lists_models: true, key_hint: "console.mistral.ai → API keys" },
  { id: "azure", title: "Azure OpenAI", company: "Microsoft", lists_models: false, needs_address: true }];
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

await scenario("a shared project: Anthropic only, and why", async (t) => {
  t.state({ settings: {}, providers: OPENAI });
  const m = await t.module("views/ai-access.js");
  const card = m.providersDefaultCard("Study", { providers_default: ["anthropic"], shared: true,
    providers_note: "Other providers come to shared projects later: your colleagues have not agreed to them. Only Anthropic may read this project's documents." }, () => {});
  document.getElementById("view").appendChild(card);
  await t.click(card.querySelector("summary"));
  return { boxes: card.querySelectorAll("input[type=checkbox]").map((b) => [b.value, !!b.checked, !!b.disabled]), text: t.text(card) };
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
  t.answer("GET /api/projects/Study/agreement/plan?*", { kinds: [], problem: null, kept: [], plan: null });
  t.answer("GET /api/settings/provider-models?*", (b, path) => (path.includes("openai") ? { models: ["gpt-a", "gpt-b"], lists: true } : { models: [], lists: false }));
  await t.render("views/settings.js", "renderSettings", ["model"]);
  await t.settle(200);
}

await scenario("Settings: choosing another cloud provider", async (t) => {
  await settingsPage(t, { backend: "claude_code", allow_claude_code: true }, NONE);
  const out = { cards: t.view.querySelectorAll(".route-cards input[type=radio]").map((r) => r.value) };
  await t.click(t.view.querySelector('.route-cards input[value="cloud_api"]'));
  const d = t.dialog();
  out.asked = t.text(d.querySelector("h2"));
  out.says = t.text(d.querySelector(".dialog-body"));
  await t.click("Continue with another provider", { within: d });
  await t.settle(100);
  const box = t.view.querySelector(".cloud-provider");
  out.text = t.text(box);
  out.keyType = box.querySelector("#cloud-key").getAttribute("type");
  t.answer("POST /api/settings/provider-key", (b) => ({ providers: OPENAI }));
  await t.type(box.querySelector("#cloud-key"), "sk-secret-123");
  await t.click("Save the key", { within: box });
  await t.settle(100);
  const box2 = t.view.querySelector(".cloud-provider");
  out.after = t.text(box2);
  out.keyField = box2.querySelector("#cloud-key").value;
  out.models = box2.querySelectorAll("#m-cloud option").map((o) => o.value);
  out.keyPost = t.calls.filter((c) => c.path === "/api/settings/provider-key").map((c) => c.body);
  await t.type(box2.querySelector("#m-cloud"), "gpt-b");
  t.answer("PUT /api/settings", (b) => ({ settings: { ...b }, backend_label: "OpenAI (API key) · gpt-b", providers: OPENAI }));
  await t.click(t.view.querySelector(".cloud-box input[type=checkbox]"));
  await t.click("Save");
  out.put = t.calls.filter((c) => c.method === "PUT" && c.path === "/api/settings").map((c) => c.body).pop() || null;
  return out;
});

await scenario("Settings: Azure asks for its address and a deployment's name", async (t) => {
  await settingsPage(t, { backend: "cloud_api", allow_cloud: true, cloud_provider: "azure", cloud_model: "my-dep" }, NONE);
  const box = t.view.querySelector(".cloud-provider");
  return { text: t.text(box), address: !t.hidden(box.querySelector("#azure-url")), model: box.querySelector("#m-cloud-txt").value,
    lists: box.querySelectorAll("#m-cloud option").length };
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
def test_a_shared_project_offers_anthropic_only_and_says_why(page):
    r = page["a shared project: Anthropic only, and why"]
    assert r["boxes"] == [["anthropic", True, False], ["openai", False, True]]
    assert "your colleagues have not agreed to them" in r["text"]


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
    assert r["cards"] == ["claude_code", "local", "baseline", "anthropic", "cloud_api"]
    assert r["asked"] == "Use another cloud provider with your API key?"
    assert "Only documents that allow that provider are sent" in r["says"] and "allows Anthropic only" in r["says"]
    assert "With OpenAI the hypothesis and the excerpts read leave this computer for OpenAI" in r["text"]
    assert "No key stored yet" in r["text"] and "not yet measured" in r["text"]
    assert r["keyType"] == "password"
    assert r["keyPost"] == [{"provider": "openai", "key": "sk-secret-123"}]
    assert "A key is stored on this computer" in r["after"] and r["keyField"] == "" and "sk-secret" not in r["after"]
    assert r["models"][1:3] == ["gpt-a", "gpt-b"]
    put = r["put"]
    assert put["backend"] == "cloud_api" and put["allow_cloud"] is True and put["cloud_provider"] == "openai"
    assert put["cloud_model"] == "gpt-b" and "sk-secret" not in str(put)


@needs_node
def test_azure_and_local_only(page):
    r = page["Settings: Azure asks for its address and a deployment's name"]
    assert r["address"] and r["model"] == "my-dep" and r["lists"] == 0
    assert "Azure lists no models: type your deployment's name." in r["text"]
    assert page["Settings on a local-only computer"]["cards"] == ["local", "baseline"]


@needs_node
def test_a_server_on_another_computer_says_so_in_place_with_a_button(page):
    r = page["a server on another computer: the Documents page's line"]
    assert "A server on another computer (https://gpu.example.org/v1) reads only documents you allow it to." in r["text"]
    assert r["dialogs"] == 0                                          # no pop-up
    assert r["put"] == [{"providers_default": ["anthropic", "other"]}] and r["saved"]
    assert "This project allows it." in r["allowed"]
    assert "your colleagues have not agreed to them" in r["shared"]
    assert r["claude"] is True                                        # on Claude's routes: no line
    r = page["Settings: a server on another computer says what it reads"]
    assert "reads only documents you allow it to" in r["text"] and "Allow it for this project" in r["text"]
    assert r["dialogs"] == 0


@needs_node
def test_differing_allowances_show_the_tick_boxes_without_another_provider(page):
    r = page["allowances that differ show the tick boxes while only Claude is set up"]
    assert r["card"] and r["byDoc"]
    assert r["boxes"] == [["anthropic", True], ["mistral", True]]
