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
    """Move file or directory to trash (cross-platform)"""
    try:
        import platform
        import subprocess
        
        system = platform.system().lower()
        path_str = str(file_path)
        
        if system == 'darwin':  # macOS
            subprocess.run(['mv', path_str, os.path.expanduser('~/.Trash/')], check=True)
        elif system == 'windows':
            # Use PowerShell to move to recycle bin
            subprocess.run([
                'powershell', '-Command', 
                f'Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("{path_str}", [Microsoft.VisualBasic.FileIO.DeleteDirectoryOption]::DeleteAllContents, [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)'
            ], check=True)
        elif system == 'linux':
            # Try trash-cli first, fallback to rm if not available
            try:
                subprocess.run(['trash', path_str], check=True)
            except FileNotFoundError:
                # trash-cli not installed, use rm as fallback
                subprocess.run(['rm', '-rf', path_str], check=True)
        else:
            # Fallback to shutil.rmtree for unknown systems
            shutil.rmtree(file_path)
            
        if callback:
            callback({'type': 'log', 'message': f'🗑️ Moved to trash: {file_path.name}'})
        return True
        
    except subprocess.CalledProcessError as e:
        if callback:
            callback({'type': 'log', 'message': f'⚠️ Failed to move to trash: {e}'})
        # Fallback to regular deletion
        try:
            shutil.rmtree(file_path)
            if callback:
                callback({'type': 'log', 'message': f'🧽 Deleted (fallback): {file_path.name}'})
            return True
        except Exception as fallback_error:
            if callback:
                callback({'type': 'log', 'message': f'⚠️ Could not delete: {fallback_error}'})
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

# Startup cleanup
@app.on_event("startup")
async def startup_cleanup():
    """Clean up any leftover temp files from previous runs"""
    try:
        # Check common locations for temp files
        volumes_path = Path('/Volumes')
        if volumes_path.exists():
            for volume in volumes_path.iterdir():
                if volume.is_dir():
                    cleanup_old_temp_dirs(volume, None)
    except Exception as e:
        print(f"Startup cleanup warning: {e}")
        
    print("🧹 Startup cleanup completed")

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
        self.active_operations[operation_id] = {
            'id': operation_id,
            'type': operation_type,
            'status': 'started',
            'progress': 0,
            'current_file': '',
            'start_time': datetime.now().isoformat(),
            'stats': {}
        }
        self.progress_logs[operation_id] = []
    
    def update_operation(self, operation_id: str, update_data: Dict) -> None:
        """Update operation progress"""
        if operation_id in self.active_operations:
            self.active_operations[operation_id].update(update_data)
            
            # Add to progress log
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'message': update_data.get('message', ''),
                'progress': update_data.get('progress_percent', 0),
                'current_file': update_data.get('current_file', '')
            }
            self.progress_logs[operation_id].append(log_entry)
            
            # Keep only last 100 log entries
            if len(self.progress_logs[operation_id]) > 100:
                self.progress_logs[operation_id] = self.progress_logs[operation_id][-100:]

gui_state = GUIState()

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
    
    operation = gui_state.active_operations[operation_id]
    recent_logs = gui_state.progress_logs.get(operation_id, [])[-10:]  # Last 10 logs
    
    return JSONResponse({
        'operation': operation,
        'recent_logs': recent_logs
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
        data = await request.json()
        operation_id = str(uuid.uuid4())
        gui_state.create_operation(operation_id, "processing")
        
        dry_run = data.get('dry_run', False)  # Default to real execution
        verify = data.get('verify', False)
        conflict_mode = data.get('conflict_mode', 'rename')  # Default to rename
        
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
        
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
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
    """Cancel a running operation"""
    if operation_id in gui_state.active_operations:
        gui_state.update_operation(operation_id, {
            'status': 'cancelled',
            'message': 'Operation cancelled by user'
        })
        return JSONResponse({'success': True, 'message': 'Operation cancelled'})
    else:
        raise HTTPException(status_code=404, detail="Operation not found")

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

