"""Stand-ins for OpenAlex, Crossref, Semantic Scholar and Unpaywall (Margin's Find literature), for the tests and for
`tools/dev_server.py --literature`. One small server speaks the four services' HTTP, each under its own prefix
(`/openalex`, `/crossref`, `/s2`, `/unpaywall`), from a catalogue of invented works about remote work and wellbeing.

    fake = FakeLiterature(); urls = fake.start(); monkeypatch.setenv("MARGIN_OPENALEX_URL", urls["openalex"]) ...
    or fake.install(monkeypatch)

`fake.requests` lists every request as (service, path, params): the tests use it to show that nothing was sent.
`fake.mode`: "ok", "rate_limited" (429 with Retry-After), "down" (503), "no_created_filter" (OpenAlex answers 403 to
`from_created_date`, as a service that keeps it for keyed users would), "refused" (401).
"""
from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse


def work(oid: str, title: str, year: int, doi: str | None, authors: list[str], venue: str, abstract: str, cited: int = 10,
         refs: tuple = (), pdf: str | None = None, created: str = "2025-01-15", type_: str = "article") -> dict:
    return {"id": f"https://openalex.org/{oid}", "doi": f"https://doi.org/{doi}" if doi else None, "title": title,
            "display_name": title, "publication_year": year, "type": type_, "cited_by_count": cited,
            "authorships": [{"author": {"display_name": a}} for a in authors],
            "primary_location": {"landing_page_url": f"https://doi.org/{doi}" if doi else f"https://openalex.org/{oid}",
                                 "source": {"display_name": venue}},
            "best_oa_location": ({"landing_page_url": f"https://repo.example/{oid}", "pdf_url": pdf, "license": "cc-by"}
                                 if pdf else None),
            "open_access": {"is_oa": bool(pdf), "oa_status": "green" if pdf else "closed", "oa_url": pdf},
            "abstract_inverted_index": _invert(abstract), "biblio": {"volume": "12", "issue": "3", "first_page": "101",
                                                                     "last_page": "120"},
            "referenced_works": [f"https://openalex.org/{r}" for r in refs], "created_date": created}


def _invert(text: str) -> dict:
    idx: dict[str, list[int]] = {}
    for i, w in enumerate(text.split()):
        idx.setdefault(w, []).append(i)
    return idx


# the works the documents in the tests have (DOIs match tests' documents), the works they cite, and the works citing them
CATALOGUE = [
    work("W1001", "Working from home and wellbeing: evidence from the Lowland Household Panel, 2019-2024", 2025,
         "10.5555/lhp.2025.1", ["Verhoeven, M.", "Okafor, A."], "Journal of Work and Society",
         "We follow employees before and after the pandemic. Remote work raises life satisfaction.", 40,
         refs=("W2001", "W2002", "W2003"), pdf="https://repo.example/lhp.pdf"),
    work("W1002", "Commuting less, emitting less? A survey of 4,000 workers in the Rivermouth region", 2024,
         "10.5555/rmi.2024.12", ["Rivermouth Mobility Institute"], "Research report", "Remote work reduces commuting "
         "emissions by less than assumed.", 12, refs=("W2002", "W2004")),
    work("W1003", "Hybrid work and productivity: a review", 2025, "10.5555/hyb.2025.3", ["Lindqvist, K."],
         "Review of Work", "Hybrid work lowers productivity in some roles and raises it in others.", 25,
         refs=("W2001", "W2005")),
    # cited by the documents
    work("W2001", "Telework and job satisfaction: a meta-analysis", 2018, "10.1000/tele.2018.1", ["Gajendran, R.", "Harrison, D."],
         "Journal of Applied Psychology", "A meta-analysis of telework, job satisfaction and performance.", 900,
         pdf="https://repo.example/tele.pdf"),
    work("W2002", "Commuting stress and wellbeing", 2016, "10.1000/commute.2016.2", ["Hansson, E."], "Transport Studies",
         "Long commutes harm wellbeing and sleep.", 300),
    work("W2003", "Loneliness among young remote employees", 2023, "10.1000/lonely.2023.3", ["Adeyemi, T.", "Brandt, L."],
         "Work and Health", "Young employees working remotely report loneliness and miss learning from colleagues.", 60),
    work("W2004", "Four-day weeks and emissions", 2022, "10.1000/four.2022.4", ["Haugen, S."], "Climate and Work",
         "A shorter week cuts commuting emissions by about a fifth.", 45),
    work("W2005", "Management by walking around in distributed teams", 2015, None, ["Moreau, C."], "Management Notes",
         "How managers keep contact with staff who work apart.", 20),
    # citing the documents
    work("W3001", "Remote work, wellbeing and parenthood", 2026, "10.1000/parents.2026.1", ["Silva, R."], "Family Studies",
         "Parents of young children gain most from remote work, building on panel evidence of life satisfaction.", 3,
         refs=("W1001", "W2001"), created="2026-09-01", pdf="https://repo.example/parents.pdf"),
    work("W3002", "Hybrid work, commuting and the carbon footprint of offices", 2026, "10.1000/carbon.2026.2",
         ["Nakamura, H."], "Energy and Buildings", "Commuting emissions fall with hybrid work, partly offset by home "
         "heating.", 5, refs=("W1002", "W1001"), created="2026-10-10"),
    work("W3003", "Productivity under hybrid schedules: new field evidence", 2026, "10.1000/prod.2026.3",
         ["Lindgren, A."], "Organization Science", "Field evidence on hybrid work and productivity.", 2,
         refs=("W1003",), created="2026-10-20"),
    # not related to any document
    work("W4001", "Remote work and the quality of public services", 2025, "10.1000/public.2025.4", ["Pereira, J."],
         "Public Administration", "Remote work by civil servants and the quality of public services in municipal "
         "offices.", 8, created="2026-10-25"),
    work("W4002", "Swallow migration in autumn", 2020, "10.1000/birds.2020.5", ["Wren, B."], "Bird Study",
         "Swallows migrate south in autumn.", 4),
]
BY_ID = {w["id"].rsplit("/", 1)[1]: w for w in CATALOGUE}


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]{3,}", s.lower())}


def _abstract(w: dict) -> str:
    idx = w.get("abstract_inverted_index") or {}
    slots = {p: word for word, ps in idx.items() for p in ps}
    return " ".join(slots[i] for i in sorted(slots))


def _score(w: dict, words: str) -> int:
    want = _tokens(words)
    return len(want & _tokens(w["title"] + " " + _abstract(w)))


class FakeLiterature:
    def __init__(self, catalogue: list[dict] | None = None):
        self.catalogue = list(catalogue or CATALOGUE)
        self.mode = "ok"
        self.requests: list[tuple[str, str, dict]] = []
        self.agents: list[str] = []          # the User-Agent of each request
        self.server: ThreadingHTTPServer | None = None

    # -- the answers ----------------------------------------------------------------------
    def _by_id(self) -> dict:
        return {w["id"].rsplit("/", 1)[1]: w for w in self.catalogue}

    def openalex(self, path: str, q: dict) -> tuple[int, object]:
        if path != "/works":
            return 404, {"error": "not found"}
        params = {k: v[0] for k, v in q.items()}
        flt = {}
        for part in (params.get("filter") or "").split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                flt[k] = v
        if "from_created_date" in flt and self.mode == "no_created_filter":
            return 403, {"error": "from_created_date needs an API key"}
        rows = list(self.catalogue)
        if params.get("search"):
            rows = [w for w in rows if _score(w, params["search"]) > 0]
            rows.sort(key=lambda w: (-_score(w, params["search"]), -w["cited_by_count"]))
        if "doi" in flt:
            dois = {d.lower() for d in flt["doi"].split("|")}
            rows = [w for w in rows if (w["doi"] or "").replace("https://doi.org/", "").lower() in dois]
        if "openalex" in flt:
            ids = set(flt["openalex"].split("|"))
            rows = [w for w in rows if w["id"].rsplit("/", 1)[1] in ids]
        if "cites" in flt:
            ids = {"https://openalex.org/" + i for i in flt["cites"].split("|")}
            rows = [w for w in rows if ids & set(w["referenced_works"])]
        if "from_created_date" in flt:
            rows = [w for w in rows if w["created_date"] >= flt["from_created_date"]]
        if "from_publication_date" in flt:
            rows = [w for w in rows if f"{w['publication_year']}-12-31" >= flt["from_publication_date"]]
        if flt.get("is_oa") == "true":
            rows = [w for w in rows if w["open_access"]["is_oa"]]
        if params.get("sort") == "cited_by_count:desc":
            rows.sort(key=lambda w: -w["cited_by_count"])
        n = int(params.get("per-page") or 25)
        return 200, {"meta": {"count": len(rows)}, "results": rows[:n]}

    def crossref(self, path: str, q: dict) -> tuple[int, object]:
        if path != "/works":
            return 404, {"error": "not found"}
        words = (q.get("query.bibliographic") or [""])[0]
        rows = [w for w in self.catalogue if _score(w, words) > 0]
        rows.sort(key=lambda w: -_score(w, words))
        items = [{"DOI": (w["doi"] or "").replace("https://doi.org/", ""), "title": [w["title"]],
                  "author": [{"given": a.split(", ")[-1], "family": a.split(", ")[0]} for a in
                             [x["author"]["display_name"] for x in w["authorships"]]],
                  "issued": {"date-parts": [[w["publication_year"]]]}, "container-title": [w["primary_location"]["source"]["display_name"]],
                  "URL": w["primary_location"]["landing_page_url"], "abstract": f"<jats:p>{_abstract(w)}</jats:p>",
                  "is-referenced-by-count": w["cited_by_count"], "type": "journal-article"} for w in rows]
        return 200, {"status": "ok", "message": {"items": items[:int((q.get('rows') or ['20'])[0])]}}

    def s2(self, path: str, q: dict) -> tuple[int, object]:
        if path != "/paper/search":
            return 404, {"error": "not found"}
        words = (q.get("query") or [""])[0]
        rows = [w for w in self.catalogue if _score(w, words) > 0]
        rows.sort(key=lambda w: -_score(w, words))
        if "openAccessPdf" in q:
            rows = [w for w in rows if w["open_access"]["is_oa"]]
        data = [{"paperId": w["id"][-5:], "title": w["title"], "year": w["publication_year"],
                 "authors": [{"name": a["author"]["display_name"]} for a in w["authorships"]],
                 "externalIds": {"DOI": (w["doi"] or "").replace("https://doi.org/", "")} if w["doi"] else {},
                 "abstract": _abstract(w), "venue": w["primary_location"]["source"]["display_name"],
                 "citationCount": w["cited_by_count"], "url": f"https://s2.example/{w['id'][-5:]}",
                 "openAccessPdf": {"url": w["open_access"]["oa_url"]} if w["open_access"]["oa_url"] else None}
                for w in rows]
        return 200, {"total": len(data), "offset": 0, "data": data[:int((q.get('limit') or ['20'])[0])]}

    def unpaywall(self, path: str, q: dict) -> tuple[int, object]:
        if not (q.get("email") or [""])[0]:
            return 422, {"error": True, "message": "Please use the email parameter"}
        doi = unquote(path.lstrip("/")).lower()
        w = next((w for w in self.catalogue if (w["doi"] or "").endswith(doi)), None)
        if w is None:
            return 404, {"error": True, "message": "not found"}
        if doi == "10.1000/commute.2016.2":   # a closed work that Unpaywall nevertheless has a copy of
            return 200, {"is_oa": True, "oa_status": "green", "best_oa_location": {
                "url": "https://repo.example/commute", "url_for_landing_page": "https://repo.example/commute",
                "url_for_pdf": "https://repo.example/commute.pdf", "license": None}}
        if not w["open_access"]["is_oa"]:
            return 200, {"is_oa": False, "oa_status": "closed", "best_oa_location": None}
        return 200, {"is_oa": True, "oa_status": "green", "best_oa_location": {
            "url": w["open_access"]["oa_url"], "url_for_landing_page": f"https://repo.example/{doi}",
            "url_for_pdf": w["open_access"]["oa_url"], "license": "cc-by"}}

    # -- the server ------------------------------------------------------------------------
    def start(self) -> dict[str, str]:
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                u = urlparse(self.path)
                m = re.match(r"^/(openalex|crossref|s2|unpaywall)(/.*)$", u.path)
                q = parse_qs(u.query)
                if not m:
                    return self._send(404, {"error": "no such service"})
                service, path = m.groups()
                fake.requests.append((service, path, {k: v[0] for k, v in q.items()}))
                fake.agents.append(self.headers.get("User-Agent") or "")
                if fake.mode == "rate_limited":
                    return self._send(429, {"error": "slow down"}, {"Retry-After": "30"})
                if fake.mode == "down":
                    return self._send(503, {"error": "down"})
                if fake.mode == "refused":
                    return self._send(401, {"error": "key needed"})
                status, body = getattr(fake, service)(path, q)
                self._send(status, body)

            def _send(self, status, body, extra=None):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        root = f"http://127.0.0.1:{self.server.server_address[1]}"
        return {"openalex": root + "/openalex", "crossref": root + "/crossref", "s2": root + "/s2",
                "unpaywall": root + "/unpaywall"}

    def env(self, urls: dict) -> dict[str, str]:
        return {"MARGIN_OPENALEX_URL": urls["openalex"], "MARGIN_CROSSREF_URL": urls["crossref"],
                "MARGIN_S2_URL": urls["s2"], "MARGIN_UNPAYWALL_URL": urls["unpaywall"]}

    def install(self, monkeypatch) -> "FakeLiterature":
        urls = self.start()
        for k, v in self.env(urls).items():
            monkeypatch.setenv(k, v)
        return self

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def sent(self, service: str | None = None) -> list:
        return [r for r in self.requests if service in (None, r[0])]
