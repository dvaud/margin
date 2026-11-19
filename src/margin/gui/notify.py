"""Notifications from the computer itself (after 0.19.7): work that took a while tells the person it has finished, so the
browser can be closed while a local model works (a closed browser leaves the model more memory).

When a job the person started ends (done, or stopped by a problem; not when it was stopped: by the person, or by Quit
and updates), and it ran for at least `MIN_SECONDS` (its time waiting for its turn not counted), `job_ended` sends one
notification, as Settings' `notify` says: `away` (the default) only when no tab of
the app is in front of the person (no request from a visible tab with the focus, `App.seen`, in the last `SEEN_WINDOW`
seconds), `always`, or `off`. Work the app started by itself (a round of the shared folder) never notifies, but for
the local model that takes over the queue at the plan's usage limit (`ANYWAY`): it carries on the person's own work.

How each system shows it (`send`):
  macOS    a small app of its own, `<name>.app` in ~/Library/Application Support/<name>/Notifier, made once with the
           system's own tools (osacompile, codesign): macOS shows a notification under the name of the app that sends
           it, and opens that app when the notification is clicked, so the plain `osascript` notification shows as
           "Script Editor" and a click opens Script Editor. This app shows the notes left in its `pending` folder. Each
           time Margin opens it, Margin leaves a mark there; opened without one, it was opened by a click on a
           notification, and it runs `open.sh`, which opens the app in the browser as its icon does (margin-gui
           --launcher). See NOTES_SH. The first notification asks whether it may send them (and again if the app is
           ever made anew: hence the app holds only a few lines, see MAC_SCRIPT). A note a minute old or more is
           dropped unseen, so a note left behind never takes a click's place.
           Without the tools: the plain osascript one.
  Windows  a toast through Windows PowerShell, under the app's own name and icon (its id registered for this account in
           HKCU\\Software\\Classes\\AppUserModelId, as unpackaged apps do; PowerShell's own id when that one is not
           known). A click opens `<name>-open:`, a link kind registered for this account whose command is the icon's
           (so an old toast still opens the app after a restart, and no toast carries the token); without it, the
           app's link. Notifications switched off for the app in Windows are respected (nothing is sent, and the test
           says so). When no toast can be made: a balloon from the notification area.
  Linux    notify-send, else gdbus (the desktop's notification service, org.freedesktop.Notifications).

MARGIN_NO_NOTIFY=1 switches it off for the whole process (tests, tools/dev_server.py): nothing reaches the screen.
"""
from __future__ import annotations

import base64
import hashlib
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from collections.abc import Callable
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from ..procs import no_window

MIN_SECONDS = 20     # work shorter than this ends while the person still looks: no notification
SEEN_WINDOW = 20     # seconds: a tab in front asks for the work's state every 2 to 5 s while work runs
CHOICES = ("away", "always", "off")
ANYWAY = {"queue-local-limit"}   # started by the app, but the person's own work: the local model at the usage limit
NOTE_LIMIT = 220     # characters of a notification's text (the systems cut longer ones anyway)

Runner = Callable[..., Any]


def disabled() -> bool:
    return os.environ.get("MARGIN_NO_NOTIFY", "").strip().lower() in ("1", "true", "yes", "on")


def _short(text: str, limit: int = NOTE_LIMIT) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _duration(seconds: float) -> str:
    s = round(seconds)
    if s < 90:
        return f"{s} s"
    m = s // 60
    return f"{m} min" if m < 90 else f"{m // 60} h {m % 60:02d} min"


def note_for(job, project_label: str | None = None) -> tuple[str, str]:
    """The title and text of the notification for an ended job."""
    took = _duration((job.finished or time.time()) - (job.started or job.created))
    where = f" · {project_label or job.project}" if job.project else ""
    if job.state == "error":
        return "Stopped with a problem", _short(f"{job.title}: {job.error or 'see the app'}{where}")
    return "Finished", _short(f"{job.title} (took {took}){where}")


def wanted(job, choice: str, seen: float, now: float | None = None) -> bool:
    """Whether the ended `job` gets a notification, with Settings' `choice` and the last time a tab was in front."""
    now = time.time() if now is None else now
    if choice not in ("away", "always") or job.state not in ("done", "error"):
        return False
    if job.background and job.kind not in ANYWAY:
        return False
    cancel = getattr(job, "cancel", None)
    if cancel is not None and cancel.is_set():   # stopped (it may still end "done" with what it had made)
        return False
    if job.started is None or (job.finished or now) - job.started < MIN_SECONDS:
        return False
    return choice == "always" or now - seen > SEEN_WINDOW


def job_ended(app, job, send: Callable[..., dict] | None = None) -> bool:
    """The jobs' listener (server.App): a notification for `job` when Settings and the tabs say so. It is sent from a
    thread of its own, so a slow system never holds the job's thread. True when one is on its way."""
    if disabled():
        return False
    try:
        choice = app.settings().get("notify") or "away"
    except Exception:  # noqa: BLE001 - unreadable settings: the default
        choice = "away"
    if not wanted(job, choice, getattr(app, "seen", 0.0)):
        return False
    title, text = note_for(job)
    sender = send or send_note
    url = _app_link(app)

    def go():
        try:
            sender(title, text, url=url)
        except Exception:  # noqa: BLE001 - a notification never stops the app
            traceback.print_exc()

    threading.Thread(target=go, daemon=True, name=f"notify-{job.id}").start()
    return True


def _app_link(app) -> str:
    """The app's link with its token (what a click on a Windows toast opens when `<name>-open:` is not there)."""
    try:
        from .launcher import link

        host = "127.0.0.1" if app.host in ("0.0.0.0", "::", "") else app.host
        return link(f"http://{host}:{app.port}/", app.token) if app.port else ""
    except Exception:  # noqa: BLE001
        return ""


def app_name() -> str:
    try:
        from .. import addons

        return str(addons.brand().get("name") or "Margin")
    except Exception:  # noqa: BLE001
        return "Margin"


def _slug(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum()) or "margin"


# ---------------------------------------------------------------------------------------------
# sending
# ---------------------------------------------------------------------------------------------
def send_note(title: str, text: str, url: str = "", platform: str | None = None, run: Runner = subprocess.run,
              folder: Path | None = None) -> dict:
    """Show one notification on this computer. → {"sent": bool, "how": what showed it, "problem": why not}.
    `platform`, `run` and `folder` (where the macOS notifier lives) are for tests."""
    platform = platform or sys.platform
    name = app_name()
    try:
        if platform == "darwin":
            return _mac(name, title, text, run, folder)
        if platform.startswith("win"):
            return _windows(name, title, text, url, run)
        return _linux(name, title, text, run)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return {"sent": False, "how": "", "problem": str(e)}


SEND_LOCK = threading.Lock()   # one notifier made (macOS) or note sent at a time


# -- macOS -------------------------------------------------------------------------------------
# The notifier's script, kept as small as it can be: macOS ties the permission to send notifications to the app's
# signature, made on this computer, so an app made again asks again. Everything that may change lives beside it, in
# `notes.sh` and `open.sh`, which Margin writes again whenever they differ. Nothing of a path is written into the app,
# so a folder with any letters in its name works. Each time it is opened (`event`) it asks notes.sh what to show; after
# showing some it looks again a second later, so a note written meanwhile is shown before it quits.
MAC_SCRIPT = r'''-- Shows the notifications of the app beside it (notes.sh decides what, and what a click does).
on run
	tellPerson()
end run

on reopen
	tellPerson()
end reopen

on tellPerson()
	local here, t, ps
	try
		set here to do shell script "cd " & quoted form of (POSIX path of (path to me)) & "/.. && pwd -P"
		set t to do shell script "/bin/sh " & quoted form of (here & "/notes.sh") & " event"
		repeat 30 times
			if t is "" then exit repeat
			set ps to paragraphs of t
			repeat with i from 1 to ((count of ps) - 1) by 2
				display notification (item (i + 1) of ps) with title (item i of ps)
			end repeat
			delay 1
			set t to do shell script "/bin/sh " & quoted form of (here & "/notes.sh")
		end repeat
	end try
end tellPerson
'''
# Each time Margin opens the notifier it leaves a `.wake` mark beside the note, and the notifier's `event` takes one:
# opened with none, it was opened by a click on a notification (macOS opens the app that sent it), so it opens the app
# (open.sh). Two notes close together are shown in one go, and the second opening then finds its mark and nothing to
# show: it never opens the app by itself. Notes and marks a minute old or more are removed unseen.
NOTES_SH = r'''#!/bin/sh
# What the notifier shows (made by Margin, gui/notify.py): the notes waiting in pending/, title and text a line each,
# then removed. "event": the notifier was opened; by Margin when a .wake mark waits (one is taken), else by a click on
# a notification, which opens Margin (open.sh). Notes and marks a minute old or more are removed unseen.
here=$(cd "$(dirname "$0")" && pwd -P) || exit 0
mkdir -p "$here/pending" && cd "$here/pending" || exit 0
find . \( -name '*.note' -o -name '*.wake' \) -mmin +1 -delete 2>/dev/null
if [ "$1" = "event" ]; then
  for w in *.wake; do
    if [ -f "$w" ]; then rm -f "$w"; woke=1; break; fi
  done
  if [ -z "$woke" ]; then
    /bin/sh "$here/open.sh" >/dev/null 2>&1 &
    exit 0
  fi
fi
for f in *.note; do
  [ -f "$f" ] || continue
  cat "$f"
  rm -f "$f"
done
'''
MAC_STAMP = hashlib.sha256(MAC_SCRIPT.encode("utf-8")).hexdigest()[:12]
LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/"
              "lsregister")


def mac_folder(name: str | None = None) -> Path:
    """Where the notifier lives: one for this account, outside the data folder (a data folder can be anywhere, or
    several), so macOS knows one app of that name."""
    name = name or app_name()
    return Path.home() / "Library" / "Application Support" / name / "Notifier"


def mac_notifier(name: str, folder: Path, run: Runner = subprocess.run, register: bool = True) -> Path:
    """The notifier app `<folder>/<name>.app`, made when missing or made by an older script (its CFBundleVersion).
    `register`: tell Launch Services about it at once (tests that make one in a temporary folder do not)."""
    app = folder / f"{name}.app"
    info = app / "Contents" / "Info.plist"
    try:
        with open(info, "rb") as f:
            if plistlib.load(f).get("CFBundleVersion") == MAC_STAMP:
                return app
    except (OSError, plistlib.InvalidFileException, ValueError):
        pass
    for tool in ("osacompile", "codesign"):
        if not shutil.which(tool):
            raise OSError(f"{tool} is not on this Mac.")
    folder.mkdir(parents=True, exist_ok=True)
    src = folder / "notifier.applescript"
    src.write_text(MAC_SCRIPT, encoding="utf-8")
    part = folder / f"{name}-new.app"
    shutil.rmtree(part, ignore_errors=True)
    r = run(["osacompile", "-o", str(part), str(src)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise OSError(f"osacompile: {(r.stderr or '').strip()[:300]}")
    pinfo = part / "Contents" / "Info.plist"
    with open(pinfo, "rb") as f:
        plist = plistlib.load(f)
    plist.update({"CFBundleIdentifier": f"org.margin.notifier.{_slug(name)}", "CFBundleName": name,
                  "CFBundleDisplayName": name, "CFBundleVersion": MAC_STAMP, "CFBundleShortVersionString": "1",
                  "LSUIElement": True})  # no Dock icon, no menu bar of its own
    from .launcher import _put_icon

    if _put_icon(part / "Contents" / "Resources" / "Margin.icns", "icns"):
        plist.pop("CFBundleIconName", None)   # the script icon of the asset catalogue would win over the file
        plist["CFBundleIconFile"] = "Margin"
    with open(pinfo, "wb") as f:
        plistlib.dump(plist, f)
    # the Info.plist changed after osacompile signed it: signed again for this computer (Apple silicon runs nothing
    # unsigned, and macOS ties the notification permission to the app's signature)
    r = run(["codesign", "--force", "--sign", "-", str(part)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise OSError(f"codesign: {(r.stderr or '').strip()[:300]}")
    shutil.rmtree(app, ignore_errors=True)
    part.rename(app)
    src.unlink(missing_ok=True)
    if register and os.path.exists(LSREGISTER):
        run([LSREGISTER, "-f", str(app)], capture_output=True, text=True, timeout=60)
    return app


def _open_command() -> list[str]:
    """What a click on a notification runs: the app's icon command (opens the running app, or starts it)."""
    from .. import home

    cmd = [sys.executable, "-m", "margin.gui.launch", "--launcher", "--home", str(home.home().resolve())]
    if home.local_only():
        cmd.append("--local-only")
    return cmd


def _write_if_changed(path: Path, text: str) -> None:
    try:
        if path.read_text(encoding="utf-8") == text:
            return
    except OSError:
        pass
    path.write_text(text, encoding="utf-8")


def _mac(name: str, title: str, text: str, run: Runner, folder: Path | None) -> dict:
    folder = folder or mac_folder(name)
    title, text = _short(title, 120), _short(text)
    with SEND_LOCK:
        try:
            app = mac_notifier(name, folder, run)
        except (OSError, subprocess.SubprocessError, ValueError, plistlib.InvalidFileException) as e:
            return _osascript(name, title, text, run, problem=str(e))
        _write_if_changed(folder / "open.sh", "#!/bin/sh\n# Opens the app (a notification was clicked).\nexec "
                          + " ".join(shlex.quote(x) for x in _open_command()) + "\n")
        _write_if_changed(folder / "notes.sh", NOTES_SH)
        pending = folder / "pending"
        pending.mkdir(exist_ok=True)
        stem = f"{time.time_ns()}-{os.getpid()}"
        part = pending / f"{stem}.part"
        part.write_text(f"{title}\n{text or title}\n", encoding="utf-8")   # two lines, always (_short: one each)
        part.replace(pending / f"{stem}.note")   # whole, or not there: the notifier never reads half a note
        (pending / f"{stem}.wake").touch()       # this opening is Margin's, not a click (NOTES_SH)
        try:
            r = run(["open", "-g", str(app)], capture_output=True, text=True, timeout=30)
            problem = "" if r.returncode == 0 else f"open: {(r.stderr or '').strip()[:300]}"
        except (OSError, subprocess.SubprocessError) as e:
            problem = f"open: {e}"
        if problem:   # never left behind for a later click to find
            (pending / f"{stem}.note").unlink(missing_ok=True)
            (pending / f"{stem}.wake").unlink(missing_ok=True)
            return _osascript(name, title, text, run, problem=problem)
    return {"sent": True, "how": "app", "problem": ""}


def _as_text(s: str) -> str:
    """An AppleScript string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _osascript(name: str, title: str, text: str, run: Runner, problem: str = "") -> dict:
    """The plain notification (shown as Script Editor's): when the notifier cannot be made."""
    if not shutil.which("osascript"):
        return {"sent": False, "how": "", "problem": problem or "osascript is not on this Mac."}
    script = f"display notification {_as_text(text)} with title {_as_text(name)} subtitle {_as_text(title)}"
    r = run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    ok = r.returncode == 0
    return {"sent": ok, "how": "osascript" if ok else "", "problem": problem if ok else
            (problem + "; " if problem else "") + f"osascript: {(r.stderr or '').strip()[:300]}"}


# -- Windows -----------------------------------------------------------------------------------
# Windows PowerShell 5.1 (on every Windows 10 and 11; PowerShell 7 cannot load these Windows types). What it shows
# comes in environment variables, so no text is ever part of the script. MARGIN_NOTE_DRY=1: everything but showing
# it and writing the registry (tests on Windows).
WIN_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$dry = $env:MARGIN_NOTE_DRY -eq '1'
$ps = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
$id = $env:MARGIN_NOTE_ID
if ($dry) { $id = $ps } else {
  try {
    $key = "HKCU:\Software\Classes\AppUserModelId\$id"
    if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
    New-ItemProperty -Path $key -Name DisplayName -Value $env:MARGIN_NOTE_NAME -PropertyType String -Force | Out-Null
    if ($env:MARGIN_NOTE_ICON) {
      New-ItemProperty -Path $key -Name IconUri -Value $env:MARGIN_NOTE_ICON -PropertyType String -Force | Out-Null
    }
  } catch { [Console]::Error.WriteLine('registry: ' + $_); $id = $ps }
}
try {
  [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
  [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
  $x = New-Object Windows.Data.Xml.Dom.XmlDocument
  $x.LoadXml($env:MARGIN_NOTE_XML)
  $t = New-Object Windows.UI.Notifications.ToastNotification $x
  try {
    $n = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id)
    $s = [string]$n.Setting
  } catch {
    [Console]::Error.WriteLine('notifier ' + $id + ': ' + $_)
    $id = $ps
    $n = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id)
    $s = [string]$n.Setting
  }
  if ($dry) { Write-Output ('toast-ready ' + $s); exit 0 }
  # only a clear "switched off" stops it: Windows PowerShell may read the setting as nothing at all (seen on a
  # Windows PC: blank, with notifications on)
  if ($s -like 'Disabled*') { Write-Output ('off ' + $s); exit 0 }
  $n.Show($t)
  Write-Output ('toast ' + $id + ' ' + $s)
} catch {
  [Console]::Error.WriteLine('toast: ' + $_)
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
  if ($dry) { Write-Output 'balloon-ready'; exit 0 }
  $b = New-Object System.Windows.Forms.NotifyIcon
  $b.Icon = [System.Drawing.SystemIcons]::Information
  $b.Text = $env:MARGIN_NOTE_NAME
  $b.Visible = $true
  $b.ShowBalloonTip(10000, $env:MARGIN_NOTE_TITLE, $env:MARGIN_NOTE_TEXT, [System.Windows.Forms.ToolTipIcon]::Info)
  Start-Sleep -Seconds 8
  $b.Dispose()
  Write-Output 'balloon'
}
'''


def toast_xml(title: str, text: str, url: str = "") -> str:
    """The toast: its title and text; a click opens `url` (the app's link) in the browser."""
    launch = f' activationType="protocol" launch={quoteattr(url)}' if url else ""
    return (f'<toast{launch}><visual><binding template="ToastGeneric"><text>{escape(title)}</text>'
            f'<text>{escape(text)}</text></binding></visual></toast>')


def win_command(script: str = WIN_SCRIPT) -> list[str]:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]


def win_env(name: str, title: str, text: str, url: str = "", icon: str = "", dry: bool = False) -> dict:
    env = dict(os.environ)
    env.update({"MARGIN_NOTE_ID": f"Margin.Notifications.{_slug(name)}", "MARGIN_NOTE_NAME": name,
                "MARGIN_NOTE_ICON": icon, "MARGIN_NOTE_TITLE": f"{name}: {title}", "MARGIN_NOTE_TEXT": text,
                "MARGIN_NOTE_XML": toast_xml(title, text, url), "MARGIN_NOTE_DRY": "1" if dry else ""})
    return env


def _win_icon() -> str:
    from .. import home
    from .launcher import _put_icon

    ico = home.home() / "Margin.ico"   # the one the Desktop icon uses too
    return str(ico) if ico.is_file() or _put_icon(ico, "ico") else ""


def win_open_scheme(name: str) -> str:
    """Register `<name>-open:` for this account (HKCU\\Software\\Classes), whose command is the app's icon command
    (pythonw, no console): what a click on a toast opens. "" when it cannot be registered (not Windows)."""
    try:
        import winreg
    except ImportError:
        return ""
    scheme = f"{_slug(name)}-open"
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    command = subprocess.list2cmdline([str(pyw if pyw.exists() else exe), *_open_command()[1:]])
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{scheme}") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"URL:Open {name}")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{scheme}\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, command)
    except OSError:
        return ""
    return f"{scheme}:"


def _windows(name: str, title: str, text: str, url: str, run: Runner) -> dict:
    title, text = _short(title, 120), _short(text)
    with SEND_LOCK:
        target = win_open_scheme(name) or url
        r = run(win_command(), env=win_env(name, title, text, target, _win_icon()), capture_output=True, text=True,
                errors="replace", timeout=60, stdin=subprocess.DEVNULL, **no_window())
    last = ((r.stdout or "").strip().splitlines()[-1:] or [""])[0]
    word = (last.split() or [""])[0]
    if r.returncode == 0 and word in ("toast", "balloon"):
        out = {"sent": True, "how": word, "problem": ""}
        if word == "toast":   # which id showed it, and the setting Windows gave (for a problem report)
            out["detail"] = last[len(word):].strip()
        return out
    if r.returncode == 0 and word == "off":
        return {"sent": False, "how": "", "problem": f"Notifications from {name} are switched off in Windows "
                f"({last[3:].strip() or 'off'}): Windows Settings › System › Notifications."}
    return {"sent": False, "how": "", "problem":
            f"PowerShell: {((r.stderr or '') or (r.stdout or '')).strip()[:300] or 'no answer'}"}


# -- Linux and the rest ------------------------------------------------------------------------
def _gv(s: str) -> str:
    """A GVariant string literal for gdbus (so a text that starts with "-" or holds quotes stays one string)."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _linux(name: str, title: str, text: str, run: Runner) -> dict:
    title, text = _short(title, 120), _short(text)
    icon = str(Path(__file__).with_name("static") / "logo.svg")
    problems = []
    if shutil.which("notify-send"):
        r = run(["notify-send", f"--app-name={name}", f"--icon={icon}", "--", f"{name}: {title}", text],
                capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {"sent": True, "how": "notify-send", "problem": ""}
        problems.append(f"notify-send: {(r.stderr or '').strip()[:200]}")
    if shutil.which("gdbus"):
        r = run(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications", "--object-path",
                 "/org/freedesktop/Notifications", "--method", "org.freedesktop.Notifications.Notify", _gv(name), "0",
                 _gv(icon), _gv(f"{name}: {title}"), _gv(text), "[]", "{}", "10000"], capture_output=True, text=True,
                timeout=30)
        if r.returncode == 0:
            return {"sent": True, "how": "gdbus", "problem": ""}
        problems.append(f"gdbus: {(r.stderr or '').strip()[:200]}")
    return {"sent": False, "how": "", "problem": "; ".join(problems) or
            "Neither notify-send nor gdbus is on this computer (install libnotify-bin, or your desktop's "
            "notification service)."}


def where_to_allow(platform: str | None = None) -> str:
    """Where the person allows or stops them on this system, in words (Settings' test)."""
    platform = platform or sys.platform
    name = app_name()
    if platform == "darwin":
        return (f"The first time, macOS asks whether {name} may send notifications: choose Allow. You can change "
                f"it later in System Settings › Notifications › {name}.")
    if platform.startswith("win"):
        return (f"If nothing appeared, look in Windows Settings › System › Notifications (is {name} on, and Do not "
                "disturb off?).")
    return "If nothing appeared, your desktop may have notifications switched off, or Do not disturb on."
