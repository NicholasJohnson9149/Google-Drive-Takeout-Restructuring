"""
Verification module for reconstructed Google Drive structure
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from .logger import ProgressLogger


class DriveVerifier:
    """Verifies the integrity and correctness of reconstructed Drive structure"""
    
    def __init__(self, logger: Optional[ProgressLogger] = None):
        self.logger = logger or ProgressLogger("verifier")
        self.verification_results: Dict[str, any] = {}
    
    def verify_reconstruction(self, original_path: Path, reconstructed_path: Path) -> Dict[str, any]:
        """
        Verify that the reconstructed structure matches the original
        
        Args:
            original_path: Path to original extracted Takeout data
            reconstructed_path: Path to reconstructed Drive structure
        
        Returns:
            Dictionary containing verification results
        """
        self.logger.info("Starting verification of reconstructed Drive structure")
        self.logger.status("verifying", "Verifying reconstructed files...")
        
        results = {
            'verified': False,
            'file_count_match': False,
            'missing_files': [],
            'extra_files': [],
            'size_mismatches': [],
            'hash_mismatches': [],
            'total_original_files': 0,
            'total_reconstructed_files': 0,
            'total_size_original': 0,
            'total_size_reconstructed': 0,
            'verification_errors': []
        }
        
        try:
            # Get file inventories
            self.logger.progress(10, operation="Scanning original files")
            original_files = self._get_file_inventory(original_path, normalize_paths=True)
            
            self.logger.progress(30, operation="Scanning reconstructed files")
            reconstructed_files = self._get_file_inventory(reconstructed_path, normalize_paths=False)
            
            results['total_original_files'] = len(original_files)
            results['total_reconstructed_files'] = len(reconstructed_files)
            results['total_size_original'] = sum(info['size'] for info in original_files.values())
            results['total_size_reconstructed'] = sum(info['size'] for info in reconstructed_files.values())
            
            self.logger.info(f"Original files: {results['total_original_files']}")
            self.logger.info(f"Reconstructed files: {results['total_reconstructed_files']}")
            
            # Check for missing and extra files
            self.logger.progress(50, operation="Comparing file lists")
            original_set = set(original_files.keys())
            reconstructed_set = set(reconstructed_files.keys())
            
            results['missing_files'] = list(original_set - reconstructed_set)
            results['extra_files'] = list(reconstructed_set - original_set)
            results['file_count_match'] = len(original_files) == len(reconstructed_files)
            
            if results['missing_files']:
                self.logger.warning(f"Missing {len(results['missing_files'])} files")
            if results['extra_files']:
                self.logger.warning(f"Found {len(results['extra_files'])} extra files")
            
            # Verify file contents for common files
            common_files = original_set & reconstructed_set
            self.logger.progress(70, operation="Verifying file contents")
            
            verified_count = 0
            for i, relative_path in enumerate(common_files):
                if i % 100 == 0:  # Update progress every 100 files
                    progress = 70 + (i / len(common_files)) * 20
                    self.logger.progress(progress, operation=f"Verifying file {i+1}/{len(common_files)}")
                
                original_info = original_files[relative_path]
                reconstructed_info = reconstructed_files[relative_path]
                
                # Check file sizes
                if original_info['size'] != reconstructed_info['size']:
                    results['size_mismatches'].append({
                        'file': relative_path,
                        'original_size': original_info['size'],
                        'reconstructed_size': reconstructed_info['size']
                    })
                    continue
                
                # For important files, verify content hash
                if self._should_verify_hash(relative_path):
                    if not self._verify_file_hash(
                        original_info['path'],  # Use actual file path from inventory
                        reconstructed_info['path']  # Use actual file path from inventory
                    ):
                        results['hash_mismatches'].append(relative_path)
                        continue
                
                verified_count += 1
            
            self.logger.progress(90, operation="Finalizing verification")
            
            # Determine overall verification status
            results['verified'] = (
                len(results['missing_files']) == 0 and
                len(results['extra_files']) == 0 and
                len(results['size_mismatches']) == 0 and
                len(results['hash_mismatches']) == 0
            )
            
            # Log summary
            if results['verified']:
                self.logger.success("✅ Verification PASSED - All files match")
            else:
                self.logger.warning("⚠️ Verification completed with issues")
                if results['missing_files']:
                    self.logger.warning(f"  - Missing files: {len(results['missing_files'])}")
                if results['extra_files']:
                    self.logger.warning(f"  - Extra files: {len(results['extra_files'])}")
                if results['size_mismatches']:
                    self.logger.warning(f"  - Size mismatches: {len(results['size_mismatches'])}")
                if results['hash_mismatches']:
                    self.logger.warning(f"  - Hash mismatches: {len(results['hash_mismatches'])}")
            
            self.logger.progress(100, operation="Verification complete")
            
        except Exception as e:
            self.logger.error(f"Verification failed: {str(e)}")
            results['verification_errors'].append(str(e))
        
        self.verification_results = results
        return results
    
    def _normalize_takeout_path(self, path_str: str) -> str:
        """
        Normalize Takeout path by removing Drive/ prefix
        e.g., 'Drive/document.txt' -> 'document.txt'
        """
        path = Path(path_str)
        if path.parts and path.parts[0] == 'Drive':
            # Remove the 'Drive' prefix
            return str(Path(*path.parts[1:]))
        return path_str
    
    def _get_file_inventory(self, base_path: Path, normalize_paths: bool = False) -> Dict[str, Dict]:
        """Get inventory of all files in a directory tree"""
        inventory = {}
        
        if not base_path.exists():
            return inventory
        
        for file_path in base_path.rglob('*'):
            if file_path.is_file():
                try:
                    relative_path = file_path.relative_to(base_path)
                    path_key = str(relative_path)
                    
                    # Normalize Takeout paths if requested
                    if normalize_paths:
                        path_key = self._normalize_takeout_path(path_key)
                    
                    stat = file_path.stat()
                    
                    inventory[path_key] = {
                        'size': stat.st_size,
                        'mtime': stat.st_mtime,
                        'path': file_path
                    }
                except Exception as e:
                    self.logger.warning(f"Could not process file {file_path}: {str(e)}")
        
        return inventory
    
    def _should_verify_hash(self, relative_path: str) -> bool:
        """Determine if a file should have its hash verified"""
        # Skip hash verification for very large files or certain file types
        # to speed up verification process
        skip_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.zip', '.iso'}
        skip_large_files = True  # Skip files larger than 100MB for performance
        
        path = Path(relative_path)
        if path.suffix.lower() in skip_extensions:
            return False
        
        # For now, only verify smaller important files
        return True
    
    def _verify_file_hash(self, original_file: Path, reconstructed_file: Path) -> bool:
        """Verify that two files have the same content hash"""
        try:
            # For performance, only hash smaller files
            if original_file.stat().st_size > 100 * 1024 * 1024:  # 100MB
                return True  # Skip hash verification for large files
            
            original_hash = self._calculate_file_hash(original_file)
            reconstructed_hash = self._calculate_file_hash(reconstructed_file)
            
            return original_hash == reconstructed_hash
            
        except Exception as e:
            self.logger.warning(f"Hash verification failed for {original_file.name}: {str(e)}")
            return False
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file"""
        hash_sha256 = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.warning(f"Could not calculate hash for {file_path}: {str(e)}")
            return ""
    
    def generate_verification_report(self, output_path: Optional[Path] = None) -> str:
        """Generate a detailed verification report"""
        if not self.verification_results:
            return "No verification results available"
        
        results = self.verification_results
        
        report = f"""
Google Drive Takeout Verification Report
========================================

Overall Status: {'PASSED' if results['verified'] else 'FAILED'}

File Statistics:
- Original files: {results['total_original_files']}
- Reconstructed files: {results['total_reconstructed_files']}
- Original total size: {results['total_size_original'] / (1024**3):.2f} GB
- Reconstructed total size: {results['total_size_reconstructed'] / (1024**3):.2f} GB

Issues Found:
- Missing files: {len(results['missing_files'])}
- Extra files: {len(results['extra_files'])}
- Size mismatches: {len(results['size_mismatches'])}
- Hash mismatches: {len(results['hash_mismatches'])}
"""
        
        if results['missing_files']:
            report += "\nMissing Files:\n"
            for file in results['missing_files'][:10]:  # Show first 10
                report += f"  - {file}\n"
            if len(results['missing_files']) > 10:
                report += f"  ... and {len(results['missing_files']) - 10} more\n"
        
        if results['extra_files']:
            report += "\nExtra Files:\n"
            for file in results['extra_files'][:10]:  # Show first 10
                report += f"  - {file}\n"
            if len(results['extra_files']) > 10:
                report += f"  ... and {len(results['extra_files']) - 10} more\n"
        
        if output_path:
            output_path.write_text(report)
            self.logger.info(f"Verification report saved to {output_path}")
        
        return report
