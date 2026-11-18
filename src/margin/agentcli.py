"""Agent CLIs of other providers on the person's own plan (stage 2 of other cloud providers): Codex (OpenAI, `codex`)
and Antigravity (Google, `agy`), set up and started from Margin as Claude Code is (claude_setup.py).

What each adapter does, behind one interface (the app's Settings → AI and its Start buttons use it):

- `find(route)`, `status(route, refresh)`: is the program here, which version, is it signed in (True, False, or None
  when it does not say), which account it names, which models the plan offers (`agy models`), and whether Margin is
  added to it. Cached for half a minute, like claude_setup.status. Only probes that start no model are run.
- `installer_command(route)`, `install_cli(route)`: the provider's own installer, run after the person confirmed it.
- `open_sign_in(route)`: Codex signs in with `codex login`, which opens the browser by itself (started in the
  background, no window); Antigravity signs in on its first interactive start, so a terminal window opens running `agy`
  in an empty folder of Margin (as Claude Code's sign-in window).
- `set_up(route)`: adds Margin to the CLI: Codex gets the Margin connector (`codex mcp add margin ...`), the skill
  `$margin-run` and the helpers as Codex subagents; Antigravity gets the Margin plugin (`agy plugin install`), one
  permission line (`mcp(margin/*)`) and Margin's own work folder as a trusted workspace. Nothing else of the person's
  is changed. `repair()` writes them again when Margin's version, Python or data folder changed.

The runner (`start_run`): neither CLI's headless mode is documented to run skills or subagents, so Margin does what
Claude Code's /margin-run does itself: it asks the queue for the groups and how many helpers to start for each
(taskqueue.run_status), starts one CLI process per helper, on the group's model in the provider's own name
(routing.Router.api_id) and with the effort of the chosen thought, waits, and asks again, until nothing is left to
start or the person presses Stop. Each process's prompt is the helper's own instructions (the body of
claude_plugin/agents/<helper>.md, the same as Claude Code's) and the batch to take. The CLI only answers: Margin
checks every quote, as for Claude Code.

Boxing each run in: Codex starts in an empty folder, with the person's own Codex settings left out
(`--ignore-user-config`), read-only, without its shell, web search and image tools, with the Margin connector given on
the command line (`-c mcp_servers.margin...`) and only its three queue tools enabled. Antigravity has no switch for
its own tools: it starts in Margin's own empty work folder, in its sandbox, without slash commands, and with its
default "ask first" for every tool (Margin refuses to start it when the person set it to run tools without asking).

Run records (process ids) are kept under <MARGIN_HOME>/claude-runs/ as `<route>-<project>.run.json`, so Stop, Quit
and a restarted app find the helpers of a run an earlier app started, as for Claude Code.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import __version__, providers
from . import home as core
from .claude_setup import _cmd, _end_process, _open_window, _run_key, _said, frontmatter
from .procs import no_window
from .store import now
from .update import semver as _semver

ROUTES = tuple(providers.AGENT_CLIS)          # codex, antigravity
SERVER = "margin"                              # the connector's name in each CLI
QUEUE_TOOLS = ("next_tasks", "submit_answers", "release")
MARKER = "[Margin queue helper]"               # the first words of every helper's prompt: how its process is known
SOURCE = Path(__file__).with_name("agent_plugins")
AGENTS = Path(__file__).with_name("claude_plugin") / "agents"
PERMISSION = f"mcp({SERVER}/*)"                # the one allow rule written into Antigravity's settings
BATCHES = 5                                    # batches one helper process takes before it ends
POLL = 2.0                                     # seconds between two looks of the runner
IDLE_ROUNDS = 5                                # looks with nothing at work and nothing to start before a run ends
MAX_FAILED = 3                                 # helper processes in a row that did nothing before a run gives up

INSTALLERS = {
    "codex": {"unix": "curl -fsSL https://chatgpt.com/codex/install.sh | sh",
              "windows": 'powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"',
              "docs": "https://github.com/openai/codex", "env": "MARGIN_CODEX_INSTALLER"},
    "antigravity": {"unix": "curl -fsSL https://antigravity.google/cli/install.sh | bash",
                    "windows": "irm https://antigravity.google/cli/install.ps1 | iex",
                    "docs": "https://antigravity.google/docs/getting-started", "env": "MARGIN_AGY_INSTALLER"},
}
PROGRAM_ENV = {"codex": "MARGIN_CODEX", "antigravity": "MARGIN_AGY"}
SIGN_IN_DOCS = {"codex": "https://learn.chatgpt.com/docs/auth", "antigravity": "https://antigravity.google/docs/getting-started"}

LIMIT_WORDS = re.compile(r"usage limit|rate limit|quota|limit reached|hit your (?:usage )?limit|too many requests|"
                         r"resource.?exhausted", re.I)
SIGNED_OUT_WORDS = re.compile(r"not logged in|not signed in|log ?in first|sign ?in|authenticat|unauthori[sz]ed|"
                              r"\b401\b", re.I)
RESETS_WORDS = re.compile(r"(?:try again|resets?|available again)\s+(?:at|in|on)?\s*([^\n.;|\"]{1,40})", re.I)


def cli(route: str) -> providers.AgentCli:
    a = providers.AGENT_CLIS.get(route)
    if a is None:
        raise ValueError(f"Unknown agent CLI {route!r}: choose {' or '.join(ROUTES)}.")
    return a


def _off() -> None:
    if core.local_only():
        raise ValueError("Cloud models are switched off on this computer: the agent CLIs are not available.")


def user_home() -> Path:
    """The person's home folder, where each CLI keeps its own settings (MARGIN_AGENT_HOME in the tests)."""
    return Path(os.environ.get("MARGIN_AGENT_HOME") or Path.home())


def codex_home() -> Path:
    if os.environ.get("MARGIN_AGENT_HOME"):
        return user_home() / ".codex"
    return Path(os.environ.get("CODEX_HOME") or (user_home() / ".codex"))


def agy_settings_path() -> Path:
    return user_home() / ".gemini" / "antigravity-cli" / "settings.json"


def runs_folder() -> Path:
    d = core.home() / "claude-runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------------------------
# finding the program, asking it
# ---------------------------------------------------------------------------------------------
def find(route: str) -> str:
    """The CLI's program: MARGIN_CODEX / MARGIN_AGY, the PATH, or where its installers put it. "" when not found."""
    a = cli(route)
    env = os.environ.get(PROGRAM_ENV[route], "").strip()
    if env:
        return env if Path(env).exists() else ""
    found = shutil.which(a.program)
    if found:
        return found
    h = Path.home()
    exe = ".exe" if os.name == "nt" else ""
    if route == "codex":
        cands = [h / ".local" / "bin" / f"codex{exe}", Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex"),
                 h / ".npm-global" / "bin" / "codex", h / "AppData" / "Roaming" / "npm" / "codex.cmd",
                 h / ".codex" / "bin" / f"codex{exe}"]
    else:
        local = Path(os.environ.get("LOCALAPPDATA") or (h / "AppData" / "Local"))
        cands = [h / ".local" / "bin" / f"agy{exe}", local / "agy" / "bin" / "agy.exe", Path("/opt/homebrew/bin/agy"),
                 Path("/usr/local/bin/agy")]
    for c in cands:
        if c.exists():
            return str(c)
    return ""


def _run(args: list[str], timeout: float = 60, cwd: Path | None = None, env: dict | None = None) -> tuple[int, str]:
    """Run the CLI and return its exit code and what it wrote (UTF-8, without a window on Windows)."""
    args = _cmd(args[0]) + list(args[1:])
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           cwd=str(cwd or core.home()), stdin=subprocess.DEVNULL,
                           env={**os.environ, **(env or {})}, **no_window())
    except (OSError, subprocess.SubprocessError) as e:
        return 1, f"{type(e).__name__}: {e}"
    return r.returncode, _plain(((r.stdout or "") + (r.stderr or "")).strip())


def _plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text or "")


_OPTIONS: dict = {}


def known_options(route: str, path: str) -> set[str]:
    """The options this CLI's headless mode knows, from its help (`codex exec --help`, `agy --help`), read once per
    program file. Empty when the help cannot be read: then only what is needed is passed."""
    try:
        st = Path(path).stat()
        key = (route, path, st.st_size, st.st_mtime_ns)
    except OSError:
        return set()
    if key not in _OPTIONS:
        code, text = _run([path, "exec", "--help"] if route == "codex" else [path, "--help"], timeout=30)
        _OPTIONS[key] = (set(re.findall(r"(?<![\w-])--[A-Za-z][A-Za-z-]+", text))
                         | set(re.findall(r"(?<![\w-])-[A-Za-z](?![\w-])", text))) if code == 0 else set()
    return _OPTIONS[key]


def _json_in(text: str, opener: str = "{"):
    """The JSON value in a CLI's output that may carry other lines around it (None when there is none)."""
    closer = "}" if opener == "{" else "]"
    i, j = text.find(opener), text.rfind(closer)
    if i < 0 or j < i:
        return None
    try:
        return json.loads(text[i:j + 1])
    except ValueError:
        return None


MODEL_LINE = re.compile(r"^\s*([a-z0-9][a-z0-9._-]*[a-z0-9])(?:\s{2,}|\t|\s*$)", re.I)


def parse_models(text: str) -> list[str]:
    """The model slugs `agy models` lists, one per line ("gemini-4-carbon-high   Gemini 4 Carbon (High)")."""
    out = []
    for line in (text or "").splitlines():
        m = MODEL_LINE.match(line)
        if m and "-" in m.group(1) and m.group(1).lower() not in out:
            out.append(m.group(1).lower())
    return out


# ---------------------------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------------------------
_STATUS: dict[str, dict] = {}


def status(route: str, refresh: bool = False) -> dict:
    """What is ready for this CLI, for the set-up checklist (cached half a minute): {found, path, version, signed_in
    (True/False/None), account, models_available, connector (Margin added: True/False/None), ready, can_start,
    local_only, problem}. `ready`: found, not known to be signed out, and Margin added (the set-up is finished).
    `can_start`: found and not known to be signed out (the app can start it; Margin is added on the first start when
    it is not yet)."""
    cli(route)
    c = _STATUS.get(route)
    if not refresh and c and time.time() - c["at"] < 30:
        return c["value"]
    started = time.time()
    out = {"found": False, "path": "", "version": "", "signed_in": None, "account": "", "models_available": [],
           "connector": None, "ready": False, "can_start": False, "local_only": core.local_only(),
           "problem": ""}
    path = "" if out["local_only"] else find(route)
    if path:
        out.update(found=True, path=path)
        code, text = _run([path, "--version"], timeout=20)
        if code == 0 and text:
            out["version"] = _said(text.splitlines()[0])
        (_codex_status if route == "codex" else _agy_status)(path, out)
    out["can_start"] = bool(out["found"] and out["signed_in"] is not False)
    out["ready"] = bool(out["can_start"] and out["connector"] is True)
    # only the newest answer is kept: a slow look begun before an install or a sign-in finished must not put back
    # "not found" over the answer of a look begun after it (the queue then said "Antigravity was not found")
    now_c = _STATUS.get(route)
    if now_c is None or now_c.get("began", 0) <= started:
        _STATUS[route] = {"at": time.time(), "began": started, "value": out}
    return out


def _codex_status(path: str, out: dict) -> None:
    code, text = _run([path, "login", "status"], timeout=20)
    if code == 0 and not re.search(r"not logged in|not signed in", text, re.I):
        out["signed_in"] = True
        # "Logged in using ChatGPT (you@uni.nl)" → "ChatGPT (you@uni.nl)": the app writes "Signed in with …"
        first = text.splitlines()[0] if text else ""
        out["account"] = _said(re.sub(r"^\s*(?:logged|signed) in (?:using|with|as)\s+", "", first, flags=re.I))
    elif re.search(r"not logged in|not signed in|logged out|no credentials", text, re.I) or code != 0 and text:
        out["signed_in"] = False
    out["connector"] = codex_connector(path)


def codex_connector(path: str) -> bool | None:
    """Whether the Margin connector is in Codex (`codex mcp list --json`, else its config.toml) and Margin's skill is
    written. None when that cannot be read."""
    code, text = _run([path, "mcp", "list", "--json"], timeout=30)
    have = None
    data = _json_in(text, "[") if code == 0 else None
    if data is None and code == 0:
        data = _json_in(text, "{")
    if isinstance(data, list):
        have = any(isinstance(x, dict) and (x.get("name") or x.get("id")) == SERVER for x in data)
    elif isinstance(data, dict):
        servers = data.get("mcp_servers") or data.get("servers") or data
        have = isinstance(servers, dict) and SERVER in servers
    if have is None:
        try:
            have = bool(re.search(rf"^\s*\[mcp_servers\.{SERVER}\]", (codex_home() / "config.toml").read_text("utf-8"),
                                  re.M))
        except OSError:
            return None
    return bool(have and codex_skill_path().exists())


def _agy_status(path: str, out: dict) -> None:
    code, text = _run([path, "models"], timeout=30)
    if code == 0:
        out["signed_in"] = True
        out["models_available"] = parse_models(text)
    elif SIGNED_OUT_WORDS.search(text):
        out["signed_in"] = False
    else:
        out["problem"] = _said(text, 300)
    code, text = _run([path, "plugin", "list", "--json"], timeout=30)
    data = _json_in(text, "[") if code == 0 else None
    if isinstance(data, list):
        out["connector"] = any(isinstance(p, dict) and p.get("name") == "margin-run" and p.get("enabled", True)
                               for p in data)


def forget_status(route: str | None = None) -> None:
    if route:
        _STATUS.pop(route, None)
    else:
        _STATUS.clear()


# ---------------------------------------------------------------------------------------------
# installing, signing in
# ---------------------------------------------------------------------------------------------
def installer_command(route: str, sys_name: str | None = None) -> dict:
    """The provider's own installer: the line shown to the person ({line, args, docs}) and the program Margin runs
    after they confirm. MARGIN_CODEX_INSTALLER / MARGIN_AGY_INSTALLER replace the program (tests, dev server)."""
    from .installation import system

    cli(route)
    i = INSTALLERS[route]
    windows = (sys_name or system()) == "windows"
    line = i["windows"] if windows else i["unix"]
    if windows:
        inner = line.split('"')[1] if line.startswith("powershell") else line
        args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", inner]
    else:
        args = ["/bin/sh" if line.endswith("| sh") else "/bin/bash", "-c", line]
    stand_in = os.environ.get(i["env"], "").strip()
    if stand_in:
        args = _cmd(stand_in)
    return {"line": line, "args": args, "docs": i["docs"]}


def install_cli(route: str, timeout: float = 900) -> dict:
    """Run the installer (the person confirmed it in the app). Returns {"ok", "text", "status"}."""
    _off()
    cmd = installer_command(route)
    env = {**os.environ, "MARGIN_INSTALLING": route}
    if route == "codex":
        env["CODEX_NON_INTERACTIVE"] = "1"   # the installer's questions skipped (its documented switch)
    try:
        r = subprocess.run(cmd["args"], capture_output=True, text=True, errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL, cwd=str(Path.home()), env=env, **no_window())
        code, text = r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        code, text = 1, f"{type(e).__name__}: {e}"
    text = _plain(text).strip()
    st = status(route, refresh=True)
    if code == 0 and not st["found"]:
        text = (text + "\n" if text else "") + (f"The installer finished, but Margin cannot find the "
                                                f"{cli(route).program} program yet.")
    return {"ok": code == 0 and st["found"], "text": text[-1500:], "status": st}


_LOGIN: dict[str, subprocess.Popen] = {}


def sign_in_folder(route: str) -> Path:
    """The empty folder Antigravity's sign-in window starts in (anything in it removed first)."""
    d = runs_folder() / f"{route}-sign-in"
    d.mkdir(parents=True, exist_ok=True)
    for child in d.iterdir():
        try:
            shutil.rmtree(child, ignore_errors=True) if child.is_dir() and not child.is_symlink() else child.unlink()
        except OSError:
            pass
    return d


def _sign_in_script(route: str, path: str, work: Path) -> Path:
    title = cli(route).title
    if os.name == "nt":
        from .gui.launcher import _ps_quote

        q = lambda s: _ps_quote(str(s))  # noqa: E731 - a PowerShell string
        p = runs_folder() / f"{route}-sign-in.ps1"
        p.write_text(f"Write-Host 'Margin: sign in to {title} with your Google account.'\r\n"
                     "Write-Host 'Follow the steps below; when it shows its prompt, close this window.'\r\n"
                     "Write-Host 'It runs in an empty folder of Margin.'\r\n"
                     f"Set-Location -LiteralPath {q(work)}\r\n"
                     f"& {' '.join(q(x) for x in _cmd(path))}\r\n", encoding="utf-8-sig", newline="")
        return p
    import shlex

    p = runs_folder() / f"{route}-sign-in.command"
    p.write_text("#!/bin/sh\n"
                 f"echo 'Margin: sign in to {title} with your Google account.'\n"
                 "echo 'Follow the steps below; when it shows its prompt, close this window.'\n"
                 "echo 'It runs in an empty folder of Margin.'\n"
                 "echo\n"
                 f"cd {shlex.quote(str(work))} || exit 1\n"
                 f"exec {' '.join(shlex.quote(x) for x in _cmd(path))}\n", encoding="utf-8")
    p.chmod(0o755)
    return p


def open_sign_in(route: str) -> dict:
    """Start the CLI's own sign-in. Codex: `codex login` in the background (it opens the browser itself; no window).
    Antigravity: a terminal window running `agy` in an empty folder of Margin. Margin never sees the login; the app
    asks `status()` until it says signed in. Returns {opened, window ("" for Codex), command}."""
    _off()
    path = find(route)
    title = cli(route).title
    if not path:
        raise ValueError(f"{title} is not on this computer yet: install it first.")
    forget_status(route)
    if route == "codex":
        running = _LOGIN.get(route)
        if running is None or running.poll() is not None:
            log = open(runs_folder() / "codex-login.log", "w", encoding="utf-8")
            try:
                _LOGIN[route] = subprocess.Popen(_cmd(path) + ["login"], cwd=str(core.home()), stdout=log,
                                                 stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                                 start_new_session=os.name != "nt", **no_window())
            except OSError as e:
                raise ValueError(f"Codex's sign-in could not start: {e}") from e
            finally:
                log.close()
        return {"opened": True, "window": "", "command": "codex login"}
    work = sign_in_folder(route)
    window = _open_window(_sign_in_script(route, path, work))
    import shlex

    line = (f"cd {shlex.quote(str(work))} && agy" if os.name != "nt" else f'cd "{work}"; agy')
    return {"opened": bool(window), "window": window, "command": line, "folder": str(work)}


# ---------------------------------------------------------------------------------------------
# adding Margin to the CLI
# ---------------------------------------------------------------------------------------------
def _fill(text: str, route: str) -> str:
    return (text.replace("{{VERSION}}", _semver(__version__)).replace("{{TITLE}}", cli(route).title)
            .replace("{{TOOL_PREFIX}}", ""))


def helper_files() -> dict[str, Path]:
    """Every helper's instruction file: Margin's own seven and an add-on kind's (taskkinds.addon_helpers)."""
    from . import taskkinds

    out = {f.stem: f for f in sorted(AGENTS.glob("*.md"))}
    out.update({h: Path(f) for h, f in taskkinds.addon_helpers().items()})
    return out


def helper_body(helper: str) -> str:
    """The instructions of a helper (the body of its agent file, without the front matter)."""
    f = helper_files().get(helper) or AGENTS / f"{helper}.md"
    text = f.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end >= 0:
            text = text[end + 4:]
    return _fill(text, "codex").strip()


def connector_env(route: str) -> dict[str, str]:
    return {"MARGIN_HOME": str(core.home()), "MARGIN_ROUTE": route}


def connector_command() -> list[str]:
    """This Python running the connector (as claude_setup.mcp_config)."""
    return [sys.executable, "-m", "margin.mcp_server"]


def toml_str(s: str) -> str:
    """A TOML basic string (JSON's escapes are TOML's)."""
    return json.dumps(str(s), ensure_ascii=False)


def toml_list(xs) -> str:
    return "[" + ", ".join(toml_str(x) for x in xs) + "]"


def toml_table(d: dict) -> str:
    return "{" + ", ".join(f"{k}={toml_str(v)}" for k, v in d.items()) + "}"


def _lineup(route: str) -> dict:
    from . import routing

    available = status(route).get("models_available") if route == "antigravity" else None
    return routing.lineup_for(core.load_settings(), route, available or None)


def codex_skill_path() -> Path:
    return user_home() / ".agents" / "skills" / "margin-run" / "SKILL.md"


def write_codex_files() -> list[Path]:
    """The skill $margin-run and the helpers as Codex subagents (~/.codex/agents/margin-<helper>.toml), each on the
    model of the line-up its alias stands for."""
    from . import routing

    lineup = _lineup("codex")
    written = []
    skill = codex_skill_path()
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(_fill((SOURCE / "codex-SKILL.md").read_text("utf-8"), "codex"), encoding="utf-8")
    written.append(skill)
    agents = codex_home() / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    for h, f in helper_files().items():
        fm = frontmatter(f)
        alias = routing.HELPER_MODEL.get(h) or fm.get("model") or "sonnet"
        model = lineup.get(providers.ALIAS_TIER.get(alias, "middle")) or ""
        lines = [f"name = {toml_str(h)}", f"description = {toml_str(fm.get('description') or h)}",
                 f"developer_instructions = {toml_str(helper_body(h))}"]
        if model:
            lines.append(f"model = {toml_str(model)}")
        p = agents / f"{h}.toml"
        p.write_text("# Written by Margin (Settings → AI → Codex); written again when Margin changes.\n"
                     + "\n".join(lines) + "\n", encoding="utf-8")
        written.append(p)
    return written


def agy_plugin_folder() -> Path:
    return core.home() / "agy-plugin" / "margin-run"


def agy_work_folder() -> Path:
    """Margin's own folder Antigravity starts in (trusted, empty but for its connector settings)."""
    return runs_folder() / "agy-work"


def agy_mcp_config(route: str = "antigravity") -> dict:
    cmd = connector_command()
    return {"mcpServers": {SERVER: {"command": cmd[0], "args": cmd[1:], "env": connector_env(route),
                                    "enabledTools": list(QUEUE_TOOLS), "timeoutSeconds": 600}}}


def write_agy_plugin() -> Path:
    """The plugin folder: plugin.json, the skill, the helpers (flash for the small ones, pro for the others) and the
    connector's settings."""
    from . import routing

    root = agy_plugin_folder()
    if root.exists():
        shutil.rmtree(root)
    (root / "skills" / "margin-run").mkdir(parents=True)
    (root / "agents").mkdir()
    src = SOURCE / "antigravity"
    (root / "plugin.json").write_text(_fill((src / "plugin.json").read_text("utf-8"), "antigravity"), encoding="utf-8")
    (root / "skills" / "margin-run" / "SKILL.md").write_text(_fill((src / "SKILL.md").read_text("utf-8"), "antigravity"),
                                                             encoding="utf-8")
    for h, f in helper_files().items():
        fm = frontmatter(f)
        alias = routing.HELPER_MODEL.get(h) or fm.get("model") or "sonnet"
        model = "flash" if alias == "haiku" else "pro"
        desc = (fm.get("description") or h).replace('"', "'")
        (root / "agents" / f"{h}.md").write_text(
            f"---\nname: {h}\ndescription: \"{desc}\"\ntools: {', '.join(QUEUE_TOOLS)}\nmodel: {model}\n---\n\n"
            f"{helper_body(h)}\n", encoding="utf-8")
    (root / "mcp_config.json").write_text(json.dumps(agy_mcp_config(), indent=2), encoding="utf-8")
    return root


def prepare_agy_work_folder() -> Path:
    """Empty Margin's Antigravity work folder but for `.agents/mcp_config.json`, the connector it loads there."""
    d = agy_work_folder()
    d.mkdir(parents=True, exist_ok=True)
    for child in d.iterdir():
        if child.name == ".agents":
            continue
        try:
            shutil.rmtree(child, ignore_errors=True) if child.is_dir() and not child.is_symlink() else child.unlink()
        except OSError:
            pass
    (d / ".agents").mkdir(exist_ok=True)
    (d / ".agents" / "mcp_config.json").write_text(json.dumps(agy_mcp_config(), indent=2), encoding="utf-8")
    return d


def agy_settings() -> dict:
    """Antigravity's own settings ({} when there are none or they cannot be read)."""
    try:
        data = json.loads(agy_settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def merge_agy_settings() -> dict:
    """Add the one allow rule `mcp(margin/*)` to `permissions.allow` and Margin's work folder to `trustedWorkspaces`,
    keeping every other key; a copy of the file as it was is kept as settings.json.bak first. Nothing is removed.
    Returns {"changed": bool, "added": [...]}. Raises ValueError when the file is there but is not JSON (it is then
    left as it is)."""
    p = agy_settings_path()
    data: dict = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8") or "{}")
        except (OSError, ValueError) as e:
            raise ValueError(f"Antigravity's settings ({p}) could not be read as JSON, so Margin left them as they "
                             f"are: {e}") from e
        if not isinstance(data, dict):
            raise ValueError(f"Antigravity's settings ({p}) are not a JSON object, so Margin left them as they are.")
    added = []
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        perms = {} if perms is None else None
    if perms is not None:
        allow = perms.get("allow")
        if allow is None:
            allow = []
        if isinstance(allow, list) and PERMISSION not in allow:
            allow.append(PERMISSION)
            perms["allow"] = allow
            data["permissions"] = perms
            added.append(f'permissions.allow "{PERMISSION}"')
    work = str(agy_work_folder())
    trusted = data.get("trustedWorkspaces")
    if trusted is None:
        trusted = []
    if isinstance(trusted, list) and work not in trusted:
        trusted.append(work)
        data["trustedWorkspaces"] = trusted
        added.append(f'trustedWorkspaces "{work}"')
    if added:
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            shutil.copyfile(p, p.with_name(p.name + ".bak"))
        tmp = p.with_name(p.name + ".margin-tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, p)
    return {"changed": bool(added), "added": added}


def always_proceeds() -> bool:
    """Whether Antigravity is set to run every tool without asking (top-level toolPermission "always-proceed")."""
    return str(agy_settings().get("toolPermission") or "").strip().lower() == "always-proceed"


ALWAYS_PROCEED = ("Antigravity is set to run every tool without asking (toolPermission \"always-proceed\" in "
                  "{path}). Margin starts it only when it asks first, so it cannot run commands or read files unasked: "
                  "change that setting to \"request-review\" (Antigravity's default), then press Start Antigravity "
                  "again.")


def _record_setup(route: str) -> None:
    p = core.home() / "agent-clis.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    data[route] = {"version": __version__, "python": sys.executable, "home": str(core.home()), "at": now()}
    try:
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def _setup_record() -> dict:
    try:
        data = json.loads((core.home() / "agent-clis.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def set_up(route: str) -> dict:
    """Add Margin to the CLI (the person pressed *Add Margin to Codex*). Returns {"steps": [{step, ok, text}],
    "status"}; never raises for the CLI's own problems (they are in the steps)."""
    _off()
    title = cli(route).title
    steps: list[dict] = []
    path = find(route)
    if not path:
        steps.append({"step": f"Add Margin to {title}", "ok": False,
                      "text": f"{title} was not found on this computer: install it first."})
        return {"steps": steps, "status": status(route, refresh=True)}
    if route == "codex":
        try:
            files = write_codex_files()
            steps.append({"step": "Write the skill $margin-run and its helpers", "ok": True,
                          "text": f"{files[0]} and {len(files) - 1} helpers in {files[1].parent}"})
        except OSError as e:
            steps.append({"step": "Write the skill $margin-run and its helpers", "ok": False, "text": str(e)})
        cmd = connector_command()
        env_args = [x for k, v in connector_env(route).items() for x in ("--env", f"{k}={v}")]
        add = [path, "mcp", "add", SERVER, *env_args, "--", *cmd]
        code, text = _run(add, timeout=120)
        if code != 0 and re.search(r"exist", text, re.I):   # an earlier Margin's: replaced by this one
            _run([path, "mcp", "remove", SERVER], timeout=60)
            code, text = _run(add, timeout=120)
        steps.append({"step": "Add the Margin connector to Codex", "ok": code == 0,
                      "text": text[-600:] or ("Added." if code == 0 else "Codex did not say why.")})
    else:
        try:
            root = write_agy_plugin()
            prepare_agy_work_folder()
            steps.append({"step": "Write the Margin plugin", "ok": True, "text": f"Written to {root}"})
        except OSError as e:
            steps.append({"step": "Write the Margin plugin", "ok": False, "text": str(e)})
            return {"steps": steps, "status": status(route, refresh=True)}
        code, text = _run([path, "plugin", "install", str(root)], timeout=120)
        steps.append({"step": "Add the plugin to Antigravity", "ok": code == 0,
                      "text": text[-600:] or ("Added." if code == 0 else "Antigravity did not say why.")})
        try:
            r = merge_agy_settings()
            steps.append({"step": "Allow the Margin tools", "ok": True,
                          "text": ("Added " + " and ".join(r["added"]) + f" to {agy_settings_path()} (a copy of it as "
                                   "it was: settings.json.bak).") if r["changed"] else "Already allowed."})
        except (OSError, ValueError) as e:
            steps.append({"step": "Allow the Margin tools", "ok": False, "text": str(e)})
    if all(s["ok"] for s in steps):
        _record_setup(route)
    forget_status(route)
    return {"steps": steps, "status": status(route, refresh=True)}


def stale(route: str) -> str:
    """Why what Margin added to the CLI no longer fits this installation ("" when it fits, or when nothing was
    added): another version of Margin, another Python or another data folder."""
    rec = _setup_record().get(route)
    if not isinstance(rec, dict):
        return ""
    if rec.get("python") != sys.executable:
        return f"it starts the connector with {rec.get('python')}, not with this Margin ({sys.executable})"
    if rec.get("home") != str(core.home()):
        return "it uses another data folder"
    if rec.get("version") != __version__:
        return f"it was written by Margin {rec.get('version')}, and this is Margin {__version__}"
    return ""


def repair() -> dict:
    """Add Margin to each CLI again where what was added no longer fits (stale), quietly: run when the app starts, as
    claude_setup.repair. Nothing happens for a CLI Margin was never added to, or on a local-only installation."""
    out: dict = {}
    if core.local_only():
        return out
    for route in ROUTES:
        why = stale(route)
        if not why:
            continue
        try:
            r = set_up(route)
            out[route] = {"repaired": all(s["ok"] for s in r["steps"]), "reason": why, "steps": r["steps"]}
        except (OSError, ValueError) as e:
            out[route] = {"repaired": False, "reason": why, "error": str(e)}
    return out


def manual_lines(route: str) -> list[str]:
    """What a person types to add Margin by hand (shown under "Prefer to do it yourself?")."""
    cmd = " ".join(f'"{x}"' if " " in x else x for x in connector_command())
    if route == "codex":
        env = " ".join(f'--env {k}="{v}"' for k, v in connector_env(route).items())
        return [f"codex mcp add {SERVER} {env} -- {cmd}"]
    return [f'agy plugin install "{agy_plugin_folder()}"']


# ---------------------------------------------------------------------------------------------
# the runner
# ---------------------------------------------------------------------------------------------
_RUNS: dict[tuple[str, str], dict] = {}
_RUNS_LOCK = threading.Lock()
_START_LOCKS: dict[tuple[str, str], threading.Lock] = {}


def _key(route: str, project: str) -> str:
    return f"{route}-{_run_key(project)}"


def _record_path(route: str, project: str) -> Path:
    return runs_folder() / f"{_key(route, project)}.run.json"


def _log_path(route: str, project: str) -> Path:
    return runs_folder() / f"{_key(route, project)}.log"


def work_folder(route: str, project: str) -> Path:
    """The folder a run's helpers start in: Codex an empty one per project; Antigravity Margin's trusted one."""
    if route == "antigravity":
        return prepare_agy_work_folder()
    d = runs_folder() / "work" / _key(route, project)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_record(run: dict) -> None:
    pids = [p["proc"].pid for p in run["procs"] if p["proc"].poll() is None and isinstance(p["proc"].pid, int)]
    try:
        _record_path(run["route"], run["project"]).write_text(json.dumps(
            {"project": run["project"], "route": run["route"], "pid": pids[0] if pids else 0, "pids": pids,
             "started_at": run["started_at"], "t0": run["t0"], "plan": run["plan"] or {}}), encoding="utf-8")
    except OSError:
        pass


def _read_record(route: str, project: str) -> dict:
    try:
        rec = json.loads(_record_path(route, project).read_text(encoding="utf-8"))
        return rec if isinstance(rec, dict) and isinstance(rec.get("pids"), list) else {}
    except (OSError, ValueError):
        return {}


def _forget_record(route: str, project: str) -> None:
    try:
        _record_path(route, project).unlink()
    except OSError:
        pass


def _pid_is_helper(pid: int) -> bool:
    """Whether process `pid` is alive and is a helper Margin started (its command line holds MARKER)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        from .procs import windows_command_line

        try:
            cmd = windows_command_line(pid)
        except (OSError, AttributeError, ValueError):
            return False
        return cmd is not None and MARKER in cmd
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        r = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(pid)], capture_output=True, text=True,
                           timeout=15)  # console: not on Windows
    except (OSError, subprocess.SubprocessError):
        return True
    return r.returncode == 0 and MARKER in (r.stdout or "")


def _resolve_agy_model(model_id: str, effort: str | None, available: list[str]) -> tuple[str, str | None]:
    """The slug Antigravity takes for a line-up id, and the effort still to pass as --effort (None when the slug
    carries it: `agy models` lists "gemini-4-carbon-high", "…-low")."""
    if not available or model_id in available:
        return model_id, effort
    cands = [a for a in available if a.startswith(model_id + "-")]
    if not cands:
        return model_id, effort
    for suffix in (effort or "medium", "medium", "high", "low"):
        if f"{model_id}-{suffix}" in cands:
            return f"{model_id}-{suffix}", None
    return cands[0], None


def helper_prompt(route: str, project: str, kind: str, model: str, helper: str) -> str:
    """One helper process's prompt: MARKER, the helper's own instructions, the batch to take."""
    title = cli(route).title
    q = json.dumps
    call = (f"next_tasks(project={q(project, ensure_ascii=False)}, kind={q(kind)}, model={q(model)}, "
            f"helper={q(helper)}, taken_by={q(f'{helper} in {title}', ensure_ascii=False)})")
    return (f"{MARKER} You are a helper of Margin, started by the Margin app to answer its task queue.\n\n"
            f"{helper_body(helper)}\n\n"
            f"Project: {project}. Kind: {kind}. Model: {model}. Helper: {helper}.\n"
            f"Take batches with the Margin tool\n{call}\n"
            f"and answer them as your instructions say, until next_tasks returns no claim or you have finished "
            f"{BATCHES} batches. Use only the Margin tools next_tasks, submit_answers and release: do not run "
            "commands, read or write files, or search the web. Then report in one line how many tasks you stored and "
            "how many still had problems.")


def run_args(route: str, path: str, prompt: str, model_id: str, effort: str | None, work: Path,
             options: set[str] | None = None, available: list[str] | None = None) -> list[str]:
    """The command of one helper process (only the options this CLI's help lists; never through a shell)."""
    opts = known_options(route, path) if options is None else options

    def has(*names):
        return any(n in opts for n in names)

    if route == "codex":
        if not has("-c", "--config"):
            raise ValueError("This Codex does not take settings on its command line (-c), which Margin needs to give "
                             "it the Margin connector: update Codex, then press Start Codex again.")
        c = "-c" if "-c" in opts else "--config"
        cmd = connector_command()
        args = _cmd(path) + ["exec"]
        for flag in ("--skip-git-repo-check", "--ephemeral", "--ignore-user-config"):
            if flag in opts:
                args.append(flag)
        if has("-C", "--cd"):
            args += ["-C" if "-C" in opts else "--cd", str(work)]
        if has("-s", "--sandbox"):
            args += ["-s" if "-s" in opts else "--sandbox", "read-only"]
        if model_id and has("-m", "--model"):
            args += ["-m" if "-m" in opts else "--model", model_id]
        settings = []
        if effort:
            settings.append(f"model_reasoning_effort={toml_str(effort)}")
        settings += ['approval_policy="never"', "features.shell_tool=false", 'web_search="disabled"',
                     "features.view_image=false",
                     f"mcp_servers.{SERVER}.command={toml_str(cmd[0])}",
                     f"mcp_servers.{SERVER}.args={toml_list(cmd[1:])}",
                     f"mcp_servers.{SERVER}.env={toml_table(connector_env(route))}",
                     f"mcp_servers.{SERVER}.enabled_tools={toml_list(QUEUE_TOOLS)}",
                     f'mcp_servers.{SERVER}.default_tools_approval_mode="approve"',
                     f"mcp_servers.{SERVER}.tool_timeout_sec=600"]
        for s in settings:
            args += [c, s]
        if "--json" in opts:
            args.append("--json")
        return args + [prompt]
    slug, eff = _resolve_agy_model(model_id, effort, available or [])
    args = _cmd(path) + ["-p", prompt]
    if "--output-format" in opts:
        args += ["--output-format", "json"]
    if slug and "--model" in opts:
        args += ["--model", slug]
    if eff and "--effort" in opts:
        args += ["--effort", eff]
    for flag in ("--sandbox", "--disable-slash-commands"):
        if flag in opts:
            args.append(flag)
    return args


def read_outcome(route: str, text: str, code: int | None) -> dict:
    """What a finished helper process said: {"ok", "limit" (the sentence, or ""), "signed_out", "message"}."""
    title = cli(route).title
    messages: list[str] = []
    failed = code not in (0, None)
    if route == "codex":
        for line in (text or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            if ev.get("type") in ("turn.failed", "error"):
                failed = True
                err = ev.get("error")
                msg = (err.get("message") if isinstance(err, dict) else err) or ev.get("message") or ""
                if msg:
                    messages.append(str(msg))
            elif ev.get("type") == "item.completed" and isinstance(ev.get("item"), dict) \
                    and ev["item"].get("type") == "agent_message":
                messages.append(str(ev["item"].get("text") or ""))
    else:
        env = _json_in(text or "", "{")
        if isinstance(env, dict) and env.get("status"):
            if str(env["status"]).upper() != "SUCCESS":
                failed = True
                err = env.get("error")
                messages.append(str((err.get("message") if isinstance(err, dict) else err) or env.get("message") or ""))
            else:
                messages.append(str(env.get("result") or env.get("response") or ""))
    if not messages and failed:
        messages.append(_said(text or "", 400))
    said = " ".join(m for m in messages if m).strip()
    limit = ""
    if failed and LIMIT_WORDS.search(said):
        m = RESETS_WORDS.search(said)
        limit = f"{title} reached your plan's usage limit" + (f" (it resets {m.group(1).strip()})" if m else "") + "."
    signed_out = bool(failed and not limit and SIGNED_OUT_WORDS.search(said))
    return {"ok": not failed, "limit": limit, "signed_out": signed_out, "message": _said(said, 400)}


def _say(run: dict, line: str) -> None:
    try:
        with open(run["log"], "a", encoding="utf-8") as fh:
            fh.write(line.rstrip() + "\n")
    except OSError:
        pass


def _claims_since(ws, taken_by: str, since: str) -> int:
    return int(ws.scalar("SELECT COUNT(*) FROM task_claims WHERE taken_by=? AND claimed_at >= ?", (taken_by, since))
               or 0)


def _spawn(run: dict, g: dict, path: str, opts: set[str], work: Path, ws) -> None:
    route, project = run["route"], run["project"]
    r = run["router"]
    model_id = r.api_id(g["model"]) or g["model"]
    effort = r.effort(g["kind"])
    prompt = helper_prompt(route, project, g["kind"], g["model"], g["helper"])
    args = run_args(route, path, prompt, model_id, effort, work, opts, run["available"])
    run["n"] += 1
    out = runs_folder() / f"{_key(route, project)}-{run['n']}.out"
    fh = open(out, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(args, cwd=str(work), stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                env={**os.environ, **connector_env(route)}, start_new_session=os.name != "nt",
                                **no_window())
    finally:
        fh.close()
    taken_by = f"{g['helper']} in {cli(route).title}"
    run["procs"].append({"proc": proc, "group": (g["kind"], g["model"], g["helper"]), "out": out, "since": now(),
                         "taken_by": taken_by, "model_id": model_id, "waited": g.get("waiting", 0)})
    run["started"] += 1
    _say(run, f"Started the {g['helper'].removeprefix('margin-')} helper on {model_id}"
              f"{f' ({effort} effort)' if effort else ''} for {g['kind']}.")
    _write_record(run)


def _reap(run: dict, ws) -> dict | None:
    """Look at the helper processes that ended. Returns {"limit"} or {"fatal"} when the run must end. Without `ws`
    (the run is ending) they are only cleared away."""
    from .taskqueue import _waiting_count

    end = None
    for p in [x for x in run["procs"] if x["proc"].poll() is not None]:
        run["procs"].remove(p)
        try:
            text = p["out"].read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        try:
            p["out"].unlink()
        except OSError:
            pass
        if ws is None:
            continue
        o = read_outcome(run["route"], text, p["proc"].returncode)
        took = _claims_since(ws, p["taken_by"], p["since"])
        run["batches"] += took
        if o["limit"]:
            end = {"limit": o["limit"]}
            _say(run, o["limit"])
        elif o["signed_out"]:
            end = {"fatal": f"{cli(run['route']).title} is not signed in: sign in once from Settings → AI, then press "
                            f"Start {cli(run['route']).title} again. ({o['message']})"}
        elif not o["ok"] or (took == 0 and _waiting_count(ws, p["group"][0]) > 0):
            run["failed_in_row"] += 1
            why = o["message"] or "it ended without taking a batch"
            _say(run, f"A helper ended without answering ({p['taken_by']}): {why}")
            if run["failed_in_row"] >= MAX_FAILED:
                end = {"fatal": f"{cli(run['route']).title} did not answer the queue: {MAX_FAILED} helpers in a row "
                                f"ended without taking a batch. The last one said: {why}"}
        else:
            run["failed_in_row"] = 0
            _say(run, f"{p['taken_by']} finished: {took} batch{'es' if took != 1 else ''}. {o['message']}".strip())
    _write_record(run)
    return end


def _orchestrate(run: dict) -> None:
    from . import routing, taskqueue

    route, project = run["route"], run["project"]
    title = cli(route).title
    path, opts, work = run["path"], run["options"], run["work"]
    idle = 0
    code = 0
    try:
        while not run["stop"].is_set():
            ws = core.open_project(project)
            end = _reap(run, ws)
            if end:
                code = 1
                if end.get("limit"):
                    run["limit"] = end["limit"]
                else:
                    _say(run, end["fatal"])
                break
            settings = core.load_settings()
            run["router"] = routing.from_settings(settings, route=route)
            run["router"].lineup = routing.lineup_for(settings, route, run["available"] or None)
            st = taskqueue.run_status(ws, project, None, run["plan"]["parallel"], run["plan"]["helpers"], route=route)
            if st.get("local_only"):
                _say(run, "This installation keeps everything on this computer: nothing is handed out.")
                break
            alive = [p for p in run["procs"] if p["proc"].poll() is None]
            per: dict[tuple, int] = {}
            for p in alive:
                per[p["group"]] = per.get(p["group"], 0) + 1
            room = run["plan"]["parallel"] - len(alive)
            started = 0
            for g in st["groups"]:
                want = int(g.get("start") or 0) - per.get((g["kind"], g["model"], g["helper"]), 0)
                while want > 0 and room > 0 and not run["stop"].is_set():
                    _spawn(run, g, path, opts, work, ws)
                    want -= 1
                    room -= 1
                    started += 1
            if not alive and not started:
                idle += 1
                if idle >= IDLE_ROUNDS:
                    break
            else:
                idle = 0
            run["stop"].wait(POLL)
    except Exception as e:  # noqa: BLE001 - the run ends with what happened, the app goes on
        code = 1
        _say(run, f"The run stopped: {type(e).__name__}: {e}")
    finally:
        for p in list(run["procs"]):
            if p["proc"].poll() is None:
                _end_process(p["proc"].pid, p["proc"], wait=5.0)
        try:
            _reap(run, None)
        except Exception:  # noqa: BLE001
            pass
        if run["stop"].is_set():
            run["stopped"] = True
            _say(run, f"{title} stopped. What it had not answered waits again.")
        elif not code:
            _say(run, f"Done: {run['batches']} batch{'es' if run['batches'] != 1 else ''} answered by {title} for "
                      f"{project}, with {run['started']} helper run{'s' if run['started'] != 1 else ''}. The results "
                      "are in the Margin app.")
        run["exit_code"] = 1 if code else 0
        run["ended"] = time.time()
        _forget_record(route, project)


def run_state(route: str, project: str) -> dict:
    """Whether the CLI, started from the app, works on this project's queue; the end of its report (the shapes of
    claude_setup.run_state, with `title`, `route` and, at a usage limit, `limit`)."""
    from . import taskqueue

    title = cli(route).title
    with _RUNS_LOCK:
        run = _RUNS.get((route, project))
    if not run:
        rec = _read_record(route, project)
        if not rec:
            return {"running": False, "title": title, "route": route}
        alive = [p for p in rec.get("pids") or [] if _pid_is_helper(p)]
        if not alive:
            _forget_record(route, project)
            return {"running": False, "title": title, "route": route}
        plan = rec.get("plan") or {}
        return {"running": True, "started_at": rec.get("started_at", ""), "title": title, "route": route,
                "seconds": int(time.time() - float(rec.get("t0") or time.time())), "exit_code": None, "report": "",
                "stopped": False, "parallel": plan.get("parallel"),
                "helpers": {taskqueue.short_helper(h): n for h, n in (plan.get("helpers") or {}).items() if n} or None}
    running = run["exit_code"] is None
    tail = ""
    if not running:
        try:
            tail = run["log"].read_text(encoding="utf-8", errors="replace")[-1200:].strip()
        except OSError:
            pass
    plan = run.get("plan") or {}
    out = {"running": running, "started_at": run["started_at"], "seconds": int(time.time() - run["t0"]),
           "exit_code": run["exit_code"], "report": tail, "stopped": run.get("stopped", False), "title": title,
           "route": route, "parallel": plan.get("parallel"),
           "helpers": {taskqueue.short_helper(h): n for h, n in (plan.get("helpers") or {}).items() if n} or None,
           "helpers_running": sum(1 for p in run["procs"] if p["proc"].poll() is None)}
    if run.get("limit") and not running:
        out["limit"] = run["limit"]
    return out


def _start_lock(route: str, project: str) -> threading.Lock:
    with _RUNS_LOCK:
        return _START_LOCKS.setdefault((route, project), threading.Lock())


def start_run(route: str, project: str, parallel=None, helpers=None) -> dict:
    """Start the CLI on the project's queue (the person pressed *Start Codex*): one runner per project and route.
    `parallel`, `helpers`: the run's plan (taskqueue.run_plan; the speed of Settings without them). Raises ValueError
    with a plain reason when it cannot start."""
    from . import taskqueue

    _off()
    a = cli(route)
    with _start_lock(route, project):
        st = run_state(route, project)
        if st.get("running"):
            return st
        plan = taskqueue.run_plan(parallel, helpers)
        path = find(route)
        if not path:
            raise ValueError(f"{a.title} was not found on this computer. Set it up in Settings → AI.")
        info = status(route)
        if info.get("signed_in") is False:
            info = status(route, refresh=True)
            if info.get("signed_in") is False:
                raise ValueError(f"{a.title} is not signed in yet: sign in once from Settings → AI, then press "
                                 f"Start {a.title} again.")
        if route == "antigravity" and always_proceeds():
            raise ValueError(ALWAYS_PROCEED.format(path=agy_settings_path()))
        if info.get("connector") is False or stale(route) or (route == "antigravity" and not agy_plugin_folder().exists()):
            set_up(route)   # Margin is added on the first start, as Claude Code's plugin is
        opts = known_options(route, path)
        if route == "codex" and not ({"-c", "--config"} & opts):
            raise ValueError("This Codex does not take settings on its command line (-c), which Margin needs to give "
                             "it the Margin connector: update Codex, then press Start Codex again.")
        if route == "antigravity" and not ({"-p", "--print"} & opts) and opts:
            raise ValueError("This Antigravity has no headless mode (-p): update it, then press Start Antigravity "
                             "again.")
        log = _log_path(route, project)
        log.write_text("", encoding="utf-8")
        run = {"route": route, "project": project, "plan": plan, "path": path, "options": opts,
               "work": work_folder(route, project), "available": list(info.get("models_available") or []),
               "procs": [], "stop": threading.Event(), "log": log, "t0": time.time(), "started_at": now(),
               "exit_code": None, "stopped": False, "limit": None, "n": 0, "started": 0, "batches": 0,
               "failed_in_row": 0, "router": None}
        with _RUNS_LOCK:
            _RUNS[(route, project)] = run
        _write_record(run)
        run["thread"] = threading.Thread(target=_orchestrate, args=(run,), daemon=True,
                                         name=f"margin-{route}-{_run_key(project)}")
        run["thread"].start()
        return run_state(route, project)


def stop_run(route: str, project: str) -> dict:
    """Stop the CLI started from the app (also the helpers an earlier copy of the app started). Batches it had taken
    return to the queue (the caller releases them; claims lapse otherwise)."""
    with _RUNS_LOCK:
        run = _RUNS.get((route, project))
    if run:
        if run["exit_code"] is None:
            run["stop"].set()
            for p in list(run["procs"]):
                if p["proc"].poll() is None:
                    _end_process(p["proc"].pid, p["proc"], wait=5.0)
            t = run.get("thread")
            if t is not None:
                t.join(30)
    else:
        rec = _read_record(route, project)
        for pid in rec.get("pids") or []:
            if _pid_is_helper(pid):
                _end_process(pid, wait=5.0, alive=_pid_is_helper)
        if rec:
            _forget_record(route, project)
    return run_state(route, project)


def stop_all_runs() -> list[dict]:
    """Stop every run of every agent CLI, this app's and an earlier one's (Quit, Update and restart). Returns
    [{"project", "started_at", "route"}] of the runs that were working."""
    with _RUNS_LOCK:
        keys = set(_RUNS)
    try:
        for f in runs_folder().glob("*.run.json"):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(rec, dict) and rec.get("route") in ROUTES and rec.get("project"):
                keys.add((rec["route"], str(rec["project"])))
    except OSError:
        pass
    stopped = []
    for route, name in sorted(keys):
        before = run_state(route, name)
        if before.get("running"):
            stop_run(route, name)
            stopped.append({"project": name, "started_at": before.get("started_at", ""), "route": route})
    return stopped


def any_running(project: str) -> dict | None:
    """The state of a run of any agent CLI working on this project now, or None."""
    for route in ROUTES:
        st = run_state(route, project)
        if st.get("running"):
            return st
    return None


def reset_for_tests() -> None:
    """Stop and forget every run and cached answer (the tests' clean slate)."""
    with _RUNS_LOCK:
        runs = list(_RUNS.values())
        _RUNS.clear()
        _START_LOCKS.clear()
    for run in runs:
        run["stop"].set()
        for p in list(run["procs"]):
            if p["proc"].poll() is None:
                _end_process(p["proc"].pid, p["proc"], wait=5.0)
        t = run.get("thread")
        if t is not None:
            t.join(10)
    for p in _LOGIN.values():
        if p.poll() is None:
            _end_process(p.pid, p, wait=5.0)
    _LOGIN.clear()
    _STATUS.clear()
    _OPTIONS.clear()
