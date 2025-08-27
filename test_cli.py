#!/usr/bin/env python3
"""
Simple test script to avoid shell parsing issues
"""
import subprocess
import sys

def test_path_flattening():
    """Test the path flattening fix"""
    cmd = [
        sys.executable, "-m", "app.cli", "--verbose", "rebuild",
        "/Volumes/Creator Pro/gDrive-test-output/extracted_takeout",
        "/tmp/flat_test",
        "--dry-run"
    ]
    
    print("Testing path flattening with command:")
    print(" ".join(f'"{arg}"' if " " in arg else arg for arg in cmd))
    print("\n" + "="*50)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        print(f"\nReturn code: {result.returncode}")
        
        # Look for key indicators
        if "Path transform:" in result.stdout:
            print("\n✅ Path transformation is working!")
        if "/Drive/" in result.stdout and "flat_test" in result.stdout:
            print("⚠️  WARNING: Still seeing Drive/ in output paths")
        if "No valid path parts remaining" in result.stdout:
            print("❌ ERROR: Path cleaning is too aggressive")
            
    except Exception as e:
        print(f"Error running command: {e}")

if __name__ == "__main__":
    test_path_flattening()