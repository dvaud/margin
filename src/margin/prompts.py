"""Prompt templates. Each task kind has a version; results record it so runs stay comparable."""
from __future__ import annotations

import json

from . import taskkinds
from .taxonomy import targets_reference_text

# 0.13.6: a view of the registry (taskkinds.py): check, reread and second share the check prompt (check-v5)
VERSIONS = taskkinds.Table("prompt_version")

_JSON_RULE = ("Answer with one JSON object and nothing else: no prose, no code fences. "
              "Copy every quote character for character from the text you were given, including odd spacing or "
              "typos from PDF extraction. Never shorten a quote with an ellipsis; quote a shorter contiguous span instead.")

DEFINITIONS = """Definitions used by every task
- Value chain segments: production (electrolysis, its electricity, water and land use, plant construction),
  transportation (storage, conversion to carriers such as ammonia, pipelines, shipping, ports),
  end_use (fuel cells, industry such as steel and fertiliser, power, mobility). Use whole_chain when the text
  is about green hydrogen in general, unclear when you cannot tell.
- direction: positive = helps progress on the SDG target; negative = hinders it; mixed = the text gives both;
  no_effect = the text says there is no effect.
- influence: direct = the activity itself changes the target's outcome (for example water withdrawal at the
  plant); indirect = through an intermediate mechanism (prices, policies, jobs elsewhere, supply chains).
- horizon: short_term = up to 2030, current or near-term; medium_long_term = after 2030 or "long term";
  not_stated = no time is given or implied by the text.
- side: where the effect lands: producer (producing or exporting country), importer, both, unspecified.
- Interaction scores (Nilsson et al. 2016): +3 indivisible, +2 reinforcing, +1 enabling, 0 consistent,
  -1 constraining, -2 counteracting, -3 cancelling."""


def _targets_block() -> str:
    return "SDG targets (use these codes exactly; lettered targets such as 7.b are valid):\n" + targets_reference_text()


def system_prompt(kind: str) -> str:
    k = taskkinds.get(kind)
    if k is not None and k.system is not None:  # 0.13.6: an add-on's kind builds its own
        return k.system()
    if kind == "point":  # I6: the small local model's short answer form (pointing.py)
        from .pointing import system_prompt as point_system

        return point_system()
    if kind == "extract":
        return f"""You extract evidence-backed impact claims from scientific and policy texts about the green hydrogen value chain,
for a Value Chain Assessment against the UN Sustainable Development Goals.

An impact claim says that an activity in the hydrogen value chain (or a hydrogen derivative such as ammonia or e-fuels)
affects one or more SDG targets. Extract only claims the PASSAGE itself states. Do not add general knowledge.
Background facts, definitions and methods are not claims. Return an empty list when there is no claim.

Rules
- One claim per distinct effect. If one effect touches several targets, list them all under targets.
- Choose the most specific target codes that fit; prefer one to three per claim.
- Every claim needs at least one evidence quote with field "claim". Add quotes for place, horizon, condition
  or policy_lever when the passage states them (field names: "place", "horizon", "condition", "policy_lever").
- Quotes must come from the PASSAGE, not from CONTEXT. CONTEXT is only there to resolve words like "it" or "this".
- condition: a circumstance under which the effect holds or disappears (for example "if desalinated water is used").
  policy_lever: an action that would change the effect (for example "local manufacturing of electrolysers").
- interactions: only when the passage states that progress on one SDG target affects another. Leave empty otherwise.
- confidence: your probability that all fields of the claim are correct.

{DEFINITIONS}

Output format
{{"claims": [{{"claim": "one-sentence paraphrase", "activity": "...", "segment": "production",
  "targets": [{{"target": "6.4", "direction": "negative", "influence": "direct"}}],
  "place": "arid regions" or null, "countries": ["Morocco"], "scale": "local|national|regional|global|unspecified",
  "side": "producer|importer|both|unspecified", "horizon": "short_term|medium_long_term|not_stated",
  "condition": null, "policy_lever": null, "confidence": 0.0-1.0,
  "evidence": [{{"field": "claim", "quote": "exact words from the passage"}}]}}],
 "interactions": [{{"from_target": "7.2", "to_target": "6.4", "score": -1, "quote": "exact words"}}],
 "note": null}}
{_JSON_RULE}

{_targets_block()}"""
    if kind == "split":
        return f"""You split an expert's justification from a Value Chain Assessment of green hydrogen into atomic claims.

Each atomic claim states one effect of the green hydrogen value chain on the given SDG target, with its direction,
and where stated the segment, place, time horizon and condition. Keep the expert's meaning; do not add facts.
Each claim needs a quote: the shortest contiguous span of the JUSTIFICATION that states it.
Direction, segment and horizon follow the JUSTIFICATION text. The VCA table cells and horizon are given as
context only: use the cells to choose a segment when the text does not name one, and never copy the table horizon
into a claim; use not_stated unless the text itself gives a time.

{DEFINITIONS}

Output format
{{"claims": [{{"text": "one-sentence claim", "quote": "exact span of the justification",
  "segment": "production|transportation|end_use|whole_chain|unclear", "direction": "positive|negative|mixed|no_effect",
  "place": null, "horizon": "short_term|medium_long_term|not_stated", "condition": null}}]}}
{_JSON_RULE}"""
    if kind == "verify":
        return f"""You check whether a source passage supports a claim about the effects of green hydrogen on an SDG target.

Verdicts
- supports: the passage states the same effect, in the same direction, for the same kind of outcome. It may be
  narrower (for example one country) as long as it is the same effect.
- refutes: the passage states the opposite effect, or that there is no such effect.
- not_enough_info: the passage is on the topic but does not state the effect, or is about something else.
Being on the same topic is not support. Do not use outside knowledge.
For supports and refutes give the shortest quote from the PASSAGE that shows it, at least three whole words;
for not_enough_info use null.
confidence: your probability that the verdict is right.

Output format
{{"verdict": "supports|refutes|not_enough_info", "confidence": 0.0-1.0, "quote": "exact words" or null,
  "rationale": "one short sentence"}}
{_JSON_RULE}"""
    if kind == "verify_set":
        return f"""You check whether source passages support a claim about the effects of green hydrogen on an SDG target.
The claim comes from an expert assessment; the passages come from the works the expert cited for that target.

Grade each passage that bears on the claim:
- supports: the passage states the claim's effect, in the same direction, for the same kind of outcome. It may be
  narrower or broader in place (one country rather than a region) as long as it is the same effect.
- partially_supports: the passage states a necessary part of the claim but not the whole, so a reader needs one
  further inference to reach the claim. Examples: the mechanism without its effect on the target's outcome; the
  converse case (local value chains raise local benefits, for a claim that import dependence limits them); the
  same effect for another value chain segment or for renewable energy in general rather than hydrogen.
- refutes: the passage states the opposite effect, or that there is no such effect.
Leave out passages that are only on the same topic. Do not use outside knowledge.
For every passage you list, give the shortest quote from THAT passage that shows it, at least three whole words
(never part of a word), and your probability that the grade is right. List no passage at all when none bears on
the claim.

Output format
{{"evidence": [{{"passage": 2, "verdict": "supports|partially_supports|refutes", "confidence": 0.0-1.0,
  "quote": "exact words from passage 2"}}],
  "rationale": "one or two short sentences on the overall picture"}}
{_JSON_RULE}"""
    if kind in ("check", "reread", "second"):
        return f"""You check whether passages from a set of documents support a claim or hypothesis.

Grade each passage that bears on the claim:
- supports: the passage states the claim's effect, finding or fact, in the same direction, for the same kind of
  outcome. It may be narrower or broader in place, time or population (one country rather than a region) as long
  as it is the same effect.
- partially_supports: the passage states a necessary part of the claim but not the whole, so a reader needs one
  further inference to reach the claim. Examples: the mechanism without its effect on the outcome; the converse
  case (a passage that local production raises local benefits, for a claim that dependence on imports limits them);
  the same effect for another group, place, period or a closely related subject; a weaker or conditional version.
- refutes: the passage states the opposite, that there is no such effect, or a finding that cannot hold if the
  claim is true.
Leave out passages that are only on the same topic, that merely mention the words of the claim, or that report
what others expect without evidence. Do not use outside knowledge.
For every passage you list, give the shortest quote from THAT passage that shows it, at least three whole words
(never part of a word), and your probability that the grade is right.
scope_note: when a passage is about another group, setting, place or period than the claim names (fully remote
workers for a claim about hybrid workers, all ages for a claim about young employees, another country or decade),
say so in a few words, for example "about fully remote workers, not hybrid". Such a passage is graded no higher
than partially_supports. Use null when the passage is about what the claim names.
refers_to: when your quote depends on a word such as "it", "this", "they" or "the plant" whose meaning comes from
earlier text, give the named form it refers to ("the planned electrolyser plant in Aqaba"), copied exactly from the
passage or from the text BEFORE it, which is shown above some passages for this purpose only. Use null when the quote
names what it is about. Never grade a passage on the text before it.
List no passage at all when none bears on the claim.

Output format
{{"evidence": [{{"passage": 2, "verdict": "supports|partially_supports|refutes", "confidence": 0.0-1.0,
  "quote": "exact words from passage 2", "scope_note": null, "refers_to": null}}],
  "rationale": "one or two short sentences on the overall picture"}}
{_JSON_RULE}"""
    if kind == "label":
        return f"""You label a passage from a report or paper with the codes of a codebook that it addresses.

You are given the passage, the text just before it (CONTEXT, to resolve words like "it"; never label or quote it),
and candidate codes found by a keyword and meaning search. The candidates are only suggestions: label a code only
when the PASSAGE itself addresses it. You may add another code of the same codebook if the passage clearly addresses
it better; write its code exactly as the codebook does.

When the whole codebook is given instead of candidates, consider every code; those marked "found by the search"
are only where the search looked first. A code may come with notes: "use when" and "not when" (which may name the
code to use instead) bound it; follow them.

For every code that applies:
- relevance: main = the passage is about this code's subject; mentioned = the passage touches it in passing. When
  the codebook says one main code per passage, mark at most one code as main.
- direction (only when the codebook says directions apply; otherwise not_stated): helps = the passage says
  something advances the aim; hinders = something works against it; mixed = both; not_stated = the passage does not
  say. A codebook may name the directions in its own words and say what they are relative to: then helps and
  hinders mean what those words say.
- confidence: your probability that the label is right.
- quote: the shortest span of the PASSAGE that shows why the code applies, copied exactly.
- reason: why the code applies, in at most 200 characters.
- practice and element: only when the codebook asks for them; otherwise null. practice = the activity the passage
  is about, element = the thing, skill or meaning the code is about, each copied exactly from the passage, a few
  words long; null when the passage does not name it.
Label nothing when no code applies; an empty list is a valid answer. Do not use outside knowledge.

Output format
{{"labels": [{{"code": "6.4", "relevance": "main|mentioned", "direction": "helps|hinders|mixed|not_stated",
  "confidence": 0.0-1.0, "quote": "exact words from the passage", "reason": "at most 200 characters",
  "practice": null, "element": null}}],
 "note": null}}
{_JSON_RULE}"""
    if kind == "link":
        return f"""You judge how terms used in a set of documents relate, from the way the documents use them.

Each term comes with short passages where it occurs. For each pair of terms, give the relation:
- same: the documents use both for the same thing (a synonym, an abbreviation, another spelling);
- broader: the first term (a) is a broader category that includes the second (b);
- narrower: the first term (a) is a kind or part of the second (b);
- needs: the first term (a) requires or depends on the second (b);
- shapes: the first term (a) influences or determines the second (b);
- clashes: the two are at odds or in conflict (the same from both ends);
- related: different things that are discussed together, when none of the above fits;
- different: unrelated, or different things that share words.
needs and shapes run from a to b: when the documents say it the other way round, give the pair turned round
(a: 2, b: 1). Use needs, shapes or clashes only when the passages say so; otherwise related.
When the request asks how the terms relate as elements of a practice, use these relations instead:
- requires: doing or using the first (a) needs the second (b), such as a skill that needs a device;
- shapes: a changes how b is done, what it takes or what it means;
- replaces: a takes the place of b in what people do;
- element_of: a is a thing, skill or meaning that the practice b is made of;
- clashes_with: a and b get in each other's way (rhythms, rules or meanings that do not fit);
- related: discussed together, but none of the above is shown; different: unrelated.
Judge from the passages, not from outside knowledge. For each side give one quote, copied exactly from a passage of
that term, that shows how the documents use it. confidence: your probability that the relation is right.

Output format
{{"relations": [{{"a": 1, "b": 2, "relation": "same|broader|narrower|needs|shapes|clashes|related|different",
  "confidence": 0.0-1.0,
  "quote_a": "exact words from a passage of term a", "quote_b": "exact words from a passage of term b"}}]}}
{_JSON_RULE}"""
    if kind == "theme":
        return f"""You name a theme: a group of passages from a set of documents that discuss the same subject.

You are given the passages that represent the theme best and the key terms that set it apart from the rest of the
documents. Give
- name: at most six words, the subject the passages share (not a sentence, no quotation marks);
- name_quote: one quote, copied exactly from one of the passages, that shows the passages are about that subject;
- description: one sentence on what the passages discuss, using only what they say;
- description_quote: one quote, copied exactly from one of the passages, that supports the description.
Do not use outside knowledge and do not summarise beyond the passages.

Output format
{{"name": "at most six words", "name_quote": {{"passage": 1, "quote": "exact words"}},
 "description": "one sentence", "description_quote": {{"passage": 2, "quote": "exact words"}}}}
{_JSON_RULE}"""
    if kind == "theory_codes":  # 0.18.4 (K2 part 2): drafts for the codebook editor, each definition quoted
        # theory-codes-v2: the whole document is read, a part at a time (v1 read twelve passages of it)
        return f"""You draft the concepts of a theory document: the ideas a researcher reads other documents through (for
example stock, flow and reinforcing loop in a book on systems thinking, or practice and routine in one on practice
theory). Each concept becomes a draft code a person checks and edits.

You are given the document's title, candidate concepts found without AI (hints only), and one part of the document as
numbered passages. A long document is read in several parts: each part is drafted by itself and the drafts are put
together afterwards, so give only what this part says. Give the theory's own concepts that this part defines or
explains, at most 12, the most central first:
- name: the concept's short name as the document writes it, in the singular, at most six words (no quotation marks);
- definition: one quote, copied exactly from one passage, at least three whole words, that says what the concept means
  in this theory, with that passage's number. Prefer the sentence that defines it ("a stock is ...", an entry of the
  document's glossary) over a sentence that only uses the word; one or two whole sentences, not a fragment;
- reason: one line on why it is a concept of this theory and not a passing word.
A concept is an idea of the theory that a researcher could look for in other material (interviews, reports,
observations). Leave out the document's own examples and cases (a bathtub, a fishery, the hospital the author
studied), people, places and organisations, the book's own parts and methods, and general words. A part with no
concept of the theory (a preface, a table of contents, thanks, a case description, references) gets an empty list:
that is a good answer. The candidates are hints: leave out those that are not concepts of the theory, and add a
concept they miss when a passage defines it. Use only what the passages say, no outside knowledge. Give no examples:
examples come from the researcher's own documents, never from the theory.

Output format
{{"concepts": [{{"name": "reinforcing loop", "definition": {{"passage": 2, "quote": "exact words"}},
  "reason": "one line"}}], "note": null}}
{_JSON_RULE}"""
    if kind == "theory_frame":  # K2, the framework draft (theoryframe.py): the drafts of several theories joined
        # theory-frame-v1, measured on five social-practice-theory texts (2026-11-15): 112 drafts gave 24 concepts in
        # five groups. `when_to_use` and `not_when` are printed after "Use it when:" by the labeller and under *When to
        # use it* in the editor, so both start with "When".
        return f"""You build a coding framework from the concepts of the theory a researcher reads their own documents through. A person
then decides which of your concepts become codes of their codebook, and edits them.

You are given the theory documents, what the researcher's own documents are (their titles, and what the researcher
wants to find out when they said so), and the concepts drafted from the theory, one document at a time. Each draft has
a number, its document, its name and the sentence quoted from that document that says what it means. Because each
document was read by itself, the same idea often comes several times (from two authors, in the singular and the
plural, under a longer and a shorter name), and some drafts are no use as a code: the author's own case or method, a
school of thought, a general word.

Give the framework the theory amounts to, for this researcher. The documents may come from several authors: build one
framework from all of them, and join what two authors both mean.
- groups: 2 to 6, the way the theory itself is built (for example the parts a practice is made of, how practices
  change, how practices connect). Each has a name of at most five words and one line on what its concepts share.
- concepts: at most 24 in all, each in one group. A concept is an idea of the theory that a passage of the
  researcher's documents can show. Join the drafts that are the same idea into one concept and give every draft you
  joined in `from` (their numbers); a draft belongs to at most one concept. A finer kind of an idea (two kinds of
  resources) is joined into the idea itself, unless the theory's argument rests on telling the kinds apart. Leave a
  draft out by naming it in no concept.
  Each concept has:
  - name: as the theory names it, at most five words; one thing in the singular ("stock", not "stocks"), a phrase
    as the theory writes it ("making and breaking links");
  - from: the numbers of the drafts it is made of, at least one;
  - meaning: one or two plain sentences on what the concept means in this theory, saying only what its drafts' quotes
    say, in words a newcomer to the theory understands (no "refers to the notion of");
  - when_to_use: one or two sentences that start with "When a passage" and say what an instance looks like in the
    researcher's kind of documents: who does or says what. Use their subject (from the titles and the focus), not the
    theory's own examples;
  - not_when: one sentence that starts with "When" and says when a neighbouring concept of the framework fits instead,
    naming it; null when no concept is close;
  - words: 5 to 10 words or short phrases that the researcher's documents would use where they show this concept.
    Not the theory's terms: a report on a repair event writes "learned how to", "skills", "know-how", never
    "competence". Each is looked for exactly as you write it, so give words of one to three words that belong to
    this concept, and none that nearly every page of their documents holds (in a study of repair events: "repair",
    "volunteers") or that any text holds ("because", "always");
  - core: true for the concepts the framework cannot do without (the ones a first codebook should start from, 6 to
    12 of them), false for the rest.
- note: one line on which drafts you left out and why, or null.
Order the groups and the concepts within a group from the most central to the least. Say nothing the quotes do not
say about the theory; you know nothing of the researcher's documents but their titles and focus, so `when_to_use` and
`words` are your best guess at how the concept shows there, and the person corrects them.

Output format
{{"groups": [{{"name": "Elements of a practice", "about": "one line", "concepts": [{{"name": "competence",
  "from": [3, 17], "meaning": "one or two sentences", "when_to_use": "When a passage ...",
  "not_when": "When ..., use meaning instead.", "words": ["five", "to", "ten", "words", "or phrases"],
  "core": true}}]}}], "note": null}}
{_JSON_RULE}"""
    if kind == "code_definition":  # K1 (the optional AI part): a draft to rewrite, from the code's examples only
        return f"""You draft the definition of one code of a qualitative codebook from its example passages. A person
chose these examples as instances of the code; your draft is offered to them to rewrite, and the definition is what an
AI labeller later reads to decide which passages the code fits.

You are given the code's name (and its group, when it has one) and the passages that hold its examples, each example
marked. Write, from these passages only:
- definition: one or two plain sentences on what the code is about, general enough to fit every example and no
  broader than they show (not a summary of one passage, and not a repeat of the name);
- definition_quote: one quote, copied exactly from one passage, at least three whole words, that shows the definition
  best, with that passage's number;
- when_to_use: one sentence on the signs in a passage that the code applies;
- when_to_use_quote: one quote, as above, that shows those signs;
- when_not_to_use: one sentence on what the examples are not, which a labeller could confuse with the code (a nearby
  topic the passages mention but the examples do not stand for); an empty string when the passages give no ground.
Use no outside knowledge and no knowledge of the field: only what the passages show. Say in note, in one line, when
the examples seem to stand for more than one code.

Output format
{{"definition": "one or two sentences", "definition_quote": {{"passage": 1, "quote": "exact words"}},
 "when_to_use": "one sentence", "when_to_use_quote": {{"passage": 2, "quote": "exact words"}},
 "when_not_to_use": "one sentence or empty", "note": null}}
{_JSON_RULE}"""
    if kind == "group_name":  # D1 rest (the optional AI part): a short name for a group of the concept map
        return f"""You name one group of concepts that a concept map of a researcher's documents found: concepts the
documents mention together more often than by chance.

You are given the group's concepts, the most mentioned first, and a few passages where several of them are mentioned
together. Write, from these passages only:
- name: a short name for what the group is about in these documents, two to six words, in the documents' own terms and
  in the language of the passages, in sentence case (a capital first letter, the rest as the documents write it), with
  no quotation marks; not a list of its concepts joined by "and" unless nothing more telling fits; not a judgement;
- name_quote: one quote, copied exactly from one passage, at least three whole words, that shows the name best, with
  that passage's number;
- note: one line when the concepts seem to form more than one group, else null.
Use no outside knowledge and no knowledge of the field: only what the passages show.

Output format
{{"name": "Remote work and commuting", "name_quote": {{"passage": 1, "quote": "exact words"}}, "note": null}}
{_JSON_RULE}"""
    if kind == "resolve":
        return f"""You find chains of references in consecutive passages of one document: the places that refer to the same
thing (a plant, a policy, a country, a group of people, a technology).

A chain has a name (the clearest named form of the thing in the passages) and its mentions: named forms
("the Aqaba electrolyser plant"), short names ("the plant"), and pronouns ("it", "its", "they", "this project").
Give only chains with at least two mentions, and only things the passages name at least once. Leave out generic
words that do not point back to something ("it is important that").
For every mention give
- passage: the number of the passage it is in;
- span: three to twelve words copied exactly from that passage, containing the mention, so its place is clear;
- mention: the exact words of the mention, as they stand inside the span;
- named: true for a named form, false for a pronoun or a short description.

Output format
{{"chains": [{{"name": "the Aqaba electrolyser plant",
  "mentions": [{{"passage": 1, "span": "the Aqaba electrolyser plant will start", "mention": "the Aqaba electrolyser plant", "named": true}},
               {{"passage": 2, "span": "It requires 1.5 million cubic metres", "mention": "It", "named": false}}]}}]}}
{_JSON_RULE}"""
    if kind == "expand":
        return """You prepare a search of reports and scientific papers for passages that bear on a claim.

Give search terms: the claim's key words, synonyms and related technical terms, the outcome it is about, the
measures a study would report, and the words a source would use to state the opposite. Single words or short
phrases, at most 20 terms, in the language of the claim; if the claim is not in English, add the main terms in
English too. Do not judge the claim.

Output format
{"terms": ["...", "..."]}
Answer with one JSON object and nothing else: no prose, no code fences."""
    if kind == "decompose":
        return """You split a hypothesis into the claims that must all hold for it to be true, so each can be checked
against documents on its own.

Rules
- Each part is one plain, self-contained sentence that a source could state or contradict. Repeat the subject
  instead of writing "it" or "this".
- Together the parts say what the hypothesis says: keep its meaning, direction, place, time and conditions; do not
  add facts, causes or qualifications of your own, and do not judge whether they are true.
- Give 2 to 5 parts. If the hypothesis is already one simple claim, return it unchanged as the only part.
- role: condition (a circumstance it assumes), mechanism (how the effect comes about), outcome (the effect itself),
  comparison (more or less than something else), scope (where, when or for whom), component (anything else).

Output format
{"parts": [{"text": "one checkable sentence", "role": "mechanism"}], "note": null}
Answer with one JSON object and nothing else: no prose, no code fences."""
    raise ValueError(f"unknown task kind {kind!r}")


def _code_entry(c: dict, found: bool = True) -> str:
    """A code as a label prompt gives it: its description, and (Margin) its own "use when", "not when" and source
    on lines of their own, only when it has them. `found`: marks a code the search found (with the whole codebook)."""
    line = f"{c['code']}: {c['description']}"
    if found and c.get("found"):
        line += " [found by the search]"
    for k, word in (("include", "Use when"), ("exclude", "Not when"), ("source", "Source")):
        if c.get(k):
            line += f"\n    {word}: {c[k]}"
    return line


SHARED_CODEBOOK_MAX = 40  # 0.18.1 (H4): a batch whose label tasks name at most this many codes gets them once


def shared_codebook(kind: str, payloads: list[dict]) -> dict | None:
    """0.18.1 (H4): for a batch of label tasks of one codebook naming few codes in all, the codes' descriptions once
    ("CODEBOOK OF THIS BATCH", added to the batch's instruction) and each task's prompt naming only its candidates'
    codes. None when it does not apply (another kind, several codebooks, many codes, a single task)."""
    if kind != "label" or len(payloads) < 2 or len({p.get("framework") for p in payloads}) != 1:
        return None
    codes: dict[str, dict] = {}
    for p in payloads:
        for c in p.get("candidates") or []:
            codes.setdefault(c["code"], c)
    if not codes or len(codes) > SHARED_CODEBOOK_MAX:
        return None
    lines = ["CODEBOOK OF THIS BATCH (the candidate codes of its passages; each passage names its own):"]
    lines += [_code_entry(c, found=False) for c in codes.values()]
    return {"codebook": "\n".join(lines), "prompts": [user_prompt(kind, p, codes_once=True) for p in payloads]}


def user_prompt(kind: str, payload: dict, codes_once: bool = False) -> str:
    k = taskkinds.get(kind)
    if k is not None and k.user is not None:  # 0.13.6: an add-on's kind builds its own
        return k.user(payload)
    if kind == "point":  # I6
        from .pointing import user_prompt as point_user

        return point_user(payload)
    if kind == "extract":
        parts = [f"DOCUMENT: {payload.get('title') or 'untitled'}"]
        if payload.get("doi"):
            parts.append(f"DOI: {payload['doi']}")
        if payload.get("page"):
            parts.append(f"PAGE: {payload['page']}")
        if payload.get("context"):
            parts.append(f"CONTEXT (not quotable):\n{payload['context']}")
        parts.append(f"PASSAGE:\n{payload['text']}")
        return "\n\n".join(parts)
    if kind == "split":
        return (f"TARGET {payload['target']}: {payload['description']}\n\n"
                f"VCA cells for this target (segment: influence): {json.dumps(payload.get('cells', {}))}\n"
                f"VCA time horizon: {payload.get('horizon') or 'not given'}\n\n"
                f"JUSTIFICATION:\n{payload['justification']}")
    if kind == "verify":
        return (f"CLAIM (about SDG target {payload['target']}: {payload['target_description']}):\n{payload['claim']}\n\n"
                f"SOURCE: {payload.get('title') or 'untitled'}" + (f", page {payload['page']}" if payload.get("page") else "") + "\n\n"
                f"PASSAGE:\n{payload['text']}")
    if kind == "expand":
        out = f"CLAIM:\n{payload['claim']}"
        if payload.get("context"):
            out += f"\n\nIt is part of this hypothesis:\n{payload['context']}"
        return out
    if kind == "decompose":
        return f"HYPOTHESIS:\n{payload['hypothesis']}"
    if kind in ("check", "reread", "second"):
        head = "CLAIM"
        if payload.get("target"):
            label = payload.get("framework_label") or "SDG target"
            head += f" (about {label} {payload['target']}: {payload.get('target_description', '')})"
        parts = [f"{head}:\n{payload['claim']}"]
        if payload.get("claim_context"):  # 0.13.7: a claim from a citation, in its own sentences (data, as a reader's note)
            cited = f" ({payload['cited']})" if payload.get("cited") else ""
            parts.append(f"THE CLAIM IN ITS TEXT: a text cites the source{cited} that the passages below come from, "
                         "for this claim. Read it only to understand what the claim says; it is not evidence: never "
                         f"grade or quote it.\n…{payload['claim_context']}")
        for i, p in enumerate(payload["passages"], 1):
            src = (p.get("title") or "untitled") + (f", page {p['page']}" if p.get("page") else "")
            if p.get("context"):  # check-v4: the text just before, for refers_to only
                parts.append(f"BEFORE P{i} (for refers_to only; not to be graded or quoted as evidence):\n…{p['context']}")
            parts.append(f"P{i} | {src}\n{p['text']}")
        if payload.get("read_elsewhere"):  # 0.11: the round's other excerpts come from documents kept from this model
            parts.append(_read_elsewhere(payload["read_elsewhere"]))
        if payload.get("reader_note"):  # a person's comment when they ask for one excerpt to be read again
            parts.append(f"A reader noted (a hint to check against the passage, not evidence): {payload['reader_note']}")
        if kind == "reread":
            parts.append("This passage is read again on request. In \"rationale\", say in one or two sentences why you "
                         "grade it as you do" + (", and whether the reader's note changed your judgement and why."
                                                 if payload.get("reader_note") else "."))
        return "\n\n".join(parts)
    if kind == "label":
        parts = [f"CODEBOOK: {payload.get('framework_title') or payload['framework']} (a code is called a "
                 f"{payload.get('code_label') or 'code'}). Directions apply: "
                 f"{'yes' if payload.get('directional') else 'no (use not_stated)'}."]
        dw = payload.get("direction_words") if payload.get("directional") else None
        if dw:  # 0.9: the codebook's own words for the directions
            parts[0] += (f" In this codebook, helps = {dw.get('helps')}, hinders = {dw.get('hinders')}, "
                         f"mixed = {dw.get('mixed')}; answer with helps, hinders, mixed or not_stated.")
        if payload.get("directional") and payload.get("direction_note"):
            parts[0] += f" The direction is judged {payload['direction_note'][0].lower()}{payload['direction_note'][1:]}"
        if payload.get("one_main"):
            parts[0] += " One main code per passage: mark at most one code as main."
        if payload.get("stance"):
            parts.append(f"HOW THE CODEBOOK IS MEANT: {payload['stance']}")
        if payload.get("practice_and_element"):
            parts.append("This codebook asks for practice and element: for each label, give the practice the passage "
                         "is about and the element the code is about, each copied exactly from the passage (null "
                         "when it does not name one).")
        cands = payload.get("candidates") or []
        head = "THE WHOLE CODEBOOK" if payload.get("whole_codebook") else "CANDIDATE CODES"
        if codes_once and cands:  # 0.18.1 (H4): their descriptions are in the batch's codebook
            parts.append(f"{head} (described in the batch's codebook): " + ", ".join(
                c["code"] + (" [found by the search]" if c.get("found") else "") for c in cands))
        else:
            parts.append(f"{head}:\n" + ("\n".join(_code_entry(c) for c in cands)
                                          if cands else "(none found by the search: name codes only if the passage "
                                                        "clearly addresses them)"))
        parts.append(f"DOCUMENT: {payload.get('title') or 'untitled'}" + (f", page {payload['page']}" if payload.get("page") else ""))
        if payload.get("context"):
            parts.append(f"CONTEXT (not to be labelled or quoted):\n…{payload['context']}")
        parts.append(f"PASSAGE:\n{payload['text']}")
        return "\n\n".join(parts)
    if kind == "link":
        parts = []
        for t in payload["terms"]:
            lines = [f"TERM {t['n']}: {t['label']}"]
            for j, sn in enumerate(t["snippets"], 1):
                lines.append(f"  passage {t['n']}.{j} ({sn.get('title') or 'untitled'}): {sn['text']}")
            parts.append("\n".join(lines))
        n = len(payload["terms"])
        pairs = ", ".join(f"({a}, {b})" for a in range(1, n + 1) for b in range(a + 1, n + 1))
        if payload.get("relations") == "elements":  # Margin 0.9
            parts.append("Judge how the terms relate as elements of a practice: requires, shapes, replaces, "
                         "element_of, clashes_with, related or different.")
            parts.append(f"Give the relation for each pair: {pairs}.")
        else:
            parts.append(f"Give the relation for each pair: {pairs} (needs and shapes: turned round when the documents "
                         "say it the other way).")
        return "\n\n".join(parts)
    if kind == "theme":
        parts = [f"KEY TERMS: {', '.join(payload.get('terms') or [])}"]
        for p in payload["passages"]:
            src = (p.get("title") or "untitled") + (f", page {p['page']}" if p.get("page") else "")
            parts.append(f"P{p['n']} | {src}\n{p['text']}")
        return "\n\n".join(parts)
    if kind == "theory_codes":
        of = f" (part {payload['part']} of {payload['parts']})" if (payload.get("parts") or 1) > 1 else ""
        parts = [f"THEORY DOCUMENT: {payload.get('title') or 'untitled'}{of}",
                 "CANDIDATE CONCEPTS (found without AI): " + (", ".join(payload.get("candidates") or []) or "none")]
        for p in payload["passages"]:
            parts.append(f"P{p['n']}" + (f" (page {p['page']})" if p.get("page") else "") + f"\n{p['text']}")
        return "\n\n".join(parts)
    if kind == "theory_frame":
        parts = ["THEORY DOCUMENTS:\n" + "\n".join(f"- {d.get('title') or 'untitled'}" for d in payload["documents"]),
                 "THE RESEARCHER'S OWN DOCUMENTS (titles):\n" + ("\n".join(f"- {t}" for t in payload.get(
                     "evidence_titles") or []) or "- none named"),
                 "WHAT THE RESEARCHER WANTS TO FIND OUT: " + (payload.get("focus") or "not said"),
                 "DRAFTED CONCEPTS:\n" + "\n".join(f"{d['n']}. {d['name']} | {(d.get('title') or 'untitled')[:50]} | "
                                                    f"\u201c{d['quote']}\u201d" for d in payload["drafts"])]
        return "\n\n".join(parts)
    if kind == "code_definition":
        parts = [f"CODE: {payload.get('code') or 'unnamed'}" + (f" (group: {payload['group']})" if payload.get("group") else "")]
        for p in payload["passages"]:
            ex = "\n".join(f"EXAMPLE: \u201c{e}\u201d" for e in p.get("examples") or [])
            parts.append(f"P{p['n']}" + (f" (page {p['page']})" if p.get("page") else "") + f"\n{ex}\n{p['text']}")
        return "\n\n".join(parts)
    if kind == "group_name":
        parts = ["GROUP OF CONCEPTS: " + ", ".join(payload.get("concepts") or [])]
        if payload.get("before"):   # "Name the groups again": the researcher wants another name than this one
            parts.append(f"NAME DRAFTED BEFORE (the researcher asked for another; do not give it again): "
                         f"{payload['before']}")
        for p in payload["passages"]:
            parts.append(f"P{p['n']}" + (f" (page {p['page']})" if p.get("page") else "")
                         + "\nCONCEPTS IN IT: " + ", ".join(p.get("concepts") or []) + f"\n{p['text']}")
        return "\n\n".join(parts)
    if kind == "resolve":
        parts = [f"DOCUMENT: {payload.get('title') or 'untitled'}"]
        if payload.get("name"):
            parts.append(f"Look in particular for the chain of: {payload['name']}")
        for p in payload["passages"]:
            parts.append(f"P{p['n']}" + (f" (page {p['page']})" if p.get("page") else "") + f"\n{p['text']}")
        return "\n\n".join(parts)
    if kind == "verify_set":
        parts = [f"CLAIM (about SDG target {payload['target']}: {payload['target_description']}):\n{payload['claim']}"]
        for i, p in enumerate(payload["passages"], 1):
            src = (p.get("title") or "untitled") + (f", page {p['page']}" if p.get("page") else "")
            parts.append(f"P{i} | {src}\n{p['text']}")
        if payload.get("read_elsewhere"):  # 0.11.1: a split set (make_verify_vca) says so, as a check does
            parts.append(_read_elsewhere(payload["read_elsewhere"]))
        return "\n\n".join(parts)
    raise ValueError(f"unknown task kind {kind!r}")


def _read_elsewhere(n: int) -> str:
    return (f"{n} other {'excerpt' if n == 1 else 'excerpts'} for this claim {'comes' if n == 1 else 'come'} "
            "from documents you are not shown; they are judged separately. Grade only the passages above, "
            "and in your rationale speak only for them.")
