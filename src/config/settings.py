import os
import json
from typing import Optional
from datetime import datetime

class AppConfig:
    """Application configuration management."""
    
    def __init__(self):
        """Initialize configuration with default values."""
        # Get the directory where the script is running
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.config_dir = os.path.dirname(__file__)
        self.config_file = os.path.join(self.config_dir, "config.json")
        
        # Default directories
        self.temp_dir = os.path.join(self.base_dir, "tempDownload")
        self.temp_extract_dir = os.path.join(self.base_dir, "tempExtract")
        self.output_dir = os.path.join(self.base_dir, "output")
        
        # Default values
        self.links_file = os.path.join(self.config_dir, "links.json")
        self.batch_size = 500
        self.batch_size_mb = 10000
        self.copy_timeout = 3600
        self.per_file_timeout = 300
        self.delete_after_copy = True
        self.batch_mode = "By Size (MB)"
        self.filter_type = "All"
        self.link_type = "ISO"
        
        # Library size tracking
        self.iso_size_gb = 0.0
        self.xbla_size_gb = 0.0
        self.xbla_addons_size_gb = 0.0
        self.last_size_check = None
        self.missing_size_iso = 0
        self.missing_size_xbla = 0
        self.missing_size_xbla_addons = 0
        
        # Create default config if it doesn't exist
        if not os.path.exists(self.config_file):
            self._create_default_config()
            self._create_default_directories()
            self._create_default_links_file()
    
    def _create_default_links_file(self) -> None:
        """Create default links.json file if it doesn't exist."""
        try:
            if not os.path.exists(self.links_file):
                default_links = []
                with open(self.links_file, 'w', encoding='utf-8') as f:
                    json.dump(default_links, f, indent=4)
                print(f"Created default links.json at {self.links_file}")
        except Exception as e:
            print(f"Error creating default links.json: {e}")
    
    def calculate_library_sizes(self) -> None:
        """Calculate and store the total size of ISO, XBLA, and XBLA Addons files."""
        try:
            if not os.path.exists(self.links_file):
                print("Links file not found. Cannot calculate library sizes.")
                return
            
            with open(self.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            iso_size_bytes = 0
            xbla_size_bytes = 0
            xbla_addons_size_bytes = 0
            total_iso = 0
            total_xbla = 0
            total_xbla_addons = 0
            self.missing_size_iso = 0
            self.missing_size_xbla = 0
            self.missing_size_xbla_addons = 0
            
            print(f"\nAnalyzing {len(links_data)} links...")
            
            for link in links_data:
                # Get size in bytes and link type
                size_bytes = link.get('size_bytes', 0)
                link_type = link.get('link_type', 'Unknown')
                
                if link_type == 'ISO':
                    total_iso += 1
                    if not size_bytes:
                        self.missing_size_iso += 1
                        print(f"Found ISO missing size: {os.path.basename(link['url'])}")
                    else:
                        iso_size_bytes += size_bytes
                        print(f"Found ISO with size: {size_bytes/1024/1024/1024:.2f} GB")
                elif link_type == 'XBLA':
                    total_xbla += 1
                    if not size_bytes:
                        self.missing_size_xbla += 1
                        print(f"Found XBLA missing size: {os.path.basename(link['url'])}")
                    else:
                        xbla_size_bytes += size_bytes
                        print(f"Found XBLA with size: {size_bytes/1024/1024/1024:.2f} GB")
                elif link_type == 'XBLA Addons':
                    total_xbla_addons += 1
                    if not size_bytes:
                        self.missing_size_xbla_addons += 1
                        print(f"Found XBLA Addon missing size: {os.path.basename(link['url'])}")
                    else:
                        xbla_addons_size_bytes += size_bytes
                        print(f"Found XBLA Addon with size: {size_bytes/1024/1024/1024:.2f} GB")
            
            # Convert to GB (1 GB = 1024^3 bytes)
            self.iso_size_gb = iso_size_bytes / (1024 ** 3)
            self.xbla_size_gb = xbla_size_bytes / (1024 ** 3)
            self.xbla_addons_size_gb = xbla_addons_size_bytes / (1024 ** 3)
            self.last_size_check = datetime.now().isoformat()
            
            # Save the updated sizes
            self.save()
            
            print(f"\nLibrary Size Check ({datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}):")
            print(f"ISO Library: {self.iso_size_gb:.2f} GB ({total_iso - self.missing_size_iso}/{total_iso} files with size info)")
            print(f"XBLA Library: {self.xbla_size_gb:.2f} GB ({total_xbla - self.missing_size_xbla}/{total_xbla} files with size info)")
            print(f"XBLA Addons: {self.xbla_addons_size_gb:.2f} GB ({total_xbla_addons - self.missing_size_xbla_addons}/{total_xbla_addons} files with size info)")
            print(f"Total: {(self.iso_size_gb + self.xbla_size_gb + self.xbla_addons_size_gb):.2f} GB")
            
            if self.missing_size_iso > 0 or self.missing_size_xbla > 0 or self.missing_size_xbla_addons > 0:
                print("\nMissing Size Information:")
                if self.missing_size_iso > 0:
                    print(f"- ISO: {self.missing_size_iso} files missing size information")
                if self.missing_size_xbla > 0:
                    print(f"- XBLA: {self.missing_size_xbla} files missing size information")
                if self.missing_size_xbla_addons > 0:
                    print(f"- XBLA Addons: {self.missing_size_xbla_addons} files missing size information")
        
        except Exception as e:
            print(f"Error calculating library sizes: {e}")
            print(f"Error details: {str(e)}")
            print(f"Links file path: {self.links_file}")
            if os.path.exists(self.links_file):
                with open(self.links_file, 'r') as f:
                    first_few_lines = ''.join(f.readlines()[:10])
                print(f"First few lines of links.json:\n{first_few_lines}")
                print(f"Links file exists and is {os.path.getsize(self.links_file)} bytes")
    
    def get_library_size_info(self) -> str:
        """Get formatted string with library size information."""
        if not self.last_size_check:
            return "Library sizes have not been calculated yet."
        
        last_check = datetime.fromisoformat(self.last_size_check)
        total_size = self.iso_size_gb + self.xbla_size_gb + self.xbla_addons_size_gb
        info = [
            f"Library Size Information (Last checked: {last_check.strftime('%Y-%m-%d %I:%M:%S %p')})",
            "",
            f"ISO Library: {self.iso_size_gb:.2f} GB",
            f"XBLA Library: {self.xbla_size_gb:.2f} GB",
            f"XBLA Addons: {self.xbla_addons_size_gb:.2f} GB",
            f"Total: {total_size:.2f} GB",
            "",
            "Missing Size Information:",
            f"- ISO: {self.missing_size_iso if hasattr(self, 'missing_size_iso') else 0} files missing size information",
            f"- XBLA: {self.missing_size_xbla if hasattr(self, 'missing_size_xbla') else 0} files missing size information",
            f"- XBLA Addons: {self.missing_size_xbla_addons if hasattr(self, 'missing_size_xbla_addons') else 0} files missing size information",
            "",
            "Storage Recommendations:",
            f"- Total Required: {total_size:.2f} GB",
            f"- Recommended Free Space: {(total_size * 1.2):.2f} GB (20% buffer)",
            f"- ISO Library: {self.iso_size_gb:.2f} GB",
            f"- XBLA Library: {self.xbla_size_gb:.2f} GB",
            f"- XBLA Addons: {self.xbla_addons_size_gb:.2f} GB"
        ]
        return "\n".join(info)
    
    def _create_default_config(self) -> None:
        """Create default configuration file."""
        try:
            config = {
                "temp_dir": self.temp_dir,
                "temp_extract_dir": self.temp_extract_dir,
                "output_dir": self.output_dir,
                "links_file": self.links_file,
                "batch_size": self.batch_size,
                "batch_size_mb": self.batch_size_mb,
                "copy_timeout": self.copy_timeout,
                "per_file_timeout": self.per_file_timeout,
                "delete_after_copy": self.delete_after_copy,
                "batch_mode": self.batch_mode,
                "filter_type": self.filter_type,
                "link_type": self.link_type,
                "iso_size_gb": self.iso_size_gb,
                "xbla_size_gb": self.xbla_size_gb,
                "xbla_addons_size_gb": self.xbla_addons_size_gb,
                "last_size_check": self.last_size_check,
                "missing_size_iso": getattr(self, 'missing_size_iso', 0),
                "missing_size_xbla": getattr(self, 'missing_size_xbla', 0),
                "missing_size_xbla_addons": getattr(self, 'missing_size_xbla_addons', 0)
            }
            
            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            
            print(f"Created default configuration at {self.config_file}")
        
        except Exception as e:
            print(f"Error creating default config: {e}")
    
    def _create_default_directories(self) -> None:
        """Create default directories if they don't exist."""
        try:
            # Create temp directories
            os.makedirs(self.temp_dir, exist_ok=True)
            os.makedirs(self.temp_extract_dir, exist_ok=True)
            
            # Create output directory
            os.makedirs(self.output_dir, exist_ok=True)
            
            print(f"Created default directories:")
            print(f"- Temporary Download: {self.temp_dir}")
            print(f"- Temporary Extract: {self.temp_extract_dir}")
            print(f"- Output: {self.output_dir}")
        
        except Exception as e:
            print(f"Error creating default directories: {e}")
    
    def load(self) -> None:
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.temp_dir = config.get("temp_dir", self.temp_dir)
                    self.temp_extract_dir = config.get("temp_extract_dir", self.temp_extract_dir)
                    self.output_dir = config.get("output_dir", self.output_dir)
                    self.links_file = config.get("links_file", self.links_file)
                    self.batch_size = config.get("batch_size", self.batch_size)
                    self.batch_size_mb = config.get("batch_size_mb", self.batch_size_mb)
                    self.copy_timeout = config.get("copy_timeout", self.copy_timeout)
                    self.per_file_timeout = config.get("per_file_timeout", self.per_file_timeout)
                    self.delete_after_copy = config.get("delete_after_copy", self.delete_after_copy)
                    self.batch_mode = config.get("batch_mode", self.batch_mode)
                    self.filter_type = config.get("filter_type", self.filter_type)
                    self.link_type = config.get("link_type", self.link_type)
                    self.iso_size_gb = config.get("iso_size_gb", self.iso_size_gb)
                    self.xbla_size_gb = config.get("xbla_size_gb", self.xbla_size_gb)
                    self.xbla_addons_size_gb = config.get("xbla_addons_size_gb", self.xbla_addons_size_gb)
                    self.last_size_check = config.get("last_size_check", self.last_size_check)
                    self.missing_size_iso = config.get("missing_size_iso", 0)
                    self.missing_size_xbla = config.get("missing_size_xbla", 0)
                    self.missing_size_xbla_addons = config.get("missing_size_xbla_addons", 0)
            else:
                print("No config file found, using default values")
                self.calculate_library_sizes()  # Calculate sizes on first load
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save(self) -> None:
        """Save configuration to file."""
        try:
            config = {
                "temp_dir": self.temp_dir,
                "temp_extract_dir": self.temp_extract_dir,
                "output_dir": self.output_dir,
                "links_file": self.links_file,
                "batch_size": self.batch_size,
                "batch_size_mb": self.batch_size_mb,
                "copy_timeout": self.copy_timeout,
                "per_file_timeout": self.per_file_timeout,
                "delete_after_copy": self.delete_after_copy,
                "batch_mode": self.batch_mode,
                "filter_type": self.filter_type,
                "link_type": self.link_type,
                "iso_size_gb": self.iso_size_gb,
                "xbla_size_gb": self.xbla_size_gb,
                "xbla_addons_size_gb": self.xbla_addons_size_gb,
                "last_size_check": self.last_size_check,
                "missing_size_iso": self.missing_size_iso,
                "missing_size_xbla": self.missing_size_xbla,
                "missing_size_xbla_addons": self.missing_size_xbla_addons
            }
            
            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def validate(self) -> bool:
        """Validate configuration values."""
        if not self.temp_dir or not os.path.exists(self.temp_dir):
            return False
        if not self.temp_extract_dir or not os.path.exists(self.temp_extract_dir):
            return False
        if not self.output_dir or not os.path.exists(self.output_dir):
            return False
        if not self.links_file or not os.path.exists(self.links_file):
            return False
        if self.batch_size <= 0:
            return False
        if self.batch_size_mb <= 0:
            return False
        if self.copy_timeout <= 0:
            return False
        if self.per_file_timeout <= 0:
            return False
        return True 