# Local model bench

Measures how well a local model reads evidence before Margin trusts it with a role (roadmap I6). Not part of the app:
it reads the green hydrogen pilot (`pilot/enlens.sqlite`, read-only) and writes everything under `data/` (not in git).

The results so far, and what they decided, are in `docs/ROADMAP.md`, item I6.

## What it measures

45 checks from the pilot: 30 real VCA claims and 15 planted controls (a paraphrase of the claim slipped into one
passage, a claim turned into its opposite, passages from another SDG goal). Each check is a claim against six
passages, asked with the app's own `verify_set` prompt. A local model answers every check 7 times: the app's settings
(temperature 0, seed 42), the same again, the passages reshuffled, and four samples at temperature 0.7.

Scores: right status, the grades it counts and how many are right against the confidence it states (overconfidence),
passages found, how often reruns agree, seconds per check, memory, heat.

**The reference is Fable's final review** of the 30 real claims (`data/review_fable*.jsonl`, three rounds). The
first gold (`data/gold.jsonl`, two blind Opus passes) is kept for the controls and for comparison.

## Benching another model

One model at a time on this computer, and never alongside a test run (see `CLAUDE.md`).

```bash
ollama pull <model>
python tools/localbench/localbench.py run --model <model>            # ~315 answers; resumes if stopped
python tools/localbench/localbench.py run --model <model> --think    # reasoning on: 2 runs per check, slow
python tools/localbench/monitor.py --tick 180                        # optional: heat, memory and progress every 20 s
python tools/localbench/localbench.py report                         # scores against the Opus gold
python tools/localbench/review.py score                              # scores against the Fable reference
python tools/localbench/viz.py                                       # data/bench-visualiser.html
```

`run` unloads other models before and after, refuses to load a model the computer clearly has no room for, and
writes `data/runs/<model>.jsonl` (every answer, with Ollama's timings) and `<model>.meta.json`.

A model earns more than *suggestions only* in Margin only by measurement here: its surest answers must be right far
more often than K2's (67% at 0.8 or more) and Qwen 3.5 4B's (73% at 0.9 or more).

## Hand-holding experiments

- `handhold.py`: one passage per call, numbered sentences, three short questions; the grade worked out by code.
- `handhold_lp.py`: yes/no questions, reading the model's own probability of "yes" (Ollama `logprobs`).

Both run 8 mixed claims in a minute or two. The opposites they need are written by hand in `handhold.py`; a
mechanical "It is not true that …" does not work.

## Adding a reviewer

A reviewer grades the claims from scratch. Never show it an AI judgement: a reviewer shown one tends to agree with it
(one agreed with 25 of 30, invented quotes included).

1. `python tools/localbench/review.py packet` writes `data/review_packet_free.txt`: the rules and 34 claims (the 30
   reviewed ones and 4 hidden controls), shuffled under ids `q01`…; the key stays in `data/review_free_key.json`.
2. Attach the packet to a fresh chat with the reviewer and send the prompt below.
3. Save its answer as `data/free/review_<name>.jsonl` and run `review.py score`. It counts only if it gets at least 3
   of the 4 controls right, at least 90% of its quotes are found in the passages, and it answers at least 25 claims.

The packet holds passages from the pilot's sources: attaching it sends them to that service.

````text
You are an independent expert reviewer. The attached file (review_packet_free.txt) contains grading rules and 34 claims. Each claim is about green hydrogen and an SDG target and comes with six source passages, P1–P6. Your job is to grade every passage yourself; nobody's answer is given to you.

For each claim, read all six passages in full and give each passage one grade under the rules in the file:
- supports: the passage states the claim's effect, in the same direction, for the same kind of outcome.
- partially_supports: the passage states a necessary part of the claim but not the whole, one inference away (for example the mechanism without its effect, the converse case, another value chain segment, or renewable energy in general rather than hydrogen).
- refutes: the passage states the opposite effect, or that there is no such effect.
- nothing: the passage does not bear on the claim. Being on the same topic is not enough.
Judge only from the passages, with no outside knowledge. Some claims are hard and some passages are long; read them anyway.

For every passage you grade supports, partially_supports or refutes, give the shortest quote that shows it: at least three whole words, copied character for character from that passage.

The status follows from your grades: any supports → "supported"; otherwise any partially_supports → "partially_supported"; otherwise any refutes → "contradicted"; otherwise "unsupported".

OUTPUT FORMAT (exactly this, nothing else):
One code block of JSON Lines. The first line names you; then one line per claim, in the order of the claims in the file:
{"reviewer": "<your model name and version>"}
{"claim": "q01", "grades": {"2": {"grade": "supports", "quote": "exact words from P2"}, "5": {"grade": "partially_supports", "quote": "exact words from P5"}}, "status": "supported", "note": "one or two sentences on your reasoning"}

Rules for the lines:
- "claim" is the id after "=== CLAIM" in the file, copied exactly.
- "grades" lists only the passages that bear on the claim, keyed by passage number as a string ("1" to "6"). Leave out passages that bear on nothing ({} if none do).
- Every one of the 34 claims must have exactly one line. Use valid JSON with double quotes, and escape any double quote inside a quote as \".
- If you cannot finish all 34 in one reply, stop after a complete line and write CONTINUE on its own line after the code block. I will reply "continue", and you go on from the next claim without repeating any.
````

## Files

| File | What it is |
| --- | --- |
| `localbench.py` | build the items, the Opus gold, the runs, the report |
| `review.py` | review cards, reviewers, the free packet, scores against a reviewer |
| `monitor.py` | the live sampler (thermal pressure, power, memory, progress) |
| `viz.py`, `page.py`, `review_view.html`, `review_template.html` | the visualiser, the results page, the review page |
| `handhold.py`, `handhold_lp.py` | the hand-holding experiments |
| `data/` | items, gold, runs, reviews (not in git) |
