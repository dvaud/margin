# Margin roadmap

Where Margin is going: from a draft and evidence checker to a research manager and writing companion. Sections C
and E are built (Margin 0.10.0); the rest is not yet. Written 6 November 2026, after Margin 0.9.1; items move to `CHANGELOG.md` as they are built.

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

**Where it is built.** *Margin*: Margin's own code. *ENLENS candidate*: useful to both apps, or it changes code Margin
shares with ENLENS (`ingest.py`, `terms.py`, `routing.py`, `llm.py`, the task queue). Build it in ENLENS and bring it
in with `tools/sync_enlens.py`, so it is not built twice and syncs do not conflict.

## Suggested order

1. **Text you can trust**: parsing and display (A), and the measurements that optimisation starts from (H1).
2. **Close the writing loop**: citations written back into Word, reference lists in any style, the reference-list
   check, re-checking only what changed, retractions (B).
3. **From corpus to structure**: the outline from themes, the literature matrix, better concepts (C, D).
4. **Finding and reading**: literature for unsupported claims, following citations, notes and Zotero annotations,
   the research log (E, F).
5. **The rest of the writing companion and the AI mix**: reviewer pass, synthesis, QDPX export, local and cloud
   mix (G, I).

Optimisation (H) is ongoing: a little in every release. The release pipeline, documentation and ENLENS sync
(J) start early, alongside step 1, because every later release of both apps is easier with them: see *Order for J
as a whole* at the end.

---

## A. Text parsing and display

Today text from PDFs often runs together, tables come out garbled, and a passage can hold material that matters in
the paper but not in Margin (running heads, affiliations, licences, funding, line numbers, captions). Bad text costs
everywhere: search finds noise, themes form around boilerplate (the *Remove theme* feature exists partly because of
this), labels and checks read junk, and quotes fail to place.

**A1. Layout-aware reading of PDFs** · Level 0, Level 1 optional · ENLENS candidate (`ingest.py`)
- Use the positions pdfminer gives (the `pdfminer` extra) to find columns and reading order, so two columns are not
  read across as one line.
- Join lines broken mid-sentence and hyphens split over lines; split words that run together (`ofthe`,
  `climatechange`) with the corpus's own vocabulary as the dictionary.
- Repair the text layer: ligatures (ﬁ, ﬂ), odd spaces, soft hyphens, broken Unicode.
- Optional local programs for hard cases: GROBID (a local server: sections, references, figures) or Docling. Used
  when installed, never required.

**A2. Know what each part of a document is** · Level 0 · ENLENS candidate
- Classify every block: body text, heading, abstract, front matter (authors, affiliations, emails, received and
  accepted dates), back matter (acknowledgements, funding, conflicts of interest, author contributions, data
  availability, licence, "Downloaded from…"), caption, table, footnote, references, page furniture (running heads
  and page and line numbers, found by repeating across pages).
- Rules from position, font size, repetition and keyword cues; no model.
- By default only body text, headings, the abstract and (for checks) captions become passages. The rest is kept,
  not deleted: shown greyed out, searchable on request, and used where it helps (the reference list for citations,
  the affiliations for the bibliography).

**A3. Tables as tables** · Level 0, Level 1 optional · ENLENS candidate
- Find tables from aligned text positions (as pdfplumber does) and keep them as rows and cells, with their caption.
- A table is shown as a table, can be downloaded for Excel, and is left out of passages unless you include it (a
  table read as prose is what makes most of today's garbled passages).
- GROBID or Docling, when installed, for tables the rules cannot rebuild.

**A4. A clean reading view** · Level 0 · Margin first, then ENLENS
- The document page shows the text as a clean reflowed article: headings, paragraphs, tables, captions apart, page
  markers in the margin, and what was set aside folded under *Left out of the text*.
- Side by side with the original page (an image of the PDF page via `pypdfium2`), so you can see what the parser
  did.
- *Restore* on any block that was left out wrongly; *Leave out* on one that should not count. Your corrections are
  kept and applied again when the document is read anew.

**A5. A reading report per document** · Level 0 · ENLENS candidate
- How well the document was read: share of text recovered, columns found, words repaired, blocks left out by kind,
  tables found, pages that needed OCR. A warning on documents that read badly, before they spoil a check.

## B. Close the writing loop

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

**B5. Retractions and corrections** · Level 0 (online lookup, not AI) · ENLENS candidate
- Check every work in the bibliography and every cited work against Crossref's Retraction Watch data; warn on the
  claim's card and in the bibliography.

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

## D. Connecting concepts

**D1. A concept map** · Level 0 · ENLENS candidate (`terms.py`, the Concepts page)
- A graph of the concepts that occur together in passages (weighted by how much more often than by chance, such as
  PMI, not by raw counts), clustered, with the links you and the AI accepted drawn in their types (same, broader,
  narrower, related, needs, shapes, clashes with). Filter by document, theme, code or year.

**D2. Relations found from the text** · Level 0 · ENLENS candidate
- Propose links from the sentences themselves, without AI: "X such as Y", "Y and other X" (broader and narrower),
  "X, also called Y" (the same), "X leads to / causes / reduces Y" (an effect), "X instead of Y" (replaces). Each
  proposal comes with its sentences; you accept or reject it as you do now.

**D3. Paths between two concepts** · Level 0 · ENLENS candidate
- Pick two concepts and see how the documents get from one to the other: the chain of concepts between them, and
  for each step the passages that join them (the bridge passages). This is a way into an argument the corpus already
  makes.

**D4. Concepts over time and across groups** · Level 0 · ENLENS candidate
- How a concept's wording and its neighbours change by publication year (from the bibliography) or between groups of
  documents you define (policy against academic, one country against another).

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

**F1. A reading queue** · Level 0 · Margin
- To read, reading, read, key source, set aside; with how far you got.

**F2. Notes and highlights on passages** · Level 0 · ENLENS candidate
- Your own notes tied to exact words of a document, searchable, and usable as evidence for a claim (quote-checked
  like everything else).

**F3. Zotero annotations** · Level 0 · Margin
- Bring in the highlights and notes you made in Zotero's PDF reader and show them in place.

**F4. The research log** · Level 0 · ENLENS candidate
- A dated record of decisions (codebook changes, claims dropped and why, themes removed, documents added), kept by
  itself, with room for your own entries. Valuable for reflexivity in qualitative work, and as an audit trail.

**F5. History inside the app** · Level 0 · ENLENS candidate
- Versions of a project you can go back to: drafts (with what changed between them), codebooks, theme sets,
  decisions and reviews. *Compare with an earlier version* and *Restore*, with the research log (F4) as their story.

## G. The rest of the writing companion

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

**G5. Export to NVivo and ATLAS.ti** · Level 0 · ENLENS candidate
- Codes, labels, quotes, memos and your decisions as a REFI-QDA (`.qdpx`) project.

## H. Optimisation across the board

**H1. Measure first** · ENLENS candidate
- A benchmark on a large corpus (several hundred PDFs) that times reading documents, search, terms, themes, the
  profile and page loads, and counts AI tasks and their size per feature. Run it each release; optimise what it shows.

**H2. Faster search** · Level 0 · ENLENS candidate
- A SQLite FTS5 index (in Python's own `sqlite3`) instead of scanning passages, kept up to date as documents come
  and go.

**H3. Recompute only what changed** · Level 0 · ENLENS candidate
- Adding one document should not redo terms, embeddings, profiles or themes for all of them: cache by passage hash
  and update incrementally.

**H4. Fewer and smaller AI tasks** · Level 0 · ENLENS candidate
- Screen passages on this computer (keywords, embeddings, rules) so the AI reads only those that can matter; never
  ask twice for the same passage, prompt and model (cache by hash); send small codebooks once per batch, not once
  per passage. Every AI task avoided is faster, cheaper and more private.

**H5. A lighter page** · Level 0 · ENLENS candidate
- Long lists (passages, search lines, claims) load as you scroll; heavy views compute in the background with
  progress; startup kept short.

**H6. Tidier code** · ENLENS candidate
- Split the largest modules (`claimcheck.py` is about 2,500 lines) along the features they serve, so later changes
  stay small and syncs conflict less.

## I. A mix of local and cloud AI

Today one route (Claude Code, the Claude API or a local model) answers every task, and each document's AI setting
limits what may go to Claude. A mix would use a local model where it is good enough and Claude only where it is
needed. · ENLENS candidate (`routing.py`, `llm.py`, the task queue)

**I1. A route per kind of task**
- In *Settings → AI*: for example labels, links and theme names on the local model; checks and second opinions on
  Claude. Presets: *Mostly local*, *Balanced*, *Best quality*.

**I2. Step up only when unsure**
- The local model answers first; when it is unsure (the certainty Margin already measures), the quote check fails,
  or its answer would change a decision, the task goes to Claude, but only for documents Claude may read. Otherwise
  it goes to a larger local model or waits for you.

**I3. Each document's setting, per task**
- A task's passages decide its route: a check over documents with mixed settings sends to Claude only the passages
  Claude may read, and the rest to the local model, with the result saying which route read what.

**I4. When the plan's limit is reached**
- Carry on locally, or wait and continue later, as you choose, instead of stopping.

**I5. Agreement between routes**
- A sample of tasks answered by both routes, with their agreement (kappa, which Margin already computes), so you can
  see whether the local model is good enough for each kind of task on your own corpus.

## J. Version control, releases, documentation and the ENLENS sync

How real products handle these, and what ENLENS and Margin would take from them. This is developer work: no AI is
involved. J1 and J2 apply to **both apps**; J3 (the sync) and J5 are Margin's only, J4 is ENLENS's only. When J is
built, both release guides change with it: the shared steps go into the main ENLENS guide (Part A of the
`margin-release` skill), so Margin's Part B shrinks to what is truly Margin's.

### J0. One pipeline, two products

ENLENS and Margin get **the same pipeline**: the same workflows, the same `tools/release.py` commands, the same
changelog fragments, documentation checks, branch names and steps. What differs is held in one short **product
profile** per app (the same file that J3 stage 2 introduces for the app's name, folders and port), plus each app's own
README and changelog. So:

- **Built once, in ENLENS.** The pipeline is shared code like any shared feature: built in ENLENS first and brought
  into Margin by the sync. Margin never edits the shared pipeline files; it changes only its profile, which the sync
  leaves alone (as it does `README.md` and `CHANGELOG.md` today).
- **The same habits.** A release is the same few commands in either repository, so switching between them needs no
  thought, and a fix to the pipeline reaches both.
- **Recognisably distinct.** Different names, looks, version numbers, release pace and, above all, audiences:

| | **ENLENS**: for scientists who rely on it | **Margin**: David's own companion |
| --- | --- | --- |
| Who the releases serve | researchers using it in their work, and those who read or review that work | David, to see what is going on |
| Pace | careful: a release candidate before each minor release, in use for at least a week | as fast as useful: release when ready, release candidates optional |
| CI | public repository: free minutes, all three systems on every push, required checks before merging | private: Linux on every push, three systems on release tags, checks advisory |
| Release notes | plain language, grouped: *New*, *Changes that can alter your results*, *Fixed*, *Privacy* | short: what changed, what came from ENLENS, what is next |
| README | a front door for scientists: what it does, install, how to cite, privacy, the manual | a short front page and the overview of J5 |
| Extras | J4: citable versions, results you can trust across versions, a validation report, methods and privacy documents | J5: an overview of both apps and the roadmap |

### J1. A release pipeline (both apps)

**Now.** In both apps, pushing a tag `vX.Y.Z` runs `release.yml`: check that the versions agree, run the tests,
build the wheel, try the one-line install on Linux, Windows and macOS, then make a draft release that a person
publishes. That is a sound base (checksums, an install test, a person in the loop). The gaps are between
releases: nothing tests a push to `main`, so a broken commit shows up only at release time; the version is typed in
three places; the tests are renamed at every release; and there is no way to try a release before everyone gets it.

**How real products do it, and the plan:**

1. **Continuous integration (CI) on every push.** A second workflow, `ci.yml`, runs the tests and a linter (`ruff`) on
   every push and pull request, on Linux, with the oldest and newest Python Margin supports (3.10 and 3.13). The full
   three-system install test stays on release tags. *Why*: a fault is found the hour it is made, while it is cheap
   to fix. Which systems run on a push is a profile setting: ENLENS is public, so its standard Actions minutes are
   free and all three systems can run on every push; `dvaud/margin` is private, so its minutes are limited (macOS
   minutes count ten times): Linux on pushes, all three systems on release tags.
2. **Work on branches, merge through pull requests.** Each feature gets a branch (`feature/word-citations`) and a
   pull request into `main` that CI must pass. Merge with *squash*, so `main` keeps one commit per feature. *Why*: even
   alone, `main` then stays releasable, and each change has a record of what and why. ENLENS, being public, can
   require the checks to pass before a merge (a branch ruleset); for the private Margin that needs GitHub Pro, and
   without it the habit and CI's red mark do the job.
3. **One version number, from the tag.** The version comes from the git tag (`setuptools-scm`, which fits
   Margin's setuptools build), and `margin.__version__` reads it from the installed package (`importlib.metadata`).
   *Why*: nothing to bump by hand, and `release.py check` has one thing less to compare. The changelog heading stays
   written by hand.
4. **Changelog fragments.** Each change adds a small file, `changes/<topic>.md`, instead of editing `## Unreleased`;
   the release step joins them into the new `## X.Y.Z` entry and deletes them (as `towncrier` or `scriv` do).
   Prose written for researchers stays as it is. *Why*: two branches, or a branch and an ENLENS sync, never edit the
   same lines of `CHANGELOG.md`, which ends a common source of merge conflicts.
5. **A release pull request.** `python tools/release.py prepare` decides nothing but does all the typing: it
   collects the fragments into the changelog, updates *New in* in the README (J2), and opens a pull request
   "ENLENS X.Y.Z" or "Margin X.Y.Z". Merging it tags the commit, and the tag starts `release.yml` as now. *Why*: the
   release is reviewed as one change before it exists (the pattern of `release-please`, without its commit-message
   rules).
6. **Pre-releases and a beta channel.** `v0.10.0rc1` makes a GitHub pre-release. *Settings → Technical → Updates*
   gets *Stable* (the default) and *Try new versions early*, and the update button follows the chosen channel. *Why*:
   a release is used on your own computer for a few days before everyone else gets it. ENLENS's profile requires a
   release candidate before every minor release; Margin's does not.
7. **Repeatable installs.** A `uv.lock` file pins every dependency that CI and the install use, and Dependabot opens a
   pull request when a dependency or a GitHub Action has a new version. Actions are pinned by their commit hash, not
   a moving tag. *Why*: the same release builds the same way next month, and an update is a change you see.
8. **Provenance.** `actions/attest-build-provenance` records which workflow and commit built each release file
   (next to the `SHA256SUMS` there already), so anyone can check a wheel came from this repository.
9. **After publishing.** A job installs from the published release with the real install line on all three
   systems, and runs once a week too (the macOS runners that hold up releases are tested then, not on release day).
   *Why*: the draft test cannot catch a fault in what the public install line downloads.
10. **Rolling back.** A short runbook in `docs/DEVELOPING.md`: a bad release is marked as a pre-release so "latest"
    falls back to the one before, the update button skips it, and the fix follows as a patch release.
11. **Tests named by topic, not version.** `tests/test_word_citations.py` rather than `test_m0_10_0_…`, never renamed.
    *Why*: renaming at every release is churn, and a test's name should say what it guards. Existing files keep their
    names.

**Order:** 1, 3, 4 and 11 first (small, and the others build on them); then 2, 5 and 7; then 6, 8, 9 and 10.

### J2. README and documentation (both apps)

**Now.** Both READMEs have the same layout (Margin's about 320 lines, ENLENS's about 350), set by the main release
guide. *Install* and *Update* are clear, but the *New in* section and *Earlier releases* repeat `CHANGELOG.md`;
*Exploring the documents*, *What a check does*, *A model per task* and *Privacy* repeat `docs/MANUAL.md`; and the git
copy and the *Layout* table are for developers in the middle of a page for researchers. Each release edits text in
two or three places, and they drift apart.

**How real products do it.** The README is the front door: what it is, a picture, how to install, where to go
next. Release notes live in the changelog and the GitHub Release. Documentation is written once and linked, never
copied, and often arranged by what the reader needs (the Diátaxis split: tutorials to learn, how-to guides for a
task, reference to look up, explanations to understand). Contributor material lives in its own file.

**The plan:**

1. **A README of about 100 lines, written for its audience** (each app's README stays its own and is not synced):
   - *ENLENS*, for scientists: one line on what it is and a screenshot; *Install*; *Update*; *What ENLENS does* (six
     or so bullets, each linking to its manual section); *New in 0.X* (three to five bullets, with whether they can
     change results); *How to cite ENLENS* (J4); *Privacy and your documents* in one paragraph, linking to the privacy
     statement; links to the manual and methods; *For developers* as a link.
   - *Margin*, for David: one line on what it is; *Install*; *Update*; *New in 0.X*; *What Margin adds to ENLENS*
     (its own features, a few lines); *Where things stand* (J5); *For developers* as a link.
2. **No copies.** *Earlier releases* leaves the README (the changelog and GitHub Releases hold them). The feature
   descriptions move into the manual, where they mostly are already. Margin's manual keeps coming through the sync
   with its own sections added, so it costs no extra writing.
3. **`docs/DEVELOPING.md`** for developers: the git copy, the *Layout* table, tests, the dev server, the release
   (J1) and the ENLENS sync (J3). `docs/EXTENDING.md` stays for add-ons.
4. **The manual in parts:** *Getting started* (a first project, start to finish), a how-to page per feature,
   reference (settings, the command line, the API) and explanations (privacy, how a check works, limits). Optionally
   published as a site (MkDocs on GitHub Pages) built by CI.
5. **Generated, not copied:** `release.py prepare` writes *New in 0.X* from the changelog; the app's *What's new*,
   shown once after an update, reads the same entry.
6. **Checked by CI:** links between documents resolve; every feature in `features.js` has a manual section; the
   README's *New in* matches the changelog.

Items 3 to 6 are shared files, built in ENLENS and synced. The README order in the main release guide (Part A)
changes to ENLENS's new one; Margin's order goes into Part B.

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

### J4. ENLENS for scientists (ENLENS only)

What a tool needs when its users publish with it, review with it, or have to justify it to an ethics board.

1. **Citable versions.** A `CITATION.cff` file (GitHub then shows *Cite this repository*) and a DOI for every release
   through Zenodo's GitHub link, so a paper can cite the exact version it used. The README's *How to cite ENLENS*
   gives both.
2. **Results you can trust across versions.** Each release note says, under *Changes that can alter your results*,
   whether the same documents can now give different answers (a new parser, as A1 would be; a new prompt, model or
   rule). Every result already records how it was made; it also records the ENLENS version, and a project opened in a
   newer version says which of its results were made with an older one. Old results stay readable.
3. **A validation report per release.** The parts that need no AI (reading documents, search, terms, themes, their
   determinism) are measured by the release workflow on the demo and pilot corpora; figures that need AI come from a
   recorded, dated run. The report goes with the release notes, so a change in accuracy is seen, not guessed.
4. **Methods and privacy documents.** `docs/METHODS.md`: how a check, labels, concepts and themes work, with their
   references, written so it can back a methods section. `docs/PRIVACY.md`: what leaves the computer, when, to whom,
   and what never does, written for ethics applications and data protection assessments.
5. **Reporting a problem without knowing GitHub.** Issue forms in plain language (what you did, what you expected,
   and the app's technical details pasted with one button), a contact for privacy and security problems
   (`SECURITY.md`), and a note on which versions get fixes.
6. **Changes announced ahead.** A feature that is removed or works differently is announced one minor release
   before, in the notes and in the app.

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
