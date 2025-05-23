"""
TorrentLite - Python File Download Manager
Sprint 1: Foundation & Basic UI

A multi-threaded file download manager with segmented downloads
Author: TorrentLite Team
Version: 1.0.0
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import threading
from typing import Optional, Dict, Any
import requests
from urllib.parse import urlparse
import time

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

class DownloadTask:
    """Represents a single download task"""
    
    def __init__(self, url: str, save_path: str, segments: int = 4):
        self.url = url
        self.save_path = save_path
        self.segments = segments
        self.status = "Pending"  # Pending, Downloading, Paused, Complete, Error
        self.progress = 0.0
        self.speed = 0.0
        self.eta = "Unknown"
        self.file_size = 0
        self.downloaded_bytes = 0
        self.start_time = None
        self.error_message = ""
    
    def get_filename(self) -> str:
        """Extract filename from URL or path"""
        if os.path.basename(self.save_path):
            return os.path.basename(self.save_path)
        
        parsed_url = urlparse(self.url)
        filename = os.path.basename(parsed_url.path) or "download"
        return filename

class UIManager:
    """Handles all UI-related functionality"""
    
    def __init__(self, download_manager):
        self.download_manager = download_manager
        self.setup_main_window()
        self.create_widgets()
        
    def setup_main_window(self):
        """Initialize the main application window"""
        self.root = ctk.CTk()
        self.root.title("TorrentLite - File Download Manager")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)
        
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
        """Create the application header"""
        header_frame = ctk.CTkFrame(self.root, fg_color=TorrentLiteColors.SEA_BLUE)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="🚀 TorrentLite",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white"
        )
        title_label.grid(row=0, column=0, pady=15)
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="High-Speed Multi-Threaded Download Manager",
            font=ctk.CTkFont(size=12),
            text_color="white"
        )
        subtitle_label.grid(row=1, column=0, pady=(0, 15))
        
    def create_input_section(self):
        """Create URL input and settings section"""
        input_frame = ctk.CTkFrame(self.root)
        input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        input_frame.grid_columnconfigure(1, weight=1)
        
        # URL input
        url_label = ctk.CTkLabel(input_frame, text="Download URL:")
        url_label.grid(row=0, column=0, padx=(15, 10), pady=(15, 5), sticky="w")
        
        self.url_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Paste your download URL here...",
            font=ctk.CTkFont(size=12)
        )
        self.url_entry.grid(row=0, column=1, columnspan=2, padx=(0, 15), pady=(15, 5), sticky="ew")
        
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
        
        # Settings row
        settings_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        settings_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 15))
        settings_frame.grid_columnconfigure(2, weight=1)
        
        # Segments selector
        segments_label = ctk.CTkLabel(settings_frame, text="Segments:")
        segments_label.grid(row=0, column=0, padx=(15, 10), sticky="w")
        
        self.segments_var = tk.StringVar(value="4")
        segments_combo = ctk.CTkComboBox(
            settings_frame,
            values=["1", "2", "4", "6", "8", "10"],
            variable=self.segments_var,
            width=80,
            state="readonly"
        )
        segments_combo.grid(row=0, column=1, padx=(0, 20))
        
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
        self.start_btn.grid(row=0, column=3, padx=(0, 15), pady=5, sticky="e")
        
    def create_download_panel(self):
        """Create the main download tracking panel"""
        panel_frame = ctk.CTkFrame(self.root)
        panel_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        panel_frame.grid_columnconfigure(0, weight=1)
        panel_frame.grid_rowconfigure(1, weight=1)
        
        # Panel header
        header = ctk.CTkLabel(
            panel_frame,
            text="Download Progress",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TorrentLiteColors.TEXT_PRIMARY
        )
        header.grid(row=0, column=0, pady=(15, 10))
        
        # Scrollable frame for downloads
        self.downloads_frame = ctk.CTkScrollableFrame(panel_frame)
        self.downloads_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.downloads_frame.grid_columnconfigure(0, weight=1)
        
        # Initial empty state
        self.show_empty_state()
        
    def create_footer(self):
        """Create the application footer"""
        footer_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 10))
        footer_frame.grid_columnconfigure(1, weight=1)
        
        # Status info
        self.status_label = ctk.CTkLabel(
            footer_frame,
            text="Ready to download",
            font=ctk.CTkFont(size=12),
            text_color=TorrentLiteColors.TEXT_SECONDARY
        )
        self.status_label.grid(row=0, column=0, padx=(10, 20), sticky="w")
        
        # Speed and stats
        self.stats_label = ctk.CTkLabel(
            footer_frame,
            text="Downloads: 0 | Speed: 0 KB/s",
            font=ctk.CTkFont(size=12),
            text_color=TorrentLiteColors.TEXT_SECONDARY
        )
        self.stats_label.grid(row=0, column=2, padx=(20, 10), sticky="e")
        
    def show_empty_state(self):
        """Show empty state when no downloads are active"""
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
            text="No downloads yet\nPaste a URL above to get started!",
            font=ctk.CTkFont(size=14),
            text_color=TorrentLiteColors.TEXT_SECONDARY,
            justify="center"
        )
        empty_text.grid(row=1, column=0)
        
    def browse_save_location(self):
        """Open file dialog to choose save location"""
        current_path = self.save_path_var.get()
        
        # If current path is a directory, use it as initial directory
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
                ("ZIP Archives", "*.zip"),
                ("Video Files", "*.mp4;*.avi;*.mkv"),
                ("Audio Files", "*.mp3;*.wav;*.flac"),
                ("Images", "*.jpg;*.png;*.gif"),
                ("Documents", "*.pdf;*.doc;*.docx")
            ]
        )
        
        if file_path:
            self.save_path_var.set(file_path)
    
    def start_download(self):
        """Handle start download button click"""
        url = self.url_entry.get().strip()
        save_path = self.save_path_var.get().strip()
        segments = int(self.segments_var.get())
        
        # Validation
        if not url:
            messagebox.showerror("Error", "Please enter a download URL")
            return
            
        if not save_path:
            messagebox.showerror("Error", "Please choose a save location")
            return
        
        # Check if URL is valid
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception:
            messagebox.showerror("Error", "Please enter a valid URL")
            return
        
        # Create download task
        task = DownloadTask(url, save_path, segments)
        
        # Add to download manager
        self.download_manager.add_download(task)
        
        # Update UI
        self.add_download_to_ui(task)
        self.url_entry.delete(0, 'end')
        self.update_status("Download started...")
        
    def add_download_to_ui(self, task: DownloadTask):
        """Add a download task to the UI"""
        # Clear empty state if this is the first download
        for widget in self.downloads_frame.winfo_children():
            widget.destroy()
        
        # Create download item frame
        item_frame = ctk.CTkFrame(self.downloads_frame)
        item_frame.grid(row=len(self.download_manager.tasks), column=0, sticky="ew", pady=5)
        item_frame.grid_columnconfigure(1, weight=1)
        
        # File info
        filename = task.get_filename()
        file_label = ctk.CTkLabel(
            item_frame,
            text=f"📄 {filename}",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        file_label.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="w")
        
        # URL (truncated)
        url_display = task.url if len(task.url) <= 60 else task.url[:60] + "..."
        url_label = ctk.CTkLabel(
            item_frame,
            text=url_display,
            font=ctk.CTkFont(size=10),
            text_color=TorrentLiteColors.TEXT_SECONDARY,
            anchor="w"
        )
        url_label.grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="w")
        
        # Progress bar
        progress_bar = ctk.CTkProgressBar(
            item_frame,
            progress_color=TorrentLiteColors.SEA_BLUE
        )
        progress_bar.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="ew")
        progress_bar.set(0)
        
        # Status and controls
        status_label = ctk.CTkLabel(
            item_frame,
            text="Preparing...",
            font=ctk.CTkFont(size=12),
            text_color=TorrentLiteColors.TEXT_SECONDARY
        )
        status_label.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="w")
        
        # Store references for updates
        task.ui_elements = {
            'frame': item_frame,
            'progress_bar': progress_bar,
            'status_label': status_label
        }
    
    def update_status(self, message: str):
        """Update the footer status message"""
        self.status_label.configure(text=message)
    
    def run(self):
        """Start the application main loop"""
        self.root.mainloop()

class DownloadManager:
    """Core download management functionality"""
    
    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_downloads = 0
        
    def add_download(self, task: DownloadTask):
        """Add a new download task"""
        task_id = f"{task.url}_{int(time.time())}"
        self.tasks[task_id] = task
        
        # Start download in background thread
        download_thread = threading.Thread(
            target=self._download_file,
            args=(task,),
            daemon=True
        )
        download_thread.start()
        
    def _download_file(self, task: DownloadTask):
        """Basic file download implementation (Sprint 1 - single threaded)"""
        try:
            task.status = "Downloading"
            task.start_time = time.time()
            
            # Make request with stream=True for large files
            response = requests.get(task.url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get file size
            task.file_size = int(response.headers.get('content-length', 0))
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(task.save_path), exist_ok=True)
            
            # Download file
            with open(task.save_path, 'wb') as file:
                downloaded = 0
                chunk_size = 8192
                
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        task.downloaded_bytes = downloaded
                        
                        # Update progress
                        if task.file_size > 0:
                            task.progress = downloaded / task.file_size
                        
                        # Calculate speed and ETA
                        elapsed = time.time() - task.start_time
                        if elapsed > 0:
                            task.speed = downloaded / elapsed
                            if task.speed > 0 and task.file_size > 0:
                                remaining = task.file_size - downloaded
                                eta_seconds = remaining / task.speed
                                task.eta = self._format_time(eta_seconds)
                        
                        # Update UI
                        self._update_task_ui(task)
            
            task.status = "Complete"
            task.progress = 1.0
            self._update_task_ui(task)
            
        except Exception as e:
            task.status = "Error"
            task.error_message = str(e)
            self._update_task_ui(task)
    
    def _update_task_ui(self, task: DownloadTask):
        """Update the UI elements for a task"""
        if hasattr(task, 'ui_elements'):
            try:
                # Update progress bar
                task.ui_elements['progress_bar'].set(task.progress)
                
                # Update status text
                if task.status == "Downloading":
                    speed_str = self._format_bytes(task.speed) + "/s" if task.speed > 0 else "0 B/s"
                    progress_str = f"{task.progress * 100:.1f}%" if task.progress > 0 else "0%"
                    status_text = f"{progress_str} • {speed_str} • ETA: {task.eta}"
                elif task.status == "Complete":
                    status_text = "✅ Download complete!"
                elif task.status == "Error":
                    status_text = f"❌ Error: {task.error_message}"
                else:
                    status_text = task.status
                
                task.ui_elements['status_label'].configure(text=status_text)
                
            except Exception:
                pass  # UI might be destroyed
    
    def _format_bytes(self, bytes_value: float) -> str:
        """Format bytes into human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} TB"
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds into human readable time"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
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
        app = UIManager(download_manager)
        app.run()
        
    except Exception as e:
        print(f"Application error: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")

if __name__ == "__main__":
    main()
