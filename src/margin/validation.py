"""The validation report's AI half (roadmap J4.3, 0.18.4): Margin's AI answers scored against known right answers.

`margin measure` (measure.py) is the half that needs no AI. This half needs a set of right answers (the gold set) and
a recorded, dated run of the AI on it. The gold set is invented on purpose (`tools/validation/`, read its README):
documents on remote work in which every name and figure is fictional, so the right answer to each question is known
by construction. It holds hypotheses with their verdicts (the kind `check`) and passages with the codes of a small
codebook made for it (the kind `label`).

    margin validate prepare --project "Validation 2026-11-13"     # a new project from the gold documents, tasks queued
    /margin-run "Validation 2026-11-13"                           # in Claude Code: the queue answers them
    margin validate prepare --project "Validation 2026-11-13 again"   # the same again, for repeatability
    /margin-run "Validation 2026-11-13 again"
    margin validate score --project "Validation 2026-11-13" --again "Validation 2026-11-13 again"
                                                                  # tools/validation/runs/<date>-<route>.json
    margin validate report --latest tools/validation/runs --out validation-report-ai.md   # no AI

A local model answers the same queue with `margin --ws <project folder> queue run --backend ollama --model <name>`
instead of /margin-run. The run file keeps every answer with its model, prompt version, Margin version and date, and
the gold answer beside it, so the report is made from the run file alone, with no AI (the release workflow does that).
A run answered on this computer is named after its model (`<date>-qwen3-5-4b.json`), not "local model server", so
two local models never share a name; `margin validate report --latest runs/` sets the newest run of every route side
by side (Claude Code beside each local model), then gives each in full.

**Right answers from a real project, labelled by a person** (the second half of J4.3, Level 0: no AI):

    margin validate person --project "Repair cafés" [--label "Repair cafés study"]
                                                                  # tools/validation/runs/person/<date>-<label>.json

takes what a person decided in a real project as the right answers and scores the AI's answers in that project against
them: each excerpt of a check that an AI judged and a person then judged themselves (*Judge it myself*, a review that
agrees or disagrees: `verifications.user_verdict`), and each code of a codebook an AI gave that a person accepted,
changed or rejected (`reviews`, kind `label`), with the codes a person added to a passage the AI had labelled (codes it
missed). Only what a person decided counts: an AI answer a person merely left alone is not a right answer, a comment
without a judgement is not one, and an excerpt only a person judged (no AI read it) has no AI answer to score. The
file holds grades, codes, models and prompt versions only, never a document's text, a quote or a hypothesis; it names
the project by `--label` (the project's own name when none is given). The report shows it beside the invented gold
set, labelled as what it is.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .store import Workspace

FORMAT = 1
FRAMEWORK = "validation"
META = "validation"
STATUSES = ("supported", "partially_supported", "contested", "contradicted", "unsupported")
GROUNDED = {"supported", "partially_supported"}
STATUS_WORDS = {"supported": "Supported", "partially_supported": "Partly supported", "contested": "Mixed evidence",
                "contradicted": "Contradicted", "unsupported": "No evidence found"}
DECOMPOSE = ("compound", "all", "none")


def version() -> str:
    """The Margin that prepares and scores a run: `git describe` of the git copy the gold set is in (the commit, which
    an installed package's metadata may not match when it runs from the sources), else the package's version."""
    from . import __version__

    try:
        import subprocess

        from .procs import no_window

        out = subprocess.run(["git", "describe", "--tags", "--match", "v[0-9]*", "--dirty"],
                             cwd=Path(__file__).resolve().parent, capture_output=True, text=True, timeout=10,
                             stdin=subprocess.DEVNULL, **no_window())
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:  # noqa: BLE001 - no git, no repository, a timeout
        pass
    return __version__


def default_folder() -> Path:
    """`tools/validation/` of a git copy of Margin (the gold set is not part of the installed package)."""
    return Path(__file__).resolve().parents[2] / "tools" / "validation"


# ---------------------------------------------------------------------------------------------------------------
# The gold set
# ---------------------------------------------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(s.split()).lower()


def _codes(v: str | None) -> list[str]:
    return sorted({c.strip() for c in re.split(r"[;,]", v or "") if c.strip()})


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def load_gold(folder: str | Path | None = None) -> dict:
    """The gold set: its documents (its own and the demo corpus beside it), codebook, hypotheses and labelled
    passages, and a fingerprint of all of them (so a run says which version of the gold set it was scored on)."""
    folder = Path(folder) if folder else default_folder()
    if not (folder / "hypotheses.csv").exists():
        raise FileNotFoundError(f"No gold set in {folder} (hypotheses.csv is missing). The gold set is in a git copy of "
                                "Margin, in tools/validation/.")
    demo = folder.parent / "demo_corpus"
    docs = sorted((folder / "documents").glob("*.*"))
    if demo.is_dir():
        docs += sorted(p for p in demo.iterdir() if p.suffix.lower() in (".txt", ".html", ".htm", ".md")
                       and p.name.lower() != "readme.md")
    codebook = (folder / "codebook.csv").read_text(encoding="utf-8-sig")
    hyps = []
    for r in _rows(folder / "hypotheses.csv"):
        v = r.get("verdict", "").lower()
        if v not in STATUSES:
            raise ValueError(f"hypotheses.csv, {r.get('id')}: the verdict {v!r} is not one of {', '.join(STATUSES)}.")
        hyps.append({"id": r["id"], "hypothesis": r["hypothesis"], "gold": v,
                     "compound": r.get("compound", "").lower() in ("yes", "y", "1", "true")})
    labels = [{"file": r["file"], "anchor": r["anchor"], "gold": _codes(r.get("codes")),
               "mentioned": _codes(r.get("mentioned"))} for r in _rows(folder / "labels.csv")]
    from .frameworks import parse_csv

    known = set(parse_csv(codebook))
    for lb in labels:
        bad = [c for c in lb["gold"] + lb["mentioned"] if c not in known]
        if bad:
            raise ValueError(f"labels.csv, {lb['file']} {lb['anchor'][:30]!r}: codes not in the codebook: {bad}")
    h = hashlib.sha256()
    for p in [folder / "codebook.csv", folder / "hypotheses.csv", folder / "labels.csv", *docs]:
        h.update(p.name.encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return {"folder": str(folder), "documents": docs, "codebook": codebook, "codes": sorted(known),
            "hypotheses": hyps, "labels": labels, "fingerprint": h.hexdigest()[:16]}


def match_passages(ws: Workspace, labels: list[dict]) -> dict[str, str]:
    """{gold key ("file#anchor"): passage_id}: the passage of that file whose text holds the anchor. Raises ValueError
    listing every anchor found in no passage, or in more than one (the gold set and the reader disagree)."""
    by_file: dict[str, list] = {}
    for r in ws.query("SELECT p.passage_id, p.text, d.path FROM passages p JOIN documents d ON d.doc_id=p.doc_id "
                      "ORDER BY p.passage_id"):
        by_file.setdefault(Path(r["path"] or "").name, []).append((r["passage_id"], _norm(r["text"])))
    out, problems = {}, []
    for lb in labels:
        a = _norm(lb["anchor"])
        hits = [pid for pid, t in by_file.get(lb["file"], []) if a in t]
        if len(hits) != 1:
            problems.append(f"{lb['file']}: {lb['anchor'][:50]!r} is in {len(hits)} passages")
        else:
            out[key(lb)] = hits[0]
    if problems:
        raise ValueError("The gold set's passages do not match how Margin reads the documents: " + "; ".join(problems))
    return out


def key(lb: dict) -> str:
    return f"{lb['file']}#{lb['anchor']}"


# ---------------------------------------------------------------------------------------------------------------
# Prepare: a new project from the gold documents, its tasks waiting in the queue
# ---------------------------------------------------------------------------------------------------------------
def prepare(ws: Workspace, folder: str | Path | None = None, decompose: str = "compound", k: int = 8,
            per_doc: int = 2) -> dict:
    """Read the gold documents into an empty project, add the gold codebook, and queue a check for every hypothesis
    and a label task for every gold passage, as the app would (`decompose`: split into parts the compound
    hypotheses, all of them, or none, as a researcher ticks *Split into parts*). Nothing is answered here."""
    from . import access, claimcheck, frameworks, home, ingest, profile, routing
    from . import tasks as tk

    if decompose not in DECOMPOSE:
        raise ValueError(f"decompose: one of {', '.join(DECOMPOSE)}")
    g = load_gold(folder)
    if ws.scalar("SELECT COUNT(*) FROM documents"):
        raise ValueError("Prepare a validation run in a new, empty project: this one already has documents.")
    access.set_default(ws, "cloud")
    read = ingest.ingest(ws, [str(p) for p in g["documents"]], ai_access="cloud")
    frameworks.save(ws, FRAMEWORK, g["codebook"], title="Validation codebook (invented, remote work)", label="code")
    pids = match_passages(ws, g["labels"])
    from .taskqueue import queue_route

    r = routing.from_settings(home.load_settings(), route=queue_route())
    hyps: dict[str, str] = {}
    with tk.queueing():
        batch = claimcheck._new_id("b")
        for h in g["hypotheses"]:
            split = decompose == "all" or (decompose == "compound" and h["compound"])
            hyps[h["id"]] = claimcheck.queue_check(ws, h["hypothesis"], r, k=k, per_doc=per_doc, expand=True,
                                                   decompose=split, batch_id=batch, origin="validation",
                                                   origin_id=h["id"])
        profile.ensure_pass1(ws, FRAMEWORK)
        made = profile.make_label_tasks(ws, FRAMEWORK, list(pids.values()), r.model("label"), all_passages=True)
        with ws.connect() as cx:
            tk.mark_queued(cx, [f"label:{FRAMEWORK}:{p}" for p in pids.values()])
    ws.set_meta(META, {"fingerprint": g["fingerprint"], "hypotheses": hyps, "passages": pids,
                       "prepared_at": _now(), "prepared_by": version(),
                       "settings": {"k": k, "per_doc": per_doc, "decompose": decompose, "expand": True}})
    return {"documents": ws.scalar("SELECT COUNT(*) FROM documents"), "failed": read.get("failed") or [],
            "hypotheses": len(hyps), "label_tasks": made,
            "gold_fingerprint": g["fingerprint"]}


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------------------------------------------
# Score: one answered project (two with --again) into a run file
# ---------------------------------------------------------------------------------------------------------------
def _quote_problem(errors: list) -> bool:
    return any("quote" in str(e) and ("not found" in str(e) or "too long" in str(e)) for e in errors or [])


def _answers(ws: Workspace, task_ids: list[str]) -> list[dict]:
    """Each task with the answer that counts (its last accepted one), how it was made, and whether its first answer
    was rejected for a quote not found in the text."""
    from .tasks import parse_json

    out = []
    for tid in task_ids:
        t = ws.query("SELECT task_id, kind, status FROM tasks WHERE task_id=?", (tid,))
        if not t:
            continue
        rs = ws.query("SELECT attempt, model, prompt_version, app_version, received_at, route, helper, valid, "
                      "errors_json, raw_json FROM results WHERE task_id=? ORDER BY attempt", (tid,))
        valid = [r for r in rs if r["valid"]]
        last = valid[-1] if valid else None
        first_errors = json.loads(rs[0]["errors_json"] or "[]") if rs else []
        try:
            answer = parse_json(last["raw_json"]) if last else None
        except ValueError:
            answer = None
        out.append({"task_id": tid, "kind": t[0]["kind"], "status": t[0]["status"], "attempts": len(rs),
                    "accepted_first": bool(rs and rs[0]["valid"]), "quote_problem_first": bool(rs) and
                    not rs[0]["valid"] and _quote_problem(first_errors),
                    "first_errors": [str(e)[:200] for e in first_errors[:3]] if rs and not rs[0]["valid"] else [],
                    "models": [r["model"] for r in valid],
                    **({"model": last["model"], "prompt_version": last["prompt_version"],
                        "app_version": last["app_version"], "answered_at": last["received_at"],
                        "route": last["route"], "helper": last["helper"]} if last else {}),
                    "answer": answer})
    return out


def _hyp_tasks(ws: Workspace, hyp_id: str) -> list[str]:
    cids = [r[0] for r in ws.query("SELECT claim_id FROM user_claims WHERE hyp_id=? ORDER BY part", (hyp_id,))]
    ids = [r[0] for r in ws.query("SELECT task_id FROM tasks WHERE task_id=?", (f"decompose:{hyp_id}",))]
    for c in cids:
        ids += [r[0] for r in ws.query(
            "SELECT task_id FROM tasks WHERE task_id=? OR task_id=? OR substr(task_id, 1, ?)=? OR substr(task_id, 1, ?)=? "
            "ORDER BY task_id", (f"expand:{c}", f"check:{c}", len(f"check:{c}:"), f"check:{c}:",
                                 len(f"second:check:{c}"), f"second:check:{c}"))]
    return list(dict.fromkeys(ids))


def collect(ws: Workspace, folder: str | Path | None = None) -> dict:
    """One answered pass of a prepared project: per gold item, Margin's result and every answer it rests on."""
    from . import claimcheck, frameworks

    meta = ws.meta(META)
    if not meta:
        raise ValueError(f"{ws.root.name} is not a validation project (made with `margin validate prepare`).")
    g = load_gold(folder)
    hist = {h["hyp_id"]: h for h in claimcheck.history(ws)}
    checks = []
    for h in g["hypotheses"]:
        hid = meta["hypotheses"].get(h["id"])
        row = hist.get(hid) if hid else None
        checks.append({"id": h["id"], "hypothesis": h["hypothesis"], "compound": h["compound"], "gold": h["gold"],
                       "got": row["status"] if row else None, "parts": row["parts"] if row else None,
                       "answers": _answers(ws, _hyp_tasks(ws, hid)) if hid else []})
    fw = frameworks.get(FRAMEWORK, ws)
    labels = []
    for lb in g["labels"]:
        pid = meta["passages"].get(key(lb))
        ans = _answers(ws, [f"label:{FRAMEWORK}:{pid}"]) if pid else []
        got = None
        if ans and ans[0]["answer"] is not None:
            got = sorted({fw.normalise(x["code"]) or str(x["code"]) for x in ans[0]["answer"].get("labels") or []
                          if isinstance(x, dict) and x.get("code")})
        labels.append({"key": key(lb), "passage_id": pid, "gold": lb["gold"], "mentioned": lb["mentioned"],
                       "got": got, "answers": ans})
    return {"project": ws.root.name, "prepared_at": meta.get("prepared_at"), "prepared_by": meta.get("prepared_by"),
            "settings": meta.get("settings"), "gold_fingerprint_prepared": meta.get("fingerprint"),
            "checks": checks, "labels": labels}


LOCAL_ROUTES = ("local model server",)   # routing.ROUTE_NAMES of a model on this computer (Ollama, a local server)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-") or "unknown"


def _route_of(passes: list[dict]) -> str:
    """The run's route, for its file name and its report: the route most answers came by; for a model on this
    computer, that model's name (most answers), since "local model server" would name every local model alike."""
    answers = [a for p in passes for it in p["checks"] + p["labels"] for a in it["answers"] if a.get("route")]
    routes = Counter(a["route"] for a in answers)
    r = routes.most_common(1)[0][0] if routes else "unanswered"
    if r in LOCAL_ROUTES:
        models = Counter(a.get("model") for a in answers if a["route"] == r and a.get("model"))
        if models:
            return _slug(models.most_common(1)[0][0])
    return _slug(r)


def _is_local(run: dict) -> bool:
    """Whether a run was answered on this computer (its answers' route), for the report's words."""
    routes = Counter(a.get("route") for p in run["passes"] for it in p["checks"] + p["labels"] for a in it["answers"]
                     if a.get("route"))
    return bool(routes) and routes.most_common(1)[0][0] in LOCAL_ROUTES


def make_run(passes: list[dict], gold: dict, route: str | None = None, date: str | None = None) -> dict:
    route = route or _route_of(passes)
    models: dict[str, Counter] = {}
    prompts: dict[str, Counter] = {}
    versions: Counter = Counter()
    for p in passes:
        for it in p["checks"] + p["labels"]:
            for a in it["answers"]:
                if a.get("model"):
                    models.setdefault(a["kind"], Counter())[a["model"]] += 1
                    prompts.setdefault(a["kind"], Counter())[a.get("prompt_version") or "?"] += 1
                    versions[a.get("app_version") or "?"] += 1
    local = any(a.get("route") in LOCAL_ROUTES for p in passes for it in p["checks"] + p["labels"]
                for a in it["answers"])
    return {"format": FORMAT, "date": date or _dt.date.today().isoformat(), "route": route, "local": local,
            "scored_by": version(), "gold": {"fingerprint": gold["fingerprint"], "hypotheses": len(gold["hypotheses"]),
                                               "passages": len(gold["labels"]), "codes": gold["codes"]},
            "models": {k: dict(v) for k, v in sorted(models.items())},
            "prompt_versions": {k: dict(v) for k, v in sorted(prompts.items())},
            "margin_versions": dict(versions), "passes": passes}


def write_run(run: dict, out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"{run['date']}-{run['route']}"
    path, n = out_dir / f"{base}.json", 2
    while path.exists():
        path, n = out_dir / f"{base}-{n}.json", n + 1
    path.write_text(json.dumps(run, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def read_run(path: str | Path) -> dict:
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    if run.get("format") != FORMAT:
        raise ValueError(f"{path}: not a validation run file of format {FORMAT}.")
    return run


def latest_run(folder: str | Path) -> Path | None:
    """The newest run file in `folder` (by the date its name starts with, then its name), or None."""
    folder = Path(folder)

    def order(p: Path) -> tuple:
        m = re.search(r"-(\d{1,3})$", p.stem)  # write_run's -2, -3 for a second run of the same day and route
        return p.name[:10], p.stem[: m.start()] if m else p.stem, int(m.group(1)) if m else 1

    files = sorted(folder.glob("*.json"), key=order) if folder.is_dir() else []
    return files[-1] if files else None


def latest_runs(folder: str | Path) -> list[Path]:
    """The newest run file of each route in `folder` (the route as the run file names it), newest first; [] when
    there is none. A person's judgements (`person/`) are not runs of the gold set and are not among them."""
    found: dict[str, tuple[tuple, Path]] = {}
    folder = Path(folder)
    for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            run = read_run(p)
        except (ValueError, OSError):
            continue
        m = re.search(r"-(\d{1,3})$", p.stem)
        order = (run.get("date") or p.name[:10], int(m.group(1)) if m else 1, p.name)
        r = run.get("route") or "unknown"
        if r not in found or order > found[r][0]:
            found[r] = (order, p)
    return [p for _o, p in sorted(found.values(), key=lambda x: x[0], reverse=True)]


# ---------------------------------------------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------------------------------------------
def kappa(pairs: list[tuple]) -> float | None:
    """Cohen's kappa of two raters over any number of categories; None with nothing to compare or when chance
    agreement is already complete (both raters always give the same one category)."""
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in ca) / (n * n)
    if pe >= 1:
        return None
    return round((po - pe) / (1 - pe), 3)


def _share(xs: list[bool]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None


def _code_pairs(a: list[str] | None, b: list[str] | None, codes: list[str], skip: list[str]) -> list[tuple]:
    a, b = set(a or []), set(b or [])
    return [(c in a, c in b) for c in codes if c not in skip]


def score_checks(items: list[dict]) -> dict:
    pairs = [(it["gold"], it["got"] or "no answer") for it in items]
    conf: dict[str, Counter] = {}
    for g, x in pairs:
        conf.setdefault(g, Counter())[x] += 1
    out = {"n": len(items), "answered": sum(1 for it in items if it["got"] in STATUSES),
           "accuracy": _share([g == x for g, x in pairs]), "kappa": kappa(pairs),
           # found evidence or not: over the finished checks only (an unfinished one found nothing, and would
           # count as right wherever the gold says nothing is there)
           "grounded_accuracy": _share([(g in GROUNDED) == (x in GROUNDED) for g, x in pairs if x in STATUSES]),
           "grounded_kappa": kappa([(g in GROUNDED, x in GROUNDED) for g, x in pairs if x in STATUSES]),
           "confusion": {g: dict(c) for g, c in conf.items()},
           "per_verdict": {s: _share([x == s for g, x in pairs if g == s]) for s in STATUSES
                           if any(g == s for g, _ in pairs)}}
    for name, sel in (("simple", False), ("compound", True)):
        sub = [(g, x) for (g, x), it in zip(pairs, items) if it.get("compound") == sel]
        if sub:
            out[f"{name}_accuracy"], out[f"{name}_n"] = _share([g == x for g, x in sub]), len(sub)
    return out


def score_labels(items: list[dict], codes: list[str]) -> dict:
    pairs = [p for it in items for p in _code_pairs(it["gold"], it["got"], codes, it.get("mentioned") or [])]
    per_code = {}
    for c in codes:
        tp = sum(1 for it in items if c in it["gold"] and c in (it["got"] or []))
        fp = sum(1 for it in items if c not in it["gold"] and c not in it.get("mentioned", []) and c in (it["got"] or []))
        fn = sum(1 for it in items if c in it["gold"] and c not in (it["got"] or []))
        per_code[c] = {"gold": tp + fn, "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                       "recall": round(tp / (tp + fn), 3) if tp + fn else None}
    same = [set(it["gold"]) == set(it["got"] or []) - set(it.get("mentioned") or []) for it in items]
    return {"n": len(items), "answered": sum(1 for it in items if it["got"] is not None),
            "code_decisions": len(pairs), "code_accuracy": _share([a == b for a, b in pairs]),
            "kappa": kappa(pairs), "same_codes": _share(same), "per_code": per_code}


def quote_failures(items: list[dict], kinds: tuple[str, ...]) -> dict:
    ans = [a for it in items for a in it["answers"] if a["kind"] in kinds and a["attempts"]]
    return {"answers": len(ans), "accepted_first": _share([a["accepted_first"] for a in ans]),
            "first_rejected_for_quotes": _share([a["quote_problem_first"] for a in ans]),
            "never_accepted": _share([not a["models"] for a in ans])}


def repeatability(p1: dict, p2: dict, codes: list[str]) -> dict:
    a = {it["id"]: it["got"] or "no answer" for it in p1["checks"]}
    b = {it["id"]: it["got"] or "no answer" for it in p2["checks"]}
    cp = [(a[i], b[i]) for i in a if i in b]
    la = {it["key"]: it for it in p1["labels"]}
    lp = [(la[it["key"]], it) for it in p2["labels"] if it["key"] in la]
    pairs = [p for x, y in lp for p in _code_pairs(x["got"], y["got"], codes, [])]
    return {"checks": {"n": len(cp), "same_status": _share([x == y for x, y in cp]), "kappa": kappa(cp)},
            "labels": {"n": len(lp), "same_codes": _share([set(x["got"] or []) == set(y["got"] or []) for x, y in lp]),
                       "code_agreement": _share([x == y for x, y in pairs]), "kappa": kappa(pairs)}}


def score(run: dict) -> dict:
    codes = run["gold"]["codes"]
    passes = run["passes"]
    out = {"passes": []}
    for p in passes:
        out["passes"].append({"checks": score_checks(p["checks"]), "labels": score_labels(p["labels"], codes),
                              "quotes": {"check": quote_failures(p["checks"], ("check",)),
                                         "label": quote_failures(p["labels"], ("label",))}})
    if len(passes) > 1:
        out["repeatability"] = repeatability(passes[0], passes[1], codes)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Right answers from a real project, labelled by a person (no AI)
# ---------------------------------------------------------------------------------------------------------------
PERSON_DIR = "person"   # the person's judgements beside the runs: runs/person/<date>-<label>.json
PERSON_GRADES = ("supports", "partially_supports", "refutes", "not_relevant")
GRADE_WORDS = {"supports": "Supports", "partially_supports": "Partly supports", "refutes": "Contradicts",
               "not_relevant": "Not about it"}


def _ai_grade(v: str | None) -> str:
    """An AI's grade of an excerpt in a person's words: anything but the three grades is "not about it" (as
    verdicts.changed_by_person reads it)."""
    return v if v in ("supports", "partially_supports", "refutes") else "not_relevant"


def collect_person(ws: Workspace, label: str | None = None) -> dict:
    """What a person decided in a real project, set beside what the AI had answered, with no text: {"format", "kind":
    "person", "project" (`label`, else the project's folder name), "date", "scored_by", "checks": [{"ai", "person",
    "model", "prompt_version"[, "shown_first"]}], "checks_person_only" (excerpts a person judged that no AI read: not
    scored), "checks_pointed" (I6: excerpts the small local model only pointed at: not scored; `shown_first`: a local
    model's suggestion the person saw before judging),
    "labels": [{"ai": true, "kept": bool, "changed": bool, "model", "prompt_version", "framework"}] (each AI code a
    person decided on), "labels_added": [{"framework"}] (codes a person added to a passage the AI had labelled),
    "people" (how many people decided)}. Only what a person decided counts (see the module's docstring)."""
    from .profile import _decisions
    from .verdicts import PERSON

    checks, person_only, pointed, people = [], 0, 0, set()
    for r in ws.query("SELECT verdict, user_verdict, model, prompt_version, suggestion_json FROM verifications "
                      "WHERE subject_kind='user_claim' AND user_verdict IS NOT NULL"):
        if r["user_verdict"] not in PERSON_GRADES:
            continue
        if not r["model"] or r["model"] == PERSON:   # no AI read it: nothing to score
            person_only += 1
            continue
        try:
            sug = json.loads(r["suggestion_json"]) if r["suggestion_json"] else None
        except ValueError:
            sug = None
        if sug and sug.get("form") == "point":   # I6: the small local model pointed at a sentence and judged nothing
            pointed += 1
            continue
        people.add("")  # Margin: one person decides
        item = {"ai": _ai_grade(r["verdict"]), "person": r["user_verdict"], "model": r["model"],
                "prompt_version": r["prompt_version"] or "?"}
        if sug:   # I6: a local model's suggestion, shown to the person before they judged: agreement is not independent
            item["shown_first"] = True
        checks.append(item)
    dec = _decisions(ws)
    who: dict[str, str] = {}  # Margin: one person (ENLENS names each label's reviewer, reviews.person_id)
    # the passages the AI labelled: their label task (`label:<framework>:<passage>`) was answered by a model. Matched
    # on the whole task id, never split: a passage id has a colon of its own (`<doc>:0001`)
    read = {r["task_id"] for r in ws.query(
        "SELECT task_id FROM tasks WHERE kind='label' AND status='done' AND COALESCE(model, '')<>?", (PERSON,))}
    labels, added = [], []
    for r in ws.query("SELECT label_id, framework, passage_id, code, source, model, prompt_version FROM labels "
                      "WHERE source IN ('model', 'person') ORDER BY label_id"):
        if r["source"] == "model":
            d = dec.get(r["label_id"])
            if not d or d["decision"] not in ("accept", "change", "reject"):
                continue   # an AI code no person decided on: not a right answer
            people.add(who.get(r["label_id"], ""))
            labels.append({"kept": d["decision"] != "reject", "changed": d["decision"] == "change",
                           "model": r["model"] or "?", "prompt_version": r["prompt_version"] or "?",
                           "framework": r["framework"]})
        elif f"label:{r['framework']}:{r['passage_id']}" in read:
            added.append({"framework": r["framework"]})
    return {"format": FORMAT, "kind": "person", "project": (label or ws.root.name).strip()[:120],
            "date": _dt.date.today().isoformat(), "scored_by": version(), "checks": checks,
            "checks_person_only": person_only, "checks_pointed": pointed, "labels": labels, "labels_added": added,
            "people": len(people - {""}) or (1 if checks or labels else 0)}


def write_person(rec: dict, runs_dir: str | Path) -> Path:
    """`runs/person/<date>-<label>.json` (-2, -3 for a second one of the same day)."""
    out = Path(runs_dir) / PERSON_DIR
    out.mkdir(parents=True, exist_ok=True)
    base = f"{rec['date']}-{_slug(rec['project'])}"
    path, n = out / f"{base}.json", 2
    while path.exists():
        path, n = out / f"{base}-{n}.json", n + 1
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def latest_person(runs_dir: str | Path) -> list[dict]:
    """The newest person's judgements of each project in `runs/person/`, newest first."""
    folder = Path(runs_dir) / PERSON_DIR
    found: dict[str, tuple[tuple, dict]] = {}
    for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if rec.get("format") != FORMAT or rec.get("kind") != "person":
            continue
        m = re.search(r"-(\d{1,3})$", p.stem)
        order = (rec.get("date") or "", int(m.group(1)) if m else 1)
        if rec["project"] not in found or order > found[rec["project"]][0]:
            found[rec["project"]] = (order, rec)
    return [r for _o, r in sorted(found.values(), key=lambda x: x[0], reverse=True)]


def score_person(rec: dict) -> dict:
    """The AI's answers against the person's: per model, and in all."""
    def checks(items):
        pairs = [(it["person"], it["ai"]) for it in items]
        conf: dict[str, Counter] = {}
        for g, x in pairs:
            conf.setdefault(g, Counter())[x] += 1
        return {"n": len(pairs), "accuracy": _share([g == x for g, x in pairs]), "kappa": kappa(pairs),
                "grounded_accuracy": _share([(g in ("supports", "partially_supports")) ==
                                             (x in ("supports", "partially_supports")) for g, x in pairs]),
                "confusion": {g: dict(c) for g, c in conf.items()}}

    def labels(items, added):
        return {"n": len(items), "kept": _share([it["kept"] for it in items]),
                "changed": sum(1 for it in items if it["changed"]), "added": added}

    by_model: dict[str, list] = {}
    for it in rec["checks"]:
        by_model.setdefault(it["model"], []).append(it)
    lab_model: dict[str, list] = {}
    for it in rec["labels"]:
        lab_model.setdefault(it["model"], []).append(it)
    return {"checks": checks(rec["checks"]), "checks_by_model": {m: checks(v) for m, v in sorted(by_model.items())},
            "labels": labels(rec["labels"], len(rec["labels_added"])),
            "labels_by_model": {m: labels(v, 0) for m, v in sorted(lab_model.items())}}


def person_markdown(recs: list[dict]) -> str:
    """The report's section for a person's judgements on real projects (no AI: from the files alone)."""
    L = ["## Right answers from a real project, labelled by a person", "",
         "Unlike the gold set above, these right answers are what a researcher decided in a real project of their own: "
         "each excerpt of a check that an AI judged and the researcher then judged themselves, and each code an AI "
         "gave that the researcher accepted, changed or rejected. Only what a person decided counts; what they left "
         "alone does not. No document text is kept here.", ""]
    if not recs:
        return "\n".join(L + ["No project's judgements are recorded yet (`margin validate person --project <name>`).",
                               ""])
    for rec in recs:
        sc = score_person(rec)
        c, lb = sc["checks"], sc["labels"]
        L += [f"### {rec['project']} ({rec['date']})", "",
              f"A person's judgements on a real project, recorded on {rec['date']} by Margin {rec['scored_by']} "
              f"({rec['people']} {'person' if rec['people'] == 1 else 'people'} decided).", ""]
        if c["n"]:
            L += [f"- **Excerpts:** the AI's grade was the person's for {_pct(c['accuracy'])} of {c['n']} excerpts "
                  f"(Cohen's kappa {_k(c['kappa'])} over the four grades); found evidence or not, the same for "
                  f"{_pct(c['grounded_accuracy'])}."
                  + (f" {rec['checks_person_only']} more excerpts were judged by the person with no AI answer, so are "
                     "not scored." if rec.get("checks_person_only") else "")
                  + (f" {rec['checks_pointed']} more were only pointed at by the small local model (it judges nothing), "
                     "so are not scored." if rec.get("checks_pointed") else "")
                  + (lambda n: f" {n} of the scored excerpts were the local model's suggestions, shown to the person "
                     "before they judged: agreement on those is not independent." if n else "")(
                      sum(1 for it in rec["checks"] if it.get("shown_first")))]
            if len(sc["checks_by_model"]) > 1:
                L += [f"  - {m}: {_pct(v['accuracy'])} of {v['n']} (kappa {_k(v['kappa'])})"
                      for m, v in sc["checks_by_model"].items()]
            L += ["", "Which grade the AI gave (columns) for each grade the person gave (rows):", "",
                  "| Person's grade | " + " | ".join(GRADE_WORDS[g] for g in PERSON_GRADES) + " | Share the same |",
                  "|---|" + "---|" * (len(PERSON_GRADES) + 1)]
            for g in PERSON_GRADES:
                row = c["confusion"].get(g)
                if row:
                    n = sum(row.values())
                    L.append(f"| {GRADE_WORDS[g]} | " + " | ".join(str(row.get(x, 0)) for x in PERSON_GRADES) +
                             f" | {_pct(row.get(g, 0) / n if n else None)} |")
            L.append("")
        else:
            L += ["- **Excerpts:** none that both an AI and a person judged.", ""]
        if lb["n"] or lb["added"]:
            L += [f"- **Codes:** the person kept {_pct(lb['kept'])} of the {lb['n']} codes an AI gave that they decided "
                  f"on ({lb['changed']} kept with another relevance or direction), and added {lb['added']} codes the "
                  "AI had not given to passages it had labelled.", ""]
            if len(sc["labels_by_model"]) > 1:
                L += [f"  - {m}: kept {_pct(v['kept'])} of {v['n']}" for m, v in sc["labels_by_model"].items()] + [""]
        models = Counter(it["model"] for it in rec["checks"] + rec["labels"])
        if models:
            L += [f"Models judged: {_listing(dict(models))}.", ""]
    L += ["Limits of these figures:", "",
          "- **The person saw the AI's answer** before deciding, so agreement is likely higher than if they had judged "
          "first; and they chose which answers to look at, so these are not a random sample.",
          "- **One project, one person's reading**: another researcher may decide otherwise; no second person "
          "checked these decisions.",
          "- A code the person added counts as missed only on a passage the AI had labelled.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------------------------------------------
# The report (no AI: from the run file alone)
# ---------------------------------------------------------------------------------------------------------------
def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{round(x * 100)}%"


def _k(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def _listing(d: dict) -> str:
    return ", ".join(f"{k} ({n})" for k, n in sorted(d.items(), key=lambda kv: -kv[1])) or "none"


def to_markdown(run: dict, gold_fingerprint: str | None = None) -> str:
    s = score(run)
    first = s["passes"][0]
    c, lb = first["checks"], first["labels"]
    L = ["# Validation report: the AI's answers against known right answers", "",
         f"Recorded on {run['date']} through the route **{run['route']}**"
         f"{' (a model on this computer)' if run.get('local') or _is_local(run) else ''}, scored by Margin "
         f"{run['scored_by']} (the "
         f"tasks prepared by {_listing(Counter(p.get('prepared_by') or '?' for p in run['passes']))}). This "
         "report was made from the recorded run file with no AI; the figures change only when a new run is recorded. "
         "It is the half of the validation report that needs AI; `validation-report.md` is the half that does not.", "",
         "## What was asked", "",
         f"The gold set (fingerprint `{run['gold']['fingerprint']}`) holds {run['gold']['hypotheses']} hypotheses with "
         f"a known verdict and {run['gold']['passages']} passages with the codes of a small codebook of "
         f"{len(run['gold']['codes'])} codes. Margin checked each hypothesis and labelled each passage as it does in "
         "the app, through its task queue, and its results were compared with the gold answers.", ""]
    if gold_fingerprint and gold_fingerprint != run["gold"]["fingerprint"]:
        L += [f"**Note:** the gold set has changed since this run (now `{gold_fingerprint}`). The figures below are "
              "scored against the gold answers as they were when the run was recorded.", ""]
    L += ["| Kind | Models (answers) | Prompt version |", "|---|---|---|"]
    for kind in sorted(run["models"]):
        L.append(f"| {kind} | {_listing(run['models'][kind])} | {_listing(run['prompt_versions'].get(kind, {}))} |")
    L += ["", f"Margin versions that answered: {_listing(run['margin_versions'])}.", "",
          "## Checks (hypotheses against the documents)", "",
          f"- **Right verdict:** {_pct(c['accuracy'])} of {c['n']} hypotheses (Cohen's kappa {_k(c['kappa'])} over "
          f"the five verdicts); {c['answered']} of {c['n']} were finished.",
          f"- **Found evidence or not** (supported or partly, against the rest): right for {_pct(c['grounded_accuracy'])} "
          f"of the {c['answered']} finished (kappa {_k(c['grounded_kappa'])}).",
          *([f"- Single hypotheses: {_pct(c['simple_accuracy'])} of {c['simple_n']}; compound ones (two claims that "
             f"must both hold): {_pct(c['compound_accuracy'])} of {c['compound_n']}."]
            if "simple_n" in c and "compound_n" in c else []),
          "", "Which verdict Margin gave (columns) for each right verdict (rows):", "",
          "| Right verdict | " + " | ".join(STATUS_WORDS[x] for x in STATUSES) + " | Other | Share right |",
          "|---|" + "---|" * (len(STATUSES) + 2)]
    for g in STATUSES:
        row = c["confusion"].get(g)
        if not row:
            continue
        other = sum(n for x, n in row.items() if x not in STATUSES)
        L.append(f"| {STATUS_WORDS[g]} | " + " | ".join(str(row.get(x, 0)) for x in STATUSES) +
                 f" | {other} | {_pct(c['per_verdict'].get(g))} |")
    L += ["", "## Labels (passages against the codebook)", "",
          f"- **Each code, present or not:** {_pct(lb['code_accuracy'])} of {lb['code_decisions']} decisions right "
          f"(Cohen's kappa {_k(lb['kappa'])}). Codes the gold set marks as only mentioned in passing are not scored.",
          f"- **Exactly the right codes:** {_pct(lb['same_codes'])} of {lb['n']} passages ({lb['answered']} answered).",
          "", "| Code | Passages with it | Precision | Recall |", "|---|---|---|---|"]
    for code, v in lb["per_code"].items():
        L.append(f"| {code} | {v['gold']} | {_pct(v['precision'])} | {_pct(v['recall'])} |")
    q = first["quotes"]
    L += ["", "## Quotes", "",
          "Every answer must quote the text it rests on, word for word; Margin rejects an answer whose quote is not in "
          "the passage and asks again.", "",
          f"- Checks: {_pct(q['check']['first_rejected_for_quotes'])} of {q['check']['answers']} answers were first "
          f"rejected for a quote; {_pct(q['check']['accepted_first'])} were accepted on the first try (the others were "
          f"rejected for a quote or another problem, such as a reference not found, and fixed); "
          f"{_pct(q['check']['never_accepted'])} were never accepted.",
          f"- Labels: {_pct(q['label']['first_rejected_for_quotes'])} of {q['label']['answers']} answers were first "
          f"rejected for a quote; {_pct(q['label']['accepted_first'])} were accepted on the first try (the others were "
          f"rejected for a quote or another problem, such as a reference not found, and fixed); "
          f"{_pct(q['label']['never_accepted'])} were never accepted.", "",
          "## Repeatability", ""]
    rp = s.get("repeatability")
    if rp:
        L += ["The whole run was made a second time, in a new project, and the two passes compared with each other "
              "(not with the gold set).", "",
              f"- Checks: the same verdict for {_pct(rp['checks']['same_status'])} of {rp['checks']['n']} hypotheses "
              f"(kappa {_k(rp['checks']['kappa'])}).",
              f"- Labels: the same codes for {_pct(rp['labels']['same_codes'])} of {rp['labels']['n']} passages; "
              f"{_pct(rp['labels']['code_agreement'])} of code decisions the same (kappa {_k(rp['labels']['kappa'])}).",
              ""]
        sec = s["passes"][1]
        L += [f"Against the gold set, the second pass had the right verdict for {_pct(sec['checks']['accuracy'])} of "
              f"hypotheses (kappa {_k(sec['checks']['kappa'])}) and {_pct(sec['labels']['code_accuracy'])} of code "
              f"decisions right (kappa {_k(sec['labels']['kappa'])}).", ""]
    else:
        L += ["This run has one pass only, so repeatability was not measured.", ""]
    L += ["## Limits", "",
          "- **The documents are invented**, written to make the right answers clear. Real documents are longer, less "
          "tidy and more ambiguous, so these figures are an upper bound more than a forecast.",
          "- **The gold set is small** (about 30 hypotheses and 100 passages): one hypothesis is about three points of "
          "accuracy, so a change of a few points between runs is not a real change.",
          "- **English only**, on one subject (remote work), with one codebook made for it.",
          "- **The right answers were written by an AI and checked by a second one**, against the documents only and "
          "without seeing any model's answers; the disagreements were settled by hand. They may still hold mistakes.",
          "- **A check's verdict also depends on the search**: when the eight passages read miss the evidence, the "
          "verdict is wrong although each grade was right. This report measures the whole check, as a researcher "
          "gets it.",
          "- **Claude's answers are not repeatable** the way a seeded local model's are; the repeatability above is "
          "of one run, on one day.", ""]
    return "\n".join(L)


def _route_words(run: dict) -> str:
    return f"{run['route']}{' (on this computer)' if run.get('local') or _is_local(run) else ''}"


def side_by_side(runs: list[dict]) -> list[str]:
    """The newest run of each route in one table (a local model beside Claude), scored on the same gold set."""
    L = ["## The routes side by side", "",
         "The newest recorded run of each route, each scored against the gold set it was recorded on. Each is given in "
         "full below.", "",
         "| Route | Recorded | Models | Right verdict | Kappa, verdicts | Code decisions right | Kappa, codes | "
         "Exactly the right codes |", "|---|---|---|---|---|---|---|---|"]
    for run in runs:
        first = score(run)["passes"][0]
        c, lb = first["checks"], first["labels"]
        models = sorted({m for kind in run["models"].values() for m in kind})
        unfinished = f" ({c['answered']} finished)" if c["answered"] < c["n"] else ""
        L.append(f"| {_route_words(run)} | {run['date']} | {', '.join(models) or 'none'} | {_pct(c['accuracy'])} of "
                 f"{c['n']}{unfinished} | {_k(c['kappa'])} | {_pct(lb['code_accuracy'])} | {_k(lb['kappa'])} | "
                 f"{_pct(lb['same_codes'])} |")
    if len({r["gold"]["fingerprint"] for r in runs}) > 1:
        L += ["", "**Note:** these runs were scored on different versions of the gold set, so they are not exactly "
                  "comparable."]
    return L + [""]


def to_markdown_many(runs: list[dict], gold_fingerprint: str | None = None) -> str:
    """Several routes: the table side by side, then each run in full (its headings one level down; the limits,
    the same for all, once at the end)."""
    L = ["# Validation report: the AI's answers against known right answers", "",
         f"{len(runs)} routes were recorded on the gold set: {', '.join(_route_words(r) for r in runs)}. This report "
         "was made from the recorded run files with no AI; the figures change only when a new run is recorded. It is "
         "the half of the validation report that needs AI; `validation-report.md` is the half that does not.", ""]
    L += side_by_side(runs)
    for i, run in enumerate(runs):
        body = to_markdown(run, gold_fingerprint).split("\n", 1)[1]
        body = re.sub(r"(?m)^## ", "### ", body)
        if i < len(runs) - 1:
            body = body.split("\n### Limits", 1)[0]
        else:
            body = body.replace("\n### Limits", "\n## Limits", 1)
        L += [f"## {_route_words(run)}, {run['date']}", body.strip("\n"), ""]
    return "\n".join(L)


def report(run_path: str | Path | None = None, latest: str | Path | None = None, out: str | Path | None = None,
           folder: str | Path | None = None) -> tuple[str | None, Path | None]:
    """(markdown, the run file used: the newest); (None, None) when `latest` names a folder without any run file.
    With `latest`, the newest run of every route in the folder is reported, side by side (`latest_runs`). A person's
    judgements on real projects (`<runs>/person/`, the newest of each project) follow, when there are any."""
    if run_path:
        paths, runs_dir = [Path(run_path)], Path(run_path).parent
    elif latest:
        paths, runs_dir = latest_runs(latest), Path(latest)
    else:
        paths, runs_dir = [], None
    if not paths:
        return None, None
    runs = [read_run(p) for p in paths]
    fp = None
    try:
        fp = load_gold(folder)["fingerprint"]
    except (FileNotFoundError, ValueError):
        pass
    md = to_markdown(runs[0], fp) if len(runs) == 1 else to_markdown_many(runs, fp)
    persons = latest_person(runs_dir) if runs_dir else []
    if persons:
        md = md.rstrip("\n") + "\n\n" + person_markdown(persons)
    path = paths[0]
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(md, encoding="utf-8")
    return md, path

