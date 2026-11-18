// I7 stage 3 (ailog.py): the AI log. Who ran which AI work in this project, with which provider and model, when, about
// what, and how many excerpts left the computer for it; a colleague's rows arrive with the sync. A record, not a
// setting: reached from the Research log's line under its title (#/log/ai), never a sidebar entry. It looks like the
// research log (the same rows, grouped by day, docs/DESIGN.md 4.20), with two lists to pick from above it: the person
// and the provider. The item a row is about is its title link (a hypothesis, a codebook, themes, a document).
import { App, api, h, icon, clear, fmt, pageHead, P, button, select, link, personMark, emptyState, latest, plural, failedLoad, session } from "../lib.js";

const PAGE = 200;

export async function renderAiLog(view) {
  const project = App.project;
  const base = `/api/projects/${P(project)}/ai-log`;
  view.appendChild(pageHead("AI log", {
    back: { href: "#/log", text: "Research log" },
    sub: "Who ran which AI work in this project: with which provider and model, when, about what, and how many excerpts left the computer for it. In a team, your colleagues’ work arrives with the sync.",
  }));
  let person = session(`ailog-person:${project}`) || "";
  let provider = session(`ailog-provider:${project}`) || "";
  let shown = PAGE;
  const fresh = latest();

  const who = select({ sm: true, id: "ailog-person" });
  const prov = select({ sm: true, id: "ailog-provider" });
  who.addEventListener("change", () => { person = who.value; session(`ailog-person:${project}`, person); shown = PAGE; load(); });
  prov.addEventListener("change", () => { provider = prov.value; session(`ailog-provider:${project}`, provider); shown = PAGE; load(); });
  const listBox = h("div", { class: "log-list", "aria-live": "polite" });
  view.append(h("div", { class: "log-tools" },
    h("label", { class: "log-show-label", for: "ailog-person" }, "Person"), who,
    h("label", { class: "log-show-label", for: "ailog-provider" }, "Provider"), prov), listBox);

  async function load() {
    const mine = fresh();
    let data;
    try {
      const qs = new URLSearchParams({ limit: String(shown) });
      if (person) qs.set("person", person);
      if (provider) qs.set("provider", provider);
      data = await api("GET", `${base}?${qs}`);
    } catch (e) { if (mine()) failedLoad(listBox, e); return; }
    if (!mine()) return;
    drawPickers(data);
    drawList(data);
  }

  function drawPickers(data) {
    const all = (data.people || []).reduce((n, p) => n + p.n, 0);
    who.replaceChildren(h("option", { value: "" }, `Everyone · ${plural(all, "row")}`),
      ...(data.people || []).map((p) => h("option", { value: p.id }, `${p.me ? "You" : p.name} · ${plural(p.n, "row")}`)));
    if (person && !(data.people || []).some((p) => p.id === person)) who.appendChild(h("option", { value: person }, "Someone · 0 rows"));
    who.value = person;
    prov.replaceChildren(h("option", { value: "" }, "Every provider"),
      ...(data.providers || []).map((p) => h("option", { value: p.id }, `${p.title} · ${plural(p.n, "row")}`)));
    if (provider && !(data.providers || []).some((p) => p.id === provider)) prov.appendChild(h("option", { value: provider }, `${provider} · 0 rows`));
    prov.value = provider;
  }

  function drawList(data) {
    clear(listBox);
    if (!data.rows.length) {
      listBox.appendChild(emptyState("cloud", person || provider ? "No row matches" : "Nothing sent to a cloud AI yet",
        person || provider ? "Choose Everyone or Every provider above." : "A row appears each time AI work sends excerpts of this project’s documents to a cloud provider, yours or a colleague’s."));
      return;
    }
    let day = null, ol = null;
    for (const r of data.rows) {
      const d = fmt.dateShort(r.at);
      if (d !== day) {
        day = d;
        listBox.appendChild(h("h2", { class: "list-head log-day" }, new Date(r.at).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })));
        ol = h("ol", { class: "log-entries log-by-time ailog-rows" });
        listBox.appendChild(ol);
      }
      ol.appendChild(row(r));
    }
    if (data.total > data.rows.length) {
      listBox.appendChild(h("div", { class: "more-row" }, button({ kind: "quiet", sm: true,
        onClick: () => { shown += PAGE; load(); } }, `Show more (${fmt.num(data.total - data.rows.length)} older)`)));
    }
  }

  // One sending, one row: the time, the cloud icon, what was sent where (in words), and a quiet line: the person (a
  // colleague's mark), the kind of task, the model and route, and what it was about as a title link
  function row(r) {
    const clock = new Date(r.at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
    const time = h("time", { class: "log-time", datetime: r.at, title: fmt.date(r.at) }, clock);
    // a colleague's work they have not shared comes without their name (sharing._masked): "A colleague", no name
    const sender = r.person ? (r.person.me ? "You" : r.person.name)
      : (r.subject && r.subject.kind === "private" ? "A colleague" : "Someone (not recorded)");
    const docs = r.documents ? ` from ${plural(r.documents, "document")}` : "";
    const text = h("div", { class: "log-text" }, `${sender} sent ${plural(r.excerpts, "excerpt")}${docs} to ${r.provider_title}: ${r.kind_words}.`);
    const s = r.subject;
    const about = s ? h("span", { class: "log-subject" }, `${s.word || "About"}: `,
      s.href ? link({ kind: "title", href: s.href }, s.title || s.word || "open it") : (s.title || "not in this copy")) : null;
    const facts = [r.model ? `Model ${r.model}` : null, r.route ? `through ${r.route}` : null, r.answered ? "answered" : null].filter(Boolean).join(" · ");
    const meta = h("div", { class: "log-meta" },
      r.person && !r.person.me ? personMark([r.person.name], { name: "short" }) : null,
      facts ? h("span", { class: "muted" }, facts) : null, about);
    return h("li", { class: "log-entry ailog-row", dataset: { provider: r.provider } }, time,
      h("span", { class: "log-icon", "aria-hidden": "true" }, icon("cloud", { size: 15 })),
      h("div", { class: "log-body" }, text, meta));
  }

  await load();
}
