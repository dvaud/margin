---
name: margin-run
description: Work through a Margin project's task queue (labels, concept links, theme names, references, search words, the claims of a draft, and checks) by handing each batch to a Margin helper agent on the model Margin names for it. Use when the user types /margin-run with a project name.
argument-hint: "<project> [kind] [--parallel N] [--helpers checker=2,labeller=1]"
arguments: project kind
disable-model-invocation: true
allowed-tools: {{TOOL_PREFIX}}queue_status Agent
effort: low
---

# Run a Margin project's queue

Margin (on this computer) has prepared tasks in a queue. Your only job is to start the Margin helper agents on them
and report progress. Margin keeps the documents, checks every quote and stores the answers; the researcher follows
the progress in the Margin app.

Arguments as typed: `$ARGUMENTS`

- **Project**: `$project` (the first argument; in quotes when it has spaces). If it is empty, call `queue_status`
  without a project to list the projects with work waiting, and ask which one.
- **Kind** (optional): `$kind`. When it is one of label, link, theme, expand, decompose, resolve, claims, check,
  reread or second, work only on that kind. When it starts with `--`, it is an option, not a kind.
- `--parallel N`: how many helpers work at the same time (1 to 8). Without it, Margin uses the speed chosen in the
  app (normally 2). More is faster but uses the plan's limit faster.
- `--helpers checker=2,labeller=1`: which helpers work in this run and how many of each at once. Helpers not named
  do nothing this run; their work keeps waiting.

## Steps

1. Call `queue_status` with the project, and with `kind`, `parallel` and `helpers` exactly as the arguments give
   them (leave out what they do not give). It lists `groups`, each with a `kind`, a `model`, a `helper`, how many
   tasks wait, and `start`: how many helpers to start for that group now.
   Follow `start`; do not work it out yourself. If it says the project is local only, tell the user and stop.
   If no group has a `start` of 1 or more, say nothing waits for this run and stop.
2. In **one message**, make one Agent call per helper to start: `start` calls for each group, in the order the
   groups are listed. Every call uses:
   - `subagent_type`: `margin-run:<helper>` (for example `margin-run:margin-labeller`);
   - `model`: the group's `model`, always;
   - `run_in_background`: `false`, so the calls run side by side and you get every report back before going on
     (a headless run would otherwise end before its helpers finish);
   - `description`: `<kind> tasks`;
   - `prompt`, filled in:

     > Project: <project>. Kind: <kind>. Model: <model>. Helper: <helper>. Take batches with
     > next_tasks(project="<project>", kind="<kind>", model="<model>", helper="<helper>",
     > taken_by="<helper> in Claude Code") and answer them as your instructions say, until next_tasks returns no
     > claim or you have finished 5 batches. Then report how many tasks you stored and how many still had problems.

   Several helpers can share a group; the queue never gives the same task to two of them.
3. Once every helper you started has reported back, call `queue_status` again (same `kind`, `parallel` and
   `helpers`) and start what `start` says. Repeat until no group has a `start` of 1 or more.
4. Finish with a short report: per kind, what was answered and what is left (with `--helpers`, also what waits for
   the helpers not named: `not_this_run`), and that the results are in the Margin app. Show no passages or
   answers.

## Rules

- Never read, summarise or answer tasks yourself, and never call `next_tasks` or `submit_answers`: the helpers do
  that, each on its own model.
- On a usage limit, or when the user stops you, just stop. A batch handed out and not answered returns to the queue
  after 30 minutes, and /margin-run later continues where this run stopped. Nothing is lost.
- Some answers come back for a second reading by a stronger model, as a new group with that model. Treat it like
  any other group.
