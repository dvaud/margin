# Which model each task needs (G6)

This is the report the 0.8 roadmap asks for: for every kind of task, which model is good enough and how long it takes,
measured on the pilot, and the default that follows. **It is not filled in yet.** The runs need the sample sheets
filled in by a person once, pass marks the team sets before any run is scored, and real Claude Code sessions. Until
then the defaults below are the roadmap's starting points.

## How the runs are made

```bash
margin --ws pilot acceptance samples                      # once: acceptance/*.csv for a person to fill in
# the team writes acceptance/pass_marks.json, e.g. {"label": 0.6, "link": 0.8, "theme": 0.8, "resolve": 0.8, "check": 0.8}
margin --ws pilot acceptance queue --kind label --model haiku     # a copy of the pilot with label tasks for Haiku
/margin-run "pilot eval label haiku"                                # in Claude Code: answers them
margin --ws pilot acceptance queue --kind label --model local:qwen3:8b
margin --ws "<the copy's folder>" queue run --backend ollama        # the local model answers its copy
margin --ws pilot acceptance queue --kind label --model haiku --again   # the same tasks again: repeatability
margin --ws pilot acceptance score                                  # writes acceptance/MODEL_CHOICE.md
margin --ws pilot acceptance score --apply                          # the cheapest passing model becomes the default
```

Each run works on its own copy of the pilot, so the models' answers never mix with each other or with the pilot's.
Every run also records seconds per task, which the queue's estimates use.

| Task kind | Sample (filled once by a person) | Measure | Models compared |
| --- | --- | --- | --- |
| label | f2_labels.csv: 200 passages with their codes | kappa on "code present"; recall of the keyword pass | Haiku, Sonnet, Opus, the local model |
| link | f3_pairs.csv: 50 term pairs, same or not | share of pairs judged as the person did | Haiku, Sonnet |
| theme | g6_theme_names_<model>.csv, written after each run: fitting name or not | share of names fitting | Sonnet, Opus |
| resolve | f5_pronouns.csv: quotes opening with "it" or "they", the right referent | share where the chain names it | Sonnet, Opus |
| check | the pilot's checked VCA claims (reference answers); g6_checks.csv: a person's status | agreement with the reference status and per excerpt; with the person | Sonnet, Opus, the local model |
| all kinds | the same tasks answered twice (`--again`) | share of identical decisions | each model above |

A kind where no affordable model passes keeps a person in the loop: its answers stay marked provisional.

## Results

Not measured yet. `margin acceptance score` writes the tables here (one per kind: model, tasks answered, score,
repeatability, seconds per task, pass mark, passes) with the chosen default and why.

## Defaults until then

| Task kind | Claude default | Steps up to | Local default |
| --- | --- | --- | --- |
| label | Haiku | Sonnet | the small model |
| link | Haiku | Sonnet | the small model |
| expand, decompose | Sonnet | Opus | the main model |
| theme | Sonnet | Opus | the main model |
| resolve | Sonnet | Opus | the main model |
| check, reread | Sonnet (high effort) | the auditor (Opus, or Fable if switched on) | the main model |
| second | the auditor | none | the second model |

ENLENS also has defaults for its SDG pack (extract, split, verify, audits); Margin 0.8 does not offer the pack, so
they are left out here (see ENLENS's own `docs/MODEL_CHOICE.md`).
