[Manual](../MANUAL.md) › Which model does what

# Which model does what, and what is recorded

> **In short**
> - Each kind of AI task goes to the model that suits it: many quick labels on a small model, judging on a larger one.
> - On Claude Code, the recommended models follow your Claude plan; every other provider and agent has three tiers
>   from its own current line-up. A model you choose yourself always comes first.
> - Every answer records how it was made, and every Excel download ends with *How these results were made*.

## The model of each kind of task

| Task | Claude Code and the Claude API | Steps up to | A local model |
| --- | --- | --- | --- |
| Codebook labels, concept links | Haiku | Sonnet | the small model, if chosen |
| Search words, splitting a hypothesis, theme names, references | Sonnet | Opus | the main model |
| Judging excerpts, reading one again | Sonnet (high effort) | the auditor | the main model |
| Second opinion | the auditor (Opus, or Fable if switched on) | | the second model |

These are the models for a **Pro** plan on Claude Code; other plans follow the next table. A model chosen in
*Settings → Technical → AI model per task* comes first. A task **steps up** once: when its answer's certainty is
under 0.6, after two rejected answers, or when you press *Ask a stronger model*. Why these defaults, and how good they
are on the validation report's gold set: [MODEL_CHOICE.md](../MODEL_CHOICE.md).

### How much thought

*Energy efficient · Balanced · Intelligence*, beside every *Start Claude Code* and in *Settings → AI*, moves each
kind of task along Haiku, Sonnet and Opus (on Codex, Antigravity and another cloud provider, along the provider's three
tiers below). **Balanced** is the table above. **Energy efficient** starts each kind one
model lower (judging excerpts never below Sonnet) and asks the helpers for low effort: easiest on your plan's limits
and on energy. **Intelligence** starts each kind one model higher and asks for high effort: it uses your plan's limits
sooner. An unsure answer still steps up to a stronger model, where there is one. A model chosen per task comes first;
*Let the auditor use Fable* stays its own switch (Claude only); a local model keeps its own choice. Where the model takes
an effort (OpenAI's and Codex's reasoning effort, Antigravity's `--effort`), *Energy efficient* asks for low and
*Intelligence* for high. Can change results, as any
change of model can: each answer records its model.

### The recommended models of each provider

Beyond Claude, Margin uses three tiers: **small** (labels and links), **middle** (judging excerpts, search words and the
rest) and **strong** (second opinions and hard cases). Each provider and agent has its own line-up, best first. Margin
takes the first one your key or plan offers, so a new version brings newer models by itself. A model you choose per tier
comes first. Checked on the makers' pages on 18 November 2026.

| | Small | Middle | Strong |
| --- | --- | --- | --- |
| OpenAI (API key), Azure OpenAI (deploy these) | GPT-6 Luna | GPT-6.2 Sol (else GPT-6.1 Sol) | GPT-6.2 Astra (else GPT-6 Astra) |
| Google Gemini (API key) | Gemini 3.5 Flash-Lite | Gemini 4 Hydrogen (else Gemini 3.8 Flash) | Gemini 4 Carbon (else Argon, else Hydrogen) |
| Mistral (API key) | Mistral Small (else Ministral 8B) | Mistral Small | Mistral Large |
| OpenRouter | Gemini 3.5 Flash-Lite (else GPT-6 Luna) | GPT-6.2 Sol (else Gemini 4 Hydrogen) | GPT-6.2 Astra (else Gemini 4 Carbon) |
| **Codex** (ChatGPT plan) | GPT-6 Luna | GPT-6.2 Sol (else GPT-6.1 Sol) | GPT-6.2 Astra (else GPT-6 Astra) |
| **Antigravity** (Google account) | Gemini 3.8 Flash | Gemini 4 Hydrogen (else Gemini 3.8 Flash) | Gemini 4 Carbon (else Argon, Hydrogen, Gemini 3.8 Flash) |

- **Free Google account.** Antigravity then offers Gemini 3.8 Flash only, so every task uses it. Google AI Pro adds
  Gemini 4 Argon and Hydrogen, Ultra also Gemini 4 Carbon; Margin follows the models your plan lists.
- **Where tasks go.** The ladder of Claude (Haiku, Sonnet, Opus) maps to the three tiers: labels and links to small,
  most tasks and judging excerpts to middle, second opinions and the hard cases a task steps up to, to strong.
- **Azure** has no list of models: you type the name of each deployment, and the table says which models to deploy.
- **Not measured.** The defaults, the tiers and how they route were measured on Claude only; for the others, check the
  answers before you rely on them ([Codex and Antigravity](other-agents.md)).

### The mix of local and Claude

With Claude Code and a local model for restricted documents both set, *Settings → AI → The mix of
local and Claude* shares the work:

| Mix | The local model answers first | Claude answers |
| --- | --- | --- |
| Mostly local | every kind of task but second opinions | second opinions, and what the local model passes up |
| Balanced | labels, concept links, search words, splitting a hypothesis, theme names, references | judging excerpts, second opinions, the SDG pack, and what the local model passes up |
| Best quality (the default) | only the documents marked *Only a local AI*, as before | everything else |

The local model's answer goes up to Claude, who reads the task again, when the local model is unsure (certainty under
0.6), when its answers fail the quote check three times, or when it judges an excerpt as contradicting the hypothesis
(a contradiction decides an answer). Only tasks of documents Claude may read go up; the local answer counts
meanwhile, except a judgement of an excerpt: since I6 a local model's judgement of an excerpt is a suggestion only,
which counts for nothing, so under *Mostly local* every check of documents Claude may read also goes up to Claude,
whose reading counts ([A model on your own computer](local-models.md#suggestions-only)). Without a local model that answers, Claude answers as before. Claude Code's helpers leave the local
model's share alone; the queue lists it as *for your local model*, and *Answer here* lets the local model answer it
when no check is open. In work Claude also does, the local model's share waits for the local model's own *Start*
(0.19.13): it never starts by itself. Can change results.

### Agreement between routes

*Settings → AI → Agreement between routes* shows, on your own documents, whether your local model is good enough for a
kind of task. It appears when Claude (Claude Code or the Claude API) and a local model are both set, and a project is
open. Choose a kind of task and a sample size (10 to 100, 30 to start). Before anything starts, the box says how many
tasks are asked of your local model, how many of Claude (that uses your plan, or your API credit) and how many are left
out because Claude may not read their documents. An answer a task already has from a route is reused, so only what is
missing is asked. Then press *Compare the routes*.

Each route answers the same tasks and the two answers are compared decision by decision: the grade of each excerpt for
checks, second readings and readings again; whether each candidate code applies for labels; the relation of each pair
of terms for links. Themes, search words, hypothesis splits and term resolutions give no decision to compare, so they
are left out. The result is the share of identical decisions and Cohen's kappa, which discounts the agreement chance
alone would give: 1 is full agreement, 0 is chance. From 0.8 the local model is good enough for that kind, from 0.6 fair
(review what it answers), below that poor (let Claude read these).

It is a measurement: it is asked only when you press the button, it changes none of the project's results, and the
passages sent to Claude are noted in the list of what left your computer. Each comparison that runs to its end is kept,
with its date, in the project on this computer (not one you stop with Stop). Under the box, *Earlier comparisons* lists
them, newest first: the kind of task, how many were compared, kappa, the share that agree, the two models' names and
the Margin version. When a new comparison finishes, its result sets kappa beside the last one of the same kind (for
example "Kappa 0.62 on 3 Nov 2026 → 0.71 now"), so you can see whether a different model or a new version helped. The
list describes the local model on this computer, so it does not travel to colleagues with the project. Agreement is not
correctness: Claude is not always right either. Cannot change results.

### Models that suit your Claude plan

On Claude Code, Margin finds your plan by itself in the background (from `claude auth status`: when the app starts,
when it looks at the queue and before a run), and work that waits follows a new plan at once.

| Plan | Recommended models |
| --- | --- |
| Free | No Opus or Fable. Haiku for most tasks (search words, splitting a hypothesis, theme names, references, labels, links), stepping up to Sonnet when unsure; judging excerpts, second opinions and the SDG pack's reference claims on Sonnet. |
| Pro, or a plan not known yet | Sonnet for most tasks, Haiku for the many labels and links, Opus for second opinions and the hard cases (and the SDG pack's reference claims and checks). |
| Max, Team, Enterprise | Opus for most tasks, checks included. Haiku and Sonnet only where there are many tasks at a time and speed matters: labels and links (Haiku), references and the SDG pack's extraction (Sonnet, stepping up to Opus). A check on Opus has no stronger model unless *Let the auditor use Fable* is on, and the result page says so. |

Should Claude Code name the plan wrongly, or not at all (signed in with an API key), set it under *Settings →
Technical → AI model per task → The recommendations follow*. The Claude API and local models do not follow the plan.
Claude Code itself may need a paid plan.

**Fable.** The auditor (second opinions, and checks read again by a stronger model) runs on Opus (on a Free plan,
Sonnet). *Let the auditor use Fable* (*Settings → AI*) switches it to Fable. In Claude Code, Fable can be billed from
usage credits instead of your plan; its model picker then says *Requires usage credits*.

**Cost.** With the Claude API, one part of a hypothesis is two calls of a few thousand tokens. With Claude Code it
counts against your plan's limits; with a local model it costs only time.

## What every answer records

| Recorded | Notes |
| --- | --- |
| The model and its exact version (digest) | Claude Code gives no digest. |
| The prompt version | Changes when a prompt changes, so old and new answers stay apart. |
| The seed (42 by default) and temperature 0 | Only a local model takes them. Claude Code and the Claude API take no seed and are sent no temperature, so their answers are not repeatable the way a seeded local model's are. |
| The route (Claude Code, Codex, Antigravity, the Claude API, another cloud provider, a local server), the provider and the model's exact name, and the helper | With Claude Code, also the model set for that helper and when its batch was claimed and answered. |
| Whether the answer came from the stronger model | |
| The Margin version that made it | Every answer, codebook label and set of themes; each check records the version that started it. |
| The reader that read each document | See [How documents are read](how-documents-are-read.md). |

*How these results were made* (at the end of every Excel download, and in the app) lists them per kind of task. The
acceptance runs (`margin acceptance queue … --again`) measure how much two readings by Claude Code differ.

## Results across versions

Researchers compare results across versions, so Margin never redoes anything by itself:

- When a project holds results an earlier version made, the *Overview* says so in one line under its cards. Those
  results stay as they were made.
- A new reader reads only documents added after the update. The documents you have keep their text, and every quote
  and judgement in them stays where it is, until you move one to the new reader
  ([Read with the new reader](reading.md#read-with-the-new-reader)).
- A change that can give other answers for the same documents is listed in the changelog under *Changes that can
  alter your results*, and announced one minor release ahead.

---

Next: [Settings →](settings.md)
