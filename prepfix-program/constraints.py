"""
Constraints: rules a timetable must pass BEFORE it is published.

A rule is a small dict, stored as JSON per school:
    {"id": "ab12", "type": "teacher_max_day", "enabled": true, "severity": "error", "teacher": "*", "max": 6}
severity "error"  = must pass (publishing is blocked until it is fixed or the rule is changed)
severity "warn"   = shown in the report, publishing still allowed.

run(data, rules) works on the dict that fet_reader / sheet_reader produce. If data has "_lessons" (the raw
lesson list from an Excel/PDF import) that is used - so clashes the finished grids could not show are still
caught. Otherwise the lessons are rebuilt from the teacher and class grids (FET).
"""
from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict

ERR, WARN = "error", "warn"
SEVERITIES = {ERR: "Must pass (blocks publishing)", WARN: "Warning only"}
MAX_PER_RULE = 40


def _n(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def _toks(s) -> list:
    return [t.strip() for t in re.split(r"[,;]", str(s or "")) if t.strip()]


def _csv(v) -> list:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return _toks(v)


# ---------------------------------------------------------------------------------------- lessons
def lessons_of(data: dict) -> list:
    """[{d, p, n, c:[classes], s, t:[teacher codes], r:[rooms]}]  (n = how many periods in a row)."""
    if data.get("_lessons") is not None:
        return [dict(l, n=l.get("n", 1)) for l in data["_lessons"]]
    out, seen, covered = {}, set(), set()

    def span(row, j):
        n = 1
        while j + n < len(row) and row[j + n] == "^":
            n += 1
        return n

    for t in data.get("teachers", []):
        for d, row in enumerate(t["grid"]):
            for p, c in enumerate(row):
                if not isinstance(c, dict):
                    continue
                classes = tuple(_toks(c.get("c", "")))
                key = (d, p, c.get("s", ""), classes)
                les = out.setdefault(key, {"d": d, "p": p, "n": span(row, p), "c": list(classes),
                                           "s": c.get("s", ""), "t": [], "r": _toks(c.get("r", ""))})
                for k_ in ("fa", "tg"):                  # FET activity id / tags (when the .fet file was read)
                    if c.get(k_) and not les.get(k_):
                        les[k_] = c[k_]
                if t["code"] not in les["t"]:
                    les["t"].append(t["code"])
                for k in range(les["n"]):
                    for cl in classes:
                        covered.add((d, p + k, cl))
    lessons = list(out.values())
    for cl in data.get("classes", []):
        for d, row in enumerate(cl["grid"]):
            for p, c in enumerate(row):
                if isinstance(c, dict) and (d, p, cl["name"]) not in covered:
                    lessons.append({"d": d, "p": p, "n": span(row, p), "c": [cl["name"]], "s": c.get("s", ""),
                                    "t": [], "r": _toks(c.get("r", "")),
                                    **{k_: c[k_] for k_ in ("fa", "tg") if c.get(k_)}})
    return lessons


class Ctx:
    def __init__(self, data):
        self.data = data
        self.periods = data["periods"]
        self.days = [d["label"] for d in data["days"]]
        self.lessons = lessons_of(data)
        self.tname = {}
        for t in data.get("teachers", []):
            self.tname[_n(t["code"])] = t.get("name") or t["code"]
        self.classes = [c["name"] for c in data.get("classes", [])]
        self.teachers = [(t["code"], t.get("name") or t["code"]) for t in data.get("teachers", [])]

    def tdisp(self, code):
        return self.tname.get(_n(code), code)

    def slots(self, l):
        return [(l["d"], l["p"] + k) for k in range(l.get("n", 1)) if l["p"] + k < len(self.periods)]

    def when(self, d, p):
        pr = self.periods[p]
        return f"{self.days[d]} {pr['label']}" + (f" ({pr['time']})" if pr.get("time") else "")

    def lab(self, l):
        return " ".join(x for x in (", ".join(l["c"]), l["s"]) if x) or "a lesson"

    def teacher_match(self, spec):
        """Teacher codes the rule's 'teacher' field refers to ('*' = everyone)."""
        spec = _n(spec)
        if spec in ("", "*", "ALL"):
            return [c for c, _ in self.teachers]
        out = [c for c, nm in self.teachers if spec in (_n(c), _n(nm))]
        return out

    def day_ok(self, d, tokens):
        if not tokens:
            return True
        lab = _n(self.days[d])
        return any(lab[:3] == _n(t)[:3] for t in tokens)

    def period_ok(self, p, tokens):
        if not tokens:
            return True
        pr = self.periods[p]
        names = {_n(pr["label"]), _n(pr.get("time", "")), str(pr.get("n", ""))}
        return any(_n(t) in names for t in tokens)


# ---------------------------------------------------------------------------------------- checks
def _clash(ctx, rule, who_of, noun):
    by = defaultdict(set)
    for i, l in enumerate(ctx.lessons):
        for d, p in ctx.slots(l):
            if not ctx.periods[p].get("brk"):
                for w in who_of(l):
                    by[(_n(w), w, d, p)].add(i)
    out = []
    for (_, w, d, p), ids in sorted(by.items(), key=lambda kv: (kv[0][2], kv[0][3], kv[0][0])):
        if len(ids) > 1:
            shown = noun(w)
            out.append(f"{shown} is in {len(ids)} lessons at {ctx.when(d, p)}: " +
                       " AND ".join(ctx.lab(ctx.lessons[i]) for i in sorted(ids)))
    return out


def chk_teacher_clash(ctx, r):
    return _clash(ctx, r, lambda l: l["t"], ctx.tdisp)


def chk_class_clash(ctx, r):
    return _clash(ctx, r, lambda l: l["c"], lambda w: w)


def chk_room_clash(ctx, r):
    return _clash(ctx, r, lambda l: l["r"], lambda w: w)


def chk_break(ctx, r):
    out = []
    for l in ctx.lessons:
        for d, p in ctx.slots(l):
            if ctx.periods[p].get("brk"):
                out.append(f"{ctx.lab(l)} is placed in a break ({ctx.when(d, p)}).")
    return out


def chk_no_teacher(ctx, r):
    return [f"{ctx.lab(l)} at {ctx.when(l['d'], l['p'])} has no teacher." for l in ctx.lessons if not l["t"]]


def _teacher_slots(ctx, codes):
    cs = {_n(c) for c in codes}
    by = defaultdict(set)
    for l in ctx.lessons:
        for t in l["t"]:
            if _n(t) in cs:
                for d, p in ctx.slots(l):
                    by[_n(t)].add((d, p))
    return by


def chk_teacher_max_day(ctx, r):
    mx, out = int(r.get("max", 0) or 0), []
    codes = ctx.teacher_match(r.get("teacher", "*"))
    for t, sl in _teacher_slots(ctx, codes).items():
        per = defaultdict(int)
        for d, p in sl:
            per[d] += 1
        for d, n in sorted(per.items()):
            if n > mx:
                out.append(f"{ctx.tdisp(t)} has {n} lessons on {ctx.days[d]} (limit {mx}).")
    return out


def chk_teacher_max_week(ctx, r):
    mx = int(r.get("max", 0) or 0)
    return [f"{ctx.tdisp(t)} has {len(sl)} lessons a week (limit {mx})."
            for t, sl in _teacher_slots(ctx, ctx.teacher_match(r.get("teacher", "*"))).items() if len(sl) > mx]


def chk_teacher_max_consec(ctx, r):
    mx, out = int(r.get("max", 0) or 0), []
    for t, sl in _teacher_slots(ctx, ctx.teacher_match(r.get("teacher", "*"))).items():
        for d in sorted({d for d, _ in sl}):
            ps = sorted(p for dd, p in sl if dd == d)
            run = best = 1
            end = ps[0]
            for a, b in zip(ps, ps[1:]):
                run = run + 1 if b == a + 1 else 1
                if run > best:
                    best, end = run, b
            if best > mx:
                out.append(f"{ctx.tdisp(t)} teaches {best} lessons in a row on {ctx.days[d]} "
                           f"(ending {ctx.periods[end]['label']}; limit {mx}).")
    return out


def chk_teacher_unavailable(ctx, r):
    days, per, out = _csv(r.get("days")), _csv(r.get("periods")), []
    cs = {_n(c) for c in ctx.teacher_match(r.get("teacher", ""))}
    if not cs:
        return [f"Rule names a teacher that is not in this timetable: “{r.get('teacher', '')}”."]
    for l in ctx.lessons:
        for t in l["t"]:
            if _n(t) in cs:
                for d, p in ctx.slots(l):
                    if ctx.day_ok(d, days) and ctx.period_ok(p, per):
                        out.append(f"{ctx.tdisp(t)} is not available at {ctx.when(d, p)} but teaches {ctx.lab(l)}.")
    return out


def _subj_ok(spec, s):
    spec = _n(spec)
    return spec in ("", "*", "ALL") or spec == _n(s) or spec in [_n(x) for x in re.split(r"[/,]", s or "")]


def chk_subject_max_day(ctx, r):
    mx, out = int(r.get("max", 0) or 0), []
    cnt = defaultdict(int)
    for l in ctx.lessons:
        if _subj_ok(r.get("subject", "*"), l["s"]):
            for c in l["c"]:
                for d, p in ctx.slots(l):
                    cnt[(c, _n(l["s"]), l["s"], d)] += 1
    for (c, _, s, d), n in sorted(cnt.items()):
        if n > mx:
            out.append(f"{c} has {n} {s or 'lessons'} periods on {ctx.days[d]} (limit {mx}).")
    return out


def chk_subject_periods(ctx, r):
    per, mode, out = _csv(r.get("periods")), r.get("mode", "never in"), []
    for l in ctx.lessons:
        if _subj_ok(r.get("subject", ""), l["s"]) and l["s"]:
            for d, p in ctx.slots(l):
                inside = ctx.period_ok(p, per)
                if (mode == "never in" and inside) or (mode == "only in" and not inside):
                    out.append(f"{ctx.lab(l)} is at {ctx.when(d, p)}, which is not allowed.")
    return out


def chk_class_week_count(ctx, r):
    op, want, out = r.get("op", "exactly"), int(r.get("count", 0) or 0), []
    cls = _n(r.get("class", "*"))
    names = ctx.classes if cls in ("", "*", "ALL") else [c for c in ctx.classes if _n(c) == cls]
    if not names:
        return [f"Rule names a class that is not in this timetable: “{r.get('class', '')}”."]
    cnt = defaultdict(int)
    for l in ctx.lessons:
        if _subj_ok(r.get("subject", ""), l["s"]):
            for c in l["c"]:
                cnt[c] += len(ctx.slots(l))
    for c in names:
        n = cnt.get(c, 0)
        bad = (op == "exactly" and n != want) or (op == "at least" and n < want) or (op == "at most" and n > want)
        if bad:
            out.append(f"{c} has {n} {r.get('subject')} lessons a week (needs {op} {want}).")
    return out


# kinds: teacher | class | subject | int | days | periods | choice:<a>|<b>
TYPES = {
    "teacher_clash": dict(label="A teacher is never in two lessons at once", fields=[], builtin=True,
                          check=chk_teacher_clash, text=lambda r: "No teacher in two lessons at the same time"),
    "class_clash": dict(label="A class is never in two lessons at once", fields=[], builtin=True,
                        check=chk_class_clash, text=lambda r: "No class in two lessons at the same time"),
    "room_clash": dict(label="A lab / field is never double-booked", fields=[], builtin=True,
                       check=chk_room_clash, text=lambda r: "No lab or field used by two lessons at once"),
    "break_lessons": dict(label="No lessons during breaks", fields=[], builtin=True,
                          check=chk_break, text=lambda r: "No lessons in break periods"),
    "no_teacher": dict(label="Every lesson has a teacher", fields=[], builtin=True,
                       check=chk_no_teacher, text=lambda r: "Every lesson has a teacher"),
    "teacher_max_day": dict(label="Teacher: most lessons in a day", fields=[("teacher", "Teacher (* = everyone)", "teacher"),
                            ("max", "Most lessons a day", "int")], check=chk_teacher_max_day,
                            text=lambda r: f"{_who(r)}: at most {r.get('max')} lessons a day"),
    "teacher_max_week": dict(label="Teacher: most lessons in a week", fields=[("teacher", "Teacher (* = everyone)", "teacher"),
                             ("max", "Most lessons a week", "int")], check=chk_teacher_max_week,
                             text=lambda r: f"{_who(r)}: at most {r.get('max')} lessons a week"),
    "teacher_max_consec": dict(label="Teacher: most lessons in a row", fields=[("teacher", "Teacher (* = everyone)", "teacher"),
                               ("max", "Most lessons in a row", "int")], check=chk_teacher_max_consec,
                               text=lambda r: f"{_who(r)}: at most {r.get('max')} lessons in a row"),
    "teacher_unavailable": dict(label="Teacher: not available at certain times", fields=[
        ("teacher", "Teacher", "teacher"), ("days", "Days (blank = every day)", "days"),
        ("periods", "Lessons / times (blank = all)", "periods")], check=chk_teacher_unavailable,
        text=lambda r: f"{r.get('teacher')}: not on {', '.join(_csv(r.get('days'))) or 'any day'}"
                       f" at {', '.join(_csv(r.get('periods'))) or 'any lesson'}"),
    "subject_max_day": dict(label="Class: most periods of a subject in a day", fields=[
        ("subject", "Subject (* = every subject)", "subject"), ("max", "Most periods a day", "int")],
        check=chk_subject_max_day,
        text=lambda r: f"{_every(r.get('subject'), 'Every subject')}: at most {r.get('max')} periods a day for a class"),
    "subject_periods": dict(label="Subject: allowed / forbidden lessons", fields=[
        ("subject", "Subject", "subject"), ("mode", "Rule", "choice:never in|only in"),
        ("periods", "Lessons / times", "periods")], check=chk_subject_periods,
        text=lambda r: f"{r.get('subject')}: {r.get('mode', 'never in')} {', '.join(_csv(r.get('periods')))}"),
    "class_week_count": dict(label="Class: lessons of a subject in a week", fields=[
        ("class", "Class (* = every class)", "class"), ("subject", "Subject", "subject"),
        ("op", "Needs", "choice:exactly|at least|at most"), ("count", "Lessons a week", "int")],
        check=chk_class_week_count,
        text=lambda r: f"{_every(r.get('class'), 'Every class')} {r.get('subject')}: {r.get('op', 'exactly')} {r.get('count')} a week"),
}


import rules_more as RM                                       # Parts 10 - 14: distribution, workload, labs
for _k, (_lab, _fields, _text) in RM.TYPES.items():
    TYPES[_k] = dict(label=_lab, fields=_fields, check=RM.check(_k), text=_text)


def _every(v, word):
    return word if str(v or "").strip() in ("", "*") else v


def _who(r):
    t = r.get("teacher") or "*"
    return "Every teacher" if t.strip() in ("*", "") else t


def new_rule(type_, **kw) -> dict:
    r = {"id": uuid.uuid4().hex[:8], "type": type_, "enabled": True, "severity": ERR}
    r.update(RM.DEFAULTS.get(type_, {}))
    r.update(kw)
    return r


def defaults() -> list:
    return [new_rule("teacher_clash"), new_rule("class_clash"), new_rule("room_clash"),
            new_rule("break_lessons"), new_rule("no_teacher", severity=WARN)]


def describe(r: dict) -> str:
    t = TYPES.get(r.get("type"))
    return t["text"](r) if t else f"(unknown rule {r.get('type')})"


def to_json(rules) -> str:
    return json.dumps(rules, indent=2, ensure_ascii=False)


def from_json(text: str) -> list:
    rules = json.loads(text)
    if isinstance(rules, dict):
        rules = rules.get("rules", [])
    out = []
    for r in rules:
        if isinstance(r, dict) and r.get("type") in TYPES:
            r.setdefault("id", uuid.uuid4().hex[:8])
            r.setdefault("enabled", True)
            r.setdefault("severity", ERR)
            out.append(r)
    return out


# ---------------------------------------------------------------------------------------- run
def run(data: dict, rules: list) -> dict:
    ctx = Ctx(data)
    issues, errors, warns, checked = [], 0, 0, 0
    for num, r in enumerate(rules, 1):                         # numbers match the Constraints tab
        t = TYPES.get(r.get("type"))
        if not t or not r.get("enabled", True):
            continue
        checked += 1
        try:
            msgs = t["check"](ctx, r)
        except Exception as e:                                   # a badly filled rule must not stop publishing checks
            msgs = [f"This rule could not be checked ({e}). Open it in the Constraints tab and correct it."]
        sev = r.get("severity", ERR)
        info = [m for m in msgs if m.endswith("exception review")]      # for the record: never blocks publishing
        msgs = [m for m in msgs if m not in info]
        for m in msgs[:MAX_PER_RULE]:
            issues.append({"sev": sev, "num": num, "rule": describe(r), "msg": m})
        if len(msgs) > MAX_PER_RULE:
            issues.append({"sev": sev, "num": num, "rule": describe(r), "msg": f"…and {len(msgs) - MAX_PER_RULE} more."})
        for m in info[:MAX_PER_RULE]:
            issues.append({"sev": WARN, "num": num, "rule": describe(r), "msg": m})
        warns += len(info[:MAX_PER_RULE])
        if msgs:
            if sev == ERR:
                errors += len(msgs)
            else:
                warns += len(msgs)
    return {"issues": issues, "errors": errors, "warnings": warns, "checked": checked,
            "lessons": len(ctx.lessons)}


def summary_line(rep: dict) -> str:
    if not rep["checked"]:
        return "Constraints: none switched on."
    if not rep["issues"]:
        return f"Constraints: ✔ all {rep['checked']} rules passed ({rep['lessons']} lessons checked)."
    failed = ", ".join(str(n) for n in sorted({i["num"] for i in rep["issues"]}))
    return (f"Constraints: ✖ {rep['errors']} must-fix problem(s), {rep['warnings']} warning(s) "
            f"({rep['checked']} ticked rules, {rep['lessons']} lessons). Rules that found problems: {failed}.  "
            "Click “View constraint report”.")


def report_text(rep: dict) -> str:
    if not rep["issues"]:
        return summary_line(rep)
    lines = [summary_line(rep).replace("  Click “View constraint report”.", ""), ""]
    for sev, title in ((ERR, "MUST FIX (publishing is blocked)"), (WARN, "WARNINGS")):
        items = [i for i in rep["issues"] if i["sev"] == sev]
        if not items:
            continue
        lines.append(title)
        lines.append("-" * len(title))
        rule = None
        for i in items:
            if (i["num"], i["rule"]) != rule:
                rule = (i["num"], i["rule"])
                lines.append(f"\n● Rule {i['num']}: {i['rule']}")
            lines.append(f"    - {i['msg']}")
        lines.append("")
    return "\n".join(lines)
