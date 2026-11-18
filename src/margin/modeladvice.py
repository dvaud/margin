"""0.18.0rc2 (M8), I6 (tiers): which local model THIS computer gets.

I6: a researcher never picks a model. Margin reads the computer (memory, a graphics card's memory, free disk space) and
picks one of three tiers itself; the person only presses Set up (no model is downloaded or started before that click):

| Computer | Model | What it does |
| Small (about 8 GB, or no graphics card) | `SMALL_MODEL` (K2 Horizon 0.9B) | Explorer only: points at sentences |
| 16 GB | `MEDIUM_MODEL` (Qwen 3.5 4B) | Suggestions only |
| about 24 GB or more | `LARGE_MODEL` (Qwen 3.5 9B) | Suggestions only (not measured yet) |

Each tag is one constant here: switching to the GGUF builds (`qwen3.5:4b-q4_K_M`, which run on llama.cpp with flat
memory) once they are benched is a one-line change. Model names show only under Settings → Technical.

What a model needs of the memory (`_need`), from the bench of 16 November 2026 (I6 research, section 2): its file, a
load overhead measured beyond the context (the vision tower of Qwen 3.5, say), its context (`num_ctx` tokens at
`llm.KV_BYTES_PER_TOKEN`) and, on Ollama's MLX runner (Apple silicon), the prompt cache it keeps growing until the
memory guard (`llm.OllamaBackend._guard`) frees it: `growth()`. Without the guard that cache grows to 8 GiB.

`computer()` reads the facts (cheap, kept for a minute: the page asks every few seconds); `advise()` decides and does no
reading, so it can be tested with made-up computers."""
from __future__ import annotations

import os
import shutil
import subprocess
import time

GB = 1 << 30
# the context the advice reckons with when a model says none (the app's smallest working length)
CONTEXT_TOKENS = 8192
# a model is offered when what it needs is at most this share of the memory it would run in ("room to spare": the system,
# the browser and the documents need the rest); the recommended one stays within COMFORT, a larger one may go to TIGHT
COMFORT = 0.5
TIGHT = 0.65
GPU_SHARE = 0.9          # of a graphics card's own memory a model may take
DISK_MARGIN = 2 * GB     # free space to leave after the download
SMALL_DISK_SHARE = 1.2   # a download is unpacked beside the files Ollama already holds

# I6: the three tiers' models, one constant each (see above). After the GGUF builds are benched (roadmap I6, "Left to
# try"), MEDIUM_MODEL may become "qwen3.5:4b-q4_K_M" and LARGE_MODEL "qwen3.5:9b-q4_K_M": change only these lines
# (and `mlx` below to False for them).
SMALL_MODEL = "ifm/k2-horizon:0.9b"
MEDIUM_MODEL = "qwen3.5:4b"
LARGE_MODEL = "qwen3.5:9b"
MLX_CACHE = 8 * GB       # what that cache grows to without the guard (Ollama's fixed budget, ollama/ollama#18131)

# The tiers, smallest first. `bytes`: the file Ollama lists (/api/tags, 18 November 2026); `overhead`: memory measured
# beyond the file and the context; `num_ctx`: the context the tier runs at; `mlx`: on Apple silicon this build runs on
# Ollama's MLX runner (a safetensors build), else on llama.cpp; `role`: what its answers are for. `good` is for a
# researcher who does not program, and names no model.
CHAT = (
    {"name": SMALL_MODEL, "tier": "small", "bytes": int(1.07 * GB), "overhead": 0, "num_ctx": 8192, "mlx": False,
     "label": "small", "role": "explorer", "form": "point",
     "good": "Explorer: it points at the sentences that bear on your hypothesis and sorts the reading order. You "
             "judge every excerpt yourself."},
    {"name": MEDIUM_MODEL, "tier": "medium", "bytes": int(3.7 * GB), "overhead": int(0.4 * GB), "num_ctx": 16384,
     "mlx": True, "label": "medium", "role": "suggestions", "form": "check",
     "good": "Suggestions: it marks the sentences that bear on your hypothesis and suggests a judgement for each "
             "excerpt. You decide each one."},
    {"name": LARGE_MODEL, "tier": "large", "bytes": int(7.11 * GB), "overhead": int(1.0 * GB), "num_ctx": 16384,
     "mlx": True, "label": "large", "role": "suggestions", "form": "check",
     "good": "Suggestions, read more carefully (not measured yet): it suggests a judgement for each excerpt. You "
             "decide each one."},
)
TIER_WORDS = {"small": "The small local model", "medium": "The local model", "large": "The larger local model"}
EMBED = (
    {"name": "nomic-embed-text", "bytes": int(0.3 * GB), "label": "small",
     "good": "Search by meaning for documents in English. Small and quick."},
    {"name": "bge-m3", "bytes": int(1.2 * GB), "label": "medium",
     "good": "Search by meaning across many languages (Hungarian, Dutch, German and more), more precise; a bigger download."},
)
WHAT_IS_A_MODEL = ("A model is the program that does the reading. It is one large file kept on this computer, so "
                   "nothing you read with it leaves the computer. The local model only suggests: you judge every "
                   "excerpt it reads, and only your judgements count.")


def tier_of(model: str | None) -> dict | None:
    """The tier whose model this is (a tag with or without `:latest`), or None for a model outside the tiers."""
    name = (model or "").strip()
    full = name if ":" in name else f"{name}:latest"
    return next((t for t in CHAT if t["name"] in (name, full)), None)


def answer_form(model: str | None) -> str:
    """I6: how a local model answers a check: "point" (the small tier: numbered sentences, Margin cuts the quote, no
    judgement; K2's check answers ran past their length limit) or "check" (the judgements of check-v5)."""
    t = tier_of(model)
    if t is not None:
        return t["form"]
    return "point" if (model or "").startswith("ifm/k2-horizon") else "check"


def growth(model: dict, facts: dict) -> int:
    """What the runner adds over a long run: on Apple silicon an MLX build's prompt cache up to the guard's threshold
    (the guard frees it there; I6 research section 2), nothing on llama.cpp."""
    from .llm import GUARD_GROW_MIN, GUARD_GROW_SHARE

    if not (model.get("mlx") and facts.get("unified")):
        return 0
    return max(GUARD_GROW_MIN, int(GUARD_GROW_SHARE * (facts.get("memory") or 0)))


def computer(home_dir: str | None = None) -> dict:
    """What this computer has: {"memory", "disk_free", "system", "unified", "gpu"} (bytes; None when it cannot be read).
    `unified`: a Mac with Apple silicon, where the graphics memory is the same memory. `gpu`: the memory of the largest
    NVIDIA card where `nvidia-smi` is installed (asked once a minute, quickly), else None."""
    now = time.time()
    hit = _FACTS.get(home_dir)
    if hit and now - hit[0] < 60:
        return dict(hit[1])
    from . import llm
    from .installation import system

    name = system()
    where = home_dir or os.path.expanduser("~")
    try:
        free = shutil.disk_usage(where).free
    except OSError:
        free = None
    facts = {"memory": llm.total_memory(), "disk_free": free, "system": name,
             "unified": name == "mac" and _machine() in ("arm64", "aarch64"), "gpu": _gpu_memory(name)}
    _FACTS[home_dir] = (now, facts)
    return dict(facts)


_FACTS: dict = {}


def _machine() -> str:
    import platform

    return platform.machine().lower()


def _gpu_memory(system: str) -> int | None:
    """The memory of the largest NVIDIA graphics card, only where `nvidia-smi` is on the computer (Windows, Linux)."""
    if system == "mac" or not shutil.which("nvidia-smi"):
        return None
    from .procs import no_window

    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=3, **no_window()).stdout
        mib = [int(x) for x in out.split() if x.strip().isdigit()]
        return max(mib) * (1 << 20) if mib else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _need(model: dict, use: str, facts: dict | None = None) -> int:
    """What running the model asks of the memory: its size, and for a chat model its load overhead, the memory its
    context takes (at the tier's own context length) and what its runner grows by over a long run (`growth`)."""
    from .llm import KV_BYTES_PER_TOKEN

    if use != "chat":
        return model["bytes"]
    return (model["bytes"] + model.get("overhead", 0) + model.get("num_ctx", CONTEXT_TOKENS) * KV_BYTES_PER_TOKEN
            + growth(model, facts or {}))


def _gb(n: int) -> str:
    n = n / GB
    return f"{round(n)} GB" if n >= 10 or abs(n - round(n)) < 0.05 else f"{n:.1f} GB"


def _size_text(n: int) -> str:
    return f"about {_gb(n)}"


def _fit(model: dict, use: str, facts: dict) -> dict | None:
    """How `model` would run here, or None when it does not fit the memory or the disk with room to spare:
    {"where": "graphics card" | "memory", "share": how much of that memory it takes}."""
    mem, gpu, disk = facts.get("memory"), facts.get("gpu"), facts.get("disk_free")
    if disk is not None and disk < model["bytes"] * SMALL_DISK_SHARE + DISK_MARGIN:
        return None
    need = _need(model, use, facts)
    options = []
    if gpu and need <= GPU_SHARE * gpu:
        options.append({"where": "graphics card", "share": need / gpu})
    if mem is None:
        return options[0] if options else {"where": "memory", "share": 0.0}   # cannot tell: not refused (the app checks again at the start)
    if need <= TIGHT * mem:
        options.append({"where": "memory", "share": need / mem})
    # the graphics card when the model sits comfortably in it, else wherever it takes the smaller share
    return next((o for o in options if o["share"] <= COMFORT), min(options, key=lambda o: o["share"], default=None))


def _speed(model: dict, use: str, facts: dict, fit: dict) -> tuple[str, str]:
    """(how quick, in words): quick on a graphics card or on a Mac's own memory, else by the size of the model."""
    if use == "embed":
        return "quick", "Quick: it only has to read each passage once, when search by meaning is set up."
    if fit["where"] == "graphics card":
        return "quick", "Quick: it runs on your graphics card. An answer takes seconds."
    if facts.get("unified"):
        big = model["bytes"] > 8 * GB
        return ("fair", "Fair: about half a minute for an answer on this Mac.") if big else \
            ("quick", "Quick: it runs on this Mac's own memory. A check takes a few seconds.")
    gb = model["bytes"] / GB
    if gb <= 2:
        return "fair", "Fair: it runs on the processor, about half a minute for an answer."
    if gb <= 3:
        return "fair", "Fair: it runs on the processor, about a minute for an answer."
    return "slow", "Slow: it runs on the processor, a few minutes for a long answer. Fine for a check you leave running."


def _option(model: dict, use: str, role: str, facts: dict, fit: dict) -> dict:
    speed, speed_text = _speed(model, use, facts, fit)
    share = fit["share"]
    out = {"name": model["name"], "use": use, "role": role, "size": _size_text(model["bytes"]), "bytes": model["bytes"],
           "speed": speed, "speed_text": speed_text, "good_for": model["good"], "tight": share > COMFORT,
           "note": ("It takes most of this computer's memory: close other programs while it works."
                    if share > COMFORT else "")}
    if use == "chat":   # I6: the tier, what its answers are for, and what it needs of the memory here
        out.update(tier=model["tier"], answers=model["role"], words=TIER_WORDS[model["tier"]],
                   need=_need(model, use, facts), num_ctx=model["num_ctx"],
                   runner="mlx" if model.get("mlx") and facts.get("unified") else "llamacpp")
    return out


def no_graphics(facts: dict) -> bool:
    """A computer without a graphics card a model can use: not Apple silicon, and no NVIDIA card's memory read (an
    Intel Mac included). Such a computer gets the small tier (I6): a larger model on the processor alone takes minutes
    a check."""
    return not facts.get("unified") and not facts.get("gpu")


def _ladder(rungs: tuple, use: str, facts: dict) -> dict:
    """The recommended rung and its neighbours, from the ones that fit."""
    fits = [(m, _fit(m, use, facts)) for m in rungs]
    ok = [(i, m, f) for i, (m, f) in enumerate(fits) if f]
    if not ok:
        need = rungs[0]["bytes"]
        disk, mem = facts.get("disk_free"), facts.get("memory")
        if disk is not None and disk < need * SMALL_DISK_SHARE + DISK_MARGIN:
            why = (f"There is not enough free disk space for even the smallest model ({_size_text(need)}): this computer "
                   f"has {_gb(disk)} free. Free some space and try again.")
        else:
            why = (f"This computer has {_gb(mem or 0)} of memory, which is too little for a local model that reads "
                   "well. Use Claude instead (Settings → AI), or a computer with more memory.")
        return {"pick": None, "smaller": None, "larger": None, "options": [], "reason": why}
    comfy = [t for t in ok if t[2]["share"] <= COMFORT] or ok[:1]
    pi, pm, pf = comfy[0] if use == "embed" else comfy[-1]   # search by meaning starts with the small one
    if use == "chat" and (no_graphics(facts) or (facts.get("memory") is None and not facts.get("gpu"))):
        # I6: no graphics card, or memory that cannot be read: the small tier (the others stay offered under Technical)
        pi, pm, pf = ok[0]
    pick = _option(pm, use, "recommended", facts, pf)
    smaller = next((_option(m, use, "smaller", facts, f) for i, m, f in reversed(ok) if i < pi), None)
    larger = next((_option(m, use, "larger", facts, f) for i, m, f in ok if i > pi), None)
    options = [o for o in (smaller, pick, larger) if o]
    return {"pick": pick, "smaller": smaller, "larger": larger, "options": options, "reason": ""}


def advise(facts: dict) -> dict:
    """The advice for a computer described by `facts` ({"memory", "disk_free", "system", "unified", "gpu"}; any may be
    None). {"computer": {...in words...}, "chat": ladder, "embed": ladder, "what_is_a_model"}; a ladder is {"pick",
    "smaller", "larger", "options", "reason"} where `reason` says why nothing is offered."""
    chat = _ladder(CHAT, "chat", facts)
    embed = _ladder(EMBED, "embed", facts)
    parts = []
    if facts.get("memory"):
        parts.append(f"{_gb(facts['memory'])} of memory")
    if facts.get("gpu"):
        parts.append(f"a graphics card with {_gb(facts['gpu'])}")
    elif facts.get("unified"):
        parts.append("Apple silicon (the graphics use the same memory)")
    if facts.get("disk_free") is not None:
        parts.append(f"{_gb(facts['disk_free'])} free disk space")
    words = "This computer has " + ", ".join(parts) + "." if parts else ""
    return {"computer": {"memory": facts.get("memory"), "disk_free": facts.get("disk_free"), "gpu": facts.get("gpu"),
                         "system": facts.get("system"), "unified": bool(facts.get("unified")), "words": words},
            "chat": chat, "embed": embed, "what_is_a_model": WHAT_IS_A_MODEL, "tier": _tier_words(chat)}


def _tier_words(chat: dict) -> dict | None:
    """I6: the tier chosen for this computer in plain words, for the pages outside Settings → Technical (no model name):
    {"tier", "answers", "words", "size", "what"}."""
    pick = chat.get("pick")
    if not pick:
        return None
    what = ("It points at the sentences that bear on your hypothesis, for you to judge." if pick["answers"] == "explorer"
            else "It suggests a judgement for each excerpt it reads, for you to decide.")
    return {"tier": pick["tier"], "answers": pick["answers"], "words": pick["words"], "size": pick["size"],
            "what": what}


def older_model(chosen: str | None, advice: dict) -> dict | None:
    """I6: a person who set up an older model (qwen3:8b, say) keeps it; Settings → Technical offers the tier's model
    beside it, never downloading it unasked. {"chosen", "offer", "size"} when the chosen model is not the tier's."""
    pick = (advice.get("chat") or {}).get("pick")
    if not chosen or not pick or tier_of(chosen) is not None and tier_of(chosen)["name"] == pick["name"]:
        return None
    return {"chosen": chosen, "offer": pick["name"], "size": pick["size"]}


def suggested(advice: dict | None = None) -> list[dict]:
    """The recommended models in the old shape of `llm.SUGGESTED_MODELS` ({"name", "use", "size"}), for the page's
    one-button download; falls back to those when the computer cannot be read."""
    from . import llm

    try:
        adv = advice or advise(computer())
    except Exception:  # noqa: BLE001 - the advice is a convenience: never break the card
        return [dict(m) for m in llm.SUGGESTED_MODELS]
    out = []
    for use in ("chat", "embed"):
        pick = adv[use]["pick"]
        if pick:
            out.append({"name": pick["name"], "use": use, "size": pick["size"]})
    return out
