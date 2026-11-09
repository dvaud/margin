"""Margin is for one person (no shared projects). ENLENS's people.py, which knows the colleagues of a shared project
and keeps each person's judgements apart, is left out of Margin. The modules brought in from ENLENS 0.16 (notes, the
research log, history, codebooks) ask it who made something; here the answer is always you.
"""
from __future__ import annotations

import sqlite3
from typing import Iterable

ME = "me"


def me() -> str:
    """The person id written on what you make (notes, log entries, versions)."""
    return ME


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
