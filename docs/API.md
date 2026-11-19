# Margin local app: HTTP API

The app (`margin-gui`) is a small HTTP server on `127.0.0.1` (default port 8766) that serves one static page
(`src/margin/gui/static/`) and a JSON API under `/api/`. Everything stays on the computer; text goes only to
the model service chosen in Settings.

## Rules

- **Token.** Every API call sends the run's token as the header `X-Margin-Token`; without it, or with an old one,
  401. The endpoints a plain link opens (the exports `…/export.csv|json|xlsx|zip`, the original file
  `…/documents/<id>/file`, the page pictures `…/pages/<n>.png`, and the 0.7 downloads: search, profile and themes
  exports, highlighted copies, the FlexiConc file) also accept `?token=`: the page uses it for an `<img>` and for
  "open the PDF at this page", which `fetch` cannot do.
- **How a client gets the token** (0.17.2). `GET /` never carries it, whatever the `Host` (any account on the computer
  could fetch it); `index.html` has `{{MARGIN_VERSION}}` and `{{MARGIN_RUN}}` (a random id of this run, not a
  secret) filled in. The app opens `http://127.0.0.1:<port>/#token=<token>` in the browser (and prints it, unless
  started from the icon, whose output goes to a log). The page reads it from `location.hash`, keeps it in
  `sessionStorage` and takes it out of the address bar; a tab without it asks the app's other tabs in the same browser
  (a `BroadcastChannel` named `margin-token`) and keeps the first answer the API accepts. A program on this computer
  reads it from `app-token-<port>.json` in the data folder: `{"url", "port", "pid", "token"}`, written whole when
  the app starts (mode 0600 on macOS and Linux; on Windows the user's profile folder protects it, and with a data
  folder outside the profile the file is in `%LOCALAPPDATA%\Margin`) and removed when it stops (`gui/launcher.py`
  `token_path`, `read_token`, `open_link`). On Linux the browser is given a file `open-<port>.html` beside it (also
  0600) that sends it on to the link, so the token is on no program's command line (`launcher.browse`). Every start has a new token, except a restart after an update
  (below).
- **Host.** Requests must name `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>` in `Host`; requests carrying an
  `Origin` other than their own `Host` are refused (403).
- **Network mode** (`margin-gui --host 0.0.0.0`): `Host` may also be an IP address of the computer (never a domain
  name: that could be DNS rebinding). As on `127.0.0.1`, the token comes in the link printed in the terminal,
  `http://<address>:<port>/#token=<token>`.
- **Content Security Policy** on the page: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
  img-src 'self' data:; font-src 'self' data:; connect-src 'self'`. No inline `<script>`, no external resources.
- **Static files**: `GET /static/<file>` serves files from the `static/` folder (also `/<file>` with an extension).
  Any path without an extension returns `index.html` (use hash routing anyway: `#/check`, `#/h/<id>` …).
  0.13.5: `GET /static/site.css` is the installation's own `site.css` followed by each add-on package's;
  `GET /static/addons/<add-on>/<file>` serves an add-on package's page files (docs/EXTENDING.md).
- **JSON in, JSON out.** Request bodies are JSON objects (`Content-Type: application/json`), except uploads (raw bytes).
- **Errors**: status 4xx/5xx with `{"error": "plain-language message", "kind": "request" | "backend" | "internal"}`.
  `kind: "backend"` (HTTP 502) means the model service is the problem (not running, model missing, key wrong): offer
  a link to Settings. 401 means the token is missing or from an earlier run: open Margin from its icon (or run
  `margin-gui`).
- **Jobs.** Long work returns `{"job": Job}` at once; poll `GET /api/jobs/<id>` (about every 500 ms while
  `state` is `queued` or `running`). Jobs that use the chat model run one at a time; others wait in `queued`.
  0.17.0: jobs of one project that change the same things wait their turn in `queued` too, with `waiting_for` saying
  for which job (see Jobs below).
- Times: hypotheses and documents carry ISO 8601 UTC strings (`created_at`); jobs carry Unix seconds.
- Ids are opaque strings. URL-encode project names (they may contain spaces).

## Statuses

A *hypothesis* is checked as one claim, or (with `decompose`) split into 2–5 *parts* that must all hold; each part
is a claim with its own check. Each passage read gets a grade or none:

| grade (`verdict`) | meaning |
| --- | --- |
| `supports` | the passage states the claim |
| `partially_supports` | it states a necessary part; one inference remains |
| `refutes` | it states the opposite / no such effect |
| `null` | read, nothing relevant ("not enough information") |

Grades count towards a status only when `confidence >= threshold` (default 0.6, a user setting; every read endpoint
takes `?threshold=`). Claim and hypothesis statuses (texts and explanations are in `GET /api/state` → `statuses`):

| status | text in the app |
| --- | --- |
| `supported` | Supported by your documents |
| `partially_supported` | Partly supported |
| `contested` | Mixed evidence (support and contradiction both present) |
| `contradicted` | Contradicted by your documents |
| `unsupported` | No evidence found (in the excerpts read) |
| `uncertain` | Only uncertain evidence: excerpts were judged, but none at or above the threshold |
| `no_passages` | Nothing in your documents matched |
| `not_checked` | Not finished yet; *Waiting for your judgement* (`status_text`) when every excerpt read waits for the person |
| `failed` | The check did not work |

0.14.3: an excerpt no model may read (`read_by: "you"`) counts towards no status until the person judges it (before,
it counted as "not about the hypothesis", so a check of *No AI* documents said "No evidence found"). A round whose
main part failed is failed, even when its other excerpts were read by the local model or wait for the person, and
none of the AI's judgements in it count anywhere (status, `balance`, `who`, `counted`, the Results list, the map).

Texts are in `GET /api/state` → `statuses` (`text`, `help`, and `next`: what a reader can do next).
A person can overrule the AI's judgement of any excerpt read (`PUT …/judgements/…`, below); their judgement replaces
the AI's in every status and count, always counts whatever the threshold, and is shown beside the AI's.
`status_any` is the same status counting every grade whatever its confidence (show it when it differs: "if the
uncertain judgements counted too: …"). `balance` = `{docs_supporting, docs_partly, docs_refuting, docs_both,
docs_counted, excerpts_uncounted, lean}`: a document counts as supporting if one of its counted excerpts supports, as
partly supporting only if none supports, as refuting if one refutes (so it can be on both sides: `docs_both`);
`docs_counted` counts each document once. `lean` runs from -1 (only contradicted) to +1 (only supported), `null`
when nothing was graded. `who` lists the same documents by side (see the hypothesis endpoint).

## Endpoints

### App state and settings

`GET /api/state` →
```json
{"version": "0.7.0", "home": "/Users/me/margin",
 "settings": {"backend": "auto", "allow_cloud": false, "anthropic_model": "claude-opus-5-5",
              "ollama_url": "http://localhost:11434", "ollama_model": "", "openai_url": "http://localhost:1234/v1",
              "openai_model": "", "num_ctx": "auto", "think": "off", "think_budget": 1500, "embed_backend": "ollama", "embed_model": "",
              "embed_url": "", "threshold": 0.6, "k": 8, "per_doc": 2, "expand": true, "decompose": false,
              "second_pass": false, "project": "Demo", "benchmark_reference": "", "second_model": "",
              "ocr": "auto", "ocr_lang": "eng"},
 "backend_label": "Ollama · qwen3:8b",
 "backend_labels": {"auto": "Local model (automatic)", "ollama": "Ollama", "openai": "Local OpenAI-compatible server",
                    "anthropic": "Claude API (cloud)", "baseline": "Offline demo"},
 "projects": [{"name": "Demo", "linked": false, "documents": 3, "hypotheses": 3, "ok": true, "path": "…"}],
 "local_only": false,
 "context": {"setting": "auto", "num_ctx": 8192, "needed": 6171, "thinking_allowance": false},
 "ocr": {"available": true, "missing": [], "languages": ["eng", "nld"]},
 "project": "Demo",
 "key": {"session": false, "env": false, "stored": false},
 "statuses": [{"status": "supported", "text": "Supported by a source", "help": "…"}, …],
 "jobs": [Job summaries of queued/running jobs],
 "brand": {"name": "Margin", "tagline": "explore and check your documents", "welcome_title": "…", "welcome_text": "…",
           "description": "…", "logo": "/static/logo.svg"}}
```
`brand` (0.13.5): the app's name and words, from `static/brand.json` and any add-on's `BRAND` (docs/EXTENDING.md).
0.13.6: an add-on may add keys of its own (its `state(app)`); they never replace one of these. Its routes are documented
in `docs/ADDON_API.md` and come after Margin's own (docs/EXTENDING.md). `GET /api/projects/<p>/overview` may carry an
add-on's counts the same way, and a hypothesis's result and history rows carry `origin` and `origin_id` (where it
comes from: `batch`, an add-on's own kind, or none).
`backend` values: `auto` (first local server found: Ollama, then LM Studio, llama.cpp, Jan, vLLM), `ollama`,
`openai` (an OpenAI-compatible local server at `openai_url`), `anthropic` (cloud; allowed only when `allow_cloud`),
`baseline` (offline demo, word overlap). Text leaves the computer only with `anthropic`.

New in 0.6:
- `num_ctx`: `"auto"` (the default) or a number. With `"auto"` the app uses the smallest of 8,192, 12,288, 16,384
  and 32,768 tokens that holds the largest task the settings can produce (the check prompt, `k` excerpts of 1,100
  characters with their headers, the answer, and 4,096 tokens of reasoning unless `think` is `off`). It stays the
  same between requests (Ollama reloads the model when it changes), and leaves the most memory to the model.
  `context` in the state says what that is now: `num_ctx` (the length used), `needed` (the estimate), `setting`;
  with a fixed number, `too_small: true` when the estimate is larger. Show it under *Advanced*. Settings files of
  0.5 hold the old default 16384: it is read as `"auto"`.
- `second_pass` (default `false`): sort the best candidates again by how closely they word the hypothesis (see
  "Checking"). It did slightly worse on the pilot, so it is off; it is an *Advanced* option.
- `second_model`: a second local chat model (on the same server) for "Ask a second AI model" (see "Results").
- `think` (0.6.1): `"off"` (the default), `"judging"` (reason only when judging excerpts: checks, re-reads and the
  second model; not when splitting a hypothesis or proposing search words), `"on"`, or `"default"` (the model's
  own default). `think_budget` (default 1500; 0 = no limit, else 256–16,384): reasoning tokens after which the
  model is stopped and asked to answer at once, with its reasoning so far as notes (Ollama only). The model report in
  a job's `progress.model` then has `budget` and `budget_reached`, and its `stats` `thinking_tokens` and
  `budget_reached`.
- `ocr` (`"auto"` | `"off"`) and `ocr_lang` (Tesseract languages joined by `+`, e.g. `"eng+nld"`): reading scanned
  PDF pages. `ocr` in the state: `available` (Tesseract and the Python parts are installed), `missing` (what is
  not: `"tesseract"`, `"pypdfium2"`, `"pillow"`), `languages` (installed Tesseract languages).

New in 0.7:
- `seed` (default 42; 0–2,147,483,647): sent with every model request (Ollama and OpenAI-compatible servers), with
  temperature 0, so the same input gives the same answer where the server honours it (`POST /api/servers/repeatable`
  tests that). Recorded with every answer.
- `profile_framework` (Margin 0.8: default `""`, no codebook; a codebook of the project, or a built-in one, `"sdg"`
  for the 169 targets or `"sdg_goals"` for the 17 goals): the codebook of the Profile page, the Codes panel and the
  keyword pass run when documents are added. A settings file written before 0.8 with `"sdg"` is read as `""` once.
  With no codebook, adding documents skips the `codes` phase, and the requests below that need one and do not name
  it answer 409 *Choose a codebook first*.
- `themes_k` (default 20; 2–60): how many themes a new set looks for.
- Adding documents (`POST …/ingest`) now ends with two phases, `glossary` and `codes`: the term index and the keyword
  pass of `profile_framework`. Their results are in the job's `result.glossary` and `result.codes`.

When no model is chosen, or the chosen Ollama model is not installed, the app picks one: a chat model the server
already holds in memory first (so nothing extra is loaded), then the most recently pulled one, then the first
in alphabetical order. `POST /api/servers/test` then says so in `warning`.

`PUT /api/settings` body: any subset of `settings` → `{"settings": {...}, "backend_label": "..."}`.
400 with a message for invalid values (e.g. `backend: "anthropic"` while `allow_cloud` is false, or any cloud setting
while `local_only` is true). `project` sets the current project.

`local_only` (in the state) is true when whoever installed the app switched cloud models off for good
(`margin-gui --local-only`, `MARGIN_LOCAL_ONLY=1`, or a file `local_only` in the data folder): hide the cloud option.

`POST /api/settings/key` `{"key": "sk-ant-…", "remember": false}` → `{"key": {...}}`. Without `remember` the key is
kept in memory for this run only. `DELETE /api/settings/key` forgets both. 403 when `local_only` is true (0.11.1).

Other cloud providers. `backend` may be `"cloud_api"`, with settings `cloud_provider` (`openai`, `gemini`,
`mistral`, `azure` or `openrouter`), `cloud_model` (judging excerpts), `cloud_small_model` (labels and links),
`cloud_strong_model` (second opinions and hard cases; providers stage 2: each empty means the provider's
recommendation, see `provider-models` below) and `azure_url` (the resource address, HTTPS; for Azure the three models
are the person's own deployment names). Refused like `anthropic` while `allow_cloud` is false or `local_only` is
true. `GET /api/state` gains `providers`: `{"list": [...], "keys": {"openai": true, …}, "route", "set_up",
"other_set_up"}` (`keys` says only whether a key is stored; `route` is the provider of the main route; `set_up` and
`other_set_up` say whether any provider, or any other than Anthropic, is set up). Provider ids: `anthropic`, `openai`,
`gemini`, `mistral`, `azure`, `openrouter` and `other` (a model server on another computer).

- `POST /api/settings/provider-key` `{"provider": "openai", "key": "…"}` → `{"providers": {…}}`. The key goes to the
  keychain and is never returned, logged or put in settings. 403 when `local_only` is true.
- `DELETE /api/settings/provider-key` `{"provider": "openai"}` → `{"providers": {…}}`.
- `GET /api/settings/provider-models?provider=openai` → `{"models": [...], "lists": true, "problem": "…", "recommended": {"small": "…", "middle": "…", "strong": "…"}}`. `recommended` (providers stage 2) is the provider's line-up resolved against the key's list: what an empty model choice in Settings uses (Azure: the models to deploy). `lists`
  is false for Azure, which has no list (type the deployment name); `problem` is a plain sentence when the list could
  not be fetched (for example that the key was refused).

`POST /api/quit` → `{"stopping": true, "jobs_stopped": n}`: stops the app ("Quit Margin" in the sidebar) once the
running jobs have stopped (at most 20 s); 409 when this copy was not started in a way that can be stopped from here.
0.14.3: every Claude Code run started from the app (`queue/claude-code`) is stopped first, and its batches go back to
the queue; the same for `POST /api/restart` and `POST /api/update`. Each run's process id is kept in
`<data folder>/claude-runs/<project>-<hash>.run.json`, so an app started later still sees a run that kept working
(`runner.running`), can stop it, and does not start a second.

"Update Margin" in the sidebar (Margin 0.2.1). `GET /api/state` says `can_quit` and `can_restart`: whether this copy
can stop itself, and restart itself (started with `margin-gui` or from the Margin icon; the button is shown only then,
and since ENLENS 0.13.6 only when there is an update).

- `GET /api/update` → `{"available": bool, "on_disk": bool, "version": running, "latest": "0.2.2" | null,
  "changes": n | null}`: whether a newer Margin waits, the way this copy was installed (the latest GitHub Release
  for the one-line install: `latest`; new commits on the branch a git copy follows: `changes`), or is installed
  already while this copy kept running (`on_disk`, `latest` is that version). 409 with the reason when it cannot be
  updated from here (files of a git copy edited by hand, a download package, no network).
  0.13.6: the page asks when it opens and every two minutes, and shows the button only when `available`. The answer
  (or the 409 and its reason) is kept for 100 seconds, so the open tabs share one look; `GET /api/update?fresh=1`
  (*Check for updates* in Settings) looks again now. A version already on disk is seen at once. The one-line install
  reads the newest version from where `github.com/…/releases/latest` redirects to, which GitHub's API limit does not
  count; the API is asked only when that page does not say. `POST /api/update` forgets the kept answer.
  0.14.3: while an update runs the answer is the kept one (or `available: true`) with `"updating": true`, and no
  `git fetch` is made beside the update's own git commands; a git command never asks for a password (stdin closed,
  `GIT_TERMINAL_PROMPT=0`, ssh in batch mode) and is stopped after 90 s.
- `GET /api/whats-new` (0.15.1) → `{"note": {"version", "title", "subtitle", "points": [...]}}` or `{"note": null}`. The
  note is `gui/static/whats-new.md` (`# 0.15.1: Title`, `*subtitle*`, a few lines starting with `-`). It is served only
  when its version is the running one and the setting `whats_new_seen` is not that version, and that setting is set
  the moment it is served, so the page shows it once, on the first start after an update. A new installation (no
  project yet, or no settings file) is marked silently and gets `null`; a malformed file is `null`, never an error.
  0.15.4: before it, once, an update on Windows that did not finish: `{"note": {"kind": "problem", "version":
  running, "title": "The update to X did not finish", "subtitle", "points": [what happened, what to do]}}`, from the
  result `handover.py` left in `updates/result.json` of the data folder (removed when read; a result that says the
  update worked is only removed).
  After 0.17.2 what is new is read only when asked, so the answer is `{"note", "changes", "unread"}`: `note` is only
  the Windows problem above (once) or `null`; `changes` is the running version's note, `{"version", "title",
  "subtitle", "points", "url"}` (`url`: the version's release page on GitHub), or `null`, served every time and marking
  nothing; `unread` is true when an update brought it and this person has not opened it (`whats_new_seen` is not the
  running version; never on a new installation, which is still marked silently). While `unread` the page shows a small note in the
  corner (after 0.18.0rc1: the title and *Read what's new*; in 0.18.0rc1 a sidebar button); Settings has it always.
- `POST /api/whats-new/read` `{}` (after 0.17.2) → `{"unread": false}`: the note was read or closed; `whats_new_seen`
  becomes the running version.

- `POST /api/update` `{}` → `{"updated": true, "restarting": true, "handover": false, "from", "version",
  "jobs_stopped": n}`: installs it as `margin update` does, then restarts on the same address and port (running jobs
  are stopped first, as for Quit; at most 20 s); `{"updated": false, "restarting": false, "version"}` when nothing
  newer waits. 409 when the update fails (nothing restarts; the reason is the error), when this copy cannot restart
  itself, and for a second request while one is updating or restarting. 0.15.4, the one-line install on Windows:
  `"handover": true`: the new version is downloaded and checked, then the app quits and `handover.py` installs it and
  starts the app again on the same address (`server.handover_command`); the page waits up to five minutes. Before
  0.15.4 this was a 409 that said to quit and run the install line again.
- 0.15: *Try new versions early*: the setting `update_channel` (`"stable"`, the default, or `"early"`, validated by
  `PUT /api/settings`) says whether the check and `margin update` of a one-line install also take release candidates:
  `early` asks GitHub's list of releases (`/releases?per_page=30`, drafts skipped) and takes the highest version
  (`update.version_tuple`); `stable` asks `/releases/latest`, which is never a pre-release. A git copy follows
  `main` and ignores it. `GET /api/update` carries `"candidate": true` when `latest` is a release candidate, and
  changing the channel makes the next look ask again.
- `GET /api/technical-details` (0.15) → `{"text": "Margin version: …\nInstalled: …\nSystem: …\nPython: …\nAI route: …\nLocal
  only: yes|no\nUpdate channel: …"}`: a short block for a problem report (*Copy technical details* in Settings →
  Technical). It holds no path, project or document name, user name or key.
- `POST /api/notify/test` (after 0.19.7) → `{"sent": bool, "how": "app"|"osascript"|"toast"|"balloon"|"notify-send"|"gdbus",
  "problem": "...", "note": "..."}`: one notification now (*Send a test notification*); `note` says where this system
  lets the person allow or stop them. A job the person started that ends after 20 s or more sends one as Settings'
  `notify` says (`away`, the default: only when no request with `X-Margin-Seen: 1`, which a tab in front of the person
  sends, came in the last 20 s; `always`; `off`). `MARGIN_NO_NOTIFY=1` switches them off for the process.
- `POST /api/restart` `{}` → `{"restarting": true, "jobs_stopped": n}`: restarts into the version on disk (*Restart
  now* on the banner *Margin X is installed, but Y is still running*); 409 when this copy cannot restart itself.

0.17.2: the restarted copy keeps the access token (it is handed over in the environment, `MARGIN_RESTART_TOKEN`,
which the new copy takes out at once; on Windows the update starts handover.py with it in that program's environment
only, and handover.py gives it to the copy it starts and to nothing else), so the open
tabs, which keep it, reach the new copy. A restart that cannot have its old port back takes a new token. The page
waits until `/` answers with a new `margin-run` (or answers again after not answering) and reloads. On macOS and Linux the same process becomes the new version (`os.execv`),
in the same terminal; on Windows a new one is started and the old one ends. Started from the icon, it is restarted
as the icon starts it (`--launcher`, output to `logs/margin.log`), without opening a new browser tab.

`GET /api/servers` → local model servers running now (probed in parallel, < 1 s):
```json
{"servers": [{"kind": "ollama", "url": "http://localhost:11434", "version": "0.12.3",
              "models": ["bge-m3:latest", "qwen3:8b"], "chat_models": ["qwen3:8b"], "embedding_models": ["bge-m3:latest"],
              "loaded": ["qwen3:8b"], "modified": {"qwen3:8b": "2026-09-30T08:12:00Z", "bge-m3:latest": "…"}},
             {"kind": "openai", "url": "http://localhost:1234/v1", "models": […], "chat_models": […], "embedding_models": […]}],
 "suggested": [{"name": "qwen3:8b", "use": "chat", "size": "about 5 GB"},
               {"name": "nomic-embed-text", "use": "embed", "size": "about 0.3 GB"}]}
```
`suggested` (0.13.7): the models the page offers to download into Ollama with one button. `ollama_app` (0.15.6):
whether Ollama is on this computer, running or not: `{"installed", "path", "system": "windows" | "mac" | "linux",
"how": "app" | "terminal", "line", "manual"}` (`how`: the app installs it itself, or on Linux opens a terminal window
running Ollama's own `line`; `manual`: Ollama's installer file, for doing it by hand). `advice` (0.18.0rc2) gives the
models that fit this computer; I6 adds `advice.tier` (`{"tier": "small" | "medium" | "large", "answers": "explorer" |
"suggestions", "words", "size", "what"}`, the chosen tier in plain words, no model name), each chat option's `tier`,
`answers`, `need` (bytes), `num_ctx` and `runner` (`mlx` | `llamacpp`), and `older_model`: `{"chosen", "offer", "size"}`
when the model set up is not the tier's (null otherwise). Since I6 a check's result (`GET …/hypotheses/<id>`) carries
per excerpt `suggestion` (`{"form": "check" | "point", "lean", "marked", "rank", "order"}`, a local model's reading,
which counts for nothing until judged) and `local_counted`, and per part and hypothesis the counts `suggestions` and
`local_counted`.

`POST /api/jobs/<id>/again` (0.19.5) → runs again a job the local model was refused in for memory (its view says
`error_kind: "memory"`, `memory: {"need", "free", "short", "model"}` and `can_run_again`): the same work, from where it
stood. `{"force": true}`: *Start it anyway*, the local model starts whatever memory is free, for that run only. Gives
`{"job"}`; 409 for any other job.

`GET /api/local-status` (0.19.4) → the local model that reads documents marked Only a local AI, for the local panel,
without starting it: `{"model", "server", "memory"}` where `memory` is `{"loaded": true}` when the model server holds it
already, else `{"need", "free", "short"}` in bytes (left out when the server or the computer does not say enough);
`{"model", "problem"}` when it cannot be used; `{"same_as_main": true}` when the main model reads those documents itself.
`GET …/profile/plan` gives the same as `local_model` when passages of such documents wait, and `POST …/profile/label`
takes `{"force": true}` to start the local model with too little memory free (*Start it anyway*); its job's result
says `local_waiting`, `local_read`, `local_model`, `memory_short`, `memory` and `local_problem`.

`GET /api/ollama` (0.15.6) → what the page shows before Ollama is installed from the app: `ollama_app`'s fields plus
`"size": {"bytes", "exact"}` (the download for this kind of computer, as ollama.com says it now, kept an hour; when
ollama.com cannot be asked, the size known in November 2026, `exact` false: 1.7 GB for Windows, 230 MB for macOS),
`"needs"` (the free disk space asked for: four times the download, for the file and Ollama unpacked), `"free"` (free
space in the temporary folder) and `"from"` (the address it downloads).

`POST /api/ollama/install` (0.15.6) → installs Ollama without a terminal, as `POST /api/claude-setup/claude-code` installs
Claude Code. Windows and macOS: `{"job": …}` of kind `ollama-install` (one at a time) that downloads Ollama's own
installer (`OllamaSetup.exe`, `Ollama-darwin.zip`: the files ollama.com's install lines download), checks that it is
Ollama's (Windows: the Authenticode signature is valid and its signer is `O=Ollama Inc.`, as Ollama's install.ps1
checks; macOS: `codesign --verify --deep --strict` against Ollama's Developer ID team, 3MU9H2V9Y9), installs it for this
user (Windows: the installer's silent per-user mode, `%LOCALAPPDATA%\Programs\Ollama`, no administrator rights; macOS:
`/Applications`, else `~/Applications`) and starts it hidden. Its `progress` is `{"step": "download" | "check" |
"install" | "start", "done", "total"}` (bytes while downloading); `POST /api/jobs/<id>/cancel` stops it while it
downloads, and nothing is installed. Its `result` is `{"path", "running"}` (`running`: Ollama answered within a
minute). An Ollama already on the computer is only started (`"already": true`). A failed install is a job `error` in
plain words (not enough disk space, offline, a file that is not Ollama's: nothing is installed from it). Linux:
`{"terminal": {"opened", "window", "command"}}`: a terminal window runs Ollama's own line, which asks for the password
(it installs for everyone and sets up a service); `command` is the line to type when no window could be opened.
Nothing of the person's is sent, so it is allowed with `--local-only` too. 0.18.0rc2: `suggested` is what fits THIS
computer (`modeladvice.suggested`), and `advice` says more: `{"computer": {"memory", "disk_free", "gpu", "system",
"unified", "words"}, "chat": {"pick", "smaller", "larger", "options", "reason"}, "embed": {…}, "what_is_a_model"}`;
a model is `{"name", "use", "role": "recommended"|"smaller"|"larger", "size", "bytes", "speed": "quick"|"fair"|"slow",
"speed_text", "good_for", "tight", "note"}`. Only models that fit the memory (the size and the memory its context takes,
at most 50 % of the memory for the recommended one, 65 % for a larger one; a graphics card's own memory where
`nvidia-smi` reports one) and the disk (the download and 2 GB to spare) are listed; when none fits, `pick` is null and
`reason` says why. `advice` is null when the computer cannot be read, and `suggested` then keeps the old
`qwen3:8b` and `nomic-embed-text`.

`POST /api/ollama/start` (0.15.6) → starts the Ollama that is on this computer but not running, hidden: `{"started",
"path"}`; 409 when Ollama is not on this computer. The page notices it within a few seconds. 0.18.0rc2: it starts nothing
when Ollama answers already (`{"started": false, "running": true}`) or was started by Margin in the last 45 seconds
(`{"started": false, "starting": true}`): the card calls it by itself whenever Ollama is on the computer and does not
answer.

`POST /api/servers/pull` (0.13.7) → downloads models into the Ollama running on this computer, so a local model needs
no terminal. Body `{"models": ["qwen3:8b", "nomic-embed-text"]}` (one to four names as Ollama's library writes them;
or `{"model": "qwen3:8b"}`), optionally `"url"`, an Ollama address as `GET /api/servers` lists it, and `"use"`: `ai`
(the AI that reads the documents: `backend` ollama and its model, plus the embedding model if one was downloaded),
`restricted` (the local model for documents marked *Only a local AI*) or `embed` (search by meaning). With `use` the
app chooses the downloaded models itself when the download is done, so closing the page does not lose the choice,
unless those settings were changed meanwhile (then the person's choice stands and `chosen` is null). Ollama fetches
the models from ollama.com itself; nothing of the person's is sent, so it is allowed with `--local-only` too. Returns
`{"job": …}` of kind `model-pull` (one at a time: while one runs, its job is returned). Its `progress` is
`{"model", "index", "count", "status", "done", "total"}` (bytes of the model being downloaded, as Ollama reports
them); its `result` `{"url", "models", "listed": {name: the name Ollama lists, e.g. "nomic-embed-text:latest"}, "chosen":
{the settings it chose} | null}`.
`POST /api/jobs/<id>/cancel` stops it (Ollama keeps what it has and goes on from there next time). 400 for a name that
is not one, 409 when no Ollama answers on this computer (or at the address in Settings). A failed download is a job
`error` in plain words (no such model, not enough disk space, offline).

`POST /api/servers/test` → tests the configured chat model (and embedding model if set):
`{"ok": true, "backend": "ollama", "model": "qwen3:8b", "model_available": true, "message": "Ollama 0.12.3 is running. …",
"warning": null | "…", "details": {"parameters": "8B", "quantization": "Q4_K_M", "trained_context": 40960},
"embedding": {"ok": true, "model": "bge-m3", "dimensions": 1024} | {"ok": false, "model": "…", "error": "…"},
"context": {"setting": "auto", "num_ctx": 8192, "needed": 6171, "thinking_allowance": false}}`
(502 `kind: backend` when the server cannot be reached). `loaded` (in `GET /api/servers`): the models in memory now
(Ollama, and LM Studio); `modified`: when each was pulled (Ollama).

### Projects

`GET /api/projects` → `{"projects": [summary]}`.
`POST /api/projects` `{"name": "Morocco"}` → `{"project": summary}` (also becomes the current project).
`POST /api/projects/link` `{"path": "/path/to/workspace", "name": "Pilot"}` → links an existing workspace folder
(not copied). `DELETE /api/projects/<p>` `{"confirm": "<p>"}` → `{"result": "unlinked" | "moved to …/trash/…"}`.

`GET /api/projects/<p>/export.zip` → the whole project as one zip, to keep or to move to another
computer: a consistent copy of the database, `config.json`, the project's codebooks, and the original file of every
document the project has (at its place in `uploads/` or `inputs/`, or as `originals/<doc_id>/<name>` when it was read
from outside the project folder). 0.14.3: nothing else of `uploads/` (before, the whole folder, so the file of a
removed document went along).
Built in a temporary file and sent in chunks; the file name is readable ("Margin project - Demo - 2026-10-28.zip").

`GET /api/projects/<p>/export.qdpx` → 0.18.7 (G5): the project for NVivo, ATLAS.ti and MAXQDA, as a REFI-QDA project (`urn:QDA-XML:project:1.0`: `project.qde` and `sources/<guid>.txt`): every document as its passages joined, the codebooks with labels and the project's own as codes, the hypotheses as codes with *Supports*, *Partly supports* and *Contradicts*, the labels and judgements that count as codings on their quotes (coded by you or by "Margin AI (<model>)"), notes and highlights as memos on their words, and the research log as one memo (`qdpx.export_project`; its docstring has every rule). `?framework=<name>` keeps one codebook (400 for an unknown one); `?threshold=` the strictness a judgement counts at (else Settings'). Built in a temporary file and sent in chunks ("Margin for NVivo - Demo - 2026-11-14.qdpx"). GUIDs are uuid5 of Margin's ids: two exports give the same.
`POST /api/projects/import?name=<name>` with the zip as the raw body → `{"project": summary}` (it becomes the
current project). Without `name` the project keeps the name it had, with " (2)" added when that is taken; a `name`
that is taken → 409. 400 for a file that is not a zip, or a zip without a project (`enlens.sqlite`). Paths in the zip
cannot leave the new project folder, and its size is capped. 0.14.3: the database is checked and opened before the
project is put in place: a damaged zip or one whose database cannot be read → 400 with a plain message, and nothing
is left in `projects/`.

`GET /api/projects/<p>` →
```json
{"name": "Demo", "linked": false, "documents": 3, "hypotheses": 3, "ok": true, "path": "…", "passages": 4,
 "search": {"model": "nomic-embed-text", "passages": 4, "embedded": 4, "complete": true, "models": ["nomic-embed-text"]},
 "frameworks": [{"name": "sdg", "title": "UN Sustainable Development Goals (169 targets)", "label": "SDG target",
                 "source": "bundled", "codes": 169}]}
```
`search`: semantic index state for the embedding model in Settings (`model` "" when embeddings are off; then search
is by keywords only). `embedded < passages` → offer "Build semantic index" (`POST …/index`).

### Sources

`GET /api/projects/<p>/documents` →
```json
{"documents": [{"doc_id": "dab20f86eee", "title": "Water footprint of …", "kind": "pdf", "pages": 3, "chars": 937,
                "passages": 2, "claims": 0, "file": "paper_a.pdf", "added": "2026-10-27 21:27",
                "check": "" | "unreadable text layer" | "very short: check it is the cited work",
                "scanned": "" | "Scanned: text recognised (OCR)" | "Scanned: text recognised (OCR) on 3 of 12 pages"
                           | "Scanned: no text on 2 of 12 pages. Ask IT to install Tesseract to read it.",
                "ocr_pages": 0, "scanned_pages": 0}],
 "search": {…as above…}}
```
`check` non-empty = a quality warning to show. `scanned` non-empty: show it as a note on the document (the text of
recognised pages may contain recognition errors).

Uploading (one request per file, all files of one upload share a `batch` id chosen by the page, `[A-Za-z0-9_-]`):
`POST /api/projects/<p>/uploads?batch=<b>&name=<file name>` with the raw file as body →
`{"batch": "b", "name": "report.pdf", "size": 123}`. Accepted: `.pdf .html .htm .txt .md .zip` (zips are opened,
also nested; a `manifest.csv` inside, columns `file, reference, doi`, names the works). Max 2 GB per file.

`POST /api/projects/<p>/ingest` `{"batch": "b", "exclude": "A_18_* draft*"}` or `{"path": "/Users/me/Reports"}`
(read a folder, zip or file in place, without uploading) → `{"job": Job}` (kind `ingest`).
Ingest job `progress`: `{"done": 3, "total": 12, "file": "report.pdf"}` (then `{"phase": "embedding", "done", "total"}`
while the new passages get vectors). `result`:
```json
{"files": 12, "added": 10, "duplicates": 1, "empty": 1, "passages": 2381, "declared": 0,
 "empty_files": ["scan.pdf"], "mostly_unreadable": ["garbled.pdf"], "failed": ["x.pdf: …"], "excluded": […],
 "ocr": ["scan2.pdf"], "scanned_no_text": ["scan.pdf"],
 "not_in_manifest": […], "documents_added": [document rows as in GET documents],
 "semantic_index": {"added": 2381, "embedded": 2381, "passages": 2381, "complete": true, …} | absent,
 "semantic_index_error": "…" | absent}
```
0.14.3: `failed` also lists a zip, or a file in a zip, that could not be unpacked (`"sources.zip: password-protected
zip: save a copy without the password and add that (report.pdf)"`, `"…: damaged zip: copy or download it again (…)"`),
a damaged Word file and a password-protected PDF (`"x.pdf: password-protected: …"`, before reported as a file without
text); the other files are added. `"stopped": true` when Stop was pressed, also during the text recognition (OCR) of a
scanned PDF, which is then not added.
(optional keys are absent when empty). `ocr`: PDFs whose scanned pages were read by OCR (on this computer, at low
priority). `scanned_no_text`: PDFs with scanned pages that stayed without text (OCR off or not installed): say
"Scanned: no text. Ask IT to install Tesseract to read it." A wholly scanned PDF without OCR is also in
`empty_files` and is not added.

`GET /api/projects/<p>/documents/<doc_id>?offset=0&limit=50` → document details with its passages:
`{"doc_id", "title", "file_title", "file", "kind", "n_pages", "n_chars", "doi", "added_at", "total_passages", "offset",
"passages": [{"passage_id", "seq", "page", "section": "body"|"references"|"reference_like"|"unreadable", "text"}]}`.
With `&view=blocks` (use `limit=500`) it adds the document as a reader cites it: `"blocks": [{"label": "Page 2,
paragraph 3" | "Paragraph 6" | "Page 2" | "The whole text", "n", "page": 2 | null, "paragraph": 3 | null, "start",
"end", "text", "headings": [{"at", "end", "text"}]}]` and `"total_blocks"`. PDFs added from 0.6 on are cited by
paragraph within each page; PDFs added earlier by page; files without pages by paragraph. `start`/`end` are
document offsets of `text`, so a quote at `doc_start + quote_start` (from a result) falls in the block whose range
contains it, at `doc_start + quote_start - start` in its `text`. `headings` are the block's heading lines (offsets
in `text`): show them as headings (bold). The detail also has `"original": {"available": true, "name":
"report.pdf", "reason": ""}` (see below).

`GET /api/projects/<p>/documents/<doc_id>/file` (also `?token=`, for a plain link) → the original file, as the
reader knows it: a PDF inline (`application/pdf`; link to `…/file?token=…#page=3` to open it at a page), a web page
as `text/html` with `Content-Security-Policy: sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src
data:` (no scripts, nothing from the internet, and it cannot reach the app), a text file as `text/plain`. Only the
file recorded when the document was added is served. When it is no longer there (or changed since), the response
is `text/plain` starting with the reason ("The original file is no longer at …; the text the app read is shown
here.") followed by the text the app read. `?check=1` → `{"doc_id", "kind", "name", "available", "reason"}` without
the file: use it to show "Open the original" only when `available`, and the `reason` otherwise.

Opening it at the quote: for a PDF add `#page=N`; for a text file add `&quote=<the quote>` and `#quote`: the file is
then shown as a page with the quote highlighted (found as quotes are), scrolled to it (no script; the same sandbox
policy as web pages; without a match the plain file is sent); for a web page add a text fragment,
`#:~:text=<first words>,<last words>` (browsers that support it scroll to and highlight that text).

**0.15: how a document was read, and the reading view.** The detail adds `"reader"` (1: read before 0.15; 2: the new
reader), `"new_reader"` (the reader new documents get), `"reading"` (the reading report: `{"reader", "engine":
"pdfminer"|"pypdf"|"text", "pages", "pages_with_text", "ocr_pages", "scanned_pages", "multi_column_pages",
"repairs": {"hyphens_joined", "hyphens_kept", "words_split", "ligatures", "spaces", "accents"}, "tables", "blocks":
{kind: n}, "left_out_chars": {kind: n}, "included_share", "passages", "body_passages", "unreadable_passages", "words",
"warnings": [sentence], "quality": "good"|"fair"|"poor"}`; for a document read before 0.15 `{"reader": 1, "older":
true, "pages", "ocr_pages", "scanned_pages", "passages", "body_passages", "unreadable_passages", "warnings": [],
"quality": null}`), `"page_images"` (a picture of each page can be had), `"tables"` and `"paragraphs"` (counts).
0.19: `"languages"`: `{"shares": {code: share of the characters whose language is known}, "blocks": {code: n},
"two": [first, second] | null (a document in two languages), "mixed_passages" (passages that hold both: a reading
before reader 6), "kept": code | null (the language the person keeps), "names": {code: name}, "v"}` (also kept in the
reading report as `languages`, without `kept` and `names`), and `"new_reader_changes"`: whether the new reader would
read it otherwise (a document reader 5 read only when one of its passages holds both of its languages).
With `&view=blocks`, a document read by the new reader comes block by block in reading order (`limit` up to 1000):
each block adds `"kind"` (`title`, `heading`, `abstract`, `body`, `caption`, `table`, `footnote`, `front`, `back`,
`references`, `figure`, `furniture`), `"kind_text"` (in words), `"included"` (searches, codes, themes and checks read
it), `"changed"` (a person restored or left it out), `"box"` (`[x0, top, x1, bottom]` on the page in points from the
top left, or null) and, for a table, `"table": {"n", "caption", "rows": [[cell]]}`. `label` is "Page 2, paragraph 3"
where a paragraph begins, empty where the paragraph above goes on (under its heading, or across a column), and the
kind in words for a block left out. Passages add `"block"` (the kind of block they were made from; null for reader 1),
and their `section` may be `"left_out"`.

`PUT /api/projects/<p>/documents/<doc_id>/blocks/<n>` `{"included": true|false, "alike": false}` → *Restore* or
*Leave out* a block: `{"blocks": [block], "group": [n], "together": n, "alike": n, "doc": {...}}`. `group`: the blocks
chosen (those sharing a passage with it change together). `blocks`: every block that changed, as `?view=blocks` lists
them now, wherever they are in the document (0.16: the first 1000 blocks of the group only before); since a choice is
kept by the block's words, that includes blocks elsewhere with the same words. `doc`: the reading's figures now
(`left_out`, `passages_read`, `passages_all`, as the document's own answer has them), so the reading view shows the
change in place. The choice is kept by the block's words (`block_choices`) and applied again when the document is
read again; choosing what the reader chose (and the start and end marks below imply) removes it. 0.15.1: with
`"alike": true`, every block that looks the same (blocks of up to 200 characters, their numbers and roman numerals
aside: a running head, a page number) changes too; `alike` in the answer is how many. 404 for no such block, 400 when
`included` or `alike` is not a boolean.

`PUT /api/projects/<p>/documents/<doc_id>/bounds` (0.15.1) `{"side": "start"|"end", "block": n|null}` → *Text starts
here* or *Text ends here* at block `n` (`null`: undo): what comes before the start, or after the end, is left out; a
block the person restored there still counts. Kept in `block_choices` as `<side>:<fingerprint>:<k>` (the k-th block
with those words), so it holds when the document is read again. `{"side", "block", "changed", "left_out",
"restored", "blocks", "doc"}`: 0.16: `blocks` are the blocks that changed and the blocks that carry or carried the
mark, as `?view=blocks` lists them now; `doc` as above. 400 for another side, a start after the end (or an end before the start), or a block that is not a
number; 404 for no such block, or a document without blocks (read before 0.15).

In `?view=blocks` (0.15.1), each block also has `alike` (how many other blocks look the same), `share` (where it
stands in the document, 0 to 1) and `bound` (`"start"`, `"end"` or null); `changed` is also true for a block with a
choice of its own.

`PUT /api/projects/<p>/documents/<doc_id>/language` (0.19) `{"keep": "<language code>"|null}` → keep one language of
a document in two (a side-by-side translation): the blocks of its other language are left out of searches, codes,
themes and checks (`null`: both count again). Blocks in both languages (a title printed twice) and blocks whose
language cannot be told still count; a block the person restored or left out themselves keeps their choice. Kept in
`block_choices` as `lang:<code>`, so it holds when the document is read again (one language at a time). Logged as `document-language`. `{"keep", "changed", "left_out", "restored",
"languages", "blocks", "doc"}` (`blocks` and `doc` as for `…/bounds`). 400 when `keep` is not a string or null, or
not one of the document's two languages; 404 for no such document, or one without blocks (read before 0.15). In
`?view=blocks`, a block left out by that choice has `lang_out: {"language", "kept"}` (language names).

`GET /api/projects/<p>/documents/<doc_id>/pages/<n>.png?scale=1.5` (also `?token=`, for an `<img>`) → page `n` of the
original PDF as a PNG (`scale` 0.5 to 3 times 72 dots per inch), drawn with pypdfium2 (the OCR extra); 404 with the
reason when the original is missing or not a PDF, the extra is not installed, or there is no such page. A block's
`box` times `scale` is its place in pixels.

`GET /api/projects/<p>/documents/<doc_id>/tables/<n>.xlsx` → a table the reader found, for Excel: its caption, where
it comes from, then its rows (cells that read as numbers are numbers).

`GET /api/projects/<p>/documents/<doc_id>/reread` → whether the document can be read with the new reader now and what
that would do, changing nothing: `{"ok": false, "reason", "reader", "new_reader", "doc_id", "title"}` when it cannot
(read by the new reader already, the original missing or changed, a task of it waiting or out with Claude Code, almost
no text in the new reading), otherwise the report: `{"ok": true, "moved": false, "doc_id", "title", "reader",
"new_reader", "counts": {kind: {"moved", "not_placed", "left_out"}}` (kinds: `check`, `judgement`, `second_opinion`,
`label`, `claim`, `sdg_check`, `theme_member`), `"not_placed": [{"kind", "kind_text", "what", "quote", "page", "where",
"left_out_kind", "why"}]` (page in the old reading), `"left_out": [{… "note"}]` (placed, in text the new reader leaves
out; page in the new reading), `"remade"`, `"tasks": {"asked_again", "moved", "kept_as_records"}`, `"themes":
{"runs_kept_up_to_date", "runs_out_of_date", "runs"}`, `"passages": {"before", "after", "one_to_one", "body_before",
"body_after"}`, `"ai_share": {"before", "after"}`, `"addons": [{"table", "rows"}]`, `"reading"` (the new reading
report), `"warnings": [sentence]}` (`reread.py`). `POST …/reread` → `{"job"}` (kind `reread`): the move in one
transaction (all or nothing), then the document's search by meaning, the glossary and the keyword pass, as after adding
a document; the job's result is `{"report": {… "moved": true}, "glossary", "codes", …}`. 409 with the reason when it
cannot be done. 0.17.0: while another job of the project runs, the move waits its turn (`waiting_for`) instead of a 409;
the same document asked for again returns the job already there. A move that finds, once its turn comes, that it can no
longer be done ends with `error_kind: "request"` and the reason; nothing changed.

`POST /api/projects/<p>/new-reader` `{"doc_ids"?: [doc_id]}` (0.15.7) → `{"job"}` (kind `new_reader`): the documents an
earlier reader read (only those of `doc_ids`, when given; others are ignored) moved one after the other, each as `POST
…/reread` does, but only when every result finds its place (`reread.move(keep_all=True)`); then, once, search by
meaning, the glossary and the keyword pass. The job's result is `{"moved": [{"doc_id", "title", "results",
"left_out"}], "kept": [{"doc_id", "title", "reason", "not_placed"?}], "stopped", "glossary", "codes", …}`: `kept` are
left as they were, `not_placed` (how many results would have had no place) when that is the reason. Stopping it keeps
the documents moved so far. 400 for `doc_ids` that is not a list; 409 when none is left to move. 0.17.0: while another
job of the project runs, it waits its turn (`waiting_for`) instead of a 409. 0.18.0rc2: `{"keep_unplaced": true}` (the person's *Move anyway*) moves a document even when some results find no
place: those are kept as records that point nowhere, as a move from the document's own page does
(`reread.move(keep_all=False)`). `moved` entries also give `no_place`, `kept` entries `cannot: true` when the document
cannot be read again now, and the result has `summary`: `{"moved", "left_as_they_were", "results_moved",
"results_without_place", "moved_anyway"}`. The list of documents (`GET …/documents`) gives `new_reader`
(`ingest.READER`) beside each document's `reader`, and (0.19) `new_reader_changes`. 0.19: a document reader 5
read is one of "the documents an earlier reader read" only when reader 6 would read it otherwise (a PDF, or a
document one of whose passages holds both languages of a document in two); `POST …/reread` of any other answers 409
with the reason.

`POST /api/projects/<p>/new-reader/preview` `{"doc_ids"?: [doc_id]}` (0.18.0rc2) → `{"job"}` (kind
`new_reader_preview`): the dry run before moving several documents; same `doc_ids` rules, errors and 409 as the move.
Each document is read again by the current reader (`reread.preview`; nothing is stored or changed). The job's result is
`{"documents": [{"doc_id", "title", "ok", "reason", "results", "no_place", "left_out", "not_placed": [{"kind_text",
"what", "quote", "page", "where", "left_out_kind", "why"}]}], "stopped", "summary": {"documents", "clean",
"would_lose", "cannot", "results_without_place"}}`: `clean` documents move with every result in place, `would_lose`
documents have `no_place` results that would find none, `cannot` documents cannot be read again now (`reason`).

`PUT /api/projects/<p>/documents/<doc_id>/reading-checked` `{"checked": bool}` (0.15.7) → `{"checked": {"by", "name",
"at"} | null}`: the person marks the reading as checked (or takes it back). It is kept in the reading report, so a new
reading asks again; the list of documents gives `reading_checked` beside `reading_quality`. 400 for a `checked` that is
not true or false; 404 for no such document; 409 for one read before 0.15 (it has no reading report). The document's
`reading` also has `places` (0.15.7, not stored): for each warning, `"page"`, `"left_out"` or null, where to look.

`DELETE /api/projects/<p>/documents/<doc_id>[?why=<reason>]` → `{"removed": {...counts}}` (past checks keep their
evidence; 0.16: the reason, up to 2,000 characters, goes into the research log, as `{"why": "…"}` in the body does;
the project's notes on the document are kept).
`DELETE /api/projects/<p>/documents` `{"confirm": true}` → removes every document **and every check**.

#### Who may read each document with AI (0.11)

Every document has one of three settings: `cloud` (Claude may read it: the chosen route), `local` (only a model
server on this computer, or a person) and `none` (a person only). A document without its own setting follows the
project's default. The setting is enforced where tasks are made and run (see `access.py`), never by a prompt.

- `GET /api/projects/<p>/documents` adds to each document `ai_access` (the setting that applies now), `own` (its own
  setting, or null for the project's default), `note`, `budget` (a cap in percent, or null), `budget_reached`,
  `sent` (the share of its text Claude has read, 0 to 1) and `sent_passages`; and to the answer `ai_access`
  (`{"default", "chosen", "ask", "banner", "counts": {"cloud", "local", "none"}, "local_only", "ledger_since"}`) and
  `restricted_model` (the local model for restricted documents, `{}` for none). `GET /api/projects/<p>` has the same
  `ai_access` block. `ask`: the project's default was never chosen (made before 0.11 and imported, or through the
  connector): ask once. `banner`: the one-time note of an existing project.
- `PUT /api/projects/<p>/documents/ai-access` `{"doc_ids": [...], "ai_access": "cloud"|"local"|"none"|null,
  "note": "…", "budget": 10|""}` (each key optional; `ai_access` null returns them to the default; `budget` "" removes
  the cap) → `{"documents": n, "tasks_changed": n, …the documents answer}`. Tasks not answered yet take the new
  setting at once; a queued one that is no longer `cloud` leaves the queue. 400 for an unknown setting, 404 for an
  unknown document; `cloud` is refused on a `--local-only` installation.
- Cloud providers: `PUT documents/ai-access` also takes `providers` (a list of provider ids that may read the
  documents, or null for the project's choice), and `PUT /api/projects/<p>/ai-access` takes `providers_default` (a
  list; the default is `["anthropic"]`). In `GET /api/projects/<p>/documents` each document has `providers` (in
  force), `providers_own` (its own list, or null) and, when a provider other than Anthropic has read some of it,
  `sent_by` (`{provider: share}`).
  A document that does not allow
  the provider of the main route is treated as `local` for that route; Claude Code's queue and the connector always
  count as `anthropic`. A model server on another computer is a provider (`other`, or a known one by its address).
- `PUT /api/projects/<p>/ai-access` `{"default": "cloud"|"local"|"none"}` and/or `{"dismiss_banner": true}` →
  `{"ai_access": {…}}`.
- `POST /api/projects/<p>/ingest` takes `ai_access` (who may read the new documents; the first answer in a project
  becomes its default) and `ai_note`. A `manifest.csv` may have `ai_access` and `ai_note` columns per file; an unknown
  value is listed under `manifest_problems`.
- `GET /api/projects/<p>/documents/<doc_id>/ai-sent` → what Claude has read of a document: `{"doc_id", "share",
  "since", "passages": [{"passage_id", "seq", "page", "preview", "times", "first", "last", "features", "routes"}]}`.
- `GET /api/projects/<p>/ai-sent.csv` (also `?token=`) → the ledger: one row per passage sent (Sent at, Route,
  Feature, Document, Document id, Passage id, Page, Task). It also has a Provider column (who received it).
- `POST /api/projects/<p>/hypotheses/<hyp_id>/read-local` → job (kind `read-local`): the excerpts of the check that
  wait for the local model (made in a Claude chat, or while the app was closed) are read by it; without one they wait
  for a person. `result`: `{"hyp_id", "parts", "status"}`. 0.13.11: the job has a check's `progress` (the local
  model's line carries `"who": "local"` and `name`); when this computer has too little memory free for the model it
  ends in `error_kind: "memory"` and the excerpts keep waiting. Body `{"force": true}` starts the model anyway (the
  page's *Start it anyway*).
- `POST /api/projects/<p>/hypotheses/<hyp_id>/judge-local` (0.19.8) → `{"hyp_id", "excerpts"}`: the excerpts of the
  check that wait for the local model wait for the person instead, and no model reads them (the page's *Judge it
  myself*). Each then has `read_by: "you"`, `waiting_for_you` until judged, and `by_choice: true` (the result says
  *Awaiting manual review*, as for excerpts no model may read). 409 while the local model reads this check's excerpts.
- `POST /api/projects/<p>/hypotheses/<hyp_id>/local-again` (0.19.12) → `{"hyp_id", "excerpts"}`: the way back from
  `judge-local` (the page's *Let the local model read them*): those excerpts wait for the local model again; the ones
  the person judged or commented on keep the judgement, which still counts over the model's. Excerpts no model may
  read are not handed back. It does not start the model: `read-local` does (the page calls it next). 400 when no local
  model is chosen.
- `/api/state` adds `restricted` (as `restricted_model` above). Settings: `restricted_server` (`""`, `ollama`,
  `openai`), `restricted_model`, `account_type` (`""`, `personal`, `commercial`).
- The result of a check: each excerpt has `read_by` (`claude`, `local`, `ai`, `you`, `waiting`), `access` (its
  document's setting), `waiting_for_you` (no model may read it and no person has judged it) and `waiting_local`; each
  round in `rounds_info` has `parts` (`[{"task_id", "read_by", "passages", "status"}]`); parts and hypotheses count
  `waiting_for_you` and `waiting_local`. A round's excerpts are split into the task Claude reads (`check:<id>` or
  `…:r<n>`), the local model's (`…:local`) and a person's (`…:person`, answered by no model); it is shown as one round.
  Reading an excerpt again (`POST …/reread/…`) is refused with 409 when no model may read its document.

`POST /api/projects/<p>/index` → job (kind `index`) that embeds passages without a vector; progress `{"done", "total"}`;
result: the `search` state plus `added` and `remaining`; 400 when no embedding model is set.

`GET /api/projects/<p>/passages/<passage_id>?around=1` → a passage with its neighbours, for "show in context":
`{"passage_id", "doc_id", "title", "page", "passages": [{"passage_id", "page", "text", "section", "current": bool,
"start", "breaks"}]}` (404 when the document was removed since; `breaks` as on excerpts, below).

### Frameworks (optional codebooks)

`GET /api/projects/<p>/frameworks` → `{"frameworks": [info], "problems": [{"file", "source", "error"}]}`: the person's own
codebooks first, then the built-in `sdg` and `sdg_goals` (Margin 0.8); `problems` lists codebook files in the folders
that could not be used, with the reason. A CSV may be separated by commas, semicolons or tabs.
`GET /api/projects/<p>/frameworks/<name>` → `{"framework": {...info, "items": [{"code", "description", "group", "group_name"}]}}`.
`POST /api/projects/<p>/frameworks` `{"name": "h2", "csv": "code,description\nH1,…", "title": "…", "label": "hypothesis code"}`
→ `{"framework": info}`; 400 with the row problem. `DELETE /api/projects/<p>/frameworks/<name>`.
0.16: the Codebooks page uses the routes under *Your record* below; these four stay.
`GET /api/projects/<p>/suggest?text=<claim>&framework=sdg&n=5` (no `framework` and no codebook chosen: no codes) → `{"codes": [{"code": "6.4", "group": "6",
"description": "…", "score": 16.9}]}` (keyword match; empty for texts under 10 characters).

### Checking

`POST /api/projects/<p>/checks`
```json
{"text": "Green hydrogen production increases water stress in arid regions.",
 "framework": "sdg", "code": "6.4",          // optional
 "decompose": false, "expand": true,         // defaults from settings
 "k": 8, "per_doc": 2,                        // passages to read per claim; at most this many per document first
 "doc_ids": ["d…"],                           // optional: only these documents
 "semantic": true,                            // use the semantic index when the project has one
 "second_pass": false,                        // default from settings (see below)
 "parts": ["…", {"text": "…", "role": "outcome"}],   // optional, from "Look before checking": the parts to check
 "terms": [["aquifer", "desalination"], []],  // optional: the extra search words, one list per part
 "edited": {"parts": false, "terms": true},  // optional: whether the person changed what the AI proposed
 "from_doc": "d…"}                            // optional (0.19.0): started from this document's text
```
→ `{"job": Job}` (kind `check`). 400 for a text under 10 characters or an unknown code (or a part under 10
characters: "Part 2 is too short…"); 502 when no model service is usable. The job's `result` is
`{"hyp_id": "h…", "status": "contested"}`. 0.19.0 (N3): with `from_doc` (a working document's *Check against the
corpus*) the hypothesis records `origin` `"document"` and `origin_id` the document's id, and its result gains
`origin_title` (the document's title, or its file's name; left out once the document is gone). 400 when `from_doc`
is not a document of the project. The words keep that document's AI setting (`docrole.origin_floor`, as an add-on's
draft does, see EXTENDING.md): from a document marked *Only a local AI* only a local model splits them, proposes
their search words and judges their excerpts (by queue, Claude Code splits nothing and proposes no words: they are
searched as written); from one marked *No AI* no model reads them, they are searched as written and every excerpt
waits for the person's judgement. The result then gains `words_access` (`"local"` or `"none"`), and the connector
does not list or open the check.

With `parts`, the hypothesis is not split by the model: one part = checked as written (1–6 parts). With `terms`, the
model writes no extra search words: each part is searched with its own words plus that list (`[]`: its own words
only); a flat list is the list of a hypothesis checked as one part. The hypothesis's `options.prepared` records
`{"parts": bool, "terms": bool, "edited_parts": bool, "edited_terms": bool}`.

`second_pass`: after the keyword (and meaning) search, the best 3 × k candidates are sorted again, without any
model, by how closely they word the hypothesis (the best sentence's share of its words, weighted by how rare they
are, and its word pairs found side by side), in steps of 0.1 so the first order decides between equals. Recorded as
`options.second_pass`. On the pilot (178 VCA claims with cited sources, `tools/eval_second_pass.py`) it brought
slightly fewer excerpts from the cited sources into the top 8 (147 against 154), so it is off by default.

#### Look before checking

`POST /api/projects/<p>/prepare` `{"text": "…", "decompose": true, "expand": true, "framework", "code", "from_doc"}`
→ job (kind `prepare`, uses the model, progress like a check). `result`:
```json
{"parts": [{"text": "Hybrid work improves wellbeing.", "role": "outcome"}, {"text": "…", "role": "outcome"}],
 "terms": [["well-being", "life satisfaction"], ["isolation", "younger workers"]],
 "split": true}
```
`terms` are the AI's extra search words for each part (the part's own words are always searched, so they are left
out). Nothing is kept in the project. Show the parts as editable lines and the words as removable chips, then send
the check with `parts`, `terms` and `edited`. 0.19.0 (N3): `from_doc` as for a check: words from a document no model
you have may read come back unsplit and with no extra words.

Check job `progress` (poll it to draw the live panel):
```json
{"message": "Reading 8 passages with qwen3:8b", "elapsed": 23.4,
 "decompose": null | {"label": "Splitting into claims", "state": "running"|"done", "detail": "3 claims to check",
                      "seconds": 3.2, "parts": ["…", "…"]},
 "parts": [{"part": 1, "text": "…" | null,
            "steps": [{"key": "terms", "label": "Search terms", "state": "pending"|"running"|"done",
                       "detail": "9 search terms: …", "seconds": 2.3, "info": {"terms": […]}},
                      {"key": "rank", "label": "Passages", …, "info": {"passages": 8, "documents": 5}},
                      {"key": "grade", "label": "Reading and grading", …, "info": {"graded": 3, "ok": true}}]}],
 "model": null | {"phase": "waiting"|"thinking"|"writing"|"done", "seconds": 12.0, "prompt_tokens": 2700,
                  "thinking_tokens": 0, "answer_tokens": 140, "rate": 11.7, "cap": 1500, "thinks": false,
                  "tail": "latest words the model wrote", "line": "Model is writing its answer · 12 s · 140 answer tokens · 11.7 tokens/s"},
 "batch": null}
```
`parts` grows as the check moves on (one entry per claim checked so far; `part` 0 = the hypothesis as written).
The `terms` step is absent when `expand` is false. `model` is filled by local servers while they stream.

`POST /api/jobs/<id>/cancel` → stops the job (a stopped check leaves nothing in the history; 0.19.13: except a check by
queue whose Claude Code part is done, kept with its excerpts waiting for the local model).

The check prompt is `check-v3`: for each excerpt the AI may add a `scope_note`, a short phrase such as "about
fully remote workers, not hybrid", when the excerpt is about another group, setting, place or period than the
hypothesis names; such an excerpt supports it at most partly (the app applies that rule when it stores the answer).
No extra model call. Excerpts read with `check-v2` (0.5) have no note.

`POST /api/projects/<p>/claims/<claim_id>/more` `{"k": 8, "terms": ["repurposing", "pipeline reuse"]}` → job
(kind `more`): reads the next best passages for one claim (none shown before), with new search terms if given, and
grades them as a further round. `result`: `{"claim_id", "hyp_id", "round": 2, "passages": 8 | 0, "ok": true}`
(`passages: 0` = nothing further matches).

Batches: `POST /api/projects/<p>/batches/preview` `{"text": "…"}` → `{"items": [{"text", "framework", "code"}], "count"}`.
`text` is one hypothesis per line (lines starting with `#` skipped) or CSV with a column `hypothesis` (or `claim`,
`text`, `statement`) and optional `framework`, `code` (or `target`). At most 500.
`POST /api/projects/<p>/batches` `{"text": "…"}` or `{"items": […]}`, plus the check options → job (kind `batch`).
Batch job `progress` is the check progress of the current hypothesis plus
`"batch": {"index": 3, "total": 12, "text": "…"}`. `result`:
`{"batch_id": "b…", "checked": ["h…", …], "errors": [{"index", "text", "error"}], "stopped": null | "message", "total": 12}`.
`GET …/hypotheses?batch=<batch_id>` lists that batch, in the order the hypotheses were given.

Near-duplicates (0.18, roadmap N1; `nearduplicates.py`, by key words, no AI):
`POST /api/projects/<p>/hypotheses/similar` `{"lines": ["…", "…"]}` (at most 500) →
```json
{"pairs": [{"a": 0, "b": 1, "score": 0.75, "differ": []},
           {"a": 1, "b": 2, "score": 1.0, "differ": ["indicate", "predicted"]}],
 "before": [[{"hyp_id": "h…", "text": "…", "created_at": "2026-11-03T10:12:00+00:00", "score": 0.8, "differ": []}], []]}
```
`pairs`: lines of the list (0-based) that say nearly the same; `differ` names the words that make them claim different
things (strength, direction, a negation), and then the page offers no merge. `before`: per line, the hypotheses checked
before in the project that say nearly the same and claim the same (the closest first, at most 3).

### Results

`GET /api/projects/<p>/hypotheses?threshold=0.6&q=<words>&status=<status>&batch=<id>&limit=<n>` →
```json
{"hypotheses": [{"hyp_id": "h…", "claim_id": "…", "created_at": "2026-10-27T21:26:09+00:00", "text": "…",
                 "framework": "", "code": "", "status": "contested", "status_any": "contested",
                 "supports": 2, "partly": 2, "refutes": 2, "uncounted": 1, "corrected": 0, "reviewed": 3, "to_review": 5,
                 "docs_supporting": 2, "docs_partly": 1, "docs_refuting": 1, "passages_read": 8, "parts": 2,
                 "model": "qwen3:8b", "batch_id": "", "lean": 0.4, "code_label": "", "note": ""}],
 "counts": {"contested": 2, "unsupported": 1}, "threshold": 0.6}
```
newest first; `counts` cover the whole project (not the filter). 0.6 adds `docs_added_since` (documents added to the
project since the check that it has not read from: tag "documents added since") and `disagreements` (excerpts
where a second opinion differs from the AI's judgement: tag "second opinion differs on N"). 0.11.2 adds
`status_before_stronger`: the answer the first model gave when a stronger model read excerpts again and changed it
(else null). `supports`/`partly`/`refutes` count the excerpts whose
judgement counts at this threshold, `uncounted` those below it; `docs_*` count documents as the result page does;
`reviewed` counts the excerpts you judged (agreeing or not), `corrected` those where you changed the AI's judgement,
`to_review` the excerpts read that you have not judged yet.
`status_text` is null, or the words for a status that says more than its code: *Waiting for your local model*, or
(0.14.3) *Waiting for your judgement*.

`GET /api/projects/<p>/hypotheses/<hyp_id>?threshold=0.6` (404 when there is no such result; 0.14.3: the answer then
carries `"in_project": "<name>"` when another project holds it, as happens when another window switched the project) →
```json
{"hyp_id": "h…", "text": "…", "framework": "sdg" | null, "code": "6.4" | null,
 "code_description": "…", "code_label": "SDG target",           // present with a code
 "created_at": "…", "options": {"k": 8, "per_doc": 2, "expand": true, "decompose": true, "doc_ids": [],
                                "backend": "ollama", "model": "qwen3:8b", "search": "keywords+meaning", "embed_model": "…"},
 "decomposed": true, "model": "qwen3:8b", "batch_id": null, "note": null | "user's note", "threshold": 0.6,
 "status": "contested", "status_any": "contested", "status_text": "Mixed evidence",
 "balance": {"docs_supporting": 2, "docs_partly": 1, "docs_refuting": 1, "docs_both": 1, "docs_counted": 3,
             "excerpts_uncounted": 2, "lean": 0.42},
 "who": [{"doc_id": "dab…", "title": "…", "side": "supports" | "partly" | "refutes", "excerpts": 2,
          "locations": ["paragraph 6 of 8"], "both_sides": false}],
 "documents_in_project": 6, "passages_in_project": 31, "excerpts_read": 16,
 "reviewed": 3, "corrected": 1, "to_review": 13, "to_review_relevant": 5,
 "incomplete": false,                      // a part failed or is not graded yet (not: it waits for your judgement)
 "models_used": [{"model": "sonnet", "roles": ["search words", "judging the excerpts"]},
                 {"model": "opus", "roles": ["judging again as the stronger model"]}],   // 0.14.3
 "rationale": "…" | null,                  // the model's summary (single-part hypotheses)
 "parts": [{
    "claim_id": "u…", "hyp_id": "h…", "part": 1, "role": "outcome" | null, "claim": "…",
    "status": "supported", "status_any": "supported", "balance": {…}, "rationale": "…" | null,
    "terms": ["…"], "model": "qwen3:8b", "rounds": 1, "round_status": "done", "errors": [],
    "target": "6.4" | null, "target_description": "…", "threshold": 0.6, "options": {…}, "created_at": "…",
    "passages": [{"n": 1, "round": 1, "passage_id": "dab…:0001", "doc_id": "dab…", "title": "…", "page": 2 | null,
                  "text": "full passage text", "found_by": "keywords" | "meaning" | "both",
                  "verdict": "supports" | "partially_supports" | "refutes" | null, "confidence": 0.82 | null,
                  "quote": "…" | null, "quote_start": 31 | null, "quote_end": 97 | null, "in_corpus": true}]
 }]}
```
Each passage also has: `ai_verdict` (the AI's own grade or null), `user_verdict` (`supports`, `partially_supports`,
`refutes`, `not_relevant` or null) and `user_note`, `verdict` (the one that counts: the person's if given),
`counted` (true when it counts at this threshold), `certainty` ("high" ≥ 0.8, "medium" ≥ 0.6, "low"), `reviewed`
(a person judged it) and `changed` (their judgement differs from the AI's), `location` (where the quote is: "page 2",
"paragraph 6 of 8"; without a quote, the excerpt's span; documents stored before 0.5.1: "about 40% into the
document"), `span` (what the whole excerpt covers: "paragraphs 1–6 of 8", "pages 2–3"), `doc_start` (the document
offset where the excerpt starts), `position_pct`, `quote_by` ("the AI", "you" when the person chose the sentence, or
null) and `ai_quote` (the AI's own quote). Each part also has `who` and `balance`. Each part has
`rounds_info`: `[{"round", "status", "passages", "terms": [words searched for in that round], "ai_note": "the AI's own
note on that round's excerpts"}]`, and (this endpoint only) `more_available`: false when "read more" would find
nothing new. `who` lists the documents behind the answer by side, with the same rule as `balance` (a document with
counted excerpts both for and against appears twice, `both_sides: true`). `to_review_relevant` counts the AI's
judgements for or against that you have not reviewed yet. 0.14.3: the hypothesis's `reviewed`, `corrected`,
`to_review`, `to_review_relevant` and `disagreements_to_review` count your own judgements (the Excel columns say "you"). `models_used` lists every model whose accepted answers the check
used, in the order they first answered, with what each did (from the answers themselves: a stronger model, the local
model for restricted documents, a model changed in Settings before Claude Code answered); `model` stays the one chosen
when the check started. Each passage has `ai_read`: false when no model's judgement of it is stored (an excerpt no
AI may read, or one whose part waits or failed); `round_failed`: its round's check failed, so no AI judgement of it
counts (`counted` false; a person's own counts only when another round of the check was answered); and `my_verdict`:
your own verdict (null when you gave none; in Margin the same as `user_verdict`). A client that saves your comment
sends `my_verdict` with it.
New in 0.6, on each passage:
- `breaks`: `[{"at": 82, "kind": "paragraph"}, {"at": 120, "kind": "heading", "end": 127}]` (offsets in `text`):
  where a new paragraph or a heading begins inside the excerpt, from the layout found when the document was added.
  Start a new paragraph at each `at`; show `text[at:end]` of a heading as a bold line. Empty for documents added
  before 0.6 (show the text as one block, as before).
- `location` / `span` for PDFs added from 0.6 on: "page 2, paragraph 3" / "page 2, paragraphs 1–4" or "pages 2–3".
- `scope_note`: the AI's note that the excerpt is about another group ("about fully remote workers, not hybrid"),
  or null. Show it as a chip: "About another group: …".
- `reread` (bool) and `ai_history`: `[{"verdict", "confidence", "quote", "scope_note", "model", "at",
  "replaced_at"}]`, oldest first: the AI's earlier judgements of this excerpt, when it was asked to read it again.
  `ai_verdict` / `confidence` / `quote` are its latest. Show "Read again by the AI: was Supports (75%), now Partly
  supports (59%)". `reread_info` (null, or `{"hint", "rationale", "model", "at"}`) is about the latest re-read: the
  person's comment given as a hint (null: none) and the AI's reason, which says whether the hint changed its
  judgement. Show the reason with the new judgement.
- `second`: null, or the second model's judgement `{"model", "verdict" (null = not about the hypothesis),
  "confidence", "quote", "scope_note", "at", "agrees"}`; `agrees` compares it with the main AI's own judgement
  (`ai_verdict`). Show "Second model: Contradicts (70%), disagrees".

Each part also has `disagreements` (excerpts where the two models disagree). The hypothesis has `second_models`
(the second models that read it), `second_read` (excerpts with a second judgement), `disagreements`,
`disagreements_to_review` (of them, not reviewed by a person yet: send "Next to review" there first),
`docs_added_since` (`[{"doc_id", "title", "added_at", "matching"}]`: documents added to the project after the check
that none of its rounds read from; `matching` = it has an excerpt that shares a word with the hypothesis) and
`docs_added_since_matching`. Say "2 documents were added since this check; 1 has matching excerpts. Read them."

`passages` are sorted: supports, partly, refutes (counted ones first, each by confidence), then the ones with no grade. Highlight
`text[quote_start:quote_end]` (character offsets into `text`). A grade with `confidence < threshold` is shown but
marked weak ("below the threshold"). `in_corpus: false` = the document was removed since (no "show in context").
`errors` lists why grading failed (status `failed`).

`PUT /api/projects/<p>/claims/<claim_id>/judgements/<passage_id>` `{"verdict": "refutes", "note": "the next sentence
says the opposite", "quote": "Loneliness did not rise among hybrid workers of any age."}` → `{"saved": true}`: the
person's own judgement of one excerpt (`supports`, `partially_supports`, `refutes`, `not_relevant`; `null` removes it,
with its sentence, and the AI's counts again). Agreeing with the AI = sending the AI's own verdict (`not_relevant`
for an excerpt it found not about the hypothesis). `quote` (optional) is the sentence the judgement rests on: text of
this excerpt (400 otherwise); left out, an earlier one is kept; `""` removes it. From 0.6, `{"verdict": null,
"note": "…"}` keeps only a comment: it is not a judgement (`reviewed` stays false, the AI's judgement counts, and it
is not counted as agreeing with the AI). "Go back to the AI's judgement" with the comment kept is `{"verdict": null,
"note": "<the comment>"}`; `{"verdict": null}` removes both.

`POST /api/projects/<p>/claims/<claim_id>/reread/<passage_id>` `{"note": "…"}` (optional) → job (kind `reread`):
the AI reads this one excerpt again, alone, with the check prompt. The person's comment (`note`; left out: the
comment saved with their judgement, if any) is added as a hint ("A reader noted: …"). The new judgement replaces the
AI's for this excerpt and the earlier one goes to `ai_history`; a person's own judgement is not changed and still
counts. `result`: `{"claim_id", "passage_id", "hyp_id", "ok", "before": {"verdict", "confidence"}, "after":
{"verdict", "confidence", "scope_note", "rationale"} | null}`. 404 when the excerpt was not read for this claim.

`POST /api/projects/<p>/hypotheses/<hyp_id>/read-new` → job (kind `read-new`): reads the documents added since
the check (those with matching excerpts), for every part, as a further round restricted to them; the check is not
run again, so reviews are kept. Documents without a matching excerpt are only marked as looked at, so the
hypothesis no longer counts them. `POST /api/projects/<p>/read-new` `{}` (every hypothesis with documents added
since), `{"hyp_ids": […]}` or `{"batch": "b…"}` → one job that does this for each, one after the other (400 when
none has new documents). `result`: `{"hypotheses": [{"hyp_id", "documents", "matching", "passages", "rounds"}],
"passages"}`.

`GET /api/projects/<p>/hypotheses/<hyp_id>/unread` (roadmap N5, 0.18.7) → the documents this check never showed an
excerpt of, asked again of the keyword search with each part's claim and search words (no model reads anything):
`{"hyp_id", "checked": false before the check read anything, "considered": documents it could have read,
"matching": [{"doc_id", "title"}] (an excerpt holds at least two different words of a part and its search words),
"matching_n", "one_word_n" (single words in common only), "no_word": [{"doc_id", "title"}], "no_word_n"}`; each list
sorted by title and cut at 200 (the counts are whole). Theory documents, documents added after the check (its
documents added since), documents with no readable text and those a limited check was limited away from are left
out. A neutral count: it changes no result. `POST /api/projects/<p>/hypotheses/<hyp_id>/read-unread` → job (kind
`read-unread`): reads the `matching` group for every part (each part the documents that hold its own words, within
its limit) as a further round limited to them, as `read-new` does; the check is not run again, so reviews are kept.
400 when there are none. `result`: `{"hyp_id", "documents", "passages", "rounds": [{"claim_id", "round", "passages",
"ok"}]}`.

`POST /api/projects/<p>/second-opinion` `{"hyp_ids": […]}` or `{"batch": "b…"}` → job (kind `second-opinion`): the
second model of Settings (`second_model`) grades every excerpt these checks already read, with the same prompt. Its
judgements are kept apart (`second` on each excerpt) and never change an answer. Only one model is in memory at a
time: the main model is unloaded first and the second one at the end (Ollama; LM Studio and other
OpenAI-compatible servers have no standard way to unload, so the server's own setting decides there). Excerpts the
second model already graded are not asked again. 400 when no second model is chosen or it is the main one; 502 when
it is not installed. `result`: `{"hypotheses", "rounds", "graded", "skipped", "failed", "unloaded": ["qwen3:8b",
"llama3.1:8b"]}`, counted in rounds of excerpts (`skipped`: rounds this second model had already graded).

The progress of the shorter model jobs has only the steps they make: `prepare` the "terms" step (and `decompose`),
`reread` and `second-opinion` the "grade" step.

#### Evidence map

`GET /api/projects/<p>/map?batch=&threshold=` →
```json
{"threshold": 0.6,
 "hypotheses": [{"hyp_id": "h…", "text": "…", "status": "supported", "status_text": "Supported by your documents",
                 "docs_counted": 1, "single_document": true, "batch_id": ""}],
 "documents": [{"doc_id": "d…", "title": "…", "answers": 2, "decides": 2, "key": true, "in_project": true}],
 "cells": {"h…": {"d…": {"side": "supports" | "partly" | "refutes" | "both", "excerpts": 2}}},
 "documents_without_evidence": 3}
```
Cells follow the rule of `who` (judgements that count at this strictness; a person's always count): `both` = the
document has counted excerpts for and against. `single_document`: the answer rests on one document. A document
`decides` an answer when leaving out its excerpts would change that answer; `key` = it decides at least two answers
and at least a fifth of them. `documents` lists only documents with counted excerpts (most answers first);
`documents_without_evidence` counts the others. Draw a grid with symbols as well as colours (+, (+), −, ±).
`GET /api/projects/<p>/map/documents?threshold=` → how many answers each document is behind (the map's counts,
without its leave-one-out), for *Documents* grouped by *Answers behind them*.

#### Calibration

`GET /api/projects/<p>/calibration` →
```json
{"bins": [{"from": 0.0, "to": 0.5, "judged": 0, "agreed": 0, "rate": null},
          {"from": 0.5, "to": 0.6, …}, {"from": 0.6, …}, {"from": 0.7, …}, {"from": 0.8, …}, {"from": 0.9, "to": 1.0, …}],
 "total": 34, "agreed": 27, "minimum": 20, "threshold": 0.6,
 "suggestion": {"threshold": 0.7, "reason": "When the AI was at least 70% sure, you agreed with it in 85% of the 26
                excerpts you judged."} | null,
 "note": "" | "Judge at least 20 of the AI's judgements to get a suggestion (12 so far)."}
```
From the excerpts a person judged that also have an AI judgement for or against: how often they gave the same
judgement, by the AI's certainty (marking an AI "supports" as not about the hypothesis is a disagreement). A comment
alone is not a judgement. For an excerpt the AI was asked to read again, its first judgement is compared (the
later ones may follow the person's own hint). The
suggestion is the lowest strictness from which on agreement is at least 80% (starting at a bin with at least 3
judgements), once at least 20 were judged. Show it next to the strictness: a small chart and "Use 70%".

`DELETE /api/projects/<p>/hypotheses/<hyp_id>[?why=<reason>]` → `{"deleted": "h…"}` (0.16: `why` as for a document).
`PUT /api/projects/<p>/hypotheses/<hyp_id>/note` `{"note": "…"}` → `{"saved": true}`.
`GET /api/projects/<p>/hypotheses/<hyp_id>/export.xlsx` → an Excel file for people, in the app's own words and local
times, with two sheets: *Summary* (one row per hypothesis: answer, answer for each part, documents per side, excerpts
that count / too uncertain / read, judgements reviewed and changed by you, excerpts you have not reviewed yet, notes,
code, strictness, every AI model whose answers the check used and what each did, for a methods section) and
*Excerpts* (every excerpt read: judgement, judged by, the AI's own judgement, AI certainty, counted in the answer,
quote and who chose it, document, where, the person's comment, the full excerpt, notes, code). 0.14.3: an excerpt no
AI judged says so: *Judged by* "nobody yet" (until you judge it) and *AI's own judgement* "Not read by an AI: kept for
your own judgement", "Not read yet: it waits for your local model" or "Not read: the AI's answer could not be used".
`.csv` and `.json` give the technical forms.
`GET /api/projects/<p>/export.xlsx?threshold=` → the same for every check of the project, plus a sheet *Map* (the
evidence map: one row per hypothesis, one column per document, + supports, (+) partly, − contradicts, ± both, with
the number of excerpts that count); `export.csv` the technical CSV (ids, raw verdicts, UTC times). File names are
readable ("Margin results - <project> - <date>.xlsx"). From 0.6 the *Excerpts* sheet also has "About another group
(AI's note)" and "AI's earlier judgement (before reading it again)", and, when a second model read any of the
excerpts, "Second model", "Second model's judgement", "Second model's certainty", "The two models agree". The
*Summary* sheet has "Excerpts where the second opinion differs" (0.11.2; before: "…a second model disagrees"),
"Answer before a stronger model read it again" (0.11.2), "Documents added since the check", (0.18.7, roadmap N5)
"Documents with the search words never read" and (0.19.0, roadmap K3) "Answer counting non-scientific documents"
(the answer counting the documents marked Non-scientific, `status_all_sources`; filled only where it differs from
"Answer") and "Non-scientific documents counted here" ("yes: " and the reason, for a check set to count them; else
empty).

### Exploring the documents (0.7)

All of these work without a model except where a job says *the AI*. Model jobs run one at a time like checks, and
every answer they store records the model, its digest, the prompt version, the seed and the settings
(`provenance`); every Excel download of these pages ends with the sheet *How these results were made*.

#### Search (F1)

- `GET /api/projects/<p>/search?q=&mode=any|all|phrase|near|meaning&near=5&exact=1&all=1&docs=a,b&code=sdg:6.4&sort=doc|left|right&offset=0&limit=200`
  → `{query, mode, words, total, passages, documents, per_doc: [{doc_id, title, hits, passages}], lines: [{n,
  doc_id, title, passage_id, page, location, left, node, right, marks, start, end}], other_forms: [{word, count}],
  rarest, offset, limit}`. `start`/`end` are document offsets (open `#/doc/<id>?q=<start>-<end>`). `exact` turns
  stemming off; `all` includes reference lists and front matter; `other_forms` are words of the documents that
  start like a searched word but are not found by it (*commuters* for *commuting*). `mode=meaning` (needs an
  embedding model) returns `{passages: [...]}`, whole passages ranked by keywords and meaning together.
- `GET /api/projects/<p>/search.csv|xlsx?…` the same lines (all of them, up to 50,000); the Excel file adds *Per
  document* and *Words around it*.
- `GET /api/projects/<p>/collocates?q=…&window=5&order=typical|often` → `{hits, window, window_words, min_count,
  order, words: [{word, stem, count, corpus, pmi}]}`: words within `window` (1–15) words of the hits, seen there at
  least `min_count` times (3, or one in a thousand hits); `typical` ranks by pointwise mutual information.

#### Profiles with a codebook (F2)

- `GET /api/projects/<p>/profile?framework=<codebook>&level=code|group|practice&docs=` (409 with no codebook named or chosen) → the keyword pass status (`pass1`), the
  grid documents × codes (`grid`), counts by source (`stats`), the codebooks (`frameworks`, each with `groups`).
  0.9: `level=practice` (codebooks with `practice_and_element`): `grid.rows` is `"practices"`, `grid.documents` are
  the practices (`doc_id` is the practice's key, `title` its most frequent wording, with `in_documents` and
  `elements`), `grid.directions` counts helps and hinders per cell, `grid.unnamed` the labels naming no practice.
  0.16: `pass1.codebook_changed` is true when the codebook's codes or the words they are matched by changed since the
  keyword pass; `removed_codes` is `[{"code", "labels"}]`, codes taken out of the codebook whose labels wait and are
  not counted; `stale_codes` is `{code: {"since", "passages"}}`, codes whose wording changed after the AI labelled
  with them. Labels first follow the codebook's renames and merges (`codebooks.follow`).
- `GET /api/projects/<p>/frameworks` and `…/frameworks/<name>` (0.9): each codebook also has `direction_words`,
  `direction_note`, `one_main`, `practice_and_element`, `send_all` (30 codes or fewer: sent whole to the AI),
  `stance` and `sources`; with its codes (`items`), each also has `keywords`, `include`, `exclude` and `source`, and
  (0.16) `examples` when it has any.
- `POST /api/projects/<p>/profile/keywords {framework?}` → job: the keyword (and meaning) pass, seconds.
- `GET /api/projects/<p>/profile/plan?framework=&docs=&all=1|0` → `{all_passages, whole_codebook, codes, passages,
  with_candidates, already_read, to_read, estimate_seconds, run: {now, last, changed}}`; `changed` lists what differs
  from the last run (model, digest, prompt, seed, settings). Without `all` (0.9), the codebook's default: every
  passage for a small codebook without a lexicon (the practice codebooks), else those with a candidate.
- `POST /api/projects/<p>/profile/label {framework?, doc_ids?, all_passages?, limit?, passage_ids?}` → job: the AI
  reads the passages (task `label`, prompt `label-v2`; `all_passages` left out: the codebook's default, as for the
  plan; 0.16: `passage_ids`, a list, reads only these passages, as `POST …/codebooks/<name>/relabel` does). Its
  result: `{read, failed, planned, stopped, changes: {confirmed,
  not_confirmed, added}}`.
- `POST /api/projects/<p>/profile/compare {…}` → job: a second model labels the same sample (`benchmark` measure).
- `GET /api/projects/<p>/profile/calibration?framework=` → how often people agreed with the AI per certainty.
- `GET /api/projects/<p>/profile.xlsx?framework=&level=` → *Documents by code* (*Practices by code* with
  `level=practice`; *Practice* and *Element* columns in the labels for such codebooks), every label with its quote, reason
  or matched words, and *Key terms per document*.
- `GET /api/projects/<p>/documents/<id>/profile?framework=` → the codes of one document, each with its passages,
  locations, quotes, reasons, matched words and who labelled them; 0.9: `direction_words`, `practice_and_element`,
  `one_main`, and each item's `practice` and `element`.
- `POST /api/projects/<p>/labels {framework, passage_id, code, quote?, relevance?, direction?, note?, practice?,
  element?}` → a label of a person's own. `PUT /api/projects/<p>/labels/<label_id> {decision:
  accept|change|reject|clear, relevance?, direction?, note?, practice?, element?}` (practice and element: 0.9).

#### Terms and concepts (F3) and key terms (F6)

- `GET /api/projects/<p>/terms?q=&sort=&offset=&limit=` → the glossary (`status`, `terms`, `concepts`).
  `POST /api/projects/<p>/terms/build` → job: rebuild it (seconds; also run after documents are added).
  The answer's `stale` is `documents_changed` or `words_changed` (0.17: what it leaves out changed).
- `GET /api/projects/<p>/terms/words` → what the glossary and key terms leave out (0.17): `languages`
  (`code`, `name`, `passages`, `on`) found by the last build, `off` (codes switched off), `own` (the
  project's own words and phrases), `status`, `max_own`. `PUT` with `off` (a list of codes; not `en`) and/or
  `own` (a list, or one per line) saves them (400 on an unknown code or a word over 80 characters); the
  glossary is then out of date: `POST .../terms/build` makes it again.
- `GET /api/projects/<p>/concepts?name=…` → the concept a wording belongs to. `GET /api/projects/<p>/concepts/<term_id>?refs=1&offset=&limit=`
  → the card: `wordings` (with `joined_by` and `joins`), `documents` (with `first`, `first_end`,
  `first_location`), `lines`, `related`, `suggested_wordings`, and (0.9) `in_labels`: the codebook labels whose
  practice or element contains a wording of the concept, `[{framework, framework_title, code, description, role:
  practice|element, passages, examples}]`.
- `PUT /api/projects/<p>/concepts/links {a, b, decision: accept|reject|change|add, relation?, note?}`; `relation`:
  same, broader, narrower, related, different, or (0.9) an element relation: requires, required_by, shapes,
  shaped_by, replaces, replaced_by, element_of, has_element, clashes_with (as seen from `a`).
  A person's `different` keeps a wording from being proposed again.
- `POST /api/projects/<p>/concepts/judge {pairs?, relations?: words|elements, term?}` → job: the AI judges proposed
  pairs (task `link`, prompt `link-v2`). 0.9: `relations: "elements"` asks how they relate as elements of a practice;
  with `term` and no `pairs`, the pairs are that concept and up to 8 concepts often mentioned with it.
  `POST /api/projects/<p>/concepts/<term_id>/wordings` → job: the AI proposes other wordings the documents use.
- `GET /api/projects/<p>/documents/<id>/terms?n=15` → key terms with their places (`spans`) for underlining;
  `GET /api/projects/<p>/passages/<id>/terms` → the key terms of one passage.
  In a project of one document, a document's key terms are weighed by the share of its passages a term occurs in
  (Margin: there is no other document to contrast it with).
- (Margin) `GET /api/projects/<p>/documents/<id>/skim?framework=` → the one-page report on one document, made without
  AI (`skim.py`): `facts {pages, words, minutes, sections, sentences}`, `documents_in_project`, `abstract`, `outline`
  (`title, start, end, page, words, share, references`), `key_terms {basis: document|corpus, terms}`,
  `key_sentences` (each with `terms`), `aims`, `findings`, `claims {total, own, others, cited, uncited, by_kind, kinds,
  items, cut}` (each item `kind, why, cited, own`), `cited {markers, works, numbered_entries, top, dois,
  references_at, references_page}` and `codes` (or null). Every item has `start, end, text, page, section`.
  `GET /api/projects/<p>/documents/<id>/skim.md` → the same as Markdown, to download.

#### Themes (F4)

- `GET /api/projects/<p>/themes` → `{runs, auto_mode, auto_why, k}`; each run has `themes_now` (after merges and
  removals).
- `POST /api/projects/<p>/themes {k?, seed?, mode?: auto|meaning|words}` → job: a new set of themes (spherical
  k-means, in numpy when it is installed and otherwise in plain Python, with the same result; the same documents and
  settings give the same themes). A small project gets fewer themes than `k`
  (about three passages a theme); fewer than 5 passages is an error.
- `GET /api/projects/<p>/themes/<run>?framework=` → the themes (names, key terms, size, documents,
  representative passages), `removed` (the themes a person removed, without a `number`), `doc_grid` and
  `code_grid` (without the removed themes' passages). Each theme has `removed`, `removed_at`, `replaces` (`{theme_id,
  name}` of the removed theme a new theme was found in place of, or null), `replaced_by` and `drawn_from` (`[{theme_id,
  name, passages}]`: the themes a new theme took its passages from); `edits` also counts `removed` and `added`.
  `GET …/themes/<run>/<theme_id>?offset=&limit=` → one theme (a removed one too) and its passages (built from that theme alone: `themes.view(only=)`). `DELETE
  …/themes/<run>[?why=<reason>]` (0.16: `why` as for a document).
- `PUT /api/projects/<p>/themes/<run>/edit {what: rename|merge|move|remove, theme_id?, value?, passage_id?, why?}`
  (0.16: `why`, an optional reason, goes into the research log; each edit also keeps the state before it as a version):
  rename, merge and move are kept as reviews, so they survive a new set with the same settings; `value: null` (or
  `""` for a name) undoes. `remove` with `value: true` leaves a theme and its passages out of the themes, `false`
  brings it back; it belongs to this set only. A removed theme takes no merge and no moved passage (400), and the
  last theme shown cannot be removed.
- `POST /api/projects/<p>/themes/<run>/new {replaces: <theme_id>}` → job (`theme-new`, scope: the run): a new theme
  in place of a removed one, on this computer and without AI (one more k-means step with the other centres fixed;
  it takes only passages closer to it than to their own theme and to every removed theme). Its result is
  `{theme_id, replaces}`. A theme that is not removed, or already has a new theme in its place, is a 400. 0.17.0: while
  another new theme is being found for the same set, it waits its turn (`waiting_for`) instead of a 409; the same
  removed theme asked for again returns the job already there.
- `POST /api/projects/<p>/themes/<run>/name` → job: the AI names the themes (task `theme`, quotes checked).
- `GET /api/projects/<p>/themes/<run>/export.xlsx`.

#### An outline from the themes (roadmap C)

No AI is used anywhere here. An outline is stored in the project (`outlines`, `outline_sections`), keeps its titles
and notes when the set of themes it came from is deleted, and several per project are fine. A section is one of a
theme (its `parts`: `[{"theme": id, "docs": [doc ids] or null}]`, so a merge adds parts and a split takes them apart)
or one of your own (`kind: "own"`). Sections nest three levels deep (`max_depth`). Errors are 400 (in plain words),
404 for a missing outline, section, set of themes or draft.

- `GET /api/projects/<p>/outlines` → `{outlines: [{outline_id, title, run_id, sections, created_at, updated_at,
  run_exists, run_created_at}], runs: [{run_id, created_at, mode, k, themes_now, passages, stale}], framework}`
  (`framework`: the codebook chosen in Settings, the default for a new outline).
- `POST /api/projects/<p>/outlines {run_id?, title?, order?: similarity|size, framework?}` → `{outline_id}`. A section
  for each theme shown in the set (`run_id`: default the newest). `order` `similarity` (default) is the suggested path:
  the theme with most passages first, then always the most similar theme not used yet (half the cosine of the themes'
  passage counts per document, half the share of key-term words they have in common), improved by 2-opt; `size` lists
  the themes as the Themes page does. 409 when there is no set of themes yet.
- `POST /api/projects/<p>/outlines {question, hypotheses?: [text], meaning?, run_id?, title?, framework?}` →
  `{outline_id, placed, left_out, meaning}` (Margin 0.14): an outline from a research question. Each hypothesis (at
  most 12) becomes a section (`kind: "hypothesis"`, linked to the latest check with the same wording) holding the
  themes that bear on it most; a `Background` section holds the themes that bear on the question but on no
  hypothesis; the others stay out (`available_themes`). Without hypotheses the themes that bear on the question make
  the outline (400 when none does). A theme bears on a sentence through the passages its check counts for or against
  it (none for the question), the key terms the sentence shares (rarer words count more; a concept's other wordings
  count too), and, with `meaning: true` and an embedding model **on this computer** that built the project's vectors,
  closeness by meaning (a theme at least a standard deviation above the mean); `meaning` in the answer is null unless
  asked, else `{used, why}`. No AI.
- `GET /api/projects/<p>/outlines/<outline>?framework=&threshold=` → `{outline, run (null when its themes were
  deleted), sections, available_themes, own_suggestions, max_depth, framework_missing}`. `sections` is a tree
  (`children`); each has `section_id`, `number` ("2.1"), `depth`, `index`, `siblings`, `parent_id`, `kind`, `title`,
  `title_source` (`you`, `model` (the AI's theme name), `person` (your rename on the Themes page), `terms`, `own`,
  `gone`), `default_title`, `note`, `themes` (`[{theme_id, name, state: shown|removed|gone}]`), `state`, `passages`,
  `documents`, `terms`, `representatives` (the passages nearest the heart of the section, one per document first, with
  `location`, `similarity` and `apa`), `sources` (`[{doc_id, title, passages, apa, narrative}]`), `cite` (`{text, html,
  count, more, missing}`: one APA 7 in-text citation of the section's documents linked to the bibliography, or null),
  `codes` (`[{code, description, passages}]` of `framework`, null without one), `concepts` (`[{concept_id, term_id,
  label, wordings}]`), `disagreements` (checks already made in which documents of the section stand on both sides,
  `tier: "inside"`, or on one side against documents elsewhere, `"across"`: `{hyp_id, claim, status, status_text,
  supports, refutes}` with each side's documents, quote, place and citation), `decisions` (what you decided about
  claims of a draft that these documents touch), `gaps` (`kind` none, one-source, few, mostly-one, thin; `text`),
  `can_split`, `split_by_documents`, `link_to_next` (`{documents, terms}` it shares with the next section).
  `framework` overrides the outline's codebook for this answer. An outline from a question has `outline.question`;
  its hypothesis sections have `hypothesis` (`{text, hyp_id, checked, status, status_text, parts, evidence, sides:
  {supports, partly, refutes: [{doc_id, title, apa, quote, location}]}}`) and gaps `unchecked`, `no-themes`,
  `no-evidence`; its theme sections have `relevance` (`{to: hypothesis|question, evidence, terms, related, meaning,
  also: [{number, text}]}`); each of `available_themes` has `shares` (key terms shared with the question) and
  `bears_on` (numbers of the hypotheses it bears on).
- `PUT …/outlines/<outline> {title?, framework?, question?}` (`question`: only for an outline from a question; the
  sections stay); `DELETE …/outlines/<outline>`.
- `POST …/outlines/<outline>/hypotheses {text}` → `{section_id, themes}`: a hypothesis added to an outline from a
  question, before Background; it takes the themes that bear on it from Background and from the themes not in the
  outline, never from another hypothesis.
- `POST …/outlines/<outline>/sections {title?, note?, parent_id?, index?, theme_id?}` → `{section_id}`: a section of
  your own (`title` required), or with `theme_id` a theme of the set that the outline does not hold.
  `PUT …/sections/<section> {title?, note?}` (an empty `title` of a theme section is its theme's heading again);
  `DELETE …/sections/<section>` (the sections inside it move up).
- `POST …/sections/<section>/move {parent_id, index}`: reorder, nest and un-nest are all this (`parent_id` null: top
  level; `index` null: last). `POST …/sections/<section>/merge {into}`: the other section gains this one's themes,
  notes and inner sections. `POST …/sections/<section>/split {doc_ids?}` → `{sections: [new ids]}`: a section of
  several themes becomes one section per theme; a section of one theme is split by documents (`doc_ids` go to the new
  section; some, not all).
- `POST …/outlines/<outline>/order {}` → `{moved}`: the theme sections at the top level are put back in the suggested
  order; sections of your own and nested sections stay. In an outline from a question, the themes inside each top-level
  section are ordered too, and the hypotheses keep your order.
- `GET …/outlines/<outline>/draft/<draft>?meaning=1&threshold=` → the outline beside a draft: `{outline, draft:
  {draft_id, title, words, cited_documents, citations}, sections: {<section_id>: {level: none|little|partly|well,
  level_text, score, terms_used, terms_total, sources_used, sources_total, terms, used_sources, unused_sources,
  unused_terms, unused_points, where: {paragraph, excerpt, hits}}}, order, notes, meaning}`. A key term counts as
  used when the draft's words contain it (stop words kept, as the glossary keeps them); a source counts as used when
  one of the draft's own citations names a work of the bibliography whose document it is. `meaning` is null unless
  asked for; with `meaning=1` it is `{available: false, why}` unless search by meaning is set up with an embedding
  model **on this computer** that has built the project's vectors (the draft is never given to a model on another
  computer), else `{available: true, model, sections}` and each section gains `closeness` (0–1, the nearest draft
  paragraph to the mean of the section's passage vectors) and `closest: {paragraph, excerpt}`.
- `GET …/outlines/<outline>/export.docx` and `…/export.md` (downloads; `?token=` allowed; `?include=` a comma list of
  terms, sources, quotes, codes, concepts, disagreements, gaps, checks; default all; `?framework=`): headings numbered like
  the outline, your notes, key terms, the citation, quotes with their place, where the sources disagree and what you
  decided, gaps, and the sources named. The Word file is written without any library (Title and Heading 1–5 styles).

#### References (F5)

- `GET /api/projects/<p>/documents/<id>/references?start=&end=` → `{status, chains}`; with `start`/`end` (a
  selection) the chain it belongs to.
- `POST /api/projects/<p>/documents/<id>/references {name?}` → job: the AI follows references window by window
  (task `resolve`), or only around one name. Result: `{windows, read, failed, already_read, chains}`.
- Checks (prompt `check-v4`) give each judged excerpt `refers_to` (what a quote's "it" or "they" means) and flag
  `reference_missing` when a quote opens with a pronoun and nothing says what it refers to.

#### Highlighted copies (F7)

- `GET /api/projects/<p>/documents/<id>/annotated.pdf?hyp=h1,h2&layers=judgements,labels,concepts,references&framework=&concept=&threshold=`
  → the PDF with highlight annotations (exact boxes with pdfminer, lines otherwise, OCR for scanned pages) and a
  note listing quotes it could not place; an HTML copy for other documents. Header `X-Margin-Placed: placed/marks`.
- `GET /api/projects/<p>/hypotheses/<id>/annotated.zip?layers=&threshold=` → every document behind one answer.

#### Quick look and FlexiConc (F8)

- `POST /api/quicklook?name=<file>` (raw body) → `{project, job}`: a temporary project for one document, opened at
  once (Margin: the page then opens its skim report); `project.temporary = {created_at, expires_at, file, from}`. It goes to the trash after 7 days unless
  `POST /api/projects/<p>/keep`. Removing it (`DELETE /api/projects/<p>`) opens another project.
- (Margin 0.8: not linked from the page, kept for ENLENS's projects) `GET /api/projects/<p>/flexiconc.sqlite?framework=` → the project in the FlexiConc layout of the Cross-Doc SDG
  Explorer: `documents`, `sentences` (with a code label, confidence and consensus), `chains`, `clusters` and, when
  the project has an embedding model, `embeddings`.

#### Repeatable answers

- `POST /api/servers/repeatable` → `{model, repeatable, seed, digest, note}`: the same short question sent twice
  with the seed of the settings (`seed`, default 42) and temperature 0.

### The task queue, model routing and the Claude Code plugin (0.8)

With `settings.backend = "claude_code"` (it needs `allow_claude_code: true`, refused with `--local-only`) every job
that would call a model prepares tasks in the queue and waits for them: its Job has `"queue": true`, does not wait
for the model's turn, and its `progress` carries `queue`: `{"phase": "queue", "text": "Waiting for Claude Code: 3
passages to label", "waiting", "being_answered", "estimate", "paused", "paused_text", "command": "/margin-run P",
"privacy"}` (checks, batches: under `progress.model` with `phase: "queue"`). Cancelling such a job takes its tasks
that no session has taken yet out of the queue; a check by queue is removed whole.

- `GET /api/projects/<p>/queue` → `{"project", "kinds": [{"kind", "title", "waiting", "being_answered", "done",
  "failed", "stronger_model", "model", "step_up", "helper", "held", "estimate_seconds", "estimate", "run_total",
  "run_done"}], "groups": [{"kind", "model", "helper", "waiting"}], "order": [...], "held": [...], "waiting",
  "being_answered", "paused", "paused_text"?, "last_answer_at", "privacy", "command", "claim_minutes", "route",
  "setup": {...as GET /api/claude-setup}}`. Reading it also takes the next steps of checks by queue.
- `GET /api/projects/<p>/queue/preview?kind=&start=` → `{"kind", "title", "model", "helper", "system", "tasks":
  [{"task_id", "prompt", "documents": [{"doc_id", "title", "pages"}]}], "raw", "waiting", "being_answered", "start",
  "more"}`, or `{"kind", "note"}` when nothing waits: the next batch of `kind` (the first kind that waits when none)
  word for word as `next_tasks` would hand it to Claude Code, `raw` the connector's whole reply. Read only: nothing is
  claimed or written to the ledger. `start` skips that many tasks (the batch after). 400 for an unknown kind.
- `POST /api/projects/<p>/queue/order` `{"kind", "action": "first" | "hold" | "go" | "reset"}` → `{"order", "held"}`.
- `POST /api/projects/<p>/queue/withdraw` `{"kind"}` → `{"withdrawn", "checks_removed"}`.
- `POST /api/projects/<p>/queue/run` `{"kinds"?: [...]}` → job (kind `queue-run`): the AI model of Settings answers
  the queue here, kind by kind. With Claude Code in Settings (0.18.1) the local model answers here instead:
  `{"local": "mix"}` (default; job kind `queue-local-mix`) the AI mix's share, `{"local": "all"}` or (0.19.13)
  `{"local": "limit"}` (job kind `queue-local-limit`) every waiting task it may.
- `GET …/queue` `at_limit` (0.18.1, I4): null, or `{"said", "choice": "wait" | "local", "local_possible", "started",
  "offer_local"}` once Claude Code stopped at the plan's usage limit. 0.19.13: with `"local"` the local model no longer
  starts by itself: `offer_local` is true (until the person presses the Start, `{"local": "limit"}` above), and
  `started` says whether that job runs.
- `POST /api/projects/<p>/tasks/<task_id>/stronger` → job (kind `stronger`): "Ask a stronger model": the task (a
  round of a check: `rounds_info[].task_id`) is read once more by the model it steps up to; 400 when it already was,
  or when this route has no stronger model.
- `POST /api/projects/<p>/hypotheses/<h>/stronger` (0.11.2) → job (kind `stronger`, `scope` the hypothesis id):
  "Ask a stronger model" for a whole result: every search with `can_step_up` is read once more by the model checks
  step up to; the job's result is `{"hyp_id", "task_ids", "answered", "model"}`. 404 for an unknown hypothesis, 400
  when the route has no stronger model or every search was already read again. The result page uses this one.
- `GET /api/routing` → `{"route", "route_name", "rows": [{"row", "kinds", "title", "model", "step_up", "helper",
  "chosen", "recommended"}], "aliases", "fable", "local_small_model", "second_model", "step_up_below", "routing"}`.
- `GET /api/claude-setup` → `{"folder", "ready", "commands": ["claude plugin marketplace add …", "claude plugin
  install margin-run@margin"], "terminal": "margin claude-setup", "in_claude_code": [...], "local_only"}`;
  `POST /api/claude-setup` writes the plugin into the data folder and adds `"problems": []`.
- Settings (`PUT /api/settings`): `allow_claude_code`, `use_fable`, `task_models` (`{"claude": {"label": "sonnet"},
  "local": {"label": "llama3.2:3b"}}`), `local_small_model`, `routing` (default true).
- `GET /api/state` adds `queue: {"waiting"}` for the current project.
- Results: a hypothesis has status `waiting` while a check by queue is not finished; `GET …/hypotheses/<id>` adds
  `stronger_model`, `stronger_reason` (0.14.3: why `stronger_model` is null: `"model_per_task_off"` (the setting is off,
  or demo mode), `"top_model"` (Claude already runs checks on the strongest model of the plan), `"one_local_model"`,
  or `"none"`; null when there is one), `queue_command`, `queue`, and per part `rounds_info[]` `task_id`, `stepped_up`,
  `stronger_waiting`, `waiting`; an excerpt's `ai_history[].why` is `"stepped up"` for a stronger model's reading.
  0.11.2 adds, on the hypothesis and on each part, `status_first` (the answer from the first model's readings),
  `status_before_stronger` (the same when it differs from `status`, else null) and `stronger` (`{}` or
  `{"excerpts", "changed", "first_models", "models"}`: the excerpts a stronger model read again and how many it
  judged differently), and per round `can_step_up`. `status` is always the stronger model's reading.
- Themes carry `number` (1 to n in the order shown) and `merged_from_names`; `PUT …/concepts/links` accepts
  `decision: "undo"`.

### Subscription first, Claude Code set up and started from the app, the overview (0.9)

- A new installation's settings have `backend: "claude_code"` and `allow_claude_code: true`. With `--local-only` the
  default is `"auto"` (and `allow_claude_code` false).
- `GET /api/claude-setup[?refresh=1]` adds `"status"`: `{"found", "path", "version", "signed_in": true | false |
  null, "written", "installed": true | false | null, "plugin_version", "ready", "local_only"}` (from `claude
  --version`, `claude auth status` and `claude plugin list --json`; cached for 30 s, `refresh=1` reads again).
- 0.13.4: the status adds `"email"`, `"org_name"` and `"auth_method"`: the account Claude Code says it is signed in
  to (`email`, `orgName`, `authMethod` of `claude auth status`), `""` when it is not signed in or does not say; one
  line of text each, at most 200 characters. (`"plan"` and `"account"`, from 0.11, are its plan and the kind of
  terms.) Only the set-up status carries them (here, and in `POST /api/servers/test`'s `"claude"`): not
  `/api/state`, not the queue's `"claude"`.
- `POST /api/claude-setup` `{}` prepares the plugin and, when Claude Code is found, adds it to Claude Code →
  `{..., "steps": [{"step", "ok", "text"}], "status", "commands", "problems"}`; `{"write_only": true}` only writes
  the plugin (as 0.8); `{"check": true}` also starts the connector to check it.
- `POST /api/projects/<p>/queue/claude-code` → `{"running", "started_at", "seconds", "exit_code", "report",
  "stopped"}`: starts Claude Code headless for the project's queue (`claude -p "/margin-run:margin-run <p>"
  --tools Agent --restricted --plugin-dir <plugin folder> --allowedTools Agent
  mcp__plugin_margin-run_margin__{queue_status,next_tasks,submit_answers,release}`, with
  `ENABLE_CLAUDEAI_MCP_SERVERS=false`, in an empty folder; an older Claude Code without those options gets
  `--disallowedTools` with the file, shell and web tools instead), one run per project; adds the plugin first if
  needed. 400 when Settings do not name Claude Code, when Claude Code is not found,
  or with `--local-only`.
- `POST /api/projects/<p>/queue/claude-code/stop` → the same object: stops it, and gives the batches it had taken
  back to the queue at once.
- `GET /api/projects/<p>/queue` adds `"runner"` (as above, or `{"running": false}`), and on the Claude Code route
  `"can_start"` and `"claude": {"found", "signed_in", "installed", "ready"}`.
- `POST /api/servers/test` on the Claude Code route answers from the set-up status: `model_available` is whether it
  is ready, `claude` the status, `warning` when it is not signed in.
- `GET /api/projects/<p>/overview` → `{"documents", "passages", "profile": {"framework", "keyword", "labels",
  "documents"}, "concepts": {"terms", "concepts"}, "themes": {"runs", "themes", "latest"}, "references",
  "hypotheses", "waiting"}`: what each feature has made, for the Overview page. 0.16 adds `"notes"`, `"log"` (entries)
  and `"codebooks"` (those of your own: not the bundled ones).

### Set-up in one button, moving to another computer (0.10)

- `GET /api/claude-setup` adds `"installer"` (the line of Anthropic's Claude Code installer for this system:
  `curl -fsSL https://claude.ai/install.sh | bash`, or `irm https://claude.ai/install.ps1 | iex` on Windows) and
  `"docs"` (Anthropic's set-up page).
- `POST /api/claude-setup/claude-code` `{}` → job (kind `claude-install`): runs that installer (the page shows the
  command and asks first). `result`: `{"ok", "text", "status"}`; the job ends in `error` when Claude Code could not
  be installed. 409 when Claude Code is already found; 403 with `--local-only`.
- `POST /api/claude-setup/sign-in` `{}` → `{"opened", "window", "command", "folder"}`: opens a terminal window
  (Terminal on macOS, PowerShell on Windows, the first terminal found on Linux) already running `claude`, for the
  one-time sign-in, in the empty `folder` (`<data folder>/claude-runs/sign-in`) and without the file, shell and web
  tools; `opened: false` when no window could be opened (the page then shows `command`, the line to type, which goes
  to that folder first). The page
  then reads `GET /api/claude-setup?refresh=1` every few seconds until `status.signed_in` is true, and adds the
  plugin. 400 when Claude Code is not found, or with `--local-only`.
- On start, the app writes the Claude Code plugin again (and runs the two set-up commands again, quietly) when the
  plugin names another Python or another data folder than this Margin (it moved, or was installed again).
- `GET /api/move.zip` (a download; the token may be given as `?token=`) → one zip with every project (each as the
  zip of `GET /api/projects/<p>/export.zip`, under `projects/NNN.zip`) and `enlens-move.json`: `{"format":
  "enlens-move", "version", "made", "projects": [{"name", "file", "documents", "linked", "missing"}], "current",
  "settings"}`. Quick looks not kept are left out, and so is a saved Claude API key.
- `POST /api/projects/import` with that zip asks first, in two steps. Step one imports nothing: it answers `{"move":
  peek, "token"}`, where `peek` is `{"made", "version", "projects": [{"name", "documents"}], "settings": {key: value
  shown}, "servers": [{"key", "url", "here": bool}] (addresses of servers; `here`: on this computer), "fresh": bool
  (this computer has no project)}`; the upload waits under `token`. Step two, `POST /api/move {"token", "settings":
  bool, "servers": [keys]}` → `{"moved": {"projects": [{"from", "name", "documents"}], "settings": bool, "current",
  "made", "version"}, "project": summary of the current one}`. `settings` takes the other computer's settings, only when
  this computer has no project yet; an address that is not on this computer is taken only when its key is in `servers`,
  else that back end goes back to its default; the installation id never comes. A project whose name is taken comes in
  as `name (2)`. With `--local-only`, never the choice of a cloud AI. An unknown or used `token` → 410.
- `GET /api/state` adds `"installation": {"kind": "git" | "script" | "package" | "pip", "system": "mac" | "windows"
  | "linux", "line", "releases"}`, and `ocr` adds `"install"` when Tesseract is missing: `{"text", "command", "link",
  "link_text"}` for this system.

### Check a draft (Margin 0.1)

A draft is the researcher's own writing, kept apart from the documents (never searched as evidence). Its claims are
the statements that need a source; each one kept is checked as a hypothesis of its own (`draft_id` on the hypothesis,
in the set `batch_id` of the draft), so the result page, reviews, exports and the map work as for any check.

- `GET /api/projects/<p>/drafts` → `{"drafts": [{"draft_id", "title", "file_name", "created_at", "found_at", "chars",
  "ai_access", "own_setting", "claims", "kept", "checked", "cite_text_id", "citations"}], "default", "labels",
  "local_only"}`. `cite_text_id`: the text of *Checking citations* made from the draft (null when it cites nothing
  Margin can read); `citations`: its cited works not left out.
- `POST /api/projects/<p>/drafts` `{"text", "title"?, "ai_access"?: "cloud" | "local" | "none"}` → `{"draft": summary}`
  (40 to 300,000 characters; no `ai_access`: the project's default).
- `POST /api/projects/<p>/drafts/upload?name=chapter.docx&ai_access=…&title=…` with the raw file as the body (Word,
  PDF, text, Markdown, HTML; at most 50 MB) → `{"draft": summary}`.
- `GET /api/projects/<p>/drafts/<d>` → `{"draft": {…, "ai_access", "ai_label", "batch_id", "found_by": "ai" | "rules",
  "found_at", "words"}, "text", "claims": [{"claim_id", "start", "end" (offsets in "text"), "quote", "claim", "kind",
  "kind_text", "why", "cited", "source": "ai" | "rules" | "person", "skip", "edited", "decision": "supported" |
  "refuted" | "dismissed" | null, "decided_at", "hyp_id", "status",
  "status_text", "evidence": {"supports" | "partly" | "refutes": [{"doc_id", "title", "excerpts", "locations",
  "quote", "location", "passage_id", "apa"}]}, "cite": {side: {"text", "html", "count", "missing"}}, "to_review",
  "waiting_for_you"}], "bibliography": bool, "counts": {"claims", "kept", "checked",
  "to_check", "cited", "status": {status: n}, "decided": {decision: n}}, "finding": {"total", "waiting", "done", "failed", "queued",
  "errors"?}, "sent": {"times", "routes", "parts_read", "claims_read", "first", "last"}, "documents",
  "queue_command", "default", "labels", "local_only", "citations"}`.
  Margin, with ENLENS 0.13.7: `citations` (null when the draft cites nothing Margin can read) is `{"text_id",
  "citations", "works", "ready", "accurate", "checking", "notices", "blocked", "has_bibliography", "numeric_unread",
  "counts": {group: n}, "refs": [{"ref_id", "cite_id", "start", "end" (the citation's place in "text"), "raw",
  "marker", "claim", "group" (the answer's group, or what it needs: "ready", "no_document", …), "state", "text",
  "help", "status", "hyp_id", "work", "quote", "ignored", "claim_id"}]}`, and each claim has `citations`: the refs
  of the citations it stands for (inside it, right after it, or before it in the same sentence). `cited` is also
  true for a claim with a citation found. Its citations are checked with `POST
  /api/projects/<p>/citations/<text_id>/check` (job `citations`, `scope` the text). The text is found (no AI) when
  the draft is added; a draft from before gets it when its page or `GET /api/projects/<p>/citations` is opened.
  Margin 0.5: `apa` is the APA 7 in-text citation of a document linked to a work of the bibliography
  (`null` otherwise): `{"text": "(Verhoeven & Okafor, 2025)", "narrative": "Verhoeven and Okafor (2025)", "html",
  "narrative_html"` (a title in `<i>` for a book or report without an author)`, "kind": "names" | "quoted" | "italic",
  "who", "who_html", "year", "sort"}`, made as the bibliography's reference list would make it (2025a and 2025b, as
  many names as tell two "et al." apart). `cite` puts the documents of each side with a citation in one parenthesis,
  ordered by author ("(Haugen, 2023, 2024; Verhoeven & Okafor, 2025)"); `missing` counts that side's documents
  without one. `bibliography`: the project has one.
- `PUT /api/projects/<p>/drafts/<d>` `{"title"?, "ai_access"?}` (`""`: the project's default) → `{"draft"}`. A changed
  setting applies at once to the tasks not answered yet that hold the draft's text.
- `DELETE /api/projects/<p>/drafts/<d>` → `{"deleted", "claims", "checks"}`: the draft, its claims and their checks,
  and its citations' text with their checks.
- `POST /api/projects/<p>/drafts/<d>/find` `{}` → job `draft-find` (`scope`: the draft). By queue (Claude Code) its
  tasks (kind `claims`, one per part of a few paragraphs) wait in the queue; a draft Claude may not read is read by the
  local model for restricted documents, or by rules when there is none (or when it is *No AI*). Progress `{"message",
  "done", "total", "queue"?}`; result `{"draft_id", "by", "found", "failed", "note"}`. Claims nobody touched are found
  anew; checked, reworded, decided, dismissed and marked ones stay.
- `POST /api/projects/<p>/drafts/<d>/check` `{"claim_ids"?, "k"?, "per_doc"?, "expand"?, "semantic"?}` → job
  `draft-check` (progress as a batch of checks). No splitting into parts; no AI search words for a draft the model
  may not read. 400 when nothing waits to be checked or the project has no documents. Without `claim_ids`, the
  claims the person decided on (Margin 0.3) wait out; with them, they are checked too.
- `POST /api/projects/<p>/drafts/<d>/claims` `{"start", "end", "claim"?}` → `{"claim_id"}`: a claim the person marks.
- `PUT /api/projects/<p>/drafts/<d>/claims/<c>` `{"claim"?, "skip"?, "decision"?}` → `{"claim_id", "claim", "skip",
  "decision"}`: reword (before it is checked), drop / keep, or (Margin 0.3) the person's decision: `"supported"`,
  `"refuted"`, `"dismissed"` (the same as `skip: true`), or `null` to take it back (a dismissed claim is kept again).
  400 for another value. A decision belongs to the draft: the answer of the claim's check does not change.
- `DELETE /api/projects/<p>/drafts/<d>/claims/<c>`: the claim and its check.
- `GET /api/projects/<p>/drafts/<d>/export.xlsx|csv`: one row per claim (sentence, claim checked, kind, cited, found
  by, answer, the person's decision, supporting, partly supporting and contradicting documents with their places, and
  *Citation (APA 7)*: the contradicting documents' citation for a claim decided *refuted*, else the supporting ones'); the Excel file ends with
  *How these results were made*.
- `GET /api/projects/<p>/hypotheses/<h>` and the Results list carry `draft_id`; `GET /api/projects/<p>/overview`
  carries `drafts`.
- `GET /api/projects/<p>/drafts/<d>/consistency?threshold=` → the draft read against itself, without AI
  (`consistency.py`): `{"draft_id", "notices": [{"key", "kind", "group", "text", "places": [{"start", "end" (offsets
  in the draft's text), "quote", "claim_id" (the claim the place is, or null)}], "dismissed"}], "groups": {group:
  heading}, "counts": {group: notices not set aside}, "open", "dismissed", "read": {"sentences", "claims",
  "checked"}}`. Groups and kinds: `contradiction` (`opposite`: two sentences about the same thing going opposite ways
  or one saying "not"; `numbers`: the same statement with two numbers; `same_passage`: one passage counted for one
  claim and against another; `answers_differ`: two nearly identical claims with opposite answers or decisions),
  `inconsistency` (`abbrev_late`, `abbrev_twice`, `spelling`), `unclear` (`pronoun`: "This …" and a verb;
  `strength`: hedged and absolute at once; `overloaded`: several claims in one long sentence; read for the claims kept
  and the sentences rules would pick). The reference list is not read. At most 40 notices of a kind (25 of an
  `unclear` kind). 404 for a missing draft.
- `PUT /api/projects/<p>/drafts/<d>/notices/<key>` `{"dismissed": true | false}` → `{"key", "dismissed"}`: set a
  notice aside ("not a problem") or bring it back. `key` names the notice by its kind and the words of its places, so
  it stays aside while those words are the same. 400 for a key that is not one.

### ENLENS's projects (Margin 0.1)

- `GET /api/state` carries `"enlens": null | {"path", "projects": [names not in Margin yet], "linked": [...], "here"}`
  (ENLENS's data folder: `ENLENS_HOME`, or `~/enlens` unless `MARGIN_HOME` is set).
- `POST /api/import-enlens` `{"names"?: [...]}` → `{"from", "copied", "linked", "codebooks", "settings": bool}`: copies
  those projects (all by default), ENLENS's codebooks, and its settings when Margin has no project yet. ENLENS's own
  folder is not changed.

### Codex and Antigravity on the queue (providers stage 2)

Two more agents answer the queue on the person's own plan, as Claude Code does: **Codex** (OpenAI, program `codex`, a
ChatGPT plan) and **Antigravity** (Google, program `agy`, a personal Google account). Both are built against stand-in
programs that follow their documentation and not yet tried with a real account.

- **Settings.** `backend` may be `"codex"` or `"antigravity"`, refused (400) until the person has said yes:
  `allow_codex` and `allow_antigravity` (both false by default; the Settings dialog names the company first), and
  refused with `--local-only` like every cloud route. `cli_models` is `{"codex": {"small", "middle", "strong"},
  "antigravity": {...}}`: the model of a tier the person chose, empty or absent meaning the recommendation. `claude_speed`
  (helpers at once) and `claude_thought` (how much thought) apply to both, as to every route that answers by the ladder
  (`claude_code`, `codex`, `antigravity`, `cloud_api`).
- `GET /api/agent-setup?route=codex|antigravity|claude_code[&refresh=1]` → `{"route", "title", "company", "program",
  "plan", "docs", "installer": {"line", "docs"}, "status": {"found", "path", "version", "signed_in": true | false |
  null, "account", "connector", "ready", "models_available", "problem"}, "recommended": {"small", "middle",
  "strong"}, "lineup_in_use", "manual": [lines to type], "local_only", "adds": [what *Add Margin* adds], "sign_in_docs",
  "measured"}`. `connector` is whether Margin is added to the agent; `models_available` is what the plan offers
  (Antigravity's `agy models`; empty for Codex); `recommended` is the line-up resolved against it (`providers.LINEUP`
  and `AGENT_CLIS`); `lineup_in_use` the same after `cli_models`; `measured` is false: neither agent is measured with
  Margin yet. For `claude_code` it wraps `GET /api/claude-setup` (its `recommended` and `lineup_in_use` are the aliases
  *haiku*, *sonnet*, *opus*). Cached for 30 s; `refresh=1` reads again. Only probes that start no model are run. 400
  for another route.
- `POST /api/agent-setup/install` `{"route"}` → `{"job": {...}}` (kind `agent-install`): runs the maker's own installer
  after the person confirmed the line shown (`MARGIN_CODEX_INSTALLER` and `MARGIN_AGY_INSTALLER` replace it in tests).
  409 when the program is found; 403 with `--local-only`; the job ends in `error` when it could not be installed.
- `POST /api/agent-setup/sign-in` `{"route"}` → `{"opened", "window", "command"}`. Codex: `codex login` starts in the
  background and opens the browser itself (`window` is `""`). Antigravity: a terminal window running `agy` in an empty
  folder of Margin, for its first sign-in, as Claude Code's. `opened: false` gives the `command` to type. The page then
  reads `GET /api/agent-setup?refresh=1` until `status.signed_in` is true.
- `POST /api/agent-setup` `{"route"}` → `{"steps": [{"step", "ok", "text"}], "status"}`: adds Margin to the agent.
  Codex gets the Margin connector (`codex mcp add margin …`), the skill `$margin-run` and the helpers as Codex
  subagents; Antigravity gets the plugin `margin-run` (`agy plugin install`, so the person can type `/margin-run`), and
  Margin's own Antigravity home is prepared (`<data folder>/agy-home`, below). Nothing else of the person's is changed.
  Margin writes them again when its version, Python or data folder changed. For Antigravity the answer of
  `GET /api/agent-setup` adds `own_leftovers` (what Margin 0.20.0–0.20.1 wrote into the person's own
  `~/.gemini/antigravity-cli/settings.json`: the line `mcp(margin/*)` and its work folders as trusted workspaces) and
  `own_settings` (that file).
- `POST /api/agent-setup/tidy` `{"route": "antigravity"}` → `{"removed": [...], "own_leftovers": []}`: takes those lines
  out of the person's own settings, keeping every other key, after a copy of the file is kept as `settings.json.margin-tidy.bak` (its permissions kept).
  400 for another route, or when the file is not JSON (left as it is).
- `POST /api/projects/<p>/queue/agent` and `POST /api/projects/<p>/queue/agent/stop`: the same handler and answer as
  `queue/claude-code` (above, which stays), for the main route, whichever agent it is. Neither agent's headless mode is
  documented to run skills or helpers, so Margin does what `/margin-run` does: it starts one process of the agent per
  helper, each on its group's model in the maker's own name and with the effort of the chosen thought, and asks the
  queue again until nothing is left to start or Stop is pressed. 409 (400 on the old path) when the main route is
  none of the three agents; 400 when the agent is not found, not signed in, or when its help does not list a switch
  that closes it in (Antigravity: `-p` and `--sandbox`; the answer names it). A reached plan limit
  ends the run with the same `limit` report as Claude Code's. A tool Antigravity refused a helper (`denied_actions`)
  is written in the run's report and listed in its state as `refused`: `[{"helper", "tools", "at"}]`. Run records are
  `<data folder>/claude-runs/<route>-<project>-<hash>.run.json`, so Stop, *Quit* and a restart find a run that kept
  working.
- **Closed in.** Codex starts in an empty folder with the person's own Codex settings left out, read-only, without its
  command, web search and image tools, and with only the connector's three queue tools (`next_tasks`,
  `submit_answers`, `release`). Antigravity's own tools cannot be switched off from outside: it starts in Margin's
  empty work folder, in its sandbox, without slash commands, asking before every tool except `mcp(margin/*)`, and with
  a home folder of its own (`HOME` and `USERPROFILE` set to `<data folder>/agy-home`, the `XDG_*` folders left out).
  Margin writes the settings there before every run: the allow rule `mcp(margin/*)` alone, its work folder as the only
  trusted one, no key that approves tools, adds a connector or hook, or spends AI credits (`toolPermission`,
  `useG1Credits`, `useAiCredits` and the like); an "off" of the person's own telemetry and usage-statistics keys is
  carried over, never an "on". The person's `GEMINI_*`, `GOOGLE_*` and `CLOUDSDK_*` variables are left out, so no key
  of theirs is billed. On macOS `Library/Keychains` there links to the person's,
  where the sign-in is kept.
- `GET /api/state` (and the answer of `PUT /api/settings`) gains `"agent"`: `{"route", "title", "start": "Start Codex",
  "company", "provider", "card"}` when the main route is Claude Code, Codex or Antigravity (else null), and
  `"clis"`: `[{"id", "title", "provider", "company", "program", "plan", "docs", "measured", "recommended"}]` for
  Codex and Antigravity. `GET /api/projects/<p>/queue` adds `"agent"` (true when an agent answers the queue) and
  `"agent_title"`; its `"route"` stays the backend's name.
- **The queue's reader.** The queue hands a task out only when every document it names allows the company of the agent
  that takes it (`access.record_sent` records that provider and the agent's name): a document that allows OpenAI but
  not Anthropic reaches Codex and never Claude Code, and the reverse. The connector (`mcp_server.py`) answers for the
  agent that started it: the environment variable `MARGIN_ROUTE` (`codex` or `antigravity`, set by the set-up) names
  it, and without it the connector is Claude Code's, as before. `MARGIN_CODEX` and `MARGIN_AGY` name the programs, as
  `MARGIN_CLAUDE` names `claude`.

### How fast Claude Code works, and which helpers it starts (0.13.10)

- Settings (`PUT /api/settings`): `claude_speed`: `"slower"` | `"normal"` (default) | `"faster"`, one, two or four
  helpers at once when the app starts Claude Code (400 for anything else).
- `GET /api/projects/<p>/queue` adds `"speed": {"chosen", "options": {"slower": 1, "normal": 2, "faster": 4},
  "max_parallel": 8, "max_per_helper": 4, "helpers": [{"helper", "name", "models", "kinds", "waiting", "batches"}],
  "all_helpers": [...]}` (`helpers`: the helpers with work waiting, with the titles of the kinds they would answer;
  `batches`: how many batches that is, the most helpers that can work on it at once). Each of `"groups"` adds
  `"start"`: how many helpers a run at the chosen speed starts for it now, and the estimates count with that speed.
- `POST /api/projects/<p>/queue/claude-code` takes `{"parallel"?: 1 to 8, "helpers"?: {"margin-checker": 2,
  "margin-labeller": 1}}` (`"checker"` works too; 0 to 4 each, at least one above 0) for that run; with neither, the
  speed of Settings. The command gets `--parallel N` and, with helpers, `--helpers checker=2,labeller=1` (the ones
  given 0 left out: they do nothing in that run). With helpers, `parallel` is at most what they add up to (their sum,
  at most 8, when not given). Whole numbers only (2.0 is 2; 2.5 is refused). 400 for a bad plan. The run's object
  adds `"parallel"` (the helpers it can have at once) and `"helpers"` (`{"checker": 2, …}` or null).
- The connector's `queue_status` takes `kind`, `parallel` and `helpers` (`"checker=2,labeller=1"`), as `/margin-run`
  was given them; without `parallel` it uses the speed of Settings. Its `groups` carry `start` (one per group in the
  queue's order, then more for the groups with more batches; with `helpers`, each helper at most as many as named),
  only for the kind asked and the helpers named; the answer adds `"parallel"` and, with `helpers`, `"helpers"` and
  `"not_this_run"` (the groups of the helpers left out). `/margin-run` starts what `start` says, and asks again only
  when all its helpers have reported back (`taskqueue.run_status`, `run_plan`, `plan_helpers`).

### Models that suit the Claude plan (0.13.10)

- Settings: `claude_plan` (`"auto"`, the default: follow the plan Claude Code names; or `"free"` | `"pro"` | `"max"`)
  and `claude_plan_detected` (`""` | `"free"` | `"pro"` | `"max"`: the tier of `subscriptionType` from `claude auth
  status`, written in the background by `claude_setup.status()` when Claude Code is signed in and the tier changed,
  and once when the app starts; Team and Enterprise are `"max"`). Not carried by *Move Margin to another computer*.
- `GET /api/routing` adds `"plan": {"tier", "chosen", "detected", "titles"}` (`tier`: the one the recommendations
  follow, `""` when not known: as Pro). Each row's `"recommended"` is now the model itself (the auditor named: opus,
  fable, or sonnet on Free), with `"recommended_role": "auditor"` where it is the auditor's.
- In `routing`: `TIERS`, `plan_tier(plan)`, `tier_defaults(kind, tier)`, `settings_tier(settings)`, `Router.tier`.
  A kind registered by an add-on can say `bulk=True` (many tasks at a time: keeps its models on Max).

### The bibliography: Zotero, or an exported file (0.13)

A project can hold one bibliography: the works of a Zotero library or collection, read from the Zotero app on this
computer through its local API (Zotero 7 or later, `http://127.0.0.1:23119/api/`, switched on in Zotero under
*Settings → Advanced → Allow other applications on this computer to communicate with Zotero*), or of a file exported
from a reference manager (BibTeX, RIS, CSL JSON, Zotero's CSV). Nothing goes over the internet; Zotero is only read.

- `GET /api/zotero` → `{"state": "ready" | "not_running" | "api_off" | "too_old" | "failed", "url", "libraries":
  [{"id": "user" | "group-<id>", "name"}], "detail"}` (`libraries` when ready).
- `GET /api/zotero/collections?library=user` → `{"collections": [{"key", "name", "parent", "items", "depth"}]}` in
  tree order (`items`: the works directly in it). 409 with `kind` `zotero_<state>` when Zotero cannot be read.
- `GET /api/zotero/works?library=user&collection=<key>&q=<words>&limit=100` (0.13.9) → `{"works": [{"key", "title",
  "cite", "type"}], "more"}`: the top-level works of a library, or of one collection (not its subcollections), by title,
  without notes; `q` is Zotero's quick search (title, creators, year); `more` when there are more than `limit` (at most
  200). 409 as above.
- `POST /api/projects/<p>/bibliography` → job (kind `bibliography`), one of:
  `{"zotero": {"library": "user", "collection": "<key>" | null, "subcollections": true}}` (null: the whole library),
  `{"zotero": {"library": "user", "items": ["<key>", …]}}` (0.13.9: only these works, 1 to 500 of them),
  `{"file": {"name": "refs.bib", "text": "…"}}`, or `{"update": true}` (the same Zotero library and collection, or the
  same chosen works, again).
  It replaces the bibliography; a person's decisions are kept for every work that is in the new one too (by its key,
  else its DOI, else its title and year). `progress`: `{"phase": "works" | "attachments" | "files" | "checksums" |
  "matching", "done", "total"}`. `result`: the counts below. 400 for a file that is not a bibliography, a file without
  works, `update` of a bibliography read from a file, or `items` that are not 1 to 500 Zotero keys. Chosen works
  that Zotero no longer has are left out (and out of the next update); none left is an error of the job.
- `GET /api/projects/<p>/bibliography` → `{"bibliography": null}` before one is brought in; else
  `{"bibliography": {"kind": "zotero" | "file", "library", "library_name", "collection", "collection_name",
  "subcollections", "items" (0.13.9: the chosen works' Zotero keys), "name", "format", "format_text", "pulled_at",
  "works"}, "counts": {"works", "linked", "confirm",
  "to_find", "not_in", "files"}, "linked": [Pair], "confirm": [Pair], "to_find": [Work], "not_in": [Document],
  "ai_access": project info}`. A Work: `{"key", "title", "cite": "Verhoeven and Okafor (2025)", "authors", "year",
  "type", "container", "doi", "url", "link": "zotero://select/…" | null, "file": name of a file Zotero keeps | null}`.
  A Pair: `{"work", "doc": {"doc_id", "title", "file", "kind", "pages", "added_at", "file_title"}, "status": "auto" |
  "confirmed" | "probable", "method": "file" | "doi" | "title" | "person", "score"}`; a probable one adds
  `"evidence": {"title": "whole" | "main" | "words", "author", "year", "excerpt", "start", "end", "page"}` (the
  title's place on the document, `start`/`end` within `excerpt`).
- How a work and a document are linked: by themselves when a file the work has and the document are the same file
  (the same checksum) or they have the same DOI (`auto`); proposed (`probable`) when the work's title stands on the
  document's first pages with an author or the year (a title of one or two words needs both); a document or work
  already linked gets no proposal, and a pair a person rejected is never proposed again. Adding documents matches
  them again: the ingest job's `result` adds `"bibliography": {"linked", "confirm"}` for the new documents.
- A linked document (`auto` or `confirmed`) takes its work's title (0.13.3): its `title` everywhere (the documents,
  search, a check's excerpts and exports) is the work's, and `file_title` (in a Pair's `doc` and in
  `GET …/documents/<doc_id>`) is the title read from the file, `null` when the two are the same or the document is not
  linked. When no work is linked any more (`different`, another bibliography, `DELETE`), the file's own title comes
  back. A document linked to several works takes the first one's (the bibliography's order). The matching always reads
  the file's own title.
- `PUT /api/projects/<p>/bibliography/links` `{"item_key", "doc_id", "decision": "same" | "different" | "clear"}` →
  the view above. `same` confirms a proposal or links by hand; `different` rejects a proposal or undoes a link;
  `clear` forgets the person's word.
- `POST /api/projects/<p>/bibliography/confirm-all` `{}` → `{"confirmed": n, …the view}`.
- `POST /api/projects/<p>/bibliography/files` `{"ai_access": "cloud" | "local" | "none", "item_keys": [...]?}` → an
  ingest job (title "Adding Zotero's files") of the files the bibliography has for works without a document, read
  where they are. 400 when there is none.
- `GET /api/projects/<p>/bibliography/to-find.xlsx` and `.csv` (downloads; `?token=` allowed): the works without a
  document: Title, Authors, Year, Type, Published in, DOI, DOI link, Web address, Open in Zotero, File in Zotero.
- `DELETE /api/projects/<p>/bibliography` `{}` → `{"removed": n, …the view}`: the works and links go; documents and
  Zotero are not touched.
- `GET /api/projects/<p>/documents` adds `"bib"` per document (`{"cite", "title", "doi", "link", "url", "type",
  "container"}` of its linked work, or null); `GET /api/projects/<p>/documents/<id>` adds the same `"bib"`.

### Checking citations (0.13.7)

A text (the person's draft, pasted or read from a file, or a document of the project) is read for its citations:
author-year ones in brackets and in the sentence, and numbered ones (`[3]`, `[2–4]`) when the text ends with its
numbered reference list. Each gets the claim in front of it (`claim`, and `claim_at`, where it stands in `sentence`)
and the sentences before it (`before`). Each cited work is looked up in the bibliography; a work whose document is in
the project gets a check of its own (a hypothesis with `origin` `"citation"` and the reference's id as `origin_id`),
against that document only, with the claim's sentences in its payload as `claim_context` (shown to the AI as context,
never as evidence; the prompt version stays `check-v4`) and `citing` (`{"text_id", "ref_id"}`). Checks of citations
are left out of `GET /api/projects/<p>/hypotheses`, the evidence map, the Results downloads and the Overview's
`hypotheses`; `GET /api/projects/<p>/hypotheses/<id>` opens them as any other (`options.citation` holds the sentence
and the work). Finding citations uses no AI.

Margin: a text pasted or read from a file is kept as a draft (*Check a draft*) whose citations it is. The view has
`draft` (`{"draft_id", "title"}` or null) and each summary of `GET …/citations` has `draft_id`; `PUT` on a draft's
text renames the draft or changes its AI setting (both stay in step); `DELETE` on it is refused (409: the draft is
removed on its page, with its citations). A pasted text without citations is not kept (400, which names Check a
draft). Every draft's citations are listed (found when the list is asked for, for drafts from before).

- `GET /api/projects/<p>/citations` → `{"texts": [text summary, newest first], "has_bibliography": bool,
  "ai_access": {...the project's AI settings}}`. A summary: the view's `text` with `citations`, `works`, `counts`,
  `notices`, `ready`, `accurate`, `checking`.
- `POST /api/projects/<p>/citations` → the view of the new text. One of `{"text", "title"?, "ai_access"?}` (pasted),
  `{"upload": {"batch", "name"}, "title"?, "ai_access"?}` (a file sent to `POST /api/projects/<p>/uploads` first: read
  as documents are read, then deleted; it never becomes a document) or `{"doc_id", "title"?}` (a document of the
  project, which keeps its own AI setting). `ai_access` (`cloud`, `local`, `none`; the project's default when left
  out) says who may read the draft's claims with AI. 400 for a text without citations or an unknown setting; 404 for
  an unknown document.
- `GET /api/projects/<p>/citations/<text>` → the view: `{"text": {"text_id", "title", "source": "paste" | "file" |
  "document", "source_text", "doc_id", "file_name", "ai_access", "level" (the setting that applies now; local-only
  turns cloud into local), "created_at", "numeric_unread" (numbered citations without a reference list), "cut"},
  "refs": [...], "counts": {group: n}, "notices", "citations", "works", "ready", "accurate", "checking",
  "has_bibliography", "bibliography_works": [{"key", "cite", "title"}]}`. A ref (one cited work of one citation):
  `{"ref_id", "cite_id", "n", "raw", "marker", "kind": "paren" | "narrative" | "numeric", "page" (of the text),
  "sentence", "claim", "claim_at": [start, end] | null, "before", "state", "state_text", "work": {...the bibliography
  view of the work} | null, "how": "auto" | "ambiguous" | "none" | "person", "candidates": [work], "documents":
  [{"doc_id", "title"}], "proposed" (documents waiting for confirmation), "hyp_id", "status" (the check's),
  "verdict": "accurate" | "partly" | "contradicted" | "mixed" | "not_found" | "unsure" | "failed" | "checking" | null,
  "verdict_text", "verdict_help", "quote": {"verdict", "quote", "page", "doc_id", "title"} | null, "reviewed",
  "corrected"}`. `state`: `ready` (a work with its document, not checked), `checked`, `no_work` (not in the
  bibliography; `candidates` are the same author's other years), `ambiguous` (several works match), `no_document`,
  `to_confirm` (its document waits on the Bibliography page), `same_document`, `ignored`, `contrast` (cited for
  another view: "but see", "contra"; left out until put back). References not checked and not decided by a person are
  matched again on every read, so a work or document added later is used.
- `PUT /api/projects/<p>/citations/<text>` `{"title"?, "ai_access"?}` → the view. A document's text keeps the
  document's setting (400). Tasks not answered yet take the new setting at once.
- `DELETE /api/projects/<p>/citations/<text>` `{}` → `{"deleted": id}`: the text, its citations and their checks.
- `POST /api/projects/<p>/citations/<text>/check` `{"ref_ids"?: [...], "again"?: bool}` → job (kind `citations`,
  `scope` the text's id; by queue when Claude Code is the AI): every ready reference (or those of `ref_ids`; with
  `again`, checked ones are checked anew), one check each, as *Check several* does. `result`: `{"text_id",
  "checked": [hyp_id], "errors", "stopped", "total"}`. 400 when none is ready. Search words are asked of the AI
  only when the text's claims may go to the model that proposes them; the excerpts are split by the most restricted
  of their document's setting and the text's (`access.text_floor`).
- `PUT /api/projects/<p>/citations/<text>/refs/<ref>` `{"item_key": key | null}` (the work it is; null: back to the
  matching; a check against another work is removed) or `{"ignored": bool}` (not a citation) → the view.
- `GET /api/projects/<p>/citations/<text>/export.xlsx` (a download; `?token=` allowed): one row per cited work: #,
  Page of your text, Sentence, Claim checked, Citation, Work, Title, Answer, Quote from the source, Page in the
  source, Document.
- `GET /api/projects/<p>/overview` adds `"citations": {"texts", "refs", "checked"}`; its `hypotheses` leaves the
  checks of citations out.

### Finding literature (Margin)

Online lookups that are not AI: OpenAlex (the main source), Crossref, Semantic Scholar and Unpaywall. The services'
addresses can be changed with `MARGIN_OPENALEX_URL`, `MARGIN_CROSSREF_URL`, `MARGIN_S2_URL` and
`MARGIN_UNPAYWALL_URL` (the tests and `tools/dev_server.py --literature` use stand-ins). Requests carry the agent
`Margin/<version>`. The setting `contact_email` (empty until the person gives one; never filled in by Margin) is sent
as `mailto` to OpenAlex and Crossref and as `email` to Unpaywall, which refuses a lookup without one. Every answer is
kept in the project (tables `lit_cache`, `lit_searches`, `lit_found`, made when first needed), so the same lookup is not
repeated; `"fresh": true` asks again.

**What may go out.** Nothing, when cloud models are off for good (`--local-only`): every endpoint that would send
answers `403` with `kind` `local_only`. A search made from a draft (`draft_id`) goes out only when the draft's AI setting
is *Claude may read it*, else `403` `not_allowed`. Following citations sends only the DOIs of documents whose setting
allows it. Errors that come from a service: `kind` `offline` (502), `rate_limited` (502, the message says how long to
wait), `refused` (502), `failed` (502), `no_email` (409, for Unpaywall); `bad_request` is 400. A work is
`{"key", "source", "title", "authors", "year", "venue", "doi", "url", "abstract", "cited_by", "type", "openalex_id",
"open": {"url", "pdf_url", "license", "status", "found_by"} | null, "volume", "issue", "pages", "have": {"where":
"documents" | "bibliography", "title"} | null, "closeness"}`.

- `GET /api/projects/<p>/literature` → `{"local_only", "email", "sources": [{"id", "name", "site"}], "embedding" (the
  local embedding model used to rank, or null), "drafts": [{"draft_id", "title", "ai_access", "ai_label", "claims"}],
  "searches": [saved search], "documents": {"total", "usable", "not_allowed", "no_doi"}, "zotero_url"}`. Sends nothing.
- `GET /api/projects/<p>/literature/draft/<d>` → `{"draft", "claims": [{"claim_id", "n", "claim", "status",
  "status_text", "cited", "words", "terms"}], "searchable", "why_not"}`: the claims no document supports (status
  `unsupported`, `no_passages` or `uncertain`) with search words made on this computer. Sends nothing.
- `POST /api/projects/<p>/literature/words` `{"text"}` → `{"words", "terms"}`: search words from a sentence or a
  research question (the corpus's key terms it contains, then its other content words; no model). Sends nothing.
- `POST /api/projects/<p>/literature/search` `{"words", "source"?: "openalex" | "crossref" | "semanticscholar",
  "from_year"?, "oa_only"?, "claim"? (the text to rank against), "draft_id"?, "limit"? (at most 50), "fresh"?}` →
  `{"works", "source", "service", "words", "ranked_by": "meaning" | "words", "note", "sent": {"service", "site",
  "words", "email", "text"}}`. Works are ordered by closeness to `claim` (else the words): by meaning when a local
  embedding model has vectors in the project (never an embedding server on another computer), else by the words they
  share. `have` marks works already in the documents or the bibliography.
- `POST /api/projects/<p>/literature/open-copies` `{"dois": [...]}` → `{"copies": {doi: open copy | null}, "service":
  "Unpaywall"}` (at most 25 DOIs; needs `contact_email`).
- `GET /api/projects/<p>/literature/citations` → `{"documents": [{"doc_id", "title", "dois", "included", "reason":
  null | "not_allowed" | "no_doi"}], "dois", "included", "not_allowed", "no_doi"}`: what following citations would send.
  Sends nothing.
- `POST /api/projects/<p>/literature/citations` `{"fresh"?}` → `{"cited", "citing", "closeness_by": "meaning" | "words" |
  "none", "documents", "not_allowed", "no_doi", "found_in_openalex", "dois", "partial", "cited_cap"}`: the works the
  documents cite and the works citing them (OpenAlex `referenced_works` and the `cites:` filter). Each work also has
  `n_docs`, `docs`, `doc_titles` (the documents it connects to), `theme_close` and `theme`; lists are ordered by
  `n_docs`, then closeness to the themes. At most 150 cited works are resolved (those shared by most documents).
- `GET|POST /api/projects/<p>/literature/searches`: the saved searches `{"search_id", "title", "words", "kind":
  "search" | "question", "filters": {"from_year", "oa_only"}, "draft_id", "created_at", "since", "last_checked_at",
  "new", "error"}`; `POST` `{"words", "title"?, "kind"?, "from_year"?, "oa_only"?, "draft_id"?}` keeps one (nothing is
  sent). `GET …/searches/<s>` → `{"search", "works"}` (the works new since the person last looked);
  `POST …/searches/<s>/check` asks OpenAlex for works created since then (`from_created_date`; a service that refuses
  that filter is asked for works published since) → `{"search", "found", "added", "works"}`; `POST …/searches/<s>/seen`
  marks them seen; `DELETE …/searches/<s>` removes it. Nothing runs by itself: the page checks searches not looked at
  for 6 hours when it opens.
- `DELETE /api/projects/<p>/literature/cache` → `{"forgotten": n}`.
- `GET /api/literature/zotero` → `{"state": "ready" | "not_running", "library", "collection", "editable"}`: whether
  Zotero's connector answers on this computer and the collection selected in Zotero. Local only.
- `POST /api/literature/zotero` `{"works": [...], "attach_pdf"?: true}` → `{"sent", "library", "collection"}`: saves the
  works through `POST {MARGIN_ZOTERO_URL}/connector/saveItems` (the JSON Zotero's browser connector sends: `sessionID`,
  `uri`, `items` with `itemType`, `title`, `creators`, `date`, `DOI`, `url`, the venue, `abstractNote` and, with
  `attach_pdf`, a *Full Text PDF* attachment that Zotero itself fetches). Zotero puts them in the collection selected
  in its window. `409` `zotero_not_running` when Zotero is not open; `502` `zotero_failed` when it refuses.
- `POST /api/literature/export` `{"works": [...], "format": "ris" | "bibtex"}` → the file as a download.
- `GET /api/projects/<p>/overview` adds `"literature": {"searches", "new"}` (counted from what is kept: it asks no
  service).

### Results across versions (0.15)

- `GET /api/projects/<p>/documents` adds `"reader"` (the reader that read the document's text: 1 for every document
  read before 0.15, 2 from 0.15), `"app_version"` (the Margin version that read it; null before 0.15),
  `"reading_quality"` (`"good"`, `"fair"`, `"poor"`; null for a document read before 0.15) and `"reading_warnings"`
  (sentences) per document. The reading view's routes are under *Documents* above.
- `GET /api/projects/<p>/overview` adds `"made_with"`: `{"version": "0.15.0", "reader": 2, "documents": [{"reader",
  "app_version", "label", "n", "older"}], "results": [{"what": "checks" | "theme_runs" | "labels" | "answers",
  "app_version", "label", "n", "older"}], "older": bool}`. `label` is the version as people read it ("before 0.15"
  when it was not recorded); `older` marks results an earlier version made, and documents an earlier reader read.
  People's own labels are not counted: they do not depend on a version.
- The sheet *How these results were made* of every Excel download has a column *Margin version* and ends with a row
  saying which reader read the project's documents.

### Your record: research log, notes, earlier versions, codebooks (0.16)

Everything here runs on this computer, without AI. Errors are the usual `{"error"}`: 400 for a value that cannot be
used, 404 for something that is not there, 403 (`PermissionError`) for a note or entry that is not yours to change. The downloads (`…/log.md|xlsx`, `…/notes.md|xlsx`, `…/codebooks/<name>.csv`) also accept `?token=`.

#### The research log

An entry: `{"entry_id", "at", "person_id", "who", "mine", "kind", "group", "text", "title", "subject_kind",
"subject_id", "why", "edited_at", "version_id", "has_version", "can_edit", "can_why", "data", "app_version"}`.
`kind` `entry` is a person's own; every other kind is written by the app (documents added or removed, `ai-access`,
`reread`, checks added or removed, `evidence-added`, themes found, removed, renamed, merged or restored, codebooks
made, changed, moved, copied or removed, `restored`). `group` is one of `entries` (an entry of your own, `kind`
`entry`, that you wrote), `documents`, `checks`, `themes`, `codebooks`, `history`. `has_version` says an earlier version
from before the change exists (`version_id`, see *Earlier versions*).

- `GET /api/projects/<p>/log?group=&q=&subject_kind=&subject_id=&offset=&limit=` → `{"entries": [entry], "total",
  "groups": {group: count}, "group_names"}`, newest first (`limit` up to 2000, default 200). `q` matches the text,
  the title and the reason. `groups` counts only the groups that have entries; `group_names` names every group for
  the page's filter (`entries`: *Your own entries*, …).
- `GET /api/projects/<p>/ai-log?person=&provider=&offset=&limit=` → the AI log (I7 stage 3, `ailog.entries`): one
  row per sending to a cloud provider, newest first: `{"rows": [{"at",
  "provider", "provider_title", "route", "model", "kind", "kind_words", "excerpts", "documents", "subject": {"kind"
  (check | codebook | themes | document), "word", "id", "title", "href" (only when the item is in this copy)} | null,
  "task_id", "answered"}], "total", "providers": [{"id", "title",
  "n"}]}`. Read from the ledger (`ai_sent`, with `model` since I7 stage 3).
- `POST /api/projects/<p>/log {"text", "subject_kind"?, "subject_id"?, "title"?}` → `{"entry"}`: an entry of your own
  (at most 10,000 characters; empty is a 400).
- `PUT /api/projects/<p>/log/<entry_id> {"text"?, "why"?}` → `{"entry"}`. `why` (at most 2,000 characters; `""`
  takes it away) can be set on any entry of yours; `text` only on an entry of your own (`kind` `entry`).
- `DELETE /api/projects/<p>/log/<entry_id>` → `{"deleted"}`: only your own entries (400 for the app's); it does not come
  back.
- `GET /api/projects/<p>/log.md` and `…/log.xlsx`: the whole log, oldest first. Markdown has a heading per day; the
  sheet *Research log* has *When (UTC)*, *Who*, *What*, *Entry*, *About*, *Why* and *Margin version*, with the usual
  *How these results were made* sheet. *What* names the group, except that your own entry is *Entry* there.

#### Notes and highlights

A note: `{"note_id", "doc_id", "title", "present", "start", "end", "quote", "text", "colour", "page", "lost", "mine",
"who", "created_at", "edited_at"}`. `start` and `end` are character offsets into the document's text; `quote` is the
words, checked against the text when the note is made (a selection cut inside a word is widened). `text` is empty for
a plain highlight. `colour` is `yellow`, `green`, `blue` or `pink`. When the document was read again, the words are
found again and `start`, `end` and `page` follow them; `lost` is true when they cannot be found (the note is kept).
`present` is false for a note on a removed document (kept).

- `GET /api/projects/<p>/notes?q=&doc=&colour=&mine=1&offset=&limit=` → `{"notes", "total", "documents": [{"doc_id",
  "title", "present", "notes"}], "colours"}`, newest first. `q`: every word of it, in the note or its words.
- `GET /api/projects/<p>/documents/<doc_id>/notes` → `{"notes", "colours"}` in the order of the text (404 for an
  unknown document).
- `POST /api/projects/<p>/notes {"doc_id", "start", "end", "quote"?, "text"?, "colour"?}` → `{"note"}`. Without
  `colour`, yellow. A selection of more than 4,000 characters, or words that are not in the text, is a 400.
- `PUT /api/projects/<p>/notes/<note_id> {"text"?, "colour"?}` → `{"note"}`; `DELETE …/notes/<note_id>` →
  `{"deleted"}`. Only your own notes.
- `POST /api/projects/<p>/notes/<note_id>/evidence {"claim_id", "verdict", "comment"?}` → `{"hyp_id", "claim_id",
  "passage_id", "new"}`: the passage holding the note's words becomes an excerpt of that part of a check, judged by
  you (`verdict`: `supports`, `partially_supports`, `refutes` or `not_relevant`), with the note's words as the sentence
  you point to; `new` is false when the check showed the passage already (your judgement of it is set). 400 when the
  words are no longer in the text, run across two passages, or lie in text left out of the reading.
- `GET /api/projects/<p>/notes.md` and `…/notes.xlsx`: every note (columns *Document*, *Page*, *Words*, *Note*,
  *Colour*, *Who*, *Made (UTC)*, *Changed (UTC)*, *Found in the text now*).

#### Earlier versions

`kind` is `themes` (key: the run id), `check` (key: the hypothesis id) or `codebook` (key: its name). A version is
kept before each change a person makes: theme names, merges, moves and removals; your own judgements, comments,
sentences and the check's note; a codebook. Not the themes found, nor the AI's answers. The latest 200 of each are
kept. Versions of themes and checks are in the project's database (the `versions` table). (A project zip is a copy of
the whole database, so it carries them: a move to another computer keeps them.) A codebook's are beside its file.

- `GET /api/projects/<p>/history/<kind>/<key>` → `{"kind", "key", "title", "versions": [{"version_id", "at", "label",
  "person_id", "who", "mine"}]}`, newest first.
- `GET /api/projects/<p>/history/<kind>/<key>/<version_id>` → `{"kind", "key", "title", "version", "changes": [{"what",
  "before", "after"}], "same"}`: what changed from that version to now, in words.
- `POST /api/projects/<p>/history/<kind>/<key>/<version_id>/restore {}` → `{"restored": true, "changes"}`, or
  `{"restored": false, "changes": []}` when it is the same as now. The state it replaces is kept as a version first,
  and the research log gets a `restored` entry that points to it.

#### Codebooks

A codebook stays a CSV file (see *Frameworks* above), kept `project` (`<project>/frameworks/`) or `home` (all projects),
with a side file for what a spreadsheet cannot hold: a stable id for each code, renames, merges and rewordings, removed
codes, where each example was found, the groups and their order. The old routes under `…/frameworks` still work.

- `GET /api/projects/<p>/codebooks` → `{"codebooks": [info + {"where": "project" | "home" | "bundled", "labels",
  "checks", "profile_default"}], "problems": [...]}`. Labels first follow renames and merges.
- `GET /api/projects/<p>/codebooks/<name>` → `{"codebook": {"title", "label", "directional", "groups": [{"group",
  "group_name"}], "codes": [{"code", "uid", "description", "group", "include", "exclude", "keywords", "examples":
  [{"quote", "doc_id", "title", "page"}]}], "where", "editable", "shadows_home", "in_home", "used": {"labels",
  "by_code", "checks"}, "removed": [{"code", "uid", "labels", …}], "stale": {code: {"since", "passages"}},
  "versions", "profile_default"}}`. `include` is *When to use it*, `exclude` *When not to use it*, `keywords`
  *Words it is matched by*. A code's `uid` is empty for a code not saved yet.
- `POST /api/projects/<p>/codebooks {"name", "title"?, "where"?: "project" | "home", "start"?: "fresh" | "themes" |
  "theory" | "copy" | "csv" | "qdc", "source"?, "label"?}` → `{"codebook"}`. `source`: `{"codes": [...]}` (drafts from
  `GET …/codebooks/sources`, the ones kept), `{"of": "<codebook name>"}`, `{"csv": "<text>"}`, or for `"qdc"` (a
  codebook from NVivo, ATLAS.ti or MAXQDA, `qdc_import.py`) `{"file": "<base64 of a .qdc or .qdpx>", "filename"}` or
  `{"qdc": "<the XML as text>"}`, each with `"codebook"?: "<title>"`: in a project file Margin wrote with several
  codebooks, the one to bring in. Without it such a file answers 400 with `"codebooks": [titles]` beside `"error"`, to
  choose from. A path on disk is never read from here. For `"qdc"` the answer's `codebook` also holds `"imported"`: what
  was brought in (`codes`, `groups`, `folded`, `parents_as_codes`, `headings`, `not_codable`, `no_description`, `cut`,
  `long`, `group_descriptions`, `sets`, `sets_as_groups`, `colours`, `renamed`: [{"from", "to"}],
  `hypotheses_left_out`, `origin`) and `"notes"`, the same in sentences. The columns of a CSV
  are `code`, `description`, `group`, `group_name`, `when_to_use`, `when_not_to_use`, `keywords` (separated by `;`) and
  `examples` (one per line); `code` and `description` are required. A cell that starts with an apostrophe before text a
  spreadsheet would run as a formula (`'=1+1`, `'@x`, `'-x`) loses that one apostrophe: it is what the CSV download
  adds (below). Any other cell is read as written. A name that is taken gets a number.
- `GET /api/projects/<p>/codebooks/sources?all=1` → `{"runs": [{"run_id", "project", "here", "created_at", "themes":
  [{"name", "size", "code": {"code", "description", "described", "keywords", "examples"}}]}]}`: the sets of themes a
  codebook can start from (removed themes left out); `all` adds those of every project.
- `PUT /api/projects/<p>/codebooks/<name> {"codebook": {…as above…}, "merges"?: [{"from": uid, "into": uid}], "why"?}`
  → `{"changes": [words], "version_id", "codebook"}`: writes the editor's state. A code without a `uid` is new; one
  that is gone is removed (its labels wait), unless named in `merges` (its labels go to the other). A bundled codebook
  is a 400. Each saved change keeps the earlier state as a version and goes into the research log with `why`.
- `DELETE /api/projects/<p>/codebooks/<name>[?why=]` → `{"deleted"}`. Labels made with it stay.
- `POST …/codebooks/<name>/move {"to": "home" | "project"}` → `{"codebook"}`: keep it with all projects, or with this
  one. `POST …/codebooks/<name>/copy-here {}` → `{"codebook"}`: this project's own copy of one kept with all projects.
- `POST …/codebooks/example {"quote", "doc_id"?}` → `{"example": {"doc_id", "title", "page", "start", "end", …}}`: where
  words are in the documents (400 when they are not).
- `POST …/codebooks/<name>/define/offer {"examples": [quotes]}` → `{"offered", "why", "reader", "passages",
  "left_line"}`: whether the AI may draft a code's definition from its examples, and who would read their passages
  (by each document's AI setting). `POST …/codebooks/<name>/define {"code", "group"?, "examples": [quotes]}` → `{"job"}`
  (kind `code-define`, waits its turn like every AI job): the AI drafts the definition, *when to use it* and *when not*
  from the passages that hold the examples; its result is the draft, shown beside the fields and never saved by
  itself. 400 without a code name or when no one may read the examples, 404 for an unknown codebook.
- `POST …/codebooks/<name>/try {"codebook"?}` → job (`codebook-try`, no model): for each code of the saved codebook,
  or of the state sent, `{"passages", "documents", "codes": {code: {"passages", "documents", "examples", "share",
  "note"}}}`; `note` says a code matches nothing, or more than a quarter of the passages.
- `POST …/codebooks/<name>/relabel {"code"}` → `{"passages", "job"}`: the AI labels again the passages it labelled with
  that code before its wording changed (a label job with `passage_ids`); 409 when there are none.
- `GET /api/projects/<p>/codebooks/<name>.csv` → the codebook as a CSV file (the columns above). As in every CSV
  Margin writes, a cell that starts with `=`, `@`, a tab or a carriage return, or with `+` or `-` unless it is a number
  (or `- ` and a space), gets a leading apostrophe, so a spreadsheet shows it and does not run it; reading a codebook
  takes that apostrophe off (`review.csv_cell` and `review.csv_uncell`, exact inverses). Codebook files written before
  0.17.2 have none; the download adds them.

### Theory documents, a codebook from theory, concepts and reader 5 (0.18.1)

**A document's role** (roadmap K2 part 1, `docrole.py`). A document marked as theory is the lens the research is read
through: still read, searched and noted, but left out of themes, codebook labels, the excerpts a check reads and key
terms.

- `GET /api/projects/<p>/codebooks/<name>.qdc` → 0.18.7 (G5): the codebook as a REFI-QDA codebook (`urn:QDA-XML:codebook:1.0`) for NVivo, ATLAS.ti and MAXQDA: its groups as parent codes, each code's definition, when to use it and when not, keywords and examples as its description (`qdpx.codebook_xml`). 404 for an unknown codebook.
- `GET /api/projects/{p}/document-roles` → `{"roles": {doc id: "theory"}, "nonscientific": [doc ids]}` (only the
  documents with a role; 0.18.6: and those marked Non-scientific).
- Roadmap N3: `PUT /api/projects/{p}/document-roles` `{"doc_ids": [...], "role": "theory" | "working" | null, "why"?}`
  → `{"role", "changed": [ids], "unchanged": [ids], "was": {id: role before}, "marked_nonscientific": [ids], "roles",
  "nonscientific"}` (the last two as the GET above): one role for many documents by the rules of one
  (`docrole.set_roles`), with ONE research-log entry for the batch (`subject_kind` "documents" when more than one
  changed; `data`: `{"role", "was", "documents"}`). 400 for another role or no documents, 404 (nothing changed) when
  one is not in the project. The bulk bar's *Undo* sends the documents back by the role each had.
- `GET /api/projects/{p}/documents/{d}/role` → `{"doc_id", "role": "theory" | "working" | null, "impact":
  {"themes": [{"run_id", "created_at", "passages"}], "labels": [{"framework", "name", "passages"}], "checks":
  [{"hyp_id", "text", "excerpts"}]}}`: what was made with the document in.
- `PUT /api/projects/{p}/documents/{d}/role` `{"role": "theory" | "working" | null, "why"?}` → `{"doc_id", "role", "changed",
  "impact"}`. 400 for any other role, 404 for no such document.
- 0.18.6: `GET …/documents/{d}/role` also gives `"nonscientific": bool` and, when it is, `"answers": [{"hyp_id",
  "text", "status", "status_text", "all", "all_text"}]` (each check that read it, its answer now and counting the
  non-scientific documents). `PUT /api/projects/{p}/documents/{d}/nonscientific` `{"nonscientific": true | false,
  "why"?}` → `{"doc_id", "nonscientific", "changed", "checks", "answers": [{"hyp_id", "text", "was", "was_text",
  "now", "now_text"}]}` (the answers the mark changed). 400 for a value that is not a boolean, 404 for no such
  document. A check's result gains `status_all_sources`, and each excerpt `nonscientific`; a part or a check that only
  non-scientific documents speak to has the status text *No scientific evidence found*.
- 0.19.1: `PUT /api/projects/{p}/documents/{d}/title` `{"title": text}` → `{"doc_id", "title", "named", "changed"}`:
  a title of the person's own (spaces tidied, at most 300 characters; `bibliography.set_title`), kept when the
  bibliography or a new reading would give another; `""` or `null` gives back the work's title, else the file's. One
  research-log entry (`document-title`) per change. 400 for a title that is not text, 404 for no such document.
  `GET …/documents` and `GET …/documents/{d}` give `"named": bool`.
- 0.19.0 (K3, `nonscientific.py`): `PUT /api/projects/{p}/hypotheses/{h}/nonscientific` `{"count": true | false,
  "why"?: text}` → `{"hyp_id", "count_nonscientific", "changed", "why_changed", "was", "was_text", "now",
  "now_text"}`: count the non-scientific documents in this check alone (stored in the hypothesis's options); a `why` while it is on replaces the reason, and an empty `why` takes it away (the usual
  reason is given again); each change is one research-log entry. 400 for a `count` that is not a boolean or
  a `why` that is not text, 404 for no such check. A result gains `count_nonscientific`, `count_nonscientific_why`,
  `nonscientific_read` (excerpts of such documents read), `status_without_nonscientific` (the answer without them,
  where they count), each part `count_nonscientific`, each excerpt `nonscientific_counted`. The document's `answers` (its role
  route) gain `count_nonscientific`.
  `GET /api/projects/{p}/nonscientific-suggestions` → `{"suggested": {doc id: "a newspaper article"}}` (from the
  bibliography's item type; never marked by itself); `GET …/documents/{d}/nonscientific-suggestion` →
  `{"doc_id", "suggestion": {"item_type", "words", "text"} | null, "answered_no": bool}`; `POST …/documents/{d}/nonscientific-suggestion` `{"answer": "no", "why"?}` → `{"doc_id", "declined":
  true}` (kept in the research log), or
  `{"answer": "again"}` → `{"doc_id", "suggestion"}` (*Suggest again*: takes your No back); 409 when there is nothing to answer or take back. The evidence map's cells gain `nonscientific` and
  `counted` (false: read, not counted), its documents `nonscientific`, its hypotheses `count_nonscientific`, and it has
  `nonscientific_shown` and `nonscientific_shown_in_project` (columns of documents behind no answer, which
  `documents_without_evidence` still counts). The connector's check summary marks evidence `counted_by_exception` and
  gives `status_without_non_scientific` where a hypothesis counts them.
- 0.19.0 (N3): `GET …/documents/{d}/role` also gives `"started": [{"hyp_id", "text", "status", "status_text"}]`, the
  checks started from the document's text (`from_doc`), newest first, as the checks list has them (a check by queue
  that waits for its parts is `"waiting"`; one interrupted before it had parts is left out).

**A codebook from a theory document** (roadmap K2 part 2, `theorycodes.py`, no AI).

- `GET /api/projects/{p}/codebook-theory` → `{"documents": [{"doc_id", "title", "theory"}]}`, theory documents first.
- `GET /api/projects/{p}/codebook-theory/{d}` → `{"doc_id", "title", "role", "concepts": [{"term", "how": "glossary" |
  "defined" | "heading" (with the framework draft no longer "frequent": a term needs a sentence that defines it, and a
  heading's single word one that says outright what it is), "ticked" (offered ticked: its glossary's entries, or the terms it defines when
  it has no glossary), "count" (the sentences that use it), "definition": {"quote", "start", "end", "page"} | null,
  "code": {a draft code}, "suggested": [examples from the evidence documents: {"quote", "doc_id", "title", "page",
  "start", "end", "project"}]}]}`.
- `GET /api/projects/{p}/codebook-theory/{d}/ai` → `{"offered", "why", "reader", "level", "parts"}` (`parts`, when
  offered: the parts the AI reads the document in). `POST` the same path starts a `theory-codes` job whose result is
  `{"ok", "parts", "parts_read", "task_ids", "concepts": [the drafts: "how": "ai", "parts": [the parts that drafted
  it], …], "problems", "reused", "model", "stopped", "withdrawn"?}`: one `theory_codes` task for each part of the
  document (prompt `theory-codes-v2`); `ok` when a part at least was read.
- Then `POST /api/projects/{p}/codebooks` with `"start": "theory"` and `"source": {"codes": [the drafts kept, with the
  examples ticked], "doc_ids": [the documents they come from]}` (`"doc_id"` for one still works); an example from a
  theory document, or from any of `doc_ids`, is dropped. 0.19: with codes from more than one document, each
  document's codes become a group named after it (a draft code's `source_doc` says which; it is not stored). With
  `"groups": [{"group", "group_name"}]` in `source` (the framework draft below) those groups are used, each code
  keeps its own `group`, a code's `source_docs` (a list) names its documents, and the research log adds "in G groups".

**A codebook from theory documents: the framework draft** (roadmap K2, `theoryframe.py`). One draft per project, kept
in the project folder (`drafts/codebook-from-theory.json`). A draft is

```
{"version": 1, "id", "title", "name", "where": "project" | "home", "doc_ids": [...], "focus": "", "created_at",
 "updated_at",
 "reading": {"state": "none" | "running" | "read" | "failed", "job": id | null, "model": str | null, "at": iso | null,
             "parts", "parts_read", "drafted", "problems": [one line each], "frame_task": id | null,
             "input": hash of (doc_ids, focus) the reading answered | null,
             "before"? (the state before a reading started), "stale" (GET and PUT only: the focus changed since)},
 "groups": [{"key": "g1", "name", "about"}],
 "concepts": [{"key": "c" + 10 hex, "group": a group's key | "", "name", "meaning", "when_to_use", "when_not",
               "words": [...], "core": bool, "how": "ai" | "glossary" | "defined" | "heading" | "own", "keep": bool,
               "touched": bool (the person changed it, or added it: a reading leaves it as it is),
               "checked": bool (the person has looked it over; a reading leaves it as it is too),
               "sources": [{"doc_id", "title", "quote", "start", "end", "page"}],
               "examples": [{"quote", "doc_id", "title", "page", "start", "end", "project"}],
               "ai": {"model", "meaning", "when_to_use", "when_not"} | null (the AI's words, to tell what was rewritten)}],
 "left_out": [{"name", "doc_id", "title", "quote", "start", "end", "page"}],   (drafted, not in the framework: a name
                                                    once, none the framework has, none whose quote is a scrap)
 "rev": n}   (raised at every write)
```

- `GET /api/projects/{p}/codebook-theory/draft` → `{"draft": draft | null, "offer": offer | null, "documents":
  [{"doc_id", "title", "theory"}]}`. `offer` = `{"offered" (the AI may read one document at least), "why" (one line
  when not), "reader": "claude" | "local" | "main" | null, "parts" (in all), "documents": [{"doc_id", "title", "level",
  "parts", "offered", "why"}]}` (a document marked No AI: `offered` false, and its `why` says only the terms it
  defines itself are used). A reading whose job is gone (the app restarted, or it was stopped) is shown as `"read"`
  when the draft had been read before, else `"failed"` (with a line in `problems`) or `"none"` (stopped), never as
  `"running"` for ever.
- `POST …/codebook-theory/draft` `{"title", "name", "where": "project" | "home", "doc_ids": [...], "focus"?}` →
  `{"draft", "offer"}`: a new draft (it replaces the one there) from what the documents define outright (glossary
  entries, defined terms, heading phrases), joined across documents by name, ungrouped; glossary entries start kept.
  400 when the name is taken or not a codebook name, no document is given, or `where` is neither; 404 for a document
  not in the project.
- `PUT …/codebook-theory/draft` `{"title"?, "name"?, "where"?, "focus"?, "groups"?, "concepts"?, "rev"?}` (each
  whole: the list sent replaces the list) → `{"draft"}`. `name` must be free for a codebook (400 when not). With `rev` (the draft's `rev` as the page loaded it), a draft that changed since
  (a reading ended, another tab saved) answers 409 and nothing is written: load it again. Concepts are matched to the stored ones by `key` (a missing or unknown key makes a new
  concept, `how: "own"`); `ai` is the app's and cannot be sent; a source must be a span of one of the draft's
  documents (`quote` equal to the text from `start` to `end`, as `lookup` gives them), else it is dropped; an example
  must be a span of an evidence document too (`quote` equal to its text from `start` to `end`, as `evidence` gives
  them; its title and page are the document's), so one from a theory or working document, or from one of `doc_ids`,
  or with words the document does not hold, is dropped; a `group` not among the groups becomes
  "". At most 60 concepts, 12 groups and 8 examples a concept; 400 for a concept without a name or too many concepts;
  404 without a draft.
- `DELETE …/codebook-theory/draft` → `{"ok": true}`: the draft is discarded (a reading that runs is stopped).
- `POST …/codebook-theory/draft/read` → `{"job"}`: a `theory-frame` job (`job.scope` = `"theory-draft"`; a reading
  that runs already is the one answered). Every part of every document the AI may read is drafted (`theory_codes`,
  one task a part, all queued at once for Claude Code), then one `theory_frame` task (prompt `theory-frame-v1`, Opus)
  joins the drafts into groups and concepts; core concepts start kept; what the person touched stays as it is. When
  the frame is refused three times, the concepts are the drafts, ungrouped, and `reading.problems` says so. The job's
  result: `{"ok" (a framework was put together), "stopped", "withdrawn", "state", "model", "parts", "parts_read",
  "drafted", "groups", "concepts", "problems", "reused", "frame_task", "discarded"}`. Stop takes the waiting
  `theory_codes` and `theory_frame` tasks out of the queue. 400 (`offer.why`) when no AI may read any of the
  documents; 404 without a draft.
- `POST …/codebook-theory/draft/evidence` `{"concept": {"name", "meaning"?, "when_to_use"?, "words"?}, "skip"?:
  [passage ids], "k"?: 1 to 8 (4)}` → `{"passages": [{"quote", "doc_id", "title", "page", "start", "end", "project",
  "passage_id", "matched", "marks", "found_by"}]}`: passages of the evidence documents only (never a theory or working
  document, nor the draft's own), found by the concept's `words` (without any, its name): a word counts as the field
  writes it (a phrase as a phrase: "repair knowledge" never finds "repair" alone), and `matched` lists the words
  found in the quote, `marks` where they stand in it (`[start, end]` pairs in characters). Of each passage the sentence (or two that follow each other) that holds the most of them
  (`start`/`end` in the document's text); the passages with the most words first, one per document before a second
  of any. A sentence that could be no example is passed over: a question (an interview guide), a run of references,
  a table's cells, a line of figures. Where the words find fewer than `k` and the project has vectors of the chosen
  embedding model, passages found by meaning (`found_by: "meaning"`, `matched` empty) fill the rest. No AI.
- `GET …/codebook-theory/draft/counts` → `{"documents": n, "counts": {concept key: n}}`: in how many of the evidence
  documents each concept's words are found in a sentence that could be an example (as `evidence` finds them; no AI),
  for the draft as it is kept. 404 without a draft.
- `GET …/codebook-theory/draft/lookup?term=…` → `{"term", "sources": [{"doc_id", "title", "uses" (sentences that use
  it), "options": [{"quote", "start", "end", "page", "score"}]}], "passages": [the evidence for the term, as above]}`:
  of each of the draft's documents, the three sentences that best say what the term means (its glossary entry first;
  `options` empty when the document does not use it). 400 without a term; 404 without a draft.
- `POST …/codebook-theory/draft/make` → `{"codebook"}` (as `GET …/codebooks/{name}`): the kept concepts become codes
  (`code`: the name with a capital first letter, at most 40 characters; `description`: the meaning, then `In the
  theory: “quote” (title, p. N).` and `Also defined in title (p. N) and title (p. N).` for the other sources; with
  no meaning the quoted line alone; `include`: when to use it; `exclude`: when not; `keywords`: the words; the kept
  examples; the framework's groups) through `POST …/codebooks`' `"start": "theory"`, with the *AI draft* mark
  (`ai_draft`, `"from": "theory"`) on the fields that still hold the AI's words. The draft is then gone. 409 while
  its reading runs. 400 when no
  concept is kept or two kept concepts share a name; 404 without a draft.

**Concepts: paths, time and groups** (roadmap D3, D4, `conceptpaths.py`).

- `GET /api/projects/{p}/concept-paths?from={term id}&to={term id}[&k=3]` → `{"from", "to", "paths": [{"cost", "steps":
  [{"from": {"node", "label"}, "to", "kind": "link" | "together", "relation", "pmi", "bridges": [{"passage_id",
  "doc_id", "title", "page", "location", "text", "start"}], "sentences"?}]}]}`. 400 without both terms, 404 for a term
  the glossary does not know.
- `GET /api/projects/{p}/concept-time/{term id}` → `{"node", "label", "with_year", "years": [{"year",
  "documents_in_group", "documents", "passages", "mentions", "wordings": [{"label", "mentions"}], "neighbours":
  [{"node", "label", "together", "pmi"}]}], "no_year": {the same} | null}`; years from the bibliography.
- `POST /api/projects/{p}/concept-groups/{term id}` `{"groups": {name: [doc ids]}}` (two to six sets, not stored) →
  `{"node", "label", "groups": [{"name", "documents_in_group", "theory_left_out", …the same profile}]}`.

**The concept map** (roadmap D1, `conceptmap.py`). Every route takes the same filters, each optional:
`doc={id}[,{id}…]`, `theme={run id}:{theme id}`, `framework={codebook}&code={code}`, `year_from={yyyy}`,
`year_to={yyyy}`.

- `GET /api/projects/{p}/concept-map[?n=60&…filters]` → `{"built", "filters", "n", "passages" (in scope),
  "concepts_in_scope", "nodes": [{"id" (a term id), "label", "passages", "group" (1… or null), "x", "y" (0 to 1, for a
  map 1.6 times as wide as high)}], "edges": [{"a", "b", "together", "pmi"}], "links": [{"a", "b", "relation",
  "source", "types": [{"relation" (seen from a), "source"}]}] (one per pair; "relation" and "source" are its first
  type), "groups": [{"group", "size", "names", "concepts" (term ids, the most central first), "name", "name_source"
  ("concepts" | "person" | "ai_draft" | "ai"), "name_id" (null for a name made from its concepts), "model" (an AI
  name's), "quote" ({"quote", "doc_id", "title", "page", "start", "end"} for an AI name), "changed" (null or {"left",
  "joined"}: labels), "naming_failed" (null or {"reason", "model"})}], "names_elsewhere" ([{"id", "name",
  "name_source", "concepts" (the first six labels), "more"}]: kept names no group on this map takes), "can_name"
  ({"offered", "why", "reader": "claude" | "local" | "main" | null}: whether the AI may be asked to name the groups;
  nothing asks a model), "links_off_map" (links with exactly one end on the map)}`. `n` is 10 to 150. 400 for a
  malformed filter or an unknown codebook, 404 for a set of themes that is gone. Relations of links may also be
  `needs`, `needed_by`, `shapes`, `shaped_by` and `clashes` (D1, the rest).
- `GET /api/projects/{p}/concept-map/options` → `{"documents": [{"doc_id", "title"}], "themes": {"run_id", "themes":
  [{"theme_id", "name"}]}, "codebooks": [{"name", "title", "codes": [{"code", "description"}]}], "years": [yyyy]}`:
  what the filters can choose from (evidence documents only).
- `GET /api/projects/{p}/concept-map/edge?a={term id}&b={term id}[&…filters]` → `{"a", "b" ({"node", "label"}),
  "together", "pmi", "links": [{"relation" (seen from a), "source", "sentences"}], "link" (the first of "links") |
  null, "passages": [{"passage_id",
  "doc_id", "title", "page", "location", "text", "start"}]}` (the first 5, by document). 400 without both, 404 for a
  term the glossary does not know.
- `POST /api/projects/{p}/concept-map/names` `{"action", …}` → `{"record"}` (D1, the rest, `groupnames.py`): a change to
  a group's name. Actions: `rename` `{"name_id"?, "name", "concepts", "labels", "filters", "n"}` (the researcher's
  name for the group as it is now; 400 for an empty name), `use_concepts` `{"name_id", "concepts"}` (named by its
  concepts again), `accept` `{"name_id" | "items": [{"name_id", "concepts", "labels"}], …}` (the AI's draft used),
  `unaccept` `{"name_id" | "items"}` (Undo), `keep` `{"name_id", "concepts", "labels", "filters", "n"}` (a changed
  group's name goes with it as it is), `forget` `{"name_id"}` (returns the removed record) and `restore`
  `{"record"}` (Undo). 404 for a name that is not there. The names stay on this computer.
- `POST /api/projects/{p}/concept-map/name-groups[?n=60&…filters]` `{"which": "unnamed" | "again"}` → `{"job"}` (kind
  `group-names`): the AI drafts a name for the groups still named by their concepts (`again`: every group but those
  the researcher named), one task of kind `group_name` per group, from a few passages where its concepts are mentioned
  together, only from documents the reader may read. The request only queues the work; the job waits for its own
  Start, as every AI job does. Its result: `{"named", "failed", "groups", "skipped" (groups with no passage the AI may
  read), "stopped", "model", "failures"}`. 400 when the map has no group or no AI may read its documents.

Links found from the text (roadmap D2, `textrelations.py`) need no route of their own: they are rows of the concept
page's `related.links` with `"source": "pattern"` and their `"sentences"` (`[{"doc_id", "title", "page", "start",
"end", "quote"}]`); relations gain `effect`, `effect_of`, `replaces` and `replaced_by`, and with D1 (the rest)
`needs`, `needed_by`, `shapes`, `shaped_by` and `clashes` (`clashes` is the same from both ends; the others turn into
their pair when seen from the other concept).

**Reader 5: figures and tables from their rules** (roadmap A6, `reader5.py`).

- `GET /api/projects/{p}/documents/{d}/figures/{n}.png[?scale=0.5–3]` (also `&token=…`, for an `<img>`, as the page
  pictures take it) → the picture of block `n`: the crop of the original PDF's page at the block's box (`x0..y1`,
  points from the top left of the page, with a small margin), as a PNG; `scale` times 72 dots per inch, default 2. It
  is drawn from the original each time it is asked for, as the *Page* panel's picture is: nothing of it is stored or
  sent to an AI. It serves a block of kind `figure`, and also a `table` found from its rules. 404 with the reason when
  there is no such block, the block is of another kind or has no box (a figure from a Word file or web page has only
  its alternative text), the original is missing or not a PDF, or the OCR extra (pypdfium2) is not installed.
- A document's blocks (`GET …/documents/{d}?view=blocks`) may hold `kind: "figure"`: `included: false` (never read
  by searches, codes, themes or checks), its `page` and `box`, the words inside it as its `text`, and `label` *Figure*
  (before 0.18.1: *Text in a figure*). A picture without words has `start == end` (and no passage). Its caption is the `caption` block just
  after it (or, failing that, just before).
- The reading report (`reading`, `documents.reading_json`) gains `figures` (how many were found) and
  `tables_joined` (tables that ran over a page and were joined into one).

### The assessment in words, retractions, agreement between routes, answers a page at a time (0.18.1)

**The assessment in words (N4).** `GET …/hypotheses/<id>` carries `assessment`: `{"sentences": [{"text", "rule",
"refs"}], "moved_by": {"text", "rule", "refs", "from", "to"} | null}`. Each sentence comes from one rule (`verdict`,
`against`, `for`, `concentration`, `part`, `below-strictness`, `waiting-for-you`, `waiting-local`, `moved-by`);
`refs` are `"<claim_id>/<passage_id>"` of the excerpts it rests on. Made by rules, never by an AI; excerpts of
documents not readable by Claude are counted, never quoted. `PUT …/judgements/<claim_id>/<passage_id>` now also
answers `{"status_before", "status", "moved"}` (`moved`: the sentence naming this judgement when it changed the
answer, also written into the research log as kind `verdict-moved`, else null).

#### Retractions and corrections

Looks the DOIs of the bibliography's works and of the documents up in Crossref, which carries Retraction Watch's
retractions and the publishers' corrections and expressions of concern. Only when asked. Off under local-only (400,
nothing sent). DOIs are sent, and for a work of the bibliography without a usable DOI (a published kind of item, with
a title of three words or more, a first author's family name and a year) its title, first author's family name and
year, one request per work (at most 300 a lookup), with a plain `User-Agent: Margin/<version>` and nothing else. A work
whose document is marked No AI is not looked up; by title, a work linked (even probably) to a No AI or a working
document is not looked up either. A match by title is strict (the
same title, a year within one, the same first author, and one candidate only); the matched DOI's notices are found as
any DOI's. A document with no DOI and no work of the bibliography is never looked up by title. The Crossref address can be set with `MARGIN_CROSSREF_URL` (tests use a stand-in).

| Route | Answer |
| --- | --- |
| `GET /api/projects/<name>/retractions` | What the last lookups found: `{"local_only", "checked_at" (the latest lookup or null), "checked", "affected", "by_doi": {doi: {"checked_at", "notices"}}, "by_item": {item_key: [notice]}, "by_doc": {doc_id: [notice]}, "plan": {"ask", "no_ai"}, "title_plan": {"ask", "no_ai", "working", "capped"}, "title_matches": [{"item_key", "doi", "title", "year", "author", "checked_at", "notices"}]}`. A notice is `{"type": "retraction", "correction", "expression_of_concern", …, "doi": the notice's DOI, "date", "source", "work_doi", "checked_at"}`; one found by title also has `"found_by": "title"` and `"match": {"doi", "title", "year", "author"}`. Only works with a notice are listed; a match the researcher rejected is not. |
| `POST /api/projects/<name>/retractions/check` | Starts the lookup as a job (`{"job"}`; `progress` has `done` and `total` works and DOIs asked; one at a time per project). Its result: `{"looked_up", "no_ai", "notices", "capped", "checked_at", "by_title", "title_matched", "title_ambiguous", "title_capped"}`. 400 under local-only or when there is nothing to ask about. |
| `POST /api/projects/<name>/retractions/matches/<item_key>` | Body `{"reject": true}` (the default): *Not this work*, the match by title of this work is hidden and not proposed again; `{"reject": false}` takes it back. Kept with who and when (`rejected_by` is the person) and written in the research log (kind `retraction-match`, subject `bib_item`). Answer: `{"item_key", "doi", "title", "rejected", "changed"}`. 404 for a work with no match. |

`GET …/bibliography` gives each work a `notices` list, and `retractions: {checked_at, affected, local_only}` beside `counts`.

#### Agreement between routes (I5)

The local model and Claude answer the same sample of an answered kind of task, and
Cohen's kappa compares their decisions (the grade of each excerpt for `check`, `reread` and `second`; whether each
candidate code applies for `label`; the relation of each pair of terms for `link`). Only tasks whose documents Claude
may read are used. An answer a task already has from a route is reused; only what is missing is asked. The passages sent to
Claude are noted in the ledger. Kappa from 0.8 is good, from 0.6 fair, below that poor.

**Kept comparisons.** A comparison that ran to its end (tasks that failed inside it count, with `failed`) is kept in
the project's `agreement_runs` table: `{"run_id", "at" (UTC, ISO), "kind", "n", "compared", "failed", "decisions",
"kappa", "agree", "local_model", "claude_model", "app_version"}`. One stopped with Stop is not kept. The comparisons
describe this computer's local model, so they stay in this copy of the project: a zip of your whole project, for moving it, keeps them.

| Route | Answer |
| --- | --- |
| `GET /api/projects/<name>/agreement/plan` | `{"kinds": [{"kind", "answered", "name", "noun"}], "problem": a sentence when it cannot start (Claude not the main AI, no local model, local-only) or null, "claude": the main backend, "plan": null, "kept": the kept comparisons, newest first, at most 20}`. With `?kind=label&n=30` (n 10 to 100), `plan` is `{"kind", "n" (tasks compared), "ask_local", "ask_claude" (tasks each route would be asked), "left_out" (answered tasks Claude may not read)}`. 400 for a kind without a decision. |
| `POST /api/projects/<name>/agreement` | Body `{"kind", "n"}`. Starts a job (`{"job"}`, kind `agreement`; `progress` has `done` and `total` tasks). Its result: `{"kind", "n", "compared", "failed", "kappa" (null when undefined), "agree" (share of identical decisions), "decisions", "verdict" (a plain sentence), "left_out", "asked": {"local", "claude"}, "items": [{"task_id", "decisions", "same", "local", "claude" ("stored" or "asked")} or {"task_id", "error"}], "thresholds": {"good": 0.8, "fair": 0.6}, "local_model", "claude_model" (the names the two routes answered under), and for a finished run "kept" (its stored row) and "previous" (the last kept run of the same kind before it, or null)}`. A stopped run has neither. 400 when it cannot start. |

**The answers a page at a time (H5).** `GET …/hypotheses?offset=<n>&limit=<n>` (with the same `q`, `status`, `batch`
and `threshold`) answers one page of the list: `hypotheses` holds at most `limit` rows (100 when not given, at most
1,000) from row `offset`, in the same order as the whole list, and `total` (the rows after the filters), `offset` and
`limit` are added. `counts` still cover every hypothesis. Without `offset` the answer is what it always was.

### Jobs

`GET /api/jobs` → `{"jobs": [Job summary]}` newest first. `GET /api/jobs/<id>` → full Job:
```json
{"id": "fdd6a426a6f0", "kind": "check" | "prepare" | "batch" | "more" | "reread" | "read-new" | "read-unread" |
         "second-opinion" | "ingest" | "index" | "benchmark" | "label" | "link" | "theme-names" | "theme-new" | "resolve" | "stronger" |
         "queue-run" | "claude-install" | "draft-find" | "draft-check" | "bibliography" | "citations" | "new_reader" | …,
 "title": "…", "queue": false,
 "project": "Demo" | null, "state": "queued" | "running" | "done" | "error" | "cancelled",
 "created_at": 1793136448.87, "started_at": … | null, "finished_at": … | null, "seconds": 19.9,
 "error": null | "message", "error_kind": null | "backend" | "memory" | "request" | "internal",
 "waiting_for": null | {"id", "kind", "title", "message": "Queued: starts when “…” has finished"},
 "background": false,
 "local": null | {"gate": "wait" | "go" | "force", "waiting": 12, "noun": "excerpt" | "passage" | "theme" | "pair" |
                  "task" | "document", "model": "qwen3.5:9b" | null,
                  "memory": null | {"need": 8700000000, "free": 2900000000, "short": true}, "problem": null | "…"},
 "progress": {…kind-specific…}, "result": {…} | null}
```
Summaries (in lists) omit `progress` and `result`. Jobs live until the app is closed. `background`: started by the app
itself, not by the person.

**The local part of a job (0.19.13, `localgate.py`).** Starting Claude and starting the local model (Settings' model for
documents marked Only a local AI, and the AI mix's share) are two separate clicks. `local` is null for a job with no
work for the local model; otherwise its gate says whether the local model may read: `wait` (it waits for its own Start:
the default of a job that also has work for Claude, and the state after a memory refusal, with `memory.short`), `go`
(Start was pressed, or the job is all local and was started by its own button, such as `read-local` or *Answer the N for
your local model now*), `force` (*Start it anyway*: whatever memory is free). `waiting` counts what waits for the local
model, in `noun`s; `model`, `memory` and `problem` (why no local model can be used: then there is no Start) come from
the model server without starting it. While the gate waits and something waits, `progress.model` is `{"who": "local",
"phase": "ready", "model"}` unless Claude's report is newer, and nothing loads the model.
- `POST /api/jobs/<id>/local/start` `{"force"?: bool}` → `{"job": Job}`: opens the gate; one Start covers the whole
  job. The local items are then read beside Claude's. A memory refusal puts the gate back to `wait` with the numbers.
- `POST /api/jobs/<id>/local/stop` → `{"job": Job}`: back to `wait` after the item in hand; the job's own
  `POST /api/jobs/<id>/cancel` still stops everything, and what waits for the local model keeps waiting (a check by
  queue whose Claude Code part is done is kept, its excerpts waiting for *Read them now*).
- Both: 409 when the job has no local part, or has ended.
Outside the app (the command line, the connector) there is no gate: the local model reads at once, as before.

**Jobs wait their turn (0.17.0, roadmap M6: `api_common.Jobs`, `LANES`).** Jobs of one project that change the same
things never run at the same time: the later one stays `queued`, with `waiting_for` naming the job it waits for (the
one just ahead of it in the project's queue, else the one running), and starts when its turn comes, first come first
served. It can be cancelled while it waits (`POST /api/jobs/<id>/cancel`: it leaves at once, `cancelled`, and the ones
behind it move up). Which jobs wait for which:
- *the new reader* (`new_reader`, and `reread` of one document, not of an excerpt) runs alone in its project: it waits
  until no other job of the project runs, and while it runs every other job waits for it (a job holding passage ids
  from before the move would put its results on passages that are gone). While it still waits, it (and search by
  meaning or another move waiting behind it) holds back only search by meaning and other moves, so a move waiting
  behind a check that waits for Claude Code never stalls the rest of the project;
- *adding documents* (`ingest`) and *search by meaning* (`index`): adding waits for search by meaning and it for
  adding; two of the same kind never run together;
- *new themes for one set of themes* (`theme-new`) run one after the other (two would take the same passages);
- everything else (checks, labels, themes, the glossary, codebooks tried out, the bibliography …) runs beside the
  others, except the new reader, as before; jobs that use the chat model still take turns for it, and a job waiting
  for its project's turn does not hold the model.
When both are asked for, the new reader goes first: search by meaning that still waits moves behind it (the other
waiting jobs keep their places), so no passage is prepared twice; search by meaning asked for while the new reader
waits or runs waits for it. `waiting_for` is null once the job has its
turn (a job that then waits only for the chat model is `queued` with `waiting_for` null, as before).

### Testing a model

Margin 0.8: the page no longer offers this (it needs a reference project such as ENLENS's pilot); the endpoint stays
for developers.

`POST /api/benchmark` `{"reference": "/path/to/pilot", "kinds": ["verify_set", "extract"], "n": 10}` → job (kind
`benchmark`): runs the chosen model on tasks a reference workspace already answered and compares. Progress
`{"done", "total", "task", "model"}`. `result`: `{"model", "backend", "verdict": ["Checking claims: usable for a first
pass; …"], "table": [{"measure": "Usable answers on the first try", "Checking claims": "90%"}], "kinds": {…raw…}}`.
