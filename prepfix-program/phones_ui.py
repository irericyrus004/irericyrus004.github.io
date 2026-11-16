"""TEACHERS & PHONES - a school's list of teachers and their phone numbers (Cyrus's edition).

When the school is LOCKED, only a phone whose number is on this list can open the school's timetables, and only
ONE phone per number. Cyrus sees who has the app and when they last opened it. A teacher who changed phones is
"freed" here and types the number again on the new phone."""
from __future__ import annotations

import json
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import prepfix_core as core
import prepfix_lock as LOCK


def core_text(e):
    try:
        import prepfix_core as _c
        return _c.public_text(str(e))
    except Exception:
        return str(e)
import prepfix_ui as U
import pin_sheet


def _ago(iso):
    if not iso:
        return ""
    try:
        from datetime import datetime, timezone
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        m = (datetime.now(timezone.utc) - t).total_seconds() / 60
    except Exception:
        return iso[:10]
    if m < 2:
        return "just now"
    if m < 60:
        return f"{int(m)} min ago"
    if m < 1440:
        return f"{int(m // 60)} h ago"
    return f"{int(m // 1440)} days ago"


class Phones:
    def __init__(self, app, code):
        self.app, self.pub, self.code = app, app.pub, code
        self.sch = self.pub.school(code)
        self.people = self.pub.phones(code)
        self.status = {}
        self.teachers = self._timetable_teachers()
        w = self.win = tk.Toplevel(app.root)
        w.title(f"PREPFIX — Teachers & phones — {self.sch['name']}")
        w.geometry("1050x640")
        w.configure(bg=U.CREAM)
        try:
            w.state("zoomed")
        except tk.TclError:
            pass
        top = ttk.Frame(w, style="Card.TFrame", padding=(14, 10))
        top.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(top, text=f"Teachers & phones — {self.sch['name']}", style="H.TLabel").pack(anchor="w")
        self.state_lbl = tk.Label(top, text="", bg="white", font=("Segoe UI Semibold", 11), wraplength=1000,
                                  justify="left")
        self.state_lbl.pack(anchor="w", pady=(4, 2))
        ttk.Label(top, style="CardMuted.TLabel", wraplength=1000, justify="left",
                  text="Add every teacher with the phone number they registered with. On the phone the teacher types "
                       "that number and makes their own 4-number PIN; they stay signed in until they sign out. A number "
                       "signed in on one phone cannot sign in anywhere else. Not the right person signed in? Click the "
                       "teacher → “Remove sign-in”, and the rightful teacher signs in."
                  ).pack(anchor="w")
        bar = ttk.Frame(w, style="Card.TFrame", padding=(14, 8))
        bar.pack(fill="x", padx=10, pady=(6, 0))
        for txt, cmd in (("+ Add teacher…", self.add), ("✎ Edit…", self.edit), ("🗑 Remove", self.remove),
                         ("📋 Paste a list…", self.paste), ("Fill names from the timetable", self.fill)):
            ttk.Button(bar, text=txt, command=cmd).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="↻ Who has the app?", command=self.check).pack(side="right")
        ttk.Button(bar, text="🔓 Remove sign-in", command=self.free).pack(side="right", padx=6)
        mid = ttk.Frame(w)
        mid.pack(fill="both", expand=True, padx=10, pady=6)
        cols = ("name", "phone", "t", "app")
        self.tv = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        for c, t_, wd in (("name", "Teacher", 300), ("phone", "Phone number", 160), ("t", "In the timetable", 240),
                          ("app", "Signed in on", 280)):
            self.tv.heading(c, text=t_)
            self.tv.column(c, width=wd, anchor="w")
        sb = ttk.Scrollbar(mid, command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", lambda e: self.edit())
        self.tv.tag_configure("bad", foreground="#B5463A")
        bot = ttk.Frame(w, style="Card.TFrame", padding=(14, 10))
        bot.pack(fill="x", side="bottom")
        self.lock_btn = ttk.Button(bot, text="", style="Accent.TButton", command=self.toggle_lock)
        if not self.pub.is_school:                        # only Cyrus switches the lock and changes the key
            self.lock_btn.pack(side="right")
        ttk.Button(bot, text="💾 Save the list", style="Gold.TButton", command=self.save).pack(side="right", padx=8)
        self.save_bar = ttk.Progressbar(bot, mode="indeterminate", length=110)     # shows while the list is being sent
        self.save_lbl = tk.Label(bot, text="", bg="white", font=("Segoe UI Semibold", 10), wraplength=430, justify="right")
        self.save_lbl.pack(side="right", padx=6)
        if not self.pub.is_school:
            ttk.Button(bot, text="🔁 New key (every phone signs in again)", command=self.rekey).pack(side="left")
        ttk.Button(bot, text="Close", command=self.close).pack(side="left", padx=8)
        w.protocol("WM_DELETE_WINDOW", self.close)
        self.dirty = False
        self.refresh()
        app.front(w)

    # ----------------------------------------------------------------------------------------------- data
    def _timetable_teachers(self):
        """[(code, name)] of the school's newest timetable (or the one on Import & Run)."""
        d = self.app.data if (self.app.data is not None and (self.app.current_school() or {}).get("code") == self.code) else None
        if d is None:
            tts = sorted(self.pub.timetables(self.code), key=lambda t: t.get("updated", ""), reverse=True)
            for t in tts:
                f = core.DATA_DIR / "history" / self.code / t["id"] / "current.json"
                if f.exists():
                    try:
                        d = (json.loads(f.read_text("utf-8")).get("bundle") or {})
                        break
                    except Exception:
                        pass
        return [(t["code"], t.get("name") or "") for t in (d or {}).get("teachers", [])]

    def tlabel(self, code):
        n = next((n for c, n in self.teachers if c == code), "")
        return f"{code} · {n}" if code and n else (code or "")

    def refresh(self):
        locked = bool(self.sch.get("lock"))
        n = sum(1 for p in self.people if p.get("phone"))
        joined = sum(1 for p in self.people if (self.status.get(p.get("phone")) or {}).get("joined"))
        self.state_lbl.configure(
            text=(f"🔒 LOCKED — only the {n} teacher(s) on this list can open the timetables on their phones."
                  + (f"  {joined} have the app." if self.status else "")) if locked else
                 ("🔓 NOT LOCKED — ask Cyrus Ireri to switch on teachers' sign-in for this school."
                  if self.pub.is_school else
                 "🔓 NOT LOCKED — anybody with the school's link can open the timetables. Add the teachers, then "
                 "press “Lock this school”."), fg="#176548" if locked else "#8A6100")
        self.lock_btn.configure(text="🔓 Unlock this school" if locked else "🔒 Lock this school")
        self.tv.delete(*self.tv.get_children())
        seen = {}
        for i, p in enumerate(self.people):
            st = self.status.get(p.get("phone")) or {}
            app_txt = ("✔ " + {"and": "Android", "ios": "iPhone", "pc": "computer"}.get(st.get("plat"), "phone")
                       + (f" · last used {_ago(st.get('last'))}" if st.get("last") else "")
                       ) if st.get("joined") else \
                ("— not yet" if self.status else "")
            dup = p.get("phone") and p["phone"] in seen
            seen[p.get("phone")] = 1
            bad = not p.get("phone") or dup
            self.tv.insert("", "end", iid=str(i), tags=("bad",) if bad else (), values=(
                p.get("name", ""), LOCK.show_phone(p["phone"]) if p.get("phone") else "⚠ no number",
                self.tlabel(p.get("t", "")), "⚠ same number twice" if dup else app_txt))

    def sel(self):
        return [int(i) for i in self.tv.selection()]

    def _changed(self):
        self.dirty = True
        self.refresh()

    # ----------------------------------------------------------------------------------------------- editing
    def _dialog(self, p=None):
        p = dict(p or {})
        d = tk.Toplevel(self.win)
        d.title("Teacher")
        d.configure(bg=U.CREAM, padx=16, pady=14)
        d.transient(self.win)
        tk.Label(d, text="Teacher's name", bg=U.CREAM).grid(row=0, column=0, sticky="w")
        nv = tk.StringVar(value=p.get("name", ""))
        ttk.Entry(d, textvariable=nv, width=40).grid(row=0, column=1, pady=4)
        tk.Label(d, text="Phone number", bg=U.CREAM).grid(row=1, column=0, sticky="w")
        pv = tk.StringVar(value=LOCK.show_phone(p["phone"]) if p.get("phone") else "")
        ttk.Entry(d, textvariable=pv, width=40).grid(row=1, column=1, pady=4)
        tk.Label(d, text="In the timetable", bg=U.CREAM).grid(row=2, column=0, sticky="w")
        opts = [""] + [self.tlabel(c) for c, _ in self.teachers]
        tv = tk.StringVar(value=self.tlabel(p.get("t", "")))
        ttk.Combobox(d, textvariable=tv, values=opts, width=38, state="readonly").grid(row=2, column=1, pady=4)
        tk.Label(d, text="(the app then opens straight on this teacher's timetable)", bg=U.CREAM, fg="#667085"
                 ).grid(row=3, column=1, sticky="w")
        out = {}

        def ok():
            ph = LOCK.normalize_phone(pv.get())
            if not nv.get().strip():
                messagebox.showinfo("Teacher", "Type the teacher's name.", parent=d)
                return
            if not ph:
                messagebox.showinfo("Teacher", "Type a phone number like 0712 345 678.", parent=d)
                return
            code = tv.get().split(" · ")[0] if tv.get() else ""
            out.update(name=nv.get().strip(), phone=ph, t=code, pin=p.get("pin", ""))
            d.destroy()
        ttk.Button(d, text="OK", style="Accent.TButton", command=ok).grid(row=4, column=1, sticky="e", pady=(10, 0))
        d.bind("<Return>", lambda e: ok())
        self.app.front(d)
        d.grab_set()
        self.win.wait_window(d)
        return out or None

    def _no_double(self, phone, skip=None):
        for i, p in enumerate(self.people):
            if i != skip and p.get("phone") == phone:
                messagebox.showinfo("Teachers & phones", f"{LOCK.show_phone(phone)} is already on the list for "
                                    f"{p.get('name')}. One number = one teacher.", parent=self.win)
                return False
        return True

    def add(self):
        p = self._dialog()
        if p and self._no_double(p["phone"]):
            p["pin"] = p.get("pin") or LOCK.new_pin()
            self.people.append(p)
            self._changed()

    def edit(self):
        s = self.sel()
        if not s:
            return
        p = self._dialog(self.people[s[0]])
        if p and self._no_double(p["phone"], skip=s[0]):
            self.people[s[0]] = p
            self._changed()

    def remove(self):
        s = self.sel()
        if s and messagebox.askyesno("Teachers & phones", f"Remove {len(s)} teacher(s) from the list? Their phones "
                                     "stop opening new timetables once the list is saved.", parent=self.win):
            self.people = [p for i, p in enumerate(self.people) if i not in s]
            self._changed()

    def _match(self, name):
        from notes_word import _surname_rx
        best, score = "", 0
        for c, n in self.teachers:
            r = _surname_rx(n) if n else None
            if r:
                k = len({m.group(0).upper() for m in r[0].finditer(name.upper())})
                if k > score:
                    best, score = c, k
        return best

    def paste(self):
        d = tk.Toplevel(self.win)
        d.title("Paste a list")
        d.geometry("640x460")
        d.configure(bg=U.CREAM)
        d.transient(self.win)
        tk.Label(d, text="One teacher per line: the name and the phone number, in any order (from Excel, WhatsApp, "
                         "a document…). PREPFIX finds the number and the teacher in the timetable.", bg=U.CREAM,
                 wraplength=600, justify="left").pack(anchor="w", padx=12, pady=(10, 6))
        bar = tk.Frame(d, bg=U.CREAM)                       # the button first, at the bottom: always visible
        bar.pack(side="bottom", fill="x", padx=12, pady=8)
        box = tk.Text(d, font=("Segoe UI", 11), wrap="none", height=12)
        box.pack(fill="both", expand=True, padx=12)
        box.focus_set()

        def use():
            added, bad = 0, []
            for line in box.get("1.0", "end").splitlines():
                if not line.strip():
                    continue
                m = re.search(r"(\+?\d[\d\s\-]{7,15}\d)", line)
                ph = LOCK.normalize_phone(m.group(1)) if m else None
                name = re.sub(r"\s+", " ", (line[:m.start()] + " " + line[m.end():]) if m else line).strip(" ,;:-\t|")
                if not ph or not name:
                    bad.append(line.strip())
                    continue
                if any(p.get("phone") == ph for p in self.people):
                    bad.append(line.strip() + "   (number already on the list)")
                    continue
                self.people.append({"name": name, "phone": ph, "t": self._match(name), "pin": LOCK.new_pin()})
                added += 1
            d.destroy()
            self._changed()
            messagebox.showinfo("Paste a list", f"{added} teacher(s) added." + (
                "\n\nNot added:\n" + "\n".join(bad[:15]) if bad else ""), parent=self.win)
        ttk.Button(bar, text="✔  Add them to the list", style="Accent.TButton", command=use).pack(side="right")
        ttk.Button(bar, text="Cancel", command=d.destroy).pack(side="right", padx=8)
        tk.Label(bar, text="Paste (Ctrl+V), then press “Add them to the list”.", bg=U.CREAM, fg="#667085").pack(side="left")
        box.bind("<Control-Return>", lambda e: (use(), "break")[1])
        self.app.front(d)

    def fill(self):
        have = {p.get("t") for p in self.people}
        new = [{"name": n or c, "phone": "", "t": c, "pin": LOCK.new_pin()} for c, n in self.teachers if c not in have]
        if not new:
            messagebox.showinfo("Teachers & phones", "Every teacher in the timetable is already on the list."
                                if self.teachers else "No timetable for this school on this computer yet.", parent=self.win)
            return
        self.people += new
        self._changed()
        messagebox.showinfo("Teachers & phones", f"{len(new)} name(s) added from the timetable. Now double-click each "
                            "one and type the phone number.", parent=self.win)

    def new_pin(self):
        s = self.sel()
        if not s:
            messagebox.showinfo("New PIN", "Click the teacher first.", parent=self.win)
            return
        if not messagebox.askyesno("New PIN", f"Give {len(s)} teacher(s) a new PIN? The old PIN stops working once "
                                   "the list is saved. Print their new slip.", parent=self.win):
            return
        for i in s:
            self.people[i]["pin"] = LOCK.new_pin()
        self._changed()

    def print_pins(self):
        from tkinter import filedialog
        self.pub.set_phones(self.code, self.people)            # every teacher has a PIN from now on
        self.people = self.pub.phones(self.code)
        self.refresh()
        if not self.people:
            messagebox.showinfo("PIN sheet", "Add the teachers first.", parent=self.win)
            return
        f = filedialog.asksaveasfilename(parent=self.win, defaultextension=".docx",
                                         initialfile=f"PIN sheet - {self.sch['name']}.docx",
                                         filetypes=[("Word document", "*.docx")])
        if not f:
            return
        pin_sheet.make(f, self.sch["name"], self.pub.school_link(self.code), self.people)
        self.app.run.log(f"🖨 PIN sheet saved: {f}")
        if self.sch.get("lock"):
            self.save()                                       # the service gets the PINs
        try:
            import os
            os.startfile(f)                                    # open it in Word to print
        except Exception:
            pass

    # ----------------------------------------------------------------------------------------------- saving / service
    def _ready_list(self):
        bad = [p.get("name") for p in self.people if not p.get("phone")]
        if bad:
            if not messagebox.askyesno("Teachers & phones", f"{len(bad)} teacher(s) have no phone number yet "
                                       f"({', '.join(bad[:4])}…). They cannot open the app until they have one.\n\n"
                                       "Save anyway?", parent=self.win):
                return False
        return True

    def _save_state(self, text, colour="#12284C", busy=False):
        try:
            self.save_lbl.configure(text=text, fg=colour)
            if busy:
                self.save_bar.pack(side="right", padx=4)
                self.save_bar.start(12)
            else:
                self.save_bar.stop()
                self.save_bar.pack_forget()
        except tk.TclError:
            pass                                          # the window was closed meanwhile

    def save(self, after=None):
        """Save the list; the window itself shows the progress and whether it went through."""
        if not self._ready_list():
            return
        self.pub.set_phones(self.code, self.people)
        self.people = self.pub.phones(self.code)
        self.dirty = False
        n = sum(1 for p in self.people if p.get("phone"))
        self.refresh()
        if not self.sch.get("lock"):
            self.pub.autosave()
            self._save_state(f"✔ Saved on this computer ({n} teachers).", "#176548")
            self.app.run.log(f"✔ Teachers' list saved for {self.sch['name']}.")
            if after:
                after()
            return
        self._save_state(f"⏳ Sending the list of {n} teachers… please wait", busy=True)
        ui = self.app.run.ui

        def work():
            try:
                self.pub.send_roster(self.code)
                if self.pub.is_school and self.pub.relay and self.pub.timetables(self.code):
                    ui(lambda: self._save_state("⏳ List sent. Locking the timetables to these teachers…", busy=True))
                    self.pub.publish_lock_state(self.code)   # only these teachers can open the timetables now
                self.pub.autosave()
            except Exception as e:
                msg = core_text(e)
                ui(lambda: (self._save_state("✖ NOT saved: " + msg + "  Check the internet and press Save again.",
                                             "#B5463A"),
                            self.app.run.log("✖ Teachers' list not sent: " + msg)))
                return
            ui(lambda: (self._save_state(f"✔ Done — {n} teachers saved. Only they can open the timetables on their "
                                         "phones.", "#176548"),
                        self.app.run.log(f"✔ Teachers' list saved for {self.sch['name']} ({n} teachers).")))
            if after:
                ui(after)
        threading.Thread(target=work, daemon=True).start()

    def toggle_lock(self):
        on = not self.sch.get("lock")
        if on and not (self.pub.s.get("push_url") and self.pub.owner_key()):
            messagebox.showinfo("Lock this school", "First, on the Setup tab: the PREPFIX service link (Lesson reminders "
                                "service) and your owner key. See SETUP GUIDE.html, Part E.", parent=self.win)
            return
        if on and not messagebox.askyesno("Lock this school", f"Lock {self.sch['name']}?\n\nFrom now on only the "
                                          "teachers on this list can open its timetables, each on one phone. Teachers "
                                          "type their number once on their phone.", parent=self.win):
            return
        if not on and not messagebox.askyesno("Unlock this school", "Unlock? Anybody with the school's link can then "
                                              "open its timetables again.", parent=self.win):
            return
        if not self._ready_list():
            return
        self.pub.set_phones(self.code, self.people)

        def go():
            self.pub.set_lock(self.code, on)
            self.app.run.log(("🔒 Locked: " if on else "🔓 Unlocked: ") + self.sch["name"])

        def done():
            self.sch = self.pub.school(self.code)
            self.refresh()
            self.app.fill_schools_local()
        self.app.run.run(go, after=done)

    def rekey(self):
        if not self.sch.get("lock"):
            return
        if not messagebox.askyesno("New key", "Give the school a NEW key? Every phone must type its number again "
                                   "(use this after a teacher left, so their old phone stops getting new timetables).",
                                   parent=self.win):
            return
        self.pub.set_phones(self.code, self.people)
        self.app.run.run(lambda: self.pub.set_lock(self.code, True, rekey=True), after=self.refresh)

    def free(self):
        s = self.sel()
        if not s:
            messagebox.showinfo("Remove sign-in", "Click the teacher first.", parent=self.win)
            return
        p = self.people[s[0]]
        if not p.get("phone") or not self.sch.get("lock"):
            return
        if not messagebox.askyesno("Remove sign-in", f"Remove the sign-in of {p.get('name')}'s number? The phone using "
                                   "it now is signed out, and the rightful teacher can sign in (number + a new PIN).",
                                   parent=self.win):
            return

        def go():
            self.pub.free_signin(self.code, [LOCK.phone_hash(self.code, p["phone"])])
            self.app.run.log(f"✔ {p.get('name')}'s number sign-in was removed: the rightful teacher can now sign in.")
        self.app.run.run(go, after=self.check)

    def check(self):
        if not self.sch.get("lock"):
            messagebox.showinfo("Who has the app?", "Lock the school first.", parent=self.win)
            return
        box = {}

        def go():
            box["st"] = self.pub.roster_status(self.code)

        def done():
            self.status = box.get("st") or {}
            self.refresh()
        self.app.run.run(go, after=done)

    def close(self):
        if self.dirty and messagebox.askyesno("Teachers & phones", "Save the changes to the list?", parent=self.win):
            self.save(after=lambda: self.win.destroy())
            return
        self.win.destroy()


class SchoolList:
    """Cyrus's view of a school whose OWN copy keeps the teachers' list: who is on it, who signed in, and the controls
    that stay with Cyrus (remove a sign-in, lock / unlock, new key). The list itself is typed in the school's copy."""

    def __init__(self, app, code):
        self.app, self.pub, self.code = app, app.pub, code
        self.sch = self.pub.school(code)
        self.rows = []
        w = self.win = tk.Toplevel(app.root)
        w.title(f"PREPFIX — Teachers & phones — {self.sch['name']}")
        w.geometry("900x560")
        w.configure(bg=U.CREAM)
        top = ttk.Frame(w, style="Card.TFrame", padding=(14, 10))
        top.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(top, text=f"Teachers & phones — {self.sch['name']}", style="H.TLabel").pack(anchor="w")
        self.state_lbl = tk.Label(top, text="", bg="white", font=("Segoe UI Semibold", 11), wraplength=850,
                                  justify="left")
        self.state_lbl.pack(anchor="w", pady=(4, 2))
        ttk.Label(top, style="CardMuted.TLabel", wraplength=850, justify="left",
                  text="This school types its own teachers in its PREPFIX copy (👥 Teachers & phones). Here you see "
                       "the list as it is on the service — names and sign-ins, never the numbers — and you can remove "
                       "a sign-in, lock or unlock the school, or give it a new key."
                  ).pack(anchor="w")
        bar = ttk.Frame(w, style="Card.TFrame", padding=(14, 8))
        bar.pack(fill="x", padx=10, pady=(6, 0))
        ttk.Button(bar, text="↻ Refresh", command=self.load).pack(side="left")
        ttk.Button(bar, text="🔓 Remove sign-in", command=self.free).pack(side="left", padx=6)
        ttk.Button(bar, text="I will keep this school's list myself…", command=self.take_over).pack(side="right")
        mid = ttk.Frame(w)
        mid.pack(fill="both", expand=True, padx=10, pady=6)
        cols = ("name", "app")
        self.tv = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        for c, t_, wd in (("name", "Teacher", 380), ("app", "Signed in on", 380)):
            self.tv.heading(c, text=t_)
            self.tv.column(c, width=wd, anchor="w")
        self.tv.pack(fill="both", expand=True)
        bot = ttk.Frame(w, style="Card.TFrame", padding=(14, 10))
        bot.pack(fill="x", side="bottom")
        self.lock_btn = ttk.Button(bot, text="", style="Accent.TButton", command=self.toggle_lock)
        self.lock_btn.pack(side="right")
        ttk.Button(bot, text="🔁 New key (every phone signs in again)", command=self.rekey).pack(side="left")
        ttk.Button(bot, text="Close", command=w.destroy).pack(side="left", padx=8)
        self.show()
        app.front(w)
        self.load()

    def show(self):
        locked = bool(self.sch.get("lock"))
        joined = sum(1 for r in self.rows if r.get("joined"))
        self.state_lbl.configure(text=(f"🔒 LOCKED — {len(self.rows)} teacher(s) on the school's list, {joined} signed in."
                                       if locked else "🔓 NOT LOCKED — anybody with the school's link can open the "
                                       "timetables."), fg="#176548" if locked else "#8A6100")
        self.lock_btn.configure(text="🔓 Unlock this school" if locked else "🔒 Lock this school")
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(self.rows):
            self.tv.insert("", "end", iid=str(i), values=(r.get("name") or "?", (
                "✔ " + {"and": "Android", "ios": "iPhone", "pc": "computer"}.get(r.get("plat"), "phone")
                + (f" · last used {_ago(r.get('last'))}" if r.get("last") else "")) if r.get("joined") else "— not yet"))

    def load(self):
        box = {}

        def go():
            box["rows"] = self.pub.roster_people(self.code)

        def done():
            self.rows = sorted(box.get("rows") or [], key=lambda r: (r.get("name") or "").upper())
            self.show()
        self.app.run.run(go, after=done)

    def free(self):
        if hasattr(self.app, "need_pw") and not self.app.need_pw("Remove a teacher's sign-in."):
            return
        s = [int(i) for i in self.tv.selection()]
        if not s:
            messagebox.showinfo("Remove sign-in", "Click the teacher first.", parent=self.win)
            return
        r = self.rows[s[0]]
        if not messagebox.askyesno("Remove sign-in", f"Remove the sign-in of {r.get('name')}? The phone using it is "
                                   "signed out, and the rightful teacher signs in again (number + a new PIN).",
                                   parent=self.win):
            return
        self.app.run.run(lambda: self.pub.free_signin(self.code, [r["ph"]]), after=self.load)

    def toggle_lock(self):
        if hasattr(self.app, "need_pw") and not self.app.need_pw("Lock or unlock a school."):
            return
        on = not self.sch.get("lock")
        if not messagebox.askyesno("Lock" if on else "Unlock", ("Lock" if on else "Unlock") + f" {self.sch['name']}?"
                                   + ("" if on else "\n\nAnybody with the school's link can then open its timetables, "
                                      "and the school's teachers' list on the service is cleared."), parent=self.win):
            return

        def go():
            if on:                                         # the school's copy sends its list again with Save
                mine = list(self.pub.s.get("schools", []))
                keys = dict(self.pub.s.get("lock_keys", {}) or {})
                keys.setdefault(self.code, LOCK.new_key())
                self.pub.s.set("lock_keys", keys)
                for x in mine:
                    if x["code"] == self.code:
                        x["lock"] = True
                self.pub.s.set("schools", mine)
                self.pub.make_school_copy(self.code)
                self.pub.autosave()
            else:
                self.pub.set_lock(self.code, False)

        def done():
            self.sch = self.pub.school(self.code)
            self.show()
            self.app.fill_schools_local()
            if on:
                messagebox.showinfo("Lock", "Locked. Send the school its new copy (FOR_SCHOOLS folder); they add "
                                    "their teachers and press Save.", parent=self.win)
        self.app.run.run(go, after=done)

    def rekey(self):
        if hasattr(self.app, "need_pw") and not self.app.need_pw("Give a school a new key."):
            return
        if not self.sch.get("lock") or not messagebox.askyesno(
                "New key", "Give the school a NEW key? Every phone signs in again, and the school needs its new copy "
                "(FOR_SCHOOLS folder).", parent=self.win):
            return

        def go():
            keys = dict(self.pub.s.get("lock_keys", {}) or {})
            keys[self.code] = LOCK.new_key()
            self.pub.s.set("lock_keys", keys)
            people = self.pub.roster_people(self.code)
            self.pub._service("/roster", {"school": self.code, "name": self.sch["name"], "lockkey": keys[self.code],
                                          "people": [{"ph": r["ph"], "name": r.get("name", "")} for r in people],
                                          "free": [r["ph"] for r in people]})
            self.pub.make_school_copy(self.code)
            self.pub.autosave()
        self.app.run.run(go, after=self.load)

    def take_over(self):
        if hasattr(self.app, "need_pw") and not self.app.need_pw("Take over a school's teachers' list."):
            return
        if not messagebox.askyesno("Keep the list yourself", f"From now on YOU type {self.sch['name']}'s teachers and "
                                   "phone numbers here, and the school's copy can no longer change the list (send the "
                                   "school its new copy from FOR_SCHOOLS).\n\nContinue?", parent=self.win):
            return
        mine = list(self.pub.s.get("schools", []))
        for x in mine:
            if x["code"] == self.code:
                x["teachers_by"] = "owner"
        self.pub.s.set("schools", mine)
        self.win.destroy()

        def go():
            self.pub.make_school_copy(self.code)
            self.pub.autosave()
        self.app.run.run(go, after=lambda: Phones(self.app, self.code))
