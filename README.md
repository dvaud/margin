# Margin: write with your sources beside you

Margin is a research and paper-writing companion: it finds the claims in your draft that need a source and shows
which of your documents support or contradict each, checks that the sources you cite say what you say, helps you
explore those documents, and checks a hypothesis against them, with every quote checked against the source. It runs on your computer, with Claude on your own plan or
a local model. It grew out of ENLENS, and can sit beside it on the same computer.

## Install

1. **Paste one line.** On a Mac or Linux, open *Terminal*; on Windows, open *PowerShell*. Paste the line for your
   system and press Enter:

   | System | Where | Paste this |
   | --- | --- | --- |
   | macOS, Linux | Terminal | `curl -fsSL https://github.com/dvaud/margin/releases/latest/download/install.sh \| sh` |
   | Windows | PowerShell | `powershell -ExecutionPolicy Bypass -c "irm https://github.com/dvaud/margin/releases/latest/download/install.ps1 \| iex"` |

   It needs no git, no Python and no administrator rights. When it is done, Margin opens in your browser and its
   icon is in the usual place (macOS: Applications and Desktop; Windows: Start menu and Desktop; Linux: the
   applications menu). **Or download a file and double-click it:**
   [Install-Margin-Windows.cmd](https://github.com/dvaud/margin/releases/latest/download/Install-Margin-Windows.cmd)
   on Windows,
   [Install-Margin-macOS.zip](https://github.com/dvaud/margin/releases/latest/download/Install-Margin-macOS.zip)
   on a Mac. Windows and macOS ask you to allow it the first time:
   [how](docs/manual/install.md#or-download-a-file-and-double-click-it).
2. **Press *Set up Claude*** on the first screen. It installs Claude Code if it is missing (it shows you the command
   first), opens a window where you sign in once with your Claude plan, and adds the Margin plugin (beside the ENLENS
   one, if you have it).
3. **Bring your ENLENS projects, or start a new one.** If ENLENS is on this computer, the first screen offers to copy
   its projects into Margin (ENLENS keeps its own). Otherwise name a project and add your documents (PDF, Word, web
   pages, text, or a zip of them); Margin asks who may read them with AI: *Claude may read them*, *Only a local AI*,
   or *No AI*. Using Zotero? The *Bibliography* page brings in a collection and the PDFs Zotero keeps.
4. **Check a draft, explore, check.** Where AI work waits, press **Start Claude Code**; the results appear as they
   come in.

Used Margin on another computer? Choose *Import from another computer* on the first screen (on the old computer:
*Projects → Move Margin to another computer*). No Claude plan? See *Other ways to run it* below.

## Update

When a new version is out, **Update to 0.x.y** appears at the bottom of the sidebar, with a note in the corner the
first time: click it and Margin installs the new version and restarts by itself, on Windows too from 0.15 on (the
update *to* 0.15 on Windows is still made by hand, below). *Settings → Technical → Updates → Check for updates* looks
at once. Or do it by hand:

1. **Quit Margin** (*Quit Margin* at the bottom of the sidebar). On Windows, close Claude Code too.
2. **Get the new version:** in Terminal or PowerShell type `margin update`, or run the install line or file again.
   On Windows, use the install line or double-click the newest `Install-Margin-Windows.cmd`.
3. **Open Margin again** from its icon.

Your projects and settings (in the folder `margin` in your home folder) are never touched. Installed from a git copy
instead? `margin update` pulls the new version (see *For developers*).

## New in 0.15: a new reader, and a manual of short pages

- **A new reader** for documents you add from now on: two columns are read in order; running heads, page numbers,
  author details, acknowledgements, footnotes and the reference list are set aside; tables stay tables; words broken
  over lines are joined. Text copied out of a PDF, and books, lose their clutter too. **Can change results** for new
  documents; those already in a project keep their reading.
- **See how each document was read** ([How documents are read](docs/manual/reading.md)): the text as the reader
  found it, the PDF page beside it, and a warning when it read badly. *Leave out* or *Restore* any part, every running
  head at once with *All like this*, or mark where the text starts and ends. *Read with the new reader* moves an older
  document, or several, with their quotes, judgements and codes.
- **Results say which Margin made them**, and large projects are quicker: documents are read three at a time, and
  search, the glossary and the Profile page do less work for the same answer.
- **Claude Code works in a box of its own**: no tool that could open your files, and nothing from your own Claude
  Code set-up. **Ollama with one button** for a model on your own computer. **Windows**: *Update* installs by itself,
  the install waits for Claude Code to close, and user folders with accents work.
- **The manual is a start page and a short page per task**, with pictures of Margin: [docs/MANUAL.md](docs/MANUAL.md).

Full notes: `CHANGELOG.md`.

## Earlier releases

- **Margin 0.14**: an outline from your research question (each hypothesis a section with the themes that bear
  on it); install by double-clicking a file (from ENLENS 0.14.5).
- **Margin 0.13**: a review of the whole app brought in from ENLENS 0.14.3 and 0.14.4: a check says when it did not
  work, stricter quotes, more care with restricted documents, and sturdier adding of documents.
- **Margin 0.12**: your draft read against itself without AI (sentences that disagree, two numbers for one thing,
  abbreviations, spellings, confusing claims); a local model that waits for free memory (0.12.1); tidier claim cards
  (0.12.2); `/margin-run` waits for its helpers (0.12.3).
- **Margin 0.11**: *Skim*, a one-page report on one document made without AI, which a quick look now opens; Find
  literature's styles back on a computer screen.
- **Margin 0.10**: an outline to write from, made from your themes (sections with key terms, passages, sources to
  cite and where they disagree; beside a draft, what it still misses; Word or Markdown), and *Find literature* for
  claims no document backs, the works your documents cite, and saved searches, straight into Zotero.
- **Margin 0.9**: social practice theory as a codebook (practices, their elements, and whether a passage holds a
  practice together or pulls it apart), codebooks of ideas rather than words; 0.9.1 a speed for Claude Code, models
  that follow your Claude plan, and only the Zotero works you choose (from ENLENS 0.13.9 and 0.13.10).
- **Margin 0.8**: no codebook until you choose one; the SDG codebooks stay as built-in examples, and the
  green-hydrogen pipeline of the ENLENS pilot is gone from what you see.
- **Margin 0.7**: remove a theme you do not need, and find a new one in its place, on your computer without AI.
- **Margin 0.6**: check your citations against their sources: a draft's citations are found, checked against the
  cited work's own document and shown where you write; a model on this computer without a terminal, and an update
  button that shows only when there is an update (from ENLENS 0.13.6 and 0.13.7).
- **Margin 0.5**: APA 7 citations to paste from your draft: every document a claim would cite has its citation on a
  button that copies it, one for all of a claim's sources, as your reference list would write it.
- **Margin 0.4**: your Zotero bibliography beside your documents (each work linked to its document, the works still
  to find, the PDFs Zotero keeps added in one go, proper titles); a result page you read at a glance and calmer
  pages everywhere; which Claude account answers; checks on Sonnet (from ENLENS 0.12 and 0.13).
- **Margin 0.3**: decide on each claim of your draft (*Claim supported*, *Claim refuted*, *Dismiss claim*); the
  draft shows where to cite, and the claims scroll on their own.
- **Margin 0.2**: Margin's own look (ink blue, a book face for titles, a red margin line for the page you are on)
  and icon; *Update Margin* from the sidebar and hand-zipped project imports (0.2.1); a stronger model's answer
  becomes the answer, *second opinion* everywhere, and a *Start Claude Code* button you cannot miss (0.2.2, from
  ENLENS 0.11.2 and 0.11.3).
- **Margin 0.1**: check a draft: the claims of your writing that need a source, and which of your documents
  support or contradict each; Margin gets its own name, command, data folder and icon beside ENLENS, and copies
  your ENLENS projects over in one click.

### As ENLENS

- **ENLENS 0.11**: per-document AI settings (*Claude may read it*, *Only a local AI*, *No AI*), enforced in every
  feature, with a record of what Claude read; 0.11.1 a deep clean.
- **ENLENS 0.10**: install with one pasted line and update with one command; *Set up Claude* in one button; move
  every project to another computer.
- **ENLENS 0.9**: subscription first (Claude Code on your own plan is the AI) and exploring first.
- **ENLENS 0.8**: Claude Code answers every AI task through a queue, with the right model for each kind of task.
- **ENLENS 0.7**: explore the documents (search, codebook profiles, concepts, themes, references).
- **ENLENS 0.5 and 0.6**: the hypothesis checker: checked quotes, your own judgements, a second opinion.

The full notes of every release are in `CHANGELOG.md`.

## What Margin does

Margin reads your sources (reports, papers, policy documents, interview notes) and helps you find your way through
them before you claim anything: every place a word occurs, the codes of your own codebook (or a built-in one) each
document addresses, a glossary of terms grouped into concepts you can follow from one document to the next, themes
across the documents, what "it" and "they" refer to, and highlighted copies. Most of that needs no AI at all; what the AI adds is quoted, checked against the text, and yours to overrule.

When you write, Margin reads your draft the same way: it marks the statements that need a source and checks each one against your documents, so you see which claims they back, which they contradict, and what to cite. It turns your themes into an outline to write from, and finds works to cite for the claims your documents do not back.

When you have a statement to test, Margin also checks it: supported, partly supported, contradicted or mixed
evidence, with the exact words of each source, where they are (page or paragraph), and a quote checked character by
character against the source text. You review the AI's judgements like a co-coder's; your judgements count and are
kept next to the AI's in the Excel download.

The AI is Claude, through Claude Code signed in with your own Claude plan (Pro, Max, Team or Enterprise). Margin
sets Claude Code up by itself and starts it when you press *Start Claude Code*; each kind of task goes to the right
model (labels on Haiku, theme names and checks on Sonnet, second opinions on Opus). Your documents, results and
reviews stay on your computer: only the passages inside the AI's tasks, from documents Claude may read, are sent to
Anthropic, and the search words you see before you search for literature go to OpenAlex. A model on your own computer (Ollama, LM Studio…) and a shared installation on the Claude API remain
available, and whoever installs it can switch everything off the computer off for good (`--local-only`).

The app is written for researchers who do not program: plain language on every working screen; each feature says
what it does and whether it uses the AI; technical details are kept under *Technical details* and
*Settings → Technical*. It grew out of ENLENS, which grew out of the Cross-Doc SDG Explorer and a green hydrogen
pilot.

## Other ways to run it

What the install line does: it gets [uv](https://docs.astral.sh/uv/) (which brings its own Python 3.12), downloads
the Margin package of the latest release, checks it against the release's `SHA256SUMS`, installs it, and makes the
icon. `MARGIN_LOCAL_ONLY=1` or `MARGIN_HOME=<folder>` before the line are built into the icon. Instead of the button,
`margin claude-setup` sets up Claude from a terminal, and `/margin-run <project>` in Claude Code answers a project's
waiting work yourself.

No Claude plan? Choose *A model on this computer* (first screen or *Settings → AI*): get Ollama (free), open it,
and *Download qwen3:8b* gets a model with one button (*Also nomic-embed-text* adds search by meaning). Other local
model servers work too (LM Studio, llama.cpp, Jan, vLLM); from a terminal: `ollama pull qwen3:8b`.

Installing it for someone else: the install line, on their account (*Quit Margin* in the app stops it);
`MARGIN_LOCAL_ONLY=1` removes every option that sends text off the computer. Scanned PDFs need the program
Tesseract; the app says how to get it on that system when it meets a scanned page.

From the command line:

```bash
margin --ws myproject init
margin --ws myproject ingest ~/Reports/                    # PDFs, Word (.docx), HTML, text, Markdown, zips
margin --ws myproject search "commuting emissions" --mode phrase --out hits.csv
margin --ws myproject profile --framework remote --keywords-only --out profile.xlsx   # codes per document, no model
margin --ws myproject themes --k 20 --out themes.xlsx
margin --ws myproject prepare label                         # AI work for Claude Code; then /margin-run myproject
margin --ws myproject check "Remote work lowers commuting emissions in large cities." --decompose --backend ollama
margin --ws myproject batch hypotheses.csv --out results.csv --backend ollama
margin detect                                               # which local model servers are running
```

`margin prepare label|link|theme|resolve|check` prepares AI work for Claude Code from the command line, and `margin
queue status|run` shows it or answers it here (`--backend anthropic` for a shared installation). Inside the Claude
app (Claude reads on your plan; only the passages shown leave the computer): `margin-mcp --install-claude-desktop`.

## For developers (a git copy)

Install Margin once from its git copy, and every later version is one command, in the same folder and the same
venv (the data folder, `~/margin`, is never touched):

```bash
git clone https://github.com/<you>/<repo>.git ~/margin-app && cd ~/margin-app   # once
python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[connector]'
margin-gui --make-launcher                                                       # once: the Desktop icon

margin update            # later: fetch the new version (add --check to only look)
```

Because the install is editable (`-e`), the app runs the code in that folder: `margin update` pulls the new version
and reinstalls only when its requirements changed. Then open Margin from its icon: an older version still running is
quit and the new one started (ENLENS 0.10.2), and if something still runs in it, the page says to quit and reopen. Run
it as `~/margin-app/.venv/bin/margin update` if the venv is not active.

**Bringing in ENLENS's work.** Margin keeps ENLENS's history, with ENLENS as the git remote `enlens`. Run
`python tools/sync_enlens.py --dry-run` to see what is new in ENLENS. Then run `python tools/sync_enlens.py` to
merge it: the tool rewrites ENLENS's new commits with Margin's names and leaves the merge uncommitted, so you can
run the tests before you `git commit`. Margin's README, changelog and version numbers stay its own; the tool lists
ENLENS's changes to them so you can copy over what Margin needs.

## Exploring the documents (the main part of the app)

| Page | What it gives | Model? |
| --- | --- | --- |
| Search | Every place words occur, with the words around them; phrases, near, other forms, words nearby; Excel/CSV | no |
| Profile | The codes each document addresses, how much and where, with the words or quote and reason behind each | keywords first; the AI confirms |
| Concepts | A glossary of terms grouped into concepts (abbreviations, wordings, your links); where each appears | optional |
| Themes | Themes across the documents, by document and by code; rename, merge, move | optional (names) |
| A document | Codes, key terms, references ("it", "they"), search, a highlighted copy | references only |

The *Overview* page (the start page of a project) shows these first, each with what it does, whether it uses the
AI and what is already made; checking hypotheses comes second. In the sidebar a filled **AI** mark means the feature
needs the AI, a dashed one that the AI is optional, and no mark that it never uses the AI.

Where the parts of the Cross-Doc SDG Explorer went:

| Cross-Doc | Margin |
| --- | --- |
| Single-document concordance (AND / OR), token strip | Search (any / all / phrase / near), across all documents or one |
| SDG classifier, dual consensus | Profile: keywords and meaning first, the AI confirms with a quote and a reason |
| Explainability (integrated gradients, span masking, keyphrases) | Key terms per document and passage; the words and reason behind every label |
| Coreference (fastcoref, LingMess) | References in a document (the AI follows "it" and "they"); checks say what a quote's "it" is |
| Global coreference (trie) across documents | Concepts: one concept followed across every document, with its wordings |
| SciCo clusters, communities and summaries | Themes, named by the AI with checked quotes |
| `pdf_highlight_post.py` | Highlighted copies of a document, an answer, a column of the evidence map |
| FlexiConc SQLite | Not offered by Margin (ENLENS has it) |

Every model answer records the model, its exact version (digest), the prompt version and the seed (42 by default,
temperature 0); every Excel download ends with *How these results were made*. Since 0.8 it also records the route
(Claude Code, the Claude API, a local server), the helper, and whether the answer came from the stronger model.

## What a check does

1. *(optional)* The model splits the hypothesis into the claims that must all hold ("decompose").
2. *(optional)* It writes search terms for each claim: synonyms, technical words, the opposite phrasing.
3. The best passages are picked by keywords (BM25), fused with semantic search when the project has embeddings,
   at most a few per document so one long report cannot fill every slot.
4. The model grades each passage that bears on the claim: supports, partly supports, refutes, with a quote and a
   confidence. Every quote is verified against the passage; answers that fail are retried with the problems listed.
5. The answer counts the judgements the AI is sure enough about (the *strictness*, 60% by default) and yours:
   **supported**, **partly supported**, **mixed evidence** (`contested`), **contradicted**, **only uncertain
   evidence**, or **no evidence found**, with who says what per document. A split hypothesis combines its parts
   (every part must hold), and the app says which part decides.

You can look at the parts and search words before a check runs and change them, review and correct every judgement,
ask the AI to read one excerpt again with your comment, ask a second local model for its judgements and see where
the two disagree, look for more evidence or search with other words, read documents added later without losing your
reviews, open the document at the quote (by page and paragraph) or the original file, see all results as a map of
which documents decide which answers, see how often you agree with the AI at each certainty, add notes, download a
result or all results for Excel (summary, every excerpt with who judged it, the map) or as CSV/JSON, and hand the
whole project to a colleague as one zip.

## A model per task (ENLENS 0.8)

| Task | Claude Code and the Claude API | Steps up to | Local |
| --- | --- | --- | --- |
| Codebook labels, concept links | Haiku | Sonnet | the small model (if chosen) |
| Search words, splitting, theme names, references | Sonnet | Opus | the main model |
| Judging excerpts, reading one again | Sonnet (high effort) | the auditor | the main model |
| Second opinion | the auditor (Opus, or Fable if switched on) | | the second model |

A task steps up once: when its answer's certainty is under 0.6, after two rejected answers, or when you press *Ask a
stronger model*. The defaults are starting points until the runs on the pilot (`margin acceptance queue|score`,
see docs/MODEL_CHOICE.md) set them.

## Privacy

- Claude Code (the default from 0.9) runs on your own Claude plan. Margin never sees its login: Claude Code uses its
  own. Started from the app, it may use only the four Margin queue tools and its helpers (`--allowedTools`), is
  denied its own file, shell and web tools (`--disallowedTools`, 0.11) and starts in an empty folder; only the
  passages inside the tasks it takes are sent to Anthropic. Stop it at any time; what it had taken waits again.
- Documents marked *Only a local AI* or *No AI* (ENLENS 0.11) are never sent to Claude: every task is labelled with the most
  restricted setting of the documents it names and refused before a model it does not allow is asked; the queue
  hands Claude Code only what Claude may read; the connector gives Claude counts instead of their text. Every passage
  that does go to Claude is recorded (*Sent to Claude* on the Documents page, a CSV under *Settings → Technical*).
- A model on this computer keeps every word on it. The Claude API is available only after *Allow cloud models* is
  switched on (or `--backend anthropic` on the command line). `--local-only` hides both cloud options for good.
- The app is a small standard-library server on 127.0.0.1 with a per-run token; the page loads nothing from the
  internet (no CDN, fonts or analytics). No Streamlit, no telemetry.
- *Find literature* (0.10) is not AI, but it does send words off the computer: the search words you see and edit
  first (to OpenAlex, and to Crossref, Semantic Scholar or Unpaywall if you choose), or your documents' DOIs to follow
  their citations. Never from a draft or document that Claude may not read, never the text of one, and never with
  `--local-only`. A contact e-mail is sent only if you give one in *Settings → Exploring*.
- Projects are plain folders with one SQLite database; settings live in `~/margin` (or `MARGIN_HOME`).

## Documentation

- [docs/MANUAL.md](docs/MANUAL.md): the manual, a start page and a short page per task (installing, exploring, your
  writing, checks, privacy and the AI, settings, the command line).
- [docs/API.md](docs/API.md): the local app's HTTP API.
- [CHANGELOG.md](CHANGELOG.md): what changed in each release (ENLENS 0.5 to 0.11.1, then Margin from 0.1.0, which takes in ENLENS 0.11.2 and later), including the defects fixed.
- [docs/USER_TESTS.md](docs/USER_TESTS.md): the first-time user tests behind the app (0.5.1 to 0.7.0).
- [docs/MODEL_CHOICE.md](docs/MODEL_CHOICE.md): which model each task needs, measured on the pilot (ENLENS 0.8: the method
  and the empty tables, until the runs are made).

## Layout

| Module | Role |
| --- | --- |
| `claimcheck.py` | Hypotheses: decomposition, checks, statuses, a person's judgements, who says what, rounds, re-reads, second opinions, new documents, the evidence map, calibration, batches, history, Excel |
| `search.py`, `embed.py`, `retrieve.py` | Cached keyword index, local embeddings and hybrid ranking; BM25 (inverted index) |
| `frameworks.py`, `taxonomy.py`, `data/codebooks/` | Optional codebooks (your CSVs; built in: social practice theory and framings of change, written by `tools/make_practice_codebooks.py`, and the SDG targets and goals as examples) |
| `llm.py` | Ollama, OpenAI-compatible local servers (LM Studio, llama.cpp…), server detection, Claude API, offline baseline |
| `tasks.py`, `schema.py`, `prompts.py` | Model tasks, validation with the quote check, versioned prompts |
| `bibliography.py` | The bibliography (ENLENS 0.13): Zotero read through its local API, BibTeX / RIS / CSL JSON / CSV files, matching works with documents, titles from the linked work |
| `outline.py` | An outline from the themes (Margin 0.10): the order by similarity, the person's sections and edits, coverage beside a draft, the Word and Markdown downloads |
| `literature.py` | Find literature (Margin 0.10): OpenAlex, Crossref, Semantic Scholar and Unpaywall with the privacy gate, the cache, following citations, saved searches, Zotero's connector, RIS and BibTeX |
| `drafts.py` | Check a draft (Margin 0.1): drafts kept apart from the documents, the claims that need a source (the AI with the quote check, or rules), the person's changes, their checks as hypotheses, the draft page's view and the export |
| `access.py` | Who may read each document with AI (ENLENS 0.11): the settings, the guard on every task, which model reads what, the ledger of what was sent to Claude, the cap |
| `ingest.py`, `textutil.py`, `store.py` | Documents and passages with page offsets, layout (paragraphs, headings), local OCR, text normalisation, the workspace database |
| `bundle.py` | A whole project as one zip (export and import); every project and the settings, to move to another computer (ENLENS 0.10) |
| `installation.py`, `update.py` | How this copy was installed (git copy, the one-line install, a package, pip) and `margin post-install`; `margin update` for each (ENLENS 0.10) |
| `home.py` | Settings, projects, the optional cloud key |
| `gui/` | The local app: `server.py` (API and jobs), `static/` (the page), `progress.py`, `launcher.py` (the Margin icon), `icons/` (its picture, drawn by `tools/make_icons.py`) |
| `concordance.py` | Search (ENLENS 0.7): concordance lines, modes, other forms, collocates |
| `profile.py` | Codebook profiles: the keyword and meaning pass, the AI's labels (with practice and element), grids by document or practice, a person's labels |
| `terms.py` | The glossary (C-value terms, abbreviations), concepts and their links, key terms |
| `themes.py` | Themes: spherical k-means (numpy or pure Python), c-TF-IDF names, a person's edits |
| `references.py` | References inside a document (chains), and what a quote's "it" refers to |
| `annotate.py` | Highlighted PDFs (pdfminer boxes, pypdf lines, OCR) and HTML copies |
| `flexiconc_export.py`, `runs.py`, `acceptance.py` | The FlexiConc export; runs and "How these results were made"; the 0.7 acceptance measures |
| `mcp_server.py` | The connector for the Claude app and Claude Code (ENLENS 0.8: also the queue tools) |
| `taskqueue.py`, `routing.py` | The task queue for Claude Code (claims, order, estimates, waiting) and the model of each kind of task (ENLENS 0.8) |
| `claude_setup.py`, `claude_plugin/` | The Claude Code plugin: `/margin-run`, its six helpers and the connector (ENLENS 0.8); finding Claude Code, adding the plugin to it and starting it for a project's queue (ENLENS 0.9) |
| `evaluation.py` | The acceptance runs per kind and model through the queue, and their scores (ENLENS 0.8, G6) |
| `vca.py`, `sources.py`, `analysis.py`, `review.py`, `report.py`, `benchmark.py` | ENLENS's SDG pack: not offered in Margin, kept so ENLENS's work merges in and a copied ENLENS project opens; `margin benchmark` for developers |

`install/install.sh` and `install/install.ps1` are the one-line install; `.github/workflows/release.yml` turns a
tag `vX.Y.Z` into a draft GitHub Release (tests, the package, the two scripts with the version filled in,
`SHA256SUMS`, and a try of the install line on Linux, macOS and Windows) with `tools/release.py`.
`tools/dev_server.py` runs the app against fake local models (for interface work; `--fresh-user` shows the app as a
new user would find it, with the remote-work demo documents in `tools/demo_corpus/`; `--claude-code` with a fake
Claude Code answering the queue; `--claude-cli` with a stand-in `claude` program the app sets up and starts, 0.9;
`--claude-install` with Claude Code still to be installed and signed in to, `--no-tesseract` without Tesseract, 0.10;
`--zotero` with a stand-in Zotero, `--update` with a stand-in update, ENLENS 0.13; `--literature` with stand-in
literature services, Margin 0.10);
`tools/pdf_to_text.py` turns a
folder of PDFs into page-preserving text files; `tools/eval_second_pass.py` measures the second sorting pass on the
pilot. The green hydrogen pilot (workspace, report, run notes) is in
`pilot/`.
