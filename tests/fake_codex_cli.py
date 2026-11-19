"""A stand-in for OpenAI's `codex` program (stage 2 of other cloud providers), for tests and
`tools/dev_server.py --codex-cli`. Point MARGIN_CODEX at this file.

It answers what Margin asks of Codex: `--version`, `login status`, `login` (signs in after FAKE_CODEX_LOGIN_DELAY
seconds), `logout`, `mcp add|remove|list --json`, `exec --help` (the options Margin looks for; FAKE_CODEX_OPTIONS
replaces them, `none` = none), and `exec [options] <prompt>`, which plays ONE helper (fake_agent_helper.py) with the
MARGIN_ROUTE and MARGIN_HOME given in `-c mcp_servers.margin.env={...}`, and prints Codex's JSONL events.

Modes: FAKE_CODEX_LOGGED_OUT=1 starts signed out; FAKE_CODEX_LIMIT=1 ends every exec at the plan's usage limit;
FAKE_CODEX_DELAY waits before answering; FAKE_CODEX_MCP_DUPLICATE=1 refuses `mcp add` of a name already there.
What it was asked is kept in <MARGIN_HOME>/fake-codex.json ("execs": each exec's argv and folder).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_agent_helper as fa  # noqa: E402

STATE = "fake-codex.json"
OPTIONS = ("--skip-git-repo-check --ephemeral --ignore-user-config -C --cd -s --sandbox -m --model -c --config --json "
           "-o --output-last-message")
WITH_VALUE = {"-C", "--cd", "-s", "--sandbox", "-m", "--model", "-c", "--config", "-o", "--output-last-message"}


def logged_in(st: dict) -> bool:
    return bool(st.get("logged_in", not os.environ.get("FAKE_CODEX_LOGGED_OUT")))


def event(**kw) -> None:
    print(json.dumps(kw), flush=True)


def toml_strings(table: str) -> dict:
    """KEY="value" pairs of a TOML inline table of basic strings."""
    return {k: json.loads(v) for k, v in re.findall(r"(\w+)\s*=\s*(\"(?:[^\"\\]|\\.)*\")", table)}


def exec_(argv: list[str]) -> int:
    st = fa.load(STATE)
    st.setdefault("execs", []).append({"argv": argv, "cwd": os.getcwd()})
    fa.save(STATE, st)
    configs, positional, out_file = [], [], None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in WITH_VALUE and i + 1 < len(argv):
            if a in ("-c", "--config"):
                configs.append(argv[i + 1])
            if a in ("-o", "--output-last-message"):
                out_file = argv[i + 1]
            i += 2
            continue
        if not a.startswith("-"):
            positional.append(a)
        i += 1
    env = next((toml_strings(c.split("=", 1)[1]) for c in configs if c.startswith("mcp_servers.margin.env=")), None)
    if not env or not positional:
        event(type="error", message="no Margin connector configured" if not env else "no prompt given")
        return 1
    if not logged_in(st):
        event(type="error", message="Not logged in. Run codex login.")
        event(type="turn.failed", error={"message": "Not logged in"})
        return 1
    if os.environ.get("FAKE_CODEX_LIMIT"):
        event(type="thread.started", thread_id="stand-in")
        event(type="turn.failed", error={"message": "You've hit your usage limit. Try again at 3:00 PM."})
        return 1
    time.sleep(float(os.environ.get("FAKE_CODEX_DELAY", "0") or 0))
    event(type="thread.started", thread_id="stand-in")
    event(type="turn.started")
    try:
        stored, problems = fa.play_helper(positional[-1], env.get("MARGIN_ROUTE", ""), env.get("MARGIN_HOME"))
    except Exception as e:  # noqa: BLE001 - reported as Codex reports a failed turn
        event(type="error", message=f"{type(e).__name__}: {e}")
        event(type="turn.failed", error={"message": f"{type(e).__name__}: {e}"})
        return 1
    text = f"Stored {stored} tasks; {problems} still had problems."
    event(type="item.completed", item={"type": "agent_message", "text": text})
    event(type="turn.completed", usage={"input_tokens": 0, "output_tokens": 0})
    if out_file:
        Path(out_file).write_text(text, encoding="utf-8")
    return 0


def main(argv: list[str]) -> int:
    st = fa.load(STATE)
    if argv[:1] == ["--version"]:
        print("codex-cli 0.200.0 (stand-in)")
        return 0
    if argv[:2] == ["login", "status"]:
        if logged_in(st):
            print("Logged in using ChatGPT (researcher@example.org)")
            return 0
        print("Not logged in")
        return 1
    if argv[:1] == ["login"]:
        time.sleep(float(os.environ.get("FAKE_CODEX_LOGIN_DELAY", "0") or 0))
        st = fa.load(STATE)
        st["logged_in"] = True
        fa.save(STATE, st)
        print("Successfully logged in (stand-in)")
        return 0
    if argv[:1] == ["logout"]:
        st["logged_in"] = False
        fa.save(STATE, st)
        print("Logged out")
        return 0
    if argv[:2] == ["mcp", "add"] and len(argv) > 2:
        name, rest = argv[2], argv[3:]
        env, cmd = {}, []
        if "--" in rest:
            cmd = rest[rest.index("--") + 1:]
            rest = rest[:rest.index("--")]
        for j, a in enumerate(rest):
            if a == "--env" and j + 1 < len(rest):
                k, _, v = rest[j + 1].partition("=")
                env[k] = v
        mcp = st.setdefault("mcp", {})
        if name in mcp and os.environ.get("FAKE_CODEX_MCP_DUPLICATE"):
            print(f"Error: MCP server '{name}' already exists", file=sys.stderr)
            return 1
        if not cmd:
            print("Error: give the server's command after --", file=sys.stderr)
            return 2
        mcp[name] = {"command": cmd[0], "args": cmd[1:], "env": env}
        fa.save(STATE, st)
        print(f"Added global MCP server '{name}'.")
        return 0
    if argv[:2] == ["mcp", "remove"] and len(argv) > 2:
        st.setdefault("mcp", {}).pop(argv[2], None)
        fa.save(STATE, st)
        print(f"Removed global MCP server '{argv[2]}'.")
        return 0
    if argv[:2] == ["mcp", "list"]:
        print(json.dumps([{"name": k, **v} for k, v in (st.get("mcp") or {}).items()]))
        return 0
    if argv[:2] == ["exec", "--help"]:
        print("Run Codex non-interactively\n\nUsage: codex exec [OPTIONS] [PROMPT]\n\nOptions:")
        for o in fa.options_list("FAKE_CODEX_OPTIONS", OPTIONS):
            print(f"  {o}    (stand-in)")
        return 0
    if argv[:1] == ["exec"]:
        return exec_(argv[1:])
    if not argv:
        print("Codex (stand-in): Margin never starts Codex interactively.")
        return 0
    print(f"unsupported: {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
