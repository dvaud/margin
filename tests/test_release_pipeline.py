"""The release pipeline (0.18.1, roadmap J1.3, J1.5, J1.7, J1.8, J1.9, J1.10): one version, from the git tag; a lock
file; actions pinned by commit; provenance; a tag made by merging the release pull request; the published install tried
every week. The shape of the workflows is read with PyYAML, which only CI's every-extra job and some laptops have, so
those tests skip without it. Nothing here pushes, tags or calls GitHub."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import margin
from margin import update

from test_update_and_grid import Pip, _g, copies, needs_git  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import release  # noqa: E402

WORKFLOWS = ROOT / ".github" / "workflows"
PYPROJECT = (ROOT / "pyproject.toml").read_text("utf-8")


def _workflow(name: str) -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((WORKFLOWS / name).read_text("utf-8"))


# ---------------------------------------------------------------------------------------------
# J1.3 one version, from the tag
# ---------------------------------------------------------------------------------------------
def test_margin_keeps_one_fixed_version_in_pyproject_and_init():
    """Margin does not make its version from the git tag (ENLENS does, with setuptools-scm): it is typed in
    pyproject.toml and src/margin/__init__.py, `release.py check` makes sure they and the tag and the changelog agree,
    and the release pull request (`release.py prepare`) writes the new one in both."""
    assert "setuptools-scm" not in PYPROJECT and "setuptools_scm" not in PYPROJECT and "dynamic" not in PYPROJECT
    assert release.pyproject_version() == margin.__version__ == release.package_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+(rc\d+)?", margin.__version__)


def test_release_check_compares_the_tag_pyproject_init_and_the_changelog(tmp_path):
    def repo(name, pyproject="0.18.1rc1", init="0.18.1rc1", top="0.18.1rc1"):
        root = tmp_path / name
        (root / "src" / "margin").mkdir(parents=True)
        (root / "pyproject.toml").write_text(f'[project]\nname = "margin"\nversion = "{pyproject}"\n', encoding="utf-8")
        (root / "src" / "margin" / "__init__.py").write_text(f'__version__ = "{init}"\n', encoding="utf-8")
        (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## {top} (November 2026): a candidate\n\n## 0.18.0 (x): y\n",
                                           encoding="utf-8")
        return root

    ok = repo("ok")
    assert release.check(root=ok) == "0.18.1rc1" and release.check("v0.18.1rc1", ok) == "0.18.1rc1"
    with pytest.raises(release.ReleaseError, match="the tag is v0.18.1, but the top entry of CHANGELOG.md is 0.18.1rc1"):
        release.check("v0.18.1", ok)
    with pytest.raises(release.ReleaseError, match="not of the form"):
        release.check("v0.18", ok)
    with pytest.raises(release.ReleaseError, match="pyproject.toml says 0.18.0"):
        release.check("v0.18.1rc1", repo("a", pyproject="0.18.0"))
    with pytest.raises(release.ReleaseError, match="__init__.py says 0.18.0"):
        release.check("v0.18.1rc1", repo("b", init="0.18.0"))
    with pytest.raises(release.ReleaseError, match="the top entry of CHANGELOG.md is 0.18.2"):
        release.check(root=repo("c", top="0.18.2"))
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    with pytest.raises(release.ReleaseError, match="CHANGELOG.md has no entry"):
        release.check(root=empty)


def test_the_release_workflow_builds_the_fixed_version_without_setuptools_scm():
    wf = (WORKFLOWS / "release.yml").read_text("utf-8")
    assert 'python tools/release.py check "${{ github.ref_type == \'tag\' && github.ref_name || \'\' }}"' in wf
    assert 'tools/release.py assets dist --expect "${{ github.ref_name }}"' in wf
    assert "setuptools_scm" not in wf and "uv build --wheel --out-dir dist" in wf


def test_the_wheel_must_carry_the_tags_version(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "margin-0.18.1.post3-py3-none-any.whl").write_bytes(b"PK")
    (dist / ".gitignore").write_text("*\n")                       # `uv build` leaves one: not a file of the release
    with pytest.raises(release.ReleaseError, match="is in pyproject.toml"):
        release.assets(dist, expect="v0.18.1")
    files = release.assets(dist)                                   # a build by hand takes the wheel's own version
    assert ".gitignore" not in {p.name for p in files} and ".gitignore" not in (dist / "SHA256SUMS").read_text()
    assert "0.18.1.post3" in (dist / "install.sh").read_text()
    (dist / "margin-0.18.1.post3-py3-none-any.whl").rename(dist / "margin-0.18.1-py3-none-any.whl")
    assert (dist / "margin-0.18.1-py3-none-any.whl") in release.assets(dist, expect="v0.18.1")


@needs_git
def test_a_git_copy_reads_its_version_from_the_newest_release_tag(tmp_path):
    repo = tmp_path / "copy"
    (repo / "src" / "margin").mkdir(parents=True)
    (repo / "src" / "margin" / "__init__.py").write_text('"""no version here"""\n', encoding="utf-8")
    _g(tmp_path, "init", "-q", str(repo))
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", "one")
    assert update.version_in(repo) == "?"                          # no tag yet
    _g(repo, "tag", "v1.2.3")
    _g(repo, "tag", "nightly")                                     # not a version tag: never taken
    (repo / "x.txt").write_text("x")
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", "two")
    assert update.version_in(repo) == "1.2.3" and not update._written_in_source(repo)
    (repo / "src" / "margin" / "__init__.py").write_text('__version__ = "mine"\n', encoding="utf-8")
    assert update.version_in(repo) == "mine" and update._written_in_source(repo)   # a copy of before 0.18.1


@needs_git
def test_an_update_to_a_new_tag_reinstalls_so_the_installed_version_follows(copies):  # noqa: F811
    dev, user = copies
    init = dev / "src" / "margin" / "__init__.py"
    init.write_text('"""the version is in the tag"""\n', encoding="utf-8")
    _g(dev, "commit", "-qam", "version from the tag")
    _g(dev, "tag", "v0.8.1b")                                      # (not a release tag: the old literal still counts)
    _g(dev, "tag", "-d", "v0.8.1b")
    _g(dev, "tag", "v0.8.1")
    _g(dev, "push", "-q", "--tags", "origin", "HEAD:main")
    pip = Pip()
    first = update.update(root=user, run=pip, python="/py")
    assert first["updated"] is True and first["reinstalled"] is False and pip.calls == []   # 0.8.1 to 0.8.1: code only
    (dev / "x.py").write_text("x = 1\n")
    _g(dev, "add", "-A")
    _g(dev, "commit", "-qm", "code only")
    _g(dev, "push", "-q", "origin", "HEAD:main")
    assert update.update(root=user, run=pip, python="/py")["reinstalled"] is False        # still tagged 0.8.1
    (dev / "y.py").write_text("y = 1\n")
    _g(dev, "add", "-A")
    _g(dev, "commit", "-qm", "release")
    _g(dev, "tag", "v0.8.2")
    _g(dev, "push", "-q", "--tags", "origin", "HEAD:main")
    out = update.update(root=user, run=pip, python="/py")
    assert out["updated"] is True and out["reinstalled"] is True and out["from"] == "0.8.1" and out["version"] == "0.8.2"
    assert len(pip.calls) == 1 and pip.calls[0][-1].startswith(str(user))   # the metadata is made again, from the new tag


def test_the_installed_version_is_read_from_the_metadata(monkeypatch):
    import importlib.metadata as md

    from margin.gui import server

    monkeypatch.setattr(md, "version", lambda name: "7.8.9")
    assert server._installed_version() == "7.8.9"


# ---------------------------------------------------------------------------------------------
# J1.7 a lock file, Dependabot, actions pinned by their commit
# ---------------------------------------------------------------------------------------------
def test_the_lock_file_names_every_package_the_install_needs():
    lock = (ROOT / "uv.lock").read_text("utf-8")
    assert lock.startswith("version = 1") and 'name = "margin"' in lock
    for pkg in ("pydantic", "pypdf", "openpyxl", "cryptography", "pytest", "pytest-xdist", "pytest-timeout", "mcp", "numpy",
                "pdfminer-six", "anthropic", "pypdfium2", "pillow", "pyyaml", "ruff"):
        assert f'name = "{pkg}"' in lock, pkg
    # Margin's own version is typed in pyproject.toml; `uv sync --frozen` does not mind the lock's note of it being older
    assert "uv sync --frozen" in (WORKFLOWS / "tests.yml").read_text("utf-8")


def test_every_action_is_pinned_by_its_commit_with_the_tag_as_a_comment():
    files = sorted(WORKFLOWS.glob("*.yml"))
    assert len(files) >= 5
    for f in files:
        for line in f.read_text("utf-8").splitlines():
            m = re.match(r"\s*(?:-\s*)?uses:\s*(\S+)(.*)$", line)
            if m and not m.group(1).startswith("./"):
                assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", m.group(1)), f"{f.name}: {line.strip()}"
                assert re.match(r"\s*#\s*v\d", m.group(2)), f"{f.name}: no tag comment on {line.strip()}"


def test_dependabot_watches_the_packages_and_the_actions():
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text("utf-8"))
    assert cfg["version"] == 2
    assert {u["package-ecosystem"] for u in cfg["updates"]} == {"uv", "github-actions"}
    assert all(u["directory"] == "/" and u["schedule"]["interval"] == "weekly" for u in cfg["updates"])


def test_every_workflow_that_needs_the_version_has_the_tags():
    for name in ("tests.yml", "nightly.yml", "release.yml", "tag-release.yml"):
        wf = _workflow(name)
        checkouts = [s for job in wf["jobs"].values() for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout@")]
        assert checkouts and all(s.get("with", {}).get("fetch-depth") == 0 for s in checkouts), name


def test_the_every_extra_job_still_installs_every_extra():
    wf = _workflow("tests.yml")
    rows = wf["jobs"]["test"]["strategy"]["matrix"]["include"]
    [full] = [r for r in rows if r["all"]]
    extras = re.search(r"^\[project\.optional-dependencies\]\n(.*?)^\[", PYPROJECT, re.M | re.S).group(1)
    every = set(re.findall(r"^(\w+)\s*=", extras, re.M)) - {"gui"}          # gui = []: nothing to install
    assert set(full["extras"].split(",")) >= every, every - set(full["extras"].split(","))


# ---------------------------------------------------------------------------------------------
# J1.8 provenance, J1.5 the tag, J1.9 the published install, J1.10 the runbook
# ---------------------------------------------------------------------------------------------
def test_each_release_file_is_attested():
    wf = _workflow("release.yml")
    job = wf["jobs"]["release"]
    assert job["permissions"]["id-token"] == "write" and job["permissions"]["attestations"] == "write"
    steps = [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/attest-build-provenance@")]
    assert len(steps) == 1 and steps[0]["with"]["subject-path"] == "dist/*"
    names = [s.get("name", "") for s in job["steps"]]
    assert names.index(steps[0]["name"]) < names.index("Upload to a draft release")    # attested before it is drafted
    assert wf["permissions"] == {"contents": "read", "actions": "read"}               # only this job may write
    text = (WORKFLOWS / "release.yml").read_text("utf-8")
    assert 'assets dist --expect "${{ github.ref_name }}"' in text and "uv build --wheel" in text


def test_merging_a_release_pull_request_tags_it_and_starts_the_release():
    wf = _workflow("tag-release.yml")
    on = wf.get("on") or wf[True]
    assert on["pull_request"] == {"types": ["closed"], "branches": ["main"]}
    job = wf["jobs"]["tag"]
    cond = job["if"]
    assert "merged == true" in cond and "startsWith(github.event.pull_request.head.ref, 'release/')" in cond
    assert "head.repo.full_name == github.repository" in cond                          # never a fork's branch
    assert job["permissions"] == {"contents": "write", "actions": "write"}
    text = (WORKFLOWS / "tag-release.yml").read_text("utf-8")
    assert "merge_commit_sha" in text and "tools/release.py check" in text and "fragments --check" in text
    assert 'gh workflow run release.yml' in text and '--ref "$tag"' in text           # a tag by GITHUB_TOKEN starts nothing
    assert "${{ github.event.pull_request.head.ref }}" not in re.sub(r"(?m)^\s+BRANCH:.*$", "", text)   # via env only
    assert "workflow_dispatch" in (WORKFLOWS / "release.yml").read_text("utf-8")
    # the branch name prepare makes is the one the workflow listens for
    assert 'branch = f"release/{version}"' in (ROOT / "tools" / "release.py").read_text("utf-8")


def test_the_published_install_is_tried_on_three_systems_on_release_and_weekly():
    wf = _workflow("published-install.yml")
    on = wf.get("on") or wf[True]
    assert on["release"] == {"types": ["published"]} and on["schedule"][0]["cron"].endswith("* * 1")
    jobs = wf["jobs"]
    systems = {*jobs["install-unix"]["strategy"]["matrix"]["os"], jobs["install-windows"]["runs-on"]}
    assert systems == {"ubuntu-latest", "macos-latest", "windows-latest"}
    text = (WORKFLOWS / "published-install.yml").read_text("utf-8")
    assert "/install.sh" in text and "/install.ps1" in text and "releases/latest/download" in text
    assert "gh attestation verify" in text and "i.kind() == 'script'" in text


def test_the_runbook_the_release_steps_and_the_pipeline_are_written_down():
    doc = (ROOT / "docs" / "DEVELOPING.md").read_text("utf-8")
    assert "## Rolling back a release" in doc and "gh release edit vX.Y.Z --prerelease" in doc
    for needle in ("python tools/release.py prepare", "release/X.Y.Z", "tag-release.yml", "uv.lock", "uv sync --frozen",
                   "dependabot.yml", "gh attestation verify", "published-install.yml", "setuptools-scm",
                   "python tools/release.py sync-notes", "fetch-depth: 0"):
        assert needle in doc, needle
    assert "stands in `pyproject.toml`, `src/margin/__init__.py`" not in doc          # the version is typed nowhere
