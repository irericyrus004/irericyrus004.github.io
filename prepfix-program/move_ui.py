"""
The "Move lessons" tab and its FULL-SCREEN working place.

  * Run (Publish tab) opens this screen in PREVIEW mode: the whole timetable, read-only, with the rules result.
    "Move lessons" switches to MOVE mode; Finish comes back to the preview; "Go to Publish" leaves.
  * The tab itself is a small launcher: open a ready timetable (FET folder / aSc file) and press the big button.
  * Moving happens on a full screen, in the TEACHERS' timetables. Classes, Master and Labs & Fields are there to look at.
  * Click a lesson -> every box shows green (free), blue (swap) or red (not allowed, point at it to read why), and
    the places it can go are listed on the right, best first.
  * Click a green / blue box (or a place in the list) -> the lesson moves at once. No preview, no questions. Undo is on top.
  * Press "Finish": it says how many TEACHERS and CLASSES were affected, then sends the changes to the Publish tab.
"""
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import constraints as K
import move_logic as M
import prepfix_ui as U

OKC, SWAPC, NOC, SELC, CHG = "#BFE8CF", "#BBD5F5", "#F3C4C0", "#F2D37A", "#FFE08A"
SIBC = "#7B2FBE"                                             # outline: the other lessons of the same subject & class
EMPTY, HEADC, BRKC, XC = "#FFFFFF", "#12284C", "#E7E2D3", "#D9D4C2"
PALETTE = ["#FDE2E4", "#E2ECE9", "#DFE7FD", "#FFF1C1", "#F0EFEB", "#D8E2DC", "#EAD7F7", "#FCD5CE", "#CDEAC0",
           "#C9E4F5", "#FBE7C6", "#E4D4F4"]
KINDS = (("t", "Teachers"), ("c", "Classes"), ("m", "Master"), ("r", "Labs & Fields"))
MOVE_VIEWS = ("t", "c", "r")                                 # timetables where a lesson can be clicked and moved
KEY = {"t": "teachers", "c": "classes", "m": "master", "r": "rooms"}


def _u(s):
    return " ".join(str(s or "").split()).upper()


def _text_on(hexcol: str) -> str:
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#1B2333" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#FFFFFF"


def _n(n, word, plural=None):
    return f"{n} {word if n == 1 else (plural or word + 's')}"


_NAMED = {"white": "#ffffff", "black": "#000000", "red": "#ff0000", "green": "#008000", "blue": "#0000ff",
          "yellow": "#ffff00", "orange": "#ffa500", "pink": "#ffc0cb", "purple": "#800080", "gray": "#808080",
          "grey": "#808080", "cyan": "#00ffff", "magenta": "#ff00ff", "lime": "#00ff00", "silver": "#c0c0c0",
          "brown": "#a52a2a", "gold": "#ffd700", "beige": "#f5f5dc", "khaki": "#f0e68c", "lightblue": "#add8e6",
          "lightgreen": "#90ee90", "lightyellow": "#ffffe0", "lightpink": "#ffb6c1", "lightgrey": "#d3d3d3",
          "lightgray": "#d3d3d3", "aqua": "#00ffff", "teal": "#008080", "navy": "#000080", "maroon": "#800000"}


def _to_hex(col):
    """FET colour as it was stored -> '#rrggbb', or None. Accepts [r, g, b], ['#abc', 'black'], 'rgb(1,2,3)', names."""
    try:
        if isinstance(col, (list, tuple)):
            if len(col) >= 3 and all(isinstance(x, (int, float)) or str(x).strip().isdigit() for x in col[:3]):
                r, g, b = (max(0, min(255, int(float(x)))) for x in col[:3])
                return f"#{r:02x}{g:02x}{b:02x}"
            col = col[0] if col else ""
        c = str(col or "").strip().lower()
        if c.startswith("#"):
            h = c[1:]
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            if len(h) >= 6 and re.fullmatch(r"[0-9a-f]{6}([0-9a-f]{2})?", h):
                return "#" + h[:6]
            return None
        m = re.match(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)", c)
        if m:
            r, g, b = (max(0, min(255, int(x))) for x in m.groups())
            return f"#{r:02x}{g:02x}{b:02x}"
        return _NAMED.get(c)
    except Exception:
        return None


# ======================================================================================================== drawing
class Look:
    """How a timetable dict is drawn as a table."""

    def __init__(self, data):
        self.data = data
        self.days = [d["label"].title() for d in data["days"]]
        self.periods = data["periods"]
        self.colours = data.get("colours") or {}

    def colour(self, subj):
        s = (subj or "").upper()
        for k in (s, s.split("/")[0].strip(), s.split(",")[0].strip()):
            if k in self.colours:
                hx = _to_hex(self.colours[k])
                if hx:
                    return hx
        return PALETTE[sum(ord(ch) for ch in s) % len(PALETTE)]

    def grid(self, kind, ident):
        field = "code" if kind == "t" else "name"
        for g in self.data.get(KEY[kind], []):
            if _u(g.get(field)) == _u(ident):
                return g["grid"]
        return None

    def box(self, val, kind, row, p, hl=False):
        """One box -> dict(fill, top, sub)."""
        pr = self.periods[p]
        if pr.get("brk"):
            return {"fill": BRKC, "top": "", "sub": "", "dim": True}
        if val == "X":
            return {"fill": XC, "top": "—", "sub": "", "dim": True}
        if val == "":
            return {"fill": CHG if hl else EMPTY, "top": "", "sub": ""}
        k = p
        while k > 0 and row[k] == "^":
            k -= 1
        base = row[k] if isinstance(row[k], dict) else {}
        fill = CHG if hl else self.colour(base.get("s", ""))
        if val == "^":
            return {"fill": fill, "top": "", "sub": "(double lesson)", "small": True}
        if kind == "t":
            sub = base.get("c", "")
        elif kind == "c":
            sub = base.get("t", "") + ("  ·  " + base["r"] if base.get("r") else "")
        elif kind == "m":
            sub = base.get("t", "")
        else:
            sub = ", ".join(x for x in (base.get("c", ""), base.get("t", "")) if x)
        return {"fill": fill, "top": base.get("s", "") or "—", "sub": sub}

    def table(self, kind, ident, flip=False, hl=frozenset(), overlay=None):
        """-> (col heads, row heads, cell(r, c) -> box dict, map(r, c) -> (d, p) or (class row, p))"""
        if kind == "m":                                      # one day, every class
            day = int(ident)
            mast = self.data.get("master", [])
            cols = [(pr["label"] + (f"\n{pr['time']}" if pr.get("time") else "")) for pr in self.periods]
            rows = [m["name"] for m in mast]

            def cell(r, c):
                b = self.box(mast[r]["grid"][day][c], "m", mast[r]["grid"][day], c, hl=(r, c) in hl)
                if overlay:
                    b = overlay(day, c, b, mast[r]["name"]) or b
                return b
            return cols, rows, cell, (lambda r, c: (r, c))
        g = self.grid(kind, ident)
        ph = [(pr["label"] + (f"\n{pr['time']}" if pr.get("time") else "")) for pr in self.periods]
        m = (lambda r, c: (c, r)) if not flip else (lambda r, c: (r, c))
        cols, rows = (self.days, ph) if not flip else (ph, self.days)

        def cell(r, c):
            d, p = m(r, c)
            if g is None:
                return {"fill": EMPTY, "top": "", "sub": ""}
            b = self.box(g[d][p], kind, g[d], p, hl=(d, p) in hl)
            if overlay:
                b = overlay(d, p, b, ident) or b
            return b
        return cols, rows, cell, m


BORDER = "#5F6B7F"                                           # lines between the boxes
FRAME = "#1B2333"                                            # the line round the whole timetable


def _put_text(cv, x, y, w, h, parts):
    """Write one or more wrapped, centred lines of text inside the box (x, y, w, h). The writing wraps to the box width
    and, if it would still be too tall, gets a little smaller until it fits. parts = [(text, family, size, colour)]."""
    parts = [pt for pt in parts if pt[0]]
    if not parts:
        return
    ids, hs = [], []
    for dec in range(0, 7):
        ids = [cv.create_text(x + w / 2, y, text=t, fill=col, font=(fam, max(6, sz - dec)), width=max(w - 8, 20),
                              justify="center", anchor="n") for t, fam, sz, col in parts]
        hs = []
        for i in ids:
            bb = cv.bbox(i)
            hs.append((bb[3] - bb[1]) if bb else 0)
        if sum(hs) + 2 * (len(ids) - 1) <= h - 4 or dec == 6:
            break
        cv.delete(*ids)
    top = y + max(2, (h - (sum(hs) + 2 * (len(ids) - 1))) / 2)
    for i, hh in zip(ids, hs):
        cv.coords(i, x + w / 2, top)
        top += hh + 2


def draw_table(cv, cols, rows, cell, head_w=92, head_h=40, rh=52, min_cw=86, fonts=(9, 10, 9)):
    """Paint a table on a canvas, with clear borders and wrapped writing. Returns {canvas item: (row, col)}."""
    cv.delete("all")
    W = max(cv.winfo_width(), 320)
    cw = max(min_cw, (W - head_w - 6) // max(len(cols), 1))
    items, hot = {}, []
    fh, ft, fs = fonts
    for ci, h in enumerate(cols):
        x = head_w + ci * cw
        cv.create_rectangle(x, 0, x + cw, head_h, fill=HEADC, outline="#FFFFFF")
        _put_text(cv, x, 0, cw, head_h, [(h, "Segoe UI Semibold", fh, "white")])
    for ri, h in enumerate(rows):
        y = head_h + ri * rh
        cv.create_rectangle(0, y, head_w, y + rh, fill=HEADC, outline="#FFFFFF")
        _put_text(cv, 0, y, head_w, rh, [(h, "Segoe UI Semibold", fh, "white")])
    for ri in range(len(rows)):
        for ci in range(len(cols)):
            try:
                b = cell(ri, ci)
            except Exception:                                 # one odd box must never blank the whole timetable
                b = {"fill": "#FFFFFF", "top": "", "sub": ""}
            x, y = head_w + ci * cw, head_h + ri * rh
            it = cv.create_rectangle(x, y, x + cw, y + rh, fill=b["fill"], outline=BORDER, width=1)
            items[it] = (ri, ci)
            if b.get("width", 1) > 1:                         # gold / purple / starred boxes: a frame on top of the
                hot.append(cv.create_rectangle(x + 1, y + 1, x + cw - 1, y + rh - 1, fill="",   # neighbours, never
                                               outline=b.get("outline", BORDER), width=b["width"]))  # over the writing
            fg = U.MUTED if b.get("dim") else (U.INK if b.get("dark") else _text_on(b["fill"]))
            _put_text(cv, x, y, cw, rh, [(b.get("top", ""), "Segoe UI Semibold", ft, fg),
                                         (b.get("sub", ""), "Segoe UI", fs - 1 if b.get("small") else fs, fg)])
            if b.get("mark"):
                cv.create_text(x + cw - 12, y + 12, text=b["mark"], fill=b.get("mark_col", U.INK),
                               font=("Segoe UI Semibold", 12))
    for it in hot:
        cv.tag_raise(it)
    if rows and cols:                                         # a firm line round the whole timetable
        cv.create_rectangle(head_w, head_h, head_w + len(cols) * cw, head_h + len(rows) * rh, outline=FRAME, width=2)
    cv.configure(scrollregion=(0, 0, head_w + len(cols) * cw + 4, head_h + len(rows) * rh + 4))
    return items


# ======================================================================================================== the full-screen place
class MoveScreen:
    """The full-screen working place. It works on tab.board (a copy of the timetable) until you press Finish."""

    def __init__(self, tab, mode="move"):
        self.tab, self.app = tab, tab.app
        self.mode_name = mode                                # "preview" (look only) or "move"
        self.alive = True
        self.full = False
        self.sel = None
        self.best = None                                     # the best place for the picked lesson (shown with a star)
        self.status = {}
        self.items = {}
        self.map = None
        self.drag_from = None
        self.place_items = []
        self._ids = []
        self.view = tk.StringVar(value="t")
        self.who = tk.StringVar()
        self.flip = tk.BooleanVar(value=True)            # lessons 1..last across, days down: the whole day is seen at once

        ttk.Style(self.app.root).configure("Card.TRadiobutton", background="white")
        win = self.win = tk.Toplevel(self.app.root)
        win.title("PREPFIX — Move lessons")
        win.configure(bg=U.CREAM)
        win.geometry("1280x800+0+0")
        win.minsize(900, 600)
        win.protocol("WM_DELETE_WINDOW", self._close)
        win.bind("<F11>", self._toggle_full)
        win.bind("<Escape>", lambda e: self._select(None))
        self._build()
        self._fill_names(keep=False)
        self._set_mode(mode)
        self._set_full(True)
        win.lift()
        win.focus_force()
        self._sync()
        win.after(250, self._grab)
        win.after(160, self.draw)

    @property
    def board(self):
        return self.tab.board

    # ------------------------------------------------------------------ window
    def _grab(self, tries=0):
        if not self.alive:
            return
        try:
            self.win.grab_set()                              # the screen is modal: nothing behind it can change the timetable
        except tk.TclError:
            if tries < 8:
                self.win.after(200, lambda: self._grab(tries + 1))

    def _set_full(self, on):
        self.full = on
        try:
            self.win.attributes("-fullscreen", on)
        except tk.TclError:
            pass
        if not on:
            try:
                self.win.state("zoomed")
            except tk.TclError:
                try:
                    self.win.attributes("-zoomed", True)
                except tk.TclError:
                    pass
        self.b_full.configure(text="▭  Exit full screen" if on else "⛶  Full screen")
        self.win.after(150, self.draw)

    def _toggle_full(self, e=None):
        self._set_full(not self.full)

    # ------------------------------------------------------------------ layout
    def _build(self):
        w = self.win
        top = ttk.Frame(w, style="Card.TFrame", padding=(14, 8))
        top.pack(fill="x")
        ttk.Label(top, text="Preview", style="Big.TLabel").pack(side="left")
        self.info = ttk.Label(top, text="", style="CardMuted.TLabel")
        self.info.pack(side="left", padx=14)
        ttk.Button(top, text="✖  Close", command=self._close).pack(side="right")
        self.b_full = ttk.Button(top, text="", command=self._toggle_full)
        self.b_full.pack(side="right", padx=6)
        self.swap = ttk.Frame(top, style="Card.TFrame")      # the buttons that change with the mode
        self.swap.pack(side="right")
        self.g_move = ttk.Frame(self.swap, style="Card.TFrame")
        self.b_finish = ttk.Button(self.g_move, text="✔  Finish", style="Accent.TButton", command=self._finish)
        self.b_finish.pack(side="right", padx=6)
        self.count = tk.Label(self.g_move, text="", bg=U.NAVY, fg="white", font=("Segoe UI Semibold", 11), padx=14,
                              pady=7)
        self.count.pack(side="right", padx=10)
        self.g_prev = ttk.Frame(self.swap, style="Card.TFrame")
        ttk.Button(self.g_prev, text="🚀  Go to Publish", style="Accent.TButton", command=self._go_publish).pack(
            side="right", padx=6)
        # V1: PREPFIX never changes a timetable - no "Move lessons" here (FET or aSc make every change)

        bar = ttk.Frame(w, style="Card.TFrame", padding=(14, 0, 14, 8))
        bar.pack(fill="x")
        for k, t in KINDS:
            ttk.Radiobutton(bar, text=t, value=k, variable=self.view, style="Card.TRadiobutton",
                            command=self._view_changed).pack(side="left", padx=4)
        self.box = ttk.Combobox(bar, textvariable=self.who, state="readonly", width=34, font=("Segoe UI", 11))
        self.box.pack(side="left", padx=8)
        self.box.bind("<<ComboboxSelected>>", lambda e: self._who_changed())
        ttk.Button(bar, text="◀", width=3, command=lambda: self._step(-1)).pack(side="left")
        ttk.Button(bar, text="▶", width=3, command=lambda: self._step(1)).pack(side="left", padx=(2, 10))
        self.flip_cb = ttk.Checkbutton(bar, text="Days down the side", variable=self.flip, command=self.draw)
        self.flip_cb.pack(side="left")
        self.edit_bar = ttk.Frame(bar, style="Card.TFrame")
        self.edit_bar.pack(side="right")
        self.b_redo = ttk.Button(self.edit_bar, text="↷ Redo", width=8, command=self._redo)
        self.b_redo.pack(side="right")
        self.b_undo = ttk.Button(self.edit_bar, text="↶ Undo", width=8, command=self._undo)
        self.b_undo.pack(side="right", padx=4)
        ttk.Button(self.edit_bar, text="Reset all", command=self._reset).pack(side="right", padx=(0, 10))

        self.flow = tk.Label(w, text="", bg=U.CREAM, fg="#5A6577", font=("Segoe UI", 10), anchor="w")
        self.flow.pack(fill="x", padx=16, pady=(6, 0))
        self.mode = tk.Label(w, text="", bg=U.CREAM, fg=U.NAVY, font=("Segoe UI Semibold", 11), anchor="w")
        self.mode.pack(fill="x", padx=16, pady=(2, 0))
        self.rules_lbl = tk.Label(w, text="", bg=U.CREAM, fg=U.GREEN, font=("Segoe UI", 10), anchor="w")
        self.rules_lbl.pack(fill="x", padx=16, pady=(0, 2))
        self.legend = tk.Frame(w, bg=U.CREAM)                # colour key, shown while moving
        for col, txt in ((SELC, "gold = the lesson you picked"), (OKC, "✔ green = free, it moves there"),
                         (SWAPC, "⇄ blue = swap with the lesson there"), (NOC, "✖ red = not allowed"),
                         ("#FFFFFF", "★ = best (keeps the plan)"), (SIBC, "◆ = its other lessons")):
            tk.Label(self.legend, text="   ", bg=col, relief="solid", bd=1).pack(side="left", padx=(0, 4))
            tk.Label(self.legend, text=txt, bg=U.CREAM, fg=U.INK, font=("Segoe UI", 9)).pack(side="left", padx=(0, 14))

        body = ttk.Frame(w)
        body.pack(fill="both", expand=True, pady=(2, 8), padx=8)
        side = self.side = ttk.Frame(body, style="Card.TFrame", padding=8, width=300)
        side.pack(side="right", fill="y", padx=(8, 0))
        side.pack_propagate(False)
        main = self.main = ttk.Frame(body, style="Card.TFrame", padding=8)
        main.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(main, bg="white", highlightthickness=0)
        hs = ttk.Scrollbar(main, orient="horizontal", command=self.canvas.xview)
        vs = ttk.Scrollbar(main, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Button-3>", lambda e: self._select(None))
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(-1 if e.delta > 0 else 1, "units"))

        # ---- side panel
        self.msg = tk.Label(side, text="", bg="white", fg=U.INK, wraplength=276, justify="left", anchor="nw",
                            font=("Segoe UI", 10), height=11)
        self.msg.pack(fill="x")
        ttk.Label(side, text="Where it can go — click one", style="H.TLabel").pack(anchor="w", pady=(4, 0))
        pl = ttk.Frame(side, style="Card.TFrame")
        pl.pack(fill="both", expand=True, pady=2)
        sb = ttk.Scrollbar(pl)
        sb.pack(side="right", fill="y")
        self.places = tk.Listbox(pl, font=("Segoe UI", 10), activestyle="none", yscrollcommand=sb.set, relief="flat",
                                 bg="#FBF8EF", exportselection=False)
        self.places.pack(fill="both", expand=True)
        sb.config(command=self.places.yview)
        self.places.bind("<ButtonRelease-1>", self._places_click)
        self.places.bind("<Return>", lambda e: self._pick_index(self.places.curselection()[0]
                                                                if self.places.curselection() else -1))
        self.b_best = ttk.Button(side, text="★  Move it to the best place", command=self._best, state="disabled")
        self.b_best.pack(fill="x", pady=(2, 2))
        self.b_deep = ttk.Button(side, text="🔎  Nothing fits? Look deeper (2-step moves)", command=self._deeper)
        self.b_deep.pack(fill="x", pady=(2, 6))
        ttk.Label(side, text="Changes made", style="H.TLabel").pack(anchor="w")
        lf = ttk.Frame(side, style="Card.TFrame")
        lf.pack(fill="x", pady=2)
        lsb = ttk.Scrollbar(lf)
        lsb.pack(side="right", fill="y")
        self.log = tk.Listbox(lf, font=("Segoe UI", 9), activestyle="none", relief="flat", height=7, bg="#FBF8EF",
                              selectbackground="#FBF8EF", selectforeground=U.INK, yscrollcommand=lsb.set)
        self.log.pack(fill="x")
        lsb.config(command=self.log.yview)
        r2 = ttk.Frame(side, style="Card.TFrame")
        r2.pack(fill="x", pady=(4, 0))
        ttk.Button(r2, text="Check for clashes", command=self._report).pack(side="left", fill="x", expand=True)

    def _set_mode(self, mode):
        self.mode_name = mode
        self.sel, self.status, self.drag_from, self.best = None, {}, None, None
        self.b_best.configure(state="disabled")
        self.places.delete(0, "end")
        self.place_items = []
        for g in (self.g_move, self.g_prev):
            g.pack_forget()
        if mode == "move":
            self.tab.untouched = False
            self.g_move.pack(side="right")
            self.legend.pack(fill="x", padx=16, pady=(0, 2), after=self.rules_lbl)
            self.edit_bar.pack(side="right")
            self.side.pack(side="right", fill="y", padx=(8, 0), before=self.main)
            self.rules_lbl.configure(text="")
            self.msg.configure(text="Click a lesson in a teacher's timetable.", fg=U.INK)
            self._sync()
        else:
            self.g_prev.pack(side="right")
            self.legend.pack_forget()
            self.edit_bar.pack_forget()
            self.side.pack_forget()
            self.rules_lbl.configure(text=self.tab.rules_text())
        self.draw()

    def _rules_run(self):
        """Apply my constraints by running again, without leaving the screen (moves made so far are kept)."""
        app, mode = self.app, self.mode_name
        if not app.use_con.get():
            app.use_con.set(True)
        app.con_toggled()
        self._destroy()
        app.root.after(60, lambda: app.run_once(True, mode))

    def _go_publish(self):
        self._destroy()
        self.app.nb.select(self.app.tab_pub)

    # ------------------------------------------------------------------ names
    def _fill_names(self, keep=True):
        b = self.board
        v = self.view.get()
        if v == "t":
            pairs = [(code, f"{nm}  [{code}]" if _u(nm) != _u(code) else code) for code, nm in b.teacher_names()]
        elif v == "c":
            pairs = [(n, n) for n in b.class_names()]
        elif v == "m":
            pairs = [(i, d.title()) for i, d in enumerate(b.days)]
        else:
            pairs = [(g["name"], g["name"]) for g in b.data.get("rooms", [])]
        self._ids = [i for i, _ in pairs]
        labels = [t for _, t in pairs]
        self.box["values"] = labels
        if labels and not (keep and self.who.get() in labels):
            self.who.set(labels[0])
        if not labels:
            self.who.set("")
        self.info.configure(
            text=f"{len(b.lessons)} lessons · {b.D} days · {sum(1 for p in b.periods if not p.get('brk'))} lessons a day")

    def _view_changed(self):
        self.sel, self.status, self.drag_from = None, {}, None
        self.places.delete(0, "end")
        self.place_items = []
        self._fill_names(keep=False)                          # the list of names must match the view BEFORE anything is drawn
        self.msg.configure(text="Click a lesson to move it." if self.view.get() in MOVE_VIEWS
                           else "The Master timetable is for looking. To move a lesson, choose Teachers, Classes or "
                                "Labs & Fields above.", fg=U.INK)
        self.draw()

    def _who_changed(self):
        if self.view.get() in MOVE_VIEWS:
            self._select(None)
        self.draw()

    def _step(self, k):
        vals = list(self.box["values"])
        if not vals:
            return
        i = (vals.index(self.who.get()) + k) % len(vals) if self.who.get() in vals else 0
        self.who.set(vals[i])
        self._who_changed()

    def _owner(self):
        vals = list(self.box["values"])
        if not self.board or self.who.get() not in vals:
            return None
        return self._ids[vals.index(self.who.get())]

    # ------------------------------------------------------------------ drawing
    def _overlay(self):
        b, sel, v = self.board, self.sel, self.view.get()
        if sel is None:
            return None
        slots = set(b.slots(sel))
        status = self.status

        mine_own = {"t": sel["t"], "c": sel["c"], "r": sel["r"]}.get(v, [])
        sib = {}                                             # the same subject's other lessons for this class
        for X in b.same_subject(sel):
            own = {"t": X["t"], "c": X["c"], "r": X["r"], "m": X["c"]}.get(v, [])
            for sl in b.slots(X):
                sib.setdefault(sl, set()).update(_u(o) for o in own)

        def with_sib(d, p, box, ident, out):
            if _u(ident) in sib.get((d, p), ()):
                out = dict(out if out is not None else box, outline=SIBC, width=4, mark="◆", mark_col=SIBC)
                if box.get("top") or box.get("sub") == "(double lesson)":
                    out["fill"] = box["fill"]                     # its own colour, so the subject reads clearly
                    out.pop("dark", None)
            return out

        def over(d, p, box, ident):
            return with_sib(d, p, box, ident, over0(d, p, box, ident))

        def over0(d, p, box, ident):
            if v in MOVE_VIEWS and any(_u(ident) == _u(x) for x in mine_own):
                st = status.get((d, p))
                if (d, p) in slots:
                    return dict(box, fill=SELC, dark=True, outline="#B08A1E", width=2)
                if st and not b.periods[p].get("brk"):
                    s = st["status"]
                    out = dict(box)
                    if s == "ok":
                        out.update(fill=OKC, dark=True, mark="★" if (d, p) == self.best else "✔",
                                   mark_col="#B08A1E" if (d, p) == self.best else "#1E7F5C")
                        if (d, p) == self.best:
                            out.update(outline="#B08A1E", width=3)
                    elif s == "swap":
                        out.update(fill=SWAPC, dark=True, mark="★" if (d, p) == self.best else "⇄",
                                   mark_col="#B08A1E" if (d, p) == self.best else "#1D5FB4")
                        if (d, p) == self.best:
                            out.update(outline="#B08A1E", width=3)
                    elif s == "no":
                        if not box["top"]:
                            out.update(fill=NOC, dark=True)
                        out.update(mark="✖", mark_col="#B42318")
                    return out
            else:                                           # reading views: show where the chosen lesson sits
                mine = {"t": sel["t"], "c": sel["c"], "r": sel["r"], "m": sel["c"]}.get(v, [])
                if (d, p) in slots and any(_u(ident) == _u(x) for x in mine):
                    return dict(box, fill=SELC, dark=True, outline="#B08A1E", width=2)
            return None
        return over

    def draw(self):
        if not self.alive:
            return
        cv = self.canvas
        b, who = self.board, self._owner()
        v = self.view.get()
        self.items, self.map = {}, None
        self.flip_cb.configure(state="disabled" if v == "m" else "normal")
        self.mode.configure(
            text=(("PREVIEW — the timetable exactly as imported. Look through Teachers, Classes, Master and Labs. "
                   "Fine? Press “Go to Publish”."
                   if self.tab.untouched else
                   "PREVIEW — this is the timetable as teachers will get it. Look through Teachers, Classes, Master and Labs. "
                   "Fine? Press “Go to Publish”.  Need a change? Make it in FET or aSc, then import again.")
                  if self.mode_name != "move" else
                  ("STEP 1 of 2 — click the lesson you want to move (Teachers, Classes or Labs & Fields)."
                   if self.sel is None else
                   "STEP 2 of 2 — click a green box (move) or a blue box (swap), or a place in the list. ★ = best. Esc = cancel.")
                  if v in MOVE_VIEWS else
                  "For looking only — to move a lesson, choose Teachers, Classes or Labs & Fields above."
                  + ("  The lesson you picked is outlined in gold." if self.sel else "")))
        if not b or who is None:
            cv.delete("all")
            cv.create_text(20, 20, anchor="nw", fill=U.MUTED, font=("Segoe UI", 12),
                           text="Nothing to show yet." if not b else
                           ("This timetable has no labs or fields." if v == "r" else "Choose one above."))
            return
        look = Look(b.data)
        n_mv = len(b.moves)
        self.flow.configure(text="A move is refused only for a clash (teacher, class or lab in two places) or a break"
                                 + ("  ·  ★ = best place: keeps the plan " + ("FET made" if b.advice else "(no subject twice a day)"))
                                 + "  ·  Moves: " + (f"{n_mv}" if n_mv else "none yet"))
        if v == "m":
            ov = None
            if self.sel is not None:
                slots, classes = set(b.slots(self.sel)), [_u(x) for x in self.sel["c"]]

                sib = {(sl, _u(c)) for X in b.same_subject(self.sel) for sl in b.slots(X) for c in X["c"]}

                def ov(d, p, box, name):
                    if _u(name) in classes and (d, p) in slots and box["top"]:
                        return dict(box, fill=SELC, dark=True, outline="#B08A1E", width=2)
                    if ((d, p), _u(name)) in sib and box["top"]:
                        return dict(box, outline=SIBC, width=3, mark="◆", mark_col=SIBC)
                    return None
            cols, rows, cell, m = look.table("m", who, overlay=ov)
        else:
            cols, rows, cell, m = look.table(v, who, flip=self.flip.get(), overlay=self._overlay())
        self.map = m
        H = max(cv.winfo_height(), 300)                      # everything fits the screen: lesson 1 to the last, no sideways scrolling
        W = max(cv.winfo_width(), 320)
        flipped = (v != "m" and self.flip.get())
        head_w = 64 if flipped else 100
        cw = (W - head_w - 6) / max(len(cols), 1)
        rh = max(30, min(80, (H - 50 - 8) // max(len(rows), 1)))
        fonts = (10, 11, 10) if cw >= 100 else ((9, 10, 9) if cw >= 78 else ((8, 9, 8) if cw >= 62 else (7, 8, 7)))
        self.items = draw_table(cv, cols, rows, cell, head_w=head_w, head_h=50, rh=rh, min_cw=30, fonts=fonts)

    def _cell_at(self, e):
        if self.map is None:
            return None
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        for it in self.canvas.find_overlapping(x, y, x, y):
            if it in self.items:
                r, c = self.items[it]
                return self.map(r, c)
        return None

    # ------------------------------------------------------------------ choosing a lesson
    def _select(self, L):
        if not self.alive:
            return
        self.sel = L
        self.drag_from = None
        self.status = self.board.where_can_it_go(L) if (L and self.board) else {}
        self.places.delete(0, "end")
        self.place_items = []
        if L:
            b = self.board
            self.msg.configure(text=f"{b.label(L)} — {', '.join(b.tdisp(t) for t in L['t']) or 'no teacher'}\n"
                                    f"Now: {b.when(L['d'], L['p'])}\n"
                                    f"◆ {b.subject_week(L)}\n"
                                    "Green = free · Blue = swap · Red = clash (point at it to see why).",
                               fg=U.INK)
            sols = b.solutions(L)
            self.best = (sols[0]["d"], sols[0]["p"]) if sols else None
            nf = sum(1 for s in sols if s["status"] == "ok")
            self.msg.configure(text=self.msg.cget("text").rsplit("\n", 1)[0] +
                               f"\n{nf} free place{'' if nf == 1 else 's'}, {len(sols) - nf} swap{'' if len(sols) - nf == 1 else 's'}"
                               " — ★ is the best. Click a green or blue box, or the list.\n"
                               "✓ plan = keeps the plan it was made with · ⚠ = allowed, but bends it (point at it).",
                               fg=U.INK)
            for i, s in enumerate(sols):
                warn = "  ⚠" if s["warn"] else "  ✓ plan"
                star = "★ " if i == 0 else ""
                if s["status"] == "ok":
                    txt = f"{star}✔  {b.when(s['d'], s['p'])} — free{warn}"
                else:
                    txt = f"{star}⇄  {b.when(s['d'], s['p'])} — swap with {b.label(s['with'])}{warn}"
                self.places.insert("end", txt)
                self.place_items.append({"steps": [(L, s["d"], s["p"])]})
            self.b_best.configure(state="normal" if sols else "disabled")
            if not sols:
                self.places.insert("end", "No free place or swap.")
                self.places.insert("end", "Press “Look deeper” below to try 2-step moves.")
                self.place_items += [None, None]
        else:
            self.best = None
            self.b_best.configure(state="disabled")
            self.msg.configure(text="Click a lesson in a teacher's timetable.", fg=U.INK)
        self.draw()

    def _best(self):
        if self.sel is not None and self.place_items and self.place_items[0]:
            self._apply(self.place_items[0]["steps"])

    def _press(self, e):
        if self.board and self.mode_name != "move":
            self.msg.configure(text="This is a preview. To change a lesson, change it in FET or aSc and import again.", fg="#8A6100")
            return
        if not self.board:
            return
        if self.view.get() not in MOVE_VIEWS:
            self.msg.configure(text="The Master timetable is for looking. To move a lesson, choose Teachers, Classes or "
                                    "Labs & Fields above and click it there.", fg="#8A6100")
            return
        c = self._cell_at(e)
        who = self._owner()
        if c is None or who is None:
            return
        d, p = c
        L = self.board.lesson_at(self.view.get(), who, d, p)
        if self.sel is not None:
            st = self.status.get(c)
            if st and st["status"] in ("ok", "swap"):
                self._apply([(self.sel, d, p)])
                return
            if L is self.sel:
                self._select(None)
                return
        if L is not None and not self.board.periods[p].get("brk"):
            self._select(L)
            self.drag_from = c
        elif self.sel is not None:
            st = self.status.get(c)
            if st:
                self.msg.configure(text=f"{self.board.when(d, p)}\n{st['why']}", fg=U.RED)

    def _release(self, e):
        if self.mode_name != "move" or self.drag_from is None or self.sel is None or self.view.get() not in MOVE_VIEWS:
            return
        c, start = self._cell_at(e), self.drag_from
        self.drag_from = None
        if c is None or c == start:
            return
        st = self.status.get(c)
        if st and st["status"] in ("ok", "swap"):
            self._apply([(self.sel, *c)])
        elif st:
            self.msg.configure(text=f"{self.board.when(*c)}\n{st['why']}", fg=U.RED)

    def _hover(self, e):
        if self.mode_name != "move" or self.sel is None or self.view.get() not in MOVE_VIEWS:
            return
        c = self._cell_at(e)
        st = self.status.get(c) if c else None
        if not st or c in self.board.slots(self.sel):
            return
        b = self.board
        extra = ("\n⚠ " + "\n⚠ ".join(st["warn"][:2])) if st.get("warn") else ""
        self.msg.configure(text=f"{b.when(*c)}\n{st['why']}{extra}", fg=U.RED if st["status"] == "no" else U.INK)

    def _places_click(self, e):
        i = self.places.nearest(e.y)
        bb = self.places.bbox(i)
        if bb is None or not (bb[1] <= e.y <= bb[1] + bb[3]):
            return
        self._pick_index(i)

    def _pick_index(self, i):
        if 0 <= i < len(self.place_items) and self.place_items[i]:
            self._apply(self.place_items[i]["steps"])

    # ------------------------------------------------------------------ deeper (2-step) answers
    def _deeper(self):
        if not self.board or self.sel is None:
            messagebox.showinfo("Look deeper", "First click a lesson in a teacher's timetable.", parent=self.win)
            return
        key = self.board.key(self.sel)
        self.win.config(cursor="watch")
        self.win.update_idletasks()
        try:
            chains = self.board.chains(self.sel)
        finally:
            self.win.config(cursor="")
        self.sel = self.board.find(key)                      # the working copy was rebuilt: pick the lesson up again
        if self.sel is None:
            self._select(None)
            return
        self.status = self.board.where_can_it_go(self.sel)
        self.places.insert("end", "")
        self.places.insert("end", "—— 2-step moves ——" if chains else "—— no 2-step move found either ——")
        self.place_items += [None, None]
        for c in chains:
            warn = "  ⚠" if c["warn"] else ""
            self.places.insert("end", "②  " + c["text"] + warn)
            self.place_items.append({"steps": [c["first"], c["then"]]})
        if not chains:
            self.msg.configure(text="No single move, swap or 2-step move works. The reasons are in the red boxes "
                                    "(point at them). Changing a Constraints rule may open more places.", fg="#8A6100")
        self.places.see("end")
        self.draw()

    # ------------------------------------------------------------------ doing it (at once — no preview)
    def _apply(self, steps):
        b = self.board
        keys = [(b.key(L), d, p) for L, d, p in steps]
        done, warns = [], []
        try:
            for k, d, p in keys:
                L = b.find(k)
                if L is None:
                    raise ValueError("That lesson is no longer where it was.")
                warns += b.check(L, d, p).get("warn", [])
                done.append(b.move(L, d, p))
        except ValueError as ex:
            self.msg.configure(text=str(ex), fg=U.RED)
            return
        self.sel, self.status, self.drag_from = None, {}, None
        self.places.delete(0, "end")
        self.place_items = []
        warn = sorted(set(warns))
        self.msg.configure(text="✔ Done:\n" + "\n".join(done) + "\nClick the next lesson to move."
                                + (("\n⚠ " + "\n⚠ ".join(warn[:2])) if warn else ""),
                           fg=U.GREEN)
        self._sync()
        self.draw()

    def _sync(self):
        if not self.alive or self.mode_name != "move":
            return
        b = self.board
        self.b_undo.configure(state="normal" if b and b.undo_stack else "disabled")
        self.b_redo.configure(state="normal" if b and b.redo_stack else "disabled")
        self.b_finish.configure(state="normal" if b and b.changed else "disabled")
        a = b.affected() if b else {"teachers": [], "classes": []}
        n = len(b.moves) if b else 0
        self.count.configure(text=f"{_n(n, 'change')}   ·   {_n(len(a['teachers']), 'teacher')}   ·   "
                                  f"{_n(len(a['classes']), 'class', 'classes')} affected")
        self.log.delete(0, "end")
        for i, m in enumerate(b.moves if b else [], 1):
            self.log.insert("end", f"{i}. {m}")
        self.log.see("end")

    def _undo(self):
        if self.board and self.board.undo() is not None:
            self._select(None)
            self._sync()

    def _redo(self):
        if self.board and self.board.redo() is not None:
            self._select(None)
            self._sync()

    def _reset(self):
        if self.board and self.board.changed and messagebox.askyesno(
                "Reset", "Put every lesson back where it was when you loaded the timetable?", parent=self.win):
            self.board.reset()
            self._select(None)
            self._sync()

    def _report(self):
        if not self.board:
            return
        import constraints_ui as CU
        CU.show_report(self.win, self.board.problems(), title="Clash check — with your moves", info=True)
        self.win.after(100, self._grab)                      # the report took the grab; take it back

    def _export(self):
        if not self.board:
            return
        f = filedialog.asksaveasfilename(parent=self.win, title="Save the timetable (with your moves) as an Excel list",
                                         defaultextension=".xlsx", initialfile="timetable-moved.xlsx",
                                         filetypes=[("Excel", "*.xlsx")])
        if f:
            try:
                self.board.export_list(f)
            except Exception as e:
                messagebox.showerror("Could not save", str(e), parent=self.win)
                return
            messagebox.showinfo("Saved", "Saved. You can load it again later with “Import Excel / PDF” (it is in the "
                                         "easy list layout), so your moves are not lost.", parent=self.win)

    # ------------------------------------------------------------------ finishing
    def _finish(self):
        b = self.board
        if not b or not b.changed:
            self._set_mode("preview")
            return
        a = b.affected()
        if not messagebox.askyesno(
                "All changes done",
                f"Teachers affected:  {len(a['teachers'])}\n"
                f"Classes affected:  {len(a['classes'])}\n\n"
                "Use these changes and look at the preview?\n(No = keep working here.)", parent=self.win):
            return
        try:                                                 # only stop if the moves made things WORSE than the file already was
            worse = b.problems()["errors"] > K.run(b.base, b.rules)["errors"]
        except Exception:
            worse = False
        if worse and not messagebox.askyesno(
                "Rules", "After your moves there are more must-fix rule problems than before.\n\n"
                         "Use the changes anyway?", parent=self.win):
            return
        self.tab.use_changes(stay=True)                      # the changed timetable now goes to Publish...
        self._fill_names(keep=True)
        self._set_mode("preview")                            # ...and you look at the result before publishing

    def _close(self):
        b = self.board
        if b and b.changed:
            ans = messagebox.askyesnocancel(
                "Close", f"You have {_n(len(b.moves), 'change')} that {'has' if len(b.moves) == 1 else 'have'} not gone to "
                         "Publish yet.\n\nYes = Finish now (see how many teachers and classes are affected)\n"
                         "No = close this screen; the changes stay here until you load another timetable\n"
                         "Cancel = keep working", parent=self.win)
            if ans is None:
                return
            if ans:
                self._finish()
                return
        self._destroy()

    def _destroy(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.win.grab_release()
        except tk.TclError:
            pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        self.tab.screen = None
        self.tab.refresh(auto=False)


# ======================================================================================================== the tab (launcher)
class MoveTab:
    def __init__(self, app, frame):
        self.app, self.f = app, frame
        self.board = None
        self.src = None
        self.screen = None
        self.want_open = False
        self._pending = False
        self.untouched = False                               # the preview of the first Run: exactly as imported
        self._build()

    def _build(self):
        card = ttk.Frame(self.f, style="Card.TFrame", padding=(26, 20))
        card.pack(fill="x", padx=2)
        ttk.Label(card, text="Move lessons", style="Big.TLabel").pack(anchor="w")
        ttk.Label(card, style="Card.TLabel", wraplength=900, justify="left", text=(
            "Take a ready timetable (for example the folder FET made, with its HTML files), move lessons on a full screen, "
            "then publish it.\n\n"
            "1.  Open the timetable below.\n"
            "2.  Click a lesson, then click one of the places shown. It moves at once.\n"
            "3.  Press Finish. You are told how many teachers and classes were affected, and the changed timetable goes "
            "to the Publish tab.")).pack(anchor="w", pady=(6, 12))
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(anchor="w")
        ttk.Button(row, text="📂  Open FET folder…", command=self._load_folder).pack(side="left")
        ttk.Button(row, text="📄  Import aSc file (.roz or PDF)…", command=self._load_sheet).pack(side="left", padx=8)
        self.status = ttk.Label(card, text="", style="Card.TLabel", wraplength=900, justify="left")
        self.status.pack(anchor="w", pady=(14, 8))
        self.btn_open = ttk.Button(card, text="⛶   Open full screen — move lessons", style="Accent.TButton",
                                   command=self.open_screen)
        self.btn_open.pack(anchor="w")

    # ------------------------------------------------------------------ loading a timetable from here
    def _load_folder(self):
        self.want_open = True
        self.app.add_folder()

    def _load_sheet(self):
        if not self.app.current_school():
            messagebox.showinfo("Choose the school", "An aSc file does not say which school it is for.\n\n"
                                                     "Choose the school at the top of “Import & Run” first, then come back "
                                                     "here and press this button again.", parent=self.app.root)
            self.app.nb.select(self.app.tab_imp)
            return
        self.want_open = True
        self.app.import_sheet()

    def after_load(self):
        """The publisher calls this when a timetable has just been loaded."""
        if self.want_open:
            self.want_open = False
            self.refresh(auto=True)
            return True
        return False

    # ------------------------------------------------------------------ state
    def refresh(self, auto=True):
        data = self.app.data
        if data is None:
            self.board, self.src = None, None
            self.status.configure(text="Nothing loaded yet. Open a FET folder or an aSc timetable above "
                                       "(or load one on “Import & Run”).", style="Card.TLabel")
            self.btn_open.configure(state="disabled")
            return
        if data is not self.src:
            rules = self.app.current_rules()
            try:
                self.board = M.Board(data, rules, advice=self.app.advice_rules())
            except Exception as e:
                self.board = None
                self.status.configure(text=f"This timetable cannot be opened here: {e}", style="Bad.TLabel")
                self.btn_open.configure(state="disabled")
                return
            self.src = data
        b = self.board
        n = len(b.moves)
        self.status.configure(
            text=f"Loaded: {len(b.lessons)} lessons · {len(b.data.get('teachers', []))} teachers · "
                 f"{len(b.data.get('classes', []))} classes."
                 + (f"   {_n(n, 'change')} waiting — open the screen and press Finish to send {'it' if n == 1 else 'them'} "
                    "to Publish." if n else ""), style="Ok.TLabel")
        self.btn_open.configure(state="normal")
        if auto and not self.screen_open() and not self._pending:
            self._pending = True
            self.f.after(200, self._auto_open)

    def _auto_open(self):
        self._pending = False
        if self.app.nb.select() == str(self.app.tab_move):
            self.open_screen()

    def screen_open(self):
        return bool(self.screen and self.screen.alive)

    def rules_text(self):
        b = self.board
        if self.untouched:
            return "UNTOUCHED — exactly as imported."
        if not b:
            return ""
        try:
            return "Clash check: " + K.summary_line(b.problems()).replace("  Click “View constraint report”.", "")
        except Exception as e:
            return f"Constraints could not be checked: {e}"

    def open_preview(self, first=False, mode="preview"):
        """Run was pressed: show the loaded timetable full screen. first=True: untouched, no rules.
        mode="move" brings you back to moving (used when Run again was pressed from the moving screen)."""
        self.untouched = bool(first) and mode != "move"
        self.open_screen(mode)

    def open_screen(self, mode="move"):
        if self.screen_open():
            self.screen.win.lift()
            return
        self.refresh(auto=False)
        if not self.board:
            messagebox.showinfo("Move lessons", "Load a timetable first: press “Open FET folder…” or "
                                                "“aSc PDF”.", parent=self.app.root)
            return
        self.screen = MoveScreen(self, mode)

    def use_changes(self, stay=False):
        """Finish was pressed: hand the changed timetable to Publish."""
        b = self.board
        if not b or not b.changed:
            return
        rules, n, a = b.rules, len(b.moves), b.affected()
        self.app.apply_moves(b.result(), n, f"{_n(len(a['teachers']), 'teacher')} and "
                                            f"{_n(len(a['classes']), 'class', 'classes')} affected",
                              stay=stay)
        self.src = self.app.data
        self.board = M.Board(self.app.data, rules, advice=b.advice)
        self.refresh(auto=False)


# ======================================================================================================== final review
def affected_teachers(orig, new):
    """Teachers whose timetable in `new` differs from `orig` -> [(code, name, {(d, p), ...})]. Nobody else is listed."""
    if not orig or not new:
        return []
    before = {_u(g.get("code")): g for g in orig.get("teachers", [])}
    out = []
    for g in new.get("teachers", []):
        a = before.get(_u(g.get("code")))
        if a is None or a["grid"] == g["grid"]:
            continue
        cells = {(d, p) for d in range(len(g["grid"])) for p in range(len(g["grid"][d]))
                 if d < len(a["grid"]) and p < len(a["grid"][d]) and a["grid"][d][p] != g["grid"][d][p]}
        if cells:
            out.append((g["code"], g.get("name") or g["code"], cells))
    return out


def _desc(v):
    if isinstance(v, dict):
        return " ".join(x for x in (v.get("s", ""), v.get("c", "")) if x) or "lesson"
    return "(double lesson)" if v == "^" else ("free" if v in ("", None) else "—")


class ReviewWindow:
    """The last look before publishing: BEFORE and AFTER side by side, only for the teachers whose timetable changed."""

    def __init__(self, app, orig, new, ask=False):
        self.app, self.orig, self.new, self.ask = app, orig, new, ask
        self.result = False
        self.rows = affected_teachers(orig, new)
        self.look_a, self.look_b = Look(orig), Look(new)
        win = self.win = tk.Toplevel(app.root)
        win.title("PREPFIX — Final preview: before and after")
        win.configure(bg=U.CREAM)
        win.geometry("1280x800+0+0")
        win.minsize(900, 600)
        try:
            win.state("zoomed")
        except tk.TclError:
            pass
        win.protocol("WM_DELETE_WINDOW", self._back)
        top = ttk.Frame(win, style="Card.TFrame", padding=(14, 8))
        top.pack(fill="x")
        ttk.Label(top, text="Final preview — before and after", style="Big.TLabel").pack(side="left")
        n = len(self.rows)
        self.count = tk.Label(top, text=f"{n} teacher{'' if n == 1 else 's'} affected — only they are shown",
                              bg=U.NAVY, fg="white", font=("Segoe UI Semibold", 11), padx=14, pady=6)
        self.count.pack(side="left", padx=14)
        if ask:
            ttk.Button(top, text="🚀  Publish now", style="Accent.TButton", command=self._go).pack(side="right")
            ttk.Button(top, text="✖  Back", command=self._back).pack(side="right", padx=8)
        else:
            ttk.Button(top, text="✖  Close", command=self._back).pack(side="right")
        body = ttk.Frame(win)
        body.pack(fill="both", expand=True, padx=8, pady=(6, 8))
        left = ttk.Frame(body, style="Card.TFrame", padding=8, width=250)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        ttk.Label(left, text="Affected teachers", style="H.TLabel").pack(anchor="w")
        lf = ttk.Frame(left, style="Card.TFrame")
        lf.pack(fill="both", expand=True, pady=4)
        sb = ttk.Scrollbar(lf)
        sb.pack(side="right", fill="y")
        self.lst = tk.Listbox(lf, font=("Segoe UI", 10), activestyle="none", exportselection=False, relief="flat",
                              bg="#FBF8EF", yscrollcommand=sb.set)
        self.lst.pack(fill="both", expand=True)
        sb.config(command=self.lst.yview)
        for code, name, cells in self.rows:
            self.lst.insert("end", f"{name}   ({len(cells)} box{'' if len(cells) == 1 else 'es'})")
        self.lst.bind("<<ListboxSelect>>", lambda e: self.draw())
        nav = ttk.Frame(left, style="Card.TFrame")
        nav.pack(fill="x")
        ttk.Button(nav, text="◀  Previous", command=lambda: self._step(-1)).pack(side="left")
        ttk.Button(nav, text="Next  ▶", command=lambda: self._step(1)).pack(side="right")
        right = ttk.Frame(body, style="Card.TFrame", padding=8)
        right.pack(side="left", fill="both", expand=True)
        self.title = ttk.Label(right, text="", style="H.TLabel")
        self.title.pack(anchor="w")
        self.cvs = []
        for txt in ("BEFORE (as imported)", "AFTER (what teachers will get)"):
            tk.Label(right, text=txt, bg="white", fg=U.NAVY, font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x")
            cv = tk.Canvas(right, bg="white", highlightthickness=0, height=200)
            cv.pack(fill="both", expand=True, pady=(0, 6))
            cv.bind("<Configure>", lambda e: self.win.after_idle(self.draw))
            self.cvs.append(cv)
        self.txt = tk.Text(right, height=6, relief="flat", bg="#FBF8EF", font=("Segoe UI", 10), wrap="word", padx=8, pady=6)
        self.txt.pack(fill="x")
        if self.rows:
            self.lst.selection_set(0)
        win.lift()
        win.focus_force()
        win.after(200, self._grab)
        win.after(160, self.draw)

    def _grab(self):
        try:
            self.win.grab_set()
        except tk.TclError:
            pass

    def _step(self, k):
        if not self.rows:
            return
        cur = self.lst.curselection()
        i = (cur[0] if cur else 0) + k
        i = max(0, min(len(self.rows) - 1, i))
        self.lst.selection_clear(0, "end")
        self.lst.selection_set(i)
        self.lst.see(i)
        self.draw()

    def draw(self):
        if not self.win.winfo_exists():
            return
        sel = self.lst.curselection()
        if not self.rows or not sel:
            for cv in self.cvs:
                cv.delete("all")
                cv.create_text(20, 20, anchor="nw", fill=U.MUTED, font=("Segoe UI", 12), text="No teacher was affected.")
            return
        code, name, cells = self.rows[sel[0]]
        self.title.configure(text=f"{name}   —   the gold boxes are what changed")
        for cv, look in zip(self.cvs, (self.look_a, self.look_b)):
            cols, rows, cell, m = look.table("t", code, flip=True, hl=frozenset(cells))
            W, H = max(cv.winfo_width(), 320), max(cv.winfo_height(), 120)
            cw = (W - 64 - 6) / max(len(cols), 1)
            rh = max(26, min(70, (H - 46 - 6) // max(len(rows), 1)))
            fonts = (10, 11, 10) if cw >= 100 else ((9, 10, 9) if cw >= 78 else ((8, 9, 8) if cw >= 62 else (7, 8, 7)))
            draw_table(cv, cols, rows, cell, head_w=64, head_h=46, rh=rh, min_cw=30, fonts=fonts)
        ga = {_u(g.get("code")): g for g in self.orig.get("teachers", [])}[_u(code)]["grid"]
        gb = {_u(g.get("code")): g for g in self.new.get("teachers", [])}[_u(code)]["grid"]
        lines = []
        for d, p in sorted(cells):
            pr = self.new["periods"][p]
            lines.append(f"{self.look_b.days[d]} {pr['label']}"
                         + (f" ({pr['time']})" if pr.get("time") else "")
                         + f":   {_desc(ga[d][p])}   →   {_desc(gb[d][p])}")
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(lines))
        self.txt.configure(state="disabled")

    def _go(self):
        self.result = True
        self._close()

    def _back(self):
        self.result = False
        self._close()

    def _close(self):
        try:
            self.win.grab_release()
        except tk.TclError:
            pass
        self.win.destroy()
