"""A whole project in one zip file, to keep or to move to another computer.

    margin --ws X export-project out.zip
    margin import-project in.zip --ws Y

The zip holds:
- `enlens.sqlite`: a consistent copy of the project's database, made with SQLite's backup API (the project can be
  in use while it is copied);
- `config.json`, and the project's own codebooks (`frameworks/`);
- the original file of every document the project has: kept at its place when it is inside the project folder
  (`uploads/`, `inputs/`), and as `originals/<doc_id>/<name>` when it was read from somewhere else on the computer.
  0.14.3: nothing else of `uploads/` (the file of a document removed since stays on this computer);
- `bundle.json`: what is where (the version that made it and, per document, its file in the zip). (ENLENS also writes
  who sent it and its sync format, for a colleague's copy of the project; Margin reads neither.)

Everything is written to a temporary file on disk and copied in chunks, never held in memory. Importing unpacks
with the same guards as adding a zip of sources (no path can leave the project folder, a size budget against zip
bombs), opens the database (which adds the columns of this version) and points each document at its file in the
new folder. 0.14.3: the database is checked and opened while the project is still in its staging folder, so a zip
whose database cannot be read leaves nothing in `projects/`.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tempfile
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .store import Workspace

STORED = {".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".docx", ".xlsx", ".pptx", ".gz"}  # compressed
MAX_IMPORT = 8 * 1024 ** 3


def _add(zf: zipfile.ZipFile, path: Path, arcname: str) -> None:
    kind = zipfile.ZIP_STORED if path.suffix.lower() in STORED else zipfile.ZIP_DEFLATED
    zf.write(path, arcname, compress_type=kind)


def export_project(ws: Workspace, out: str | Path) -> dict:
    """Write the whole project to the zip file `out` (to keep, or to move it to another computer); returns what it
    holds. (ENLENS 0.18 can also write only what was shared, for a colleague: Margin has no colleagues.)"""
    from .sources import original_file

    out = Path(out)
    root = ws.root.resolve()
    tmp_dir = Path(tempfile.mkdtemp(prefix="margin-export-"))
    try:
        db = tmp_dir / "enlens.sqlite"
        src = sqlite3.connect(ws.db_path, timeout=60)
        dst = sqlite3.connect(db)
        try:
            src.backup(dst)  # a consistent copy, even while the app writes
        finally:
            dst.close()
            src.close()
        files: dict[str, str] = {}
        missing: list[str] = []
        stats = {"documents": 0, "uploads": 0, "originals": 0, "missing": missing}
        part = out.with_name(out.name + ".part")
        with zipfile.ZipFile(part, "w", allowZip64=True) as zf:
            zf.write(db, "enlens.sqlite", compress_type=zipfile.ZIP_DEFLATED)
            if ws.config_path.exists():
                zf.write(ws.config_path, "config.json")
            base = root / "frameworks"  # the project's own codebooks
            if base.is_dir():
                for f in sorted(base.rglob("*")):
                    if f.is_file() and not f.is_symlink():
                        _add(zf, f, f.relative_to(root).as_posix())
            written = {n for n in zf.namelist()}
            # 0.14.3: the file of each document the project has now, and nothing else of `uploads/`: the files of
            # documents removed since (one added by mistake), and uploads that failed or were already in the
            # project, stay on this computer
            for r in ws.query("SELECT doc_id FROM documents ORDER BY doc_id"):
                stats["documents"] += 1
                info = original_file(ws, r["doc_id"], verify=False)
                if not info["available"]:
                    missing.append(info["name"] or r["doc_id"])
                    continue
                f = Path(info["path"])
                if info["inside"]:
                    arc = f.relative_to(root).as_posix()
                else:
                    arc = f"originals/{r['doc_id']}/{f.name}"
                    stats["originals"] += 1
                if arc not in written:
                    _add(zf, f, arc)
                    written.add(arc)
                    stats["uploads"] += arc.startswith("uploads/")
                files[r["doc_id"]] = arc
            zf.writestr("bundle.json", json.dumps({"format": "margin-project", "version": __version__,
                                                   "name": ws.root.name, "files": files}, indent=1))
        part.replace(out)
        stats["size"] = out.stat().st_size
        return stats
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _project_folder(names: list[str]) -> str:
    """Where in a project zip the project is: "" when its database is at the top (a zip made with "Download as a
    zip"), or the folder that holds it ("Tovertafel/") when the project's folder itself was zipped, as Finder's
    Compress or Windows' "Send to compressed folder" do."""
    dbs = [n for n in names if not n.startswith("__MACOSX") and (n == "enlens.sqlite" or n.endswith("/enlens.sqlite"))]
    if "enlens.sqlite" in dbs:
        return ""
    if len(dbs) == 1:
        return dbs[0][:-len("enlens.sqlite")]
    if dbs:
        folders = ", ".join(sorted(d[:-len("/enlens.sqlite")] for d in dbs)[:6])
        raise ValueError(f"This zip holds {len(dbs)} projects ({folders}). Import one project at a time: zip each "
                         "project's folder on its own, or use “Download as a zip” in the app they come from.")
    raise ValueError("This zip holds no Margin project: a project has a database file, enlens.sqlite, and this zip "
                     "has none. To add the files in it to a project as documents, use Add documents instead.")


def relocate_documents(db: Path, relative, new_root: Path) -> int:
    """Point the documents of the project database `db` at their files in `new_root`. `relative(parts)` gives, for
    the parts of a recorded path, its parts inside the project folder (or None when it was not in it); a path is
    changed only when that file is there. Returns how many were changed."""
    root = Path(new_root).resolve()
    n = 0
    cx = sqlite3.connect(db)
    try:
        with cx:
            for doc_id, path in cx.execute("SELECT doc_id, path FROM documents").fetchall():
                if not path or not Path(path).is_absolute():
                    continue
                rel = relative(Path(path.replace("\\", "/")).parts)
                if not rel:
                    continue
                # the same name may be written with accents composed or not (macOS decomposes them)
                target = next((t for t in (root.joinpath(*(unicodedata.normalize(f, x) for x in rel)).resolve()
                                           for f in ("NFC", "NFD")) if t.is_file()), None)
                if target and target != Path(path) and target.is_relative_to(root):
                    cx.execute("UPDATE documents SET path=? WHERE doc_id=?", (str(target), doc_id))
                    n += 1
    finally:
        cx.close()
    return n


DAMAGED_DB = ("The project's database in this zip cannot be read: the zip is damaged, or it is not a Margin project. "
              "Ask for a new copy of the file.")


NOT_ROWS = ("The project's database in this zip holds more than a project's rows (a table that works out its own "
            "values). Margin does not open it. Ask for a new copy, made with “Download as a zip”.")


def _rows_only(cx: sqlite3.Connection) -> None:
    """A database that came from someone else is taken for its rows alone. What else a database file can hold goes:
    triggers (they would run at every change this person makes afterwards: one turned *Only a local AI* back to
    *cloud* the moment it was set, another emptied the record of what was sent to Claude) and views (one can stand in
    the place of a table). A table that works out its values itself (a generated column, a virtual table) is refused:
    a setting kept in one could not be changed here. (ENLENS's own triggers, which count changes for its shared folder,
    go too: Margin has none.) An add-on's own come back when the project is opened (`store._setup_addons`)."""
    for kind, name in cx.execute("SELECT type, name FROM sqlite_master WHERE type IN ('trigger', 'view')").fetchall():
        cx.execute(f"DROP {'TRIGGER' if kind == 'trigger' else 'VIEW'} IF EXISTS \"{name.replace(chr(34), chr(34) * 2)}\"")
    for name, sql in cx.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall():
        if name.startswith("sqlite_"):
            continue
        quoted = name.replace(chr(34), chr(34) * 2)
        if (sql or "").lstrip().upper().startswith("CREATE VIRTUAL") or any(
                r[6] in (2, 3) for r in cx.execute(f"PRAGMA table_xinfo(\"{quoted}\")")):
            raise ValueError(NOT_ROWS)
    cx.commit()


def _open_staged(folder: Path) -> bool:
    """0.14.3: check the database unpacked into the staging folder and open it there (which adds the tables and
    columns of this version), before the project is put in place. Raises ValueError with a plain message when it
    cannot be read. Returns whether it was made before 0.11 (per-document AI settings)."""
    try:
        cx = sqlite3.connect(folder / "enlens.sqlite")
        try:
            ok = cx.execute("PRAGMA quick_check").fetchone()
            if ok and ok[0] == "ok":
                _rows_only(cx)
            before_011 = "ai_access" not in {r[1] for r in cx.execute("PRAGMA table_info(documents)")}
        finally:
            cx.close()
        if not ok or ok[0] != "ok":
            raise ValueError(DAMAGED_DB)
        ws = Workspace.open(folder)
        ws.close()  # no connection stays open on the folder that is about to move
    except sqlite3.DatabaseError as e:
        raise ValueError(DAMAGED_DB) from e
    return before_011


# config.json: what Margin reads of a project's settings, and what each may hold. A project from a zip keeps only these,
# each of its kind and in a sensible range, else Margin's own (`store.DEFAULT_CONFIG`): the file comes from someone
# else's computer, and a value of the wrong kind stopped every page of results (a `thresholds` that is not a dict)
_NUMBERS = {"thresholds": {"screen_min_score": (0.0, 100.0), "accept_confidence": (0.0, 1.0),
                           "support_confidence": (0.0, 1.0), "verify_top_k": (1, 200)},
            "passages": {"max_chars": (100, 100000), "min_chars": (0, 100000)}}
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,119}")  # a model's name, as Settings and the routes write it


def _clean_config(raw: Any) -> dict:
    """A project's config.json as a zip brought it, with only what Margin knows (see `_NUMBERS`)."""
    from .access import LEVELS
    from .store import DEFAULT_CONFIG

    cfg = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}
    for part, ranges in _NUMBERS.items():
        given = cfg.get(part) if isinstance(cfg.get(part), dict) else {}
        out[part] = {}
        for k, (lo, hi) in ranges.items():
            v = given.get(k)
            ok = isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi and \
                (isinstance(v, int) or not isinstance(lo, int))
            out[part][k] = v if ok else DEFAULT_CONFIG[part][k]
    if out["passages"]["min_chars"] > out["passages"]["max_chars"]:
        out["passages"] = dict(DEFAULT_CONFIG["passages"])
    models = cfg.get("models") if isinstance(cfg.get("models"), dict) else {}
    out["models"] = {k: (v if isinstance(v, str) and _MODEL.fullmatch(v) else d)
                     for k, d in DEFAULT_CONFIG["models"].items() for v in [models.get(k)]}
    if cfg.get("ai_access_default") in LEVELS:
        out["ai_access_default"] = cfg["ai_access_default"]
    for k in ("ai_access_ask", "ai_access_banner"):
        if isinstance(cfg.get(k), bool):
            out[k] = cfg[k]
    return out


# what a project zip may hold that is not unpacked: made again here (the search index, the cache of the terms), or the
# sender's own (the copy of their database made before they brought work in)
_NOT_UNPACKED = ("cache/", "backups/")


class _Without:
    """A zip as `ingest._safe_extract` reads it, without what is not unpacked (`_NOT_UNPACKED`)."""

    def __init__(self, zf: zipfile.ZipFile, prefix: str):
        self.zf, self.prefix = zf, prefix

    def infolist(self) -> list[zipfile.ZipInfo]:
        from .ingest import zip_name

        skip = tuple(self.prefix + n for n in _NOT_UNPACKED)
        return [i for i in self.zf.infolist() if not zip_name(i).startswith(skip)]

    def open(self, *a, **k):
        return self.zf.open(*a, **k)


def import_project(zip_path: str | Path, dest: str | Path) -> Workspace:
    """Unpack a project zip into the folder `dest` (which must not exist yet, or be empty) and open it. The zip is one
    made with export_project (by Margin or by ENLENS: the tables of ENLENS's shared projects stay in the file,
    unread), or a project folder zipped by hand (0.13.5)."""
    from .ingest import ZIP_ERRORS, _safe_extract, zip_name, zip_problem

    zip_path, dest = Path(zip_path), Path(dest)
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("This is not a zip file.")
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"The folder {dest} is not empty: choose another name.")
    with zipfile.ZipFile(zip_path) as zf:
        prefix = _project_folder([zip_name(i) for i in zf.infolist()])
        total = sum(i.file_size for i in zf.infolist())
        if total > MAX_IMPORT:
            raise ValueError(f"The project in this zip is larger than {MAX_IMPORT // 1024 ** 3} GB unpacked.")
        staging = dest.with_name(dest.name + ".importing")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        try:
            try:
                _safe_extract(_Without(zf, prefix), staging, [MAX_IMPORT], strip=prefix)
            except ZIP_ERRORS as e:  # 0.14.3: a damaged or password-protected zip, in words
                raise ValueError(f"This project zip could not be unpacked ({zip_problem(e)}). Ask for a new copy of "
                                 "the file.") from e
            if not (staging / "enlens.sqlite").is_file():
                raise ValueError("The project's database could not be unpacked.")
            try:
                meta = json.loads((staging / "bundle.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            before_011 = _open_staged(staging)
            if dest.exists():
                dest.rmdir()
            staging.replace(dest)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    ws = Workspace.open(dest)  # opened in staging already: the tables and columns of this version are there
    try:
        sent = json.loads(ws.config_path.read_text(encoding="utf-8")) if ws.config_path.exists() else {}
    except (OSError, ValueError):
        sent = {}
    ws.config_path.write_text(json.dumps(_clean_config(sent), indent=2), encoding="utf-8")
    ws._config_cache = None
    if before_011:
        # 0.11: a project made before per-document AI settings: the app asks once who may read its documents
        cfg = json.loads(ws.config_path.read_text(encoding="utf-8")) if ws.config_path.exists() else {}
        cfg.pop("ai_access_default", None)
        cfg.pop("ai_access_banner", None)
        cfg["ai_access_ask"] = True
        ws.config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    root = dest.resolve()
    files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
    with ws.connect() as cx:
        for doc_id, path in cx.execute("SELECT doc_id, path FROM documents").fetchall():
            arc = files.get(doc_id)
            if not arc:
                continue
            target = (root / arc).resolve()
            if target.is_relative_to(root) and target.is_file():
                cx.execute("UPDATE documents SET path=? WHERE doc_id=?", (str(target), doc_id))
    if prefix and not files:
        # a project folder zipped by hand: its documents still point into the folder it was zipped from
        name = prefix.rstrip("/").rsplit("/", 1)[-1]
        relocate_documents(dest / "enlens.sqlite", lambda parts: parts[len(parts) - parts[::-1].index(name):]
                           if name in parts[:-1] else None, root)
    for sub in ("tasks", "results", "exports", "report"):
        (dest / sub).mkdir(exist_ok=True)
    (dest / "bundle.json").unlink(missing_ok=True)
    return ws


# ---------------------------------------------------------------------------------------------
# 0.10: Move Margin to another computer: every project and the settings in one zip
# ---------------------------------------------------------------------------------------------
MOVE_MANIFEST = "enlens-move.json"
# settings that belong to this computer rather than to the person: not carried over
MACHINE_SETTINGS = {"project", "benchmark_reference", "claude_plan_detected",  # 0.13.10: found per computer
                    # stage 1 of other cloud providers: like the Claude API key (never in a move zip), the chosen
                    # provider and what goes with it stay here; its key is in this computer's keychain only
                    "cloud_provider", "cloud_model", "cloud_small_model", "azure_url"}
# ENLENS roles: who the person is (ENLENS's settings; a move zip made by ENLENS may hold them). Margin has one person,
# so they are never taken
PERSON_SETTINGS = ("person_id", "your_name")
# ENLENS roles (§4.11): the settings that hold a server's address; one that is not on this computer is taken only when
# the person ticks it (a back end left without its address keeps this computer's own)
SERVER_SETTINGS = ("ollama_url", "openai_url", "embed_url")
_SERVER_OF = {"ollama": "ollama_url", "openai": "openai_url"}  # a server kind and the setting of its address
NOT_A_MOVE = "This zip was not made with “Move Margin to another computer”."


def is_move_zip(zip_path: str | Path) -> bool:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return MOVE_MANIFEST in zf.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


def export_all(out: str | Path, progress=None) -> dict:
    """Write every project (each as its own project zip, see export_project) and the settings to the zip `out`. Quick
    looks that were not kept are left out, and so is any saved Claude API key: it never leaves this computer."""
    from . import home

    out = Path(out)
    names = [n for n in home.list_projects() if not home.is_temporary(n)]
    tmp_dir = Path(tempfile.mkdtemp(prefix="enlens-move-"))
    listed, skipped = [], []
    try:
        part = out.with_name(out.name + ".part")
        with zipfile.ZipFile(part, "w", allowZip64=True) as zf:
            for i, name in enumerate(names):
                if progress:
                    progress(i, len(names), name)
                try:
                    ws = home.open_project(name)
                except Exception as e:  # noqa: BLE001 - a project that cannot be opened is reported, not fatal
                    skipped.append({"name": name, "error": str(e)})
                    continue
                arc = f"projects/{i + 1:03d}.zip"
                one = tmp_dir / f"{i + 1:03d}.zip"
                stats = export_project(ws, one)
                zf.write(one, arc, compress_type=zipfile.ZIP_STORED)  # already compressed
                one.unlink()
                listed.append({"name": name, "file": arc, "documents": stats["documents"],
                               "linked": home.is_linked(name), "missing": stats["missing"]})
            settings = _movable(home.load_settings())
            current = home.load_settings().get("project") or ""
            zf.writestr(MOVE_MANIFEST, json.dumps({"format": "enlens-move", "version": __version__,
                                                   "made": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                   "projects": listed, "current": current,
                                                   "settings": settings}, indent=1))
        part.replace(out)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return {"projects": listed, "skipped": skipped, "size": out.stat().st_size}


def _movable(settings: dict) -> dict:
    """The settings a move zip carries: not this computer's own, and not another cloud provider as the main route
    (its key and choice stay on this computer, as the Claude API key does: the other computer keeps its own route)."""
    out = {k: v for k, v in settings.items() if k not in MACHINE_SETTINGS}
    if out.get("backend") == "cloud_api":
        out.pop("backend", None)
    return out


def _move_meta(zf: zipfile.ZipFile) -> dict:
    try:
        meta = json.loads(zf.read(MOVE_MANIFEST))
    except (KeyError, ValueError) as e:
        raise ValueError(NOT_A_MOVE) from e
    if not isinstance(meta, dict) or meta.get("format") != "enlens-move":
        raise ValueError(NOT_A_MOVE)
    if not isinstance(meta.get("settings"), dict):
        meta["settings"] = {}
    return meta


def _fresh() -> bool:
    """Whether this computer has no project yet (a quick look that was not kept does not count)."""
    from . import home

    return not [n for n in home.list_projects() if not home.is_temporary(n)]


def peek_move(zip_path: str | Path) -> dict:
    """What a move zip holds, shown before anything is brought in (ENLENS roles §5.5): {"made", "version", "projects":
    [{"name", "documents"}], "settings": {key: value}, "servers": [{"key", "url", "here"}], "fresh"} ("settings": what
    *Take the settings too* would take, but the servers' addresses, listed in "servers"; "here": the address is this
    computer, so it is taken with the settings without asking; "fresh": this computer has no project yet, so the
    settings are taken by default). Margin: you always move, the same person (ENLENS also asks "moving" or "both
    computers")."""
    from . import home
    from .access import on_this_computer

    with zipfile.ZipFile(zip_path) as zf:
        meta = _move_meta(zf)
    sent = meta["settings"]
    projects = [{"name": str(p.get("name") or ""), "documents": p.get("documents") if isinstance(p.get("documents"), int)
                 else None} for p in meta.get("projects") or [] if isinstance(p, dict)]
    shown = {k: v for k, v in sent.items() if k in home.DEFAULTS and k not in MACHINE_SETTINGS
             and k not in PERSON_SETTINGS and k not in SERVER_SETTINGS}
    servers = [{"key": k, "url": str(sent[k]), "here": on_this_computer(str(sent[k]))}
               for k in SERVER_SETTINGS if isinstance(sent.get(k), str) and sent[k].strip()]
    return {"made": meta.get("made"), "version": meta.get("version"), "projects": projects,
            "settings": shown, "servers": servers, "fresh": _fresh()}


def _settings_to_take(sent: dict, servers: Iterable[str]) -> dict:
    """The other computer's settings this one takes (*Take the settings too*): never this computer's own (the
    installation, the current project), nor ENLENS's who the person is, nor an address that is not
    on this computer unless its key is in `servers`. A back end, a search server or the local AI for restricted
    documents whose address was not taken keeps this computer's own setting."""
    from . import home
    from .access import on_this_computer

    allowed = set(servers or ())
    wanted = {k: v for k, v in _movable(sent).items() if k in home.DEFAULTS and k not in PERSON_SETTINGS}
    dropped = {k for k in SERVER_SETTINGS if isinstance(wanted.get(k), str) and wanted[k].strip()
               and not on_this_computer(wanted[k]) and k not in allowed}
    for k in dropped:
        wanted.pop(k, None)
    if _SERVER_OF.get(str(wanted.get("backend"))) in dropped:
        for k in ("backend", "ollama_model", "openai_model"):
            wanted.pop(k, None)
    embed_url = sent.get("embed_url") if isinstance(sent.get("embed_url"), str) else ""
    if "embed_url" in dropped or (not embed_url.strip() and _SERVER_OF.get(str(wanted.get("embed_backend"))) in dropped):
        for k in ("embed_backend", "embed_url", "embed_model"):
            wanted.pop(k, None)
    if _SERVER_OF.get(str(wanted.get("restricted_server"))) in dropped:
        for k in ("restricted_server", "restricted_model"):
            wanted.pop(k, None)
    return wanted


def _take_settings(wanted: dict) -> bool:
    from . import home

    try:
        home.update_settings(wanted)
    except ValueError:
        # e.g. the old computer used Claude Code and this one keeps everything on it (local only)
        wanted = {k: v for k, v in wanted.items() if k not in ("backend", "allow_cloud", "allow_claude_code")}
        try:
            home.update_settings(wanted)
        except ValueError:
            wanted = {}
    return bool(wanted)


def import_all(zip_path: str | Path, settings: bool | None = None, servers: Iterable[str] = ()) -> dict:
    """Bring in a zip made by export_all: every project as a new project (a name in use gets " (2)"). Margin: you move
    to this computer and stay the same person (ENLENS also offers "I will use both computers", a second person).
    `settings`: take the other settings too (`_settings_to_take`; `servers`: the addresses not on this computer to
    take as well); None: only when this computer has no project yet (a new computer takes the old one's settings, one
    in use keeps its own). Returns {"projects": [{"from", "name", "documents"}], "settings": bool, "current", "made",
    "version"}."""
    from . import home

    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        meta = _move_meta(zf)
        sent = meta["settings"]
        fresh = _fresh()
        take = fresh if settings is None else bool(settings)
        done, renamed = [], {}
        tmp_dir = Path(tempfile.mkdtemp(prefix="enlens-move-in-"))
        try:
            for p in meta.get("projects") or []:
                if not isinstance(p, dict):
                    continue
                arc = str(p.get("file") or "")
                if not arc.startswith("projects/") or ".." in arc or arc not in zf.namelist():
                    continue
                one = tmp_dir / "one.zip"
                with zf.open(arc) as src, open(one, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                pname = home.unique_project_name(str(p.get("name") or "Imported project"))
                ws = import_project(one, home.home() / "projects" / pname)
                one.unlink()
                n_docs = ws.scalar("SELECT COUNT(*) FROM documents") or 0
                done.append({"from": p.get("name"), "name": pname, "documents": n_docs})
                renamed[p.get("name")] = pname
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    applied = _take_settings(_settings_to_take(sent, servers)) if take else False
    current = renamed.get(meta.get("current")) or (done[0]["name"] if done else None)
    if current and (fresh or not home.load_settings().get("project")):
        home.update_settings({"project": current})   # a computer in use stays on the project it was on
    else:
        current = home.load_settings().get("project") or current
    return {"projects": done, "settings": applied, "current": current, "made": meta.get("made"),
            "version": meta.get("version")}


# ---------------------------------------------------------------------------------------------
# ENLENS roles (§4.11): a folder linked as a project is cleaned as an import is. (ENLENS also asks first about a folder
# another person made; Margin has one person: every folder is yours.)
# ---------------------------------------------------------------------------------------------
def _linked_config(root: Path) -> tuple[dict | None, list[str]]:
    """config.json of a folder to link, as it is kept: `_clean_config`. (None, []) when it needs no change; else (the
    new config, the keys that change: dropped or given another value)."""
    f = root / "config.json"
    try:
        raw = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except (OSError, ValueError):
        raw = "unreadable"
    if raw is None:
        return None, []
    new = _clean_config(raw)
    old = raw if isinstance(raw, dict) else {}
    changed = sorted(k for k in old if old.get(k) != new.get(k)) if isinstance(raw, dict) else ["config.json"]
    return (new if new != old else None), changed


def _sqlite(root: Path) -> sqlite3.Connection:
    db = root / "enlens.sqlite"
    if not db.is_file():
        raise ValueError(f"No workspace (enlens.sqlite) in {root}.")
    return sqlite3.connect(db, timeout=60)


def check_linked(path: str | Path) -> dict:
    """What linking an existing folder as a project would clean, without changing anything: {"triggers": n, "views":
    n, "config": [keys changed]}."""
    root = Path(path).expanduser().resolve()
    cx = _sqlite(root)
    try:
        try:
            kinds = cx.execute("SELECT type, name FROM sqlite_master WHERE type IN ('trigger', 'view')").fetchall()
        except sqlite3.DatabaseError as e:
            raise ValueError(DAMAGED_DB.replace("in this zip", "in this folder")) from e
    finally:
        cx.close()
    _new, changed = _linked_config(root)
    return {"triggers": sum(1 for k, _n in kinds if k == "trigger"), "views": sum(1 for k, _n in kinds if k == "view"),
            "config": changed}


def clean_linked(path: str | Path) -> dict:
    """Clean a folder before it is linked as a project, as a project from a zip is (`import_project`): the quick
    check, its rows alone (`_rows_only`: triggers and views go, a table that works out its own values is refused)
    and its config.json (`_clean_config`; the old file kept as config.json.before-linking). Returns what
    `check_linked` found."""
    root = Path(path).expanduser().resolve()
    report = check_linked(root)
    cx = _sqlite(root)
    try:
        ok = cx.execute("PRAGMA quick_check").fetchone()
        if not ok or ok[0] != "ok":
            raise ValueError(DAMAGED_DB.replace("in this zip", "in this folder"))
        _rows_only(cx)  # before Margin opens it: a trigger would run at the first change opening it makes
    except sqlite3.DatabaseError as e:
        raise ValueError(DAMAGED_DB.replace("in this zip", "in this folder")) from e
    finally:
        cx.close()
    new, _changed = _linked_config(root)
    if new is not None:
        f = root / "config.json"
        if f.exists():
            shutil.copyfile(f, root / "config.json.before-linking")
        f.write_text(json.dumps(new, indent=2), encoding="utf-8")
    return report
