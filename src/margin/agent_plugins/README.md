# Margin for the agent CLIs of other providers (stage 2)

Margin writes these files into each CLI's own places when the person presses *Add Margin to Codex* or *Add Margin to
Antigravity* in Settings → AI (agentcli.py). The helpers' instructions are the same as Claude Code's
(`claude_plugin/agents/*.md`, their bodies); only the orchestrating skill differs.

- `codex-SKILL.md`: the skill `$margin-run`, written to `~/.agents/skills/margin-run/SKILL.md`; the helpers become
  `~/.codex/agents/margin-<helper>.toml`; the connector is added with `codex mcp add margin …`.
- `antigravity/`: the plugin written to `<Margin data folder>/agy-plugin/margin-run/` (`plugin.json`, the skill,
  `agents/*.md`, `mcp_config.json`) and installed with `agy plugin install`.

*Start Codex* and *Start Antigravity* in the app do not use the skill: Margin starts one CLI process per helper itself,
with the helper's instructions as its prompt (agentcli.start_run).

Placeholders: `{{VERSION}}`, `{{TITLE}}` (Codex, Antigravity).
