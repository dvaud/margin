// 0.17.0: "Work waiting for Claude Code", a section of Settings › AI (#/settings/queue). What waits for Claude Code in
// this project, kind by kind: do first, hold or go on, remove; Start Claude Code with its speed and helpers; or answer
// it with the AI model of Settings. (Until 0.16.1 this was the queue panel at the foot of the sidebar; the sidebar now
// shows only the work's essentials, in its status area, and links here.)
import { App, api, h, icon, replace, toast, showError, confirmDialog, P, watchJob, button, card, tag, withAI, readsLine, aiWhere, notice, queueAiLine, TERMINAL,
  aiButton, aiSide, aiSides, aiSeat, placeSide, redrawSide, sideFigures, modelFigures, cancelJob, setBusy } from "../lib.js";
import { aiRun } from "./progress.js";

export function queueSection() {
  const body = h("div", { class: "queue-section", "aria-live": "polite" });
  const section = card({ class: "settings-section", id: "s-queue", "aria-labelledby": "s-queue-h" },
    h("h2", { id: "s-queue-h", tabindex: "-1" }, "Work waiting for Claude Code"),
    h("p", { class: "lead" }, "What the AI buttons of this project prepared for Claude Code, kind by kind. Claude Code answers it on your Claude plan; you choose what comes first, hold a kind, or take it out."),
    body);
  let timer = null;
  let defers = 0;
  // 0.19.13: the AI run panel of the queue, kept across draws so its buttons stay put: Claude's side (Start Claude Code)
  // and, when the local model has a share or may take over at the plan's limit, this computer's side with its own Start
  let block = null, cloud = null, local = null, localKey = "", localJob = null, localStatus = null, hereRun = null;
  // a job of this project whose local part waits for its own Start (a check's excerpts, themes to name…): its side
  // shows here as waiting, with that Start, not as an empty seat
  let gated = null;
  const seen = {};
  api("GET", "/api/local-status").then((r) => { localStatus = r && !r.same_as_main ? r : null; draw(); }).catch(() => {});
  const runLocal = async (which) => {
    const r = await api("POST", `/api/projects/${P(App.project)}/queue/run`, { local: which });
    localJob = r.job;
    const w = watchJob(r.job.id, (job) => { localJob = job; drawLocal(); });
    w.promise.then((job) => { localJob = null; if (job.state === "done") toast("Your local model has answered its share.", "ok", { small: true }); draw(); }).catch(showError);
    drawLocal();
  };
  function localOpts(q) {
    const st = localStatus || {};
    const base = { model: st.model || App.settings().restricted_model, memory: st.memory || null, problem: st.problem || null, noun: "task", compact: true };
    if (localJob && !TERMINAL.has(localJob.state)) {
      const m = (localJob.progress || {}).model || {};
      return { ...base, memory: null, running: { phase: m.phase || "waiting", seconds: m.seconds }, onStop: () => cancelJob(localJob.id) };
    }
    if (gated && !(q && (q.for_local || (q.at_limit && q.at_limit.offer_local)))) {
      const L = gated.local, m = (gated.progress || {}).model || {};
      const model = L.model || base.model;
      if (L.gate !== "wait") return { ...base, model, memory: null, noun: L.noun || "task", running: { phase: m.who === "local" && m.phase !== "ready" ? m.phase || "waiting" : "waiting", seconds: m.seconds }, count: L.waiting,
        onStop: async () => { await api("POST", `/api/jobs/${P(gated.id)}/local/stop`, {}); draw(); } };
      return { ...base, model, memory: L.memory || base.memory, problem: L.problem || base.problem, noun: L.noun || "task", count: L.waiting,
        sub: `For “${String(gated.title || "").replace(/[.?!]+$/, "")}”`,
        onStart: async (force) => { await api("POST", `/api/jobs/${P(gated.id)}/local/start`, { force: !!force }); draw(); } };
    }
    const limit = q && q.at_limit && q.at_limit.offer_local;
    return { ...base, count: limit ? q.waiting : q.for_local, head: limit ? `Claude Code stopped at your plan’s limit: ${base.model || "your local model"} can answer what waits` : null,
      onStart: () => runLocal(limit ? "limit" : "mix") };
  }
  function drawLocal(q = lastQ) {
    if (!block || !local) return;
    const o = localOpts(q);
    const key = JSON.stringify(o.running ? ["run", o.model] : o);
    if (key !== localKey) { localKey = key; redrawSide(local, o); }
    const m = localJob && (localJob.progress || {}).model;
    sideFigures(local, m && m.phase ? modelFigures(m, seen) : null);
  }
  let lastQ = null;
  async function draw() {
    clearTimeout(timer);
    if (!section.isConnected && body.dataset.drawn) return;   // the page moved on
    // not while a list of "Choose the helpers for this run" is open (redrawing would close it), for half a minute at most
    const el = document.activeElement;
    if (body.contains(el) && el.matches(".sc-helpers select") && defers < 6) { defers += 1; timer = setTimeout(draw, 5000); return; }
    defers = 0;
    body.dataset.drawn = "1";
    if (!App.project) { replace(body, h("p", { class: "muted small" }, "Open a project first.")); return; }
    let q;
    try { q = await api("GET", `/api/projects/${P(App.project)}/queue`); } catch (e) { replace(body, h("p", { class: "muted small" }, e.message)); return; }
    try {
      gated = ((await api("GET", "/api/jobs")).jobs || []).find((j) => j.project === App.project && !TERMINAL.has(j.state) && j.local && (j.local.waiting || 0) > 0 && !j.local.problem) || null;
    } catch (_) { gated = null; }
    const s = App.settings();
    const act = async (kind, action) => {
      try { await api("POST", `/api/projects/${P(App.project)}/queue/order`, { kind, action }); draw(); } catch (e) { showError(e); }
    };
    const remove = async (k) => {
      const ok = await confirmDialog({ title: `Take the ${k.title.toLowerCase()} out of the queue?`, message: `The ${k.waiting.toLocaleString()} tasks no session has taken yet are removed${["check", "expand", "decompose"].includes(k.kind) ? ", and the checks still waiting are removed whole (as a stopped check)" : ""}. Answers already stored stay.`, confirmText: "Remove" });
      if (!ok) return;
      try { const r = await api("POST", `/api/projects/${P(App.project)}/queue/withdraw`, { kind: k.kind }); toast(`${r.withdrawn} tasks taken out of the queue.`, "ok"); App.refresh().catch(() => {}); draw(); } catch (e) { showError(e); }
    };
    const kinds = (q.kinds || []).filter((k) => k.waiting || k.being_answered || k.for_local);
    const head = q.runner && q.runner.running ? `Claude Code is working: ${(q.waiting + q.being_answered).toLocaleString()} to go`
      : q.waiting ? (q.paused ? `Paused: ${q.waiting.toLocaleString()} waiting` : `${(q.waiting + q.being_answered).toLocaleString()} waiting for Claude Code`)
      : q.being_answered ? `Claude Code is answering ${q.being_answered}` : "Nothing waits.";
    const parts = [h("p", { class: "qp-head" }, icon(q.paused ? "pause" : "inbox", { size: 14 }), " ", h("strong", {}, head))];
    if (q.paused && q.paused_text) parts.push(h("p", { class: "small qp-paused" }, q.paused_text));
    // 0.18.1 (I4): Claude Code stopped at the plan's usage limit, and what happens now (Settings › AI)
    if (q.at_limit) parts.push(notice({ kind: "attention", class: "qp-limit" }, h("p", {}, q.at_limit.said, " ",
      q.at_limit.started ? "Your local model answers what waits, where it may." : q.at_limit.offer_local ? "Your local model can answer what waits: start it below, on this computer’s side."
        : q.at_limit.choice === "local" && !q.at_limit.local_possible
        ? "No local model is chosen, so the work waits for the next start." : "The work waits; start Claude Code again when the limit resets.",
      " ", h("a", { href: "#/settings/model" }, "Change what happens"))));
    if (!kinds.length) parts.push(h("p", { class: "muted small" }, "Press an AI button (a check, Label passages, Name the themes…): its work waits here for Claude Code."));
    for (const k of kinds) {
      parts.push(h("div", { class: "qp-row" + (k.held ? " qp-held" : "") },
        h("div", { class: "qp-title" }, h("strong", {}, k.title), k.held ? tag({}, "held") : null),
        h("div", { class: "muted small" }, `${k.waiting.toLocaleString()} waiting${k.being_answered ? ` · ${k.being_answered} being answered` : ""}${k.done ? ` · ${k.done.toLocaleString()} done` : ""}${k.stronger_model ? ` · ${k.stronger_model} for a stronger model` : ""}${k.for_local ? ` · ${k.for_local.toLocaleString()} for your local model` : ""}`),
        h("div", { class: "muted small" }, [k.helper ? `${k.helper} on ${k.model}` : k.model ? `on ${k.model}` : "", k.estimate ? ` · ${k.estimate}` : ""].join("")),
        h("div", { class: "qp-actions" },
          (q.order || [])[0] !== k.kind ? button({ kind: "quiet", sm: true, onClick: () => act(k.kind, "first") }, icon("arrow-up", { size: 12 }), "Do first") : null,
          button({ kind: "quiet", sm: true, onClick: () => act(k.kind, k.held ? "go" : "hold") }, icon(k.held ? "play" : "pause", { size: 12 }), k.held ? "Go on" : "Hold"),
          button({ kind: "danger", sm: true, onClick: () => remove(k) }, icon("trash", { size: 12 }), "Remove"))));
    }
    // the AI run panel: Claude's side (Start Claude Code, its choices) and, for the AI mix's share (0.18.1, I1) or at the
    // plan's limit, this computer's side with its own Start: two starts, nothing starts by itself
    lastQ = q;
    const wantCloud = kinds.length || s.backend === "claude_code";
    const wantLocal = !!gated || (s.backend === "claude_code" && (q.for_local || (q.at_limit && q.at_limit.offer_local) || (localJob && !TERMINAL.has(localJob.state))));
    if (wantCloud || wantLocal) {
      if (!block) block = aiSides(null, null, { compact: true });
      if (wantCloud && !cloud) { cloud = aiSide({ where: "cloud", live: true, project: App.project, command: q.command, always: true, privacy: false, compact: true }); placeSide(block, "cloud", cloud); }
      if (wantLocal && !local) { localKey = ""; local = aiSide({ where: "local", ...localOpts(q) }); placeSide(block, "local", local); }
      else if (!wantLocal && local) { placeSide(block, "local", aiSeat("local")); local = null; }
      drawLocal(q);
      parts.push(h("div", { class: "qp-start" }, block));
    }
    // where the tasks' text goes (docs/DESIGN.md 4.4): under the card's AI actions. With Claude Code, under its panel;
    // with another AI, under "Answer them here instead"
    if (s.backend === "claude_code") parts.push(queueAiLine(q.privacy, kinds.length ? App.project : null));
    // the local model's own line (readsLine() names the AI of Settings, which is Claude here)
    if (wantLocal) parts.push(aiWhere(`Your local model (${(localStatus || {}).model || App.settings().restricted_model || "chosen in Settings › AI"}) reads its part on this computer: it never leaves it.`, "local"));
    if (kinds.length && s.backend !== "claude_code") {
      const go = aiButton({ sm: true, disabled: !!(hereRun && hereRun.job && !TERMINAL.has(hereRun.job.state)), onClick: async () => {
        setBusy(go, true);
        try {
          const r = await api("POST", `/api/projects/${P(App.project)}/queue/run`, {});
          hereRun = aiRun({ size: "compact", title: `${App.state.backend_label} answers the queue` });
          const w = watchJob(r.job.id, (job) => { hereRun.job = job; hereRun.update(job); });
          w.promise.then(() => draw()).catch(showError);
          draw();
        } catch (e) { showError(e); setBusy(go, false); }
      } }, "Answer them here instead");
      parts.push(h("div", { class: "qp-here" }, ...withAI(go), h("span", { class: "muted small" }, ` with ${App.state.backend_label}`)),
        hereRun ? hereRun.el : null, readsLine("the tasks waiting"));
    }
    replace(body, ...parts);
    if (local && localJob) drawLocal(q);
    if (q.waiting || q.being_answered || (q.runner && q.runner.running) || gated) timer = setTimeout(draw, 5000);
  }
  draw();
  return section;
}
