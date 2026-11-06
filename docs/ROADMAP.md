# Margin roadmap

Where Margin is going: from a draft and evidence checker to a research manager and writing companion. Nothing here
is built yet. Written 6 November 2026, after Margin 0.9.1; items move to `CHANGELOG.md` as they are built.

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

Optimisation (H) and the version control workflow (J) are ongoing: a little in every release.

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

## J. Version control workflow

Two readings; both are listed until David says which he meant.

**J1. The developer workflow** · Margin and ENLENS
- Shared features built once in ENLENS and brought in, not built twice (as *remove a theme* was in 0.7).
- Margin's own code kept in its own modules (the add-on layer), so syncs touch Margin's files less often.
- `tools/sync_enlens.py` runs the tests itself, reports conflicts in plain words, and checks for leftover ENLENS names
  and colours.
- One command turns `## Unreleased` into a version (version bump, test renames, README sections) before the release
  check.
- A test run on every push to `dvaud/margin`, not only on release tags.

**J2. History inside the app** · Level 0 · ENLENS candidate
- Versions of a project you can go back to: drafts (with what changed between them), codebooks, theme sets,
  decisions and reviews. *Compare with an earlier version* and *Restore*, with the research log (F4) as their story.
