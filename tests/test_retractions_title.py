"""B5 by title: a work of the bibliography without a DOI is looked up in Crossref by its title, first author's family
name and year, strictly; the match is shown with its notice, can be rejected, and what is sent is only those three. The
tests use a stand-in Crossref (a QuickServer on this computer) and never touch the network. The page's *found by title*
line and *Not this work* are run in Node (tests/_views.py)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import pytest

from _views import needs_node, run_views
from margin import __version__, access, bibliography, retractions
from test_app import api, home  # noqa: F401  (fixtures)

TITLE = "Repair cafés and the politics of everyday maintenance"
MATCH = "10.5555/match.1"
OTHER = "10.5555/other.2"
NOTICE = "10.9999/notice-1"


def candidate(doi=MATCH, title=TITLE, year=2020, family="Verhoeven", **kw):
    return {"DOI": doi, "title": [title], "author": [{"family": family, "given": "A."}],
            "issued": {"date-parts": [[year]]}, **kw}


class Crossref:
    """What Margin asks of Crossref: /works?query.bibliographic=… (candidates), then the notices of a DOI."""

    def __init__(self):
        from margin.gui.server import QuickServer

        outer = self
        self.requests: list[tuple[str, dict]] = []
        self.candidates = [candidate()]
        self.retracted = {MATCH}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                outer.requests.append((self.path, {k.lower(): v for k, v in self.headers.items()}))
                q = parse_qs(urlparse(self.path).query)
                items = []
                if "query.bibliographic" in q:
                    items = outer.candidates
                elif q.get("filter", [""])[0].startswith("updates:"):
                    asked = {p.split(":", 1)[1] for p in q["filter"][0].split(",")}
                    items = [{"DOI": NOTICE, "update-to": [{"DOI": d, "type": "retraction", "source": "retraction-watch",
                                                            "updated": {"date-parts": [[2024, 3, 9]]}}]}
                             for d in sorted(asked & outer.retracted)]
                body = json.dumps({"status": "ok", "message": {"total-results": len(items), "items": items}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = QuickServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def title_requests(self):
        return [p for p, _h in self.requests if "query.bibliographic" in p]

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def crossref():
    c = Crossref()
    yield c
    c.stop()


def add_work(ws, key, title=TITLE, year="2020", family="Verhoeven", doi=None, kind="journalArticle", seq=0):
    creators = json.dumps([{"last": family, "first": "A.", "role": "author"}] if family else [])
    with ws.connect() as cx:
        cx.execute("INSERT INTO bib_items(item_key, item_type, title, creators_json, year, doi, files_json, seq) "
                   "VALUES (?,?,?,?,?,?,?,?)", (key, kind, title, creators, year, doi, "[]", seq))


def add_doc(ws, doc_id, link_to=None, role=None):
    with ws.connect() as cx:
        cx.execute("INSERT INTO documents(doc_id, path, sha1, title, kind, n_pages, n_chars, text, added_at, role) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?)", (doc_id, f"{doc_id}.txt", doc_id, doc_id, "txt", 1, 1, "x",
                                                    "2026-01-01", role))
        if link_to:
            cx.execute("INSERT INTO bib_links(item_key, doc_id, status, method) VALUES (?,?, 'confirmed', 'person')",
                       (link_to, doc_id))


@pytest.fixture
def ws(home):  # noqa: F811
    from margin import home as core

    ws = core.create_project("R")
    add_work(ws, "w1")
    ws.set_meta("bibliography", {"kind": "file", "name": "x.bib", "pulled_at": "2026-01-01T00:00:00+00:00"})
    return ws


def look(ws, crossref):
    return retractions.lookup(ws, base_url=crossref.url, sleep=lambda s: None)


# ------------------------------------------------------------------------------------------------ a strict match
def test_a_strict_match_is_found_and_its_notice_shown_as_found_by_title(ws, crossref):
    add_doc(ws, "d1", link_to="w1")
    out = look(ws, crossref)
    assert out["by_title"] == 1 and out["title_matched"] == 1 and out["notices"] == 1
    s = retractions.status(ws)
    n = s["by_item"]["w1"][0]
    assert n["type"] == "retraction" and n["found_by"] == "title" and n["work_doi"] == MATCH
    assert n["match"] == {"doi": MATCH, "title": TITLE, "year": "2020", "author": "Verhoeven, A."}
    assert s["by_doc"]["d1"][0]["found_by"] == "title"
    assert [m["item_key"] for m in s["title_matches"]] == ["w1"]
    v = bibliography.view(ws)
    work = next(w for w in v["to_find"] + [r["work"] for r in v["linked"]] if w["key"] == "w1")
    assert work["notices"][0]["found_by"] == "title"


def test_a_notice_title_prefix_and_a_year_off_by_one_and_accents_still_match(ws, crossref):
    crossref.candidates = [candidate(title="RETRACTED: Repair Cafes and the politics of everyday maintenance", year=2021,
                                     family="Verhoevén")]
    assert look(ws, crossref)["title_matched"] == 1


@pytest.mark.parametrize("name,cand", [
    ("title differs", candidate(title="Repair cafés and the economics of everyday maintenance work")),
    ("year off by two", candidate(year=2022)),
    ("other first author", candidate(family="Okafor")),
    ("a retraction notice's own title", candidate(title="Retraction: " + TITLE)),
    ("a retraction note's own record", candidate(title="Retraction Note: " + TITLE)),
    ("a correction's own record", candidate(title="Correction to: " + TITLE)),
    ("an erratum's own record", candidate(title="Erratum: " + TITLE)),
    ("no author", {"DOI": MATCH, "title": [TITLE], "issued": {"date-parts": [[2020]]}}),
    ("no year", {"DOI": MATCH, "title": [TITLE], "author": [{"family": "Verhoeven"}]}),
])
def test_near_misses_are_refused(ws, crossref, name, cand):
    crossref.candidates = [cand]
    out = look(ws, crossref)
    assert out["by_title"] == 1 and out["title_matched"] == 0, name
    assert retractions.status(ws)["title_matches"] == [] and retractions.status(ws)["by_item"] == {}
    assert ws.scalar("SELECT doi FROM retraction_matches WHERE item_key='w1'") is None   # looked up, no match


def test_two_candidates_that_pass_are_no_match(ws, crossref):
    crossref.candidates = [candidate(), candidate(doi=OTHER)]
    out = look(ws, crossref)
    assert out["title_matched"] == 0 and out["title_ambiguous"] == 1
    assert retractions.status(ws)["title_matches"] == []


def test_a_candidate_that_fails_does_not_make_a_match_ambiguous(ws, crossref):
    crossref.candidates = [candidate(doi=OTHER, year=1999), candidate()]
    assert look(ws, crossref)["title_matched"] == 1


# ------------------------------------------------------------------------------------------- which works are asked
def test_works_that_are_left_out(ws, crossref):
    add_work(ws, "w_no_ai", title="A second long enough title here", seq=1)
    add_doc(ws, "d_no_ai", link_to="w_no_ai")
    access.set_documents(ws, ["d_no_ai"], "none")
    add_work(ws, "w_working", title="A third long enough title here", seq=2)
    add_doc(ws, "d_work", link_to="w_working", role="working")
    add_work(ws, "w_manuscript", title="A fourth long enough title here", kind="manuscript", seq=3)
    add_work(ws, "w_letter", title="A fifth long enough title here", kind="letter", seq=4)
    add_work(ws, "w_web", title="A sixth long enough title here", kind="webpage", seq=5)
    add_work(ws, "w_none", title="A seventh long enough title here", kind=None, seq=6)
    add_work(ws, "w_short", title="Two words", seq=7)
    add_work(ws, "w_noyear", title="An eighth long enough title here", year=None, seq=8)
    add_work(ws, "w_noauthor", title="A ninth long enough title here", family=None, seq=9)
    add_work(ws, "w_doi", title="A tenth long enough title here", doi="10.1/x", seq=10)
    add_work(ws, "w_book", title="An eleventh long enough title here", kind="book", seq=11)
    add_doc(ws, "d_free")   # a document with no DOI and no work: never looked up by title
    plan = retractions.title_works(ws)
    assert [w["key"] for w in plan["works"]] == ["w1", "w_book"]
    assert plan["no_ai"] == ["w_no_ai"] and plan["working"] == ["w_working"]
    look(ws, crossref)
    sent = " ".join(crossref.title_requests()).lower()
    assert len(crossref.title_requests()) == 2 and "d_free" not in sent and "ninth" not in sent and "seventh" not in sent


def test_local_only_sends_nothing(ws, crossref, monkeypatch):
    monkeypatch.setenv("MARGIN_LOCAL_ONLY", "1")
    with pytest.raises(retractions.RetractionError, match="local-only"):
        look(ws, crossref)
    assert crossref.requests == []


def test_only_title_family_and_year_are_sent(ws, crossref):
    look(ws, crossref)
    path, headers = crossref.title_requests()[0], crossref.requests[0][1]
    q = parse_qs(urlparse(path).query)
    assert q["query.bibliographic"] == [f"{TITLE} Verhoeven 2020"]
    assert set(q) == {"query.bibliographic", "filter", "rows", "select"} and q["filter"] == ["is-update:false"]
    for p, h in crossref.requests:
        assert h["user-agent"] == f"Margin/{__version__}"
        flat = (p + json.dumps(h)).lower()
        assert "mailto" not in flat and "@" not in flat and "authorization" not in h and "cookie" not in h
        assert "/r" not in urlparse(p).path   # no project name
    assert "R" not in q["query.bibliographic"][0].split() and headers["user-agent"].startswith("Margin/")


def test_the_cap_is_one_request_per_work(ws, crossref, monkeypatch):
    monkeypatch.setattr(retractions, "MAX_TITLES", 2)
    for i in range(3):
        add_work(ws, f"x{i}", title=f"A work number {i} with a long title", seq=i + 1)
    out = look(ws, crossref)
    assert out["by_title"] == 2 and out["title_capped"] is True and len(crossref.title_requests()) == 2


# --------------------------------------------------------------------------------------------------- rejecting
def test_a_rejected_match_is_hidden_and_not_proposed_again(ws, crossref):
    look(ws, crossref)
    r = retractions.reject_match(ws, "w1")
    assert r["rejected"] is True and r["doi"] == MATCH
    s = retractions.status(ws)
    assert s["title_matches"] == [] and s["by_item"] == {} and MATCH not in s["by_doi"] and s["affected"] == 0
    row = ws.query("SELECT rejected_at, rejected_by FROM retraction_matches WHERE item_key='w1'")[0]
    assert row["rejected_at"] and row["rejected_by"]
    out = look(ws, crossref)                      # the same DOI again: not proposed
    assert out["title_matched"] == 0 and retractions.status(ws)["by_item"] == {}
    assert ws.scalar("SELECT rejected_at FROM retraction_matches WHERE item_key='w1'")
    crossref.candidates = [candidate(doi=OTHER)]  # a different DOI may be
    crossref.retracted = {OTHER}
    assert look(ws, crossref)["title_matched"] == 1
    assert retractions.status(ws)["by_item"]["w1"][0]["match"]["doi"] == OTHER
    entry = ws.query("SELECT kind, subject_kind, subject_id, text, data_json FROM research_log WHERE "
                     "kind='retraction-match'")[0]
    assert entry["subject_kind"] == "bib_item" and entry["subject_id"] == "w1" and MATCH in entry["text"]
    assert "another work" in entry["text"]


def test_a_work_and_its_notice_record_still_match_the_work(ws, crossref):
    crossref.candidates = [candidate(), candidate(doi=OTHER, title="Retraction Note: " + TITLE)]
    out = look(ws, crossref)
    assert out["title_matched"] == 1 and out["title_ambiguous"] == 0


def test_a_rejection_survives_an_ambiguous_or_empty_lookup(ws, crossref):
    look(ws, crossref)
    retractions.reject_match(ws, "w1")
    crossref.candidates = [candidate(), candidate(doi=OTHER)]   # two fit, one of them the rejected DOI: OTHER alone
    crossref.retracted = set()
    assert look(ws, crossref)["title_matched"] == 1            # another work alone fits: it may be proposed
    retractions.reject_match(ws, "w1")                         # not that one either
    for cands in ([candidate(doi="10.1/third"), candidate(doi="10.1/fourth")], []):   # two others; none
        crossref.candidates = cands
        look(ws, crossref)
        assert ws.scalar("SELECT rejected_at FROM retraction_matches WHERE item_key='w1'")   # kept
    crossref.candidates = [candidate(doi=OTHER)]
    assert look(ws, crossref)["title_matched"] == 0            # the rejected DOI is not proposed again


def test_taking_a_rejection_back(ws, crossref):
    look(ws, crossref)
    retractions.reject_match(ws, "w1")
    assert retractions.reject_match(ws, "w1", False)["rejected"] is False
    assert retractions.status(ws)["by_item"]["w1"][0]["found_by"] == "title"
    assert retractions.reject_match(ws, "w1", False)["changed"] is False
    with pytest.raises(KeyError):
        retractions.reject_match(ws, "nope")


def test_the_routes(api, ws, crossref, monkeypatch):  # noqa: F811
    monkeypatch.setenv("MARGIN_CROSSREF_URL", crossref.url)
    st, r = api("GET", "/api/projects/R/retractions")
    assert st == 200 and r["title_plan"] == {"ask": 1, "no_ai": 0, "working": 0, "capped": False} and r["title_matches"] == []
    st, r = api("POST", "/api/projects/R/retractions/check", {})
    assert st == 200
    job = api.wait(r["job"]["id"])
    assert job["state"] == "done" and job["result"]["by_title"] == 1 and job["result"]["title_matched"] == 1, job
    st, r = api("GET", "/api/projects/R/retractions")
    assert r["by_item"]["w1"][0]["found_by"] == "title" and r["title_matches"][0]["doi"] == MATCH
    st, r = api("POST", "/api/projects/R/retractions/matches/w1", {"reject": True})
    assert st == 200 and r["rejected"] is True
    st, r = api("GET", "/api/projects/R/retractions")
    assert r["title_matches"] == [] and r["by_item"] == {}
    st, r = api("POST", "/api/projects/R/retractions/matches/w1", {"reject": False})
    assert st == 200 and r["rejected"] is False
    st, r = api("POST", "/api/projects/R/retractions/matches/nope", {"reject": True})
    assert st == 404
    st, r = api("POST", "/api/projects/R/retractions/matches/w1", {"reject": "yes"})
    assert st == 400


def test_a_work_with_nothing_to_ask_is_refused(api, home):  # noqa: F811
    from margin import home as core

    core.create_project("Empty")
    st, r = api("POST", "/api/projects/Empty/retractions/check", {})
    assert st == 400 and "nothing to look up" in r["error"]


# ------------------------------------------------------------------------------------------------------- the page
PROBE = r"""
const BIB = "/api/projects/Study/bibliography";
const MATCH = { doi: "10.5555/match.1", title: "Repair cafés and the politics of everyday maintenance", year: "2020", author: "Verhoeven, A." };
const work = (o = {}) => ({ key: "w1", title: MATCH.title, cite: "Verhoeven (2020)", authors: "Verhoeven, A.", year: "2020", type: "Journal article",
  notices: [{ type: "retraction", date: "2024-03-09", doi: "10.9999/n", source: "retraction-watch", work_doi: MATCH.doi, checked_at: "2026-11-01T10:00:00+00:00", found_by: "title", match: MATCH }], ...o });
await scenario("found by title", async (t) => {
  let rejected = false;
  t.answer(`GET ${BIB}`, () => ({ bibliography: { kind: "file", name: "x.bib", format_text: "BibTeX", works: 1 }, counts: { to_find: 1, linked: 0, confirm: 0, not_in: 0 },
    to_find: [rejected ? work({ notices: [] }) : work()], linked: [], confirm: [], not_in: [], retractions: { checked_at: "2026-11-01T10:00:00+00:00", affected: 1, local_only: false } }));
  t.answer("POST /api/projects/Study/retractions/matches/w1", (body) => { rejected = body.reject; return { rejected: body.reject }; });
  await t.render("views/bibliography.js", "renderBibliography", [], {});
  const line = t.view.querySelector(".bib-match");
  const out = { line: line ? t.text(line) : null, link: line ? line.querySelector("a").href : null, tags: t.view.querySelectorAll(".bib-notices").length };
  await t.click("Not this work", { within: line });
  out.posts = t.calls.filter((c) => c.method === "POST").map((c) => [c.path, c.body]);
  out.toasts = t.toasts();
  out.after = t.view.querySelector(".bib-match") ? "still shown" : "gone";
  await t.click("Undo", { within: document.getElementById("toasts") });
  out.undo = t.calls.filter((c) => c.method === "POST").map((c) => c.body);
  out.back = t.view.querySelector(".bib-match") ? "shown" : "gone";
  return out;
});
await scenario("a claim card", async (t) => {
  const H = "/api/projects/Study/hypotheses/h1";
  const px = { passage_id: "p1", doc_id: "d1", title: "Repair report", text: "Volunteers fix toasters for free.", quote: "Volunteers fix toasters",
    quote_start: 0, quote_end: 23, verdict: "supports", ai_verdict: "supports", confidence: 0.9, counted: true, read_by: "claude-sonnet",
    in_corpus: true, page: 3, round: 1, found_by: "keywords" };
  const res = { hyp_id: "h1", text: "Repair cafés build community", status: "supported", threshold: 0.6, options: {}, decomposed: false, model: "claude-sonnet",
    parts: [{ claim_id: "c1", part: 1, claim: "Repair cafés build community", status: "supported", passages: [px], rounds_info: [], model: "claude-sonnet" }] };
  t.state({ settings: { threshold: 0.6 } });
  t.answer("GET /api/projects/Study/retractions", { by_doc: { d1: [{ type: "retraction", date: "2024-03-09", checked_at: "2026-11-01T10:00:00+00:00", found_by: "title", match: MATCH }] } });
  t.answer("GET /api/projects/Study/sharing/check/h1", { shared: false });
  t.answer(/^GET \/api\/projects\/Study\/documents\/[^/]+\/file\?check=1$/, t.fail(404, "no file"));
  t.answer(`GET ${H}/unread`, { documents: [] });
  t.answer("GET /api/servers", { servers: [] });
  t.answer("GET /api/projects/Study/shared-folder", { folder: null });
  t.answer("GET /api/projects/Study/sync-poller", t.fail(404, "none"));
  t.answer("GET /api/local-status", { running: false, models: [] });
  t.answer(`GET ${H}?*`, () => res);
  await t.render("views/result.js", "renderResult", ["h1"], {});
  const el = t.view.querySelector('[data-passage="p1"]');
  return { text: t.text(el) };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("retractions_title"))


@needs_node
def test_the_page_says_found_by_title_and_not_this_work_rejects_with_undo(page):
    p = page["found by title"]
    assert p["line"].startswith("Found by title: Repair cafés and the politics of everyday maintenance (2020) · 10.5555/match.1")
    assert p["line"].endswith("Not this work") and p["link"] == "https://doi.org/10.5555/match.1"
    assert p["posts"] == [["/api/projects/Study/retractions/matches/w1", {"reject": True}]]
    assert p["toasts"] and "not the same work" in str(p["toasts"]).lower()
    assert p["after"] == "gone"
    assert p["undo"][-1] == {"reject": False} and p["back"] == "shown"


@needs_node
def test_the_claim_card_says_found_by_title_beside_the_notice(page):
    assert "work retracted · found by title" in page["a claim card"]["text"]
