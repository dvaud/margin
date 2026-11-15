// The Team page of a project that has no team yet: what a person came to do, in their words. Two cards, *Start a team
// for this project* (you are the first: choose where the team's shared work is kept, then set that up) and *Join a
// colleague's team* (an invite link, or a folder they share with you), and a third for the one-off (*Send it once, as a
// file*). Above them, when a colleague's shared folder for this project is already among this computer's cloud
// folders, a notice offers it.
// Where the shared work is kept is an option card each (docs/DESIGN.md 4.7), named by what it is and who it suits; the
// card's one main button says what pressing it starts. A storage space is then set up step by step in a dialog
// (team-space.js setupDialog, the guided steps of 4.28); a shared folder is chosen in a dialog here (folderDialog).
// The sections are drawn by the Team page's panel (team.js teamPanel, `ctx`); placed in views.css ("Working together").
import { App, api, h, replace, toast, showError, P, field, switchControl, helpMark, button, link, input, fold, notice,
  dialog, listRow, listGroup, aiWhere, optionCards, setBusy } from "../lib.js";
import { zipButton, ZIP_WORDS } from "./share.js";
import { cleanPath, folderAsSeen, KEEP_OUT_LABEL, KEEP_OUT_HELP } from "./team-state.js";
import { setupDialog, joinDialog, firstRound } from "./team-space.js";

const mac = () => /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent || "");
const win = () => /Win/i.test(navigator.platform || navigator.userAgent || "");

function section(key, title, ...children) {
  const id = `team-h-${key}`;
  return h("section", { class: `team-section team-sec-${key}`, "aria-labelledby": id, dataset: { key } },
    h("h3", { class: "team-h", id }, title), ...children.filter((c) => c !== null && c !== undefined));
}

const HOW_HELP = "Each of you keeps your own copy of this project on your own computer. Margin puts what you share in the place you choose here and brings in what your colleagues share, by itself. Nothing of yours goes to the team until you press Share on it: a check, a set of themes, a codebook, a note, an entry of your own or a link between terms.";

// Where the team's shared work can be kept: what it is, who it suits, and what its button starts
const SEALED = "It will hold the documents’ text and files and only what you share of your own work, encrypted on this computer before it is sent, with a key only your team has: the service cannot read it.";
export const WHERE = [
  { value: "b2", icon: "database", title: "A storage space at Backblaze", tag: "Recommended", go: "Set up at Backblaze…", holds: SEALED,
    text: "Online storage only your team can read. Free, no payment card, kept in the EU; you make one account, your colleagues need none." },
  { value: "webdav", icon: "library", title: "Your institution’s drive", go: "Set up in your institution’s drive…", holds: SEALED,
    text: "A folder in SURFdrive, SURF Research Drive or a Nextcloud, which only your team can read. No new account, but every colleague needs one at the same drive." },
  { value: "r2", icon: "database", title: "A storage space at Cloudflare", go: "Set up at Cloudflare…", holds: SEALED,
    text: "Online storage only your team can read, for large teams that grow quickly. Asks for a payment card; nothing is charged within the free amount." },
  { value: "folder", icon: "folder", title: "A folder you already share", go: "Choose the folder…",
    holds: "The folder will hold the documents’ text and files, and only what you share of your own work. Your project’s database stays on this computer.",
    text: "A folder in OneDrive, Dropbox, Google Drive or on a network drive that every colleague has on their computer. Nothing to sign up for." },
];

const noTeam = (ctx) => !ctx.status.folder && !ctx.status.space;

// ---- the cloud folders this computer has, and a colleague's shared folder for this project among them
let cloudAnswer = null;
function cloudFolders() {
  if (!cloudAnswer) cloudAnswer = api("GET", "/api/cloud-folders").catch(() => ({ folders: [], picker: false }));
  return cloudAnswer;
}
// read once per project while the set-up shows (kept in ctx.setup, which the panel makes afresh for another project);
// when a colleague's folder is found, the page is drawn again so the notice shows
function offersOf(ctx) {
  const typed = ctx.setup;
  if (typed.offers) return typed.offers;
  const o = typed.offers = { loaded: false, folders: [], picker: false, found: [], ready: null };
  const project = ctx.project;
  o.ready = Promise.all([cloudFolders(), api("GET", `/api/projects/${P(project)}/shared-folder/find`).catch(() => ({ found: [] }))])
    .then(([cloud, find]) => {
      Object.assign(o, { loaded: true, folders: cloud.folders || [], picker: !!cloud.picker, found: find.found || [] });
      if (o.found.length && ctx.setup === typed && ctx.project === project) ctx.refresh({ force: true });
      return o;
    });
  return o;
}

// ---------------------------------------------------------------------------------------------
// a colleague's shared folder is already on this computer
// ---------------------------------------------------------------------------------------------
function foundSection(ctx) {
  if (!noTeam(ctx)) return null;
  const o = offersOf(ctx);
  if (!o.found.length) return null;
  const dir = o.found[0];
  const seen = folderAsSeen(dir, o.folders);
  return section("found", "Your colleague’s shared folder is on this computer",
    notice({ kind: "info", role: "note" },
      h("p", {}, "A colleague already works on this project through the folder ", h("strong", { title: dir }, seen.text), ". Use it to join them."),
      button({ sm: true, icon: "folder", id: "team-found-use", onClick: () => folderDialog(ctx, { path: dir, joining: true }) }, "Use this folder…")));
}

// ---------------------------------------------------------------------------------------------
// start a team: where its shared work is kept
// ---------------------------------------------------------------------------------------------
function startSection(ctx) {
  if (!noTeam(ctx)) return null;
  const typed = ctx.setup;
  const chosen = () => WHERE.find((w) => w.value === typed.where) || WHERE[0];
  const goWords = h("span", {}, chosen().go);
  const holds = h("span", {}, chosen().holds);
  const go = button({ kind: "main", id: "team-start-go", onClick: () => {
    const w = chosen().value;
    if (w === "folder") folderDialog(ctx); else setupDialog(ctx, w);
  } }, goWords);
  const cards = optionCards({ label: "Where the team’s shared work is kept", id: "team-where", class: "team-where", value: chosen().value,
    options: WHERE.map(({ value, icon, title, tag, text }) => ({ value, icon, title, tag, text })),
    onPick: (v) => { typed.where = v; goWords.textContent = chosen().go; holds.textContent = chosen().holds; } });
  return section("space-setup", "Start a team for this project",
    // (the help mark stays on the line of the last words: alone on a line it reads as a stray icon)
    h("p", { class: "team-text" }, "This project is not shared with a team yet. Choose where the team’s shared work is kept; your colleagues join ",
      h("span", { class: "nowrap" }, "after that. ", helpMark("How working together works", HOW_HELP))),
    cards,
    h("div", { class: "btn-row" }, go),
    aiWhere(holds, "folder"));
}

// ---------------------------------------------------------------------------------------------
// join a colleague's team: an invite link, or the folder they share
// ---------------------------------------------------------------------------------------------
function joinSection(ctx) {
  if (!noTeam(ctx)) return null;
  return section("join", "Join a colleague’s team",
    h("p", { class: "team-text" }, "A colleague already started the team and sent you an invite link. It starts with ", h("span", { class: "mono" }, "margin://join#"), "."),
    h("div", { class: "btn-row" }, button({ kind: "main", icon: "link", id: "team-space-join", onClick: () => joinDialog(ctx) }, "Join with an invite link…")),
    h("p", { class: "muted team-text" }, "No invite link? If your colleague shared a folder with you instead (OneDrive, Dropbox, Google Drive or a network drive), choose it."),
    h("div", { class: "btn-row" }, button({ sm: true, icon: "folder", id: "team-join-folder", onClick: () => folderDialog(ctx, { joining: true }) }, "Choose the shared folder…")));
}

// ---------------------------------------------------------------------------------------------
// without a team: the project as a file
// ---------------------------------------------------------------------------------------------
function fileSection(ctx) {
  if (!noTeam(ctx)) return null;
  const project = ctx.project;
  return section("downloads", "Send it once, as a file",
    h("p", { class: "muted team-text" }, "No team needed: by e-mail or a USB stick. Nothing keeps the copies in step afterwards; a colleague brings your file in with Import a project, under ",
      link({ href: "#/projects" }, "Projects"), "."),
    h("ul", { class: "team-downloads" },
      h("li", {}, zipButton(project, "shared", { id: "team-zip-shared" }), h("span", { class: "muted small" }, ZIP_WORDS.shared.what)),
      h("li", {}, zipButton(project, "all", { id: "team-zip-all" }), h("span", { class: "muted small" }, ZIP_WORDS.all.what))));
}

// The Team page's sections while the project has no team, in order (team.js draws them, each a card)
export const TEAM_SETUP_SECTIONS = [
  { key: "found", render: foundSection },
  { key: "space-setup", render: startSection },
  { key: "join", render: joinSection },
  { key: "downloads", render: fileSection },
];

// ---------------------------------------------------------------------------------------------
// a shared folder, chosen in a dialog: a cloud folder by name, the system's folder window, or its pasted path
// ---------------------------------------------------------------------------------------------
const FOLDER_HELP = "Each of you keeps your own copy of this project. Margin puts what you share in the folder and brings in what your colleagues share. Nothing of yours goes to the team until you press Share on it: a check, a set of themes, a codebook, a note, an entry of your own or a link between terms.";
const FOUND_WORDS = "Your colleague’s shared folder is here:";

// `joining`: a colleague already works through the folder (the Join card, the notice of a folder found): the dialog
// says so and offers what helps to find their folder; the one who starts is not asked about a colleague's folder.
export async function folderDialog(ctx, { path: start = "", joining = false } = {}) {
  const st = ctx.status, me = st.me || {};
  const project = ctx.project;
  const example = win() ? "C:\\Users\\Anna\\OneDrive\\Our project" : "/Users/anna/Dropbox/Our project";
  const path = input({ mono: true, id: "team-folder-path", autocomplete: "off", spellcheck: "false", placeholder: example, value: start });
  const copyTip = mac() ? "In the Finder, select the folder and press ⌥⌘C to copy its path." : win() ? "In File Explorer, hold Shift, right-click the folder and choose Copy as path." : "";
  const pathField = field("The shared folder", path, { help: `Its whole path on this computer. ${copyTip}`.trim() });
  const err = h("p", { class: "field-error team-error", role: "alert", id: "team-folder-error" });
  path.setAttribute("aria-describedby", `${path.getAttribute("aria-describedby") || ""} team-folder-error`.trim());
  const showErr = (text) => {
    err.textContent = text;
    path.setAttribute("aria-invalid", text ? "true" : "false");
    if (text) path.focus();
  };
  const fillPath = (p) => { path.value = p; showErr(""); path.focus(); };
  // the switch: untouched, the project's own stays as it is (it stays on after Stop using this folder, and a project
  // moved to this computer brings it)
  let keepOut = null;
  const sw = switchControl(KEEP_OUT_LABEL, !!(st.keep_out || {}).mine, {});
  sw.input.id = "team-setup-keep-out";
  const swLabel = sw.querySelector("label");
  if (swLabel) swLabel.htmlFor = "team-setup-keep-out";
  sw.input.addEventListener("change", () => { keepOut = sw.input.checked; });
  const name = input({ id: "team-your-name", maxlength: 60, autocomplete: "name", placeholder: "e.g. Anna de Vries" });
  const nameField = me.name ? null : field("Your name", name, { help: "Colleagues see your work under this name." });
  // the cloud folders by name, the system's folder window, and a colleague's folder already found
  const offers = h("div", { class: "team-offers", id: "team-offers" });
  const o = offersOf(ctx);
  const drawOffers = () => replace(offers, offerBlock(o, fillPath, showErr, () => path.value, joining));
  drawOffers();
  if (!o.loaded) o.ready.then(() => { if (offers.isConnected) drawOffers(); });
  path.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); document.getElementById("team-use-folder")?.click(); } });

  await dialog({
    title: joining ? "Join through a folder your colleague shared" : "Start with a folder you share", wide: true,
    body: h("div", { class: "team-folder-setup" },
      h("p", { class: "muted" }, joining ? "The folder your colleague chose for this project, as it is on this " : "A folder that OneDrive, Dropbox, Google Drive or a network drive keeps the same on every colleague’s ",
        h("span", { class: "nowrap" }, "computer. ", helpMark("About working through a shared folder", FOLDER_HELP))),
      nameField, offers, pathField, err,
      h("div", { class: "team-switch" }, sw, helpMark("About documents that stay here", KEEP_OUT_HELP)),
      // where text goes, at the foot (docs/DESIGN.md 4.4 and 5.5: the AI line's folder)
      aiWhere([h("strong", {}, "The folder will hold the documents’ text and files, and only what you share of your own work. "),
        "Your project’s database stays on this computer."], "folder")),
    actions: [{ text: "Cancel", value: null }, {
      text: "Use this folder", primary: true, id: "team-use-folder",
      async onClick(dlg) {
        showErr("");
        const p = cleanPath(path.value);
        if (!p) { showErr("Type or paste the path of the folder your team shares, or choose it above."); return false; }
        const b = dlg.querySelector("#team-use-folder");
        b.disabled = true;
        let named = false;
        try {
          if (!me.name && name.value.trim()) { await api("PUT", "/api/settings", { your_name: name.value.trim() }); named = true; }
          await api("PUT", `/api/projects/${P(project)}/shared-folder`, keepOut === null ? { path: p } : { path: p, keep_out: keepOut });
        } catch (e) {
          b.disabled = false;
          if (e.status === 400) showErr(e.message); else showError(e);
          return false;
        } finally {
          if (named) App.refresh().catch(() => {});   // the name, for the other pages (after the folder: no read beside it)
        }
        toast("This project now works through the shared folder. The first round starts now.", "ok");
        await firstRound(ctx);
        return true;
      } }],
    onOpen() { (start ? document.getElementById("team-use-folder") : nameField ? name : path).focus(); },
  });
}

// Above the path field. A colleague's shared folder, when it is already among this computer's cloud folders ("Use it");
// the cloud folders by name (one press fills the path); the system's folder window; and, when the team's folder is
// nowhere yet, what to do at each service. The pasted path stays as the fallback.
function offerBlock(o, fillPath, showErr, typedPath, joining) {
  const rows = [];
  for (const dir of joining ? o.found : []) {
    const seen = folderAsSeen(dir, o.folders);
    rows.push(h("p", { class: "team-text team-found" }, `${FOUND_WORDS} `, h("strong", { title: dir }, seen.text), " · ",
      link({ kind: "jump", "data-found": dir, onclick: () => fillPath(dir) }, "Use it")));
  }
  if (o.folders.length) {
    rows.push(h("div", { class: "team-cloud" }, listGroup("Cloud folders on this computer", ...o.folders.map((c) =>
      listRow({ title: c.name, sub: c.path, actions: [button({ sm: true, "aria-label": `Use ${c.name}`, onclick: () => fillPath(c.path) }, "Use")] })))));
  }
  if (o.picker) {
    const pick = button({ sm: true, icon: "folder", id: "team-choose-folder" }, "Choose folder…");
    pick.addEventListener("click", async () => {
      showErr("");
      setBusy(pick, true);
      try {
        const r = await api("POST", "/api/choose-folder", { prompt: "Choose the folder your team shares", start: cleanPath(typedPath()) || undefined });
        if (r.path) fillPath(r.path);
      } catch (e) {
        if (e.status === 409) showErr(e.message); else showError(e);
      } finally { setBusy(pick, false); }
    });
    rows.push(h("div", { class: "btn-row team-pick" }, pick));
  }
  if (joining && o.loaded && !o.found.length) {   // how a colleague's folder comes to this computer, folded beside the field
    rows.push(fold({ sm: true, class: "team-where-fold", id: "team-where-fold" }, "Your colleague’s folder is not here yet?",
      h("p", { class: "muted small" }, "Ask the colleague who set it up to share the folder with you, then make it available on this computer. ",
        h("strong", {}, "OneDrive: "), "on OneDrive’s website, choose ", h("em", {}, "Add shortcut to My files"), " on the shared folder, and ",
        h("em", {}, "Always keep on this device"), " so its files are not fetched only when opened. ",
        h("strong", {}, "Google Drive and Dropbox: "), "accept the share and keep the folder available offline. ",
        "It then appears here.")));
  }
  return h("div", {}, ...rows);
}
