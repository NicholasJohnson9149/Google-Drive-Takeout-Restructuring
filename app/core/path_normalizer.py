"""
Path Normalizer - Handles cleaning and transforming Takeout paths
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class PathTransformation:
    """Result of path transformation"""
    original_path: Path
    clean_path: Optional[Path]
    transformation_log: str
    should_skip: bool = False


class PathNormalizer:
    """Responsible for cleaning Google Takeout folder structures"""
    
    def __init__(self, dest_dir: Path):
        self.dest_dir = Path(dest_dir)
        
        # Configurable transformation rules
        self.skip_patterns = [
            re.compile(r'^Takeout.*', re.IGNORECASE),  # Any folder starting with "Takeout"
            re.compile(r'^Drive$', re.IGNORECASE),     # Exact "Drive" folder
        ]
        
        # Patterns for files to skip entirely
        self.skip_file_patterns = [
            re.compile(r'\.json$'),  # Will be checked for metadata later
        ]
    
    def normalize_path(self, relative_path: Path, is_metadata: bool = False) -> PathTransformation:
        """
        Transform a relative path from takeout structure to clean destination
        
        Args:
            relative_path: Path relative to the source directory
            is_metadata: Whether this is a Google metadata file
            
        Returns:
            PathTransformation with the result
        """
        original_parts = list(relative_path.parts)
        
        # Skip metadata files entirely
        if is_metadata:
            return PathTransformation(
                original_path=relative_path,
                clean_path=None,
                transformation_log=f"Skipped metadata file: {relative_path}",
                should_skip=True
            )
        
        # Clean path parts
        clean_parts = []
        transformations = []
        
        for part in original_parts:
            # Check if this part should be skipped
            should_skip_part = any(pattern.match(part) for pattern in self.skip_patterns)
            
            if should_skip_part:
                transformations.append(f"Removed '{part}'")
            else:
                clean_parts.append(part)
        
        # If no parts remain, skip the file
        if not clean_parts:
            return PathTransformation(
                original_path=relative_path,
                clean_path=None,
                transformation_log=f"All parts removed, skipping: {' → '.join(transformations)}",
                should_skip=True
            )
        
        # Create clean relative path
        clean_relative_path = Path(*clean_parts)
        final_path = self.dest_dir / clean_relative_path
        
        # Build transformation log
        if transformations:
            log = f"Transformed: {'/'.join(original_parts)} → {'/'.join(clean_parts)} ({'; '.join(transformations)})"
        else:
            log = f"No transformation needed: {relative_path}"
        
        return PathTransformation(
            original_path=relative_path,
            clean_path=final_path,
            transformation_log=log,
            should_skip=False
        )
    
    def add_skip_pattern(self, pattern: str):
        """Add a new pattern for folders to skip"""
        self.skip_patterns.append(re.compile(pattern, re.IGNORECASE))
    
    def test_transformations(self, test_paths: List[str]) -> List[PathTransformation]:
        """
        Test path transformations with a list of sample paths
        Useful for debugging and validation
        """
        results = []
        for path_str in test_paths:
            path = Path(path_str)
            result = self.normalize_path(path)
            results.append(result)
        return results