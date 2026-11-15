### New

- **Rename a document.** Open a document's row on the Documents page, or its page, and press *Rename…* to give it a
  title of your own. It is used everywhere in the project (the Documents list, results, Search, the bibliography and
  exports), and it stays when the bibliography links the document to a work or a new reading would find another title.
  *Use the title it had before* gives back the work's title, or the one read from the file, which the page still
  shows as *Title in the file*. The research log notes each rename. In a shared project the title is in your copy
  only. Changes no result.

### Fixed

- **Draft with AI in *Codebook from theory* could not be started.** The draft waited for Claude Code, but the dialog
  covered the sidebar, so its *Start* could not be pressed. The dialog now has its own *Start Claude Code* under the
  AI line while the draft waits, and it goes once the draft is back.

### Tests

- `tests/test_document_rename.py`: a title of one's own wins over the bibliography's and comes back off with *Use the
  title it had before*; the search index follows it; the research log says so; the API, the list's opened row and the
  page offer it; the theory dialog carries its own *Start Claude Code*.

### For developers

- `documents.own_title` (a new column; NULL: none) holds the person's title; `bibliography.set_title()` sets or
  clears it and `_sync_titles()` lets it win, keeping the replaced title in `file_title`. `PUT
  /api/projects/<p>/documents/<id>/title` `{"title"}`; the list and the document carry `named`.
