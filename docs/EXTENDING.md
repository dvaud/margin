# Building on Margin

An app built on Margin (Margin is one) adds its features **in files of its own**, plus a short list of files that
Margin creates once and never edits again: the **local layer**. A new Margin release then merges without clashes,
because it never touches what the app wrote.

Margin stays complete on its own: every extension point below is empty, or Margin's default, in Margin, and nothing
changes for people who use Margin itself.

## Two ways to build on Margin

- **A fork** (a copy of Margin's repository, like Margin) fills in the local-layer files listed below. Its own new
  modules, views and tests live in files Margin does not have.
- **A separate package** installed next to Margin names an add-on module under the Python entry point group
  `margin.extensions`, in its `pyproject.toml`:

  ```toml
  [project.entry-points."margin.extensions"]
  fieldnotes = "fieldnotes_addon"
  ```

Both give Margin an **add-on module**: the fork's is `margin/gui/extensions.py`, a package's is the module its
entry point names. Margin reads both (`margin/addons.py`: the fork's first, then each package's by name).
Margin reads only the names a module defines and keeps its own default for every other one. An add-on that fails to
load is left out, Margin still starts, and the error is printed and kept (`addons.errors()`).

## The local layer

Margin releases **never edit** these files. Margin ships each one empty, or holding Margin's own values.

| File | What it is for |
| --- | --- |
| `src/margin/gui/static/site.css` | The installation's own look. Linked last, so it wins. |
| `src/margin/gui/static/brand.json` | The app's name and words. |
| `src/margin/gui/extensions.py` | The fork's add-on module. |
| `docs/ADDON_API.md` | The routes the app adds, documented like `docs/API.md`. |
| `docs/ADDON_MANUAL.md` | The manual for what the app adds. |

## The look: `site.css` and the theme tokens

`index.html` links Margin's stylesheets in release order, then a fixed comment, then `site.css`:

```html
<link rel="stylesheet" href="/static/tokens.css">
<link rel="stylesheet" href="/static/app.css">
…
<link rel="stylesheet" href="/static/v0134.css">
<!-- release stylesheets end -->
<link rel="stylesheet" href="/static/site.css">
```

Each release adds its own stylesheet just above the comment, so `site.css` always loads last.

The colours, faces, shadows and sizes are **tokens** (CSS custom properties) in `tokens.css`, for the light theme,
the dark theme chosen by the system, and the dark theme chosen in the app. A different look overrides them in
`site.css`; nobody edits `app.css` or `tokens.css` for it:

```css
:root { --accent: #8a3b12; --accent-strong: #6d2e0e; --font-ui: "Inter", system-ui, sans-serif; }
:root[data-theme="dark"] { --accent: #f0a46c; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --accent: #f0a46c; } }
```

A **package** puts its page files in a folder and names it in its add-on module:

```python
from pathlib import Path
STATIC = Path(__file__).with_name("static")
```

They are served at `/static/addons/<add-on>/…`. Its `site.css`, when there is one, is added to `/static/site.css`
after the installation's own.

## The name: `brand.json`

```json
{
  "name": "Margin",
  "tagline": "explore and check your documents",
  "welcome_title": "Explore your documents, and check what they say",
  "welcome_text": "Margin reads your reports, papers and interview notes. …",
  "description": "Explore your documents and check hypotheses against them, with verified quotes.",
  "logo": "/static/logo.svg"
}
```

`GET /api/state` returns it as `brand`, and the page takes the app's name, tagline, logo and welcome screen from
there. A package sets any of these keys in its add-on module instead (other keys are ignored):

```python
BRAND = {"name": "Fieldnotes", "tagline": "notes from the field", "logo": "/static/addons/fieldnotes/logo.svg"}
```

Page code names the app with `appName()` (or `brand()`) from `lib.js`, never with a fixed "Margin".

## Rules that no add-on gets round

`home.local_only()` (switched off cloud models), the per-document AI settings and the quote check apply to anything
an add-on adds. Margin checks them; an add-on never has to, and cannot switch them off.

## Tests

Every extension point is tried with a stand-in add-on, `tests/fake_extension/`, the way `tests/fake_claude_cli.py`
stands in for Claude Code. The `addon` fixture turns it on through its entry point, as if it were installed; the
`local_addon` fixture fills in `gui/extensions.py` as a fork would (`tests/addon_fixtures.py`).

Tests of a release's stylesheet say which sheets it follows, not that it is linked last: `assert_sheet_after(sheet,
earlier)` in `tests/_static.py`. The routes-are-documented tests read every `docs/*API*.md`.

## Keeping it small, and stable

The interface is the names listed here. Changing one counts as a breaking change: it is written up in
`CHANGELOG.md`, and the old form keeps working for one minor version.
