"""Stage 2 of other cloud providers: the agent CLIs (Codex, Antigravity, and Claude Code beside them) set up from
Settings → AI, one shape for all three, so the set-up dialog is the same for each (docs/API.md, "Agent CLIs").

- `GET /api/agent-setup?route=<codex|antigravity|claude_code>[&refresh=1]` → what is ready, what is recommended for
  the plan, what to type by hand;
- `POST /api/agent-setup/install {route}` → `{job}` (kind "agent-install"; 409 when the program is there);
- `POST /api/agent-setup/sign-in {route}` → `{opened, window, command}`;
- `POST /api/agent-setup {route}` → `{steps, status}`: adds Margin to it.

Claude Code's own endpoints (/api/claude-setup…) stay as they were; for route=claude_code these wrap them."""
from __future__ import annotations

from .api_common import ApiError, Job, _str
from .. import home, providers

PLANS = {"claude_code": "a Claude plan (Pro, Max, Team or Enterprise)"}
# what "Add Margin to …" adds, in the set-up's words (nothing else of the person's is changed)
ADDS = {"codex": ["the Margin connector (margin), with only its three queue tools",
                  "the skill $margin-run, so you can also type $margin-run <project> in Codex",
                  "the Margin helpers, as Codex subagents"],
        "antigravity": ["the Margin plugin (margin-run): its connector, its skill and its helpers",
                        "one permission line, mcp(margin/*), so its tools may be used without asking each time",
                        "Margin's own empty work folder as a trusted workspace (Antigravity starts there, in its "
                        "sandbox)"],
        "claude_code": ["the Margin plugin (margin-run): its connector, its skill /margin-run and its helpers"]}


def agent_info(route: str | None) -> dict | None:
    """What the app shows for an agent route as the main route ({route, title, start, company, provider, card}), or
    None for any other route. `card`: the sidebar's words ("Codex, on your ChatGPT plan")."""
    if route == "claude_code":
        return {"route": route, "title": "Claude Code", "start": "Start Claude Code", "company": "Anthropic",
                "provider": providers.ANTHROPIC, "card": "Claude, on your plan"}
    a = providers.AGENT_CLIS.get(route or "")
    if a is None:
        return None
    card = {"codex": "Codex, on your ChatGPT plan", "antigravity": "Antigravity, on your Google account"}.get(
        a.id, f"{a.title}, on your plan")
    return {"route": a.id, "title": a.title, "start": f"Start {a.title}", "company": providers.company(a.provider),
            "provider": a.provider, "card": card}


def _route(value) -> str:
    r = str(value or "").strip().lower()
    if r not in providers.AGENT_ROUTES:
        raise ApiError(400, f"Choose an agent: {', '.join(providers.AGENT_ROUTES)}.")
    return r


def _claude_status(refresh: bool) -> dict:
    from .. import claude_setup

    st = claude_setup.status(refresh=refresh)
    return {"found": st["found"], "path": st["path"], "version": st["version"], "signed_in": st["signed_in"],
            "account": claude_setup.account_words(st), "connector": st.get("installed"), "ready": st["ready"],
            "models_available": [], "problem": ""}


def setup_view(route: str, refresh: bool = False) -> dict:
    """GET /api/agent-setup for one route (also used by the tests)."""
    from .. import agentcli, routing

    settings = home.load_settings()
    local = home.local_only()
    if route == "claude_code":
        from .. import claude_setup

        status = _claude_status(refresh) if not local else {
            "found": False, "path": "", "version": "", "signed_in": None, "account": "", "connector": None,
            "ready": False, "models_available": [], "problem": ""}
        aliases = {t: providers.TIER_ALIAS[t] for t in providers.TIERS}
        inst = claude_setup.installer_command()
        return {"route": route, "title": "Claude Code", "company": "Anthropic", "program": "claude",
                "plan": PLANS[route], "docs": claude_setup.INSTALL_DOCS,
                "installer": {"line": inst["line"], "docs": inst["docs"]}, "status": status,
                "recommended": aliases, "lineup_in_use": aliases, "manual": claude_setup.commands(),
                "local_only": local, "adds": ADDS[route], "sign_in_docs": claude_setup.INSTALL_DOCS}
    a = providers.AGENT_CLIS[route]
    if local:
        status = {"found": False, "path": "", "version": "", "signed_in": None, "account": "", "connector": None,
                  "ready": False, "models_available": [], "problem": ""}
    else:
        st = agentcli.status(route, refresh=refresh)
        status = {k: st.get(k) for k in ("found", "path", "version", "signed_in", "account", "connector", "ready",
                                         "can_start", "models_available", "problem")}
    available = status.get("models_available") or None
    inst = agentcli.installer_command(route)
    return {"route": route, "title": a.title, "company": providers.company(a.provider), "program": a.program,
            "plan": a.plan, "docs": a.docs, "installer": {"line": inst["line"], "docs": inst["docs"]},
            "status": status, "recommended": providers.cli_recommended(route, available),
            "lineup_in_use": routing.lineup_for(settings, route, available), "manual": agentcli.manual_lines(route),
            "local_only": local, "adds": ADDS[route], "sign_in_docs": agentcli.SIGN_IN_DOCS[route],
            "measured": a.measured}


class AgentApi:
    def get_agent_setup(self, q):
        return setup_view(_route(_str(q, "route")), refresh=(_str(q, "refresh") or "") in ("1", "true"))

    def _agents_allowed(self) -> None:
        if home.local_only():
            raise ApiError(403, "Cloud models are switched off on this computer: the agent CLIs are not available.")

    def post_agent_setup(self, q):
        """Add Margin to the agent (the set-up's step "Add Margin to Codex") → {steps, status}."""
        from .. import agentcli, claude_setup

        route = _route(self._body().get("route"))
        self._agents_allowed()
        try:
            if route == "claude_code":
                r = claude_setup.install()
                return {"steps": r["steps"], "status": _claude_status(False)}
            r = agentcli.set_up(route)
        except ValueError as e:
            raise ApiError(400, str(e)) from e
        return {"steps": r["steps"], "status": setup_view(route)["status"]}

    def post_agent_install(self, q):
        """Install the agent with its provider's own installer, after the person confirmed the line shown (a job)."""
        from .. import agentcli, claude_setup

        route = _route(self._body().get("route"))
        self._agents_allowed()
        title = setup_view(route)["title"] if route != "claude_code" else "Claude Code"
        found = claude_setup.find_claude() if route == "claude_code" else agentcli.find(route)
        if found:
            raise ApiError(409, f"{title} is already on this computer.")
        running = [j for j in self.app.jobs.all() if j.kind == "agent-install" and j.scope == route
                   and j.state in ("queued", "running")]
        if running:
            return {"job": running[0].view()}

        def run(job: Job):
            r = claude_setup.install_claude_code() if route == "claude_code" else agentcli.install_cli(route)
            if not r["ok"]:
                raise ValueError(f"{title} could not be installed. " + (r["text"][-600:] or ""))
            return r

        job = self.app.jobs.start("agent-install", f"Installing {title}", None, run, uses_model=False)
        job.scope = route
        return {"job": job.view()}

    def post_agent_sign_in(self, q):
        """Start the agent's own sign-in (Margin never sees the login) → {opened, window, command}."""
        from .. import agentcli, claude_setup

        route = _route(self._body().get("route"))
        self._agents_allowed()
        try:
            r = claude_setup.open_sign_in() if route == "claude_code" else agentcli.open_sign_in(route)
        except ValueError as e:
            raise ApiError(400, str(e)) from e
        return {"opened": r["opened"], "window": r["window"], "command": r["command"],
                **({"folder": r["folder"]} if r.get("folder") else {})}
