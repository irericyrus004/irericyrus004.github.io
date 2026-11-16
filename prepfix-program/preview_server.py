"""
LOCAL PREVIEW - the teachers' app, on this computer only (http://127.0.0.1:<port>/), before anything is published.

The pages are built in memory exactly as Publish would build them (same app, same timetable file), so what you see
is what teachers will get. Nothing is uploaded. The server stops when PREPFIX is closed.

    srv = PreviewServer()
    url = srv.show(code, school_name, data, title="TERM 1 2027", marks={...})   # returns the address
    open_full_screen(url)

`marks` (optional) = {"moved": [(kind, name, day, period), ...], "bad": [(kind, name, day, period, "Rule 3 · why"), ...]}
- lessons shown with a "moved" marker / with the rule they still break (preview only).
"""
from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import prepfix_core as core

PREVIEW_TT = "preview"

# A service worker would keep old preview pages in the browser; the preview gets one that removes itself.
NO_SW = b"self.addEventListener('install',()=>self.skipWaiting());" \
        b"self.addEventListener('activate',e=>e.waitUntil(self.registration.unregister()));"


def build_files(code: str, school_name: str, data: dict, title: str = "PREVIEW", marks: dict | None = None,
                desktop: bool = False) -> dict:
    """The same files Publish would upload for this school and timetable, plus a preview flag."""
    files = dict(core.shell_files())
    files.update(core.school_page_files(code, school_name))
    bundle = dict(data)
    bundle.pop("institutions", None)
    bundle.pop("_lessons", None)
    bundle.pop("_unplaced", None)
    bundle["published"] = core.now_iso()
    if marks and (marks.get("moved") or marks.get("bad")):
        bundle = _mark_moved(bundle, marks.get("moved") or [], marks.get("bad") or [])
    tname = core.tt_name(title) or "PREVIEW"
    entry = {"id": PREVIEW_TT, "name": tname, "version": "preview-" + bundle["published"], "updated": bundle["published"],
             "note": "Preview on this computer - not published yet.", "institution": bundle.get("institution", ""),
             "teachers": len(bundle.get("teachers", [])), "classes": len(bundle.get("classes", [])), "count": 1,
             "created": bundle["published"]}
    school = {"name": school_name, "institution": entry["institution"], "note": entry["note"],
              "teachers": entry["teachers"], "classes": entry["classes"], "updated": entry["updated"],
              "footer": core.LOCKED_BRAND, "contact": core.LOCKED_CONTACT}
    doc = {"version": entry["version"], "school": school, "timetable": {"id": PREVIEW_TT, "name": tname}, "bundle": bundle}
    sch = {"code": code, "name": school_name, "registered": ""}
    files[f"s/{code}/t/{PREVIEW_TT}/data.json"] = core.compact_json(doc)
    files[f"s/{code}/meta.json"] = core.compact_json(core.school_meta(sch, [entry]))
    files["schools.json"] = core.compact_json({"schools": [{"code": code, "name": school_name,
                                                            "institution": entry["institution"],
                                                            "teachers": entry["teachers"], "classes": entry["classes"],
                                                            "updated": entry["updated"]}]})
    # the app reads this: local school list, no reminders, no app-update checks, a "PREVIEW" strip on top
    cfg_txt = files["config.js"].decode("utf-8")
    cfg = json.loads(cfg_txt[cfg_txt.index("{"): cfg_txt.rindex("}") + 1])
    cfg.update({"directory": "/schools.json", "preview": True, "previewTitle": tname})
    if desktop:                                       # PREPFIX desktop: the full app on this computer (no phones)
        cfg["desktop"] = True
    cfg.pop("push", None)
    files["config.js"] = ("self.IRERI_CONFIG = " + json.dumps(cfg, ensure_ascii=False) + ";\n").encode("utf-8")
    files["sw.js"] = NO_SW
    return files


def _mark_moved(bundle: dict, moved, bad=()) -> dict:
    """Copy of the bundle where the given lessons carry "mv": 1 (the app draws a 'moved' marker on them) and
    "bad": "Rule 3 · ..." (a rule PREPFIX could not make this lesson obey). Preview only - never published."""
    b = json.loads(json.dumps(bundle))
    want = {(k, str(n), int(d), int(p)) for k, n, d, p in moved}
    why = {}
    for k, n, d, p, text in bad:
        why.setdefault((k, str(n), int(d), int(p)), text)
    for kind in ("teachers", "classes", "rooms", "master"):
        for it in b.get(kind, []):
            nm = str(it.get("code") if kind == "teachers" else it.get("name"))
            for d, row in enumerate(it.get("grid", [])):
                for p, c in enumerate(row):
                    if isinstance(c, dict) and (kind, nm, d, p) in want:
                        c["mv"] = 1
                    if isinstance(c, dict) and (kind, nm, d, p) in why:
                        c["bad"] = why[(kind, nm, d, p)]
    return b


def moved_cells(before: dict, after: dict) -> list:
    """Every lesson box that differs between the imported timetable and the timetable now, in every view
    (teachers, classes, labs & fields, master): [(kind, name, day, period)]."""
    out = []
    if not before or not after:
        return out
    for kind in ("teachers", "classes", "rooms", "master"):
        old = {str(it.get("code") if kind == "teachers" else it.get("name")): it for it in before.get(kind, [])}
        for it in after.get(kind, []):
            nm = str(it.get("code") if kind == "teachers" else it.get("name"))
            o = old.get(nm)
            for d, row in enumerate(it.get("grid", [])):
                orow = (o or {}).get("grid", [])[d] if o and d < len(o.get("grid", [])) else []
                for p, c in enumerate(row):
                    oc = orow[p] if p < len(orow) else ""
                    if isinstance(c, dict) and c != oc:
                        out.append((kind, nm, d, p))
    return out


CLOSED = {"msg": ""}          # set when the school's PREPFIX is suspended or its subscription ended: no preview at all

_CLOSED_PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PREPFIX</title><style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#1D2A44;color:#fff;font:16px/1.5 "Segoe UI",Arial,sans-serif;text-align:center;padding:24px;box-sizing:border-box}
b{display:block;font-size:24px;margin:8px 0}p{color:#D7DEEA;max-width:560px}</style></head>
<body><div><div style="font-size:48px">&#9940;</div><b>PREPFIX is closed</b><p>%s</p></div></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    server_version = "PREPFIX-preview"

    def log_message(self, *a):                       # keep the PREPFIX window quiet
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if CLOSED["msg"]:
            import html as _h
            body = (_CLOSED_PAGE % _h.escape(CLOSED["msg"])).encode("utf-8")
            self.send_response(403)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        files = self.server.files
        if path == "" or path.endswith("/"):
            path += "index.html"
        body = files.get(path)
        if body is None:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith(".webmanifest"):
            ctype = "application/manifest+json"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        """The preview's own buttons: full screen on/off (no F11 key needed) and Close preview."""
        path = self.path.split("?", 1)[0]
        ok = False
        if path == "/__prepfix/fullscreen":
            ok = press_f11()
        elif path == "/__prepfix/close":
            ok = close_window()
        body = json.dumps({"ok": ok}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class PreviewServer:
    """One small web server on 127.0.0.1 (this computer only), started the first time a preview is shown."""

    def __init__(self):
        self.httpd = None
        self.code = None

    def show(self, code: str, school_name: str, data: dict, title: str = "PREVIEW", marks: dict | None = None,
             desktop: bool = False) -> str:
        files = build_files(code, school_name, data, title, marks, desktop)
        if self.httpd is None:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            self.httpd.daemon_threads = True
            self.httpd.files = files
            threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        else:
            self.httpd.files = files
        self.code = code
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/s/{code}/"

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd = None


def _browsers():
    """Chrome / Edge on Windows (they can open a window straight into full screen)."""
    out = []
    if sys.platform.startswith("win"):
        for base in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", ""), os.environ.get("LOCALAPPDATA", "")):
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
                p = Path(base) / rel
                if base and p.exists():
                    out.append(str(p))
    for name in ("msedge", "google-chrome", "chrome", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            out.append(p)
    return out


_WINDOW = {"proc": None}                     # the browser window PREPFIX opened for the preview


def press_f11() -> bool:
    """Switch the preview window's full screen on / off by pressing F11 for it (the window is in front, because
    its button was just clicked). Works when the keyboard's own F11 does not (laptops with an Fn key)."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        u = ctypes.windll.user32
        u.keybd_event(0x7A, 0, 0, 0)          # F11 down
        u.keybd_event(0x7A, 0, 2, 0)          # F11 up
        return True
    except Exception:
        return False


def close_window() -> bool:
    """Close the preview window PREPFIX opened."""
    p = _WINDOW.get("proc")
    if p is None or p.poll() is not None:
        return False
    threading.Timer(0.3, p.terminate).start()   # answer the page first, then close the window
    _WINDOW["proc"] = None
    return True


# The preview window is Edge / Chrome with a profile of its own (so full screen always applies). A browser profile
# grows big (cache, GPU cache, downloaded browser parts), so it is NOT kept in the toolkit folder: it lives in the
# computer's own app-data folder, its caches are emptied every time, and the old one inside the toolkit is removed.
_JUNK = ("Cache", "Code Cache", "GPUCache", "GrShaderCache", "GraphiteDawnCache", "ShaderCache", "DawnCache",
         "Service Worker", "Crashpad", "OptimizationGuidePredictionModels", "optimization_guide_model_store",
         "Safe Browsing", "component_crx_cache", "extensions_crx_cache", "WidevineCdm", "screen_ai", "ZxcvbnData",
         "hyphen-data", "Subresource Filter", "MEIPreload", "SODA", "SODALanguagePacks", "BrowserMetrics",
         "segmentation_platform", "Edge Wallet", "EdgeEDrop", "Speech Recognition", "Trust Protection Lists",
         "AutoLaunchProtocolsComponent", "FirstPartySetsPreloaded", "OnDeviceHeadSuggestModel", "PKIMetadata")


def _profile_dir() -> Path:
    import os
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or str(Path.home())
    return Path(base) / "PREPFIX Timetable Toolkit" / "preview_browser"


def _trim(prof: Path):
    """Empty the browser's caches (they are rebuilt in a second) - keeps the profile small."""
    import shutil
    if not prof.exists():
        return
    for root in (prof, prof / "Default"):
        for name in _JUNK:
            shutil.rmtree(root / name, ignore_errors=True)


def tidy_old_profiles(data_dir: Path | None = None):
    """Remove the big preview profile older versions kept inside the toolkit folder; trim the new one."""
    import shutil
    for old in (Path(data_dir or core.DATA_DIR) / "preview_browser", core.APP_DIR / "publisher_data" / "preview_browser"):
        shutil.rmtree(old, ignore_errors=True)
    if _WINDOW.get("proc") is None or _WINDOW["proc"].poll() is not None:
        _trim(_profile_dir())


def open_full_screen(url: str, data_dir: Path | None = None) -> bool:
    """Open the preview in its own browser window, full screen. Falls back to the normal browser.
    Returns True if a full-screen window was started."""
    prof = _profile_dir()
    for exe in _browsers():
        try:
            prof.mkdir(parents=True, exist_ok=True)
            old = _WINDOW.get("proc")
            if old is not None and old.poll() is None:  # a preview window is already open: show the new one there
                old.terminate()
                try:
                    old.wait(3)
                except Exception:
                    pass
            if old is None or old.poll() is not None:
                _trim(prof)
            _WINDOW["proc"] = subprocess.Popen([exe, f"--app={url}", "--start-fullscreen", f"--user-data-dir={prof}",
                                                "--no-first-run", "--no-default-browser-check",
                                                "--disk-cache-size=1", "--media-cache-size=1",
                                                "--disable-component-update", "--disable-background-networking",
                                                "--disable-sync", "--disable-extensions", "--disable-breakpad",
                                                "--disable-features=OptimizationGuideModelDownloading,"
                                                "OptimizationHintsFetching,MediaRouter,Translate"],
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            continue
    webbrowser.open(url)
    return False
