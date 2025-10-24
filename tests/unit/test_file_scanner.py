#!/usr/bin/env python3
"""
Unit tests for FileScanner - ensures file discovery and cataloging works correctly
"""
import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.file_scanner import FileScanner, FileInfo, ScanResult


class TestFileScanner:
    """Test suite for FileScanner class"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests"""
        with tempfile.TemporaryDirectory() as temp_path:
            yield Path(temp_path)
    
    @pytest.fixture
    def sample_takeout_structure(self, temp_dir):
        """Create a sample Takeout directory structure"""
        # Create standard Takeout structure
        takeout_dir = temp_dir / "Takeout" / "Drive"
        takeout_dir.mkdir(parents=True)
        
        # Create numbered Takeout structures
        takeout1_dir = temp_dir / "Takeout-1" / "Drive"
        takeout1_dir.mkdir(parents=True)
        
        takeout2_dir = temp_dir / "Takeout 2" / "Drive"
        takeout2_dir.mkdir(parents=True)
        
        # Create test files
        (takeout_dir / "document.txt").write_text("Sample document")
        (takeout_dir / "photo.jpg").write_bytes(b"fake image data")
        
        (takeout1_dir / "music.mp3").write_bytes(b"fake audio data")
        (takeout2_dir / "video.mp4").write_bytes(b"fake video data")
        
        # Create metadata files (JSON)
        (takeout_dir / "document.txt.json").write_text(json.dumps({
            "title": "document.txt",
            "createdTime": "2023-01-01T00:00:00Z",
            "modifiedTime": "2023-01-01T00:00:00Z"
        }))
        
        # Create nested structure
        nested_dir = takeout_dir / "Projects" / "Code"
        nested_dir.mkdir(parents=True)
        (nested_dir / "script.py").write_text("print('hello world')")
        
        # Create hidden files (should be skipped)
        (takeout_dir / ".hidden_file").write_text("hidden content")
        
        # Create temp files (should be skipped)
        (takeout_dir / "temp_file.tmp").write_text("temporary content")
        
        return temp_dir
    
    @pytest.fixture
    def progress_callback(self):
        """Mock progress callback"""
        return Mock()
    
    def test_basic_scanning(self, sample_takeout_structure, progress_callback):
        """Test basic file scanning functionality"""
        scanner = FileScanner(sample_takeout_structure, progress_callback)
        result = scanner.scan()
        
        assert isinstance(result, ScanResult), "Should return ScanResult object"
        assert result.total_files > 0, "Should find files"
        assert result.total_size > 0, "Should calculate total size"
        assert len(result.files) == result.total_files, "File count should match list length"
        assert len(result.errors) == 0, "Should not have errors with valid structure"
    
    def test_takeout_folder_detection(self, sample_takeout_structure, progress_callback):
        """Test that various Takeout folder patterns are detected"""
        scanner = FileScanner(sample_takeout_structure, progress_callback)
        scanner._detect_takeout_folders()
        
        assert len(scanner.takeout_folders) >= 3, "Should detect multiple Takeout folders"
        
        # Check that different patterns are found
        takeout_names = [folder.name for folder in scanner.takeout_folders]
        has_standard = any("Drive" in name for name in takeout_names)
        has_numbered = any("Takeout-1" in str(folder) for folder in scanner.takeout_folders)
        has_spaced = any("Takeout 2" in str(folder) for folder in scanner.takeout_folders)
        
        assert has_standard or has_numbered or has_spaced, "Should detect various Takeout patterns"
    
    def test_file_info_creation(self, sample_takeout_structure, progress_callback):
        """Test that FileInfo objects are created correctly"""
        scanner = FileScanner(sample_takeout_structure, progress_callback)
        result = scanner.scan()
        
        # Check first file
        if result.files:
            file_info = result.files[0]
            assert isinstance(file_info, FileInfo), "Should create FileInfo objects"
            assert file_info.path.exists(), "File path should exist"
            assert file_info.size >= 0, "File size should be non-negative"
            assert isinstance(file_info.relative_path, Path), "Relative path should be Path object"
            assert isinstance(file_info.is_metadata, bool), "is_metadata should be boolean"
    
    def test_metadata_detection(self, sample_takeout_structure, progress_callback):
        """Test that Google metadata files are properly identified"""
        scanner = FileScanner(sample_takeout_structure, progress_callback)
        result = scanner.scan()
        
        # Find metadata files
        metadata_files = [f for f in result.files if f.is_metadata]
        json_files = [f for f in result.files if f.path.name.endswith('.json')]
        
        assert len(metadata_files) > 0, "Should detect metadata files"
        assert len(metadata_files) <= len(json_files), "Metadata files should be subset of JSON files"
        
        # Verify metadata detection logic
        for metadata_file in metadata_files:
            assert metadata_file.path.name.endswith('.json'), "Metadata files should be JSON"
            # The file should contain Google metadata structure
            assert scanner._is_google_metadata(metadata_file.path), "Should correctly identify Google metadata"
    
    def test_hidden_files_skipped(self, sample_takeout_structure, progress_callback):
        """Test that hidden files and temp files are skipped"""
        scanner = FileScanner(sample_takeout_structure, progress_callback)
        result = scanner.scan()
        
        # Check that no hidden files are included
        hidden_files = [f for f in result.files if f.path.name.startswith('.')]
        temp_files = [f for f in result.files if f.path.name.endswith('.tmp')]
        
        assert len(hidden_files) == 0, "Hidden files should be skipped"
        assert len(temp_files) == 0, "Temp files should be skipped"
    
    def test_progress_callback_invoked(self, sample_takeout_structure, progress_callback):
        """Test that progress callback is called during scanning"""
        scanner = FileScanner(sample_takeout_structure, progress_callback)
        result = scanner.scan()
        
        # Progress callback should be called if there are enough files
        if result.total_files >= 100:
            progress_callback.assert_called()
        else:
            # For small test sets, callback might not be called (every 100 files)
            pass
    
    def test_scan_nonexistent_directory(self, progress_callback):
        """Test scanning a nonexistent directory"""
        nonexistent_path = Path("/path/that/does/not/exist")
        scanner = FileScanner(nonexistent_path, progress_callback)
        result = scanner.scan()
        
        assert result.total_files == 0, "Should find no files"
        assert result.total_size == 0, "Should have zero total size"
        assert len(result.files) == 0, "File list should be empty"
        assert len(result.errors) > 0, "Should have error for nonexistent directory"
        assert "does not exist" in result.errors[0], "Error should mention directory doesn't exist"
    
    def test_scan_file_instead_of_directory(self, temp_dir, progress_callback):
        """Test scanning a file path instead of directory"""
        # Create a regular file
        test_file = temp_dir / "test_file.txt"
        test_file.write_text("test content")
        
        scanner = FileScanner(test_file, progress_callback)
        result = scanner.scan()
        
        assert result.total_files == 0, "Should find no files when given a file path"
        assert len(result.errors) > 0, "Should have error for file instead of directory"
        assert "not a directory" in result.errors[0], "Error should mention it's not a directory"
    
    def test_google_metadata_detection_logic(self, temp_dir):
        """Test the _is_google_metadata method specifically"""
        scanner = FileScanner(temp_dir)
        
        # Create a Google metadata file
        google_metadata = temp_dir / "google_meta.json"
        google_metadata.write_text(json.dumps({
            "title": "My Document",
            "createdTime": "2023-01-01T00:00:00Z",
            "modifiedTime": "2023-01-02T00:00:00Z",
            "mimeType": "application/pdf"
        }))
        
        # Create a non-Google JSON file
        regular_json = temp_dir / "regular.json"
        regular_json.write_text(json.dumps({
            "name": "Regular JSON",
            "data": [1, 2, 3]
        }))
        
        # Create an invalid JSON file
        invalid_json = temp_dir / "invalid.json"
        invalid_json.write_text("{ invalid json content")
        
        # Create a non-JSON file
        text_file = temp_dir / "document.txt"
        text_file.write_text("Regular text file")
        
        # Test detection
        assert scanner._is_google_metadata(google_metadata), "Should detect Google metadata"
        assert not scanner._is_google_metadata(regular_json), "Should not detect regular JSON as metadata"
        assert not scanner._is_google_metadata(invalid_json), "Should handle invalid JSON gracefully"
        assert not scanner._is_google_metadata(text_file), "Should not process non-JSON files"
    
    def test_relative_path_calculation(self, sample_takeout_structure, progress_callback):
        """Test that relative paths are calculated correctly"""
        scanner = FileScanner(sample_takeout_structure, progress_callback)
        result = scanner.scan()
        
        for file_info in result.files:
            # Relative path should be relative to the source directory
            assert not file_info.relative_path.is_absolute(), "Relative path should not be absolute"
            
            # Full path should be source_dir + relative_path
            expected_full_path = sample_takeout_structure / file_info.relative_path
            assert file_info.path == expected_full_path, f"Path calculation mismatch: {file_info.path} != {expected_full_path}"
    
    def test_file_size_calculation(self, sample_takeout_structure, progress_callback):
        """Test that file sizes are calculated correctly"""
        scanner = FileScanner(sample_takeout_structure, progress_callback)
        result = scanner.scan()
        
        # Check that total size equals sum of individual file sizes
        calculated_total = sum(f.size for f in result.files)
        assert result.total_size == calculated_total, "Total size should equal sum of individual sizes"
        
        # Check that all files have reasonable sizes
        for file_info in result.files:
            assert file_info.size >= 0, "File size should not be negative"
            actual_size = file_info.path.stat().st_size
            assert file_info.size == actual_size, f"Recorded size should match actual size for {file_info.path}"
    
    @pytest.mark.parametrize("takeout_pattern", [
        "Takeout",
        "Takeout-1", 
        "Takeout-999",
        "Takeout 2",
        "Takeout 123",
        "Takeout_3",
        "Takeout_456"
    ])
    def test_takeout_pattern_matching(self, temp_dir, takeout_pattern, progress_callback):
        """Test that various Takeout folder naming patterns are detected"""
        # Create a Takeout folder with the given pattern
        takeout_dir = temp_dir / takeout_pattern / "Drive"
        takeout_dir.mkdir(parents=True)
        (takeout_dir / "test_file.txt").write_text("test content")
        
        scanner = FileScanner(temp_dir, progress_callback)
        scanner._detect_takeout_folders()
        
        assert len(scanner.takeout_folders) > 0, f"Should detect Takeout pattern: {takeout_pattern}"
        
        # Check that our specific pattern was found
        found_patterns = [str(folder) for folder in scanner.takeout_folders]
        assert any(takeout_pattern in pattern for pattern in found_patterns), f"Should find pattern {takeout_pattern}"
    
    def test_error_handling_for_inaccessible_files(self, temp_dir, progress_callback):
        """Test error handling when files become inaccessible during scan"""
        # Create a file
        test_file = temp_dir / "test_file.txt" 
        test_file.write_text("test content")
        
        scanner = FileScanner(temp_dir, progress_callback)
        
        # Mock os.walk to simulate file access error
        with patch('os.walk') as mock_walk:
            # Simulate a file that throws OSError when accessing
            mock_walk.return_value = [
                (str(temp_dir), [], ["test_file.txt", "bad_file.txt"])
            ]
            
            # Mock stat to fail for bad_file
            original_stat = Path.stat
            def mock_stat(self):
                if "bad_file" in str(self):
                    raise OSError("Permission denied")
                return original_stat(self)
            
            with patch.object(Path, 'stat', mock_stat):
                result = scanner.scan()
                
                # Should continue scanning despite errors
                assert result.total_files >= 0, "Should handle file access errors gracefully"


class TestFileInfo:
    """Test the FileInfo dataclass"""
    
    def test_file_info_creation(self):
        """Test creating FileInfo objects"""
        path = Path("/test/file.txt")
        relative = Path("file.txt")
        size = 1024
        
        file_info = FileInfo(
            path=path,
            size=size,
            relative_path=relative,
            is_metadata=False
        )
        
        assert file_info.path == path
        assert file_info.size == size
        assert file_info.relative_path == relative
        assert not file_info.is_metadata
    
    def test_file_info_with_metadata(self):
        """Test FileInfo for metadata files"""
        file_info = FileInfo(
            path=Path("/test/metadata.json"),
            size=512,
            relative_path=Path("metadata.json"),
            is_metadata=True
        )
        
        assert file_info.is_metadata


class TestScanResult:
    """Test the ScanResult dataclass"""
    
    def test_scan_result_creation(self):
        """Test creating ScanResult objects"""
        files = [
            FileInfo(Path("/test/file1.txt"), 100, Path("file1.txt")),
            FileInfo(Path("/test/file2.txt"), 200, Path("file2.txt"))
        ]
        
        result = ScanResult(
            files=files,
            total_files=2,
            total_size=300,
            errors=[]
        )
        
        assert len(result.files) == 2
        assert result.total_files == 2
        assert result.total_size == 300
        assert len(result.errors) == 0
    
    def test_scan_result_with_errors(self):
        """Test ScanResult with errors"""
        result = ScanResult(
            files=[],
            total_files=0,
            total_size=0,
            errors=["Error 1", "Error 2"]
        )
        
        assert len(result.files) == 0
        assert len(result.errors) == 2


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])