"""
Command-line interface for Google Drive Takeout Consolidator
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional
import logging

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.logging import RichHandler

from app.core.rebuilder_v2 import SafeTakeoutReconstructor
from app.core.duplicate_checker import DuplicateStrategy
from app.core.extractor import TakeoutExtractor
from app.core.verifier import DriveVerifier
from app.config import config, load_config


console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )


def handle_extract(args: argparse.Namespace) -> int:
    """Handle extraction of takeout zip files"""
    extractor = TakeoutExtractor()
    
    # Find or use specified zip files
    if args.input.is_file() and args.input.suffix == '.zip':
        zip_files = [args.input]
    elif args.input.is_dir():
        zip_files = extractor.find_takeout_zips(args.input)
        if not zip_files:
            console.print(f"[red]✗[/red] No valid ZIP files found in {args.input}", style="red")
            return 1
    else:
        console.print(f"[red]✗[/red] Invalid input: {args.input}", style="red")
        return 1
    
    output_dir = args.output or Path.cwd() / "extracted"
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Extracting takeout files...", total=100)
        
        def update_progress(data):
            if isinstance(data, dict):
                message = data.get('message', '')
                percent = data.get('percent', 0)
                progress.update(task, description=message, completed=percent)
            else:
                # Fallback for old-style calls
                progress.update(task, description=str(data), completed=0)
        
        extractor.logger.set_progress_callback(update_progress)
        result_path = extractor.extract_zip_files(zip_files, output_dir)
        
    if result_path:
        console.print(f"[green]✓[/green] Extraction completed successfully to {result_path}")
        return 0
    else:
        console.print("[red]✗[/red] Extraction failed", style="red")
        return 1


def handle_rebuild(args: argparse.Namespace) -> int:
    """Handle rebuilding of Drive structure"""
    if not args.force and not args.dry_run:
        console.print("[yellow]Warning:[/yellow] Running without --dry-run will modify files.")
        console.print("Use --dry-run to preview changes or --force to skip this prompt.")
        
        if not console.input("Continue? [y/N]: ").lower().startswith('y'):
            console.print("Operation cancelled")
            return 0
    
    # Determine duplicate strategy based on verification level
    duplicate_strategy = DuplicateStrategy.VERIFY if args.verify else DuplicateStrategy.HASH
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Rebuilding Drive structure...", total=100)
        
        def update_progress(data):
            if isinstance(data, dict):
                if data.get('type') == 'progress':
                    message = data.get('operation', 'Processing...')
                    percent = data.get('percent', 0)
                    progress.update(task, description=message, completed=percent)
                elif data.get('type') == 'status':
                    message = data.get('message', '')
                    progress.update(task, description=message)
        
        reconstructor = SafeTakeoutReconstructor(
            takeout_path=args.input,
            export_path=args.output,
            dry_run=args.dry_run,
            duplicate_strategy=duplicate_strategy,
            progress_callback=update_progress
        )
        
        try:
            success = reconstructor.rebuild_drive_structure(verify_copies=args.verify)
            
            if success:
                console.print("\n[bold green]✅ Drive reconstruction completed successfully![/bold green]")
            else:
                console.print("\n[bold yellow]⚠️ Drive reconstruction completed with errors[/bold yellow]")
            
            # Print final statistics
            stats = reconstructor.stats
            console.print(f"\nReconstruction Statistics:")
            console.print(f"  Total files processed: {stats.total_files}")
            console.print(f"  Files copied: {stats.copied_files}")
            console.print(f"  Duplicates skipped: {stats.skipped_duplicates}")
            console.print(f"  Metadata skipped: {stats.skipped_metadata}")
            console.print(f"  Errors: {stats.errors}")
            console.print(f"  Total size: {stats.total_size / (1024**3):.2f} GB")
            console.print(f"  Copied size: {stats.copied_size / (1024**3):.2f} GB")
            
            if reconstructor.errors:
                console.print(f"\n[yellow]Warning: {len(reconstructor.errors)} errors occurred during processing[/yellow]")
                console.print("Check the error log for details.")
            
            if args.dry_run:
                console.print("\n[yellow]This was a dry run. No files were actually modified.[/yellow]")
            else:
                console.print(f"Output saved to: {args.output}")
                
            return 0 if success else 1
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            reconstructor.cancel()
            return 1
        except Exception as e:
            console.print(f"\n[bold red]❌ Error during reconstruction: {str(e)}[/bold red]")
            return 1
        finally:
            reconstructor.close()


def handle_verify(args: argparse.Namespace) -> int:
    """Handle verification of reconstructed structure"""
    verifier = DriveVerifier()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Verifying reconstruction...", total=100)
        
        def update_progress(data):
            if isinstance(data, dict):
                message = data.get('message', '')
                percent = data.get('percent', 0)
                progress.update(task, description=message, completed=percent)
            else:
                # Fallback for old-style calls
                progress.update(task, description=str(data), completed=0)
        
        verifier.logger.set_progress_callback(update_progress)
        result = verifier.verify_reconstruction(args.source, args.dest)
    
    if result['verified']:
        console.print("[green]✓[/green] Verification passed")
        console.print(f"  Files verified: {result['total_original_files']}")
        console.print(f"  Total size: {result['total_size_original'] / (1024**3):.2f} GB")
    else:
        console.print("[red]✗[/red] Verification failed", style="red")
        if result['missing_files']:
            console.print(f"  Missing files: {len(result['missing_files'])}")
        if result['extra_files']:
            console.print(f"  Extra files: {len(result['extra_files'])}")
        if result['size_mismatches']:
            console.print(f"  Size mismatches: {len(result['size_mismatches'])}")
        if result['hash_mismatches']:
            console.print(f"  Hash mismatches: {len(result['hash_mismatches'])}")
    
    return 0 if result['verified'] else 1


def main() -> int:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Google Drive Takeout Consolidator - Rebuild your Drive structure from takeout files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview reconstruction (dry run)
  %(prog)s rebuild ~/Downloads/Takeout ~/Desktop/MyDrive --dry-run
  
  # Execute reconstruction
  %(prog)s rebuild ~/Downloads/Takeout ~/Desktop/MyDrive --force
  
  # Extract takeout zip first
  %(prog)s extract ~/Downloads/takeout.zip ~/Downloads/Takeout
  
  # Verify reconstruction
  %(prog)s verify ~/Downloads/Takeout ~/Desktop/MyDrive
        """
    )
    
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--config', type=str,
                        help='Path to configuration file')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract',
                                           help='Extract takeout zip files')
    extract_parser.add_argument('input', type=Path,
                                help='Path to takeout zip file')
    extract_parser.add_argument('--output', '-o', type=Path,
                                help='Output directory (default: ./extracted)')
    
    # Rebuild command
    rebuild_parser = subparsers.add_parser('rebuild',
                                           help='Rebuild Drive structure from extracted takeout')
    rebuild_parser.add_argument('input', type=Path,
                                help='Path to extracted takeout directory')
    rebuild_parser.add_argument('output', type=Path,
                                help='Output directory for reconstructed Drive')
    rebuild_parser.add_argument('--dry-run', '-n', action='store_true',
                                help='Preview changes without modifying files')
    rebuild_parser.add_argument('--force', '-f', action='store_true',
                                help='Skip confirmation prompt')
    rebuild_parser.add_argument('--verify', action='store_true',
                                help='Verify file copies (slower but safer)')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify',
                                          help='Verify reconstructed Drive structure')
    verify_parser.add_argument('source', type=Path,
                               help='Path to original takeout directory')
    verify_parser.add_argument('dest', type=Path,
                               help='Path to reconstructed Drive directory')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Load configuration
    if args.config:
        config = load_config(args.config)
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Handle commands
    if args.command == 'extract':
        return handle_extract(args)
    elif args.command == 'rebuild':
        return handle_rebuild(args)
    elif args.command == 'verify':
        return handle_verify(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())