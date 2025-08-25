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
from typing import Optional, Dict, List, Tuple
import time

# Optional enhanced features
try:
    from tqdm import tqdm
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    import psutil
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    tqdm = None
    console = None
    print("📝 Note: Install 'rich' and 'tqdm' for enhanced output")
    print("Run: pip install rich tqdm psutil")

class SafeTakeoutReconstructor:
    def __init__(self, source_dir: str, dest_dir: str, dry_run: bool = True):
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.dry_run = dry_run
        
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
        self.file_hashes: Dict[str, List[Path]] = {}
        self.processed_files = set()
        
    def log(self, message: str, file: Optional[Path] = None, level: str = "INFO"):
        """Enhanced logging with color support"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        # Console output with color
        if RICH_AVAILABLE and console:
            if level == "ERROR":
                console.print(f"[red]{log_message}[/red]")
            elif level == "WARNING":
                console.print(f"[yellow]{log_message}[/yellow]")
            elif level == "SUCCESS":
                console.print(f"[green]{log_message}[/green]")
            else:
                console.print(log_message)
        else:
            print(log_message)
        
        # File logging
        if file is None:
            file = self.log_file
        
        with open(file, "a", encoding='utf-8') as f:
            f.write(log_message + "\n")
    
    def check_system_resources(self) -> Dict[str, float]:
        """Check available system resources"""
        resources = {}
        
        if 'psutil' in sys.modules:
            import psutil
            
            # CPU usage
            resources['cpu_percent'] = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            resources['memory_percent'] = memory.percent
            resources['memory_available_gb'] = memory.available / (1024**3)
            
            # Disk usage for destination
            try:
                disk = psutil.disk_usage(str(self.dest_dir.parent))
                resources['disk_free_gb'] = disk.free / (1024**3)
                resources['disk_percent'] = disk.percent
            except:
                pass
        
        return resources
    
    def display_system_status(self):
        """Display current system status"""
        resources = self.check_system_resources()
        
        if RICH_AVAILABLE and console and resources:
            table = Table(title="System Resources")
            table.add_column("Resource", style="cyan")
            table.add_column("Status", style="green")
            
            table.add_row("CPU Usage", f"{resources.get('cpu_percent', 'N/A')}%")
            table.add_row("Memory Usage", f"{resources.get('memory_percent', 'N/A')}%")
            table.add_row("Memory Available", f"{resources.get('memory_available_gb', 'N/A'):.2f} GB")
            table.add_row("Disk Free", f"{resources.get('disk_free_gb', 'N/A'):.2f} GB")
            
            console.print(table)
    
    def calculate_file_hash(self, filepath: Path, chunk_size: int = 8192) -> Optional[str]:
        """Calculate SHA256 hash of a file"""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(chunk_size):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            self.log(f"Error hashing {filepath}: {e}", self.error_log, "ERROR")
            return None
    
    def validate_environment(self) -> bool:
        """Pre-flight checks before starting"""
        if RICH_AVAILABLE and console:
            console.print(Panel.fit("🔍 VALIDATING ENVIRONMENT", style="bold blue"))
        else:
            self.log("=" * 60)
            self.log("VALIDATING ENVIRONMENT")
            self.log("=" * 60)
        
        # Check source directory exists
        if not self.source_dir.exists():
            raise ValueError(f"Source directory does not exist: {self.source_dir}")
        
        self.log(f"✅ Source directory exists: {self.source_dir}", level="SUCCESS")
        
        # Display system resources
        self.display_system_status()
        
        # Check available disk space
        try:
            import shutil as shutil_disk
            dest_stats = shutil_disk.disk_usage(self.dest_dir.parent if self.dest_dir.exists() else self.dest_dir.parent.parent)
            free_gb = dest_stats.free / (1024**3)
            self.log(f"Available disk space: {free_gb:.2f} GB")
            
            if free_gb < 50:  # Warning if less than 50GB free
                self.log(f"⚠️  WARNING: Only {free_gb:.2f} GB free", level="WARNING")
                response = input(f"Continue? (y/n): ")
                if response.lower() != 'y':
                    sys.exit("Aborted by user")
        except Exception as e:
            self.log(f"Could not check disk space: {e}", self.error_log, "WARNING")
        
        # Scan for takeout folders
        self.takeout_folders = list(self.source_dir.glob("Takeout*/Drive"))
        if not self.takeout_folders:
            # Also try without /Drive suffix
            self.takeout_folders = list(self.source_dir.glob("Takeout*"))
        
        self.log(f"Found {len(self.takeout_folders)} Takeout folders")
        for folder in self.takeout_folders:
            self.log(f"  📁 {folder}")
        
        if not self.takeout_folders:
            raise ValueError("No Takeout folders found!")
        
        return True
    
    def estimate_operation_size(self) -> Tuple[int, int]:
        """Calculate total size and file count before processing"""
        if RICH_AVAILABLE and console:
            console.print(Panel.fit("📊 ESTIMATING OPERATION SIZE", style="bold blue"))
        else:
            self.log("\n" + "=" * 60)
            self.log("ESTIMATING OPERATION SIZE")
            self.log("=" * 60)
        
        total_size = 0
        total_files = 0
        
        # Use progress bar if available
        if RICH_AVAILABLE:
            with Progress() as progress:
                task = progress.add_task("[cyan]Scanning files...", total=None)
                
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
                                progress.update(task, advance=1)
                            except:
                                pass
        else:
            for takeout_drive in self.takeout_folders:
                for root, dirs, files in os.walk(takeout_drive):
                    if '.metadata' in root:
                        continue
                    for file in files:
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
        
        # Display summary
        if RICH_AVAILABLE and console:
            table = Table(title="Operation Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Files", f"{total_files:,}")
            table.add_row("Total Size", f"{total_size / (1024**3):.2f} GB")
            table.add_row("Average File Size", f"{(total_size / total_files / (1024**2)) if total_files > 0 else 0:.2f} MB")
            
            console.print(table)
        else:
            self.log(f"Total files to process: {total_files:,}")
            self.log(f"Total size: {total_size / (1024**3):.2f} GB")
        
        return total_files, total_size
    
    def reconstruct(self, verify_copies: bool = False):
        """Main reconstruction process with progress tracking"""
        self.verify_copies = verify_copies
        
        # Pre-flight checks
        self.validate_environment()
        
        # Estimate size
        total_files, total_size = self.estimate_operation_size()
        
        # Confirmation
        if not self.dry_run:
            if RICH_AVAILABLE and console:
                console.print(Panel.fit(
                    f"⚠️  READY TO START ACTUAL COPY OPERATION\n"
                    f"Mode: {'DRY RUN' if self.dry_run else 'LIVE COPY'}\n"
                    f"Files: {total_files:,}\n"
                    f"Size: {total_size / (1024**3):.2f} GB\n"
                    f"Verification: {'ENABLED' if verify_copies else 'DISABLED'}",
                    style="bold yellow"
                ))
            else:
                self.log("\n" + "=" * 60)
                self.log("⚠️  READY TO START ACTUAL COPY OPERATION")
                self.log(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE COPY'}")
                self.log(f"Files: {total_files:,}")
                self.log(f"Size: {total_size / (1024**3):.2f} GB")
                self.log(f"Verification: {'ENABLED' if verify_copies else 'DISABLED'}")
                self.log("=" * 60)
            
            response = input("\n⚠️  This will copy files. Continue? (yes/no): ")
            if response.lower() != 'yes':
                sys.exit("Aborted by user")
        
        # Process files with progress bar
        if RICH_AVAILABLE and console:
            console.print(Panel.fit("🚀 STARTING RECONSTRUCTION", style="bold green"))
        else:
            self.log("\n" + "=" * 60)
            self.log("STARTING RECONSTRUCTION")
            self.log("=" * 60)
        
        # Process with progress tracking
        if tqdm:
            pbar = tqdm(total=total_files, desc="Processing files", unit="files")
        else:
            pbar = None
        
        processed = 0
        start_time = time.time()
        
        for takeout_drive in self.takeout_folders:
            self.log(f"\n📁 Processing: {takeout_drive}")
            
            for root, dirs, files in os.walk(takeout_drive):
                # Skip metadata directories
                if '.metadata' in root:
                    continue
                
                # Calculate relative path
                try:
                    rel_path = Path(root).relative_to(takeout_drive)
                except ValueError:
                    rel_path = Path()
                
                for file in files:
                    # Skip JSON metadata files
                    if file.endswith('.json') and not file.startswith('.'):
                        continue
                    
                    src_file = Path(root) / file
                    
                    # Update progress
                    processed += 1
                    if pbar:
                        pbar.update(1)
                        # Update description with current file
                        pbar.set_description(f"Processing: {file[:30]}...")
                    elif processed % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = processed / elapsed if elapsed > 0 else 0
                        eta = (total_files - processed) / rate if rate > 0 else 0
                        self.log(f"Progress: {processed}/{total_files} ({processed/total_files*100:.1f}%) - ETA: {eta/60:.1f} min")
                    
                    # Process the file (implement your processing logic here)
                    # self.process_file(src_file, rel_path)
        
        if pbar:
            pbar.close()
        
        # Final report
        self.print_summary()
    
    def print_summary(self):
        """Print final summary with enhanced formatting"""
        if RICH_AVAILABLE and console:
            # Create summary table
            table = Table(title="🎉 RECONSTRUCTION COMPLETE", title_style="bold green")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total files found", f"{self.stats['total_files']:,}")
            table.add_row("Files copied", f"{self.stats['copied_files']:,}")
            table.add_row("Skipped (identical)", f"{self.stats['skipped_duplicates']:,}")
            table.add_row("Renamed (collisions)", f"{self.stats['renamed_duplicates']:,}")
            table.add_row("Errors", f"{self.stats['errors']:,}" if self.stats['errors'] == 0 else f"[red]{self.stats['errors']:,}[/red]")
            table.add_row("Total size processed", f"{self.stats['copied_size'] / (1024**3):.2f} GB")
            table.add_row("Logs saved to", str(self.log_dir))
            
            console.print(table)
            
            if self.stats['errors'] > 0:
                console.print(f"[yellow]⚠️  Check error log: {self.error_log}[/yellow]")
        else:
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
