# Margin roadmap

Where Margin is going: from a draft and evidence checker to a research manager and writing companion. Written
6 November 2026, after Margin 0.9.1; items move to `CHANGELOG.md` as they are built. Sections C and E are built
(Margin 0.10.0), and C4 (Margin 0.14.0).

**Margin's own plans only.** On 10 November 2026 everything built in ENLENS (the ENLENS releases, the reader, concepts,
notes, the codebook editor, optimisation, the AI mix, the shared release pipeline and documentation, working
together) moved to ENLENS's roadmap: [`docs/ROADMAP.md` in ENLENS](https://github.com/dvaud/claim_checker_demo/blob/main/docs/ROADMAP.md). The items keep their letters in both files,
so A0 to A6, B5, D1 to D4, F2, F4, F5, G5, H, I, J0 to J2, J4, K, L, M and N are there.

## The rule: as little AI as possible

Margin should be a companion that a few prompts to a chatbot cannot replace: it keeps your corpus, your decisions
and your history; it gives the same answer twice; every step can be traced; and most of it runs on your computer
without any model. So every feature is built at the **lowest level that does the job well**:

| Level | What it means | Examples |
| --- | --- | --- |
| **0 · No AI** | Plain code: rules, statistics, text matching, the document's layout | search, C-value terms, k-means themes, kappa |
| **1 · Local program** | A program or library on this computer, still no language model | Tesseract, GROBID, an embedding model for search by meaning |
| **2 · Local model** | A language model on this computer (Ollama, LM Studio…) | labelling passages when no Claude may read them |
| **3 · Claude** | Only where 0–2 cannot do it well enough, and only for documents Claude may read | a hard check, a second opinion |

Each item below says its level. Where an item has an AI part, the AI part is optional, the rest works without it, and
what the AI says is still quoted, checked against the text and yours to overrule. Online lookups that are not AI
(OpenAlex, Crossref) still send words off the computer: they follow each document's AI setting and are switched off
by `--local-only`.

**Where it is built.** *Margin*: Margin's own code, listed here. Anything useful to both apps, or that changes code
Margin shares with ENLENS (`ingest.py`, `terms.py`, `routing.py`, `llm.py`, the task queue), is built in ENLENS and
brought in with `tools/sync_enlens.py`, so it is not built twice and syncs do not conflict: it is planned in
[ENLENS's roadmap](https://github.com/dvaud/claim_checker_demo/blob/main/docs/ROADMAP.md).

## Suggested order

1. **Close the writing loop**: citations written back into Word, reference lists in any style, the reference-list
   check, re-checking only what changed (B), and stronger claim finding without AI (B6).
2. **Finding and reading**: following citations and alerts (E2, E3), a reading queue and Zotero annotations (F1, F3).
3. **The rest of the writing companion**: the literature matrix, reviewer pass, counter-evidence and synthesis (G1
   to G4), and concepts in the writing (D5).
4. **The sync and the overview** (J3, J5), alongside the rest, as ENLENS's shared pipeline arrives.

What ENLENS builds comes in with each sync; see its roadmap for when.

---

## B. Close the writing loop

B5 (retractions) is built in ENLENS.

**B1. Citations written back into Word** · Level 0 · Margin
- Download the draft as `.docx` with a citation at every *cite here* you accepted, as Zotero citation fields where
  the work is in Zotero (so the Zotero Word plugin keeps managing them) and as plain text otherwise.

**B2. A reference list in any style** · Level 0 · Margin
- Full references, not only in-text citations, in any CSL style (APA, Harvard, Chicago, Vancouver, a journal's own),
  with a pure-Python CSL processor or Margin's own APA 7 code extended.

**B3. The reference-list check** · Level 0 · Margin
- Works cited in the text but missing from the list, listed but never cited, years or spellings that disagree,
  *2024a* and *2024b* that clash, and works without a DOI.

**B4. Re-check only what changed** · Level 0 (the comparison) · Margin
- Load a new version of a draft, or let Margin watch the file: it compares paragraphs, keeps every decision on
  unchanged claims, carries decisions over to lightly edited ones, and finds and checks claims only in what changed.
  Fewer AI tasks, and a draft you can keep open while you write.

**B6. Stronger claim finding without AI** · Level 0 · Margin
- Improve the rules that find claims for a draft marked *No AI* (numbers, causal verbs, comparisons, hedges, "studies
  show") so they are good enough that the AI pass is a refinement, not a necessity.

## C. An outline from the corpus's themes

**Built in Margin 0.10.0** (see `CHANGELOG.md`); kept here for what it was meant to do.

**C1. Outline from themes** · Level 0 · Margin
- Turn a set of themes into a writing outline: each theme becomes a section with its key terms, the passages that
  represent it best, the documents to cite (with APA citations), its codes and its concepts.
- A suggested order without AI: themes that share documents and terms sit next to each other (order by theme
  similarity, so the outline reads as a path rather than a list). Drag to reorder, merge, split, nest, and add
  sections of your own (introduction, methods) that no theme covers.
- Each section shows where the documents disagree (from the checks: support and contradiction side by side), the
  gaps (themes with few documents or one source only), and what you have already decided about its claims.

**C2. Outline and draft side by side** · Level 0, Level 1 optional · Margin
- As you write, each section shows how much of it the draft covers (key terms and sources the draft uses, or
  closeness by meaning with a local embedding model), and which sources and points are still unused.

**C3. Outline to a document** · Level 0 · Margin
- Download the outline as Word or Markdown: headings, notes, quotes with their place, and the citations, ready to
  write into.
- Optional (Level 2, then 3): a heading phrased for each section from its key terms. The outline is complete without
  it.

**C4. Outline from a research question** · Level 0, Level 1 optional · Margin · **Built in Margin 0.14.0**
- Start from a research question and optional hypotheses: each hypothesis holds the themes that bear on it (the
  passages its check counts, then shared key terms and concepts, then closeness by meaning with a local model);
  themes of the question only go under Background; the rest stay out. Each theme says why it is there.
- Later: research questions kept once per project, shared with *Find literature* and the literature matrix.

## D. Connecting concepts

D1 to D4 are built in ENLENS and come in with the sync.

**D5. Concepts in the writing** · Level 0 · Margin
- In a draft and in the outline, the concepts it uses are marked, with their wordings in the corpus, so you can see
  where your terms differ from your sources'.

## E. Finding literature

**Built in Margin 0.10.0** (see `CHANGELOG.md`); kept here for what it was meant to do.

**E1. Literature for unsupported claims** · Level 0 (online lookup, not AI), Level 1 optional · Margin
- For a claim no document supports: search OpenAlex, Crossref or Semantic Scholar with search words taken from the
  claim on this computer (key terms, concepts), rank the results by closeness with a local embedding model, find open
  copies through Unpaywall, and send the works you choose to Zotero.

**E2. Follow citations** · Level 0 (online lookup) · Margin
- The works your documents cite and the works that cite them, ranked by how many of your documents they connect to
  and how close they are to your themes.

**E3. Alerts on saved searches** · Level 0 (online lookup) · Margin
- New works on a saved search or on your research questions since you last looked.

## F. Reading and notes

F2, F4 and F5 are built in ENLENS (0.16.0) and come in with the sync.

**F1. A reading queue** · Level 0 · Margin
- To read, reading, read, key source, set aside; with how far you got.

**F3. Zotero annotations** · Level 0 · Margin
- Bring in the highlights and notes you made in Zotero's PDF reader and show them in place.

## G. The rest of the writing companion

G5 (export to NVivo and ATLAS.ti) is built in ENLENS.

**G1. Literature matrix** · Level 0 · Margin
- Sources down the side; research questions, codes, themes or concepts across the top; each cell the best checked
  quote, from what Margin already has. Download for Excel. The classic scaffold of a literature review.

**G2. Reviewer pass** · Level 0 · Margin
- Terms used inconsistently, abbreviations used before they are defined or never defined, numbers that differ
  between the abstract and the results, paraphrases too close to a source (word n-grams shared with the source
  passage), direct quotes that do not match their source or lack a page.

**G3. Counter-evidence your draft leaves unanswered** · Level 0, Level 1 optional · Margin
- From the checks already made: the contradicting passages, and whether the draft addresses them anywhere (matching
  terms, or closeness by meaning with a local embedding model).

**G4. What do my sources say about X** · Level 0, Level 2 or 3 optional · Margin
- Without AI: the quotes about X, grouped by stance and theme and ordered as an argument, each with its citation.
- With AI (local first): a short synthesis paragraph from those quotes only, each sentence carrying its citation and
  checked quote, marked as a scaffold to rewrite, not text to submit.

## J. The ENLENS sync and the overview

J0 (one pipeline, two products), J1 (the release pipeline), J2 (README and documentation) and J4 (ENLENS for
scientists) are built in ENLENS and planned in [its roadmap](https://github.com/dvaud/claim_checker_demo/blob/main/docs/ROADMAP.md). Margin's own parts:

### J3. Bringing in ENLENS's work (Margin only)

**Now.** `tools/sync_enlens.py` rewrites each new ENLENS commit with Margin's names (nine text substitutions such
as `ENLENS` → `Margin` and port 8765 → 8766), merges the result, and leaves conflicts to be resolved by hand;
`README.md`, `CHANGELOG.md` and the version lines are Margin's own. It works, but every ENLENS change to a file
Margin also changed can conflict, a text substitution can rename what it should not, a feature was built in both
apps (*remove a theme*, 0.7), and the `enlens` remote still has a push address.

**How real products do it.** Three patterns, from loosest to firmest:
- *A fork with its changes on top* (Linux distributions' patch sets, browsers built on Chromium): flexible, but every
  upstream release can conflict, and the work grows with the distance between the two.
- *Identity as configuration* (VSCodium builds Visual Studio Code's own code with its own `product.json` for name,
  folders and icons): the code is the same, so updates merge cleanly.
- *Upstream as a dependency* (apps built on a framework, with plugins): the derived product does not copy the code
  at all; it depends on a released version and adds its own parts through extension points. An update is a version
  bump.

ENLENS has the start of the second and third already: `brand.json`, the add-on module and the local layer
(`docs/EXTENDING.md`).

**The plan, in three stages:**

1. **Safer and calmer now** (Margin; small):
   - `git remote set-url --push enlens no-push`, so a push to ENLENS from this clone is impossible.
   - **Upstream first**: a fix or feature both apps need is built in ENLENS and brought in, never built twice.
   - Sync **ENLENS's release tags**, not whatever is on its `main`, on a branch `sync/enlens-X.Y.Z` with a pull
     request that CI must pass.
   - The tool runs the tests itself, compares the failures with those before the merge, lists leftover ENLENS
     names and colours, and explains each conflict in plain words.
   - A weekly workflow on `dvaud/margin` checks ENLENS (public) for a new release tag and opens the sync pull request
     by itself.
2. **ENLENS's identity as configuration** (ENLENS; medium): one *product profile* (app name, command names, the
   `*_HOME` style variables, the data folder, the port, the plugin's name) read in one place, and no "ENLENS"
   written into code or page text elsewhere (the page already uses `appName()`). The substitutions then shrink to
   the Python package name, and most sync conflicts go with them.
3. **Margin as ENLENS plus an add-on** (both; large, the end state): ENLENS publishes its package with each release;
   Margin becomes a package that depends on a pinned ENLENS version, brings its own features (drafts, citation
   checks, APA citations, the bibliography additions) as an add-on through the `extensions` entry point, and sets
   its profile and look. A sync is a version bump that Dependabot can propose, tested by CI. The price: Margin no
   longer edits ENLENS's code directly. What Margin needs from it becomes an extension point added in ENLENS first.

**Order:** stage 1 now; stage 2 in ENLENS next; stage 3 once ENLENS's extension points cover what Margin adds
(the list of Margin's changes to shared files, from `git diff` against the last synced ENLENS, shows what is
missing).

### J5. Margin as an overview (Margin only)

Margin is where David sees what is going on in both apps and in the plan, at a glance and without digging.

1. **`python tools/status.py`** (and the same text in the summary of each CI run): which ENLENS version Margin is
   built on and the ENLENS releases not brought in yet; what waits to be released (the changelog fragments); open
   branches and their CI state; the last release of each app and whether its after-publishing check passed; the
   roadmap's items by state.
2. **The roadmap keeps state.** Each item is marked *planned*, *in progress* or *done in X.Y.Z*; `status.py` counts
   them, and the release step marks the items a release finishes.
3. **One changelog for both.** Margin's release notes say *From ENLENS X.Y.Z* for what came in, so Margin's changelog
   reads as the log of both apps.
4. **About this version.** *Settings → Technical* says "Margin X.Y.Z, built on ENLENS A.B.C", with links to both
   changelogs.
5. **Lighter gates.** The macOS install test stays advisory, release candidates are optional, and a release can be
   made the day its work is done.

### Order for J as a whole

1. In ENLENS: J1 items 1, 3, 4 and 11, the product profile (J0) and J2 items 3 and 6. Sync them into Margin.
2. In Margin: J3 stage 1 and J5 items 1 and 2.
3. In ENLENS: J2's new README and the rest of J1, then J4 (citation first, as it is the smallest). Sync.
4. Both: J3 stage 2, then stage 3 when ready.
