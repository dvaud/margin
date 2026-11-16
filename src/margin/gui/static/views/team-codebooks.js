// Team codebooks (teamcodebooks.py): the *Codebooks* card of Team › People and settings (#/team/settings?at=codebooks),
// after the Owner card. Two settings of the owner, which reach every copy of the project:
// - the switch *Codebooks made in this project are shared with the team* (on by default): a codebook made in the
//   project is shared as soon as it is made, by its maker; codebooks made before stay as they are;
// - the select *Default codebook for this project*: the codebook the pages use when none is named (the Profile page,
//   a document's Codes panel, the codes new documents get), in place of each computer's own setting. Not set: each
//   computer's setting. The owner's own private codebook may be picked: it is then shared, and the line beside the
//   select says so.
// A Co-owner or a Member sees both as text, with who set them. Built on GET/PUT …/owner/codebooks (gui/api_owner.py,
// docs/API.md) and the components of docs/DESIGN.md 5.5: a switch with its help line, a field with a select, a help mark.
import { App, api, h, toast, showError, P, switchControl, select, field, helpMark, personMark } from "../lib.js";

export const CODEBOOKS_API = (p) => `/api/projects/${p}/owner/codebooks`;   // GET; PUT {share} | {default}
export const SHARE_LABEL = "Codebooks made in this project are shared with the team";
const SHARE_HELP = "A codebook made in this project (fresh, from themes or theory, a copy or an imported file) is shared as soon as it is made; the research log says why. Codebooks made before stay as they are: their maker can share them from the Codebooks page. Anyone can still unshare one of their own. Turned off, nothing is taken back. Codebooks kept with all projects are not covered.";
const DEFAULT_LABEL = "Default codebook for this project";
const DEFAULT_HELP = "The codebook the Profile page, a document’s Codes panel and the codes of new documents use when none is chosen, in every copy of the project. It takes the place of each computer’s own setting (Settings › Exploring the documents) here; a page’s own codebook picker still lets anyone look with another one.";
const NONE = "";   // the select's value for "no default"

export const CODEBOOKS_SECTION = {
  key: "codebooks",
  render: codebooksSection,
  load: (project) => api("GET", CODEBOOKS_API(P(project))),
};

function sec(title, ...children) {
  const id = "team-h-codebooks";
  return h("section", { class: "team-section team-sec-codebooks", "aria-labelledby": id, dataset: { key: "codebooks" } },
    h("h3", { class: "team-h", id, tabindex: "-1" }, title), ...children);
}

const byWords = (who) => (who ? (who.me ? "you" : who.name) : "the owner");

function codebooksSection(ctx) {
  const v = ctx.data && ctx.data.codebooks;
  if (!v || !v.team) return null;
  return sec("Codebooks", v.can_set ? shareSwitch(ctx, v) : shareText(v), v.can_set ? defaultPicker(ctx, v) : defaultText(v));
}

// ---- for a Co-owner or a Member: what the owner set, in words ----
function shareText(v) {
  const s = v.share_codebooks || {};
  return h("p", { class: "team-text", id: "team-codebooks-share" },
    s.on ? "Codebooks made in this project are shared with the team as soon as they are made." : "Codebooks made in this project stay private until their maker shares them.",
    s.by ? [" ", personMark([s.by.name]), ` Set by ${byWords(s.by)}.`] : " The owner’s setting.",
    " ", helpMark("About sharing codebooks", SHARE_HELP));
}

function defaultText(v) {
  const d = v.default;
  return h("p", { class: "team-text", id: "team-codebooks-default" },
    d ? [`Default codebook: “${d.title}”`, d.here ? "" : " (not on this computer yet: your own setting holds until it comes)", `, set by ${byWords(d.by)}.`]
      : "No default codebook: each computer’s own setting holds (Settings › Exploring the documents).",
    " ", helpMark("About the default codebook", DEFAULT_HELP));
}

// ---- for the owner ----
async function put(ctx, body) {
  const v = await api("PUT", CODEBOOKS_API(P(ctx.project)), body);
  if (ctx.data) ctx.data.codebooks = v;
  try { await App.refresh(); } catch (_) { /* the pages read it again when they open */ }
  await ctx.refresh({ force: true });
  return v;
}

function shareSwitch(ctx, v) {
  const s = v.share_codebooks || {};
  const sw = switchControl(SHARE_LABEL, !!s.on, { help: SHARE_HELP });
  sw.input.id = "team-codebooks-share";
  const lab = sw.querySelector("label");
  if (lab) lab.htmlFor = sw.input.id;
  sw.input.addEventListener("change", async () => {
    const want = sw.input.checked;
    sw.input.disabled = true;
    try {
      await put(ctx, { share: want });
      toast(want ? "Codebooks made in this project are shared with the team from now on." : "New codebooks stay private until their maker shares them. Nothing shared was taken back.", "ok", { small: true, ttl: 6000 });
      const again = document.getElementById("team-codebooks-share");
      if (again) again.focus();
    } catch (e) {
      showError(e);
      sw.input.checked = !want;
      sw.input.setAttribute("aria-checked", sw.input.checked ? "true" : "false");
      sw.input.disabled = false;
    }
  });
  return h("div", { class: "owner-setting" }, sw);
}

function optionWords(c) {
  if (c.source === "bundled") return `${c.title} (ships with Margin)`;
  return c.state === "shared" ? c.title : `${c.title} (yours, private: shared when you choose it)`;
}

function defaultPicker(ctx, v) {
  const d = v.default;
  const choices = v.choices || [];
  const known = new Set(choices.map((c) => c.name));
  const sel = select({ id: "team-codebooks-default" },
    h("option", { value: NONE, selected: !d }, "None: each computer’s own setting"),
    choices.map((c) => h("option", { value: c.name, selected: !!d && d.name === c.name }, optionWords(c))),
    // a default whose codebook is not here (a colleague's, not arrived yet): kept as it is until the owner changes it
    d && !known.has(d.name) ? h("option", { value: d.name, selected: true, disabled: true }, `${d.title || d.name} (not on this computer)`) : null);
  const said = h("span", { id: "team-codebooks-default-said", "aria-live": "polite" }, pickedWords(v, d ? d.name : NONE));
  sel.addEventListener("change", async () => {
    const want = sel.value;
    said.textContent = pickedWords(v, want);
    sel.disabled = true;
    try {
      const after = await put(ctx, { default: want || null });
      const c = choices.find((x) => x.name === want);
      toast(!want ? "This project has no default codebook now: each computer’s own setting holds."
        : `“${(after.default && after.default.title) || want}” is this project’s default codebook${c && c.source === "project" && c.state !== "shared" ? ", and it is shared with the team now" : ""}.`, "ok", { small: true, ttl: 6000 });
      const again = document.getElementById("team-codebooks-default");
      if (again) again.focus();
    } catch (e) {
      showError(e);
      sel.value = d ? d.name : NONE;
      said.textContent = pickedWords(v, sel.value);
      sel.disabled = false;
    }
  });
  return h("div", { class: "owner-setting" },
    field(DEFAULT_LABEL, sel, { help: [said, " ", helpMark("About the default codebook", DEFAULT_HELP)] }));
}

// the line beside the select: what the choice does now (a private one of yours is shared when you choose it)
function pickedWords(v, name) {
  if (!name) return "None set: each computer uses its own setting.";
  const c = (v.choices || []).find((x) => x.name === name);
  if (c && c.source === "project" && c.state !== "shared") return `Choosing “${c.title}” shares it with the team, so every copy can use it.`;
  return "Every copy of the project uses it when no codebook is chosen.";
}
