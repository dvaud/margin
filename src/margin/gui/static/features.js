// 0.9: one description of every feature, used by the sidebar, the Overview page and the page heads, so each feature
// says the same thing wherever it is shown: what it does, which part of the app it belongs to, and whether it needs
// the AI.
import { h, icon, plural } from "./lib.js";

// 0.13.6: `sub` and `compact`: the section's line and card size on the Overview (registry.js builds it from these)
export const SECTIONS = {
  explore: { title: "Explore the documents", short: "Explore", sub: "Start here: no hypothesis needed." },
  write: { title: "Your writing", short: "Write", sub: "Which claims of your draft the documents back, and whether the sources you cite say what you say.", compact: true },
  check: { title: "Check hypotheses", short: "Check", sub: "When you have a statement to test against the documents.", compact: true },
  project: { title: "Your project", short: "Project" },
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
    section: "explore", title: "Skim", icon: "eye", href: "#/skim", ai: "none",
    what: "A one-page report on one document: what it sets out to do and says it found, its key sentences, the claims it makes without a citation and the works it cites most.",
    use: "To skim a publication before deciding to read it, without setting up a project (Quick look).",
  },
  search: {
    section: "explore", title: "Search", icon: "text-search", href: "#/search", ai: "none",
    what: "Every place a word or phrase occurs in the documents, one line per place, with the words around it.",
    use: "To see how the documents talk about something, or to find a passage you remember.",
  },
  profile: {
    section: "explore", title: "Profile", icon: "tag", href: "#/profile", ai: "optional",
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
    section: "write", title: "Check a draft", icon: "file-pen", href: "#/drafts", ai: "uses",
    state: (o) => (o.drafts ? [true, plural(o.drafts, "draft", "drafts")] : [false, "None yet"]),  // its Overview line
    what: "Marks the statements in your draft that need a source, and finds the documents that support or contradict each one.",
    use: "While you write: to see which claims your documents back, which they contradict, and what to cite.",
  },
  check: {
    section: "check", title: "Check a hypothesis", icon: "flask", href: "#/check", ai: "uses",
    what: "Whether the documents support or contradict one statement, with the exact quotes for you to judge.",
  },
  batch: {
    section: "check", title: "Check several", icon: "list-checks", href: "#/batch", ai: "uses",
    what: "A list of hypotheses (pasted or from a spreadsheet), checked one after the other.",
  },
  citations: {  // 0.13.7; Margin: with your writing, beside Check a draft (a draft's citations are checked there too)
    section: "write", title: "Check citations", icon: "quote", href: "#/citations", ai: "uses",
    what: "Whether each source your draft cites says what your sentence says, with the excerpt that shows it.",
    use: "Before you submit: to catch a citation that does not back its sentence.",
  },
  outline: {  // roadmap C: a writing plan made from the themes, with no AI
    section: "write", title: "Outline", icon: "file-text", href: "#/outline", ai: "none",
    what: "A writing plan made from your themes, around your research question and hypotheses (each holds the themes that bear on it) or from all of them, with key terms, best passages, the sources to cite and where they disagree.",
    use: "Before you write, or beside a draft: to see what each hypothesis has behind it, what each section needs and which sources it does not use yet.",
  },
  history: {
    section: "check", title: "Results", icon: "history", href: "#/history", ai: "optional",
    what: "Every hypothesis checked in this project: the answers, your reviews, the evidence map and Excel downloads.",
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
};

const AI_TEXT = {
  none: ["circle-check", "No AI needed"],
  optional: ["sparkles", "Works without AI; the AI can add to it"],
  uses: ["cpu", "Uses the AI"],
};

export function aiTag(ai) {
  const [ic, text] = AI_TEXT[ai] || AI_TEXT.none;
  return h("span", { class: `ai-tag ai-${ai}` }, icon(ic, { size: 12 }), text);
}

// The line above a page title: which part of the app the page belongs to, and whether it needs the AI.
export function featureEyebrow(key) {
  const f = FEATURES[key];
  if (!f) return null;
  return h("span", { class: "feature-eyebrow" }, h("span", { class: "fe-section" }, SECTIONS[f.section].title), aiTag(f.ai));
}
