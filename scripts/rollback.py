#!/usr/bin/env python3
"""
Utility script to rollback a reconstruction using manifest file
"""
import sys
import json
import argparse
from pathlib import Path

# Simple rollback without importing the full app
def main():
    parser = argparse.ArgumentParser(
        description="Rollback a Google Drive reconstruction using manifest file"
    )
    
    parser.add_argument(
        'manifest',
        type=Path,
        help='Path to the manifest JSON file from the reconstruction'
    )
    parser.add_argument(
        '--dry-run',
        '-n',
        action='store_true',
        help='Preview what would be rolled back without making changes'
    )
    
    args = parser.parse_args()
    
    # Load manifest
    try:
        with open(args.manifest) as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"Error loading manifest: {e}")
        return 1
    
    print("="*50)
    print("RECONSTRUCTION ROLLBACK")
    print("="*50)
    print(f"Manifest: {args.manifest}")
    print(f"Date: {manifest.get('timestamp', 'Unknown')}")
    print(f"Source: {manifest.get('source_directory', 'Unknown')}")
    print(f"Destination: {manifest.get('destination_directory', 'Unknown')}")
    print(f"Files to rollback: {len(manifest.get('copied_files', []))}")
    print("")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be deleted")
        print("")
        print("Files that would be removed:")
        for file_info in manifest.get('copied_files', []):
            dest_path = Path(file_info['destination'])
            if dest_path.exists():
                print(f"  - {dest_path}")
        print(f"\nTotal files to remove: {len(manifest.get('copied_files', []))}")
    else:
        print("This functionality requires the full app. Use:")
        print(f"python -c \"")
        print(f"import json, shutil")
        print(f"with open('{args.manifest}') as f: manifest = json.load(f)")
        print(f"for file_info in manifest.get('copied_files', []):")
        print(f"    try: Path(file_info['destination']).unlink()")
        print(f"    except: pass")
        print(f"\"")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())