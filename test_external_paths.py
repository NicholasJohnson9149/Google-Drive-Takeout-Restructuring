#!/usr/bin/env python3
"""
Test external drive path detection and validation
This verifies our smart path detection logic works with external drives
"""

import sys
from pathlib import Path

def test_path_detection(input_path):
    """Test the same smart path detection logic used in gui_server.py"""
    print(f"\n🔍 Testing path: '{input_path}'")
    
    # Smart path detection - same logic as GUI server
    possible_paths = [
        Path(input_path),  # Original path
        Path(input_path.rstrip()),  # Remove trailing spaces
        Path(input_path.strip()),  # Remove leading/trailing spaces
        Path(input_path.replace(' ', '-')),  # Replace spaces with hyphens
        Path(input_path.replace('-', ' ')),  # Replace hyphens with spaces
    ]
    
    print("  Trying variations:")
    for i, path_candidate in enumerate(possible_paths, 1):
        try:
            # Handle external drives carefully
            if str(path_candidate).startswith('/Volumes/'):
                resolved_path = path_candidate.expanduser()
                resolve_method = "expanduser() [external drive]"
            else:
                resolved_path = path_candidate.expanduser().resolve()
                resolve_method = "expanduser().resolve() [local]"
            
            exists = resolved_path.exists()
            is_dir = resolved_path.is_dir() if exists else False
            
            status = "✅ FOUND" if (exists and is_dir) else "❌ Missing"
            print(f"    {i}. {path_candidate} -> {status}")
            print(f"       Method: {resolve_method}")
            print(f"       Resolved: {resolved_path}")
            print(f"       Exists: {exists}, Is Dir: {is_dir}")
            
            if exists and is_dir:
                print(f"  🎉 SUCCESS: Found valid directory at {resolved_path}")
                
                # Check for ZIP files
                zip_files = list(resolved_path.glob('*.zip'))
                print(f"  📦 Found {len(zip_files)} ZIP files")
                if zip_files:
                    for zip_file in zip_files[:3]:  # Show first 3
                        size_mb = zip_file.stat().st_size / (1024 * 1024)
                        print(f"    - {zip_file.name} ({size_mb:.1f} MB)")
                    if len(zip_files) > 3:
                        print(f"    ... and {len(zip_files) - 3} more")
                
                return resolved_path
                
        except (OSError, RuntimeError) as e:
            print(f"    {i}. {path_candidate} -> ⚠️  Error: {e}")
            continue
    
    print("  ❌ No valid directory found")
    return None

def main():
    print("=" * 60)
    print("🧪 EXTERNAL DRIVE PATH DETECTION TEST")
    print("=" * 60)
    
    # Test paths
    test_paths = [
        "/Users/nicholasjohnson/Developer/gDrive-consaldator",  # Local path
    ]
    
    # Add external drive path if provided as argument
    if len(sys.argv) > 1:
        external_path = sys.argv[1]
        test_paths.append(external_path)
        
        # Test variations that commonly cause issues
        test_paths.extend([
            external_path + " ",  # With trailing space
            external_path.replace(" ", "-"),  # Spaces to hyphens
            external_path.replace("-", " "),  # Hyphens to spaces
        ])
    
    results = []
    for test_path in test_paths:
        result = test_path_detection(test_path)
        results.append((test_path, result))
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    success_count = 0
    for test_path, result in results:
        if result:
            print(f"✅ {test_path}")
            success_count += 1
        else:
            print(f"❌ {test_path}")
    
    print(f"\n🎯 Success Rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    if len(sys.argv) == 1:
        print("\n💡 Usage: python test_external_paths.py '/Volumes/Creator Pro/gDrive-Jul-31st'")

if __name__ == "__main__":
    main()
