"""
File Scanner - Handles walking source directories and collecting file information
"""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Iterator, Optional
import logging


@dataclass
class FileInfo:
    """Information about a discovered file"""
    path: Path
    size: int
    relative_path: Path
    is_metadata: bool = False


@dataclass
class ScanResult:
    """Result of scanning a directory"""
    files: List[FileInfo]
    total_files: int
    total_size: int
    errors: List[str]


class FileScanner:
    """Responsible for scanning source directories and cataloging files"""
    
    def __init__(self, source_dir: Path, progress_callback: Optional[callable] = None):
        self.source_dir = Path(source_dir)
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)
    
    def scan(self) -> ScanResult:
        """
        Scan the source directory and return file information
        
        Returns:
            ScanResult with all discovered files and metadata
        """
        files = []
        errors = []
        total_size = 0
        
        if not self.source_dir.exists():
            errors.append(f"Source directory does not exist: {self.source_dir}")
            return ScanResult(files=[], total_files=0, total_size=0, errors=errors)
        
        if not self.source_dir.is_dir():
            errors.append(f"Source path is not a directory: {self.source_dir}")
            return ScanResult(files=[], total_files=0, total_size=0, errors=errors)
        
        # Walk directory tree
        for file_info in self._walk_directory():
            files.append(file_info)
            total_size += file_info.size
            
            # Report progress
            if self.progress_callback and len(files) % 100 == 0:
                self.progress_callback({
                    'type': 'scan_progress',
                    'files_found': len(files),
                    'current_file': str(file_info.path.name),
                    'total_size_gb': total_size / (1024**3)
                })
        
        self.logger.info(f"Scan complete: {len(files)} files, {total_size / (1024**3):.2f} GB")
        
        return ScanResult(
            files=files,
            total_files=len(files),
            total_size=total_size,
            errors=errors
        )
    
    def _walk_directory(self) -> Iterator[FileInfo]:
        """Walk directory tree and yield FileInfo objects"""
        try:
            for root, dirs, files in os.walk(self.source_dir):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                root_path = Path(root)
                
                for file_name in files:
                    # Skip hidden and temp files
                    if file_name.startswith('.') or file_name.endswith('.tmp'):
                        continue
                    
                    file_path = root_path / file_name
                    
                    try:
                        # Get file info
                        stat_info = file_path.stat()
                        relative_path = file_path.relative_to(self.source_dir)
                        
                        # Check if this is Google metadata
                        is_metadata = self._is_google_metadata(file_path)
                        
                        yield FileInfo(
                            path=file_path,
                            size=stat_info.st_size,
                            relative_path=relative_path,
                            is_metadata=is_metadata
                        )
                        
                    except (OSError, ValueError) as e:
                        self.logger.warning(f"Could not process file {file_path}: {e}")
                        continue
                        
        except OSError as e:
            self.logger.error(f"Error walking directory {self.source_dir}: {e}")
            return
    
    def _is_google_metadata(self, file_path: Path) -> bool:
        """Check if a file is Google metadata that should be skipped"""
        if not file_path.name.endswith('.json'):
            return False
        
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Check for Google metadata structure
                return any(key in data for key in ['title', 'createdTime', 'modifiedTime', 'mimeType'])
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return False