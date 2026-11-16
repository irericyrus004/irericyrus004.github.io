"""
NOTES TEMPLATE - many notes at once from an Excel file (or .csv).

    make_template(dest, classes, teachers)     -> writes "PREPFIX notes template.xlsx"
    read_notes(path, classes, teachers)        -> (notes, problems)

The file has one note per row:   For | Note
"For" is one of:  Every class · Every teacher · a class name (11 A) · a teacher (code, name, or "6 · MR. PETERSON K.").
A pick-list in the "For" column offers exactly those, taken from the loaded timetable.
Rows whose "For" cannot be matched are NOT added: they come back in `problems` so they can be corrected.
"""
from __future__ import annotations

import re
from pathlib import Path

EVERY_CLASS, EVERY_TEACHER = "Every class", "Every teacher"


def _n(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def make_template(dest, classes: list, teachers: list) -> Path:
    """classes = ['9N', ...]; teachers = [(code, name), ...]"""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Notes"
    ws.append(["For", "Note"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="12284C")
    ex_class = classes[0] if classes else "11 A"
    ex_t = teachers[0] if teachers else ("6", "MR. PETERSON K.")
    for row in ([EVERY_CLASS, "Half term break starts on Friday. Clear your desks and lockers."],
                [ex_class, f"{ex_class}: Bring your revision books on Monday."],
                [EVERY_TEACHER, "Staff meeting on Friday at 4:20 pm in the staffroom."],
                [f"{ex_t[0]} · {ex_t[1]}", "Please collect the new class lists from the office."]):
        ws.append(row)
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 100
    for r in ws.iter_rows(min_row=2, max_row=400):
        r[1].alignment = Alignment(wrap_text=True, vertical="top")
        r[0].alignment = Alignment(vertical="top")
    # the pick-list for "For": every class and every teacher of the loaded timetable
    names = wb.create_sheet("Names")
    choices = [EVERY_CLASS, EVERY_TEACHER] + list(classes) + [f"{c} · {n}" for c, n in teachers]
    for v in choices:
        names.append([v])
    names.column_dimensions["A"].width = 40
    dv = DataValidation(type="list", formula1=f"=Names!$A$1:$A${max(1, len(choices))}", allow_blank=True,
                        showErrorMessage=False)
    dv.add("A2:A400")
    ws.add_data_validation(dv)
    how = wb.create_sheet("How to")
    for line in [
        "ONE NOTE PER ROW on the 'Notes' sheet. Keep the first row (For | Note). Delete the example rows.",
        "For  - click the cell and pick from the list: Every class, Every teacher, a class, or a teacher.",
        "       You can also type a class name (11 A), a teacher's code (6) or a teacher's name (MR. PETERSON K.).",
        "Note - type or paste the note. Several lines in one cell are fine (Alt + Enter starts a new line).",
        "Then in PREPFIX: Publish tab -> Notes under the timetables -> 'Import notes from file'.",
        "Rows PREPFIX cannot match are listed so you can correct them; nothing is guessed.",
    ]:
        how.append([line])
    how.column_dimensions["A"].width = 110
    dest = Path(dest)
    wb.save(str(dest))
    return dest


def _rows(path: Path) -> list:
    if path.suffix.lower() == ".csv":
        import csv
        raw = path.read_bytes()
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        try:
            dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return [list(r) for r in csv.reader(text.splitlines(), dialect)]
    import openpyxl
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    ws = wb["Notes"] if "Notes" in wb.sheetnames else wb.worksheets[0]
    return [["" if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True)]


def read_notes(path, classes: list, teachers: list):
    """-> (notes, problems). notes are ready for PREPFIX; problems = [(row number, text, reason)]."""
    rows = _rows(Path(path))
    cls = {_n(c): c for c in classes}
    tby = {}
    for code, name in teachers:
        lab = f"{code} · {name}"
        for k in (code, name, lab, f"{code} {name}", f"{code}. {name}"):
            if k:
                tby[_n(k)] = (code, lab)
    notes, problems = [], []
    start = 1 if rows and _n(rows[0][0] if rows[0] else "") in ("FOR", "TO", "CLASS / TEACHER") else 0
    for i, r in enumerate(rows[start:], start + 1):
        r = list(r) + ["", ""]
        who, text = str(r[0]).strip(), str(r[1]).strip()
        if not who and not text:
            continue
        if not text:
            problems.append((i, who, "the Note cell is empty"))
            continue
        k = _n(who)
        if k in ("EVERY CLASS", "ALL CLASSES", "ALL", "CLASSES", "EVERYONE"):
            notes.append({"to": "classes", "name": "", "text": text})
        elif k in ("EVERY TEACHER", "ALL TEACHERS", "TEACHERS", "STAFF", "ALL STAFF"):
            notes.append({"to": "teachers", "name": "", "text": text})
        elif k in cls:
            notes.append({"to": "class", "name": cls[k], "text": text})
        elif k in tby:
            code, lab = tby[k]
            notes.append({"to": "teacher", "name": code, "label": lab, "text": text})
        else:
            problems.append((i, who or "(empty)", "not a class or teacher in this timetable"))
    return notes, problems
