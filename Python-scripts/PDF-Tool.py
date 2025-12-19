# --------------------------------------------------------------------------------
# Application Specification: PDF Stamp & Watermark Tool
# --------------------------------------------------------------------------------
# Program Name: pdfstamp.py
# Version:      8.7 (Fixes: Text Alignment/Selection, Arrow Weight)
# Author:       Senior Developer (Gemini)
# Created:      2025-12-19
# Environment:  Windows 10/11 (Python 3.10+)
#
# 1. OVERVIEW
#    A professional-grade GUI application designed to apply digital stamps, 
#    watermarks, and custom elements to PDF documents. It features a modern 
#    Tkinter interface with real-time previewing, allowing users to manipulate 
#    PDF pages and overlays visually before saving.
#
# 2. DETAILED SPECIFICATIONS & FEATURES
#
#    A. Multi-Layer Stamping System
#       - **Architecture**: 3 Independent Stamp Layers (Set 1, Set 2, Set 3).
#       - **Content Modes**: 
#         1. Text: Supports up to 3 lines per stamp set.
#         2. Image: Supports PNG/JPG logos with transparency.
#       - **Styling**: 
#         - Fonts: Auto-scans system fonts + internal fallbacks (Tahoma, Helvetica).
#         - Colors: HEX input or RGB sliders with visual preview.
#         - Opacity: 0-100% alpha blending.
#         - Borders: Solid, Dashed, or Dotted styles around the stamp area.
#       - **Positioning**: 
#         - 5x3 Matrix (Top/Center/Bottom x Left/Center/Right).
#         - Advanced alignment options (e.g., "Left-Top" aligns to margin start).
#         - Rotation: 0, 45, 90, 135, 180, 225, 270, 315 degrees.
#       - **Safety Algorithm**: Calculates rotated bounding boxes to strictly enforce
#         edge margins (10px - 25px), preventing stamps from being cut off.
#
#    B. Page Management
#       - **Manager**: dedicated dialog to reorder or delete pages.
#       - **Visual Feedback**: Real-time preview updates when pages are moved.
#
#    C. Custom Interactive Canvas (The "Overlay" Engine)
#       - **Concept**: A WYSIWYG editor overlaid on the PDF page preview.
#       - **Elements**:
#         1. **Text**: Add custom strings with specific font, size, color, angle.
#            - *Optimization (v8.6)*: Tight bounding box calculation for selection.
#         2. **Image**: Place external images with scaling and opacity control.
#         3. **Arrow**: Vector-drawn directional arrows with custom length/angle/color.
#       - **Interaction**:
#         - Click to Select (Red bounding box).
#         - Drag body to Move.
#         - Drag red handle (bottom-right) to Resize/Scale.
#         - Double-click to open Property Editor.
#         - Right-click context menu to Delete.
#         - Undo/Redo support (Ctrl+Z) with history stack.
#
#    D. Security & Encryption
#       - **Input**: Automatically handles password-protected input PDFs.
#       - **Output**: 
#         - AES-128 Encryption.
#         - User Password (for opening).
#         - Owner Password (for permissions).
#         - Permission toggles: Printing (Default: Off), Content Copying (Default: Off).
#         - Password Generation: Manual entry or Cryptographically secure random generation.
#
#    E. Output Optimization
#       - **Compression**: Optional "Garbage Collection" and stream deflation via PyMuPDF.
#       - **Tiled Watermark**: Optional diagonal text overlay across the entire page.
#
#    F. System Integration
#       - **Dependency Management**: Auto-installs `pymupdf`, `pypdf`, `reportlab`, `pillow`.
#       - **Proxy Support**: Respects system env vars and `--proxy` arg for pip installs.
#       - **Configuration**: Persists UI state to `settings.json`.
#       - **Build Ready**: Includes `build_executable()` function for PyInstaller.
#
# 3. BUILD INSTRUCTIONS
#    Command: python pdfstamp.py --build
#    Logic:
#      - Installs PyInstaller if missing.
#      - Runs: pyinstaller --noconfirm --onedir --windowed --name "PDF_Tools"
#        --hidden-import pypdf --hidden-import reportlab --hidden-import fitz 
#        --hidden-import PIL --hidden-import tkinter --clean pdfstamp.py
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
import glob
import copy

# --- CONFIGURATION ---
TITLEBAR = "PDF Tools"
APPNAME  = "PDF_Tool" 
COLOR_TO_HEX = {
    "Red": "#FF0000", "Green": "#008000", "Blue": "#0000FF", 
    "Black": "#000000", "Grey": "#808080", "Yellow": "#FFFF00"
}
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
from tkinter import filedialog, messagebox, ttk, simpledialog, colorchooser, font
from PIL import Image, ImageTk, ImageFont, ImageDraw, ImageOps
import fitz
from pypdf import PdfReader, PdfWriter, PageObject
from pypdf.constants import UserAccessPermissions
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# --- 4. Font Registration ---
REGISTERED_FONTS = []
SYSTEM_FONT_MAP = {} 

def register_fonts():
    dirs = [r"C:\Windows\Fonts", r"C:\WINNT\Fonts", "/usr/share/fonts", "/Library/Fonts"]
    priority = [
        ("Tahoma", ["tahoma.ttf"]), 
        ("Segoe Print", ["segoepr.ttf", "segoeprb.ttf"]),
        ("Thai-Angsana", ["angsa.ttc","angsana.ttc"]), 
        ("JP-MSGothic", ["msgothic.ttc"]), 
        ("CN-SimHei", ["simhei.ttf"]), 
        ("Arial-Unicode", ["arialuni.ttf"])
    ]
    for name, fnames in priority:
        for d in dirs:
            for fn in fnames:
                fp = os.path.join(d, fn)
                if os.path.exists(fp):
                    try: 
                        pdfmetrics.registerFont(TTFont(name, fp))
                        REGISTERED_FONTS.append(name)
                        SYSTEM_FONT_MAP[name] = fp
                        break 
                    except: pass
            if name in REGISTERED_FONTS: break

    for d in dirs:
        if os.path.exists(d):
            for fp in glob.glob(os.path.join(d, "*.ttf")):
                fn = os.path.basename(fp)
                name = fn.split(".")[0].replace("-", " ").title()
                if name not in SYSTEM_FONT_MAP:
                    SYSTEM_FONT_MAP[name] = fp
register_fonts()

# --- 5. Build Automation ---
def build_executable():
    install_and_import("pyinstaller", "PyInstaller", PROXY_URL)
    script_name = os.path.basename(__file__)
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

# --- 6. Dialog: Custom Item (Add/Edit) ---
class CustomItemDialog(tk.Toplevel):
    def __init__(self, parent, edit_data=None):
        super().__init__(parent)
        self.title("Custom Element")
        self.geometry("420x480") 
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.edit_data = edit_data
        
        self.type_var = tk.StringVar(value="Text")
        
        # Text Vars
        self.text_content = tk.StringVar(value="")
        self.font_fam = tk.StringVar(value="Tahoma")
        self.font_size = tk.IntVar(value=24)
        self.font_color = "#000000"
        self.text_angle = tk.IntVar(value=0)
        self.text_opacity = tk.IntVar(value=100)
        
        # Image Vars
        self.img_path = tk.StringVar(value="")
        self.img_width = tk.IntVar(value=200)
        self.img_opacity = tk.IntVar(value=100)
        
        # Arrow Vars
        self.arrow_color = tk.StringVar(value="Red")
        self.arrow_angle = tk.StringVar(value="0")
        self.arrow_opacity = tk.IntVar(value=100)
        self.arrow_size = tk.IntVar(value=80) 

        if edit_data:
            # Fix mapping for "img" -> "Image" for UI
            t_raw = edit_data['type']
            if t_raw == 'img': self.type_var.set("Image")
            else: self.type_var.set(t_raw.capitalize())
            
            if edit_data['type'] == 'text':
                self.text_content.set(edit_data.get('content',''))
                self.font_fam.set(edit_data.get('font','Tahoma'))
                self.font_size.set(edit_data.get('size',24))
                self.font_color = edit_data.get('color','#000000')
                self.text_angle.set(edit_data.get('angle',0))
                self.text_opacity.set(int(edit_data.get('opacity',1.0)*100))
            elif edit_data['type'] == 'img':
                self.img_path.set(edit_data.get('path',''))
                self.img_width.set(edit_data.get('w',200))
                self.img_opacity.set(int(edit_data.get('opacity',1.0)*100))
            elif edit_data['type'] == 'arrow':
                self.arrow_color.set(edit_data.get('color_name', 'Red'))
                self.arrow_angle.set(str(edit_data.get('angle',0)))
                self.arrow_opacity.set(int(edit_data.get('opacity',1.0)*100))
                self.arrow_size.set(edit_data.get('len', 80))

        self._build_ui()
        
    def _build_ui(self):
        # Type Selection (Compact)
        type_f = ttk.Frame(self); type_f.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(type_f, text="Type:").pack(side=tk.LEFT)
        for t in ["Text", "Image", "Arrow"]:
            rb = ttk.Radiobutton(type_f, text=t, variable=self.type_var, value=t, command=self._toggle_ui)
            rb.pack(side=tk.LEFT, padx=10)
            if self.edit_data: rb.configure(state="disabled") 
        
        self.main_frame = ttk.Frame(self, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Buttons
        btn_f = ttk.Frame(self, padding=5)
        btn_f.pack(side=tk.BOTTOM, fill=tk.X)
        txt = "Save" if self.edit_data else "Add"
        ttk.Button(btn_f, text=txt, command=self._apply).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_f, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)

        self._toggle_ui()

    def _toggle_ui(self):
        for widget in self.main_frame.winfo_children(): widget.destroy()
        t = self.type_var.get()
        
        if t == "Text":
            self._grid_row(0, "Text:", ttk.Entry(self.main_frame, textvariable=self.text_content, width=35))
            font_list = ["Tahoma", "Segoe Print"] + sorted([f for f in SYSTEM_FONT_MAP.keys() if f not in ["Tahoma", "Segoe Print"]])
            self._grid_row(1, "Font:", ttk.Combobox(self.main_frame, textvariable=self.font_fam, values=font_list, state="readonly"))
            
            r2 = ttk.Frame(self.main_frame); r2.grid(row=2, column=1, sticky="w")
            ttk.Label(self.main_frame, text="Size/Col:").grid(row=2, column=0, sticky="w")
            ttk.Spinbox(r2, textvariable=self.font_size, from_=8, to=300, width=5).pack(side=tk.LEFT)
            self.btn_col = tk.Button(r2, text="Color", bg=self.font_color, fg="white", command=self._choose_color, width=6)
            self.btn_col.pack(side=tk.LEFT, padx=5)

            r3 = ttk.Frame(self.main_frame); r3.grid(row=3, column=1, sticky="w", pady=5)
            ttk.Label(self.main_frame, text="Ang/Opac:").grid(row=3, column=0, sticky="w")
            ttk.Spinbox(r3, textvariable=self.text_angle, values=list(range(0, 360, 15)), width=4).pack(side=tk.LEFT)
            ttk.Scale(r3, variable=self.text_opacity, from_=0, to=100, orient=tk.HORIZONTAL, length=100).pack(side=tk.LEFT, padx=5)

        elif t == "Image":
            fr = ttk.Frame(self.main_frame); fr.grid(row=0, column=1, sticky="w")
            ttk.Label(self.main_frame, text="File:").grid(row=0, column=0, sticky="w")
            ttk.Entry(fr, textvariable=self.img_path, width=25).pack(side=tk.LEFT)
            ttk.Button(fr, text="...", width=3, command=self._browse_img).pack(side=tk.LEFT)
            
            self._grid_row(1, "Width:", ttk.Spinbox(self.main_frame, textvariable=self.img_width, from_=10, to=2000, width=8))
            self._grid_row(2, "Opacity:", ttk.Scale(self.main_frame, variable=self.img_opacity, from_=0, to=100, orient=tk.HORIZONTAL))

        elif t == "Arrow":
            colors = sorted(list(COLOR_TO_HEX.keys()))
            self._grid_row(0, "Color:", ttk.Combobox(self.main_frame, textvariable=self.arrow_color, values=colors, state="readonly"))
            
            # Angles: 0 to 315
            angles = [str(x) for x in range(0, 360, 45)]
            self._grid_row(1, "Angle:", ttk.Combobox(self.main_frame, textvariable=self.arrow_angle, values=angles, state="readonly"))
            
            self._grid_row(2, "Len (px):", ttk.Spinbox(self.main_frame, textvariable=self.arrow_size, from_=20, to=1000, width=8))
            self._grid_row(3, "Opacity:", ttk.Scale(self.main_frame, variable=self.arrow_opacity, from_=0, to=100, orient=tk.HORIZONTAL))

    def _grid_row(self, r, lbl, widget):
        ttk.Label(self.main_frame, text=lbl).grid(row=r, column=0, sticky="w", pady=5)
        widget.grid(row=r, column=1, sticky="w", pady=5)

    def _choose_color(self):
        c = colorchooser.askcolor(color=self.font_color, title="Text Color")[1]
        if c: self.font_color = c; self.btn_col.config(bg=c)

    def _browse_img(self):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if f: self.img_path.set(f)

    def _apply(self):
        t = self.type_var.get()
        if t == "Text":
            if not self.text_content.get(): messagebox.showwarning("Missing", "Enter content."); return
            self.result = {"type": "text", "content": self.text_content.get(), "font": self.font_fam.get(), "size": self.font_size.get(), "color": self.font_color, "angle": self.text_angle.get(), "opacity": self.text_opacity.get() / 100.0}
        elif t == "Image":
            if not self.img_path.get(): messagebox.showwarning("Missing", "Select image."); return
            self.result = { "type": "img", "path": self.img_path.get(), "w": self.img_width.get(), "opacity": self.img_opacity.get() / 100.0}
        elif t == "Arrow":
            self.result = {"type": "arrow", "color_name": self.arrow_color.get(), "angle": int(self.arrow_angle.get()), "opacity": self.arrow_opacity.get() / 100.0, "len": self.arrow_size.get()}
        self.destroy()

# --- 7. Page Manager ---
class PageManagerDialog(tk.Toplevel):
    def __init__(self, parent, page_count, current_mapping, callback):
        super().__init__(parent); self.title("Page Manager"); self.geometry("400x500"); self.transient(parent); self.grab_set()
        self.page_count = page_count; self.mapping = list(current_mapping); self.callback = callback
        ttk.Label(self, text="Select pages to move or delete:", font=("", 10, "bold")).pack(pady=10)
        f=ttk.Frame(self); f.pack(fill=tk.BOTH, expand=True, padx=10)
        sb=ttk.Scrollbar(f, orient=tk.VERTICAL); self.lb=tk.Listbox(f, yscrollcommand=sb.set, selectmode=tk.SINGLE, font=("Courier", 10))
        sb.config(command=self.lb.yview); sb.pack(side=tk.RIGHT, fill=tk.Y); self.lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.refresh(); b=ttk.Frame(self); b.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(b,text="Up",command=self.up).pack(side=tk.LEFT); ttk.Button(b,text="Down",command=self.down).pack(side=tk.LEFT)
        ttk.Button(b,text="Delete",command=self.dele).pack(side=tk.LEFT); ttk.Button(b,text="Apply",command=self.apply).pack(side=tk.RIGHT)
    def refresh(self):
        self.lb.delete(0, tk.END)
        for i, original_idx in enumerate(self.mapping): self.lb.insert(tk.END, f"New Page {i+1}  (Original Page {original_idx+1})")
    def up(self):
        s=self.lb.curselection(); 
        if s and s[0]>0: i=s[0]; self.mapping[i], self.mapping[i-1] = self.mapping[i-1], self.mapping[i]; self.refresh(); self.lb.selection_set(i-1)
    def down(self):
        s=self.lb.curselection(); 
        if s and s[0]<len(self.mapping)-1: i=s[0]; self.mapping[i], self.mapping[i+1] = self.mapping[i+1], self.mapping[i]; self.refresh(); self.lb.selection_set(i+1)
    def dele(self): 
        s=self.lb.curselection(); 
        if s: del self.mapping[s[0]]; self.refresh()
    def apply(self):
        if not self.mapping: messagebox.showwarning("Warning", "Cannot have empty document."); return
        self.callback(self.mapping); self.destroy()

# --- 8. Security & Save Options (Compact & Labeled) ---
class SecurityDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Save & Security")
        self.geometry("450x550") # Reduced height
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.enc = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value="Manual")
        self.mpass = tk.StringVar()
        self.mown = tk.StringVar()
        self.prn = tk.BooleanVar(value=False) # Fix: Disabled by default
        self.cpy = tk.BooleanVar(value=False) # Fix: Disabled by default
        self.watermark_text = tk.StringVar()
        
        self._init_ui()

    def _init_ui(self):
        p = ttk.Frame(self, padding=10)
        p.pack(fill=tk.BOTH, expand=True)

        # 1. Encryption Frame
        f = ttk.LabelFrame(p, text="1. Security Settings", padding=5)
        f.pack(fill=tk.X, pady=(0, 5))

        # Checkbox + Radio row
        top_row = ttk.Frame(f); top_row.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(top_row, text="Enable Encryption", variable=self.enc, command=self.toggle_state).pack(side=tk.LEFT)
        
        self.r_man = ttk.Radiobutton(f, text="Manual Configuration", variable=self.mode, value="Manual", command=self.toggle_state)
        self.r_man.pack(anchor="w", padx=10, pady=(5,0))
        
        # Manual Input Area (Grid for Labels)
        self.f_man = ttk.Frame(f, padding=(20, 0))
        self.f_man.pack(fill=tk.X, pady=2)
        
        ttk.Label(self.f_man, text="User Password:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.eu = ttk.Entry(self.f_man, textvariable=self.mpass, show="*", width=22)
        self.eu.grid(row=0, column=1, sticky="w", pady=2)
        
        ttk.Label(self.f_man, text="Owner Password:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.eo = ttk.Entry(self.f_man, textvariable=self.mown, show="*", width=22)
        self.eo.grid(row=1, column=1, sticky="w", pady=2)

        self.r_auto = ttk.Radiobutton(f, text="Auto-Generate (Random Passwords)", variable=self.mode, value="Random", command=self.toggle_state)
        self.r_auto.pack(anchor="w", padx=10, pady=(2, 5))

        # 2. Permissions
        fp = ttk.LabelFrame(p, text="2. Permissions", padding=5)
        fp.pack(fill=tk.X, pady=5)
        perm_row = ttk.Frame(fp); perm_row.pack(fill=tk.X)
        ttk.Checkbutton(perm_row, text="Allow Printing", variable=self.prn).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(perm_row, text="Allow Copying", variable=self.cpy).pack(side=tk.LEFT, padx=10)

        # 3. Watermark
        fw = ttk.LabelFrame(p, text="3. Tiled Text Overlay", padding=5)
        fw.pack(fill=tk.X, pady=5)
        self.cb = ttk.Combobox(fw, textvariable=self.watermark_text, values=["", "Confidential", "Draft", "Copy", "Internal Use Only"])
        self.cb.pack(fill=tk.X, pady=2)

        # Buttons
        b = ttk.Frame(p, padding=(0, 15, 0, 0))
        b.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(b, text="Save PDF", command=self.on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(b, text="Cancel", command=self.on_cancel).pack(side=tk.RIGHT)

        self.toggle_state()

    def toggle_state(self):
        is_enc = self.enc.get()
        is_man = self.mode.get() == "Manual"
        
        state_all = 'normal' if is_enc else 'disabled'
        self.r_man.configure(state=state_all)
        self.r_auto.configure(state=state_all)
        
        state_entries = 'normal' if is_enc and is_man else 'disabled'
        self.eu.configure(state=state_entries)
        self.eo.configure(state=state_entries)
        
        # Visual feedback for disabled grid area
        for child in self.f_man.winfo_children():
            try: child.configure(state=state_entries)
            except: pass

    def on_save(self):
        self.result = {
            "encrypt": self.enc.get(),
            "pass_mode": self.mode.get(),
            "manual_user": self.mpass.get(),
            "manual_owner": self.mown.get(),
            "allow_print": self.prn.get(),
            "allow_copy": self.cpy.get(),
            "tiled_text": self.watermark_text.get()
        }
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

# --- 9. Component: Stamp Tab ---
class StampTab(ttk.Frame):
    def __init__(self, parent, update_callback, text_l1="", text_l2="Confidential", default_enabled=False):
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
        self.margin_var = tk.IntVar(value=20)

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
        self.lbl_img_path = ttk.Label(img_row, text="No image", foreground="gray")
        self.lbl_img_path.pack(side=tk.LEFT, padx=5)

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
        m_row = ttk.Frame(p_grp); m_row.pack(fill=tk.X, pady=2)
        ttk.Label(m_row, text="Edge Margin:").pack(side=tk.LEFT)
        cb_m = ttk.Combobox(m_row, textvariable=self.margin_var, values=("10", "15", "20", "25"), width=4, state="readonly")
        cb_m.pack(side=tk.LEFT, padx=5)
        cb_m.bind("<<ComboboxSelected>>", lambda e: self.update_callback())
        ttk.Button(m_row, text="Clear", command=self.clear_pos).pack(side=tk.RIGHT)

        gf = ttk.Frame(p_grp); gf.pack(expand=True)
        # Updated Rotation Angles
        rot_vals = ("0","45","90","135","180","225","270","315")
        for pid, (lbl, _, r, c) in self.pos_map.items():
            cf = ttk.Frame(gf, borderwidth=1, relief="groove")
            cf.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
            ttk.Checkbutton(cf, text=lbl, variable=self.pos_vars[pid], command=self.update_callback).pack()
            cb = ttk.Combobox(cf, textvariable=self.rot_vars[pid], values=rot_vals, width=3, state="readonly")
            cb.pack(); cb.bind("<<ComboboxSelected>>", lambda e: self.update_callback())

    def select_image(self):
        f = filedialog.askopenfilename(filetypes=[("PNG Image", "*.png")])
        if f: 
            self.image_path.set(f)
            self.lbl_img_path.configure(text=os.path.basename(f), foreground="black")
            self.update_callback()
    
    def clear_image(self): 
        self.image_path.set("")
        self.lbl_img_path.configure(text="No image", foreground="gray")
        self.update_callback()
    
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
            "bd": self.border.get(), "bs": self.border_style.get(), "col": self.col_hex, 
            "pos": p_d, "margin": self.margin_var.get()
        }
    def load_settings_dict(self, d):
        if not d: return
        try:
            self.enabled.set(d.get("en", False))
            self.image_path.set(d.get("img", "")); 
            if self.image_path.get(): self.lbl_img_path.configure(text=os.path.basename(self.image_path.get()), foreground="black")
            self.txt_1.set(d.get("t1","")); self.sz_1.set(d.get("s1",20)); self.align_1.set(d.get("a1","Left"))
            self.txt_2.set(d.get("t2","")); self.sz_2.set(d.get("s2",40)); self.align_2.set(d.get("a2","Center"))
            self.txt_3.set(d.get("t3","")); self.sz_3.set(d.get("s3",20)); self.align_3.set(d.get("a3","Center"))
            self.fam.set(d.get("fam","Tahoma")); self.sty.set(d.get("sty","Regular"))
            self.opac.set(d.get("op",50)); self.border.set(d.get("bd",True)); self.border_style.set(d.get("bs","Solid"))
            self.set_hex(d.get("col","#FF0000"))
            self.margin_var.set(d.get("margin", 20))
            for k,v in d.get("pos",{}).items():
                if k in self.pos_vars: self.pos_vars[k].set(v.get("en",False)); self.rot_vars[k].set(v.get("rot","0"))
        except: pass

# --- 10. Main Application ---
class PDFWatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title(TITLEBAR)
        self.root.geometry("960x1152")
        
        self.input_file = None; self.doc_ref = None
        self.current_page_idx = 0; self.total_pages = 0; self.tk_img = None
        self.page_mapping = [] 
        
        # UI Vars
        self.compress_var = tk.BooleanVar(value=False)
        self.open_file_var = tk.BooleanVar(value=True)
        self.input_password = None 

        # Custom Elements Storage
        self.custom_overlays = {} 
        self.canvas_images = [] # Prevent GC for preview images
        self.current_preview_ratio = 1.0

        # Undo System
        self.undo_stack = [] 
        self.MAX_UNDO = 20

        # Interaction State
        self.selected_item_uid = None
        self.interaction_mode = None 
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.initial_item_vals = {} 
        self.dragging_in_progress = False 

        self._setup_ui()
        self.load_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.preview_canvas.bind("<Configure>", self.on_canvas_resize)
        
        # Bindings
        self.preview_canvas.bind("<Button-1>", self.on_canvas_click)
        self.preview_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.preview_canvas.bind("<Button-3>", self.on_right_click)
        self.preview_canvas.bind("<Double-Button-1>", self.edit_custom_item)
        
        # Undo Binding
        self.root.bind("<Control-z>", self.undo)

    def _setup_ui(self):
        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(main, width=650, padding=2); right = ttk.Frame(main, padding=5)
        main.add(left, weight=0); main.add(right, weight=1)

        # --- LEFT PANEL ---
        f_frame = ttk.Frame(left); f_frame.pack(fill=tk.X, pady=2)
        ttk.Button(f_frame, text="Help / Instructions", command=self.show_help).pack(fill=tk.X, pady=(0, 2))
        
        row1 = ttk.Frame(f_frame); row1.pack(fill=tk.X)
        ttk.Button(row1, text="1. Load PDF File", command=self.load_pdf).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_pg = ttk.Button(row1, text="Manage Pages", command=self.open_page_manager, state=tk.DISABLED)
        self.btn_pg.pack(side=tk.RIGHT, padx=(5,0))
        self.lbl_file = ttk.Label(f_frame, text="No file loaded", foreground="gray"); self.lbl_file.pack(fill=tk.X)

        self.nb = ttk.Notebook(left); self.nb.pack(fill=tk.BOTH, expand=True, pady=2)
        self.tab1 = StampTab(self.nb, self.update_preview, "", "Confidential", True)
        self.tab2 = StampTab(self.nb, self.update_preview, "", "Copy", False)
        self.tab3 = StampTab(self.nb, self.update_preview, "", "Draft", False)
        self.nb.add(self.tab1, text=" Stamp Set 1 "); self.nb.add(self.tab2, text=" Stamp Set 2 "); self.nb.add(self.tab3, text=" Stamp Set 3 ")

        act = ttk.LabelFrame(left, text="Actions", padding=2); act.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(act, text="Compress Output (Smaller File Size)", variable=self.compress_var).pack(anchor="w", pady=(0,2))
        ttk.Checkbutton(act, text="Open File after Save", variable=self.open_file_var).pack(anchor="w", pady=(0,2))
        
        ttk.Button(act, text="Refresh Preview", command=self.update_preview).pack(fill=tk.X, pady=1)
        ttk.Button(act, text="Save Settings", command=self.save_settings).pack(fill=tk.X, pady=1)
        ttk.Button(act, text="Reload Settings", command=self.reload_settings_action).pack(fill=tk.X, pady=1)
        ttk.Button(act, text="SAVE PDF", command=self.initiate_save).pack(fill=tk.X, pady=3)

        # --- RIGHT PANEL ---
        cust_tools = ttk.LabelFrame(right, text="Custom Page Elements", padding=2)
        cust_tools.pack(fill=tk.X, pady=(0, 5), side=tk.TOP)
        
        ct_row = ttk.Frame(cust_tools); ct_row.pack(fill=tk.X)
        ttk.Button(ct_row, text="+ Add Item", command=self.add_custom_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(ct_row, text="Edit Selected", command=lambda: self.edit_custom_item(None)).pack(side=tk.LEFT, padx=5)
        ttk.Button(ct_row, text="Undo (Ctrl+Z)", command=lambda: self.undo(None)).pack(side=tk.LEFT, padx=5)
        ttk.Button(ct_row, text="Clear Page", command=self.clear_custom_page).pack(side=tk.RIGHT, padx=5)

        self.canvas_frame = tk.Frame(right, bg="#404040"); self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas = tk.Canvas(self.canvas_frame, bg="#404040", highlightthickness=0); self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        
        nav = ttk.Frame(right); nav.pack(fill=tk.X, pady=5)
        ttk.Button(nav, text="< Prev", command=self.prev_page).pack(side=tk.LEFT)
        self.lbl_page = ttk.Label(nav, text="0 / 0"); self.lbl_page.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav, text="Next >", command=self.next_page).pack(side=tk.LEFT)

    def show_help(self):
        msg = ("PDF Stamp & Watermark Tools\n============================\n"
               "[ENGLISH]\n"
               "1. 'Load PDF' to start.\n"
               "2. 'Custom Page Elements' (Top Right):\n"
               "   - Add Text, Images, or Arrows.\n"
               "   - CLICK item to SELECT (Red Box).\n"
               "   - DOUBLE CLICK to EDIT properties.\n"
               "   - DRAG body to MOVE.\n"
               "   - DRAG red handle (bottom-right) to RESIZE.\n"
               "   - Use 'Undo' or Ctrl+Z to revert.\n"
               "3. 'SAVE PDF' opens Security/Encryption menu.")
        messagebox.showinfo("Help / Instructions", msg)

    # --- UNDO SYSTEM ---
    def save_state(self):
        state = copy.deepcopy(self.custom_overlays)
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)

    def undo(self, event):
        if not self.undo_stack: 
            return
        last_state = self.undo_stack.pop()
        self.custom_overlays = last_state
        self.selected_item_uid = None
        self.update_preview()

    # --- CANVAS INTERACTION LOGIC ---
    def get_item_data_by_uid(self, uid):
        real_idx = self.page_mapping[self.current_page_idx]
        if real_idx in self.custom_overlays:
            return next((x for x in self.custom_overlays[real_idx] if x['uid'] == uid), None)
        return None

    def on_canvas_click(self, event):
        clicked_items = self.preview_canvas.find_closest(event.x, event.y)
        if not clicked_items:
            self.selected_item_uid = None
            self.update_preview()
            return
            
        top_item = clicked_items[0]
        tags = self.preview_canvas.gettags(top_item)
        
        # 1. Handle RESIZE Click
        if "resize_handle" in tags and self.selected_item_uid:
            self.save_state() # Save before resize
            self.interaction_mode = "RESIZE"
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            
            data = self.get_item_data_by_uid(self.selected_item_uid)
            if data:
                real_idx = self.page_mapping[self.current_page_idx]
                page = self.doc_ref.load_page(real_idx)
                pdf_h = page.rect.height
                
                cw, ch = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
                if self.tk_img:
                    img_x = (cw/2) - (self.tk_img.width()/2)
                    img_y = (ch/2) - (self.tk_img.height()/2)
                else: img_x, img_y = 0, 0
                
                cx_scr = img_x + (data['x'] * 2 * self.current_preview_ratio)
                cy_scr = img_y + ((pdf_h - data['y']) * 2 * self.current_preview_ratio)
                
                dist = math.hypot(event.x - cx_scr, event.y - cy_scr)
                if dist < 1: dist = 1
                
                self.initial_item_vals = {
                    'dist': dist,
                    'size': data['size'] if data['type'] == 'text' else 0,
                    'w': data['w'] if data['type'] == 'img' else 0,
                    'len': data['len'] if data['type'] == 'arrow' else 0
                }
            return

        # 2. Handle MOVE Click
        uid = next((t for t in tags if t.startswith("uid:")), None)
        if uid:
            self.selected_item_uid = uid
            self.interaction_mode = "MOVE"
            self.save_state() # Save before move
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            data = self.get_item_data_by_uid(uid)
            if data:
                self.initial_item_vals = {'x': data['x'], 'y': data['y']}
            self.update_preview()
        else:
            self.selected_item_uid = None
            self.interaction_mode = None
            self.update_preview()

    def on_canvas_drag(self, event):
        if not self.interaction_mode or not self.selected_item_uid: return
        
        real_idx = self.page_mapping[self.current_page_idx]
        page = self.doc_ref.load_page(real_idx)
        pdf_h = page.rect.height
        
        data = self.get_item_data_by_uid(self.selected_item_uid)
        if not data: return

        # --- MOVE LOGIC ---
        if self.interaction_mode == "MOVE":
            dx_scr = event.x - self.drag_start_x
            dy_scr = event.y - self.drag_start_y
            
            # Screen = PDF * 2 * ratio
            dx_pdf = dx_scr / (2 * self.current_preview_ratio)
            dy_pdf = - (dy_scr / (2 * self.current_preview_ratio))
            
            data['x'] = self.initial_item_vals['x'] + dx_pdf
            data['y'] = self.initial_item_vals['y'] + dy_pdf
            
            self.update_preview()

        # --- RESIZE LOGIC (RATIO BASED) ---
        elif self.interaction_mode == "RESIZE":
            cw, ch = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
            if self.tk_img:
                img_x = (cw/2) - (self.tk_img.width()/2)
                img_y = (ch/2) - (self.tk_img.height()/2)
            else: img_x, img_y = 0, 0
            
            cx_scr = img_x + (data['x'] * 2 * self.current_preview_ratio)
            cy_scr = img_y + ((pdf_h - data['y']) * 2 * self.current_preview_ratio)

            curr_dist = math.hypot(event.x - cx_scr, event.y - cy_scr)
            start_dist = self.initial_item_vals.get('dist', 1)
            ratio = curr_dist / start_dist
            
            if data['type'] == 'img':
                start_w = self.initial_item_vals['w']
                new_w = start_w * ratio
                if new_w < 10: new_w = 10
                data['w'] = new_w
            elif data['type'] == 'text':
                start_size = self.initial_item_vals['size']
                new_size = start_size * ratio
                if new_size < 5: new_size = 5
                data['size'] = int(new_size)
            elif data['type'] == 'arrow':
                start_len = self.initial_item_vals['len']
                new_len = start_len * ratio
                if new_len < 10: new_len = 10
                data['len'] = int(new_len)

            self.update_preview()

    def on_canvas_release(self, event):
        self.interaction_mode = None

    def on_right_click(self, event):
        item = self.preview_canvas.find_closest(event.x, event.y)[0]
        tags = self.preview_canvas.gettags(item)
        uid = next((t for t in tags if t.startswith("uid:")), None)
        
        if uid:
            self.selected_item_uid = uid
            self.update_preview()
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Delete Item", command=lambda: self.delete_custom_item(uid))
            menu.post(event.x_root, event.y_root)

    def delete_custom_item(self, uid):
        self.save_state()
        real_idx = self.page_mapping[self.current_page_idx]
        if real_idx in self.custom_overlays:
            self.custom_overlays[real_idx] = [x for x in self.custom_overlays[real_idx] if x['uid'] != uid]
            self.selected_item_uid = None
            self.update_preview()

    # --- CUSTOM ITEMS ADD/EDIT ---
    def add_custom_item(self):
        if not self.doc_ref: return
        dlg = CustomItemDialog(self.root)
        self.root.wait_window(dlg)
        
        if not dlg.result: return
        self.save_state()
        res = dlg.result
        
        real_idx = self.page_mapping[self.current_page_idx]
        page = self.doc_ref.load_page(real_idx)
        mid_x = page.rect.width / 2
        mid_y = page.rect.height / 2
        
        if real_idx not in self.custom_overlays: self.custom_overlays[real_idx] = []
        
        new_uid = "uid:" + secrets.token_hex(4)
        res['uid'] = new_uid
        res['x'] = mid_x
        res['y'] = mid_y
        
        self.custom_overlays[real_idx].append(res)
        self.selected_item_uid = new_uid
        self.update_preview()

    def edit_custom_item(self, event):
        if not self.selected_item_uid: return
        
        data = self.get_item_data_by_uid(self.selected_item_uid)
        if not data: return
        
        dlg = CustomItemDialog(self.root, edit_data=data)
        self.root.wait_window(dlg)
        
        if dlg.result:
            self.save_state()
            # Update dict in place
            for k, v in dlg.result.items():
                data[k] = v
            self.update_preview()

    def clear_custom_page(self):
        if not self.doc_ref: return
        if messagebox.askyesno("Clear", "Remove all custom items for THIS page?"):
            self.save_state()
            real_idx = self.page_mapping[self.current_page_idx]
            if real_idx in self.custom_overlays:
                del self.custom_overlays[real_idx]
            self.selected_item_uid = None
            self.update_preview()

    # --- EXISTING LOAD/NAVIGATE ---
    def load_pdf(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.input_file = f; self.lbl_file.config(text=os.path.basename(f))
            self.input_password = None 
            self.custom_overlays = {} 
            self.undo_stack = []
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

        margin = tab.margin_var.get()
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
                
                # --- CALCULATE EDGE COORDINATES (With Margin Logic) ---
                # Rotate dimensions
                ang_rad = math.radians(angle)
                rot_w = abs(eff_w * math.cos(ang_rad)) + abs(eff_h * math.sin(ang_rad))
                rot_h = abs(eff_w * math.sin(ang_rad)) + abs(eff_h * math.cos(ang_rad))

                # Align bounding box edge to margin
                y_T_cor = h - margin - rot_h/2
                y_B_cor = margin + rot_h/2
                
                x_L_cor = off_10_w + rot_w/2
                x_R_cor = w - off_10_w - rot_w/2
                
                x_L_side = margin + rot_w/2 
                x_R_side = w - margin - rot_w/2
                
                y_S_top = h - off_16_h
                y_S_bot = off_16_h

                if pid=="TL": cx,cy = x_L_cor, y_T_cor
                elif pid=="TC": cx,cy = xm, y_T_cor
                elif pid=="TR": cx,cy = x_R_cor, y_T_cor
                
                # --- Advanced Side Positioning (Alignment to End/Start) ---
                elif pid in ["LT", "RT"]:
                    # Align Top Edge of text box to (h - margin)
                    cy = h - margin - (rot_h / 2)
                    if pid == "LT": cx = x_L_side
                    else: cx = x_R_side

                elif pid in ["LB", "RB"]:
                    # Align Bottom Edge of text box to (margin)
                    cy = margin + (rot_h / 2)
                    if pid == "LB": cx = x_L_side
                    else: cx = x_R_side

                elif pid=="LC": cx,cy = x_L_side, ym
                elif pid=="RC": cx,cy = x_R_side, ym
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
        c.translate(w/2, h/2); c.rotate(45)
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
        self.preview_canvas.delete("all")
        self.canvas_images = [] 
        if not self.doc_ref or not self.page_mapping: return
        
        if self.current_page_idx >= len(self.page_mapping): self.current_page_idx = 0
            
        try:
            real_page_idx = self.page_mapping[self.current_page_idx]
            if real_page_idx >= self.doc_ref.page_count: return 

            page = self.doc_ref.load_page(real_page_idx)
            
            # Base PDF Render (using PyMuPDF)
            pix = page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=True)
            mode = "RGBA" if pix.alpha else "RGB"
            bg = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            if mode=="RGBA": bg = Image.alpha_composite(Image.new("RGBA", bg.size, (255,255,255,255)), bg)

            # Standard Stamp Render (ReportLab)
            pkt = self.get_combined_watermark(page.rect.width, page.rect.height)
            wm_doc = fitz.open("pdf", pkt.getvalue())
            
            if wm_doc.page_count > 0:
                wm_pix = wm_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2,2), alpha=True)
                wm_img = Image.frombytes("RGBA", [wm_pix.width, wm_pix.height], wm_pix.samples)
                if wm_img.size != bg.size: wm_img = wm_img.resize(bg.size, Image.Resampling.LANCZOS)
                final = Image.alpha_composite(bg.convert("RGBA"), wm_img)
            else:
                final = bg.convert("RGBA")
            
            # --- CUSTOM ITEMS LAYER (using PIL) ---
            overlay = Image.new("RGBA", final.size, (255,255,255,0))
            draw = ImageDraw.Draw(overlay)
            
            if real_page_idx in self.custom_overlays:
                for item in self.custom_overlays[real_page_idx]:
                    # Map PDF points -> Pixel Coordinates (Scale = 2)
                    ix = item['x'] * 2
                    iy = (page.rect.height - item['y']) * 2
                    
                    if item['type'] == 'text':
                        try:
                            f_size = int(item['size'] * 2) 
                            font_path = SYSTEM_FONT_MAP.get(item['font'], "arial.ttf")
                            if not os.path.exists(font_path): font = ImageFont.load_default()
                            else: font = ImageFont.truetype(font_path, f_size)
                        except: font = ImageFont.load_default()
                        
                        # New Tight Bounding Box Logic
                        bbox = font.getbbox(item['content']) # (left, top, right, bottom)
                        # Text width and height
                        t_w = bbox[2] - bbox[0]
                        t_h = bbox[3] - bbox[1]
                        
                        # Add a larger padding for safety (e.g. Italics)
                        pad = 30
                        img_w = t_w + pad
                        img_h = t_h + pad
                        
                        txt_img = Image.new("RGBA", (int(img_w), int(img_h)), (0,0,0,0))
                        d = ImageDraw.Draw(txt_img)
                        
                        # Draw centered
                        d.text((img_w/2, img_h/2), item['content'], font=font, fill=item['color'], anchor="mm")
                        
                        # Rotate with expand=True to calculate correct selection box size
                        txt_rot = txt_img.rotate(item['angle'], resample=Image.BICUBIC, expand=True)
                        
                        # Opacity
                        if item['opacity'] < 1.0:
                            alpha = txt_rot.split()[3]
                            alpha = alpha.point(lambda p: p * item['opacity'])
                            txt_rot.putalpha(alpha)
                            
                        # Paste (Center stays at ix, iy)
                        overlay.alpha_composite(txt_rot, dest=(int(ix - txt_rot.width/2), int(iy - txt_rot.height/2)))
                        item['disp_w'] = txt_rot.width / 4; item['disp_h'] = txt_rot.height / 4
                        
                    elif item['type'] == 'arrow':
                        l = item['len'] * 2
                        
                        # Create arrow on explicit right-pointing shaft
                        # Shaft from Center-L/2 to Center+L/2
                        # Then we rotate the whole image
                        arr_img = Image.new("RGBA", (int(l+100), int(l+100)), (0,0,0,0))
                        d = ImageDraw.Draw(arr_img)
                        cx, cy = arr_img.width/2, arr_img.height/2
                        
                        base_col = COLOR_TO_HEX.get(item['color_name'], "#FF0000")
                        if base_col.startswith('#'): rgb = tuple(int(base_col[i:i+2], 16) for i in (1, 3, 5))
                        else: rgb=(255,0,0)
                        col = rgb + (int(255*item['opacity']),)
                        
                        # Shaft (Left to Right)
                        start_x = cx - l/2
                        end_x = cx + l/2
                        
                        # Shaft: stop at end_x - head_len
                        head_len = 30 # Scaled
                        d.line([(start_x, cy), (end_x - head_len + 5, cy)], fill=col, width=10)
                        
                        # Head (Triangle at Right End)
                        tip = (end_x, cy)
                        top = (end_x - head_len, cy - 15)
                        bot = (end_x - head_len, cy + 15)
                        d.polygon([tip, top, bot], fill=col)
                        
                        # Rotate the entire arrow image
                        arr_rot = arr_img.rotate(item['angle'], resample=Image.BICUBIC)
                        overlay.alpha_composite(arr_rot, dest=(int(ix - arr_rot.width/2), int(iy - arr_rot.height/2)))
                        item['disp_w'] = arr_rot.width/4; item['disp_h'] = arr_rot.height/4

                    elif item['type'] == 'img':
                        if os.path.exists(item['path']):
                            try:
                                im_src = Image.open(item['path']).convert("RGBA")
                                w_t = item['w'] * 2
                                asp = im_src.height / im_src.width
                                h_t = w_t * asp
                                im_res = im_src.resize((int(w_t), int(h_t)), Image.Resampling.LANCZOS)
                                if item['opacity'] < 1.0:
                                    alpha = im_res.split()[3]
                                    alpha = alpha.point(lambda p: p * item['opacity'])
                                    im_res.putalpha(alpha)
                                overlay.alpha_composite(im_res, dest=(int(ix-w_t/2), int(iy-h_t/2)))
                                item['disp_w'] = w_t/4; item['disp_h'] = h_t/4
                            except: pass

            final = Image.alpha_composite(final, overlay)
            cw, ch = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
            if cw < 10: cw, ch = 800, 600 
            iw, ih = final.size
            ratio = min(cw/iw, ch/ih)
            self.current_preview_ratio = ratio 
            
            new_w, new_h = int(iw*ratio*0.95), int(ih*ratio*0.95)
            final = final.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(final)
            
            cx, cy = cw/2, ch/2
            self.preview_canvas.create_image(cx, cy, image=self.tk_img, anchor=tk.CENTER)
            
            img_x = cx - new_w/2; img_y = cy - new_h/2
            if real_page_idx in self.custom_overlays:
                for item in self.custom_overlays[real_page_idx]:
                    sx = img_x + (item['x'] * 2 * ratio)
                    sy = img_y + ((page.rect.height - item['y']) * 2 * ratio)
                    dw = item.get('disp_w', 20) * ratio * 2
                    dh = item.get('disp_h', 20) * ratio * 2
                    self.preview_canvas.create_rectangle(sx-dw, sy-dh, sx+dw, sy+dh, fill="", outline="", tags=("item", item['uid']))
                    if item['uid'] == self.selected_item_uid:
                        self.preview_canvas.create_rectangle(sx-dw-5, sy-dh-5, sx+dw+5, sy+dh+5, outline="red", width=2, dash=(4,4))
                        self.preview_canvas.create_rectangle(sx+dw, sy+dh, sx+dw+10, sy+dh+10, fill="red", tags=("resize_handle", item['uid']))

            # Update Page Label
            self.lbl_page.config(text=f"{self.current_page_idx + 1} / {len(self.page_mapping)}")

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
            self.root.geometry(d.get("win", "960x1152"))
            self.compress_var.set(d.get("comp", False))
            self.tab1.load_settings_dict(d.get("t1"))
            self.tab2.load_settings_dict(d.get("t2"))
            self.tab3.load_settings_dict(d.get("t3"))
            print("[INFO] Settings Loaded.")
        except: pass

    def reload_settings_action(self):
        self.load_settings(); self.update_preview()

    def on_close(self):
        self.save_settings()
        self.root.destroy()

    def generate_random_password(self):
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for i in range(12))

    def initiate_save(self):
        if not self.input_file: return
        dlg = SecurityDialog(self.root)
        self.root.wait_window(dlg)
        if dlg.result is None: return 
        self.save_pdf(dlg.result)

    def save_pdf(self, options):
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out: return
        
        user_password = None; owner_password = None
        
        if options["encrypt"]:
            if options["pass_mode"] == "Manual":
                user_password = options["manual_user"]
                if options["manual_owner"].strip(): owner_password = options["manual_owner"]
                else: owner_password = self.generate_random_password()
            else: 
                user_password = self.generate_random_password()
                owner_password = self.generate_random_password()
            
            try:
                with open(out + ".pass", "w") as f:
                    f.write(f"User Password: {user_password}\n")
                    f.write(f"Owner Password: {owner_password}\n")
            except: pass

        is_overwrite = (os.path.abspath(out) == os.path.abspath(self.input_file))
        try:
            if is_overwrite: self.doc_ref.close()

            with open(self.input_file, "rb") as f: input_stream = io.BytesIO(f.read())
            r = PdfReader(input_stream)
            if r.is_encrypted and self.input_password: r.decrypt(self.input_password)
                
            w = PdfWriter()
            
            for real_idx in self.page_mapping:
                if real_idx < len(r.pages):
                    p = r.pages[real_idx]
                    try: p.transfer_rotation_to_content()
                    except: pass
                    
                    w_pt = float(p.mediabox.width)
                    h_pt = float(p.mediabox.height)
                    
                    # 1. Standard Stamps
                    pkt = self.get_combined_watermark(w_pt, h_pt)
                    wm_reader = PdfReader(pkt)
                    if len(wm_reader.pages) > 0: p.merge_page(wm_reader.pages[0])
                    
                    # 2. Custom Items (New Logic)
                    if real_idx in self.custom_overlays:
                        cust_pkt = io.BytesIO()
                        c = canvas.Canvas(cust_pkt, pagesize=(w_pt, h_pt))
                        
                        for item in self.custom_overlays[real_idx]:
                            c.saveState()
                            c.translate(item['x'], item['y'])
                            
                            if item['type'] == 'text':
                                c.rotate(item['angle'])
                                c.setFillAlpha(item['opacity'])
                                f_name = item.get('font', 'Helvetica')
                                # Ensure font registered logic
                                if f_name in REGISTERED_FONTS: c.setFont(f_name, item['size'])
                                else: c.setFont("Helvetica", item['size'])
                                
                                c.setFillColor(HexColor(item['color']))
                                offset_y = -(item['size'] * 0.35)
                                c.drawCentredString(0, offset_y, item['content'])
                                
                            elif item['type'] == 'arrow':
                                c.rotate(item['angle'])
                                col_hex = COLOR_TO_HEX.get(item['color_name'], "#FF0000")
                                c.setStrokeColor(HexColor(col_hex), alpha=item['opacity'])
                                c.setLineWidth(5)
                                # FIXED: Shaft stops at tip base
                                L = item['len']
                                head_len = 15 # PDF units
                                c.line(-L/2, 0, L/2 - head_len + 2, 0)
                                # Head
                                c.setFillColor(HexColor(col_hex), alpha=item['opacity'])
                                p_h = c.beginPath()
                                p_h.moveTo(L/2, 0)
                                p_h.lineTo(L/2 - head_len, 7)
                                p_h.lineTo(L/2 - head_len, -7)
                                p_h.close()
                                c.drawPath(p_h, fill=1, stroke=0)
                                
                            elif item['type'] == 'img':
                                if os.path.exists(item['path']):
                                    try:
                                        ir = ImageReader(item['path'])
                                        iw, ih = ir.getSize()
                                        asp = ih / iw
                                        c.drawImage(ir, -item['w']/2, -item['w']*asp/2, item['w'], item['w']*asp, mask='auto')
                                    except: pass
                            
                            c.restoreState()
                        
                        c.save()
                        cust_pkt.seek(0)
                        cust_reader = PdfReader(cust_pkt)
                        if len(cust_reader.pages)>0: p.merge_page(cust_reader.pages[0])

                    # 3. Tiled
                    tiled_text = options["tiled_text"]
                    if tiled_text.strip():
                        overlay_pkt = self.get_overlay_watermark(tiled_text, w_pt, h_pt)
                        overlay_reader = PdfReader(overlay_pkt)
                        if len(overlay_reader.pages) > 0: p.merge_page(overlay_reader.pages[0]) 

                    w.add_page(p)
            
            if user_password:
                perms = UserAccessPermissions(0) 
                if options["allow_print"]: perms |= UserAccessPermissions.PRINT
                if options["allow_copy"]: perms |= UserAccessPermissions.EXTRACT
                w.encrypt(user_password=user_password, owner_password=owner_password, permissions_flag=perms, algorithm="AES-128")

            with open(out, "wb") as f_out: w.write(f_out)
            
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
            if self.open_file_var.get() and os.name == 'nt': os.startfile(out)
        
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
