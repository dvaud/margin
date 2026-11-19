"""Mini test 2: yes/no questions with the model's own probability of "yes" (Ollama logprobs), per passage.
Scores: P(yes | says the claim), P(yes | says the opposite), P(yes | is about the claim's subject)."""
import json, math, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
HERE = Path(__file__).resolve().parent; DATA = HERE / "data"
sys.path.insert(0, str(HERE))
import review as rv
from handhold import CLAIMS, OPPOSITE

MODEL = sys.argv[1] if len(sys.argv) > 1 else "ifm/k2-horizon:0.9b"
SYS = "You read one passage and answer one question about it with Yes or No. Use only the passage."


def p_yes(question: str, passage: str) -> tuple[float, float]:
    body = {"model": MODEL, "stream": False, "think": False, "logprobs": True, "top_logprobs": 10, "keep_alive": "5m",
            "options": {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 1},
            "messages": [{"role": "system", "content": SYS},
                         {"role": "user", "content": f"PASSAGE:\n{passage}\n\nQUESTION: {question}\nAnswer Yes or No."}]}
    t = time.time()
    with urlopen(Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                         headers={"Content-Type": "application/json"}), timeout=120) as r:
        d = json.loads(r.read().decode())
    top = d["logprobs"][0]["top_logprobs"]
    y = sum(math.exp(t_["logprob"]) for t_ in top if t_["token"].strip().lower().startswith("yes"))
    n = sum(math.exp(t_["logprob"]) for t_ in top if t_["token"].strip().lower().startswith("no"))
    return (y / (y + n) if y + n else 0.5), time.time() - t


def auc(pos, neg):
    if not pos or not neg: return None
    return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))


items = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "items.jsonl")}
gold = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "gold.jsonl")}
fab = rv._gold_from(rv.reviewer_rows("fable"), json.loads((DATA / "review_cards.json").read_text()))
rows, secs = [], 0.0
for iid in CLAIMS:
    p = items[iid]["payload"]; ref = fab.get(iid) or {"grades": gold[iid]["grades"]}
    for k, psg in enumerate(p["passages"], 1):
        a, s1 = p_yes(f"Does this passage say that {p['claim'][0].lower() + p['claim'][1:]}", psg["text"])
        b, s2 = p_yes(f"Does this passage say that {OPPOSITE[iid][0].lower() + OPPOSITE[iid][1:]}", psg["text"])
        c, s3 = p_yes(f"Is this passage about the same subject as this claim: {p['claim']}", psg["text"])
        secs += s1 + s2 + s3
        rows.append({"id": iid, "p": k, "ref": ref["grades"].get(str(k), "none"), "claim": a, "opp": b, "about": c})
rel = lambda r: r["ref"] != "none"
print(f"{len(rows)} passages, {secs:.0f} s in all ({secs / len(rows):.2f} s per passage for 3 questions)")
for key in ("claim", "about", "opp"):
    print(f"P(yes) for '{key}': relevant mean {sum(r[key] for r in rows if rel(r)) / sum(map(rel, rows)):.2f}, "
          f"not relevant mean {sum(r[key] for r in rows if not rel(r)) / sum(not rel(r) for r in rows):.2f}, "
          f"AUC (ranks relevant above not relevant) {auc([r[key] for r in rows if rel(r)], [r[key] for r in rows if not rel(r)]):.2f}")
pos = [r["claim"] - r["opp"] for r in rows if r["ref"] in ("supports", "partially_supports")]
neg = [r["claim"] - r["opp"] for r in rows if r["ref"] == "refutes"]
print("direction: claim-minus-opposite for supporting passages", [round(x, 2) for x in pos][:12], "... for contradicting", [round(x, 2) for x in neg])
# reading order: within each claim, are relevant passages ranked first by P(yes|claim)?
hits = []
for iid in CLAIMS:
    rs = sorted([r for r in rows if r["id"] == iid], key=lambda r: -r["claim"]); n = sum(map(rel, rs))
    if n: hits.append((iid, n, sum(map(rel, rs[:n]))))
print("reading order: relevant passages in the top-n of each claim (n = number relevant):", hits,
      f"→ {sum(h[2] for h in hits)}/{sum(h[1] for h in hits)} (random would get about {sum(h[1] * h[1] / 6 for h in hits):.1f})")
json.dump(rows, open(DATA / f"handhold_lp_{MODEL.replace('/', '_').replace(':', '_')}.json", "w"), indent=1)
