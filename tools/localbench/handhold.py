"""Mini test: can hand-holding make a small local model read better? One passage per call, small questions, numbered
sentences instead of quotes, the grade worked out by code.

    python tools/localbench/handhold.py --model ifm/k2-horizon:0.9b --variants opp noopp
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CLAIMS = ["i03", "i37", "i02", "i12", "i29", "i17", "i41", "i04"]
OPPOSITE = {  # written by hand for this test; in the app the opposite would be drafted once per claim
    "i03": "Green hydrogen cannot decarbonise hard-to-abate sectors such as steel, cement, chemicals, refineries and aluminium.",
    "i37": "Few countries have included green hydrogen in their climate mitigation actions to 2030.",
    "i02": "The green hydrogen value chain is likely to create new jobs.",
    "i12": "The green hydrogen value chain does not expand infrastructure or upgrade technology for energy services.",
    "i29": "Producing green hydrogen does not increase the share of renewable energy.",
    "i17": "Green hydrogen production does not compete with the industrial and agriculture sectors for water.",
    "i41": "The costs of using green hydrogen as a maritime fuel are not expected to fall.",
    "i04": "Green hydrogen production does not replace fossil fuels or reduce pollution, even with green electricity.",
}
SYSTEM = ("You answer three short questions about ONE passage and ONE claim about green hydrogen. Use only the passage, "
          "no outside knowledge. Most passages only mention the topic without saying the claim: then the answer is "
          "\"neither\".")


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"(])", " ".join(text.split()))
    return [p for p in parts if p.strip()]


def prompt(variant: str, claim: str, opp: str, sents: list[str]) -> str:
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(sents, 1))
    head = f"CLAIM: {claim}\n" + (f"OPPOSITE OF THE CLAIM: {opp}\n" if variant == "opp" else "")
    says = ('"claim" if that sentence states the claim, "opposite" if it states the opposite of the claim (or that '
            'there is no such effect), "neither" if it only mentions the topic' if variant == "opp" else
            '"claim" if that sentence states the claim, "opposite" if it states the opposite (or that there is no such '
            'effect), "neither" if it only mentions the topic')
    return (f"{head}\nPASSAGE (sentences numbered):\n{numbered}\n\nQUESTIONS\n"
            f"1. evidence: the number of the sentence that comes closest to stating the claim or its opposite; 0 if "
            f"no sentence does.\n2. says: {says}.\n3. scope: \"whole\" if it states the claim's own effect for green "
            f"hydrogen; \"part\" if it states only part of it (the mechanism without the effect, renewable energy in "
            f"general rather than hydrogen, another step of the value chain); \"none\" if says is \"neither\".")


SCHEMA = {"type": "object", "properties": {
    "evidence": {"type": "integer"}, "says": {"type": "string", "enum": ["claim", "opposite", "neither"]},
    "scope": {"type": "string", "enum": ["whole", "part", "none"]}}, "required": ["evidence", "says", "scope"]}


def grade(a: dict, n: int) -> str:
    if a.get("says") == "neither" or not (1 <= int(a.get("evidence") or 0) <= n):
        return "none"
    if a["says"] == "opposite":
        return "refutes"
    return "supports" if a.get("scope") == "whole" else "partially_supports"


def ask(model: str, user: str, seed: int = 42, temp: float = 0.0) -> tuple[dict, float, dict]:
    body = {"model": model, "stream": False, "format": SCHEMA, "think": False, "keep_alive": "5m",
            "options": {"temperature": temp, "seed": seed, "num_ctx": 4096, "num_predict": 120},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
    t = time.time()
    with urlopen(Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                         headers={"Content-Type": "application/json"}), timeout=300) as r:
        out = json.loads(r.read().decode())
    try:
        ans = json.loads(out["message"]["content"])
    except Exception:
        ans = {"says": "neither", "evidence": 0, "scope": "none", "bad": out["message"]["content"][:200]}
    return ans, time.time() - t, {"out_tokens": out.get("eval_count")}


def status(grades: dict) -> str:
    v = set(grades.values())
    return ("supported" if "supports" in v else "partially_supported" if "partially_supports" in v
            else "contradicted" if "refutes" in v else "unsupported")


def main() -> None:
    sys.path.insert(0, str(HERE))
    import review as rv

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ifm/k2-horizon:0.9b")
    ap.add_argument("--variants", nargs="+", default=["opp", "noopp"])
    ap.add_argument("--claims", nargs="+", default=CLAIMS)
    a = ap.parse_args()
    items = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "items.jsonl")}
    gold = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "gold.jsonl")}
    fab = rv._gold_from(rv.reviewer_rows("fable"), json.loads((DATA / "review_cards.json").read_text()))
    base = {}
    tag = a.model.replace("/", "_").replace(":", "_")
    for l in open(DATA / "runs" / f"{tag}.jsonl"):
        r = json.loads(l)
        if r["variant"] == "base":
            base[r["id"]] = r
    results = {"model": a.model, "claims": {}}
    for iid in a.claims:
        p = items[iid]["payload"]
        ref = fab.get(iid) or {"grades": gold[iid]["grades"], "status": gold[iid]["status"]}
        row = {"claim": p["claim"], "ref_source": "Fable" if iid in fab else "design",
               "ref": {k: ref["grades"].get(k, "none") for k in "123456"}, "ref_status": ref["status"],
               "baseline": {k: (base[iid].get("grades") or {}).get(k, {}).get("verdict", "none") for k in "123456"},
               "baseline_status": base[iid].get("status"), "baseline_seconds": base[iid].get("seconds")}
        for v in a.variants:
            gs, answers, secs = {}, {}, 0.0
            for k, psg in enumerate(p["passages"], 1):
                sents = sentences(psg["text"])
                ans, s, meta = ask(a.model, prompt(v, p["claim"], OPPOSITE[iid], sents))
                secs += s
                g = grade(ans, len(sents))
                answers[str(k)] = {**ans, "grade": g, "sentence": sents[int(ans.get("evidence") or 0) - 1][:160]
                                   if 1 <= int(ans.get("evidence") or 0) <= len(sents) else "", **meta}
                if g != "none":
                    gs[str(k)] = g
            row[v] = {"grades": {k: gs.get(k, "none") for k in "123456"}, "status": status(gs),
                      "seconds": round(secs, 1), "answers": answers}
        results["claims"][iid] = row
        print(iid, "ref", row["ref_status"], "| base", row["baseline_status"],
              *[f"| {v} {row[v]['status']} ({row[v]['seconds']} s)" for v in a.variants], flush=True)
    out = DATA / f"handhold_{tag}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    # summary
    short = {"none": "·", "partially_supports": "p", "supports": "S", "refutes": "R"}
    print("\nper passage (· nothing, p partly, S supports, R contradicts):")
    for iid, r in results["claims"].items():
        line = f"{iid} ref {''.join(short[r['ref'][k]] for k in '123456')}  base {''.join(short[r['baseline'][k]] for k in '123456')}"
        for v in a.variants:
            line += f"  {v} {''.join(short[r[v]['grades'][k]] for k in '123456')}"
        print(line)
    for col in ["baseline", *a.variants]:
        st = sum((r[f"{col}_status"] if col == "baseline" else r[col]["status"]) == r["ref_status"] for r in results["claims"].values())
        P = [(r["ref"][k], (r[col] if col == "baseline" else r[col]["grades"])[k]) for r in results["claims"].values() for k in "123456"]
        same = sum(x == y for x, y in P)
        tp = sum(x != "none" and y != "none" for x, y in P); fl = sum(y != "none" for x, y in P); rl = sum(x != "none" for x, y in P)
        print(f"{col:9} status {st}/{len(results['claims'])}  same grade {same}/{len(P)}  found {tp}/{rl}  flagged {fl} (relevant {tp})")


if __name__ == "__main__":
    main()
