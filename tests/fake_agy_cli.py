"""A stand-in for Google's Antigravity CLI, `agy` (stage 2 of other cloud providers), for tests and
`tools/dev_server.py --agy-cli`. Point MARGIN_AGY at this file.

It answers what Margin asks of Antigravity: `--version`, `--help` (the options Margin looks for; FAKE_AGY_OPTIONS
replaces them, `none` = none), `models` (the plan's models, FAKE_AGY_PLAN free | pro | ultra), `plugin install <path>`,
`plugin list --json`, `plugin validate --json <path>`, a start without arguments (the sign-in window: it signs in), and
`-p <prompt> ...`, which plays ONE helper (fake_agent_helper.py) with the connector settings of its folder
(`.agents/mcp_config.json`, as Antigravity loads a workspace's), and prints its JSON envelope.

Modes: FAKE_AGY_LOGGED_OUT=1 starts signed out; FAKE_AGY_LIMIT=1 ends every run at the plan's usage limit;
FAKE_AGY_DELAY waits before answering. What it was asked is kept in <MARGIN_HOME>/fake-agy.json ("runs").
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_agent_helper as fa  # noqa: E402

STATE = "fake-agy.json"
OPTIONS = "-p --print --output-format --model --effort --sandbox --disable-slash-commands --print-timeout"
WITH_VALUE = {"-p", "--print", "--output-format", "--model", "--effort", "--print-timeout"}
MODELS = {"free": [("gemini-3.8-flash", "Gemini 3.8 Flash")],
          "pro": [("gemini-3.8-flash", "Gemini 3.8 Flash"), ("gemini-4-argon", "Gemini 4 Argon"),
                  ("gemini-4-hydrogen-high", "Gemini 4 Hydrogen (High)"),
                  ("gemini-4-hydrogen-low", "Gemini 4 Hydrogen (Low)")]}
MODELS["ultra"] = MODELS["pro"] + [("gemini-4-carbon-high", "Gemini 4 Carbon (High)"),
                                   ("gemini-4-carbon-low", "Gemini 4 Carbon (Low)")]


def logged_in(st: dict) -> bool:
    return bool(st.get("logged_in", not os.environ.get("FAKE_AGY_LOGGED_OUT")))


def run(argv: list[str]) -> int:
    st = fa.load(STATE)
    st.setdefault("runs", []).append({"argv": argv, "cwd": os.getcwd()})
    fa.save(STATE, st)
    opts: dict = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in WITH_VALUE and i + 1 < len(argv):
            opts[a] = argv[i + 1]
            i += 2
            continue
        opts[a] = True
        i += 1
    prompt = opts.get("-p") or opts.get("--print") or ""
    as_json = opts.get("--output-format") == "json"

    def say(status: str, text: str) -> None:
        if as_json:
            print(json.dumps({"status": status, "result": text} if status == "SUCCESS" else
                             {"status": status, "error": {"message": text}}))
        else:
            print(text)

    try:
        cfg = json.loads((Path.cwd() / ".agents" / "mcp_config.json").read_text(encoding="utf-8"))
        env = cfg["mcpServers"]["margin"]["env"]
    except (OSError, ValueError, KeyError, TypeError):
        say("ERROR", "no Margin tools in this workspace")
        return 1
    if not logged_in(st):
        say("ERROR", "authentication required")
        return 1
    if os.environ.get("FAKE_AGY_LIMIT"):
        say("ERROR", "Quota exceeded: you have reached your plan's usage limit. It resets at 15:00.")
        return 1
    time.sleep(float(os.environ.get("FAKE_AGY_DELAY", "0") or 0))
    try:
        stored, problems = fa.play_helper(prompt, env.get("MARGIN_ROUTE", ""), env.get("MARGIN_HOME"))
    except Exception as e:  # noqa: BLE001 - reported in the envelope, as Antigravity reports an error
        say("ERROR", f"{type(e).__name__}: {e}")
        return 1
    say("SUCCESS", f"Stored {stored} tasks; {problems} still had problems.")
    return 0


def main(argv: list[str]) -> int:
    st = fa.load(STATE)
    if argv[:1] == ["--version"]:
        print("agy 1.4.0 (stand-in)")
        return 0
    if argv[:1] in (["--help"], ["-h"]):
        print("Antigravity CLI (stand-in)\n\nUsage: agy [options] [command]\n\nOptions:")
        for o in fa.options_list("FAKE_AGY_OPTIONS", OPTIONS):
            print(f"  {o}    (stand-in)")
        return 0
    if not argv:
        st["logged_in"] = True
        fa.save(STATE, st)
        print("Signed in with your Google account (stand-in).")
        return 0
    if argv[:1] == ["models"]:
        if not logged_in(st):
            print("Error: authentication required. Run agy to sign in.", file=sys.stderr)
            return 1
        for slug, title in MODELS.get(os.environ.get("FAKE_AGY_PLAN", "pro"), MODELS["pro"]):
            print(f"{slug}   {title}")
        return 0
    if argv[:2] == ["plugin", "install"] and len(argv) > 2:
        try:
            meta = json.loads((Path(argv[2]) / "plugin.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"Error: not a plugin folder: {e}", file=sys.stderr)
            return 1
        st["plugin"] = {"name": meta.get("name"), "path": argv[2]}
        fa.save(STATE, st)
        print(f"Installed plugin {meta.get('name')} (stand-in)")
        return 0
    if argv[:2] == ["plugin", "list"]:
        p = st.get("plugin")
        print(json.dumps([{"name": p["name"], "path": p["path"], "enabled": True}] if p else []))
        return 0
    if argv[:2] == ["plugin", "validate"]:
        path = next((a for a in argv[2:] if not a.startswith("-")), "")
        try:
            json.loads((Path(path) / "plugin.json").read_text(encoding="utf-8"))
            print(json.dumps({"valid": True, "problems": []}))
            return 0
        except (OSError, ValueError) as e:
            print(json.dumps({"valid": False, "problems": [str(e)]}))
            return 1
    if argv[:1] in (["-p"], ["--print"]) or "-p" in argv or "--print" in argv:
        return run(argv)
    print(f"unsupported: {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
