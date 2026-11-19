"""Retractions and corrections (0.18.1, roadmap B5; and by title, for works without a DOI): the works of the bibliography and the
documents, looked up in Crossref, whose metadata carries Retraction Watch's retractions and the publishers'
corrections and expressions of concern as "updates" of the work. A plain lookup, no AI.

The first online lookup of works, so it keeps the rules of every online lookup:
- it runs only when the person asks (the button, `margin retractions --check`), never by itself;
- it follows each document's AI setting: a work whose document is marked *No AI* is not looked up;
- it is off under local-only: nothing is sent;
- it sends no name, no e-mail and no project name: a plain `User-Agent: Margin/<version>`, and only what follows.

By DOI (0.18.1): the DOI of every work of the bibliography and of every document is sent, and nothing else.

By title (the works that have no usable DOI): only a work of the bibliography (`bib_items`) is looked up, and only when
it has a title of at least three words, a year, a first author with a family name, and a published kind of item (a
journal article, book, book chapter, conference paper, report, thesis or preprint, as `bibliography.type_text` names
them; a manuscript, letter, e-mail, interview, web page, blog post, note, data set and an item of unknown type are
left out). What is sent is the title, the first author's family name and the year, in one request per work, and
nothing else. A work linked (or confirmed) to a document marked *No AI* is left out, and so is a work linked to a
*working* document (`documents.role`, the researcher's own draft). A document that has no DOI and no work of the
bibliography is never looked up by title: its title may be a file name or a private draft.

A title lookup is strict, because a wrong match would call a paper retracted that is not: a candidate counts only when
its title is (all but) the same, its year is within a year of the work's, its first author's family name is the work's,
and it is the only candidate that passes (two that pass: no match). The matched DOI's notices are then found as any DOI's.
The researcher sees the match beside the notice and may say *Not this work* (`reject_match`): that match is never shown
again: a later lookup never proposes that DOI for that work, and keeps the rejection unless another work alone
fits. A record titled as a notice ("Retraction note: …", "Correction to: …") is never a candidate.

Each answer is kept with its date in the table `retractions` (a DOI looked up and found clean is kept too, so the page
can say when it was last checked); a work's match by title in `retraction_matches`. Both are public facts about
published works or the researcher's own decision about a match, so both are shared with a team's folder like the other
project tables (neither is in `sync.common.LOCAL_ONLY`), and both go in a zip of the whole project. They travel by
the plain rule for such tables (a row not here yet comes in; a row here is kept): so a colleague's *Not this work* reaches
a copy that has no match for that work yet, not one that already holds the match, where it must be said again."""
from __future__ import annotations

import difflib
import json
import os
import re
import time
import unicodedata
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener

from . import __version__, access, home
from .store import Workspace, now
from .textutil import clean_doi

BASE_URL = "https://api.crossref.org"
BATCH = 20        # DOIs in one request (Crossref ORs a filter given several times)
MAX_DOIS = 2000   # a cap per lookup, so a huge library never becomes thousands of requests
PAUSE = 0.15      # seconds between two requests: politeness
MAX_TITLES = 300  # works looked up by title in one lookup: one request each
TITLE_ROWS = 5    # candidates asked for per work
ROWS = 1000
TIMEOUT = 25
SERIOUS = "retraction"  # what the page shows as serious; every other type is milder
_OPENER = build_opener()  # the system's proxy settings apply, as for the app's update check (a proxy is how some
#                           universities reach the internet at all)

# the kinds of item that are a published work (bibliography.type_text names them); every other kind, and no kind, is not
# looked up by title
PUBLISHED = {"Journal article", "Book", "Book chapter", "Conference paper", "Report", "Thesis", "Preprint"}

TYPE_TEXT = {"retraction": "Retracted", "correction": "Corrected", "expression_of_concern": "Expression of concern",
             "erratum": "Corrected", "corrigendum": "Corrected", "addendum": "Addendum", "withdrawal": "Withdrawn",
             "removal": "Removed", "new_edition": "New edition", "new_version": "New version"}


class RetractionError(Exception):
    """A lookup that cannot be made or did not work; the message is for the person."""


def norm_doi(doi: str | None) -> str | None:
    d = clean_doi(doi)
    return d if d and d.startswith("10.") else None


def _kind(t: str) -> str:
    return str(t or "").strip().lower().replace("-", "_").replace(" ", "_")


def serious(notices: list[dict]) -> bool:
    return any(n.get("type") in (SERIOUS, "withdrawal", "removal") for n in notices)


def _date(parts) -> str | None:
    try:
        ymd = [int(x) for x in (parts or [[]])[0]]
    except (TypeError, ValueError, IndexError):
        return None
    if not ymd:
        return None
    return "-".join(f"{n:02d}" if i else f"{n:04d}" for i, n in enumerate(ymd[:3]))


# -------------------------------------------------------------------------------------------------------- which DOIs
def _dois(ws: Workspace) -> dict[str, dict]:
    """{doi: {"items": [item_key], "docs": [doc_id]}} for every work of the bibliography and every document with a DOI;
    a document linked (or confirmed) to a work is a document of the work's DOI too."""
    out: dict[str, dict] = {}

    def entry(d):
        return out.setdefault(d, {"items": [], "docs": []})

    for r in ws.query("SELECT item_key, doi FROM bib_items WHERE doi IS NOT NULL AND doi<>'' ORDER BY seq"):
        d = norm_doi(r["doi"])
        if d:
            entry(d)["items"].append(r["item_key"])
    for r in ws.query("SELECT l.doc_id, b.doi FROM bib_links l JOIN bib_items b ON b.item_key=l.item_key "
                      "WHERE l.status IN ('auto', 'confirmed') AND b.doi IS NOT NULL AND b.doi<>''"):
        d = norm_doi(r["doi"])
        if d and r["doc_id"] not in entry(d)["docs"]:
            entry(d)["docs"].append(r["doc_id"])
    for r in ws.query("SELECT doc_id, doi FROM documents WHERE doi IS NOT NULL AND doi<>''"):
        d = norm_doi(r["doi"])
        if d and r["doc_id"] not in entry(d)["docs"]:
            entry(d)["docs"].append(r["doc_id"])
    return out


def plan(ws: Workspace) -> dict:
    """What a lookup would ask: {"ask": [DOIs], "no_ai": [DOIs left out], "capped": bool}."""
    found = _dois(ws)
    doc_ids = sorted({d for e in found.values() for d in e["docs"]})
    level = access.levels(ws, doc_ids) if doc_ids else {}
    ask, no_ai = [], []
    for d, e in found.items():
        # one document of the work marked No AI is enough to keep the work out: the person said no machine goes near it
        (no_ai if any(level.get(x) == "none" for x in e["docs"]) else ask).append(d)
    return {"ask": ask[:MAX_DOIS], "no_ai": no_ai, "capped": len(ask) > MAX_DOIS}


# ------------------------------------------------------------------------------------------- which works, by title
def _plain(s: str | None) -> str:
    """Letters and digits only, without accents, lower case, single spaces: how two titles or names are compared."""
    d = unicodedata.normalize("NFKD", str(s or ""))
    d = "".join(c for c in d if not unicodedata.combining(c)).lower()
    return " ".join("".join(c if c.isalnum() else " " for c in d).split())


def _first_family(creators: list[dict]) -> str | None:
    authors = [c for c in creators if isinstance(c, dict) and c.get("role") in (None, "author")]
    return (str(authors[0].get("last") or "").strip() or None) if authors else None


def _year(v) -> int | None:
    m = re.search(r"\b(\d{4})\b", str(v or ""))
    return int(m.group(1)) if m else None


def title_works(ws: Workspace) -> dict:
    """The works that would be looked up by title: {"works": [{"key", "title", "family", "year"}] (before the cap),
    "no_ai": [item_key], "working": [item_key]} (the last two: left out for the document they are linked to)."""
    from . import bibliography

    rows = ws.query("SELECT item_key, item_type, title, creators_json, year, doi FROM bib_items ORDER BY seq")
    cand = []
    for r in rows:
        if norm_doi(r["doi"]) or bibliography.type_text(r["item_type"]) not in PUBLISHED:
            continue
        title = re.sub(r"\s+", " ", str(r["title"] or "")).strip()
        try:
            family = _first_family(json.loads(r["creators_json"] or "[]"))
        except json.JSONDecodeError:
            family = None
        year = _year(r["year"])
        if len(title.split()) < 3 or not family or not year:
            continue
        cand.append({"key": r["item_key"], "title": title[:300], "family": family, "year": year})
    docs: dict[str, list[str]] = {}
    # a probable link counts too: when in doubt whether a work is a No-AI or working document, its title is not sent
    for r in ws.query("SELECT item_key, doc_id FROM bib_links WHERE status IN ('auto', 'confirmed', 'probable')"):
        docs.setdefault(r["item_key"], []).append(r["doc_id"])
    ids = sorted({d for c in cand for d in docs.get(c["key"], [])})
    level = access.levels(ws, ids) if ids else {}
    role = {r["doc_id"]: r["role"] for r in ws.query("SELECT doc_id, role FROM documents")} if ids else {}
    works, no_ai, working = [], [], []
    for c in cand:
        mine = docs.get(c["key"], [])
        if any(level.get(d) == "none" for d in mine):
            no_ai.append(c["key"])
        elif any(role.get(d) == "working" for d in mine):
            working.append(c["key"])
        else:
            works.append(c)
    return {"works": works, "no_ai": no_ai, "working": working}


def title_plan(ws: Workspace) -> dict:
    """What a lookup by title would ask: {"ask": works, "no_ai": works, "working": works (counts), "capped": bool}."""
    t = title_works(ws)
    return {"ask": min(len(t["works"]), MAX_TITLES), "no_ai": len(t["no_ai"]), "working": len(t["working"]),
            "capped": len(t["works"]) > MAX_TITLES}


# ------------------------------------------------------------------------------------------------ the match by title
_LABEL = re.compile(r"^\s*(retracted article|retracted|withdrawn)\s*:\s*", re.I)  # a retracted work's own title, as
#                                                              publishers write it; "Retraction: …" is a notice, no match
# a notice's own record, often not filed as an update (so `is-update:false` lets it through), titled after the work it
# is about: never a candidate, or a retracted work and its "Retraction note" would be two matches, and so none
_NOTICE = re.compile(r"^\s*(retraction( note| notice)?|notice of retraction|correction( note)?( to)?|erratum|"
                     r"corrigendum|expression of concern|editorial expression of concern|withdrawal|addendum)\b",
                     re.I)


def _years(it: dict) -> list[int]:
    out = []
    for k in ("issued", "published-print", "published-online"):
        try:
            out.append(int(((it.get(k) or {}).get("date-parts") or [[]])[0][0]))
        except (TypeError, ValueError, IndexError):
            pass
    return out


def _same_title(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    return (difflib.SequenceMatcher(None, a, b).ratio() >= 0.95
            and min(len(a), len(b)) >= 0.9 * max(len(a), len(b)))


def accepts(work: dict, it: dict) -> bool:
    """Whether the candidate `it` (a Crossref item) is the work: all of title, year and first author agree."""
    want = _plain(work["title"])
    raw = [str(t) for t in (it.get("title") or []) if isinstance(t, str)]
    if any(_NOTICE.match(t) for t in raw):
        return False
    titles = [_LABEL.sub("", t, count=1) for t in raw]
    if not any(_same_title(want, _plain(t)) for t in titles):
        return False
    if not any(abs(y - work["year"]) <= 1 for y in _years(it)):
        return False
    first = ((it.get("author") or [{}])[0] or {}).get("family")
    return bool(first) and _plain(first) == _plain(work["family"])


def _candidate(it: dict, work: dict) -> dict:
    a = ((it.get("author") or [{}])[0]) or {}
    ys = _years(it)
    year = min(ys, key=lambda y: abs(y - work["year"])) if ys else None
    return {"doi": norm_doi(it.get("DOI")), "title": str((it.get("title") or [""])[0]).strip()[:300],
            "year": str(year) if year else None,
            "author": ", ".join(x for x in (a.get("family"), a.get("given")) if x) or None}


def find_by_title(base: str, work: dict) -> tuple[list[dict], int]:
    """Ask Crossref for the work: (the candidates that pass `accepts`, without repeats; how many came back). The query
    holds the title, the first author's family name and the year, and the fixed filter and field list."""
    q = urlencode({"query.bibliographic": f"{work['title']} {work['family']} {work['year']}",
                   "filter": "is-update:false", "rows": TITLE_ROWS,
                   "select": "DOI,title,author,issued,published-print,published-online,type"})
    items = ((_get(f"{base}/works?{q}").get("message") or {}).get("items") or [])
    seen, ok = set(), []
    for it in items:
        if isinstance(it, dict) and norm_doi(it.get("DOI")) and accepts(work, it):
            c = _candidate(it, work)
            if c["doi"] not in seen:
                seen.add(c["doi"])
                ok.append(c)
    return ok, len(items)


def _look_by_title(ws: Workspace, base: str, works: list[dict], stamp: str, sleep, should_stop, progress, offset: int,
                   total: int) -> dict:
    """The lookup by title of `works`: each answer kept in `retraction_matches`. Returns the counts."""
    done = matched = ambiguous = 0
    for i, w in enumerate(works):
        if should_stop and should_stop():
            break
        if progress:
            progress(done=offset + i, total=total, phase="retractions")
        if i:
            sleep(PAUSE)
        ok, _n = find_by_title(base, w)
        done += 1
        with ws.connect() as cx:
            was = cx.execute("SELECT doi, rejected_at FROM retraction_matches WHERE item_key=?", (w["key"],)).fetchone()
            if was and was[1]:
                # the researcher said this work is not the one its title matched: that DOI is never a candidate for it
                # again, and the rejection stays unless another DOI alone fits (an ambiguous or empty answer must not
                # wipe it, or the same match would come back on the next lookup)
                ok = [c for c in ok if c["doi"] != was[0]]
                if len(ok) != 1:
                    ambiguous += len(ok) > 1
                    cx.execute("UPDATE retraction_matches SET checked_at=? WHERE item_key=?", (stamp, w["key"]))
                    continue
            if len(ok) > 1:  # two works fit: not this one, not that one
                ambiguous += 1
                ok = []
            if ok:
                m = ok[0]
                matched += 1
                cx.execute("INSERT OR REPLACE INTO retraction_matches(item_key, checked_at, doi, title, year, author, "
                           "rejected_at, rejected_by) VALUES (?,?,?,?,?,?,NULL,NULL)",
                           (w["key"], stamp, m["doi"], m["title"], m["year"], m["author"]))
            else:
                cx.execute("INSERT OR REPLACE INTO retraction_matches(item_key, checked_at) VALUES (?,?)",
                           (w["key"], stamp))
    return {"done": done, "matched": matched, "ambiguous": ambiguous}


# -------------------------------------------------------------------------------------------------------- the lookup
def _get(url: str) -> dict:
    req = Request(url, headers={"User-Agent": f"Margin/{__version__}", "Accept": "application/json"})
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except HTTPError as e:
        if e.code == 429:
            raise RetractionError("Crossref asked for fewer requests. Try again in a few minutes.") from None
        raise RetractionError(f"Crossref answered with an error ({e.code}). Try again later.") from None
    except (URLError, OSError, TimeoutError):
        raise RetractionError("Could not reach Crossref. Check the internet connection and try again.") from None
    except ValueError:
        raise RetractionError("Crossref sent an answer Margin could not read. Try again later.") from None


def _batch(base: str, dois: list[str], sleep: Callable[[float], None]) -> dict[str, list[dict]]:
    """Notices for one batch: {doi: [notice]}. The filter is repeated, once per DOI (Crossref ORs it); each notice
    says which work it updates, so a notice that updates a DOI outside the batch is ignored."""
    asked = set(dois)
    got: dict[str, list[dict]] = {}
    offset = 0
    while True:
        flt = ",".join(f"updates:{d}" for d in dois)
        url = f"{base}/works?filter={quote(flt, safe=':,/')}&rows={ROWS}&offset={offset}&select=DOI,update-to"
        msg = (_get(url).get("message") or {})
        items = msg.get("items") or []
        for it in items:
            for u in it.get("update-to") or []:
                target = norm_doi(u.get("DOI"))
                if target in asked:
                    notice = {"type": _kind(u.get("type") or u.get("label")), "doi": norm_doi(it.get("DOI")),
                              "date": _date((u.get("updated") or {}).get("date-parts")), "source": u.get("source")}
                    if notice not in got.setdefault(target, []):
                        got[target].append(notice)
        offset += len(items)
        if not items or offset >= int(msg.get("total-results") or 0) or offset >= 5 * ROWS:
            break
        sleep(PAUSE)
    # the works themselves: Retraction Watch's entries, and a publisher's notice deposited without a link of its own,
    # stand on the retracted work as `updated-by`
    sleep(PAUSE)
    flt = ",".join(f"doi:{d}" for d in dois)
    try:
        msg = _get(f"{base}/works?filter={quote(flt, safe=':,/')}&rows={len(dois)}&select=DOI,updated-by").get(
            "message") or {}
    except RetractionError as e:
        if "(400)" not in str(e):  # a server that does not know this filter: the notices above stand
            raise
        msg = {}
    for it in msg.get("items") or []:
        target = norm_doi(it.get("DOI"))
        if target not in asked:
            continue
        for u in it.get("updated-by") or []:
            notice = {"type": _kind(u.get("type") or u.get("label")), "doi": norm_doi(u.get("DOI")),
                      "date": _date((u.get("updated") or {}).get("date-parts")), "source": u.get("source")}
            if not any(n["type"] == notice["type"] and n["doi"] == notice["doi"] for n in got.get(target, [])):
                got.setdefault(target, []).append(notice)
    return got


def lookup(ws: Workspace, progress: Callable[..., None] | None = None, base_url: str | None = None,
           should_stop: Callable[[], bool] | None = None, sleep: Callable[[float], None] = time.sleep) -> dict:
    """Ask Crossref about the works: the works without a DOI by title (one request each), then the DOIs. Returns
    {"looked_up" (DOIs asked, those found by title included), "no_ai", "notices" (how many works have one), "capped",
    "checked_at", "by_title" (works looked up by title), "title_matched", "title_ambiguous", "title_capped"}. Raises
    RetractionError under local-only, and when Crossref cannot be reached (what was answered before is kept)."""
    if home.local_only():
        raise RetractionError("Online lookups are off on this computer (local-only), so nothing was sent.")
    base = (base_url or os.environ.get("MARGIN_CROSSREF_URL") or BASE_URL).rstrip("/")
    p = plan(ws)
    tp = title_works(ws)
    titles = tp["works"][:MAX_TITLES]
    ask, stamp = list(p["ask"]), now()
    t = {"done": 0, "matched": 0, "ambiguous": 0}
    if titles:
        t = _look_by_title(ws, base, titles, stamp, sleep, should_stop, progress, 0, len(titles) + len(ask))
        if t["done"] < len(titles):  # stopped
            return {"looked_up": 0, "no_ai": len(p["no_ai"]), "notices": 0, "capped": p["capped"], "checked_at": stamp,
                    "by_title": t["done"], "title_matched": t["matched"], "title_ambiguous": t["ambiguous"],
                    "title_capped": len(tp["works"]) > MAX_TITLES}
        ask += sorted(_matched_dois(titles, ws) - set(ask))  # the notices of a match are found as any DOI's
    base_done = len(titles)
    total = len(titles) + len(ask)
    done = found = 0
    for i in range(0, len(ask), BATCH):
        if should_stop and should_stop():
            break
        chunk = ask[i:i + BATCH]
        if progress:
            progress(done=base_done + done, total=total, phase="retractions")
        got = _batch(base, chunk, sleep)
        with ws.connect() as cx:
            cx.executemany("INSERT OR REPLACE INTO retractions(doi, checked_at, notices_json) VALUES (?,?,?)",
                           [(d, stamp, json.dumps(got.get(d, []), ensure_ascii=False)) for d in chunk])
        done += len(chunk)
        found += sum(1 for d in chunk if got.get(d))
        if i + BATCH < len(ask):
            sleep(PAUSE)
    if progress:
        progress(done=base_done + done, total=total, phase="retractions")
    return {"looked_up": done, "no_ai": len(p["no_ai"]), "notices": found, "capped": p["capped"], "checked_at": stamp,
            "by_title": t["done"], "title_matched": t["matched"], "title_ambiguous": t["ambiguous"],
            "title_capped": len(tp["works"]) > MAX_TITLES}


def _matched_dois(works: list[dict], ws: Workspace) -> set[str]:
    """The DOIs of the matches of `works` that stand (not rejected)."""
    keys = {w["key"] for w in works}
    return {r["doi"] for r in ws.query("SELECT item_key, doi FROM retraction_matches WHERE doi IS NOT NULL AND "
                                       "rejected_at IS NULL") if r["item_key"] in keys}


# -------------------------------------------------------------------------------------------------------- what is kept
def _kept(ws: Workspace) -> dict[str, dict]:
    out = {}
    for r in ws.query("SELECT doi, checked_at, notices_json FROM retractions"):
        try:
            notices = json.loads(r["notices_json"] or "[]")
        except json.JSONDecodeError:
            notices = []
        out[r["doi"]] = {"checked_at": r["checked_at"], "notices": notices}
    return out


def _matches(ws: Workspace) -> list[dict]:
    return [dict(r) for r in ws.query("SELECT item_key, checked_at, doi, title, year, author, rejected_at, rejected_by "
                                      "FROM retraction_matches")]


def status(ws: Workspace) -> dict:
    """What the last lookups found, for the page, the claim card and the command line:
    {"local_only": bool, "checked_at": the latest lookup or None, "checked": DOIs kept, "affected": DOIs with a notice,
     "by_doi": {doi: {"checked_at", "notices": [{type, doi, date, source}]}} (only DOIs with a notice),
     "by_item": {item_key: [notices]}, "by_doc": {doc_id: [notices]}} (notices carry "work_doi" and "checked_at";
     only works and documents with at least one notice), and (B5 by title) "title_matches": [{"item_key", "doi",
     "title", "year", "author", "checked_at", "notices"}] (the works without a DOI whose title matched a work of
     Crossref, with that work's notices; a match the researcher rejected is not listed and shows nowhere). A notice
     found by the title carries "found_by": "title" and "match": {"doi", "title", "year", "author"}."""
    kept = _kept(ws)
    found = _dois(ws)
    matches = _matches(ws)
    has_doi = {k for e in found.values() for k in e["items"]}
    live = [m for m in matches if m["doi"] and not m["rejected_at"] and m["item_key"] not in has_doi]
    gone = {m["doi"] for m in matches if m["doi"] and m["rejected_at"]} - set(found) - {m["doi"] for m in live}
    kept = {d: k for d, k in kept.items() if d not in gone}   # a DOI only a rejected match led to is no one's
    by_item: dict[str, list] = {}
    by_doc: dict[str, list] = {}
    for d, k in kept.items():
        if not k["notices"]:
            continue
        rows = [{**n, "work_doi": d, "checked_at": k["checked_at"]} for n in k["notices"]]
        for key in found.get(d, {}).get("items", []):
            by_item[key] = rows
        for doc in found.get(d, {}).get("docs", []):
            by_doc[doc] = rows
    title_matches = []
    linked: dict[str, list[str]] = {}
    for r in ws.query("SELECT item_key, doc_id FROM bib_links WHERE status IN ('auto', 'confirmed')"):
        linked.setdefault(r["item_key"], []).append(r["doc_id"])
    for m in live:
        k = kept.get(m["doi"]) or {"checked_at": m["checked_at"], "notices": []}
        card = {"doi": m["doi"], "title": m["title"], "year": m["year"], "author": m["author"]}
        rows = [{**n, "work_doi": m["doi"], "checked_at": k["checked_at"], "found_by": "title", "match": card}
                for n in k["notices"]]
        title_matches.append({"item_key": m["item_key"], **card, "checked_at": m["checked_at"], "notices": rows})
        if rows:
            by_item.setdefault(m["item_key"], rows)
            for doc in linked.get(m["item_key"], []):
                by_doc.setdefault(doc, rows)
    stamps = [k["checked_at"] for k in kept.values() if k["checked_at"]]
    return {"local_only": home.local_only(), "checked_at": max(stamps) if stamps else None, "checked": len(kept),
            "affected": sum(1 for k in kept.values() if k["notices"]),
            "by_doi": {d: k for d, k in kept.items() if k["notices"]}, "by_item": by_item, "by_doc": by_doc,
            "title_matches": title_matches}


def reject_match(ws: Workspace, item_key: str, reject: bool = True) -> dict:
    """*Not this work*: the researcher says the lookup by title matched the work to another one (`reject`), or takes
    that back. Kept with who and when, and written in the research log. Raises KeyError when the work has no match.
    Returns {"item_key", "doi", "title", "rejected": bool}."""
    from . import researchlog, solo as people  # Margin: one person

    with ws.connect() as cx:
        row = cx.execute("SELECT doi, title, rejected_at FROM retraction_matches WHERE item_key=? AND doi IS NOT NULL",
                         (item_key,)).fetchone()
        if not row:
            raise KeyError(item_key)
        doi, cand_title, was = row
        work = cx.execute("SELECT title FROM bib_items WHERE item_key=?", (item_key,)).fetchone()
        work_title = work[0] if work else None
        if bool(was) == reject:
            return {"item_key": item_key, "doi": doi, "title": cand_title, "rejected": reject, "changed": False}
        me = people.me()
        if reject:
            cx.execute("UPDATE retraction_matches SET rejected_at=?, rejected_by=? WHERE item_key=?",
                       (now(), me, item_key))
            said = (f"Not the same work: the lookup by title matched it to {doi} (“{cand_title or ''}”), which was "
                    "said to be another work. Its notices are no longer shown for it.")
        else:
            cx.execute("UPDATE retraction_matches SET rejected_at=NULL, rejected_by=NULL WHERE item_key=?", (item_key,))
            said = f"Same work after all: the match by title to {doi} (“{cand_title or ''}”) stands again."
        researchlog.record(cx, "retraction-match", said, "bib_item", item_key, work_title,
                           data={"doi": doi, "title": cand_title, "rejected": reject})
    return {"item_key": item_key, "doi": doi, "title": cand_title, "rejected": reject, "changed": True}


def for_docs(ws: Workspace) -> dict[str, list[dict]]:
    """{doc_id: notices} for the claim card."""
    return status(ws)["by_doc"]


def for_items(ws: Workspace) -> dict[str, list[dict]]:
    """{item_key: notices} for the bibliography's works."""
    return status(ws)["by_item"]


def text(n: dict) -> str:
    """One notice in words: 'Retracted (2023-04-12)'."""
    t = TYPE_TEXT.get(n.get("type") or "") or (n.get("type") or "notice").replace("_", " ").capitalize()
    return f"{t} ({n['date']})" if n.get("date") else t
