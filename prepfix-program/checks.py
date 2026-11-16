"""
CHECK REPORT - problems found in the imported timetable data itself (both paths).

    report(data) -> {"items": [...], "counts": {kind: n}, "problems": n, "line": "one line", ...}

Each item names who / what / when:
    {"kind", "teacher", "cls", "subject", "room", "day", "period", "msg"}

Kinds (in the order they are shown):
    teacher_clash   a teacher in two places at once
    class_clash     a class double-booked
    room_clash      a lab / field / room double-booked
    on_break        a lesson placed in a break
    gaps            a teacher with many free lessons between lessons in one day
    too_many        a teacher with too many lessons in one day
    odd_double      unusual double lessons (3 or more in a row, or the same subject doubled twice in a day)

The checker only READS the timetable. It never blocks previewing or printing; publishing with problems is
allowed only after the person has seen a clear warning (see prepfix_timetable.py).
"""
from __future__ import annotations

from collections import defaultdict

import constraints as K

GAPS_A_DAY = 4          # a teacher-day with this many gaps (or more) is listed
MAX_A_DAY = 7           # more lessons than this in one day is listed

KINDS = [
    ("teacher_clash", "Teacher in two places at once"),
    ("class_clash", "Class double-booked"),
    ("room_clash", "Lab / room double-booked"),
    ("on_break", "Lesson placed in a break"),
    ("gaps", f"Teacher with many gaps ({GAPS_A_DAY}+ free lessons between lessons in a day)"),
    ("too_many", f"Too many lessons in a day (more than {MAX_A_DAY})"),
    ("odd_double", "Unusual double lessons"),
    ("unplaced", "Lesson NOT placed on the timetable (missing in the source file, e.g. aSc)"),
]
LABEL = dict(KINDS)


def _item(kind, msg, teacher="", cls="", subject="", room="", day="", period=""):
    return {"kind": kind, "msg": msg, "teacher": teacher, "cls": cls, "subject": subject, "room": room,
            "day": day, "period": period}


def report(data: dict) -> dict:
    ctx = K.Ctx(data)
    P, D = ctx.periods, ctx.days
    items = []

    # ---- double-booking: a teacher / class / room in two different lessons in the same period
    for kind, who_of, show in (("teacher_clash", lambda l: l["t"], ctx.tdisp),
                               ("class_clash", lambda l: l["c"], lambda w: w),
                               ("room_clash", lambda l: l["r"], lambda w: w)):
        by = defaultdict(list)
        for i, l in enumerate(ctx.lessons):
            for d, p in ctx.slots(l):
                if not P[p].get("brk"):
                    for w in who_of(l):
                        by[(K._n(w), d, p)].append((w, i))
        for (_, d, p), lst in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
            ids = sorted({i for _, i in lst})
            if len(ids) < 2:
                continue
            w = lst[0][0]
            les = [ctx.lessons[i] for i in ids]
            what = " AND ".join(f"{ctx.lab(l)}" + (f" ({', '.join(ctx.tdisp(t) for t in l['t'])})" if l["t"] and kind != "teacher_clash" else "")
                                for l in les)
            items.append(_item(kind, f"{show(w)} has {len(ids)} lessons at {ctx.when(d, p)}: {what}.",
                               teacher=show(w) if kind == "teacher_clash" else ", ".join(sorted({ctx.tdisp(t) for l in les for t in l["t"]})),
                               cls=w if kind == "class_clash" else ", ".join(sorted({c for l in les for c in l["c"]})),
                               subject=", ".join(sorted({l["s"] for l in les if l["s"]})),
                               room=w if kind == "room_clash" else "", day=D[d], period=P[p]["label"]))

    # ---- a teacher in two places: also read the teacher codes written in the CLASS timetables (a teacher's own
    #      grid can hold only one lesson per period, so a clash only shows up when the class timetables are compared)
    seen = {(K._n(it["teacher"]), it["day"], it["period"]) for it in items if it["kind"] == "teacher_clash"}
    by = defaultdict(dict)
    # aSc (.roz / PDF) gives the real lessons, so the loop above already saw every clash; reading class grids would
    # count one lesson taught to several classes together (e.g. an option block) as a clash
    for cl in ([] if data.get("_lessons") is not None else data.get("classes", [])):
        for d, row in enumerate(cl.get("grid", [])):
            for p, c in enumerate(row):
                if not isinstance(c, dict) or P[p].get("brk"):
                    continue
                n = 1
                while p + n < len(row) and row[p + n] == "^":
                    n += 1
                grp = tuple(sorted(K._toks(c.get("c") or cl["name"])))
                for t in K._toks(c.get("t", "")):
                    for k in range(n):
                        by[(K._n(t), t, d, p + k)].setdefault((K._n(c.get("s", "")), grp), (c.get("s", ""), grp))
    for (_, t, d, p), les in sorted(by.items(), key=lambda kv: (kv[0][2], kv[0][3], kv[0][0])):
        if len(les) < 2 or (K._n(ctx.tdisp(t)), D[d], P[p]["label"]) in seen:
            continue
        what = " AND ".join(f"{', '.join(g)} {s}" for s, g in les.values())
        items.append(_item("teacher_clash", f"{ctx.tdisp(t)} has {len(les)} lessons at {ctx.when(d, p)}: {what}.",
                           teacher=ctx.tdisp(t), cls=", ".join(sorted({c for _, g in les.values() for c in g})),
                           subject=", ".join(sorted({s for s, _ in les.values() if s})), day=D[d], period=P[p]["label"]))

    # ---- lessons in a break
    for l in ctx.lessons:
        for d, p in ctx.slots(l):
            if P[p].get("brk"):
                items.append(_item("on_break", f"{ctx.lab(l)} is placed in {P[p]['label']} ({ctx.when(d, p)}).",
                                   teacher=", ".join(ctx.tdisp(t) for t in l["t"]), cls=", ".join(l["c"]),
                                   subject=l["s"], day=D[d], period=P[p]["label"]))

    # ---- per teacher, per day: gaps and lessons a day
    lessons_idx = [j for j, p in enumerate(P) if not p.get("brk")]
    busy = defaultdict(set)                                      # (teacher code, day) -> lesson periods taught
    for l in ctx.lessons:
        for t in l["t"]:
            for d, p in ctx.slots(l):
                if not P[p].get("brk"):
                    busy[(t, d)].add(p)
    for (t, d), ps in sorted(busy.items(), key=lambda kv: (ctx.tdisp(kv[0][0]), kv[0][1])):
        first, last = min(ps), max(ps)
        free = [j for j in lessons_idx if first < j < last and j not in ps]
        if len(free) >= GAPS_A_DAY:
            items.append(_item("gaps", f"{ctx.tdisp(t)} has {len(free)} gaps on {D[d]} "
                                       f"(free at {', '.join(P[j]['label'] for j in free)}; first lesson {P[first]['label']}, "
                                       f"last {P[last]['label']}).",
                               teacher=ctx.tdisp(t), day=D[d], period=", ".join(P[j]["label"] for j in free)))
        if len(ps) > MAX_A_DAY:
            items.append(_item("too_many", f"{ctx.tdisp(t)} has {len(ps)} lessons on {D[d]} (more than {MAX_A_DAY}).",
                               teacher=ctx.tdisp(t), day=D[d]))

    # ---- unusual double lessons
    doubles = defaultdict(list)                                  # (class, subject, day) -> double lessons
    for l in ctx.lessons:
        n = l.get("n", 1)
        if n >= 3:
            items.append(_item("odd_double", f"{ctx.lab(l)} runs {n} lessons in a row on {D[l['d']]} "
                                             f"({P[l['p']]['label']}–{P[l['p'] + n - 1]['label']}).",
                               teacher=", ".join(ctx.tdisp(t) for t in l["t"]), cls=", ".join(l["c"]), subject=l["s"],
                               day=D[l["d"]], period=P[l["p"]]["label"]))
        if n >= 2:
            for c in l["c"]:
                doubles[(c, K._n(l["s"]), l["d"])].append(l)
    for (c, _, d), ls in sorted(doubles.items()):
        if len(ls) > 1:
            l = ls[0]
            items.append(_item("odd_double", f"{c} has {len(ls)} double lessons of {l['s']} on {D[d]} "
                                             f"(at {', '.join(P[x['p']]['label'] for x in ls)}).",
                               teacher=", ".join(sorted({ctx.tdisp(t) for x in ls for t in x["t"]})), cls=c,
                               subject=l["s"], day=D[d], period=", ".join(P[x["p"]]["label"] for x in ls)))

    # ---- lessons the timetable program was asked for but did not place (aSc keeps a count per lesson)
    for u in data.get("_unplaced") or []:
        miss = max(0, u.get("want", 0) - u.get("placed", 0))
        items.append(_item("unplaced", f"{u['c']} {u['s']} ({u['t']}): needs {u['want']} a week, only {u['placed']} placed"
                                       + (f" — {miss} missing" if miss else "")
                                       + (f"; {u['dropped']} card(s) with no valid day / lesson" if u.get("dropped") else "")
                                       + ".", teacher=u["t"], cls=u["c"], subject=u["s"]))

    order = {k: i for i, (k, _) in enumerate(KINDS)}
    items.sort(key=lambda it: order[it["kind"]])
    counts = {k: sum(1 for it in items if it["kind"] == k) for k, _ in KINDS}
    teachers = defaultdict(set)
    for it in items:
        teachers[it["kind"]].add(it["teacher"])
    rep = {"items": items, "counts": counts, "problems": len(items), "lessons": len(ctx.lessons),
           "teachers_by_kind": {k: sorted(x for x in v if x) for k, v in teachers.items()}}
    rep["line"] = summary_line(rep)
    return rep


def summary_line(rep: dict) -> str:
    if not rep["problems"]:
        return f"Check: ✔ no problems found in the imported timetable ({rep['lessons']} lessons)."
    parts = []
    words = {"teacher_clash": ("teacher clash", "teacher clashes"), "class_clash": ("class double-booking", "class double-bookings"),
             "room_clash": ("room double-booking", "room double-bookings"), "on_break": ("lesson on a break", "lessons on a break"),
             "gaps": ("teacher-day with many gaps", "teacher-days with many gaps"),
             "too_many": ("day with too many lessons", "days with too many lessons"),
             "odd_double": ("unusual double lesson", "unusual double lessons"),
             "unplaced": ("lesson not placed", "lessons not placed")}
    for k, _ in KINDS:
        n = rep["counts"].get(k, 0)
        if n:
            parts.append(f"{n} {words[k][0] if n == 1 else words[k][1]}")
    return "Check: ⚠ " + " · ".join(parts) + "."


def report_text(rep: dict, school: str = "") -> str:
    lines = [f"CHECK REPORT{(' — ' + school) if school else ''}", rep["line"], ""]
    if not rep["problems"]:
        return "\n".join(lines)
    lines.append("Counts:")
    for k, label in KINDS:
        n = rep["counts"].get(k, 0)
        lines.append(f"  {n:>4}  {label}")
    for k, label in KINDS:
        its = [it for it in rep["items"] if it["kind"] == k]
        if not its:
            continue
        lines += ["", f"{label.upper()}  ({len(its)})", "-" * min(70, len(label) + 8)]
        ppl = rep["teachers_by_kind"].get(k, [])
        if ppl and k in ("gaps", "too_many"):
            lines.append(f"  Teachers: {', '.join(ppl)}")
        for it in its:
            lines.append(f"  - {it['msg']}")
    lines += ["", "This report only reads the timetable. Previewing and printing are never blocked; publishing with "
                  "problems asks you to confirm first."]
    return "\n".join(lines)
