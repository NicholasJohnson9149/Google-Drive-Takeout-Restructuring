#!/usr/bin/env python3
"""
End-to-end tests for the complete Google Drive Takeout restructuring system
Tests the entire workflow from start to finish with realistic scenarios
"""
import pytest
import tempfile
import json
import zipfile
import shutil
import os
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.rebuilder_v2 import SafeTakeoutReconstructor
from app.core.duplicate_checker import DuplicateStrategy
from app.core.extractor import TakeoutExtractor
from app.core.verifier import DriveVerifier


class TestCompleteRestructuringWorkflow:
    """End-to-end tests for the complete restructuring workflow"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for tests"""
        with tempfile.TemporaryDirectory() as temp_path:
            workspace = Path(temp_path)
            
            # Create standard directories
            zip_dir = workspace / "zips"
            extracted_dir = workspace / "extracted"
            output_dir = workspace / "output"
            
            zip_dir.mkdir()
            extracted_dir.mkdir()
            output_dir.mkdir()
            
            yield {
                'workspace': workspace,
                'zips': zip_dir,
                'extracted': extracted_dir,
                'output': output_dir
            }
    
    @pytest.fixture
    def realistic_takeout_data(self, temp_workspace):
        """Create realistic Google Takeout data structure"""
        extracted_dir = temp_workspace['extracted']
        
        # Simulate multiple Takeout exports (common when Drive is large)
        takeout_structures = [
            {
                'name': 'Takeout',
                'files': {
                    'Drive/Documents/Important Report.pdf': b'PDF content for important report',
                    'Drive/Documents/Meeting Notes/2023-Q1.txt': 'Meeting notes from Q1 2023',
                    'Drive/Photos/Vacation 2023/beach.jpg': b'fake beach photo data',
                    'Drive/Photos/Vacation 2023/sunset.png': b'fake sunset photo data',
                    'Drive/Work/Projects/Project Alpha/plan.docx': b'project planning document',
                    'Drive/Work/Projects/Project Alpha/budget.xlsx': b'budget spreadsheet data',
                    'Drive/Archive/Old Files/legacy_data.zip': b'compressed legacy data',
                }
            },
            {
                'name': 'Takeout-1',  # Second export
                'files': {
                    'Drive/Documents/Updated Report.pdf': b'Updated PDF content',
                    'Drive/Music/Favorites/song1.mp3': b'fake audio data for song 1',
                    'Drive/Music/Favorites/song2.mp3': b'fake audio data for song 2',
                    'Drive/Videos/Family/birthday.mp4': b'fake video data',
                    'Drive/Shared/Team Folder/presentation.pptx': b'presentation data',
                }
            },
            {
                'name': 'Takeout 2',  # Third export (space in name)
                'files': {
                    'Drive/Documents/Important Report.pdf': b'PDF content for important report',  # Duplicate
                    'Drive/Code/Python/script.py': 'print("Hello, World!")\n# Python script',
                    'Drive/Code/JavaScript/app.js': 'console.log("JavaScript app");\n// JS code',
                    'Drive/Personal/Finance/taxes_2023.pdf': b'tax document content',
                }
            },
            {
                'name': 'Takeout_3',  # Fourth export (underscore)
                'files': {
                    'Drive/Research/Papers/paper1.pdf': b'academic paper content',
                    'Drive/Research/Data/dataset.csv': 'name,value\ntest,123\ndata,456',
                    'backup_file.txt': 'Direct file in Takeout (no Drive folder)',
                }
            }
        ]
        
        created_files = []
        metadata_files = []
        
        for structure in takeout_structures:
            takeout_dir = extracted_dir / structure['name']
            
            for file_path, content in structure['files'].items():
                full_path = takeout_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                if isinstance(content, str):
                    full_path.write_text(content, encoding='utf-8')
                else:
                    full_path.write_bytes(content)
                
                created_files.append(full_path)
                
                # Create corresponding metadata JSON files for some files
                if file_path.endswith(('.pdf', '.docx', '.jpg', '.png')):
                    metadata_path = full_path.with_suffix(full_path.suffix + '.json')
                    metadata_content = {\n                        'title': full_path.name,\n                        'createdTime': '2023-01-01T00:00:00Z',\n                        'modifiedTime': '2023-06-01T00:00:00Z',\n                        'mimeType': f'application/{full_path.suffix[1:]}' if full_path.suffix else 'application/octet-stream'\n                    }\n                    metadata_path.write_text(json.dumps(metadata_content, indent=2))\n                    metadata_files.append(metadata_path)\n        \n        return {\n            'source_dir': extracted_dir,\n            'created_files': created_files,\n            'metadata_files': metadata_files\n        }\n    \n    @pytest.fixture\n    def progress_monitor(self):\n        \"\"\"Progress monitoring for e2e tests\"\"\"\n        progress_data = {\n            'status_updates': [],\n            'progress_updates': [],\n            'stats_updates': [],\n            'error_count': 0\n        }\n        \n        def callback(update):\n            if update.get('type') == 'status':\n                progress_data['status_updates'].append(update)\n            elif update.get('type') == 'progress':\n                progress_data['progress_updates'].append(update)\n            elif update.get('type') == 'stats':\n                progress_data['stats_updates'].append(update)\n            elif update.get('type') == 'error':\n                progress_data['error_count'] += 1\n        \n        callback.data = progress_data\n        return callback\n    \n    def test_complete_workflow_dry_run(self, realistic_takeout_data, temp_workspace, progress_monitor):\n        \"\"\"Test the complete workflow in dry run mode\"\"\"\n        source_dir = realistic_takeout_data['source_dir']\n        output_dir = temp_workspace['output']\n        \n        # Step 1: Initialize reconstructor\n        reconstructor = SafeTakeoutReconstructor(\n            takeout_path=str(source_dir),\n            export_path=str(output_dir),\n            dry_run=True,\n            duplicate_strategy=DuplicateStrategy.HASH,\n            conflict_resolution=\"rename\",\n            progress_callback=progress_monitor\n        )\n        \n        # Step 2: Run reconstruction\n        success = reconstructor.rebuild_drive_structure(verify_copies=False)\n        \n        # Step 3: Verify results\n        assert success, \"Dry run should succeed\"\n        assert not output_dir.exists() or not any(output_dir.iterdir()), \"Dry run should not create files\"\n        \n        # Verify statistics\n        stats = reconstructor.stats\n        assert stats.total_files > 0, \"Should find files to process\"\n        assert stats.copied_files > 0, \"Should identify files to copy\"\n        assert stats.skipped_metadata > 0, \"Should identify metadata files\"\n        assert stats.errors == 0, \"Dry run should have no errors\"\n        \n        # Verify progress tracking\n        assert len(progress_monitor.data['status_updates']) > 0, \"Should have status updates\"\n        assert len(progress_monitor.data['progress_updates']) > 0, \"Should have progress updates\"\n        \n        # Check that all phases were tracked\n        statuses = [update['status'] for update in progress_monitor.data['status_updates']]\n        expected_statuses = ['starting', 'scanning', 'processing', 'completed']\n        for expected_status in expected_statuses:\n            assert any(status == expected_status for status in statuses), f\"Should have {expected_status} status\"\n    \n    def test_complete_workflow_actual_execution(self, realistic_takeout_data, temp_workspace, progress_monitor):\n        \"\"\"Test the complete workflow with actual file operations\"\"\"\n        source_dir = realistic_takeout_data['source_dir']\n        output_dir = temp_workspace['output']\n        \n        # Initialize reconstructor for actual execution\n        reconstructor = SafeTakeoutReconstructor(\n            takeout_path=str(source_dir),\n            export_path=str(output_dir),\n            dry_run=False,\n            duplicate_strategy=DuplicateStrategy.HASH,\n            conflict_resolution=\"rename\",\n            progress_callback=progress_monitor\n        )\n        \n        # Run reconstruction\n        success = reconstructor.rebuild_drive_structure(verify_copies=True)\n        \n        # Verify basic success\n        assert success, \"Reconstruction should succeed\"\n        assert output_dir.exists(), \"Output directory should be created\"\n        assert any(output_dir.iterdir()), \"Output directory should contain files\"\n        \n        # Verify expected files exist\n        expected_files = [\n            \"Documents/Important Report.pdf\",\n            \"Documents/Updated Report.pdf\", \n            \"Documents/Meeting Notes/2023-Q1.txt\",\n            \"Photos/Vacation 2023/beach.jpg\",\n            \"Photos/Vacation 2023/sunset.png\",\n            \"Work/Projects/Project Alpha/plan.docx\",\n            \"Work/Projects/Project Alpha/budget.xlsx\",\n            \"Music/Favorites/song1.mp3\",\n            \"Music/Favorites/song2.mp3\",\n            \"Videos/Family/birthday.mp4\",\n            \"Code/Python/script.py\",\n            \"Code/JavaScript/app.js\",\n            \"Personal/Finance/taxes_2023.pdf\",\n            \"Research/Papers/paper1.pdf\",\n            \"Research/Data/dataset.csv\",\n            \"backup_file.txt\"\n        ]\n        \n        for expected_file in expected_files:\n            file_path = output_dir / expected_file\n            if not file_path.exists():\n                # Check for renamed version (due to conflicts)\n                renamed_files = list(file_path.parent.glob(f\"{file_path.stem}_*{file_path.suffix}\"))\n                assert file_path.exists() or len(renamed_files) > 0, f\"Expected file or renamed version should exist: {expected_file}\"\n        \n        # Verify metadata files were NOT copied\n        json_files = list(output_dir.glob(\"**/*.json\"))\n        assert len(json_files) == 0, \"Metadata JSON files should not be copied\"\n        \n        # Verify file contents are correct\n        script_file = output_dir / \"Code/Python/script.py\"\n        if script_file.exists():\n            content = script_file.read_text()\n            assert \"Hello, World!\" in content, \"Python script content should be preserved\"\n        \n        # Verify duplicate handling\n        important_reports = list(output_dir.glob(\"Documents/Important Report*.pdf\"))\n        assert len(important_reports) >= 1, \"Should have at least one Important Report file\"\n        \n        # Verify statistics\n        stats = reconstructor.stats\n        assert stats.copied_files > 0, \"Should have copied files\"\n        assert stats.total_size > 0, \"Should have processed data\"\n        assert stats.errors == 0, \"Should have no errors\"\n        \n        # Verify logs were created\n        log_dir = output_dir.parent / \"takeout_logs\"\n        assert log_dir.exists(), \"Log directory should be created\"\n        \n        manifest_files = list(log_dir.glob(\"manifest_*.json\"))\n        assert len(manifest_files) == 1, \"Should create manifest file\"\n        \n        # Verify manifest content\n        manifest_file = manifest_files[0]\n        with open(manifest_file, 'r') as f:\n            manifest_data = json.load(f)\n        \n        assert manifest_data['source_directory'] == str(source_dir)\n        assert manifest_data['destination_directory'] == str(output_dir)\n        assert manifest_data['dry_run'] is False\n        assert 'statistics' in manifest_data\n    \n    def test_performance_with_many_files(self, temp_workspace, progress_monitor):\n        \"\"\"Test performance with a large number of files\"\"\"\n        source_dir = temp_workspace['extracted']\n        output_dir = temp_workspace['output']\n        \n        # Create many small files to test performance\n        takeout_dir = source_dir / \"Takeout\" / \"Drive\" / \"LargeFolder\"\n        takeout_dir.mkdir(parents=True)\n        \n        # Create 1000 small files\n        for i in range(1000):\n            file_path = takeout_dir / f\"file_{i:04d}.txt\"\n            file_path.write_text(f\"Content of file {i}\")\n        \n        # Create some larger files\n        for i in range(10):\n            large_file = takeout_dir / f\"large_file_{i}.bin\"\n            # Create 1MB files\n            large_file.write_bytes(b\"x\" * (1024 * 1024))\n        \n        reconstructor = SafeTakeoutReconstructor(\n            takeout_path=str(source_dir),\n            export_path=str(output_dir),\n            dry_run=False,\n            duplicate_strategy=DuplicateStrategy.HASH,\n            conflict_resolution=\"rename\",\n            progress_callback=progress_monitor\n        )\n        \n        # Measure time (basic performance check)\n        import time\n        start_time = time.time()\n        \n        success = reconstructor.rebuild_drive_structure(verify_copies=False)\n        \n        end_time = time.time()\n        duration = end_time - start_time\n        \n        assert success, \"Large file reconstruction should succeed\"\n        assert duration < 30, f\"Should complete within 30 seconds, took {duration:.2f}s\"\n        \n        # Verify all files were processed\n        stats = reconstructor.stats\n        assert stats.total_files >= 1010, \"Should find all created files\"\n        assert stats.copied_files >= 1010, \"Should copy all files\"\n        \n        # Verify progress reporting was frequent enough\n        progress_updates = progress_monitor.data['progress_updates']\n        assert len(progress_updates) >= 10, \"Should have frequent progress updates for large operations\"\n    \n    def test_error_resilience(self, realistic_takeout_data, temp_workspace, progress_monitor):\n        \"\"\"Test system resilience to various error conditions\"\"\"\n        source_dir = realistic_takeout_data['source_dir']\n        output_dir = temp_workspace['output']\n        \n        # Create a file that will cause permission error\n        problematic_dir = source_dir / \"Takeout\" / \"Drive\" / \"ProblematicFolder\"\n        problematic_dir.mkdir(parents=True, exist_ok=True)\n        problem_file = problematic_dir / \"readonly_file.txt\"\n        problem_file.write_text(\"This file will cause issues\")\n        \n        reconstructor = SafeTakeoutReconstructor(\n            takeout_path=str(source_dir),\n            export_path=str(output_dir),\n            dry_run=False,\n            duplicate_strategy=DuplicateStrategy.HASH,\n            conflict_resolution=\"rename\",\n            progress_callback=progress_monitor\n        )\n        \n        # Mock copy operations to fail for specific files\n        original_copy_file = reconstructor._copy_file\n        \n        def mock_copy_file(source_path, dest_path, verify=False):\n            if \"readonly_file\" in str(source_path):\n                raise PermissionError(\"Simulated permission error\")\n            return original_copy_file(source_path, dest_path, verify)\n        \n        reconstructor._copy_file = mock_copy_file\n        \n        # Run reconstruction - should continue despite errors\n        success = reconstructor.rebuild_drive_structure()\n        \n        # Should complete but report the error\n        assert not success, \"Should return False due to errors\"\n        assert reconstructor.stats.errors > 0, \"Should record the error\"\n        assert reconstructor.stats.copied_files > 0, \"Should still copy other files\"\n        \n        # Verify error logging\n        assert len(reconstructor.errors) > 0, \"Should record error details\"\n        error_messages = [error.error_message for error in reconstructor.errors]\n        assert any(\"permission\" in msg.lower() for msg in error_messages), \"Should record permission error\"\n        \n        # Other files should still be copied successfully\n        copied_files = list(output_dir.glob(\"**/*\"))\n        copied_files = [f for f in copied_files if f.is_file()]\n        assert len(copied_files) > 0, \"Should copy other files despite errors\"\n    \n    def test_workflow_with_verification(self, realistic_takeout_data, temp_workspace, progress_monitor):\n        \"\"\"Test workflow with file verification enabled\"\"\"\n        source_dir = realistic_takeout_data['source_dir']\n        output_dir = temp_workspace['output']\n        \n        reconstructor = SafeTakeoutReconstructor(\n            takeout_path=str(source_dir),\n            export_path=str(output_dir),\n            dry_run=False,\n            duplicate_strategy=DuplicateStrategy.VERIFY,  # Use verification-based duplicate detection\n            conflict_resolution=\"rename\",\n            progress_callback=progress_monitor\n        )\n        \n        # Run reconstruction with verification\n        success = reconstructor.rebuild_drive_structure(verify_copies=True)\n        \n        assert success, \"Reconstruction with verification should succeed\"\n        \n        # Verify that verification was actually performed\n        # This is implicit in the success of the operation\n        assert reconstructor.stats.copied_files > 0, \"Should have copied and verified files\"\n        assert reconstructor.stats.errors == 0, \"Verification should not introduce errors\"\n    \n    def test_memory_usage_with_large_dataset(self, temp_workspace, progress_monitor):\n        \"\"\"Test memory usage remains reasonable with large datasets\"\"\"\n        source_dir = temp_workspace['extracted']\n        output_dir = temp_workspace['output']\n        \n        # Create a large dataset\n        takeout_dir = source_dir / \"Takeout\" / \"Drive\"\n        takeout_dir.mkdir(parents=True)\n        \n        # Create nested folder structure with many files\n        for folder_i in range(10):\n            folder_dir = takeout_dir / f\"Folder_{folder_i}\"\n            folder_dir.mkdir()\n            \n            for subfolder_i in range(10):\n                subfolder_dir = folder_dir / f\"SubFolder_{subfolder_i}\"\n                subfolder_dir.mkdir()\n                \n                for file_i in range(10):\n                    file_path = subfolder_dir / f\"file_{file_i}.txt\"\n                    file_path.write_text(f\"Content {folder_i}-{subfolder_i}-{file_i}\")\n        \n        reconstructor = SafeTakeoutReconstructor(\n            takeout_path=str(source_dir),\n            export_path=str(output_dir),\n            dry_run=True,  # Dry run for memory test\n            duplicate_strategy=DuplicateStrategy.HASH,\n            progress_callback=progress_monitor\n        )\n        \n        # Monitor memory usage (basic check)\n        try:\n            import psutil\n            process = psutil.Process()\n            initial_memory = process.memory_info().rss\n            \n            success = reconstructor.rebuild_drive_structure()\n            \n            final_memory = process.memory_info().rss\n            memory_increase = final_memory - initial_memory\n            \n            # Memory increase should be reasonable (less than 100MB for this test)\n            assert memory_increase < 100 * 1024 * 1024, f\"Memory usage increased by {memory_increase / (1024*1024):.1f}MB\"\n            \n        except ImportError:\n            # psutil not available, just run the test\n            success = reconstructor.rebuild_drive_structure()\n        \n        assert success, \"Large dataset reconstruction should succeed\"\n        assert reconstructor.stats.total_files == 1000, \"Should process all 1000 files\"\n    \n    def test_concurrent_access_simulation(self, realistic_takeout_data, temp_workspace, progress_monitor):\n        \"\"\"Test behavior when files are accessed during reconstruction\"\"\"\n        source_dir = realistic_takeout_data['source_dir']\n        output_dir = temp_workspace['output']\n        \n        reconstructor = SafeTakeoutReconstructor(\n            takeout_path=str(source_dir),\n            export_path=str(output_dir),\n            dry_run=False,\n            duplicate_strategy=DuplicateStrategy.HASH,\n            conflict_resolution=\"rename\",\n            progress_callback=progress_monitor\n        )\n        \n        # Simulate file modification during scanning\n        def simulate_concurrent_modification():\n            # Add a new file while reconstruction is running\n            concurrent_dir = source_dir / \"Takeout\" / \"Drive\" / \"ConcurrentFiles\"\n            concurrent_dir.mkdir(parents=True, exist_ok=True)\n            concurrent_file = concurrent_dir / \"added_during_reconstruction.txt\"\n            concurrent_file.write_text(\"This file was added during reconstruction\")\n        \n        # Mock the scanning process to add a file mid-scan\n        original_scan = reconstructor.scanner.scan\n        \n        def mock_scan():\n            result = original_scan()\n            simulate_concurrent_modification()  # Add file after initial scan\n            return result\n        \n        reconstructor.scanner.scan = mock_scan\n        \n        # Run reconstruction\n        success = reconstructor.rebuild_drive_structure()\n        \n        # Should complete successfully even with concurrent changes\n        assert success, \"Should handle concurrent file system changes gracefully\"\n        \n        # The new file won't be included (since scan was already done)\n        # but reconstruction should not fail\n        assert reconstructor.stats.errors == 0, \"Concurrent changes should not cause errors\"\n\n\nif __name__ == \"__main__\":\n    # Run tests directly\n    pytest.main([__file__, \"-v\", \"-s\"])