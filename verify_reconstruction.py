import os
import hashlib
import json
from pathlib import Path
from collections import defaultdict

class TakeoutVerifier:
    def __init__(self, source_dir, dest_dir):
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.issues = []
        
    def calculate_file_hash(self, filepath, chunk_size=8192):
        """Calculate SHA256 hash of a file"""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(chunk_size):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            return None
    
    def verify_structure(self):
        """Verify folder structure was properly recreated"""
        print("\n" + "=" * 60)
        print("VERIFYING FOLDER STRUCTURE")
        print("=" * 60)
        
        source_dirs = set()
        dest_dirs = set()
        
        # Collect all directories from source
        for takeout in self.source_dir.glob("Takeout*/Drive"):
            for root, dirs, _ in os.walk(takeout):
                rel_path = Path(root).relative_to(takeout)
                source_dirs.add(str(rel_path))
        
        # Collect all directories from destination
        for root, dirs, _ in os.walk(self.dest_dir):
            rel_path = Path(root).relative_to(self.dest_dir)
            dest_dirs.add(str(rel_path))
        
        # Check for missing directories
        missing = source_dirs - dest_dirs
        if missing:
            print(f"⚠️  Missing directories in destination: {len(missing)}")
            for d in list(missing)[:10]:  # Show first 10
                print(f"  - {d}")
        else:
            print("✅ All source directories exist in destination")
        
        return len(missing) == 0
    
    def verify_files(self, sample_size=100):
        """Verify a sample of files were copied correctly"""
        print("\n" + "=" * 60)
        print(f"VERIFYING FILE INTEGRITY (sample of {sample_size})")
        print("=" * 60)
        
        import random
        
        # Collect all source files
        source_files = []
        for takeout in self.source_dir.glob("Takeout*/Drive"):
            for root, _, files in os.walk(takeout):
                for file in files:
                    if not file.endswith('.json'):  # Skip metadata
                        source_files.append(Path(root) / file)
        
        # Sample files for verification
        if len(source_files) > sample_size:
            sample = random.sample(source_files, sample_size)
        else:
            sample = source_files
        
        verified = 0
        failed = 0
        
        for src_file in sample:
            # Try to find corresponding file in destination
            # This is simplified - you might need more complex matching
            rel_path = None
            for takeout in self.source_dir.glob("Takeout*/Drive"):
                try:
                    rel_path = src_file.relative_to(takeout)
                    break
                except ValueError:
                    continue
            
            if rel_path:
                dst_file = self.dest_dir / rel_path
                
                if dst_file.exists():
                    # Verify size
                    if src_file.stat().st_size == dst_file.stat().st_size:
                        verified += 1
                        print(f"✅ Verified: {rel_path}")
                    else:
                        failed += 1
                        print(f"❌ Size mismatch: {rel_path}")
                        self.issues.append(f"Size mismatch: {rel_path}")
                else:
                    # Check for renamed versions
                    found = False
                    for f in dst_file.parent.glob(f"{dst_file.stem}*{dst_file.suffix}"):
                        if src_file.stat().st_size == f.stat().st_size:
                            verified += 1
                            print(f"✅ Found renamed: {rel_path} -> {f.name}")
                            found = True
                            break
                    
                    if not found:
                        failed += 1
                        print(f"❌ Missing: {rel_path}")
                        self.issues.append(f"Missing: {rel_path}")
        
        print(f"\nVerification Results:")
        print(f"  Verified: {verified}/{len(sample)}")
        print(f"  Failed: {failed}/{len(sample)}")
        
        return failed == 0
    
    def check_duplicates(self):
        """Check for unintended duplicates in destination"""
        print("\n" + "=" * 60)
        print("CHECKING FOR DUPLICATES")
        print("=" * 60)
        
        file_sizes = defaultdict(list)
        
        # Collect all files by size
        for root, _, files in os.walk(self.dest_dir):
            for file in files:
                filepath = Path(root) / file
                try:
                    size = filepath.stat().st_size
                    file_sizes[size].append(filepath)
                except:
                    pass
        
        # Find potential duplicates (same size)
        potential_dupes = 0
        checked = 0
        confirmed_dupes = 0
        
        for size, files in file_sizes.items():
            if len(files) > 1:
                potential_dupes += len(files) - 1
                
                # For files of same size, check if they're actually duplicates
                if checked < 50:  # Limit checking to avoid taking too long
                    hashes = {}
                    for f in files:
                        h = self.calculate_file_hash(f)
                        if h:
                            if h in hashes:
                                confirmed_dupes += 1
                                print(f"  Duplicate found: {f} == {hashes[h]}")
                            else:
                                hashes[h] = f
                    checked += 1
        
        print(f"\nDuplicate Analysis:")
        print(f"  Files with same size: {potential_dupes}")
        print(f"  Confirmed duplicates (sample): {confirmed_dupes}")
        
        return confirmed_dupes
    
    def run_verification(self):
        """Run all verification checks"""
        print("\n" + "🔍 STARTING VERIFICATION PROCESS")
        print("=" * 60)
        
        structure_ok = self.verify_structure()
        files_ok = self.verify_files()
        duplicates = self.check_duplicates()
        
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        print(f"Structure intact: {'✅ Yes' if structure_ok else '❌ No'}")
        print(f"Files verified: {'✅ Yes' if files_ok else '❌ No'}")
        print(f"Duplicates found: {duplicates}")
        
        if self.issues:
            print(f"\n⚠️  Issues found: {len(self.issues)}")
            for issue in self.issues[:10]:
                print(f"  - {issue}")
        
        return structure_ok and files_ok

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python verify_reconstruction.py <source_dir> <dest_dir>")
        sys.exit(1)
    
    verifier = TakeoutVerifier(sys.argv[1], sys.argv[2])
    success = verifier.run_verification()
    
    sys.exit(0 if success else 1)
