"""0.20.3: every kind of job the server starts has its own row in the sidebar's registry (static/registry.js
JOB_KINDS). Without one its row linked to the Overview, so from the Overview a click on *Reading excerpts with the local
model* went nowhere."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "margin"
STATIC = SRC / "gui" / "static"


def server_job_kinds() -> set[str]:
    kinds = set()
    for f in SRC.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        # jobs.start("kind", …), self._job(…), self._model_job(…), start_queued_job(…), the kind on the same line or the next
        kinds |= set(re.findall(r'(?:jobs\.start|\._job|\._model_job|start_queued_job)\(\s*"([a-z_-]+)"', text))
    return kinds


def registry_kinds() -> set[str]:
    js = (STATIC / "registry.js").read_text(encoding="utf-8")
    body = js[js.index("export const JOB_KINDS = {"):js.index("\n};", js.index("export const JOB_KINDS = {"))]
    kinds = set(re.findall(r'^\s+"?([a-z_-]+)"?: \{', body, re.M))
    # Margin: its draft jobs are named in its own page module, which registry.js takes in (extensions.js jobKinds)
    ext = (STATIC / "extensions.js").read_text(encoding="utf-8")
    ext = ext[ext.index("  jobKinds: {"):ext.index("\n  },", ext.index("  jobKinds: {"))]
    return kinds | set(re.findall(r'^\s+"([a-z_-]+)": \{', ext, re.M))


def test_every_job_kind_has_a_row_of_its_own():
    kinds = server_job_kinds()
    assert {"read-local", "stronger", "check", "group-names"} <= kinds   # the search finds them
    assert kinds - registry_kinds() == set(), sorted(kinds - registry_kinds())


def test_the_local_reading_links_to_its_result():
    js = (STATIC / "registry.js").read_text(encoding="utf-8")
    assert '"read-local": { icon: "house", text: "Reading excerpts with the local model", link: (j) => (j.scope ? `#/h/${encodeURIComponent(j.scope)}` : "#/hypotheses") }' in js
