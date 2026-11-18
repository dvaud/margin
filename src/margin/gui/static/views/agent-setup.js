// Providers stage 2 (B4): an agent on the person's own plan (Claude Code, Codex, Antigravity), set up step by step in
// the same dialog as an API key or a storage space (outside-setup.js): install it, sign in, add Margin to it. Steps
// already done show as done and the dialog opens at the first that is not. Installing runs as a job and the step moves
// on by itself once the program is found; signing in is watched every 4 s while its step is open and moves on by itself
// once the program says so; adding Margin is the dialog's main button. Margin never sees the login: the program keeps it.
// Each agent is an adapter: Codex and Antigravity here, on GET/POST /api/agent-setup (stage 2, A4), Claude Code in
// settings.js on /api/claude-setup. Settings → AI shows each one's checklist card (settings.js) with a button that
// opens this dialog.
import { api, h, toast, notice, fold, copyLine, workState, watchJob, replace, rememberAgent } from "../lib.js";
import { outsideSetup, stepButton, allowLine } from "./outside-setup.js";
import { appliedLine } from "./provider-setup.js";

// the done step's line of the models applied: the adapter's own (Claude's ladder), else the CLI's line-up in use
const appliedLineup = (r, ad) => (ad.applied ? ad.applied(r)
  : r && r.lineup_in_use ? appliedLine(r.lineup_in_use, `Applied from ${ad.title}’s recommendations for your plan: `) : null);

// The facts of each agent CLI (providers.py AGENT_CLIS, checked 18 November 2026), for the words of its steps; the
// API (A4) gives the same and more when it answers.
export const AGENTS = {
  codex: { route: "codex", title: "Codex", company: "OpenAI", program: "codex", plan: "your ChatGPT plan", account: "your ChatGPT account",
    installer: "curl -fsSL https://chatgpt.com/codex/install.sh | sh", docs: "https://learn.chatgpt.com/docs/auth", call: "$margin-run" },
  antigravity: { route: "antigravity", title: "Antigravity", company: "Google", program: "agy", plan: "your Google account", account: "your Google account",
    installer: "curl -fsSL https://antigravity.google/cli/install.sh | bash", docs: "https://antigravity.google/docs/getting-started", call: "" },
};

// The adapter of Codex or Antigravity on the agent-setup API. Its `read` gives the API's answer with its status made
// the same as Claude Code's (`connector`: Margin added).
export function cliAdapter(route) {
  const a = AGENTS[route];
  const q = `route=${encodeURIComponent(route)}`;
  return {
    ...a,
    read: async (refresh) => {
      const r = await api("GET", `/api/agent-setup?${q}${refresh ? "&refresh=1" : ""}`);
      return { ...r, status: r.status || {}, installer: (r.installer && r.installer.line) || a.installer, docs: (r.installer && r.installer.docs) || r.docs || a.docs };
    },
    install: async () => (await api("POST", "/api/agent-setup/install", { route })).job,
    signIn: () => api("POST", "/api/agent-setup/sign-in", { route }),
    addMargin: () => api("POST", "/api/agent-setup", { route }),
    installWhy: () => h("p", {}, `${a.title} is ${a.company}’s program that lets Margin work on ${a.plan}. Margin runs ${a.company}’s installer, which puts it in your user folder. It needs no administrator rights and takes a minute or two.`),
    signInWords: (opened) => (opened.opened === false
      ? h("div", {}, h("p", {}, `${route === "codex" ? "Codex could not open its sign-in" : "No window could be opened"} from here. Open a terminal (Terminal on a Mac, PowerShell on Windows), type the line below and follow the steps:`),
        copyLine(opened.command || (route === "codex" ? "codex login" : "agy"), "Copy", "a terminal"))
      : h("p", {}, route === "codex" ? "Codex opens its sign-in page in your browser. Sign in there with your ChatGPT account; this step moves on by itself."
        : `A ${opened.window || "terminal"} window opened with Antigravity, which opens Google’s sign-in page in your browser. Sign in, then switch off Enable Telemetry in Antigravity’s settings (under AI credits and feedback) and close that window; this step moves on by itself.`)),
    // the first line is what the button does; a second, muted, is what to do in the window that opens
    signInIntro: route === "codex" ? "Press the button: Codex opens its sign-in page in your browser."
      : ["Press the button: a window opens with Antigravity, in an empty folder of Margin, and it opens Google’s sign-in page in your browser.",
        "Sign in in the window that opens. Before you close it, switch off Enable Telemetry in Antigravity’s settings, under AI credits and feedback: while it is on, Google may use what Antigravity reads."],
    adds: route === "codex"
      ? ["the Margin connector, through which Codex takes the tasks and sends back its answers", ["its skill ", h("code", {}, "$margin-run")], "its helpers, one for each kind of task"]
      : ["the Margin connector, through which Antigravity takes the tasks and sends back its answers", "its skill margin-run and its helpers, as one plugin",
        "one permission line, so Antigravity may use the Margin connector without asking each time",
        "Margin’s own empty work folder, marked as trusted, where it starts Antigravity"],
    addsNote: route === "antigravity"
      ? notice({ kind: "info", role: "note" }, h("p", {}, "Antigravity’s own tools cannot be switched off from outside, so Margin starts it in an empty folder of its own, in its sandbox: it sees only the passages in Margin’s tasks."))
      : null,
    afterWords: (project) => [
      h("p", {}, "Press ", h("strong", {}, `Start ${a.title}`), " wherever work waits (or in the sidebar): Margin starts it in the background on the project’s work, and the results appear as they come in."),
      a.call ? h("p", { class: "muted small" }, "You can also type ", h("code", {}, `${a.call} ${project || "<project>"}`), ` in ${a.title} yourself.`) : null],
  };
}

// The first step not done yet: 0 install, 1 sign in, 2 add Margin.
export function firstToDo(st = {}) {
  if (!st.found) return 0;
  if (st.signed_in === true) return 2;
  if (st.signed_in === false) return 1;
  return st.connector ? 2 : 1;   // the program does not say: the sign-in step, unless Margin was added already
}

// The dialog. `ad`: an adapter; `info`: its last answer (read again as the steps go). opts.project: for the done
// step's line; opts.onChange(info): after every new reading (the card's checklist follows). Resolves with the last
// reading once Margin is added, or null.
export async function agentSetupDialog(ad, info = {}, opts = {}) {
  let cur = info || {};
  const st = () => cur.status || {};
  let timer = null;
  let polling = -1;
  const stopPoll = () => { clearTimeout(timer); timer = null; polling = -1; };
  const fresh = async () => {
    cur = await ad.read(true);
    rememberAgent(ad.route, cur.status || {});   // the sidebar's line follows the set-up
    if (opts.onChange) opts.onChange(cur);
    return st();
  };
  let ui = null;
  // ---- step 1: install
  const installNow = h("div", { class: "agent-step-now", "aria-live": "polite" });
  const installed = h("p", { class: "agent-found" });
  const showFound = () => {
    replace(installed, st().found ? workState("done", `${ad.title} is on this computer${st().version ? ` (${st().version})` : ""}.`) : "");
  };
  async function runInstall(btn) {
    btn.disabled = true;
    ui.lock.on = true;
    replace(installNow, workState("running", `Installing ${ad.title}… (a minute or two)`));
    try {
      const job = await ad.install();
      const done = await watchJob(job.id, null, 1000).promise;
      if (done.state !== "done") {
        replace(installNow, notice({ kind: "error", live: false }, h("p", {}, `${ad.title} could not be installed from here. Run the command yourself in a terminal, or follow its set-up page.`),
          done.error ? fold({ sm: true }, "Technical details", h("div", { class: "mono small" }, done.error)) : null));
        return;
      }
      const s = await fresh();
      showFound();
      replace(installNow);
      if (s.found) ui.go(1);
      else replace(installNow, notice({ kind: "attention", live: false }, h("p", {}, `The installer finished, but ${ad.title} is not found yet. Press I have installed it in a moment.`)));
    } catch (e) { replace(installNow, notice({ kind: "error", live: false }, h("p", {}, e.message || String(e)))); }
    finally { ui.lock.on = false; btn.disabled = false; }
  }
  const installBtn = stepButton(`Install ${ad.title}`, (e) => runInstall(e.currentTarget), { id: `agent-install-${ad.route}`, icon: "download" });
  const checkInstalled = stepButton("I have installed it", async () => { try { const s = await fresh(); showFound(); if (s.found) ui.go(1); else toast(`${ad.title} is not found on this computer yet.`, "warn"); } catch (e) { toast(e.message, "warn"); } }, { kind: "quiet" });
  // no "Next step": "I have installed it" checks, then moves on by itself once the program is found
  const stepInstall = { title: `Install ${ad.title}`, next: false, body: [
    ad.installWhy(),
    h("p", { class: "small muted" }, "The command it runs:"), copyLine(cur.installer || ad.installer, "Copy", "a terminal"),
    h("div", { class: "btn-row" }, installBtn, checkInstalled), installNow, installed,
    h("p", { class: "muted small" }, "Prefer to do it yourself? Run the command in a terminal, or follow ",
      h("a", { href: cur.docs || ad.docs, target: "_blank", rel: "noopener" }, `${ad.title}’s set-up page`), ", then press I have installed it.")] };
  // ---- step 2: sign in
  const signNow = h("div", { class: "agent-step-now", "aria-live": "polite" });
  const signedAs = h("p", { class: "agent-found" });
  const showSigned = () => (st().signed_in === true ? replace(signNow) : null, replace(signedAs, st().signed_in === true ? workState("done", `Signed in${st().account ? ` with ${st().account}` : ""}.`) : ""));
  // while it waits, Open the sign-in stays pressed (a second press would start a second sign-in); after 30 s a quiet
  // "Open it again" offers a new one, for a window closed too soon
  let againTimer = null;
  async function openSignIn() {
    clearTimeout(againTimer);
    signBtn.disabled = true;
    let opened = { opened: false };
    try { opened = await ad.signIn(); } catch (e) { opened = { opened: false, error: e.message }; }
    signIntro.hidden = true;   // what the button does is done; the words of what to do now take its place
    const again = h("span", { class: "agent-again", hidden: true }, " ", stepButton("Open it again", () => openSignIn(), { kind: "quiet", id: `agent-sign-in-again-${ad.route}` }));
    replace(signNow, h("div", {}, ad.signInWords(opened), h("p", {}, workState("waiting", "Waiting for you to sign in…"), again)));
    if (opened.opened === false) { signBtn.disabled = false; return; }   // nothing started: the button may try again
    againTimer = setTimeout(() => { again.hidden = false; }, 30000);
  }
  async function checkSigned(now) {
    try {
      const s = await fresh();
      showSigned();
      if (s.signed_in === true || (now && s.signed_in !== false)) { stopPoll(); ui.go(2); return; }
      if (now) toast(`${ad.title} does not say it is signed in yet. Finish signing in, then press the button again.`, "warn");
    } catch (_) { /* try again */ }
  }
  const poll = (i) => {
    if (polling === i) return;
    stopPoll(); polling = i;
    const started = Date.now();
    const tick = async () => {
      if (polling !== i) return;
      await checkSigned(false);
      if (polling !== i) return;
      if (Date.now() - started > 15 * 60 * 1000) { stopPoll(); replace(signNow, h("p", { class: "muted small" }, "Stopped waiting for the sign-in. Press I have signed in once you have.")); return; }
      timer = setTimeout(tick, 4000);
    };
    timer = setTimeout(tick, 4000);
  };
  const signBtn = stepButton("Open the sign-in", () => openSignIn(), { id: `agent-sign-in-${ad.route}`, icon: "external-link" });
  const signIntro = h("div", {}, [].concat(ad.signInIntro).map((t, i) => h("p", { class: i ? "muted small" : null }, t)));
  const stepSign = { title: "Sign in", next: false, body: [
    signIntro,
    h("div", { class: "btn-row" }, signBtn,
      stepButton("I have signed in", () => checkSigned(true), { id: `agent-signed-${ad.route}` })),
    signNow, signedAs,
    h("p", { class: "muted small" }, `Margin never sees your login: ${ad.title} keeps it.`)] };
  // ---- step 3: add Margin (the main button)
  const stepAdd = { title: `Add Margin to ${ad.title}`, next: false, body: [
    h("p", {}, "The button below adds to ", ad.title, ":"),
    h("ul", { class: "agent-adds" }, ad.adds.map((x) => h("li", {}, x))),
    h("p", { class: "muted small" }, `Nothing else in ${ad.title} is changed.`),
    ad.addsNote || null] };
  showFound(); showSigned();
  return outsideSetup({
    title: `Set up ${ad.title}`, label: `Setting up ${ad.title}`, id: `agent-steps-${ad.route}`,
    steps: [stepInstall, stepSign, stepAdd],
    start: firstToDo(st()), ask: false,
    mainText: `Add Margin to ${ad.title}`,
    onStep: (i, u) => { ui = u; if (i === 1) poll(i); else stopPoll(); },
    onClose: () => { stopPoll(); clearTimeout(againTimer); },
    async submit(_body, u) {
      u.progress(`Adding Margin to ${ad.title}…`);
      const r = await ad.addMargin();
      const bad = (r.steps || []).filter((x) => !x.ok);
      if (bad.length) {
        u.progress("");
        u.error(`Margin could not be added: ${bad[0].step}${bad[0].text ? ` (${bad[0].text})` : ""}`);
        return false;
      }
      if (r.status) cur = { ...cur, status: r.status };
      try { await fresh(); } catch (_) { /* the answer above is enough */ }
      return cur;
    },
    after: (r) => ({ title: `${ad.title} is ready`, body: [
      notice({ kind: "done", role: "note" }, h("p", {}, `Margin is added to ${ad.title}.`)),
      ...[].concat(ad.afterWords(opts.project)),
      appliedLineup(r, ad),
      allowLine(opts.project) ] }),
    doneWords: `${ad.title} is set up.`,
  });
}
