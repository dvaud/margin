# Changelog

## 0.13.0 (November 2026): a sounder check, and fewer surprises

From ENLENS 0.14.3 and 0.14.4: fixes from a review of the whole app. Five reviewers each took one part of ENLENS
(checking, privacy, the server and updates, exploring, the pages); most defects were reproduced before they were fixed,
and each fix has a test. Several **can change results**: each says so. ENLENS's fixes for shared projects are left out,
as Margin has no shared projects.

### Privacy

- **A local model's summary no longer reaches a Claude chat.** When your main AI was a model on this computer, the
  connector showed its summary of a check (and its "about another group" notes) to Claude, although it had read
  documents marked *Only a local AI*. Now they are shown only when the check read nothing but text Claude may read.
  **Can change what Claude is sent.**
- **Letting Claude read a document asks first.** Loosening a document's setting (to *Claude may read it*, or from *No
  AI* to *Only a local AI*) now asks before saving and shows the document's note; *Cancel* puts it back. Making a
  setting stricter stays instant.
- **The project zip leaves out removed documents.** *Download as a zip* took the whole uploads folder, so a document
  you had removed went along. Only the current documents' files and the codebooks go in now, and the download link
  no longer carries the app's access key in its address. **Can change exports.**
- **Glossary terms stay home.** With an embedding server on another computer, terms found only in documents kept from
  Claude are no longer sent to it.

### Checking a hypothesis

- **A check whose AI answers failed no longer says "No evidence found".** It says *The check did not work* and why;
  nothing the AI said in a failed search counts anywhere. Your own judgements of its excerpts are kept and count once
  another search of the check is answered. **Can change results.**
- **Excerpts that wait for your judgement are not "not about it".** A check of *No AI* documents now says *Waiting for
  your judgement* (result, Results list, map, Excel, connector), and the answer card says so beside any other caution.
  **Can change results.**
- **Excel says who really judged each excerpt** ("nobody yet", and why), and the *AI model used* column lists every
  model whose answers the check used. **Can change exports.**
- **A stricter quote check.** Quotes match whole words only ("legal" is not found in "illegal"), may not start or end
  inside a number, and a judgement's quote needs at least three words or 15 characters (prompts `check-v5`,
  `verify-v2`, `verify-set-v2`). Your own selections are widened to whole words. Stored results do not change.
  **Can change new checks.**
- **A local model's runaway answer no longer stops everything**: an answer cut off or stuck writing blank space is one
  failed try, asked again, and the check goes on.
- **The stronger model gets its own three tries** (it could get only two and then wait for good).
- The evidence map agrees with the Results list and is faster; *How these results were made* records the prompt
  version the model was actually given.

### Exploring the documents

- **A phrase finds only the phrase**: "the economy" no longer counts every "economy", and words typed beside a quoted
  phrase must be in the passage too. **Can change results.**
- **Highlights land where their words stand** in a highlighted copy, and short mentions match whole words.
- **The bibliography no longer renames a document after a work it cites.** A DOI links on its own only when it is in
  the file name or on the title page; otherwise the pair waits under *Please confirm*. Decisions and *Confirm all* are
  near-instant, matching is about four times faster, and BibTeX `@string` names are filled in. **Can change results.**
- **Theme edits follow their themes** (by the passages they share, not by theme number). **Can change results.**
- **A code you agreed with stays** after the AI reads the passage. **Can change results.**
- **Codebooks from European Excel**: CSVs with semicolons or in a Windows code page are read, and a codebook file that
  cannot be used is listed with the reason.

### Adding documents

- **One bad file no longer stops the whole add**: a password-protected or damaged zip, PDF or Word file is listed with
  the reason, and the rest are added.
- **Text in other code pages is read as written** (a Hungarian Notepad file, an old web page in Windows-1250 or
  -1252). **Newly added documents only.**
- *Stop* reaches the text recognition of a long scan; files picked during an add wait for the next one.
- **A damaged project zip is refused** with a plain message and leaves nothing in your projects.

### The app

- **Notes typed on a waiting result are kept** (the page no longer rebuilds while you type).
- **When Margin stops answering, a banner says so** and offers to reload.
- **One Claude Code run per project, stopped on Quit** and on *Update and restart*; a reopened app sees a run still
  going and can stop it (on Linux too).
- **The Claude Code plugin follows an update** of a one-line install.
- Smaller fixes: the Documents table shows *Open* and *Remove* under each title; a result of another project offers to
  switch to it; *Check several* skips lines too short to check; the *Let the auditor use Fable* switch saves at once;
  empty Search, Profile and Concepts say *Add documents first*; keyboard and contrast fixes (faint labels are easier to
  read); an update on disk no longer mixes the new page with the old code; the look for a new version cannot hang on
  a password prompt; on Windows, a user name with an accent works.

### For developers

- `.github/workflows/tests.yml` runs the tests on every push to `main`.
- `tools/dev_server.py` never finds the real Claude Code.

### In Margin

- The shared-project parts of these releases are left out (`sync.py`, `people.py`, the bring-in dialog, sync-clash
  notices, colleagues' judgements). Each excerpt's `my_verdict` is your verdict, and `judged_by` is "you" or null.
- The server's errors can carry extra fields again (`ApiError(extra=…)`), which the "result of another project" notice
  needs.
- Tests from ENLENS: `tests/test_0_14_3_check_status.py`, `test_0_14_3_explore.py`, `test_0_14_3_pages.py`,
  `test_0_14_3_privacy.py` (ENLENS's `…_privacy_and_sync.py` without its shared-project tests),
  `test_0_14_3_setup_and_update.py`, `test_0_14_4_runs_on_linux.py`. `test_m0_9_0_practice_codebook.py` now quotes
  whole words; `test_0_13_6_task_kinds.py` has the new prompt versions; `test_0_14_3_setup_and_update.py` fakes an
  older plugin as 0.1.0 (its 0.13.0 is this release).
- **Not yet done:** not tried with a real signed-in Claude Code or a real local model; the browser check covered
  Overview, Documents, Results, a result, Projects and Settings (light, dark, 390 px, no console errors).

## 0.12.3 (November 2026): /margin-run waits for its helpers

- **From ENLENS 0.14.2: the theme is a small icon beside Settings.** The *Theme: system* button at the foot of the
  sidebar no longer takes a row of its own: it is an icon at the end of the *Settings* row (a screen to follow your
  computer, a sun for light, a moon for dark). A click moves to the next one, as before; the tooltip says which is in
  use. On a short window the sidebar's foot needs one row less. Checked in light, dark and at phone width: Margin's
  paper look still wins. Tests: `tests/test_0_14_2_theme_icon.py`.
- **`/margin-run` brought up to date with current Claude Code.** Claude Code now starts helper agents in the
  background unless told otherwise, so the skill asks for them in the foreground: the helpers still work side by
  side, but the run waits for their reports before it looks at the queue again. Without this, the run Margin starts
  from the app (*Start Claude Code*) could end before its helpers had finished.
- **Every helper gets the group's model.** The skill used to pass a model only when it differed from a list of
  defaults written into it, and that list had fallen behind (no Fable for second opinions when switched on). It now
  always passes the model Margin names, so Margin's model table is the only place that decides.
- **Lighter and safer helpers.** Each helper skips your own `CLAUDE.md` (it answers from the task's text alone, and
  your notes cost tokens on every helper), stops after at most 40 turns instead of looping on a stuck batch (the
  batch goes back to the queue as before), and has its own colour in Claude Code's list of agents. The run itself
  works at low effort: it only hands out work.
- The skill reads its project and kind as named arguments, so a project name in quotes with spaces arrives whole.
- Tests: `tests/test_m0_12_3_modern_skill.py`. `claude plugin validate` passes on the written plugin.
- **Not yet done:** not tried with a real signed-in Claude Code on a real queue (the tests use the stand-in). Kept
  on purpose: the skill stays at the plugin's root rather than in `skills/margin-run/`, which Claude Code still
  supports for a one-skill plugin and which keeps ENLENS syncs clean.

## 0.12.2 (November 2026): claim cards without sideways scrolling, and a tidier foot

- **No more sideways scrolling in Claims.** One evidence quote whose PDF text had lost its spaces
  ("Socialpracticetheoryseesthepractice…") could not wrap, and the claims column grew to fit it: every card became
  wider than the pane and its right side (the status, the end of the claim) was cut off behind a sideways scrollbar.
  The column now never grows past the pane, and a word too long for a card breaks where it has to.
- **The card's buttons are sorted.** Six bordered buttons of equal weight sat in two loose rows. Now the foot of a
  card has the verdict as one switch of three (*Your verdict: Supported | Refuted | Dismiss*; press the chosen one
  again to take it back), then plain links for the ways on (*Find literature*, *Open the result*, or *Check this
  one* and *Reword* before a check), with *Fold* and *Remove* quiet at the far end. On a phone the switch takes the
  card's full width.
- Tests: `tests/test_m0_12_2_claim_card.py`; `test_m0_10_0_literature_page.py` now checks the hover colours of the
  Find literature link instead of the old button.
- **Not yet done:** checked in the browser (light, dark, 390 px, with a copy of the Tovertafel project's draft that
  showed the problem) but not on the Mac app window itself.

## 0.12.1 (November 2026): the local model waits for room, and the Mac install works again

Two fixes from ENLENS, and one ENLENS feature Margin leaves out.

### The local model shows itself, and waits for room (from ENLENS 0.13.11)

Found in an ENLENS user test: with Claude Code as the AI, a check whose key document was marked *Only a local AI*
loaded a 7.6 GB local model on a 16 GB Mac with 2.7 GB free, and the computer all but froze for minutes while the
page said only *Waiting for Claude Code*.

- **You see the local model at work.** While it reads its excerpts, the progress says so (*Your local model … is
  reading 3 excerpts from documents marked Only a local AI, on this computer*), with what it is doing and Stop. A
  check whose only waiting excerpts are the local model's says *Waiting for your local model* on the result, each
  part, the Results list and the map.
- **Not started without room for it.** Before the local model for restricted documents is loaded (Ollama), Margin
  compares what it needs with the memory free. When it clearly cannot fit, it is not started and says why and what to
  do; Claude's part of the check finishes and those excerpts wait. *Read them now* tries again, and *Start it anyway*
  lets you decide.
- **Memory given back.** A local model taking more than a third of the computer's memory is let go once it has read
  (once per set, for *Check several*), instead of staying loaded for 15 minutes.

Defects fixed on the way: taking waiting checks out of the queue removed a check whose local excerpts still waited,
Claude's answers included; the progress said excerpts *were read on this computer* when no local model could be used;
the steps of a queued check showed one poll late; a test could read your own `~/margin` settings.

API: `POST …/hypotheses/<id>/read-local` takes `{"force": true}`; results carry `status_text` *Waiting for your
local model*; jobs can end with `error_kind: "memory"`. `tools/dev_server.py --low-memory`.

### The one-line install works on a Mac again (from ENLENS 0.14.1)

Since 0.10.0 the one-line install stopped after its first step in most Mac Terminals: macOS's `sh` (bash 3.2) in a
UTF-8 locale read the ellipsis after `$VERSION` as part of the name and ended with "unbound variable". `install.sh`
is now plain ASCII. A failed install now ends as a failure, always removes its temporary folder, and stops at once on
Ctrl-C. A git copy (`margin update`) was not affected.

### Left out: working on a project together (ENLENS 0.14.0)

ENLENS 0.14.0 lets colleagues each keep a copy of a project and bring in each other's work (per-person judgements and
reviews, *sync clash* copies, `bring-in`). Margin is used by one person, so this is not needed for the foreseeable
future: the merge records ENLENS 0.14.0 as seen and takes none of its changes (no `sync.py`, `people.py` or new
tables), so later syncs bring in only ENLENS's later work. *Download as a zip* and *Import a project* stay as before.

**Tests added.** `tests/test_0_13_11_local_memory.py` (17, from ENLENS): the progress names the local model on Claude
Code and the Claude API; a queued check with no room ends once Claude Code is done, its local excerpts waiting, and
*Read them now* refuses until *Start it anyway*; Stop leaves them waiting; a large model let go and a small one kept;
a set loads the model once; withdrawing keeps a finished check; Ollama's memory check; *Waiting for your local model*
everywhere it shows. `tests/test_0_14_1_mac_install.py` (from ENLENS): `install.sh` is ASCII, the install line piped
into `sh` in UTF-8 locales, errors end as failures. Checked in the app with `tools/dev_server.py --mixed --claude-code
--low-memory`: the result page while the local excerpt waits, in light and dark and at 390 px.

**Not yet done.** Tried with stand-in models only; loading a real model with too little memory free was not repeated
on purpose. A local model on LM Studio or another OpenAI-compatible server is not checked for memory. The install fix
was tried for real on a Mac (macOS's `sh`, `en_US.UTF-8`, a scratch home folder, the release wheel): it installed.

## 0.12.0 (November 2026): your draft against itself

A draft is now also read against itself, without AI: where it may contradict itself, what is inconsistent in it, and
the claims a reader may find confusing.

### Your draft against itself

Check a draft compared each claim with the documents, but never the draft with itself: two sentences saying opposite
things, or the same figure given twice, went unnoticed unless a document happened to contradict one of them. A new
card on the draft page now reads the draft against itself, **without AI** (`consistency.py`), from its sentences and
what Margin already has for it: the claims found, their checks and your decisions.

- **May contradict each other**: two sentences about the same thing going opposite ways ("fell" / "rose",
  "effective" / "ineffective") or one saying "not"; the same statement with two numbers; one passage of a document
  counted for one claim and against another; two nearly identical claims with opposite answers or opposite
  decisions.
- **Inconsistent**: an abbreviation used before it is spelt out, or spelt out two ways; one word written two ways
  (UK and US spelling, "data set" / "dataset").
- **May confuse a reader**: a claim opening with "This …" and a verb, one hedged and absolute at once, several claims
  in one long sentence.

Contrasts drawn on purpose are left out ("However, …" close by, a view reported to be answered, two works cited for
the two sides, sentences naming different things, two different years), and so are the reference list, figure and
table captions, page headers, and a PDF's split words and removed line-break hyphens. Clicking a place highlights it
and the notice's other places in the draft; a claim's card names the notices it is in. **Not a problem** sets a
notice aside, and it stays aside while those sentences are the same. Tried on eight 40,000-word reports from PDFs:
about a second each, and four contradiction notices in all, each a pair worth a second look.

API: `GET …/drafts/<d>/consistency`, `PUT …/drafts/<d>/notices/<key>`; table `draft_notices`.

**Tests added.** `tests/test_m0_12_0_draft_itself.py` (18): opposite directions, "not" and "in-" opposites;
contrasts on purpose, a reported view, another place and two cited works left out; two numbers for one statement, two
years left out; page numbers and captions not read as numbers; abbreviations used early or spelt out two ways (a
heading and a PDF's stray space left out); spelling two ways, with names, the reference list, "large-scale" / "on a
large scale" and PDF artefacts left out; the three kinds of unclear claim, and the sentences rules pick before any
claim is found; opposite decisions; one passage on both sides of two checked claims; setting a notice aside, finding
it again and removing it with the draft; a 2,500-sentence draft; the API; the page files.

**Not yet done.** No AI reading of the pairs the rules find, or of contradictions worded too differently for them
(a local model would be the next level up). Abbreviations never spelt out are not flagged (too many are common
knowledge). The notices are not in the Excel or CSV download.

## 0.11.0 (November 2026): skim one document

Skim, a one-page report on one document that a quick look now lands on, made without AI; and Find literature's
styles back on a computer screen.

### Skim one document

For a publication you only want to skim: **Skim** (sidebar, first under *Explore the documents*; *Skim it* on every
document) is a one-page report on one document, and a **quick look** now lands on it, so there is no project to set up
(drop the file, read the report, keep or discard the quick look). Everything is made on this computer without AI
(Level 0): rules, counts and the document's own words. Nothing in it needs the other documents.

- **At a glance:** reading time, sections, works cited and claims without a citation; the abstract (under its heading,
  or a line starting with *Abstract*, without the keywords).
- **What it sets out to do, and what it says it found:** sentences in its own voice ("we", "this study", "our results
  show", "we conclude"); a plan ("we will describe") is not a finding. *Check a draft* skips these on purpose; a skim
  wants them first.
- **Key sentences:** an extractive summary: the sentences carrying most of its key terms, at most two per section, in
  reading order, with fewer that open with "it" or "they".
- **Claims about the world:** *Check a draft*'s rules (numbers, causes, comparisons, what research found, general
  claims), each with or without a citation. Those in its own abstract, data, methods or results are counted apart, as
  its evidence rather than claims to source, so *No citation* lists what leans on nothing.
- **Sections** with their length, **key terms**, the **works it cites most** (author-year and numbered citations), the
  DOIs in its reference list (*Follow its citations* on Find literature), and its **codes** when a codebook is chosen.
- Every item opens the document at its place, highlighted ("The place from the skim is highlighted"). *Markdown (.md)*
  downloads the report as notes. In a quick look, *Ask it something* leads to *Check a hypothesis* and *Search*.
- **Single-document versions.** Key terms in a project of one document were plain counts (TF-IDF has nothing to
  contrast with); they are now weighed by how far a term runs through the document (the share of its passages), with
  a little extra for longer terms. This also changes the *Key terms* panel of a quick look's document. Line breaks are
  rebuilt from the layout the document was read with, so a sentence never runs across a heading (a text file is stored
  with its breaks as spaces) and a PDF's line broken mid-sentence is one sentence. Passages the reading marked as
  references or unreadable, and lines with a web address or DOI, are left out, and so are lines of a contents page,
  figure captions, running heads glued to the text, rows of numbers and a footnote's number at a sentence's start
  (found by trying it on the pilot's 300-page reports). "USD (2019)" is not read as a citation.
- For developers: `src/margin/skim.py`, `GET /api/projects/<p>/documents/<id>/skim` and `…/skim.md` (`docs/API.md`),
  `views/skim.js`, the feature `skim` in `features.js`, routes `#/skim` and `#/skim/<doc>`, a *skim* section in
  `margin.css`. ENLENS candidate: the single-document weighting in `terms.key_terms`.

**Defects fixed on the way.** The Outline section of `margin.css` (0.10.0) left its phone-width block unclosed, so
every rule of *Find literature* after it applied only on screens 640 px wide or less: on a computer the page's tabs,
privacy box, works and saved searches were unstyled. Closed; the Literature page now looks as designed at every width.

**Tests added.** `tests/test_m0_11_0_skim.py` (12): a Markdown paper (abstract, aims and findings, no sentence across
a heading, every item's place and text), key sentences spread over sections and in order, claims with its own results
kept apart, works cited and the reference list, line breaks rebuilt, one document's key terms favouring a term that
runs through it (and the corpus contrast back with a second document), a document with little text, the Markdown copy,
the API with a quick look end to end, a PDF without headings whose reference entries and DOI line stay out, lines that
are not sentences, and the page files and docs. `test_0_13_6_page_extensions.py` lists Skim among the Overview's *Explore* cards; `test_m0_10_0_literature_page.py` no longer
expects 0.10.0 at the very top of the changelog.

**Not yet done.** Tried on Markdown and on the suite's small PDFs, not on a range of real publications: heading
detection in PDFs decides the sections and the abstract, and two-column layouts, footnotes or a reference list without
a heading may leak into the lists. The own-voice rules are English only. Citations in footnote style (Chicago notes)
are not read. Codes appear only when a codebook was chosen before the quick look (it runs the keyword pass then).
Nothing is cached: the report is made again on each visit (about half a second for a 300-page report, less for a
paper). On long reports without headings, key sentences and findings are noisier than on papers.

## 0.10.0 (November 2026): an outline from your themes, and finding literature

Two parts of the roadmap (`docs/ROADMAP.md`), both without AI: **Outline** turns your themes into a plan to write
from, beside your draft, downloadable as Word or Markdown (section C); **Find literature** looks for works to cite for
the claims your documents do not back, follows your documents' citations and keeps saved searches (section E).

### An outline from your themes

Roadmap section C. *Outline* (sidebar, under *Your writing*; also *Make an outline* on a set of themes) turns a set of
themes into a plan to write from, beside a draft if you like, and downloads it as Word or Markdown. It uses no AI
(Level 0; the optional embedding model is Level 1) and never sends anything off the computer.

- **C1, the outline.** A section for each theme: key terms, the passages that represent it best (one per document
  first, with their place), the documents to cite with an APA 7 in-text citation (when linked to the bibliography), the
  codes of a codebook and the concepts its key terms belong to. The order is a path: the theme with most passages
  first, then always the most similar theme not used yet (half the cosine of the passage counts per document, half
  the share of key-term words in common), improved by 2-opt; the same themes always give the same order, and each
  section says what it shares with the next. You drag a section (or use *Move up*, *Move down*, *Put inside the
  section above*, *Take out of its section*), merge, split (several themes back into themes; one theme by
  documents), rename, take out and bring back, add sections of your own and write notes; sections nest three levels
  deep. Each section shows where its documents disagree (the checks already made, support and contradiction side by
  side), gaps (no, one, two sources, mostly one source, few passages) and what you decided about the claims it
  touches. Headings use the AI's theme name when there is one (no new AI task), else your rename, else the key
  terms. The outline is stored in the project (`outlines`, `outline_sections`), survives a reload and the deletion of
  its set of themes (titles and notes stay), and several outlines per project are fine.
- **C2, beside a draft.** Each section says how much of it the draft covers (its key terms in your words, its sources
  among the works your citations name) and lists the sources, points and key terms still unused, and where the draft
  touches it. *Also by meaning* compares the draft's paragraphs with each section using the embedding model, only
  with one on this computer that has built the project's vectors; a model on another computer is never given the
  draft.
- **C3, a document.** *Word (.docx)* and *Markdown (.md)*: numbered headings, notes, key terms, the citation, quotes
  with their place, disagreements, decisions, gaps and the sources named. The .docx is written with `zipfile` (Title
  and Heading styles, no new dependency).
- For developers: twelve routes under `/api/projects/<p>/outlines` (`docs/API.md`), `margin/outline.py`, two new
  tables in `store.py`'s schema, `views/outline.js`, a feature entry and a route in the page, and *Outline* in the
  manual.

Defects fixed on the way: none found in existing code.

Tests: `tests/test_m0_10_0_outline.py` (22): the order puts similar themes together and 2-opt never makes the path
worse; sections, terms, passages, citations; several outlines and reopening; reorder, nesting, depth limit and cycles;
own sections, notes and titles; merge and split (by themes and by documents); taking out and bringing back; suggesting
the order again; an outline that outlives its themes and follows a merge or removal; disagreements, decisions, gaps and
APA from real checks; codes and concepts; beside a draft with and without a bibliography; closeness by meaning only
with a local, built model; Markdown, a well-formed Word package; the API end to end; the page files and the docs.

**Not yet done.** Dragging works with a mouse only (a phone has the arrow buttons); the .docx was checked as a package
and read back by Pandoc, but not opened in Word itself; closeness by meaning was tested with a stand-in embedding
model, not a real one; the outline's key terms, quotes and sources are not re-made when documents are added (find the
themes again and make a new outline); a reference list in full APA style waits for roadmap B (the outline names its
sources by title and in-text citation).

### Finding literature

Roadmap section E (E1, E2, E3): a new page, **Find literature** (under *Your writing*), for works your documents do not
have yet. It is not AI: it asks OpenAlex (and, if you choose, Crossref, Semantic Scholar and Unpaywall), and the words it
asks with are made on your computer and shown to you first.

- **Search for the claims no document supports (E1).** On a draft, a claim the documents do not back gets a *Find
  literature* button. The page suggests search words from the claim (the corpus's key terms it contains, kept whole,
  then its other content words), you change them, and the line under them says what will be sent and to whom. The works
  found are ordered by closeness to the claim: by meaning when a local embedding model has vectors in the project (never
  one on another computer), else by the words they share. Works you already have in the documents or the bibliography are
  marked; open copies come from OpenAlex, and *Look for open copies* asks Unpaywall for the rest.
- **Follow citations (E2).** The works your documents cite and the works that cite them, from the documents' DOIs (and
  those of the bibliography's works linked to them), ordered by how many of your documents they connect to and then by
  closeness to your themes (meaning with the embedding model, else shared words).
- **Saved searches (E3).** Keep a search or a research question (search words made from it on this computer); the page
  says how many works are *new since you last looked* (OpenAlex `from_created_date`; where the service refuses that
  filter, works published since). It checks searches not looked at for six hours when the page opens, and on *Check now*:
  nothing runs in the background. The Overview card shows the count, from what is kept (it asks no service).
- **Send to Zotero.** Works you tick go through Zotero's local connector (`/connector/saveItems`) into the collection
  selected in Zotero, with the open PDF if you wish (Zotero fetches it); the bar says where they will go, and says so
  plainly when Zotero is not open. RIS and BibTeX files are the fallback.
- **Privacy.** Nothing goes out with `--local-only`. A search made from a draft goes out only if the draft's AI setting is
  *Claude may read it* (for another draft you type your own words); following citations uses only documents whose setting
  allows it and lists the DOIs it sends. No text of a document or draft is sent. A contact e-mail address in *Settings →
  Exploring* is optional, empty until you give one, never filled in by Margin, and sent only to OpenAlex, Crossref and
  Unpaywall (which needs one: without it only OpenAlex's own open-access links are used). The agent is `Margin/<version>`.
  Answers are kept in the project (`lit_cache`), so the same lookup is not repeated; timeouts and plain-language errors
  (offline, rate limited, refused) are shown with *Try again*.
- For developers: `src/margin/literature.py`, the endpoints under `/api/projects/<p>/literature` and `/api/literature/*`
  (`docs/API.md`), `MARGIN_OPENALEX_URL`, `MARGIN_CROSSREF_URL`, `MARGIN_S2_URL` and `MARGIN_UNPAYWALL_URL`, the setting
  `contact_email`, and `tools/dev_server.py --literature` (stand-in services, a draft with unsupported claims, saved
  searches). The project's three tables are made when first used, so there is no migration.

**Defects fixed on the way.** None in existing code. Found while building: a draft id that does not exist is refused as
"no such draft" rather than treated as a draft that may not send.

**Tests added.** `tests/test_m0_10_0_literature.py` (search words, the three services, caching, offline, rate limit and
refusal errors, the privacy gate for `--local-only`, drafts and documents, ranking with and without an embedding model,
following citations, saved searches and their fallback, Zotero's connector, RIS and BibTeX, the API) and
`tests/test_m0_10_0_literature_page.py`; stand-ins in `tests/fake_literature.py`, and `tests/fake_zotero.py` now answers
the connector's `getSelectedCollection` and `saveItems`. None touches the network.

**Not yet done.** Not tried against the real OpenAlex, Crossref, Semantic Scholar, Unpaywall or Zotero: everything was built
from their documentation and stand-ins, so OpenAlex asking for an API key, or Zotero's connector wanting other fields,
would show as *refused* or *Zotero did not save*. No count in the sidebar (only on the Overview card). Saved searches use
OpenAlex only and list at most 50 works per look; following citations resolves at most 150 cited works, and runs while you
wait (no job). Zotero's collections are not chosen from Margin: the one selected in Zotero is used.

## 0.9.1 (November 2026): how fast Claude Code works, models for your plan, and the Zotero works you choose

From ENLENS 0.13.9 and 0.13.10, in Margin's names: a speed for Claude Code, recommended models that follow your
Claude plan, and only the Zotero works you choose. (ENLENS 0.13.9's *remove a theme and find a new one in its place*
has been in Margin since 0.7; its tests come along.)

### Faster or slower, and which helpers (ENLENS 0.13.10)

- **Speed: Slower · Normal · Faster** sits under every *Start Claude Code* (a check's progress, a result that waits,
  the sidebar's queue panel) and under *Settings → AI → Speed of Claude Code*: one, two or four helpers at once.
  Faster is done sooner but uses your plan's limits faster; Slower is easiest on them. The choice is kept, and the
  estimates follow it. *Claude Code is working on it* says how many helpers the run has.
- **Choose the helpers for this run**, folded away under the speed, lists each helper with work waiting (its model,
  what it would answer, how much waits). Set how many of each work at once (0: that work waits for a later run) and
  how many in all (1 to 8). It holds for one run; *Use the speed again*, or picking a speed, undoes it.
- A typed `/margin-run` without `--parallel` goes at the speed chosen in the app, and takes `--helpers
  checker=2,labeller=1` too. Margin now shares the helpers out itself: `queue_status` says how many to start for each
  group (`start`), and the skill starts what it says, so a run never has more helpers at once than chosen.
- For developers: Settings' `claude_speed`; `GET …/queue` adds `speed` and `start` on each group; `POST
  …/queue/claude-code` takes `{"parallel", "helpers"}`; the connector's `queue_status` takes `kind`, `parallel` and
  `helpers`. `docs/API.md` and the manual's *Start Claude Code* describe it.

### Models that suit your Claude plan (ENLENS 0.13.10)

- The recommended model of each task now follows the plan Claude Code is signed in with, found in the background
  (from `claude auth status`), also for work that already waits:
  - **Free:** no Opus or Fable. Haiku for most tasks (search words, splitting a hypothesis, theme names, references,
    a draft's claims, labels, links), stepping up to Sonnet; judging excerpts and second opinions on Sonnet.
  - **Pro** (and a plan not known yet): as before.
  - **Max, Team, Enterprise:** Opus for most tasks, checks included; Haiku and Sonnet only for the many labels, links
    and references, where speed matters.
- Models you chose in *Settings → Technical → AI model per task* come first on every plan. That section says which
  plan the recommendations follow, with a choice by hand for when Claude Code names it wrongly or not at all. The
  Claude API and local models do not follow the plan.
- For developers: Settings' `claude_plan` and `claude_plan_detected`; `routing.plan_tier`, `tier_defaults`,
  `settings_tier`; a task kind's `bulk` (label, link, resolve). `GET /api/routing` adds `plan`.
  `docs/MODEL_CHOICE.md` has the rules per plan.

### Only the Zotero works you choose (ENLENS 0.13.9)

- On *Bibliography*, tick **Choose the works one by one** under *Collection*: the library's works (or the chosen
  collection's) are listed by title with authors, year and type, searchable with Zotero's own quick search. Ticked
  works stay ticked while you search and stand above the list; the button says *Bring in 3 works*. A choice is 1 to
  500 works.
- *Update from Zotero* reads those same works again; *Choose other works or a file* opens the choice with last time's
  works ticked. Their files come along as for a collection.
- For developers: `GET /api/zotero/works`; `POST …/bibliography` takes `{"zotero": {"library", "items"}}`.

### In Margin

- The merge keeps Margin's prompt versions (`label-v2`, `link-v2`) and its draft-claims kind; the SDG pack's kinds
  and the extractor helper, which Margin does not offer since 0.8, are left out of `/margin-run`, the manual's plan
  table and `docs/MODEL_CHOICE.md`.

**Defects fixed (from ENLENS 0.13.10).** A plan of helpers asking for more at once than the helpers named add up to
said *8 helpers at once*: it now says what the run can really have. A decimal number of helpers (2.5) was cut down
without a word: it is refused.

**Tests** (from ENLENS, in Margin's names): `tests/test_0_13_10_helpers_per_run.py` (15),
`tests/test_0_13_10_plan_models.py` (10), `tests/test_0_13_9_chosen_works.py` (4),
`tests/test_0_13_9_remove_themes.py` (7); `tests/test_08_queue.py` expects `start` on each group. 604 pass.
Checked in headless Chromium with `tools/dev_server.py --corpus social --claude-cli --zotero`: the speed in Settings,
the plan choice under *Technical*, and choosing Zotero works one by one, in light and dark and at 390 px, with no
console errors.

**Not yet done.** Tried with the stand-in Claude Code and stand-in Zotero only. Whether a real, signed-in Claude Code
starts exactly `start` helpers at once, and how much faster four helpers make a large run, needs a real run. The plan
is read from `subscriptionType` in `claude auth status`; only the stand-in's values were tried, so a real value spelt
otherwise leaves the recommendations as for Pro until set by hand. The Zotero choice was not tried in Margin against a
real Zotero (ENLENS tried it with Zotero 10.0.7), nor with a library of thousands of works.

## 0.9.0 (November 2026): social practice theory as a codebook

Margin 0.9 adds two built-in codebooks from social practice theory, and what a codebook of *analytical* codes needs
to work. The SDG targets are topics whose words appear in a report ("water stress"); a code like *practical
consciousness* is an analyst's reading of "I just plug it in, I don't think about it". Its words are not in the text,
so a keyword search alone misses it, and a label needs to say more than its code: which practice, which element.

**Two built-in codebooks.** Listed after your own and before the SDG ones.
- **Social practice theory** (`practice`, 25 codes in 6 groups): elements (materials, competences, meanings),
  performing (sayings and doings, bodies, timing, practical concerns, emotions, breakdown), knowing (practical
  consciousness, accounts), rules, resources and power, dynamics (links made, sustained and broken, mutual shaping,
  circulation, careers) and connections between practices. Each code has a definition, keywords, when to use it,
  when not to (naming the code to use instead) and its source pages (Shove, Pantzar and Watson 2012; Giddens 1984;
  Nicolini 2012; Spaargaren, Lamers and Weenink 2016). Its stance, Nicolini's "programmatic eclecticism", and its
  sources are shown with it in *Settings → Codebooks → View codes*.
- **Framings of conduct and change** (`change_framing`, 4 codes): how a text explains what people do or why it
  changes: through practices, individual choice, structure or system, or technology by itself. One main framing per
  passage. Meant for policy documents.
- They are written by `tools/make_practice_codebooks.py` into `src/margin/data/codebooks/` (edit the codes there).

**Codebooks say more** (`frameworks.py`; for your own codebooks too).
- The CSV may have the columns `keywords` (separated by `;`), `include`, `exclude` and `source`. Keywords found in a
  passage as whole words make a code a candidate (certainty 0.45, so on their own they do not count in the
  provisional profile); keywords and the include text are matched with the description. The AI gets include,
  exclude and source with each code. *View codes* shows them under *Notes*.
- The codebook's JSON file may set `direction_labels` (the words for helps, hinders and mixed), `direction_note`,
  `one_main`, `practice_and_element`, `stance` and `sources`. The practice codebook says **holds together** and
  **pulls apart** (Shove et al. 2012: 36) instead of helps and hinders, on the document's *Codes* panel, in the
  forms and in the Excel table. A JSON file changed on its own is now read again (it was cached with its CSV).
- **Small codebooks go to the AI whole.** A codebook of 30 codes or fewer is sent complete with every passage (the
  codes the search found are marked), and the AI reads every passage by default, not only those with a candidate.
  The 17 SDGs are small too but keep reading only passages with a candidate: their keyword search is strong.
  *Options → Read every passage* still switches it either way.

**The practice and the element.** For the practice codebook, each label also names the practice the passage is
about and the element the code is about, copied from the passage ("switched the table on", "the games"). They are
checked like the quote: words the passage does not have are sent back. You can correct them (*Change how it
applies*) or give them with a label of your own. They are kept in a new table, `label_parts`.
- **Profile → Count by → Practice**: practices by code, like Shove et al.'s snapshot of car-driving (Fig. 2.2): the
  practices the labels name (namings that differ only in capitals or "the" are one row), each with its elements, and
  in each cell the passages, with how many hold the practice together or pull it apart. In the Excel download too.
- **A concept's page** lists *In codebook labels*: the codes whose labels name it as a practice or an element
  ("follow the elements of practice", Shove et al. 2012: 22).

**How elements relate.** Links between concepts can now be element relations: *needs*, *shapes*, *replaces*, *is an
element of* and *clashes with* (an element of two or more practices is shared by them). When the chosen codebook
names practices, a concept's page offers them under *Add a link yourself* and *Another relation*, and *Ask the AI how
they relate in a practice* under *Often mentioned together* (up to 8 pairs). The link task asks for them when told
(`link-v2`); the word relations (same, broader, narrower, related, different) are unchanged.

**Prompts.** `label-v2`: the whole codebook or the candidates, each code's notes, the codebook's direction words and
note, one main code, practice and element. `link-v2`: the element relations. Labels and links made before keep
their prompt version; the Profile page's *Something changed since the last labelling* says the instructions changed.

**Tests.** `tests/test_m0_9_0_practice_codebook.py` (13 tests): the built-in codebooks, their order and protected
names; the shipped files equal what the builder writes; the new columns, keywords as whole words, malformed JSON;
the whole codebook and every passage for small codebooks, not the 17 SDGs; keyword candidates; the label task and
its prompt; practice and element checked against the passage, corrected and shown; one main framing; the grid by
practice and labels of your own (and removing a document removes their parts); the concept's labels; element
relations in the link task (turned round with the pair, a word relation refused); the app's routes; the page's
words. Updated: the codebook order in `test_m0_8_0_no_sdg_default.py`, the prompt versions in
`test_0_13_6_task_kinds.py`, and the second wheel in `test_0100_setup_and_moving.py` (it was named 0.9.0, now
Margin's own version, so it no longer made a second wheel).

**Cautions** (from the readings, also in the manual). These concepts are sensitising, "not meant to be applied
formulaically" (Nicolini 2012: 240). AI labels on interview transcripts record *accounts* of practice; fieldnotes
code better, and KN1 (practical consciousness) only where a speaker marks their knowing as tacit. Concepts that show
only across a body of material (duality of structure, a practice's trajectory, proto- and ex-practices) are left out
of the codebook on purpose: check them as hypotheses.

**Not yet done.**
- Not tried with a real model: how well the AI codes with the whole codebook, names practices and elements, and
  judges element relations. Coding 50 to 100 passages by hand (from *Ethnographies* or *Tovertafel*) and comparing
  them with the AI's labels is the next step.
- The source pages in the codebook come from reading the texts, not from a check run against them (a theory
  project with the five readings would verify them).
- Not in the codebook: Bourdieu (habitus, field, capital), Schatzki at first hand, carriers, recruitment and
  defection (Shove et al. ch. 4), and the critique of attitude-behaviour-choice models.
- The codes are listed in natural order (DY before EL), not in the codebook's own order of groups.
- An element relation judged for a pair replaces an earlier word relation the AI gave the same pair.
- Not tried with a real signed-in Claude Code.

## 0.8.0 (November 2026): Margin without ENLENS's SDG baggage

ENLENS is built around the UN Sustainable Development Goals; Margin is a companion for writing with any sources. 0.8
takes the SDGs out of Margin's defaults and the SDG pack (the green-hydrogen Value Chain Assessment pipeline of the
ENLENS pilot) out of everything a Margin user sees. The SDG codebooks stay as a built-in option. The pack's code,
prompts and tables stay where they are, unused, so ENLENS's work still comes in through `tools/sync_enlens.py` and a
project copied from ENLENS that holds pack results still opens. The edits are in ENLENS's own files, so the next
syncs will meet conflicts in them, accepted for now.

**No codebook until you choose one.**
- The setting `profile_framework` defaults to none (`""`) instead of `sdg`. A settings file written before 0.8 had
  `sdg` as everyone's default, so it is read as none once (`_version` 3); choose it again if you used it. The labels
  in your projects are kept.
- Adding documents skips the codes step when there is no codebook (it ran an SDG keyword pass on every document).
- The Profile page, a document's *Codes* panel and the themes' code grid show **Choose a codebook first**, with the
  project's codebooks and *Add your own codebook (CSV)*; choosing one saves the setting. A codebook that is no longer
  there (it fell back to the SDG targets) now asks again too. The Overview says *Choose a codebook first*.
- *Check a hypothesis* starts with *No codebook* (it preselected the SDG targets and fetched SDG suggestions as you
  typed). *Settings → Exploring* offers *No codebook*.
- Requests that need a codebook and name none answer 409 *Choose a codebook first* (profile, keyword pass, AI labels,
  comparing labels, adding a label); code suggestions return none; a highlighted copy has no labels layer.
- The command line's `profile`, `annotate` and `prepare label`, and the connector's `suggest_targets` and
  `document_profile`, take the codebook chosen in Settings when none is named (they defaulted to `sdg`).
- A code given without a codebook is still read as an SDG target (`check --code 6.4`, the API), as before.

**The SDG codebooks, as built-in examples.** Your own codebooks are listed first everywhere and the SDG ones last
(`frameworks.available`). Settings → Codebooks no longer opens with "The UN SDG targets are built in"; the Profile
card, the search code filter (`codebook:code`), the help-or-hinder switch and the fallback wording no longer name
the SDGs. "Goal" still counts the SDG codebooks by goal when one is chosen.

**The SDG pack, out of sight.**
- *Settings → AI model per task* drops its four rows (`routing.SDG_PACK_ROWS`); "Second opinion (and audits of the
  SDG pack)" is now "Second opinion".
- *Settings → Technical* drops the *Model test*, which was scored against the pilot's VCA checks and needed the pilot
  folder, which no install has. `margin benchmark` and `POST /api/benchmark` stay for developers.
- *Projects* drops *For FlexiConc / Cross-Doc* (the Cross-Doc SDG Explorer's layout); the endpoint stays.
- `margin --help` no longer lists `load-vca`, `match-sources`, `reset-corpus`, `coverage`, `screen`, `make-tasks`,
  `export-flexiconc`, `acceptance`, `review-export`, `review-import`, `gold-export`, `evaluate` and `report`
  (`cli.SDG_PACK_COMMANDS`); they still run when typed. Its description no longer mentions the VCA pipeline.
- The Claude Code plugin loses the `margin-extractor` helper (six helpers now), and its descriptions (`plugin.json`,
  `SKILL.md`, the checker and the auditor), which Claude Code loads in every session, no longer mention the pack.
- *Remove all documents* is still refused for a project that holds pack results; the troubleshooting line now says
  that means a project copied from ENLENS.
- `docs/MANUAL.md` loses sections 9 to 14 (about 400 lines on the pack; *Limits* and *Troubleshooting* are now 9
  and 10) and the pack's limits and troubleshooting rows; `docs/MODEL_CHOICE.md` its pack rows and their reasons;
  the README its "optional pack" line and the FlexiConc export.

**Removing themes, shared with ENLENS.** The code of 0.7's *remove a theme, and find a new one in its place* is
offered to ENLENS as well (as ENLENS 0.14.0). So that it comes back through `tools/sync_enlens.py` without a conflict,
Margin's copy is now the same as ENLENS's apart from the names: its rules move from `margin.css` (section `m070`) to
the Themes page's own stylesheet, `concepts-themes.css`, unchanged; the comment on its columns in `store.py` no longer
names an app; and its tests are ENLENS's, `tests/test_0_14_0_remove_themes.py` (was `tests/test_m0_7_0_remove_themes.py`,
the same 7 tests, which now look for the rules in `concepts-themes.css`). Nothing changes on screen.

**Tests.** `tests/test_m0_8_0_no_sdg_default.py` (9 tests): no codebook by default and an old `sdg` default dropped
once (chosen again, it stays); own codebooks before the built-in ones; through the app, adding documents with no
codebook (no codes step, no error), the 409s, empty suggestions, then a codebook named and chosen; the model table
without the pack's rows; `margin --help` without the pack's commands (which still run) and `profile` asking for a
codebook; the connector's codebook; the plugin without the extractor; the page without an SDG default, the model
test or the FlexiConc button; the manual and README without the pack.

**Not yet done.** The pack's modules, prompts, task kinds and tables are still in the code (unused); taking them out
would conflict with every ENLENS sync. ENLENS's `pilot/` folder (38 MB, used by tests) is still in the repository. A
code without a codebook is still read as an SDG target. Not tried with a real signed-in Claude Code: `/margin-run`
without the extractor helper.

## 0.7.0 (November 2026): remove a theme, and find a new one in its place

Margin 0.7 lets you take out the themes that say nothing about your question, and look for one it missed instead.
ENLENS 0.13.8 takes *Check citations* out of ENLENS again; Margin keeps it, as part of *Check a draft* since 0.6, so
nothing of 0.13.8 changes Margin (the add-on fix it keeps came with ENLENS 0.13.7, already in Margin 0.6).

**Remove a theme you do not need, and find a new one in its place.** A set of themes often has one or two that say
nothing about your question (running headers, reference lists, a topic outside your research). Now you can take them
out, and let Margin look for a theme it missed.
- **Remove…** on each theme (on the list and on its page) asks *Just remove it* or **Remove and find a new theme**.
  A removed theme's passages are left out of the themes, the grids and the Excel file; it waits under **Removed
  themes** at the foot of the list, crossed out, with **Bring it back**. Its page still opens, so a passage that
  matters can be moved into a theme you keep. The last theme shown, a theme merged into another, and merges or moves
  into a removed theme are refused.
- **A new theme in its place**, found on this computer without AI. Every theme shown is split in two
  inside itself (2-means, the set's seed); the half that fits its theme least well becomes a candidate, the one that
  draws most passages closer to it than to their own theme wins, and it is refined with every other theme fixed. It
  takes only passages the clustering placed (never one you moved), and never one closer to a theme you removed, so
  the removed theme does not come back under another name. The new theme is named by its key terms like the others;
  the themes it takes passages from keep their names (and new representatives where theirs moved). It is marked
  *new: found in place of “…”*, and its page says which themes its passages come from. *Find a new theme in its
  place* also sits beside each removed theme; once per removed theme (remove the new one to find another).
- *Let the AI name the other N themes* names a new theme without renaming the others. *Your changes* counts removed
  and new themes; they belong to that set of themes only (renames, merges and moves still apply again to a new set
  with the same settings).
- Excel: *Found in place of* on the themes, and a *Removed themes* sheet. The FlexiConc export leaves removed themes'
  passages out. The Overview counts the themes shown.
- `PUT …/themes/<run>/edit {what: "remove", theme_id, value: true|false}` and `POST …/themes/<run>/new {replaces}`
  (job `theme-new`); three new columns, added to a project when it opens: `themes.removed_at`, `themes.replaces`,
  `theme_members.found_in` (the theme a passage was in before a new theme took it).

**Tests.** `tests/test_m0_7_0_remove_themes.py` (7 tests), on six generated topics in twelve documents: removing
and bringing back (left out of the list, the grids, the counts and the Excel themes; its page opens; a passage moved
out of it; merges and moves into it refused); the last theme and a merged one; a new theme by words (one topic, never
the removed one's, nothing of the removed theme, where its passages came from, representatives kept right, the same
result from the same set, once per removed theme, a second new theme in place of the first, renamed, named by the
AI); by meaning, on planted embeddings, a new theme that splits a mixed one; through the app (refusals, the job, the
export, bringing back); a project from before gains the columns; the page and its section of `margin.css` (colour
tokens only). Checked in headless Chrome with `tools/dev_server.py` and the generated corpus: remove and find a new
theme from the list, the new theme's page, the removed theme's page, the removed themes in light and dark and at
390 px, bringing one back, with no console errors and no sideways scroll.

**Not yet done.** A removed theme's passages are not left out of search, the profile or checks: only out of the
themes. A new theme is not named by the AI by itself; press *Let the AI name the other themes*. When the passages
left fit their themes well (a small project, or themes of fewer than six passages), no new theme is found, and the
message says to find the themes again with more themes.

## 0.6.0 (November 2026): check your citations against their sources

Margin 0.6 checks the other half of a draft's sources. *Check a draft* already showed which of your documents back
each claim; now it also checks the citations you wrote yourself: does the work you cite say what your sentence says?
Your citations are found as you add a draft, checked against the cited work's own document, and shown where you
write: underlined in the draft and on the claim they stand for. It comes from ENLENS 0.13.7's *Check citations*,
made one with *Check a draft*. From ENLENS 0.13.6 and 0.13.7 also come an update button that shows only when there is
an update, and a model on this computer without a terminal.

**Check a draft checks your citations too.** ENLENS 0.13.7's *Check citations* now works with *Check a draft*.
Your own writing has one home, and a cited claim shows both what your documents say about it and whether the source
you cite says it.
- **Your citations are found when you add a draft**, without AI: *(Smith, 2020)*, *Smith et al. (2020) found that
  …*, *[3]* with a numbered reference list. A third step on the draft page, **Check your citations against their
  sources**, counts them (*5 not checked yet, 4 cannot be checked yet*), and **Check N citations** checks each cited
  work whose document is in the project against that document only. *Review every citation* opens them on *Check
  citations*, where you choose the work of a citation or leave one out.
- **In the draft**, each citation is underlined by its answer: solid green when the source says it, wavy red when it
  says otherwise or both, wavy amber when it says only part of it or the excerpts read do not say it, dotted while it
  waits or cannot be checked yet. Hovering names the work and its answer.
- **On the claim it stands for** (the citation inside the claim, right after it, or before it in the same sentence:
  *According to Lindqvist (2025), …*; never the sentence before's), **Your citation** names the work and its answer,
  with *See the excerpts*, *Check this citation* or *What it needs*. A notice says what it means and shows the
  source's excerpt. A folded card names your citation and its answer. A new filter shows the claims with a *Citation
  to look at*. A found citation also marks its claim *cited in your draft*, whatever the AI guessed.
- **Check citations sits under Your writing**, beside *Check a draft*, in the sidebar and on the Overview. A text you
  paste or choose there is kept as a draft, with its name and AI setting, so its claims can be found too. Every
  draft's citations are listed there, and drafts from before are linked when the list or their page opens. A draft's
  citations lead *Back to your draft*. Their name and AI setting are the draft's, changed from either page, and they
  are removed with the draft (removing them on their own is refused). A pasted text without citations is not kept,
  and the message points to *Check a draft*.
- **Privacy.** The checks of a draft's citations keep the draft's AI setting, as its claims' checks do. Every task of
  them counts as the draft's text (`access.draft_of` follows a citation to its draft), so a draft marked *Only a local
  AI* never reaches Claude, its checks are hidden from a Claude chat, and what Claude reads of it is recorded with
  the draft. A new setting reaches the tasks not answered yet at once.
- **Excel and CSV** of a draft gain *Your citations* and *What the cited source says*.
- `tools/dev_server.py --citations` makes its demo text a draft (claims found by rules), so the page shows both.

**Tests.** `tests/test_m0_6_0_draft_citations.py` (9 tests): a new draft's citations found at once, with the
draft's name and setting kept in step (and the project's default); a draft without citations; drafts from before
linked; each citation on the claim it stands for (after, before in the same sentence, inside; never across a
sentence's end) with its place in the draft; checking a draft's citations (answers on the claims, the export, what
Claude read recorded, removed with the draft); a draft for *Only a local AI* (nothing reaches the stand-in Claude,
hidden from the connector, every task the draft's); a new setting reaching queued tasks; through the app (a draft's
citations on its page and in the list, checked, renamed and set from Check citations, removal refused, a pasted text
kept as a draft, one without citations not kept); the page files and its rules in `margin.css` (colour tokens only). ENLENS's
`test_0_13_7_citations.py` and `test_0_13_6_page_extensions.py` expect Check citations under *Your writing*, and
removing a pasted text through its draft. Checked in headless Chrome with `tools/dev_server.py --citations`: the
draft page before and after checking (step 3, the underlines, *Your citation*, the filter), the drafts list, Check
citations (the list and a draft's text), the Overview, in light and dark and at 390 px, with no console errors.

**One stylesheet for Margin.** Margin's CSS was one file per release (`m-tokens.css`, `m010.css`, `m030.css`,
`m050.css`, `m020.css`) plus the next release's. It is now one stylesheet, `margin.css`, which `site.css` (the local
layer, linked after every stylesheet of ENLENS) imports. Its sections keep the old order, so nothing looks different:
18 screenshots (the draft page before and after checking, the drafts list, Check citations, a draft's citations, the
Overview; light, dark, 390 px) are identical, byte for byte, before and after. Margin's tests read its sections
(`tests/margin_static.py`: `sections()`, `section(name)`). New rules go into the section of their feature, never
into a new file.

**Not yet done.** A draft has no pages, so its citations show no *page 3 of your text*, as a file given to ENLENS's
Check citations would. Checking the claims and checking the citations are two buttons, and two jobs. A claim with a
citation is checked against all the documents *and* against its cited source, which costs one more AI check per
citation. Not tried with a real signed-in Claude Code (the stand-in Claude Code and models were used).

**From ENLENS 0.13.6 and 0.13.7: check your citations, updates that announce themselves, and a local model without a
terminal.**
- **Check citations** (ENLENS 0.13.7): a text's citations, *(Smith, 2020)*, *Smith et al. (2020) found that …* and
  *[3]* with a numbered reference list, are found without AI; each is matched with a work of the bibliography and its
  claim is checked against that work's own document, and no other: *Source accurate*, or a notice (only partly
  supported, not found in the source, the source says otherwise). Every answer goes through the quote check and can
  be overruled on the result page. How it works together with *Check a draft* is in the next entry.
- **Updates that announce themselves** (ENLENS 0.13.6): the *Update Margin* button shows only when there is
  something to install, with the version (*Update to 0.6.0*); the page looks when it opens and every two minutes, and
  a new version pops up once in the corner (*Update and restart*, *Later*). *Settings → Technical → Check for updates*
  looks at once and says why when it cannot.
- **A model on this computer, without a terminal** (ENLENS 0.13.7): with Ollama running, *A model on this computer*
  (first screen and *Settings → AI*) downloads qwen3:8b with one button and a progress bar, and chooses it when the
  download ends; without Ollama, three plain steps. *Local model for restricted documents* and *Search by meaning*
  offer the same download. Fixed: *Use a local model* on the first screen no longer skips the model step.
- **Version numbers.** ENLENS withdrew its 0.14.0, 0.15.0 and 0.15.1 (their changes are in its 0.13.6). Those were
  never Margin's numbers, so Margin withdraws none (`update.WITHDRAWN` is empty) and its own 0.14.0 will count as a
  later version. `test_0_13_6_version_numbers.py` checks the order of Margin's own releases only (ENLENS's history
  follows Margin 0.1.0 in this changelog), and `test_0_13_7_local_model.py` reads this changelog, not the README.
- **Fixed on the way:** reading an excerpt again (*Read again* on the result page) now keeps the AI setting of the
  text a claim comes from, a citation's text as well as a draft (`access.text_floor`). ENLENS's tests renamed
  `test_0140_addons.py`, `test_0150_task_kinds.py` and `test_0151_page_extensions.py` to `test_0_13_6_*`.

**From ENLENS 0.13.5 to 0.15.1: room for apps built on ENLENS, and Margin moved into it.** ENLENS now gives an app
built on it extension points, so Margin can add its features in files of its own instead of editing ENLENS's, and
each sync clashes less. Nothing changes on screen.
- **Margin's look is in the local layer.** Margin's colour tokens moved out of `app.css` into `m-tokens.css`, and
  `site.css` (linked last, never edited by ENLENS) imports them and Margin's own sheets (`m010`, `m030`, `m050`,
  `m020`, in the same order as before). ENLENS's tokens now live in `tokens.css`, which Margin's override.
- **Margin's name and welcome words** are in `brand.json`; the sidebar, window titles, welcome screen and the Update
  and Quit buttons read them.
- **Finding the claims in a draft is a registered kind of AI task** (`drafts.py`, ENLENS's `taskkinds.py`), no longer
  edits to ENLENS's prompts, routing, queue, store, limits, offline demo and size estimate. Its prompt is unchanged
  (`claims-v1`). ENLENS's quote check now reads every quote of its answers too, before Margin's own store function.
- **A draft's AI setting runs through ENLENS's access hooks** (`register_floor`, `register_hidden`), so tasks holding
  a draft's text and the checks of its claims keep the draft's setting, and drafts kept on this computer stay out of
  a Claude chat, as before.
- **A claim of a draft records where it comes from** as ENLENS 0.14 does (`origin` "draft"); claims made earlier are
  given it when a project is opened (Margin's `gui/extensions.py`). The result page's *Back to your draft* and *a
  claim of your draft*, and the sidebar's names for draft jobs, come from Margin's page module (`static/extensions.js`).
- From ENLENS 0.13.5: an import of a project's folder zipped by hand works as in Margin 0.2.1; the release workflow,
  the zip-name and icon fixes were Margin's already. *Second opinion* wording everywhere. Steadier tests.
- From ENLENS 0.14 to 0.15.1 (for developers): add-on routes, jobs, tables, access hooks, task kinds and page modules
  (docs/EXTENDING.md), with ENLENS's stand-in add-on and its tests.

**Tests.** ENLENS's new tests (`test_0135_*`, `test_0140_addons.py`, `test_0150_task_kinds.py`,
`test_0151_page_extensions.py`) run in Margin with Margin's filled local layer: its kind of task, its look and its
page module. Margin's look tests read the sheets `site.css` imports (`tests/margin_static.py`). Checked in headless
Chrome: the Overview (*Your writing* between exploring and checking) and *Check a draft* in Margin's look, with no
console errors.

**Not yet done.** The `claims` row of Settings' model table now comes last (it was between *References* and
*Judging excerpts*). The drafts' tables, columns, routes and page still live in ENLENS's files (`store.py`,
`server.py`, `index.html`, `features.js`); they can move into Margin's local layer step by step.

## 0.5.0 (November 2026): APA citations to paste from your draft

**Citations to paste from a draft.** With a bibliography (your Zotero library or a collection, or an exported file),
every document a draft's claim would cite now has its APA 7 in-text citation beside it, such as **(Verhoeven &
Okafor, 2025)**: one click copies it, ready to paste into your text, and Alt-click (Option-click on a Mac) copies the
narrative form, *Verhoeven and Okafor (2025)*. A claim you marked *supported* or *refuted* has one button for all the
documents to cite, in one parenthesis and in APA's order: *(Adeyemi & Brandt, 2024; Verhoeven & Okafor, 2025)*. The
citations follow APA 7 as your reference list would: *et al.* from three authors, editors when there are no authors,
*n.d.*, *2024a*/*2024b* for the same authors and year, as many names as needed when two *et al.* would read the same,
and the first words of the title for a work without an author (in quotation marks for an article or web page, in
italics for a book or report; the italics come along when pasted into Word). Documents not linked to a work are
named, with a link to *Bibliography*. Nothing is sent anywhere and no AI is used: the citation is made from what
Zotero holds. The draft's Excel and CSV files have a new column, *Citation (APA 7)*.

**Tests:** `tests/test_m050_apa_citations.py` (one, two and more authors, group authors, editors, no date, a
and b, *et al.* told apart, works without an author, several works in one parenthesis, a checked draft with a Zotero
library from the stand-in Zotero, the API, the page). `test_0133_app_wide_polish.py` and `test_0134_claude_account.py`
count `unreleased.css` (a feature's stylesheet before its release) as one of Margin's own; the new look is in
`m050.css`, linked before `m020.css`. Checked in Chrome with the dev server (the social corpus,
the stand-in Zotero): a draft's cards folded and open, a document not linked, copying (the combined citation and the
narrative form, read back from the clipboard), light and dark, 1280 and 390 px; no console errors.

**Not yet done:** pasting into Word and Google Docs was not tried by hand (the browser's clipboard was read back
instead). Page numbers for a direct quote (*p. 12*) are not added: the citations are for paraphrase. Only APA 7;
other styles (Chicago, Harvard, Vancouver) would come from Zotero's own citation styles.

## 0.4.0 (November 2026): your Zotero bibliography, and a calmer result page

From ENLENS 0.12.0 to 0.13.4: a Zotero bibliography beside your documents, a rebuilt result page, a calmer look on
every page, the Claude account that answers, and checks on Sonnet. Margin keeps its own look, its drafts and its
*second opinion* wording on top. Every answer still goes through the quote check and a person can overrule it.

**Your Zotero bibliography next to your documents (from ENLENS 0.13.0).** A new **Bibliography** page brings in a
Zotero collection (or the whole library, or a group library) from the Zotero app on this computer: Zotero 7 or later,
with *Settings → Advanced → Allow other applications on this computer to communicate with Zotero* ticked once.
Nothing goes over the internet, Zotero is only read, and no AI is used. No Zotero at hand: a file exported from
Zotero, Mendeley or EndNote (BibTeX, RIS, CSL JSON or Zotero's CSV).
- Each work is linked to the document you already have by itself when it is the same file or has the same DOI; when
  only its title, with an author or the year, stands on a document's first pages, the pair waits for *Same work* or
  *Not the same*, shown beside the place where the title stands. A document that only cites a work is not taken for
  it.
- *To find* lists the works without a document (DOI link, web address, *Open in Zotero*, *Download the list* as a
  spreadsheet); the PDFs Zotero keeps for them are added in one go, read where Zotero keeps them. *Not in the
  bibliography* lists the documents Zotero does not have. Documents added later are matched as they come in; your
  decisions are kept when you update from Zotero or switch to another collection or file.
- **Titles from your bibliography (from ENLENS 0.13.3).** A linked document takes its work's title everywhere (the
  Documents list, the document page, Search, a check's excerpts and exports); the title read from the file is kept
  and shown under it, and comes back when the link goes. AI tasks made after the link carry the work's title.

**The result page, rebuilt to be read (from ENLENS 0.12.0 and 0.13.2).** The answer first, in one card: who says what
(one row per document), one caution in one sentence and one button, **Next to review**. Then the evidence, as *Cards*
or *Table*: each excerpt card shows the judgement, the document and place, and the quote with one sentence around
it, with the same row of actions (**Agree**, **Not about this** (new: one click, with Undo), **Judge differently…**,
*In context*, *Details*). Then *Ask another AI model*, your notes, quiet download links, and *Technical details*. A
short heading that opens a paragraph (*Recommendations.*) shows as a small heading. On a claim of a draft the page
still links back to the draft (*Back to your draft*, *a claim of your draft*).

**Every page calmer (from ENLENS 0.13.3).** A few type sizes and two weights, one card style without shadows,
colour only where it means something (the AI marks are grey), one-line page subtitles, help marks (?) instead of
paragraphs, and downloads as quiet links on *Results*, *Search*, *Profile*, *Themes* and the evidence map. Margin's
own look (`m010.css`, `m020.css`, `m030.css`) is still linked last, so its ink blue, book face, eyebrows and margin
line win where the two differ.

**The sidebar says when nothing runs (from ENLENS 0.12.0).** Work waiting for Claude Code while nothing answers it
now says *1 task not running · Waiting for Claude Code to start*, with *Start Claude Code* in its panel, instead of
*1 task running*. This covers Margin's own draft jobs too (finding a draft's claims, checking them).

**Which Claude account answers (from ENLENS 0.13.4).** Hovering the sidebar's *Claude, on your plan* line (or
reaching it with the Tab key) opens a small card: *Signed in to Claude Code as you@university.nl*, the plan (and the
organisation on Team or Enterprise), where the text goes and where to change it; Escape closes it. Signed out or not
installed, it says so and points to *Settings → AI*, which names the account too (also on a phone), as does `margin
claude-setup`. The address comes from `claude auth status` and is only shown: it is not written into Margin's files,
`/api/state` or the queue, and with `--local-only` Claude Code is not asked. The sidebar, *Overview* and *Settings*
share one answer from Claude Code.

**Checks on Sonnet (from ENLENS 0.13.3).** Judging excerpts (a check, reading one excerpt again, a draft's claims)
goes to Sonnet at high effort instead of Opus. An unsure judgement, two rejected answers and *Ask a stronger model*
still go to the auditor (Opus, or Fable when switched on), and second opinions stay on the auditor. *Settings →
Technical → AI model per task* can set checks back to Opus. A Margin plugin set up earlier runs its checker on Sonnet
at the normal effort until it is written again (*Update Margin* or `margin update`, then `/plugin marketplace update
margin` in Claude Code; `margin claude-setup` on a git copy).

**Defects fixed (from ENLENS).** Dates in the computer's own language and order are now *4 Nov 2026, 19:36*
everywhere; a quote opening with *There is…* or *It seems…* is no longer flagged for a reference to check; a comment
typed and then *In context* clicked is no longer lost; on a phone *Search* no longer scrolls sideways; a help note
near the right edge stays in view; a DOI in a document's header is a link; a card's source line no longer begins
with "·"; a selection across "…" in an excerpt is accepted.

**Update Margin (ENLENS 0.13.1).** ENLENS took Margin 0.2.1's *Update Margin* button. The code was the same on both
sides; Margin's wording stays, `docs/API.md` and `docs/MANUAL.md` now describe it in more detail, and ENLENS's tests
for it (`tests/test_0131_update_button.py`) run beside Margin's.

**Tests:** from ENLENS, `tests/test_0120_results_page.py`, `test_0130_bibliography.py`, `test_0131_update_button.py`,
`test_0132_result_page_polish.py`, `test_0133_app_wide_polish.py`, `test_0133_zotero_titles.py` and
`test_0134_claude_account.py`, with the stand-in
Zotero `tests/fake_zotero.py` (also `tools/dev_server.py --zotero`). `test_0133_app_wide_polish.py` and
`test_0134_claude_account.py` now check that only Margin's own stylesheets come after ENLENS's last one (ENLENS wants
its own last). New:
`tests/test_m040_draft_jobs_on_hold.py`: finding and checking a draft's claims are *not running* while nothing
answers and running once Claude Code takes a batch. Checked in Chrome with the dev server (the social corpus, the
stand-in Claude Code and Zotero): the result page (a mixed answer and a claim of a draft), *Bibliography*, a draft,
*Overview*, *Documents*, *Search*, *Results*, *Profile*, *Themes* and *Settings*, light and dark, 1280 and 390 px, and
the account card on hover with the stand-in Claude Code; no console errors.

**Fixed:** `test_make_backend` (`tests/test_app.py`) asked the default Ollama address on the computer, so it failed
when an Ollama with a model was running there; it now asks an address nothing answers on.
`test_a_launched_copy_restarts_in_place` could fail on a busy computer: it asked whether Margin answers and then read
its page, and a restart starting between the two raised an error instead of counting as "not answering yet". It
now waits. ENLENS's `tests/test_0131_update_button.py` is Margin's `test_m021_update_button.py` with one test more,
so Margin's copy is gone and the real restart runs once.

**Not yet done.** Not tried with a real Zotero 7 (only the stand-in) nor with a real signed-in Claude Code (the
*not running* state and checks on Sonnet were tried with stand-ins). Checked in Chrome only.

## 0.3.1 (November 2026): the 0.3 release, with a test that no longer depends on timing

0.3.0's release workflow stopped on one test, so 0.3.0 was never published; 0.3.1 is the same release (see 0.3.0
below for what it does) with that test fixed. Nothing in the app changed.

**Fixed:** `test_enlens_projects_are_copied_and_enlens_keeps_its_own` checks that copying ENLENS's projects leaves
ENLENS's folder untouched by listing its files before and after. On the Linux test machine an ENLENS project's
database still had SQLite's temporary `-wal` and `-shm` files when the first list was made; when the copy closed the
last connection to that database, SQLite folded them into the database and removed them, as it always does, so the
lists differed although no data had changed. The test now leaves those two temporary files out of the lists and
compares the database's rows before and after instead.

**Not yet done:** as for 0.3.0. SQLite on macOS keeps those files in the same situation, so the failure could not be
reproduced on the Mac; the fix was checked against the files the Linux run reported.

## 0.3.0 (November 2026): decide on each claim of a draft

**Claim supported, Claim refuted, Dismiss claim.** Each claim's card on the *Check a draft* page has three buttons for
your own decision, before or after a check.
- **The card folds** to what is left to do: the claim's number, your decision, the AI's answer if it was checked, the
  claim (two lines at most) and what to cite: the documents that support it (for *supported*) or contradict it (for
  *refuted*), or *Your draft cites a source here*. *More* opens the full card (the chosen button is pressed; press it
  again or *Undo* to take the decision back) and *Fold* closes it.
- **The highlight in the draft changes** to say a source should be cited there: no colour fill, a green (supported)
  or red (refuted) underline, and a small tag **cite here** after the sentence, where the citation goes (*cited*, in
  grey, when the draft already gives a source). A dismissed claim is only dotted, as a dropped one was.
- **Dismiss claim takes the place of Drop**, so there is one way to say a sentence needs no source; claims dropped
  before 0.3 show as dismissed. Person-marked claims keep *Remove* as well.
- New filters: *To decide* (once something is decided), *You: supported*, *You: refuted*; *Dropped* is now
  *Dismissed*. The claims heading counts the decided ones.
- A decision belongs to the draft: **the result page and the claim's answer do not change** (no change was asked
  there). Decided claims are kept when the claims are found again, are left out of *Check N claims* (open the card
  and press *Check this one* to check one anyway), and the Excel and CSV export gain a *Your decision* column.
- API: `PUT …/drafts/<d>/claims/<c>` takes `{"decision": "supported" | "refuted" | "dismissed" | null}`; each claim
  of `GET …/drafts/<d>` has `decision` and `decided_at`, and `counts` has `decided` (`docs/API.md`). Two new columns
  on `draft_claims`, added to existing projects when they open.

**The claims scroll on their own.** On a wide window the draft and the claims are two panes of the window's height:
the page scrolls until they fill it, then each scrolls by itself, so looking through the claims never moves the
draft. The claims' heading and filters stay in view at the top of their pane. Clicking a sentence in the draft
scrolls only the claims pane to its card; on a narrow window (stacked) the page scrolls as before.

**The whole card is clickable.** A click anywhere on a claim's card (not on its buttons, links, or text being
selected) shows its sentence in the draft, scrolling only the draft pane; the number stays the keyboard way to do it.

**Fixed on the way:** the draft pane's heading could slide off the top of the window when the page was scrolled to
its end (the page's bottom margin let it scroll past the board); the wording "dropped" in the steps, the *Find again*
question and the export is now "dismissed".

**Tests:** `tests/test_m030_claim_decisions.py` (the three decisions and taking one back, dismissing is dropping and
older dropped claims, decided claims kept when found again and left out of the bulk check, a decision never changing
the check and its export, the API, the page files). Checked in Chrome on the dev server: a draft of 13 claims, 8
checked and 4 decided, in light and dark at 1440 px and at 390 px; the wheel over the claims moves only the claims;
a click on a card scrolls the draft to its sentence and a click on a sentence scrolls the claims to its card; deciding
folds the card and the tag *4 · cite here* appears; *Undo* unfolds it; no console errors and nothing wider than a
phone.

**Not yet done:** tried only with the dev server's stand-in models, not a real signed-in Claude Code. The Map and the
result page do not show the person's decision. Keyboard users open a sentence from a card with its number button
(the card itself is not a tab stop).

## 0.2.2 (November 2026): a stronger model's answer, and a Start Claude Code button you cannot miss

**From ENLENS 0.11.2 and 0.11.3**, brought in with `tools/sync_enlens.py` (the first sync: ENLENS's commits keep
their own messages in the history, with Margin's names). Every answer still goes through the quote check, a person
can overrule it, every result records how it was made, and nothing about what leaves the computer changed.

**A stronger model's answer is the answer (ENLENS 0.11.2).**
- When a stronger model reads a check's excerpts again and changes the answer, the result shows the new answer with
  a small mark, e.g. **Supported** *at first: partly supported* (hover or click it: which models, how many judgements
  changed). Each part of a split hypothesis carries its own mark; the Results list shows *was partly supported*, and
  the Excel *Summary* sheet has the column "Answer before a stronger model read it again". Each changed excerpt
  keeps its first reading under *Technical details*.
- *Keep this result up to date* has one block, **Ask another AI model to read these excerpts**, with two clearly
  different choices: **Stronger model** (replaces the AI's judgements, so the answer can change) and **Second
  opinion** (only for comparison, never changes the answer). *Ask a stronger model* now works on the whole result
  (`POST /api/projects/<p>/hypotheses/<h>/stronger`) instead of a button under each search.
- "Second AI model" is called **second opinion** everywhere. On an excerpt, a second opinion is one line with every
  reading (the AI, the second opinion, you), and a switch shows which sentence each of them quoted.
- API: `status_first`, `status_before_stronger` and `stronger` on a hypothesis and each part, `can_step_up` per
  search, `status_before_stronger` on each row of the Results list (`docs/API.md`).

**A Start Claude Code button you cannot miss (ENLENS 0.11.3).**
- About five seconds after work starts waiting with nothing answering it, **Start Claude Code** pulses and says
  **Nothing runs until you press it.** (a still ring with reduced motion). It stops once the button is pressed or
  something answers the work (Claude Code started from Margin, or `/margin-run` typed in Claude Code). The same in a
  check's progress, a waiting result and the sidebar's queue panel.
- A follow-up on a result that waits (a stronger model, a second opinion, reading again) now has the button too,
  not only the command to type. The button that stops Claude Code is called **Stop Claude Code**, so it is no longer
  mixed up with a job's own *Stop*.

**Merged with Margin's own work:** the results history keeps both Margin's `draft_id` and ENLENS's
`status_before_stronger`; ENLENS's new styles (`v0112.css`, `v0113.css`) load before Margin's, so Margin's look wins.

**Also:** `tools/sync_enlens.py` fetches ENLENS into a ref of its own (`refs/sync-enlens/head`) instead of the shared
`FETCH_HEAD`, which another fetch had overwritten during the first sync, and stops if the commits it would bring in
are already in Margin's history.

**"Second opinion" everywhere, finished.** ENLENS 0.11.2 renamed the second AI model *second opinion*, but a few
places still said "second model": the job's name in the sidebar and progress panel ("Second AI model"), its progress
lines ("The second model is reading 12 excerpts"), the line under a result ("The second model read all 6 excerpts"),
the two error messages when none is chosen or it is the main model, and a note in Settings. They now say *second
opinion* (or *the model for second opinions*), like the rest.

**Tests:** `tests/test_0112_stronger_model.py` and `tests/test_0113_start_nudge.py` (from ENLENS);
`tests/test_sync_enlens.py` gains two tests for the fix above; `tests/test_app.py` checks the new error wording.
Checked in Chrome in Margin's look: a result a stronger model changed (the mark and its explanation on hover, the two
choices), the Results list and Settings, in light and dark, at 1280 and 390 px, with no console errors and nothing
wider than a phone; a check started from the page with the stand-in Claude Code chosen: *Start Claude Code* pulses in
ink blue after about five seconds with *Nothing runs until you press it.*, and has a still ring with reduced motion.

**Not yet done:** as in ENLENS, tried only with the stand-in Claude Code, not a real signed-in one. The Map does not
show the stronger-model mark yet, and the waiting step still spins until Claude Code takes the work. The "second
opinion" wording fixes are Margin's only; ENLENS still has the old wording in the same places.

## 0.2.1 (November 2026): Update Margin from the app, import hand-zipped projects

**Update Margin** (bottom of the sidebar, beside *Quit Margin*).
- It asks whether a newer Margin waits: the latest GitHub release for the one-line install, or new commits on the
  branch a git copy follows. It says what it found ("Margin 0.2.2 is ready (you have 0.2.1)", or how many changes are
  waiting), and on *Update and restart* installs it the way this copy was installed (`update.py`, as `margin update`
  does), then restarts on the same port; the open page shows that Margin is restarting and reloads by itself once the
  new version answers. If a check or documents being added still run, the dialog says that restarting stops them.
- When a newer version is already on disk (updated in a terminal while this copy ran), the button and the update
  banner offer **Restart now** instead of *Quit Margin*.
- The button appears only where this copy can restart itself (started from its icon or `margin-gui`). On Windows,
  where a running program cannot replace itself, a one-line install says to quit Margin and run the install line.
- New endpoints: `GET /api/update`, `POST /api/update`, `POST /api/restart` (`docs/API.md`). On macOS and Linux the
  restart replaces the running process (same terminal, same Ctrl+C); on Windows it starts the new one beside it.

**Import a project folder zipped by hand.** *Projects → Import a project (.zip)* now takes a project's folder
compressed with Finder's *Compress* or Windows' *Send to compressed folder*, not only zips made with *Download as a
zip*; its documents are pointed at the unpacked copies. A zip holding several projects, or none, says so plainly.

**Fixed on the way.**
- Zips that do not mark their names as UTF-8 (Finder's *Compress*, for one) garbled accented file names
  ("másolat" became "ma╠üsolat"); they are now read correctly, for projects and for documents.
- Projects copied over from ENLENS kept their uploaded documents pointing into ENLENS's folder; they now point at the
  copies in Margin's.
- A checkout used as `MARGIN_HOME` no longer shows Margin's data folders and settings as untracked files
  (`.gitignore`).
- The release workflow: the one-line install test on macOS is now its own job, and the draft release no longer waits
  for it. GitHub's Mac runners were unavailable for three runs in a row, which held up the whole release. Check that
  the Mac job is green (or re-run it) before publishing.

**For developers.** `tools/sync_enlens.py` merges ENLENS's new commits under Margin's names (`--dry-run` lists them
first) and leaves the merge uncommitted so the tests can run before the commit (README, *For developers*).

**Tests:** `tests/test_m021_update_button.py` (the update check and its answers, update and restart, the restart
command, a second click while updating, the hand-zipped import with relinked documents, accented zip names),
`tests/test_sync_enlens.py`, and additions to `tests/test_hypotheses.py` and `tests/test_m010_drafts.py`.

**Not yet done**
- *Update and restart* against a real published release and a real restart from the Mac icon: the tests use
  stand-ins for GitHub, uv and the restart. The first update to 0.2.1 itself is still the old way (`margin update`
  or the install line), since 0.2.0 has no button.

## 0.2.0 (November 2026): Margin's own look

A full re-styling, so Margin no longer looks like ENLENS. Nothing about how the app works changed: every page keeps
its layout, controls, words and steps.

**The look.**
- **Colours:** ink blue (`--accent`, light `#2b4a9b`, dark `#8fa9f0`) replaces ENLENS's teal for buttons, links,
  focus rings and selected items, on a slightly cooler paper; the dark theme is a night ink palette. A new token,
  `--rule` (with `--rule-soft` and `--rule-text` for small text, 5:1 on the paper), is the red margin line: Margin's
  one signature colour, kept apart from the verdict colours (supports, partly, contradicts, mixed, none are
  unchanged, so results read as before).
- **Type:** page and card titles (`h1`, `h2`) and the name in the sidebar are set in the book face already used for
  quotes; the small label above each title, the sidebar group names and table headings are small spaced capitals,
  the page labels in the margin red; each page head ends on a hairline.
- **Shapes:** crisper corners (8 px cards, 6 px buttons and fields), lighter shadows.
- **The sidebar:** its edge is a faint red rule, and the page you are on is marked by a red bar at its left, like a
  note in a margin.
- **The logo and the icon:** a page with its red margin rule and a tick in the margin on an ink-blue tile
  (`static/logo.svg`, drawn the same by `launcher.draw_icon`; `Margin.icns` and `Margin.ico` made again with
  `tools/make_icons.py`). This was 0.1's open item "the icon still shows ENLENS's lens picture".
- The window that shows a document's original text with a quote highlighted, and the annotated copy you can download,
  use the same paper, ink and rule colours.
- All of it is in one new stylesheet, `m020.css`, plus the colour tokens of `app.css`, which every other stylesheet
  already uses, so light and dark both follow.

**Fixed on the way.**
- At phone width, a long button label (*Open an existing Margin project folder (advanced)* on the first screen)
  made the page wider than the screen; buttons now wrap their label below 480 px.
- The tab title and the line under the name in the sidebar said "explore and check your documents"; they now say
  "your writing and your sources", which covers checking a draft.

**Tests:** `tests/test_m020_look.py` (6): the stylesheet is linked after every other one, the margin-rule tokens are
defined for light and both dark settings, the accent is no longer ENLENS's teal anywhere in the page's styles, the
logo is the new one and the icon drawing matches it, the shipped icon files are present, and the page's title. The
pages were looked at in light and dark and at phone width (Overview, Documents, Search, Profile, Concepts, Themes,
Check a draft, Check a hypothesis, Check several, Results, a result, Settings, Projects, the first screen), with no
console errors.

**Not yet done**
- The new icon on a real Mac Dock and Windows Start menu: the icon files are made and installed as before, but an
  icon pinned before the update may keep the old picture until it is pinned again.
- The Excel downloads and the SDG report (`margin report`) keep their own styling.

## 0.1.0 (November 2026): Margin, a writing companion that checks your draft against your sources

Margin is a research and paper-writing companion grown from ENLENS 0.11.1: everything ENLENS did (exploring the
documents, checking hypotheses, per-document AI settings, Claude Code on your own plan) is here, and Margin adds what a
writer needs first: **check a draft**. Its numbering starts again at 0.1.0; the entries below 0.1.0 are ENLENS's.

**Check a draft** (sidebar, *Your writing*; also on the Overview).
- Paste a section, a chapter or a paper, or load it (Word, PDF, text, Markdown, a web page). The draft is kept apart
  from the documents (`drafts` table): it is never searched as evidence.
- **Find the claims.** A new AI task, `claims` (prompt `claims-v1`, Sonnet by default, stepping up to Opus; the
  `margin-reader` helper in Claude Code), reads the draft a few paragraphs at a time (up to 4,000 characters, with
  the end of the part before to say what "it" stands for) and lists the statements a reader would want a source for:
  numbers, causes and effects, comparisons, what research found, general claims, definitions. Not the author's own
  aims, methods, arguments or results. Each claim quotes its sentence, which goes through the quote check against
  the draft (an answer whose quote is not in the text is rejected with the problem listed, as every other answer);
  it is restated as one self-contained sentence and says whether the draft already cites a source there.
- **Without AI**, rules find the likely claims (numbers, "studies show", causal verbs, comparisons, generalisations,
  minus the author's own work, questions, headings, citations and references such as "Table 2"): for a draft marked
  *No AI*, for *Only a local AI* without a local model, and for the offline demo. The page says when rules were used.
- **The person decides.** Drop a claim, reword it before it is checked, or select a sentence in the draft and press
  *Mark as a claim*. *Find again* keeps every claim that was checked, dropped, reworded or marked.
- **Check them.** Each claim kept is checked as a hypothesis of its own (`hypotheses.draft_id`, one set per draft),
  so the result page, reviews, second opinions, Excel downloads and the evidence map all work as before; the result
  page links back to the draft. The draft page shows the text with each claim marked and numbered, coloured by its
  answer, and a card per claim with the documents that support, partly support or contradict it, the best quote and
  its place, and what to do next. *Excel* / *CSV*: one row per claim, a list of what to cite.

**The draft's AI setting, enforced in code.** A draft has the same three settings as a document. Every task that holds
its text (finding its claims, and each task of the checks of its claims: search words, judging excerpts, reading
again, second opinions) is labelled with it by `access.label_payload`, which follows a task's claim or hypothesis to
its draft (`access.draft_of`); a round of excerpts of such a claim goes to the local model or to the person, never
to Claude. Changing the setting relabels the tasks not answered yet. A Claude chat (the connector) does not see the
checks of a draft it may not read. Each time Claude reads part of a draft is recorded (`draft_sent`), and the page
says how much of the draft Claude has read and when.

**Margin, beside ENLENS.** The rename is complete, so the two can be installed on one computer side by side:
- the commands are `margin`, `margin-gui` and `margin-mcp`; the package `margin` (Python module `margin`); the
  data folder `~/margin` (`MARGIN_HOME`, and every other `ENLENS_*` variable is now `MARGIN_*`); the app's default
  address `http://127.0.0.1:8766`; the icon *Margin*; the Claude Code plugin `margin-run@margin` (`/margin-run`,
  helpers `margin-checker`, `margin-reader`…); the Claude app connector `margin`;
- the one-line install and `margin update` take their releases from github.com/dvaud/margin;
- **your ENLENS projects come along**: on the first screen (and on the Projects page) *Bring them over* copies every
  ENLENS project (documents, results, judgements, notes), its codebooks and, on a first start, its settings into
  Margin; each database is copied with SQLite's backup, so a running ENLENS does not spoil the copy; a project ENLENS
  uses in place from another folder is linked, not copied. ENLENS's folder is not changed. Also `margin
  import-enlens [names]`, and `ENLENS_HOME` when ENLENS's data is not in `~/enlens`;
- a project's database keeps its file name (`enlens.sqlite`) and the zips of *Download as a zip* and *Move to
  another computer* keep their format, so Margin opens ENLENS projects and imports ENLENS zips as they are.

**API:** `GET|POST /api/projects/<p>/drafts`, `POST …/drafts/upload`, `GET|PUT|DELETE …/drafts/<d>`,
`POST …/drafts/<d>/find` (job `draft-find`), `POST …/drafts/<d>/check` (job `draft-check`), `POST|PUT|DELETE
…/drafts/<d>/claims[/<c>]`, `GET …/drafts/<d>/export.xlsx|csv`, `POST /api/import-enlens`; `GET /api/state` carries
`enlens` (docs/API.md). The page: `views/drafts.js`, `m010.css`; the manual has a section *Checking a draft*.

**Defects fixed on the way:** an uploaded draft's file title was read from a field that does not exist (the upload
failed); the rules missed numbers with units they did not list ("9 litres"); a link ending in `#token=…` opened
while the page already carried its token showed *No such page* (an ENLENS defect).

**Tests:** `tests/test_m010_drafts.py` (16): the rules, the parts, the quote check of the AI's claims, the person's
changes surviving *Find again*, checks as hypotheses of the draft, a draft kept from Claude never reaching a cloud
model (nor its search words, nor its excerpts), relabelling, the queue handing out only drafts Claude may read and
recording what it read, the offline demo, a PDF draft, the whole API, the page files, and bringing ENLENS projects
over (copied, linked, codebooks, settings, ENLENS untouched). The launcher tests use versions below 0.1.0. The test
stand-in model answers `claims` tasks with the rules.

**Not yet done**
- Not tried with a real signed-in Claude Code or a real local model: how well `claims-v1` finds claims (and leaves
  out the author's own) is untested beyond the stand-in. Worth measuring on a real draft.
- The one-line install of Margin has not run on a real computer yet (the release workflow tries it on Linux, macOS
  and Windows), nor *Set up Claude* adding `margin-run` beside an existing `enlens-run`.
- A draft cannot be edited in place; a new version is a new draft (its claims are found and checked again).
- The icon's picture is still ENLENS's lens.

## 0.11.1 (November 2026): a deep clean after 0.11

No new features. Much had been added between 0.7 and 0.11, so every part of the code was read again for defects,
misbehaviour, redundant code and needless work: the server and the launcher, the checks and the model tasks, the
AI-access guard, the queue and the model backends, the documents and the exploring layer, settings, updating and the
install scripts, the SDG pack, and the page. What follows is what was found and fixed. Every answer still goes
through the quote check, a person can overrule it, every result records how it was made, and `local_only()` is
honoured everywhere (one more place now).

**What Claude may see (three defects of 0.11).**
- A check's written summary was overwritten by the local model's note, because the `:local` part is answered after
  the main part and both stored their rationale on the claim. The summary is shown to a Claude chat through the
  connector's `get_check`, so a local model paraphrasing a licensed passage could have handed its words to the
  cloud. The summary and the model of a claim are now the main part's only (`tasks._store_check`).
- Removing a document never relabelled the tasks still waiting that held its passages (a check by queue, a theme name,
  a concept link), so Claude Code could still be handed the removed document's text. `remove_document` now relabels
  them, as a changed setting does; a task of a removed document counts as *No AI* and leaves the queue.
- The connector's `add_sources` reported a *No AI* document's title in its warnings (`list_documents` hides it as
  *Restricted document 3*). Hidden there too.

**Defects in checks and judgements.**
- A check queued again under a new prompt version (`enlens refresh`) wiped a person's own judgements when the new
  answer was stored. A judgement now survives any second answer, and the earlier AI judgement joins the excerpt's
  history ("answered again").
- The Results list and a result page disagreed about *waiting*: the list looked at the last task row only (with 0.11
  that is usually the `:person` or `:local` part) and never treated a `:local` part not read yet as waiting. One rule
  (`_round_waiting`) for both.
- A judgement on an excerpt no model read (waiting for you) counted as a correction of the AI (the result's
  "Judgements you changed", the Excel summary). It is a review, not a change.
- The single part a person reworded under *Look before checking* was lost when the check went by queue (the wording
  was stored only for two or more parts). Stored for one part too.
- A `:local` part whose answers were rejected three times was invisible: the round said done, the excerpt said read by
  "ai", no error was shown. The result now says so (`local_failed`), lists the technical details, and *Read them again
  on this computer* tries the part once more (`POST …/read-local` retries failed local parts); the progress says it
  while the check runs.
- The progress panel did not know the `note` step 0.11 added (the local model could not be reached, the local
  excerpts were read on this computer): it opened a phantom part and said nothing. Notes are kept and shown under the
  steps (`notes` in the tracker's state).
- `more_passages` reported a wrong round number when nothing more was found (the number of parts plus one).
- The SDG pack's `verify_set` prompt was not told about excerpts read elsewhere when a set was split (the check prompt
  was); it is now.
- The ledger over-reported for a Claude chat: the connector shows the chat the excerpts alone, but the passage before
  each (its context in the app) was recorded as sent. `record_sent(context=False)` for that route; the chat's
  `refers_to` instruction no longer mentions text it is never shown.
- A model test by queue (comparing labels, the benchmark) wrote every passage to the ledger before Claude Code took
  anything, so a test stopped at once still said they were sent. The copy's own ledger is carried into the project's
  afterwards, so only what Claude Code took is recorded.

**Waiting, stopping, claiming.**
- A check waiting for Claude Code never stopped waiting when its document was set to *Only a local AI* meanwhile
  (the task had left the queue; no session would ever answer it). `wait_for` now returns with a plain message.
- *Stop* had no effect while Ollama or another local server was still reading the prompt: the response is sent
  with the first token, so there was nothing to close yet, and the model went on generating the whole answer (and
  the next task queued behind it). The reader now closes the response the moment it arrives.
- The Claude API client retries once at most (the SDK's default of two could hold a task for three times the
  timeout; a Stop in the app took effect only when the call returned).
- `enlens queue run` (answering the queue here) claimed each task unconditionally, overwriting a claim a Claude Code
  session had made in between, so both answered it. It is now the same compare-and-set as `next_tasks`, and a task
  taken meanwhile is skipped.

**Settings, projects, the app.**
- On a `--local-only` installation whose settings file still said `allow_cloud: true` (from before the switch), every
  settings save was refused ("Cloud models are switched off…"), the page sends the stored value back, and the switch
  to clear it is hidden in local-only mode: nothing could be changed at all. `load_settings` now turns both cloud
  permissions off under `local_only()`.
- `POST /api/settings/key` was the one cloud setting that did not honour `local_only()`: 403 now.
- A quick look failed with "Invalid cross-device link" when the data folder is on another disk than the temporary
  folder (Windows `--home D:\…`, a tmpfs `/tmp`), leaving an empty project behind. `shutil.move`, and nothing is left
  on failure. The three raw-body uploads (documents, project zips, quick looks) share one body reader.
- Creating a project whose name was a stale link (the linked folder gone) made the new project at the old external
  path; it is made in the data folder and the link dropped.
- Started from the icon, Ollama was launched only when it was the main AI: with Claude as the main AI and Ollama as
  the local model for restricted documents (or the embedding server), it was not, and *Only a local AI* excerpts
  silently fell to your judgement. It starts whenever any route uses it.
- Numbers in JSON bodies (`k`, `n`, `limit`, `seed`) answered with Python's own message when they were not numbers;
  now "k must be a whole number." like the query values. `start_label_compare` checks the codebook and whether AI
  labels exist before starting a job instead of failing inside it. `GET …/passages/<id>/terms` gives 404 for an
  unknown passage as its siblings do. `POST /api/quit` is documented in `docs/API.md`.
- `enlens prepare theme` made naming tasks whose representatives included *Only a local AI* passages; the queue
  refused them, so such themes were never named. It asks for Claude-readable representatives only, as the app does,
  and counts what was queued. `enlens prepare link` counted pairs for which no task was made. `enlens prepare check
  --file` dropped the `framework` and `code` columns of the CSV. `enlens queue withdraw` without a kind removed the
  tasks of every kind but left the waiting hypotheses behind. `make-tasks audit-vca` re-checked every claim
  (`--sample` defaulted to 1.0 instead of the pack's 0.1).
- `enlens update` on a git copy read the installed extras after the merge, against the new `pyproject.toml`: an extra
  whose packages grew counted as "not installed" and was dropped by the reinstall (OCR or pdfminer silently gone
  after an update). They are read before the merge. On Python 3.10 without `tomli` every extra was dropped (the
  table is now read line by line there). On a detached HEAD the advice was a command git refuses; it says `git
  checkout main`. `update_release` ignored a failed `post-install` and did not pin uv to its own Python as the
  install line does.
- `install.sh` piped uv's installer into `sh`: a failed download went unnoticed and the line ended with "uv was
  installed, but cannot be found". It downloads to a file first and says "Are you online?"; `install.ps1` checks the
  installer's exit code.
- Choosing the Claude API on a one-line install said `pip install 'enlens-claims[anthropic]'`, which a uv tool
  install cannot do; the message now gives the `uv tool install` line for the release's wheel.
- `evaluation.py` had a backslash inside an f-string expression: a SyntaxError on Python 3.10 and 3.11 (the one-line
  install uses 3.12, so it showed only on git copies; four tests failed there). The whole suite passes on 3.11 now.
- A Claude Code plugin file with an opening `---` and no closing one made `check_files` raise instead of listing the
  problem; a `.docx` that is not a zip, has no document inside or holds malformed XML stopped the whole ingest
  instead of being listed under *failed* with the rest going on; a very long "sentence" cut at the length limit lost
  one character where there was no space to cut at.
- The Profile's keyword pass cached each code's denominator by the address of the index's `idf` dictionary; after the
  index was rebuilt (documents added, another project opened) CPython reused the address and the old corpus's
  denominators were used (verified: a coverage of 0.021 where 0.105 was right). The totals now live for one pass.

**Needless work removed (measured on a 150-document, 13,000-passage, one-million-mention project).**
- The label lookups per passage (`WHERE framework=? AND passage_id=?`, two or three per passage in an AI pass) were
  planned over the framework index alone (a project has no statistics): 5.9 ms each at 52,000 labels against 0.014 ms
  with an index on `(passage_id, framework)`, which every project gets on its next open; `DELETE … WHERE task_id=?`
  per answered label task was a full scan (an index on `task_id`).
- Removing a document ran four statements per passage, each a full scan of embeddings, theme members, tasks and
  results (0.62 s for an 87-passage document with 13,000 tasks; tens of seconds on a large project, holding the
  write lock). One set-based statement per table.
- `passages_with_code` (every Search with a code filter) read every label of the codebook (0.47 s at 36,000); the
  code is now in the query. A theme's page read every member of the run with its text (0.115 s per page); only the
  theme's own, merged and moved-in rows are read. The glossary read every mention of the corpus per page (280 ms at a
  million); a term's own document count is kept with it. The term build re-tokenised the same spelling for every
  mention (a third of the build); spellings are cached per build. Term vectors of terms a rebuild dropped stayed for
  good (a few MB a rebuild); pruned.
- A search export ran the whole search once per thousand lines (50 times for 50,000 hits); once now.
- The Results list with a filter ran the five whole-table reads of `history` twice; once, with the counts over all
  and the filter applied in memory. An Excel download computed the history and every result two or three times
  (one sheet each); a `ResultCache` computes them once for all the sheets.
- `_usable_embedder` ran the full embedding status (three counts over the embeddings) per check, per batch item and
  per result page; one row is enough. The document viewer's blocks view also fetched up to 200 passage texts it
  never used. The FlexiConc export was read into memory as a whole (hundreds of MB with embeddings); streamed.
  "Ask a stronger model" probed the model server twice. The quick-look list was rewritten on every `/api/state`.
  `advance_queued` read the settings and built a router per hypothesis per 2-second poll; once per call. Changing a
  document's setting on a big project took seconds because the project's default was re-read per task (1.25 s with
  nothing changed for 8,000 tasks); read once, and unchanged rows are not written. The chain numbering of references
  was O(chains × mentions) after every window; one pass. The FlexiConc themes loop walked every sentence of a
  document per passage; bisection.
- The page: the queue notice (with *Start Claude Code*) was rebuilt on every 500 ms poll, losing focus and letting a
  second click send a second start; the `/queue` request kept being sent for boxes no longer on the page (about two a
  second while Claude Code ran); the "Look before checking" watcher and the Settings watchers (model test, Claude Code
  install) kept polling after leaving the page; a job's end drew the queue panel twice; the Documents table was
  rebuilt (a fresh request) after every setting change, losing the ticks, and the Profile drew twice on load; a
  follow-up on a result fetched it twice.

**Redundant code removed.** `gui/core.py` (a 0.4 alias of `home`), `home._first_chat_model`, `access.split_by_level`,
`llm.OpenAICompatibleBackend`, `_probe` (folded into `models(timeout)`), `OllamaBackend.reserve`, `ingest.doc_text`,
`references.references_table`, `_payload_json`, `stamp`, an unused connection in `profile.compare_sample`, the
`terms_by_doc` cache nobody wrote, `installation.post_install(quiet)`, duplicated name tables (`ROUTE_NAMES`,
`OFF_COMPUTER` live in `routing.py` only), three term-cleaning routines (one, `schema.clean_terms`), two
`round_base`, `_installation` beside `installation.info()`, the no-op entries of `MODEL_JOB_KINDS`, two identical
branches in `analysis.interaction_table`, `REPEAT_SAMPLE`, inner imports of modules already imported, and seven
guards around `make_embedder` that already does the check. In the page: dead exports (`frag`, `iconText`,
`GRADE_VERB`, `FOUND_BY*`, `balanceSentence`, `GRADE_ICON`, `PROMISE`, `plainSection`, the unreachable "starred"
codes), unused imports, five copies each of `plural`/`shortTitle`/`runningJob`/`heatCell`/`jobCard` folded into
`lib.js` and `progress.js`, 74 CSS rules whose classes no file uses (the 0.6 evidence-balance block, the pre-0.9
settings layout, radio cards…), the duplicate rules at the end of `v09.css` folded into their originals, and the nav
`title` attributes `app.js` overwrote. `features.js` marks Documents and Results as *AI optional* (both start AI
jobs: "Let the AI read this document", "Read the new documents", a second opinion). The auditor's name is computed
in one place (`auditorName` in `lib.js`); the typed-model input has a label; the part sections of a result can take
focus. The release's CSS is in `gui/static/v0111.css`.

Tests: 37 new (`tests/test_0111_bug_hunt.py`), one per defect above where it can be shown: the summary after a
chatty local model and the connector's view of it; the queue after a document is removed; the chat's ledger rows;
the hidden title; waiting that ends when the task leaves the queue; a task Claude Code took meanwhile; a model test
stopped before a batch; relabelling only what changed; a person's judgement after a second answer; the list and the
page agreeing; a judgement on a person's excerpt; the reworded single part; the round number; a failed local part
and its retry; the verifier's prompt; local-only with a stale `allow_cloud`; a stale link; the tracker's notes; the
app's plain numbers, 404 and the 403 key; Ollama started for the restricted model; a Stop before the first token;
the API client's retries; the extra hint; `prepare` by queue, `prepare check --file`, `queue withdraw`; the update's
extras and the detached HEAD; the pyproject reader; the installer; a bad Word file; the forced cut; coverage totals;
the indexes and the set-based removal; `passages_with_code`; a theme's passages under merges and moves; the search
export; the front matter; the page files. Two 0.9 and 0.5 tests follow the changes (`history` and `sources` marked
optional; `pick_chat_model` instead of the removed alias; the connector test imports `home`).

**Not yet done.**
- The Stop while a local server reads the prompt, the Claude API's retries and the one-line install's `curl` change
  were tested with stand-ins and by reading; a real Ollama, a real key and a real Mac or Windows were not at hand.
  The install line is exercised by the release workflow on the three systems.
- Two optimisations the review measured were left for later as larger changes: `history()` and `evidence_map()`
  still parse every check task's payload (full passage texts) only to count passages and collect document ids, and
  the term build's `_grams` still tests every token pair (`_edge_ok`); both matter only on projects of hundreds of
  documents.
- `annotate.check_placement` (the F7 acceptance measure) has no caller yet; it stays for that measure.
- Everything in the *Not yet done* of 0.11.0 still stands (a real signed-in Claude Code with `--disallowedTools`,
  the account kind from `claude auth status`, a real local model reading restricted excerpts).

## 0.11.0 (October 2026): per-document AI settings

Until now the choice was all or nothing: `local_only()` switched cloud models off for a whole installation and a
project ran on one route, so a single licensed PDF or interview transcript forced the whole project onto a local
model. 0.11 lets one project mix documents Claude may read with documents that must stay on the computer, and the
code makes it impossible for a restricted document's text to reach a cloud model. The promise, in the app's words:
*Documents you mark as local stay on this computer. ENLENS never sends their text to Claude, in any feature, and
shows you how much of every other document it has sent.* Every model answer still goes through the quote check, a
person can overrule it, every result records how it was made, and `local_only()` is honoured everywhere.

**Three settings per document** (`documents.ai_access`; NULL: the project's default, `ai_access_default` in the
project's config): *Claude may read it* (`cloud`), *Only a local AI* (`local`: a model server on this computer, or a
person) and *No AI* (`none`: a person only; Search, the keyword Profile, Concepts and Themes still work).
- *Adding documents* asks *Who may read these documents with AI?*, one answer for everything added at once. A new
  project asks with nothing preselected; its first answer becomes the default, which is preselected afterwards.
- The Documents page has a column *AI* with a dropdown per document, a checkbox per row to change several together,
  and a note per document (*Why*, e.g. "publisher licence"), kept and exported with the project; it changes nothing.
- `manifest.csv` may have `ai_access` and `ai_note` columns (per file, for large corpora; a wrong value is reported).
- The connector's `create_project` and `add_sources` take `ai_access`.
- A `--local-only` installation defaults to *Only a local AI* and does not offer Claude.

**Enforcement: one guard where tasks are made and run** (new module `access.py`), never an instruction in a prompt.
- `tasks._insert_task` (every task of every feature passes through it) walks the payload for `passage_id` and
  `doc_id` at any depth and stores the most restricted setting in the new column `tasks.access`. A task without
  document text (search words, parts of a hypothesis) is `cloud`; passages of a removed document count as `none`.
- `tasks.run_one` (and `answer_again`, the old `run`, the label comparison, the model test) refuses, before any model
  is asked, a `local` task on a route that leaves the computer and a `none` task on any route (`AccessError`). A model
  server counts as on this computer only at a loopback address (localhost, 127.x, ::1): one on another machine is
  treated like Claude. With Claude Code, a task the queue would never hand out is refused instead of waited for.
- The queue only ever holds and hands out `cloud` tasks (`mark_queued`, `next_tasks`, `status` and the sidebar count
  check `access` too), so Claude Code never sees the rest. The file queue (`enlens export`) writes only `cloud` tasks.
- Changing a setting applies to every task not answered yet (`access.relabel`); a queued task that is no longer
  `cloud` leaves the queue. What Claude already read stays in the results and the ledger.
- Search by meaning: an embedding server on another computer is not given restricted passages (they are found by
  their words; the status no longer counts them as missing).
- The guard is the backstop: features split their work themselves (below), and a feature that forgets fails loudly
  (`tests/test_0110_no_leak.py` proved it by switching the split off: the guard stopped the first task).

**Mixed processing, feature by feature.** Finding passages is unchanged, so restricted documents still compete for
every check on equal terms; only the reading is split.
- *Checking a hypothesis* (one check, several, a further round, documents added since, a check by queue, a check in a
  Claude chat): a round's excerpts are split into the part the main model may read (`check:<id>`, `…:r<n>`), the
  local part (`…:local`, read by the local model for restricted documents) and the person's part (`…:person`, no
  model: its excerpts are stored as *Waiting for your judgement*). The round is shown as one; each excerpt says who
  read it (Claude, the local model, or you), from the provenance already recorded. The overall answer counts every
  excerpt; a model is told how many excerpts of the round it is not shown, so its note speaks only for its own.
  With a main model on this computer, cloud and local excerpts are read together (no split needed).
- A local part whose local model is not chosen, or cannot be reached, waits for a person instead, and the progress
  says so. A check by queue reads its local part in the app while the app follows it; a check made in a Claude chat
  (or while the app was closed) shows *N excerpts wait for the local model · Read them now on this computer* on its
  result (`POST …/hypotheses/<id>/read-local`).
- Excerpts waiting for you are listed under *Waiting for your judgement* (no longer among "not about this"), with
  the judging options open; they have no *Agree with the AI* and no *Ask the AI to read this again*.
- *Second opinion* and *Read again* follow the excerpt's document: a second opinion on a local excerpt only from a
  second model on this computer; reading again a *No AI* excerpt is refused (409) with a plain message.
- *Profile's AI pass*: each passage goes to its document's reader; *All passages* of a local document run locally, of
  a *No AI* document are skipped (`skipped_restricted`). The setting is looked at again before each passage, so a cap
  reached meanwhile takes effect.
- *Theme names*: representatives from documents the reader may read (topped up from the theme's other passages);
  a theme whose passages are all restricted is named by the local model or keeps its key terms. Key terms sent are
  only words found in the passages sent.
- *Concept links*: snippets from documents the reader may read. A term found only in restricted documents is linked
  by the local model, or not at all. The roadmap allowed "from its labels alone", but a term's label is words of the
  documents, so 0.11 does not send it; *Propose wordings* likewise sends only wordings found in documents Claude may
  read.
- *References*: follow the document; a *No AI* document is refused with a plain message.
- *The SDG pack*: `extract` and `verify` follow their passages; `verify_set` splits like a check (`…:local`), and
  passages of *No AI* documents are left out (the pack has no person's judgement of a single passage).
- *Hypothesis parts and search words*: no document text, unchanged.

**The Claude Code run and the connector.**
- The headless run started from the app is denied Claude Code's own tools that read or write files, run commands or
  fetch pages (`--disallowedTools Bash,Read,Grep,Glob,Write,Edit,WebFetch,…`, which holds for the helper agents too;
  `--allowedTools` only pre-approves) and starts in an empty folder (`~/enlens/claude-runs/work/`, emptied first),
  away from the projects' databases, which hold every document's full text.
- The connector's tools filter restricted documents: `search_corpus` gives lines from documents Claude may read and
  the other hits as `restricted_hits`; `find_concept` example lines and wordings only from them; `document_profile` a
  restricted document's codes, shares and pages without quotes; `start_check` and `more_passages` only the excerpts
  Claude may read, the others counted (`restricted_passages`) and left to the local model or the user; `get_check`
  quotes only from documents Claude may read, restricted evidence as counts and verdicts; `list_documents` each
  document's setting, and the title of a *No AI* document as *Restricted document 3*. The queue tools are covered by
  the guard.

**The ledger of what was sent, and a cap per document.**
- New table `ai_sent(passage_id, doc_id, route, task_id, sent_at, feature)`: one row per passage (and per passage
  shown before it as context) at the moment it leaves: before a Claude API call, when Claude Code takes a batch,
  when a Claude chat is shown excerpts or lines through the connector, when the file queue writes a batch. Local and
  person reading write nothing.
- The Documents page column *Sent to Claude* shows the share of each document's text in distinct passages sent;
  clicking it lists the passages with feature, route and date. *Settings → Technical → What was sent to Claude*
  downloads the list as CSV (`GET …/ai-sent.csv`), for records such as a data management plan.
- The cap (the roadmap's stretch goal; shipped because the ledger landed cleanly): *Claude may read at most N %* per
  document (`documents.ai_budget`). Once reached, its further passages count as *Only a local AI* for new tasks and
  *All passages* of the Profile is not sent for it. It is checked when tasks are made.

**Your Claude account.** *Set up Claude* and *Settings → AI* (Claude API) show *What happens to the text Claude
reads*: the account kind when `claude auth status` reports a plan, otherwise a choice (*Pro or Max*, *Team, Enterprise
or the Claude API*, setting `account_type`). Personal plans: consumer terms; training when the model-improvement
setting is on (5 years' retention, 30 days when off), with a link to turn it off. Commercial: no training, 30 days.
EU-only: mark those documents *Only a local AI*. The panel cites Anthropic's Claude Code data-usage page and the date
its wording was checked (30 October 2026); ENLENS decides nothing there. *Settings → AI* also gets *Local model for
restricted documents* (`restricted_server`, `restricted_model`; a model of a server on this computer, or none).

**Upgrading.** A normal commit on `main`; `enlens update` and a reopen are enough, no new venv. Migrations add
`documents.ai_access`, `ai_note`, `ai_budget`, `tasks.access` and `ai_sent`. A project made before 0.11, on its first
open: its default becomes *Claude may read it* (`local` on a `--local-only` installation), so nothing changes silently;
the tasks not answered yet get their setting (a queued one no longer `cloud` leaves the queue); answers given on a
Claude route (from their recorded provenance) enter the ledger with the time of the answer, and the column says
"since 0.11, plus earlier results ENLENS recorded"; the Documents page shows a one-time banner, *New in 0.11: choose
which documents Claude may read*. Project zips (export, import, *Move ENLENS to another computer*) carry each
document's setting and note; importing a zip made before 0.11 asks the question once for all its documents.

**Answers to the roadmap's open questions.**
- The account kind: read from `claude auth status` when it reports a plan (`subscriptionType`, `subscription` or
  `plan`), else the person picks; the field names are not confirmed against a real Claude Code (below).
- The tool restriction: `--disallowedTools` (present in Claude Code for long) rather than `--tools` (newer), so an
  older Claude Code does not refuse to start; not tried against a real one (below).
- *Only a local AI* without a local model: neither silent nor a question at check time. The excerpts wait for your
  judgement, the progress line and the result say so, and *Settings → AI* is where a local model is chosen.
- The cap: shipped in 0.11 (above).
- Titles of *No AI* documents are hidden where Claude would see them (the connector). The app's own exports (Excel,
  project zips) keep them: they are the researcher's files, and a zip must keep them to move a project.

**Usability, on the way.** The new CSS is in `gui/static/v011.css` (colour tokens of `app.css` only; light and dark,
and 390 px wide, checked with screenshots and no console errors). The banner's link to the column *AI* goes to the
first dropdown on a phone, where the table head is hidden.

Tests: 35 new. `tests/test_0110_no_leak.py`: a project with one document per setting, each restricted one carrying a
marker in every sentence; every task kind (search words, parts, check, further rounds, a batch, second opinion, read
again, labels over all passages, theme names, concept links, references, the SDG pack's extract and verify_set, the
file queue) through a recording stand-in for Claude, the queue through the stand-in Claude Code, and every connector
tool; no marker in anything Claude was given, and nothing marked *No AI* reached the local model either.
`test_0110_access_guard.py` (labels at any depth, refusals before the backend, a model server on another computer, the
queue holding only cloud tasks even when forced, a changed setting applied to tasks not answered yet, the default and
the question once, the manifest, the cap, addresses, embeddings on another computer); `test_0110_mixed_check.py` (one
round, three readers, shown as one; no local model; a local model that cannot be reached; a local main model; a check
in a Claude chat read later on this computer); `test_0110_ledger.py` (rows on send only, by route; the share; the cap
stopping further reading; the CSV and the Documents endpoints); `test_0110_upgrade.py` (a 0.10 project opens
unchanged with its ledger backfilled once; on a local-only installation queued tasks leave; zips carry the settings;
a 0.10 zip asks once; the headless run's arguments and empty folder; the account kind from `claude auth status`);
`test_0110_connector.py`; `test_0110_page.py`.

**Not yet done.**
- The headless run with `--disallowedTools` and the empty working folder was tried only with the stand-in
  (`tests/fake_claude_cli.py`). Needs a real, signed-in Claude Code: does `/enlens-run` still work with those tools
  denied (it needs only Agent and the ENLENS tools), and does the version people run accept the flag?
- Whether a real `claude auth status` reports the plan, and under which field name; until then most people pick their
  account kind in the panel.
- A real local model reading restricted excerpts while Claude reads the rest (only stand-ins were used), and a person
  trying the Documents page, the import question and a mixed result with a real corpus.
- The cap is checked when tasks are made. A label pass by queue hands Claude Code batches of up to 20 at once, so a
  capped document can go over by one batch (a check by one round of excerpts).
- The roadmap's acceptance gates for 0.10 still stand (a fresh Mac and Windows account to a finished check).

## 0.10.2 (October 2026): the icon has its picture, and opens the new version

Two problems met right after updating to 0.10.1 on a Mac. No analysis changes: every answer still goes through the
quote check, a person can overrule it, and every result records how it was made.

**The icon has its picture, always.** The ENLENS icon was drawn when it was made, with the Python package Pillow;
without Pillow (a git copy installed without the `ocr` extra) it silently came out as a blank square on macOS and a
plain shortcut on Windows. The picture now ships with ENLENS (`gui/icons/ENLENS.icns`, up to 1024 pixels for the
Desktop at full size, and `ENLENS.ico`), drawn once by `tools/make_icons.py` from the same logo; Pillow is only a
fallback if the files are missing. An icon made without its picture is given it when ENLENS starts
(`launcher.repair_icons`): on macOS the ENLENS app (and only an app made by `--make-launcher`) gets `ENLENS.icns`
and its Info.plist names it, nothing else changes; on Windows, when the data folder has no `ENLENS.ico`, it is
written and the ENLENS shortcuts on the Desktop and in the Start menu are pointed at it. Linux already used
`logo.svg`.

**The icon opens the version that is installed.** After an update (`git pull`, `enlens update`, the install line),
the copy still running was the old version, and double-clicking the icon only showed it again: the new page files
(read from disk) with the old program, so Settings showed the old version number with the new layout.
- Double-clicking the icon while an **older** version runs now quits it, as *Quit ENLENS* would, and starts this
  version (`launcher.is_older`, `launcher.stop_older`; the log says so). When a check or another job runs in it, it
  is left alone and opened, because quitting would stop that work. A newer copy running is just opened.
- `/api/state` says which version is installed now (`installed_version`, read from the package on disk). When it is
  newer than the running one, every page shows *ENLENS X is installed, but Y is still running* with a *Quit ENLENS*
  button, and the version label in Settings shows *Y · X installed*. (A copy older than 0.10.2 cannot say this; the
  icon handles that case.)

Tests: 10 new (`tests/test_0102_icon_and_restart.py`): the icon files (valid ICNS with the 1024-pixel image, ICO
with five sizes, in the package data); the macOS app and the Windows shortcut get their picture without Pillow; a
blank macOS icon repaired, its start script and other apps untouched, and only once; blank Windows shortcuts pointed
at the picture (a stand-in for PowerShell); which running copy is older; quitting it only when nothing runs; two
real launches, the second quitting an "older" first copy and starting in its place; `installed_version` in the
state; the page files. Two 0.10.1 tests no longer pin the version number (the same fix as for the 0.10.0 tests in
0.10.1).

**Not yet done.**
- The repaired and the shipped icon were checked as files here, not shown by a real Finder or Windows Explorer.
  macOS caches icons: a repaired app is given a new date so Finder notices, but `killall Finder` may still be needed.
  The Windows repair (PowerShell setting `IconLocation` on the existing shortcuts) was tested only with a stand-in.
- Replacing an older copy was tested with two real launches on Linux, not from a real macOS or Windows icon.

## 0.10.1 (October 2026): Settings beside Theme and Quit, and the version in sight

A small polish release, and the first made with the new release workflow from start to finish. No analysis changes:
every answer still goes through the quote check, a person can overrule it, and every result records how it was made.

- **Settings moved to the foot of the sidebar,** in one short list with *Theme* and *Quit ENLENS*, under the line
  that says where text goes. The list above now holds only what you do with the documents (Overview, Documents,
  Explore the documents, Check hypotheses); what you set up for the app is in one place at the bottom, on the
  desktop and in the menu on a phone. *Theme* and *Quit ENLENS* are aligned with Settings (same icon width, padding
  and hover) instead of sitting as two small buttons. Settings still shows as the current page on every Settings
  tab.
- **The version on every Settings tab.** The title row of Settings shows *Version X.Y.Z*; clicking it opens
  *Technical → Where your data is*, which says how this copy was installed and how to update it. Before, the
  version was only in that card, three clicks away, so after `enlens update` there was no quick way to see whether
  the new version was running.
- **Fixed on the way: the release tests no longer break on every new version.** Three 0.10.0 tests had `0.10.0`
  written into them (the message after `post-install`, `enlens update` finding a newer release, and
  `tools/release.py check`/`notes`/`assets`), so the first thing any new tag did was fail its own release workflow
  at *Test and build*. They now follow the package's version, with the next patch as the "newer release".
- The release's CSS is in `gui/static/v0101.css` (colour tokens of `app.css` only; light and dark checked, and at
  390 px wide).

Tests: 5 new (`tests/test_0101_settings_and_version.py`): Settings, Theme and Quit together at the foot and Settings
gone from the list of features; Settings still marked as the current page; the version on the Settings page and
its link; `/api/state` and the page carry the version; the page files. The 0.9 test of the sidebar order no longer
expects Settings at the end of the list of features. Three tests in `tests/test_0100_setup_and_moving.py` follow the version (above).

**Not yet done.**
- Everything in the *Not yet done* of 0.10.0 still stands; in particular this is the first tag whose release
  workflow, draft and publish are to be followed through end to end (check *Actions → Release* after the push).

## 0.10.0 (October 2026): from GitHub to the icon in one line

Getting from the GitHub page to an ENLENS icon took eleven separate actions in 0.9.1, seven of them in a terminal
(git, Python, a venv, pip, `--make-launcher`, Claude Code, its sign-in). 0.10 is Phase 1 of the set-up roadmap, with
the parts of Phases 2 and 3 that live inside the app: one pasted line, then one button. No analysis changes: every
answer still goes through the quote check, a person can overrule it, and every result records how it was made.

**The one-line install.**
- `install/install.sh` (macOS, Linux) and `install/install.ps1` (Windows), attached to every GitHub Release with the
  release's version filled in. The line (`curl -fsSL …/releases/latest/download/install.sh | sh`, or `irm
  …/install.ps1 | iex` in PowerShell) gets uv unless it is there, downloads the release's wheel and checks it against
  the release's `SHA256SUMS`, installs it with `uv tool install` into its own Python 3.12 (uv-managed only, so a
  Homebrew upgrade cannot break it; no git, no venv, no pip, no administrator rights), with the `connector`, `fast`,
  `pdfminer` and `ocr` extras, and runs `enlens post-install`: it records how ENLENS was installed, makes the icon,
  repairs the Claude Code plugin, and opens ENLENS. Running the line again updates. `ENLENS_LOCAL_ONLY=1` and
  `ENLENS_HOME=` are built into the icon; `ENLENS_WHEEL=` installs a local build. The PowerShell script never calls
  `exit`, which would close the window `irm | iex` runs in.
- `installation.py`: how this copy was installed (`git`, `script`, `package`, `pip`), from a marker
  `<sys.prefix>/enlens-install.json` the installers write (a git copy needs none). *Settings → Technical* says it and
  how to update. `enlens post-install [--by script|package|pip|none] [--no-icon] [--open] [--home]`.
- `enlens update` follows the installation: a git copy pulls as in 0.8.2; a one-line install asks GitHub for the
  latest release, downloads its wheel, refuses it unless it matches `SHA256SUMS`, installs it with uv in the same
  place (so the icon and the plugin keep their Python) and runs `post-install` from the new version; on Windows, where
  a running program cannot replace itself, it gives the install line instead. A pip install is told about the line.
- **Releases.** `.github/workflows/release.yml` (the repo had no `.github/` and no workflow): a tag `vX.Y.Z` checks
  that the tag, `pyproject.toml`, `__init__.py` and the top CHANGELOG entry agree (`tools/release.py check`), runs the
  tests, builds the wheel, fills the version into the two scripts and writes `SHA256SUMS` (`tools/release.py assets`),
  tries the one-line install of that build on Linux, macOS and Windows runners (the connector must start and offer
  the queue tools), and uploads everything to a **draft** release whose notes are this entry with the install lines
  on top (`tools/release.py notes`). You check the draft and press Publish; the line always takes the latest
  published release. *Run workflow* by hand builds test copies without a release.

**Set up Claude, in one button.** On the first screen and in *Settings → AI*, *Set up Claude* does every Claude step
still open, in order, and skips what is done:
- Claude Code missing: it shows the command of Anthropic's native installer (`curl -fsSL
  https://claude.ai/install.sh | bash`; `irm https://claude.ai/install.ps1 | iex` on Windows) and runs it after you
  confirm, as a background job (`POST /api/claude-setup/claude-code`); a failure says so and links Anthropic's set-up
  page. `find_claude()` also looks for `~/.local/bin/claude.exe` (Windows).
- Not signed in: it opens a Terminal (macOS) or PowerShell (Windows) window, or the first terminal found on Linux,
  already running `claude` (`POST /api/claude-setup/sign-in`), and checks every few seconds until Claude Code says it
  is signed in; *I have signed in* checks at once, *Stop waiting* stops. No window: the line to type. ENLENS still
  never sees the login.
- The plugin: added straight away, with no second button. The checklist ticks each step as it is done.
- *Set it up yourself instead* keeps the three steps to type.
- **The plugin follows the installation.** When the plugin names another Python or another data folder (ENLENS moved,
  or was installed again), the app writes it again on start and runs the two set-up commands again, quietly, in the
  background (`claude_setup.repair()`); `post-install` and `enlens update` do the same. The Claude desktop app's
  connector entry is pointed at this Python when the one it names is gone (`mcp_server.repair_desktop()`).

**Move ENLENS to another computer.** *Projects → Move ENLENS to another computer → Download everything (.zip)*
(`GET /api/move.zip`): every project (each as its own project zip, `bundle.export_all`) and the settings, never a
saved Claude API key; quick looks not kept stay behind; projects used in place come along as copies. The new
computer's first screen offers *Import from another computer*, and *Import a project (.zip)* takes both kinds of zip
(`POST /api/projects/import`). Each project keeps its name (`name (2)` when taken). The settings come along only when
the computer has no project yet (a computer in use keeps its own, and its current project), and on a `--local-only`
installation never the choice of a cloud AI.

**Scanned PDFs: Tesseract offered, and found.** When a scanned page stays without text because Tesseract is missing,
the notice after adding documents, the Documents page and *Settings → Documents* say how to get it on this system
(Homebrew's `brew install tesseract`, the Windows installer the Tesseract project links to, `apt install
tesseract-ocr`), instead of "ask IT to install Tesseract". ENLENS now finds Tesseract where those installers put it
when it is not on the PATH (`ingest.find_tesseract()`; also used for highlighted copies).

**Usability problems fixed on the way.**
- *Check again* on the Claude Code checklist (and every `GET /api/claude-setup?refresh=1`) showed the status of up to
  half a minute before: the query's value is a list, so `refresh` was never seen. Signing in or installing Claude Code
  was therefore not noticed until the cache ran out.
- A Mac app started from its icon has no Homebrew folder on its PATH, and the Windows Tesseract installer does not add
  itself to the PATH: an installed Tesseract was reported missing. See above.
- After a scanned document, "turn it on in Settings" opened the *Checking* tab; the setting is under *Documents*.
- *Copy* on a terminal line (set-up commands, the Tesseract line) said "Paste it in Claude Code"; it names the
  terminal now.

Tests: 21 new (`tests/test_0100_setup_and_moving.py`): the installation kinds and marker; `post-install` (marker,
icon, plugin repaired with the stand-in `claude`); the plugin repaired only when it names another Python or data
folder, never when local only; the Claude desktop entry; `enlens update` from a release (up to date, waiting,
installed with uv, a wrong checksum refused, Windows, offline) and by kind; `install.sh` with stand-ins for uv and
curl (download, checksum, the uv command, `post-install`; a wrong checksum installs nothing; a local package and the
options; the raw script refuses without a version); the PowerShell script's shape; `tools/release.py` and the
workflow; *Set up Claude* through the API (the stand-in installer `tests/fake_claude_installer.py`, the sign-in window,
the plugin; a failed install; local only; `refresh=1`); moving everything (no key, a fresh computer takes the
settings, one in use keeps its own, local only); Tesseract found and offered; the page files. One 0.8.2 test now
expects the pip install's new message. `tools/dev_server.py --claude-install` shows the whole button with
stand-ins; `--no-tesseract` the Tesseract offer.

**Not yet done.**
- The one-line install was run for real on Linux only (uv, a managed Python 3.12, the icon entry, the marker).
  `install.ps1` was not run (no PowerShell in the build environment), and `install.sh` was not run on a Mac: the
  release workflow tries both on GitHub's runners when the tag is pushed; check that run before publishing.
- The install line works only once a release is **published** (`releases/latest`); the draft from the tag must be
  published first. Until then `enlens update` on a one-line install says it cannot ask GitHub.
- *Set up Claude* against a real Claude Code: Anthropic's installer, the sign-in window on macOS (`open -a Terminal`
  with a `.command` file) and Windows (`Start-Process powershell`), and `claude auth status` after signing in were
  tested only with stand-ins. Re-running `claude plugin marketplace add` / `install` after a move relies on both
  being idempotent, as tested with Claude Code 2.1.312 in 0.9.
- Packaged apps (dmg, setup.exe, AppImage), the in-app update button and signing (Phases 2 to 4) are for later
  releases; the marker already knows the kind `package`.
- Gate A of the roadmap (a fresh Mac and Windows account reach a finished check with the line and the button) is
  for a person to run.

## 0.9.1 (October 2026): link buttons readable on hover

- **A primary button made from a link stays readable under the mouse.** On the Overview, *Finish the set-up* (and
  *Set up Claude Code*) turned into an empty teal bar when hovered, most visibly in the dark theme; so did other
  link buttons such as *Add documents* on the first-run page. The general link hover colour (`a:hover`) outranked
  the button's own, so the text took the colour of its own hover background. Link buttons now keep their button
  colours (`a.btn:hover`, `a.btn-primary:hover`, `a.btn-danger:hover`, `a.btn-outline-danger:hover`).
- Tests: 1 new (`tests/test_090_subscription_first.py`): link buttons keep their colours on hover.

## 0.9.0 (October 2026): subscription first, exploring first

0.9 changes no analysis: every answer still goes through the quote check, a person can overrule it, and every result
records how it was made. It changes what a researcher meets first: the AI is Claude on their own plan, set up and
started from the app, and the app opens on exploring the documents, with checking hypotheses second.

**Subscription first.**
- A new installation answers with **Claude Code on the researcher's own Claude plan** (`backend: "claude_code"`,
  `allow_claude_code: true` by default). Nothing is sent before the researcher starts Claude Code (a button or
  `/enlens-run`); then only the passages inside the tasks it takes go to Anthropic. An installation that already
  chose a model keeps it when it is updated (its settings file names it). With `--local-only` the default stays the
  local model (`auto`) and Claude Code cannot be chosen.
- **Set up Claude Code** (first screen, *Settings → AI*): a checklist (Claude Code on this computer, signed in with
  your plan, the ENLENS plugin added) and one button that prepares the plugin and adds it to Claude Code itself, by
  running the two commands a person used to type (`claude plugin marketplace add …`, `claude plugin install
  enlens-run@enlens`; both tested idempotent with Claude Code 2.1.312). What only a person can do (install Claude
  Code, sign in once) is said plainly; *Set it up from a terminal instead* keeps the two lines. `enlens claude-setup`
  does the same from a terminal (`--print-only`: only print them). ENLENS finds `claude` on the PATH or where its
  installers put it; `ENLENS_CLAUDE` names it.
- **Start Claude Code.** Wherever AI work waits (a check, labels, theme names…) and in the sidebar's queue panel,
  *Start Claude Code* starts it in the background for that project (`claude -p "/enlens-run:enlens-run <project>"`,
  allowed only the four ENLENS queue tools and its helpers, run in the ENLENS folder). The page says *Claude Code is
  working on it*, with *Stop*; it stops by itself when nothing waits; *Stop* gives the batches it had taken back to
  the queue at once instead of after 30 minutes; a run that ends with a problem shows the end of its report. The
  first start adds the plugin if that was not done yet. Typing `/enlens-run <project>` in Claude Code still works
  and is shown one line below. ENLENS still never sees the Claude login. **Not yet done:** a run in a signed-in
  Claude Code from the button; the command line was checked against Claude Code 2.1.312 (the skill resolves as
  `enlens-run:enlens-run` with its seven helpers, with the model API blocked), and the whole path with a stand-in.
- *Save and test* on Claude Code says whether it is set up (and signed in) instead of always "working".
- The sidebar's privacy line on Claude Code is the normal case, not a warning: *Claude, on your plan · Only the
  passages of AI tasks leave this computer*.

**Exploring first, clear separations.**
- New **Overview** page, the start page of a project (and of the app): *Explore the documents* first (Search,
  Profile, Concepts, Themes, Read one document), *Check hypotheses* second (Check a hypothesis, Check several,
  Results). Each feature has one line on what it does, one on what it is for, whether it uses the AI, and what is
  already made in the project (a profile, a glossary, a set of themes, results). It also says which AI is in use
  and what is left to set up, and holds *Quick look at one document* (moved from the check page) and *Add
  documents*. `GET /api/projects/<p>/overview` gives the counts.
- The sidebar is ordered the same way: Overview, Documents, **Explore the documents**, **Check hypotheses**,
  Settings. Each feature carries an **AI mark**: filled *AI* (needs the AI: checks), dashed *AI* (works without it;
  the AI can add to it: Profile, Concepts, Themes), no mark (never uses the AI: Search, Documents, Results), with a
  legend under the list and a tooltip saying what the feature does.
- Above every feature's title: the part of the app it belongs to and its AI use (*Explore the documents · No AI
  needed*). One description of every feature (`static/features.js`) feeds the sidebar, the Overview and the titles.
- The welcome screen leads with exploring ("Explore your documents, and check what they say"); its first step is
  the AI (Claude Code, with *No Claude plan? Other options*: a local model, or no AI for now).

**Less clutter, fewer menus inside menus.**
- **Settings as five flat tabs**: *AI*, *Checking*, *Exploring*, *Documents*, *Technical*. In 0.8 the choice of the
  AI was folded inside *Advanced (for IT staff)* together with seven other sections; now it is the first tab, as
  four large choices (Claude Code, recommended; a model on this computer, with the local server as one choice inside
  it; no AI; the Claude API for a team key). Old links to a section open its tab. On the Claude Code route the
  Technical tab leaves out what only a local model uses (the second model, the context length).
- The sidebar shows the jobs box only when there are jobs, and the queue panel only when work waits or Claude Code
  is working; *Theme* and *Quit ENLENS* share a row.
- Profile: the explanation of what a passage is moved into *Technical details*.

**Usability fixes found on the way.**
- The check page's "Set up the AI model" link went to the first-run page even when a project existed; it opens
  *Settings → AI*.
- Switching projects from a theme or concept page returned to that page of the other project, where it does not
  exist; it opens the Overview (as from a result or a document).
- With Claude Code, the AI-labelling and references notes said the passages were sent "to the Claude API"; they now
  say Claude Code reads them on your plan.
- Settings links in Search, Documents and the check options pointed at *Settings → Advanced*; they name the tab.

Tests: 9 new (`tests/test_090_subscription_first.py`): the defaults (and local only), set-up with Claude Code missing
and with a stand-in `claude` (`tests/fake_claude_cli.py`), the run command's allowed tools, *Start Claude Code*
answering a project's queue and *Stop* returning its batches, the overview counts, the model test, and the order and
AI marks of the sidebar. A test never touches a real Claude Code (`conftest.py` points `ENLENS_CLAUDE` nowhere).
`tools/dev_server.py --claude-cli` runs the app with the stand-in.

## 0.8.2 (October 2026): readable heat grids, updating in place

- **The heat grids stay readable on hover.** On *Profile → Documents by goal/target* and on *Themes* (documents and
  codes by theme), the row under the mouse lost its colours: the row hover (`.row-link:hover .map-cell`) outranked
  the heat levels, so the darkest cells showed their white (light theme) or near-black (dark theme) numbers on the
  pale hover background, about 1.1:1, and could not be read. The levels now outrank the hover (`.map-table
  td.pf-cell.pf-lN`, the same for `th-`); the hovered row is still marked by its document cell and its empty cells,
  and a cell under the mouse by its outline.
- **The darkest cell in the light theme is darker** (`--heat-4`, a new token): its white numbers went from 3.3:1 to
  4.7:1 against the background. The dark theme is unchanged (4.7:1).
- **`enlens update`.** ENLENS installed once from a git copy (clone, venv, `pip install -e .`) now updates itself:
  `enlens update` fetches the new version from GitHub into the same folder and moves forward only; it reinstalls
  into the same Python only when `pyproject.toml` changed (keeping the extras already installed), refreshes the
  Claude Code plugin if one was set up, and says to restart the app if it is running. It stops, changing nothing,
  if files of the copy were edited by hand. `enlens update --check` only says whether a new version is waiting.
  The data folder is never touched. See the README, *Updating*.
- Tests: 7 new (`tests/test_082_update_and_grid.py`): the heat levels outrank every row-hover rule, the darkest cell
  has its token in all three theme blocks, and `enlens update` on real git copies (up to date, code only, new
  requirements, local changes, not a git copy).

## 0.8.1 (October 2026): Claude Code for every AI task

0.8 sent every AI button of the app to Claude Code, but three kinds of work still could not use it. They can now.

- **The SDG pack through the queue.** `enlens prepare split|extract|verify-vca|verify-claims|audit-vca` makes the
  pack's tasks (the options of `make-tasks`) and puts them in the queue; `/enlens-run` answers them. The pack's
  tasks still never enter the queue on their own: `make-tasks`, `run` and the file queue are unchanged, and the
  test that the pilot makes no new tasks still holds.
  - Routing (`routing.py`) knows the pack's kinds: extract on Sonnet (stepping up to Opus), split on Opus, verify and
    verify_set on Opus (both stepping up to the auditor). The reasons are in `docs/MODEL_CHOICE.md`. Settings'
    *AI model per task* has a row for each of them.
  - Audits (audit-vca, verify-claims) get the role "audit" (new column `tasks.role`). They are routed like a second
    opinion, to the auditor (or the `--model` given), and they keep that model: an audit never steps up.
  - A seventh helper, `enlens-extractor` (Sonnet), answers extract and split. The checker also answers verify and
    verify_set, and the auditor the audits.
  - The queue: batch sizes for the pack's kinds, which are handed out after the app's own work. A batch's system
    prompt now counts against the connector's 25,000-token cap (extract's holds the 169 targets, about 11,000
    tokens). The other kinds' batches are unchanged.
  - Groups are told apart by helper as well as kind and model. `next_tasks` takes `helper`, and `/enlens-run`
    passes it, so each answer records the helper that gave it.
- **Model tests with Claude Code.** *Compare a sample* of labels and the *Model test* no longer refuse Claude Code.
  Their tasks wait in the queue of a temporary copy of the project, which is removed afterwards
  (`taskqueue.answer_on_copy`), so nothing is stored. The model test answers each kind on its routed model, or the
  alias given.
- **Repeatable answers?** said nothing useful for Claude Code: it called the model directly and failed. It now says
  that Claude Code takes no seed.
- Tests: 8 new (`tests/test_081_claude_code_everywhere.py`), among them a check that every task kind has a model, a
  helper and a batch size on Claude Code. The fake Claude Code passes `helper` like the skill does.

## 0.8.0 (October 2026): Claude Code on your own plan, a model per task

0.8 lets a researcher use Claude Code, signed in with their own Claude plan, as the AI behind every ENLENS task, and
adds the tools to prove on the pilot which model each task needs (G1 to G7 of the 0.8 roadmap). It adds no new
exploring features. The 0.7 rules hold: every answer goes through the quote check, a person can overrule it, and
every result records how it was made. Four rules are added: the researcher runs Claude Code and ENLENS never does;
one queue feeds every AI; each kind of task gets the cheapest model that is good enough; checking itself does not
change.

**The task queue (G1).** *Settings → AI model service → Claude Code (your subscription)*, behind a confirmation
(the passages inside the tasks Claude Code takes are sent to Anthropic). Every AI button then prepares tasks
instead of calling a model: profile labels, concept links, theme names, references, checks, reading an excerpt
again, second opinions and other wordings of a concept. The page says what waits, for example *Waiting for Claude
Code: 120 passages to label · about 25 minutes*, with the command to type and a copy button. The progress moves as
answers arrive, and the result appears as before.
- Tasks in the queue are marked (`tasks.queued`). Tasks of 0.7 and of the SDG pack never are, so `/enlens-run` never
  answers the pack's work.
- A batch handed out is a claim (table `task_claims`: who took it, when, model, helper). Two sessions never get the
  same task, and a claim not answered within 30 minutes lapses: its tasks are handed out again.
- **A check by queue.** The search and the choice of excerpts run in ENLENS at once; only the model's steps wait
  (search words, the split into parts, the judging). Each step is taken when the answer before it arrives, in the
  app or in the connector, so a check finishes even when the app was closed meanwhile. Until then it is listed as
  *Waiting for Claude Code*. Stop withdraws it, as a stopped check leaves nothing behind.
- **The queue panel** (sidebar, under the jobs): per kind what waits, is being answered and is done; the model,
  helper and estimate; *Do first*, *Hold* / *Go on*, *Remove*; the command to type; and the privacy line. When the
  route is not Claude Code, *Answer them here instead* answers the queue with the AI model of Settings.
- The app's waiting jobs do not hold the model's turn, and the app reads the queue every few seconds.
- Command line: `enlens prepare label|link|theme|resolve|check`, and `enlens queue status|run|first|hold|go|withdraw`.
  `queue run --backend anthropic` answers the queue unattended (the shared installation).

**The Claude Code plugin (G2).** `enlens claude-setup` writes the plugin into the ENLENS data folder
(`claude-plugin/`, a marketplace of one plugin), checks that the connector starts and offers the queue tools, and
prints the two lines that add it to Claude Code (`claude plugin marketplace add …`, `claude plugin install
enlens-run@enlens`). Settings offers the same as *Prepare the plugin*. ENLENS writes nothing to Claude Code's own
settings, never starts Claude Code and never handles its login.
- `/enlens-run <project> [kind] [--parallel N]`: the orchestrator skill. It hands each group of tasks (kind and
  model) to a helper agent and reports what is done and what is left. It never reads a task itself.
- Six helpers, each limited to the connector's queue tools: `enlens-labeller` and `enlens-linker` (Haiku),
  `enlens-namer` and `enlens-reader` (Sonnet), `enlens-checker` and `enlens-auditor` (Opus). A task routed to
  another model goes to its helper with Claude Code's per-call model choice.
- The connector gains `queue_status`, `next_tasks` (a claim, the versioned system prompt once, each task's prompt,
  at most about 15,000 tokens a batch), `submit_answers` (every answer quote-checked; per task *stored* or
  *problems*) and `release`.
- The plugin's files were checked with Claude Code 2.1.312 (`claude plugin validate`, installed from the data
  folder: one skill, six agents, one connector). **Not yet done:** a run in a signed-in Claude Code, and a check of
  which model each helper actually ran on (G5). The skill is named so that its command is `/enlens-run`; if Claude
  Code shows it with its plugin's prefix (`/enlens-run:enlens-run`), autocomplete offers it on `/enlens-run`.

**Model routing (G3).** New module `routing.py`. Each kind of task has its own model on all three routes:
- Claude Code and the Claude API: labels and links on Haiku (stepping up to Sonnet), search words, splitting,
  theme names and references on Sonnet (to Opus), judging excerpts on Opus (to the auditor), second opinions by
  the auditor. The auditor is Opus, or Fable when *Let the auditor use Fable* is on.
- Local servers: a small model for labels and links (Settings, `local_small_model`) and the main model for the
  rest. With no small model chosen, the main model does everything and nothing steps up, exactly as in 0.7.
- **Stepping up, once.** A task goes to the stronger model when its answer's certainty (the lowest confidence it
  gives) is under 0.6, when two answers in a row were rejected (the third attempt goes to the stronger model), or
  when a person presses *Ask a stronger model* on a round of a check. Both answers are kept (`results.step`); the
  stronger model's counts. A person's own judgements stay. If the stronger model's answer does not pass, the first
  one stays. With local models the second readings come after the run, so each model is loaded once.
- *Settings → Advanced → AI model per task*: the model, what it steps up to and the helper per kind, a choice per
  kind, *Use the recommended models*, and (Claude API and local) *one model for everything, as in 0.7*.
- On the Claude API the second opinion comes from the auditor, so no second local model is needed.

**Time, limits and stopping (G4).** Claims are small (20 labels, 1 check) and lapse after 30 minutes, so a stop
costs at most one batch and the next `/enlens-run` continues. The researcher's own requests come first, then small
jobs, then the bulk. Estimates come from the measured seconds per task of each kind and model; before any are
measured the panel says so. When answers stop arriving the app says *Paused at 340 of 7,868 labels. To go on, type
/enlens-run Pilot in Claude Code.*

**Privacy and records (G5).** Choosing Claude Code shows what leaves the computer once, with a confirmation, and the
queue panel repeats it. `--local-only` hides the option and makes the connector refuse `next_tasks`. Each answer
records its route, helper, model as set for the helper, prompt version, whether it stepped up and when its batch was
claimed (`results.route`, `helper`, `step`, `claimed_at`). *How these results were made* shows them per kind, says
that Claude Code answers are not repeatable by seed, and counts the answers that stepped up.

**Proving it on the pilot (G6).** New module `evaluation.py`. `enlens acceptance queue --kind K --model M [--again]`
makes a copy of the reference workspace with that kind's sample tasks waiting for that model. The copy keeps each
model's answers apart from the others and from the pilot's. Claude models are answered with `/enlens-run "<copy>"`,
a local model with `enlens queue run`. `enlens acceptance score [--apply]` scores every run: labels by kappa against
f2, links against f3, theme names against a sheet written per model, references against f5, and checks against the
pilot's reference answers and a person's g6 sheet. It also measures repeatability (`--again`) and seconds per task.
It writes `acceptance/MODEL_CHOICE.md`, and with `--apply` makes the cheapest passing model the installation's
default. The team sets the pass marks first (`acceptance/pass_marks.json`). **Not measured yet:** the runs need the
filled sheets and real Claude Code sessions; `docs/MODEL_CHOICE.md` holds the empty report and the current
defaults.

**Carried over from 0.7 (G7).**
- *Cross-Doc in the docs*: no document refers to Cross-Doc users. The user tests note that round 8's testers were
  told they had used it, as a premise only.
- *Letter-spaced PDFs*: for the glossary and key terms, pieces such as "Elec tr oly ser" are read as one word
  when the documents write it whole at least as often and one piece is not a word of its own. The text, search and
  quotes keep the text as read. On the pilot the glossary loses its fragments ("Elec tr oly ser", "tr", "er", "ma",
  "pr") and keeps phrases such as "net zero", and the key terms hold no fragments.
- *Undo for concept links*: removing a link (*Not right*, *No, not the same*) has an Undo, as a rejected code has;
  `PUT …/concepts/links` takes `decision: "undo"`.
- *Theme numbers*: themes are numbered 1 to n in the order shown (`number`), with no gaps after a merge. The stable
  `theme_id` stays for links, edits and the FlexiConc export.
- *Word files*: `.docx` is read with the standard library: paragraphs, headings (Title, Heading 1 to 9), tables
  row by row, pages where Word marked them, and the title from the document properties. A Word file reads like its
  PDF (same text, pages and passages in the tests). Uploads, quick looks and folders accept it; *Open the original*
  downloads it.
- Comparing profiles waits for a later release.

**Tests.** 173 automated tests (21 new). The new ones play `/enlens-run` with a fake Claude Code through the
connector, in process and over MCP, with a wrong quote on the first try of each kind. They check every AI button by
queue, two sessions at once, a lapsed claim, a stop at a random point followed by a new session (every task answered
once, no claim left open), routing on the three routes (the fake Claude API and fake Ollama), stepping up once,
*Ask a stronger model*, local only, the plugin's files (and `claude plugin validate` when Claude Code is installed),
the connector starting as Claude Code starts it, the command line, the SDG pack (0 new tasks on the pilot, none in
the queue), an acceptance run scored end to end, and the G7 items. `tools/dev_server.py --claude-code` runs the app
with a fake Claude Code answering, and `--claude-code-paused` with none.

**Not in 0.8 yet** (the roadmap's gates): a run in a real, signed-in Claude Code; the team's confirmation of the terms;
the G6 runs and pass marks; and the test with two or three real researchers.

### Compatibility

- New columns, added when a project is opened: `tasks.queued`, `queued_at`, `claimed_by`, `claimed_at`, `step`,
  `again`, `forced_model`; `results.route`, `helper`, `step`, `claimed_at`; `hypotheses.queue`; `user_claims.stage`.
  New table `task_claims`.
- New settings: `allow_claude_code`, `use_fable`, `task_models`, `local_small_model`, `routing` (on). On the Claude
  API, search words, splitting, labels and the other kinds now use their own model. `anthropic_model` is the model
  for judging excerpts; switch `routing` off for one model everywhere.
- The SDG pack is unchanged: its tasks are never routed and never queued.
- Prompts are unchanged (`check-v4`, `label-v1`, …).

## 0.7.0 (October 2026): explore the documents; Cross-Doc SDG Explorer replaced

0.7 builds the whole design roadmap (F1 to F8, reproducibility and testing) so that ENLENS does what people used the
Cross-Doc SDG Explorer for. Its outcomes are rebuilt with ENLENS's own parts (keyword index, optional embeddings,
model tasks with checked quotes, review screens); SpanBERT, fastcoref, SciCo, PreSumm, FAISS and Integrated Gradients
are not ported. The core stays light (pydantic, pypdf, openpyxl; numpy with `fast`, pdfminer and OCR as extras). The
SDG pack is untouched: on the pilot, `make-tasks` for every SDG kind creates 0 new tasks.

New pages under **Explore the documents**, and what they replace:

- **Search (F1)**, for Cross-Doc's concordance and token strip: any / all / phrase / near (N words), exact words,
  reference lists on request, per-document counts first, sort by document or by the words before or after, clickable
  words (Shift-click: a phrase), *other forms in the documents* (words the stemmer keeps apart, e.g. *commuters*),
  words nearby (window 2–10, by count or by PMI), Excel/CSV, a check started from a line, search by meaning.
  `textutil.token_spans` gives the tokenizer's words with offsets, so search and checks use one rule.
- **Profile (F2)**, for SDG-BERT's labels: a keyword (and meaning) pass on adding documents gives a provisional
  profile in seconds; the AI pass (task `label`, prompt `label-v1`) confirms codes with a quote and a reason, and says
  how many keyword codes it confirmed, did not confirm, and added. Count by target or goal (`sdg_goals`, 17 codes, is
  bundled), grids, a person's labels (agree, change, reject, add; Undo), calibration, a second-model comparison.
- **Concepts (F3)**, for global coreference and SciCo: a glossary by C-value (running heads and page furniture left
  out), Schwartz–Hearst abbreviations, wordings close in meaning, links judged by the AI (task `link`) and by people,
  concept cards (wordings, documents and first place, lines, related concepts), wordings proposed by the AI that a
  person can accept or refuse for good.
- **Themes (F4)**, for clusters and their summaries: deterministic spherical k-means on embeddings or terms,
  c-TF-IDF key terms, names by the AI with checked quotes (task `theme`), rename / merge / move kept as reviews, grids
  by document and by code, Excel. 2 to 60 themes; a small project gets about three passages a theme at least.
- **References (F5)**, for fastcoref/LingMess: chains followed by the AI window by window (task `resolve`); checks
  (prompt `check-v4`) say what a quote's "it" or "they" refers to, and flag quotes that open with a pronoun and do not.
- **Key terms and reasons (F6)**, for keyphrases and token attributions: key terms per document and passage, the words
  that found each excerpt and each keyword label, the AI's reason with every label.
- **Highlighted copies (F7)**, for `pdf_highlight_post.py`: PDF highlight annotations with exact boxes (pdfminer),
  whole lines (pypdf) or OCR, a note for quotes not placed, HTML copies for other documents; per document, per
  answer (zip) and per document column of the evidence map.
- **Quick look and FlexiConc (F8)**: one document in a temporary project (kept or discarded; trash after 7 days), and
  the project as Cross-Doc's FlexiConc SQLite (`documents`, `sentences`, `chains`, `clusters`, `embeddings`), from the
  Projects page or `enlens export-flexiconc`.

**Reproducibility.** Every model request carries a seed (setting `seed`, 42) at temperature 0; every answer records
the model, its digest (Ollama) or file (LM Studio), the prompt version, the seed and the settings; runs warn when any
of these changed since the last run; *Settings → Advanced → Repeatable results* (and `backend-check --repeatable`)
tests whether a server gives the same answer twice; every Excel download ends with *How these results were made*.

**Also new.** Settings *Exploring the documents* (`profile_framework`, `themes_k`); codebooks marked as aims a text
can help or hinder; the CLI commands `search`, `profile`, `terms`, `concept`, `themes`, `resolve`, `annotate`,
`export-flexiconc`, `acceptance`; the connector tools `search_corpus`, `document_profile`, `find_concept`; benchmark
kind `label`; 38 API endpoints (docs/API.md).

**Measured on the pilot** (38 documents, 8,778 body passages; this computer, no model): the passage index 3 s; a
search under 1 s (median 0.35 s over the 20 most frequent terms, and hit counts equal to a case-insensitive regular
expression for all 20); the keyword pass 12 s; the glossary 22 s (6,000 terms, 87 abbreviation links, 83 concepts);
themes by words about 40 s; the FlexiConc export 13 s. The keyword pass puts 62% of the codes of the pilot's
extraction answers among a passage's top 8 candidates (a proxy for the F2 recall measure).

**Not measured yet** (they need people or a real model): the acceptance measures of F2 to F7 (`enlens acceptance
samples` writes the sheets; the team sets the pass marks first), and the quality of the AI passes with a local model;
the tests run against a stand-in model.

**Tests.** 152 automated tests (19 new for 0.7: offsets, concordance against regular expressions, abbreviations,
running heads, k-means determinism, highlight boxes inside the page, the FlexiConc layout read back, retries after a
wrong quote for every new task kind, the new CLI commands and API endpoints). Two simulated first-time users (round
8, see docs/USER_TESTS.md) found the problems fixed before release: listed there.

## 0.6.1 (October 2026): reasoning within a time limit

A reasoning model could take more than 1,800 seconds on a check of a single document. For example, qwen3.5:9b
writes about 20 tokens a second, may reason for longer than its allowance of 4,096 tokens, then loses its answer
to the output cap and is asked again, up to three times, for every step of the check. 0.6.1 bounds that time.

- **Reasoning only when judging** (`think: "judging"`, *Settings → Advanced → Reasoning: Only when judging
  excerpts*). The model reasons when it judges excerpts: the check itself, *Ask the AI to read this again* and the
  second model. It does not reason when it splits a hypothesis or proposes search words. Those calls stay as fast
  as with reasoning off. Ollama's `think` is a per-request option, so switching it per step does not reload the
  model.
- **A reasoning budget** (`think_budget`, default 1,500 tokens; 0 = no limit). When a model is still reasoning at
  the budget, ENLENS stops that request and asks again without reasoning, giving the reasoning so far as notes. The
  model must still quote only from the passages, and every quote is checked as before. At 20 tokens a second, a
  judgement then takes at most about 75 seconds of reasoning, and an answer is never lost to the output cap. The
  budget applies whenever reasoning is on (`judging`, `on`, or the model's default).
- The progress panel says when the budget was used up ("answering from its notes now"). The model's statistics
  record `thinking_tokens` and `budget_reached`.
- The automatic context length makes room for the budget twice: once for reasoning, once as notes. With
  `judging`, 8 excerpts per check and a budget of 1,500 tokens, it is 12,288 tokens; with reasoning off it stays
  8,192.
- Command line: `--think on|off|judging` and `--think-budget N` (default 1500) on every model command, so
  `enlens benchmark … --think judging` compares a model with and without reasoning on the pilot's tasks.

Whether reasoning helps depends on the model. Small models do not always judge better with it, and it can make
copying quotes word for word worse. Run the test with `--think off` and `--think judging` before relying on it.

## 0.6.0 (October 2026): look before checking, a second opinion, and an icon to start it

0.6 builds the fifteen features agreed after 0.5.1 and adds an icon that starts the app without a terminal. Through
all of them the owner's standing requirement holds: the local model gets as much of the computer as possible.
ENLENS loads no model of its own, makes one model call at a time, keeps heavy tools optional, streams files, and
runs OCR at low priority on one thread.

Two simulated first-time users tested it: a labour sociologist with ten goals covering the new features, then,
after the fixes, a public-administration researcher on the parts that had caused trouble.
- "It is obvious what to do": 7/10 and 7/10.
- "It is obvious what is happening and what the result means": 7/10 and 8/10.

0.5.1's last round gave 8/10 and 6/10. Both testers' findings were fixed (see docs/USER_TESTS.md).

### Model choice and memory

- **Default model.** When no model is chosen, or the chosen one is not installed, the app picks one the server
  already holds in memory (Ollama `/api/ps`, LM Studio `/api/v0/models`), so nothing extra is loaded. Failing that,
  it takes the most recently pulled model, then the first in alphabetical order. The command line does the same,
  and *Test the AI model* says when it fell back.
- **Context length `auto`** (the new default). The app uses the smallest of 8,192, 12,288, 16,384 and 32,768 tokens
  that holds the largest task the settings can produce. That is 8,192 for 8 excerpts without reasoning, which
  frees about 1.2 GB of memory for qwen3:8b compared with 16,384. The length stays the same between requests, so
  Ollama never reloads the model. A request that reads more excerpts at once gets a length that fits, and the
  command line's `run` fits the largest pending task. Settings files of 0.5 hold the old default 16,384: they are
  read as `auto`. A number chosen in 0.6 is kept.
- **Unloading.** `OllamaBackend.unload()` frees a model at once (`keep_alive: 0`). LM Studio and other
  OpenAI-compatible servers have no standard way to unload a model, so there it does nothing.

### Documents

- **Paragraphs and headings** are found when a document is added, without changing its stored text (the SDG pack
  reads exactly the same text and passages as before).
  - Text and web pages: paragraphs are blocks between blank lines, numbered as in 0.5.1.
  - PDFs: a new paragraph starts at each page, at a vertical gap or an indent (positions read in the same
    extraction pass), after a short line that ends a sentence, and at a numbered section.
  - Headings: `<h1>`–`<h6>` in web pages, `#` lines in Markdown, and short lines without closing punctuation
    elsewhere.
  - Quotes in PDFs are cited as "page 2, paragraph 3". Excerpts carry `breaks`, so the app shows their paragraphs
    and bold headings ("…2024 Summary. Remote work…" no longer runs together).
  - Documents added earlier have no layout and look as before.
- **Open the original.** `GET …/documents/<id>/file` serves only the file recorded for the document, resolved
  against the project folder when needed, and streamed. A PDF opens at the page. A text file opens with the quote
  highlighted. A web page is served sandboxed (no scripts, no internet, no access to the app) and scrolls to the
  quote in browsers that support text fragments. When the file has moved or changed, the response says so plainly
  and shows the text the app read.
- **Scanned PDFs.** With the extra `ocr` (pypdfium2, pillow) and the program Tesseract, pages with less than 30
  characters of text are read by OCR. Each page is rendered alone at 200 dpi and freed afterwards, and Tesseract
  runs with one thread at low priority. The settings are `ocr` (auto or off) and `ocr_lang`. The Documents list
  says "Scanned: text recognised (OCR)", or "Scanned: no text. Ask IT to install Tesseract to read it."

### Checks

- **Look before checking** (`POST …/prepare`): the parts the AI would split a hypothesis into and the extra
  search words it proposes, to edit before the check. `check_hypothesis(…, parts=, terms=, edited=)` then skips
  those model calls and records what the person changed (`options.prepared`).
- **About another group.** The prompt `check-v3` lets the AI add a `scope_note` per excerpt ("about fully remote
  workers, not hybrid"). Such an excerpt supports a hypothesis at most partly; the app applies that rule when it
  stores the answer. This costs no extra model call. The SDG pack's prompts are unchanged.
- **Read one excerpt again** (`POST …/claims/<id>/reread/<passage>`). The AI grades the excerpt alone, with the
  person's comment as a hint, and says why. Its earlier judgements are kept (`ai_history`), and a person's own
  judgement still counts.
- **The second sorting pass is off by default.** It re-sorts the best 3 × k candidates by how closely they word
  the hypothesis, without a model. It was evaluated on the pilot first, with 178 VCA claims that have readable
  cited sources (`tools/eval_second_pass.py`). It brought slightly fewer excerpts from the cited sources into the
  top k: 147 instead of 154 at k = 8, and 125 instead of 126 at k = 6. Variants with other weights did not do
  better, so it is an Advanced setting (`second_pass`) and off, as the handoff asked ("keep it only if it does not
  get worse").

### Results

- **Evidence map** (`GET …/map`; *Show as a map*). One row per hypothesis and one column per document, with
  symbols as well as colours. It flags answers that rest on one document, and documents that decide answers
  (leaving them out would change those answers). The all-results Excel file gains a *Map* sheet.
- **Calibration** (`GET …/calibration`; in Settings next to the strictness): how often the person agreed with the
  AI at each band of AI certainty. After 20 judgements it suggests the lowest strictness from which they agreed
  at least 80% of the time ("Use 70%"). An excerpt that was read again is compared on the AI's first judgement.
- **Documents added since a check.**
  - The Results list gets a tag "documents added since".
  - The result page says how many documents were added and how many have matching excerpts.
  - *Read them* reads those documents as a further round. The check is not run again, so reviews are kept.
  - *Read the new documents for all N* does this for every result in one job.
- **A second AI model** (setting `second_model`; `POST …/second-opinion`). Another local model grades the
  excerpts already read, with the same prompt. The main model is unloaded first and the second one at the end,
  so two models are never in memory together. Its judgements are stored apart (table `second_opinions`) and never
  change an answer. Cards show "Second AI model: Contradicts (70%), disagrees", and *Next to review* goes to
  disagreements first. The Results list gets "models disagree on N", and Excel gets columns for it.
- **A project as one zip** (`GET …/export.zip`, `POST /api/projects/import`, `enlens export-project` /
  `import-project`). The zip holds a consistent copy of the database (SQLite's backup API), `config.json`, the
  codebooks, `uploads/`, and the original files kept outside the project. It is written to a temporary file and
  streamed. Import unpacks with the zip-slip guard and a size budget, and points the documents at their files.

### Starting without the terminal

- **`enlens-gui --make-launcher`** puts an ENLENS icon on the Desktop:
  - macOS: an app, also in ~/Applications;
  - Windows: a shortcut that runs `pythonw`, also in the Start menu;
  - Linux: a menu entry.

  The icon calls the Python ENLENS was installed in, so another `enlens-gui` earlier on the PATH cannot get in
  the way.
- **Double-clicking the icon** runs `enlens-gui --launcher`. If ENLENS is already running, it opens it again.
  Otherwise it starts the app in the background, writes its output to `logs/enlens.log`, starts the Ollama app
  when the model service is Ollama on this computer and not running, and opens the browser.
- **Quit ENLENS** in the sidebar (`POST /api/quit`) stops the app. It asks first when a check is running, and
  stopped checks clean up before the app exits.
- Tested on Linux, where the icon was built, run and run again. On macOS and Windows only the icon files were
  checked; a trial on those systems is pending.

### Fixes and smaller changes

- A request body that no endpoint read could be taken for the start of the next request on the same connection.
  Unread bodies are now drained.
- From the user tests:
  - a judged card keeps its place on the screen and says where it moved;
  - *Next to review* moves forward through disagreements, excerpts about another group, then those that count;
    *Next disagreement* cycles through the disagreements;
  - a *Table* view lists every excerpt read with the AI's, your and the second model's judgement;
  - the second model is also compared with your own judgement;
  - marking the sentence you mean waits for your judgement instead of recording agreement;
  - a re-read's hint can be saved as your comment, and the app warns that the AI may simply follow it;
  - every card of a split hypothesis names its part.
- A comment saved without a judgement is a comment, not "you agreed with the AI".
  `PUT …/judgements/…` with `{"verdict": null, "note": …}` keeps it. *Go back to the AI's judgement* now keeps
  the comment, as it says.
- `reset_corpus` now also removes paragraph rows, which were left behind before.
- Files are checksummed in chunks; a large PDF is no longer read into memory to compute its checksum.
- The progress of short jobs lists only the steps they make.

### Compatibility

- New columns and tables are added to existing projects when they are first opened (through `MIGRATIONS`):
  - columns `paragraphs.page`, `documents.ocr_pages`, `documents.scanned_pages`, `verifications.scope_note`,
    `verifications.ai_history_json`, `verifications.reread_json` and `hypotheses.docs_checked_at`;
  - tables `headings` and `second_opinions`.
- Task kinds `reread` and `second`, both using the prompt `check-v3`. The `check` prompt is now `check-v3`;
  results record it.
- The SDG pack is byte-identical to 0.5.1: `clean_page`, `tokens_v1`, the sentence regex, its prompts and its
  answer schemas. A fingerprint of these, and of the text, pages and passages of a test corpus, is unchanged.
- The API additions are listed in docs/API.md ("New in 0.6").

## 0.5.1 (October 2026): an app for researchers who don't program

0.5.0 made ENLENS a local hypothesis checker; 0.5.1 makes its app clear to a social scientist who has never
programmed, using it for the first time on a computer someone else set up.

It was tested that way five times by simulated first-time users (sociologists and a public-administration researcher who
had never programmed), each round fixing what they found (the fixes after the fifth test were checked with scripted
browser flows). "It is obvious what to do" stayed at 8/10; "it is obvious what is happening and what the result
means" went from 4/10 to 6/10. Most of the remaining distrust was about the stand-in AI's wrong judgements in the
test setup, which the app let the testers catch and correct.

- Plain language on every working screen ("excerpt", "judgement", "AI certainty", "strictness", "Mixed evidence");
  model names, ids, tokens and CSV/JSON only under *Technical details* and *Settings → Advanced (for IT staff)*.
- One consistent story on a result: the answer, the documents it rests on (named), who says what, and the evidence
  list always agree; an unreviewed answer is shown as *the AI's first reading*; a caution when it rests on a single
  document or on one or two unchecked judgements; for split hypotheses, which part decides the answer.
- Reviewing like a co-coder: *Agree with the AI* / *Judge it differently* (saves at once, with Undo), comments,
  *Mark the sentence you mean*, *Next to review* (judgements that count first), place kept while cards move.
- Strictness has one home (Settings), says honestly that the AI's certainty is its own estimate, applies to all
  results, and reports which answers and counts changed; *Back to normal (60%)*.
- Looking harder says what it found ("Just now: 5 more excerpts read…"), marks new excerpts, shows the words of each
  search, and says when everything that matches has been read. A search with other words reads only excerpts that
  contain them.
- *Check several* starts as soon as hypotheses are pasted and ends with each answer listed, in the order typed.
- The cloud option sits apart, behind a confirmation; `enlens-gui --local-only` (or `ENLENS_LOCAL_ONLY=1`, or a file
  `local_only` in the data folder) removes it for good.
- `tools/dev_server.py --fresh-user` shows the app as a new user finds it, with a demo corpus on remote work.

### New in the results

- **Your own judgements**: agree with the AI's judgement of an excerpt, change it, comment on it, and point to the
  sentence you mean. Your judgement replaces the AI's in the answer, the counts and the exports, always counts, and
  is kept next to the AI's; the result shows how much you reviewed and how often you agreed with the AI.
- **"Only uncertain evidence"** (`uncertain`): excerpts were judged, but none as surely as the strictness asks. Before,
  this showed as "nothing found".
- **Who says what**, from the same rule as the counts: a document is supporting if one of its counted excerpts
  supports, partly supporting only if none does, contradicting if one contradicts (so it can be on both sides).
- **Locations you can cite**: pages for PDFs, paragraphs for text and web pages ("quote in paragraph 6 of 8"), and a
  document view by page or paragraph that opens at the highlighted quote.
- **Excel downloads**: a summary sheet (one row per hypothesis) and every excerpt read, with who judged it, the AI's
  own judgement and certainty, the quote and who chose it, where it is, comments and notes; local dates.
- Text files take their title from their first line.

### Compatibility

- Status texts are the app's plain words ("Supported by your documents", "Mixed evidence", …); new status
  `uncertain`. Status codes are unchanged.
- New columns (`verifications.user_*`) and a `paragraphs` table are added to existing projects on first open.
  Paragraph locations apply to documents added from 0.5.1 on; older ones show "about 40% into the document".
- `continue_check` / `more_passages` with `terms` read only passages that contain at least one of the terms.
- The API gains `PUT …/claims/<id>/judgements/<passage_id>`, `…/export.xlsx`, `?view=blocks` on documents and
  `local_only` in the state; see docs/API.md.

### Suggested next steps (from the user tests)

- Preview and edit the split into parts, and the AI's extra search words, before a check runs.
- Flag excerpts about another group than the hypothesis names (fully remote vs. hybrid, all ages vs. young).

## 0.5.0 (October 2026): a local-first hypothesis checker

0.4 checked single SDG claims, by default through the Claude API, in a Streamlit app. 0.5 checks **any hypothesis**
against your own documents, **locally by default**, in a new dependency-free app. The SDG / value chain assessment
pipeline of the green hydrogen pilot is kept as an optional pack and gives the same results as 0.4.

### Hypotheses

- **Decomposition**: a hypothesis can be split by the model into 2–5 claims that must all hold; each is searched and
  graded on its own and the verdict combines them (a contradicted part makes the hypothesis contradicted).
- **"Contested"**: support and contradiction above the threshold together (shown as *Mixed evidence* from 0.5.1).
  In 0.4 a single supporting passage made a claim "stated by a source" however many passages refuted it.
- **Evidence balance**: documents supporting / partly / refuting, and a lean from −1 to +1.
- **Rounds in the app**: *Read more passages* and *Search again with other terms* (before, only the connector could).
- **Show in context** (neighbouring passages), **notes** on a check, **remove one document** (past checks keep their
  evidence), a **document viewer**.
- **Batches**: one hypothesis per line or a CSV (comma, semicolon or tab; `hypothesis`, optional `framework`, `code`),
  in the app and with `enlens batch FILE --out results.csv`.
- **Frameworks**: optional codebooks a hypothesis can be tagged with. The 169 SDG targets ship as one; add your own as
  a CSV (`code, description[, group, group_name]`) per project or for all projects.
- Generic prompts (`check-v2`, `expand-v2`, new `decompose-v1`); the pack's prompts are unchanged.
- 0.4 checks are migrated into the new `hypotheses` table on first open.

### Local first

- **Model servers found automatically**: Ollama, LM Studio, llama.cpp, Jan, vLLM (`enlens detect`; backend `auto`, the
  new default in the app and on the command line).
- **OpenAI-compatible backend rewritten**: streams (progress, stall detection, Stop), sends the answer's JSON schema and
  falls back to `json_object` or no format, has `check()` and `models()`, and turns network problems into plain
  messages. In 0.4 it sent only `json_object`, which LM Studio rejects.
- **The Claude API is opt-in**: the app uses it only after *Allow cloud models* (with a notice that passages leave the
  computer); on the command line only with `--backend anthropic`.
- **Semantic search with local embeddings** (optional): Ollama or OpenAI-compatible embedding models, vectors stored in
  the project, keyword and semantic rankings fused (reciprocal rank fusion). `enlens embed`, or *Build semantic index*.
- **Multilingual search**: the tokenizer keeps letters of every language (0.4 turned "économie" into "conomie").
- **The app** (`enlens-gui`, now http://127.0.0.1:8765) is a standard-library HTTP server with a static page: no
  Streamlit, no CDN, no fonts or analytics from the internet. A token per run, Host and Origin checks (no DNS
  rebinding, no cross-site requests), a strict Content Security Policy. `--host 0.0.0.0` serves the network only by IP
  address and hands the token out only in the link printed in the terminal.
- `<think>` blocks of local reasoning models are ignored when reading answers.

### The app

Redesigned from scratch (designed and built by a Fable 5.1 sub-agent against `docs/API.md`): a guided first run
(project → documents; the model is set up once under Settings), a persistent indicator of where text goes, live progress per claim with the model's
activity, a result page built for auditing (verdict, balance, per-part evidence with the verified quote highlighted,
weak grades marked, found by keywords / meaning), history with filters and threshold, batches, sources with quality
warnings and the semantic index, settings incl. frameworks and *Test a model*. Light and dark themes, keyboard
accessible, works down to 380 px wide, no external resources. Long work runs as background jobs that can be stopped.

### Faster

Measured on the pilot workspace (38 documents, 11,312 passages):

| | 0.4.1 | 0.5.0 |
| --- | --- | --- |
| First check (builds the keyword index) | 3.4 s | 1.4 s |
| 30 further checks (offline baseline) | 1.5 s | 0.6 s |
| History of 32 checks | 97 ms | 3 ms |
| Export of all checks | 180 ms | 10 ms |
| `make-tasks verify-vca` | 32.7 s | 3.2 s |
| `make-tasks extract --per-target 6` | 5.0 s | 1.4 s |
| `screen` | 12.4 s | 4.8 s |
| Tokenising the corpus | 3.0 s | 0.9 s (pack) / 1.2 s (hypotheses) |

How: BM25 as an inverted index (a query touches only passages containing its terms; scores bit-identical to 0.4), one
index per set of sources instead of one per VCA claim, per-thread SQLite connections with `synchronous=NORMAL`, indexes
on verifications/tasks/claims, history computed in four queries, a translate-table normaliser, cached stemming,
binary search for page numbers, a thread-safe index cache per corpus state.

### The SDG pack stays as it was

The pack keeps 0.4's tokenizer, sentence splitter and prompts. On the pilot, `make-tasks verify-vca` and
`make-tasks extract --per-target 6` queue no new tasks, the tokens of all 8,778 body passages, the BM25 rankings, the
per-target selection and all 11,312 screen scores are identical to 0.4, and `load-vca` and `match-sources` give the
same results.

### Defects fixed

Found by an independent review of 0.4.1 (each confirmed with a reproduction; regression tests added):

High
- A zip named `...zip` (for example inside an uploaded zip) unpacked into the workspace itself and could overwrite
  `enlens.sqlite` and `config.json`, destroying the project.
- The Turkish capital "İ" shifted every quote offset after it and crashed quote checking when a quote ended at the
  end of a passage; the task stayed pending, so every later `run` stopped at it (also `import-results`,
  `check-results`, the connector's `submit_grades`).
- Re-splitting a justification left the old claim's grades under the same position id (`6.4#1`), so the report showed
  a new claim as supported by quotes graded for another.
- Re-answering an extraction task (`refresh`) undid reviewer decisions; rejected claims came back and never returned to
  the review queue.

Medium
- A failing answer deleted the earlier valid claims of an extraction task (the deletion was committed).
- Two zips with the same file name (from different folders) overwrote each other; one corpus was silently lost.
- The app's *Remove all documents* on a linked pilot also deleted all extracted claims and VCA verifications (now
  refused while pipeline results exist).
- `ingest` held the database write lock for the whole run; checks in the app or connector failed with "database is
  locked" (now one transaction per document).
- `export-tasks` numbered batches by count, so after a batch file was removed the next export overwrote another.
- `tools/pdf_to_text.py` deleted a sources folder called `enlens_text`, and lost one of two PDFs with the same name in
  different subfolders.
- `make-tasks verify-vca` rebuilt the BM25 index for every VCA claim, inside the write transaction (≈12 minutes with
  `--beyond-cited`).
- `review-import` failed on CSVs saved by Excel (byte-order mark, Windows-1252); so did manifests.
- `refresh KIND --model M` switched audit tasks to the main model, so audits compared a model with itself.
- The claim checker's passage index could go stale after removing and re-adding documents (keyed on counts).

Low
- `match-sources` deleted links added by hand (now kept with method `manual`).
- The same claim checked twice within a second raised an IntegrityError (ids were text + second).
- The connector's `create_project` left an empty project behind when the path was mistyped.
- Quotes were rejected when the source had decomposed accents or soft hyphens.
- The zip-slip guard was a string-prefix check (`../src_evil/` escaped a folder `src`).
- Reports of one organisation from different years were merged as one reference.
- Invalid influence values in review imports were stored.
- A results line that is valid JSON but not an object crashed `import-results` and `check-results`.
- The saved API key file was briefly readable by other users.
- Nested zips had no size limit (now one 8 GB budget per ingest).

Found while rebuilding:
- The claim's own words were meant to count double in the search; BM25 ignored repeated query terms, so they did not.
- The tokenizer dropped accented and non-Latin letters, and stemmed inconsistently ("stress"/"stresses",
  "price"/"prices" never matched).
- `backend-check --backend local` crashed (no `check()`); local-server network errors surfaced as tracebacks.
- `check` and `run` with `--backend ollama` used the Claude model name stored in `config.json` ("Ollama has no
  model claude-opus-5-5").
- Re-storing an extraction deleted stated interactions with a `LIKE` prefix that also matched other tasks
  (passage numbers ≥ 10,000; `_` in ids).
- One unreadable file aborted a whole ingest, and nothing of that run was saved.
- A failed capability lookup was cached, so Ollama's reasoning setting was ignored after Ollama started late.
- The checker's index cache was cleared on every miss (projects evicted each other) and was not thread-safe.
- File names in the documents table kept Windows paths.

A second review of the 0.5 code before release found and fixed twelve more (among them: parallel jobs failing with
"database is locked" under deferred transactions, `--host` handing out the token, path checks on framework deletion
and uploads, Stop not reaching the Claude API, semicolon CSVs, overlapping ingests).

### Compatibility

- `enlens-gui` no longer needs Streamlit; the `gui` extra is empty. New extra `fast` (numpy).
- Default backend is `auto` (local). For the 0.4 behaviour pass `--backend anthropic`. Settings of a 0.4 install that
  used the Claude API with a key keep it (cloud allowed); otherwise the app starts local.
- Status texts: "Stated by a source" is now "Supported by a source"; new status `contested`.
- `claimcheck.check_claim`, `result`, `history`, `open_check`, `submit_grades`, `more_passages` keep their signatures
  (history rows gain `hyp_id`, `parts`, `lean`); `gui.core` re-exports `home`.

### Suggested next steps (not in 0.5)

- Pick the default local model by recency (Ollama reports when each model was pulled) instead of alphabetically.
- An evidence map after a batch: hypotheses × documents, to spot verdicts that rest on one source.
- Export and import a project as a zip, to back up or share a corpus with its checks.
- Local OCR for scanned PDFs (ocrmypdf) during ingest.
- A local reranker (cross-encoder) after the hybrid search.
- A calibration view: your agreement with grades at each confidence, to set the threshold.
- Re-check hypotheses whose verdict may change after new documents are added.
- Grade with two local models and flag disagreements.
