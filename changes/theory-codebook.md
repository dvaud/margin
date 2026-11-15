### Changes that can alter your results

- **A codebook from a theory document now finds the theory's concepts.** The first version offered every sentence
  that starts "X is a …" as a definition and ticked it, so a book gave "Takes" (from "All it takes is a click"),
  "Say", "Tree" and its printer's marks as concepts, and the AI draft read only twelve passages of it. Now, without
  AI, the entries of the document's own glossary come first, each with its definition (*Stock: an accumulation of
  material or information …*), then the terms its text defines, the terms its headings name ("Stocks, Flows, and
  Dynamic Equilibrium" gives three) and the phrases it uses far more than your evidence documents do. Running heads,
  printer's marks, tables of contents, equations and figure labels are left out, a definition is the sentence that
  best says what the term means and never a heading, and only the glossary's entries are ticked (the defined terms
  where there is no glossary, and nothing in a long text that defines fewer than three). *Draft with AI* reads **the whole document**, a part at a time, and puts the parts'
  drafts together: a concept found in several parts is offered once with its best definition, the most central first,
  and the AI is told to leave out the theory's own examples and cases. It can change results: the concepts offered
  for a theory document are different ones, so a codebook started from it again will differ. Codebooks you already
  made are not changed.

- **Terms in any alphabet are found whole.** The words of a theory document were read with Western European letters
  only, so a Hungarian term with "ő" or "ű" was cut at that letter and a Cyrillic or Greek one was not seen at all.
  Can change results, for the concepts offered from such a document.

### Under the hood

- Prompt `theory-codes-v2` (was `-v1`): one `theory_codes` task for each part of the document (`theorycodes._ai_parts`,
  at most 22,000 characters a part and 60 parts), so answers kept from `-v1` are not reused. A model on this computer
  with the automatic context length gets 16,384 tokens for the draft (the app sized it for a check's excerpts, 8,192,
  so the first version's draft failed on a long document with "This task needs about … tokens of context"); with a
  context length you set, the parts are made to fit it (`theorycodes._part_chars`). The job's result carries
  `parts`, `parts_read` and `task_ids`; `GET …/codebook-theory/<doc>/ai` says `parts`; a candidate says `ticked` and
  may be `"how": "glossary"`. With Claude Code as the AI every part waits in the queue at once.

### Not yet done

- The rules that find defined terms are English. A theory in another language still gives its glossary, headings and
  frequent phrases, and the AI draft reads any language.
- Tried on two books of one project (a primer with a glossary, and one chapter of a book that argues instead of
  defining). The AI draft of the second leaves out its case study; without AI a term of its case study is still
  offered, unticked.
