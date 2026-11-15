// 0.17.0: the research log beside any page. A button fixed at the top right of the window opens a panel on the right:
// write an entry while looking at anything, and see the entries kept with the page you are on (or all of them).
// The whole log, with search, export and the rest, is its own place (#/log): there the button and the panel hide (the
// page has the write box and every entry), and the panel comes back on the next page if it was open.
import { App, api, h, icon, clear, session, fmt, toast, showError, P, button, link, textarea, choice, drawer, drawerButton, setDrawerOpen } from "../lib.js";
import { subjectHref, entryText, entrySubject, entryWho } from "./log.js";

const PAGE = 30;
const GROUP_ICON = { entries: "note", colleagues: "users", documents: "book-open", checks: "flask", themes: "shapes",
  codebooks: "book-marked", history: "undo", together: "users", other: "circle" };
const NOTHING_HERE = "Nothing is kept with this page; showing all";

// Which part of the log belongs to the page at this hash. {subject_kind, subject_id} for one item, {group} for a place
// (a list of things), null for a page that has none (Overview, Search, Concepts, Settings...). `label` finishes
// "Kept with: ...". `place` pages write their entries with no subject.
export function pageContext(hash) {
  const path = String(hash || "").replace(/^#/, "").split("?")[0].replace(/\/+$/, "");
  const parts = path.split("/").filter(Boolean).map((s) => { try { return decodeURIComponent(s); } catch (_) { return s; } });
  const [a, id] = parts;
  if (a === "h" && id) return { subject_kind: "check", subject_id: id, label: "this hypothesis" };
  if (a === "doc" && id) return { subject_kind: "document", subject_id: id, label: "this document" };
  if (a === "themes" && id) return { subject_kind: "themes", subject_id: id, label: "these themes" };
  if (a === "codebooks" && id) return { subject_kind: "codebook", subject_id: id, label: id };
  const place = { sources: "documents", notes: "documents", bibliography: "documents", hypotheses: "checks", check: "checks",
    batch: "checks", history: "checks", map: "checks", themes: "themes", profile: "codebooks", codebooks: "codebooks" }[a];
  if (place && parts.length === 1) return { group: place, label: "the project" };
  return null;
}

export function initLogDrawer() {
  if (document.getElementById("logdrawer")) return;
  const shell = document.getElementById("shell");
  if (!shell) return;
  const body = document.body;
  let open = session("logdrawer-open") === true;   // wanted open (remembered); shown only off the Research log page
  let mode = session("logdrawer-mode") === "all" ? "all" : "page";
  let shown = PAGE;
  let token = 0;               // the newest refresh wins
  const docTitles = new Map(); // "project, document" -> its title, each asked for once when a document page is the context
  // the Research log page (#/log) has the write box and every entry: no button and no panel there
  const onLogPage = () => /^#\/log\/?(?:\?|$)/.test(location.hash);
  const showing = () => open && !onLogPage();

  // ---- the button (docs/DESIGN.md 4.19): the drawer component's, soft teal while the drawer is open; in the top bar
  // under 861 px
  const phone = () => window.matchMedia("(max-width: 860px)").matches;
  const btn = drawerButton({ id: "logdrawer-btn", controls: "logdrawer", label: "Write in the log", icon: "notebook",
    title: "The research log, beside this page", onClick: () => (open ? close(true) : openIt(true)) });
  const placeBtn = () => {
    const bar = document.getElementById("topbar");
    if (phone() && bar) { if (btn.parentNode !== bar) bar.appendChild(btn); }
    else if (btn.parentNode !== body) {
      const skip = document.querySelector(".skip-link");
      if (skip) skip.after(btn); else body.prepend(btn);
    }
  };

  // ---- the drawer: its frame is the drawer component; its parts are the Research log page's own (the write box and
  // the list of entries, .log-new and .log-entries), so an entry looks the same on the page and here. Its one control,
  // This page | All, is in its head (docs/DESIGN.md 4.19: at most one control)
  const which = choice({ label: "Show entries of", filter: true, sm: true, value: mode, options: [["page", "This page"], ["all", "All"]],
    onPick: (v) => { mode = v; session("logdrawer-mode", mode); shown = PAGE; refresh(); } });
  const pageBtn = which.querySelector('[data-value="page"]');
  const ta = textarea({ class: "logdrawer-text", rows: 3, maxlength: 10000, "aria-label": "A new research-log entry", placeholder: "A decision and why…" });
  const keptWith = h("p", { class: "muted small logdrawer-kept" });
  const addBtn = button({ kind: "main", sm: true, onClick: add }, "Add to the log");
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); add(); } });
  // the note line: said when This page has nothing and all entries show
  const note = h("p", { class: "muted small log-show", hidden: true });
  const list = h("div", { class: "logdrawer-list", "aria-live": "polite" });
  const aside = drawer({ id: "logdrawer", title: "Research log", icon: "notebook", control: which,
    onClose: () => close(true), closeLabel: "Close the research log",
    sections: [h("div", { class: "log-new" }, ta, h("div", { class: "log-new-foot" }, keptWith, addBtn)), note, list],
    foot: link({ href: "#/log" }, "The whole research log") });
  const closeBtn = aside.closeButton;
  shell.appendChild(aside);
  placeBtn();
  window.matchMedia("(max-width: 860px)").addEventListener("change", placeBtn);

  const overlay = () => window.matchMedia("(max-width: 999px)").matches;

  // shows or hides the panel and the button for the page: open or not, and never on the Research log page
  function place() {
    btn.hidden = onLogPage();
    aside.hidden = !showing();
    setDrawerOpen(showing(), btn);
  }
  function openIt(byUser) {
    open = true;
    session("logdrawer-open", true);
    place();
    refresh();
    if (byUser) (phone() ? closeBtn : ta).focus();
  }
  function close(returnFocus) {
    const hadFocus = aside.contains(document.activeElement);
    open = false;
    session("logdrawer-open", false);
    place();
    if ((returnFocus || hadFocus) && !btn.hidden) btn.focus();
  }

  // ---- what this page is
  const context = () => pageContext(location.hash);
  async function titleOf(ctx) {
    if (!ctx || ctx.subject_kind !== "document") return ctx && ctx.label;
    const project = App.project;
    const key = `${project}\n${ctx.subject_id}`;
    if (!docTitles.has(key)) {
      try {   // the one document, not the whole list of them
        const r = await api("GET", `/api/projects/${P(project)}/documents/${P(ctx.subject_id)}?limit=1`);
        docTitles.set(key, r.title || null);
      } catch (_) { /* the words "this document" do */ }
    }
    return docTitles.get(key) || ctx.label;
  }

  // ---- reading
  async function refresh() {
    if (!showing() || !App.project) return;   // the log reads itself only when it is shown
    const mine = ++token;
    const project = App.project;
    const ctx = context();
    const name = await titleOf(ctx);
    if (mine !== token) return;
    keptWith.textContent = `Kept with: ${ctx ? name : "the project"}`;
    const base = `/api/projects/${P(project)}/log`;
    const query = (filter) => {
      const qs = new URLSearchParams({ limit: String(shown) });
      if (filter) for (const [k, v] of Object.entries(filter)) if (v && ["group", "subject_kind", "subject_id"].includes(k)) qs.set(k, v);
      return `${base}?${qs}`;
    };
    let data, fellBack = false;
    try {
      if (mode === "page" && ctx) {
        data = await api("GET", query(ctx));
        if (mine !== token) return;
        if (!data.entries.length) { fellBack = true; data = await api("GET", query(null)); }
      } else {
        fellBack = mode === "page";
        data = await api("GET", query(null));
      }
    } catch (e) {
      if (mine !== token) return;
      clear(list);
      list.appendChild(h("p", { class: "muted small" }, "The log could not be read. ", button({ kind: "quiet", sm: true, onClick: refresh }, "Try again")));
      return;
    }
    if (mine !== token) return;
    const showingAll = mode === "all" || fellBack;
    which.set(showingAll ? "all" : "page");
    pageBtn.disabled = !ctx;
    note.hidden = !fellBack;
    note.textContent = fellBack ? NOTHING_HERE : "";
    draw(data, ctx, showingAll);
  }

  function draw(data, ctx, showingAll) {
    clear(list);
    if (!data.entries.length) {
      list.appendChild(h("p", { class: "muted small" }, "Nothing in the log yet. Write the first entry above."));
      return;
    }
    const here = location.hash.split("?")[0];
    const ol = h("ol", { class: "log-entries" });
    for (const e of data.entries) {
      const href = subjectHref(e);
      const to = href && href !== here && !(ctx && ctx.subject_id && !showingAll) ? href : null;
      ol.appendChild(h("li", { class: "log-entry" + (e.kind === "entry" ? " log-own" : "") },
        h("span", { class: "log-icon", "aria-hidden": "true" }, icon(GROUP_ICON[e.group] || "circle", { size: 14 })),
        h("div", { class: "log-body" },
          h("div", { class: "log-meta" }, h("time", { class: "log-time", datetime: e.at, title: fmt.date(e.at) }, fmt.whenText(e.at)), entryWho(e)),
          entryText(e, to),
          e.why ? h("div", { class: "log-why" }, `Why: ${e.why}`) : null,
          entrySubject(e, to) ? h("div", { class: "log-meta" }, entrySubject(e, to)) : null)));
    }
    list.appendChild(ol);
    if (data.total > data.entries.length) {
      list.appendChild(h("div", { class: "logdrawer-more" }, button({ kind: "quiet", sm: true,
        onClick: () => { shown += PAGE; refresh(); } }, `Show more (${fmt.num(data.total - data.entries.length)} older)`)));
    }
  }

  // ---- writing
  async function add() {
    const text = ta.value.trim();
    if (!text) { ta.focus(); return; }
    const ctx = context();
    const payload = { text };
    if (ctx && ctx.subject_kind) {
      payload.subject_kind = ctx.subject_kind;
      payload.subject_id = ctx.subject_id;
      if (ctx.subject_kind === "codebook") payload.title = ctx.subject_id;
      else if (ctx.subject_kind === "document") { const t = await titleOf(ctx); if (t && t !== ctx.label) payload.title = t; }
    }
    addBtn.disabled = true;
    try {
      await api("POST", `/api/projects/${P(App.project)}/log`, payload);
      ta.value = "";
      shown = PAGE;
      toast("Added to the research log.", "ok");
      await refresh();
    } catch (e) { showError(e); } finally { addBtn.disabled = false; }
  }

  // ---- when to read again, and when to close
  window.addEventListener("hashchange", () => { shown = PAGE; place(); refresh(); });
  App.onChange(() => { if (showing()) { shown = PAGE; refresh(); } });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && showing() && !e.defaultPrevented && !document.querySelector("#dialogs dialog[open]")) close(aside.contains(document.activeElement)); });
  document.addEventListener("click", (e) => {
    if (showing() && overlay() && !aside.contains(e.target) && !btn.contains(e.target) && !e.target.closest(".sidebar, .topbar, .toasts, #dialogs")) close(false);
  });

  place();
  if (showing()) refresh();
}
