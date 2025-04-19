import os
import zipfile
import tarfile
import shutil
from typing import Optional
from queue import Queue

class FileExtractor:
    """Handles file extraction operations."""
    
    def __init__(self):
        """Initialize the extractor."""
        self.supported_formats = {
            '.zip': self._extract_zip,
            '.tar': self._extract_tar,
            '.tar.gz': self._extract_tar,
            '.tgz': self._extract_tar
        }
    
    def extract(self, file_path: str, output_dir: str, progress_queue: Queue) -> Optional[str]:
        """Extract a file to the output directory."""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Get file extension
            _, ext = os.path.splitext(file_path)
            
            # Check if format is supported
            if ext not in self.supported_formats:
                progress_queue.put(("status", f"Unsupported archive format: {ext}"))
                return None
            
            # Create extraction directory
            filename = os.path.basename(file_path)
            extract_dir = os.path.join(output_dir, os.path.splitext(filename)[0])
            os.makedirs(extract_dir, exist_ok=True)
            
            # Extract file
            extract_func = self.supported_formats[ext]
            if extract_func(file_path, extract_dir, progress_queue):
                progress_queue.put(("status", f"Extracted {filename}"))
                return extract_dir
            return None
        
        except Exception as e:
            progress_queue.put(("status", f"Error extracting {file_path}: {str(e)}"))
            return None
    
    def _extract_zip(self, file_path: str, extract_dir: str, progress_queue: Queue) -> bool:
        """Extract a ZIP file."""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Get total size for progress tracking
                total_size = sum(file.file_size for file in zip_ref.filelist)
                extracted_size = 0
                
                for file in zip_ref.filelist:
                    zip_ref.extract(file, extract_dir)
                    extracted_size += file.file_size
                    
                    # Update progress
                    if total_size > 0:
                        progress = (extracted_size / total_size) * 100
                        progress_queue.put(("progress", progress))
            
            return True
        except Exception as e:
            progress_queue.put(("status", f"Error extracting ZIP: {str(e)}"))
            return False
    
    def _extract_tar(self, file_path: str, extract_dir: str, progress_queue: Queue) -> bool:
        """Extract a TAR file."""
        try:
            with tarfile.open(file_path, 'r:*') as tar_ref:
                # Get total size for progress tracking
                total_size = sum(member.size for member in tar_ref.getmembers())
                extracted_size = 0
                
                for member in tar_ref.getmembers():
                    tar_ref.extract(member, extract_dir)
                    extracted_size += member.size
                    
                    # Update progress
                    if total_size > 0:
                        progress = (extracted_size / total_size) * 100
                        progress_queue.put(("progress", progress))
            
            return True
        except Exception as e:
            progress_queue.put(("status", f"Error extracting TAR: {str(e)}"))
            return False
    
    def cleanup(self, extract_dir: str) -> bool:
        """Clean up extracted files."""
        try:
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            return True
        except Exception as e:
            print(f"Error cleaning up {extract_dir}: {str(e)}")
            return False 