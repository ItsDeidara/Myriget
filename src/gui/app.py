import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
import webbrowser
from typing import Optional, Dict, Any
import os
import json
from datetime import datetime
import requests
import shutil

from operations.downloader import FileDownloader
from operations.extractor import FileExtractor
from operations.copier import FileCopier
from config.settings import AppConfig
from utils.logger import Logger
from models.link import LinkManager

class ExpandableFrame(ttk.Frame):
    """A frame that can be expanded/collapsed with a smooth animation."""
    
    def __init__(self, parent, text="", *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        
        self.expanded = False  # Start collapsed by default
        
        # Create main container for header and content
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.X, expand=True)
        
        # Header with arrow
        self.header = ttk.Frame(self.container)
        self.header.pack(fill=tk.X, expand=True)
        
        self.arrow_label = ttk.Label(self.header, text="▼", font=("Arial", 10))
        self.arrow_label.pack(side=tk.LEFT, padx=5)
        
        self.title_label = ttk.Label(self.header, text=text, font=("Arial", 10, "bold"))
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Content frame
        self.content = ttk.Frame(self.container)
        self.content.pack(fill=tk.X, expand=True)
        
        # Bind click event to header
        self.header.bind("<Button-1>", self.toggle)
        self.arrow_label.bind("<Button-1>", self.toggle)
        self.title_label.bind("<Button-1>", self.toggle)
        
        # Style for header hover
        self.header.bind("<Enter>", lambda e: self.header.configure(style="Hover.TFrame"))
        self.header.bind("<Leave>", lambda e: self.header.configure(style="TFrame"))
    
    def toggle(self, event=None):
        self.expanded = not self.expanded
        if self.expanded:
            self.content.pack(fill=tk.X, expand=True)
            self.arrow_label.configure(text="▼")
        else:
            self.content.pack_forget()
            self.arrow_label.configure(text="▶")

class DownloaderApp:
    """Main application class for the file downloader and extractor."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the application with its main components."""
        self.root = root
        self.root.title("Myriget")
        
        # Configure window - increased minimum size and default size
        self.root.minsize(1024, 768)  # Minimum size increased
        self.root.geometry("1280x800")  # Larger default size
        
        # Configure grid weights for responsiveness
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Set default font
        self.default_font = ("Segoe UI", 10)
        self.header_font = ("Segoe UI", 11, "bold")
        self.button_font = ("Segoe UI", 10, "bold")
        
        # Initialize components first
        self.config = AppConfig()
        self.logger = Logger()
        self.link_manager = LinkManager()
        self.downloader = FileDownloader()
        self.extractor = FileExtractor()
        self.copier = FileCopier()
        
        # Initialize GUI state
        self.processing = False
        self.progress_queue = queue.Queue()
        
        # Load configuration first
        self.config.load()
        
        # Initialize GUI elements
        self.temp_dir_entry = None
        self.temp_extract_entry = None
        self.output_dir_entry = None
        self.batch_entry = None
        self.progress_bar = None
        self.progress_label = None
        self.status_text = None
        self.start_button = None
        
        # Try to load Azure theme, fallback to default if not available
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            theme_dir = os.path.join(script_dir, "theme")
            
            # Ensure theme directory exists
            os.makedirs(theme_dir, exist_ok=True)
            
            # Create theme/dark and theme/light directories for images
            os.makedirs(os.path.join(theme_dir, "dark"), exist_ok=True)
            os.makedirs(os.path.join(theme_dir, "light"), exist_ok=True)
            
            # Load Azure theme
            self.root.tk.call("source", os.path.join(script_dir, "azure.tcl"))
            self.root.tk.call("set_theme", "dark")  # Use dark theme by default
        except Exception as e:
            self.logger.log(f"Error loading theme, using default: {str(e)}")
            # Configure fallback styles
            style = ttk.Style()
            style.configure(".", font=self.default_font)
            style.configure("Accent.TButton", font=self.button_font, padding=[20, 10])
            style.configure("Header.TLabel", font=self.header_font)
            style.configure("Success.TLabel", foreground="#00a000", font=self.default_font)
            style.configure("Error.TLabel", foreground="#cc0000", font=self.default_font)
        
        # Configure styles
        self._configure_styles()
        
        # Setup GUI - this creates all the GUI elements
        self._setup_gui()
        
        # Start progress update loop
        self._start_progress_updates()
        
        # Calculate initial library sizes if links.json exists
        if os.path.exists(self.config.links_file):
            self.config.calculate_library_sizes()
            self._update_size_info()
    
    def _configure_styles(self):
        """Configure custom styles for the application."""
        style = ttk.Style()
        
        # Get current theme colors
        bg_color = style.lookup("TFrame", "background") or "#ffffff"
        fg_color = style.lookup("TFrame", "foreground") or "#000000"
        
        # Configure accent button - smaller padding
        style.configure("Accent.TButton",
                      font=self.button_font,
                      padding=[10, 5])  # Reduced padding
        
        # Configure switch style
        style.configure("Switch.TCheckbutton",
                      font=self.button_font)
        
        # Configure card frame
        style.configure("Card.TFrame",
                      relief="solid",
                      borderwidth=1)
        
        # Configure header label
        style.configure("Header.TLabel",
                      font=self.header_font)
        
        # Configure status labels
        style.configure("Success.TLabel",
                      foreground="#00a000",
                      font=self.default_font)
        style.configure("Error.TLabel",
                      foreground="#cc0000",
                      font=self.default_font)
        
        # Update text widget colors and font
        self.root.option_add("*Text.background", bg_color)
        self.root.option_add("*Text.foreground", fg_color)
        self.root.option_add("*Text.font", self.default_font)
        self.root.option_add("*Entry.font", self.default_font)
        self.root.option_add("*Label.font", self.default_font)
    
    def _update_gui_from_config(self) -> None:
        """Update GUI fields with loaded configuration values."""
        # Update directory entries
        self.temp_dir_entry.delete(0, tk.END)
        self.temp_dir_entry.insert(0, self.config.temp_dir)
        
        self.temp_extract_entry.delete(0, tk.END)
        self.temp_extract_entry.insert(0, self.config.temp_extract_dir)
        
        self.output_dir_entry.delete(0, tk.END)
        self.output_dir_entry.insert(0, self.config.output_dir)
        
        # Update batch settings
        self.batch_entry.delete(0, tk.END)
        self.batch_entry.insert(0, str(self.config.batch_size))
        
        # Update batch mode
        self.batch_mode_var.set(self.config.batch_mode)
        
        # Update filter type
        self.filter_type_var.set(self.config.filter_type)
        
        # Update link type
        self.link_type_var.set(self.config.link_type)
        
        # Update size info display
        self._update_size_info()
    
    def _setup_gui(self) -> None:
        """Setup the main GUI components."""
        # Create main container frame with padding
        main_container = ttk.Frame(self.root)
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)
        
        # Create the Start Processing button in the top right
        button_frame = ttk.Frame(main_container)
        button_frame.grid(row=0, column=0, sticky="ne")
        
        self.start_button = ttk.Button(button_frame, text="Start Processing",
                                     command=self._start_processing,
                                     style="Accent.TButton")
        self.start_button.pack(padx=2, pady=2)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        
        # Create main container frames for each tab
        main_container = ttk.Frame(self.notebook)
        tools_container = ttk.Frame(self.notebook)
        settings_container = ttk.Frame(self.notebook)
        games_container = ttk.Frame(self.notebook)  # New games tab container
        
        # Configure grid weights for containers
        for container in (main_container, settings_container, tools_container, games_container):
            container.grid_rowconfigure(0, weight=1)
            container.grid_columnconfigure(0, weight=1)
        
        # Add tabs to notebook in desired order
        self.notebook.add(main_container, text="Main")
        self.notebook.add(games_container, text="Games")  # Add games tab
        self.notebook.add(tools_container, text="Tools")
        self.notebook.add(settings_container, text="Settings")
        
        # Create scrollable frames for each tab
        self.main_frame = self._create_scrollable_frame(main_container)
        self.tools_frame = self._create_scrollable_frame(tools_container)
        self.settings_frame = self._create_scrollable_frame(settings_container)
        self.games_frame = self._create_scrollable_frame(games_container)  # New games frame
        
        # Setup content for each tab
        self._setup_main_tab(self.main_frame)
        self._setup_games_tab(self.games_frame)  # Setup games tab
        self._setup_tools_tab(self.tools_frame)
        self._setup_settings_tab(self.settings_frame)
    
    def _create_scrollable_frame(self, container):
        """Create a scrollable frame that adapts to window size."""
        # Create canvas with proper background
        canvas = tk.Canvas(container, highlightthickness=0, bg=self.root.cget('bg'))
        canvas.grid(row=0, column=0, sticky="nsew")
        
        # Create scrollbar
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Create the scrollable frame with proper background
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # Create window in canvas
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", tags="self.frame")
        
        # Configure scrolling
        def configure_scroll(event=None):
            # Update the scroll region to encompass the inner frame
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Set the canvas width to the frame's width
            canvas.itemconfig("self.frame", width=canvas.winfo_width())
        
        def configure_canvas(event):
            # Update canvas width when window is resized
            canvas_width = event.width
            canvas.itemconfig("self.frame", width=canvas_width)
        
        def on_mousewheel(event):
            # Handle mouse wheel scrolling
            if canvas.winfo_containing(event.x_root, event.y_root) == canvas:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind events
        scrollable_frame.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", configure_canvas)
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Configure canvas
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configure container
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        return scrollable_frame

    def _setup_main_tab(self, parent):
        """Setup the main tab with processing controls."""
        # Directory Settings Card
        dir_card = ttk.Frame(parent, style="Card.TFrame")
        dir_card.grid(row=0, column=0, sticky="ew", padx=5, pady=2)  # Reduced padding
        dir_card.grid_columnconfigure(1, weight=1)
        
        ttk.Label(dir_card, text="Directory Settings", style="Header.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=5, pady=2)  # Reduced padding
        
        self._add_directory_control(dir_card, "Download Location (SSD):", 
                                  self.config.temp_dir, self._browse_temp, 1)
        self._add_directory_control(dir_card, "Extract Location (SSD):", 
                                  self.config.temp_extract_dir, self._browse_temp_extract, 2)
        self._add_directory_control(dir_card, "Output Location:", 
                                  self.config.output_dir, self._browse_output, 3)
        
        # Processing Settings Card
        proc_card = ttk.Frame(parent, style="Card.TFrame")
        proc_card.grid(row=1, column=0, sticky="ew", padx=5, pady=2)  # Reduced padding
        proc_card.grid_columnconfigure(0, weight=1)
        
        ttk.Label(proc_card, text="Processing Settings", style="Header.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=5, pady=2)  # Reduced padding
        
        # Add batch controls in a grid layout
        batch_frame = ttk.Frame(proc_card)
        batch_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=2)  # Reduced padding
        batch_frame.grid_columnconfigure(1, weight=1)
        
        self._setup_batch_controls(batch_frame)
        
        # Progress and Status Card
        status_card = ttk.Frame(parent, style="Card.TFrame")
        status_card.grid(row=2, column=0, sticky="ew", padx=5, pady=2)  # Reduced padding
        status_card.grid_columnconfigure(0, weight=1)
        
        ttk.Label(status_card, text="Progress and Status", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=5, pady=2)  # Reduced padding
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(status_card, mode='determinate')
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=5, pady=2)  # Reduced padding
        
        self.progress_label = ttk.Label(status_card, text="Progress: 0%")
        self.progress_label.grid(row=2, column=0, sticky="w", padx=5, pady=1)  # Reduced padding
        
        # Status text with Azure theme colors
        self.status_text = tk.Text(status_card, height=5, wrap=tk.WORD)  # Reduced height
        self.status_text.grid(row=3, column=0, sticky="ew", padx=5, pady=2)  # Reduced padding
        self.status_text.config(state='disabled')
        
        # Configure text tags
        self.status_text.tag_configure("success", foreground="#00a000")
        self.status_text.tag_configure("error", foreground="#cc0000")
        self.status_text.tag_configure("warning", foreground="#cc6600")
        self.status_text.tag_configure("info", foreground="#0066CC")
    
    def _setup_settings_tab(self, parent):
        """Setup the settings tab with configuration options."""
        # Links Management Card
        links_card = ttk.Frame(parent, style="Card.TFrame")
        links_card.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
        links_card.grid_columnconfigure(0, weight=1)
        
        ttk.Label(links_card, text="Links Management", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=10, pady=5)
        
        # Add links controls
        links_frame = ttk.Frame(links_card)
        links_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self._add_links_control(links_frame)
        
        # Library Information Card
        lib_card = ttk.Frame(parent, style="Card.TFrame")
        lib_card.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        lib_card.grid_columnconfigure(0, weight=1)
        
        ttk.Label(lib_card, text="Library Information", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=10, pady=5)
        
        # Size information display
        self.size_info_text = tk.Text(lib_card, height=6, wrap=tk.WORD)
        self.size_info_text.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.size_info_text.config(state='disabled')
        
        # Calculate button
        ttk.Button(lib_card, text="Calculate Library Sizes",
                  command=self._calculate_sizes).grid(row=2, column=0, pady=10)
    
    def _setup_tools_tab(self, parent):
        """Setup the tools tab with additional utilities."""
        # Import to HDD Card
        hdd_card = ttk.Frame(parent, style="Card.TFrame")
        hdd_card.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
        hdd_card.grid_columnconfigure(0, weight=1)
        
        ttk.Label(hdd_card, text="Import to HDD", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=5, pady=2)
        
        # Add description
        desc_text = ("This tool will scan your output folder and copy games to your Xbox HDD.\n"
                    "It tracks progress in links.json and can verify against the actual HDD contents.")
        ttk.Label(hdd_card, text=desc_text, wraplength=600).grid(
            row=1, column=0, sticky="w", padx=5, pady=2)
        
        # HDD Location Controls
        hdd_frame = ttk.Frame(hdd_card)
        hdd_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=2)
        hdd_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(hdd_frame, text="HDD Location:").grid(row=0, column=0, padx=5, sticky="e")
        self.hdd_entry = ttk.Entry(hdd_frame, width=50)
        self.hdd_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(hdd_frame, text="Browse", command=self._browse_hdd).grid(
            row=0, column=2, padx=5)
        
        # Import Controls
        import_frame = ttk.Frame(hdd_card)
        import_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=2)
        
        # Timeout setting
        timeout_frame = ttk.Frame(import_frame)
        timeout_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(timeout_frame, text="Copy Timeout (seconds):").pack(side=tk.LEFT)
        self.timeout_entry = ttk.Entry(timeout_frame, width=5)
        self.timeout_entry.pack(side=tk.LEFT, padx=5)
        self.timeout_entry.insert(0, "300")  # Default 5 minutes
        
        # Import button
        ttk.Button(import_frame, text="Start Import",
                  command=self._start_hdd_import).pack(side=tk.RIGHT, padx=5)
        
        # Reset button
        ttk.Button(import_frame, text="Reset Import Status",
                  command=self._reset_import_status).pack(side=tk.RIGHT, padx=5)
        
        # Import Tools Card
        import_card = ttk.Frame(parent, style="Card.TFrame")
        import_card.grid(row=1, column=0, sticky="ew", padx=5, pady=2)
        import_card.grid_columnconfigure(0, weight=1)
        
        ttk.Label(import_card, text="Import Links from URL", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=5, pady=2)
        
        # Add description
        desc_text = ("Import a links.json file directly from a URL (e.g., Pastebin raw URL).\n"
                    "You can either append the imported links to your existing links.json "
                    "or replace your current links.json entirely.")
        ttk.Label(import_card, text=desc_text, wraplength=600).grid(
            row=1, column=0, sticky="w", padx=10, pady=5)
        
        # Add import controls
        import_frame = ttk.Frame(import_card)
        import_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        import_frame.grid_columnconfigure(1, weight=1)
        
        # URL entry with label
        ttk.Label(import_frame, text="URL:").grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")
        self.import_url_entry = ttk.Entry(import_frame)
        self.import_url_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        # Import mode selection
        mode_frame = ttk.Frame(import_frame)
        mode_frame.grid(row=1, column=1, sticky="w", pady=5)
        
        self.import_mode_var = tk.StringVar(value="append")
        ttk.Radiobutton(mode_frame, text="Append to existing links", 
                       variable=self.import_mode_var, value="append").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Replace existing links", 
                       variable=self.import_mode_var, value="replace").pack(side=tk.LEFT, padx=5)
        
        # Import button
        ttk.Button(import_frame, text="Import from URL",
                  command=self._import_links_json).grid(row=2, column=1, sticky="w", padx=5, pady=10)
        
        # Merge Tools Card
        merge_card = ttk.Frame(parent, style="Card.TFrame")
        merge_card.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        merge_card.grid_columnconfigure(0, weight=1)
        
        ttk.Label(merge_card, text="Merge Links Files", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=10, pady=5)
        
        # Add description
        merge_desc = ("Combine two links.json files into one.\n\n"
                     "This tool will:\n"
                     "• Let you select another links.json file to merge with your current one\n"
                     "• Remove any duplicate links automatically\n"
                     "• Create a backup of your current links.json before merging\n"
                     "• Update the library size information after merging")
        ttk.Label(merge_card, text=merge_desc, wraplength=600).grid(
            row=1, column=0, sticky="w", padx=10, pady=5)
        
        merge_frame = ttk.Frame(merge_card)
        merge_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        ttk.Button(merge_frame, text="Select Links File to Merge",
                  command=self._merge_links_file).pack(pady=10)
        
        # Help Card
        help_card = ttk.Frame(parent, style="Card.TFrame")
        help_card.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        help_card.grid_columnconfigure(0, weight=1)
        
        ttk.Label(help_card, text="Documentation & Help", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=10, pady=5)
        
        help_desc = ("Access the online documentation for detailed instructions on:\n"
                    "• How to create and manage your links.json file\n"
                    "• Understanding the different file types (ISO, XBLA, XBLA Addons)\n"
                    "• Using the import and merge tools effectively\n"
                    "• Troubleshooting common issues")
        ttk.Label(help_card, text=help_desc, wraplength=600).grid(
            row=1, column=0, sticky="w", padx=10, pady=5)
        
        self.secret_button = ttk.Button(help_card, text="Open Documentation",
                                      command=self._open_pastebin)
        self.secret_button.grid(row=2, column=0, sticky="w", padx=10, pady=10)
    
    def _setup_batch_controls(self, parent):
        """Setup the batch processing controls."""
        # Batch size controls
        size_frame = ttk.Frame(parent)
        size_frame.grid(row=0, column=0, sticky="ew", pady=2)
        size_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(size_frame, text="Batch Size:").grid(row=0, column=0, padx=5)
        self.batch_entry = ttk.Entry(size_frame, width=10)
        self.batch_entry.grid(row=0, column=1, sticky="w", padx=5)
        self.batch_entry.insert(0, str(self.config.batch_size))
        
        # Batch mode selection using radiobuttons
        mode_frame = ttk.Frame(parent)
        mode_frame.grid(row=1, column=0, sticky="ew", pady=2)
        
        self.batch_mode_var = tk.StringVar(value=self.config.batch_mode)
        tk.Radiobutton(mode_frame, text="By Number", variable=self.batch_mode_var,
                      value="By Number").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(mode_frame, text="By Size (MB)", variable=self.batch_mode_var,
                      value="By Size (MB)").pack(side=tk.LEFT, padx=5)
        
        # Processing mode
        proc_frame = ttk.Frame(parent)
        proc_frame.grid(row=2, column=0, sticky="ew", pady=5)
        proc_frame.grid_columnconfigure(0, weight=1)
        
        ttk.Label(proc_frame, text="Processing Mode:", style="Header.TLabel").grid(
            row=0, column=0, sticky="w")
        
        desc_text = "Choose which files to process:\n" \
                   "- All: Process every file in the list\n" \
                   "- Incomplete: Only process files that haven't been copied yet"
        ttk.Label(proc_frame, text=desc_text, wraplength=400).grid(
            row=1, column=0, sticky="w", pady=2)
        
        # Filter type selection using radiobuttons
        filter_frame = ttk.Frame(proc_frame)
        filter_frame.grid(row=2, column=0, sticky="w")
        
        self.filter_type_var = tk.StringVar(value=self.config.filter_type)
        tk.Radiobutton(filter_frame, text="All Files", variable=self.filter_type_var,
                      value="All").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(filter_frame, text="Incomplete Only", variable=self.filter_type_var,
                      value="Incomplete").pack(side=tk.LEFT, padx=5)
        
        # File type selection
        type_frame = ttk.Frame(parent)
        type_frame.grid(row=3, column=0, sticky="ew", pady=5)
        type_frame.grid_columnconfigure(0, weight=1)
        
        ttk.Label(type_frame, text="File Type:", style="Header.TLabel").grid(
            row=0, column=0, sticky="w")
        
        desc_text = "Select the type of files to process:\n" \
                   "- ISO: Process ISO image files\n" \
                   "- XBLA: Process Xbox Live Arcade files\n" \
                   "- XBLA Addons: Process Xbox Live Arcade add-on content"
        ttk.Label(type_frame, text=desc_text, wraplength=400).grid(
            row=1, column=0, sticky="w", pady=2)
        
        # Link type selection using radiobuttons
        link_frame = ttk.Frame(type_frame)
        link_frame.grid(row=2, column=0, sticky="w")
        
        self.link_type_var = tk.StringVar(value=self.config.link_type)
        tk.Radiobutton(link_frame, text="ISO", variable=self.link_type_var,
                      value="ISO").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(link_frame, text="XBLA", variable=self.link_type_var,
                      value="XBLA").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(link_frame, text="XBLA Addons", variable=self.link_type_var,
                      value="XBLA Addons").pack(side=tk.LEFT, padx=5)
    
    def _add_directory_control(self, parent: tk.Widget, label_text: str, 
                             default_value: str, browse_command: callable, 
                             row: int) -> None:
        """Add a directory control to the frame."""
        ttk.Label(parent, text=label_text).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        entry = ttk.Entry(parent, width=50)
        entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
        entry.insert(0, default_value)
        
        # Store entry reference
        if "Download Location" in label_text:
            self.temp_dir_entry = entry
        elif "Extract Location" in label_text:
            self.temp_extract_entry = entry
        elif "Output Location" in label_text:
            self.output_dir_entry = entry
            
        ttk.Button(parent, text="Browse", command=browse_command).grid(
            row=row, column=2, padx=5, pady=5)
    
    def _add_links_control(self, parent: tk.Widget) -> None:
        """Add links file control to the frame."""
        # Create frame for file selection
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(file_frame, text="URLs File (.txt):").grid(
            row=0, column=0, padx=5, pady=5, sticky="e")
        self.links_entry = ttk.Entry(file_frame, width=50)
        self.links_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="Browse", command=self._browse_links).grid(
            row=0, column=2, padx=5, pady=5)
        
        # Create frame for file type selection
        type_frame = ttk.LabelFrame(parent, text="File Type")
        type_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Add description
        type_desc = "What type of game files are you adding?"
        ttk.Label(type_frame, text=type_desc).pack(anchor="w", padx=5, pady=2)
        
        self.links_type_var = tk.StringVar(value="ISO")
        ttk.Radiobutton(type_frame, text="ISO", variable=self.links_type_var,
                       value="ISO").pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Radiobutton(type_frame, text="XBLA", variable=self.links_type_var,
                       value="XBLA").pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Radiobutton(type_frame, text="XBLA Addons", variable=self.links_type_var,
                       value="XBLA Addons").pack(side=tk.LEFT, padx=5, pady=5)
        
        # Create frame for action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Add mode selection
        mode_frame = ttk.LabelFrame(button_frame, text="Update Mode")
        mode_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.links_mode_var = tk.StringVar(value="append")
        ttk.Radiobutton(mode_frame, text="Append to links.json", variable=self.links_mode_var, 
                       value="append").pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Radiobutton(mode_frame, text="Replace links.json", variable=self.links_mode_var, 
                       value="replace").pack(side=tk.LEFT, padx=5, pady=5)
        
        # Add generate and estimate buttons
        action_frame = ttk.Frame(button_frame)
        action_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(action_frame, text="Generate/Update", 
                  command=self._process_links_txt).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Calculate Library Size", 
                  command=self._calculate_sizes).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Merge 2 Links.json Files", 
                  command=self._merge_links_file).pack(side=tk.LEFT, padx=5)
    
    def _add_import_control(self, parent: tk.Widget) -> None:
        """Add import controls to the frame."""
        self.import_url_entry = tk.Entry(parent, width=50)
        self.import_url_entry.pack(fill=tk.X, padx=5, pady=5)
        
        self.import_mode_var = tk.StringVar(value="append")
        tk.Radiobutton(parent, text="Append", variable=self.import_mode_var, 
                      value="append").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(parent, text="Replace", variable=self.import_mode_var, 
                      value="replace").pack(side=tk.LEFT, padx=5)
        
        tk.Button(parent, text="Import", command=self._import_links_json).pack(
            side=tk.RIGHT, padx=5, pady=5)
    
    def _start_progress_updates(self) -> None:
        """Start the progress update loop."""
        self._update_progress()
    
    def _update_progress(self) -> None:
        """Update progress bar and status text from queue."""
        try:
            while not self.progress_queue.empty():
                msg_type, msg = self.progress_queue.get_nowait()
                if msg_type == "status":
                    self._update_status(msg)
                elif msg_type == "progress":
                    self.progress_bar['value'] = msg
                    self.progress_label.config(text=f"Progress: {msg:.1f}%")
                    
                    # Force GUI update
                    self.root.update_idletasks()
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.log(f"Error updating progress: {e}")
        
        # Schedule next update
        self.root.after(100, self._update_progress)
    
    def _browse_temp(self) -> None:
        """Browse for temporary download directory."""
        self.config.temp_dir = self._browse_directory("Select Temporary Download Directory")
        self.config.save()
    
    def _browse_temp_extract(self) -> None:
        """Browse for temporary extraction directory."""
        self.config.temp_extract_dir = self._browse_directory("Select Temporary Extraction Directory")
        self.config.save()
    
    def _browse_output(self) -> None:
        """Browse for output directory."""
        self.config.output_dir = self._browse_directory("Select Output Directory")
        self.config.save()
    
    def _browse_links(self) -> None:
        """Browse for links text file."""
        file_path = tk.filedialog.askopenfilename(
            title="Select URLs Text File",
            filetypes=[("Text files", "*.txt")]
        )
        if file_path:
            self.links_entry.delete(0, tk.END)
            self.links_entry.insert(0, file_path)
    
    def _browse_directory(self, title: str) -> str:
        """Open directory browser dialog."""
        directory = tk.filedialog.askdirectory(title=title)
        return directory if directory else ""
    
    def _browse_file(self, title: str, filetypes: list) -> str:
        """Open file browser dialog."""
        file = tk.filedialog.askopenfilename(title=title, filetypes=filetypes)
        return file if file else ""
    
    def _start_processing(self) -> None:
        """Start processing links in a separate thread."""
        if self.processing:
            self.logger.log("Processing already in progress.")
            messagebox.showwarning(
                "Processing in Progress",
                "A processing task is already running.\n"
                "Please wait for it to complete."
            )
            return
        
        if not self._validate_settings():
            return
        
        # Confirm processing with user
        confirm_msg = (
            "Ready to start processing.\n\n"
            f"File Type: {self.link_type_var.get()}\n"
            f"Processing Mode: {self.filter_type_var.get()}\n"
            f"Batch Mode: {self.batch_mode_var.get()}\n\n"
            "Would you like to proceed?"
        )
        
        if not messagebox.askyesno("Confirm Processing", confirm_msg):
            return
        
        self.processing = True
        self.start_button.config(state='disabled')
        self.progress_bar['value'] = 0
        
        threading.Thread(target=self._process_links, daemon=True).start()
    
    def _validate_settings(self) -> bool:
        """Validate application settings and provide helpful feedback."""
        validation_errors = []
        validation_warnings = []
        
        # Check directories
        if not self.config.temp_dir or not os.path.exists(self.config.temp_dir):
            validation_errors.append("• Missing temporary download directory")
        
        if not self.config.temp_extract_dir or not os.path.exists(self.config.temp_extract_dir):
            validation_errors.append("• Missing temporary extraction directory")
        
        if not self.config.output_dir or not os.path.exists(self.config.output_dir):
            validation_errors.append("• Missing output directory")
        
        # Check links.json
        if not self.config.links_file or not os.path.exists(self.config.links_file):
            validation_errors.append("• No links.json file found")
        else:
            try:
                with open(self.config.links_file, 'r', encoding='utf-8') as f:
                    links_data = json.load(f)
                    
                    if not isinstance(links_data, list):
                        validation_errors.append("• Invalid links.json format: expected a list of links")
                    else:
                        # Check for common issues that we can fix
                        for link in links_data:
                            if not isinstance(link, dict):
                                validation_errors.append("• Invalid link format in links.json")
                                break
                            
                            if 'url' not in link:
                                validation_errors.append("• Missing URL in one or more links")
                                break
                            
                            if 'link_type' not in link:
                                validation_warnings.append("• Some links are missing type information")
                            
                            if 'size_bytes' not in link or not link['size_bytes']:
                                validation_warnings.append("• Some links are missing size information")
                            
                            if 'processed' not in link:
                                validation_warnings.append("• Some links are missing processing status")
            
            except json.JSONDecodeError:
                validation_errors.append("• links.json is not valid JSON")
            except Exception as e:
                validation_errors.append(f"• Error reading links.json: {str(e)}")
        
        if validation_errors:
            error_message = "The following errors need to be fixed:\n\n" + "\n".join(validation_errors)
            self.logger.log(f"Validation errors: {error_message}")
            messagebox.showerror("Validation Errors", error_message)
            return False
        
        if validation_warnings:
            # Remove duplicates while preserving order
            validation_warnings = list(dict.fromkeys(validation_warnings))
            
            warning_message = ("The following issues were found that our tool can fix:\n\n" + 
                             "\n".join(validation_warnings) +
                             "\n\nWould you like to fix these issues now?")
            
            self.logger.log(f"Validation warnings: {warning_message}")
            
            if messagebox.askyesno("Fix Issues", warning_message):
                self._fix_links_issues()
                return False  # Return False to prevent processing until fixes are applied
        
        return True
    
    def _fix_links_issues(self) -> None:
        """Fix common issues in the links.json file."""
        try:
            with open(self.config.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            # Create backup
            backup_file = f"{self.config.links_file}.bak"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(links_data, f, indent=4)
            
            modified = False
            for link in links_data:
                if not isinstance(link, dict):
                    continue
                
                # Add missing link type
                if 'link_type' not in link:
                    link['link_type'] = 'Unknown'
                    modified = True
                
                # Add missing size
                if 'size_bytes' not in link or not link['size_bytes']:
                    link['size_bytes'] = 0
                    modified = True
                
                # Add missing processing status
                if 'processed' not in link:
                    link['processed'] = False
                    modified = True
            
            if modified:
                with open(self.config.links_file, 'w', encoding='utf-8') as f:
                    json.dump(links_data, f, indent=4)
                
                self.logger.log("Fixed issues in links.json")
                messagebox.showinfo(
                    "Issues Fixed",
                    "The issues have been fixed. A backup of your original links.json "
                    f"has been saved as {backup_file}\n\n"
                    "You can now:\n"
                    "1. Use 'Estimate Library Size' to update missing file sizes\n"
                    "2. Start processing to download and extract files"
                )
                
                # Recalculate library sizes
                self.config.calculate_library_sizes()
                self._update_size_info()
        
        except Exception as e:
            self.logger.log(f"Error fixing links.json: {e}")
            messagebox.showerror(
                "Error",
                f"An error occurred while fixing the issues:\n{str(e)}\n\n"
                "Please check your links.json file manually."
            )
    
    def _process_links(self) -> None:
        """Process links in a separate thread."""
        try:
            self.link_manager.process_links(
                self.config.links_file,
                self.config.temp_dir,
                self.config.temp_extract_dir,
                self.config.output_dir,
                self.config.batch_size,
                self.progress_queue,
                self.filter_type_var.get()
            )
        except Exception as e:
            self.logger.log(f"Error during processing: {str(e)}")
            messagebox.showerror("Error", f"Processing failed: {e}")
        finally:
            self.processing = False
            self.start_button.config(state='normal')
            self.progress_queue.put(("progress", 0))
    
    def _process_links_txt(self) -> None:
        """Process the links text file to generate/update links.json."""
        txt_file = self.links_entry.get().strip()
        if not txt_file:
            messagebox.showerror("Error", "Please select a text file containing URLs")
            return
        
        if not os.path.exists(txt_file):
            messagebox.showerror("Error", "Selected file does not exist")
            return
        
        try:
            # Read URLs from text file
            with open(txt_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
            
            if not urls:
                messagebox.showerror("Error", "No URLs found in the text file")
                return
            
            # Process URLs and update links.json
            self.link_manager.process_urls_file(
                urls,
                self.links_mode_var.get(),
                self.links_type_var.get(),  # Pass the selected file type
                self.progress_queue
            )
            
            messagebox.showinfo("Success", "Links.json has been updated successfully")
            
        except Exception as e:
            self.logger.log(f"Error processing links file: {e}")
            messagebox.showerror("Error", f"Failed to process links file: {e}")
    
    def _open_pastebin(self) -> None:
        """Open the secret pastebin URL in the default browser."""
        try:
            webbrowser.open("https://pastebin.com/your-secret-url")
        except Exception as e:
            self.logger.log(f"Error opening pastebin: {e}")
    
    def _import_links_json(self) -> None:
        """Import links.json from a URL."""
        url = self.import_url_entry.get().strip()
        if not url:
            self.logger.log("Error: Please enter a URL")
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        try:
            self.link_manager.import_links_json(
                url,
                self.import_mode_var.get(),
                self.progress_queue
            )
        except Exception as e:
            self.logger.log(f"Error importing links.json: {e}")
            messagebox.showerror("Error", f"Import failed: {e}")
    
    def _calculate_sizes(self) -> None:
        """Calculate and display library sizes."""
        try:
            self.config.calculate_library_sizes()
            self._update_size_info()
        except Exception as e:
            self.logger.log(f"Error calculating sizes: {e}")
            messagebox.showerror("Error", f"Failed to calculate sizes: {e}")
    
    def _update_size_info(self) -> None:
        """Update the size information display."""
        self.size_info_text.config(state='normal')
        self.size_info_text.delete(1.0, tk.END)
        
        if not self.config.last_size_check:
            self.size_info_text.insert(tk.END, 
                "Library sizes have not been calculated yet.\n"
                "Click 'Calculate Library Sizes' to get size information.")
        else:
            # Get detailed size information
            size_info = self.config.get_library_size_info()
            self.size_info_text.insert(tk.END, size_info)
            
            # Add storage recommendations
            total_size = self.config.iso_size_gb + self.config.xbla_size_gb
            self.size_info_text.insert(tk.END, "\n\nStorage Recommendations:")
            self.size_info_text.insert(tk.END, f"\n- Total Required: {total_size:.2f} GB")
            self.size_info_text.insert(tk.END, f"\n- Recommended Free Space: {(total_size * 1.2):.2f} GB (20% buffer)")
            self.size_info_text.insert(tk.END, f"\n- ISO Library: {self.config.iso_size_gb:.2f} GB")
            self.size_info_text.insert(tk.END, f"\n- XBLA Library: {self.config.xbla_size_gb:.2f} GB")
        
        self.size_info_text.config(state='disabled')
    
    def _load_games(self) -> None:
        """Load games from links.json into the treeview."""
        try:
            # Clear existing items
            for item in self.game_tree.get_children():
                self.game_tree.delete(item)
            
            # Load links.json
            with open(self.config.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            # Add games to treeview
            for game in links_data:
                # Use the sanitized name if available, otherwise generate one
                game_name = game.get('name', '')
                if not game_name:
                    game_name = self.link_manager._sanitize_game_name(game.get('url', ''))
                
                game_type = game.get('link_type', 'Unknown')
                size_bytes = game.get('size_bytes', 0)
                size_str = f"{size_bytes / (1024*1024*1024):.2f} GB" if size_bytes else "Unknown"
                enabled = game.get('enabled', True)
                
                self.game_tree.insert('', tk.END, values=(
                    "☑" if enabled else "☐",  # Checkbox
                    game_name,
                    game_type,
                    size_str
                ))
            
            # Sort by name by inserting items in sorted order
            items = [(self.game_tree.set(item, 'name'), item) for item in self.game_tree.get_children()]
            for name, item in sorted(items):
                self.game_tree.move(item, '', 'end')
            
            # Force GUI update
            self.root.update_idletasks()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load games: {str(e)}")

    def _enable_selected(self) -> None:
        """Enable selected games in the treeview."""
        selected = self.game_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select games to enable")
            return
        
        for item in selected:
            self.game_tree.set(item, 'enabled', "☑")

    def _disable_selected(self) -> None:
        """Disable selected games in the treeview."""
        selected = self.game_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select games to disable")
            return
        
        for item in selected:
            self.game_tree.set(item, 'enabled', "☐")

    def _save_game_changes(self) -> None:
        """Save game enabled/disabled status to links.json."""
        try:
            # Load current links.json
            with open(self.config.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            # Update enabled status for each game
            for item in self.game_tree.get_children():
                values = self.game_tree.item(item)['values']
                game_name = values[1]  # Name is now in position 1
                
                # Find matching game in links.json
                for game in links_data:
                    if os.path.basename(game.get('output_path', '')) == game_name:
                        game['enabled'] = values[0] == "☑"  # Checkbox is in position 0
                        break
            
            # Save changes
            with open(self.config.links_file, 'w', encoding='utf-8') as f:
                json.dump(links_data, f, indent=4)
            
            self._update_status("Game status changes saved successfully")
            messagebox.showinfo("Success", "Game status changes saved")
            
        except Exception as e:
            self._update_status(f"Error saving game changes: {str(e)}")
            messagebox.showerror("Error", f"Failed to save changes: {str(e)}")
    
    def _merge_links_file(self) -> None:
        """Merge another links.json file with the current one."""
        if not os.path.exists(self.config.links_file):
            messagebox.showerror(
                "Error",
                "No primary links.json found in the config folder.\n\n"
                "Please generate a links.json file first."
            )
            return
        
        # Ask user for the second links.json file
        second_file = tk.filedialog.askopenfilename(
            title="Select Second Links File",
            filetypes=[("JSON files", "*.json")],
            initialdir=os.path.dirname(self.config.links_file)
        )
        
        if not second_file:
            return
        
        if self.processing:
            messagebox.showwarning(
                "Warning",
                "A process is already running.\n\n"
                "Please wait for the current process to complete."
            )
            return
        
        # Switch to main tab and show alert
        self.notebook.select(0)  # Select the first (main) tab
        result = messagebox.showinfo(
            "Merging Files",
            "Starting merge process...\n\n"
            "A backup of your current links.json will be created automatically.\n"
            "Please watch the Status section for progress."
        )
        
        try:
            # Clear previous status
            self.status_text.config(state='normal')
            self.status_text.delete(1.0, tk.END)
            self.status_text.config(state='disabled')
            
            # Reset progress
            self.progress_bar['value'] = 0
            self.progress_label.config(text="Progress: 0%")
            
            # Update status to show we're starting
            self._update_status("Starting merge process...")
            
            self.processing = True
            threading.Thread(target=self._process_merge, args=(second_file,), daemon=True).start()
        except Exception as e:
            self.processing = False
            self.logger.log(f"Error starting merge: {e}")
            self._update_status(f"Error starting merge: {e}")
            messagebox.showerror("Error", f"Failed to start merge: {e}")
    
    def _process_merge(self, second_file: str) -> None:
        """Process the merge in a separate thread."""
        try:
            self.link_manager.merge_links_files(second_file, self.progress_queue)
            
            # Recalculate sizes after merge
            self._update_status("Recalculating library sizes...")
            self.config.calculate_library_sizes()
            
            # Force GUI update
            self.root.after(0, lambda: [
                self._update_size_info(),
                self._update_status("Merge complete!")
            ])
            
            # Show completion message
            self.root.after(100, lambda: 
                messagebox.showinfo("Success", "Links files have been merged successfully!"))
        except Exception as e:
            self.logger.log(f"Error during merge: {e}")
            self._update_status(f"Error during merge: {e}")
            messagebox.showerror(
                "Error",
                f"An error occurred during merge:\n{str(e)}\n\n"
                "Your original links.json has been preserved in the .bak file."
            )
        finally:
            self.processing = False
            self.progress_queue.put(("progress", 0))
            self.progress_label.config(text="Progress: 0%")
    
    def _browse_hdd(self) -> None:
        """Browse for Xbox HDD directory."""
        directory = tk.filedialog.askdirectory(title="Select Xbox HDD Directory")
        if directory:
            self.hdd_entry.delete(0, tk.END)
            self.hdd_entry.insert(0, directory)
    
    def _start_hdd_import(self) -> None:
        """Start the HDD import process."""
        if self.processing:
            messagebox.showwarning(
                "Processing in Progress",
                "A process is already running. Please wait for it to complete."
            )
            return
        
        hdd_dir = self.hdd_entry.get().strip()
        if not hdd_dir:
            messagebox.showerror("Error", "Please select an HDD directory")
            return
        
        try:
            timeout = int(self.timeout_entry.get())
            if timeout < 1:
                raise ValueError("Timeout must be positive")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid timeout value")
            return
        
        if not os.path.exists(self.config.output_dir):
            messagebox.showerror("Error", "Output directory does not exist")
            return
        
        # Confirm with user
        if not messagebox.askyesno("Confirm Import",
                                 "This will copy games from the output directory to your Xbox HDD.\n"
                                 "The process may take a long time.\n\n"
                                 "Would you like to proceed?"):
            return
        
        self.processing = True
        self.start_button.config(state='disabled')
        self.progress_bar['value'] = 0
        
        threading.Thread(target=self._process_hdd_import, args=(hdd_dir, timeout), daemon=True).start()
    
    def _process_hdd_import(self, hdd_dir: str, timeout: int) -> None:
        """Process the HDD import in a separate thread."""
        try:
            # Load links.json
            with open(self.config.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            # Filter for unimported games
            games_to_import = [link for link in links_data 
                             if not link.get('imported', False)]
            
            total_games = len(games_to_import)
            if total_games == 0:
                self._update_status("No games to import - all games are already marked as imported")
                return
            
            self._update_status(f"Starting import of {total_games} games...")
            
            for i, game in enumerate(games_to_import, 1):
                game_name = os.path.basename(game.get('output_path', ''))
                self._update_status(f"Importing {game_name} ({i}/{total_games})")
                
                # Calculate progress
                progress = (i / total_games) * 100
                self.progress_queue.put(("progress", progress))
                
                # Copy game to HDD
                source_path = os.path.join(self.config.output_dir, game_name)
                if not os.path.exists(source_path):
                    self._update_status(f"Warning: {game_name} not found in output directory")
                    continue
                
                dest_path = os.path.join(hdd_dir, game_name)
                try:
                    # Use shutil.copy2 to preserve metadata
                    shutil.copy2(source_path, dest_path)
                    
                    # Update links.json
                    game['imported'] = True
                    game['import_date'] = datetime.now().isoformat()
                    game['hdd_path'] = dest_path
                    
                    with open(self.config.links_file, 'w', encoding='utf-8') as f:
                        json.dump(links_data, f, indent=4)
                    
                    self._update_status(f"Successfully imported {game_name}")
                except Exception as e:
                    self._update_status(f"Error importing {game_name}: {str(e)}")
                    continue
            
            self._update_status("Import process completed")
            messagebox.showinfo("Success", "HDD import process completed")
            
        except Exception as e:
            self._update_status(f"Error during HDD import: {str(e)}")
            messagebox.showerror("Error", f"Import failed: {str(e)}")
        finally:
            self.processing = False
            self.start_button.config(state='normal')
            self.progress_queue.put(("progress", 0))
    
    def _reset_import_status(self) -> None:
        """Reset the import status for all games in links.json."""
        if not messagebox.askyesno("Confirm Reset",
                                 "This will mark all games as not imported in links.json.\n"
                                 "This action cannot be undone.\n\n"
                                 "Would you like to proceed?"):
            return
        
        try:
            with open(self.config.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            for game in links_data:
                game['imported'] = False
                if 'import_date' in game:
                    del game['import_date']
                if 'hdd_path' in game:
                    del game['hdd_path']
            
            with open(self.config.links_file, 'w', encoding='utf-8') as f:
                json.dump(links_data, f, indent=4)
            
            self._update_status("Import status has been reset for all games")
            messagebox.showinfo("Success", "Import status has been reset")
            
        except Exception as e:
            self._update_status(f"Error resetting import status: {str(e)}")
            messagebox.showerror("Error", f"Reset failed: {str(e)}")

    def _setup_games_tab(self, parent):
        """Setup the games management tab."""
        # Main container with padding
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)
        
        # Header with description
        header_frame = ttk.Frame(container)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Label(header_frame, text="Game Management", style="Header.TLabel").pack(anchor="w")
        desc_text = ("Enable or disable games in your library.\n"
                    "Disabled games will be skipped during processing.")
        ttk.Label(header_frame, text=desc_text, wraplength=600).pack(anchor="w", pady=5)
        
        # Control buttons frame
        button_frame = ttk.Frame(container)
        button_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        
        # Add generate names button
        ttk.Button(button_frame, text="Generate Game Names",
                  command=self._generate_game_names).pack(side=tk.LEFT, padx=5)
        
        # Search and filter frame
        search_frame = ttk.Frame(container)
        search_frame.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.game_search_var = tk.StringVar()
        self.game_search_var.trace_add("write", self._filter_games)
        search_entry = ttk.Entry(search_frame, textvariable=self.game_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # Filter frame
        filter_frame = ttk.Frame(container)
        filter_frame.grid(row=3, column=0, sticky="ew", pady=(0, 5))
        
        self.game_filter_var = tk.StringVar(value="all")
        ttk.Radiobutton(filter_frame, text="All Games", variable=self.game_filter_var,
                       value="all", command=self._filter_games).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(filter_frame, text="Enabled Only", variable=self.game_filter_var,
                       value="enabled", command=self._filter_games).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(filter_frame, text="Disabled Only", variable=self.game_filter_var,
                       value="disabled", command=self._filter_games).pack(side=tk.LEFT, padx=5)
        
        # Game list frame
        list_frame = ttk.Frame(container)
        list_frame.grid(row=4, column=0, sticky="nsew", pady=5)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        
        # Create Treeview for games with checkboxes
        columns = ('enabled', 'name', 'type', 'size')
        self.game_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        # Define headings
        self.game_tree.heading('enabled', text='')
        self.game_tree.heading('name', text='Game Name')
        self.game_tree.heading('type', text='Type')
        self.game_tree.heading('size', text='Size')
        
        # Define columns
        self.game_tree.column('enabled', width=30, anchor='center')
        self.game_tree.column('name', width=300)
        self.game_tree.column('type', width=100)
        self.game_tree.column('size', width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.game_tree.yview)
        self.game_tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid the tree and scrollbar
        self.game_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind checkbox click
        self.game_tree.bind('<ButtonRelease-1>', self._toggle_game)
        
        # Control buttons frame
        button_frame = ttk.Frame(container)
        button_frame.grid(row=5, column=0, sticky="ew", pady=5)
        
        ttk.Button(button_frame, text="Enable All",
                  command=lambda: self._toggle_all_games(True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Disable All",
                  command=lambda: self._toggle_all_games(False)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Changes",
                  command=self._save_game_changes).pack(side=tk.RIGHT, padx=5)
        
        # Load games
        self._load_games()

    def _toggle_game(self, event):
        """Toggle game enabled/disabled status when checkbox is clicked."""
        region = self.game_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.game_tree.identify_column(event.x)
            if column == "#1":  # Enabled column
                item = self.game_tree.identify_row(event.y)
                current_value = self.game_tree.set(item, 'enabled')
                new_value = "☐" if current_value == "☑" else "☑"
                self.game_tree.set(item, 'enabled', new_value)

    def _toggle_all_games(self, enable: bool):
        """Enable or disable all games in the list."""
        for item in self.game_tree.get_children():
            self.game_tree.set(item, 'enabled', "☑" if enable else "☐")

    def _filter_games(self, *args):
        """Filter games based on search text and filter type."""
        search_text = self.game_search_var.get().lower()
        filter_type = self.game_filter_var.get()
        
        for item in self.game_tree.get_children():
            game_name = self.game_tree.set(item, 'name').lower()
            enabled = self.game_tree.set(item, 'enabled') == "☑"
            
            # Apply search filter
            matches_search = search_text in game_name
            
            # Apply type filter
            matches_type = (
                filter_type == "all" or
                (filter_type == "enabled" and enabled) or
                (filter_type == "disabled" and not enabled)
            )
            
            # Show/hide based on filters
            if matches_search and matches_type:
                self.game_tree.item(item, open=True)
            else:
                self.game_tree.item(item, open=False)

    def _update_status(self, message: str) -> None:
        """Update the status text with a new message."""
        def _do_update():
            self.status_text.config(state='normal')
            timestamp = datetime.now().strftime('%I:%M:%S %p')
            
            # Determine message type and apply appropriate tag
            if any(s in message.lower() for s in ["success", "complete", "saved", "updated", "added"]):
                tag = "success"
            elif any(s in message.lower() for s in ["error", "failed", "invalid", "missing"]):
                tag = "error"
            elif any(s in message.lower() for s in ["warning", "caution", "notice"]):
                tag = "warning"
            else:
                tag = ""
            
            # Insert timestamp with info color
            self.status_text.insert(tk.END, f"{timestamp} - ", "info")
            
            # Insert message with appropriate color
            if tag:
                self.status_text.insert(tk.END, f"{message}\n", tag)
            else:
                self.status_text.insert(tk.END, f"{message}\n")
            
            self.status_text.see(tk.END)
            self.status_text.config(state='disabled')
        
        # If we're in the main thread, update directly
        if threading.current_thread() is threading.main_thread():
            _do_update()
        else:
            # Otherwise schedule the update
            self.root.after(0, _do_update)

    def _generate_game_names(self) -> None:
        """Generate and store sanitized names for all games."""
        if self.processing:
            messagebox.showwarning(
                "Processing in Progress",
                "A process is already running. Please wait for it to complete."
            )
            return
        
        # Confirm with user
        if not messagebox.askyesno("Generate Game Names",
                                 "This will generate clean, readable names for all games in your library.\n"
                                 "The process may take a few moments.\n\n"
                                 "Would you like to proceed?"):
            return
        
        self.processing = True
        self.start_button.config(state='disabled')
        self.progress_bar['value'] = 0
        
        threading.Thread(target=self._process_generate_names, daemon=True).start()

    def _process_generate_names(self) -> None:
        """Process the name generation in a separate thread."""
        try:
            self.link_manager.generate_game_names(self.progress_queue)
            
            # Force a refresh of the game list
            self.root.after(0, self._load_games)  # Schedule on main thread
            
            # Show success message after a short delay to ensure list is refreshed
            self.root.after(100, lambda: messagebox.showinfo(
                "Success", 
                "Game names have been generated successfully!\n\n"
                "The game list has been refreshed with the new names."
            ))
        except Exception as e:
            self._update_status(f"Error generating game names: {str(e)}")
            messagebox.showerror("Error", f"Failed to generate game names: {str(e)}")
        finally:
            self.processing = False
            self.start_button.config(state='normal')
            self.progress_queue.put(("progress", 0)) 