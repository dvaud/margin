"""Margin 0.2: Margin's own look. The new stylesheet and its tokens, the logo and the icon drawn from it, and that
nothing of ENLENS's teal is left in the page's styles."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from margin.gui import launcher
from margin_static import section, sections, sheets_in_order

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"
ICONS = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "icons"


def test_the_new_stylesheet_comes_last():
    sheets = sheets_in_order()
    assert sheets == ["tokens.css", "app.css", "components.css", "views.css", "site.css", "margin.css"], sheets
    # Margin's colours are token overrides, linked after every sheet of ENLENS (site.css, the installation's own, ships
    # empty): they win over tokens.css, and every rule of ENLENS's sheets reads them through var()
    assert sections()[0] == "m-tokens"
    # ENLENS's look is not restyled: its five sheets are ENLENS's own and margin.css holds no rule for ENLENS's pages
    # beyond the few of m-shared (the serif headings, the red margin rule in the sidebar and the small eyebrows are gone)
    css = (STATIC / "margin.css").read_text(encoding="utf-8")
    for dropped in (".sidebar .brand-text em", "text-transform: uppercase", "font-variant-caps", "--sidebar-w: 248px"):
        assert dropped not in css, dropped


def test_margins_colours_are_token_overrides_and_nowhere_else():
    """Margin's colours are custom properties on :root (light), on the dark-by-system selector and on the dark-chosen
    one, in the m-tokens section. No other rule of margin.css holds a colour of its own (a hex or rgb value)."""
    from _static import css_blocks

    tokens = section("m-tokens")
    blocks = css_blocks(tokens)
    assert [sels for _m, sels, _d in blocks] == [[":root"], [":root:not([data-theme=\"light\"])"], [":root[data-theme=\"dark\"]"]]
    assert blocks[1][0] == "@media (prefers-color-scheme: dark)" and blocks[0][0] == "" and blocks[2][0] == ""
    for _m, _s, decls in blocks:
        assert decls and all(k.startswith("--") for k in decls), decls   # only tokens are overridden
    # every token it overrides is one of ENLENS's (tokens.css), plus Margin's own rule colours
    ours = {"--rule", "--rule-soft", "--rule-text"}
    defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", (STATIC / "tokens.css").read_text(encoding="utf-8")))
    for _m, _s, decls in blocks:
        assert set(decls) - ours <= defined, set(decls) - ours - defined
    # outside the token block, no hard-coded colour
    css = (STATIC / "margin.css").read_text(encoding="utf-8")
    rest = re.sub(r"/\*.*?\*/", "", css.replace(tokens, ""), flags=re.S)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", rest), re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", rest)


def test_margin_rule_tokens_in_light_and_both_dark_settings():
    css = section("m-tokens")  # the local layer, over ENLENS's tokens.css (m-tokens.css until Margin 0.6)
    for token in ("--rule:", "--rule-soft:", "--rule-text:"):
        assert css.count(token) == 3, token  # light, dark by the system, dark chosen in the app
    assert "--accent: #2b4a9b;" in css and css.count("--accent: #8fa9f0;") == 2


def test_no_enlens_teal_left_in_the_styles():
    teal = {"#0f6e6a", "#0a5451", "#0b5a57", "#dcecea", "#5cc3ba", "#7fd6ce", "#163634", "#1c8c86", "#0d5c5a"}
    # ENLENS's tokens.css keeps its teal (releases change it); margin.css's tokens override every one of them
    for f in [*(x for x in STATIC.glob("*.css") if x.name != "tokens.css"), STATIC / "logo.svg", STATIC / "index.html"]:
        text = f.read_text(encoding="utf-8").lower()
        assert not [c for c in teal if c in text], f.name


def test_the_logo_is_margins_page_and_rule():
    svg = (STATIC / "logo.svg").read_text(encoding="utf-8")
    assert "#24345f" in svg and "#d04a32" in svg  # the ink tile and the margin rule
    assert "<circle" not in svg  # ENLENS's lens was a circle


def test_the_icon_drawing_matches_the_logo():
    pytest.importorskip("PIL")
    img = launcher.draw_icon(64).convert("RGB")
    assert img.size == (64, 64)
    assert img.getpixel((8, 32)) == pytest.approx((0x24, 0x34, 0x5f), abs=6)  # the tile, left of the page
    assert img.getpixel((40, 48)) == pytest.approx((0xf8, 0xf4, 0xea), abs=6)  # the paper
    r, g, b = img.getpixel((24, 46))  # the margin rule, below the tick
    assert r > 150 and g < 110 and b < 90


def test_icon_files_ship_and_the_page_title():
    for ext in ("icns", "ico"):
        assert (ICONS / f"Margin.{ext}").stat().st_size > 1000
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "<title>Margin · your writing and your sources</title>" in page
