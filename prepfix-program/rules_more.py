"""
MORE RULES - subject distribution, morning / afternoon, teacher workload, single/double/triple lessons and
laboratories (Parts 10 - 14 of the PREPFIX rules). Every value is a setting of the rule, so a school changes it
in the Rules window or in the Word template.

Each rule type has an OFFENCES function:  offences(ctx, rule) -> [(message, [lesson index, ...], how far over)]
The checker (constraints.py) shows the messages; 🛠 Fix (autofix.py) uses the lessons and "how far over".

Words used:
  session  = one lesson block: a single (1 period), a double (2 in a row) or a triple (3 in a row)
  periods  = teaching periods occupied (a double = one session, two periods)
  lunch    = the break whose name contains the lunch word (default LUNCH); morning ends there, afternoon after it
  qualifying break = a break of at least the given minutes (a free period is NOT a qualifying break)
"""
from __future__ import annotations

import re
from collections import defaultdict


def _n(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def _int(v, d=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return d


def _pairs(text) -> dict:
    """'2:1, 3:2, 4:2' -> {2: 1, 3: 2, 4: 2}"""
    out = {}
    for a, b in re.findall(r"(\d+)\s*[:=→>-]+\s*(\d+)", str(text or "")):
        out[int(a)] = int(b)
    return out


def _subjects(text) -> list:
    return [_n(x) for x in re.split(r"[,;/]| AND ", str(text or "")) if x.strip()]


def _yes(v, default=True):
    v = _n(v)
    return default if not v else v in ("YES", "Y", "TRUE", "1")


# ------------------------------------------------------------------------------------------- the day
def teaching(ctx):
    return [j for j, p in enumerate(ctx.periods) if not p.get("brk")]


def lunch_index(ctx, r):
    word = _n(r.get("lunch") or "LUNCH")
    return next((j for j, p in enumerate(ctx.periods) if p.get("brk") and word in _n(p.get("label"))), None)


def _mins(p):
    if p.get("start") is not None and p.get("end") is not None:
        return p["start"], p["end"]
    m = re.findall(r"(\d{1,2})[:.](\d{2})", str(p.get("time", "")))
    if len(m) >= 2:
        a, b = [int(h) * 60 + int(mm) for h, mm in m[:2]]
        if b < a:
            b += 12 * 60
        return a, b
    return None, None


def _qualifying(ctx, j, minutes):
    """Is period j a break of at least `minutes`?"""
    p = ctx.periods[j]
    if not p.get("brk"):
        return False
    a, b = _mins(p)
    return a is None or (b - a) >= minutes


# ------------------------------------------------------------------------------------------- indexes
def class_subject(ctx):
    """(class, SUBJECT) -> [lesson index] ; weekly periods counted from the lessons."""
    by = defaultdict(list)
    for i, l in enumerate(ctx.lessons):
        if l["s"]:
            for c in l["c"]:
                by[(c, _n(l["s"]))].append(i)
    return by


def weekly(ctx, ids):
    return sum(ctx.lessons[i].get("n", 1) for i in ids)


def teacher_lessons(ctx):
    by = defaultdict(list)
    for i, l in enumerate(ctx.lessons):
        for t in l["t"]:
            by[_n(t)].append(i)
    return by


def _lab(ctx, l):
    return ctx.lab(l)


# ------------------------------------------------------------------------------------------- PART 10
def off_subject_sessions(ctx, r):
    """10.1 / 10.3: sessions of one subject for one class in a day."""
    lim = _int(r.get("weekly_limit"), 5)
    lo, hi = _int(r.get("max_low"), 1), _int(r.get("max_high"), 2)
    out = []
    for (c, s), ids in class_subject(ctx).items():
        wk = weekly(ctx, ids)
        mx = lo if wk <= lim else hi
        per = defaultdict(list)
        for i in ids:
            per[ctx.lessons[i]["d"]].append(i)
        for d, li in sorted(per.items()):
            if len(li) > mx:
                l0 = ctx.lessons[li[0]]
                out.append((f"{c} {l0['s']} has {len(li)} sessions on {ctx.days[d]} ({wk} a week: at most {mx} a day)",
                            li, len(li) - mx))
    return out


def off_mixed_blocks(ctx, r):
    """10.2 / 13: a single and a double (or double + triple, triple + single) of the same subject and class on
    the same day."""
    name = {1: "single", 2: "double", 3: "triple"}
    out = []
    for (c, s), ids in class_subject(ctx).items():
        per = defaultdict(list)
        for i in ids:
            per[ctx.lessons[i]["d"]].append(i)
        for d, li in sorted(per.items()):
            kinds = {min(ctx.lessons[i].get("n", 1), 3) for i in li}
            if len(kinds) > 1:
                l0 = ctx.lessons[li[0]]
                out.append((f"{c} {l0['s']} has a " + " and a ".join(name[k] for k in sorted(kinds)) +
                            f" on {ctx.days[d]}", li, len(kinds) - 1))
    return out


def off_subject_gap(ctx, r):
    """10.4: two sessions of the same subject for a class on one day need at least N teaching periods between."""
    gap = _int(r.get("min_gap"), 2)
    T = teaching(ctx)
    pos = {j: k for k, j in enumerate(T)}
    out = []
    for (c, s), ids in class_subject(ctx).items():
        per = defaultdict(list)
        for i in ids:
            per[ctx.lessons[i]["d"]].append(i)
        for d, li in per.items():
            li = sorted(li, key=lambda i: ctx.lessons[i]["p"])
            for a, b in zip(li, li[1:]):
                A, Bl = ctx.lessons[a], ctx.lessons[b]
                end = A["p"] + A.get("n", 1) - 1
                if end not in pos or Bl["p"] not in pos:
                    continue
                between = pos[Bl["p"]] - pos[end] - 1
                if between < gap:
                    out.append((f"{c} {A['s']} on {ctx.days[d]}: only {between} lesson(s) between "
                                f"{ctx.periods[A['p']]['label']} and {ctx.periods[Bl['p']]['label']} (aim {gap})",
                                [a, b], gap - between))
    return out


def off_subject_pair(ctx, r):
    """10.5: the two subjects of a pair are not one right after the other for the same class."""
    A, B = _n(r.get("subject")), _n(r.get("subject2"))
    T = teaching(ctx)
    nxt = {T[k]: T[k + 1] for k in range(len(T) - 1)}
    at = {}
    for i, l in enumerate(ctx.lessons):
        for c in l["c"]:
            for d, p in ctx.slots(l):
                at[(c, d, p)] = i
    out = []
    for i, l in enumerate(ctx.lessons):
        if _n(l["s"]) not in (A, B):
            continue
        last = l["p"] + l.get("n", 1) - 1
        if last not in nxt:
            continue
        for c in l["c"]:
            j = at.get((c, l["d"], nxt[last]))
            if j is not None and j != i and {_n(l["s"]), _n(ctx.lessons[j]["s"])} == {A, B}:
                out.append((f"{c}: {l['s']} is followed by {ctx.lessons[j]['s']} on {ctx.days[l['d']]} "
                            f"({ctx.periods[l['p']]['label']}–{ctx.periods[nxt[last]]['label']})", [i, j], 1))
    return out


# ------------------------------------------------------------------------------------------- PART 11
def off_morning_min(ctx, r):
    """11.1: at least the given number of a subject's weekly lessons in the morning (before lunch); not all of
    them in the last period before lunch."""
    L = lunch_index(ctx, r)
    if L is None:
        return [(f"No break called “{r.get('lunch') or 'LUNCH'}” in this timetable, so morning and afternoon cannot "
                 "be told apart. Type the lunch break's name in the rule.", [], 0)]
    table = _pairs(r.get("table") or "2:1, 3:2, 4:2, 5:3, 6:3, 7:4, 8:5")
    T = [j for j in teaching(ctx) if j < L]
    last_am = T[-1] if T else None
    out = []
    for (c, s), ids in class_subject(ctx).items():
        wk = weekly(ctx, ids)
        need = table.get(wk) if wk in table else (table[max(table)] if table and wk > max(table) else None)
        if not need:
            continue
        am = [(i, k) for i in ids for k in range(ctx.lessons[i].get("n", 1)) if ctx.lessons[i]["p"] + k < L]
        n_am = len(am)
        l0 = ctx.lessons[ids[0]]
        if n_am < need:
            out.append((f"{c} {l0['s']}: {n_am} of its {wk} weekly lessons are in the morning (needs at least {need})",
                        [i for i in ids if ctx.lessons[i]["p"] >= L], need - n_am))
        elif n_am > 1 and last_am is not None and all(ctx.lessons[i]["p"] + k == last_am for i, k in am):
            out.append((f"{c} {l0['s']}: every morning lesson is in the last period before lunch", [i for i, _ in am], 1))
    return out


# ------------------------------------------------------------------------------------------- PART 12
def _tmatch(ctx, r):
    return {_n(c) for c in ctx.teacher_match(r.get("teacher", "*"))}


def off_first_last(ctx, r):
    """12.1 / 12.2: first-period and last-period allocations per teacher in the week."""
    T = teaching(ctx)
    if not T:
        return []
    first, last = T[0], T[-1]
    mf, ml = _int(r.get("max_first"), 3), _int(r.get("max_last"), 3)
    who = _tmatch(ctx, r)
    out = []
    for t, ids in teacher_lessons(ctx).items():
        if t not in who:
            continue
        f = [i for i in ids if ctx.lessons[i]["p"] == first]
        la = [i for i in ids if ctx.lessons[i]["p"] + ctx.lessons[i].get("n", 1) - 1 == last]
        if len(f) > mf:
            out.append((f"{ctx.tdisp(t)} has the first period {len(f)} times a week (at most {mf})", f, len(f) - mf))
        if len(la) > ml:
            out.append((f"{ctx.tdisp(t)} has the last period {len(la)} times a week (at most {ml})", la, len(la) - ml))
    return out


def off_monfri_first(ctx, r):
    """12.3: first period on Monday and Friday together."""
    T = teaching(ctx)
    if not T:
        return []
    mx = _int(r.get("max"), 1)
    days = [d for d, lab in enumerate(ctx.days) if _n(lab)[:3] in ("MON", "FRI")]
    who = _tmatch(ctx, r)
    out = []
    for t, ids in teacher_lessons(ctx).items():
        if t not in who:
            continue
        f = [i for i in ids if ctx.lessons[i]["p"] == T[0] and ctx.lessons[i]["d"] in days]
        if len(f) > mx:
            out.append((f"{ctx.tdisp(t)} has the first period on Monday and Friday {len(f)} times (at most {mx})",
                        f, len(f) - mx))
    return out


def _teacher_day(ctx, ids, d):
    """[(period, lesson index)] a teacher teaches on day d, in order."""
    out = []
    for i in ids:
        l = ctx.lessons[i]
        if l["d"] == d:
            for k in range(l.get("n", 1)):
                out.append((l["p"] + k, i))
    return sorted(out)


def off_consec_break(ctx, r):
    """12.4: at most N ordinary periods in a row without a qualifying break (periods next to each other with no
    break between). Different classes count too - it is about continuous teaching."""
    mx, mins = _int(r.get("max"), 2), _int(r.get("break_minutes"), 10)
    who = _tmatch(ctx, r)
    out = []
    for t, ids in teacher_lessons(ctx).items():
        if t not in who:
            continue
        for d in range(len(ctx.days)):
            day = _teacher_day(ctx, ids, d)
            run = []
            for p, i in day:
                if run:
                    pp = run[-1][0]
                    between = range(pp + 1, p)
                    joined = all(ctx.periods[j].get("brk") and not _qualifying(ctx, j, mins) for j in between)
                    if not joined:
                        run = []
                run.append((p, i))
                if len(run) == mx + 1:
                    out.append((f"{ctx.tdisp(t)} teaches {mx + 1} periods in a row with no break on {ctx.days[d]} "
                                f"(from {ctx.periods[run[0][0]]['label']})", sorted({x for _, x in run}), 1))
    return out


def off_continuous(ctx, r):
    """12.5: at most N minutes of teaching without a qualifying break (a free period is NOT a break)."""
    mx, mins = _int(r.get("max_minutes"), 120), _int(r.get("break_minutes"), 10)
    who = _tmatch(ctx, r)
    out = []
    for t, ids in teacher_lessons(ctx).items():
        if t not in who:
            continue
        for d in range(len(ctx.days)):
            day = _teacher_day(ctx, ids, d)
            if not day:
                continue
            block = []
            blocks = []
            for p, i in day:
                if block and any(_qualifying(ctx, j, mins) for j in range(block[-1][0] + 1, p)):
                    blocks.append(block)
                    block = []
                block.append((p, i))
            blocks.append(block)
            for b in blocks:
                a, _ = _mins(ctx.periods[b[0][0]])
                _, e = _mins(ctx.periods[b[-1][0]])
                if a is None or e is None:
                    continue
                if e - a > mx:
                    out.append((f"{ctx.tdisp(t)} teaches {e - a} minutes without a qualifying break on {ctx.days[d]} "
                                f"({ctx.periods[b[0][0]]['label']}–{ctx.periods[b[-1][0]]['label']}; at most {mx})",
                                sorted({x for _, x in b}), max(1, (e - a - mx) // 30 + 1)))
    return out


def off_free_afternoon(ctx, r):
    """12.6: afternoons in the week with no teaching (from the end of lunch to the end of the day)."""
    L = lunch_index(ctx, r)
    if L is None:
        return [(f"No break called “{r.get('lunch') or 'LUNCH'}” in this timetable, so afternoons cannot be found. "
                 "Type the lunch break's name in the rule.", [], 0)]
    need = _int(r.get("min"), 1)
    who = _tmatch(ctx, r)
    out = []
    for t, ids in teacher_lessons(ctx).items():
        if t not in who:
            continue
        busy = defaultdict(list)
        for i in ids:
            l = ctx.lessons[i]
            if l["p"] + l.get("n", 1) - 1 > L:
                busy[l["d"]].append(i)
        free = len(ctx.days) - len(busy)
        if free < need:
            pm = sorted(busy.items(), key=lambda kv: len(kv[1]))
            out.append((f"{ctx.tdisp(t)} has {free} free afternoon(s) a week (needs {need})",
                        pm[0][1] if pm else [], need - free))
    return out


def off_daily_by_length(ctx, r):
    """12.9: most occupied periods a day for a teacher, by the length of the day; review list for big loads."""
    lim, rev = _pairs(r.get("limits") or "10:7, 9:6"), _pairs(r.get("review") or "10:35, 9:30")
    T = teaching(ctx)
    mx = lim.get(len(T))
    if mx is None:
        return []
    out = []
    for t, ids in teacher_lessons(ctx).items():
        wk = weekly(ctx, ids)
        if rev.get(len(T)) and wk > rev[len(T)]:
            out.append((f"{ctx.tdisp(t)} has {wk} lessons a week (more than {rev[len(T)]}) — exception review", [], 0))
        per = defaultdict(list)
        for i in ids:
            per[ctx.lessons[i]["d"]].append(i)
        for d, li in sorted(per.items()):
            n = sum(ctx.lessons[i].get("n", 1) for i in li)
            if n > mx:
                out.append((f"{ctx.tdisp(t)} has {n} periods on {ctx.days[d]} ({len(T)}-period day: at most {mx})",
                            li, n - mx))
    return out


def off_afternoon_doubles(ctx, r):
    """12.11: double lessons in one afternoon for a teacher."""
    L = lunch_index(ctx, r)
    if L is None:
        return []
    mx = _int(r.get("max"), 2)
    out = []
    for t, ids in teacher_lessons(ctx).items():
        per = defaultdict(list)
        for i in ids:
            l = ctx.lessons[i]
            if l.get("n", 1) >= 2 and l["p"] > L:
                per[l["d"]].append(i)
        for d, li in sorted(per.items()):
            if len(li) > mx:
                out.append((f"{ctx.tdisp(t)} has {len(li)} double lessons on {ctx.days[d]} afternoon (at most {mx})",
                            li, len(li) - mx))
    return out


def off_same_teacher_class(ctx, r):
    """12.12: the same teacher with the same class in two separate lessons one right after the other."""
    T = teaching(ctx)
    nxt = {T[k]: T[k + 1] for k in range(len(T) - 1)}
    start = {}
    for i, l in enumerate(ctx.lessons):
        for t in l["t"]:
            for c in l["c"]:
                start[(_n(t), c, l["d"], l["p"])] = i
    out = []
    for i, l in enumerate(ctx.lessons):
        last = l["p"] + l.get("n", 1) - 1
        if last not in nxt:
            continue
        for t in l["t"]:
            for c in l["c"]:
                j = start.get((_n(t), c, l["d"], nxt[last]))
                if j is not None and j != i:
                    out.append((f"{ctx.tdisp(t)} teaches {c} twice in a row on {ctx.days[l['d']]} "
                                f"({ctx.periods[l['p']]['label']} and {ctx.periods[nxt[last]]['label']})", [i, j], 1))
    return out


# ------------------------------------------------------------------------------------------- PART 14
def off_lab(ctx, r):
    """14: lessons that need a laboratory (its subjects; doubles only if set) at the same time - no more than the
    lab can hold."""
    subs = set(_subjects(r.get("subjects")))
    cap = _int(r.get("capacity"), 1)
    doubles = _yes(r.get("doubles_only"), True)
    if not subs:
        return [(f"Laboratory “{r.get('lab') or '?'}”: no subjects given, so it cannot be checked.", [], 0)]
    at = defaultdict(list)
    for i, l in enumerate(ctx.lessons):
        if _n(l["s"]) in subs and (not doubles or l.get("n", 1) >= 2):
            for d, p in ctx.slots(l):
                at[(d, p)].append(i)
    out, seen = [], set()
    for (d, p), ids in sorted(at.items()):
        if len(ids) > cap and tuple(ids) not in seen:
            seen.add(tuple(ids))
            out.append((f"{r.get('lab') or 'Laboratory'}: {len(ids)} practical lessons at {ctx.when(d, p)} "
                        f"({', '.join(ctx.lab(ctx.lessons[i]) for i in ids)}) — it holds {cap}", ids, len(ids) - cap))
    return out


OFFENCES = {
    "subject_sessions": off_subject_sessions, "mixed_blocks": off_mixed_blocks, "subject_gap": off_subject_gap,
    "subject_pair": off_subject_pair, "morning_min": off_morning_min, "first_last": off_first_last,
    "monfri_first": off_monfri_first, "consec_break": off_consec_break, "continuous": off_continuous,
    "free_afternoon": off_free_afternoon, "daily_by_length": off_daily_by_length,
    "afternoon_doubles": off_afternoon_doubles, "same_teacher_class": off_same_teacher_class, "lab": off_lab,
}


def check(typ):
    return lambda ctx, r: [m for m, _, _ in OFFENCES[typ](ctx, r)]


def _w(r):
    t = r.get("teacher") or "*"
    return "Every teacher" if t.strip() in ("*", "") else t


# label, fields (key, label, kind), text
TYPES = {
    "subject_sessions": ("Subject: sessions a day (by weekly lessons)", [
        ("weekly_limit", "Weekly lessons up to (low)", "int"), ("max_low", "Sessions a day if low", "int"),
        ("max_high", "Sessions a day if more", "int")],
        lambda r: f"Subject spread: up to {r.get('weekly_limit', 5)} a week → at most {r.get('max_low', 1)} session a day; "
                  f"more → at most {r.get('max_high', 2)} a day"),
    "mixed_blocks": ("Subject: no single + double (or double + triple…) on one day", [],
                     lambda r: "No single and double (or double and triple, triple and single) of a subject on the same day"),
    "subject_gap": ("Subject: periods between two sessions on one day", [("min_gap", "At least this many periods between", "int")],
                    lambda r: f"Same subject twice in a day: at least {r.get('min_gap', 2)} periods between"),
    "subject_pair": ("Subject pair: not one right after the other", [("subject", "Subject", "subject"),
                                                                     ("subject2", "And subject", "subject")],
                     lambda r: f"{r.get('subject')} and {r.get('subject2')}: not one right after the other"),
    "morning_min": ("Subject: lessons in the morning (before lunch)", [
        ("lunch", "Lunch break name contains", "text"), ("table", "Weekly → at least in the morning", "text")],
        lambda r: f"Morning lessons ({r.get('table') or '2:1, 3:2, 4:2, 5:3, 6:3, 7:4, 8:5'}); lunch = “{r.get('lunch') or 'LUNCH'}”"),
    "first_last": ("Teacher: first and last periods in a week", [("teacher", "Teacher (* = everyone)", "teacher"),
                   ("max_first", "Most first periods", "int"), ("max_last", "Most last periods", "int")],
                   lambda r: f"{_w(r)}: first period at most {r.get('max_first', 3)}, last period at most {r.get('max_last', 3)} times a week"),
    "monfri_first": ("Teacher: first period on Monday + Friday", [("teacher", "Teacher (* = everyone)", "teacher"),
                     ("max", "Most (both days together)", "int")],
                     lambda r: f"{_w(r)}: first period on Monday and Friday together at most {r.get('max', 1)}"),
    "consec_break": ("Teacher: periods in a row before a break", [("teacher", "Teacher (* = everyone)", "teacher"),
                     ("max", "Most periods in a row", "int"), ("break_minutes", "A break counts if at least (minutes)", "int")],
                     lambda r: f"{_w(r)}: at most {r.get('max', 2)} periods in a row, then a break of {r.get('break_minutes', 10)}+ minutes"),
    "continuous": ("Teacher: minutes of teaching without a break", [("teacher", "Teacher (* = everyone)", "teacher"),
                   ("max_minutes", "Most minutes", "int"), ("break_minutes", "A break counts if at least (minutes)", "int")],
                   lambda r: f"{_w(r)}: at most {r.get('max_minutes', 120)} minutes without a {r.get('break_minutes', 10)}+ minute break"),
    "free_afternoon": ("Teacher: free afternoons a week", [("teacher", "Teacher (* = everyone)", "teacher"),
                       ("min", "At least", "int"), ("lunch", "Lunch break name contains", "text")],
                       lambda r: f"{_w(r)}: at least {r.get('min', 1)} free afternoon a week"),
    "daily_by_length": ("Teacher: periods a day by length of day", [("limits", "Day length → most periods", "text"),
                        ("review", "Day length → weekly load for review", "text")],
                        lambda r: f"Teacher periods a day ({r.get('limits') or '10:7, 9:6'}); review loads over ({r.get('review') or '10:35, 9:30'})"),
    "afternoon_doubles": ("Teacher: double lessons in one afternoon", [("max", "Most doubles in one afternoon", "int"),
                          ("lunch", "Lunch break name contains", "text")],
                          lambda r: f"At most {r.get('max', 2)} double lessons in one afternoon for a teacher"),
    "same_teacher_class": ("Teacher + class: not twice in a row", [],
                           lambda r: "The same teacher and class not in two separate lessons one right after the other"),
    "lab": ("Laboratory: practical lessons at the same time", [("lab", "Laboratory", "text"), ("subjects", "Subjects", "text"),
            ("capacity", "Lessons at once", "int"), ("doubles_only", "Doubles only (Yes / No)", "text")],
            lambda r: f"{r.get('lab') or 'Laboratory'}: at most {r.get('capacity', 1)} of {r.get('subjects')} at once"
                      + (" (doubles)" if _yes(r.get('doubles_only'), True) else "")),
}


# the values a new rule starts with (Parts 10 - 14 of the PREPFIX rules) - all can be changed
DEFAULTS = {
    "subject_sessions": {"weekly_limit": 5, "max_low": 1, "max_high": 2},
    "subject_gap": {"min_gap": 2},
    "morning_min": {"lunch": "LUNCH", "table": "2:1, 3:2, 4:2, 5:3, 6:3, 7:4, 8:5"},
    "first_last": {"teacher": "*", "max_first": 3, "max_last": 3},
    "monfri_first": {"teacher": "*", "max": 1},
    "consec_break": {"teacher": "*", "max": 2, "break_minutes": 10},
    "continuous": {"teacher": "*", "max_minutes": 120, "break_minutes": 10},
    "free_afternoon": {"teacher": "*", "min": 1, "lunch": "LUNCH"},
    "daily_by_length": {"limits": "10:7, 9:6", "review": "10:35, 9:30"},
    "afternoon_doubles": {"max": 2, "lunch": "LUNCH"},
    "lab": {"capacity": 1, "doubles_only": "Yes"},
}


# =========================================================================================================
# RULES IN OPERATION read from FET (fet_rules.py). Lessons carry "fa" (FET activity id) and "tg" (tags, "a|b").
# =========================================================================================================
def _slotset(ctx, text):
    """'MON L8, TUE L9' -> {(0, 9), (1, 10)}"""
    days = [_n(d) for d in ctx.days]
    labs = [_n(p["label"]) for p in ctx.periods]
    out = set()
    for part in str(text or "").split(","):
        part = _n(part)
        if not part:
            continue
        for di, dn in enumerate(days):
            if part.startswith(dn + " "):
                rest = part[len(dn) + 1:]
                if rest in labs:
                    out.add((di, labs.index(rest)))
                break
    return out


def _tags(l):
    return {_n(x) for x in str(l.get("tg") or "").split("|") if x.strip()}


def off_not_available(ctx, r):
    who, name, sl = r.get("who", "teacher"), r.get("name", ""), _slotset(ctx, r.get("slots"))
    out = []
    for i, l in enumerate(ctx.lessons):
        mine = (who == "teacher" and any(_n(t) == _n(name) for t in l["t"])) or \
               (who == "class" and any(_n(c) == _n(name) for c in l["c"])) or \
               (who == "room" and any(_n(x) == _n(name) for x in l["r"]))
        if mine:
            for d, p in ctx.slots(l):
                if (d, p) in sl:
                    shown = ctx.tdisp(name) if who == "teacher" else name
                    out.append((f"{shown} is not available at {ctx.when(d, p)} but has {ctx.lab(l)}", [i], 1))
                    break
    return out


def off_teacher_min_days(ctx, r):
    mn, out = _int(r.get("min"), 1), []
    for t, ids in teacher_lessons(ctx).items():
        if t not in _tmatch(ctx, r):
            continue
        days = {ctx.lessons[i]["d"] for i in ids}
        if len(days) < mn:
            out.append((f"{ctx.tdisp(t)} teaches on {len(days)} day(s) (at least {mn})", ids, mn - len(days)))
    return out


def off_interval_max_days(ctx, r):
    labs = [_n(p["label"]) for p in ctx.periods]
    a = labs.index(_n(r.get("start"))) if _n(r.get("start")) in labs else 0
    b = labs.index(_n(r.get("end"))) if _n(r.get("end")) in labs else len(labs)
    mx, out = _int(r.get("max"), 5), []
    for t, ids in teacher_lessons(ctx).items():
        if t not in _tmatch(ctx, r):
            continue
        per = defaultdict(list)
        for i in ids:
            l = ctx.lessons[i]
            if any(a <= p < b for _, p in ctx.slots(l)):
                per[l["d"]].append(i)
        if len(per) > mx:
            out.append((f"{ctx.tdisp(t)} teaches between {r.get('start') or 'the start'} and {r.get('end') or 'the end of the day'} "
                        f"on {len(per)} days (at most {mx})", [i for v in per.values() for i in v], len(per) - mx))
    return out


def off_max_gaps_day(ctx, r):
    mx, T, out = _int(r.get("max"), 5), teaching(ctx), []
    for t, ids in teacher_lessons(ctx).items():
        if t not in _tmatch(ctx, r):
            continue
        for d in range(len(ctx.days)):
            busy = sorted({p for i in ids if ctx.lessons[i]["d"] == d for _, p in ctx.slots(ctx.lessons[i])})
            if not busy:
                continue
            gaps = [j for j in T if busy[0] < j < busy[-1] and j not in busy]
            if len(gaps) > mx:
                out.append((f"{ctx.tdisp(t)} has {len(gaps)} gaps on {ctx.days[d]} (at most {mx})",
                            [i for i in ids if ctx.lessons[i]["d"] == d], len(gaps) - mx))
    return out


def off_tag_max_daily(ctx, r):
    tag, mx, out = _n(r.get("tag")), _int(r.get("max"), 1), []
    per = defaultdict(list)
    for i, l in enumerate(ctx.lessons):
        if tag in _tags(l):
            for c in l["c"]:
                per[(c, l["d"])].append(i)
    for (c, d), ids in sorted(per.items()):
        n = sum(ctx.lessons[i].get("n", 1) for i in ids)
        if n > mx:
            out.append((f"{c} has {n} “{r.get('tag')}” period(s) on {ctx.days[d]} (at most {mx})", ids, n - mx))
    return out


def off_tag_min_gaps(ctx, r):
    t1, t2, mn = _n(r.get("tag")), _n(r.get("tag2")), _int(r.get("min"), 1)
    T = teaching(ctx)
    pos = {j: k for k, j in enumerate(T)}
    by = defaultdict(lambda: ([], []))
    for i, l in enumerate(ctx.lessons):
        tg = _tags(l)
        for c in l["c"]:
            if t1 in tg:
                by[(c, l["d"])][0].append(i)
            if t2 in tg:
                by[(c, l["d"])][1].append(i)
    out = []
    for (c, d), (A, B) in by.items():
        for a in A:
            for b in B:
                la, lb = ctx.lessons[a], ctx.lessons[b]
                end_a = la["p"] + la.get("n", 1) - 1
                if lb["p"] > end_a:                       # ordered: first, then second
                    gap = lb["p"] - end_a - 1                 # FET counts the hours between, breaks included
                    if gap < mn:
                        out.append((f"{c} on {ctx.days[d]}: “{r.get('tag2')}” must come at least {mn} lesson(s) after "
                                    f"“{r.get('tag')}”", [a, b], mn - gap if gap >= 0 else mn + 1))
    return out


def off_tags_not_overlap(ctx, r):
    tags = {_n(x) for x in str(r.get("tags") or "").split("|") if x.strip()}
    at = defaultdict(list)
    for i, l in enumerate(ctx.lessons):
        if _tags(l) & tags:
            for s in ctx.slots(l):
                at[s].append(i)
    out = []
    for (d, p), ids in sorted(at.items()):
        kinds = {t for i in ids for t in (_tags(ctx.lessons[i]) & tags)}
        if len(kinds) > 1:
            out.append((f"{' and '.join(sorted(kinds))} lessons overlap at {ctx.when(d, p)}", ids, 1))
    return out


def off_min_days_between(ctx, r):
    ids_ = {x.strip() for x in str(r.get("ids") or "").split(",") if x.strip()}
    mn = _int(r.get("min"), 1)
    les = [i for i, l in enumerate(ctx.lessons) if str(l.get("fa") or "") in ids_]
    out = []
    for k, a in enumerate(les):
        for b in les[k + 1:]:
            da, db = ctx.lessons[a]["d"], ctx.lessons[b]["d"]
            if abs(da - db) < mn:
                l = ctx.lessons[a]
                out.append((f"{ctx.lab(l)}: two of its lessons on {ctx.days[da]}" + ("" if da == db else f" and {ctx.days[db]}")
                            + f" (at least {mn} day(s) apart)", [a, b], 1))
    return out


def off_allowed_slots(ctx, r):
    sl = _slotset(ctx, r.get("slots"))
    out = []
    for i, l in enumerate(ctx.lessons):
        if r.get("subject") and _n(l["s"]) != _n(r["subject"]):
            continue
        if r.get("teacher") and not any(_n(t) == _n(r["teacher"]) for t in l["t"]):
            continue
        if r.get("students") and not any(_n(c) == _n(r["students"]) or _n(c).startswith(_n(r["students"]) + " ") for c in l["c"]):
            continue
        if r.get("tag") and _n(r["tag"]) not in _tags(l):
            continue
        if (l["d"], l["p"]) not in sl:
            out.append((f"{ctx.lab(l)} must be at {r.get('slots')} (it is at {ctx.when(l['d'], l['p'])})", [i], 1))
    return out


def off_occupy_slots(ctx, r):
    ids_ = {x.strip() for x in str(r.get("ids") or "").split(",") if x.strip()}
    sl = _slotset(ctx, r.get("slots"))
    les = [i for i, l in enumerate(ctx.lessons) if str(l.get("fa") or "") in ids_]
    used = {s for i in les for s in ctx.slots(ctx.lessons[i]) if s in sl}
    n, want = len(used), _int(r.get("count"), 0)
    if r.get("mode") == "max" and n > want:
        return [(f"these lessons use {n} of the chosen times (at most {want})", les, n - want)]
    if r.get("mode") == "min" and n < want:
        return [(f"these lessons use {n} of the chosen times (at least {want})", les, want - n)]
    return []


OFFENCES.update({
    "not_available": off_not_available, "teacher_min_days": off_teacher_min_days,
    "interval_max_days": off_interval_max_days, "max_gaps_day": off_max_gaps_day, "tag_max_daily": off_tag_max_daily,
    "tag_min_gaps": off_tag_min_gaps, "tags_not_overlap": off_tags_not_overlap,
    "min_days_between": off_min_days_between, "allowed_slots": off_allowed_slots, "occupy_slots": off_occupy_slots,
})
TYPES.update({
    "not_available": ("FET: not available at", [("who", "Who (teacher / class / room)", "text"), ("name", "Name", "text"),
                      ("slots", "Times", "text")],
                      lambda r: f"{r.get('who', '').title()} {r.get('name')}: not available at {r.get('slots')}"),
    "teacher_min_days": ("FET: teacher's days a week", [("teacher", "Teacher", "teacher"), ("min", "At least", "int")],
                         lambda r: f"{_w(r)}: teaches on at least {r.get('min')} days"),
    "interval_max_days": ("FET: days with lessons in a part of the day", [("teacher", "Teacher", "teacher"),
                          ("start", "From", "text"), ("end", "To", "text"), ("max", "At most days", "int")],
                          lambda r: f"{_w(r)}: lessons from {r.get('start') or 'start'} to {r.get('end') or 'end of day'} on at most {r.get('max')} days"),
    "max_gaps_day": ("FET: teacher's gaps a day", [("teacher", "Teacher", "teacher"), ("max", "At most", "int")],
                     lambda r: f"{_w(r)}: at most {r.get('max')} gaps a day"),
    "tag_max_daily": ("FET: class's periods of a kind a day", [("tag", "Activity tag", "text"), ("max", "At most", "int")],
                      lambda r: f"Classes: at most {r.get('max')} “{r.get('tag')}” period(s) a day"),
    "tag_min_gaps": ("FET: lessons between two kinds", [("tag", "First", "text"), ("tag2", "Second", "text"), ("min", "At least", "int")],
                     lambda r: f"“{r.get('tag2')}” at least {r.get('min')} lesson(s) after “{r.get('tag')}” on the same day"),
    "tags_not_overlap": ("FET: kinds of lessons not at the same time", [("tags", "Activity tags (a|b)", "text")],
                         lambda r: f"{' / '.join(str(r.get('tags')).split('|'))}: never at the same time"),
    "min_days_between": ("FET: days between lessons of a subject", [("ids", "FET activities", "text"), ("min", "At least days", "int")],
                         lambda r: f"Lessons of one activity group at least {r.get('min')} day(s) apart"),
    "allowed_slots": ("FET: lessons only at certain times", [("subject", "Subject", "text"), ("slots", "Times", "text")],
                      lambda r: f"{r.get('subject') or r.get('tag') or r.get('teacher') or 'Lessons'}: only at {r.get('slots')}"),
    "occupy_slots": ("FET: chosen times used by a group of lessons", [("ids", "FET activities", "text"), ("slots", "Times", "text"),
                     ("mode", "max / min", "text"), ("count", "Number", "int")],
                     lambda r: f"A group of lessons uses {'at most' if r.get('mode') == 'max' else 'at least'} {r.get('count')} of {len(str(r.get('slots')).split(','))} chosen times"),
})
