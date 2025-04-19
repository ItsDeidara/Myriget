import os
import shutil
from typing import Optional
from queue import Queue

class FileCopier:
    """Handles file copying operations."""
    
    def __init__(self):
        """Initialize the copier."""
        self.chunk_size = 8192
    
    def copy(self, source_dir: str, dest_dir: str, progress_queue: Queue) -> bool:
        """Copy files from source directory to destination directory."""
        try:
            # Create destination directory if it doesn't exist
            os.makedirs(dest_dir, exist_ok=True)
            
            # Get total size for progress tracking
            total_size = self._get_total_size(source_dir)
            copied_size = 0
            
            # Copy files
            for root, _, files in os.walk(source_dir):
                for file in files:
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(root, source_dir)
                    dst_dir = os.path.join(dest_dir, rel_path)
                    os.makedirs(dst_dir, exist_ok=True)
                    dst_path = os.path.join(dst_dir, file)
                    
                    # Copy file with progress updates
                    self._copy_file(src_path, dst_path, progress_queue)
                    
                    # Update progress
                    file_size = os.path.getsize(src_path)
                    copied_size += file_size
                    if total_size > 0:
                        progress = (copied_size / total_size) * 100
                        progress_queue.put(("progress", progress))
            
            progress_queue.put(("status", "Copy complete"))
            return True
        
        except Exception as e:
            progress_queue.put(("status", f"Error copying files: {str(e)}"))
            return False
    
    def _copy_file(self, src_path: str, dst_path: str, progress_queue: Queue) -> None:
        """Copy a single file with progress updates."""
        try:
            file_size = os.path.getsize(src_path)
            copied_size = 0
            
            with open(src_path, 'rb') as src, open(dst_path, 'wb') as dst:
                while True:
                    chunk = src.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    dst.write(chunk)
                    copied_size += len(chunk)
                    
                    # Update progress for this file
                    progress = (copied_size / file_size) * 100
                    progress_queue.put(("progress", progress))
            
            # Preserve file metadata
            shutil.copystat(src_path, dst_path)
            
        except Exception as e:
            progress_queue.put(("status", f"Error copying {src_path}: {str(e)}"))
            raise
    
    def _get_total_size(self, directory: str) -> int:
        """Calculate total size of all files in directory."""
        total_size = 0
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        return total_size
    
    def cleanup(self, source_dir: str) -> bool:
        """Clean up source directory after copying."""
        try:
            if os.path.exists(source_dir):
                shutil.rmtree(source_dir)
            return True
        except Exception as e:
            print(f"Error cleaning up {source_dir}: {str(e)}")
            return False 