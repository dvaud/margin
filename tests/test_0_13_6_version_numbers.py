"""0.13.6: 0.14.0, 0.15.0 and 0.15.1 were withdrawn (their changes are part of 0.13.6).

In Margin: those were ENLENS's numbers; Margin withdrew none, so its own 0.14.0 will count as newer. Margin's
changelog keeps ENLENS's history below Margin 0.1.0, so only Margin's own releases are checked for their order.

- a copy of a withdrawn version that is still running counts as older, so the icon stops it and starts this one;
- the changelog lists no withdrawn version as a release, and its versions go down from the top.
"""
from __future__ import annotations

import sys
from pathlib import Path

from margin import __version__

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import release  # noqa: E402


def test_a_withdrawn_version_still_running_counts_as_older():
    from margin import update
    from margin.gui import launcher

    assert update.WITHDRAWN == frozenset()
    assert not launcher.is_older({"version": __version__})
    assert launcher.is_older({"version": "0.0.9"})
    assert not launcher.is_older({"version": "0.14.0"})  # Margin's own 0.14.0 will be a later version
    assert not launcher.is_older({"version": "0.16.0"})


def test_the_changelog_lists_no_withdrawn_version():
    from margin import update
    from margin.update import version_tuple

    versions = release.changelog_versions()
    versions = versions[:versions.index("0.1.0") + 1]  # Margin's own; ENLENS's history follows
    assert versions[0] == __version__
    assert not set(versions) & update.WITHDRAWN
    assert [version_tuple(v) for v in versions] == sorted((version_tuple(v) for v in versions), reverse=True)
    assert len(set(versions)) == len(versions)
