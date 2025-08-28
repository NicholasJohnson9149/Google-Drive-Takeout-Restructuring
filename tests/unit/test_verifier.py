"""
Unit tests for the DriveVerifier module
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.core.verifier import DriveVerifier


class TestDriveVerifier:
    """Test cases for DriveVerifier class"""
    
    def test_verifier_creation(self):
        """Test basic verifier creation"""
        verifier = DriveVerifier()
        assert verifier is not None
        assert verifier.logger is not None
        assert verifier.verification_results == {}
    
    def test_verifier_with_logger(self):
        """Test verifier creation with custom logger"""
        mock_logger = Mock()
        verifier = DriveVerifier(logger=mock_logger)
        assert verifier.logger == mock_logger
    
    def test_get_file_inventory_empty_dir(self, tmp_path):
        """Test getting inventory of empty directory"""
        verifier = DriveVerifier()
        inventory = verifier._get_file_inventory(tmp_path)
        assert inventory == {}
    
    def test_get_file_inventory_with_files(self, tmp_path):
        """Test getting inventory of directory with files"""
        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file2.txt").write_text("content2")
        
        verifier = DriveVerifier()
        inventory = verifier._get_file_inventory(tmp_path)
        
        assert len(inventory) == 2
        assert "file1.txt" in inventory
        assert "subdir/file2.txt" in inventory
        assert inventory["file1.txt"]["size"] == 8
        assert inventory["subdir/file2.txt"]["size"] == 8
    
    def test_get_file_inventory_nonexistent(self):
        """Test getting inventory of non-existent directory"""
        verifier = DriveVerifier()
        inventory = verifier._get_file_inventory(Path("/nonexistent/path"))
        assert inventory == {}
    
    def test_should_verify_hash(self):
        """Test hash verification decision logic"""
        verifier = DriveVerifier()
        
        # Should verify regular files
        assert verifier._should_verify_hash("document.txt") is True
        assert verifier._should_verify_hash("image.jpg") is True
        
        # Should skip video files
        assert verifier._should_verify_hash("video.mp4") is False
        assert verifier._should_verify_hash("movie.mov") is False
        assert verifier._should_verify_hash("video.avi") is False
        
        # Should skip archive files
        assert verifier._should_verify_hash("archive.zip") is False
        assert verifier._should_verify_hash("disk.iso") is False
    
    def test_calculate_file_hash(self, tmp_path):
        """Test file hash calculation"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        verifier = DriveVerifier()
        hash_result = verifier._calculate_file_hash(test_file)
        
        # Known SHA-256 hash for "Hello World"
        expected_hash = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
        assert hash_result == expected_hash
    
    def test_calculate_file_hash_nonexistent(self):
        """Test hash calculation for non-existent file"""
        verifier = DriveVerifier()
        hash_result = verifier._calculate_file_hash(Path("/nonexistent/file"))
        assert hash_result == ""
    
    def test_verify_file_hash_matching(self, tmp_path):
        """Test file hash verification with matching files"""
        # Create two identical files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = "Test content"
        file1.write_text(content)
        file2.write_text(content)
        
        verifier = DriveVerifier()
        assert verifier._verify_file_hash(file1, file2) is True
    
    def test_verify_file_hash_different(self, tmp_path):
        """Test file hash verification with different files"""
        # Create two different files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Content 1")
        file2.write_text("Content 2")
        
        verifier = DriveVerifier()
        assert verifier._verify_file_hash(file1, file2) is False
    
    @patch('app.core.verifier.DriveVerifier._calculate_file_hash')
    @patch('app.core.verifier.DriveVerifier._get_file_inventory')
    def test_verify_reconstruction_success(self, mock_inventory, mock_hash, tmp_path):
        """Test successful reconstruction verification"""
        # Create actual test files
        file1 = tmp_path / "file1.txt"
        file1.write_text("test content 1")
        
        dir_path = tmp_path / "dir"
        dir_path.mkdir()
        file2 = dir_path / "file2.txt"
        file2.write_text("test content 2")
        
        # Mock identical inventories
        common_inventory = {
            "file1.txt": {"size": file1.stat().st_size, "mtime": 123456, "path": file1},
            "dir/file2.txt": {"size": file2.stat().st_size, "mtime": 123457, "path": file2}
        }
        mock_inventory.return_value = common_inventory
        
        # Mock hash function to return consistent hashes
        mock_hash.return_value = "mock_hash_value"
        
        verifier = DriveVerifier()
        results = verifier.verify_reconstruction(tmp_path, tmp_path)
        
        assert results['verified'] is True
        assert results['file_count_match'] is True
        assert len(results['missing_files']) == 0
        assert len(results['extra_files']) == 0
        assert len(results['size_mismatches']) == 0
    
    @patch('app.core.verifier.DriveVerifier._get_file_inventory')
    def test_verify_reconstruction_missing_files(self, mock_inventory, tmp_path):
        """Test verification with missing files"""
        # First call returns original inventory
        original_inventory = {
            "file1.txt": {"size": 100, "mtime": 123456, "path": tmp_path / "file1.txt"},
            "file2.txt": {"size": 200, "mtime": 123457, "path": tmp_path / "file2.txt"}
        }
        # Second call returns reconstructed inventory (missing file2)
        reconstructed_inventory = {
            "file1.txt": {"size": 100, "mtime": 123456, "path": tmp_path / "file1.txt"}
        }
        mock_inventory.side_effect = [original_inventory, reconstructed_inventory]
        
        verifier = DriveVerifier()
        results = verifier.verify_reconstruction(tmp_path, tmp_path)
        
        assert results['verified'] is False
        assert results['file_count_match'] is False
        assert "file2.txt" in results['missing_files']
        assert len(results['extra_files']) == 0
    
    @patch('app.core.verifier.DriveVerifier._get_file_inventory')
    def test_verify_reconstruction_extra_files(self, mock_inventory, tmp_path):
        """Test verification with extra files"""
        # First call returns original inventory
        original_inventory = {
            "file1.txt": {"size": 100, "mtime": 123456, "path": tmp_path / "file1.txt"}
        }
        # Second call returns reconstructed inventory (extra file2)
        reconstructed_inventory = {
            "file1.txt": {"size": 100, "mtime": 123456, "path": tmp_path / "file1.txt"},
            "file2.txt": {"size": 200, "mtime": 123457, "path": tmp_path / "file2.txt"}
        }
        mock_inventory.side_effect = [original_inventory, reconstructed_inventory]
        
        verifier = DriveVerifier()
        results = verifier.verify_reconstruction(tmp_path, tmp_path)
        
        assert results['verified'] is False
        assert results['file_count_match'] is False
        assert len(results['missing_files']) == 0
        assert "file2.txt" in results['extra_files']
    
    @patch('app.core.verifier.DriveVerifier._get_file_inventory')
    def test_verify_reconstruction_size_mismatch(self, mock_inventory, tmp_path):
        """Test verification with size mismatches"""
        # First call returns original inventory
        original_inventory = {
            "file1.txt": {"size": 100, "mtime": 123456, "path": tmp_path / "file1.txt"}
        }
        # Second call returns reconstructed inventory (different size)
        reconstructed_inventory = {
            "file1.txt": {"size": 150, "mtime": 123456, "path": tmp_path / "file1.txt"}
        }
        mock_inventory.side_effect = [original_inventory, reconstructed_inventory]
        
        verifier = DriveVerifier()
        results = verifier.verify_reconstruction(tmp_path, tmp_path)
        
        assert results['verified'] is False
        assert len(results['size_mismatches']) == 1
        assert results['size_mismatches'][0]['file'] == "file1.txt"
        assert results['size_mismatches'][0]['original_size'] == 100
        assert results['size_mismatches'][0]['reconstructed_size'] == 150
    
    def test_generate_verification_report(self):
        """Test verification report generation"""
        verifier = DriveVerifier()
        verifier.verification_results = {
            'verified': True,
            'total_original_files': 100,
            'total_reconstructed_files': 100,
            'total_size_original': 1024 * 1024 * 1024,  # 1 GB
            'total_size_reconstructed': 1024 * 1024 * 1024,
            'missing_files': [],
            'extra_files': [],
            'size_mismatches': [],
            'hash_mismatches': []
        }
        
        report = verifier.generate_verification_report()
        
        assert "PASSED" in report
        assert "Original files: 100" in report
        assert "1.00 GB" in report
    
    def test_generate_verification_report_with_issues(self, tmp_path):
        """Test verification report generation with issues"""
        verifier = DriveVerifier()
        verifier.verification_results = {
            'verified': False,
            'total_original_files': 100,
            'total_reconstructed_files': 98,
            'total_size_original': 1024 * 1024 * 1024,
            'total_size_reconstructed': 1024 * 1024 * 900,
            'missing_files': ["file1.txt", "file2.txt"],
            'extra_files': ["extra.txt"],
            'size_mismatches': [{"file": "mismatch.txt"}],
            'hash_mismatches': []
        }
        
        report_file = tmp_path / "report.txt"
        report = verifier.generate_verification_report(report_file)
        
        assert "FAILED" in report
        assert "Missing files: 2" in report
        assert "Extra files: 1" in report
        assert "Size mismatches: 1" in report
        assert "file1.txt" in report
        assert report_file.exists()
    
    def test_generate_verification_report_no_results(self):
        """Test report generation without verification results"""
        verifier = DriveVerifier()
        report = verifier.generate_verification_report()
        assert report == "No verification results available"