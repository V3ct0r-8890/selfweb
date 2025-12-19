#!/usr/bin/env python3
# 2025-09-24 11:36:00

"""
Port Status Checker, CIDR Calculator & Traceroute GUI Tool

This tool provides a graphical user interface with three main functions:
1. Continuous Network Test: Checks the status of TCP ports and performs ICMP ping tests
   on a list of hosts. It displays the response time in milliseconds for each check.
2. CIDR Calculator: Calculates network details (network address, netmask, host range) for any given CIDR.
3. Traceroute: Maps the network path from the local machine to a specified destination.

Usage:
  python3 combined_network_tool.py [--help]

Parameters:
  --help             Display this help message and exit.

Input Format:
  Network Test: Enter one host per line.
  - For an ICMP ping test only: simply enter the host (e.g., '10.17.100.1').
  - For a port check with or without ping: use the format 'hostname or IP:port1,port2,ping'.
    The 'ping' flag explicitly enables an ICMP ping check for that host.
  - CIDR notation from /24 to /32 is supported for host entries. The script will automatically
    calculate the network's start IP and scan the full range.
  - Host range notation (e.g., '192.168.1.10-20') is also supported.
  
  Example:
    10.17.100.21-22:33128
    10.100.8.201-202:33128
    10.17.100.189-191:ping,80
    8.8.8.8

  CIDR Calculator: Enter a single IP address with its CIDR prefix (e.g., 192.168.1.50/24).
  
  Traceroute: Enter a single hostname or IP address to trace.

Log Output Format:
  The log file, located in the 'logs' directory, is a continuously appended
  file. The log file name will be formatted as network_check_<machine_name>_<yy-mm-dd>.<ext>,
  where <ext> is based on the selected log type (csv or md). CSV is the default format.
  The column headers are written only when a new log file is created.
    - Check Time:      (timestamp)
    - Source IP:       (local machine's IP)
    - Host:Port:       (host and port)
    - Status:          (status)
    - Response (ms):   (response time in milliseconds)

PyInstaller Notes:
  To build an executable, use the following command to ensure all necessary modules are included.
  This is required because some modules are not automatically detected by PyInstaller.
  
  Command:
    pyinstaller --onefile --windowed --hidden-import=icmplib --hidden-import=ipaddress your_script.py
  
  Note: On Windows, you might also need to add --hidden-import=pydivert for the ICMP ping functionality.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import socket
import os
import sys
import ipaddress
import subprocess
import math
from icmplib import ping

# --- User Configuration ---
# Log file directory
LOG_DIR = "logs"
# Max lines to keep in the on-screen output buffer
MAX_OUTPUT_LINES = 1024
# Default hosts to populate the network test input box
DEFAULT_HOSTS_AND_PORTS = """10.17.100.21-22:33128
10.100.8.201-202:33128
10.17.100.189-191:ping,80
"""
# Maximum number of devices to check at once
# MAX_DEVICES = 255 # for SE
MAX_DEVICES = 20 # for users

class NetworkToolGUI(tk.Tk):
    """
    Main GUI application class for the combined network tool.
    """
    def __init__(self):
        super().__init__()

        # Handle --help command-line argument
        if "--help" in sys.argv:
            messagebox.showinfo("Combined Network Tool Help", self.__doc__)
            self.destroy()
            return

        self.title("Network Test & CIDR Calculator")
        self.geometry("800x600")
        self.checking = False
        self.check_thread = None

        self.interval = tk.IntVar()
        self.client_name = tk.StringVar(value=socket.gethostname())
        self.log_file_path = ""
        self.output_buffer_lock = threading.Lock()
        self.current_hosts_count = 0
        self.log_file_type = tk.StringVar(value="csv")
        self.traceroute_thread = None

        # Get local IP address
        try:
            self.source_ip = socket.gethostbyname(socket.gethostname())
        except socket.error:
            self.source_ip = "127.0.0.1"

        self._create_widgets()

        # Populate with default values and set initial interval
        self.network_test_input.insert("1.0", DEFAULT_HOSTS_AND_PORTS)
        self.update_interval()

    def _create_widgets(self):
        """Creates and lays out the GUI widgets."""
        main_notebook = ttk.Notebook(self)
        main_notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # --- Network Test Tab ---
        network_test_frame = ttk.Frame(main_notebook)
        main_notebook.add(network_test_frame, text="Network Test")

        control_frame = ttk.Frame(network_test_frame, padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(control_frame, text=f"Enter Host:Port List (max {MAX_DEVICES} devices):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.network_test_input = tk.Text(control_frame, height=5, width=60)
        self.network_test_input.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        self.network_test_input.bind("<KeyRelease>", self.update_interval)
        
        ttk.Label(control_frame, text="Check Interval (s):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(control_frame, textvariable=self.interval, width=10).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        self.countdown_label = ttk.Label(control_frame, text="Countdown: N/A", font=('Arial', 8, 'italic'))
        self.countdown_label.grid(row=2, column=2, padx=15, pady=5, sticky="w")

        ttk.Label(control_frame, text="Log File Type:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        log_type_combo = ttk.Combobox(control_frame, textvariable=self.log_file_type, state="readonly", width=10)
        log_type_combo['values'] = ('csv', 'md')
        log_type_combo.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        # Action Buttons
        ttk.Button(control_frame, text="Load & Start Check", command=self.start_check).grid(row=4, column=0, padx=5, pady=5)
        ttk.Button(control_frame, text="Stop Check", command=self.stop_check).grid(row=4, column=1, padx=5, pady=5)
        ttk.Button(control_frame, text="Open Logfile Location", command=self.open_logfile_location).grid(row=4, column=2, padx=5, pady=5)
        
        # Frame to hold output text and scrollbar
        output_frame = ttk.Frame(network_test_frame)
        output_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        font_style = ("Consolas", 10) if sys.platform == "win32" else ("Courier New", 10)
        
        self.output_text = tk.Text(output_frame, wrap=tk.NONE, font=font_style, state=tk.DISABLED)
        self.scrollbar = ttk.Scrollbar(output_frame, command=self.output_text.yview)
        
        self.output_text.config(yscrollcommand=self.scrollbar.set)
        
        self.output_text.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure color tags
        self.output_text.tag_configure("green", foreground="green")
        self.output_text.tag_configure("red", foreground="red")
        self.output_text.tag_configure("title", foreground="blue", font=(font_style[0], font_style[1], "bold"))
        self.output_text.tag_configure("header", foreground="gray", font=(font_style[0], font_style[1], "bold"))

        # --- CIDR Calculator Tab ---
        cidr_calc_frame = ttk.Frame(main_notebook)
        main_notebook.add(cidr_calc_frame, text="CIDR Calculator")

        calc_control_frame = ttk.Frame(cidr_calc_frame, padding="10")
        calc_control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(calc_control_frame, text="Enter IP Address with CIDR:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.cidr_input = ttk.Entry(calc_control_frame, width=30)
        self.cidr_input.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Button(calc_control_frame, text="Calculate", command=self.on_calculate_cidr_click).grid(row=0, column=2, padx=5, pady=5)
        
        self.cidr_output_text = tk.Text(cidr_calc_frame, wrap=tk.NONE, font=font_style, height=10, state=tk.DISABLED)
        self.cidr_output_text.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        
        # --- Traceroute Tab ---
        traceroute_frame = ttk.Frame(main_notebook)
        main_notebook.add(traceroute_frame, text="Traceroute")
        
        traceroute_control_frame = ttk.Frame(traceroute_frame, padding="10")
        traceroute_control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(traceroute_control_frame, text="Enter Hostname or IP to trace:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.traceroute_input = ttk.Entry(traceroute_control_frame, width=30)
        self.traceroute_input.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        self.run_traceroute_button = ttk.Button(traceroute_control_frame, text="Run Traceroute", command=self.start_traceroute)
        self.run_traceroute_button.grid(row=0, column=2, padx=5, pady=5)
        
        self.stop_traceroute_button = ttk.Button(traceroute_control_frame, text="Stop Traceroute", command=self.stop_traceroute, state=tk.DISABLED)
        self.stop_traceroute_button.grid(row=0, column=3, padx=5, pady=5)
        
        traceroute_output_frame = ttk.Frame(traceroute_frame)
        traceroute_output_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        self.traceroute_output_text = tk.Text(traceroute_output_frame, wrap=tk.NONE, font=font_style, state=tk.DISABLED)
        self.traceroute_scrollbar = ttk.Scrollbar(traceroute_output_frame, command=self.traceroute_output_text.yview)
        
        self.traceroute_output_text.config(yscrollcommand=self.traceroute_scrollbar.set)
        
        self.traceroute_output_text.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.traceroute_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_interval(self, event=None):
        """Dynamically calculates and updates the default interval based on host count."""
        input_data = self.network_test_input.get("1.0", tk.END).strip()
        try:
            parsed_hosts = self._parse_input(input_data)
            self.current_hosts_count = sum(len(h['hosts']) for h in parsed_hosts)
            
            # Calculate and round up the interval to the nearest 5 seconds
            new_interval = self.current_hosts_count * 3
            new_interval = max(10, new_interval) # Ensure minimum of 10s
            rounded_interval = math.ceil(new_interval / 5) * 5
            self.interval.set(rounded_interval)
        except ValueError:
            pass

    def _initialize_log(self):
        """Creates the log directory and initializes the log file with headers based on the selected type."""
        os.makedirs(LOG_DIR, exist_ok=True)
        
        client_name = self.client_name.get()
        log_type = self.log_file_type.get()
        date_str = time.strftime('%y-%m-%d')
        sanitized_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '_', '-')).rstrip().replace(' ', '_').replace('.', '-')
        
        if sanitized_name:
            log_file_name = f"network_check_{sanitized_name}_{date_str}.{log_type}"
        else:
            log_file_name = f"network_check_{date_str}.{log_type}"

        self.log_file_path = os.path.join(LOG_DIR, log_file_name)

        if not os.path.exists(self.log_file_path):
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                if log_type == "md":
                    f.write("# Continuous Port Check Report\n\n")
                    f.write(f"Date started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Client Name: {client_name}\n")
                    f.write(f"Check interval: {self.interval.get()} seconds\n\n")
                    f.write("| Check Time           | Source IP            | Host:Port                 | Status       | Response |\n")
                    f.write("| :------------------- | :------------------- | :------------------------ | :----------- | :------- |\n")
                elif log_type == "csv":
                    f.write("Check Time,Source IP,Host:Port,Status,Response (ms)\n")

    def _log_and_display_result(self, check_timestamp, host_port_str, status_text, response_time_ms, is_success):
        """Appends a new line to the on-screen display and the log file, with an optional tag for coloring."""
        
        # Format for on-screen display (Markdown)
        on_screen_output = f"| {check_timestamp: <20} |  {self.source_ip: <19} | {host_port_str: <25} | {status_text: <10} | {response_time_ms: >6.2f}ms |"
        tag = "green" if is_success else "red"

        # Format for log file based on selected type
        log_type = self.log_file_type.get()
        if log_type == "csv":
            log_output = f'"{check_timestamp}","{self.source_ip}","{host_port_str}","{status_text.replace("✅ ", "").replace("❌ ", "").replace("⚠️ ", "")}","{response_time_ms:.2f}"'
        else: # Markdown
            log_output = on_screen_output

        with self.output_buffer_lock:
            # Append to log file
            with open(self.log_file_path, "a", encoding="utf-8") as log_file:
                log_file.write(log_output + "\n")

            # Update GUI text widget
            self.output_text.config(state=tk.NORMAL)
            self.output_text.insert(tk.END, on_screen_output + "\n", tag)
            
            # Check and trim buffer if necessary
            current_lines = int(self.output_text.index('end-1c').split('.')[0])
            if current_lines > MAX_OUTPUT_LINES:
                lines_to_delete = current_lines - MAX_OUTPUT_LINES
                self.output_text.delete('1.0', f'{lines_to_delete}.0')

            self.output_text.see(tk.END) # Auto-scroll to the end
            self.output_text.config(state=tk.DISABLED)

    def _update_cidr_output(self, text):
        """Updates the CIDR calculator text widget."""
        self.cidr_output_text.config(state=tk.NORMAL)
        self.cidr_output_text.delete("1.0", tk.END)
        self.cidr_output_text.insert(tk.END, text)
        self.cidr_output_text.config(state=tk.DISABLED)
        
    def _update_traceroute_output(self, text):
        """Updates the traceroute text widget."""
        self.traceroute_output_text.config(state=tk.NORMAL)
        self.traceroute_output_text.delete("1.0", tk.END)
        self.traceroute_output_text.insert(tk.END, text)
        self.traceroute_output_text.config(state=tk.DISABLED)
        
    def _append_traceroute_output(self, text, tag=None):
        """Appends text to the traceroute output widget."""
        self.traceroute_output_text.config(state=tk.NORMAL)
        self.traceroute_output_text.insert(tk.END, text, tag)
        self.traceroute_output_text.see(tk.END)
        self.traceroute_output_text.config(state=tk.DISABLED)

    def start_check(self):
        """Starts the continuous port checking process in a new thread."""
        if self.checking:
            messagebox.showinfo("Info", "Check is already running.")
            return

        input_data = self.network_test_input.get("1.0", tk.END).strip()
        if not input_data:
            messagebox.showerror("Error", "Input list cannot be empty.")
            return

        try:
            self.parsed_hosts = self._parse_input(input_data)
        except ValueError as e:
            messagebox.showerror("Configuration Error", str(e))
            return
        
        self.current_hosts_count = sum(len(h['hosts']) for h in self.parsed_hosts)
        if self.current_hosts_count > MAX_DEVICES:
            messagebox.showerror("Limit Exceeded", f"Total number of devices ({self.current_hosts_count}) exceeds the limit of {MAX_DEVICES}. Please reduce the host list.")
            return

        self.checking = True
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)
        
        self._initialize_log()
        
        # Display initial headers on screen
        markdown_header =  "| Check Time           | Source IP            | Host:Port                 | Status       | Response |\n"
        markdown_header += "| :------------------- | :------------------- | :------------------------ | :----------- | :------- |"
        
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, "\n*** Starting continuous port check... ***\n", "title")
        self.output_text.insert(tk.END, markdown_header + "\n", "header")
        self.output_text.config(state=tk.DISABLED)

        self.check_thread = threading.Thread(target=self._run_check_loop, daemon=True)
        self.check_thread.start()

    def _parse_input(self, data):
        """Parses the host/port list from the input text box, including CIDR."""
        parsed_list = []
        for line in data.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            ports_list = []
            do_ping = False
            
            if ':' in line:
                host_str, ports_str = line.split(':', 1)
                ports_and_flags = [p.strip() for p in ports_str.split(',')]
                
                if 'ping' in ports_and_flags:
                    do_ping = True
                
                ports_list = [int(p) for p in ports_and_flags if p.isdigit()]
            else:
                host_str = line
                do_ping = True
            
            if '/' in host_str:
                hosts = self._expand_cidr(host_str)
            elif '-' in host_str:
                hosts = self._expand_ip_range(host_str)
            else:
                hosts = [host_str]
            
            parsed_list.append({'hosts': hosts, 'ports': ports_list, 'ping': do_ping})
        
        return parsed_list

    def stop_check(self):
        """Stops the continuous port checking process."""
        if not self.checking:
            messagebox.showinfo("Info", "Check is not running.")
            return
        self.checking = False
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, "\n*** Stopping check. Please wait for the current loop to finish. ***\n", "title")
        self.output_text.config(state=tk.DISABLED)
        self.countdown_label.config(text="Countdown: N/A")
        
    def open_logfile_location(self):
        """Opens the log file's directory and selects the file."""
        if not os.path.exists(self.log_file_path):
            messagebox.showinfo("Info", f"Log file not found: {self.log_file_path}")
            return
            
        try:
            if sys.platform == "win32":
                subprocess.run(['explorer', '/select,', self.log_file_path])
            elif sys.platform == "darwin":
                subprocess.run(['open', '-R', self.log_file_path])
            else: # For Linux/other Unix-like systems
                subprocess.run(['xdg-open', LOG_DIR])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open log file location.\nError: {e}")

    def _expand_cidr(self, cidr_str):
        """Expands a /24 to /32 CIDR block into a list of IP addresses."""
        try:
            # Use strict=False to automatically calculate the network address from a host IP
            network = ipaddress.ip_network(cidr_str, strict=False)
            if network.prefixlen < 24 or network.prefixlen > 32:
                raise ValueError(f"CIDR prefix must be between 24 and 32, but got /{network.prefixlen}.")
            return [str(ip) for ip in network.hosts()]
        except ipaddress.AddressValueError as e:
            raise ipaddress.AddressValueError(f"Invalid CIDR notation: {e}")
        except ValueError as e:
            raise e
            
    def _expand_ip_range(self, range_str):
        """Expands an IP range (e.g., 192.168.1.10-20) into a list of IP addresses."""
        try:
            start_str, end_str = range_str.rsplit('-', 1)
            
            # Reconstruct the full end IP if a partial one is given
            if '.' not in end_str:
                parts = start_str.rsplit('.', 1)
                if len(parts) == 2:
                    end_str = f"{parts[0]}.{end_str}"
                else:
                    raise ValueError("Invalid IP range format. Must be full IPs or 'X.Y.Z.A-B'.")

            start_ip = ipaddress.ip_address(start_str)
            end_ip = ipaddress.ip_address(end_str)
            
            if start_ip > end_ip:
                raise ValueError("Start IP cannot be greater than end IP.")
            
            ip_list = []
            current_ip = start_ip
            while current_ip <= end_ip:
                ip_list.append(str(current_ip))
                current_ip += 1
            
            return ip_list
        except (ValueError, ipaddress.AddressValueError) as e:
            raise ValueError(f"Invalid IP range format: '{range_str}'\nError: {e}")

    def _check_port(self, host, port):
        """Checks if a single TCP port is open with a 1-second timeout."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect((host, port))
            return True, "OPEN"
        except socket.timeout:
            return False, "TIMEOUT"
        except ConnectionRefusedError:
            return False, "CLOSED"
        except Exception:
            return False, "ERROR"

    def _run_check_loop(self):
        """The main loop that runs in a separate thread to perform checks."""
        while self.checking:
            check_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            for entry in self.parsed_hosts:
                if not self.checking:
                    break
                hosts = entry['hosts']
                ports = entry['ports']
                do_ping = entry['ping']
                
                for host in hosts:
                    if not self.checking:
                        break
                    
                    if do_ping:
                        try:
                            # Use icmplib for ICMP ping
                            host_result = ping(host, count=1, timeout=1)
                            is_up = host_result.is_alive
                            response_time_ms = host_result.avg_rtt
                            
                            status = "✅ UP" if is_up else "❌ DOWN"
                            self._log_and_display_result(check_timestamp, host, status, response_time_ms, is_up)

                            if not is_up and ports:
                                # Skip port checks if the host is down
                                continue

                        except Exception as e:
                            self._log_and_display_result(check_timestamp, host, "❌ ERROR", 0.0, False)
                            continue

                    for port in ports:
                        if not self.checking:
                            break
                        
                        start_time = time.perf_counter()
                        is_open, status_reason = self._check_port(host, port)
                        end_time = time.perf_counter()
                        response_time_ms = (end_time - start_time) * 1000

                        if status_reason == "OPEN":
                            status = "✅ OPEN"
                        elif status_reason == "TIMEOUT":
                            status = "❌ TIMEOUT"
                        else:
                            status = "❌ CLOSED"
                        
                        host_port_str = f"{host}:{port}"
                        
                        self._log_and_display_result(check_timestamp, host_port_str, status, response_time_ms, is_open)
            
            if self.checking:
                interval = self.interval.get()
                
                # Countdown timer loop
                for i in range(interval, 0, -1):
                    if not self.checking:
                        break
                    self.countdown_label.config(text=f"Countdown: {i}s")
                    time.sleep(1)
                self.countdown_label.config(text="Countdown: N/A")
            
            time.sleep(0.5) # Small buffer before next check loop

    def on_calculate_cidr_click(self):
        """Calculates CIDR details and updates the display."""
        input_cidr = self.cidr_input.get().strip()
        if not input_cidr:
            self._update_cidr_output("Please enter a valid IP address with a CIDR prefix.")
            return

        network_ip, netmask, first_ip, last_ip = self._calculate_network_address(input_cidr)
        
        if network_ip:
            output = f"Input:           {input_cidr}\n"
            output += f"Network Address: {network_ip}\n"
            output += f"Netmask:         {netmask}\n"
            output += f"Usable Host Range: {first_ip} - {last_ip}\n"
            self._update_cidr_output(output)
        else:
            self._update_cidr_output(f"Error: Invalid IP or CIDR notation provided: {input_cidr}")

    def _calculate_network_address(self, ip_with_cidr):
        """Calculates network details from a CIDR string."""
        try:
            network = ipaddress.ip_network(ip_with_cidr, strict=False)
            network_address = str(network.network_address)
            netmask = str(network.netmask)
            
            hosts = list(network.hosts())
            first_host = str(hosts[0]) if hosts else 'N/A'
            last_host = str(hosts[-1]) if hosts else 'N/A'
            
            return network_address, netmask, first_host, last_host
        except ValueError:
            return None, None, None, None
            
    def start_traceroute(self):
        """Initiates the traceroute in a new thread."""
        target = self.traceroute_input.get().strip()
        if not target:
            messagebox.showerror("Error", "Please enter a hostname or IP address.")
            return

        # Disable buttons and clear output while running
        self.run_traceroute_button.config(state=tk.DISABLED)
        self.stop_traceroute_button.config(state=tk.NORMAL)
        self._update_traceroute_output("Tracing route...\n\n")

        self.traceroute_thread = threading.Thread(target=self._run_traceroute_process, args=(target,), daemon=True)
        self.traceroute_thread.start()

    def stop_traceroute(self):
        """Stops the traceroute process."""
        if self.traceroute_thread and self.traceroute_thread.is_alive():
            # This is a bit of a hack, but it's the simplest way to kill the subprocess
            # as there is no clean way to do it cross-platform.
            self.traceroute_process.terminate()
            self.traceroute_thread = None
            self.run_traceroute_button.config(state=tk.NORMAL)
            self.stop_traceroute_button.config(state=tk.DISABLED)
            self._append_traceroute_output("\n\nTraceroute stopped by user.\n")

    def _run_traceroute_process(self, target):
        """Runs the system traceroute command and displays the output."""
        try:
            if sys.platform == "win32":
                command = ["tracert", "-d", target]
            else:
                command = ["traceroute", "-n", target]
                
            self.traceroute_process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                universal_newlines=True
            )
            
            for line in iter(self.traceroute_process.stdout.readline, ''):
                if line:
                    self._append_traceroute_output(line)
            
            self.traceroute_process.wait()
            
            # Check for errors
            if self.traceroute_process.returncode != 0:
                stderr_output = self.traceroute_process.stderr.read()
                self._append_traceroute_output(f"\nError running traceroute:\n{stderr_output}", "red")

        except FileNotFoundError:
            self._append_traceroute_output(
                "\nError: Traceroute command not found. Please ensure 'tracert' (Windows) or 'traceroute' (Linux/macOS) is installed and in your system PATH.\n",
                "red"
            )
        except Exception as e:
            self._append_traceroute_output(f"\nAn unexpected error occurred: {e}", "red")
        
        finally:
            self.run_traceroute_button.config(state=tk.NORMAL)
            self.stop_traceroute_button.config(state=tk.DISABLED)


if __name__ == "__main__":
    app = NetworkToolGUI()
    if app.winfo_exists():
        app.mainloop()
