"""
RULES IN OPERATION - read straight from FET (the .fet file FET saves with every timetable it makes, e.g.
KIANDERI_data_and_timetable.fet), or from text pasted from it. These are the rules the timetable was made with;
PREPFIX keeps them on every move (a rule FET had at 100 % is mandatory: a move that would break it is refused).

    read_folder(folder, data)  -> (data with FET activity ids / tags in the cells, rules, report lines)
    read_text(text, data)      -> the same, from pasted .fet text (XML)

Rule types (checked in rules_more.py) with "src": "FET":
    break_lessons, teacher_max_day, teacher_max_consec, not_available (teacher / class / room), teacher_min_days,
    interval_max_days, max_gaps_day, tag_max_daily, tag_min_gaps, tags_not_overlap, min_days_between,
    allowed_slots, occupy_slots
FET's "activity preferred starting time" entries in a *_data_and_timetable.fet are the timetable itself (FET
writes one for every activity), not rules - they are only used to find each lesson's FET activity.
"""
from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import constraints as K


def _n(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()


def find_fet(folder):
    f = Path(folder)
    if f.is_file() and f.suffix.lower() == ".fet":
        return f
    if not f.is_dir():
        return None
    hits = sorted(f.glob("*_data_and_timetable.fet")) or sorted(f.glob("*.fet"))
    return hits[0] if hits else None


def read_folder(folder, data):
    p = find_fet(folder)
    if not p:
        return data, [], ["No FET .fet file in this folder - rules in operation can be pasted instead."]
    return read_text(p.read_text("utf-8", errors="replace"), data, source=p.name)


def read_text(text, data, source="pasted text"):
    text = text.lstrip("\ufeff").strip()
    if not text.startswith("<"):
        raise ValueError("Paste the contents of the FET .fet file (it starts with “<?xml” or “<fet”). Open the .fet "
                         "file with Notepad, press Ctrl+A, Ctrl+C, then paste here.")
    if "<fet" not in text[:400] and "<Time_Constraints_List" not in text:
        text = "<fet>" + text + "</fet>"
    text = re.sub(r"^<\?xml[^>]*\?>", "", text).strip()
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as e:
        raise ValueError(f"That is not complete FET text ({e}). Copy the whole .fet file.")
    return _read(root, data, source)


def _read(root, data, source):
    data = copy.deepcopy(data)
    report = []
    days = [_n(x["label"]) for x in data["days"]]
    hours = [_n(x["label"]) for x in data["periods"]]
    fdays = [_n(d.findtext("Name")) for d in root.find("Days_List").findall("Day")] if root.find("Days_List") is not None else []
    fhours = [_n(h.findtext("Name")) for h in root.find("Hours_List").findall("Hour")] if root.find("Hours_List") is not None else []

    def day_ix(name):
        n = _n(name)
        if n in days:
            return days.index(n)
        if n in fdays and len(fdays) == len(days):
            return fdays.index(n)
        return next((i for i, d in enumerate(days) if d[:3] == n[:3]), None)

    def hour_ix(name):
        n = _n(name)
        if n in hours:
            return hours.index(n)
        if n in fhours and len(fhours) == len(hours):
            return fhours.index(n)
        return None

    def slot(el, dtag="Day", htag="Hour"):
        d, h = day_ix(el.findtext(dtag)), hour_ix(el.findtext(htag))
        return None if d is None or h is None else f"{data['days'][d]['label']} {data['periods'][h]['label']}"

    def slots_of(el, tag):
        out = []
        for s in el.findall(tag):
            x = slot(s)
            if x:
                out.append(x)
        return ", ".join(out)

    # ---- activities: who / what / tags, and where FET placed them (to label each lesson in the grids)
    acts = {}
    al = root.find("Activities_List")
    for a in (al.findall("Activity") if al is not None else []):
        if (a.findtext("Active") or "true").strip().lower() != "true":
            continue
        aid = (a.findtext("Id") or "").strip()
        acts[aid] = {"t": [x.text.strip() for x in a.findall("Teacher") if x.text],
                     "st": [x.text.strip() for x in a.findall("Students") if x.text],
                     "s": (a.findtext("Subject") or "").strip(),
                     "tg": [x.text.strip() for x in a.findall("Activity_Tag") if x.text and x.text.strip()],
                     "n": int(a.findtext("Duration") or 1)}
    tl = root.find("Time_Constraints_List")
    placed = {}
    for c in (tl.findall("ConstraintActivityPreferredStartingTime") if tl is not None else []):
        aid = (c.findtext("Activity_Id") or "").strip()
        d, h = day_ix(c.findtext("Day")), hour_ix(c.findtext("Hour"))
        if aid in acts and d is not None and h is not None:
            placed[aid] = (d, h)
    classes = [c["name"] for c in data.get("classes", [])]

    def classes_of(st):
        out = []
        for s in st:
            if _n(s) in map(_n, classes):
                out.append(next(c for c in classes if _n(c) == _n(s)))
            else:                                         # a year or a group: its classes
                out += [c for c in classes if _n(c).startswith(_n(s) + " ") or _n(s).startswith(_n(c) + " ")]
        return out
    labelled = 0
    tg_of = lambda a: "|".join(a["tg"])
    for aid, (d, h) in placed.items():
        a = acts[aid]
        hit = False
        for code in a["t"]:
            g = next((x for x in data.get("teachers", []) if _n(x["code"]) == _n(code)), None)
            if g and isinstance(g["grid"][d][h], dict):
                g["grid"][d][h]["fa"] = aid
                if a["tg"]:
                    g["grid"][d][h]["tg"] = tg_of(a)
                hit = True
        for key in ("classes", "master"):
            for cl in classes_of(a["st"]):
                g = next((x for x in data.get(key, []) if _n(x["name"]) == _n(cl)), None)
                if g and h < len(g["grid"][d]) and isinstance(g["grid"][d][h], dict):
                    g["grid"][d][h].setdefault("fa", aid)
                    if a["tg"]:
                        g["grid"][d][h].setdefault("tg", tg_of(a))
                    hit = True
        labelled += hit
    data["_fet_acts"] = {aid: {"tg": a["tg"], "s": a["s"]} for aid, a in acts.items()}

    # ---- the rules
    rules, skipped = [], {}

    def add(typ, c, **kw):
        w = float((c.findtext("Weight_Percentage") or "100").strip() or 100)
        r = K.new_rule(typ, severity=K.ERR if w >= 100 else K.WARN, src="FET", fet=c.tag.replace("Constraint", ""),
                       weight=w, **kw)
        rules.append(r)

    for lst in ("Time_Constraints_List", "Space_Constraints_List"):
        L = root.find(lst)
        for c in (L if L is not None else []):
            if (c.findtext("Active") or "true").strip().lower() != "true":
                continue
            tag = c.tag
            if tag in ("ConstraintBasicCompulsoryTime", "ConstraintBasicCompulsorySpace", "ConstraintActivityPreferredStartingTime"):
                continue
            if tag == "ConstraintBreakTimes":
                add("break_lessons", c)
            elif tag == "ConstraintTeacherMaxHoursDaily":
                add("teacher_max_day", c, teacher=c.findtext("Teacher"), max=int(c.findtext("Maximum_Hours_Daily")))
            elif tag == "ConstraintTeachersMaxHoursDaily":
                add("teacher_max_day", c, teacher="*", max=int(c.findtext("Maximum_Hours_Daily")))
            elif tag == "ConstraintTeacherMaxHoursContinuously":
                add("teacher_max_consec", c, teacher=c.findtext("Teacher"), max=int(c.findtext("Maximum_Hours_Continuously")))
            elif tag == "ConstraintTeachersMaxHoursContinuously":
                add("teacher_max_consec", c, teacher="*", max=int(c.findtext("Maximum_Hours_Continuously")))
            elif tag == "ConstraintTeacherNotAvailableTimes":
                add("not_available", c, who="teacher", name=c.findtext("Teacher"), slots=slots_of(c, "Not_Available_Time"))
            elif tag == "ConstraintStudentsSetNotAvailableTimes":
                for cl in classes_of([c.findtext("Students")]) or [c.findtext("Students")]:
                    add("not_available", c, who="class", name=cl, slots=slots_of(c, "Not_Available_Time"))
            elif tag == "ConstraintRoomNotAvailableTimes":
                add("not_available", c, who="room", name=c.findtext("Room"), slots=slots_of(c, "Not_Available_Time"))
            elif tag == "ConstraintTeacherMinDaysPerWeek":
                add("teacher_min_days", c, teacher=c.findtext("Teacher"), min=int(c.findtext("Minimum_Days_Per_Week")))
            elif tag == "ConstraintTeachersMinDaysPerWeek":
                add("teacher_min_days", c, teacher="*", min=int(c.findtext("Minimum_Days_Per_Week")))
            elif tag in ("ConstraintTeachersIntervalMaxDaysPerWeek", "ConstraintTeacherIntervalMaxDaysPerWeek"):
                add("interval_max_days", c, teacher=c.findtext("Teacher") or "*", start=c.findtext("Interval_Start_Hour") or "",
                    end=c.findtext("Interval_End_Hour") or "", max=int(c.findtext("Max_Days_Per_Week")))
            elif tag in ("ConstraintTeachersMaxGapsPerDay", "ConstraintTeacherMaxGapsPerDay"):
                add("max_gaps_day", c, teacher=c.findtext("Teacher") or "*", max=int(c.findtext("Max_Gaps")))
            elif tag == "ConstraintStudentsActivityTagMaxHoursDaily":
                add("tag_max_daily", c, tag=c.findtext("Activity_Tag"), max=int(c.findtext("Maximum_Hours_Daily")))
            elif tag == "ConstraintStudentsMinGapsBetweenOrderedPairOfActivityTags":
                add("tag_min_gaps", c, tag=c.findtext("First_Activity_Tag"), tag2=c.findtext("Second_Activity_Tag"),
                    min=int(c.findtext("MinGaps")))
            elif tag == "ConstraintActivityTagsNotOverlapping":
                add("tags_not_overlap", c, tags="|".join(x.text for x in c.findall("Activity_Tag") if x.text))
            elif tag == "ConstraintMinDaysBetweenActivities":
                add("min_days_between", c, ids=",".join(x.text for x in c.findall("Activity_Id") if x.text),
                    min=int(c.findtext("MinDays") or 1))
            elif tag in ("ConstraintActivitiesPreferredTimeSlots", "ConstraintSubactivitiesPreferredTimeSlots"):
                add("allowed_slots", c, teacher=c.findtext("Teacher") or "", students=c.findtext("Students") or "",
                    subject=c.findtext("Subject") or "", tag=c.findtext("Activity_Tag") or "",
                    slots=slots_of(c, "Preferred_Time_Slot"))
            elif tag in ("ConstraintActivitiesOccupyMaxTimeSlotsFromSelection", "ConstraintActivitiesOccupyMinTimeSlotsFromSelection"):
                kind = "max" if "Max" in tag else "min"
                add("occupy_slots", c, ids=",".join(x.text for x in c.findall("Activity_Id") if x.text),
                    slots=slots_of(c, "Selected_Time_Slot"), mode=kind,
                    count=int(c.findtext("Max_Number_of_Occupied_Time_Slots") or c.findtext("Min_Number_of_Occupied_Time_Slots") or 0))
            else:
                skipped[tag.replace("Constraint", "")] = skipped.get(tag.replace("Constraint", ""), 0) + 1
    must = sum(1 for r in rules if r["severity"] == K.ERR)
    report.append(f"Rules in operation read from {source}: {len(rules)} ({must} at 100 % = must never be broken, "
                  f"{len(rules) - must} preferred). {labelled} lessons matched to their FET activities.")
    if skipped:
        report.append("Not used by PREPFIX (kept as they are, not checked): " +
                      ", ".join(f"{k} ×{v}" for k, v in sorted(skipped.items())))
    return data, rules, report
