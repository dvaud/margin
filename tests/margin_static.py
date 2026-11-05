"""Margin's look is in the local layer (ENLENS 0.13.5): index.html links ENLENS's sheets and then site.css, which
imports Margin's tokens (m-tokens.css) and Margin's own sheets (m*.css). `sheets_in_order()` is the order the browser
applies them in, with site.css replaced by what it imports."""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"


def sheets_in_order() -> list[str]:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    out = []
    for s in re.findall(r'<link rel="stylesheet" href="/static/([^"]+)">', index):
        if s == "site.css":
            out += re.findall(r'@import url\("/static/([^"]+)"\);', (STATIC / "site.css").read_text(encoding="utf-8"))
        out.append(s)
    return out


def styles_text() -> str:
    """index.html and the sheets in order, as one text (for "is this sheet used, and where")."""
    return "\n".join(f"/static/{s}" for s in sheets_in_order())
