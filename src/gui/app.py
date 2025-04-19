import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
import webbrowser
from typing import Optional, Dict, Any
import os

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
        
        self.expanded = True
        
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
        self.root.title("File Downloader and Extractor")
        
        # Set minimum window size
        self.root.minsize(800, 600)
        
        # Configure styles
        self._configure_styles()
        
        # Initialize components
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
        
        # Setup GUI
        self._setup_gui()
        
        # Update GUI fields with loaded config
        self._update_gui_from_config()
        
        # Start progress update loop
        self._start_progress_updates()
    
    def _configure_styles(self):
        """Configure custom styles for the application."""
        style = ttk.Style()
        style.configure("Hover.TFrame", background="#f0f0f0")
        style.configure("TFrame", background="white")
        style.configure("TLabel", padding=5)
        style.configure("TButton", padding=5)
        style.configure("TEntry", padding=5)
    
    def _update_gui_from_config(self) -> None:
        """Update GUI fields with loaded configuration values."""
        # Update directory entries
        self.temp_dir_entry.delete(0, tk.END)
        self.temp_dir_entry.insert(0, self.config.temp_dir)
        
        self.temp_extract_entry.delete(0, tk.END)
        self.temp_extract_entry.insert(0, self.config.temp_extract_dir)
        
        self.output_dir_entry.delete(0, tk.END)
        self.output_dir_entry.insert(0, self.config.output_dir)
        
        # Update links entry
        self.links_entry.delete(0, tk.END)
        self.links_entry.insert(0, self.config.links_file)
        
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
        # Create main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create main tab
        main_tab = ttk.Frame(self.notebook)
        self.notebook.add(main_tab, text="Main")
        
        # Create settings tab
        settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(settings_tab, text="Settings")
        
        # Setup frames in main tab
        self._setup_directory_frame(main_tab)
        self._setup_links_frame(main_tab)
        self._setup_batch_frame(main_tab)
        self._setup_progress_frame(main_tab)
        self._setup_status_frame(main_tab)
        self._setup_start_button(main_tab)
        
        # Setup frames in settings tab
        self._setup_import_frame(settings_tab)
        self._setup_size_calculation_frame(settings_tab)
        self._setup_secret_button(settings_tab)
    
    def _setup_directory_frame(self, parent: tk.Widget) -> None:
        """Setup the directory settings frame."""
        dir_frame = ExpandableFrame(parent, text="Directory Settings")
        dir_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Add directory controls
        self._add_directory_control(dir_frame.content, "Temporary Download Location (SSD):", 
                                  self.config.temp_dir, self._browse_temp, 0)
        self._add_directory_control(dir_frame.content, "Temporary Extraction Location (SSD):", 
                                  self.config.temp_extract_dir, self._browse_temp_extract, 1)
        self._add_directory_control(dir_frame.content, "Final Output Location (Slow Drive):", 
                                  self.config.output_dir, self._browse_output, 2)
    
    def _setup_links_frame(self, parent: tk.Widget) -> None:
        """Setup the links settings frame."""
        links_frame = ExpandableFrame(parent, text="Links JSON Generator")
        links_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Add description
        desc_text = "Generate or update links.json from a text file containing URLs (one per line)"
        desc_label = ttk.Label(links_frame.content, text=desc_text, wraplength=400)
        desc_label.pack(anchor="w", padx=5, pady=5)
        
        # Add links controls
        self._add_links_control(links_frame.content)
    
    def _setup_batch_frame(self, parent: tk.Widget) -> None:
        """Setup the batch settings frame."""
        batch_frame = ExpandableFrame(parent, text="Batch Settings")
        batch_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Add batch controls
        self._add_batch_control(batch_frame.content)
    
    def _setup_progress_frame(self, parent: tk.Widget) -> None:
        """Setup the progress display frame."""
        progress_frame = ExpandableFrame(parent, text="Progress")
        progress_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Add progress bar
        self.progress_bar = ttk.Progressbar(progress_frame.content, length=300, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_label = ttk.Label(progress_frame.content, text="Progress: 0%")
        self.progress_label.pack(pady=5, padx=5)
    
    def _setup_status_frame(self, parent: tk.Widget) -> None:
        """Setup the status display frame."""
        status_frame = ExpandableFrame(parent, text="Status")
        status_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Add status text
        self.status_text = tk.Text(status_frame.content, width=60, height=4, wrap=tk.WORD)
        self.status_text.pack(fill=tk.X, padx=5, pady=5)
        self.status_text.config(state='disabled')
    
    def _setup_size_calculation_frame(self, parent: tk.Widget) -> None:
        """Setup the size calculation frame."""
        size_frame = ExpandableFrame(parent, text="Library Size Calculator")
        size_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Size calculation button
        ttk.Button(size_frame.content, text="Calculate Library Sizes", 
                  command=self._calculate_sizes).pack(padx=5, pady=5, anchor="w")
        
        # Size information display
        self.size_info_text = tk.Text(size_frame.content, width=80, height=12, wrap=tk.WORD)
        self.size_info_text.pack(fill=tk.X, padx=5, pady=5)
        self.size_info_text.config(state='disabled')
        
        # Update size info display
        self._update_size_info()
    
    def _setup_import_frame(self, parent: tk.Widget) -> None:
        """Setup the import controls frame."""
        import_frame = ExpandableFrame(parent, text="Import Links.json")
        import_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Add import controls
        self._add_import_control(import_frame.content)
    
    def _setup_start_button(self, parent: tk.Widget) -> None:
        """Setup the start processing button."""
        self.start_button = ttk.Button(parent, text="Start Processing", 
                                     command=self._start_processing)
        self.start_button.pack(pady=10)
    
    def _setup_secret_button(self, parent: tk.Widget) -> None:
        """Setup the secret pastebin button."""
        self.secret_button = ttk.Button(parent, text="?", width=1, 
                                      command=self._open_pastebin)
        self.secret_button.pack(padx=5, pady=5, anchor="e")
    
    def _add_directory_control(self, parent: tk.Widget, label_text: str, 
                             default_value: str, browse_command: callable, 
                             row: int) -> None:
        """Add a directory control to the frame."""
        tk.Label(parent, text=label_text).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        entry = tk.Entry(parent, width=50)
        entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
        entry.insert(0, default_value)
        
        # Store entry reference
        if "Temporary Download" in label_text:
            self.temp_dir_entry = entry
        elif "Temporary Extraction" in label_text:
            self.temp_extract_entry = entry
        elif "Final Output" in label_text:
            self.output_dir_entry = entry
            
        tk.Button(parent, text="Browse", command=browse_command).grid(
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
        type_desc = "Select the type of files in your URLs list:"
        ttk.Label(type_frame, text=type_desc).pack(anchor="w", padx=5, pady=2)
        
        self.link_type_import_var = tk.StringVar(value="ISO")
        ttk.Radiobutton(type_frame, text="ISO", variable=self.link_type_import_var,
                       value="ISO").pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Radiobutton(type_frame, text="XBLA", variable=self.link_type_import_var,
                       value="XBLA").pack(side=tk.LEFT, padx=5, pady=5)
        
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
        
        # Add generate button
        ttk.Button(button_frame, text="Generate/Update", command=self._process_links_txt).pack(
            side=tk.RIGHT, padx=5, pady=5)
    
    def _add_batch_control(self, parent: tk.Widget) -> None:
        """Add batch size control to the frame."""
        # Batch size entry
        tk.Label(parent, text="Batch Size:").pack(side=tk.LEFT, padx=5, pady=5)
        self.batch_entry = tk.Entry(parent, width=10)
        self.batch_entry.pack(side=tk.LEFT, padx=5, pady=5)
        self.batch_entry.insert(0, str(self.config.batch_size))
        
        # Batch mode selection
        self.batch_mode_var = tk.StringVar(value=self.config.batch_mode)
        tk.Radiobutton(parent, text="By Number", variable=self.batch_mode_var,
                      value="By Number").pack(side=tk.LEFT, padx=5, pady=5)
        tk.Radiobutton(parent, text="By Size (MB)", variable=self.batch_mode_var,
                      value="By Size (MB)").pack(side=tk.LEFT, padx=5, pady=5)
        
        # Add separator
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Processing Mode section
        mode_frame = tk.Frame(parent)
        mode_frame.pack(fill=tk.X, pady=5)
        
        # Processing Mode label
        tk.Label(mode_frame, text="Processing Mode:", font=("Arial", 10, "bold")).pack(
            anchor="w", pady=(0, 5))
        
        # Processing Mode description
        desc_text = "Choose which files to process:\n" \
                   "- All: Process every file in the list\n" \
                   "- Incomplete: Only process files that haven't been copied yet"
        desc_label = tk.Label(mode_frame, text=desc_text, justify=tk.LEFT, wraplength=400)
        desc_label.pack(anchor="w", pady=(0, 10))
        
        # Filter type selection
        self.filter_type_var = tk.StringVar(value=self.config.filter_type)
        tk.Radiobutton(mode_frame, text="All Files", variable=self.filter_type_var,
                      value="All").pack(side=tk.LEFT, padx=5, pady=5)
        tk.Radiobutton(mode_frame, text="Incomplete Only", variable=self.filter_type_var,
                      value="Incomplete").pack(side=tk.LEFT, padx=5, pady=5)
        
        # Add separator
        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # File Type section
        type_frame = tk.Frame(parent)
        type_frame.pack(fill=tk.X, pady=5)
        
        # File Type label
        tk.Label(type_frame, text="File Type:", font=("Arial", 10, "bold")).pack(
            anchor="w", pady=(0, 5))
        
        # File Type description
        type_desc = "Select the type of files to process:\n" \
                   "- ISO: Process ISO image files\n" \
                   "- XBLA: Process Xbox Live Arcade files"
        type_desc_label = tk.Label(type_frame, text=type_desc, justify=tk.LEFT, wraplength=400)
        type_desc_label.pack(anchor="w", pady=(0, 10))
        
        # Link type selection
        self.link_type_var = tk.StringVar(value=self.config.link_type)
        tk.Radiobutton(type_frame, text="ISO", variable=self.link_type_var,
                      value="ISO").pack(side=tk.LEFT, padx=5, pady=5)
        tk.Radiobutton(type_frame, text="XBLA", variable=self.link_type_var,
                      value="XBLA").pack(side=tk.LEFT, padx=5, pady=5)
    
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
                    self.status_text.config(state='normal')
                    self.status_text.insert(tk.END, msg + "\n")
                    self.status_text.see(tk.END)
                    self.status_text.config(state='disabled')
                elif msg_type == "progress":
                    self.progress_bar['value'] = msg
                    self.progress_label.config(text=f"Progress: {msg:.1f}%")
        except queue.Empty:
            pass
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
            return
        
        if not self._validate_settings():
            return
        
        self.processing = True
        self.start_button.config(state='disabled')
        self.progress_bar['value'] = 0
        
        threading.Thread(target=self._process_links, daemon=True).start()
    
    def _validate_settings(self) -> bool:
        """Validate application settings."""
        if not self.config.temp_dir or not os.path.exists(self.config.temp_dir):
            self.logger.log("Error: Invalid or missing temporary download directory.")
            messagebox.showerror("Error", "Please select a valid temporary download directory.")
            return False
        
        if not self.config.temp_extract_dir or not os.path.exists(self.config.temp_extract_dir):
            self.logger.log("Error: Invalid or missing temporary extraction directory.")
            messagebox.showerror("Error", "Please select a valid temporary extraction directory.")
            return False
        
        if not self.config.output_dir or not os.path.exists(self.config.output_dir):
            self.logger.log("Error: Invalid or missing output directory.")
            messagebox.showerror("Error", "Please select a valid output directory.")
            return False
        
        if not self.config.links_file or not os.path.exists(self.config.links_file):
            self.logger.log("Error: No links file found.")
            messagebox.showerror("Error", "Please select a valid links file.")
            return False
        
        return True
    
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
                self.link_type_import_var.get(),  # Pass the selected file type
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