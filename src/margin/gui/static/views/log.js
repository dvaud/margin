// 0.16 (roadmap F4): the research log. A dated record of what was decided in the project, written by the app as it
// happens (documents added and removed, checks made and dropped, themes removed, codebook changes...), with room for
// a person's own entries and their reasons. An entry about a change can be compared with now and restored (F5).
import { featureEyebrow } from "../features.js";
import { App, api, h, icon, clear, toast, showError, failedLoad, fmt, pageHead, P, confirmDialog, download, downloadLinks,
  debounce, session, dialog, button, searchField, select, textarea, menu, link, personMark, emptyState, latest, plural } from "../lib.js";
import { compareVersion } from "./versions.js";
import { shareTag, shareItem, unshareItem, sharingOf } from "./share.js";   // 0.18 (L1)

const GROUP_ICON = { entries: "note", colleagues: "users", documents: "book-open", checks: "flask", themes: "shapes",
  codebooks: "book-marked", history: "undo", together: "users", other: "circle" };
const GONE = new Set(["document-removed", "check-removed", "themes-removed", "codebook-removed"]);
const VERSION_KIND = { themes: "themes", check: "check", codebook: "codebook" };
const PAGE = 200;

export function subjectHref(e) {
  if (!e.subject_id || GONE.has(e.kind)) return null;
  const id = encodeURIComponent(e.subject_id);
  return { document: `#/doc/${id}`, check: `#/h/${id}`, themes: `#/themes/${id}`, codebook: `#/codebooks/${id}` }[e.subject_kind] || null;
}

// One entry's words and what it is about, the same on the page and in the drawer (docs/DESIGN.md 4.20): the item's
// name is its title link, with no separate "Open". In an entry Margin wrote, the item's quoted name is the link
// ("Checked the hypothesis “Working from home…”"); where the words do not quote it, the item is named after "About:",
// as under your own entries, which stay your words (in serif).
const SUBJECT_WORD = { document: "the document", check: "the hypothesis", themes: "the themes", codebook: "the codebook" };
function quotedName(e) {
  const m = /“([^”]+)”/.exec(e.text || "");
  const name = (e.title || "").replace(/[.…]+$/, "").trim();
  return m && name && (name.startsWith(m[1].replace(/…$/, "")) || m[1].startsWith(name)) ? m : null;
}
export function entryText(e, href) {
  if (e.kind === "entry") return h("div", { class: "log-text log-own-text" }, e.text);
  const m = href ? quotedName(e) : null;
  if (!m) return h("div", { class: "log-text" }, e.text);
  const t = e.text;
  return h("div", { class: "log-text" }, t.slice(0, m.index), "“", link({ kind: "title", href }, m[1]), "”", t.slice(m.index + m[0].length));
}
export function entrySubject(e, href) {
  if (!href || (e.kind !== "entry" && quotedName(e))) return null;
  return h("span", { class: "log-subject" }, "About: ", link({ kind: "title", href }, e.title || SUBJECT_WORD[e.subject_kind] || "its item"));
}
// a colleague's entry: a person mark that stands alone (nothing else in the entry names them), so with the name
export function entryWho(e) {
  return e.mine ? null : personMark([e.who], { name: "short" });
}

export async function renderLog(view) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/log`;
  // 0.19.7: the page's head says what the log is; its downloads are the head's small quiet buttons (DESIGN.md 4.14)
  view.appendChild(pageHead("Research log", {
    eyebrow: featureEyebrow("researchlog"),
    sub: "What was decided in this project, and when. Margin writes down what happens; you add your own entries and say why.",
    actions: downloadLinks([
      { text: "Markdown (.md)", title: "The whole log, oldest first, a heading per day: for an appendix or an audit", onClick: () => download(`${base}.md`).catch(showError) },
      { text: "Excel (.xlsx)", onClick: () => download(`${base}.xlsx`).catch(showError) },
    ]),
  }));
  let group = session(`log-group:${project}`) || "";
  let q = "";
  let shown = PAGE;
  let shares = new Map();   // the sharing state of entries people wrote, by entry id
  let sharesStale = true;   // read once for the page; again only after a change that can alter it (a new entry, a share)
  const fresh = latest();   // the newest request of the list: an older answer never draws over it

  // ---- a new entry: one slim box, a line that grows to three while it has the focus or holds words, and its button
  const ta = textarea({ class: "log-new-text", rows: 1, maxlength: 10000, "aria-label": "A new entry",
    placeholder: "A decision, a reason, a field note…" });
  const addBtn = button({ kind: "main", title: "Ctrl/⌘ + Enter adds it", onClick: add }, icon("plus", { size: 14 }), "Add to the log");
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); add(); } });
  view.appendChild(h("div", { class: "log-new log-new-row" }, ta, addBtn));

  async function add() {
    const text = ta.value.trim();
    if (!text) { ta.focus(); return; }
    addBtn.disabled = true;
    try { await api("POST", base, { text }); ta.value = ""; toast("Added to the research log.", "ok"); sharesStale = true; await load(); }
    catch (e) { showError(e); } finally { addBtn.disabled = false; }
  }

  // ---- one row of tools (which entries, and words to find), and the list
  // a list to pick from, not a choice: up to nine groups, each with the entries it would show
  const show = select({ sm: true, id: "log-show" });
  const showLabel = h("label", { class: "log-show-label", for: "log-show" }, "Show");
  show.addEventListener("change", () => { group = show.value; session(`log-group:${project}`, group); shown = PAGE; load(); });
  const searchBox = searchField({ placeholder: "Search the log", "aria-label": "Search the log" });
  const search = searchBox.input;
  search.addEventListener("input", debounce(() => { q = search.value.trim(); shown = PAGE; load(); }, 250));
  const listBox = h("div", { class: "log-list", "aria-live": "polite" });
  view.append(h("div", { class: "log-tools" }, showLabel, show, searchBox), listBox);

  async function load() {
    const mine = fresh();
    let data, read = null;
    try {
      const qs = new URLSearchParams({ limit: String(shown) });
      if (group) qs.set("group", group);
      if (q) qs.set("q", q);
      [data, read] = await Promise.all([api("GET", `${base}?${qs}`), sharesStale ? sharingOf("log") : null]);
    } catch (e) { if (mine()) failedLoad(listBox, e); return; }
    if (!mine()) return;
    if (read) { shares = read; sharesStale = false; }
    drawShow(data);
    drawList(data);
  }

  // the groups that have entries, each with how many; the one chosen stays offered even when it has none left
  function drawShow(data) {
    const counts = data.groups || {};
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    const items = [["", "Everything", total]].concat(Object.entries(data.group_names)
      .filter(([g]) => counts[g] || g === group).map(([g, t]) => [g, t, counts[g] || 0]));
    show.replaceChildren(...items.map(([g, text, n]) => h("option", { value: g }, `${text} · ${plural(n, "entry", "entries")}`)));
    show.value = group;
  }

  function drawList(data) {
    clear(listBox);
    if (!data.entries.length) {
      listBox.appendChild(emptyState("notebook", q || group ? "No entry matches" : "Nothing in the log yet",
        q || group ? "Try other words, or choose Everything under Show." : "Entries appear as you work: add documents, check a hypothesis, find themes, or write the first entry above."));
      return;
    }
    let day = null, ol = null;
    for (const e of data.entries) {
      const d = fmt.dateShort(e.at);
      if (d !== day) {
        day = d;
        listBox.appendChild(h("h2", { class: "list-head log-day" }, new Date(e.at).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })));
        ol = h("ol", { class: "log-entries log-by-time" });
        listBox.appendChild(ol);
      }
      ol.appendChild(entryRow(e));
    }
    if (data.total > data.entries.length) {
      listBox.appendChild(h("div", { class: "more-row" }, button({ kind: "quiet", sm: true,
        onClick: () => { shown += PAGE; load(); } }, `Show more (${fmt.num(data.total - data.entries.length)} older)`)));
    }
  }

  // One entry, one row: the time, the group's icon, the words (a why under them, the quiet facts under that), and at
  // its end one More menu with what can be done to it (DESIGN.md 4.17, 4.20); no button stands under an entry
  function entryRow(e) {
    const href = subjectHref(e);
    const clock = new Date(e.at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
    const time = h("time", { class: "log-time", datetime: e.at, title: fmt.date(e.at) }, clock);
    const who = entryWho(e), about = entrySubject(e, href);
    // 0.18 (L1): an entry you wrote has its sharing state as a tag in its quiet line; Share and Unshare are in its menu
    const shared = e.kind === "entry" && e.mine ? shares.get(e.entry_id) : null;
    const share = shared ? shareTag(shared) : null;
    const meta = who || share || about || e.edited_at ? h("div", { class: "log-meta" }, who, share, about,
      e.edited_at ? h("span", { class: "muted" }, `edited ${fmt.dateShort(e.edited_at)}`) : null) : null;
    const why = e.why ? h("p", { class: "log-why" }, h("strong", {}, "Why: "), e.why) : null;
    const items = [];
    if (e.can_why && e.kind !== "entry") items.push({ text: e.why ? "Change why" : "Say why", icon: "quote", onClick: () => editWhy(e) });
    if (e.can_edit) items.push({ text: "Edit", icon: "type", onClick: () => editEntry(e) });
    if (shared && shared.can_change) {
      const on = shared.state === "shared";
      items.push({ text: on ? "Unshare" : shared.state === "withdrawn" ? "Share again" : "Share", icon: on ? "undo" : "users",
        title: on ? "Stop sending it to your colleagues (what they have stays with them)" : "Give it to your colleagues with your work",
        onClick: async () => { if (await (on ? unshareItem(shared) : shareItem(shared))) { sharesStale = true; load(); } } });
    }
    if (e.has_version && VERSION_KIND[e.subject_kind]) {
      items.push({ text: "Compare with before", icon: "history", title: "What changed since just before this, and Restore",
        onClick: () => compareVersion({ kind: VERSION_KIND[e.subject_kind], key: e.subject_id, versionId: e.version_id, onRestored: load }) });
    }
    if (e.can_edit) items.push("sep", { text: "Remove…", icon: "trash", danger: true, onClick: () => removeEntry(e) });
    const more = items.length ? menu({ class: "log-more", iconOnly: true, label: `More for the entry of ${fmt.date(e.at)}`, items }) : null;
    return h("li", { class: `log-entry log-${e.group}` + (e.kind === "entry" ? " log-own" : "") }, time,
      h("span", { class: "log-icon", "aria-hidden": "true" }, icon(GROUP_ICON[e.group] || "circle", { size: 15 })),
      h("div", { class: "log-body" }, entryText(e, href), why, meta), more);
  }

  async function editWhy(e) {
    const ta2 = textarea({ rows: 3, maxlength: 2000 });
    ta2.value = e.why || "";
    const r = await textDialog(`Why? ${e.text.length > 80 ? e.text.slice(0, 79) + "…" : e.text}`, ta2, "Save");
    if (r === null) return;
    try { await api("PUT", `${base}/${P(e.entry_id)}`, { why: ta2.value }); await load(); } catch (err) { showError(err); }
  }

  async function editEntry(e) {
    const ta2 = textarea({ rows: 5, maxlength: 10000 });
    ta2.value = e.text;
    const r = await textDialog("Edit your entry", ta2, "Save");
    if (r === null) return;
    try { await api("PUT", `${base}/${P(e.entry_id)}`, { text: ta2.value }); sharesStale = true; await load(); } catch (err) { showError(err); }
  }

  async function removeEntry(e) {
    if (!(await confirmDialog({ title: "Remove your entry?", message: "It is removed from the log here and, once your work is sent, from your colleagues' copies.", confirmText: "Remove" }))) return;
    try { await api("DELETE", `${base}/${P(e.entry_id)}`); sharesStale = true; await load(); } catch (err) { showError(err); }
  }

  await load();
}

async function textDialog(title, control, ok) {
  const r = await dialog({ title, body: h("div", {}, control), actions: [{ text: "Cancel", value: null }, { text: ok, value: true, primary: true }],
    onOpen: () => control.focus() });
  return r ? true : null;
}

