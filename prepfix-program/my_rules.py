"""
MY RULES - rules Cyrus writes in his own words, one per line, about students (classes), teachers and rooms
(labs & fields). PREPFIX reads each line, says how it understood it, and runs it over the timetable.
Nothing is blocked: whatever the result, the work goes on (moving, printing, publishing).

    run(sections, data) -> [result]      sections = {"students": text, "teachers": text, "rooms": text}
    result = {"section", "line", "ok": True | False | None, "understood": str, "problems": [str], "why": str}
             ok None = PREPFIX could not understand the line (why says what is missing)

What a line can say (any order, any words around it):
  WHO      a class (10A = 10 A, "grade 10", "form 4", "all classes", "students"), a teacher (name, surname,
           "teacher 6", "all teachers"), a room / lab / field (its name, "labs", "all rooms").
           Nobody named: everybody of that section (the Teachers box -> every teacher, ...).
  SUBJECT  e.g. Maths, English, Chemistry, P.E, or the short name used in the timetable (ENG, KISW ...).
  LIMIT    not more than / at most / maximum / no more than / less than / at least / minimum / exactly + a number,
           with: a day, a week, in a row (without a break), free periods (gaps) a day, days a week.
  TIME     days (Monday, Fri ...), morning / afternoon (before / after lunch), before / after a break,
           first / last lesson, L3 / period 3, before / after 4:00.  With "not", "no", "never", "free",
           "unavailable": nothing then.  With "only" (or no "not"): only then.
  "every day" alone: at least one a day.
"""
from __future__ import annotations

import re

import constraints as K
from notes_word import _class_rx, _surname_rx

NUMS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9,
        "TEN": 10, "ELEVEN": 11, "TWELVE": 12, "A SINGLE": 1, "SINGLE": 1}
NUM = r"(\d{1,3}|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE)"
DAYNAMES = {"MON": ["MON", "MONDAY", "MONDAYS"], "TUE": ["TUE", "TUES", "TUESDAY", "TUESDAYS"],
            "WED": ["WED", "WEDNESDAY", "WEDNESDAYS"], "THU": ["THU", "THUR", "THURS", "THURSDAY", "THURSDAYS"],
            "FRI": ["FRI", "FRIDAY", "FRIDAYS"], "SAT": ["SAT", "SATURDAY", "SATURDAYS"],
            "SUN": ["SUN", "SUNDAY", "SUNDAYS"]}
SUBJECT_WORDS = {
    "MATHEMATICS": ["MATH"], "MATHS": ["MATH"], "MATH": ["MATH"], "ENGLISH": ["ENG"], "KISWAHILI": ["KIS"],
    "SWAHILI": ["KIS"], "CHEMISTRY": ["CHEM"], "BIOLOGY": ["BIO"], "PHYSICS": ["PHY"], "GEOGRAPHY": ["GEO"],
    "HISTORY": ["HIST"], "BUSINESS": ["BST", "BUS"], "AGRICULTURE": ["AGR"], "COMPUTER": ["COMP", "ICT"],
    "COMPUTERS": ["COMP", "ICT"], "LITERATURE": ["LIT"], "FRENCH": ["FRE", "FRN"], "GERMAN": ["GER"],
    "MUSIC": ["MUS"], "ART": ["ART", "F.ART"], "PE": ["P.E", "PE"], "P.E": ["P.E", "PE"],
    "PHYSICAL EDUCATION": ["P.E", "PE"], "HOME SCIENCE": ["HSC"], "CRE": ["CRE"], "IRE": ["IRE"],
    "HRE": ["HRE"], "SPORTS": ["SPRT", "SPORT"], "PPI": ["PPI"], "LIFE SKILLS": ["L.S", "LS"],
    "CSL": ["CSL"], "ICT": ["ICT"], "SCIENCE": ["SCI"], "SCIENCES": ["SCI"],
}
NEG = r"\b(?:NOT|NO|NEVER|CANNOT|CAN'?T|SHOULDN'?T|MUSTN'?T|WON'?T|DON'?T|DOESN'?T|AVOID|FREE|OFF|UNAVAILABLE|ABSENT|AWAY|NONE)\b"
TITLES = r"(?:MR|MRS|MS|MISS|MADAM|MDM|TR|TCHR|SIR|DR)\.?"


def _u(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def _num(s) -> int:
    s = _u(s)
    return int(s) if s.isdigit() else NUMS.get(s, 0)


def _mins(t) -> int | None:
    m = re.match(r"\s*(\d{1,2})(?:[:.](\d{2}))?", str(t or ""))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h < 7:                                        # school hours: 2:20 = 14:20
        h += 12
    return h * 60 + mi


class _Model:
    def __init__(self, data, lessons=None):
        self.data = data
        self.days = [_u(d["label"]) for d in data["days"]]
        self.per = data["periods"]
        self.P = len(self.per)
        self.lessons = [dict(L) for L in lessons] if lessons is not None else K.lessons_of(data)
        # rooms: when the lessons do not carry them, take them from the labs & fields timetables
        at = {}
        for L in self.lessons:
            for s_ in self.slots(L):
                at.setdefault(s_, []).append(L)
        for r in data.get("rooms", []):
            for d, row in enumerate(r.get("grid") or []):
                for p_, c in enumerate(row):
                    if not isinstance(c, dict):
                        continue
                    cls = {_u(x) for x in re.split(r"[,;]", str(c.get("c", ""))) if x.strip()}
                    for L in at.get((d, p_), []):
                        if (not cls or cls & {_u(x) for x in L["c"]}) and r["name"] not in L["r"]:
                            L["r"] = list(L["r"]) + [r["name"]]
        self.teachers = [(t["code"], t.get("name") or "") for t in data.get("teachers", [])]
        self.classes = [c["name"] for c in data.get("classes", [])]
        self.rooms = [r["name"] for r in data.get("rooms", [])]
        self.teach = [p for p in range(self.P) if not self.per[p].get("brk")]
        brks = [p for p in range(self.P) if self.per[p].get("brk")]
        lunch = next((p for p in brks if "LUNCH" in _u(self.per[p]["label"])), None)
        if lunch is None and brks:
            lunch = brks[-1]
        self.lunch = lunch if lunch is not None else (self.teach[len(self.teach) // 2] if self.teach else 0)

    def tname(self, code):
        n = next((n for c, n in self.teachers if c == code), "")
        return n or f"teacher {code}"

    def when(self, d, p):
        pr = self.per[p]
        return f"{self.data['days'][d]['label']} {pr['label']}" + (f" ({pr['time']})" if pr.get("time") else "")

    def slots(self, L):
        return [(L["d"], L["p"] + k) for k in range(L.get("n", 1))]


# ------------------------------------------------------------------------------------------------ reading a line
def _find_people(M, s):
    """-> (classes, teachers, rooms, text with those names blanked, notes, unknown)"""
    notes, unknown = [], []
    masked = s

    def blank(a, b):
        nonlocal masked
        masked = masked[:a] + " " * (b - a) + masked[b:]
    # rooms first (a room name can hold a subject: "COMP LAB")
    rooms = []
    for r in sorted(M.rooms, key=len, reverse=True):
        words = re.findall(r"[A-Z0-9]+", _u(r))
        if not words:
            continue
        rx = re.compile(r"(?<![A-Z0-9])" + r"\W+".join(map(re.escape, words)) + r"(?![A-Z0-9])")
        for m in rx.finditer(masked):
            rooms.append(r)
            blank(m.start(), m.end())
    m = re.search(r"\b(?:ALL|EVERY|EACH|THE)?\s*(?:LABS|LABORATORIES|ROOMS|LABS AND FIELDS)\b", masked)
    if m and not rooms:
        labs = [r for r in M.rooms if "LAB" in _u(r)] if "LAB" in m.group(0) else list(M.rooms)
        rooms += labs or list(M.rooms)
        blank(m.start(), m.end())
    # teachers
    teachers = []
    for m in re.finditer(r"\b(?:TEACHER|TR|TCHR|CODE)\.?\s*(?:NO\.?|NUMBER)?\s*#?\s*([A-Z0-9]{1,6})\b", masked):
        code = next((c for c, _ in M.teachers if _u(c) == m.group(1)), None)
        if code:
            teachers.append(code)
            blank(m.start(), m.end())
    for c, _ in M.teachers:                          # a code written alone (not a plain number: that is a count)
        if not _u(c).isdigit() and len(c) >= 2:
            for m in re.finditer(r"(?<![A-Z0-9])" + re.escape(_u(c)) + r"(?![A-Z0-9])", masked):
                teachers.append(c)
                blank(m.start(), m.end())
    score = {}
    spans = {}
    for c, n in M.teachers:
        r = _surname_rx(n) if n else None
        if not r:
            continue
        hits = list(r[0].finditer(masked))
        if hits:
            score[c] = len({h.group(0).upper() for h in hits})
            spans[c] = [(h.start(), h.end()) for h in hits]
    if score:
        best = max(score.values())
        pick = [c for c, v in score.items() if v == best]
        if len(pick) > 1:
            notes.append(f"{len(pick)} teachers match ({', '.join(M.tname(c) for c in pick)}) — all of them are "
                         "checked; write the full name to choose one")
        for c in pick:
            teachers.append(c)
        for c in score:
            for a, b in spans[c]:
                blank(a, b)
    for m in re.finditer(r"\b" + TITLES + r" ([A-Z][A-Z'\-]{2,})", masked if not score else ""):   # "Mr Otieno": nobody
        unknown.append(f"there is no teacher called “{m.group(0).title()}” in this timetable")
    if re.search(r"\b(?:ALL|EVERY|EACH)\s+(?:THE\s+)?(?:TEACHERS?|STAFF|TUTORS?)\b", masked):
        teachers = [c for c, _ in M.teachers]
    # classes
    classes, hits = [], []
    for c in M.classes:
        rx = _class_rx(c)
        if rx:
            for m in rx.finditer(masked):
                hits.append((m.start(), m.end(), c))
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    last = -1
    for a, b, c in hits:
        if a >= last:
            classes.append(c)
            last = b
            blank(a, b)
    for m in re.finditer(r"\b(?:GRADE|FORM|GR|F)\.?\s*(\d{1,2})\b(?!\s*[A-Z]\b)", masked):
        g = [c for c in M.classes if re.findall(r"\d+", c)[:1] == [m.group(1)]]
        if g:
            classes += g
            blank(m.start(), m.end())
        else:
            unknown.append(f"there is no {m.group(0).title()} in this timetable")
    for m in re.finditer(r"(?<![A-Z0-9:.])(\d{1,2})\s?([A-Z])(?![A-Z0-9])", masked):   # "10c" - no such class
        if not re.match(r"\d{1,2}\s?(?:AM|PM|A|P)$", m.group(0)) and _u(m.group(0)) not in ("1ST", "2ND"):
            unknown.append(f"there is no class “{m.group(0)}” in this timetable")
    if re.search(r"\b(?:ALL|EVERY|EACH)\s+(?:THE\s+)?(?:CLASS(?:ES)?|STREAMS?|GRADES?|FORMS?)\b|\b(?:STUDENTS|LEARNERS|PUPILS)\b",
                 masked) and not classes:
        classes = list(M.classes)
    return (list(dict.fromkeys(classes)), list(dict.fromkeys(teachers)), list(dict.fromkeys(rooms)), masked,
            notes, unknown)


def _subjects_in_data(M):
    out = set()
    for L in M.lessons:
        for part in re.split(r"[/,]", _u(L["s"])):
            part = part.strip()
            if part:
                out.add(part)
    return out


def _find_subject(M, s):
    """-> (stems, label, masked) ; stems: a lesson matches if one of its subject words starts with a stem."""
    stems, names = [], []
    for word in sorted(SUBJECT_WORDS, key=len, reverse=True):
        rx = re.compile(r"(?<![A-Z0-9])" + re.escape(word).replace(r"\ ", r"\s+") + r"(?![A-Z0-9])")
        m = rx.search(s)
        if m:
            stems += SUBJECT_WORDS[word]
            names.append(word.title() if len(word) > 3 else word)
            s = s[:m.start()] + " " * (m.end() - m.start()) + s[m.end():]
    for part in sorted(_subjects_in_data(M), key=len, reverse=True):     # the short names used in the timetable
        if len(part) < 2:
            continue
        rx = re.compile(r"(?<![A-Z0-9])" + re.escape(part).replace(r"\ ", r"\s+") + r"(?![A-Z0-9])")
        m = rx.search(s)
        if m and part not in ("L", "S"):
            stems.append(part)
            names.append(part)
            s = s[:m.start()] + " " * (m.end() - m.start()) + s[m.end():]
    return list(dict.fromkeys(stems)), " / ".join(dict.fromkeys(names)), s


def _subject_ok(stems, subj):
    if not stems:
        return True
    words = [w for w in re.split(r"[/\s,]+", _u(subj)) if w]
    whole = _u(subj)
    for st in stems:
        st_ = st.replace(".", "")
        if whole == st or any(w == st or w.replace(".", "").startswith(st_) for w in words):
            return True
        if " " in st and st in whole:
            return True
    return False


def _find_time(M, s):
    """-> (set of (d, p) or None, label)"""
    days = []
    for key, names in DAYNAMES.items():
        if re.search(r"\b(?:" + "|".join(names) + r")\b", s):
            ix = next((i for i, d in enumerate(M.days) if d[:3] == key), None)
            if ix is not None:
                days.append(ix)
    parts, label = None, []

    def keep(ps, text):
        nonlocal parts
        parts = set(ps) if parts is None else parts & set(ps)
        label.append(text)
    if re.search(r"\bMORNINGS?\b|\bBEFORE LUNCH\b", s):
        keep(range(0, M.lunch), "in the morning (before lunch)")
    if re.search(r"\bAFTERNOONS?\b|\bAFTER LUNCH\b|\bEVENINGS?\b", s):
        keep(range(M.lunch + 1, M.P), "in the afternoon (after lunch)")
    for m in re.finditer(r"\b(BEFORE|AFTER)\s+(?:THE\s+)?((?:LONG|SHORT|TEA|FIRST|SECOND|GAMES|MORNING)?\s*BREAK)\b", s):
        word = m.group(2).split()[0] if len(m.group(2).split()) > 1 else ""
        brk = next((p for p in range(M.P) if M.per[p].get("brk") and (not word or word in _u(M.per[p]["label"]))), None)
        if brk is not None:
            keep(range(0, brk) if m.group(1) == "BEFORE" else range(brk + 1, M.P), f"{m.group(1).lower()} {M.per[brk]['label']}")
    for m in re.finditer(r"\b(BEFORE|AFTER|FROM|BY)\s+(\d{1,2}(?:[:.]\d{2})?)\s*(AM|PM|A\.M\.|P\.M\.)?", s):
        t = _mins(m.group(2))
        if m.group(3) and m.group(3).startswith("P") and t < 12 * 60:
            t += 12 * 60
        starts = {p: _mins((M.per[p].get("time") or "").split("-")[0]) for p in range(M.P)}
        if m.group(1) in ("BEFORE", "BY"):
            keep([p for p, st in starts.items() if st is not None and st < t], f"before {m.group(2)}")
        else:
            keep([p for p, st in starts.items() if st is not None and st >= t], f"from {m.group(2)}")
    if re.search(r"\bFIRST\s+(?:LESSON|PERIOD|CLASS)\b|\b(?:LESSON|PERIOD)\s+ONE\b", s) and M.teach:
        keep([M.teach[0]], "in the first lesson")
    if re.search(r"\bLAST\s+(?:LESSON|PERIOD|CLASS)\b", s) and M.teach:
        keep([M.teach[-1]], "in the last lesson")
    pl = []
    for m in re.finditer(r"\b(?:L|LESSON|PERIOD|P)\s*\.?\s*(\d{1,2})\b(?!\s*(?:LESSONS|PERIODS))", s):
        lab = f"L{m.group(1)}"
        p = next((i for i in range(M.P) if _u(M.per[i]["label"]).replace(" ", "") == lab), None)
        if p is None and int(m.group(1)) <= len(M.teach):
            p = M.teach[int(m.group(1)) - 1]
        if p is not None:
            pl.append(p)
    if pl:
        keep(pl, "in " + ", ".join(M.per[p]["label"] for p in pl))
    if not days and parts is None:
        return None, ""
    dset = days or list(range(len(M.days)))
    pset = parts if parts is not None else set(range(M.P))
    dl = ", ".join(M.data["days"][d]["label"] for d in days)
    return {(d, p) for d in dset for p in pset}, " ".join(x for x in ([("on " + dl) if days else ""] + label) if x)


def _find_limit(s):
    """-> (kind 'max'|'min'|'eq', n, unit 'day'|'week'|'row'|'gaps'|'days'|None) or None"""
    neg = bool(re.search(NEG, s))
    lim = None
    pats = [(r"\b(?:NOT|NO)\s+MORE\s+THAN\s+" + NUM, "max", 0), (r"\bAT\s+MOST\s+" + NUM, "max", 0),
            (r"\bMAX(?:IMUM|\.)?\s*(?:OF\s+)?" + NUM, "max", 0), (r"\bUP\s+TO\s+" + NUM, "max", 0),
            (r"\b(?:NOT\s+)?EXCEED(?:ING)?\s+" + NUM, "max", 0), (r"\bNOT\s+(?:OVER|ABOVE)\s+" + NUM, "max", 0),
            (r"\b" + NUM + r"\s+OR\s+(?:LESS|FEWER)\b", "max", 0), (r"\b(?:LESS|FEWER)\s+THAN\s+" + NUM, "max", -1),
            (r"\bBELOW\s+" + NUM, "max", -1),
            (r"\b(?:NOT|NO)\s+(?:LESS|FEWER)\s+THAN\s+" + NUM, "min", 0), (r"\bAT\s+LEAST\s+" + NUM, "min", 0),
            (r"\bMIN(?:IMUM|\.)?\s*(?:OF\s+)?" + NUM, "min", 0), (r"\b" + NUM + r"\s+OR\s+MORE\b", "min", 0),
            (r"\bEXACTLY\s+" + NUM, "eq", 0), (r"\bMORE\s+THAN\s+" + NUM, "more", 0)]
    for rx, kind, adj in pats:
        m = re.search(rx, s)
        if m:
            n = _num(m.group(1))
            if kind == "max" and adj == -1 and re.search(r"\b(?:NOT|NO)\s+(?:LESS|FEWER)\s+THAN", s):
                continue
            if kind == "more":
                kind, n = ("max", n) if neg else ("min", n + 1)
            lim = [kind, n + adj, m.end()]
            break
    if lim is None:
        m = re.search(r"\b(?:ONLY|JUST)\s+" + NUM + r"\b", s)
        if m:
            lim = ["max", _num(m.group(1)), m.end()]
    if lim is None:
        m = re.search(r"\b" + NUM + r"\s+(?:LESSONS?|PERIODS?|DAYS?|FREE|GAPS?)\b", s)
        if m and re.search(r"\b(?:SHOULD|MUST|HAVE|HAS|TEACH|GET)\b", s):
            lim = ["eq", _num(m.group(1)), m.end()]
    if lim is None:
        return None
    unit = None
    if re.search(r"\bIN\s+A\s+ROW\b|\bCONSECUTIVE(?:LY)?\b|\bCONTINUOUS(?:LY)?\b|\bSTRAIGHT\b|\bBACK\s*TO\s*BACK\b|"
                 r"\bWITHOUT\s+(?:A\s+)?BREAK\b|\bNON[\s-]?STOP\b", s):
        unit = "row"
    elif re.search(r"\bFREE\s+(?:PERIODS?|LESSONS?)\b|\bGAPS?\b|\bIDLE\b", s):
        unit = "gaps"
    elif re.search(NUM + r"\s+(?:WORKING\s+)?DAYS?\b", s) and re.search(r"\bWEEK\b", s):
        unit = "days"
    elif re.search(r"\b(?:A|PER|EACH|EVERY|IN\s+A|ANY|ONE|A\s+SINGLE|THE\s+SAME)\s+DAY\b|\bDAILY\b", s):
        unit = "day"
    elif re.search(r"\b(?:A|PER|EACH|EVERY|IN\s+A|IN\s+THE|THE)\s+WEEK\b|\bWEEKLY\b", s):
        unit = "week"
    return lim[0], max(0, lim[1]), unit


# ------------------------------------------------------------------------------------------------ one line
def check_line(M, line, section):
    raw = line.strip()
    s = _u(raw).replace("’", "'")
    res = {"section": section, "line": raw, "ok": None, "understood": "", "problems": [], "why": ""}
    classes, teachers, rooms, masked, notes, unknown = _find_people(M, s)
    stems, subj, masked = _find_subject(M, masked)
    if unknown and not (classes or teachers or rooms):
        res["why"] = unknown[0]
        return res
    # who is counted
    if teachers:
        by, who = "t", teachers
    elif classes:
        by, who = "c", classes
    elif rooms:
        by, who = "r", rooms
    else:
        by = {"students": "c", "teachers": "t", "rooms": "r"}[section]
        who = {"c": M.classes, "t": [c for c, _ in M.teachers], "r": M.rooms}[by]
    wset = {_u(x) for x in who}
    cset = {_u(x) for x in classes}
    tset = {_u(x) for x in teachers}
    rset = {_u(x) for x in rooms}

    def mine(L):
        if teachers and not tset & {_u(x) for x in L["t"]}:
            return False
        if classes and not cset & {_u(x) for x in L["c"]}:
            return False
        if rooms and not rset & {_u(x) for x in L["r"]}:
            return False
        return _subject_ok(stems, L["s"])
    Ls = [L for L in M.lessons if mine(L)]
    owners = lambda L: [x for x in L[by] if _u(x) in wset]
    show = (lambda x: M.tname(x)) if by == "t" else (lambda x: x)
    times, tlabel = _find_time(M, masked)
    lim = _find_limit(masked)
    neg = bool(re.search(NEG, masked))
    only = bool(re.search(r"\bONLY\b", masked)) and not (lim and lim[0] == "max" and re.search(r"\bONLY\s+" + NUM, masked))
    every_day = bool(re.search(r"\bEVERY\s*DAY\b|\bDAILY\b|\bEACH\s+DAY\b", masked))
    allw = {"c": "every class", "t": "every teacher", "r": "every room"}[by]
    whotxt = (allw if len(who) == len({"c": M.classes, "t": M.teachers, "r": M.rooms}[by]) and len(who) > 3
              else ", ".join(show(x) for x in who[:6]) + (f" (+{len(who) - 6})" if len(who) > 6 else ""))
    extra = []
    if teachers and by != "t":
        extra.append("with " + ", ".join(M.tname(t) for t in teachers))
    if classes and by != "c":
        extra.append("with " + ", ".join(classes))
    if rooms and by != "r":
        extra.append("in " + ", ".join(rooms))
    head = whotxt + (" · " + subj if subj else "") + (" · " + " ".join(extra) if extra else "")
    probs, offs = [], []
    ix = {id(L): i for i, L in enumerate(M.lessons)}

    def add(msg, les=(), ex=1):
        probs.append(msg)
        offs.append((msg, sorted({ix[id(L)] for L in les if id(L) in ix}), max(1, ex)))
    what = "lessons" if not subj else f"{subj} lessons"
    if lim:
        kind, n, unit = lim
        if unit is None:
            unit = "day" if (times or by == "t") else "week"
        word = {"max": "at most", "min": "at least", "eq": "exactly"}[kind]
        bad = (lambda v: v > n) if kind == "max" else (lambda v: v < n) if kind == "min" else (lambda v: v != n)
        inside = (lambda d, p: (d, p) in times) if times else (lambda d, p: True)
        ndays = len(M.days)
        if unit in ("day", "week"):
            cnt, who_les = {}, {}
            for L in Ls:
                for w in owners(L):
                    for d, p in M.slots(L):
                        if inside(d, p):
                            k = (w, d) if unit == "day" else (w,)
                            cnt[k] = cnt.get(k, 0) + 1
                            who_les.setdefault(k, []).append(L)
            for w in who:
                rng = [(w, d) for d in range(ndays)] if unit == "day" else [(w,)]
                if unit == "day" and times:
                    rng = [(w, d) for d in sorted({d for d, _ in times})]
                for k in rng:
                    v = cnt.get(k, 0)
                    if bad(v):
                        add(f"{show(w)} has {v} {what}" + (f" on {M.data['days'][k[1]]['label']}" if unit == "day" else " in the week")
                            + (f" {tlabel}" if tlabel else "") + f" (wanted {word} {n})",
                            who_les.get(k) or [L for L in Ls if w in owners(L)], abs(v - n))
            res["understood"] = f"{head} — {word} {n} {what} a {unit}" + (f" {tlabel}" if tlabel else "") + \
                                " (a double counts as 2)"
        elif unit == "row":
            for w in who:
                for d in range(ndays):
                    busy = sorted({p for L in Ls if w in owners(L) for dd, p in M.slots(L) if dd == d and inside(dd, p)})
                    run, best, end = 0, 0, None
                    for i, p in enumerate(busy):
                        run = run + 1 if i and p == busy[i - 1] + 1 else 1
                        if run > best:
                            best, end = run, p
                    if (kind == "max" and best > n) or (kind == "eq" and best and best != n):
                        add(f"{show(w)} has {best} {what} in a row on {M.data['days'][d]['label']} "
                            f"(ending {M.per[end]['label']}; wanted {word} {n})",
                            [L for L in Ls if w in owners(L) and any(dd == d for dd, _ in M.slots(L))], abs(best - n))
            res["understood"] = f"{head} — {word} {n} {what} in a row (a break ends the row)"
        elif unit == "gaps":
            for w in who:
                for d in range(ndays):
                    busy = {p for L in M.lessons if w in owners(L) for dd, p in M.slots(L) if dd == d}
                    if not busy:
                        continue
                    gaps = [p for p in range(min(busy), max(busy) + 1) if p not in busy and not M.per[p].get("brk")]
                    if bad(len(gaps)):
                        add(f"{show(w)} has {len(gaps)} free period(s) between lessons on "
                            f"{M.data['days'][d]['label']} (wanted {word} {n})",
                            [L for L in M.lessons if w in owners(L) and L["d"] == d], abs(len(gaps) - n))
            res["understood"] = f"{head} — {word} {n} free period(s) between lessons a day"
        elif unit == "days":
            for w in who:
                v = len({d for L in Ls if w in owners(L) for d, p in M.slots(L) if inside(d, p)})
                if bad(v):
                    add(f"{show(w)} has {what} on {v} day(s) a week (wanted {word} {n})",
                        [L for L in Ls if w in owners(L)], abs(v - n))
            res["understood"] = f"{head} — {what} on {word} {n} day(s) a week" + (f" {tlabel}" if tlabel else "")
    elif times:
        if neg and not only:
            for L in Ls:
                hit = [(d, p) for d, p in M.slots(L) if (d, p) in times]
                if hit:
                    for w in owners(L) or ["-"]:
                        add(f"{show(w) if w != '-' else ', '.join(L['c'])}: {L['s'] or 'lesson'} "
                            f"({', '.join(L['c'])}) at {M.when(*hit[0])}", [L])
            res["understood"] = f"{head} — no {what} {tlabel}"
        else:
            for L in Ls:
                out = [(d, p) for d, p in M.slots(L) if (d, p) not in times]
                if out:
                    for w in owners(L) or ["-"]:
                        add(f"{show(w) if w != '-' else ', '.join(L['c'])}: {L['s'] or 'lesson'} "
                            f"({', '.join(L['c'])}) at {M.when(*out[0])}", [L])
            res["understood"] = f"{head} — {what} only {tlabel}"
    elif every_day and not neg:
        for w in who:
            have = {d for L in Ls if w in owners(L) for d, p in M.slots(L)}
            for d in range(len(M.days)):
                if d not in have:
                    add(f"{show(w)} has no {what} on {M.data['days'][d]['label']}", [L for L in Ls if w in owners(L)])
        res["understood"] = f"{head} — at least 1 of these {what} every day"
    else:
        res["why"] = ("PREPFIX could not tell what to check: give a number (e.g. “not more than …”, “at least …”) "
                      "or a time (a day, morning / afternoon, a lesson, before / after …).")
        if unknown:
            res["why"] = unknown[0] + ". " + res["why"]
        return res
    if not Ls and (subj or classes or teachers or rooms) and not (lim and lim[0] == "min"):
        notes.append("no lessons in the timetable match this")
    probs = list(dict.fromkeys(probs))
    seen_o, res["off"] = set(), []
    for o in offs:
        if o[0] not in seen_o:
            seen_o.add(o[0])
            res["off"].append(o)
    res["problems"] = probs
    res["ok"] = not probs
    if notes or unknown:
        res["understood"] += "   [" + "; ".join(notes + unknown) + "]"
    return res


def lines_of(sections):
    for sec in ("students", "teachers", "rooms"):
        for line in str((sections or {}).get(sec) or "").splitlines():
            if line.strip() and not line.strip().startswith("#"):
                yield sec, line.strip(" -•\t")


def run(sections, data):
    M = _Model(data)
    out = []
    for sec, line in lines_of(sections):
        try:
            out.append(check_line(M, line, sec))
        except Exception as e:                       # one odd line must never stop the others
            out.append({"section": sec, "line": line, "ok": None, "understood": "", "problems": [],
                        "why": f"PREPFIX could not read this line ({e})."})
    return out


def summary(results):
    ok = sum(1 for r in results if r["ok"] is True)
    bad = sum(1 for r in results if r["ok"] is False)
    unk = sum(1 for r in results if r["ok"] is None)
    return (f"{len(results)} rule(s): {ok} kept ✔, {bad} not kept ✖"
            + (f", {unk} not understood ?" if unk else "") + ". You can continue either way.")


def report_text(results, school=""):
    out = [f"MY RULES — {school}".strip(" —"), summary(results), ""]
    for i, r in enumerate(results, 1):
        mark = {True: "✔", False: "✖", None: "?"}[r["ok"]]
        out.append(f"{i}. {mark} [{r['section']}] {r['line']}")
        if r["understood"]:
            out.append(f"     Understood as: {r['understood']}")
        if r["why"]:
            out.append(f"     {r['why']}")
        for p in r["problems"]:
            out.append(f"     – {p}")
        out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ "observe" my rules
# A rule written in my own words can also be OBSERVED: moves never break it, ★ shows the best places for it and
# "Streamline" moves lessons to keep it. It is a rule like the others (type "my_rule").
SECTION_OF = {"c": "students", "t": "teachers", "r": "rooms"}


def _offences(ctx, r):
    try:
        M = _Model(ctx.data, ctx.lessons)
        res = check_line(M, r.get("text", ""), r.get("section", "students"))
    except Exception:
        return []
    return res.get("off", []) if res.get("ok") is False else []


def as_rules(sections, observe=True) -> list:
    """My rules (only the lines PREPFIX understands) as rules that moves / Streamline keep."""
    return [{"type": "my_rule", "text": line, "section": sec, "severity": K.ERR, "enabled": True, "src": "MY"}
            for sec, line in lines_of(sections)] if observe else []


def _register():
    import rules_more as RM
    RM.OFFENCES["my_rule"] = _offences
    K.TYPES["my_rule"] = dict(label="My rule (in my own words)", fields=[("text", "Rule", "text")],
                              check=lambda ctx, r: [m for m, _, _ in _offences(ctx, r)],
                              text=lambda r: f"My rule: {r.get('text', '')}")


_register()
