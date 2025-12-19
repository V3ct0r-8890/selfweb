#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interval File Copy/Archiving Utility (Scheduled and Logged)
Generated on: 2025-09-26 15:52:21 +07

*** SPECIFICATIONS AND BEHAVIOR ***
- Purpose: Automatically process files (copy/move or archive/move) from multiple source directories 
  to a structured target location at a configurable interval.
- **GUI Layout:** Fixed size 700x650, non-resizable, with a compact control section.
- **Compact Controls:** 'Start Operation' and 'Save Settings' buttons are on the same line.
- **Configurable Log Prefix (log_prefix):** The prefix for daily log files (e.g., 'se-arch_log_YYMMDD.csv') 
  can now be adjusted in the configuration file. Default is 'se-arch_log_'.
- **Unique Config File:** Default config file name is 'se-arch.ini'.
- **Alternate Config Option:** Supports --config-file <path> to specify a non-default configuration.
- **Configurable Log Directory (log_dir):** All log files and the se-arch.ini (or custom INI) are 
  stored in the directory specified by the 'log_dir' setting inside the config file.
- **Next Action Countdown:** A real-time countdown (in seconds) is displayed in both CLI and GUI modes.
- **Action Parameter:** Determines if files are copied ('copy', default) or moved ('move').
- **Move/Delete Logic:** If 'move' is selected, files are deleted from the source upon successful transfer/archiving.
- **Age-Based Deletion (Move + Archive):** When moving with the 'archive' mode, files are only removed from the 
  source if their modification time is older than the specified threshold (Min: 30 days).
- **Interval Constraints:** Minimum: 0.5 minutes (30 seconds), Default: 5 minutes, Maximum: 60 minutes.
- **Log Header:** ['run date / time', 'source folder', 'source file name', 'target folder (archived file name)', 'status / error message']
- **Recursive Processing:** Uses os.walk() to include files within subfolders.

Usage:
  python interval_copy_util.py                                   (Runs the GUI using default se-arch.ini)
  python interval_copy_util.py --cli                             (Runs scheduled job using default se-arch.ini)
  python interval_copy_util.py --config-file /path/to/my.ini --cli
                                                                 (Runs scheduled job using a specific config file)
  python interval_copy_util.py --help -h                         (Show this help message and exit)

Options:
  --cli            Run the application in command line mode (loads config and starts the scheduled job).
  --config-file <path>
                   Specify an alternate configuration file path (e.g., C:\Configs\test.ini).
  --mode {copy,archive}
                   Overrides the mode specified in the configuration file.
  --action {copy,move}
                   Overrides the action (copy or move) specified in the configuration file.
  --help, -h       Show this help message and exit.
  --hiden-import   This hint is for PyInstaller: additional modules to include 
                   are 'tkinter', 'configparser', 'schedule', 'os', 'shutil', 'time', 'datetime', 'csv', 'tkinter.ttk', 'tarfile', 'fnmatch'.
"""

import sys
import os
import shutil
import time
import argparse
import configparser
import csv
import tarfile 
from datetime import datetime, timedelta
from collections import deque, defaultdict 
import fnmatch 

# Non-standard module needed:
# If 'schedule' is missing, install it with: pip install schedule
try:
    import schedule
except ImportError:
    print("Error: The 'schedule' module is not installed.")
    print("Please install it using: pip install schedule")
    sys.exit(1)

# --- Configuration Constants ---
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_HISTORY_LIMIT = 100 

# --- UNIQUE CONFIG NAME ---
CONFIG_FILE_NAME = 'se-arch.ini'
DEFAULT_CONFIG_PATH = os.path.join('.', 'config') 
DEFAULT_LOG_PREFIX = 'se-arch_log_'
# ---------------------------

# Global variable to hold the determined LOG_DIR path
GLOBAL_LOG_DIR = None
# Global variable to hold the actual CONFIG_FILE path being used (might not be default)
GLOBAL_CONFIG_FILE_PATH = None
# Global variable to hold the log prefix, set after config is loaded
GLOBAL_LOG_PREFIX = DEFAULT_LOG_PREFIX 

# --- INTERVAL CONSTANTS ---
MIN_INTERVAL_MINUTES = 0.5  # 30 seconds
DEFAULT_INTERVAL_MINUTES = 5 
MAX_INTERVAL_MINUTES = 60 

# --- DELETION CONSTANTS (for 'move' action) ---
MIN_DELETE_AGE_DAYS = 30
DEFAULT_DELETE_AGE_DAYS = 30

# --- LOG HEADERS ---
LOG_HEADER = ['run date / time', 'source folder', 'source file name', 'target folder (archived file name)', 'status / error message']
TREE_COLUMNS = ['Time', 'Source File Name', 'Source Path', 'Target Path/Archive', 'Status'] 

IS_WINDOWS = os.name == 'nt'
PATH_SEP_HINT = os.sep 

# Time structure formats
COPY_TIME_SUBDIR_FORMAT = f'%Y{os.sep}%m{os.sep}%d{os.sep}%H'
ARCHIVE_TIME_SUBDIR_FORMAT = f'%Y{os.sep}%m'

# Global Deque for log history
LOG_HISTORY = deque(maxlen=LOG_HISTORY_LIMIT)

# --- Core Logic ---

def configure_paths(alt_config_path=None, log_dir_override=None):
    """
    Determines the path of the config file and the log directory (GLOBAL_LOG_DIR).
    It ensures the log directory exists and updates the global path variables.
    Returns the final, determined config file path.
    """
    global GLOBAL_LOG_DIR
    global GLOBAL_CONFIG_FILE_PATH

    # 1. Determine the path to the configuration file (se-arch.ini or alternate)
    if alt_config_path:
        # Use the explicit alternate path
        config_file_path = os.path.normpath(os.path.abspath(alt_config_path))
    else:
        # Use the default path: ./config/se-arch.ini
        config_file_path = os.path.join(DEFAULT_CONFIG_PATH, CONFIG_FILE_NAME)
        config_file_path = os.path.normpath(os.path.abspath(config_file_path))
        
    GLOBAL_CONFIG_FILE_PATH = config_file_path
    
    # 2. Determine the path for the log directory (where config is stored/read from)
    if log_dir_override:
        # Override takes precedence
        GLOBAL_LOG_DIR = os.path.normpath(os.path.abspath(log_dir_override))
    elif GLOBAL_LOG_DIR is None:
        # First time call: Try to read log_dir from the config file itself
        temp_config = configparser.ConfigParser()
        
        if os.path.exists(config_file_path):
            try:
                temp_config.read(config_file_path)
                custom_log_dir = temp_config['Settings'].get('log_dir')
                
                if custom_log_dir and os.path.isabs(custom_log_dir):
                    GLOBAL_LOG_DIR = os.path.normpath(custom_log_dir)
                else:
                    # If log_dir is not absolute or missing, use the directory containing the config file
                    GLOBAL_LOG_DIR = os.path.dirname(config_file_path)
            except Exception:
                # Fallback if config is corrupted, use the directory containing the config file
                GLOBAL_LOG_DIR = os.path.dirname(config_file_path)
        else:
            # If config file doesn't exist, use its intended directory as the log_dir
            GLOBAL_LOG_DIR = os.path.dirname(config_file_path)

    # 3. Ensure the determined log directory exists
    os.makedirs(GLOBAL_LOG_DIR, exist_ok=True)
    
    return GLOBAL_CONFIG_FILE_PATH

def load_config(alt_config_path=None):
    """Loads configuration from the determined config file path and sets GLOBAL_LOG_PREFIX."""
    global GLOBAL_LOG_PREFIX
    
    # Determine the configuration file path (and the GLOBAL_LOG_DIR)
    config_file_path = configure_paths(alt_config_path)
    
    config = configparser.ConfigParser()
    default_interval_str = str(DEFAULT_INTERVAL_MINUTES)
    default_delete_age_str = str(DEFAULT_DELETE_AGE_DAYS)
    
    # The default log_dir is the path determined by configure_paths based on the config location
    default_log_dir = os.path.dirname(config_file_path)
    
    default_settings = {
        'source_dirs': '', 
        'target_dir': '',
        'interval_minutes': default_interval_str,
        'file_patterns': '*.*', 
        'mode': 'copy',
        'action': 'copy', 
        'delete_files_older_than_days': default_delete_age_str,
        'log_dir': default_log_dir,
        'log_prefix': DEFAULT_LOG_PREFIX
    }

    # Load from file or initialize with defaults
    if not os.path.exists(config_file_path):
        config['Settings'] = default_settings
        # If config file doesn't exist, we need to save the path that should be used for the first run
    else:
        config.read(config_file_path)
        
        if 'Settings' not in config:
             config['Settings'] = {}

        # Ensure all default settings are present in the loaded config
        for key, default_val in default_settings.items():
            if key not in config['Settings']:
                 config['Settings'][key] = default_val

    # Re-check for a custom log_dir setting in the loaded config
    current_log_dir_in_file = config['Settings'].get('log_dir')
    
    # Update GLOBAL_LOG_PREFIX from the loaded or default config
    GLOBAL_LOG_PREFIX = config['Settings'].get('log_prefix', DEFAULT_LOG_PREFIX)
    
    # If the log_dir in the file is different from what was globally set by the file's location,
    # we need to reconfigure the paths (only updating GLOBAL_LOG_DIR).
    if current_log_dir_in_file and os.path.normpath(current_log_dir_in_file) != GLOBAL_LOG_DIR:
        
        # Just update the GLOBAL_LOG_DIR path and ensure it exists.
        configure_paths(alt_config_path=alt_config_path, log_dir_override=current_log_dir_in_file)
        
    return config

def save_config(source_dirs, target_dir, interval_minutes, file_patterns, mode, action, delete_age_days, log_dir, log_prefix):
    """Saves the current configuration to the config file path (GLOBAL_CONFIG_FILE_PATH)."""
    global GLOBAL_LOG_PREFIX
    
    if not GLOBAL_CONFIG_FILE_PATH:
        print("CRITICAL ERROR: Configuration file path not initialized.")
        return
    
    # Update global paths based on what the user wants to save
    configure_paths(alt_config_path=GLOBAL_CONFIG_FILE_PATH, log_dir_override=log_dir)
    GLOBAL_LOG_PREFIX = log_prefix # Update the global prefix for immediate use
    
    config = configparser.ConfigParser()
    config['Settings'] = {
        'source_dirs': source_dirs,
        'target_dir': target_dir,
        'interval_minutes': str(interval_minutes),
        'file_patterns': file_patterns,
        'mode': mode,
        'action': action, 
        'delete_files_older_than_days': str(delete_age_days), 
        'log_dir': log_dir, 
        'log_prefix': log_prefix, 
    }
    
    try:
        with open(GLOBAL_CONFIG_FILE_PATH, 'w') as configfile:
            config.write(configfile)
        
        print(f"Configuration saved to {GLOBAL_CONFIG_FILE_PATH}")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not save configuration to {GLOBAL_CONFIG_FILE_PATH}: {e}")

def write_log_entry(data_row, log_history_deque=None, app_instance=None):
    """Writes a single row to the CSV log file and updates the in-memory history."""
    
    # Use the global log directory and prefix for the daily log file
    LOG_DIR = GLOBAL_LOG_DIR if GLOBAL_LOG_DIR else DEFAULT_CONFIG_PATH
    LOG_PREFIX = GLOBAL_LOG_PREFIX if GLOBAL_LOG_PREFIX else DEFAULT_LOG_PREFIX
        
    # LOG_FILE_DAILY now uses the GLOBAL_LOG_PREFIX
    LOG_FILE_DAILY = os.path.join(LOG_DIR, f'{LOG_PREFIX}{datetime.now().strftime("%y%m%d")}.csv')
    file_exists = os.path.exists(LOG_FILE_DAILY)
    
    try:
        # Ensure log directory exists before writing
        os.makedirs(LOG_DIR, exist_ok=True)
        
        with open(LOG_FILE_DAILY, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            
            if not file_exists:
                writer.writerow(LOG_HEADER)
            
            writer.writerow(data_row)
            
    except Exception as e:
        print(f"[{datetime.now().strftime(TIME_FORMAT)}] CRITICAL ERROR writing to log: {e}")

    if log_history_deque is not None:
        # Prepare GUI row based on the new log structure: 
        gui_row = [
            data_row[0].split()[-1], # Time only (from run date / time)
            data_row[2] if data_row[2] else os.path.basename(data_row[3]), # Source File Name or Archive Name
            data_row[1],             # Source Path (folder/dir)
            data_row[3],             # Target Path (file/archive path)
            data_row[4]              # Status / Error Message
        ]
        log_history_deque.appendleft(gui_row) 
        
        if app_instance is not None:
            app_instance.update_log_display()

def remove_source_file(source_path, log_entry, log_history_deque=None, app_instance=None):
    """Safely attempts to remove the source file and updates the log."""
    try:
        os.remove(source_path)
        log_entry[4] += " (MOVED/DELETED)"
        print(f"  - Deleted source file: {source_path}")
        return True
    except Exception as delete_e:
        log_entry[4] += f" (ERROR DELETING SOURCE: {str(delete_e).replace('\n', ' ')})"
        write_log_entry(log_entry, log_history_deque, app_instance)
        print(f"  - ERROR deleting source {source_path}: {delete_e}")
        return False
    
def process_files(source_dirs_str, target_dir, file_patterns, mode, action, delete_age_days, log_history_deque=None, app_instance=None):
    """
    Main function to process files. Handles both 'copy'/'move' and 'copy'/'archive' modes.
    (Function body remains the same as previous version)
    """
    source_dirs = [d.strip() for d in source_dirs_str.split(';') if d.strip()]
    patterns = [p.strip() for p in file_patterns.split(';') if p.strip()] 
    target_dir = os.path.normpath(os.path.abspath(target_dir))
    current_runtime_str = datetime.now().strftime(TIME_FORMAT)
    total_processed_count = 0

    # Determine deletion threshold for archive/move mode
    delete_age_days_int = int(delete_age_days)
    delete_age_threshold = datetime.now() - timedelta(days=delete_age_days_int)
    
    if not source_dirs:
        print(f"[{current_runtime_str}] WARNING: No source directories configured. Skipping operation.")
        return

    print(f"\n\n[{current_runtime_str}] Starting processing: Mode={mode.upper()}, Action={action.upper()}, Delete Age={delete_age_days_int} days (if needed).")
    
    # ----------------------------------------------------
    # --- Collect and Group Files ---
    # ----------------------------------------------------
    file_groups = defaultdict(list)
    files_to_process = set() 
    
    for source_dir in source_dirs:
        source_dir_norm = os.path.normpath(os.path.abspath(source_dir))
        source_name = os.path.basename(source_dir_norm)
        
        if not os.path.isdir(source_dir_norm):
            print(f"[{current_runtime_str}] ERROR: Source directory not found: {source_dir_norm}")
            continue

        source_base_prefix = source_dir_norm.rstrip(os.sep) + os.sep
        
        for root, _, files in os.walk(source_dir_norm):
            rel_sub_path = os.path.relpath(root, source_dir_norm)
            
            for filename in files:
                source_path = os.path.join(root, filename)
                
                if source_path in files_to_process:
                    continue 
                    
                if not any(fnmatch.fnmatch(filename, p) for p in patterns):
                    continue

                try:
                    mod_timestamp = os.path.getmtime(source_path)
                    mod_dt = datetime.fromtimestamp(mod_timestamp)
                    
                    if mode == 'copy':
                        time_segment = mod_dt.strftime(COPY_TIME_SUBDIR_FORMAT)
                        key = (source_dir_norm, time_segment, rel_sub_path)
                    else: # archive mode
                        time_segment = mod_dt.strftime(ARCHIVE_TIME_SUBDIR_FORMAT) 
                        archive_base_name = mod_dt.strftime('%Y%m%d') 
                        key = (source_dir_norm, time_segment, archive_base_name)
                    
                    # Store file data: (source_path, filename, modification_dt, relative_sub_path, mod_timestamp)
                    file_groups[key].append((source_path, filename, mod_dt, rel_sub_path, mod_timestamp))
                    files_to_process.add(source_path)

                except Exception as e:
                    print(f"  - WARNING: Could not get modification time or process {source_path}: {e}")

    # ----------------------------------------------------
    # --- Process Files by Group ---
    # ----------------------------------------------------
    for key, files_to_handle in file_groups.items():
        source_dir_norm = key[0]
        time_segment = key[1]
        
        # --- Copy Mode Execution (Copy/Move) ---
        if mode == 'copy':
            rel_sub_path = key[2]
            source_name = os.path.basename(source_dir_norm)
            final_target_dir = os.path.join(target_dir, source_name, time_segment, rel_sub_path)
            
            for source_path, filename, _, rel_sub_path, _ in files_to_handle:
                target_path = os.path.join(final_target_dir, filename)
                log_entry = [current_runtime_str, source_path, filename, target_path, ""]

                try:
                    os.makedirs(final_target_dir, exist_ok=True)
                    shutil.copy2(source_path, target_path) 
                    
                    log_entry[4] = "SUCCESS (Copied)"
                    
                    if action == 'move':
                        # In copy mode + move, we delete regardless of age
                        remove_source_file(source_path, log_entry, log_history_deque, app_instance)
                        
                    write_log_entry(log_entry, log_history_deque, app_instance)
                    
                    print_source = os.path.join(rel_sub_path, filename) if rel_sub_path != '.' else filename
                    print(f"  - {action.title()}: {print_source} -> {target_path}")
                    total_processed_count += 1
                    
                except Exception as e:
                    error_msg = str(e).replace('\n', ' ')
                    log_entry[4] = f"ERROR ({action.title()} failed): {error_msg}"
                    write_log_entry(log_entry, log_history_deque, app_instance)
                    print(f"  - ERROR processing {source_path}: {error_msg}")

        # --- Archive Mode Execution (Archive/Archive & Move) ---
        elif mode == 'archive':
            archive_base_name = key[2] 
            source_name = os.path.basename(source_dir_norm)
            archive_filename = f"{archive_base_name}.tar"
            base_target_dir = os.path.join(target_dir, source_name, time_segment)
            archive_path = os.path.join(base_target_dir, archive_filename)
            
            os.makedirs(base_target_dir, exist_ok=True)
            
            tar_mode = "a" if os.path.exists(archive_path) else "w"
            action_desc = "Appending" if tar_mode == "a" else "Creating"
            print(f"[{current_runtime_str.split()[-1]}] {action_desc} archive: {archive_path}")
            
            files_added_count = 0
            
            try:
                with tarfile.open(archive_path, tar_mode) as tar:
                    files_in_archive = {m.name for m in tar.getmembers()} if tar_mode == 'a' else set()
                    
                    for source_path, filename, mod_dt, rel_sub_path, mod_timestamp in files_to_handle:
                        arcname = os.path.relpath(source_path, start=source_dir_norm)
                        file_log_entry = [current_runtime_str, source_path, filename, archive_path, ""] 

                        if arcname in files_in_archive:
                            file_log_entry[4] = "SKIPPED (Already in archive)"
                            write_log_entry(file_log_entry, log_history_deque, app_instance)
                            continue 
                        
                        try:
                            # 1. Add to archive
                            tarinfo = tar.gettarinfo(source_path, arcname=arcname)
                            tarinfo.mtime = mod_timestamp 
                            
                            with open(source_path, 'rb') as f:
                                tar.addfile(tarinfo, f)
                                
                            file_log_entry[4] = "SUCCESS (Archived)"
                            files_added_count += 1
                            total_processed_count += 1
                            
                            # 2. Handle 'move' logic for archiving
                            if action == 'move':
                                if mod_dt < delete_age_threshold:
                                    remove_source_file(source_path, file_log_entry, log_history_deque, app_instance)
                                else:
                                    file_log_entry[4] += f" (Move SKIPPED, not older than {delete_age_days_int} days)"

                            write_log_entry(file_log_entry, log_history_deque, app_instance)
                            
                        except Exception as file_e:
                            file_error_msg = str(file_e).replace('\n', ' ')
                            file_log_entry[4] = f"ERROR (Archiving failed): {file_error_msg}"
                            write_log_entry(file_log_entry, log_history_deque, app_instance)
                            print(f"  - ERROR archiving {filename}: {file_error_msg}")

                if files_added_count > 0:
                    print(f"  - Successfully completed {action_desc.lower()} {files_added_count} files to: {archive_path}")

            except Exception as e:
                error_msg = str(e).replace('\n', ' ')
                critical_log_entry = [current_runtime_str, source_dir_norm, archive_filename, archive_path, f"CRITICAL ERROR (Archive Failed): {error_msg}"]
                write_log_entry(critical_log_entry, log_history_deque, app_instance)
                print(f"  - CRITICAL ERROR during archiving {source_dir_norm}: {error_msg}")
            
    print(f"[{current_runtime_str}] Operation run complete. Total items processed/archived: {total_processed_count}")

# --- CLI Mode Implementation (Unchanged from v5) ---

def run_cli_mode(alt_config_path=None, cli_mode_override=None, cli_action_override=None):
    """Loads config, sets up the schedule, and runs the infinite loop for CLI mode."""
    
    config = load_config(alt_config_path)
    settings = config['Settings']
    
    source_dirs_str = settings.get('source_dirs', '')
    target_dir = settings.get('target_dir', '')
    patterns = settings.get('file_patterns', '')
    
    mode = cli_mode_override if cli_mode_override in ('copy', 'archive') else settings.get('mode', 'copy')
    action = cli_action_override if cli_action_override in ('copy', 'move') else settings.get('action', 'copy')
    
    try:
        interval = float(settings.get('interval_minutes', DEFAULT_INTERVAL_MINUTES))
        if not MIN_INTERVAL_MINUTES <= interval <= MAX_INTERVAL_MINUTES:
            raise ValueError("Interval out of range.")
            
        delete_age_days = int(settings.get('delete_files_older_than_days', DEFAULT_DELETE_AGE_DAYS))
        if delete_age_days < MIN_DELETE_AGE_DAYS:
            raise ValueError("Delete age too low.")

    except ValueError as e:
        print(f"[{datetime.now().strftime(TIME_FORMAT)}] CRITICAL ERROR: Invalid configuration value. Defaulting values.")
        interval = DEFAULT_INTERVAL_MINUTES
        delete_age_days = DEFAULT_DELETE_AGE_DAYS

    if not all([source_dirs_str, target_dir, interval > 0]):
        print(f"[{datetime.now().strftime(TIME_FORMAT)}] CRITICAL ERROR: Missing configuration values.")
        sys.exit(1)

    print("-" * 50)
    print(f"[{datetime.now().strftime(TIME_FORMAT)}] Starting Utility in CLI Mode")
    print(f"  > Config File: {GLOBAL_CONFIG_FILE_PATH}")
    print(f"  > Log Prefix:  {GLOBAL_LOG_PREFIX}")
    print(f"  > Operation: {mode.upper()} / {action.upper()}")
    print(f"  > Log Directory: {GLOBAL_LOG_DIR}")
    print(f"  > Delete Age (Move/Archive): {delete_age_days} days")
    print(f"  > Interval:  Every {interval} minutes")
    print("-" * 50)
    print("Press Ctrl+C to stop the scheduler.")
    
    def job_wrapper():
        process_files(source_dirs_str, target_dir, patterns, mode, action, delete_age_days, None, None)
        # Re-print status line after job is complete
        print(f"\n[{datetime.now().strftime(TIME_FORMAT)}] Job complete. Next run status:")
        
    job_wrapper() 
    schedule.every(interval).minutes.do(job_wrapper)
    
    while True:
        try:
            # Get idle seconds and convert to integer seconds
            idle_secs = int(schedule.idle_seconds())
            
            # Use carriage return to overwrite the current line
            sys.stdout.write(f"\rNext action in: {idle_secs:4d} seconds. Status: Idle.")
            sys.stdout.flush()
            
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            # Clear the status line before exiting
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            sys.stdout.flush()
            print("\n" + "=" * 50)
            print(f"[{datetime.now().strftime(TIME_FORMAT)}] Scheduler stopped by user (Ctrl+C).")
            print("=" * 50)
            break
        except Exception as e:
            print(f"\n[{datetime.now().strftime(TIME_FORMAT)}] An unexpected error occurred in the scheduler loop: {e}")
            time.sleep(5)


# --- GUI Logic (Updated for Fixed Size and Compact Layout) ---

def run_gui(alt_config_path=None):
    """Initializes and runs the tkinter GUI."""
    
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        from tkinter.scrolledtext import ScrolledText 
        from tkinter import ttk 
    except ImportError:
        print("ERROR: tkinter or tkinter.ttk is required for the GUI mode but could not be imported.")
        sys.exit(1)

    class App(tk.Frame):
        def __init__(self, master=None):
            super().__init__(master)
            self.master = master
            self.master.title("Interval File Copy/Archiving Utility")
            
            # --- FIXED SIZE AND NON-RESIZABLE ---
            self.master.geometry("700x650") 
            self.master.resizable(False, False)
            # ------------------------------------
            
            self.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
            
            self.alt_config_path = alt_config_path
            self.config = load_config(self.alt_config_path)
            self.job = None 
            self.is_running = False
            self.log_history = LOG_HISTORY 
            self.current_job_status = "Ready" 
            
            self.create_widgets()
            self.load_settings()

        def create_widgets(self):
            # Configure grid weights (only needed for internal layout, master remains non-resizable)
            self.grid_columnconfigure(1, weight=1)
            # The Treeview frame row will consume the remaining space (but constrained by 650 height)
            self.grid_rowconfigure(13, weight=1) 

            current_row = 0
            
            # Row 0: Config File Path Display
            tk.Label(self, text="Using Config File:").grid(row=current_row, column=0, sticky="w", pady=2)
            self.config_path_var = tk.StringVar(value=GLOBAL_CONFIG_FILE_PATH)
            tk.Label(self, textvariable=self.config_path_var, fg="blue").grid(row=current_row, column=1, columnspan=2, sticky="w", padx=10)
            current_row += 1
            
            # Row 1: Operation Mode (Copy/Archive)
            tk.Label(self, text="Operation Mode:").grid(row=current_row, column=0, sticky="w", pady=2)
            self.mode_var = tk.StringVar()
            self.mode_var.set(self.config['Settings'].get('mode', 'copy'))
            ttk.Radiobutton(self, text="Copy (file-by-file)", variable=self.mode_var, value='copy').grid(row=current_row, column=1, sticky="w", padx=10)
            ttk.Radiobutton(self, text="Archive (.tar, Day-based)", variable=self.mode_var, value='archive').grid(row=current_row, column=2, sticky="w", padx=10)
            current_row += 1
            
            # Row 2: Action (Copy/Move)
            tk.Label(self, text="Action:").grid(row=current_row, column=0, sticky="w", pady=2)
            self.action_var = tk.StringVar()
            self.action_var.set(self.config['Settings'].get('action', 'copy'))
            ttk.Radiobutton(self, text="Copy (Keep Source)", variable=self.action_var, value='copy').grid(row=current_row, column=1, sticky="w", padx=10)
            ttk.Radiobutton(self, text="Move (Delete Source)", variable=self.action_var, value='move').grid(row=current_row, column=2, sticky="w", padx=10)
            current_row += 1
            
            # Row 3: Delete Age (Only relevant for Move + Archive)
            age_label_text = f"Min Delete Age (Days, Move/Archive only, min {MIN_DELETE_AGE_DAYS}):"
            tk.Label(self, text=age_label_text).grid(row=current_row, column=0, sticky="w", pady=2)
            self.delete_age_var = tk.StringVar()
            tk.Entry(self, textvariable=self.delete_age_var, width=10).grid(row=current_row, column=1, sticky="w", pady=2)
            current_row += 1
            
            # Row 4: Source Dirs (Height reduced from 4 to 3 lines)
            tk.Label(self, text=f"Source Dirs (1 per line or ; separated, use '{PATH_SEP_HINT}'):").grid(row=current_row, column=0, sticky="nw", pady=2)
            self.source_text = ScrolledText(self, width=60, height=3) 
            self.source_text.grid(row=current_row, column=1, columnspan=2, pady=2, sticky="ew")
            current_row += 1
            
            # Row 5: Target Directory
            tk.Label(self, text=f"Target Root Dir (use '{PATH_SEP_HINT}'):").grid(row=current_row, column=0, sticky="w", pady=2)
            self.target_var = tk.StringVar()
            tk.Entry(self, textvariable=self.target_var, width=60).grid(row=current_row, column=1, pady=2, sticky="ew")
            tk.Button(self, text="Browse", command=lambda: self.browse_dir(self.target_var)).grid(row=current_row, column=2, padx=5, pady=2)
            current_row += 1

            # Row 6: Interval
            interval_label_text = f"Interval (minutes, {MIN_INTERVAL_MINUTES}-{MAX_INTERVAL_MINUTES}):"
            tk.Label(self, text=interval_label_text).grid(row=current_row, column=0, sticky="w", pady=2)
            self.interval_var = tk.StringVar()
            tk.Entry(self, textvariable=self.interval_var, width=10).grid(row=current_row, column=1, sticky="w", pady=2)
            current_row += 1
            
            # Row 7: File Patterns
            tk.Label(self, text="File Patterns (*.ext;...):").grid(row=current_row, column=0, sticky="w", pady=2)
            self.patterns_var = tk.StringVar()
            tk.Entry(self, textvariable=self.patterns_var, width=60).grid(row=current_row, column=1, pady=2, sticky="ew")
            current_row += 1

            # Row 8: Log Directory
            tk.Label(self, text=f"Log Directory (where logs/config are written):").grid(row=current_row, column=0, sticky="w", pady=2)
            self.log_dir_var = tk.StringVar()
            tk.Entry(self, textvariable=self.log_dir_var, width=60).grid(row=current_row, column=1, pady=2, sticky="ew")
            tk.Button(self, text="Browse", command=lambda: self.browse_dir(self.log_dir_var)).grid(row=current_row, column=2, padx=5, pady=2)
            current_row += 1
            
            # Row 9: Log Prefix
            tk.Label(self, text="Log File Prefix (e.g., 'se-arch_log_'):").grid(row=current_row, column=0, sticky="w", pady=2)
            self.log_prefix_var = tk.StringVar()
            tk.Entry(self, textvariable=self.log_prefix_var, width=30).grid(row=current_row, column=1, sticky="w", pady=2)
            current_row += 1

            # Row 10: Control Buttons (Combined 'Start' and 'Save' on the same line)
            control_frame = ttk.Frame(self)
            control_frame.grid(row=current_row, column=0, columnspan=3, pady=10, sticky="ew")
            control_frame.grid_columnconfigure(0, weight=1)
            control_frame.grid_columnconfigure(1, weight=1)
            
            self.control_button_var = tk.StringVar(value="Start Operation")
            self.control_button = tk.Button(control_frame, textvariable=self.control_button_var, command=self.toggle_copy_job, width=20)
            self.control_button.grid(row=0, column=0, padx=(0, 5), sticky="e")
            
            tk.Button(control_frame, text="Save Settings", command=self.save_settings, width=20).grid(row=0, column=1, padx=(5, 0), sticky="w")
            current_row += 1
            
            # Row 11: Status 
            self.status_var = tk.StringVar(value="Status: Ready")
            self.status_label = tk.Label(self, textvariable=self.status_var)
            self.status_label.grid(row=current_row, column=0, columnspan=3, sticky="w", pady=5)
            current_row += 1
            
            # Row 12: Log Header
            tk.Label(self, text=f"Last {LOG_HISTORY_LIMIT} Events (Source File Name/Archive):").grid(row=current_row, column=0, columnspan=3, sticky="w", pady=5)
            current_row += 1
            
            # Row 13: Treeview Display Section (This will expand vertically to fill the remaining space)
            tree_frame = ttk.Frame(self)
            tree_frame.grid(row=current_row, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
            tree_frame.grid_rowconfigure(0, weight=1)
            tree_frame.grid_columnconfigure(0, weight=1)

            # NOTE: Height is kept default or slightly reduced to fit 650 constraint.
            self.log_tree = ttk.Treeview(tree_frame, columns=TREE_COLUMNS, show='headings') 
            
            # Configure Columns 
            self.log_tree.column("#0", width=0, stretch=tk.NO) 
            self.log_tree.column("Time", width=70, minwidth=60, stretch=tk.NO, anchor=tk.CENTER)
            self.log_tree.column("Source File Name", width=160, minwidth=100, stretch=tk.YES) 
            self.log_tree.column("Source Path", width=160, minwidth=100, stretch=tk.YES)
            self.log_tree.column("Target Path/Archive", width=160, minwidth=100, stretch=tk.YES) 
            self.log_tree.column("Status", width=100, minwidth=70, stretch=tk.YES)
            
            for col in TREE_COLUMNS:
                self.log_tree.heading(col, text=col.replace(" Name", ""), anchor=tk.W)
            
            self.log_tree.grid(row=0, column=0, sticky="nsew")

            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.log_tree.yview)
            self.log_tree.configure(yscrollcommand=vsb.set)
            vsb.grid(row=0, column=1, sticky='ns')
            
            style = ttk.Style(self)
            style.configure("Error.Treeview", foreground="red")
            
        def browse_dir(self, var):
            directory = filedialog.askdirectory()
            if directory:
                var.set(directory)

        def get_source_dirs_from_text(self):
            content = self.source_text.get("1.0", tk.END).strip()
            source_dirs = ';'.join([d.strip() for line in content.splitlines() for d in line.split(';') if d.strip()])
            return source_dirs

        def load_settings(self):
            settings = self.config['Settings']
            self.source_text.delete("1.0", tk.END)
            source_dirs_display = settings.get('source_dirs', '').replace(';', '\n')
            self.source_text.insert("1.0", source_dirs_display)
            
            self.target_var.set(settings.get('target_dir', ''))
            self.interval_var.set(settings.get('interval_minutes', str(DEFAULT_INTERVAL_MINUTES))) 
            self.patterns_var.set(settings.get('file_patterns', '*.*'))
            self.mode_var.set(settings.get('mode', 'copy'))
            self.action_var.set(settings.get('action', 'copy'))
            self.delete_age_var.set(settings.get('delete_files_older_than_days', str(DEFAULT_DELETE_AGE_DAYS)))
            self.log_dir_var.set(GLOBAL_LOG_DIR) 
            self.log_prefix_var.set(GLOBAL_LOG_PREFIX) 
            self.config_path_var.set(GLOBAL_CONFIG_FILE_PATH)
            
        def save_settings(self):
            try:
                source_dirs_str = self.get_source_dirs_from_text()
                target = self.target_var.get()
                interval = float(self.interval_var.get())
                delete_age_days = int(self.delete_age_var.get())
                patterns = self.patterns_var.get()
                mode = self.mode_var.get()
                action = self.action_var.get()
                log_dir = self.log_dir_var.get()
                log_prefix = self.log_prefix_var.get()
                
                # Validation
                if not MIN_INTERVAL_MINUTES <= interval <= MAX_INTERVAL_MINUTES:
                    messagebox.showerror("Error", f"Interval must be between {MIN_INTERVAL_MINUTES} and {MAX_INTERVAL_MINUTES} minutes.")
                    return
                if delete_age_days < MIN_DELETE_AGE_DAYS:
                    messagebox.showerror("Error", f"Minimum delete age for archived files must be {MIN_DELETE_AGE_DAYS} days.")
                    return
                if not all([source_dirs_str, target, patterns, log_dir, log_prefix]):
                    messagebox.showerror("Error", "All configuration fields must be filled.")
                    return

                # Save the config (this updates the GLOBAL_LOG_DIR and GLOBAL_LOG_PREFIX)
                save_config(source_dirs_str, target, interval, patterns, mode, action, delete_age_days, log_dir, log_prefix)
                messagebox.showinfo("Success", f"Settings saved successfully to {GLOBAL_CONFIG_FILE_PATH}.")
                
            except ValueError:
                messagebox.showerror("Error", "Interval and Delete Age must be valid numbers.")

        def update_log_display(self):
            """Clears and re-populates the Treeview with the current log_history."""
            
            for item in self.log_tree.get_children():
                self.log_tree.delete(item)
            
            for row in self.log_history:
                tags = ()
                if row[4].startswith("ERROR") or row[4].startswith("CRITICAL") or "(ERROR DELETING SOURCE:" in row[4]: 
                    tags = ('Error',)
                
                self.log_tree.insert('', 0, values=row, tags=tags)
                
        def run_copy_wrapper(self):
            """Wrapper for the copy function to run within the schedule."""
            source_dirs_str = self.get_source_dirs_from_text()
            target = self.target_var.get()
            patterns = self.patterns_var.get()
            mode = self.mode_var.get()
            action = self.action_var.get()
            
            try:
                delete_age_days = int(self.delete_age_var.get())
            except ValueError:
                messagebox.showerror("Error", "Delete Age must be a valid integer.")
                return

            # Set base status to 'Processing...'
            self.current_job_status = f"Processing ({mode.upper()}/{action.upper()})..."
            self.status_var.set(self.current_job_status)
            self.master.update()
            
            process_files(source_dirs_str, target, patterns, mode, action, delete_age_days, self.log_history, self)
            
            # Set base status to 'Running' after job completion
            self.current_job_status = f"Running ({mode.upper()}/{action.upper()} Mode)"
        
        def toggle_copy_job(self):
            """Starts or stops the scheduled copy job."""
            
            if self.is_running:
                schedule.clear() # Clear all jobs just to be safe
                self.is_running = False
                self.control_button_var.set("Start Operation")
                self.current_job_status = "Stopped"
                self.status_var.set(f"Status: {self.current_job_status}")
                print("Operation job stopped.")
            else:
                try:
                    source_dirs_str = self.get_source_dirs_from_text()
                    target = self.target_var.get()
                    interval = float(self.interval_var.get())
                    delete_age_days = int(self.delete_age_var.get())
                    mode = self.mode_var.get()
                    action = self.action_var.get()
                    log_dir = self.log_dir_var.get()
                    log_prefix = self.log_prefix_var.get()

                    # Basic input validation before starting
                    if not MIN_INTERVAL_MINUTES <= interval <= MAX_INTERVAL_MINUTES:
                        messagebox.showerror("Error", f"Interval must be between {MIN_INTERVAL_MINUTES} and {MAX_INTERVAL_MINUTES} minutes.")
                        return
                    if delete_age_days < MIN_DELETE_AGE_DAYS:
                         messagebox.showerror("Error", f"Minimum delete age for archived files must be {MIN_DELETE_AGE_DAYS} days.")
                         return
                    if not all([source_dirs_str, target, log_dir, log_prefix]):
                        messagebox.showerror("Error", "Please fill in valid Source(s), Target, Log Directory, and Log Prefix fields first.")
                        return

                    # Important: Update the GLOBAL_LOG_DIR and GLOBAL_LOG_PREFIX immediately before the job starts
                    configure_paths(alt_config_path=GLOBAL_CONFIG_FILE_PATH, log_dir_override=log_dir)
                    global GLOBAL_LOG_PREFIX
                    GLOBAL_LOG_PREFIX = log_prefix
                    
                    # Run immediately, then schedule
                    self.run_copy_wrapper() 
                    self.job = schedule.every(interval).minutes.do(self.run_copy_wrapper)
                    
                    self.is_running = True
                    self.control_button_var.set("Stop Operation")
                    # Set base status to be updated by check_schedule
                    self.current_job_status = f"Running ({mode.upper()}/{action.upper()} Mode)"
                    print(f"Operation job started in {mode.upper()}/{action.upper()} mode, running every {interval} minutes.")
                    
                    self.master.after(100, self.check_schedule) # Start the countdown loop
                    
                except ValueError:
                    messagebox.showerror("Error", f"Interval and Delete Age must be valid numbers.")
                
        def check_schedule(self):
            """Checks the schedule, runs pending jobs, and updates the countdown."""
            if self.is_running:
                schedule.run_pending()
                
                # Update countdown only if not actively processing
                if not self.current_job_status.startswith("Processing"):
                    next_run_time = schedule.next_run()
                    if next_run_time:
                        time_until_next = (next_run_time - datetime.now()).total_seconds()
                        if time_until_next > 0:
                            countdown_sec = int(time_until_next)
                            self.status_var.set(f"Status: {self.current_job_status} | Next Run in: {countdown_sec} seconds")
                        else:
                            # Should happen rarely, if job is overdue
                            self.status_var.set(f"Status: {self.current_job_status} | Next Run: Due Now")
                    else:
                        self.status_var.set(f"Status: {self.current_job_status} | No Next Job Scheduled")
                
                self.master.after(1000, self.check_schedule) # Rerun every 1 second

    root = tk.Tk()
    app = App(master=root)
    root.mainloop()

# --- Main Execution ---

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description=f"Interval File Copy/Archiving Utility (Time: 2025-09-26 15:52:21 +07)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '--cli', 
        action='store_true', 
        help="Run the application in command line mode (loads config and starts the scheduled job)."
    )
    parser.add_argument(
        '--config-file', 
        type=str,
        default=None,
        help=f"Specify an alternate configuration file path. Default is ./config/{CONFIG_FILE_NAME}."
    )
    parser.add_argument(
        '--mode', 
        choices=['copy', 'archive'],
        default=None,
        help="Overrides the mode specified in the configuration file."
    )
    parser.add_argument(
        '--action', 
        choices=['copy', 'move'],
        default=None,
        help="Overrides the action specified in the configuration file."
    )
    # Hint for PyInstaller (as requested)
    parser.add_argument(
        '--hiden-import', 
        action='store_true', 
        help="Hint for PyInstaller: additional modules to include are 'tkinter', 'configparser', 'schedule', 'os', 'shutil', 'time', 'datetime', 'csv', 'tkinter.ttk', 'tarfile', 'fnmatch'."
    )
    
    args = parser.parse_args()
    
    # Configure paths first, respecting the command line argument
    configure_paths(alt_config_path=args.config_file) 
    
    cli_mode = args.mode
    cli_action = args.action
    
    if args.cli:
        run_cli_mode(args.config_file, cli_mode, cli_action)
    else:
        # Default behavior: run GUI, passing the alternate config path if provided
        run_gui(args.config_file)