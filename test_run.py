#!/usr/bin/env python
"""
Test runner for Google Drive consolidation
Testing with sample data before running on full 300GB dataset
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Test Configuration
TEST_SOURCE = "/Volumes/Creator Pro/gDrive-test-sample"
TEST_DEST = "/Volumes/Creator Pro/gDrive-test-output"
FULL_SOURCE = "/Volumes/Creator Pro/GDrive Jul 31st"
FULL_DEST = "/Volumes/Creator Pro/GDrive Jul 31st/Drive Combine"

def check_paths():
    """Verify paths exist and show disk space"""
    print("=" * 60)
    print("PATH VERIFICATION")
    print("=" * 60)
    
    source_path = Path(TEST_SOURCE)
    
    if source_path.exists():
        print(f"✅ Test source exists: {TEST_SOURCE}")
        
        # Count files and calculate size
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(source_path):
            for file in files:
                filepath = Path(root) / file
                try:
                    total_size += filepath.stat().st_size
                    file_count += 1
                except:
                    pass
        
        print(f"   Files: {file_count:,}")
        print(f"   Size: {total_size / (1024**2):.2f} MB")
    else:
        print(f"❌ Test source NOT found: {TEST_SOURCE}")
        return False
    
    # Check disk space
    import shutil
    try:
        disk_usage = shutil.disk_usage("/Volumes/Creator Pro")
        free_gb = disk_usage.free / (1024**3)
        used_percent = (disk_usage.used / disk_usage.total) * 100
        
        print(f"\n💾 External Drive Space:")
        print(f"   Free: {free_gb:.2f} GB")
        print(f"   Used: {used_percent:.1f}%")
    except:
        print("⚠️  Could not check disk space")
    
    return True

def create_test_structure():
    """Create a proper test structure if needed"""
    print("\n" + "=" * 60)
    print("PREPARING TEST STRUCTURE")
    print("=" * 60)
    
    # Check if the test sample has Takeout structure
    test_path = Path(TEST_SOURCE)
    takeout_folders = list(test_path.glob("Takeout*"))
    
    if not takeout_folders:
        print("⚠️  No Takeout folders found in test sample")
        print("   Expected structure: Takeout/Drive/[your files]")
        
        # Check if we need to create the structure
        response = input("\nCreate Takeout structure for testing? (y/n): ")
        if response.lower() == 'y':
            # Create a mock Takeout structure
            mock_takeout = test_path / "Takeout" / "Drive"
            mock_takeout.mkdir(parents=True, exist_ok=True)
            
            # Move files into the structure
            for item in test_path.iterdir():
                if item.name != "Takeout" and not item.name.startswith('.'):
                    print(f"   Moving {item.name} to Takeout/Drive/")
                    item.rename(mock_takeout / item.name)
            
            print("✅ Created Takeout structure for testing")
    else:
        print(f"✅ Found {len(takeout_folders)} Takeout folder(s)")

def run_test():
    """Run the actual test"""
    print("\n" + "=" * 60)
    print("RUNNING TEST CONSOLIDATION")
    print("=" * 60)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Commands to run
    commands = [
        {
            'name': 'Dry Run (Safe Preview)',
            'cmd': f'python main_enhanced.py --source "{TEST_SOURCE}" --dest "{TEST_DEST}"',
            'safe': True
        },
        {
            'name': 'Actual Execution',
            'cmd': f'python main_enhanced.py --source "{TEST_SOURCE}" --dest "{TEST_DEST}" --execute',
            'safe': False
        },
        {
            'name': 'Execution with Verification',
            'cmd': f'python main_enhanced.py --source "{TEST_SOURCE}" --dest "{TEST_DEST}" --execute --verify',
            'safe': False
        }
    ]
    
    print("\nAvailable commands:")
    for i, cmd in enumerate(commands, 1):
        safety = "✅ SAFE" if cmd['safe'] else "⚠️  WRITES DATA"
        print(f"\n{i}. {cmd['name']} [{safety}]")
        print(f"   Command: {cmd['cmd']}")
    
    print("\n" + "-" * 60)
    choice = input("\nWhich test would you like to run? (1/2/3): ")
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(commands):
            selected = commands[idx]
            
            if not selected['safe']:
                confirm = input(f"\n⚠️  This will write to {TEST_DEST}. Continue? (yes/no): ")
                if confirm.lower() != 'yes':
                    print("Aborted.")
                    return
            
            print(f"\n🚀 Running: {selected['name']}")
            print(f"Command: {selected['cmd']}")
            print("-" * 60)
            
            # Execute the command
            os.system(selected['cmd'])
            
            # After execution, show results location
            if not selected['safe']:
                print("\n" + "=" * 60)
                print("TEST COMPLETE")
                print("=" * 60)
                print(f"✅ Output location: {TEST_DEST}")
                print(f"📋 Logs location: {TEST_DEST}/../takeout_logs/")
                
                # Quick verification
                if Path(TEST_DEST).exists():
                    file_count = sum(1 for _ in Path(TEST_DEST).rglob('*') if _.is_file())
                    print(f"📁 Files in output: {file_count}")
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")

def verify_results():
    """Verify the test results"""
    print("\n" + "=" * 60)
    print("VERIFYING TEST RESULTS")
    print("=" * 60)
    
    dest_path = Path(TEST_DEST)
    
    if not dest_path.exists():
        print("❌ Output directory doesn't exist yet")
        print("   Run the test first!")
        return
    
    # Run verification script
    verify_cmd = f'python verify_reconstruction.py "{TEST_SOURCE}" "{TEST_DEST}"'
    print(f"Running verification: {verify_cmd}")
    os.system(verify_cmd)

def main():
    print("=" * 60)
    print("GOOGLE DRIVE CONSOLIDATOR - TEST MODE")
    print("=" * 60)
    print(f"Test Source: {TEST_SOURCE}")
    print(f"Test Output: {TEST_DEST}")
    print("=" * 60)
    
    # Check environment
    if not check_paths():
        print("\n❌ Path verification failed!")
        sys.exit(1)
    
    # Prepare test structure
    create_test_structure()
    
    # Menu
    while True:
        print("\n" + "=" * 60)
        print("TEST MENU")
        print("=" * 60)
        print("1. Run test consolidation")
        print("2. Verify test results")
        print("3. Clean test output (start fresh)")
        print("4. Show full dataset info")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ")
        
        if choice == '1':
            run_test()
        elif choice == '2':
            verify_results()
        elif choice == '3':
            if Path(TEST_DEST).exists():
                confirm = input(f"Delete {TEST_DEST}? (yes/no): ")
                if confirm.lower() == 'yes':
                    import shutil
                    shutil.rmtree(TEST_DEST)
                    print("✅ Test output cleaned")
            else:
                print("No test output to clean")
        elif choice == '4':
            print(f"\nFull Dataset Info:")
            print(f"Source: {FULL_SOURCE}")
            print(f"Destination: {FULL_DEST}")
            if Path(FULL_SOURCE).exists():
                # Quick size check
                import subprocess
                result = subprocess.run(['du', '-sh', FULL_SOURCE], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"Size: {result.stdout.strip()}")
        elif choice == '5':
            print("Goodbye!")
            break

if __name__ == "__main__":
    main()
