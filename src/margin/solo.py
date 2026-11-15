"""Margin is for one person (no shared projects). ENLENS's people.py (the colleagues of a shared project, each person's
judgements kept apart), sharing.py (private until shared), ownership.py (one owner, co-owners and proposals) and the
shared folder are left out of Margin. The modules brought in from ENLENS ask them who made something, whether it is
shared and who may decide; here the answer is always you: you are the only person and the owner, everything is yours,
nothing is shared.

ENLENS's modules import this module in their place (`from . import solo as people`, `solo as sharing`,
`solo as ownership`), so their lines stay as ENLENS writes them and later syncs merge cleanly.
"""
from __future__ import annotations

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
