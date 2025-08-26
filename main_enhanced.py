import os
import shutil
import filecmp
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse

# cSpell:ignore Reconstructor fsrc fdst reconstructor
class SafeTakeoutReconstructor:
    def __init__(self, source_dir, dest_dir, dry_run=True, progress_callback=None, gui_mode=False):
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.dry_run = dry_run
        self.progress_callback = progress_callback  # GUI progress updates
        self.gui_mode = gui_mode  # When True, sends prompts to GUI instead of terminal
        
        # Logging setup
        self.log_dir = self.dest_dir.parent / "takeout_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"rebuild_log_{timestamp}.txt"
        self.error_log = self.log_dir / f"errors_{timestamp}.txt"
        self.duplicate_log = self.log_dir / f"duplicates_{timestamp}.txt"
        self.manifest_file = self.log_dir / f"manifest_{timestamp}.json"
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'copied_files': 0,
            'skipped_duplicates': 0,
            'renamed_duplicates': 0,
            'errors': 0,
            'total_size': 0,
            'copied_size': 0
        }
        
        # File tracking for deduplication
        self.file_hashes = {}  # hash -> list of file paths
        self.processed_files = set()
        
        # GUI state tracking
        self.current_operation = "idle"
        self.current_file = ""
        self.progress_percent = 0
        self.pending_prompt = None  # For GUI prompts
        self.cancelled = False  # Cancellation flag
        self.temp_files = set()  # Track temporary files for cleanup
        self.open_file_handles = set()  # Track open file handles
        
    def log(self, message, file=None):
        """Thread-safe logging with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        
        # Send to GUI if callback is available
        if self.progress_callback:
            self.progress_callback({
                'type': 'log',
                'message': message,
                'timestamp': timestamp,
                'stats': self.stats.copy(),
                'current_operation': self.current_operation,
                'current_file': self.current_file,
                'progress_percent': self.progress_percent
            })
        
        if file is None:
            file = self.log_file
        
        with open(file, "a", encoding='utf-8') as f:
            f.write(log_message + "\n")
    
    def prompt_user(self, message, prompt_type="confirm", expected_responses=None):
        """Handle user prompts for both terminal and GUI"""
        if self.gui_mode:
            # Send prompt to GUI and wait for response
            self.pending_prompt = {
                'message': message,
                'type': prompt_type,
                'expected': expected_responses or ['y', 'n']
            }
            
            if self.progress_callback:
                self.progress_callback({
                    'type': 'prompt',
                    'message': message,
                    'prompt_type': prompt_type,
                    'expected_responses': expected_responses or ['y', 'n']
                })
            
            # In GUI mode, this should be handled by the GUI server
            # Return a default for now - GUI will override this
            return 'y'  
        else:
            # Terminal mode - use input() as before
            if prompt_type == "space_warning":
                response = input(f"{message}. Continue? (y/n): ")
                return response.lower()
            elif prompt_type == "copy_confirm":
                response = input(f"{message} (yes/no): ")
                return response.lower()
            else:
                response = input(f"{message}: ")
                return response.lower()
    
    def calculate_file_hash(self, filepath, chunk_size=8192):
        """Calculate SHA256 hash of a file"""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(chunk_size):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            self.log(f"Error hashing {filepath}: {e}", self.error_log)
            return None
    
    def validate_environment(self):
        """Pre-flight checks before starting"""
        self.log("=" * 60)
        self.log("VALIDATING ENVIRONMENT")
        self.log("=" * 60)
        
        # Smart path detection - try variations
        source_dir_str = str(self.source_dir)
        possible_paths = [
            self.source_dir,  # Original path
            Path(source_dir_str.rstrip()),  # Remove trailing spaces
            Path(source_dir_str.strip()),  # Remove leading and trailing spaces
            Path(source_dir_str.rstrip().replace(' ', '-')),  # Spaces to hyphens
            Path(source_dir_str.rstrip().replace('-', ' ')),  # Hyphens to spaces
        ]
        
        # Try to find the actual path
        actual_source = None
        for path in possible_paths:
            if path.exists():
                actual_source = path
                if path != self.source_dir:
                    self.log(f"📝 Note: Found source at slightly different path: {path}")
                    self.log(f"   (Original input: {self.source_dir})")
                break
        
        # If still not found, try glob pattern matching
        if not actual_source and self.source_dir.parent.exists():
            # Try to find similar named directories
            parent = self.source_dir.parent
            name = self.source_dir.name
            
            # Create patterns to try
            patterns = [
                name.strip(),  # Remove spaces
                name.strip().replace(' ', '*'),  # Allow any character where spaces are
                name.strip().replace('-', '*'),  # Allow any character where hyphens are
            ]
            
            for pattern in patterns:
                matches = list(parent.glob(pattern))
                if matches:
                    actual_source = matches[0]
                    self.log(f"📝 Found source using pattern matching: {actual_source}")
                    self.log(f"   (Original input: {self.source_dir})")
                    break
        
        if not actual_source:
            # Show helpful error with what directories DO exist
            self.log(f"❌ Source directory not found: {self.source_dir}")
            if self.source_dir.parent.exists():
                self.log("Available directories in parent folder:")
                available_dirs = sorted([d for d in self.source_dir.parent.iterdir() if d.is_dir()])
                for item in available_dirs[:10]:  # Show first 10
                    self.log(f"  📁 {item.name}")
                if len(available_dirs) > 10:
                    self.log(f"  ... and {len(available_dirs) - 10} more")
            raise ValueError(f"Source directory does not exist: {self.source_dir}")
        
        # Update the source directory to the actual found path
        self.source_dir = actual_source
        self.log(f"✅ Source directory exists: {self.source_dir}")
        
        # Check available disk space
        try:
            import shutil
            dest_stats = shutil.disk_usage(self.dest_dir.parent if self.dest_dir.exists() else self.dest_dir.parent.parent)
            free_gb = dest_stats.free / (1024**3)
            self.log(f"Available disk space: {free_gb:.2f} GB")
            
            if free_gb < 50:  # Warning if less than 50GB free
                warning_msg = f"⚠️  WARNING: Only {free_gb:.2f} GB free"
                self.log(warning_msg)
                
                if self.gui_mode:
                    # In GUI mode, space check should have been done upfront
                    # Log the warning but continue (user already confirmed in GUI)
                    self.log("GUI mode: continuing with user pre-approval")
                else:
                    # Terminal mode: prompt user
                    response = input(f"{warning_msg}. Continue? (y/n): ")
                    if response.lower() != 'y':
                        sys.exit("Aborted by user")
        except:
            self.log("Could not check disk space", self.error_log)
        
        # Scan for takeout folders (handle multiple nested structures)
        self.takeout_folders = []
        
        # Pattern 1: Direct Takeout/Drive structure
        direct_takeouts = list(self.source_dir.glob("Takeout*/Drive"))
        self.takeout_folders.extend(direct_takeouts)
        
        # Pattern 2: Nested structure from ZIP extraction (takeout-*/Takeout/Drive)
        nested_takeouts = list(self.source_dir.glob("*/Takeout/Drive"))
        self.takeout_folders.extend(nested_takeouts)
        
        # Pattern 3: Double nested structure (takeout-*/Takeout*)
        double_nested = list(self.source_dir.glob("*/Takeout*"))
        self.takeout_folders.extend(double_nested)
        
        # Pattern 4: Fallback - any Takeout folder at any level
        if not self.takeout_folders:
            fallback_takeouts = list(self.source_dir.glob("**/Takeout*"))
            # Filter to only include directories
            self.takeout_folders = [f for f in fallback_takeouts if f.is_dir()]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_takeouts = []
        for folder in self.takeout_folders:
            if folder not in seen:
                seen.add(folder)
                unique_takeouts.append(folder)
        self.takeout_folders = unique_takeouts
        
        self.log(f"Found {len(self.takeout_folders)} Takeout folders")
        for folder in self.takeout_folders:
            self.log(f"  - {folder}")
        
        if not self.takeout_folders:
            raise ValueError("No Takeout folders found!")
        
        return True
    
    def estimate_operation_size(self):
        """Calculate total size and file count before processing"""
        self.log("\n" + "=" * 60)
        self.log("ESTIMATING OPERATION SIZE")
        self.log("=" * 60)
        
        total_size = 0
        total_files = 0
        
        for takeout_drive in self.takeout_folders:
            for root, dirs, files in os.walk(takeout_drive):
                # Skip metadata folders
                if '.metadata' in root:
                    continue
                    
                for file in files:
                    # Skip Google metadata JSON files
                    if file.endswith('.json') and not file.startswith('.'):
                        continue
                        
                    filepath = Path(root) / file
                    try:
                        size = filepath.stat().st_size
                        total_size += size
                        total_files += 1
                    except:
                        pass
        
        self.stats['total_files'] = total_files
        self.stats['total_size'] = total_size
        
        self.log(f"Total files to process: {total_files:,}")
        self.log(f"Total size: {total_size / (1024**3):.2f} GB")
        
        return total_files, total_size
    
    def handle_google_metadata(self, src_file):
        """Extract original filename from Google Takeout metadata with proper resource management"""
        # Google Takeout may append numbers or have companion .json files
        json_file = Path(str(src_file) + ".json")
        if json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    # Google metadata might have original title
                    if 'title' in metadata:
                        title = metadata['title']
                        # Ensure title is safe for filesystem
                        import re
                        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
                        return safe_title
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
                self.log(f"Warning: Could not read metadata for {src_file}: {e}")
            except Exception as e:
                self.log(f"Unexpected error reading metadata for {src_file}: {e}")
        
        # Handle numbered exports (file(1).ext, file(2).ext, etc.)
        filename = src_file.name
        import re
        pattern = r'^(.+)\(\d+\)(\.[^.]+)?$'
        match = re.match(pattern, filename)
        if match:
            return match.group(1) + (match.group(2) or '')
        
        return filename
    
    def safe_copy_file(self, src_file, dst_file):
        """Copy file with verification and proper resource management"""
        try:
            # Validate source file
            if not src_file.exists():
                raise FileNotFoundError(f"Source file does not exist: {src_file}")
            
            if not src_file.is_file():
                raise ValueError(f"Source is not a file: {src_file}")
            
            # Create parent directory if needed with proper permissions
            dst_file.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Check if destination already exists and handle appropriately
            if dst_file.exists():
                if dst_file.samefile(src_file):
                    # Same file, no need to copy
                    return True
            
            # Copy with metadata preservation using chunks for large files
            if not self.dry_run:
                # For files larger than 100MB, use chunked copy to prevent memory issues
                file_size = src_file.stat().st_size
                if file_size > 100 * 1024 * 1024:  # 100MB
                    self._chunked_copy(src_file, dst_file)
                else:
                    shutil.copy2(src_file, dst_file)
                
                # Verify copy immediately
                dst_stat = dst_file.stat()
                src_stat = src_file.stat()
                
                if src_stat.st_size != dst_stat.st_size:
                    # Clean up failed copy
                    try:
                        dst_file.unlink()
                    except:
                        pass
                    raise ValueError(f"Size mismatch after copy! Expected {src_stat.st_size}, got {dst_stat.st_size}")
                
                # For critical mode, also verify hash
                if hasattr(self, 'verify_copies') and self.verify_copies:
                    try:
                        src_hash = self.calculate_file_hash(src_file)
                        dst_hash = self.calculate_file_hash(dst_file)
                        if src_hash != dst_hash:
                            # Clean up failed copy
                            try:
                                dst_file.unlink()
                            except:
                                pass
                            raise ValueError(f"Hash mismatch after copy! File may be corrupted.")
                    except Exception as hash_error:
                        # If hash verification fails, remove the copy to be safe
                        try:
                            dst_file.unlink()
                        except:
                            pass
                        raise ValueError(f"Hash verification failed: {hash_error}")
            
            return True
            
        except (OSError, IOError) as e:
            self.log(f"ERROR: I/O error copying {src_file}: {e}", self.error_log)
            self.stats['errors'] += 1
            return False
        except Exception as e:
            self.log(f"ERROR copying {src_file}: {e}", self.error_log)
            self.stats['errors'] += 1
            return False
    
    def _chunked_copy(self, src_file, dst_file):
        """Copy large files in chunks to prevent memory issues"""
        chunk_size = 64 * 1024  # 64KB chunks
        
        try:
            with open(src_file, 'rb') as fsrc:
                with open(dst_file, 'wb') as fdst:
                    while True:
                        chunk = fsrc.read(chunk_size)
                        if not chunk:
                            break
                        fdst.write(chunk)
                        
            # Copy metadata separately
            shutil.copystat(src_file, dst_file)
            
        except Exception as e:
            # Clean up partial file on error
            try:
                if dst_file.exists():
                    dst_file.unlink()
            except:
                pass
            raise e
    
    def process_file(self, src_file, rel_path):
        """Process a single file with deduplication"""
        # Get clean filename
        clean_name = self.handle_google_metadata(src_file)
        
        # Build target path
        target_dir = self.dest_dir / rel_path
        dst_file = target_dir / clean_name
        
        # Skip if already processed (across different takeouts)
        file_key = f"{rel_path}/{clean_name}"
        if file_key in self.processed_files:
            self.log(f"Already processed: {file_key}")
            self.stats['skipped_duplicates'] += 1
            return
        
        # Handle existing files
        if dst_file.exists() and not self.dry_run:
            # Check if it's the same file
            if filecmp.cmp(src_file, dst_file, shallow=False):
                self.log(f"Identical file exists, skipping: {dst_file}")
                self.stats['skipped_duplicates'] += 1
                self.processed_files.add(file_key)
                return
            else:
                # Find unique name
                counter = 1
                while dst_file.exists():
                    name_parts = clean_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        new_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        new_name = f"{clean_name}_{counter}"
                    dst_file = target_dir / new_name
                    counter += 1
                
                self.log(f"Renamed to avoid collision: {dst_file.name}", self.duplicate_log)
                self.stats['renamed_duplicates'] += 1
        
        # Perform the copy
        if self.dry_run:
            self.log(f"[DRY RUN] Would copy: {src_file} -> {dst_file}")
        else:
            if self.safe_copy_file(src_file, dst_file):
                self.log(f"Copied: {src_file} -> {dst_file}")
                self.stats['copied_files'] += 1
                self.stats['copied_size'] += src_file.stat().st_size
                
                # Record in manifest
                self.record_manifest_entry(src_file, dst_file)
        
        self.processed_files.add(file_key)
    
    def record_manifest_entry(self, src_file, dst_file):
        """Record file operation in manifest for potential rollback"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'source': str(src_file),
            'destination': str(dst_file),
            'size': src_file.stat().st_size,
            'hash': self.calculate_file_hash(src_file) if self.verify_copies else None
        }
        
        # Append to manifest file
        with open(self.manifest_file, 'a') as f:
            json.dump(entry, f)
            f.write('\n')
    
    def reconstruct(self, verify_copies=False):
        """Main reconstruction process"""
        self.verify_copies = verify_copies
        
        # Pre-flight checks
        self.validate_environment()
        
        # Estimate size
        total_files, total_size = self.estimate_operation_size()
        
        # Confirmation
        if not self.dry_run:
            self.log("\n" + "=" * 60)
            self.log("⚠️  READY TO START ACTUAL COPY OPERATION")
            self.log(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE COPY'}")
            self.log(f"Files: {total_files:,}")
            self.log(f"Size: {total_size / (1024**3):.2f} GB")
            self.log(f"Verification: {'ENABLED' if verify_copies else 'DISABLED'}")
            self.log("=" * 60)
            
            if self.gui_mode:
                # In GUI mode, user already confirmed by clicking "Start Restructuring"
                self.log("\n✅ GUI mode: proceeding with user pre-approval")
            else:
                # Terminal mode: prompt user
                response = input("\n⚠️  This will copy files. Continue? (yes/no): ")
                if response.lower() != 'yes':
                    sys.exit("Aborted by user")
        
        # Process files
        self.log("\n" + "=" * 60)
        self.log("STARTING RECONSTRUCTION")
        self.log("=" * 60)
        
        processed = 0
        for takeout_drive in self.takeout_folders:
            if self.cancelled:
                self.log("⚠️ Operation cancelled during processing")
                return
                
            self.log(f"\nProcessing: {takeout_drive}")
            
            for root, dirs, files in os.walk(takeout_drive):
                if self.cancelled:
                    self.log("⚠️ Operation cancelled during file processing")
                    return
                # Skip metadata directories
                if '.metadata' in root:
                    continue
                
                # Calculate relative path
                try:
                    rel_path = Path(root).relative_to(takeout_drive)
                except ValueError:
                    rel_path = Path()
                
                for file in files:
                    if self.cancelled:
                        self.log("⚠️ Operation cancelled during file iteration")
                        return
                        
                    # Skip JSON metadata files
                    if file.endswith('.json') and not file.startswith('.'):
                        continue
                    
                    src_file = Path(root) / file
                    
                    # Progress indicator
                    processed += 1
                    if processed % 100 == 0:
                        pct = (processed / total_files) * 100
                        self.progress_percent = pct
                        self.log(f"Progress: {processed}/{total_files} ({pct:.1f}%)")
                    
                    # Update current file for GUI
                    self.current_file = str(src_file.name)
                    
                    # Process the file
                    self.process_file(src_file, rel_path)
        
        # Final report
        self.print_summary()
    
    def print_summary(self):
        """Print final summary"""
        self.log("\n" + "=" * 60)
        self.log("RECONSTRUCTION COMPLETE")
        self.log("=" * 60)
        self.log(f"Total files found: {self.stats['total_files']:,}")
        self.log(f"Files copied: {self.stats['copied_files']:,}")
        self.log(f"Skipped (identical): {self.stats['skipped_duplicates']:,}")
        self.log(f"Renamed (collisions): {self.stats['renamed_duplicates']:,}")
        self.log(f"Errors: {self.stats['errors']:,}")
        self.log(f"Total size processed: {self.stats['copied_size'] / (1024**3):.2f} GB")
        self.log("=" * 60)
        self.log(f"Logs saved to: {self.log_dir}")
        
        if self.stats['errors'] > 0:
            self.log(f"⚠️  Check error log: {self.error_log}")
    
    def cancel(self):
        """Cancel the current operation and clean up resources"""
        self.cancelled = True
        self.log("🛑 Operation cancelled by user")
        self.cleanup_resources()
    
    def cleanup_resources(self):
        """Clean up all open resources and temporary files"""
        try:
            # Close any open file handles
            for handle in list(self.open_file_handles):
                try:
                    if hasattr(handle, 'close') and not handle.closed:
                        handle.close()
                except:
                    pass
            self.open_file_handles.clear()
            
            # Clean up temporary files
            for temp_file in list(self.temp_files):
                try:
                    temp_path = Path(temp_file)
                    if temp_path.exists():
                        if temp_path.is_file():
                            temp_path.unlink()
                        elif temp_path.is_dir():
                            import shutil
                            shutil.rmtree(temp_path, ignore_errors=True)
                except Exception as e:
                    self.log(f"Warning: Could not cleanup temp file {temp_file}: {e}")
            self.temp_files.clear()
            
            self.log("🧹 Resource cleanup completed")
            
        except Exception as e:
            self.log(f"Warning: Error during resource cleanup: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup on object deletion"""
        try:
            self.cleanup_resources()
        except:
            pass
        
        # Update GUI state if callback exists
        if self.progress_callback:
            self.progress_callback({
                'status': 'cancelled',
                'message': 'Operation cancelled by user',
                'progress_percent': 0
            })

def main():
    parser = argparse.ArgumentParser(description='Safely reconstruct Google Drive from Takeout')
    parser.add_argument('--source', default="/Volumes/Creator Pro/GDrive Jul 31st",
                       help='Source directory containing Takeout folders')
    parser.add_argument('--dest', default="/Volumes/Creator Pro/GDrive Jul 31st/Drive Combine",
                       help='Destination directory for reconstructed drive')
    parser.add_argument('--execute', action='store_true',
                       help='Execute actual copy (default is dry run)')
    parser.add_argument('--verify', action='store_true',
                       help='Verify each file after copying (slower but safer)')
    
    args = parser.parse_args()
    
    # Create reconstructor
    reconstructor = SafeTakeoutReconstructor(
        source_dir=args.source,
        dest_dir=args.dest,
        dry_run=not args.execute
    )
    
    # Run reconstruction
    reconstructor.reconstruct(verify_copies=args.verify)

if __name__ == "__main__":
    main()
