[Manual](../MANUAL.md) › The command line

# The command line

> **In short**
> - Three programs: `margin-gui` (the app), `margin` (everything else; also `python -m margin`) and
>   `margin-mcp` (the [connector](claude-code.md#claude-in-a-chat-the-connector)).
> - Every `margin` command takes `--ws FOLDER` (default `./workspace`): any project folder, including the app's.
> - Almost everything here can also be done in the app. The project's database is a plain SQLite file you can open.

## The app

```bash
margin-gui                 # opens http://127.0.0.1:8766 in your browser
```

| Option | Effect |
| --- | --- |
| `--home FOLDER` | Where projects, history and settings live (default `~/margin`). |
| `--port 8600` | Another port. |
| `--headless` | Do not open a browser. |
| `--local-only` | No cloud option at all ([Settings](settings.md#for-whoever-installs-margin)). |
| `--make-launcher` | Make the Margin icon ([Install](install.md#the-margin-icon)). |
| `--host 0.0.0.0` | Expose the app to your network (below). |

The app listens on this computer only and answers only to the page it served (a token per run). Nothing is loaded
from the internet: no CDN, no fonts, no analytics. Stop it with <kbd>Ctrl</kbd>+<kbd>C</kbd> or *Quit Margin*.

> [!WARNING]
> `--host 0.0.0.0` exposes the app to your network. The page then does not carry the token: open the link the
> terminal prints (it ends in `#token=…`), and only by IP address. Do this only on a network you trust.

## Checking hypotheses

```bash
margin --ws myproject init
margin --ws myproject ingest ~/Reports/ more.zip                    # PDF, Word (.docx), HTML, text, Markdown, zips
margin --ws myproject ingest scans/ --ocr auto --ocr-lang eng+nld   # scanned pages by OCR (default: auto, eng)
margin --ws myproject embed --embed-model nomic-embed-text          # optional: search by meaning
margin --ws myproject check "Green hydrogen production increases water stress in arid regions." --code 6.4
margin --ws myproject check "..." --decompose --embed-model nomic-embed-text
margin --ws myproject batch hypotheses.csv --out results.csv
margin --ws myproject history --limit 20                            # or --csv all_checks.csv
margin --ws myproject frameworks
margin detect                                                       # local servers and their models
```

`check` (or `hypothesis`) prints, as JSON, the answer, the balance, and per part the judged passages with quotes and
the passages read without result. Options: `--decompose`, `--framework NAME --code CODE` (a code without `--framework` is
read as an SDG target), `--k`, `--per-doc`, `--no-expand`, `--threshold`, `--embed-model` and `--embed-url`.

**Backends** (`--backend`, on every model command):

| Backend | What it is |
| --- | --- |
| `auto` | The default: the first local server running, Ollama first. |
| `ollama` | Ollama (`--url`, `--num-ctx`, `--think on\|off\|judging`). |
| `local` | An OpenAI-compatible server (`--url http://localhost:1234/v1`). |
| `anthropic` | The Claude API: the text read is sent to Anthropic. |
| `baseline` | An offline keyword demo. |

Without `--model`, a local backend uses a chat model its server already holds in memory, else the most recently
downloaded one, and says which; the Claude API uses `models.verify` of `config.json`. `--num-ctx` is `auto` by
default: the smallest of 8,192, 12,288, 16,384 and 32,768 tokens that fits the largest task (for `run`, the largest
pending task).

Every model command takes `--model-seed N` (default: the seed in Settings, 42). `margin backend-check --repeatable`
asks the model the same question twice and says whether the answers match.

## Exploring the documents

```bash
margin --ws myproject search "electrolyser imports" --mode phrase --out hits.csv   # also --mode any|all|near --near 5
margin --ws myproject search water --collocates                                    # the words around the hits
margin --ws myproject terms --rebuild                                              # the glossary; --q water filters
margin --ws myproject concept "proton exchange membrane" --references              # a concept card as JSON
margin --ws myproject profile --keywords-only --out profile.xlsx                   # codes by keywords, no model
margin --ws myproject profile --framework remote --level group --limit 50          # the AI labels 50 passages
margin --ws myproject themes --k 20 --mode auto --name-with-model --out themes.xlsx
margin --ws myproject resolve <doc_id> [--name "the plant"]                        # follow references
margin --ws myproject annotate <doc_id> --hyp <hyp_id> --layers judgements labels --out highlighted.pdf
margin --ws myproject export-flexiconc project.sqlite [--framework NAME] [--no-embeddings]
margin measure [--folder DIR] [--ws PROJECT] [--timings] [--report FILE.md]       # how well Margin reads
```

## Projects, Claude Code and the queue

```bash
margin --ws myproject export-project myproject.zip                  # the whole project in one zip
margin import-project myproject.zip --ws copy_of_project            # into a new (or empty) folder
margin import-enlens [project ...]                                  # copy projects, codebooks and settings from ENLENS
margin claude-setup [--print-only]                                  # the Claude Code plugin
margin --ws myproject prepare label|link|theme|resolve|check ["hypothesis"]   # tasks for Claude Code
margin --ws myproject queue status|run|first|hold|go|withdraw [kind]          # the queue (run: answer it here)
margin update [--check]                                             # a new version (Install and update)
```

Moving projects to another computer, and bringing them over from ENLENS, is on
[Projects and other computers](projects.md).

<details>
<summary>The acceptance measures (for choosing models)</summary>

```bash
margin --ws pilot acceptance samples|measure|search                 # the acceptance measures
margin --ws pilot acceptance queue --kind label --model haiku [--again]   # a run through the queue
margin --ws pilot acceptance score [--apply]                        # score the runs (docs/MODEL_CHOICE.md)
margin --ws pilot benchmark --backend ollama --model qwen3:8b --sample 30  # test a model (A model on your own computer)
```

`export-tasks` warns when asked for the kinds `label`, `link`, `theme` and `resolve`: the file queue works for them,
but their tasks are made per project run and are usually answered in the app.

</details>

## The project's database

A project is a plain folder with one SQLite database, `enlens.sqlite`. Open it with any SQLite tool. Offsets in
`evidence` and `verifications` index into `documents.text`. Removing one document keeps past checks intact (each check
stores the passages it showed); removing all documents also removes every check.

The folder also has `cache/`: each document's words for the keyword index (`search.sqlite`) and each document's
reading for the glossary (`glossary.sqlite`), kept so that adding a document does not read every other one again. Both
are made from the documents and brought up to date by themselves; neither goes into a project's zip, and the folder can be deleted at any time (the next search and the next glossary are a little slower,
once). A project folder that a cloud service copies (Dropbox, OneDrive) copies `cache/` too; it can be left out there.

Adding documents reads up to three files at a time in reading processes of their own; `MARGIN_READ_WORKERS=1` reads
them one at a time (any number sets how many at once).

<details>
<summary>The tables</summary>

| Table | Holds |
| --- | --- |
| hypotheses | Every hypothesis checked: text, framework and code, options, the parts found, note, batch |
| user_claims | Each claim checked (a hypothesis as written, or one of its parts) with its search terms and the model's summary; its grades are in `verifications` with `subject_kind` `user_claim` |
| documents, pages, passages | Source text, page spans, passages with `section` (body, references, reference_like, unreadable) and screen score |
| embeddings | One vector per passage and embedding model (float32, unit length) |
| tasks, results | Every model call, its payload and status; every answer with model, prompt version, validity and errors |
| verifications | One row per passage read, with its grade, quote and offsets; your judgement (`user_*`), the AI's scope note, and its earlier judgements when it read the excerpt again (`ai_history_json`, `reread_json`) |
| paragraphs, headings | Where each paragraph (with its page) and heading of a document starts, found when it was added |
| blocks, doc_tables, block_choices | Each document's blocks in reading order (paragraph, heading, caption, table, running head), whether features read them, their box on the page; a table's rows and cells; your corrections (*Restore*, *Leave out*), kept by the block's text so they hold when the document is read again |
| second_opinions | A second model's grade of each excerpt it read again (never used for an answer) |
| task_claims | The batches of queued tasks handed out to Claude Code: who took them, when, model, helper; `tasks.queued`, `claimed_by`, `step`, `again` and `results.route`, `helper`, `step` belong with it |
| ai_sent | Every passage that left for Claude (Claude Code, the Claude API, a chat through the connector): when, route and feature. It is the list *What was sent to Claude* downloads |
| labels, label_parts, code_vectors | The codebook profile: one row per passage and code (from keywords, meaning, the AI or you), what a label names besides its code (practice and element), and the vector of each code's text |
| terms, term_mentions, concepts, concept_terms, concept_links | The glossary of the corpus, where each term occurs, the concepts and how they relate |
| mentions | References within a document: each mention in a chain (*it*, *the plant*), quote-checked and placed by offset |
| theme_runs, themes, theme_members | Each set of themes, its themes and the passages in each |
| runs | One row per run of an AI task kind: scope, model, prompt version, Margin version |
| drafts, draft_claims, draft_sent, draft_notices | Your drafts (text, AI setting), their claims (offsets in `drafts.text`, the quote, the claim checked, who found it, the hypothesis that checks it), every time Claude read part of a draft, and the notices about a draft read against itself that you set aside |
| cite_texts, citations, cite_refs | The texts whose citations were checked, the citations found in each, and the work each one cites (`how`: `auto`, `ambiguous`, `none` or `person`) |
| outlines, outline_sections | Your outlines: the set of themes or question each came from, and their sections in order, with your own titles and notes |
| lit_searches, lit_found, lit_cache | Saved literature searches, the works each one found (and whether you have seen them), and the answers of the online services kept for a while |
| bib_items, bib_links | The bibliography's works (title, creators, year, DOI, web address, Zotero link, the files Zotero keeps with their checksums) and which document each is (`status`: `auto` for the same file or DOI, `probable`, `confirmed` or `rejected` by you; `method`: `file`, `doi`, `title`, `person`); where it came from is in `meta` (`bibliography`); `documents.file_title` keeps the file's own title while a linked work's title replaces it (`meta` `titles_version` rebuilds the keyword index) |
| `reader`, `app_version` | `documents.reader` is the reader that read a document's text and `documents.app_version` the Margin version that read it; `app_version` in `results`, `runs`, `labels`, `theme_runs` and `hypotheses` is the version that made each (empty: made by an earlier version) |
| meta | Thresholds, and the corpus version (the search index and the glossary are brought up to date when it changes) |
| vca_targets, vca_refs, doc_refs, claims, claim_targets, evidence, interactions, vca_claims, reviews | ENLENS's SDG pack's tables: not used by Margin, and empty unless the project came from ENLENS (kept so it opens) (`reviews` also holds your decisions on items such as a codebook label) |

</details>
