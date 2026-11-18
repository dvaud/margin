### New

- **The local model is chosen for your computer.** Margin reads the computer's memory, graphics card and free disk
  space and picks one of three tiers: the small K2 Horizon model (about 8 GB, or no graphics card), Qwen 3.5 4B (16 GB)
  or Qwen 3.5 9B (about 24 GB or more). One button, *Set up the local model*, downloads it; nothing is downloaded or
  started before. Margin sets its context length, switches reasoning off for checks and sends a fixed seed. The names
  show only under *Settings → Technical → The local model*, which also offers the tier's model to whoever set up an
  older one (that one keeps working; nothing is downloaded unasked).
- **A short answer form for the small model.** The small model could not finish a check (its quotes ran past the
  length limit). It now names the sentence of each excerpt that bears on the hypothesis, and Margin cuts the quote
  itself, so it is always in the excerpt.

### Changes that can alter your results

- **A local model only suggests.** Every excerpt a model on this computer reads waits under *Awaiting manual review*,
  with the sentence it marked and the judgement it suggests (no certainty shown); only your judgements, and Claude's
  for documents Claude may read, set an answer. A check read only by a local model says *Waiting for your judgement*
  until you judge its excerpts; *Agree* takes a suggestion in one press. The checks list, the evidence map and the
  Excel rows agree. Checks made before keep their answers; the result says how many of the local model's judgements
  still count unreviewed. Under the AI mix *Mostly local*, Claude now reads every check of documents it may read after
  the local model, whose reading stays a suggestion. Can change results, for new checks with a local model.
- **Long local runs no longer fill the memory.** On a Mac, Ollama's MLX engine grew the 4B model from about 5 GB to
  12.7 GB over a long run. Margin now frees the model's memory when it has grown by about 1.6 GB, or when less than a
  fifth of the memory is free (it reloads in about 3 seconds), and lets go of an MLX model when the work ends.

### Fixed

- The search-word answer is bounded (at most 20 words of at most 60 characters), so a small model cannot write until
  its answer is cut off.
- The memory Margin reckons for a local model counts the memory it needs beyond its file and, on a Mac, what it grows
  by over a long run, so the advice no longer offers a model the computer cannot hold.

### For developers

- `pointing.py`, task kind `point` (prompt `point-v1`, local only: `tasks.answer_form` answers a check in it for the
  small tier); `schema.output_schema(kind, payload)`; `verifications.suggestion_json` (`verdicts.is_suggestion`,
  `tasks.mark_suggestions`); `OllamaBackend._guard`, `details`, `engine_version`, `p_yes`; `llm.let_go(runner=)`;
  provenance `runner`, `quantization`, `ollama`; `runs.engine_text`, the *Engine* column; `modeladvice.SMALL_MODEL`,
  `MEDIUM_MODEL`, `LARGE_MODEL`, `answer_form`, `older_model`.

### Tests

- `tests/test_local_tiers.py` (no model loaded): the pointer form, K2's real answers from the bench replayed
  (`tests/data/k2_pointer_replay.json`), suggestions only in the result, the list and Excel, old checks, the memory
  guard on made-up `/api/ps` readings, the engine in provenance, and the result card in Node.
  `tests/test_model_advice.py` covers the tiers on made-up computers.

### Not yet done

- A colleague on an older version of Margin counts the local model's readings in a shared project until they update
  (their copy does not know the mark that makes them suggestions).
- The lean the small model may suggest (from its probability of "yes") stays off until it is measured with opposites
  it writes itself; the GGUF builds of Qwen 3.5 are not benched yet; the AI run panel still names the local model.
