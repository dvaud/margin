### New

- **One panel for every place where AI runs: this computer on the left, Claude on the right.** A check, reading
  more, a second opinion, naming themes, judging pairs, labelling, following references, reading a theory, drafting a
  definition and the tests in Settings all show the same AI run panel, in full, in a card or as the sidebar's row.
  Each engine has its seat: the house on a solid tile at the left, the cloud on a hollow tile at the right, and one
  split bar along their top shows how far each has got. A seat whose engine has no work in this job stays empty and
  dashed, so you can see at a glance that nothing in it goes to Claude (or that no model on this computer reads it).
  Each side says its state once (*Waits for you*, *At work*, *Paused*, *Needs you*, *Done*), and the panel's head
  breathes slowly while it waits for you and flows once in 15 seconds while something works. Nothing of the Claude
  Code panel or the local-model panel is lost: Start Claude Code, Thought, the helpers, the command to type and See
  what is sent are in one fold that names your choices; the memory the model needs against what is free, Start it
  anyway and Judge it myself are where they were. The running model's figures are one quiet line with a small graph
  of its last 30 seconds.
- **Two parts, two starts.** When a job has work for both engines, both sides wait with their own Start: the model
  on this computer starts only when you press its Start (one press covers the job), and it has its own Stop beside
  the job's. The sidebar's row shows both engines; when both wait, it offers Open, which takes you to the panel.

### Changes

- **Every button that asks the AI for work follows one rule.** The play icon first, a verb and what it works on, and
  *Uses the AI* after it: *Check* (no more flask), *Name the themes*, *Judge the proposed pairs*, *Judge this pair*,
  *Propose other wordings*, *Label 33 passages*, *Read this again…*. Only a panel's own *Start Claude Code* or
  *Start qwen3.5:9b* names an engine. Labelling a code again, drafting a definition and answering the queue's share
  for your local model now show their progress and a Stop in the panel, where a toast or a button's spinner was.
- **Settings › Technical › Test a model** says in one sentence where the test tasks go (it said both that nothing is
  sent and that the Claude API is billed).

### For developers

- `aiRun()` (views/progress.js) with `aiSide()`, `aiSides()`, `aiSeat()`, `aiStart()`, `aiButton()` and `inStep()`
  (lib.js) draw the panel; `ProgressPanel`, `MiniJob`, `jobCard({ ai: true })`, `queueNotice()`, `localPanel()` and
  `memoryRefused()` keep their names on top of them. `startClaude()` is gone (Claude's live side replaces it). The
  classes `.queue-notice`, `.notice-local` (the notice kind `"local"`), `.lp-*`, `.mini-job`, `.model-line`,
  `.work-rail`, `.work-cloud`, `.start-claude`, `.sc-start`, `.sc-running` and `.sc-nudge` are retired (the nudge is
  `.ar-nudge`). The panel reads `job.local` (the local part's gate) when the server sends it, and works without it.
