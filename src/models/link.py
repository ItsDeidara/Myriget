import json
import os
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from queue import Queue

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
    
    def process_links(self, links_file: str, temp_dir: str, temp_extract_dir: str,
                     output_dir: str, batch_size: int, progress_queue: Queue,
                     filter_type: str = "All") -> None:
        """Process links from the links file."""
        try:
            with open(links_file, 'r', encoding='utf-8') as f:
                links = json.load(f)
            
            # Filter links based on filter_type
            if filter_type == "Incomplete":
                links_to_process = [link for link in links if not link.get("copied", False)]
            else:  # "All"
                links_to_process = links
            
            # Process links in batches
            for i in range(0, len(links_to_process), batch_size):
                batch = links_to_process[i:i + batch_size]
                self._process_batch(batch, temp_dir, temp_extract_dir, output_dir, progress_queue)
                
                # Update progress
                progress = min((i + len(batch)) / len(links_to_process) * 100, 100)
                progress_queue.put(("progress", progress))
            
            progress_queue.put(("status", "Processing complete"))
        
        except Exception as e:
            progress_queue.put(("status", f"Error processing links: {str(e)}"))
            raise
    
    def _process_batch(self, batch: List[Dict[str, Any]], temp_dir: str,
                      temp_extract_dir: str, output_dir: str,
                      progress_queue: Queue) -> None:
        """Process a batch of links."""
        for link in batch:
            try:
                url = link["url"]
                progress_queue.put(("status", f"Processing {url}"))
                
                # Download file
                file_path = self._download_file(url, temp_dir, progress_queue)
                if not file_path:
                    continue
                
                # Extract file
                extract_dir = self._extract_file(file_path, temp_extract_dir, progress_queue)
                if not extract_dir:
                    continue
                
                # Copy to output
                if self._copy_to_output(extract_dir, output_dir, progress_queue):
                    # Update link status
                    link["copied"] = True
                    self._update_processing_log(url, file_path, extract_dir)
                
            except Exception as e:
                progress_queue.put(("status", f"Error processing {url}: {str(e)}"))
    
    def _download_file(self, url: str, temp_dir: str,
                      progress_queue: Queue) -> Optional[str]:
        """Download a file from URL."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            filename = os.path.basename(url)
            file_path = os.path.join(temp_dir, filename)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            progress_queue.put(("status", f"Downloaded {filename}"))
            return file_path
        
        except Exception as e:
            progress_queue.put(("status", f"Error downloading {url}: {str(e)}"))
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
            import shutil
            
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
                    "size_bytes": 0,  # Will be updated when downloaded
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
                progress_queue.put(("status", f"Replaced links.json with {len(new_links)} new {link_type} links"))
            
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