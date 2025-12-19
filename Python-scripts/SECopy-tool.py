#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interval File Copy Utility (Scheduled and Logged)
Generated on: 2025-09-26 13:23:25 +07

*** SPECIFICATIONS AND BEHAVIOR ***
- Purpose: Automatically copy files, including those in subfolders, from multiple source directories 
  to a structured target directory at a configurable interval.
- **Recursive Copy:** Uses os.walk() to include files within subfolders.
- Default Mode: Runs in **GUI** mode if no arguments are provided.
- CLI Mode: Use the **--cli** flag to run the scheduler using parameters defined in 'config/config.ini'.
- Target Directory Structure (Includes Subfolder): 
    - The file's original subfolder structure is preserved under the date stamp.
    - Structure: target_dir / source_folder_name / YYYY / MM / DD / HH / [Original Subpath] / file_name
- Configuration Paths:
    - **Path Separator Hint:** Uses the native OS separator ('\' for Windows, '/' for Unix/Linux) for directory inputs and log paths.
- Logging: 
    - All successful copies and failures are logged to 'config/copy_log_YYMMDD.csv'. (New file generated daily)
    - **CSV Quoting:** All fields in the log file are enclosed in double quotes ("") for data integrity.
    - Log Format (Fields):
        1. source folder (Full path of original file directory, including subpath if applicable)
        2. file name (Name of the copied file)
        3. **target absolute path (Absolute path to the copied file location)**
        4. action date/time (Timestamp of when the copy operation occurred)
        5. **status / error message (SUCCESS or exception details)**
- **GUI Feature:** Displays the last 100 copy events in a grid view, highlighting errors in red.

Usage:
  python interval_copy_util.py           (Runs the GUI)
  python interval_copy_util.py --cli     (Runs scheduled job using config/config.ini)
  python interval_copy_util.py --help -h (Show this help message and exit)

Options:
  --cli            Run the application in command line mode (loads config/config.ini and starts the scheduled job).
  --help, -h       Show this help message and exit.
  --hiden-import   This hint is for PyInstaller: additional modules to include 
                   are 'tkinter', 'configparser', 'schedule', 'os', 'shutil', 'time', 'datetime', 'csv', 'tkinter.ttk'.
"""

import sys
import os
import shutil
import time
import argparse
import configparser
import csv
from datetime import datetime
from collections import deque # To manage the 100-file history efficiently

# Non-standard module needed:
# If 'schedule' is missing, install it with: pip install schedule

try:
    import schedule
except ImportError:
    print("Error: The 'schedule' module is not installed.")
    print("Please install it using: pip install schedule")
    sys.exit(1)

# --- Configuration Constants ---
CONFIG_DIR = 'config'
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_HISTORY_LIMIT = 100 # Limit for the GUI display

# New log file naming convention with date
TODAY_DATE_STR = datetime.now().strftime('%y%m%d')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.ini')
# Log file path generation is dynamic, only used inside functions

# UPDATED LOG HEADER (reduced fields for grid view)
LOG_HEADER = ['source folder', 'file name', 'target absolute path', 'action date/time', 'status / error message']

# Columns for the GUI Treeview
TREE_COLUMNS = ['Time', 'File Name', 'Source Path', 'Target Path', 'Status']
# Map LOG_HEADER to TREE_COLUMNS indices
# Log Index: [0: source folder, 1: file name, 2: target absolute path, 3: action date/time, 4: status / error message]
# Tree Index: [0: Time, 1: File Name, 2: Source Path, 3: Target Path, 4: Status]

# Determine OS for input hint and time path format
IS_WINDOWS = os.name == 'nt'
PATH_SEP_HINT = os.sep # Use os.sep ('\' or '/')
TIME_SUBDIR_FORMAT = f'%Y{os.sep}%m{os.sep}%d{os.sep}%H'

# Global Deque to store log history for GUI (used if GUI is running)
LOG_HISTORY = deque(maxlen=LOG_HISTORY_LIMIT)

# --- Core Logic ---

def configure_config_file():
    """Ensures the configuration directory exists."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    return CONFIG_FILE

def load_config():
    """Loads configuration from the config file."""
    config = configparser.ConfigParser()
    config_file = configure_config_file()
    
    if os.path.exists(config_file):
        config.read(config_file)
    else:
        # Set defaults if file doesn't exist
        print(f"[{datetime.now().strftime(TIME_FORMAT)}] WARNING: {CONFIG_FILE} not found. Using default settings.")
        config['Settings'] = {
            'source_dirs': '', 
            'target_dir': '',
            'interval_minutes': '5',
            'file_patterns': '*.txt;*.log', # Example patterns
        }
    
    return config

def save_config(source_dirs, target_dir, interval_minutes, file_patterns):
    """Saves the current configuration to the config file."""
    config = configparser.ConfigParser()
    config['Settings'] = {
        'source_dirs': source_dirs,
        'target_dir': target_dir,
        'interval_minutes': str(interval_minutes),
        'file_patterns': file_patterns,
    }
    
    with open(configure_config_file(), 'w') as configfile:
        config.write(configfile)
    
    print(f"Configuration saved to {CONFIG_FILE}")

def write_log_entry(data_row, log_history_deque=None, app_instance=None):
    """
    Writes a single row to the CSV log file and, if GUI is running, updates the in-memory history.
    
    data_row: [source folder, file name, target absolute path, action date/time, status / error message]
    """
    
    # 1. Write to permanent CSV log file
    LOG_FILE_DAILY = os.path.join(CONFIG_DIR, f'copy_log_{datetime.now().strftime("%y%m%d")}.csv')
    file_exists = os.path.exists(LOG_FILE_DAILY)
    
    try:
        with open(LOG_FILE_DAILY, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            
            if not file_exists:
                writer.writerow(LOG_HEADER)
            
            writer.writerow(data_row)
            
    except Exception as e:
        print(f"[{datetime.now().strftime(TIME_FORMAT)}] CRITICAL ERROR writing to log: {e}")

    # 2. Update in-memory log history for GUI display
    if log_history_deque is not None:
        # We only store the relevant fields for the GUI display
        gui_row = [
            data_row[3].split()[-1], # Time only
            data_row[1],             # File Name
            data_row[0],             # Source Path (full path)
            data_row[2],             # Target Path (absolute path)
            data_row[4]              # Status / Error Message
        ]
        log_history_deque.appendleft(gui_row) # Add to the start (most recent)
        
        # Signal the GUI to update (if the app instance is passed)
        if app_instance is not None:
            app_instance.update_log_display()


def interval_copy_files(source_dirs_str, target_dir, file_patterns, log_history_deque=None, app_instance=None):
    """
    Core function to copy files recursively and log the output.
    Takes optional log_history_deque and app_instance for GUI integration.
    """
    source_dirs = [d.strip() for d in source_dirs_str.split(';') if d.strip()]
    
    if not source_dirs:
        print(f"[{datetime.now().strftime(TIME_FORMAT)}] WARNING: No source directories configured. Skipping copy.")
        return

    patterns = [p.strip() for p in file_patterns.split(';') if p.startswith('*')]
    total_copied_count = 0
    target_dir = os.path.normpath(os.path.abspath(target_dir))
    
    for source_dir in source_dirs:
        source_dir_norm = os.path.normpath(os.path.abspath(source_dir))
        source_name = os.path.basename(source_dir_norm)
        
        if not os.path.isdir(source_dir_norm):
            print(f"[{datetime.now().strftime(TIME_FORMAT)}] ERROR: Source directory not found: {source_dir_norm}")
            continue
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Processing source (including subfolders): {source_dir_norm}")
        copied_from_source = 0
        source_base_prefix = source_dir_norm.rstrip(os.sep) + os.sep
        
        try:
            for root, dirs, files in os.walk(source_dir_norm):
                
                # --- Relative Path Calculation ---
                if root == source_dir_norm:
                    rel_sub_path = '.'
                else:
                    root_norm = os.path.normpath(root)
                    if root_norm.startswith(source_base_prefix):
                        rel_sub_path = root_norm[len(source_base_prefix):]
                    else:
                        rel_sub_path = os.path.relpath(root_norm, source_dir_norm)
                        if rel_sub_path.startswith('..'):
                            rel_sub_path = root_norm[len(source_dir_norm):].lstrip(os.sep)
                            if not rel_sub_path: rel_sub_path = '.'
                # --- End Relative Path Calculation ---
                
                for filename in files:
                    source_path = os.path.join(root, filename)
                    
                    if not any(filename.endswith(p[1:]) for p in patterns):
                         continue

                    # Log entry template: [source folder, file name, target absolute path, action date/time, status / error message]
                    log_entry = [source_path, filename, "", datetime.now().strftime(TIME_FORMAT), ""]
                    target_path = 'N/A' 

                    try:
                        mod_timestamp = os.path.getmtime(source_path)
                        mod_dt = datetime.fromtimestamp(mod_timestamp)
                        time_sub_dir = mod_dt.strftime(TIME_SUBDIR_FORMAT)
                        base_target_dir = os.path.join(target_dir, source_name, time_sub_dir)
                        final_target_dir = os.path.join(base_target_dir, rel_sub_path)
                        
                        os.makedirs(final_target_dir, exist_ok=True)
                        target_path = os.path.join(final_target_dir, filename)
                        
                        shutil.copy2(source_path, target_path) 
                        
                        # SUCCESS LOGGING
                        log_entry[2] = target_path
                        log_entry[4] = "SUCCESS"
                        write_log_entry(log_entry, log_history_deque, app_instance)
                        
                        print_source = os.path.join(rel_sub_path, filename) if rel_sub_path != '.' else filename
                        print(f"  - Copied: {print_source} -> {target_path}")
                        
                        copied_from_source += 1
                        total_copied_count += 1
                        
                    except Exception as e:
                        # ERROR LOGGING
                        error_msg = str(e).replace('\n', ' ')
                        log_entry[2] = target_path
                        log_entry[4] = f"ERROR: {error_msg}"
                        write_log_entry(log_entry, log_history_deque, app_instance)

                        print(f"  - ERROR processing {source_path}: {error_msg}")
            
        except PermissionError as pe:
             print(f"  [CRITICAL] PERMISSION ERROR: Cannot read directory {source_dir_norm}. Error: {pe}")
        except FileNotFoundError as fnfe:
             print(f"  [CRITICAL] FILE NOT FOUND ERROR: Source directory {source_dir_norm} disappeared during walk. Error: {fnfe}")
        except Exception as e_walk:
             print(f"  [CRITICAL] UNEXPECTED ERROR during os.walk on {source_dir_norm}: {e_walk}")


        print(f"  > Done processing all files in {source_dir_norm}. Files copied: {copied_from_source}")

    print(f"[{datetime.now().strftime(TIME_FORMAT)}] Copy run complete. Total files copied: {total_copied_count}")

# --- CLI Mode Implementation ---

def run_cli_mode():
    """Loads config, sets up the schedule, and runs the infinite loop for CLI mode."""
    # CLI mode doesn't use the GUI elements (log_history_deque, app_instance)
    config = load_config()
    settings = config['Settings']
    
    source_dirs_str = settings.get('source_dirs', '')
    target_dir = settings.get('target_dir', '')
    patterns = settings.get('file_patterns', '')
    
    try:
        interval = int(settings.get('interval_minutes', '5'))
    except ValueError:
        print(f"[{datetime.now().strftime(TIME_FORMAT)}] CRITICAL ERROR: Invalid interval_minutes value in config.ini. Using default: 5.")
        interval = 5

    if not all([source_dirs_str, target_dir, interval > 0]):
        print(f"[{datetime.now().strftime(TIME_FORMAT)}] CRITICAL ERROR: Missing configuration values in config.ini (Source Dir, Target Dir, or Interval). Please run without --cli to use the GUI and configure settings first.")
        sys.exit(1)

    print("-" * 50)
    print(f"[{datetime.now().strftime(TIME_FORMAT)}] Starting Copy Utility in CLI Mode")
    print(f"  > Source(s): {source_dirs_str}")
    print(f"  > Target:    {target_dir}")
    print(f"  > Patterns:  {patterns}")
    print(f"  > Interval:  Every {interval} minutes")
    print("-" * 50)
    print("Press Ctrl+C to stop the scheduler.")
    
    def job_wrapper():
        # Pass None for GUI arguments in CLI mode
        interval_copy_files(source_dirs_str, target_dir, patterns, None, None)
        
    job_wrapper() 
    schedule.every(interval).minutes.do(job_wrapper)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n" + "=" * 50)
            print(f"[{datetime.now().strftime(TIME_FORMAT)}] Scheduler stopped by user (Ctrl+C).")
            print("=" * 50)
            break
        except Exception as e:
            print(f"[{datetime.now().strftime(TIME_FORMAT)}] An unexpected error occurred in the scheduler loop: {e}")
            time.sleep(5)


# --- GUI Logic (tkinter) ---

def run_gui():
    """Initializes and runs the tkinter GUI."""
    
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        from tkinter.scrolledtext import ScrolledText 
        from tkinter import ttk # REQUIRED FOR Treeview
    except ImportError:
        print("ERROR: tkinter or tkinter.ttk is required for the GUI mode but could not be imported.")
        print("Please ensure your Python installation includes tkinter.")
        sys.exit(1)

    class App(tk.Frame):
        def __init__(self, master=None):
            super().__init__(master)
            self.master = master
            self.master.title("Interval File Copy Utility (Multi-Source, Logged)")
            self.pack(padx=10, pady=10, fill=tk.BOTH, expand=True) # Allow frame to expand
            
            self.config = load_config()
            self.job = None 
            self.is_running = False
            
            # Deque for log history, initialized once
            self.log_history = LOG_HISTORY 
            
            self.create_widgets()
            self.load_settings()
            
            # Initial load of any existing log data is complex, so we start the GUI log empty.

        def create_widgets(self):
            # Configure grid weights to allow resizing
            self.master.grid_columnconfigure(0, weight=1)
            self.master.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=1)
            self.grid_rowconfigure(8, weight=1) # Row for the treeview

            # --- Settings Section ---
            # Row 0: Source Dirs
            tk.Label(self, text=f"Source Dirs (1 per line or ; separated, use '{PATH_SEP_HINT}'):").grid(row=0, column=0, sticky="nw", pady=2)
            self.source_text = ScrolledText(self, width=60, height=4)
            self.source_text.grid(row=0, column=1, columnspan=2, pady=2, sticky="ew")
            
            # Row 1: Target Directory
            tk.Label(self, text=f"Target Root Dir (use '{PATH_SEP_HINT}'):").grid(row=1, column=0, sticky="w", pady=2)
            self.target_var = tk.StringVar()
            tk.Entry(self, textvariable=self.target_var, width=60).grid(row=1, column=1, pady=2, sticky="ew")
            tk.Button(self, text="Browse", command=lambda: self.browse_dir(self.target_var)).grid(row=1, column=2, padx=5, pady=2)

            # Row 2: Interval
            tk.Label(self, text="Interval (minutes):").grid(row=2, column=0, sticky="w", pady=2)
            self.interval_var = tk.StringVar()
            tk.Entry(self, textvariable=self.interval_var, width=10).grid(row=2, column=1, sticky="w", pady=2)
            
            # Row 3: File Patterns
            tk.Label(self, text="File Patterns (*.ext;...):").grid(row=3, column=0, sticky="w", pady=2)
            self.patterns_var = tk.StringVar()
            tk.Entry(self, textvariable=self.patterns_var, width=60).grid(row=3, column=1, pady=2, sticky="ew")

            # Row 4: Control Buttons
            self.control_button_var = tk.StringVar(value="Start Copy")
            self.control_button = tk.Button(self, textvariable=self.control_button_var, command=self.toggle_copy_job)
            self.control_button.grid(row=4, column=0, columnspan=3, pady=10)
            
            # Row 5: Save Settings
            tk.Button(self, text="Save Settings", command=self.save_settings).grid(row=5, column=0, columnspan=3, pady=5)
            
            # Row 6: Status
            self.status_var = tk.StringVar(value="Status: Ready")
            tk.Label(self, textvariable=self.status_var).grid(row=6, column=0, columnspan=3, sticky="w", pady=5)
            
            # --- Treeview Display Section ---
            
            # Row 7: Log Header
            tk.Label(self, text=f"Last {LOG_HISTORY_LIMIT} Copy Events:").grid(row=7, column=0, columnspan=3, sticky="w", pady=5)
            
            # Frame for Treeview and Scrollbar
            tree_frame = ttk.Frame(self)
            tree_frame.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
            tree_frame.grid_rowconfigure(0, weight=1)
            tree_frame.grid_columnconfigure(0, weight=1)

            # Create Treeview
            self.log_tree = ttk.Treeview(tree_frame, columns=TREE_COLUMNS, show='headings', height=10)
            
            # Configure Columns
            self.log_tree.column("#0", width=0, stretch=tk.NO) # Hide the default Tree column
            self.log_tree.column("Time", width=70, minwidth=60, stretch=tk.NO, anchor=tk.CENTER)
            self.log_tree.column("File Name", width=150, minwidth=100, stretch=tk.YES)
            self.log_tree.column("Source Path", width=250, minwidth=150, stretch=tk.YES)
            self.log_tree.column("Target Path", width=250, minwidth=150, stretch=tk.YES)
            self.log_tree.column("Status", width=120, minwidth=80, stretch=tk.YES)
            
            # Configure Headings
            for col in TREE_COLUMNS:
                self.log_tree.heading(col, text=col, anchor=tk.W)
            
            self.log_tree.grid(row=0, column=0, sticky="nsew")

            # Add Scrollbar
            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.log_tree.yview)
            self.log_tree.configure(yscrollcommand=vsb.set)
            vsb.grid(row=0, column=1, sticky='ns')
            
            # Configure Style Tag for highlighting errors
            style = ttk.Style(self)
            style.configure("Error.Treeview", foreground="red")
            
        def browse_dir(self, var):
            """Opens a directory selection dialog."""
            directory = filedialog.askdirectory()
            if directory:
                var.set(directory)

        def get_source_dirs_from_text(self):
            """Converts the Text widget content into a semi-colon separated string."""
            content = self.source_text.get("1.0", tk.END).strip()
            source_dirs = ';'.join([d.strip() for line in content.splitlines() for d in line.split(';') if d.strip()])
            return source_dirs

        def load_settings(self):
            """Loads settings from the loaded config object."""
            settings = self.config['Settings']
            self.source_text.delete("1.0", tk.END)
            source_dirs_display = settings.get('source_dirs', '').replace(';', '\n')
            self.source_text.insert("1.0", source_dirs_display)
            
            self.target_var.set(settings.get('target_dir', ''))
            self.interval_var.set(settings.get('interval_minutes', '5'))
            self.patterns_var.set(settings.get('file_patterns', '*.txt;*.log'))
            
        def save_settings(self):
            """Collects and saves settings."""
            try:
                source_dirs_str = self.get_source_dirs_from_text()
                target = self.target_var.get()
                interval = int(self.interval_var.get())
                patterns = self.patterns_var.get()
                
                if not all([source_dirs_str, target, interval > 0, patterns]):
                    messagebox.showerror("Error", "All fields must be filled, and interval must be a positive number.")
                    return

                save_config(source_dirs_str, target, interval, patterns)
                messagebox.showinfo("Success", f"Settings saved successfully to {CONFIG_FILE}.")
                
            except ValueError:
                messagebox.showerror("Error", "Interval must be a valid number.")

        def update_log_display(self):
            """Clears and re-populates the Treeview with the current log_history."""
            
            # Clear existing items
            for item in self.log_tree.get_children():
                self.log_tree.delete(item)
            
            # Insert new items from the deque (which is already limited to 100)
            for row in self.log_history:
                # row is: [Time, File Name, Source Path, Target Path, Status]
                
                tags = ()
                # Apply error highlighting tag
                if row[4].startswith("ERROR"): 
                    tags = ('Error',)
                
                # Insert row at the beginning (index 0)
                self.log_tree.insert('', 0, values=row, tags=tags)
                
        def run_copy_wrapper(self):
            """Wrapper for the copy function to run within the schedule."""
            source_dirs_str = self.get_source_dirs_from_text()
            target = self.target_var.get()
            patterns = self.patterns_var.get()
            
            self.status_var.set(f"Status: Copying...")
            self.master.update()
            
            # Pass the deque and self (App instance) to the core copy logic
            interval_copy_files(source_dirs_str, target, patterns, self.log_history, self)
            
            self.status_var.set(f"Status: Running (Next in {self.interval_var.get()} min)")
        
        def toggle_copy_job(self):
            """Starts or stops the scheduled copy job."""
            
            if self.is_running:
                # Stop the job
                schedule.clear(self.job)
                self.is_running = False
                self.control_button_var.set("Start Copy")
                self.status_var.set("Status: Stopped")
                print("Copy job stopped.")
            else:
                # Start the job
                try:
                    source_dirs_str = self.get_source_dirs_from_text()
                    target = self.target_var.get()
                    interval = int(self.interval_var.get())
                    
                    if not all([source_dirs_str, target, interval > 0]):
                        messagebox.showerror("Error", "Please fill in valid Source(s), Target, and Interval fields first.")
                        return

                    # Run immediately, then schedule
                    self.run_copy_wrapper() 
                    self.job = schedule.every(interval).minutes.do(self.run_copy_wrapper)
                    
                    self.is_running = True
                    self.control_button_var.set("Stop Copy")
                    self.status_var.set(f"Status: Running (Next in {interval} min)")
                    print(f"Copy job started, running every {interval} minutes.")
                    
                    self.master.after(1000, self.check_schedule) 
                    
                except ValueError:
                    messagebox.showerror("Error", "Interval must be a valid number.")
                
        def check_schedule(self):
            """Checks the schedule and runs pending jobs."""
            if self.is_running:
                schedule.run_pending()
                self.master.after(1000, self.check_schedule) 

    root = tk.Tk()
    app = App(master=root)
    root.mainloop()

# --- Main Execution ---

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description=f"Interval File Copy Utility (Time: 2025-09-26 13:23:25 +07)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '--cli', 
        action='store_true', 
        help="Run the application in command line mode (loads config/config.ini and starts the scheduled job)."
    )
    # Hint for PyInstaller (as requested)
    parser.add_argument(
        '--hiden-import', 
        action='store_true', 
        help="Hint for PyInstaller: additional modules to include are 'tkinter', 'configparser', 'schedule', 'os', 'shutil', 'time', 'datetime', 'csv', 'tkinter.ttk'."
    )
    
    args = parser.parse_args()
    
    if args.cli:
        run_cli_mode()
    else:
        # Default behavior: run GUI
        run_gui()