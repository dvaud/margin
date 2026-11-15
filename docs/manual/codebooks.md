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
3. Choose how it starts, then *Create* (*Next* for themes and theory). The editor opens (for theory, the draft's page
   first).

| Start | What you get |
| --- | --- |
| *Start fresh* | An empty codebook: add codes and groups yourself. |
| *From the themes* | You tick themes found in the documents; each becomes a draft code (see below). |
| *From theory documents* (0.18.1) | The concepts of the theories you read your documents through, shaped on a page of their own before they become codes (see below). |
| *A copy of a codebook* | The SDG targets, or one of yours, to change. |
| *From a CSV file* | A spreadsheet saved as CSV (see below). |
| *From NVivo, ATLAS.ti or MAXQDA* | A REFI-QDA codebook (`.qdc`), or the codebook of a REFI-QDA project (`.qdpx`) (see below). |

**From the themes.** Each theme you tick becomes a draft code with a short name, its description where the AI named
the theme, its key terms as *Words it is matched by* and its best passages as examples. Removed themes are left out.
When the codebook is kept with all projects, the themes of every project are offered. Find the themes first (*Themes*
in the sidebar): it takes seconds and needs no AI.

**From theory documents (0.18.1; rebuilt as a framework draft after 0.19).** The theory you read your documents through
becomes a **framework**: its concepts in groups, each with the theory's own words, a definition to code with, and
passages of your documents that may show it. You choose and shape them on a page of their own, and only then make the
codebook. A project holds one such draft at a time; it waits on its page while you do other work, and the Codebooks
list says so (*A codebook from theory is being drafted*, with *Continue the draft*).

1. *Next* asks which documents to draw on: one theory, or several (a framework built from five authors, say). Those
   marked as theory are ticked to begin with ([Theory documents](explore.md#theory-documents)). *What do you want to
   find out?* is optional: a sentence or two about your study, so that the AI later puts the concepts in its words.
   *Start the draft* opens the page. If a draft is there already, you are asked first: *Continue the draft*, or *Start
   again* (that draft and what you changed in it are removed; what the AI read is kept, so reading again costs
   nothing).
2. **Without AI** the page starts from what the documents define outright: the entries of a glossary (a heading such
   as *Glossary*, *Definitions* or *Key terms* over lines like "Stock: an accumulation of …"), the terms the text
   defines ("by a reinforcing loop we mean …", "X refers to …"), and a heading's phrase when it has two words or more
   or the text has a sentence that defines it. A term two documents both define is one concept, with each author's
   sentence. Glossary entries start in the codebook. Words a text merely uses often are no longer offered. This is a
   start, not a framework, and the card *The theory* says so.
3. ***Read the theory*** lets the AI read the documents whole, in parts (the line under the button says how many and
   who reads them), and then put one framework together from what all the authors define: at most 30 concepts in up
   to six groups, each with its meaning in plain words, *When to use it* and *When not to use it* written for your
   documents, and the words your documents are likely to use for it. Every quote is checked against its document, and
   every concept rests on sentences the AI drafted from the parts. The concepts the AI holds central start in the
   codebook; the others wait below a thin line in their group (*Also in the theory, not in the codebook*). What the AI
   drafted and left out of the framework (the authors' methods, schools of thought, sentences that define nothing) is
   folded away under *N concepts set aside by the AI*, each with *Add*. Reading takes minutes: you can leave the page,
   and *Stop* ends it with the draft as it was. A document's own AI setting decides who reads it: Claude, only a local
   AI on this computer, or no AI (then only the terms it defines outright are used, and the card says so). The reading
   is written in the research log. *Read again* (under *Your question, and reading again*) keeps every concept you
   changed, marked as done, added or kept examples for, and replaces the rest.
4. **Shape it.** Each group is a card whose name you can change; *All*, *In the codebook* and *Not in the codebook*
   filter the rows. A row says how many of your theory documents say what the concept means (when more than one),
   in how many of your own documents its words are found (*in 11 documents*; *in no document* is a reason to try
   other words or leave it out), how many examples you kept and whether you marked it *Done*. A row's *Add* and
   *Take out* put a concept in the codebook or take it out. Open a concept to see, top to bottom:
   - *In the theory*: each source sentence, with its document (it opens the document at that place) and page;
     *Remove this quote*, and *Look for more in the theory*, which lists the best sentences of each theory document
     for the concept's name, each with *Add this quote*.
   - The code's fields, named as in the editor: *Name*, *Group*, *Definition*, *When to use it*, *When not to use it*,
     *Words it is matched by*. A field still in the AI's words carries the *AI draft* mark until you rewrite it.
   - *In your documents*: passages of your evidence documents that may show the concept, found by its words without
     AI (never from a theory or working document), the words found marked and listed (*Matched: skills, repair
     knowledge*). A word counts as you wrote it, a phrase as a phrase; a question of an interview guide, a run of
     references and a table's row are passed over. *Keep as an example* keeps one (at most
     eight, as a code keeps), *Hide this passage* sets one aside, *Show other passages* asks again, and *Every place
     these words occur, in Search* opens the Search page. The passages follow *Words it is matched by* as you type.
   - *Mark as done*, *Next concept* (the next one in the codebook), *Merge into…* (the other concept takes this
     one's quotes, examples and words; the toast has *Undo*), and *Remove from the draft* for a concept you added.
5. **Add a concept by name** (no AI): type a name and *Look it up*; tick the sentences of the theory documents that
   define it (none is fine: you write its definition yourself), then add it. It joins *Concepts without a group*, in
   the codebook, opened.
6. ***Make the codebook*** (in the bar at the foot, which counts the concepts in the codebook, how many are done
   and how many have examples) first says what will happen: how many concepts become codes, how many of them are
   still as the AI drafted them, and that the draft ends here (the concepts not in the codebook are not kept; what
   the AI read is, so a new draft from the same documents gives the framework again at once). It then makes a code
   of each concept in the codebook and opens the editor. *Draft settings*, at the top of the page, holds the
   codebook's *Title*, its *Short name* and where it is *Kept*. A code's
   description is its definition followed by the theory's sentence with its document and page ("In the theory: “…”
   (Title, p. 12)"), and the other documents that define it; *When to use it*, *When not to use it*, the words and
   the examples come with it, and the framework's groups become its groups. Fields still in the AI's words keep the
   *AI draft* mark in the editor. Two concepts in the codebook with one name cannot both become codes: rename or merge
   one. *Discard the draft* removes the draft without making anything.

Every change on the page is kept in the draft as you work. If the draft changed in another window, the page says so
and shows it as it is now.

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
is in each group, *Add a group* at the foot. *Remove group* takes a group out: its codes stay, with their labels, under
*Codes without a group*, and each one's *Group* field moves it to another. *Codebook settings* holds the title, what one code is called
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
draft, one quiet line under the codebook's title says how many: *3 codes still hold the AI’s draft. A downloaded file does
not carry that mark: say so to whoever you send it to.* It counts what is on screen and goes when you have rewritten
them; the download is still one click. `margin export-qdc` and `margin export-qdpx` print the same sentence after
their usual answer. *History*
lists its earlier versions, to compare and restore ([earlier versions](notes-and-log.md#earlier-versions)).
