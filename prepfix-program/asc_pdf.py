"""
aSc Timetables PDF printouts -> the same data PREPFIX gets from a FET folder or a .roz file.

aSc prints one timetable per page:
    line 1  the timetable's name            TIMETABLE TERM 3 2026 REVISED 2
    line 2  whose timetable it is            3K      or      Teacher MR. MBOTHU J.M
    line 3  the school                       KIANYAGA BOYS' HIGH SCHOOL, ...
    a grid: days down the side (Mo Tu We Th Fr), lessons 1, 2, ... and breaks across the top with their times.

    CLASS page:   a box holds the subject in big letters and the teachers' short names (numbers) in small letters.
    TEACHER page: a box holds the subject in small letters at the top and the classes ("4L1/4L2") in big letters.
    A box two lessons wide is a double lesson.

Give it the class PDF, the teachers PDF, or both (best: the classes come from the class pages and the teachers'
full names from the teacher pages).

    data = scan_pdfs(["class_tt.pdf", "teachers.pdf"], school="ST. X", timetable="TERM 3 2026")
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

DAY_KEYS = {"mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6}
DAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
TIME = re.compile(r"(\d{1,2})[:.](\d{2})\s*-\s*(\d{1,2})[:.](\d{2})")


class PdfError(ValueError):
    pass


def _plumber():
    try:
        import pdfplumber
        return pdfplumber
    except ImportError:
        import importlib
        import subprocess
        import sys
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "pdfplumber"], timeout=300,
                           check=True, capture_output=True)
            importlib.invalidate_caches()
            import pdfplumber
            return pdfplumber
        except Exception:
            raise PdfError("The PDF helper (pdfplumber) is missing and could not be installed. Connect to the "
                           "internet once and try again.")


def _lines(words, tol=2.5):
    """Words -> lines of text (top to bottom, left to right)."""
    out = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if out and abs(out[-1][0] - w["top"]) <= tol:
            out[-1][1].append(w)
        else:
            out.append([w["top"], [w]])
    return [" ".join(x["text"] for x in sorted(ws, key=lambda x: x["x0"])) for _, ws in out]


def _inside(w, box):
    cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _join(lines):
    """Subject lines back into one name: "Mat" + "hs" -> "Maths", but "CHEM/COMP" + "DOUBLE" -> "CHEM/COMP DOUBLE"."""
    out = ""
    for ln in lines:
        ln = ln.strip()
        if out and re.match(r"(?i)double\b", ln) and not out.endswith(" "):
            out += " "
        out += ln
    return out.strip()


def _whole(tok):
    return bool(re.search(r"\d", tok) and re.search(r"[A-Za-z]", tok))


def _classes(lines):
    """Class names from the lines of a box: "4L1/4L2" + "4L3/4L4"; a narrow box may break one name ("10" + "W")."""
    out = []
    for i, ln in enumerate(lines):
        toks = [x for x in re.split(r"[/,\s]+", ln) if x]
        if not toks:
            continue
        if out and i and not lines[i - 1].rstrip().endswith("/") and (not _whole(out[-1]) or not _whole(toks[0])):
            out[-1] += toks.pop(0)
        out.extend(toks)
    return out


def _read_page(page):
    """-> dict(kind, name, title, school, cols, cells) or None for a page that is not an aSc timetable."""
    tables = page.find_tables()
    if not tables:
        return None
    tb = max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]))
    words = page.extract_words(extra_attrs=["size"], keep_blank_chars=False)
    above = [w for w in words if w["bottom"] <= tb.bbox[1] + 1]
    head = _lines(above)
    if len(head) < 2:
        return None
    title, who = _norm(head[0]), _norm(head[1])
    school = _norm(head[2]) if len(head) > 2 else ""
    rows = tb.rows
    if len(rows) < 2:
        return None
    # ---- columns from the header row: a number = a lesson, words = a break; times under them
    cols = []
    for c in rows[0].cells:
        if not c:
            continue
        txt = _norm(" ".join(w["text"] for w in words if _inside(w, c)))
        if not txt:
            cols.append(None)                                 # the corner box above the day names
            continue
        m = TIME.search(txt)
        label = _norm(TIME.sub("", txt))
        cols.append({"x0": c[0], "x1": c[2], "label": label, "lesson": bool(re.fullmatch(r"\d{1,2}", label)),
                     "start": int(m.group(1)) * 60 + int(m.group(2)) if m else None,
                     "end": int(m.group(3)) * 60 + int(m.group(4)) if m else None})
    if sum(1 for c in cols if c and c["lesson"]) < 2:
        return None
    kind = "teacher" if re.match(r"(?i)teacher\b", who) else "room" if re.match(r"(?i)(class)?room\b", who) else "class"
    name = re.sub(r"(?i)^teacher\s+", "", who).strip()
    cells = []
    for r in rows[1:]:
        boxes = [c for c in r.cells if c]
        if not boxes:
            continue
        dtxt = _norm(" ".join(w["text"] for w in words if _inside(w, boxes[0]))).lower()[:2]
        if dtxt not in DAY_KEYS:
            continue
        day = DAY_KEYS[dtxt]
        for c in boxes[1:]:
            covered = [k for k, col in enumerate(cols) if col and col["x0"] >= c[0] - 1 and col["x1"] <= c[2] + 1]
            lessons = [k for k in covered if cols[k]["lesson"]]
            if not lessons:
                continue                                      # a break column
            ws = [w for w in words if _inside(w, c)]
            if not ws:
                continue
            big = max(w["size"] for w in ws)
            small = min(w["size"] for w in ws)
            if kind == "class":
                main = [w for w in ws if w["size"] > small + 0.5] or ws
                tiny = [w for w in ws if w["size"] <= small + 0.5] if len(main) < len(ws) else []
                subj = _join(_lines(main))          # "Mat" + "hs" -> "Maths"; "Chem D" stays
                codes = [x for x in re.split(r"[\s/,]+", " ".join(w["text"] for w in sorted(tiny, key=lambda w: (round(w["top"]), w["x0"])))) if x]
                cells.append({"d": day, "cols": lessons, "s": subj, "who": codes})
            else:
                label = [w for w in ws if w["size"] <= small + 0.3] if big - small > 0.5 else []
                rest = [w for w in ws if w not in label]
                if label:                                     # small letters = subject, big letters = classes
                    subj = _join(_lines(label))
                    rest_ls = _lines(rest)
                else:                                         # one size only: first line is the subject
                    ls = _lines(ws)
                    subj, rest_ls = ls[0], ls[1:]
                groups = _classes(rest_ls)
                cells.append({"d": day, "cols": lessons, "s": subj, "who": groups})
    return {"kind": kind, "name": name, "title": title, "school": school, "cols": cols, "cells": cells}


def scan_pdfs(paths, school: str = "", timetable: str = "", log=print) -> dict:
    pl = _plumber()
    pages, stamp = [], ""
    for p in paths:
        p = Path(p)
        try:
            with pl.open(str(p)) as pdf:
                got = 0
                for pg in pdf.pages:
                    if not stamp:                       # aSc prints "Timetable generated: <date> <time>" on each page
                        try:
                            m = re.search(r"generated\s*:?\s*([0-9]{1,4}[./-][0-9]{1,2}[./-][0-9]{1,4}(?:[ ,]+[0-9]{1,2}:[0-9]{2}(?:\s*[AaPp][Mm])?)?)",
                                          pg.extract_text() or "")
                            stamp = m.group(1).strip() if m else ""
                        except Exception:
                            pass
                    r = _read_page(pg)
                    if r:
                        pages.append(r)
                        got += 1
                if not got:
                    if not any((pg.extract_text() or "").strip() for pg in pdf.pages):
                        raise PdfError(f"{p.name} has no text in it (a scan or photo). Print it to PDF again from aSc.")
                    raise PdfError(f"{p.name} does not look like an aSc timetable printout (no days and lessons grid).")
        except PdfError:
            raise
        except Exception as e:
            raise PdfError(f"{p.name} could not be read as a PDF: {e}")
        log(f"Read {p.name}: {got} page(s)")
    cls_pages = [p for p in pages if p["kind"] == "class"]
    tch_pages = [p for p in pages if p["kind"] == "teacher"]
    if not cls_pages and not tch_pages:
        raise PdfError("No class or teacher timetables were found in the PDF(s).")

    # ---- one spelling per subject: a long name wraps differently on each page ("CHEM/BC" + "BS" or "CHEM/BC/" + "BS")
    skey = lambda x: re.sub(r"[^A-Z0-9]", "", x.upper())
    best = {}
    for pg in cls_pages + tch_pages:
        for c in pg["cells"]:
            k = skey(c["s"])
            score = (c["s"].count("/") + c["s"].count(" "), pg["kind"] == "class")
            if k not in best or score > best[k][0]:
                best[k] = (score, c["s"])
    for pg in pages:
        for c in pg["cells"]:
            c["s"] = best.get(skey(c["s"]), (0, c["s"]))[1]

    # ---- one list of periods for everyone (pages may differ: a teacher page can carry an extra lunch column)
    periods, key_of = [], {}
    for pg in sorted(pages, key=lambda p: -len(p["cols"])):
        last = -1
        for col in pg["cols"]:
            if not col:
                continue
            k = (col["label"].upper(), col["start"], col["end"])
            if k in key_of:
                last = key_of[k]
                continue
            p = {"label": col["label"].upper(), "start": col["start"] or 0, "end": col["end"] or 0, "brk": not col["lesson"]}
            periods.insert(last + 1, p)
            for kk, v in list(key_of.items()):
                if v > last:
                    key_of[kk] = v + 1
            key_of[k] = last + 1
            last += 1
    n = 0
    for p in periods:
        p["time"] = f"{p['start'] // 60}:{p['start'] % 60:02d}-{p['end'] // 60}:{p['end'] % 60:02d}" if p["end"] else ""
        p["pm"] = p["start"] >= 13 * 60
        if not p["brk"]:
            n += 1
            p["num"], p["label"], p["n"] = p["label"], f"L{n}", n
    P = len(periods)

    def pidx(pg, cols):
        out = []
        for k in cols:
            c = pg["cols"][k]
            out.append(key_of[(c["label"].upper(), c["start"], c["end"])])
        return out

    # ---- teacher codes (numbers on class pages) <-> teachers' names (teacher pages), matched by where they teach
    slots_t = defaultdict(set)                            # (day, period, class) -> teacher names
    for pg in tch_pages:
        for c in pg["cells"]:
            for j in pidx(pg, c["cols"]):
                for g in c["who"]:
                    slots_t[(c["d"], j, g)].add(pg["name"])
    votes = defaultdict(Counter)
    for pg in cls_pages:
        for c in pg["cells"]:
            if not c["who"]:
                continue
            for j in pidx(pg, c["cols"]):
                there = slots_t.get((c["d"], j, pg["name"]), ())
                for code in c["who"]:
                    for t in there:
                        votes[code][t] += 1.0 / (len(c["who"]) * len(there))
    # strongest matches first; one name per number and one number per name
    code_name, used = {}, set()
    for score, code, t in sorted(((v, code, t) for code, cnt in votes.items() for t, v in cnt.items()), reverse=True):
        if code not in code_name and t not in used:
            code_name[code] = t
            used.add(t)

    # ---- lessons
    lessons = {}                                          # (day, first period, subject) -> lesson

    def add(d, js, subj, classes, teachers):
        js = sorted(js)
        k = (d, js[0], subj.upper(), tuple(sorted(classes)) if not cls_pages else None)
        if cls_pages and k not in lessons:
            # with class pages the same lesson can come from several classes: join by teachers too
            for kk, L in lessons.items():
                if kk[:3] == k[:3] and set(L["t"]) & set(teachers) and teachers:
                    k = kk
                    break
            else:
                k = k + (tuple(sorted(teachers)) if teachers else tuple(sorted(classes)),)
        L = lessons.setdefault(k, {"d": d, "p": js[0], "js": js, "c": [], "s": subj, "t": []})
        if len(js) > len(L["js"]):
            L["js"] = js
        for c in classes:
            if c not in L["c"]:
                L["c"].append(c)
        for t in teachers:
            if t not in L["t"]:
                L["t"].append(t)

    names = {}                                            # code -> full name
    if cls_pages:
        for pg in cls_pages:
            for c in pg["cells"]:
                add(c["d"], pidx(pg, c["cols"]), c["s"], [pg["name"]], c["who"])
        for code, nm in code_name.items():
            names[code] = nm
        known = set(code_name.values())
        # teachers who appear only on teacher pages (no number found on any class page)
        for pg in tch_pages:
            if pg["name"] not in known:
                code = (re.search(r"(\d+)\s*$", pg["name"]) or [None, None])[1] or pg["name"]
                if code in names and names[code] != pg["name"]:
                    code = pg["name"]
                names[code] = pg["name"]
                for c in pg["cells"]:
                    add(c["d"], pidx(pg, c["cols"]), c["s"], c["who"], [code])
    else:
        for pg in tch_pages:
            code = (re.search(r"(\d+)\s*$", pg["name"]) or [None, None])[1] or pg["name"]
            if code in names:
                code = pg["name"]
            names[code] = pg["name"]
            for c in pg["cells"]:
                js = sorted(pidx(pg, c["cols"]))
                k = (c["d"], js[0], c["s"].upper(), tuple(sorted(c["who"])))
                L = lessons.setdefault(k, {"d": c["d"], "p": js[0], "js": js, "c": list(c["who"]), "s": c["s"], "t": []})
                L["t"].append(code)
    for L in lessons.values():
        for t in L["t"]:
            names.setdefault(t, t)

    # ---- grids, exactly like a .roz
    lesson_list = sorted(lessons.values(), key=lambda L: (L["d"], L["p"]))
    D = max(5, max((L["d"] for L in lesson_list), default=4) + 1)
    blank = lambda: [["" for _ in range(P)] for _ in range(D)]

    def nat(s):
        return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)]
    cname = sorted({c for L in lesson_list for c in L["c"]} | {p["name"] for p in cls_pages}, key=nat)
    tcode = sorted(names, key=nat)
    tg = {c: blank() for c in tcode}
    cg = {c: blank() for c in cname}
    mg = {c: blank() for c in cname}

    def put(grid, dd, j, cell, span):
        old = grid[dd][j]
        if isinstance(old, dict):
            for k, v in cell.items():
                if k in ("s", "t", "c") and v and v not in old.get(k, "").split(" / "):
                    old[k] = (old[k] + " / " + v) if old.get(k) else v
            return
        grid[dd][j] = dict(cell)
        for k in range(1, span):
            if j + k < P:
                grid[dd][j + k] = "^"

    out_lessons = []
    for L in lesson_list:
        # the boxes of a double sit side by side; an extra break column (e.g. one grade's lunch) splits them
        runs, cur = [], [L["js"][0]]
        for x in L["js"][1:]:
            if x == cur[-1] + 1:
                cur.append(x)
            else:
                runs.append(cur)
                cur = [x]
        runs.append(cur)
        codes = L["t"]
        for run in runs:
            j, span = run[0], len(run)
            dbl = {"g": "DBL"} if len(L["js"]) > 1 else {}
            for t in codes:
                put(tg[t], L["d"], j, {"c": ", ".join(L["c"]), "s": L["s"],
                                       **({"t": ", ".join(codes)} if len(codes) > 1 else {}), **dbl}, span)
            for c in L["c"]:
                if c not in cg:
                    continue
                put(cg[c], L["d"], j, {"s": L["s"], **({"t": ", ".join(codes)} if codes else {}), **dbl}, span)
                put(mg[c], L["d"], j, {"c": c, "s": L["s"], **({"t": ", ".join(codes)} if codes else {}), **dbl}, span)
            out_lessons.append({"d": L["d"], "p": j, "n": span, "c": list(L["c"]), "s": L["s"], "t": list(codes), "r": []})
    for g in list(cg.values()) + list(tg.values()) + list(mg.values()):
        for row in g:
            for j, p in enumerate(periods):
                if p["brk"] and row[j] == "":
                    row[j] = "X"
    for p in periods:
        p.pop("num", None)

    load = lambda g: sum(1 for row in g for c in row if isinstance(c, dict) or c == "^")
    first = (cls_pages or tch_pages)[0]
    title = (timetable or first["title"]).upper()
    il = [x for x in ((school or "").upper(), title) if x]
    srcs = ", ".join(Path(p).name for p in paths)
    data = {
        "format": 2,
        "periods": periods,
        "days": [{"label": DAY_LABELS[i], "wd": i + 1} for i in range(D)],
        "teachers": [{"id": f"T{i + 1}", "code": c, "name": names[c], "grid": tg[c], "load": load(tg[c])}
                     for i, c in enumerate(tcode)],
        "classes": [{"id": f"C{i + 1}", "name": c, "grid": cg[c]} for i, c in enumerate(cname)],
        "master": [{"id": f"M{i + 1}", "name": c, "grid": mg[c]} for i, c in enumerate(cname)],
        "rooms": [],
        "institution": " ".join(il),
        "institution_lines": il,
        "institutions": {"classes": " ".join(il)},
        "colours": {},
        "fet": {"version": "", "when": stamp},
        "source": "aSc Timetables PDF (" + srcs + ")",
        "pdf_title": first["title"],
        "pdf_school": first["school"],
        "_lessons": out_lessons,
        "_unplaced": [],
    }
    unnamed = [c for c in tcode if names[c] == c] if tch_pages else []
    log(f"✔ aSc PDF: {len(cls_pages)} class page(s), {len(tch_pages)} teacher page(s) → {len(tcode)} teachers · "
        f"{len(cname)} classes · {len(out_lessons)} lessons · {D} days · {n} lessons a day")
    if cls_pages and not tch_pages:
        log("ℹ Only class pages: teachers are shown by their aSc number. Add the teachers PDF too for their names.")
    elif unnamed:
        log(f"ℹ {len(unnamed)} teacher number(s) could not be matched to a name: {', '.join(unnamed[:12])}")
    return data
