"""
Unit tests for the TakeoutExtractor module
"""
from __future__ import annotations

import pytest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from app.core.extractor import TakeoutExtractor


class TestTakeoutExtractor:
    """Test cases for TakeoutExtractor class"""
    
    def test_extractor_creation(self):
        """Test basic extractor creation"""
        extractor = TakeoutExtractor()
        assert isinstance(extractor.logger, type(extractor.logger))
        assert len(extractor.temp_dirs) == 0
    
    def test_extractor_with_logger(self, test_logger):
        """Test extractor creation with custom logger"""
        extractor = TakeoutExtractor(test_logger)
        assert extractor.logger == test_logger
    
    def test_find_takeout_zips_empty_directory(self, temp_dir):
        """Test finding ZIP files in empty directory"""
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(temp_dir)
        assert len(zip_files) == 0
    
    def test_find_takeout_zips_with_valid_zips(self, sample_zip_directory):
        """Test finding valid ZIP files"""
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(sample_zip_directory)
        
        assert len(zip_files) >= 1
        for zip_file in zip_files:
            assert zip_file.suffix == '.zip'
            assert zip_file.exists()
    
    def test_find_takeout_zips_excludes_system_files(self, temp_dir):
        """Test that system files are excluded"""
        # Create system files that should be ignored
        (temp_dir / "._system_file.zip").write_text("fake zip")
        (temp_dir / ".hidden_file.zip").write_text("fake zip")
        (temp_dir / "thumbs.db").write_text("fake zip")
        (temp_dir / "temp_file.tmp").write_text("fake zip")
        
        # Create a valid ZIP file
        valid_zip = temp_dir / "valid_takeout.zip"
        with zipfile.ZipFile(valid_zip, 'w') as zipf:
            zipf.writestr("test.txt", "test content")
        
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(temp_dir)
        
        assert len(zip_files) == 1
        assert zip_files[0].name == "valid_takeout.zip"
    
    def test_find_takeout_zips_invalid_directory(self):
        """Test finding ZIP files in non-existent directory"""
        extractor = TakeoutExtractor()
        non_existent = Path("/non/existent/directory")
        zip_files = extractor.find_takeout_zips(non_existent)
        assert len(zip_files) == 0
    
    def test_find_takeout_zips_corrupted_zip(self, temp_dir):
        """Test handling of corrupted ZIP files"""
        # Create a corrupted ZIP file
        corrupted_zip = temp_dir / "corrupted.zip"
        corrupted_zip.write_text("This is not a valid ZIP file")
        
        # Create a valid ZIP file
        valid_zip = temp_dir / "valid.zip"
        with zipfile.ZipFile(valid_zip, 'w') as zipf:
            zipf.writestr("test.txt", "test content")
        
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(temp_dir)
        
        # Should only return the valid ZIP file
        assert len(zip_files) == 1
        assert zip_files[0].name == "valid.zip"
    
    def test_extract_zip_files_to_temp(self, sample_zip_file):
        """Test extracting ZIP files to temporary directory"""
        extractor = TakeoutExtractor()
        zip_files = [sample_zip_file]
        
        extract_dir = extractor.extract_zip_files(zip_files)
        
        assert extract_dir.exists()
        assert extract_dir.is_dir()
        assert len(extractor.temp_dirs) == 1
        
        # Check that files were extracted
        extracted_files = list(extract_dir.rglob('*'))
        assert len(extracted_files) > 0
    
    def test_extract_zip_files_to_specified_directory(self, sample_zip_file, temp_dir):
        """Test extracting ZIP files to specified directory"""
        extractor = TakeoutExtractor()
        zip_files = [sample_zip_file]
        output_dir = temp_dir / "extraction_output"
        
        extract_dir = extractor.extract_zip_files(zip_files, output_dir)
        
        assert extract_dir == output_dir
        assert output_dir.exists()
        assert output_dir.is_dir()
        
        # Check that files were extracted
        extracted_files = list(output_dir.rglob('*'))
        assert len(extracted_files) > 0
    
    def test_extract_zip_files_multiple_zips(self, sample_zip_directory):
        """Test extracting multiple ZIP files"""
        extractor = TakeoutExtractor()
        zip_files = list(sample_zip_directory.glob('*.zip'))
        
        extract_dir = extractor.extract_zip_files(zip_files)
        
        assert extract_dir.exists()
        # Should have files from both ZIP files
        extracted_files = list(extract_dir.rglob('*.txt'))
        assert len(extracted_files) >= 2  # At least one file from each ZIP
    
    def test_extract_zip_files_with_progress_callback(self, sample_zip_file):
        """Test extraction with progress callback"""
        mock_callback = Mock()
        logger = Mock()
        logger.info = Mock()
        logger.status = Mock()
        logger.progress = Mock()
        logger.stats = Mock()
        logger.success = Mock()
        logger.warning = Mock()
        
        extractor = TakeoutExtractor(logger)
        zip_files = [sample_zip_file]
        
        extractor.extract_zip_files(zip_files)
        
        # Verify that progress callbacks were made
        assert logger.info.called
        assert logger.status.called
        assert logger.success.called
    
    def test_extract_zip_files_invalid_zip(self, temp_dir):
        """Test extraction with invalid ZIP file"""
        extractor = TakeoutExtractor()
        
        # Create an invalid ZIP file
        invalid_zip = temp_dir / "invalid.zip"
        invalid_zip.write_text("Not a ZIP file")
        
        zip_files = [invalid_zip]
        
        # Should handle the error gracefully
        extract_dir = extractor.extract_zip_files(zip_files)
        assert extract_dir.exists()  # Directory should still be created
    
    def test_cleanup_temp_dirs(self, sample_zip_file):
        """Test cleanup of temporary directories"""
        extractor = TakeoutExtractor()
        zip_files = [sample_zip_file]
        
        # Extract to create temp directories
        extract_dir = extractor.extract_zip_files(zip_files)
        assert extract_dir.exists()
        assert len(extractor.temp_dirs) > 0
        
        # Cleanup
        extractor.cleanup_temp_dirs()
        
        # Temp directory should be removed
        assert not extract_dir.exists()
        assert len(extractor.temp_dirs) == 0
    
    def test_destructor_cleanup(self, sample_zip_file):
        """Test that destructor cleans up temporary directories"""
        extractor = TakeoutExtractor()
        zip_files = [sample_zip_file]
        
        # Extract to create temp directories
        extract_dir = extractor.extract_zip_files(zip_files)
        temp_dir_path = extract_dir
        
        assert temp_dir_path.exists()
        
        # Delete the extractor (triggers __del__)
        del extractor
        
        # Note: __del__ is not guaranteed to be called immediately,
        # so we can't reliably test this without forcing garbage collection
        # This test mainly ensures __del__ doesn't raise exceptions
    
    @pytest.mark.slow
    def test_extract_large_zip_file(self, temp_dir, large_file_content):
        """Test extraction of large ZIP file"""
        # Create a large ZIP file
        large_zip = temp_dir / "large_takeout.zip"
        with zipfile.ZipFile(large_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("Takeout/Drive/large_file.bin", large_file_content)
            # Add more files to make it substantial
            for i in range(100):
                zipf.writestr(f"Takeout/Drive/file_{i}.txt", f"Content {i}")
        
        extractor = TakeoutExtractor()
        zip_files = [large_zip]
        
        extract_dir = extractor.extract_zip_files(zip_files)
        
        assert extract_dir.exists()
        
        # Verify large file was extracted
        large_file = extract_dir / "Takeout" / "Drive" / "large_file.bin"
        assert large_file.exists()
        assert large_file.stat().st_size >= len(large_file_content)
        
        # Clean up
        extractor.cleanup_temp_dirs()
