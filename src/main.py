#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from pathlib import Path
from gui.app import DownloaderApp

def ensure_directories():
    """Ensure all required directories exist."""
    # Get the base directory - use different logic for bundled exe vs. script
    if getattr(sys, 'frozen', False):
        # Running as bundled exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Create config directory
    config_dir = os.path.join(base_dir, 'src', 'config')
    os.makedirs(config_dir, exist_ok=True)
    
    # Create default directories that will be used
    default_dirs = [
        os.path.join(base_dir, 'downloads'),  # For temporary downloads
        os.path.join(base_dir, 'temp'),       # For temporary extraction
        os.path.join(base_dir, 'output'),     # For final output
        os.path.join(base_dir, 'output', 'god_converted'),  # For GOD conversions
        os.path.join(base_dir, 'logs')        # For log files
    ]
    
    for directory in default_dirs:
        os.makedirs(directory, exist_ok=True)
    
    # Create empty links.json if it doesn't exist
    links_file = os.path.join(config_dir, 'links.json')
    if not os.path.exists(links_file):
        with open(links_file, 'w', encoding='utf-8') as f:
            f.write('[]')
    
    # Create empty settings.json if it doesn't exist
    settings_file = os.path.join(config_dir, 'settings.json')
    if not os.path.exists(settings_file):
        default_settings = {
            "temp_dir": os.path.join(base_dir, 'downloads'),
            "temp_extract_dir": os.path.join(base_dir, 'temp'),
            "output_dir": os.path.join(base_dir, 'output'),
            "batch_size": 10240,  # 10GB default
            "batch_mode": "By Size (MB)",
            "filter_type": "Incomplete",
            "link_type": "ISO"
        }
        import json
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=4)
    
    return base_dir

def main():
    """Main entry point for the application."""
    try:
        # Ensure all directories exist
        base_dir = ensure_directories()
        
        # Create and run GUI
        root = tk.Tk()
        root.title("Myriget")
        
        # Set icon if available
        icon_path = os.path.join(base_dir, 'src', 'gui', 'assets', 'icon.ico')
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
        
        # Create app
        app = DownloaderApp(root)
        
        # Center window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'+{x}+{y}')
        
        # Start main loop
        root.mainloop()
        
    except Exception as e:
        import traceback
        error_msg = f"Fatal Error: {str(e)}\n\n{traceback.format_exc()}"
        
        # Try to show error in GUI
        try:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Fatal Error", error_msg)
        except:
            # Fallback to console
            print(error_msg)
        
        # Create error log
        try:
            log_dir = os.path.join(base_dir, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'error.log'), 'a', encoding='utf-8') as f:
                f.write(f"\n{'-'*50}\n{error_msg}\n")
        except:
            pass
        
        sys.exit(1)

if __name__ == '__main__':
    main() 