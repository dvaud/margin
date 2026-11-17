# Which model each task needs

How Margin chooses a model for each kind of AI task, and where the figures that test the choice are. The rule is the
roadmap's: the cheapest model likely to be good enough. A task steps up to a stronger model once: when its answer's
certainty is under 0.6, after two rejected answers, or when you press *Ask a stronger model*.

## How good the defaults are: the validation report

The defaults are measured by the AI half of the validation report (roadmap J4.3, `margin validate`, the gold set in
[`tools/validation/`](../tools/validation/README.md)): 30 hypotheses and 110 labelled passages on invented documents,
with right answers made by construction and checked by a second reader. Each release carries the report as
`validation-report-ai.md`. The first recorded run (Claude through Claude Code with these defaults, 13 November 2026)
gave 93% right verdicts and 99% right code decisions, and the same verdict on a second pass for 97% of hypotheses.

Not measured yet (both on the [roadmap](ROADMAP.md)): a run on a local model, and right answers from real documents
labelled by a person. Until then the figures are closer to an upper bound than to a forecast: real documents are
longer and less tidy than the gold set.

## The defaults

The recommendation for a **Pro** plan (and for a plan Claude Code does not name), from each kind's entry in
`taskkinds.py`:

| Task kind | Claude default | Steps up to | Local default |
| --- | --- | --- | --- |
| label | Haiku | Sonnet | the small model |
| link | Haiku | Sonnet | the small model |
| expand, decompose | Sonnet | Opus | the main model |
| theme | Sonnet | Opus | the main model |
| resolve | Sonnet | Opus | the main model |
| theory_codes, code_definition | Sonnet | Opus | the main model |
| group_name | Haiku | Sonnet | the main model |
| theory_frame | Opus | none | the main model |
| check, reread | Sonnet (high effort) | the auditor (Opus, or Fable if switched on) | the main model |
| second, audit | the auditor | none | the second model |
| SDG pack: extract | Sonnet | Opus | the main model |
| SDG pack: split, verify, verify_set | Opus | the auditor | the main model |

A model chosen in *Settings → Technical → AI model per task* comes first, on every plan and setting below. The
Claude API and local models do not follow the plan.

### What moves the defaults

- **The Claude plan** (0.13.10, `routing.tier_defaults`; Settings' `claude_plan`, found in the background as
  `claude_plan_detected`). **Free**: no Opus or Fable (the auditor is Sonnet); kinds that judge excerpts or set
  reference claims (check, reread, second, audit, split, verify, verify_set) run on Sonnet with nothing above, and
  every other kind starts on Haiku and steps up to Sonnet. **Max, Team, Enterprise**: kinds with many tasks at a time
  (label, link, resolve, extract) keep the Pro models, as speed matters there; every other kind starts on Opus,
  stepping up to the auditor only where it reads the hard cases, and only to a stronger model (Fable, when switched
  on).
- **How much thought** (0.18.1, roadmap N2; the choice beside *Start Claude Code*, Settings' `claude_thought`).
  *Balanced* is the table above. *Energy efficient* starts each kind one step lower (Opus → Sonnet → Haiku) and asks
  the helpers for low effort; *Intelligence* one step higher, with high effort. A kind that starts on the auditor
  keeps it.
- **The AI mix** (0.18.1, roadmap I1; Settings' `ai_mix`, when Claude Code and a local model are both set). *Best
  quality*: everything on Claude. *Balanced*: labels, links, search words, splitting a hypothesis, theme names and
  references on the local model. *Mostly local*: checks and the SDG pack's kinds as well. Documents marked *Only a
  local AI* go to the local model under every mix.

### Why these defaults for the SDG pack (0.8.1)

The SDG pack's tasks reach Claude Code only when they are prepared for the queue (`margin prepare split|extract|
verify-vca|verify-claims|audit-vca`). What the pilot used is the anchor (split on Fable, extract and the VCA checks on
Opus, audits on Fable):

- **extract: Sonnet, stepping up to Opus.** It is the bulk of the pack (319 tasks on the pilot with `--per-target 6`,
  thousands with every screened passage). Every claim has a confidence, so a claim Sonnet is unsure of sends the
  passage to Opus; claims under `accept_confidence` (0.8) wait for a person in any case, and every quote is checked.
  Haiku was not chosen: coding claims against 169 targets with directions and interactions is the hardest coding task
  Margin has.
- **split: Opus, stepping up to the auditor.** Few tasks (61 on the pilot), but its claims become the reference every
  VCA check is measured against, and the format has no confidence to step up on.
- **verify, verify_set: Opus, stepping up to the auditor.** They judge excerpts, as `check` does.
- **audits: the auditor, never stepping up.** An audit is a second model's reading; with *Let the auditor use Fable*
  off the auditor is Opus, the same model as the first reading, so give `--model fable` (or switch Fable on) for a
  real second model.

The validation report does not cover the SDG pack's kinds.

## Measuring on your own documents

The gold set is invented. To see how a model does on a corpus of your own:

- **Agreement between routes** (roadmap I5, *Settings → AI → Agreement between routes*): a sample of tasks answered
  by both the local model and Claude, with their kappa per kind, so you can see whether the local model is good
  enough for each kind of task.
- **The *Model test*** in Settings, or `margin benchmark` (local models, the Claude API): a model against a project's
  reference answers.
- **`margin acceptance`** (0.8): runs on copies of a project scored against samples a person fills in once, with pass
  marks the team sets before any run is scored. It writes its own `MODEL_CHOICE.md` and `model_choice.json` into the
  sample folder, and `--apply` makes the cheapest passing model the default.

```bash
margin --ws pilot acceptance samples                                 # once: acceptance/*.csv for a person to fill in
# the team writes acceptance/pass_marks.json, e.g. {"label": 0.6, "link": 0.8, "theme": 0.8, "resolve": 0.8, "check": 0.8}
margin --ws pilot acceptance queue --kind label --model haiku       # a copy of the project with label tasks for Haiku
/margin-run "pilot eval label haiku"                                  # in Claude Code: answers them
margin --ws pilot acceptance queue --kind label --model haiku --again   # the same tasks again: repeatability
margin --ws pilot acceptance score [--apply]                          # scores every run
```

Each run works on its own copy, so the models' answers never mix with each other or with the project's. A kind where
no affordable model passes keeps a person in the loop: its answers stay marked provisional.
