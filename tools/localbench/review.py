"""Blind manual review: one card per distinct judgement (a model's counting grades on one claim).

    python tools/localbench/review.py cards     # data/review_cards.json (with the models) + data/review_page.json (blind)

Identical judgements of several models on the same claim become one card; the mapping card -> models stays in
review_cards.json and never goes into the page. The order is random but fixed (seeded), with cards of the same claim
kept apart, so a reviewer can resume on any device.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
THR = 0.6
SOURCES = {"qwen3.5_4b": "base", "ifm_k2-horizon_0.9b": "base", "opus-A": "base", "sonnet-A": "base"}


def _jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def status_of(grades: dict) -> str:
    v = {g["verdict"] for g in grades.values()}
    return ("supported" if "supports" in v else "partially_supported" if "partially_supports" in v
            else "contradicted" if "refutes" in v else "unsupported")


def cards(args=None) -> None:
    items = {it["id"]: it for it in _jl(DATA / "items.jsonl")}
    by_item: dict[str, dict] = {}
    for tag, variant in SOURCES.items():
        for r in _jl(DATA / "runs" / f"{tag}.jsonl"):
            if r["variant"] != variant:
                continue
            g = {k: v for k, v in (r.get("grades") or {}).items() if v["confidence"] >= THR}
            key = tuple(sorted((k, v["verdict"]) for k, v in g.items()))
            slot = by_item.setdefault(r["id"], {}).setdefault(key, {"models": [], "grades": {}, "failed": False})
            slot["models"].append(tag)
            for k, v in g.items():   # keep each model's quote: shown together on the passage
                slot["grades"].setdefault(k, {"verdict": v["verdict"], "quotes": []})
                if v["quote"] not in slot["grades"][k]["quotes"]:
                    slot["grades"][k]["quotes"].append(v["quote"])
            if r.get("error") or not r.get("json_ok", True):
                slot["failed"] = True
    # Which claims can move the ranking: the real ones where the models disagree, plus controls where a Claude
    # model departed from the design. One card per claim: the reviewer's answer becomes the human gold for that
    # claim, and every model's answer on it is re-scored against it. The judgement shown is one model's, chosen at
    # random but evenly across the four models, so no model gets more anchoring than another.
    status = {iid: {m: status_of({k: {"verdict": v} for k, v in key}) for key, s in g.items() for m in s["models"]}
              for iid, g in by_item.items()}
    chosen = [i for i in sorted(by_item) if
              (items[i]["origin"] == "real" and len(set(status[i].values())) > 1) or
              (items[i]["origin"] != "real" and any(status[i].get(m) != items[i]["expect"] for m in ("opus-A", "sonnet-A")))]
    rng0 = random.Random(7)
    models = list(SOURCES)
    shown = (models * (len(chosen) // len(models) + 1))[:len(chosen)]
    rng0.shuffle(shown)
    out, blind = [], []
    for iid, m in zip(chosen, shown):
        key, s = next((k, s) for k, s in by_item[iid].items() if m in s["models"])
        cid = "c" + hashlib.sha1(f"{iid}|{key}".encode()).hexdigest()[:8]
        out.append({"card": cid, "item": iid, "shown_model": m, "same_answer": s["models"], "grades": s["grades"],
                    "status": status_of(s["grades"]), "failed": s["failed"],
                    "all": {mm: [kk, ss["grades"]] for kk, ss in by_item[iid].items() for mm in ss["models"]}})
        blind.append({"card": cid, "item": iid,
                      "grades": {k: {"verdict": v["verdict"], "quotes": v["quotes"]} for k, v in s["grades"].items()},
                      "status": status_of(s["grades"])})
    by_item = {i: by_item[i] for i in chosen}
    # random order, cards of one claim at least 6 places apart where possible
    rng = random.Random(2026)
    rng.shuffle(blind)
    order, pool = [], blind[:]
    while pool:
        recent = {c["item"] for c in order[-6:]}
        pick = next((c for c in pool if c["item"] not in recent), pool[0])
        pool.remove(pick)
        order.append(pick)
    claims = {}
    for iid in sorted(by_item):
        p = items[iid]["payload"]
        claims[iid] = {"target": p["target"], "target_description": p["target_description"], "claim": p["claim"],
                       "passages": [{"title": x.get("title"), "page": x.get("page"), "text": x["text"]} for x in p["passages"]]}
    (DATA / "review_cards.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    (DATA / "review_page.json").write_text(json.dumps({"cards": order, "claims": claims}, ensure_ascii=False))
    per = {}
    for c in out:
        per[c["shown_model"]] = per.get(c["shown_model"], 0) + 1
    print(f"{len(out)} cards, one per claim; judgement shown from: {per}; "
          f"page data {len(json.dumps({'cards': order, 'claims': claims})) // 1024} KB")





# ---------------------------------------------------------------------------------------------------- scoring
MODELS = ["qwen3.5_4b", "ifm_k2-horizon_0.9b", "opus-A", "opus-B", "sonnet-A", "sonnet-B"]
GR = ["none", "partially_supports", "supports", "refutes"]


def reviewer_rows(name: str) -> dict:
    """{card: {decision, grades, note}} for 'you' (the review page's export) or 'fable'."""
    if name.startswith("free-"):
        return free_rows(name[5:])[0]
    if name == "you":
        rows = [json.loads(p.read_text()) for p in sorted((DATA / "human" / "reviews").glob("*.json"))]
    elif name != "fable":   # another reviewer's pasted answers: data/review_<name>.jsonl (a first line may name it)
        rows = [r for r in _jl(DATA / f"review_{name}.jsonl") if r.get("card")]
    else:   # Fable's final answer: round 1, then its reconsidered cards (rounds 2 and 3) on top
        rows = _jl(DATA / "review_fable.jsonl")
        later = {r["card"]: r for n in (2, 3) for r in _jl(DATA / f"review_fable_round{n}.jsonl")}
        rows = [{**r, **({"grades": later[r["card"]]["grades"], "status": later[r["card"]]["status"]} if r["card"] in later else {})}
                for r in rows]
    return {r["card"]: r for r in rows if r.get("card")}


def _gold_from(rows: dict, cards: list[dict]) -> dict:
    by_card = {c["card"]: c for c in cards}
    out = {}
    for cid, r in rows.items():
        if r.get("decision") == "unsure" or cid not in by_card:
            continue
        g = {str(k): v for k, v in (r.get("grades") or {}).items() if v in GR[1:]}
        out[by_card[cid]["item"]] = {"status": status_of({k: {"verdict": v} for k, v in g.items()}), "grades": g}
    return out


def score_reviews(args=None) -> None:
    sys.path.insert(0, str(HERE))
    import localbench as lb

    items = {it["id"]: it for it in _jl(DATA / "items.jsonl")}
    gold = {g["id"]: g for g in _jl(DATA / "gold.jsonl")}
    cards = json.loads((DATA / "review_cards.json").read_text())
    extra = sorted(p.stem[len("review_"):] for p in DATA.glob("review_*.jsonl")
                   if not p.stem.startswith(("review_fable", "review_cards")))
    gates = {}
    for p in sorted((DATA / "free").glob("review_*.jsonl")) if (DATA / "free").exists() else []:
        n = p.stem[len("review_"):]
        gates[f"free-{n}"] = free_rows(n)[1]
    names = ["fable", "you", *extra, *[n for n, g in gates.items() if g["passed"]]]
    reviewers = {n: _gold_from(reviewer_rows(n), cards) for n in names}
    # where both reviewed a claim and gave the same grades
    # where you and Fable give the claim the same status (passage grades: Fable's)
    both = {i: reviewers["fable"][i] for i, g in reviewers["you"].items()
            if i in reviewers["fable"] and reviewers["fable"][i]["status"] == g["status"]}
    reviewers["both"] = both
    keys = ["status_acc", "grounded_kappa", "counting_mean_conf", "counting_precision", "counting_overconfidence",
            "passage_recall", "false_positives_counting", "ece_lenient", "grade_acc_lenient"]
    out = {"reviewed": {n: len(g) for n, g in reviewers.items()}, "total_cards": len(cards), "by": {}, "gates": gates}
    for name, hg in reviewers.items():
        if not hg:
            continue
        ids = sorted(hg)
        before = {i: gold[i] for i in ids}
        res = {"ids": ids, "models": {}}
        for tag in MODELS:
            b = lb.score(tag, items, before)
            a = lb.score(tag, items, hg)
            res["models"][tag] = {"before": {k: b.get(k) for k in keys}, "after": {k: a.get(k) for k in keys}}
        # the Opus gold itself, judged by the reviewer
        res["gold_status_agree"] = sum(gold[i]["status"] == hg[i]["status"] for i in ids) / len(ids)
        res["gold_grade_agree"] = sum((gold[i]["grades"] or {}) == hg[i]["grades"] for i in ids) / len(ids)
        # how the reviewer moved the Opus gold's grades, passage by passage (6 per claim)
        tr = {a: {b: 0 for b in GR} for a in GR}
        for i in ids:
            for k in map(str, range(1, 7)):
                tr[(gold[i]["grades"] or {}).get(k, "none")][hg[i]["grades"].get(k, "none")] += 1
        res["transitions_gold"] = tr
        # the status moves, claim by claim
        res["claims"] = [{"id": i, "claim": items[i]["payload"]["claim"], "target": items[i]["payload"]["target"],
                          "gold": gold[i]["status"], "reviewer": hg[i]["status"]} for i in ids]
        out["by"][name] = res
    # the two reviewers against each other
    y, f = reviewers["you"], reviewers["fable"]
    common = sorted(set(y) & set(f))
    if common:
        out["you_vs_fable"] = {"claims": len(common),
                               "status": sum(y[i]["status"] == f[i]["status"] for i in common) / len(common),
                               "grades": sum(y[i]["grades"] == f[i]["grades"] for i in common) / len(common),
                               "passages": sum(y[i]["grades"].get(k, "none") == f[i]["grades"].get(k, "none")
                                               for i in common for k in map(str, range(1, 7))) / (6 * len(common))}
    # the three readings on the claims you judged: how often each uses each grade, and pairwise passage agreement
    if common:
        P6 = [(i, k) for i in common for k in map(str, range(1, 7))]
        rd = {"Opus gold": lambda i, k: (gold[i]["grades"] or {}).get(k, "none"),
              "Fable": lambda i, k: f[i]["grades"].get(k, "none"), "You": lambda i, k: y[i]["grades"].get(k, "none")}
        for n in [x for x in names if x not in ("fable", "you")]:
            if all(i in reviewers[n] for i in common):
                rd[n.replace("free-", "").capitalize()] = (lambda n: lambda i, k: reviewers[n][i]["grades"].get(k, "none"))(n)
        out["readings"] = {"claims": len(common), "passages": len(P6),
                           "counts": {n: {g: sum(fn(i, k) == g for i, k in P6) for g in GR} for n, fn in rd.items()},
                           "pairs": {f"{a} · {b}": sum(rd[a](i, k) == rd[b](i, k) for i, k in P6) / len(P6)
                                     for a, b in (("You", "Fable"), ("You", "Opus gold"), ("Fable", "Opus gold"),
                                                  *[(x, "Fable") for x in rd if x not in ("You", "Fable", "Opus gold")])}}
    # every reviewer against Fable and the Opus gold, on all the claims both judged, passage by passage
    out["pairs_all"] = {}
    for n in names:
        if n == "fable" or not reviewers[n]:
            continue
        for ref, get in (("Fable", lambda i, k: f.get(i, {}).get("grades", {}).get(k, "none")),
                         ("Opus gold", lambda i, k: (gold[i]["grades"] or {}).get(k, "none"))):
            ids = [i for i in reviewers[n] if ref != "Fable" or i in f]
            out["pairs_all"][f"{n} · {ref}"] = {
                "claims": len(ids),
                "status": sum(reviewers[n][i]["status"] == (f[i]["status"] if ref == "Fable" else gold[i]["status"]) for i in ids) / len(ids),
                "passages": sum(reviewers[n][i]["grades"].get(k, "none") == get(i, k) for i in ids for k in map(str, range(1, 7))) / (6 * len(ids))}
    out["pairs_all"]["fable · Opus gold"] = {"claims": len(f), "status": sum(f[i]["status"] == gold[i]["status"] for i in f) / len(f),
        "passages": sum(f[i]["grades"].get(k, "none") == (gold[i]["grades"] or {}).get(k, "none") for i in f for k in map(str, range(1, 7))) / (6 * len(f))}
    r1 = {r["card"]: r for r in _jl(DATA / "review_fable.jsonl")}
    fin = reviewer_rows("fable")
    out["fable_rounds"] = {"changed_passages": sum(r1[c]["grades"].get(k, "none") != fin[c]["grades"].get(k, "none")
                                                   for c in r1 for k in map(str, range(1, 7))),
                           "changed_status": sum(r1[c]["status"] != fin[c]["status"] for c in r1)}
    # per reviewer: agreement with the judgement shown, by the model that gave it (unblinded here)
    # whether a reviewer checked the quotes: judgements shown whose quote is not in the passage it grades
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    from margin.textutil import find_quote
    claims = json.loads((DATA / "review_page.json").read_text())["claims"]
    bad = {c["card"] for c in cards for k, g in c["grades"].items()
           if not any(find_quote(claims[c["item"]]["passages"][int(k) - 1]["text"], q) for q in g["quotes"])}
    out["bad_quote_cards"] = len(bad)
    out["meta"] = {}
    for name in names:
        rows = reviewer_rows(name)
        decided = [r for r in rows.values() if r.get("decision") in ("agree", "changed", "free")]
        out["meta"][name] = {"decided": len(decided), "agreed": sum(r["decision"] == "agree" for r in decided),
                             "unsure": sum(r.get("decision") == "unsure" for r in rows.values()),
                             "accepted_bad_quotes": sum(1 for c in bad if rows.get(c, {}).get("decision") == "agree"),
                             "saw_bad_quotes": sum(1 for c in bad if rows.get(c, {}).get("decision") in ("agree", "changed"))}
    for name in names:
        rows = reviewer_rows(name)
        per = {}
        for c in cards:
            r = rows.get(c["card"])
            if r and r.get("decision") in ("agree", "changed"):
                per.setdefault(c["shown_model"], []).append(r["decision"] == "agree")
        if name in out["by"]:
            out["by"][name]["agreed_with_shown"] = {m: [sum(v), len(v)] for m, v in per.items()}
    (DATA / "review_scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({"reviewed": out["reviewed"], "you_vs_fable": out.get("you_vs_fable")}))


# ---------------------------------------------------------------------------------------------------- judgement-free packet
FREE_CONTROLS = {"i13": "planted", "i33": "planted", "i02": "flip", "i12": "irrel"}


def packet_free(args=None) -> None:
    """A packet with no AI judgement: claims and passages only, the 30 review claims plus 4 known-answer controls,
    shuffled, under opaque ids. The key (id -> claim) stays in data/review_free_key.json."""
    items = {it["id"]: it for it in _jl(DATA / "items.jsonl")}
    cards = json.loads((DATA / "review_cards.json").read_text())
    entries = [{"item": c["item"], "control": None} for c in cards]
    entries += [{"item": i, "control": kind} for i, kind in FREE_CONTROLS.items()]
    random.Random(4242).shuffle(entries)
    key, parts = {}, []
    for n, e in enumerate(entries, 1):
        qid = f"q{n:02d}"
        it = items[e["item"]]
        key[qid] = {"item": e["item"], "control": e["control"], "expect": it.get("expect"),
                    "planted_passage": it.get("planted_passage")}
        p = it["payload"]
        s = [f"=== CLAIM {qid} ===", f"CLAIM (SDG target {p['target']}: {p['target_description']}):", p["claim"], ""]
        for i, x in enumerate(p["passages"], 1):
            s.append(f"P{i} | {x.get('title') or 'untitled'}{', page ' + str(x['page']) if x.get('page') else ''}\n{x['text']}\n")
        parts.append("\n".join(s))
    rules = (DATA / "system_prompt.txt").read_text().strip()
    head = (f"REVIEW PACKET: {len(entries)} claims. Each claim is about green hydrogen and an SDG target, with six source "
            "passages (P1-P6). Grade every passage yourself.\n\n=== THE GRADING RULES ===\n")
    (DATA / "review_packet_free.txt").write_text(head + rules + "\n\n=== THE CLAIMS ===\n\n" + "\n\n".join(parts))
    (DATA / "review_free_key.json").write_text(json.dumps(key, indent=1))
    print(f"{len(entries)} claims ({len(FREE_CONTROLS)} controls) -> review_packet_free.txt "
          f"({(DATA / 'review_packet_free.txt').stat().st_size // 1000} KB)")


def free_rows(name: str):
    """A judgement-free review (data/free/review_<name>.jsonl) as card rows, plus its gate: controls and quotes."""
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    from margin.textutil import find_quote

    key = json.loads((DATA / "review_free_key.json").read_text())
    items = {it["id"]: it for it in _jl(DATA / "items.jsonl")}
    card_of = {c["item"]: c["card"] for c in json.loads((DATA / "review_cards.json").read_text())}
    rows, quotes, ctl = {}, [0, 0], []
    for r in _jl(DATA / "free" / f"review_{name}.jsonl"):
        q = r.get("claim")
        if q not in key:
            continue
        k = key[q]
        ps = items[k["item"]]["payload"]["passages"]
        grades = {}
        for pk, g in (r.get("grades") or {}).items():
            grade = g.get("grade") if isinstance(g, dict) else g
            if grade not in GR[1:]:
                continue
            grades[str(pk)] = grade
            quotes[1] += 1
            quote = g.get("quote") if isinstance(g, dict) else None
            if quote and 1 <= int(pk) <= len(ps) and find_quote(ps[int(pk) - 1]["text"], quote):
                quotes[0] += 1
        st = status_of({x: {"verdict": v} for x, v in grades.items()})
        if k["control"]:
            if k["control"] == "planted":
                ok = grades.get(str(k["planted_passage"])) in ("supports", "partially_supports")
            else:
                ok = st == k["expect"]
            ctl.append({"claim": q, "kind": k["control"], "ok": ok})
        elif k["item"] in card_of:
            rows[card_of[k["item"]]] = {"card": card_of[k["item"]], "decision": "free", "grades": grades,
                                        "status": st, "note": r.get("note", "")}
    gate = {"controls_ok": sum(c["ok"] for c in ctl), "controls": len(ctl), "quotes_found": quotes[0],
            "quotes": quotes[1], "claims": len(rows)}
    gate["passed"] = (len(ctl) == len(FREE_CONTROLS) and gate["controls_ok"] >= 3
                      and (quotes[1] == 0 or quotes[0] / quotes[1] >= 0.9) and len(rows) >= 25)
    gate["control_detail"] = ctl
    return rows, gate


if __name__ == "__main__":
    {"cards": cards, "score": score_reviews, "packet": packet_free}[sys.argv[1]]()
