#!/usr/bin/env python3
"""
Test real file processing (not dry run)
"""
import subprocess
import sys

def test_real_processing():
    """Test actual file processing"""
    cmd = [
        sys.executable, "-m", "app.cli", "--verbose", "rebuild",
        "/Volumes/Creator Pro/gDrive-test-output/extracted_takeout",
        "/Volumes/Creator Pro/gDrive-test-output/REAL_FLAT_OUTPUT",
        "--force", "--verify"  # Real run with verification
    ]
    
    print("🚀 REAL RUN: Processing files with path flattening")
    print(" ".join(f'"{arg}"' if " " in arg else arg for arg in cmd))
    print("\n" + "="*50)
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        print(f"\nReturn code: {result.returncode}")
        
        if result.returncode == 0:
            print("✅ SUCCESS! Files processed with flat structure")
            print("📂 Check: /Volumes/Creator Pro/gDrive-test-output/REAL_FLAT_OUTPUT")
            print("   Should contain your folders directly (no Drive/ nesting)")
        else:
            print("❌ Process failed")
            
    except Exception as e:
        print(f"Error running command: {e}")

if __name__ == "__main__":
    response = input("⚠️  This will create real files. Continue? (y/N): ")
    if response.lower().startswith('y'):
        test_real_processing()
    else:
        print("Cancelled")