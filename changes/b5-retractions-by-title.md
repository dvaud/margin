### New

- **Retractions are found for works without a DOI too.** *Check for retractions* now looks a work of your bibliography
  up by its title, first author's family name and year when it has no DOI (a published kind of work with a title of
  three words or more). A match is accepted only when the title is (all but) the same, the year is within one, the
  first author is the same and no other work fits. Its notice shows with *Found by title*, the matched work and its DOI,
  and a quiet *Not this work* button (with Undo): a rejected match is hidden and not proposed again. The claim card says
  *found by title* beside such a notice. A lookup changes no result and no judgement.

### Privacy

- **What leaves the computer in a retraction lookup grows by one thing.** Besides DOIs, the title, the first author's
  family name and the year of each bibliography work without a DOI go to Crossref, one request per work, only when you
  press *Check for retractions* (or run `margin retractions --check`), and never under local-only. A work whose
  document is marked *No AI*, or is one of your own drafts (a *working* document), is left out, and so is every document
  that is not a work of the bibliography: its title may be a file name or a private draft. No name, email address or
  project name is sent.
