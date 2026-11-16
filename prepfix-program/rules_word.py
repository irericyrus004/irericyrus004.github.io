"""
RULES FROM WORD - write the school's timetable rules in a Word document, then import them into PREPFIX.

    make_template(dest, school, data=None)   -> writes "PREPFIX rules - <school>.docx"
    read_rules(path, data=None)              -> (rules, problems)

The template is an ordinary Word file with one table per kind of rule. Fill the empty rows (add rows if you
need more), save, then in PREPFIX: Rules window -> "Import rules from Word". Nothing extra has to be installed:
the file is written and read with Python alone.

Tables (the heading row of each table tells PREPFIX what it is - keep the heading rows as they are):
    STANDARD RULES          Rule | Use it? (Yes / No) | If it fails
    TEACHER LIMITS          Teacher | Most lessons a day | Most lessons a week | Most lessons in a row | If it fails
    TEACHER NOT AVAILABLE   Teacher | Days | Lessons / times | If it fails
    SUBJECT TIMES           Subject | Never in / Only in | Lessons / times | If it fails
    SUBJECT PER DAY         Subject | Most periods a day (for a class) | If it fails
    LESSONS PER WEEK        Class | Subject | Exactly / At least / At most | Lessons a week | If it fails
"If it fails":  "Must pass" (blocks publishing until fixed)  or  "Warning".
Rows PREPFIX cannot understand are NOT added: they come back in `problems` with the reason.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import constraints as K
import rules_more as RM

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

STANDARD = [("teacher_clash", "A teacher is never in two lessons at once"),
            ("class_clash", "A class is never in two lessons at once"),
            ("room_clash", "A lab / field is never used by two lessons at once"),
            ("break_lessons", "No lessons during breaks"),
            ("no_teacher", "Every lesson has a teacher")]

TABLES = {
    "STANDARD RULES": ["Rule", "Use it? (Yes / No)", "If it fails"],
    "TEACHER LIMITS": ["Teacher", "Most lessons a day", "Most lessons a week", "Most lessons in a row", "If it fails"],
    "TEACHER NOT AVAILABLE": ["Teacher", "Days", "Lessons / times", "If it fails", "Reason"],
    "SUBJECT TIMES": ["Subject", "Never in / Only in", "Lessons / times", "If it fails"],
    "SUBJECT PER DAY": ["Subject", "Most periods a day (for a class)", "If it fails"],
    "LESSONS PER WEEK": ["Class", "Subject", "Exactly / At least / At most", "Lessons a week", "If it fails"],
    "PART RULES": ["No.", "Rule", "Setting (change the values)", "Use it? (Yes / No)", "If it fails"],
    "LABORATORIES": ["Laboratory", "Subjects (practicals)", "Lessons at once", "Doubles only (Yes / No)", "If it fails"],
}

# Parts 10 - 14: (number, rule type, what it says, settings, use it, if it fails)
PARTS = [
    ("PART 10 · SUBJECT DISTRIBUTION RULES", "Defaults are configurable: change any value in the Setting column.", [
        ("10.1 + 10.3", "subject_sessions", "Sessions of a subject for a class in one day. Fewer weekly lessons: once a "
         "day on different days. More than five a week: may be twice a day, never three separate sessions.",
         {}, "Yes", "Must pass"),
        ("10.2", "mixed_blocks", "No single and double (or double and triple, triple and single) of the same subject and "
         "class on the same day; spread the types across days. Weekly periods are kept.", {}, "Yes", "Must pass"),
        ("10.4", "subject_gap", "The same subject twice in a day: teaching periods between the two (no ordinary lessons "
         "back to back unless an intentional double).", {}, "Yes", "Warning"),
        ("10.5", "subject_pair", "Subject pair: not one right after the other for the same class.",
         {"subject": "ENGLISH", "subject2": "KISWAHILI"}, "Yes", "Warning"),
        ("10.5", "subject_pair", "Subject pair: not one right after the other for the same class.",
         {"subject": "CHEMISTRY", "subject2": "MATHEMATICS"}, "Yes", "Warning"),
        ("10.5", "subject_pair", "Subject pair: not one right after the other for the same class.",
         {"subject": "PHYSICS", "subject2": "BIOLOGY"}, "Yes", "Warning"),
    ]),
    ("PART 11 · MORNING AND AFTERNOON DISTRIBUTION",
     "Morning ends at the lunch break and the afternoon begins straight after it — PREPFIX uses the real day of the "
     "timetable, not an assumed number of periods. Write the lunch break's name as it is in the timetable.", [
        ("11.1", "morning_min", "Minimum morning lessons: weekly lessons → at least this many before lunch, spread "
         "across the morning (not all in the last period before lunch). Weekly totals are never changed.",
         {}, "Yes", "Must pass"),
    ]),
    ("PART 12 · TEACHER WORKLOAD AND DISTRIBUTION", "Defaults are configurable. “Every teacher” or one teacher's name.", [
        ("12.1 + 12.2", "first_last", "First-period and last-period allocations per teacher in a five-day week.",
         {}, "Yes", "Warning"),
        ("12.3", "monfri_first", "First period on Monday and Friday together.", {}, "Yes", "Warning"),
        ("12.4", "consec_break", "Two consecutive ordinary periods are allowed; after two, a qualifying break must come "
         "before another lesson (different classes count too).", {}, "Yes", "Warning"),
        ("12.5", "continuous", "Continuous teaching without a qualifying break. A free period is not a qualifying break.",
         {}, "Yes", "Warning"),
        ("12.6", "free_afternoon", "Free afternoons a week: no teaching from the end of lunch to the end of the day.",
         {}, "Yes", "Warning"),
        ("12.9", "daily_by_length", "Daily occupied periods by the length of the day (10-period day: at most 7; 9-period "
         "day: at most 6). Weekly loads above the review number are listed for an exception review.",
         {}, "Yes", "Must pass"),
        ("12.11", "afternoon_doubles", "Double lessons in one afternoon for a teacher (three are flagged).",
         {}, "Yes", "Warning"),
        ("12.12", "same_teacher_class", "The same teacher and class in two separate lessons one right after the other "
         "(intentional doubles and triples are fine).", {}, "Yes", "Warning"),
    ]),
]
GUIDANCE = [
    "12.7  Spread attendance reasonably; do not force low-load teachers to attend all five days.",
    "12.8  Teachers with 10+ weekly lessons normally aim for 2 sessions per teaching day (a double may justify one); "
    "15+ aim for 3. These preferences never create lessons.",
    "12.10  Sessions are counted separately from occupied periods: one double is one session, two periods.",
    "12.13  Manual constraints (unavailable or preferred days, periods, times; special arrangements) go in the "
    "TEACHER NOT AVAILABLE table: Must pass = hard (never overridden), Warning = preferred. Write the reason.",
    "Part 13  Single = 1 period, double = 2 in a row, triple = 3 in a row. Blocks stay whole. Single + double, "
    "double + triple and triple + single of the same subject and class are not on the same day (rule 10.2). Triples "
    "are allowed as intentional blocks and are checked with 12.4 and 12.5; a triple never allows a fourth lesson in a row.",
]


def _lab_of(label) -> str:
    return re.sub(r"\s*\(\*[^)]*\)", "", label).strip()


def setting_text(typ, r) -> str:
    """'Weekly lessons up to (low) = 5;  Sessions a day if low = 1; ...' - the values a school edits in Word."""
    fields = RM.TYPES[typ][1]
    out = []
    for k, label, kind in fields:
        v = r.get(k, "")
        if k == "teacher" and str(v).strip() in ("", "*"):
            v = "Every teacher"
        out.append(f"{_lab_of(label)} = {v}")
    return ";  ".join(out) if out else "(no setting)"


def parse_setting(typ, text):
    """-> (values, problem)"""
    fields = RM.TYPES[typ][1]
    vals, parts = {}, [x.strip() for x in str(text or "").split(";") if x.strip()]
    if not fields:
        return vals, None
    loose = []
    for part in parts:
        if "=" in part:
            lab, v = part.split("=", 1)
            key = next((k for k, label, _ in fields if _n(_lab_of(label)) == _n(lab)), None)
            if key is None:
                key = next((k for k, label, _ in fields if _n(lab) and _n(lab) in _n(_lab_of(label))), None)
            if key is None:
                return None, f"“{lab.strip()}” is not a setting of this rule"
            vals[key] = v.strip()
        else:
            loose.append(part)
    for (k, label, kind), v in zip([f for f in fields if f[0] not in vals], loose):
        vals[k] = v
    for k, label, kind in fields:
        v = str(vals.get(k, RM.DEFAULTS.get(typ, {}).get(k, ""))).strip()
        if kind == "int":
            if not v.isdigit():
                return None, f"“{label}” must be a whole number (not “{v}”)"
            v = int(v)
        if kind == "teacher" and _n(v) in ("EVERY TEACHER", "ALL", "*", ""):
            v = "*"
        vals[k] = v
    return vals, None


CODES = {"10.1": "subject_sessions", "10.3": "subject_sessions", "10.2": "mixed_blocks", "10.4": "subject_gap",
         "10.5": "subject_pair", "11.1": "morning_min", "12.1": "first_last", "12.2": "first_last",
         "12.3": "monfri_first", "12.4": "consec_break", "12.5": "continuous", "12.6": "free_afternoon",
         "12.9": "daily_by_length", "12.11": "afternoon_doubles", "12.12": "same_teacher_class", "13": "mixed_blocks"}


def _n(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


# ------------------------------------------------------------------------------------------------ writing
def _run(text, bold=False, size=None, color=None, italic=False):
    rpr = ""
    if bold or size or color or italic:
        rpr = "<w:rPr>" + ('<w:b/>' if bold else "") + ('<w:i/>' if italic else "") + \
              (f'<w:color w:val="{color}"/>' if color else "") + (f'<w:sz w:val="{size}"/>' if size else "") + "</w:rPr>"
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(str(text))}</w:t></w:r>'


def _p(text="", bold=False, size=None, color=None, italic=False, space_after=120, keep=False):
    ppr = f'<w:pPr>{"<w:keepNext/>" if keep else ""}<w:spacing w:after="{space_after}"/></w:pPr>'
    return f"<w:p>{ppr}{_run(text, bold, size, color, italic) if text else ''}</w:p>"


def _cell(text, width, head=False, grey=False):
    shade = '<w:shd w:val="clear" w:color="auto" w:fill="12284C"/>' if head else \
            ('<w:shd w:val="clear" w:color="auto" w:fill="F3EEDF"/>' if grey else "")
    return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
            f'{_run(text, bold=head, color="FFFFFF" if head else ("7A7464" if grey else None), size=20, italic=grey) if text else ""}'
            f'</w:p></w:tc>')


def _table(head, rows, widths, example_rows=0):
    borders = ''.join(f'<w:{b} w:val="single" w:sz="6" w:space="0" w:color="9AA3B2"/>'
                      for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:tblBorders>{borders}</w:tblBorders>'
           f'<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>'
           + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"]
    out.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>' + "".join(_cell(h, w, head=True) for h, w in zip(head, widths)) + "</w:tr>")
    for i, r in enumerate(rows):
        out.append("<w:tr>" + "".join(_cell(v, w, grey=i < example_rows) for v, w in zip(r, widths)) + "</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def _parts(doc: str) -> dict:
    """The files inside a .docx around the main document."""
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}"><w:docDefaults>'
              '<w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="22"/>'
              '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120"/></w:pPr></w:pPrDefault>'
              '</w:docDefaults></w:styles>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
             '</Relationships>')
    return {"[Content_Types].xml": ct, "_rels/.rels": rels, "word/document.xml": doc, "word/styles.xml": styles,
            "word/_rels/document.xml.rels": drels}


def make_template(dest, school: str = "", data: dict | None = None) -> Path:
    """A ready-to-fill Word document. With a loaded timetable, its teachers, classes, subjects, days and lessons
    are listed at the end so the names are typed exactly."""
    data = data or {}
    teachers = [(t["code"], t.get("name") or "") for t in data.get("teachers", [])]
    classes = [c["name"] for c in data.get("classes", [])]
    subjects = sorted({str(c.get("s")) for t in data.get("teachers", []) for row in t.get("grid", [])
                       for c in row if isinstance(c, dict) and c.get("s")})
    days = [d["label"] for d in data.get("days", [])]
    lessons = [f"{p['label']} ({p.get('time', '')})".replace(" ()", "") for p in data.get("periods", []) if not p.get("brk")]
    ex_t = (f"{teachers[0][0]} · {teachers[0][1]}" if teachers and teachers[0][1] else teachers[0][0]) if teachers else "MR. KAMAU J."
    count = {}
    for t in data.get("teachers", []):
        for row in t.get("grid", []):
            for c in row:
                if isinstance(c, dict) and c.get("s"):
                    count[c["s"]] = count.get(c["s"], 0) + 1
    ex_s = next((s for s in subjects if _n(s) in ("MATHS", "MATHEMATICS", "ENGLISH")), None) or \
        (max(count, key=count.get) if count else "MATHS")
    ex_c = classes[0] if classes else "10 A"
    body = []
    body.append(_p("PREPFIX Timetable Toolkit — timetable rules", bold=True, size=36, color="12284C", space_after=60))
    body.append(_p(school or "School name", bold=True, size=26, color="1E7F5C", space_after=160))
    body.append(_p("How to fill this in", bold=True, size=24, color="12284C", keep=True))
    for line in [
        "1.  Type in the EMPTY rows of each table. The grey row at the top of a table is an example — delete it or "
        "leave it (grey rows that still say “example” are ignored).",
        "2.  Need more rows? Click in the last row → right-click → Insert → Insert Rows Below. Leave a table empty "
        "if you do not need that kind of rule.",
        "3.  Teacher: the teacher's name or number as in the timetable, or “Every teacher”. Class: a class name or "
        "“Every class”. Subject: as written on the timetable, or “Every subject”.",
        "4.  Days: Monday, Tuesday … or a range like Mon-Wed. Empty = every day.   Lessons / times: L1, L2 or a range "
        "like L1-L3, or a time like 8:20-9:00. Empty = every lesson.",
        "5.  If it fails: “Must pass” (PREPFIX will not publish until it is fixed) or “Warning” (shown, but publishing "
        "is allowed). Empty = Must pass.",
        "6.  Save the file. In PREPFIX: Import & Run → 📋 Rules → Extra checks → “📥 Import rules from Word”. PREPFIX lists "
        "any row it could not understand, so nothing is guessed.",
    ]:
        body.append(_p(line, size=21, space_after=80))
    W_ = 9600

    def section(title, sub, rows, widths, ex=1, blank=6):
        body.append(_p(""))
        body.append(_p(title, bold=True, size=26, color="12284C", space_after=40, keep=True))
        body.append(_p(sub, size=20, color="555555", italic=True, space_after=100, keep=True))
        head = TABLES[title]
        body.append(_table(head, rows + [[""] * len(head) for _ in range(blank)], widths, example_rows=ex))

    section("STANDARD RULES", "The basic checks. Write Yes to use a rule, No to leave it out.",
            [[label, "Yes", "Warning" if key == "no_teacher" else "Must pass"] for key, label in STANDARD],
            [5600, 2000, 2000], ex=0, blank=0)
    section("TEACHER LIMITS", "How many lessons a teacher may have. Fill only the limits you want.",
            [["example: Every teacher", "7", "", "4", "Must pass"]], [3200, 1600, 1600, 1600, 1600])
    section("TEACHER NOT AVAILABLE", "Times a teacher cannot teach (part-time, duties, meetings). Must pass = hard "
            "(never overridden); Warning = preferred. Write the reason.",
            [[f"example: {ex_t}", "Friday", "L7-L8", "Must pass", "Part-time"]], [2800, 1600, 1700, 1300, 2200])
    section("SUBJECT TIMES", "Subjects that must never be (or must only be) at certain lessons.",
            [[f"example: {ex_s}", "Never in", "L7, L8", "Warning"]], [3000, 2000, 3000, 1600])
    section("SUBJECT PER DAY", "The most periods of one subject a class may have in a day.",
            [["example: Every subject", "2", "Must pass"]], [4400, 3600, 1600])
    section("LESSONS PER WEEK", "How many lessons of a subject a class must have in a week.",
            [[f"example: {ex_c}", ex_s, "Exactly", "6", "Must pass"]], [2200, 2600, 1800, 1400, 1600])
    for title, sub, rows in PARTS:
        body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>' if title.startswith("PART 10") else _p(""))
        body.append(_p(title, bold=True, size=26, color="12284C", space_after=40, keep=True))
        body.append(_p(sub, size=20, color="555555", italic=True, space_after=100, keep=True))
        trs = [[num, what, setting_text(typ, dict(RM.DEFAULTS.get(typ, {}), **extra)), use, sev]
               for num, typ, what, extra, use, sev in rows]
        body.append(_table(TABLES["PART RULES"], trs + ([["10.5", "Subject pair: not one right after the other "
                                                           "for the same class.", "Subject = ;  And subject = ", "Yes",
                                                           "Warning"]] if title.startswith("PART 10") else []),
                           [900, 3700, 3200, 900, 1000], example_rows=0))
    body.append(_p(""))
    body.append(_p("PART 12 / 13 · GUIDANCE (written here for the school; PREPFIX does not check these)", bold=True,
                   size=22, color="12284C", space_after=60, keep=True))
    for g in GUIDANCE:
        body.append(_p(g, size=19, space_after=60))
    body.append(_p(""))
    body.append(_p("PART 14 · LABORATORY AND ROOM MANAGEMENT", bold=True, size=26, color="12284C", space_after=40, keep=True))
    body.append(_p("One row per laboratory: its name, the subjects whose practicals need it, how many lessons it can hold at "
                   "once, and whether only double (practical) lessons count. PREPFIX does not assume the school's "
                   "facilities: with no laboratory listed, laboratory checks are not done.", size=20, color="555555",
                   italic=True, space_after=100, keep=True))
    body.append(_table(TABLES["LABORATORIES"], [["example: Chemistry lab", "CHEMISTRY", "1", "Yes", "Must pass"],
                                                ["example: Biology / Physics lab", "BIOLOGY, PHYSICS", "1", "Yes", "Must pass"]]
                       + [[""] * 5 for _ in range(5)], [2600, 3000, 1300, 1500, 1200], example_rows=2))
    if teachers or classes:
        body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        body.append(_p("Names in this timetable (type them exactly like this)", bold=True, size=24, color="12284C"))
        if teachers:
            body.append(_p("Teachers", bold=True, size=21, space_after=40))
            body.append(_p("   ".join(f"{c} · {n}" if n else c for c, n in teachers), size=19))
        if classes:
            body.append(_p("Classes", bold=True, size=21, space_after=40))
            body.append(_p(",  ".join(classes), size=19))
        if subjects:
            body.append(_p("Subjects", bold=True, size=21, space_after=40))
            body.append(_p(",  ".join(subjects), size=19))
        if days:
            body.append(_p("Days", bold=True, size=21, space_after=40))
            body.append(_p(",  ".join(days), size=19))
        if lessons:
            body.append(_p("Lessons", bold=True, size=21, space_after=40))
            body.append(_p(",  ".join(lessons), size=19))
    body.append(_p(""))
    body.append(_p("PREPFIX Timetable Toolkit · Prepare. Perfect. Present. · Cyrus Ireri 0720872582", size=16, color="7A7464"))
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1000" w:right="1000" w:bottom="1000" '
            'w:left="1000" w:header="500" w:footer="500" w:gutter="0"/></w:sectPr>')
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>'
           + "".join(body) + sect + "</w:body></w:document>")
    dest = Path(dest)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for name, part in _parts(doc).items():
            z.writestr(name, part)
    return dest


# ------------------------------------------------------------------------------------------------ reading
def _tables(path) -> list:
    """[[row, ...], ...] - every table in the Word file, each row a list of cell texts."""
    with zipfile.ZipFile(str(path)) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    out = []
    for tbl in root.iter(f"{{{W}}}tbl"):
        rows = []
        for tr in tbl.findall("w:tr", NS):
            cells = []
            for tc in tr.findall("w:tc", NS):
                paras = ["".join(t.text or "" for t in p.iter(f"{{{W}}}t")) for p in tc.iter(f"{{{W}}}p")]
                cells.append(" ".join(x.strip() for x in paras if x.strip()))
            rows.append(cells)
        out.append(rows)
    return out


def _kind(head: list):
    h = [_n(x) for x in head]
    for title, cols in TABLES.items():
        want = [_n(x) for x in cols]
        if want[-1] == "REASON":                              # older templates have no Reason column
            want = want[:-1]
        if len(h) >= len(want) and all(a.split(" (")[0] == b.split(" (")[0] for a, b in zip(h, want)):
            return title
    return None


def _sev(v):
    v = _n(v)
    if not v or v.startswith("MUST") or v in ("ERROR", "BLOCK"):
        return K.ERR, None
    if v.startswith("WARN"):
        return K.WARN, None
    return None, f"“If it fails” must be Must pass or Warning (not “{v.title()}”)"


def _int(v):
    v = str(v or "").strip()
    if not v:
        return None, None
    m = re.fullmatch(r"\d{1,3}", v)
    return (int(v), None) if m else (None, f"“{v}” is not a number")


def _days(v):
    """'Mon-Wed, Fri' -> ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'FRIDAY']"""
    out = []
    for part in re.split(r"[,;/]| AND ", _n(v)):
        part = part.strip()
        if not part or part in ("EVERY DAY", "ALL", "ALL DAYS"):
            continue
        m = re.fullmatch(r"([A-Z]{3,})\s*(?:-|–|TO)\s*([A-Z]{3,})", part)
        if m:
            a = next((i for i, d in enumerate(DAYS) if d.startswith(m.group(1)[:3])), None)
            b = next((i for i, d in enumerate(DAYS) if d.startswith(m.group(2)[:3])), None)
            if a is None or b is None or b < a:
                return None, f"“{part.title()}” is not a range of days"
            out += [d.title() for d in DAYS[a:b + 1]]
            continue
        d = next((d for d in DAYS if d.startswith(part[:3])), None)
        if not d:
            return None, f"“{part.title()}” is not a day"
        out.append(d.title())
    return out, None


def _periods(v):
    """'L1-L3, 8:20-9:00, L7' -> ['L1', 'L2', 'L3', '8:20-9:00', 'L7']"""
    out = []
    for part in re.split(r"[,;]| AND ", str(v or "")):
        part = part.strip()
        if not part or _n(part) in ("ALL", "EVERY LESSON", "ALL LESSONS"):
            continue
        m = re.fullmatch(r"([A-Za-z]*)\s*(\d+)\s*(?:-|–|to)\s*([A-Za-z]*)\s*(\d+)", part)
        if m and (not m.group(3) or _n(m.group(3)) == _n(m.group(1))) and ":" not in part:
            a, b = int(m.group(2)), int(m.group(4))
            if b < a or b - a > 20:
                return None, f"“{part}” is not a range of lessons"
            out += [f"{m.group(1).upper()}{i}" for i in range(a, b + 1)]
        else:
            out.append(part.upper() if re.fullmatch(r"[A-Za-z]+\d+", part) else part)
    return out, None


def read_rules(path, data: dict | None = None):
    """-> (rules, problems). problems = [(table, row number, text, reason)]. With a loaded timetable, teacher,
    class and subject names are checked against it."""
    data = data or {}
    tnames = {}
    for t in data.get("teachers", []):
        for k in (t["code"], t.get("name"), f"{t['code']} · {t.get('name', '')}", f"{t['code']} {t.get('name', '')}"):
            if k:
                tnames[_n(k)] = t.get("name") or t["code"]        # the rule shows the teacher's name
    cnames = {_n(c["name"]): c["name"] for c in data.get("classes", [])}
    subs = {_n(c.get("s")) for t in data.get("teachers", []) for row in t.get("grid", [])
            for c in row if isinstance(c, dict) and c.get("s")}
    labels = {_n(p["label"]) for p in data.get("periods", [])} | {_n(p.get("time", "")) for p in data.get("periods", [])}
    every = lambda v, word: _n(v) in ("", "*", "ALL", f"EVERY {word}", f"ALL {word}S", f"EVERY {word}S")

    def teacher(v):
        if every(v, "TEACHER"):
            return "*", None
        if not data:
            return v.strip(), None
        code = tnames.get(_n(v))
        return (code, None) if code else (None, f"no teacher called “{v}” in this timetable")

    def subject(v, allow_every=False):
        if allow_every and every(v, "SUBJECT"):
            return "*", None
        if not str(v).strip():
            return None, "the Subject is empty"
        if subs and _n(v) not in subs:
            return None, f"no subject called “{v}” in this timetable"
        return v.strip(), None

    rules, problems, std_seen = [], [], {}
    for tbl in _tables(path):
        if not tbl:
            continue
        kind = _kind(tbl[0])
        if not kind:
            continue
        for i, row in enumerate(tbl[1:], 2):
            row = list(row) + [""] * 6
            if not any(c.strip() for c in row) or _n(row[0]).startswith("EXAMPLE"):
                continue
            text = " | ".join(c for c in row if c.strip())
            bad = lambda why: problems.append((kind.title(), i, text, why))
            if kind == "STANDARD RULES":
                key = next((k for k, lab in STANDARD if _n(lab)[:25] == _n(row[0])[:25]), None)
                use = _n(row[1])
                sev, e = _sev(row[2])
                if not key:
                    bad("not one of the standard rules (keep their wording)")
                elif use not in ("YES", "Y", "NO", "N", ""):
                    bad("“Use it?” must be Yes or No")
                elif e:
                    bad(e)
                else:
                    std_seen[key] = (use in ("YES", "Y", ""), sev)
                continue
            if kind == "PART RULES":
                code = re.match(r"\s*(\d+\.\d+)", row[0] or "")
                typ = CODES.get(code.group(1)) if code else None
                if not typ:
                    bad("the No. must be one of the rule numbers (10.1, 10.2, 10.4, 10.5, 11.1, 12.1, 12.3, 12.4, 12.5, "
                        "12.6, 12.9, 12.11, 12.12)")
                    continue
                use = _n(row[3])
                if use in ("NO", "N"):
                    continue
                if use not in ("YES", "Y", ""):
                    bad("“Use it?” must be Yes or No")
                    continue
                sev, e = _sev(row[4])
                vals, e2 = parse_setting(typ, row[2])
                e = e or e2
                if not e and typ == "subject_pair":
                    if not vals.get("subject") or not vals.get("subject2"):
                        continue                                 # an empty pair row: nothing to add
                if not e and vals.get("teacher") and vals["teacher"] != "*":
                    who, e = teacher(vals["teacher"])
                    vals["teacher"] = who
                if e:
                    bad(e)
                else:
                    rules.append(K.new_rule(typ, severity=sev, **vals))
                continue
            if kind == "LABORATORIES":
                sev, e = _sev(row[4])
                names = [x.strip() for x in re.split(r"[,;/]", row[1]) if x.strip()]
                n, e2 = _int(row[2])
                dbl = _n(row[3])
                e = e or e2 or (None if names else "give the subjects") or (None if n else "type how many lessons at once") \
                    or (None if dbl in ("", "YES", "Y", "NO", "N") else "“Doubles only” must be Yes or No")
                if not e and subs:
                    miss = [x for x in names if _n(x) not in subs]
                    if miss:
                        e = "subject(s) not in this timetable: " + ", ".join(miss)
                if e:
                    bad(e)
                else:
                    rules.append(K.new_rule("lab", lab=row[0].strip() or "Laboratory", subjects=", ".join(names), capacity=n,
                                            doubles_only="No" if dbl in ("NO", "N") else "Yes", severity=sev))
                continue
            sev, e = _sev(row[-1] if kind == "STANDARD RULES" else row[len(TABLES[kind]) - (2 if kind == "TEACHER NOT AVAILABLE" else 1)])
            if e:
                bad(e)
                continue
            if kind == "TEACHER LIMITS":
                who, e = teacher(row[0])
                if e:
                    bad(e)
                    continue
                vals = []
                for typ, v in (("teacher_max_day", row[1]), ("teacher_max_week", row[2]), ("teacher_max_consec", row[3])):
                    n, e2 = _int(v)
                    if e2:
                        e = e2
                    elif n is not None:
                        vals.append(K.new_rule(typ, teacher=who, max=n, severity=sev))
                if e:
                    bad(e)
                elif not vals:
                    bad("no limit typed (fill at least one number)")
                else:
                    rules += vals
            elif kind == "TEACHER NOT AVAILABLE":
                who, e = teacher(row[0])
                if not e and who == "*":
                    e = "name one teacher (not every teacher)"
                d, e2 = _days(row[1])
                ps, e3 = _periods(row[2])
                e = e or e2 or e3
                if not e and labels and any(_n(x) not in labels for x in ps):
                    e = "lesson(s) not in this timetable: " + ", ".join(x for x in ps if _n(x) not in labels)
                if not e and not d and not ps:
                    e = "give the days and / or the lessons"
                if e:
                    bad(e)
                else:
                    rules.append(K.new_rule("teacher_unavailable", teacher=who, days=", ".join(d), periods=", ".join(ps),
                                            severity=sev, **({"reason": row[4].strip()} if row[4].strip() else {})))
            elif kind == "SUBJECT TIMES":
                s, e = subject(row[0])
                mode = _n(row[1])
                mode = "only in" if mode.startswith("ONLY") else "never in" if mode.startswith("NEVER") or not mode else None
                ps, e2 = _periods(row[2])
                e = e or e2 or (None if mode else "write Never in or Only in") or (None if ps else "give the lessons / times")
                if not e and labels and any(_n(x) not in labels for x in ps):
                    e = "lesson(s) not in this timetable: " + ", ".join(x for x in ps if _n(x) not in labels)
                if e:
                    bad(e)
                else:
                    rules.append(K.new_rule("subject_periods", subject=s, mode=mode, periods=", ".join(ps), severity=sev))
            elif kind == "SUBJECT PER DAY":
                s, e = subject(row[0], allow_every=True)
                n, e2 = _int(row[1])
                e = e or e2 or (None if n is not None else "type the most periods a day")
                if e:
                    bad(e)
                else:
                    rules.append(K.new_rule("subject_max_day", subject=s, max=n, severity=sev))
            elif kind == "LESSONS PER WEEK":
                if every(row[0], "CLASS"):
                    c, e = "*", None
                elif cnames and _n(row[0]) not in cnames:
                    c, e = None, f"no class called “{row[0]}” in this timetable"
                else:
                    c, e = cnames.get(_n(row[0]), row[0].strip()), None
                s, e2 = subject(row[1])
                op = _n(row[2])
                op = {"EXACTLY": "exactly", "AT LEAST": "at least", "AT MOST": "at most", "": "exactly"}.get(op)
                n, e3 = _int(row[3])
                e = e or e2 or (None if op else "write Exactly, At least or At most") or e3 or \
                    (None if n is not None else "type the number of lessons a week")
                if e:
                    bad(e)
                else:
                    rules.append(K.new_rule("class_week_count", **{"class": c}, subject=s, op=op, count=n, severity=sev))
    std = []
    for key, _ in STANDARD:                               # the standard rules always come first, in their order
        on, sev = std_seen.get(key, (True, K.WARN if key == "no_teacher" else K.ERR))
        r = K.new_rule(key, severity=sev)
        r["enabled"] = on
        std.append(r)
    return std + rules, problems
