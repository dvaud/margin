# Margin: write with your sources beside you

Margin is a research and paper-writing companion: it finds the claims in your draft that need a source, shows which of
your documents support or contradict each, checks that the sources you cite say what you say, and helps you explore
those documents and check a hypothesis against them, with every quote checked against the source. It runs on your
computer, with Claude on your own plan or a local model. It grew out of ENLENS, and can sit beside it.

## Install

1. **Paste one line.** On a Mac or Linux, open *Terminal*; on Windows, open *PowerShell*. Paste the line for your
   system and press Enter:

   | System | Where | Paste this |
   | --- | --- | --- |
   | macOS, Linux | Terminal | `curl -fsSL https://github.com/dvaud/margin/releases/latest/download/install.sh \| sh` |
   | Windows | PowerShell | `powershell -ExecutionPolicy Bypass -c "irm https://github.com/dvaud/margin/releases/latest/download/install.ps1 \| iex"` |

   It needs no git, no Python and no administrator rights. When it is done, Margin opens in your browser, and its
   icon is with your other programs. **Or download a file and double-click it:**
   [Install-Margin-Windows.cmd](https://github.com/dvaud/margin/releases/latest/download/Install-Margin-Windows.cmd)
   on Windows,
   [Install-Margin-macOS.zip](https://github.com/dvaud/margin/releases/latest/download/Install-Margin-macOS.zip)
   on a Mac. Windows and macOS ask you to allow it the first time:
   [how](docs/manual/install.md#or-download-a-file-and-double-click-it).
2. **Press *Set up Claude*** on the first screen. It installs Claude Code if it is missing (it shows you the command
   first), opens a window where you sign in once with your Claude plan, and connects Margin to it.
3. **Bring your ENLENS projects, or start a new one.** If ENLENS is on this computer, the first screen offers to copy
   its projects into Margin (ENLENS keeps its own). Otherwise name a project and add your documents (PDF, Word, web
   pages, text, or a zip of them). Margin asks who may read them with AI: *Claude may read them*, *Only a local AI*,
   or *No AI*.
4. **Check a draft, explore, check.** Where AI work waits, press **Start Claude Code**; the results appear as they
   come in.

No Claude plan? Choose *A model on this computer* on the first screen. Used Margin on another computer? Choose
*Import from another computer*. Every option: [Install and update](docs/manual/install.md) in the manual.

## Update

1. Type `margin update` in Terminal or PowerShell, or run the install line or file again (on Windows, quit Margin
   and close Claude Code first).
2. Quit Margin (*Quit* at the bottom of the sidebar, or *Settings* › *Technical*) and open it again from its icon.

Margin also tells you when a new version is ready; *Update and restart* in its pop-up does both steps for you. Your
projects and settings (the `margin` folder in your home folder) are never touched.

## What Margin does

- **Check a draft**: the statements in your text that need a source, and the documents that support or contradict
  each one, with what you could cite.
- **Check citations**: whether each source you cite says what your sentence says.
- **Outline** and **Find literature**: a writing plan made from the themes of your documents, and works to cite for
  what no document supports yet. Neither uses AI.
- **[Explore your documents](docs/manual/explore.md)** before you claim anything: skim one document, every place a
  word occurs, the codes each document addresses (your own codebook or a built-in one), a glossary, a concept map,
  themes.
- **[Check a statement against them](docs/manual/check.md)**: supported, partly supported, contradicted or mixed
  evidence, with the words of each source and every quote checked against the source text.
- **[Review the AI's judgements](docs/manual/review.md)** as you would a co-coder's: your judgements count, and the
  Excel download keeps them next to the AI's.
- **[Keep your bibliography beside your documents](docs/manual/bibliography.md)**: bring in a Zotero collection or a
  reference file, and see which works you have and which you still need to find.
- **[Use a model on your own computer](docs/manual/local-models.md)**, or no AI for some documents.

<!-- new-in:start (written by `python tools/release.py prepare`: change the changelog entry, not this) -->
## New in 0.17.2: Codex, Antigravity and other cloud providers, and a local model that waits for you

- **More AIs to choose from.** Codex and Antigravity answer the queue on your own plan as Claude Code does, and *Another cloud provider* (OpenAI, Google Gemini, Mistral, Azure OpenAI, OpenRouter) works with an API key.
- **Your local model starts only when you press its Start**, has its own panel wherever it has work, and only *suggests*: you judge what it read, or press *Judge it myself* instead.
- **Settings in five tabs** (AI, Checking, Documents, General, Technical), and every change saves as you make it.
- **The concept map grows:** named groups (the AI can draft the names, on request), zoom, links that *need*, *shape* or *clash with*, and pictures to download.
- **Research log is a place in the sidebar**, with an **AI log** under it: which AI work sent what, to which provider.
<!-- new-in:end -->

How it works, in the manual: [Explore your documents](docs/manual/explore.md),
[Codebooks](docs/manual/codebooks.md) and [How documents are read](docs/manual/how-documents-are-read.md). Every
release, with what came from ENLENS and what was not tested: [CHANGELOG.md](CHANGELOG.md).

## Privacy and your documents

Your documents, results, judgements and settings stay on your computer. With Claude (the default), only the passages
inside the AI's tasks are sent to Anthropic, through Claude Code on your own Claude plan (or the Claude API, when you
switched it on), and only from documents and drafts marked *Claude may read it*; Margin records every passage it sends
(*Sent to Claude* on the *Documents* page), and *See what is sent* shows a batch word for word before it goes. To keep
a document from Claude, mark it *Only a local AI* or *No AI*. To keep everything on the computer, choose *A model on
this computer* in *Settings → AI*, or put `MARGIN_LOCAL_ONLY=1` before `sh` in the install line, which removes every
cloud option for good. *Find literature* sends only the search words you have seen to OpenAlex. Apart from that, the
AI you chose and looking for a new version on GitHub, Margin sends nothing anywhere on its own and has no telemetry.
The details: [Privacy](docs/manual/privacy.md) in the manual and [docs/PRIVACY.md](docs/PRIVACY.md).

## Documentation

- [The manual](docs/MANUAL.md): a one-page start, then a short page per task.
- [How Margin works, for a methods section](docs/METHODS.md), and [what leaves the computer](docs/PRIVACY.md).
- [Which model each task needs](docs/MODEL_CHOICE.md) and [the app's HTTP API](docs/API.md).
- Add-ons: [building an app on Margin](docs/EXTENDING.md), with an add-on's own [manual](docs/ADDON_MANUAL.md) and
  [API](docs/ADDON_API.md).
- [What changed in each release](CHANGELOG.md) and [what comes next](docs/ROADMAP.md).

## For developers

A git copy, the tests, the layout of the code and how a release is made: [docs/DEVELOPING.md](docs/DEVELOPING.md).
