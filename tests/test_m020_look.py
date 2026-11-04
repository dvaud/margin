"""Margin 0.2: Margin's own look. The new stylesheet and its tokens, the logo and the icon drawn from it, and that
nothing of ENLENS's teal is left in the page's styles."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from margin.gui import launcher

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"
ICONS = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "icons"


def test_the_new_stylesheet_comes_last():
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    sheets = re.findall(r'<link rel="stylesheet" href="/static/([^"]+)">', page)
    assert sheets[-1] == "m020.css", sheets  # it restyles what the others draw, so it must win
    assert (STATIC / "m020.css").is_file()


def test_margin_rule_tokens_in_light_and_both_dark_settings():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    for token in ("--rule:", "--rule-soft:", "--rule-text:"):
        assert css.count(token) == 3, token  # light, dark by the system, dark chosen in the app
    assert "--accent: #2b4a9b;" in css and css.count("--accent: #8fa9f0;") == 2


def test_no_enlens_teal_left_in_the_styles():
    teal = {"#0f6e6a", "#0a5451", "#0b5a57", "#dcecea", "#5cc3ba", "#7fd6ce", "#163634", "#1c8c86", "#0d5c5a"}
    for f in [*STATIC.glob("*.css"), STATIC / "logo.svg", STATIC / "index.html"]:
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
