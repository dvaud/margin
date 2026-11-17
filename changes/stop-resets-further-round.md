### Fixed

- **Stop puts a further reading back as it was.** When you stopped *Read it* (documents added since a check), *Read
  these*, *Read more excerpts* or *Search with other words* while its local model still waited for its Start, the
  excerpts of documents marked Only a local AI kept waiting on the result, with the local model's Start and *Judge
  them myself*, and the button that asked for them did not come back. Switching such a document to *Claude may read
  it* then changed nothing: only the local model could read its excerpts. Stop now takes back whatever no model has
  read in that reading, and the search words it added: the result shows *Read it* (or the button you used) again, and
  the next click follows each document's setting at that moment. What Claude has already read stays, and so does a
  judgement of your own. The first reading of a check is unchanged: stopped, its local excerpts still wait under the
  local model's Start. Cannot change results.
