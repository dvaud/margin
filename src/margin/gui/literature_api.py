"""The API of Find literature (docs/API.md, "Finding literature"). The handlers are the methods of a mixin class that
`server.Handler` inherits, so `server.ROUTES` names them like any other handler and the server module does not grow;
`literature.LiteratureError` carries its own status and kind and is answered by `Handler._route`."""
from __future__ import annotations

from .. import access, bibliography, drafts, embed, home, literature
from ..literature import LiteratureError


def _body(h) -> dict:
    return h._body()


def _text(body: dict, key: str, limit: int = 2000) -> str:
    v = body.get(key)
    return str(v).strip()[:limit] if v is not None else ""


def _source(body: dict) -> str:
    s = _text(body, "source") or "openalex"
    if s not in literature.SEARCH_SOURCES:
        raise LiteratureError("bad_request", "Search OpenAlex, Crossref or Semantic Scholar.")
    return s


def _filters(body: dict) -> dict:
    return {"from_year": body.get("from_year") or None, "oa_only": bool(body.get("oa_only"))}


class LiteratureHandlers:
    """The `lit_*` endpoints of `server.Handler`."""

    def lit_get_literature(self, name, q):
        """The page's first look: whether lookups are allowed, the e-mail address, the drafts, the saved searches. Nothing
        is sent."""
        ws = self.app.ws(name)
        s = self.app.settings()
        emb = None
        try:
            e = home.make_embedder(s)
            if e is not None and not embed.remote(e) and ws.scalar("SELECT 1 FROM embeddings WHERE model=? LIMIT 1", (e.model,)):
                emb = e.model
        except Exception:  # noqa: BLE001
            emb = None
        plan = literature.citation_plan(ws)
        return {"local_only": home.local_only(), "email": literature.contact_email(),
                "sources": [{"id": k, "name": literature.NAMES[k], "site": literature.SITES[k]} for k in literature.SEARCH_SOURCES],
                "embedding": emb, "drafts": [{"draft_id": d["draft_id"], "title": d["title"], "ai_access": d["ai_access"],
                                              "ai_label": access.LABEL.get(d["ai_access"], d["ai_access"]),
                                              "claims": d["claims"]} for d in drafts.list_drafts(ws)],
                "searches": literature.list_searches(ws), "documents": {"total": len(plan["documents"]),
                                                                        "usable": plan["included"],
                                                                        "not_allowed": plan["not_allowed"],
                                                                        "no_doi": plan["no_doi"]},
                "zotero_url": bibliography.zotero_url()}

    def lit_get_draft_claims(self, name, draft_id, q):
        return literature.draft_claims(self.app.ws(name), draft_id)

    def lit_post_words(self, name, q):
        """Search words for a text, made on this computer. Nothing is sent."""
        ws = self.app.ws(name)
        text = _text(_body(self), "text")
        if not text:
            raise LiteratureError("bad_request", "Give the text to make search words from.")
        return literature.search_words(ws, text)

    def lit_post_search(self, name, q):
        ws = self.app.ws(name)
        b = _body(self)
        src = _source(b)
        words = _text(b, "words", 400)
        out = literature.find_for_text(ws, words, _text(b, "claim") or None, source=src, from_year=b.get("from_year"),
                                       oa_only=bool(b.get("oa_only")), limit=int(b.get("limit") or 25),
                                       draft_id=_text(b, "draft_id") or None, fresh=bool(b.get("fresh")))
        out["sent"] = literature.what_is_sent(out["words"], src)
        return out

    def lit_post_open_copies(self, name, q):
        b = _body(self)
        dois = b.get("dois")
        if not isinstance(dois, list):
            raise LiteratureError("bad_request", "Give the DOIs as a list.")
        return {"copies": literature.open_copies(self.app.ws(name), [str(d) for d in dois]), "service": "Unpaywall"}

    def lit_get_citation_plan(self, name, q):
        return literature.citation_plan(self.app.ws(name))

    def lit_post_citations(self, name, q):
        b = _body(self)
        return literature.follow_citations(self.app.ws(name), fresh=bool(b.get("fresh")))

    def lit_get_searches(self, name, q):
        return {"searches": literature.list_searches(self.app.ws(name))}

    def lit_post_searches(self, name, q):
        ws = self.app.ws(name)
        b = _body(self)
        return {"search": literature.save_search(ws, _text(b, "words", 400), title=_text(b, "title", 200) or None,
                                                 kind=_text(b, "kind") or "search", draft_id=_text(b, "draft_id") or None,
                                                 **{k: v for k, v in _filters(b).items()})}

    def lit_get_search_works(self, name, search_id, q):
        ws = self.app.ws(name)
        return {"search": literature.get_search(ws, search_id), "works": literature.new_works(ws, search_id)}

    def lit_delete_search(self, name, search_id, q):
        literature.delete_search(self.app.ws(name), search_id)
        return {"deleted": search_id}

    def lit_post_search_check(self, name, search_id, q):
        ws = self.app.ws(name)
        out = literature.check_search(ws, search_id)
        out["works"] = literature.new_works(ws, search_id)
        return out

    def lit_post_search_seen(self, name, search_id, q):
        return {"search": literature.mark_seen(self.app.ws(name), search_id)}

    def lit_delete_cache(self, name, q):
        return {"forgotten": literature.forget_cache(self.app.ws(name))}

    def lit_get_zotero_target(self, q):
        """Whether Zotero is open and where works would go (local; nothing goes over the internet)."""
        return literature.zotero_target()

    def lit_post_zotero(self, q):
        b = _body(self)
        return literature.send_to_zotero(b.get("works"), attach_pdf=b.get("attach_pdf", True) is not False)

    def lit_post_export(self, q):
        b = _body(self)
        fmt = _text(b, "format") or "ris"
        if fmt not in ("ris", "bibtex"):
            raise LiteratureError("bad_request", "Download RIS or BibTeX.")
        text = literature.to_ris(b.get("works")) if fmt == "ris" else literature.to_bibtex(b.get("works"))
        fname = "Margin - works found." + ("ris" if fmt == "ris" else "bib")
        from .server import _disposition

        return self._send(200, text.encode("utf-8"), "application/x-research-info-systems; charset=utf-8" if fmt == "ris"
                       else "application/x-bibtex; charset=utf-8", {"Content-Disposition": _disposition(fname)})
