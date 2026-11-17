### Fixed

- **A second opinion differs only from a first reading, and Show them finds it.** *Get a second opinion* also read
  excerpts no model had read yet (for instance those of a document still waiting for the local model, once it was
  switched to *Claude may read it*). With no first reading to compare with, each counted as a difference: the
  Hypotheses list said "second opinion differs on 7" and the result "judged 7 differently", yet no card on the page
  showed one, as such excerpts are not drawn as cards. A second opinion is now asked only of excerpts already read,
  and a second reading already made of an excerpt not read yet is no longer counted. Beside "judged N differently"
  under *Ask another AI model*, **Show them** now goes to each excerpt where the second opinion differs, one per click,
  including those you have already judged (which *Next to review* passes over). Cannot change results: a second
  opinion never changes an answer.
