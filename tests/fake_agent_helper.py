"""What the stand-ins of the agent CLIs (fake_codex_cli.py, fake_agy_cli.py) share (stage 2 of other cloud providers):
playing ONE helper process as Margin starts it (agentcli.start_run), through the connector's own queue functions
(mcp_server.queue_next_tasks, queue_submit, queue_release) with MARGIN_ROUTE set, as the real connector would be
started by the CLI. The answers come from the fake model (fake_servers._answer, via fake_claude_code.FakeClaudeCode).

The prompt holds exactly one call `next_tasks(project=<json>, kind=<json>, model=<json>, helper=<json>,
taken_by=<json>)` (agentcli.helper_prompt): the stand-in reads the batch to take from it, as a model would.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALL = re.compile(r"next_tasks\((.*?)\)\s*$", re.M)
ARG = re.compile(r"(\w+)=(\"(?:[^\"\\]|\\.)*\")")


def state_file(name: str) -> Path:
    return Path(os.environ.get("MARGIN_HOME", ".")) / name


def load(name: str) -> dict:
    try:
        return json.loads(state_file(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(name: str, st: dict) -> None:
    p = state_file(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st), encoding="utf-8")


def options_list(env: str, default: str) -> list[str]:
    known = os.environ.get(env, default)
    return [] if known == "none" else known.split()


def parse_call(prompt: str) -> dict:
    """The arguments of the next_tasks call written in a helper's prompt. Raises ValueError when there is none."""
    m = CALL.search(prompt or "")
    if not m:
        raise ValueError("no next_tasks call in the prompt")
    args = {k: json.loads(v) for k, v in ARG.findall(m.group(1))}
    if not args.get("project"):
        raise ValueError("the next_tasks call names no project")
    return args


class ConnectorTools:
    """The queue tools as the connector serves them (FakeClaudeCode's interface)."""

    def __init__(self):
        from margin import mcp_server

        self.m = mcp_server

    def next_tasks(self, project, kind=None, n=None, model=None, taken_by=None, helper=None):
        return self.m.queue_next_tasks(project, kind, n, model, taken_by, helper)

    def submit_answers(self, claim, answers, project=None):
        return self.m.queue_submit(claim, answers)

    def release(self, claim):
        return self.m.queue_release(claim)


def play_helper(prompt: str, route: str, home: str | None, batches: int = 5) -> tuple[int, int]:
    """Take up to `batches` batches as the prompt says and answer them. Returns (tasks stored, with problems)."""
    call = parse_call(prompt)
    os.environ["MARGIN_ROUTE"] = route
    if home:
        os.environ["MARGIN_HOME"] = home
    sys.path[:0] = [str(HERE), str(HERE.parent / "src")]
    import fake_claude_code

    helper = fake_claude_code.FakeClaudeCode(ConnectorTools(), name=call.get("taken_by") or "helper", wrong_first=False)
    stored = problems = 0
    for _ in range(batches):
        e = helper.batch(call["project"], call.get("kind"), call.get("model"), call.get("helper"))
        if e is None:
            break
        stored += e["stored"]
        problems += e["problems"]
    return stored, problems
