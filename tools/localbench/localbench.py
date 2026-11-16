"""Local model bench on the green hydrogen pilot: accuracy, overconfidence, guessing or reasoning, reliability, speed.

Not part of the app. It reads the pilot workspace (read-only) and writes everything under a data folder.

    python tools/localbench/localbench.py build                     # items.jsonl + the Opus sheets
    (Opus answers each sheet twice, blind: data/opus/A.jsonl, data/opus/B.jsonl)
    python tools/localbench/localbench.py gold                      # gold.jsonl + disagreements.json
    python tools/localbench/localbench.py run --model qwen3.5:4b    # resumable; --think for reasoning on
    python tools/localbench/localbench.py report                    # report.json

Items (45): 30 real verify_set tasks of the pilot (balanced over Opus's statuses: 10 supported, 7 partly, 1
contradicted, 12 nothing) and 15 planted controls whose answer is known by construction:
- planted: a paraphrase of the claim is slipped into one passage of a task where nothing bore on it -> supported
- flip: a supported claim rewritten to say the opposite -> contradicted
- irrel: a claim shown with passages of another SDG goal's task -> nothing

Runs per item (reasoning off): base (the app's settings: temperature 0, seed 42), base2 (the same again:
determinism), shuffle (passages in another order), t07_s1..s4 (temperature 0.7, four seeds: how settled the model
is). With --think: base and shuffle only (each answer takes minutes).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PILOT = HERE.parents[1] / "pilot"   # the repository's pilot workspace (read-only)
THR = 0.6                      # the pilot's support_confidence: a grade below it does not count
SEED = 11
STATUSES = ("supported", "partially_supported", "contradicted", "unsupported")
GROUNDED = {"supported", "partially_supported"}

FLIPS = {  # supported claim -> its opposite (the passages that supported it should now contradict it)
    "verify_set:5.1#1": "The green hydrogen value chain offers few work opportunities for women, because its jobs "
                        "tend to be reserved for men.",
    "verify_set:4.4#1": "The green hydrogen value chain is unlikely to create new jobs.",
    "verify_set:12.2#1": "Electrolyser technology for green hydrogen production needs only abundant, inexpensive "
                         "materials and puts little strain on natural resources.",
    "verify_set:14.2#1": "Hydrogen-based fuels offer little prospect of decarbonising the maritime sector.",
    "verify_set:6.1#1": "Even in water-stressed regions, the water source for green hydrogen production needs no "
                        "particular attention in strategies or project planning.",
}
PLANTS = {  # claim with nothing in its passages -> a paraphrase slipped into one passage
    "verify_set:16.1#3": "In cities, building the pipelines and refuelling stations that hydrogen use requires has "
                         "already sparked local disputes and opposition from residents.",
    "verify_set:5.1#4": "As hydrogen projects add jobs, women risk being under-represented in this workforce and "
                        "paid less than men.",
    "verify_set:7.3#1": "Because energy is lost at every step from electrolysis to final use, the overall efficiency "
                        "of the hydrogen chain still has to be raised considerably.",
    "verify_set:17.7#2": "Moving hydrogen technologies from one country to another depends on cooperation across "
                         "borders, and this dependence deserves particular attention as a possible source of concern.",
    "verify_set:9.a#5": "Using hydrogen locally, in industry and transport, can help communities build sustainable "
                        "and resilient infrastructure.",
}
IRREL = ["verify_set:8.2#1", "verify_set:7.b#2", "verify_set:7.3#3", "verify_set:17.19#2", "verify_set:2.3#3"]

VARIANTS = {  # name: (temperature, seed, shuffled)
    "base": (0.0, 42, False), "base2": (0.0, 42, False), "shuffle": (0.0, 42, True),
    "t07_s1": (0.7, 1, False), "t07_s2": (0.7, 2, False), "t07_s3": (0.7, 3, False), "t07_s4": (0.7, 4, False),
}
THINK_VARIANTS = ("base", "shuffle")


def _jl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def _status(out: dict | None) -> str | None:
    if out is None:
        return None
    from margin.benchmark import _status_from
    return _status_from(out, 6, THR)


# ---------------------------------------------------------------------------------------------------- build
def build(args) -> None:
    from margin import prompts
    from margin.benchmark import _status_from

    cx = sqlite3.connect(f"file:{PILOT / 'enlens.sqlite'}?mode=ro", uri=True)
    rows = []
    for tid, pj, raw in cx.execute(
            "SELECT t.task_id, t.payload_json, r.raw_json FROM tasks t JOIN results r USING(task_id) "
            "WHERE t.kind='verify_set' AND r.valid=1 AND r.model='claude-opus-5-5' ORDER BY t.task_id"):
        p, o = json.loads(pj), json.loads(raw)
        rows.append({"task": tid, "payload": p, "pilot_opus": o, "pilot_status": _status_from(o, len(p["passages"]), THR)})
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r["pilot_status"], []).append(r)
    rng = random.Random(SEED)
    for k in sorted(by):
        rng.shuffle(by[k])
    controls = set(FLIPS) | set(PLANTS) | set(IRREL)
    pick = lambda st, n: [r for r in by[st] if r["task"] not in controls][:n]
    real = pick("supported", 10) + pick("partially_supported", 7) + pick("contradicted", 1) + pick("unsupported", 12)
    task = {r["task"]: r for r in rows}

    items = [{"origin": "real", "source": r["task"], "expect": None, "payload": r["payload"],
              "pilot_status": r["pilot_status"]} for r in real]
    for tid, claim in FLIPS.items():
        p = json.loads(json.dumps(task[tid]["payload"]))
        p["claim"] = claim
        items.append({"origin": "flip", "source": tid, "expect": "contradicted", "payload": p,
                      "original_claim": task[tid]["payload"]["claim"]})
    for tid, sent in PLANTS.items():
        p = json.loads(json.dumps(task[tid]["payload"]))
        k = rng.randrange(len(p["passages"]))
        text = p["passages"][k]["text"]
        cuts = [m.end() for m in re.finditer(r"[.!?]\s+(?=[A-Z])", text)]
        at = cuts[len(cuts) // 2] if cuts else len(text)
        p["passages"][k]["text"] = (text[:at].rstrip() + " " + sent + " " + text[at:].lstrip()).strip()
        items.append({"origin": "planted", "source": tid, "expect": "supported", "payload": p,
                      "planted_passage": k + 1, "planted_sentence": sent})
    goal = lambda t: t.split(":")[1].split(".")[0]
    for tid in IRREL:
        other = [r for r in real if goal(r["task"]) != goal(tid) and r["pilot_status"] == "unsupported"]
        donor = other[IRREL.index(tid) % len(other)]
        p = json.loads(json.dumps(task[tid]["payload"]))
        p["passages"] = json.loads(json.dumps(donor["payload"]["passages"]))
        items.append({"origin": "irrel", "source": tid, "expect": "unsupported", "payload": p,
                      "passages_from": donor["task"]})
    rng.shuffle(items)
    sysp = prompts.system_prompt("verify_set")
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "items.jsonl").open("w") as f:
        for i, it in enumerate(items, 1):
            it["id"] = f"i{i:02d}"
            perm = list(range(len(it["payload"]["passages"])))
            random.Random(f"{SEED}-{it['id']}").shuffle(perm)
            it["shuffle"] = perm      # shown position j holds original passage perm[j]
            it["user"] = prompts.user_prompt("verify_set", it["payload"])
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    (DATA / "system_prompt.txt").write_text(sysp)
    # the Opus sheets: no origin, no expectation, no pilot answer
    (DATA / "opus").mkdir(exist_ok=True)
    half = (len(items) + 1) // 2
    for part, chunk in (("1", items[:half]), ("2", items[half:])):
        body = [f"=== ITEM {it['id']} ===\n{it['user']}\n" for it in chunk]
        (DATA / "opus" / f"sheet_{part}.txt").write_text("\n".join(body))
    print(f"{len(items)} items -> {DATA / 'items.jsonl'}; sheets in {DATA / 'opus'}")


# ---------------------------------------------------------------------------------------------------- validation
def judge(raw: str | None, payload: dict, perm: list[int] | None = None) -> dict:
    """Parse and check one answer like the app does. Passage numbers are mapped back to the original order."""
    from margin.schema import VerifySetOut
    from margin.tasks import parse_json
    from margin.textutil import find_quote, grade_quote_problem

    rec: dict = {"json_ok": False, "usable": False, "errors": []}
    if raw is None:
        return rec
    try:
        obj = VerifySetOut.model_validate(parse_json(raw))
    except Exception as e:
        rec["errors"] = [str(e)[:200]]
        return rec
    rec["json_ok"] = True
    shown = payload["passages"] if perm is None else [payload["passages"][j] for j in perm]
    grades: dict[str, dict] = {}
    for ev in obj.evidence:
        if ev.passage > len(shown):
            rec["errors"].append(f"no passage P{ev.passage}")
            continue
        orig = ev.passage if perm is None else perm[ev.passage - 1] + 1
        quote_ok = not grade_quote_problem(ev.quote) and bool(find_quote(shown[ev.passage - 1]["text"], ev.quote))
        if not quote_ok:
            rec["errors"].append(f"quote not found in P{ev.passage}")
        if str(orig) in grades:
            rec["errors"].append(f"P{ev.passage} twice")
            continue
        grades[str(orig)] = {"verdict": ev.verdict, "confidence": ev.confidence, "quote_ok": quote_ok,
                             "quote": ev.quote}
    rec["grades"] = grades
    rec["usable"] = not rec["errors"]
    out = {"evidence": [{"passage": int(k), **v} for k, v in grades.items()]}
    rec["status"] = _status(out)
    rec["rationale"] = (obj.rationale or "")[:400]
    return rec


# ---------------------------------------------------------------------------------------------------- gold
def gold(args) -> None:
    items = {it["id"]: it for it in _jl(DATA / "items.jsonl")}
    passes = {}
    for name in ("A", "B"):
        rows = {r["id"]: r for r in _jl(DATA / "opus" / f"{name}.jsonl")}
        missing = sorted(set(items) - set(rows))
        if missing:
            sys.exit(f"Opus pass {name} misses {missing}")
        passes[name] = {i: judge(json.dumps(rows[i]["answer"]), items[i]["payload"]) for i in items}
    adj = {r["id"]: r for r in _jl(DATA / "opus" / "adjudication.jsonl")}
    golds, disagree = [], []
    for i, it in sorted(items.items()):
        a, b = passes["A"][i], passes["B"][i]
        ga, gb = ({k: v["verdict"] for k, v in x.get("grades", {}).items() if v["confidence"] >= THR} for x in (a, b))
        same = a.get("status") == b.get("status") and ga == gb
        rec = {"id": i, "origin": it["origin"], "expect": it["expect"], "A_status": a.get("status"),
               "B_status": b.get("status"), "agree_status": a.get("status") == b.get("status"), "agree_grades": ga == gb}
        if same:
            rec.update(status=a["status"], grades=ga, by="A=B")
        elif i in adj:
            ans = judge(json.dumps(adj[i]["answer"]), it["payload"])
            rec.update(status=ans["status"],
                       grades={k: v["verdict"] for k, v in ans["grades"].items() if v["confidence"] >= THR},
                       by="adjudicated", note=adj[i].get("note"))
        else:
            disagree.append({"id": i, "A": passes["A"][i], "B": passes["B"][i]})
            rec.update(status=None, grades=None, by="open")
        if it["expect"] and rec.get("status") and rec["status"] != it["expect"]:
            rec["against_design"] = True
        golds.append(rec)
    with (DATA / "gold.jsonl").open("w") as f:
        for r in golds:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (DATA / "disagreements.json").write_text(json.dumps(disagree, ensure_ascii=False, indent=1))
    # Opus's own calibration and agreement, for comparison with the local models
    (DATA / "runs").mkdir(exist_ok=True)
    for name in ("A", "B"):
        with (DATA / "runs" / f"opus-{name}.jsonl").open("w") as f:
            for i in sorted(items):
                f.write(json.dumps({"id": i, "variant": "base", **passes[name][i]}, ensure_ascii=False) + "\n")
    n = len(golds)
    print(f"gold: {sum(r['by'] == 'A=B' for r in golds)} agreed, {sum(r['by'] == 'adjudicated' for r in golds)} "
          f"adjudicated, {len(disagree)} open of {n}; status agreement A/B "
          f"{sum(r['agree_status'] for r in golds)}/{n}; against design: {[r['id'] for r in golds if r.get('against_design')]}")


# ---------------------------------------------------------------------------------------------------- run
def _machine() -> dict:
    def sh(*c):
        try:
            return subprocess.run(c, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            return ""
    swap = re.search(r"used = ([\d.]+)M", sh("sysctl", "vm.swapusage"))
    free = re.search(r"free percentage: (\d+)%", sh("memory_pressure", "-Q"))
    return {"swap_mb": float(swap.group(1)) if swap else None, "mem_free_pct": int(free.group(1)) if free else None,
            "therm": sh("pmset", "-g", "therm").replace("\n", " ")[-160:]}


def _ollama(path: str, body: dict | None = None) -> dict:
    from urllib.request import Request, urlopen
    req = Request(f"http://127.0.0.1:11434{path}", data=json.dumps(body).encode() if body else None,
                  method="POST" if body else "GET", headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode() or "{}")


def unload_all() -> None:
    for m in _ollama("/api/ps").get("models", []):
        _ollama("/api/generate", {"model": m["name"], "keep_alive": 0})


def run(args) -> None:
    from margin import prompts
    from margin.llm import OllamaBackend

    class Bench(OllamaBackend):
        temperature = 0.0

        def _stream(self, body, *a, **k):
            body = {**body, "options": {**body["options"], "temperature": self.temperature}}
            return super()._stream(body, *a, **k)

    items = _jl(DATA / "items.jsonl")
    if args.limit:
        items = items[:args.limit]
    tag = args.model.replace("/", "_").replace(":", "_") + ("-think" if args.think else "")
    out = DATA / "runs" / f"{tag}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["id"], r["variant"]) for r in _jl(out)}
    variants = [v for v in (args.variants or (THINK_VARIANTS if args.think else VARIANTS)) if v in VARIANTS]
    sysp = (DATA / "system_prompt.txt").read_text()
    if not args.keep_loaded:
        unload_all()
    before = _machine()
    be = Bench(think=args.think, think_budget=args.budget if args.think else 0, num_ctx=16384)
    be.memory_guard = True
    todo = [(v, it) for v in variants for it in items if (it["id"], v) not in done]
    print(f"{args.model} think={args.think}: {len(todo)} answers to go ({len(done)} done) -> {out}", flush=True)
    t_start = time.time()
    with out.open("a") as f:
        for n, (v, it) in enumerate(todo, 1):
            temp, seed, shuffled = VARIANTS[v]
            be.temperature, be.seed = temp, seed
            perm = it["shuffle"] if shuffled else None
            payload = it["payload"] if perm is None else {**it["payload"],
                                                          "passages": [it["payload"]["passages"][j] for j in perm]}
            user = it["user"] if perm is None else prompts.user_prompt("verify_set", payload)
            t0 = time.time()
            raw, err = None, None
            try:
                raw = be.complete("verify_set", sysp, user, args.model, payload)
            except Exception as e:  # keep going: a failure is a result too
                err = f"{type(e).__name__}: {str(e)[:300]}"
                if type(e).__name__ == "MemoryShort":
                    print(err)
                    break
            rec = {"id": it["id"], "variant": v, "seconds": round(time.time() - t0, 2), "error": err,
                   "stats": getattr(be, "last_stats", None) if err is None else None, "raw": raw,
                   **judge(raw, it["payload"], perm)}
            if n % 10 == 1:
                rec["machine"] = _machine()
                ps = _ollama("/api/ps").get("models", [])
                rec["loaded"] = [{"name": m["name"], "gb": round(m.get("size_vram", m.get("size", 0)) / 1e9, 2),
                                  "ctx": m.get("context_length")} for m in ps]
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if n % 10 == 0 or n == len(todo):
                el = time.time() - t_start
                print(f"  {n}/{len(todo)}  {el / 60:.1f} min, ~{el / n * (len(todo) - n) / 60:.0f} min left", flush=True)
    meta = DATA / "runs" / f"{tag}.meta.json"
    m = json.loads(meta.read_text()) if meta.exists() else {"model": args.model, "think": args.think, "sessions": []}
    m["sessions"].append({"before": before, "after": _machine(), "budget": args.budget if args.think else 0,
                          "variants": variants, "at": time.strftime("%Y-%m-%d %H:%M")})
    try:
        tags = {x["name"]: x for x in _ollama("/api/tags")["models"]}
        x = tags.get(args.model) or {}
        m["disk_gb"], m["details"] = round(x.get("size", 0) / 1e9, 2), x.get("details")
    except Exception:
        pass
    meta.write_text(json.dumps(m, indent=1))
    if not args.keep_loaded:
        unload_all()


# ---------------------------------------------------------------------------------------------------- report
def _kappa(pairs):
    from margin.benchmark import kappa
    return kappa(pairs)


def _q(xs, p):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def score(tag: str, items: dict, golds: dict) -> dict:
    rows = _jl(DATA / "runs" / f"{tag}.jsonl")
    by = {}
    for r in rows:
        by.setdefault(r["variant"], {})[r["id"]] = r
    base = by.get("base", {})
    ids = [i for i in sorted(base) if golds.get(i, {}).get("status")]
    real = [i for i in ids if items[i]["origin"] == "real"]
    res: dict = {"answers": len(rows), "items": len(ids)}
    if not ids:
        return res
    st = lambda i: base[i].get("status")
    # --- performance
    res["usable"] = sum(base[i]["usable"] for i in ids) / len(ids)
    res["quote_problem"] = sum(any("quote" in e for e in base[i].get("errors", [])) for i in ids) / len(ids)
    res["errors"] = sum(bool(base[i].get("error")) for i in ids)
    res["status_acc"] = sum(st(i) == golds[i]["status"] for i in ids) / len(ids)
    res["status_acc_real"] = sum(st(i) == golds[i]["status"] for i in real) / len(real) if real else None
    res["grounded_kappa"] = _kappa([(golds[i]["status"] in GROUNDED, st(i) in GROUNDED) for i in ids])
    res["always_nothing_acc"] = sum(golds[i]["status"] == "unsupported" for i in ids) / len(ids)
    conf = {s: {t: 0 for t in STATUSES + ("none",)} for s in STATUSES}
    for i in ids:
        conf[golds[i]["status"]][st(i) or "none"] += 1
    res["confusion"] = conf
    # controls
    ctl = {}
    for o in ("planted", "flip", "irrel"):
        cs = [i for i in ids if items[i]["origin"] == o]
        if not cs:
            continue
        if o == "planted":
            ok = [str(items[i]["planted_passage"]) in {k for k, g in base[i].get("grades", {}).items()
                                                      if g["confidence"] >= THR and g["verdict"] != "refutes"} for i in cs]
        elif o == "flip":
            ok = [st(i) == "contradicted" for i in cs]
            res["flip_still_supported"] = sum(st(i) in GROUNDED for i in cs) / len(cs)
        else:
            ok = [st(i) == "unsupported" for i in cs]
        ctl[o] = sum(ok) / len(cs)
    res["controls"] = ctl
    # --- overconfidence (per passage the model graded, at any confidence)
    # strict: the same grade as gold; lenient: gold also grades the passage, in the same direction
    # (supports and partially_supports count as one direction, refutes as the other)
    sign = lambda v: "neg" if v == "refutes" else "pos"
    pts, lpts = [], []   # (confidence, correct)
    fp_conf = []         # confidence on passages that gold says bear on nothing
    for i in ids:
        g = golds[i]["grades"] or {}
        for k, e in base[i].get("grades", {}).items():
            pts.append((e["confidence"], g.get(k) == e["verdict"]))
            lpts.append((e["confidence"], k in g and sign(g[k]) == sign(e["verdict"])))
            if k not in g:
                fp_conf.append(e["confidence"])
    if lpts:
        res["mean_conf"] = statistics.mean(c for c, _ in lpts)
        res["grade_acc_lenient"] = sum(r for _, r in lpts) / len(lpts)
        res["overconfidence_lenient"] = res["mean_conf"] - res["grade_acc_lenient"]
        cnt = [(c, r) for c, r in lpts if c >= THR]   # the grades that count in the app
        if cnt:
            res["counting_grades"] = len(cnt)
            res["counting_mean_conf"] = statistics.mean(c for c, _ in cnt)
            res["counting_precision"] = sum(r for _, r in cnt) / len(cnt)
            res["counting_overconfidence"] = res["counting_mean_conf"] - res["counting_precision"]
        rel, ece = [], 0.0
        for lo, hi in [(0, .5), (.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01)]:
            b = [(c, r) for c, r in lpts if lo <= c < hi]
            if b:
                mc, acc = statistics.mean(c for c, _ in b), sum(r for _, r in b) / len(b)
                rel.append({"bin": f"{lo:.1f}-{min(hi, 1):.1f}", "n": len(b), "conf": mc, "acc": acc})
                ece += len(b) / len(lpts) * abs(mc - acc)
        res["reliability_lenient"], res["ece_lenient"] = rel, ece
    if pts:
        res["graded_passages"] = len(pts)
        res["mean_conf"] = statistics.mean(c for c, _ in pts)
        res["grade_acc"] = sum(r for _, r in pts) / len(pts)
        res["overconfidence"] = res["mean_conf"] - res["grade_acc"]
        bins = [(0, .5), (.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01)]
        rel = []
        ece = 0.0
        for lo, hi in bins:
            b = [(c, r) for c, r in pts if lo <= c < hi]
            if b:
                mc, acc = statistics.mean(c for c, _ in b), sum(r for _, r in b) / len(b)
                rel.append({"bin": f"{lo:.1f}-{min(hi, 1):.1f}", "n": len(b), "conf": mc, "acc": acc})
                ece += len(b) / len(pts) * abs(mc - acc)
        res["reliability"], res["ece"] = rel, ece
        res["brier"] = statistics.mean((c - r) ** 2 for c, r in pts)
        hi = [r for c, r in pts if c >= .8]
        res["acc_when_conf_ge_0.8"] = sum(hi) / len(hi) if hi else None
        res["share_conf_ge_0.8"] = len(hi) / len(pts)
    res["false_positives"] = len(fp_conf)
    res["false_positives_counting"] = sum(c >= THR for c in fp_conf)   # crossing the app's threshold
    res["fp_mean_conf"] = statistics.mean(fp_conf) if fp_conf else None
    gold_pass = sum(len(golds[i]["grades"] or {}) for i in ids)
    found = sum(1 for i in ids for k, v in (golds[i]["grades"] or {}).items()
                if base[i].get("grades", {}).get(k, {}).get("confidence", 0) >= THR)
    res["passage_recall"] = found / gold_pass if gold_pass else None
    # --- reliability
    def same(v):
        o = by.get(v, {})
        c = [i for i in ids if i in o]
        return (sum(o[i].get("status") == st(i) for i in c) / len(c), len(c)) if c else (None, 0)
    res["determinism"], _ = same("base2")
    if "base2" in by:
        c = [i for i in ids if i in by["base2"]]
        res["identical_raw"] = sum(by["base2"][i].get("raw") == base[i].get("raw") for i in c) / len(c)
    res["order_stable"], _ = same("shuffle")
    samp = [v for v in by if v.startswith("t07")]
    if samp:
        stable, modal, ent_wrong, ent_right = 0, [], [], []
        for i in ids:
            sts = [st(i)] + [by[v][i].get("status") for v in samp if i in by[v]]
            top = max(set(sts), key=sts.count)
            stable += len(set(sts)) == 1
            modal.append(sts.count(top) / len(sts))
        res["sampling_runs"] = len(samp) + 1
        res["all_runs_same"] = stable / len(ids)
        res["modal_share"] = statistics.mean(modal)
        # does stated confidence track how settled the model is? mean top confidence on stable vs unsettled items
        topc = lambda i: max([g["confidence"] for g in base[i].get("grades", {}).values()] or [None], key=lambda x: x or 0)
        st_c = [topc(i) for i, m in zip(ids, modal) if m == 1 and topc(i) is not None]
        un_c = [topc(i) for i, m in zip(ids, modal) if m < 1 and topc(i) is not None]
        res["conf_when_settled"] = statistics.mean(st_c) if st_c else None
        res["conf_when_unsettled"] = statistics.mean(un_c) if un_c else None
        votes = []
        for i in ids:
            sts = [st(i)] + [by[v][i].get("status") for v in samp if i in by[v]]
            votes.append(max(set(sts), key=sts.count) == golds[i]["status"])
        res["acc_majority_vote"] = sum(votes) / len(votes)
        # settledness vs correctness: are the unsettled items the wrong ones?
        right = [st(i) == golds[i]["status"] for i in ids]
        res["acc_when_settled"] = (sum(r for r, m in zip(right, modal) if m == 1) / max(1, sum(m == 1 for m in modal)))
        res["acc_when_unsettled"] = (sum(r for r, m in zip(right, modal) if m < 1) / max(1, sum(m < 1 for m in modal)))
    # --- speed and hardware
    secs = [r["seconds"] for r in rows if r.get("seconds") is not None and not r.get("error")]
    stats = [r["stats"] for r in rows if r.get("stats")]
    res["sec_median"], res["sec_p90"] = _q(secs, .5), _q(secs, .9)
    if stats:
        pt = sum(s["prompt_tokens"] or 0 for s in stats)
        ps = sum(s["prompt_seconds"] or 0 for s in stats)
        ot = sum(s["output_tokens"] or 0 for s in stats)
        os_ = sum(s["output_seconds"] or 0 for s in stats)
        res["prompt_tok_s"] = pt / ps if ps else None
        res["output_tok_s"] = ot / os_ if os_ else None
        res["thinking_tokens_median"] = _q([s.get("thinking_tokens") or 0 for s in stats], .5)
        res["budget_reached"] = sum(bool(s.get("budget_reached")) for s in stats) / len(stats)
    mach = [r["machine"] for r in rows if r.get("machine")]
    loaded = [x for r in rows for x in r.get("loaded", [])]
    if loaded:
        res["memory_gb"] = max(x["gb"] for x in loaded)
    if mach:
        res["swap_mb_max"] = max((m["swap_mb"] or 0) for m in mach)
        res["mem_free_pct_min"] = min((m["mem_free_pct"] or 100) for m in mach)
    meta = DATA / "runs" / f"{tag}.meta.json"
    if meta.exists():
        mm = json.loads(meta.read_text())
        res["disk_gb"], res["details"] = mm.get("disk_gb"), mm.get("details")
        res["sessions"] = mm.get("sessions")
    return res


def report(args) -> None:
    items = {it["id"]: it for it in _jl(DATA / "items.jsonl")}
    golds = {g["id"]: g for g in _jl(DATA / "gold.jsonl")}
    tags = sorted(p.stem for p in (DATA / "runs").glob("*.jsonl"))
    out = {"items": len(items), "gold_open": sum(g["status"] is None for g in golds.values()),
           "gold_by": {k: sum(g["by"] == k for g in golds.values()) for k in ("A=B", "adjudicated", "open")},
           "opus_status_agreement": sum(g["agree_status"] for g in golds.values()) / max(1, len(golds)),
           "models": {t: score(t, items, golds) for t in tags}}
    (DATA / "report.json").write_text(json.dumps(out, indent=1))
    keys = ["status_acc", "status_acc_real", "always_nothing_acc", "grounded_kappa", "controls", "mean_conf", "grade_acc_lenient", "counting_mean_conf", "counting_precision", "counting_overconfidence", "ece_lenient", "acc_majority_vote", "acc_when_settled", "acc_when_unsettled",
            "grade_acc", "overconfidence", "ece", "acc_when_conf_ge_0.8", "false_positives_counting", "passage_recall",
            "determinism", "order_stable", "all_runs_same", "modal_share", "sec_median", "output_tok_s", "memory_gb"]
    for t, r in out["models"].items():
        print(f"\n{t}")
        for k in keys:
            v = r.get(k)
            print(f"  {k:26} {json.dumps(v) if isinstance(v, dict) else (f'{v:.3f}' if isinstance(v, float) else v)}")


def html(args) -> None:
    sys.path.insert(0, str(HERE))
    import page
    print(page.build(DATA, DATA / "local-model-bench.html"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("gold")
    sub.add_parser("report")
    sub.add_parser("html")
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--think", action="store_true", help="reasoning on (the app's default for models that can)")
    r.add_argument("--budget", type=int, default=2500, help="reasoning budget in tokens (the app's default 2500)")
    r.add_argument("--variants", nargs="+", choices=list(VARIANTS))
    r.add_argument("--limit", type=int, help="only the first N items (a smoke test)")
    r.add_argument("--keep-loaded", action="store_true", help="do not unload models before and after")
    a = ap.parse_args()
    {"build": build, "gold": gold, "run": run, "report": report, "html": html}[a.cmd](a)


if __name__ == "__main__":
    main()
