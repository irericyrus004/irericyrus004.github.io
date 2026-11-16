"""Shared look and background-task plumbing for the Ireri window."""
import queue
import threading
import traceback
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import prepfix_core as core

NAVY, NAVY2, GREEN, GOLD, CREAM, INK, MUTED, RED = ("#12284C", "#0B1B36", "#1E7F5C", "#C9A227", "#FBF6EA",
                                                    "#1B2333", "#667085", "#B42318")


def style(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", font=("Segoe UI", 10), background=CREAM, foreground=INK)
    st.configure("TFrame", background=CREAM)
    st.configure("Card.TFrame", background="white")
    st.configure("TLabel", background=CREAM)
    st.configure("Card.TLabel", background="white")
    st.configure("CardMuted.TLabel", background="white", foreground=MUTED)
    st.configure("H.TLabel", background="white", foreground=NAVY, font=("Segoe UI Semibold", 12))
    st.configure("Big.TLabel", background="white", foreground=NAVY, font=("Segoe UI Semibold", 16))
    st.configure("Ok.TLabel", background="white", foreground=GREEN, font=("Segoe UI Semibold", 10))
    st.configure("Bad.TLabel", background="white", foreground=RED, font=("Segoe UI Semibold", 10))
    st.configure("TNotebook", background=CREAM, borderwidth=0)
    st.configure("TNotebook.Tab", padding=(18, 8), font=("Segoe UI Semibold", 10))
    st.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", NAVY)])
    st.configure("TButton", padding=(12, 6))
    st.configure("Accent.TButton", background=GREEN, foreground="white", font=("Segoe UI Semibold", 11),
                 padding=(18, 9), borderwidth=0)
    st.map("Accent.TButton", background=[("active", "#176548"), ("disabled", "#9BB8AC")])
    st.configure("Gold.TButton", background=GOLD, foreground=NAVY2, font=("Segoe UI Semibold", 10),
                 padding=(14, 7), borderwidth=0)
    st.map("Gold.TButton", background=[("active", "#B08A1E")])
    st.configure("Treeview", rowheight=26)
    st.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
    st.configure("Horizontal.TProgressbar", troughcolor="#EDE6D3", background=GREEN)
    st.configure("TCheckbutton", background="white")


BRAND_DIR = core.APP_DIR / "teacher_app" / "brand"


def _logo(file, factor):
    try:
        return tk.PhotoImage(file=str(BRAND_DIR / file)).subsample(factor)
    except Exception:
        return None


def header(root, title):
    head = tk.Frame(root, bg="white")
    head.pack(fill="x")
    small = root.winfo_screenheight() < 900                      # laptops (e.g. 1366 x 768): a smaller header
    # the PREPFIX Timetable Toolkit badge, then its name and slogan
    img = _logo("prepfix-badge-64.png" if small else "prepfix-badge-84.png", 1) or \
        (_logo("prepfix-logo-230.png", 1) if small else None) or _logo("prepfix-logo-320.png", 1)
    if img:
        lbl = tk.Label(head, image=img, bg="white")
        lbl.image = img
        lbl.pack(side="left", padx=(12, 8), pady=3 if small else 6)
    name = tk.Frame(head, bg="white")
    name.pack(side="left")
    tk.Label(name, text="PREPFIX Timetable Toolkit", bg="white", fg=NAVY,
             font=("Segoe UI Black", 17 if small else 20)).pack(anchor="w")
    sl = tk.Frame(name, bg="white")
    sl.pack(anchor="w")
    for word, col in (("Prepare.", NAVY), ("Perfect.", GREEN), ("Present.", NAVY)):
        tk.Label(sl, text=word, bg="white", fg=col, font=("Segoe UI Semibold", 10 if small else 11)).pack(side="left", padx=(0, 4))
    if title:
        tk.Label(head, text=title, bg="white", fg=NAVY, font=("Segoe UI Semibold", 15)).pack(side="left", padx=10, pady=12)
    right = tk.Label(head, text="", bg=NAVY, fg="#C9D3E6", font=("Segoe UI Semibold", 10), padx=12, pady=6)
    right.pack(side="right", padx=16)
    tk.Frame(root, bg=GOLD, height=3).pack(fill="x")
    return right


class Runner:
    """Runs slow work in a thread and keeps the window responsive."""

    def __init__(self, root, logbox: tk.Text, prog: ttk.Progressbar, after_done=None):
        self.root, self.logbox, self.prog = root, logbox, prog
        self.q = queue.Queue()
        self.busy = False
        self.after_done = after_done
        root.after(100, self._pump)

    def log(self, msg):
        self.q.put(("log", str(msg)))

    def progress(self, p):
        self.q.put(("prog", p))

    def ui(self, fn):
        self.q.put(("call", fn))

    def _pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.logbox.configure(state="normal")
                    self.logbox.insert("end", val + "\n")
                    self.logbox.see("end")
                    self.logbox.configure(state="disabled")
                elif kind == "prog":
                    self.prog.stop()
                    self.prog.configure(mode="determinate")
                    self.prog["value"] = val
                elif kind == "call":
                    val()
        except queue.Empty:
            pass
        self.root.after(100, self._pump)

    def run(self, fn, quiet=False, after=None):
        """after: called on the window when fn finished without a problem."""
        if self.busy:
            if not quiet:
                messagebox.showinfo("Please wait", "Still working on the previous task…")
            return
        self.busy = True
        self.root.config(cursor="watch")
        self.prog.configure(mode="indeterminate")
        self.prog.start(12)

        ok = []

        def work():
            try:
                fn()
                ok.append(1)
            except (core.PublishError, ValueError, OSError) as e:
                if not quiet:
                    self.log("✖ " + str(e))
                    msg = str(e)
                    self.ui(lambda: messagebox.showerror("Problem", msg))
            except Exception as e:
                self.log("✖ Unexpected error: " + repr(e))
                self.log(traceback.format_exc())
                if not quiet:
                    msg = repr(e)
                    self.ui(lambda: messagebox.showerror("Unexpected error", msg))
            finally:
                def done():
                    self.busy = False
                    self.root.config(cursor="")
                    self.prog.stop()
                    self.prog.configure(mode="determinate")
                    if self.after_done:
                        self.after_done()
                    if after and ok:
                        after()
                self.ui(done)

        threading.Thread(target=work, daemon=True).start()


def bottom_log(root):
    bottom = ttk.Frame(root, padding=(12, 8, 12, 10))
    bottom.pack(fill="x", side="bottom")
    prog = ttk.Progressbar(bottom, mode="determinate", maximum=100)
    prog.pack(fill="x")
    logbox = tk.Text(bottom, height=3 if root.winfo_screenheight() < 900 else 6, bg=NAVY2, fg="#E6ECF5", insertbackground="white", font=("Consolas", 9),
                     relief="flat", wrap="word", padx=8, pady=6)
    logbox.pack(fill="x", pady=(6, 0))
    logbox.configure(state="disabled")
    return logbox, prog


def set_icon(root):
    try:                                            # Windows: the PREPFIX icon in the title bar and the taskbar
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PREPFIX.TimetableToolkit")
            except Exception:
                pass
            ico = BRAND_DIR / "prepfix-toolkit.ico"
            root.iconbitmap(default=str(ico if ico.exists() else BRAND_DIR / "prepfix.ico"))
    except Exception:
        pass
    try:
        png = BRAND_DIR / "prepfix-toolkit-icon-256.png"
        root.iconphoto(True, tk.PhotoImage(file=str(png if png.exists() else BRAND_DIR / "prepfix-mark.png")))
    except Exception:
        try:
            root.iconphoto(True, tk.PhotoImage(file=str(core.APP_DIR / "teacher_app" / "icons" / "icon-192.png")))
        except Exception:
            pass


class Splash:
    """The opening screen: full screen, the PREPFIX logo with TIMETABLE TOOLKIT and the slogan, big. The logo rises
    in, a timetable fills itself in cell by cell, a gold bar runs while PREPFIX loads, then it fades into the app."""
    CELLS = ["#2F6FE4", "#F28C28", "#1E7F5C", "#C9A227", "#7B4BD8", "#E04F7A", "#1AA6B7", "#12284C"]

    def __init__(self, root):
        import time
        self.root, self.t0, self.time = root, time.time(), time
        self.ok = False
        try:
            root.withdraw()
            w = self.w = tk.Toplevel(root)
            w.overrideredirect(True)
            W, H = w.winfo_screenwidth(), w.winfo_screenheight()
            self.W, self.H = W, H
            w.geometry(f"{W}x{H}+0+0")
            w.configure(bg="white")
            try:
                w.attributes("-topmost", True)
                w.attributes("-alpha", 0.0)
            except tk.TclError:
                pass
            img = None
            # the PREPFIX Timetable Toolkit badge, as big as the screen allows
            for name in ("prepfix-badge-700.png", "prepfix-badge-520.png", "prepfix-badge-380.png",
                         "prepfix-logo-760.png", "prepfix-logo.png"):
                try:
                    cand = tk.PhotoImage(file=str(BRAND_DIR / name))
                except Exception:
                    continue
                img = cand
                if cand.height() <= H * 0.52:
                    break
            self.img = img
            c = self.c = tk.Canvas(w, width=W, height=H, bg="white", highlightthickness=0)
            c.pack(fill="both", expand=True)
            c.create_rectangle(0, 0, W, 8, fill=GOLD, outline="")                    # brand edges
            c.create_rectangle(0, H - 46, W, H, fill=NAVY, outline="")
            c.create_text(W // 2, H - 23, text=f"{core.LOCKED_BRAND} {core.LOCKED_CONTACT}", fill="white",
                          font=("Segoe UI Semibold", 12))
            self.cy = int(H * 0.33)
            self.logo = c.create_image(W // 2, self.cy + 70, image=img) if img else \
                c.create_text(W // 2, self.cy, text="PREPFIX", fill=NAVY, font=("Segoe UI Black", 72))
            lh = img.height() if img else 120
            # a little timetable that fills itself in, under the logo
            self.gy = self.cy + lh // 2 + 26
            cw, ch, gap, cols, rows = 40, 18, 5, 8, 3
            gx = W // 2 - (cols * cw + (cols - 1) * gap) // 2
            self.cells = []
            for r in range(rows):
                for k in range(cols):
                    x, y = gx + k * (cw + gap), self.gy + r * (ch + gap)
                    self.cells.append(c.create_rectangle(x, y, x + cw, y + ch, fill="#F1EEE6", outline=""))
            self.order = [(k * 5 + 3) % len(self.cells) for k in range(len(self.cells))]
            by = self.gy + rows * (ch + gap) + 22
            bw = min(520, int(W * 0.4))
            self.bar = (W // 2 - bw // 2, by, W // 2 + bw // 2, by + 6)
            c.create_rectangle(*self.bar, fill="#E9E4D6", outline="")
            self.run = c.create_rectangle(self.bar[0], by, self.bar[0], by + 6, fill=GOLD, outline="")
            self.msg = c.create_text(W // 2, by + 24, text="", fill=MUTED, font=("Segoe UI", 12))
            self.ok = True
            self.animate(2.2)
        except Exception:
            self.close()

    def frame(self, t):
        """Draw the opening at time t (seconds)."""
        c, W = self.c, self.W
        ease = lambda x: 1 - (1 - max(0.0, min(1.0, x))) ** 3
        try:
            self.w.attributes("-alpha", min(1.0, t / 0.45))
        except tk.TclError:
            pass
        rise = ease(t / 0.9)
        c.coords(self.logo, W // 2, self.cy + 70 * (1 - rise))
        n = int(len(self.cells) * ease((t - 0.5) / 1.3))
        for i, idx in enumerate(self.order):
            c.itemconfigure(self.cells[idx], fill=self.CELLS[idx % len(self.CELLS)] if i < n else "#F1EEE6")
        x0, y0, x1, y1 = self.bar
        seg = (x1 - x0) * 0.28
        pos = ((t * 0.9) % 1.0) * (x1 - x0 + seg) - seg
        c.coords(self.run, x0 + max(0, pos), y0, x0 + min(x1 - x0, pos + seg), y1)
        words = ["Preparing your timetables", "Loading the rules", "Getting everything ready"]
        c.itemconfigure(self.msg, text=words[min(2, int(t / 0.8))] + "." * (1 + int(t * 3) % 3))

    def animate(self, seconds):
        end = self.time.time() + seconds
        while self.ok and self.time.time() < end:
            self.frame(self.time.time() - self.t0)
            self.w.update()
            self.time.sleep(1 / 60)

    def keep_alive(self):
        """While the main window is being built: keep the bar moving."""
        if self.ok:
            try:
                self.frame(self.time.time() - self.t0)
                self.w.update()
            except tk.TclError:
                self.ok = False

    def close(self, after_ms=0):
        def go():
            if getattr(self, "w", None) is not None:
                if self.ok:
                    try:                                       # fade out
                        for k in range(10, -1, -1):
                            self.w.attributes("-alpha", k / 10)
                            self.w.update()
                            self.time.sleep(0.02)
                    except tk.TclError:
                        pass
                try:
                    self.w.destroy()
                except tk.TclError:
                    pass
            self.ok = False
            try:
                self.root.deiconify()
                try:
                    self.root.state("zoomed")
                except tk.TclError:
                    self.root.attributes("-zoomed", True)
                self.root.lift()
                self.root.focus_force()
            except tk.TclError:
                pass
        if after_ms:
            self.root.after(after_ms, go)
        else:
            go()


def splash(root, ms=0):
    """Kept for older callers."""
    s = Splash(root)
    s.close(ms)
    return s


def dpi_aware():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
