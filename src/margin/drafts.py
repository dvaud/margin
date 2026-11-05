"""Check a draft (Margin 0.1): the statements of the researcher's own writing that need a source, and the documents
of the project that support or contradict each.

A draft is the researcher's own text (pasted, or read from a Word, PDF, text or web file). It is kept apart from the
documents: it is never searched as evidence. Checking it has two steps:

1. **Find the claims.** The draft is cut into parts of a few paragraphs, and the AI lists in each the statements a
   reader would want a source for (numbers, causes and effects, comparisons, what earlier research found, general
   claims about the world), each with the exact sentence it quotes (checked against the draft like every quote), the
   claim restated as one self-contained sentence, and whether the draft already cites a source there. Without AI
   (a draft marked *No AI*, or no model that may read it) rules find the likely ones instead. The person keeps,
   drops, rewords or adds claims (by selecting a sentence).
2. **Check them.** Each claim kept is checked against the documents as a hypothesis of its own (claimcheck), in one
   set per draft, so every result, review, export and the evidence map work as for any other check.
3. **Check its citations** (with ENLENS 0.13.7's Check citations, citations.py). The draft's own citations, "(Smith,
   2020)", "Smith et al. (2020) found that …", "[3]" with a numbered reference list, are found without AI when the
   draft is added; each cited work of the bibliography whose document is in the project is checked against that
   document only: does the source say what the sentence says? The claims of step 1 that carry a citation show its
   answer, so a cited claim says both what the documents say and whether its own source says it.

The draft has an AI setting of its own, as a document has (access.py): the tasks that hold its text, the finding of
its claims and every task of their checks and of its citations' checks, keep it, and each time a cloud model reads
part of it is recorded.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from . import access, bibliography, citations, claimcheck, taskkinds, tasks
from .schema import ClaimsOut
from .store import Workspace, now
from .textutil import find_quote, normalise, split_sentences

MAX_CHARS = 300_000   # about 50,000 words: a thesis chapter, a long report
PART_CHARS = 4000     # the most text one task holds (a few paragraphs)
CONTEXT_CHARS = 400   # the end of the part before, to say what "it" and "this" are (not quotable)
MAX_PER_PART = 25
READ_KINDS = (".pdf", ".docx", ".txt", ".md", ".html", ".htm")

KIND_TEXT = {"statistic": "A number or share", "causal": "A cause or effect", "comparison": "A comparison",
             "prior_research": "What research found", "generalisation": "A general claim",
             "definition": "A definition or history", "other": "A claim"}
SOURCE_TEXT = {"ai": "the AI", "rules": "rules (no AI)", "person": "you"}
# Margin 0.3: the person's own decision on a claim, made on the draft page. "dismissed" is a claim that needs no
# source (skip=1: it is not checked); "supported" and "refuted" say a source should be cited there. A decision
# belongs to the draft: it never changes the answer of the claim's check.
DECISIONS = ("supported", "refuted", "dismissed")
DECISION_TEXT = {"supported": "supported", "refuted": "refuted", "dismissed": "dismissed"}
_KEEP = object()

Progress = Callable[..., None]


def _id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:12]


def _clean_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ").replace("\f", "\n\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


# ---------------------------------------------------------------------------------------------
# drafts
# ---------------------------------------------------------------------------------------------
def new_draft(ws: Workspace, text: str, title: str | None = None, file_name: str | None = None,
              ai_access: str | None = None) -> str:
    """Keep a draft; returns its id. `ai_access` (cloud, local, none; None: the project's default)."""
    text = _clean_text(text)
    if len(text) < 40:
        raise ValueError("The draft is too short: paste at least a few sentences.")
    if len(text) > MAX_CHARS:
        raise ValueError(f"The draft is too long ({len(text):,} characters). Check it a chapter or a section at a time "
                         f"(at most {MAX_CHARS:,} characters).")
    lv = access.clean(ai_access, allow_empty=True)
    if lv == "cloud" and access._local_only():
        raise ValueError("Cloud models are switched off on this computer: choose Only a local AI or No AI.")
    title = " ".join((title or "").split())[:200] or _guess_title(text)
    did = _id("d")
    with ws.connect() as cx:
        cx.execute("INSERT INTO drafts(draft_id, title, text, file_name, ai_access, batch_id, created_at, updated_at) "
                   "VALUES (?,?,?,?,?,?,?,?)", (did, title, text, file_name, lv, "b" + did, now(), now()))
    try:
        citation_text(ws, did)  # its citations, found at once (no AI)
    except Exception:  # noqa: BLE001 - never lose a draft over its citations: they are looked for again on its page
        pass
    return did


def _guess_title(text: str) -> str:
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    first = " ".join(first.split())
    return (first[:80] + "…") if len(first) > 80 else (first or "Untitled draft")


def read_file(path: Path) -> tuple[str, str | None]:
    """The text and title of a draft file (Word, PDF, text, Markdown, web page), as Margin reads documents."""
    from .ingest import assemble, read_file as read_raw

    if path.suffix.lower() not in READ_KINDS:
        raise ValueError("Give the draft as a Word file (.docx), a PDF, a text or Markdown file, or a web page.")
    raw = read_raw(path)
    text, _spans = assemble(raw.pages)
    return text, raw.meta_title


def _row(ws: Workspace, draft_id: str) -> dict:
    rows = ws.query("SELECT * FROM drafts WHERE draft_id=?", (draft_id,))
    if not rows:
        raise KeyError(draft_id)
    return dict(rows[0])


def level(ws: Workspace, draft_id: str) -> str:
    return access.draft_levels(ws, [draft_id])[draft_id]


def update(ws: Workspace, draft_id: str, title: str | None = None, ai_access: Any = None) -> dict:
    """Rename a draft, or change its AI setting (`ai_access`: cloud, local, none, or "" for the project's default).
    The tasks not answered yet that hold its text take the new setting at once."""
    _row(ws, draft_id)
    with ws.connect() as cx:
        if title is not None:
            t = " ".join(str(title).split())[:200]
            if not t:
                raise ValueError("Give the draft a title.")
            cx.execute("UPDATE drafts SET title=?, updated_at=? WHERE draft_id=?", (t, now(), draft_id))
        if ai_access is not None:
            lv = access.clean(ai_access, allow_empty=True)
            if lv == "cloud" and access._local_only():
                raise ValueError("Cloud models are switched off on this computer: choose Only a local AI or No AI.")
            cx.execute("UPDATE drafts SET ai_access=?, updated_at=? WHERE draft_id=?", (lv, now(), draft_id))
        _mirror(cx, draft_id)  # its citations' text keeps the same name and setting
        if ai_access is not None:
            access.relabel(cx)
    return summary(ws, draft_id)


def delete(ws: Workspace, draft_id: str) -> dict:
    """Remove a draft, its claims, its citations and their checks. What Claude read of it stays in the record
    (`draft_sent`)."""
    tid = _row(ws, draft_id).get("cite_text_id")
    if tid and ws.scalar("SELECT 1 FROM cite_texts WHERE text_id=?", (tid,)):
        citations.remove_text(ws, tid)
    hyps = [r[0] for r in ws.query("SELECT hyp_id FROM hypotheses WHERE draft_id=?", (draft_id,))]
    for hid in hyps:
        claimcheck.delete_hypothesis(ws, hid)
    with ws.connect() as cx:
        for tbl in ("results", "tasks"):
            cx.execute(f"DELETE FROM {tbl} WHERE task_id LIKE ?", (f"claims:{draft_id}:%",))
        n = cx.execute("DELETE FROM draft_claims WHERE draft_id=?", (draft_id,)).rowcount
        cx.execute("DELETE FROM drafts WHERE draft_id=?", (draft_id,))
    return {"deleted": draft_id, "claims": n, "checks": len(hyps)}


def list_drafts(ws: Workspace) -> list[dict]:
    counts = {r[0]: (r[1], r[2], r[3]) for r in ws.query(
        "SELECT draft_id, COUNT(*), SUM(CASE WHEN skip=0 THEN 1 ELSE 0 END), SUM(CASE WHEN hyp_id IS NOT NULL THEN 1 "
        "ELSE 0 END) FROM draft_claims GROUP BY draft_id")}
    lv = access.draft_levels(ws)
    cites = {r[0]: r[1] for r in ws.query("SELECT text_id, COUNT(*) FROM cite_refs WHERE ignored=0 GROUP BY text_id")}
    out = []
    for r in ws.query("SELECT draft_id, title, file_name, ai_access, created_at, found_at, cite_text_id, "
                      "LENGTH(text) AS chars FROM drafts ORDER BY created_at DESC, rowid DESC"):
        n, kept, checked = counts.get(r["draft_id"], (0, 0, 0))
        out.append({"draft_id": r["draft_id"], "title": r["title"], "file_name": r["file_name"],
                    "created_at": r["created_at"], "found_at": r["found_at"], "chars": r["chars"],
                    "ai_access": lv.get(r["draft_id"], "none"), "own_setting": r["ai_access"] is not None,
                    "claims": n or 0, "kept": kept or 0, "checked": checked or 0,
                    "cite_text_id": r["cite_text_id"] or None, "citations": cites.get(r["cite_text_id"], 0)})
    return out


def summary(ws: Workspace, draft_id: str) -> dict:
    return next(d for d in list_drafts(ws) if d["draft_id"] == draft_id)


# ---------------------------------------------------------------------------------------------
# step 1: the claims that need a source
# ---------------------------------------------------------------------------------------------
def parts(text: str, size: int = PART_CHARS) -> list[tuple[int, int]]:
    """The draft cut into parts of whole paragraphs (a paragraph longer than `size` at sentence ends)."""
    paras = []
    for m in re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", text):
        a, b = m.start(), m.end()
        if b - a <= size:
            paras.append((a, b))
            continue
        cur = a
        for s, e in split_sentences(text[a:b], a):
            if e - cur > size and s > cur:
                paras.append((cur, s))
                cur = s
        paras.append((cur, b))
    out: list[tuple[int, int]] = []
    for a, b in paras:
        if out and b - out[-1][0] <= size:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def _task_ids(ws: Workspace, draft_id: str) -> list[str]:
    return [r[0] for r in ws.query("SELECT task_id FROM tasks WHERE kind='claims' AND task_id LIKE ? ORDER BY created_at, "
                                   "rowid", (f"claims:{draft_id}:%",))]


def _forget_found(cx, draft_id: str) -> None:
    """Before finding again: the claims nobody touched go (a claim checked, reworded, decided on, dismissed or added
    stays), and so do the earlier tasks."""
    cx.execute("DELETE FROM draft_claims WHERE draft_id=? AND hyp_id IS NULL AND edited=0 AND skip=0 AND decision IS "
               "NULL AND source != 'person'", (draft_id,))
    for tbl in ("results", "tasks"):
        cx.execute(f"DELETE FROM {tbl} WHERE task_id LIKE ?", (f"claims:{draft_id}:%",))


def plan(ws: Workspace, draft_id: str, model: str) -> list[str]:
    """The tasks that find the claims of a draft, one per part (made anew)."""
    d = _row(ws, draft_id)
    text = d["text"]
    spans = parts(text)
    ids = []
    with ws.connect() as cx:
        _forget_found(cx, draft_id)
        for n, (a, b) in enumerate(spans, 1):
            payload = {"draft_id": draft_id, "title": d["title"], "part": n, "parts": len(spans), "start": a,
                       "text": text[a:b]}
            ctx = text[max(0, a - CONTEXT_CHARS):a].strip()
            if ctx:
                payload["context"] = ctx
            tid = f"claims:{draft_id}:{n}"
            tasks._insert_task(cx, tid, "claims", model, payload)
            ids.append(tid)
    return ids


def find_claims(ws: Workspace, draft_id: str, backend, model: str, progress: Progress | None = None,
                should_stop: Callable[[], bool] | None = None, readers=None) -> dict:
    """Find the claims of a draft now: with the model that may read it, or by rules when none may (No AI, or Only a
    local AI without a local model). Backend errors propagate; what was found before stays."""
    say = claimcheck._adapt(progress)
    lv = level(ws, draft_id)
    readers = readers if readers is not None else access.Readers(backend, model)
    reader = None
    if lv != "none" and backend is not None and getattr(backend, "name", "") != "baseline":
        reader = readers.for_level(lv)  # the offline demo cannot read: rules, said as such
    if reader is None:
        note = ("This draft is marked No AI: the claims were found by rules, without AI." if lv == "none" else
                "No AI model is set up, so the claims were found by rules, without AI." if backend is None or
                getattr(backend, "name", "") == "baseline" else
                "No local model is chosen for drafts marked Only a local AI, so the claims were found by rules, "
                "without AI. Choose one in Settings → AI to let it read the draft.")
        say("rank", "Looking for claims by rules (no AI)", {})
        n = find_by_rules(ws, draft_id)
        say("rank_done", f"Found {n} {'claim' if n == 1 else 'claims'} by rules", {"claims": n})
        return {"draft_id": draft_id, "by": "rules", "found": n, "failed": 0, "note": note}
    be, m = reader
    ids = plan(ws, draft_id, claimcheck._used(be, m))
    failed = 0
    for i, tid in enumerate(ids, 1):
        if should_stop and should_stop():
            break
        say("grade", f"Reading part {i} of {len(ids)} of your draft", {"index": i, "total": len(ids)})
        ok, _errs = tasks.run_one(ws, tid, be, m)
        failed += not ok
    with ws.connect() as cx:
        cx.execute("UPDATE drafts SET found_by=?, found_at=? WHERE draft_id=?", ("ai", now(), draft_id))
    n = int(ws.scalar("SELECT COUNT(*) FROM draft_claims WHERE draft_id=?", (draft_id,)) or 0)
    say("grade_done", f"Found {n} {'claim' if n == 1 else 'claims'} that may need a source"
        + (f"; {failed} {'part' if failed == 1 else 'parts'} could not be read" if failed else ""), {"claims": n})
    return {"draft_id": draft_id, "by": "ai", "found": n, "failed": failed, "parts": len(ids), "note": None}


def queue_find(ws: Workspace, draft_id: str, router=None) -> list[str]:
    """Find the claims through the queue (Claude Code answers). A draft Claude may not read is read here instead
    (the caller runs `find_claims`)."""
    model = (router.model("claims") if router is not None else None) or "sonnet"
    with tasks.queueing():
        return plan(ws, draft_id, model)


def finding(ws: Workspace, draft_id: str) -> dict:
    """Where the finding of the claims stands: its parts waiting, done and failed, and the latest problems."""
    rows = ws.query("SELECT task_id, status, queued, access FROM tasks WHERE kind='claims' AND task_id LIKE ?",
                    (f"claims:{draft_id}:%",))
    waiting = [r for r in rows if r["status"] in ("pending", "retry")]
    failed = [r for r in rows if r["status"] == "failed"]
    out = {"total": len(rows), "waiting": len(waiting), "failed": len(failed),
           "done": sum(1 for r in rows if r["status"] == "done"),
           "queued": sum(1 for r in waiting if r["queued"])}
    if failed:
        err = ws.query("SELECT errors_json FROM results WHERE task_id=? ORDER BY attempt DESC LIMIT 1",
                       (failed[0]["task_id"],))
        out["errors"] = (json.loads(err[0][0]) if err else [])[:5]
    return out


def store_claims(cx, t, payload: dict, obj: Any, model: str) -> tuple[bool, list[str]]:
    """The answer of a `claims` task: every quote must be in the part of the draft it was given (the usual quote
    check); the claims are kept with their place in the draft."""
    out = ClaimsOut.model_validate(obj)
    text, base, did = payload["text"], int(payload["start"]), payload["draft_id"]
    if not cx.execute("SELECT 1 FROM drafts WHERE draft_id=?", (did,)).fetchone():
        return True, []  # the draft was removed meanwhile: nothing to keep
    errors, found = [], []
    for i, c in enumerate(out.claims):
        hit = find_quote(text, c.quote)
        if hit is None:
            errors.append(f"claims.{i}.quote: not found in the passage. Copy the sentence character for character, "
                          "or quote a shorter contiguous piece of it.")
            continue
        found.append((base + hit[0], base + hit[1], c))
    if errors:
        return False, errors
    with_draft = cx.execute("SELECT text FROM drafts WHERE draft_id=?", (did,)).fetchone()[0]
    cx.execute("DELETE FROM draft_claims WHERE task_id=? AND hyp_id IS NULL AND edited=0 AND skip=0 AND decision IS "
               "NULL", (t["task_id"],))
    kept = [(r[0], r[1]) for r in cx.execute("SELECT start, end FROM draft_claims WHERE draft_id=?", (did,))]
    for a, b, c in found:
        if any(_overlap((a, b), k) > 0.5 for k in kept):
            continue  # the same sentence again (or one a person kept or marked)
        kept.append((a, b))
        _insert(cx, did, a, b, with_draft[a:b], " ".join(c.claim.split()), c.kind, c.why, c.cited, "ai", model,
                t["task_id"])
    cx.execute("UPDATE drafts SET found_by='ai', found_at=? WHERE draft_id=?", (now(), did))
    return True, []


def _overlap(x: tuple[int, int], y: tuple[int, int]) -> float:
    inter = min(x[1], y[1]) - max(x[0], y[0])
    return inter / min(x[1] - x[0], y[1] - y[0]) if inter > 0 else 0.0


def _insert(cx, did: str, a: int, b: int, quote: str, claim: str, kind: str, why: str | None, cited: bool,
            source: str, model: str | None, task_id: str | None, edited: int = 0) -> str:
    cid = "dc" + tasks._h(did, str(a), str(b), source)
    cx.execute("INSERT OR REPLACE INTO draft_claims(claim_id, draft_id, start, end, quote, claim, kind, why, cited, "
               "source, model, task_id, skip, edited, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)",
               (cid, did, a, b, quote, claim, kind, why, int(bool(cited)), source, model, task_id, edited, now()))
    return cid


# ---------------------------------------------------------------------------------------------
# without AI: rules for the sentences that most often need a source
# ---------------------------------------------------------------------------------------------
_CITATION = re.compile(
    r"\((?:see |e\.g\.,? |cf\.? )?[A-Z][\w'’\-]+(?: et al\.?| (?:and|&) [A-Z][\w'’\-]+)?,? (?:19|20)\d{2}[a-z]?"
    r"(?:[,;][^)]{0,120})?\)|\[\d+(?:\s?[-–,]\s?\d+)*\]|\b[A-Z][\w'’\-]+(?: et al\.?)? \((?:19|20)\d{2}[a-z]?\)")
_RULES = (
    ("prior_research", re.compile(
        r"\b(?:stud(?:y|ies)|research(?:ers)?|evidence|literature|scholars|surveys?|experiments?|trials?|"
        r"meta-analys[ie]s|reviews?|data|reports?)\b[^.;]{0,60}?\b(?:show(?:s|ed|n)?|suggest(?:s|ed)?|f(?:ou|i)nds?|"
        r"found|indicate(?:s|d)?|demonstrate(?:s|d)?|report(?:s|ed)?|confirm(?:s|ed)?|reveal(?:s|ed)?|"
        r"point(?:s|ed)? to)\b|\baccording to\b|\bit (?:is|has been) (?:well[- ])?(?:known|established|"
        r"documented|shown|argued|reported|estimated)\b", re.I)),
    ("statistic", re.compile(
        r"\b\d+(?:[.,]\d+)*\b|\b(?:million|billion|trillion|thousands?|hundreds?|half|a third|a quarter|two-thirds|"
        r"twice|doubled|tripled|halved|per ?cent|percent)\b", re.I)),
    ("causal", re.compile(
        r"\b(?:caus(?:e|es|ed|ing)|lead(?:s)? to|led to|leading to|result(?:s|ed)? in|due to|because of|"
        r"contribut(?:e|es|ed|ing) to|driv(?:e|es|en|ing)|increas(?:e|es|ed|ing)|decreas(?:e|es|ed|ing)|"
        r"reduc(?:e|es|ed|ing)|improv(?:e|es|ed|ing)|lower(?:s|ed)?|rais(?:e|es|ed|ing)|affect(?:s|ed)?|"
        r"impact(?:s|ed)?|associated with|linked to|correlat\w* with|depends? on|prevent(?:s|ed)?|"
        r"enabl(?:e|es|ed)|undermin(?:e|es|ed))\b", re.I)),
    ("comparison", re.compile(
        r"\b(?:more|less|fewer|higher|lower|greater|larger|smaller|better|worse|faster|slower|cheaper) than\b|"
        r"\b(?:the )?(?:most|least|largest|smallest|highest|lowest|fastest|biggest|main|leading|majority|"
        r"minority)\b", re.I)),
    ("generalisation", re.compile(
        r"\b(?:widely|commonly|generally|typically|usually|increasingly|traditionally|universally|rarely|"
        r"well[- ]known|well[- ]established|consensus|it is (?:clear|accepted|recognised|recognized))\b", re.I)),
)
_REFS = re.compile(r"\b(?:table|figure|fig\.|section|chapter|eq\.?|equation|appendix|page|p\.|pp\.)\s?\d+[a-z]?\b", re.I)
_WHY = {"prior_research": "Reports what earlier research found", "statistic": "Gives a number, amount or share",
        "causal": "States a cause or an effect", "comparison": "Compares or ranks",
        "generalisation": "Generalises about the world or a field"}
_OWN = re.compile(r"^(?:we|our|us|i|my|here(?:,)? we|this (?:paper|article|study|chapter|thesis|report|section|work|"
                  r"essay)|in this (?:paper|article|study|chapter|thesis|report|section|work|essay)|the (?:aim|purpose|"
                  r"goal|objective) of this|section \d|chapter \d|table \d|figure \d|fig\. \d|first(?:ly)?,? we|"
                  r"next,? we|finally,? we)\b", re.I)


def rule_claims(text: str) -> list[dict]:
    """The sentences of a text that most often need a source, by rules (no AI): numbers and shares, causes and
    effects, comparisons, what research found, general claims. Not the author's own aims, methods or results, not
    questions or headings. In the format of the `claims` task, so the same check applies."""
    out = []
    spans = [sp for m in re.finditer(r"[^\n]+", text) for sp in split_sentences(m.group(0), m.start())]
    for a, b in spans:
        s = text[a:b].strip()
        flat = " ".join(s.split())
        if len(flat) < 30 or len(flat) > 1200 or flat.endswith("?") or not re.search(r"[.!:;)\]]$", flat):
            continue  # too short, a question, or a heading
        if _OWN.search(flat):
            continue  # the author's own aims, methods or results
        bare = _CITATION.sub("", flat)
        kind = next((k for k, rx in _RULES if rx.search(_REFS.sub("", bare))), None)
        if kind is None:
            continue
        claim = " ".join(bare.split()).replace(" .", ".").replace(" ,", ",")
        if len(claim) < 10:
            continue
        out.append({"quote": s, "claim": claim[:500], "kind": kind, "cited": bool(_CITATION.search(flat)),
                    "why": _WHY[kind]})
        if len(out) >= MAX_PER_PART * 4:
            break
    return out


def find_by_rules(ws: Workspace, draft_id: str) -> int:
    d = _row(ws, draft_id)
    with ws.connect() as cx:
        _forget_found(cx, draft_id)
        kept = [(r[0], r[1]) for r in cx.execute("SELECT start, end FROM draft_claims WHERE draft_id=?", (draft_id,))]
        for a, b in parts(d["text"]):
            for c in rule_claims(d["text"][a:b]):
                hit = find_quote(d["text"][a:b], c["quote"])
                if hit is None:
                    continue
                s, e = a + hit[0], a + hit[1]
                if any(_overlap((s, e), k) > 0.5 for k in kept):
                    continue
                kept.append((s, e))
                _insert(cx, draft_id, s, e, d["text"][s:e], c["claim"], c["kind"], c["why"], c["cited"], "rules", None,
                        None)
        cx.execute("UPDATE drafts SET found_by='rules', found_at=? WHERE draft_id=?", (now(), draft_id))
    return int(ws.scalar("SELECT COUNT(*) FROM draft_claims WHERE draft_id=?", (draft_id,)) or 0)


# ---------------------------------------------------------------------------------------------
# the person's changes
# ---------------------------------------------------------------------------------------------
def add_claim(ws: Workspace, draft_id: str, start: int, end: int, claim: str | None = None) -> str:
    """A claim a person marks in the draft (a sentence or part of one)."""
    text = _row(ws, draft_id)["text"]
    start, end = int(start), int(end)
    if not (0 <= start < end <= len(text)):
        raise ValueError("Select a sentence of the draft.")
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    quote = text[start:end]
    if len(quote.strip()) < 10:
        raise ValueError("Select at least a few words (10 characters).")
    if end - start > 1500:
        raise ValueError("Select one sentence or two at most.")
    c = " ".join((claim or quote).split())
    claimcheck._clean(c)
    with ws.connect() as cx:
        return _insert(cx, draft_id, start, end, quote, c, "other", "Marked by you",
                       bool(_CITATION.search(quote)), "person", None, None, edited=1)


def update_claim(ws: Workspace, draft_id: str, claim_id: str, claim: str | None = None,
                 skip: bool | None = None, decision: Any = _KEEP) -> dict:
    """Reword a claim (before it is checked), drop or keep it (`skip`), or record the person's decision on it
    (`decision`: 'supported', 'refuted', 'dismissed', or None to take it back). Dismissing is dropping: both set
    skip, and keeping a dismissed claim takes the decision back."""
    rows = ws.query("SELECT * FROM draft_claims WHERE claim_id=? AND draft_id=?", (claim_id, draft_id))
    if not rows:
        raise KeyError(claim_id)
    if decision is not _KEEP and decision is not None and decision not in DECISIONS:
        raise ValueError("A decision is 'supported', 'refuted' or 'dismissed'.")
    if skip is not None and decision is _KEEP:
        decision = "dismissed" if skip else (None if rows[0]["decision"] in (None, "dismissed") else rows[0]["decision"])
    with ws.connect() as cx:
        if claim is not None:
            if rows[0]["hyp_id"]:
                raise ValueError("This claim was checked already. Mark the sentence again to check new wording.")
            c = claimcheck._clean(claim)
            cx.execute("UPDATE draft_claims SET claim=?, edited=1 WHERE claim_id=?", (c, claim_id))
        if decision is not _KEEP:
            cx.execute("UPDATE draft_claims SET decision=?, decided_at=?, skip=? WHERE claim_id=?",
                       (decision, now() if decision else None, int(decision == "dismissed"), claim_id))
    return dict(ws.query("SELECT * FROM draft_claims WHERE claim_id=?", (claim_id,))[0])


def remove_claim(ws: Workspace, draft_id: str, claim_id: str) -> None:
    rows = ws.query("SELECT hyp_id FROM draft_claims WHERE claim_id=? AND draft_id=?", (claim_id, draft_id))
    if not rows:
        raise KeyError(claim_id)
    if rows[0]["hyp_id"]:
        claimcheck.delete_hypothesis(ws, rows[0]["hyp_id"])
    with ws.connect() as cx:
        cx.execute("DELETE FROM draft_claims WHERE claim_id=?", (claim_id,))


# ---------------------------------------------------------------------------------------------
# step 2: check the claims against the documents
# ---------------------------------------------------------------------------------------------
def to_check(ws: Workspace, draft_id: str, claim_ids: list[str] | None = None) -> list[dict]:
    """The claims kept and not checked yet (or these of them), in the order of the draft. A claim the person has
    already decided on is checked only when asked for by its id."""
    rows = [dict(r) for r in ws.query("SELECT * FROM draft_claims WHERE draft_id=? AND skip=0 AND hyp_id IS NULL "
                                      "ORDER BY start", (draft_id,))]
    if claim_ids is None:
        rows = [r for r in rows if not r["decision"]]
    else:
        want = set(claim_ids)
        rows = [r for r in rows if r["claim_id"] in want]
    return rows


def check_options(ws: Workspace, draft_id: str, opts: dict, backend) -> dict:
    """The options of the checks of a draft's claims: one claim each (no splitting); the search words come from the
    AI only when the model that reads the draft may (a draft kept from it is searched with its own words)."""
    out = dict(opts)
    out["decompose"] = False
    if level(ws, draft_id) not in access.backend_levels(backend):
        out["expand"] = False
    return out


def link(ws: Workspace, claim_id: str, hyp_id: str) -> None:
    with ws.connect() as cx:
        cx.execute("UPDATE draft_claims SET hyp_id=? WHERE claim_id=?", (hyp_id, claim_id))


def check_claims(ws: Workspace, draft_id: str, backend, model: str, claim_ids: list[str] | None = None,
                 progress: Progress | None = None, should_stop: Callable[[], bool] | None = None,
                 **options: Any) -> dict:
    """Check the claims kept, one after the other, each as a hypothesis in the draft's set. A problem with one is
    recorded and the next is checked; a problem with the model service stops (what was done is kept)."""
    from .llm import BackendError

    say = claimcheck._adapt(progress)
    d = _row(ws, draft_id)
    todo = to_check(ws, draft_id, claim_ids)
    opts = check_options(ws, draft_id, options, backend)
    done, errors, stopped = [], [], None
    for i, c in enumerate(todo, 1):
        if should_stop and should_stop():
            stopped = "Stopped."
            break
        say("item", f"Claim {i} of {len(todo)}", {"index": i, "total": len(todo), "text": c["claim"]})
        try:
            hid = claimcheck.check_hypothesis(ws, c["claim"], backend, model, batch_id=d["batch_id"], draft_id=draft_id,
                                              progress=lambda s, m, info=None, _i=i: say(s, m, {**(info or {}),
                                                                                               "index": _i}),
                                              should_stop=should_stop, **opts)
            link(ws, c["claim_id"], hid)
            done.append(hid)
        except BackendError as e:
            stopped = str(e)
            break
        except ValueError as e:
            errors.append({"index": i, "text": c["claim"], "error": str(e)})
    return {"draft_id": draft_id, "batch_id": d["batch_id"], "checked": done, "errors": errors, "stopped": stopped,
            "total": len(todo)}


def queue_checks(ws: Workspace, draft_id: str, router, claim_ids: list[str] | None = None,
                 **options: Any) -> dict:
    """Prepare the checks of the claims kept for Claude Code (the queue); returns their hypothesis ids."""
    d = _row(ws, draft_id)
    opts = dict(options)
    opts["decompose"] = False
    if level(ws, draft_id) != "cloud":
        opts["expand"] = False
    done, errors = [], []
    for i, c in enumerate(to_check(ws, draft_id, claim_ids), 1):
        try:
            hid = claimcheck.queue_check(ws, c["claim"], router, batch_id=d["batch_id"], draft_id=draft_id, **opts)
            link(ws, c["claim_id"], hid)
            done.append(hid)
        except ValueError as e:
            errors.append({"index": i, "text": c["claim"], "error": str(e)})
    return {"draft_id": draft_id, "batch_id": d["batch_id"], "checked": done, "errors": errors, "stopped": None,
            "total": len(done) + len(errors)}


# ---------------------------------------------------------------------------------------------
# step 3: the draft's own citations, checked against the sources they cite (ENLENS's citations.py)
# ---------------------------------------------------------------------------------------------
# A draft's citations are an ENLENS "text" (cite_texts) made from the draft's text, so the Check citations page, its
# checks, its jobs and its result-page links work for it unchanged. The draft keeps the text's name and AI setting in
# step with its own (`_mirror`), and its claims' and citations' tasks keep the draft's setting (access.draft_of).
def citation_text(ws: Workspace, draft_id: str, create: bool = True) -> str | None:
    """The id of the text whose citations are checked for this draft, made from it the first time (no AI is used);
    None when the draft cites nothing Margin can read."""
    d = _row(ws, draft_id)
    tid = d.get("cite_text_id")
    if tid and ws.scalar("SELECT 1 FROM cite_texts WHERE text_id=?", (tid,)):
        return tid
    if tid == "" or not create:
        return None  # looked for already: the draft's text never changes
    try:
        tid = citations.add_text(ws, d["text"], title=d["title"], file_name=d["file_name"])
    except citations.CitationError:
        tid = ""
    with ws.connect() as cx:
        cx.execute("UPDATE drafts SET cite_text_id=? WHERE draft_id=?", (tid, draft_id))
        if tid:
            _mirror(cx, draft_id)
    return tid or None


def link_all(ws: Workspace) -> None:
    """Every draft's citations looked for (drafts added before Margin read citations), for the Check citations list."""
    for (did,) in ws.query("SELECT draft_id FROM drafts WHERE cite_text_id IS NULL"):
        try:
            citation_text(ws, did)
        except Exception:  # noqa: BLE001 - one draft that cannot be read must not hide the others
            continue


def _mirror(cx, draft_id: str) -> None:
    """The draft's citations' text takes its name and its AI setting (its own, or NULL: the project's default)."""
    cx.execute("UPDATE cite_texts SET title=(SELECT title FROM drafts WHERE draft_id=?), "
               "ai_access=(SELECT ai_access FROM drafts WHERE draft_id=?) "
               "WHERE text_id=(SELECT cite_text_id FROM drafts WHERE draft_id=?)", (draft_id, draft_id, draft_id))


def of_text(ws: Workspace, text_id: str) -> dict | None:
    """The draft a text of Check citations was made from: {draft_id, title}, or None."""
    r = ws.query("SELECT draft_id, title FROM drafts WHERE cite_text_id=?", (text_id,))
    return {"draft_id": r[0]["draft_id"], "title": r[0]["title"]} if r else None


def new_cited_draft(ws: Workspace, text: str, title: str | None = None, file_name: str | None = None,
                    ai_access: str | None = None) -> str:
    """A text given to Check citations (pasted, or read from a file) is kept as a draft, so it can also be checked
    for the claims that need a source; returns its citations' text id. A text without citations is not kept."""
    did = new_draft(ws, text, title, file_name, ai_access)
    tid = citation_text(ws, did)
    if not tid:
        delete(ws, did)
        raise citations.CitationError(
            "No citations were found in this text. Margin reads author-year citations such as (Smith, 2020) and "
            "Smith et al. (2020), and numbered ones such as [3] when the text ends with its numbered reference list. "
            "To see which of its statements need a source, use Check a draft.")
    return tid


# the answer about a citation, in the groups of Check citations (citations.VERDICT, STATE_TEXT)
CITE_NOTICES = citations.NOTICE_GROUPS
CITE_BLOCKED = ("ambiguous", "no_work", "no_document", "to_confirm", "same_document")


def _citations(ws: Workspace, draft_id: str, threshold: float) -> dict | None:
    """The draft's citations for its page: each cited work with its place in the draft, its answer or what it needs,
    and the counts of Check citations."""
    tid = citation_text(ws, draft_id)
    if not tid:
        return None
    v = citations.view(ws, tid, threshold)
    at = {r["cite_id"]: (r["start"], r["end"]) for r in ws.query("SELECT cite_id, start, end FROM citations "
                                                                  "WHERE text_id=?", (tid,))}
    refs = []
    for r in v["refs"]:
        a, b = at.get(r["cite_id"], (None, None))
        group = r["verdict"] if r["state"] == "checked" else r["state"]
        refs.append({"ref_id": r["ref_id"], "cite_id": r["cite_id"], "start": a, "end": b, "raw": r["raw"],
                     "marker": r["marker"], "claim": r["claim"], "group": group, "state": r["state"],
                     "text": r["verdict_text"] or r["state_text"], "help": r["verdict_help"], "status": r["status"],
                     "hyp_id": r["hyp_id"], "work": (r["work"] or {}).get("cite"),
                     "quote": (r["quote"] or {}).get("quote"), "ignored": r["state"] in ("ignored", "contrast")})
    c = v["counts"]
    return {"text_id": tid, "citations": v["citations"], "works": v["works"], "refs": refs, "counts": c,
            "ready": v["ready"], "accurate": v["accurate"], "checking": v["checking"], "notices": v["notices"],
            "blocked": sum(c.get(k, 0) for k in CITE_BLOCKED), "has_bibliography": v["has_bibliography"],
            "numeric_unread": v["text"]["numeric_unread"]}


def _claim_of(text: str, claims: list[dict], a: int, b: int) -> dict | None:
    """The claim a citation at a..b stands for: the one it is inside of, or right after it ("… a week (Smith, 2020)",
    "… rose.[3]"), or right before it in the same sentence ("According to Smith (2020), …"; never across the end of a
    sentence: "(Smith, 2020). It also …" is not the next sentence's)."""
    best, gap = None, 4
    for c in claims:
        if a < c["end"] and b > c["start"]:
            g = 0
        elif a >= c["end"]:
            g = a - c["end"]
        else:
            g = c["start"] - b if not re.search(r"[.!?\n]", text[b:c["start"]]) else gap
        if 0 <= g < gap:
            best, gap = c, g
    return best


# ---------------------------------------------------------------------------------------------
# the view of a draft
# ---------------------------------------------------------------------------------------------
SIDES =(("supports", "supports"), ("partly", "partially_supports"), ("refutes", "refutes"))


def _evidence(res: dict, cites: dict[str, dict] | None = None) -> dict[str, list[dict]]:
    """The documents on each side of a claim's answer (as the result page counts them), each with its best quote and,
    for a document linked to a work of the bibliography, its APA 7 in-text citation (`apa`, Margin 0.5)."""
    items = [x for p in res["parts"] for x in p["passages"] if x.get("counted")]
    out: dict[str, list[dict]] = {"supports": [], "partly": [], "refutes": []}
    for w in res.get("who") or []:
        verdict = dict(SIDES)[w["side"]]
        best = max((x for x in items if x["doc_id"] == w["doc_id"] and x["verdict"] == verdict),
                   key=lambda x: x.get("confidence") or 0, default=None)
        out[w["side"]].append({"doc_id": w["doc_id"], "title": w["title"], "excerpts": w["excerpts"],
                               "locations": w["locations"][:3], "both_sides": w["both_sides"],
                               "quote": best["quote"] if best else None,
                               "location": best["location"] if best else None,
                               "passage_id": best["passage_id"] if best else None,
                               "quote_by": best["quote_by"] if best else None,
                               "apa": (cites or {}).get(w["doc_id"])})
    return out


def _cite_sides(ev: dict[str, list[dict]]) -> dict[str, dict]:
    """Margin 0.5: the documents of each side in one APA 7 citation, "(Haugen, 2024; Verhoeven & Okafor, 2025)"."""
    out = {}
    for side, docs in ev.items():
        both = bibliography.apa_together([e["apa"] for e in docs if e.get("apa")])
        if both:
            out[side] = {**both, "missing": sum(1 for e in docs if not e.get("apa"))}
    return out


def view(ws: Workspace, draft_id: str, threshold: float | None = None) -> dict:
    """Everything the draft page shows: the text, each claim with its place, its answer and the documents for and
    against it, how the finding stands, and what Claude has read of the draft."""
    d = _row(ws, draft_id)
    thr = claimcheck._threshold(ws, threshold)
    lv = level(ws, draft_id)
    cache = claimcheck.ResultCache(ws, thr)
    has_bib = bibliography.has(ws)
    cites = bibliography.apa_citations(ws) if has_bib else {}
    claims = []
    counts: dict[str, int] = {}
    for r in ws.query("SELECT * FROM draft_claims WHERE draft_id=? ORDER BY start, end", (draft_id,)):
        c = {k: r[k] for k in ("claim_id", "start", "end", "quote", "claim", "kind", "why", "source", "model",
                               "hyp_id")}
        c.update(cited=bool(r["cited"]), skip=bool(r["skip"]), edited=bool(r["edited"]),
                 decision=r["decision"] or ("dismissed" if r["skip"] else None), decided_at=r["decided_at"],
                 kind_text=KIND_TEXT.get(r["kind"] or "other", "A claim"),
                 source_text=SOURCE_TEXT.get(r["source"], r["source"]), status=None, evidence=None, cite=None,
                 citations=[])
        if r["hyp_id"]:
            try:
                res = cache.result(r["hyp_id"])
            except KeyError:
                res = None
            if res is not None:
                ev = _evidence(res, cites)
                c.update(status=res["status"], status_text=res["status_text"], evidence=ev, cite=_cite_sides(ev),
                         excerpts_read=res["excerpts_read"], to_review=res["to_review_relevant"],
                         waiting_for_you=res["waiting_for_you"], balance=res["balance"],
                         checked_at=res["created_at"])
                counts[res["status"]] = counts.get(res["status"], 0) + 1
        claims.append(c)
    cits = _citations(ws, draft_id, thr)
    for ref in (cits or {}).get("refs", []):  # each citation on the claim it stands for (step 3 with step 1)
        c = _claim_of(d["text"], claims, ref["start"], ref["end"]) if ref["start"] is not None else None
        ref["claim_id"] = c["claim_id"] if c else None
        if c:
            c["citations"].append(ref)
            c["cited"] = c["cited"] or not ref["ignored"]
    return {"draft": {"draft_id": draft_id, "title": d["title"], "file_name": d["file_name"],
                      "created_at": d["created_at"], "chars": len(d["text"]), "words": len(d["text"].split()),
                      "ai_access": lv, "own_setting": d["ai_access"] is not None, "ai_label": access.LABEL[lv],
                      "batch_id": d["batch_id"], "found_by": d["found_by"], "found_at": d["found_at"]},
            "text": d["text"], "claims": claims, "threshold": thr, "bibliography": has_bib,
            "counts": {"claims": len(claims), "kept": sum(1 for c in claims if not c["skip"]),
                       "checked": sum(1 for c in claims if c["hyp_id"]),
                       "to_check": sum(1 for c in claims if not c["skip"] and not c["hyp_id"] and not c["decision"]),
                       "decided": {k: sum(1 for c in claims if c["decision"] == k) for k in DECISIONS},
                       "cited": sum(1 for c in claims if c["cited"]), "status": counts},
            "citations": cits,
            "finding": finding(ws, draft_id), "sent": access.draft_ledger(ws, draft_id),
            "status_text": claimcheck.STATUS_TEXT}


def export_rows(ws: Workspace, draft_id: str, threshold: float | None = None) -> list[dict]:
    """One row per claim, in the order of the draft: for a table of what to cite."""
    v = view(ws, draft_id, threshold)

    def docs(c: dict, side: str) -> str:
        ev = (c.get("evidence") or {}).get(side) or []
        return "; ".join(e["title"] + (f" ({', '.join(e['locations'])})" if e["locations"] else "") for e in ev)

    rows = []
    for n, c in enumerate(v["claims"], 1):
        rows.append({"#": n, "Sentence in the draft": c["quote"], "Claim checked": c["claim"], "Kind": c["kind_text"],
                     "Already cited in the draft": "yes" if c["cited"] else "no", "Found by": c["source_text"],
                     "Checked": "dismissed" if c["skip"] else ("yes" if c["hyp_id"] else "not yet"),
                     "Answer": c.get("status_text") or "",
                     "Your decision": DECISION_TEXT.get(c["decision"] or "", ""),
                     "Supporting documents": docs(c, "supports"), "Partly supporting": docs(c, "partly"),
                     "Contradicting documents": docs(c, "refutes"),
                     "Citation (APA 7)": ((c.get("cite") or {}).get("refutes" if c["decision"] == "refuted"
                                                                     else "supports") or {}).get("text", ""),
                     "Your citations": "; ".join(r["raw"] for r in c["citations"] if not r["ignored"]),
                     "What the cited source says": "; ".join(f"{r['raw']}: {r['text']}" for r in c["citations"]
                                                             if not r["ignored"]),
                     "Position in the draft": f"characters {c['start']}–{c['end']}"})
    return rows


# ---------------------------------------------------------------------------------------------
# Margin's kind of AI task: the claims in a part of a draft (registered with ENLENS's task registry, taskkinds.py,
# as an add-on's kind is: ENLENS checks every quote against the part of the draft before store_claims stores it)
# ---------------------------------------------------------------------------------------------
def claims_system() -> str:
    from .prompts import _JSON_RULE  # noqa: F401  (used in the text)

    return f"""You read part of a researcher's own draft (a paper, thesis, report or proposal) and list the
statements that need a source: a citation to published evidence that lets a reader verify them.

A statement needs a source when it presents as fact something this draft does not establish itself:
- statistic: a number, amount, share, rate or trend;
- causal: a cause, an effect, an influence or a mechanism;
- comparison: more or less than, the largest, the main, a ranking;
- prior_research: what studies, data or experts found or say;
- generalisation: a claim about the world, a field, a group or a practice ("is widely used", "most firms");
- definition: a definition, a date or a history attributed to others;
- other: any other factual claim a careful reviewer would ask a source for.
It does not need one when it is the author's own aim, plan, method, argument, interpretation or result in this
work ("we interviewed", "this paper argues", "our results show"), a question, a heading, a signpost of the text
itself, or common knowledge no reader would doubt.

Rules
- quote: the statement as it stands in the PASSAGE, copied character for character: the whole sentence, or the
  clause that makes the claim. Never quote the BEFORE text.
- claim: the statement as one plain, self-contained sentence that a source could support or contradict: say what
  "it", "this" and "they" stand for, keep its numbers, place, time, group and direction; add nothing and leave out
  any citation. Do not judge whether it is true.
- cited: true when the passage already gives a source for it (an author and year, a number in brackets, a footnote
  mark), else false. List cited statements too: the researcher wants to see whether the documents back them.
- why: a few words on what a reader would want a source for.
- At most {25} statements, in the order they appear. An empty list is a valid answer.

Output format
{{"claims": [{{"quote": "It cut their emissions by 30% in 2021.", "claim": "Remote work cut commuters' emissions by 30% in 2021.",
  "kind": "statistic", "cited": false, "why": "a figure and a year"}}], "note": null}}
{_JSON_RULE}"""


def claims_user(payload: dict) -> str:
    out = f"DRAFT: {payload.get('title') or 'untitled'} (part {payload.get('part', 1)} of {payload.get('parts', 1)})"
    if payload.get("context"):
        out += f"\n\nBEFORE (to know what \"it\" and \"this\" refer to; not to be listed or quoted):\n…{payload['context']}"
    return out + f"\n\nPASSAGE:\n{payload['text']}"


def _claims_demo(payload: dict) -> dict:
    """The offline demo: the rules a draft marked No AI is read with."""
    return {"claims": rule_claims(payload["text"])[:MAX_PER_PART], "note": "Offline demo: found by rules, not by reading."}


CLAIMS_KIND = taskkinds.register(taskkinds.TaskKind(
    name="claims", prompt_version="claims-v1", system=claims_system, user=claims_user, schema=None,
    quote_from=lambda payload: payload["text"], store=lambda cx, t, payload, obj, model: store_claims(cx, t, payload, obj, model),
    # reading a draft for its claims is careful reading of the researcher's own text, not bulk work
    claude=("sonnet", "opus"), local="large", helper="margin-reader",
    row="claims", row_title="Claims in a draft that need a source",
    batch=3, order=0,  # the researcher's own request: first in the queue; parts of up to 4,000 characters each
    noun=("part of a draft to read for claims", "parts of a draft to read for claims"), short="parts of drafts",
    title="Claims in a draft", run_name="Claims in a draft", output_cap=4000, demo=_claims_demo,
    size=lambda k, max_chars: 300 + 4000 + 400))  # a part of a draft and the end of the part before
