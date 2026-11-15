// Projects: create, link an existing workspace folder, switch, remove.
import { quickLookButton } from "./quicklook.js";
import { App, api, h, icon, replace, toast, showError, field, navigate, dialog, confirmDialog, pageHead, P, fmt, download, button, downloadButton, card, input, tag, emptyState,
  switchControl, fold, setBusy } from "../lib.js";
import { projectZipLink } from "./result.js";

// Import a project from a zip made with "Download as a zip" (on this or another computer). 0.10: the same dialog takes
// the zip of "Move Margin to another computer" (every project and the settings); its projects keep their names.
const MOVE_NAME = /^Margin - all projects and settings - .*\.zip$/i;
export function importProjectDialog(opts = {}) {
  const file = input({ type: "file", accept: ".zip,application/zip", id: "import-zip" });
  const name = input({ placeholder: "the name the project had", autocomplete: "off", maxlength: 60 });
  const nameField = field("Project name", name, { help: "Proposed from the file name. If a project of that name exists already, you are asked for another." });
  nameField.hidden = !!opts.move;  // a zip of everything keeps the names its projects had
  const err = h("div", { class: "field-error", role: "alert" });
  const status = h("div", { class: "muted small", "aria-live": "polite" });
  const moveNote = h("p", { class: "small", hidden: true }, "This file holds everything from another computer: each project comes in under its own name (with “(2)” when a project of that name is here already)", opts.move ? ", and the settings come with it when this computer has no project yet." : ".");
  let proposed = "";
  file.addEventListener("change", () => {
    const f = file.files && file.files[0];
    err.textContent = "";
    if (!f) return;
    const everything = MOVE_NAME.test(f.name);
    nameField.hidden = everything;
    moveNote.hidden = !everything;
    // "Margin project - Demo - 2026-10-28.zip" -> "Demo"
    const m = /^Margin project - (.+?) - \d{4}-\d{2}-\d{2}\.zip$/i.exec(f.name);
    proposed = (m ? m[1] : f.name.replace(/\.zip$/i, "")).trim();
    if (!everything && (!name.value.trim() || name.value === proposed)) name.value = proposed;
    status.textContent = `${f.name} · ${fmt.bytes(f.size)}`;
  });
  return dialog({
    title: opts.move ? "Bring Margin from another computer" : "Import a project (.zip)",
    body: h("div", {},
      opts.move ? h("p", { class: "muted" }, "On the other computer, open Projects and choose “Download everything (.zip)” under Move Margin to another computer. Bring that file here (a USB stick, a shared folder, an e-mail to yourself), then choose it below.")
        : h("p", { class: "muted" }, "A zip made with “Download as a zip”, from this or another computer: the documents, the results and the notes in it come with it, as a new project. A project folder zipped by hand works too, and so does a zip of everything (from “Move Margin to another computer”)."),
      field("Zip file", file), status, moveNote, nameField, err),
    actions: [{ text: "Cancel", value: null }, {
      text: "Import", value: true, primary: true, id: "dlg-confirm",
      async onClick(dlg) {
        err.textContent = "";
        const f = file.files && file.files[0];
        if (!f) { err.textContent = "Choose a zip file first."; file.focus(); return false; }
        const typed = nameField.hidden ? "" : name.value.trim();
        const btn = dlg.querySelector("#dlg-confirm");
        btn.disabled = true; status.textContent = `Importing ${f.name}… this can take a moment for a large project.`;
        try {
          const r = await api("POST", `/api/projects/import${typed ? `?name=${encodeURIComponent(typed)}` : ""}`, f);
          // a move zip is not brought in yet: the app asks first about the settings
          if (r.move && r.token) { setTimeout(() => moveDialog(r.move, r.token)); return true; }
          await App.refresh();
          if (r.moved) {
            const n = r.moved.projects.length;
            const renamed = r.moved.projects.filter((p) => p.name !== p.from);
            toast(`${n} ${n === 1 ? "project" : "projects"} brought in${r.moved.settings ? ", with the settings" : ""}.${renamed.length ? ` Renamed because the name was taken: ${renamed.map((p) => `${p.from} → ${p.name}`).join(", ")}.` : ""}`, "ok", { ttl: 9000 });
            navigate(n ? "#/projects" : "#/overview");
          } else {
            toast(`Project “${r.project.name}” imported: ${r.project.documents} ${r.project.documents === 1 ? "document" : "documents"}, ${r.project.hypotheses} ${r.project.hypotheses === 1 ? "result" : "results"}. It is now the current project.`, "ok", { ttl: 7000 });
            navigate("#/hypotheses");
          }
        } catch (e) {
          btn.disabled = false; status.textContent = "";
          err.textContent = e.status === 409 ? `${e.message} Type another name and try again.` : e.message;
          if (e.status === 409) { name.focus(); name.select(); }
          return false;
        }
        return true;
      },
    }],
    onOpen(dlg) {
      const btn = dlg.querySelector("#dlg-confirm");
      name.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); btn.click(); } });
      file.focus();
    },
  });
}

// 0.10: every project and the settings in one zip, for another computer.
// Margin 0.1: the projects of ENLENS (the app Margin grew out of) on this computer, copied here in one go.
export function enlensCard(onDone) {
  const info = App.state && App.state.enlens;
  if (!info || !(info.projects || []).length) return null;
  const n = info.projects.length;
  const btn = button({ kind: "main", sm: true, icon: "download" }, `Bring ${n === 1 ? "it" : `all ${n}`} over`);
  btn.addEventListener("click", async () => {
    setBusy(btn, true);
    try {
      const r = await api("POST", "/api/import-enlens", {});
      await App.refresh();
      const k = r.copied.length + r.linked.length;
      toast(`${k === 1 ? "One project" : `${k} projects`} from ENLENS ${k === 1 ? "is" : "are"} here now${r.settings ? ", with your settings" : ""}. ENLENS keeps its own.`, "ok", { ttl: 6000 });
      if (onDone) onDone(r);
    } catch (e) { showError(e); setBusy(btn, false); }
  });
  return card({ as: "div", class: "move-in", title: `Your ENLENS ${n === 1 ? "project" : "projects"} on this computer` },
    h("p", { class: "muted small" }, `${info.projects.slice(0, 6).join(", ")}${n > 6 ? ` and ${n - 6} more` : ""}. They are copied into Margin with their documents, results, judgements and codebooks${info.here ? "" : ", and your settings"}; ENLENS keeps its own and works as before. Quit ENLENS first if it is open.`),
    btn);
}

function moveCard() {
  const btn = downloadButton({ onClick: async () => {
    btn.disabled = true;
    toast("Packing every project… this can take a while for large projects.", "info", { small: true, ttl: 4000 });
    try { await download("/api/move.zip"); } catch (e) { showError(e); }
    btn.disabled = false;
  } }, "Download everything (.zip)");
  return card({ as: "div", class: "move-card" },
    h("h2", {}, icon("monitor", { size: 16 }), " Move Margin to another computer"),
    h("p", { class: "muted small" }, "One file with every project (documents, results, your judgements and notes) and your settings. A saved Claude API key is left out: it stays on this computer. Projects used in place from another folder come along as copies."),
    h("ol", { class: "small move-steps" },
      h("li", {}, "Here: ", btn),
      h("li", {}, "On the new computer: install Margin, then on its first screen (or under Projects → Import) choose the file.")));
}

export function newProjectDialog() {
  const nameInput = input({ placeholder: "e.g. Green hydrogen Morocco", autocomplete: "off", maxlength: 60 });
  const err = h("div", { class: "field-error", role: "alert" });
  return dialog({
    title: "New project",
    body: h("div", {}, h("p", { class: "muted" }, "A project is one set of documents and the hypotheses you check against them, for example one literature review."), field("Name", nameInput), err),
    actions: [{ text: "Cancel", value: null }, {
      text: "Create", value: true, primary: true, id: "dlg-confirm",
      async onClick() {
        err.textContent = "";
        try {
          const typed = nameInput.value.trim();
          const r = await api("POST", "/api/projects", { name: typed });
          await App.refresh();
          if (r.project.name !== typed) toast(`Saved as “${r.project.name}” (some characters can't be used in a project name). Now add your documents.`, "warn", { ttl: 9000 });
          else toast(`Project “${r.project.name}” created. Now add your documents.`, "ok");
          navigate("#/sources");
        } catch (e) { err.textContent = e.message; return false; }
        return true;
      },
    }],
    onOpen(dlg) {
      const btn = dlg.querySelector("#dlg-confirm");
      nameInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); btn.click(); } });
      nameInput.focus();
    },
  });
}

// A zip of every project and the settings (from "Move Margin to another computer") is not brought in at once: the
// app says what is in it, and the settings come only with the switch; an address of a server that is not on this
// computer only with its own tick. Moving is always a plain move: this computer takes the other one's place.
const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;
export function moveDialog(peek, token) {
  const n = (peek.projects || []).length;
  const m = Date.parse(peek.made || "");
  const when = Number.isFinite(m) ? ` on ${new Date(m).toLocaleDateString("en-GB", { day: "numeric", month: "long" })}` : "";
  const summary = `${plural(n, "project")}${when || peek.version ? `, made${when}${peek.version ? ` with Margin ${peek.version}` : ""}` : ""}.`;
  const err = h("div", { class: "field-error", role: "alert" });
  const settings = switchControl("Take the settings too", !!peek.fresh, { help: "Which AI reads and how checks are made." });
  const listed = Object.entries(peek.settings || {});
  const settingsList = listed.length ? fold({ sm: true }, "The settings it takes", h("ul", { class: "small move-settings" }, listed.map(([k, v]) => h("li", {}, `${k}: ${v}`)))) : null;
  const servers = (peek.servers || []).filter((sv) => !sv.here).map((sv) => {
    const box = h("input", { type: "checkbox", id: `move-server-${sv.key}`, value: sv.key });
    return h("label", { class: "move-server", for: box.id }, box, h("span", {}, "Send what Margin reads to ", h("span", { class: "mono" }, sv.url), " as the other computer did."));
  });
  return dialog({ title: "This file moves Margin from another computer", wide: true,
    body: h("div", { class: "move-dialog" }, h("p", {}, summary),
      peek.fresh ? null : h("p", { class: "move-why" }, "This computer already has projects, so it keeps its own settings."),
      settings, settingsList, ...servers, err),
    actions: [{ text: "Cancel", value: null }, { text: "Bring in", value: true, primary: true, id: "move-go",
      async onClick(dlg) {
        err.textContent = "";
        const b = dlg.querySelector("#move-go");
        b.disabled = true;
        try {
          const r = await api("POST", "/api/move", { token, mode: "moving",
            settings: settings.input.checked, servers: servers.map((l) => l.querySelector("input")).filter((x) => x.checked).map((x) => x.value) });
          await App.refresh();
          toast(movedText(r), "ok", { ttl: 9000 });
          navigate("#/projects");
        } catch (e) { b.disabled = false; err.textContent = e.message; return false; }
        return true;
      } }] });
}
// what the move did, for the toast
function movedText(r) {
  const moved = (r && r.moved) || r || {};
  const list = moved.projects || [];
  const renamed = list.filter((p) => p.from && p.name !== p.from);
  return `${plural(list.length, "project")} brought in${moved.settings ? ", with the settings" : ""}.${renamed.length ? ` Renamed because the name was taken: ${renamed.map((p) => `${p.from} → ${p.name}`).join(", ")}.` : ""}`;
}

export function linkProjectDialog() {
  const path = input({ mono: true, placeholder: "/path/to/workspace (contains enlens.sqlite)", autocomplete: "off" });
  const name = input({ placeholder: "defaults to the folder's name", maxlength: 60 });
  const err = h("div", { class: "field-error", role: "alert" });
  return dialog({
    title: "Open an existing Margin project folder",
    body: h("div", {}, h("p", { class: "muted" }, "For technical users. This is not for a folder of documents (add those under Documents), but for a project folder that Margin itself made earlier, on the command line or in another copy of the app. It is used in place, not copied."), field("Folder path", path), field("Project name (optional)", name), err),
    actions: [{ text: "Cancel", value: null }, {
      text: "Link", value: true, primary: true, id: "dlg-confirm",
      async onClick(dlg) {
        err.textContent = "";
        try {
          const body = { path: path.value.trim(), name: name.value.trim() || undefined };
          const r = await api("POST", "/api/projects/link", body);
          await App.refresh();
          toast(`Project “${r.project.name}” added.`, "ok");
          navigate("#/hypotheses");
        } catch (e) { err.textContent = e.message; return false; }
        return true;
      },
    }],
    onOpen(dlg) {
      const btn = dlg.querySelector("#dlg-confirm");
      for (const el of [path, name]) el.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); btn.click(); } });
      path.focus();
    },
  });
}

export async function renderProjects(view) {
  view.appendChild(pageHead("Projects", { sub: "Each project keeps its own documents, results and notes.", actions: [
    button({ kind: "main", onClick: () => newProjectDialog() }, icon("plus", { size: 14 }), "New project"),
    button({ onClick: () => importProjectDialog() }, icon("upload", { size: 14 }), "Import a project (.zip)"),
    button({ onClick: () => linkProjectDialog() }, icon("link", { size: 14 }), "Open an existing Margin project folder"),
    quickLookButton()] }));
  view.appendChild(h("p", { class: "muted small pj-zip-note" }, "“Download as a zip” gives a project as one file with the documents, the results, your judgements and notes: to keep it, or to move it to another computer. “Import a project” brings such a zip in as a new project."));
  const list = h("div", { class: "stack" });
  view.appendChild(list);
  const fromEnlens = enlensCard(() => window.dispatchEvent(new HashChangeEvent("hashchange")));
  if (fromEnlens) view.appendChild(fromEnlens);
  if ((App.state.projects || []).some((p) => !p.temporary)) view.appendChild(moveCard());
  const draw = () => {
    replace(list);
    const projects = App.state.projects || [];
    if (!projects.length) { list.appendChild(emptyState("folder", "No projects yet", "Create one to get started.")); return; }
    for (const p of projects) {
      const current = p.name === App.project;
      list.appendChild(card({ as: "div" },
        h("div", { class: "row pj-row" },
          h("div", { class: "grow" },
            h("div", { class: "it" }, icon(p.linked ? "link" : "folder", { size: 16 }), h("h2", {}, p.name), current ? tag({ kind: "code" }, "current") : null, !p.ok ? tag({ kind: "attention" }, "cannot be opened") : null),
            h("div", { class: "muted small pj-counts" }, `${p.documents} ${p.documents === 1 ? "document" : "documents"} · ${p.hypotheses} ${p.hypotheses === 1 ? "result" : "results"}${p.linked ? " · folder used in place" : ""}${p.temporary ? ` · a quick look, moved to the trash on ${fmt.dateShort(new Date(p.temporary.expires_at * 1000).toISOString())} unless kept` : ""}`),
            h("div", { class: "muted small mono pj-path" }, p.path)),
          h("div", { class: "btn-row" },
            !current ? button({ sm: true, onClick: async () => { try { await api("PUT", "/api/settings", { project: p.name }); await App.refresh(); toast(`Project: ${p.name}`, "ok", { ttl: 2000 }); draw(); } catch (e) { showError(e); } } }, "Switch to") : null,
            p.ok ? projectZipLink(p.name, { text: "Download as a zip" }) : null,
            button({ kind: "danger", sm: true, onClick: async () => {
              const ok = await confirmDialog({ title: `Remove project “${p.name}”?`, message: p.linked ? "The folder is no longer used by the app and is left untouched on disk." : "The project (documents, results, notes) is moved to a trash folder inside the app's data folder.", confirmText: "Remove", typeToConfirm: p.name });
              if (!ok) return;
              try { const r = await api("DELETE", `/api/projects/${P(p.name)}`, { confirm: p.name }); await App.refresh(); toast(r.result === "unlinked" ? "Project removed: its folder is left as it was." : "Project removed: it is in the trash folder inside the data folder.", "ok"); if (!App.state.projects.length) navigate("#/setup"); else draw(); } catch (e) { showError(e); }
            } }, icon("trash", { size: 13 }), "Remove")))));
    }
  };
  draw();
  return App.onChange(draw);
}
