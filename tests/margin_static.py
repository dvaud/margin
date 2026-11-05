"""Margin's look is in the local layer (ENLENS 0.13.5): index.html links ENLENS's sheets and then site.css, which
imports margin.css, all of Margin's CSS (Margin 0.6; before, m-tokens.css and one m*.css per release).
`sheets_in_order()` is the order the browser applies them in, with site.css replaced by what it imports;
`sections()` names margin.css's sections in order (m-tokens, m010, …) and `section(name)` gives one's rules."""
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


_SECTION = re.compile(r"^/\* ==== ([\w-]+): [^\n]*==== \*/$", re.M)


def sections() -> list[str]:
    """The sections of margin.css, in order: the sheets they were before Margin 0.6 (m-tokens, m010, m030, …)."""
    return _SECTION.findall((STATIC / "margin.css").read_text(encoding="utf-8"))


def section(name: str) -> str:
    """The rules of one section of margin.css (without its heading)."""
    css = (STATIC / "margin.css").read_text(encoding="utf-8")
    heads = list(_SECTION.finditer(css))
    for i, m in enumerate(heads):
        if m.group(1) == name:
            return css[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(css)]
    raise KeyError(name)
