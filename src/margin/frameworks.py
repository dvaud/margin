"""Frameworks: optional codebooks a hypothesis can be tagged with, such as the 169 SDG targets.

A framework is a list of codes with descriptions. When a hypothesis names a code, the model sees the code's text
next to the claim, and the history can be filtered by it. The SDG targets ship with the package (`sdg`); any
other codebook is a CSV file:

    code,description[,group][,group_name][,keywords][,include][,exclude][,source]
    H1,"Remote work lowers commuting emissions",transport,Transport

placed in MARGIN_HOME/frameworks/ (all projects) or in a project's frameworks/ folder (that project only), or
added in the app. An optional `<name>.json` next to it gives {"title": ..., "label": ...}.

Margin 0.9 reads more of a codebook:
- the columns `keywords` (words and phrases separated by ";", found as whole words in a passage), `include` (when to
  use the code), `exclude` (when not to, and which code to use instead) and `source` (where the definition comes
  from). Keywords and the include text are matched with the description; include, exclude and source go to the AI;
- from the JSON file: `direction_labels` (the words for helps, hinders, mixed and not stated, such as "holds
  together" and "pulls apart"), `direction_note` (what the direction is relative to), `one_main` (at most one main
  code per passage), `practice_and_element` (a label also names the practice and the element, in the passage's own
  words), `stance` and `sources` (shown with the codebook);
- a codebook of ALL_CODES_UP_TO codes or fewer is sent whole to the AI with every passage, and the AI reads every
  passage, not only those the keyword search found something in.

Margin ships two such codebooks from social practice theory in data/codebooks (`practice`, `change_framing`).
"""
from __future__ import annotations

import csv
import io
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .retrieve import BM25
from .textutil import tokens

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
ALL_CODES_UP_TO = 30   # a codebook this small goes to the AI whole, with every passage (0.9)
DIRECTION_WORDS = {"helps": "helps", "hinders": "hinders", "mixed": "mixed", "not_stated": "not stated"}
CODEBOOKS = Path(__file__).with_name("data") / "codebooks"


@dataclass(frozen=True)
class Code:
    code: str
    description: str
    group: str = ""
    group_name: str = ""
    keywords: tuple[str, ...] = ()   # 0.9: words and phrases a passage may use for it
    include: str = ""                # when to use the code
    exclude: str = ""                # when not to, and what to use instead
    ref: str = ""                    # where its definition comes from (the CSV column `source`)


@dataclass
class Framework:
    name: str
    title: str
    label: str                       # what one code is called, e.g. "SDG target"
    codes: dict[str, Code]
    source: str = "bundled"          # bundled | home | project
    lexicon: list[tuple[str, str]] = field(default_factory=list)
    directional: bool = False        # its codes are aims a text can help or hinder (the SDG targets): labels say which
    match_text: dict[str, str] = field(default_factory=dict)  # the text a code is matched by, when not its description
    direction_words: dict[str, str] = field(default_factory=lambda: dict(DIRECTION_WORDS))
    direction_note: str = ""         # what a direction is relative to (said to the AI and shown with the codebook)
    one_main: bool = False           # at most one main code per passage
    practice_and_element: bool = False  # a label also names the practice and the element, in the passage's words
    stance: str = ""
    sources: tuple[str, ...] = ()
    _index: tuple | None = None
    _lex: tuple | None = None
    _kw: list | None = None

    @property
    def send_all(self) -> bool:
        """Small codebooks go to the AI whole (0.9): their codes are often analytical, so their words are not in
        the text and a keyword search misses them."""
        return len(self.codes) <= ALL_CODES_UP_TO

    def sorted_codes(self) -> list[Code]:
        if self.name == "sdg":
            from .taxonomy import target_sort_key

            return sorted(self.codes.values(), key=lambda c: target_sort_key(c.code))
        return sorted(self.codes.values(), key=lambda c: _natural(c.code))

    def normalise(self, code: str | None) -> str | None:
        if not code:
            return None
        c = str(code).strip()
        if c in self.codes:
            return c
        if self.name == "sdg":
            from .taxonomy import normalise_target

            return normalise_target(c)
        if self.name == "sdg_goals":
            m = re.match(r"^(?:sdg|goal)?\s*(\d{1,2})(?:\s*\.\s*\w+)?\.?$", c.lower())
            return str(int(m.group(1))) if m and str(int(m.group(1))) in self.codes else None
        low = {k.lower(): k for k in self.codes}
        return low.get(c.lower())

    def code_text(self, code: str) -> str:
        """The words a code is matched by: its description and group name (or its own matching text)."""
        c = self.codes[code]
        return self.match_text.get(code) or " ".join(x for x in (c.description, c.group_name, " ".join(c.keywords),
                                                                  c.include) if x)

    def keyword_hits(self, text: str) -> dict[str, list[str]]:
        """Codes whose keywords (the CSV column) occur in the text as whole words: {code: [keywords found]}."""
        if self._kw is None:
            self._kw = [(re.compile(r"(?<!\w)" + r"\W+".join(map(re.escape, k.lower().split())) + r"(?!\w)"), k, c.code)
                        for c in self.codes.values() for k in c.keywords if k.strip()]
        if not self._kw:
            return {}
        low = text.lower()
        out: dict[str, list[str]] = {}
        for rx, k, code in self._kw:
            if rx.search(low):
                out.setdefault(code, []).append(k)
        return out

    def _bm(self) -> tuple:
        if self._index is None:
            cs = self.sorted_codes()
            toks = [tokens(self.code_text(c.code)) for c in cs]
            self._index = (cs, BM25(toks), {c.code: set(t) for c, t in zip(cs, toks)})
        return self._index

    def scores(self, text: str, toks: list[str] | None = None, lex_hits: set[str] | None = None) -> dict[str, float]:
        """BM25 score of every code that shares a word with the text, plus the lexicon's common phrasings (`lex_hits`
        when the caller matched them already)."""
        cs, bm, _sets = self._bm()
        scores = {cs[i].code: s for i, s in bm.sparse(tokens(text) if toks is None else toks).items()}
        top = max(scores.values(), default=0.0)
        hits = self.lexicon_hits(text) if lex_hits is None else lex_hits
        for code in hits:  # common phrasings the code texts do not use ("water stress", "jobs")
            scores[code] = scores.get(code, 0.0) + 10 + top
        return scores

    def lexicon_hits(self, text: str) -> set[str]:
        """Codes whose common phrasings occur in the text (one pass over the text for all of them)."""
        if not self.lexicon:
            return set()
        if self._lex is None:  # the patterns are lower case: matching lower-cased text is faster than re.I
            self._lex = [(re.compile(p.lower()), c) for p, c in self.lexicon if c in self.codes]
        low = text.lower()
        return {c for rx, c in self._lex if rx.search(low)}

    def code_stems(self, code: str) -> set[str]:
        return self._bm()[2].get(code, set())

    def suggest(self, text: str, n: int = 5) -> list[dict]:
        """Codes whose wording is closest to the text (keyword match, no model): a starting point only."""
        scores = self.scores(text)
        best = sorted((c for c in scores if scores[c] > 0), key=lambda c: (-scores[c], _natural(c)))[:n]
        return [{"code": c, "group": self.codes[c].group, "description": self.codes[c].description,
                 "score": round(scores[c], 2)} for c in best]

    def info(self, with_codes: bool = False) -> dict:
        out = {"name": self.name, "title": self.title, "label": self.label, "source": self.source, "codes": len(self.codes),
               "directional": self.directional, "groups": len({c.group for c in self.codes.values() if c.group}),
               "direction_words": self.direction_words, "direction_note": self.direction_note,
               "one_main": self.one_main, "practice_and_element": self.practice_and_element,
               "send_all": self.send_all, "stance": self.stance, "sources": list(self.sources)}
        if with_codes:
            out["items"] = [{"code": c.code, "description": c.description, "group": c.group, "group_name": c.group_name,
                             "keywords": list(c.keywords), "include": c.include, "exclude": c.exclude, "source": c.ref}
                            for c in self.sorted_codes()]
        return out


def _natural(code: str) -> list:
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", code)]


_LOCK = threading.Lock()
_CACHE: dict[tuple, Framework] = {}


def _sdg() -> Framework:
    key = ("bundled", "sdg")
    with _LOCK:
        if key not in _CACHE:
            from .llm import LEXICON
            from .taxonomy import targets

            codes = {t.code: Code(t.code, t.description, str(t.goal), t.goal_name) for t in targets().values()}
            _CACHE[key] = Framework("sdg", "UN Sustainable Development Goals (169 targets)", "SDG target", codes,
                                    "bundled", list(LEXICON), directional=True)
        return _CACHE[key]


def _sdg_goals() -> Framework:
    """The 17 goals, as a codebook of their own (faster profiles, more agreement; coarser). A goal is matched by
    its name and the texts of its targets."""
    key = ("bundled", "sdg_goals")
    with _LOCK:
        if key not in _CACHE:
            from .llm import LEXICON
            from .taxonomy import goal_names, targets

            names = goal_names()
            texts: dict[str, list[str]] = {}
            for t in targets().values():
                texts.setdefault(str(t.goal), []).append(t.description)
            codes = {str(g): Code(str(g), name, str(g), name) for g, name in sorted(names.items())}
            lex = [(pat, code.split(".")[0]) for pat, code in LEXICON]
            _CACHE[key] = Framework("sdg_goals", "UN Sustainable Development Goals (17 goals)", "SDG", codes, "bundled",
                                    lex, directional=True,
                                    match_text={g: f"{codes[g].description} " + " ".join(texts.get(g, [])) for g in codes})
        return _CACHE[key]


def parse_csv(text: str) -> dict[str, Code]:
    """Codes from CSV text. Raises ValueError naming the problem."""
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        raise ValueError("The file has no rows. Columns: code, description (and optionally group, group_name).")
    cols = {c.strip().lower(): c for c in rows[0].keys() if c}
    if "code" not in cols or "description" not in cols:
        raise ValueError("The file needs the columns code and description (and optionally group, group_name).")
    out: dict[str, Code] = {}
    for i, r in enumerate(rows, start=2):
        code = (r.get(cols["code"]) or "").strip()
        desc = " ".join((r.get(cols["description"]) or "").split())
        if not code and not desc:
            continue
        if not code or not desc:
            raise ValueError(f"Row {i}: every row needs a code and a description.")
        if len(code) > 40:
            raise ValueError(f"Row {i}: the code {code[:40]!r}… is longer than 40 characters.")
        if code in out:
            raise ValueError(f"Row {i}: the code {code!r} appears twice.")
        def col(name: str) -> str:
            return " ".join((r.get(cols[name]) or "").split()) if name in cols else ""

        kws = tuple(k.strip() for k in col("keywords").split(";") if k.strip())
        out[code] = Code(code, desc, col("group"), col("group_name"), kws, col("include"), col("exclude"),
                         col("source"))
    if len(out) > 5000:
        raise ValueError("A framework can hold at most 5,000 codes.")
    return out


def _load_file(path: Path, source: str) -> Framework | None:
    try:
        st = path.stat()
        side = path.with_suffix(".json")
        sst = side.stat() if side.exists() else None  # 0.9: a changed JSON file is read again too
        key = (str(path), st.st_mtime_ns, st.st_size, sst and (sst.st_mtime_ns, sst.st_size))
    except OSError:
        return None
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
    try:
        codes = parse_csv(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeDecodeError):
        return None
    meta = {}
    side = path.with_suffix(".json")
    if side.exists():
        try:
            meta = json.loads(side.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}
    name = path.stem.lower()
    fw = Framework(name, str(meta.get("title") or name.replace("_", " ").replace("-", " ").capitalize()),
                   str(meta.get("label") or "code"), codes, source, directional=bool(meta.get("directional")),
                   **_meta_fields(meta))
    with _LOCK:
        _CACHE[key] = fw
    return fw


def _meta_fields(meta: dict) -> dict:
    """The 0.9 settings of a codebook's JSON file (anything missing or malformed keeps its default)."""
    words = dict(DIRECTION_WORDS)
    got = meta.get("direction_labels")
    if isinstance(got, dict):
        for k in words:
            v = " ".join(str(got.get(k) or "").split())[:40]
            if v:
                words[k] = v
    src = meta.get("sources")
    return {"direction_words": words, "direction_note": " ".join(str(meta.get("direction_note") or "").split())[:600],
            "one_main": bool(meta.get("one_main")), "practice_and_element": bool(meta.get("practice_and_element")),
            "stance": " ".join(str(meta.get("stance") or "").split())[:1000],
            "sources": tuple(str(x) for x in src[:20]) if isinstance(src, list) else ()}


def _built_in() -> dict[str, Framework]:
    """The codebooks that ship in data/codebooks (0.9: social practice theory), as source "bundled"."""
    out = {}
    order = ("practice", "change_framing")
    for p in sorted(CODEBOOKS.glob("*.csv"), key=lambda p: (order.index(p.stem) if p.stem in order else 99, p.stem)):
        fw = _load_file(p, "bundled")
        if fw:
            out[fw.name] = fw
    return out


def _folders(ws=None) -> list[tuple[Path, str]]:
    from .home import home

    out = [(home() / "frameworks", "home")]
    if ws is not None:
        out.append((Path(ws.root) / "frameworks", "project"))
    return out


def available(ws=None) -> dict[str, Framework]:
    """All frameworks a project can use: home-wide, then the project's own, then the built-in ones: social practice
    theory (0.9), then the SDG codebooks (Margin 0.8 lists them last, as examples)."""
    out = {}
    for folder, source in _folders(ws):
        if folder.is_dir():
            for p in sorted(folder.glob("*.csv")):
                fw = _load_file(p, source)
                if fw and NAME_RE.match(fw.name) and fw.name not in BUNDLED:
                    out[fw.name] = fw
    out.update(_built_in())
    out.update({"sdg": _sdg(), "sdg_goals": _sdg_goals()})
    return out


def get(name: str | None, ws=None) -> Framework | None:
    if not name:
        return None
    fw = available(ws).get(name)
    if fw is None:
        raise ValueError(f"Unknown framework {name!r}. Available: {', '.join(available(ws))}.")
    return fw


BUNDLED = ("sdg", "sdg_goals", "practice", "change_framing")


def save(ws, name: str, csv_text: str, title: str | None = None, label: str | None = None,
         directional: bool = False) -> Framework:
    """Add (or replace) a project framework from CSV text. `directional`: its codes are aims a text can help or
    hinder, so a profile says which."""
    n = (name or "").strip().lower().replace(" ", "_")
    if not NAME_RE.match(n) or n in BUNDLED:
        raise ValueError("Give the framework a short name: letters, digits, - or _ (and not 'sdg', 'sdg_goals', "
                         "'practice' or 'change_framing': built-in codebooks have these names).")
    parse_csv(csv_text)  # validate before writing
    folder = Path(ws.root) / "frameworks"
    folder.mkdir(exist_ok=True)
    (folder / f"{n}.csv").write_text(csv_text.lstrip("﻿"), encoding="utf-8")
    meta = {k: v for k, v in (("title", title), ("label", label), ("directional", bool(directional) or None)) if v}
    side = folder / f"{n}.json"
    if meta:
        side.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    elif side.exists():
        side.unlink()
    fw = _load_file(folder / f"{n}.csv", "project")
    assert fw is not None
    return fw


def delete(ws, name: str) -> None:
    if not NAME_RE.match(name or "") or name in BUNDLED:
        raise KeyError(name)  # never a path: the name comes from a URL
    folder = Path(ws.root) / "frameworks"
    p = folder / f"{name}.csv"
    if not p.exists():
        raise KeyError(name)
    p.unlink()
    side = folder / f"{name}.json"
    if side.exists():
        side.unlink()


def resolve(ws, framework: str | None, code: str | None) -> tuple[str | None, str | None, str | None, str | None]:
    """(framework, code, description, label) for a hypothesis; raises ValueError for an unknown code."""
    if not code:
        return (framework or None), None, None, None
    fw = get(framework or "sdg", ws)
    assert fw is not None
    c = fw.normalise(code)
    if not c:
        raise ValueError(f"Unknown {fw.label} {code!r} in {fw.title}.")
    return fw.name, c, fw.codes[c].description, fw.label
