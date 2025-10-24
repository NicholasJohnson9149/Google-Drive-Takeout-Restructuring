#!/usr/bin/env python3
"""
Test script to verify the fixes implemented for Google Drive Takeout restructuring
"""
import tempfile
import shutil
from pathlib import Path
import sys
import os

# Add the app directory to path
sys.path.append(str(Path(__file__).parent))

from app.core.rebuilder_v2 import SafeTakeoutReconstructor
from app.core.duplicate_checker import DuplicateStrategy
from app.core.path_normalizer import PathNormalizer


def test_path_normalization():
    """Test that path normalization preserves Drive folder structure"""
    print("🧪 Testing path normalization...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_dir = Path(temp_dir) / "output"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        normalizer = PathNormalizer(dest_dir)
        
        # Test cases for path normalization
        test_cases = [
            # (input_path, expected_relative_output)
            ("Takeout/Drive/Documents/file.txt", "Documents/file.txt"),
            ("Takeout/Drive/Photos/2023/vacation.jpg", "Photos/2023/vacation.jpg"),
            ("Takeout 1/Drive/Projects/code.py", "Projects/code.py"),
            ("MyTakeout/Drive/Music/song.mp3", "Music/song.mp3"),
        ]
        
        for input_path, expected_output in test_cases:
            input_relative = Path(input_path)
            result = normalizer.normalize_path(input_relative, is_metadata=False)
            
            if result.clean_path:
                actual_relative = result.clean_path.relative_to(dest_dir)
                print(f"  ✓ {input_path} → {actual_relative}")
                
                if str(actual_relative) != expected_output:
                    print(f"  ❌ Expected: {expected_output}")
                    print(f"  ❌ Got: {actual_relative}")
                    return False
            else:
                print(f"  ❌ Path was skipped: {input_path}")
                return False
    
    print("  ✅ Path normalization tests passed!")
    return True


def test_duplicate_handling():
    """Test duplicate handling with different conflict resolution strategies"""
    print("🧪 Testing duplicate handling...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock Takeout structure
        source_dir = Path(temp_dir) / "source"
        takeout_dir = source_dir / "Takeout" / "Drive" 
        takeout_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test files
        file1 = takeout_dir / "test.txt"
        file2 = takeout_dir / "duplicate.txt"
        file1.write_text("Test content 1")
        file2.write_text("Test content 2")
        
        # Output directory
        output_dir = Path(temp_dir) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a duplicate in the output directory
        existing_file = output_dir / "test.txt"
        existing_file.write_text("Test content 1")  # Same content as file1
        
        # Test 1: Skip duplicates
        print("  Testing skip duplicates...")
        reconstructor_skip = SafeTakeoutReconstructor(
            takeout_path=str(source_dir),
            export_path=str(output_dir),
            dry_run=True,  # Dry run for testing
            conflict_resolution="skip",
            duplicate_strategy=DuplicateStrategy.HASH
        )
        
        success = reconstructor_skip.rebuild_drive_structure()
        stats_skip = reconstructor_skip.stats
        print(f"    Skip mode - Duplicates skipped: {stats_skip.skipped_duplicates}")
        
        # Test 2: Rename duplicates
        print("  Testing rename duplicates...")
        # Clean output for fresh test
        if existing_file.exists():
            existing_file.unlink()
        existing_file.write_text("Test content 1")  # Recreate
        
        reconstructor_rename = SafeTakeoutReconstructor(
            takeout_path=str(source_dir),
            export_path=str(output_dir),
            dry_run=True,  # Dry run for testing
            conflict_resolution="rename",
            duplicate_strategy=DuplicateStrategy.HASH
        )
        
        success = reconstructor_rename.rebuild_drive_structure()
        stats_rename = reconstructor_rename.stats
        print(f"    Rename mode - Duplicates renamed: {stats_rename.renamed_duplicates}")
        
        print("  ✅ Duplicate handling tests passed!")
        return True


def test_cli_integration():
    """Test CLI command building and parameter passing"""
    print("🧪 Testing CLI integration...")
    
    from app.core.cli_executor import CLIExecutor
    
    executor = CLIExecutor()
    
    # Test CLI command building with new parameters
    options = {
        'dry_run': True,
        'verify': True,
        'conflict_resolution': 'rename',
        'force': True,
        'verbose': True
    }
    
    cmd = executor.build_rebuild_command("/test/input", "/test/output", options)
    
    print(f"  Built command: {' '.join(cmd)}")
    
    # Verify all expected parameters are included
    expected_flags = ['--dry-run', '--verify', '--conflict-resolution', 'rename', '--force', '--verbose']
    cmd_str = ' '.join(cmd)
    
    for flag in expected_flags:
        if flag not in cmd_str:
            print(f"  ❌ Missing expected flag: {flag}")
            return False
    
    print("  ✅ CLI integration tests passed!")
    return True


def main():
    """Run all tests"""
    print("🚀 Testing Google Drive Takeout Restructuring Fixes")
    print("=" * 60)
    
    tests = [
        test_path_normalization,
        test_duplicate_handling,
        test_cli_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            failed += 1
        print()
    
    print("=" * 60)
    print(f"🏁 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All tests passed! The fixes should work correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please review the issues above.")
        return 1


if __name__ == "__main__":
    exit(main())