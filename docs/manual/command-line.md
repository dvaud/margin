[Manual](../MANUAL.md) › The command line

# The command line

> **In short**
> - Three programs: `margin-gui` (the app), `margin` (everything else; also `python -m margin`) and
>   `margin-mcp` (the [connector](claude-code.md#claude-in-a-chat-the-connector)).
> - Every `margin` command takes `--ws FOLDER` (default `./workspace`): any project folder, including the app's.
> - Everything here can also be done in the app, except the [SDG pack](sdg-pack.md)'s pipeline.

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
the passages read without result. Options: `--decompose`, `--framework NAME --code CODE` (`--target` still works for
SDG targets), `--k`, `--per-doc`, `--no-expand`, `--threshold`, `--embed-model` and `--embed-url`.

**Backends** (`--backend`, on every model command):

| Backend | What it is |
| --- | --- |
| `auto` | The default: the first local server running, Ollama first. |
| `ollama` | Ollama (`--url`, `--num-ctx`, `--think on\|off`). |
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
margin --ws myproject profile --framework sdg_goals --level group --limit 50       # the AI labels 50 passages
margin --ws myproject themes --k 20 --mode auto --name-with-model --out themes.xlsx
margin --ws myproject resolve <doc_id> [--name "the plant"]                        # follow references
margin --ws myproject annotate <doc_id> --hyp <hyp_id> --layers judgements labels --out highlighted.pdf
margin --ws myproject export-flexiconc project.sqlite [--no-embeddings]
margin measure [--folder DIR] [--ws PROJECT] [--timings] [--report FILE.md]       # how well Margin reads
```

## Projects, Claude Code and the queue

```bash
margin --ws myproject export-project myproject.zip                  # the whole project in one zip
margin import-project myproject.zip --ws copy_of_project            # into a new (or empty) folder
margin --ws myproject bring-in colleague.zip [--anyway]             # a colleague's work (Work together)
margin claude-setup [--print-only]                                  # the Claude Code plugin
margin --ws myproject prepare label|link|theme|resolve|check ["hypothesis"]   # tasks for Claude Code
margin --ws myproject queue status|run|first|hold|go|withdraw [kind]          # the queue (run: answer it here)
margin update [--check]                                             # a new version (Install and update)
```

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

<details>
<summary>The tables</summary>

| Table | Holds |
| --- | --- |
| hypotheses | Every hypothesis checked: text, framework and code, options, the parts found, note, batch |
| user_claims | Each claim checked (a hypothesis as written, or one of its parts) with its search terms and the model's summary; its grades are in `verifications` with `subject_kind` `user_claim` |
| documents, pages, passages | Source text, page spans, passages with `section` (body, references, reference_like, unreadable) and screen score |
| embeddings | One vector per passage and embedding model (float32, unit length) |
| tasks, results | Every model call, its payload and status; every answer with model, prompt version, validity and errors |
| verifications | One row per passage read, with its grade, quote and offsets; a person's judgement (`user_*`), the AI's scope note, and its earlier judgements when it read the excerpt again (`ai_history_json`, `reread_json`) |
| paragraphs, headings | Where each paragraph (with its page) and heading of a document starts, found when it was added |
| second_opinions | A second model's grade of each excerpt it read again (never used for an answer) |
| task_claims | The batches of queued tasks handed out to Claude Code: who took them, when, model, helper; `tasks.queued`, `claimed_by`, `step`, `again` and `results.route`, `helper`, `step` belong with it |
| meta | Thresholds used by the pack, and the corpus version (search indexes are rebuilt when it changes) |
| `reader`, `app_version` | `documents.reader` is the reader that read a document's text (1 for every document read before 0.15) and `documents.app_version` the Margin version that read it; `app_version` in `results`, `runs`, `labels`, `theme_runs` and `hypotheses` is the version that made each (empty: made before 0.15) |
| bib_items, bib_links | The bibliography's works (title, creators, year, DOI, web address, Zotero link, the files Zotero keeps with their checksums) and which document each is (`status`: `auto` for the same file or DOI, `probable`, `confirmed` or `rejected` by a person; `method`: `file`, `doi`, `title`, `person`); where it came from is in `meta` (`bibliography`); `documents.file_title` keeps the file's own title while a linked work's title replaces it (`meta` `titles_version` rebuilds the keyword index) |
| people, judgements | The people whose work is in the project (id and name), and each person's own judgement of an excerpt; the one in force is copied to `verifications.user_*`, with `user_by`; `reviews.person_id` says who made a review |
| sync_seen, sync_copies, sync_removed, sync_log | Every state of a result, set of themes or codebook that was sent or brought in (its fingerprint); a colleague's version kept beside yours (a sync clash); what was removed here; each colleague's work brought in, with its report. `documents.text_fp` is a fingerprint of a document's text; `meta` `project_uid` says which project a copy belongs to |
| vca_targets, vca_refs, doc_refs, claims, claim_targets, evidence, interactions, vca_claims, reviews | The SDG pack ([its tables](sdg-pack.md#the-packs-tables)) |

</details>
