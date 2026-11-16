"""
NOTES FROM WORD - many notes at once, written in an ordinary Word document. Nothing to pick from a list:
PREPFIX finds who each note is for.

    make_template(dest, school, classes, teachers)   -> writes the Word template
    find_targets(text, classes, teachers)            -> ([note target, ...], text without the "For …:" start)
    read_notes(path, classes, teachers)              -> (notes, problems)

How PREPFIX finds who a note is for (in this order):
  1. The note starts with who it is for and a colon:  "9N: …", "10A and 10 B: …", "All classes: …",
     "All teachers: …", "Mr Mukono: …".
  2. Otherwise the note itself is read: classes named in it ("9N will …", "10 A and 10B …"), "all classes /
     all learners / all students", "all teachers / all staff", or a teacher's name ("Mr Mukono").
A paragraph that names nobody belongs to the note above it. A note that names nobody at all is listed in
`problems`, so nothing is guessed.
classes = ['9N', ...];  teachers = [(code, name), ...]
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from rules_word import W, _p, _table           # the same small Word writer as the rules template

ALL_CLASSES = r"(?:all|every|each)\s+(?:the\s+)?(?:classes|class|learners|students|pupils|grades|streams)"
ALL_TEACHERS = r"(?:all|every|each)\s+(?:the\s+)?(?:teachers|teacher|staff|members of staff|tutors)|\bstaff\b"
TITLES = r"(?:MR|MRS|MS|MISS|MADAM|MDM|TR|TCHR|TEACHER|SIR|DR|PROF|REV|FR)\.?"


def _n(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def _class_rx(name):
    """'9N' / '10 A' -> a pattern that finds the class written with or without the space: 9N = 9 N, 10A = 10 A
    (not inside other words)."""
    parts = re.findall(r"[A-Z]+|\d+", _n(name))
    if not parts:
        return None
    body = r"[\s\-./]*".join(re.escape(p) for p in parts)
    return re.compile(r"(?<![A-Z0-9])(?:(?:GRADE|FORM|CLASS|GR|F)\.?\s*)?" + body + r"(?![A-Z0-9])", re.I)


def _surname_rx(name):
    """'MR. PETERSON K.' -> finds 'Peterson', 'Mr Peterson', 'Mr. Peterson K.'"""
    words = [w for w in re.findall(r"[A-Z][A-Z'\-]+", re.sub(TITLES + r"(?=\s)", " ", _n(name) + " ")) if len(w) > 2]
    if not words:
        return None
    return re.compile(r"(?<![A-Z])(?:" + "|".join(re.escape(w) for w in words) + r")(?![A-Z])", re.I), words


def find_targets(text, classes, teachers):
    """-> ([{"to": classes|teachers|class|teacher, "name", "label"?}], text to show)"""
    text = str(text or "").strip()
    crx = [(c, _class_rx(c)) for c in classes]
    trx = [(code, name, _surname_rx(name)) for code, name in teachers if name]

    def scan(s, strict=False):
        out = []
        if re.search(ALL_CLASSES, s, re.I):
            out.append({"to": "classes", "name": ""})
        if re.search(ALL_TEACHERS, s, re.I):
            out.append({"to": "teachers", "name": ""})
        hits = []
        for c, rx in crx:
            if rx:
                for m in rx.finditer(s):
                    hits.append((m.start(), m.end(), c))
        # "9N" must not also count as "9" + "N": keep the longest match at each place
        hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
        taken, last_end = [], -1
        for a, b, c in hits:
            if a >= last_end:
                taken.append(c)
                last_end = b
        for c in dict.fromkeys(taken):
            out.append({"to": "class", "name": c})
        if not any(o["to"] == "class" for o in out):
            for code, name, r in trx:
                if r and r[0].search(s) and (not strict or len(r[1]) >= 1):
                    out.append({"to": "teacher", "name": code, "label": f"{code} · {name}"})
            if strict:                                          # "6: …" or "Teacher 6: …" in the "For" part
                for code, name in teachers:
                    if re.fullmatch(r"(?:TEACHER\s*|TR\.?\s*)?" + re.escape(_n(code)), _n(s)):
                        out.append({"to": "teacher", "name": code, "label": f"{code} · {name}"})
        if any(o["to"] == "classes" for o in out):
            out = [o for o in out if o["to"] != "class"]
        if any(o["to"] == "teachers" for o in out):
            out = [o for o in out if o["to"] != "teacher"]
        seen, uniq = set(), []
        for o in out:
            k = (o["to"], o["name"])
            if k not in seen:
                seen.add(k)
                uniq.append(o)
        return uniq

    m = re.match(r"^\s*(?:for\s+)?([^:\n]{1,60}?)\s*[:\-–]\s+(.+)$", text, re.S | re.I)
    if m:
        who = scan(m.group(1), strict=True)
        if who:
            return who, m.group(2).strip()
    return scan(text), text


# ------------------------------------------------------------------------------------------------ Word template
def make_template(dest, school="", classes=(), teachers=()) -> Path:
    import zipfile as Z
    ex_c = list(classes)[0] if classes else "9N"
    ex_c2 = list(classes)[1] if len(classes) > 1 else "9S"
    ex_t = next((n for _, n in teachers if n), "MR KAMAU")
    body = [
        _p("PREPFIX Timetable Toolkit — notes under the timetables", bold=True, size=36, color="12284C", space_after=60),
        _p(school or "School name", bold=True, size=26, color="1E7F5C", space_after=160),
        _p("How to write the notes", bold=True, size=24, color="12284C"),
        _p("Write each note as its own paragraph below the line “NOTES START HERE”. Start it with who it is for and a "
           "colon — or simply mention the class or teacher in the note. PREPFIX finds who each note is for; there is "
           "nothing to pick from a list.", size=21, space_after=80),
        _p("Examples:", bold=True, size=21, space_after=40),
    ]
    for ex in [f"{ex_c}: Bring your revision books on Monday.",
               f"{ex_c} and {ex_c2}: Science practical on Thursday in the lab.",
               f"{ex_c} will have a class meeting on Friday after lunch.",
               "All classes: Half term starts on Friday. Clear your desks and lockers.",
               "All teachers: Staff meeting on Friday at 4:20 pm in the staffroom.",
               f"{ex_t}: Please collect the new class lists from the office."]:
        body.append(_p("     " + ex, size=20, color="555555", italic=True, space_after=30))
    body += [
        _p("Write class names as they are in the timetable — with or without a space (10A and 10 A are the same "
           "class). A paragraph that names nobody belongs to the note above it (for long notes). Paste freely from WhatsApp, "
           "email or another document. Delete the examples above if you like — they are not imported.", size=20,
           space_after=80),
        _p("Then in PREPFIX: Import & Run → 📌 Add / edit notes → “Import notes from file” → choose this file. "
           "PREPFIX shows who each note goes to before adding it.", size=20, space_after=160),
        _p("NOTES START HERE", bold=True, size=24, color="C9A227", space_after=120),
        _p(""), _p(""), _p(""),
    ]
    if classes or teachers:
        body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        body.append(_p("Classes and teachers in this timetable", bold=True, size=22, color="12284C"))
        if classes:
            body.append(_p("Classes: " + ",  ".join(classes), size=19))
        if teachers:
            body.append(_p("Teachers: " + "   ".join(f"{c} · {n}" if n else c for c, n in teachers), size=19))
        body.append(_p("(This page is only a reminder; it is not imported.)", size=17, color="7A7464", italic=True))
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1000" w:right="1000" w:bottom="1000" '
            'w:left="1000" w:header="500" w:footer="500" w:gutter="0"/></w:sectPr>')
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>'
           + "".join(body) + sect + "</w:body></w:document>")
    from rules_word import _parts
    dest = Path(dest)
    with Z.ZipFile(dest, "w", Z.ZIP_DEFLATED) as z:
        for name, data in _parts(doc).items():
            z.writestr(name, data)
    return dest


# ------------------------------------------------------------------------------------------------ reading
def _paragraphs(path) -> list:
    """Every paragraph's text, in order (table cells too: a table row 'For | Note' is read as 'For: Note')."""
    with zipfile.ZipFile(str(path)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(f"{{{W}}}body")
    out = []

    def ptext(p):
        return "".join(t.text or "" for t in p.iter(f"{{{W}}}t")).strip()
    for el in body:
        if el.tag == f"{{{W}}}p":
            out.append(ptext(el))
        elif el.tag == f"{{{W}}}tbl":
            for tr in el.iter(f"{{{W}}}tr"):
                cells = [" ".join(ptext(p) for p in tc.iter(f"{{{W}}}p")).strip() for tc in tr.findall(f"{{{W}}}tc")]
                cells = [c for c in cells if c]
                if len(cells) >= 2 and _n(cells[0]) not in ("FOR", "TO", "WHO"):
                    out.append(f"{cells[0]}: {' '.join(cells[1:])}")
                elif len(cells) == 1:
                    out.append(cells[0])
            out.append("")
    return out


def read_notes(path, classes, teachers):
    """-> (notes, problems). problems = [(paragraph number, text, reason)]."""
    if Path(path).suffix.lower() in (".xlsx", ".xlsm", ".csv"):          # older Excel templates still work
        import notes_file
        return notes_file.read_notes(path, classes, teachers)
    paras = _paragraphs(path)
    start = next((i + 1 for i, t in enumerate(paras) if _n(t).startswith("NOTES START HERE")), None)
    if start is None:                                    # any Word file: read it all
        start = 0
    stop = next((i for i in range(start, len(paras)) if _n(paras[i]).startswith("CLASSES AND TEACHERS IN THIS TIMETABLE")),
                len(paras))
    notes, problems, cur = [], [], None
    for i in range(start, stop):
        t = paras[i].strip()
        if not t:
            cur = None if cur is not None and cur.get("_closed") else cur
            continue
        who, text = find_targets(t, classes, teachers)
        if who:
            cur = {"who": who, "text": text, "n": i + 1}
            notes.append(cur)
            continue
        m = re.match(r"^\s*(?:for\s+)?(\d{1,2}\s*[A-Za-z]{1,3}(?:\s*(?:,|and|&)\s*\d{1,2}\s*[A-Za-z]{1,3})*)\s*:", t, re.I)
        if m:                                            # it starts like a class ("10c: …") but there is no such class
            problems.append((i + 1, t[:80], f"there is no class “{m.group(1).strip()}” in this timetable"))
            cur = None
        elif cur is not None:
            cur["text"] += "\n" + t                       # the note above goes on
        else:
            problems.append((i + 1, t[:80], "it does not say which class or teacher it is for "
                                            "(start with e.g. “9N:” or “All classes:”)"))
    # ONE note per class / teacher: several paragraphs for the same class become one statement
    out, at = [], {}
    for n in notes:
        for w in n["who"]:
            k = (w["to"], w.get("name", ""))
            if k in at:
                if n["text"] not in at[k]["text"]:
                    at[k]["text"] += "\n" + n["text"]
            else:
                at[k] = dict(w, text=n["text"])
                out.append(at[k])
    return out, problems


def one_per_target(notes):
    """Keep ONE note for each class / teacher / 'every class' / 'every teacher': the newest wins."""
    last = {}
    for n in notes:
        last[(n.get("to"), n.get("name", ""))] = n
    seen, out = set(), []
    for n in reversed(notes):
        k = (n.get("to"), n.get("name", ""))
        if k not in seen and last[k] is n:
            seen.add(k)
            out.append(n)
    return list(reversed(out))
