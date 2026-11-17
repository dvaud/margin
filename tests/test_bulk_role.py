"""Roadmap N3: one role for many documents, from the Documents list's bulk bar.

`docrole.set_roles` gives many documents a role by the rules of one (each document's one `role:` block choice, so it
travels and is proposed as one document's mark is), with ONE research-log entry for the batch that names the role each
had before (Undo uses it). The Non-scientific mark stays. The route is PUT /api/projects/<p>/document-roles; the bar's
Role menu asks, sends the ticked documents, and offers Undo (views/doc-role.js, views/sources.js).
"""
from __future__ import annotations

import json

import pytest

from _views import needs_node, run_views
from margin import docrole, ingest
from margin.store import Workspace
from owner_helpers import TEXTS


@pytest.fixture
def project(tmp_path):
    ws = Workspace.create(tmp_path / "proj")
    d = tmp_path / "docs"
    d.mkdir()
    for key in ("desalination", "jobs", "grid"):
        (d / f"{key}.txt").write_text(TEXTS[key], encoding="utf-8")
    ingest.ingest(ws, [d])
    ids = sorted(r[0] for r in ws.query("SELECT doc_id FROM documents"))
    yield ws, ids
    ws.close_all()


def _roles(ws):
    return {r[0]: r[1] for r in ws.query("SELECT doc_id, role FROM documents")}


def test_many_documents_take_one_role_with_one_log_entry(project):
    ws, (a, b, c) = project
    docrole.set_role(ws, a, "working")
    before = ws.scalar("SELECT COUNT(*) FROM research_log WHERE kind='document-role'")
    out = docrole.set_roles(ws, [a, b, c], "theory", why="our framework books")
    assert sorted(out["changed"]) == [a, b, c] and out["unchanged"] == []
    assert out["was"] == {a: "working", b: None, c: None}
    assert _roles(ws) == {a: "theory", b: "theory", c: "theory"}
    # each document's one role: choice, as one document's mark is (so it travels and merges the same way)
    for d in (a, b, c):
        assert [r[0] for r in ws.query("SELECT fp FROM block_choices WHERE doc_id=? AND fp LIKE 'role:%'", (d,))] == [
            "role:theory"]
    rows = ws.query("SELECT subject_kind, subject_id, text, why, data_json FROM research_log WHERE kind='document-role' "
                    "ORDER BY at, rowid")
    assert len(rows) == before + 1                             # one entry for the batch, not three
    kind, sid, text, why, data = rows[-1]
    assert (kind, sid, why) == ("documents", None, "our framework books")
    assert text.startswith("3 documents marked as theory") and "The documents: " in text
    assert json.loads(data) == {"role": "theory", "was": {a: "working", b: None, c: None}, "documents": [a, b, c]}
    assert docrole.theory_docs(ws._conn()) == {a, b, c} and not docrole.working_docs(ws._conn())


def test_a_document_that_has_the_role_already_is_no_change(project):
    ws, (a, b, c) = project
    docrole.set_role(ws, a, "theory")
    n = ws.scalar("SELECT COUNT(*) FROM research_log")
    out = docrole.set_roles(ws, [a, b], "theory")
    assert out["changed"] == [b] and out["unchanged"] == [a] and out["was"] == {b: None}
    log = ws.query("SELECT subject_kind, subject_id, text FROM research_log ORDER BY at DESC, rowid DESC LIMIT 1")[0]
    assert ws.scalar("SELECT COUNT(*) FROM research_log") == n + 1
    assert (log[0], log[1]) == ("document", b) and log[2] == docrole.ROLE_LOG["theory"]   # one changed: as one mark
    out = docrole.set_roles(ws, [a, b], "theory")
    assert out["changed"] == [] and ws.scalar("SELECT COUNT(*) FROM research_log") == n + 1   # nothing: no entry


def test_evidence_again_and_the_nonscientific_mark_stays(project):
    ws, (a, b, c) = project
    docrole.set_nonscientific(ws, b, True)
    docrole.set_roles(ws, [a, b], "working")
    assert docrole.is_nonscientific(ws, b) and _roles(ws)[b] == "working"
    out = docrole.set_roles(ws, [a, b, c], None)
    assert sorted(out["changed"]) == sorted([a, b]) and out["marked_nonscientific"] == [b]
    assert _roles(ws) == {a: None, b: None, c: None} and docrole.is_nonscientific(ws, b)
    assert not ws.scalar("SELECT COUNT(*) FROM block_choices WHERE fp LIKE 'role:%'")
    assert ws.scalar("SELECT COUNT(*) FROM block_choices WHERE fp=?", (docrole.NONSCI_KEY,)) == 1


def test_an_unknown_document_or_role_changes_nothing(project):
    ws, (a, b, c) = project
    with pytest.raises(KeyError):
        docrole.set_roles(ws, [a, "no-such-doc"], "theory")
    assert _roles(ws)[a] is None                               # all or nothing
    with pytest.raises(ValueError):
        docrole.set_roles(ws, [a], "framework")
    with pytest.raises(ValueError):
        docrole.set_roles(ws, [], "theory")


def test_the_route(api, tmp_path):  # noqa: F811
    d = tmp_path / "in"
    d.mkdir()
    for key in ("jobs", "grid"):
        (d / f"{key}.txt").write_text(TEXTS[key], encoding="utf-8")
    assert api("POST", "/api/projects", {"name": "Lens"})[0] == 200
    from margin import home as home_mod

    ws = Workspace.open(home_mod.project_path("Lens"))
    try:
        ingest.ingest(ws, [d])
        ids = sorted(r[0] for r in ws.query("SELECT doc_id FROM documents"))
    finally:
        ws.close_all()
    st, body = api("PUT", "/api/projects/Lens/document-roles", {"doc_ids": ids, "role": "working"})
    assert st == 200 and sorted(body["changed"]) == ids and body["was"] == {i: None for i in ids}
    assert body["roles"] == {i: "working" for i in ids} and body["nonscientific"] == []
    assert api("PUT", "/api/projects/Lens/document-roles", {"doc_ids": ids, "role": "framework"})[0] == 400
    assert api("PUT", "/api/projects/Lens/document-roles", {"doc_ids": [], "role": "theory"})[0] == 400
    assert api("PUT", "/api/projects/Lens/document-roles", {"doc_ids": [ids[0], "nope"], "role": None})[0] == 404
    st, body = api("PUT", "/api/projects/Lens/document-roles", {"doc_ids": ids, "role": None})
    assert st == 200 and body["roles"] == {}


def test_an_owners_marks_reach_a_colleague_and_a_members_are_proposals(anna_and_ben, tmp_path):  # noqa: F811
    from margin.sync import folder
    from owner_helpers import add_doc, proposals, sync, view

    shared = tmp_path / "shared"
    shared.mkdir()
    anna, ben = anna_and_ben
    for p in (anna, ben):
        with p:
            folder.set_folder(p.ws, str(shared))
    sync(anna, ben)
    one, two = add_doc(anna, tmp_path, "jobs"), add_doc(anna, tmp_path, "grid")
    three = add_doc(anna, tmp_path, "desalination")
    sync(anna, ben)
    with anna:
        docrole.set_roles(anna.ws, [one, two], "theory")
    view(anna)
    sync(anna, ben, rounds=2)
    with ben:
        assert docrole.role_of(ben.ws, one) == "theory" and docrole.role_of(ben.ws, two) == "theory"
    with ben:                                                  # Ben, a Member: proposals, one per document
        docrole.set_roles(ben.ws, [two, three], "working")
    props = proposals(ben, state="waiting", kind="blocks")
    assert sorted(p["doc"] for p in props) == sorted([two, three])
    assert {p["detail"]["role"] for p in props} == {"working"}


# ---- the bulk bar (views/sources.js, views/doc-role.js) ------------------------------------------------------------
PROBE = r"""
async function list(t, roles = { d2: "theory" }) {
  t.state({ settings: {} });
  const D = (id, title) => ({ doc_id: id, title, file: `${id}.pdf`, kind: "pdf", ai_access: "cloud", added_at: "2026-11-01" });
  t.answer("GET /api/projects/Study", { search: null, passages: 30 });
  t.answer(/^GET \/api\/projects\/Study\/documents(\?.*)?$/, { documents: [D("d1", "Field notes"), D("d2", "Bourdieu, Distinction"), D("d3", "My chapter draft")] });
  let now = { ...roles };
  t.answer(/^GET \/api\/projects\/Study\/document-roles/, () => ({ roles: now, nonscientific: [] }));
  t.answer("PUT /api/projects/Study/document-roles", (b) => {
    const was = {};
    for (const id of b.doc_ids) if ((now[id] || null) !== b.role) { was[id] = now[id] || null; if (b.role) now[id] = b.role; else delete now[id]; }
    return { role: b.role, changed: Object.keys(was), unchanged: b.doc_ids.filter((x) => !(x in was)), was, marked_nonscientific: [], roles: now, nonscientific: [] };
  });
  t.answer("GET /api/projects/Study/nonscientific-suggestions", { suggested: {} });
  t.answer("GET /api/projects/Study/map/documents?*", t.fail(404, "no answers yet"));
  await t.render("views/sources.js", "renderSources");
  return { get roles() { return now; } };
}
const tick = async (t, name) => t.click(t.view.querySelector(`.doc-tick[aria-label="Select ${name}"]`));
const bar = (t) => t.view.querySelector(".bulk-bar");
const roleItems = async (t) => { await t.click(bar(t).querySelector(".bulk-role summary")); return document.querySelectorAll(".bulk-role [role=menuitem]").map((x) => ({ text: t.text(x), disabled: !!x.disabled })); };

await scenario("two documents marked as working, then undone", async (t) => {
  const s = await list(t);
  const out = { closed: !!bar(t).querySelector(".bulk-role summary") };
  await tick(t, "Field notes"); await tick(t, "Bourdieu, Distinction");
  out.items = await roleItems(t);
  await t.click("Working document", { within: bar(t) });
  const d = t.dialog();
  out.asked = t.text(d.querySelector("h2"));
  out.says = t.text(d.querySelector(".dialog-body"));
  await t.click("Mark as my working documents", { within: d.querySelector(".dialog-actions") });
  out.put = t.calls.filter((c) => c.method === "PUT").map((c) => c.body);
  out.toasts = t.toasts();
  out.roles = { ...s.roles };
  out.ticked = t.view.querySelectorAll(".doc-tick").filter((c) => c.checked).length;
  out.barHidden = t.hidden(bar(t));
  await t.click("Undo", { within: document.getElementById("toasts") });
  out.undo = t.calls.filter((c) => c.method === "PUT").slice(1).map((c) => c.body);
  out.after = { ...s.roles };
  return out;
});

await scenario("the role every ticked document has is off", async (t) => {
  await list(t, { d1: "theory", d2: "theory" });
  await tick(t, "Field notes"); await tick(t, "Bourdieu, Distinction");
  return await roleItems(t);
});

await scenario("one document ticked", async (t) => {
  const s = await list(t);
  t.answer(/^PUT \/api\/projects\/Study\/documents\/d1\/role$/, (b) => { s.roles.d1 = b.role; return { doc_id: "d1", role: b.role, changed: true }; });
  await tick(t, "Field notes");
  await roleItems(t);
  await t.click("Theory", { within: bar(t) });
  await t.click("Mark as theory", { within: t.dialog().querySelector(".dialog-actions") });
  return { puts: t.calls.filter((c) => c.method === "PUT").map((c) => c.path), ticked: t.view.querySelectorAll(".doc-tick").filter((c) => c.checked).length,
    barHidden: t.hidden(bar(t)), errors: [...t.errors] };
});

await scenario("cancelled", async (t) => {
  await list(t);
  await tick(t, "Field notes"); await tick(t, "My chapter draft");
  await roleItems(t);
  await t.click("Theory", { within: bar(t) });
  await t.click("Cancel", { within: t.dialog() });
  return { puts: t.calls.filter((c) => c.method === "PUT").length, ticked: t.view.querySelectorAll(".doc-tick").filter((c) => c.checked).length };
});
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    return run_views(PROBE, tmp_path_factory.mktemp("bulkrole"))


@needs_node
def test_the_bar_marks_the_ticked_documents_and_undo_puts_each_back(page):
    r = page["two documents marked as working, then undone"]
    assert r["closed"] is False                                # no menu until a document is ticked
    assert [i["text"] for i in r["items"]] == ["Evidence", "Theory", "Working document"]
    assert not any(i["disabled"] for i in r["items"])          # one is evidence, one theory: every role is a change
    assert r["asked"] == "Mark 2 documents as your working documents?"
    assert "never a source" in r["says"] and "keeps that mark" in r["says"] and "proposals" in r["says"]
    assert r["put"] == [{"doc_ids": ["d1", "d2"], "role": "working"}]
    assert any("2 documents marked as your working documents." in x for x in r["toasts"])
    assert r["roles"] == {"d1": "working", "d2": "working"}
    assert r["ticked"] == 0 and r["barHidden"]                 # done with them
    assert sorted(json.dumps(b, sort_keys=True) for b in r["undo"]) == sorted([
        json.dumps({"doc_ids": ["d1"], "role": None}, sort_keys=True),
        json.dumps({"doc_ids": ["d2"], "role": "theory"}, sort_keys=True)])
    assert r["after"] == {"d2": "theory"}


@needs_node
def test_a_role_every_ticked_document_has_is_off(page):
    items = page["the role every ticked document has is off"]
    assert [(i["text"], i["disabled"]) for i in items] == [("Evidence", False), ("Theory", True), ("Working document", False)]


@needs_node
def test_cancel_changes_nothing_and_keeps_the_ticks(page):
    assert page["cancelled"] == {"puts": 0, "ticked": 2}


from test_shared_projects import anna_and_ben  # noqa: E402,F401  (fixture)
from test_app import api, home  # noqa: E402,F401  (fixtures)


@needs_node
def test_one_ticked_document_takes_the_single_route_and_the_list_goes_on(page):
    r = page["one document ticked"]
    assert r["puts"] == ["/api/projects/Study/documents/d1/role"]   # the one-document route, as its own page uses
    assert r["ticked"] == 0 and r["barHidden"]                 # the list was redrawn: no "true is not iterable"
    assert not r["errors"]
