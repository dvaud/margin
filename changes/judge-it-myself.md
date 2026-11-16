### New

- **Judge it myself, instead of starting the local model.** When excerpts of documents marked Only a local AI wait for
  your local model, the panel on the result now offers *Judge it myself* first, then *Start <model>*, in place of
  *Start it anyway* (two Starts side by side read oddly; *Start it anyway* is still offered if Start is refused for
  memory). The excerpts then wait for you under *Awaiting manual review*, each tagged so and saying you chose it; no
  model reads them. Every excerpt that waits for your judgement
  now carries the *Awaiting manual review* tag, with its reason. Can change results only through the judgements you
  give.

### Fixed

- **The local model's thinking line stays inside its card.** The latest words it streams wrap onto a second line at
  most, then end in an ellipsis; on one long line they pushed the box out past the card's edge.
- **No "more…" or "less" on an excerpt the card already shows whole.** It changed nothing but the links under it;
  such a card's ways into its document (open it at this place, the original file, a highlighted copy) are under
  *Details* now.

### For developers

- `POST /api/projects/<p>/hypotheses/<hyp_id>/judge-local` (`claimcheck.judge_local_yourself`): the local parts of a
  check go to the person, their rows marked `prompt_version = "by-choice"`; results carry `by_choice`.

### Tests

- `tests/test_judge_local_yourself.py`: the excerpts go to the person and stay out of every later local read, the
  judgement counts, excerpts no model may read are not `by_choice`, and the page's buttons, tag, "more…" rule and the
  two-line thinking line.

### Not yet done

- Once handed to you, the excerpts cannot be given back to the local model from the page.
