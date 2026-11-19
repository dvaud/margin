"""A stand-in for the installers of Codex and Antigravity (stage 2), for tests and the dev server.

Point MARGIN_CODEX_INSTALLER (or MARGIN_AGY_INSTALLER) at this file, and MARGIN_CODEX (or MARGIN_AGY) at a path
that does not exist yet, ending in .py. Margin runs it with MARGIN_INSTALLING set to the route (codex or
antigravity); it "installs" the CLI by writing, at that path, a small program that runs the stand-in
(fake_codex_cli.py or fake_agy_cli.py). FAKE_INSTALLER_FAIL=1 fails as a real installer would without a network.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIS = {"codex": ("MARGIN_CODEX", "fake_codex_cli.py", "Codex", "chatgpt.com"),
        "antigravity": ("MARGIN_AGY", "fake_agy_cli.py", "Antigravity", "antigravity.google")}


def main() -> int:
    route = os.environ.get("MARGIN_INSTALLING", "")
    if route not in CLIS:
        print("MARGIN_INSTALLING must be codex or antigravity", file=sys.stderr)
        return 2
    env, script, title, host = CLIS[route]
    if os.environ.get("FAKE_INSTALLER_FAIL"):
        print(f"curl: (6) Could not resolve host: {host}", file=sys.stderr)
        return 6
    target = os.environ.get(env, "")
    if not target.endswith(".py"):
        print(f"{env} must name a .py path for the stand-in installer", file=sys.stderr)
        return 2
    time.sleep(float(os.environ.get("FAKE_INSTALLER_DELAY", "0") or 0))
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    cli = HERE / script
    Path(target).write_text("import runpy, sys\n"
                            f"sys.argv[0] = {str(cli)!r}\n"
                            f"runpy.run_path({str(cli)!r}, run_name='__main__')\n", encoding="utf-8")
    print(f"Installing {title}...\n{title} installed (stand-in).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
