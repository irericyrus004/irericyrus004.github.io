"""
Reads a FET timetable export folder into structured data for the teachers' app.

Files used (anything else is ignored):
  *_groups_days_vertical.html      -> Classes
  *_teachers_days_vertical.html    -> Teachers
  *_subgroups_days_vertical.html   -> Master timetable (shown day by day)
  *_rooms_days_vertical.html       -> Fields & labs
  *_teachers_statistics.html       -> (optional) lessons per week
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, Comment, Tag

KINDS = {
    "classes": "_groups_days_vertical.htm",
    "teachers": "_teachers_days_vertical.htm",
    "master": "_subgroups_days_vertical.htm",
    "rooms": "_rooms_days_vertical.htm",
}
STATS = "_teachers_statistics.htm"
REQUIRED = ["classes", "teachers"]

BREAK_RX = re.compile(r"\b(break|lunch|tea|games|prep|assembly|recess)\b", re.I)
TIME_RX = re.compile(r"(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})")
DAY_MAP = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0}


class FetError(ValueError):
    pass


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def _decode(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="ignore")


_FET_RX = re.compile(r"generated\s+with\s+(?:<[^>]*>\s*)*FET\s*v?\s*([0-9][0-9A-Za-z.\-]*)(.{0,300})", re.I | re.S)
_DATE_RX = re.compile(r"(\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})")
_CLOCK_RX = re.compile(r"(?<!\d)(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)")


def fet_stamp_of(text: str) -> dict:
    """FET writes 'Timetable generated with FET <version> on <date> <time>' in every page it exports
    (visible footer and/or an HTML comment). Return {'version': ..., 'when': ...} or {}."""
    m = _FET_RX.search(text or "")
    if not m:
        return {}
    tail = re.sub(r"<[^>]*>", " ", m.group(2))
    tail = re.sub(r"\s+", " ", tail.replace("&nbsp;", " ")).strip()
    stop = re.search(r"-->|\n\n", m.group(2))
    d = _DATE_RX.search(tail)
    c = _CLOCK_RX.search(tail[d.end():] if d else tail)
    when = " ".join(x for x in (d.group(1) if d else "", c.group(1) if c else "") if x)
    if not when:
        o = re.match(r"\s*(?:on|at)\s+(.{1,40}?)\s*(?:\.|-->|$)", tail, re.I)
        when = o.group(1).strip() if o else ""
    return {"version": m.group(1).rstrip(".,"), "when": when}


def _read(path: Path) -> BeautifulSoup:
    text = _decode(path)
    soup = BeautifulSoup(text, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return soup


def _lines(el: Tag) -> list[str]:
    """Text of an element split on <br> and block children."""
    parts, cur = [], []
    for node in el.descendants:
        if isinstance(node, Tag):
            if node.name == "br":
                parts.append("".join(cur)); cur = []
            elif node.name in ("div", "p") and cur:
                parts.append("".join(cur)); cur = []
        elif isinstance(node, str):
            cur.append(str(node))
    parts.append("".join(cur))
    return [_clean(p) for p in parts if _clean(p)]


def to_minutes(h: int, m: int) -> int:
    if h < 7:          # 1:20 means 13:20 in a school day
        h += 12
    return h * 60 + m


def _school_word(line: str) -> str:
    """'ST. BARBARA KIANDERI SEN. SCH' -> 'ST. BARBARA KIANDERI SEN. SCHOOL'"""
    return re.sub(r"\bSCH\b\.?", "SCHOOL", line)


def institution_lines_of(soup: BeautifulSoup) -> list:
    sp = soup.find("span", class_="institution")
    lines = _lines(sp) if sp else []
    if len(lines) < 2:
        whole = " ".join(lines) or institution_of(soup)
        m = re.search(r"\s(TERM\b.*|END\b.*|\d{4}\b.*TIMETABLE.*)$", whole, re.I)
        lines = [whole[:m.start()].strip(), m.group(1).strip()] if m else [whole]
    return [_school_word(x).upper() for x in lines if x.strip()]


def institution_of(soup: BeautifulSoup) -> str:
    sp = soup.find("span", class_="institution")
    if sp:
        return " ".join(_lines(sp))
    for th in soup.find_all("th"):
        if "institution" in th.get_text().lower():
            td = th.find_next("td")
            if td:
                return " ".join(_lines(td))
    if soup.title:
        return _clean(soup.title.get_text())
    return ""


def _parse_periods(table: Tag):
    head = table.find("thead") or table
    row = head.find("tr")
    cols = [c for c in row.find_all(["th", "td"], recursive=False)][1:]
    periods = []
    for c in cols:
        lines = _lines(c)
        text = " ".join(lines)
        m = TIME_RX.search(text)
        start = end = None
        time = ""
        if m:
            h1, m1, h2, m2 = map(int, m.groups())
            start, end = to_minutes(h1, m1), to_minutes(h2, m2)
            if end <= start:
                end += 12 * 60 if end + 12 * 60 > start else 0
            time = f"{h1}:{m1:02d}-{h2}:{m2:02d}"
        label = ""
        for ln in lines:
            if not TIME_RX.search(ln):
                label = re.sub(r"[{}()]", " ", ln).strip()
                break
        if not label:
            brace = re.search(r"\{([^}]*)\}", text)
            if brace:
                label = brace.group(1).strip()
        periods.append({"label": _clean(label), "time": time, "start": start, "end": end,
                        "brk": bool(BREAK_RX.search(text)), "head": text})
    return periods


_RULE_RX = re.compile(r"td\.(c_\d+)\s*\{([^}]*)\}", re.S)


def _css_colours(soup: BeautifulSoup, folder: Path) -> dict:
    """FET's own colours: td.c_N { background-color: …; color: … } in <style> or the linked stylesheet."""
    css = " ".join(t.get_text() for t in soup.find_all("style"))
    for ln in soup.find_all("link", href=True):
        f = folder / ln["href"]
        if f.suffix.lower() == ".css" and f.is_file():
            css += f.read_text("utf-8", errors="ignore")
    out = {}
    for cls, body in _RULE_RX.findall(css):
        bg = re.search(r"background-color\s*:\s*([^;]+)", body)
        fg = re.search(r"(?<![-\w])color\s*:\s*([^;]+)", body)
        if bg:
            out[cls] = [bg.group(1).strip(), fg.group(1).strip() if fg else "black"]
    return out


_COLOURS: dict = {}


def _cell_parts(td: Tag):
    """Return '' (free), 'X' (break / not available) or a dict of the lesson."""
    cls = " ".join(td.get("class") or [])
    text = _clean(td.get_text(" "))
    if "empty" in cls or text in ("---", ""):
        return ""
    if "break" in cls or text == "-X-":
        return "X"
    d = {}
    col = next((_COLOURS[c] for c in (td.get("class") or []) if c in _COLOURS), None)
    if col:
        d["_col"] = col
    found = False
    for key, css in (("c", "studentsset"), ("s", "subject"), ("t", "teacher"), ("r", "room"), ("g", "activitytag")):
        els = td.find_all(class_=css)
        vals = [_clean(e.get_text(" ")) for e in els if _clean(e.get_text(" "))]
        if vals:
            found = True
            d[key] = ", ".join(vals)
    if not found:
        d["_lines"] = _lines(td)
    return d


def _parse_tables(soup: BeautifulSoup):
    out = []
    for table in soup.find_all("table"):
        if not table.get("id", "").startswith("table_"):
            continue
        cap = table.find("caption")
        name = comment = ""
        if cap:
            n = cap.find("span", class_="name")
            cm = cap.find("span", class_="comment")
            name = _clean(n.get_text(" ")) if n else ""
            comment = _clean(cm.get_text(" ")) if cm else ""
            if not name:
                lines = _lines(cap)
                name = lines[-1] if lines else ""
        periods = _parse_periods(table)
        body = table.find("tbody") or table
        days, grid = [], []
        for tr in body.find_all("tr", recursive=False):
            if "foot" in (tr.get("class") or []):
                continue
            th = tr.find("th", recursive=False)
            if not th:
                continue
            day = _clean(th.get_text(" "))
            row = []
            for td in tr.find_all("td", recursive=False):
                span = int(td.get("colspan", 1)) if str(td.get("colspan", "1")).isdigit() else 1
                cell = _cell_parts(td)
                row.append(cell)
                for _ in range(span - 1):
                    row.append("^")
            row = (row + [""] * len(periods))[:len(periods)]
            days.append(day)
            grid.append(row)
        out.append({"name": name, "comment": comment, "periods": periods, "days": days, "grid": grid})
    return out


def _split_tokens(s: str):
    return [t.strip() for t in re.split(r"[,+]", s) if t.strip()]


def _classify_lines(cell: dict, classes: set, teachers: set, rooms: set):
    """Old FET versions give plain lines; work out which line is which."""
    lines = cell.pop("_lines", [])
    for ln in lines:
        toks = _split_tokens(ln)
        if toks and all(t in classes or t.replace(" Automatic Subgroup", "") in classes for t in toks) and "c" not in cell:
            cell["c"] = ", ".join(t.replace(" Automatic Subgroup", "") for t in toks)
        elif toks and all(t in teachers for t in toks) and "t" not in cell:
            cell["t"] = ln
        elif toks and all(t in rooms for t in toks) and "r" not in cell:
            cell["r"] = ln
        elif "s" not in cell:
            cell["s"] = ln
        else:
            cell["g"] = (cell.get("g", "") + " " + ln).strip()
    return cell


def _names_from_fet_files(folder: Path) -> dict:
    """Teacher code -> full name from FET's own data file (Long_Name, else Comments)."""
    import xml.etree.ElementTree as ET
    names = {}
    cands = sorted(folder.rglob("*.fet")) + sorted(p for p in folder.rglob("*.xml") if "teacher" in p.name.lower())
    for f in cands:
        try:
            root = ET.parse(f).getroot()
        except Exception:
            continue
        for t in root.iter("Teacher"):
            code = (t.findtext("Name") or t.get("name") or "").strip()
            nm = (t.findtext("Long_Name") or "").strip() or (t.findtext("Comments") or "").strip()
            if code and nm and nm != code and code not in names:
                names[code] = re.sub(r"\s+", " ", nm)
    return names


def scan_fet(folder: str | Path, log=print) -> dict:
    folder = Path(folder)
    files = {p.name.lower(): p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in (".html", ".htm")}
    found = {}
    for kind, suffix in KINDS.items():
        for lname, p in files.items():
            if lname.endswith(suffix + "l") or lname.endswith(suffix):
                found[kind] = p
                break
    stats_file = next((p for n, p in files.items() if n.endswith(STATS + "l") or n.endswith(STATS)), None)
    missing = [k for k in REQUIRED if k not in found]
    if missing:
        names = {"classes": "…_groups_days_vertical.html", "teachers": "…_teachers_days_vertical.html"}
        raise FetError("This folder is not a complete FET export. Missing: " +
                       ", ".join(names[m] for m in missing) +
                       ". Choose the folder FET created (it contains files ending in _days_vertical.html).")

    institutions = {}
    inst_lines = {}
    parsed = {}
    stamps = []
    for kind, p in found.items():
        st = fet_stamp_of(_decode(p))
        if st:
            stamps.append(st)
        soup = _read(p)
        institutions[kind] = institution_of(soup)
        inst_lines[kind] = institution_lines_of(soup)
        _COLOURS.clear()
        _COLOURS.update(_css_colours(soup, p.parent))
        parsed[kind] = _parse_tables(soup)
        log(f"  • {p.name}: {len(parsed[kind])} timetables")

    teachers_t = parsed["teachers"]
    if not teachers_t:
        raise FetError("No teacher timetables were found in the teachers file.")
    periods = teachers_t[0]["periods"]
    days = teachers_t[0]["days"]

    # Breaks: header says so, or every class has -X- in that column
    classes_t = parsed["classes"]
    for i, p in enumerate(periods):
        if not p["brk"] and classes_t:
            col = [t["grid"][d][i] for t in classes_t for d in range(len(t["grid"])) if i < len(t["grid"][d])]
            if col and all(c == "X" for c in col):
                p["brk"] = True
    n = 0
    for p in periods:
        if not p["brk"]:
            n += 1
            p["n"] = n
            if not p["label"] or TIME_RX.search(p["label"]) or re.fullmatch(r"[Pp]\s*\d+", p["label"]):
                p["label"] = f"L{n}"
        elif not p["label"]:
            p["label"] = "Break"
    lunch_idx = next((i for i, p in enumerate(periods) if p["brk"] and re.search(r"lunch", p["head"], re.I)), None)
    for i, p in enumerate(periods):
        if lunch_idx is not None:
            p["pm"] = i > lunch_idx
        else:
            p["pm"] = bool(p["start"] and p["start"] >= 13 * 60)
        p.pop("head", None)

    class_names = {t["name"] for t in classes_t}
    teacher_codes = {t["name"] for t in teachers_t}
    room_names = {t["name"] for t in parsed.get("rooms", [])}
    for kind, tables in parsed.items():
        for t in tables:
            if len(t["periods"]) != len(periods):
                raise FetError(f"The {kind} file has a different number of periods from the teachers file. "
                               "Export all files from the same FET timetable.")
            for row in t["grid"]:
                for j, c in enumerate(row):
                    if isinstance(c, dict):
                        if "_lines" in c:
                            _classify_lines(c, class_names, teacher_codes, room_names)
                        if "c" in c:
                            c["c"] = ", ".join(x.replace(" Automatic Subgroup", "").strip() for x in _split_tokens(c["c"]))

    # Fill in the teacher on class / master lessons when FET left it out
    def resolve(row, j):
        while j > 0 and row[j] == "^":
            j -= 1
        return row[j]
    slot_teachers: dict[tuple, list] = {}
    for t in teachers_t:
        for d, row in enumerate(t["grid"]):
            for j in range(len(row)):
                c = resolve(row, j)
                if isinstance(c, dict) and c.get("c"):
                    for cls in _split_tokens(c["c"]):
                        slot_teachers.setdefault((cls, d, j), []).append(t["name"])
    for kind in ("classes", "master"):
        for t in parsed.get(kind, []):
            cname = t["name"].replace(" Automatic Subgroup", "").strip()
            for d, row in enumerate(t["grid"]):
                for j, c in enumerate(row):
                    if isinstance(c, dict) and not c.get("t"):
                        who = slot_teachers.get((cname, d, j))
                        if who:
                            c["t"] = ", ".join(dict.fromkeys(who))

    # Teacher display names: from the HTML, else from the FET data file (.fet) or teachers XML in the folder
    extra = _names_from_fet_files(folder)
    teachers = []
    for i, t in enumerate(teachers_t):
        nm = (t["comment"] or "").strip() or extra.get(t["name"].strip(), "")
        teachers.append({"id": f"T{i + 1}", "code": t["name"], "name": nm, "grid": t["grid"]})
    named = sum(1 for t in teachers if t["name"])
    log(f"  • Teacher names: {named} of {len(teachers)}" + ("" if named == len(teachers) else
        " — codes will show for the rest (add names in FET: Data → Teachers → Long name or Comments)"))

    def simple(tables, prefix, strip_sub=False):
        out = []
        for i, t in enumerate(tables):
            nm = t["name"].replace(" Automatic Subgroup", "").strip() if strip_sub else t["name"].strip()
            out.append({"id": f"{prefix}{i + 1}", "name": nm, "grid": t["grid"]})
        return out

    data = {
        "format": 2,
        "periods": periods,
        "days": [{"label": d, "wd": DAY_MAP.get(d.strip().lower()[:3], -1)} for d in days],
        "teachers": teachers,
        "classes": simple(classes_t, "C"),
        "master": simple(parsed.get("master", classes_t), "M", strip_sub=True),
        "rooms": simple(parsed.get("rooms", []), "R"),
    }

    # Lessons per week from statistics (optional) or counted
    stats = {}
    if stats_file:
        try:
            soup = _read(stats_file)
            for tr in soup.find_all("tr"):
                cells = [_clean(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
                if len(cells) >= 2 and cells[1].isdigit():
                    code = cells[0].split(" ")[0] if cells[0].split(" ")[0] in teacher_codes else cells[0]
                    stats[code] = int(cells[1])
        except Exception:
            stats = {}
    for t in teachers:
        lessons = sum(1 for row in t["grid"] for c in row if isinstance(c, dict))
        t["load"] = stats.get(t["code"], lessons)

    insts = {k: v for k, v in institutions.items() if v}
    institution = insts.get("teachers") or next(iter(insts.values()), "")
    data["institution"] = institution
    # Subject colours exactly as FET exported them (most used colour for each subject)
    tally = {}
    for kind in parsed:
        for t in parsed[kind]:
            for row in t["grid"]:
                for c in row:
                    if isinstance(c, dict) and "_col" in c:
                        col = c.pop("_col")
                        for subj in _split_tokens(c.get("s", "")) if c.get("s") else []:
                            k = (subj.upper(), tuple(col))
                            tally[k] = tally.get(k, 0) + (3 if kind == "classes" else 1)
    colours = {}
    for (subj, col), n in sorted(tally.items(), key=lambda kv: -kv[1]):
        colours.setdefault(subj, list(col))
    data["colours"] = colours
    if colours:
        log(f"  • FET subject colours: {len(colours)} subjects")
    # "Created by the FET program" + the time FET stamped on the timetable (as FET wrote it)
    withtime = [x for x in stamps if x.get("when")]
    fet = (withtime or stamps or [{}])[0]
    data["fet"] = {"version": fet.get("version", ""), "when": fet.get("when", "")}
    if fet:
        log(f"  • FET stamp: FET {fet.get('version', '')} · {fet.get('when') or 'time not found'}")
    else:
        log("  • FET stamp not found in these files (the app will still say the timetable was made with FET)")
    data["institution_lines"] = inst_lines.get("teachers") or next((v for v in inst_lines.values() if v), [])
    data["institutions"] = insts
    log(f"✔ {len(teachers)} teachers · {len(data['classes'])} classes · {len(data['rooms'])} fields/labs · "
        f"master for {len(days)} days · {sum(1 for p in periods if not p['brk'])} lessons a day")
    return data


def norm_words(s: str) -> list[str]:
    return [w for w in re.sub(r"[^A-Z0-9 ]+", " ", (s or "").upper()).split() if w]


def institution_matches(institution: str, lock_words: str) -> bool:
    inst = " " + " ".join(norm_words(institution)) + " "
    words = norm_words(lock_words)
    return bool(words) and all(f" {w} " in inst for w in words)
