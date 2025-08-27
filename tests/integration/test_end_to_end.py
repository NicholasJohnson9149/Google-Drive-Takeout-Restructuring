"""
End-to-end integration tests for the Google Drive Takeout Consolidator
"""
from __future__ import annotations

import pytest
import zipfile
from pathlib import Path
from unittest.mock import Mock

from app.core.extractor import TakeoutExtractor
from app.core.rebuilder import SafeTakeoutReconstructor
from app.core.verifier import DriveVerifier


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete workflow from ZIP extraction to verification"""
    
    def test_complete_workflow_single_zip(self, temp_dir):
        """Test complete workflow with a single ZIP file"""
        # Setup: Create a realistic Takeout ZIP structure
        zip_file = temp_dir / "takeout-001.zip"
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add Drive files
            zipf.writestr("Takeout/Drive/My Documents/document1.pdf", b"PDF content 1")
            zipf.writestr("Takeout/Drive/My Documents/document2.txt", "Text content 2")
            zipf.writestr("Takeout/Drive/Photos/photo1.jpg", b"JPEG data")
            zipf.writestr("Takeout/Drive/Spreadsheets/data.xlsx", b"Excel data")
            
            # Add metadata files (should be ignored)
            zipf.writestr("Takeout/Drive/My Documents/document1.pdf.json", 
                         '{"title": "document1.pdf", "createdTime": "2023-01-01"}')
        
        zip_dir = temp_dir / "zips"
        zip_dir.mkdir()
        zip_file.rename(zip_dir / zip_file.name)
        
        # Step 1: Extract ZIP files
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(zip_dir)
        assert len(zip_files) == 1
        
        extracted_dir = extractor.extract_zip_files(zip_files)
        assert extracted_dir.exists()
        
        # Step 2: Rebuild Drive structure
        output_dir = temp_dir / "rebuilt_drive"
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(extracted_dir),
            export_path=str(output_dir),
            dry_run=False,
            gui_mode=True
        )
        
        reconstructor.rebuild_drive_structure()
        
        # Step 3: Verify results
        expected_files = [
            output_dir / "My Documents" / "document1.pdf",
            output_dir / "My Documents" / "document2.txt",
            output_dir / "Photos" / "photo1.jpg",
            output_dir / "Spreadsheets" / "data.xlsx"
        ]
        
        for expected_file in expected_files:
            assert expected_file.exists(), f"Missing file: {expected_file}"
            assert expected_file.is_file()
        
        # Verify metadata files were not copied
        metadata_files = list(output_dir.rglob("*.json"))
        assert len(metadata_files) == 0, "Metadata files should not be copied"
        
        # Step 4: Run verification
        verifier = DriveVerifier()
        verification_result = verifier.verify_reconstruction(extracted_dir, output_dir)
        
        # Note: Verification might not be perfect due to metadata filtering
        assert verification_result['total_reconstructed_files'] > 0
        assert verification_result['verification_errors'] == []
        
        # Cleanup
        extractor.cleanup_temp_dirs()
    
    def test_complete_workflow_multiple_zips(self, temp_dir):
        """Test workflow with multiple ZIP files (realistic scenario)"""
        zip_dir = temp_dir / "zips"
        zip_dir.mkdir()
        
        # Create multiple ZIP files simulating large Takeout export
        zip_files_data = [
            ("takeout-001.zip", {
                "Takeout/Drive/Documents/work/report1.docx": b"Report 1 content",
                "Takeout/Drive/Documents/work/report2.docx": b"Report 2 content",
                "Takeout/Drive/Documents/personal/notes.txt": "Personal notes",
            }),
            ("takeout-002.zip", {
                "Takeout/Drive/Photos/2023/vacation/IMG_001.jpg": b"JPEG data 1",
                "Takeout/Drive/Photos/2023/vacation/IMG_002.jpg": b"JPEG data 2",
                "Takeout/Drive/Photos/2023/family/family_pic.jpg": b"Family photo",
            }),
            ("takeout-003.zip", {
                "Takeout/Drive/Spreadsheets/budget.xlsx": b"Budget data",
                "Takeout/Drive/Presentations/project.pptx": b"Presentation data",
                "Takeout/Drive/Videos/demo.mp4": b"Video data",
            })
        ]
        
        for zip_name, files in zip_files_data:
            zip_path = zip_dir / zip_name
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path, content in files.items():
                    if isinstance(content, str):
                        zipf.writestr(file_path, content.encode('utf-8'))
                    else:
                        zipf.writestr(file_path, content)
        
        # Track progress with mock callback
        progress_callback = Mock()
        
        # Step 1: Extract all ZIP files
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(zip_dir)
        assert len(zip_files) == 3
        
        extracted_dir = extractor.extract_zip_files(zip_files)
        
        # Step 2: Rebuild Drive structure
        output_dir = temp_dir / "rebuilt_drive"
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(extracted_dir),
            export_path=str(output_dir),
            dry_run=False,
            progress_callback=progress_callback,
            gui_mode=True
        )
        
        reconstructor.rebuild_drive_structure()
        
        # Step 3: Verify structure
        expected_structure = {
            "Documents/work/report1.docx",
            "Documents/work/report2.docx", 
            "Documents/personal/notes.txt",
            "Photos/2023/vacation/IMG_001.jpg",
            "Photos/2023/vacation/IMG_002.jpg",
            "Photos/2023/family/family_pic.jpg",
            "Spreadsheets/budget.xlsx",
            "Presentations/project.pptx",
            "Videos/demo.mp4"
        }
        
        reconstructed_files = {
            str(f.relative_to(output_dir)) 
            for f in output_dir.rglob('*') 
            if f.is_file()
        }
        
        # Remove log files from comparison
        reconstructed_files = {f for f in reconstructed_files if 'takeout_logs' not in f}
        
        assert expected_structure.issubset(reconstructed_files), \
            f"Missing files: {expected_structure - reconstructed_files}"
        
        # Verify progress callback was used
        assert progress_callback.called
        
        # Check statistics
        stats = reconstructor.stats
        assert stats['total_files'] > 0
        assert stats['copied_files'] > 0
        assert stats['errors'] == 0
        
        # Cleanup
        extractor.cleanup_temp_dirs()
    
    def test_workflow_with_conflicts(self, temp_dir):
        """Test workflow with file conflicts (duplicate names)"""
        zip_dir = temp_dir / "zips"
        zip_dir.mkdir()
        
        # Create ZIP files with conflicting file names
        zip1 = zip_dir / "takeout-part1.zip"
        with zipfile.ZipFile(zip1, 'w') as zipf:
            zipf.writestr("Takeout/Drive/shared_file.txt", "Content from ZIP 1")
            zipf.writestr("Takeout/Drive/Documents/report.pdf", b"Report from ZIP 1")
        
        zip2 = zip_dir / "takeout-part2.zip"
        with zipfile.ZipFile(zip2, 'w') as zipf:
            zipf.writestr("Takeout/Drive/shared_file.txt", "Different content from ZIP 2")
            zipf.writestr("Takeout/Drive/Documents/report.pdf", b"Different report from ZIP 2")
        
        # Extract and rebuild
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(zip_dir)
        extracted_dir = extractor.extract_zip_files(zip_files)
        
        output_dir = temp_dir / "rebuilt_drive"
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(extracted_dir),
            export_path=str(output_dir),
            dry_run=False
        )
        
        reconstructor.rebuild_drive_structure()
        
        # Verify that conflicts were handled
        # (The exact behavior depends on the conflict resolution strategy)
        shared_files = list(output_dir.glob("shared_file*"))
        report_files = list(output_dir.rglob("report*"))
        
        # Should have at least one version of each file
        assert len(shared_files) >= 1
        assert len(report_files) >= 1
        
        # Check statistics for duplicates
        stats = reconstructor.stats
        assert stats['total_files'] > 0
        
        # Cleanup
        extractor.cleanup_temp_dirs()
    
    @pytest.mark.slow
    def test_large_dataset_workflow(self, temp_dir):
        """Test workflow with a larger dataset (performance test)"""
        zip_dir = temp_dir / "zips"
        zip_dir.mkdir()
        
        # Create a larger ZIP with many files
        large_zip = zip_dir / "large_takeout.zip"
        with zipfile.ZipFile(large_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add many small files
            for i in range(100):
                folder = f"Folder_{i // 10}"
                zipf.writestr(f"Takeout/Drive/{folder}/file_{i}.txt", f"Content {i}")
            
            # Add some larger files
            large_content = "Large file content " * 1000
            for i in range(5):
                zipf.writestr(f"Takeout/Drive/Large/large_file_{i}.txt", large_content)
        
        # Track performance
        import time
        start_time = time.time()
        
        # Extract
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(zip_dir)
        extracted_dir = extractor.extract_zip_files(zip_files)
        
        extraction_time = time.time() - start_time
        
        # Rebuild
        rebuild_start = time.time()
        output_dir = temp_dir / "rebuilt_drive"
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(extracted_dir),
            export_path=str(output_dir),
            dry_run=False
        )
        
        reconstructor.rebuild_drive_structure()
        
        rebuild_time = time.time() - rebuild_start
        total_time = time.time() - start_time
        
        # Verify results
        reconstructed_files = list(output_dir.rglob('*.txt'))
        # Should have 105 files (100 small + 5 large), minus any log files
        content_files = [f for f in reconstructed_files if 'takeout_logs' not in str(f)]
        assert len(content_files) == 105
        
        # Performance assertions (these are rough estimates)
        assert extraction_time < 30.0, f"Extraction took too long: {extraction_time}s"
        assert rebuild_time < 30.0, f"Rebuild took too long: {rebuild_time}s"
        assert total_time < 60.0, f"Total workflow took too long: {total_time}s"
        
        # Verify statistics
        stats = reconstructor.stats
        assert stats['copied_files'] == 105
        assert stats['errors'] == 0
        
        print(f"Performance: Extraction={extraction_time:.2f}s, "
              f"Rebuild={rebuild_time:.2f}s, Total={total_time:.2f}s")
        
        # Cleanup
        extractor.cleanup_temp_dirs()
    
    def test_error_recovery_workflow(self, temp_dir):
        """Test workflow error handling and recovery"""
        zip_dir = temp_dir / "zips"
        zip_dir.mkdir()
        
        # Create a ZIP with some problematic content
        problem_zip = zip_dir / "problem_takeout.zip"
        with zipfile.ZipFile(problem_zip, 'w') as zipf:
            # Normal files
            zipf.writestr("Takeout/Drive/normal_file.txt", "Normal content")
            
            # File with problematic characters in name (depending on OS)
            try:
                zipf.writestr("Takeout/Drive/special<>chars.txt", "Special chars content")
            except:
                # Skip if the OS doesn't support these characters
                pass
            
            # Very long filename (might cause issues on some filesystems)
            long_name = "very_long_filename_" + "x" * 200 + ".txt"
            try:
                zipf.writestr(f"Takeout/Drive/{long_name}", "Long name content")
            except:
                # Skip if the filename is too long
                pass
        
        # Process with error tracking
        progress_callback = Mock()
        
        extractor = TakeoutExtractor()
        zip_files = extractor.find_takeout_zips(zip_dir)
        extracted_dir = extractor.extract_zip_files(zip_files)
        
        output_dir = temp_dir / "rebuilt_drive"
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=str(extracted_dir),
            export_path=str(output_dir),
            dry_run=False,
            progress_callback=progress_callback
        )
        
        # Should complete without raising exceptions
        reconstructor.rebuild_drive_structure()
        
        # At least the normal file should be processed
        normal_file = output_dir / "normal_file.txt"
        assert normal_file.exists()
        
        # Check that any errors were tracked
        stats = reconstructor.stats
        # We should have at least processed the normal file
        assert stats['copied_files'] >= 1
        
        # Cleanup
        extractor.cleanup_temp_dirs()
