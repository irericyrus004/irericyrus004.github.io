"""The "Teacher change" window (Path B, step 5): a teacher leaves - give the lessons to another teacher.

Only the lessons handed over change. A lesson that fits the receiving teacher at the same time is simply handed
over. One that clashes is listed with the reason; "Find a place" shows where it can go (free for the receiving
teacher, the class, the lab and any co-teachers, and no must-pass rule broken) and moves it there."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import constraints as K
import prepfix_ui as U
import transfer as TR


class TeacherChange:
    def __init__(self, app):
        self.app = app
        self.orig = app.data
        self.work = app.data
        self.rules = app.current_rules()             # no clashes, no lessons in breaks (nothing else)
        self.done = []                              # texts of what was handed over / moved
        self.done_rows = []                         # (when, class, subject, text) shown at the top of the list
        self.added = []                             # new teachers made here
        w = self.win = tk.Toplevel(app.root)
        w.title("PREPFIX — Teacher change")
        w.geometry("1180x720")
        w.configure(bg=U.CREAM)
        w.transient(app.root)
        try:
            w.state("zoomed")
        except tk.TclError:
            pass
        try:
            w.attributes("-topmost", True)
            w.after(400, lambda: w.attributes("-topmost", False))
        except tk.TclError:
            pass
        top = ttk.Frame(w, style="Card.TFrame", padding=14)
        top.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(top, text="👥  Teacher change — a teacher leaves, another takes the lessons", style="Big.TLabel").pack(anchor="w")
        ttk.Label(top, style="CardMuted.TLabel", wraplength=1100, justify="left", text=(
            "Only the lessons you hand over change — every other teacher and class stays exactly as it is. A lesson that "
            "fits the receiving teacher at the same time is handed over at once. One that clashes shows why; "
            "“📍 Find a place” lists where it can go (no clashes, no breaks) and moves it there. In a group lesson the other "
            "teachers stay; only the leaving teacher is replaced.")).pack(anchor="w", pady=(4, 8))
        r1 = ttk.Frame(top, style="Card.TFrame")
        r1.pack(fill="x")
        ttk.Label(r1, text="Teacher leaving:", style="H.TLabel").pack(side="left")
        self.donor_var = tk.StringVar()
        self.donor_box = ttk.Combobox(r1, textvariable=self.donor_var, state="readonly", width=34)
        self.donor_box.pack(side="left", padx=(6, 18))
        self.donor_box.bind("<<ComboboxSelected>>", lambda e: self.fill())
        ttk.Label(r1, text="Give the lessons to:", style="H.TLabel").pack(side="left")
        self.rec_var = tk.StringVar()
        self.rec_box = ttk.Combobox(r1, textvariable=self.rec_var, state="readonly", width=34)
        self.rec_box.pack(side="left", padx=6)
        self.rec_box.bind("<<ComboboxSelected>>", lambda e: self.fill())
        ttk.Button(r1, text="➕  New teacher…", command=self.new_teacher).pack(side="left", padx=4)

        mid = ttk.Frame(w, style="Card.TFrame", padding=(14, 8))
        mid.pack(fill="both", expand=True, padx=10, pady=8)
        cols = ("when", "class", "subject", "teachers", "status")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        for c, txt, wd in (("when", "When", 110), ("class", "Class", 90), ("subject", "Subject", 190),
                           ("teachers", "Teachers of the lesson", 190), ("status", "With the receiving teacher", 560)):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=wd, anchor="w", stretch=(c == "status"))
        sb = ttk.Scrollbar(mid, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.tag_configure("ok", foreground=U.GREEN)
        self.tree.tag_configure("bad", foreground=U.RED)
        self.tree.tag_configure("done", foreground="#5B6B85", background="#EEF6F0")
        self.tree.bind("<Double-1>", lambda e: self.find_place())

        bar = ttk.Frame(w, style="Card.TFrame", padding=(14, 8))
        bar.pack(fill="x", padx=10)
        ttk.Button(bar, text="✔  Hand over ALL that fit", style="Accent.TButton", command=lambda: self.hand(all_=True)).pack(side="left")
        ttk.Button(bar, text="Hand over selected", command=lambda: self.hand(all_=False)).pack(side="left", padx=6)
        ttk.Button(bar, text="📍  Find a place (selected clash)", style="Gold.TButton", command=self.find_place).pack(side="left", padx=6)
        ttk.Button(bar, text="↶  Start again", command=self.reset).pack(side="left", padx=6)
        self.remove_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Remove the leaving teacher when all lessons are handed over",
                        variable=self.remove_var).pack(side="right")

        bot = ttk.Frame(w, style="Card.TFrame", padding=(14, 10))
        bot.pack(fill="x", padx=10, pady=(8, 10))
        self.info = ttk.Label(bot, text="", style="Card.TLabel", wraplength=860, justify="left")
        self.info.pack(side="left", fill="x", expand=True)
        ttk.Button(bot, text="Cancel", command=w.destroy).pack(side="right")
        ttk.Button(bot, text="✔  Use these changes", style="Accent.TButton", command=self.finish).pack(side="right", padx=8)
        self.load_names()
        self.fill()

    # ------------------------------------------------------------------ names
    def tlabels(self):
        return [TR.label(self.work, t["code"]) for t in self.work.get("teachers", [])]

    def code_of(self, lab):
        return lab.split(" · ")[0].strip() if lab else ""

    def load_names(self):
        labs = self.tlabels()
        self.donor_box.configure(values=labs)
        self.rec_box.configure(values=labs)
        if not self.donor_var.get() and labs:
            self.donor_var.set(labs[0])

    def new_teacher(self):
        name = simpledialog.askstring("New teacher", "Name of the new teacher (as it should appear on the timetables):",
                                      parent=self.win)
        if not name:
            return
        try:
            self.work, code = TR.add_teacher(self.work, name)
        except ValueError as e:
            messagebox.showinfo("New teacher", str(e), parent=self.win)
            return
        self.added.append(code)
        self.load_names()
        self.rec_var.set(TR.label(self.work, code))
        self.fill()

    # ------------------------------------------------------------------ the list
    def when(self, L):
        d, p = L["d"], L["p"]
        P = self.work["periods"]
        lab = P[p]["label"] + (f"–{P[p + L.get('n', 1) - 1]['label']}" if L.get("n", 1) > 1 else "")
        return f"{self.work['days'][d]['label']} {lab}"

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        donor, rec = self.code_of(self.donor_var.get()), self.code_of(self.rec_var.get())
        self.rows = []
        for i, (wh, cl, su, txt) in enumerate(self.done_rows):
            self.tree.insert("", "end", iid=f"done{i}", values=(wh, cl, su, "handed over", "✔ " + txt), tags=("done",))
        if not donor:
            return
        base = None
        for L in TR.lessons_of_teacher(self.work, donor):
            if rec and rec != donor:
                ok, why = TR.fits(self.work, L, donor, rec)
                if ok:
                    if base is None:
                        base = {(i["sev"], i["msg"]) for i in K.run(self.work, self.rules)["issues"]}
                    new = [m for s, m in {(i["sev"], i["msg"]) for i in K.run(TR.hand_over(self.work, L, donor, rec),
                                                                                self.rules)["issues"]} - base if s == K.ERR]
                    if new:
                        ok, why = False, "same time, but: " + new[0]
                status = "✔ fits at the same time" if ok else "✖ " + why + "  → Find a place"
                tag = "ok" if ok else "bad"
            else:
                status, tag = "choose who gets the lessons", ""
            iid = f"r{len(self.rows)}"
            self.rows.append(L)
            self.tree.insert("", "end", iid=iid, tags=(tag,), values=(
                self.when(L), ", ".join(L["c"]), L["s"] + (" (double)" if L.get("n", 1) == 2 else " (triple)" if L.get("n", 1) == 3 else ""),
                ", ".join(TR.label(self.work, t).split(" · ")[-1] + (" ← leaving" if t == donor else "") for t in L["t"]),
                status))
        self.update_info()

    def update_info(self):
        donor = self.code_of(self.donor_var.get())
        left = len(TR.lessons_of_teacher(self.work, donor)) if donor else 0
        aff = TR.affected(self.orig, self.work)
        try:
            rep = K.run(self.work, self.rules)
            rl = ("✔ no clashes" if not rep["errors"] else f"✖ {rep['errors']} clash(es)")
        except Exception:
            rl = ""
        self.info.configure(text=(f"{len(self.done)} lesson(s) handed over · {left} still with the leaving teacher · "
                                  f"changed: {len(aff['teachers'])} teacher(s) {', '.join(aff['teachers'][:6])}"
                                  f"{'…' if len(aff['teachers']) > 6 else ''} and {len(aff['classes'])} class(es) "
                                  f"{', '.join(aff['classes'][:8])} — nobody else.   Rules: {rl}"))

    def picked(self):
        return [self.rows[int(i[1:])] for i in self.tree.selection() if i.startswith("r")]

    # ------------------------------------------------------------------ actions
    def need(self):
        donor, rec = self.code_of(self.donor_var.get()), self.code_of(self.rec_var.get())
        if not donor or not rec:
            messagebox.showinfo("Teacher change", "Choose the teacher leaving and who gets the lessons "
                                                  "(or ➕ New teacher).", parent=self.win)
            return None
        if donor == rec:
            messagebox.showinfo("Teacher change", "Choose a different teacher to receive the lessons.", parent=self.win)
            return None
        return donor, rec

    def hand(self, all_=False):
        dr = self.need()
        if not dr:
            return
        donor, rec = dr
        todo = list(self.rows) if all_ else self.picked()
        if not todo:
            messagebox.showinfo("Teacher change", "Select the lessons in the list first.", parent=self.win)
            return
        n, skipped = 0, 0
        for L in todo:
            ok, why = TR.fits(self.work, L, donor, rec)
            if not ok:
                skipped += 1
                continue
            new = TR.hand_over(self.work, L, donor, rec)
            if K.run(new, self.rules)["errors"] > K.run(self.work, self.rules)["errors"]:
                skipped += 1                       # it would break a must-pass rule: leave it for "Find a place"
                continue
            self.work = new
            txt = (f"{TR.label(self.work, donor).split(' · ')[-1]} → {TR.label(self.work, rec).split(' · ')[-1]} (same time)")
            self.done.append(f"{self.when(L)} {', '.join(L['c'])} {L['s']}: {txt}")
            self.done_rows.append((self.when(L), ", ".join(L["c"]), L["s"], txt))
            n += 1
        self.fill()
        if skipped:
            messagebox.showinfo("Teacher change", f"{n} lesson(s) handed over at the same time.\n\n{skipped} lesson(s) "
                                                  "clash with the receiving teacher . Select one "
                                                  "and press “📍 Find a place”.", parent=self.win)

    def find_place(self):
        dr = self.need()
        if not dr:
            return
        donor, rec = dr
        sel = self.picked()
        if len(sel) != 1:
            messagebox.showinfo("Find a place", "Select ONE lesson in the list.", parent=self.win)
            return
        L = sel[0]
        pl = TR.places(self.work, self.rules, L, donor, rec)
        if not pl:
            messagebox.showinfo("Find a place", "No place in the week is free for the receiving teacher, the class and "
                                                "the lab without a clash. Give this lesson to another "
                                                "teacher, or move other lessons first (step 4).", parent=self.win)
            return
        win = tk.Toplevel(self.win)
        win.title("Find a place")
        win.geometry("760x460")
        win.configure(bg=U.CREAM)
        win.transient(self.win)
        tk.Label(win, text=f"{', '.join(L['c'])} {L['s']} (now {self.when(L)}) with "
                           f"{TR.label(self.work, rec).split(' · ')[-1]} can go to:", bg=U.CREAM, fg=U.NAVY,
                 font=("Segoe UI Semibold", 11), wraplength=720, justify="left").pack(anchor="w", padx=12, pady=(10, 6))
        tv = ttk.Treeview(win, columns=("when", "how", "note"), show="headings", height=12)
        for c, txt, wd in (("when", "Place", 180), ("how", "How", 300), ("note", "Receiving teacher that day", 240)):
            tv.heading(c, text=txt)
            tv.column(c, width=wd)
        tv.pack(fill="both", expand=True, padx=12)
        for i, x in enumerate(pl[:40]):
            tv.insert("", "end", iid=str(i), values=(
                self.when(dict(L, d=x["d"], p=x["p"])),
                "free — the lesson moves here" if x["status"] == "ok" else f"swap with {x['with']}",
                f"{x['day_load']} lesson(s)"))
        tv.selection_set("0")

        def go():
            s = tv.selection()
            if not s:
                return
            x = pl[int(s[0])]
            try:
                self.work = TR.move_and_hand_over(self.work, self.rules, L, donor, rec, x["d"], x["p"])
            except ValueError as e:
                messagebox.showinfo("Find a place", str(e), parent=win)
                return
            txt = (f"moved to {self.when(dict(L, d=x['d'], p=x['p']))}"
                   + (f" (swapped with {x['with']})" if x["status"] == "swap" else "")
                   + f", now {TR.label(self.work, rec).split(' · ')[-1]}")
            self.done.append(f"{', '.join(L['c'])} {L['s']} {self.when(L)}: {txt}")
            self.done_rows.append((self.when(L), ", ".join(L["c"]), L["s"], txt))
            win.destroy()
            self.fill()
        b = tk.Frame(win, bg=U.CREAM)
        b.pack(fill="x", padx=12, pady=10)
        ttk.Button(b, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(b, text="✔  Move here and hand over", style="Accent.TButton", command=go).pack(side="right", padx=8)
        tv.bind("<Double-1>", lambda e: go())

    def reset(self):
        if self.done or self.added:
            if not messagebox.askyesno("Start again", "Undo everything done in this window?", parent=self.win):
                return
        self.work, self.done, self.done_rows, self.added = self.orig, [], [], []
        self.load_names()
        self.fill()

    def finish(self):
        if not self.done:
            self.win.destroy()
            return
        donor = self.code_of(self.donor_var.get())
        if self.remove_var.get() and donor and not TR.lessons_of_teacher(self.work, donor):
            try:
                self.work = TR.remove_teacher(self.work, donor)
            except ValueError:
                pass
        aff = TR.affected(self.orig, self.work)
        self.app.apply_moves(self.work, len(self.done), extra="teacher change — only " + ", ".join(aff["teachers"]) +
                             (" and classes " + ", ".join(aff["classes"]) if aff["classes"] else ""), stay=True)
        self.app.run.log("👥 Teacher change: " + "; ".join(self.done[:6]) + ("…" if len(self.done) > 6 else ""))
        self.win.destroy()
