from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable


def remove_file_directly(file_path: Path, callback: Optional[Callable] = None) -> bool:
    """Directly remove a file or directory WITHOUT using trash.
    
    This function is designed for temporary files that should be immediately deleted.
    Uses os.unlink() for files and shutil.rmtree() for directories to bypass
    Finder/trash system entirely, avoiding issues on exFAT and other external drives.
    
    Args:
        file_path: Path to file or directory to remove
        callback: Optional callback for logging
        
    Returns:
        True if successful, False otherwise
    """
    if not file_path.exists():
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Path does not exist: {file_path}'})
        return True  # Already gone, consider it success
    
    try:
        path_str = str(file_path.resolve())
        
        # Safety check - never delete system directories
        forbidden_paths = {'/System', '/Library', '/usr', '/bin', '/sbin', '/Applications', '/Users', '/Volumes'}
        if path_str in forbidden_paths or any(path_str == forbidden for forbidden in forbidden_paths):
            if callback:
                callback({'type': 'log', 'message': f'🚫 Refusing to delete system path: {path_str}'})
            return False
        
        # Additional safety - don't delete if path is too short (like / or /Users)
        if len(path_str) < 5:
            if callback:
                callback({'type': 'log', 'message': f'🚫 Path too short, refusing to delete: {path_str}'})
            return False
        
        # Check if it's a temporary file we created
        is_temp_file = any([
            'temp_extract_' in file_path.name,
            'takeout_upload_' in file_path.name,
            'takeout_temp' in str(file_path),
            str(file_path).startswith(tempfile.gettempdir())
        ])
        
        if not is_temp_file:
            if callback:
                callback({'type': 'log', 'message': f'⚠️ Not a temporary file, skipping direct deletion: {file_path.name}'})
            return False
        
        if file_path.is_file():
            # Use os.unlink for files (avoids Finder)
            os.unlink(file_path)
            if callback:
                callback({'type': 'log', 'message': f'🗑️ Directly removed file: {file_path.name}'})
            return True
            
        elif file_path.is_dir():
            # Use shutil.rmtree for directories (avoids Finder)
            shutil.rmtree(file_path, ignore_errors=False)
            if callback:
                callback({'type': 'log', 'message': f'🗑️ Directly removed directory: {file_path.name}'})
            return True
        else:
            if callback:
                callback({'type': 'log', 'message': f'⚠️ Unknown file type: {file_path.name}'})
            return False
            
    except PermissionError as e:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Permission denied removing {file_path.name}: {e}'})
        return False
    except OSError as e:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ OS error removing {file_path.name}: {e}'})
        return False
    except Exception as e:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Failed to remove {file_path.name}: {e}'})
        return False


def _is_external_drive(path: Path) -> bool:
    """Check if a path is on an external drive."""
    try:
        path_str = str(path.resolve())
        # Check if it's on /Volumes (macOS external drives)
        if path_str.startswith('/Volumes/'):
            return True
        # Check if it's on a Windows drive other than C:
        if len(path_str) > 1 and path_str[1] == ':' and path_str[0].upper() != 'C':
            return True
        return False
    except Exception:
        return False


def _get_file_system_type(path: Path) -> str:
    """Get the file system type for a given path."""
    try:
        import platform
        if platform.system().lower() == 'darwin':
            # Use df to get filesystem info on macOS
            result = subprocess.run(['df', '-T', str(path)], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and len(result.stdout.split('\n')) > 1:
                # Parse df output to get filesystem type
                fs_info = result.stdout.split('\n')[1].split()
                if len(fs_info) > 1:
                    return fs_info[1].lower()
    except Exception:
        pass
    return 'unknown'


def move_to_trash(file_path: Path, callback: Optional[Callable] = None) -> bool:
    """SAFE move file or directory to trash with proper error handling.

    On macOS uses Finder via AppleScript with intelligent fallbacks for external drives.
    On Windows tries send2trash then PowerShell. On Linux uses trash-put with fallbacks.
    For exFAT and other external drives, creates a .deleted folder on the same drive.
    """
    if not file_path.exists():
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Path does not exist: {file_path}'})
        return False

    try:
        import platform

        system = platform.system().lower()
        path_str = str(file_path.resolve())

        # Ensure we're not trying to delete system directories
        forbidden_paths = {'/System', '/Library', '/usr', '/bin', '/sbin', '/Applications'}
        if any(path_str.startswith(forbidden) for forbidden in forbidden_paths):
            if callback:
                callback({'type': 'log', 'message': f'🚫 Refusing to delete system path: {path_str}'})
            return False

        if system == 'darwin':  # macOS
            # Check if we're dealing with an external drive
            is_external = _is_external_drive(file_path)
            fs_type = _get_file_system_type(file_path) if is_external else 'unknown'
            
            # For external drives, especially exFAT, skip AppleScript and use direct approach
            if is_external and fs_type in ['exfat', 'msdos', 'ntfs']:
                if callback:
                    callback({'type': 'log', 'message': f'📀 Detected {fs_type.upper()} external drive, using safe deletion method'})
                
                # Create a .deleted folder on the same drive as the file
                try:
                    drive_root = file_path
                    while drive_root.parent != drive_root:
                        drive_root = drive_root.parent
                        if str(drive_root).startswith('/Volumes/'):
                            break
                    
                    deleted_folder = drive_root / '.deleted'
                    deleted_folder.mkdir(exist_ok=True)
                    
                    # Create unique name in .deleted folder
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    deleted_path = deleted_folder / f"{file_path.name}_{timestamp}"
                    counter = 1
                    while deleted_path.exists():
                        name = f"{file_path.stem}_{timestamp}_{counter}{file_path.suffix}"
                        deleted_path = deleted_folder / name
                        counter += 1
                    
                    shutil.move(str(file_path), str(deleted_path))
                    if callback:
                        callback({'type': 'log', 'message': f'🗑️ Moved to drive trash folder: {file_path.name}'})
                    return True
                    
                except Exception as e:
                    if callback:
                        callback({'type': 'log', 'message': f'⚠️ External drive trash failed, trying system trash: {e}'})
            
            # Try AppleScript for internal drives or as fallback
            try:
                escaped_path = path_str.replace("'", "'\"'\"'")
                applescript = f"tell application \"Finder\" to delete POSIX file '{escaped_path}'"
                result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    if callback:
                        callback({'type': 'log', 'message': f'🗑️ Moved to trash: {file_path.name}'})
                    return True
                else:
                    raise subprocess.CalledProcessError(result.returncode, 'osascript')
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # Final fallback to user's trash (for internal drives only)
                if not is_external:
                    try:
                        trash_path = Path.home() / ".Trash" / file_path.name
                        counter = 1
                        while trash_path.exists():
                            name = file_path.stem + f"_{counter}" + file_path.suffix
                            trash_path = Path.home() / ".Trash" / name
                            counter += 1
                        shutil.move(str(file_path), str(trash_path))
                        if callback:
                            callback({'type': 'log', 'message': f'🗑️ Moved to trash (fallback): {file_path.name}'})
                        return True
                    except Exception:
                        return False
                else:
                    if callback:
                        callback({'type': 'log', 'message': f'⚠️ Could not safely delete external drive file: {file_path.name}'})
                    return False

        elif system == 'windows':
            try:
                import send2trash  # type: ignore
                send2trash.send2trash(str(file_path))
                if callback:
                    callback({'type': 'log', 'message': f'🗑️ Moved to recycle bin: {file_path.name}'})
                return True
            except Exception:
                try:
                    subprocess.run([
                        'powershell', '-Command',
                        f'Add-Type -AssemblyName Microsoft\.VisualBasic; '
                        f'[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("{path_str}", '
                        f'[Microsoft.VisualBasic.FileIO.DeleteDirectoryOption]::DeleteAllContents, '
                        f'[Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)'
                    ], check=True, timeout=30)
                    if callback:
                        callback({'type': 'log', 'message': f'🗑️ Moved to recycle bin: {file_path.name}'})
                    return True
                except Exception:
                    return False

        elif system == 'linux':
            try:
                subprocess.run(['trash-put', path_str], check=True, timeout=30)
                if callback:
                    callback({'type': 'log', 'message': f'🗑️ Moved to trash: {file_path.name}'})
                return True
            except Exception:
                try:
                    trash_dir = Path.home() / ".local/share/Trash/files"
                    trash_dir.mkdir(parents=True, exist_ok=True)
                    trash_path = trash_dir / file_path.name
                    counter = 1
                    while trash_path.exists():
                        name = file_path.stem + f"_{counter}" + file_path.suffix
                        trash_path = trash_dir / name
                        counter += 1
                    shutil.move(str(file_path), str(trash_path))
                    if callback:
                        callback({'type': 'log', 'message': f'🗑️ Moved to trash: {file_path.name}'})
                    return True
                except Exception:
                    return False

        else:
            try:
                user_trash = Path.home() / ".trash"
                user_trash.mkdir(exist_ok=True)
                trash_path = user_trash / file_path.name
                counter = 1
                while trash_path.exists():
                    name = file_path.stem + f"_{counter}" + file_path.suffix
                    trash_path = user_trash / name
                    counter += 1
                shutil.move(str(file_path), str(trash_path))
                if callback:
                    callback({'type': 'log', 'message': f'🗑️ Moved to trash: {file_path.name}'})
                return True
            except Exception:
                return False

    except subprocess.TimeoutExpired:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Trash operation timed out for: {file_path.name}'})
        return False
    except Exception as e:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Trash operation failed: {e}'})
        return False


def cleanup_old_temp_dirs(base_path: Optional[Path] = None, callback: Optional[Callable] = None) -> None:
    """Clean up any old temp_extract_* directories in a base path.
    
    Uses direct deletion for temporary directories to avoid Finder/trash issues
    on external drives, especially exFAT formatted drives.
    """
    if base_path is None:
        # Default to common temp locations
        base_paths = [
            Path.home() / "Downloads",
            Path(tempfile.gettempdir()),
            Path.cwd()
        ]
    else:
        base_paths = [base_path]
    
    total_cleaned = 0
    
    for base_path in base_paths:
        if not base_path.exists():
            continue
            
        try:
            # Look for temp directories from takeout extraction
            patterns = ['temp_extract_*', 'takeout_upload_*', 'takeout_temp*']
            temp_dirs = []
            
            for pattern in patterns:
                temp_dirs.extend(list(base_path.glob(pattern)))
            
            if temp_dirs and callback:
                callback({'type': 'log', 'message': f'🧽 Found {len(temp_dirs)} temp directories to clean in {base_path}...'})
            
            for temp_dir in temp_dirs:
                try:
                    if temp_dir.is_dir():
                        # Use direct deletion for temp files to avoid exFAT issues
                        if remove_file_directly(temp_dir, callback):
                            total_cleaned += 1
                except Exception as e:
                    if callback:
                        callback({'type': 'log', 'message': f'⚠️ Could not clean {temp_dir.name}: {e}'})
        except Exception as e:
            if callback:
                callback({'type': 'log', 'message': f'⚠️ Temp cleanup scan failed for {base_path}: {e}'})
    
    if total_cleaned > 0 and callback:
        callback({'type': 'log', 'message': f'✅ Successfully cleaned {total_cleaned} temporary directories'})


def cleanup_system_temp_files(callback: Optional[Callable] = None) -> None:
    """Remove old temporary takeout directories (>24h) from the system temp dir.
    
    Uses direct deletion to avoid Finder/trash issues on any file system.
    """
    temp_dir = Path(tempfile.gettempdir())
    patterns = ["takeout_upload_*", "temp_extract_*", "takeout_temp*", "takeout_rebuild_*"]
    cleaned_count = 0
    
    for pattern in patterns:
        for item in temp_dir.glob(pattern):
            try:
                if item.is_dir() or item.is_file():
                    age = datetime.now().timestamp() - item.stat().st_mtime
                    # Remove files older than 24 hours
                    if age > 86400:
                        # Use os.unlink/shutil.rmtree directly to avoid exFAT issues
                        if item.is_file():
                            os.unlink(item)
                        else:
                            shutil.rmtree(item, ignore_errors=False)
                        cleaned_count += 1
                        if callback:
                            callback({'type': 'log', 'message': f'🧹 Removed old temp: {item.name}'})
            except PermissionError:
                # Skip files we don't have permission to delete
                continue
            except Exception as e:
                # Best-effort cleanup
                if callback:
                    callback({'type': 'log', 'message': f'⚠️ Could not remove {item.name}: {e}'})
    
    if cleaned_count > 0 and callback:
        callback({'type': 'log', 'message': f'✅ Cleaned {cleaned_count} old temporary files from system temp'})


