"""Margin's own add-on module, in the local layer (ENLENS 0.13.5). ENLENS's releases never edit it.

What Margin adds to ENLENS through its extension points (docs/EXTENDING.md). Margin's drafts still live partly in
ENLENS's modules; they move here step by step.
"""
from .. import drafts  # noqa: F401  (registers Margin's kind of AI task, "claims", with taskkinds)

# A claim of a draft says where it comes from as ENLENS 0.14 records it (origin "draft"), so the result page links
# back to its draft; hypotheses made before Margin took in ENLENS 0.14 are given it when a project is opened.
SCHEMA = """
UPDATE hypotheses SET origin='draft', origin_id=draft_id WHERE draft_id IS NOT NULL AND origin IS NULL;
"""
