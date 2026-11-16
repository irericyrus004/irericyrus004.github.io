"""
aSc TIMETABLES (.roz) -> the same data PREPFIX gets from a FET folder.

aSc keeps a timetable in its own binary file (it starts with "ASCTT"). The layout is not published, so this reader
was worked out from real files. It reads:
    periods (lessons and breaks, with times), subjects, teachers (name + short name = code),
    classes, student groups (whole class / Group 1 / Boys ...), lessons (subject, classes, teachers, length)
    and the CARDS - where each lesson was placed (day, period).
It checks itself as it goes; if a file does not look the way it expects it stops with a clear message instead of
guessing.

    data = scan_roz("TERM 3 2026.roz", school="ST. X", timetable="TERM 3 2026")
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

MARK = bytes.fromhex("020000000200000002000100")           # every object in the file starts with this
HEAD = re.compile(rb"(.{4})\x00\x00\x00\x00\x00\x01\x00\x00\x00(.{4})\x00\x00\x00\x00.{3}" + re.escape(MARK), re.S)
OBJ = re.compile(rb"\x02\x00\x01\x00.{8}\x00{7}\x02", re.S)   # the end of an object's marker + id + its first byte
CARD = re.compile(rb"(.{4})\x01\x00\x00\x00\xff\xff\xff\xff(.{4})(.{4})\x00\x00\x00\x00(.{4})\x01\x00\x00\x00", re.S)
T_TEACHERS, T_GROUPS, T_LESSONS, T_GRADES = 1, 6, 7, 10
DAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


class AscError(ValueError):
    pass


def _i(b, o):
    return struct.unpack_from("<i", b, o)[0]


def _str_at(b, o):
    """A string stored as one length byte + the letters."""
    n = b[o]
    return b[o + 1:o + 1 + n].decode("cp1252", "replace"), o + 1 + n


def _names(rec):
    """The first strings of an object: (name, short name)."""
    o = 28                                               # after marker (12) + id (8) + 7 bytes + the 02 byte
    if len(rec) < 30 or rec[27] not in (0, 2):          # 0 = an object aSc keeps but marks (e.g. a teacher not used)
        return "", ""
    a, o = _str_at(rec, o)
    b, o = _str_at(rec, o)
    if a == "CLASSTT":                                   # classes carry an extra tag first
        a, o2 = b, o
        b, _ = _str_at(rec, o2)
    return a.strip(), b.strip()


def _is_teacher(rec):
    """A teacher object: name, short name, then 17 empty bytes (a subject has ff ff ff ff there)."""
    if len(rec) < 60 or rec[27] not in (0, 2):
        return False
    try:
        _, o = _str_at(rec, 28)
        _, o = _str_at(rec, o)
    except IndexError:
        return False
    return rec[o:o + 17] == bytes(17) and rec[o + 17] > 0


def _period(rec):
    """(number, name, start, end) or None. Times sit just before the first run of ff bytes."""
    if len(rec) < 60 or rec[27] != 2:
        return None
    k = rec.find(b"\xff\xff\xff\xff", 32)
    if k < 48:
        return None
    sh, sm, eh, em = struct.unpack_from("<4i", rec, k - 16)
    if not (0 <= sh < 24 and 0 <= sm < 60 and 0 <= eh < 24 and 0 <= em < 60 and sh * 60 + sm < eh * 60 + em):
        return None
    num = _i(rec, 28)
    name = ""
    m = re.match(rb"[\x00]{0,4}\x01([\x01-\x40])", rec[32:40])
    if m:
        name, _ = _str_at(rec, 32 + m.start(1))
    return num, name.strip(), sh * 60 + sm, eh * 60 + em


def _hm(m):
    return f"{m // 60}:{m % 60:02d}"


def scan_roz(path, school: str = "", timetable: str = "", log=print) -> dict:
    path = Path(path)
    d = path.read_bytes()
    if d[5:10] != b"ASCTT":
        raise AscError("This is not an aSc Timetables file (.roz).")
    offs = sorted({m.start() for m in re.finditer(re.escape(MARK), d)} |
                  {m.start() - 8 for m in OBJ.finditer(d) if m.start() >= 8})   # some objects carry a different first 8 bytes
    if len(offs) < 20:
        raise AscError("This aSc file has no timetable data in it.")
    recs = [d[o:(offs[i + 1] if i + 1 < len(offs) else len(d))] for i, o in enumerate(offs)]
    at = {o: i for i, o in enumerate(offs)}
    sec = {}
    for m in HEAD.finditer(d):
        cnt, typ = struct.unpack("<ii", m.group(1) + m.group(2))
        first = at.get(m.end() - len(MARK))
        if first is not None and typ not in sec:
            sec[typ] = (first, cnt)
    if T_TEACHERS not in sec and T_GROUPS in sec and T_GRADES in sec:
        # some aSc files do not mark where the teachers start: they are the run just before the student groups
        q0, k = sec[T_GROUPS][0], sec[T_GROUPS][0]
        while k - 1 >= sec[T_GRADES][0] + sec[T_GRADES][1] and _is_teacher(recs[k - 1]):
            k -= 1
        if k < q0:
            sec[T_TEACHERS] = (k, q0 - k)
    need = {T_TEACHERS: "teachers", T_GROUPS: "student groups", T_LESSONS: "lessons", T_GRADES: "grades"}
    miss = [v for k, v in need.items() if k not in sec]
    if miss:
        raise AscError("This aSc file is laid out differently from the ones PREPFIX knows (no " + ", ".join(miss) +
                       " found). Send the file to Cyrus Ireri, 0720872582.")

    # ---- periods (lessons and breaks), in time order
    per = [p for p in (_period(r) for r in recs[:sec[T_GRADES][0]]) if p]
    per.sort(key=lambda p: p[2])
    if not per:
        raise AscError("No lesson times were found in this aSc file.")
    periods, num_to_idx, n = [], {}, 0
    for num, name, s, e in per:
        brk = bool(name)
        p = {"label": name.upper() if brk else "", "time": f"{_hm(s)}-{_hm(e)}", "start": s, "end": e, "brk": brk,
             "pm": s >= 13 * 60}
        if not brk:
            n += 1
            p["label"], p["n"] = f"L{n}", n
            num_to_idx[num] = len(periods)
        periods.append(p)

    # ---- subjects, teachers, groups, classes
    g0, gn = sec[T_GRADES]
    t0, tn = sec[T_TEACHERS]
    s_recs = recs[g0 + gn:t0]
    subjects = [_names(r) for r in s_recs]                              # (name, short)
    teachers = [_names(r) for r in recs[t0:t0 + tn]]                     # (name, short = code)
    q0, qn = sec[T_GROUPS]
    groups = [_names(r)[0] for r in recs[q0:q0 + qn]]
    l0, ln = sec[T_LESSONS]
    c_end = min([l0] + [f for f, _ in sec.values() if q0 + qn <= f < l0])   # rooms may sit between classes and lessons
    classes = [_names(r) for r in recs[q0 + qn:c_end]]
    if not classes or qn % len(classes):
        raise AscError("The classes in this aSc file could not be matched to their student groups.")
    per_class = qn // len(classes)

    def group_label(gi):
        ci, k = divmod(gi, per_class)
        cls = classes[ci][1] or classes[ci][0]
        gname = groups[gi] if gi < len(groups) else ""
        return cls, ("" if k == 0 or gname.lower() in ("entire class", "whole class", "") else gname)

    # ---- lessons
    lessons = []
    for r in recs[l0:l0 + ln]:
        try:
            dur = 1 + _i(r, 41)
            per_week = _i(r, 45)                         # how many times a week aSc must place it
            subj = _i(r, 62)
            o = 66
            lists = []
            for _ in range(3):
                c = _i(r, o)
                if not 0 <= c <= 64:
                    raise ValueError
                lists.append([_i(r, o + 4 + 4 * k) for k in range(c)])
                o += 4 + 4 * c
        except (struct.error, ValueError):
            raise AscError("A lesson in this aSc file could not be read. Send the file to Cyrus Ireri, 0720872582.")
        grp, tch = lists[0], lists[1]
        if not (0 <= subj < len(subjects)) or any(not 0 <= g < qn for g in grp) or any(not 0 <= t < tn for t in tch) \
                or not 1 <= dur <= 4:
            raise AscError("A lesson in this aSc file points at a subject, class or teacher that is not there. "
                           "Send the file to Cyrus Ireri, 0720872582.")
        lessons.append({"subj": subj, "groups": grp, "teachers": tch, "dur": dur,
                        "want": per_week if 0 <= per_week <= 60 else 0})

    # ---- cards: where each lesson was placed
    region = d[offs[l0 + ln - 1]:offs[l0 + ln]] if l0 + ln < len(offs) else d[offs[l0 + ln - 1]:]
    cards, dropped = [], []                                # dropped = cards aSc left without a valid day / period
    for m in CARD.finditer(region):
        li, pnum, _flag, dm = struct.unpack("<iiii", b"".join(m.groups()))
        if not 0 <= li < len(lessons):
            continue
        day = dm.bit_length() - 1 if dm > 0 else -1
        if dm > 0 and dm == 1 << day and day < 7 and pnum in num_to_idx:
            cards.append((li, day, num_to_idx[pnum]))
        else:
            dropped.append(li)
    if not cards:
        raise AscError("This aSc file has no lessons placed on the timetable yet (generate it in aSc first).")

    days_used = max(c[1] for c in cards) + 1
    D, P = max(5, days_used), len(periods)
    blank = lambda: [["" for _ in range(P)] for _ in range(D)]
    tcode = [(s or n or f"T{i + 1}") for i, (n, s) in enumerate(teachers)]
    tname = [(n or s) for n, s in teachers]
    cname = [(s or n) for n, s in classes]
    sshort = [(s or n) for n, s in subjects]
    tg = {c: blank() for c in tcode}
    cg = {c: blank() for c in cname}
    mg = {c: blank() for c in cname}
    lesson_list, placed = [], 0

    def put(grid, dd, j, cell, span):
        """Write a lesson (and its '^' continuation boxes); a second lesson in the same box is joined to it."""
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

    # ---- aSc's own errors: lessons placed fewer times than aSc was told to, and cards with no valid place
    placed_n = {}
    for li, _, _ in cards:
        placed_n[li] = placed_n.get(li, 0) + 1
    unplaced = []
    for li, L in enumerate(lessons):
        got = placed_n.get(li, 0)
        if L["want"] and got < L["want"] or li in dropped:
            cls = list(dict.fromkeys(group_label(g)[0] for g in L["groups"]))
            unplaced.append({"s": sshort[L["subj"]], "c": ", ".join(cls),
                             "t": ", ".join(tname[t] for t in L["teachers"]) or "no teacher",
                             "want": L["want"], "placed": got, "dropped": dropped.count(li)})
    if unplaced:
        log(f"⚠ aSc left {sum(max(0, u['want'] - u['placed']) for u in unplaced)} lesson(s) unplaced "
            f"({len(unplaced)} lesson card group(s)) — see the check report.")

    for li, dd, j in sorted(cards, key=lambda c: (c[1], c[2])):
        L = lessons[li]
        span = max(1, min(L["dur"], P - j))
        # a double lesson never runs across a break: keep it to the lesson periods that follow
        while span > 1 and any(periods[j + k]["brk"] for k in range(1, span)):
            span -= 1
        cls, parts = [], []
        for g in L["groups"]:
            c, part = group_label(g)
            if c not in cls:
                cls.append(c)
            if part:
                parts.append(part)
        subj = sshort[L["subj"]] + (f" ({', '.join(dict.fromkeys(parts))})" if parts else "")
        codes = [tcode[t] for t in L["teachers"]]
        dbl = {"g": "DBL"} if span > 1 else {}
        for t in codes:
            put(tg[t], dd, j, {"c": ", ".join(cls), "s": subj, **({"t": ", ".join(codes)} if len(codes) > 1 else {}), **dbl}, span)
        for c in cls:
            put(cg[c], dd, j, {"s": subj, **({"t": ", ".join(codes)} if codes else {}), **dbl}, span)
            put(mg[c], dd, j, {"c": c, "s": subj, **({"t": ", ".join(codes)} if codes else {}), **dbl}, span)
        lesson_list.append({"d": dd, "p": j, "n": span, "c": cls, "s": subj, "t": codes, "r": []})
        placed += 1
    for g in cg.values():                                  # breaks are blocked for every class
        for row in g:
            for j, p in enumerate(periods):
                if p["brk"] and row[j] == "":
                    row[j] = "X"
    for g in list(tg.values()) + list(mg.values()):
        for row in g:
            for j, p in enumerate(periods):
                if p["brk"] and row[j] == "":
                    row[j] = "X"

    load = lambda g: sum(1 for row in g for c in row if isinstance(c, dict) or c == "^")
    title = (timetable or path.stem.replace("_", " ")).upper()
    il = [x for x in ((school or "").upper(), title) if x]
    data = {
        "format": 2,
        "periods": periods,
        "days": [{"label": DAY_LABELS[i], "wd": i + 1} for i in range(D)],
        "teachers": [{"id": f"T{i + 1}", "code": c, "name": tname[i], "grid": tg[c], "load": load(tg[c])}
                     for i, c in enumerate(tcode)],
        "classes": [{"id": f"C{i + 1}", "name": c, "grid": cg[c]} for i, c in enumerate(cname)],
        "master": [{"id": f"M{i + 1}", "name": c, "grid": mg[c]} for i, c in enumerate(cname)],
        "rooms": [],
        "institution": " ".join(il),
        "institution_lines": il,
        "institutions": {"classes": " ".join(il)},
        "colours": {},
        "fet": {"version": "", "when": ""},
        "source": "aSc Timetables (" + path.name + ")",
        "_lessons": lesson_list,
        "_unplaced": unplaced,                             # lessons aSc did not place (shown in the check report)
    }
    log(f"✔ aSc timetable: {len(tcode)} teachers · {len(cname)} classes · {len(subjects)} subjects · "
        f"{placed} lessons placed · {D} days · {sum(1 for p in periods if not p['brk'])} lessons a day")
    return data
