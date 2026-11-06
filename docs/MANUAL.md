# Margin: usage manual

Margin is a research and paper-writing companion grown from ENLENS (whose releases, 0.5 to 0.11.1, the version
numbers in brackets below refer to; Margin's own start at 0.1.0). It **checks your draft** against your documents
(section 3, *Checking a draft*), helps you **explore** your own documents and **check hypotheses** against them. Exploring comes first: every
place a word occurs, the codes of your codebook each document addresses, a glossary of terms
grouped into concepts you follow across documents, themes, references inside a document, highlighted copies. Most of
it needs no AI. When you have a statement that could be true or false ("Green hydrogen production increases water
stress in arid regions", "Remote work lowers commuting emissions in large cities"), Margin finds the passages of your
sources that bear on it, has a language model grade each one, verifies every quoted word against the source text,
and reports whether the sources support, partly support, contest or contradict the hypothesis, with the document,
page and quote behind every grade.

It is **subscription first** (0.9): the AI is Claude, through Claude Code signed in with your own Claude plan, which
Margin sets up and starts for you. Your documents, results and reviews stay on your computer; only the passages
inside the AI's tasks are sent to Anthropic. A model served on your own computer by Ollama, LM Studio, llama.cpp, Jan
or vLLM keeps every word on it, and the Claude API with a team key serves a shared installation. Whoever installs the
app can remove every cloud option for good (`--local-only`).

---

## 1. Install

**Coming from ENLENS.** Margin installs beside ENLENS: its own command (`margin`), data folder (`~/margin`,
`MARGIN_HOME`), address (`http://127.0.0.1:8766`), icon and Claude Code plugin (`margin-run@margin`, `/margin-run`).
On its first screen (and on the Projects page) *Bring them over* copies your ENLENS projects, codebooks and (on a
first start) settings from `~/enlens` (or `ENLENS_HOME`); from a terminal, `margin import-enlens [names]`. Each
project's database is copied with SQLite's backup; a project ENLENS uses in place from another folder is linked, so
both apps open it. ENLENS's folder is not changed. Quit ENLENS first if it is open. Margin opens ENLENS's project zips
and *Move to another computer* zips as they are.

**The one-line install (0.10).** No git, no Python and no venv of your own. Paste one line, and Margin ends up as an
icon in its usual place:

| System | Where | Paste this |
| --- | --- | --- |
| macOS, Linux | Terminal | `curl -fsSL https://github.com/dvaud/margin/releases/latest/download/install.sh \| sh` |
| Windows | PowerShell | `powershell -ExecutionPolicy Bypass -c "irm https://github.com/dvaud/margin/releases/latest/download/install.ps1 \| iex"` |

It says what it does in four steps: it gets **uv** (a small installer for Python programs, from Astral) unless it is
already there; downloads the Margin package of the latest release and checks it against the release's checksums
(`SHA256SUMS`); installs Margin with uv, which brings its own Python 3.12 and keeps it apart from any other Python on
the computer (no administrator rights); and makes the **Margin icon** (macOS: Applications and the Desktop; Windows:
the Start menu and the Desktop; Linux: the applications menu) and opens Margin. The package includes the connector,
faster search (numpy), pdfminer and the Python parts of text recognition, so no feature needs a later install. Then
press **Set up Claude** on the first screen (section 3, *First use*). Running the same line again installs the newest
release over this one (on Windows quit Margin first); your projects in `~/margin` stay as they are. Options go before
the line as environment variables: `MARGIN_LOCAL_ONLY=1` (nothing may leave the computer, built into the icon),
`MARGIN_HOME=<folder>` (another data folder, built into the icon), `MARGIN_VERSION=0.10.0` (that release).

**From a git copy (developers).** Python 3.10 or newer:

```bash
pip install -e '.[connector]'    # the app, the command line and the Claude Code plugin's connector (recommended)
pip install -e .                 # core only: pydantic, pypdf, openpyxl; the app and the command line
pip install -e '.[fast]'         # numpy: faster semantic search on large projects
pip install -e '.[anthropic]'    # the Claude API (cloud, opt-in)
pip install -e '.[ocr]'          # read scanned PDFs on this computer (also needs the program Tesseract, below)
pip install -e '.[dev]'          # pytest
```

**Scanned PDFs (optional).** A PDF page without a text layer is a picture of text. With the `ocr` extra and the
program Tesseract installed, Margin recognises the text of such pages on this computer, one page at a time, at low
priority and on one processor thread, so a local model working at the same time is not slowed down. Install
Tesseract with `brew install tesseract tesseract-lang` (macOS), `sudo apt install tesseract-ocr tesseract-ocr-nld`
(Debian/Ubuntu; one package per language) or the installer for Windows that the Tesseract project links to (UB
Mannheim). Since 0.10 Margin also finds Tesseract where these installers put it when that folder is not on the PATH
(Homebrew's folder for an app started from its icon, `C:\Program Files\Tesseract-OCR` on Windows), and notices a new
installation within a minute. Choose the languages in Settings (`eng+nld` for English and Dutch). Without Tesseract a
scanned PDF is listed as "Scanned: no text", and the app says how to get Tesseract on this system (after adding the
document, and in *Settings → Documents*). The one-line install brings the `ocr` extra; only Tesseract is separate.

**Updating.** `margin update` updates Margin the way it was installed (0.10). Installed with the one-line install,
it asks GitHub for the latest release, downloads its package, checks it against the release's checksums, installs it
over this one with uv and brings the Claude Code plugin up to date; on Windows, where a running program cannot
replace itself, it says to quit Margin and run the install line again (which does the same). The version you have
is at the top of every *Settings* tab; *Settings → Technical* says how this copy was installed. Installed from the git copy of Margin (`git clone …`, then `pip install -e .` in a
venv) every new version is also `margin update` (0.8.2): it fetches the version from GitHub into the same folder, reinstalls into the
same Python only when the requirements changed (with the extras already installed), refreshes the Claude Code
plugin if one was set up, and says to restart the app if it is running. It changes nothing if files of the copy
were edited by hand, and never touches the data folder. `margin update --check` only looks.

**Update Margin in the app (Margin 0.2.1).** *Update Margin* at the bottom of the sidebar does the same as `margin update`
without a terminal: it looks for a new version (the latest release, or new commits for a git copy), says which one is
ready, and with *Update and restart* installs it and restarts Margin on the same address. The open page shows
*Starting Margin …* and opens the new version by itself; started from the icon, Margin is restarted the same way,
without a new browser tab. Anything still running (a check, documents being added) stops first, as with *Quit
Margin*, and the dialog says so. If the update fails, the reason is shown and nothing restarts. With the one-line
install on Windows it says to quit Margin and run the install line again (a running program cannot replace itself
there).

**Only when there is an update (0.13.6).** The button is not in the sidebar all the time any more. Margin looks for a
new version when the page opens, every two minutes after, and when you come back to a tab that was in the
background. When it finds one, a pop-up in the corner says which version (*Margin 0.13.7 is available*), with *Update
and restart* and *Later*, and the button appears at the bottom of the sidebar as *Update to 0.13.7*. *Later* puts the
pop-up away for that version; the button stays until you update. A look that fails (offline, files of a git copy
edited by hand) stays quiet. To look yourself, or to read why a look failed, use **Check for updates** in *Settings
→ Technical → Updates* (the version at the top right of every Settings tab opens it). For the one-line install,
Margin reads the newest version from GitHub's release page, which GitHub's limit of 60 questions an hour does not
count, so several computers in one office can look every two minutes.

**An icon instead of the terminal.** The one-line install makes it. From a git copy, run once, as the person who will
use the app:

```bash
margin-gui --make-launcher                     # add --home FOLDER and/or --local-only if the app is used that way
```

It puts an **Margin** icon on the Desktop (macOS: also an app in the user's Applications folder; Windows: also in the
Start menu; Linux: also in the applications menu). Double-clicking it starts Margin in the background, with no
terminal window, and opens it in the browser; double-clicking it again while it runs just opens it again. After an
update (`margin update`, `git pull`, the install line again), the copy still running is the old version: the icon
then quits it and starts the new one (0.10.2), unless a check or documents being added still run in it, in which
case it opens it and every page says *Margin X is installed, but Y is still running*, with a *Restart now* button
(0.13.1; before, *Quit Margin*);
the version label in Settings says the same. The icon's picture ships with Margin (0.10.2; before, it needed the
Python package Pillow, and without it the icon was blank); an icon made without its picture gets it the next time
Margin starts. If the
model service is Ollama on this computer and it is not running, the Ollama app is started too. The icon calls the
Python Margin was installed in, so another `margin-gui` earlier on the PATH (for example an old one in Anaconda)
cannot get in the way. **Quit Margin** at the bottom of the sidebar stops it (it asks first when a check is still
running). What the app would print goes to `logs/margin.log` in the data folder. On Linux desktops that ask for it,
right-click the Desktop icon and choose *Allow launching* once.

Check the install with the tests (about 15 seconds, no network):

```bash
pytest
```

A local model server: install [Ollama](https://ollama.com) and open it; the app then downloads a chat model with one
button (*Download qwen3:8b*, about 5 GB, 0.13.7), and with it, if you like, an embedding model for search by meaning
(nomic-embed-text). In a terminal it is `ollama pull qwen3:8b` and `ollama pull nomic-embed-text` (English) or
`ollama pull bge-m3` (many languages, so an English hypothesis also finds Dutch or French passages). Or start the
server of [LM Studio](https://lmstudio.ai) (Developer → Start server) with a model loaded. Section 5 helps choose.

The commands are `margin-gui` (the app), `margin` (or `python -m margin`; every command takes `--ws FOLDER`,
default `./workspace`) and `margin-mcp` (the connector).

---

## 2. Concepts

The app speaks plain language; the command line, the API and the code use the technical names. Both are listed.

| In the app | Technical name | Meaning |
| --- | --- | --- |
| Project | Project / workspace | A folder with `config.json` and `enlens.sqlite`. The app keeps its projects in `~/margin/projects` (or `MARGIN_HOME`); the command line works on any folder given with `--ws`. Both use the same format. |
| Document | Document | One source file (PDF, Word .docx, HTML, TXT or MD; zips are opened). Its text is stored once; every offset points into it. Its paragraphs and headings are kept, so a quote can be cited as "paragraph 6 of 8" (text and web pages) or "page 2, paragraph 3" (PDFs added from 0.6 on; older ones by page). Scanned pages can be read by OCR. |
| Excerpt | Passage | A run of whole sentences (up to about 1,100 characters, some 180 words) inside a document. Excerpts are what the AI reads. Reference lists and unreadable text are skipped. |
| Hypothesis | Hypothesis | What you check. Checked as written, or split into 2 to 5 *parts* that must all hold, each checked on its own. |
| Part | Claim | One statement that is checked: the hypothesis itself, or one of its parts. |
| Judgement | Grade / verdict | What the AI says about one excerpt: *supports*, *partly supports* (an important part is stated; something remains to be inferred), *contradicts* (`refutes`), or *not about this hypothesis*. With a quote and a certainty. |
| Your judgement | User verdict | Your own judgement of an excerpt. It replaces the AI's in the answer and the counts, always counts, and is kept next to the AI's. Agreeing with the AI is a review; choosing another judgement is a change. You can point to the sentence you mean. |
| AI certainty | Confidence | The AI's own estimate (0–100%) of how sure it is. It is not a check of whether it is right: high (≥ 80%), medium (≥ 60%), low. |
| Strictness | Threshold | How sure the AI must be for a judgement to count (default 60%). Weaker judgements stay visible, marked *not counted*. It applies to every result, old and new. |
| Search | Round | One set of excerpts read for a part. *Look for more evidence* and *Search with other words* add searches. |
| Search by meaning | Semantic index | Optional: a vector per excerpt from a local embedding model, so excerpts are found by meaning as well as by shared words. |
| About another group | Scope note | The AI's note that an excerpt is about another group, setting, place or period than the hypothesis names ("about fully remote workers, not hybrid"). Such an excerpt supports the hypothesis at most partly. |
| Second opinion | Model for second opinions | Another model that reads the same excerpts on its own, to show where it differs. Its judgements never change an answer. |
| Stronger model | Model routing (*Steps up to*) | The model a check steps up to: it reads the excerpts again and its judgements replace the first ones; the answer shows what it was at first. |
| Codebook | Framework | An optional list of codes a hypothesis can be tagged with (like codes in NVivo or Atlas.ti). Add your own as a CSV; the UN SDG targets and goals are built in as examples. The AI sees the code's text. |

### Answers

| In the app | Status | Meaning |
| --- | --- | --- |
| Supported by your documents | `supported` | At least one excerpt says what the hypothesis says (and counts), and none says the opposite. |
| Partly supported | `partially_supported` | No excerpt says it all, but one says an important part of it. |
| **Mixed evidence** | `contested` | Some excerpts support the hypothesis (fully or partly) and others contradict it. Read both sides: do they concern the same place, group or period? |
| Contradicted by your documents | `contradicted` | An excerpt says the opposite, and none supports it. |
| Only uncertain evidence | `uncertain` | Excerpts were judged, but the AI was not sure enough about any of them for your strictness. Judge them yourself, or lower the strictness. |
| No evidence found | `unsupported` | None of the excerpts read was about the hypothesis. This is not proof that no document says it: look for more evidence, search with other words, or add documents. |
| Nothing in your documents matched | `no_passages` | No excerpt shares words (or meaning) with the hypothesis. |
| The check did not work | `failed` | The AI's answers did not pass the checks three times. |

A split hypothesis combines its parts, which must all hold: a part contradicted → contradicted (even when other
parts are supported); otherwise a part with mixed evidence → mixed evidence; every part supported → supported; some
parts (partly) supported → partly supported; only uncertain evidence → only uncertain evidence; otherwise nothing
found. The app says which part decides ("Part 2 has mixed evidence, so the whole hypothesis has mixed evidence").
Parts whose check failed are left out (the result says it is incomplete).

**Who says what** lists the documents behind an answer by side. A document counts as supporting if one of its
counted excerpts supports, as partly supporting only if none supports, and as contradicting if one contradicts, so a
document can be on both sides (the app says so). The lean (−1 only contradicting, +1 only supporting) summarises the
excerpts read; it is not a measure of truth.

---

## 3. The app

```bash
margin-gui                 # opens http://127.0.0.1:8766 in your browser
```

Options: `--home FOLDER` (where projects, history and settings live; default `~/margin`), `--port 8600`,
`--headless` (do not open a browser), `--local-only` (no cloud option at all; see *For whoever installs the app*),
`--make-launcher` (the Margin icon, see section 1).
The app listens on this computer only and answers only to the page it served (a token per run). `--host 0.0.0.0`
exposes it to your network: the page then does not carry the token, so open the link the terminal prints (it ends
in `#token=…`), and only by IP address; do this only on a network you trust. Stop it with Ctrl+C or *Quit Margin*. Nothing is loaded
from the internet: no CDN, no fonts, no analytics.

The app is written for researchers who do not program: plain words on every working screen, model names and other
technical details only under *Technical details* and *Settings → Technical*. Each feature says, above its title,
which part of the app it belongs to (*Explore the documents* or *Check hypotheses*) and whether it uses the AI; in
the sidebar a filled **AI** mark means the feature needs the AI, a dashed one that the AI is optional, and no mark
that it never uses the AI (0.9). The marks are grey (0.13.3): green, amber, red and purple are kept for the
judgements and answers.

**One look on every page (0.13.3).** Every page follows the rules of the result page: a title and one short line
under it; a few type sizes, and bold only for headings and the page's main button; cards with a thin edge and no
shadow; a longer explanation behind a small **(?)** that opens on hover or click (what a passage is, what a second
opinion does, the auditor, how the AI labels passages); and downloads as one quiet line of links (*Download
Excel (.xlsx) · CSV*) instead of buttons. The *Overview* cards say what each feature does; hover a card for what it
is for.

**The sidebar (0.9).** *Overview* (the start page of a project), *Documents*, *Bibliography* (0.13), then **Explore the documents**
(Search, Profile, Concepts, Themes) and **Check hypotheses** (Check a hypothesis, Check several, Results). At the
bottom, under the line that says where text goes, *Settings*, *Theme*, *Update to …* (0.13.1; since 0.13.6 only when
there is an update) and *Quit Margin* sit together (0.10.1); every
*Settings* tab shows the version of Margin at the top right, and clicking it opens *Technical → Updates* (0.13.6:
*Check for updates*, then how this copy was installed under *Where your data is*). The *Overview* shows every feature with one line on what it does, whether it uses the AI and what is
already made in the project (a profile, a glossary, a set of themes, results), and the AI in use with what is left
to set up. *Quick look at one document* is there too.

### First use

The welcome screen has three steps (0.9). **The AI**: Margin uses Claude Code, signed in with your Claude plan. The
step shows a checklist (Claude Code on this computer, signed in, the Margin plugin added) and one button, **Set up
Claude** (0.10), that does every step still open, in order:

1. Claude Code is not on the computer: Margin shows the command of Anthropic's installer (`curl -fsSL
   https://claude.ai/install.sh | bash`, or `irm https://claude.ai/install.ps1 | iex` on Windows) and runs it when you
   choose *Install Claude Code*. It needs no administrator rights and takes a minute or two. *Anthropic's set-up
   page* is linked for doing it yourself.
2. Not signed in: Margin opens a Terminal (macOS) or PowerShell (Windows) window already running Claude Code. Sign in
   there with your Claude plan (it opens a page in your browser) and close the window; Margin checks every few
   seconds and continues by itself (*I have signed in* checks at once). Margin never sees your login. If no window
   can be opened, the page shows the line to type.
3. The plugin is not added: Margin adds it (as in 0.9).

*Set it up yourself instead* keeps the lines to type. *No Claude plan? Other options* offers a model on this computer
or no AI for now. **A model on this computer needs no terminal (0.13.7):** with no model server running, the step says
how to get Ollama (free, from ollama.com) and notices by itself when it starts; with Ollama running but no model yet,
*Download qwen3:8b* (about 5 GB) downloads one, with *Also nomic-embed-text* for search by meaning, a progress bar
and *Stop* (Ollama keeps what it has and goes on from there). Ollama fetches the model from ollama.com; none of your
documents are sent. The downloaded model becomes the AI and is tested at once. When whoever installed the app chose a
local model that answers, this step is skipped. Then name a **project**
(one per set of documents); used Margin on another computer before? *Import from another computer* brings every
project and the settings in one go (section 7). Then **add documents**: choose
files (PDF, Word .docx, HTML, text, Markdown, zip) or a folder. A Word file keeps its paragraphs, headings and the pages
Word marked (0.8); older .doc files are not read: save them as .docx or PDF. The list shows the
title read from each file and warns about unreadable text and very short files (often a landing page instead of the
report). *Open an existing Margin project folder (advanced)* links a project made with the command line, without
copying it.

The sidebar always says where text goes: *Claude, on your plan · Only the passages of AI tasks leave this computer*
(the default from 0.9), *Private · The AI runs on this computer* with a local model, or that excerpts are sent to the
Claude API if a shared installation allowed it (section 6). Hover that line, or reach it with the Tab key, for a
short card (0.13.4): on Claude Code it names the account Claude Code is signed in to (*Signed in to Claude Code as
you@university.nl*, *Team plan · University of Amsterdam*; the organisation only on a Team or Enterprise plan),
then where the text goes and where to change it. Escape closes it. *Settings → AI* names the account as well, under
*Signed in with your Claude plan*, and so does `margin claude-setup`. Margin reads it from Claude Code (`claude auth
status`); the login itself stays with Claude Code.

### Checking a hypothesis

Write one sentence that could be true or false and press *Check* (Ctrl+Enter). When it contains "and", "but" or a
semicolon, the app offers to **check each part separately**. *What happens when you check* explains the four
steps (search, read, verify, answer). *More options*: let the AI think of other words your documents might use,
tag the hypothesis with a code, and limit the check to some documents.

**Look before checking** shows first how the hypothesis will be checked: the parts the AI would split it into (with
*Check each part separately*) and the extra words it would search for. Change a part, remove one or add one; remove
search words that do not fit and add words your documents use; then *Check*. The result records that you set them.

While it runs, the panel shows each step as it finishes: the parts, the other words searched for, how many excerpts
from how many documents, the AI reading them; *Technical details* shows what the model is doing second by second.
Remarks about the round (excerpts of restricted documents read on this computer, or waiting for you) appear under
the steps. *Stop* ends the check and leaves nothing behind; with a model on this computer it also stops the model
while it is still reading the prompt (0.11.1). You can use the rest of the app meanwhile.

### Reading and reviewing a result

The page reads from top to bottom in four parts (0.12): the answer, the evidence, the other AI models, then notes and
downloads. *Technical details* and *Delete this result* close it. It keeps to a few type sizes; green, amber and red
are the judgements (supports, partly supports, contradicts) and purple is mixed evidence.

**The answer** is one card:

- the answer, and beside it who judged it: *judged by the AI*, *partly reviewed by you* or *reviewed by you* (hover
  it for the AI model);
- **who says what**: one row per document, with a coloured dot per side and where, e.g. *supports it: paragraph 9 ·
  contradicts it: paragraph 5*. A hypothesis checked in parts lists its parts instead, each with its answer and its
  documents for and against, under one line on which part decides the answer (*Part 1 decides the answer*; hover it:
  the hypothesis holds only if every part does). A document with excerpts on both sides counts once (*3 documents
  for, one of them also against*). Click a part to go to its evidence;
- at most one caution, when the answer is fragile: *It rests on a single document and on two excerpts you have not
  reviewed* (or one of the two; for a hypothesis checked in parts, only the parts that decide the answer count);
- documents added to the project since the check, when there are any, with *Read them* (a further search for this
  result; the check is not run again, so your reviews are kept);
- **Next to review**: it goes to the excerpts you have not reviewed, the judgements that count in the answer first
  (where a second opinion differs, or the AI flagged another group, before the others), then the rest, then those you
  only commented on. Past the evidence it goes on to the excerpts the AI found not about the hypothesis.

When the AI was too unsure to count any excerpt, the card says so in one sentence, and *Next to review* takes you to
them: your own judgement always counts.

**The evidence** has **Cards** and a compact **Table** (one row per excerpt, with your decisions; click a row to open
its card) beside its title, and two lines under it: how many excerpts count at your strictness (the (?) explains
strictness and offers *Try another strictness on this page*), and *Every quote is checked against its document; your
judgement overrides the AI's.* A hypothesis checked in parts shows each part under its own heading (*Part 1: …*) with
its own documents above its excerpts.

Each excerpt card shows, in this order: its judgement with at most two quiet facts (*Certainty: medium*; *Not
counted* and *Certainty: low* when it is below your strictness; *Second opinion: partly supports*, with its colour
dot; *You agreed with the AI*; *Your judgement (the AI said …)*); the document and where the quote is (*paragraph 6
of 8*); and the quote, highlighted in its judgement's colour, with one sentence before and after it (on a phone, the
sentence before it). A short heading that opens a paragraph of the document (*Recommendations.*) is shown as a small
heading above it (0.13.2). An excerpt read for another part too says *also in part 1*; hover it for your judgement
there. Cards that do not count come after those that do; cards you have judged sit back (no fill, a dashed edge). One
row of actions, the same on every card:

- **Agree** makes the AI's judgement yours (it then counts, whatever the AI's certainty); a note at the bottom says
  so, and whether the answer changed, with *Undo*. The card then says *You agreed with the AI*, and the button
  becomes **Take back**.
- **Not about this** dismisses the excerpt in one click (0.12): your judgement *Not about this* moves it to the
  excerpts that are not about the hypothesis, under the cards. *Undo* is offered.
- **Judge differently…** (*Edit judgement…* once you have judged; *Judge this excerpt…* when no AI may read it): the
  other judgements, each with its colour dot, under a line that says what your judgement is now (each saves at once,
  with *Undo*), a comment (saved on Enter or when you leave the field), and the sentence you mean when the AI
  highlighted the wrong one (select it in the excerpt, then *Use it*; or pick it from a list). Your judgement
  replaces the AI's in the answer and in the downloads, always counts whatever the strictness, and the card shows
  what the AI said. A comment without a judgement stays a comment: it is not a review.
- **In context** shows the whole excerpt the AI read, with *Open the whole document at this place* (by paragraph or
  page, the quote highlighted; *Back to the result* returns to the excerpt), *the original file* (a PDF at the page,
  a text file with the quote highlighted, a web page scrolled to the quote in browsers that support it) and *a
  highlighted copy* of the document (a PDF, or a web page for a text document), with this hypothesis's judgements
  highlighted.
- **Details**: *Ask the AI to read this again* (one excerpt, alone, with your comment as a hint; the card then says
  what it was and what it is now, and your own judgement still counts), the AI's certainty as a percentage, how the
  excerpt was found, and the technical facts (span, id, earlier judgements).

After a save, the card keeps its place on the screen and says where it moved in the list. *About another group* under
a quote means the AI thinks the excerpt is about another group, place or period than your hypothesis (fully remote
workers for a hypothesis about hybrid work): it then counts at most as partly supporting. Excerpts the AI found not
about the hypothesis are folded under the cards, so you can check those too.

Under the cards, **Read more excerpts** reads the next excerpts that match the same words; **Search with other
words** reads excerpts containing words you type (documents often say "telework" where the hypothesis says "remote
work"). New excerpts are marked *new*, a *Just now* line in the answer says what was found, and when everything that
matches has been read, the line above the buttons says so.

**Ask another AI model** says what has happened (what a second opinion found; that no stronger model is set, with
*Set one in Settings*), then has two buttons side by side (0.11.2); each button's tooltip says what it does, and the
(?) explains the difference:

- **Ask a stronger model** (*it replaces the AI's judgements; the answer can change*): the model checks step up to
  (on Claude the auditor, Opus or Fable) reads every search of the result again, once. Its judgements take the place
  of the first AI's. The answer then shows a small mark beside it, e.g. **Supported** *at first: partly supported*
  (hover or click it for which models and how many judgements changed), and each changed excerpt shows both readings.
  The same happens on its own when an answer was unsure or rejected twice. Your own judgements stay and count either
  way. When the AI chosen in Settings has no stronger model, the card says so, with *Set one* (Settings).
- **Get a second opinion** (*shown only for comparison: it never changes the answer*): another model (on Claude the
  auditor; with a local model, a second local model chosen there or in Settings) reads the same excerpts on its own.
  Each card then says *Second opinion: …* beside the AI's judgement, *Next to review* goes to the excerpts where it
  differs first, and when it points to another sentence, *Highlight the quote of: the AI / the second opinion*
  switches which quote is highlighted. With local models only one is kept in memory at a time, so this takes a while.

Add **notes** (saved as you type). **Download**, one link per file: *Excel (.xlsx)*: a *Summary* sheet (one row per
hypothesis: answer, answer per part, documents per side, excerpts counted and too uncertain, your reviews and
changes, notes, strictness, the AI model for a methods section) and an *Excerpts* sheet (every excerpt read:
judgement, judged by you or the AI, the AI's own judgement and certainty, counted or not, quote and who chose it,
document, where, your comment, the AI's note about another group, its earlier judgement when it read an excerpt
again, the second model's judgement when one was asked, the full excerpt); *Highlighted documents (.zip)*; *Whole
project (.zip)*; and *CSV · JSON (for programmers)*. *Technical details* has the strictness slider (this page only),
the models and settings of the check, what each search looked for and the AI's note on what it read.

A check still **waiting for Claude Code** shows only the waiting card (with *Start Claude Code*), any excerpts
already read, and your notes; the rest appears when the answer is in.

### Results and checking several

**Results** lists every hypothesis with its answer, the excerpts that count (and how many were too uncertain), tags
such as *part of a set*, *checked in 2 parts*, *N to review*, *N changed by you*, *has notes*, *N documents added
since*, *second opinion differs on N*, and the date; an answer a stronger model changed carries the small mark *was
partly supported* (or whatever it was at first). Search, filter by answer, open one, or download them all
(*Download all: Excel (.xlsx)*, with a *Map* sheet, or *CSV (for programmers)*, under *Show as a map*). *Read the new
documents for all N* brings every result with documents added since up to date in one go; *Get a second opinion for
all results* does the same for second opinions (for comparison only: the answers do not change; its (?) says more).

**Show as a map** shows all results (or one set) as a grid: one row per hypothesis, one column per document, and in
each cell + supports, (+) partly supports, − contradicts or ± both, with the number of excerpts that count. It flags
answers that rest on one document, and documents that *decide* answers (leaving them out would change those answers),
which are the ones to read most carefully.

**Projects** (the project menu → *Manage projects*): *Download as a zip* puts the whole project in one file (the
database, the documents and their original files, the codebooks) for a co-author or another computer; *Import a
project (.zip)* opens such a file as a new project. It also takes a project's folder zipped by hand (Finder's
*Compress*, Windows' *Send to compressed folder*; 0.2.1): its documents are pointed at the unpacked copies.
*Download the whole project (.zip)* is also on the Results page.

**Check several** checks many hypotheses one after the other: paste them one per line, or load a CSV with a column
`hypothesis` (or `claim`, `text`, `statement`) and optional `framework` and `code` columns. *Show the list* previews
what will be checked; *Check all N* runs them. A hypothesis that cannot be checked is listed and the next one is
checked; a problem with the AI stops the set and keeps what was done. The end screen lists each answer.

### Checking a draft (Margin 0.1)

**Check a draft** (sidebar, *Your writing*) is for what you are writing yourself: a section, a chapter or a whole
paper. Paste it or load it (Word, PDF, text, Markdown or a web page), and say who may read it with AI, as for a
document: *Claude may read it*, *Only a local AI*, or *No AI*. The draft is kept apart from the documents: it is never
used as evidence.

1. **Find the claims.** The AI reads the draft a few paragraphs at a time and marks the statements a reader would want
   a source for: numbers and trends, causes and effects, comparisons, what research found, general claims about the
   world, definitions and histories. It leaves out your own aims, methods, arguments and results, questions and
   headings. Each claim quotes its sentence exactly (the quote is checked against your draft like every other quote),
   is restated as one self-contained sentence ("it" replaced by what it stands for), and says whether your draft
   already cites a source there. Without AI (a draft marked *No AI*, or *Only a local AI* with no local model chosen)
   rules find the likely ones instead, and the page says so.
2. **Keep the ones you want checked.** *Dismiss claim* on one that is not a claim, *Reword* one before it is checked
   (what is checked is that wording), or select a sentence in the draft and press *Mark as a claim*. *Find again*
   finds the claims anew and keeps every one you checked, decided on, dismissed, reworded or marked.
3. **Check them.** Each claim is checked against all the documents as a hypothesis of its own (one claim, no
   splitting; AI search words only when the AI may read the draft). The draft then shows each claim coloured by its
   answer, and each card lists the documents that support it, partly support it or contradict it, with the best quote
   and its place, and what to do next ("cite them", "your documents disagree: cite both sides"). *Open the result*
   gives the full result page, where you review the excerpts as for any check.
4. **Decide on each claim (Margin 0.3).** Every card has three buttons: **Claim supported**, **Claim refuted** and
   **Dismiss claim**. You can use them before or after a check. The card then folds to what you need: its number,
   your decision, the claim, and what to cite (the documents that support it, or the ones that contradict it, or
   *Your draft cites a source here*); *More* opens it again and *Undo* takes the decision back. In the draft, the
   sentence loses its colour fill and gets an underline (green for supported, red for refuted) with a small tag
   **cite here** where the citation goes (*cited* when your draft already gives one); a dismissed claim is only
   dotted. Your decision belongs to the draft: the answer on the claim's result page does not change. The filters
   above the claims add *To decide*, *You: supported* and *You: refuted*. Claims you decided on are left out of
   *Check N claims*; open the card and press *Check this one* to check one anyway.
5. **Check your citations against their sources.** When you add a draft, Margin also finds its own citations, such
   as *(Smith, 2020)*, *Smith et al. (2020) found that …* and *[3]* (with a numbered reference list at its end). No AI
   is used for that. A third step on the draft page counts them, and **Check N citations** checks each cited work
   whose document is in the project against that document only: does the source say what your sentence says? See
   *Checking citations* below for what each answer means. In the draft, each citation is underlined by its answer:
   solid green when the source says it, wavy red when the source says otherwise or both, wavy amber when it says only
   part of it or the excerpts read do not say it, dotted while it waits or cannot be checked yet. The claim a
   citation stands for shows it under **Your citation**, with *See the excerpts*, *Check this citation*, or *What it
   needs* (a work to choose, a document to add). So a cited claim tells you two things: what all your documents say
   about it (step 2), and whether the source you cite says it (step 3). The filter *Citation to look at* shows the
   claims whose source needs a look, and a folded card names your citation and its answer. *Review every citation*
   opens the draft on the *Check citations* page, where you choose the work of a citation or leave one out. The checks
   of the draft's citations keep the draft's AI setting, as its claims' checks do, and *Remove* removes them with the
   draft. The Excel and CSV files gain *Your citations* and *What the cited source says*.

**Your draft against itself.** Between the steps and the draft, a card reads the draft against itself, without AI,
using its sentences and what Margin already has for it (the claims, their checks, your decisions). It opens on what
needs a look first:

- **May contradict each other**: two sentences about the same thing that go opposite ways ("costs fell" and "costs
  rose", "effective" and "ineffective") or where one says "not"; the same statement with two numbers ("grew by 40%"
  and "grew by 25%"); one passage of a document that supports one claim and contradicts another; two claims that say
  nearly the same thing but got opposite answers, or that you marked one supported and the other refuted.
- **Inconsistent**: an abbreviation used before it is spelt out, or spelt out two ways; one word written two ways
  ("organisation" and "organization", "data set" and "dataset").
- **May confuse a reader**: a claim that opens with "This" or "These" and a verb ("This shows …"), one that is
  careful and absolute at once ("probably … certainly"), and one long sentence holding several claims.

Contrasts you draw on purpose are left out: a sentence opening with "However", "In contrast" and the like close by,
a view you report in order to answer it ("Some argue …"), two different works cited for the two sides, sentences
naming different things ("costs in Europe" and "costs in Japan"), or two different years. Your reference list is not
read. Click a quoted place to highlight it, with the notice's other places, in your draft; a claim's card also names
the notices it is in ("May contradict claim 6"), and clicking that opens the notice. **Not a problem** sets a notice
aside; it stays aside while those sentences are the same, and *Show … set aside* brings it back. Each notice is a
prompt to look, not a verdict: the rules are careful rather than complete, so a contradiction worded very differently
is not found.

**Citations to paste (Margin 0.5).** With a bibliography on the *Bibliography* page (your Zotero library or
a collection, or a file exported from a reference manager), every document a claim would cite that is linked to a
work of the bibliography has its APA 7 in-text citation next to it, such as **(Verhoeven & Okafor, 2025)**. Click it
to copy it, then paste it into your text; Alt-click (Option-click on a Mac) copies the narrative form, *Verhoeven and
Okafor (2025)*. A folded card has one button for all the documents to cite, in one parenthesis and in APA's order:
*(Adeyemi & Brandt, 2024; Verhoeven & Okafor, 2025)*. The citations follow APA 7 as your reference list would: one
or two authors by name, three or more as *et al.*, editors when there are no authors, *n.d.* without a year,
*2024a* and *2024b* for two works of the same authors and year, and as many names as needed when two *et al.* would
read the same. A work without an author is cited by the first words of its title (in quotation marks for an article,
a chapter or a web page; in italics for a book or a report, which come along when pasted into Word). A document not
linked to a work has no citation; the card says so and links to *Bibliography*, where you can link it. The
citation is made from what Zotero holds: an author or year missing there is missing in the citation too.

On a wide window the draft and the claims scroll on their own: scroll through the claims and the draft stays where
it is. Click anywhere on a claim's card (not on its buttons or links) to show its sentence in the draft, and click a
sentence in the draft to bring its card into view.

*Excel* and *CSV* download one row per claim: the sentence, the claim checked, whether it is cited, the answer, your
decision and the documents on each side, as a list of what to cite, with their APA 7 citation when you have a
bibliography. The checks are also under *Results*, as a set. A draft marked
*Only a local AI* or *No AI* is never sent to Claude, in finding its claims or in any task of their checks, and is
hidden from a Claude chat; for a draft Claude may read, the page says how much of it Claude has read and when.

### Exploring the documents (0.7)

Before or alongside checking hypotheses, the pages under **Explore the documents** show what the documents say and
where. Search, key terms, the keyword profile, the glossary and themes by
words need no AI model; the AI only adds readings on top, and every one of them quotes the text and is checked
against it.

**Search.** Every place words occur, one line per place with the words before and after (a concordance), with the
count per document first. *Find* any of the words, all of them in one passage, a phrase, or words near each other
(within N words). Without *exact words only*, a word also finds its other endings ("price" finds "prices"); forms the
search does not include are listed under the count (*Other forms in the documents: commuters*), to add with one
click. Click a word in a line to add it to the search, Shift-click to make a phrase. Sort by document, by the words
before or by the words after. *Words that often appear nearby* lists the words within 2 to 10 words of the places
found, most often or most typical first (point at one for both figures). Every line opens the document at its words,
and its flask button starts a check of what the line says. Download all lines for Excel or as CSV. A *passage* is
the stretch of text the app reads as one unit, up to about 1,100 characters; the location (page, paragraph) is that
of the original.

**Profile.** Which codes of a codebook (your own CSV, or a built-in one: social practice theory, framings of
conduct and change, the 169 SDG targets or their 17 goals) each
document addresses, how much and where. There is no codebook until you choose one (Margin 0.8): the Profile page,
the Codes panel of a document and the themes' code grid ask for it, and *Settings → Exploring* can set it to none
again. Once one is chosen, when documents are added the app finds candidate codes in seconds by their
keywords (and by meaning, with an embedding model): a *provisional* profile. *Let the AI label the passages* has the
AI read each passage with a candidate code and say which codes really apply (main topic or mentioned; for a codebook of aims,
whether the passage says it helps or hinders the aim), with a quote and a reason; afterwards it says how many keyword
codes it confirmed, did not confirm, and added. Count by code or by group (a codebook's groups). The grid opens the passages
behind each cell. In a document, the **Codes** panel shows every code with its passages, quotes, reasons or the
words that found it (highlighted in the text): agree, change how it applies, reject (with Undo), or add a code of
your own; your labels always count. *Technical details* show the model, its exact version (digest), the prompt and
the seed, and warn when they differ from the last run.

**Codebooks with more to say (Margin 0.9).** Besides `code` and `description` (and `group`, `group_name`), a
codebook's CSV may have `keywords` (words and phrases separated by `;`, found as whole words), `include` (when to use
the code), `exclude` (when not to, and which code to use instead) and `source` (where its definition comes from).
The AI reads include, exclude and source with each code. A JSON file next to the CSV (same name, `.json`) may give
`title`, `label`, `directional`, `direction_labels` (your words for helps, hinders and mixed), `direction_note` (what
the direction is relative to), `one_main` (at most one main code per passage), `practice_and_element` (each label
also names the practice and the element), `stance` and `sources`. A codebook of 30 codes or fewer is sent to the AI
whole with every passage, and the AI reads every passage by default (*Options* switches it), since a keyword search
misses codes whose words are not in the text. *Settings → Codebooks → View codes* shows all of it.

**Social practice theory.** Two built-in codebooks follow practices rather than topics:
- *Social practice theory* (25 codes): elements (EL: materials, competences, meanings), performing the practice (PF),
  knowing (KN), rules, resources and power (RP), dynamics of links made, sustained and broken (DY), and connections
  between practices (NX). A label says whether the passage **holds the practice together** or **pulls it apart**,
  and names the practice and the element in the passage's words: "When the night nurse left, nobody switched the
  table on again and the games stayed in the cupboard" is DY3 *Breaking links*, DY6 *Learning and careers* and EL1
  *Materials* (the games), all pulling apart. *Count by → Practice* shows practices by code, each with its elements.
  A concept's page lists the labels that name it (*In codebook labels*), and its links can say how elements relate:
  needs, shapes, replaces, is an element of, clashes with (*Ask the AI how they relate in a practice* under *Often
  mentioned together*).
- *Framings of conduct and change* (4 codes, one main code per passage): whether a text explains what people do
  through practices, individual choice, structure or system, or technology by itself. Run it on policy documents.

Use them with care: these concepts are sensitising, not a formula (Nicolini 2012: 240). Labels on interview
transcripts record what people say about their practice; fieldnotes code better, and *practical consciousness* (KN1)
only where a speaker marks their knowing as tacit. Concepts that show only across a body of material (a practice's
trajectory, proto- and ex-practices, the duality of structure) are not codes: check them as hypotheses, tagged with
a code ("Use of the table lasted only where a staff member made it part of the daily care routine", DY2).

**Concepts.** A glossary of the terms the documents use (one or more words, found by the C-value method; running
heads and page furniture are left out), grouped into concepts: abbreviations and their long forms ("proton exchange
membrane (PEM)"), wordings close in meaning (with an embedding model), links the AI proposes and you accept, and
links of your own. A concept card shows how the documents write it (*Not the same* splits a wording off), which
documents discuss it and where it first appears, every line where it occurs, and related concepts (the same,
broader, narrower, related, often together). *Ask the AI for other wordings* lists wordings the documents use;
add them, or say *Not the same* and they are not proposed again.

**Themes.** What the documents are about, grouped into themes (spherical k-means on the passages' embeddings, or on
their terms without an embedding model; the same documents and settings always give the same themes). Each theme has
key terms, a size, the documents it comes from and the passages that represent it best; grids show themes by document
and by code. Rename, merge and move passages (kept and reapplied to a new set with the same settings); *Let the AI
name the themes* gives names and short descriptions with checked quotes. A small project gets fewer themes than
asked (about three passages a theme).

A theme that is not relevant to you (running headers, reference lists, a topic outside your question) can be
**removed**: its passages are left out of the themes, the grids and the downloads, and it waits under *Removed
themes* at the foot of the list, where *Bring it back* undoes it. *Remove and find a new theme* also looks for a new
theme in its place, on this computer and without AI: among the passages that fit their own theme least well, it
finds the group that sits closer to a new centre than to the theme it is in, and moves it into a new theme named by
its key terms (the themes it takes passages from keep their names). It never takes passages that are closer to a
theme you removed, so the removed theme does not come back under another name. A new theme says which theme it
replaces and where its passages come from; remove it too to find another. Removals and new themes belong to that
set of themes only.

### An outline from your themes

*Outline* (in the sidebar, under *Your writing*; or *Make an outline* on a set of themes) turns the themes into a
plan to write from. It uses no AI: everything is made on your computer from what Margin already knows, so it gives
the same outline twice.

**One section for each theme.** A section shows the theme's key terms, the passages that represent it best (with
their place in the document), the documents to cite (with an APA in-text citation such as *(Haugen, 2024; Okafor,
2023)* and a *Copy* button when the documents are linked to your bibliography), the codes of your codebook that its
passages carry, and the concepts its key terms belong to. A heading comes from the theme: the name the AI gave it
(*Themes → Let the AI name the themes*, optional), your own rename, or else its first key terms.

**An order that reads as a path.** Themes that share documents and key terms sit next to each other. The outline
starts with the theme that has most passages and goes on to the most similar theme not used yet; each section says
what it shares with the next. The order is a suggestion: *Suggest the order again* puts the theme sections back in it
(sections of your own stay where they are).

**Make it yours.** Drag a section by its grip to move it (top of another section: before it; bottom: after it;
middle: inside it), or use the arrow buttons: *Move up*, *Move down*, *Put inside the section above*, *Take out of its
section*. The three dots give *Rename*, *Join to another section* (the other gains its themes, notes and inner
sections), *Split* (a section of several themes becomes one for each; a section of one theme is split by documents)
and *Take out of the outline* (its theme waits under *Themes not in the outline*). *Add a section* makes one of your
own, such as an introduction or the methods. Each section has a box for your notes. Sections nest three levels deep.
The outline is kept in the project, survives a reload, and stays when you find the themes again or delete the set it
came from (the sections keep their titles and notes). You can make several outlines.

**What each section tells you.** *Where the sources disagree* shows, side by side, the claims you checked in which the
section's documents are on both sides (or on one side against documents elsewhere), with the quote and place of each.
*Gaps* names a section with one source only, two sources, mostly one source or few passages. *You decided* lists what
you decided about claims of a draft that these documents touch.

**Beside a draft.** *Beside a draft* marks each section with how much of it the draft covers: its key terms found in
your words, and its sources found among the works your draft's own citations name. Opened, a section lists the
sources not cited yet, their passages, the key terms not used yet and where in the draft it is touched. *Also by
meaning* compares each draft paragraph with the section using the embedding model, only when search by meaning is
set up with a model on this computer; nothing is sent anywhere. Without a bibliography no source can count as used, and
the page says so.

**Download.** *Word (.docx)* and *Markdown (.md)* give the outline as a document to write into: numbered headings,
your notes, key terms, the citation, quotes with their place, where the sources disagree, gaps, and the sources named.

**In a document.** Besides *Codes*: **Key terms** (the terms that set the document apart; in a project of one document, the terms that
run through it; point at one to underline it in the text), **References** (*Follow the references*: the AI reads the document three passages at a time and links
"it", "they" or "the study" to the name they stand for; select a name in the text to see every later mention), and
**Search** in the document. *Download a highlighted copy* gives the PDF with highlights for the judgements, codes,
concepts or references you choose (exact boxes with the `pdfminer` extra, whole lines otherwise, text recognition for
scanned pages), and a note listing any quote it could not place; other documents come as an HTML copy.

**In a result.** A quote that starts with "it" or "they" says what it refers to (*"it" = green hydrogen*); when the
AI did not say, the excerpt is flagged *Check what the quote's first word refers to*. *Highlighted copy* on an
excerpt, *Highlighted documents (.zip)* in the downloads, and *highlighted* under each document of the evidence map
give the documents with the quotes marked.

**Quick look.** *Quick look at one document* (on the start page, on *Skim* and on *Manage projects*) reads one file
into a temporary project and opens its *Skim* report (below): search it, see its codes and references at once. A banner
offers *Keep as a project* or *Discard now*; otherwise it goes to the trash after 7 days.

### Skimming one document (Margin)

**Skim** (sidebar, first under *Explore the documents*; *Skim it* on any document) is a one-page report on one
document, for a publication you want to skim before deciding to read it. A quick look lands on it, so there is no
project to set up. It is made on this computer without AI (rules, counts and the document's own words), and needs no
other document: what compares documents elsewhere has a single-document version here.

- **At a glance:** reading time (the words before the reference list, at 230 a minute), sections, works cited, and
  claims without a citation.
- **Abstract:** under a heading *Abstract* or *Summary*, or a line starting with the word near the start; the keywords
  after it are left out.
- **What it sets out to do, and what it says it found:** sentences in its own voice ("we", "this study", "our results
  show", "we conclude"). A plan ("we will describe") is not a finding. *Check a draft* leaves these sentences out on
  purpose; here they come first.
- **Key sentences:** the sentences that carry most of its key terms, at most two from a section, in reading order: a
  summary in its own words. One that opens with "it" or "they" is chosen less often, since out of context the reader
  cannot tell what it refers to.
- **Claims about the world:** the statements of the kinds that usually need a source (numbers, causes and effects,
  comparisons, what research found, general claims), by the rules of *Check a draft*, each marked with or without a
  citation. Those in its own abstract, data, methods or results are kept apart: there a number is its evidence. The list
  opens on *Without a citation*.
- **Sections** with the words in each, **key terms** (with one document, weighed by how far each term runs through it,
  since there is nothing to compare it with; in a larger project, against the other documents), the **works it cites
  most** in its text, and the DOIs in its reference list (*Follow its citations* on *Find literature*), and its
  **codes**, when a codebook is chosen.

Every sentence opens the document at its place. *Markdown (.md)* downloads the report as notes to keep. In a quick look,
*Ask it something* leads to *Check a hypothesis* (which uses the AI) and *Search*.

### The bibliography: Zotero (0.13)

*Bibliography* (in the sidebar, under *Documents*) puts your Zotero library, one collection of it, or just the works
you choose, next to the project's documents. It answers three questions: which works of the bibliography do I have, which do I still need
to find, and which documents are not in my bibliography. It uses no AI.

**Bringing it in.** Margin reads Zotero from the Zotero app on this computer: Zotero 7 or later, open, with *Settings
→ Advanced → Allow other applications on this computer to communicate with Zotero* ticked once. Choose the library
(My Library, or a group library), a collection (or *The whole library*) and whether its subcollections come along,
and press *Bring in the bibliography*. To bring in only some works, even a single one, tick *Choose the works one by
one* (0.13.9): a list of the library's works appears (or of the collection chosen above), searched by title, author
or year as in Zotero's own search box. Tick the works you want; they stay ticked while you search or switch
collections, and stand above the list (click one to leave it out). Press *Bring in 1 work* (or *2 works*, and so on). Nothing goes over the internet, no Zotero account or key is needed, and Zotero
is only read, never changed. The page says plainly when Zotero is not open, does not allow it yet (with the box to
tick), or is too old. Without the app, *Use an exported file instead* takes a file exported from Zotero (right-click a
collection → *Export Collection…*: BibTeX, RIS, CSL JSON or CSV) or from Mendeley, EndNote and other reference
managers (BibTeX or RIS). With Zotero's CSV and BibTeX the paths of the files Zotero keeps come along too.

**The four lists.** Four tiles at the top count them and open each one:

- *Please confirm*: a work whose title stands on the first pages of a document, with an author or the year. The work
  and the document are side by side, with the place on the document where the title stands, highlighted, and what was
  found (*Found on page 1: the whole title, the author Lindqvist, the year 2025*). *Same work* links them; *Not the
  same* means the pair is never proposed again. *Confirm all* takes every pair at once.
- *To find*: the works without a document, with their authors, year, type, where they were published, a DOI link,
  their web address and *Open in Zotero*. *Download the list* gives them as a spreadsheet, your to-download list.
  When Zotero keeps a file (a PDF, a saved web page, a Word file) for some of them, a card offers *Add these files to
  the project*: they are read where Zotero keeps them (nothing is copied), after you say who may read them with AI
  (the project's choice is preselected), and each is linked to its work. *Link a document* says by hand which
  document a work is.
- *Linked*: each work with its document, and how they were linked: *Same file* (a file Zotero keeps for the work is
  the very file you added, by its checksum), *Same DOI* (the document prints the work's DOI), *You confirmed it* or
  *You linked it*. *Unlink* undoes a link for good (*Undo* in the message brings it back). A linked document is
  called by its work's title everywhere in Margin (0.13.3); when the file's own title says something else, it stays
  under the file name (*Title in the file: …*).
- *Not in the bibliography*: the documents no work is linked to. Add them to Zotero and press *Update from Zotero*, or
  *Link to a work* by hand.

**Keeping it up to date.** *Update from Zotero* reads the same collection again, or the same chosen works (a work
deleted from Zotero goes; a work added to Zotero does not come along). *Use another collection or file* replaces the
bibliography; for chosen works it is called *Choose other works or a file*, and the works you chose last time start
ticked, so adding one more is one tick away. Your decisions are kept for every work that is still there, even when it comes from
another source (by its Zotero key, else its DOI, else its title and year). Documents you add later are matched as
they come in: the message after adding says how many were linked and how many wait for you. A document linked to a
work takes the work's title (0.13.3): in the Documents list, on the document page, in Search, in a check's excerpts
and in the exports. The document page also shows the title read from the file, which comes back when no work is
linked any more; a title edited in Zotero follows with *Update from Zotero*. The document also shows its reference
(*Verhoeven and Okafor (2025)*) in the Documents list, and on the document page with its DOI and *Open in Zotero*.
*Remove the bibliography* takes the works and links out of the project; documents and Zotero
stay as they are.

**What the matching does not do.** A scanned PDF without a text layer has no title to find until text recognition
(OCR) has read it. The same title in different years (an annual report) is told apart by the year printed nearest the
title; when both are close, both pairs are shown for you to choose. A book and one of its chapters, or a translation,
are at best proposed. A document that only cites a work is not taken for it: the title must stand on its first pages
as a title, not as words spread over them.

### Checking citations (0.13.7)

*Check citations* (in the sidebar, under *Your writing*, beside *Check a draft*) reads a text for its citations and
checks each one
against the source it cites: does the source say what the sentence says? It needs the project's bibliography (the
page above): a citation is matched with a work of the bibliography, and checked against that work's document in the
project, and against no other document.

In Margin, your own writing has one home: a text you paste or choose here is kept as a draft (with its name and AI
setting), so *Check a draft* can also show which of its statements still need a source, and every draft's citations
are listed here. A text without any citation is not kept. A draft's citations lead back to it (*Back to your draft*,
*Open your draft*); they are removed with the draft, on its page.

**A text to check.** Paste your draft, choose its file (Word, PDF, text, Markdown or a saved web page; it is read on
this computer and does not become one of the project's documents, so it never turns up as evidence in another
check), or pick a document of the project (a report whose citations you want to check). For a draft, say who may read
it with AI, as for documents: *Claude may read it*, *Only a local AI* or *No AI* (the project's choice is
preselected; you can change it later at the bottom of the summary). A document keeps its own setting. *Find the
citations* reads the text at once; no AI is used for that, and nothing is checked yet.

**What it finds.** Citations with an author and a year, in brackets or in the sentence: *(Smith, 2020)*, *(Smith &
Jones 2019; Lee et al., 2021a, p. 4)*, *(e.g., WHO, 2021)*, *Smith (2020) found that …*, *According to Lindqvist et
al. (2025), …*, *The World Health Organization [WHO] (2019) warned …*. Numbered citations (*[3]*, *[2, 4–5]*) when
the text ends with its numbered reference list; without the list, the page says how many it could not read. The
reference list itself is never read as citations, nor are *(Figure 3, 2020)* and the like.

For each citation Margin takes **the claim** it stands for: the words before a citation in brackets (from the start
of the sentence, or from the citation before it in the same sentence: *X rose (A, 2020), while Y fell (B, 2021)*
gives *X rose* to A and *Y fell* to B), or what follows a citation in the sentence (*Smith (2020) found that X*: X).
The claim is highlighted in its sentence on the page. The sentences before it go along as **context**, so the AI
understands *it* and *this effect*; the context is never graded or quoted as evidence.

**Which work it is.** A citation is matched with the bibliography by its first author's surname and the year: the
second author decides between two works of one author in one year, *2020a* and *2020b* follow the order of their
titles, *van der Berg* and *Berg* are the same name, *Müller* and *Muller* too, and *WHO* is found for the World
Health Organization. A work cited with another year is not taken, but offered (a wrong year in the draft is worth a
look). A citation introduced by *but see* or *contra* is cited for another view: it is left out of the checks
(*Left out*, at the bottom, with *Put it back*).

**The answers.** Four tiles count them; the main button, *Check 12 citations*, checks every citation that is ready,
one after the other (by Claude Code, through the queue, as any check; you can leave the page). Each cited work gets
its own check: a sentence citing three works gets three, one per source.

- **Source accurate**: an excerpt of the source says what the sentence says, and none says the opposite.
- **To look at**, with a notice:
  - *Only partly supported by the source*: it says part of it (a narrower finding, another group or period, a weaker
    version). Reword the sentence, or add a source for the rest.
  - *Not found in the source*: none of the excerpts read says it. The source may say it in other words: open the
    excerpts and *Look for more evidence*, or check that the right work is cited.
  - *The source says otherwise*, *The source says both*, *Unsure*, and *The check did not work* (with *Check again*).
  Each shows the sentence, the cited work, and the excerpt that shows the answer best, with its page.
- **Cannot be checked yet**: *Not in your bibliography* (choose the work from your bibliography, or *Not a
  citation*), *Which work is it?* (several works match: choose one), *Its source is not in the project* (add its
  document on the Bibliography page, *To find*), *Its document waits for your confirmation* (on the Bibliography
  page). Once that is done, the citation is ready: works and documents added later are used without adding the text
  again.

*See the excerpts and judge them* opens the check on the result page, with *In your text:* and the sentence at the
top, and every excerpt to agree with, mark as not about it, or judge differently: your judgement changes the answer
on the Citations page too. *Download: Excel (.xlsx)* gives one row per cited work (the sentence, the claim checked, the
citation, the work, the answer, the quote and its page). *Remove this text* removes the text, its citations and their
checks; your file and your documents are not touched. Checks of citations are kept apart from your hypotheses: they
are not in *Results*, the evidence map or its downloads.

**What it sends.** Each check sends what a check of a hypothesis sends: the claim (with its sentences as context) and
excerpts of the cited source, to the AI of *Settings*. A draft marked *Only a local AI* is read by the model on this
computer only (also when Claude Code is your AI), one marked *No AI* is judged by you (every excerpt waits for your
judgement), and a document keeps its own setting. The search words a check asks the AI for are asked only when the
text may go to that AI. Checks of a text Claude may not read are never shown to a Claude chat through the connector.

**What it does not do yet.** Footnote citations (*Chicago* notes), superscript numbers and citations inside a Word
file's footnotes are not read; a numbered citation needs its reference list in the same text. The claim is cut from
the sentence by rules, not by the AI: when it starts with *it* or *they*, the context says what they are, and the
answer is yours to overrule. A text that changed is added again (remove the old one).

### Finding literature (Margin)

**Find literature** (under *Your writing*) looks things up online. It is not AI: it asks OpenAlex, a free index of
scholarly works, and the words it asks with are made on your computer. It has three tabs.

- **Search.** Start from a claim of a draft that no document supports (the draft page's *Find literature* button opens
  it with that claim), or type words. Margin suggests search words from the claim and from the key terms of your
  documents; you can change them, and the line under them says exactly what will be sent and to whom. Pick *Search
  in* OpenAlex, Crossref or Semantic Scholar, a first year, and *only works with an open copy* if you wish. The works
  are ordered by how close they are to your claim: by meaning when you have a local embedding model (Settings →
  Documents), otherwise by the words they share. Works you already have are marked. An open copy is shown when
  OpenAlex knows one; *Look for open copies* asks Unpaywall for the rest (it needs your e-mail address).
- **Follow citations.** The works your documents cite and the works that cite them, from the DOIs of your documents
  (and of the works of your bibliography linked to them). They are ordered by how many of your documents they connect
  to, then by how close they are to your themes. *Show exactly what is sent* lists the DOIs; documents whose AI
  setting keeps them on this computer are left out.
- **Saved searches.** Keep a search, or write a research question: Margin makes search words from it and you change
  them. A saved search says how many works are *new since you last looked*. Margin checks searches when you open the
  page (those not checked for six hours) and when you press *Check now*; nothing runs in the background. *Mark as
  seen* starts the next look from today. The Overview card shows the count.

**Choosing works.** Tick works anywhere on the page; the bar at the bottom offers **Send to Zotero** (Zotero's own
connection on this computer: Zotero puts the works in the collection that is selected in its window, so open Zotero
and select one first; the bar says which) or a **RIS** or **BibTeX** file to import yourself. *Let Zotero fetch the open
PDFs* adds each open PDF to the work; Zotero itself downloads them. Then update the bibliography to match the new works
with your documents.

**What it sends, and what it never does.** Search words, the DOIs of your documents when you follow citations, and, if
you set one under *Settings → Exploring*, your e-mail address (so the services can reach you if you ask for much;
Unpaywall requires one). Margin never fills it in. Nothing goes out when cloud models are off for good on this
computer (`--local-only`); a search from a draft goes out only when the draft's setting is *Claude may read it*, so for
other drafts you type your own words; documents with another setting are left out of *Follow citations*. No text of a
draft or document is ever sent, and no AI reads anything. Answers are kept in the project so the same lookup is not
repeated; *Ask again* asks the service again.

**What it does not do yet.** It has not been tried against the real services by its authors' tests (they use stand-ins),
so a change in OpenAlex's rules (it may ask for a key) can show as *refused*. A saved search lists at most 50 works per
look. Following citations resolves at most 150 cited works. Crossref and Semantic Scholar are for searching only; saved
searches use OpenAlex.

### Settings

Settings has five tabs, each one page with nothing folded inside another (0.9):

- **AI**: which AI reads your documents, as four choices: **Claude Code** (recommended: your own Claude plan),
  **A model on this computer** (automatic, Ollama, or an OpenAI-compatible server such as LM Studio, with the
  address, model and reasoning switch), **No AI (demo)**, and the **Claude API (team key)** for a shared
  installation, behind a confirmation and *Allow cloud models*. With Claude Code: the set-up checklist and *Set up
  Claude Code* (section 6) and *Let the auditor use Fable*. *Save and test* says whether the AI answers (with Claude
  Code: whether it is set up). With a model on this computer chosen but none installed, the same steps as on the
  first screen: get Ollama, then *Download qwen3:8b* (0.13.7). *Local model for restricted documents* offers the
  download too, and *Settings → Documents* downloads nomic-embed-text for search by meaning when Ollama has no
  embedding model.
- **Checking**: the **strictness** (how sure the AI must be before a judgement counts; it saves at once, applies to
  every result, and reports which answers and counts changed; *Back to normal (60%)*), with **how often you agreed
  with the AI, by its certainty**: a small chart from the excerpts you judged; after 20 judgements it may suggest a
  strictness ("When the AI was at least 70% sure, you agreed with it in 85% … *Use 70%*"); and how new checks start
  (other words, parts, how many excerpts to read and at most how many from one document).
- **Exploring**: the codebook of the profiles, how many themes a new set looks for, and the **codebooks**: view the
  codes, add a CSV codebook, remove one; a CSV codebook can be marked as aims a text can help or hinder, like policy
  goals. The built-in SDG codebooks are listed last. Margin adds **Looking up literature online**: your optional
  e-mail address for *Find literature* (empty until you give one).
- **Documents**: **reading scanned PDFs** (on or off, and the languages) and the embedding model for **search by
  meaning**.
- **Technical**: **AI model per task** (which model answers each kind of task, what it steps up to, the helper on
  Claude Code, a choice per kind, *Use the recommended models*, and for local servers the small model for labels and
  links; on Claude Code, since 0.13.10, *The recommendations follow* your Claude plan, see *Models that suit your
  Claude plan* below); with a local model, the **model for second opinions** and the **context length** (automatic by default, see section
  5) with *Sort the best excerpts again by wording* (off; see the changelog of 0.6.0); **Repeatable results** (the
  seed sent with every request, 42 by default, and a test of whether the server gives the same answer twice); *Test a
  model before trusting it* (section 5); and where your data is.

Old links to a section (`#/settings/second`, `#/settings/calibration`…) open its tab.

When no local model is chosen, or the chosen one is not installed, the app uses one the model server already holds
in memory (so nothing extra is loaded), else the most recently downloaded one, and the test says so.

### For whoever installs the app

- A new installation uses Claude Code on the researcher's own plan (0.9). To use a model on this computer instead,
  choose it once in *Settings → AI* (or let *automatic* find Ollama or LM Studio) and press *Save and test*; with
  Ollama running, *Download qwen3:8b* there gets a model without a terminal (0.13.7); an
  installation that already chose a local model keeps it when it is updated. With an embedding model set
  (*Settings → Documents*), new documents are indexed for search by meaning right away.
- To make sure nothing can ever be sent to a cloud model, start the app with `margin-gui --local-only`, set
  `MARGIN_LOCAL_ONLY=1`, or create an empty file named `local_only` in the data folder. The cloud options (the
  Claude API and Claude Code) are then hidden, the default becomes the local model (*automatic*), the app and its
  API refuse to switch to them, Margin never starts Claude Code, and the connector refuses to hand out queued tasks.
- Keep the data folder (`--home`) somewhere that is backed up: it holds the projects, their results and the settings.
- Install it with the one-line install (section 1): it makes the icon. With `MARGIN_LOCAL_ONLY=1` and
  `MARGIN_HOME=<folder>` before the line, both are built into the icon. From a git copy, give the user an icon with
  `margin-gui --make-launcher` (section 1), with the same `--home` and `--local-only` you would start it with.
- For scanned PDFs, install Tesseract and the `ocr` extra (section 1); Settings shows whether it is available.

**Cost and time.** With a local model, a check costs nothing but time: from seconds to several minutes per call
depending on the model and the computer. With the Claude API one part is two calls of a few thousand tokens.

---

## 4. The command line for hypotheses

```bash
margin --ws myproject init
margin --ws myproject ingest ~/Reports/ more.zip
margin --ws myproject embed --embed-model nomic-embed-text          # optional semantic index
margin --ws myproject check "Green hydrogen production increases water stress in arid regions." --code 6.4
margin --ws myproject check "..." --decompose --embed-model nomic-embed-text
margin --ws myproject batch hypotheses.csv --out results.csv
margin --ws myproject history --limit 20                            # or --csv all_checks.csv
margin --ws myproject frameworks
margin detect                                                       # local servers and their models
```

`check` (or `hypothesis`) prints the verdict, the balance, and per claim the graded passages with quotes and the
passages read without result, as JSON. Options: `--decompose`, `--framework NAME --code CODE` (a code without `--framework` is read as an SDG target), `--k`, `--per-doc`, `--no-expand`, `--threshold`, `--embed-model` and `--embed-url`.

Backends (`--backend`, every model command): `auto` (default: the first local server running, Ollama first), `ollama`
(`--url`, `--num-ctx`, `--think on|off`), `local` (an OpenAI-compatible server, `--url http://localhost:1234/v1`),
`anthropic` (the Claude API: the text read is sent to Anthropic), `baseline` (offline keyword demo). Without
`--model`, a local backend uses a chat model its server already holds in memory, else the most recently downloaded
one, and says which; the Claude API uses `models.verify` of `config.json`. `--num-ctx` is `auto` by default: the
smallest of 8,192, 12,288, 16,384 and 32,768 tokens that fits the largest task (for `run`, the largest pending task).

```bash
margin --ws myproject ingest scans/ --ocr auto --ocr-lang eng+nld   # scanned pages read by OCR (default: auto, eng)
margin --ws myproject export-project myproject.zip                  # the whole project in one zip
margin import-project myproject.zip --ws copy_of_project            # into a new (or empty) folder
```

Exploring the documents (0.7):

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
margin --ws pilot acceptance queue --kind label --model haiku [--again]           # 0.8: a run through the queue
margin --ws pilot acceptance score [--apply]                                      # 0.8: score the runs (docs/MODEL_CHOICE.md)
margin --ws myproject prepare label|link|theme|resolve|check ["hypothesis"]       # 0.8: tasks for Claude Code
margin --ws myproject queue status|run|first|hold|go|withdraw [kind]              # 0.8: the queue (run: answer it here)
margin claude-setup                                                               # 0.8: the Claude Code plugin
```

Every model command takes `--model-seed N` (default: the seed of the settings, 42). `margin backend-check
--repeatable` asks the model the same question twice and says whether the answers match. `export-tasks` warns when
asked for the 0.7 kinds (`label`, `link`, `theme`, `resolve`): the file queue works for them, but their tasks are
made per project run and are usually answered in the app.

---

## 5. Local models

What Margin asks of a model is harder than chat: quotes copied word for word, fine judgement between "partly
supports" and "same topic", and answers in a fixed JSON format. Ollama and the OpenAI-compatible servers are given
the answer's JSON schema, so even small models give valid JSON; the rest depends on the model.

- **Size.** Rough guide by memory (October 2026; check your server's library for current models): about 16 GB runs
  models of 8 to 12 billion parameters, 32 GB runs 27 to 32 billion, 64 GB or more runs the largest. Larger models
  judge better and are slower. If memory allows, an 8-bit version copies quotes more reliably than a 4-bit one.
- **Context.** Margin sets the context length on every Ollama request (Ollama's own default is much smaller and
  cuts long prompts without warning). By default it is automatic: the smallest of 8,192, 12,288, 16,384 and 32,768
  tokens that holds the largest task the settings can produce (8 excerpts without reasoning: 8,192). The model's
  working memory grows with it (for qwen3:8b about 1.2 GB at 8,192 tokens and 2.4 GB at 16,384), so this leaves the
  most memory for the model itself. It stays the same between requests, because Ollama reloads the model when it
  changes. Settings → Technical shows the length in use and takes a fixed number instead. With LM Studio or
  llama.cpp set it when loading the model (16,384 covers every task of the app).
- **Memory.** Margin loads no model of its own and makes one model call at a time. A second opinion unloads the
  main model first (Ollama) and unloads itself when it is done, so two models are never in memory together; LM
  Studio and other OpenAI-compatible servers have no standard way to unload a model, so there their own setting
  (LM Studio can be set to keep only one model loaded) decides.
- **Reasoning.** For models that reason before answering (Qwen 3 and 3.5, for example), *Settings → AI →
  Reasoning* (Ollama) has four choices:
  - *Off*, the fastest;
  - *Only when judging excerpts*: reasoning where it can help, not for search words or splitting a hypothesis;
  - *On for every step*;
  - *Model's default*.

  The **reasoning budget** (default 1,500 tokens) keeps reasoning within a time limit. A model still reasoning at
  the budget is stopped and asked to answer at once from its notes. At 20 tokens a second that is at most about 75
  seconds of reasoning per judgement, and with *Only when judging excerpts* a check takes a minute or two per part
  instead of half an hour. Whether reasoning judges better depends on the model: compare it with
  `margin --ws pilot benchmark --model … --think off` and `--think judging` before relying on it. Reasoning text
  that a server puts before the answer is ignored.
- **Embeddings.** `nomic-embed-text` (fast, English), `mxbai-embed-large`, or `bge-m3` (multilingual). Building the
  index embeds every passage once (minutes for ten thousand passages); after that a search costs one short call.
  With numpy installed (`.[fast]`) the comparison is instant; without it, about half a second per search on ten
  thousand passages.

**Test a model before trusting it** (for developers; Margin 0.8 took it out of Settings, since it needs a project
whose earlier answers serve as the reference):

```bash
margin --ws pilot benchmark --backend ollama --model qwen3:8b --sample 30
```

It runs the model on tasks the pilot already answered with Claude Opus 5.5 and reports, per task kind: the share of
usable answers, of answers with a quote not in the text, agreement with the reference (same status, and Cohen's κ
beyond chance), and seconds per task. Nothing is stored. The verdict line uses rules of thumb: at least 90% usable
and κ 0.6 is "good enough to use, with review"; at least 75% and κ 0.4 is "usable for a first pass". Agreement with
Opus is not correctness, but a model that disagrees with it often will also disagree with your reviewers.

Confidences are the model's own estimates. They are not calibrated until you compare them with your own judgement:
Settings shows how often you agreed with the AI at each certainty, from the excerpts you judged, and after 20
judgements suggests the lowest strictness from which you agreed at least 80% of the time.

---

## 6. The connector for the Claude app and Claude Code

The connector lets Claude check claims and hypotheses against your documents inside an ordinary chat. Claude does the
reading and grading on your Claude plan, with no API key; only the passages shown to it (about 8,000 characters a
round) leave the computer. The connector, a small program on your computer, keeps the projects, picks the passages,
checks every quote against the source and keeps the history. It uses the same projects as the app, so a check made
in the chat appears in the app's History (graded by "claude (chat)") and the other way round.

### Set it up

```bash
pip install -e '.[connector]'
margin-mcp --install-claude-desktop      # adds the connector to the Claude desktop app's config (keeps a .bak copy)
```

Quit and reopen the Claude desktop app. `margin-mcp --print-config` prints the block for the desktop app's config file
(to add by hand) and the exact `claude mcp add …` command for Claude Code. Both start the connector with the Python
it was installed in. Use `--home FOLDER` with either command if your projects are not in `~/margin`.

### Use it

Write in the chat as you would to a colleague:

- "Make a new project called Morocco from ~/Downloads/morocco_sources.zip" (give a path; files attached to the chat do
  not reach the connector)
- "Use my pilot folder ~/margin/pilot as a project called Pilot"
- "In Pilot, check this hypothesis: hydrogen leakage along the value chain undercuts its climate benefits, because
  leaked hydrogen extends the lifetime of methane." (Claude splits a compound hypothesis into parts and checks each)
- "Read more passages" or "Try a different search" when nothing was found
- "Show me my recent checks in Pilot"

- "In Pilot, where do the documents talk about electrolyser imports?" or "Which codes does the IEA Africa
  outlook address?" or "What does Pilot call PEM electrolysis, and in which documents?" (0.7)

The connector's tools: `list_projects`, `create_project`, `add_sources`, `use_folder_as_project`, `list_documents`,
`list_frameworks`, `suggest_targets`, `start_check`, `submit_grades`, `more_passages`, `get_check`, `list_checks`,
and since 0.7 `search_corpus` (concordance lines, so Claude can look around before proposing a hypothesis),
`document_profile` (a document's codes with their passages) and `find_concept` (a concept's wordings and documents).
A recorded demo of a session is in `docs/connector_demo.html` (made with 0.4; the flow is the same).

If the Claude app does not show the connector, check its connector settings for an error. Running `margin-mcp` in a
terminal shows any start-up problem (it then waits for the app; stop it with Ctrl+C).

### Claude Code as the AI behind every task (0.8; the default from 0.9)

With Claude Code, signed in with your own Claude plan, every AI button of Margin is answered by Claude: profile
labels, concept links, theme names, references, checks, reading an excerpt again, second opinions and *Compare a sample* of labels. Margin prepares
the work in a queue and checks every answer as it checks any other; Claude Code does only the reading. Margin never
sees your Claude login (Claude Code uses its own) and never runs on anyone else's plan. For a shared installation
that runs unattended, use the Claude API with the team's key instead (the same queue and the same models per task:
`margin queue run --backend anthropic`).

**Set it up once.** In Margin, the first screen or *Settings → AI → Claude Code*: press **Set up Claude** (0.10). It
installs Claude Code if it is missing (after showing you the command), opens a window for the one-time sign-in with
your Claude plan and waits for it (section 3, *First use*), then writes the plugin into your Margin folder
(`claude-plugin/`) and adds it to Claude Code by
running the same two commands you would type (`claude plugin marketplace add …`, `claude plugin install
margin-run@margin`); nothing else in Claude Code's settings changes. The checklist then shows three ticks. From a
terminal, `margin claude-setup` does the same (`--print-only` only prints the two lines). Margin finds the `claude`
program on the PATH or where its installers put it; `MARGIN_CLAUDE=/path/to/claude` names it. When Margin is moved
or installed again (a new Python), it writes the plugin again on its next start and adds it again, quietly (0.10);
the Claude desktop app's connector entry is pointed at the new Python too when the old one is gone.

**Start Claude Code (0.9).** Press an AI button in Margin. The page says what waits, for example *Waiting for
Claude Code: 120 passages to label · about 25 minutes*, with **Start Claude Code**. Margin then starts Claude Code
in the background for that project (`claude -p "/margin-run:margin-run <project>"`, run in the Margin folder),
allowed only the four Margin queue tools and its helpers, so a passage that tries to give it instructions can do
nothing else. The page and the sidebar's queue panel say *Claude Code is working on it*, with *Stop Claude Code*;
it stops by itself when nothing waits. *Stop Claude Code* returns the batches it had taken to the queue at once. If a
run ends with a problem (a usage limit, for example), the page shows the end of its report. The first start also
adds the plugin if that was not done yet.

**How fast it works (0.13.10).** Under **Start Claude Code** is **Speed: Slower · Normal · Faster**. Claude Code
hands the work to helpers (one per kind of task, each on its own model); the speed is how many work at once: Slower
one, Normal two (as before), Faster four. Faster is done sooner but uses your plan's limits faster; Slower takes longer
and is easiest on them. The choice is kept, is the same beside every *Start Claude Code*, and is also under *Settings
→ AI → Speed of Claude Code*. A run already working keeps the speed it started with; the line *Claude Code is working
on it* says how many helpers it has (*· 4 helpers at once*).

For one run you can also choose the helpers yourself: **Choose the helpers for this run**, folded away under the
speed, lists each helper that has work waiting, with its model, what it would answer and how much waits (*Labeller
haiku · Codebook labels · 7,868 waiting*). Set how many of each work at once (0 leaves that work waiting for a later
run) and **Helpers at once, in all** (1 to 8). The fold then says *changed* and the speed above it greys out; *Use the
speed again*, or picking a speed (even the one shown), undoes it. Work that comes in during the run for a helper not listed (an unsure answer for the auditor,
a check's excerpts after its search words) gets one helper. The choice is for that run only: after *Start Claude
Code* the fold is back to the speed. Which model each helper uses stays under *Settings → Technical → AI model per
task*.

Until it is pressed, nothing is answered: the step that waits keeps its spinner, so from 0.11.3 a **Start Claude
Code** left unpressed for about five seconds while work waits (and nothing answers it) pulses, and the line beside it
says *Nothing runs until you press it.* (with reduced motion in the computer's settings, it has a still ring
instead). The pulse stops once it is pressed, or once Claude Code started some other way takes the work. The button
is wherever work waits: a check's progress, a result that waits, the sidebar's queue panel, and since 0.11.3 also
the line of a follow-up on a result (reading an excerpt again, reading new documents, a second opinion, a stronger
model), which used to say only which command to type.

**Or type it yourself.** The same work can be started in Claude Code, opened in any folder:

```
/margin-run Pilot              # every kind of task waiting in the project Pilot
/margin-run Pilot label        # only the labels
/margin-run Pilot --parallel 4 # four helpers at once: faster, but it uses your plan's limit faster
/margin-run Pilot --helpers checker=2,labeller=1   # only these helpers, as many of each at once (0.13.10)
```

Without `--parallel`, a typed run goes at the speed chosen in Margin (two helpers at once unless you changed it;
0.13.10). With `--helpers`, the helpers not named do nothing in that run, and `--parallel` (if given) caps the total.
The helpers' names are labeller, linker, namer, reader, checker and auditor. Margin works out how many
helpers each kind of task gets, in the queue's order, and never more than it has batches for. The speed counts the
helpers of one run: Claude Code started both from Margin and in a terminal at the same time runs both runs' helpers.

`/margin-run` hands each kind of task to a helper agent on the model Margin names for it (labels and links on
Haiku, theme names, references, search words and checks on Sonnet, second opinions on the auditor; *AI model per task*
in Settings) and
reports what is done and what is left. The helpers can use only the Margin queue tools: they see nothing but the
passages handed out and write nothing but answers. Every answer is quote-checked; a wrong quote is sent back and
answered again. An unsure answer (certainty under 0.6), or one rejected twice, goes once to a stronger model.

You follow the progress in Margin: on the page that waits, and in the **queue panel** under the jobs in the
sidebar (per kind: waiting, being answered, done, the model and helper, the estimate; *Do first*, *Hold*, *Remove*).
Work that waits for Claude Code while nothing answers it (Claude Code not started from Margin, no `/margin-run`
taking or answering a batch, no answer in the last two minutes) is **not running**, and the jobs line above the queue
panel says so in amber with a pause mark: *1 task not running · Waiting for Claude Code to start*, with *Start Claude
Code* in its panel (0.12). Once Claude Code takes the work it says *1 task running* again, with the pulsing dot.
A check waits under Results as *Waiting for Claude Code*: its search runs in Margin at once, and only its search
words, parts and judging wait. It finishes when the answers arrive, even if the app was closed meanwhile.

**Stopping.** A run can stop at any moment (a usage limit, a closed laptop, Ctrl+C). A batch taken and not answered
returns to the queue after 30 minutes, and the next `/margin-run` continues where it stopped; nothing is lost. When
answers stop arriving, Margin says *Paused at 340 of 7,868 labels. To go on, type /margin-run Pilot in Claude Code.*
*Stop* on a waiting page takes its tasks that no session has taken yet out of the queue (a waiting check is removed
whole).

**Models that suit your Claude plan (0.13.10).** On Claude Code the recommended model of each task follows the plan
Claude Code is signed in with. Margin finds it by itself, in the background (from `claude auth status`, when the app
starts, when it looks at the queue and before a run), and work that waits follows a new plan at once:

| Plan | Recommended models |
| --- | --- |
| Free | No Opus or Fable. Haiku for most tasks (search words, splitting a hypothesis, theme names, references, a draft's claims, labels, links), stepping up to Sonnet when unsure; judging excerpts and second opinions on Sonnet. |
| Pro (and a plan not known yet) | As before: Sonnet for most tasks, Haiku for the many labels and links, Opus for second opinions and the hard cases. |
| Max, Team, Enterprise | Opus for most tasks, checks included. Haiku and Sonnet only where there are many tasks at a time and speed matters: labels and links (Haiku), references (Sonnet, stepping up to Opus). A check on Opus has no stronger model unless *Let the auditor use Fable* is on. |

A model you chose for a kind of task (*AI model per task*) comes first on every plan. Should Claude Code name the
plan wrongly, or not at all (signed in with an API key), set it under *Settings → Technical → AI model per task →
The recommendations follow*. The Claude API and local models do not follow the plan. Note that Claude Code itself
may need a paid plan.

**Fable.** The auditor (second opinions, and checks read again by a stronger model) runs on Opus (on a Free plan:
Sonnet). *Let the auditor
use Fable* switches it to Fable. In Claude Code, Fable can be billed from usage credits instead of your plan; its
model picker then says *Requires usage credits*.

**What is recorded.** Claude Code gives no seed and no model digest, so its answers are not repeatable the way a
seeded local model's are. Each answer records its route (Claude Code), helper, the model set for that helper,
prompt version, whether it stepped up, and when its batch was claimed and answered; *How these results were made*
lists them per kind. The acceptance runs (`margin acceptance queue … --again`) measure how much two readings differ.

**Model tests with Claude Code.** *Compare a sample* (profile labels) and `margin benchmark` put their
tasks in the queue of a temporary copy of the project, named on the waiting page (type `/margin-run "<that
name>"`). The copy is removed when the test ends, so nothing is stored; the labels are read by the label model, and
the model test answers each kind on its own model. *Test: repeatable answers?* says that Claude Code takes no seed.

**The connector's queue tools** (used by the plugin; not meant for a chat): `queue_status`, `next_tasks` (a batch,
claimed for 30 minutes), `submit_answers` (each answer quote-checked: stored, or its problems), `release`.

---

## 7. Data

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
| task_claims | 0.8: the batches of queued tasks handed out to Claude Code: who took them, when, model, helper; `tasks.queued`, `claimed_by`, `step`, `again` and `results.route`, `helper`, `step` belong with it |
| meta | Thresholds, and the corpus version (search indexes are rebuilt when it changes) |
| drafts, draft_claims, draft_sent | Margin 0.1: your drafts (text, AI setting), their claims (offsets in `drafts.text`, the quote, the claim checked, who found it, the hypothesis that checks it) and every time Claude read part of a draft |
| bib_items, bib_links | 0.13: the bibliography's works (title, creators, year, DOI, web address, Zotero link, the files Zotero keeps with their checksums) and which document each is (`status`: `auto` for the same file or DOI, `probable`, `confirmed` or `rejected` by a person; `method`: `file`, `doi`, `title`, `person`); where it came from is in `meta` (`bibliography`); 0.13.3: `documents.file_title` keeps the file's own title while a linked work's title replaces it (`meta` `titles_version` rebuilds the keyword index) |
| vca_targets, vca_refs, doc_refs, claims, claim_targets, evidence, interactions, vca_claims, reviews | ENLENS's SDG pack: empty in Margin, kept so a project copied from ENLENS opens |

Open it with any SQLite tool. Offsets in `evidence` and `verifications` index into `documents.text`. Removing one
document keeps past checks intact (each check stores the passages it showed); removing all documents also removes
every check.

**Moving to another computer (0.10).** *Projects → Move Margin to another computer → Download everything (.zip)*
makes one file with every project (each as its own project zip: database, uploads, original files) and the settings.
A saved Claude API key is left out, and so are quick looks not kept; projects used in place from another folder come
along as copies. On the new computer, install Margin and choose the file under *Import from another computer* on the
first screen (or *Projects → Import a project (.zip)*, which takes both kinds of zip). Each project keeps its name
(`name (2)` when the name is taken). The settings come along only when the new computer has no project yet, and on a
`--local-only` installation never the choice of a cloud AI.

---

## 8. Privacy and copyright

**Zotero (0.13).** The Bibliography page reads Zotero through the Zotero app's own connection on this computer
(`127.0.0.1`, port 23119), never through Zotero's servers, and only reads. The works' details stay in the project;
nothing about them is sent to Claude.

**Finding literature (Margin).** *Find literature* sends search words (and, to follow citations, the DOIs of your
documents) to OpenAlex, and if you choose Crossref, Semantic Scholar or Unpaywall, after showing them to you. It sends
no text of a document or draft, uses no AI, never runs with `--local-only`, takes nothing from a draft or document
whose AI setting keeps it on this computer, and sends your e-mail address only if you gave one in Settings.

### Who may read each document with AI (0.11)

One project can mix documents Claude may read with documents that must stay on the computer: a licensed PDF, an
interview transcript. Every document has one of three settings:

| Setting | Who may read its text |
| --- | --- |
| *Claude may read it* | the AI you chose: Claude Code, the Claude API, or a local model |
| *Only a local AI* | a model server on this computer, or you |
| *No AI* | you only; Search, the keyword Profile, Concepts and Themes without AI still work |

> Documents you mark as local stay on this computer. Margin never sends their text to Claude, in any feature, and
> shows you how much of every other document it has sent.

**Where you set it.** When you add documents, the page asks *Who may read these documents with AI?*; one answer
covers everything added at once. The first answer in a new project becomes its default (nothing is preselected the
first time); later the default is preselected. On the Documents page the column *AI* has a small dropdown per
document; tick several documents to change them together. A note (*Why*, for example "publisher licence") is kept
with the document and exported with the project; it changes nothing. For large corpora, a `manifest.csv` may have
`ai_access` (cloud, local or none) and `ai_note` columns. Projects made before 0.11 keep *Claude may read it* for every
document, so nothing changes until you change it; a project zip made before 0.11 asks once when it is imported. On an
installation without cloud models (`--local-only`) the default is *Only a local AI* and Claude is not offered.

**What happens in each feature.** Finding passages is unchanged: every document competes for every check. Only the
reading is split. In a check, Claude reads the excerpts it may; those marked *Only a local AI* go to the local model
chosen in *Settings → AI → Local model for restricted documents*; those marked *No AI* (and the local ones when no
local model is chosen, or it cannot be reached) are shown as *Waiting for your judgement*, with your own judgement
open on the excerpt. The round stays one round, and each excerpt says who read it. The answer counts every
excerpt; the AI's written note speaks only for the excerpts it read, and is told how many others there are. A second
opinion, reading an excerpt again, the Profile's AI pass, theme names, concept links and references follow the same
rule: a task takes the setting of the most restricted document it touches. A theme whose passages are all
restricted is named by the local model or keeps its key terms; two concepts found only in restricted documents are
linked by the local model or not at all (a term's words are words of the documents). A check started in a Claude chat
(the connector) shows Claude only the excerpts it may read; the result page then offers *Read them now on this
computer* for the local ones. When the local model's answers for its excerpts cannot be used (three tries), the
result says so and shows them without a judgement; *Read them again on this computer* tries once more (0.11.1, for
instance after choosing another local model), or you judge them yourself. The check's written summary is always the
main model's, never the local model's note. Search by meaning: an embedding server on another computer does not
receive the restricted passages (they are found by their words).

**How it is enforced.** In code, where every AI task is made and run, never by an instruction in a prompt: each task
is labelled with the most restricted setting of the documents it names, a task is refused before any model is asked
when its setting does not allow that model, and the queue for Claude Code only ever hands out tasks Claude may read.
The connector's tools (search, concepts, document profiles, checks) give Claude counts instead of restricted text,
and show a document marked *No AI* as *Restricted document 3*, because a title can name a person. The Claude Code run
that Margin starts may not use Claude Code's own file, shell and web tools and starts in an empty folder, away from
the projects' databases.

**What Claude has read.** Margin writes down every passage at the moment it leaves for Claude (Claude Code, the Claude
API, a Claude chat through the connector). The column *Sent to Claude* shows the share of each document's text;
click it for the passages, when and for which feature. *Settings → Technical → What was sent to Claude* downloads the
whole list (CSV), for example for a data management plan. For a project made before 0.11 the list starts with the
results Margin recorded then. Changing a document to *Only a local AI* applies to everything not yet answered; what
Claude already read stays in the results and the list. Removing a document takes its passages out of everything
still waiting for Claude Code (0.11.1). A check that was waiting for Claude Code when a document's setting changed
stops waiting and says so: the excerpts are then for the local model or for you.

**A cap.** In a document's dialog you can set *Claude may read at most N %*. Once Claude has read that much, its
further passages are treated as *Only a local AI*. It is checked when tasks are made, so a check that is running can
go over by one round of excerpts.

**Your Claude account.** *Set up Claude* and *Settings → AI* show *What happens to the text Claude reads*: on a
personal plan (Pro, Max) consumer terms apply, and Anthropic may use your sessions for training when the account's
model-improvement setting is on (turn it off at claude.ai/settings/data-privacy-controls before Claude reads licensed
documents); Team, Enterprise and the Claude API are under commercial terms. Documents that must stay in the EU:
mark them *Only a local AI*. The panel cites Anthropic's data-usage page and the date it was checked; that page is the
authority.

### Models and licences

With a local model nothing leaves the computer. With the Claude API (app or `--backend anthropic`) the hypothesis and
the passages read are sent to Anthropic; with the connector, the passages shown to Claude are part of your chat; with
Claude Code (0.8), the passages inside the tasks it takes are sent to Anthropic on your own plan. For
paywalled literature, check with your library whether your licences allow text and data mining with an outside
service, or keep to a local model.

---
## 9. Limits

- Grades and claims are model output until reviewed. The quote check proves the quoted words exist; it does not prove the fields
  follow from them.
- The corpus is what you provide.
- Text comes from the PDF text layer. Tables and figures are read as text, which is often garbled; scanned pages need OCR.
- "Nothing found" is about the passages read, not the documents: read more passages or search with other words.
- Verification reads only the top `--k` passages per claim (a hypothesis check: `k` per claim per round; semantic search
  narrows the gap). In the pilot, a manual search of the full cited documents
  for 10 claims with no graded passage found partial support for 2 and a weak contradiction for 1; the other 7 had
  nothing anywhere in their sources. Retrieval misses some evidence, mostly where the source uses other words
  ("repurposing" for "upgrading").

## 10. Troubleshooting

| Problem | Fix |
| --- | --- |
| Many quotes fail | Look at `results.errors_json`. Usually the model tidied PDF text; the retry prompt tells it to copy exactly. |
| Tasks stuck as `exported` | `margin requeue KIND`. |
| "No Claude API key" | Export `ANTHROPIC_API_KEY` or enter it in Settings, or use a local model or the file queue. |
| "No local model server is running" | Start Ollama (or `ollama serve`) or LM Studio's server; `margin detect` lists what is found. Or choose `--backend baseline` / the offline demo to try things out. |
| "Cloud models are switched off" / "Allow cloud models first" | The Claude API sends the passages read to Anthropic, so the app asks you to allow it first (Settings → Model service). |
| "The local server … has no model" | Load the model in LM Studio, start llama.cpp with it, or name another with `--model` / in Settings. |
| A semantic search error about vector sizes | The embedding model changed since the index was built: Sources → *Build semantic index*. |
| "Remove all documents" is refused | The project was copied from ENLENS and holds results of its SDG pack (extracted claims, VCA verifications). Remove documents one by one, or run `margin --ws FOLDER reset-corpus --yes` if you mean it. |
| Empty document, or "Scanned: no text" | No text layer (scanned). Install Tesseract and the `ocr` extra (section 1) and add the file again, or run OCR yourself (`ocrmypdf in.pdf out.pdf`). |
| The Margin icon is a blank square (macOS) or a plain shortcut (Windows) | It was made before 0.10.2 without Pillow. Open Margin once with 0.10.2 or later: it gives the icon its picture (macOS: if Finder still shows the blank one, `killall Finder`). Or make the icon again: `margin-gui --make-launcher`. |
| Settings shows an older version after updating | That copy was still running. Choose *Restart now* on the notice at the top of the page (0.13.1), or *Quit Margin* and open Margin from its icon (0.10.2 does this by itself when nothing runs). |
| There is no *Update* button in the sidebar | It shows only when there is an update (0.13.6). To look now, or to see why a look failed: *Settings → Technical → Check for updates*. |
| *Update* says it cannot update | It says why. Offline: try again later. Files of a git copy edited by hand: keep them with `git stash` (or undo them), then update. One-line install on Windows: choose *Quit Margin* and run the install line again in PowerShell. |
| The page keeps saying *Starting Margin …* | After 90 seconds it says Margin did not come back: open it again from its icon (or with `margin-gui`), and look at `logs/margin.log` in the data folder for the reason. |
| Double-clicking the Margin icon does nothing | Look at `logs/margin.log` in the data folder. Run the install line again (one-line install), or `margin-gui --make-launcher` again after moving or reinstalling Python (git copy). On macOS, if the icon was copied from another computer, right-click it and choose *Open* once. |
| The install line stops with "does not match the release's checksum" | The download was cut off or changed on the way; nothing was installed. Run the line again later. |
| The install line on Windows says uv could not install Margin | Margin is probably running: choose *Quit Margin* in it and run the line again. |
| *Set up Claude* cannot install Claude Code | No network, or the installer was blocked. Install it with Anthropic's set-up page (linked under *Technical details*), then press *Set up Claude* again. |
| Claude Code answers with the wrong Claude account | The sidebar card (hover *Claude, on your plan*) and *Settings → AI* name the account it uses. To switch, type `claude auth logout` in Terminal or PowerShell, then press *Check again* and *Set up Claude* in *Settings → AI*: it opens the sign-in window, where you sign in with the other account. |
| *Set up Claude* keeps waiting for the sign-in | Finish signing in in the window it opened (and in the browser page that window opened), then press *I have signed in*. No window? Open Terminal or PowerShell, type `claude`, and sign in. |
| "The original file is no longer at …" | The file was moved or renamed after it was added; the app still has its text. Put it back, or add it again. |
| The app says it cannot reach Ollama | Start the Ollama app (or `ollama serve`) and check the address in Settings (default `http://localhost:11434`). |
| "Ollama has no model ..." | Download it: `ollama pull <model>`, then pick it again in Settings. |
| Test connection warns about Ollama's cloud | The model runs on Ollama's servers, which do not support the JSON format the app needs, and the text leaves your computer. Pick a model downloaded with `ollama pull`. |
| "This task needs about N tokens of context" | Set the context length to automatic in Settings → Technical (the default), or raise it (`--num-ctx`). 16,384 covers every task of the app. |
| A check with a local model takes very long | The progress panel shows where the time goes. Long "loading the model and reading the prompt": the model is too large for the memory (check Activity Monitor) or the computer is swapping. Long "reasoning": set *Reasoning* to off. |
| "… sent nothing for 600 seconds" | The model did not start or stopped answering: usually too little memory. Close other apps or choose a smaller model. |
| "… used its whole allowance … on reasoning" | The model kept reasoning without answering. Give reasoning a budget (Settings → AI, the default 1,500 tokens), choose *Only when judging excerpts*, or set it off. |
| A check with reasoning takes half an hour | Set *Reasoning* to *Only when judging excerpts* with a budget (1,500 tokens is the default; lower it for a slow computer). |
| "… got stuck writing blank space" | A known failure of some models with fixed-format answers. Try again, set *Reasoning* to off, or choose another model. |
| "The Claude API rejected the key" | Copy the key again from console.anthropic.com; check it has credit. |
| Two workers' answers ended up in one results file | Give each worker its own scratch folder. Move the stray lines to the right file; `import-results` accepts any order. |
