[Manual](../MANUAL.md) › Troubleshooting and limits

# Troubleshooting and limits

Find your problem by topic: [Install and update](#install-and-update) · [The icon and the app](#the-icon-and-the-app) ·
[Claude](#claude) · [Local models](#local-models) · [Documents](#documents) · [Projects](#projects) ·
[Claude Code and the queue](#claude-code-and-the-queue) · [Limits](#limits). Still stuck? [Report a problem](settings.md#reporting-a-problem).

Two files in the data folder (`~/margin` unless you chose another) often say why: `logs/margin.log` (the app) and
`logs/update.log` (updates).

## Install and update

| Problem | Fix |
| --- | --- |
| The install line stops with "does not match the release's checksum" | The download was cut off or changed on the way; nothing was installed. Run the line again later. |
| The install line on Windows says *Margin cannot be replaced while these programs run from its folder* | Margin or Claude Code is still running (Claude Code keeps Margin connected, which runs Margin's own Python). Choose *Quit Margin* and close Claude Code: the Claude app and every terminal or editor where it runs. The line goes on by itself once they have closed; nothing was changed before. If one does not close, end it with the `Stop-Process` line it shows. |
| The install line on Windows says uv could not install Margin, "Access is denied" | A program still used Margin's folder (the lines of Margin 0.14 and earlier did not wait for it). Quit Margin, close Claude Code and run the line again. |
| On Windows, every `margin` command says "uv trampoline failed to canonicalize script path", and the icon does nothing | An install of Margin 0.14 or earlier ran while Claude Code had Margin connected and left Margin's folder half removed. Close Claude Code and run the install line (or *Install-Margin-Windows.cmd*) again: it installs Margin whole. Your projects were not touched. |
| The install on Windows says "Margin was installed, but C:\Users\…\margin.exe is missing", with odd letters in the name | Your user folder has a letter with an accent (C:\Users\Dávid), which the installers of Margin 0.14 and earlier misread. Run the install line or *Install-Margin-Windows.cmd* of a later Margin: it installs over the half-done copy and makes the icons. |
| macOS says *Install Margin.command* was "Not Opened" | The file is not signed by an Apple developer. Click *Done*, then allow it once in *System Settings → Privacy & Security → Open Anyway* ([Install](install.md#or-download-a-file-and-double-click-it)), or paste the install line in Terminal instead. |
| Windows says it protected your PC, or the browser calls *Install-Margin-Windows.cmd* uncommon | The file is not signed. Keep it, then *More info → Run anyway*, or paste the install line in PowerShell instead. |
| There is no *Update* button in the sidebar | It shows only when there is an update. To look now, or to see why a look failed: *Settings → Technical → Updates → Check for updates*. |
| *Update* says it cannot update | It says why. Offline: try again later. Files of a git copy edited by hand: keep them with `git stash` (or undo them), then update. One-line install on Windows, Margin 0.14 and earlier: choose *Quit Margin* and run the install line again in PowerShell. |
| On Windows, a note says *The update to … did not finish* | Margin closed to install the new version but could not. Most often Claude Code still had Margin connected: close Claude Code, then press *Update* again. The details are in `logs/update.log`. |
| Settings shows an older version after updating | That copy was still running. Choose *Restart now* on the notice at the top of the page, or *Quit Margin* and open Margin from its icon. |
| The page keeps saying *Starting Margin …* | After 90 seconds it says Margin did not come back: open it again from its icon (or with `margin-gui`), and look in `logs/margin.log` for the reason. |

## The icon and the app

| Problem | Fix |
| --- | --- |
| Double-clicking the Margin icon does nothing | Look in `logs/margin.log`. Run the install line again (one-line install), or `margin-gui --make-launcher` again after moving or reinstalling Python (git copy). On macOS, if the icon was copied from another computer, right-click it and choose *Open* once. |
| The icon is a blank square (macOS) or a plain shortcut (Windows) | It was made without its picture. Open Margin once: it gives the icon its picture (on macOS, if Finder still shows the blank one, `killall Finder`). Or make the icon again: `margin-gui --make-launcher`. |
| On Windows, black windows flash open and closed while Margin runs, taking the focus | Margin 0.14 and earlier started Claude Code, Tesseract and its updates in windows of their own. Update Margin. |
| "The original file is no longer at …" | The file was moved or renamed after it was added; the app still has its text. Put it back, or add it again. |
| On Windows, removing a project says "a file in it is still open" | Another program still has a file of the project open: a sync tool (OneDrive, Dropbox), a search index or an antivirus check. Wait a moment and try again. Margin 0.14 and earlier held the project open itself on Windows, and removing it failed with an error: update Margin. |

## Claude

| Problem | Fix |
| --- | --- |
| *Set up Claude* cannot install Claude Code | No network, or the installer was blocked. Install it with Anthropic's set-up page (linked under *Technical details*), then press *Set up Claude* again. |
| *Set up Claude* keeps waiting for the sign-in | Finish signing in in the window it opened (and in the browser page that window opened), then press *I have signed in*. No window? Open Terminal or PowerShell, type the line the page shows (it goes to an empty folder of Margin, then starts `claude`), and sign in. |
| Claude Code answers with the wrong Claude account | The sidebar card (hover *Claude, on your plan*) and *Settings → AI* name the account it uses. To switch, type `claude auth logout` in Terminal or PowerShell, then press *Check again* and *Set up Claude* in *Settings → AI*: the sign-in window opens, and you sign in with the other account. |
| Nothing happens after pressing an AI button | Work waits for Claude Code: press *Start Claude Code* ([Claude Code](claude-code.md#start-claude-code)). |
| "No Claude API key" | Export `ANTHROPIC_API_KEY` or enter it in Settings, or use a local model or the file queue. |
| "Cloud models are switched off" / "Allow cloud models first" | The Claude API sends the passages read to Anthropic, so the app asks you to allow it first (*Settings → AI*). |
| "The Claude API rejected the key" | Copy the key again from console.anthropic.com, and check it has credit. |

## Local models

| Problem | Fix |
| --- | --- |
| "No local model server is running" | Start Ollama (or `ollama serve`) or LM Studio's server; `margin detect` lists what is found. Or choose `--backend baseline` / the offline demo to try things out. |
| The app says it cannot reach Ollama | Start the Ollama app (or `ollama serve`) and check the address in Settings (default `http://localhost:11434`). |
| "Ollama has no model …" | Download it: `ollama pull <model>`, then pick it again in Settings. |
| "The local server … has no model" | Load the model in LM Studio, start llama.cpp with it, or name another with `--model` or in Settings. |
| *Test connection* warns about Ollama's cloud | The model runs on Ollama's servers, which do not support the JSON format the app needs, and the text leaves your computer. Pick a model downloaded with `ollama pull`. |
| "This task needs about N tokens of context" | Set the context length to automatic in *Settings → Technical* (the default), or raise it (`--num-ctx`). 16,384 covers every task of the app. |
| A check with a local model takes very long | The progress panel shows where the time goes. A long "loading the model and reading the prompt": the model is too large for the memory (check Activity Monitor) or the computer is swapping. A long "reasoning": set *Reasoning* to off. |
| A check with reasoning takes half an hour | Set *Reasoning* to *Only when judging excerpts* with a budget (1,500 tokens is the default; lower it for a slow computer). |
| "… sent nothing for 600 seconds" | The model did not start or stopped answering: usually too little memory. Close other apps or choose a smaller model. |
| "… used its whole allowance … on reasoning" | The model kept reasoning without answering. Give reasoning a budget (*Settings → AI*, the default 1,500 tokens), choose *Only when judging excerpts*, or set it off. |
| "… got stuck writing blank space" | A known failure of some models with fixed-format answers. It counts as one failed try of that task (and so does an answer cut off at the length limit): it is asked again, and the check goes on with its other parts. If it keeps happening, set *Reasoning* to off or choose another model. |
| Excerpts wait with *Waiting for your local model* | Too little memory was free to start it ([Privacy](privacy.md#the-local-model-and-your-computers-memory)). Close programs and press *Read them now on this computer*, or choose a smaller model. |

## Documents

| Problem | Fix |
| --- | --- |
| An empty document, or *Scanned: no text* | No text layer (a scanned PDF). Install Tesseract ([Install](install.md#scanned-pdfs-optional)) and add the file again, or run OCR yourself (`ocrmypdf in.pdf out.pdf`). |
| A document reads badly | Look at its *Reading* panel and fix it with *Leave out*, *Restore*, *Text starts here* or *Text ends here* ([How documents are read](reading.md#the-reading-view)). For a text file, add the PDF instead if you have it. |
| An error about vectors of different sizes | The embedding model changed since search by meaning was set up: on the Documents page, press *Set up search by meaning* (or run `margin --ws FOLDER embed`). |
| "Remove all documents" is refused | The project was copied from ENLENS and holds results of its SDG pack (extracted claims, VCA verifications). Remove documents one by one, or run `margin --ws FOLDER reset-corpus --yes` if you mean it. |

## Projects

| Problem | Fix |
| --- | --- |
| *Import a project (.zip)* refuses the file | A damaged zip, or one whose database cannot be read, is refused with a plain message and leaves nothing behind. Make the zip again with *Download as a zip* ([Projects](projects.md#download-a-project-as-a-zip)). |
| There is no *Bring it over* button | Margin shows it only when it finds ENLENS projects in `~/enlens` (or the folder in `ENLENS_HOME`). Check where ENLENS keeps its data, or import a project zip instead ([Projects](projects.md#bringing-projects-over-from-enlens)). |

## Claude Code and the queue

| Problem | Fix |
| --- | --- |
| Many quotes fail | Look at `results.errors_json`. Usually the model tidied the PDF text; the retry prompt tells it to copy exactly. |
| Tasks stuck as `exported` | `margin requeue KIND`. |
| Two workers' answers ended up in one results file | Give each worker its own scratch folder. Move the stray lines to the right file; `import-results` accepts any order. |

## Limits

What Margin cannot promise, and how to work with it:

- **Judgements and claims are model output until reviewed.** The quote check proves the quoted words exist; it does
  not prove that the judgement or the claim's fields follow from them.
- **"Nothing found" is about the passages read, not the documents.** A check reads the top `k` passages per part per
  round (search by meaning narrows the gap). Read more passages or search with other words. In the pilot, a search by
  hand of the full cited documents for 10 claims with no graded passage found partial support for 2 and a weak
  contradiction for 1; the other 7 had nothing anywhere in their sources. Retrieval misses some evidence, mostly where
  the source uses other words ("repurposing" for "upgrading").
- **The corpus is what you provide.** Margin knows only the documents in the project.
- **Reading has limits.** The text comes from the PDF text layer. Tables and figures are read as text, which is often
  garbled; scanned pages need text recognition; the words inside charts and diagrams are set aside. Check a
  document's *Reading* panel ([How documents are read](reading.md#the-reading-view)).
