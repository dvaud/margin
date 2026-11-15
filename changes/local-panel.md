### Added

- **Your local model has its own panel, like Claude Code's.** Wherever work waits for the local model (passages of
  documents marked Only a local AI on the Codes page, excerpts on a hypothesis's result), a panel says so, built like
  the Claude Code panel so the two read as one family: what waits, the model, *Start*, and where the text goes. It is
  told apart by its white ground and *On this computer* with the house over it, and it shows what Claude Code's panel
  has no need of: how much memory the model needs against what this computer has free now. While the model reads, the
  panel says what it is doing, above Claude Code's panel when both work.

### Fixed

- **Labelling no longer stops when the local model cannot start.** On the Codes page with Claude as the AI, a project
  whose documents fell back to "Only a local AI" stopped the whole run with "qwen3.5:9b was not started: it needs
  about 8.1 GB of memory…" after a passage or two, although Claude could read every other passage; the page had said
  only that Claude reads them. Now the local model's passages are read first, and when it cannot start (too little
  memory free, or it does not answer) they wait while Claude labels the rest. The panel says why, with *Start it
  anyway*, and the page says beforehand how many passages the local model reads. Does not change results.
