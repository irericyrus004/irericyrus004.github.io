"""
Move lessons - the logic behind the "Move lessons" tab (no windows here, so it can be tested on its own).

A Board holds a WORKING COPY of the loaded timetable (the dict that fet_reader / sheet_reader produce).
You pick a lesson and ask  where_can_it_go()  - every day x lesson box gets a status:

    "ok"    the lesson can simply be moved there (free for the teacher(s), class(es) and lab/field, not a break,
            and none of your Constraints rules gets worse)
    "swap"  another lesson of the same length is there and the two can change places
    "no"    not allowed (the reason is given)
    "same"  where the lesson is now

move() changes the teacher, class, master and lab/field grids together, so every timetable stays in step.
undo() / redo() / reset() go back and forward. result() gives the changed timetable to publish.
"""
from __future__ import annotations

import copy

import constraints as K

_GRID_KEYS = ("teachers", "classes", "master", "rooms")


def _u(s) -> str:
    return " ".join(str(s or "").split()).upper()


class Board:
    def __init__(self, data: dict, rules: list | None = None, advice: list | None = None):
        self.base = data                                   # what was loaded (never changed)
        self.data = copy.deepcopy(data)                    # the working copy
        # rules that BLOCK a move: only what is physically impossible (a teacher / class / lab in two places, a lesson
        # in a break). advice = the rules the timetable was made with (FET): never block, they only show which places
        # keep the timetable as it was planned (★ and "keeps the plan") and which would bend it (⚠).
        self.rules = [dict(r) for r in (rules if rules is not None else K.defaults()) if r.get("enabled", True)]
        self.advice = [dict(r) for r in (advice or []) if r.get("enabled", True) and r.get("type") != "break_lessons"]
        self.days = [d["label"] for d in self.data["days"]]
        self.periods = self.data["periods"]
        self.D, self.P = len(self.days), len(self.periods)
        self.undo_stack, self.redo_stack, self.moves = [], [], []
        self._reindex()

    # ------------------------------------------------------------------ indexes
    def _find(self, key, name, field):
        n = _u(name)
        for g in self.data.get(key, []):
            if _u(g.get(field)) == n:
                return g
        return None

    def _reindex(self):
        self.lessons = K.lessons_of(self.data)
        self.at = {}                                       # (d, p) -> [lesson, ...]
        self.by_owner = {}                                 # ("t"|"c"|"r", NAME) -> {(d, p): lesson}
        for L in self.lessons:
            for d, p in self.slots(L):
                self.at.setdefault((d, p), []).append(L)
                for kind, names in (("t", L["t"]), ("c", L["c"]), ("r", L["r"])):
                    for nm in names:
                        self.by_owner.setdefault((kind, _u(nm)), {})[(d, p)] = L
        self._baseline = None

    def slots(self, L, d=None, p=None):
        d = L["d"] if d is None else d
        p = L["p"] if p is None else p
        return [(d, p + k) for k in range(L.get("n", 1))]

    def teacher_names(self):
        return [(t["code"], t.get("name") or t["code"]) for t in self.data.get("teachers", [])]

    def class_names(self):
        return [c["name"] for c in self.data.get("classes", [])]

    def lesson_at(self, kind, name, d, p):
        return self.by_owner.get((kind, _u(name)), {}).get((d, p))

    def blocked(self, kind, name, d, p) -> bool:
        """True if this class's grid marks the box as a break / not available."""
        if kind != "c":
            return False
        g = self._find("classes", name, "name")
        return bool(g) and g["grid"][d][p] == "X"

    def label(self, L) -> str:
        return " ".join(x for x in (", ".join(L["c"]), L["s"]) if x) or "lesson"

    def when(self, d, p) -> str:
        pr = self.periods[p]
        return f"{self.days[d]} {pr['label']}" + (f" ({pr['time']})" if pr.get("time") else "")

    # ------------------------------------------------------------------ constraint comparison
    def _sim_data(self, lessons):
        return {"periods": self.periods, "days": self.data["days"], "teachers": self.data.get("teachers", []),
                "classes": self.data.get("classes", []), "_lessons": lessons}

    def _issues(self, lessons):
        rep = K.run(self._sim_data(lessons), self.rules)
        return {(i["sev"], i["msg"]) for i in rep["issues"]}

    def baseline(self):
        if self._baseline is None:
            self._baseline = self._issues(self.lessons)
        return self._baseline

    def _relevant(self, r, Ls):
        """Can this rule be affected by moving these lessons? (Many rules name one teacher, class, tag or FET
        activity - only those that touch the moved lessons are checked, so moving stays quick with hundreds of rules.)"""
        nm = lambda s: _u(s)
        t = r.get("type")
        if r.get("teacher") and str(r["teacher"]).strip() not in ("*", ""):
            want = {nm(r["teacher"])}
            codes = {nm(c) for c, n in self.teacher_names() if nm(c) in want or nm(n) in want}
            if not any(codes & {nm(x) for x in L["t"]} for L in Ls):
                return False
        if t == "not_available":
            key = {"teacher": "t", "class": "c", "room": "r"}.get(r.get("who"), "t")
            return any(nm(r.get("name")) in {nm(x) for x in L[key]} for L in Ls)
        if t in ("tag_max_daily", "tag_min_gaps", "tags_not_overlap"):
            tags = {nm(x) for x in [r.get("tag"), r.get("tag2")] + str(r.get("tags") or "").split("|") if x and str(x).strip()}
            return any(tags & {nm(x) for x in str(L.get("tg") or "").split("|") if x.strip()} for L in Ls)
        if t in ("min_days_between", "occupy_slots"):
            ids = {x.strip() for x in str(r.get("ids") or "").split(",")}
            return any(str(L.get("fa") or "") in ids for L in Ls)
        if t == "allowed_slots" and r.get("subject"):
            return any(nm(L["s"]) == nm(r["subject"]) for L in Ls)
        return True

    def _rule_check(self, changes, rules=None):
        """changes: [(lesson, new_d, new_p)]. Returns (errors, warnings) that are NEW because of the change.
        Only the lessons that share a teacher, class or lab/field with the moved lessons (or sit at the old / new
        times) and only the rules that can touch them are checked: the answer is the same, much faster."""
        # by the lesson's key, not the object: a lesson picked before the last move is still found
        changes = [(self.find(self.key(L)) or L, d, p) for L, d, p in changes]
        moved = {id(L): (d, p) for L, d, p in changes}
        Ls = [L for L, _, _ in changes]
        rules = [r for r in (self.rules if rules is None else rules) if self._relevant(r, Ls)]
        if not rules:
            return [], []
        times = {s for L, d, p in changes for s in self.slots(L) + self.slots(L, d, p)}
        seen, sub = set(), []
        for L in Ls:
            for kind, names in (("t", L["t"]), ("c", L["c"]), ("r", L["r"])):
                for nm_ in names:
                    for X in self.by_owner.get((kind, _u(nm_)), {}).values():
                        if id(X) not in seen:
                            seen.add(id(X))
                            sub.append(X)
        for s in times:
            for X in self.at.get(s, []):
                if id(X) not in seen:
                    seen.add(id(X))
                    sub.append(X)
        before = K.run(self._sim_data([dict(X) for X in sub]), rules)
        after = K.run(self._sim_data([dict(X, d=moved[id(X)][0], p=moved[id(X)][1]) if id(X) in moved else dict(X)
                                      for X in sub]), rules)
        key = lambda rep: {(i["sev"], i["msg"]) for i in rep["issues"]}
        new = key(after) - key(before)
        return ([m for s, m in sorted(new) if s == K.ERR], [m for s, m in sorted(new) if s == K.WARN])

    # ------------------------------------------------------------------ advice (never blocks)
    def same_subject(self, L):
        """The other lessons of the same subject for the same class(es) - e.g. every CHEM of 4E (doubles included)."""
        cls, sub = set(map(_u, L["c"])), _u(L["s"])
        if not sub or not cls:
            return []
        out = [X for X in self.lessons if X is not L and _u(X["s"]) == sub and (set(map(_u, X["c"])) & cls)]
        return sorted(out, key=lambda X: (X["d"], X["p"]))

    def subject_week(self, L) -> str:
        """'CHEM · 4E: 4 lessons a week — Mon L3–L4 (double), Wed L2, Fri L5' (the lesson itself included)."""
        allL = sorted(self.same_subject(L) + [L], key=lambda X: (X["d"], X["p"]))
        parts, total = [], 0
        for X in allL:
            n = X.get("n", 1)
            total += n
            a = self.periods[X["p"]]["label"]
            b = self.periods[X["p"] + n - 1]["label"] if n > 1 else ""
            parts.append(f"{self.days[X['d']].title()[:3]} {a}" + (f"–{b} (double)" if n > 1 else "")
                         + (" ← this one" if X is L else ""))
        return (f"{L['s']} · {', '.join(L['c'])}: {total} lesson{'' if total == 1 else 's'} a week — " + ", ".join(parts))

    def _spread(self, L, d, M=None):
        """Plain advice when no FET rules came with the timetable (aSc): a class should not get the same subject twice
        on one day in separate lessons."""
        out = []
        for X in self.same_subject(L):
            if X is M or X["d"] != d:
                continue
            if X["d"] == L["d"] and d == L["d"]:
                continue                                      # it is already on that day now: nothing new
            out.append(f"{', '.join(L['c'])} already has {L['s']} on {self.days[d].title()} ({self.when(X['d'], X['p'])}).")
            break
        return out

    def _advise(self, changes):
        """Messages for the places that would bend the plan the timetable was made with (empty = keeps the plan)."""
        if self.advice:
            errs, warns = self._rule_check(changes, self.advice)
            return ([("Breaks a FET rule: " + m) for m in errs] + [("Against a FET preference: " + m) for m in warns])
        out = []
        for i, (L, d, p) in enumerate(changes):
            M = changes[1 - i][0] if len(changes) == 2 else None
            out += self._spread(L, d, M)
        return out

    # ------------------------------------------------------------------ where can a lesson go
    def _others(self, L, d, p, n):
        """Other lessons sharing a teacher, class or lab/field with L that sit in the target boxes."""
        want = {(d, p + k) for k in range(n)}
        out = []
        for M in self.lessons:
            if M is L:
                continue
            if not (set(self.slots(M)) & want):
                continue
            if (set(map(_u, M["t"])) & set(map(_u, L["t"]))) or (set(map(_u, M["c"])) & set(map(_u, L["c"]))) \
                    or (set(map(_u, M["r"])) & set(map(_u, L["r"]))):
                out.append(M)
        return out

    def check(self, L, d, p) -> dict:
        """-> {"status": ok|swap|no|same, "why": text, "warn": [..], "with": lesson-or-None}"""
        L = self.find(self.key(L)) or L                      # an older copy of the lesson -> the lesson as it is now
        n = L.get("n", 1)
        if (d, p) == (L["d"], L["p"]):
            return {"status": "same", "why": "This is where the lesson is now.", "warn": [], "with": None}
        if p + n > self.P:
            return {"status": "no", "why": "A double lesson does not fit here (the day ends).", "warn": [], "with": None}
        for k in range(n):
            if self.periods[p + k].get("brk"):
                return {"status": "no", "why": f"{self.when(d, p + k)} is a break.", "warn": [], "with": None}
        for c in L["c"]:
            for k in range(n):
                if self.blocked("c", c, d, p + k) and (d, p + k) not in self.slots(L):
                    return {"status": "no", "why": f"{c} cannot have a lesson at {self.when(d, p + k)}.",
                            "warn": [], "with": None}
        others = self._others(L, d, p, n)
        if not others:
            errs, warns = self._rule_check([(L, d, p)])
            if errs:
                return {"status": "no", "why": errs[0] + (f"  (+{len(errs) - 1} more)" if len(errs) > 1 else ""),
                        "warn": warns, "with": None}
            adv = self._advise([(L, d, p)])
            return {"status": "ok", "why": "Free - the lesson can move here." + ("" if adv else " Keeps the plan."),
                    "warn": warns + adv, "with": None}
        # something is in the way: say who, then see if a swap works
        why = []
        for M in others[:3]:
            who = []
            for nm, mine, theirs in (("teacher", L["t"], M["t"]), ("class", L["c"], M["c"]), ("lab/field", L["r"], M["r"])):
                both = sorted(set(map(_u, mine)) & set(map(_u, theirs)))
                if both:
                    who.append(f"{nm} {', '.join(both)}")
            why.append(f"{self.label(M)} is there ({' and '.join(who)} would clash)")
        if len(others) == 1:
            M = others[0]
            if M.get("n", 1) != n or (M["d"], M["p"]) != (d, p):
                return {"status": "no", "why": "; ".join(why) + ". It is a different length, so they cannot swap.",
                        "warn": [], "with": None}
            # M goes to L's old place: is that free for M's people (ignoring L, which leaves)?
            for k in range(n):
                if self.periods[L["p"] + k].get("brk"):
                    return {"status": "no", "why": "; ".join(why), "warn": [], "with": None}
            for X in self._others(M, L["d"], L["p"], n):
                if X is not L:
                    return {"status": "no", "why": "; ".join(why) + f". Swapping fails: {self.label(X)} is in the way "
                                                                    f"at {self.when(L['d'], L['p'])}.", "warn": [], "with": None}
            for c in M["c"]:
                for k in range(n):
                    if self.blocked("c", c, L["d"], L["p"] + k) and (L["d"], L["p"] + k) not in self.slots(M):
                        return {"status": "no", "why": f"{c} cannot have a lesson at {self.when(L['d'], L['p'] + k)}.",
                                "warn": [], "with": None}
            same = lambda X: (sorted(map(_u, X["c"])), _u(X["s"]), sorted(map(_u, X["t"])), sorted(map(_u, X["r"])))
            if same(L) == same(M):
                return {"status": "no", "why": f"{self.label(M)} is there too — the same class, subject and teacher, "
                                               "so swapping them would change nothing.", "warn": [], "with": None}
            errs, warns = self._rule_check([(L, d, p), (M, L["d"], L["p"])])
            if errs:
                return {"status": "no", "why": "Swap: " + errs[0], "warn": warns, "with": M}
            adv = self._advise([(L, d, p), (M, L["d"], L["p"])])
            return {"status": "swap", "why": f"Swap with {self.label(M)}." + ("" if adv else " Keeps the plan."),
                    "warn": warns + adv, "with": M}
        return {"status": "no", "why": "; ".join(why) + ".", "warn": [], "with": None}

    def where_can_it_go(self, L) -> dict:
        return {(d, p): self.check(L, d, p) for d in range(self.D) for p in range(self.P)}

    # ------------------------------------------------------------------ doing it
    def _owner_grids(self, L):
        grids = []
        for code in L["t"]:
            g = self._find("teachers", code, "code")
            if g:
                grids.append(g["grid"])
        for c in L["c"]:
            for key in ("classes", "master"):
                g = self._find(key, c, "name")
                if g and g["grid"] is not None and len(g["grid"]) == self.D:
                    # FET "master" tables are per class too; skip any that are not day x lesson
                    grids.append(g["grid"])
        for r in L["r"]:
            g = self._find("rooms", r, "name")
            if g:
                grids.append(g["grid"])
        seen, out = set(), []                               # the same grid can be listed twice (e.g. master = classes)
        for g in grids:
            if id(g) not in seen:
                seen.add(id(g))
                out.append(g)
        return out

    def _lift(self, L):
        """Take the lesson's boxes out of every grid (leaving them free) and return them."""
        n = L.get("n", 1)
        taken = []
        for grid in self._owner_grids(L):
            cells = [grid[L["d"]][L["p"] + k] for k in range(n)]
            for k in range(n):
                grid[L["d"]][L["p"] + k] = ""
            taken.append((grid, cells))
        return taken

    def _drop(self, taken, d, p):
        for grid, cells in taken:
            for k, c in enumerate(cells):
                grid[d][p + k] = c

    def _snapshot(self):
        return {k: copy.deepcopy(self.data.get(k)) for k in _GRID_KEYS + ("_lessons",) if k in self.data}

    def _restore(self, snap):
        for k, v in snap.items():
            self.data[k] = copy.deepcopy(v)
        self._reindex()

    def key(self, L):
        return (L["d"], L["p"], tuple(map(_u, L["c"])), _u(L["s"]), tuple(map(_u, L["t"])))

    def find(self, key):
        return next((X for X in self.lessons if self.key(X) == key), None)

    def _do_move(self, L, d, p, M=None):
        """Change the grids (and the raw list). No checks, no history."""
        old = (L["d"], L["p"])
        keyL, keyM = self.key(L), (self.key(M) if M else None)
        a = self._lift(L)
        b = self._lift(M) if M else []
        self._drop(a, d, p)
        if M:
            self._drop(b, old[0], old[1])
        if self.data.get("_lessons") is not None:           # keep the raw list (Excel / PDF imports) in step
            for X in self.data["_lessons"]:
                kx = self.key(X)
                if kx == keyL:
                    X["d"], X["p"] = d, p
                elif keyM and kx == keyM:
                    X["d"], X["p"] = old
        self._reindex()
        return old

    def move(self, L, d, p) -> str:
        """Move (or swap) the lesson. Returns a one-line description. Raises ValueError if it is not allowed."""
        L = self.find(self.key(L)) or L                      # the lesson as it is now (not an older copy)
        res = self.check(L, d, p)
        if res["status"] not in ("ok", "swap"):
            raise ValueError(res["why"])
        M = res["with"] if res["status"] == "swap" else None
        self.undo_stack.append((self._snapshot(), list(self.moves)))
        self.redo_stack.clear()
        la, lb = self.label(L), (self.label(M) if M else "")
        old = self._do_move(L, d, p, M)
        text = (f"{la}: {self.when(*old)}  →  {self.when(d, p)}"
                if not M else f"{la} ⇄ {lb}: {self.when(*old)}  ⇄  {self.when(d, p)}")
        self.moves.append(text)
        return text

    # ------------------------------------------------------------------ who is involved / preview / solutions
    def tdisp(self, code):
        for c, n in self.teacher_names():
            if _u(c) == _u(code):
                return n
        return code

    def involved(self, L, M=None):
        """Teachers, classes and labs/fields of one lesson (and of the lesson it swaps with)."""
        out = {"teachers": [], "classes": [], "rooms": []}
        for X in [L] + ([M] if M else []):
            for key, vals in (("teachers", X["t"]), ("classes", X["c"]), ("rooms", X["r"])):
                for v in vals:
                    if _u(v) not in [_u(z[0]) for z in out[key]]:
                        out[key].append((v, self.tdisp(v) if key == "teachers" else v))
        return out

    def clone(self):
        b = Board.__new__(Board)
        b.base, b.data, b.rules, b.advice = self.data, copy.deepcopy(self.data), self.rules, self.advice
        b.days, b.periods, b.D, b.P = self.days, self.periods, self.D, self.P
        b.undo_stack, b.redo_stack, b.moves = [], [], []
        b._reindex()
        return b

    def diff(self, other):
        """{("teachers"|"classes"|"master"|"rooms", name): {(d, p), ...}} - the boxes that differ in `other`."""
        out = {}
        for key, field in (("teachers", "code"), ("classes", "name"), ("master", "name"), ("rooms", "name")):
            mine = {g[field]: g for g in self.data.get(key, [])}
            for g in other.data.get(key, []):
                a = mine.get(g[field])
                if a is None:
                    continue
                cells = {(d, p) for d in range(self.D) for p in range(self.P) if a["grid"][d][p] != g["grid"][d][p]}
                if cells:
                    out[(key, g[field])] = cells
        return out

    def affected(self) -> dict:
        """Teachers, classes and labs/fields whose timetable now differs from the one that was loaded.
        A lesson that was moved and then moved back (or undone) does not count.
        -> {"teachers": [code, ...], "classes": [name, ...], "rooms": [name, ...]}"""
        out = {"teachers": [], "classes": [], "rooms": []}
        for key, field in (("teachers", "code"), ("classes", "name"), ("rooms", "name")):
            before = {_u(g[field]): g for g in self.base.get(key, [])}
            for g in self.data.get(key, []):
                a = before.get(_u(g[field]))
                if a is not None and a["grid"] != g["grid"]:
                    out[key].append(g[field])
        return out

    def preview(self, steps):
        """steps: [(lesson, day, period), ...] done one after the other on a COPY. Nothing here is changed.
        -> {"after": Board, "changed": diff, "texts": [...], "warn": [...], "problems_before": n, "problems_after": n}"""
        b2 = self.clone()
        keys = [(self.key(L), d, p) for L, d, p in steps]
        texts, warns = [], []
        for k, d, p in keys:
            L2 = b2.find(k)
            if L2 is None:
                raise ValueError("That lesson is no longer where it was.")
            res = b2.check(L2, d, p)
            warns += res.get("warn", [])
            texts.append(b2.move(L2, d, p))
        return {"after": b2, "changed": self.diff(b2), "texts": texts, "warn": warns,
                "before_n": len(self.baseline()), "after_n": len(b2.baseline())}

    def solutions(self, L):
        """Every place the lesson can go, best first: free before swap, no warning before warning, nearest first."""
        out = []
        for (d, p), r in self.where_can_it_go(L).items():
            if r["status"] in ("ok", "swap"):
                imp = self.involved(L, r["with"])
                bend = sum(2 if str(w).startswith("Breaks") else 1 for w in r["warn"])
                rank = (bend, 0 if r["status"] == "ok" else 1,
                        0 if d == L["d"] else 1, abs(d - L["d"]), abs(p - L["p"]))
                out.append(dict(r, d=d, p=p, rank=rank, who=imp))
        return sorted(out, key=lambda x: x["rank"])

    def _blockers(self, L, d, p):
        n = L.get("n", 1)
        if p + n > self.P or any(self.periods[p + k].get("brk") for k in range(n)):
            return []
        return self._others(L, d, p, n)

    def chains(self, L, limit=12, max_blockers=14, per_blocker=4):
        """Two-step answers: where a lesson is blocked by ONE other lesson, move that one away first.
        -> [{"first": (lesson, d, p), "then": (lesson, d, p), "who": involved, "text": str}]"""
        keyL = self.key(L)
        res_all = self.where_can_it_go(L)
        blockers = {}
        for (d, p), r in res_all.items():
            if r["status"] != "no":
                continue
            bl = self._blockers(L, d, p)
            if len(bl) == 1:
                blockers.setdefault(self.key(bl[0]), []).append((d, p))
        order = sorted(blockers, key=lambda k: (len(blockers[k]) * -1))[:max_blockers]
        out = []
        for kM in order:
            M = self.find(kM)
            if M is None:
                continue
            dests = sorted([c for c, r in self.where_can_it_go(M).items() if r["status"] == "ok"],
                           key=lambda c: (0 if c[0] == M["d"] else 1, abs(c[0] - M["d"]), abs(c[1] - M["p"])))[:per_blocker]
            for (md, mp) in dests:
                snap = self._snapshot()
                try:
                    la = self.label(M)
                    old = self._do_move(self.find(kM), md, mp)
                    L2 = self.find(keyL)
                    for (d, p) in blockers[kM]:
                        r = self.check(L2, d, p)
                        if r["status"] == "ok":
                            out.append({"first": (kM, md, mp), "then": (keyL, d, p), "warn": r["warn"],
                                        "text": f"1) Move {la} to {self.when(md, mp)}   2) Move {self.label(L2)} to "
                                                f"{self.when(d, p)}"})
                finally:
                    self._restore(snap)
            if len(out) >= limit * 3:
                break
        # attach real lessons (after the restore the objects are new) and who is involved
        final = []
        for o in out:
            M, L2 = self.find(o["first"][0]), self.find(o["then"][0])
            if M is None or L2 is None:
                continue
            o["first"], o["then"] = (M, o["first"][1], o["first"][2]), (L2, o["then"][1], o["then"][2])
            o["who"] = self.involved(L2, M)
            o["rank"] = (len(o["warn"]), len(o["who"]["teachers"]) + len(o["who"]["classes"]),
                         abs(o["then"][1] - L2["d"]) + abs(o["then"][2] - L2["p"]))
            final.append(o)
        return sorted(final, key=lambda x: x["rank"])[:limit]

    def undo(self):
        if not self.undo_stack:
            return None
        snap, moves = self.undo_stack.pop()
        self.redo_stack.append((self._snapshot(), list(self.moves)))
        self._restore(snap)
        undone = self.moves[-1] if len(self.moves) > len(moves) else ""
        self.moves = moves
        return undone

    def redo(self):
        if not self.redo_stack:
            return None
        snap, moves = self.redo_stack.pop()
        self.undo_stack.append((self._snapshot(), list(self.moves)))
        self._restore(snap)
        self.moves = moves
        return moves[-1] if moves else ""

    def reset(self):
        self.data = copy.deepcopy(self.base)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.moves = []
        self._reindex()

    @property
    def changed(self) -> bool:
        return bool(self.moves)

    def result(self) -> dict:
        return copy.deepcopy(self.data)

    def problems(self):
        """The Constraints report for the working copy (same checks as before publishing)."""
        return K.run(self.data, self.rules)

    # ------------------------------------------------------------------ export as an Excel "list" (re-importable)
    def export_list(self, dest):
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Lessons"
        ws.append(["Day", "Period", "Class", "Subject", "Teacher", "Code", "Room"])
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F3A5F")
        name_of = {_u(c): n for c, n in self.teacher_names()}
        pname = lambda i: self.periods[i].get("time") or self.periods[i]["label"]
        rows = []
        for L in self.lessons:
            for d, p in self.slots(L):
                if p >= self.P:
                    continue
                if len(L["t"]) == 1:
                    teacher, code = name_of.get(_u(L["t"][0]), L["t"][0]), L["t"][0]
                else:
                    teacher, code = ", ".join(L["t"]), ""
                rows.append((d, p, [self.days[d], pname(p), ", ".join(L["c"]), L["s"], teacher, code,
                                    ", ".join(L["r"])]))
        for i, pr in enumerate(self.periods):                # keep the breaks, so the day has the same shape
            if pr.get("brk"):
                rows.append((0, i, [self.days[0], f"{pr['label'] or 'Break'} {pr.get('time', '')}".strip(), "", "", "", "", ""]))
        for _, _, r in sorted(rows, key=lambda x: (x[0], x[1])):
            ws.append(r)
        for col, w in zip("ABCDEFG", (12, 14, 18, 16, 24, 8, 14)):
            ws.column_dimensions[col].width = w
        wb.save(str(dest))
        return dest
