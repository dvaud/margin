"""I6: the short answer form of the small local model (`point`, prompt `point-v1`).

The small tier (K2 Horizon 0.9B) could not finish a check in the bench and the validation runs of November 2026: it
wrote whole passages as quotes (60% of its quoted words were not in the passage) until the answer's length limit cut
it off. In the `point` form Margin numbers the sentences of every excerpt and the model writes only numbers: for each
excerpt that bears on the claim, the excerpt (`p`) and its one sentence that comes closest (`s`). Margin cuts the quote
itself, so it is in the excerpt by construction, and no judgement is stored: the person judges every excerpt (I6,
"suggestions only"; the small tier is an explorer).

The grammar bounds the answer: at most one mark per excerpt, the excerpt numbers an enum, the sentence numbers at most
the longest excerpt's count; the token limit is `24 + 14 * K` (`cap`). Sentences are marked `<s1>`, `<s2>`… in the
prompt, never `[1]`, which scientific text uses for its citations.

The lean (`p_yes` of the claim against its opposite) is measured on 15 passages only and the opposites the app would
write are not measured at all, so it stays off (`LEAN`) until `tools/localbench/handhold_lp.py` has been run with
opposites written by the model (roadmap I6, "Left to try"). `lean()` is the rule it will follow.
"""
from __future__ import annotations

import re

from .textutil import split_sentences

PROMPT_VERSION = "point-v1"
LONG_SENTENCE = 300       # a "sentence" longer than this (a run-on PDF paragraph) is split at ; or : or a comma
MAX_PASSAGES = 20         # the schema without a payload (the registry's own view) allows this many
MAX_SENTENCES = 60
CAP_BASE, CAP_EACH = 24, 14
MAX_K = 60                # the most excerpts one task can hold (a press of Read these reads at most 40)
OUTPUT_CAP = 24 + 14 * MAX_K   # the registry's cap; a task's own is `cap(k)`, which follows its excerpts
# the lean, off until measured (see above); its threshold, from the bench's 48 rows (13 of 15 passages that matter)
LEAN = False
LEAN_MARGIN = 0.10
LEAN_PASSAGES = 4         # only the first marked excerpts get a lean


def _split_long(text: str, a: int, b: int) -> list[tuple[int, int]]:
    """A span longer than LONG_SENTENCE cut at `;` or `:` (else the comma nearest its middle), again until each fits."""
    if b - a <= LONG_SENTENCE:
        return [(a, b)]
    piece = text[a:b]
    cuts = [m.end() for m in re.finditer(r"[;:]\s", piece)]
    if not cuts:
        commas = [m.end() for m in re.finditer(r",\s", piece)]
        if not commas:
            return [(a, b)]
        mid = len(piece) // 2
        cuts = [min(commas, key=lambda c: abs(c - mid))]
    out, start = [], 0
    for c in cuts + [len(piece)]:
        seg = piece[start:c]
        if seg.strip():
            lead = len(seg) - len(seg.lstrip())
            s, e = a + start + lead, a + start + len(seg.rstrip())
            if e > s:
                out.append((s, e))
        start = c
    if len(out) <= 1:
        return [(a, b)]
    return [x for s, e in out for x in _split_long(text, s, e)]


def sentences(text: str) -> list[tuple[int, int]]:
    """The numbered sentences of an excerpt as (start, end) offsets in it: the app's sentence splitter
    (`textutil.split_sentences`, the one the card's highlights use), with run-on sentences cut (`_split_long`)."""
    out: list[tuple[int, int]] = []
    for a, b in split_sentences(text or ""):
        out += _split_long(text, a, b)
    return out


def cap(k: int) -> int:
    """The answer's token limit for `k` excerpts: about 12 tokens a mark, and a little for the brackets. It follows k:
    the schema allows a mark for every excerpt, so a lower ceiling would cut a full answer off."""
    return CAP_BASE + CAP_EACH * max(1, int(k))


def system_prompt() -> str:
    return ("You point at the passages that bear on a claim. Each passage's sentences are marked <s1>, <s2> and so on. "
            "For each passage that states the claim, part of it, or "
            "its opposite, give the passage number p and the number s of its one sentence that comes closest. List "
            "the passage that bears most on the claim first. Leave out passages that only share the topic. Write "
            'nothing else.\n\nAnswer in this format: {"marks": [{"p": 3, "s": 2}]}')


def user_prompt(payload: dict) -> str:
    parts = [f"CLAIM: {payload['claim']}"]
    for i, p in enumerate(payload["passages"], 1):
        text = p.get("text") or ""
        numbered = " ".join(f"<s{j}> {' '.join(text[a:b].split())}" for j, (a, b) in enumerate(sentences(text), 1))
        parts.append(f"P{i}\n{numbered}")
    return "\n\n".join(parts)


def schema(payload: dict | None = None) -> dict:
    """The answer's JSON schema, bounded by the task: at most K marks, `p` one of 1..K, `s` at most the longest
    excerpt's number of sentences. Without a payload, the loosest bounds (the registry's view)."""
    if payload and payload.get("passages"):
        k = len(payload["passages"])
        s_max = max(1, max(len(sentences(p.get("text") or "")) for p in payload["passages"]))
    else:
        k, s_max = MAX_PASSAGES, MAX_SENTENCES
    return {"type": "object", "required": ["marks"], "properties": {"marks": {
        "type": "array", "maxItems": k, "items": {
            "type": "object", "required": ["p", "s"], "properties": {
                "p": {"type": "integer", "enum": list(range(1, k + 1))},
                "s": {"type": "integer", "minimum": 1, "maximum": s_max}}}}}}


def marks(obj, payload: dict) -> list[dict]:
    """The usable marks of an answer, in the model's order: {"passage": index from 0, "sentence": index from 0,
    "start", "end", "quote", "rank": from 1}. A mark outside the excerpts or past its excerpt's sentences is dropped; so
    is a second mark of the same excerpt (the first stays)."""
    out: list[dict] = []
    seen: set[int] = set()
    passages = payload.get("passages") or []
    items = (obj or {}).get("marks") if isinstance(obj, dict) else None
    for m in items or []:
        if not isinstance(m, dict):
            continue
        try:
            p, s = int(m.get("p")), int(m.get("s"))
        except (TypeError, ValueError):
            continue
        if not 1 <= p <= len(passages) or p in seen:
            continue
        text = passages[p - 1].get("text") or ""
        spans = sentences(text)
        if not 1 <= s <= len(spans):
            continue
        a, b = spans[s - 1]
        seen.add(p)
        out.append({"passage": p - 1, "sentence": s - 1, "start": a, "end": b, "quote": text[a:b],
                    "rank": len(out) + 1})
    return out


def reading_order(n: int, got: list[dict]) -> list[int]:
    """The excerpts' reading order (indexes from 0): the marked ones as the model listed them, then the others in
    Margin's own search order."""
    first = [m["passage"] for m in got]
    return first + [i for i in range(n) if i not in first]


def lean(p_claim: float | None, p_opposite: float | None, margin: float = LEAN_MARGIN) -> str | None:
    """A possible lean from the model's probability of "yes" to *does the passage say the claim* and *… its
    opposite*: "may support" or "may contradict" past `margin`, else None. Shown without a number, and only once
    LEAN is on."""
    if p_claim is None or p_opposite is None:
        return None
    diff = p_claim - p_opposite
    if diff >= margin:
        return "may support"
    if diff <= -margin:
        return "may contradict"
    return None
