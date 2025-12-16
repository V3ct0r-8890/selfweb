# --------------------------------------------------------------------------------
# Script Name: pdf_watermark_gui_v16.py
# Description: v16 - FIXED BUILD ERROR (FileNotFoundError).
#              - Uses 'python -m PyInstaller' instead of relying on PATH.
#              - Retains v15 features (16% balance, Unicode fonts, clean UI).
# Author:      Gemini (Assistant)
# Created:     2025-12-17
#
# USAGE:
#   1. To Run GUI:    python pdf_watermark_gui_v16.py
#   2. To Build EXE:  python pdf_watermark_gui_v16.py --build
# --------------------------------------------------------------------------------

import sys
import subprocess
import os
import importlib
import io
import math

# --- 1. Auto-Installation Function ---
def install_and_import(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        importlib.import_module(import_name)
    except ImportError:
        print(f"[INFO] Module '{import_name}' not found. Installing '{package_name}'...")
        try:
            # Use sys.executable to ensure we install to the running python environment
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"[SUCCESS] Installed {package_name}")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to install {package_name}. Error: {e}")
            sys.exit(1)

# --- 2. Dependency Check ---
print("[INIT] Checking dependencies...")
install_and_import("pymupdf", "fitz")
install_and_import("pypdf")
install_and_import("reportlab")
install_and_import("Pillow", "PIL")

# --- 3. Imports ---
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
from PIL import Image, ImageTk
import fitz
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- 4. Font Registration Logic (Unicode Support) ---
REGISTERED_FONTS = []

def register_fonts():
    """Attempts to register common Windows fonts for Asian languages."""
    font_dirs = [r"C:\Windows\Fonts", r"C:\WINNT\Fonts", "/usr/share/fonts", "/Library/Fonts"]
    
    font_candidates = [
        ("Tahoma", ["tahoma.ttf"]),
        ("Thai-Angsana", ["angsa.ttc", "angsana.ttc", "angsa.ttf"]),
        ("Thai-Leelawadee", ["leelawad.ttf"]),
        ("JP-MSGothic", ["msgothic.ttc", "msgothic.ttf"]),
        ("CN-SimHei", ["simhei.ttf"]),
        ("Arial-Unicode", ["arialuni.ttf"])
    ]

    for font_name, filenames in font_candidates:
        found = False
        for d in font_dirs:
            if found: break
            for fname in filenames:
                full_path = os.path.join(d, fname)
                if os.path.exists(full_path):
                    try:
                        pdfmetrics.registerFont(TTFont(font_name, full_path))
                        REGISTERED_FONTS.append(font_name)
                        print(f"[INFO] Registered font: {font_name}")
                        found = True
                        break
                    except Exception as e:
                        pass 

register_fonts()

# --- 5. Build Function (PyInstaller) ---
def build_executable():
    print("--------------------------------------------------")
    print("[BUILD] Starting PyInstaller Build Process...")
    print("--------------------------------------------------")
    
    # Ensure pyinstaller is installed
    install_and_import("pyinstaller", "PyInstaller")
    
    script_name = os.path.basename(__file__)
    exe_name = "PDF_Watermark_Tool_v16"
    
    # FIX: Use sys.executable to call PyInstaller as a module
    # This avoids 'FileNotFoundError' if pyinstaller.exe is not in PATH
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", 
        "--onedir", 
        "--windowed",
        "--name", exe_name,
        "--hidden-import", "pypdf",
        "--hidden-import", "reportlab",
        "--hidden-import", "fitz",
        "--hidden-import", "PIL",
        "--hidden-import", "tkinter",
        script_name
    ]
    
    print(f"[EXEC] Running command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("--------------------------------------------------")
        print(f"[SUCCESS] Build Complete!")
        print(f"[INFO] Executable is located in: {os.path.join(os.getcwd(), 'dist', exe_name)}")
        print("--------------------------------------------------")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Build failed with error code {e.returncode}")
    except OSError as e:
        print(f"[FATAL] OS Error during build: {e}")

# --- 6. Main GUI Application Class ---
class PDFWatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Stamp & Watermark Tool v16")
        self.root.geometry("1350x950")

        # Variables
        self.input_file = None
        self.doc_ref = None
        self.current_page_idx = 0
        self.total_pages = 0
        self.tk_img = None 
        
        # Text Defaults
        self.wm_text = tk.StringVar(value="CONFIDENTIAL")
        self.wm_font_size = tk.IntVar(value=20) 
        self.wm_font_family = tk.StringVar(value="Helvetica")
        self.wm_font_style = tk.StringVar(value="Regular") 
        self.wm_opacity_pct = tk.IntVar(value=50) 
        self.wm_border = tk.BooleanVar(value=True)

        # Color Variables
        self.wm_color_hex = "#FF0000"
        self.wm_r = tk.IntVar(value=255)
        self.wm_g = tk.IntVar(value=0)
        self.wm_b = tk.IntVar(value=0)

        # Position Definitions
        # LT/RT at 16% down, LB/RB at 16% up
        self.position_defs = [
            # Left Column
            ("TL", "Top-Left", "0", 0),
            ("LT", "Left-Top", "90", 0),    
            ("LC", "Left-Center", "90", 0),
            ("LB", "Left-Bottom", "90", 0),
            ("BL", "Bottom-Left", "0", 0),
            ("C",  "Center", "45", 0),
            
            # Right Column
            ("TR", "Top-Right", "0", 1),
            ("RT", "Right-Top", "270", 1),
            ("RC", "Right-Center", "270", 1),
            ("RB", "Right-Bottom", "270", 1),
            ("BR", "Bottom-Right", "0", 1),
        ]

        # Dynamic Variables
        self.pos_vars = {}   
        self.rot_vars = {}   
        for pid, label, drot, col in self.position_defs:
            self.pos_vars[pid] = tk.BooleanVar(value=(pid == "C")) 
            self.rot_vars[pid] = tk.StringVar(value=drot)

        self._setup_ui()
        self.preview_canvas.bind("<Configure>", self.on_canvas_resize)

    def _setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_paned, width=540, padding=10)
        right_frame = ttk.Frame(main_paned, padding=10)
        
        main_paned.add(left_frame, weight=0)
        main_paned.add(right_frame, weight=1)

        # === LEFT PANEL ===
        # 1. File
        grp_file = ttk.LabelFrame(left_frame, text="1. File", padding=5)
        grp_file.pack(fill=tk.X, pady=5)
        ttk.Button(grp_file, text="Load PDF", command=self.load_pdf).pack(fill=tk.X)
        self.lbl_file = ttk.Label(grp_file, text="No file loaded", foreground="gray")
        self.lbl_file.pack(fill=tk.X)

        # 2. Text & Font (Reordered)
        grp_txt = ttk.LabelFrame(left_frame, text="2. Text & Font", padding=5)
        grp_txt.pack(fill=tk.X, pady=5)
        
        # Text Input
        ttk.Entry(grp_txt, textvariable=self.wm_text).pack(fill=tk.X, pady=(0, 5))
        
        # Row 1: Font Selection (Family & Style)
        r1 = ttk.Frame(grp_txt)
        r1.pack(fill=tk.X, pady=2)
        
        font_families = ['Helvetica', 'Times-Roman', 'Courier'] + REGISTERED_FONTS
        self.cb_fam = ttk.Combobox(r1, textvariable=self.wm_font_family, values=font_families, state="readonly", width=18)
        self.cb_fam.pack(side=tk.LEFT, padx=(0, 5))
        self.cb_fam.bind("<<ComboboxSelected>>", lambda e: self.update_preview())
        
        self.cb_sty = ttk.Combobox(r1, textvariable=self.wm_font_style, values=('Regular', 'Bold', 'Italic', 'BoldItalic'), state="readonly", width=12)
        self.cb_sty.pack(side=tk.LEFT)
        self.cb_sty.bind("<<ComboboxSelected>>", lambda e: self.update_preview())
        
        # Row 2: Size (Moved here)
        r2 = ttk.Frame(grp_txt)
        r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="Font Size:").pack(side=tk.LEFT)
        ttk.Spinbox(r2, from_=5, to=300, textvariable=self.wm_font_size, width=5, command=self.update_preview).pack(side=tk.LEFT, padx=5)

        # 3. Color
        grp_col = ttk.LabelFrame(left_frame, text="3. Color", padding=5)
        grp_col.pack(fill=tk.X, pady=5)
        
        # Upper: Preset Buttons (Grid Layout)
        btn_frame = ttk.Frame(grp_col)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        
        ttk.Button(btn_frame, text="Red", command=lambda: self.set_rgb(255,0,0)).grid(row=0, column=0, sticky="ew", padx=1)
        ttk.Button(btn_frame, text="Green", command=lambda: self.set_rgb(0,128,0)).grid(row=0, column=1, sticky="ew", padx=1)
        ttk.Button(btn_frame, text="Blue", command=lambda: self.set_rgb(0,0,255)).grid(row=0, column=2, sticky="ew", padx=1)

        # Lower: RGB Manual Input
        rgb_frame = ttk.Frame(grp_col)
        rgb_frame.pack(fill=tk.X)
        
        ttk.Label(rgb_frame, text="R:").pack(side=tk.LEFT)
        ttk.Entry(rgb_frame, textvariable=self.wm_r, width=4).pack(side=tk.LEFT, padx=(0,5))
        
        ttk.Label(rgb_frame, text="G:").pack(side=tk.LEFT)
        ttk.Entry(rgb_frame, textvariable=self.wm_g, width=4).pack(side=tk.LEFT, padx=(0,5))
        
        ttk.Label(rgb_frame, text="B:").pack(side=tk.LEFT)
        ttk.Entry(rgb_frame, textvariable=self.wm_b, width=4).pack(side=tk.LEFT, padx=(0,5))
        
        ttk.Button(rgb_frame, text="Apply RGB", command=self.apply_manual_rgb).pack(side=tk.LEFT, padx=5)
        
        self.lbl_swatch = tk.Label(rgb_frame, text="      ", bg=self.wm_color_hex, relief="sunken", width=4)
        self.lbl_swatch.pack(side=tk.RIGHT, fill=tk.Y)

        # Opacity & Border
        o_row = ttk.Frame(grp_col)
        o_row.pack(fill=tk.X, pady=10)
        ttk.Label(o_row, text="Opacity (%):").pack(side=tk.LEFT)
        ttk.Spinbox(o_row, from_=0, to=100, textvariable=self.wm_opacity_pct, width=5, command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(o_row, text="Border", variable=self.wm_border, command=self.update_preview).pack(side=tk.RIGHT)

        # 4. Positions
        grp_pos = ttk.LabelFrame(left_frame, text="4. Positions (Angle Deg)", padding=5)
        grp_pos.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Header with Clear Button
        head_frame = ttk.Frame(grp_pos)
        head_frame.grid(row=0, column=0, columnspan=5, sticky="ew", pady=5)
        ttk.Label(head_frame, text="Select Positions:", font=("", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(head_frame, text="Clear All", command=self.clear_positions, width=10).pack(side=tk.RIGHT)

        ttk.Separator(grp_pos, orient=tk.VERTICAL).grid(row=1, column=2, rowspan=10, sticky="ns", padx=10)

        rot_opts = ("0", "45", "90", "180", "270")
        r0, r1 = 2, 2
        
        for pid, label, _, col_idx in self.position_defs:
            if col_idx == 0:
                chk = ttk.Checkbutton(grp_pos, text=label, variable=self.pos_vars[pid], command=self.update_preview)
                chk.grid(row=r0, column=0, sticky="w", pady=2)
                cb = ttk.Combobox(grp_pos, textvariable=self.rot_vars[pid], values=rot_opts, width=4, state="readonly")
                cb.grid(row=r0, column=1, padx=5)
                cb.bind("<<ComboboxSelected>>", lambda e: self.update_preview())
                r0 += 1
            else:
                chk = ttk.Checkbutton(grp_pos, text=label, variable=self.pos_vars[pid], command=self.update_preview)
                chk.grid(row=r1, column=3, sticky="w", pady=2)
                cb = ttk.Combobox(grp_pos, textvariable=self.rot_vars[pid], values=rot_opts, width=4, state="readonly")
                cb.grid(row=r1, column=4, padx=5)
                cb.bind("<<ComboboxSelected>>", lambda e: self.update_preview())
                r1 += 1

        # 5. Actions
        grp_act = ttk.LabelFrame(left_frame, text="Actions", padding=5)
        grp_act.pack(fill=tk.X, pady=10)
        ttk.Button(grp_act, text="Refresh Preview", command=self.update_preview).pack(fill=tk.X, pady=2)
        ttk.Button(grp_act, text="SAVE AS NEW PDF", command=self.save_pdf).pack(fill=tk.X, pady=5)

        # === RIGHT PANEL ===
        self.canvas_frame = tk.Frame(right_frame, bg="#404040")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas = tk.Canvas(self.canvas_frame, bg="#404040", highlightthickness=0)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        
        nav = ttk.Frame(right_frame)
        nav.pack(fill=tk.X, pady=5)
        ttk.Button(nav, text="< Prev", command=self.prev_page).pack(side=tk.LEFT)
        self.lbl_page = ttk.Label(nav, text="0 / 0")
        self.lbl_page.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav, text="Next >", command=self.next_page).pack(side=tk.LEFT)

    # --- Logic ---
    def clear_positions(self):
        for pid in self.pos_vars:
            self.pos_vars[pid].set(False)
        self.update_preview()

    def get_font_name(self):
        fam = self.wm_font_family.get()
        sty = self.wm_font_style.get()
        
        if fam in REGISTERED_FONTS:
            if fam == "Tahoma" and ("Bold" in sty): return "Tahoma-Bold"
            return fam 

        if fam == "Helvetica":
            if sty == "Regular": return "Helvetica"
            if sty == "Bold": return "Helvetica-Bold"
            if sty == "Italic": return "Helvetica-Oblique"
            if sty == "BoldItalic": return "Helvetica-BoldOblique"
        elif fam == "Times-Roman":
            if sty == "Regular": return "Times-Roman"
            if sty == "Bold": return "Times-Bold"
            if sty == "Italic": return "Times-Italic"
            if sty == "BoldItalic": return "Times-BoldItalic"
        elif fam == "Courier":
            if sty == "Regular": return "Courier"
            if sty == "Bold": return "Courier-Bold"
            if sty == "Italic": return "Courier-Oblique"
            if sty == "BoldItalic": return "Courier-BoldOblique"
            
        return "Helvetica"

    def set_rgb(self, r, g, b):
        self.wm_r.set(r); self.wm_g.set(g); self.wm_b.set(b)
        self.apply_manual_rgb()

    def apply_manual_rgb(self):
        try:
            r = max(0, min(255, self.wm_r.get()))
            g = max(0, min(255, self.wm_g.get()))
            b = max(0, min(255, self.wm_b.get()))
            self.wm_r.set(r); self.wm_g.set(g); self.wm_b.set(b)
            self.wm_color_hex = f"#{r:02x}{g:02x}{b:02x}"
            self.lbl_swatch.config(bg=self.wm_color_hex)
            self.update_preview()
        except: pass

    def load_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.input_file = path
            self.lbl_file.config(text=os.path.basename(path))
            try:
                self.doc_ref = fitz.open(path)
                self.total_pages = self.doc_ref.page_count
                self.current_page_idx = 0
                self.update_preview()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def prev_page(self):
        if self.doc_ref and self.current_page_idx > 0:
            self.current_page_idx -= 1
            self.update_preview()

    def next_page(self):
        if self.doc_ref and self.current_page_idx < self.total_pages - 1:
            self.current_page_idx += 1
            self.update_preview()

    def get_watermark_packet(self, w, h):
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(w, h))
        
        txt = self.wm_text.get()
        font_name = self.get_font_name()
        size = self.wm_font_size.get()
        opac = self.wm_opacity_pct.get() / 100.0
        
        try: c.setFont(font_name, size)
        except: c.setFont("Helvetica", size)

        try: c.setFillColor(HexColor(self.wm_color_hex), alpha=opac)
        except: c.setFillColorRGB(0,0,0, alpha=opac)

        sw = c.stringWidth(txt, font_name, size)
        margin = 20
        
        # --- OFFSET LOGIC (16% for Side-Stamps) ---
        pct_10_w = w * 0.10
        pct_16_h = h * 0.16 # UPDATED: 16% Offset
        
        # 1. Corner X
        x_left_corner = pct_10_w + sw/2
        x_right_corner = w - pct_10_w - sw/2
        
        # Corner Y
        y_top_edge = h - margin - size/2
        y_bottom_edge = margin + size/2
        
        # 2. Side Vertical Offsets (Moved to 16%)
        y_side_top_16 = h - pct_16_h
        y_side_bottom_16 = pct_16_h
        
        x_left_edge_v = margin + size/2
        x_right_edge_v = w - margin - size/2
        
        x_center, y_center = w/2, h/2
        
        positions = []
        for pid, _, _, _ in self.position_defs:
            if self.pos_vars[pid].get():
                angle = int(self.rot_vars[pid].get())
                cx, cy = 0, 0
                
                # Top Corners
                if pid == "TL":   cx, cy = x_left_corner, y_top_edge
                elif pid == "TR": cx, cy = x_right_corner, y_top_edge
                # Bottom Corners
                elif pid == "BL": cx, cy = x_left_corner, y_bottom_edge
                elif pid == "BR": cx, cy = x_right_corner, y_bottom_edge
                
                # Left Side
                elif pid == "LT": cx, cy = x_left_edge_v, y_side_top_16
                elif pid == "LB": cx, cy = x_left_edge_v, y_side_bottom_16
                elif pid == "LC": cx, cy = x_left_edge_v, y_center
                
                # Right Side
                elif pid == "RT": cx, cy = x_right_edge_v, y_side_top_16
                elif pid == "RB": cx, cy = x_right_edge_v, y_side_bottom_16
                elif pid == "RC": cx, cy = x_right_edge_v, y_center
                
                # Center
                elif pid == "C":  cx, cy = x_center, y_center

                positions.append((cx, cy, angle))

        for cx, cy, angle in positions:
            c.saveState()
            c.translate(cx, cy)
            c.rotate(angle)
            shift_y = -(size * 0.35) 

            if self.wm_border.get():
                pad = 8
                try: c.setStrokeColor(HexColor(self.wm_color_hex), alpha=opac)
                except: pass
                box_w = sw + pad*2
                box_h = size + pad*2
                c.rect(-box_w/2, -box_h/2, box_w, box_h, fill=0)
            
            c.drawCentredString(0, shift_y, txt)
            c.restoreState()
            
        c.save()
        packet.seek(0)
        return packet

    def on_canvas_resize(self, event):
        if self.doc_ref: self.update_preview()

    def update_preview(self):
        if not self.doc_ref: return
        self.lbl_page.config(text=f"{self.current_page_idx+1} / {self.total_pages}")
        
        try:
            page = self.doc_ref.load_page(self.current_page_idx)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=True)
            mode = "RGBA" if pix.alpha else "RGB"
            bg = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            if mode == "RGBA":
                background_layer = Image.new("RGBA", bg.size, (255, 255, 255, 255))
                bg = Image.alpha_composite(background_layer, bg)

            wm_pdf = self.get_watermark_packet(page.rect.width, page.rect.height)
            wm_doc = fitz.open("pdf", wm_pdf)
            wm_pix = wm_doc.load_page(0).get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=True)
            wm_mode = "RGBA" if wm_pix.alpha else "RGB"
            wm_img = Image.frombytes(wm_mode, [wm_pix.width, wm_pix.height], wm_pix.samples)
            
            bg = bg.convert("RGBA")
            wm_img = wm_img.convert("RGBA")
            final = Image.alpha_composite(bg, wm_img)
            
            canvas_w = self.preview_canvas.winfo_width()
            canvas_h = self.preview_canvas.winfo_height()
            if canvas_w < 10: canvas_w = 800
            if canvas_h < 10: canvas_h = 600

            img_w, img_h = final.size
            ratio = min(canvas_w / img_w, canvas_h / img_h)
            new_w = int(img_w * ratio * 0.95)
            new_h = int(img_h * ratio * 0.95)
            
            final = final.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(final)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(canvas_w/2, canvas_h/2, image=self.tk_img, anchor=tk.CENTER)
        
        except Exception as e:
            print(f"Preview Error: {e}")

    def save_pdf(self):
        if not self.input_file: return
        base_dir = os.path.dirname(self.input_file)
        base_name = os.path.splitext(os.path.basename(self.input_file))[0]
        suggested_name = f"{base_name}_stamped.pdf"
        
        out = filedialog.asksaveasfilename(initialdir=base_dir, initialfile=suggested_name,
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out: return
        
        if os.path.abspath(out) == os.path.abspath(self.input_file):
            if not messagebox.askyesno("Warning", "Overwrite original file?"): return
        
        try:
            r = PdfReader(self.input_file)
            w = PdfWriter()
            
            for p in r.pages:
                mb = p.mediabox
                pkt = self.get_watermark_packet(float(mb.width), float(mb.height))
                wm_page = PdfReader(pkt).pages[0]
                p.merge_page(wm_page)
                w.add_page(p)
                
            with open(out, "wb") as f: w.write(f)
            messagebox.showinfo("Done", f"Saved to:\n{out}")
            if os.name == 'nt': os.startfile(out)
            
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--build":
        build_executable()
    else:
        root = tk.Tk()
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except: pass
        app = PDFWatermarkApp(root)
        root.mainloop()
