"""Output schemas for each model task. Loose spellings are normalised before validation."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .taxonomy import (CLAIM_SEGMENTS, DIRECTIONS, EVIDENCE_VERDICTS, HORIZONS, INFLUENCES, SCALES, SIDES, VERDICTS,
                       normalise_target)

_ALIASES = {
    "end-use": "end_use", "enduse": "end_use", "end use": "end_use", "use": "end_use",
    "transport": "transportation", "storage": "transportation", "distribution": "transportation",
    "whole chain": "whole_chain", "all": "whole_chain", "value chain": "whole_chain",
    "medium_to_long_term": "medium_long_term", "medium-long": "medium_long_term", "long_term": "medium_long_term",
    "medium_term": "medium_long_term", "short": "short_term", "none": "not_stated", "unknown": "not_stated",
    "not stated": "not_stated", "n/a": "not_stated", "neutral": "no_effect", "none_effect": "no_effect",
    "support": "supports", "supported": "supports", "partial": "partially_supports",
    "partially_supported": "partially_supports", "partly_supports": "partially_supports", "partial_support": "partially_supports", "refute": "refutes", "contradicts": "refutes",
    "nei": "not_enough_info", "not enough info": "not_enough_info", "insufficient": "not_enough_info",
    "unspecified_scale": "unspecified", "exporter": "producer", "exporting": "producer", "importing": "importer",
}


def _norm_enum(v: object) -> object:
    if not isinstance(v, str):
        return v
    s = v.strip().lower()
    s = _ALIASES.get(s, s)
    s = s.replace("-", "_").replace(" ", "_")
    return _ALIASES.get(s, s)


class EvidenceQuote(BaseModel):
    field: str = "claim"
    quote: str


class TargetEffect(BaseModel):
    target: str
    direction: Literal[DIRECTIONS]
    influence: Literal[INFLUENCES] = "unclear"

    @field_validator("target", mode="before")
    @classmethod
    def _target(cls, v):
        code = normalise_target(v)
        if not code:
            raise ValueError(f"unknown SDG target {v!r}; use a code such as '6.4' or '7.b'")
        return code

    @field_validator("direction", "influence", mode="before")
    @classmethod
    def _enum(cls, v):
        return _norm_enum(v)


class ImpactClaimOut(BaseModel):
    claim: str = Field(min_length=10)
    activity: str = Field(min_length=2)
    segment: Literal[CLAIM_SEGMENTS]
    targets: list[TargetEffect] = Field(min_length=1)
    place: Optional[str] = None
    countries: list[str] = Field(default_factory=list)
    scale: Literal[SCALES] = "unspecified"
    side: Literal[SIDES] = "unspecified"
    horizon: Literal[HORIZONS] = "not_stated"
    condition: Optional[str] = None
    policy_lever: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceQuote] = Field(min_length=1)

    @field_validator("segment", "scale", "side", "horizon", mode="before")
    @classmethod
    def _enum(cls, v):
        return _norm_enum(v) if v is not None else v

    @field_validator("countries", mode="before")
    @classmethod
    def _countries(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v


class InteractionOut(BaseModel):
    from_target: str
    to_target: str
    score: int = Field(ge=-3, le=3)
    quote: str

    @field_validator("from_target", "to_target", mode="before")
    @classmethod
    def _target(cls, v):
        code = normalise_target(v)
        if not code:
            raise ValueError(f"unknown SDG target {v!r}")
        return code


class ExtractOut(BaseModel):
    claims: list[dict] = Field(default_factory=list)       # validated one by one as ImpactClaimOut
    interactions: list[dict] = Field(default_factory=list)  # validated one by one as InteractionOut
    note: Optional[str] = None


class VcaClaimOut(BaseModel):
    text: str = Field(min_length=10)
    quote: str
    segment: Literal[CLAIM_SEGMENTS] = "unclear"
    direction: Literal[DIRECTIONS]
    place: Optional[str] = None
    horizon: Literal[HORIZONS] = "not_stated"
    condition: Optional[str] = None

    @field_validator("segment", "direction", "horizon", mode="before")
    @classmethod
    def _enum(cls, v):
        return _norm_enum(v) if v is not None else v


class SplitOut(BaseModel):
    claims: list[VcaClaimOut] = Field(min_length=1)


class VerifyOut(BaseModel):
    verdict: Literal[VERDICTS]
    confidence: float = Field(ge=0, le=1)
    quote: Optional[str] = None
    rationale: Optional[str] = None

    @field_validator("verdict", mode="before")
    @classmethod
    def _enum(cls, v):
        return _norm_enum(v)


class PassageEvidence(BaseModel):
    passage: int = Field(ge=1, description="number of the passage as shown (P1 = 1)")
    verdict: Literal[EVIDENCE_VERDICTS]
    confidence: float = Field(ge=0, le=1)
    quote: str = Field(min_length=3)

    @field_validator("verdict", mode="before")
    @classmethod
    def _enum(cls, v):
        return _norm_enum(v)

    @field_validator("passage", mode="before")
    @classmethod
    def _num(cls, v):
        if isinstance(v, str):
            v = v.strip().upper().lstrip("P")
        return v


class VerifySetOut(BaseModel):
    evidence: list[PassageEvidence] = Field(default_factory=list)
    rationale: Optional[str] = None


def _none_words(v):
    if v is None:
        return None
    v = " ".join(str(v).split())
    return None if v.lower().strip(" .") in ("", "null", "none", "n/a", "no", "same", "nothing") else v


class CheckEvidence(PassageEvidence):
    """A grade of the hypothesis checker (check-v3): may say the passage is about another group or setting; (check-v4)
    may name what its quote refers to, quoted from the passage or the text before it."""
    scope_note: Optional[str] = Field(None, max_length=200)
    refers_to: Optional[str] = Field(None, max_length=200)

    @field_validator("scope_note", mode="before")
    @classmethod
    def _note(cls, v):
        v = _none_words(v)
        return v.strip(" .")[:200] if v else None

    @field_validator("refers_to", mode="before")
    @classmethod
    def _ref(cls, v):
        v = _none_words(v)
        return v.strip()[:200] if v else None


class CheckOut(BaseModel):
    evidence: list[CheckEvidence] = Field(default_factory=list)
    rationale: Optional[str] = None


def clean_terms(terms) -> list[str]:
    """Search words as a person or a model gives them: trimmed, at most 80 characters each, no repeats, at most 40
    (one routine for the model's answer and a person's words, 0.11.1)."""
    if isinstance(terms, str):
        terms = terms.replace(";", ",").split(",")
    out: list[str] = []
    for t in terms or []:
        t = " ".join(str(t).split()).strip("\"'")
        if t and len(t) <= 80 and t.lower() not in {x.lower() for x in out}:
            out.append(t)
    return out[:40]


class ExpandOut(BaseModel):
    terms: list[str] = Field(min_length=1)

    @field_validator("terms", mode="before")
    @classmethod
    def _clean(cls, v):
        return clean_terms(v)


PART_ROLES = ("condition", "mechanism", "outcome", "comparison", "scope", "component")


class HypothesisPart(BaseModel):
    text: str = Field(min_length=10, max_length=400)
    role: Literal[PART_ROLES] = "component"

    @field_validator("role", mode="before")
    @classmethod
    def _role(cls, v):
        v = _norm_enum(v) if v is not None else "component"
        return v if v in PART_ROLES else "component"


class DecomposeOut(BaseModel):
    parts: list[HypothesisPart] = Field(min_length=1, max_length=6)
    note: Optional[str] = None

    @field_validator("parts", mode="before")
    @classmethod
    def _strings(cls, v):  # a plain list of sentences is accepted too
        if isinstance(v, list):
            return [{"text": x} if isinstance(x, str) else x for x in v]
        return v


# ---------------------------------------------------------------------------------------------
# 0.7: codebook labels (label-v1), links between terms (link-v1), theme names (theme-v1), reference chains (resolve-v1)
# ---------------------------------------------------------------------------------------------
class CodeLabel(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    relevance: Literal["main", "mentioned"] = "mentioned"
    direction: Literal["helps", "hinders", "mixed", "not_stated"] = "not_stated"
    confidence: float = Field(ge=0, le=1)
    quote: str = Field(min_length=3)
    reason: str = Field("", max_length=200)

    @field_validator("code", mode="before")
    @classmethod
    def _code(cls, v):
        return str(v).strip() if v is not None else v

    @field_validator("relevance", mode="before")
    @classmethod
    def _rel(cls, v):
        v = _norm_enum(v) if v is not None else "mentioned"
        return {"main_topic": "main", "primary": "main", "central": "main", "mention": "mentioned",
                "minor": "mentioned", "secondary": "mentioned"}.get(v, v)

    @field_validator("direction", mode="before")
    @classmethod
    def _dir(cls, v):
        v = _norm_enum(v) if v is not None else "not_stated"
        return {"positive": "helps", "help": "helps", "negative": "hinders", "hinder": "hinders",
                "both": "mixed", "no_effect": "not_stated", "unclear": "not_stated"}.get(v, v)

    @field_validator("reason", mode="before")
    @classmethod
    def _reason(cls, v):
        return " ".join(str(v or "").split())[:200]


class LabelOut(BaseModel):
    labels: list[CodeLabel] = Field(default_factory=list)
    note: Optional[str] = None


LINK_RELATIONS = ("same", "broader", "narrower", "related", "different",
                  # link-v2 (D1, the last part): the kinds the text patterns and a person could already give. From the
                  # first term (a) to the second (b); needed_by and shaped_by are the same seen from b (accepted, so an
                  # answer that turns the pair round in words is not sent back); clashes is the same from both ends
                  "needs", "needed_by", "shapes", "shaped_by", "clashes")


class TermLink(BaseModel):
    a: int = Field(ge=1)
    b: int = Field(ge=1)
    relation: Literal[LINK_RELATIONS]
    confidence: float = Field(ge=0, le=1)
    quote_a: str = Field(min_length=3)
    quote_b: str = Field(min_length=3)

    @field_validator("relation", mode="before")
    @classmethod
    def _rel(cls, v):
        v = _norm_enum(v)
        return {"synonym": "same", "equivalent": "same", "identical": "same", "parent": "broader",
                "child": "narrower", "hypernym": "broader", "hyponym": "narrower", "unrelated": "different",
                "co_occurs": "related",
                # link-v2: other words for the three new kinds
                "requires": "needs", "depends_on": "needs", "relies_on": "needs", "need": "needs",
                "required_by": "needed_by", "influences": "shapes", "shape": "shapes", "affects": "shapes",
                "influenced_by": "shaped_by", "clashes_with": "clashes", "clash": "clashes", "conflicts": "clashes",
                "conflicts_with": "clashes", "conflict": "clashes", "at_odds": "clashes"}.get(v, v)


class LinkOut(BaseModel):
    relations: list[TermLink] = Field(min_length=1)


class QuoteRef(BaseModel):
    passage: int = Field(ge=1)
    quote: str = Field(min_length=3)

    @field_validator("passage", mode="before")
    @classmethod
    def _num(cls, v):
        if isinstance(v, str):
            v = v.strip().upper().lstrip("P")
        return v


class ThemeOut(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    name_quote: QuoteRef
    description: str = Field(min_length=10, max_length=300)
    description_quote: QuoteRef

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v):
        v = " ".join(str(v or "").split()).strip(" .\"'")
        if len(v.split()) > 6:
            raise ValueError("the name must have at most six words")
        return v

    @field_validator("description", mode="before")
    @classmethod
    def _desc(cls, v):
        return " ".join(str(v or "").split())


class TheoryConcept(BaseModel):
    """0.18.4 (K2 part 2): one concept of a theory document, as the AI drafts it (theory-codes-v2)."""
    name: str = Field(min_length=2, max_length=60)
    definition: QuoteRef
    reason: str = Field(default="", max_length=300)

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v):
        v = " ".join(str(v or "").split()).strip(" .\"'")
        if len(v.split()) > 6:
            raise ValueError("the name must have at most six words")
        return v

    @field_validator("reason", mode="before")
    @classmethod
    def _reason(cls, v):
        return " ".join(str(v or "").split())[:300]


class TheoryCodesOut(BaseModel):
    concepts: list[TheoryConcept] = Field(default_factory=list, max_length=40)
    note: Optional[str] = None


class FrameConcept(BaseModel):
    """One concept of the framework put together from a theory's drafted concepts (theory-frame-v1). `from` names the
    drafts it joins (by their numbers); `from_` in Python, as `from` is a reserved word."""
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=2, max_length=60)
    from_: list[int] = Field(alias="from", min_length=1)
    meaning: str = Field(min_length=10, max_length=600)
    when_to_use: str = Field(min_length=10, max_length=500)
    not_when: Optional[str] = Field(default=None, max_length=400)
    words: list[str] = Field(min_length=3, max_length=12)
    core: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v):
        v = " ".join(str(v or "").split()).strip(" .\"'")
        if len(v.split()) > 6:
            raise ValueError("the name must have at most six words")
        return v

    @field_validator("from_", mode="before")
    @classmethod
    def _nums(cls, v):
        if isinstance(v, (int, str)):
            v = [v]
        out = []
        for x in v or []:
            if isinstance(x, str) and x.strip().isdigit():
                x = int(x.strip())
            if isinstance(x, bool) or not isinstance(x, int) or x < 1:
                raise ValueError(f"`from` holds the numbers of drafts (1 or more), not {x!r}")
            out.append(x)
        return out

    @field_validator("meaning", "when_to_use", mode="before")
    @classmethod
    def _flat(cls, v):
        return " ".join(str(v or "").split())

    @field_validator("not_when", mode="before")
    @classmethod
    def _none(cls, v):
        v = " ".join(str(v or "").split())
        return None if v.lower().strip(" .") in ("", "none", "null", "n/a") else v

    @field_validator("words", mode="before")
    @classmethod
    def _words(cls, v):
        out = []
        for w in v or []:
            w = " ".join(str(w or "").split())
            if len(w) > 60:
                raise ValueError(f"a word or phrase of at most 60 characters, not {w[:60]!r}…")
            if w and w.lower() not in [x.lower() for x in out]:
                out.append(w)
        return out


class FrameGroup(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    about: str = Field(default="", max_length=200)
    concepts: list[FrameConcept] = Field(min_length=1)

    @field_validator("name", "about", mode="before")
    @classmethod
    def _flat(cls, v):
        return " ".join(str(v or "").split())


MAX_FRAME_CONCEPTS = 30


class TheoryFrameOut(BaseModel):
    """The framework of a codebook from theory documents (theory-frame-v1, theoryframe.py): groups of concepts, each
    concept joining drafts of one or more documents."""
    groups: list[FrameGroup] = Field(min_length=1, max_length=6)
    note: Optional[str] = None

    @field_validator("groups")
    @classmethod
    def _at_most(cls, v):
        n = sum(len(g.concepts) for g in v)
        if n > MAX_FRAME_CONCEPTS:
            raise ValueError(f"at most {MAX_FRAME_CONCEPTS} concepts in all, not {n}: join or leave out the least "
                             "central")
        return v


class CodeDefinitionOut(BaseModel):
    """K1 (the optional AI part): a code's definition, when to use it and when not, drafted from its examples
    (code-definition-v1). The definition and when to use it each name a quote that shows them."""
    definition: str = Field(min_length=10, max_length=600)
    definition_quote: QuoteRef
    when_to_use: str = Field(min_length=5, max_length=400)
    when_to_use_quote: QuoteRef
    when_not_to_use: str = Field(default="", max_length=400)
    note: Optional[str] = None

    @field_validator("definition", "when_to_use", "when_not_to_use", mode="before")
    @classmethod
    def _flat(cls, v):
        return " ".join(str(v or "").split())


class GroupNameOut(BaseModel):
    """D1 rest (the optional AI part): a short name for a group of concepts on the concept map, drafted from passages
    where its concepts are mentioned together (group-name-v1), with a quote that shows it."""
    name: str = Field(min_length=3, max_length=60)
    name_quote: QuoteRef
    note: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def _flat(cls, v):
        return " ".join(str(v or "").split())

    @field_validator("name")
    @classmethod
    def _six_words(cls, v):
        if len(v.split()) > 6:
            raise ValueError("the name has more than six words: give at most six words")
        return v


class Mention(BaseModel):
    passage: int = Field(ge=1)
    span: str = Field(min_length=3, max_length=300)
    mention: str = Field(min_length=1, max_length=200)
    named: bool = False

    @field_validator("passage", mode="before")
    @classmethod
    def _num(cls, v):
        if isinstance(v, str):
            v = v.strip().upper().lstrip("P")
        return v


class Chain(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mentions: list[Mention] = Field(min_length=1)


class ResolveOut(BaseModel):
    chains: list[Chain] = Field(default_factory=list)


# ---------------------------------------------------------------------------------------------
# JSON schemas for constrained decoding (Ollama's `format`); validation still runs on every answer
# ---------------------------------------------------------------------------------------------
def _inline(schema: dict) -> dict:
    """Resolve $ref/$defs so the schema is one self-contained tree, and drop titles and descriptions.

    The names under "properties" are the answer's own fields and are always kept: a field called "description" (a
    theme's) is not a schema's description. Until 0.19.6 it was dropped with them, so a constrained decoder (Ollama's
    `format`, an OpenAI-compatible server's json_schema) could not write it, and every local answer to a theme was
    rejected for leaving it out."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: ({name: walk(sub) for name, sub in v.items()} if k == "properties" and isinstance(v, dict)
                        else walk(v))
                    for k, v in node.items() if k not in ("$defs", "title", "description", "default")}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node
    return walk(schema)


def _require_all(node):
    """Ask for every property: constrained decoders then always write the key (null where allowed)."""
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            node["required"] = list(node["properties"])
        for v in node.values():
            _require_all(v)
    elif isinstance(node, list):
        for v in node:
            _require_all(v)
    return node


EXPAND_MAX_TERMS = 20   # I6: the prompt says "at most 20"; the grammar now holds a small model to it
EXPAND_MAX_CHARS = 60


def output_schema(kind: str, payload: dict | None = None) -> dict:
    """The JSON schema a model's answer for this task kind must follow. I6: `payload` bounds the `point` form's answer
    by the task (its number of excerpts and sentences; pointing.schema)."""
    from .taxonomy import targets

    if kind == "point":
        from .pointing import schema

        return schema(payload)
    if kind == "extract":
        claim = _inline(ImpactClaimOut.model_json_schema())
        claim["properties"]["targets"]["items"]["properties"]["target"] = {"type": "string", "enum": sorted(targets())}
        inter = _inline(InteractionOut.model_json_schema())
        for k in ("from_target", "to_target"):
            inter["properties"][k] = {"type": "string", "enum": sorted(targets())}
        s = {"type": "object", "properties": {"claims": {"type": "array", "items": claim},
                                              "interactions": {"type": "array", "items": inter},
                                              "note": {"anyOf": [{"type": "string"}, {"type": "null"}]}}}
    elif kind == "split":
        s = _inline(SplitOut.model_json_schema())
    elif kind == "verify":
        s = _inline(VerifyOut.model_json_schema())
    elif kind == "verify_set":
        s = _inline(VerifySetOut.model_json_schema())
    elif kind in ("check", "reread", "second"):
        s = _inline(CheckOut.model_json_schema())
    elif kind == "expand":
        s = _inline(ExpandOut.model_json_schema())
        # I6: bounded, so a small model cannot add search words until the length limit cuts it off (llama.cpp's grammar
        # honours both; whether Ollama's MLX runner does is not checked yet: roadmap I6, "Left to try")
        s["properties"]["terms"]["maxItems"] = EXPAND_MAX_TERMS
        s["properties"]["terms"]["items"] = {**s["properties"]["terms"].get("items", {}), "type": "string",
                                             "maxLength": EXPAND_MAX_CHARS}
    elif kind == "decompose":
        s = _inline(DecomposeOut.model_json_schema())
    elif kind == "label":
        s = _inline(LabelOut.model_json_schema())
    elif kind == "link":
        s = _inline(LinkOut.model_json_schema())
    elif kind == "theme":
        s = _inline(ThemeOut.model_json_schema())
    elif kind == "resolve":
        s = _inline(ResolveOut.model_json_schema())
    elif kind == "theory_codes":
        s = _inline(TheoryCodesOut.model_json_schema())
    elif kind == "code_definition":
        s = _inline(CodeDefinitionOut.model_json_schema())
    elif kind == "group_name":
        s = _inline(GroupNameOut.model_json_schema())
    elif kind == "theory_frame":
        s = _inline(TheoryFrameOut.model_json_schema(by_alias=True))
    else:
        raise ValueError(f"no output schema for task kind {kind!r}")
    return _require_all(s)
