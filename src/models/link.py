import json
import os
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from queue import Queue
import shutil
import time

class LinkManager:
    """Manages link processing and JSON operations."""
    
    def __init__(self):
        """Initialize the link manager."""
        self.processing_log_file = os.path.join(
            os.path.dirname(__file__), "..", "..", "processing_log.json"
        )
        self.links_file = os.path.join(
            os.path.dirname(__file__), "..", "config", "links.json"
        )
        self.last_status_time = 0  # Track last status update time
    
    def set_links_file(self, links_file: str) -> None:
        """Set the links file path."""
        self.links_file = links_file
    
    def _sanitize_game_name(self, url: str) -> str:
        """Sanitize a game name from URL or filename."""
        try:
            # Extract filename from URL and decode URL-encoded characters
            filename = os.path.basename(url)
            filename = requests.utils.unquote(filename)  # Decode %20, %28, etc.
            
            # Remove file extension
            name = os.path.splitext(filename)[0]
            
            # Replace special characters with spaces
            name = name.replace('_', ' ').replace('-', ' ').replace('+', ' ')
            
            # Remove any numbers or special characters at the start
            name = name.lstrip('0123456789.-_ ')
            
            # Remove any remaining special characters that Windows doesn't like
            name = ''.join(c for c in name if c.isalnum() or c in ' -')
            
            # Replace multiple spaces with single space
            name = ' '.join(name.split())
            
            # Capitalize words
            name = ' '.join(word.capitalize() for word in name.split())
            
            # Ensure the name isn't too long (Windows has a 255 character limit for filenames)
            if len(name) > 200:  # Leave room for extensions
                name = name[:200].rstrip()
            
            return name
        
        except Exception as e:
            # If anything goes wrong, return a basic sanitized version
            return os.path.splitext(os.path.basename(url))[0].replace('_', ' ').replace('-', ' ')
    
    def _should_update_status(self, message: str = "") -> bool:
        """Check if status should be updated based on message type and timing.
        
        Args:
            message: The status message to check
        
        Returns:
            bool: True if status should be updated
        """
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
    
    def process_links(self, links_file: str, temp_dir: str, temp_extract_dir: str,
                     output_dir: str, batch_size: int, progress_queue: Queue,
                     filter_type: str = "All") -> None:
        """Process links from the specified file."""
        try:
            # Important messages - show immediately
            progress_queue.put(("status", "Loading links from file..."))
            with open(links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            # Validate URLs in JSON
            invalid_urls = []
            for link in links_data:
                url = link.get('url', '')
                if not url.endswith('.zip'):
                    invalid_urls.append(url)
            
            if invalid_urls:
                error_msg = "Error: Found invalid URLs in links.json (will be skipped):\n" + "\n".join(invalid_urls)
                progress_queue.put(("status", error_msg))
                # Don't raise error, just skip invalid URLs
                links_data = [link for link in links_data if link.get('url', '').endswith('.zip')]
            
            # Filter links based on type
            total_before_filter = len(links_data)
            if filter_type == "Incomplete":
                links_data = [link for link in links_data if not (
                    link.get('downloaded', False) and 
                    link.get('extracted', False) and 
                    link.get('copied', False)
                )]
                progress_queue.put(("status", "\033[38;5;208mBefore filtering: {total_before_filter} links\033[0m".format(total_before_filter=total_before_filter)))
                progress_queue.put(("status", "\033[38;5;208mAfter filtering for incomplete: {filtered} links\033[0m".format(filtered=len(links_data))))
                
                # Debug counts for each state
                downloaded_count = sum(1 for link in links_data if link.get('downloaded', False))
                extracted_count = sum(1 for link in links_data if link.get('extracted', False))
                copied_count = sum(1 for link in links_data if link.get('copied', False))
                progress_queue.put(("status", "\033[38;5;208mState counts in filtered links:\033[0m"))
                progress_queue.put(("status", "\033[38;5;208m- Downloaded: {downloaded_count}\033[0m".format(downloaded_count=downloaded_count)))
                progress_queue.put(("status", "\033[38;5;208m- Extracted: {extracted_count}\033[0m".format(extracted_count=extracted_count)))
                progress_queue.put(("status", "\033[38;5;208m- Copied: {copied_count}\033[0m".format(copied_count=copied_count)))
                
            elif filter_type == "Enabled":
                links_data = [link for link in links_data if link.get('enabled', True)]
                progress_queue.put(("status", "\033[38;5;208mAfter filtering for enabled: {filtered} links\033[0m".format(filtered=len(links_data))))
            
            # Count total links to process
            total_links = len(links_data)
            progress_queue.put(("status", f"Found {total_links} links to process"))
            
            if total_links == 0:
                progress_queue.put(("status", "No links to process"))
                return
            
            # Process in batches
            processed_count = 0
            total_batches = (total_links + batch_size - 1) // batch_size  # Calculate total number of batches
            for i in range(0, total_links, batch_size):
                batch = links_data[i:i + batch_size]
                batch_size_actual = len(batch)
                current_batch = (i // batch_size) + 1
                status_msg = f"\033[38;5;208mProcessing batch {current_batch} of {total_batches} ({batch_size_actual} links)...\033[0m"
                progress_queue.put(("status", status_msg))
                
                # Process each link in the batch
                for j, link in enumerate(batch):
                    try:
                        # Skip disabled games
                        if not link.get('enabled', True):
                            status_msg = f"Skipping disabled game: {link.get('name', 'Unknown')}"
                            if self._should_update_status(status_msg):
                                progress_queue.put(("status", status_msg))
                            continue
                        
                        # Get game name
                        game_name = link.get('name', os.path.basename(link['url']))
                        status_msg = f"Processing {game_name} ({processed_count + 1}/{total_links})"
                        if self._should_update_status(status_msg):
                            progress_queue.put(("status", status_msg))
                        
                        # Download file
                        file_path = self._download_file(link['url'], temp_dir, progress_queue)
                        if not file_path:
                            continue
                        
                        # Extract if needed
                        extract_dir = os.path.join(temp_extract_dir, os.path.basename(file_path))
                        if self._extract_file(file_path, extract_dir, progress_queue):
                            # Copy to output
                            if self._copy_to_output(extract_dir, output_dir, progress_queue):
                                # Update link status
                                link['downloaded'] = True
                                link['extracted'] = True
                                link['copied'] = True
                                link['processed'] = True
                                link['output_path'] = os.path.join(output_dir, game_name)
                                
                                # Save progress after each successful game
                                with open(links_file, 'w', encoding='utf-8') as f:
                                    json.dump(links_data, f, indent=4)
                                
                                # Show success immediately
                                progress_queue.put(("status", f"Successfully processed: {game_name}"))
                        
                        # Cleanup
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            status_msg = f"Cleaned up download: {game_name}"
                            if self._should_update_status(status_msg):
                                progress_queue.put(("status", status_msg))
                        if os.path.exists(extract_dir):
                            shutil.rmtree(extract_dir)
                            status_msg = f"Cleaned up extraction: {game_name}"
                            if self._should_update_status(status_msg):
                                progress_queue.put(("status", status_msg))
                        
                        processed_count += 1
                        # Update progress
                        progress = (processed_count / total_links) * 100
                        progress_queue.put(("progress", progress))
                        
                    except Exception as e:
                        # Show errors immediately
                        error_msg = f"Error processing {link.get('name', 'Unknown')}: {str(e)}"
                        progress_queue.put(("status", error_msg))
                        continue
                
                # Save progress after each batch
                status_msg = f"\033[38;5;208mCompleted batch {current_batch} of {total_batches}. Progress: {(processed_count / total_links) * 100:.1f}%\033[0m"
                progress_queue.put(("status", status_msg))
                with open(links_file, 'w', encoding='utf-8') as f:
                    json.dump(links_data, f, indent=4)
            
            # Show completion immediately
            progress_queue.put(("status", f"Processing complete! Processed {processed_count} of {total_links} links."))
            
        except Exception as e:
            # Show errors immediately
            error_msg = f"Error processing links: {str(e)}"
            progress_queue.put(("status", error_msg))
            raise
    
    def _validate_download(self, file_path: str, expected_url: str, progress_queue: Queue) -> bool:
        """Validate that the downloaded file matches what we expect.
        
        Args:
            file_path: Path to the downloaded file
            expected_url: The URL from the JSON that we downloaded
            progress_queue: Queue for progress updates
        
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Get expected filename from URL
            expected_filename = os.path.basename(expected_url)
            actual_filename = os.path.basename(file_path)
            
            # Check if filenames match
            if expected_filename != actual_filename:
                progress_queue.put(("status", f"Error: Downloaded file '{actual_filename}' does not match expected '{expected_filename}'. Skipping for now."))
                return False
            
            # Check if file exists and has size
            if not os.path.exists(file_path):
                progress_queue.put(("status", f"Error: Downloaded file '{file_path}' does not exist. Will retry later."))
                return False
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                progress_queue.put(("status", f"Error: Downloaded file '{file_path}' is empty. Will retry later."))
                return False
            
            # Check if it's a valid zip file
            if not self._is_valid_zip(file_path):
                progress_queue.put(("status", f"Error: File '{file_path}' is not a valid zip file. Will retry later."))
                return False
            
            return True
        
        except Exception as e:
            progress_queue.put(("status", f"Error validating download: {str(e)}. Will retry later."))
            return False
    
    def _is_valid_zip(self, file_path: str) -> bool:
        """Check if a file is a valid zip file.
        
        Args:
            file_path: Path to the file to check
        
        Returns:
            bool: True if valid zip file, False otherwise
        """
        try:
            import zipfile
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Try to read the zip contents
                zip_ref.testzip()
            return True
        except zipfile.BadZipFile:
            return False
        except Exception:
            return False
    
    def _download_file(self, url: str, temp_dir: str, progress_queue: Queue) -> Optional[str]:
        """Download a file from URL."""
        try:
            status_msg = f"Downloading: {os.path.basename(url)}"
            if self._should_update_status(status_msg):
                progress_queue.put(("status", status_msg))
            
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            filename = os.path.basename(url)
            file_path = os.path.join(temp_dir, filename)
            
            # Get total file size
            total_size = int(response.headers.get('content-length', 0))
            
            with open(file_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # Update download progress less frequently
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                status_msg = f"Downloading {filename}: {percent:.1f}%"
                                if self._should_update_status(status_msg):
                                    progress_queue.put(("status", status_msg))
            
            # Validate the downloaded file
            if not self._validate_download(file_path, url, progress_queue):
                # Don't remove the file, just skip it for now
                return None
            
            # Show success immediately
            progress_queue.put(("status", f"Download complete and validated: {filename}"))
            return file_path
        
        except requests.RequestException as e:
            # Show errors immediately
            error_msg = f"Error downloading {url}: {str(e)}. Will retry later."
            progress_queue.put(("status", error_msg))
            return None
        except Exception as e:
            # Show errors immediately
            error_msg = f"Error saving download {url}: {str(e)}. Will retry later."
            progress_queue.put(("status", error_msg))
            return None
    
    def _extract_file(self, file_path: str, temp_extract_dir: str,
                     progress_queue: Queue) -> Optional[str]:
        """Extract a file to temporary directory."""
        try:
            import zipfile
            import tarfile
            
            filename = os.path.basename(file_path)
            extract_dir = os.path.join(temp_extract_dir, os.path.splitext(filename)[0])
            os.makedirs(extract_dir, exist_ok=True)
            
            if filename.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif filename.endswith(('.tar', '.tar.gz', '.tgz')):
                with tarfile.open(file_path, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_dir)
            else:
                progress_queue.put(("status", f"Unsupported archive format: {filename}"))
                return None
            
            progress_queue.put(("status", f"Extracted {filename}"))
            return extract_dir
        
        except Exception as e:
            progress_queue.put(("status", f"Error extracting {file_path}: {str(e)}"))
            return None
    
    def _copy_to_output(self, source_dir: str, output_dir: str,
                       progress_queue: Queue) -> bool:
        """Copy extracted files to output directory."""
        try:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(root, source_dir)
                    dst_dir = os.path.join(output_dir, rel_path)
                    os.makedirs(dst_dir, exist_ok=True)
                    dst_path = os.path.join(dst_dir, file)
                    
                    shutil.copy2(src_path, dst_path)
                    progress_queue.put(("status", f"Copied {file}"))
            
            return True
        
        except Exception as e:
            progress_queue.put(("status", f"Error copying files: {str(e)}"))
            return False
    
    def _update_processing_log(self, url: str, file_path: str,
                             extract_dir: str) -> None:
        """Update the processing log with file information."""
        try:
            log_entry = {
                "url": url,
                "file_path": file_path,
                "extract_dir": extract_dir,
                "timestamp": str(datetime.now())
            }
            
            log_entries = []
            if os.path.exists(self.processing_log_file):
                with open(self.processing_log_file, 'r', encoding='utf-8') as f:
                    log_entries = json.load(f)
            
            log_entries.append(log_entry)
            
            with open(self.processing_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_entries, f, indent=4)
        
        except Exception as e:
            print(f"Error updating processing log: {e}")
    
    def import_links_json(self, url: str, mode: str, progress_queue: Queue) -> None:
        """Import links from a JSON URL."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            new_links = response.json()
            
            if not isinstance(new_links, list):
                raise ValueError("Invalid links.json format: expected a list")
            
            # Validate each link
            for link in new_links:
                if not isinstance(link, dict):
                    raise ValueError("Invalid link format: expected a dictionary")
                if "url" not in link:
                    raise ValueError("Invalid link: missing 'url' field")
            
            if mode == "append":
                # Load existing links
                existing_links = []
                if os.path.exists(self.links_file):
                    with open(self.links_file, 'r', encoding='utf-8') as f:
                        existing_links = json.load(f)
                
                # Add only new links
                existing_urls = {link["url"] for link in existing_links}
                for link in new_links:
                    if link["url"] not in existing_urls:
                        existing_links.append(link)
                
                new_links = existing_links
            
            # Save the updated links
            with open(self.links_file, 'w', encoding='utf-8') as f:
                json.dump(new_links, f, indent=4)
            
            progress_queue.put(("status", f"Successfully imported {len(new_links)} links"))
        
        except Exception as e:
            progress_queue.put(("status", f"Error importing links: {str(e)}"))
            raise

    def process_urls_file(self, urls: list, mode: str, link_type: str, progress_queue: Queue) -> None:
        """Process URLs from a text file and update links.json.
        
        Args:
            urls: List of URLs to process
            mode: Either 'append' or 'replace'
            link_type: Either 'ISO' or 'XBLA'
            progress_queue: Queue for progress updates
        """
        try:
            # Create link entries with the specified type
            new_links = []
            for i, url in enumerate(urls):
                # Update progress
                progress = (i + 1) / len(urls) * 100
                progress_queue.put(("progress", progress))
                progress_queue.put(("status", f"Processing URL {i + 1} of {len(urls)}"))
                
                # Create link entry
                link = {
                    "url": url.strip(),
                    "downloaded": False,
                    "extracted": False,
                    "deleted": False,
                    "copied": False,
                    "size_bytes": 0,
                    "link_type": link_type
                }
                new_links.append(link)
            
            # Load existing links.json if it exists and we're in append mode
            existing_links = []
            if mode == "append" and os.path.exists(self.links_file):
                try:
                    with open(self.links_file, 'r', encoding='utf-8') as f:
                        existing_links = json.load(f)
                except json.JSONDecodeError:
                    progress_queue.put(("status", "Warning: Existing links.json is invalid, creating new file"))
            
            # Combine or replace links based on mode
            if mode == "append":
                # Add only new URLs that don't exist in the current file
                existing_urls = {link["url"] for link in existing_links}
                new_links = [link for link in new_links if link["url"] not in existing_urls]
                final_links = existing_links + new_links
                progress_queue.put(("status", f"Added {len(new_links)} new {link_type} links to existing {len(existing_links)} links"))
            else:
                final_links = new_links
                progress_queue.put(("status", f"Created new links.json with {len(new_links)} {link_type} links"))
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.links_file), exist_ok=True)
            
            # Save the updated links.json
            with open(self.links_file, 'w', encoding='utf-8') as f:
                json.dump(final_links, f, indent=4)
            
            progress_queue.put(("status", "Links.json has been updated successfully"))
            progress_queue.put(("progress", 100))
        
        except Exception as e:
            progress_queue.put(("status", f"Error processing URLs: {str(e)}"))
            raise

    def update_file_sizes(self, progress_queue: Queue) -> None:
        """Update missing file sizes in links.json using HEAD requests.
        
        Args:
            progress_queue: Queue for progress updates
        """
        try:
            if not os.path.exists(self.links_file):
                progress_queue.put(("status", "No links.json found"))
                return
            
            with open(self.links_file, 'r', encoding='utf-8') as f:
                links = json.load(f)
            
            total_links = len(links)
            missing_links = [link for link in links if not link.get('size_bytes', 0)]
            total_missing = len(missing_links)
            
            if total_missing == 0:
                progress_queue.put(("status", "No missing sizes found"))
                return
            
            progress_queue.put(("status", f"Found {total_missing} links with missing sizes"))
            links_updated = 0
            errors = 0
            
            # Create a session for connection pooling
            with requests.Session() as session:
                for i, link in enumerate(missing_links):
                    try:
                        progress_queue.put(("status", f"Checking size for {os.path.basename(link['url'])}"))
                        
                        response = session.head(link['url'], timeout=10, allow_redirects=True)
                        response.raise_for_status()
                        
                        # Get file size from Content-Length header
                        size = int(response.headers.get('Content-Length', 0))
                        if size > 0:
                            # Find and update the link in the original list
                            for orig_link in links:
                                if orig_link['url'] == link['url']:
                                    orig_link['size_bytes'] = size
                                    break
                            links_updated += 1
                            progress_queue.put(("status", 
                                f"Updated size for {os.path.basename(link['url'])}: {size/1024/1024/1024:.2f} GB"))
                            
                            # Save progress after each successful update
                            try:
                                with open(self.links_file, 'w', encoding='utf-8') as f:
                                    json.dump(links, f, indent=4)
                                progress_queue.put(("status", "Progress saved"))
                            except Exception as save_error:
                                progress_queue.put(("status", f"Warning: Could not save progress: {save_error}"))
                        else:
                            errors += 1
                            progress_queue.put(("status", 
                                f"No size information available for {os.path.basename(link['url'])}"))
                    
                    except requests.RequestException as e:
                        errors += 1
                        progress_queue.put(("status", 
                            f"Error checking size for {os.path.basename(link['url'])}: {str(e)}"))
                    
                    # Update progress
                    progress = (i + 1) / total_missing * 100
                    progress_queue.put(("progress", progress))
            
            # Final status update
            status = f"Size update complete:\n" \
                    f"- {links_updated} files updated\n" \
                    f"- {errors} errors\n" \
                    f"- {total_missing - links_updated - errors} files skipped"
            progress_queue.put(("status", status))
            
        except Exception as e:
            progress_queue.put(("status", f"Error updating sizes: {str(e)}"))
            raise

    def merge_links_files(self, second_file: str, progress_queue: Queue) -> None:
        """Merge another links.json file with the current one.
        
        Args:
            second_file: Path to the second links.json to merge
            progress_queue: Queue for progress updates
        """
        try:
            if not os.path.exists(self.links_file):
                progress_queue.put(("status", "Primary links.json not found"))
                raise FileNotFoundError("Primary links.json not found")
            
            if not os.path.exists(second_file):
                progress_queue.put(("status", "Secondary links.json not found"))
                raise FileNotFoundError(f"Secondary file not found: {second_file}")
            
            # Load both files
            progress_queue.put(("status", "Loading links files..."))
            with open(self.links_file, 'r', encoding='utf-8') as f:
                primary_links = json.load(f)
            
            with open(second_file, 'r', encoding='utf-8') as f:
                secondary_links = json.load(f)
            
            # Validate format
            if not isinstance(primary_links, list) or not isinstance(secondary_links, list):
                raise ValueError("Invalid links.json format: expected a list")
            
            # Create backup of primary file
            backup_file = f"{self.links_file}.bak"
            progress_queue.put(("status", f"Creating backup at {backup_file}"))
            shutil.copy2(self.links_file, backup_file)
            
            # Create URL set for quick lookup
            existing_urls = {link['url'] for link in primary_links}
            
            # Merge links, preserving size information
            new_links = []
            duplicates = 0
            updates = 0
            
            progress_queue.put(("status", "Merging links..."))
            total = len(secondary_links)
            
            for i, new_link in enumerate(secondary_links):
                if new_link['url'] in existing_urls:
                    # If the new link has size info and old one doesn't, update it
                    for old_link in primary_links:
                        if old_link['url'] == new_link['url']:
                            if not old_link.get('size_bytes', 0) and new_link.get('size_bytes', 0):
                                old_link['size_bytes'] = new_link['size_bytes']
                                updates += 1
                            break
                    duplicates += 1
                else:
                    new_links.append(new_link)
                
                # Update progress
                progress = (i + 1) / total * 100
                progress_queue.put(("progress", progress))
            
            # Combine lists
            merged_links = primary_links + new_links
            
            # Save merged file
            progress_queue.put(("status", "Saving merged links file..."))
            with open(self.links_file, 'w', encoding='utf-8') as f:
                json.dump(merged_links, f, indent=4)
            
            # Final status
            status = (
                f"Merge complete:\n"
                f"- Added {len(new_links)} new links\n"
                f"- Found {duplicates} duplicates\n"
                f"- Updated {updates} existing links with size information\n"
                f"- Total links: {len(merged_links)}\n"
                f"- Backup saved as: {os.path.basename(backup_file)}"
            )
            progress_queue.put(("status", status))
            
        except Exception as e:
            progress_queue.put(("status", f"Error merging links: {str(e)}"))
            raise

    def generate_game_names(self, progress_queue: Queue) -> None:
        """Generate and store sanitized names for all games in links.json."""
        try:
            if not os.path.exists(self.links_file):
                progress_queue.put(("status", "No links.json found"))
                return
            
            # Load links
            with open(self.links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)
            
            total_links = len(links_data)
            updated = 0
            
            # Process each link
            for i, link in enumerate(links_data):
                url = link.get('url')
                if not url:
                    continue
                
                # Generate sanitized name if not already present
                if 'name' not in link:
                    link['name'] = self._sanitize_game_name(url)
                    updated += 1
                
                # Update progress
                progress = (i + 1) / total_links * 100
                progress_queue.put(("progress", progress))
                progress_queue.put(("status", f"Processing {i + 1} of {total_links}"))
            
            # Save changes if any names were updated
            if updated > 0:
                with open(self.links_file, 'w', encoding='utf-8') as f:
                    json.dump(links_data, f, indent=4)
                
                progress_queue.put(("status", f"Generated names for {updated} games"))
            else:
                progress_queue.put(("status", "All games already have names"))
            
            progress_queue.put(("progress", 100))
        
        except Exception as e:
            progress_queue.put(("status", f"Error generating game names: {str(e)}"))
            raise 