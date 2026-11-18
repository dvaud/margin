[Manual](../MANUAL.md) › A model on your own computer

# A model on your own computer

> **In short**
> - No Claude plan, or documents that must stay on your computer? A model served on your own computer keeps every
>   word on it.
> - Choose *A model on this computer*: Margin installs Ollama and then sets up the model chosen for your computer,
>   each with one button. You never pick a model.
> - A local model only **suggests**: every excerpt it reads waits for your own judgement, and only your judgements
>   decide an answer.

## Getting one

Choose *A model on this computer* on the first screen, or *Local model* in *Settings → AI*. Without a model server, the step
offers **Ollama**, a free program that runs AI models on your computer:

- *Install Ollama* first says how big the download is on your computer (in November 2026 about **1.7 GB on Windows**
  and **230 MB on a Mac**) and how much free disk space it needs (about four times that), before anything is
  downloaded. Then Margin downloads Ollama's own installer from ollama.com, checks that it is signed by Ollama, installs
  it (Windows: in your user folder, no administrator rights; Mac: in *Applications*) and starts it, with a progress
  bar and *Stop*. On Linux, Ollama's installer asks for your password, so Margin opens a terminal window running it.
- Ollama already on the computer but not running: press *Start Ollama*. Since 0.19.15 Margin starts nothing AI by
  itself, not when it opens and not when a page is drawn: the first Start of a local model (or search by meaning, when
  it needs it) starts Ollama, and right after an install Margin starts it when Ollama's installer did not.
- **Stop lets go of the model.** The job's *Stop*, or *Stop* on the local side, frees the local model's memory at once
  (after the item in hand), instead of Ollama keeping it for its next 15 minutes. A job that ends by itself keeps a
  model that runs on llama.cpp; a model on Ollama's MLX engine (a Mac) is let go of at once too, as it keeps growing.
- Rather do it yourself? *Download Ollama's installer* gets the file itself (ollama.com's own download page now leads
  with a line to type in a terminal).

Then Margin sets up the model chosen for this computer with one button, *Set up the local model* (roadmap I6). It reads
the computer's memory, graphics card and free disk space, and picks one of three tiers itself:

| Computer | What the local model does |
| --- | --- |
| Small (about 8 GB of memory, or no graphics card) | **Explorer**: points at the sentence of each excerpt that bears on your hypothesis and sorts the reading order. It judges nothing. |
| 16 GB | **Suggestions**: marks the sentences that bear on your hypothesis and suggests a judgement for each excerpt. |
| About 24 GB or more | **Suggestions**, from a larger model (not measured yet). |

Nothing is downloaded or started before you press the button. Margin also sets the model's context length, switches
its reasoning off for checks (on, one check took 114 seconds instead of 9) and sends a fixed seed. The models' names
show only under *Settings → Technical → The local model*, where you can choose another one. Set up a model before
Margin chose for you (qwen3:8b, say)? It keeps working; the same place offers the one chosen for your computer, which
is downloaded only if you press *Download*.

The memory Margin reckons for a model is what the bench of November 2026 measured: the file, the memory it needs
beyond it, its context, and on a Mac the memory Ollama's MLX engine adds over a long run (see below). A model is only
offered when that fits the memory and the disk with room to spare. For search by meaning,
*nomic-embed-text* (about 0.3 GB, English) or *bge-m3* (about 1.2 GB, many languages) ([First steps](first-steps.md#1-the-ai)). None of your documents are sent. **LM Studio**, **llama.cpp**, **Jan** and **vLLM** work too, as
OpenAI-compatible servers: in [LM Studio](https://lmstudio.ai), *Developer → Start server* with a model loaded.

In a terminal instead:

```bash
ollama pull qwen3.5:4b           # the local model Margin chooses for a 16 GB computer
ollama pull nomic-embed-text     # optional: search by meaning (English)
ollama pull bge-m3               # or this one for many languages: an English hypothesis also finds Dutch or French passages
```

Two other ways to use a local model:

- **Only for some documents**: mark them *Only a local AI*, and choose the model in *Settings → AI → Documents only
  a local AI may read* ([Privacy](privacy.md#who-may-read-each-document-with-ai)).
- **For everything, for good**: start Margin with `--local-only` ([Settings](settings.md#for-whoever-installs-margin)).

When no local model is chosen, or the chosen one is not installed, Margin uses one the model server already holds in
memory (so nothing extra is loaded), else the most recently downloaded one, and the test says which.

## Choosing and tuning

What Margin asks of a model is harder than chat: quotes copied word for word, fine judgement between "partly supports"
and "same topic", and answers in a fixed JSON format. Ollama and the OpenAI-compatible servers are given the answer's
JSON schema, so even small models give valid JSON; the rest depends on the model.

| Topic | What to know |
| --- | --- |
| **Size** | Margin chooses by memory (above). Larger models judge better and are slower; none of them decides anything: a local model only suggests. |
| **Context** | Margin sets the context length on every Ollama request (Ollama's own default is much smaller and cuts long prompts without warning). Automatic by default: the smallest of 8,192, 12,288, 16,384 and 32,768 tokens that holds the largest task your settings can produce (8 excerpts without reasoning: 8,192). It stays the same between requests, because Ollama reloads the model when it changes. The model's working memory grows with it (for qwen3:8b about 1.2 GB at 8,192 tokens, 2.4 GB at 16,384). *Settings → Technical* shows the length in use and takes a fixed number instead. With LM Studio or llama.cpp, set it when loading the model: 16,384 covers every task of the app. |
| **Memory** | Margin loads no model of its own and makes one model call at a time. On Ollama, a second opinion unloads the main model first and unloads itself when done, so two models are never in memory together. LM Studio and other OpenAI-compatible servers have no standard way to unload a model, so their own setting decides (LM Studio can keep only one model loaded). Restricted documents and memory: see [Privacy](#the-local-models-own-start-and-your-computers-memory). |
| **Reasoning** | For models that reason before answering (Qwen 3 and 3.5, for example), *Settings › Technical › The local model › Reasoning* (Ollama) has four choices: *Off* (the fastest), *Only when judging excerpts* (where reasoning can help; not for search words or splitting a hypothesis), *On for every step*, and *Model's default*. |
| **Reasoning budget** | Default 1,500 tokens. A model still reasoning at the budget is stopped and asked to answer at once from its notes. At 20 tokens a second that is at most about 75 seconds of reasoning per judgement; with *Only when judging excerpts*, a check takes a minute or two per part instead of half an hour. Reasoning text a server puts before the answer is ignored. |
| **Embeddings** | `nomic-embed-text` (fast, English), `mxbai-embed-large`, or `bge-m3` (many languages). Building the index embeds every passage once (minutes for ten thousand passages); after that a search costs one short call. With numpy installed the comparison is instant; without it, about half a second per search on ten thousand passages. Choose the model in *Settings → Documents*. |

> [!TIP]
> Whether reasoning judges better depends on the model. Compare with
> `margin --ws pilot benchmark --model … --think off` and `--think judging` before relying on it.

**Cost and time.** With a local model a check costs nothing but time: from seconds to several minutes per call,
depending on the model and the computer.

## Test a model before trusting it

*Settings → Technical → Test a model*, or:

```bash
margin --ws pilot benchmark --backend ollama --model qwen3:8b --sample 30
```

It runs the model on tasks the pilot already answered with Claude Opus 5.5 and reports, per kind of task: the share of
usable answers, the share with a quote not in the text, agreement with the reference (the same status, and Cohen's κ
beyond chance), and seconds per task. Nothing is stored.

| Verdict | Rule of thumb |
| --- | --- |
| Good enough to use, with review | at least 90% usable and κ 0.6 |
| Usable for a first pass | at least 75% usable and κ 0.4 |

Agreement with Opus is not correctness, but a model that often disagrees with it will also often disagree with your
reviewers.

**Certainties are the model's own estimates.** They mean little until you compare them with your own judgement:
*Settings → Checking* shows how often you agreed with the AI at each certainty, from the excerpts you judged, and after
20 judgements suggests the lowest strictness from which you agreed at least 80% of the time.

**Repeatable results.** Margin sends a seed (42 by default) and temperature 0 with every request, and records with each
answer the exact model build, the engine Ollama ran it on (MLX or llama.cpp), its quantisation and Ollama's version
(the *Engine* column of *How these results were made*). Even so, asking again can give a differently worded suggestion:
the program that runs the model does its sums in a slightly different order depending on what it read just before. In
the bench the same words came back about 6 times in 10 on a Mac's MLX engine (9 in 10 on llama.cpp), and the same
overall suggestion 19 times in 20. *Settings → Technical → Repeatable results* says "not guaranteed" for a model on
MLX without asking it (asking twice in a row would look repeatable when a long run is not); for others it asks the
same question twice (`margin backend-check --repeatable` on the command line). It does not matter for your answers: a
local model's suggestions decide nothing.

## Suggestions only

A local model **never sets a status** (roadmap I6). Every excerpt it reads goes to *Awaiting manual review* on the
result, filled in with what it found: the sentence it marked, highlighted, and (from the 16 GB tier up) the judgement
it suggests, as *The local model suggests: supports*. No certainty is shown. The suggestion shows before your own
judgement, so agreeing is one press (*Agree*); the small tier only points, so you choose the judgement yourself. The
answer of a check comes only from your judgements (and from Claude's, for documents Claude may read): until you judge
them, the check says *Waiting for your judgement*. The Excel rows, the checks list and the evidence map say the same.

A check made before this change, whose local model's judgements already counted, keeps its answer: nothing is changed
in silence. The result says how many of its judgements were made that way, and reviewing them (*Agree*, or judge
differently) makes them yours.

**The small tier's short answer.** The smallest model could not finish a check in the bench: it quoted whole passages
until its answer was cut off. It now answers in a short form: Margin numbers the sentences of each excerpt, the model
names the sentence that comes closest to the hypothesis (or its opposite) in each excerpt that bears on it, and Margin
cuts the quote itself, so it is always in the excerpt. A *possible lean* from that model is not shown yet: it is not
measured well enough.

## The local model's own Start, and your computer's memory

Your local model never starts by itself in work that Claude also does (0.19.13): starting Claude and starting the local
model are two separate clicks. While Claude reads its excerpts, the ones marked *Only a local AI* (and the AI mix's
share) wait beside them for the local model's own *Start*; one press covers the whole job, and the local model then
reads beside Claude: *Your local model (…) is reading 3 excerpts…*, with what it is doing and its own *Stop*, which
lets it finish the excerpt in hand and wait again. Work that only the local model does, started by its own button
(*Read them now on this computer*, say), needs no second click. Work that only the local model may do but that another
button asked for waits for its *Start* as well: *Name the themes*, when every theme comes from documents marked *Only a
local AI*, says so on the Themes page and loads nothing until you press the local model's *Start*.

A local model needs about as much memory as its size (a 9-billion-parameter model about 8 GB). On Ollama, Margin does
not start it when this computer clearly has too little free: starting it anyway pushes every other program into swap
and can all but freeze the computer. The progress then says why and the local part waits for *Start it anyway*; stop
the job instead, and those excerpts wait on the result (*Waiting for your local model*). Close programs you do not
need and press *Start* again (or *Read them now on this computer* on the result), or choose a smaller local model in
*Settings → AI*. If it still says too little is free, *Start it anyway* starts it regardless.

You need not start the model at all: *Judge it myself* (before *Start*) hands those excerpts to you. They wait under
*Awaiting manual review*, no model reads them, and your judgement counts like any other. Changed your mind? *Let the
local model read them*, above those excerpts, hands back the ones you have not judged yet and starts the model; what
you judged meanwhile stays and counts.

A model that takes more than a third of this computer's memory is let go as soon as it has read, instead of being
kept for 15 minutes. A local model you chose as the **main** AI is not checked this way: you start it yourself and see
it load.

**Long runs.** On a Mac, Ollama runs the Qwen 3.5 models on its MLX engine, which keeps what it read before (up to
8 GB) to answer the next request faster: over a long run the bench saw qwen3.5:4b grow from about 5 GB to 12.7 GB of
memory. Margin watches the model's memory before each request of work you started, and lets go of it when it has
grown by about 1.6 GB (or a tenth of the memory), or when less than a fifth of the memory is free; the next request
loads it again, which takes about 3 seconds. It never loads a model to do so, and never outside work you started.

---

Next: [Which model does what →](models.md)
