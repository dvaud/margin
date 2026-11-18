// The AI run panel (docs/DESIGN.md 4.21): one panel for every place where AI runs, at three sizes. Full: a job's
// panel (a check, a batch, reading more, a theory), its head, its steps, and the two sides under the step they work on.
// Compact: the two sides alone in a card under what started them (reading one excerpt again, naming themes, a label
// run). The row: the sidebar's work box (app.js). Updated in place from the job every poll, so nothing under the
// pointer is replaced, a running spinner does not restart and the page does not flicker. The pieces (the sides, the
// split bar, the start row) are in lib.js.
import { App, api, h, icon, replace, clear, fmt, cancelJob, showError, memoryRefused, watchJob, TERMINAL, P, button, card, fold, link, notice, stopButton,
  setBusy, plural, inStep, aiSide, aiSides, placeSide, redrawSide, sideFigures, setHalf, sidePct, modelFigures, readsLine, aiWhere, aiLead, isAgent, agentTitle, cloudName } from "../lib.js";
import { providerAllowLine } from "./ai-access.js";

const STEP_ICON = { pending: "circle", running: "loader", done: "check", waiting: "clock" };
// 0.19.4: the backends of Settings that are a model on this computer
const LOCAL_MAIN = new Set(["ollama", "openai", "auto"]);
const plainPhase = (phase) => ({ waiting: "The AI is getting ready and reading", thinking: "The AI is thinking it over", writing: "The AI is writing down its judgement", done: "The AI has finished" }[phase] || "The AI is working");
// what Claude's side draws from the queue's words: not when they were said (a poll's own clock)
const queueKey = (q) => JSON.stringify(q ? Object.fromEntries(Object.entries(q).filter(([k]) => !["at", "seconds"].includes(k))) : null);
const MIXED_FOOT = "Two parts, two starts: each begins when you press its own Start, in either order, and they run side by side. Nothing is sent to Anthropic from the documents marked Only a local AI.";

// 0.19.6: the line under a short job while a model reads, in words: what it has written so far and how fast, and how
// long since its last token. `seen` keeps when the token count last changed, across polls. The panel shows the same
// figures as one muted line (modelFigures(), lib.js); this is that line as text.
export function modelDetail(m, seen) {
  const f = modelFigures(m, seen);
  if (!f) return null;
  const local = m.who === "local" || LOCAL_MAIN.has(App.settings().backend);
  return [local ? "On this computer" : null, ...f.bits, f.quiet ? f.quiet.replace(/\.$/, "").replace(/^N/, "n") : null].filter(Boolean).join(" · ");
}

// "about 3 min left": `spent` the seconds the `finished` items took (up to the moment the last one finished), `since`
// the seconds on the current one; null before the first is done, and once the estimate has run out
export function timeLeft(spent, finished, total, since = 0) {
  if (!finished || !spent || finished >= total) return null;
  const left = (spent / finished) * (total - finished) - since;
  if (left <= 0) return null;
  const mins = Math.ceil(left / 60);
  return left < 60 ? "less than a minute left" : mins < 90 ? `about ${mins} min left` : `about ${Math.floor(mins / 60)} h ${mins % 60} min left`;
}


// The panel. opts: size ("full" | "compact"), title (full: the panel's name; compact: what runs, "The AI names the
// themes"), steps (full: the step keys to show), batchWords ({ doing, done }), noun (what the local model reads:
// "passage", "excerpt", "theme"), engines (["local", "cloud"]: which seats have work; by default read from the job and
// kept once seen), onStop (after the job's Stop), stop (false: no Stop of its own, the card around it has one),
// label(job) (compact: the line's words, in place of the title's), onLocalStart (after this computer's Start).
/** 0.19.15: whether the person stopped this job: "cancelled", or ended (done, error) after Stop was pressed. */
export function isStopped(job) {
  return !!job && (job.state === "cancelled" || (!!job.stopped && job.state !== "queued" && job.state !== "running"));
}

export class AiRun {
  constructor(o = {}) {
    this.o = o;
    this.size = o.size || "full";
    this.onStop = o.onStop;
    this.title = o.title || "Working";
    this.steps = o.steps ? new Set(o.steps) : null;
    this.batchWords = o.batchWords || { doing: "checking hypothesis", done: "hypotheses checked" };
    this.engines = new Set(o.engines || []);
    this.fixed = !!o.engines;
    this.rows = new Map();     // key -> step row
    this.partEls = new Map();  // part number -> block
    this.sides = { local: null, cloud: null };
    this.sideKey = { local: "", cloud: "" };
    this.sideState = { local: null, cloud: null };
    this.seen = {};            // the running model's figures, across polls
    this.localTotal = 0;
    this.active = { local: false, cloud: false };   // each engine has been at work in this job
    this.jobId = null;
    this.job = null;
    this.headKind = "";
    this.lastLive = "";
    this.liveAt = 0;
    this.waiting = false;
    this.live = h("div", { class: "visually-hidden", "aria-live": "polite", "aria-atomic": "true" });
    this.lead = h("span", { class: "ar-lead" });
    this.msg = h(this.size === "full" ? "div" : "span", { class: "msg" }, this.size === "full" ? "Starting…" : `${this.title}…`);
    this.elapsed = h("span", { class: "elapsed" }, this.size === "full" ? "0 s" : "");
    this.stopBtn = o.stop === false ? null : stopButton({ onClick: () => this.stop() });
    this.block = aiSides(null, null);   // filled once the job says which engines it has
    this.block.hidden = true;
    if (this.size === "full") {
      this.head = h("div", { class: "progress-head" }, this.lead, this.msg, this.elapsed, this.stopBtn);
      this.batchBox = h("div", { class: "batch-box", hidden: true });
      this.decompBox = h("div", { class: "decomp-box", hidden: true });
      this.partsBox = h("div", { class: "parts-box" });
      this.li = h("li", { class: "step-sides", role: "presentation" });
      this.notesBox = h("ul", { class: "progress-notes small", hidden: true });
      this.expect = h("p", { class: "ar-foot" }, "");
      this.body = h("div", { class: "progress-body" }, this.batchBox, this.decompBox, this.partsBox, this.block, this.notesBox, this.expect);
      this.el = inStep(h("div", { class: "progress ar-full ab ar-running", "aria-label": o.title || "Progress" }, this.head, this.body, this.live));
    } else {
      this.head = h("p", { class: "ab-line" }, this.lead, this.msg, this.elapsed, this.stopBtn);
      this.el = inStep(h("div", { class: "ab ab-compact ab-run ar-running" }, this.head, this.block, this.live));
    }
    this.setHead("running");
  }

  async stop() {
    if (!this.jobId) return;
    setBusy(this.stopBtn, true);
    try { await cancelJob(this.jobId); } catch (e) { showError(e); setBusy(this.stopBtn, false); }
    if (this.onStop) this.onStop();
  }

  destroy() { this.el.remove(); }

  // the head: waiting for you (a clock, the slow breath), at work (the running dot, the flow), needs you (the amber
  // pause), done, stopped, did not work
  setHead(kind) {
    if (kind === this.headKind) return;
    this.headKind = kind;
    for (const k of ["waiting", "running", "attention", "done", "error", "stopped"]) this.el.classList.toggle(`ar-${k}`, k === kind);
    this.el.classList.toggle("progress-error", kind === "error");
    replace(this.lead, aiLead(kind));
  }

  headFromSides() {
    const job = this.job;
    if (!job) return;
    const running = job.state === "queued" || job.state === "running";
    const st = [this.sideState.local, this.sideState.cloud].filter(Boolean);
    let kind;
    if (!running) kind = job.state === "done" ? "done" : job.state === "error" ? "error" : "stopped";
    else if (job.state === "queued" || job.waiting_for) kind = "waiting";
    else if (st.includes("run")) kind = "running";
    else if (st.includes("need") || st.includes("paused")) kind = "attention";
    else if (st.includes("wait")) kind = "waiting";
    else kind = "running";
    this.setHead(kind);
    if (this.size === "full" && this.expect) {
      this.expect.textContent = running ? this.foot() : "";
      this.expect.hidden = !this.expect.textContent;
    }
    // the steps that wait for a Start show a clock, not the turning loader (nothing runs until it is pressed); once
    // the job has ended, a step it was on shows that it stopped there
    if (this.size === "full") {
      for (const li of this.rows.values()) {
        const on = li.dataset.state === "running";
        const look = !on ? "" : !running ? "stopped" : kind === "waiting" || kind === "attention" ? "waiting" : "";
        if ((li.dataset.look || "") === look) continue;
        li.dataset.look = look;
        li.classList.toggle("step-waiting", look === "waiting");
        replace(li.querySelector(".st-icon"), icon(look === "waiting" ? "clock" : look === "stopped" ? "minus" : STEP_ICON[li.dataset.state] || "circle", { size: 16 }));
      }
    }
  }

  // The foot: one sentence on what happens next, chosen by the sides' states (who waits for a Start, who works)
  foot() {
    const L = this.sideState.local, C = this.sideState.cloud;
    const has = (w) => this.engines.has(w);
    const waits = (k) => k === "wait" || k === "need" || k === "paused";
    if (has("local") && has("cloud") && waits(L) && waits(C)) return MIXED_FOOT;
    if (has("cloud") && waits(C) && isAgent()) {
      const t = agentTitle();   // stage 2: Claude Code, Codex or Antigravity
      return L === "run" ? `Your local model reads its part meanwhile. ${t} reads the rest once you press Start ${t} (or type the command in ${t}); the work waits in the queue meanwhile, and you can move around the app.`
        : `${t} reads it once you press Start ${t} (or type the command in ${t}). You can move around the app, or close it: the work waits in the queue, and its answer appears where you started it.`;
    }
    if (has("local") && waits(L)) {
      return C === "run" ? `${cloudName()} reads its part meanwhile. The work ends only once your local model has read its part too: press its Start, or stop the work.`
        : "The work goes on once your local model has read what waits for it: press its Start, or stop the work. You can move around the app meanwhile.";
    }
    if (L === "run") return "A model on this computer can take a few minutes. You can move around the app meanwhile; the work keeps running.";
    return "You can move around the app meanwhile; the work keeps running.";
  }

  // Draw the job (state + progress).
  update(job) {
    this.job = job;
    this.jobId = job.id;
    const p = job.progress || {};
    const running = job.state === "queued" || job.state === "running";
    this.el.classList.toggle("progress-done", job.state === "done");
    // 0.19.15: a job that was stopped keeps no panel (its head, its steps, its two sides and the bar all go); the page
    // says so once, in its own words or a quiet toast. A job stopped between two items ends "done" with what it had:
    // `stopped` says Stop was pressed
    this.el.hidden = isStopped(job);
    if (this.stopBtn) this.stopBtn.hidden = !running;
    const m = p.model;
    let message;
    if (this.size === "full") {
      message = this.o.label ? this.o.label(job) : job.waiting_for ? job.waiting_for.message   // 0.18 queued jobs
        : p.message || (job.state === "queued" ? "Waiting for the AI (another task is using it)" : "Starting");
      if (job.state === "done") message = "Done";
      else if (job.state === "error") message = "Stopped because something went wrong";
      else if (job.state === "cancelled") message = "Stopped";
    } else {
      message = this.o.label ? this.o.label(job) : `${this.title}…`;
      if (!this.o.label) {
        if (job.waiting_for) message = `${this.title}: ${job.waiting_for.message.replace(/^Q/, "q")}`;
        else if (job.state === "queued") message = `${this.title}: waiting for the AI (another task is using it)`;
        else if (running && p.message) message = `${this.title}: ${p.message}`;
        else if (running && m && m.phase && !["queue", "done", "ready", "refused"].includes(m.phase) && m.who !== "local") message = `${this.title}: ${(m.plain || plainPhase(m.phase)).replace(/^The AI/, "the AI").replace(/^Your /, "your ")}`;
      }
      if (job.state === "done") message = "Done.";
      else if (job.state === "error") message = "Stopped because something went wrong.";
      else if (job.state === "cancelled") message = "Stopped.";
    }
    if (this.msg.textContent !== message) this.msg.textContent = message;
    const secs = p.elapsed !== undefined ? p.elapsed : job.seconds;
    const t = running || this.size === "full" ? fmt.secs(secs || 0) : "";
    if (this.elapsed.textContent !== t) this.elapsed.textContent = t;

    if (this.size === "full") this.drawSteps(job, running);
    this.drawSides(job, running);
    if (this.size === "full") this.drawEnd(job);
    this.headFromSides();
    if (this.size === "full") this.placeBlock();

    // screen readers: the message at most every 4 s, and state changes at once
    const announce = `${message.replace(/[.…]$/, "")}${running ? "" : "."}`;
    const now = Date.now();
    if (announce !== this.lastLive && (!running || now - this.liveAt > 4000)) {
      this.live.textContent = announce + (running ? ` (${fmt.secs(secs || 0)})` : "");
      this.lastLive = announce;
      this.liveAt = now;
    }
  }

  drawSteps(job, running) {
    const p = job.progress || {};
    // a batch moved on to its next hypothesis: the steps start over
    if (p.batch && p.batch.index !== this.batchIndex) {
      this.batchIndex = p.batch.index;
      clear(this.partsBox); this.partEls.clear(); this.rows.clear();
    }
    if (p.batch && p.batch.total) {
      this.batchBox.hidden = false;
      const finished = !running;
      // 0.14.3: once the job has ended the count is the job's own (the same "N of M" as the summary under it), and the
      // steps of the last hypothesis are not shown any more
      const res = job.result || {};
      const total = finished && Number.isInteger(res.total) ? res.total : p.batch.total;
      const doneCount = finished ? (Array.isArray(res.checked) ? res.checked.length : p.batch.index) : p.batch.index - 1;
      const pct = Math.round((doneCount / total) * 100);
      this.partsBox.hidden = finished;
      replace(this.batchBox,
        h("div", { class: "row prg-batch-head" }, h("strong", {}, finished ? `${doneCount} of ${total} ${this.batchWords.done}` : `${doneCount} of ${total} done · ${this.batchWords.doing} ${p.batch.index}`), h("span", { class: "muted small" }, `${pct}%`)),
        h("div", { class: "progress-bar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": total, "aria-valuenow": doneCount }, h("span", { style: { width: `${Math.max(2, pct)}%` } })),
        finished ? null : h("p", { class: "batch-current" }, p.batch.text || ""));
    } else this.batchBox.hidden = true;

    if (p.decompose) {
      this.decompBox.hidden = false;
      const d = p.decompose;
      const row = this.row("decompose", d.label, d.state, d.detail, d.seconds);
      const list = h("ol", { class: "decomp-parts" }, (d.parts || []).map((x) => h("li", {}, x)));
      replace(this.decompBox, row, d.parts && d.parts.length ? list : null);
    } else this.decompBox.hidden = true;

    for (const part of p.parts || []) {
      let block = this.partEls.get(part.part);
      if (block && block.dataset.text !== (part.text || "")) {
        const t = block.querySelector(".part-title");
        if (t) replace(t, h("span", { class: "pn" }, part.part ? `Part ${part.part}` : "Hypothesis"), part.text || "");
        block.dataset.text = part.text || "";
      }
      if (!block) {
        block = h("div", { class: "part-block" });
        block.dataset.text = part.text || "";
        if ((p.parts || []).length > 1 || part.part > 0) {
          block.appendChild(h("p", { class: "part-title" }, h("span", { class: "pn" }, part.part ? `Part ${part.part}` : "Hypothesis"), part.text || ""));
        }
        block.appendChild(h("ul", { class: "step-list" }));
        this.partEls.set(part.part, block);
        this.partsBox.appendChild(block);
      }
      const ul = block.querySelector(".step-list");
      for (const s of part.steps || []) {
        if (this.steps && !this.steps.has(s.key)) continue;
        const key = `${part.part}:${s.key}`;
        let row = this.rows.get(key);
        if (!row) { row = this.row(key, s.label, s.state, s.detail, s.seconds); ul.appendChild(row); }
        else this.setRow(row, s.state, s.detail, s.seconds);
      }
    }
  }

  // notes on restricted documents, and why it did not work
  drawEnd(job) {
    const notes = (job.progress || {}).notes || [];
    this.notesBox.hidden = notes.length === 0;
    if (notes.length !== this.notesBox.childElementCount) replace(this.notesBox, ...notes.map((n) => h("li", {}, n)));
    if (job.state === "error") {
      let err = this.body.querySelector(".progress-err");
      if (!err) { err = notice({ kind: "error", class: "progress-err" }); this.body.appendChild(err); }
      replace(err.querySelector(".notice-body"), ...jobErrorParts(job, "The check could not finish."));
    }
  }

  // the two sides stand directly under the step they work on (the first that is not done); with no steps, under the head
  placeBlock() {
    const rows = this.partsBox.hidden ? [] : [...this.partsBox.querySelectorAll("li.step")];
    const active = rows.find((r) => r.dataset.state !== "done") || rows[rows.length - 1];
    if (active) {
      if (this.block.parentNode !== this.li) this.li.append(this.block);
      if (this.li.previousElementSibling !== active) active.after(this.li);
    } else if (this.block.parentNode !== this.body) {
      this.li.remove();
      this.notesBox.before(this.block);
    }
  }

  // Which engines the job has, and the state of each side. Read from what the server sends: Claude's when its work
  // waits in the queue (progress.queue, the model's phase "queue", job.queue) or the Claude API is Settings' AI; this
  // computer's when the local model reports (progress.model.who "local"), job.local_model, job.local (its gate), or
  // a refusal for memory. Once seen, an engine keeps its seat.
  drawSides(job, running) {
    const p = job.progress || {}, m = p.model || null, L = job.local || null;
    const s = App.settings();
    const mainLocal = LOCAL_MAIN.has(s.backend);
    // 0.19.6: the queue's report counts only while it is the later one (as the server's latest_report)
    // 0.19.14: "queue_end" is the end of the wait (taskqueue.end_report), not words of what waits
    const pq = p.queue && p.queue.phase !== "queue_end" && !(m && m.phase !== "queue" && (m.at || 0) > (p.queue.at || 0)) ? p.queue : null;
    const wq = running ? ((m && m.phase === "queue" && m.queue) || pq || null) : null;
    // stage 2: the agent may not read the project's documents yet (its company not allowed): the side says so
    const held = running && m && m.phase === "held" ? m : null;
    const localNow = running && !!(m && m.phase && !["queue", "done", "refused", "ready"].includes(m.phase) && (m.who === "local" || (mainLocal && m.who !== "cloud")));
    if (!this.fixed) {
      if (L || localNow || job.local_model || job.error_kind === "memory" || (m && (m.who === "local" || m.phase === "refused")) || (mainLocal && !job.queue && job.where !== "cloud") || (job.kind === "read-local")) this.engines.add("local");
      if (wq || held || job.where === "cloud" || (job.where !== "here" && (job.queue || (s.backend === "anthropic" && job.where == null && !job.local_model)))) this.engines.add("cloud");
    }
    this.block.hidden = !this.engines.size;
    if (!this.engines.size) return;
    if (localNow) this.active.local = true;
    if (wq || (s.backend === "anthropic" && running && !localNow && this.engines.has("cloud"))) this.active.cloud = true;
    const compact = this.size !== "full";
    const onState = (where) => (key) => { this.sideState[where] = key; if (this.job) this.headFromSides(); };

    // ---- this computer
    if (this.engines.has("local")) {
      const model = (L && L.model) || (m && m.who === "local" && (m.model || m.name)) || job.local_model
        || (mainLocal ? String(App.privacy().detail || "").split(" · ").pop() : s.restricted_model) || "";
      // what it reads: the server's word, unless it is only the generic "task" and the page knows better
      const noun = (L && L.noun && L.noun !== "task" ? L.noun : null) || this.o.noun || (L && L.noun) || (job.kind === "read-local" ? "excerpt" : "passage");
      // how many it has to read: the most that waited at once (the server counts what is left, the item in hand
      // too); none when the job never said
      if (L && L.waiting) this.localTotal = Math.max(this.localTotal, L.waiting);
      const counts = (waiting) => (this.localTotal ? { done: Math.max(0, this.localTotal - waiting), total: this.localTotal } : {});
      const cloudBusy = this.engines.has("cloud") && !["done", "stopped", "later"].includes(this.sideState.cloud || "");
      // Stop <model> (job.local's gate open): back to waiting after the item in hand; the job's own Stop ends it all
      const stopLocal = L && L.gate !== "wait" ? async () => { const r = await api("POST", `/api/jobs/${P(job.id)}/local/stop`, {}); if (r && r.job) this.update(r.job); } : null;
      let o;
      if (!running) {
        o = job.state === "done" ? (this.active.local ? { done: { text: `${model || "Your local model"} has read its part` } } : { plain: { key: "done", what: "Nothing was left for it to read" } })
          : { plain: { key: "stopped", what: "Stopped" } };
      } else if (localNow) {
        // Stop <model> pressed: it reads on to the end of what it has in hand, and says so where its Stop was
        const stopping = L && L.gate === "wait" ? `Stops after the ${["excerpt", "passage"].includes(noun) ? `${noun}s` : noun} in hand` : null;
        o = { running: { phase: m.phase, seconds: m.seconds, ...(L ? counts(L.waiting || 0) : {}) }, onStop: stopLocal, stopping };
      } else if (m && m.phase === "refused" && m.who === "local") {
        o = { memory: m.memory || null, refused: m.memory ? true : (m.error || true), count: L ? L.waiting : 0,
          note: L ? null : "When this run has finished, you can start it from here.", sub: this.engines.has("cloud") ? `${agentTitle()} reads the rest meanwhile.` : null };
      } else if (L && L.problem) {
        o = { problem: L.problem };
      } else if (L && L.gate === "wait" && (L.waiting || 0) > 0) {
        o = { count: L.waiting, memory: L.memory || null, since: this.localSince || (this.localSince = Date.now()),
          // all that is left of the job: a model that cannot start (memory short) needs you
          blocking: !cloudBusy,
          // the job goes on only once these are read (or Stop): said once Claude's side is done or absent
          sub: cloudBusy ? null : `The work goes on once ${L.waiting === 1 ? "it is" : "they are"} read: press Start, or stop the work.` };
      } else if (L && (L.waiting || 0) > 0) {   // its Start was pressed: the model is on its way
        o = { running: { phase: "waiting", ...counts(L.waiting) }, count: L.waiting, onStop: stopLocal };
      } else {
        o = this.active.local ? { done: { text: `${model || "Your local model"} has read its part` } }
          : { plain: { key: "later", what: mainLocal ? "Its part comes with the steps above" : "Nothing waits for it yet" } };
      }
      o = { model, noun, compact, ...o };
      const key = JSON.stringify(o.running ? ["run", model, !!o.onStop, o.stopping || null] : o);
      let side = this.sides.local;
      if (o.count && !o.running && !o.problem && !o.plain && !o.done) o.onStart = async (force) => { const r = await api("POST", `/api/jobs/${P(job.id)}/local/start`, { force: !!force }); if (r && r.job) this.update(r.job); if (this.o.onLocalStart) this.o.onLocalStart(); };
      if (!side) {
        side = this.sides.local = aiSide({ where: "local", ...o, onState: onState("local") });
        placeSide(this.block, "local", side);
        this.sideKey.local = key;
      } else if (key !== this.sideKey.local) {
        this.sideKey.local = key;
        redrawSide(side, { ...o, onState: onState("local") });
      } else if (o.running) {   // written in place: what it does and how far, never a new Stop under the pointer
        const what = side.querySelector(".ab-what strong");
        const words = `${model || "Your local model"} ${{ waiting: "is loading and reading", thinking: "is thinking it over", writing: "is writing its answer" }[o.running.phase] || "is reading"}`;
        if (what && what.textContent !== words) what.textContent = words;
        const c = side.querySelector(".ab-count");
        const r = o.running;
        const cw = [r.total ? `${fmt.num(r.done || 0)} of ${plural(r.total, noun)} done` : "", r.seconds ? fmt.secs(r.seconds) : ""].filter(Boolean).join(" · ");
        if (c && c.textContent !== cw) c.textContent = cw;
        sidePct(side, r.total ? 100 * (r.done || 0) / r.total : null);
      }
      sideFigures(side, localNow ? modelFigures(m, this.seen) : null);
    }

    // ---- Claude
    if (this.engines.has("cloud")) {
      const pct = p.batch && p.batch.total ? 100 * Math.max(0, p.batch.index - 1) / p.batch.total : p.total && !localNow ? 100 * (p.done || 0) / p.total : null;
      let side = this.sides.cloud;
      // a Claude Code job keeps Claude's live side once it was there: the project's queue says whether its part still
      // waits, works or is answered (the local model's report may be the newer one meanwhile)
      if (wq) this.lastQ = wq;
      // the last words it had, whole, while the local model's report is the newer one: flipping between two would
      // draw Claude's side again (and its Stop under the pointer) every poll. 0.19.14: marked `stale`, so its counts
      // never outvote the project's queue: once Claude Code has answered, its "1 waits" asked for Claude Code again
      // while the local model read, and each run found nothing to do
      const jqNow = wq || (this.lastQ && { ...this.lastQ, stale: true }) || null;
      if (held) {
        const key = `held:${held.provider}:${held.excerpts}`;
        if (this.sideKey.cloud !== key || !side) {
          this.sideKey.cloud = key;
          const n = held.excerpts || 0;
          const o = { state: "need", what: `${plural(n, "excerpt")} ${n === 1 ? "waits" : "wait"} for ${held.agent_title || agentTitle(s)}`,
            muted: `It may read only documents that allow ${held.company || "its company"}`,
            line: providerAllowLine(App.project, null, () => {}), onState: onState("cloud") };
          if (side && !side.arSetQueue) redrawSide(side, o);
          else { side = this.sides.cloud = aiSide({ where: "cloud", ...o }); placeSide(this.block, "cloud", side); }
        }
      } else if (App.project && (wq || (running && job.queue && this.lastQ))) {
        const key = "live";
        if (this.sideKey.cloud !== key || !side) {
          this.sideKey.cloud = key;
          const fresh = aiSide({ where: "cloud", live: true, q: jqNow, compact, pct, onState: onState("cloud") });
          fresh.dataset.qk = queueKey(jqNow);
          placeSide(this.block, "cloud", fresh);
          side = this.sides.cloud = fresh;
        } else {
          const qk = queueKey(jqNow);
          if (side.dataset.qk !== qk) { side.dataset.qk = qk; side.arSetQueue(jqNow); }
          sidePct(side, pct);
        }
      } else {
        let o;
        if (!running) o = job.state === "done" ? { state: "done", what: this.active.cloud ? `${cloudName()} has answered its part` : `Nothing was sent to ${cloudName()}` } : { state: "stopped" };
        else if (s.backend === "anthropic" && !localNow) o = { state: "run", what: "Claude reads the excerpts", line: compact ? null : readsLine("the excerpts it needs"), pct };
        else if (this.active.cloud) o = { state: "done", what: `${cloudName()} has answered its part` };
        else o = { state: "later", what: isAgent(s) ? `Nothing waits for ${agentTitle(s)} yet` : "Its part comes after the steps above" };
        const key = JSON.stringify({ ...o, line: !!o.line, pct: null });
        if (!side || this.sideKey.cloud !== key) {
          this.sideKey.cloud = key;
          if (side && !side.arSetQueue) redrawSide(side, { ...o, onState: onState("cloud") });
          else { side = this.sides.cloud = aiSide({ where: "cloud", ...o, onState: onState("cloud") }); placeSide(this.block, "cloud", side); }
        } else if (o.state === "run") sidePct(side, pct);
      }
    }
  }

  row(key, label, state, detail, seconds) {
    const li = h("li", { class: `step step-${state}` },
      h("span", { class: "st-icon" }, icon(STEP_ICON[state] || "circle", { size: 16 })),
      h("span", {}, h("span", { class: "st-label" }, label), h("span", { class: "st-detail" }, detail || "")),
      h("span", { class: "st-time" }, seconds !== null && seconds !== undefined ? fmt.secs(seconds) : ""));
    li.dataset.state = state;
    this.rows.set(key, li);
    return li;
  }

  setRow(li, state, detail, seconds) {
    if (li.dataset.state !== state) {
      li.className = `step step-${state}`;
      li.dataset.state = state;
      replace(li.querySelector(".st-icon"), icon(STEP_ICON[state] || "circle", { size: 16 }));
    }
    const d = li.querySelector(".st-detail");
    if (d.textContent !== (detail || "")) d.textContent = detail || "";
    const t = li.querySelector(".st-time");
    const txt = seconds !== null && seconds !== undefined ? fmt.secs(seconds) : "";
    if (t.textContent !== txt) t.textContent = txt;
  }

  // One line with the time each step took (for the result page).
  static summary(progress) {
    if (!progress) return "";
    const bits = [];
    if (progress.decompose && progress.decompose.state === "done") bits.push(`splitting into parts ${fmt.secs(progress.decompose.seconds)}`);
    const totals = {};
    for (const part of progress.parts || []) for (const s of part.steps || []) if (s.state === "done" && s.seconds !== null) totals[s.label] = (totals[s.label] || 0) + s.seconds;
    for (const [label, secs] of Object.entries(totals)) bits.push(`${label.toLowerCase()} ${fmt.secs(secs)}`);
    return bits.join(" · ");
  }
}

// The panel at either size: aiRun({ size, … }) → { el, update(job), destroy() }
export function aiRun(opts = {}) { return new AiRun(opts); }

// The full panel of a check (also batches and "read more"), by its old name: aiRun({ size: "full" }).
export class ProgressPanel extends AiRun {
  constructor(opts = {}) { super({ ...opts, size: "full" }); }
}

// A short AI job inside a card (reading one excerpt again, naming the themes), by its old name: aiRun({ size:
// "compact" }) with what runs as its line. `.waiting`: it waits for a Start or its turn (the page's own counter leaves
// out the time left then).
export class MiniJob extends AiRun {
  constructor(opts = {}) { super({ ...opts, size: "compact" }); }
  update(job) {
    super.update(job);
    this.waiting = job.state === "queued" || this.headKind === "waiting" || this.headKind === "attention";
  }
}

// A simple bar for work that is not the AI's (adding documents, search by meaning, the glossary).
export function simpleProgress(job, labelFn) {
  const p = job.progress || {};
  const total = p.total || 0, done = p.done || 0;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const running = job.state === "queued" || job.state === "running";
  const label = job.waiting_for ? job.waiting_for.message   // 0.18 queued jobs
    : labelFn ? labelFn(p, job) : (p.file ? `${done} of ${total} · ${p.file}` : total ? `${done} of ${total}` : "Starting…");
  return h("div", { class: "stack prg-line" },
    h("div", { class: "row prg-line-head" }, h("span", { class: "it" }, running ? h("span", { class: "running-dot", "aria-hidden": "true" }) : null, h("strong", {}, label)), h("span", { class: "muted small" }, fmt.secs(job.seconds))),
    h("div", { class: "progress-bar " + (running && !total ? "indeterminate" : ""), role: "progressbar", "aria-valuemin": 0, "aria-valuemax": total || 100, "aria-valuenow": total ? done : null, "aria-label": label },
      h("span", { style: { width: `${Math.max(2, pct)}%` } })));
}

// A job in a card: what it is doing, its time and a Stop button. `onEnd(job)` runs when it ends. opts: small (h3),
// stoppedText, ai (the AI does this work: the AI run panel in the card, its two sides under the line; noun, engines
// as aiRun's). Returns the watcher (stop it when the page is left).
export function jobCard(box, jobId, title, labelFn, onEnd, opts = {}) {
  // a running job's Stop (stopButton(): small, quiet, the stop icon); a queued one's Cancel (a small quiet button, as
  // the work state Queued has it: docs/DESIGN.md 4.21). One shows at a time; both cancel the job.
  const stop = stopButton();
  const cancel = button({ kind: "quiet", sm: true, hidden: true }, "Cancel");   // 0.18 queued jobs
  const pb = h("div", { "aria-live": opts.ai ? null : "polite" });
  const head = h("span", {}, title);
  const holder = card({ as: "div", title: head, level: opts.small ? "h3" : "h2", action: h("span", { class: "btn-row" }, stop, cancel) }, pb);
  for (const b of [stop, cancel]) {
    b.addEventListener("click", async () => {
      stop.disabled = cancel.disabled = true;
      try { await api("POST", `/api/jobs/${P(jobId)}/cancel`); } catch (e) { showError(e); stop.disabled = cancel.disabled = false; }
    });
  }
  box.hidden = false;
  replace(box, holder);
  const run = opts.ai ? aiRun({ size: "compact", stop: false, noun: opts.noun, engines: opts.engines,
    label: (job) => (job.waiting_for ? job.waiting_for.message : labelFn ? labelFn(job.progress || {}, job) : title) }) : null;
  if (run) replace(pb, run.el);
  const w = watchJob(jobId, (job) => {
    if (run) run.update(job); else replace(pb, simpleProgress(job, labelFn));
    const queued = !TERMINAL.has(job.state) && !!job.waiting_for;
    stop.hidden = TERMINAL.has(job.state) || queued;
    cancel.hidden = !queued;
  });
  w.promise.then((job) => {
    if (job.state === "error" && job.error_kind === "memory" && job.can_run_again) {
      // 0.19.4: the local model was not started: its side, whose Start runs the job again in this card
      head.textContent = "Waiting for your local model";
      stop.hidden = cancel.hidden = true;
      replace(pb, memoryRefused(job, (j) => jobCard(box, j.id, title, labelFn, onEnd, opts)));
    } else if (job.state === "error") {
      head.textContent = "It did not work";
      replace(pb, jobError(job));
    } else if (job.state === "cancelled") {
      head.textContent = "Stopped";
      replace(pb, h("p", { class: "muted prg-stopped" }, opts.stoppedText || "Stopped. What was done so far is kept."));
    }
    if (onEnd) onEnd(job);
  }).catch(showError);
  return w;
}

function jobErrorParts(job, fallback) {
  return [h("p", {}, job.error_kind === "backend" ? "The AI model stopped answering." : job.error_kind === "internal" ? "Something went wrong inside the app." : (job.error || fallback)),
    job.error_kind === "backend" || job.error_kind === "internal" ? fold({}, "Technical details", h("div", { class: "mono small" }, job.error || "")) : null,
    job.error_kind === "backend" ? link({ href: "#/settings" }, "Check the AI model in Settings") : null];
}

// Why a job did not work, in plain words, with the technical message folded away.
export function jobError(job) {
  return notice({ kind: "error" }, ...jobErrorParts(job, "It could not finish."));
}
