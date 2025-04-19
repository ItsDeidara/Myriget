import os
import requests
from typing import Optional
from queue import Queue

class FileDownloader:
    """Handles file downloading operations."""
    
    def __init__(self):
        """Initialize the downloader."""
        self.chunk_size = 8192
    
    def download(self, url: str, output_dir: str, progress_queue: Queue) -> Optional[str]:
        """Download a file from URL to output directory."""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Get filename from URL
            filename = os.path.basename(url)
            if not filename:
                filename = "downloaded_file"
            
            file_path = os.path.join(output_dir, filename)
            
            # Download file with progress updates
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Update progress
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            progress_queue.put(("progress", progress))
            
            progress_queue.put(("status", f"Downloaded {filename}"))
            return file_path
        
        except requests.exceptions.RequestException as e:
            progress_queue.put(("status", f"Error downloading {url}: {str(e)}"))
            return None
        
        except Exception as e:
            progress_queue.put(("status", f"Unexpected error downloading {url}: {str(e)}"))
            return None
    
    def get_file_size(self, url: str) -> Optional[int]:
        """Get the size of a file from URL without downloading it."""
        try:
            response = requests.head(url)
            response.raise_for_status()
            return int(response.headers.get('content-length', 0))
        except:
            return None
    
    def validate_url(self, url: str) -> bool:
        """Validate if a URL is accessible."""
        try:
            response = requests.head(url)
            return response.status_code == 200
        except:
            return False 