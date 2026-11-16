### New

- **Highlight the words that matter on an excerpt you judge yourself.** On a card under *Awaiting manual review*,
  selecting words in the excerpt highlights them at once, as the AI's quote is highlighted: dashed until you choose a
  judgement, then saved with it and marked *Highlighted by you*; it goes into the exports and the highlighted copies
  as your quote. A selection that cuts a word keeps the whole word, and one that crosses a line end is found too.
  *Pick from a list* still offers the sentences for the keyboard; *Remove the highlight* takes it off. Before, the way
  was *Quote another sentence … Use it*, made for replacing the AI's quote. Changes no results.
- **Changed your mind: let the local model read them after all.** When you chose *Judge it myself* rather than start
  the local model, *Awaiting manual review* now offers *Let the local model read them*: the excerpts you have not judged
  wait for the local model again and it starts at once (with too little memory free, the usual *Start it anyway*
  question comes, and *Judge it myself* is offered again). What you judged meanwhile stays and still counts over the
  model's judgement. Excerpts no model may read are not offered. Can change results: the local model's judgements
  count for the excerpts you had not judged.

### Fixed

- **A card no AI read no longer says "You agreed with the AI".** Your judgement of an excerpt awaiting manual review is
  shown as *Your judgement*. Changes no results.
- An excerpt that waited for you and is then read by a model no longer shows a "read again" note with an empty earlier
  reading.

### For developers

- `POST /api/projects/<p>/hypotheses/<hyp_id>/local-again` (`claimcheck.local_again`): the parts handed to the person
  by *Judge it myself* (rows with `prompt_version = "by-choice"`) wait for the local model again; rows the person judged
  or commented on are kept. Refused (400) without a local model. `views/result.js` `selectionPlace(text, q)`: where a
  selection is in an excerpt, widened to whole words.

### Tests

- `tests/test_manual_highlight.py`: the way back and the model's reading after it (your judgement and quote kept, no
  "read again"), excerpts no model may read stay with you, a highlight that cuts a word, the page's wiring and
  `selectionPlace` in node.
