### Easier to read

- **A document's page opens with less on it.** Under the title stand its facts and *Open the original* in one line,
  then the bibliography's line. The file's name, and the work's name in the bibliography, show only when they say
  more than the title does. *Download a highlighted copy* stands at the right of the title, and beside it *More*
  holds the marks: *Mark as theory…*, *Mark as my working document…*, *Mark as non-scientific…* (and the ways back,
  *Mark as evidence…* and *Count as scientific…*). A document with no mark shows no row of mark buttons any more; a
  marked one still says so in its box, with the one button that takes the mark back. The bibliography's suggestion
  (*Your bibliography lists this as a blog post…*) keeps its line, its *Mark* and *No* now set apart, here and in the
  Documents list. Changes no result.
- **On a page that is one thing, the buttons stand on the back link's line.** A document's, a theme's and a
  codebook's buttons (*Download a highlighted copy*, *Rename…*, *Try it*…) stood beside the title and broke a long
  title a line early. They now stand at the right of *← All documents* (*All themes*, *All codebooks*), and the title
  and its lines have the page's whole width. On a narrow window nothing changes: the title first, the buttons under
  its lines. The design guide's page heads (`docs/DESIGN.md` 4.14) say so.
- **A menu is as wide as its longest row**, so a row such as *Mark as my working document…* stays on one line while
  the page has the room.

### Tests

- `tests/test_document_head.py`: the document page's head says the title once, puts the marks in *More* and leaves a
  notice one action; a menu takes the width of its rows and the project switch keeps the sidebar's; one item's head
  draws its back link's line first with the actions beside it, stacks when narrow, and a head without actions (a
  result) or of a place is as it was.

### For developers

- `pageHead()` gives a head with a back link and actions the class `page-head-item` and makes its back link's line
  (`.eyebrow`) a child of the head, before `.page-head-main`; every other head is unchanged. `doc-shared.js` has
  `repeatsTitle(name, title)`; `roleBox()` takes the head's element it fills with *More* as its fifth argument.
