"""Bring ENLENS's new work into Margin.

    python tools/sync_enlens.py --dry-run   # what would come in, changing nothing
    python tools/sync_enlens.py             # fetch ENLENS, rename its new commits, merge them (not committed)

Margin grew from ENLENS 0.11.1 and renamed everything (enlens_claims -> margin, ENLENS_* -> MARGIN_*, port 8766, ...),
so ENLENS's commits cannot be merged as they are. This tool rewrites each new ENLENS commit with Margin's names (a
"translated" commit, which keeps ENLENS's author, date and message and adds an `ENLENS-Commit: <sha>` line), then
merges the last one into the current branch with an ordinary git merge. Margin's own changes stay; where both changed
the same lines git marks a conflict as usual. The merge is left uncommitted: run the tests, then `git commit`.

Where the last sync stopped is read from the `ENLENS-Commit:` lines in the branch's history, so nothing else is
stored. The first sync also records (as a merge that changes no file) that Margin grew from ENLENS 0.11.1.

Kept as Margin's own, so ENLENS's changes to them are listed but not merged: README.md, CHANGELOG.md and the version
numbers. Copied without renaming: pilot/ and docs/USER_TESTS.md (history, which names ENLENS on purpose). Names kept
on purpose everywhere: enlens.sqlite, the enlens-move bundle and the enlens_text/enlens_sources zips (shared formats).

Options: --remote (default enlens), --branch (default main), --ref REV (use REV instead of fetching).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SPLIT = "68201e33d88791f34c1d0b5540911373d03402bc"  # ENLENS 0.11.1, which Margin 0.1 grew from
TRAILER = "ENLENS-Commit"

# Names that stay ENLENS's in Margin: file formats both apps read.
_PROTECT = re.compile(r"enlens(?=\.sqlite|-move|_text|_sources)")
# The 0.1 rename, in order (checked against Margin 0.1: what is left over is Margin's own work).
_RULES = [(re.compile(a), b) for a, b in [
    (r"dvaud/claim_checker_demo", "dvaud/margin"),
    (r"enlens[_-]claims", "margin"),
    (r"\ban ENLENS\b", "a Margin"),
    (r"\bAn ENLENS\b", "A Margin"),
    (r"ENLENS_", "MARGIN_"),
    (r"ENLENS", "Margin"),
    (r"Enlens", "Margin"),
    (r"enlens", "margin"),
    (r"(?<![\w.])8765\b", "8766"),
]]
VERBATIM = ("pilot/", "docs/USER_TESTS.md")            # copied as they are
FROZEN = ("README.md", "CHANGELOG.md")                 # Margin's own: ENLENS's changes are listed, not merged
FROZEN_LINES = {                                       # Margin's own lines inside files that are otherwise merged
    "pyproject.toml": re.compile(r"^version\s*=.*$", re.M),
    "src/margin/__init__.py": re.compile(r"^__version__\s*=.*$", re.M),
}


class SyncError(Exception):
    pass


def translate(text: str) -> str:
    """ENLENS's names to Margin's, leaving the shared file-format names alone."""
    kept: list[str] = []

    def hide(m: re.Match) -> str:
        kept.append(m.group(0))
        return f"\0{len(kept) - 1}\0"

    text = _PROTECT.sub(hide, text)
    for rx, rep in _RULES:
        text = rx.sub(rep, text)
    return re.sub(r"\0(\d+)\0", lambda m: kept[int(m.group(1))], text)


def translate_path(path: str) -> str:
    return path if path.startswith(VERBATIM) else translate(path)


# -- git ----------------------------------------------------------------------------------------------------------

class Git:
    def __init__(self, repo: Path):
        self.repo = repo
        self._blobs: dict[str, str] = {}  # ENLENS blob -> translated blob

    def run(self, *args: str, input: bytes | None = None, env: dict | None = None, check: bool = True) -> str:
        p = subprocess.run(["git", *args], cwd=self.repo, input=input, capture_output=True,
                           env={**os.environ, **(env or {})})
        if check and p.returncode:
            raise SyncError(f"git {' '.join(args)} failed:\n{p.stderr.decode(errors='replace').strip()}")
        return p.stdout.decode(errors="replace")

    def ok(self, *args: str) -> bool:
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True).returncode == 0

    def read_blobs(self, shas: list[str]) -> dict[str, bytes]:
        if not shas:
            return {}
        out = subprocess.run(["git", "cat-file", "--batch"], cwd=self.repo, capture_output=True, check=True,
                             input="".join(s + "\n" for s in shas).encode()).stdout
        blobs, i = {}, 0
        for sha in shas:
            j = out.index(b"\n", i)
            size = int(out[i:j].split()[2])
            blobs[sha] = out[j + 1:j + 1 + size]
            i = j + 1 + size + 1
        return blobs

    def write_blob(self, data: bytes) -> str:
        return self.run("hash-object", "-w", "--stdin", input=data).strip()

    def tree(self, rev: str) -> dict[str, tuple[str, str]]:
        """path -> (mode, sha) of every file in rev."""
        entries = {}
        for rec in self.run("ls-tree", "-r", "-z", "--full-tree", rev).split("\0"):
            if rec:
                meta, path = rec.split("\t", 1)
                mode, _kind, sha = meta.split()
                entries[path] = (mode, sha)
        return entries


def _text(data: bytes) -> str | None:
    if b"\0" in data[:8000]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def translate_commit(git: Git, commit: str, parent: str, first: bool = False) -> str:
    """Write the Margin-named copy of ENLENS's `commit` on top of `parent` (the last translated commit, or for the
    `first` one ENLENS's own commit it copies); return its id."""
    src = git.tree(commit)
    prev = {} if first else git.tree(parent)
    todo = [sha for path, (mode, sha) in src.items()
            if mode in ("100644", "100755") and not path.startswith(VERBATIM) and sha not in git._blobs]
    for sha, data in git.read_blobs(todo).items():
        text = _text(data)
        new = translate(text) if text is not None else None
        git._blobs[sha] = git.write_blob(new.encode("utf-8")) if new is not None and new != text else sha

    out: dict[str, tuple[str, str]] = {}
    for path, (mode, sha) in src.items():
        if path.startswith(VERBATIM) or mode not in ("100644", "100755"):
            out[path] = (mode, sha)
        else:
            out[translate_path(path)] = (mode, git._blobs[sha])
    if prev:  # Margin's own files and lines stay as they were in the last translated commit
        for path in FROZEN:
            out.pop(path, None)
            if path in prev:
                out[path] = prev[path]
        for path, rx in FROZEN_LINES.items():
            if path in out and path in prev and out[path][1] != prev[path][1]:
                new_b, old_b = git.read_blobs([out[path][1], prev[path][1]]).values()
                new_t, old_t = new_b.decode("utf-8"), old_b.decode("utf-8")
                m_old = rx.search(old_t)
                if m_old and rx.search(new_t):
                    fixed = rx.sub(lambda _m: m_old.group(0), new_t, count=1)
                    out[path] = (out[path][0], git.write_blob(fixed.encode("utf-8")))

    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        info = "".join(f"{mode} {sha}\t{path}\0" for path, (mode, sha) in sorted(out.items()))
        git.run("update-index", "-z", "--index-info", input=info.encode(), env=env)
        tree = git.run("write-tree", env=env).strip()

    an, ae, ad, cn, ce, cd, msg = git.run("log", "-1", "--format=%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%B",
                                          commit).split("\0", 6)
    msg = git.run("interpret-trailers", "--trailer", f"{TRAILER}: {commit}", input=msg.rstrip("\n").encode() + b"\n")
    env = {"GIT_AUTHOR_NAME": an, "GIT_AUTHOR_EMAIL": ae, "GIT_AUTHOR_DATE": ad,
           "GIT_COMMITTER_NAME": cn, "GIT_COMMITTER_EMAIL": ce, "GIT_COMMITTER_DATE": cd}
    return git.run("commit-tree", tree, "-p", parent, "-F", "-", input=msg.encode(), env=env).strip()


# -- the sync -----------------------------------------------------------------------------------------------------

def last_synced(git: Git) -> tuple[str, str] | None:
    """(translated commit, the ENLENS commit it copies) of the newest sync in HEAD's history, or None."""
    for line in git.run("log", "HEAD", f"--format=%H %(trailers:key={TRAILER},valueonly,separator=%x20)").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            return parts[0], parts[1]
    return None


def plan(git: Git, enlens_head: str, split: str = SPLIT) -> dict:
    if not git.ok("cat-file", "-e", f"{split}^{{commit}}"):
        raise SyncError(f"ENLENS 0.11.1 ({split[:7]}) is not in this repository: is this a Margin checkout?")
    done = last_synced(git)
    base_enlens = done[1] if done else split
    if not git.ok("merge-base", "--is-ancestor", base_enlens, enlens_head):
        raise SyncError(f"ENLENS's history no longer contains {base_enlens[:7]}, where the last sync stopped "
                        "(was it rewritten?). Nothing was changed.")
    new = git.run("rev-list", "--first-parent", "--reverse", f"{base_enlens}..{enlens_head}").split()
    frozen = git.run("diff", "--name-only", base_enlens, enlens_head, "--", *FROZEN).split() if new else []
    return {"first": done is None, "base": done[0] if done else None, "since": base_enlens, "commits": new,
            "frozen": frozen}


def sync(repo: Path, ref: str | None = None, remote: str = "enlens", branch: str = "main",
         dry_run: bool = False, split: str = SPLIT, say=print) -> dict:
    git = Git(repo)
    if not dry_run:
        if git.ok("rev-parse", "-q", "--verify", "MERGE_HEAD"):
            raise SyncError("A merge is in progress: finish it (git commit) or drop it (git merge --abort) first.")
        if git.run("status", "--porcelain", "--untracked-files=no").strip():
            raise SyncError("There are uncommitted changes: commit or stash them first, so the merge is only "
                            "ENLENS's work.")
    if ref is None:
        say(f"Fetching {remote} {branch} ...")
        git.run("fetch", "--quiet", remote, branch)
        ref = "FETCH_HEAD"
    head = git.run("rev-parse", f"{ref}^{{commit}}").strip()
    p = plan(git, head, split)
    commits = p["commits"]
    if not commits:
        say("Nothing new in ENLENS since the last sync.")
        return {**p, "merged": None, "conflicts": []}

    say(f"{len(commits)} new ENLENS commit{'s' if len(commits) != 1 else ''}:")
    for c in commits:
        say("  " + git.run("log", "-1", "--format=%h %s", c).strip())

    parent = p["base"]
    if parent is None:
        parent = translate_commit(git, split, split, first=True)  # ENLENS 0.11.1 in Margin's names: the common ground
        start = parent
    for c in commits:
        parent = translate_commit(git, c, parent)
    tip = parent

    if p["frozen"]:
        say("ENLENS changed these, which Margin keeps as its own (carry over by hand what Margin needs):")
        for f in p["frozen"]:
            say(f"  {f}   (see: git diff {p['since'][:7]} {head[:7]} -- {f})")

    if dry_run:
        files = git.run("diff", "--stat", p["base"] or start, tip).strip()
        say("Files it would change (in Margin's names):\n" + (files or "  none"))
        return {**p, "merged": None, "conflicts": [], "tip": tip}

    if p["first"]:
        git.run("merge", "-s", "ours", "--no-ff", "-m",
                "Record ENLENS 0.11.1 as the point Margin grew from\n\n"
                "Changes no file: it lets tools/sync_enlens.py merge ENLENS's later work.", start)
    subjects = [git.run("log", "-1", "--format=%s", c).strip() for c in commits]
    msg = (f"Bring in ENLENS {head[:7]}: {len(commits)} commit{'s' if len(commits) != 1 else ''}\n\n"
           + "\n".join(f"- {s}" for s in subjects))
    merged = git.run("merge", "--no-ff", "--no-commit", "-m", msg, tip, check=False)
    conflicts = git.run("diff", "--name-only", "--diff-filter=U").split()
    if conflicts:
        say("Merged with conflicts in:\n" + "\n".join(f"  {f}" for f in conflicts))
        say("Fix them, run the tests, then `git add` them and `git commit` (or `git merge --abort` to drop it).")
    elif not git.ok("rev-parse", "-q", "--verify", "MERGE_HEAD"):
        raise SyncError("git merge did not start:\n" + merged)
    else:
        say("Merged, not committed yet: run the tests (python -m pytest), then `git commit`.")
    return {**p, "merged": tip, "conflicts": conflicts, "tip": tip}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bring ENLENS's new commits into Margin, with Margin's names.")
    ap.add_argument("--dry-run", action="store_true", help="show what would come in; change nothing")
    ap.add_argument("--remote", default="enlens", help="the ENLENS remote or path (default: enlens)")
    ap.add_argument("--branch", default="main", help="ENLENS's branch (default: main)")
    ap.add_argument("--ref", help="use this ENLENS commit instead of fetching")
    a = ap.parse_args(argv)
    repo = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                               check=True).stdout.strip())
    try:
        r = sync(repo, ref=a.ref, remote=a.remote, branch=a.branch, dry_run=a.dry_run)
    except SyncError as e:
        print(e, file=sys.stderr)
        return 1
    return 2 if r["conflicts"] else 0


if __name__ == "__main__":
    sys.exit(main())
