# --------------------------------------------------------------------------------
# Script Name: heic_converter_v39.py
# Description: Advanced Image Viewer & Batch Converter (Explorer Style).
#              Features: Drive Selector, Zoom, Batch Queue, Favorites, Clipboard.
#              Update: Added --proxy support for auto-installing missing modules.
# Author:      Gemini (Assistant)
# Created:     2025-12-17 23:30:00 (+07)
# --------------------------------------------------------------------------------
# APPLICATION SPECIFICATIONS:
# 1.  CORE FUNCTIONALITY:
#     - Viewer: Browse folders, view images with Zoom (10%-200%) and Pan.
#     - Converter: Batch convert selected images to JPG, PNG, or GIF.
#     - Clipboard: Copy current image to system clipboard (Windows DIB support).
#
# 2.  INTERFACE (GUI):
#     - Title: "Image browser and Converter".
#     - Layout: 3-Pane (Folder Tree | File/Folder List | Preview & Controls).
#     - Navigation Bar: Favorites (⭐), History (< >), Drive, Filter, Address Bar.
#     - File List: Robust Mouse Scrolling, Search Bar, Folders & Files.
#     - Preview Pane: Zoom Slider/Buttons, Fast Draft Render, Info Bar, Context Menu.
#
# 3.  LOGIC & STATE:
#     - Installation: Auto-installs dependencies with PROXY support.
#     - Favorites: Store up to 10 paths + Home location.
#     - Startup: Startup Sequence to ensure UI readiness.
#     - Auto-Save: Remembers last path and window geometry in INI file.
#
# --------------------------------------------------------------------------------
# CHANGE LOG:
# - v39: Added --proxy parameter and environment var check for pip installation.
# - v38: Fixed "GlobalLock Failed" (64-bit Clipboard).
# - v37: Changed Clipboard check to be OS-name agnostic.
# --------------------------------------------------------------------------------
# PIP INSTALL COMMAND:
# pip install Pillow pillow-heif svglib reportlab --proxy http://user:pass@proxy:port
#
# PYINSTALLER BUILD COMMAND:
# pyinstaller --noconfirm --onedir --windowed --name "My-imagetool" --hidden-import pillow_heif --hidden-import PIL.JpegImagePlugin --hidden-import PIL.PngImagePlugin --hidden-import PIL.GifImagePlugin --hidden-import PIL.BmpImagePlugin --hidden-import PIL.TiffImagePlugin --hidden-import svglib --hidden-import reportlab.graphics --hidden-import reportlab.pdfgen heic_converter_v39.py
# --------------------------------------------------------------------------------

import sys
import argparse
import os
import threading
import subprocess
import platform
import string
import queue
import time
import configparser
import ctypes
from ctypes import wintypes
from io import BytesIO
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --- CONFIGURATION ---
TITLEBAR = "Image browser and Converter"

# --- HELPER: Proxy Detection ---
def get_install_proxy():
    """
    Determines the proxy to use for pip installation.
    Priority:
    1. Command line argument --proxy
    2. Environment variable http_proxy
    3. Environment variable https_proxy
    4. None
    """
    # 1. Check sys.argv for --proxy manually (before argparse)
    if "--proxy" in sys.argv:
        try:
            idx = sys.argv.index("--proxy")
            if idx + 1 < len(sys.argv):
                return sys.argv[idx + 1]
        except ValueError:
            pass
    
    # 2. Check Environment Variables
    env_proxy = os.environ.get("http_proxy") or os.environ.get("https_proxy")
    if env_proxy:
        return env_proxy
        
    return None

# --- HELPER: Auto-Install Packages ---
def install_package(package_name):
    print(f"[*] Installing missing package: {package_name}...")
    proxy = get_install_proxy()
    
    cmd = [sys.executable, "-m", "pip", "install", package_name]
    
    if proxy:
        print(f"    Using proxy: {proxy}")
        cmd.extend(["--proxy", proxy])
        
    try:
        subprocess.check_call(cmd)
        print(f"[+] Installed {package_name}.")
    except Exception as e:
        print(f"[-] Failed to install {package_name}: {e}")
        print("    Try running script with: --proxy http://user:pass@host:port")

# --- BUILDER LOGIC ---
def run_build(build_type):
    script_path = os.path.abspath(__file__)
    print(f"--- Building for: {build_type.upper()} ---")

    try: import PyInstaller
    except ImportError: install_package("pyinstaller")

    required = ["Pillow", "pillow-heif", "svglib", "reportlab"]
    for req in required:
        try: __import__(req.replace("-","_")) 
        except ImportError: install_package(req)

    base_cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--hidden-import", "pillow_heif",
        "--hidden-import", "PIL.JpegImagePlugin",
        "--hidden-import", "PIL.PngImagePlugin",
        "--hidden-import", "PIL.GifImagePlugin",
        "--hidden-import", "PIL.BmpImagePlugin",
        "--hidden-import", "PIL.TiffImagePlugin",
        "--hidden-import", "svglib",
        "--hidden-import", "reportlab.graphics",
        "--hidden-import", "reportlab.pdfgen",
    ]

    name = "My_Image_Tool"
    if "gui" in build_type: cmd = base_cmd + ["--windowed", "--name", name]
    else: cmd = base_cmd + ["--console", "--name", name + "_CLI"]
    
    cmd.append(script_path)
    subprocess.check_call(cmd)
    print(f"[+] Build Complete. Check 'dist/{name}' folder.")

# --- RUNTIME IMPORTS ---
try:
    from PIL import Image, ImageTk, ImageOps
    import pillow_heif
except ImportError:
    if "--build" not in sys.argv:
        print("Missing core libraries. Auto-installing...")
        install_package("Pillow")
        install_package("pillow-heif")
        os.execv(sys.executable, ['python'] + sys.argv)

try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    SVG_SUPPORT = True
except ImportError:
    if "--build" not in sys.argv:
        # Optional SVG support, try to install but don't restart if fail (to avoid loops)
        install_package("svglib")
        install_package("reportlab")
        try:
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPM
            SVG_SUPPORT = True
        except ImportError:
            SVG_SUPPORT = False
    else:
        SVG_SUPPORT = False

if 'pillow_heif' in sys.modules:
    pillow_heif.register_heif_opener()

# -----------------------------------------------------------------------------
# CORE LOGIC
# -----------------------------------------------------------------------------
class ConverterEngine:
    def convert_file(self, file_path, target_dir, fmt, resize_config):
        try:
            if file_path.suffix.lower() == '.svg' and SVG_SUPPORT:
                drawing = svg2rlg(str(file_path))
                img = renderPM.drawToPIL(drawing)
            else:
                img = Image.open(file_path)
                img = ImageOps.exif_transpose(img)

            mode = resize_config.get('mode', 'factor')
            if mode == 'factor':
                divisor = resize_config.get('factor', 1)
                if divisor > 1:
                    new_w = max(1, img.width // divisor)
                    new_h = max(1, img.height // divisor)
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            elif mode == 'custom':
                target_w = resize_config.get('width', 0)
                target_h = resize_config.get('height', 0)
                if target_w > 0 or target_h > 0:
                    fit_w = target_w if target_w > 0 else 999999
                    fit_h = target_h if target_h > 0 else 999999
                    img.thumbnail((fit_w, fit_h), Image.Resampling.LANCZOS)

            if target_dir:
                save_path = Path(target_dir) / file_path.with_suffix(f".{fmt}").name
            else:
                save_path = file_path.with_suffix(f".{fmt}")

            if fmt == 'jpg':
                img = img.convert("RGB")
                img.save(save_path, "JPEG", quality=95, dpi=(300, 300))
            elif fmt == 'png':
                img.save(save_path, "PNG", dpi=(300, 300))
            elif fmt == 'gif':
                img = img.convert("P", palette=Image.ADAPTIVE, colors=256)
                img.save(save_path, "GIF")
            return True, None
        except Exception as e:
            return False, str(e)

# -----------------------------------------------------------------------------
# CLIPBOARD UTILS (Windows DIB Support - Fixed 64-bit)
# -----------------------------------------------------------------------------
def copy_image_to_clipboard(image):
    try:
        if not hasattr(ctypes, 'windll'):
             return False, "Windows API (windll) not found."

        # Convert to RGB and save as BMP to memory
        output = BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:] # Strip 14-byte BMP header for DIB
        output.close()

        # Windows API Constants & Types
        CF_DIB = 8
        GMEM_MOVEABLE = 0x0002
        
        # Explicitly define types for 64-bit compatibility
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        
        # GlobalAlloc
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        
        # GlobalLock
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        
        # GlobalUnlock
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        
        # SetClipboardData
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE

        # Open Clipboard
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        if user32.OpenClipboard(None):
            user32.EmptyClipboard()
            
            # Allocate global memory
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not h_mem:
                user32.CloseClipboard()
                return False, "GlobalAlloc failed"

            # Lock memory
            mem_ptr = kernel32.GlobalLock(h_mem)
            if not mem_ptr:
                kernel32.GlobalFree(h_mem)
                user32.CloseClipboard()
                return False, "GlobalLock failed"

            # Copy data
            ctypes.memmove(mem_ptr, data, len(data))
            
            # Unlock
            kernel32.GlobalUnlock(h_mem)
            
            # Set Clipboard
            if not user32.SetClipboardData(CF_DIB, h_mem):
                # If set fails, we must free memory. If set succeeds, system owns memory.
                kernel32.GlobalFree(h_mem) 
                user32.CloseClipboard()
                return False, "SetClipboardData failed"
            
            user32.CloseClipboard()
            return True, "Success"
        else:
            return False, "Could not open clipboard"
            
    except Exception as e:
        return False, str(e)

# -----------------------------------------------------------------------------
# GUI COMPONENTS
# -----------------------------------------------------------------------------
class CheckboxListFrame(ttk.Frame):
    def __init__(self, parent, select_callback=None, navigate_callback=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.select_callback = select_callback
        self.navigate_callback = navigate_callback
        
        self.canvas = tk.Canvas(self, borderwidth=0, background="white", takefocus=1, highlightthickness=1)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.canvas, background="white")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.items = []
        self.current_idx = -1
        self.selected_widget_bg = "#cce8ff"
        self.normal_bg = "white"

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Up>", self._move_up)
        self.canvas.bind("<Down>", self._move_down)
        self.canvas.bind("<space>", self._toggle_current_check)
        self.canvas.bind("<Return>", self._on_enter_key)
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set()) 
        
        self._bind_scroll_to_widget(self.canvas)
        self._bind_scroll_to_widget(self.scrollable_frame)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _bind_scroll_to_widget(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        if self.scrollable_frame.winfo_height() <= self.canvas.winfo_height(): return "break"
        top, bottom = self.canvas.yview()
        scroll_up = False
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0): scroll_up = True
        if scroll_up and top <= 0.0: return "break"
        if not scroll_up and bottom >= 1.0: return "break"

        if event.num == 5 or (hasattr(event, 'delta') and event.delta < 0): self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or (hasattr(event, 'delta') and event.delta > 0): self.canvas.yview_scroll(-1, "units")
        return "break"

    def add_item(self, filepath, is_folder=False):
        index = len(self.items)
        var = tk.BooleanVar(value=False)
        row = tk.Frame(self.scrollable_frame, background="white")
        row.pack(fill=tk.X, expand=True, padx=2, pady=1)
        self._bind_scroll_to_widget(row)
        
        if not is_folder:
            chk = ttk.Checkbutton(row, variable=var, takefocus=0)
            chk.pack(side=tk.LEFT)
            self._bind_scroll_to_widget(chk)
        else:
            spacer = tk.Label(row, text="  ", background="white")
            spacer.pack(side=tk.LEFT, padx=2)
            self._bind_scroll_to_widget(spacer)

        icon_char = "📁" if is_folder else "📄"
        icon_lbl = tk.Label(row, text=icon_char, background="white", foreground="gray")
        icon_lbl.pack(side=tk.LEFT, padx=(2,0))
        self._bind_scroll_to_widget(icon_lbl)
        
        lbl = tk.Label(row, text=filepath.name, background="white", anchor="w", cursor="hand2")
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._bind_scroll_to_widget(lbl)
        
        def on_click(e):
            self.canvas.focus_set()
            self._select_index(index)

        def on_double_click(e):
            if is_folder and self.navigate_callback:
                self.navigate_callback(filepath)

        for w in (lbl, row):
            w.bind("<Button-1>", on_click)
            w.bind("<Double-Button-1>", on_double_click)
        
        self.items.append({'path': filepath, 'var': var, 'widget': row, 'label': lbl, 'index': index, 'is_folder': is_folder})

    def _select_index(self, index):
        if index < 0 or index >= len(self.items): return
        if self.current_idx != -1 and self.current_idx < len(self.items):
            old = self.items[self.current_idx]
            old['label'].config(background=self.normal_bg, foreground="black")
            old['widget'].config(background=self.normal_bg)
        self.current_idx = index
        new = self.items[index]
        new['label'].config(background=self.selected_widget_bg, foreground="black")
        new['widget'].config(background=self.selected_widget_bg)
        if not new['is_folder'] and self.select_callback: self.select_callback(new['path'])
        self._ensure_visible(new['widget'])

    def _ensure_visible(self, widget):
        widget_y = widget.winfo_y(); widget_h = widget.winfo_height()
        canvas_h = self.canvas.winfo_height(); curr_y_view = self.canvas.yview()
        total_h = self.scrollable_frame.winfo_height()
        if total_h == 0: return
        top_pos = widget_y; bottom_pos = widget_y + widget_h
        view_top = curr_y_view[0] * total_h; view_bottom = curr_y_view[1] * total_h
        if top_pos < view_top: self.canvas.yview_moveto(top_pos / total_h)
        elif bottom_pos > view_bottom: self.canvas.yview_moveto((bottom_pos - canvas_h) / total_h + 0.01)

    def _move_up(self, event):
        if not self.items: return
        target = max(0, self.current_idx - 1)
        self._select_index(target)

    def _move_down(self, event):
        if not self.items: return
        target = min(len(self.items) - 1, self.current_idx + 1)
        self._select_index(target)

    def _toggle_current_check(self, event):
        if 0 <= self.current_idx < len(self.items):
            if not self.items[self.current_idx]['is_folder']:
                var = self.items[self.current_idx]['var']
                var.set(not var.get())

    def _on_enter_key(self, event):
        if 0 <= self.current_idx < len(self.items):
            item = self.items[self.current_idx]
            if item['is_folder'] and self.navigate_callback:
                self.navigate_callback(item['path'])

    def get_checked_files(self):
        return [item['path'] for item in self.items if not item['is_folder'] and item['var'].get()]

    def clear(self):
        for item in self.items: item['widget'].destroy()
        self.items.clear()
        self.current_idx = -1
        self.canvas.yview_moveto(0)

    def toggle_all(self, state=True):
        for item in self.items: 
            if not item['is_folder']: item['var'].set(state)

# -----------------------------------------------------------------------------
# APP LOGIC
# -----------------------------------------------------------------------------
class ExplorerApp:
    CONFIG_FILE = Path.home() / ".heic_explorer_config.ini"

    def __init__(self, root):
        self.root = root
        self.root.title(TITLEBAR) # USE CUSTOM TITLE
        self.root.geometry("1200x800")
        
        self.engine = ConverterEngine()
        self.current_folder = None
        self.all_files_cache = []
        
        self.history = []
        self.history_pos = -1
        self.favorites = []
        self.home_path = ""
        
        self.filters = {
            "All Images": {'.bmp', '.svg', '.jpg', '.jpeg', '.gif', '.png', '.heic', '.heif', '.tiff', '.tif'},
            "HEIC/HEIF": {'.heic', '.heif'},
            "JPG/JPEG": {'.jpg', '.jpeg'},
            "PNG": {'.png'},
            "BMP": {'.bmp'},
            "GIF": {'.gif'},
            "SVG": {'.svg'}
        }
        
        self.preview_queue = queue.Queue()
        self.full_res_image = None
        self.current_preview_path = None
        self.calc_lock = False
        self.zoom_job = None
        self.search_job = None 
        
        self._init_vars()
        self._setup_layout()
        self._init_drives()
        self._start_preview_worker()
        
        self.root.after(100, self._startup_sequence)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _startup_sequence(self):
        self._load_config()
        self._refresh_view() 

    def _init_vars(self):
        self.drive_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="All Images")
        self.search_var = tk.StringVar() 
        self.search_var.trace_add("write", self._on_search_change)
        
        self.address_var = tk.StringVar()
        self.fmt_var = tk.StringVar(value="jpg")
        self.resize_mode_var = tk.StringVar(value="factor")
        self.scale_factor_var = tk.StringVar(value="1:1")
        self.custom_w_var = tk.StringVar()
        self.custom_h_var = tk.StringVar()
        self.custom_w_var.trace_add("write", self._on_width_change)
        self.custom_h_var.trace_add("write", self._on_height_change)
        self.status_var = tk.StringVar(value="Ready")
        self.image_info_var = tk.StringVar(value="No selection")
        self.output_path_var = tk.StringVar()
        self.zoom_var = tk.DoubleVar(value=1.0)
        self.zoom_str_var = tk.StringVar(value="100%")

    def _setup_layout(self):
        # TOP NAV
        nav_bar = ttk.Frame(self.root, padding=(5, 5))
        nav_bar.pack(fill=tk.X)
        self.btn_back = ttk.Button(nav_bar, text="<", width=3, command=self._go_back, state="disabled")
        self.btn_back.pack(side=tk.LEFT, padx=(0, 2))
        self.btn_fwd = ttk.Button(nav_bar, text=">", width=3, command=self._go_forward, state="disabled")
        self.btn_fwd.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_fav = ttk.Menubutton(nav_bar, text="⭐", width=3)
        self.btn_fav.pack(side=tk.LEFT, padx=(0, 10))
        self.fav_menu = tk.Menu(self.btn_fav, tearoff=0)
        self.btn_fav.config(menu=self.fav_menu)
        self._update_fav_menu()
        ttk.Label(nav_bar, text="Drive:").pack(side=tk.LEFT)
        self.cb_drive = ttk.Combobox(nav_bar, textvariable=self.drive_var, state="readonly", width=5)
        self.cb_drive.pack(side=tk.LEFT, padx=(5, 10))
        self.cb_drive.bind("<<ComboboxSelected>>", self._on_drive_select)
        ttk.Label(nav_bar, text="Type:").pack(side=tk.LEFT)
        self.cb_filter = ttk.Combobox(nav_bar, textvariable=self.filter_var, values=list(self.filters.keys()), state="readonly", width=12)
        self.cb_filter.pack(side=tk.LEFT, padx=(5, 10))
        self.cb_filter.bind("<<ComboboxSelected>>", self._on_filter_change)
        ttk.Button(nav_bar, text="⬆", width=3, command=self._go_up).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(nav_bar, text="↻", width=3, command=self._refresh_view).pack(side=tk.LEFT, padx=(0, 5))
        self.entry_path = ttk.Entry(nav_bar, textvariable=self.address_var)
        self.entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry_path.bind("<Return>", self._on_address_enter)
        ttk.Button(nav_bar, text="Browse...", command=self._browse_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(nav_bar, text="+ Import", command=self._import_files).pack(side=tk.LEFT)

        # PANES
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=4, bg="#d9d9d9")
        self.paned.pack(fill=tk.BOTH, expand=True)

        # Left
        left_frame = ttk.Frame(self.paned)
        self.paned.add(left_frame, width=250)
        self.tree = ttk.Treeview(left_frame, show="tree")
        ysb = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(left_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=ysb.set, xscroll=xsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y); xsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Middle
        mid_frame = ttk.Frame(self.paned)
        self.paned.add(mid_frame, width=350)
        mid_filter = ttk.Frame(mid_frame)
        mid_filter.pack(fill=tk.X, padx=2, pady=2)
        ttk.Label(mid_filter, text="🔍").pack(side=tk.LEFT, padx=(2,0))
        self.ent_search = ttk.Entry(mid_filter, textvariable=self.search_var)
        self.ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        mid_tools = ttk.Frame(mid_frame)
        mid_tools.pack(fill=tk.X, padx=2, pady=2)
        ttk.Button(mid_tools, text="All", width=5, command=lambda: self.file_list.toggle_all(True)).pack(side=tk.LEFT)
        ttk.Button(mid_tools, text="None", width=5, command=lambda: self.file_list.toggle_all(False)).pack(side=tk.LEFT)
        self.file_list = CheckboxListFrame(mid_frame, select_callback=self._trigger_preview_load, navigate_callback=self._navigate_to)
        self.file_list.pack(fill=tk.BOTH, expand=True)

        # Right
        right_frame = ttk.Frame(self.paned)
        self.paned.add(right_frame, width=450)
        viewer_container = ttk.Frame(right_frame)
        viewer_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.v_xscroll = ttk.Scrollbar(viewer_container, orient="horizontal")
        self.v_yscroll = ttk.Scrollbar(viewer_container, orient="vertical")
        self.viewer_canvas = tk.Canvas(viewer_container, bg="#202020", highlightthickness=0, 
                                       xscrollcommand=self.v_xscroll.set, yscrollcommand=self.v_yscroll.set)
        self.v_xscroll.config(command=self.viewer_canvas.xview)
        self.v_yscroll.config(command=self.viewer_canvas.yview)
        self.v_xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.v_yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.viewer_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.viewer_canvas.bind("<ButtonPress-1>", self._start_pan)
        self.viewer_canvas.bind("<B1-Motion>", self._do_pan)
        self.viewer_canvas.bind("<MouseWheel>", self._wheel_zoom)
        self.viewer_canvas.bind("<Button-4>", self._wheel_zoom)
        self.viewer_canvas.bind("<Button-5>", self._wheel_zoom)
        # Context Menu
        self.preview_menu = tk.Menu(self.viewer_canvas, tearoff=0)
        self.preview_menu.add_command(label="Copy Image", command=self._copy_current_image)
        self.viewer_canvas.bind("<Button-3>", lambda e: self.preview_menu.post(e.x_root, e.y_root))
        
        self.lbl_info = ttk.Label(viewer_container, textvariable=self.image_info_var, background="#e0e0e0", relief="flat", anchor="center")
        self.lbl_info.pack(fill=tk.X)

        zoom_frame = ttk.Frame(right_frame)
        zoom_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(zoom_frame, text="Zoom:").pack(side=tk.LEFT)
        ttk.Button(zoom_frame, text="-", width=2, command=self._zoom_minus).pack(side=tk.LEFT)
        self.zoom_slider = ttk.Scale(zoom_frame, from_=0.1, to=2.0, variable=self.zoom_var, command=self._on_zoom_slide)
        self.zoom_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(zoom_frame, text="+", width=2, command=self._zoom_plus).pack(side=tk.LEFT)
        zoom_levels = [f"{i}%" for i in range(10, 210, 10)]
        self.cb_zoom = ttk.Combobox(zoom_frame, textvariable=self.zoom_str_var, values=zoom_levels, width=5, state="readonly")
        self.cb_zoom.pack(side=tk.LEFT, padx=(5,2))
        self.cb_zoom.bind("<<ComboboxSelected>>", self._on_zoom_combo)
        ttk.Button(zoom_frame, text="Fit", width=4, command=self._fit_to_window).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="📋 Copy", command=self._copy_current_image).pack(side=tk.LEFT, padx=5)

        ctrl_frame = ttk.LabelFrame(right_frame, text="Conversion Options", padding=10)
        ctrl_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        r1 = ttk.Frame(ctrl_frame); r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="Target:").pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self.output_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(r1, text="...", width=3, command=self._browse_target).pack(side=tk.LEFT, padx=(0,2))
        ttk.Button(r1, text="📂 Open", command=self._open_target_folder).pack(side=tk.LEFT)
        r2 = ttk.Frame(ctrl_frame); r2.pack(fill=tk.X, pady=5)
        ttk.Label(r2, text="Format:").pack(side=tk.LEFT)
        for f in ["jpg", "png", "gif"]: ttk.Radiobutton(r2, text=f.upper(), variable=self.fmt_var, value=f).pack(side=tk.LEFT, padx=5)
        r3 = ttk.Frame(ctrl_frame); r3.pack(fill=tk.X, pady=5)
        ttk.Label(r3, text="Resize:").pack(side=tk.LEFT)
        rb_factor = ttk.Radiobutton(r3, text="Scale:", variable=self.resize_mode_var, value="factor", command=self._toggle_resize_ui)
        rb_factor.pack(side=tk.LEFT)
        self.cb_scale = ttk.Combobox(r3, textvariable=self.scale_factor_var, values=["1:1", "1:2", "1:3", "1:4"], width=5, state="readonly")
        self.cb_scale.pack(side=tk.LEFT, padx=5)
        rb_custom = ttk.Radiobutton(r3, text="Fit Size:", variable=self.resize_mode_var, value="custom", command=self._toggle_resize_ui)
        rb_custom.pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(r3, text="W").pack(side=tk.LEFT, padx=(2,1))
        self.ent_w = ttk.Entry(r3, textvariable=self.custom_w_var, width=5)
        self.ent_w.pack(side=tk.LEFT)
        ttk.Label(r3, text="H").pack(side=tk.LEFT, padx=(2,1))
        self.ent_h = ttk.Entry(r3, textvariable=self.custom_h_var, width=5)
        self.ent_h.pack(side=tk.LEFT)
        self.btn_convert = ttk.Button(ctrl_frame, text="CONVERT ➔", command=self._start_batch)
        self.btn_convert.pack(fill=tk.X, pady=(10, 0))
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate")
        self.progress.pack(side=tk.BOTTOM, fill=tk.X)
        self._toggle_resize_ui()

    # --- CLIPBOARD ---
    def _copy_current_image(self):
        if self.full_res_image:
            success, msg = copy_image_to_clipboard(self.full_res_image)
            if success:
                self.status_var.set("Image copied to clipboard!")
            else:
                messagebox.showerror("Clipboard Error", f"Failed to copy image.\nReason: {msg}")

    # --- FAVORITES & HOME ---
    def _update_fav_menu(self):
        self.fav_menu.delete(0, tk.END)
        self.fav_menu.add_command(label="➕ Add Current to Favorites", command=self._add_current_to_fav)
        self.fav_menu.add_command(label="🏠 Set Current as Home", command=self._set_current_as_home)
        self.fav_menu.add_command(label="❌ Clear Home (Reset)", command=self._clear_home)
        self.fav_menu.add_separator()
        if not self.favorites: self.fav_menu.add_command(label="(No Favorites)", state="disabled")
        else:
            for path in self.favorites:
                self.fav_menu.add_command(label=f"📂 {Path(path).name}", command=lambda p=path: self._navigate_to(p))
        self.fav_menu.add_separator()
        self.fav_menu.add_command(label="🗑 Clear Favorites", command=self._clear_favorites)

    def _add_current_to_fav(self):
        if not self.current_folder: return
        path_str = str(self.current_folder)
        if path_str not in self.favorites:
            if len(self.favorites) >= 10: self.favorites.pop(0)
            self.favorites.append(path_str)
            self._update_fav_menu()
            messagebox.showinfo("Favorites", "Added to favorites.")

    def _set_current_as_home(self):
        if not self.current_folder: return
        self.home_path = str(self.current_folder)
        messagebox.showinfo("Home", f"Default start location set to:\n{self.home_path}")

    def _clear_home(self):
        self.home_path = ""
        messagebox.showinfo("Home", "Default start location cleared.")

    def _clear_favorites(self):
        self.favorites = []
        self._update_fav_menu()

    # --- STATE MANAGEMENT ---
    def _load_config(self):
        initial_path = Path.home() / "Documents"
        if self.CONFIG_FILE.exists():
            config = configparser.ConfigParser()
            try:
                config.read(self.CONFIG_FILE)
                if 'Window' in config and 'geometry' in config['Window']:
                    self.root.geometry(config['Window']['geometry'])
                if 'Favorites' in config:
                    fav_str = config['Favorites'].get('paths', '')
                    if fav_str: self.favorites = fav_str.split('|')
                    self.home_path = config['Favorites'].get('default_home', '')
                    self._update_fav_menu()
                if self.home_path and os.path.exists(self.home_path):
                    initial_path = Path(self.home_path)
                elif 'Navigation' in config and 'last_path' in config['Navigation']:
                    saved_path = config['Navigation']['last_path']
                    if os.path.exists(saved_path): initial_path = Path(saved_path)
            except: pass
        self._navigate_to(initial_path)

    def _on_close(self):
        config = configparser.ConfigParser()
        config['Window'] = {'geometry': self.root.geometry()}
        config['Navigation'] = {'last_path': str(self.current_folder) if self.current_folder else ""}
        config['Favorites'] = {'paths': '|'.join(self.favorites), 'default_home': self.home_path}
        try:
            with open(self.CONFIG_FILE, 'w') as f: config.write(f)
        except: pass
        self.root.destroy()

    def _toggle_resize_ui(self):
        if self.resize_mode_var.get() == 'factor':
            self.cb_scale.state(['!disabled']); self.ent_w.state(['disabled']); self.ent_h.state(['disabled'])
        else:
            self.cb_scale.state(['disabled']); self.ent_w.state(['!disabled']); self.ent_h.state(['!disabled'])

    # --- FILTRATION (Restored) ---
    def _on_search_change(self, *args):
        if self.search_job: self.root.after_cancel(self.search_job)
        self.search_job = self.root.after(500, self._apply_file_filter)

    def _apply_file_filter(self):
        search_term = self.search_var.get().lower()
        self.file_list.canvas.pack_forget()
        self.file_list.clear()
        count = 0
        for item in self.all_files_cache:
            if search_term in item['path'].name.lower():
                self.file_list.add_item(item['path'], is_folder=item['is_folder'])
                count += 1
        self.file_list.canvas.pack(side="left", fill="both", expand=True)
        if search_term: self.status_var.set(f"Filtered: {count} items matching '{search_term}'")

    # --- LOGIC SECTIONS ---
    def _on_width_change(self, *args):
        if self.calc_lock or not self.full_res_image: return
        w_str = self.custom_w_var.get()
        if not w_str.isdigit(): return
        self.calc_lock = True
        try:
            ratio = self.full_res_image.width / self.full_res_image.height
            w = int(w_str); h = int(w / ratio)
            self.custom_h_var.set(str(h))
        except: pass
        self.calc_lock = False

    def _on_height_change(self, *args):
        if self.calc_lock or not self.full_res_image: return
        h_str = self.custom_h_var.get()
        if not h_str.isdigit(): return
        self.calc_lock = True
        try:
            ratio = self.full_res_image.width / self.full_res_image.height
            h = int(h_str); w = int(h * ratio)
            self.custom_w_var.set(str(w))
        except: pass
        self.calc_lock = False

    def _start_preview_worker(self):
        def worker():
            while True:
                path = self.preview_queue.get()
                if path is None: break
                try:
                    size_mb = path.stat().st_size / (1024 * 1024)
                    if path.suffix.lower() == '.svg' and SVG_SUPPORT:
                        img = renderPM.drawToPIL(svg2rlg(str(path)))
                    else:
                        img = Image.open(path); img = ImageOps.exif_transpose(img)
                    self.root.after(0, lambda: self._update_preview_image(img, path, size_mb))
                except Exception as e: self.root.after(0, lambda: self._show_preview_error(str(e)))
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _trigger_preview_load(self, filepath):
        self.viewer_canvas.delete("all")
        self.viewer_canvas.create_text(self.viewer_canvas.winfo_width()//2, self.viewer_canvas.winfo_height()//2, text="Loading...", fill="white")
        self.preview_queue.put(filepath)

    def _update_preview_image(self, full_image, path, size_mb):
        self.full_res_image = full_image
        self.current_preview_path = path
        if self.resize_mode_var.get() == 'custom' and not self.custom_w_var.get():
             self.calc_lock = True
             self.custom_w_var.set(str(full_image.width)); self.custom_h_var.set(str(full_image.height))
             self.calc_lock = False
        self.image_info_var.set(f"{path.name}  |  {full_image.width} x {full_image.height} px  |  {size_mb:.2f} MB")
        self.status_var.set(f"Viewing: {path.name}")
        self._fit_to_window()

    def _show_preview_error(self, msg):
        self.viewer_canvas.delete("all")
        self.viewer_canvas.create_text(100, 100, text=f"Error: {msg}", fill="red")

    def _fit_to_window(self):
        if not self.full_res_image: return
        cw = self.viewer_canvas.winfo_width(); ch = self.viewer_canvas.winfo_height()
        if cw < 10 or ch < 10: return
        w_ratio = cw / self.full_res_image.width
        h_ratio = ch / self.full_res_image.height
        scale = min(w_ratio, h_ratio, 1.0)
        self.zoom_var.set(scale)
        self.zoom_str_var.set(f"{int(scale*100)}%")
        self._render_zoom(hq=True)

    def _on_zoom_slide(self, val):
        self.zoom_str_var.set(f"{int(float(val)*100)}%")
        self._render_zoom(hq=False)
        if self.zoom_job: self.root.after_cancel(self.zoom_job)
        self.zoom_job = self.root.after(200, lambda: self._render_zoom(hq=True))

    def _on_zoom_combo(self, event):
        val_str = self.zoom_str_var.get().replace("%", "")
        try:
            val = int(val_str) / 100.0
            self.zoom_var.set(val)
            self._render_zoom(hq=True)
        except: pass

    def _zoom_plus(self):
        curr = self.zoom_var.get()
        new_val = min(2.0, curr + 0.1)
        self.zoom_var.set(new_val)
        self._on_zoom_slide(new_val)

    def _zoom_minus(self):
        curr = self.zoom_var.get()
        new_val = max(0.1, curr - 0.1)
        self.zoom_var.set(new_val)
        self._on_zoom_slide(new_val)

    def _wheel_zoom(self, event):
        if not self.full_res_image: return
        if event.num == 5 or event.delta < 0: factor = 0.9 
        else: factor = 1.1 
        new_zoom = self.zoom_var.get() * factor
        new_zoom = max(0.1, min(new_zoom, 2.0))
        self.zoom_var.set(new_zoom)
        self.zoom_str_var.set(f"{int(new_zoom*100)}%")
        self._render_zoom(hq=False)
        if self.zoom_job: self.root.after_cancel(self.zoom_job)
        self.zoom_job = self.root.after(200, lambda: self._render_zoom(hq=True))

    def _render_zoom(self, hq=True):
        if not self.full_res_image: return
        scale = self.zoom_var.get()
        new_w = int(self.full_res_image.width * scale)
        new_h = int(self.full_res_image.height * scale)
        method = Image.Resampling.BILINEAR if hq else Image.Resampling.NEAREST
        resized = self.full_res_image.resize((new_w, new_h), method)
        self.tk_image = ImageTk.PhotoImage(resized)
        self.viewer_canvas.delete("all")
        self.viewer_canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        self.viewer_canvas.config(scrollregion=self.viewer_canvas.bbox("all"))

    def _start_pan(self, event):
        self.viewer_canvas.scan_mark(event.x, event.y)

    def _do_pan(self, event):
        self.viewer_canvas.scan_dragto(event.x, event.y, gain=1)

    def _init_drives(self):
        drives = []
        if platform.system() == "Windows":
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1: drives.append(f"{letter}:\\")
                bitmask >>= 1
        else: drives = ["/"]
        self.cb_drive['values'] = drives
        if self.current_folder and platform.system() == "Windows":
            root = self.current_folder.anchor
            if root in drives: self.cb_drive.set(root)
        elif drives: self.cb_drive.current(0)

    def _on_drive_select(self, event):
        d = self.cb_drive.get()
        for i in self.tree.get_children(): self.tree.delete(i)
        root_node = self.tree.insert("", "end", text=f" {d}", values=[d], open=True)
        self._populate_tree(root_node, d)
        self._navigate_to(d)
        
    def _on_filter_change(self, event):
        if self.current_folder: self._load_file_list(self.current_folder)

    def _populate_tree(self, parent_node, path):
        self.tree.delete(*self.tree.get_children(parent_node))
        try:
            for p in Path(path).iterdir():
                if p.is_dir() and not p.name.startswith(('$','.')):
                    node = self.tree.insert(parent_node, "end", text=f" 📁 {p.name}", values=[str(p)])
                    self.tree.insert(node, "end", text="dummy")
        except: pass

    def _on_tree_open(self, event):
        node = self.tree.focus()
        if node: self._populate_tree(node, self.tree.item(node, "values")[0])

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if sel: self._navigate_to(self.tree.item(sel[0], "values")[0])

    def _go_back(self):
        if self.history_pos > 0:
            self.history_pos -= 1
            self._navigate_to(self.history[self.history_pos], record_history=False)

    def _go_forward(self):
        if self.history_pos < len(self.history) - 1:
            self.history_pos += 1
            self._navigate_to(self.history[self.history_pos], record_history=False)

    def _update_nav_buttons(self):
        state_back = "normal" if self.history_pos > 0 else "disabled"
        state_fwd = "normal" if self.history_pos < len(self.history) - 1 else "disabled"
        self.btn_back.config(state=state_back)
        self.btn_fwd.config(state=state_fwd)

    def _navigate_to(self, path, record_history=True):
        p = Path(path)
        if not p.exists(): return
        
        if record_history:
            if self.history_pos < len(self.history) - 1:
                self.history = self.history[:self.history_pos+1]
            if not self.history or self.history[-1] != p:
                self.history.append(p)
                self.history_pos += 1
                if len(self.history) > 20: 
                    self.history.pop(0)
                    self.history_pos -= 1

        self._update_nav_buttons()
        self.current_folder = p
        self.address_var.set(str(p))
        self.entry_path.delete(0, tk.END)
        self.entry_path.insert(0, str(p))
        self._load_file_list(p)
        self.output_path_var.set(str(p))
        if platform.system() == "Windows": self.cb_drive.set(p.anchor)
        if not self.tree.get_children():
             root = p.anchor if platform.system() == "Windows" else "/"
             root_node = self.tree.insert("", "end", text=f" {root}", values=[root], open=True)
             self._populate_tree(root_node, root)

    def _on_address_enter(self, e):
        if os.path.isdir(self.address_var.get()): self._navigate_to(self.address_var.get())

    def _go_up(self):
        if self.current_folder and self.current_folder.parent != self.current_folder: self._navigate_to(self.current_folder.parent)
    def _refresh_view(self):
        if self.current_folder: self._load_file_list(self.current_folder)
        else: self._navigate_to(Path.home())
    def _browse_folder(self):
        d = filedialog.askdirectory()
        if d: self._navigate_to(d)
    def _browse_target(self):
        d = filedialog.askdirectory()
        if d: self.output_path_var.set(d)
    def _open_target_folder(self):
        path = self.output_path_var.get()
        if os.path.exists(path):
            if platform.system() == "Windows": os.startfile(path)
            else: subprocess.Popen(["xdg-open", path])
        else: messagebox.showwarning("Error", "Target path does not exist.")

    def _load_file_list(self, folder):
        self.file_list.canvas.pack_forget() 
        self.file_list.clear()
        self.viewer_canvas.delete("all") 
        self.full_res_image = None
        self.image_info_var.set("")
        self.root.update_idletasks()
        
        self.all_files_cache = [] # RESET CACHE
        active_filter = self.filters.get(self.filter_var.get(), self.filters["All Images"])
        
        try:
            for p in folder.iterdir():
                if p.is_dir() and not p.name.startswith(('$','.')):
                    self.all_files_cache.append({'path': p, 'is_folder': True})
        except: pass

        try:
            for p in folder.iterdir():
                if p.is_file() and p.suffix.lower() in active_filter:
                    self.all_files_cache.append({'path': p, 'is_folder': False})
        except: pass
        
        self._apply_file_filter()
        self.file_list.canvas.pack(side="left", fill="both", expand=True)
        self.status_var.set(f"Found {len(self.all_files_cache)} items in {folder.name}")

    def _import_files(self):
        filters = (("Supported Images", "*.*"),)
        files = filedialog.askopenfilenames(title="Import Images", filetypes=filters)
        if files:
            for f in files: self.file_list.add_item(Path(f))

    def _start_batch(self):
        files = self.file_list.get_checked_files()
        if not files: messagebox.showwarning("!", "No files selected."); return
        target = self.output_path_var.get().strip()
        if not target: target = str(self.current_folder) if self.current_folder else ""
        if not target: messagebox.showerror("Error", "Target folder is undefined."); return
        target_path = Path(target)
        if not target_path.exists():
            if not messagebox.askyesno("Create Folder?", f"Create directory:\n{target}?"): return
            try: target_path.mkdir(parents=True, exist_ok=True)
            except Exception as e: messagebox.showerror("Error", f"Could not create: {e}"); return
        mode = self.resize_mode_var.get()
        config = {'mode': mode}
        if mode == 'factor':
            scale_map = {"1:1": 1, "1:2": 2, "1:3": 3, "1:4": 4}
            config['factor'] = scale_map.get(self.scale_factor_var.get(), 1)
        else:
            try: config['width'] = int(self.custom_w_var.get() or 0)
            except: config['width'] = 0
            try: config['height'] = int(self.custom_h_var.get() or 0)
            except: config['height'] = 0
        self.btn_convert.config(state="disabled")
        self.progress['value'] = 0; self.progress['maximum'] = len(files)
        threading.Thread(target=self._run_convert, args=(files, target, config)).start()

    def _run_convert(self, files, target_dir, config):
        succ, err = 0, 0
        fmt = self.fmt_var.get()
        for i, f in enumerate(files):
            ok, msg = self.engine.convert_file(f, target_dir, fmt, config)
            if ok: succ += 1
            else: err += 1
            self.progress['value'] = i + 1
        self.status_var.set(f"Done: {succ} OK, {err} Errs")
        messagebox.showinfo("Report", f"Processed {len(files)} files.\nSuccess: {succ}\nErrors: {err}")
        self.btn_convert.config(state="normal")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Image Explorer")
    parser.add_argument('--build', choices=['win-gui', 'win-cli', 'linux-gui', 'linux-cli'], help="Build")
    parser.add_argument('--proxy', help="Proxy for installing modules (http://user:pass@host:port)")
    args = parser.parse_args()

    if args.build:
        run_build(args.build)
    else:
        root = tk.Tk()
        app = ExplorerApp(root)
        root.mainloop()
