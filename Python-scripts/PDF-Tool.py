# --------------------------------------------------------------------------------
# Application Specification: FETL PDF Stamp & Watermark Tool
# --------------------------------------------------------------------------------
# Program Name: pdfstamp.py
# Version:      3.31 (Added Config Variables: TITLEBAR, APPNAME)
# Author:       Senior Developer (Gemini)
# Created:      2025-12-18
# Environment:  Windows 10/11 (Python 3.10+)
#
# 1. OVERVIEW
#    A professional-grade GUI application designed to apply digital stamps and 
#    watermarks to PDF documents. It supports multi-layer stamping, dynamic 
#    page reordering, output compression, and granular security controls.
#
# 2. KEY FEATURES
#    A. Multi-Layer Stamping:
#       - 3 Independent Stamp Layers (Sets 1, 2, 3).
#       - Content: Text (3 lines) or Image (PNG).
#       - Styling: Default Font "Tahoma", Colors, Opacity, Borders.
#       - Positioning: 5x3 Grid + Rotation.
#
#    B. Page Management:
#       - "Manage Pages": Reorder/Delete pages visually.
#       - Preview updates immediately.
#
#    C. Security & Encryption:
#       - **Input Support**: Detects encrypted input files and prompts for password.
#       - **Output Security**:
#         * Owner Password: Automatically randomized to enforce restrictions.
#         * User Password: Manual or Random (saves .pass file).
#         * Permissions: Toggle Allow Printing / Allow Copying.
#
#    D. Output Generation:
#       - **Rotation Normalization**: Automatically rotates source content to 0°
#         before stamping to ensure watermarks are always upright.
#       - **Tiled Watermark**: Spaced 200x100 diagonal text (Size 14, Tahoma).
#       - **Compression**: Optional 'Deflate' (Skipped if Encryption is on).
#       - **Auto-Open**: Checkbox to open file after saving.
#
#    E. System Integration:
#       - **Auto-Install**: Missing libraries (pymupdf, pypdf, reportlab, Pillow).
#       - **Proxy Support**: --proxy arg or system env.
#       - **Settings**: Auto-save/load 'settings.json'.
#
# 3. BUILD INSTRUCTIONS
#    Run: python pdfstamp.py --build
# --------------------------------------------------------------------------------

import sys
import subprocess
import os
import importlib
import io
import json
import shutil
import time
import secrets
import string
import math

# --- CONFIGURATION ---
TITLEBAR = "PDF Tools"
APPNAME  = "PDF_Tools" 
# ---------------------

# --- 0. Parse Proxy ---
PROXY_URL = None
if "--proxy" in sys.argv:
    try:
        p_idx = sys.argv.index("--proxy")
        if p_idx + 1 < len(sys.argv): PROXY_URL = sys.argv[p_idx + 1]
    except: pass

# --- 1. Auto-Installation Logic ---
def install_and_import(package_name, import_name=None, proxy=None):
    if import_name is None: import_name = package_name
    try:
        importlib.import_module(import_name)
    except ImportError:
        print(f"[INFO] Module '{import_name}' not found. Installing '{package_name}'...")
        cmd = [sys.executable, "-m", "pip", "install", package_name]
        if not proxy:
            proxy = os.environ.get('http_proxy') or os.environ.get('https_proxy')
        if proxy: 
            cmd.extend(["--proxy", proxy])
            print(f"       Using proxy: {proxy}")
        try:
            subprocess.check_call(cmd)
            print(f"[SUCCESS] Installed {package_name}")
        except subprocess.CalledProcessError: 
            print(f"[ERROR] Failed to install {package_name}. Check connection.")
            sys.exit(1)

# --- 2. Install Dependencies ---
install_and_import("pymupdf", "fitz", PROXY_URL)
install_and_import("pypdf", proxy=PROXY_URL)
install_and_import("reportlab", proxy=PROXY_URL)
install_and_import("Pillow", "PIL", PROXY_URL)

# --- 3. Imports ---
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from PIL import Image, ImageTk
import fitz
from pypdf import PdfReader, PdfWriter, PageObject
from pypdf.constants import UserAccessPermissions
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# --- 4. Font Registration (Tahoma Default) ---
REGISTERED_FONTS = []
def register_fonts():
    dirs = [r"C:\Windows\Fonts", r"C:\WINNT\Fonts", "/usr/share/fonts", "/Library/Fonts"]
    cands = [
        ("Tahoma",["tahoma.ttf"]), 
        ("Thai-Angsana",["angsa.ttc","angsana.ttc"]), 
        ("JP-MSGothic",["msgothic.ttc"]), 
        ("CN-SimHei",["simhei.ttf"]), 
        ("Arial-Unicode",["arialuni.ttf"])
    ]
    for name, fnames in cands:
        for d in dirs:
            for fn in fnames:
                fp = os.path.join(d, fn)
                if os.path.exists(fp):
                    try: 
                        pdfmetrics.registerFont(TTFont(name, fp))
                        REGISTERED_FONTS.append(name)
                        break
                    except: pass
            if name in REGISTERED_FONTS: break
register_fonts()

# --- 5. Build Automation ---
def build_executable():
    install_and_import("pyinstaller", "PyInstaller", PROXY_URL)
    script_name = os.path.basename(__file__)
    # Use APPNAME variable
    exe_name = APPNAME
    
    cmd = [
        sys.executable, "-m", "PyInstaller", 
        "--noconfirm", "--onedir", "--windowed", 
        "--name", exe_name, 
        "--hidden-import", "pypdf", 
        "--hidden-import", "reportlab", 
        "--hidden-import", "fitz", 
        "--hidden-import", "PIL", 
        "--hidden-import", "tkinter", 
        "--clean", script_name
    ]
    print(f"[INFO] Building {exe_name}...")
    try: subprocess.check_call(cmd); print(f"[SUCCESS] Build complete. Check 'dist/{exe_name}' folder.")
    except: print("[ERROR] Build failed.")

# --- 6. Dialog: Page Manager ---
class PageManagerDialog(tk.Toplevel):
    def __init__(self, parent, page_count, current_mapping, callback):
        super().__init__(parent)
        self.title("Page Manager")
        self.geometry("400x500")
        self.transient(parent)
        self.grab_set()
        
        self.page_count = page_count
        self.mapping = list(current_mapping)
        self.callback = callback
        
        ttk.Label(self, text="Select pages to move or delete:", font=("", 10, "bold")).pack(pady=10)
        frame = ttk.Frame(self); frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE, font=("Courier", 10))
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.refresh_list()
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Move Up", command=self.move_up).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Move Down", command=self.move_down).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete", command=self.delete_page).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Apply", command=self.apply).pack(side=tk.RIGHT, padx=5)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for i, original_idx in enumerate(self.mapping):
            self.listbox.insert(tk.END, f"New Page {i+1}  (Original Page {original_idx+1})")

    def move_up(self):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        if idx > 0:
            self.mapping[idx], self.mapping[idx-1] = self.mapping[idx-1], self.mapping[idx]
            self.refresh_list(); self.listbox.selection_set(idx-1)

    def move_down(self):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        if idx < len(self.mapping) - 1:
            self.mapping[idx], self.mapping[idx+1] = self.mapping[idx+1], self.mapping[idx]
            self.refresh_list(); self.listbox.selection_set(idx+1)

    def delete_page(self):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        del self.mapping[idx]
        self.refresh_list()
        if self.mapping: self.listbox.selection_set(min(idx, len(self.mapping)-1))

    def apply(self):
        if not self.mapping: messagebox.showwarning("Warning", "Cannot have empty document."); return
        self.callback(self.mapping); self.destroy()

# --- 7. Dialog: Security & Save Options ---
class SecurityDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Save & Security Options")
        self.geometry("550x650")
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        
        # Variables
        self.enable_enc = tk.BooleanVar(value=False)
        self.pass_mode = tk.StringVar(value="Manual")
        self.manual_pass = tk.StringVar(value="")
        self.manual_owner = tk.StringVar(value="")
        
        self.allow_print = tk.BooleanVar(value=False)
        self.allow_copy = tk.BooleanVar(value=False)
        
        self.watermark_text = tk.StringVar(value="")

        self._init_ui()

    def _init_ui(self):
        main_p = ttk.Frame(self, padding=15)
        main_p.pack(fill=tk.BOTH, expand=True)

        # 1. Encryption Toggle
        f_enc = ttk.LabelFrame(main_p, text="1. Encryption Settings", padding=10)
        f_enc.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(f_enc, text="Enable Password Protection", variable=self.enable_enc, command=self.toggle_state).pack(anchor="w", pady=(0,5))
        
        # Password Mode
        self.f_mode = ttk.Frame(f_enc)
        self.f_mode.pack(fill=tk.X, padx=10)
        
        # A. Manual
        ttk.Radiobutton(self.f_mode, text="Manual Configuration", variable=self.pass_mode, value="Manual", command=self.toggle_state).pack(anchor="w")
        
        self.f_man = ttk.Frame(self.f_mode, padding=(20, 5))
        self.f_man.pack(fill=tk.X)
        
        ttk.Label(self.f_man, text="User Password (Required):", font=("", 9, "bold")).pack(anchor="w")
        ttk.Label(self.f_man, text="• Recipients use this to OPEN the file.\n• Permissions (No Print/Copy) apply to them.", foreground="#555", font=("", 8)).pack(anchor="w")
        self.ent_user = ttk.Entry(self.f_man, textvariable=self.manual_pass, show="*", width=30)
        self.ent_user.pack(anchor="w", pady=(2, 10))
        
        ttk.Label(self.f_man, text="Owner Password (Optional):", font=("", 9, "bold")).pack(anchor="w")
        ttk.Label(self.f_man, text="• Grants FULL ACCESS (Bypasses all restrictions).\n• If blank, a random secure password is generated.", foreground="#555", font=("", 8)).pack(anchor="w")
        self.ent_owner = ttk.Entry(self.f_man, textvariable=self.manual_owner, show="*", width=30)
        self.ent_owner.pack(anchor="w", pady=2)

        ttk.Separator(self.f_mode, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # B. Random
        ttk.Radiobutton(self.f_mode, text="Full Auto (Random Passwords)", variable=self.pass_mode, value="Random", command=self.toggle_state).pack(anchor="w")
        ttk.Label(self.f_mode, text="   Generates secure User & Owner passwords.\n   Saved to [filename].pass", foreground="gray", font=("", 8)).pack(anchor="w")

        # 2. Permissions
        self.f_perm = ttk.LabelFrame(main_p, text="2. User Permissions", padding=10)
        self.f_perm.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(self.f_perm, text="Allow Printing", variable=self.allow_print).pack(anchor="w")
        ttk.Checkbutton(self.f_perm, text="Allow Copying Content (Text/Images)", variable=self.allow_copy).pack(anchor="w")
        ttk.Label(self.f_perm, text="* Uncheck 'Copying' to make file Read-Only.", foreground="gray", font=("", 8)).pack(anchor="w", padx=20)

        # 3. Tiled Watermark
        f_water = ttk.LabelFrame(main_p, text="3. Additional Tiled Watermark", padding=10)
        f_water.pack(fill=tk.X, pady=5)
        ttk.Label(f_water, text="Select text (Repeats diagonally across page):").pack(anchor="w")
        
        options = ["", "Confidential", "Draft", "Copy", "Internal used Only"]
        self.cb = ttk.Combobox(f_water, textvariable=self.watermark_text, values=options)
        self.cb.pack(fill=tk.X, pady=5)
        ttk.Label(f_water, text="Leave blank for none.", foreground="gray", font=("", 8)).pack(anchor="w")

        # Buttons
        btn_f = ttk.Frame(main_p, padding=(0, 15, 0, 0))
        btn_f.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(btn_f, text="Save PDF", command=self.on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_f, text="Cancel", command=self.on_cancel).pack(side=tk.RIGHT)
        
        self.toggle_state()

    def toggle_state(self):
        state = 'normal' if self.enable_enc.get() else 'disabled'
        
        for child in self.f_perm.winfo_children():
            try: child.configure(state=state)
            except: pass
            
        for child in self.f_mode.winfo_children():
            if isinstance(child, ttk.Radiobutton):
                child.configure(state=state)

        is_manual = (self.pass_mode.get() == "Manual" and self.enable_enc.get())
        state_man = 'normal' if is_manual else 'disabled'
        self.ent_user.configure(state=state_man)
        self.ent_owner.configure(state=state_man)

    def on_save(self):
        if self.enable_enc.get() and self.pass_mode.get() == "Manual":
            if len(self.manual_pass.get()) < 6:
                messagebox.showerror("Error", "User Password must be at least 6 characters.")
                return

        self.result = {
            "encrypt": self.enable_enc.get(),
            "pass_mode": self.pass_mode.get(),
            "manual_user": self.manual_pass.get(),
            "manual_owner": self.manual_owner.get(),
            "allow_print": self.allow_print.get(),
            "allow_copy": self.allow_copy.get(),
            "tiled_text": self.watermark_text.get()
        }
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

# --- 8. Component: Stamp Tab ---
class StampTab(ttk.Frame):
    def __init__(self, parent, update_callback, text_l1="FETL", text_l2="Confidential", default_enabled=False):
        super().__init__(parent)
        self.update_callback = update_callback
        self.enabled = tk.BooleanVar(value=default_enabled)
        self.image_path = tk.StringVar(value="")
        
        self.txt_1 = tk.StringVar(value=text_l1); self.sz_1 = tk.IntVar(value=20)
        self.txt_2 = tk.StringVar(value=text_l2); self.sz_2 = tk.IntVar(value=40)
        self.txt_3 = tk.StringVar(value="");      self.sz_3 = tk.IntVar(value=20)
        
        self.align_1 = tk.StringVar(value="Left"); self.align_2 = tk.StringVar(value="Center"); self.align_3 = tk.StringVar(value="Center")
        self.fam = tk.StringVar(value="Tahoma"); self.sty = tk.StringVar(value="Regular")
        self.opac = tk.IntVar(value=50); self.border = tk.BooleanVar(value=True); self.border_style = tk.StringVar(value="Solid") 
        self.col_r = tk.IntVar(value=255); self.col_g = tk.IntVar(value=0); self.col_b = tk.IntVar(value=0); self.col_hex = "#FF0000"

        self.pos_vars = {}; self.rot_vars = {}
        self.pos_map = {
            "TL": ("TL", "0", 0, 0), "TC": ("TC", "0", 0, 1), "TR": ("TR", "0", 0, 2),
            "LT": ("LT", "90", 1, 0),                         "RT": ("RT", "270", 1, 2),
            "LC": ("LC", "90", 2, 0), "C":  ("C", "45", 2, 1),"RC": ("RC", "270", 2, 2),
            "LB": ("LB", "90", 3, 0),                         "RB": ("RB", "270", 3, 2),
            "BL": ("BL", "0", 4, 0), "BC": ("BC", "0", 4, 1), "BR": ("BR", "0", 4, 2),
        }
        for pid, (lbl, rot, r, c) in self.pos_map.items():
            self.pos_vars[pid] = tk.BooleanVar(value=(pid=="C"))
            self.rot_vars[pid] = tk.StringVar(value=rot)
        self._build_ui()

    def _build_ui(self):
        top_f = ttk.Frame(self, padding=2); top_f.pack(fill=tk.X)
        ttk.Checkbutton(top_f, text="Enable this Stamp Set", variable=self.enabled, command=self.update_callback).pack(anchor="w")
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=1)

        img_grp = ttk.LabelFrame(self, text="Image / Logo", padding=2); img_grp.pack(fill=tk.X, padx=2, pady=1)
        img_row = ttk.Frame(img_grp); img_row.pack(fill=tk.X)
        ttk.Button(img_row, text="Select PNG", command=self.select_image).pack(side=tk.LEFT)
        ttk.Button(img_row, text="Clear", command=self.clear_image).pack(side=tk.LEFT, padx=5)
        self.lbl_img_path = ttk.Label(img_row, text="No image", foreground="gray"); self.lbl_img_path.pack(side=tk.LEFT, padx=5)

        t_grp = ttk.LabelFrame(self, text="Text", padding=2); t_grp.pack(fill=tk.X, padx=2, pady=1)
        tg = ttk.Frame(t_grp); tg.pack(fill=tk.X)
        ttk.Label(tg, text="Content").grid(row=0,column=0); ttk.Label(tg, text="Size").grid(row=0,column=1); ttk.Label(tg, text="Align").grid(row=0,column=2)
        for i, (tv, sv, av) in enumerate([(self.txt_1, self.sz_1, self.align_1), (self.txt_2, self.sz_2, self.align_2), (self.txt_3, self.sz_3, self.align_3)]):
            ttk.Entry(tg, textvariable=tv).grid(row=i+1, column=0, sticky="ew")
            ttk.Spinbox(tg, from_=1, to=200, textvariable=sv, width=4, command=self.update_callback).grid(row=i+1, column=1)
            cb = ttk.Combobox(tg, textvariable=av, values=("Left", "Center", "Right"), width=7, state="readonly"); cb.grid(row=i+1, column=2)
            cb.bind("<<ComboboxSelected>>", lambda e: self.update_callback())
        tg.columnconfigure(0, weight=1)

        fs = ttk.Frame(t_grp); fs.pack(fill=tk.X, pady=2)
        cb_f = ttk.Combobox(fs, textvariable=self.fam, values=['Helvetica','Times-Roman','Courier']+REGISTERED_FONTS, state="readonly", width=15)
        cb_f.pack(side=tk.LEFT, fill=tk.X, expand=True); cb_f.bind("<<ComboboxSelected>>", lambda e: self.update_callback())
        cb_s = ttk.Combobox(fs, textvariable=self.sty, values=('Regular','Bold','Italic','BoldItalic'), state="readonly", width=10)
        cb_s.pack(side=tk.LEFT); cb_s.bind("<<ComboboxSelected>>", lambda e: self.update_callback())

        c_grp = ttk.LabelFrame(self, text="Appearance", padding=2); c_grp.pack(fill=tk.X, padx=2, pady=1)
        btn = ttk.Frame(c_grp); btn.pack(fill=tk.X)
        for t,c in [("R","#FF0000"),("G","#008000"),("B","#0000FF")]: ttk.Button(btn, text=t, width=3, command=lambda x=c: self.set_hex(x)).pack(side=tk.LEFT, expand=True, fill=tk.X)
        rgb = ttk.Frame(c_grp); rgb.pack(fill=tk.X, pady=1)
        for l,v in [("R",self.col_r),("G",self.col_g),("B",self.col_b)]:
            ttk.Label(rgb, text=l).pack(side=tk.LEFT); ttk.Entry(rgb, textvariable=v, width=3).pack(side=tk.LEFT)
        ttk.Button(rgb, text="Set", width=4, command=self.apply_rgb).pack(side=tk.LEFT)
        self.lbl_sw = tk.Label(rgb, width=4, bg=self.col_hex, relief="sunken"); self.lbl_sw.pack(side=tk.RIGHT)
        
        o_row = ttk.Frame(c_grp); o_row.pack(fill=tk.X)
        ttk.Label(o_row, text="Opac%").pack(side=tk.LEFT)
        ttk.Spinbox(o_row, from_=0, to=100, textvariable=self.opac, width=4, command=self.update_callback).pack(side=tk.LEFT)
        ttk.Checkbutton(o_row, text="Bdr", variable=self.border, command=self.update_callback).pack(side=tk.LEFT, padx=5)
        cb_b = ttk.Combobox(o_row, textvariable=self.border_style, values=("Solid","Dashed","Dotted"), width=6, state="readonly"); cb_b.pack(side=tk.LEFT)
        cb_b.bind("<<ComboboxSelected>>", lambda e: self.update_callback())

        p_grp = ttk.LabelFrame(self, text="Positions", padding=2); p_grp.pack(fill=tk.BOTH, expand=True, padx=2, pady=1)
        ttk.Button(p_grp, text="Clear", command=self.clear_pos).pack(anchor="e")
        gf = ttk.Frame(p_grp); gf.pack(expand=True)
        for pid, (lbl, _, r, c) in self.pos_map.items():
            cf = ttk.Frame(gf, borderwidth=1, relief="groove")
            cf.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
            ttk.Checkbutton(cf, text=lbl, variable=self.pos_vars[pid], command=self.update_callback).pack()
            cb = ttk.Combobox(cf, textvariable=self.rot_vars[pid], values=("0","45","90","180","270"), width=3, state="readonly")
            cb.pack(); cb.bind("<<ComboboxSelected>>", lambda e: self.update_callback())

    def select_image(self):
        f = filedialog.askopenfilename(filetypes=[("PNG Image", "*.png")])
        if f: self.image_path.set(f); self.lbl_img_path.config(text=os.path.basename(f), fg="black"); self.update_callback()
    def clear_image(self): self.image_path.set(""); self.lbl_img_path.config(text="No image", fg="gray"); self.update_callback()
    def set_hex(self, h): self.col_hex=h; self.lbl_sw.config(bg=h); self.update_callback()
    def apply_rgb(self):
        try: r,g,b = self.col_r.get(), self.col_g.get(), self.col_b.get(); self.col_hex=f"#{r:02x}{g:02x}{b:02x}"; self.lbl_sw.config(bg=self.col_hex); self.update_callback()
        except: pass
    def clear_pos(self):
        for v in self.pos_vars.values(): v.set(False)
        self.update_callback()
    
    def get_settings_dict(self):
        p_d = {k: {"en": v.get(), "rot": self.rot_vars[k].get()} for k, v in self.pos_vars.items()}
        return {
            "en": self.enabled.get(), "img": self.image_path.get(),
            "t1": self.txt_1.get(), "s1": self.sz_1.get(), "a1": self.align_1.get(),
            "t2": self.txt_2.get(), "s2": self.sz_2.get(), "a2": self.align_2.get(),
            "t3": self.txt_3.get(), "s3": self.sz_3.get(), "a3": self.align_3.get(),
            "fam": self.fam.get(), "sty": self.sty.get(), "op": self.opac.get(), 
            "bd": self.border.get(), "bs": self.border_style.get(), "col": self.col_hex, "pos": p_d
        }
    def load_settings_dict(self, d):
        if not d: return
        try:
            self.enabled.set(d.get("en", False))
            self.image_path.set(d.get("img", "")); 
            if self.image_path.get(): self.lbl_img_path.config(text=os.path.basename(self.image_path.get()), fg="black")
            self.txt_1.set(d.get("t1","")); self.sz_1.set(d.get("s1",20)); self.align_1.set(d.get("a1","Left"))
            self.txt_2.set(d.get("t2","")); self.sz_2.set(d.get("s2",40)); self.align_2.set(d.get("a2","Center"))
            self.txt_3.set(d.get("t3","")); self.sz_3.set(d.get("s3",20)); self.align_3.set(d.get("a3","Center"))
            self.fam.set(d.get("fam","Tahoma")); self.sty.set(d.get("sty","Regular"))
            self.opac.set(d.get("op",50)); self.border.set(d.get("bd",True)); self.border_style.set(d.get("bs","Solid"))
            self.set_hex(d.get("col","#FF0000"))
            for k,v in d.get("pos",{}).items():
                if k in self.pos_vars: self.pos_vars[k].set(v.get("en",False)); self.rot_vars[k].set(v.get("rot","0"))
        except: pass

# --- 9. Main Application ---
class PDFWatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title(TITLEBAR) # Use variable
        self.root.geometry("1450x980")
        
        self.input_file = None; self.doc_ref = None
        self.current_page_idx = 0; self.total_pages = 0; self.tk_img = None
        self.page_mapping = [] 
        
        # UI Vars
        self.compress_var = tk.BooleanVar(value=False)
        self.open_file_var = tk.BooleanVar(value=True)
        self.input_password = None 

        self._setup_ui()
        self.load_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.preview_canvas.bind("<Configure>", self.on_canvas_resize)

    def _setup_ui(self):
        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(main, width=650, padding=2); right = ttk.Frame(main, padding=5)
        main.add(left, weight=0); main.add(right, weight=1)

        f_frame = ttk.Frame(left); f_frame.pack(fill=tk.X, pady=2)
        ttk.Button(f_frame, text="Help / Instructions", command=self.show_help).pack(fill=tk.X, pady=(0, 2))
        
        row1 = ttk.Frame(f_frame); row1.pack(fill=tk.X)
        ttk.Button(row1, text="1. Load PDF File", command=self.load_pdf).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_pg = ttk.Button(row1, text="Manage Pages", command=self.open_page_manager, state=tk.DISABLED)
        self.btn_pg.pack(side=tk.RIGHT, padx=(5,0))
        self.lbl_file = ttk.Label(f_frame, text="No file loaded", foreground="gray"); self.lbl_file.pack(fill=tk.X)

        self.nb = ttk.Notebook(left); self.nb.pack(fill=tk.BOTH, expand=True, pady=2)
        self.tab1 = StampTab(self.nb, self.update_preview, "FETL", "Confidential", True)
        self.tab2 = StampTab(self.nb, self.update_preview, "FETL", "Copy", False)
        self.tab3 = StampTab(self.nb, self.update_preview, "FETL", "Draft", False)
        self.nb.add(self.tab1, text=" Stamp Set 1 "); self.nb.add(self.tab2, text=" Stamp Set 2 "); self.nb.add(self.tab3, text=" Stamp Set 3 ")

        act = ttk.LabelFrame(left, text="Actions", padding=2); act.pack(fill=tk.X, pady=2)
        
        # -- Compression & Auto Open --
        ttk.Checkbutton(act, text="Compress Output (Smaller File Size)", variable=self.compress_var).pack(anchor="w", pady=(0,2))
        ttk.Checkbutton(act, text="Open File after Save", variable=self.open_file_var).pack(anchor="w", pady=(0,2))
        
        ttk.Button(act, text="Refresh Preview", command=self.update_preview).pack(fill=tk.X, pady=1)
        ttk.Button(act, text="Save Settings", command=self.save_settings).pack(fill=tk.X, pady=1)
        
        # Save Trigger
        ttk.Button(act, text="SAVE PDF", command=self.initiate_save).pack(fill=tk.X, pady=3)

        self.canvas_frame = tk.Frame(right, bg="#404040"); self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas = tk.Canvas(self.canvas_frame, bg="#404040", highlightthickness=0); self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        nav = ttk.Frame(right); nav.pack(fill=tk.X, pady=5)
        ttk.Button(nav, text="< Prev", command=self.prev_page).pack(side=tk.LEFT)
        self.lbl_page = ttk.Label(nav, text="0 / 0"); self.lbl_page.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav, text="Next >", command=self.next_page).pack(side=tk.LEFT)

    def show_help(self):
        msg = ("FETL PDF Stamp & Watermark Tools\n============================\n"
               "[ENGLISH]\n1. 'Load PDF' to start.\n2. Use Tabs to set stamps.\n3. 'SAVE PDF' opens Security/Encryption menu.")
        messagebox.showinfo("Help / Instructions", msg)

    def load_pdf(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.input_file = f; self.lbl_file.config(text=os.path.basename(f))
            self.input_password = None 
            try:
                doc = fitz.open(f)
                if doc.is_encrypted:
                    if not doc.authenticate(""):
                        while True:
                            pwd = simpledialog.askstring("Encrypted PDF", "File is encrypted. Enter Password:", show='*')
                            if not pwd: 
                                messagebox.showinfo("Cancelled", "Load cancelled.")
                                return
                            if doc.authenticate(pwd):
                                self.input_password = pwd
                                break
                            else:
                                messagebox.showerror("Error", "Incorrect Password.")
                
                if self.doc_ref: self.doc_ref.close()
                self.doc_ref = doc
                self.total_pages = self.doc_ref.page_count
                self.page_mapping = list(range(self.total_pages))
                self.current_page_idx = 0
                self.btn_pg.config(state=tk.NORMAL)
                self.update_preview()
            except Exception as e: messagebox.showerror("Error", str(e))

    def open_page_manager(self):
        if not self.input_file: return
        PageManagerDialog(self.root, self.total_pages, self.page_mapping, self.on_pages_reordered)

    def on_pages_reordered(self, new_mapping):
        self.page_mapping = new_mapping
        self.total_pages = len(self.page_mapping)
        self.current_page_idx = 0
        self.update_preview()

    def prev_page(self):
        if self.current_page_idx > 0: self.current_page_idx -= 1; self.update_preview()
    def next_page(self):
        if self.current_page_idx < self.total_pages - 1: self.current_page_idx += 1; self.update_preview()

    def get_font_name(self, fam, sty):
        if fam in REGISTERED_FONTS: return "Tahoma-Bold" if fam=="Tahoma" and "Bold" in sty else fam
        base = "Helvetica"
        if fam == "Times-Roman": base = "Times-Roman"
        elif fam == "Courier": base = "Courier"
        suffix = ""
        if "Bold" in sty: suffix += "-Bold"
        if "Italic" in sty: suffix += "-Oblique" if base in ["Helvetica","Courier"] else "-Italic"
        full = base + suffix
        if full == "Times-Roman-Bold": full = "Times-Bold"
        return full

    def draw_stamp_layer(self, c, tab, w, h, used_positions):
        opac = tab.opac.get() / 100.0
        is_image = False
        img_path = tab.image_path.get()
        if img_path and os.path.exists(img_path):
            is_image = True
            try:
                img_reader = ImageReader(img_path)
                iw, ih = img_reader.getSize()
                nat_w, nat_h = iw, ih
            except: is_image = False
        
        if not is_image:
            lines = [(tab.txt_1.get(), tab.sz_1.get(), tab.align_1.get()), (tab.txt_2.get(), tab.sz_2.get(), tab.align_2.get()), (tab.txt_3.get(), tab.sz_3.get(), tab.align_3.get())]
            lines = [(t, s, a) for t, s, a in lines if t.strip()]
            if not lines: return
            
            font_name = self.get_font_name(tab.fam.get(), tab.sty.get())
            pad = 10; max_w, total_h, line_dims = 0, 0, []
            for txt, sz, alg in lines:
                try: c.setFont(font_name, sz)
                except: c.setFont("Helvetica", sz)
                lw = c.stringWidth(txt, font_name, sz); lh = sz * 1.2
                line_dims.append((lw, lh, sz, txt, alg))
                if lw > max_w: max_w = lw
                total_h += lh
            nat_w, nat_h = max_w + pad*2, total_h + pad*2

        try: c.setFillColor(HexColor(tab.col_hex), alpha=opac)
        except: c.setFillColorRGB(0,0,0, alpha=opac)
        try: c.setStrokeColor(HexColor(tab.col_hex), alpha=opac)
        except: pass

        margin = 10 
        off_10_w, off_16_h = w*0.10, h*0.16
        xm, ym = w/2, h/2

        for pid, (lbl, _, r, c_idx) in tab.pos_map.items():
            if tab.pos_vars[pid].get():
                if pid in used_positions: continue
                used_positions.add(pid)
                angle = int(tab.rot_vars[pid].get())
                cx, cy = 0, 0
                if pid == "C": MAX_W, MAX_H = 300, 200
                else: MAX_W, MAX_H = 200, 60
                scale = min(1.0, MAX_W/nat_w if nat_w>MAX_W else 1.0, MAX_H/nat_h if nat_h>MAX_H else 1.0)
                eff_w, eff_h = nat_w * scale, nat_h * scale
                
                x_L_cor, x_R_cor = off_10_w + eff_w/2, w - off_10_w - eff_w/2
                y_T_cor, y_B_cor = h - margin - eff_h/2, margin + eff_h/2
                y_S_top, y_S_bot = h - off_16_h, off_16_h
                x_L_side, x_R_side = margin + eff_h/2, w - margin - eff_h/2

                if pid=="TL": cx,cy = x_L_cor, y_T_cor
                elif pid=="TC": cx,cy = xm, y_T_cor
                elif pid=="TR": cx,cy = x_R_cor, y_T_cor
                elif pid=="LT": cx,cy = x_L_side, y_S_top
                elif pid=="LC": cx,cy = x_L_side, ym
                elif pid=="LB": cx,cy = x_L_side, y_S_bot
                elif pid=="RT": cx,cy = x_R_side, y_S_top
                elif pid=="RC": cx,cy = x_R_side, ym
                elif pid=="RB": cx,cy = x_R_side, y_S_bot
                elif pid=="BL": cx,cy = x_L_cor, y_B_cor
                elif pid=="BC": cx,cy = xm, y_B_cor
                elif pid=="BR": cx,cy = x_R_cor, y_B_cor
                elif pid=="C":  cx,cy = xm, ym

                c.saveState()
                c.translate(cx, cy); c.rotate(angle); c.scale(scale, scale)
                
                if is_image:
                    c.setFillAlpha(opac); c.drawImage(img_reader, -nat_w/2, -nat_h/2, nat_w, nat_h, mask='auto')
                else:
                    if tab.border.get():
                        bs = tab.border_style.get()
                        if bs == "Dotted": c.setDash([2, 2])
                        elif bs == "Dashed": c.setDash([6, 3])
                        else: c.setDash([])
                        c.rect(-nat_w/2, -nat_h/2, nat_w, nat_h, fill=0)
                    cur_y = (total_h / 2) 
                    for (lw, lh, sz, txt, alg) in line_dims:
                        try: c.setFont(font_name, sz)
                        except: c.setFont("Helvetica", sz)
                        dy = cur_y - (sz * 0.95)
                        dx = 0
                        if alg == "Left": dx = -max_w/2
                        elif alg == "Right": dx = max_w/2 - lw
                        if alg == "Center": c.drawCentredString(0, dy, txt)
                        else: c.drawString(dx, dy, txt)
                        cur_y -= lh 
                c.restoreState()

    def get_combined_watermark(self, w, h):
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(w, h))
        used = set()
        for tab in [self.tab1, self.tab2, self.tab3]:
            if tab.enabled.get(): self.draw_stamp_layer(c, tab, w, h, used)
        c.save()
        packet.seek(0)
        return packet
    
    def get_overlay_watermark(self, text, w, h):
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(w, h))
        
        try: c.setFont("Tahoma", 14)
        except: c.setFont("Helvetica-Bold", 14)
        
        c.setFillColorRGB(0.6, 0.6, 0.6, alpha=0.3) 
        
        c.saveState()
        c.translate(w/2, h/2)
        c.rotate(45)
        
        # Spaced 200x100
        max_dim = max(w, h)
        grid_range = int(max_dim / 100) + 4 
        
        for ix in range(-grid_range, grid_range + 1):
            for iy in range(-grid_range, grid_range + 1):
                c.drawCentredString(ix * 200, iy * 100, text)
        
        c.restoreState()
        c.save()
        packet.seek(0)
        return packet

    def on_canvas_resize(self, event):
        if self.doc_ref: self.update_preview()

    def update_preview(self):
        if not self.doc_ref or not self.page_mapping: 
            self.preview_canvas.delete("all")
            return
        if self.current_page_idx >= len(self.page_mapping): self.current_page_idx = 0
            
        try:
            real_page_idx = self.page_mapping[self.current_page_idx]
            if real_page_idx >= self.doc_ref.page_count: return 

            page = self.doc_ref.load_page(real_page_idx)
            
            pix = page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=True)
            mode = "RGBA" if pix.alpha else "RGB"
            bg = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            if mode=="RGBA": bg = Image.alpha_composite(Image.new("RGBA", bg.size, (255,255,255,255)), bg)

            pkt = self.get_combined_watermark(page.rect.width, page.rect.height)
            wm_doc = fitz.open("pdf", pkt.getvalue())
            
            if wm_doc.page_count > 0:
                wm_pix = wm_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2,2), alpha=True)
                wm_img = Image.frombytes("RGBA", [wm_pix.width, wm_pix.height], wm_pix.samples)
                
                if wm_img.size != bg.size:
                    wm_img = wm_img.resize(bg.size, Image.Resampling.LANCZOS)
                
                final = Image.alpha_composite(bg.convert("RGBA"), wm_img)
            else:
                final = bg.convert("RGBA")
            
            cw, ch = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
            if cw < 10: cw, ch = 800, 600 
            iw, ih = final.size
            ratio = min(cw/iw, ch/ih)
            new_w, new_h = int(iw*ratio*0.95), int(ih*ratio*0.95)
            if new_w <= 0: new_w = 100
            if new_h <= 0: new_h = 100
            final = final.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(final)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(cw/2, ch/2, image=self.tk_img, anchor=tk.CENTER)
            self.lbl_page.config(text=f"Page {self.current_page_idx+1} / {len(self.page_mapping)}")
        except Exception as e: print(f"Preview Error: {e}")

    def save_settings(self):
        data = { "t1": self.tab1.get_settings_dict(), "t2": self.tab2.get_settings_dict(), "t3": self.tab3.get_settings_dict(), "win": self.root.geometry(), "comp": self.compress_var.get() }
        try:
            with open("settings.json", "w") as f: json.dump(data, f, indent=4)
            print("[INFO] Settings Saved.")
        except: pass

    def load_settings(self):
        if not os.path.exists("settings.json"): return
        try:
            with open("settings.json", "r") as f: d = json.load(f)
            if "win" in d: self.root.geometry(d["win"])
            if "comp" in d: self.compress_var.set(d["comp"])
            self.tab1.load_settings_dict(d.get("t1"))
            self.tab2.load_settings_dict(d.get("t2"))
            self.tab3.load_settings_dict(d.get("t3"))
            print("[INFO] Settings Loaded.")
        except: pass

    def on_close(self):
        self.save_settings()
        self.root.destroy()

    def generate_random_password(self):
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for i in range(12))

    def initiate_save(self):
        if not self.input_file: return
        
        # Trigger popup for options
        dlg = SecurityDialog(self.root)
        self.root.wait_window(dlg)
        
        if dlg.result is None:
            return # Cancelled
            
        self.save_pdf(dlg.result)

    def save_pdf(self, options):
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out: return
        
        user_password = None
        owner_password = None
        
        # Handle Password
        if options["encrypt"]:
            if options["pass_mode"] == "Manual":
                user_password = options["manual_user"]
                if options["manual_owner"].strip():
                    owner_password = options["manual_owner"]
                else:
                    owner_password = self.generate_random_password()
            else: # Random
                user_password = self.generate_random_password()
                owner_password = self.generate_random_password()
            
            # Save passwords to file (for both Manual and Random)
            try:
                with open(out + ".pass", "w") as f:
                    f.write(f"User Password: {user_password}\n")
                    f.write(f"Owner Password: {owner_password}\n")
            except: pass

        # -- Saving Process --
        is_overwrite = (os.path.abspath(out) == os.path.abspath(self.input_file))
        try:
            if is_overwrite: self.doc_ref.close()

            with open(self.input_file, "rb") as f: input_stream = io.BytesIO(f.read())
            r = PdfReader(input_stream)
            
            # Decrypt Input if needed
            if r.is_encrypted and self.input_password:
                r.decrypt(self.input_password)
                
            w = PdfWriter()
            
            for real_idx in self.page_mapping:
                if real_idx < len(r.pages):
                    p = r.pages[real_idx]
                    
                    # 1. Normalizing Rotation Strategy:
                    try: p.transfer_rotation_to_content()
                    except: pass
                    
                    # 2. Standard Stamps
                    pkt = self.get_combined_watermark(float(p.mediabox.width), float(p.mediabox.height))
                    wm_reader = PdfReader(pkt)
                    if len(wm_reader.pages) > 0: p.merge_page(wm_reader.pages[0])
                    
                    # 3. Tiled Watermark
                    tiled_text = options["tiled_text"]
                    if tiled_text.strip():
                        overlay_pkt = self.get_overlay_watermark(tiled_text, float(p.mediabox.width), float(p.mediabox.height))
                        overlay_reader = PdfReader(overlay_pkt)
                        if len(overlay_reader.pages) > 0: p.merge_page(overlay_reader.pages[0]) 

                    w.add_page(p)
            
            # -- Apply Encryption --
            if user_password:
                perms = UserAccessPermissions(0) 
                if options["allow_print"]: perms |= UserAccessPermissions.PRINT
                if options["allow_copy"]: perms |= UserAccessPermissions.EXTRACT
                
                w.encrypt(user_password=user_password, owner_password=owner_password, permissions_flag=perms, algorithm="AES-128")

            with open(out, "wb") as f_out: w.write(f_out)
            
            # -- Compression --
            if self.compress_var.get() and not user_password:
                temp_compressed = out + ".tmp"
                try:
                    doc = fitz.open(out)
                    doc.save(temp_compressed, garbage=4, deflate=True)
                    doc.close()
                    shutil.move(temp_compressed, out) 
                except: 
                    if os.path.exists(temp_compressed): os.remove(temp_compressed)

            if is_overwrite:
                self.doc_ref = fitz.open(self.input_file)
                self.update_preview()
            
            msg = f"Saved: {out}"
            if user_password: msg += f"\nPasswords saved to {os.path.basename(out)}.pass"
            messagebox.showinfo("Done", msg)
            
            if self.open_file_var.get() and os.name == 'nt':
                os.startfile(out)
        
        except Exception as e: 
            messagebox.showerror("Error", str(e))
            if is_overwrite:
                 try: self.doc_ref = fitz.open(self.input_file)
                 except: pass

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--build": build_executable()
    else:
        root = tk.Tk()
        try: from ctypes import windll; windll.shcore.SetProcessDpiAwareness(1)
        except: pass
        PDFWatermarkApp(root); root.mainloop()
