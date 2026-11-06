"""A draft's claim cards: no sideways scrolling, and a tidy foot (the verdict as one switch, then quiet links)."""
from __future__ import annotations

import re
from pathlib import Path

from margin_static import section

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"


def test_a_long_word_cannot_widen_the_claims():
    css = section("m010")
    # an implicit grid column grows to the widest word (a PDF's text without spaces); this one never passes the pane
    assert re.search(r"\.draft-claims \{[^}]*grid-template-columns: minmax\(0, 1fr\)", css)
    assert re.search(r"\.dc-card \{[^}]*overflow-wrap: anywhere", css)


def test_the_card_foot():
    js = (STATIC / "views" / "drafts.js").read_text(encoding="utf-8")
    assert 'class: "dc-foot"' in js and 'class: "dc-seg"' in js and "Your verdict" in js
    assert "btn btn-sm dc-decide-btn" not in js            # the verdict is one switch, not three loose buttons
    assert 'class: "btn btn-sm dc-lit"' not in js           # Find literature and Open the result are links
    assert 'class: "dc-actions-end"' in js                  # Fold and Remove sit apart, at the far end
    assert "function foot(" not in js                       # one place builds the card's ways on
    css = section("m030")
    assert ".dc-seg" in css and "a.dc-link:hover" in css and "@media (max-width: 640px)" in css
    assert "#" not in css.split("*/", 1)[1]                 # colour tokens only
