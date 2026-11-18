[Manual](../MANUAL.md) › Settings

# Settings, and setting Margin up for others

> **In short**
> - *Settings* has five tabs: **AI**, **Checking**, **Exploring**, **Documents** and **Technical**.
> - The version of Margin is at the top right of every tab; click it to look for updates.
> - Whoever installs Margin for others can make sure nothing ever leaves the computer.

## The five tabs

<img src="../images/manual/settings-ai.png" alt="Settings, the AI tab" width="800">

| Tab | What you set there |
| --- | --- |
| **AI** | **Work waiting for Claude Code** (what waits, in order: *Do first*, *Hold*, *Remove*; the helpers; [Claude Code](claude-code.md#following-the-work)). Which AI reads your documents, as five choices: **Claude Code** (recommended: your own Claude plan), **A model on this computer** (automatic, Ollama, or an OpenAI-compatible server such as LM Studio, with its address, model and reasoning switch), **No AI (demo)**, and the **Claude API (team key)** for a shared installation, behind a confirmation and *Allow cloud models*, and, after *Allow cloud models*, **Another cloud provider (API key)** ([below](#another-cloud-provider-with-an-api-key)). With Claude Code: the set-up checklist with *Set up Claude*, *Let the auditor use Fable*, *How much thought*, *Helpers at once*, *The mix of local and Claude* and *At your plan's usage limit* ([Which model does what](models.md#the-mix-of-local-and-claude)). With a local model: *Install Ollama* (or *Start Ollama*) when no model server runs, *Download qwen3:8b* when none is installed, and the *Local model for restricted documents*. *Save and test* says whether the AI answers (with Claude Code, whether it is set up). |
| **Checking** | The **strictness**: how sure the AI must be before a judgement counts. It saves at once, applies to every result, and reports which answers and counts changed; *Back to normal (60%)*. Beside it, **how often you agreed with the AI, by its certainty**: a small chart from the excerpts you judged, and after 20 judgements perhaps a suggestion ("When the AI was at least 70% sure, you agreed with it in 85% … *Use 70%*"). Also how new checks start: other words, parts, how many excerpts to read, and at most how many from one document. And **When work has finished**: a notification from your computer when work you started that took more than 20 seconds has finished, or stopped with a problem, so you can close the browser while a local model works (Margin keeps working; a click on the notification opens it again). *When Margin is not in front* (the default) sends one only when no Margin tab is the one you are looking at; also *Always* or *Never*, and *Send a test notification*. On a Mac, the first one asks whether Margin may send notifications (System Settings › Notifications › Margin). |
| **Exploring** | The codebook of *By document* and how many themes a new set looks for (in a team project whose owner chose a default codebook, that one holds there, and its help line says *This project uses the team’s default*; your setting still holds in your other projects). A link to *Codes* › *Codebooks* leads to the page where you make, change and remove codebooks ([Make your own codebook](codebooks.md)). |
| **Documents** | **Reading scanned PDFs** (on or off, and the languages), and the embedding model for **search by meaning** (with *Download nomic-embed-text* when Ollama has none). |
| **Technical** | **AI model per task** ([Which model does what](models.md)): the model of each kind of task, what it steps up to, the helper on Claude Code, *Use the recommended models*, *The recommendations follow* your plan, and for local servers the small model for labels and links. With a local model, the **model for second opinions** and the **context length** (automatic by default), with *Sort the best excerpts again by wording* (off). **Repeatable results**: the seed (42 by default) and a test of whether the server gives the same answer twice. *Test a model* ([how](local-models.md#test-a-model-before-trusting-it)). **Updates** (*Check for updates*, how this copy was installed), **Your link to Margin** (*Copy my link*: the link with this run's key, for a bookmark; it works until Margin stops, and opens Margin for whoever has it, see [Privacy](privacy.md#what-goes-where)), where your data is, *What was sent to Claude*, **Which new versions to offer** and **Copy technical details**. |

### Another cloud provider (with an API key)

The last main choice in *Settings → AI*, after Claude Code, a model on this computer, the offline demo and the Claude
API, is **Another cloud provider (API key)**: OpenAI, Google Gemini, Mistral, Azure OpenAI or OpenRouter, each reached through
its OpenAI-compatible chat API, over HTTPS only. It needs *Allow cloud models* (as the Claude API does), and is refused
where cloud models are switched off for good (`--local-only`).

- **The key.** Enter one per provider and press *Save*. It goes into the system's keychain (macOS Keychain, Windows
  Credential Manager, `secret-tool` on Linux; or a file only you can read where there is none), never into
  `settings.json`, a log, an error message, the record of how an answer was made, or a *Move Margin to another
  computer* file. The page shows only whether a key is stored; *Forget* removes it.
- **The model.** Pick it from the provider's list. For Azure, type the deployment name and give the resource address
  (for example `https://my-resource.openai.azure.com`). An optional smaller model answers labels and links, the kinds
  a small local model takes; the chosen model answers everything else.
- **Not yet measured.** Margin's default models and routing were measured on Claude only, and the page says so for
  these providers. Claude's thought modes (*Energy efficient*, *Balanced*, *Intelligence*) stay Claude only.
- **Who may read what.** Nothing goes to a provider until a document allows it: [Other cloud
  providers](privacy.md#other-cloud-providers). Its own terms decide what it keeps; check them.

Old links to a section (`#/settings/second`, `#/settings/calibration`…) open its tab.

## Trying new versions early

Margin offers full releases only, by default. From 0.16 on, a **release candidate** (a try-out of the next version)
comes out at least a week before each new version. To be offered candidates, choose *Try new versions early*
under *Settings → Technical → Which new versions to offer*; *Stable (recommended)* goes back. A copy installed from
git follows its branch and has no such choice.

> [!WARNING]
> Try a candidate on a project you do not share with colleagues: going back to the stable version can show sync
> clashes on what the candidate made (nothing is lost).

## Reporting a problem

*Settings → Technical → Copy technical details* copies a few lines for a problem report: the Margin version, how it
was installed, the system and Python, the AI route, whether cloud models are switched off, and the update channel.
Never a path, a project or document name, or a key. *Report a problem* opens a short form on GitHub (a free GitHub
account is needed) to paste them in; please paste no text from documents that must stay private.

A **security or privacy problem** is reported privately instead: see [SECURITY.md](../../SECURITY.md).

## For whoever installs Margin

- **The AI.** A new installation uses Claude Code on the researcher's own plan. To use a model on this computer
  instead, choose it once in *Settings → AI* (or let *automatic* find Ollama or LM Studio) and press *Save and test*;
  with Ollama running, *Download qwen3:8b* there gets a model without a terminal. An installation that already chose a
  local model keeps it when it is updated. With an embedding model set (*Settings → Documents*), new documents are
  indexed for search by meaning right away.
- **Nothing may ever leave the computer.** Start the app with `margin-gui --local-only`, set `MARGIN_LOCAL_ONLY=1`,
  or create an empty file named `local_only` in the data folder. The cloud options (the Claude API and Claude Code)
  are then hidden, the default becomes the local model (*automatic*), the app and its API refuse to switch to them,
  Margin never starts Claude Code, and the connector refuses to hand out queued tasks.
- **Backups.** Keep the data folder (`--home`) somewhere that is backed up: it holds the projects, their results and
  the settings.
- **The icon.** Install with the one-line install ([Install](install.md)): it makes the icon. With
  `MARGIN_LOCAL_ONLY=1` and `MARGIN_HOME=<folder>` before `sh`, both are built into the icon. From a git copy, make
  the icon with `margin-gui --make-launcher`, with the same `--home` and `--local-only` you would start it with.
- **Scanned PDFs** need Tesseract ([Install](install.md#scanned-pdfs-optional)). Settings shows whether it is
  available.
- **Starting it by hand**: `margin-gui` and its options are in [The command line](command-line.md#the-app).
