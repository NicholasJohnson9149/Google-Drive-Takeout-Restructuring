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
        
        # Match Takeout folders with various naming patterns
        # Matches: Takeout, Takeout-1, Takeout 2, Takeout_3, etc.
        self.takeout_pattern = re.compile(r'^Takeout[\s\-_]?\d*$', re.IGNORECASE)
        
        # The Drive folder that contains the actual content
        self.drive_pattern = re.compile(r'^Drive$', re.IGNORECASE)
        
        # Patterns for files to skip entirely
        self.skip_file_patterns = [
            re.compile(r'\.json$'),  # Will be checked for metadata later
        ]
    
    def normalize_path(self, relative_path: Path, is_metadata: bool = False) -> PathTransformation:
        """
        Transform a relative path from takeout structure to clean destination
        
        Handles structures like:
        - Takeout/Drive/folder/file.txt → folder/file.txt
        - Takeout-1/Drive/folder/file.txt → folder/file.txt
        - Takeout 2/Drive/folder/file.txt → folder/file.txt
        
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
        
        # Process path parts to remove Takeout wrapper and Drive folder
        clean_parts = []
        transformations = []
        found_takeout = False
        found_drive = False
        start_preserving = False
        
        for i, part in enumerate(original_parts):
            # Check if this is a Takeout folder
            if self.takeout_pattern.match(part) and not found_takeout:
                transformations.append(f"Removed Takeout folder: '{part}'")
                found_takeout = True
                continue
            
            # Check if this is the Drive folder (should come after Takeout)
            if self.drive_pattern.match(part) and found_takeout and not found_drive:
                transformations.append(f"Removed Drive folder: '{part}'")
                found_drive = True
                start_preserving = True
                continue
            
            # If we haven't found Takeout yet, or we've found both Takeout and Drive,
            # preserve the folder structure
            if not found_takeout or start_preserving:
                clean_parts.append(part)
        
        # Handle edge case: files directly in Takeout folder (not in Drive)
        # If we found Takeout but not Drive, preserve everything after Takeout
        if found_takeout and not found_drive and len(original_parts) > 1:
            # Find index of Takeout folder
            takeout_idx = next((i for i, part in enumerate(original_parts) 
                              if self.takeout_pattern.match(part)), -1)
            if takeout_idx >= 0 and takeout_idx + 1 < len(original_parts):
                clean_parts = list(original_parts[takeout_idx + 1:])
                transformations.append("Preserved structure after Takeout (no Drive folder found)")
        
        # If no parts remain, skip the file
        if not clean_parts:
            return PathTransformation(
                original_path=relative_path,
                clean_path=None,
                transformation_log=f"No valid path after transformation: {' → '.join(transformations)}",
                should_skip=True
            )
        
        # Create clean relative path
        clean_relative_path = Path(*clean_parts)
        final_path = self.dest_dir / clean_relative_path
        
        # Build transformation log
        if transformations:
            log = f"Path: {'/'.join(original_parts)} → {'/'.join(clean_parts)} ({'; '.join(transformations)})"
        else:
            log = f"No transformation needed: {relative_path}"
        
        return PathTransformation(
            original_path=relative_path,
            clean_path=final_path,
            transformation_log=log,
            should_skip=False
        )
    
    def add_skip_pattern(self, pattern: str):
        """Add a new pattern for files to skip"""
        self.skip_file_patterns.append(re.compile(pattern, re.IGNORECASE))
    
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