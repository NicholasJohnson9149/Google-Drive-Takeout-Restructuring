from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable


def move_to_trash(file_path: Path, callback: Optional[Callable] = None) -> bool:
    """SAFE move file or directory to trash with proper error handling.

    On macOS uses Finder via AppleScript with a safe fallback. On Windows tries
    send2trash then PowerShell. On Linux uses trash-put with fallbacks.
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


def cleanup_old_temp_dirs(base_path: Path, callback: Optional[Callable] = None) -> None:
    """Clean up any old temp_extract_* directories in a base path."""
    try:
        temp_dirs = list(base_path.glob('temp_extract_*'))
        if temp_dirs and callback:
            callback({'type': 'log', 'message': f'🧽 Cleaning up {len(temp_dirs)} old temp directories...'})
        for temp_dir in temp_dirs:
            try:
                if temp_dir.is_dir():
                    move_to_trash(temp_dir, callback)
            except Exception as e:
                if callback:
                    callback({'type': 'log', 'message': f'⚠️ Could not clean {temp_dir.name}: {e}'})
    except Exception as e:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Temp cleanup scan failed: {e}'})


def cleanup_system_temp_files() -> None:
    """Remove old temporary takeout upload directories (>24h) from the system temp dir."""
    temp_dir = Path(tempfile.gettempdir())
    for item in temp_dir.glob("takeout_upload_*"):
        try:
            if item.is_dir():
                age = datetime.now().timestamp() - item.stat().st_mtime
                if age > 86400:
                    shutil.rmtree(item)
        except Exception:
            # Best-effort cleanup
            pass


