"""
Pytest configuration and shared fixtures for Google Drive Takeout Consolidator tests
"""
from __future__ import annotations

import pytest
import tempfile
import shutil
import zipfile
from pathlib import Path
from typing import Generator
from unittest.mock import Mock

# Add app to path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from app.core.logger import ProgressLogger
from app.core.rebuilder import SafeTakeoutReconstructor
from app.config import get_test_config


@pytest.fixture
def test_config():
    """Get test configuration"""
    return get_test_config()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests"""
    temp_path = Path(tempfile.mkdtemp(prefix="takeout_test_"))
    try:
        yield temp_path
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_progress_callback():
    """Mock progress callback for testing"""
    return Mock()


@pytest.fixture
def test_logger(mock_progress_callback):
    """Create a test logger with mock callback"""
    logger = ProgressLogger("test")
    logger.set_progress_callback(mock_progress_callback, "test_operation")
    return logger


@pytest.fixture
def sample_takeout_structure(temp_dir: Path) -> Path:
    """Create a sample Takeout directory structure for testing"""
    takeout_dir = temp_dir / "sample_takeout"
    takeout_dir.mkdir()
    
    # Create sample directory structure
    drive_dir = takeout_dir / "Takeout" / "Drive"
    drive_dir.mkdir(parents=True)
    
    # Create some sample files
    (drive_dir / "document1.txt").write_text("Sample document 1")
    (drive_dir / "document2.txt").write_text("Sample document 2")
    
    # Create a subdirectory
    sub_dir = drive_dir / "SubFolder"
    sub_dir.mkdir()
    (sub_dir / "subdoc.txt").write_text("Document in subfolder")
    
    # Create some metadata files (should be ignored)
    (drive_dir / "document1.txt.json").write_text('{"title": "document1.txt", "createdTime": "2023-01-01"}')
    
    return takeout_dir


@pytest.fixture
def sample_zip_file(temp_dir: Path, sample_takeout_structure: Path) -> Path:
    """Create a sample ZIP file containing Takeout structure"""
    zip_path = temp_dir / "takeout_sample.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in sample_takeout_structure.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(sample_takeout_structure)
                zipf.write(file_path, arcname)
    
    return zip_path


@pytest.fixture
def sample_zip_directory(temp_dir: Path, sample_zip_file: Path) -> Path:
    """Create a directory containing sample ZIP files"""
    zip_dir = temp_dir / "zip_files"
    zip_dir.mkdir()
    
    # Copy the sample ZIP file
    shutil.copy2(sample_zip_file, zip_dir / "takeout_part1.zip")
    
    # Create another ZIP file
    zip_path2 = zip_dir / "takeout_part2.zip"
    with zipfile.ZipFile(zip_path2, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("Takeout/Drive/additional_file.txt", "Additional content")
    
    return zip_dir


@pytest.fixture
def output_directory(temp_dir: Path) -> Path:
    """Create an output directory for test results"""
    output_dir = temp_dir / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def reconstructor(sample_takeout_structure: Path, output_directory: Path, mock_progress_callback):
    """Create a SafeTakeoutReconstructor instance for testing"""
    return SafeTakeoutReconstructor(
        takeout_path=str(sample_takeout_structure),
        export_path=str(output_directory),
        dry_run=True,  # Default to dry run for safety
        progress_callback=mock_progress_callback,
        gui_mode=True
    )


@pytest.fixture
def large_file_content() -> bytes:
    """Generate content for testing large file operations"""
    # Create 1MB of test data
    return b"test_data_chunk" * (1024 * 1024 // 15)  # Approximately 1MB


@pytest.fixture
def complex_takeout_structure(temp_dir: Path) -> Path:
    """Create a more complex Takeout structure for advanced testing"""
    takeout_dir = temp_dir / "complex_takeout"
    takeout_dir.mkdir()
    
    # Multiple Takeout folders (simulating multiple exports)
    for i in range(1, 4):
        takeout_sub = takeout_dir / f"Takeout_{i}"
        drive_dir = takeout_sub / "Drive"
        drive_dir.mkdir(parents=True)
        
        # Create files with potential conflicts
        (drive_dir / "shared_file.txt").write_text(f"Content from export {i}")
        (drive_dir / f"unique_file_{i}.txt").write_text(f"Unique content {i}")
        
        # Create nested directories
        nested_dir = drive_dir / "Shared" / f"Folder_{i}"
        nested_dir.mkdir(parents=True)
        (nested_dir / "nested_file.txt").write_text(f"Nested content {i}")
    
    return takeout_dir


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location"""
    for item in items:
        # Add markers based on test file location
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif "unit" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        
        # Mark slow tests
        if "slow" in item.name or "large" in item.name:
            item.add_marker(pytest.mark.slow)
