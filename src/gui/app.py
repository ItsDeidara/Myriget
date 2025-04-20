import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import queue
import threading
import webbrowser
from typing import Optional, Dict, Any
import os
import json
from datetime import datetime
import requests
import shutil
import time
import multiprocessing

from operations.downloader import FileDownloader
from operations.extractor import FileExtractor
from operations.copier import FileCopier
from operations.iso2god import ISO2GODConverter
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
    
    # Define schema as a class variable
    LINK_SCHEMA = {
        # Common fields for all link types
        'common': {
            'url': '',
            'link_type': 'Unknown',
            'name': '',
            'size_bytes': 0,
            'enabled': True,
            'processed': False,
            'downloaded': False,
            'extracted': False,
            'deleted': False,
            'copied': False,
            'imported': False,
            'import_date': None,
            'output_path': None
        },
        # Additional fields for ISO files
        'iso': {
            'god_converted': False,
            'god_conversion_date': None,
            'god_output_path': None,
            'god_conversion_error': None,
            'god_conversion_progress': 0,
            'god_conversion_started': False,
            'god_conversion_completed': False
        }
    }
    
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
        games_container = ttk.Frame(self.notebook)
        iso2god_container = ttk.Frame(self.notebook)  # New ISO2GOD container
        
        # Configure grid weights for containers
        for container in (main_container, settings_container, tools_container, games_container, iso2god_container):
            container.grid_rowconfigure(0, weight=1)
            container.grid_columnconfigure(0, weight=1)
        
        # Add tabs to notebook in desired order
        self.notebook.add(main_container, text="Main")
        self.notebook.add(games_container, text="Games")
        self.notebook.add(tools_container, text="Tools")
        self.notebook.add(settings_container, text="Settings")
        self.notebook.add(iso2god_container, text="ISO2GOD")  # Add ISO2GOD tab
        
        # Create scrollable frames for each tab
        self.main_frame = self._create_scrollable_frame(main_container)
        self.tools_frame = self._create_scrollable_frame(tools_container)
        self.settings_frame = self._create_scrollable_frame(settings_container)
        self.games_frame = self._create_scrollable_frame(games_container)
        self.iso2god_frame = self._create_scrollable_frame(iso2god_container)  # Create ISO2GOD frame
        
        # Setup content for each tab
        self._setup_main_tab(self.main_frame)
        self._setup_games_tab(self.games_frame)
        self._setup_tools_tab(self.tools_frame)
        self._setup_settings_tab(self.settings_frame)
        self._setup_iso2god_tab(self.iso2god_frame)  # Setup ISO2GOD tab
    
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
        self.batch_entry.insert(0, "10240")  # Default to 10GB instead of 500MB
        
        # Batch mode selection using radiobuttons
        mode_frame = ttk.Frame(parent)
        mode_frame.grid(row=1, column=0, sticky="ew", pady=2)
        
        self.batch_mode_var = tk.StringVar(value="By Size (MB)")  # Default to size-based batching
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
        
        self.filter_type_var = tk.StringVar(value="Incomplete")  # Default to Incomplete
        tk.Radiobutton(filter_frame, text="All Files", variable=self.filter_type_var,
                      value="All").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(filter_frame, text="Incomplete Only", variable=self.filter_type_var,
                      value="Incomplete").pack(side=tk.LEFT, padx=5)
        
        # ISO2GOD options frame
        iso_frame = ttk.LabelFrame(parent, text="ISO Processing Options")
        iso_frame.grid(row=3, column=0, sticky="ew", pady=5)
        
        # Convert to GOD option
        self.convert_god_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            iso_frame,
            text="Convert ISOs to GOD format after download",
            variable=self.convert_god_var
        ).pack(side=tk.LEFT, padx=5)
        
        # Thread count for GOD conversion
        thread_frame = ttk.Frame(iso_frame)
        thread_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(thread_frame, text="Threads:").pack(side=tk.LEFT)
        self.convert_god_threads_var = tk.StringVar(value=str(self.config.iso2god_threads))
        thread_spinbox = ttk.Spinbox(
            thread_frame,
            from_=1,
            to=15,
            textvariable=self.convert_god_threads_var,
            width=5,
            command=self._save_thread_count
        )
        thread_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Delete ISO after conversion option
        self.delete_iso_var = tk.BooleanVar(value=self.config.iso2god_delete_iso)
        ttk.Checkbutton(
            iso_frame,
            text="Delete ISO after GOD conversion",
            variable=self.delete_iso_var,
            command=lambda: self._save_iso2god_option('iso2god_delete_iso', self.delete_iso_var.get())
        ).pack(side=tk.LEFT, padx=5)
        
        # Trim ISO option
        self.trim_iso_var = tk.BooleanVar(value=self.config.iso2god_trim)
        ttk.Checkbutton(
            iso_frame,
            text="Trim ISOs",
            variable=self.trim_iso_var,
            command=lambda: self._save_iso2god_option('iso2god_trim', self.trim_iso_var.get())
        ).pack(side=tk.LEFT, padx=5)
        
        # File type selection
        type_frame = ttk.Frame(parent)
        type_frame.grid(row=4, column=0, sticky="ew", pady=5)
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
        
        # Store entry reference and add validation
        if "Download Location" in label_text:
            self.temp_dir_entry = entry
            entry.bind('<FocusOut>', lambda e: self._validate_and_create_dir(self.temp_dir_entry, 'temp_dir'))
            entry.bind('<Return>', lambda e: self._validate_and_create_dir(self.temp_dir_entry, 'temp_dir'))
        elif "Extract Location" in label_text:
            self.temp_extract_entry = entry
            entry.bind('<FocusOut>', lambda e: self._validate_and_create_dir(self.temp_extract_entry, 'temp_extract_dir'))
            entry.bind('<Return>', lambda e: self._validate_and_create_dir(self.temp_extract_entry, 'temp_extract_dir'))
        elif "Output Location" in label_text:
            self.output_dir_entry = entry
            entry.bind('<FocusOut>', lambda e: self._validate_and_create_dir(self.output_dir_entry, 'output_dir'))
            entry.bind('<Return>', lambda e: self._validate_and_create_dir(self.output_dir_entry, 'output_dir'))
            
        ttk.Button(parent, text="Browse", command=browse_command).grid(
            row=row, column=2, padx=5, pady=5)

    def _validate_and_create_dir(self, entry_widget: ttk.Entry, config_attr: str) -> None:
        """Validate directory path and create if it doesn't exist."""
        try:
            directory = entry_widget.get().strip()
            
            # Skip if empty
            if not directory:
                return
            
            # Expand user directory and environment variables
            directory = os.path.expanduser(directory)
            directory = os.path.expandvars(directory)
            
            # Convert to absolute path
            directory = os.path.abspath(directory)
            
            # Create directory if it doesn't exist
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                    self._update_status(f"Created directory: {directory}")
                except Exception as e:
                    messagebox.showerror(
                        "Error",
                        f"Failed to create directory:\n{directory}\n\nError: {str(e)}"
                    )
                    return
            
            # Update entry with normalized path
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, directory)
            
            # Update config
            setattr(self.config, config_attr, directory)
            self.config.save()
            
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Invalid directory path:\n{str(e)}"
            )

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
        
        # Add action buttons frame
        action_frame = ttk.Frame(button_frame)
        action_frame.pack(side=tk.RIGHT, padx=5)
        
        # Add validate button with description
        validate_frame = ttk.LabelFrame(parent, text="Links Validation", padding=5)
        validate_frame.pack(fill=tk.X, padx=5, pady=5)
        
        validate_desc = ("Check and fix issues in links.json:\n"
                        "• Missing or invalid fields\n"
                        "• ISO2GOD conversion status\n"
                        "• Processing and download status")
        ttk.Label(validate_frame, text=validate_desc, wraplength=400).pack(anchor="w", padx=5, pady=2)
        
        validate_button_frame = ttk.Frame(validate_frame)
        validate_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(validate_button_frame, text="Validate Links",
                  command=self._validate_links_manually).pack(side=tk.LEFT, padx=5)
        
        # Add other action buttons
        ttk.Button(action_frame, text="Generate/Update", 
                  command=self._process_links_txt).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Calculate Library Size", 
                  command=self._calculate_sizes).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Merge 2 Links.json Files", 
                  command=self._merge_links_file).pack(side=tk.LEFT, padx=5)

    def _validate_links_manually(self):
        """Manually validate and fix links.json."""
        try:
            # First check if links.json exists
            if not os.path.exists(self.config.links_file):
                messagebox.showerror(
                    "Error",
                    "links.json not found. Please generate it first using the URLs file."
                )
                return
            
            # Run validation
            validation_errors = []
            validation_warnings = []
            
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
                        
                        # Check for required URL field
                        if 'url' not in link:
                            validation_errors.append("• Missing URL in one or more links")
                            break
                        
                        # Check common fields
                        for field in self.LINK_SCHEMA['common']:
                            if field not in link:
                                validation_warnings.append(f"• Some links are missing the '{field}' field")
                        
                        # Check ISO-specific fields
                        if link.get('link_type', '').upper() == 'ISO':
                            for field in self.LINK_SCHEMA['iso']:
                                if field not in link:
                                    validation_warnings.append(f"• Some ISO files are missing the '{field}' field")
            
            if validation_errors:
                error_message = "The following errors were found:\n\n" + "\n".join(validation_errors)
                messagebox.showerror("Validation Errors", error_message)
                return
            
            if validation_warnings:
                # Remove duplicates while preserving order
                validation_warnings = list(dict.fromkeys(validation_warnings))
                
                warning_message = ("The following issues were found that can be fixed:\n\n" + 
                                 "\n".join(validation_warnings) +
                                 "\n\nWould you like to fix these issues now?")
                
                if messagebox.askyesno("Fix Issues", warning_message):
                    self._fix_links_issues()
            else:
                messagebox.showinfo(
                    "Validation Complete",
                    "No issues found in links.json. All required fields are present."
                )
            
        except json.JSONDecodeError:
            messagebox.showerror("Error", "links.json is not valid JSON")
        except Exception as e:
            messagebox.showerror("Error", f"Error validating links.json: {str(e)}")
    
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
                    def update_progress():
                        try:
                            self.progress_bar['value'] = msg
                            self.progress_label.config(text=f"Progress: {msg:.1f}%")
                            self.root.update_idletasks()
                        except Exception as e:
                            print(f"Error updating progress: {e}")
                    
                    # Schedule progress updates on main thread
                    self.root.after(0, update_progress)
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.log(f"Error updating progress: {e}")
        
        # Schedule next update with a longer delay to reduce GUI load
        self.root.after(100, self._update_progress)
    
    def _browse_temp(self) -> None:
        """Browse for temporary download directory."""
        directory = self._browse_directory("Select Temporary Download Directory")
        if directory:
            self.temp_dir_entry.delete(0, tk.END)
            self.temp_dir_entry.insert(0, directory)
            self._validate_and_create_dir(self.temp_dir_entry, 'temp_dir')
    
    def _browse_temp_extract(self) -> None:
        """Browse for temporary extraction directory."""
        directory = self._browse_directory("Select Temporary Extraction Directory")
        if directory:
            self.temp_extract_entry.delete(0, tk.END)
            self.temp_extract_entry.insert(0, directory)
            self._validate_and_create_dir(self.temp_extract_entry, 'temp_extract_dir')
    
    def _browse_output(self) -> None:
        """Browse for output directory."""
        directory = self._browse_directory("Select Output Directory")
        if directory:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, directory)
            self._validate_and_create_dir(self.output_dir_entry, 'output_dir')
    
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
            f"Batch Mode: {self.batch_mode_var.get()}\n"
            f"Batch Size: {self.config.batch_size}\n\n"
            f"Download Directory: {self.config.temp_dir}\n"
            f"Extract Directory: {self.config.temp_extract_dir}\n"
            f"Output Directory: {self.config.output_dir}\n\n"
            "Would you like to proceed?"
        )
        
        if not messagebox.askyesno("Confirm Processing", confirm_msg):
            return
        
        # Create directories if they don't exist
        try:
            os.makedirs(self.config.temp_dir, exist_ok=True)
            os.makedirs(self.config.temp_extract_dir, exist_ok=True)
            os.makedirs(self.config.output_dir, exist_ok=True)
        except Exception as e:
            self.logger.log(f"Error creating directories: {e}")
            messagebox.showerror("Error", f"Failed to create directories: {e}")
            return
        
        self._update_status("Starting processing...")
        self.processing = True
        self.start_button.config(state='disabled')
        self.progress_bar['value'] = 0
        
        # Start processing in a daemon thread
        processing_thread = threading.Thread(target=self._process_links, daemon=True)
        processing_thread.start()
    
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
                            
                            # Check for required URL field
                            if 'url' not in link:
                                validation_errors.append("• Missing URL in one or more links")
                                break
                            
                            # Check common fields
                            for field in self.LINK_SCHEMA['common']:
                                if field not in link:
                                    validation_warnings.append(f"• Some links are missing the '{field}' field")
                            
                            # Check ISO-specific fields
                            if link.get('link_type', '').upper() == 'ISO':
                                for field in self.LINK_SCHEMA['iso']:
                                    if field not in link:
                                        validation_warnings.append(f"• Some ISO files are missing the '{field}' field")
            
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
                return False
        
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
            fixed_links = []
            
            for link in links_data:
                if not isinstance(link, dict):
                    continue
                
                # Create a new link with all required fields
                fixed_link = {}
                
                # Add all common fields with their default values if missing
                for field, default_value in self.LINK_SCHEMA['common'].items():
                    fixed_link[field] = link.get(field, default_value)
                
                # If it's an ISO file, add ISO-specific fields
                if link.get('link_type', '').upper() == 'ISO':
                    for field, default_value in self.LINK_SCHEMA['iso'].items():
                        fixed_link[field] = link.get(field, default_value)
                
                # Check if any fields were added or modified
                if fixed_link != link:
                    modified = True
                
                fixed_links.append(fixed_link)
            
            if modified:
                with open(self.config.links_file, 'w', encoding='utf-8') as f:
                    json.dump(fixed_links, f, indent=4)
                
                self.logger.log("Fixed issues in links.json")
                messagebox.showinfo(
                    "Issues Fixed",
                    "The issues have been fixed. A backup of your original links.json "
                    f"has been saved as {backup_file}\n\n"
                    "You can now:\n"
                    "1. Use 'Estimate Library Size' to update missing file sizes\n"
                    "2. Start processing to download and extract files\n"
                    "3. Use the ISO2GOD tab to convert ISO files"
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
            self._update_status("Starting processing...")
            self._update_status("Loading links.json...")
            
            # Validate links.json exists
            if not os.path.exists(self.config.links_file):
                raise FileNotFoundError("links.json not found")
            
            # Load and validate links.json
            with open(self.config.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
                if not isinstance(links_data, list):
                    raise ValueError("Invalid links.json format")
            
            # Get selected link type
            link_type = self.link_type_var.get()
            convert_god = self.convert_god_var.get() and link_type == "ISO"
            
            if convert_god:
                self._update_status(f"Checking output directory for existing ISOs that need conversion...")
                # The link manager will handle checking and converting existing ISOs
            else:
                self._update_status(f"Processing {link_type} files...")
            
            # Get batch size and mode from GUI
            try:
                batch_size = int(self.batch_entry.get())
                batch_mode = self.batch_mode_var.get()
            except ValueError:
                raise ValueError("Invalid batch size")
            
            # Process the links
            self.link_manager.process_links(
                self.config.links_file,
                self.config.temp_dir,
                self.config.temp_extract_dir,
                self.config.output_dir,
                batch_size,  # Use the batch size from GUI
                self.progress_queue,
                self.filter_type_var.get(),
                convert_god=convert_god,
                delete_iso=self.delete_iso_var.get(),
                trim_iso=self.trim_iso_var.get(),
                batch_mode=batch_mode  # Pass the batch mode from GUI
            )
            
            self._update_status("Processing complete!")
            self.root.after(0, lambda: messagebox.showinfo("Success", "Processing completed successfully!"))
            
        except FileNotFoundError as e:
            error_msg = str(e)
            self.logger.log(f"File not found: {error_msg}")
            self._update_status(f"Error: {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"File not found: {error_msg}"))
        except json.JSONDecodeError as e:
            error_msg = "Invalid JSON format in links.json"
            self.logger.log(f"JSON error: {e}")
            self._update_status(f"Error: {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
        except Exception as e:
            self.logger.log(f"Error during processing: {str(e)}")
            self._update_status(f"Error: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Processing failed: {e}"))
        finally:
            self.processing = False
            self.root.after(0, lambda: self.start_button.config(state='normal'))
            self.root.after(0, lambda: self.progress_queue.put(("progress", 0)))
    
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
        desc_text = ("Manage your game library:\n"
                    "- Checkbox: Enable/disable games for processing\n"
                    "- Status: Shows download, extraction, and copy status\n"
                    "- Click column headers to sort\n"
                    "- Search using exact words (e.g., 'ace' won't match 'space')\n"
                    "- Disabled games will be skipped during processing")
        ttk.Label(header_frame, text=desc_text, wraplength=600).pack(anchor="w", pady=5)
        
        # Status count frame
        self.status_count_frame = ttk.Frame(container)
        self.status_count_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        
        # Control buttons frame
        button_frame = ttk.Frame(container)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        
        # Add generate names button
        ttk.Button(button_frame, text="Generate Game Names",
                  command=self._generate_game_names).pack(side=tk.LEFT, padx=5)
        
        # Add refresh button
        ttk.Button(button_frame, text="Refresh List",
                  command=self._load_games).pack(side=tk.LEFT, padx=5)
        
        # Add reset library button
        ttk.Button(button_frame, text="Reset Library Status",
                  command=self._reset_library_status).pack(side=tk.LEFT, padx=5)
        
        # Search and filter frame
        search_frame = ttk.Frame(container)
        search_frame.grid(row=3, column=0, sticky="ew", pady=(0, 5))
        
        # Search section
        search_section = ttk.LabelFrame(search_frame, text="Search Options")
        search_section.pack(fill=tk.X, padx=5, pady=2)
        
        # Search entry
        search_entry_frame = ttk.Frame(search_section)
        search_entry_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(search_entry_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.game_search_var = tk.StringVar()
        self.game_search_var.trace_add("write", self._filter_games)
        search_entry = ttk.Entry(search_entry_frame, textvariable=self.game_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # Search options
        options_frame = ttk.Frame(search_section)
        options_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Exact match option
        self.exact_match_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Exact Word Match",
                        variable=self.exact_match_var,
                        command=self._filter_games).pack(side=tk.LEFT, padx=5)
        
        # Search fields options
        ttk.Label(options_frame, text="Search in:").pack(side=tk.LEFT, padx=5)
        self.search_name_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Name",
                        variable=self.search_name_var,
                        command=self._filter_games).pack(side=tk.LEFT, padx=5)
        self.search_type_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Type",
                        variable=self.search_type_var,
                        command=self._filter_games).pack(side=tk.LEFT, padx=5)
        
        # Filter frame
        filter_frame = ttk.Frame(container)
        filter_frame.grid(row=4, column=0, sticky="ew", pady=(0, 5))
        
        self.game_filter_var = tk.StringVar(value="all")
        ttk.Radiobutton(filter_frame, text="All Games", variable=self.game_filter_var,
                       value="all", command=self._filter_games).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(filter_frame, text="Enabled Only", variable=self.game_filter_var,
                       value="enabled", command=self._filter_games).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(filter_frame, text="Disabled Only", variable=self.game_filter_var,
                       value="disabled", command=self._filter_games).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(filter_frame, text="Incomplete Only", variable=self.game_filter_var,
                       value="incomplete", command=self._filter_games).pack(side=tk.LEFT, padx=5)
        
        # Game list frame
        list_frame = ttk.Frame(container)
        list_frame.grid(row=5, column=0, sticky="nsew", pady=5)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        
        # Create Treeview for games with checkboxes
        columns = ('enabled', 'name', 'type', 'size', 'status')
        self.game_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        # Define headings with sort functionality
        self.game_tree.heading('enabled', text='Enabled', command=lambda: self._sort_tree('enabled'))
        self.game_tree.heading('name', text='Game Name', command=lambda: self._sort_tree('name'))
        self.game_tree.heading('type', text='Type', command=lambda: self._sort_tree('type'))
        self.game_tree.heading('size', text='Size', command=lambda: self._sort_tree('size'))
        self.game_tree.heading('status', text='Status', command=lambda: self._sort_tree('status'))
        
        # Define columns
        self.game_tree.column('enabled', width=60, anchor='center')
        self.game_tree.column('name', width=300)
        self.game_tree.column('type', width=100)
        self.game_tree.column('size', width=100)
        self.game_tree.column('status', width=200)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.game_tree.yview)
        self.game_tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid the tree and scrollbar
        self.game_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind events
        self.game_tree.bind('<ButtonRelease-1>', self._toggle_game)
        self.game_tree.bind('<space>', self._toggle_selected_games)  # Space to toggle
        self.game_tree.bind('<Return>', self._toggle_selected_games)  # Enter to toggle
        self.game_tree.bind('<Control-a>', self._select_all_games)  # Ctrl+A to select all
        self.game_tree.bind('<Control-d>', self._deselect_all_games)  # Ctrl+D to deselect all
        self.game_tree.bind('<Control-e>', lambda e: self._enable_disable_all(True))  # Ctrl+E to enable all
        self.game_tree.bind('<Control-x>', lambda e: self._enable_disable_all(False))  # Ctrl+X to disable all
        
        # Add keyboard shortcut hints to button tooltips
        self.enable_all_btn = ttk.Button(button_frame, text="Enable All (Ctrl+E)",
                                       command=lambda: self._enable_disable_all(True))
        self.enable_all_btn.pack(side=tk.LEFT, padx=5)
        
        self.disable_all_btn = ttk.Button(button_frame, text="Disable All (Ctrl+X)",
                                        command=lambda: self._enable_disable_all(False))
        self.disable_all_btn.pack(side=tk.LEFT, padx=5)
        
        # Add keyboard shortcuts help
        shortcuts_frame = ttk.LabelFrame(container, text="Keyboard Shortcuts")
        shortcuts_frame.grid(row=7, column=0, sticky="ew", padx=5, pady=5)
        
        shortcuts_text = (
            "Space/Enter: Toggle selected games\n"
            "Ctrl+A: Select all games\n"
            "Ctrl+D: Deselect all games\n"
            "Ctrl+E: Enable all games\n"
            "Ctrl+X: Disable all games\n"
            "↑/↓: Navigate games\n"
            "Type to search"
        )
        ttk.Label(shortcuts_frame, text=shortcuts_text).pack(padx=5, pady=5)
        
        # Control buttons frame
        button_frame = ttk.Frame(container)
        button_frame.grid(row=6, column=0, sticky="ew", pady=5)
        
        ttk.Button(button_frame, text="Enable All",
                  command=lambda: self._toggle_all_games(True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Disable All",
                  command=lambda: self._toggle_all_games(False)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Changes",
                  command=self._save_game_changes).pack(side=tk.RIGHT, padx=5)
        
        # Configure tag for hidden items
        self.game_tree.tag_configure('hidden', background='gray')
        
        # Initialize sort state
        self.sort_column = 'name'  # Default sort column
        self.sort_reverse = False  # Default sort direction
        
        # Load games
        self._load_games()

    def _toggle_selected_games(self, event=None):
        """Toggle enabled status of selected games."""
        selected_items = self.game_tree.selection()
        if not selected_items:
            return
        
        # Get the current state of the first selected item
        current_state = self.game_tree.set(selected_items[0], 'enabled')
        # Toggle to opposite state
        new_state = "☐" if current_state == "☑" else "☑"
        
        # Apply to all selected items
        for item in selected_items:
            self.game_tree.set(item, 'enabled', new_state)
        
        # Update status count
        self._update_status_count()

    def _select_all_games(self, event=None):
        """Select all visible games."""
        self.game_tree.selection_set(self.game_tree.get_children())

    def _deselect_all_games(self, event=None):
        """Deselect all games."""
        self.game_tree.selection_remove(self.game_tree.get_children())

    def _enable_disable_all(self, enable: bool):
        """Enable or disable all visible games."""
        for item in self.game_tree.get_children():
            self.game_tree.set(item, 'enabled', "☑" if enable else "☐")
        self._update_status_count()

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
                self._update_status_count()

    def _toggle_all_games(self, enable: bool):
        """Enable or disable all games in the list."""
        for item in self.game_tree.get_children():
            self.game_tree.set(item, 'enabled', "☑" if enable else "☐")

    def _filter_games(self, *args):
        """Filter games based on search text and filter type."""
        search_text = self.game_search_var.get().lower().strip()
        filter_type = self.game_filter_var.get()
        exact_match = self.exact_match_var.get()
        
        # First, reattach all items to make them available for filtering
        hidden_items = []
        for item in self.game_tree.get_children():
            hidden_items.append(item)
        for item in hidden_items:
            self.game_tree.reattach(item, '', 'end')
        
        # Now filter the items
        for item in self.game_tree.get_children():
            game_name = self.game_tree.set(item, 'name').lower()
            game_type = self.game_tree.set(item, 'type').lower()
            enabled = self.game_tree.set(item, 'enabled') == "☑"
            status = self.game_tree.set(item, 'status').lower()
            
            # Apply search filter
            matches_search = True
            if search_text:  # Only apply search filter if there's search text
                matches_name = matches_type = False
                
                # Split search text into words for multi-word search
                search_words = search_text.split()
                
                if self.search_name_var.get():
                    if exact_match:
                        # Match all words exactly
                        game_words = set(word.strip('()[]{}.,') for word in game_name.split())
                        matches_name = all(search_word in game_words for search_word in search_words)
                    else:
                        # Match all words anywhere in the name
                        matches_name = all(search_word in game_name for search_word in search_words)
                
                if self.search_type_var.get():
                    if exact_match:
                        game_type_words = set(game_type.split())
                        matches_type = all(search_word in game_type_words for search_word in search_words)
                    else:
                        matches_type = all(search_word in game_type for search_word in search_words)
                
                # Special category matching
                if any(category in search_text for category in ['sports', 'racing', 'action', 'rpg', 'shooter']):
                    category_matches = False
                    game_categories = self._get_game_categories(game_name, game_type)
                    for search_word in search_words:
                        if search_word in game_categories:
                            category_matches = True
                            break
                    matches_name = matches_name or category_matches
                
                matches_search = (self.search_name_var.get() and matches_name) or \
                               (self.search_type_var.get() and matches_type)
            
            # Apply type filter
            matches_type = False
            if filter_type == "all":
                matches_type = True
            elif filter_type == "enabled":
                matches_type = enabled
            elif filter_type == "disabled":
                matches_type = not enabled
            elif filter_type == "incomplete":
                matches_type = "complete" not in status and "disabled" not in status
            
            # Hide items that don't match
            if not (matches_search and matches_type):
                self.game_tree.detach(item)
        
        # Update status count to reflect filtered items
        self._update_status_count()

    def _get_game_categories(self, game_name: str, game_type: str) -> set:
        """Get categories for a game based on its name and type."""
        categories = set()
        
        # Sports games detection
        sports_keywords = {'sports', 'fifa', 'nba', 'nfl', 'mlb', 'hockey', 'tennis', 
                         'golf', 'wrestling', 'boxing', 'ufc', 'racing', 'soccer',
                         'football', 'baseball', 'basketball'}
        
        # Racing games detection
        racing_keywords = {'racing', 'race', 'cars', 'rally', 'drift', 'forza', 
                         'motorsport', 'bike', 'rider', 'drive', 'cart', 'speed'}
        
        # Action games detection
        action_keywords = {'action', 'fight', 'combat', 'warrior', 'battle', 'war',
                         'ninja', 'hero', 'adventure'}
        
        # RPG games detection
        rpg_keywords = {'rpg', 'role', 'fantasy', 'dragon', 'souls', 'elder', 
                       'scrolls', 'fallout', 'knights'}
        
        # Shooter games detection
        shooter_keywords = {'shooter', 'fps', 'combat', 'warfare', 'call of duty',
                          'battlefield', 'halo', 'gears', 'sniper'}
        
        # Convert game name to a set of words
        name_words = set(game_name.lower().split())
        
        # Check each category
        if any(keyword in game_name.lower() for keyword in sports_keywords):
            categories.add('sports')
        if any(keyword in game_name.lower() for keyword in racing_keywords):
            categories.add('racing')
        if any(keyword in game_name.lower() for keyword in action_keywords):
            categories.add('action')
        if any(keyword in game_name.lower() for keyword in rpg_keywords):
            categories.add('rpg')
        if any(keyword in game_name.lower() for keyword in shooter_keywords):
            categories.add('shooter')
            
        # Add game type as a category
        if game_type:
            categories.add(game_type.lower())
            
        return categories

    def _update_status(self, message: str) -> None:
        """Update the status text with a new message."""
        def _do_update():
            try:
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
                
                # Force GUI update
                self.root.update_idletasks()
            except Exception as e:
                print(f"Error updating status: {e}")
        
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

    def _update_status_count(self):
        """Update the status count display."""
        # Clear existing status labels
        for widget in self.status_count_frame.winfo_children():
            widget.destroy()
        
        # Count statuses (only for visible items)
        total = complete = disabled = in_progress = not_started = 0
        for item in self.game_tree.get_children():
            status = self.game_tree.set(item, 'status').lower()
            total += 1
            if "complete" in status:
                complete += 1
            elif "disabled" in status:
                disabled += 1
            elif "not started" in status:
                not_started += 1
            else:
                in_progress += 1
        
        # Create status labels with colors
        status_text = f"Showing: {total}  |  "
        status_text += f"Complete: {complete}  |  "
        status_text += f"In Progress: {in_progress}  |  "
        status_text += f"Not Started: {not_started}  |  "
        status_text += f"Disabled: {disabled}"
        
        ttk.Label(self.status_count_frame, text=status_text).pack(side=tk.LEFT, padx=5)

    def _sort_tree(self, col):
        """Sort treeview by column."""
        # Get all items
        items = [(self.game_tree.set(item, col), item) for item in self.game_tree.get_children()]
        
        # If clicking the same column, reverse the sort
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        
        # Sort items
        items.sort(reverse=self.sort_reverse)
        
        # Special handling for size column
        if col == 'size':
            items.sort(key=lambda x: float(x[0].split()[0]) if x[0] != "Unknown" else -1, 
                      reverse=self.sort_reverse)
        
        # Special handling for status column (custom order)
        elif col == 'status':
            def status_key(item):
                status = item[0].lower()
                if "complete" in status: return 0
                if "progress" in status: return 1
                if "not started" in status: return 2
                if "disabled" in status: return 3
                return 4
            items.sort(key=status_key, reverse=self.sort_reverse)
        
        # Rearrange items
        for index, (val, item) in enumerate(items):
            self.game_tree.move(item, '', index)
        
        # Update header arrows
        for column in ('enabled', 'name', 'type', 'size', 'status'):
            if column == col:
                arrow = " ▼" if self.sort_reverse else " ▲"
            else:
                arrow = ""
            self.game_tree.heading(column, text=column.title() + arrow)

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
                
                # Determine status
                status = []
                if not enabled:
                    status.append("Disabled")
                else:
                    # Check if all steps are complete
                    if game.get('copied', False):  # If copied is true, it means all previous steps were completed
                        status.append("Complete")
                    else:
                        # Show individual step status
                        if game.get('downloaded', False):
                            status.append("Downloaded")
                        if game.get('extracted', False):
                            status.append("Extracted")
                        if not any([game.get('downloaded', False), 
                                  game.get('extracted', False), 
                                  game.get('copied', False)]):
                            status.append("Not Started")
                
                status_text = " | ".join(status) if status else "Not Started"
                
                # Add color tags based on status
                if "Complete" in status_text:
                    status_text = "✓ " + status_text
                elif "Not Started" in status_text:
                    status_text = "○ " + status_text
                elif "Disabled" in status_text:
                    status_text = "✗ " + status_text
                else:
                    status_text = "⟳ " + status_text  # In progress
                
                self.game_tree.insert('', tk.END, values=(
                    "☑" if enabled else "☐",  # Checkbox
                    game_name,
                    game_type,
                    size_str,
                    status_text
                ))
            
            # Sort by name by inserting items in sorted order
            items = [(self.game_tree.set(item, 'name'), item) for item in self.game_tree.get_children()]
            for name, item in sorted(items):
                self.game_tree.move(item, '', 'end')
            
            # Force GUI update
            self.root.update_idletasks()
            
            # Update status count
            self._update_status_count()
            
            # Apply current filter
            self._filter_games()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load games: {str(e)}")

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

    def _setup_iso2god_tab(self, parent):
        """Set up the ISO2GOD conversion tab"""
        # Main container
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Header with description
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(
            header_frame,
            text="ISO to GOD Conversion",
            font=("Arial", 12, "bold")
        ).pack(anchor="w")
        
        desc_text = ("Convert ISO files to GOD format for Xbox 360.\n"
                    "• Select source directory containing ISO files\n"
                    "• Choose output directory for GOD files\n"
                    "• Configure conversion options\n"
                    "• Monitor progress in real-time")
        ttk.Label(header_frame, text=desc_text, wraplength=600).pack(anchor="w", pady=5)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Conversion Settings", padding="10")
        settings_frame.pack(fill="x", pady=(0, 10))
        
        # Input directory
        input_frame = ttk.Frame(settings_frame)
        input_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Label(input_frame, text="ISO Directory:").pack(side="left")
        self.iso_dir_var = tk.StringVar(value=getattr(self.config, 'iso_dir', ''))
        ttk.Entry(input_frame, textvariable=self.iso_dir_var, width=50).pack(side="left", padx=5)
        ttk.Button(
            input_frame,
            text="Browse",
            command=self._browse_iso_dir
        ).pack(side="left")
        
        # Output directory
        output_frame = ttk.Frame(settings_frame)
        output_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Label(output_frame, text="GOD Output:").pack(side="left")
        self.god_dir_var = tk.StringVar(value=getattr(self.config, 'god_dir', ''))
        ttk.Entry(output_frame, textvariable=self.god_dir_var, width=50).pack(side="left", padx=5)
        ttk.Button(
            output_frame,
            text="Browse",
            command=self._browse_god_dir
        ).pack(side="left")
        
        # Conversion options
        options_frame = ttk.LabelFrame(settings_frame, text="Options", padding=5)
        options_frame.pack(fill="x", pady=(5, 0))
        
        # Left side options
        left_options = ttk.Frame(options_frame)
        left_options.pack(side="left", padx=10)
        
        # Thread count
        thread_frame = ttk.Frame(left_options)
        thread_frame.pack(fill="x", pady=2)
        ttk.Label(thread_frame, text="Threads:").pack(side="left")
        
        # Get CPU core count for max threads
        cpu_count = multiprocessing.cpu_count()
        max_threads = min(15, cpu_count * 2)  # Allow up to 15 threads or 2x CPU cores
        optimal_threads = max(4, cpu_count - 1)  # Default to CPU cores - 1, minimum 4
        
        self.thread_count_var = tk.StringVar(value=str(optimal_threads))
        thread_spinbox = ttk.Spinbox(
            thread_frame,
            from_=1,
            to=max_threads,
            textvariable=self.thread_count_var,
            width=5
        )
        thread_spinbox.pack(side="left", padx=5)
        
        # Add CPU info tooltip
        cpu_info = f"CPU Cores: {cpu_count}\nRecommended: {optimal_threads} threads\nMax: {max_threads} threads"
        ttk.Label(thread_frame, text="ⓘ", cursor="hand2").pack(side="left")
        CreateToolTip(thread_frame, cpu_info)
        
        # Right side options
        right_options = ttk.Frame(options_frame)
        right_options.pack(side="left", padx=10)
        
        # Checkboxes for options
        self.trim_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            right_options,
            text="Trim ISO (reduce file size)",
            variable=self.trim_var
        ).pack(side="top", anchor="w")
        
        self.delete_iso_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            right_options,
            text="Delete ISO after successful conversion",
            variable=self.delete_iso_var
        ).pack(side="top", anchor="w")
        
        self.delete_source_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            right_options,
            text="Delete source folder after conversion",
            variable=self.delete_source_var
        ).pack(side="top", anchor="w")
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(
            control_frame,
            text="Start Conversion",
            command=self._start_conversion,
            style="Accent.TButton"
        ).pack(side="left", padx=5)
        
        ttk.Button(
            control_frame,
            text="Stop",
            command=self._stop_conversion
        ).pack(side="left", padx=5)
        
        ttk.Button(
            control_frame,
            text="Refresh List",
            command=self._refresh_iso_list
        ).pack(side="left", padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.pack(fill="both", expand=True)
        
        # Progress bar
        self.conversion_progress = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            length=100,
            mode="determinate"
        )
        self.conversion_progress.pack(fill="x", pady=(0, 5))
        
        # Status text
        self.conversion_status = ttk.Label(progress_frame, text="Ready")
        self.conversion_status.pack(fill="x")
        
        # Game list
        list_frame = ttk.Frame(progress_frame)
        list_frame.pack(fill="both", expand=True, pady=(5, 0))
        
        # Create treeview
        columns = ("game", "status", "size", "path")
        self.conversion_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="extended"
        )
        
        # Define headings
        self.conversion_tree.heading("game", text="Game", command=lambda: self._sort_conversion_list("game"))
        self.conversion_tree.heading("status", text="Status", command=lambda: self._sort_conversion_list("status"))
        self.conversion_tree.heading("size", text="Size", command=lambda: self._sort_conversion_list("size"))
        self.conversion_tree.heading("path", text="Path", command=lambda: self._sort_conversion_list("path"))
        
        # Define columns
        self.conversion_tree.column("game", width=300)
        self.conversion_tree.column("status", width=100)
        self.conversion_tree.column("size", width=100)
        self.conversion_tree.column("path", width=400)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.conversion_tree.yview
        )
        self.conversion_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack tree and scrollbar
        self.conversion_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind right-click menu
        self.conversion_tree.bind("<Button-3>", self._show_conversion_menu)
        
        # Create right-click menu
        self.conversion_menu = tk.Menu(self.root, tearoff=0)
        self.conversion_menu.add_command(label="Convert Selected", command=self._convert_selected)
        self.conversion_menu.add_command(label="Delete Selected", command=self._delete_selected_isos)
        self.conversion_menu.add_separator()
        self.conversion_menu.add_command(label="Open ISO Location", command=self._open_iso_location)
        self.conversion_menu.add_command(label="Open GOD Location", command=self._open_god_location)
        
        # Initial refresh of the list
        self._refresh_iso_list()

    def _refresh_iso_list(self):
        """Refresh the ISO list in the conversion tab."""
        # Clear existing items
        for item in self.conversion_tree.get_children():
            self.conversion_tree.delete(item)
        
        # Get ISO directory
        iso_dir = self.iso_dir_var.get()
        if not iso_dir or not os.path.exists(iso_dir):
            return
        
        # Find all ISO files
        for root, _, files in os.walk(iso_dir):
            for file in files:
                if file.lower().endswith('.iso'):
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    size_str = f"{size / (1024*1024*1024):.2f} GB"
                    
                    # Check if GOD version exists
                    god_dir = self.god_dir_var.get()
                    game_name = os.path.splitext(file)[0]
                    god_path = os.path.join(god_dir, game_name) if god_dir else None
                    
                    status = "Not Converted"
                    if god_path and os.path.exists(god_path):
                        god_files = [f for f in os.listdir(god_path) if f.endswith('.god')]
                        if god_files:
                            status = "Converted"
                    
                    self.conversion_tree.insert('', 'end', values=(
                        game_name,
                        status,
                        size_str,
                        file_path
                    ))

    def _sort_conversion_list(self, column):
        """Sort the conversion list by column."""
        # Get all items
        items = [(self.conversion_tree.set(item, column), item) for item in self.conversion_tree.get_children()]
        
        # Sort items
        items.sort(reverse=hasattr(self, 'sort_reverse') and self.sort_reverse)
        
        # Move items in sorted order
        for index, (_, item) in enumerate(items):
            self.conversion_tree.move(item, '', index)
        
        # Toggle sort direction
        self.sort_reverse = not getattr(self, 'sort_reverse', False)

    def _show_conversion_menu(self, event):
        """Show the right-click menu for the conversion tree."""
        # Get item under cursor
        item = self.conversion_tree.identify_row(event.y)
        if item:
            # Select the item if not already selected
            if item not in self.conversion_tree.selection():
                self.conversion_tree.selection_set(item)
            # Show menu
            self.conversion_menu.post(event.x_root, event.y_root)

    def _convert_selected(self):
        """Convert selected ISOs to GOD format."""
        selected = self.conversion_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select ISOs to convert")
            return
        
        # Get paths of selected items
        iso_paths = []
        for item in selected:
            values = self.conversion_tree.item(item)['values']
            if values[1] != "Converted":  # Only add if not already converted
                iso_paths.append(values[3])  # Path is in the fourth column
        
        if not iso_paths:
            messagebox.showinfo("Info", "All selected items are already converted")
            return
        
        # Start conversion
        self._start_conversion(iso_paths)

    def _delete_selected_isos(self):
        """Delete selected ISO files."""
        selected = self.conversion_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select ISOs to delete")
            return
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete",
                                 "Are you sure you want to delete the selected ISO files?\n"
                                 "This action cannot be undone."):
            return
        
        # Delete files
        deleted = 0
        errors = 0
        for item in selected:
            values = self.conversion_tree.item(item)['values']
            file_path = values[3]  # Path is in the fourth column
            try:
                os.remove(file_path)
                self.conversion_tree.delete(item)
                deleted += 1
            except Exception as e:
                errors += 1
                self._update_status(f"Error deleting {values[0]}: {str(e)}")
        
        # Show results
        self._update_status(f"Deleted {deleted} files, {errors} errors")
        if deleted > 0:
            self._refresh_iso_list()

    def _open_iso_location(self):
        """Open the location of the selected ISO file."""
        selected = self.conversion_tree.selection()
        if not selected:
            return
        
        values = self.conversion_tree.item(selected[0])['values']
        file_path = values[3]  # Path is in the fourth column
        os.startfile(os.path.dirname(file_path))

    def _open_god_location(self):
        """Open the GOD output location for the selected game."""
        selected = self.conversion_tree.selection()
        if not selected:
            return
        
        values = self.conversion_tree.item(selected[0])['values']
        game_name = values[0]  # Game name is in the first column
        god_path = os.path.join(self.god_dir_var.get(), game_name)
        
        if os.path.exists(god_path):
            os.startfile(god_path)
        else:
            messagebox.showinfo("Info", "GOD version not found for this game")

    def _start_conversion(self, specific_files=None):
        """Start the ISO to GOD conversion process."""
        if self.processing:
            messagebox.showwarning(
                "Processing in Progress",
                "A process is already running. Please wait for it to complete."
            )
            return

        # Validate directories
        iso_dir = self.iso_dir_var.get()
        god_dir = self.god_dir_var.get()
        
        if not iso_dir or not god_dir:
            messagebox.showerror(
                "Error",
                "Please select both input and output directories"
            )
            return
        
        # Get conversion settings
        try:
            num_threads = int(self.thread_count_var.get())
            if num_threads < 1 or num_threads > 15:  # Allow up to 15 threads
                raise ValueError("Thread count must be between 1 and 15")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        # Warn user about conversion duration
        if not messagebox.askyesno(
            "Conversion Time Warning",
            "Converting ISOs to GOD format is a very time-intensive process:\n\n"
            "• Each game can take 10+ minutes to convert\n"
            "• Larger games (8GB+) may take even longer\n"
            "• Using more threads can help but also uses more CPU\n"
            "• Your computer may run slower during conversion\n\n"
            "Are you sure you want to proceed with the conversion?"
        ):
            return
        
        # Create directories if they don't exist
        try:
            os.makedirs(iso_dir, exist_ok=True)
            os.makedirs(god_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create directories: {e}")
            return
        
        # Start conversion in a separate thread
        self.processing = True
        self.conversion_status.config(text="Starting conversion...")
        self.conversion_progress['value'] = 0
        
        # Start the conversion thread
        threading.Thread(
            target=self._run_conversion,
            args=(iso_dir, god_dir, num_threads, self.trim_var.get(), specific_files),
            daemon=True
        ).start()

    def _stop_conversion(self):
        """Stop the conversion process."""
        if hasattr(self, 'converter'):
            self.converter.stop()
            self._update_status("Conversion stopped")
            self.processing = False

    def _run_conversion(self, iso_dir: str, god_dir: str, num_threads: int, trim: bool, specific_files=None):
        """Run the conversion process in a separate thread."""
        try:
            # Create converter instance
            try:
                self.converter = ISO2GODConverter()
            except Exception as e:
                raise Exception(f"Failed to initialize ISO2GOD converter: {str(e)}")
            
            # Save directories to config
            self.config.iso_dir = iso_dir
            self.config.god_dir = god_dir
            self.config.save()
            
            # Get list of ISO files
            if specific_files:
                iso_files = [(os.path.basename(f), f) for f in specific_files]
            else:
                iso_files = [(f, os.path.join(iso_dir, f)) 
                            for f in os.listdir(iso_dir) 
                            if f.lower().endswith('.iso')]
            
            if not iso_files:
                self._update_status("No ISO files found to convert")
                messagebox.showinfo("Complete", "No ISO files found to convert")
                return
            
            # Process each ISO file
            total_files = len(iso_files)
            for i, (iso_name, iso_path) in enumerate(iso_files, 1):
                if not self.processing:  # Check if we should stop
                    break
                
                game_name = os.path.splitext(iso_name)[0]
                game_output_dir = os.path.join(god_dir, game_name)
                os.makedirs(game_output_dir, exist_ok=True)
                
                # Update tree status
                for item in self.conversion_tree.get_children():
                    if self.conversion_tree.item(item)['values'][0] == game_name:
                        self.conversion_tree.item(item, values=(
                            game_name,
                            "Converting...",
                            self.conversion_tree.item(item)['values'][2],
                            iso_path
                        ))
                        break
                
                # Convert the ISO
                self._update_status(f"Converting {iso_name} ({i}/{total_files})")
                try:
                    success = self.converter.convert_iso_to_god(
                        iso_path=iso_path,
                        output_dir=game_output_dir,
                        progress_queue=self.progress_queue,
                        num_threads=num_threads,
                        trim=trim
                    )
                except AttributeError as e:
                    raise Exception(f"ISO2GOD converter method not found: {str(e)}")
                except Exception as e:
                    raise Exception(f"Error during conversion: {str(e)}")
                
                # Update status in tree
                status = "Complete" if success else "Failed"
                for item in self.conversion_tree.get_children():
                    if self.conversion_tree.item(item)['values'][0] == game_name:
                        self.conversion_tree.item(item, values=(
                            game_name,
                            status,
                            self.conversion_tree.item(item)['values'][2],
                            iso_path
                        ))
                        break
                
                # Update overall progress
                progress = (i / total_files) * 100
                self.conversion_progress['value'] = progress
                self.conversion_status.config(text=f"Converting: {progress:.1f}%")
            
            if self.processing:  # If we didn't stop early
                self._update_status("Conversion complete!")
                messagebox.showinfo("Complete", "All ISO files have been converted")
            
        except Exception as e:
            error_msg = f"Conversion failed: {str(e)}"
            self._update_status(error_msg)
            messagebox.showerror("Error", error_msg)
        finally:
            self.processing = False
            self.conversion_progress['value'] = 0
            self.conversion_status.config(text="Ready")

    def _reset_library_status(self) -> None:
        """Reset all processing statuses in links.json to their initial state."""
        if not os.path.exists(self.config.links_file):
            messagebox.showerror("Error", "No links.json file found")
            return
            
        # Confirm with user
        if not messagebox.askyesno(
            "Confirm Reset",
            "This will reset ALL processing status in your library to their initial state:\n\n"
            "• Download status\n"
            "• Extraction status\n"
            "• Copy status\n"
            "• GOD conversion status\n"
            "• Import status\n\n"
            "This is useful for:\n"
            "• Starting fresh with a clean library\n"
            "• Creating a clean links.json to share\n"
            "• Troubleshooting processing issues\n\n"
            "A backup of your current links.json will be created.\n"
            "Would you like to proceed?"
        ):
            return
            
        try:
            # Create backup
            backup_file = f"{self.config.links_file}.bak"
            shutil.copy2(self.config.links_file, backup_file)
            
            # Load current links.json
            with open(self.config.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            # Reset status for each link
            for link in links_data:
                # Reset common fields
                link['processed'] = False
                link['downloaded'] = False
                link['extracted'] = False
                link['deleted'] = False
                link['copied'] = False
                link['imported'] = False
                link['import_date'] = None
                link['output_path'] = None
                
                # Reset ISO-specific fields if it's an ISO
                if link.get('link_type', '').upper() == 'ISO':
                    link['god_converted'] = False
                    link['god_conversion_date'] = None
                    link['god_output_path'] = None
                    link['god_conversion_error'] = None
                    link['god_conversion_progress'] = 0
                    link['god_conversion_started'] = False
                    link['god_conversion_completed'] = False
                
                # Keep enabled status and other metadata
                # This preserves user preferences while resetting processing status
            
            # Save updated links.json
            with open(self.config.links_file, 'w', encoding='utf-8') as f:
                json.dump(links_data, f, indent=4)
            
            self._update_status("Library status has been reset successfully")
            
            # Reload the games list to show updated status
            self._load_games()
            
            messagebox.showinfo(
                "Reset Complete",
                f"Library status has been reset successfully.\n\n"
                f"A backup of your previous links.json has been saved as:\n{backup_file}"
            )
            
        except Exception as e:
            self.logger.log(f"Error resetting library status: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to reset library status: {str(e)}\n\n"
                "Your original links.json has not been modified."
            )

    def _browse_iso_dir(self):
        """Browse for ISO directory."""
        directory = filedialog.askdirectory(title="Select ISO Directory")
        if directory:
            self.iso_dir_var.set(directory)
            setattr(self.config, 'iso_dir', directory)
            self.config.save()

    def _browse_god_dir(self):
        """Browse for GOD output directory."""
        directory = filedialog.askdirectory(title="Select GOD Output Directory")
        if directory:
            self.god_dir_var.set(directory)
            setattr(self.config, 'god_dir', directory)
            self.config.save()

    def _save_thread_count(self) -> None:
        """Save the thread count value to config."""
        try:
            thread_count = int(self.convert_god_threads_var.get())
            if 1 <= thread_count <= 8:  # Validate thread count range (1-8)
                self.config.iso2god_threads = thread_count
                self.config.save()
                self._update_status(f"Thread count updated to {thread_count}")
            else:
                self._update_status("Error: Thread count must be between 1 and 8")
                # Reset to last valid value
                self.convert_god_threads_var.set(str(self.config.iso2god_threads))
        except ValueError:
            self._update_status("Error: Invalid thread count value")
            # Reset to last valid value
            self.convert_god_threads_var.set(str(self.config.iso2god_threads))

class CreateToolTip(object):
    """Create a tooltip for a given widget."""
    def __init__(self, widget, text='widget info'):
        self.waittime = 500     # miliseconds
        self.wraplength = 180   # pixels
        self.widget = widget
        self.text = text
        self.widget.bind('<Enter>', self.enter)
        self.widget.bind('<Leave>', self.leave)
        self.widget.bind('<Button-1>', self.enter)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                      background="#ffffff", relief='solid', borderwidth=1,
                      wraplength = self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()