"""
ZIP extraction module for Google Drive Takeout files
"""
from __future__ import annotations

import zipfile
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Callable
from .logger import ProgressLogger


class TakeoutExtractor:
    """Handles extraction of Google Takeout ZIP files"""
    
    def __init__(self, logger: Optional[ProgressLogger] = None):
        self.logger = logger or ProgressLogger("extractor")
        self.temp_dirs: List[Path] = []
    
    def extract_zip_files(self, zip_files: List[Path], extract_to: Optional[Path] = None) -> Path:
        """
        Extract multiple ZIP files to a temporary or specified directory
        
        Args:
            zip_files: List of ZIP file paths to extract
            extract_to: Optional destination directory (creates temp dir if None)
        
        Returns:
            Path to extraction directory
        """
        if extract_to is None:
            extract_to = Path(tempfile.mkdtemp(prefix="takeout_extract_"))
            self.temp_dirs.append(extract_to)
        else:
            extract_to.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Starting extraction of {len(zip_files)} ZIP files")
        self.logger.status("extracting", f"Extracting {len(zip_files)} ZIP files...")
        
        total_files = 0
        extracted_files = 0
        
        # First pass: count total files
        for zip_path in zip_files:
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    total_files += len(zip_ref.namelist())
            except Exception as e:
                self.logger.warning(f"Could not read ZIP file {zip_path.name}: {str(e)}")
        
        self.logger.info(f"Total files to extract: {total_files}")
        
        # Second pass: extract files
        for i, zip_path in enumerate(zip_files):
            try:
                self.logger.progress(
                    percent=(i / len(zip_files)) * 100,
                    current_file=zip_path.name,
                    operation=f"Extracting ZIP {i+1} of {len(zip_files)}"
                )
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    file_list = zip_ref.namelist()
                    
                    for j, file_name in enumerate(file_list):
                        try:
                            # Update progress for individual files
                            file_progress = ((i * total_files + j) / total_files) * 100 if total_files > 0 else 0
                            self.logger.progress(
                                percent=file_progress,
                                current_file=file_name,
                                operation=f"Extracting from {zip_path.name}"
                            )
                            
                            # Extract the file
                            zip_ref.extract(file_name, extract_to)
                            extracted_files += 1
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to extract {file_name}: {str(e)}")
                
                self.logger.success(f"Extracted {zip_path.name}")
                
            except Exception as e:
                self.logger.error(f"Failed to extract ZIP file {zip_path.name}: {str(e)}")
        
        self.logger.stats({
            'total_files_extracted': extracted_files,
            'zip_files_processed': len(zip_files)
        })
        
        self.logger.success(f"Extraction complete. Extracted {extracted_files} files to {extract_to}")
        return extract_to
    
    def find_takeout_zips(self, search_dir: Path) -> List[Path]:
        """
        Find all valid Takeout ZIP files in a directory
        
        Args:
            search_dir: Directory to search for ZIP files
        
        Returns:
            List of valid ZIP file paths
        """
        zip_files = []
        
        if not search_dir.exists() or not search_dir.is_dir():
            self.logger.error(f"Search directory does not exist: {search_dir}")
            return zip_files
        
        self.logger.info(f"Searching for ZIP files in {search_dir}")
        
        for zip_file in search_dir.glob("*.zip"):
            # Skip system files and temporary files
            filename = zip_file.name.lower()
            if (
                filename.startswith('._') or
                filename.startswith('.') or
                filename in ['thumbs.db', 'desktop.ini', 'folder.htt'] or
                filename.endswith('.tmp') or
                filename.endswith('.temp')
            ):
                continue
            
            # Verify it's a valid ZIP file
            try:
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    # Test the ZIP file
                    zip_ref.testzip()
                zip_files.append(zip_file)
                self.logger.info(f"Found valid ZIP file: {zip_file.name}")
            except Exception as e:
                self.logger.warning(f"Invalid ZIP file {zip_file.name}: {str(e)}")
        
        self.logger.info(f"Found {len(zip_files)} valid ZIP files")
        return zip_files
    
    def cleanup_temp_dirs(self):
        """Clean up temporary extraction directories"""
        for temp_dir in self.temp_dirs:
            try:
                if temp_dir.exists():
                    import shutil
                    shutil.rmtree(temp_dir)
                    self.logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up {temp_dir}: {str(e)}")
        
        self.temp_dirs.clear()
    
    def __del__(self):
        """Cleanup on destruction"""
        self.cleanup_temp_dirs()
