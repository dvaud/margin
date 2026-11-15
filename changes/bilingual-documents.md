### New

- **Keep one language of a document in two.** A journal that prints each article in two languages, column beside
  column, gave every finding twice: search by meaning found both, a check could quote the translation, codes and
  themes counted each point twice. When at least a fifth of a document is in a second language, its *Reading* panel
  now says *In two languages: English 52 %, Spanish 48 %* and offers **Keep only English** (or the other one): the
  other language's paragraphs stay in the text, folded and marked *left out: Spanish (you kept English)*, but
  searches, codes, themes and checks no longer read them. A paragraph in both languages (a title printed twice) and
  one whose language cannot be told still count; your own *Restore* or *Leave out* of a paragraph wins. The choice
  is kept with the document, holds when it is read again and travels to colleagues as *Leave out* does. Changes
  results only for the documents you choose it for.

### Changes that can alter your results

- **Reader 6 also keeps the two languages of a document apart.** Reader 5 sometimes put a paragraph of each
  language into one passage, where a column ended without a full stop and the next started in lower case. Reader 6
  never does, in a document in two languages of any kind (besides what it changes in PDFs). A document reader
  5 read is offered *Read with the new reader* only when reader 6 reads it otherwise: a PDF, or a document in two
  languages one of whose passages held both. New documents get reader 6. Can change results, for documents you move
  to it.

### Tests

- `tests/test_bilingual.py`: a two-page Spanish and English PDF made for the test; the two languages and each
  paragraph's; reader 5's passage in both languages and reader 6 without one; one-language documents read the same by
  both readers; *Keep only English*, a restored paragraph, *Count both again* and the research log through the API;
  the choice held through *Read with the new reader*; a one-language reader-5 document not offered the new reader;
  one language kept between copies, never two.

### Not yet done

- A colleague on a Margin older than 0.19 keeps the choice but does not apply it, so their copy still reads both
  languages until they update (as with marking a document as theory).
- A document in three languages: only its two main ones are told apart, so paragraphs of the third may still count.
