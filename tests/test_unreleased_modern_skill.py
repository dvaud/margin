"""The /margin-run skill and its helpers follow current Claude Code conventions: helpers run in the foreground so a
headless run waits for them, every helper gets the group's model, and each helper has a turn limit and skips the
user's CLAUDE.md."""


def test_the_skill_waits_for_its_helpers_and_always_names_the_model(tmp_path):
    from margin import claude_setup

    plug = claude_setup.write_plugin(tmp_path) / "plugins" / "margin-run"
    text = (plug / "SKILL.md").read_text()
    fm = claude_setup.frontmatter(plug / "SKILL.md")
    assert fm["disable-model-invocation"] == "true" and fm["effort"] == "low"
    assert fm["arguments"] == "project kind" and "$project" in text and "$kind" in text and "$ARGUMENTS" in text
    assert fm["allowed-tools"] == claude_setup.TOOL_PREFIX + "queue_status Agent"
    assert "`run_in_background`: `false`" in text
    assert "`model`: the group's `model`, always" in text
    assert "{{" not in text


def test_every_helper_has_a_turn_limit_and_skips_claude_md(tmp_path):
    from margin import claude_setup

    plug = claude_setup.write_plugin(tmp_path) / "plugins" / "margin-run"
    colours = set()
    for h in claude_setup.HELPERS:
        fm = claude_setup.frontmatter(plug / "agents" / f"{h}.md")
        assert int(fm["maxTurns"]) >= 20, h
        assert fm["omitClaudeMd"] == "true", h
        colours.add(fm["color"])
    assert len(colours) == len(claude_setup.HELPERS)   # each helper is told apart at a glance
