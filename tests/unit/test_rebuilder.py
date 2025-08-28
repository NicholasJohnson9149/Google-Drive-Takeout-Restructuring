"""
Unit tests for the SafeTakeoutReconstructor module
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from app.core.rebuilder import SafeTakeoutReconstructor


class TestSafeTakeoutReconstructor:
    """Test cases for SafeTakeoutReconstructor class"""
    
    def test_reconstructor_creation(self, sample_takeout_structure, output_directory):
        """Test basic reconstructor creation"""
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(sample_takeout_structure),
            export_path=str(output_directory),
            dry_run=True
        )
        
        assert reconstructor.source_dir == sample_takeout_structure
        assert reconstructor.dest_dir == output_directory
        assert reconstructor.dry_run is True
        assert reconstructor.gui_mode is False
    
    def test_reconstructor_with_callback(self, sample_takeout_structure, output_directory):
        """Test reconstructor with progress callback"""
        callback = Mock()
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(sample_takeout_structure),
            export_path=str(output_directory),
            progress_callback=callback,
            gui_mode=True
        )
        
        assert reconstructor.progress_callback == callback
        assert reconstructor.gui_mode is True
    
    def test_determine_destination_path(self, reconstructor):
        """Test destination path determination"""
        # Test normal file
        source_file = reconstructor.source_dir / "Takeout" / "Drive" / "document1.txt"
        dest_path = reconstructor._determine_destination_path(source_file)
        
        expected = reconstructor.dest_dir / "document1.txt"
        assert dest_path == expected
    
    def test_determine_destination_path_with_subfolder(self, reconstructor):
        """Test destination path with subfolder"""
        source_file = reconstructor.source_dir / "Takeout" / "Drive" / "SubFolder" / "subdoc.txt"
        dest_path = reconstructor._determine_destination_path(source_file)
        
        expected = reconstructor.dest_dir / "SubFolder" / "subdoc.txt"
        assert dest_path == expected
    
    def test_determine_destination_path_metadata_file(self, reconstructor):
        """Test that metadata files return None"""
        # Create a mock JSON metadata file
        metadata_file = reconstructor.source_dir / "Takeout" / "Drive" / "document1.txt.json"
        
        with patch.object(reconstructor, '_is_google_metadata', return_value=True):
            dest_path = reconstructor._determine_destination_path(metadata_file)
            assert dest_path is None
    
    def test_is_google_metadata(self, reconstructor, temp_dir):
        """Test Google metadata detection"""
        # Create a metadata file
        metadata_file = temp_dir / "test.json"
        metadata_content = '{"title": "test.txt", "createdTime": "2023-01-01T00:00:00Z"}'
        metadata_file.write_text(metadata_content)
        
        assert reconstructor._is_google_metadata(metadata_file) is True
        
        # Test non-metadata JSON file
        regular_file = temp_dir / "regular.json"
        regular_file.write_text('{"data": "not metadata"}')
        
        assert reconstructor._is_google_metadata(regular_file) is False
        
        # Test non-JSON file
        text_file = temp_dir / "test.txt"
        text_file.write_text("Regular text file")
        
        assert reconstructor._is_google_metadata(text_file) is False
    
    def test_is_duplicate_no_destination(self, reconstructor, sample_takeout_structure):
        """Test duplicate detection when destination doesn't exist"""
        source_file = sample_takeout_structure / "Takeout" / "Drive" / "document1.txt"
        dest_file = reconstructor.dest_dir / "document1.txt"
        
        assert reconstructor._is_duplicate(source_file, dest_file) is False
    
    def test_is_duplicate_different_sizes(self, reconstructor, temp_dir):
        """Test duplicate detection with different file sizes"""
        source_file = temp_dir / "source.txt"
        dest_file = temp_dir / "dest.txt"
        
        source_file.write_text("Short content")
        dest_file.write_text("Much longer content that is different")
        
        assert reconstructor._is_duplicate(source_file, dest_file) is False
    
    def test_is_duplicate_same_content(self, reconstructor, temp_dir):
        """Test duplicate detection with same content"""
        source_file = temp_dir / "source.txt"
        dest_file = temp_dir / "dest.txt"
        
        content = "Same content in both files"
        source_file.write_text(content)
        dest_file.write_text(content)
        
        assert reconstructor._is_duplicate(source_file, dest_file) is True
    
    def test_safe_copy_file_nonexistent_source(self, reconstructor, temp_dir):
        """Test copying non-existent source file"""
        source_file = temp_dir / "nonexistent.txt"
        dest_file = temp_dir / "destination.txt"
        
        result = reconstructor._safe_copy_file(source_file, dest_file)
        assert result is False
    
    def test_safe_copy_file_small_file(self, reconstructor, temp_dir):
        """Test copying small file"""
        source_file = temp_dir / "source.txt"
        dest_file = temp_dir / "dest.txt"
        
        content = "Test content for copying"
        source_file.write_text(content)
        
        result = reconstructor._safe_copy_file(source_file, dest_file)
        assert result is True
        assert dest_file.exists()
        assert dest_file.read_text() == content
    
    @pytest.mark.slow
    def test_safe_copy_file_large_file(self, reconstructor, temp_dir, large_file_content):
        """Test copying large file (uses chunked copy)"""
        source_file = temp_dir / "large_source.bin"
        dest_file = temp_dir / "large_dest.bin"
        
        source_file.write_bytes(large_file_content)
        
        result = reconstructor._safe_copy_file(source_file, dest_file)
        assert result is True
        assert dest_file.exists()
        assert dest_file.stat().st_size == len(large_file_content)
    
    def test_chunked_copy(self, reconstructor, temp_dir):
        """Test chunked copy functionality"""
        source_file = temp_dir / "source.bin"
        dest_file = temp_dir / "dest.bin"
        
        # Create test data
        test_data = b"chunk_test_data" * 1000  # ~15KB
        source_file.write_bytes(test_data)
        
        result = reconstructor._chunked_copy(source_file, dest_file, chunk_size=1024)
        assert result is True
        assert dest_file.exists()
        assert dest_file.read_bytes() == test_data
    
    def test_chunked_copy_failure(self, reconstructor, temp_dir):
        """Test chunked copy with non-existent parent directory"""
        source_file = temp_dir / "source.bin"
        # Create a destination with non-existent parent directories
        dest_file = temp_dir / "non_existent" / "deep" / "path" / "dest.bin"
        
        source_file.write_bytes(b"test data")
        
        # This should fail because parent directories don't exist
        result = reconstructor._chunked_copy(source_file, dest_file)
        assert result is False  # Should fail gracefully
        assert not dest_file.exists()
    
    def test_cleanup_resources(self, reconstructor):
        """Test resource cleanup"""
        # Add some mock resources
        reconstructor.temp_files = ["/tmp/test_file"]
        reconstructor.open_file_handles = [Mock()]
        
        # Should not raise any exceptions
        reconstructor.cleanup_resources()
        
        assert len(reconstructor.temp_files) == 0
        assert len(reconstructor.open_file_handles) == 0
    
    def test_cancel_operation(self, reconstructor):
        """Test operation cancellation"""
        reconstructor.cancel()
        
        # Should have cleaned up resources
        assert len(reconstructor.temp_files) == 0
        assert len(reconstructor.open_file_handles) == 0
    
    def test_rebuild_drive_structure_dry_run(self, reconstructor):
        """Test dry run mode"""
        # This should not raise any exceptions and not create files
        reconstructor.rebuild_drive_structure()
        
        # In dry run mode, no files should be created in destination
        created_files = list(reconstructor.dest_dir.rglob('*'))
        # Only log directory and files should exist
        assert all('log' in str(f) for f in created_files if f.is_file())
    
    def test_rebuild_drive_structure_invalid_source(self, output_directory):
        """Test with invalid source directory"""
        reconstructor = SafeTakeoutReconstructor(
            takeout_path="/nonexistent/path",
            export_path=str(output_directory),
            dry_run=True
        )
        
        with pytest.raises(ValueError, match="Source directory does not exist"):
            reconstructor.rebuild_drive_structure()
    
    @pytest.mark.integration
    def test_rebuild_drive_structure_real_execution(self, sample_takeout_structure, output_directory):
        """Test actual file reconstruction (integration test)"""
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(sample_takeout_structure),
            export_path=str(output_directory),
            dry_run=False  # Real execution
        )
        
        reconstructor.rebuild_drive_structure()
        
        # Verify files were copied
        expected_files = [
            output_directory / "document1.txt",
            output_directory / "document2.txt",
            output_directory / "SubFolder" / "subdoc.txt"
        ]
        
        for expected_file in expected_files:
            assert expected_file.exists()
            assert expected_file.is_file()
    
    def test_generate_manifest(self, reconstructor):
        """Test manifest generation"""
        reconstructor._generate_manifest()
        
        # In dry run mode, manifest file should not be created
        assert not reconstructor.manifest_file.exists()
        
        # Test with real execution
        reconstructor.dry_run = False
        reconstructor._generate_manifest()
        
        assert reconstructor.manifest_file.exists()
        
        # Verify manifest content
        import json
        with open(reconstructor.manifest_file) as f:
            manifest = json.load(f)
        
        assert 'reconstruction_date' in manifest
        assert 'source_directory' in manifest
        assert 'destination_directory' in manifest
        assert 'statistics' in manifest
        assert manifest['dry_run'] is False
    
    def test_statistics_tracking(self, reconstructor):
        """Test that statistics are properly tracked"""
        initial_stats = reconstructor.stats.copy()
        
        # Stats should start with zero values
        assert initial_stats['total_files'] == 0
        assert initial_stats['copied_files'] == 0
        assert initial_stats['skipped_duplicates'] == 0
        assert initial_stats['errors'] == 0
    
    def test_progress_callback_integration(self, sample_takeout_structure, output_directory):
        """Test integration with progress callback"""
        callback = Mock()
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(sample_takeout_structure),
            export_path=str(output_directory),
            progress_callback=callback,
            gui_mode=True,
            dry_run=True
        )
        
        reconstructor.rebuild_drive_structure()
        
        # Verify callback was called with various types of updates
        assert callback.called
        
        # Check for different types of callback calls
        call_types = {call[0][0]['type'] for call in callback.call_args_list if call[0]}
        expected_types = {'log', 'stats', 'status'}
        
        # At least some of these should be present
        assert len(call_types.intersection(expected_types)) > 0
