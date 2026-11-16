"""
PREPFIX Timetable Toolkit V1 - engine.

Reads a FET export (fet_reader.py), turns it into one data file, and puts it on a free web
page (GitHub Pages). Teachers open the page on their phones; the app shows the newest
timetable every time it is opened.

V1
  * "DEVELOPED BY CYRUS IRERI" and the contact number are built in and cannot be changed.
  * Registered schools are permanent: they cannot be deleted or renamed. The register is
    kept on the website itself, so any computer can load it again.
  * A school can have several named timetables (e.g. KIANDERI, KIANDERI WEEKDAY,
    KIANDERI SATURDAY TTS, END TERM EXAM, TUITION). Publishing with a name that already
    exists replaces that one timetable; a new name adds a new timetable.
  * Every publish is kept on this computer as a dated copy, so progress can be traced.

Extra Python packages: requests, beautifulsoup4, openpyxl.
"""
from __future__ import annotations

import base64
import gzip
import platform
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

import prepfix_licence as ireri_licence
import prepfix_lock as LOCK

APP_DIR = Path(__file__).resolve().parent
FOR_SCHOOLS_DIR = APP_DIR / "FOR_SCHOOLS"            # every registered school's own PREPFIX copy
DATA_DIR = APP_DIR / "prepfix_data"
_OLD_DATA_DIR = APP_DIR / "publisher_data"          # name used by earlier versions
if _OLD_DATA_DIR.is_dir() and not DATA_DIR.exists():
    try:
        _OLD_DATA_DIR.rename(DATA_DIR)
    except OSError:                                   # in use (e.g. a preview window open): keep using it this time
        DATA_DIR = _OLD_DATA_DIR
TEACHER_APP_DIR = APP_DIR / "teacher_app"
API = "https://api.github.com"

# ---- built in, not editable from the program ------------------------------------------
LOCKED_BRAND = "DEVELOPED BY CYRUS IRERI"
LOCKED_CONTACT = "0720872582"

# What a SCHOOL sees never names the tools behind PREPFIX (Cyrus Ireri's Google Sheet, his GitHub): those are his alone.
_PRIVATE_WORDS = [("in your Google Sheet", "in the PREPFIX backup"), ("in the PREPFIX Google Sheet", "in the PREPFIX backup"),
                  ("from the Google Sheet", "from the PREPFIX backup"), ("in the Google Sheet", "in the PREPFIX backup"),
                  ("the Google Sheet", "the PREPFIX service"), ("your Google Sheet", "the PREPFIX backup"),
                  ("Google Sheet", "PREPFIX backup"), ("GitHub", "the website"), ("github.io", "website")]


_GITHUB_WORDS = [("GitHub Pages", "the website"), ("your GitHub account", "your website account"),
                 ("own GitHub", "own website account"), ("GitHub token", "website key"), ("GitHub", "the website"),
                 ("github.io", "website")]


def public_text(s, school=True):
    """school=True: a school copy (no Google Sheet, no GitHub). False: Cyrus's own copy (no GitHub)."""
    s = str(s)
    for a, b in (_PRIVATE_WORDS if school else _GITHUB_WORDS):
        s = s.replace(a, b)
    return s.replace("the the website", "the website").replace("The the website", "The website")
LOCKED_WATERMARK = "© Cyrus Ireri"
# PREPFIX is the brand; each product is a toolkit under it (Timetable Toolkit now; Lyrics, Display ... later)
BRAND_NAME = "PREPFIX"
PRODUCT_NAME = "Timetable Toolkit"
PRODUCT_VERSION = "V1"
SLOGAN = "Prepare. Perfect. Present."
# The program only works with Cyrus's own GitHub account(s). Empty = the first account set up becomes the
# only one this copy will ever accept (kept in the saved folder and on the website).
LOCKED_GITHUB_OWNERS: list = ["irericyrus004"]
# Cyrus's Google Sheet (the same one the church toolkits use): every published timetable is also kept there,
# with its last 25 versions - a safe backup the website does not need. Setup can point it elsewhere ("sheet_url").
SHEET_URL = "https://script.google.com/macros/s/AKfycbyU3Qfwfsu_sF0gC5GGuclMPkMfcFBmTKdw41-2GZRS2zGWbHHU1AJdZ48JyEHNa74e/exec"
SETUP_FILE = "prepfix-setup.json"        # private: goes in the saved folder, never on the website
OLD_SETUP_FILE = "ireri-setup.json"      # name used by earlier versions (still read)
LICENCE_FILE = "prepfix-licence.json"    # in a school copy: the school's signed licence
OLD_LICENCE_FILE = "ireri-licence.json"  # name used by earlier copies (still read)


def licence_path() -> Path:
    """This copy's licence file (new name, or the name earlier copies used)."""
    p = APP_DIR / LICENCE_FILE
    return p if p.is_file() or not (APP_DIR / OLD_LICENCE_FILE).is_file() else APP_DIR / OLD_LICENCE_FILE
OWNER_GITHUB = f"https://{LOCKED_GITHUB_OWNERS[0]}.github.io" if LOCKED_GITHUB_OWNERS else ""
# Cyrus Ireri's own web address. The website is still kept on GitHub, but every link, QR poster, school list and
# licence check uses this address, so github.io is never shown. (Old github.io links still work: GitHub forwards them.)
OWNER_DOMAIN = "https://cbcrevisionhub.co.ke"
OWNER_SITE = OWNER_DOMAIN or OWNER_GITHUB
LICENCE_KEY_PATH = "licence-key.json"
DIRECTORY_URL = OWNER_SITE + "/schools.json" if OWNER_SITE else "/schools.json"
SITE_DIR = "site"

COMMON_WORDS = {"ST", "SAINT", "THE", "OF", "AND", "SCHOOL", "SCH", "SCHOOLS", "HIGH", "GIRLS", "BOYS", "SEC",
                "SECONDARY", "SENIOR", "SEN", "JUNIOR", "MIXED", "DAY", "BOARDING", "ACADEMY", "PRIMARY",
                "COMPREHENSIVE", "NATIONAL", "COUNTY", "SUB", "EXTRA", "TERM", "TIMETABLE", "GIRL", "BOY",
                "SNR", "SS", "HS", "COLLEGE"}


class PublishError(Exception):
    """A problem with a plain-English message that can be shown to the user."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def slugify(name: str, limit=30) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:limit].strip("-") or "school"


def make_code(name: str, existing=()) -> str:
    """st-barbara-kianderi-sen-school-8df5 : the school's name, then 4 random letters / digits, so the link
    (…/s/st-barbara-kianderi-sen-school-8df5/) shows the school and cannot be guessed. Schools registered earlier
    keep their links."""
    base = slugify(name, 50) or "school"
    while True:
        code = f"{base}-{secrets.token_hex(2)}"
        if code not in existing:
            return code


def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip()


def tt_name(name: str) -> str:
    """Timetable names are compared in capitals with single spaces: 'Kianderi  weekday' == 'KIANDERI WEEKDAY'."""
    return clean_name(name).upper()


def tt_id(name: str) -> str:
    return slugify(tt_name(name), 40) or "main"


def suggest_lock_words(name: str) -> str:
    words = [w for w in re.sub(r"[^A-Z0-9 ]+", " ", (name or "").upper()).split() if w not in COMMON_WORDS]
    return " ".join(words) or (name or "").upper()


def make_version() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(3)


SUB_DAYS = 365                       # a school's subscription: one year from the day it is registered


def plus_years(day: str, n: int = 1) -> str:
    """YYYY-MM-DD n calendar years later (29 Feb -> 28 Feb)."""
    d = datetime.strptime(str(day)[:10], "%Y-%m-%d")
    try:
        return d.replace(year=d.year + n).strftime("%Y-%m-%d")
    except ValueError:
        return d.replace(year=d.year + n, day=28).strftime("%Y-%m-%d")


def sub_until(sch) -> str:
    """The last day a school's subscription is paid for (YYYY-MM-DD): set when it is registered or renewed;
    schools registered before subscriptions existed: one year after their registration."""
    u = str((sch or {}).get("until") or "")[:10]
    if u:
        return u
    try:
        return plus_years(str((sch or {}).get("registered") or "")[:10])
    except ValueError:
        return ""


def days_left(until: str):
    """Days until the subscription ends (0 = ends today, negative = ended). None = unknown."""
    try:
        return (datetime.strptime(str(until)[:10], "%Y-%m-%d").date() - datetime.now().date()).days
    except ValueError:
        return None


def nice_day(d: str) -> str:
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return str(d or "")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def compact_json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def check_brand_files():
    """Refuse to work if the built-in name has been removed from the teachers' app."""
    try:
        js = (TEACHER_APP_DIR / "app.js").read_text("utf-8")
    except OSError:
        raise PublishError("This copy is incomplete (teacher_app\\app.js is missing). Contact Cyrus Ireri, "
                           f"{LOCKED_CONTACT}.")
    if LOCKED_BRAND not in js or LOCKED_CONTACT not in js or f"const WATERMARK = '{LOCKED_WATERMARK}'" not in js:
        raise PublishError("This copy of PREPFIX has been changed and cannot be used. Contact Cyrus Ireri, "
                           f"{LOCKED_CONTACT}, for a genuine copy.")


def _backup_file():
    """Where the set-up (token etc.) is ALSO kept: on this computer, outside the program folder, so that putting a new
    version of PREPFIX in place never asks for the token again. One file per owner / per school copy."""
    root = Path(os.environ.get("APPDATA") or (Path.home() / ".config")) / "PREPFIX"
    who, gh = "owner", ""
    try:
        lic = json.loads(licence_path().read_text("utf-8"))
        gh = str(lic.get("github", "")).lower()
        who = "school-" + re.sub(r"[^a-z0-9_-]", "", gh)
    except Exception:
        pass
    return root / (who + ".json"), gh


class Settings:
    def __init__(self, name="settings.json"):
        DATA_DIR.mkdir(exist_ok=True)
        self.path = DATA_DIR / name
        self.data = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text("utf-8"))
            except Exception:
                self.data = {}
        self.backup, self._gh = _backup_file() if name == "settings.json" else (None, "")
        if self.backup:
            if not self.data.get("token"):
                self._restore()
            elif not self.backup.exists():
                self._mirror()

    def _restore(self):
        """The program folder was replaced / prepfix_data lost: take the token back from this computer's own copy."""
        try:
            d = json.loads(self.backup.read_text("utf-8"))
            if d.get("token") and d.get("owner") and (not self._gh or str(d["owner"]).lower() == self._gh):
                self.data = d
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), "utf-8")
                tmp.replace(self.path)
        except Exception:
            pass

    def _mirror(self):
        try:
            if self.data.get("token") and self.data.get("owner"):
                self.backup.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.backup.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8")
                tmp.replace(self.backup)
        except Exception:
            pass

    def get(self, k, default=None):
        v = self.data.get(k, default)
        return default if v is None else v

    def set(self, k, v):
        self.data[k] = v
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)
        if self.backup:
            self._mirror()


# ---------------------------------------------------------------------------
# GitHub (free hosting)
# ---------------------------------------------------------------------------

class GitHub:
    def __init__(self, token: str):
        self.token = (token or "").strip()
        self.s = requests.Session()
        self.s.headers.update({"Authorization": "Bearer " + self.token,
                               "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28",
                               "User-Agent": "PREPFIX-Timetable-Toolkit"})

    def req(self, method, path, ok=(200,), **kw):
        url = path if path.startswith("http") else API + path
        for attempt in range(4):
            try:
                r = self.s.request(method, url, timeout=60, **kw)
            except requests.RequestException:
                if attempt == 3:
                    raise PublishError("No internet connection. Connect this computer to the internet and try again.")
                time.sleep(2 + attempt * 3)
                continue
            limited = r.status_code == 429 or (r.status_code == 403 and "rate limit" in r.text.lower())
            if (r.status_code in (500, 502, 503, 504) or limited) and attempt < 3:
                time.sleep(4 + attempt * 6)
                continue
            if r.status_code == 401:
                raise PublishError("GitHub did not accept the token. Create a new one (see the Setup guide) "
                                   "and paste it again.")
            if r.status_code not in ok:
                try:
                    msg = r.json().get("message", r.text[:200])
                except Exception:
                    msg = r.text[:200]
                raise PublishError(f"GitHub said: {msg} ({r.status_code})")
            return r
        raise PublishError("GitHub did not respond. Try again in a minute.")

    def whoami(self) -> str:
        r = self.req("GET", "/user")
        scopes = r.headers.get("X-OAuth-Scopes")
        if scopes is not None and not ({"public_repo", "repo"} & {x.strip() for x in scopes.split(",")}):
            raise PublishError("The token is missing the 'public_repo' permission. Create a new token and tick "
                               "the box called public_repo.")
        return r.json()["login"]

    def ensure_repo(self, owner: str, repo: str) -> str:
        r = self.req("GET", f"/repos/{owner}/{repo}", ok=(200, 404))
        if r.status_code == 404:
            self.req("POST", "/user/repos", ok=(201,),
                     json={"name": repo, "description": "School timetables", "private": False,
                           "auto_init": True, "has_issues": False, "has_wiki": False, "has_projects": False})
            for _ in range(10):
                time.sleep(1.5)
                r = self.req("GET", f"/repos/{owner}/{repo}", ok=(200, 404))
                if r.status_code == 200 and self.req("GET", f"/repos/{owner}/{repo}/commits?per_page=1",
                                                     ok=(200, 409)).status_code == 200:
                    break
        return r.json().get("default_branch", "main")

    def enable_pages(self, owner: str, repo: str, branch: str):
        r = self.req("GET", f"/repos/{owner}/{repo}/pages", ok=(200, 404))
        if r.status_code == 404:
            self.req("POST", f"/repos/{owner}/{repo}/pages", ok=(201, 409),
                     json={"source": {"branch": branch, "path": "/"}})

    def tree(self, owner, repo, branch) -> dict:
        base = f"/repos/{owner}/{repo}"
        head = self.req("GET", f"{base}/git/ref/heads/{branch}").json()["object"]["sha"]
        tree_sha = self.req("GET", f"{base}/git/commits/{head}").json()["tree"]["sha"]
        tree = self.req("GET", f"{base}/git/trees/{tree_sha}?recursive=1").json()
        return {t["path"]: t["sha"] for t in tree.get("tree", []) if t["type"] == "blob"}

    def commit_files(self, owner, repo, branch, files: dict, message: str, delete_prefixes=()):
        """files: {path: bytes}. Only changed files are sent. Files are deleted only under delete_prefixes."""
        base = f"/repos/{owner}/{repo}"
        for attempt in range(3):
            head = self.req("GET", f"{base}/git/ref/heads/{branch}").json()["object"]["sha"]
            tree_sha = self.req("GET", f"{base}/git/commits/{head}").json()["tree"]["sha"]
            tree = self.req("GET", f"{base}/git/trees/{tree_sha}?recursive=1").json()
            have = {t["path"]: t["sha"] for t in tree.get("tree", []) if t["type"] == "blob"}
            entries = []
            for path, data in files.items():
                if have.get(path) == git_blob_sha(data):
                    continue
                b = self.req("POST", f"{base}/git/blobs", ok=(201,),
                             json={"content": base64.b64encode(data).decode(), "encoding": "base64"}).json()
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": b["sha"]})
            for pre in delete_prefixes:
                for path in have:
                    if path.startswith(pre) and path not in files:
                        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            if not entries:
                return None
            new_tree = self.req("POST", f"{base}/git/trees", ok=(201,),
                                json={"base_tree": tree_sha, "tree": entries}).json()["sha"]
            commit = self.req("POST", f"{base}/git/commits", ok=(201,),
                              json={"message": message, "tree": new_tree, "parents": [head]}).json()["sha"]
            r = self.req("PATCH", f"{base}/git/refs/heads/{branch}", ok=(200, 422), json={"sha": commit})
            if r.status_code == 200:
                return commit
            time.sleep(2)
        raise PublishError("Could not save to GitHub (it was busy). Try again in a minute.")

    def read_file(self, owner, repo, branch, path):
        r = self.req("GET", f"/repos/{owner}/{repo}/contents/{path}?ref={branch}", ok=(200, 404),
                     headers={"Accept": "application/vnd.github.raw"})
        return r.content if r.status_code == 200 else None

    def pages_status(self, owner, repo):
        r = self.req("GET", f"/repos/{owner}/{repo}/pages/builds/latest", ok=(200, 404))
        return r.json() if r.status_code == 200 else {}


# ---------------------------------------------------------------------------
# The website that teachers open
# ---------------------------------------------------------------------------

REMOTE_SHELL: dict = {}   # school copies: the newest teachers' app, taken from Cyrus Ireri's website


def _app_bytes(name: str) -> bytes:
    if name in REMOTE_SHELL:
        return REMOTE_SHELL[name]
    return (TEACHER_APP_DIR / name).read_bytes()


OWNER_PW = {}          # owner password (salt + hash only) - lets the owner open every school inside the app
PUSH_URL = ""          # the reminder service (Cloudflare Worker) link; set by the Publisher from its settings


PC_ONLY_PICTURES = {"prepfix-logo-230.png", "prepfix-logo-760.png", "prepfix-logo-1000.png", "prepfix-logo-1300.png",
                    "prepfix-toolkit.ico", "prepfix-toolkit-icon-256.png", "prepfix-badge-64.png",
                    "prepfix-badge-84.png", "prepfix-badge-380.png", "prepfix-badge-520.png", "prepfix-badge-700.png"}


def shell_files() -> dict:
    """The app itself (same for every school)."""
    check_brand_files()
    files = {}
    for name in ("app.css", "app.js", "sw.js", "qrcode.js", "manifest.webmanifest", "fet_schools.json"):
        files[name] = _app_bytes(name)
    for p in sorted((TEACHER_APP_DIR / "icons").glob("*.png")):
        files["icons/" + p.name] = p.read_bytes()
    for p in sorted([*(TEACHER_APP_DIR / "brand").glob("*.png"), *(TEACHER_APP_DIR / "brand").glob("*.jpg")]):
        if p.name in PC_ONLY_PICTURES:                  # the big opening-screen logos stay on the computer
            continue
        files["brand/" + p.name] = p.read_bytes()
    for k, v in REMOTE_SHELL.items():                  # newest pictures / icons from Cyrus Ireri's website
        if k.startswith(("icons/", "brand/")):
            files[k] = v
    files["index.html"] = _app_bytes("index.html").replace(b"__TITLE__", PRODUCT_NAME.encode())
    build = hashlib.sha1(b"".join(files[k] for k in sorted(files))).hexdigest()[:8]
    raw = {k: (_app_bytes(k) if k == "index.html" else files[k]) for k in files}
    files["shell.json"] = compact_json({"build": build, "files": sorted(raw), "by": LOCKED_BRAND})
    cfg = {"brand": LOCKED_BRAND, "contact": LOCKED_CONTACT, "build": build, "directory": DIRECTORY_URL}
    if OWNER_PW:
        cfg["ownerPw"] = OWNER_PW                  # salt + scrambled password; the password itself is never stored
    if PUSH_URL:
        cfg["push"] = PUSH_URL                     # lesson reminders that arrive even when the app is closed
    files["config.js"] = ("self.IRERI_CONFIG = " + json.dumps(cfg, ensure_ascii=False) + ";\n").encode("utf-8")
    files[".nojekyll"] = b""
    return files


def owner_files() -> dict:
    """The PREPFIX Owner app (Cyrus Ireri's phone): /owner/ on his own website only, never on a school's."""
    d = TEACHER_APP_DIR / "owner"
    if not (d / "index.html").is_file():
        return {}
    page = (d / "index.html").read_bytes().replace(b"__PUSH__", (PUSH_URL or "__PUSH__").encode())
    return {"owner/index.html": page, "owner/manifest.webmanifest": (d / "manifest.webmanifest").read_bytes(),
            "owner/sw.js": (d / "sw.js").read_bytes()}


def school_page_files(code: str, name: str) -> dict:
    page = _app_bytes("index.html").decode("utf-8").replace("__TITLE__", html.escape(name + " · " + PRODUCT_NAME))
    manifest = json.loads(_app_bytes("manifest.webmanifest"))
    manifest.update({"name": PRODUCT_NAME, "short_name": PRODUCT_NAME,
                     "description": f"{name} · {manifest.get('description', '')}",
                     "id": f"/s/{code}/", "start_url": f"/s/{code}/", "scope": "/"})
    base = f"s/{code}/"
    return {base + "index.html": page.encode("utf-8"),
            base + "manifest.webmanifest": json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")}


PC_ONLY_MESSAGE = ("This school uses PREPFIX on the school computer only. Timetables on phones are not switched on "
                   "for this school - ask the school office.")
SUSPENDED_MESSAGE = ("This school's timetable service is suspended. Please contact the school office or "
                     "Cyrus Ireri, " + LOCKED_CONTACT + ".")


def school_meta(sch: dict, timetables: list) -> dict:
    """s/<code>/meta.json - the school and the list of its timetables (newest first)."""
    tts = sorted(timetables, key=lambda t: (t.get("created") or t.get("updated") or ""))   # first published first
    latest = max(tts, key=lambda t: t.get("updated", "")) if tts else {}
    if sch.get("mobile") is False and not sch.get("suspended"):   # PC only: phones show a message, no timetable
        return {"code": sch["code"], "name": sch["name"], "suspended": True, "pc_only": True, "footer": LOCKED_BRAND,
                "contact": LOCKED_CONTACT, "message": PC_ONLY_MESSAGE, "timetables": []}
    if sch.get("suspended"):                         # suspended by Cyrus Ireri: phones show the message, no timetable
        return {"code": sch["code"], "name": sch["name"], "suspended": True, "footer": LOCKED_BRAND,
                "contact": LOCKED_CONTACT, "message": SUSPENDED_MESSAGE, "timetables": []}
    return {"code": sch["code"], "name": sch["name"], "registered": sch.get("registered", ""),
            "footer": LOCKED_BRAND, "contact": LOCKED_CONTACT, "locked": bool(sch.get("lock")),
            "updated": latest.get("updated", ""), "institution": latest.get("institution", ""),
            "note": latest.get("note", ""),
            "version": hashlib.sha1("|".join(f"{t['id']}:{t['version']}" for t in tts).encode()).hexdigest()[:16]
            if tts else "",
            "timetables": [{k: t.get(k) for k in ("id", "name", "version", "created", "updated", "note", "institution",
                                                  "teachers", "classes", "count")} for t in tts]}


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------

PACKAGE_FILES = ["prepfix_timetable.py", "prepfix_core.py", "prepfix_ui.py", "prepfix_licence.py", "fet_reader.py",
                 "constraints.py", "constraints_ui.py", "move_logic.py", "move_ui.py", "checks.py", "preview_server.py", "asc_reader.py", "asc_pdf.py", "notes_file.py", "notes_word.py",
                 "rules_word.py", "rules_more.py", "autofix.py", "transfer.py", "transfer_ui.py", "fet_rules.py", "my_rules.py", "my_rules_ui.py", "prepfix_lock.py", "phones_ui.py", "sheet_reader.py", "pin_sheet.py",
                 "Start PREPFIX.bat", "README.txt", "SETUP GUIDE.html"]
# every program file must be in a school copy, or the copy cannot start: check it here, once, when PREPFIX opens
_MISSING = sorted(p.name for p in APP_DIR.glob("*.py") if p.name not in PACKAGE_FILES)
GITHUB_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


SCHOOL_GUIDE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>PREPFIX · How to use</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:760px;margin:30px auto;padding:0 16px;color:#1B2333;line-height:1.55}
h1{color:#12284C;margin:6px 0}h2{color:#12284C;margin-top:26px}.card{background:#fff;border:1px solid #E9E1CC;border-radius:12px;padding:12px 16px;margin:10px 0}
.n{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#12284C;color:#fff;font-weight:700;margin-right:8px}
body{background:#FBF6EA}code{background:#F3EEDF;padding:1px 6px;border-radius:6px}</style></head><body>
<p><img src="teacher_app/brand/prepfix-logo-600.png" alt="PREPFIX Timetable Toolkit" style="width:min(100%,380px)"></p>
<h1>__SCHOOL__</h1>
<p>This is the school's own copy of PREPFIX Timetable Toolkit V1. Make the timetable in FET or aSc Timetables as usual;
PREPFIX gives it a clean look, prints it and sends it to teachers' phones. It never changes the timetable.</p>
<h2>First time only</h2>
<div class="card"><span class="n">1</span><b>Install Python</b> from <code>python.org/downloads</code> — on the first screen tick <b>Add python.exe to PATH</b>, then <b>Install Now</b>.</div>
<div class="card"><span class="n">2</span>Copy this whole folder to a permanent place (e.g. Documents) and double-click <b>Start PREPFIX.bat</b>.
Nothing else to set up.</div>
<h2>Every time a timetable is ready</h2>
<div class="card"><span class="n">1</span>Open <b>Start PREPFIX.bat</b> → <b>Import &amp; Run</b>.</div>
<div class="card"><span class="n">2</span>Add the timetable: the folder FET made, or the PDFs printed from aSc Timetables (the class and the teacher timetables, both together).</div>
<div class="card"><span class="n">3</span>Add notes if you wish → <b>Preview</b> → print. Press <b>Publish</b> to send it to teachers' phones.</div>
<h2>Teachers who may open the timetables</h2>
<div class="card">Only teachers this school registers can open its timetables on a phone — nobody from another school.
<br><span class="n">1</span>Open PREPFIX → click the school → <b>👥 Teachers &amp; phones</b>.
<br><span class="n">2</span><b>+ Add teacher</b> (name and phone number) or <b>📋 Paste a list</b>, then <b>💾 Save the list</b>.
<br><span class="n">3</span>Share the app link. Each teacher types the registered number and makes their own 4-number PIN, once.
Install appears after signing in. One number = one phone.
<br><span class="n">4</span>Wrong person signed in, or a teacher forgot the PIN? Click the teacher → <b>🔓 Remove sign-in</b>; the
teacher then signs in again with a new PIN. <b>↻ Who has the app?</b> shows who is signed in.</div>
<h2>New laptop</h2>
<div class="card">Open <b>Setup</b> → <b>Back up everything: Save now</b> and keep the saved folder on a flash disk.
On the new laptop, copy this folder, start PREPFIX → <b>Setup</b> → <b>Import my saved folder</b>. Everything comes back.</div>
<p>Help: Cyrus Ireri · 0720872582</p></body></html>"""


def load_licence():
    p = licence_path()
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        raise PublishError("This copy's licence file is damaged. Contact Cyrus Ireri, " + LOCKED_CONTACT + ".")


class Publisher:
    """edition 'owner' (Cyrus: registers any number of schools) or 'school' (registers its own school once)."""

    def __init__(self, log=print):
        self.log = log
        self.s = Settings()
        self.licence = load_licence()                      # present only in a school copy
        global PUSH_URL, OWNER_PW
        PUSH_URL = ((self.licence or {}).get("push") or self.s.get("push_url") or "").rstrip("/")
        OWNER_PW = ({"salt": self.s.get("owner_pw_salt"), "hash": self.s.get("owner_pw_hash")}
                    if (self.s.get("owner_pw_hash") and not self.licence) else {})
        self._lic_ok = False
        self._fix_mobile_settings()

    def _fix_mobile_settings(self):
        """Owner: every school gets a real 'mobile app' setting that only Cyrus Ireri changes. Schools that were
        already publishing to phones before the switch existed start ON; every other school starts PC ONLY."""
        if self.licence:
            return
        mine = list(self.s.get("schools", []) or [])
        changed = False
        for sch in mine:
            if "mobile" not in sch:
                sch["mobile"] = bool(self.timetables(sch["code"]) or (sch.get("remote") or {}).get("count"))
                sch["mobile_since"] = now_iso()
                changed = True
        if changed:
            self.s.set("schools", mine)

    @property
    def edition(self) -> str:
        return "school" if self.licence else "owner"

    @property
    def is_school(self) -> bool:
        return bool(self.licence)

    @property
    def copy_id(self) -> str:
        return "owner"

    @property
    def bound_school(self):
        """School copies: the one school named in the signed licence. It never changes."""
        if not self.licence:
            return None
        L = self.licence
        return {"code": L["code"], "name": L["name"], "registered": L.get("registered", ""), "github": L["github"],
                "lock": bool(L.get("lock"))}

    def verify_licence(self):
        """School copies: check the licence against Cyrus Ireri's website."""
        if not self.licence or self._lic_ok:
            return
        try:
            r = requests.get(f"{self.licence.get('owner_site') or OWNER_SITE}/{LICENCE_KEY_PATH}",
                             params={"t": int(time.time())}, timeout=30)
            pub = r.json() if r.status_code == 200 else None
        except Exception:
            raise PublishError("No internet connection (the licence is checked online). Connect and try again.")
        if not pub or not ireri_licence.verify(self.licence, pub) or \
                (self.licence.get("owner_site") and OWNER_SITE and
                 self.licence["owner_site"].rstrip("/") not in {OWNER_SITE, OWNER_GITHUB}):
            raise PublishError("This copy's licence is not valid. Contact Cyrus Ireri, " + LOCKED_CONTACT + ".")
        try:
            d = requests.get(f"{self.licence.get('owner_site') or OWNER_SITE}/schools.json",
                             params={"t": int(time.time())}, timeout=30).json()
            me = next((x for x in d.get("schools", []) if x.get("code") == self.licence.get("code")), {})
        except Exception:
            me = {}
        if me.get("suspended"):
            raise PublishError("This school's PREPFIX service is SUSPENDED. Contact Cyrus Ireri, " + LOCKED_CONTACT + ".")
        if me and (days_left(sub_until(me)) or 0) < 0:
            raise PublishError(f"This school's PREPFIX subscription ended on {nice_day(sub_until(me))}. To renew, "
                               f"contact Cyrus Ireri, {LOCKED_CONTACT}.")
        self._lic_ok = True

    def owner_entry(self) -> dict | None:
        """School copies: this school's line in Cyrus Ireri's list of schools (None = could not check)."""
        try:
            d = requests.get(f"{self.licence.get('owner_site') or OWNER_SITE}/schools.json",
                             params={"t": int(time.time())}, timeout=20).json()
        except Exception:
            return None
        return next((x for x in d.get("schools", []) if x.get("code") == self.licence.get("code")), {})

    def linked_github(self) -> str:
        """School copies: the GitHub account this school publishes with - in the licence, or linked later by
        Cyrus Ireri when he switched the mobile app on."""
        g = (self.licence or {}).get("github") or ""
        if g:
            return g.lower()
        e = self.owner_entry() or {}
        return (e.get("github") or "").lower()

    def check_mobile_allowed(self):
        """School copies, before sending anything to phones: the mobile app must be allowed by Cyrus Ireri."""
        ok = self.mobile_allowed_here()
        if ok is None:
            raise PublishError("No internet connection (PREPFIX checks online). Connect and try again.")
        if not ok:
            raise PublishError("The mobile app is not switched on for this school, so timetables cannot be sent to "
                               "phones. You can still preview and print every timetable on this computer "
                               "(Import & Run → Preview). To use phones, contact Cyrus Ireri, " + LOCKED_CONTACT + ".")

    # ---- settings
    @property
    def relay(self) -> bool:
        """School copies with no GitHub account of their own (the default now): Publish goes through Cyrus Ireri's
        Google Sheet, which puts the school's timetables on his website. The school never needs GitHub."""
        return bool(self.is_school and (self.licence or {}).get("skey") and not self.s.get("token"))

    @property
    def ready(self) -> bool:
        return bool(self.s.get("token") and self.s.get("owner")) or self.relay

    @property
    def github_url(self) -> str:
        return f"https://{self.s.get('owner')}.github.io"

    @property
    def domain(self) -> str:
        """The web address teachers see (a custom domain) - empty when the plain GitHub address is used."""
        d = (self.s.get("domain") or "").strip().rstrip("/")
        if not d and OWNER_DOMAIN and not self.is_school and LOCKED_GITHUB_OWNERS and \
                (self.s.get("owner") or "").lower() == LOCKED_GITHUB_OWNERS[0].lower():
            d = OWNER_DOMAIN
        if d and not d.startswith("http"):
            d = "https://" + d
        return d

    @property
    def site_url(self) -> str:
        if self.relay:
            return ((self.licence or {}).get("owner_site") or OWNER_SITE).rstrip("/")
        return self.domain or self.github_url

    def same_site(self, url) -> bool:
        """Is this address our own website (the domain, or the github.io address behind it)?"""
        u = (url or "").rstrip("/").lower()
        return bool(u) and u in {self.site_url.lower(), self.github_url.lower()}

    @property
    def repo(self) -> str:
        return f"{self.s.get('owner')}.github.io"

    @property
    def branch(self):
        return self.s.get("branch", "main")

    def school_link(self, code: str) -> str:
        sch = self.school(code) or {}
        site = self.site_url if self.is_school else (sch.get("site") or self.site_url)
        if self.same_site(site):
            site = self.site_url
        return f"{site}/s/{code}/"

    def own_account(self, sch) -> bool:
        """Owner edition: this school publishes for itself on its own GitHub account."""
        return bool(not self.is_school and sch and sch.get("site") and not self.same_site(sch["site"]))

    def gh(self) -> GitHub:
        if not self.ready:
            raise PublishError("Finish the one-time Setup first (Setup tab).")
        return GitHub(self.s.get("token"))

    # ---- permanent register of schools -------------------------------------------------
    def schools(self) -> list:
        if self.is_school:
            return [self.bound_school]
        gone = set(self.s.get("deleted", []))
        return [x for x in self.s.get("schools", []) if x["code"] not in gone]

    def school(self, code):
        return next((x for x in self.schools() if x["code"] == code), None)

    def _merge_register(self, entries: list) -> int:
        """Add schools we did not know about, and take over name changes made on another computer."""
        if self.is_school:
            return 0                                       # a school copy only ever knows its own school
        mine = list(self.s.get("schools", []))
        have = {x["code"] for x in mine} | set(self.s.get("deleted", []))
        added = 0
        changed = False
        for x in mine:                                     # a licence made on another computer
            e = next((e for e in entries if e.get("code") == x["code"]), None)
            if e and e.get("github") and not x.get("github"):
                x.update({"github": e["github"], "site": e.get("site", "")})
                changed = True
            if e and e.get("renamed") and e.get("name") and e["renamed"] > (x.get("renamed") or "") \
                    and e["name"] != x["name"]:                  # renamed on another computer
                x.update({"name": e["name"], "renamed": e["renamed"]})
                changed = True
        for e in entries:
            if e.get("code") and e["code"] not in have and e.get("name"):
                mine.append({"code": e["code"], "name": e["name"], "copy_id": e.get("copy_id", ""),
                             "github": e.get("github", ""), "site": e.get("site", ""),
                             "registered": e.get("registered") or e.get("updated") or now_iso()})
                have.add(e["code"])
                added += 1
        if added or changed:
            self.s.set("schools", mine)
        return added

    def bind_from_website(self):
        return self.bound_school

    def can_register(self) -> bool:
        return not self.is_school

    def register_school(self, name: str) -> dict:
        name = clean_name(name).upper()
        if len(name) < 3:
            raise PublishError("Type the school's name first.")
        key = lambda n: re.sub(r"[^A-Z0-9]", "", n.upper())
        if self.is_school:
            raise PublishError(f"This copy belongs to {self.bound_school['name']}. Schools are registered only by "
                               f"Cyrus Ireri, {LOCKED_CONTACT}.")
        everyone = list(self.s.get("schools", []))
        if self.ready:
            remote = self.remote_directory()
            everyone += [x for x in (remote.get("register") or remote.get("schools", []))]
        gone = set(self.s.get("deleted", [])) | set((remote.get("deleted") or []) if self.ready else [])
        if any(key(x.get("name", "")) == key(name) and x.get("code") not in gone for x in everyone):
            raise PublishError(f"{name} is already registered. A school is registered only once"
                               + (" — contact Cyrus Ireri, " + LOCKED_CONTACT + "." if self.is_school else "."))
        mine = list(self.s.get("schools", []))
        sch = {"code": make_code(name, {x.get("code") for x in everyone} | gone), "name": name, "registered": now_iso(),
               "copy_id": self.copy_id, "mobile": True,        # new schools: everything on, teachers' phones included
               "lock": True}                                    # only teachers the school registers open its timetables
        sch["until"] = plus_years(datetime.now().strftime("%Y-%m-%d"))   # paid for one year from today
        mine.append(sch)
        self.s.set("schools", mine)
        keys = dict(self.s.get("lock_keys", {}) or {})
        keys[sch["code"]] = LOCK.new_key()
        self.s.set("lock_keys", keys)
        self.log(f"✔ Registered {name}.")
        if self.ready:
            try:
                self._upload({**school_page_files(sch["code"], name),
                              f"s/{sch['code']}/meta.json": compact_json(school_meta(sch, self.timetables(sch['code']))),
                              "schools.json": self.build_directory(event=("registered", sch, None))},
                             f"Register {name}")
                self.log("  ✔ Saved on the website too.")
            except PublishError as e:
                self.log("  ! Not yet saved on the website (it will be with the next publish): " + str(e))
            try:
                self.make_school_copy(sch["code"])
            except PublishError as e:
                self.log("  ! The school's PREPFIX copy was not made yet: " + str(e))
        self.autosave()
        return sch

    # ---- timetables of a school (kept on this computer) -------------------------------
    def _dir(self, code: str, tid: str = "") -> Path:
        d = DATA_DIR / "history" / code / tid if tid else DATA_DIR / "history" / code
        d.mkdir(parents=True, exist_ok=True)
        return d

    def timetables(self, code: str) -> list:
        """[{id, name, version, updated, note, institution, teachers, classes, count}] for one school."""
        idx = self.s.get("timetables", {})
        return list(idx.get(code, []))

    def _set_tt(self, code, entry):
        idx = dict(self.s.get("timetables", {}))
        lst = [t for t in idx.get(code, []) if t["id"] != entry["id"]]
        lst.append(entry)
        idx[code] = sorted(lst, key=lambda t: (t.get("created") or t.get("updated") or ""))
        self.s.set("timetables", idx)

    def history(self, code) -> list:
        """Every publish of every timetable of a school, newest first (from this computer)."""
        out = []
        root = DATA_DIR / "history" / code
        if not root.exists():
            return out
        for tdir in root.iterdir():
            if not tdir.is_dir():
                continue
            for f in tdir.glob("2*.json"):
                out.append({"tid": tdir.name, "file": f, "when": f.stem})
        out.sort(key=lambda x: x["when"], reverse=True)
        return out

    # ---- the shared list of schools on the website ------------------------------------
    def remote_json(self, path, gh=None):
        if self.relay and gh is None:                  # read straight from the website (public files)
            try:
                r = requests.get(f"{self.site_url}/{path}", params={"t": int(time.time())}, timeout=30)
                return r.json() if r.status_code == 200 else None
            except Exception:
                return None
        gh = gh or self.gh()
        raw = gh.read_file(self.s.get("owner"), self.repo, self.branch, path)
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def remote_directory(self, gh=None) -> dict:
        d = self.remote_json("schools.json", gh) or {}
        d.setdefault("schools", [])
        d.setdefault("activity", [])
        return d

    def build_directory(self, event=None, gh=None) -> bytes:
        """schools.json: every registered school (never removed) + recent activity."""
        d = self.remote_directory(gh) if self.ready else {"schools": [], "activity": []}
        if not self.is_school:
            self.adopt_web(d)                                     # suspended / restored on the owner page
        if not self.is_school and d.get("deleted"):               # removed on another computer
            self.s.set("deleted", sorted(set(self.s.get("deleted", [])) | set(d["deleted"])))
        gone = set(self.s.get("deleted", [])) | set(d.get("deleted", []))
        self._merge_register(d["schools"])
        by = {x["code"]: x for x in d["schools"] if x.get("code") and x["code"] not in gone}
        d["activity"] = [a for a in d.get("activity", []) if a.get("code") not in gone]
        if gone:
            d["deleted"] = sorted(gone)
        for sch in self.schools():
            e = by.get(sch["code"], {})
            tts = self.timetables(sch["code"])
            latest = max(tts, key=lambda t: t.get("updated", "")) if tts else {}
            if not tts and sch.get("remote"):
                rm = sch["remote"]
                latest = {"institution": rm.get("institution", ""), "updated": rm.get("updated", ""),
                          "teachers": rm.get("teachers"), "classes": rm.get("classes")}
            elif not tts and e.get("timetables"):
                latest = {"institution": e.get("institution", ""), "updated": e.get("updated", ""),
                          "teachers": e.get("teachers"), "classes": e.get("classes")}
            by[sch["code"]] = {
                "code": sch["code"], "name": sch["name"], "registered": sch.get("registered") or e.get("registered", ""),
                "copy_id": sch.get("copy_id") or e.get("copy_id", ""),
                "github": sch.get("github") or e.get("github", ""),
                "site": (self.site_url if self.same_site(sch.get("site") or e.get("site")) else
                         sch.get("site") or e.get("site") or (self.site_url if self.ready and not self.is_school else "")),
                "institution": latest.get("institution", e.get("institution", "")),
                "updated": latest.get("updated", e.get("updated", "")),
                "teachers": latest.get("teachers", e.get("teachers")), "classes": latest.get("classes", e.get("classes")),
                "count": sum(t.get("count", 1) for t in tts) if tts else (sch.get("remote") or {}).get("count") or e.get("count", 0),
                "school_name_locked": True,
                **({"renamed": sch["renamed"]} if sch.get("renamed") else {}),
                **({"suspended": True} if sch.get("suspended") else {}),
                "until": str(sch.get("until") or e.get("until") or sub_until(sch))[:10],
                "mobile": self.mobile_on(sch),
                "timetables": [t["name"] for t in tts] if tts else (sch.get("remote") or {}).get("timetables") or e.get("timetables", []),
            }
        if event:
            what, sch, tt = event
            text = {"registered": "Registered", "published": "Published", "restored": "Restored an earlier version",
                    "replaced": "Replaced (same name)", "licensed": "School copy made (own GitHub)",
                    "suspended": "SUSPENDED (service switched off)", "unsuspended": "Restored (service switched back on)",
                    "mobile_on": "Mobile app ALLOWED", "mobile_off": "Mobile app STOPPED (PC only)",
                    "renamed": "Name changed", "deleted": "Timetable DELETED",
                    "renewed": "Subscription RENEWED"}.get(what, what)
            d["activity"].insert(0, {"time": now_iso(), "code": sch["code"], "name": sch["name"],
                                     "timetable": tt.get("name", "") if tt else "", "what": text,
                                     "note": tt.get("note", "") if tt else "",
                                     "teachers": tt.get("teachers") if tt else None,
                                     "classes": tt.get("classes") if tt else None})
        d["activity"] = d["activity"][:500]
        d["schools"] = sorted(by.values(), key=lambda x: str(x.get("name", "")).lower())
        d["register"] = [{"code": x["code"], "name": x["name"], "registered": x.get("registered", ""),
                          "copy_id": x.get("copy_id", ""), "github": x.get("github", ""), "site": x.get("site", ""),
                          **({"renamed": x["renamed"]} if x.get("renamed") else {})}
                         for x in d["schools"]]
        d["updated"] = now_iso()
        return compact_json(d)

    def adopt_web(self, d=None) -> list:
        """Owner: take over what was done on the owner page (cbcrevisionhub.co.ke/owner): a school suspended or
        restored there. Returns [(name, suspended)] of the schools that changed here."""
        if self.is_school:
            return []
        if d is None:
            if not self.ready:
                return []
            try:
                d = self.remote_directory()
            except Exception:
                return []
        mine, done = list(self.s.get("schools", [])), []
        for x in d.get("schools", []):
            w = x.get("web") or {}
            sch = next((s for s in mine if s["code"] == x.get("code")), None)
            when = str(w.get("when") or "")
            if not sch or not when or when <= str(sch.get("web_seen") or ""):
                continue
            sch["web_seen"] = when
            if x.get("until") and str(sch.get("until_changed") or "") < when and str(x["until"])[:10] != sub_until(sch):
                sch["until"] = str(x["until"])[:10]                # renewed on the owner page
                done.append((sch["name"], "renewed", sch["code"]))
            if str(sch.get("susp_changed") or "") >= when:        # changed here after that: this computer wins
                continue
            if bool(x.get("suspended")) == bool(sch.get("suspended")):
                continue
            if x.get("suspended"):
                sch["suspended"] = {"when": when, "reason": "on the owner page"}
            else:
                sch.pop("suspended", None)
            done.append((sch["name"], bool(x.get("suspended")), sch["code"]))
        if any(str((x.get("web") or {}).get("when") or "") for x in d.get("schools", [])):
            self.s.set("schools", mine)
        for name, on, code in done:
            sch = next(s for s in mine if s["code"] == code)
            if on is False and self.ready and not self.own_account(sch) and self.timetables(code):
                try:                                              # its timetables back on the phones
                    self._upload({f"s/{code}/meta.json": compact_json(school_meta(sch, self.timetables(code)))},
                                 "Restore " + name)
                except Exception:
                    pass
        if done:
            self.autosave()
        return [(n, on) for n, on, _ in done]

    def renew_school(self, code: str, years: int = 1, start: str = "end", until: str = "") -> str:
        """Owner only: the school paid - its subscription runs one more year. start="end": counted from the day it
        was due to end (paid early or late, the school keeps its own date); start="today": from today. until: a
        last day chosen by hand (YYYY-MM-DD). Returns the new last day (YYYY-MM-DD)."""
        if self.is_school:
            raise PublishError("Only Cyrus Ireri can renew a school.")
        mine = list(self.s.get("schools", []))
        sch = next((x for x in mine if x["code"] == code), None)
        if not sch:
            raise PublishError("That school is not in the list.")
        today = datetime.now().strftime("%Y-%m-%d")
        if until:
            try:
                sch["until"] = datetime.strptime(str(until).strip()[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                raise PublishError("Type the date like 2027-11-16 (year-month-day).")
        else:
            base = today if start == "today" else (sub_until(sch) or today)
            sch["until"] = plus_years(base, max(1, int(years)))
        sch["until_changed"] = now_iso()
        self.s.set("schools", mine)
        if self.ready:
            self._wait_live(self._upload({"schools.json": self.build_directory(
                event=("renewed", sch, {"name": "paid until " + nice_day(sch["until"])}))}, "Renew " + sch["name"]))
        self.autosave()
        self.log(f"✔ {sch['name']}: subscription renewed — paid until {nice_day(sch['until'])}.")
        return sch["until"]

    def my_subscription(self, online=True):
        """School copies: (last paid day, days left, checked online, suspended). Online: from Cyrus Ireri's list of schools (and
        remembered); offline: the last day remembered, or one year after registration. Turning the computer's clock
        back does not help: the latest day seen is kept."""
        me = self.owner_entry() if online else None
        if me:
            u = sub_until(me)
            self.s.set("sub_until", u)
            if bool(me.get("suspended")) != bool(self.s.get("sub_susp")):
                self.s.set("sub_susp", bool(me.get("suspended")))
        else:
            u = self.s.get("sub_until") or sub_until(self.bound_school or {})
        today = max(datetime.now().strftime("%Y-%m-%d"), str(self.s.get("sub_seen") or ""))
        if today != self.s.get("sub_seen"):
            self.s.set("sub_seen", today)
        try:
            dl = (datetime.strptime(u, "%Y-%m-%d") - datetime.strptime(today, "%Y-%m-%d")).days
        except (TypeError, ValueError):
            dl = None
        return u, dl, bool(me), bool(self.s.get("sub_susp"))

    def set_suspended(self, code: str, on: bool, reason: str = "") -> str:
        """Owner only: switch a school's timetable service off (suspend) or back on (restore). Nothing is deleted:
        its registration, timetables and history stay, so restoring brings everything back at once."""
        if self.is_school:
            raise PublishError("Only Cyrus Ireri can suspend or restore a school.")
        mine = list(self.s.get("schools", []))
        sch = next((x for x in mine if x["code"] == code), None)
        if not sch:
            raise PublishError("That school is not in the list.")
        if on:
            sch["suspended"] = {"when": now_iso(), "reason": (reason or "").strip()}
        else:
            sch.pop("suspended", None)
        sch["susp_changed"] = now_iso()
        self.s.set("schools", mine)
        if self.ready:
            files = {"schools.json": self.build_directory(event=("suspended" if on else "unsuspended", sch, None))}
            if not self.own_account(sch):                  # on my website: its own page switches off / on too
                files[f"s/{code}/meta.json"] = compact_json(school_meta(sch, self.timetables(code)))
            self.log(("Suspending " if on else "Restoring ") + sch["name"] + "…")
            sha = self._upload(files, ("Suspend " if on else "Restore ") + sch["name"])
            self._wait_live(sha)
        self.autosave()
        self.log(("⏸ Suspended " if on else "▶ Restored ") + sch["name"] + (
            " — teachers' phones show that the service is suspended; publishing is blocked." if on else
            " — teachers see the timetables again; publishing works again."))
        return sch["name"]

    def rename_school(self, code: str, new_name: str) -> str:
        """Owner only: correct or change a school's name. Its link (code) stays the same, so teachers' phones and
        posters keep working. The website, the list of schools and the school's copy follow the new name."""
        if self.is_school:
            raise PublishError("Only Cyrus Ireri can change a school's name.")
        new = clean_name(new_name).upper()
        if len(new) < 3:
            raise PublishError("Type the new name first.")
        key = lambda n: re.sub(r"[^A-Z0-9]", "", str(n).upper())
        mine = list(self.s.get("schools", []))
        sch = next((x for x in mine if x["code"] == code), None)
        if not sch:
            raise PublishError("That school is not in the list.")
        if new == sch["name"]:
            raise PublishError("That is already its name.")
        everyone = [x for x in mine if x["code"] != code]
        if self.ready:
            remote = self.remote_directory()
            everyone += [x for x in (remote.get("register") or remote.get("schools", [])) if x.get("code") != code]
        if any(key(x.get("name", "")) == key(new) for x in everyone):
            raise PublishError(f"{new} is already the name of another registered school.")
        old = sch["name"]
        sch["name"] = new
        sch["renamed"] = now_iso()
        sch["old_names"] = [n for n in (sch.get("old_names") or []) if n != new] + [old]
        self.s.set("schools", mine)
        self.log(f"✎ {old}  →  {new}")
        if self.ready:
            files = {"schools.json": self.build_directory(event=("renamed", sch, {"name": f"was {old}"}))}
            if not self.own_account(sch):                  # its page on my website shows the new name at once
                files.update(school_page_files(code, new))
                files[f"s/{code}/meta.json"] = compact_json(school_meta(sch, self.timetables(code)))
            self._wait_live(self._upload(files, f"Rename {old} -> {new}"))
            try:
                self.make_school_copy(code)                # its copy carries the new name (folder renamed too)
            except PublishError as e:
                self.log("  ! The school's copy was not updated: " + str(e))
        self.autosave()
        return new

    def mobile_on(self, sch) -> bool:
        """Owner: may this school's teachers use the mobile app? Set by Cyrus Ireri on the Schools tab.
        Schools registered before this switch existed and already publishing to phones keep it."""
        if not sch:
            return False
        return bool(sch.get("mobile"))

    def set_mobile(self, code: str, on: bool, github: str = "") -> str:
        """Owner only: allow (on) or stop (off) the mobile app for a school. github (optional, when allowing): the
        school publishes from its own copy with that GitHub account; empty = Cyrus publishes for it on his website."""
        if self.is_school:
            raise PublishError("Only Cyrus Ireri can allow or stop the mobile app.")
        mine = list(self.s.get("schools", []))
        sch = next((x for x in mine if x["code"] == code), None)
        if not sch:
            raise PublishError("That school is not in the list.")
        github = (github or "").strip().lstrip("@").lower()
        if on and github and not sch.get("github"):
            if not GITHUB_NAME.match(github):
                raise PublishError("Type the school's GitHub username (letters, numbers and dashes only).")
            if github in [o.lower() for o in LOCKED_GITHUB_OWNERS]:
                raise PublishError("That is your own account. Leave it empty: you publish for this school.")
            others = [x for x in mine if x["code"] != code and (x.get("github") or "").lower() == github]
            if others:
                raise PublishError(f"The GitHub account “{github}” already belongs to {others[0]['name']}.")
            sch.update({"github": github, "site": f"https://{github}.github.io"})
        sch["mobile"] = bool(on)
        sch["mobile_since"] = now_iso()
        self.s.set("schools", mine)
        if self.ready:
            files = {"schools.json": self.build_directory(event=("mobile_on" if on else "mobile_off", sch, None))}
            if not self.own_account(sch) and self.timetables(code):          # its page on my website follows at once
                files[f"s/{code}/meta.json"] = compact_json(school_meta(dict(sch, mobile=bool(on)), self.timetables(code)))
            self.log(("Allowing" if on else "Stopping") + f" the mobile app for {sch['name']}…")
            self._wait_live(self._upload(files, ("Allow" if on else "Stop") + f" mobile app: {sch['name']}"))
        self.autosave()
        self.log(("📱 Mobile app ALLOWED for " if on else "🚫 Mobile app STOPPED for ") + sch["name"] +
                 (" — it can now publish to teachers' phones." if on else
                  " — teachers' phones stop showing its timetables; it keeps PREPFIX on the computer."))
        return sch["name"]

    def mobile_allowed_here(self) -> bool | None:
        """School copies: has Cyrus Ireri allowed the mobile app for this school? None = could not check (offline)."""
        if not self.is_school or not self.licence:
            return True
        try:
            d = requests.get(f"{self.licence.get('owner_site') or OWNER_SITE}/schools.json",
                             params={"t": int(time.time())}, timeout=20).json()
        except Exception:
            return None
        me = next((x for x in d.get("schools", []) if x.get("code") == self.licence.get("code")), None)
        return bool(me and me.get("mobile") and not me.get("suspended"))

    def is_suspended(self, code: str) -> bool:
        return bool((self.school(code) or {}).get("suspended"))

    def delete_school(self, code: str, typed_name: str) -> str:
        """Owner only: remove a school completely (for test schools / mistakes). Cannot be undone."""
        if self.is_school:
            raise PublishError("Only Cyrus Ireri can delete a school.")
        sch = self.school(code)
        if not sch:
            raise PublishError("That school is not in the list.")
        if clean_name(typed_name or "").upper() != sch["name"].upper():
            raise PublishError(f"The name you typed does not match “{sch['name']}”. Nothing was deleted.")
        self.s.set("deleted", sorted(set(self.s.get("deleted", [])) | {code}))
        self.s.set("schools", [x for x in self.s.get("schools", []) if x["code"] != code])
        idx = dict(self.s.get("timetables", {}))
        idx.pop(code, None)
        self.s.set("timetables", idx)
        shutil.rmtree(DATA_DIR / "history" / code, ignore_errors=True)
        if self.s.get("push_url") and self.owner_key():
            try:
                self._service("/roster", {"school": code, "off": True})
            except Exception as e:
                self.log(f"  (the sign-in service was not told: {e})")
        if self.ready:
            self.log(f"Removing {sch['name']} from the website…")
            sha = self._upload({"schools.json": self.build_directory()}, f"Delete school {sch['name']}",
                               delete_prefixes=(f"s/{code}/",))
            self._wait_live(sha)
        if self.s.get("save_folder"):
            shutil.rmtree(Path(self.s.get("save_folder")) / SITE_DIR / "s" / code, ignore_errors=True)
        self.autosave()
        note = " (its own GitHub website is the school's; only its listing was removed)" if sch.get("site") and not (self.ready and self.same_site(sch["site"])) else ""
        self.log(f"✔ Deleted {sch['name']}{note}.")
        return sch["name"]

    # ---- one-time set-up -----------------------------------------------------------------
    def setup(self, token: str) -> str:
        check_brand_files()
        token = (token or "").strip()
        if not token:
            raise PublishError("Paste your GitHub token first.")
        self.verify_licence()
        self.refresh_app_from_owner()
        self.log("Checking the token…")
        gh = GitHub(token)
        owner = gh.whoami().lower()
        self.check_owner(owner)
        self.log(f"  ✔ Signed in to GitHub as {owner}")
        repo = f"{owner}.github.io"
        self.log("Opening your timetable website (creating it if it does not exist yet)…")
        branch = gh.ensure_repo(owner, repo)
        gh.enable_pages(owner, repo, branch)
        self.s.set("token", token)
        self.s.set("owner", owner)
        self.s.set("owner_lock", owner)
        self.s.set("branch", branch)
        n = self.load_from_website()
        self.deploy_shell()
        self.autosave()
        self.log(f"✔ Done. Your timetable website is {self.site_url}" +
                 (f"  ({n} school(s) loaded from it)" if n else ""))
        return self.site_url

    def check_owner(self, owner: str):
        if self.is_school:
            want = self.linked_github()
            if not want:
                raise PublishError(f"Teachers' phones are not switched on for {self.licence['name']} yet, so no GitHub "
                                   "account is linked to this copy. PREPFIX works fully on this computer (import, "
                                   "check, fix, preview, print). For phones, contact Cyrus Ireri, " + LOCKED_CONTACT + ".")
            if owner.lower() != want:
                raise PublishError(f"This copy is for {self.licence['name']} and only works with the GitHub "
                                   f"account “{want}”. Contact Cyrus Ireri, {LOCKED_CONTACT}.")
            return
        allowed = [o.lower() for o in LOCKED_GITHUB_OWNERS] or ([self.s.get("owner_lock")] if self.s.get("owner_lock") else [])
        if allowed and owner.lower() not in allowed:
            raise PublishError("This copy of PREPFIX belongs to Cyrus Ireri and only works with "
                               f"his website. Contact Cyrus Ireri, {LOCKED_CONTACT}.")

    # ---- the saved folder: set up once, then just import -----------------------------------
    def setup_doc(self) -> dict:
        tok = self.s.get("token", "")
        return {"what": "PREPFIX - private set-up. Keep this file private; never upload it.",
                "owner": self.s.get("owner", ""), "owner_lock": self.s.get("owner_lock") or self.s.get("owner", ""),
                "branch": self.branch, "site": self.site_url if self.ready else "",
                "key": base64.b64encode(tok[::-1].encode()).decode() if tok else "",
                "edition": self.edition, "copy_id": self.copy_id,
                "licence_key": self.s.get("sign_key") if not self.is_school else None,
                "push_url": self.s.get("push_url") if not self.is_school else None,
                "owner_pw": ({"salt": self.s.get("owner_pw_salt"), "hash": self.s.get("owner_pw_hash")}
                             if (self.s.get("owner_pw_hash") and not self.is_school) else None),
                "deleted": self.s.get("deleted", []),
                "tk_pw": ({"salt": self.s.get("tk_pw_salt"), "hash": self.s.get("tk_pw_hash")}
                          if self.s.get("tk_pw_hash") else None),
                "phones": self.s.get("phones", {}) or {},                  # teachers' names and numbers
                "lock_keys": (self.s.get("lock_keys", {}) or {}) if not self.is_school else None,
                "owner_key": self.owner_key() if not self.is_school else None,
                "brand": LOCKED_BRAND, "contact": LOCKED_CONTACT, "saved": now_iso()}

    def save_folder(self, dest=None, quiet=False) -> Path:
        """Save everything (private set-up + the whole site) into one folder that can be imported later."""
        dest = Path(dest or self.s.get("save_folder") or "")
        if not str(dest) or str(dest) == ".":
            raise PublishError("Choose where to keep your saved folder first (Setup tab).")
        dest.mkdir(parents=True, exist_ok=True)
        n = self.export_site(dest / SITE_DIR)
        (dest / SETUP_FILE).write_text(json.dumps(self.setup_doc(), indent=2), "utf-8")
        try:                                           # the same file under its old name: now replaced by the one above
            (dest / OLD_SETUP_FILE).unlink(missing_ok=True)
        except OSError:
            pass
        (dest / "READ ME.txt").write_text(
            "PREPFIX - SAVED FOLDER\r\n\r\nTo use on any computer: open PREPFIX -> "
            "Setup tab -> Import my saved folder -> choose this folder.\r\n\r\nprepfix-setup.json is PRIVATE (it "
            "lets PREPFIX reach your website). Never upload or share it.\r\nThe 'site' folder is a full copy "
            "of the website (every school and timetable).\r\n", "utf-8")
        if not quiet:
            self.log(f"✔ Saved everything ({n} school(s)) to {dest}")
        return dest

    def autosave(self):
        if self.s.get("save_folder"):
            try:
                self.save_folder(quiet=True)
                self.log("  ✔ Saved folder updated.")
            except Exception as e:
                self.log("  ! Could not update the saved folder: " + str(e))

    @staticmethod
    def _find_site(folder: Path):
        """The newest saved site inside a folder (the folder itself, 'site', or any sub-folder)."""
        cands = []
        for p in [folder] + [x for x in folder.rglob("*") if x.is_dir() and len(x.relative_to(folder).parts) <= 3]:
            if (p / "schools.json").is_file():
                try:
                    upd = json.loads((p / "schools.json").read_text("utf-8")).get("updated", "")
                except Exception:
                    upd = ""
                cands.append((upd, 2, p))
            elif (p / "s").is_dir() and any((p / "s").glob("*/meta.json")):
                cands.append(("", 1, p))
        if not cands:
            return None
        cands.sort(key=lambda c: (c[0], c[1]))
        return cands[-1][2]

    def import_setup_file(self, sf) -> bool:
        doc = json.loads(Path(sf).read_text("utf-8"))
        tok = base64.b64decode(doc.get("key", "")).decode()[::-1] if doc.get("key") else ""
        owner = (doc.get("owner") or "").lower()
        if owner:
            self.check_owner(owner)
        if (doc.get("edition", "owner") == "school") != self.is_school:
            raise PublishError("That saved folder belongs to a different kind of copy of PREPFIX.")
        if doc.get("phones"):                                   # teachers' lists come back too
            allp = dict(self.s.get("phones", {}) or {})
            for code, people in doc["phones"].items():
                if people and not allp.get(code):
                    allp[code] = people
            self.s.set("phones", allp)
        if doc.get("lock_keys") and not self.is_school:
            keys = dict(doc["lock_keys"])
            keys.update(self.s.get("lock_keys", {}) or {})
            self.s.set("lock_keys", keys)
        if (doc.get("tk_pw") or {}).get("hash") and not self.s.get("tk_pw_hash"):
            self.s.set("tk_pw_salt", doc["tk_pw"].get("salt", ""))
            self.s.set("tk_pw_hash", doc["tk_pw"]["hash"])
        if doc.get("owner_key") and not self.is_school and not self.owner_key():
            self.s.set("owner_key", doc["owner_key"])
        if not (tok and owner):
            return self.relay
        if doc.get("licence_key") and not self.is_school:
            self.s.set("sign_key", doc["licence_key"])
        if doc.get("deleted") and not self.is_school:
            self.s.set("deleted", sorted(set(self.s.get("deleted", [])) | set(doc["deleted"])))
        if doc.get("push_url") and not self.is_school:
            self.set_push_url(doc["push_url"])
        if (doc.get("owner_pw") or {}).get("hash") and not self.is_school:
            global OWNER_PW
            self.s.set("owner_pw_salt", doc["owner_pw"].get("salt", ""))
            self.s.set("owner_pw_hash", doc["owner_pw"]["hash"])
            OWNER_PW = {"salt": doc["owner_pw"].get("salt", ""), "hash": doc["owner_pw"]["hash"]}
        self.s.set("token", tok)
        self.s.set("owner", owner)
        self.s.set("owner_lock", (doc.get("owner_lock") or owner).lower())
        self.s.set("branch", doc.get("branch", "main"))
        self.log(f"✔ Set-up imported: website {self.site_url}")
        return True

    def set_push_url(self, url: str) -> str:
        """Owner: the link of the lesson-reminder service (Cloudflare Worker)."""
        global PUSH_URL
        url = (url or "").strip().rstrip("/")
        if url and not re.match(r"^https://[A-Za-z0-9.-]+(/[A-Za-z0-9._~/-]*)?$", url):
            raise PublishError("The reminder service link must start with https:// (copy it from Cloudflare).")
        if url:
            try:
                r = requests.get(url + "/health", timeout=20)
                ok = r.status_code == 200 and r.json().get("service", "").startswith("prepfix-reminders")
            except Exception:
                ok = False
            if not ok:
                raise PublishError("That link is not answering as the PREPFIX reminder service. Check the steps in "
                                   "SETUP GUIDE.html (Part E) and try again.")
        self.s.set("push_url", url)
        PUSH_URL = url
        return url

    # ---- TOOLKIT PASSWORD (Cyrus's own PREPFIX): to open it, and for delete / suspend / restore / send to phones ----
    def _tk_hash(self, pw, salt):
        return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), 150000).hex()

    def has_tk_password(self) -> bool:
        return bool(self.s.get("tk_pw_hash"))

    def set_tk_password(self, pw: str):
        if len(pw or "") < 4:
            raise PublishError("Choose a password of at least 4 characters.")
        salt = secrets.token_hex(16)
        self.s.set("tk_pw_salt", salt)
        self.s.set("tk_pw_hash", self._tk_hash(pw, salt))

    def reset_code(self, code=None, day=None) -> str:
        """A one-day code Cyrus gives a school that forgot its PREPFIX password (made from the school's key)."""
        k = (self.licence or {}).get("skey") if self.is_school else self.school_key(code)
        if not k:
            return ""
        day = day or time.strftime("%Y-%m-%d")
        return hashlib.sha256(f"{k}|reset|{day}".encode()).hexdigest()[:6].upper()

    def reset_code_ok(self, typed: str) -> bool:
        t = (typed or "").strip().upper()
        days = [time.strftime("%Y-%m-%d"), time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))]
        return bool(t) and any(t == self.reset_code(day=d) for d in days)

    def check_tk_password(self, pw: str) -> bool:
        h, salt = self.s.get("tk_pw_hash"), self.s.get("tk_pw_salt")
        return bool(h and salt and pw) and hmac.compare_digest(self._tk_hash(pw, salt), h)

    def set_owner_password(self, pw: str) -> bool:
        """Owner: the private password that turns on 'owner mode' in the app (open every school). Only a scrambled
        copy (salt + SHA-256) goes into the app files. Empty = switch owner mode off."""
        global OWNER_PW
        if self.is_school:
            raise PublishError("Only the owner can set the owner password.")
        pw = pw or ""
        if not pw:
            for k in ("owner_pw_salt", "owner_pw_hash"):
                self.s.set(k, "")
            OWNER_PW = {}
            return False
        if len(pw) < 6:
            raise PublishError("Choose a password of at least 6 characters.")
        salt = secrets.token_hex(8)
        h = hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
        self.s.set("owner_pw_salt", salt)
        self.s.set("owner_pw_hash", h)
        OWNER_PW = {"salt": salt, "hash": h}
        return True

    def signing_key(self) -> dict:
        k = self.s.get("sign_key")
        if not k:
            try:
                r = requests.get(f"{self.site_url}/{LICENCE_KEY_PATH}", params={"t": int(time.time())}, timeout=30)
                exists = r.status_code == 200
            except Exception:
                raise PublishError("No internet connection. Connect and try again.")
            if exists:
                raise PublishError("Your licence key is in your saved folder. Import your saved folder first (Setup "
                                   "tab); a new key would stop the school copies you already gave out.")
            self.log("Creating your licence key (one time, a few seconds)…")
            k = ireri_licence.new_key()
            self.s.set("sign_key", k)
        return k

    @staticmethod
    def copy_folder_name(name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9 .-]+", "", name).strip()[:60]
        return f"PREPFIX - {safe}"

    def copy_path(self, sch) -> Path:
        """Where this school's own copy lives on this computer (FOR_SCHOOLS)."""
        return FOR_SCHOOLS_DIR / self.copy_folder_name(sch["name"])

    def has_copy(self, sch) -> bool:
        cp = self.copy_path(sch)
        return (cp / "program" / LICENCE_FILE).is_file() or (cp / LICENCE_FILE).is_file()

    def make_school_copy(self, code: str, github: str = "", dest=None) -> Path:
        """Owner only: the school's own copy of PREPFIX, licensed to ONE registered school. It works on the school's
        computer at once (import, check, fix, preview, print). The school's GitHub account is optional: it is only
        needed for teachers' phones, and can be linked later (Allow mobile app)."""
        if self.is_school:
            raise PublishError("Only Cyrus Ireri can make school copies.")
        if not self.ready:
            raise PublishError("Finish the Setup first.")
        github = (github or "").strip().lstrip("@").lower()
        if github and not GITHUB_NAME.match(github):
            raise PublishError("Type the school's GitHub username (letters, numbers and dashes only).")
        if github and github in [o.lower() for o in LOCKED_GITHUB_OWNERS]:
            raise PublishError("That is your own account. Leave it empty: you publish for this school on your website.")
        mine = list(self.s.get("schools", []))
        sch = next((x for x in mine if x["code"] == code), None)
        if not sch:
            raise PublishError("Register the school first.")
        if github:
            if sch.get("github") and sch["github"].lower() != github:
                raise PublishError(f"{sch['name']} is already linked to the GitHub account “{sch['github']}”. "
                                   "That cannot be changed.")
            others = [x for x in mine if x["code"] != code and (x.get("github") or "").lower() == github]
            if others:
                raise PublishError(f"The GitHub account “{github}” already belongs to {others[0]['name']}.")
            new_link = not sch.get("github")
            sch.update({"github": github, "site": f"https://{github}.github.io"})
        else:
            new_link = False
        github = sch.get("github", "") or ""
        site = sch.get("site", "") if github else ""
        key = self.signing_key()
        lic = ireri_licence.sign({"v": 1, "code": sch["code"], "name": sch["name"], "github": github, "site": site,
                                  "registered": sch.get("registered", ""), "issued": now_iso(),
                                  "owner_site": OWNER_SITE or self.site_url, "push": self.s.get("push_url", ""),
                                  "brand": LOCKED_BRAND, "contact": LOCKED_CONTACT,
                                  **({"lock": self.lock_key(sch["code"])} if self.lock_key(sch["code"]) else {}),
                                  **({"skey": self.school_key(sch["code"])} if self.school_manages(sch["code"]) else {})}, key)
        dest = Path(dest) if dest else FOR_SCHOOLS_DIR
        root = dest / self.copy_folder_name(sch["name"])
        old = (sch.get("copy") or {}).get("folder")
        if dest == FOR_SCHOOLS_DIR and old and old != root.name and (dest / old).is_dir() and not root.exists():
            (dest / old).rename(root)                     # the school was renamed: its folder follows
        if dest == FOR_SCHOOLS_DIR:
            sch["copy"] = {"made": now_iso(), "folder": root.name}
        self.s.set("schools", mine)
        files = {}
        if not self.s.get("key_live") or new_link:
            files[LICENCE_KEY_PATH] = json.dumps(ireri_licence.public(key), indent=1).encode()
        if new_link:
            files["schools.json"] = self.build_directory(event=("licensed", sch, {"name": f"own account: {github}"}))
        if files:
            self.log("Publishing your licence key" + (" and the school's link" if new_link else "") + " on your website…")
            self._upload(files, f"Licence for {sch['name']}")
            self.s.set("key_live", True)
        root.mkdir(parents=True, exist_ok=True)
        # A TIDY FOLDER for the school: only "Start PREPFIX" and "HOW TO USE" on top; the program sits in "program"
        prog = root / "program"
        prog.mkdir(exist_ok=True)
        keep_top = {"Start PREPFIX.bat", "HOW TO USE.html", "program"}
        for item in list(root.iterdir()):                  # a copy made before: its files move into "program"
            if item.name in keep_top:
                continue
            target = prog / item.name
            try:
                if target.exists():
                    if item.is_dir():
                        shutil.copytree(item, target, dirs_exist_ok=True)
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink()
                else:
                    shutil.move(str(item), str(target))
            except OSError:
                pass
        for f in PACKAGE_FILES:
            if f in ("SETUP GUIDE.html", "README.txt"):     # those are Cyrus's own notes; schools get a short guide
                continue
            if (APP_DIR / f).is_file():
                shutil.copyfile(APP_DIR / f, prog / f)
        (root / "Start PREPFIX.bat").write_bytes(
            b'@echo off\r\nrem PREPFIX Timetable Toolkit - double-click this file (or the PREPFIX icon on the desktop).\r\n'
            b'rem The program itself is in the "program" folder: nothing there needs to be opened.\r\n'
            b'call "%~dp0program\\Start PREPFIX.bat"\r\n')
        (root / "HOW TO USE.html").write_text(SCHOOL_GUIDE.replace("__SCHOOL__", html.escape(sch["name"]))
                                              .replace("__GITHUB__", html.escape(github or "linked by Cyrus Ireri")),
                                              "utf-8")
        shutil.copytree(TEACHER_APP_DIR, prog / "teacher_app", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("owner"))   # the owner app stays with Cyrus Ireri
        if (APP_DIR / "helpers").is_dir():                 # Python helpers: a school laptop needs no internet for them
            shutil.copytree(APP_DIR / "helpers", prog / "helpers", dirs_exist_ok=True)
        (prog / LICENCE_FILE).write_text(json.dumps(lic, indent=2, ensure_ascii=False), "utf-8")
        old_lic = prog / OLD_LICENCE_FILE
        if old_lic.is_file():
            old_lic.unlink()                               # replaced by the licence just written
        self.autosave()
        self.log(f"✔ PREPFIX copy for {sch['name']} ready: {root}")
        return root

    def ensure_locks(self) -> int:
        """Owner: every school is locked to the teachers it registers (V1: always). A school that was not yet locked
        gets its key now, and its copy in FOR_SCHOOLS is remade so the copy carries the key."""
        if self.is_school or not self.ready:
            return 0
        mine, keys, n = list(self.s.get("schools", [])), dict(self.s.get("lock_keys", {}) or {}), 0
        changed = []
        for sch in mine:
            if sch.get("lock") and keys.get(sch["code"]) and sch.get("mobile"):
                continue
            sch["lock"] = True
            sch["mobile"] = True                         # V1: every school's teachers use the phone app
            keys.setdefault(sch["code"], LOCK.new_key())
            changed.append(sch)
        if not changed:
            return 0
        self.s.set("lock_keys", keys)
        self.s.set("schools", mine)
        for sch in changed:
            if self.has_copy(sch):
                try:
                    self.make_school_copy(sch["code"], sch.get("github", ""))
                    n += 1
                except PublishError as e:
                    self.log(f"  ! {sch['name']}: {e}")
        self.autosave()
        return len(changed)

    def publish_lock_state(self, code):
        """School copy: put its timetables on the website again, locked with the school's key (after the teachers'
        list is saved, so only those teachers can open them)."""
        sch = self.school(code)
        if not sch:
            return ""
        tts, files = self.timetables(code), {}
        for t in tts:
            cur = DATA_DIR / "history" / code / t["id"] / "current.json"
            if cur.exists():
                files[f"s/{code}/t/{t['id']}/data.json"] = self.web_doc(code, cur.read_bytes())
        files[f"s/{code}/meta.json"] = compact_json(school_meta(sch, tts))
        return self._upload(files, f"Lock {sch['name']} to its teachers")

    def ensure_school_copies(self) -> int:
        """Owner: every registered school has its own copy in FOR_SCHOOLS (made the moment it is registered)."""
        if self.is_school or not self.ready:
            return 0
        n = 0
        for sch in self.schools():
            cp = self.copy_path(sch)
            if self.has_copy(sch) and (cp / "program").is_dir():
                continue                                  # (a copy in the old, untidy layout is made again, tidy)
            try:
                self.make_school_copy(sch["code"], sch.get("github", ""))
                n += 1
            except PublishError as e:
                self.log(f"  ! No copy made for {sch['name']}: {e}")
                break
        return n

    def refresh_school_sites(self) -> int:
        """Owner: read the latest public details of schools that publish on their own GitHub account."""
        mine = list(self.s.get("schools", []))
        n = 0
        for sch in mine:
            if not sch.get("site") or self.same_site(sch["site"]):
                continue
            try:
                r = requests.get(f"{sch['site']}/s/{sch['code']}/meta.json", params={"t": int(time.time())}, timeout=20)
                if r.status_code != 200:
                    continue
                m = r.json()
            except Exception:
                continue
            sch["remote"] = {"updated": m.get("updated", ""), "institution": m.get("institution", ""),
                             "timetables": [t.get("name") for t in m.get("timetables", [])],
                             "teachers": max([t.get("teachers") or 0 for t in m.get("timetables", [])] or [0]),
                             "classes": max([t.get("classes") or 0 for t in m.get("timetables", [])] or [0]),
                             "count": sum(t.get("count", 1) for t in m.get("timetables", []))}
            n += 1
        self.s.set("schools", mine)
        if n:
            self._upload({"schools.json": self.build_directory()}, "Refresh schools on their own websites")
        return n

    def import_folder(self, folder) -> dict:
        """Setup by import: restores the private set-up (if present) and every school and timetable."""
        folder = Path(folder)
        res = {"setup": False, "schools": 0, "site": None}
        sf = folder / SETUP_FILE
        if not sf.is_file() and (folder / OLD_SETUP_FILE).is_file():
            sf = folder / OLD_SETUP_FILE
        if not sf.is_file():
            hits = sorted(list(folder.rglob(SETUP_FILE)) + list(folder.rglob(OLD_SETUP_FILE)), key=lambda p: p.stat().st_mtime)
            sf = hits[-1] if hits else None
        if sf and sf.is_file():
            res["setup"] = self.import_setup_file(sf)
        site = self._find_site(folder)
        if site:
            res["schools"] = self.load_from_folder(site)
            res["site"] = str(site)
        elif not res["setup"]:
            raise PublishError("Nothing to import in that folder. Choose the folder you saved with "
                               "'Save my folder' (it has prepfix-setup.json and a folder called site), or an "
                               "older 'timetable-site' folder.")
        self.s.set("save_folder", str(folder))
        return res

    # ---- SCHOOL COPIES UPDATE THEMSELVES: Cyrus puts the newest program on his website, signed with his private key ----
    PROGRAM_DIR = "prepfix-program"

    def _program_files(self) -> dict:
        """{path: bytes} of the program a school copy runs (never data, licence or Cyrus's own notes)."""
        out = {}
        for f in PACKAGE_FILES:
            if f in ("SETUP GUIDE.html", "README.txt"):
                continue
            if (APP_DIR / f).is_file():
                out[f] = (APP_DIR / f).read_bytes()
        out["HOW TO USE.html"] = SCHOOL_GUIDE.replace("__SCHOOL__", "PREPFIX Timetable Toolkit V1").replace(
            "__GITHUB__", "").encode("utf-8")
        for fp in TEACHER_APP_DIR.rglob("*"):
            rel = fp.relative_to(TEACHER_APP_DIR).as_posix()
            if fp.is_file() and not rel.startswith("owner/"):
                out["teacher_app/" + rel] = fp.read_bytes()
        return out

    def publish_program(self) -> str:
        """Owner: put the newest PREPFIX program on the website for every school copy (signed by Cyrus)."""
        if self.is_school or not self.ready:
            return ""
        files = self._program_files()
        sums = {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())}
        ver = hashlib.sha256(json.dumps(sums, sort_keys=True).encode()).hexdigest()[:16]
        man = ireri_licence.sign({"v": 1, "what": "PREPFIX program", "version": ver, "made": now_iso(),
                                  "files": sums}, self.signing_key())
        up = {f"{self.PROGRAM_DIR}/{k}": v for k, v in files.items()}
        up[f"{self.PROGRAM_DIR}/manifest.json"] = json.dumps(man, indent=1).encode("utf-8")
        if not self.s.get("key_live"):
            up[LICENCE_KEY_PATH] = json.dumps(ireri_licence.public(self.signing_key()), indent=1).encode()
            self.s.set("key_live", True)
        self.log("Putting the newest PREPFIX program on your website for the schools' computers…")
        return self._upload(up, f"PREPFIX program {ver}")

    def update_program(self, log=lambda m: None) -> int:
        """School copy: if Cyrus has put a newer PREPFIX on his website (signed by him), take it. Returns the number of
        files changed (0 = already up to date, or offline). Data, licence and teachers' list are never touched."""
        if not self.is_school:
            return 0
        base = (self.licence.get("owner_site") or OWNER_SITE).rstrip("/")
        try:
            man = requests.get(f"{base}/{self.PROGRAM_DIR}/manifest.json", params={"t": int(time.time())}, timeout=20).json()
            pub = requests.get(f"{base}/{LICENCE_KEY_PATH}", params={"t": int(time.time())}, timeout=20).json()
        except Exception:
            return 0                                     # offline: open the version already here
        if not ireri_licence.verify(man, pub) or not isinstance(man.get("files"), dict):
            return 0                                     # not signed by Cyrus Ireri: ignored
        todo = []
        for rel, want in man["files"].items():
            parts = rel.split("/")
            if ".." in parts or rel.startswith("/") or parts[0] in ("prepfix_data", "helpers") or \
                    rel in (LICENCE_FILE, OLD_LICENCE_FILE) or "\\" in rel:
                continue
            fp = APP_DIR / rel
            have = hashlib.sha256(fp.read_bytes()).hexdigest() if fp.is_file() else ""
            if have != want:
                todo.append((rel, want))
        if not todo:
            return 0
        got = {}
        for rel, want in todo:
            try:
                r = requests.get(f"{base}/{self.PROGRAM_DIR}/{rel}", params={"v": man.get("version", "")}, timeout=60)
            except Exception:
                return 0
            if r.status_code != 200 or hashlib.sha256(r.content).hexdigest() != want:
                return 0                                 # incomplete or changed on the way: try again next time
            got[rel] = r.content
        for rel, data in got.items():                    # everything arrived and checked: now put it in place
            fp = APP_DIR / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            tmp = fp.with_name(fp.name + ".new")
            tmp.write_bytes(data)
            os.replace(tmp, fp)
        log(f"✔ PREPFIX updated ({len(got)} file(s)).")
        return len(got)

    def refresh_app_from_owner(self) -> str:
        """School copies: take the newest teachers' app from Cyrus Ireri's website (so improvements reach every school)."""
        global REMOTE_SHELL
        if not self.is_school:
            return ""
        base = (self.licence.get("owner_site") or OWNER_SITE).rstrip("/")
        try:
            man = requests.get(f"{base}/shell.json", params={"t": int(time.time())}, timeout=30).json()
            got = {}
            for path in man.get("files", []):
                if path in ("config.js", "schools.json", "shell.json", ".nojekyll") or path.startswith("s/"):
                    continue
                r = requests.get(f"{base}/{path}", params={"t": int(time.time())}, timeout=60)
                if r.status_code != 200:
                    raise PublishError("incomplete")
                got[path] = r.content
            js = got.get("app.js", b"").decode("utf-8", "ignore")
            if (LOCKED_BRAND not in js and "DESIGNED BY CYRUS IRERI" not in js and "CREATED BY CYRUS IRERI" not in js) \
                    or LOCKED_CONTACT not in js \
                    or "index.html" not in got:
                raise PublishError("not genuine")
            REMOTE_SHELL = got
            return man.get("build", "")
        except Exception:
            return ""                                   # offline: keep the app that came with this copy

    def sync_app_update(self) -> bool:
        """School copies: if PREPFIX has improved, put the improved teachers' app on the school's website."""
        if not (self.is_school and self.ready) or self.relay:      # relay schools use Cyrus's website: always newest
            return False
        self.verify_licence()
        if not self.refresh_app_from_owner():
            return False
        want = json.loads(shell_files()["shell.json"]).get("build", "")
        try:
            have = requests.get(f"{self.site_url}/shell.json", params={"t": int(time.time())}, timeout=30).json().get("build", "")
        except Exception:
            have = ""
        if want and want != have:
            self.log("PREPFIX has been improved — updating the teachers' app…")
            self.deploy_shell()
            return True
        return False

    def deploy_shell(self):
        files = shell_files()
        if not self.is_school:
            files.update(owner_files())
        files["schools.json"] = self.build_directory()
        for sch in self.schools():
            files.update(school_page_files(sch["code"], sch["name"]))
        self.log("Putting the teachers' app online…")
        sha = self._upload(files, "Update teachers' app")
        self.log("  ✔ App uploaded." if sha else "  ✔ App already up to date.")
        return sha

    # ---- load what is already on the website / in a saved folder -------------------------
    def _absorb(self, code, name, registered, meta, read, copy_id=""):
        """Bring one school's timetables into this computer. read(path) -> dict or None."""
        self._merge_register([{"code": code, "name": name, "copy_id": copy_id,
                               "registered": registered or (meta or {}).get("registered") or (meta or {}).get("updated", "")}])
        got = 0
        tts = (meta or {}).get("timetables")
        if tts is None and meta:                                        # v6 layout: one timetable
            doc = read(f"s/{code}/data.json")
            if doc:
                tts = [{"id": tt_id(name), "name": tt_name(name), "version": doc.get("version", ""),
                        "updated": (doc.get("school") or {}).get("updated", "")}]
                self._store_doc(code, tts[0]["id"], doc, tts[0])
                return 1
            return 0
        for t in tts or []:
            known = {x["id"]: x for x in self.timetables(code)}
            if known.get(t["id"], {}).get("version") == t.get("version"):
                continue
            doc = self.open_doc(code, read(f"s/{code}/t/{t['id']}/data.json"))
            if doc:
                self._store_doc(code, t["id"], doc, t)
                got += 1
        return got

    def _store_doc(self, code, tid, doc, entry):
        d = self._dir(code, tid)
        cur = d / "current.json"
        if cur.exists():
            shutil.copyfile(cur, d / "previous.json")
        cur.write_bytes(compact_json(doc))
        stamp = re.sub(r"[^0-9]", "", str(entry.get("updated") or now_iso()))[:14] or datetime.now().strftime("%Y%m%d%H%M%S")
        (d / f"{stamp}.json").write_bytes(compact_json(doc))
        b = doc.get("bundle", {})
        self._set_tt(code, {"id": tid, "name": entry.get("name") or (doc.get("timetable") or {}).get("name", tid.upper()),
                            "version": doc.get("version", entry.get("version", "")),
                            "updated": entry.get("updated") or (doc.get("school") or {}).get("updated", ""),
                            "note": entry.get("note", ""), "institution": b.get("institution", ""),
                            "teachers": len(b.get("teachers", [])), "classes": len(b.get("classes", [])),
                            "count": entry.get("count", 1),
                            "created": entry.get("created") or entry.get("updated") or ""})

    def load_from_website(self) -> int:
        """Bring every registered school and its timetables from the website into this computer."""
        gh = None if self.relay else self.gh()
        self.log("Loading the schools and timetables already on your website…")
        d = self.remote_directory(gh)
        entries = d.get("register") or d.get("schools", [])
        n = 0
        for e in entries:
            code = e.get("code")
            if not code or (self.is_school and code != self.bound_school["code"]):
                continue
            meta = self.remote_json(f"s/{code}/meta.json", gh)
            got = self._absorb(code, e.get("name") or (meta or {}).get("name", code), e.get("registered", ""), meta,
                               lambda p: self.remote_json(p, gh), e.get("copy_id", ""))
            n += 1
            if got:
                self.log(f"  ✔ {e.get('name', code)}: {got} timetable(s) loaded")
        self.log(f"  ✔ {n} school(s) on the website. All are now on this computer.")
        return n

    def load_from_folder(self, folder) -> int:
        """Bring schools and timetables from a folder saved earlier with 'Save site folder'."""
        folder = Path(folder)
        if (folder / "timetable-site").is_dir() and not (folder / "schools.json").exists():
            folder = folder / "timetable-site"

        def read(rel):
            p = folder / rel
            try:
                return json.loads(p.read_text("utf-8")) if p.exists() else None
            except Exception:
                return None
        d = read("schools.json")
        if d is None and not (folder / "s").is_dir():
            raise PublishError("That folder is not a saved timetable site. Choose the folder that contains "
                               "schools.json and a folder called s.")
        entries = (d or {}).get("register") or (d or {}).get("schools") or []
        known = {e.get("code") for e in entries}
        for p in sorted((folder / "s").glob("*/meta.json")):
            if p.parent.name not in known:
                m = read(f"s/{p.parent.name}/meta.json") or {}
                entries.append({"code": p.parent.name, "name": m.get("name", p.parent.name)})
        n = 0
        for e in entries:
            code = e.get("code")
            if not code or (self.is_school and code != self.bound_school["code"]):
                continue
            meta = read(f"s/{code}/meta.json")
            self._absorb(code, e.get("name") or (meta or {}).get("name", code), e.get("registered", ""), meta, read,
                         e.get("copy_id", ""))
            n += 1
        self.log(f"✔ Loaded {n} school(s) from {folder}")
        return n

    def upload_everything(self, progress=lambda p: None):
        """Put every school and every timetable this computer has onto the website."""
        files = shell_files()
        for sch in self.schools():
            files.update(school_page_files(sch["code"], sch["name"]))
            tts = self.timetables(sch["code"])
            for t in tts:
                cur = DATA_DIR / "history" / sch["code"] / t["id"] / "current.json"
                if cur.exists():
                    files[f"s/{sch['code']}/t/{t['id']}/data.json"] = self.web_doc(sch["code"], cur.read_bytes())
            files[f"s/{sch['code']}/meta.json"] = compact_json(school_meta(sch, tts))
        files["schools.json"] = self.build_directory()
        progress(40)
        sha = self._upload(files, "Upload saved timetables")
        progress(70)
        self._wait_live(sha)
        progress(100)
        return sha

    # ---- publish / undo -------------------------------------------------------------------
    def _upload(self, files, message, delete_prefixes=()):
        if self.relay:
            return self._relay_upload(files, message, delete_prefixes)
        host = self.domain.replace("https://", "").replace("http://", "").strip("/")
        if host and "CNAME" not in files:                      # keeps GitHub's custom-domain setting on every publish
            files = dict(files, CNAME=host.encode())
        return self.gh().commit_files(self.s.get("owner"), self.repo, self.branch, files, message, delete_prefixes)

    def _relay_upload(self, files, message, delete_prefixes=()):
        """School copy: send this school's files to the Google Sheet; it puts them on Cyrus Ireri's website.
        Only the school's own folder (s/<code>/) is accepted there; everything else is left out here already."""
        code = self.licence.get("code")
        pre = f"s/{code}/"
        mine = {k: v for k, v in files.items() if k.startswith(pre)}
        dels = [d for d in delete_prefixes if str(d).startswith(pre)]
        if not mine and not dels:
            return ""
        body = {"action": "ttPublish", "school": code, "skey": self.licence.get("skey"), "message": message[:120],
                "files": {k: base64.b64encode(v).decode() for k, v in mine.items()}, "del": dels}
        j, err = None, None
        for attempt in range(2):                         # one quiet retry: a slow line often works the second time
            try:
                j = self._sheet(body, timeout=180)
                break
            except requests.RequestException as e:
                err = e
        if j is None:
            try:                                         # the details stay on this computer, for Cyrus Ireri
                (DATA_DIR / "publish-problem.txt").write_text(f"{now_iso()}  {type(err).__name__}: {err}\n", encoding="utf-8")
            except Exception:
                pass
            raise PublishError("Could not reach the PREPFIX service. Check the internet and try again.")
        if j.get("error"):
            e = str(j["error"])
            raise PublishError("This copy's school key was not accepted. Contact Cyrus Ireri, " + LOCKED_CONTACT + "."
                               if e == "key" else "Publishing did not go through: " + (
                                   e if len(e) < 90 and "google" not in e.lower() and "http" not in e.lower()
                                   else "the PREPFIX service is not ready. Try again later, or call Cyrus Ireri, " + LOCKED_CONTACT + "."))
        return j.get("commit") or "relay"

    def _wait_live(self, sha):
        if not sha:
            return
        if self.relay:
            self.log("  ✔ Sent. Teachers see it within a minute or two, the next time they open the app.")
            return
        gh = self.gh()
        owner = self.s.get("owner")
        for _ in range(40):
            st = gh.pages_status(owner, self.repo)
            if st.get("status") == "built" and (st.get("commit") or "") == sha:
                self.log("  ✔ Live. Teachers will see it the next time they open the app.")
                return
            if st.get("status") == "errored" and (st.get("commit") or "") == sha:
                raise PublishError("GitHub could not switch the website on: " +
                                   str((st.get("error") or {}).get("message", "unknown reason")))
            time.sleep(6)
        self.log("  … GitHub is still busy. It will be live within a few minutes; no need to publish again.")

    def existing_timetable(self, code, name):
        tid = tt_id(name)
        return next((t for t in self.timetables(code) if t["id"] == tid), None)

    # ---- SCHOOL LOCK: only teachers registered by phone number open the timetables ---------------
    def lock_key(self, code):
        if self.is_school:
            return (self.licence or {}).get("lock") or None
        sch = self.school(code)
        return (self.s.get("lock_keys", {}) or {}).get(code) if sch and sch.get("lock") else None

    def web_doc(self, code, doc) -> bytes:
        """The timetable as it goes on the website: locked with the school's key when the school is locked."""
        if isinstance(doc, (bytes, bytearray)):
            doc = json.loads(doc.decode("utf-8"))
        key = self.lock_key(code)
        if not key or "bundle" not in doc:
            return compact_json(doc)
        out = {k: v for k, v in doc.items() if k != "bundle"}
        out["benc"] = LOCK.lock(key, doc["bundle"])
        return compact_json(out)

    def open_doc(self, code, doc):
        """A timetable read back from the website: opened if it is locked and the key is known here."""
        if not doc or "benc" not in doc:
            return doc
        keys = [self.lock_key(code), (self.s.get("lock_keys", {}) or {}).get(code)]
        for k in keys:
            if k:
                try:
                    out = {kk: v for kk, v in doc.items() if kk != "benc"}
                    out["bundle"] = LOCK.unlock(k, doc["benc"])
                    return out
                except Exception:
                    continue
        return None

    def phones(self, code) -> list:
        return [dict(x) for x in (self.s.get("phones", {}) or {}).get(code, [])]

    def set_phones(self, code, people):
        if not self.is_school and people:
            mine = list(self.s.get("schools", []))
            for x in mine:
                if x["code"] == code:
                    x["teachers_by"] = "owner"
            self.s.set("schools", mine)
        allp = dict(self.s.get("phones", {}) or {})
        allp[code] = [{"name": str(p.get("name", "")).strip(), "phone": LOCK.normalize_phone(p.get("phone")) or "",
                       "t": str(p.get("t") or "")} for p in people]
        self.s.set("phones", allp)

    def owner_key(self):
        return (self.s.get("owner_key") or "").strip()

    def school_key(self, code):
        """Owner: the key a school's own copy uses to keep ITS teachers' list on the service (and nothing else).
        Made from the owner key, so the service checks it without storing anything."""
        ok = self.owner_key()
        return hashlib.sha256(f"prepfix-school|{ok}|{code}".encode()).hexdigest()[:32] if ok else None

    def school_manages(self, code) -> bool:
        """Who keeps a school's teachers' list: the school's own copy (default), or Cyrus (schools whose list Cyrus
        already typed before school copies could do it)."""
        if self.is_school:
            return bool((self.licence or {}).get("skey"))
        sch = self.school(code) or {}
        if sch.get("teachers_by") == "owner":
            return False
        return bool(self.owner_key() and not self.phones(code))

    def _service(self, path, body):
        if self.is_school:
            url = ((self.licence or {}).get("push") or self.s.get("push_url") or "").rstrip("/")
            skey = (self.licence or {}).get("skey")
            if not url or not skey:
                raise PublishError("Teachers' sign-in is not switched on in this copy yet. Ask Cyrus Ireri, "
                                   + LOCKED_CONTACT + ", for an updated copy.")
            auth = {"skey": skey, "school": self.licence.get("code")}   # a school copy speaks for its school only
        else:
            url = (self.s.get("push_url") or "").rstrip("/")
            if not url:
                raise PublishError("The PREPFIX service link is not set yet: Setup → “Lesson reminders service” "
                                   "(see SETUP GUIDE.html, Part E).")
            if not self.owner_key():
                raise PublishError("Type your owner key first (Setup → the same password as OWNER_KEY in Cloudflare).")
            auth = {"key": self.owner_key()}
        try:
            r = requests.post(url + path, json=dict(body, **auth), timeout=25)
        except requests.RequestException as e:
            raise PublishError(f"Could not reach the PREPFIX service ({e}). Check the internet.")
        if r.status_code == 404 and path != "/join":
            raise PublishError("The PREPFIX service is an older version. In Cloudflare, paste the new worker.js "
                               "(reminder_service folder) and Deploy, then try again.")
        if r.status_code == 403:
            raise PublishError("This copy's sign-in key was not accepted. Ask Cyrus Ireri, " + LOCKED_CONTACT +
                               ", for an updated copy." if self.is_school else
                               "The owner key is not the same as OWNER_KEY in Cloudflare.")
        try:
            j = r.json()
        except ValueError:
            raise PublishError(f"The PREPFIX service answered {r.status_code}.")
        if not j.get("ok"):
            raise PublishError(f"The PREPFIX service said: {j.get('error', r.status_code)}")
        return j

    def _not_suspended(self):
        me = self.owner_entry() if self.is_school else None
        if (me or {}).get("suspended"):
            raise PublishError("This school's PREPFIX service is SUSPENDED. Contact Cyrus Ireri, " + LOCKED_CONTACT + ".")
        if me and (days_left(sub_until(me)) or 0) < 0:
            raise PublishError(f"This school's PREPFIX subscription ended on {nice_day(sub_until(me))}. To renew, "
                               f"contact Cyrus Ireri, {LOCKED_CONTACT}.")

    def free_signin(self, code, phs):
        """Remove sign-ins only (the list itself is not touched). phs: number codes (ph)."""
        self._not_suspended()
        return self._service("/roster", {"school": code, "only_free": True, "free": list(phs)})

    def send_roster(self, code, free=()):
        """Send the school's list (names + a code made from each number - never the number) and its key."""
        self._not_suspended()
        sch = self.school(code)
        key = self.lock_key(code) if self.is_school else (self.s.get("lock_keys", {}) or {}).get(code)
        people = [{"ph": LOCK.phone_hash(code, p["phone"]), "name": p["name"], "t": p.get("t", ""),
                   "pinh": None}                       # members make their own PIN when they sign in
                  for p in self.phones(code) if p.get("phone")]
        return self._service("/roster", {"school": code, "name": sch["name"], "lockkey": key, "people": people,
                                         "free": [LOCK.phone_hash(code, f) for f in free]})

    def roster_people(self, code) -> list:
        """Owner: the list as the school's own copy keeps it on the service (names and sign-ins; no numbers)."""
        return self._service("/roster-status", {"school": code}).get("people", [])

    def roster_status(self, code) -> dict:
        """{normalized phone: {joined, plat, first, last}}"""
        j = self._service("/roster-status", {"school": code})
        by = {x["ph"]: x for x in j.get("people", [])}
        return {p["phone"]: by.get(LOCK.phone_hash(code, p["phone"]), {}) for p in self.phones(code) if p.get("phone")}

    def set_lock(self, code, on: bool, progress=lambda p: None, rekey=False):
        """Lock / unlock a school: its timetables are put on the website again, locked or open.
        rekey: a NEW school key - every phone must type its number again (e.g. after a teacher left)."""
        if self.is_school:
            raise PublishError("Only Cyrus Ireri's edition locks schools.")
        mine = list(self.s.get("schools", []))
        sch = next((x for x in mine if x["code"] == code), None)
        if not sch:
            raise PublishError("Choose a registered school first.")
        if on:
            if not any(p.get("phone") for p in self.phones(code)):
                raise PublishError("Add the teachers and their phone numbers first.")
            keys = dict(self.s.get("lock_keys", {}) or {})
            if rekey or code not in keys:
                keys[code] = LOCK.new_key()
            self.s.set("lock_keys", keys)
            sch["lock"] = True
            self.s.set("schools", mine)
            try:
                self.send_roster(code, free=[p["phone"] for p in self.phones(code) if p.get("phone")] if rekey else ())
            except Exception:
                sch["lock"] = False
                self.s.set("schools", mine)
                raise
        else:
            sch["lock"] = False
            self.s.set("schools", mine)
            try:
                self._service("/roster", {"school": code, "off": True})
            except PublishError as e:
                self.log(f"  (the service was not told: {e})")
        progress(30)
        files = {}
        tts = self.timetables(code)
        for t in tts:
            cur = DATA_DIR / "history" / code / t["id"] / "current.json"
            if cur.exists():
                files[f"s/{code}/t/{t['id']}/data.json"] = self.web_doc(code, cur.read_bytes())
        files[f"s/{code}/meta.json"] = compact_json(school_meta(sch, tts))
        if tts:
            self.log(("Locking" if on else "Opening") + f" {sch['name']}'s timetables on the website…")
            sha = self._upload(files, f"{'Lock' if on else 'Unlock'} {sch['name']}")
            self._wait_live(sha)
        try:
            if self.has_copy(sch):
                self.make_school_copy(code)                      # the school's own copy keeps the lock too
        except Exception as e:
            self.log(f"  (the school copy was not remade: {e})")
        self.autosave()
        progress(100)
        return sch

    def publish(self, code: str, timetable_name: str, data: dict, note: str, progress=lambda p: None) -> dict:
        check_brand_files()
        sch = self.school(code)
        if not sch:
            raise PublishError("Choose a registered school first.")
        if self.is_school:
            self.verify_licence()
            self.check_mobile_allowed()
            self.refresh_app_from_owner()
        elif sch.get("suspended"):
            raise PublishError(f"{sch['name']} is SUSPENDED. Restore it on the Schools tab first.")
        elif not self.mobile_on(sch):
            raise PublishError(f"{sch['name']} is PC ONLY: the mobile app is not allowed for it, so nothing is sent to "
                               "phones. Preview and print on this computer instead, or allow the mobile app on the "
                               "Schools tab (📱 Allow mobile app) and publish again.")
        elif self.own_account(sch):
            raise PublishError(f"{sch['name']} publishes for itself on its own GitHub account ({sch['github']}). "
                               "Publish from the school's copy.")
        tname = tt_name(timetable_name)
        if len(tname) < 2:
            raise PublishError("Type a name for this timetable (for example KIANDERI or END TERM EXAM).")
        tid = tt_id(tname)
        old = self.existing_timetable(code, tname)
        version = make_version()
        data = dict(data)
        data.pop("institutions", None)
        data.pop("_lessons", None)
        data.pop("_unplaced", None)
        data["published"] = now_iso()
        entry = {"id": tid, "name": tname, "version": version, "updated": data["published"], "note": (note or "").strip(),
                 "institution": data.get("institution", ""), "teachers": len(data.get("teachers", [])),
                 "classes": len(data.get("classes", [])), "count": (old or {}).get("count", 0) + 1,
                 "created": (old or {}).get("created") or (old or {}).get("updated") or data["published"]}
        school = {"name": sch["name"], "institution": entry["institution"], "note": entry["note"],
                  "teachers": entry["teachers"], "classes": entry["classes"], "updated": entry["updated"],
                  "footer": LOCKED_BRAND, "contact": LOCKED_CONTACT}
        doc = {"version": version, "school": school, "timetable": {"id": tid, "name": tname}, "bundle": data}
        progress(10)
        tts = [t for t in self.timetables(code) if t["id"] != tid] + [entry]
        files = dict(shell_files())
        files.update(school_page_files(code, sch["name"]))
        files[f"s/{code}/t/{tid}/data.json"] = self.web_doc(code, doc)      # locked when the school is locked
        files[f"s/{code}/meta.json"] = compact_json(school_meta(sch, tts))
        self._set_tt(code, entry)                                     # so schools.json lists it
        try:
            files["schools.json"] = self.build_directory(event=("replaced" if old else "published", sch, entry))
            progress(30)
            self.log(f"Uploading “{tname}” for {sch['name']}…")
            sha = self._upload(files, f"{'Replace' if old else 'Add'} {tname} timetable for {sch['name']}")
        except Exception:
            if old:
                self._set_tt(code, old)
            else:
                idx = dict(self.s.get("timetables", {}))
                idx[code] = [t for t in idx.get(code, []) if t["id"] != tid]
                self.s.set("timetables", idx)
            raise
        progress(70)
        self._store_doc(code, tid, doc, entry)
        self.log("  ✔ Uploaded. Waiting for the website to switch over…")
        self._wait_live(sha)
        self.autosave()
        self.sheet_backup(code, tid, doc, "replaced" if old else "published", entry.get("note", ""))
        progress(100)
        return {"link": self.school_link(code), "version": version, "commit": sha, "replaced": bool(old),
                "timetable": tname}

    def can_undo(self, code: str, tid: str) -> bool:
        return (DATA_DIR / "history" / code / tid / "previous.json").exists()

    def undo(self, code: str, tid: str, progress=lambda p: None) -> dict:
        sch = self.school(code)
        d = self._dir(code, tid)
        prev, cur = d / "previous.json", d / "current.json"
        if not prev.exists() or not cur.exists():
            raise PublishError("There is no earlier version of this timetable to go back to.")
        doc = json.loads(prev.read_text("utf-8"))
        doc["version"] = make_version()
        old = next((t for t in self.timetables(code) if t["id"] == tid), {})
        b = doc.get("bundle", {})
        entry = dict(old, version=doc["version"], updated=now_iso(), note=(doc.get("school") or {}).get("note", ""),
                     teachers=len(b.get("teachers", [])), classes=len(b.get("classes", [])))
        tts = [t for t in self.timetables(code) if t["id"] != tid] + [entry]
        files = {f"s/{code}/t/{tid}/data.json": self.web_doc(code, doc),
                 f"s/{code}/meta.json": compact_json(school_meta(sch, tts))}
        self._set_tt(code, entry)
        files["schools.json"] = self.build_directory(event=("restored", sch, entry))
        progress(30)
        sha = self._upload(files, f"Restore earlier {entry.get('name', tid)} for {sch['name']}")
        newer = cur.read_bytes()
        cur.write_bytes(compact_json(doc))
        prev.write_bytes(newer)
        self._wait_live(sha)
        self.autosave()
        self.sheet_backup(code, tid, doc, "put back (undo)")
        progress(100)
        return {"link": self.school_link(code), "version": doc["version"], "commit": sha}

    def delete_timetable(self, code: str, tid: str, progress=lambda p: None) -> dict:
        """Remove one published timetable of a school from the website (so from teachers' phones too). The school's
        other timetables stay. Its history stays on this computer (moved to history/<code>/deleted-<tid>-<time>)."""
        sch = self.school(code)
        if not sch:
            raise PublishError("Choose a registered school first.")
        if self.is_school:
            self.verify_licence()
        old = next((t for t in self.timetables(code) if t["id"] == tid), None)
        if not old:
            raise PublishError("That timetable is not published.")
        tts = [t for t in self.timetables(code) if t["id"] != tid]
        idx = dict(self.s.get("timetables", {}))
        idx[code] = tts
        self.s.set("timetables", idx)
        try:
            files = {f"s/{code}/meta.json": compact_json(school_meta(sch, tts)),
                     "schools.json": self.build_directory(event=("deleted", sch, old))}
            progress(30)
            self.log(f"Deleting “{old['name']}” of {sch['name']} from the website…")
            sha = self._upload(files, f"Delete {old['name']} timetable of {sch['name']}",
                               delete_prefixes=(f"s/{code}/t/{tid}/",))
        except Exception:
            idx = dict(self.s.get("timetables", {}))
            idx[code] = [t for t in idx.get(code, []) if t["id"] != tid] + [old]
            self.s.set("timetables", idx)
            raise
        progress(70)
        try:                                                  # keep the history, out of the way
            d = DATA_DIR / "history" / code / tid
            if d.exists():
                d.rename(d.with_name(f"deleted-{tid}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"))
        except OSError:
            pass
        if sha:
            self._wait_live(sha)
        self.autosave()
        try:                                                  # the Google Sheet keeps its copies; it only notes the deletion
            auth = self._sheet_auth(code)
            if auth:
                self._sheet(dict(auth, action="ttDeleted", school=code, schoolName=sch.get("name", ""), name=old["name"]), 20)
        except Exception:
            pass
        progress(100)
        return {"commit": sha, "timetable": old["name"]}

    # ---- GOOGLE SHEET BACKUP ----------------------------------------------------------------
    # Every timetable put on the website is also kept in Cyrus's Google Sheet (tab "TT <school code>", the newest
    # 25 versions of each timetable; tab "Timetables" lists them all). Cyrus's PREPFIX uses the owner key; a school
    # copy uses its own school key and can only save / read its own school. A backup problem never stops a publish.
    def _sheet_auth(self, code):
        if self.is_school:
            lic = self.licence or {}
            return {"skey": lic["skey"]} if lic.get("skey") and lic.get("code") == code else None
        ok = self.owner_key()
        return {"key": ok} if ok else None

    def _sheet(self, body, timeout=60):
        url = (self.s.get("sheet_url") or SHEET_URL).strip()
        r = requests.post(url, data=json.dumps(body).encode("utf-8"), timeout=timeout,
                          headers={"Content-Type": "text/plain;charset=utf-8"})
        try:
            return r.json()
        except ValueError:
            return {"error": f"the Google Sheet answered {r.status_code}"}

    def sheet_link_website(self) -> bool:
        """Owner: tell the Google Sheet how to put school copies' timetables on this website (the GitHub key stays in
        the sheet's private Script properties, which only Cyrus can see). Done quietly at every start."""
        if self.is_school or not (self.s.get("token") and self.s.get("owner") and self.owner_key()):
            return False
        try:
            j = self._sheet({"action": "ttSite", "key": self.owner_key(), "school": "owner", "token": self.s.get("token"),
                             "owner": self.s.get("owner"), "repo": self.repo, "branch": self.branch}, timeout=40)
            return bool(j.get("ok"))
        except Exception:
            return False

    # ---- SCHOOLS USING FET: Cyrus's list, shown in the teachers' app (teacher_app/fet_schools.json) ------------
    def fet_schools(self) -> list:
        try:
            return list(json.loads((TEACHER_APP_DIR / "fet_schools.json").read_text("utf-8")).get("schools", []))
        except Exception:
            return []

    def set_fet_schools(self, names) -> int:
        if self.is_school:
            raise PublishError("Only Cyrus Ireri keeps this list.")
        seen, out = set(), []
        for n in names:
            n = " ".join(str(n).split()).strip()
            if n and n.lower() not in seen:
                seen.add(n.lower())
                out.append(n)
        p = TEACHER_APP_DIR / "fet_schools.json"
        try:
            doc = json.loads(p.read_text("utf-8"))
        except Exception:
            doc = {}
        doc.update({"title": "Schools using FET Timetable Program", "schools": out,
                    "note": "Kept by Cyrus Ireri in PREPFIX (Schools tab -> Schools using FET). Teachers see it in the app."})
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
        return len(out)

    def sheet_backup(self, code, tid, doc, what="published", note="", quiet=False) -> bool:
        try:
            auth = self._sheet_auth(code)
            if not auth:
                if not quiet:
                    self.log("  ☁ Not saved in the Google Sheet: " + ("this copy has no school key (ask Cyrus for an updated copy)."
                             if self.is_school else "type your owner key in Setup first."))
                return False
            sch = self.school(code) or {}
            b = doc.get("bundle", {})
            body = dict(auth, action="ttBackup", school=code, schoolName=sch.get("name", ""), tid=tid,
                        name=(doc.get("timetable") or {}).get("name", tid.upper()), version=doc.get("version", ""),
                        what=what, note=note or (doc.get("school") or {}).get("note", ""), computer=platform.node()[:40],
                        info={"teachers": len(b.get("teachers", [])), "classes": len(b.get("classes", []))},
                        data=base64.b64encode(gzip.compress(compact_json(doc))).decode("ascii"))
            j = self._sheet(body)
            if j.get("ok"):
                done = dict(self.s.get("sheet_done", {}))
                done[f"{code}/{tid}"] = doc.get("version", "")
                self.s.set("sheet_done", done)
                if not quiet:
                    self.log(f"  ☁ Also saved in your Google Sheet ({j.get('kept', 1)} version(s) of this timetable kept there).")
                return True
            e = j.get("error", "")
            self.log("  ⚠ Google Sheet backup: " + ("the owner key in Setup is not the same as OWNER_KEY in the Google Sheet."
                     if e == "key" and not self.is_school else "this copy's school key was not accepted." if e == "key" else str(e)))
        except Exception as e:
            self.log(f"  ⚠ Not saved in the Google Sheet now (no internet?). It is tried again the next time PREPFIX opens.")
        return False

    def sheet_backup_all(self) -> int:
        """Timetables not yet in the Google Sheet (published before this version, or while offline) are sent now."""
        done, n = self.s.get("sheet_done", {}), 0
        for sch in self.schools():
            code = sch.get("code")
            if not code or not self._sheet_auth(code):
                continue
            for t in self.timetables(code):
                cur = DATA_DIR / "history" / code / t["id"] / "current.json"
                if not cur.exists():
                    continue
                try:
                    doc = json.loads(cur.read_text("utf-8"))
                except (OSError, ValueError):
                    continue
                if done.get(f"{code}/{t['id']}") == doc.get("version", ""):
                    continue
                if self.sheet_backup(code, t["id"], doc, "backup", quiet=True):
                    n += 1
        return n

    def sheet_versions(self, code) -> list:
        auth = self._sheet_auth(code)
        if not auth:
            raise PublishError("Type your owner key in Setup first." if not self.is_school else
                               "This copy has no school key. Ask Cyrus Ireri, " + LOCKED_CONTACT + ", for an updated copy.")
        try:
            j = self._sheet(dict(auth, action="ttList", school=code))
        except requests.RequestException:
            raise PublishError("Could not reach the Google Sheet. Check the internet.")
        if not j.get("ok"):
            raise PublishError("The Google Sheet said: " + ("the key was not accepted." if j.get("error") == "key" else str(j.get("error"))))
        return j.get("versions", [])

    def restore_from_sheet(self, code: str, tid: str, version: str, progress=lambda p: None) -> dict:
        """Put a version kept in the Google Sheet back on the website (and on teachers' phones)."""
        sch = self.school(code)
        if not sch:
            raise PublishError("Choose a registered school first.")
        auth = self._sheet_auth(code)
        j = self._sheet(dict(auth or {}, action="ttGet", school=code, tid=tid, version=version))
        if not j.get("ok"):
            raise PublishError("The Google Sheet said: " + str(j.get("error")))
        doc = json.loads(gzip.decompress(base64.b64decode(j["data"])).decode("utf-8"))
        progress(20)
        doc["version"] = make_version()
        old = next((t for t in self.timetables(code) if t["id"] == tid), {}) or {"id": tid, "name": j.get("name") or tid.upper()}
        b = doc.get("bundle", {})
        entry = dict(old, version=doc["version"], updated=now_iso(), note=(doc.get("school") or {}).get("note", ""),
                     teachers=len(b.get("teachers", [])), classes=len(b.get("classes", [])))
        tts = [t for t in self.timetables(code) if t["id"] != tid] + [entry]
        files = {f"s/{code}/t/{tid}/data.json": self.web_doc(code, doc),
                 f"s/{code}/meta.json": compact_json(school_meta(sch, tts))}
        self._set_tt(code, entry)
        files["schools.json"] = self.build_directory(event=("restored", sch, entry))
        progress(40)
        sha = self._upload(files, f"Restore {entry.get('name', tid)} for {sch['name']} from the Google Sheet")
        self._store_doc(code, tid, doc, entry)
        self._wait_live(sha)
        self.autosave()
        self.sheet_backup(code, tid, doc, "restored from the sheet")
        progress(100)
        return {"link": self.school_link(code), "version": doc["version"], "timetable": entry.get("name", tid)}

    # ---- a ready-to-upload / back-up folder ------------------------------------------------
    def export_site(self, dest: Path) -> int:
        dest = Path(dest)
        files = dict(shell_files())
        n = 0
        for sch in self.schools():
            files.update(school_page_files(sch["code"], sch["name"]))
            tts = self.timetables(sch["code"])
            for t in tts:
                cur = DATA_DIR / "history" / sch["code"] / t["id"] / "current.json"
                if cur.exists():
                    files[f"s/{sch['code']}/t/{t['id']}/data.json"] = self.web_doc(sch["code"], cur.read_bytes())
            files[f"s/{sch['code']}/meta.json"] = compact_json(school_meta(sch, tts))
            n += 1
        try:
            files["schools.json"] = self.build_directory()
        except PublishError:
            files["schools.json"] = compact_json({"updated": now_iso(), "activity": [],
                                                  "schools": [{"code": s["code"], "name": s["name"],
                                                               "registered": s.get("registered", ""),
                                                               "timetables": [t["name"] for t in self.timetables(s["code"])]}
                                                              for s in self.schools()],
                                                  "register": [{"code": s["code"], "name": s["name"],
                                                                "registered": s.get("registered", "")}
                                                               for s in self.schools()]})
        for rel, data in files.items():
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return n
