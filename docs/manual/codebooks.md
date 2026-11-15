[Manual](../MANUAL.md) › Make your own codebook

# Make your own codebook

> **In short**
> - A codebook is your list of codes: each with a definition, when to use it and when not, the words it is matched by
>   and examples from your documents. *Codes* › *Codebooks* makes, changes and removes them.
> - Start fresh, from the themes already found, from a copy of another codebook, from a CSV file, or from a codebook
>   made in NVivo, ATLAS.ti or MAXQDA (`.qdc`).
> - Changing a codebook changes no result by itself: labels follow renames and merges, and wait when a code is removed.

## What a codebook is for

*Codes* › *By document* and a document's *Codes* panel look for the codes of a codebook, and a hypothesis can be
tagged with one of its codes ([Explore your documents](explore.md#codes)). The 169 SDG targets ship with Margin; they cannot be changed, but
you can make a copy and change that. A codebook stays a CSV file, so it still opens in a spreadsheet.

The page lists *Your codebooks* and those that ship with Margin. Each card says how many codes it has, where it is
kept, how many labels and checks use it and whether *By document* uses it. A codebook file that cannot be used is listed
above them, with the reason.

## Make one

1. Press *New codebook*.
2. Give it a *Title* (the *Short name*, the file's name, follows it) and choose where it is *Kept*: *With this project*,
   or *With all my projects* (every project can use it, and a change shows in each).
3. Choose how it starts, then *Create* (*Next* for themes and theory). The editor opens.

| Start | What you get |
| --- | --- |
| *Start fresh* | An empty codebook: add codes and groups yourself. |
| *From the themes* | You tick themes found in the documents; each becomes a draft code (see below). |
| *From theory documents* (0.18.1) | You tick the concepts of one or several theories you read the documents through; each becomes a draft code with its definition quoted from its theory (see below). |
| *A copy of a codebook* | The SDG targets, or one of yours, to change. |
| *From a CSV file* | A spreadsheet saved as CSV (see below). |
| *From NVivo, ATLAS.ti or MAXQDA* | A REFI-QDA codebook (`.qdc`), or the codebook of a REFI-QDA project (`.qdpx`) (see below). |

**From the themes.** Each theme you tick becomes a draft code with a short name, its description where the AI named
the theme, its key terms as *Words it is matched by* and its best passages as examples. Removed themes are left out.
When the codebook is kept with all projects, the themes of every project are offered. Find the themes first (*Themes*
in the sidebar): it takes seconds and needs no AI.

**From theory documents (0.18.1; several at once since 0.19).** Tick the documents the codes should come from: one theory, or several (a
framework built from five authors, say). Those marked as theory are ticked to begin with ([Theory
documents](explore.md#theory-documents)). With several, each document's concepts are listed in a section of their
own, and each becomes a group of codes named after the document. A concept that two documents both define (*practice*
in two practice theorists) is offered once for each, with each author's own definition; if you keep both, each gets
its document's title after its name, and you can merge or rename them in the editor. Margin offers each document's concepts, without AI, the surest first: the entries of its own glossary when it has one
(a heading such as *Glossary*, *Definitions* or *Key terms* over lines like "Stock: an accumulation of …"), the terms
it defines in its text ("by a reinforcing loop we mean …", "X is defined as …", "X refers to …", and "a feedback loop
is a …" for a phrase or a term that is also a heading), the terms its headings name, and the words and short phrases
it uses far more often than your evidence documents do. Each comes with its definition **quoted from the theory, with
its page** (the quote, then the document's title and the page), which becomes the code's description: the glossary's
own entry, or else the sentence that best says what the term means. The glossary's entries are ticked; in a document
without a glossary, the terms it defines are (none is ticked when a long text defines fewer than three: what it
defines outright is then as likely its case as its theory). Running heads, printer's marks, tables of contents and equations are
left out, and so are sentences that only start like a definition ("All it takes is a …") and things the text calls
by a general name once ("A tree is a system"). A theory that argues instead of defining gives a short list this way:
the dialog says so and points to *Draft with AI*. Under each concept, sentences from the **evidence documents** that use
its words are offered as examples, unticked: an example is kept only when you tick it, and never comes from a theory
document or from any of the documents you started from. So the labeller learns what a reinforcing loop looks like in your field, not in the theory's own examples.
Words set in italics are not offered (the readers do not keep slant).

**Draft with AI.** Beside the concepts found without AI, *Draft with AI* asks the AI to draft the theory's concepts (with several documents, each section has its own button).
It reads **the whole document**, a part at a time (about 22,000 characters a part: a book of 200 pages is some 19
parts, and the line under the button says how many; a model on this computer whose context length you set yourself
gets smaller parts that fit it, and one set too small for any part says so), and gives each concept a short name, its definition quoted
exactly from the theory with its page, and one line on why it is a concept of the theory and not one of its examples.
Every quote is checked against the document, and a definition must be at least three words that say more than the
concept's name. What the parts give is put together: a concept found in several parts is offered once, with the
sentence that defines it best, and the concepts the theory comes back to most come first (40 at most). They join the
list unticked and marked *AI draft*. A term of the glossary or one the text defines is not offered twice; a heading or
a frequent word the AI drafts too gets the AI's definition in its place; and once the whole document was read, the
words that were listed only for being frequent, that the AI did not draft and you did not tick, leave the list. If a
part could not be read (its quotes were not found after three tries), the message says how many. Read each concept
before you tick it. Examples still come only from your evidence
documents, never from the theory or the AI. The document's own AI setting decides who reads it: Claude, only a local
AI on this computer, or no AI, in which case the button is not offered and the dialog says why. The draft is written
in the research log, and asking again for the same document reuses the answers, part by part. Closing the dialog stops a draft that
is still running. Nothing changes until you tick concepts and make the codebook.

**The short names (0.16.1).** A code's name is one or two words of the theme's name when your documents allow it, as
short as an SDG goal's: "National green hydrogen strategies and markets" becomes *Hydrogen strategies*. Margin tries
the shortest names first and takes a longer one only when the shorter ones are too generic: when most of the passages
that use them are in other themes ("Green hydrogen" is everywhere in a hydrogen corpus). No AI is asked. Beside each
name, − and + make it less or more specific (*Strategies*, *Hydrogen strategies*, *Green hydrogen strategies*, …), and
*Shorter* and *Longer* move every ticked theme at once; the theme's full name is shown beside it. Two themes never get
the same code, and a name you gave a theme yourself is kept when it fits in 40 characters. A name marked *check it*
had no evidence either way: its words are rare in the documents, or the documents are in another language than the
theme names. You can still rename every code in the editor.

**From a CSV file.** The columns are in this table; `code` and `description` are required. A semicolon or tab may separate
the columns, and a file saved in a Windows code page (a spreadsheet saved in Hungarian, say) is read correctly.

| Column | Holds |
| --- | --- |
| `code` | The code's name |
| `description` | Its definition |
| `group`, `group_name` | A short name for its group, and the group's full name |
| `when_to_use`, `when_not_to_use` | When the code applies, and when it does not |
| `keywords` | The words it is matched by, separated by `;` |
| `examples` | Quotes from the documents, one per line |

**From NVivo, ATLAS.ti or MAXQDA.** In the other program, export the codebook as a REFI-QDA codebook (`.qdc`), then
choose that file (a whole REFI-QDA project, `.qdpx`, works too: only its codebook is read, up to 14 MB in the app).
The title is the file's name until you type another. No AI reads the file. After *Create*, a summary says how many
codes and groups came in and what was folded or left out; then the editor opens. What maps to what:

| In the other program | In Margin |
| --- | --- |
| A code at the top with codes under it | A group of that name; the codes under it are its codes. |
| A code three or more levels down | A code of its top group (Margin's groups have one level); its place in the tree ends its definition, as in “(In the tree: Emotions › Positive › Joy.)” |
| A code with codes under it that has a description | A code as well as a group (or a step in the tree). Without a description, or when it cannot be coded, it is a heading only. |
| A code's description | Its definition. A code without one gets its place in the tree (or its name) as its definition: write a real one in the editor. |
| A name longer than 40 characters | Cut at a word; the whole name opens the definition. |
| Two codes of the same name | The second becomes “Name (2)”. |
| A code that cannot be coded, with nothing under it | Left out. |
| Sets of codes (ATLAS.ti's code groups) | Groups, when no code has codes under it and no code is in two sets; otherwise left out. |
| Colours, memos, the description of a heading that cannot be coded | Left out (a group has only a name). The summary counts them. |

A codebook Margin exported (*Download as .qdc*) comes back with its definitions, when to use and when not,
keywords, examples (their words: a `.qdc` does not carry an example's document and page), groups and group names.
Its label and direction setting are not in the file, so set them again in *Codebook settings*. Nor is the *AI draft*
mark: words you took from the AI's draft and had not rewritten come back unmarked, as if you wrote them. The title is
taken from the file's name, which you can change before *Create*. It comes in as a new codebook with its own history;
labels made with the codebook it was exported from stay with that one. A project file Margin wrote with several
codebooks asks which one to bring in.

## Change it in the editor

Codes sit in groups. Click a code to open it:

| Field | What to write |
| --- | --- |
| *Name* | Short: it is how labels and checks name the code. |
| *Definition* | What the code is about, in a sentence or two. The AI reads it when it labels. |
| *When to use it*, *When not to use it* | The boundaries, in your own words. |
| *Words it is matched by* | Words besides the definition for the keyword pass, separated by commas. |
| *Examples from the documents* | Paste words of a document exactly as they are there. Each is checked against the documents, and one that is not found is refused. |

To move a code, drag it by its grip, or use *Up* and *Down*. *Split* makes a second code from one (the first keeps its
labels); *Merge into…* sends a code's labels to another and takes the code out; *Remove* takes a code out. *Add a code*
and *Add a group* are in each group and at the foot. *Codebook settings* holds the title, what one code is called
(*code*, *theme*, *category*) and whether its codes are aims that a text can help or hinder, like the SDG targets.

**Draft from the examples.** A code with two examples or more (in different passages) can have its definition, *when
to use it* and *when not to use it* drafted by the AI: open the code and press *Draft from the examples*. The AI reads
only the passages that hold the code's examples, with its name and group: not the rest of the documents, not the
other codes, and not the definition you already wrote. The definition and *when to use it* each come with a quote
from one of those passages that shows them, checked like every quote. The draft appears under the examples, not in
the fields: *Use* (or *Use instead*) takes one part, *Use all of it* takes all three, and *Put it aside* drops it.
What you take is marked *AI draft*, under the fields and on the code's row, until you rewrite it in your own words;
the mark stays across saves while the words are still the AI's, and *Save* writes in the research log that the
wording came from the AI's draft. Each document's AI setting decides who reads its passage: an example in a document
marked *No AI* is left out, and one in a document marked *Only a local AI* is read by the local model (then the whole
draft is) or left out when there is none; the line under the button says how many were left out and why. Each example
is read where it was added: the same sentence in another document, with another AI setting, does not take its place.
A definition you keep is sent with every later label task, to whichever AI labels your other documents, as every
definition is: when the local model drafted it from documents marked *Only a local AI*, rewrite it if it gives away
what those documents say. The mark goes with the words when you copy the codebook, split the code, remove it and bring
it back, or keep a colleague's version of it. Asking again with the same examples reuses the answer. The editor is
complete without it.

Changes are kept as drafts until you press *Save*, where you can write *Why?* for the research log
([Notes, the research log and earlier versions](notes-and-log.md#the-research-log)). *Discard* throws them away. A
draft stays while you look at another page.

## Try it before you use it

*Try it* shows, without any AI, which passages and documents each code would pick by its words, so you can sharpen a
code before the AI reads anything. It warns about a code that matches nothing, and about one that matches a large part
of the documents, which is probably too broad.

## What happens to labels

An edit changes no result by itself: labels are moved, never made or deleted.

| You do | The labels |
| --- | --- |
| Rename a code, or merge two | Follow it. This holds in every other project that uses a codebook kept with all projects, when it is opened. A merge can be undone by restoring the codebook from before. |
| Remove a code | Wait under *Removed codes*, are not counted, and come back with *Bring it back*. |
| Reword a code after the AI labelled with it | Stay as they are. The code shows *earlier wording* and *Label them again*, which has the AI label only those passages again. |

*By document* shows a notice when the codebook changed since the keyword pass (*Find the codes again* takes seconds), when
codes were reworded and when removed codes' labels wait, each with *Open the codebook*.

## Where it is kept

The ⋯ menu beside the codebook has *Keep it with all my projects* and *Keep it with this project only*; for a codebook
kept with all projects, *This project's own copy (change it here only)*; and *Remove the codebook*, which asks *Why?*.
Labels made with a codebook stay when it is removed: they are results. *CSV* downloads the codebook (a cell that starts with `=`, `@` or a sign gets an apostrophe in front, so a spreadsheet
shows it and does not run it as a formula; Margin takes the apostrophe off again when it reads the file), *Download
as .qdc* downloads it as a REFI-QDA codebook for NVivo, ATLAS.ti and MAXQDA (each code with its definition, when to
use it, keywords and examples; [the whole project](explore.md#for-nvivo-atlasti-and-maxqda) goes too). Neither file
carries the *AI draft* mark: brought back in, the AI's words read as yours. So while codes still hold the AI's
draft, one quiet line beside the downloads says how many: *3 codes still hold the AI’s draft. A downloaded file does
not carry that mark: say so to whoever you send it to.* It counts what is on screen and goes when you have rewritten
them; the download is still one click. `margin export-qdc` and `margin export-qdpx` print the same sentence after
their usual answer. *History*
lists its earlier versions, to compare and restore ([earlier versions](notes-and-log.md#earlier-versions)).
