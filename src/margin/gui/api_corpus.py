"""0.18.1 part A (documents, theory documents, concepts and team copies): the endpoints of Handler that
part adds, kept out of server.py so the two parts of 0.18.1, built side by side, never edit the same lines.


`Handler` takes this class as a base, so the names in ROUTES resolve on it. server.py adds ROUTES after its own
(the first pattern that matches wins), DOWNLOADS to the routes that may take the token as ?token=, and NOT_A_CHANGE to
the changes after which the shared folder's poller does not bring a round forward."""
from __future__ import annotations

from .api_common import ApiError, _int, _list, _str

P = r"([^/]+)"  # one path segment, as in server.py

# (method, pattern without ^ and $, handler name), e.g. ("GET", rf"/api/projects/{P}/…", "get_…")
ROUTES: list[tuple[str, str, str]] = [
    # K2 part 1: a document's role (theory or evidence; docrole.py)
    ("GET", rf"/api/projects/{P}/document-roles", "get_document_roles"),
    ("GET", rf"/api/projects/{P}/documents/{P}/role", "get_document_role"),
    ("PUT", rf"/api/projects/{P}/documents/{P}/role", "put_document_role"),
    # 0.18.6: a document marked Non-scientific (docrole.py): read and judged, never counted in an answer
    ("PUT", rf"/api/projects/{P}/documents/{P}/nonscientific", "put_document_nonscientific"),
    # 0.19.1: a document's title, as the person names it (bibliography.set_title)
    ("PUT", rf"/api/projects/{P}/documents/{P}/title", "put_document_title"),
    # K2 part 2: a codebook from a theory document (theorycodes.py)
    ("GET", rf"/api/projects/{P}/codebook-theory", "get_codebook_theory_docs"),
    # K2, the framework draft (theoryframe.py): one draft per project, its reading, the evidence, a term looked up,
    # and the codebook made from it. Before codebook-theory/{doc}, which "draft" would match.
    ("GET", rf"/api/projects/{P}/codebook-theory/draft", "get_codebook_theory_draft"),
    ("POST", rf"/api/projects/{P}/codebook-theory/draft", "post_codebook_theory_draft"),
    ("PUT", rf"/api/projects/{P}/codebook-theory/draft", "put_codebook_theory_draft"),
    ("DELETE", rf"/api/projects/{P}/codebook-theory/draft", "delete_codebook_theory_draft"),
    ("POST", rf"/api/projects/{P}/codebook-theory/draft/read", "post_codebook_theory_draft_read"),
    ("POST", rf"/api/projects/{P}/codebook-theory/draft/evidence", "post_codebook_theory_draft_evidence"),
    ("GET", rf"/api/projects/{P}/codebook-theory/draft/lookup", "get_codebook_theory_draft_lookup"),
    ("GET", rf"/api/projects/{P}/codebook-theory/draft/counts", "get_codebook_theory_draft_counts"),
    ("POST", rf"/api/projects/{P}/codebook-theory/draft/make", "post_codebook_theory_draft_make"),
    ("GET", rf"/api/projects/{P}/codebook-theory/{P}", "get_codebook_theory"),
    # 0.18.4 (K2 part 2, the optional AI part): whether the AI may draft a theory document's concepts, and the draft
    ("GET", rf"/api/projects/{P}/codebook-theory/{P}/ai", "get_codebook_theory_ai"),
    ("POST", rf"/api/projects/{P}/codebook-theory/{P}/ai", "post_codebook_theory_ai"),
    # D3 and D4: paths between two concepts, a concept over time and across groups (conceptpaths.py)
    ("GET", rf"/api/projects/{P}/concept-paths", "get_concept_paths"),
    ("GET", rf"/api/projects/{P}/concept-time/{P}", "get_concept_time"),
    ("POST", rf"/api/projects/{P}/concept-groups/{P}", "post_concept_groups"),
    # D1: the concept map, its filters' choices, and one edge's passages (conceptmap.py)
    ("GET", rf"/api/projects/{P}/concept-map", "get_concept_map"),
    ("GET", rf"/api/projects/{P}/concept-map/options", "get_concept_map_options"),
    ("GET", rf"/api/projects/{P}/concept-map/edge", "get_concept_map_edge"),
    # A7 (reader 5): a figure's picture, drawn from the original PDF when it is shown, never stored
    ("GET", rf"/api/projects/{P}/documents/{P}/figures/{P}\.png", "get_figure_image"),
    # 0.19.0 (K3, nonscientific.py): a hypothesis that counts the non-scientific documents, and the suggestion from
    # the bibliography's item type (Mark is the route above; No is this POST)
    ("PUT", rf"/api/projects/{P}/hypotheses/{P}/nonscientific", "put_hypothesis_nonscientific"),
    ("GET", rf"/api/projects/{P}/nonscientific-suggestions", "get_nonscientific_suggestions"),
    ("GET", rf"/api/projects/{P}/documents/{P}/nonscientific-suggestion", "get_nonscientific_suggestion"),
    ("POST", rf"/api/projects/{P}/documents/{P}/nonscientific-suggestion", "post_nonscientific_suggestion"),
]
DOWNLOADS: set[str] = {"get_figure_image"}  # A7: in an <img>, as get_page_image is
NOT_A_CHANGE: set[str] = {
    # K2, the framework draft: the draft is a file of this computer's project folder that the shared folder does not
    # carry (only the codebook made from it is shared), and the evidence is a search
    "post_codebook_theory_draft", "put_codebook_theory_draft", "delete_codebook_theory_draft",
    "post_codebook_theory_draft_evidence"}


class CorpusApi:
    # ---- K2 part 1: a document's role ---------------------------------------------------------------------------
    def get_document_roles(self, name, q):
        """{"roles": {doc id: "theory"}, "nonscientific": [doc ids]}: the documents with a role other than evidence,
        and (0.18.6) those marked Non-scientific, for the Documents list."""
        from .. import docrole

        ws = self.app.ws(name)
        return {"roles": {r[0]: r[1] for r in ws.query("SELECT doc_id, role FROM documents WHERE role IS NOT NULL")},
                "nonscientific": sorted(docrole.nonscientific_docs(ws))}

    def get_document_role(self, name, doc_id, q):
        """{"doc_id", "role" (null: evidence), "impact": what was made with it in (docrole.impact), "nonscientific",
        "answers" (the checks that read it, when it is non-scientific), "started" (0.19.0: the checks started from its
        text)}."""
        from .. import docrole

        ws = self.app.ws(name)
        if not ws.scalar("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)):
            raise ApiError(404, "No such document in this project.")
        ns = docrole.is_nonscientific(ws, doc_id)
        return {"doc_id": doc_id, "role": docrole.role_of(ws, doc_id), "impact": docrole.impact(ws, doc_id),
                # 0.18.6: marked Non-scientific, and (when it is) each check that read it, now and counting it
                "nonscientific": ns, "answers": docrole.counted_without(ws, doc_id) if ns else [],
                # 0.19.0 (N3): the checks started from its text (*Check against the corpus*), each with its answer
                "started": docrole.checks_started_from(ws, doc_id)}

    def put_document_role(self, name, doc_id, q):
        """{"role": "theory" | "working" | null, "why"?}: mark a document as theory, as a working document (N3), or
        as evidence again. Under an owner, a
        Member's mark is a proposal (the Team tab's next look writes it), as *Leave out* is."""
        from .. import docrole

        body = self._body()
        role = body.get("role")
        if role is not None and role not in docrole.ROLES:
            raise ApiError(400, "A document's role is \"theory\" or \"working\", or null (evidence).")
        why = body.get("why")
        try:
            return docrole.set_role(self.app.ws(name), doc_id, role, str(why).strip() or None if why else None)
        except KeyError:
            raise ApiError(404, "No such document in this project.") from None

    def put_document_nonscientific(self, name, doc_id, q):
        """{"nonscientific": true | false, "why"?}: mark a document as Non-scientific, or count it again. Answers
        change at once: the reply lists those it changed (docrole.set_nonscientific)."""
        from .. import docrole

        body = self._body()
        on = body.get("nonscientific")
        if not isinstance(on, bool):
            raise ApiError(400, "\"nonscientific\" is true or false.")
        why = body.get("why")
        try:
            return docrole.set_nonscientific(self.app.ws(name), doc_id, on, str(why).strip() or None if why else None)
        except KeyError:
            raise ApiError(404, "No such document in this project.") from None

    def put_document_title(self, name, doc_id, q):
        """{"title": "…"}: rename a document; "" (or null) gives it back the title it would have had. Returns
        {"doc_id", "title", "named", "changed"} (bibliography.set_title)."""
        from .. import bibliography

        title = self._body().get("title")
        if title is not None and not isinstance(title, str):
            raise ApiError(400, "\"title\" is text, or \"\" for the title it had before.")
        try:
            return bibliography.set_title(self.app.ws(name), doc_id, title)
        except KeyError:
            raise ApiError(404, "No such document in this project.") from None

    # ---- K2 part 2: a codebook from a theory document -------------------------------------------------------------
    def get_codebook_theory_docs(self, name, q):
        """{"documents": [{"doc_id", "title", "theory"}]}: the documents a codebook can start from, theory first."""
        ws = self.app.ws(name)
        rows = ws.query("SELECT doc_id, title, role FROM documents ORDER BY role IS NOT 'theory', title")   # (N3)
        return {"documents": [{"doc_id": r["doc_id"], "title": r["title"], "theory": r["role"] == "theory"} for r in rows]}

    # ---- K2, the framework draft (theoryframe.py) ------------------------------------------------------------------
    def _theory_job(self, draft: dict):
        """The job of the draft's running reading, while it runs; None otherwise."""
        r = draft["reading"]
        job = self.app.jobs.jobs.get(r.get("job") or "") if r.get("state") == "running" else None
        return job if job is not None and job.state in ("queued", "running") else None

    def _theory_view(self, draft: dict | None) -> dict | None:
        """The draft as the page reads it: a reading whose job died (the app restarted, or the job ended without
        writing its end) is never shown as running for ever."""
        from .. import theoryframe

        if draft is None:
            return None
        r = draft["reading"]
        # the focus changed since the last reading (the documents never do): reading again gives another framework
        stale = bool(r.get("input")) and r["input"] != theoryframe._input_hash(draft["doc_ids"], draft.get("focus") or "")
        draft = {**draft, "reading": {**r, "stale": stale}}
        r = draft["reading"]
        if r.get("state") != "running" or self._theory_job(draft) is not None:
            return draft
        job = self.app.jobs.jobs.get(r.get("job") or "")
        if r.get("before") == "read":
            state = "read"
        else:
            state = "none" if job is not None and job.state == "cancelled" else "failed"
        why = (job.error if job is not None and job.error else
               "The reading stopped before it was done (the app was closed, or it was stopped).")
        return {**draft, "reading": {**r, "state": state, "problems": list(r.get("problems") or [])
                                     + ([why] if state == "failed" else [])}}

    def _theory_draft(self, ws) -> dict:
        from .. import theoryframe

        d = theoryframe.load(ws)
        if d is None:
            raise ApiError(404, theoryframe.NO_DRAFT)
        return d

    def get_codebook_theory_draft(self, name, q):
        """{"draft": draft | null, "offer": whether the AI may read its documents (theoryframe.offer) | null,
        "documents": the documents a draft can start from, theory first (as GET …/codebook-theory)}."""
        from .. import theoryframe

        ws = self.app.ws(name)
        d = self._theory_view(theoryframe.load(ws))
        return {"draft": d, "offer": theoryframe.offer(ws, d["doc_ids"], self.app.settings()) if d else None,
                **self.get_codebook_theory_docs(name, q)}

    def post_codebook_theory_draft(self, name, q):
        """Body {"title", "name", "where", "doc_ids", "focus"?}: a new draft (it replaces the one there), its
        framework without AI. {"draft", "offer"}."""
        from .. import theoryframe

        ws = self.app.ws(name)
        body = self._body()
        old = theoryframe.load(ws)
        job = self._theory_job(old) if old else None
        if job is not None:   # a reading of the draft this one replaces: stopped, as when a draft is discarded
            self.app.jobs.cancel(job)
        try:
            d = theoryframe.start(ws, str(body.get("title") or ""), str(body.get("name") or ""),
                                  str(body.get("where") or "project"), body.get("doc_ids"), str(body.get("focus") or ""))
        except KeyError:
            raise ApiError(404, "No such document in this project.") from None
        except ValueError as e:
            raise ApiError(400, str(e)) from None
        return {"draft": d, "offer": theoryframe.offer(ws, d["doc_ids"], self.app.settings())}

    def put_codebook_theory_draft(self, name, q):
        """Body: what changed, {"title"?, "name"?, "where"?, "focus"?, "groups"?, "concepts"?, "rev"?}
        (theoryframe.save). {"draft"};
        409 when "rev" is not the draft's (it changed since the page loaded it)."""
        from .. import theoryframe

        try:
            return {"draft": self._theory_view(theoryframe.save(self.app.ws(name), self._body()))}
        except theoryframe.Stale as e:   # the page's draft is older than the one kept: it loads it again
            raise ApiError(409, str(e)) from None
        except LookupError as e:
            raise ApiError(404, str(e)) from None
        except ValueError as e:
            raise ApiError(400, str(e)) from None

    def delete_codebook_theory_draft(self, name, q):
        """The draft is discarded (a reading that runs is stopped). {"ok": true}."""
        from .. import theoryframe

        ws = self.app.ws(name)
        d = theoryframe.load(ws)
        job = self._theory_job(d) if d else None
        if job is not None:
            self.app.jobs.cancel(job)
        theoryframe.discard(ws)
        return {"ok": True}

    def post_codebook_theory_draft_read(self, name, q):
        """{"job"}: the AI reads the draft's theory documents and puts the framework together (theoryframe.read), as
        a job that waits its turn like every AI job. A reading that runs already is the one answered."""
        from .. import theorycodes, theoryframe

        ws = self.app.ws(name)
        d = self._theory_draft(ws)
        running = self._theory_job(d)
        if running is not None:
            return {"job": running.view()}
        offer = theoryframe.offer(ws, d["doc_ids"], self.app.settings())
        if not offer["offered"]:
            raise ApiError(400, offer["why"])
        job = self.app.start_queued_job(
            "theory-frame", f"The AI reads the theory for “{d['title'][:60]}”", name,
            lambda job, be, model, prog: theoryframe.read(ws, be, model, prog, job.cancel.is_set, job=job.id),
            withdraw=(theorycodes.AI_KIND, theoryframe.KIND))
        job.scope = "theory-draft"
        theoryframe.mark_running(ws, job.id)
        return {"job": job.view()}

    def post_codebook_theory_draft_evidence(self, name, q):
        """Body {"concept": {"name", "meaning"?, "when_to_use"?, "words"?}, "skip"?: [passage ids], "k"?: 1 to 8}:
        passages of the evidence documents that may show the concept (theoryframe.evidence, no AI). {"passages"}."""
        from .. import theoryframe

        ws = self.app.ws(name)
        body = self._body()
        concept = body.get("concept")
        if not isinstance(concept, dict):
            raise ApiError(400, "Send the concept: {\"concept\": {\"name\", \"when_to_use\", \"words\"}}.")
        skip = body.get("skip") or []
        if not isinstance(skip, list):
            raise ApiError(400, "\"skip\" is a list of passage ids.")
        try:
            k = max(1, min(8, int(body.get("k") or 4)))
        except (TypeError, ValueError):
            k = 4
        return {"passages": theoryframe.evidence(ws, concept, k=k, skip=[str(x) for x in skip],
                                                 embedder=self._quiet_embedder(ws))}

    def _quiet_embedder(self, ws):
        """The app's embedder when this project has vectors from it already (as the Search page's search by meaning
        gets it), else None; any problem getting it: None, and the search goes by keywords."""
        try:
            return self.app._embedder_for(ws)
        except Exception:  # noqa: BLE001
            return None

    def get_codebook_theory_draft_counts(self, name, q):
        """{"documents": n, "counts": {concept key: n}}: in how many of the evidence documents each concept's words
        are found (theoryframe.evidence_counts, no AI), for the draft as it is kept."""
        from .. import theoryframe

        ws = self.app.ws(name)
        self._theory_draft(ws)
        return theoryframe.evidence_counts(ws)

    def get_codebook_theory_draft_lookup(self, name, q):
        """?term=…: the term in each of the draft's theory documents (theoryframe.lookup), and "passages": the evidence
        for it (theoryframe.evidence)."""
        from .. import theoryframe

        ws = self.app.ws(name)
        d = self._theory_draft(ws)
        term = (_str(q, "term") or "").strip()
        try:
            got = theoryframe.lookup(ws, d["doc_ids"], term)
        except ValueError as e:
            raise ApiError(400, str(e)) from None
        return {**got, "passages": theoryframe.evidence(ws, {"name": got["term"], "words": [got["term"]]},
                                                        embedder=self._quiet_embedder(ws))}

    def post_codebook_theory_draft_make(self, name, q):
        """The kept concepts become a codebook (theoryframe.make) and the draft is gone. {"codebook"}."""
        from .. import theoryframe

        ws = self.app.ws(name)
        d = theoryframe.load(ws)
        if d is not None and self._theory_job(d) is not None:
            raise ApiError(409, "The AI is still reading the theory: wait until it is done, or stop it.")
        try:
            return {"codebook": theoryframe.make(ws)}
        except LookupError as e:
            raise ApiError(404, str(e)) from None
        except ValueError as e:
            raise ApiError(400, str(e)) from None

    # ---- D3 and D4 -----------------------------------------------------------------------------------------------
    def get_concept_paths(self, name, q):
        """?from=<term id>&to=<term id>[&k=3]: the shortest chains between two concepts (conceptpaths.paths)."""
        from .. import conceptpaths

        a, b = _str(q, "from"), _str(q, "to")
        if not a or not b:
            raise ApiError(400, "Say both concepts: ?from=<term id>&to=<term id>.")
        try:
            k = max(1, min(5, int(_str(q, "k") or 3)))
        except ValueError:
            k = 3
        try:
            return conceptpaths.paths(self.app.ws(name), a, b, k)
        except KeyError:
            raise ApiError(404, "No such term in the glossary: make the glossary again.") from None

    def get_concept_time(self, name, term, q):
        """A concept by publication year (conceptpaths.over_time)."""
        from .. import conceptpaths

        try:
            return conceptpaths.over_time(self.app.ws(name), term)
        except KeyError:
            raise ApiError(404, "No such term in the glossary: make the glossary again.") from None

    def post_concept_groups(self, name, term, q):
        """{"groups": {name: [doc ids]}}: a concept in sets of documents picked on the page, not stored."""
        from .. import conceptpaths

        groups = self._body().get("groups")
        if not isinstance(groups, dict) or not all(isinstance(v, list) for v in groups.values()):
            raise ApiError(400, "Send {\"groups\": {name: [document ids]}}.")
        try:
            return conceptpaths.compare_groups(self.app.ws(name), term, {str(k): [str(x) for x in v]
                                                                         for k, v in groups.items()})
        except KeyError:
            raise ApiError(404, "No such term in the glossary: make the glossary again.") from None
        except ValueError as e:
            raise ApiError(400, str(e)) from None

    # ---- D1: the concept map ---------------------------------------------------------------------------------------
    def get_concept_map(self, name, q):
        """?doc=<id>[,<id>…]&theme=<run id>:<theme id>&framework=<codebook>&code=<code>&year_from=&year_to=&n=: the
        concept map within these filters (conceptmap.concept_map)."""
        from .. import conceptmap

        ws = self.app.ws(name)
        try:
            return conceptmap.concept_map(ws, _map_filters(q), _int(q, "n", conceptmap.DEFAULT_N, conceptmap.MIN_N,
                                                                     conceptmap.MAX_N))
        except KeyError:
            raise ApiError(404, "That set of themes is gone: make the themes again, or choose another theme.") from None
        except ValueError as e:
            raise ApiError(400, str(e)) from None

    def get_concept_map_options(self, name, q):
        """{"documents", "themes", "codebooks", "years"}: what the map's filters can choose from."""
        from .. import conceptmap

        return conceptmap.options(self.app.ws(name))

    def get_concept_map_edge(self, name, q):
        """?a=<term id>&b=<term id> and the map's filters: how two concepts on the map are joined, with the passages
        that mention both (conceptmap.edge)."""
        from .. import conceptmap

        a, b = _str(q, "a"), _str(q, "b")
        if not a or not b:
            raise ApiError(400, "Say both concepts: ?a=<term id>&b=<term id>.")
        try:
            return conceptmap.edge(self.app.ws(name), a, b, _map_filters(q))
        except KeyError:
            raise ApiError(404, "No such term in the glossary, or that set of themes is gone: make them again.") from None
        except ValueError as e:
            raise ApiError(400, str(e)) from None

    def get_codebook_theory(self, name, doc_id, q):
        """The candidate concepts of a document, as draft codes with their quoted definitions and the evidence's
        suggested examples (theorycodes.candidates)."""
        from .. import theorycodes

        try:
            return theorycodes.candidates(self.app.ws(name), doc_id)
        except KeyError:
            raise ApiError(404, "No such document in this project.") from None

    def get_codebook_theory_ai(self, name, doc_id, q):
        """{"offered", "why", "reader", "level"}: whether the AI may draft this document's concepts (its own AI
        setting decides: Claude, a local AI, or none), and in one line why not (theorycodes.ai_offer)."""
        from .. import theorycodes

        try:
            return theorycodes.ai_offer(self.app.ws(name), doc_id, self.app.settings())
        except KeyError:
            raise ApiError(404, "No such document in this project.") from None

    def post_codebook_theory_ai(self, name, doc_id, q):
        """{"job"}: the AI drafts the concepts of a theory document (theorycodes.draft_with_ai), as a job that waits
        its turn like every AI job; its result holds the drafts, to join the list unticked."""
        from .. import theorycodes

        ws = self.app.ws(name)
        title = ws.scalar("SELECT title FROM documents WHERE doc_id=?", (doc_id,))
        if title is None:
            raise ApiError(404, "No such document in this project.")
        offer = theorycodes.ai_offer(ws, doc_id, self.app.settings())
        if not offer["offered"]:
            raise ApiError(400, offer["why"])
        job = self.app.start_queued_job(
            "theory-codes", f"The AI drafts the concepts of “{title[:60]}”", name,
            lambda job, be, model, prog: theorycodes.draft_with_ai(ws, doc_id, be, model, prog, job.cancel.is_set),
            withdraw=(theorycodes.AI_KIND,))
        job.scope = doc_id
        return {"job": job.view()}

    # ---- A7 (reader 5): a figure's picture ------------------------------------------------------------------------
    def get_figure_image(self, name, doc_id, n, q):
        """The picture of a block that has a box on its page (a figure; also a table found from its rules): the crop of
        the original PDF's page the reader found (`blocks.x0..y1`, points from the top left), as a PNG. It is drawn
        from the original when asked for, as the *Page* panel's picture is, and nothing of it is stored or sent to an
        AI. `?scale=` (0.5 to 3, default 2)."""
        from pathlib import Path

        from .api_common import _float, page_images_available

        ws = self.app.ws(name)
        try:
            n = int(n)
        except ValueError:
            raise ApiError(404, "No such block in this document.") from None
        rows = ws.query("SELECT page, kind, x0, y0, x1, y1 FROM blocks WHERE doc_id=? AND n=?", (doc_id, n))
        if not rows:
            raise ApiError(404, "No such block in this document.")
        b = rows[0]
        if b["page"] is None or b["x0"] is None or b["kind"] not in ("figure", "table"):
            raise ApiError(404, "This block has no place on a page to draw.")
        info = self.app.original(ws, doc_id)
        if not info["available"] or (info.get("kind") or "") != "pdf":
            raise ApiError(404, info.get("reason") or "The original PDF is not available.")
        if not page_images_available():
            raise ApiError(404, "Pictures of pages need the OCR extra (pypdfium2), which is not installed.")
        png = _render_crop(Path(info["path"]), int(b["page"]), (b["x0"], b["y0"], b["x1"], b["y1"]),
                           min(3.0, max(0.5, _float(q, "scale", 2.0))))
        if png is None:
            raise ApiError(404, "No such page.")
        return self._send(200, png, "image/png", {"Cache-Control": "private, max-age=3600"})

    # ---- 0.19.0 (K3): the per-hypothesis exception and the bibliography's suggestion (nonscientific.py) ----------
    def put_hypothesis_nonscientific(self, name, hyp_id, q):
        """{"count": true | false, "why"?: text}: count the non-scientific documents in this hypothesis's check, or
        not again; a "why" while it is on replaces the reason, and an empty one takes it away (the usual reason is
        given again). The answer changes at once: the reply has it before and after (nonscientific.set_counting)."""
        from .. import nonscientific

        body = self._body()
        on = body.get("count")
        if not isinstance(on, bool):
            raise ApiError(400, "\"count\" is true or false.")
        why = body.get("why")
        if why is not None and not isinstance(why, str):
            raise ApiError(400, "\"why\" is text, or left out.")
        try:
            return nonscientific.set_counting(self.app.ws(name), hyp_id, on, why)
        except KeyError:
            raise ApiError(404, "No such result.") from None

    def get_nonscientific_suggestions(self, name, q):
        """{"suggested": {doc id: "a newspaper article"}}: the documents the bibliography suggests marking, for the
        Documents list."""
        from .. import nonscientific

        return {"suggested": {d: x["words"] for d, x in nonscientific.suggestions(self.app.ws(name)).items()}}

    def get_nonscientific_suggestion(self, name, doc_id, q):
        """{"doc_id", "suggestion": {"item_type", "words", "text"} | null, "answered_no": {"by", "may_suggest_again"}
        | null}."""
        from .. import nonscientific

        ws = self.app.ws(name)
        if not ws.scalar("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)):
            raise ApiError(404, "No such document in this project.")
        return {"doc_id": doc_id, "suggestion": nonscientific.suggestion(ws, doc_id),
                "answered_no": nonscientific.answered_no(ws, doc_id)}

    def post_nonscientific_suggestion(self, name, doc_id, q):
        """{"answer": "no", "why"?}: the person's No to the suggestion, kept as a decision (the research log);
        {"answer": "again"}: take a No back (*Suggest again*). 409 when there is nothing to answer now."""
        from .. import nonscientific

        body = self._body()
        answer = body.get("answer")
        if answer not in ("no", "again"):
            raise ApiError(400, "\"answer\" is \"no\" or \"again\" (to mark the document, use its nonscientific "
                                "route).")
        why = body.get("why")
        if why is not None and not isinstance(why, str):
            raise ApiError(400, "\"why\" is text, or left out.")
        ws = self.app.ws(name)
        try:
            if answer == "again":
                return nonscientific.suggest_again(ws, doc_id)
            return nonscientific.decline(ws, doc_id, why)
        except nonscientific.NoSuggestion:
            if answer == "again":
                raise ApiError(409, "There is nothing to take back: no No that you may take back hides the "
                                    "suggestion now.") from None
            raise ApiError(409, "This document has no suggestion to answer now: it is marked already, someone said "
                                "No, or its bibliography entry is of a scientific kind. Reload the page to see it as "
                                "it is.") from None
        except KeyError:
            raise ApiError(404, "No such document in this project.") from None


def _render_crop(path, page: int, box: tuple[float, float, float, float], scale: float) -> bytes | None:
    """The box (points from the top left of the page, with a margin of a few points) of a PDF page (1-based) as PNG
    bytes, or None when there is no such page. The whole page is drawn at `scale` and the box cut from it."""
    import io

    import pypdfium2 as pdfium

    from .api_common import _PDFIUM_LOCK

    with _PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(str(path))
        try:
            if not 1 <= page <= len(pdf):
                return None
            pg = pdf[page - 1]
            width, height = pg.get_size()
            img = pg.render(scale=scale).to_pil()
        finally:
            pdf.close()
    pad = 4.0
    sx, sy = img.width / max(width, 1.0), img.height / max(height, 1.0)
    left, top = max(0.0, box[0] - pad) * sx, max(0.0, box[1] - pad) * sy
    right, bottom = min(width, box[2] + pad) * sx, min(height, box[3] + pad) * sy
    if right - left < 2 or bottom - top < 2:
        return None
    buf = io.BytesIO()
    img.crop((int(left), int(top), int(right) + 1, int(bottom) + 1)).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _map_filters(q):
    """The concept map's filters from a query (D1): documents, a theme, a code, years."""
    from ..conceptmap import Filters

    f = Filters()
    f.docs = _list(q, "doc")
    th = _str(q, "theme")
    if th:
        run, _, tid = th.rpartition(":")
        try:
            f.theme = (run, int(tid))
        except ValueError:
            raise ApiError(400, "A theme is <run id>:<theme id>.") from None
        if not run:
            raise ApiError(400, "A theme is <run id>:<theme id>.")
    fw, code = _str(q, "framework"), _str(q, "code")
    if code:
        if not fw:
            raise ApiError(400, "Say the codebook of the code: &framework=<name>.")
        f.code = (fw, code)
    for k in ("year_from", "year_to"):
        v = _str(q, k)
        if v:
            if not v.isdigit() or len(v) != 4 or int(v) < 1:
                raise ApiError(400, f"{k} is a year of four digits.")
            setattr(f, k, int(v))
    f.applied = f.describe()
    return f
