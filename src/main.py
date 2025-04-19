import tkinter as tk
from gui.app import DownloaderApp

def main():
    """Main entry point for the application."""
    root = tk.Tk()
    app = DownloaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 