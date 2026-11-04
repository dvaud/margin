"""tools/sync_enlens.py: ENLENS's new commits come into Margin with Margin's names, through an ordinary merge."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("sync_enlens", Path(__file__).parent.parent / "tools" / "sync_enlens.py")
sync_enlens = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_enlens)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def write(repo: Path, files: dict[str, str | bytes]) -> None:
    for path, content in files.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode())


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


HOME_PY = 'HOME = "~/enlens"\nDB = "enlens.sqlite"\n\n\ndef port():\n    return 8765\n'


@pytest.fixture
def repos(tmp_path: Path, monkeypatch):
    """A tiny ENLENS at its 0.11.1 (the split), and a Margin made from it by the rename and some work of its own."""
    cfg = tmp_path / "gitconfig"
    cfg.write_text("")
    for k, v in {"GIT_CONFIG_GLOBAL": str(cfg), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "T",
                 "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "T",
                 "GIT_COMMITTER_EMAIL": "t@example.org"}.items():
        monkeypatch.setenv(k, v)
    enlens, margin = tmp_path / "enlens", tmp_path / "margin"
    enlens.mkdir()
    git(enlens, "init", "-q", "-b", "main")
    write(enlens, {
        "pyproject.toml": 'name = "enlens-claims"\nversion = "0.11.1"\n',
        "src/enlens_claims/__init__.py": '"""ENLENS."""\n__version__ = "0.11.1"\n',
        "src/enlens_claims/home.py": HOME_PY,
        "src/enlens_claims/gui/icons/ENLENS.ico": b"\0\1ENLENS\0",
        "README.md": "# ENLENS\n", "CHANGELOG.md": "## 0.11.1\n",
        "pilot/RUN_NOTES.md": "Run with enlens 0.1.\n",
    })
    split = commit(enlens, "ENLENS 0.11.1")
    git(tmp_path, "clone", "-q", str(enlens), str(margin))
    git(margin, "mv", "src/enlens_claims", "src/margin")
    git(margin, "mv", "src/margin/gui/icons/ENLENS.ico", "src/margin/gui/icons/Margin.ico")
    write(margin, {
        "pyproject.toml": 'name = "margin"\nversion = "0.2.0"\n',
        "src/margin/__init__.py": '"""Margin."""\n__version__ = "0.2.0"\n',
        "src/margin/home.py": HOME_PY.replace('"~/enlens"', '"~/margin"').replace("8765", "8766")
                              + "\n\ndef drafts():  # Margin's own\n    return []\n",
        "src/margin/gui/icons/Margin.ico": b"\0\1MARGIN\0",
        "README.md": "# Margin\n", "CHANGELOG.md": "## 0.2.0\n\n## 0.1.0\n",
    })
    commit(margin, "Margin 0.2.0")
    return enlens, margin, split


def run(margin: Path, enlens: Path, split: str, **kw) -> dict:
    return sync_enlens.sync(margin, remote=str(enlens), branch="main", split=split, say=lambda *_: None, **kw)


def test_the_rename_rules():
    t = sync_enlens.translate
    assert t("import enlens_claims.store") == "import margin.store"
    assert t('pip install "enlens-claims[gui]"') == 'pip install "margin[gui]"'
    assert t("ENLENS_HOME or ~/enlens, port 8765") == "MARGIN_HOME or ~/margin, port 8766"
    assert t("an ENLENS icon; X-Enlens-Token") == "a Margin icon; X-Margin-Token"
    assert t("github.com/dvaud/claim_checker_demo") == "github.com/dvaud/margin"
    # the file formats both apps share keep their names
    assert t("enlens.sqlite, enlens-move.json, enlens_text.zip") == "enlens.sqlite, enlens-move.json, enlens_text.zip"
    assert t("id 18765, 0.8765") == "id 18765, 0.8765"
    assert sync_enlens.translate_path("pilot/enlens/x.md") == "pilot/enlens/x.md"


def test_enlens_work_comes_in_with_margin_names_and_margin_keeps_its_own(repos):
    enlens, margin, split = repos
    write(enlens, {
        "src/enlens_claims/home.py": HOME_PY.replace("def port():", "def port():  # ENLENS fix"),
        "src/enlens_claims/new.py": 'from enlens_claims import home  # reads ENLENS_HOME\n',
        "pyproject.toml": 'name = "enlens-claims"\nversion = "0.12.0"\n',
        "src/enlens_claims/__init__.py": '"""ENLENS."""\n__version__ = "0.12.0"\n',
        "CHANGELOG.md": "## 0.12.0\n\n## 0.11.1\n", "README.md": "# ENLENS 0.12\n",
        "pilot/RUN_NOTES.md": "Run with enlens 0.2.\n",
    })
    fix = commit(enlens, "ENLENS 0.12.0")
    head = git(margin, "rev-parse", "HEAD").strip()

    dry = run(margin, enlens, split, dry_run=True)
    assert dry["commits"] == [fix] and dry["first"]
    assert git(margin, "rev-parse", "HEAD").strip() == head and not (margin / ".git" / "MERGE_HEAD").exists()

    r = run(margin, enlens, split)
    assert r["conflicts"] == [] and (margin / ".git" / "MERGE_HEAD").exists()
    assert sorted(r["frozen"]) == ["CHANGELOG.md", "README.md"]
    home = (margin / "src/margin/home.py").read_text()
    assert "def port():  # ENLENS fix" not in home and "def port():  # Margin fix" in home  # the fix, renamed
    assert '"~/margin"' in home and "8766" in home and "def drafts():" in home              # Margin's own stays
    assert '"enlens.sqlite"' in home
    assert (margin / "src/margin/new.py").read_text() == "from margin import home  # reads MARGIN_HOME\n"
    assert not (margin / "src/enlens_claims").exists()
    assert 'version = "0.2.0"' in (margin / "pyproject.toml").read_text()
    assert '__version__ = "0.2.0"' in (margin / "src/margin/__init__.py").read_text()
    assert (margin / "README.md").read_text() == "# Margin\n"
    assert (margin / "CHANGELOG.md").read_text() == "## 0.2.0\n\n## 0.1.0\n"
    assert (margin / "pilot/RUN_NOTES.md").read_text() == "Run with enlens 0.2.\n"     # history, as it is
    assert (margin / "src/margin/gui/icons/Margin.ico").read_bytes() == b"\0\1MARGIN\0"

    git(margin, "commit", "-q", "--no-edit")
    log = git(margin, "log", "--format=%an %s%n%b")
    assert "Record ENLENS 0.11.1" in log and f"ENLENS-Commit: {fix}" in log
    assert run(margin, enlens, split)["commits"] == []  # nothing new now


def test_a_later_sync_takes_only_the_new_commits_and_stops_at_a_conflict(repos):
    enlens, margin, split = repos
    write(enlens, {"src/enlens_claims/home.py": HOME_PY.replace("\n\n\n", "\n# one\n\n\n")})
    commit(enlens, "one")
    run(margin, enlens, split)
    git(margin, "commit", "-q", "--no-edit")

    write(enlens, {"src/enlens_claims/home.py": HOME_PY.replace("\n\n\n", "\n# one\n# two\n\n\n"),
                   "src/enlens_claims/__init__.py": '"""ENLENS, reworded."""\n__version__ = "0.12.1"\n'})
    two = commit(enlens, "two")
    r = run(margin, enlens, split)
    assert r["commits"] == [two] and not r["first"]
    assert r["conflicts"] == ["src/margin/__init__.py"]  # both changed its first line; the version did not clash
    git(margin, "merge", "--abort")
    assert run(margin, enlens, split, dry_run=True)["commits"] == [two]


def test_it_refuses_to_mix_in_uncommitted_changes(repos):
    enlens, margin, split = repos
    (margin / "README.md").write_text("# Margin, edited\n")
    with pytest.raises(sync_enlens.SyncError, match="uncommitted"):
        run(margin, enlens, split)


def test_it_refuses_margin_s_own_history_as_enlens(repos):
    enlens, margin, split = repos
    with pytest.raises(sync_enlens.SyncError, match="that is Margin, not ENLENS"):
        sync_enlens.sync(margin, ref="HEAD", split=split, say=lambda *_: None)


def test_a_fetch_by_something_else_does_not_change_what_comes_in(repos):
    enlens, margin, split = repos
    write(enlens, {"src/enlens_claims/new.py": "x = 1\n"})
    new = commit(enlens, "new")
    (margin / ".git" / "FETCH_HEAD").write_text(git(margin, "rev-parse", "HEAD").strip() + "\t\tbranch 'main'\n")
    assert run(margin, enlens, split, dry_run=True)["commits"] == [new]
