"""The "My rules" window: Cyrus writes his own rules in his own words - for students (classes), teachers and
rooms (labs & fields) - and runs them over the timetable. The result is for information: whatever it says, the
work goes on. Nothing here is suggested and nothing is blocked."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

import my_rules as R
import prepfix_core as core
import prepfix_ui as U

SECTIONS = (("students", "Students (classes)"), ("teachers", "Teachers"), ("rooms", "Rooms (labs & fields)"))


class MyRules:
    def __init__(self, app):
        self.app = app
        self.win = None
        self.boxes = {}

    # --- storage: per school
    def _store(self):
        return dict(self.app.pub.s.get("my_rules", {}) or {})

    def texts(self):
        sch = self.app.current_school()
        return dict(self._store().get(sch["code"], {})) if sch else {}

    def count(self):
        return sum(1 for _ in R.lines_of(self.texts()))

    def observe(self):
        """Should the timetable OBSERVE my rules (moves keep them; Streamline moves lessons to keep them)?"""
        return bool(self.texts().get("_observe"))

    def rules(self):
        return R.as_rules(self.texts(), observe=self.observe())

    def save(self):
        sch = self.app.current_school()
        if not sch or not self.win:
            return
        st = self._store()
        st[sch["code"]] = {k: self.boxes[k].get("1.0", "end").strip() for k, _ in SECTIONS}
        st[sch["code"]]["_observe"] = bool(self.obs_var.get())
        self.app.pub.s.set("my_rules", st)
        self.app.move.src = None                       # the moving screen is rebuilt with (or without) my rules
        self.app.update_path_steps()

    # --- the window
    def open(self):
        sch = self.app.current_school()
        if not sch:
            messagebox.showinfo("My rules", "Choose the school first.")
            return
        if self.win and self.win.winfo_exists():
            self.app.front(self.win)
            return
        w = self.win = tk.Toplevel(self.app.root)
        w.title("PREPFIX — My rules")
        w.geometry("1100x700")
        w.configure(bg=U.CREAM)
        try:
            w.state("zoomed")
        except tk.TclError:
            pass
        w.protocol("WM_DELETE_WINDOW", self.close)
        bar = ttk.Frame(w, style="Card.TFrame", padding=(14, 10))
        bar.pack(fill="x", side="bottom")
        ttk.Button(bar, text="▶  Run my rules on the timetable", style="Accent.TButton", command=self.run
                   ).pack(side="right")
        ttk.Button(bar, text="Close", command=self.close).pack(side="right", padx=8)
        ttk.Button(bar, text="Save", command=lambda: (self.save(), self.app.run.log("✔ My rules saved."))
                   ).pack(side="left")
        self.obs_var = tk.BooleanVar(value=self.observe())
        ttk.Checkbutton(bar, variable=self.obs_var, command=self.save,
                        text="Make the timetable OBSERVE my rules — moves never break them, and “Streamline” moves "
                             "lessons to keep them").pack(side="left", padx=14)
        top = ttk.Frame(w, style="Card.TFrame", padding=(14, 10))
        top.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(top, text=f"My rules — {sch['name']}", style="H.TLabel").pack(anchor="w")
        ttk.Label(top, style="CardMuted.TLabel", wraplength=1000, justify="left",
                  text="Write your rules in your own words, one rule per line. Name the class, teacher or room the "
                       "rule is about — or leave the name out to mean all of them. Then press “Run my rules”: "
                       "PREPFIX shows how it understood each line and whether the timetable keeps it. Whatever the "
                       "result, you continue as usual.").pack(anchor="w")
        cols = ttk.Frame(w, style="Card.TFrame", padding=(10, 6))
        cols.pack(fill="both", expand=True, padx=10, pady=(6, 0))
        saved = self.texts()
        for i, (key, title) in enumerate(SECTIONS):
            f = ttk.Frame(cols, style="Card.TFrame")
            f.grid(row=0, column=i, sticky="nsew", padx=4)
            cols.columnconfigure(i, weight=1)
            ttk.Label(f, text=title, style="H.TLabel").pack(anchor="w")
            t = tk.Text(f, wrap="word", font=("Segoe UI", 11), relief="solid", bd=1, padx=8, pady=6, undo=True)
            t.pack(fill="both", expand=True)
            t.insert("1.0", saved.get(key, ""))
            self.boxes[key] = t
        cols.rowconfigure(0, weight=1)
        self.app.front(w)

    def close(self):
        if self.win and self.win.winfo_exists():
            self.save()
            self.win.destroy()
        self.win = None

    def run(self):
        self.save()
        data = self.app.data
        if data is None:
            messagebox.showinfo("My rules", "Add the timetable first.", parent=self.win)
            return
        if not any(True for _ in R.lines_of(self.texts())):
            messagebox.showinfo("My rules", "Write at least one rule first.", parent=self.win)
            return
        res = R.run(self.texts(), data)
        self.app.run.log("My rules: " + R.summary(res))
        self.show(res)

    def show(self, res):
        sch = self.app.current_school() or {}
        w = tk.Toplevel(self.win or self.app.root)
        w.title("My rules — result")
        w.geometry("1000x640")
        w.configure(bg=U.CREAM)
        w.transient(self.win or self.app.root)
        tk.Label(w, text=R.summary(res), bg=U.CREAM, fg=U.NAVY, font=("Segoe UI Semibold", 12), wraplength=960,
                 justify="left").pack(anchor="w", padx=14, pady=(12, 6))
        box = tk.Frame(w)
        box.pack(fill="both", expand=True, padx=14)
        sb = ttk.Scrollbar(box)
        sb.pack(side="right", fill="y")
        txt = tk.Text(box, wrap="word", font=("Segoe UI", 10), bg="white", relief="flat", padx=10, pady=8,
                      yscrollcommand=sb.set)
        txt.pack(fill="both", expand=True)
        sb.config(command=txt.yview)
        txt.tag_configure("ok", foreground=U.GREEN, font=("Segoe UI Semibold", 11))
        txt.tag_configure("bad", foreground=U.RED, font=("Segoe UI Semibold", 11))
        txt.tag_configure("unk", foreground="#8A6100", font=("Segoe UI Semibold", 11))
        txt.tag_configure("how", foreground="#555555", font=("Segoe UI", 9, "italic"))
        names = dict(SECTIONS)
        for i, r in enumerate(res, 1):
            tag = {True: "ok", False: "bad", None: "unk"}[r["ok"]]
            mark = {True: "✔ kept", False: f"✖ not kept ({len(r['problems'])})", None: "? not understood"}[r["ok"]]
            txt.insert("end", f"{i}.  {mark}   —   {r['line']}   ", tag)
            txt.insert("end", f"[{names[r['section']]}]\n", "how")
            if r["understood"]:
                txt.insert("end", f"      Understood as: {r['understood']}\n", "how")
            if r["why"]:
                txt.insert("end", f"      {r['why']}\n")
            for p in r["problems"][:40]:
                txt.insert("end", f"      – {p}\n")
            if len(r["problems"]) > 40:
                txt.insert("end", f"      … and {len(r['problems']) - 40} more (Save the result to see all)\n")
            txt.insert("end", "\n")
        txt.configure(state="disabled")
        bar = tk.Frame(w, bg=U.CREAM)
        bar.pack(fill="x", padx=14, pady=10)

        def save():
            f = filedialog.asksaveasfilename(parent=w, defaultextension=".txt", initialfile="PREPFIX my rules.txt",
                                             filetypes=[("Text", "*.txt")])
            if f:
                Path(f).write_text(R.report_text(res, sch.get("name", "")) +
                                   f"\n{core.LOCKED_BRAND} {core.LOCKED_CONTACT}\n", encoding="utf-8")
        ttk.Button(bar, text="Save the result…", command=save).pack(side="left")
        ttk.Button(bar, text="Continue", style="Accent.TButton", command=w.destroy).pack(side="right")
        ttk.Button(bar, text="✎  Move lessons", command=lambda: (w.destroy(), self.close(),
                                                                 self.app.run_once(True, mode="move"))
                   ).pack(side="right", padx=8)
        if any(r["ok"] is False for r in res):
            def streamline():
                if not self.observe():
                    self.obs_var.set(True)
                    self.save()
                w.destroy()
                self.close()
                self.app.path_fix()
            ttk.Button(bar, text="🛠  Streamline: move lessons to keep my rules", style="Gold.TButton",
                       command=streamline).pack(side="right", padx=8)
        self.app.front(w)
