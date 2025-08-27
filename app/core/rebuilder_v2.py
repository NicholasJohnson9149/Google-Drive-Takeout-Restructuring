"""
Improved SafeTakeoutReconstructor with proper separation of concerns
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import logging
import json

from .file_scanner import FileScanner, FileInfo, ScanResult
from .path_normalizer import PathNormalizer, PathTransformation
from .duplicate_checker import DuplicateChecker, DuplicateStrategy, DuplicateResult
from .logger import ProgressLogger


@dataclass
class ProcessingStats:
    """Statistics for the reconstruction process"""
    total_files: int = 0
    copied_files: int = 0
    skipped_duplicates: int = 0
    skipped_metadata: int = 0
    errors: int = 0
    total_size: int = 0
    copied_size: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class ProcessingError:
    """Information about a processing error"""
    file_path: str
    error_message: str
    timestamp: str
    error_type: str = "processing"


class SafeTakeoutReconstructor:
    """
    Orchestrates the reconstruction of Google Drive structure from Takeout data
    Uses composition with specialized classes for better separation of concerns
    """
    
    def __init__(self, 
                 takeout_path: str, 
                 export_path: str, 
                 dry_run: bool = True,
                 duplicate_strategy: DuplicateStrategy = DuplicateStrategy.HASH,
                 progress_callback: Optional[Callable] = None):
        
        # Core paths
        self.source_dir = Path(takeout_path)
        self.dest_dir = Path(export_path)
        self.dry_run = dry_run
        self.progress_callback = progress_callback
        
        # Initialize components
        self.logger = ProgressLogger("rebuilder")
        if progress_callback:
            self.logger.set_progress_callback(progress_callback)
        
        self.scanner = FileScanner(self.source_dir, self._emit_progress)
        self.path_normalizer = PathNormalizer(self.dest_dir)
        self.duplicate_checker = DuplicateChecker(duplicate_strategy)
        
        # State
        self.stats = ProcessingStats()
        self.errors: List[ProcessingError] = []
        self.temp_dir: Optional[Path] = None
        
        # Logging setup
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging directories and files"""
        self.log_dir = self.dest_dir.parent / "takeout_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.error_log_file = self.log_dir / f"errors_{timestamp}.txt"
        self.manifest_file = self.log_dir / f"manifest_{timestamp}.json"
    
    def rebuild_drive_structure(self, verify_copies: bool = False) -> bool:
        """
        Main method to rebuild the Drive structure
        
        Args:
            verify_copies: Whether to verify file integrity after copying
            
        Returns:
            True if successful, False if critical errors occurred
        """
        try:
            with self._managed_resources():
                self._emit_status("starting", "Initializing reconstruction...")
                
                # Validate inputs
                if not self._validate_inputs():
                    return False
                
                # Create destination if needed
                if not self.dry_run:
                    self.dest_dir.mkdir(parents=True, exist_ok=True)
                
                # Scan source directory
                self._emit_status("scanning", "Scanning source directory...")
                scan_result = self.scanner.scan()
                
                if scan_result.errors:
                    for error in scan_result.errors:
                        self._record_error("scan", error, "ScanError")
                    
                    if not scan_result.files:  # Fatal: no files found
                        self._emit_status("failed", "No files found to process")
                        return False
                
                self.stats.total_files = scan_result.total_files
                self.stats.total_size = scan_result.total_size
                
                self.logger.info(f"Found {self.stats.total_files} files ({self.stats.total_size / (1024**3):.2f} GB)")
                
                # Process files
                self._emit_status("processing", "Processing and copying files...")
                success = self._process_files(scan_result.files, verify_copies)
                
                # Generate manifest
                self._write_manifest()
                
                # Write error log
                self._write_error_log()
                
                # Log final statistics
                self._log_final_statistics()
                
                if success and self.stats.errors == 0:
                    self._emit_status("completed", "Reconstruction completed successfully")
                    self.logger.success("Drive reconstruction completed successfully!")
                    return True
                else:
                    self._emit_status("completed_with_errors", f"Completed with {self.stats.errors} errors")
                    self.logger.warning(f"Drive reconstruction completed with {self.stats.errors} errors")
                    return False
                
        except Exception as e:
            self.logger.error(f"Fatal error during reconstruction: {e}")
            self._emit_status("failed", f"Fatal error: {str(e)}")
            return False
    
    @contextmanager
    def _managed_resources(self):
        """Context manager for resource cleanup"""
        try:
            # Create temporary directory
            self.temp_dir = Path(tempfile.mkdtemp(prefix="takeout_rebuild_"))
            yield
        finally:
            # Cleanup
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            
            # Clear caches
            self.duplicate_checker.clear_cache()
    
    def _validate_inputs(self) -> bool:
        """Validate input parameters"""
        if not self.source_dir.exists():
            self._record_error("validation", f"Source directory does not exist: {self.source_dir}", "ValidationError")
            return False
        
        if not self.source_dir.is_dir():
            self._record_error("validation", f"Source path is not a directory: {self.source_dir}", "ValidationError")
            return False
        
        return True
    
    def _process_files(self, files: List[FileInfo], verify_copies: bool = False) -> bool:
        """Process all files from the scan"""
        processed = 0
        
        for file_info in files:
            processed += 1
            
            # Update progress
            progress_percent = (processed / self.stats.total_files) * 100
            self._emit_progress({
                'type': 'progress',
                'percent': progress_percent,
                'current_file': file_info.path.name,
                'operation': f"Processing file {processed}/{self.stats.total_files}"
            })
            
            try:
                result = self._process_single_file(file_info, verify_copies)
                
                # Update stats based on result
                if result == "copied":
                    self.stats.copied_files += 1
                    self.stats.copied_size += file_info.size
                elif result == "skipped_duplicate":
                    self.stats.skipped_duplicates += 1
                elif result == "skipped_metadata":
                    self.stats.skipped_metadata += 1
                elif result == "error":
                    self.stats.errors += 1
                
            except Exception as e:
                self.stats.errors += 1
                self._record_error(
                    str(file_info.path),
                    f"Unexpected error processing file: {e}",
                    "ProcessingError"
                )
        
        return self.stats.errors == 0
    
    def _process_single_file(self, file_info: FileInfo, verify_copies: bool = False) -> str:
        """
        Process a single file
        
        Returns:
            String indicating the result: "copied", "skipped_duplicate", "skipped_metadata", "error"
        """
        # Skip metadata files
        if file_info.is_metadata:
            self.logger.debug(f"Skipping metadata file: {file_info.path.name}")
            return "skipped_metadata"
        
        # Normalize the destination path
        transformation = self.path_normalizer.normalize_path(
            file_info.relative_path, 
            file_info.is_metadata
        )
        
        if transformation.should_skip or not transformation.clean_path:
            self.logger.debug(transformation.transformation_log)
            return "skipped_metadata"
        
        dest_path = transformation.clean_path
        self.logger.debug(transformation.transformation_log)
        
        # Check for duplicates
        duplicate_result = self.duplicate_checker.is_duplicate(file_info.path, dest_path)
        if duplicate_result.is_duplicate:
            self.logger.info(f"Skipped duplicate: {file_info.path.name} ({duplicate_result.reason})")
            return "skipped_duplicate"
        
        # Copy the file
        if not self.dry_run:
            success = self._copy_file(file_info.path, dest_path, verify_copies)
            if success:
                return "copied"
            else:
                return "error"
        else:
            self.logger.info(f"Would copy: {file_info.path} -> {dest_path}")
            return "copied"
    
    def _copy_file(self, source_path: Path, dest_path: Path, verify: bool = False) -> bool:
        """
        Copy a single file with verification
        
        Returns:
            True if successful, False if failed
        """
        try:
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Choose copy method based on file size
            file_size = source_path.stat().st_size
            
            if file_size > 100 * 1024 * 1024:  # 100MB
                self._chunked_copy(source_path, dest_path)
            else:
                shutil.copy2(source_path, dest_path)
            
            # Verify copy if requested
            if verify:
                if not self._verify_copy(source_path, dest_path):
                    dest_path.unlink()  # Remove bad copy
                    self._record_error(
                        str(source_path),
                        "Copy verification failed",
                        "VerificationError"
                    )
                    return False
            
            return True
            
        except Exception as e:
            self._record_error(
                str(source_path),
                f"Copy failed: {e}",
                "CopyError"
            )
            return False
    
    def _chunked_copy(self, source_path: Path, dest_path: Path, chunk_size: int = 1024 * 1024):
        """Copy large files in chunks"""
        with open(source_path, 'rb') as src, open(dest_path, 'wb') as dst:
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                dst.write(chunk)
        
        # Copy metadata
        shutil.copystat(source_path, dest_path)
    
    def _verify_copy(self, source_path: Path, dest_path: Path) -> bool:
        """Verify that a file was copied correctly"""
        try:
            import filecmp
            return filecmp.cmp(source_path, dest_path, shallow=False)
        except Exception as e:
            self.logger.error(f"Error verifying copy {source_path} -> {dest_path}: {e}")
            return False
    
    def _record_error(self, file_path: str, message: str, error_type: str):
        """Record an error for later reporting"""
        error = ProcessingError(
            file_path=file_path,
            error_message=message,
            timestamp=datetime.now().isoformat(),
            error_type=error_type
        )
        self.errors.append(error)
        self.logger.error(f"{error_type}: {message}")
    
    def _write_manifest(self):
        """Write reconstruction manifest"""
        manifest = {
            'reconstruction_date': datetime.now().isoformat(),
            'source_directory': str(self.source_dir),
            'destination_directory': str(self.dest_dir),
            'dry_run': self.dry_run,
            'statistics': self.stats.to_dict(),
            'duplicate_checker_stats': self.duplicate_checker.get_stats(),
            'error_count': len(self.errors)
        }
        
        if not self.dry_run:
            with open(self.manifest_file, 'w') as f:
                json.dump(manifest, f, indent=2)
            self.logger.info(f"Manifest saved to {self.manifest_file}")
    
    def _write_error_log(self):
        """Write detailed error log"""
        if not self.errors:
            return
            
        if not self.dry_run:
            with open(self.error_log_file, 'w') as f:
                f.write(f"Error Log - {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")
                
                for error in self.errors:
                    f.write(f"[{error.timestamp}] {error.error_type}\n")
                    f.write(f"File: {error.file_path}\n")
                    f.write(f"Error: {error.error_message}\n")
                    f.write("-" * 30 + "\n")
            
            self.logger.info(f"Error log written to {self.error_log_file}")
    
    def _log_final_statistics(self):
        """Log final reconstruction statistics"""
        self.logger.info("=== Reconstruction Complete ===")
        self.logger.info(f"Total files scanned: {self.stats.total_files}")
        self.logger.info(f"Files copied: {self.stats.copied_files}")
        self.logger.info(f"Duplicates skipped: {self.stats.skipped_duplicates}")
        self.logger.info(f"Metadata skipped: {self.stats.skipped_metadata}")
        self.logger.info(f"Errors: {self.stats.errors}")
        self.logger.info(f"Total size: {self.stats.total_size / (1024**3):.2f} GB")
        self.logger.info(f"Copied size: {self.stats.copied_size / (1024**3):.2f} GB")
        
        # Emit stats for GUI
        self._emit_progress({
            'type': 'stats',
            'stats': self.stats.to_dict()
        })
    
    def _emit_progress(self, data: Dict[str, Any]):
        """Emit progress update"""
        if self.progress_callback:
            self.progress_callback(data)
    
    def _emit_status(self, status: str, message: str):
        """Emit status update"""
        self._emit_progress({
            'type': 'status',
            'status': status,
            'message': message
        })
    
    def cancel(self):
        """Cancel the operation"""
        self.logger.warning("Operation cancelled by user")
        self._emit_status('cancelled', 'Operation cancelled by user')
    
    def close(self):
        """Clean up resources (alternative to __del__)"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.duplicate_checker.clear_cache()
        self.logger.info("🧹 Resource cleanup completed")