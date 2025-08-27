"""
Core rebuilder module for reconstructing Google Drive structure from Takeout
"""
from __future__ import annotations

import os
import shutil
import filecmp
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Set, Optional, Callable, Any

from .logger import ProgressLogger


class SafeTakeoutReconstructor:
    """Safely reconstructs Google Drive structure from Takeout data"""
    
    def __init__(self, takeout_path: str, export_path: str, dry_run: bool = True, 
                 progress_callback: Optional[Callable] = None, gui_mode: bool = False):
        # Initialize paths
        self.source_dir = Path(takeout_path)
        self.dest_dir = Path(export_path)
        self.dry_run = dry_run
        self.progress_callback = progress_callback
        self.gui_mode = gui_mode
        
        # Initialize logger
        self.logger = ProgressLogger("rebuilder")
        if progress_callback:
            self.logger.set_progress_callback(progress_callback)
        
        # Logging setup
        self.log_dir = self.dest_dir.parent / "takeout_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"rebuild_log_{timestamp}.txt"
        self.error_log = self.log_dir / f"errors_{timestamp}.txt"
        self.duplicate_log = self.log_dir / f"duplicates_{timestamp}.txt"
        self.manifest_file = self.log_dir / f"manifest_{timestamp}.json"
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'copied_files': 0,
            'skipped_duplicates': 0,
            'renamed_duplicates': 0,
            'errors': 0,
            'total_size': 0,
            'copied_size': 0
        }
        
        # File tracking for deduplication
        self.file_hashes = {}  # hash -> list of file paths
        self.processed_files = set()
        
        # Resource management
        self.temp_files: List[str] = []
        self.open_file_handles: List[Any] = []
        
        # GUI state tracking
        self.current_operation = "idle"
        self.current_file = ""
        self.progress_percent = 0
        self.pending_prompt = None
    
    def rebuild_drive_structure(self, verify_copies: bool = False):
        """Main method to rebuild the Drive structure"""
        try:
            self.logger.info("Starting Google Drive reconstruction")
            self.logger.status("starting", "Initializing reconstruction...")
            
            # Validate paths
            if not self.source_dir.exists():
                raise ValueError(f"Source directory does not exist: {self.source_dir}")
            
            # Create destination directory
            if not self.dry_run:
                self.dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Scan source directory
            self.logger.status("processing", "Scanning source directory...")
            self._scan_source_directory()
            
            # Process files
            self.logger.status("processing", "Processing and copying files...")
            self._process_files(verify_copies)
            
            # Generate manifest
            self._generate_manifest()
            
            # Final statistics
            self._log_final_statistics()
            
            self.logger.status("completed", "Reconstruction completed successfully")
            self.logger.success("Drive reconstruction completed successfully!")
            
        except Exception as e:
            self.logger.error(f"Reconstruction failed: {str(e)}")
            self.logger.status("failed", f"Reconstruction failed: {str(e)}")
            raise
    
    def _scan_source_directory(self):
        """Scan the source directory to count files and analyze structure"""
        total_files = 0
        total_size = 0
        
        for root, dirs, files in os.walk(self.source_dir):
            for file in files:
                if not file.startswith('.') and not file.endswith('.tmp'):
                    file_path = Path(root) / file
                    try:
                        stat = file_path.stat()
                        total_files += 1
                        total_size += stat.st_size
                    except OSError:
                        continue
        
        self.stats['total_files'] = total_files
        self.stats['total_size'] = total_size
        
        self.logger.info(f"Found {total_files} files ({total_size / (1024**3):.2f} GB)")
        self.logger.stats(self.stats)
    
    def _process_files(self, verify_copies: bool = False):
        """Process all files in the source directory"""
        processed_count = 0
        
        for root, dirs, files in os.walk(self.source_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.startswith('.') or file.endswith('.tmp'):
                    continue
                
                source_path = Path(root) / file
                processed_count += 1
                
                # Update progress
                progress = (processed_count / self.stats['total_files']) * 100 if self.stats['total_files'] > 0 else 0
                self.logger.progress(
                    percent=progress,
                    current_file=file,
                    operation=f"Processing file {processed_count}/{self.stats['total_files']}"
                )
                
                try:
                    self._process_single_file(source_path, verify_copies)
                except Exception as e:
                    self.stats['errors'] += 1
                    self.logger.error(f"Failed to process {source_path}: {str(e)}")
                
                # Update statistics periodically
                if processed_count % 100 == 0:
                    self.logger.stats(self.stats)
    
    def _process_single_file(self, source_path: Path, verify_copies: bool = False):
        """Process a single file"""
        # Determine destination path
        dest_path = self._determine_destination_path(source_path)
        
        if not dest_path:
            return
        
        # Check for duplicates
        if self._is_duplicate(source_path, dest_path):
            self.stats['skipped_duplicates'] += 1
            self.logger.info(f"Skipped duplicate: {source_path.name}")
            return
        
        # Copy the file
        if not self.dry_run:
            success = self._safe_copy_file(source_path, dest_path, verify_copies)
            if success:
                self.stats['copied_files'] += 1
                self.stats['copied_size'] += source_path.stat().st_size
            else:
                self.stats['errors'] += 1
        else:
            self.logger.info(f"Would copy: {source_path} -> {dest_path}")
            self.stats['copied_files'] += 1
    
    def _determine_destination_path(self, source_path: Path) -> Optional[Path]:
        """Determine the appropriate destination path for a file"""
        relative_path = source_path.relative_to(self.source_dir)
        
        # Handle Google metadata files
        if source_path.name.endswith('.json') and self._is_google_metadata(source_path):
            return None  # Skip metadata files
        
        # Clean up the path (remove Takeout folder structure)
        path_parts = list(relative_path.parts)
        original_parts = path_parts.copy()  # For debugging
        
        # More aggressive removal of Takeout and Drive structures
        cleaned_parts = []
        for part in path_parts:
            # Skip any folder that starts with "Takeout" (handles Takeout, Takeout 1, etc.)
            if part.startswith('Takeout'):
                continue
            # Skip "Drive" folders entirely - we want files to go directly to output
            elif part == 'Drive':
                continue
            # Keep everything else
            else:
                cleaned_parts.append(part)
        
        # Debug logging for path transformation
        if self.logger and len(original_parts) != len(cleaned_parts):
            self.logger.debug(f"Path transform: {'/'.join(original_parts)} → {'/'.join(cleaned_parts)}")
        
        if not cleaned_parts:
            self.logger.warning(f"No valid path parts remaining for: {source_path}")
            return None
        
        # Reconstruct clean path - files go directly into dest_dir without Drive/ nesting
        clean_relative_path = Path(*cleaned_parts)
        final_path = self.dest_dir / clean_relative_path
        
        # Additional debug logging
        if self.logger:
            self.logger.debug(f"Final destination: {source_path} → {final_path}")
        
        return final_path
    
    def _is_google_metadata(self, file_path: Path) -> bool:
        """Check if a file is Google metadata"""
        if not file_path.name.endswith('.json'):
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Check for Google metadata structure
                return 'title' in data or 'createdTime' in data or 'modifiedTime' in data
        except:
            return False
    
    def _is_duplicate(self, source_path: Path, dest_path: Path) -> bool:
        """Check if a file is a duplicate"""
        if not dest_path.exists():
            return False
        
        # Compare file sizes first (fast)
        try:
            source_size = source_path.stat().st_size
            dest_size = dest_path.stat().st_size
            
            if source_size != dest_size:
                return False
            
            # For small files, compare content
            if source_size < 1024 * 1024:  # 1MB
                return filecmp.cmp(source_path, dest_path, shallow=False)
            
            # For large files, just assume different if sizes match
            return True
            
        except OSError:
            return False
    
    def _safe_copy_file(self, source_path: Path, dest_path: Path, verify: bool = False) -> bool:
        """Safely copy a file with error handling"""
        try:
            # Ensure source exists and is a file
            if not source_path.exists() or not source_path.is_file():
                self.logger.warning(f"Source is not a valid file: {source_path}")
                return False
            
            # Create destination directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the file
            if source_path.stat().st_size > 100 * 1024 * 1024:  # 100MB
                # Use chunked copy for large files
                success = self._chunked_copy(source_path, dest_path)
            else:
                shutil.copy2(source_path, dest_path)
                success = True
            
            if success and verify:
                # Verify the copy
                if not filecmp.cmp(source_path, dest_path, shallow=False):
                    self.logger.error(f"Copy verification failed: {source_path}")
                    dest_path.unlink()  # Remove bad copy
                    return False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Copy failed {source_path} -> {dest_path}: {str(e)}")
            return False
    
    def _chunked_copy(self, source_path: Path, dest_path: Path, chunk_size: int = 1024 * 1024) -> bool:
        """Copy large files in chunks to prevent memory issues"""
        try:
            with open(source_path, 'rb') as fsrc, open(dest_path, 'wb') as fdst:
                # Track file handles for cleanup
                self.open_file_handles.extend([fsrc, fdst])
                
                while True:
                    chunk = fsrc.read(chunk_size)
                    if not chunk:
                        break
                    fdst.write(chunk)
                
                # Remove from tracking once closed
                if fsrc in self.open_file_handles:
                    self.open_file_handles.remove(fsrc)
                if fdst in self.open_file_handles:
                    self.open_file_handles.remove(fdst)
            
            # Copy metadata
            shutil.copystat(source_path, dest_path)
            return True
            
        except Exception as e:
            self.logger.error(f"Chunked copy failed: {str(e)}")
            if dest_path.exists():
                dest_path.unlink()  # Clean up partial copy
            return False
    
    def _generate_manifest(self):
        """Generate a manifest file with reconstruction details"""
        manifest = {
            'reconstruction_date': datetime.now().isoformat(),
            'source_directory': str(self.source_dir),
            'destination_directory': str(self.dest_dir),
            'statistics': self.stats,
            'dry_run': self.dry_run
        }
        
        if not self.dry_run:
            with open(self.manifest_file, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            self.logger.info(f"Manifest saved to {self.manifest_file}")
    
    def _log_final_statistics(self):
        """Log final reconstruction statistics"""
        self.logger.info("=== Reconstruction Complete ===")
        self.logger.info(f"Total files scanned: {self.stats['total_files']}")
        self.logger.info(f"Files copied: {self.stats['copied_files']}")
        self.logger.info(f"Duplicates skipped: {self.stats['skipped_duplicates']}")
        self.logger.info(f"Errors: {self.stats['errors']}")
        self.logger.info(f"Total size: {self.stats['total_size'] / (1024**3):.2f} GB")
        self.logger.info(f"Copied size: {self.stats['copied_size'] / (1024**3):.2f} GB")
        
        self.logger.stats(self.stats)
    
    def cleanup_resources(self):
        """Clean up resources (file handles, temp files)"""
        try:
            # Close any open file handles
            for handle in self.open_file_handles:
                try:
                    if hasattr(handle, 'close'):
                        handle.close()
                except Exception as e:
                    self.logger.warning(f"Could not close file handle: {e}")
            self.open_file_handles.clear()
            
            # Clean up temporary files
            for temp_file in self.temp_files:
                try:
                    temp_path = Path(temp_file)
                    if temp_path.exists():
                        if temp_path.is_file():
                            temp_path.unlink()
                        elif temp_path.is_dir():
                            shutil.rmtree(temp_path, ignore_errors=True)
                except Exception as e:
                    self.logger.warning(f"Could not cleanup temp file {temp_file}: {e}")
            self.temp_files.clear()
            
            self.logger.info("🧹 Resource cleanup completed")
            
        except Exception as e:
            self.logger.warning(f"Error during resource cleanup: {e}")
    
    def cancel(self):
        """Cancel the operation and clean up resources"""
        self.logger.warning("Operation cancelled by user")
        self.cleanup_resources()
        
        if self.progress_callback:
            self.progress_callback({
                'type': 'status',
                'status': 'cancelled',
                'message': 'Operation cancelled by user'
            })
    
    def __del__(self):
        """Destructor to ensure cleanup on object deletion"""
        try:
            self.cleanup_resources()
        except:
            pass
