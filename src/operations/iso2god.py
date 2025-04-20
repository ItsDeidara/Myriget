import os
import subprocess
from typing import Optional, List
from queue import Queue
import shutil
import time

class ISO2GODConverter:
    """Handles ISO to GOD conversion operations."""
    
    def __init__(self):
        """Initialize the converter with default settings."""
        self.last_status_time = 0  # Track last status update time
    
    def _should_update_status(self, message: str = "") -> bool:
        """Check if status should be updated based on message type and timing."""
        # Always show important messages immediately
        lower_msg = message.lower()
        if any(s in lower_msg for s in [
            "error", "failed", "invalid", "missing",  # Errors
            "success", "complete", "saved", "finished",  # Success
            "warning", "caution", "critical"  # Warnings
        ]):
            return True
        
        # Rate limit regular status updates
        current_time = time.time()
        if current_time - self.last_status_time >= 10:  # 10 seconds between regular updates
            self.last_status_time = current_time
            return True
        return False
    
    def convert_iso(self, iso_path: str, output_dir: str, progress_queue: Queue,
                   game_title: Optional[str] = None, num_threads: int = 4,
                   trim: bool = True) -> bool:
        """Convert an ISO file to GOD format.
        
        Args:
            iso_path: Path to the ISO file
            output_dir: Directory to save the GOD files
            progress_queue: Queue for progress updates
            game_title: Optional game title to use
            num_threads: Number of threads to use for conversion
            trim: Whether to trim unused space from the ISO
            
        Returns:
            bool: True if conversion was successful
        """
        try:
            # Validate paths
            if not os.path.exists(iso_path):
                progress_queue.put(("status", f"Error: ISO file not found: {iso_path}"))
                return False
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Build iso2god command
            cmd = ["iso2god"]
            if game_title:
                cmd.extend(["--game-title", game_title])
            if trim:
                cmd.append("--trim")
            cmd.extend(["-j", str(num_threads)])
            cmd.extend([iso_path, output_dir])
            
            # Run conversion
            progress_queue.put(("status", f"Converting {os.path.basename(iso_path)} to GOD format..."))
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                progress_queue.put(("status", f"Successfully converted {os.path.basename(iso_path)}"))
                return True
            else:
                progress_queue.put(("status", f"Error converting {os.path.basename(iso_path)}: {result.stderr}"))
                return False
                
        except Exception as e:
            progress_queue.put(("status", f"Error during conversion: {str(e)}"))
            return False
    
    def batch_convert(self, iso_dir: str, output_dir: str, progress_queue: Queue,
                     batch_size: int = 1, num_threads: int = 4, trim: bool = True) -> None:
        """Convert multiple ISO files to GOD format.
        
        Args:
            iso_dir: Directory containing ISO files
            output_dir: Directory to save the GOD files
            progress_queue: Queue for progress updates
            batch_size: Number of conversions to run simultaneously
            num_threads: Number of threads to use per conversion
            trim: Whether to trim unused space from the ISOs
        """
        try:
            # Get list of ISO files
            iso_files = [f for f in os.listdir(iso_dir) if f.lower().endswith('.iso')]
            total_files = len(iso_files)
            
            if total_files == 0:
                progress_queue.put(("status", "No ISO files found in directory"))
                return
            
            progress_queue.put(("status", f"Found {total_files} ISO files to convert"))
            
            # Process in batches
            for i in range(0, total_files, batch_size):
                batch = iso_files[i:i + batch_size]
                batch_size_actual = len(batch)
                current_batch = (i // batch_size) + 1
                total_batches = (total_files + batch_size - 1) // batch_size
                
                status_msg = f"\033[38;5;208mProcessing batch {current_batch} of {total_batches} ({batch_size_actual} files)...\033[0m"
                progress_queue.put(("status", status_msg))
                
                # Convert each ISO in the batch
                for j, iso_file in enumerate(batch):
                    iso_path = os.path.join(iso_dir, iso_file)
                    game_output_dir = os.path.join(output_dir, os.path.splitext(iso_file)[0])
                    
                    # Get game title from filename
                    game_title = os.path.splitext(iso_file)[0].replace('_', ' ')
                    
                    if self.convert_iso(iso_path, game_output_dir, progress_queue,
                                      game_title, num_threads, trim):
                        # Update progress
                        progress = ((i + j + 1) / total_files) * 100
                        progress_queue.put(("progress", progress))
                    else:
                        progress_queue.put(("status", f"Failed to convert {iso_file}"))
                
                # Save progress after each batch
                status_msg = f"\033[38;5;208mCompleted batch {current_batch} of {total_batches}. Progress: {((i + batch_size_actual) / total_files) * 100:.1f}%\033[0m"
                progress_queue.put(("status", status_msg))
            
            progress_queue.put(("status", "All conversions completed!"))
            
        except Exception as e:
            progress_queue.put(("status", f"Error during batch conversion: {str(e)}"))
    
    def get_conversion_status(self, output_dir: str) -> List[dict]:
        """Get status of converted games.
        
        Args:
            output_dir: Directory containing converted GOD files
            
        Returns:
            List of dictionaries containing game status information
        """
        try:
            if not os.path.exists(output_dir):
                return []
            
            status_list = []
            for game_dir in os.listdir(output_dir):
                game_path = os.path.join(output_dir, game_dir)
                if os.path.isdir(game_path):
                    # Check for GOD format files
                    god_files = [f for f in os.listdir(game_path) if f.endswith('.000')]
                    status = {
                        'name': game_dir,
                        'converted': len(god_files) > 0,
                        'file_count': len(god_files),
                        'path': game_path
                    }
                    status_list.append(status)
            
            return status_list
            
        except Exception as e:
            print(f"Error getting conversion status: {e}")
            return [] 