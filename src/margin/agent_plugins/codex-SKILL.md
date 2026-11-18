---
name: margin-run
description: Work through a Margin project's task queue (labels, concept links, theme names, codes, references, search words, checks) with the Margin helper subagents, each on the model Margin names for that kind of task. Use only when the user types $margin-run with a project name.
---

# Run a Margin project's queue

Margin (on this computer) has prepared tasks in a queue. Your job is only to hand them to the Margin helper subagents
and report progress. Margin keeps the documents, checks every quote and stores the answers; the researcher follows the
progress in the Margin app. The easiest way is the app's own *Start Codex* button, which does all of this by itself.

The user names the project (in quotes when it has spaces), and may add one kind of task (label, link, theme, check,
...) and `--parallel N` (helpers at the same time, 1 to 8).

## Steps

1. Call the Margin tool `queue_status` with the project (and `kind` and `parallel` when the user gave them). It lists
   `groups`: each has a `kind`, a `model`, a `helper`, how many tasks wait, and `start`: how many helpers to start for
   that group now. Follow `start`; do not work it out yourself. If the project is local only, or no group has a
   `start` of 1 or more, say so and stop.
2. For each group, start `start` subagents named after the group's `helper` (for example `margin-checker`, defined in
   `~/.codex/agents/margin-checker.toml`), each with this prompt, filled in:

   > Project: <project>. Kind: <kind>. Model: <model>. Helper: <helper>. Take batches with
   > next_tasks(project="<project>", kind="<kind>", model="<model>", helper="<helper>", taken_by="<helper> in Codex")
   > and answer them as your instructions say, until next_tasks returns no claim or you have finished 5 batches. Then
   > report how many tasks you stored and how many still had problems.

   If this Codex cannot start subagents, do not answer the tasks yourself: tell the user to press *Start Codex* in
   Margin instead, and stop.
3. When every subagent has reported back, call `queue_status` again and start what `start` says, until no group has
   a `start` of 1 or more.
4. Finish with a short report: per kind, what was answered and what is left, and that the results are in the Margin
   app. Do not show passages or answers.

## Rules

- Never read, summarise or answer the tasks yourself, and never call next_tasks or submit_answers yourself.
- Use only the Margin tools. Do not run commands, read files or search the web for this work.
- If you hit a usage limit, or the user stops you, just stop. A batch handed out and not answered returns to the queue
  after 30 minutes; nothing is lost.
