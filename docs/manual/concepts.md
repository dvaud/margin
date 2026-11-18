[Manual](../MANUAL.md) › Concepts and the concept map

# Concepts and the concept map

> **In short**
> - The **glossary** gathers the terms your documents use into concepts, with no AI; the **map** shows which concepts
>   are mentioned together more often than by chance, in named groups, with the links between them.
> - Links (*is part of*, *leads to*, *needs*, *shapes*, *clashes with*, …) are proposed from the text and count only once
>   you accept them; you can add your own.
> - The map's groups are named by their concepts until you rename them; the AI names them only when you ask.
>   *Download the map* saves it as a picture (PNG or SVG).

## Concepts

A **glossary** of the terms the documents use (one or more words, found by the C-value method; running heads and page
furniture are left out), grouped into **concepts**:

- abbreviations and their long forms ("proton exchange membrane (PEM)");
- wordings close in meaning (with an embedding model);
- links found in the sentences themselves (0.18.1, see below);
- links the AI proposes and you accept, and links of your own.

A concept card shows how the documents write it (*Not the same* splits a wording off), which documents discuss it and
where it first appears, every line where it occurs, and related concepts (the same, broader, narrower, related,
often together). *Ask the AI for other wordings* lists wordings the documents use: add them, or say *Not the same*
and they are not proposed again.

**Links found in the text (0.18.1).** When the glossary is made, Margin proposes links from the sentences, without AI,
only between two terms the glossary knows and only when the connecting words alone stand between them:

| The sentence says | The link proposed |
| --- | --- |
| "X such as Y, Z and W" | X is broader than Y, Z and W |
| "Y, Z and other X" | Y and Z are kinds of X (narrower) |
| "X, also called Y", "X (also known as Y)", "X, i.e. Y" | the same |
| "X leads to / causes / reduces / increases / undermines / results in Y" | X *leads to* Y |
| "X requires / needs / depends on / relies on Y" | X *needs* Y |
| "X shapes / influences / affects / determines Y" | X *shapes* Y |
| "X conflicts with / clashes with / is at odds with Y" | X *clashes with* Y |
| "X instead of Y" | X *replaces* Y |

Words inside quotation marks are passed by. Each proposal, marked *found in the text*, shows the sentences it was
found in with their document and page, and waits for *Yes, right* or *No* like any proposed link. English sentences
only, for now. On a concept's card the links are listed by kind: *What it leads to*, *What leads to it*, *What it
shapes*, *What shapes it*, *What it needs*, *What needs it*, *What it replaces*, *What replaces it*, *What it clashes
with* and the rest. *Add a link yourself* and *Another relation…* offer every kind, *shapes*, *is shaped by*,
*needs*, *is needed by* and *clashes with* among them. *Clashes with* reads the same from both concepts.

**Paths to another concept (0.18.1).** On a concept's card, type another concept and *Find the paths*: the shortest
chains between them, through links you accepted and concepts the documents mention together more often than by chance
(pointwise mutual information). Each step shows the passages that mention both its concepts: a way into an argument
the corpus already makes. A list, not a drawn map.

**Over time and across groups (0.18.1).** *By year* shows, for each publication year, how many documents mention the
concept, how they word it and what it is mentioned with. The year is that of the work the document is in your
[bibliography](bibliography.md); documents without one are counted apart. *Compare two sets of documents* does the
same for two sets you tick (policy against academic, one country against another); the sets are not kept.

**The concept map.** The *Map* tab beside *Glossary* draws the concepts mentioned in the most passages (60 at first;
*Concepts on the map* gives 30 to 150) as a map, made on this computer without AI:

- **A line** joins two concepts the documents mention together, in two passages or more, more often than by chance
  (pointwise mutual information): two common words that turn up together only as often as chance would give are not
  joined, however many passages they share. The thicker the line, the more often than by chance. Each concept keeps
  its strongest lines only, so the map stays readable.
- **Groups** are concepts that are mentioned with each other more than with the rest. Each group has a name (see
  *Groups* below), which the legend gives with its number of concepts and, on a map 600 pixels wide or more, the map
  itself, over or under the group. Groups 1 to 5 are each a filled shape in a colour of their own (circle, square,
  diamond, triangle, hexagon); groups 6 to 10 are the same five shapes outlined, in the same five colours; groups 11
  and on, the smallest, are all grey stars (*The 4 smallest groups* in the legend), and *Groups* under the map names
  each. A concept with no line is in no group: a grey dashed circle. So no two kinds of mark differ by colour alone.
- **Links** (those you accepted or added, the AI's confident ones and the abbreviations) are darker lines with their
  words; the end of the line says the kind: a diamond at the whole for *is part of*, a filled arrow for *leads to*, an
  open arrow for *shapes*, a ring at the one needed for *needs*, a cross at the one replaced for *is used instead of*, a
  bar across each end for *clashes with*, and a plain line for *is related to*. The legend shows each kind on the map
  with its line. Two concepts with links of two kinds (two wordings you joined, or two sources) have one line, with
  the end of the first kind in that order and the words of both. Two wordings you joined as *the same* are one
  concept, so they are one mark.

Choose a concept to open its page. Choose a line to see, under the map, the passages that mention both (and, for a
link, its sentences); *The lines as lists* gives every line and the links as lists, with *Show the passages* on
each. Pointing at a concept dims everything it is not joined to. Marks that would cover each other are
pushed apart a little, and on a narrow screen they are smaller.

**Zoom.** *Zoom in*, *Zoom out* and *Whole map* stand over the map (up to four times the size). You can also hold
*Ctrl* (or *⌘* on a Mac) and turn the wheel, pinch on a trackpad, or press **+**, **−** and **0** (the whole map)
anywhere in the map. Zoomed in, drag the map to move around it, or press the arrow keys when the map itself has the
keyboard's focus; a concept you reach with *Tab* comes into view. Words grow more slowly than the map, so they stay
readable, and from twice the size on every concept's name shows. The zoom stays while you rename groups and is undone
by other filters. A downloaded picture is always the whole map.

When fewer than 30 passages are counted (one short document, a narrow filter), the page says so: a line that rests on
two or three passages can look strong by chance.

The filters above the map narrow the passages it counts, and the map is drawn again from those passages alone:
*Documents*, a *Theme* (of the latest set, with your merges and moves), a *Code* of a codebook (the passages labelled
with it), and the years a document was *Published from* and *until* (from the [bibliography](bibliography.md);
documents without a year are then left out). The same project and filters always give the same map. On the command
line: `margin --ws myproject concept-map`.

**Groups.** Under the map, *Groups* lists every group with its concepts and their passages. Each group is named by
its two most central concepts (*Office days and team days*) until you rename it. A name stays with its group between
visits, and when the groups are found again (new documents, other filters, another number of concepts), as long as
the group still holds most of the same concepts. Each name says where it comes from: *named by its concepts*, *named
by you* (or by a colleague, by name), *AI draft* or *named by the AI, accepted by you*.

- *Rename* opens *Rename the group*: type a *New name* (up to 60 characters) and *Save*, or *Use its concepts as the
  name* to go back to the name made from its concepts.
- *Name the groups* (*Name the other 2 groups*, *Name the groups again*) asks the AI to draft a short name for each
  group still named by its concepts (*again*: for every group but those you named). It only puts the work in the
  queue: the AI run panel opens under the button, and nothing runs until you press its own *Start Claude Code* (or
  the start of your local model, for documents marked *Only a local AI*). The AI reads a few passages of each group
  where its concepts are mentioned together, only from documents it may read (a document marked *No AI* is never
  sent; when no document may be read by an AI, the groups can only be named by you), and drafts a name with a quote
  that is checked against the passage. Names you gave yourself are never touched.
- An AI's name shows at once as the group's name, always marked *AI draft* (and *(AI draft)* on the map and in a
  downloaded picture), until you press *Use this name* (or *Use all 4 names*) or rename it. *What the AI’s name rests
  on* shows its quote and where it is. A group the AI could not name after three tries keeps the name made from its
  concepts, and the page says why, with *Name them again*.
- A group that lost or gained a third or more of its concepts since it was named, on the map with the same filters
  and number of concepts, is marked *changed since it was named*, with the concepts that left and joined; *Keep the
  name* gives the name to the group as it is now.
- A name whose group is not on this map is kept under *2 names kept for groups that are not on this map*, and comes
  back with its group; *Forget this name* removes it.

**Group names with a team.** Group names go with the rest of the project: in a copy for a colleague, through the
shared folder and a team's storage space. The groups themselves are not sent: each copy finds them from its own
counts, so a group can differ a little between two copies. A name keeps its group's concepts, and on another copy it
goes to the group there that holds most of them, by the same rule as on yours; a name that fits no group there is kept
under *names kept for groups that are not on this map*, and comes back with its group.

- When two people name the **same group**, the map shows the later name on every copy, and the group says *Also named
  “…” by …* with the other name, its author and the date; *Rename* lists it too, with *Use this one*, and *Remove*
  takes the other name away on every copy (with *Undo*). Nothing a person typed is lost by itself: when two people
  changed the same name at the same time, each on their own copy, the later change counts and the other stays as a name
  of its own. A change made after seeing the other (a rename of a colleague's name) simply replaces it.
- Between two different names for one group, a name a person gave (or an AI draft a person used) comes before an AI
  draft, whenever the draft was made.
- *Keep the name* keeps it its author's name; the group says who named it, not who kept it.
- A name you remove (*Use its concepts as the name*, *Forget this name*) is removed on your colleagues' copies too,
  unless someone renamed it after you removed it.
- The AI's quote for its name goes with the name, but only to a copy that holds the quoted document. The AI's work
  that drafted it (its task) stays on the computer it ran on.
- Times are compared as each copy records them, but a change made after seeing another is always counted as later,
  whatever the computer's clock says; a name dated more than ten minutes ahead of your clock waits until it is not.
- Names are trusted as your team's other work is: a colleague's file may carry names in a third person's name (as it
  carries their reviews), but never changes one you changed last in yours.

**Download the map.** *PNG* and *SVG* at the top right save the map as a picture, made in the page (nothing is sent
anywhere): the title (*Concept map of* and the project's name), what was counted, the filters when one is set, the
groups and the lines with their names, the map as a wide window shows it, and a foot that says what a darker line and
*(AI draft)* mean, and with which Margin version and when it was made. The picture is always light on white, whatever
theme the app is in. The SVG stays sharp at any size and opens in a drawing program; the PNG is 2,400 pixels wide, for
slides and documents. The file is named after the project and the day: `my-project-concept-map-2026-11-17.png`, with
`-filtered` before the date when a filter is set.

Theory and working documents are left out of the glossary, of key terms, of both cards and of the map.

**The AI's links.** When the AI judges how two terms relate (*How concepts relate*, link tasks), it may now propose
any kind the text patterns and you can give: *same*, *broader*, *narrower*, *needs*, *shapes*, *clashes with*,
*related* or *different*, each with a quote from the passages of both terms. Its proposals are marked as the AI's
(with how sure it is), drawn on the map in their kind's line when it is confident, and yours to accept, change or
reject on the concept's page, as before.

### Words the glossary leaves out

No term starts or ends with a common word of its passage's language: "because" and "themselves" in English, "dan",
"wel", "maar" and "ja" in Dutch. Margin tells each passage's language by the common words it uses (lists for 58
languages come with it; a passage too short to tell, such as "Ja.", takes the language of the one before it). A Dutch
word that is also English ("net", "door") is left out only in Dutch passages, so "net zero" stays a term of an English
report. The key terms of themes come from the glossary, so they leave out the same words.

Under *Words the glossary leaves out* on the Concepts page:

- **Languages found**, with how many passages each. Switch one off to read its passages as English; a language with a
  few passages is often a table or a reference list. English common words are always left out.
- **Your own words**, one per line: a speaker label such as "Interviewer" or "R1", or a word that says nothing in your
  project. No term starts or ends with a word listed here; a phrase ("zeg maar") leaves out just that term.

*Save and update the glossary* makes the glossary again. Themes found before keep their key terms; the Themes page
says which of them are now left out, and finding the themes again gives key terms without them. Search is not
changed: it still finds every word.
