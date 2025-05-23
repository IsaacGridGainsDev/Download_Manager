"""
TorrentLite - Python File Download Manager
Sprint 2: Enhanced Download Engine

Enhanced single-threaded download engine with better progress tracking,
server capability detection, and improved error handling.

Author: TorrentLite Team
Version: 1.1.0
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import threading
from typing import Optional, Dict, Any, Tuple
import requests
from urllib.parse import urlparse
import time
import tempfile
import shutil
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

# Set CustomTkinter appearance and color theme
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class TorrentLiteColors:
    """Color constants for the application"""
    WOOD_BROWN = "#A97449"
    SEA_BLUE = "#0277BD"
    BACKGROUND = "#FFFFFF"
    TEXT_PRIMARY = "#2C3E50"
    TEXT_SECONDARY = "#7F8C8D"
    SUCCESS_GREEN = "#27AE60"
    ERROR_RED = "#E74C3C"
    WARNING_ORANGE = "#F39C12"
    LIGHT_GRAY = "#ECF0F1"

class ServerCapabilities:
    """Represents server download capabilities"""
    
    def __init__(self):
        self.supports_range_requests = False
        self.supports_head_requests = False
        self.content_length = 0
        self.content_type = ""
        self.filename = ""
        self.server_info = ""
        self.last_modified = None
        self.accept_ranges = ""
        
    def __str__(self):
        return (f"Range Support: {self.supports_range_requests}, "
                f"Size: {self.content_length}, "
                f"Type: {self.content_type}")

class DownloadTask:
    """Enhanced download task with detailed tracking"""
    
    def __init__(self, url: str, save_path: str, segments: int = 1):
        self.url = url
        self.save_path = save_path
        self.segments = segments
        self.status = "Pending"  # Pending, Analyzing, Downloading, Paused, Complete, Error
        self.progress = 0.0
        self.speed = 0.0
        self.eta = "Unknown"
        self.file_size = 0
        self.downloaded_bytes = 0
        self.start_time = None
        self.error_message = ""
        self.temp_file = None
        
        # Enhanced tracking
        self.server_capabilities = ServerCapabilities()
        self.retry_count = 0
        self.max_retries = 3
        self.last_error = None
        self.download_history = []  # Speed history for smoother calculations
        self.pause_requested = False
        self.cancel_requested = False
        
    def get_filename(self) -> str:
        """Extract filename from URL or path with enhanced detection"""
        # Try to get from server capabilities first
        if self.server_capabilities.filename:
            return self.server_capabilities.filename
            
        # Get from save path
        if os.path.basename(self.save_path):
            return os.path.basename(self.save_path)
        
        # Extract from URL
        parsed_url = urlparse(self.url)
        filename = os.path.basename(parsed_url.path)
        
        # If no filename in URL, generate one
        if not filename or filename == "/":
            filename = f"download_{int(time.time())}"
            
        return filename
    
    def get_temp_filename(self) -> str:
        """Generate temporary filename"""
        filename = self.get_filename()
        name, ext = os.path.splitext(filename)
        return f"{name}.torrentlite_tmp{ext}"

class UIManager:
    """Enhanced UI with better feedback and controls"""
    
    def __init__(self, download_manager):
        self.download_manager = download_manager
        self.setup_main_window()
        self.create_widgets()
        self.start_ui_updater()
        
    def setup_main_window(self):
        """Initialize the main application window"""
        self.root = ctk.CTk()
        self.root.title("TorrentLite v1.1 - Enhanced Download Manager")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Configure grid weights for responsive design
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)  # Download panel row
        
    def create_widgets(self):
        """Create and arrange all UI widgets"""
        self.create_header()
        self.create_input_section()
        self.create_download_panel()
        self.create_footer()
        
    def create_header(self):
        """Create the application header with version info"""
        header_frame = ctk.CTkFrame(self.root, fg_color=TorrentLiteColors.SEA_BLUE)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="🚀 TorrentLite v1.1",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white"
        )
        title_label.grid(row=0, column=0, pady=15)
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Enhanced Multi-Threaded Download Manager • Sprint 2",
            font=ctk.CTkFont(size=12),
            text_color="white"
        )
        subtitle_label.grid(row=1, column=0, pady=(0, 15))
        
    def create_input_section(self):
        """Create enhanced URL input and settings section"""
        input_frame = ctk.CTkFrame(self.root)
        input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        input_frame.grid_columnconfigure(1, weight=1)
        
        # URL input with validation indicator
        url_label = ctk.CTkLabel(input_frame, text="Download URL:")
        url_label.grid(row=0, column=0, padx=(15, 10), pady=(15, 5), sticky="w")
        
        self.url_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Paste your download URL here... (http:// or https://)",
            font=ctk.CTkFont(size=12)
        )
        self.url_entry.grid(row=0, column=1, columnspan=2, padx=(0, 15), pady=(15, 5), sticky="ew")
        self.url_entry.bind("<KeyRelease>", self.on_url_change)
        
        # URL validation indicator
        self.url_status_label = ctk.CTkLabel(
            input_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=TorrentLiteColors.TEXT_SECONDARY
        )
        self.url_status_label.grid(row=0, column=3, padx=(5, 15), pady=(15, 5))
        
        # Save location
        save_label = ctk.CTkLabel(input_frame, text="Save to:")
        save_label.grid(row=1, column=0, padx=(15, 10), pady=5, sticky="w")
        
        self.save_path_var = tk.StringVar(value=os.path.expanduser("~/Downloads"))
        self.save_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.save_path_var,
            font=ctk.CTkFont(size=12)
        )
        self.save_entry.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="ew")
        
        browse_btn = ctk.CTkButton(
            input_frame,
            text="Browse",
            command=self.browse_save_location,
            fg_color=TorrentLiteColors.WOOD_BROWN,
            hover_color="#8B5A2B",
            width=80
        )
        browse_btn.grid(row=1, column=2, padx=(0, 15), pady=5)
        
        # Enhanced settings row
        settings_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        settings_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 15))
        settings_frame.grid_columnconfigure(4, weight=1)
        
        # Segments selector (prepared for Sprint 3)
        segments_label = ctk.CTkLabel(settings_frame, text="Segments:")
        segments_label.grid(row=0, column=0, padx=(15, 10), sticky="w")
        
        self.segments_var = tk.StringVar(value="1")
        segments_combo = ctk.CTkComboBox(
            settings_frame,
            values=["1"],  # Only 1 for Sprint 2
            variable=self.segments_var,
            width=80,
            state="readonly"
        )
        segments_combo.grid(row=0, column=1, padx=(0, 20))
        
        # Retry count
        retry_label = ctk.CTkLabel(settings_frame, text="Max Retries:")
        retry_label.grid(row=0, column=2, padx=(20, 10), sticky="w")
        
        self.retry_var = tk.StringVar(value="3")
        retry_combo = ctk.CTkComboBox(
            settings_frame,
            values=["1", "2", "3", "5", "10"],
            variable=self.retry_var,
            width=80,
            state="readonly"
        )
        retry_combo.grid(row=0, column=3, padx=(0, 20))
        
        # Start button
        self.start_btn = ctk.CTkButton(
            settings_frame,
            text="🚀 Start Download",
            command=self.start_download,
            fg_color=TorrentLiteColors.SEA_BLUE,
            hover_color="#025A8B",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=35
        )
        self.start_btn.grid(row=0, column=5, padx=(0, 15), pady=5, sticky="e")
        
    def create_download_panel(self):
        """Create enhanced download tracking panel"""
        panel_frame = ctk.CTkFrame(self.root)
        panel_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        panel_frame.grid_columnconfigure(0, weight=1)
        panel_frame.grid_rowconfigure(1, weight=1)
        
        # Panel header with stats
        header_frame = ctk.CTkFrame(panel_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(15, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        header_label = ctk.CTkLabel(
            header_frame,
            text="Download Progress",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TorrentLiteColors.TEXT_PRIMARY
        )
        header_label.grid(row=0, column=0, padx=(15, 0), sticky="w")
        
        self.active_downloads_label = ctk.CTkLabel(
            header_frame,
            text="Active: 0",
            font=ctk.CTkFont(size=12),
            text_color=TorrentLiteColors.TEXT_SECONDARY
        )
        self.active_downloads_label.grid(row=0, column=1, padx=(0, 15), sticky="e")
        
        # Scrollable frame for downloads
        self.downloads_frame = ctk.CTkScrollableFrame(panel_frame)
        self.downloads_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.downloads_frame.grid_columnconfigure(0, weight=1)
        
        # Initial empty state
        self.show_empty_state()
        
    def create_footer(self):
        """Create enhanced application footer"""
        footer_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 10))
        footer_frame.grid_columnconfigure(1, weight=1)
        
        # Status info
        self.status_label = ctk.CTkLabel(
            footer_frame,
            text="Ready to download • Enhanced Engine v1.1",
            font=ctk.CTkFont(size=12),
            text_color=TorrentLiteColors.TEXT_SECONDARY
        )
        self.status_label.grid(row=0, column=0, padx=(10, 20), sticky="w")
        
        # Speed and stats
        self.stats_label = ctk.CTkLabel(
            footer_frame,
            text="Downloads: 0 | Total Speed: 0 KB/s | Memory: 0 MB",
            font=ctk.CTkFont(size=12),
            text_color=TorrentLiteColors.TEXT_SECONDARY
        )
        self.stats_label.grid(row=0, column=2, padx=(20, 10), sticky="e")
        
    def on_url_change(self, event):
        """Handle URL input changes for validation"""
        url = self.url_entry.get().strip()
        if not url:
            self.url_status_label.configure(text="", text_color=TorrentLiteColors.TEXT_SECONDARY)
            return
        
        try:
            parsed = urlparse(url)
            if parsed.scheme in ['http', 'https'] and parsed.netloc:
                self.url_status_label.configure(text="✓ Valid", text_color=TorrentLiteColors.SUCCESS_GREEN)
            else:
                self.url_status_label.configure(text="⚠ Invalid", text_color=TorrentLiteColors.WARNING_ORANGE)
        except:
            self.url_status_label.configure(text="✗ Error", text_color=TorrentLiteColors.ERROR_RED)
    
    def show_empty_state(self):
        """Show enhanced empty state"""
        empty_frame = ctk.CTkFrame(self.downloads_frame, fg_color="transparent")
        empty_frame.grid(row=0, column=0, pady=50)
        
        empty_icon = ctk.CTkLabel(
            empty_frame,
            text="📁",
            font=ctk.CTkFont(size=48)
        )
        empty_icon.grid(row=0, column=0, pady=(0, 10))
        
        empty_text = ctk.CTkLabel(
            empty_frame,
            text="No downloads yet\nPaste a URL above to get started!\n\nSprint 2 Features:\n• Enhanced server analysis\n• Better progress tracking\n• Improved error handling",
            font=ctk.CTkFont(size=14),
            text_color=TorrentLiteColors.TEXT_SECONDARY,
            justify="center"
        )
        empty_text.grid(row=1, column=0)
        
    def browse_save_location(self):
        """Enhanced file dialog with better file type detection"""
        current_path = self.save_path_var.get()
        
        if os.path.isdir(current_path):
            initial_dir = current_path
            initial_file = ""
        else:
            initial_dir = os.path.dirname(current_path) or os.path.expanduser("~/Downloads")
            initial_file = os.path.basename(current_path)
        
        file_path = filedialog.asksaveasfilename(
            title="Choose save location",
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[
                ("All Files", "*.*"),
                ("Archives", "*.zip;*.rar;*.7z;*.tar.gz"),
                ("Video Files", "*.mp4;*.avi;*.mkv;*.mov;*.wmv"),
                ("Audio Files", "*.mp3;*.wav;*.flac;*.aac;*.ogg"),
                ("Images", "*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.svg"),
                ("Documents", "*.pdf;*.doc;*.docx;*.txt;*.rtf"),
                ("Software", "*.exe;*.msi;*.dmg;*.deb;*.rpm")
            ]
        )
        
        if file_path:
            self.save_path_var.set(file_path)
    
    def start_download(self):
        """Enhanced download start with validation"""
        url = self.url_entry.get().strip()
        save_path = self.save_path_var.get().strip()
        segments = int(self.segments_var.get())
        max_retries = int(self.retry_var.get())
        
        # Enhanced validation
        if not url:
            messagebox.showerror("Error", "Please enter a download URL")
            return
            
        if not save_path:
            messagebox.showerror("Error", "Please choose a save location")
            return
        
        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Only HTTP and HTTPS URLs are supported")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid URL: {str(e)}")
            return
        
        # Check if save directory exists and is writable
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create directory: {str(e)}")
                return
        
        # Check if file already exists
        if os.path.exists(save_path):
            result = messagebox.askyesno(
                "File Exists", 
                f"File already exists:\n{save_path}\n\nDo you want to overwrite it?"
            )
            if not result:
                return
        
        # Create download task
        task = DownloadTask(url, save_path, segments)
        task.max_retries = max_retries
        
        # Add to download manager
        self.download_manager.add_download(task)
        
        # Update UI
        self.add_download_to_ui(task)
        self.url_entry.delete(0, 'end')
        self.url_status_label.configure(text="")
        self.update_status("Analyzing server capabilities...")
        
    def add_download_to_ui(self, task: DownloadTask):
        """Enhanced download UI with more details"""
        # Clear empty state if this is the first download
        if len(self.download_manager.tasks) == 1:
            for widget in self.downloads_frame.winfo_children():
                widget.destroy()
        
        # Create download item frame
        item_frame = ctk.CTkFrame(self.downloads_frame)
        item_frame.grid(row=len(self.download_manager.tasks) - 1, column=0, sticky="ew", pady=5)
        item_frame.grid_columnconfigure(1, weight=1)
        
        # File info header
        filename = task.get_filename()
        file_info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        file_info_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=15, pady=(15, 5))
        file_info_frame.grid_columnconfigure(1, weight=1)
        
        file_label = ctk.CTkLabel(
            file_info_frame,
            text=f"📄 {filename}",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        file_label.grid(row=0, column=0, sticky="w")
        
        # Status indicator
        status_indicator = ctk.CTkLabel(
            file_info_frame,
            text="🔄 Analyzing...",
            font=ctk.CTkFont(size=12),
            text_color=TorrentLiteColors.WARNING_ORANGE
        )
        status_indicator.grid(row=0, column=1, sticky="e")
        
        # URL display (truncated)
        url_display = task.url if len(task.url) <= 70 else task.url[:70] + "..."
        url_label = ctk.CTkLabel(
            item_frame,
            text=url_display,
            font=ctk.CTkFont(size=10),
            text_color=TorrentLiteColors.TEXT_SECONDARY,
            anchor="w"
        )
        url_label.grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="w")
        
        # Progress section
        progress_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        progress_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 10))
        progress_frame.grid_columnconfigure(0, weight=1)
        
        # Main progress bar
        progress_bar = ctk.CTkProgressBar(
            progress_frame,
            progress_color=TorrentLiteColors.SEA_BLUE
        )
        progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        progress_bar.set(0)
        
        # Progress details
        progress_detail_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        progress_detail_frame.grid(row=1, column=0, sticky="ew")
        progress_detail_frame.grid_columnconfigure(1, weight=1)
        
        # Status and details
        status_label = ctk.CTkLabel(
            progress_detail_frame,
            text="Preparing download...",
            font=ctk.CTkFont(size=12),
            text_color=TorrentLiteColors.TEXT_SECONDARY,
            anchor="w"
        )
        status_label.grid(row=0, column=0, sticky="w")
        
        # Server info label
        server_info_label = ctk.CTkLabel(
            progress_detail_frame,
            text="Server: Unknown",
            font=ctk.CTkFont(size=10),
            text_color=TorrentLiteColors.TEXT_SECONDARY,
            anchor="e"
        )
        server_info_label.grid(row=0, column=1, sticky="e")
        
        # Control buttons frame
        controls_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        controls_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 15))
        
        # Pause button (for future use)
        pause_btn = ctk.CTkButton(
            controls_frame,
            text="⏸ Pause",
            command=lambda: self.pause_download(task),
            fg_color=TorrentLiteColors.WARNING_ORANGE,
            hover_color="#E67E22",
            width=80,
            height=30,
            state="disabled"  # Disabled in Sprint 2
        )
        pause_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Cancel button
        cancel_btn = ctk.CTkButton(
            controls_frame,
            text="✗ Cancel",
            command=lambda: self.cancel_download(task),
            fg_color=TorrentLiteColors.ERROR_RED,
            hover_color="#C0392B",
            width=80,
            height=30
        )
        cancel_btn.grid(row=0, column=1)
        
        # Store references for updates
        task.ui_elements = {
            'frame': item_frame,
            'progress_bar': progress_bar,
            'status_label': status_label,
            'status_indicator': status_indicator,
            'server_info_label': server_info_label,
            'pause_btn': pause_btn,
            'cancel_btn': cancel_btn
        }
    
    def pause_download(self, task: DownloadTask):
        """Handle pause button (Sprint 2 - Basic implementation)"""
        task.pause_requested = True
        messagebox.showinfo("Info", "Pause functionality will be available in Sprint 4")
    
    def cancel_download(self, task: DownloadTask):
        """Handle cancel button"""
        result = messagebox.askyesno(
            "Cancel Download", 
            f"Are you sure you want to cancel downloading:\n{task.get_filename()}?"
        )
        if result:
            task.cancel_requested = True
            if hasattr(task, 'ui_elements'):
                task.ui_elements['status_label'].configure(text="❌ Cancelled by user")
                task.ui_elements['status_indicator'].configure(
                    text="❌ Cancelled",
                    text_color=TorrentLiteColors.ERROR_RED
                )
    
    def start_ui_updater(self):
        """Enhanced UI updater with better performance"""
        def update_ui():
            try:
                # Update active downloads count
                active_count = sum(1 for task in self.download_manager.tasks.values() 
                                 if task.status == "Downloading")
                self.active_downloads_label.configure(text=f"Active: {active_count}")
                
                # Update stats
                total_speed = sum(task.speed for task in self.download_manager.tasks.values() 
                                if task.status == "Downloading")
                total_downloads = len(self.download_manager.tasks)
                
                # Simple memory usage estimation
                memory_mb = total_downloads * 2  # Rough estimate
                
                speed_str = self.download_manager._format_bytes(total_speed) + "/s" if total_speed > 0 else "0 B/s"
                self.stats_label.configure(
                    text=f"Downloads: {total_downloads} | Total Speed: {speed_str} | Memory: {memory_mb} MB"
                )
                
                # Update individual download UI elements
                for task in self.download_manager.tasks.values():
                    if hasattr(task, 'ui_elements'):
                        self.download_manager._update_task_ui(task)
                
            except Exception:
                pass  # Ignore UI update errors
            
            # Schedule next update
            self.root.after(1000, update_ui)
        
        update_ui()
    
    def update_status(self, message: str):
        """Update the footer status message"""
        self.status_label.configure(text=message)
    
    def run(self):
        """Start the application main loop"""
        self.root.mainloop()

class DownloadManager:
    """Enhanced download management with server analysis"""
    
    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_downloads = 0
        
    def add_download(self, task: DownloadTask):
        """Add a new download task with enhanced analysis"""
        task_id = f"{task.url}_{int(time.time())}"
        self.tasks[task_id] = task
        
        # Start download in background thread
        download_thread = threading.Thread(
            target=self._enhanced_download_process,
            args=(task,),
            daemon=True
        )
        download_thread.start()
    
    def _enhanced_download_process(self, task: DownloadTask):
        """Enhanced download process with server analysis"""
        try:
            # Phase 1: Analyze server capabilities
            task.status = "Analyzing"
            self._analyze_server_capabilities(task)
            
            if task.cancel_requested:
                return
            
            # Phase 2: Download file
            task.status = "Downloading"
            self._download_with_retry(task)
            
        except Exception as e:
            task.status = "Error"
            task.error_message = str(e)
            self._update_task_ui(task)
    
    def _analyze_server_capabilities(self, task: DownloadTask):
        """Analyze what the server supports"""
            # First, try a HEAD request to get file info without downloading
        try:
            head_response = requests.head(task.url, timeout=10, allow_redirects=True)
            task.server_capabilities.supports_head_requests = True
            
            # Extract server information
            headers = head_response.headers
            task.server_capabilities.content_length = int(headers.get('content-length', 0))
            task.server_capabilities.content_type = headers.get('content-type', '')
            task.server_capabilities.server_info = headers.get('server', 'Unknown')
            task.server_capabilities.accept_ranges = headers.get('accept-ranges', '')
            task.server_capabilities.supports_range_requests = 'bytes' in task.server_capabilities.accept_ranges.lower()
            
            # Try to extract filename from Content-Disposition header
            content_disposition = headers.get('content-disposition', '')
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"\'')
                task.server_capabilities.filename = filename
                
            # Last modified
            if 'last-modified' in headers:
                task.server_capabilities.last_modified = headers['last-modified']
                
            task.file_size = task.server_capabilities.content_length
            
        except requests.RequestException:
            # If HEAD fails, try a small GET request
            task.server_capabilities.supports_head_requests = False
            get_response = requests.get(task.url, stream=True, timeout=10, headers={'Range': 'bytes=0-1023'})
            
            if get_response.status_code == 206:  # Partial content
                task.server_capabilities.supports_range_requests = True
                content_range = get_response.headers.get('content-range', '')
                if '/' in content_range:
                    total_size = content_range.split('/')[-1]
                    if total_size.isdigit():
                            task.server_capabilities.content_length = int(total_size)
                            task.file_size = int(total_size)
                
                get_response.close()
            
            # Update UI with server info
            if hasattr(task, 'ui_elements'):
                server_info = f"Server: {task.server_capabilities.server_info}"
                if task.server_capabilities.supports_range_requests:
                    server_info += " | Range: ✓"
                else:
                    server_info += " | Range: ✗"
                
                task.ui_elements['server_info_label'].configure(text=server_info)
                
                # Update file size if known
                if task.file_size > 0:
                    size_str = self._format_bytes(task.file_size)
                    task.ui_elements['status_label'].configure(
                        text=f"File size: {size_str} • Ready to download"
                    )
                else:
                    task.ui_elements['status_label'].configure(text="Size unknown • Ready to download")
                
                task.ui_elements['status_indicator'].configure(
                    text="✓ Ready",
                    text_color=TorrentLiteColors.SUCCESS_GREEN
                )
            
        except Exception as e:
            task.error_message = f"Server analysis failed: {str(e)}"
            if hasattr(task, 'ui_elements'):
                task.ui_elements['status_label'].configure(text=f"Analysis error: {str(e)}")
                task.ui_elements['status_indicator'].configure(
                    text="⚠ Error",
                    text_color=TorrentLiteColors.ERROR_RED
                )
    
    def _download_with_retry(self, task: DownloadTask):
        """Download file with retry logic"""
        for attempt in range(task.max_retries + 1):
            if task.cancel_requested:
                return
            
            try:
                task.retry_count = attempt
                if attempt > 0:
                    wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30 seconds
                    if hasattr(task, 'ui_elements'):
                        task.ui_elements['status_label'].configure(
                            text=f"Retrying in {wait_time}s... (Attempt {attempt + 1}/{task.max_retries + 1})"
                        )
                    time.sleep(wait_time)
                
                self._perform_download(task)
                
                # If we get here, download was successful
                task.status = "Complete"
                if hasattr(task, 'ui_elements'):
                    task.ui_elements['status_label'].configure(text="✅ Download completed successfully!")
                    task.ui_elements['status_indicator'].configure(
                        text="✅ Complete",
                        text_color=TorrentLiteColors.SUCCESS_GREEN
                    )
                    task.ui_elements['progress_bar'].set(1.0)
                return
                
            except Exception as e:
                task.last_error = str(e)
                if attempt == task.max_retries:
                    # Final attempt failed
                    task.status = "Error"
                    task.error_message = f"Download failed after {task.max_retries + 1} attempts: {str(e)}"
                    if hasattr(task, 'ui_elements'):
                        task.ui_elements['status_label'].configure(text=f"❌ Failed: {str(e)}")
                        task.ui_elements['status_indicator'].configure(
                            text="❌ Failed",
                            text_color=TorrentLiteColors.ERROR_RED
                        )
                else:
                    # Will retry
                    if hasattr(task, 'ui_elements'):
                        task.ui_elements['status_label'].configure(
                            text=f"Error: {str(e)} • Will retry..."
                        )
    
    def _perform_download(self, task: DownloadTask):
        """Perform the actual download with progress tracking"""
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        temp_filename = task.get_temp_filename()
        task.temp_file = os.path.join(temp_dir, temp_filename)
        
        # Start download
        task.start_time = time.time()
        task.downloaded_bytes = 0
        
        try:
            response = requests.get(task.url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get actual file size from response if not already known
            if task.file_size == 0:
                content_length = response.headers.get('content-length')
                if content_length:
                    task.file_size = int(content_length)
            
            # Download with progress tracking
            with open(task.temp_file, 'wb') as file:
                chunk_size = 8192  # 8KB chunks
                last_update_time = time.time()
                bytes_since_last_update = 0
                
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if task.cancel_requested:
                        response.close()
                        return
                    
                    if chunk:  # Filter out keep-alive chunks
                        file.write(chunk)
                        task.downloaded_bytes += len(chunk)
                        bytes_since_last_update += len(chunk)
                        
                        # Update progress every 0.5 seconds
                        current_time = time.time()
                        if current_time - last_update_time >= 0.5:
                            # Calculate speed
                            time_elapsed = current_time - last_update_time
                            current_speed = bytes_since_last_update / time_elapsed
                            
                            # Smooth speed calculation using history
                            task.download_history.append(current_speed)
                            if len(task.download_history) > 10:  # Keep last 10 measurements
                                task.download_history.pop(0)
                            
                            # Average speed
                            task.speed = sum(task.download_history) / len(task.download_history)
                            
                            # Calculate progress
                            if task.file_size > 0:
                                task.progress = task.downloaded_bytes / task.file_size
                                
                                # Calculate ETA
                                if task.speed > 0:
                                    remaining_bytes = task.file_size - task.downloaded_bytes
                                    eta_seconds = remaining_bytes / task.speed
                                    task.eta = self._format_time(eta_seconds)
                                else:
                                    task.eta = "Unknown"
                            else:
                                task.progress = 0
                                task.eta = "Unknown"
                            
                            # Reset counters
                            last_update_time = current_time
                            bytes_since_last_update = 0
            
            response.close()
            
            # Move temp file to final location
            final_dir = os.path.dirname(task.save_path)
            if not os.path.exists(final_dir):
                os.makedirs(final_dir, exist_ok=True)
            
            # Remove existing file if it exists
            if os.path.exists(task.save_path):
                os.remove(task.save_path)
            
            shutil.move(task.temp_file, task.save_path)
            
            # Final progress update
            task.progress = 1.0
            task.speed = 0
            task.eta = "Complete"
            
        except Exception as e:
            # Clean up temp file on error
            if task.temp_file and os.path.exists(task.temp_file):
                try:
                    os.remove(task.temp_file)
                except:
                    pass
            raise e
    
    def _update_task_ui(self, task: DownloadTask):
        """Update the UI elements for a specific task"""
        if not hasattr(task, 'ui_elements'):
            return
        
        try:
            ui = task.ui_elements
            
            # Update progress bar
            ui['progress_bar'].set(task.progress)
            
            # Update status based on task status
            if task.status == "Downloading":
                if task.file_size > 0:
                    downloaded_str = self._format_bytes(task.downloaded_bytes)
                    total_str = self._format_bytes(task.file_size)
                    speed_str = self._format_bytes(task.speed) + "/s"
                    progress_percent = int(task.progress * 100)
                    
                    status_text = f"{downloaded_str} / {total_str} ({progress_percent}%) • {speed_str} • ETA: {task.eta}"
                else:
                    downloaded_str = self._format_bytes(task.downloaded_bytes)
                    speed_str = self._format_bytes(task.speed) + "/s"
                    status_text = f"{downloaded_str} downloaded • {speed_str}"
                
                ui['status_label'].configure(text=status_text)
                ui['status_indicator'].configure(
                    text="⬇ Downloading",
                    text_color=TorrentLiteColors.SEA_BLUE
                )
            
            elif task.status == "Complete":
                if task.file_size > 0:
                    size_str = self._format_bytes(task.file_size)
                    ui['status_label'].configure(text=f"✅ Completed • {size_str}")
                else:
                    ui['status_label'].configure(text="✅ Download completed")
                
                ui['status_indicator'].configure(
                    text="✅ Complete",
                    text_color=TorrentLiteColors.SUCCESS_GREEN
                )
                
                # Disable controls
                ui['cancel_btn'].configure(state="disabled")
            
            elif task.status == "Error":
                ui['status_label'].configure(text=f"❌ Error: {task.error_message}")
                ui['status_indicator'].configure(
                    text="❌ Error",
                    text_color=TorrentLiteColors.ERROR_RED
                )
            
            elif task.status == "Analyzing":
                ui['status_label'].configure(text="🔍 Analyzing server capabilities...")
                ui['status_indicator'].configure(
                    text="🔍 Analyzing",
                    text_color=TorrentLiteColors.WARNING_ORANGE
                )
        
        except Exception:
            pass  # Ignore UI update errors
    
    def _format_bytes(self, bytes_value: float) -> str:
        """Format bytes into human readable format"""
        if bytes_value == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(bytes_value)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds into human readable time"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

def main():
    """Main application entry point"""
    try:
        # Create download manager
        download_manager = DownloadManager()
        
        # Create and run UI
        ui_manager = UIManager(download_manager)
        ui_manager.run()
        
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
