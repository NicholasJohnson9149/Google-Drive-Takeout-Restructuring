#!/usr/bin/env python3
"""
Utility script to verify reconstructed Google Drive structure
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.verifier import DriveVerifier
from app.core.logger import ProgressLogger


def main():
    parser = argparse.ArgumentParser(
        description="Verify reconstructed Google Drive structure"
    )
    
    parser.add_argument(
        'original',
        type=Path,
        help='Path to original extracted takeout directory'
    )
    parser.add_argument(
        'reconstructed',
        type=Path,
        help='Path to reconstructed Drive directory'
    )
    parser.add_argument(
        '--report',
        type=Path,
        help='Path to save verification report'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Validate paths
    if not args.original.exists():
        print(f"Error: Original path does not exist: {args.original}")
        return 1
    
    if not args.reconstructed.exists():
        print(f"Error: Reconstructed path does not exist: {args.reconstructed}")
        return 1
    
    # Create verifier with logger
    logger = ProgressLogger("verifier")
    verifier = DriveVerifier(logger=logger)
    
    print(f"Verifying reconstruction...")
    print(f"  Original: {args.original}")
    print(f"  Reconstructed: {args.reconstructed}")
    print("")
    
    # Run verification
    results = verifier.verify_reconstruction(args.original, args.reconstructed)
    
    # Generate report
    report = verifier.generate_verification_report(args.report)
    
    # Print summary
    print("\n" + "="*50)
    print("VERIFICATION RESULTS")
    print("="*50)
    
    if results['verified']:
        print("✅ PASSED - All files match")
    else:
        print("❌ FAILED - Issues found")
    
    print(f"\nFile Statistics:")
    print(f"  Original files: {results['total_original_files']}")
    print(f"  Reconstructed files: {results['total_reconstructed_files']}")
    print(f"  Original size: {results['total_size_original'] / (1024**3):.2f} GB")
    print(f"  Reconstructed size: {results['total_size_reconstructed'] / (1024**3):.2f} GB")
    
    if not results['verified']:
        print(f"\nIssues Found:")
        if results['missing_files']:
            print(f"  Missing files: {len(results['missing_files'])}")
            for file in results['missing_files'][:5]:
                print(f"    - {file}")
            if len(results['missing_files']) > 5:
                print(f"    ... and {len(results['missing_files']) - 5} more")
        
        if results['extra_files']:
            print(f"  Extra files: {len(results['extra_files'])}")
            for file in results['extra_files'][:5]:
                print(f"    - {file}")
            if len(results['extra_files']) > 5:
                print(f"    ... and {len(results['extra_files']) - 5} more")
        
        if results['size_mismatches']:
            print(f"  Size mismatches: {len(results['size_mismatches'])}")
        
        if results['hash_mismatches']:
            print(f"  Hash mismatches: {len(results['hash_mismatches'])}")
    
    if args.report:
        print(f"\nReport saved to: {args.report}")
    
    return 0 if results['verified'] else 1


if __name__ == "__main__":
    sys.exit(main())