"""
Duplicate Checker - Handles detection and management of duplicate files
"""
from __future__ import annotations

import hashlib
import filecmp
from pathlib import Path
from typing import Dict, Optional, Set
from enum import Enum
from dataclasses import dataclass
import logging


class DuplicateStrategy(Enum):
    """Strategy for handling duplicate detection"""
    FAST = "fast"          # Size-based only
    HASH = "hash"          # Size + SHA256 hash
    VERIFY = "verify"      # Size + hash + content comparison


@dataclass
class DuplicateResult:
    """Result of duplicate checking"""
    is_duplicate: bool
    reason: str
    existing_path: Optional[Path] = None
    hash_computed: bool = False
    hash_value: Optional[str] = None


class DuplicateChecker:
    """Responsible for detecting and managing duplicate files"""
    
    def __init__(self, strategy: DuplicateStrategy = DuplicateStrategy.HASH):
        self.strategy = strategy
        self.file_hashes: Dict[str, Set[Path]] = {}  # hash -> set of paths
        self.size_cache: Dict[int, Set[Path]] = {}   # size -> set of paths  
        self.logger = logging.getLogger(__name__)
    
    def is_duplicate(self, source_path: Path, dest_path: Path) -> DuplicateResult:
        """
        Check if a file is a duplicate of an existing file
        
        Args:
            source_path: Path to the source file
            dest_path: Path where file would be copied
            
        Returns:
            DuplicateResult indicating if file is duplicate and why
        """
        # If destination doesn't exist, not a duplicate
        if not dest_path.exists():
            return DuplicateResult(
                is_duplicate=False,
                reason="Destination does not exist"
            )
        
        try:
            source_size = source_path.stat().st_size
            dest_size = dest_path.stat().st_size
            
            # Different sizes = not duplicate
            if source_size != dest_size:
                return DuplicateResult(
                    is_duplicate=False,
                    reason=f"Different sizes: source={source_size}, dest={dest_size}"
                )
            
            # Same size, now check based on strategy
            if self.strategy == DuplicateStrategy.FAST:
                return DuplicateResult(
                    is_duplicate=True,
                    reason="Same size (fast mode)",
                    existing_path=dest_path
                )
            
            elif self.strategy == DuplicateStrategy.HASH:
                return self._check_hash_duplicate(source_path, dest_path)
            
            elif self.strategy == DuplicateStrategy.VERIFY:
                # First try hash, then full comparison if needed
                hash_result = self._check_hash_duplicate(source_path, dest_path)
                if hash_result.is_duplicate:
                    # Double-check with full file comparison for critical files
                    if source_size > 100 * 1024 * 1024:  # 100MB+
                        content_match = filecmp.cmp(source_path, dest_path, shallow=False)
                        return DuplicateResult(
                            is_duplicate=content_match,
                            reason=f"Hash match + content verification: {content_match}",
                            existing_path=dest_path,
                            hash_computed=True,
                            hash_value=hash_result.hash_value
                        )
                return hash_result
            
        except OSError as e:
            self.logger.error(f"Error checking duplicate {source_path} -> {dest_path}: {e}")
            return DuplicateResult(
                is_duplicate=False,
                reason=f"Error during check: {e}"
            )
    
    def _check_hash_duplicate(self, source_path: Path, dest_path: Path) -> DuplicateResult:
        """Check for duplicates using SHA256 hash comparison"""
        try:
            source_hash = self._get_file_hash(source_path)
            dest_hash = self._get_file_hash(dest_path)
            
            is_dup = source_hash == dest_hash
            
            return DuplicateResult(
                is_duplicate=is_dup,
                reason=f"Hash comparison: {'match' if is_dup else 'different'}",
                existing_path=dest_path if is_dup else None,
                hash_computed=True,
                hash_value=source_hash
            )
            
        except Exception as e:
            self.logger.error(f"Error computing hashes for {source_path}: {e}")
            return DuplicateResult(
                is_duplicate=False,
                reason=f"Hash computation failed: {e}"
            )
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file"""
        # Check cache first
        file_key = f"{file_path}:{file_path.stat().st_mtime}"
        
        hasher = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                # Read in chunks for memory efficiency
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            
            hash_value = hasher.hexdigest()
            
            # Cache the hash
            if hash_value not in self.file_hashes:
                self.file_hashes[hash_value] = set()
            self.file_hashes[hash_value].add(file_path)
            
            return hash_value
            
        except OSError as e:
            self.logger.error(f"Error reading file for hash {file_path}: {e}")
            raise
    
    def register_file(self, file_path: Path, size: int):
        """Register a file in the duplicate tracking system"""
        if size not in self.size_cache:
            self.size_cache[size] = set()
        self.size_cache[size].add(file_path)
    
    def get_potential_duplicates_by_size(self, size: int) -> Set[Path]:
        """Get all files with the same size (potential duplicates)"""
        return self.size_cache.get(size, set())
    
    def clear_cache(self):
        """Clear internal caches"""
        self.file_hashes.clear()
        self.size_cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about duplicate detection"""
        return {
            'unique_hashes': len(self.file_hashes),
            'unique_sizes': len(self.size_cache),
            'total_files_by_hash': sum(len(paths) for paths in self.file_hashes.values()),
            'total_files_by_size': sum(len(paths) for paths in self.size_cache.values())
        }