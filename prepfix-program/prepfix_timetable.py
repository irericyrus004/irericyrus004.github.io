"""
PREPFIX Timetable Toolkit V1.
Choose the school, name the timetable, add the FET folder, press Publish.
Run with: Start PREPFIX.bat
"""
import os
import threading
import re
import webbrowser
from datetime import datetime
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog

import prepfix_core as core
import fet_reader
import asc_pdf
import notes_file
import notes_word
import constraints as K
import constraints_ui as CU
import move_ui as MV
import prepfix_ui as U
import checks as CH
import autofix as AF
import transfer_ui as TU
import time
import preview_server as PS
import fet_rules as FR
import my_rules_ui as MR
import phones_ui as PH

TOKEN_URL = "https://github.com/settings/tokens/new?scopes=public_repo&description=PREPFIX+Timetable+Toolkit"
EXAMPLES = ""


# rule types the teachers' app (phones) can check itself
PHONE_RULES = {"teacher_clash", "class_clash", "room_clash", "break_lessons", "teacher_max_day", "teacher_max_week",
               "teacher_max_consec", "teacher_unavailable", "subject_max_day", "subject_periods"}


def when(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso or "—"


class App:
    def __init__(self, root):
        self.root = root
        root.title(core.PRODUCT_NAME + " " + core.PRODUCT_VERSION)
        root.geometry("1040x860")
        root.minsize(900, 680)
        try:                                               # opens full screen (maximised, taskbar still visible)
            if root.state() != "withdrawn":                # behind the opening screen: maximised when it closes
                root.state("zoomed")
        except tk.TclError:
            try:
                root.attributes("-zoomed", True)
            except tk.TclError:
                pass
        root.configure(bg=U.CREAM)
        U.set_icon(root)
        U.style(root)
        self.head_right = U.header(root, "")
        self.logbox, self.prog = U.bottom_log(root)
        self.run = U.Runner(root, self.logbox, self.prog)
        self.pub = core.Publisher(log=self.run.log)
        if True:                                 # nothing on screen names the tools behind PREPFIX (GitHub…)
            _log = self.run.log
            self.run.log = lambda m, *a, **k: _log(core.public_text(m, self.pub.is_school), *a, **k)
            self.pub.log = self.run.log
            for _n in ("showinfo", "showerror", "showwarning", "askyesno", "askokcancel", "askyesnocancel"):
                _f = getattr(messagebox, _n)
                setattr(messagebox, _n, (lambda f: lambda title="", message="", *a, **k:
                                         f(core.public_text(title, self.pub.is_school), core.public_text(message, self.pub.is_school), *a, **k))(_f))
        self.data = None
        self.orig_data = None
        self._reviewed = None
        self.folder = None
        self.ran = False
        self.applied_con = False                 # were the rules applied the last time Run was pressed?
        self.use_con = tk.BooleanVar(value=False)   # (old switch - the rules in operation are now always kept)
        self.rules_op, self.ops_src, self.ops_notes = [], "", []   # RULES IN OPERATION (from FET): kept on every move
        self._ops_cache = (None, None)
        try:
            core.check_brand_files()
        except core.PublishError as e:
            messagebox.showerror("PREPFIX", str(e))
            root.destroy()
            return

        if not self.owner_login():                   # Cyrus's PREPFIX and every school's copy open with a password
            root.destroy()
            return
        sp = getattr(root, "_splash", None)
        if sp is not None and sp.ok and getattr(sp, "w", None) is not None:
            try:
                sp.w.deiconify()                         # signed in: the opening screen again while PREPFIX loads
            except tk.TclError:
                pass

        self.sub_bar = None
        if self.pub.is_school:                   # always in sight: how long the subscription still runs
            self.sub_bar = tk.Label(root, text="", anchor="w", font=("Segoe UI Semibold", 10), padx=14, pady=5)
            self.sub_bar.pack(fill="x", side="top")
            try:
                u, dl, _, susp = self.pub.my_subscription(online=False)
                self.show_sub(u, dl)
            except Exception:
                pass
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        self.nb = nb
        self.tab_imp = ttk.Frame(nb, padding=(0, 10, 0, 0))
        self.tab_pub = ttk.Frame(nb, padding=(0, 10, 0, 0))
        self.tab_sch = ttk.Frame(nb, padding=(0, 10, 0, 0))
        self.tab_set = ttk.Frame(nb, padding=(0, 10, 0, 0))
        # Four tabs, in the order the work is done. Rules and moving lessons are steps of the paths on
        # "Import & Run" and open in their own windows, so they are not tabs any more.
        tabs = [(self.tab_set, "Setup (once)")] + ([] if self.pub.is_school else [(self.tab_sch, "Schools")]) + \
               [(self.tab_imp, "Import & Run"), (self.tab_pub, "Publish")]
        for i, (t, name) in enumerate(tabs, 1):
            nb.add(t, text=f"  {i} · {name}  ")
        # the RULES window: 1. the rules in operation (read from FET; kept on every move)  2. extra checks (optional)
        self.rules_win = tk.Toplevel(root)
        self.rules_win.title("PREPFIX — Rules")
        self.rules_win.geometry("1000x700")
        self.rules_win.configure(bg=U.CREAM)
        self.rules_win.withdraw()
        self.rules_win.protocol("WM_DELETE_WINDOW", self.rules_win.withdraw)
        rb = ttk.Frame(self.rules_win, style="Card.TFrame", padding=(14, 8))
        rb.pack(fill="x", side="bottom")
        ttk.Button(rb, text="Close", style="Accent.TButton", command=self.rules_win.withdraw).pack(side="right")
        op = ttk.Frame(self.rules_win, style="Card.TFrame", padding=(14, 10))
        op.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(op, text="1.  Rules in operation — kept on every move", style="H.TLabel").pack(anchor="w")
        ttk.Label(op, style="CardMuted.TLabel", wraplength=940, justify="left",
                  text="The rules the timetable was made with. PREPFIX reads them by itself from the FET folder (the "
                       "*_data_and_timetable.fet file). Or paste them: open the .fet file with Notepad, Ctrl+A, Ctrl+C, "
                       "then “Paste rules”. A rule set at 100 % in FET is never broken by a move.").pack(anchor="w")
        self.ops_lbl = tk.Label(op, text="", bg="white", fg=U.NAVY, font=("Segoe UI Semibold", 10), wraplength=940,
                                justify="left")
        self.ops_lbl.pack(anchor="w", pady=(6, 4))
        ob = ttk.Frame(op, style="Card.TFrame")
        ob.pack(fill="x")
        ttk.Button(ob, text="📋  Paste rules…", style="Gold.TButton", command=self.paste_ops).pack(side="left")
        ttk.Button(ob, text="📂  Read a .fet file…", command=self.read_ops_file).pack(side="left", padx=6)
        ttk.Button(ob, text="✔  Check the timetable with them", command=self.check_ops).pack(side="left")
        ttk.Button(ob, text="List them…", command=self.list_ops).pack(side="left", padx=6)
        ttk.Button(ob, text="Remove", command=self.clear_ops).pack(side="right")
        ttk.Label(self.rules_win, text="   2.  Extra checks (optional) — rules that may have been left out",
                  style="H.TLabel", background=U.CREAM).pack(anchor="w", padx=10, pady=(10, 0))
        self.tab_con = ttk.Frame(self.rules_win)
        self.tab_con.pack(fill="both", expand=True, padx=10, pady=(2, 6))
        self.tab_move = ttk.Frame(self.rules_win)          # the Move lessons starting page is no longer shown:
                                                           # moving opens straight into its full screen
        self.build_setup()
        self.build_publish()
        self.con = CU.ConstraintsTab(self, self.tab_con)
        self.move = MV.MoveTab(self, self.tab_move)
        self.my = MR.MyRules(self)                         # MY RULES: written in my own words, run when I want
        threading.Thread(target=PS.tidy_old_profiles, daemon=True).start()   # the preview browser kept small
        self.build_schools()
        nb.bind("<<NotebookTabChanged>>", lambda e: self.on_tab())
        self.refresh_header()
        nb.select(self.tab_imp if (self.pub.ready or self.pub.is_school) else self.tab_set)
        if self.pub.is_school:                       # the school's PREPFIX updates itself from Cyrus Ireri's website
            threading.Thread(target=self._self_update, daemon=True).start()
            try:                                         # suspended / ended (as this computer last knew): closed at once
                u, dl, _, susp = self.pub.my_subscription(online=False)
                if susp or (dl is not None and dl < 0):
                    self.lock_closed(u, susp)
            except Exception:
                pass
            threading.Thread(target=self._sub_check, daemon=True).start()
        if not self.pub.ready and self.pub.is_school:
            self.run.log(f"Welcome, {self.pub.bound_school['name']}. Import & Run: add a timetable, check it, fix it, "
                         "preview and print — all on this computer.")
        elif not self.pub.ready:
            self.run.log("Welcome. Do the one-time Setup first. See SETUP GUIDE.html.")
        else:
            self.run.log("Ready. On “Import & Run”: add the ready timetable (FET folder or aSc PDF) → notes → Preview → Publish.")
            if not self.pub.is_school:
                self.run.run(self.bg_sync_register, quiet=True)
            else:                                    # school copy: bring the newest teachers' app to the school's site
                def school_start():
                    if self.pub.sync_app_update():
                        self.run.log("✔ Teachers' app updated to the newest PREPFIX.")
                    ok = self.pub.mobile_allowed_here()           # has Cyrus Ireri switched the mobile app on?
                    self._mobile_here = ok
                    try:
                        if self.pub.sheet_backup_all():              # this school's timetables kept in the Google Sheet
                            self.run.log("☁ Backup done.")
                    except Exception:
                        pass

                    def show():
                        self.school_changed()
                        self.update_pub_state()
                        if ok is False:
                            self.run.log("🖥 This school uses PREPFIX on this computer (preview and print). The mobile "
                                         "app for teachers' phones is not switched on — contact Cyrus Ireri, "
                                         + core.LOCKED_CONTACT + ".")
                    self.run.ui(show)
                self.run.run(school_start, quiet=True)
        self.root.after(50, self.apply_edition)

    # ------------------------------------------------------------------ Publish tab
    def scrollable(self, outer):
        """A frame inside `outer` that scrolls up / down (mouse wheel or the bar) when it is taller than the window,
        so nothing is ever cut off on a small screen (e.g. a 1366 x 768 laptop)."""
        cv = tk.Canvas(outer, bg=U.CREAM, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        inner = ttk.Frame(cv)
        win = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)

        def resize(e=None):
            cv.itemconfigure(win, width=cv.winfo_width())
            need = inner.winfo_reqheight()
            cv.itemconfigure(win, height=max(need, cv.winfo_height()))
            cv.configure(scrollregion=(0, 0, cv.winfo_width(), max(need, cv.winfo_height())))
            if need > cv.winfo_height() + 2:
                if not sb.winfo_ismapped():
                    sb.pack(side="right", fill="y")
            elif sb.winfo_ismapped():
                sb.pack_forget()
                cv.yview_moveto(0)
        cv.bind("<Configure>", resize)
        inner.bind("<Configure>", resize)
        cv.pack(side="left", fill="both", expand=True)

        def wheel(e):
            if sb.winfo_ismapped():
                cv.yview_scroll(int(-e.delta / 120) if e.delta else (-1 if e.num == 4 else 1), "units")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            inner.bind_all(seq, lambda e: wheel(e) if str(self.nb.select()) == str(outer) else None, add="+")
        return inner

    def build_publish(self):
        f = self.scrollable(self.tab_imp)                    # Import & Run: scrolls when the screen is small
        g = self.tab_pub                                     # tab 4: Timetable name, link, Publish
        top = ttk.Frame(f, style="Card.TFrame", padding=14)
        top.pack(fill="x")
        r = ttk.Frame(top, style="Card.TFrame")
        r.pack(fill="x")
        ttk.Label(r, text="School:", style="H.TLabel", width=11).pack(side="left")
        self.school_var = tk.StringVar()
        self.school_box = ttk.Combobox(r, textvariable=self.school_var, state="readonly", width=40,
                                       font=("Segoe UI", 11))
        self.school_box.pack(side="left", padx=8)
        self.school_box.bind("<<ComboboxSelected>>", lambda e: self.school_changed())
        self.btn_reg = ttk.Button(r, text="+ Register my school (once only)…" if self.pub.is_school
                                  else "+ Register a school…", command=self.new_school)
        if self.pub.is_school:                               # the owner registers schools on the Schools tab
            self.btn_reg.pack(side="left")
        ttk.Label(r, text="(recognised by itself from the FET folder or aSc PDF)", style="CardMuted.TLabel").pack(side="left", padx=6)

        top2 = ttk.Frame(g, style="Card.TFrame", padding=14)
        top2.pack(fill="x")
        r1 = ttk.Frame(top2, style="Card.TFrame")
        r1.pack(fill="x", pady=(10, 0))
        ttk.Label(r1, text="Timetable:", style="H.TLabel", width=11).pack(side="left")
        self.tt_var = tk.StringVar()
        self.tt_box = ttk.Combobox(r1, textvariable=self.tt_var, width=40, font=("Segoe UI", 11))
        self.tt_box.pack(side="left", padx=8)
        self.tt_var.trace_add("write", lambda *a: self.tt_changed(typed=not getattr(self, "_auto_tt", False)))
        self.tt_box.bind("<<ComboboxSelected>>", lambda e: self.warn_replace(now=True))
        self.tt_state = ttk.Label(r1, text="", style="CardMuted.TLabel")
        self.tt_state.pack(side="left", padx=4)
        ttk.Label(top2, text="Type a new name to ADD a timetable, or pick an existing name to REPLACE it.",
                  style="CardMuted.TLabel", wraplength=960).pack(anchor="w", pady=(4, 0))

        r2 = ttk.Frame(top2, style="Card.TFrame")
        r2.pack(fill="x", pady=(10, 0))
        ttk.Label(r2, text="Teachers' link:", style="Card.TLabel", width=14).pack(side="left")
        self.link_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.link_var, state="readonly", width=52).pack(side="left", padx=8)
        ttk.Button(r2, text="Copy", command=self.copy_link).pack(side="left")
        ttk.Button(r2, text="Open", command=lambda: self.open_link("")).pack(side="left", padx=4)
        ttk.Button(r2, text="QR poster", command=lambda: self.open_link("?poster=1")).pack(side="left")
        if self.pub.is_school:                        # a school copy has no Schools tab: its teachers' list is here
            ttk.Button(r2, text="👥  Teachers & phones…", style="Accent.TButton",
                       command=self.open_phones).pack(side="left", padx=(14, 0))

        s2 = ttk.Frame(g, style="Card.TFrame", padding=14)
        s2.pack(fill="x", pady=(10, 0))
        s1 = ttk.Frame(f, style="Card.TFrame", padding=14)
        s1.pack(fill="both", expand=True, pady=(10, 0))
        t = ttk.Frame(s1, style="Card.TFrame")
        t.pack(fill="x")
        ttk.Label(t, text="1.  Add the timetable",
                  style="H.TLabel").pack(side="left")
        ttk.Button(t, text="📁  FET folder", style="Gold.TButton", command=self.add_folder).pack(side="right")
        ttk.Button(t, text="📄  aSc PDF", style="Gold.TButton", command=self.import_sheet
                   ).pack(side="right", padx=6)
        self.folder_lbl = ttk.Label(s1, text="A ready timetable, as it is: the folder FET created, or from aSc Timetables "
                                             "its PDF printouts (the class and the teacher timetables - pick both PDFs "
                                             "together). PREPFIX never changes it.",
                                    style="CardMuted.TLabel")
        self.folder_lbl.pack(anchor="w", pady=(4, 2))
        nmr = ttk.Frame(s1, style="Card.TFrame")                     # the timetable's name - typed here, at once
        nmr.pack(fill="x", pady=(4, 2))
        ttk.Label(nmr, text="Timetable name:", style="H.TLabel").pack(side="left")
        self.tt_box2 = ttk.Combobox(nmr, textvariable=self.tt_var, width=34, font=("Segoe UI", 11))
        self.tt_box2.pack(side="left", padx=8)
        self.tt_box2.bind("<<ComboboxSelected>>", lambda e: self.warn_replace(now=True))
        self.tt_state2 = ttk.Label(nmr, text="", style="CardMuted.TLabel")
        self.tt_state2.pack(side="left", padx=4)
        ttk.Label(s1, text="Type a NEW name to add this timetable (e.g. TERM 1 2027, END TERM EXAM), or pick a published "
                           "name to REPLACE it. Published timetables can be deleted on the Publish tab.",
                  style="CardMuted.TLabel", wraplength=900).pack(anchor="w")
        rr = ttk.Frame(s1, style="Card.TFrame")                      # the classic Run (kept; the paths below use it)
        self.btn_run = ttk.Button(rr, text="▶  Run", style="Accent.TButton", command=lambda: self.run_once(False),
                                  state="disabled")
        # ---- after the folder is read: choose a path
        nrow = ttk.Frame(s1, style="Card.TFrame")                   # notes come BEFORE the paths
        nrow.pack(fill="x", pady=(4, 2))
        ttk.Label(nrow, text="Notes under the timetables (optional):", style="H.TLabel").pack(side="left")
        self.notes_count = ttk.Label(nrow, text="", style="CardMuted.TLabel")
        self.notes_count.pack(side="left", padx=8)
        ttk.Button(nrow, text="📌  Add / edit notes…", command=self.open_notes).pack(side="right")
        pf = ttk.Frame(s1, style="Card.TFrame")
        pf.pack(fill="x", pady=(2, 6))
        ck = ttk.Frame(pf, style="Card.TFrame")
        self.check_line = ttk.Label(ck, text="Check: load a timetable first.", style="CardMuted.TLabel",
                                    wraplength=760, justify="left")
        self.check_line.pack(side="left")
        self.btn_fullcheck = ttk.Button(ck, text="🔎  Run full check", command=self.show_check_report, state="disabled")
        self.btn_fullcheck.pack(side="right")
        ttk.Label(pf, text="2.  Fine-tune and publish", style="H.TLabel").pack(anchor="w", pady=(4, 4))
        self.path_mark = {}
        self.path = "B"
        row = ttk.Frame(pf, style="Card.TFrame")
        row.pack(fill="x")
        self.steps = []
        for txt, cmd in (("👁  Preview", lambda: self.browser_preview(True)),
                         ("🚀  Publish", self.goto_pub_tab)):
            b = ttk.Button(row, text=txt, command=lambda c=cmd: self.step(c),
                           style="Accent.TButton" if txt.endswith("Publish") else "TButton")
            b.pack(side="left", padx=(0, 4))
            self.steps.append(b)
        self.rules_state = tk.Label(pf, text="", bg="white", fg="#7A5A00", font=("Segoe UI", 9), wraplength=920,
                                    justify="left")
        ttk.Label(pf, style="CardMuted.TLabel", wraplength=920, justify="left",
                  text="The timetable comes in exactly as FET or aSc made it, and PREPFIX never changes it: it only "
                       "makes it look good, prints it and sends it to teachers' phones. To change a lesson, change it in "
                       "FET or aSc and add the timetable again."
                  ).pack(anchor="w", pady=(6, 0))
        self.pv = PS.PreviewServer()
        self.check_lbl = ttk.Label(s1, text="", style="Card.TLabel", wraplength=900, justify="left")
        self.check_lbl.pack(anchor="w")
        self.summary = tk.Text(s1, height=4 if self.root.winfo_screenheight() < 900 else 8, relief="flat", bg="#FBF8EF", font=("Segoe UI", 10), wrap="word",
                               padx=10, pady=8)
        self.summary.pack(fill="both", expand=True, pady=(6, 0))
        self.set_summary("Nothing loaded yet.")

        ttk.Label(s2, text="Publish to teachers' phones", style="H.TLabel").pack(anchor="w")
        self.pub_status = ttk.Label(s2, text="", style="CardMuted.TLabel", wraplength=900, justify="left")
        self.pub_status.pack(anchor="w", pady=(2, 0))
        n = ttk.Frame(s2, style="Card.TFrame")
        n.pack(fill="x", pady=(6, 0))
        ttk.Label(n, text="Message to teachers (optional):", style="Card.TLabel").pack(side="left")
        self.note_var = tk.StringVar()
        ttk.Entry(n, textvariable=self.note_var).pack(side="left", fill="x", expand=True, padx=8)
        b = ttk.Frame(s2, style="Card.TFrame")
        b.pack(fill="x", pady=(10, 0))
        pass
        ttk.Button(b, text="👁  Final preview: before / after (affected teachers)",
                   command=lambda: self.review_changes(False)).pack(side="left")
        self.btn_pub = ttk.Button(b, text="🚀  Publish", style="Accent.TButton", command=self.publish, state="disabled")
        self.btn_pub.pack(side="right")
        ttk.Button(b, text="↶  Undo last publish of this timetable", command=self.undo).pack(side="right", padx=8)
        ttk.Button(b, text=("☁  Restore an earlier version…" if self.pub.is_school else "☁  Restore from Google Sheet…"), command=self.sheet_restore).pack(side="right")

        s4 = ttk.Frame(g, style="Card.TFrame", padding=14)             # what is on teachers' phones now - delete
        s4.pack(fill="both", expand=True, pady=(10, 0))
        h4 = ttk.Frame(s4, style="Card.TFrame")
        h4.pack(fill="x")
        ttk.Label(h4, text="Published timetables of this school (on teachers' phones now)", style="H.TLabel").pack(side="left")
        ttk.Button(h4, text="🗑  Delete selected…", command=self.delete_timetable).pack(side="right")
        self.pub_tree = ttk.Treeview(s4, columns=("name", "updated", "times", "size"), show="headings", height=5,
                                     selectmode="browse")
        for c, t, w in (("name", "Timetable", 260), ("updated", "Last published", 170), ("times", "Times published", 120),
                        ("size", "Teachers · Classes", 150)):
            self.pub_tree.heading(c, text=t)
            self.pub_tree.column(c, width=w, anchor="w")
        self.pub_tree.pack(fill="both", expand=True, pady=(6, 0))
        ttk.Label(s4, text="Delete removes the timetable from the website and from teachers' phones. The school's other "
                           "timetables stay. A copy stays on this computer.", style="CardMuted.TLabel",
                  wraplength=900).pack(anchor="w", pady=(4, 0))

        # ---- NOTES under the timetables: paste or type, choose who it is for (own window, opened from Import & Run
        #      BEFORE the paths, so the previews of A and B already show them and they can be checked)
        self.notes_win = tk.Toplevel(self.root)
        self.notes_win.title("PREPFIX — Notes under the timetables")
        self.notes_win.geometry("1000x620")
        self.notes_win.configure(bg=U.CREAM)
        self.notes_win.withdraw()
        self.notes_win.protocol("WM_DELETE_WINDOW", self.close_notes)
        nb_ = ttk.Frame(self.notes_win, style="Card.TFrame", padding=(14, 10))
        nb_.pack(fill="x", side="bottom")
        ttk.Button(nb_, text="Done", style="Accent.TButton", command=self.close_notes).pack(side="right")
        ttk.Button(nb_, text="👁  Preview with the notes", command=lambda: (self.close_notes(), self.browser_preview(
            True, start="classes"))).pack(side="right", padx=8)
        s3 = ttk.Frame(self.notes_win, style="Card.TFrame", padding=14)
        s3.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        ttk.Label(s3, text="📌  Notes under the timetables", style="H.TLabel").pack(anchor="w")
        ttk.Label(s3, style="CardMuted.TLabel", wraplength=900, justify="left",
                  text="Type or paste a note, choose who it is for and press “Add note”. It shows under that class's or "
                       "teacher's timetable on phones and on printed pages. Notes go out with the next Publish "
                       "(and show in the preview at once). They stay until you remove them.").pack(anchor="w", pady=(2, 6))
        nr = ttk.Frame(s3, style="Card.TFrame")
        nr.pack(fill="x")
        ttk.Label(nr, text="For:", style="Card.TLabel").pack(side="left")
        self.note_to = tk.StringVar(value="Auto — PREPFIX finds who it is for")
        self.note_to_box = ttk.Combobox(nr, textvariable=self.note_to, state="readonly", width=40,
                                        values=["Auto — PREPFIX finds who it is for", "Every class", "Every teacher"])
        self.note_to_box.pack(side="left", padx=8)
        ttk.Button(nr, text="＋  Add note", style="Gold.TButton", command=self.add_tt_note).pack(side="left")
        ttk.Button(nr, text="Remove selected", command=self.remove_tt_note).pack(side="left", padx=6)
        nr2 = ttk.Frame(s3, style="Card.TFrame")                    # many notes at once: a Word template
        nr2.pack(fill="x", pady=(6, 0))
        ttk.Label(nr2, text="Many notes?", style="Card.TLabel").pack(side="left")
        ttk.Button(nr2, text="⬇  Download notes template (Word)", command=self.notes_template).pack(side="left", padx=8)
        ttk.Button(nr2, text="📥  Import notes from file…", command=self.import_tt_notes).pack(side="left")
        ttk.Label(nr2, text="write “9N: …”, “All teachers: …” or just name the class — PREPFIX finds it",
                  style="CardMuted.TLabel").pack(side="left", padx=8)
        nb2 = ttk.Frame(s3, style="Card.TFrame")                    # the note (left) and the saved notes (right)
        nb2.pack(fill="both", expand=True, pady=(6, 0))
        self.note_text = tk.Text(nb2, height=5, width=44, relief="solid", bd=1, font=("Segoe UI", 10), wrap="word",
                                 padx=8, pady=6)
        self.note_text.pack(side="left", fill="both", expand=True)
        self.note_tree = ttk.Treeview(nb2, columns=("to", "text"), show="headings", height=5)
        self.note_tree.heading("to", text="For")
        self.note_tree.heading("text", text="Saved notes")
        self.note_tree.column("to", width=150, stretch=False)
        self.note_tree.column("text", width=330)
        self.note_tree.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.reload_schools()

    # ------------------------------------------------------------------ Schools tab
    def build_schools(self):
        f = ttk.Frame(self.tab_sch, style="Card.TFrame", padding=14)
        f.pack(fill="both", expand=True)
        head = ttk.Frame(f, style="Card.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="Registered schools", style="Big.TLabel").pack(side="left")
        self.sch_count = ttk.Label(head, text="", style="CardMuted.TLabel")
        self.sch_count.pack(side="left", padx=12)
        # V1: only what Cyrus himself does - schools publish and keep their teachers' lists in their own copies
        row = ttk.Frame(f, style="Card.TFrame")
        row.pack(fill="x", pady=(6, 6))
        ttk.Button(row, text="+ Register a school…", style="Accent.TButton", command=self.new_school).pack(side="left")
        ttk.Button(row, text="📂  Open FOR_SCHOOLS", command=self.open_for_schools).pack(side="left", padx=6)
        ttk.Button(row, text="📦  Update school copy", style="Gold.TButton", command=self.make_copy).pack(side="left")
        ttk.Button(row, text="Open school's app", command=self.open_selected_school).pack(side="left", padx=6)
        more = ttk.Menubutton(row, text="More…")
        mm = tk.Menu(more, tearoff=0)
        mm.add_command(label="🗑  Delete school…", command=self.delete_school)
        more["menu"] = mm
        more.pack(side="right")
        ttk.Button(row, text="▶  Restore", command=lambda: self.suspend_school(False)).pack(side="right", padx=6)
        ttk.Button(row, text="⏸  Suspend…", command=lambda: self.suspend_school(True)).pack(side="right")
        row2 = ttk.Frame(f, style="Card.TFrame")
        row2.pack(fill="x", pady=(0, 8))
        ttk.Button(row2, text="⬆  Send app improvements to phones", style="Accent.TButton", command=self.push_app).pack(side="left")
        ttk.Button(row2, text="🏫  Schools using FET…", command=self.edit_fet_schools).pack(side="left", padx=6)
        ttk.Button(row2, text="📱  Who has the app…", command=self.open_phones).pack(side="left")
        ttk.Button(row2, text="🔑  Password reset code…", command=self.show_reset_code).pack(side="left", padx=6)
        ttk.Button(row2, text="🔄  Renew 1 year…", command=self.renew_school).pack(side="left")

        cols = ("school", "registered", "paid", "status", "timetables", "last")
        self.sch_tree = ttk.Treeview(f, columns=cols, show="headings", height=9)
        for c, t, w in (("school", "School", 260), ("registered", "Registered", 120), ("paid", "Paid until (days left)", 180),
                        ("status", "Status", 100), ("timetables", "Timetables", 280), ("last", "Last published", 140)):
            self.sch_tree.heading(c, text=t)
            self.sch_tree.column(c, width=w, anchor="w")
        self.sch_tree.pack(fill="x")
        self.sch_tree.bind("<Double-1>", lambda e: self.goto_publish())

        ttk.Label(f, text="Activity — everything that happened, newest first", style="H.TLabel").pack(anchor="w", pady=(10, 2))
        self.act_tree = ttk.Treeview(f, columns=("when", "school", "tt", "what", "note"), show="headings", height=8)
        for c, t, w in (("when", "When", 150), ("school", "School", 250), ("tt", "Timetable", 190),
                        ("what", "What happened", 170), ("note", "Message to teachers", 200)):
            self.act_tree.heading(c, text=t)
            self.act_tree.column(c, width=w, anchor="w")
        self.act_tree.pack(fill="both", expand=True)
        self.sch_loaded = False

    def on_tab(self):
        if self.nb.select() != str(self.tab_move):
            self.move.want_open = False                    # a load started from "Move lessons" was abandoned
        if self.nb.select() == str(self.tab_con):
            self.con.refresh()
        if self.nb.select() == str(self.tab_move):
            self.move.refresh()
        if self.nb.select() == str(self.tab_sch):
            self.fill_schools_local()
            if self.pub.ready:
                if self.run.busy:                      # still busy starting up: try again in a moment, no pop-up
                    self.root.after(1200, self.on_tab)
                else:
                    self.load_schools()

    def fill_schools_local(self, activity=None):
        self.sch_tree.delete(*self.sch_tree.get_children())
        web = getattr(self, "web_meta", {}) or {}
        for s in self.pub.schools():
            tts = self.pub.timetables(s["code"])
            names = [t["name"] for t in tts]
            last = max((t.get("updated", "") for t in tts), default="")
            wm = web.get(s["code"]) or {}                  # what the school itself published (from the website)
            wt = wm.get("timetables") or []
            if wt and (wm.get("updated", "") >= last):
                names, last = [t.get("name", "") for t in wt], wm.get("updated", "") or last
            u = core.sub_until(s)
            dl = core.days_left(u)
            paid = "—" if dl is None else (f"ENDED {core.nice_day(u)}" if dl < 0 else f"{core.nice_day(u)}  ({dl} days)")
            tag = ("susp",) if s.get("suspended") or (dl is not None and dl < 0) else ("due",) if dl is not None and dl <= 30 else ()
            self.sch_tree.insert("", "end", iid=s["code"], tags=tag, values=(
                s["name"], when(s.get("registered", "")), paid, "⏸ Suspended" if s.get("suspended") else
                ("⛔ Not paid" if dl is not None and dl < 0 else "✔ Active"),
                ", ".join(names) or "— none yet —", when(last) if last else "—"))
        n = len(self.pub.schools())
        ns = sum(1 for s in self.pub.schools() if s.get("suspended"))
        self.sch_count.configure(text=f"{n} school{'s' if n != 1 else ''}" + (f" · {ns} suspended" if ns else ""))
        self.sch_tree.tag_configure("susp", foreground="#B5463A")
        self.sch_tree.tag_configure("due", foreground="#8A5A12")
        if activity is not None:
            self.act_tree.delete(*self.act_tree.get_children())
            for a in activity:
                self.act_tree.insert("", "end", values=(when(a.get("time", "")), a.get("name", ""), a.get("timetable", ""),
                                                        a.get("what", ""), a.get("note", "")))

    def load_schools(self):
        if not self.pub.ready:
            self.fill_schools_local()
            return

        def go():
            d = self.pub.remote_directory()
            self.pub._merge_register(d.get("register") or d.get("schools", []))
            if self.pub.refresh_school_sites():
                d = self.pub.remote_directory()
            wm = {}
            for sc in self.pub.schools():
                try:
                    m = self.pub.remote_json(f"s/{sc['code']}/meta.json")
                    if m:
                        wm[sc["code"]] = m
                except Exception:
                    pass
            self.web_meta = wm
            self.run.ui(lambda: (setattr(self, "sch_loaded", True), self.fill_schools_local(d.get("activity", [])),
                                 self.reload_schools()))
        self.run.run(go)

    def bg_sync_register(self):
        d = self.pub.remote_directory()
        added = self.pub._merge_register(d.get("register") or d.get("schools", []))
        if added:
            self.run.log(f"✔ {added} registered school(s) loaded from the website.")
        for name, on in (self.pub.adopt_web(d) if not self.pub.is_school else []):
            self.run.log(("🔄 " + name + " was renewed") if on == "renewed" else
                         (("⏸ " if on else "▶ ") + name + (" was suspended" if on else " was restored")) + " on your owner page.")
        locked = self.pub.ensure_locks()               # V1: every school is locked to the teachers it registers
        if locked:
            self.run.log(f"🔒 {locked} school(s) now open only for the teachers they register. Give them their "
                         "updated copy (FOR_SCHOOLS).")
        made = self.pub.ensure_school_copies()
        if made:
            self.run.log(f"✔ {made} school cop{'y' if made == 1 else 'ies'} made in FOR_SCHOOLS (one for every "
                         "registered school).")
            self.run.ui(self.fill_schools_local)
        self.run.ui(lambda: (self.reload_schools(), self.apply_edition()))
        self.pub.sheet_link_website()                    # quietly, at every start
        try:
            n = self.pub.sheet_backup_all()                   # timetables not yet in the Google Sheet go there now
            if n:
                self.run.log(f"☁ {n} timetable(s) saved in your Google Sheet (backup).")
        except Exception:
            pass

    def import_folder(self):
        d = filedialog.askdirectory(title="Choose your saved folder (the one with prepfix-setup.json and 'site', "
                                          "or an older 'timetable-site' folder)")
        if not d:
            return

        def go():
            res = self.pub.import_folder(d)

            def after():
                self.refresh_header()
                self.fill_schools_local()
                self.reload_schools()
                self.folder_var.set(self.pub.s.get("save_folder", ""))
                if self.pub.ready:
                    if res["schools"] and messagebox.askyesno(
                            "Imported", f"Imported {res['schools']} school(s) with all their timetables.\n\n"
                                        "Make sure the website has all of them too? (Nothing is deleted; a timetable "
                                        "with the same name is replaced.)"):
                        self.run.run(lambda: (self.pub.upload_everything(self.run.progress), self.pub.autosave(),
                                              self.run.log("✅ Website and saved folder are complete.")))
                    self.nb.select(self.tab_imp)
                else:
                    messagebox.showinfo("Almost there", f"Imported {res['schools']} school(s).\n\nThis folder has no "
                                        "set-up file yet. Do the 'Very first time' part below once (website key); "
                                        "after that, your saved folder will hold everything and setting up is just "
                                        "importing.")
            self.run.ui(after)
        self.run.run(go)

    def make_copy(self):
        if not self.pub.ready:
            messagebox.showinfo("Setup", "Finish the Setup first.")
            return
        code = self.selected_code()
        sch = self.pub.school(code) if code else None
        if not sch:
            messagebox.showinfo("School copy", "First click the school in the list above.")
            return
        extra = messagebox.askyesnocancel(
            "Update school copy", f"{sch['name']}\n\nThe school's copy in FOR_SCHOOLS is brought up to date with this "
            "version of PREPFIX.\n\nAlso save a copy straight to a flash disk?\n\nYes = choose the flash disk too\n"
            "No = FOR_SCHOOLS only")
        if extra is None:
            return
        d = filedialog.askdirectory(title="Choose the flash disk (or folder) for the school copy") if extra else ""

        def go():
            root = self.pub.make_school_copy(code, sch.get("github", ""))
            disk = self.pub.make_school_copy(code, sch.get("github", ""), d) if d else None
            self.run.ui(lambda: (self.fill_schools_local(), messagebox.showinfo(
                "School copy ready", f"{sch['name']}:\n{root}" + (f"\n\nAlso saved to:\n{disk}" if disk else "") +
                "\n\nGive this whole folder to the school. On their computer they double-click Start PREPFIX.bat, "
                "add their teachers and publish.")))
        self.run.run(go)

    def open_for_schools(self):
        core.FOR_SCHOOLS_DIR.mkdir(exist_ok=True)
        try:
            os.startfile(str(core.FOR_SCHOOLS_DIR))          # Windows: open the folder
        except Exception:
            webbrowser.open(core.FOR_SCHOOLS_DIR.as_uri())

    def rename_school(self):
        code = self.selected_code()
        sch = self.pub.school(code) if code else None
        if not sch:
            messagebox.showinfo("Rename", "First click the school in the list above.")
            return
        new = simpledialog.askstring("Rename school", f"New name for:\n{sch['name']}\n\nThe teachers' link stays the "
                                     "same; phones, posters and printed pages show the new name.",
                                     initialvalue=sch["name"], parent=self.root)
        new = core.clean_name(new or "")
        if not new or new.upper() == sch["name"]:
            return

        def go():
            nm = self.pub.rename_school(code, new)
            self.run.ui(lambda: (self.fill_schools_local(), self.reload_schools(select=nm), messagebox.showinfo(
                "Renamed", f"Now: {nm}\n\nThe website and its copy in FOR_SCHOOLS show the new name." +
                ("\n\nThis school publishes from its own computer: give it the updated folder from FOR_SCHOOLS."
                 if self.pub.own_account(self.pub.school(code)) else ""))))
        self.run.run(go)

    def edit_fet_schools(self):
        """Owner: the list of schools using FET, shown to teachers in the app. One school per line."""
        w = tk.Toplevel(self.root)
        w.title("Schools using FET Timetable Program")
        w.geometry("560x620")
        w.configure(bg=U.CREAM)
        ttk.Label(w, text="Schools using FET Timetable Program", style="H.TLabel", background=U.CREAM).pack(anchor="w", padx=14, pady=(12, 0))
        ttk.Label(w, text="One school per line. Teachers see this list in the app (menu → Schools using FET). "
                          "Save, then send it to phones.", background=U.CREAM, wraplength=520, justify="left"
                  ).pack(anchor="w", padx=14, pady=(2, 6))
        box = tk.Text(w, font=("Segoe UI", 11), wrap="none", height=22)
        box.pack(fill="both", expand=True, padx=14)
        box.insert("1.0", "\n".join(self.pub.fet_schools()))
        cnt = ttk.Label(w, text="", background=U.CREAM)
        cnt.pack(anchor="w", padx=14, pady=(4, 0))

        def count(_=None):
            n = len([x for x in box.get("1.0", "end").splitlines() if x.strip()])
            cnt.configure(text=f"{n} school{'s' if n != 1 else ''}")
        box.bind("<KeyRelease>", count)
        count()

        def save(send):
            try:
                n = self.pub.set_fet_schools(box.get("1.0", "end").splitlines())
            except core.PublishError as e:
                messagebox.showerror("Schools using FET", str(e), parent=w)
                return
            w.destroy()
            self.run.log(f"✔ Schools using FET: {n} saved.")
            if send:
                self.push_app()
        b = ttk.Frame(w, style="Card.TFrame", padding=(14, 8))
        b.pack(fill="x", side="bottom")
        ttk.Button(b, text="💾  Save and send to phones", style="Accent.TButton", command=lambda: save(True)).pack(side="right")
        ttk.Button(b, text="Save only", command=lambda: save(False)).pack(side="right", padx=6)
        ttk.Button(b, text="Cancel", command=w.destroy).pack(side="left")

    def _self_update(self):
        try:
            n = self.pub.update_program(self.run.log)
        except Exception:
            n = 0
        if not n:
            return

        def restart():
            messagebox.showinfo("PREPFIX updated", "PREPFIX has been updated to the newest version.\n\nIt will now "
                                                   "restart. Your timetables and teachers' list are kept.")
            try:
                import subprocess
                import sys
                subprocess.Popen([sys.executable] + sys.argv, cwd=str(core.APP_DIR), close_fds=True)
            finally:
                self.root.destroy()
        self.run.ui(restart)

    def push_app(self):
        if not self.need_pw("Send app improvements to teachers' phones."):
            return
        """Owner: put the newest teachers' app on the website. School copies pick it up from there automatically."""
        def go():
            sha = self.pub.deploy_shell()
            self.pub._wait_live(sha)
            self.pub.publish_program()                       # schools' computers update themselves from this
            self.run.ui(lambda: messagebox.showinfo(
                "App improvements sent", "Done. Teachers get the improvements when they open the app or tap "
                "‘Check for updates’. Schools' PREPFIX updates itself the next time it is opened with internet."))
        self.run.run(go)

    def mobile_school(self, on):
        code = self.selected_code()
        if not code:
            messagebox.showinfo("Schools", "Click a school in the list first.")
            return
        sch = self.pub.school(code)
        if bool(self.pub.mobile_on(sch)) == bool(on):
            messagebox.showinfo("Mobile app", f"{sch['name']} is already " + ("on the mobile app." if on else "PC only."))
            return
        if not messagebox.askyesno(
                "Mobile app", (f"ALLOW the mobile app for {sch['name']}?\n\nIt can then publish timetables to teachers' "
                               "phones (teachers' link and QR poster)." if on else
                               f"STOP the mobile app for {sch['name']}?\n\nTeachers' phones stop showing its timetables "
                               "(the saved copy on each phone is cleared). The school keeps PREPFIX on its computer "
                               "(preview, print, all features). You can allow it again at any time.")):
            return

        gh = ""
        if on and not sch.get("github"):
            gh = simpledialog.askstring(
                "Who publishes to phones?", f"{sch['name']}\n\nLeave this EMPTY if YOU publish this school's timetables "
                "(on your website).\n\nIf the school publishes from its own PREPFIX copy, type the school's GitHub "
                "username:", parent=self.root)
            if gh is None:
                return

        def go():
            self.pub.set_mobile(code, on, gh)
            self.run.ui(lambda: (self.fill_schools_local(), self.reload_schools(), self.school_changed()))
        self.run.run(go)

    def suspend_school(self, on):
        if not self.need_pw("Suspend a school." if on else "Restore a school."):
            return
        code = self.selected_code()
        if not code:
            messagebox.showinfo("Schools", "Click a school in the list first.")
            return
        sch = self.pub.school(code)
        if on and sch.get("suspended"):
            messagebox.showinfo("Suspend", f"{sch['name']} is already suspended.")
            return
        if not on and not sch.get("suspended"):
            messagebox.showinfo("Restore", f"{sch['name']} is not suspended.")
            return
        if on:
            reason = simpledialog.askstring(
                "Suspend school", f"SUSPEND {sch['name']}?\n\nTeachers' phones stop showing its timetables (and the "
                "saved copy on each phone is cleared). Publishing is blocked. Nothing is deleted: “Restore” brings "
                "everything back.\n\nReason (for your records, optional):", parent=self.root)
            if reason is None:
                return
        else:
            if not messagebox.askyesno("Restore school", f"Restore {sch['name']}?\n\nTeachers see its timetables "
                                                         "again the next time they open the app, and it can publish again."):
                return
            reason = ""

        def go():
            self.pub.set_suspended(code, on, reason)
            self.run.ui(lambda: (self.fill_schools_local(), self.reload_schools()))
        self.run.run(go)

    def renew_school(self):
        code = self.selected_code()
        if not code:
            messagebox.showinfo("Renew", "Click a school in the list first.")
            return
        sch = self.pub.school(code)
        u = core.sub_until(sch)
        dl = core.days_left(u)
        today = datetime.now().strftime("%Y-%m-%d")
        d = tk.Toplevel(self.root)
        d.title("Renew subscription")
        d.configure(bg=U.CREAM)
        d.resizable(False, False)
        now_txt = ("ended on " + core.nice_day(u)) if dl is not None and dl < 0 else \
            f"paid until {core.nice_day(u)} ({dl} days left)"
        tk.Label(d, text=f"{sch['name']}\nNow: {now_txt}", bg=U.CREAM, font=("Segoe UI Semibold", 11),
                 justify="left").pack(anchor="w", padx=18, pady=(16, 10))
        how = tk.StringVar(value="end")
        new_end = core.plus_years(u or today)
        for val, txt in (("end", f"One more year from the day it was due to end ({core.nice_day(u)})  →  paid until "
                                 f"{core.nice_day(new_end)}"),
                         ("today", f"One more year from today  →  paid until {core.nice_day(core.plus_years(today))}"),
                         ("date", "Set the last paid day myself:")):
            tk.Radiobutton(d, text=txt, variable=how, value=val, bg=U.CREAM, anchor="w", justify="left",
                           font=("Segoe UI", 10)).pack(anchor="w", padx=18)
        ent = ttk.Entry(d, width=14)
        ent.insert(0, new_end)
        ent.pack(anchor="w", padx=44, pady=(2, 6))
        tk.Label(d, text="(year-month-day, e.g. 2027-11-16)", bg=U.CREAM, fg="#667085").pack(anchor="w", padx=44)
        res = {}
        bar = tk.Frame(d, bg=U.CREAM)
        bar.pack(fill="x", padx=18, pady=(10, 14))

        def ok():
            res["how"], res["date"] = how.get(), ent.get().strip()
            d.destroy()
        ttk.Button(bar, text="Renew", style="Accent.TButton", command=ok).pack(side="right")
        ttk.Button(bar, text="Cancel", command=d.destroy).pack(side="right", padx=8)
        d.grab_set()
        self.front(d)
        self.root.wait_window(d)
        if not res:
            return
        if not self.need_pw("Renew a school's subscription."):
            return

        def go():
            until = self.pub.renew_school(code, start="today" if res["how"] == "today" else "end",
                                          until=res["date"] if res["how"] == "date" else "")
            self.run.ui(lambda: (self.fill_schools_local(), messagebox.showinfo(
                "Renewed", f"{sch['name']} is now paid until {core.nice_day(until)}.")))
        self.run.run(go)

    def _sub_check(self):
        """School copies: how long this school's subscription still runs (a reminder in the last 30 days).
        Suspended by Cyrus Ireri, or the subscription has ended: PREPFIX closes down (nothing works - not even the
        preview) until it is restored or renewed."""
        self.run.ui(lambda: self.root.after(20 * 60 * 1000, lambda: threading.Thread(
            target=self._sub_check, daemon=True).start()))          # checked again every 20 minutes
        try:
            u, dl, online, susp = self.pub.my_subscription(online=True)
        except Exception:
            return
        if susp or (dl is not None and dl < 0):
            self.run.ui(lambda: self.lock_closed(u, susp))
            return
        self.run.ui(self.unlock_closed)
        self.run.ui(lambda: self.show_sub(u, dl))
        if dl is None or getattr(self, "_sub_told", False):
            return
        self._sub_told = True
        msg = f"Subscription: paid until {core.nice_day(u)} — {dl} day{'s' if dl != 1 else ''} left."
        self.run.log("📅 " + msg)
        if dl <= 30:
            msg += f"\n\nTo renew for another year, contact Cyrus Ireri, {core.LOCKED_CONTACT}."
            self.run.ui(lambda: messagebox.showwarning("PREPFIX subscription", msg))

    def show_sub(self, until, dl):
        """The strip at the top of a school's PREPFIX: paid until … — N days left (amber in the last 30 days,
        red in the last 7)."""
        b = getattr(self, "sub_bar", None)
        if b is None or dl is None:
            return
        if dl < 0:
            t, bg, fg = f"⛔  Subscription ended on {core.nice_day(until)}.", "#FDE7E4", "#B5463A"
        else:
            t = f"📅  Subscription: paid until {core.nice_day(until)} — {dl} day{'s' if dl != 1 else ''} left."
            bg, fg = (("#FDE7E4", "#B5463A") if dl <= 7 else ("#FFF3D6", "#8A5A12") if dl <= 30 else ("#E7F5EC", "#1E7F5C"))
        if dl <= 30:
            t += f"   To renew for another year, contact Cyrus Ireri, {core.LOCKED_CONTACT}."
        b.configure(text=t, bg=bg, fg=fg)

    def lock_closed(self, until, suspended=False):
        """Suspended / subscription over: a closed screen covers the whole window and the preview stops.
        Only “Check again” and “Close” work."""
        name = self.pub.bound_school["name"]
        if suspended:
            head, text = "PREPFIX is suspended", f"{name}'s PREPFIX service has been suspended by Cyrus Ireri."
        else:
            head, text = "PREPFIX subscription has ended", f"{name}'s subscription ended on {core.nice_day(until)}."
        PS.CLOSED["msg"] = text + f" Contact Cyrus Ireri, {core.LOCKED_CONTACT}."
        try:
            PS.close_window()                              # an open preview closes too
        except Exception:
            pass
        sp = getattr(getattr(self.root, "_splash", None), "w", None)
        for w in self.root.winfo_children():               # other PREPFIX windows (Preview, rules, phones…) close
            if isinstance(w, tk.Toplevel) and w is not sp:
                try:
                    w.destroy()
                except tk.TclError:
                    pass
        old = getattr(self, "_closed_box", None)
        if old:
            old.destroy()
        bg = "#1D2A44"
        box = tk.Frame(self.root, bg=bg)
        box.place(relx=0, rely=0, relwidth=1, relheight=1)
        inner = tk.Frame(box, bg=bg)
        inner.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(inner, text="⛔", bg=bg, fg="#F2C14E", font=("Segoe UI", 40)).pack()
        tk.Label(inner, text=head, bg=bg, fg="white", font=("Segoe UI", 20, "bold")).pack(pady=(4, 8))
        tk.Label(inner, text=text + "\nPREPFIX, the preview and the teachers' phones stay closed until it is "
                 + ("switched back on" if suspended else "renewed") + ".\n"
                 "Your timetables and teachers' list are kept safely.\n\n"
                 f"Contact Cyrus Ireri, {core.LOCKED_CONTACT}.", bg=bg, fg="#D7DEEA",
                 font=("Segoe UI", 12), justify="center").pack()
        self._closed_msg = tk.Label(inner, text="", bg=bg, fg="#F2C14E", font=("Segoe UI", 11))
        self._closed_msg.pack(pady=(10, 0))
        btns = tk.Frame(inner, bg=bg)
        btns.pack(pady=14)
        ttk.Button(btns, text="↻  Check again", style="Accent.TButton",
                   command=self._recheck_closed).pack(side="left", padx=6)
        ttk.Button(btns, text="Close PREPFIX", command=self.root.destroy).pack(side="left", padx=6)
        box.lift()
        self._closed_box = box
        if not getattr(self, "_closed_bound", False):
            self._closed_bound = True
            for seq in ("<Key>", "<Button>"):
                self.root.bind_all(seq, self._swallow_when_closed, add="+")

    def _swallow_when_closed(self, e):
        box = getattr(self, "_closed_box", None)
        if box and not str(e.widget).startswith(str(box)):
            return "break"

    def unlock_closed(self):
        PS.CLOSED["msg"] = ""
        box = getattr(self, "_closed_box", None)
        if box:
            box.destroy()
            self._closed_box = None
            self.run.log("✔ PREPFIX is open again.")

    def _recheck_closed(self):
        self._closed_msg.configure(text="Checking…")

        def go():
            try:
                u, dl, online, susp = self.pub.my_subscription(online=True)
            except Exception:
                u, dl, online, susp = None, None, False, True
            if not online:
                self.run.ui(lambda: self._closed_msg.configure(text="No internet - connect and try again."))
            elif not susp and dl is not None and dl >= 0:
                self.run.ui(self.unlock_closed)
            else:
                self.run.ui(lambda: self._closed_msg.configure(
                    text="Still suspended." if susp else "Not renewed yet."))
        threading.Thread(target=go, daemon=True).start()

    def delete_school(self):
        if not self.need_pw("Delete a school."):
            return
        code = self.selected_code()
        sch = self.pub.school(code) if code else None
        if not sch:
            messagebox.showinfo("Delete school", "First click the school in the list above.")
            return
        if not messagebox.askyesno(
                "Delete school?", f"Delete {sch['name']} completely?\n\n• it disappears from the list of schools\n"
                "• its timetables are removed from the website — teachers will no longer see them\n"
                "• this CANNOT be undone\n\nUse this only for test schools or mistakes.", icon="warning"):
            return
        typed = sch["name"]                            # one Yes is enough: no typing the name

        def go():
            name = self.pub.delete_school(code, typed)
            self.run.ui(lambda: (self.fill_schools_local(), self.reload_schools(),
                                 messagebox.showinfo("Deleted", f"{name} has been deleted.")))
        self.run.run(go)

    def choose_save_folder(self):
        d = filedialog.askdirectory(title="Where should your saved folder be kept? (e.g. Documents or a flash disk)")
        if not d:
            return
        target = Path(d)
        if not (target / core.SETUP_FILE).exists() and not (target / core.OLD_SETUP_FILE).exists() and not (target / core.SITE_DIR).exists():
            target = target / "PREPFIX saved folder"
        self.pub.s.set("save_folder", str(target))
        self.folder_var.set(str(target))
        if self.pub.ready:
            self.save_now()

    def save_now(self):
        if not self.pub.s.get("save_folder"):
            self.choose_save_folder()
            return
        self.run.run(lambda: self.pub.save_folder())

    def selected_code(self):
        sel = self.sch_tree.selection()
        return sel[0] if sel else None

    def open_phones(self):
        code = self.selected_code()
        if not code and self.pub.is_school:
            sch = next(iter(self.pub.schools()), None)       # a school copy holds just its own school
            code = sch["code"] if sch else None
        if not code:
            messagebox.showinfo("Teachers & phones", "Click the school in the list first.")
            return
        if self.pub.is_school:
            if not self.pub.school_manages(code):
                messagebox.showinfo("Teachers & phones", "The teachers' list of this school is kept by Cyrus Ireri, "
                                    + core.LOCKED_CONTACT + ".")
                return
            PH.Phones(self, code)
            return
        if self.pub.school_manages(code):
            PH.SchoolList(self, code)                       # the school types its own teachers in its copy
            return
        PH.Phones(self, code)

    def open_selected_school(self):
        code = self.selected_code()
        if code and self.pub.ready:
            webbrowser.open(self.pub.school_link(code))

    def goto_publish(self):
        code = self.selected_code()
        s = self.pub.school(code) if code else None
        if s:
            self.reload_schools(select=s["name"])
            self.nb.select(self.tab_imp)

    # ------------------------------------------------------------------ Setup tab
    def build_setup(self):
        f = ttk.Frame(self.scrollable(self.tab_set), style="Card.TFrame", padding=18)   # scrolls on a small screen
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=("Back up everything / move to another laptop" if self.pub.relay else
                           "Set up by importing your saved folder"), style="Big.TLabel").pack(anchor="w")
        ttk.Label(f, text="Your saved folder holds everything: your website details, every registered school and every "
                          "timetable. On any computer, setting up is just importing it.",
                  style="CardMuted.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=(4, 10))
        g = ttk.Frame(f, style="Card.TFrame")
        g.pack(fill="x", pady=(2, 4))
        ttk.Button(g, text="📂  Import my saved folder…", style="Accent.TButton", command=self.import_folder).pack(side="left")
        self.setup_state = ttk.Label(g, text="", style="Card.TLabel")
        self.setup_state.pack(side="left", padx=14)

        k = ttk.Frame(f, style="Card.TFrame")
        k.pack(fill="x", pady=(8, 2))
        ttk.Label(k, text="My saved folder:", style="H.TLabel", width=18).pack(side="left")
        self.folder_var = tk.StringVar(value=self.pub.s.get("save_folder", ""))
        ttk.Entry(k, textvariable=self.folder_var, state="readonly", width=58).pack(side="left", padx=6)
        ttk.Button(k, text="Change…", command=self.choose_save_folder).pack(side="left")
        ttk.Button(k, text="Save now", command=self.save_now).pack(side="left", padx=6)
        ttk.Label(f, text="It is updated automatically after every registration and every publish. Keep a copy on a "
                          "flash disk too. prepfix-setup.json inside it is private — never upload or share it.",
                  style="CardMuted.TLabel", wraplength=900, justify="left").pack(anchor="w")

        h = ttk.Frame(f, style="Card.TFrame")
        h.pack(fill="x", pady=(12, 0))
        if self.pub.is_school and self.pub.relay:
            L = self.pub.licence
            ttk.Label(h, text=f"{L['name']}", style="H.TLabel").pack(anchor="w")
            ttk.Label(h, text="Nothing else to set up. Publish sends this school's timetables to teachers' phones."
                              "\n\nBACK UP EVERYTHING: “Save now” above keeps "
                              "every timetable, the teachers' list and the notes in your saved folder (choose a flash disk "
                              "or Google Drive folder with “Change…”). On a new laptop: install PREPFIX, then “Import my "
                              "saved folder” — everything comes back.", style="CardMuted.TLabel", wraplength=900,
                      justify="left").pack(anchor="w", pady=(2, 6))
            ttk.Button(h, text="🔑 Change PREPFIX password", command=self.change_tk_password).pack(anchor="w", pady=(0, 6))
        elif self.pub.is_school:
            L = self.pub.licence
            ttk.Label(h, text=f"{L['name']}", style="H.TLabel").pack(anchor="w")
            ttk.Label(h, text=f"Very first time only: sign in to the GitHub account “{L['github']}”, open the token page, "
                              "create the token and paste it here. PREPFIX remembers it on this computer — it is never asked for again, "
                              "even when you put a new version of PREPFIX in place.", style="CardMuted.TLabel", wraplength=900,
                      justify="left").pack(anchor="w", pady=(2, 6))
        else:
            ttk.Label(h, text="Very first time only (no saved folder yet)", style="H.TLabel").pack(anchor="w")
            ttk.Label(h, text="Only needed once ever. Paste your website key, then choose where to keep your saved "
                              "folder. PREPFIX then remembers it on this computer and never asks for it again (a new version of PREPFIX "
                              "keeps it too). On another computer, use Import.", style="CardMuted.TLabel",
                      wraplength=900).pack(anchor="w", pady=(2, 6))
        c = ttk.Frame(h, style="Card.TFrame")
        if not self.pub.relay:
            c.pack(fill="x", pady=2)
        ttk.Button(c, text="Open token page", command=lambda: webbrowser.open(TOKEN_URL)).pack(side="left")
        self.token_var = tk.StringVar()
        ttk.Entry(c, textvariable=self.token_var, show="•", width=44, font=("Consolas", 10)).pack(side="left", padx=8, ipady=3)
        ttk.Button(c, text="⚙  Connect my website", command=self.do_setup).pack(side="left")
        if not self.pub.is_school:                       # lesson reminders that reach phones when the app is closed
            rr = ttk.Frame(f, style="Card.TFrame")
            rr.pack(fill="x", pady=(10, 0))
            ttk.Label(rr, text="⏰ Lesson reminders service (Cloudflare, free)", style="H.TLabel").pack(anchor="w")
            ttk.Label(rr, text="Paste the link of your reminder service once (see SETUP GUIDE.html, Part E). Teachers then get "
                               "the 10-minute alert even when the app is closed. New school copies carry it too.",
                      style="CardMuted.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=(2, 6))
            r2 = ttk.Frame(rr, style="Card.TFrame")
            r2.pack(fill="x")
            ttk.Button(r2, text="Open Cloudflare", command=lambda: webbrowser.open("https://dash.cloudflare.com/sign-up")).pack(side="left")
            self.push_var = tk.StringVar(value=self.pub.s.get("push_url", ""))
            ttk.Entry(r2, textvariable=self.push_var, width=52).pack(side="left", padx=8, ipady=3)
            ttk.Button(r2, text="✔ Save & check", command=self.save_push).pack(side="left")

            ow = ttk.Frame(f, style="Card.TFrame")
            ow.pack(fill="x", pady=(10, 0))
            ttk.Label(ow, text="🔑 Owner password (see every school inside the app)", style="H.TLabel").pack(anchor="w")
            ttk.Label(ow, text="Choose a private password (6+ characters). In the app, open the menu and tap the line ‘Version V1’ "
                               "5 times, type the password, and the Schools page lets you open any school. Only a scrambled copy "
                               "is put on the website. Leave the box empty and save to switch it off.",
                      style="CardMuted.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=(2, 6))
            ok_ = ttk.Frame(f, style="Card.TFrame")
            ok_.pack(fill="x", pady=(10, 0))
            ttk.Label(ok_, text="🔒 Owner key for the PREPFIX service (school lock & who has the app)", style="H.TLabel"
                      ).pack(anchor="w")
            ttk.Label(ok_, text="The same private password you typed as OWNER_KEY in Cloudflare (SETUP GUIDE.html, Part E). "
                               "Needed to lock schools so that only their teachers open the timetables.",
                      style="CardMuted.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=(2, 6))
            k2 = ttk.Frame(ok_, style="Card.TFrame")
            k2.pack(fill="x")
            self.ownkey_var = tk.StringVar(value=self.pub.s.get("owner_key", ""))
            ttk.Entry(k2, textvariable=self.ownkey_var, show="•", width=30).pack(side="left", padx=(0, 8), ipady=3)
            ttk.Button(k2, text="✔ Save owner key", command=lambda: (self.pub.s.set("owner_key", self.ownkey_var.get().strip()),
                                                                     self.run.log("✔ Owner key saved."))).pack(side="left")
            o2 = ttk.Frame(ow, style="Card.TFrame")
            o2.pack(fill="x")
            self.ownpw_var = tk.StringVar()
            ttk.Entry(o2, textvariable=self.ownpw_var, show="•", width=30).pack(side="left", padx=(0, 8), ipady=3)
            ttk.Button(o2, text="✔ Save owner password", command=self.save_owner_pw).pack(side="left")
            ttk.Button(o2, text="🔑 Change PREPFIX password", command=self.change_tk_password).pack(side="left", padx=8)

    def save_push(self):
        url = self.push_var.get()

        def go():
            u = self.pub.set_push_url(url)
            if u and self.pub.ready:
                self.run.log("Updating the app on your website so phones know the reminder service…")
                self.pub.deploy_shell()
            self.pub.autosave()
            self.run.log("✔ Reminder service saved: " + (u or "(none)"))
            self.run.ui(lambda: messagebox.showinfo("Lesson reminders", "Saved. Teachers who switch on ‘Lesson reminder’ "
                                                   "will now get it even when the app is closed." if u else "Reminder service removed."))
        self.run.run(go)

    def save_owner_pw(self):
        pw = self.ownpw_var.get()

        def go():
            on = self.pub.set_owner_password(pw)
            if self.pub.ready:
                self.run.log("Updating the app on your website with the owner password…")
                self.pub.deploy_shell()
            self.pub.autosave()
            self.run.log("✔ Owner password " + ("saved." if on else "removed."))
            self.run.ui(lambda: (self.ownpw_var.set(""), messagebox.showinfo(
                "Owner password", "Saved. On your phone: menu → tap ‘App version’ 5 times → type the password. "
                                  "(Phones first tap Update when the ‘PREPFIX has been improved’ box shows.)" if on
                else "Owner password removed.")))
        self.run.run(go)

    # ------------------------------------------------------------------ helpers
    def apply_edition(self):
        """School copies: the one licensed school; nothing else to choose."""
        if not self.pub.is_school:
            return
        b = self.pub.bound_school
        self.btn_reg.pack_forget()
        self.school_box.configure(state="disabled")
        self.reload_schools(select=b["name"])
        self.refresh_header()

    def refresh_header(self):
        b = self.pub.bound_school if self.pub.is_school else None
        if self.pub.ready and b:
            self.head_right.configure(text=f"{b['name']}", fg="#F2D37A")
            self.setup_state.configure(text=f"✔ {b['name']} · website {self.pub.site_url}", style="Ok.TLabel")
        elif self.pub.is_school:
            b = self.pub.bound_school
            self.head_right.configure(text=f"{b['name']} · on this computer", fg="#F2D37A")
            self.setup_state.configure(text="", style="Card.TLabel")
        elif self.pub.ready:
            self.head_right.configure(text=f"● Ready · {self.pub.site_url.replace('https://', '')}", fg="#9BE3C2")
            self.setup_state.configure(text=f"✔ Connected. Website: {self.pub.site_url}", style="Ok.TLabel")
        else:
            self.head_right.configure(text="Setup needed", fg="#F2D37A")
            self.setup_state.configure(text="", style="Card.TLabel")

    def reload_schools(self, select=None):
        names = [s["name"] for s in self.pub.schools()]
        self.school_box["values"] = names
        if select and select in names:
            self.school_var.set(select)
        elif names and self.school_var.get() not in names:
            self.school_var.set(names[0])
        self.school_changed()

    def current_school(self):
        return next((s for s in self.pub.schools() if s["name"] == self.school_var.get()), None)

    def school_changed(self):
        s = self.current_school()
        self.link_var.set((self.pub.school_link(s["code"]) if self.mobile_ok() else "— mobile app not switched on for this school —")
                          if s and self.pub.ready else "")
        names = [t["name"] for t in self.pub.timetables(s["code"])] if s else []
        self.tt_box["values"] = names
        if hasattr(self, "tt_box2"):
            self.tt_box2["values"] = names
        self.fill_published(s)
        if s and not self.tt_var.get():
            self.set_tt(names[0] if names else core.suggest_lock_words(s["name"]).split(" ")[0])
        elif s and names and core.tt_name(self.tt_var.get()) not in names and getattr(self, "_last_school", None) != s["code"]:
            self.set_tt(names[0])
        self._last_school = s["code"] if s else None
        self.tt_changed()
        if hasattr(self, "note_tree"):
            self.refresh_tt_notes()
        if hasattr(self, "con"):
            self.con.refresh()

    # ------------------------------------------------------------------ notes under the timetables
    def tt_notes(self):
        sch = self.current_school()
        return notes_word.one_per_target(list((self.pub.s.get("tt_notes", {}) or {}).get(sch["code"], []))) if sch else []

    def _save_tt_notes(self, notes):
        sch = self.current_school()
        if not sch:
            return
        allm = dict(self.pub.s.get("tt_notes", {}) or {})
        allm[sch["code"]] = notes_word.one_per_target(notes)       # one statement per class / teacher
        self.pub.s.set("tt_notes", allm)

    @staticmethod
    def _note_label(n):
        return {"classes": "Every class", "teachers": "Every teacher"}.get(n["to"]) or \
            (f"Class: {n['name']}" if n["to"] == "class" else f"Teacher: {n.get('label') or n['name']}")

    def open_notes(self):
        if not self.current_school():
            messagebox.showinfo("Notes", "Choose the school first.")
            return
        self.refresh_tt_notes()
        self.front(self.notes_win)
        try:
            self.notes_win.state("zoomed")
        except tk.TclError:
            pass

    def close_notes(self):
        self.notes_win.withdraw()
        self.refresh_tt_notes()

    def refresh_tt_notes(self):
        vals = ["Auto — PREPFIX finds who it is for", "Every class", "Every teacher"]
        if self.data:
            vals += [f"Class: {c['name']}" for c in self.data.get("classes", [])]
            vals += [f"Teacher: {t['code']} · {t.get('name') or t['code']}" for t in self.data.get("teachers", [])]
        self.note_to_box["values"] = vals
        self.note_tree.delete(*self.note_tree.get_children())
        for i, n in enumerate(self.tt_notes()):
            self.note_tree.insert("", "end", iid=str(i), values=(self._note_label(n), " ".join(n["text"].split())[:160]))
        if hasattr(self, "notes_count"):
            k = len(self.tt_notes())
            self.notes_count.configure(text=(f"{k} note(s) saved — they show in the previews of A and B" if k else
                                             "none yet — add them first, then check them in the preview"))

    def add_tt_note(self):
        if not self.current_school():
            messagebox.showinfo("Notes", "Choose the school first (Import & Run).")
            return
        text = self.note_text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Notes", "Type or paste the note in the box first.")
            return
        to = self.note_to.get()
        if to.startswith("Auto"):                                # PREPFIX reads who it is for from the note
            classes, teachers = self._targets()
            who, body = notes_word.find_targets(text, classes, teachers)
            if not who:
                messagebox.showinfo("Notes", "PREPFIX could not tell who this note is for.\n\nStart it with the class or "
                                             "teacher and a colon (e.g. “9N: …”, “All classes: …”, “All teachers: …”), "
                                             "or name the class in the note — or choose “For” yourself.")
                return
            new = [dict(w, text=body) for w in who]
            self._save_tt_notes(self.tt_notes() + new)
            self.note_text.delete("1.0", "end")
            self.refresh_tt_notes()
            self.run.log("📌 Note added for " + ", ".join(self._note_label(n) for n in new) +
                         " — it goes out with the next Publish.")
            return
        if to == "Every class":
            n = {"to": "classes", "name": "", "text": text}
        elif to == "Every teacher":
            n = {"to": "teachers", "name": "", "text": text}
        elif to.startswith("Class: "):
            n = {"to": "class", "name": to[7:], "text": text}
        elif to.startswith("Teacher: "):
            code, _, nm = to[9:].partition(" · ")
            n = {"to": "teacher", "name": code, "label": f"{code} · {nm}", "text": text}
        else:
            return
        self._save_tt_notes(self.tt_notes() + [n])
        self.note_text.delete("1.0", "end")
        self.refresh_tt_notes()
        self.run.log(f"📌 Note added for {self._note_label(n)} — it goes out with the next Publish.")

    def _targets(self):
        d = self.data or {}
        return ([c["name"] for c in d.get("classes", [])],
                [(t["code"], t.get("name") or t["code"]) for t in d.get("teachers", [])])

    def notes_template(self):
        sch = self.current_school()
        name = "PREPFIX notes" + (f" - {re.sub(r'[^A-Za-z0-9 .-]+', '', sch['name'])[:40]}" if sch else "") + ".docx"
        f = filedialog.asksaveasfilename(title="Save the notes template (Word)", defaultextension=".docx", initialfile=name,
                                         filetypes=[("Word document", "*.docx")])
        if not f:
            return
        try:
            notes_word.make_template(f, sch["name"] if sch else "", *self._targets())
        except Exception as e:
            messagebox.showerror("Notes template", f"The template could not be made: {e}")
            return
        self.run.log(f"✔ Notes template (Word) saved: {f}")
        if messagebox.askyesno("Notes template", f"Saved:\n{f}\n\nWrite each note as a paragraph, starting with who it "
                                                 "is for (“9N: …”, “All teachers: …”) or just naming the class. Save, then "
                                                 "“Import notes from file”.\n\nOpen it in Word now?"):
            try:
                os.startfile(f)
            except Exception:
                pass

    def import_tt_notes(self):
        if not self.current_school():
            messagebox.showinfo("Notes", "Choose the school first (Import & Run).")
            return
        f = filedialog.askopenfilename(title="Choose the notes file", filetypes=[("Word document", "*.docx"),
                                                                                 ("Excel (older template)", "*.xlsx *.xlsm *.csv")])
        if not f:
            return
        try:
            notes, problems = notes_word.read_notes(f, *self._targets())
        except Exception as e:
            messagebox.showerror("Notes", f"The file could not be read: {e}")
            return
        msg = f"{len(notes)} note(s) ready to add:\n" + "\n".join(
            f"  • {self._note_label(n)}: {' '.join(n['text'].split())[:60]}" for n in notes[:14]) + \
            (f"\n  …and {len(notes) - 14} more" if len(notes) > 14 else "")
        if problems:
            msg += ("\n\nNOT added (correct them in the file and import again):\n" +
                    "\n".join(f"  paragraph {r}: “{w}” — {why}" for r, w, why in problems[:15]) +
                    (f"\n  …and {len(problems) - 15} more" if len(problems) > 15 else ""))
        if not notes:
            messagebox.showwarning("Notes", msg if problems else "No notes were found in that file.")
            return
        if not messagebox.askyesno("Import notes", msg + "\n\nAdd them now? (One note per class or teacher: a class that "
                                                        "already has a note gets this one instead.)"):
            return
        self._save_tt_notes(self.tt_notes() + notes)
        self.refresh_tt_notes()
        self.run.log(f"📌 {len(notes)} note(s) imported" + (f", {len(problems)} row(s) not matched" if problems else "") +
                     " — they go out with the next Publish.")

    def remove_tt_note(self):
        sel = self.note_tree.selection()
        if not sel:
            messagebox.showinfo("Notes", "Click a note in the list first.")
            return
        notes = [n for i, n in enumerate(self.tt_notes()) if str(i) not in sel]
        self._save_tt_notes(notes)
        self.refresh_tt_notes()
        self.run.log("Note removed — teachers stop seeing it after the next Publish.")

    def set_tt(self, value):
        """Set the timetable name from the program (no pop-up)."""
        self._auto_tt = True
        try:
            self.tt_var.set(value)
        finally:
            self._auto_tt = False
        self._warned = core.tt_name(value)

    def warn_replace(self, now=False):
        """Pop up as soon as the name matches a timetable that is already published."""
        if getattr(self, "_warn_job", None):
            self.root.after_cancel(self._warn_job)
            self._warn_job = None
        if not now:                                  # wait until typing pauses
            self._warn_job = self.root.after(900, lambda: self.warn_replace(now=True))
            return
        s = self.current_school()
        name = core.tt_name(self.tt_var.get())
        old = self.pub.existing_timetable(s["code"], name) if s and len(name) >= 2 else None
        if not old:
            self._warned = None
            return
        if getattr(self, "_warned", None) == name:
            return
        self._warned = name
        messagebox.showwarning(
            "This name is already published",
            f"“{old['name']}” is already published for {s['name']}\n(last published {when(old.get('updated', ''))}).\n\n"
            f"If you publish with this name, it will REPLACE that timetable on teachers' phones.\n\n"
            "To ADD a new timetable instead, type a different name.")

    def fill_published(self, s=None):
        if not hasattr(self, "pub_tree"):
            return
        s = s if s is not None else self.current_school()
        self.pub_tree.delete(*self.pub_tree.get_children())
        for t in sorted(self.pub.timetables(s["code"]) if s else [], key=lambda t: t.get("updated", ""), reverse=True):
            self.pub_tree.insert("", "end", iid=t["id"], values=(t["name"], when(t.get("updated", "")), t.get("count", 1),
                                                                  f"{t.get('teachers', '?')} · {t.get('classes', '?')}"))

    def delete_timetable(self, sch=None, tid=None):
        """Remove a published timetable from the website (teachers' phones). The school's other timetables stay."""
        sch = sch or self.current_school()
        if not sch:
            messagebox.showinfo("Delete a timetable", "Choose the school first.")
            return
        if tid is None:
            sel = self.pub_tree.selection() if hasattr(self, "pub_tree") else ()
            if not sel:
                messagebox.showinfo("Delete a timetable", "Click the timetable in the list first.")
                return
            tid = sel[0]
        t = next((x for x in self.pub.timetables(sch["code"]) if x["id"] == tid), None)
        if not t:
            return
        if not self.pub.ready:
            messagebox.showinfo("Setup", "Do the one-time Setup first.")
            return
        if not messagebox.askyesno(
                "Delete this timetable?",
                f"DELETE “{t['name']}” of {sch['name']}?\n(last published {when(t.get('updated', ''))})\n\n"
                "It is removed from the website and from teachers' phones (they see the school's other timetables, if "
                "any). A copy stays on this computer.\n\nDelete it?", icon="warning", default="no"):
            return

        def go():
            self.pub.delete_timetable(sch["code"], tid, progress=self.run.progress)
            self.run.log(f"🗑 “{t['name']}” deleted for {sch['name']}.")
            self.run.ui(lambda: (self.school_changed(), self.fill_schools_local() if hasattr(self, "sch_tree") else None,
                                 messagebox.showinfo("Deleted", f"“{t['name']}” is no longer on teachers' phones.")))
        self.run.run(go)

    def delete_timetable_picker(self):
        if not self.need_pw("Delete a timetable."):
            return
        """Schools tab: choose one of the selected school's published timetables to delete."""
        code = self.selected_code()
        sch = self.pub.school(code) if code else None
        if not sch:
            messagebox.showinfo("Delete a timetable", "First click the school in the list above.")
            return
        tts = sorted(self.pub.timetables(code), key=lambda t: t.get("updated", ""), reverse=True)
        if not tts:
            messagebox.showinfo("Delete a timetable", f"{sch['name']} has no published timetable.")
            return
        w = tk.Toplevel(self.root)
        w.title(f"Delete a timetable — {sch['name']}")
        w.configure(bg=U.CREAM)
        w.transient(self.root)
        f = ttk.Frame(w, style="Card.TFrame", padding=14)
        f.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Label(f, text=f"Published timetables of {sch['name']}", style="H.TLabel").pack(anchor="w")
        lb = tk.Listbox(f, height=min(10, len(tts)), width=60, font=("Segoe UI", 11), exportselection=False)
        for t in tts:
            lb.insert("end", f"{t['name']}   —   {when(t.get('updated', ''))}")
        lb.pack(fill="both", expand=True, pady=6)
        lb.selection_set(0)
        bb = ttk.Frame(f, style="Card.TFrame")
        bb.pack(fill="x")

        def do():
            i = lb.curselection()
            if i:
                w.destroy()
                self.delete_timetable(sch, tts[i[0]]["id"])
        ttk.Button(bb, text="🗑  Delete", style="Accent.TButton", command=do).pack(side="right")
        ttk.Button(bb, text="Cancel", command=w.destroy).pack(side="right", padx=6)

    def tt_changed(self, typed=False):
        if typed:
            self.warn_replace()
        s = self.current_school()
        name = core.tt_name(self.tt_var.get())
        labels = [self.tt_state] + ([self.tt_state2] if hasattr(self, "tt_state2") else [])
        if not s or len(name) < 2:
            for lb in labels:
                lb.configure(text="")
            return
        old = self.pub.existing_timetable(s["code"], name)
        for lb in labels:
            if old:
                lb.configure(text=f"⟳ REPLACES the one from {when(old.get('updated', ''))}", style="Bad.TLabel")
            else:
                lb.configure(text="＋ NEW timetable (added)", style="Ok.TLabel")

    def new_school(self, name=None):
        if not self.pub.can_register():
            messagebox.showinfo("Registered", "This copy is already registered to its school. A school registers "
                                              "only once.")
            return
        name = name or simpledialog.askstring("Register a school", "School name (as teachers know it):", parent=self.root)
        name = core.clean_name(name or "")
        if not name:
            return
        if not messagebox.askyesno(
                "Register a school",
                f"Register “{name.upper()}”?\n\n• no timetable is needed now\n• its own PREPFIX copy is made in "
                "FOR_SCHOOLS at once\n• it starts as PC only (you allow the mobile app later)\n• it gets its own link "
                "for teachers"
                + ("\n• this copy can never register another school" if self.pub.is_school else "")
                + "\n\nCheck the spelling (you can still rename it later)."):
            return

        def go():
            s = self.pub.register_school(name)
            self.run.ui(lambda: (self.reload_schools(select=s["name"]), self.fill_schools_local(), self.apply_edition(),
                                 messagebox.showinfo("Registered", f"{s['name']} is registered.\n\nIts own PREPFIX copy:\n"
                                                     f"{self.pub.copy_path(s)}" if self.pub.has_copy(s) else
                                                     f"{s['name']} is registered.")))
        self.run.run(go)

    def open_link(self, extra):
        if self.link_var.get().startswith("http"):
            webbrowser.open(self.link_var.get() + extra)

    def copy_link(self):
        if self.link_var.get().startswith("http"):
            self.root.clipboard_clear()
            self.root.clipboard_append(self.link_var.get())
            self.run.log("Copied: " + self.link_var.get())

    def set_summary(self, text):
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    # ------------------------------------------------------------------ actions
    def do_setup(self):
        token = self.token_var.get()

        def go():
            url = self.pub.setup(token)

            def done():
                self.token_var.set("")
                self.refresh_header()
                self.reload_schools()
                self.fill_schools_local()
                if not self.pub.s.get("save_folder"):
                    messagebox.showinfo("Your saved folder", "Now choose where to keep your saved folder (e.g. "
                                        "Documents). It will hold everything, so next time setting up is just importing.")
                    self.choose_save_folder()
                messagebox.showinfo("Setup complete", f"Your timetable website is:\n\n{url}\n\nIt can take up to "
                                                      "10 minutes to switch on the very first time.")
                self.nb.select(self.tab_imp)
            self.run.ui(done)
        self.run.run(go)

    def match_school(self, data):
        """The registered school whose name matches the FET institution name, if any."""
        best = None
        for sch in self.pub.schools():
            lock = core.suggest_lock_words(sch["name"])
            if all(fet_reader.institution_matches(v, lock) for v in data["institutions"].values()):
                score = len(lock.split())
                if not best or score > best[0]:
                    best = (score, sch)
        return best[1] if best else None

    def add_folder(self):
        d = filedialog.askdirectory(title="Choose the FET timetables folder")
        if not d:
            return
        self.folder = Path(d)
        self.folder_lbl.configure(text=f"Folder: {d}")
        self.data = None
        self.reset_run()
        self.check_lbl.configure(text="", style="Card.TLabel")

        def go():
            self.run.log(f"Reading {d} …")
            data = fet_reader.scan_fet(self.folder, log=self.run.log)
            P = data["periods"]
            lessons = [p for p in P if not p["brk"]]
            breaks = [p["label"] for p in P if p["brk"]]
            il = data.get("institution_lines") or [data["institution"]]
            lines = [
                "School (from FET):   " + il[0],
                "Timetable (from FET):  " + (" ".join(il[1:]) or "—"),
                "",
                f"Teachers: {len(data['teachers'])}   ·   Classes: {len(data['classes'])}   ·   "
                f"Master: {len(data['master'])} (day by day)   ·   Labs & Fields: {len(data['rooms'])}",
                f"Days: {', '.join(x['label'] for x in data['days'])}    ·    Lessons a day: {len(lessons)}"
                + (f"  ({lessons[0]['time'].split('-')[0]} – {lessons[-1]['time'].split('-')[-1]})"
                   if lessons and lessons[0]['time'] else ""),
                f"Breaks: {', '.join(breaks) or 'none'}",
                "FET stamp:  " + ((f"FET {data['fet']['version']}  ·  {data['fet']['when'] or 'time not found'}")
                                  if data.get("fet", {}).get("version") else "not found in these files (the app will still say the timetable was made with FET)"),
                f"Teacher names: {sum(1 for t in data['teachers'] if t['name'])} of {len(data['teachers'])}"
                + ("  (names replace codes on class & master timetables)" if all(t['name'] for t in data['teachers'])
                   else "  ⚠ some teachers have only a code — add their names in FET (Long name) and export again"),
            ]
            self.run.ui(lambda: self.after_scan(data, lines, il))
        self.run.run(go)

    def changed_teachers(self):
        return MV.affected_teachers(self.orig_data, self.data) if self.data is not None else []

    def review_changes(self, ask=False):
        """Final preview: BEFORE and AFTER for the affected teachers only. ask=True: returns True if the user chose to publish."""
        if self.data is None or self.orig_data is None:
            messagebox.showinfo("Final preview", "Load a timetable first (“Import & Run”).")
            return False
        if not self.changed_teachers():
            if not ask:
                messagebox.showinfo("Final preview", "No lessons were moved, so no teacher's timetable is affected.\n\n"
                                                     "What teachers get is exactly what was imported.")
            return True if ask else False
        w = MV.ReviewWindow(self, self.orig_data, self.data, ask=ask)
        self.root.wait_window(w.win)
        if ask and w.result:
            self._reviewed = self.data
        return w.result

    def apply_moves(self, data, n, extra="", stay=False):
        """The Move lessons tab hands back the changed timetable; Publish now uses it."""
        self.data = data
        self.ran = True
        self.update_pub_state()
        old = self.summary.get("1.0", "end").rstrip()
        old = old.split("\n\n✎")[0]
        self.set_summary(old + f"\n\n✎ {n} change(s) made in “Move lessons”" + (f" — {extra}" if extra else "") +
                         ". Press Publish to send the changed timetable "
                               "to teachers' phones. (Your own file is not changed.)")
        self.run.log(f"✔ {n} lesson move(s) applied" + (f" ({extra})" if extra else "") +
                     ". Press Publish to send them to teachers.")
        if not stay:
            self.nb.select(self.tab_pub)

    def reset_run(self):
        """A new timetable was loaded: Run (then Publish) must be done again."""
        self.ran = False
        self.applied_con = False
        self.btn_pub.configure(state="disabled")
        for nm in ("btn_run", "btn_run2"):
            if hasattr(self, nm):
                getattr(self, nm).configure(state="disabled")

    def rerun_needed(self):
        """(Old: rules switched on / off.) The rules in operation are always kept now, so never."""
        return False

    def rules_active(self):
        """Moves always keep the rules in operation."""
        return True

    def mobile_ok(self):
        """May this school send timetables to phones? (owner: the school's switch; school copy: as Cyrus set it)"""
        sch = self.current_school()
        if not sch:
            return False
        if self.pub.is_school:
            return getattr(self, "_mobile_here", None) is not False
        return bool(self.pub.mobile_on(self.pub.school(sch["code"])) and not self.pub.is_suspended(sch["code"]))

    def update_pub_state(self):
        self.update_path_steps()
        self._update_pub_state()

    def _update_pub_state(self):
        if self.current_school() and not self.mobile_ok():
            self.btn_pub.configure(state="disabled")
            self.pub_status.configure(text=(
                "🖥 PC ONLY — the mobile app is not switched on for this school, so nothing is sent to phones. "
                "Use “Import & Run” to preview and print every timetable on this computer. " +
                ("To use phones, contact Cyrus Ireri, " + core.LOCKED_CONTACT + "." if self.pub.is_school else
                 "To allow phones: Schools tab → click the school → 📱 Allow mobile app.")))
            return
        ok = bool(self.data is not None and self.current_school())
        self.btn_pub.configure(state="normal" if ok else "disabled")
        if hasattr(self, "pub_status"):
            self.pub_status.configure(text=(
                f"Ready — {(self.current_school() or {}).get('name', '')}." if ok else
                "Locked: on “Import & Run”, add the FET folder (or aSc PDF) first." if self.data is None else
                "Locked: choose the school on “Import & Run”."))
        if hasattr(self, "btn_run2"):
            self.btn_run2.configure(state="normal" if self.ran else "disabled")

    def run_once(self, again=False, mode="preview"):
        """Step 2 (again=False): the timetable exactly as loaded, no rules, preview.
        Step 4 (again=True): apply the rules if ticked, preview again (move lessons from there if need be)."""
        if not self.data:
            messagebox.showinfo("Run", "Add a folder or import a timetable first.")
            return
        mv = self.move
        if mv.board is not None and mv.board.moves:                  # changes waiting? keep them before the rules change
            mv.use_changes(stay=True)
        use = bool(again)
        self.applied_con = use
        mv.src = None                                                # the screen is rebuilt with the rules in force
        if use:
            line = self.ops_line()
        else:
            line = "The timetable exactly as imported."
        old = self.summary.get("1.0", "end").rstrip().split("\n\n▶")[0]
        if again:
            tail = "\nLook it over, then follow the next numbered button."
        else:
            tail = "\nLook it over, then follow the next numbered button."
        self.set_summary(old + "\n\n▶ " + line + tail)
        self.ran = True
        self.update_pub_state()
        self.run.log("Preview open — the timetable exactly as FET or aSc made it.")
        self.move.open_preview(first=not again, mode=mode)

    def con_toggled(self):
        self.con.save_on()
        self.update_pub_state()
        if self.rerun_needed():
            self.run.log("Rules switched " + ("on" if self.use_con.get() else "off") +
                         " — press “✔ Check the timetable with these rules” before publishing.")

    def current_rules(self):
        """What may never happen when a lesson is moved: a clash (teacher, class, lab in two places) or a break lesson."""
        return self.mandatory_rules()

    def advice_rules(self):
        """The rules FET made the timetable with: they never block a move, they only point at the best places."""
        return list(self.rules_op)

    def _old_current_rules(self):
        """The rules every move keeps: no clashes, no lessons in breaks + the RULES IN OPERATION (from FET).
        Rules at 100 % may never be broken; preferred ones only rank the places (★ = fewest warnings)."""
        return self.mandatory_rules()

    def mandatory_rules(self):
        # moving only checks what is physically impossible: nobody in two places at once, no lesson in a break
        return [r for r in K.defaults() if r["type"] in ("teacher_clash", "class_clash", "room_clash", "break_lessons")]

    def extra_rules(self):
        sch = self.current_school()
        rules = self.con.rules if (sch and self.con.code == sch["code"]) else (self.con.rules_for(sch["code"]) if sch else [])
        return [r for r in rules if r.get("enabled", True)]

    def check_constraints(self, data=None):
        data = data or self.data
        self.report = K.run(data, self.current_rules()) if data else None
        return self.report

    # ------------------------------------------------------------------ RULES IN OPERATION (from FET)
    def _ops_file(self, code):
        return core.DATA_DIR / "rules_in_operation" / f"{code}.fet"

    def load_ops(self, data, sch):
        """A timetable was read: its rules in operation - from the folder's .fet file, else the ones pasted before for
        this school. Returns the timetable with each lesson's FET activity (needed by some FET rules)."""
        self.rules_op, self.ops_src, self.ops_notes = [], "", []
        self._ops_cache = (None, None)
        folder = self.folder if (self.folder is not None and Path(self.folder).is_dir()) else None
        try:
            fet = FR.find_fet(folder) if folder else None
            if fet:
                text = fet.read_text("utf-8", errors="replace")
                data, rules, notes = FR.read_text(text, data, source=fet.name)
                src = fet.name
                if sch:
                    self._save_ops_text(sch["code"], text)
            elif sch and self._ops_file(sch["code"]).exists():
                data, rules, notes = FR.read_text(self._ops_file(sch["code"]).read_text("utf-8", errors="replace"), data,
                                                  source="the rules pasted before")
                src = "the rules pasted before"
            else:
                return data
        except Exception as e:
            self.run.log(f"⚠ The rules in operation could not be read: {e}")
            return data
        self._set_ops(rules, src, notes)
        return data

    def _save_ops_text(self, code, text):
        try:
            f = self._ops_file(code)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        except OSError:
            pass

    def _set_ops(self, rules, src, notes):
        self.rules_op = [r for r in rules if r.get("type") != "break_lessons"]     # breaks are always kept anyway
        self.ops_src, self.ops_notes = src, list(notes)
        self._ops_cache = (None, None)
        self.move.src = None                                     # the moving screen is rebuilt with these rules
        for line in notes:
            self.run.log("📋 " + line)
        self.update_path_steps()
        self.refresh_ops()

    def ops_counts(self):
        must = sum(1 for r in self.rules_op if r.get("severity") == K.ERR)
        return must, len(self.rules_op) - must

    def ops_report(self):
        """The rules in operation checked against the timetable as it is now (kept while the timetable is the same)."""
        if self.data is None:
            return None
        if self._ops_cache[0] is not self.data:
            try:
                self._ops_cache = (self.data, K.run(self.data, self.mandatory_rules()))
            except Exception:
                self._ops_cache = (self.data, None)
        return self._ops_cache[1]

    def ops_line(self):
        n = self.my.count() if hasattr(self, "my") else 0
        obs = hasattr(self, "my") and self.my.observe()
        return (f"My rules: {n} written — " + ("🔒 the timetable OBSERVES them: moves keep them." if obs else
                                               "press 📝 My rules to run them on the timetable.") if n else
                "My rules: none written yet (optional).")

    def refresh_ops(self):
        if hasattr(self, "ops_lbl"):
            self.ops_lbl.configure(text=self.ops_line())

    def paste_ops(self):
        if self.data is None:
            messagebox.showinfo("Rules", "Add the timetable first (FET folder or aSc PDF), then paste its rules.",
                                parent=self.rules_win)
            return
        w = tk.Toplevel(self.rules_win)
        w.title("Paste the rules in operation")
        w.geometry("820x520")
        w.configure(bg=U.CREAM)
        w.transient(self.rules_win)
        tk.Label(w, bg=U.CREAM, fg=U.NAVY, font=("Segoe UI Semibold", 10), wraplength=780, justify="left",
                 text="Open the FET file of this timetable (…_data_and_timetable.fet) with Notepad, press Ctrl+A, Ctrl+C, "
                      "then click below and press Ctrl+V. A part of the file (the constraints only) also works."
                 ).pack(anchor="w", padx=12, pady=(10, 6))
        box = tk.Text(w, wrap="none", font=("Consolas", 9), relief="solid", bd=1)
        box.pack(fill="both", expand=True, padx=12)
        bar = tk.Frame(w, bg=U.CREAM)
        bar.pack(fill="x", padx=12, pady=8)

        def use():
            self._use_ops_text(box.get("1.0", "end"), "the pasted rules", parent=w)
        ttk.Button(bar, text="Use these rules", style="Accent.TButton", command=use).pack(side="right")
        ttk.Button(bar, text="Cancel", command=w.destroy).pack(side="right", padx=8)
        self.front(w)
        box.focus_set()

    def read_ops_file(self):
        if self.data is None:
            messagebox.showinfo("Rules", "Add the timetable first.", parent=self.rules_win)
            return
        f = filedialog.askopenfilename(parent=self.rules_win, title="Choose the FET file (.fet)",
                                       filetypes=[("FET file", "*.fet"), ("All files", "*.*")])
        if f:
            self._use_ops_text(Path(f).read_text("utf-8", errors="replace"), Path(f).name)

    def _use_ops_text(self, text, src, parent=None):
        parent = parent or self.rules_win
        moved = self.orig_data is not None and self.data is not self.orig_data and PS.moved_cells(self.orig_data, self.data)
        if moved and not messagebox.askyesno("Rules", "New rules start again from the timetable as imported — the "
                                             "lessons moved so far are undone.\n\nContinue?", parent=parent):
            return
        try:
            data, rules, notes = FR.read_text(text, self.orig_data or self.data, source=src)
        except ValueError as e:
            messagebox.showerror("Rules", str(e), parent=parent)
            return
        if not rules:
            messagebox.showinfo("Rules", "No FET rules were found in that text.", parent=parent)
            return
        sch = self.current_school()
        if sch:
            self._save_ops_text(sch["code"], text)
        self.data = self.orig_data = data
        self._set_ops(rules, src, notes)
        if parent is not self.rules_win:
            parent.destroy()
        must, pref = self.ops_counts()
        messagebox.showinfo("Rules in operation", f"{len(self.rules_op)} rules read: {must} at 100 % (never broken by "
                            f"a move) and {pref} preferred.\n\n" + "\n".join(notes), parent=self.rules_win)

    def clear_ops(self):
        if not self.rules_op:
            return
        if not messagebox.askyesno("Rules", "Remove the rules in operation for this timetable? Moves will then keep "
                                   "only the basics (no clashes, no lessons in breaks).", parent=self.rules_win):
            return
        sch = self.current_school()
        if sch:
            try:
                self._ops_file(sch["code"]).unlink()
            except OSError:
                pass
        self._set_ops([], "", [])

    def check_ops(self):
        if self.data is None:
            messagebox.showinfo("Rules", "Add the timetable first.", parent=self.rules_win)
            return
        rep = self.ops_report() or K.run(self.data, self.mandatory_rules())
        self.run.log(K.summary_line(rep).replace("  Click “View constraint report”.", ""))
        CU.show_report(self.rules_win, rep, title="Rules in operation — this timetable", info=True,
                       on_fix=None)

    def list_ops(self):
        w = tk.Toplevel(self.rules_win)
        w.title("Rules in operation")
        w.geometry("900x560")
        w.transient(self.rules_win)
        tv = ttk.Treeview(w, columns=("lvl", "rule"), show="headings")
        tv.heading("lvl", text="In FET")
        tv.heading("rule", text="Rule")
        tv.column("lvl", width=150, stretch=False)
        tv.column("rule", width=720)
        sb = ttk.Scrollbar(w, command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        for r in self.mandatory_rules():
            lvl = ("100 % — never broken" if r.get("severity") == K.ERR else f"{r.get('weight', '')} % — preferred"
                   ) if r.get("src") == "FET" else ("always" if r.get("severity") == K.ERR else "preferred")
            tv.insert("", "end", values=(lvl, K.describe(r)))
        self.front(w)

    def run_extra(self):
        """The optional extra checks: for information. They never block moving or publishing."""
        if self.data is None:
            messagebox.showinfo("Extra checks", "Add the timetable first.", parent=self.rules_win)
            return
        rules = self.extra_rules()
        if not rules:
            messagebox.showinfo("Extra checks", "Tick at least one rule first.", parent=self.rules_win)
            return
        rep = K.run(self.data, rules)
        self.run.log("Extra checks: " + ("✔ the timetable passes them." if not rep["issues"] else
                     f"{rep['errors']} problem(s), {rep['warnings']} warning(s) — correcting is up to you; "
                     "publishing is allowed."))
        CU.show_report(self.rules_win, rep, title="Extra checks — for your information", info=True,
                       on_fix=None)

    def view_constraint_report(self):
        if not self.data:
            messagebox.showinfo("Constraints", "Load a timetable first (FET folder or aSc PDF).")
            return
        CU.show_report(self.root, self.check_constraints())

    def import_sheet(self):
        sch = self.current_school()
        if not sch:
            messagebox.showinfo("Choose the school", "Choose the school at the top first. An "
                                                     "aSc PDF does not say which school it is for.")
            return
        fs = filedialog.askopenfilenames(title="Choose the aSc PDFs: the class timetables and the teacher timetables",
                                         filetypes=[("aSc Timetables PDF", "*.pdf")])
        if not fs:
            return
        paths = [Path(f) for f in fs]
        pdfs = [p for p in paths if p.suffix.lower() == ".pdf"]
        if not pdfs or len(pdfs) != len(paths):
            messagebox.showinfo("aSc timetable", "Choose the PDFs printed from aSc Timetables: the class timetables and "
                                                 "the teacher timetables, both together.")
            return
        path = paths[0]
        self.folder = path
        self.folder_lbl.configure(text="File: " + "  +  ".join(str(p) for p in paths))
        self.data = None
        self.reset_run()
        self.check_lbl.configure(text="", style="Card.TLabel")
        typed = core.tt_name(self.tt_var.get())
        tname = typed or core.tt_name(path.stem.replace("_", " ").replace("-", " "))

        def go():
            nonlocal tname
            self.run.log("Reading " + ", ".join(p.name for p in paths) + " …")
            try:
                data = asc_pdf.scan_pdfs(pdfs, school=sch["name"], timetable="", log=self.run.log)
                tname = core.tt_name(data.get("pdf_title", "")) or typed or tname   # the name printed on the PDF
                il = [x for x in (sch["name"].upper(), (tname or "").upper()) if x]
                data.update(institution=" ".join(il), institution_lines=il, institutions={"classes": " ".join(il)})
            except asc_pdf.PdfError as e:
                self.run.log(f"✖ {e}")
                self.run.ui(lambda e=e: messagebox.showerror("aSc timetable", str(e)))
                return
            P = data["periods"]
            lessons = [p for p in P if not p["brk"]]
            lines = [
                "School:   " + sch["name"],
                "Timetable:  " + (tname or "-"),
                "Source:  " + ", ".join(p.name for p in paths) + "  (aSc Timetables PDF)",
                "",
                f"Teachers: {len(data['teachers'])}   ·   Classes: {len(data['classes'])}   ·   "
                f"Labs & Fields: {len(data['rooms'])}",
                f"Days: {', '.join(x['label'] for x in data['days'])}    ·    Lessons a day: {len(lessons)}",
                f"Breaks: {', '.join(p['label'] for p in P if p['brk']) or 'none'}",
                "",
                "Check these numbers against your file before you publish.",
            ]
            self.run.ui(lambda: self.after_scan(data, lines, [sch["name"], tname]))
        self.run.run(go)

    def ask_ui(self, fn):
        """Run a dialog on the window thread from the worker thread and return its answer."""
        import threading
        box, ev = [], threading.Event()
        self.run.ui(lambda: (box.append(fn()), ev.set()))
        ev.wait()
        return box[0]

    def after_scan(self, data, lines, il):
        self.set_summary("\n".join(lines))
        sch = self.match_school(data)
        if self.pub.is_school and self.pub.bound_school and not sch:
            self.check_lbl.configure(text=f"✖  This FET timetable is not for {self.pub.bound_school['name']}. This copy "
                                          "publishes only its own school's timetables.", style="Bad.TLabel")
            return
        if sch:
            self.run.log(f"✔ Recognised {sch['name']}.")
        elif not self.pub.can_register():
            pass
        else:
            name = core.clean_name(il[0]).upper()
            if messagebox.askyesno(
                    "New school",
                    f"This timetable is for:\n\n{name}\n\nwhich is not registered yet.\n\nRegister it now?\n"
                    "Its own PREPFIX copy is made in FOR_SCHOOLS. Check the spelling (you can correct it on the next "
                    "screen, or rename the school later on the Schools tab)."):
                fixed = simpledialog.askstring("Register a school", "School name (as teachers know it):",
                                               initialvalue=name, parent=self.root)
                fixed = core.clean_name(fixed or "")
                if fixed:
                    try:
                        sch = self.pub.register_school(fixed)
                        self.apply_edition()
                    except core.PublishError as e:
                        messagebox.showerror("Problem", str(e))
                        return
        if not sch:
            self.check_lbl.configure(text="⚠  This timetable's school is not registered. Register it to publish.",
                                     style="Bad.TLabel")
            return
        self.reload_schools(select=sch["name"])
        given = core.tt_name(" ".join(il[1:]))                      # the name FET / aSc gave it (can be changed)
        if given or not self.pub.timetables(sch["code"]):
            self.set_tt(given or core.tt_name(sch["name"]))
        self.tt_changed()
        self.rules_op = []                                        # FET's rules: used only to SUGGEST good places
        if self.folder is not None and Path(self.folder).is_dir():
            try:
                fet = FR.find_fet(self.folder)
                if fet:
                    data, rules, _notes = FR.read_text(fet.read_text("utf-8", errors="replace"), data, source=fet.name)
                    self.rules_op = [r for r in rules if r.get("type") != "break_lessons"]
            except Exception as e:
                self.rules_op = []
                pass
        self.data = data
        self.orig_data = data                                     # as imported: the "before" of the final preview
        self._reviewed = None
        self.reset_run()
        self.btn_run.configure(state="normal")
        self.check_lbl.configure(text=f"✔  School: {sch['name']}.  Now use the buttons in 2.", style="Ok.TLabel")
        self.refresh_tt_notes()
        self.after_import_check()
        if not self.move.after_load():                             # loaded from "Move lessons"? that screen opens instead
            self.run.log("Now: check the timetable name, then Preview → Publish.")

    # ------------------------------------------------------------------ the two paths (A: preview & print, B: check & move)
    def after_import_check(self):
        try:
            self.check_rep = CH.report(self.data)
            line = self.check_rep["line"]
        except Exception as e:                                       # the check must never stop the import
            self.check_rep, line = None, f"Check could not run: {e}"
        self.check_line.configure(text=line, style="Ok.TLabel" if self.check_rep and not self.check_rep["problems"]
                                  else "Card.TLabel")
        self.btn_fullcheck.configure(state="normal")
        self.path = None
        self.mark_path()
        self.update_path_steps()

    def update_path_steps(self):
        """Every button always answers a click: it runs, or says to add the timetable first."""
        if not hasattr(self, "steps"):
            return
        loaded = self.data is not None
        if not hasattr(self, "_step_text"):
            self._step_text = [b.cget("text") for b in self.steps]
        for b, txt in zip(self.steps, self._step_text):
            b.configure(state="normal", text=("🔒 " if not loaded else "") + txt)
        if hasattr(self, "rules_state"):
            self.rules_state.configure(text="", fg=U.NAVY)          # rules are kept in FET / aSc, not here
        self.refresh_ops()

    def mark_path(self):
        pass

    def teacher_change(self):
        """Path B, step 5: a teacher leaves - hand the lessons to another teacher, under the rules."""
        if self.data is None:
            return
        mv = self.move
        if mv.board is not None and mv.board.moves:
            mv.use_changes(stay=True)
        TU.TeacherChange(self)

    def step(self, fn):
        if self.data is None:
            messagebox.showinfo("Timetable", "First add the timetable: step 1 at the top — “FET folder”, or "
                                             "“aSc PDF”.")
            return
        fn()

    def path_step(self, key, fn):                   # kept for older callers
        self.step(fn)

    def origin(self, data=None):
        """The line printed on every timetable: the program that created it, with its date and time."""
        data = self.data if data is None else data
        src, st = str(data.get("source") or ""), data.get("fet") or {}
        if src.startswith("aSc"):
            text = "Created with aSc Timetables"
        else:
            text = "Created with FET" + (f" {st['version']}" if st.get("version") else "")
        if st.get("when"):
            text += f" on {st['when']}"
        return {"path": "A", "text": text}

    def browser_preview(self, final=False, start="teachers"):
        """The teachers' app on this computer (http://127.0.0.1), full screen, with the timetable as it is now."""
        if PS.CLOSED["msg"]:
            messagebox.showerror("Preview", PS.CLOSED["msg"])
            return
        sch = self.current_school()
        if self.data is None or not sch:
            messagebox.showinfo("Preview", "Add the FET folder and choose the school first.")
            return
        marks = {"moved": PS.moved_cells(self.orig_data, self.data)} if final and self.orig_data is not None else {}
        if self.rules_op and (self.ops_report() or {}).get("errors"):
            try:                                             # what breaks a rule in operation: red, with the rule
                marks["bad"] = AF.bad_marks(AF.fix(self.data, self.current_rules(), max_moves=0)["left"])
            except Exception:
                pass
        try:
            url = self.pv.show(sch["code"], sch["name"], dict(self.data, origin=self.origin(), notes=self.tt_notes()),
                               self.tt_var.get() or "PREVIEW", marks, desktop=not self.mobile_ok())
        except Exception as e:
            messagebox.showerror("Preview", f"The preview could not start: {e}")
            return
        full = PS.open_full_screen(url + f"#pages/{start}", core.DATA_DIR)
        n = len((marks or {}).get("moved", []))
        self.run.log(("Preview final (" + (f"{n} moved lesson box(es) marked MOVED" if n else "no lessons moved") + ")"
                      if final else "Preview") + f" open on this computer: {url}  — nothing is published."
                     + ("" if full else "  (Press F11 in the browser for full screen.)"))
        if not self.ran:                                         # looking at it counts as the Run (Publish unlocks)
            self.ran = True
            self.applied_con = False
            self.update_pub_state()

    # ---- TOOLKIT PASSWORD: Cyrus's PREPFIX opens only with it; delete / suspend / restore / send ask for it again ----
    def _pw_box(self, title, lines, fields=1, forgot=False, err=""):
        """A small password window. Returns the typed password(s), "FORGOT", or None (cancel).
        A mistake is shown in red inside the window itself (a separate message could open behind the opening
        screen and PREPFIX would look stuck)."""
        sp = getattr(self.root, "_splash", None)
        if sp is not None and getattr(sp, "w", None) is not None:
            try:
                sp.w.withdraw()                       # the opening screen steps aside while the password is asked
            except tk.TclError:
                pass
        d = tk.Toplevel(self.root)
        d.title(title)
        d.configure(bg=U.CREAM)
        d.resizable(False, False)
        res = {"v": None}
        tk.Label(d, text=lines, bg=U.CREAM, font=("Segoe UI", 11), justify="left", wraplength=380).pack(
            anchor="w", padx=18, pady=(16, 8))
        if err:
            tk.Label(d, text="✖ " + err, bg=U.CREAM, fg="#B5463A", font=("Segoe UI", 11, "bold"), justify="left",
                     wraplength=380).pack(anchor="w", padx=18, pady=(0, 8))
        es = []
        for i in range(fields):
            if fields > 1:
                tk.Label(d, text=("Password" if i == 0 else "Type it again"), bg=U.CREAM, fg="#667085").pack(
                    anchor="w", padx=18)
            e = ttk.Entry(d, show="•", width=32, font=("Segoe UI", 12))
            e.pack(padx=18, pady=(0, 8), anchor="w")
            es.append(e)
        bar = tk.Frame(d, bg=U.CREAM)
        bar.pack(fill="x", padx=18, pady=(4, 14))

        def ok(_=None):
            res["v"] = [e.get() for e in es] if fields > 1 else es[0].get()
            d.destroy()

        def fg():
            res["v"] = "FORGOT"
            d.destroy()
        ttk.Button(bar, text="OK", style="Accent.TButton", command=ok).pack(side="right")
        ttk.Button(bar, text="Cancel", command=d.destroy).pack(side="right", padx=8)
        if forgot:
            ttk.Button(bar, text="Forgot password?", command=fg).pack(side="left")
        for e in es:
            e.bind("<Return>", ok)
        d.bind("<Escape>", lambda e: d.destroy())
        es[0].focus_set()
        try:
            d.attributes("-topmost", True)
        except tk.TclError:
            pass
        d.grab_set()
        self.root.wait_window(d)
        return res["v"]

    def _new_tk_password(self, why):
        err = ""
        while True:
            v = self._pw_box("PREPFIX — password", why + "\n\nChoose a password (at least 4 characters). You will "
                             "type it to open PREPFIX and before deleting, suspending, restoring or sending to phones.", 2,
                             err=err)
            if v is None:
                return False
            if v[0] != v[1]:
                err = "The two passwords are not the same. Try again."
                continue
            try:
                self.pub.set_tk_password(v[0])
            except core.PublishError as e:
                err = str(e)
                continue
            try:
                self.pub.autosave()
            except Exception:
                pass
            return True

    def owner_login(self):
        if not self.pub.has_tk_password():
            return self._new_tk_password("Protect your PREPFIX with a password.")
        err = ""
        for tries in range(5):
            v = self._pw_box("PREPFIX — sign in", "Type your PREPFIX password.", forgot=True, err=err)
            if v is None:
                return False
            if v == "FORGOT":
                if self.pub.is_school:
                    k = self._pw_box("Forgot password", "Call Cyrus Ireri, " + core.LOCKED_CONTACT + ", for today's "
                                     "reset code, then type it here.")
                    ok = k is not None and self.pub.reset_code_ok(k)
                else:
                    k = self._pw_box("Forgot password", "Type your OWNER KEY (the same key as in Setup) to choose a new "
                                     "password.")
                    ok = k is not None and bool(k.strip()) and k.strip() == self.pub.owner_key()
                if k is None:
                    continue
                if ok:
                    return self._new_tk_password("Accepted.")
                err = "That code is not right." if self.pub.is_school else "That is not your owner key."
                continue
            if self.pub.check_tk_password(v):
                return True
            left = 4 - tries
            err = f"Wrong password. {left} more tr{'ies' if left != 1 else 'y'}." if left else ""
        return False

    def need_pw(self, what):
        """Vital actions on Cyrus's PREPFIX ask for the password again."""
        v = self._pw_box("Password needed", f"{what}\n\nType your PREPFIX password to continue.")
        if v is None:
            return False
        if self.pub.check_tk_password(v):
            return True
        messagebox.showerror("Password", "Wrong password. Nothing was done.")
        return False

    def show_reset_code(self):
        code = self.selected_code()
        sch = self.pub.school(code) if code else None
        if not sch:
            messagebox.showinfo("Password reset code", "First click the school in the list.")
            return
        if not self.need_pw("Show a password reset code for a school."):
            return
        c = self.pub.reset_code(code)
        messagebox.showinfo("Password reset code", f"{sch['name']}\n\nToday's reset code:   {c}\n\nThe school presses "
                            "“Forgot password?” in its PREPFIX and types this code (it works today and tomorrow).")

    def change_tk_password(self):
        if self.need_pw("Change the PREPFIX password."):
            if self._new_tk_password("New password."):
                self.run.log("✔ PREPFIX password changed.")

    def front(self, w):
        """Bring a window in front of the full-screen PREPFIX window (on Windows it can open behind it)."""
        w.deiconify()
        try:
            w.attributes("-topmost", True)
            w.after(400, lambda: w.attributes("-topmost", False))
        except tk.TclError:
            pass
        w.lift()
        w.focus_force()

    def open_rules(self):
        self.my.open()
        return
        self.con.refresh()
        self.refresh_ops()
        try:
            self.rules_win.state("zoomed")
        except tk.TclError:
            pass
        self.front(self.rules_win)

    def path_constraints(self):                      # kept for older callers
        self.check_ops()

    def path_fix(self):
        """Path B step 3: PREPFIX moves lessons until the rules are obeyed. What it cannot fix is listed with the
        rule it breaks, and marked in red on the preview."""
        if self.data is None:
            messagebox.showinfo("Fix", "Load a timetable first.")
            return
        mv = self.move
        if mv.board is not None and mv.board.moves:                  # moves waiting in "Move by hand": keep them first
            mv.use_changes(stay=True)
        rules, before = self.current_rules(), self.data
        self.run.log("🛠 Streamlining: PREPFIX moves lessons so the timetable keeps your rules (no clashes, no breaks)…")

        def go():
            last = [time.time()]

            def prog(done, total, text):
                if time.time() - last[0] > 3:
                    last[0] = time.time()
                    self.run.log("   🛠 " + text)
            res = AF.fix(before, rules, prog)
            self.run.ui(lambda: self.show_fix(res, before))
        self.run.run(go)

    def show_fix(self, res, before):
        sch = self.current_school() or {}
        if res["moves"]:
            self.apply_moves(res["data"], len(res["moves"]), extra="made by 🛠 Fix", stay=True)
        self.fix_left = res["left"]
        errs = [x for x in res["left"] if x["sev"] == K.ERR]
        b, a = res["before"], res["after"]
        self.run.log(f"🛠 Fix: {len(res['moves'])} move(s). Must-fix problems {b[0]} → {a[0]}"
                     + (f" ({a[0]} could not be fixed — marked in red on the preview)." if a[0] else " — every rule obeyed."))
        win = tk.Toplevel(self.root)
        win.title("Fix — what PREPFIX did")
        win.geometry("900x620")
        win.configure(bg=U.CREAM)
        win.transient(self.root)
        head = (f"✔ Fixed. {len(res['moves'])} lesson move(s); every must-pass rule is now obeyed." if not a[0] else
                f"{len(res['moves'])} lesson move(s). {b[0] - a[0]} of {b[0]} must-fix problem(s) fixed — "
                f"{a[0]} could NOT be fixed (listed in red with the rule, and marked in red on the preview).")
        if not res["moves"] and not b[0]:
            head = "Nothing to fix: the timetable already obeys every must-pass rule."
        tk.Label(win, text=head, bg=U.CREAM, fg=U.GREEN if not a[0] else U.RED, wraplength=860, justify="left",
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=14, pady=(12, 6))
        box = tk.Frame(win)
        box.pack(fill="both", expand=True, padx=14)
        sb = ttk.Scrollbar(box)
        sb.pack(side="right", fill="y")
        txt = tk.Text(box, wrap="word", font=("Segoe UI", 10), bg="white", relief="flat", padx=10, pady=8,
                      yscrollcommand=sb.set)
        txt.pack(fill="both", expand=True)
        sb.config(command=txt.yview)
        txt.tag_configure("h", font=("Segoe UI Semibold", 11), foreground=U.NAVY)
        txt.tag_configure("bad", foreground=U.RED, font=("Segoe UI Semibold", 10))
        txt.tag_configure("why", foreground="#7A5A00")
        txt.tag_configure("ok", foreground=U.GREEN)
        if errs:
            txt.insert("end", "COULD NOT BE FIXED — the rule each one breaks\n", "h")
            for num in sorted({x["num"] for x in errs}):
                its = [x for x in errs if x["num"] == num]
                txt.insert("end", f"\n● Rule {num}: {its[0]['rule']}\n", "bad")
                whys = {x["why"] for x in its}
                for x in its:
                    txt.insert("end", f"     – {x['msg']}.\n")
                    if len(whys) > 1:
                        txt.insert("end", f"        Why: {x['why']}\n", "why")
                if len(whys) == 1:
                    txt.insert("end", f"     Why: {its[0]['why']}\n", "why")
            txt.insert("end", "\n")
        if res["moves"]:
            txt.insert("end", f"MOVES MADE ({len(res['moves'])})\n", "h")
            for i, m in enumerate(res["moves"], 1):
                txt.insert("end", f"  {i}. {m}\n", "ok")
        warns = [x for x in res["left"] if x["sev"] != K.ERR]
        if warns:
            txt.insert("end", f"\nWARNINGS LEFT ({len(warns)}) — publishing is allowed\n", "h")
            for x in warns[:60]:
                txt.insert("end", f"  – Rule {x['num']}: {x['msg']}.\n")
        txt.configure(state="disabled")
        bar = tk.Frame(win, bg=U.CREAM)
        bar.pack(fill="x", padx=14, pady=10)

        def undo():
            self.data = before
            self.fix_left = None
            self.update_pub_state()
            self.run.log("↶ The fixes were undone — the timetable is as it was before 🛠 Fix.")
            win.destroy()

        def save():
            f = filedialog.asksaveasfilename(parent=win, defaultextension=".txt", initialfile="PREPFIX fix report.txt",
                                             filetypes=[("Text", "*.txt")])
            if f:
                Path(f).write_text(AF.report_text(res, sch.get("name", "")) + f"\n\n{core.LOCKED_BRAND} · "
                                   f"{core.LOCKED_CONTACT}\n", encoding="utf-8")
        ttk.Button(bar, text="Save report…", command=save).pack(side="left")
        if res["moves"]:
            ttk.Button(bar, text="↶  Undo the fixes", command=undo).pack(side="left", padx=8)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
        ttk.Button(bar, text="👁  Preview as printed" + (" (problems in red)" if errs else ""), style="Accent.TButton",
                   command=lambda: (win.destroy(), self.browser_preview(True))).pack(side="right", padx=8)

    def show_check_report(self, final=False):
        if self.data is None:
            return
        rep = CH.report(self.data)
        sch = self.current_school() or {}
        text = CH.report_text(rep, sch.get("name", ""))
        if final:
            n = len(PS.moved_cells(self.orig_data, self.data)) if self.orig_data is not None else 0
            con = "\n\nRULES IN OPERATION\n" + K.report_text(self.check_constraints())
            text = (f"FINAL CHECK — the timetable as it will be published"
                    f"{f' ({n} moved lesson box(es))' if n else ' (no lessons moved)'}\n\n") + text + con
        win = tk.Toplevel(self.root)
        win.title("Final check" if final else "Check report")
        win.geometry("860x600")
        win.configure(bg=U.CREAM)
        win.transient(self.root)
        tk.Label(win, text=rep["line"], bg=U.CREAM, fg=U.GREEN if not rep["problems"] else U.RED, wraplength=820,
                 justify="left", font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=14, pady=(12, 6))
        box = tk.Frame(win)
        box.pack(fill="both", expand=True, padx=14)
        sb = ttk.Scrollbar(box)
        sb.pack(side="right", fill="y")
        txt = tk.Text(box, wrap="word", font=("Consolas", 10), bg="white", relief="flat", padx=10, pady=8,
                      yscrollcommand=sb.set)
        txt.pack(fill="both", expand=True)
        sb.config(command=txt.yview)
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        bb = tk.Frame(win, bg=U.CREAM)
        bb.pack(fill="x", padx=14, pady=10)

        def save():
            f = filedialog.asksaveasfilename(parent=win, defaultextension=".txt", initialfile="PREPFIX check report.txt",
                                             filetypes=[("Text", "*.txt")])
            if f:
                Path(f).write_text(text + f"\n\n{core.LOCKED_BRAND} {core.LOCKED_CONTACT}\n", encoding="utf-8")
        ttk.Button(bb, text="Save as text…", command=save).pack(side="left")
        ttk.Button(bb, text="Close", command=win.destroy).pack(side="right")

    def goto_pub_tab(self):
        if self.data is not None and not self.ran:
            self.browser_preview(False)
        self.nb.select(self.tab_pub)

    def publish(self):
        sch = self.current_school()
        if not self.data or not sch:
            return
        if not self.pub.ready:
            messagebox.showinfo("Setup", "Do the one-time Setup first.")
            self.nb.select(self.tab_set)
            return
        if self.changed_teachers() and self._reviewed is not self.data:      # moved lessons: one last look, before / after
            if not self.review_changes(ask=True):
                return
        tname = core.tt_name(self.tt_var.get())
        if len(tname) < 2:
            messagebox.showinfo("Timetable name", "Type a name for this timetable first.")
            return
        old = self.pub.existing_timetable(sch["code"], tname)
        d = self.data
        head = (f"REPLACE the timetable “{old['name']}” of {sch['name']}?\n(last published {when(old.get('updated', ''))})"
                if old else f"ADD a new timetable “{tname}” to {sch['name']}?\n(the school's other timetables stay as they are)")
        msg = (f"{head}\n\nTeachers: {len(d['teachers'])}   Classes: {len(d['classes'])}\n"
               f"Master: {len(d['days'])} days   Labs & Fields: {len(d['rooms'])}")
        lock = core.suggest_lock_words(sch["name"])
        if any(not fet_reader.institution_matches(v, lock) for v in d.get("institutions", {}).values()):
            messagebox.showerror("Wrong school", f"The FET timetable says “{d['institution']}”.\n\nIt cannot be "
                                 f"published to {sch['name']}. Choose the right school, or add that school's folder.")
            return
        if False and self.rules_op:                      # rules belong to FET / aSc now
            rep = self.ops_report()
            if rep is not None:
                msg += ("\n\n✔ Every rule in operation is kept." if not rep["errors"] else
                        f"\n\n⚠ {rep['errors']} rule(s) in operation broken (📋 Rules → Check). Publishing is allowed.")
        try:
            chk = CH.report(d)
        except Exception:
            chk = None
        clash_kinds = ("teacher_clash", "class_clash", "room_clash", "on_break")
        if chk and any(chk["counts"].get(k) for k in clash_kinds):
            if not messagebox.askyesno(
                    "Problems found — publish anyway?",
                    "⚠  The check found problems in this timetable:\n\n" +
                    "\n".join(f"   {chk['counts'][k]}  ×  {lbl}" for k, lbl in CH.KINDS if k in clash_kinds and chk["counts"].get(k)) +
                    "\n\nTeachers will get the timetable WITH these problems.\n\nPublish anyway?",
                    icon="warning", default="no"):
                return
            msg += "\n\n⚠ Publishing with clashes."
        if not messagebox.askyesno("Publish", msg):
            return
        note = self.note_var.get().strip()

        rules_now = [r for r in self.current_rules() if r.get("type") in PHONE_RULES]
        org = self.origin(d)
        notes_now = self.tt_notes()

        def go():
            d["origin"] = org                                # the note on every timetable: FET as imported (A) / checked (B)
            d["notes"] = [{k: v for k, v in n.items() if k != "label"} for n in notes_now]
            d["rules"] = [dict(r) for r in rules_now]       # the phone's "Move / swap this lesson" screen keeps these
            d.pop("_fet_acts", None)
            res = self.pub.publish(sch["code"], tname, d, note, progress=self.run.progress)
            self.run.log(f"✅ DONE — {'replaced' if res['replaced'] else 'added'} “{tname}” for {sch['name']}.  "
                         f"Link: {res['link']}")
            self.run.ui(lambda: (self.school_changed(), messagebox.showinfo(
                "Published", f"“{tname}” is on the website for {sch['name']}.\n\nTeachers see it the next time they "
                             f"open the app.\n\nLink: {res['link']}")))
        self.run.run(go)

    def undo(self):
        sch = self.current_school()
        if not sch:
            return
        old = self.pub.existing_timetable(sch["code"], self.tt_var.get())
        if not old or not self.pub.can_undo(sch["code"], old["id"]):
            messagebox.showinfo("Undo", "There is no earlier version of this timetable yet.")
            return
        if not messagebox.askyesno("Undo last publish", f"Put back the PREVIOUS version of “{old['name']}”?\n\n"
                                                         "(Pressing Undo again switches back to the newer one.)"):
            return

        def go():
            self.pub.undo(sch["code"], old["id"], progress=self.run.progress)
            self.run.log(f"✅ Previous version of “{old['name']}” restored.")
            self.run.ui(self.school_changed)
        self.run.run(go)

    def sheet_restore(self):
        """Every published version (the newest 25 of each timetable) is kept in the Google Sheet: pick one to put back."""
        sch = self.current_school()
        if not sch:
            messagebox.showinfo("Restore", "Choose the school first.")
            return
        box = []

        def fetch():
            box.extend(self.pub.sheet_versions(sch["code"]))
            self.run.ui(show)

        def show():
            if not box:
                messagebox.showinfo("Restore", f"No versions of {sch['name']} are in the Google Sheet yet.\n\n"
                                    "Each publish from now on is kept there.")
                return
            win = tk.Toplevel(self.root)
            win.title(core.public_text(f"Versions kept in the Google Sheet – {sch['name']}") if self.pub.is_school else f"Versions kept in the Google Sheet – {sch['name']}")
            win.geometry("760x460")
            win.configure(bg=U.CREAM)
            win.transient(self.root)
            tk.Label(win, text="Newest first. Choose a version and press Put it back: it goes on the website and "
                               "teachers' phones again (the one there now is kept too).", bg=U.CREAM, fg=U.NAVY,
                     wraplength=720, justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=(12, 6))
            lb = tk.Listbox(win, font=("Consolas", 10), activestyle="dotbox")
            lb.pack(fill="both", expand=True, padx=14)
            for v in box:
                when = str(v.get("at", ""))[:16].replace("T", " ")
                lb.insert("end", f"{when}   {v.get('name', '')[:28]:<28}  {v.get('what', '')[:22]:<22} {v.get('by', '')[:22]}")
            bar = tk.Frame(win, bg=U.CREAM)
            bar.pack(fill="x", padx=14, pady=10)

            def go_back():
                sel = lb.curselection()
                if not sel:
                    return
                v = box[sel[0]]
                if not messagebox.askyesno("Put it back", f"Put back “{v.get('name')}” saved on "
                                           f"{str(v.get('at', ''))[:16].replace('T', ' ')}?\n\nIt replaces the one teachers "
                                           "see now (that one stays in the sheet too).", parent=win):
                    return
                win.destroy()

                def go():
                    res = self.pub.restore_from_sheet(sch["code"], v["tid"], v["version"], progress=self.run.progress)
                    self.run.log(f"✅ “{res['timetable']}” put back from the Google Sheet for {sch['name']}.")
                    self.run.ui(self.school_changed)
                self.run.run(go)
            ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
            ttk.Button(bar, text="↶  Put it back", style="Accent.TButton", command=go_back).pack(side="right", padx=8)
        self.run.run(fetch)

    def export_site(self):
        d = filedialog.askdirectory(title="Choose where to save the site folder (back-up)")
        if not d:
            return
        dest = Path(d) / f"timetable-site {datetime.now().strftime('%Y-%m-%d %H%M')}"

        def go():
            n = self.pub.export_site(dest)
            self.run.log(f"✔ Saved {n} school(s) with all their timetables to {dest}")
        self.run.run(go)


def tidy_folder() -> bool:
    """Cyrus's own PREPFIX folder: only "Start PREPFIX" (+ its icon) on top, everything else inside "program".
    Done once; then PREPFIX starts again from "program". Returns True when it restarted."""
    import shutil
    import subprocess
    import sys
    here = core.APP_DIR
    if here.name.lower() == "program" or not (here / "prepfix_core.py").is_file() or \
            (here / core.LICENCE_FILE).is_file() or (here / core.OLD_LICENCE_FILE).is_file():
        return False                                  # already tidy, or a school copy (tidied by Cyrus's PREPFIX)
    prog = here / "program"
    prog.mkdir(exist_ok=True)
    keep = {"program", "Start PREPFIX.bat", "PREPFIX Timetable Toolkit.lnk"}
    for item in list(here.iterdir()):
        if item.name in keep:
            continue
        try:
            shutil.move(str(item), str(prog / item.name))
        except OSError:
            pass
    try:
        if (here / "Start PREPFIX.bat").is_file():
            shutil.copyfile(here / "Start PREPFIX.bat", prog / "Start PREPFIX.bat")
        (here / "Start PREPFIX.bat").write_bytes(
            b'@echo off\r\nrem PREPFIX Timetable Toolkit - double-click this file (or the PREPFIX icon on the desktop).\r\n'
            b'rem The program itself is in the "program" folder.\r\n'
            b'call "%~dp0program\\Start PREPFIX.bat"\r\n')
    except OSError:
        pass
    subprocess.Popen([sys.executable, str(prog / "prepfix_timetable.py")], cwd=str(prog), close_fds=True)
    return True


def main():
    try:
        if tidy_folder():
            return
    except Exception:
        pass
    U.dpi_aware()
    root = tk.Tk()
    sp = U.Splash(root)                     # full-screen opening: logo, TIMETABLE TOOLKIT, slogan - in motion
    root._splash = sp                       # (steps aside while the password is asked)
    App(root)
    try:
        if not root.winfo_exists():
            return
        sp.keep_alive()
        sp.close(300)
        root.mainloop()
    except tk.TclError:                     # closed before it opened (wrong password, cancelled)
        pass


if __name__ == "__main__":
    main()
