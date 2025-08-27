"""
Test utilities and helper functions
"""
from __future__ import annotations

import zipfile
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import tempfile


def create_test_zip(output_path: Path, files: Dict[str, str]) -> Path:
    """
    Create a test ZIP file with specified contents
    
    Args:
        output_path: Path where the ZIP file should be created
        files: Dictionary mapping file paths to their content
    
    Returns:
        Path to the created ZIP file
    """
    with zipfile.ZipFile(output_path, 'w') as zipf:
        for file_path, content in files.items():
            zipf.writestr(file_path, content)
    return output_path


def create_takeout_structure(base_path: Path) -> Dict[str, Any]:
    """
    Create a mock Google Takeout directory structure
    
    Args:
        base_path: Base directory to create the structure in
    
    Returns:
        Dictionary with information about created files
    """
    structure = {
        'files_created': [],
        'total_size': 0,
        'base_path': base_path
    }
    
    # Create Takeout directory
    takeout_dir = base_path / "Takeout"
    takeout_dir.mkdir(parents=True, exist_ok=True)
    
    # Create Drive directory
    drive_dir = takeout_dir / "Drive"
    drive_dir.mkdir(exist_ok=True)
    
    # Create various files and folders
    test_files = {
        "Drive/document.txt": "This is a test document",
        "Drive/Folder1/file1.txt": "File in Folder1",
        "Drive/Folder1/SubFolder/nested.txt": "Nested file",
        "Drive/Folder2/image.jpg": b"fake_image_data",
        "Drive/spreadsheet.xlsx": b"fake_spreadsheet_data",
        "Drive/My Folder/special chars & spaces.txt": "File with special characters"
    }
    
    for rel_path, content in test_files.items():
        file_path = takeout_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, bytes):
            file_path.write_bytes(content)
            structure['total_size'] += len(content)
        else:
            file_path.write_text(content)
            structure['total_size'] += len(content.encode())
        
        structure['files_created'].append(str(file_path.relative_to(base_path)))
    
    return structure


def create_mock_progress_callback():
    """
    Create a mock progress callback for testing
    
    Returns:
        Mock callback function that records calls
    """
    calls = []
    
    def callback(status: str, message: str, percent: float = 0):
        calls.append({
            'status': status,
            'message': message,
            'percent': percent,
            'timestamp': datetime.now()
        })
    
    callback.calls = calls
    return callback


def create_manifest_file(output_path: Path, source_dir: Path, dest_dir: Path, 
                        files_copied: List[Dict]) -> Path:
    """
    Create a mock manifest file for testing rollback
    
    Args:
        output_path: Path where the manifest should be saved
        source_dir: Source directory path
        dest_dir: Destination directory path
        files_copied: List of file copy information
    
    Returns:
        Path to the created manifest file
    """
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'source_directory': str(source_dir),
        'destination_directory': str(dest_dir),
        'copied_files': files_copied,
        'statistics': {
            'total_files': len(files_copied),
            'total_size': sum(f.get('size', 0) for f in files_copied)
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    return output_path


def compare_directories(dir1: Path, dir2: Path, 
                       ignore_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Compare two directories and return differences
    
    Args:
        dir1: First directory to compare
        dir2: Second directory to compare
        ignore_patterns: List of filename patterns to ignore
    
    Returns:
        Dictionary with comparison results
    """
    ignore_patterns = ignore_patterns or []
    
    def should_ignore(path: Path) -> bool:
        name = path.name
        for pattern in ignore_patterns:
            if pattern in name:
                return True
        return False
    
    def get_files(directory: Path) -> set:
        files = set()
        for item in directory.rglob('*'):
            if item.is_file() and not should_ignore(item):
                rel_path = item.relative_to(directory)
                files.add(str(rel_path))
        return files
    
    files1 = get_files(dir1)
    files2 = get_files(dir2)
    
    return {
        'identical': files1 == files2,
        'only_in_first': files1 - files2,
        'only_in_second': files2 - files1,
        'common_files': files1 & files2,
        'total_files_first': len(files1),
        'total_files_second': len(files2)
    }


def cleanup_test_directory(directory: Path):
    """
    Safely clean up a test directory
    
    Args:
        directory: Directory to clean up
    """
    if directory.exists() and str(directory).startswith('/tmp'):
        shutil.rmtree(directory, ignore_errors=True)


class TempDirectoryManager:
    """Context manager for temporary test directories"""
    
    def __init__(self, prefix: str = "test_"):
        self.prefix = prefix
        self.temp_dir = None
    
    def __enter__(self) -> Path:
        self.temp_dir = Path(tempfile.mkdtemp(prefix=self.prefix))
        return self.temp_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)


def assert_file_contains(file_path: Path, expected_content: str):
    """
    Assert that a file contains expected content
    
    Args:
        file_path: Path to the file to check
        expected_content: Content that should be in the file
    """
    assert file_path.exists(), f"File {file_path} does not exist"
    content = file_path.read_text()
    assert expected_content in content, \
        f"Expected '{expected_content}' not found in {file_path}"


def assert_directory_structure(base_path: Path, expected_structure: List[str]):
    """
    Assert that a directory has the expected structure
    
    Args:
        base_path: Base directory to check
        expected_structure: List of relative paths that should exist
    """
    for rel_path in expected_structure:
        full_path = base_path / rel_path
        assert full_path.exists(), f"Expected path {full_path} does not exist"


def create_large_file(path: Path, size_mb: int) -> Path:
    """
    Create a large file for testing
    
    Args:
        path: Path where the file should be created
        size_mb: Size of the file in megabytes
    
    Returns:
        Path to the created file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write data in chunks to avoid memory issues
    chunk_size = 1024 * 1024  # 1MB chunks
    remaining = size_mb * 1024 * 1024
    
    with open(path, 'wb') as f:
        while remaining > 0:
            write_size = min(chunk_size, remaining)
            f.write(b'0' * write_size)
            remaining -= write_size
    
    return path


def mock_gui_state():
    """
    Create a mock GUI state for testing
    
    Returns:
        Dictionary representing GUI state
    """
    return {
        'status': 'idle',
        'progress': 0,
        'current_file': '',
        'operation': '',
        'stats': {
            'total_files': 0,
            'copied_files': 0,
            'skipped_duplicates': 0,
            'errors': 0
        },
        'logs': [],
        'errors': [],
        'start_time': None,
        'end_time': None
    }