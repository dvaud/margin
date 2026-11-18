"""I7 stage 3: cloud providers in a shared project (teamproviders.py, ailog.py).

- each person reads with the provider they chose: a Member's own provider reads the project's `cloud` documents on
  their copy; their consent is theirs (never merged into a colleague's copy, not carried by a zip or a new document);
- the owner may limit the providers the team may use (off by default): the limit reaches a member through a merge,
  is lifted the same way, and a new owner's limit reaches the former owner; a Member cannot set it; a provider outside
  it reads nothing, and the note names the limit and who set it;
- the AI log: rows from two people, with person, provider, model, kind and subject; a row a file brings in this
  person's own name names nobody; filters by person and provider;
- an old database gains the ledger's new columns, and its rows read as this person's while the project is not shared.

Two people exchanging zips of a small text project (no shared folder): light on the disk.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from _views import needs_node, run_views
from margin import access, ailog, home, ingest, ownership, teamcodebooks, teamproviders
from margin.gui import server
from margin.store import Workspace
from owner_more_helpers import join_zip, small_project, zips
from test_shared_projects import Person


@pytest.fixture
def team(tmp_path, monkeypatch):
    """Anna's small project (she owns it) and Ben's copy from her zip; they have exchanged once."""
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    anna = Person(tmp_path, "Anna", monkeypatch)
    small_project(anna, tmp_path / "anna-project", keys=("desalination", "jobs"))
    with anna:
        access.set_default(anna.ws, "cloud")
    ben = Person(tmp_path, "Ben", monkeypatch)
    join_zip(ben, anna, tmp_path / "ben-project")
    zips(ben, anna)
    return anna, ben


def _docs(p: Person) -> list[str]:
    with p:
        return [r[0] for r in p.ws.query("SELECT doc_id FROM documents ORDER BY doc_id")]


def _levels(p: Person, provider):
    with p:
        return access.levels(p.ws, provider=provider)


def _passages(p: Person, n: int = 2) -> list[str]:
    with p:
        return [r[0] for r in p.ws.query("SELECT passage_id FROM passages ORDER BY passage_id LIMIT ?", (n,))]


# ---------------------------------------------------------------------------------------------
# 1. each person chooses their own provider
# ---------------------------------------------------------------------------------------------
def test_a_members_own_provider_reads_the_cloud_documents_in_a_shared_project(team):
    anna, ben = team
    with ben:
        assert access.is_shared(ben.ws._conn(), ben.ws)
        assert set(_levels(ben, "openai").values()) == {"local"}   # not allowed by Ben yet: Anthropic only
        access.set_providers_default(ben.ws, ["anthropic", "openai"])   # no longer refused in a shared project
        info = access.project_info(ben.ws)
    assert info["shared"] and info["team_limit"] is None and info["providers_note"] is None
    assert set(_levels(ben, "openai").values()) == {"cloud"}
    assert set(_levels(ben, "anthropic").values()) == {"cloud"}
    with ben:  # the research log tells the team, and says it is Ben's own choice
        entry = ben.ws.query("SELECT text, person_id FROM research_log WHERE kind='ai-access' ORDER BY at DESC")[0]
    assert "OpenAI" in entry["text"] and "own choice" in entry["text"] and entry["person_id"] == ben.id
    # a document's own list too
    with ben:
        access.set_documents(ben.ws, [_docs(ben)[0]], allow=["gemini"])
    assert _levels(ben, "gemini")[_docs(ben)[0]] == "cloud"


def test_consent_is_each_persons_own_and_never_merged(team, tmp_path):
    anna, ben = team
    first = _docs(ben)[0]
    with ben:
        access.set_providers_default(ben.ws, ["anthropic", "openai"])
        access.set_documents(ben.ws, [first], allow=["openai", "mistral"])
        f = tmp_path / "bens-new.txt"
        f.write_text("Desalination plants in arid regions need energy and brine disposal. " * 8, encoding="utf-8")
        ingest.ingest(ben.ws, [f])
        new = [d for d in _docs(ben) if d not in _docs(anna)]
        access.set_documents(ben.ws, new, allow=["openai"])
    zips(ben, anna)
    with anna:
        rows = {r[0]: r[1] for r in anna.ws.query("SELECT doc_id, ai_providers FROM documents")}
        assert new and set(new) <= set(rows)            # Ben's new document came in
        assert all(v is None for v in rows.values())     # with none of Ben's lists
        assert access.providers_default(anna.ws) == ["anthropic"]
    assert set(_levels(anna, "openai").values()) == {"local"}
    # a copy made from Ben's whole project starts without his lists
    chloe = Person(tmp_path, "Chloe", ben.mp)
    join_zip(chloe, ben, tmp_path / "chloe-project")
    with chloe:
        assert chloe.ws.query("SELECT COUNT(*) AS n FROM documents WHERE ai_providers IS NOT NULL")[0]["n"] == 0
        assert access.providers_default(chloe.ws) == ["anthropic"]
    with ben:  # Ben's own copy keeps them
        assert json.loads(ben.ws.scalar("SELECT ai_providers FROM documents WHERE doc_id=?", (first,))) == \
            ["openai", "mistral"]


# ---------------------------------------------------------------------------------------------
# 2. the owner's limit
# ---------------------------------------------------------------------------------------------
def test_the_owners_limit_reaches_a_member_and_is_lifted_the_same_way(team):
    anna, ben = team
    with ben:
        access.set_providers_default(ben.ws, ["anthropic", "openai"])
        assert teamproviders.view(ben.ws)["limit"] is None
    with anna:
        v = teamproviders.set_limit(anna.ws, ["anthropic"])
    assert v["limit"]["providers"] == ["anthropic"] and v["limit"]["by"]["me"] and v["can_set"]
    with ben:  # not here yet
        assert set(access.levels(ben.ws, provider="openai").values()) == {"cloud"}
    zips(anna, ben)
    with ben:
        v = teamproviders.view(ben.ws)
        assert v["limit"]["providers"] == ["anthropic"] and v["limit"]["by"]["id"] == anna.id and not v["can_set"]
        assert set(access.levels(ben.ws, provider="openai").values()) == {"local"}
        assert set(access.levels(ben.ws, provider="anthropic").values()) == {"cloud"}
        assert set(access.levels(ben.ws, provider=None).values()) == {"cloud"}   # the setting as chosen stays
        note = teamproviders.note(ben.ws._conn(), "openai")
        assert note.startswith("The team uses Anthropic only (set by Anna)") and "OpenAI reads none" in note
        info = access.project_info(ben.ws)
        assert info["team_limit"]["providers"] == ["anthropic"] and "set by Anna" in info["providers_note"]
        assert any("may use Anthropic only" in r[0] for r in ben.ws._conn().execute(
            "SELECT text FROM research_log WHERE kind='owner'"))
        with pytest.raises(ownership.NotAllowed):
            teamproviders.set_limit(ben.ws, None)
        assert teamproviders.note(ben.ws._conn(), "anthropic") is None
    with anna:  # the owner's own copy follows it too
        assert set(access.levels(anna.ws, provider="openai").values()) == {"local"}
        teamproviders.set_limit(anna.ws, None)
    zips(anna, ben)
    with ben:
        assert teamproviders.view(ben.ws)["limit"] is None
        assert set(access.levels(ben.ws, provider="openai").values()) == {"cloud"}


def test_a_new_owners_limit_reaches_the_former_owner(team):
    anna, ben = team
    with anna:
        teamproviders.set_limit(anna.ws, ["anthropic", "openai"])
        ownership.hand_over(anna.ws, ben.id)
    zips(anna, ben)
    with ben:
        ownership.settle(ben.ws)
        assert teamproviders.view(ben.ws)["can_set"]
        assert teamproviders.limit(ben.ws._conn())["providers"] == ["anthropic", "openai"]  # written again as his
        teamproviders.set_limit(ben.ws, ["openai"])
    zips(ben, anna)
    with anna:
        lim = teamproviders.limit(anna.ws._conn())
        assert lim["providers"] == ["openai"] and lim["by"] == ben.id
        with pytest.raises(ownership.NotAllowed):
            teamproviders.set_limit(anna.ws, None)
        access.set_providers_default(anna.ws, ["anthropic", "openai"])
        lv = access.levels(anna.ws, provider="anthropic")
        assert set(lv.values()) == {"local"}  # Anthropic is outside the team's limit now
        assert set(access.levels(anna.ws, provider="openai").values()) == {"cloud"}


def test_a_members_limit_row_counts_for_nothing(team):
    anna, ben = team
    with ben:
        with ben.ws.connect() as cx:
            teamcodebooks._write(cx, teamproviders.KEY, ben.id, 1, 9, ["mistral"])
        assert teamproviders.limit(ben.ws._conn()) is None
    zips(ben, anna)
    with anna:
        assert teamproviders.limit(anna.ws._conn()) is None


def test_a_limit_must_name_known_providers(team):
    anna, _ben = team
    with anna:
        with pytest.raises(ValueError):
            teamproviders.set_limit(anna.ws, [])
        with pytest.raises(ValueError):
            teamproviders.set_limit(anna.ws, ["nobody"])
        with anna.ws.connect() as cx:   # a row that is not a list of providers is not taken
            cx.execute("INSERT OR REPLACE INTO team_settings(key, by, owner_seq, n, value_json, at) VALUES "
                       "(?,?,?,?,?,?)", (teamproviders.KEY, anna.id, 1, 99, json.dumps(["openai", "nobody"]), "x"))
        assert teamproviders.limit(anna.ws._conn()) is None


def test_the_held_note_names_the_limit_and_who_set_it(team):
    from margin import claimcheck, tasks

    anna, ben = team
    with anna:
        teamproviders.set_limit(anna.ws, ["anthropic"])
    zips(anna, ben)
    with ben:
        access.set_providers_default(ben.ws, ["anthropic", "openai"])
        home.update_settings({"allow_codex": True, "backend": "codex"})
        hid = "h-limit"
        with ben.ws.connect() as cx:
            cx.execute("INSERT INTO hypotheses(hyp_id, text, created_at) VALUES (?,?,?)", (hid, "Water.", "now"))
            cx.execute("INSERT INTO user_claims(claim_id, text, hyp_id, part, stage) VALUES (?,?,?,0,'judge')",
                       ("c-limit", "Water.", hid))
            pids = _passages(ben, 2)
            payload = {"claim": "Water.", "passages": [{"passage_id": p, "doc_id": p.split(":")[0], "text": "t"}
                                                       for p in pids]}
            with tasks.queueing(False):
                claimcheck._add_round(ben.ws, "c-limit", "check:c-limit", payload, "m", cx=cx, provider="openai",
                                      hold=True)
        held = claimcheck.held_parts(ben.ws, [hid])
    assert held and held[0]["why"] == "limit"
    with ben:
        note = teamproviders.note(ben.ws._conn(), "openai")
    assert "The team uses Anthropic only (set by Anna)" in note
    with anna:  # lifted: the same part is held only for Ben's own consent, which he gave
        teamproviders.set_limit(anna.ws, None)
    zips(anna, ben)
    with ben:
        assert teamproviders.allows(ben.ws._conn(), "openai")
        assert set(access.levels(ben.ws, pids and [p.split(":")[0] for p in pids], provider="openai").values()) == \
            {"cloud"}


# ---------------------------------------------------------------------------------------------
# 3. the AI log
# ---------------------------------------------------------------------------------------------
def test_ai_log_rows_from_two_people_with_person_provider_and_model(team):
    anna, ben = team
    pa, pb = _passages(anna, 3), _passages(ben, 2)
    with anna:
        with anna.ws.connect() as cx:
            access.record_sent(cx, None, [{"passage_id": p} for p in pa], "Claude Code", "check", context=False,
                               model="claude-sonnet-5-5")
    with ben:
        with ben.ws.connect() as cx:
            # a search through the connector started for Codex (no task: nothing private about it)
            access.record_sent(cx, None, [{"passage_id": p} for p in pb], "Codex (connector)", "search",
                               context=False, provider="openai", model="gpt-6")
            # his labels of a codebook he did not share: private work
            access.record_sent(cx, "label:sdg:" + pb[0], [{"passage_id": pb[0]}], "Codex", "label",
                               context=False, provider="openai", model="gpt-6")
            # a row Ben's file says Anna sent, which Anna's copy does not hold
            cx.execute("INSERT INTO ai_sent(passage_id, doc_id, route, task_id, sent_at, feature, provider, person_id, "
                       "model) VALUES (?,?,?,?,?,?,?,?,?)", (pb[0], pb[0].split(":")[0], "Claude Code", None,
                                                             "2026-11-18T09:00:00", "check", "anthropic", anna.id, "x"))
    zips(ben, anna)
    zips(anna, ben)
    with anna:
        log = ailog.entries(anna.ws)
    rows = log["rows"]
    mine = [r for r in rows if r["person"] and r["person"]["me"]]
    bens = [r for r in rows if r["person"] and r["person"]["id"] == ben.id]
    assert len(mine) == 1 and mine[0]["provider"] == "anthropic" and mine[0]["excerpts"] == 3
    assert mine[0]["model"] == "claude-sonnet-5-5" and mine[0]["kind_words"] == "Check" and mine[0]["route"] == "Claude Code"
    assert len(bens) == 1 and bens[0]["provider"] == "openai" and bens[0]["provider_title"] != "openai"
    assert bens[0]["person"]["name"] == "Ben" and bens[0]["model"] == "gpt-6" and bens[0]["excerpts"] == 2
    assert bens[0]["kind_words"].startswith("Search") and bens[0]["route"] == "Codex (connector)"
    # his private work: the task, his name and the model are masked as it leaves (sharing._masked)
    private = [r for r in rows if r["subject"] and r["subject"]["kind"] == "private"]
    assert len(private) == 1 and private[0]["person"] is None and private[0]["model"] == ""
    assert private[0]["provider"] == "openai" and private[0]["subject"]["href"] is None
    forged = [r for r in rows if r["at"] == "2026-11-18T09:00:00"]
    assert len(forged) == 1 and forged[0]["person"] is None   # not taken in Anna's name (merge fix_sent)
    assert {p["id"] for p in log["people"]} == {anna.id, ben.id, ailog.UNKNOWN}
    with anna:
        only_ben = ailog.entries(anna.ws, person=ben.id)["rows"]
        only_openai = ailog.entries(anna.ws, provider="openai")["rows"]
        only_me = ailog.entries(anna.ws, person="me")["rows"]
    assert [r["person"]["id"] for r in only_ben] == [ben.id]
    assert sorted(r["provider"] for r in only_openai) == ["openai", "openai"]
    assert [r["person"]["id"] for r in only_me] == [anna.id]
    with ben:  # Ben's copy has Anna's row too; in his own, his label row names its codebook and him
        brows = ailog.entries(ben.ws)["rows"]
    assert any(r["person"] and r["person"]["id"] == anna.id for r in brows)
    own_label = [r for r in brows if r["person"] and r["person"]["me"] and r["kind"] == "label"]
    assert own_label and own_label[0]["subject"]["kind"] == "codebook" and own_label[0]["subject"]["id"] == "sdg"
    assert own_label[0]["model"] == "gpt-6"


def test_an_old_database_gains_the_columns_and_its_rows_are_this_persons_while_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGIN_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGIN_LOCAL_ONLY", raising=False)
    me = Person(tmp_path, "Dora", monkeypatch)
    ws = small_project(me, tmp_path / "old", keys=("desalination",))
    pid = ws.scalar("SELECT passage_id FROM passages LIMIT 1")
    ws.close()
    cx = sqlite3.connect(ws.db_path)
    for c in ("person_id", "model"):
        cx.execute(f"ALTER TABLE ai_sent DROP COLUMN {c}")
    cx.execute("INSERT INTO ai_sent(passage_id, doc_id, route, task_id, sent_at, feature, provider) VALUES "
               "(?,?,?,?,?,?,?)", (pid, pid.split(":")[0], "Claude Code", None, "2026-11-01T10:00:00", "search", None))
    cx.commit()
    cx.close()
    with me:
        ws = Workspace.open(ws.root)
        cols = {r[1] for r in ws._conn().execute("PRAGMA table_info(ai_sent)")}
        assert {"person_id", "model"} <= cols
        rows = ailog.entries(ws)["rows"]
        assert len(rows) == 1 and rows[0]["person"]["me"] and rows[0]["provider"] == "anthropic"
        assert rows[0]["kind_words"].startswith("Search") and rows[0]["model"] == ""
        from margin.sync.folder import FOLDER

        access._write_config(ws, {FOLDER: str(tmp_path / "team")})   # shared now: whose it was is not known
        assert ailog.entries(ws)["rows"][0]["person"] is None
        ws.close_all()


def test_the_routes_are_there():
    for method, path, name in (("GET", "/api/projects/Demo/owner/providers", "get_owner_providers"),
                               ("PUT", "/api/projects/Demo/owner/providers", "put_owner_providers"),
                               ("GET", "/api/projects/Demo/ai-log", "get_ai_log")):
        hits = [n for m, rx, n in server.ROUTES if m == method and rx.match(path)]
        assert hits == [name]


# ---------------------------------------------------------------------------------------------
# review fixes (19 November 2026)
# ---------------------------------------------------------------------------------------------
def test_lists_inherited_from_colleagues_are_cleared_once_and_this_persons_own_are_kept(team, tmp_path):
    from margin.store import Workspace as W

    anna, ben = team
    a, b = _docs(ben)[:2]
    with ben:
        access.set_documents(ben.ws, [b], allow=["anthropic", "mistral"])   # his own: in the research log
        with ben.ws.connect() as cx:   # as 0.20.0 left it: Anna's pre-share tick, copied with her document
            cx.execute("UPDATE documents SET ai_providers=? WHERE doc_id=?", (json.dumps(["anthropic", "openai"]), a))
            cx.execute("DELETE FROM meta WHERE key IN (?, ?)", (access.OWN_PROVIDERS_DONE, access.PROVIDERS_RESET))
        ben.ws.close_all()
        ws = W.open(ben.ws.root)   # opening the project runs the one-off check
        rows = {r[0]: r[1] for r in ws.query("SELECT doc_id, ai_providers FROM documents")}
        assert rows[a] is None and json.loads(rows[b]) == ["anthropic", "mistral"]
        assert access.levels(ws, [a], provider="openai") == {a: "local"}
        info = access.project_info(ws)
        assert info["providers_reset"]["documents"] == 1
        assert access.settle_own_providers(ws) == 0          # once
        access.set_providers_default(ws, ["anthropic"])      # ticking again: the note goes
        assert access.project_info(ws)["providers_reset"] is None
        ws.close_all()
    # a project not shared keeps every list, and is not asked again
    dora = Person(tmp_path, "Dora", anna.mp)
    small_project(dora, tmp_path / "dora", keys=("desalination",))
    with dora:
        d = _docs(dora)[0]
        with dora.ws.connect() as cx:
            cx.execute("UPDATE documents SET ai_providers=? WHERE doc_id=?", (json.dumps(["openai"]), d))
            cx.execute("DELETE FROM meta WHERE key=?", (access.OWN_PROVIDERS_DONE,))
        assert access.settle_own_providers(dora.ws) == 0
        assert dora.ws.scalar("SELECT ai_providers FROM documents WHERE doc_id=?", (d,)) is not None


def test_setting_or_lifting_the_limit_relabels_the_open_tasks(team):
    from margin import tasks

    anna, _ben = team
    pid = _passages(anna, 1)[0]
    with anna:
        access.set_providers_default(anna.ws, ["anthropic", "openai"])
        with anna.ws.connect() as cx:
            access.relabel(cx, provider="openai")   # the main route is Codex: the tasks are labelled for OpenAI
        with tasks.queueing(True):
            with anna.ws.connect() as cx:
                tasks._insert_task(cx, "label:sdg:" + pid, "label", "m",
                                   {"framework": "sdg", "passage_id": pid, "candidates": []})
        state = lambda: anna.ws.query("SELECT access, queued FROM tasks WHERE task_id=?", ("label:sdg:" + pid,))[0]  # noqa: E731
        assert state()["access"] == "cloud"
        teamproviders.set_limit(anna.ws, ["anthropic"])
        assert state()["access"] == "local" and not state()["queued"]
        teamproviders.set_limit(anna.ws, None)
        assert state()["access"] == "cloud"


def test_a_limit_in_the_owners_name_from_someone_elses_file_is_named_in_the_log(team, tmp_path):
    from owner_more_helpers import send

    anna, ben = team
    chloe = Person(tmp_path, "Chloe", anna.mp)
    join_zip(chloe, anna, tmp_path / "chloe-project")
    zips(chloe, anna, ben)
    with ben:   # a changed app: a row in Anna's name, numbered high
        with ben.ws.connect() as cx:
            teamcodebooks._write(cx, teamproviders.KEY, anna.id, 1, 77, ["mistral"])
    chloe.bring_in(send(ben))
    with chloe:
        assert teamproviders.limit(chloe.ws._conn())["providers"] == ["mistral"]   # (not signed: believed until …)
        texts = [r[0] for r in chloe.ws._conn().execute("SELECT text FROM research_log WHERE kind='owner'")]
    assert any("a change in Anna's name (the owner's), which came in Ben's file" in t for t in texts)
    zips(ben, anna)   # Anna's copy refuses it and answers above it
    zips(anna, chloe)
    with chloe:   # … the owner's next round
        assert teamproviders.limit(chloe.ws._conn()) is None


def test_the_connector_records_its_own_provider_and_route(team, monkeypatch):
    from margin import claimcheck, mcp_server

    anna, _ben = team
    monkeypatch.setenv("MARGIN_ROUTE", "codex")
    assert mcp_server.reader() == "openai" and mcp_server.sent_route() == "Codex (connector)"
    monkeypatch.delenv("MARGIN_ROUTE")
    assert mcp_server.sent_route() == access.ROUTE_NAMES["chat"]
    with anna:
        access.set_providers_default(anna.ws, ["anthropic", "openai"])
        claimcheck.open_check(anna.ws, "Desalination needs energy.", terms=["desalination", "energy"], k=3,
                              provider="openai", route="Codex (connector)")
        rows = {(r[0], r[1]) for r in anna.ws._conn().execute("SELECT provider, route FROM ai_sent")}
    assert rows == {("openai", "Codex (connector)")}


def test_the_ledger_never_makes_a_person_id(monkeypatch, tmp_path):
    from margin import people

    monkeypatch.setattr(teamcodebooks, "_my_id", lambda: "not-an-id")
    assert access.sender() is None
    monkeypatch.setattr(teamcodebooks, "_my_id", lambda: "")
    monkeypatch.setattr(people, "me", lambda: (_ for _ in ()).throw(AssertionError("an id was made")))
    assert access.sender() is None
    monkeypatch.setattr(teamcodebooks, "_my_id", lambda: "p0123456789ab")
    assert access.sender() == "p0123456789ab"


# ---------------------------------------------------------------------------------------------
# the page: the AI log (#/log/ai), the way to it, and the owner's AI providers card
# ---------------------------------------------------------------------------------------------
PROBE = r"""
const ROWS = [
  { at: "2026-11-18T10:05:00+00:00", task_id: "check:c1", person: { id: "pa", name: "you", me: true }, provider: "anthropic",
    provider_title: "Anthropic (Claude)", route: "Claude Code", model: "claude-sonnet-5-5", kind: "check", kind_words: "Check",
    excerpts: 6, documents: 3, subject: { kind: "check", word: "Hypothesis", id: "h1", title: "Water stress rises", href: "#/h/h1" }, answered: true },
  { at: "2026-11-18T09:00:00+00:00", task_id: "private", person: { id: "pb", name: "Ben", me: false }, provider: "openai",
    provider_title: "OpenAI", route: "Codex", model: "gpt-6", kind: "label", kind_words: "Profile (AI pass)",
    excerpts: 2, documents: 1, subject: { kind: "private", word: "About", id: null, title: "work not shared with the team", href: null }, answered: false },
];
const LOG = { rows: ROWS, total: 2, team: true, people: [{ id: "pa", name: "you", me: true, n: 1 }, { id: "pb", name: "Ben", me: false, n: 1 }],
  providers: [{ id: "anthropic", title: "Anthropic (Claude)", n: 1 }, { id: "openai", title: "OpenAI", n: 1 }] };

await scenario("the AI log", async (t) => {
  t.state({ settings: {} });
  t.answer("GET /api/projects/Study/ai-log?*", (b, path) => (path.includes("person=pb") ? { ...LOG, rows: [ROWS[1]], total: 1 } : LOG));
  await t.render("views/ailog.js", "renderAiLog", []);
  await t.settle(20);
  const out = { title: t.text(t.view.querySelector("h1")), rows: t.view.querySelectorAll(".ailog-row").map((r) => t.text(r)),
    links: t.view.querySelectorAll(".ailog-row a").map((a) => a.getAttribute("href")) };
  await t.type("Person", "pb");
  await t.settle(20);
  out.filtered = t.view.querySelectorAll(".ailog-row").map((r) => t.text(r));
  out.asked = t.calls.filter((c) => c.method === "GET").map((c) => c.path);
  return out;
});

await scenario("the research log links to the AI log", async (t) => {
  t.state({ settings: {} });
  t.answer("GET /api/projects/Study/log?*", { entries: [], total: 0, groups: {}, group_names: {} });
  t.answer("GET /api/projects/Study/sharing?*", { items: [] });
  t.answer("GET /api/projects/Study/sharing", { items: [] });
  await t.render("views/log.js", "renderLog", []);
  await t.settle(20);
  const a = t.view.querySelector(".page-sub a");
  return { href: a && a.getAttribute("href"), text: a && t.text(a) };
});

await scenario("the cleared ticks are said in place", async (t) => {
  t.state({ settings: {}, providers: { list: [{ id: "anthropic", title: "Anthropic (Claude)" }], set_up: [], other_set_up: false } });
  const m = await t.module("views/ai-access.js");
  const card = m.providersDefaultCard("Study", { providers_default: ["anthropic"], shared: true, providers_reset: { documents: 2, at: "x" } }, () => {});
  const none = m.providersDefaultCard("Study", { providers_default: ["anthropic"], shared: true, providers_reset: null }, () => {});
  document.getElementById("view").appendChild(card);
  return { text: t.text(card), dialogs: document.querySelectorAll("dialog").length, none: none === null };
});

await scenario("the owner's AI providers card", async (t) => {
  t.state({ settings: {} });
  const m = await t.module("views/team-providers.js");
  const CHOICES = [{ id: "anthropic", title: "Anthropic (Claude)" }, { id: "openai", title: "OpenAI" }];
  let v = { team: true, can_set: true, limit: null, choices: CHOICES };
  t.answer("PUT /api/projects/Study/owner/providers", (b) => (v = { ...v, limit: b.providers ? { providers: b.providers, titles: "Anthropic", by: { id: "pa", name: "Anna", me: true } } : null }));
  t.answer("GET /api/state", {});
  const ctx = { project: "Study", data: { providers: v }, refresh: async () => {} };
  const sec = m.PROVIDERS_SECTION.render(ctx);
  document.getElementById("view").appendChild(sec);
  const out = { off: t.hidden(sec.querySelector("fieldset")), text: t.text(sec) };
  await t.click(sec.querySelector("#team-providers-on"));
  out.listShown = !t.hidden(sec.querySelector("fieldset"));
  out.putsBeforeSave = t.calls.filter((c) => c.method === "PUT").length;
  await t.click(sec.querySelector("#team-providers-save"));
  await t.settle(20);
  out.put = t.calls.filter((c) => c.method === "PUT").map((c) => c.body);
  const member = m.PROVIDERS_SECTION.render({ project: "Study", data: { providers: { team: true, can_set: false, choices: CHOICES,
    limit: { providers: ["anthropic"], titles: "Anthropic", by: { id: "pa", name: "Anna", me: false } } } } });
  out.member = t.text(member);
  out.noTeam = m.PROVIDERS_SECTION.render({ project: "Study", data: { providers: { team: false } } }) === null;
  return out;
});
"""


@pytest.fixture(scope="module")
def views(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("team_providers"))


@needs_node
def test_the_ai_log_page_shows_who_sent_what_and_filters(views):
    r = views["the AI log"]
    assert r["title"] == "AI log"
    assert "You sent 6 excerpts from 3 documents to Anthropic (Claude): Check." in r["rows"][0]
    assert "Model claude-sonnet-5-5 · through Claude Code · answered" in r["rows"][0] and "Water stress rises" in r["rows"][0]
    assert "Ben sent 2 excerpts from 1 document to OpenAI: Profile (AI pass)." in r["rows"][1]
    assert "work not shared with the team" in r["rows"][1]
    assert r["links"] == ["#/h/h1"]
    assert len(r["filtered"]) == 1 and "Ben sent" in r["filtered"][0]
    assert any("person=pb" in p for p in r["asked"])


@needs_node
def test_the_research_log_line_leads_to_the_ai_log(views):
    r = views["the research log links to the AI log"]
    assert r["href"] == "#/log/ai" and r["text"].startswith("AI log")


@needs_node
def test_the_cleared_ticks_are_said_on_the_documents_page_without_a_pop_up(views):
    r = views["the cleared ticks are said in place"]
    assert "Your provider ticks for 2 documents of this shared project were cleared" in r["text"]
    assert r["dialogs"] == 0 and r["none"] is True


@needs_node
def test_the_owner_turns_the_limit_on_and_saves_it_and_a_member_reads_it(views):
    r = views["the owner's AI providers card"]
    assert r["off"] is True and "Limit the providers the team may use" in r["text"]
    assert r["listShown"] is True and r["putsBeforeSave"] == 0       # nothing limited until Save
    assert r["put"] == [{"providers": ["anthropic"]}]
    assert "The team uses Anthropic only." in r["member"] and "Set by Anna." in r["member"]
    assert r["noTeam"] is True


def test_opening_a_project_leaves_no_connection_of_the_provider_check_open(tmp_path):
    """Integration of 0.20.1 (CI on Windows and Linux): the once-only provider check runs as a project is opened and
    left its connection open, so the database file stayed open: on Windows a project folder could not be moved, and
    closing a project's copy waited on it."""
    from margin.store import Workspace

    ws = Workspace.create(tmp_path / "p")
    assert getattr(ws._local, "cx", None) is None
    again = Workspace.open(ws.root)
    assert getattr(again._local, "cx", None) is None
    with again.connect() as cx:   # a thread that uses it afterwards opens its own, as before
        assert cx.execute("SELECT 1").fetchone()
