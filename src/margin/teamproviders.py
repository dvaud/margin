"""The cloud providers a team may use (I7 stage 3): one setting of the project's owner, off by default.

**Each person chooses their own.** In a shared project every person reads the project's documents marked for cloud AI
with the route they chose on their own computer (Claude Code, Codex, Antigravity, a provider's API key), for the
providers they allowed on their own copy (`documents.ai_providers`, the project's `ai_providers_default`: access.py).
That consent is the person's, never the team's: it stays in their copy (sync/merge.py does not take a colleague's list
for a document new to this copy, and a copy made from a colleague's zip or folder starts without the colleague's lists,
bundle._forget_folder). What the team decides is the AI level of each document (cloud, local, none), as before.

**The owner may limit it** (*Providers the team may use*, People and settings › *AI providers*): no limit by default;
set, a list of providers (Anthropic only, or several). It is a row of `team_settings` (key `team_providers`), written
and merged exactly as the owner's settings about codebooks are (teamcodebooks.py: only the owner writes it, a row
counts when its writer owned the place it names in the chain of owners this copy follows, a row in this copy's own name
that it does not hold is refused and answered). So it reaches every copy with the owner's other rules, and the app
offers it to the owner alone. The rows are not signed yet (as roles and the codebook settings): a changed app could
write one in the owner's name, which third copies would follow until the owner's copy answers it with its next round;
when the row that counts came in someone else's file, the research log names both (`arrived`). The owner chose this
trust model over signing for now (roadmap, open decisions). A provider outside the limit reads none of the
project's documents in any copy (access._Allow, where every decision about a provider passes): its work is held as
when the person has not allowed that provider yet, and the note says which limit holds and who set it (`note`). A copy of an older Margin does not know the row and leaves
it aside: such a copy allows Anthropic only in a shared project, which is inside any limit but one without Anthropic.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from . import providers
from .teamcodebooks import PROVIDERS as KEY

LABEL = "Providers the team may use"
NO_LIMIT = "No limit: each person uses the provider they choose"


def limit(cx: sqlite3.Connection) -> dict | None:
    """{"providers": [...], "by": person id, "at"} of the owner's limit as it counts in this copy, or None (no limit).
    Raises sqlite3.Error when the tables cannot be read (access._Allow then reads as strictly as before stage 3)."""
    from .teamcodebooks import _counting, has_table

    # most projects never had a limit: one look at the table, and nothing else is read (labelling many tasks reads
    # no settings, tests/test_providers_fixes.py)
    if not has_table(cx) or not cx.execute("SELECT 1 FROM team_settings WHERE key=? LIMIT 1", (KEY,)).fetchone():
        return None
    r = _counting(cx).get(KEY)
    if not r or r["value"] is None:
        return None
    return {"providers": list(r["value"]), "by": r["by"], "at": r["at"]}


def allows(cx: sqlite3.Connection, provider: str | None) -> bool:
    """Whether the team's limit lets this provider read (always, without a limit; a model on this computer, None,
    always)."""
    if provider is None:
        return True
    lim = limit(cx)
    return lim is None or provider in lim["providers"]


def _titles(ids) -> str:
    names = [_title(p) for p in ids]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _title(pid: str) -> str:
    return "a server on another computer" if pid == providers.OTHER else providers.company(pid)


def _who(cx: sqlite3.Connection, pid: str | None, unknown: str = "the owner") -> str:
    from .ownership import _names_cx
    from .teamcodebooks import _my_id

    if pid and pid == _my_id():
        return "you"
    return _names_cx(cx).get(pid or "", unknown)


def note(cx: sqlite3.Connection, provider: str | None = None) -> str | None:
    """The short note of the limit ("The team uses Anthropic only (set by Anna): OpenAI reads none of this project's
    documents."), or None without a limit (or when `provider` is inside it)."""
    try:
        lim = limit(cx)
    except sqlite3.Error:
        return None
    if lim is None or (provider is not None and provider in lim["providers"]):
        return None
    head = f"The team uses {_titles(lim['providers'])} only (set by {_who(cx, lim['by'])})"
    if provider is None:
        return head + "."
    return f"{head}: {_title(provider)} reads none of this project's documents. Ask the owner, or choose another route."


def arrived(cx: sqlite3.Connection, before: dict | None, via: str | None) -> bool:
    """After a merge brought `team_settings` rows (sync/owner_merge.py): when the limit that counts changed, and the
    row that counts now was written in another person's name than the person whose file brought it (relayed, or
    forged: rows are not signed yet), the research log says so, naming both, so the team can see where it came from.
    The owner's own change already has the owner's entry. True when an entry was written."""
    try:
        after = limit(cx)
    except sqlite3.Error:
        return False
    if (before or {}).get("providers") == (after or {}).get("providers"):
        return False
    from .teamcodebooks import _counting

    row = _counting(cx).get(KEY)
    by = row["by"] if row else None
    if not by or by == via:
        return False
    from . import researchlog

    words = f"{_titles(after['providers'])} only" if after else "any cloud provider again"
    sender = _who(cx, via, "a colleague")
    researchlog.record(cx, "owner", f"The team may use {words}: a change in {_who(cx, by)}'s name (the owner's), "
                                    f"which came in {sender}'s file. If the owner did not make it, their next change "
                                    "replaces it.",
                       data={"setting": KEY, "providers": after["providers"] if after else None, "by": by, "via": via})
    return True


def view(ws) -> dict:
    """For the *AI providers* card of People and settings and the API (GET …/owner/providers):
    {"team", "can_set", "limit": {"providers", "titles", "by", "at"} | None, "choices": [{"id", "title"}],
     "label", "no_limit"}."""
    from . import ownership, people
    from .teamcodebooks import is_team

    me = people.me()
    cx = ws._conn()
    names = people.names(ws)
    lim = limit(cx)
    return {"team": is_team(cx, ws), "can_set": ownership.is_owner(ws, cx), "label": LABEL, "no_limit": NO_LIMIT,
            "limit": {"providers": lim["providers"], "titles": _titles(lim["providers"]),
                      "by": ownership._person(names, me, lim["by"]), "at": lim["at"]} if lim else None,
            "choices": [{"id": p, "title": _title(p) if p == providers.OTHER else providers.title(p),
                         "company": _title(p)} for p in providers.ALLOWABLE]}


def set_limit(ws, value: Any) -> dict:
    """The owner limits the providers the team may use (a list), or lifts the limit (None). NotAllowed for anyone
    else; ValueError for a list that is not one (empty, unknown providers). Logged in the research log, which travels
    to the team (who changed what, and its effect). Returns `view`."""
    from . import people, researchlog
    from .teamcodebooks import _counting, _own_n, _owner_only, _place, _write

    want = None if value is None else providers.clean_list(value)
    me = people.me()
    with ws.connect() as cx:
        _owner_only(ws, cx, "which providers the team may use")
        cur = _counting(cx).get(KEY)
        if (cur["value"] if cur else None) == want and (cur is not None or want is None):
            return view(ws)
        _write(cx, KEY, me, _place(cx), _own_n(cx, me) + 1, want)
        # the open tasks get their setting under the new limit now, in this transaction: a task its route may no
        # longer read leaves the queue, and one held for the limit is `cloud` again once it is lifted (as
        # access.set_providers_default does; a member's copy relabels at the end of the merge that brings the row)
        from .access import relabel

        relabel(cx)
        if want is None:
            researchlog.record(cx, "owner", "The team may use any cloud provider again: each person reads with the "
                                            "provider they choose, for the documents marked for cloud AI.",
                               data={"setting": KEY, "providers": None})
        else:
            researchlog.record(cx, "owner", f"The team may use {_titles(want)} only. Anyone whose route is another "
                                            "provider has their AI work on this project's documents held until the "
                                            "limit changes or they choose another route.",
                               data={"setting": KEY, "providers": want})
    return view(ws)
