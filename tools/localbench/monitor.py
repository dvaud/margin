"""Live sampler for the bench: heat, power, memory and run progress every 20 s.

Writes data/live.json (the current snapshot, with the last 90 samples for sparklines) and appends
data/telemetry.jsonl. Stops by itself when no `localbench.py run` has been seen for a minute, or after --hours.
With --tick N it prints one short line every N seconds (for a watcher that copies live.json elsewhere).

    python tools/localbench/monitor.py --tick 180
"""
from __future__ import annotations

import argparse
import json
import plistlib
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
THERM_BIN = DATA / "therm"   # a tiny helper printing macOS's thermal state (built once with swiftc, if present)


def _therm_bin() -> Path | None:
    if THERM_BIN.exists():
        return THERM_BIN
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        src = DATA / "therm.swift"
        src.write_text("import Foundation\nprint(ProcessInfo.processInfo.thermalState.rawValue)\n")
        subprocess.run(["swiftc", "-O", str(src), "-o", str(THERM_BIN)], capture_output=True, timeout=120)
    except Exception:
        return None
    return THERM_BIN if THERM_BIN.exists() else None
PRESSURE = {0: "nominal", 1: "moderate", 2: "heavy", 3: "trapping", 4: "sleeping"}
STATE = {0: "nominal", 1: "fair", 2: "serious", 3: "critical"}
SHORT = {"supported": "supported", "partially_supported": "partly", "contradicted": "contradicted",
         "unsupported": "nothing", None: "no answer"}


def sh(*c: str, timeout: int = 10) -> str:
    try:
        return subprocess.run(c, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def machine() -> dict:
    out: dict = {}
    m = re.search(r"(\d+)\s*$", sh("notifyutil", "-g", "com.apple.system.thermalpressurelevel"))
    out["pressure"] = PRESSURE.get(int(m.group(1)), m.group(1)) if m else None
    tb = _therm_bin()
    s = sh(str(tb)).strip() if tb else ""
    out["thermal_state"] = STATE.get(int(s), s) if s.isdigit() else None
    try:
        d = plistlib.loads(subprocess.run(["ioreg", "-rn", "AppleSmartBattery", "-a"], capture_output=True,
                                          timeout=10).stdout)[0]
        pt = d.get("PowerTelemetryData", {})
        out["watts"] = round(pt.get("SystemLoad", 0) / 1000, 1) if pt.get("SystemLoad") else None
        out["on_power"] = bool(d.get("ExternalConnected"))
        out["battery_pct"] = d.get("CurrentCapacity")
    except Exception:
        pass
    m = re.search(r"free percentage: (\d+)%", sh("memory_pressure", "-Q"))
    out["mem_free_pct"] = int(m.group(1)) if m else None
    m = re.search(r"used = ([\d.]+)M", sh("sysctl", "vm.swapusage"))
    out["swap_gb"] = round(float(m.group(1)) / 1024, 2) if m else None
    la = sh("sysctl", "-n", "vm.loadavg").split()
    out["load1"] = float(la[1]) if len(la) > 2 else None
    try:
        from urllib.request import urlopen
        with urlopen("http://127.0.0.1:11434/api/ps", timeout=5) as r:
            ps = json.loads(r.read().decode()).get("models", [])
        out["loaded"] = [{"name": x["name"], "gb": round(x.get("size_vram", x.get("size", 0)) / 1e9, 1)} for x in ps]
    except Exception:
        out["loaded"] = None
    return out


def _jl(p: Path) -> list[dict]:
    rows = []
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass  # a line still being written
    return rows


def runs() -> dict:
    items = {it["id"]: it for it in _jl(DATA / "items.jsonl")}
    gold = {g["id"]: g for g in _jl(DATA / "gold.jsonl")}
    order = [it["id"] for it in _jl(DATA / "items.jsonl")]
    files = [p for p in (DATA / "runs").glob("*.jsonl") if not p.stem.startswith("opus")]
    if not files:
        return {}
    active = max(files, key=lambda p: p.stat().st_mtime)
    rows = _jl(active)
    think = active.stem.endswith("-think")
    variants = ["base", "shuffle"] if think else ["base", "base2", "shuffle", "t07_s1", "t07_s2", "t07_s3", "t07_s4"]
    done = {(r["id"], r["variant"]) for r in rows}
    total = len(order) * len(variants)
    nxt = next(((v, i) for v in variants for i in order if (i, v) not in done), None)
    recent = rows[-40:]
    secs = [r["seconds"] for r in recent if r.get("seconds") and not r.get("error")]
    toks = [r["stats"]["output_tokens"] / r["stats"]["output_seconds"] for r in recent
            if r.get("stats") and r["stats"].get("output_seconds")]
    base = [r for r in rows if r["variant"] == "base" and gold.get(r["id"], {}).get("status")]
    right = [r.get("status") == gold[r["id"]]["status"] for r in base]
    conf = [g["confidence"] for r in base for g in (r.get("grades") or {}).values() if g["confidence"] >= 0.6]
    same = [r for r in rows if r["variant"] != "base"]
    base_status = {r["id"]: r.get("status") for r in base}
    flips = [r.get("status") != base_status[r["id"]] for r in same if r["id"] in base_status]
    left = total - len(done & {(i, v) for v in variants for i in order})
    out = {
        "model": active.stem, "file_updated": active.stat().st_mtime, "done": total - left, "total": total,
        "sec_recent": round(sum(secs) / len(secs), 1) if secs else None,
        "eta_min": round(left * (sum(secs) / len(secs)) / 60) if secs else None,
        "tok_s_recent": round(sum(toks[-10:]) / len(toks[-10:]), 1) if toks else None,
        "right_so_far": round(sum(right) / len(right), 3) if right else None, "base_done": len(right),
        "counting_conf": round(sum(conf) / len(conf), 3) if conf else None,
        "changed_mind": round(sum(flips) / len(flips), 3) if flips else None, "reruns_done": len(flips),
        "errors": sum(bool(r.get("error")) for r in rows), "unusable": sum(not r.get("usable") for r in rows),
        "last": [{"id": r["id"], "variant": r["variant"], "origin": items[r["id"]]["origin"],
                  "answer": SHORT.get(r.get("status"), r.get("status")),
                  "gold": SHORT.get(gold.get(r["id"], {}).get("status")),
                  "right": r.get("status") == gold.get(r["id"], {}).get("status"),
                  "conf": max([g["confidence"] for g in (r.get("grades") or {}).values()] or [None], key=lambda x: x or 0),
                  "seconds": r.get("seconds"), "error": (r.get("error") or "")[:80]} for r in rows[-8:]][::-1],
    }
    if nxt:
        v, i = nxt
        it = items[i]
        out["now"] = {"id": i, "variant": v, "origin": it["origin"], "target": it["payload"]["target"],
                      "claim": it["payload"]["claim"][:300], "gold": SHORT.get(gold.get(i, {}).get("status"))}
    others = {}
    for p in files:
        if p != active:
            rs = _jl(p)
            others[p.stem] = len(rs)
    out["other_runs"] = others
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=20)
    ap.add_argument("--tick", type=int, default=0)
    ap.add_argument("--hours", type=float, default=4)
    a = ap.parse_args()
    hist = [json.loads(x) for x in (DATA / "telemetry.jsonl").read_text().splitlines()[-90:]] \
        if (DATA / "telemetry.jsonl").exists() else []
    t0 = last_tick = time.time()
    idle = 0
    first = True
    while time.time() - t0 < a.hours * 3600:
        m = machine()
        r = runs()
        point = {"t": round(time.time()), **{k: m.get(k) for k in ("pressure", "thermal_state", "watts", "mem_free_pct",
                                                                    "swap_gb", "load1")},
                 "tok_s": r.get("tok_s_recent"), "model": r.get("model"),
                 "model_gb": max([x["gb"] for x in (m.get("loaded") or [])] or [None], key=lambda x: x or 0)}
        hist = (hist + [point])[-90:]
        with (DATA / "telemetry.jsonl").open("a") as f:
            f.write(json.dumps(point) + "\n")
        running = bool(sh("pgrep", "-f", "localbench.py run").strip())
        idle = 0 if running else idle + 1
        snap = {"t": round(time.time()), "running": running, "machine": m, "run": r, "history": hist}
        tmp = DATA / "live.json.tmp"
        tmp.write_text(json.dumps(snap))
        tmp.replace(DATA / "live.json")
        if a.tick and (time.time() - last_tick >= a.tick or idle >= 3 or first):
            last_tick, first = time.time(), False
            # what the page shows next to each figure: the change since the previous update it got
            summary = {"t": snap["t"], "model": r.get("model"), "model_gb": point["model_gb"],
                       **{k: r.get(k) for k in ("done", "right_so_far", "counting_conf", "changed_mind", "sec_recent",
                                                "tok_s_recent", "errors", "unusable")},
                       **{k: m.get(k) for k in ("watts", "mem_free_pct", "swap_gb", "load1")}}
            prev_file = DATA / "push_prev.json"
            prev = json.loads(prev_file.read_text()) if prev_file.exists() else None
            (DATA / "push.json").write_text(json.dumps({**snap, "prev": prev}))
            prev_file.write_text(json.dumps(summary))
            print(f"tick {r.get('model')} {r.get('done')}/{r.get('total')} pressure={m.get('pressure')} "
                  f"W={m.get('watts')} free={m.get('mem_free_pct')}% running={running}", flush=True)
        if idle >= 3:
            print("bench stopped; monitor ends", flush=True)
            return
        time.sleep(a.every)


if __name__ == "__main__":
    main()
