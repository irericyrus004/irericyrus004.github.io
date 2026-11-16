"""
FIX - after the timetable is checked with the rules, PREPFIX moves lessons until every rule it can satisfy is
satisfied. What cannot be fixed is listed with the rule it still breaks (and marked on the preview).

    res = fix(data, rules, progress=lambda done, total, text: None)
    res["data"]      the fixed timetable (a copy - the one given is never changed)
    res["moves"]     ["9N MATHS: Mon L7 -> Tue L2  (Rule 6: Teacher: at most 6 lessons a day)", ...]
    res["left"]      [{"num", "rule", "msg", "why", "cells": [(kind, name, day, period), ...]}, ...]
    res["before"] / res["after"]   (must-fix problems, warnings) counted by the rules

Every move is a real move on the Board of "Move lessons": a lesson only goes to a box that is free for its
teacher(s), class(es) and lab/field, not a break, not a box the class may not use - or it swaps with a lesson of
the same length. A move is kept only if the number of must-fix problems goes DOWN (and warnings never pay for
it). Nothing is guessed: rules that moving cannot satisfy (a number of lessons a week, a lesson without a
teacher) are reported, not "fixed".
"""
from __future__ import annotations

import time
from collections import defaultdict
from functools import lru_cache

import constraints as K
import move_logic as ML
import rules_more as RM

NOT_BY_MOVING = {"teacher_max_week": "the number of lessons a week does not change by moving lessons — change the "
                                     "teacher's load in the timetable program",
                 "class_week_count": "the number of lessons a week does not change by moving lessons — change the "
                                     "lessons in the timetable program",
                 "no_teacher": "a lesson without a teacher needs a teacher assigned in the timetable program"}


_N = lru_cache(maxsize=None)(lambda s: K._n(s))


def _n(s):
    try:
        return _N(s)
    except TypeError:
        return K._n(s)


class _FixBoard(ML.Board):
    """A Board whose move checks look only at clashes, breaks and blocked boxes - the rules are scored here."""
    def _rule_check(self, changes, rules=None):
        return [], []


# ------------------------------------------------------------------------------------------- offences
def _offences(ctx, r):
    """[(message, [lesson index, ...], excess)] - like the rule's check, but naming the lessons and how far over."""
    typ, out = r.get("type"), []
    P = ctx.periods
    if typ in ("teacher_clash", "class_clash", "room_clash"):
        who = {"teacher_clash": lambda l: l["t"], "class_clash": lambda l: l["c"], "room_clash": lambda l: l["r"]}[typ]
        by = defaultdict(set)
        for i, l in enumerate(ctx.lessons):
            for d, p in ctx.slots(l):
                if not P[p].get("brk"):
                    for w in who(l):
                        by[(_n(w), d, p)].add(i)
        for (w, d, p), ids in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
            if len(ids) > 1:
                shown = ctx.tdisp(w) if typ == "teacher_clash" else w
                out.append((f"{shown} is in {len(ids)} lessons at {ctx.when(d, p)}", sorted(ids), len(ids) - 1))
    elif typ == "break_lessons":
        for i, l in enumerate(ctx.lessons):
            if any(P[p].get("brk") for _, p in ctx.slots(l)):
                out.append((f"{ctx.lab(l)} is placed in a break ({ctx.when(l['d'], l['p'])})", [i], 1))
    elif typ == "no_teacher":
        for i, l in enumerate(ctx.lessons):
            if not l["t"]:
                out.append((f"{ctx.lab(l)} at {ctx.when(l['d'], l['p'])} has no teacher", [i], 1))
    elif typ in ("teacher_max_day", "teacher_max_week", "teacher_max_consec"):
        mx = int(r.get("max", 0) or 0)
        codes = {_n(c) for c in ctx.teacher_match(r.get("teacher", "*"))}
        mine = defaultdict(list)                           # teacher -> [(d, p, lesson index)]
        for i, l in enumerate(ctx.lessons):
            for t in l["t"]:
                if _n(t) in codes:
                    for d, p in ctx.slots(l):
                        mine[_n(t)].append((d, p, i))
        for t, sl in mine.items():
            if typ == "teacher_max_week":
                if len(sl) > mx:
                    out.append((f"{ctx.tdisp(t)} has {len(sl)} lessons a week (limit {mx})",
                                sorted({i for _, _, i in sl}), len(sl) - mx))
                continue
            for d in sorted({d for d, _, _ in sl}):
                day = sorted((p, i) for dd, p, i in sl if dd == d)
                if typ == "teacher_max_day":
                    if len(day) > mx:
                        out.append((f"{ctx.tdisp(t)} has {len(day)} lessons on {ctx.days[d]} (limit {mx})",
                                    sorted({i for _, i in day}), len(day) - mx))
                else:
                    run, best, ids, cur = 1, 1, set(), [day[0]]
                    for a, b in zip(day, day[1:]):
                        if b[0] == a[0] + 1:
                            run += 1
                            cur.append(b)
                        else:
                            run, cur = 1, [b]
                        if run > mx:
                            ids |= {i for _, i in cur}
                        best = max(best, run)
                    if best > mx:
                        out.append((f"{ctx.tdisp(t)} teaches {best} lessons in a row on {ctx.days[d]} (limit {mx})",
                                    sorted(ids), best - mx))
    elif typ == "teacher_unavailable":
        days, per = K._csv(r.get("days")), K._csv(r.get("periods"))
        cs = {_n(c) for c in ctx.teacher_match(r.get("teacher", ""))}
        for i, l in enumerate(ctx.lessons):
            if any(_n(t) in cs for t in l["t"]):
                for d, p in ctx.slots(l):
                    if ctx.day_ok(d, days) and ctx.period_ok(p, per):
                        out.append((f"{ctx.tdisp(next(t for t in l['t'] if _n(t) in cs))} is not available at "
                                    f"{ctx.when(d, p)} but teaches {ctx.lab(l)}", [i], 1))
                        break
    elif typ == "subject_max_day":
        mx = int(r.get("max", 0) or 0)
        cnt = defaultdict(list)
        for i, l in enumerate(ctx.lessons):
            if K._subj_ok(r.get("subject", "*"), l["s"]):
                for c in l["c"]:
                    for d, p in ctx.slots(l):
                        cnt[(c, _n(l["s"]), l["s"], d)].append(i)
        for (c, _, s, d), ids in sorted(cnt.items()):
            if len(ids) > mx:
                out.append((f"{c} has {len(ids)} {s or 'lessons'} periods on {ctx.days[d]} (limit {mx})",
                            sorted(set(ids)), len(ids) - mx))
    elif typ == "subject_periods":
        per, mode = K._csv(r.get("periods")), r.get("mode", "never in")
        for i, l in enumerate(ctx.lessons):
            if K._subj_ok(r.get("subject", ""), l["s"]) and l["s"]:
                for d, p in ctx.slots(l):
                    inside = ctx.period_ok(p, per)
                    if (mode == "never in" and inside) or (mode == "only in" and not inside):
                        out.append((f"{ctx.lab(l)} is at {ctx.when(d, p)}, which is not allowed", [i], 1))
                        break
    elif typ == "class_week_count":
        for m in K.chk_class_week_count(ctx, r):
            out.append((m.rstrip("."), [], 1))
    elif typ in RM.OFFENCES:                                  # Parts 10 - 14
        out = [(m.rstrip("."), ids, ex) for m, ids, ex in RM.OFFENCES[typ](ctx, r) if ex > 0 or ids]
    return out


class _Scorer:
    def __init__(self, board, rules):
        self.b = board
        self.rules = [(num, r) for num, r in enumerate(rules, 1) if r.get("enabled", True) and r.get("type") in K.TYPES]

    def ctx(self, lessons):
        return K.Ctx(self.b._sim_data(lessons))

    def all(self, lessons):
        """[(num, rule, severity, message, [lesson idx], excess)]"""
        ctx, out = self.ctx(lessons), []
        for num, r in self.rules:
            for msg, ids, ex in _offences(ctx, r):
                out.append((num, r, r.get("severity", K.ERR), msg, ids, ex))
        return out

    def score(self, lessons):
        e = w = 0
        for _, _, sev, _, _, ex in self.all(lessons):
            if sev == K.ERR:
                e += ex
            else:
                w += ex
        return e, w


def _subset(board, Ls):
    """Every lesson that shares a teacher, class or lab/field with the given lessons - the only ones whose rule
    problems can change when those lessons move."""
    seen, out = set(), []
    for L in Ls:
        for kind, names in (("t", L["t"]), ("c", L["c"]), ("r", L["r"])):
            for nm in names:
                for X in board.by_owner.get((kind, ML._u(nm)), {}).values():
                    if id(X) not in seen:
                        seen.add(id(X))
                        out.append(X)
    return out


def _sim(board, changes):
    moved = {id(L): (d, p) for L, d, p in changes}
    return [dict(L, d=moved[id(L)][0], p=moved[id(L)][1]) if id(L) in moved else dict(L) for L in board.lessons]


def _count(scorer, lessons):
    errs = warns = 0
    for _, _, sev, _, _, _ in scorer.all(lessons):
        if sev == K.ERR:
            errs += 1
        else:
            warns += 1
    return errs, warns


def fix(data: dict, rules: list, progress=lambda done, total, text: None, max_moves: int = 300,
        seconds: float = 120.0, warnings: bool = True) -> dict:
    board = _FixBoard(data, rules)
    sc = _Scorer(board, rules)
    before = _count(sc, board.lessons)
    moves, t0, tried_out = [], time.time(), set()
    start_e = sc.score(board.lessons)[0] or 1
    while len(moves) < max_moves and time.time() - t0 < seconds:
        cur = sc.score(board.lessons)
        if cur[0] == 0 and (cur[1] == 0 or not warnings):
            break
        # must-pass problems first; when none are left, the warnings (preferred rules) are improved too
        want = K.ERR if cur[0] else K.WARN
        offs = [o for o in sc.all(board.lessons) if o[2] == want and o[1]["type"] not in NOT_BY_MOVING and o[4]]
        # lessons to try: those in the worst problems first; a lesson that could not be helped is tried last
        cand, seen = [], set()
        for num, r, sev, msg, ids, ex in sorted(offs, key=lambda o: -o[5]):
            for i in ids:
                k = board.key(board.lessons[i])
                if k not in seen:
                    seen.add(k)
                    cand.append((k, num, r, msg))
        cand.sort(key=lambda c: c[0] in tried_out)
        progress(max(0, start_e - cur[0]), start_e, f"{cur[0]} must-fix and {cur[1]} preferred point(s) left · "
                                                    f"{len(moves)} move(s)")
        done = False
        base = {}
        for k, num, r, msg in cand:
            L = board.find(k)
            if L is None:
                continue
            best = None
            for d in range(board.D):
                for p in range(board.P):
                    res = board.check(L, d, p)
                    if res["status"] not in ("ok", "swap"):
                        continue
                    ch = [(L, d, p)] + ([(res["with"], L["d"], L["p"])] if res["status"] == "swap" else [])
                    sub = _subset(board, [x for x, _, _ in ch])
                    old = base.get(tuple(sorted(id(x) for x in sub)))
                    if old is None:
                        old = base[tuple(sorted(id(x) for x in sub))] = sc.score(sub)
                    moved = {id(x): (dd, pp) for x, dd, pp in ch}
                    s = sc.score([dict(x, d=moved[id(x)][0], p=moved[id(x)][1]) if id(x) in moved else x for x in sub])
                    de, dw = s[0] - old[0], s[1] - old[1]
                    if de < 0 or (de == 0 and dw < 0 and want == K.WARN):
                        rank = (de, dw, 0 if res["status"] == "ok" else 1, 0 if d == L["d"] else 1,
                                abs(d - L["d"]) + abs(p - L["p"]))
                        if best is None or rank < best[0]:
                            best = (rank, d, p)
            if best:
                _, d, p = best
                text = board.move(L, d, p)
                moves.append(f"{text}   (Rule {num}: {K.describe(r)})")
                done = True
                break
            tried_out.add(k)
        if not done:
            break
    after = _count(sc, board.lessons)
    # what is left, with the boxes to highlight in every view
    left = []
    grids = {("teachers", t["code"]): t for t in board.data.get("teachers", [])}
    for num, r, sev, msg, ids, ex in sc.all(board.lessons):
        cells = []
        for i in ids:
            L = board.lessons[i]
            for d, p in board.slots(L):
                for t in L["t"]:
                    g = board._find("teachers", t, "code")
                    if g:
                        cells.append(("teachers", g["code"], d, p))
                for c in L["c"]:
                    cells.append(("classes", c, d, p))
                    cells.append(("master", c, d, p))
                for rm in L["r"]:
                    cells.append(("rooms", rm, d, p))
        why = NOT_BY_MOVING.get(r["type"]) or _impossible(board, r, ids) or ("no free place was found for these lessons without breaking another "
                                               "rule or making a clash — move one by hand in “Move lessons”, or "
                                               "change the rule")
        left.append({"num": num, "rule": K.describe(r), "sev": sev, "msg": msg, "why": why, "cells": cells})
    return {"data": board.result(), "moves": moves, "left": left, "before": before, "after": after,
            "seconds": round(time.time() - t0, 1)}


def _impossible(board, r, ids):
    """A reason when the rule cannot be met however the lessons are placed."""
    if r["type"] == "teacher_max_day" and ids:
        mx = int(r.get("max", 0) or 0)
        for t in board.lessons[ids[0]]["t"]:
            load = sum(len(board.slots(X)) for X in board.by_owner.get(("t", ML._u(t)), {}).values()) // 1
            load = len(board.by_owner.get(("t", ML._u(t)), {}))
            if load > mx * board.D:
                return (f"{board.tdisp(t)} has {load} lessons a week — more than {mx} a day × {board.D} days = "
                        f"{mx * board.D}. No placement can obey this rule: lower the load or raise the limit")
    return None


def bad_marks(left) -> list:
    """For the preview: [(kind, name, day, period, "Rule n · rule — problem")] for every must-fix problem left."""
    out = []
    for it in left:
        if it["sev"] != K.ERR:
            continue
        for kind, name, d, p in it["cells"]:
            out.append((kind, name, d, p, f"Rule {it['num']} · {it['rule']} — {it['msg']}"))
    return out


def report_text(res: dict, school: str = "") -> str:
    b, a = res["before"], res["after"]
    lines = [f"FIX REPORT{(' — ' + school) if school else ''}",
             f"Before: {b[0]} must-fix problem(s), {b[1]} warning(s).   After: {a[0]} must-fix, {a[1]} warning(s).",
             f"{len(res['moves'])} lesson move(s) made by PREPFIX ({res['seconds']} s).", ""]
    if res["moves"]:
        lines += ["MOVES MADE", "----------"] + [f"  {i}. {m}" for i, m in enumerate(res["moves"], 1)] + [""]
    errs = [x for x in res["left"] if x["sev"] == K.ERR]
    warns = [x for x in res["left"] if x["sev"] != K.ERR]
    if errs:
        lines += ["COULD NOT BE FIXED (must pass) — marked in red on the preview", "-" * 60]
        for num in sorted({x["num"] for x in errs}):
            its = [x for x in errs if x["num"] == num]
            whys = {x["why"] for x in its}
            lines += ["", f"● Rule {num}: {its[0]['rule']}"]
            if len(whys) == 1:
                lines.append(f"    Why: {its[0]['why']}")
            for x in its:
                lines.append(f"    - {x['msg']}." + (f"\n        Why: {x['why']}" if len(whys) > 1 else ""))
        lines.append("")
    if warns:
        lines += ["WARNINGS LEFT (publishing is allowed)", "-" * 37]
        for x in warns:
            lines.append(f"  - Rule {x['num']}: {x['msg']}.")
    if not errs and not warns:
        lines.append("✔ Every rule is now obeyed.")
    return "\n".join(lines)
