[Manual](../MANUAL.md) › Settings

# Settings, and setting Margin up for others

> **In short**
> - *Settings* has five tabs: **AI**, **Checking**, **Documents**, **General** and **Technical**.
> - Every change saves as you make it: the right end of the tabs says *Saving…*, then *Saved*. There is no Save button.
> - The version of Margin is in the line under the title of every tab; click it to look for updates.
> - Whoever installs Margin for others can make sure nothing ever leaves the computer.

## The five tabs

<img src="../images/manual/settings-ai.png" alt="Settings, the AI tab" width="800">

| Tab | What you set there |
| --- | --- |
| **AI** | **Which AI reads your documents**, four cards in two rows. In the cloud: **Subscription** (an agent on a plan you already pay for: Claude Code, Codex or Antigravity; [below](#subscription-claude-code-codex-or-antigravity)) and **API key** (the Claude API or another provider, billed per use; [below](#an-api-key-claude-or-another-provider)). On this computer: **Local model** and **No AI (demo)**. Under the cards, only the chosen one's set-up: whose plan and its set-up card; the provider and its key; or what is chosen for this computer, *Install Ollama* (or *Start Ollama*) when no model server runs and *Download qwen3:8b* when none is installed. *Test the connection* (local model, API key) says whether the AI answers. Then, on a cloud AI: **How the AI works** (*How much thought*; *Helpers at once* with an agent; *Let the auditor use Fable* with Claude Code or the Claude API), **Documents only a local AI may read** (the local model for them; with an agent and that model, *Sharing the work* and *At your plan's usage limit*: [Which model does what](models.md#the-mix-of-local-and-claude)), **Your Claude account and your documents** (Claude Code, the Claude API) and **Work waiting for** the agent (what waits, in order: *Do first*, *Hold*, *Remove*; [Claude Code](claude-code.md#following-the-work)), shown with an agent or while work waits. Every choice saves as soon as you make it; one that sends text off the computer asks first. The server, the model's name and reasoning of a local model, and the models of a provider, are under **Technical**. |
| **Checking** | **Strictness**: how sure the AI must be before a judgement counts (its help mark explains it). It saves when you let go of the slider, applies to every result, and reports which answers and counts changed; *Back to normal (60%)*. Under it, **how often you agreed with the AI, by its certainty**: a small chart from the excerpts you judged, and after 20 judgements perhaps a suggestion ("When the AI was at least 70% sure, you agreed with it in 85% … *Use 70%*"). **How new checks start**: other words, parts, how many excerpts to read, and at most how many from one document; each check can still change them under *More options*. |
| **Documents** | **Reading scanned PDFs** (on or off, and the languages). **Search by meaning**: on or off, whether a model is set up, and *Download nomic-embed-text* when Ollama has none; it is set up per project on the Documents page, and the model and its server are under *Technical*. **Exploring**: the codebook of *By document* and how many themes a new set looks for (in a team project whose owner chose a default codebook, that one holds there, and its help line says *This project uses the team’s default*; your setting still holds in your other projects), and *Open Codebooks*, the page where you make, change and remove codebooks ([Make your own codebook](codebooks.md)). |
| **General** | **Notifications**: a notification from your computer when work you started that took more than 20 seconds has finished, or stopped with a problem, so you can close the browser while a local model works (Margin keeps working; a click on the notification opens it again). *When Margin is not in front* (the default) sends one only when no Margin tab is the one you are looking at; also *Always* or *Never*, and *Send a test notification*. On a Mac, the first one asks whether Margin may send notifications (System Settings › Notifications › Margin). **Updates**: your version and how this copy was installed, *Check for updates*, *What's new*, **Which new versions to offer** (*Stable* or *Early*, [below](#trying-new-versions-early)) and, while an update waits in its place, *Quit Margin*. **Your data**: the data folder, your projects (*Manage projects*) and *What was sent to Claude* (a CSV of the open project). **Help**: *Copy technical details*, *Report a problem (on GitHub)* and *Source code (on GitHub)*. |
| **Technical** | Each card is one line until you open it: its name and its current value (*Seed 42*, *The recommended models*); a card you opened stays open while Margin runs, and a link to one opens it. **The local model** and the provider's models (with a model on this computer, or another provider). **AI model per task** ([Which model does what](models.md)): a table of the model of each kind of task, what it steps up to and your choice (each saves when changed), the helper on Claude Code under the task, *Use the recommended models*, *The recommendations follow* your plan, and for local servers the small model for labels and links. With a local model, the **model for second opinions** and the **context length** (automatic by default), with *Sort the best excerpts again by wording* (off). **Search by meaning: the model**: the server kind, the embedding model and its address. **Repeatable results**: the seed (42 by default) and a test of whether the server gives the same answer twice. *Test a model* ([how](local-models.md#test-a-model-before-trusting-it)). **Your link to Margin** (*Copy my link*: the link with this run's key, for a bookmark; it works until Margin stops, and opens Margin for whoever has it, see [Privacy](privacy.md#what-goes-where)). **This installation**: the version, how it was installed and is updated, the network, and the text-recognition parts and what is missing. |

### Subscription: Claude Code, Codex or Antigravity

The first choice answers on a plan you already pay for, with no API key. Its card names three agents, and you pick one
inside it. Each carries a mark where it fits.

| Agent | Your plan | Mark |
| --- | --- | --- |
| **Claude Code** | A Claude plan (Pro, Max, Team) | *Recommended* |
| **Codex** | A ChatGPT plan (Plus, Pro, Business) | |
| **Antigravity** | A Google account, free or paid; free: every task on Gemini 3.8 Flash | *For a free plan* |

Choosing Codex or Antigravity asks first, naming the company that then receives the passages inside the tasks, as
Claude Code does; the yes is the choice, saved at once, and a no keeps the agent you had. *Set up Codex* (or *Set up
Antigravity*) opens guided steps: install, sign in, add Margin ([Codex and Antigravity](other-agents.md#set-it-up-once)).
The card then shows what is found, signed in and added. A line says the agent is **not yet measured with Margin**.
*How much thought* and *Helpers at once* are in the card below it, and the **models in use** per tier in *Settings ›
Technical › The provider's models*. Claude Code's own set-up, checklist and speeds are in [Claude Code](claude-code.md).

### An API key: Claude or another provider

The second card in the cloud row, **API key**, reads with a key billed per use: **Claude**, marked
*Recommended* as the only provider measured with Margin, or OpenAI, Google Gemini, Mistral, Azure OpenAI or OpenRouter,
each reached through its OpenAI-compatible chat API, over HTTPS only. Picking the card, or another provider inside it,
asks first: the dialog names the company the excerpts go to, says the use is billed to the key, that only documents
that allow that provider are sent and, for the providers other than Claude, that it is not yet measured with Margin.
The yes allows cloud models and saves the provider at once; the safe answer keeps what you had. Nothing is sent before
a key is stored. It is refused where cloud models are switched off for good (`--local-only`).

- **The key, in guided steps.** Each provider has its own: pick it among the option cards (each shows *Key stored* once
  one is) and press *Set up OpenAI…* (or its name). A window leads you one step at a time: make an account (the
  address to open is shown to copy, not a link), add credit or a plan with API access where the provider needs one, make
  a key, and paste it. Where a key is made: [OpenAI](https://platform.openai.com/api-keys), [Google AI
  Studio](https://aistudio.google.com/apikey), [Mistral](https://console.mistral.ai/api-keys),
  [OpenRouter](https://openrouter.ai/keys); Mistral's billing is at
  [admin.mistral.ai](https://admin.mistral.ai/organization/billing); Azure's key and address are in the
  [Azure portal](https://portal.azure.com) after you deploy the models in [Microsoft Foundry](https://ai.azure.com). The
  key goes into the system's keychain (macOS Keychain, Windows Credential Manager, `secret-tool` on Linux; or a file only
  you can read where there is none; the page says which), never into `settings.json`, a log, an error message, the record of how an answer was
  made, or a *Move Margin to another computer* file. The page shows only whether a key is stored: *Change the key…* opens
  the window at its paste step, *Forget the key* removes it. Two things to know first: a ChatGPT plan pays for
  Codex (above), not for OpenAI's API, and on Google's free tier Google may use what is sent to improve its
  products, except in the EEA, Switzerland and the UK, where its paid terms apply to all use. The Claude API
  ([key page](https://platform.claude.com/settings/keys)) has the same steps.
- **Recommended models, applied automatically.** Margin picks three models from the provider's own current line-up,
  among the models your key may use: one for small tasks (labels and links), one for judging excerpts, one for second
  opinions and hard cases. *Settings › Technical › The provider's models* shows them, *Recommended* or *Your choice*;
  choose another from the list only if you need to (the first entry, *Recommended*, goes back). A newer Margin brings
  newer models by itself. Azure has no list: type the names of your three deployments, with the recommended names as a
  hint ([the line-ups](models.md#the-recommended-models-of-each-provider)); Azure's endpoint is on the AI tab, under its key.
- **How much thought.** *Energy efficient*, *Balanced* and *Intelligence* work for every provider and agent: one model
  tier lower or higher, and less or more reasoning effort where the model takes it
  ([Which model does what](models.md#how-much-thought)).
- **Not yet measured.** Margin's default models and routing were measured on Claude only, and the page says so for
  these providers.
- **Who may read what.** Nothing goes to a provider until a document allows it: [Other cloud
  providers](privacy.md#other-cloud-providers). Its own terms decide what it keeps; check them.

Old links to a section (`#/settings/second`, `#/settings/calibration`…) open its tab.

## Trying new versions early

Margin offers full releases only, by default. From 0.16 on, a **release candidate** (a try-out of the next version)
comes out at least a week before each new version. To be offered candidates, choose *Early* under
*Settings → General → Which new versions to offer*; *Stable* goes back. A copy installed from git follows its branch
and has no such choice.

> [!WARNING]
> Try a candidate on a project you do not share with colleagues: going back to the stable version can show sync
> clashes on what the candidate made (nothing is lost).

## Reporting a problem

*Settings → General → Copy technical details* copies a few lines for a problem report: the Margin version, how it
was installed, the system and Python, the AI route, whether cloud models are switched off, and the update channel.
Never a path, a project or document name, or a key. *Report a problem* opens a short form on GitHub (a free GitHub
account is needed) to paste them in; please paste no text from documents that must stay private.

A **security or privacy problem** is reported privately instead: see [SECURITY.md](../../SECURITY.md).

## For whoever installs Margin

- **The AI.** A new installation uses Claude Code on the researcher's own plan. To use a model on this computer
  instead, choose *Local model* once in *Settings → AI* (it finds Ollama or LM Studio by itself) and press *Test the connection*;
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
