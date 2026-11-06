"""Read a draft against itself (Margin, no AI): where it may contradict itself, where it is inconsistent, and the
claims a reader may find confusing.

Check a draft (drafts.py) compares each claim with the documents. This reads the draft on its own and with what
Margin already has for it (its sentences, the claims found, their checks and the person's decisions), by rules only:

- **May contradict each other** (`contradiction`)
  - `opposite`: two sentences about the same thing that go opposite ways ("rose" / "fell", "effective" /
    "ineffective") or where one says "not" and the other does not;
  - `numbers`: the same thing with two different numbers ("emissions fell by 12%" / "emissions fell by 20%");
  - `same_passage`: one passage of a document supports one claim and contradicts another (from the checks);
  - `answers_differ`: two claims that say nearly the same thing got opposite answers or opposite decisions.
- **Inconsistent** (`inconsistency`)
  - `abbrev_late`: an abbreviation used before it is spelt out; `abbrev_twice`: one spelt out two different ways;
  - `spelling`: one word written two ways ("organisation" / "organization", "data set" / "dataset").
- **May confuse a reader** (`unclear`), for the claims kept and the sentences rules would pick as claims
  - `pronoun`: opens with "This" or "These" and a verb ("This shows …"), so the reader has to guess what it is;
  - `strength`: hedged and absolute at once ("may always", "possibly proves");
  - `overloaded`: several claims in one long sentence, hard to check or cite.

Each rule is careful rather than complete: a contrast the draft draws on purpose ("However, …" close by, or two
different works cited) is left out. A notice is a prompt to look, not a verdict; the person can set one aside
(`draft_notices`), and it stays aside while the draft's text is the same.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict

from . import citations, claimcheck
from .drafts import _CITATION, _REFS, _RULES, _row, rule_claims
from .references import EXPLETIVE
from .store import Workspace, now
from .textutil import STOPWORDS, split_sentences, tokens

GROUPS = {"contradiction": "May contradict each other", "inconsistency": "Inconsistent",
          "unclear": "May confuse a reader"}
KINDS = {"opposite": "contradiction", "numbers": "contradiction", "same_passage": "contradiction",
         "answers_differ": "contradiction", "abbrev_late": "inconsistency", "abbrev_twice": "inconsistency",
         "spelling": "inconsistency", "pronoun": "unclear", "strength": "unclear", "overloaded": "unclear"}
MAX_PER_KIND = 40
MAX_UNCLEAR = 25  # per kind: a long report has many long sentences; the first ones show the pattern

# ---------------------------------------------------------------------------------------------
# the sentences of a draft
# ---------------------------------------------------------------------------------------------
_NEG = re.compile(r"\b(?:not|no|never|none|neither|nor|cannot|nothing|nobody)\b|n['’]t\b", re.I)
# directions on one scale: a sentence with only "up" words and one with only "down" words go opposite ways
_AXES = (
    (r"increas\w*|ris(?:e|es|ing)|rose|risen|grow(?:s|ing|n)?|grew|growth|higher|gain(?:s|ed)?|boost\w*|"
     r"expand\w*|expansion|doubl\w*|tripl\w*",
     r"decreas\w*|fall(?:s|ing|en)?|fell|declin\w*|drop(?:s|ped|ping)?|shr[iau]nk\w*|lower(?:ed|ing|s)?|"
     r"loss(?:es)?|reduc\w*|halv\w*"),
    (r"better|improv\w*", r"worse|worsen\w*|deteriorat\w*"),
    (r"positive(?:ly)?|benefi\w*", r"negative(?:ly)?|harm\w*|detrimental"),
    (r"strengthen\w*|stronger", r"weaken\w*|weaker"),
    (r"more than|greater than", r"less than|fewer than"),
)
_AXES_RX = [(re.compile(rf"\b(?:{up})\b", re.I), re.compile(rf"\b(?:{down})\b", re.I)) for up, down in _AXES]
_DIRECTION_WORDS = re.compile("|".join(rf"\b(?:{up}|{down})\b" for up, down in _AXES), re.I)
# a contrast the draft draws on purpose, close by
_CONTRAST = re.compile(r"^\W*(?:however|but|yet|in contrast|by contrast|conversely|on the other hand|whereas|"
                       r"unlike|although|though|while|contrary to|on the contrary|instead|still|nevertheless|"
                       r"nonetheless|meanwhile|at the same time|others?|some)\b", re.I)
# a view the draft reports in order to answer it
_REPORTED = re.compile(r"\b(?:some (?:argue|claim|suggest|believe)|critics|it is (?:often|commonly|widely) "
                       r"(?:claimed|assumed|believed|argued)|a common (?:view|assumption|belief)|myth|misconception|"
                       r"contrary to)\b", re.I)
# "effective" / "ineffective": adjectives only ("employment" / "unemployment" are two things, not opposites)
_PREFIX_NEG = re.compile(r"\b(un|in|im)([a-z]{3,}(?:able|ible|ive|ent|ant|al|ic|ous|ary|ory|ful))\b", re.I)
# not statements: a figure or table caption, a source line, a contents line with dot leaders
_CAPTION = re.compile(r"^\W*\d*\s*(?:figure|fig\.|table|source|sources|note|notes|box|chart|map)\b|"
                      r"\.\s?\.\s?\.\s?\.|^\d{1,3}\s+[A-Z]", re.I)
_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})s?\b")


class _Sent:
    __slots__ = ("i", "start", "end", "text", "topic", "neg", "dirs", "words", "cites", "years", "names")

    def __init__(self, i: int, start: int, end: int, text: str):
        self.i, self.start, self.end, self.text = i, start, end, text
        bare = _CITATION.sub(" ", text)
        self.cites = {" ".join(m.group(0).split()) for m in _CITATION.finditer(text)}
        self.neg = len(_NEG.findall(bare)) % 2 == 1
        self.dirs = []
        for up, down in _AXES_RX:
            u, d = bool(up.search(bare)), bool(down.search(bare))
            self.dirs.append(1 if u and not d else -1 if d and not u else 0)
        self.words = {w.lower() for w in re.findall(r"[A-Za-z]+", bare)}
        self.years = set(_YEAR.findall(bare))
        # what the sentence names: capitalised words and abbreviations ("Solar PV", "Europe", "SMR")
        self.names = {w for w in re.findall(r"\b[A-Z][\w\-]*", bare) if w.lower() not in STOPWORDS}
        topic = _DIRECTION_WORDS.sub(" ", _YEAR.sub(" ", bare))
        self.topic = {t for t in tokens(topic) if not t.isdigit() and not re.fullmatch(r"[\d.,]+", t)}


def body_end(text: str) -> int:
    """Where the draft's own writing ends: its reference list is not read for these notices."""
    at = citations.references_start(text)
    return at if at is not None else len(text)


def sentences(text: str) -> list[_Sent]:
    """The sentences of the draft's body that make a statement (not headings, questions or very short lines)."""
    end = body_end(text)
    out: list[_Sent] = []
    for m in re.finditer(r"[^\n]+", text[:end]):
        for a, b in split_sentences(m.group(0), m.start()):
            s = text[a:b].strip()
            flat = " ".join(s.split())
            if len(flat) < 25 or flat.endswith("?") or not re.search(r"[.!:;)\]]$", flat) or _CAPTION.search(flat):
                continue
            lead = len(text[a:b]) - len(text[a:b].lstrip())
            out.append(_Sent(len(out), a + lead, a + lead + len(s), s))
    return out


def _sim(a: set, b: set) -> tuple[float, int]:
    if not a or not b:
        return 0.0, 0
    shared = len(a & b)
    return shared / len(a | b), shared


def _pairs(sents: list[_Sent], min_shared: int = 3):
    """Pairs of sentences sharing at least `min_shared` topic words that are not in most of the draft (an index, so
    a long draft stays quick; a running header's words do not make two sentences alike)."""
    common = max(30, len(sents) // 20)
    index: dict[str, list[int]] = defaultdict(list)
    for s in sents:
        for t in s.topic:
            index[t].append(s.i)
    for s in sents:
        counts: Counter = Counter()
        for t in s.topic:
            post = index[t]
            if len(post) > common:
                continue
            counts.update(j for j in post if j > s.i)
        for j, n in counts.items():
            if n >= min_shared:
                yield s, sents[j]


def _on_purpose(a: _Sent, b: _Sent) -> bool:
    """A contrast drawn on purpose, or two different things: "However, …" close by, a view reported to be answered,
    two different works cited for the two sides, or each sentence naming something the other does not ("Solar PV
    costs …" / "Onshore wind costs …")."""
    if a.names - b.names and b.names - a.names:
        return True
    if b.i - a.i <= 3 and _CONTRAST.match(b.text):
        return True
    if _REPORTED.search(a.text) or _REPORTED.search(b.text):
        return True
    return bool(a.cites and b.cites and not (a.cites & b.cites))


def _prefix_opposite(a: _Sent, b: _Sent) -> str | None:
    """"effective" in one and "ineffective" in the other."""
    for x, y in ((a, b), (b, a)):
        for m in _PREFIX_NEG.finditer(x.text):
            base = m.group(2).lower()
            if base in y.words and m.group(0).lower() not in y.words and base not in x.words:
                return f"“{base}” / “{m.group(0).lower()}”"
    return None


# ---------------------------------------------------------------------------------------------
# May contradict each other
# ---------------------------------------------------------------------------------------------
def opposite(sents: list[_Sent]) -> list[dict]:
    out = []
    for a, b in _pairs(sents):
        jac, shared = _sim(a.topic, b.topic)
        if jac < 0.4 or _on_purpose(a, b):
            continue
        axis = next((k for k, (x, y) in enumerate(zip(a.dirs, b.dirs)) if x and y and x != y), None)
        neg = a.neg != b.neg
        pre = _prefix_opposite(a, b)
        if axis is not None and not neg:
            why = "One says it goes one way, the other the opposite way"
        elif pre and not neg:
            why = f"One says {pre.split(' / ')[0]}, the other {pre.split(' / ')[1]}"
        elif neg and axis is None and not pre and jac >= 0.6 and a.dirs == b.dirs:
            why = "Nearly the same sentence, but one says “not”"
        else:
            continue
        out.append({"kind": "opposite", "score": jac, "places": [a, b],
                    "text": f"{why}. If both are meant, say what differs (a place, a group, a period)."})
    return out


_NUM = re.compile(r"(?<![\w.,])([$€£]\s?)?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?(%|per ?cent\b|percent\b|"
                  r"[A-Za-z°][A-Za-z°/]*)?")
_NOT_UNITS = {"and", "or", "to", "of", "in", "the", "a", "an", "for", "by", "on", "at", "from", "with", "than",
              "is", "are", "was", "were", "et", "s"}


def _numbers(s: _Sent) -> list[tuple[str, float, str]]:
    """(unit, value, as written) of each number with a unit, leaving out years, citations and "Table 3"."""
    bare = _REFS.sub(" ", _CITATION.sub(" ", s.text))
    out = []
    first = re.match(r"\W*", bare).end()
    for m in _NUM.finditer(bare):
        cur, num, unit = m.group(1), m.group(2), (m.group(3) or "")
        if m.start() <= first or (unit[:1].isupper() and unit not in ("GW", "MW", "kW", "TW", "GWh", "MWh", "TWh",
                                                                     "EJ", "PJ", "Mt", "Gt")):
            continue  # a page or list number, or a number before a name
        value = float(num.replace(",", ""))
        u = "%" if unit.lower().replace(" ", "") in ("%", "percent") else unit.lower()
        if cur:
            u = cur.strip() + (u if u not in _NOT_UNITS else "")
        elif u in _NOT_UNITS or not u:
            continue
        if not cur and u != "%" and re.fullmatch(r"1[89]\d{2}|20\d{2}", num):
            continue  # a year
        out.append((u, value, m.group(0).strip()))
    return out


def numbers(sents: list[_Sent]) -> list[dict]:
    out = []
    nums = {s.i: _numbers(s) for s in sents}
    for a, b in _pairs(sents):
        if not nums[a.i] or not nums[b.i] or _on_purpose(a, b):
            continue
        if a.years != b.years:
            continue  # two moments (or one sentence dated and one not), not two answers
        jac, shared = _sim(a.topic, b.topic)
        if jac < 0.55 or shared < 4:
            continue
        ua, ub = Counter(u for u, _, _ in nums[a.i]), Counter(u for u, _, _ in nums[b.i])
        for u in ua:
            if ua[u] != 1 or ub.get(u) != 1:
                continue  # several numbers of one kind in a sentence: which goes with which is not clear
            va = next(x for x in nums[a.i] if x[0] == u)
            vb = next(x for x in nums[b.i] if x[0] == u)
            if abs(va[1] - vb[1]) <= 0.01 * max(abs(va[1]), abs(vb[1]), 1e-9):
                continue
            out.append({"kind": "numbers", "score": jac, "places": [a, b],
                        "text": f"Much the same statement with two numbers: {va[2]} and {vb[2]}. If they measure "
                                f"different things, say how; if not, one of them is wrong."})
            break
    return out


_SUPPORTS = ("supports", "partially_supports")
_FOR = ("supported", "partially_supported")


def from_checks(ws: Workspace, claims: list[dict], thr: float) -> list[dict]:
    """From the checks and decisions already made: one passage on both sides of two claims, and two claims that say
    nearly the same thing with opposite answers."""
    cache = claimcheck.ResultCache(ws, thr)
    sides: dict[str, dict[str, set]] = {}
    status: dict[str, str | None] = {}
    passages: dict[str, dict] = {}
    for c in claims:
        status[c["claim_id"]] = None
        sides[c["claim_id"]] = {"for": set(), "against": set()}
        if not c["hyp_id"]:
            continue
        try:
            res = cache.result(c["hyp_id"])
        except KeyError:
            continue
        status[c["claim_id"]] = res["status"]
        for p in res["parts"]:
            for x in p["passages"]:
                if not x.get("counted"):
                    continue
                sides[c["claim_id"]]["for" if x["verdict"] in _SUPPORTS else "against"].add(x["passage_id"])
                passages.setdefault(x["passage_id"], {"title": x["title"], "location": x["location"]})
    topics = {c["claim_id"]: set(tokens(_DIRECTION_WORDS.sub(" ", c["claim"] or c["quote"]))) for c in claims}
    out = []
    for i, a in enumerate(claims):
        for b in claims[i + 1:]:
            if a["start"] < b["end"] and b["start"] < a["end"]:
                continue
            jac, shared = _sim(topics[a["claim_id"]], topics[b["claim_id"]])
            sa, sb = sides[a["claim_id"]], sides[b["claim_id"]]
            both = (sa["for"] & sb["against"]) | (sa["against"] & sb["for"])
            if both and shared >= 2 and jac >= 0.25:
                pid = sorted(both)[0]
                p = passages[pid]
                where = f"“{p['title']}”" + (f" ({p['location']})" if p.get("location") else "")
                first_for = pid in sa["for"]
                out.append({"kind": "same_passage", "score": 0.5 + jac, "places": [a, b], "claims": True,
                            "text": f"The same passage of {where} supports the {'first' if first_for else 'second'} "
                                    f"and contradicts the {'second' if first_for else 'first'}: the two may say "
                                    f"opposite things."})
                continue
            if jac < 0.6 or shared < 3:
                continue
            da, db = a.get("decision"), b.get("decision")
            if {da, db} == {"supported", "refuted"}:
                out.append({"kind": "answers_differ", "score": jac, "places": [a, b], "claims": True,
                            "text": "Two claims that say nearly the same thing: you marked one supported and the "
                                    "other refuted."})
                continue
            ta, tb = status[a["claim_id"]], status[b["claim_id"]]
            if (ta in _FOR and tb == "contradicted") or (tb in _FOR and ta == "contradicted"):
                out.append({"kind": "answers_differ", "score": jac, "places": [a, b], "claims": True,
                            "text": "Two claims that say nearly the same thing: your documents support one and "
                                    "contradict the other. Do they differ in a detail that matters?"})
    return out


# ---------------------------------------------------------------------------------------------
# Inconsistent
# ---------------------------------------------------------------------------------------------
_ABBR_DEF = re.compile(r"\(([A-Z][A-Za-z]{0,3}[A-Z](?:[A-Za-z]{0,4})?)\)")


def _long_form(before: str, abbr: str) -> tuple[int, str] | None:
    """The words before "(ABC)" that ABC abbreviates, with where they start in `before`: the fewest last words whose
    initials hold its capitals in order, the first word starting with the first."""
    letters = [ch.lower() for ch in re.sub(r"s$", "", abbr) if ch.isupper() or ch.isdigit()]
    if len(letters) < 2:
        return None
    words = list(re.finditer(r"[A-Za-z][\w'’]*(?:-[A-Za-z][\w'’]*)*", before))[-12:]
    for k in range(1, min(len(words), len(letters) + 3) + 1):
        cand = [w.group(0) for w in words[-k:]]
        if cand[0][0].lower() != letters[0]:
            continue
        initials = "".join(part[0].lower() for w in cand for part in w.split("-") if part)
        it = iter(initials)
        if all(ch in it for ch in letters):
            return words[-k].start(), " ".join(cand)
    return None


def abbreviations(text: str) -> list[dict]:
    end = body_end(text)
    body = text[:end]
    defs: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for m in _ABBR_DEF.finditer(body):
        line_start = body.rfind("\n", 0, m.start()) + 1
        before = body[max(line_start, m.start() - 150):m.start()]
        before = re.split(r"[.;:!?]\s", before)[-1]
        found = _long_form(before, m.group(1))
        if found:
            defs[re.sub(r"(?<=[A-Z])s$", "", m.group(1))].append((m.start() - len(before) + found[0], m.end(), found[1]))
    out = []
    for abbr, ds in defs.items():
        first_def = ds[0]
        uses = [u for u in re.finditer(rf"\b{re.escape(abbr)}s?\b", body) if u.start() < first_def[0]
                and not _shouting(body, u.start())]
        if uses:
            u = uses[0]
            out.append({"kind": "abbrev_late", "score": 1.0,
                        "places": [(u.start(), u.end()), (first_def[0], first_def[1])],
                        "text": f"“{abbr}” is used {_times(len(uses))} before it is spelt out as “{first_def[2]}”. "
                                f"Spell it out at its first use."})
        forms: dict[str, tuple[int, int, str]] = {}
        for d in ds:  # a PDF's stray space ("Cong o") or a word more ("… Services programme") is the same form
            key = re.sub(r"[^a-z]", "", d[2].lower())
            if not any(key.startswith(k) or k.startswith(key) for k in forms):
                forms[key] = d
        if len(forms) > 1:
            fs = list(forms.values())
            out.append({"kind": "abbrev_twice", "score": 1.0, "places": [(d[0], d[1]) for d in fs[:3]],
                        "text": f"“{abbr}” is spelt out in {len(fs)} ways: "
                                + " and ".join(f"“{d[2]}”" for d in fs[:3]) + ". Choose one."})
    return out


def _shouting(text: str, at: int) -> bool:
    """Whether the line at `at` is mostly capitals (a heading or a running header)."""
    a, b = text.rfind("\n", 0, at) + 1, text.find("\n", at)
    letters = [ch for ch in text[a:b if b >= 0 else len(text)] if ch.isalpha()]
    return len(letters) >= 8 and sum(ch.isupper() for ch in letters) > 0.6 * len(letters)


def _times(n: int) -> str:
    return "once" if n == 1 else "twice" if n == 2 else f"{n} times"


_OUR = ("colo", "behavio", "labo", "favo", "hono", "humo", "neighbo", "flavo", "harbo", "rumo", "vapo", "endeavo",
        "savo", "vigo", "fervo", "armo")
_RE_ER = ("cent", "lit", "fib", "theat", "calib", "sombr", "spect")
_LL = ("model", "label", "travel", "cancel", "signal", "fuel", "counsel", "level", "channel", "tunnel", "total",
       "equal", "dial", "marshal", "rival", "jewel", "pedal", "quarrel", "shovel")
# two words that are rightly two words in some places and one in others
_NOT_JOINED = {"everyone", "anyone", "someone", "sometime", "everyday", "anyway", "maybe", "into", "onto",
               "everybody", "anybody", "somebody", "nobody", "whatever", "however", "therefore", "forever",
               "altogether", "already", "alright", "awhile", "overall", "nevertheless"}


def _spelling_key(w: str) -> str:
    k = re.sub(r"([iy])z(e|es|ed|ing|ation|ations|er|ers)$", r"\1s\2", w)
    m = re.fullmatch(r"([a-z]+)l(l?)(ed|ing|er|ers)", k)
    if m and m.group(1) + "l" in _LL:
        k = m.group(1) + "l" + m.group(3)
    for stem in _OUR:
        if k.startswith(stem + "ur"):
            k = stem + "r" + k[len(stem) + 2:]
            break
    for stem in _RE_ER:
        if re.fullmatch(rf"{stem}(re|er)(s|d)?", k):
            k = re.sub(r"(re|er)(s|d)?$", r"er\2", k)
            break
    return k


_URL = re.compile(r"https?://\S+|www\.\S+|\b\S+\.(?:org|com|net|int|edu|gov|eu|io)\b\S*", re.I)
_FRAGMENTS = {"ing", "ings", "ed", "ion", "ions", "tion", "tions", "ment", "ments", "ness", "ity", "ies", "ers",
              "able", "ible", "ance", "ence", "ous", "ive", "ally"}


def _artefacts(c: Counter) -> Counter:
    """Leave out the forms a PDF makes: a closed form met once beside a hyphenated one (a line-break hyphen taken
    out, "earlystage"), and a split form far rarer than the whole word ("ene rgy")."""
    hyph = any("-" in w for w in c)
    total = sum(c.values())
    return Counter({w: n for w, n in c.items()
                    if not (hyph and n == 1 and " " not in w and "-" not in w)
                    and not (" " in w and n * 10 < total - n)})


def spelling(text: str) -> list[dict]:
    """One word written two ways: UK and US spelling side by side, or "data set" / "data-set" / "dataset". Only
    words in lower case are counted (a name, such as "World Health Organization", keeps its own spelling)."""
    body = text[:body_end(text)]
    blank = lambda m: " " * len(m.group(0))  # noqa: E731 - keeps every offset
    body_nc = _URL.sub(blank, _CITATION.sub(blank, body))
    forms: dict[str, Counter] = defaultdict(Counter)
    first: dict[str, tuple[int, int]] = {}
    words = list(re.finditer(r"\b[a-z]+(?:-[a-z]+)*\b", body_nc))
    alone = Counter(m.group(0) for m in words)
    for m in words:
        w = m.group(0)
        if len(w) < 4:
            continue
        key = _spelling_key(w.replace("-", ""))
        forms[key][w] += 1
        first.setdefault(w, (m.start(), m.end()))
    # two words that are one elsewhere: "data set" next to "dataset" or "data-set"
    known = set(forms)
    for a, b in zip(words, words[1:]):
        x, y = a.group(0), b.group(0)
        if b.start() - a.end() != 1 or body_nc[a.end()] != " " or "-" in x + y:
            continue
        joined = _spelling_key(x + y)
        # both halves words of their own elsewhere: "data set", not a word split by a PDF ("tra nsporting")
        if (joined in known and joined not in _NOT_JOINED and len(x) >= 3 and len(y) >= 3 and alone[x] >= 2
                and alone[y] >= 2 and y not in _FRAGMENTS):
            w = f"{a.group(0)} {b.group(0)}"
            forms[joined][w] += 1
            first.setdefault(w, (a.start(), b.end()))
    out = []
    for key, c in forms.items():
        c = _artefacts(c)
        if len(c) < 2 or all(" " in w or "-" in w for w in c):
            continue  # "large-scale" before a noun, "on a large scale" after: both right
        ws_ = [w for w, _ in c.most_common(3)]
        out.append({"kind": "spelling", "score": sum(c.values()) / 100, "places": [first[w] for w in ws_],
                    "text": "Written " + " and ".join(f"“{w}” ({_times(c[w])})" for w in ws_)
                            + ". Choose one spelling."})
    return out


# ---------------------------------------------------------------------------------------------
# May confuse a reader
# ---------------------------------------------------------------------------------------------
_PRONOUN_VERB = re.compile(
    r"^\W*(this|these|those)\s+(?:also\s+|therefore\s+|thus\s+)?(is|are|was|were|has|have|had|shows?|"
    r"showed|suggests?|suggested|means?|meant|leads?|led|can|could|may|might|will|would|does|did|indicates?|"
    r"indicated|demonstrates?|demonstrated|implies|implied|results?|resulted|causes?|caused|makes?|made|explains?|"
    r"reflects?|confirms?|supports?|highlights?|reveals?|underlines?)\b", re.I)
_HEDGE = re.compile(r"\b(?:may|might|possibly|perhaps|probably|likely|seems? to|appears? to|arguably)\b", re.I)
_ABSOLUTE = re.compile(r"\b(?:certainly|definitely|undoubtedly|unquestionably|proves?|proven|without (?:a |any )?"
                       r"doubt|in all cases|invariably|beyond (?:any )?doubt)\b", re.I)


def unclear(text: str, spans: list[tuple[int, int, str | None]]) -> list[dict]:
    out = []
    for a, b, cid in spans:
        s = " ".join(text[a:b].split())
        place = [(a, b, cid)]
        m = _PRONOUN_VERB.match(s)
        if m and not EXPLETIVE.match(s):
            out.append({"kind": "pronoun", "score": 0.5, "places": place,
                        "text": f"Opens with “{m.group(1)}” and a verb: a reader has to guess what "
                                f"“{m.group(1).lower()}” is. Name it (“{m.group(1).capitalize()} "
                                f"{'rise in prices' if m.group(1).lower() == 'this' else 'results'} …”)."})
        h, ab = _HEDGE.search(s), _ABSOLUTE.search(s)
        if h and ab:
            out.append({"kind": "strength", "score": 0.5, "places": place,
                        "text": f"Careful and absolute at once (“{h.group(0)}”, “{ab.group(0)}”): say how sure "
                                f"you are, once."})
        n = len(s.split())
        kinds = {k for k, rx in _RULES if rx.search(_CITATION.sub("", s))}
        if n > 55 or (n > 35 and len(kinds) >= 3):
            out.append({"kind": "overloaded", "score": n / 100, "places": place,
                        "text": f"{n} words with several claims in one sentence: split it, so each claim can be "
                                f"checked and cited on its own."})
    return out


# ---------------------------------------------------------------------------------------------
# all of it, for the draft page
# ---------------------------------------------------------------------------------------------
def _key(kind: str, places: list[tuple[int, int]], text: str) -> str:
    sig = kind + "|" + "|".join(" ".join(text[a:b].split()) for a, b in sorted(places))
    return hashlib.sha1(sig.encode()).hexdigest()[:16]


def _claim_at(claims: list[dict], a: int, b: int) -> dict | None:
    """The claim a sentence mostly is (at least half of the shorter of the two overlaps)."""
    best, most = None, 0
    for c in claims:
        n = min(b, c["end"]) - max(a, c["start"])
        if n > most:
            best, most = c, n
    return best if best and most >= 0.5 * min(b - a, best["end"] - best["start"]) else None


def review(ws: Workspace, draft_id: str, threshold: float | None = None) -> dict:
    """Every notice about the draft read against itself, most telling first within each group."""
    d = _row(ws, draft_id)
    text = d["text"]
    thr = claimcheck._threshold(ws, threshold)
    claims = [dict(r) for r in ws.query("SELECT claim_id, start, end, quote, claim, hyp_id, skip, decision "
                                         "FROM draft_claims WHERE draft_id=? ORDER BY start, end", (draft_id,))]
    kept = [c for c in claims if not c["skip"]]
    sents = sentences(text)
    found = opposite(sents) + numbers(sents) + from_checks(ws, kept, thr)
    found += abbreviations(text) + spelling(text)
    # the claims kept, and the sentences rules would pick that are not one of them
    spans = [(c["start"], c["end"], c["claim_id"]) for c in kept]
    for s in sents:
        if not _claim_at(kept, s.start, s.end) and rule_claims(s.text):
            spans.append((s.start, s.end, None))
    found += unclear(text, spans)

    dismissed = {r[0]: r[1] for r in ws.query("SELECT key, dismissed_at FROM draft_notices WHERE draft_id=?",
                                              (draft_id,))}
    notices, seen_pairs = [], set()
    per_kind: Counter = Counter()
    for f in sorted(found, key=lambda f: -f["score"]):
        places = []
        for p in f["places"]:
            if isinstance(p, _Sent):
                places.append((p.start, p.end, None))
            elif isinstance(p, dict):
                places.append((p["start"], p["end"], p["claim_id"]))
            else:
                places.append((p[0], p[1], p[2] if len(p) > 2 else None))
        spans_only = [(a, b) for a, b, _ in places]
        if KINDS[f["kind"]] == "contradiction":
            pair = tuple(sorted(spans_only))
            if pair in seen_pairs:
                continue  # one notice per pair of places
            seen_pairs.add(pair)
        if per_kind[f["kind"]] >= (MAX_UNCLEAR if KINDS[f["kind"]] == "unclear" else MAX_PER_KIND):
            continue
        per_kind[f["kind"]] += 1
        key = _key(f["kind"], spans_only, text)
        out_places = []
        for a, b, cid in places:
            c = next((x for x in claims if x["claim_id"] == cid), None) if cid else _claim_at(kept, a, b)
            out_places.append({"start": a, "end": b, "quote": " ".join(text[a:b].split()),
                               "claim_id": c["claim_id"] if c else None})
        notices.append({"key": key, "kind": f["kind"], "group": KINDS[f["kind"]], "text": f["text"],
                        "places": out_places, "dismissed": key in dismissed})
    order = list(GROUPS)
    notices.sort(key=lambda n: (order.index(n["group"]), n["places"][0]["start"]))
    open_ = [n for n in notices if not n["dismissed"]]
    return {"draft_id": draft_id, "notices": notices, "groups": GROUPS,
            "counts": {g: sum(1 for n in open_ if n["group"] == g) for g in GROUPS},
            "open": len(open_), "dismissed": len(notices) - len(open_),
            "read": {"sentences": len(sents), "claims": len(kept), "checked": sum(1 for c in kept if c["hyp_id"])}}


def set_dismissed(ws: Workspace, draft_id: str, key: str, dismissed: bool = True) -> None:
    """Set a notice aside ("not a problem"), or bring it back."""
    _row(ws, draft_id)
    if not re.fullmatch(r"[0-9a-f]{16}", key or ""):
        raise ValueError("Not a notice of this draft.")
    with ws.connect() as cx:
        if dismissed:
            cx.execute("INSERT OR REPLACE INTO draft_notices(draft_id, key, dismissed_at) VALUES (?,?,?)",
                       (draft_id, key, now()))
        else:
            cx.execute("DELETE FROM draft_notices WHERE draft_id=? AND key=?", (draft_id, key))
