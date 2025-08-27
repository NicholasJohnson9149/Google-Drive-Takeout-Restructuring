#!/usr/bin/env python3
"""
Test the improved rebuilder with better separation of concerns
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.rebuilder_v2 import SafeTakeoutReconstructor
from app.core.duplicate_checker import DuplicateStrategy


def test_improved_rebuilder():
    """Test the improved rebuilder with your real data"""
    
    print("🚀 Testing Improved SafeTakeoutReconstructor")
    print("=" * 50)
    
    # Progress callback to show updates
    def progress_callback(data):
        if data.get('type') == 'progress':
            percent = data.get('percent', 0)
            current_file = data.get('current_file', '')
            print(f"Progress: {percent:.1f}% - {current_file}")
        
        elif data.get('type') == 'status':
            status = data.get('status', '')
            message = data.get('message', '')
            print(f"Status: {status.upper()} - {message}")
        
        elif data.get('type') == 'stats':
            stats = data.get('stats', {})
            print(f"Stats: {stats}")
    
    # Initialize improved reconstructor
    reconstructor = SafeTakeoutReconstructor(
        takeout_path="/Volumes/Creator Pro/gDrive-test-output/extracted_takeout",
        export_path="/tmp/improved_flat_test",
        dry_run=True,  # Safe testing
        duplicate_strategy=DuplicateStrategy.HASH,  # Proper duplicate detection
        progress_callback=progress_callback
    )
    
    try:
        print("\nStarting reconstruction with improved architecture...")
        success = reconstructor.rebuild_drive_structure(verify_copies=False)
        
        print(f"\nReconstruction {'succeeded' if success else 'failed'}")
        
        # Show final stats
        print("\nFinal Statistics:")
        print(f"  Total files: {reconstructor.stats.total_files}")
        print(f"  Files to copy: {reconstructor.stats.copied_files}")
        print(f"  Skipped duplicates: {reconstructor.stats.skipped_duplicates}")
        print(f"  Skipped metadata: {reconstructor.stats.skipped_metadata}")
        print(f"  Errors: {reconstructor.stats.errors}")
        print(f"  Total size: {reconstructor.stats.total_size / (1024**3):.2f} GB")
        
        print(f"\nErrors encountered: {len(reconstructor.errors)}")
        if reconstructor.errors:
            print("First 5 errors:")
            for error in reconstructor.errors[:5]:
                print(f"  - {error.error_type}: {error.error_message}")
        
        return success
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False
    
    finally:
        # Clean up resources
        reconstructor.close()


def test_path_transformations():
    """Test path normalization logic"""
    print("\n🧪 Testing Path Transformations")
    print("=" * 30)
    
    from app.core.path_normalizer import PathNormalizer
    
    normalizer = PathNormalizer(Path("/tmp/output"))
    
    test_paths = [
        "Takeout/Drive/My Files/document.pdf",
        "Takeout 2/Drive/Photos/image.jpg", 
        "Takeout-123/Drive/Work/Spreadsheet.xlsx",
        "Takeout/Drive/Archive/Old Files/backup.zip",
        "Takeout/metadata.json"
    ]
    
    results = normalizer.test_transformations(test_paths)
    
    for result in results:
        print(f"Original: {result.original_path}")
        print(f"Result:   {result.clean_path or 'SKIPPED'}")
        print(f"Log:      {result.transformation_log}")
        print()


if __name__ == "__main__":
    print("Testing improved rebuilder architecture...")
    
    # Test path transformations first
    test_path_transformations()
    
    # Test full rebuilder
    success = test_improved_rebuilder()
    
    if success:
        print("\n✅ All tests passed! The improved rebuilder is working correctly.")
    else:
        print("\n❌ Tests failed. Check error messages above.")