import json
import os
from pathlib import Path
from datetime import datetime

class TakeoutRollback:
    def __init__(self, manifest_file):
        self.manifest_file = Path(manifest_file)
        if not self.manifest_file.exists():
            raise ValueError(f"Manifest file not found: {manifest_file}")
        
        self.operations = []
        self.load_manifest()
    
    def load_manifest(self):
        """Load operations from manifest file"""
        with open(self.manifest_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    self.operations.append(entry)
                except:
                    pass
        
        print(f"Loaded {len(self.operations)} operations from manifest")
    
    def rollback(self, dry_run=True):
        """Rollback operations by removing copied files"""
        print("\n" + "=" * 60)
        print(f"ROLLBACK {'(DRY RUN)' if dry_run else '(EXECUTING)'}")
        print("=" * 60)
        
        removed = 0
        errors = 0
        
        # Process in reverse order
        for op in reversed(self.operations):
            dest_file = Path(op['destination'])
            
            if dest_file.exists():
                if dry_run:
                    print(f"[DRY RUN] Would remove: {dest_file}")
                else:
                    try:
                        dest_file.unlink()
                        print(f"Removed: {dest_file}")
                        removed += 1
                        
                        # Remove empty directories
                        try:
                            dest_file.parent.rmdir()
                        except:
                            pass  # Directory not empty
                    except Exception as e:
                        print(f"Error removing {dest_file}: {e}")
                        errors += 1
        
        print(f"\nRollback complete:")
        print(f"  Files removed: {removed}")
        print(f"  Errors: {errors}")
        
        return errors == 0

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Rollback takeout reconstruction')
    parser.add_argument('manifest', help='Path to manifest file')
    parser.add_argument('--execute', action='store_true', 
                       help='Actually perform rollback (default is dry run)')
    
    args = parser.parse_args()
    
    rollback = TakeoutRollback(args.manifest)
    success = rollback.rollback(dry_run=not args.execute)
    
    sys.exit(0 if success else 1)
