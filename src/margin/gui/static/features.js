// 0.9: one description of every feature, used by the sidebar, the Overview page and the page heads, so each feature
// says the same thing wherever it is shown: what it does, which part of the app it belongs to, and whether it needs
// the AI.
import { h, aiTag, tabs, plural } from "./lib.js";

// 0.13.6: `sub` and `compact`: the section's line and card size on the Overview (registry.js builds it from these)
export const SECTIONS = {
  explore: { title: "Explore the documents", short: "Explore", sub: "Start here: no hypothesis needed." },
  write: { title: "Your writing", short: "Write", sub: "Which claims of your draft the documents back, and whether the sources you cite say what you say.", compact: true },
  check: { title: "Check hypotheses", short: "Check", sub: "When you have a statement to test against the documents.", compact: true },
  project: { title: "Your project", short: "Project" },
  // 0.16: what you note and decide, kept as you work (notes and highlights, the research log)
  record: { title: "Your notes and decisions", short: "Notes", sub: "Kept as you work, with the date.", compact: true },
};

// ai: "none" (never uses the AI), "optional" (works without it; the AI can add to it), "uses" (the AI does the work).
// 0.13.6: `overview` (where its Overview card goes, or false), and an add-on's `state(o)` and `nav` (registry.js).
export const FEATURES = {
  sources: {
    section: "project", title: "Documents", icon: "book-open", href: "#/sources", ai: "optional",
    what: "Add your reports, papers and web pages, say who may read each with AI, and open one to read it with its codes, key terms and references, and see how it was read.",
    overview: { section: "explore", order: 99, title: "Read one document", what: "Open a document from the list to see its codes, key terms, what “it” and “they” refer to, how it was read beside its pages, and a highlighted copy." },
  },
  bibliography: {
    section: "project", title: "Bibliography", icon: "library", href: "#/bibliography", ai: "none",
    what: "Your Zotero library or a collection of it, matched with the documents: which works you have, which you still need to find, and which documents Zotero does not have.",
    overview: false,
  },
  // Margin: a one-page report on one document, no AI; a quick look (one file, no project to set up) lands on it
  skim: {
    section: "explore", title: "Skim", icon: "eye", href: "#/skim", ai: "none", nav: true,
    what: "A one-page report on one document: what it sets out to do and says it found, its key sentences, the claims it makes without a citation and the works it cites most.",
    use: "To skim a publication before deciding to read it, without setting up a project (Quick look).",
  },
  codebooks: {
    section: "project", title: "Codebooks", icon: "book-marked", href: "#/codebooks", ai: "optional",
    what: "Make and change your own codebooks: codes with a definition, when to use them and when not, the words they are matched by and examples from the documents. Start fresh or from the themes found.",
    use: "To code the documents with your own categories, and see before any AI labels what each code would pick.",
    overview: false,   // 0.17.0: a view of Codes, named on its card
  },
  search: {
    section: "explore", title: "Search", icon: "text-search", href: "#/search", ai: "none",
    what: "Every place a word or phrase occurs in the documents, one line per place, with the words around it.",
    use: "To see how the documents talk about something, or to find a passage you remember.",
  },
  profile: {
    section: "explore", title: "Codes by document", icon: "tag", href: "#/profile", ai: "optional",
    overview: { title: "Codes", what: "Which codes of your codebook each document addresses, how much and where. Make your own codebooks beside it." },
    what: "Which codes of your codebook each document addresses, how much, and where.",
    use: "To compare documents by topic and find the passages behind each code.",
  },
  concepts: {
    section: "explore", title: "Concepts", icon: "network", href: "#/concepts", ai: "optional",
    what: "A glossary of the terms the documents use, grouped into concepts you can follow from one document to the next.",
    use: "To see which words mean the same thing (abbreviations, other wordings) and where each concept appears.",
  },
  themes: {
    section: "explore", title: "Themes", icon: "shapes", href: "#/themes", ai: "optional",
    what: "What the documents are about, grouped into themes, by document and by code.",
    use: "For an overview of a set of documents before you form hypotheses.",
  },
  drafts: {
    section: "write", title: "Check a draft", icon: "file-pen", href: "#/drafts", ai: "uses", nav: true,
    state: (o) => (o.drafts ? [true, plural(o.drafts, "draft", "drafts")] : [false, "None yet"]),  // its Overview line
    what: "Marks the statements in your draft that need a source, and finds the documents that support or contradict each one.",
    use: "While you write: to see which claims your documents back, which they contradict, and what to cite.",
  },
  check: {
    section: "check", title: "Hypotheses", icon: "flask", href: "#/hypotheses", ai: "uses",
    what: "Check one statement or a list against the documents: whether they support or contradict each, with the exact quotes for you to judge. Every answer stays here, with the evidence map.",
  },
  batch: {
    section: "check", title: "Check several", icon: "list-checks", href: "#/hypotheses", ai: "uses",
    what: "A list of hypotheses (pasted or from a spreadsheet), checked one after the other: write them in the Hypotheses box, one per line.",
    overview: false,   // 0.17.0: a mode of Hypotheses
  },
  citations: {  // 0.13.7; Margin: with your writing, beside Check a draft (a draft's citations are checked there too)
    section: "write", title: "Check citations", icon: "quote", href: "#/citations", ai: "uses", nav: true,
    what: "Whether each source your draft cites says what your sentence says, with the excerpt that shows it.",
    use: "Before you submit: to catch a citation that does not back its sentence.",
  },
  outline: {  // roadmap C: a writing plan made from the themes, with no AI
    section: "write", title: "Outline", icon: "file-text", href: "#/outline", ai: "none", nav: true,
    what: "A writing plan made from your themes, around your research question and hypotheses (each holds the themes that bear on it) or from all of them, with key terms, best passages, the sources to cite and where they disagree.",
    use: "Before you write, or beside a draft: to see what each hypothesis has behind it, what each section needs and which sources it does not use yet.",
  },
  history: {
    section: "check", title: "Answers", icon: "history", href: "#/hypotheses", ai: "optional",
    what: "Every hypothesis checked in this project: the answers, your reviews, the evidence map and Excel downloads.",
    overview: false,   // 0.17.0: the answers are on the Hypotheses page
  },
  // Margin: online lookups that are not AI (OpenAlex, Crossref, Semantic Scholar, Unpaywall); sidebar entry via `nav`
  literature: {
    section: "write", title: "Find literature", icon: "search", href: "#/literature", ai: "none", nav: true,
    state: (o) => {
      const l = o.literature || {};
      return l.new ? [true, `${plural(l.new, "new work", "new works")} on your saved searches`]
        : l.searches ? [false, `${plural(l.searches, "saved search", "saved searches")}, nothing new`] : [false, "Ready: search for works to cite"];
    },
    what: "Finds works to cite for the claims no document supports, the works your documents cite and those citing them, and what is new on a search you keep. Works you choose go to Zotero.",
    use: "When a claim needs a source you do not have yet.",
  },
  // 0.16 (F2, F4)
  annotations: {
    section: "project", title: "Notes", icon: "highlighter", href: "#/notes", ai: "none",
    what: "Your highlights and notes on exact words of the documents, in one searchable list. A note can be evidence in a check.",
    overview: false,   // 0.17.0: a view of Documents
  },
  researchlog: {
    section: "project", title: "Research log", icon: "notebook", href: "#/log", ai: "none",
    what: "A dated record of what was decided: documents added, checks made and dropped, themes removed, codebook changes. Add your own entries, say why, and go back to an earlier version.",
    overview: false,   // a place of the sidebar's Project group, and the drawer beside every page
  },
  // 0.18.1 part A (documents, theory, concepts): its features below this line
  // end of 0.18.1 part A
  // 0.18.1 part B (AI mix, checks, retractions): its features below this line
  retractions: {
    section: "project", title: "Retractions and corrections", icon: "alert-triangle", href: "#/bibliography", ai: "none",
    what: "Asks Crossref, when you press a button, whether the works of your bibliography and your documents have been retracted, corrected or flagged. Only DOIs are sent, and for a work of your bibliography without one its title, first author’s family name and year; works whose document is marked No AI, and your own drafts, are left out.",
    overview: false,   // a button and a warning on the Bibliography, and a mark on excerpts
  },
  agreement: {
    section: "project", title: "Agreement between routes", icon: "scale", href: "#/settings", ai: "uses",
    what: "On request, your local model and Claude answer the same sample of your own tasks of one kind, and Cohen's kappa says whether the local model is good enough for it. Only documents Claude may read go to Claude; nothing is stored.",
    overview: false,   // a box in Settings → AI, under the mix of local and Claude
  },
  // end of 0.18.1 part B
};

// The one AI mark (aiTag()) and a row's buttons with it (withAI()) are components: they live in lib.js with the other
// helpers (lib.js's own queue notice uses them), and are offered here too, where the pages have always found them.
export { aiTag, withAI } from "./lib.js";

// 0.17.0: the places of the sidebar, in its order, and the views each place has (tabs on its pages). A view is
// [key, label, href, icon]; its key is the FEATURES key of the page when there is one. `section` is the sidebar group
// (null: above the groups, the Overview only). `match` lists the routes (as their FEATURES/nav keys) that light it.
export const PLACES = {
  overview: { title: "Overview", icon: "grid", href: "#/overview", section: null,
    what: "Your project: what is made so far and where to go next.", views: [] },
  // the Project group: the project's own places (the documents, the research log; Margin has no team)
  documents: { title: "Documents", icon: "book-open", href: "#/sources", section: "project",
    what: "Your reports, papers and web pages: add them, read one, your notes on them, and your Zotero library.",
    views: [["sources", "Documents", "#/sources", "book-open"], ["annotations", "Notes", "#/notes", "highlighter"], ["bibliography", "Bibliography", "#/bibliography", "library"]] },
  researchlog: { title: "Research log", icon: "notebook", href: "#/log", section: "project",
    what: "A dated record of what was decided in this project; add your own entries and say why.", views: [] },
  search: { title: "Search", icon: "text-search", href: "#/search", section: "explore",
    what: "Every place a word or phrase occurs in the documents, one line per place.", views: [] },
  codes: { title: "Codes", icon: "tag", href: "#/profile", section: "explore",
    what: "Which codes of your codebook each document addresses, and your codebooks.",
    views: [["profile", "By document", "#/profile", "tag"], ["codebooks", "Codebooks", "#/codebooks", "book-marked"]] },
  concepts: { title: "Concepts", icon: "network", href: "#/concepts", section: "explore",
    what: "A glossary of the terms the documents use, grouped into concepts, and a map of the concepts mentioned together.",
    views: [["concepts", "Glossary", "#/concepts", "type"], ["conceptmap", "Map", "#/concept-map", "network"]] },
  themes: { title: "Themes", icon: "shapes", href: "#/themes", section: "explore",
    what: "What the documents are about, grouped into themes.", views: [] },
  hypotheses: { title: "Hypotheses", icon: "flask", href: "#/hypotheses", section: "check",
    what: "Check one hypothesis or a list against the documents, and every answer with its quotes.",
    views: [["answers", "Answers", "#/hypotheses", "history"], ["map", "Evidence map", "#/map", "layers"]] },
};

// The tabs of a place's views, under its page title: the same component on every place (and in Settings).
export function viewTabs(place, current) {
  const p = PLACES[place];
  if (!p || !p.views.length) return null;
  return tabs({ class: "view-tabs", label: `${p.title}: views`, items: p.views, current });
}

// The line above a page title: which part of the app the page belongs to, and whether it needs the AI.
// 0.17.0: the part's short name, the same word as the sidebar's group ("Explore", "Check", "Project").
export function featureEyebrow(key) {
  const f = FEATURES[key];
  if (!f) return null;
  const sec = SECTIONS[f.section] || {};
  return h("span", { class: "feature-eyebrow" }, h("span", { class: "fe-section" }, sec.short || sec.title || ""), aiTag(f.ai));
}
