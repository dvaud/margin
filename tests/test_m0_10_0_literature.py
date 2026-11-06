"""Margin 0.10.0: finding literature. Online lookups that are not AI: search for works for the claims no document
supports (E1), follow what the documents cite and who cites them (E2), and saved searches that say what is new (E3).
The tests never touch the network: OpenAlex, Crossref, Semantic Scholar, Unpaywall and Zotero are stand-ins on this
computer (tests/fake_literature.py, tests/fake_zotero.py), and the privacy gate is tested explicitly."""
from __future__ import annotations

import json
import re
import socket

import pytest

from fake_literature import FakeLiterature
from fake_zotero import FakeZotero
from test_app import api, home  # noqa: F401  (fixtures)

from margin import access, drafts, home as home_mod, literature
from margin.literature import LiteratureError
from margin.llm import BaselineBackend

DRAFT = """Remote work and wellbeing

Studies show that employees who work from home report higher life satisfaction (Verhoeven & Okafor, 2025).

Unicorn populations doubled in the last decade across the northern hemisphere, and sightings keep rising.

We interviewed twelve people in two offices.
"""


@pytest.fixture
def fake(monkeypatch, home):  # noqa: F811
    f = FakeLiterature().install(monkeypatch)
    yield f
    f.stop()


@pytest.fixture
def zotero(monkeypatch):
    z = FakeZotero()
    monkeypatch.setenv("MARGIN_ZOTERO_URL", z.start())
    yield z
    z.stop()


DOCS = {
    "d1": ("Working from home and wellbeing: evidence from the Lowland Household Panel", "10.5555/lhp.2025.1",
           "Employees who worked from home at least two days a week reported higher life satisfaction than comparable "
           "employees at the office. Remote work raised wellbeing, most of all for parents of young children. The panel "
           "followed 6,200 employees of the Lowland Household Panel before, during and after the pandemic."),
    "d2": ("Commuting less, emitting less?", "10.5555/rmi.2024.12",
           "Remote work reduces commuting emissions, but by less than often assumed. Workers who stay home two days a week "
           "cut their commuting distance by 35 percent, and part of the saving is lost to errands by car in the region."),
    "d3": ("Hybrid work and productivity: a review", "10.5555/hyb.2025.3",
           "Hybrid work lowers productivity in some roles and raises it in others. The review compares field studies of "
           "hybrid schedules and finds that managers matter more than the number of days spent at home."),
}


@pytest.fixture
def project(home, tmp_path):  # noqa: F811
    """A project with three documents, each with its DOI printed on its first page; `project.ids` maps d1, d2, d3 to
    their document ids. Claude may read all of them."""
    from margin import ingest

    ws = home_mod.create_project("Lit")
    folder = tmp_path / "docs"
    folder.mkdir()
    for key, (title, doi, body) in DOCS.items():
        (folder / f"{key}.txt").write_text(f"{title}\ndoi:{doi}\n\n{body}\n\n{body}\n", encoding="utf-8")
    access.set_default(ws, "cloud")
    ingest.ingest(ws, [folder], ai_access="cloud")
    ws.ids = {k: ws.scalar("SELECT doc_id FROM documents WHERE doi=?", (v[1],)) for k, v in DOCS.items()}
    assert all(ws.ids.values()), ws.ids
    return ws


def _sent(fake, service=None):
    return fake.sent(service)


# ---------------------------------------------------------------------------------------------
# the words of a search are made on this computer
# ---------------------------------------------------------------------------------------------
def test_search_words_come_from_the_claim_and_the_corpus_terms(project):
    out = literature.search_words(project, "Remote work lowers the quality of public services in municipal offices.")
    assert out["terms"] == [] and out["words"].startswith("remote work") and "services" in out["words"]
    assert len(out["words"].split()) <= 6 and "the" not in out["words"].split()
    assert "according" not in literature.search_words(None, "According to several recent studies, remote work helps")["words"]
    with project.connect() as cx:  # a corpus term of two words is kept whole and quoted
        cx.execute("INSERT INTO terms(term_id, label, stems, n_words, df, tf, passages, cvalue) VALUES "
                   "('t1','public services','public servic',2,3,5,4,9.0)")
    out = literature.search_words(project, "Remote work lowers the quality of public services in municipal offices.")
    assert out["terms"] == ["public services"] and '"public services"' in out["words"]
    assert literature.search_words(None, "")["words"] == ""
    assert literature.search_words(None, "Studies show 12 percent.")["words"]  # something to start from


# ---------------------------------------------------------------------------------------------
# E1: searching
# ---------------------------------------------------------------------------------------------
def test_an_openalex_search_gives_works_with_open_copies_and_a_polite_address(project, fake):
    out = literature.search(project, "remote work wellbeing")
    w = out["works"][0]
    assert w["title"].startswith("Working from home and wellbeing") and w["doi"] == "10.5555/lhp.2025.1"
    assert w["authors"] == ["Verhoeven, M.", "Okafor, A."] and w["year"] == 2025 and w["venue"] == "Journal of Work and Society"
    assert w["abstract"].startswith("We follow employees") and w["cited_by"] == 40
    assert w["open"]["pdf_url"] == "https://repo.example/lhp.pdf" and w["open"]["found_by"] == "OpenAlex"
    assert w["key"] == "doi:10.5555/lhp.2025.1" and w["pages"] == "101-120"
    # a generic agent, and no address unless the person gave one
    svc, path, params = fake.requests[-1]
    assert (svc, path) == ("openalex", "/works") and "mailto" not in params and "email" not in params
    assert fake.agents[-1].startswith("Margin/") and "@" not in fake.agents[-1]
    home_mod.update_settings({"contact_email": "me@example.org"})
    literature.search(project, "remote work wellbeing parents", fresh=True)
    assert fake.requests[-1][2]["mailto"] == "me@example.org"
    # filters travel as OpenAlex filters
    literature.search(project, "remote work", from_year=2025, oa_only=True)
    assert fake.requests[-1][2]["filter"] == "from_publication_date:2025-01-01,is_oa:true"


def test_crossref_and_semantic_scholar_can_be_searched_too(project, fake):
    cr = literature.search(project, "commuting emissions", source="crossref")
    assert cr["service"] == "Crossref" and cr["works"][0]["doi"] == "10.5555/rmi.2024.12"
    assert cr["works"][0]["authors"] and cr["works"][0]["year"] == 2024 and "<" not in (cr["works"][0]["abstract"] or "")
    s2 = literature.search(project, "wellbeing", source="semanticscholar", oa_only=True)
    assert s2["works"] and all(w["open"] for w in s2["works"]) and s2["works"][0]["open"]["found_by"] == "Semantic Scholar"
    with pytest.raises(LiteratureError) as e:
        literature.search(project, "x y", source="google")
    assert e.value.kind == "bad_request"
    with pytest.raises(LiteratureError):
        literature.search(project, "   ")


def test_the_same_lookup_is_not_repeated(project, fake):
    literature.search(project, "remote work wellbeing")
    n = len(fake.requests)
    again = literature.search(project, "remote work wellbeing")
    assert len(fake.requests) == n and again["works"]
    literature.search(project, "remote work wellbeing", fresh=True)
    assert len(fake.requests) == n + 1
    assert literature.forget_cache(project) >= 1
    literature.search(project, "remote work wellbeing")
    assert len(fake.requests) == n + 2


def test_errors_are_said_in_plain_words(project, fake):
    fake.mode = "rate_limited"
    with pytest.raises(LiteratureError) as e:
        literature.search(project, "remote work")
    assert e.value.kind == "rate_limited" and "slow down" in str(e.value) and "30 seconds" in str(e.value)
    fake.mode = "down"
    with pytest.raises(LiteratureError) as e:
        literature.search(project, "remote work")
    assert e.value.kind == "failed" and "503" in str(e.value)
    fake.mode = "refused"
    with pytest.raises(LiteratureError) as e:
        literature.search(project, "remote work")
    assert e.value.kind == "refused"


def test_offline_is_said_too(project, monkeypatch):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead = f"http://127.0.0.1:{s.getsockname()[1]}"
    monkeypatch.setenv("MARGIN_OPENALEX_URL", dead)
    with pytest.raises(LiteratureError) as e:
        literature.search(project, "remote work")
    assert e.value.kind == "offline" and "OpenAlex" in str(e.value) and "online" in str(e.value)


# ---------------------------------------------------------------------------------------------
# the privacy gate
# ---------------------------------------------------------------------------------------------
def test_nothing_goes_out_when_cloud_services_are_off_for_good(project, fake, monkeypatch):
    monkeypatch.setenv("MARGIN_LOCAL_ONLY", "1")
    calls = [lambda: literature.search(project, "remote work"),
             lambda: literature.find_for_text(project, "remote work"),
             lambda: literature.open_copies(project, ["10.1000/tele.2018.1"]),
             lambda: literature.follow_citations(project),
             lambda: literature.check_search(project, literature.save_search(project, "remote work")["search_id"])]
    home_mod.update_settings({"contact_email": "me@example.org"})
    for call in calls:
        with pytest.raises(LiteratureError) as e:
            call()
        assert e.value.kind == "local_only", e.value
    assert fake.requests == []
    # not even a lookup that was made before is answered from the project's cache while this holds? (nothing is asked)
    assert literature.counts(project)["searches"] == 1


def test_a_search_from_a_draft_goes_out_only_if_the_draft_allows_the_cloud(project, fake):
    cloud = drafts.new_draft(project, DRAFT, "Open draft", ai_access="cloud")
    local = drafts.new_draft(project, DRAFT, "Local draft", ai_access="local")
    none = drafts.new_draft(project, DRAFT, "No-AI draft", ai_access="none")
    for did in (local, none):
        with pytest.raises(LiteratureError) as e:
            literature.search(project, "unicorn populations", draft_id=did)
        assert e.value.kind == "not_allowed" and "stay on this computer" in str(e.value)
        saved = literature.save_search(project, "unicorn populations", draft_id=did)   # keeping it sends nothing
        with pytest.raises(LiteratureError) as e:
            literature.check_search(project, saved["search_id"])
        assert e.value.kind == "not_allowed"
    assert fake.requests == []
    literature.search(project, "unicorn populations", draft_id=cloud)
    assert len(fake.requests) == 1
    # words typed on the page are the person's own: no draft is involved
    literature.search(project, "typed by the person")
    assert len(fake.requests) == 2
    with pytest.raises(LiteratureError) as e:
        literature.search(project, "x", draft_id="nodraft")
    assert e.value.kind == "bad_request"
    # the draft's claims are listed (their words suggested) without sending anything, and say whether a search may go
    n = len(fake.requests)
    assert literature.draft_claims(project, cloud)["searchable"] is True
    out = literature.draft_claims(project, local)
    assert out["searchable"] is False and "not sent" in out["why_not"]
    assert len(fake.requests) == n


def test_a_saved_search_from_a_draft_is_checked_only_while_the_draft_allows_it(project, fake):
    did = drafts.new_draft(project, DRAFT, "Open draft", ai_access="cloud")
    s = literature.save_search(project, "unicorn populations", draft_id=did)
    drafts.update(project, did, ai_access="local")
    with pytest.raises(LiteratureError) as e:
        literature.check_search(project, s["search_id"])
    assert e.value.kind == "not_allowed" and fake.requests == []
    assert "stay on this computer" in literature.get_search(project, s["search_id"])["error"]


def test_documents_whose_setting_forbids_it_are_left_out_of_following_citations(project, fake):
    access.set_documents(project, [project.ids["d3"]], "local")
    plan = literature.citation_plan(project)
    assert plan["included"] == 2 and plan["not_allowed"] == 1 and "_by_doi" not in plan
    assert {d["doc_id"] for d in plan["documents"] if d["included"]} == {project.ids["d1"], project.ids["d2"]}
    assert plan["dois"] == ["10.5555/lhp.2025.1", "10.5555/rmi.2024.12"]
    assert fake.requests == []   # showing what would be sent sends nothing
    out = literature.follow_citations(project)
    sent = " ".join(p.get("filter", "") for _s, _p, p in fake.requests)
    assert "10.5555/hyb.2025.3" not in sent and "10.5555/lhp.2025.1" in sent
    assert out["documents"] == 2 and out["not_allowed"] == 1
    # every document restricted: nothing to look up, and nothing sent
    access.set_documents(project, [project.ids["d1"], project.ids["d2"]], "none")
    n = len(fake.requests)
    with pytest.raises(LiteratureError) as e:
        literature.follow_citations(project)
    assert e.value.kind == "bad_request" and len(fake.requests) == n


# ---------------------------------------------------------------------------------------------
# E1: ranking, what is already there, open copies
# ---------------------------------------------------------------------------------------------
def test_works_are_ranked_by_the_words_they_share_without_an_embedding_model(project, fake):
    out = literature.find_for_text(project, "remote work", "Remote work lowers the quality of public services")
    assert out["ranked_by"] == "words" and out["note"] == ""
    titles = [w["title"] for w in out["works"]]
    assert titles[0].startswith("Remote work and the quality of public services")
    assert out["works"][0]["closeness"] > out["works"][-1]["closeness"]


class _Embedder:
    """A local embedding model that knows two directions: remote work, and birds."""
    model = "stub-embed"
    base_url = "http://localhost:11434"

    def embed(self, texts):
        return [[3.0, 0.0] if re.search(r"remote|hybrid|telework|commut", t, re.I) else [0.0, 3.0] for t in texts]


def test_with_a_local_embedding_model_works_are_ranked_by_meaning(project, fake):
    works = literature.search(project, "remote work swallows")["works"]
    r = literature.rank(project, works, "remote working from home", embedder=_Embedder())
    assert r["by"] == "meaning"
    assert r["works"][-1]["title"].startswith("Swallow") and r["works"][-1]["closeness"] == 0.0
    assert r["works"][0]["closeness"] == 1.0
    class Broken(_Embedder):
        def embed(self, texts):
            raise RuntimeError("down")
    r = literature.rank(project, works, "remote work", embedder=Broken())
    assert r["by"] == "words" and "embedding model could not be used" in r["note"]


def test_an_embedding_server_elsewhere_is_never_given_the_claim(project, fake, monkeypatch):
    with project.connect() as cx:
        cx.execute("INSERT INTO embeddings VALUES ('m', 'p1', ?)", (b"\x00" * 8,))
    remote = _Embedder()
    remote.model, remote.base_url = "m", "https://embeddings.example.org"
    monkeypatch.setattr(home_mod, "make_embedder", lambda s: remote)
    assert literature._embedder(project) is None
    local = _Embedder()
    local.model = "m"
    monkeypatch.setattr(home_mod, "make_embedder", lambda s: local)
    assert literature._embedder(project) is local


def test_works_already_in_the_documents_or_the_bibliography_are_marked(project, fake):
    with project.connect() as cx:
        cx.execute("INSERT INTO bib_items(item_key, title, creators_json, year, doi, seq) VALUES "
                   "('k1','Telework and job satisfaction: a meta-analysis','[]','2018','10.1000/tele.2018.1',0)")
    works = literature.find_for_text(project, "telework satisfaction remote wellbeing")["works"]
    have = {w["doi"]: (w["have"] or {}).get("where") for w in works}
    assert have["10.5555/lhp.2025.1"] == "documents"       # by DOI, in the documents
    assert have["10.1000/tele.2018.1"] == "bibliography"   # by DOI, in the bibliography only


def test_open_copies_need_an_address_and_are_looked_up_one_by_one(project, fake):
    with pytest.raises(LiteratureError) as e:
        literature.open_copies(project, ["10.1000/commute.2016.2"])
    assert e.value.kind == "no_email" and fake.requests == []
    home_mod.update_settings({"contact_email": "me@example.org"})
    got = literature.open_copies(project, ["https://doi.org/10.1000/commute.2016.2", "10.1000/four.2022.4", "10.9999/none", "x"])
    assert got["10.1000/commute.2016.2"]["pdf_url"] == "https://repo.example/commute.pdf"
    assert got["10.1000/commute.2016.2"]["found_by"] == "Unpaywall"
    assert got["10.1000/four.2022.4"] is None and got["10.9999/none"] is None and "x" not in got
    assert {r[0] for r in fake.requests} == {"unpaywall"} and fake.requests[0][2]["email"] == "me@example.org"
    n = len(fake.requests)
    literature.open_copies(project, ["10.1000/commute.2016.2"])
    assert len(fake.requests) == n   # cached


def test_a_drafts_unsupported_claims_are_listed_with_search_words(project, fake):
    did = drafts.new_draft(project, DRAFT, "Draft", ai_access="cloud")
    drafts.find_by_rules(project, did)
    drafts.check_claims(project, did, BaselineBackend(), "baseline", k=4, per_doc=2, expand=True)
    v = drafts.view(project, did)
    assert v["claims"]
    out = literature.draft_claims(project, did)
    assert out["searchable"] is True and out["draft"]["title"] == "Draft"
    for c in out["claims"]:
        assert c["status"] in literature.NEEDS and c["words"] and c["claim"]
    assert any("unicorn" in c["words"].lower() for c in out["claims"])
    assert fake.requests == []


# ---------------------------------------------------------------------------------------------
# E2: following citations
# ---------------------------------------------------------------------------------------------
def test_the_works_the_documents_cite_and_the_works_citing_them(project, fake):
    out = literature.follow_citations(project)
    assert out["documents"] == 3 and out["found_in_openalex"] == 3 and out["partial"] is False
    cited = {w["openalex_id"]: w for w in out["cited"]}
    # W2001 is cited by the first and the third document, W2002 by the first and the second
    assert cited["W2001"]["n_docs"] == 2 and set(cited["W2001"]["docs"]) == {project.ids["d1"], project.ids["d3"]}
    assert cited["W2001"]["doc_titles"][0].startswith("Working from home") or cited["W2001"]["doc_titles"]
    assert cited["W2002"]["n_docs"] == 2 and cited["W2003"]["n_docs"] == 1
    assert [w["n_docs"] for w in out["cited"]] == sorted((w["n_docs"] for w in out["cited"]), reverse=True)
    citing = {w["openalex_id"]: w for w in out["citing"]}
    assert set(citing) == {"W3001", "W3002", "W3003"} and citing["W3002"]["n_docs"] == 2
    assert set(citing["W3002"]["docs"]) == {project.ids["d1"], project.ids["d2"]} and "W4001" not in citing
    # the documents themselves are not offered back
    assert not {"W1001", "W1002", "W1003"} & (set(cited) | set(citing))
    assert all("theme_close" in w and "have" in w for w in out["cited"] + out["citing"])
    assert out["closeness_by"] in ("none", "words", "meaning")


def test_followed_citations_are_ranked_by_closeness_to_the_themes_after_the_count(project, fake):
    with project.connect() as cx:
        cx.execute("INSERT INTO theme_runs(run_id, mode, k, seed, created_at) VALUES ('r1','keywords',2,0,'2026-01-01')")
        cx.execute("INSERT INTO themes(run_id, theme_id, name, terms_json, size) VALUES "
                   "('r1', 1, 'Loneliness', ?, 5)", (json.dumps(["loneliness", "young employees", "learning"]),))
    out = literature.follow_citations(project)
    assert out["closeness_by"] == "words"
    singles = [w for w in out["cited"] if w["n_docs"] == 1]
    assert singles[0]["openalex_id"] == "W2003" and singles[0]["theme"] == "Loneliness" and singles[0]["theme_close"] > 0


def test_works_already_in_the_corpus_are_marked_when_following_citations(project, fake):
    with project.connect() as cx:   # a work in the bibliography that no document is
        cx.execute("INSERT INTO bib_items(item_key, title, creators_json, year, doi, seq) VALUES "
                   "('k3','Commuting stress and wellbeing','[]','2016','10.1000/commute.2016.2',0)")
    out = literature.follow_citations(project)
    cited = {w["openalex_id"]: w for w in out["cited"]}
    assert cited["W2002"]["have"]["where"] == "bibliography" and cited["W2001"]["have"] is None
    # a work that is one of the documents is not offered back as something to find
    with project.connect() as cx:
        cx.execute("UPDATE documents SET doi='10.1000/tele.2018.1' WHERE doc_id=?", (project.ids["d3"],))
    out = literature.follow_citations(project)
    assert "W2001" not in {w["openalex_id"] for w in out["cited"]}


def test_following_citations_uses_the_dois_of_linked_bibliography_works(project, fake):
    with project.connect() as cx:
        cx.execute("UPDATE documents SET doi=NULL WHERE doc_id=?", (project.ids["d2"],))
        cx.execute("INSERT INTO bib_items(item_key, title, creators_json, year, doi, seq) VALUES "
                   "('k2','Commuting less','[]','2024','10.5555/rmi.2024.12',0)")
        cx.execute("INSERT INTO bib_links VALUES ('k2',?,'confirmed','title',1.0,NULL,NULL)", (project.ids["d2"],))
    plan = literature.citation_plan(project)
    assert next(d for d in plan["documents"] if d["doc_id"] == project.ids["d2"])["included"] is True
    assert plan["included"] == 3


# ---------------------------------------------------------------------------------------------
# E3: saved searches
# ---------------------------------------------------------------------------------------------
def test_a_saved_search_says_what_is_new_since_you_last_looked(project, fake):
    s = literature.save_search(project, "remote work", title="My topic", from_year=2020)
    assert s["title"] == "My topic" and s["since"] and s["new"] == 0 and s["filters"]["from_year"] == 2020
    assert fake.requests == []   # saving sends nothing
    with project.connect() as cx:   # looked at before the works of the catalogue were created
        cx.execute("UPDATE lit_searches SET since='2026-09-30' WHERE search_id=?", (s["search_id"],))
    out = literature.check_search(project, s["search_id"])
    assert out["search"]["new"] == out["added"] == 3 and out["search"]["last_checked_at"]
    flt = fake.requests[-1][2]["filter"]
    assert "from_created_date:2026-09-30" in flt and "from_publication_date:2020-01-01" in flt
    titles = [w["title"] for w in literature.new_works(project, s["search_id"])]
    assert any("public services" in t for t in titles) and not any("Swallow" in t for t in titles)
    assert literature.counts(project) == {"searches": 1, "new": 3}
    # looking again finds nothing new; the same works are not counted twice
    again = literature.check_search(project, s["search_id"])
    assert again["added"] == 0 and again["search"]["new"] == 3
    # marking them seen: nothing new, and the next look starts today
    seen = literature.mark_seen(project, s["search_id"])
    assert seen["new"] == 0 and literature.new_works(project, s["search_id"]) == [] and seen["since"] >= "2026"
    assert literature.counts(project)["new"] == 0
    literature.delete_search(project, s["search_id"])
    assert literature.list_searches(project) == [] and not project.scalar("SELECT COUNT(*) FROM lit_found")
    with pytest.raises(KeyError):
        literature.get_search(project, s["search_id"])


def test_a_service_that_keeps_its_created_date_filter_still_gives_new_works(project, fake):
    fake.mode = "no_created_filter"
    s = literature.save_search(project, "remote work", kind="question", title="Does remote work help?")
    assert s["kind"] == "question"
    with project.connect() as cx:
        cx.execute("UPDATE lit_searches SET since='2026-01-01' WHERE search_id=?", (s["search_id"],))
    out = literature.check_search(project, s["search_id"])
    assert out["added"] >= 1
    assert any("from_publication_date:2026-01-01" in p.get("filter", "") for _s, _p, p in fake.requests)


def test_a_search_that_fails_keeps_its_error_and_its_old_findings(project, fake):
    s = literature.save_search(project, "remote work")
    with project.connect() as cx:
        cx.execute("UPDATE lit_searches SET since='2026-01-01' WHERE search_id=?", (s["search_id"],))
    literature.check_search(project, s["search_id"])
    before = literature.get_search(project, s["search_id"])["new"]
    fake.mode = "rate_limited"
    with pytest.raises(LiteratureError):
        literature.check_search(project, s["search_id"])
    row = literature.get_search(project, s["search_id"])
    assert row["new"] == before and "slow down" in row["error"]


def test_a_saved_search_is_stale_after_a_few_hours(project):
    s = literature.save_search(project, "remote work")
    assert literature.stale(s) is True   # never looked at
    s["last_checked_at"] = literature.now()
    assert literature.stale(s) is False
    s["last_checked_at"] = "2020-01-01T00:00:00+00:00"
    assert literature.stale(s) is True


# ---------------------------------------------------------------------------------------------
# sending works to Zotero, and RIS / BibTeX
# ---------------------------------------------------------------------------------------------
def _two_works(project, fake):
    works = literature.search(project, "remote work wellbeing loneliness")["works"]
    return [w for w in works if w["doi"] in ("10.5555/lhp.2025.1", "10.1000/lonely.2023.3")]


def test_works_are_sent_to_the_collection_selected_in_zotero(project, fake, zotero):
    works = _two_works(project, fake)
    assert len(works) == 2
    out = literature.send_to_zotero(works)
    assert out == {"sent": 2, "library": "My Library", "collection": "Remote work"}
    posted = [p for p in zotero.posts if p[0] == "/connector/saveItems"]
    assert len(posted) == 1 and {k.lower(): v for k, v in posted[0][2].items()}.get("x-zotero-connector-api-version") == "3"
    body = posted[0][1]
    assert body["sessionID"] and body["uri"].startswith("https://doi.org/") and len(body["items"]) == 2
    item = next(i for i in zotero.saved if i["DOI"] == "10.5555/lhp.2025.1")
    assert item["itemType"] == "journalArticle" and item["title"].startswith("Working from home")
    assert item["creators"][0] == {"firstName": "M.", "lastName": "Verhoeven", "creatorType": "author"}
    assert item["date"] == "2025" and item["publicationTitle"] == "Journal of Work and Society"
    assert item["volume"] == "12" and item["pages"] == "101-120" and item["abstractNote"].startswith("We follow")
    assert item["attachments"] == [{"title": "Full Text PDF", "url": "https://repo.example/lhp.pdf", "mimeType": "application/pdf"}]
    zotero.saved.clear()
    literature.send_to_zotero(works, attach_pdf=False)
    assert all(i["attachments"] == [] for i in zotero.saved)


def test_zotero_not_being_open_is_said_plainly(project, fake, monkeypatch):
    works = _two_works(project, fake)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        monkeypatch.setenv("MARGIN_ZOTERO_URL", f"http://127.0.0.1:{s.getsockname()[1]}")
    with pytest.raises(LiteratureError) as e:
        literature.send_to_zotero(works)
    assert e.value.kind == "zotero_not_running" and "Open the Zotero app" in str(e.value) and "download" in str(e.value)
    assert literature.zotero_target() == {"state": "not_running"}


def test_zotero_refusing_the_works_is_said_too(project, fake, zotero):
    works = _two_works(project, fake)
    zotero.save_status = 500
    with pytest.raises(LiteratureError) as e:
        literature.send_to_zotero(works)
    assert e.value.kind == "zotero_failed" and "500" in str(e.value)
    zotero.save_status = 201
    zotero.selected = {**zotero.selected, "libraryEditable": False, "name": "Shared"}
    with pytest.raises(LiteratureError) as e:
        literature.send_to_zotero(works)
    assert e.value.kind == "zotero_failed" and "cannot be changed" in str(e.value) and not zotero.saved
    with pytest.raises(LiteratureError):
        literature.send_to_zotero([])
    with pytest.raises(LiteratureError):
        literature.send_to_zotero("nonsense")


def test_works_download_as_ris_and_bibtex(project, fake):
    works = _two_works(project, fake)
    works[0]["title"] = "A {risky} title & 100% of #1_case"
    ris = literature.to_ris(works)
    assert ris.count("TY  - JOUR") == 2 and ris.count("ER  - ") == 2 and "AU  - Verhoeven, M." in ris
    assert "DO  - 10.5555/lhp.2025.1" in ris and "PY  - 2025" in ris and "SP  - 101" in ris and "EP  - 120" in ris
    bib = literature.to_bibtex(works)
    assert bib.count("@article{") == 2 and "author = {Verhoeven, M. and Okafor, A.}" in bib
    assert r"title = {A \{risky\} title \& 100\% of \#1\_case}" in bib
    assert "pages = {101--120}" in bib and "doi = {10.5555/lhp.2025.1}" in bib
    keys = re.findall(r"@article\{([^,]+),", bib)
    assert len(set(keys)) == 2 and keys[0].startswith("verhoeven2025")
    same = literature.to_bibtex([works[0], works[0]])
    assert len(set(re.findall(r"@article\{([^,]+),", same))) == 2   # keys never collide


# ---------------------------------------------------------------------------------------------
# the API
# ---------------------------------------------------------------------------------------------
def _p(name="Lit"):
    return f"/api/projects/{name}/literature"


def test_the_api_end_to_end(api, project, fake, zotero):
    st, info = api("GET", _p())
    assert st == 200 and info["local_only"] is False and info["email"] == "" and info["searches"] == []
    assert [s["id"] for s in info["sources"]] == ["openalex", "crossref", "semanticscholar"]
    assert info["documents"] == {"total": 3, "usable": 3, "not_allowed": 0, "no_doi": 0} and info["drafts"] == []
    st, w = api("POST", _p() + "/words", {"text": "Remote work lowers the quality of public services."})
    assert st == 200 and "services" in w["words"]
    assert api("POST", _p() + "/words", {})[0] == 400
    assert fake.requests == []
    st, r = api("POST", _p() + "/search", {"words": "remote work wellbeing", "claim": "Remote work raises wellbeing"})
    assert st == 200 and r["works"][0]["closeness"] >= r["works"][-1]["closeness"] and r["ranked_by"] == "words"
    assert r["sent"]["service"] == "OpenAlex" and "remote work wellbeing" in r["sent"]["text"]
    st, e = api("POST", _p() + "/search", {"words": ""})
    assert st == 400 and e["kind"] == "bad_request"
    assert api("POST", _p() + "/search", {"words": "x", "source": "nope"})[0] == 400
    # open copies need an address
    st, e = api("POST", _p() + "/open-copies", {"dois": ["10.1000/commute.2016.2"]})
    assert st == 409 and e["kind"] == "no_email"
    assert api("PUT", "/api/settings", {"contact_email": "me@example.org"})[0] == 200
    assert api("PUT", "/api/settings", {"contact_email": "not an address"})[0] == 400
    st, o = api("POST", _p() + "/open-copies", {"dois": ["10.1000/commute.2016.2"]})
    assert st == 200 and o["copies"]["10.1000/commute.2016.2"]["pdf_url"].endswith("commute.pdf")
    # saved searches
    st, saved = api("POST", _p() + "/searches", {"words": "remote work", "title": "Remote work", "from_year": 2020, "oa_only": False})
    sid = saved["search"]["search_id"]
    assert st == 200 and saved["search"]["filters"] == {"from_year": 2020, "oa_only": False}
    st, c = api("POST", _p() + f"/searches/{sid}/check")
    assert st == 200 and "works" in c and c["search"]["last_checked_at"]
    st, got = api("GET", _p() + f"/searches/{sid}")
    assert st == 200 and got["search"]["search_id"] == sid
    st, seen = api("POST", _p() + f"/searches/{sid}/seen")
    assert st == 200 and seen["search"]["new"] == 0
    assert api("GET", _p() + "/searches")[1]["searches"][0]["search_id"] == sid
    assert api("DELETE", _p() + f"/searches/{sid}")[0] == 200
    assert api("GET", _p() + f"/searches/{sid}")[0] == 404
    # following citations: what will be sent, then the lookup
    st, plan = api("GET", _p() + "/citations")
    assert st == 200 and plan["included"] == 3 and "_by_doi" not in plan
    st, fc = api("POST", _p() + "/citations", {})
    assert st == 200 and fc["cited"] and fc["citing"]
    # Zotero and downloads
    works = r["works"][:2]
    st, z = api("GET", "/api/literature/zotero")
    assert st == 200 and z == {"state": "ready", "library": "My Library", "collection": "Remote work", "editable": True}
    st, sent = api("POST", "/api/literature/zotero", {"works": works})
    assert st == 200 and sent["sent"] == 2 and sent["collection"] == "Remote work"
    assert api("POST", "/api/literature/zotero", {"works": []})[0] == 400
    st, ris = api("POST", "/api/literature/export", {"works": works, "format": "ris"})
    assert st == 200 and b"TY  - JOUR" in ris
    st, bib = api("POST", "/api/literature/export", {"works": works, "format": "bibtex"})
    assert st == 200 and b"@article{" in bib
    assert api("POST", "/api/literature/export", {"works": works, "format": "word"})[0] == 400
    assert api("POST", "/api/literature/zotero", {"works": works}, token=False)[0] == 401
    # the project's overview counts what is new, and the cache can be forgotten
    assert api("DELETE", _p() + "/cache")[1]["forgotten"] >= 1


def test_the_api_refuses_a_lookup_that_may_not_go_out(api, project, fake, monkeypatch):
    did = drafts.new_draft(project, DRAFT, "Local draft", ai_access="local")
    st, e = api("POST", _p() + "/search", {"words": "unicorn", "draft_id": did})
    assert st == 403 and e["kind"] == "not_allowed"
    monkeypatch.setenv("MARGIN_LOCAL_ONLY", "1")
    st, e = api("POST", _p() + "/search", {"words": "unicorn"})
    assert st == 403 and e["kind"] == "local_only"
    st, info = api("GET", _p())
    assert st == 200 and info["local_only"] is True
    st, e = api("POST", _p() + "/citations", {})
    assert st == 403 and e["kind"] == "local_only"
    assert fake.requests == []


def test_the_overview_counts_the_works_new_on_saved_searches(api, project, fake):
    assert api("GET", "/api/projects/Lit/overview")[1]["literature"] == {"searches": 0, "new": 0}
    sid = literature.save_search(project, "remote work")["search_id"]
    with project.connect() as cx:
        cx.execute("UPDATE lit_searches SET since='2026-09-30' WHERE search_id=?", (sid,))
    n = len(fake.requests)
    assert api("GET", "/api/projects/Lit/overview")[1]["literature"] == {"searches": 1, "new": 0}
    assert len(fake.requests) == n   # the Overview never asks a service
    api("POST", _p() + f"/searches/{sid}/check")
    assert api("GET", "/api/projects/Lit/overview")[1]["literature"] == {"searches": 1, "new": 3}


def test_the_draft_api_lists_the_claims_to_find_literature_for(api, project, fake):
    did = drafts.new_draft(project, DRAFT, "Draft", ai_access="cloud")
    drafts.find_by_rules(project, did)
    drafts.check_claims(project, did, BaselineBackend(), "baseline", k=4, per_doc=2, expand=True)
    st, out = api("GET", _p() + f"/draft/{did}")
    assert st == 200 and out["searchable"] is True and out["claims"]
    st, info = api("GET", _p())
    assert info["drafts"][0]["draft_id"] == did and info["drafts"][0]["ai_access"] == "cloud"
    assert api("GET", _p() + "/draft/nodraft")[0] == 404
