# Privacy and data protection

What Margin sends off the computer it runs on, when, to whom, and what it never sends. Written for ethics
applications and data protection impact assessments (DPIAs). For the same facts written for users, see
[Privacy: what leaves your computer](manual/privacy.md). How the methods work is in [METHODS.md](METHODS.md).

Each statement names the module of `src/margin/` or the manual page it can be checked against. It describes
Margin as of this version.

## Who processes what

Margin is a program the researcher installs and runs on their own computer. It is a small web server that listens on
`127.0.0.1` only by default (`--host` can open it to the network, which nobody needs for ordinary use), with a key per
run (`gui/server.py`); the page loads nothing from the internet. Margin's developers
run no service of their own, and the app sends them nothing: there is no telemetry, no account and no analytics.
Releases are downloaded from GitHub ([below](#other-online-services-not-ai)).

| Party | Role | What it receives |
| --- | --- | --- |
| The researcher (and their institution) | Decides what is processed, and how | Everything: the projects stay on their computer |
| Anthropic | Runs the Claude models, when the researcher uses Claude | The passages and text inside the AI tasks Claude answers, from documents Claude may read ([below](#what-goes-to-claude)) |
| OpenAI, Google, Mistral, Microsoft (Azure) or OpenRouter | Run a model, only when the researcher sets that provider up and allows a document to it | The passages and text inside the AI tasks it answers, from documents that allow that provider ([below](#other-cloud-providers)) |
| OpenAI (Codex) or Google (Antigravity) | Run an agent on the researcher's own ChatGPT plan or Google account, only when the researcher chooses it and allows a document to that company | The passages inside the queue's tasks that agent takes, from documents that allow that company ([below](#codex-and-antigravity)) |
| A model server on the computer (Ollama, LM Studio and others) | Runs a local model | The text of the tasks it answers; it stays on the computer |
| Crossref | Answers a retraction lookup | DOIs, and the title, first author's family name and year of bibliography works without a DOI, only when the researcher asks ([Other online services](#other-online-services-not-ai)) |
| GitHub | Hosts Margin's releases | A request for the latest version ([Other online services](#other-online-services-not-ai)) |

## In short

- **Projects stay on the computer.** The documents, their text, the database, judgements, notes, the research log
  and settings are kept in the data folder (`~/margin` or `MARGIN_HOME`).
- **Each document has an AI setting**: *Claude may read it*, *Only a local AI*, or *No AI*. Margin enforces it in
  code, at the point where every AI task passes (`access.py`).
- **Document text leaves the computer by two ways only**: a cloud route, from documents marked *Claude may read
  it* that allow its provider (by default only Anthropic), each passage written to a ledger as it leaves
  (`access.record_sent`); and a model or embedding server the researcher set up at another computer's address, from
  documents that allow it. The cloud routes are Claude's and [other providers'](#other-cloud-providers).
- **The whole installation can be made local-only** (`--local-only`): no document text then goes to Claude
  ([Switching everything off](#switching-everything-off)).

Nothing is sent to Claude until the researcher runs a feature that uses the AI. With Claude Code, the default route,
the work then waits until the researcher starts Claude Code
([Start Claude Code](manual/claude-code.md#start-claude-code)). In the app, the first documents added to a new
project ask who may read them, with nothing preselected (`access.default_chosen`). Documents added from the command
line or the connector without a setting take the project's default, which is *Claude may read it* until a default is
chosen (*Only a local AI* on a local-only installation; `access.default`).

## Each document's AI setting

Every document has one of three settings (`access.LEVELS`; [Who may read each document with
AI](manual/privacy.md#who-may-read-each-document-with-ai)):

| Setting | Who may read its text |
| --- | --- |
| *Claude may read it* (`cloud`) | Claude Code, the Claude API, and the cloud providers and agents (Codex, Antigravity) whose company the document allows (by default only Anthropic) |
| *Only a local AI* (`local`) | A model server on this computer, or a person |
| *No AI* (`none`) | A person only |

It is set when documents are added (one answer per batch), per document on the Documents page, or in a `manifest.csv`.
An optional note (*Why*, for example "publisher licence") is kept with it. A document can also have a cap: once Claude
has read a given share of its text, it is treated as *Only a local AI* for new tasks (`documents.ai_budget`).

**How it is enforced** (`access.py`, `tasks.py`; [How it is enforced](manual/privacy.md#how-it-is-enforced)):

1. Each AI task is labelled with the most restricted setting of every document it names, at any depth of its
   contents (`access.label_payload`).
2. Before any model is asked, the setting is worked out again from the task's contents, and a task is refused when its
   setting does not allow that model (`access.require`). A *No AI* task is refused on every route; an *Only a local
   AI* task is refused on every route that leaves the computer.
3. The queue hands out only tasks the agent that takes them may read, by that agent's company: Anthropic for Claude
   Code, OpenAI for Codex, Google for Antigravity (`taskqueue.next_tasks`); the file queue writes only tasks Claude may
   read (`tasks.export`).
4. A model server counts as "on this computer" only when its address is `localhost` or a loopback address
   (`access.on_this_computer`). A model server at any other address is a cloud provider: a known one by its address
   (an OpenAI address is OpenAI), otherwise "a server on another computer". It may read only documents marked
   *Claude may read it* that allow that provider ([below](#other-cloud-providers)).

The rule is code, not an instruction in a prompt. A feature that forgot to split its work would be stopped by the
guard before anything is sent.

## What goes to Claude

Claude is reached by three routes (`routing.ROUTE_NAMES`, `routing.OFF_COMPUTER`):

| Route | Account | When text leaves |
| --- | --- | --- |
| **Claude Code** (the default) | The researcher's own Claude plan. Margin never sees the login | When a Claude Code helper takes a batch of tasks from Margin's queue (`taskqueue.py`) |
| **The Claude API** | A key of the researcher's own, only after *Allow cloud models* is switched on (`home.py` `allow_cloud`) | When a task is sent (`tasks._send`) |
| **A Claude chat with the connector** | The researcher's own Claude account, in the Claude app or Claude Code | When the connector's tools return results to the chat (`mcp_server.py`) |

**What a task holds.** Depending on its kind (`prompts.py`): the hypothesis or claim, the search words, the excerpts
and the 300 characters before each one (to resolve words such as "it"), each document's title and page, a codebook's
codes, pairs of glossary terms with short passages where each occurs, the passages that best represent a theme,
consecutive passages of one document (references), the passages that hold a code's examples with the code's name and
group (a draft definition, `codedefine.py`), and, when a person asks for an excerpt to be read again, their
comment. A document linked to a bibliography entry is titled by that work's title
(`bibliography.py`). Tasks of documents marked *Only a local AI* or *No AI* are never among them. A code's
definition, *when to use it* and *when not* go with every label task of its codebook, whatever document it labels: a
definition the local model drafted from documents marked *Only a local AI* does too once it is kept, so the editor
says to rewrite it if it gives away what those documents say.

**What a Claude chat sees through the connector.** The project names and the path of the projects folder; document
titles, pages and counts, except that a document marked *No AI* is shown as *Restricted document 3*, because a title
can name a person (`access.restricted_titles`); the hypotheses of the project's checks and their answers, except a
check started from words of a document marked *Only a local AI* or *No AI* (a working document's *Check against the
corpus*), which it neither lists nor opens (`docrole.kept_here`); and the excerpts, search lines and concept details of documents Claude may read. Text of documents marked *Only a local AI*
or *No AI* is reported as counts only, and what a model wrote after reading such text is left out. Excerpts are shown
without the text before them. The connector reads files on the computer when asked to add sources; it sends nothing
of them except what its tools return.

**The Claude Code run Margin starts** works in an empty folder away from the projects, has no tool that reads, writes
or searches files, runs commands or browses, and loads none of the researcher's own Claude Code settings, hooks,
instructions or other plugins. All it can see are the tasks Margin gives it ([How it is
enforced](manual/privacy.md#how-it-is-enforced)).

**The ledger.** Every passage that leaves for Claude, through any of the three routes, or in the file queue, is written
to the table `ai_sent` at that moment, with the passage, the document, the route, the feature, the task and the time;
for the queue and the API, the passage shown before each excerpt is recorded too (`access.record_sent`). The
Documents page shows the share of each document sent; *Settings → Technical → What was sent to Claude* downloads the
whole list as CSV ([What Claude has read](manual/privacy.md#what-claude-has-read)). Changing a document's setting
applies to everything not yet answered; what Claude has already read stays in the results and the ledger.

**Agreement between routes and model tests** send their samples through the same guard and ledger
(`access.sending`), and are asked only when the researcher presses the button.

## Other cloud providers

The providers are one table (`providers.py`), reached through `llm.CloudBackend`. *Settings → AI* has a fourth choice,
**Another cloud provider (API key)**: OpenAI, Google Gemini, Mistral, Azure OpenAI or OpenRouter, each through its
OpenAI-compatible chat API, over HTTPS only. It needs *Allow cloud models*, and is refused on a local-only
installation ([Switching everything off](#switching-everything-off)).

- **Who may read what.** A document marked *Claude may read it* also lists the cloud providers that may read it, **by
  default only Anthropic**. So every project made before means what it did, and nothing reaches another provider until
  the researcher allows it: for the project (on the *Documents* page) or per document (its AI setting). A document that does not
  allow the provider of the main route is treated as *Only a local AI* for that route: its excerpts go to the local
  model for restricted documents, or wait for the researcher's judgement. The Claude connector and Claude Code's queue
  count as Anthropic, whatever the main route.
- **What a provider receives.** The same text Claude receives (the hypothesis and the excerpts inside the AI's tasks,
  [above](#what-goes-to-claude)), only from documents that allow it. Its own terms decide what it keeps and whether it
  trains on it: Margin decides nothing there. Check the provider's API data terms. OpenRouter passes the text on to the
  model's own provider.
- **The ledger** names the provider that received each passage (a *Provider* column in the CSV).
- **A model server on another computer** is a provider too (see *Local models* below): this closes a gap in versions
  before this one, where such a server, typed into the local server field (an OpenAI address, or a lab's GPU server),
  could read every document marked *Claude may read it*. Documents now wait until the researcher allows it.
- **Not measured.** Margin's default models and routing were measured on Claude only.

## Codex and Antigravity

*Settings → AI → Subscription* also offers **Codex** (OpenAI, on a ChatGPT plan) and **Antigravity** (Google, on a
personal Google account), set up and started from Margin as Claude Code is (`agentcli.py`, `gui/api_agents.py`). Neither
has been tried with a real account yet: they are built against stand-in programs that follow the makers' documentation,
and are not measured with Margin.

- **Consent per agent.** Choosing one asks first, naming the company (`allow_codex`, `allow_antigravity`, false until the
  researcher says yes; the setting is refused without it). Nothing runs until the researcher presses *Start Codex* or
  *Start Antigravity*.
- **Passages go to the company of the agent that takes them.** The queue works out every document's setting for the
  provider of the agent that takes a task (`access.py`, `taskqueue.next_tasks`): Codex is OpenAI, Antigravity is Google,
  Claude Code is Anthropic. A document that allows OpenAI but not Anthropic reaches Codex and never Claude Code, and the
  reverse. The connector each agent uses answers for that agent (`MARGIN_ROUTE`), so what it shows and hands out follows
  the same rule. The ledger
  records the provider and the agent for each passage, and since I7 stage 3 the model (the AI log).
- **Codex is closed in.** It starts in an empty folder, read-only, with the researcher's own Codex settings left out
  (`--ignore-user-config`). Its command, web search and image tools are switched off, it may not ask for approval, and
  Margin's connector, the only one it is given, offers it three tools: `next_tasks`, `submit_answers` and `release`.
- **Antigravity cannot be closed in from outside.** Its own tools cannot be switched off. Margin starts it in an empty
  work folder of its own, in its sandbox and without slash commands, with its default of asking before every tool,
  which nobody can answer in a background run: every tool but Margin's three is refused. **It runs in a home folder of
  its own** (`<data folder>/agy-home`), with settings Margin writes before every run, so the researcher's own
  Antigravity settings never reach it: no permission they gave, no "run every tool without asking", no connector of
  theirs, and no AI credits are spent. Their own choices about telemetry are carried over. **Margin refuses to start it
  when its help does not list `--sandbox`**, rather than start it less closed in. A tool it refused a helper is written
  in the run's report: a helper never needs one, so text in a passage may have asked for it (prompt injection).
  Margin 0.20.0–0.20.1 wrote the line `mcp(margin/*)` and its work folder into the researcher's own Antigravity
  settings; the set-up offers to take them out again.
- **The login stays with the agent.** Margin never sees it. The installers are the makers' own, run only when the
  researcher confirms the line shown ([OpenAI](https://github.com/openai/codex), [Google](https://antigravity.google/docs/getting-started)),
  and refused under `--local-only`.
- **What each company does with the text** is decided by the researcher's plan and the company's terms: check them
  before a document that needs care is allowed to them (Codex: [sign-in and plan](https://learn.chatgpt.com/docs/auth)).

## Local models

A model served on the computer (Ollama, LM Studio, llama.cpp, Jan, vLLM) keeps every word on it
([A model on your own computer](manual/local-models.md)). It may read documents marked *Claude may read it* or *Only a
local AI*. Requests go to its address on this computer; nothing about them is sent elsewhere.

Points for an assessment:

- **A model server on another computer** (an address that is not `localhost`, `127.0.0.1` or `::1`) is treated like a
  cloud provider: it may read only documents marked *Claude may read it* that allow it (`access.backend_levels`;
  [Other cloud providers](#other-cloud-providers)). Passages sent to it are written to the ledger, with the provider
  it is (`other` for a server that is none of the known providers). A researcher who used such a server before this
  version finds its documents waiting until they allow it.
- **Search by meaning** sends passages to the embedding server. An embedding server on another computer receives
  neither passages of documents marked *Only a local AI* or *No AI*, nor of documents that do not allow its provider
  (`other`, or a known one by its address), nor glossary terms found only in them (`embed.py`, `terms.py`); it does
  receive the text of searches.
- **Getting a model** downloads Ollama's installer from ollama.com and a model from Ollama's library, only when the
  researcher presses the button. No document is sent.

## What never leaves the computer

- The text of documents marked *Only a local AI* or *No AI*, to Claude or to a model server on another computer, in
  any feature, words selected from them and checked against the corpus included: such a check is read by a local
  model only, or, from a document marked *No AI*, by no model (`docrole.origin_floor`).
- The project's database (`enlens.sqlite`) as a file.
- The answers Margin keeps so as not to ask the AI again (`ai_cache`), the search index, the glossary, embeddings,
  earlier versions (*History*) and settings are kept for speed, not for sharing. The kept answers are not tied to one
  document: removing a document leaves them (they answer only the same text again) and *Remove everything* clears them.
- Anything at all, to another person: Margin has no sharing. A project leaves the computer only as a zip the
  researcher makes and carries away themselves ([Projects and other computers](manual/projects.md)).
- Keys and secrets ([Keys and secrets](#keys-and-secrets)).
- Paths on the computer.
- Zotero data: Margin reads it from the Zotero app on this computer (`127.0.0.1`, port 23119), never from Zotero's
  servers, and never changes it (`bibliography.py`).
- Text recognition of scanned pages: Tesseract runs on the computer (`ingest.py`).

## Other online services (not AI)

| Service | What is sent | When | Under `--local-only` |
| --- | --- | --- | --- |
| **Crossref** (`api.crossref.org`), retractions and corrections | DOIs, and for a bibliography work without a DOI (a published kind of item with a title of three words or more, a first author and a year) its title, first author's family name and year, one request per work; with `User-Agent: Margin/<version>`; no name, e-mail or project name. A work with a document marked *No AI*, or linked to a working document, is not looked up; a document with no work of the bibliography is never looked up by title | Only when the researcher presses *Check for retractions*, or runs `margin retractions --check` | Off: nothing is sent |
| **GitHub** (`api.github.com`, `github.com`), updates | A request for the latest release, with `User-Agent: margin-update`; no project data | When a page of the app opens, every two minutes while it is open (one look shared by open tabs), and on *Check for updates*; a download only on *Update* | Not switched off |
| **Anthropic's installer** (`claude.ai`) | A download of Claude Code | Only when the researcher confirms installing it in *Set up Claude* | Refused |
| **OpenAI's and Google's installers** (`chatgpt.com`, `antigravity.google`) | A download of Codex or Antigravity | Only when the researcher confirms installing it in the agent's set-up | Refused |

Sources: `retractions.py`, `update.py`, `gui/server.py` (`get_update`), `claude_setup.py`;
[Retractions and corrections](manual/bibliography.md#retractions-and-corrections),
[Update](manual/install.md#update). Like any web request, each of these shows the service the computer's network
address.

*Report a problem* opens a GitHub form in the browser; *Copy technical details* copies the Margin version, how it was
installed, the system, the AI route and the update channel, never a path, project, document name or key
([Reporting a problem](manual/settings.md#reporting-a-problem)).

## Keys and secrets

- **A cloud provider's API key** (OpenAI, Gemini, Mistral, Azure, OpenRouter) is kept in the system's keychain, or in
  a user-only key file where there is none (`keychain.py`). Never in `settings.json`, a log, an error message, the
  record of how an answer was made, a project, or a *Move Margin to another computer* file. The app shows only
  whether a key is stored.
- **A Claude API key**, if saved, is kept in `credentials.json` in the data folder, readable by the user only, or
  read from `ANTHROPIC_API_KEY` (`home.py`). It is never in a project or a move file.
- **Claude Code's, Codex's and Antigravity's login** is the agent's own; Margin never sees it.
- **The app's key** for the running server is kept in a file only the user can read (`app-token-<port>.json`).
  Whoever has the link with that key can open Margin while it runs ([What goes
  where](manual/privacy.md#what-goes-where)).

## Records for an audit

- **The ledger of what was sent to Claude**: per passage, document, route, feature, task and time, downloadable as
  CSV ([What Claude has read](manual/privacy.md#what-claude-has-read)).
- **The research log**: dated entries the app writes by itself (documents added or removed, who may read a document
  with AI, checks made or removed, codebooks changed), and entries of the researcher's
  own. The app's entries cannot be removed (`researchlog.py`; [The research log](manual/notes-and-log.md#the-research-log)).
- **How these results were made**, at the end of every Excel download: the models, routes, prompt versions and Margin
  versions behind the results ([What every answer records](manual/models.md#what-every-answer-records)).
- **The raw answer of every model**, with its model, route and time, in the project's `results` table.

## Switching everything off

Whoever installs Margin can remove every cloud option for good, with `margin-gui --local-only`, the environment variable
`MARGIN_LOCAL_ONLY=1`, or an empty file named `local_only` in the data folder (`home.local_only`;
[For whoever installs Margin](manual/settings.md#for-whoever-installs-margin)). Then:

- every document counts as *Only a local AI*, and no document can be set to *Claude may read it* (`access.levels`,
  `access.set_documents`);
- the Claude API, the other cloud providers, Claude Code, Codex and Antigravity are hidden and refused, Margin never starts an agent, its plugin is not written
  (`claude_setup.py`), and the queue hands out no tasks (`taskqueue.py`);
- the Crossref lookup is off.

Two things are not switched off: the update check with GitHub, which sends no project data, and the connector program
itself if someone adds it to a Claude app. Through the connector a chat could still see project names, document
titles and counts, but no document text, since every document counts as *Only a local AI*. Do not add the connector
on a local-only installation.

## What Margin cannot promise

- **Anthropic's handling of the text it receives.** Retention, use for training, the location of processing and
  sub-processors are set by Anthropic's terms for the account used (a personal Claude plan, a Claude Team or Enterprise
  plan, or the API), not by Margin. *Set up Claude* and *Settings → AI* show which terms apply to each kind of plan
  and link to Anthropic's own page with the date it was checked ([Your Claude account and
  licences](manual/privacy.md#your-claude-account-and-licences)). Check Anthropic's current privacy policy, terms and
  the account's data settings for the application; mark documents that must not reach Anthropic *Only a local AI*.
- **Another cloud provider's handling of the text it receives** (OpenAI, Google, Mistral, Microsoft, OpenRouter and the
  provider behind it): set by that provider's API terms, not by Margin. Check them before allowing a document to it.
- **Cloud folders.** If the data folder, or a zip made from a project, is kept in a cloud service (OneDrive,
  Dropbox), that service holds the files under the institution's own agreement with it, and may keep earlier or
  deleted versions for a while.
- **The computer itself.** Projects are only as private as the data folder; on a computer other people use, keep it in
  the user's own folder.
- **Licences of the documents.** Whether a licence allows text and data mining by an outside service is for the
  researcher and their library to check.
- **Local models are not checked** for what they do beyond answering: choose a model server you trust.

## For an ethics application or a DPIA

A short description that can be adapted:

> Analysis used Margin [version], which runs on the researcher's computer and keeps all documents and results there.
> Each document was assigned an AI setting. Documents containing personal data [were marked "No AI" / "Only a local
> AI" and were read only by the researcher / by a language model running on the researcher's computer]. [For
> documents marked "Claude may read it", only the passages selected for each task were sent to Anthropic's Claude
> models via [Claude Code on a [plan] account / the Claude API], under Anthropic's [commercial / consumer] terms; / only the passages selected for each task were sent to [OpenAI via Codex / Google via Antigravity], on the researcher's own [ChatGPT plan / Google account], under that company's terms.]
> Every passage sent was logged by the software, and the log is kept with the project. [The installation was set to local-only, so no document text could be sent to
> a cloud model.]
