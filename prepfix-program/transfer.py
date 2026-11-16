"""
TEACHER CHANGE - a teacher leaves (transfer), another teacher takes over the lessons. Only the lessons handed over
change; every other teacher and class stays exactly as it is.

    lessons_of_teacher(data, code)          -> the leaving teacher's lessons (with any co-teachers of a group)
    add_teacher(data, name, code="")        -> (new data, code)   a new teacher with an empty timetable
    remove_teacher(data, code)              -> new data           (only when the teacher has no lessons left)
    fits(data, lesson, donor, recipient)    -> (True, "") or (False, "why")   at the SAME time
    hand_over(data, lesson, donor, recipient)                    -> new data   (same time; must fit)
    places(data, rules, lesson, donor, recipient)                -> where the lesson could go with the new teacher
    move_and_hand_over(data, rules, lesson, donor, recipient, d, p) -> new data   (moved, or swapped, then handed over)

A "lesson" is the dict move_logic.Board uses: {d, p, n, c: [classes], s, t: [teacher codes], r: [rooms]}.
Teacher codes are written into the teacher, class, master and lab grids and into the raw lesson list, so every
view and every check sees the new teacher. Data is never changed in place: each step returns a new copy.
"""
from __future__ import annotations

import copy
import re

import constraints as K
import move_logic as ML

_u = ML._u


def _toks(s):
    return [x.strip() for x in re.split(r"[,;]", str(s or "")) if x.strip()]


def teacher(data, code):
    return next((t for t in data.get("teachers", []) if _u(t["code"]) == _u(code)), None)


def label(data, code):
    t = teacher(data, code)
    return f"{t['code']} · {t['name']}" if t and t.get("name") else str(code)


def lessons_of_teacher(data, code) -> list:
    return sorted([L for L in K.lessons_of(data) if any(_u(t) == _u(code) for t in L["t"])],
                  key=lambda L: (L["d"], L["p"], L["c"], L["s"]))


def _empty_grid(data):
    D, P = len(data["days"]), len(data["periods"])
    return [["X" if data["periods"][p].get("brk") else "" for p in range(P)] for _ in range(D)]


def add_teacher(data, name, code=""):
    """A new teacher (e.g. the one who replaces a transferring teacher), with an empty timetable."""
    data = copy.deepcopy(data)
    name = re.sub(r"\s+", " ", str(name or "")).strip().upper()
    if not name:
        raise ValueError("Type the new teacher's name.")
    have = {_u(t["code"]) for t in data["teachers"]}
    if any(_u(t.get("name")) == _u(name) for t in data["teachers"]):
        raise ValueError(f"{name} is already a teacher in this timetable.")
    if not code:
        nums = [int(t["code"]) for t in data["teachers"] if str(t["code"]).isdigit()]
        code = str(max(nums) + 1 if nums else len(data["teachers"]) + 1)
    if _u(code) in have:
        raise ValueError(f"The teacher number {code} is already used.")
    ids = {t.get("id") for t in data["teachers"]}
    n = len(data["teachers"]) + 1
    while f"T{n}" in ids:
        n += 1
    data["teachers"].append({"id": f"T{n}", "code": str(code), "name": name, "load": 0, "grid": _empty_grid(data)})
    return data, str(code)


def remove_teacher(data, code):
    if lessons_of_teacher(data, code):
        raise ValueError("This teacher still has lessons. Hand them over first.")
    data = copy.deepcopy(data)
    data["teachers"] = [t for t in data["teachers"] if _u(t["code"]) != _u(code)]
    return data


def _slots(L, d=None, p=None):
    d = L["d"] if d is None else d
    p = L["p"] if p is None else p
    return [(d, p + k) for k in range(L.get("n", 1))]


def fits(data, L, donor, rec):
    """Can the receiving teacher take this lesson at the SAME time?"""
    if any(_u(t) == _u(rec) for t in L["t"]):
        return False, f"{label(data, rec)} already teaches this lesson."
    g = teacher(data, rec)
    if g is None:
        return False, "That teacher is not in this timetable."
    for d, p in _slots(L):
        c = g["grid"][d][p] if p < len(g["grid"][d]) else ""
        if c == "X" and not data["periods"][p].get("brk"):
            return False, f"{label(data, rec)} is marked not available at {data['days'][d]['label']} {data['periods'][p]['label']}."
        if isinstance(c, dict) or c == "^":
            other = next((M for M in lessons_of_teacher(data, rec) if (d, p) in _slots(M)), None)
            what = f"{', '.join(other['c'])} {other['s']}" if other else "another lesson"
            when = f"{data['days'][d]['label']} {data['periods'][p]['label']}"
            return False, f"{label(data, rec)} already teaches {what} at {when}."
    return True, ""


def _swap_code(cell, donor, rec):
    if isinstance(cell, dict) and cell.get("t"):
        toks = _toks(cell["t"])
        if any(_u(x) == _u(donor) for x in toks):
            cell["t"] = ", ".join(rec if _u(x) == _u(donor) else x for x in toks)


def _hand_over_in_place(data, L, donor, rec):
    """data is changed: the lesson L (at its place) goes from donor to rec in every grid and the raw list."""
    D = teacher(data, donor)
    R = teacher(data, rec)
    for d, p in _slots(L):
        cell = D["grid"][d][p]
        R["grid"][d][p] = copy.deepcopy(cell)
        D["grid"][d][p] = "X" if data["periods"][p].get("brk") else ""
        _swap_code(R["grid"][d][p], donor, rec)
        mine = {"teachers": {_u(x) for x in L["t"]}, "classes": {_u(x) for x in L["c"]},
                "master": {_u(x) for x in L["c"]}, "rooms": {_u(x) for x in L["r"]}}
        for key in ("teachers", "classes", "master", "rooms"):    # only this lesson's co-teachers, classes, labs
            for g in data.get(key, []):
                if _u(g.get("code") if key == "teachers" else g.get("name")) not in mine[key]:
                    continue
                grid = g.get("grid") or []
                if d < len(grid) and p < len(grid[d]) and (not isinstance(grid[d][p], dict) or
                                                           _u(grid[d][p].get("s", L["s"])) == _u(L["s"])):
                    _swap_code(grid[d][p], donor, rec)
    if data.get("_lessons") is not None:
        k = (L["d"], L["p"], tuple(map(_u, L["c"])), _u(L["s"]))
        for X in data["_lessons"]:
            if (X["d"], X["p"], tuple(map(_u, X["c"])), _u(X["s"])) == k and any(_u(t) == _u(donor) for t in X["t"]):
                X["t"] = [rec if _u(t) == _u(donor) else t for t in X["t"]]
    n = L.get("n", 1)
    D["load"] = max(0, int(D.get("load") or 0) - n)
    R["load"] = int(R.get("load") or 0) + n


def hand_over(data, L, donor, rec):
    ok, why = fits(data, L, donor, rec)
    if not ok:
        raise ValueError(why)
    data = copy.deepcopy(data)
    _hand_over_in_place(data, L, donor, rec)
    return data


def _board(data, rules):
    return ML.Board(data, rules if rules is not None else K.defaults())


def places(data, rules, L, donor, rec):
    """Every place the lesson can go once the new teacher has it: free for the new teacher, the class(es), the
    lab/field and any co-teachers (or a swap with a lesson of the same length), and no must-pass rule broken.
    -> [{"d", "p", "status": "ok"|"swap", "with": text, "warn": [...]}] best first"""
    b = _board(data, rules)
    L0 = b.find(b.key(L))
    if L0 is None:
        return []
    L1 = dict(L0, t=[rec if _u(t) == _u(donor) else t for t in L0["t"]])
    base = K.run(b._sim_data(b.lessons), b.rules)["errors"]
    out = []
    for d in range(b.D):
        for p in range(b.P):
            if (d, p) == (L0["d"], L0["p"]):
                continue
            res = b.check(L1, d, p)
            if res["status"] not in ("ok", "swap"):
                continue
            M = res["with"]
            if M is not None and any(_u(t) == _u(donor) for t in M["t"]):
                continue                                   # do not swap with another of the leaving teacher's lessons
            if any(b.lesson_at("t", donor, d, p + k) not in (None, L0) for k in range(L0.get("n", 1))):
                continue                                   # the leaving teacher still has a lesson there
            sim = []
            for X in b.lessons:
                if X is L0:
                    sim.append(dict(L1, d=d, p=p))
                elif M is not None and X is M:
                    sim.append(dict(M, d=L0["d"], p=L0["p"]))
                else:
                    sim.append(dict(X))
            rep = K.run(b._sim_data(sim), b.rules)
            if rep["errors"] > base:
                continue
            day = sum(len(b.slots(X)) for X in b.lessons if X["d"] == d and X is not L0 and
                      any(_u(t) == _u(rec) for t in X["t"])) + L0.get("n", 1)
            out.append({"d": d, "p": p, "status": res["status"],
                        "with": (f"{', '.join(M['c'])} {M['s']}" if M is not None else ""),
                        "warn": rep["warnings"], "day_load": day,
                        "rank": (0 if res["status"] == "ok" else 1, rep["errors"], 0 if day <= 6 else day,
                                 rep["warnings"], 0 if d == L0["d"] else 1, abs(d - L0["d"]) + abs(p - L0["p"]))})
    return sorted(out, key=lambda x: x["rank"])


def move_and_hand_over(data, rules, L, donor, rec, d, p):
    """Move the lesson (or swap it with the lesson there) and give it to the new teacher."""
    b = _board(data, rules)
    L0 = b.find(b.key(L))
    if L0 is None:
        raise ValueError("That lesson is no longer where it was.")
    L1 = dict(L0, t=[rec if _u(t) == _u(donor) else t for t in L0["t"]])
    res = b.check(L1, d, p)
    if res["status"] not in ("ok", "swap"):
        raise ValueError(res["why"])
    b._do_move(L0, d, p, res["with"] if res["status"] == "swap" else None)
    new = b.result()
    moved = dict(L0, d=d, p=p)
    _hand_over_in_place(new, moved, donor, rec)
    return new


def _shape(grid):
    """The grid without teacher codes: what is taught when (a co-teacher's name changing in a group is not a change
    to that teacher's own timetable)."""
    return [[{k: v for k, v in c.items() if k != "t"} if isinstance(c, dict) else c for c in row] for row in grid or []]


def affected(before, after):
    """Teachers and classes whose lessons moved, or teachers who gave / got lessons. Everyone else is untouched."""
    out = {"teachers": [], "classes": []}
    for key, field in (("teachers", "code"), ("classes", "name")):
        old = {_u(g[field]): g["grid"] for g in before.get(key, [])}
        for g in after.get(key, []):
            o = old.get(_u(g[field]))
            changed = o is None or (_shape(o) != _shape(g["grid"]) if key == "teachers" else _shape(o) != _shape(g["grid"]))
            if changed:
                out[key].append(g.get("name") or g[field] if key == "teachers" else g[field])
        if key == "teachers":
            gone = {_u(g[field]) for g in after.get(key, [])}
            out[key] += [g.get("name") or g[field] for g in before.get(key, []) if _u(g[field]) not in gone]
    return out
