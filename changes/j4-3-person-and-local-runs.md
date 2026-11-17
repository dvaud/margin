### New

- **The validation report: right answers from a real project, labelled by a person.** `margin validate person
  --project <name>` takes what you decided in one of your projects as the right answers: each excerpt an AI judged
  that you then judged yourself, and each code an AI gave that you accepted, changed or rejected (with the codes you
  added where the AI had labelled). The AI's answers in that project are scored against them, by model, and `margin
  validate report` shows them beside the invented gold set, labelled as a person's judgements on a real project, with
  how many and the date. Only what you decided counts: an answer you left alone, or a comment without a judgement, is
  not a right answer. No AI is used, and the file holds no document text. Cannot change results.
- **A local model's run beside Claude's.** A validation run answered by a model on this computer is now named after
  that model (not "local model server"), and `margin validate report --latest` sets the newest run of each route side
  by side before giving each in full.
- **Two local models measured on the gold set (17 November 2026).** Each answered the same 30 hypotheses and 110
  passages twice, through the app's own queue, reasoning off. **Qwen 3.5 4B**: the right verdict for 47% of the
  hypotheses (26 of 30 finished; kappa 0.35), 93% of code decisions right (kappa 0.65), and the same verdict in both
  runs for 87%. **K2 Horizon 0.9B** finished none of its checks: on every passage it wrote a whole-sentence quote,
  so each answer ran past Margin's length limit and was refused; 89% of its code decisions were right (kappa 0.40).
  Claude Code's run of 13 November: 93% and 99%. So a small local model labels passages fairly well, but should not
  decide a check on its own (roadmap I6). The report is attached to the release.

### Fixed

- **The validation report no longer counts an unfinished check as finding nothing.** *Found evidence or not* is now
  over the finished checks only, and the routes side by side say how many were finished.

### For developers

- `validation.collect_person`, `write_person`, `latest_person`, `score_person`, `person_markdown`, `latest_runs` and
  `to_markdown_many`; run files carry `"local"`; person files live in `tools/validation/runs/person/`.
