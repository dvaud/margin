// I7 stage 3 (teamproviders.py): the *AI providers* card of Team › People and settings (#/team/settings?at=providers),
// after the Codebooks card. Each person reads with the cloud provider they choose on their own computer; the owner may
// limit the providers the team may use (off by default). The limit reaches every copy with the owner's other rules; a
// person whose provider is outside it has that work held, with a note naming the limit and who set it.
// For the owner: a switch *Limit the providers the team may use* with its help line; on, the providers as tick boxes and
// a small Save (DESIGN.md 5.5, as the Codebooks card). A Co-owner or a Member sees it as one sentence, with who set it.
// Built on GET/PUT …/owner/providers (gui/api_owner.py).
import { App, api, h, toast, showError, P, switchControl, button, helpMark, personMark } from "../lib.js";

export const PROVIDERS_API = (p) => `/api/projects/${p}/owner/providers`;   // GET; PUT {providers: [ids] | null}
export const LIMIT_LABEL = "Limit the providers the team may use";
const HELP = "Each person reads this project’s documents marked for cloud AI with the AI they chose on their own computer (Claude Code, Codex, Antigravity or an API key), for the providers they allowed there. With a limit, a provider outside it reads none of the project’s documents in anyone’s copy: that work waits, and the person is told who set the limit. Which documents may go to cloud AI at all stays as each document’s AI setting says.";

export const PROVIDERS_SECTION = {
  key: "providers",
  render: providersSection,
  load: (project) => api("GET", PROVIDERS_API(P(project))),
};

function sec(title, ...children) {
  const id = "team-h-providers";
  return h("section", { class: "team-section team-sec-providers", "aria-labelledby": id, dataset: { key: "providers" } },
    h("h3", { class: "team-h", id, tabindex: "-1" }, title), ...children);
}

const byWords = (who) => (who ? (who.me ? "you" : who.name) : "the owner");

function providersSection(ctx) {
  const v = ctx.data && ctx.data.providers;
  if (!v || !v.team) return null;
  return sec("AI providers", v.can_set ? ownerControls(ctx, v) : limitText(v));
}

// ---- for a Co-owner or a Member: the owner's word, in a sentence
function limitText(v) {
  const l = v.limit;
  return h("p", { class: "team-text", id: "team-providers-limit" },
    l ? [`The team uses ${l.titles} only. `, l.by ? [personMark([l.by.name]), ` Set by ${byWords(l.by)}.`] : "Set by the owner."]
      : "No limit: each person uses the cloud provider they choose.",
    " ", helpMark("About the providers the team may use", HELP));
}

// ---- for the owner
async function put(ctx, providers) {
  const v = await api("PUT", PROVIDERS_API(P(ctx.project)), { providers });
  if (ctx.data) ctx.data.providers = v;
  try { await App.refresh(); } catch (_) { /* the pages read it again when they open */ }
  await ctx.refresh({ force: true });
  return v;
}

function ownerControls(ctx, v) {
  const l = v.limit;
  const sw = switchControl(LIMIT_LABEL, !!l, { help: HELP });
  sw.input.id = "team-providers-on";
  const lab = sw.querySelector("label");
  if (lab) lab.htmlFor = sw.input.id;
  const picked = new Set(l ? l.providers : ["anthropic"]);
  const boxes = (v.choices || []).map((c) => {
    const box = h("input", { type: "checkbox", id: `team-prov-${c.id}`, value: c.id, checked: picked.has(c.id) });
    box.addEventListener("change", () => { if (box.checked) picked.add(c.id); else picked.delete(c.id); said(); });
    return h("label", { class: "it small provider-check", for: box.id }, box, " ", c.title);
  });
  const state = h("span", { class: "save-state", "aria-live": "polite" });
  const save = button({ sm: true, id: "team-providers-save" }, "Save");
  const list = h("fieldset", { class: "provider-checks", hidden: !l }, h("legend", { class: "field-label" }, "Providers the team may use"),
    ...boxes, h("div", { class: "row" }, save, state));
  function said() {
    const now = [...picked];
    const same = l && now.length === l.providers.length && now.every((x) => l.providers.includes(x));
    save.disabled = !now.length || !!same;
    state.textContent = !now.length ? "Tick at least one, or turn the limit off." : same ? (l.by ? `Set by ${byWords(l.by)}.` : "") : "Not saved yet.";
  }
  said();
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      const order = (v.choices || []).map((c) => c.id).filter((id) => picked.has(id));
      const after = await put(ctx, order);
      toast(`The team uses ${(after.limit && after.limit.titles) || "the providers you ticked"} only. Everyone sees it after the next round.`, "ok", { small: true, ttl: 6000 });
    } catch (e) { showError(e); said(); }
  });
  sw.input.addEventListener("change", async () => {
    const on = sw.input.checked;
    list.hidden = !on;
    said();
    if (on || !l) return;   // turned on: nothing is limited until Save
    sw.input.disabled = true;
    try {
      await put(ctx, null);
      toast("No limit: each person uses the cloud provider they choose.", "ok", { small: true, ttl: 6000 });
    } catch (e) {
      showError(e);
      sw.input.checked = true;
      sw.input.setAttribute("aria-checked", "true");
      list.hidden = false;
      sw.input.disabled = false;
    }
  });
  return h("div", { class: "owner-setting" }, sw, list);
}
