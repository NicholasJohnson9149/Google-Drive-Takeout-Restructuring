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

# Initialize FastAPI app
app = FastAPI(title="Google Drive Takeout Consolidator", version="1.0.0")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global state for GUI operations
class GUIState:
    def __init__(self):
        self.active_operations: Dict[str, Dict] = {}
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
        path = Path(data['path']).expanduser().resolve()
        
        if not path.exists():
            return JSONResponse({
                'success': False, 
                'message': f'Path does not exist: {path}'
            })
        
        if not path.is_dir():
            return JSONResponse({
                'success': False, 
                'message': f'Path is not a directory: {path}'
            })
        
        # Find ZIP files
        zip_files = []
        for zip_file in path.glob('*.zip'):
            try:
                zip_files.append({
                    'name': zip_file.name,
                    'size': zip_file.stat().st_size,
                    'path': str(zip_file)
                })
            except:
                continue
        
        return JSONResponse({
            'success': True,
            'zip_files': zip_files,
            'path': str(path),
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
        
        source_path = Path(data['source_path']).expanduser().resolve()
        output_path = Path(data['output_path']).expanduser().resolve()
        dry_run = data.get('dry_run', True)
        verify = data.get('verify', False)
        
        # Validate paths
        if not source_path.exists():
            gui_state.update_operation(operation_id, {
                'status': 'error',
                'message': f'Source path does not exist: {source_path}'
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
                
                gui_state.update_operation(operation_id, {
                    'status': 'starting',
                    'message': 'Initializing consolidation process...'
                })
                
                # Create reconstructor with direct path processing
                reconstructor = SafeTakeoutReconstructor(
                    source_dir=str(source_path),
                    dest_dir=str(output_path), 
                    dry_run=dry_run,
                    progress_callback=callback
                )
                
                gui_state.update_operation(operation_id, {
                    'status': 'processing',
                    'message': 'Processing files...'
                })
                
                # Run the consolidation
                reconstructor.reconstruct(verify_copies=verify)
                
                gui_state.update_operation(operation_id, {
                    'status': 'completed',
                    'message': 'Processing completed successfully',
                    'final_stats': reconstructor.stats,
                    'log_dir': str(reconstructor.log_dir)
                })
                
            except Exception as e:
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

