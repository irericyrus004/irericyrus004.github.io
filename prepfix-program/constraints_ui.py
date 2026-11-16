"""The Constraints tab of PREPFIX, the rule editor and the report window."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import constraints as K
import rules_word as RW
import prepfix_ui as U


# ---------------------------------------------------------------------------------------- report window
def show_report(root, rep, can_continue=False, title="Constraint report", on_fix=None, info=False,
                fix_text="🛠  Fix it now (step 3)") -> bool:
    """Show the report. Returns True only if can_continue and the user chose 'Publish anyway'.
    on_fix: when given and rules failed, a "Fix it" button runs it.
    info=True: the report is for information only - nothing is blocked (rules in operation / extra checks)."""
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("820x560")
    win.configure(bg=U.CREAM)
    win.transient(root)
    win.grab_set()
    out = {"go": False}
    head = K.summary_line(rep).replace("  Click “View constraint report”.", "")
    tk.Label(win, text=head, bg=U.CREAM, fg=U.RED if rep["errors"] else U.GREEN, wraplength=780, justify="left",
             font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=14, pady=(12, 6))
    box = tk.Frame(win)
    box.pack(fill="both", expand=True, padx=14)
    sb = ttk.Scrollbar(box)
    sb.pack(side="right", fill="y")
    txt = tk.Text(box, wrap="word", font=("Segoe UI", 10), bg="white", relief="flat", padx=10, pady=8,
                  yscrollcommand=sb.set)
    txt.pack(fill="both", expand=True)
    sb.config(command=txt.yview)
    txt.tag_configure("err", foreground=U.RED, font=("Segoe UI Semibold", 10))
    txt.tag_configure("warn", foreground="#8A6100", font=("Segoe UI Semibold", 10))
    txt.tag_configure("rule", font=("Segoe UI Semibold", 10), foreground=U.NAVY)
    if not rep["issues"]:
        txt.insert("end", "Every rule passed.")
    else:
        heads = ((K.ERR, "BROKEN — a rule set at 100 % (you may correct it by moving lessons; publishing is still allowed)"
                  if info else "MUST FIX — publishing is blocked", "err"),
                 (K.WARN, "WARNINGS — preferred rules" if info else "WARNINGS — publishing is allowed", "warn"))
        for sev, title_, tag in heads:
            items = [i for i in rep["issues"] if i["sev"] == sev]
            if not items:
                continue
            txt.insert("end", title_ + "\n", tag)
            rule = None
            for i in items:
                if (i["num"], i["rule"]) != rule:
                    rule = (i["num"], i["rule"])
                    txt.insert("end", f"\n● Rule {i['num']}: {i['rule']}\n", "rule")
                txt.insert("end", "     – " + i["msg"] + "\n")
            txt.insert("end", "\n")
    txt.configure(state="disabled")
    bar = tk.Frame(win, bg=U.CREAM)
    bar.pack(fill="x", padx=14, pady=10)

    def save():
        f = filedialog.asksaveasfilename(parent=win, defaultextension=".txt", initialfile="constraint-report.txt",
                                         filetypes=[("Text", "*.txt")])
        if f:
            open(f, "w", encoding="utf-8").write(K.report_text(rep))

    def go():
        out["go"] = True
        win.destroy()

    ttk.Button(bar, text="Save report…", command=save).pack(side="left")
    if on_fix and rep["issues"]:
        def fix():
            win.destroy()
            root.after(50, on_fix)
        ttk.Button(bar, text=fix_text, style="Accent.TButton", command=fix).pack(side="right", padx=(8, 0))
    if can_continue and not rep["errors"]:
        ttk.Button(bar, text="Publish anyway", style="Accent.TButton", command=go).pack(side="right")
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=8)
    else:
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
    root.wait_window(win)
    return out["go"]


# ---------------------------------------------------------------------------------------- rule editor
class RuleDialog:
    def __init__(self, root, data, rule=None, num=None):
        self.result = None
        self.data = data
        self.rule = dict(rule) if rule else None
        w = self.win = tk.Toplevel(root)
        w.title(f"Edit rule {num}" if rule else "New rule")
        w.configure(bg="white")
        w.transient(root)
        w.grab_set()
        w.resizable(False, False)
        self.body = ttk.Frame(w, style="Card.TFrame", padding=16)
        self.body.pack(fill="both", expand=True)
        ttk.Label(self.body, text="Rule type", style="H.TLabel").grid(row=0, column=0, sticky="w", pady=4)
        self.labels = {k: v["label"] for k, v in K.TYPES.items() if not v.get("builtin")}
        self.type_var = tk.StringVar()
        cb = ttk.Combobox(self.body, textvariable=self.type_var, state="readonly", width=46,
                          values=list(self.labels.values()))
        cb.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.build_fields())
        self.sev_var = tk.StringVar(value=K.SEVERITIES[(rule or {}).get("severity", K.ERR)])
        self.frame = ttk.Frame(self.body, style="Card.TFrame")
        self.frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.vars = {}
        self.sev_row = 20
        ttk.Label(self.body, text="If it fails", style="H.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 4))
        ttk.Combobox(self.body, textvariable=self.sev_var, state="readonly", width=46,
                     values=list(K.SEVERITIES.values())).grid(row=2, column=1, sticky="w", padx=8, pady=(10, 4))
        bar = ttk.Frame(self.body, style="Card.TFrame")
        bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(bar, text="Cancel", command=w.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(bar, text="Save rule", style="Accent.TButton", command=self.save).pack(side="right")
        if rule and rule["type"] in self.labels:
            self.type_var.set(self.labels[rule["type"]])
            cb.configure(state="disabled")
        else:
            self.type_var.set(list(self.labels.values())[0])
        self.build_fields()
        root.wait_window(w)

    def key(self):
        return next(k for k, v in self.labels.items() if v == self.type_var.get())

    def suggestions(self, kind):
        d = self.data
        if not d:
            return []
        if kind == "teacher":
            return ["*"] + [t.get("name") or t["code"] for t in d["teachers"]]
        if kind == "class":
            return ["*"] + [c["name"] for c in d["classes"]]
        if kind == "subject":
            seen = []
            for l in K.lessons_of(d):
                for s in (l["s"],):
                    if s and s not in seen:
                        seen.append(s)
            return ["*"] + sorted(seen)
        return []

    def build_fields(self):
        for ch in self.frame.winfo_children():
            ch.destroy()
        self.vars = {}
        spec = K.TYPES[self.key()]["fields"]
        cur = self.rule if self.rule and self.rule["type"] == self.key() else K.new_rule(self.key())
        d = self.data
        for i, (k, label, kind) in enumerate(spec):
            ttk.Label(self.frame, text=label, style="Card.TLabel").grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar(value=str(cur.get(k, "")))
            if k in ("teacher", "class", "subject") and not cur.get(k):
                v.set("*" if k != "subject" or self.key() == "subject_max_day" else "")
            self.vars[k] = v
            if kind in ("teacher", "class", "subject"):
                w = ttk.Combobox(self.frame, textvariable=v, width=44, values=self.suggestions(kind))
            elif kind == "int":
                w = ttk.Spinbox(self.frame, textvariable=v, from_=0, to=60, width=8)
                if not v.get():
                    v.set("2")
            elif kind.startswith("choice:"):
                opts = kind[7:].split("|")
                w = ttk.Combobox(self.frame, textvariable=v, state="readonly", width=20, values=opts)
                if not v.get():
                    v.set(opts[0])
            elif kind == "text":
                w = ttk.Entry(self.frame, textvariable=v, width=46)
            else:                                               # days / periods: comma separated
                w = ttk.Entry(self.frame, textvariable=v, width=46)
                hint = ""
                if kind == "days" and d:
                    hint = ", ".join(x["label"] for x in d["days"])
                if kind == "periods" and d:
                    hint = ", ".join(p["label"] for p in d["periods"] if not p["brk"])
                if hint:
                    ttk.Label(self.frame, text="e.g. " + hint[:70], style="CardMuted.TLabel").grid(
                        row=i, column=2, sticky="w", padx=6)
                elif kind == "days":
                    ttk.Label(self.frame, text="e.g. Mon, Tue", style="CardMuted.TLabel").grid(row=i, column=2, padx=6)
                else:
                    ttk.Label(self.frame, text="e.g. L1, L2 or 7:00-7:40", style="CardMuted.TLabel").grid(
                        row=i, column=2, padx=6)
            w.grid(row=i, column=1, sticky="w", padx=8, pady=4)
        if not self.data:
            ttk.Label(self.frame, text="Tip: add a timetable first and the boxes will suggest names to pick.",
                      style="CardMuted.TLabel").grid(row=len(spec), column=0, columnspan=3, sticky="w", pady=4)

    def save(self):
        key = self.key()
        r = dict(self.rule) if self.rule and self.rule["type"] == key else K.new_rule(key)
        for k, label, kind in K.TYPES[key]["fields"]:
            val = self.vars[k].get().strip()
            if kind == "int":
                if not val.isdigit():
                    messagebox.showinfo("Check the rule", f"“{label}” must be a whole number.", parent=self.win)
                    return
                val = int(val)
            elif kind in ("teacher", "class", "subject") and not val:
                messagebox.showinfo("Check the rule", f"Fill in “{label}”.", parent=self.win)
                return
            elif kind in ("days", "periods"):
                val = K._csv(val)
                if kind == "periods" and key == "subject_periods" and not val:
                    messagebox.showinfo("Check the rule", f"Fill in “{label}”.", parent=self.win)
                    return
            r[k] = val
        r["severity"] = next(k for k, v in K.SEVERITIES.items() if v == self.sev_var.get())
        r["enabled"] = r.get("enabled", True)
        self.result = r
        self.win.destroy()


# ---------------------------------------------------------------------------------------- the tab
class ConstraintsTab:
    def __init__(self, app, parent):
        self.app = app
        f = ttk.Frame(parent, style="Card.TFrame", padding=14)
        f.pack(fill="both", expand=True)
        self.title = ttk.Label(f, text="", style="H.TLabel")
        self.title.pack(anchor="w")
        top = ttk.Frame(f, style="Card.TFrame")
        top.pack(fill="x", pady=(4, 2))
        ttk.Button(top, text="▶  Run the extra checks on the timetable", style="Accent.TButton",
                   command=app.run_extra).pack(side="left")
        ttk.Label(top, text="  for your information — they never block moving or publishing",
                  style="CardMuted.TLabel").pack(side="left")
        app.btn_run2 = ttk.Button(top, text="▶  Run again", style="Accent.TButton", command=lambda: app.run_once(True),
                                  state="normal" if getattr(app, "ran", False) else "disabled")

        ttk.Label(f, text="Rules that may have been left out when the timetable was made. Tick the ones to run (click "
                          "the box). If the timetable passes, well; if not, the report shows what to correct — correcting "
                          "is up to you. Moves never depend on these: moves keep the rules in operation (above).",
                  style="CardMuted.TLabel", wraplength=940,
                  justify="left").pack(anchor="w", pady=(2, 8))
        bar = ttk.Frame(f, style="Card.TFrame")
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="＋  Add rule…", style="Gold.TButton", command=self.add).pack(side="left")
        ttk.Button(bar, text="Edit…", command=self.edit).pack(side="left", padx=6)
        ttk.Button(bar, text="Delete", command=self.delete).pack(side="left", padx=6)
        ttk.Button(bar, text="Tick all", command=lambda: self.tick_all(True)).pack(side="left")
        ttk.Button(bar, text="Untick all", command=lambda: self.tick_all(False)).pack(side="left", padx=6)
        ttk.Button(bar, text="Save rules to file…", command=self.export).pack(side="right")
        ttk.Button(bar, text="Load rules from file…", command=self.load_file).pack(side="right", padx=6)
        wb = ttk.Frame(f, style="Card.TFrame")
        wb.pack(fill="x", pady=(0, 6))
        ttk.Label(wb, text="Rules in Word:", style="H.TLabel").pack(side="left")
        ttk.Button(wb, text="📄  Download Word template", command=self.word_template).pack(side="left", padx=8)
        ttk.Button(wb, text="📥  Import rules from Word…", style="Accent.TButton", command=self.word_import).pack(side="left")
        ttk.Label(wb, style="CardMuted.TLabel", text="Fill the tables in Word, save, import.").pack(side="left", padx=10)
        self.tree = ttk.Treeview(f, columns=("on", "no", "lvl", "rule"), show="headings", height=7, selectmode="browse")
        self.tree.heading("on", text="Apply")
        self.tree.heading("no", text="No.")
        self.tree.heading("lvl", text="If it fails")
        self.tree.heading("rule", text="Rule")
        self.tree.column("on", width=60, anchor="center", stretch=False)
        self.tree.column("no", width=50, anchor="center", stretch=False)
        self.tree.column("lvl", width=130, stretch=False)
        self.tree.column("rule", width=700)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit() if self.tree.identify_column(e.x) != "#1" else None)
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.tag_configure("off", foreground="#98A2B3")
        row = ttk.Frame(f, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="Reset to the standard rules", command=self.reset).pack(side="left")
        self.rules = []
        self.code = None

    # --- storage: one list of rules per school
    def code_now(self):
        sch = self.app.current_school()
        return sch["code"] if sch else None

    def rules_for(self, code):
        store = self.app.pub.s.get("constraints", {}) or {}
        if code in store:
            return store[code]
        return K.defaults()

    def save_on(self):
        if self.code:
            st = dict(self.app.pub.s.get("constraints_on", {}) or {})
            st[self.code] = bool(self.app.use_con.get())
            self.app.pub.s.set("constraints_on", st)

    def save(self):
        if not self.code:
            return
        store = dict(self.app.pub.s.get("constraints", {}) or {})
        store[self.code] = self.rules
        self.app.pub.s.set("constraints", store)

    def refresh(self):
        self.code = self.code_now()
        sch = self.app.current_school()
        self.title.configure(text=("Extra checks for " + sch["name"]) if sch else "Extra checks")
        self.app.use_con.set(bool((self.app.pub.s.get("constraints_on", {}) or {}).get(self.code, False)))
        self.rules = self.rules_for(self.code) if self.code else K.defaults()
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for n, r in enumerate(self.rules, 1):
            self.tree.insert("", "end", iid=r["id"], tags=() if r.get("enabled", True) else ("off",),
                             values=("☑" if r.get("enabled", True) else "☐", n,
                                     "Must pass" if r.get("severity") == K.ERR else "Warning", K.describe(r)))
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])

    def need_school(self):
        if not self.code:
            messagebox.showinfo("Choose the school", "Choose the school on “Import & Run” first. Each school has "
                                                      "its own rules.")
            return False
        return True

    def picked(self):
        s = self.tree.selection()
        return next((r for r in self.rules if r["id"] == s[0]), None) if s else None

    def add(self):
        if not self.need_school():
            return
        res = RuleDialog(self.app.root, self.app.data).result
        if res:
            self.rules.append(res)
            self.save()
            self.refresh()

    def edit(self):
        r = self.picked()
        if not r:
            return
        if K.TYPES[r["type"]].get("builtin"):                    # standard rules: only the level can change
            cur = r.get("severity", K.ERR)
            r["severity"] = K.WARN if cur == K.ERR else K.ERR
            self.save()
            self.refresh()
            return
        res = RuleDialog(self.app.root, self.app.data, r, self.rules.index(r) + 1).result
        if res:
            self.rules[self.rules.index(r)] = res
            self.save()
            self.refresh()

    def on_click(self, e):
        if self.tree.identify_region(e.x, e.y) == "cell" and self.tree.identify_column(e.x) == "#1":
            iid = self.tree.identify_row(e.y)
            r = next((x for x in self.rules if x["id"] == iid), None)
            if r:
                r["enabled"] = not r.get("enabled", True)
                self.save()
                self.refresh()
                self.tree.selection_set(iid)
            return "break"

    def tick_all(self, on):
        for r in self.rules:
            r["enabled"] = on
        self.save()
        self.refresh()

    def toggle(self):
        r = self.picked()
        if r:
            r["enabled"] = not r.get("enabled", True)
            self.save()
            self.refresh()

    def delete(self):
        r = self.picked()
        if r and messagebox.askyesno("Delete rule", f"Delete this rule?\n\n{K.describe(r)}"):
            self.rules.remove(r)
            self.save()
            self.refresh()

    def reset(self):
        if self.need_school() and messagebox.askyesno("Reset", "Replace this school's rules with the standard ones?"):
            self.rules = K.defaults()
            self.save()
            self.refresh()

    def export(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", initialfile="constraints.json",
                                         filetypes=[("Rules file", "*.json")])
        if f:
            open(f, "w", encoding="utf-8").write(K.to_json(self.rules))

    def word_template(self):
        sch = self.app.current_school()
        name = sch["name"] if sch else ""
        f = filedialog.asksaveasfilename(title="Save the Word template", defaultextension=".docx",
                                         initialfile=f"PREPFIX rules - {name or 'school'}.docx".replace("/", "-"),
                                         filetypes=[("Word document", "*.docx")])
        if not f:
            return
        try:
            RW.make_template(f, name, self.app.data)
        except Exception as e:
            messagebox.showerror("Word template", f"The template could not be saved:\n{e}")
            return
        self.app.run.log("✔ Word template saved: " + f)
        if messagebox.askyesno("Word template", "Saved:\n" + f + "\n\nOpen it in Word now?"):
            try:
                import os
                os.startfile(f)
            except Exception:
                pass

    def word_import(self):
        if not self.need_school():
            return
        f = filedialog.askopenfilename(title="Choose the filled Word file", filetypes=[("Word document", "*.docx")])
        if not f:
            return
        try:
            new, probs = RW.read_rules(f, self.app.data)
        except Exception as e:
            messagebox.showerror("Import rules", f"That file could not be read as a Word document (.docx).\n\n{e}")
            return
        mine = [r for r in new if not K.TYPES[r["type"]].get("builtin")]
        msg = f"{len(mine)} rule(s) found in the Word file (plus the standard rules)."
        if probs:
            msg += f"\n\n{len(probs)} row(s) were NOT added — correct them in Word and import again:\n\n" + \
                   "\n".join(f"• {t}, row {n}: {why}\n    ({txt})" for t, n, txt, why in probs[:12]) + \
                   (f"\n…and {len(probs) - 12} more." if len(probs) > 12 else "")
        if not mine and not probs:
            messagebox.showinfo("Import rules", "The Word file has no rules filled in yet.")
            return
        ans = messagebox.askyesnocancel("Import rules", msg + "\n\nREPLACE this school's rules with these (Yes), or ADD "
                                                              "them to the rules it has (No)?")
        if ans is None:
            return
        if ans:
            self.rules = new
        else:
            have = {r["type"] for r in self.rules if K.TYPES.get(r["type"], {}).get("builtin")}
            self.rules += [r for r in new if not (K.TYPES[r["type"]].get("builtin") and r["type"] in have)]
        self.save()
        self.refresh()
        self.app.run.log(f"✔ {len(mine)} rule(s) imported from Word" + (f" — {len(probs)} row(s) need correcting" if probs else "") + ".")

    def load_file(self):
        if not self.need_school():
            return
        f = filedialog.askopenfilename(filetypes=[("Rules file", "*.json")])
        if not f:
            return
        try:
            new = K.from_json(open(f, encoding="utf-8").read())
        except Exception as e:
            messagebox.showerror("Problem", f"That is not a rules file.\n\n{e}")
            return
        if new and messagebox.askyesno("Load rules", f"Load {len(new)} rules? They REPLACE this school's current "
                                                      "rules (Yes) or are ADDED to them (No)?"):
            self.rules = new
        elif new:
            self.rules += new
        self.save()
        self.refresh()
