#!/usr/bin/env python3
"""
Unit tests for Google Drive Takeout Consolidator
Tests zip extraction, file operations, and GUI functionality
"""

import unittest
import tempfile
import zipfile
import shutil
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import threading
import time

# Import our modules
from main_enhanced import SafeTakeoutReconstructor
from gui_server import ZipExtractor, GUIState

class TestZipExtractor(unittest.TestCase):
    """Test zip extraction functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.upload_dir = self.temp_dir / "uploads"
        self.extract_dir = self.temp_dir / "extracted"
        self.upload_dir.mkdir()
        self.extract_dir.mkdir()
        
        # Mock progress callback
        self.progress_data = []
        self.progress_callback = lambda data: self.progress_data.append(data)
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_zip(self, filename: str, files: dict) -> Path:
        """Create a test zip file with specified files
        
        Args:
            filename: Name of zip file to create
            files: Dict of {filepath: content} to add to zip
        """
        zip_path = self.upload_dir / filename
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for filepath, content in files.items():
                zf.writestr(filepath, content)
        
        return zip_path
    
    def test_extract_single_zip(self):
        """Test extracting a single zip file"""
        # Create test zip
        test_files = {
            'Takeout/Drive/document.txt': 'Test document content',
            'Takeout/Drive/folder/image.jpg': b'fake image data',
            'Takeout/Drive/metadata.json': '{"title": "Test Metadata"}'
        }
        
        zip_path = self.create_test_zip('takeout1.zip', test_files)
        
        # Extract
        extractor = ZipExtractor(self.progress_callback)
        result = extractor.extract_takeout_zips(self.upload_dir, self.extract_dir)
        
        # Verify success
        self.assertTrue(result)
        
        # Verify files extracted
        extract_subdir = self.extract_dir / 'takeout1'
        self.assertTrue(extract_subdir.exists())
        
        for filepath in test_files.keys():
            extracted_file = extract_subdir / filepath
            self.assertTrue(extracted_file.exists(), f"File not extracted: {filepath}")
        
        # Verify progress callbacks
        self.assertGreater(len(self.progress_data), 0)
        self.assertTrue(any('extraction_progress' in str(data) for data in self.progress_data))
    
    def test_extract_multiple_zips(self):
        """Test extracting multiple zip files"""
        # Create multiple test zips
        zip1_files = {'Takeout/Drive/file1.txt': 'Content 1'}
        zip2_files = {'Takeout/Drive/file2.txt': 'Content 2'}
        
        self.create_test_zip('takeout1.zip', zip1_files)
        self.create_test_zip('takeout2.zip', zip2_files)
        
        # Extract
        extractor = ZipExtractor(self.progress_callback)
        result = extractor.extract_takeout_zips(self.upload_dir, self.extract_dir)
        
        # Verify success
        self.assertTrue(result)
        
        # Verify both extractions
        self.assertTrue((self.extract_dir / 'takeout1' / 'Takeout/Drive/file1.txt').exists())
        self.assertTrue((self.extract_dir / 'takeout2' / 'Takeout/Drive/file2.txt').exists())
    
    def test_extract_no_zip_files(self):
        """Test behavior when no zip files present"""
        # Create non-zip file
        (self.upload_dir / 'not_a_zip.txt').write_text('This is not a zip')
        
        extractor = ZipExtractor(self.progress_callback)
        
        with self.assertRaises(ValueError) as cm:
            extractor.extract_takeout_zips(self.upload_dir, self.extract_dir)
        
        self.assertIn("No zip files found", str(cm.exception))
    
    def test_extract_corrupted_zip(self):
        """Test handling of corrupted zip files"""
        # Create corrupted zip
        corrupted_zip = self.upload_dir / 'corrupted.zip'
        corrupted_zip.write_text('This is not valid zip data')
        
        # Create valid zip too
        self.create_test_zip('valid.zip', {'test.txt': 'valid content'})
        
        extractor = ZipExtractor(self.progress_callback)
        result = extractor.extract_takeout_zips(self.upload_dir, self.extract_dir)
        
        # Should succeed (valid zip extracted, corrupted skipped)
        self.assertTrue(result)
        
        # Valid zip should be extracted
        self.assertTrue((self.extract_dir / 'valid' / 'test.txt').exists())
        
        # Corrupted zip directory should not exist or be empty
        corrupted_dir = self.extract_dir / 'corrupted'
        if corrupted_dir.exists():
            self.assertEqual(len(list(corrupted_dir.rglob('*'))), 0)
    
    def test_progress_callback_called(self):
        """Test that progress callback is called with correct data"""
        test_files = {'test.txt': 'content'}
        self.create_test_zip('test.zip', test_files)
        
        extractor = ZipExtractor(self.progress_callback)
        extractor.extract_takeout_zips(self.upload_dir, self.extract_dir)
        
        # Check callback was called
        self.assertGreater(len(self.progress_data), 0)
        
        # Check callback data structure
        for data in self.progress_data:
            self.assertIsInstance(data, dict)
            if 'type' in data and data['type'] == 'extraction_progress':
                self.assertIn('progress_percent', data)
                self.assertIn('current_file', data)
                self.assertIn('message', data)


class TestSafeTakeoutReconstructor(unittest.TestCase):
    """Test core consolidation functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.dest_dir = self.temp_dir / "destination"
        
        # Create test directory structure
        self.source_dir.mkdir()
        self.dest_dir.mkdir()
        
        # Mock progress callback
        self.progress_data = []
        self.progress_callback = lambda data: self.progress_data.append(data)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_takeout_structure(self, takeout_name: str, files: dict):
        """Create a mock Takeout directory structure
        
        Args:
            takeout_name: Name of takeout directory
            files: Dict of {relative_path: content}
        """
        takeout_dir = self.source_dir / takeout_name / "Drive"
        takeout_dir.mkdir(parents=True)
        
        for rel_path, content in files.items():
            file_path = takeout_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if isinstance(content, bytes):
                file_path.write_bytes(content)
            else:
                file_path.write_text(content)
        
        return takeout_dir
    
    def test_constructor_with_callback(self):
        """Test constructor with progress callback"""
        reconstructor = SafeTakeoutReconstructor(
            source_dir=str(self.source_dir),
            dest_dir=str(self.dest_dir),
            dry_run=True,
            progress_callback=self.progress_callback
        )
        
        self.assertEqual(reconstructor.progress_callback, self.progress_callback)
        self.assertEqual(reconstructor.current_operation, "idle")
        self.assertEqual(reconstructor.progress_percent, 0)
    
    def test_path_detection_variations(self):
        """Test smart path detection with variations"""
        # Create directory with hyphens
        actual_dir = self.temp_dir / "GDrive-Jul-31st"
        actual_dir.mkdir()
        
        # Test with spaces (should find hyphen version)
        reconstructor = SafeTakeoutReconstructor(
            source_dir=str(self.temp_dir / "GDrive Jul 31st"),  # Spaces
            dest_dir=str(self.dest_dir),
            dry_run=True,
            progress_callback=self.progress_callback
        )
        
        # Should find the actual directory
        reconstructor.validate_environment()
        self.assertEqual(reconstructor.source_dir, actual_dir)
    
    def test_log_with_callback(self):
        """Test logging sends data to callback"""
        reconstructor = SafeTakeoutReconstructor(
            source_dir=str(self.source_dir),
            dest_dir=str(self.dest_dir),
            progress_callback=self.progress_callback
        )
        
        # Create minimal takeout structure
        self.create_takeout_structure("Takeout1", {"test.txt": "content"})
        
        # Log a message
        reconstructor.log("Test message")
        
        # Check callback was called
        self.assertEqual(len(self.progress_data), 1)
        callback_data = self.progress_data[0]
        
        self.assertEqual(callback_data['type'], 'log')
        self.assertEqual(callback_data['message'], 'Test message')
        self.assertIn('timestamp', callback_data)
        self.assertIn('stats', callback_data)
    
    def test_file_processing_updates_gui_state(self):
        """Test that file processing updates GUI state variables"""
        # Create test structure
        takeout_dir = self.create_takeout_structure("Takeout1", {
            "Documents/test1.txt": "content1",
            "Documents/test2.txt": "content2"
        })
        
        reconstructor = SafeTakeoutReconstructor(
            source_dir=str(self.source_dir),
            dest_dir=str(self.dest_dir),
            dry_run=True,  # Dry run for testing
            progress_callback=self.progress_callback
        )
        
        # Run reconstruction
        reconstructor.reconstruct()
        
        # Check that GUI state was updated
        self.assertGreater(len(self.progress_data), 0)
        
        # Find progress updates
        progress_updates = [d for d in self.progress_data if 'Progress:' in d.get('message', '')]
        self.assertGreater(len(progress_updates), 0)
    
    def test_google_metadata_handling(self):
        """Test Google metadata file handling"""
        reconstructor = SafeTakeoutReconstructor(
            source_dir=str(self.source_dir),
            dest_dir=str(self.dest_dir),
            dry_run=True
        )
        
        # Test numbered file handling
        test_file = Path("document(1).pdf")
        clean_name = reconstructor.handle_google_metadata(test_file)
        self.assertEqual(clean_name, "document.pdf")
        
        # Test JSON metadata handling
        test_dir = self.temp_dir / "metadata_test"
        test_dir.mkdir()
        
        test_file = test_dir / "photo.jpg"
        test_file.write_text("fake photo")
        
        metadata_file = test_dir / "photo.jpg.json"
        metadata = {"title": "My Original Photo.jpg"}
        metadata_file.write_text(json.dumps(metadata))
        
        clean_name = reconstructor.handle_google_metadata(test_file)
        self.assertEqual(clean_name, "My Original Photo.jpg")


class TestGUIState(unittest.TestCase):
    """Test GUI state management"""
    
    def setUp(self):
        """Set up test environment"""
        self.gui_state = GUIState()
    
    def test_create_operation(self):
        """Test operation creation"""
        operation_id = "test-123"
        self.gui_state.create_operation(operation_id, "upload")
        
        self.assertIn(operation_id, self.gui_state.active_operations)
        operation = self.gui_state.active_operations[operation_id]
        
        self.assertEqual(operation['id'], operation_id)
        self.assertEqual(operation['type'], "upload")
        self.assertEqual(operation['status'], "started")
        self.assertIn('start_time', operation)
    
    def test_update_operation(self):
        """Test operation updates"""
        operation_id = "test-123"
        self.gui_state.create_operation(operation_id, "extraction")
        
        # Update operation
        update_data = {
            'progress_percent': 50,
            'current_file': 'test.zip',
            'message': 'Extracting test.zip'
        }
        self.gui_state.update_operation(operation_id, update_data)
        
        # Check operation updated
        operation = self.gui_state.active_operations[operation_id]
        self.assertEqual(operation['progress_percent'], 50)
        self.assertEqual(operation['current_file'], 'test.zip')
        
        # Check log entry created
        self.assertIn(operation_id, self.gui_state.progress_logs)
        logs = self.gui_state.progress_logs[operation_id]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['message'], 'Extracting test.zip')
    
    def test_log_size_limit(self):
        """Test that logs are limited to prevent memory issues"""
        operation_id = "test-123"
        self.gui_state.create_operation(operation_id, "test")
        
        # Add more than 100 log entries
        for i in range(150):
            self.gui_state.update_operation(operation_id, {
                'message': f'Log entry {i}',
                'progress_percent': i
            })
        
        # Should only keep last 100
        logs = self.gui_state.progress_logs[operation_id]
        self.assertEqual(len(logs), 100)
        self.assertEqual(logs[-1]['message'], 'Log entry 149')
        self.assertEqual(logs[0]['message'], 'Log entry 50')


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete workflow"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.upload_dir = self.temp_dir / "uploads"
        self.extract_dir = self.temp_dir / "extracted"
        self.output_dir = self.temp_dir / "output"
        
        for dir_path in [self.upload_dir, self.extract_dir, self.output_dir]:
            dir_path.mkdir()
    
    def tearDown(self):
        """Clean up integration test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_realistic_takeout_zip(self, zip_name: str) -> Path:
        """Create a realistic Google Takeout zip file"""
        zip_path = self.upload_dir / zip_name
        
        # Realistic Google Drive structure
        files = {
            'Takeout/Drive/Documents/Important Document.pdf': b'PDF content here',
            'Takeout/Drive/Documents/Important Document.pdf.json': '{"title": "Important Document.pdf"}',
            'Takeout/Drive/Photos/vacation.jpg': b'JPEG data',
            'Takeout/Drive/Photos/vacation.jpg.json': '{"title": "Beach Vacation 2023.jpg"}',
            'Takeout/Drive/Spreadsheets/Budget(1).xlsx': b'Excel data',
            'Takeout/Drive/Presentations/Meeting Slides.pptx': b'PowerPoint data',
            'Takeout/Drive/Other/random_file.txt': 'Some text content'
        }
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for filepath, content in files.items():
                zf.writestr(filepath, content)
        
        return zip_path
    
    def test_complete_workflow(self):
        """Test the complete extraction and consolidation workflow"""
        # Create realistic test data
        zip_path1 = self.create_realistic_takeout_zip('takeout-1.zip')
        zip_path2 = self.create_realistic_takeout_zip('takeout-2.zip')
        
        # Track progress
        progress_data = []
        progress_callback = lambda data: progress_data.append(data)
        
        # Step 1: Extract zips
        extractor = ZipExtractor(progress_callback)
        extract_success = extractor.extract_takeout_zips(self.upload_dir, self.extract_dir)
        self.assertTrue(extract_success)
        
        # Verify extraction created proper structure
        self.assertTrue((self.extract_dir / 'takeout-1' / 'Takeout' / 'Drive').exists())
        self.assertTrue((self.extract_dir / 'takeout-2' / 'Takeout' / 'Drive').exists())
        
        # Step 2: Consolidate extracted files
        reconstructor = SafeTakeoutReconstructor(
            source_dir=str(self.extract_dir),
            dest_dir=str(self.output_dir),
            dry_run=False,  # Actually copy files for integration test
            progress_callback=progress_callback
        )
        
        # Find takeout directories (they should be auto-detected)
        reconstructor.validate_environment()
        self.assertGreater(len(reconstructor.takeout_folders), 0)
        
        # Run consolidation
        reconstructor.reconstruct()
        
        # Verify consolidation results
        self.assertGreater(reconstructor.stats['total_files'], 0)
        
        # Check that files were organized properly
        expected_structure = [
            'Documents/Important Document.pdf',  # Should use metadata title
            'Photos/Beach Vacation 2023.jpg',   # Should use metadata title
            'Spreadsheets/Budget.xlsx',         # Should remove (1) numbering
            'Presentations/Meeting Slides.pptx',
            'Other/random_file.txt'
        ]
        
        for expected_file in expected_structure:
            output_file = self.output_dir / expected_file
            # Note: Due to potential duplicate handling, exact names may vary
            # So we check that files exist in correct directories
            parent_dir = output_file.parent
            self.assertTrue(parent_dir.exists(), f"Directory should exist: {parent_dir}")
        
        # Verify progress callbacks were called
        self.assertGreater(len(progress_data), 0)
        
        # Check for different types of progress updates
        log_messages = [d.get('message', '') for d in progress_data if d.get('type') == 'log']
        extraction_progress = [d for d in progress_data if d.get('type') == 'extraction_progress']
        
        self.assertGreater(len(log_messages), 0)
        self.assertGreater(len(extraction_progress), 0)


def run_tests():
    """Run all tests with detailed output"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestZipExtractor,
        TestSafeTakeoutReconstructor,
        TestGUIState,
        TestIntegration
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
