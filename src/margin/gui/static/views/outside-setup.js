// Providers stage 2 (B1): one way to set up anything outside Margin. A dialog of guided steps (docs/DESIGN.md 4.28),
// lifted from the storage space's set-up (team-space.js setupDialog), so a provider's API key, the Claude API key and
// an agent on the person's own plan (Claude Code, Codex, Antigravity) are set up the way a storage space is: one thing
// to do at a time; the address to open as a line to copy into a browser of the person's choosing (a link would open
// the default browser, where some sign-up pages loop); what cannot be undone later in an attention notice; the step
// remembered for the window (never what was typed); the dialog's main button waiting for the last step that asks for
// something; "Stop the set-up?" once begun; and a last step, once it is done, that says what is left.
// Used by provider-setup.js (the keys) and agent-setup.js (the agents).
import { h, toast, field, input, button, dialog, confirmDialog, copyLine, guidedSteps, session } from "../lib.js";
import * as access from "./ai-access.js";

// The line that says how many of the project's documents the main route's provider may read, with a button to allow
// it for the project (ai-access.js providerAllowLine; null when every document allows it, or in a copy of Margin
// without it). Shown where a set-up ends and in Settings beside an agent or a provider.
export function allowLine(project) {
  const f = access.providerAllowLine;
  if (!project || typeof f !== "function") return null;
  try { return f(project, null, () => {}) || null; } catch (_) { return null; }
}

// "a" or "an" before a word ("an OpenAI key", "a Mistral key")
export const article = (word) => (/^[aeiou]/i.test(String(word || "")) ? "an" : "a");

// A web address to type or paste in a browser, with a Copy button (the storage space's typeAddress).
export function typeAddress(href, id) {
  const row = copyLine(String(href || "").replace(/^https?:\/\//, ""), "Copy", "your browser's address bar", "link");
  if (id) row.id = id;
  return row;
}

// A step whose first thing to do is to open an address: "Open this address in your browser:", the address to copy,
// then the step's other lines (`more`). { title, href, id, next, lead, more }.
export function addressStep({ title, href, id, next, lead = "Open this address in your browser:", more = [], back }) {
  return { title, next, back, body: [h("p", {}, lead), typeAddress(href, id), ...[].concat(more).filter(Boolean)] };
}

// A field to paste a secret or a name into: mono, not filled in by the browser, a password field unless `plain`.
// Returns the field; its input is `.input`.
export function pasteField(label, { id, help, placeholder, plain = false } = {}) {
  const inp = input({ mono: true, id, type: plain ? "text" : "password", autocomplete: "off", spellcheck: "false", placeholder: placeholder || null });
  const f = field(label, inp, help ? { help } : {});
  f.input = inp;
  return f;
}

// The dialog. Options:
//   title, label (the steps' name for a screen reader), id (the steps' id), intro (a line above the steps)
//   steps: [{ title, body, next, back }]: the last one asks for what the main button needs (a key pasted; a button
//     pressed); the main button waits until it is open
//   read(): what was typed, as an object; missing(body): what is still to enter ("" when nothing), missingAt(body):
//     at which step (default the last)
//   mainText: the main button's words ("Store the key"); submit(body, ui): does the task; returns a result (anything
//     but false) when done, false to stay (ui.error said why), or throws (its message is shown)
//   after: a step shown once done (no buttons), or (result) => step | null: what is left, what was applied. The step
//     may carry `main: { text, run(result) }` (the main button's words and what it does when pressed: "Allow cloud
//     models and use OpenAI") and `quiet` (the words of a quiet button that just closes: "Not now"); without them the
//     main button says Done
//   start: the step to open at; rememberKey: the window remembers the step under this key (a set-up taken up again
//     later opens where it was); start wins over it
//   ask: false: no "Stop the set-up?" (nothing typed can be lost); stopMessage: its words
//   doneWords: a toast once done (after the after step's Done, or at once without one), or (result) => words
//   onStep(i, ui): after every move (a step that waits for something outside starts watching for it here)
//   onClose(): once the dialog has gone, however it went
//   foot: lines under the steps (a note that stays)
// ui: { go(i), at(), error(text), progress(text), lock, done(result) } (done ends the task from a step's own button,
// as the main button would). Resolves with the result, or null when closed before the end.
export async function outsideSetup(opts) {
  const { title, label, id, intro, steps, read = () => ({}), missing = () => "", missingAt, mainText = "Done", submit,
    after, start, rememberKey, ask = true, stopMessage, doneWords, onStep, onClose, foot, wide = true } = opts;
  const err = h("p", { class: "field-error", role: "alert" });
  const progress = h("p", { class: "muted small", role: "status", "aria-live": "polite" });
  const lock = { on: false };
  const list = steps.filter(Boolean);
  const last = list.length - 1;              // the last step that asks for something
  let ready = false;                         // done: the after step says what is left
  let afterStep = null;
  let result = null;
  const afterHolder = h("div", { class: "outside-after" });
  const afterTitle = h("span", {}, "What Margin applied");
  const all = after ? [...list, { title: afterTitle, next: false, back: false, body: [afterHolder] }] : list;
  const remembered = rememberKey ? Number(session(rememberKey)) || 0 : 0;
  const first = Math.min(Math.max(0, start ?? remembered), last);
  const confirmBtn = () => document.querySelector("#dialogs dialog[open] #dlg-confirm");
  const cancelBtn = () => document.querySelector("#dialogs dialog[open] #dlg-cancel");
  const WAITS = "Waits for the last step: go through the steps above first.";
  const hold = (b, on) => { b.disabled = on; if (on) b.title = WAITS; else b.removeAttribute("title"); };
  const ui = {
    go: (i) => way.go(i), at: () => way.at(), lock,
    error: (t) => { err.textContent = t || ""; },
    progress: (t) => { progress.textContent = t || ""; },
    done: (r) => finish(r),
  };
  const way = guidedSteps({ label: label || title, id, steps: all, current: first,
    onStep: (i) => {
      const b = confirmBtn(); if (b && !ready) hold(b, i < last);
      if (rememberKey && !ready) session(rememberKey, i > 0 && i <= last ? i : null);
      if (onStep && i <= last && !ready) onStep(i, ui);
    } });
  // the task is done: the after step (if any) says what is left, the main button says Done. Returns whether the
  // dialog stays open (it has an after step to show).
  let closeNow = () => {};
  function finish(r, fromMain = false) {
    result = r === undefined ? true : r;
    if (rememberKey) session(rememberKey, null);
    progress.textContent = ""; err.textContent = "";
    const step = typeof after === "function" ? after(result) : after;
    if (!step) { if (!fromMain) closeNow(); return false; }
    ready = true;
    afterStep = step;
    afterHolder.replaceChildren(...[].concat(step.body || []).filter(Boolean));
    if (step.title) afterTitle.textContent = step.title;
    way.go(all.length - 1);
    const b = confirmBtn(); if (b) { b.textContent = (step.main && step.main.text) || "Done"; hold(b, false); }
    const c = cancelBtn(); if (c) { c.hidden = !step.quiet; if (step.quiet) c.textContent = step.quiet; }
    return true;
  }
  const begun = () => !ready && ask && (way.at() > 0 || Object.values(read()).some(Boolean));
  const shown = dialog({
    title, wide, lock,
    body: h("div", { class: "outside-setup team-space-setup" }, intro || null, way, err, progress, ...[].concat(foot || []).filter(Boolean)),
    onDismiss: async () => !begun() || (await confirmDialog({ title: "Stop the set-up?", confirmText: "Stop the set-up", danger: false,
      message: stopMessage || "Nothing has been set up yet. What you pasted here is not kept; the step you were at is, until you close Margin." })) === true,
    actions: [{ text: "Cancel", value: null, id: "dlg-cancel" }, {
      text: mainText, primary: true, id: "dlg-confirm",
      async onClick(dlg) {
        if (ready) {   // the button says Done now, or what it still does (afterStep.main)
          const run = afterStep && afterStep.main && afterStep.main.run;
          if (!run) return true;
          const again = dlg.querySelector("#dlg-confirm");
          again.disabled = true;
          try { await run(result); return true; }
          catch (e) { err.textContent = e.message || String(e); again.disabled = false; return false; }
        }
        err.textContent = "";
        const body = read();
        const lacks = missing(body);
        if (lacks) { err.textContent = lacks; way.go(missingAt ? missingAt(body) : last); return false; }
        const btn = dlg.querySelector("#dlg-confirm");
        btn.disabled = true; lock.on = true;
        try {
          const r = await submit(body, ui);
          lock.on = false;
          if (r === false) return false;
          return !finish(r, true);
        } catch (e) { progress.textContent = ""; err.textContent = e.message || String(e); return false; }
        finally { lock.on = false; const again = dlg.querySelector("#dlg-confirm"); if (again && !ready) hold(again, way.at() < last); }
      } }],
    onOpen(dlg) {
      closeNow = () => { const c = dlg.querySelector("#dlg-cancel"); if (c) c.click(); };
      const b = dlg.querySelector("#dlg-confirm"); if (b) hold(b, way.at() < last);
      const f = dlg.querySelector(".guided-step[data-state='current'] input"); (f || dlg.querySelector(".guided-step[data-state='current'] .guided-step-title")).focus();
      if (onStep) onStep(way.at(), ui);
    },
  });
  const value = await shown;
  if (onClose) { try { onClose(); } catch (_) { /* gone anyway */ } }
  const words = result === null ? "" : typeof doneWords === "function" ? doneWords(result) : doneWords;
  if (words) toast(words, "ok", { ttl: 9000 });
  void value;
  return result;
}

// A small button inside a step that does something there (Install Codex, Open the sign-in): a standard button, so the
// step's own "I have…" button stays the quiet way on.
export const stepButton = (text, onClick, { id, icon, kind } = {}) => button({ sm: true, id, icon, kind, onClick }, text);
