"""Margin 0.10.0: the page of Find literature, its place in the app, and its documentation. The page itself is
looked at in a browser (see the changelog); these tests keep what a browser is not run for: the entries, the CSS rules,
and that every endpoint is documented."""
from __future__ import annotations

import re
from pathlib import Path

from _static import defined_tokens
from helpers import api_docs

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"
ROOT = Path(__file__).resolve().parent.parent


def test_the_feature_is_in_the_app_without_ai():
    features = (STATIC / "features.js").read_text(encoding="utf-8")
    block = features[features.index("  literature: {"):]
    block = block[:block.index("\n  },") + 5]
    assert 'section: "write"' in block and 'ai: "none"' in block and 'href: "#/literature"' in block and "nav: true" in block
    assert 'icon: "search"' in block and "state: (o)" in block
    icons = (STATIC / "icons.js").read_text(encoding="utf-8")
    assert re.search(r'^\s+search: \[\[', icons, re.M)
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'import { renderLiterature } from "./views/literature.js"' in app
    assert '[/^\\/literature$/, "literature", renderLiterature]' in app
    settings = (STATIC / "views" / "settings.js").read_text(encoding="utf-8")
    assert "literatureSettings(s, save, sectionCard)" in settings and 'literature: "explore"' in settings


def test_a_draft_claim_nobody_supports_links_to_the_page():
    js = (STATIC / "views" / "drafts.js").read_text(encoding="utf-8")
    assert '["unsupported", "no_passages", "uncertain"]' in js
    assert "#/literature?draft=" in js and "claim=" in js
    assert "const lit = literatureLink(c);\n      if (lit) row.append(lit);" in js   # append(null) would write "null"
    assert 'data.draft.ai_access === "cloud"' in js   # a draft kept on this computer opens the page without its words


def test_the_page_shows_what_is_sent_and_never_builds_html():
    js = (STATIC / "views" / "literature.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js and "eval(" not in js
    for text in ("Only these words go to", "Show exactly what is sent", "Send to Zotero", "Mark as seen", "Check all now",
                 "Add a research question", "Look for open copies", "Margin never fills it in by itself"):
        assert text in js, text
    assert "/api/literature/zotero" in js and "/api/literature/export" in js
    assert 'rel: "noopener noreferrer"' in js   # works open in a new tab without handing it this page
    assert "api.openalex.org" not in js   # the page never talks to a service: only the app does (the page's CSP)


def test_the_css_uses_the_tokens_and_has_a_phone_layout():
    css = (STATIC / "margin.css").read_text(encoding="utf-8")
    block = css[css.index("/* ---- Find literature"):]
    assert ".lit-work.chosen" in block and ".lit-bar" in block and "@media (max-width: 600px)" in block
    used = set(re.findall(r"var\((--[a-z0-9-]+)", block))
    assert used and used <= defined_tokens(), used - defined_tokens()
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", block)   # colours only through the tokens (light and dark)
    assert "a.dc-link:hover" in css   # the draft card's Find literature link has its own hover colours


def test_every_endpoint_is_documented():
    from margin.gui.server import ROUTES

    api_md = api_docs()
    seen = 0
    for method, rx, name in ROUTES:
        if not isinstance(name, str) or not name.startswith("lit_"):
            continue
        seen += 1
        path = rx.pattern.strip("^$").replace("([^/]+)", "<x>").replace("\\", "")
        path = re.sub(r"/api/projects/<x>", "", path)
        tail = path.split("/literature", 1)[1] if path.startswith("/literature") else path
        assert tail.split("<x>")[0].rstrip("/") in api_md or path in api_md, (method, path)
    assert seen == 17
    for env in ("MARGIN_OPENALEX_URL", "MARGIN_CROSSREF_URL", "MARGIN_S2_URL", "MARGIN_UNPAYWALL_URL", "contact_email",
                "/connector/saveItems", "from_created_date", "local_only"):
        assert env in api_md, env
    manual = (ROOT / "docs" / "MANUAL.md").read_text(encoding="utf-8")
    assert "### Finding literature (Margin)" in manual and "Find literature" in manual and "--local-only" in manual


def test_the_dev_server_can_run_the_stand_ins():
    src = (ROOT / "tools" / "dev_server.py").read_text(encoding="utf-8")
    assert "--literature" in src and "fake_literature" in src and "no_created_filter" in src
    assert "\n## 0.10.0 (" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")  # later work goes on top
