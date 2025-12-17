# --------------------------------------------------------------------------------
# Script Name: pdf_watermark_gui_v29.py
# Author:      Gemini (Assistant)
# Created:     2025-12-17
#
# DESCRIPTION:
#   A professional GUI tool to batch watermark/stamp PDF files with support for
#   multiple independent layers, images, and advanced positioning.
#   Designed for Windows environments with auto-dependency installation.
#
# ==============================================================================
# FULL APPLICATION SPECIFICATIONS:
# ==============================================================================
# 1. SYSTEM & DEPLOYMENT
#    - Auto-installs missing modules (pymupdf, pypdf, reportlab, pillow).
#    - Supports HTTP Proxy for pip installation via --proxy argument.
#    - Built-in "Build Mode" to generate standalone .exe using PyInstaller.
#    - **Settings Persistence**: Saves/Loads 'settings.json' on Exit/Start.
#
# 2. INPUT / OUTPUT
#    - Input: Select single PDF file via system dialog.
#    - Output: Save as new file (does not overwrite unless confirmed).
#    - Preview: Real-time visual preview with Page Navigation (Prev/Next).
#
# 3. MULTI-LAYER LOGIC (3 Tabs)
#    - Three independent stamp sets (Set 1, Set 2, Set 3).
#    - Master "Enable" switch for each set.
#    - PRIORITY & COLLISION: Set 1 > Set 2 > Set 3. If a higher priority set
#      occupies a position (e.g., Top-Left), lower sets cannot stamp there.
#
# 4. CONTENT MODES
#    - Mode A: TEXT
#        * Up to 3 lines of text per stamp.
#        * Individual Font Size per line.
#        * Individual Alignment per line (Left, Center, Right).
#        * Default L1: "FETL" (Align Left, Size 20).
#        * Default L2: "Confidential"/"Copy"/"Draft" (Align Center, Size 40).
#        * Default L3: Empty (Align Center, Size 20).
#    - Mode B: IMAGE (Logo)
#        * Supports PNG images.
#        * If an image is loaded, it overrides the Text content for that tab.
#        * Auto-scales to fit within the Size Constraints while keeping aspect ratio.
#
# 5. SIZE CONSTRAINTS & SCALING
#    - Center Position (C): Max Box 300x200 px.
#    - All Other Positions: Max Box 200x60 px.
#    - Content (Text or Image) is automatically scaled down if it exceeds these limits.
#
# 6. POSITIONING LOGIC
#    - Visual 5-row grid selection.
#    - Corners (TL, TR, BL, BR): Offset 10% from X edge, 20px from Y edge.
#    - Side-Verticals (LT, RT, LB, RB): Offset 16% from Y edge, 20px from X edge.
#    - Centers (TC, BC, LC, RC, C): Standard center alignment logic.
#
# 7. VISUAL STYLING
#    - Fonts: Standard (Helvetica/Times/Courier) + Auto-detected Unicode (Thai/JP/CN).
#    - Color: RGB Manual Input or Quick Presets (Red/Green/Blue).
#    - Opacity: 0% to 100% slider.
#    - Borders: Toggleable box with styles (Solid, Dashed, Dotted).
#    - Vertical Alignment: Text is optically centered vertically (0.95 baseline offset).
#
# 8. HELP & LOCALIZATION
#    - Help Message in English, Thai, and Japanese.
# ==============================================================================
#
# USAGE:
#   Run GUI:       python pdf_watermark_gui_v29.py
#   Build EXE:     python pdf_watermark_gui_v29.py --build
#   With Proxy:    python pdf_watermark_gui_v29.py --proxy http://user:pass@host:port
# --------------------------------------------------------------------------------

import sys
import subprocess
import os
import importlib
import io
import json

# --- 0. Parse Proxy ---
PROXY_URL = None
if "--proxy" in sys.argv:
    try:
        p_idx = sys.argv.index("--proxy")
        if p_idx + 1 < len(sys.argv): PROXY_URL = sys.argv[p_idx + 1]
    except: pass

# --- 1. Auto-Installation ---
def install_and_import(package_name, import_name=None, proxy=None):
    if import_name is None: import_name = package_name
    try:
        importlib.import_module(import_name)
    except ImportError:
        print(f"[INFO] Installing '{package_name}'...")
        try:
            cmd = [sys.executable, "-m", "pip", "install", package_name]
            if proxy: cmd.extend(["--proxy", proxy])
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError: sys.exit(1)

# --- 2. Dependencies ---
install_and_import("pymupdf", "fitz", PROXY_URL)
install_and_import("pypdf", proxy=PROXY_URL)
install_and_import("reportlab", proxy=PROXY_URL)
install_and_import("Pillow", "PIL", PROXY_URL)

# --- 3. Imports ---
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import fitz
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# --- 4. Fonts ---
REGISTERED_FONTS = []
def register_fonts():
    dirs = [r"C:\Windows\Fonts", r"C:\WINNT\Fonts", "/usr/share/fonts", "/Library/Fonts"]
    cands = [("Tahoma",["tahoma.ttf"]), ("Thai-Angsana",["angsa.ttc","angsana.ttc"]), ("JP-MSGothic",["msgothic.ttc"]), ("CN-SimHei",["simhei.ttf"]), ("Arial-Unicode",["arialuni.ttf"])]
    for name, fnames in cands:
        for d in dirs:
            for fn in fnames:
                fp = os.path.join(d, fn)
                if os.path.exists(fp):
                    try: pdfmetrics.registerFont(TTFont(name, fp)); REGISTERED_FONTS.append(name); break
                    except: pass
            if name in REGISTERED_FONTS: break
register_fonts()

# --- 5. Build ---
def build_executable():
    install_and_import("pyinstaller", "PyInstaller", PROXY_URL)
    script_name = os.path.basename(__file__)
    exe_name = "FETL_PDF_Stamp_Tools"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed", "--name", exe_name, "--hidden-import", "pypdf", "--hidden-import", "reportlab", "--hidden-import", "fitz", "--hidden-import", "PIL", "--hidden-import", "tkinter", script_name]
    try: subprocess.check_call(cmd); print(f"[SUCCESS] Built {exe_name}")
    except: print("[ERROR] Build failed")

# --- 6. Stamp Tab Class ---
class StampTab(ttk.Frame):
    def __init__(self, parent, update_callback, text_l1="FETL", text_l2="Confidential", default_enabled=False):
        super().__init__(parent)
        self.update_callback = update_callback
        
        # --- Variables ---
        self.enabled = tk.BooleanVar(value=default_enabled)
        self.image_path = tk.StringVar(value="")
        
        # Text Lines & Default Sizes
        self.txt_1 = tk.StringVar(value=text_l1); self.sz_1 = tk.IntVar(value=20)
        self.txt_2 = tk.StringVar(value=text_l2); self.sz_2 = tk.IntVar(value=40)
        self.txt_3 = tk.StringVar(value="");      self.sz_3 = tk.IntVar(value=20)
        
        # Per-Line Alignment
        self.align_1 = tk.StringVar(value="Left")   
        self.align_2 = tk.StringVar(value="Center")
        self.align_3 = tk.StringVar(value="Center")
        
        self.fam = tk.StringVar(value="Helvetica")
        self.sty = tk.StringVar(value="Regular")
        self.opac = tk.IntVar(value=50)
        self.border = tk.BooleanVar(value=True)
        self.border_style = tk.StringVar(value="Solid") 
        
        self.col_r = tk.IntVar(value=255)
        self.col_g = tk.IntVar(value=0)
        self.col_b = tk.IntVar(value=0)
        self.col_hex = "#FF0000"

        # Position Map
        self.pos_vars = {}
        self.rot_vars = {}
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
        # Enable Switch
        top_f = ttk.Frame(self, padding=5); top_f.pack(fill=tk.X)
        ttk.Checkbutton(top_f, text="Enable this Stamp Set", variable=self.enabled, command=self.update_callback).pack(anchor="w")
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=2)

        # 1. Image / Logo Section
        img_grp = ttk.LabelFrame(self, text="Image / Logo (Overrides Text)", padding=5)
        img_grp.pack(fill=tk.X, padx=5, pady=2)
        
        img_row = ttk.Frame(img_grp); img_row.pack(fill=tk.X)
        ttk.Button(img_row, text="Select PNG", command=self.select_image).pack(side=tk.LEFT)
        ttk.Button(img_row, text="Clear", command=self.clear_image).pack(side=tk.LEFT, padx=5)
        self.lbl_img_path = ttk.Label(img_row, text="No image selected", foreground="gray")
        self.lbl_img_path.pack(side=tk.LEFT, padx=5)

        # 2. Text Section
        t_grp = ttk.LabelFrame(self, text="Text Configuration", padding=5)
        t_grp.pack(fill=tk.X, padx=5, pady=2)
        
        tg = ttk.Frame(t_grp); tg.pack(fill=tk.X)
        ttk.Label(tg, text="Text Content").grid(row=0, column=0, sticky="w")
        ttk.Label(tg, text="Size").grid(row=0, column=1, padx=2, sticky="w")
        ttk.Label(tg, text="Align").grid(row=0, column=2, padx=2, sticky="w")
        
        rows_data = [(self.txt_1, self.sz_1, self.align_1), (self.txt_2, self.sz_2, self.align_2), (self.txt_3, self.sz_3, self.align_3)]
        for i, (tv, sv, av) in enumerate(rows_data):
            r = i+1
            ttk.Entry(tg, textvariable=tv).grid(row=r, column=0, sticky="ew", pady=2)
            ttk.Spinbox(tg, from_=1, to=200, textvariable=sv, width=4, command=self.update_callback).grid(row=r, column=1, padx=2)
            cb_al = ttk.Combobox(tg, textvariable=av, values=("Left", "Center", "Right"), state="readonly", width=7)
            cb_al.grid(row=r, column=2, padx=2); cb_al.bind("<<ComboboxSelected>>", lambda e: self.update_callback())
        tg.columnconfigure(0, weight=1)

        fs_row = ttk.Frame(t_grp); fs_row.pack(fill=tk.X, pady=5)
        fams = ['Helvetica', 'Times-Roman', 'Courier'] + REGISTERED_FONTS
        cb_f = ttk.Combobox(fs_row, textvariable=self.fam, values=fams, state="readonly", width=15)
        cb_f.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5)); cb_f.bind("<<ComboboxSelected>>", lambda e: self.update_callback())
        cb_s = ttk.Combobox(fs_row, textvariable=self.sty, values=('Regular', 'Bold', 'Italic', 'BoldItalic'), state="readonly", width=10)
        cb_s.pack(side=tk.LEFT); cb_s.bind("<<ComboboxSelected>>", lambda e: self.update_callback())

        # 3. Color & Style
        c_grp = ttk.LabelFrame(self, text="Appearance", padding=5)
        c_grp.pack(fill=tk.X, padx=5, pady=2)
        
        btn_row = ttk.Frame(c_grp); btn_row.pack(fill=tk.X)
        for t, c in [("Red","#FF0000"), ("Green","#008000"), ("Blue","#0000FF")]:
            ttk.Button(btn_row, text=t, command=lambda x=c: self.set_hex(x)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
            
        rgb_row = ttk.Frame(c_grp); rgb_row.pack(fill=tk.X, pady=2)
        for l, v in [("R", self.col_r), ("G", self.col_g), ("B", self.col_b)]:
            ttk.Label(rgb_row, text=l).pack(side=tk.LEFT)
            ttk.Entry(rgb_row, textvariable=v, width=3).pack(side=tk.LEFT, padx=(0,3))
        ttk.Button(rgb_row, text="Set", width=4, command=self.apply_rgb).pack(side=tk.LEFT)
        self.lbl_sw = tk.Label(rgb_row, width=4, bg=self.col_hex, relief="sunken"); self.lbl_sw.pack(side=tk.RIGHT)
        
        o_row = ttk.Frame(c_grp); o_row.pack(fill=tk.X)
        ttk.Label(o_row, text="Opac%").pack(side=tk.LEFT)
        ttk.Spinbox(o_row, from_=0, to=100, textvariable=self.opac, width=4, command=self.update_callback).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(o_row, text="Border", variable=self.border, command=self.update_callback).pack(side=tk.LEFT, padx=5)
        style_cb = ttk.Combobox(o_row, textvariable=self.border_style, values=("Solid", "Dashed", "Dotted"), state="readonly", width=7)
        style_cb.pack(side=tk.LEFT); style_cb.bind("<<ComboboxSelected>>", lambda e: self.update_callback())

        # 4. Positions
        p_grp = ttk.LabelFrame(self, text="Positions", padding=5)
        p_grp.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        ttk.Button(p_grp, text="Clear", command=self.clear_pos).pack(anchor="e")
        grid_f = ttk.Frame(p_grp); grid_f.pack(expand=True)
        rot_opts = ("0", "45", "90", "180", "270")
        for pid, (lbl, _, r, c) in self.pos_map.items():
            cell = ttk.Frame(grid_f, borderwidth=1, relief="groove")
            cell.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
            ttk.Checkbutton(cell, text=lbl, variable=self.pos_vars[pid], command=self.update_callback).pack()
            cmb = ttk.Combobox(cell, textvariable=self.rot_vars[pid], values=rot_opts, width=3, state="readonly")
            cmb.pack(); cmb.bind("<<ComboboxSelected>>", lambda e: self.update_callback())

    def select_image(self):
        f = filedialog.askopenfilename(filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")])
        if f:
            self.image_path.set(f)
            self.lbl_img_path.config(text=os.path.basename(f), foreground="black")
            self.update_callback()

    def clear_image(self):
        self.image_path.set("")
        self.lbl_img_path.config(text="No image selected", foreground="gray")
        self.update_callback()

    def set_hex(self, h): self.col_hex=h; self.lbl_sw.config(bg=h); self.update_callback()
    def apply_rgb(self):
        try: r,g,b = self.col_r.get(), self.col_g.get(), self.col_b.get(); self.col_hex=f"#{r:02x}{g:02x}{b:02x}"; self.lbl_sw.config(bg=self.col_hex); self.update_callback()
        except: pass
    def clear_pos(self):
        for v in self.pos_vars.values(): v.set(False)
        self.update_callback()
    
    # --- Serialization for Settings ---
    def get_settings_dict(self):
        # Extract all state to a dict
        pos_data = {k: {"en": v.get(), "rot": self.rot_vars[k].get()} for k, v in self.pos_vars.items()}
        return {
            "enabled": self.enabled.get(),
            "image_path": self.image_path.get(),
            "txt_1": self.txt_1.get(), "sz_1": self.sz_1.get(), "align_1": self.align_1.get(),
            "txt_2": self.txt_2.get(), "sz_2": self.sz_2.get(), "align_2": self.align_2.get(),
            "txt_3": self.txt_3.get(), "sz_3": self.sz_3.get(), "align_3": self.align_3.get(),
            "fam": self.fam.get(), "sty": self.sty.get(),
            "opac": self.opac.get(), "border": self.border.get(), "border_style": self.border_style.get(),
            "col_hex": self.col_hex,
            "positions": pos_data
        }

    def load_settings_dict(self, data):
        # Restore state from dict
        if not data: return
        try:
            self.enabled.set(data.get("enabled", False))
            self.image_path.set(data.get("image_path", ""))
            if self.image_path.get(): self.lbl_img_path.config(text=os.path.basename(self.image_path.get()), foreground="black")
            
            self.txt_1.set(data.get("txt_1", "")); self.sz_1.set(data.get("sz_1", 20)); self.align_1.set(data.get("align_1", "Left"))
            self.txt_2.set(data.get("txt_2", "")); self.sz_2.set(data.get("sz_2", 40)); self.align_2.set(data.get("align_2", "Center"))
            self.txt_3.set(data.get("txt_3", "")); self.sz_3.set(data.get("sz_3", 20)); self.align_3.set(data.get("align_3", "Center"))
            
            self.fam.set(data.get("fam", "Helvetica"))
            self.sty.set(data.get("sty", "Regular"))
            self.opac.set(data.get("opac", 50))
            self.border.set(data.get("border", True))
            self.border_style.set(data.get("border_style", "Solid"))
            
            self.set_hex(data.get("col_hex", "#FF0000"))
            
            p_data = data.get("positions", {})
            for k, v in p_data.items():
                if k in self.pos_vars:
                    self.pos_vars[k].set(v.get("en", False))
                    self.rot_vars[k].set(v.get("rot", "0"))
        except Exception as e: print(f"Load Tab Error: {e}")

# --- 7. Main Application ---
class PDFWatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Stamp & Watermark Tools")
        self.root.geometry("1450x980")
        self.input_file = None; self.doc_ref = None
        self.current_page_idx = 0; self.total_pages = 0; self.tk_img = None
        
        self._setup_ui()
        self.load_settings() # Auto-load on start
        self.root.protocol("WM_DELETE_WINDOW", self.on_close) # Auto-save on exit
        self.preview_canvas.bind("<Configure>", self.on_canvas_resize)

    def _setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(main_paned, width=650, padding=5)
        right = ttk.Frame(main_paned, padding=5)
        main_paned.add(left, weight=0); main_paned.add(right, weight=1)

        f_frame = ttk.Frame(left); f_frame.pack(fill=tk.X, pady=5)
        ttk.Button(f_frame, text="Help / Instructions (English/Thai/Japanese)", command=self.show_help).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(f_frame, text="1. Load PDF File", command=self.load_pdf).pack(fill=tk.X)
        self.lbl_file = ttk.Label(f_frame, text="No file loaded", foreground="gray"); self.lbl_file.pack(fill=tk.X)

        self.nb = ttk.Notebook(left)
        self.nb.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.tab1 = StampTab(self.nb, self.update_preview, text_l1="FETL", text_l2="Confidential", default_enabled=True)
        self.tab2 = StampTab(self.nb, self.update_preview, text_l1="FETL", text_l2="Copy", default_enabled=False)
        self.tab3 = StampTab(self.nb, self.update_preview, text_l1="FETL", text_l2="Draft", default_enabled=False)
        
        self.nb.add(self.tab1, text=" Stamp Set 1 ")
        self.nb.add(self.tab2, text=" Stamp Set 2 ")
        self.nb.add(self.tab3, text=" Stamp Set 3 ")

        act_grp = ttk.LabelFrame(left, text="Actions", padding=5)
        act_grp.pack(fill=tk.X, pady=5)
        ttk.Button(act_grp, text="Refresh Preview", command=self.update_preview).pack(fill=tk.X, pady=2)
        ttk.Button(act_grp, text="Save Settings", command=self.save_settings).pack(fill=tk.X, pady=2)
        ttk.Button(act_grp, text="SAVE PDF", command=self.save_pdf).pack(fill=tk.X, pady=5)

        self.canvas_frame = tk.Frame(right, bg="#404040")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas = tk.Canvas(self.canvas_frame, bg="#404040", highlightthickness=0)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        nav = ttk.Frame(right); nav.pack(fill=tk.X, pady=5)
        ttk.Button(nav, text="< Prev", command=self.prev_page).pack(side=tk.LEFT)
        self.lbl_page = ttk.Label(nav, text="0 / 0"); self.lbl_page.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav, text="Next >", command=self.next_page).pack(side=tk.LEFT)

    def show_help(self):
        msg = (
            "FETL PDF Stamp & Watermark Tools\n"
            "=========================================\n"
            "[ENGLISH]\n"
            "1. Click 'Load PDF File' to open a document.\n"
            "2. Configure up to 3 stamp layers in the tabs.\n"
            "3. Settings are Auto-Saved on exit.\n"
            "4. Click 'SAVE PDF' to process.\n\n"
            "[THAI - ภาษาไทย]\n"
            "1. คลิก 'Load PDF File' เพื่อเปิดไฟล์\n"
            "2. ตั้งค่าตรายางได้สูงสุด 3 ชั้นในแท็บต่างๆ\n"
            "3. การตั้งค่าจะถูกบันทึกอัตโนมัติเมื่อปิดโปรแกรม\n"
            "4. คลิก 'SAVE PDF' เพื่อบันทึกไฟล์\n\n"
            "[JAPANESE - 日本語]\n"
            "1. 「Load PDF File」をクリックしてファイルを開きます。\n"
            "2. タブで最大3つのスタンプレイヤーを設定できます。\n"
            "3. 設定は終了時に自動的に保存されます。\n"
            "4. 「SAVE PDF」をクリックして保存します。"
        )
        messagebox.showinfo("Help / Instructions", msg)

    # --- Settings persistence ---
    def save_settings(self):
        data = {
            "tab1": self.tab1.get_settings_dict(),
            "tab2": self.tab2.get_settings_dict(),
            "tab3": self.tab3.get_settings_dict(),
            "win_geo": self.root.geometry()
        }
        try:
            with open("settings.json", "w") as f:
                json.dump(data, f, indent=4)
            print("[INFO] Settings Saved.")
        except Exception as e:
            print(f"[ERR] Save Settings Failed: {e}")

    def load_settings(self):
        if not os.path.exists("settings.json"): return
        try:
            with open("settings.json", "r") as f:
                data = json.load(f)
            
            if "win_geo" in data: self.root.geometry(data["win_geo"])
            if "tab1" in data: self.tab1.load_settings_dict(data["tab1"])
            if "tab2" in data: self.tab2.load_settings_dict(data["tab2"])
            if "tab3" in data: self.tab3.load_settings_dict(data["tab3"])
            print("[INFO] Settings Loaded.")
            self.update_preview()
        except Exception as e:
            print(f"[ERR] Load Settings Failed: {e}")

    def on_close(self):
        self.save_settings()
        self.root.destroy()

    # --- Core Logic (Same as v27) ---
    def load_pdf(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.input_file = f; self.lbl_file.config(text=os.path.basename(f))
            try: self.doc_ref = fitz.open(f); self.total_pages = self.doc_ref.page_count; self.current_page_idx = 0; self.update_preview()
            except Exception as e: messagebox.showerror("Error", str(e))

    def prev_page(self):
        if self.doc_ref and self.current_page_idx > 0: self.current_page_idx -= 1; self.update_preview()
    def next_page(self):
        if self.doc_ref and self.current_page_idx < self.total_pages - 1: self.current_page_idx += 1; self.update_preview()

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
            lines = [(tab.txt_1.get(), tab.sz_1.get(), tab.align_1.get()),
                     (tab.txt_2.get(), tab.sz_2.get(), tab.align_2.get()),
                     (tab.txt_3.get(), tab.sz_3.get(), tab.align_3.get())]
            lines = [(t, s, a) for t, s, a in lines if t.strip()]
            if not lines: return
            
            font_name = self.get_font_name(tab.fam.get(), tab.sty.get())
            pad = 10
            max_w, total_h, line_dims = 0, 0, []
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
                    c.setFillAlpha(opac)
                    c.drawImage(img_reader, -nat_w/2, -nat_h/2, nat_w, nat_h, mask='auto')
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
        used_positions = set()
        for tab in [self.tab1, self.tab2, self.tab3]:
            if tab.enabled.get():
                self.draw_stamp_layer(c, tab, w, h, used_positions)
        c.save()
        packet.seek(0)
        return packet

    def on_canvas_resize(self, event):
        if self.doc_ref: self.update_preview()

    def update_preview(self):
        if not self.doc_ref: return
        try:
            page = self.doc_ref.load_page(self.current_page_idx)
            pix = page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=True)
            mode = "RGBA" if pix.alpha else "RGB"
            bg = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            if mode=="RGBA": bg = Image.alpha_composite(Image.new("RGBA", bg.size, (255,255,255,255)), bg)

            pkt = self.get_combined_watermark(page.rect.width, page.rect.height)
            wm_pix = fitz.open("pdf", pkt).load_page(0).get_pixmap(matrix=fitz.Matrix(2,2), alpha=True)
            wm_img = Image.frombytes("RGBA", [wm_pix.width, wm_pix.height], wm_pix.samples)
            
            final = Image.alpha_composite(bg.convert("RGBA"), wm_img)
            cw, ch = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
            if cw<10: cw,ch=800,600
            iw, ih = final.size
            ratio = min(cw/iw, ch/ih)
            final = final.resize((int(iw*ratio*0.95), int(ih*ratio*0.95)), Image.Resampling.LANCZOS)
            
            self.tk_img = ImageTk.PhotoImage(final)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(cw/2, ch/2, image=self.tk_img, anchor=tk.CENTER)
            self.lbl_page.config(text=f"{self.current_page_idx+1} / {self.total_pages}")
        except Exception as e: print(e)

    def save_pdf(self):
        if not self.input_file: return
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out: return
        try:
            r = PdfReader(self.input_file); w = PdfWriter()
            for p in r.pages:
                pkt = self.get_combined_watermark(float(p.mediabox.width), float(p.mediabox.height))
                p.merge_page(PdfReader(pkt).pages[0])
                w.add_page(p)
            with open(out, "wb") as f: w.write(f)
            messagebox.showinfo("Done", f"Saved: {out}"); os.startfile(out) if os.name=='nt' else None
        except Exception as e: messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--build": build_executable()
    else:
        root = tk.Tk()
        try: from ctypes import windll; windll.shcore.SetProcessDpiAwareness(1)
        except: pass
        PDFWatermarkApp(root); root.mainloop()
