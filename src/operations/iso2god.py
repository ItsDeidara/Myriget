import os
import subprocess
from typing import Optional, List
from queue import Queue
import shutil
import time
import multiprocessing  # Add this import

class ISO2GODConverter:
    """Handles ISO to GOD conversion operations."""
    
    def __init__(self):
        """Initialize the converter with default settings."""
        self.last_status_time = 0  # Track last status update time
        
        # Find iso2god executable
        self.iso2god_path = self._find_iso2god()
        if not self.iso2god_path:
            raise Exception("iso2god executable not found. Please ensure it is installed and in the tools directory.")
            
        # Calculate optimal thread count (physical cores - 1, minimum 2)
        self.optimal_threads = max(2, multiprocessing.cpu_count() - 1)

    def _find_iso2god(self) -> Optional[str]:
        """Find the iso2god executable."""
        # Check in the tools directory next to main.py
        tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools')
        possible_paths = [
            os.path.join(tools_dir, 'iso2god.exe'),  # Windows executable
            os.path.join(tools_dir, 'iso2god'),      # Linux/Mac executable
            'iso2god.exe',  # In PATH (Windows)
            'iso2god'       # In PATH (Linux/Mac)
        ]
        
        # Create tools directory if it doesn't exist
        os.makedirs(tools_dir, exist_ok=True)
        
        # Try each possible path
        for path in possible_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
            
        return None

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
    
    def convert_iso_to_god(self, iso_path: str, output_dir: str, progress_queue: Queue,
                         game_title: Optional[str] = None, num_threads: Optional[int] = None,
                         trim: bool = True) -> Optional[str]:
        """Convert an ISO file to GOD format."""
        try:
            # Use optimal thread count if none specified
            if num_threads is None:
                num_threads = self.optimal_threads
                progress_queue.put(("status", f"Using optimal thread count: {num_threads}"))
            
            # Validate paths
            if not os.path.exists(iso_path):
                progress_queue.put(("status", f"Error: ISO file not found: {iso_path}"))
                return None
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Build iso2god command using the found executable path
            cmd = [self.iso2god_path]
            
            # Add optional parameters
            if game_title:
                cmd.extend(["--game-title", game_title])
            if trim:
                cmd.append("--trim")
            if num_threads > 1:
                cmd.extend(["-j", str(num_threads)])
            
            # Add required parameters
            cmd.extend([iso_path, output_dir])
            
            # Run conversion with real-time output monitoring
            progress_queue.put(("status", f"Converting {os.path.basename(iso_path)} to GOD format..."))
            progress_queue.put(("status", f"Using command: {' '.join(cmd)}"))
            
            try:
                # Use Popen for real-time output monitoring
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,  # Line buffered
                    universal_newlines=True
                )
                
                last_activity = time.time()
                while True:
                    # Check stdout
                    output = process.stdout.readline()
                    if output:
                        progress_queue.put(("status", f"iso2god: {output.strip()}"))
                        last_activity = time.time()
                    
                    # Check stderr
                    error = process.stderr.readline()
                    if error:
                        progress_queue.put(("status", f"iso2god error: {error.strip()}"))
                        last_activity = time.time()
                    
                    # Check if process has finished
                    if process.poll() is not None:
                        break
                    
                    # Check for timeout (no activity for 5 minutes)
                    if time.time() - last_activity > 300:  # 5 minutes
                        process.kill()
                        progress_queue.put(("status", "Error: Process appears to be frozen (no activity for 5 minutes). Terminating."))
                        return None
                    
                    # Small sleep to prevent CPU spinning
                    time.sleep(0.1)
                
                # Get remaining output
                remaining_out, remaining_err = process.communicate()
                if remaining_out:
                    progress_queue.put(("status", f"iso2god final output: {remaining_out.strip()}"))
                if remaining_err:
                    progress_queue.put(("status", f"iso2god final error: {remaining_err.strip()}"))
                
                # Check return code
                if process.returncode != 0:
                    progress_queue.put(("status", f"Error: iso2god failed with return code {process.returncode}"))
                    return None
                
            except subprocess.CalledProcessError as e:
                progress_queue.put(("status", f"Error converting {os.path.basename(iso_path)}: {e.stderr}"))
                return None
            except Exception as e:
                progress_queue.put(("status", f"Error running iso2god: {str(e)}"))
                return None
            
            # Find the converted GOD file
            god_files = [f for f in os.listdir(output_dir) if f.endswith('.000')]
            if god_files:
                god_path = os.path.join(output_dir, god_files[0])
                progress_queue.put(("status", f"Successfully converted {os.path.basename(iso_path)}"))
                return god_path
            else:
                progress_queue.put(("status", f"Error: No GOD files found after conversion: {os.path.basename(iso_path)}"))
                return None
                
        except Exception as e:
            progress_queue.put(("status", f"Error during conversion: {str(e)}"))
            return None
    
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
                    
                    if self.convert_iso_to_god(iso_path, game_output_dir, progress_queue,
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