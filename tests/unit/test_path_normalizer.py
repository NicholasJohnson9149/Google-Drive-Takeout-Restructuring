#!/usr/bin/env python3
"""
Unit tests for PathNormalizer - ensures path transformations work correctly
"""
import pytest
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.path_normalizer import PathNormalizer, PathTransformation


class TestPathNormalizer:
    """Test suite for PathNormalizer class"""
    
    @pytest.fixture
    def normalizer(self):
        """Create a PathNormalizer instance for testing"""
        return PathNormalizer(Path("/test/destination"))
    
    def test_standard_takeout_drive_structure(self, normalizer):
        """Test standard Takeout/Drive/folder/file.txt structure"""
        test_cases = [
            ("Takeout/Drive/Documents/file.pdf", "Documents/file.pdf"),
            ("Takeout/Drive/Photos/2023/vacation.jpg", "Photos/2023/vacation.jpg"),
            ("Takeout/Drive/Music/Artist/Album/song.mp3", "Music/Artist/Album/song.mp3"),
            ("Takeout/Drive/file.txt", "file.txt"),
        ]
        
        for input_path, expected_output in test_cases:
            result = normalizer.normalize_path(Path(input_path))
            
            assert not result.should_skip, f"Path should not be skipped: {input_path}"
            assert result.clean_path is not None, f"Clean path should not be None: {input_path}"
            
            expected_full_path = Path("/test/destination") / expected_output
            assert result.clean_path == expected_full_path, f"Expected {expected_full_path}, got {result.clean_path}"
    
    def test_numbered_takeout_variations(self, normalizer):
        """Test various numbered Takeout folder patterns"""
        test_cases = [
            # Hyphen patterns
            ("Takeout-1/Drive/Documents/file.pdf", "Documents/file.pdf"),
            ("Takeout-123/Drive/Photos/image.jpg", "Photos/image.jpg"),
            
            # Space patterns  
            ("Takeout 2/Drive/Videos/movie.mp4", "Videos/movie.mp4"),
            ("Takeout 456/Drive/file.txt", "file.txt"),
            
            # Underscore patterns
            ("Takeout_3/Drive/Projects/code.py", "Projects/code.py"),
            ("Takeout_789/Drive/Archive/backup.zip", "Archive/backup.zip"),
        ]
        
        for input_path, expected_output in test_cases:
            result = normalizer.normalize_path(Path(input_path))
            
            assert not result.should_skip, f"Path should not be skipped: {input_path}"
            assert result.clean_path is not None, f"Clean path should not be None: {input_path}"
            
            expected_full_path = Path("/test/destination") / expected_output
            assert result.clean_path == expected_full_path, f"Expected {expected_full_path}, got {result.clean_path}"
    
    def test_takeout_without_drive_folder(self, normalizer):
        """Test files directly in Takeout folder (no Drive subfolder)"""
        test_cases = [
            ("Takeout/random_file.txt", "random_file.txt"),
            ("Takeout-1/backup.zip", "backup.zip"),
            ("Takeout 2/export.csv", "export.csv"),
            ("Takeout_3/subfolder/file.txt", "subfolder/file.txt"),
        ]
        
        for input_path, expected_output in test_cases:
            result = normalizer.normalize_path(Path(input_path))
            
            assert not result.should_skip, f"Path should not be skipped: {input_path}"
            assert result.clean_path is not None, f"Clean path should not be None: {input_path}"
            
            expected_full_path = Path("/test/destination") / expected_output
            assert result.clean_path == expected_full_path, f"Expected {expected_full_path}, got {result.clean_path}"
    
    def test_no_takeout_structure(self, normalizer):
        """Test paths that don't contain Takeout folders"""
        test_cases = [
            ("MyFolder/file.txt", "MyFolder/file.txt"),
            ("Drive/Projects/code.py", "Drive/Projects/code.py"),
            ("Documents/report.pdf", "Documents/report.pdf"),
            ("just_a_file.txt", "just_a_file.txt"),
        ]
        
        for input_path, expected_output in test_cases:
            result = normalizer.normalize_path(Path(input_path))
            
            assert not result.should_skip, f"Path should not be skipped: {input_path}"
            assert result.clean_path is not None, f"Clean path should not be None: {input_path}"
            
            expected_full_path = Path("/test/destination") / expected_output
            assert result.clean_path == expected_full_path, f"Expected {expected_full_path}, got {result.clean_path}"
    
    def test_metadata_files_skipped(self, normalizer):
        """Test that metadata files are properly skipped"""
        metadata_paths = [
            "Takeout/Drive/document.json",
            "Takeout-1/Drive/Photos/image.jpg.json",
            "Takeout 2/Drive/metadata.json",
        ]
        
        for metadata_path in metadata_paths:
            result = normalizer.normalize_path(Path(metadata_path), is_metadata=True)
            
            assert result.should_skip, f"Metadata file should be skipped: {metadata_path}"
            assert result.clean_path is None, f"Clean path should be None for metadata: {metadata_path}"
            assert "metadata" in result.transformation_log.lower(), f"Log should mention metadata: {result.transformation_log}"
    
    def test_edge_cases(self, normalizer):
        """Test edge cases and potential problem scenarios"""
        # Empty drive folder - should be skipped
        result = normalizer.normalize_path(Path("Takeout/Drive"))
        assert result.should_skip, "Empty Drive folder should be skipped"
        
        # Just Takeout folder - should be skipped  
        result = normalizer.normalize_path(Path("Takeout"))
        assert result.should_skip, "Empty Takeout folder should be skipped"
        
        # Very nested structure
        deep_path = "Takeout/Drive/A/B/C/D/E/F/G/file.txt"
        result = normalizer.normalize_path(Path(deep_path))
        assert not result.should_skip, "Deep nested path should not be skipped"
        expected = Path("/test/destination") / "A/B/C/D/E/F/G/file.txt"
        assert result.clean_path == expected, f"Deep path transformation failed"
    
    def test_case_insensitive_matching(self, normalizer):
        """Test that Takeout and Drive matching is case insensitive"""
        test_cases = [
            ("takeout/drive/file.txt", "file.txt"),
            ("TAKEOUT/DRIVE/file.txt", "file.txt"),
            ("Takeout/drive/file.txt", "file.txt"),
            ("takeout/Drive/file.txt", "file.txt"),
        ]
        
        for input_path, expected_output in test_cases:
            result = normalizer.normalize_path(Path(input_path))
            
            assert not result.should_skip, f"Case insensitive path should work: {input_path}"
            expected_full_path = Path("/test/destination") / expected_output
            assert result.clean_path == expected_full_path, f"Case insensitive matching failed for {input_path}"
    
    def test_special_characters_in_paths(self, normalizer):
        """Test paths with special characters"""
        test_cases = [
            ("Takeout/Drive/Folder (1)/file.txt", "Folder (1)/file.txt"),
            ("Takeout/Drive/My Docs & Files/report.pdf", "My Docs & Files/report.pdf"),
            ("Takeout/Drive/São Paulo/vacation.jpg", "São Paulo/vacation.jpg"),
            ("Takeout/Drive/东京/photos.png", "东京/photos.png"),
        ]
        
        for input_path, expected_output in test_cases:
            result = normalizer.normalize_path(Path(input_path))
            
            assert not result.should_skip, f"Special character path should work: {input_path}"
            expected_full_path = Path("/test/destination") / expected_output
            assert result.clean_path == expected_full_path, f"Special character handling failed for {input_path}"
    
    def test_transformation_logging(self, normalizer):
        """Test that transformation logs provide useful information"""
        # Standard transformation
        result = normalizer.normalize_path(Path("Takeout/Drive/Documents/file.pdf"))
        assert "Takeout" in result.transformation_log
        assert "Drive" in result.transformation_log
        assert "Removed" in result.transformation_log
        
        # No transformation needed
        result = normalizer.normalize_path(Path("Documents/file.pdf"))
        assert "No transformation needed" in result.transformation_log
        
        # Metadata skip
        result = normalizer.normalize_path(Path("Takeout/Drive/metadata.json"), is_metadata=True)
        assert "metadata" in result.transformation_log.lower()
    
    def test_multiple_takeout_patterns_in_path(self, normalizer):
        """Test paths that might have multiple Takeout-like patterns"""
        # This could happen if someone names a folder "Takeout"
        test_cases = [
            ("Takeout/Drive/My Takeout Folder/file.txt", "My Takeout Folder/file.txt"),
            ("Takeout-1/Drive/Takeout Archive/data.zip", "Takeout Archive/data.zip"),
        ]
        
        for input_path, expected_output in test_cases:
            result = normalizer.normalize_path(Path(input_path))
            
            assert not result.should_skip, f"Multiple Takeout patterns should work: {input_path}"
            expected_full_path = Path("/test/destination") / expected_output
            assert result.clean_path == expected_full_path, f"Multiple Takeout pattern handling failed for {input_path}"
    
    def test_test_transformations_method(self, normalizer):
        """Test the test_transformations helper method"""
        test_paths = [
            "Takeout/Drive/Documents/file.pdf",
            "Takeout-1/Drive/Photos/image.jpg",
            "Regular/Folder/file.txt"
        ]
        
        results = normalizer.test_transformations(test_paths)
        
        assert len(results) == 3, "Should return results for all test paths"
        assert all(isinstance(r, PathTransformation) for r in results), "All results should be PathTransformation objects"
        
        # Check first result
        first_result = results[0]
        assert first_result.original_path == Path("Takeout/Drive/Documents/file.pdf")
        assert first_result.clean_path == Path("/test/destination/Documents/file.pdf")
        assert not first_result.should_skip
    
    def test_add_skip_pattern(self, normalizer):
        """Test adding custom skip patterns"""
        # Add a custom skip pattern
        normalizer.add_skip_pattern(r'.*\.tmp$')
        
        # Test that .tmp files are now handled by the skip pattern check
        # Note: The current implementation doesn't use skip_file_patterns in normalize_path,
        # but this tests the method exists and works
        assert len(normalizer.skip_file_patterns) > 1, "Should have added a new skip pattern"


class TestPathTransformation:
    """Test the PathTransformation dataclass"""
    
    def test_path_transformation_creation(self):
        """Test creating PathTransformation objects"""
        original = Path("test/path")
        clean = Path("/dest/clean/path")
        log = "Test transformation"
        
        transformation = PathTransformation(
            original_path=original,
            clean_path=clean,
            transformation_log=log,
            should_skip=False
        )
        
        assert transformation.original_path == original
        assert transformation.clean_path == clean
        assert transformation.transformation_log == log
        assert not transformation.should_skip
    
    def test_skip_transformation(self):
        """Test PathTransformation for skipped files"""
        transformation = PathTransformation(
            original_path=Path("metadata.json"),
            clean_path=None,
            transformation_log="Skipped metadata file",
            should_skip=True
        )
        
        assert transformation.should_skip
        assert transformation.clean_path is None


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])