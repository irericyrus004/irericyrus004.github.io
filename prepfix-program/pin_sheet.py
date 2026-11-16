"""THE PIN SHEET - one slip per teacher (cut along the lines and hand out, e.g. at a staff meeting):
the school's link, the teacher's name, phone number and 4-digit PIN. A teacher types the number and the PIN once
on their phone. Somebody who only knows a teacher's number cannot open the timetables."""
from __future__ import annotations

import zipfile
from pathlib import Path

import prepfix_lock as LOCK
from rules_word import W, _p, _parts, _run


def _slip(school, link, p, width):
    paras = [
        _p("PREPFIX Timetable Toolkit — your timetable on your phone", bold=True, size=18, color="12284C", space_after=40),
        _p(school, bold=True, size=20, color="1E7F5C", space_after=80),
        f'<w:p><w:pPr><w:spacing w:after="20"/></w:pPr>{_run("Teacher:  ", size=20)}{_run(p["name"], bold=True, size=22)}</w:p>',
        f'<w:p><w:pPr><w:spacing w:after="20"/></w:pPr>{_run("Phone:  ", size=20)}'
        f'{_run(LOCK.show_phone(p["phone"]) if p.get("phone") else "(ask for your number to be added)", bold=True, size=22)}</w:p>',
        f'<w:p><w:pPr><w:spacing w:after="60"/></w:pPr>{_run("PIN:  ", size=24)}'
        f'{_run(" ".join(p.get("pin", "")), bold=True, size=44, color="B3261E")}</w:p>',
        _p("1. Open: " + link, size=17, space_after=10),
        _p("2. Type your phone number and this PIN — once. The app opens on your own timetable.", size=17, space_after=10),
        _p("Keep the PIN private. It works on ONE phone. Changed phone? Tell the timetable office.", size=16,
           color="667085", italic=True, space_after=0),
    ]
    return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:tcMar><w:top w:w="140" w:type="dxa"/>'
            f'<w:left w:w="160" w:type="dxa"/><w:bottom w:w="140" w:type="dxa"/><w:right w:w="160" w:type="dxa"/>'
            f'</w:tcMar></w:tcPr>{"".join(paras)}</w:tc>')


def make(dest, school: str, link: str, people: list) -> Path:
    people = [p for p in people if p.get("pin")]
    widths = 4950
    borders = "".join(f'<w:{b} w:val="dashed" w:sz="8" w:space="0" w:color="7A7464"/>'
                      for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
    rows = []
    for i in range(0, len(people), 2):
        pair = people[i:i + 2]
        cells = "".join(_slip(school, link, p, widths) for p in pair)
        if len(pair) == 1:
            cells += f'<w:tc><w:tcPr><w:tcW w:w="{widths}" w:type="dxa"/></w:tcPr><w:p/></w:tc>'
        rows.append(f'<w:tr><w:trPr><w:cantSplit/></w:trPr>{cells}</w:tr>')
    table = (f'<w:tbl><w:tblPr><w:tblW w:w="{2 * widths}" w:type="dxa"/><w:tblBorders>{borders}</w:tblBorders>'
             f'<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid><w:gridCol w:w="{widths}"/><w:gridCol w:w="{widths}"/>'
             f'</w:tblGrid>{"".join(rows)}</w:tbl>')
    head = [_p(f"PIN sheet — {school}", bold=True, size=30, color="12284C", space_after=40),
            _p(f"{len(people)} teachers. Cut along the dashed lines and give each teacher their own slip. "
               "Keep this sheet private.", size=18, color="667085", space_after=120)]
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="700" w:right="700" w:bottom="700" '
            'w:left="700" w:header="400" w:footer="400" w:gutter="0"/></w:sectPr>')
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>'
           + "".join(head) + table + "<w:p/>" + sect + "</w:body></w:document>")
    dest = Path(dest)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in _parts(doc).items():
            z.writestr(name, data)
    return dest
