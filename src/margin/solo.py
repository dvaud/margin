"""Margin is for one person (no shared projects). ENLENS's people.py (the colleagues of a shared project, each person's
judgements kept apart), sharing.py (private until shared), ownership.py (one owner, co-owners and proposals) and the
shared folder are left out of Margin. The modules brought in from ENLENS ask them who made something, whether it is
shared and who may decide; here the answer is always you: you are the only person and the owner, everything is yours,
nothing is shared.

ENLENS's modules import this module in their place (`from . import solo as people`, `solo as sharing`,
`solo as ownership`), so their lines stay as ENLENS writes them and later syncs merge cleanly.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any, Iterable

ME = "me"
UNKNOWN = ME  # ENLENS: the sender of a project zip made before 0.14 ("a colleague"); here, you


# -- people ---------------------------------------------------------------------------------------------------------
def me() -> str:
    """The person id written on what you make (notes, log entries, versions)."""
    return ME


def my_name() -> str:
    """Your name as a colleague would see it: Margin asks for none."""
    return ""


def names(ws=None) -> dict[str, str]:
    """{person_id: name}: you, and nobody else."""
    return {ME: "you"}


def record(cx: sqlite3.Connection, claim_id: str, passage_id: str, person_id: str, verdict: str | None,
           note: str | None, at: str | None, quote: str | None = None, start: int | None = None,
           end: int | None = None) -> None:
    """Your judgement of an excerpt, on its verification row (Margin keeps no table of each person's judgements)."""
    from .store import now

    if not verdict and not note:
        verdict = note = quote = start = end = None
    cx.execute("UPDATE verifications SET user_verdict=?, user_note=?, user_at=?, user_quote=?, user_start=?, "
               "user_end=? WHERE subject_kind='user_claim' AND subject_id=? AND passage_id=?",
               (verdict, note, (at or now()) if verdict or note else None, quote, start, end, claim_id, passage_id))


def refresh(cx: sqlite3.Connection, claim_ids: Iterable[str] | None = None, me_id: str | None = None) -> None:
    """Nothing to do: with one person, the judgement written is the one in force."""


def review_order(me_id: str | None = None) -> tuple[str, tuple]:
    """The ORDER BY of a query over `reviews` whose last row counts: in the order they were made (Margin's reviews
    name no person)."""
    return "ORDER BY review_id", ()


def mine_sql(me_id: str | None = None) -> tuple[str, tuple]:
    """A condition on `reviews` that keeps your own rows: every row is yours."""
    return "1=1", ()


# -- sharing (ENLENS: private until shared) -------------------------------------------------------------------------
def rows(cx: sqlite3.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    """{(kind, key): the row of its state}: none, since nothing is shared (ENLENS: no row means yours)."""
    return {}


def state(cx: sqlite3.Connection, kind: str, key: str) -> dict[str, Any]:
    """An item's state: yours, never shared."""
    return {"state": "private", "owner": ME, "mine": True}


# -- ownership (ENLENS: one owner, co-owners, members) --------------------------------------------------------------
def may_write(cx: sqlite3.Connection, person: str | None = None) -> bool:
    """Whether a person's word decides for the project: yours always does (you are the owner)."""
    return True


# -- ENLENS's team settings (teamcodebooks.py, teamproviders.py) and a person's second account (sharing._partner) ----
# ENLENS's modules import these under the names of the modules Margin leaves out (`solo as teamcodebooks`, ...).
ID_RE = re.compile(re.escape(ME))  # ENLENS: what a person id looks like; here, yours


def _my_id() -> str:
    """This installation's person id (ENLENS: teamcodebooks._my_id)."""
    return ME


def is_team(cx=None, ws=None) -> bool:
    """Whether the project is worked on with colleagues: never in Margin."""
    return False


def made(ws, name: str) -> None:
    """ENLENS shares a codebook made in a project when the team's setting says so; Margin shares nothing."""
    return None


def default_name(ws) -> None:
    """The project's default codebook set by its owner (ENLENS): none in Margin, which has no default codebook."""
    return None


def default_info(ws) -> None:
    return None


def codebooks_line(ws) -> None:
    """ENLENS's line about private codebooks while the team shares new ones: none here."""
    return None


def allows(cx, provider: str) -> bool:
    """Whether the team's limit lets this cloud provider read (ENLENS: teamproviders.allows): no team, no limit."""
    return True


def limit(cx) -> None:
    return None


def note(cx, provider: str | None = None) -> None:
    """The note of the team's limit of providers: none here."""
    return None


def _partner(cx, me_id: str | None = None) -> None:
    """Your other account in the team (ENLENS: two computers, two accounts of one person): none here."""
    return None

