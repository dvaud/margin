"""Finding literature (Margin, roadmap E1 to E3): online lookups that are not AI.

OpenAlex is the main source (Crossref and Semantic Scholar can be searched too, Unpaywall finds open copies). Nothing
here uses a language model; the words of a search are made on this computer, from the key terms of the documents and
the words of a claim, and the person sees and edits them before they are sent.

What may go out (the rule of docs/ROADMAP.md):

- nothing at all when cloud models are switched off for good on this computer (`--local-only`);
- a search built from a draft's words only when that draft's AI setting allows the cloud (the draft is then treated
  as the text it is: its words may leave);
- a lookup built from documents (their DOIs, to follow citations) only for documents whose setting allows the cloud;
- the e-mail address in Settings, if there is one, travels only to the services that use it (OpenAlex and Crossref
  `mailto`, Unpaywall `email`); Margin never fills it in by itself.

Every answer is kept in the project (`lit_cache`), so the same lookup is not repeated. The services' base addresses can
be changed with MARGIN_OPENALEX_URL, MARGIN_CROSSREF_URL, MARGIN_S2_URL and MARGIN_UNPAYWALL_URL (the tests and the
development server point them at stand-ins). Works found can be sent to Zotero (its connector on this computer) or
downloaded as RIS or BibTeX.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import time
import uuid
from collections import Counter, defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

from . import __version__, access, bibliography, home
from .store import Workspace, now
from .textutil import clean_doi, is_stop, token_spans, tokens

BASES = {"openalex": ("MARGIN_OPENALEX_URL", "https://api.openalex.org"),
         "crossref": ("MARGIN_CROSSREF_URL", "https://api.crossref.org"),
         "semanticscholar": ("MARGIN_S2_URL", "https://api.semanticscholar.org/graph/v1"),
         "unpaywall": ("MARGIN_UNPAYWALL_URL", "https://api.unpaywall.org/v2")}
NAMES = {"openalex": "OpenAlex", "crossref": "Crossref", "semanticscholar": "Semantic Scholar", "unpaywall": "Unpaywall"}
SITES = {"openalex": "openalex.org", "crossref": "crossref.org", "semanticscholar": "semanticscholar.org",
         "unpaywall": "unpaywall.org"}
SEARCH_SOURCES = ("openalex", "crossref", "semanticscholar")
TIMEOUT = 20
CACHE_DAYS = 14          # how long an answer is kept before the same lookup is asked again
OPEN_COPY_DAYS = 30
MAX_RESULTS = 50
MAX_OPEN_COPIES = 25
DEADLINE = 90            # seconds one "follow citations" may take before it shows what it has
STALE_HOURS = 6          # a saved search is looked at again when the page opens after this long
MAX_WORK_TEXT = 6000

STATUS = {"local_only": 403, "not_allowed": 403, "bad_request": 400, "no_email": 409, "offline": 502,
          "rate_limited": 502, "refused": 502, "failed": 502, "zotero_not_running": 409, "zotero_failed": 502}


class LiteratureError(ValueError):
    """`kind`: local_only, not_allowed (the AI setting of a draft or document), bad_request, no_email, offline,
    rate_limited, refused, failed, zotero_not_running or zotero_failed."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.status = STATUS.get(kind, 400)


# ---------------------------------------------------------------------------------------------
# what may go out
# ---------------------------------------------------------------------------------------------
def contact_email() -> str:
    """The address the person gave in Settings (for the polite pool of OpenAlex and Crossref, and for Unpaywall,
    which asks for one). Empty when they gave none; Margin never makes one up."""
    return str(home.load_settings().get("contact_email") or "").strip()


def allow_online() -> None:
    if home.local_only():
        raise LiteratureError("local_only", "Looking up literature online is switched off on this computer "
                                            "(cloud services are off for good here), so nothing is sent.")


def allow_draft(ws: Workspace, draft_id: str | None) -> None:
    """A lookup built from a draft's words goes out only when the draft's AI setting allows the cloud."""
    if not draft_id:
        return
    from . import drafts

    if not ws.scalar("SELECT 1 FROM drafts WHERE draft_id=?", (draft_id,)):
        raise LiteratureError("bad_request", "No such draft.")
    lv = drafts.level(ws, draft_id)
    if lv != "cloud":
        raise LiteratureError("not_allowed", "This draft is set so that its words stay on this computer "
                                             f"({access.LABEL.get(lv, lv).lower()}), so a search made from them is not "
                                             "sent. Type your own search words on the Find literature page instead, "
                                             "or change the draft's AI setting.")


def sendable_documents(ws: Workspace) -> dict[str, bool]:
    """{doc_id: whether lookups built from this document may go out} (its AI setting allows the cloud)."""
    allowed = access.levels(ws)
    return {d: lv == "cloud" for d, lv in allowed.items()}


# ---------------------------------------------------------------------------------------------
# the project's tables (made when first needed, so older projects need no migration)
# ---------------------------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS lit_cache(key TEXT PRIMARY KEY, source TEXT, fetched_at TEXT, expires REAL, body TEXT);
CREATE TABLE IF NOT EXISTS lit_searches(search_id TEXT PRIMARY KEY, title TEXT, words TEXT, kind TEXT, filters_json TEXT,
  draft_id TEXT, created_at TEXT, since TEXT, last_checked_at TEXT, new_count INT DEFAULT 0, error TEXT);
CREATE TABLE IF NOT EXISTS lit_found(search_id TEXT, work_key TEXT, work_json TEXT, found_at TEXT, seen INT DEFAULT 0,
  PRIMARY KEY(search_id, work_key));
"""
_READY: set[str] = set()


def _ensure(ws: Workspace) -> None:
    key = str(ws.db_path.resolve())
    if key in _READY:
        return
    with ws.connect() as cx:
        for statement in SCHEMA.split(";"):
            if statement.strip():
                cx.execute(statement)
    _READY.add(key)


# ---------------------------------------------------------------------------------------------
# talking to the services
# ---------------------------------------------------------------------------------------------
_DIRECT = build_opener(ProxyHandler({}))   # a stand-in on this computer is never reached through a proxy
_SYSTEM = build_opener()


def base_url(source: str) -> str:
    env, default = BASES[source]
    return (os.environ.get(env) or default).rstrip("/")


def _http(source: str, path: str, params: dict | None = None, timeout: float = TIMEOUT, allow_404: bool = False):
    """One request, answered as JSON. Plain-language errors: offline, rate limited, refused, failed."""
    url = base_url(source) + path + ("?" + urlencode(params, quote_via=quote) if params else "")
    req = Request(url, headers={"Accept": "application/json", "User-Agent": f"Margin/{__version__}"})
    opener = _DIRECT if access.on_this_computer(url) else _SYSTEM
    name = NAMES[source]
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read()
    except HTTPError as e:
        if e.code == 404 and allow_404:
            return None
        if e.code == 429:
            wait = e.headers.get("Retry-After") if e.headers else None
            raise LiteratureError("rate_limited", f"{name} is asking Margin to slow down (too many lookups just now). "
                                                  f"Try again in {('about ' + wait + ' seconds') if wait and wait.isdigit() else 'a minute'}"
                                                  ".") from None
        if e.code in (401, 403):
            raise LiteratureError("refused", f"{name} refused the lookup ({e.code}). It may now ask for a key or an "
                                             "address; try again later.") from None
        if e.code == 400:
            raise LiteratureError("failed", f"{name} did not understand the search ({e.code}). Try simpler words.") from None
        raise LiteratureError("failed", f"{name} had a problem ({e.code}). Try again later.") from None
    except (URLError, OSError, TimeoutError) as e:
        raise LiteratureError("offline", f"Margin could not reach {name}. Are you online? ({getattr(e, 'reason', e)})") from None
    try:
        return json.loads(body or b"null")
    except json.JSONDecodeError:
        raise LiteratureError("failed", f"{name} answered, but not in a form Margin can read.") from None


def _key(source: str, path: str, params: dict | None) -> str:
    keep = {k: v for k, v in (params or {}).items() if k not in ("mailto", "email")}
    raw = f"{source}|{path}|{json.dumps(keep, sort_keys=True, default=str)}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _cached(ws: Workspace, source: str, path: str, params: dict | None, parse, *, days: float = CACHE_DAYS,
            fresh: bool = False, allow_404: bool = False):
    """The parsed answer of a lookup: from the project when the same lookup was made lately, else from the service."""
    _ensure(ws)
    key = _key(source, path, params)
    if not fresh:
        row = ws.query("SELECT body FROM lit_cache WHERE key=? AND expires>?", (key, time.time()))
        if row:
            return json.loads(row[0]["body"])
    allow_online()
    raw = _http(source, path, params, allow_404=allow_404)
    out = parse(raw)
    with ws.connect() as cx:
        cx.execute("INSERT OR REPLACE INTO lit_cache(key, source, fetched_at, expires, body) VALUES (?,?,?,?,?)",
                   (key, source, now(), time.time() + days * 86400, json.dumps(out, ensure_ascii=False)))
    return out


def forget_cache(ws: Workspace) -> int:
    _ensure(ws)
    n = int(ws.scalar("SELECT COUNT(*) FROM lit_cache") or 0)
    with ws.connect() as cx:
        cx.execute("DELETE FROM lit_cache")
    return n


# ---------------------------------------------------------------------------------------------
# works: one shape for every service
# ---------------------------------------------------------------------------------------------
def _clean_text(s, limit: int = 600) -> str:
    s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()
    return s[:limit]


def work_key(w: dict) -> str:
    if w.get("doi"):
        return "doi:" + w["doi"]
    if w.get("openalex_id"):
        return "oa:" + w["openalex_id"]
    return "t:" + _fold_title(w.get("title") or "") + "|" + str(w.get("year") or "")


def _fold_title(t: str) -> str:
    return " ".join(tokens(t, keep_stop=True))


def _work(source: str, *, title, authors, year, venue=None, doi=None, url=None, abstract=None, cited_by=0, type_=None,
          openalex_id=None, open_=None, volume=None, issue=None, pages=None, refs=None) -> dict:
    w = {"source": source, "title": _clean_text(title, 500), "authors": [_clean_text(a, 120) for a in authors if a][:40],
         "year": int(year) if str(year or "").isdigit() else None, "venue": _clean_text(venue, 300) or None,
         "doi": clean_doi(doi) if doi else None, "url": str(url).strip() if url else None,
         "abstract": _clean_text(abstract, MAX_WORK_TEXT) or None, "cited_by": int(cited_by or 0), "type": type_,
         "openalex_id": openalex_id, "open": open_, "volume": _clean_text(volume, 40) or None,
         "issue": _clean_text(issue, 40) or None, "pages": _clean_text(pages, 40) or None}
    if refs is not None:
        w["refs"] = refs
    if not w["url"] and w["doi"]:
        w["url"] = "https://doi.org/" + w["doi"]
    w["key"] = work_key(w)
    return w


def _short_oa(i: str | None) -> str | None:
    m = re.search(r"\bW\d+\b", str(i or ""))
    return m.group(0) if m else None


def _uninvert(idx) -> str:
    """An abstract OpenAlex gives as {word: [positions]}, as text."""
    if not isinstance(idx, dict):
        return ""
    slots: dict[int, str] = {}
    for word, places in idx.items():
        for p in places or []:
            if isinstance(p, int):
                slots[p] = word
    return " ".join(slots[i] for i in sorted(slots))


def _oa_work(w: dict, refs: bool = False) -> dict:
    loc = w.get("best_oa_location") or {}
    oa = w.get("open_access") or {}
    prim = w.get("primary_location") or {}
    opened = None
    if oa.get("is_oa") or loc:
        link = loc.get("landing_page_url") or oa.get("oa_url")
        pdf = loc.get("pdf_url") or (oa.get("oa_url") if str(oa.get("oa_url") or "").lower().endswith(".pdf") else None)
        if link or pdf:
            opened = {"url": link or pdf, "pdf_url": pdf, "license": loc.get("license"),
                      "status": oa.get("oa_status"), "found_by": "OpenAlex"}
    bib = w.get("biblio") or {}
    pages = "-".join(str(x) for x in (bib.get("first_page"), bib.get("last_page")) if x) or None
    return _work("openalex", title=w.get("title") or w.get("display_name"),
                 authors=[(a.get("author") or {}).get("display_name") for a in w.get("authorships") or []],
                 year=w.get("publication_year"), venue=(prim.get("source") or {}).get("display_name"),
                 doi=w.get("doi"), url=prim.get("landing_page_url"), abstract=_uninvert(w.get("abstract_inverted_index")),
                 cited_by=w.get("cited_by_count"), type_=w.get("type"), openalex_id=_short_oa(w.get("id")), open_=opened,
                 volume=bib.get("volume"), issue=bib.get("issue"), pages=pages,
                 refs=[_short_oa(r) for r in w.get("referenced_works") or [] if _short_oa(r)] if refs else None)


def _cr_year(item: dict):
    for k in ("issued", "published-print", "published-online", "published"):
        parts = ((item.get(k) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            return parts[0]
    return None


def _cr_work(it: dict) -> dict:
    authors = [(a.get("name") or f"{a.get('given', '')} {a.get('family', '')}").strip() for a in it.get("author") or []]
    return _work("crossref", title=(it.get("title") or [""])[0], authors=authors, year=_cr_year(it),
                 venue=(it.get("container-title") or [""])[0], doi=it.get("DOI"), url=it.get("URL"),
                 abstract=it.get("abstract"), cited_by=it.get("is-referenced-by-count"),
                 type_={"journal-article": "article", "posted-content": "preprint", "proceedings-article": "conference",
                        "book-chapter": "book-chapter", "dissertation": "dissertation"}.get(it.get("type"), it.get("type")),
                 volume=it.get("volume"), issue=it.get("issue"), pages=it.get("page"))


def _s2_work(p: dict) -> dict:
    pdf = (p.get("openAccessPdf") or {}).get("url")
    return _work("semanticscholar", title=p.get("title"), authors=[a.get("name") for a in p.get("authors") or []],
                 year=p.get("year"), venue=p.get("venue"), doi=(p.get("externalIds") or {}).get("DOI"), url=p.get("url"),
                 abstract=p.get("abstract"), cited_by=p.get("citationCount"),
                 open_={"url": pdf, "pdf_url": pdf, "license": None, "status": None, "found_by": "Semantic Scholar"}
                 if pdf else None)


OA_SELECT = ("id,doi,title,display_name,publication_year,type,authorships,primary_location,best_oa_location,open_access,"
             "cited_by_count,abstract_inverted_index,biblio")


def _polite(params: dict, source: str) -> dict:
    mail = contact_email()
    if mail and source in ("openalex", "crossref"):
        params = {**params, "mailto": mail}
    return params


# ---------------------------------------------------------------------------------------------
# search words, made on this computer
# ---------------------------------------------------------------------------------------------
# words that say how a claim is made, not what it is about
GENERIC = frozenset("according several recent recently studies study shows show shown found finds finding findings report "
                    "reports reported research researchers evidence suggest suggests often many most also however across "
                    "about among between still every those these their which while where since within without whether "
                    "because overall generally typically usually really very much more less".split())


def search_words(ws: Workspace | None, text: str, n: int = 6) -> dict:
    """Search words for a claim or a question: the corpus's own key terms and concepts that the text contains (a term
    of several words is kept whole and quoted), then its other content words. No model is involved."""
    spans = token_spans(text or "", keep_stop=True)
    if not spans:
        return {"words": "", "terms": []}
    found: list[tuple[float, int, int, str]] = []   # (score, first word, last word, label)
    if ws is not None:
        grams: dict[str, tuple[int, int]] = {}
        for i in range(len(spans)):
            if is_stop(spans[i][3]):
                continue
            for j in range(i, min(len(spans), i + 4)):
                if is_stop(spans[j][3]):
                    continue
                grams.setdefault(" ".join(s[2] for s in spans[i:j + 1]), (i, j))
        keys = list(grams)
        try:
            for a in range(0, len(keys), 400):
                chunk = keys[a:a + 400]
                for r in ws.query(f"SELECT label, stems, df, cvalue, n_words FROM terms WHERE stems IN "
                                  f"({','.join('?' * len(chunk))})", chunk):
                    i, j = grams[r["stems"]]
                    score = (r["cvalue"] or 0) + 0.5 * (r["n_words"] or 1) + math.log1p(r["df"] or 0) * 0.1
                    found.append((score, i, j, r["label"]))
        except Exception:  # noqa: BLE001 - no term index yet
            found = []
    found.sort(key=lambda x: (-x[0], x[1]))
    chosen: list[tuple[int, int, str]] = []
    for _s, i, j, label in found:
        if any(not (j < a or i > b) for a, b, _l in chosen):
            continue
        chosen.append((i, j, label))
        if len(chosen) >= 4:
            break
    used = {k for i, j, _l in chosen for k in range(i, j + 1)}
    extra: list[tuple[int, str]] = []
    seen: set[str] = set()
    for k, (_a, _b, st, w) in enumerate(spans):
        if k in used or is_stop(w) or len(w) < 4 or st in seen or w.isdigit() or w in GENERIC:
            continue
        seen.add(st)
        extra.append((k, w))
    room = max(0, n - len(chosen))
    picks = extra[:max(room, 2 if not chosen else 0)]   # the words the claim opens with name what it is about
    parts = sorted([(i, f'"{l}"' if " " in l.strip() else l) for i, _j, l in chosen] + [(k, w) for k, w in picks])
    return {"words": " ".join(p for _k, p in parts), "terms": [l for _i, _j, l in chosen]}


# ---------------------------------------------------------------------------------------------
# E1: search
# ---------------------------------------------------------------------------------------------
def _clean_words(words) -> str:
    w = re.sub(r"\s+", " ", str(words or "")).strip()
    if not w:
        raise LiteratureError("bad_request", "Give the words to search for.")
    return w[:300]


def _year(v) -> int | None:
    try:
        y = int(v)
    except (TypeError, ValueError):
        return None
    return y if 1000 <= y <= 3000 else None


def what_is_sent(words: str, source: str = "openalex") -> dict:
    """What a search sends, in words, for the page to show before it goes."""
    mail = contact_email()
    return {"service": NAMES[source], "site": SITES[source], "words": words,
            "email": mail if mail and source in ("openalex", "crossref") else "",
            "text": f"Only these search words go to {NAMES[source]} ({SITES[source]}): {words}"}


def search(ws: Workspace, words: str, *, source: str = "openalex", from_year=None, oa_only: bool = False,
           limit: int = 25, draft_id: str | None = None, fresh: bool = False) -> dict:
    """Works matching the words. Raises LiteratureError when the lookup may not go out or the service cannot be
    reached. The words are exactly what is sent."""
    allow_online()
    allow_draft(ws, draft_id)
    if source not in SEARCH_SOURCES:
        raise LiteratureError("bad_request", "Search OpenAlex, Crossref or Semantic Scholar.")
    words = _clean_words(words)
    limit = max(1, min(int(limit or 25), MAX_RESULTS))
    year = _year(from_year)
    if source == "openalex":
        flt = ([f"from_publication_date:{year}-01-01"] if year else []) + (["is_oa:true"] if oa_only else [])
        params = {"search": words, "per-page": limit, "select": OA_SELECT, **({"filter": ",".join(flt)} if flt else {})}
        works = _cached(ws, "openalex", "/works", _polite(params, source),
                        lambda r: [_oa_work(x) for x in (r or {}).get("results") or []], fresh=fresh)
    elif source == "crossref":
        params = {"query.bibliographic": words, "rows": limit,
                  **({"filter": f"from-pub-date:{year}"} if year else {})}
        works = _cached(ws, "crossref", "/works", _polite(params, source),
                        lambda r: [_cr_work(x) for x in ((r or {}).get("message") or {}).get("items") or []], fresh=fresh)
    else:
        params = {"query": words, "limit": limit, "fields": "title,year,authors,externalIds,abstract,venue,citationCount,"
                  "openAccessPdf,url", **({"year": f"{year}-"} if year else {}), **({"openAccessPdf": ""} if oa_only else {})}
        works = _cached(ws, "semanticscholar", "/paper/search", params,
                        lambda r: [_s2_work(x) for x in (r or {}).get("data") or []], fresh=fresh)
    works = [w for w in works if w.get("title")]
    if oa_only:
        works = [w for w in works if w.get("open")]
    return {"works": works, "source": source, "service": NAMES[source], "words": words}


def open_copies(ws: Workspace, dois: list[str], *, fresh: bool = False) -> dict:
    """Open copies of works by DOI, from Unpaywall (which asks for an e-mail address; Margin uses the one in Settings
    and never makes one up). {doi: open copy or None}"""
    allow_online()
    mail = contact_email()
    if not mail:
        raise LiteratureError("no_email", "Unpaywall asks for an e-mail address with each lookup. Add yours in "
                                          "Settings (Exploring) to use it; OpenAlex's own open-access links need none.")
    out: dict[str, dict | None] = {}
    for d in [clean_doi(x) for x in dois or []][:MAX_OPEN_COPIES]:
        if not d or not d.startswith("10."):
            continue

        def parse(r):
            if not r or not r.get("is_oa"):
                return None
            b = r.get("best_oa_location") or {}
            url = b.get("url_for_landing_page") or b.get("url")
            pdf = b.get("url_for_pdf")
            return {"url": url or pdf, "pdf_url": pdf, "license": b.get("license"), "status": r.get("oa_status"),
                    "found_by": "Unpaywall"} if (url or pdf) else None

        out[d] = _cached(ws, "unpaywall", "/" + quote(d, safe="/"), {"email": mail}, parse, days=OPEN_COPY_DAYS,
                         fresh=fresh, allow_404=True)
    return out


# ---------------------------------------------------------------------------------------------
# what the person already has, and how close a work is
# ---------------------------------------------------------------------------------------------
def known(ws: Workspace) -> dict:
    """The documents and the bibliography's works, by DOI and by title, to mark a work found as already there."""
    by_doi: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    for r in ws.query("SELECT doc_id, title, file_title, doi FROM documents"):
        info = {"where": "documents", "title": r["title"], "doc_id": r["doc_id"]}
        if r["doi"]:
            by_doi.setdefault(clean_doi(r["doi"]), info)
        for t in (r["title"], r["file_title"]):
            if t and len(tokens(t)) >= 3:
                by_title.setdefault(_fold_title(t), info)
    try:
        for r in ws.query("SELECT i.item_key, i.title, i.doi, i.year, (SELECT 1 FROM bib_links l WHERE l.item_key=i.item_key "
                          "AND l.status!='rejected' LIMIT 1) AS linked FROM bib_items i"):
            info = {"where": "documents" if r["linked"] else "bibliography", "title": r["title"]}
            if r["doi"]:
                by_doi.setdefault(clean_doi(r["doi"]), info)
            if r["title"] and len(tokens(r["title"])) >= 3:
                by_title.setdefault(_fold_title(r["title"]), info)
    except Exception:  # noqa: BLE001 - no bibliography table in an older project
        pass
    return {"doi": by_doi, "title": by_title}


def mark_known(ws: Workspace, works: list[dict], index: dict | None = None) -> list[dict]:
    idx = index or known(ws)
    for w in works:
        have = (idx["doi"].get(w["doi"]) if w.get("doi") else None) or (
            idx["title"].get(_fold_title(w["title"])) if w.get("title") and len(tokens(w["title"])) >= 3 else None)
        w["have"] = have
    return works


def _embedder(ws: Workspace):
    """The local embedding model, when the project has vectors from one that runs on this computer (a draft's words
    are never sent to an embedding server elsewhere)."""
    from . import embed

    try:
        s = home.load_settings()
        emb = home.make_embedder(s)
        if emb is None or embed.remote(emb) or not ws.scalar("SELECT 1 FROM embeddings WHERE model=? LIMIT 1", (emb.model,)):
            return None
        return emb
    except Exception:  # noqa: BLE001 - a bad setting never stops a search
        return None


def _cos(a, b) -> float:
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _text_of(w: dict) -> str:
    return (w.get("title") or "") + ". " + (w.get("abstract") or "")[:700]


def _overlap_score(want: set[str], w: dict) -> float:
    if not want:
        return 0.0
    title = set(tokens(w.get("title") or ""))
    body = set(tokens(w.get("abstract") or ""))
    return min(1.0, (2 * len(want & title) + len(want & (body - title))) / (2 * len(want)))


def rank(ws: Workspace, works: list[dict], query: str, embedder="auto") -> dict:
    """Order works by closeness to `query`: by meaning with a local embedding model when the project has one, else by
    the words they share. Adds `closeness` (0 to 1) to each; returns {"works", "by", "note"}."""
    by, note = "words", ""
    emb = _embedder(ws) if embedder == "auto" else embedder
    scores: list[float] | None = None
    if emb is not None and works:
        from . import embed

        try:
            q = embed.query_vector(emb, query)
            _qp, dp = embed.prefixes(emb.model)
            docs: list[list[float]] = []
            for i in range(0, len(works), 32):
                docs += emb.embed([dp + _text_of(w) for w in works[i:i + 32]])
            scores = [max(0.0, _cos(q, d)) for d in docs]
            by = "meaning"
        except Exception as e:  # noqa: BLE001
            note = "The embedding model could not be used just now, so the works are ordered by the words they share."
            scores = None
            _ = e
    if scores is None:
        want = set(tokens(query))
        scores = [_overlap_score(want, w) for w in works]
    for w, s in zip(works, scores):
        w["closeness"] = round(float(s), 3)
    order = sorted(range(len(works)), key=lambda i: (-works[i]["closeness"], -math.log1p(works[i]["cited_by"]), i))
    return {"works": [works[i] for i in order], "by": by, "note": note}


def find_for_text(ws: Workspace, words: str, text: str | None = None, **kw) -> dict:
    """A search, ranked against `text` (the claim; else the words) and marked with what the person already has."""
    out = search(ws, words, **kw)
    r = rank(ws, out["works"], text or words)
    out["works"] = mark_known(ws, r["works"])
    out["ranked_by"], out["note"] = r["by"], r["note"]
    return out


# ---------------------------------------------------------------------------------------------
# E1: the claims of a draft that no document supports
# ---------------------------------------------------------------------------------------------
NEEDS = ("unsupported", "no_passages", "uncertain")


def draft_claims(ws: Workspace, draft_id: str) -> dict:
    """A draft's claims that no document supports (nothing read backs them, or nothing close enough was found), each
    with suggested search words. The draft's words are not sent here; whether a search from it may go out is
    `searchable`."""
    from . import drafts

    v = drafts.view(ws, draft_id)
    lv = v["draft"]["ai_access"]
    online = not home.local_only()
    claims = []
    for c in v["claims"]:
        if c["skip"] or c.get("decision") == "dismissed":
            continue
        if c.get("status") in NEEDS:
            claims.append({"claim_id": c["claim_id"], "n": len(claims) + 1, "claim": c["claim"], "status": c["status"],
                           "status_text": c.get("status_text"), "cited": c["cited"],
                           **search_words(ws, c["claim"])})
    return {"draft": {"draft_id": draft_id, "title": v["draft"]["title"], "ai_access": lv, "ai_label": v["draft"]["ai_label"]},
            "claims": claims, "searchable": online and lv == "cloud",
            "why_not": ("" if online and lv == "cloud" else
                        "Looking up literature online is switched off on this computer." if not online else
                        f"This draft is set to “{v['draft']['ai_label']}”, so a search made from its words is not sent.")}


# ---------------------------------------------------------------------------------------------
# E2: follow citations
# ---------------------------------------------------------------------------------------------
def _theme_sets(ws: Workspace) -> list[dict]:
    """The corpus's themes as sets of words (from the latest set of themes), else its most common terms as one."""
    out: list[dict] = []
    run = ws.query("SELECT run_id FROM theme_runs ORDER BY created_at DESC LIMIT 1")
    if run:
        for r in ws.query("SELECT name, terms_json FROM themes WHERE run_id=? AND removed_at IS NULL", (run[0]["run_id"],)):
            terms = [str(t) for t in json.loads(r["terms_json"] or "[]")]
            if terms:
                out.append({"name": r["name"] or ", ".join(terms[:3]), "terms": terms})
    if not out:
        top = [r["label"] for r in ws.query("SELECT label FROM terms ORDER BY df DESC, cvalue DESC LIMIT 25")]
        if top:
            out.append({"name": "your documents' most common terms", "terms": top})
    return out


def theme_closeness(ws: Workspace, works: list[dict], embedder="auto") -> str:
    """Add `theme_close` (0 to 1) and `theme` (the closest) to each work. Returns how it was measured."""
    themes = _theme_sets(ws)
    if not themes:
        for w in works:
            w["theme_close"], w["theme"] = 0.0, None
        return "none"
    emb = _embedder(ws) if embedder == "auto" else embedder
    if emb is not None and works and len(works) <= 400:
        from . import embed

        try:
            _qp, dp = embed.prefixes(emb.model)
            tv = []
            for i in range(0, len(themes), 32):
                tv += emb.embed([embed.prefixes(emb.model)[0] + ", ".join(t["terms"]) for t in themes[i:i + 32]])
            wv: list[list[float]] = []
            for i in range(0, len(works), 32):
                wv += emb.embed([dp + _text_of(w) for w in works[i:i + 32]])
            for w, v in zip(works, wv):
                sims = [max(0.0, _cos(v, t)) for t in tv]
                best = max(range(len(sims)), key=lambda k: sims[k])
                w["theme_close"], w["theme"] = round(sims[best], 3), themes[best]["name"]
            return "meaning"
        except Exception:  # noqa: BLE001
            pass
    sets = [(t["name"], {s for term in t["terms"] for s in tokens(term)}) for t in themes]
    for w in works:
        have = set(tokens(_text_of(w)))
        best = max(sets, key=lambda t: len(t[1] & have) / (len(t[1]) or 1))
        w["theme_close"] = round(len(best[1] & have) / (len(best[1]) or 1), 3)
        w["theme"] = best[0]
    return "words"


def citation_plan(ws: Workspace) -> dict:
    """Which documents their DOIs would be sent for, and which are left out (no AI setting that allows it, or no DOI).
    Nothing is sent."""
    plan = _plan(ws)
    plan.pop("_by_doi")
    return plan


def _plan(ws: Workspace) -> dict:
    allowed = sendable_documents(ws)
    links: dict[str, set[str]] = defaultdict(set)
    try:
        for r in ws.query("SELECT l.doc_id, i.doi FROM bib_links l JOIN bib_items i ON i.item_key=l.item_key WHERE "
                          "l.status!='rejected' AND i.doi IS NOT NULL AND i.doi != ''"):
            links[r["doc_id"]].add(clean_doi(r["doi"]))
    except Exception:  # noqa: BLE001
        pass
    docs, dois = [], {}
    for r in ws.query("SELECT doc_id, title, doi FROM documents ORDER BY title"):
        ds = ({clean_doi(r["doi"])} if r["doi"] else set()) | links.get(r["doc_id"], set())
        ds = {d for d in ds if d and d.startswith("10.")}
        ok = allowed.get(r["doc_id"], False)
        reason = None if ok and ds else ("not_allowed" if not ok else "no_doi")
        docs.append({"doc_id": r["doc_id"], "title": r["title"], "dois": sorted(ds), "included": reason is None,
                     "reason": reason})
        if reason is None:
            for d in ds:
                dois.setdefault(d, []).append(r["doc_id"])
    return {"documents": docs, "dois": sorted(dois), "included": sum(1 for d in docs if d["included"]),
            "not_allowed": sum(1 for d in docs if d["reason"] == "not_allowed"),
            "no_doi": sum(1 for d in docs if d["reason"] == "no_doi"), "_by_doi": dois}


def _oa_ids_filter(ids: list[str]) -> str:
    return "|".join(ids)


def follow_citations(ws: Workspace, *, fresh: bool = False, cap: int = 150, deadline: float = DEADLINE) -> dict:
    """The works the documents cite, and the works that cite them (OpenAlex), ranked by how many of the documents they
    connect to and then by closeness to the corpus's themes. Only documents whose AI setting allows the cloud are
    used. Works already in the documents or the bibliography are marked."""
    allow_online()
    plan = _plan(ws)
    by_doi = plan.pop("_by_doi")
    if not by_doi:
        raise LiteratureError("bad_request", "No document has a DOI that may be looked up. Add documents with a DOI, or "
                                             "bring in your Zotero library on the Bibliography page.")
    t0 = time.time()
    partial = False
    titles = {d["doc_id"]: d["title"] for d in plan["documents"]}
    dois = sorted(by_doi)

    def get(params: dict):
        return _cached(ws, "openalex", "/works", _polite(params, "openalex"),
                       lambda r: [_oa_work(x, refs=True) for x in (r or {}).get("results") or []], fresh=fresh)

    # 1. the documents themselves, with the works each cites
    seeds: dict[str, dict] = {}
    for i in range(0, len(dois), 40):
        for w in get({"filter": "doi:" + "|".join(dois[i:i + 40]), "per-page": 50, "select": OA_SELECT + ",referenced_works"}):
            if w.get("openalex_id") and w.get("doi") in by_doi:
                seeds[w["openalex_id"]] = w
    seed_docs = {oid: by_doi[w["doi"]] for oid, w in seeds.items()}
    cited: dict[str, set[str]] = defaultdict(set)
    for oid, w in seeds.items():
        for ref in w.get("refs") or []:
            if ref not in seeds:
                cited[ref].update(seed_docs[oid])
    ranked_refs = sorted(cited, key=lambda r: (-len(cited[r]), r))[:cap]
    # 2. the works cited, in full
    cited_works: list[dict] = []
    for i in range(0, len(ranked_refs), 50):
        if time.time() - t0 > deadline:
            partial = True
            break
        for w in get({"filter": "openalex:" + _oa_ids_filter(ranked_refs[i:i + 50]), "per-page": 50, "select": OA_SELECT}):
            w["docs"] = sorted(cited.get(w.get("openalex_id"), ()))
            cited_works.append(w)
    # 3. the works that cite the documents
    citing: dict[str, dict] = {}
    seed_ids = sorted(seeds)
    for i in range(0, len(seed_ids), 25):
        if time.time() - t0 > deadline:
            partial = True
            break
        group = set(seed_ids[i:i + 25])
        for w in get({"filter": "cites:" + _oa_ids_filter(seed_ids[i:i + 25]), "per-page": 100,
                      "sort": "cited_by_count:desc", "select": OA_SELECT + ",referenced_works"}):
            oid = w.get("openalex_id")
            if not oid or oid in seeds:
                continue
            hit = citing.setdefault(oid, w)
            hit.setdefault("_docs", set()).update(d for r in w.get("refs") or [] if r in group for d in seed_docs[r])
    citing_works = []
    for w in citing.values():
        w["docs"] = sorted(w.pop("_docs", ()))
        w.pop("refs", None)
        if w["docs"]:
            citing_works.append(w)
    index = known(ws)
    out = {}
    for name, ws_ in (("cited", cited_works), ("citing", citing_works)):
        measured = theme_closeness(ws, ws_)
        mark_known(ws, ws_, index)
        for w in ws_:
            w["n_docs"] = len(w["docs"])
            w["doc_titles"] = [titles.get(d) or d for d in w["docs"]]
            w.pop("refs", None)
        ws_.sort(key=lambda w: (-w["n_docs"], -w["theme_close"], -w["cited_by"], w["title"]))
        out[name] = ws_
        out["closeness_by"] = measured
    return {**out, "documents": plan["included"], "not_allowed": plan["not_allowed"], "no_doi": plan["no_doi"],
            "found_in_openalex": len(seeds), "partial": partial, "dois": len(dois),
            "cited_cap": cap if len(cited) > cap else None}


# ---------------------------------------------------------------------------------------------
# E3: saved searches and what is new
# ---------------------------------------------------------------------------------------------
def _today() -> str:
    return now()[:10]


def _search_row(r) -> dict:
    return {"search_id": r["search_id"], "title": r["title"], "words": r["words"], "kind": r["kind"],
            "filters": json.loads(r["filters_json"] or "{}"), "draft_id": r["draft_id"] or None,
            "created_at": r["created_at"], "since": r["since"], "last_checked_at": r["last_checked_at"],
            "new": int(r["new_count"] or 0), "error": r["error"] or None}


def save_search(ws: Workspace, words: str, *, title: str | None = None, kind: str = "search", from_year=None,
                oa_only: bool = False, draft_id: str | None = None) -> dict:
    """Keep a search (words and filters, or a research question) to be looked at again. Nothing is sent now."""
    _ensure(ws)
    words = _clean_words(words)
    if draft_id:
        if not ws.scalar("SELECT 1 FROM drafts WHERE draft_id=?", (draft_id,)):
            raise LiteratureError("bad_request", "No such draft.")
    sid = "s" + uuid.uuid4().hex[:10]
    flt = {"from_year": _year(from_year), "oa_only": bool(oa_only)}
    with ws.connect() as cx:
        cx.execute("INSERT INTO lit_searches(search_id, title, words, kind, filters_json, draft_id, created_at, since) "
                   "VALUES (?,?,?,?,?,?,?,?)",
                   (sid, (title or words).strip()[:200], words, "question" if kind == "question" else "search",
                    json.dumps(flt), draft_id or None, now(), _today()))
    return get_search(ws, sid)


def get_search(ws: Workspace, search_id: str) -> dict:
    _ensure(ws)
    r = ws.query("SELECT * FROM lit_searches WHERE search_id=?", (search_id,))
    if not r:
        raise KeyError(search_id)
    return _search_row(r[0])


def list_searches(ws: Workspace) -> list[dict]:
    _ensure(ws)
    return [_search_row(r) for r in ws.query("SELECT * FROM lit_searches ORDER BY created_at DESC, rowid DESC")]


def delete_search(ws: Workspace, search_id: str) -> None:
    get_search(ws, search_id)
    with ws.connect() as cx:
        cx.execute("DELETE FROM lit_found WHERE search_id=?", (search_id,))
        cx.execute("DELETE FROM lit_searches WHERE search_id=?", (search_id,))


def new_works(ws: Workspace, search_id: str) -> list[dict]:
    """The works found since the person last looked, not yet marked as seen."""
    get_search(ws, search_id)
    rows = ws.query("SELECT work_json, found_at FROM lit_found WHERE search_id=? AND seen=0 ORDER BY found_at DESC, rowid",
                    (search_id,))
    works = [json.loads(r["work_json"]) for r in rows]
    return mark_known(ws, works)


def _alert_query(ws: Workspace, s: dict, date_filter: str) -> list[dict]:
    flt = [f"{date_filter}:{s['since']}"]
    f = s["filters"]
    if f.get("from_year"):
        flt.append(f"from_publication_date:{f['from_year']}-01-01")
    if f.get("oa_only"):
        flt.append("is_oa:true")
    params = {"search": s["words"], "per-page": 50, "select": OA_SELECT, "filter": ",".join(flt)}
    return _cached(ws, "openalex", "/works", _polite(params, "openalex"),
                   lambda r: [_oa_work(x) for x in (r or {}).get("results") or []], fresh=True)


def check_search(ws: Workspace, search_id: str) -> dict:
    """Ask OpenAlex for works created since the person last looked (`from_created_date`; where the service will not
    answer that filter, works published since). New ones are kept until the person marks them as seen."""
    s = get_search(ws, search_id)
    try:
        allow_online()
        allow_draft(ws, s["draft_id"])
        try:
            found = _alert_query(ws, s, "from_created_date")
        except LiteratureError as e:
            if e.kind not in ("refused", "failed"):
                raise
            found = _alert_query(ws, s, "from_publication_date")
    except LiteratureError as e:
        with ws.connect() as cx:
            cx.execute("UPDATE lit_searches SET error=? WHERE search_id=?", (str(e), search_id))
        raise
    added = 0
    with ws.connect() as cx:
        for w in found:
            if not w.get("title"):
                continue
            cur = cx.execute("INSERT OR IGNORE INTO lit_found(search_id, work_key, work_json, found_at, seen) "
                             "VALUES (?,?,?,?,0)", (search_id, w["key"], json.dumps(w, ensure_ascii=False), now()))
            added += cur.rowcount or 0
        unseen = cx.execute("SELECT COUNT(*) FROM lit_found WHERE search_id=? AND seen=0", (search_id,)).fetchone()[0]
        cx.execute("UPDATE lit_searches SET last_checked_at=?, new_count=?, error=NULL WHERE search_id=?",
                   (now(), unseen, search_id))
    return {"search": get_search(ws, search_id), "found": len(found), "added": added}


def mark_seen(ws: Workspace, search_id: str) -> dict:
    get_search(ws, search_id)
    with ws.connect() as cx:
        cx.execute("UPDATE lit_found SET seen=1 WHERE search_id=?", (search_id,))
        cx.execute("UPDATE lit_searches SET since=?, new_count=0 WHERE search_id=?", (_today(), search_id))
    return get_search(ws, search_id)


def stale(s: dict, hours: float = STALE_HOURS) -> bool:
    """Whether a saved search has not been looked at lately (the page then looks when it opens)."""
    if not s.get("last_checked_at"):
        return True
    from datetime import datetime, timezone

    try:
        then = datetime.fromisoformat(s["last_checked_at"])
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - then).total_seconds() > hours * 3600


def counts(ws: Workspace) -> dict:
    """For the Overview: how many searches are kept and how many works are new on them. Nothing is sent."""
    try:
        _ensure(ws)
        return {"searches": int(ws.scalar("SELECT COUNT(*) FROM lit_searches") or 0),
                "new": int(ws.scalar("SELECT COALESCE(SUM(new_count), 0) FROM lit_searches") or 0)}
    except Exception:  # noqa: BLE001
        return {"searches": 0, "new": 0}


# ---------------------------------------------------------------------------------------------
# sending works to Zotero, and RIS / BibTeX
# ---------------------------------------------------------------------------------------------
ZOTERO_TYPES = {"article": "journalArticle", "journal-article": "journalArticle", "preprint": "preprint",
                "book": "book", "monograph": "book", "book-chapter": "bookSection", "dissertation": "thesis",
                "conference": "conferencePaper", "proceedings-article": "conferencePaper", "report": "report",
                "review": "journalArticle", "letter": "journalArticle", "editorial": "journalArticle"}
VENUE_FIELD = {"journalArticle": "publicationTitle", "bookSection": "bookTitle", "conferencePaper": "proceedingsTitle",
               "preprint": "repository", "book": "publisher", "report": "institution", "thesis": "university"}


def clean_work(w) -> dict:
    """A work as the page sends it back, cut down to the fields Margin made (anything else is dropped)."""
    if not isinstance(w, dict):
        raise LiteratureError("bad_request", "A work must be an object.")
    op = w.get("open") if isinstance(w.get("open"), dict) else None
    return _work(str(w.get("source") or "openalex"), title=w.get("title"),
                 authors=[str(a) for a in w.get("authors") or [] if isinstance(a, str)], year=w.get("year"),
                 venue=w.get("venue"), doi=w.get("doi"), url=w.get("url"), abstract=w.get("abstract"),
                 cited_by=w.get("cited_by") if isinstance(w.get("cited_by"), int) else 0, type_=w.get("type"),
                 openalex_id=w.get("openalex_id"), volume=w.get("volume"), issue=w.get("issue"), pages=w.get("pages"),
                 open_={k: (str(op.get(k))[:500] if op.get(k) else None) for k in ("url", "pdf_url", "license", "status",
                                                                                    "found_by")} if op else None)


def _clean_works(works) -> list[dict]:
    if not isinstance(works, list) or not works:
        raise LiteratureError("bad_request", "Choose at least one work.")
    return [clean_work(w) for w in works[:200]]


def _split_name(name: str) -> tuple[str, str]:
    name = name.strip()
    if "," in name:
        last, first = name.split(",", 1)
        return last.strip(), first.strip()
    parts = name.split()
    return (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (name, "")


def zotero_item(w: dict, n: int, attach_pdf: bool = True) -> dict:
    """A work in the shape Zotero's connector saves (the same JSON the Zotero browser extension sends)."""
    kind = ZOTERO_TYPES.get(w.get("type") or "", "journalArticle")
    creators = []
    for a in w["authors"]:
        last, first = _split_name(a)
        creators.append({"firstName": first, "lastName": last, "creatorType": "author"} if first
                        else {"name": last, "creatorType": "author"})
    item = {"id": f"margin-{n}", "itemType": kind, "title": w["title"], "creators": creators,
            "attachments": [], "tags": [], "notes": []}
    if w.get("year"):
        item["date"] = str(w["year"])
    if w.get("doi"):
        item["DOI"] = w["doi"]
    if w.get("url"):
        item["url"] = w["url"]
    if w.get("venue") and VENUE_FIELD.get(kind):
        item[VENUE_FIELD[kind]] = w["venue"]
    for k in ("volume", "issue", "pages"):
        if w.get(k) and kind == "journalArticle":
            item[k] = w[k]
    if w.get("abstract"):
        item["abstractNote"] = w["abstract"]
    pdf = (w.get("open") or {}).get("pdf_url")
    if attach_pdf and pdf:
        item["attachments"].append({"title": "Full Text PDF", "url": pdf, "mimeType": "application/pdf"})
    return item


def _zotero_post(path: str, body: dict, timeout: float = 30):
    req = Request(bibliography.zotero_url() + path, data=json.dumps(body).encode(), method="POST",
                  headers={"Content-Type": "application/json", "X-Zotero-Connector-API-Version": "3",
                           "User-Agent": f"Margin/{__version__}"})
    try:
        with bibliography._OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read()
    except HTTPError as e:
        return e.code, (e.read() or b"")
    except (URLError, OSError, TimeoutError):
        raise LiteratureError("zotero_not_running", "Zotero is not open on this computer. Open the Zotero app, choose the "
                                                    "collection the works should go into, then try again. Or download "
                                                    "them as a file and import that in Zotero.") from None


def zotero_target() -> dict:
    """Whether Zotero is open, and the collection it would save into (the one selected in Zotero). Local only."""
    try:
        req = Request(bibliography.zotero_url() + "/connector/ping", headers={"User-Agent": f"Margin/{__version__}"})
        with bibliography._OPENER.open(req, timeout=3) as r:
            r.read()
    except (HTTPError, URLError, OSError, TimeoutError):
        return {"state": "not_running"}
    out = {"state": "ready"}
    try:
        status, raw = _zotero_post("/connector/getSelectedCollection", {}, timeout=5)
        if status == 200:
            d = json.loads(raw or b"{}")
            out.update(library=d.get("libraryName"), collection=d.get("name"), editable=d.get("libraryEditable", True))
    except (LiteratureError, ValueError):
        pass
    return out


def send_to_zotero(works, attach_pdf: bool = True) -> dict:
    """Save works into Zotero through its connector on this computer. Zotero puts them in the collection selected in
    its window. Nothing is sent over the internet by Margin (with `attach_pdf`, Zotero itself fetches the open PDFs)."""
    items = [zotero_item(w, i, attach_pdf) for i, w in enumerate(_clean_works(works), 1)]
    target = zotero_target()
    if target["state"] != "ready":
        raise LiteratureError("zotero_not_running", "Zotero is not open on this computer. Open the Zotero app, choose the "
                                                    "collection the works should go into, then try again. Or download "
                                                    "them as a file and import that in Zotero.")
    if target.get("editable") is False:
        raise LiteratureError("zotero_failed", "The library or collection selected in Zotero cannot be changed. Select "
                                               "one of your own collections in Zotero, then try again.")
    first_url = next((i.get("url") for i in items if i.get("url")), "https://doi.org/")
    status, raw = _zotero_post("/connector/saveItems", {"sessionID": uuid.uuid4().hex, "uri": first_url, "items": items})
    if status not in (200, 201):
        detail = raw.decode("utf-8", "replace")[:200]
        raise LiteratureError("zotero_failed", f"Zotero did not save the works ({status}{': ' + detail if detail else ''}). "
                                               "Make sure a collection is selected in Zotero, then try again.")
    return {"sent": len(items), "library": target.get("library"), "collection": target.get("collection")}


def _ris_type(w: dict) -> str:
    return {"article": "JOUR", "preprint": "JOUR", "book": "BOOK", "book-chapter": "CHAP", "dissertation": "THES",
            "conference": "CPAPER", "report": "RPRT"}.get(w.get("type") or "", "JOUR")


def to_ris(works) -> str:
    lines = []
    for w in _clean_works(works):
        lines.append(f"TY  - {_ris_type(w)}")
        lines += [f"AU  - {a}" for a in w["authors"]]
        lines.append(f"TI  - {w['title']}")
        for tag, key in (("PY", "year"), ("JO", "venue"), ("VL", "volume"), ("IS", "issue"), ("DO", "doi"), ("UR", "url"),
                         ("AB", "abstract")):
            if w.get(key):
                lines.append(f"{tag}  - {w[key]}")
        if w.get("pages"):
            a, _s, b = w["pages"].partition("-")
            lines.append(f"SP  - {a}")
            if b:
                lines.append(f"EP  - {b}")
        lines.append("ER  - ")
        lines.append("")
    return "\r\n".join(lines)


_BIB_ESC = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"}


def _bib(s: str) -> str:
    return "".join(_BIB_ESC.get(c, c) for c in s)


def to_bibtex(works) -> str:
    out, used = [], Counter()
    for w in _clean_works(works):
        last = re.sub(r"[^a-z]", "", _fold_title(_split_name(w["authors"][0])[0]).replace(" ", "")) if w["authors"] else "anon"
        first_word = next((t for t in re.findall(r"[a-z]{4,}", (w["title"] or "").lower())), "work")
        key = f"{last or 'anon'}{w.get('year') or ''}{first_word}"
        used[key] += 1
        if used[key] > 1:
            key += chr(96 + used[key])
        kind = {"book": "book", "book-chapter": "incollection", "dissertation": "phdthesis", "conference": "inproceedings",
                "report": "techreport", "preprint": "misc"}.get(w.get("type") or "", "article")
        fields = [("title", w["title"]), ("author", " and ".join(w["authors"])), ("year", w.get("year")),
                  ("journal" if kind == "article" else "booktitle" if kind in ("incollection", "inproceedings") else "howpublished",
                   w.get("venue")), ("volume", w.get("volume")), ("number", w.get("issue")),
                  ("pages", (w.get("pages") or "").replace("-", "--") or None), ("doi", w.get("doi")),
                  ("url", w.get("url")), ("abstract", w.get("abstract"))]
        body = ",\n".join(f"  {k} = {{{_bib(str(v))}}}" for k, v in fields if v)
        out.append(f"@{kind}{{{key},\n{body}\n}}\n")
    return "\n".join(out)
