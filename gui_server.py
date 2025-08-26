#!/usr/bin/env python3
"""
Google Drive Takeout Consolidator - Web GUI
FastAPI server with HTMX interface for cross-platform GUI functionality
"""

import os
import asyncio
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json
import threading
import uuid

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from main_enhanced import SafeTakeoutReconstructor

def move_to_trash(file_path: Path, callback=None):
    """SAFE move file or directory to trash with proper error handling"""
    if not file_path.exists():
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Path does not exist: {file_path}'})
        return False
        
    try:
        import platform
        import subprocess
        import time
        
        system = platform.system().lower()
        path_str = str(file_path.resolve())  # Use absolute path
        
        # Ensure we're not trying to delete system directories
        forbidden_paths = {'/System', '/Library', '/usr', '/bin', '/sbin', '/Applications'}
        if any(path_str.startswith(forbidden) for forbidden in forbidden_paths):
            if callback:
                callback({'type': 'log', 'message': f'🚫 Refusing to delete system path: {path_str}'})
            return False
        
        if system == 'darwin':  # macOS - SAFER VERSION
            # Use osascript for safer trash operations on macOS
            try:
                # Quote the path properly to handle spaces and special characters
                escaped_path = path_str.replace("'", "'\"'\"'")
                applescript = f"tell application \"Finder\" to delete POSIX file '{escaped_path}'"
                
                result = subprocess.run([
                    'osascript', '-e', applescript
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    if callback:
                        callback({'type': 'log', 'message': f'🗑️ Moved to trash: {file_path.name}'})
                    return True
                else:
                    raise subprocess.CalledProcessError(result.returncode, 'osascript')
                    
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # Fallback to mv if AppleScript fails
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
                except Exception as mv_error:
                    raise mv_error
                    
        elif system == 'windows':
            # Windows - use safer method
            try:
                import send2trash
                send2trash.send2trash(str(file_path))
                if callback:
                    callback({'type': 'log', 'message': f'🗑️ Moved to recycle bin: {file_path.name}'})
                return True
            except ImportError:
                # Fallback to PowerShell if send2trash not available
                subprocess.run([
                    'powershell', '-Command', 
                    f'Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("{path_str}", [Microsoft.VisualBasic.FileIO.DeleteDirectoryOption]::DeleteAllContents, [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)'
                ], check=True, timeout=30)
                if callback:
                    callback({'type': 'log', 'message': f'🗑️ Moved to recycle bin: {file_path.name}'})
                return True
                
        elif system == 'linux':
            # Linux - safer trash handling
            try:
                subprocess.run(['trash-put', path_str], check=True, timeout=30)
                if callback:
                    callback({'type': 'log', 'message': f'🗑️ Moved to trash: {file_path.name}'})
                return True
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Create safe trash directory in user home
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
        else:
            # Unknown system - safe removal to user trash
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
            
    except subprocess.TimeoutExpired:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Trash operation timed out for: {file_path.name}'})
        return False
    except Exception as e:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Trash operation failed: {e}'})
        return False

def cleanup_old_temp_dirs(base_path: Path, callback=None):
    """Clean up any old temp_extract directories"""
    try:
        temp_dirs = list(base_path.glob('temp_extract_*'))
        if temp_dirs:
            if callback:
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

# Initialize FastAPI app
app = FastAPI(title="Google Drive Takeout Consolidator", version="1.0.0")

# Startup cleanup - SAFE VERSION
@app.on_event("startup") 
async def startup_cleanup():
    """Clean up any leftover temp files from previous runs - SAFE VERSION"""
    try:
        # ONLY check common safe locations, NOT all volumes
        safe_locations = [
            Path.home() / "Desktop",
            Path.home() / "Downloads", 
            Path("/tmp"),
            Path(os.getcwd())  # Current working directory only
        ]
        
        for location in safe_locations:
            if location.exists() and location.is_dir():
                try:
                    cleanup_old_temp_dirs(location, None)
                except Exception as e:
                    print(f"Safe cleanup warning for {location}: {e}")
                    
    except Exception as e:
        print(f"Startup cleanup warning: {e}")
        
    print("🧹 Safe startup cleanup completed")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global state for GUI operations
class GUIState:
    def __init__(self):
        self.active_operations: Dict[str, Dict] = {}
        self.pending_prompts: Dict[str, Dict] = {}  # operation_id -> prompt info
        self.progress_logs: Dict[str, List[Dict]] = {}
        
    def create_operation(self, operation_id: str, operation_type: str) -> None:
        """Create a new operation tracking entry"""
        self.ensure_attributes()
        
        self.active_operations[operation_id] = {
            'id': operation_id,
            'type': operation_type,
            'status': 'started',
            'progress': 0,
            'current_file': '',
            'start_time': datetime.now().isoformat(),
            'stats': {},
            'last_save': datetime.now().isoformat()
        }
        self.last_operation_id = operation_id
        self.save_state()
        self.progress_logs[operation_id] = []
    
    def update_operation(self, operation_id: str, update_data: Dict) -> None:
        """Update operation progress"""
        if operation_id in self.active_operations:
            # Update last activity timestamp for hang detection
            now = datetime.now()
            update_data['last_activity'] = now.isoformat()
            
            self.active_operations[operation_id].update(update_data)
            
            # Add to progress log
            log_entry = {
                'timestamp': now.isoformat(),
                'message': update_data.get('message', ''),
                'progress': update_data.get('progress_percent', 0),
                'current_file': update_data.get('current_file', '')
            }
            self.progress_logs[operation_id].append(log_entry)
            
            # Keep only last 100 log entries
            if len(self.progress_logs[operation_id]) > 100:
                self.progress_logs[operation_id] = self.progress_logs[operation_id][-100:]
                
            # Save state periodically (every 10 seconds) or on important updates
            last_save_str = self.active_operations[operation_id].get('last_save', now.isoformat())
            last_save = datetime.fromisoformat(last_save_str)
            
            # Save if it's been 10+ seconds or if it's a status change
            should_save = (
                (now - last_save).total_seconds() > 10 or
                'status' in update_data or
                update_data.get('progress_percent', 0) % 5 == 0  # Every 5% progress
            )
            
            if should_save:
                self.active_operations[operation_id]['last_save'] = now.isoformat()
                self.save_state()
    
    def check_for_hung_operations(self, timeout_minutes: int = 10) -> List[str]:
        """Check for operations that haven't updated in specified timeout period"""
        hung_operations = []
        now = datetime.now()
        
        for op_id, operation in self.active_operations.items():
            # Skip completed/failed operations
            if operation.get('status') in ['completed', 'failed', 'cancelled']:
                continue
                
            # Check last activity timestamp
            last_activity_str = operation.get('last_activity', operation.get('start_time'))
            if last_activity_str:
                try:
                    last_activity = datetime.fromisoformat(last_activity_str)
                    minutes_since_activity = (now - last_activity).total_seconds() / 60
                    
                    if minutes_since_activity > timeout_minutes:
                        hung_operations.append(op_id)
                        print(f"⚠️ Operation {op_id} appears hung - no activity for {minutes_since_activity:.1f} minutes")
                except (ValueError, TypeError):
                    # If we can't parse the timestamp, consider it potentially hung
                    hung_operations.append(op_id)
                    
        return hung_operations
    
    def mark_operation_as_hung(self, operation_id: str) -> None:
        """Mark an operation as potentially hung"""
        if operation_id in self.active_operations:
            self.active_operations[operation_id].update({
                'status': 'hung',
                'message': 'Operation appears to have hung - no progress updates received',
                'hung_detected_at': datetime.now().isoformat()
            })
    
    def save_state(self):
        """Save current state to disk for persistence across restarts"""
        try:
            # Ensure attributes exist (for existing instances)
            if not hasattr(self, 'last_operation_id'):
                self.last_operation_id = None
            if not hasattr(self, 'last_settings'):
                self.last_settings = {}
            if not hasattr(self, 'session_data'):
                self.session_data = {}
                
            state_data = {
                'active_operations': self.active_operations,
                'progress_logs': self.progress_logs,
                'last_operation_id': self.last_operation_id,
                'last_settings': self.last_settings,
                'session_data': self.session_data,
                'timestamp': datetime.now().isoformat()
            }
            
            import pickle
            with open(self.state_file, 'wb') as f:
                pickle.dump(state_data, f)
                
        except Exception as e:
            print(f"Warning: Could not save state: {e}")
    
    def load_state(self):
        """Load persistent state from disk"""
        # Ensure attributes exist first
        if not hasattr(self, 'last_operation_id'):
            self.last_operation_id = None
        if not hasattr(self, 'last_settings'):
            self.last_settings = {}
        if not hasattr(self, 'session_data'):
            self.session_data = {}
            
        try:
            if self.state_file.exists():
                import pickle
                with open(self.state_file, 'rb') as f:
                    state_data = pickle.load(f)
                
                self.active_operations = state_data.get('active_operations', {})
                self.progress_logs = state_data.get('progress_logs', {})
                self.last_operation_id = state_data.get('last_operation_id')
                self.last_settings = state_data.get('last_settings', {})
                self.session_data = state_data.get('session_data', {})
                
                # Check if we have a recent active operation (within last 24 hours)
                recent_active = None
                for op_id, op_data in self.active_operations.items():
                    if op_data.get('status') in ['processing', 'consolidating', 'extracting']:
                        start_time = datetime.fromisoformat(op_data.get('start_time', datetime.now().isoformat()))
                        if (datetime.now() - start_time).total_seconds() < 86400:  # 24 hours
                            recent_active = op_id
                            break
                
                if recent_active:
                    self.last_operation_id = recent_active
                    print(f"\n✅ Restored operation state: {recent_active}")
                else:
                    print("\n✅ Loaded saved state successfully")
                    
        except Exception as e:
            print(f"Warning: Could not load state: {e}")
            # Initialize with empty state if loading fails
            self.active_operations = {}
            self.progress_logs = {}
            self.last_operation_id = None
            self.last_settings = {}
            self.session_data = {}
    
    def update_last_settings(self, settings: Dict):
        """Update and persist the last used settings"""
        if not hasattr(self, 'last_settings'):
            self.last_settings = {}
        self.last_settings = settings.copy()
        self.save_state()
    
    def ensure_attributes(self):
        """Ensure all required attributes exist (for existing instances)"""
        if not hasattr(self, 'last_operation_id'):
            self.last_operation_id = None
        if not hasattr(self, 'last_settings'):
            self.last_settings = {}
        if not hasattr(self, 'session_data'):
            self.session_data = {}
        if not hasattr(self, 'state_file'):
            self.state_file = Path("gui_state.pkl")
    
    def get_recovery_info(self):
        """Get comprehensive information about recoverable state"""
        self.ensure_attributes()
        
        # Find all potentially active operations
        active_operations = []
        now = datetime.now()
        
        for op_id, op_data in self.active_operations.items():
            status = op_data.get('status', 'unknown')
            
            if status in ['processing', 'consolidating', 'extracting', 'started']:
                # Check if operation is actually still alive
                last_activity_str = op_data.get('last_activity', op_data.get('start_time'))
                is_likely_active = True
                minutes_since_activity = 0
                
                if last_activity_str:
                    try:
                        last_activity = datetime.fromisoformat(last_activity_str)
                        minutes_since_activity = (now - last_activity).total_seconds() / 60
                        # Consider active if updated within 15 minutes
                        is_likely_active = minutes_since_activity < 15
                    except:
                        is_likely_active = False
                
                active_operations.append({
                    'operation_id': op_id,
                    'status': status,
                    'progress': op_data.get('progress_percent', 0),
                    'current_file': op_data.get('current_file', ''),
                    'current_operation': op_data.get('current_operation', 'Processing...'),
                    'start_time': op_data.get('start_time'),
                    'last_activity': op_data.get('last_activity'),
                    'stats': op_data.get('stats', {}),
                    'is_likely_active': is_likely_active,
                    'minutes_since_activity': round(minutes_since_activity, 1),
                    'dry_run': op_data.get('dry_run', False)
                })
        
        # Sort by most recent activity
        active_operations.sort(key=lambda x: x.get('last_activity', ''), reverse=True)
        
        # Primary operation is the most recently active one
        primary_operation = active_operations[0] if active_operations else None
        
        recovery_data = {
            'has_recovery': len(active_operations) > 0,
            'active_operations': active_operations,
            'primary_operation': primary_operation,
            'total_active_operations': len(active_operations),
            'server_time': now.isoformat(),
            'has_saved_settings': bool(self.last_settings),
            'settings': self.last_settings or {}
        }
        
        # Add backward compatibility fields for existing frontend code
        if primary_operation:
            recovery_data.update({
                'operation_id': primary_operation['operation_id'],
                'status': primary_operation['status'],
                'progress': primary_operation['progress'],
                'current_file': primary_operation['current_file']
            })
        
        return recovery_data

gui_state = GUIState()
# Ensure the instance has all required attributes
gui_state.ensure_attributes()

# Global thread tracking for cancellation
active_threads = {}  # operation_id -> thread object
active_reconstructors = {}  # operation_id -> SafeTakeoutReconstructor instance

class ZipExtractor:
    """Handles zip file extraction with progress tracking"""
    
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        self.current_operation = "extracting"
        
    def extract_takeout_zips(self, upload_dir: Path, extract_dir: Path) -> bool:
        """Extract all zip files in upload directory to extract directory"""
        try:
            # Find all zip files
            zip_files = list(upload_dir.glob("*.zip"))
            if not zip_files:
                raise ValueError("No zip files found in upload directory")
            
            self._log(f"Found {len(zip_files)} zip files to extract")
            
            total_files = len(zip_files)
            for i, zip_path in enumerate(zip_files):
                self._log(f"Extracting {zip_path.name} ({i+1}/{total_files})")
                
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        # Extract to subdirectory named after zip file
                        extract_subdir = extract_dir / zip_path.stem
                        extract_subdir.mkdir(parents=True, exist_ok=True)
                        
                        # Extract all files
                        zip_ref.extractall(extract_subdir)
                        
                    progress = ((i + 1) / total_files) * 100
                    self._log(f"Extracted {zip_path.name} successfully")
                    
                    if self.progress_callback:
                        self.progress_callback({
                            'type': 'extraction_progress',
                            'progress_percent': progress,
                            'current_file': zip_path.name,
                            'message': f"Extracted {zip_path.name}"
                        })
                        
                except zipfile.BadZipFile:
                    self._log(f"Error: {zip_path.name} is not a valid zip file", error=True)
                    continue
                except Exception as e:
                    self._log(f"Error extracting {zip_path.name}: {str(e)}", error=True)
                    continue
            
            self._log(f"Extraction complete. Files extracted to: {extract_dir}")
            return True
            
        except Exception as e:
            self._log(f"Extraction failed: {str(e)}", error=True)
            return False
    
    def _log(self, message: str, error: bool = False):
        """Log message with optional error flag"""
        print(f"[ZipExtractor] {message}")
        if self.progress_callback:
            self.progress_callback({
                'type': 'log',
                'message': message,
                'current_operation': self.current_operation,
                'error': error
            })

def create_progress_callback(operation_id: str):
    """Create a progress callback function for a specific operation"""
    def callback(data: Dict):
        gui_state.update_operation(operation_id, data)
    return callback

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main page with drag-drop interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Simple health check endpoint for frontend connectivity testing"""
    return JSONResponse({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_operations': len([op for op in gui_state.active_operations.values() 
                                 if op.get('status') in ['processing', 'consolidating', 'extracting', 'started']])
    })

@app.get("/user-paths")
async def get_user_paths():
    """Get platform-appropriate default paths for the current user"""
    import platform
    import os
    
    system = platform.system().lower()
    username = os.getlogin() if hasattr(os, 'getlogin') else os.environ.get('USER', os.environ.get('USERNAME', 'user'))
    
    if system == 'darwin':  # macOS
        home = Path.home()
        paths = {
            'platform': 'macOS',
            'username': username,
            'home': str(home),
            'desktop': str(home / 'Desktop'),
            'documents': str(home / 'Documents'),
            'downloads': str(home / 'Downloads'),
            'defaultSource': str(home / 'Downloads' / 'Takeout'),
            'defaultOutput': str(home / 'Desktop' / 'Drive Export')
        }
    elif system == 'windows':
        home = Path.home()
        paths = {
            'platform': 'Windows',
            'username': username,
            'home': str(home),
            'desktop': str(home / 'Desktop'),
            'documents': str(home / 'Documents'),
            'downloads': str(home / 'Downloads'),
            'defaultSource': str(home / 'Downloads' / 'Takeout'),
            'defaultOutput': str(home / 'Desktop' / 'Drive Export')
        }
    else:  # Linux and others
        home = Path.home()
        paths = {
            'platform': 'Linux',
            'username': username,
            'home': str(home),
            'desktop': str(home / 'Desktop'),
            'documents': str(home / 'Documents'),
            'downloads': str(home / 'Downloads'),
            'defaultSource': str(home / 'Downloads' / 'Takeout'),
            'defaultOutput': str(home / 'Desktop' / 'Drive Export')
        }
    
    return JSONResponse(paths)

@app.post("/complete-path")
async def complete_path(request: Request):
    """Try to complete a partial path using server-side file system access"""
    try:
        data = await request.json()
        partial_path = data.get('partialPath', '')
        
        if not partial_path:
            return JSONResponse({
                'success': False,
                'error': 'No partial path provided'
            })
        
        # Try different completion strategies
        completed_paths = []
        
        # Strategy 1: Check user's common directories
        user_dirs = [
            Path.home() / 'Desktop',
            Path.home() / 'Downloads', 
            Path.home() / 'Documents'
        ]
        
        for base_dir in user_dirs:
            if base_dir.exists():
                potential_path = base_dir / partial_path
                if potential_path.exists():
                    completed_paths.append({
                        'path': str(potential_path),
                        'confidence': 0.9,
                        'method': 'user-directory-match'
                    })
        
        # Strategy 2: Search mounted volumes (safe locations only)
        volumes_path = Path('/Volumes') if os.name == 'posix' else None
        if volumes_path and volumes_path.exists():
            try:
                for volume in volumes_path.iterdir():
                    if volume.is_dir() and not volume.name.startswith('.'):
                        potential_path = volume / partial_path
                        if potential_path.exists():
                            completed_paths.append({
                                'path': str(potential_path),
                                'confidence': 0.8,
                                'method': 'volume-match'
                            })
            except (PermissionError, OSError):
                pass  # Skip inaccessible volumes
        
        # Strategy 3: Try relative to current working directory
        cwd_path = Path.cwd() / partial_path
        if cwd_path.exists():
            completed_paths.append({
                'path': str(cwd_path),
                'confidence': 0.7,
                'method': 'cwd-relative'
            })
        
        if completed_paths:
            # Return the highest confidence match
            best_match = max(completed_paths, key=lambda x: x['confidence'])
            return JSONResponse({
                'success': True,
                'completedPath': best_match['path'],
                'confidence': best_match['confidence'],
                'method': best_match['method'],
                'allMatches': completed_paths
            })
        else:
            return JSONResponse({
                'success': False,
                'error': 'Could not find any matching paths',
                'partialPath': partial_path
            })
            
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': f'Path completion failed: {str(e)}'
        })

@app.post("/resolve-directory-path")
async def resolve_directory_path(request: Request):
    """Resolve a directory path based on name and contents analysis"""
    try:
        data = await request.json()
        dir_name = data.get('directoryName', '')
        has_zip_files = data.get('hasZipFiles', False)
        zip_files = data.get('zipFiles', [])
        directories = data.get('directories', [])
        has_takeout_structure = data.get('hasTakeoutStructure', False)
        
        if not dir_name:
            return JSONResponse({
                'success': False,
                'error': 'No directory name provided'
            })
        
        resolved_paths = []
        
        # Search strategy: Look for directories with matching name and content signature
        search_locations = [
            Path.home() / 'Desktop',
            Path.home() / 'Downloads',
            Path.home() / 'Documents'
        ]
        
        # Add mounted volumes for macOS/Linux
        if os.name == 'posix':
            volumes_path = Path('/Volumes')
            if volumes_path.exists():
                try:
                    for volume in volumes_path.iterdir():
                        if volume.is_dir() and not volume.name.startswith('.'):
                            search_locations.append(volume)
                except (PermissionError, OSError):
                    pass
        
        for base_location in search_locations:
            if not base_location.exists():
                continue
                
            try:
                # Look for exact directory name match
                candidate_path = base_location / dir_name
                if candidate_path.exists() and candidate_path.is_dir():
                    # Verify contents match what we expect
                    confidence = calculate_directory_match_confidence(
                        candidate_path, has_zip_files, zip_files, has_takeout_structure
                    )
                    
                    if confidence > 0.5:  # Only suggest if reasonably confident
                        resolved_paths.append({
                            'path': str(candidate_path),
                            'confidence': confidence,
                            'location': str(base_location)
                        })
                
                # Also search subdirectories one level deep
                try:
                    for subdir in base_location.iterdir():
                        if subdir.is_dir() and subdir.name == dir_name:
                            confidence = calculate_directory_match_confidence(
                                subdir, has_zip_files, zip_files, has_takeout_structure
                            )
                            if confidence > 0.5:
                                resolved_paths.append({
                                    'path': str(subdir),
                                    'confidence': confidence,
                                    'location': str(base_location)
                                })
                except (PermissionError, OSError):
                    continue
                    
            except (PermissionError, OSError):
                continue
        
        if resolved_paths:
            # Return the highest confidence match
            best_match = max(resolved_paths, key=lambda x: x['confidence'])
            return JSONResponse({
                'success': True,
                'resolvedPath': best_match['path'],
                'confidence': best_match['confidence'],
                'searchLocation': best_match['location'],
                'allMatches': resolved_paths
            })
        else:
            return JSONResponse({
                'success': False,
                'error': 'Could not find matching directory',
                'searchedLocations': [str(loc) for loc in search_locations]
            })
            
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': f'Directory resolution failed: {str(e)}'
        })

def calculate_directory_match_confidence(dir_path, expected_has_zips, expected_zip_files, expected_takeout_structure):
    """Calculate confidence that this directory matches the expected structure"""
    try:
        confidence = 0.5  # Base confidence for name match
        
        # Check for ZIP files
        zip_files_found = []
        takeout_structure_found = False
        
        for item in dir_path.iterdir():
            if item.is_file() and item.name.lower().endswith('.zip'):
                zip_files_found.append(item.name)
                if 'takeout' in item.name.lower():
                    takeout_structure_found = True
            elif item.is_dir() and 'takeout' in item.name.lower():
                takeout_structure_found = True
        
        # Boost confidence based on content matches
        if expected_has_zips and zip_files_found:
            confidence += 0.2
            
            # Check for specific ZIP file matches
            matches = set(expected_zip_files) & set(zip_files_found)
            if matches:
                confidence += 0.2 * (len(matches) / len(expected_zip_files))
        
        if expected_takeout_structure and takeout_structure_found:
            confidence += 0.1
        
        return min(confidence, 1.0)  # Cap at 1.0
        
    except (PermissionError, OSError):
        return 0.3  # Low confidence if we can't read the directory

@app.get("/recovery-info")
async def get_recovery_info():
    """Get information about recoverable operations and last settings"""
    recovery_info = gui_state.get_recovery_info()
    return JSONResponse(recovery_info)

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Handle multiple zip file uploads"""
    operation_id = str(uuid.uuid4())
    gui_state.create_operation(operation_id, "upload")
    
    try:
        # Create temporary upload directory
        temp_dir = Path(tempfile.mkdtemp(prefix="takeout_upload_"))
        
        uploaded_files = []
        for file in files:
            if not file.filename.endswith('.zip'):
                continue
                
            file_path = temp_dir / file.filename
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            uploaded_files.append(file.filename)
        
        gui_state.update_operation(operation_id, {
            'status': 'upload_complete',
            'temp_dir': str(temp_dir),
            'uploaded_files': uploaded_files,
            'message': f"Uploaded {len(uploaded_files)} zip files"
        })
        
        return JSONResponse({
            'success': True,
            'operation_id': operation_id,
            'uploaded_files': uploaded_files,
            'temp_dir': str(temp_dir)
        })
        
    except Exception as e:
        gui_state.update_operation(operation_id, {
            'status': 'error',
            'message': f"Upload failed: {str(e)}"
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract")
async def extract_zips(
    operation_id: str = Form(...),
    temp_dir: str = Form(...),
    output_dir: str = Form(...)
):
    """Extract uploaded zip files"""
    try:
        upload_path = Path(temp_dir)
        extract_path = Path(output_dir) / "extracted_takeouts"
        extract_path.mkdir(parents=True, exist_ok=True)
        
        # Create progress callback
        callback = create_progress_callback(operation_id)
        
        # Extract in background thread
        def extract_thread():
            extractor = ZipExtractor(progress_callback=callback)
            success = extractor.extract_takeout_zips(upload_path, extract_path)
            
            gui_state.update_operation(operation_id, {
                'status': 'extraction_complete' if success else 'extraction_failed',
                'extract_dir': str(extract_path) if success else None,
                'message': 'Extraction completed successfully' if success else 'Extraction failed'
            })
        
        thread = threading.Thread(target=extract_thread)
        thread.daemon = True
        thread.start()
        
        return JSONResponse({
            'success': True,
            'message': 'Extraction started',
            'operation_id': operation_id
        })
        
    except Exception as e:
        gui_state.update_operation(operation_id, {
            'status': 'error',
            'message': f"Extraction setup failed: {str(e)}"
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/consolidate")
async def consolidate_files(
    operation_id: str = Form(...),
    source_dir: str = Form(...),
    dest_dir: str = Form(...),
    verify: bool = Form(default=False)
):
    """Start the consolidation process"""
    try:
        # Create progress callback
        callback = create_progress_callback(operation_id)
        
        # Consolidate in background thread
        def consolidate_thread():
            try:
                reconstructor = SafeTakeoutReconstructor(
                    source_dir=source_dir,
                    dest_dir=dest_dir,
                    dry_run=False,  # GUI mode = real execution
                    progress_callback=callback
                )
                
                gui_state.update_operation(operation_id, {
                    'status': 'consolidating',
                    'message': 'Starting consolidation process...'
                })
                
                reconstructor.reconstruct(verify_copies=verify)
                
                gui_state.update_operation(operation_id, {
                    'status': 'consolidation_complete',
                    'message': 'Consolidation completed successfully',
                    'final_stats': reconstructor.stats,
                    'log_dir': str(reconstructor.log_dir)
                })
                
            except Exception as e:
                gui_state.update_operation(operation_id, {
                    'status': 'consolidation_failed',
                    'message': f'Consolidation failed: {str(e)}'
                })
        
        thread = threading.Thread(target=consolidate_thread)
        thread.daemon = True
        thread.start()
        
        return JSONResponse({
            'success': True,
            'message': 'Consolidation started',
            'operation_id': operation_id
        })
        
    except Exception as e:
        gui_state.update_operation(operation_id, {
            'status': 'error',
            'message': f"Consolidation setup failed: {str(e)}"
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/progress/{operation_id}")
async def get_progress(operation_id: str):
    """Get progress updates for an operation"""
    if operation_id not in gui_state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    # Check for hung operations before returning progress
    hung_ops = gui_state.check_for_hung_operations(timeout_minutes=5)  # 5-minute timeout
    if operation_id in hung_ops:
        gui_state.mark_operation_as_hung(operation_id)
    
    operation = gui_state.active_operations[operation_id]
    recent_logs = gui_state.progress_logs.get(operation_id, [])[-10:]  # Last 10 logs
    
    # Add hang detection info
    now = datetime.now()
    last_activity_str = operation.get('last_activity', operation.get('start_time'))
    minutes_since_activity = 0
    if last_activity_str:
        try:
            last_activity = datetime.fromisoformat(last_activity_str)
            minutes_since_activity = (now - last_activity).total_seconds() / 60
        except:
            pass
    
    return JSONResponse({
        'operation': operation,
        'recent_logs': recent_logs,
        'hang_detection': {
            'minutes_since_activity': round(minutes_since_activity, 1),
            'is_potentially_hung': operation.get('status') == 'hung',
            'last_activity': last_activity_str
        }
    })

@app.get("/logs/{operation_id}")
async def get_logs(operation_id: str):
    """Get all logs for an operation"""
    if operation_id not in gui_state.progress_logs:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    return JSONResponse({
        'logs': gui_state.progress_logs[operation_id]
    })

def cleanup_temp_files():
    """Clean up temporary files older than 24 hours"""
    temp_dir = Path(tempfile.gettempdir())
    for item in temp_dir.glob("takeout_upload_*"):
        try:
            if item.is_dir():
                # Check if older than 24 hours
                age = datetime.now().timestamp() - item.stat().st_mtime
                if age > 86400:  # 24 hours in seconds
                    shutil.rmtree(item)
        except:
            pass

if __name__ == "__main__":
    # Clean up old temp files on startup
    cleanup_temp_files()
    
    print("=" * 60)
    print("🚀 Google Drive Takeout Consolidator - Web GUI")
    print("=" * 60)
    print("Starting server...")
    print("Open your browser to: http://localhost:8000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    # Start the server
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000, 
        log_level="info",
        access_log=False
    )

# NEW PATH-BASED ENDPOINTS (No uploads required)

@app.post("/validate-path")
async def validate_path(request: Request):
    """Validate local path and find ZIP files - no uploads needed"""
    try:
        data = await request.json()
        input_path = data['path']
        
        # Smart path detection - try variations to handle external drives and path issues
        possible_paths = [
            Path(input_path),  # Original path
            Path(input_path.rstrip()),  # Remove trailing spaces
            Path(input_path.strip()),  # Remove leading/trailing spaces
            Path(input_path.replace(' ', '-')),  # Replace spaces with hyphens
            Path(input_path.replace('-', ' ')),  # Replace hyphens with spaces
        ]
        
        # Try glob matching for partial matches
        if '*' not in input_path:
            parent_dir = Path(input_path).parent
            if parent_dir.exists():
                search_pattern = Path(input_path).name + '*'
                glob_matches = list(parent_dir.glob(search_pattern))
                possible_paths.extend(glob_matches)
        
        # Find the first valid path
        valid_path = None
        for path_candidate in possible_paths:
            try:
                # Expand user and resolve, but handle external drives carefully
                if str(path_candidate).startswith('/Volumes/'):
                    # For external drives, don't use resolve() as it might cause issues
                    resolved_path = path_candidate.expanduser()
                else:
                    resolved_path = path_candidate.expanduser().resolve()
                
                if resolved_path.exists() and resolved_path.is_dir():
                    valid_path = resolved_path
                    break
            except (OSError, RuntimeError):
                # Skip paths that cause resolution errors
                continue
        
        if not valid_path:
            # Provide helpful error message
            error_msg = f'Source path does not exist: {input_path}'
            if input_path.startswith('/Volumes/'):
                error_msg += '\n\nTip: Make sure the external drive is mounted and the folder name is correct.'
            elif ' ' in input_path or '-' in input_path:
                error_msg += '\n\nTip: Check for spaces vs hyphens in the folder name.'
            
            return JSONResponse({
                'success': False, 
                'message': error_msg
            })
        
        path = valid_path
        
        # Find ZIP files (exclude system/metadata files like OS file browsers do)
        zip_files = []
        for zip_file in path.glob('*.zip'):
            # Skip system/metadata files that should be hidden (like Finder/Explorer do)
            filename = zip_file.name.lower()
            
            # macOS: ._ files (AppleDouble metadata)
            # Windows: Thumbs.db, desktop.ini, etc.
            # Linux: .directory, .DS_Store, etc.
            # General: any file starting with . (hidden files)
            if (filename.startswith('._') or          # macOS metadata
                filename.startswith('.') or           # Hidden files (all OS)
                filename in ['thumbs.db', 'desktop.ini', 'folder.htt'] or  # Windows
                filename.endswith('.tmp') or          # Temporary files
                filename.endswith('.temp')):
                continue
                
            try:
                zip_files.append({
                    'name': zip_file.name,
                    'size': zip_file.stat().st_size,
                    'path': str(zip_file)
                })
            except:
                continue
        
        # Calculate space requirements if ZIP files found
        space_info = {}
        if zip_files:
            total_zip_size = sum(f['size'] for f in zip_files)
            estimated_extraction_space = total_zip_size * 2.5  # Extraction needs ~2.5x ZIP size
            
            try:
                free_space = shutil.disk_usage(path).free
                space_info = {
                    'zip_size_gb': total_zip_size / (1024**3),
                    'extraction_space_gb': estimated_extraction_space / (1024**3),
                    'available_space_gb': free_space / (1024**3),
                    'space_sufficient': estimated_extraction_space < free_space
                }
            except:
                space_info = {'error': 'Could not check disk space'}
        
        return JSONResponse({
            'success': True,
            'zip_files': zip_files,
            'path': str(path),
            'space_info': space_info,
            'message': f'Found {len(zip_files)} ZIP files'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Error validating path: {str(e)}'
        })

@app.post("/start-processing")
async def start_processing(request: Request):
    """Start processing with local paths - NO UPLOADS"""
    try:
        # Check if there's already an active operation
        gui_state.ensure_attributes()
        for op_id, op_data in gui_state.active_operations.items():
            if op_data.get('status') in ['processing', 'consolidating', 'extracting', 'started']:
                return JSONResponse({
                    'success': False,
                    'message': f'Another operation is already running (ID: {op_id}). Only one operation allowed at a time.',
                    'active_operation_id': op_id
                })
        
        data = await request.json()
        operation_id = str(uuid.uuid4())
        gui_state.create_operation(operation_id, "processing")
        
        dry_run = data.get('dry_run', False)  # Default to real execution
        verify = data.get('verify', False)
        conflict_mode = data.get('conflict_mode', 'rename')  # Default to rename
        
        # Save settings for state persistence
        settings = {
            'source_path': data.get('source_path'),
            'output_path': data.get('output_path'),
            'dry_run': dry_run,
            'verify': verify,
            'conflict_mode': conflict_mode,
            'timestamp': datetime.now().isoformat()
        }
        gui_state.update_last_settings(settings)
        gui_state.last_operation_id = operation_id
        
        # Smart path detection for source path
        source_input = data['source_path']
        source_path = None
        possible_source_paths = [
            Path(source_input),
            Path(source_input.rstrip()),
            Path(source_input.strip()),
            Path(source_input.replace(' ', '-')),
            Path(source_input.replace('-', ' ')),
        ]
        
        for path_candidate in possible_source_paths:
            try:
                if str(path_candidate).startswith('/Volumes/'):
                    resolved_path = path_candidate.expanduser()
                else:
                    resolved_path = path_candidate.expanduser().resolve()
                
                if resolved_path.exists() and resolved_path.is_dir():
                    source_path = resolved_path
                    break
            except (OSError, RuntimeError):
                continue
        
        # Handle output path
        output_input = data['output_path']
        if str(output_input).startswith('/Volumes/'):
            output_path = Path(output_input).expanduser()
        else:
            output_path = Path(output_input).expanduser().resolve()
        
        # Validate paths
        if not source_path or not source_path.exists():
            error_msg = f'Source path does not exist: {source_input}'
            if source_input.startswith('/Volumes/'):
                error_msg += '\n\nTip: Make sure the external drive is mounted and the folder name is correct.'
            
            gui_state.update_operation(operation_id, {
                'status': 'error',
                'message': error_msg
            })
            return JSONResponse({
                'success': False,
                'message': f'Source path does not exist: {source_path}'
            })
        
        # Create output directory if it doesn't exist
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            gui_state.update_operation(operation_id, {
                'status': 'error',
                'message': f'Cannot create output directory: {e}'
            })
            return JSONResponse({
                'success': False,
                'message': f'Cannot create output directory: {e}'
            })
        
        # Process in background thread
        def process_thread():
            try:
                callback = create_progress_callback(operation_id)
                extract_dir = None
                
                gui_state.update_operation(operation_id, {
                    'status': 'starting',
                    'message': 'Initializing process...'
                })
                
                # Check if we have ZIP files that need extraction
                zip_files = list(source_path.glob('*.zip'))
                zip_files = [f for f in zip_files if not f.name.startswith('._')]  # Filter system files
                
                if zip_files:
                    # Calculate disk space requirements
                    total_zip_size = sum(f.stat().st_size for f in zip_files)
                    # Estimate: extraction needs ~2x ZIP size (compressed + uncompressed)
                    estimated_space_needed = total_zip_size * 2.5  # Add buffer
                    
                    gui_state.update_operation(operation_id, {
                        'status': 'checking_space',
                        'message': f'Checking disk space requirements...'
                    })
                    
                    # Check available disk space
                    import shutil as disk_util
                    try:
                        free_space = disk_util.disk_usage(source_path).free
                        space_needed_gb = estimated_space_needed / (1024**3)
                        space_available_gb = free_space / (1024**3)
                        
                        if estimated_space_needed > free_space:
                            raise Exception(f"Insufficient disk space. Need {space_needed_gb:.1f} GB, have {space_available_gb:.1f} GB available.")
                        
                        callback({
                            'type': 'log', 
                            'message': f'Space check: Need {space_needed_gb:.1f} GB, have {space_available_gb:.1f} GB available ✅'
                        })
                    except Exception as space_error:
                        raise Exception(f"Disk space check failed: {space_error}")
                    
                    # Step 1: Extract ZIP files IN-PLACE (same directory as ZIPs)
                    gui_state.update_operation(operation_id, {
                        'status': 'extracting',
                        'message': f'Extracting {len(zip_files)} ZIP files... ({space_needed_gb:.1f} GB needed)'
                    })
                    
                    # Create temporary extraction directory IN THE SOURCE PATH
                    extract_dir = source_path / f"temp_extract_{operation_id[:8]}"
                    extract_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Extract ZIP files
                    extractor = ZipExtractor(progress_callback=callback)
                    success = extractor.extract_takeout_zips(source_path, extract_dir)
                    
                    if not success:
                        raise Exception("ZIP extraction failed")
                    
                    # Use extracted directory as source for consolidation
                    consolidation_source = extract_dir
                else:
                    # No ZIP files, assume already extracted folders
                    consolidation_source = source_path
                    
                    # Still clean up any old temp directories
                    cleanup_old_temp_dirs(source_path, callback)
                
                # Step 2: Consolidate files
                gui_state.update_operation(operation_id, {
                    'status': 'consolidating',
                    'message': 'Consolidating Google Drive structure...'
                })
                
                # Create reconstructor
                reconstructor = SafeTakeoutReconstructor(
                    source_dir=str(consolidation_source),
                    dest_dir=str(output_path), 
                    dry_run=dry_run,
                    progress_callback=callback,
                    gui_mode=True  # Send prompts to GUI instead of terminal
                )
                
                # Track reconstructor for cancellation
                active_reconstructors[operation_id] = reconstructor
                
                # Run the consolidation
                reconstructor.reconstruct(verify_copies=verify)
                
                # Clean up temporary extraction directory if created
                if extract_dir and extract_dir.exists():
                    try:
                        callback({'type': 'log', 'message': f'🧽 Starting cleanup of temporary files...'})
                        
                        # Move temp directory to trash instead of just deleting
                        if move_to_trash(extract_dir, callback):
                            callback({'type': 'log', 'message': f'✅ Successfully moved temp directory to trash'})
                        
                        # Also clean up any other old temp directories
                        cleanup_old_temp_dirs(source_path, callback)
                        
                        # Final verification - ensure only ZIP files remain in source
                        remaining_files = list(source_path.iterdir())
                        zip_files = [f for f in remaining_files if f.suffix.lower() == '.zip' and not f.name.startswith('._')]
                        temp_files = [f for f in remaining_files if f.name.startswith('temp_') or f.name.startswith('._')]
                        
                        if temp_files:
                            callback({'type': 'log', 'message': f'🧽 Cleaning up {len(temp_files)} remaining temp files...'})
                            for temp_file in temp_files:
                                try:
                                    if temp_file.is_dir():
                                        move_to_trash(temp_file, callback)
                                    else:
                                        temp_file.unlink()  # Delete small files directly
                                        callback({'type': 'log', 'message': f'🧽 Removed: {temp_file.name}'})
                                except Exception as e:
                                    callback({'type': 'log', 'message': f'⚠️ Could not remove {temp_file.name}: {e}'})
                        
                        callback({'type': 'log', 'message': f'✨ Cleanup complete! Source folder now contains only {len(zip_files)} ZIP files'})
                        
                    except Exception as cleanup_error:
                        callback({'type': 'log', 'message': f'⚠️ Warning: Could not complete cleanup: {cleanup_error}'})
                
                gui_state.update_operation(operation_id, {
                    'status': 'completed',
                    'message': 'Processing completed successfully',
                    'final_stats': reconstructor.stats,
                    'log_dir': str(reconstructor.log_dir)
                })
                
            except Exception as e:
                # Clean up temporary extraction directory on error
                if 'extract_dir' in locals() and extract_dir and extract_dir.exists():
                    try:
                        callback({'type': 'log', 'message': f'🧽 Cleaning up after error...'})
                        move_to_trash(extract_dir, callback)
                        cleanup_old_temp_dirs(source_path, callback)
                    except Exception as cleanup_error:
                        callback({'type': 'log', 'message': f'⚠️ Could not clean up temp directory: {cleanup_error}'})
                        
                gui_state.update_operation(operation_id, {
                    'status': 'failed',
                    'message': f'Processing failed: {str(e)}'
                })
            finally:
                # CRITICAL: Ensure complete resource cleanup
                try:
                    # Clean up reconstructor resources
                    if operation_id in active_reconstructors:
                        reconstructor = active_reconstructors[operation_id]
                        if hasattr(reconstructor, 'cleanup_resources'):
                            reconstructor.cleanup_resources()
                        del active_reconstructors[operation_id]
                    
                    # Clean up thread tracking
                    if operation_id in active_threads:
                        del active_threads[operation_id]
                    
                    # Final cleanup of any remaining temp files in source directory
                    if 'source_path' in locals() and source_path and source_path.exists():
                        try:
                            cleanup_old_temp_dirs(source_path, callback)
                        except Exception as final_cleanup_error:
                            if callback:
                                callback({'type': 'log', 'message': f'⚠️ Final cleanup warning: {final_cleanup_error}'})
                
                    # Force garbage collection to release file handles
                    import gc
                    gc.collect()
                    
                    if callback:
                        callback({'type': 'log', 'message': '🧹 Final resource cleanup completed'})
                        
                except Exception as cleanup_error:
                    if callback:
                        callback({'type': 'log', 'message': f'⚠️ Final cleanup error: {cleanup_error}'})
        
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        active_threads[operation_id] = thread  # Track thread for cancellation
        thread.start()
        
        return JSONResponse({
            'success': True,
            'operation_id': operation_id,
            'message': 'Processing started'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Error starting processing: {str(e)}'
        })

@app.post("/cancel/{operation_id}")
async def cancel_operation(operation_id: str):
    """Cancel a running operation and clean up resources"""
    if operation_id not in gui_state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    try:
        # 1. Signal the reconstructor to cancel if it exists
        if operation_id in active_reconstructors:
            reconstructor = active_reconstructors[operation_id]
            reconstructor.cancel()
            print(f"\n⚠️ Cancelling operation {operation_id}")
        
        # 2. Update operation status
        gui_state.update_operation(operation_id, {
            'status': 'cancelled',
            'message': 'Operation cancelled by user',
            'progress_percent': 0
        })
        
        # 3. Clean up thread tracking (thread will clean itself up)
        if operation_id in active_threads:
            print(f"\u2139️ Thread {operation_id} will terminate gracefully")
        
        # 4. Clear GUI state for fresh start
        gui_state.last_operation_id = None
        
        return JSONResponse({
            'success': True, 
            'message': 'Operation cancelled successfully',
            'reset_to_main': True  # Signal frontend to reset
        })
        
    except Exception as e:
        print(f"Error cancelling operation: {e}")
        return JSONResponse({
            'success': False,
            'message': f'Error cancelling operation: {str(e)}'
        })

@app.post("/open-folder")
async def open_folder(request: Request):
    """Try to open a folder using system commands"""
    try:
        data = await request.json()
        folder_path = data.get('path', '')
        
        if not folder_path or not Path(folder_path).exists():
            return JSONResponse({
                'success': False,
                'message': 'Invalid or non-existent folder path'
            })
        
        import subprocess
        import platform
        
        system = platform.system().lower()
        
        try:
            if system == 'darwin':  # macOS
                subprocess.run(['open', folder_path], check=True)
            elif system == 'windows':
                subprocess.run(['explorer', folder_path], check=True)
            elif system == 'linux':
                subprocess.run(['xdg-open', folder_path], check=True)
            else:
                return JSONResponse({
                    'success': False,
                    'message': f'Unsupported operating system: {system}'
                })
            
            return JSONResponse({
                'success': True,
                'message': f'Opened folder: {folder_path}'
            })
            
        except subprocess.CalledProcessError as e:
            return JSONResponse({
                'success': False,
                'message': f'Failed to open folder: {str(e)}'
            })
        except FileNotFoundError:
            return JSONResponse({
                'success': False,
                'message': 'System file manager not found'
            })
            
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Error opening folder: {str(e)}'
        })

@app.post("/cleanup-temp")
async def cleanup_temp_files(request: Request):
    """Clean up temporary files from source directory"""
    try:
        data = await request.json()
        source_path = Path(data.get('source_path', ''))
        
        if not source_path.exists():
            return JSONResponse({
                'success': False,
                'message': 'Source path does not exist'
            })
        
        # Count temp files before cleanup
        temp_dirs = list(source_path.glob('temp_extract_*'))
        temp_files = [f for f in source_path.iterdir() if f.name.startswith('._') and f.suffix.lower() == '.zip']
        
        total_cleaned = 0
        
        # Clean temp directories
        for temp_dir in temp_dirs:
            if temp_dir.is_dir():
                try:
                    move_to_trash(temp_dir)
                    total_cleaned += 1
                except Exception as e:
                    print(f"Could not clean {temp_dir}: {e}")
        
        # Clean ._ metadata files
        for temp_file in temp_files:
            try:
                temp_file.unlink()
                total_cleaned += 1
            except Exception as e:
                print(f"Could not clean {temp_file}: {e}")
        
        # Count remaining files
        remaining_files = list(source_path.iterdir())
        zip_files = [f for f in remaining_files if f.suffix.lower() == '.zip' and not f.name.startswith('._')]
        
        message = f"Cleaned {total_cleaned} temporary items. Source folder now contains {len(zip_files)} ZIP files."
        
        return JSONResponse({
            'success': True,
            'message': message,
            'cleaned_count': total_cleaned,
            'remaining_zips': len(zip_files)
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Cleanup failed: {str(e)}'
        })

