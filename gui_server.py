#!/usr/bin/env python3
"""
Original GUI Server for Google Drive Takeout Restructuring
Sophisticated web interface with state management, real-time progress tracking, and recovery
"""
from __future__ import annotations

import os
import pickle
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel


class GUIState:
    """Manages persistent state for the GUI application"""
    
    def __init__(self):
        self.state_file = Path("gui_state.pkl")
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self.progress_logs: Dict[str, List[Dict[str, Any]]] = {}
        self.user_paths: Dict[str, str] = {}
        self.last_cleanup = datetime.now()
        
        # Load existing state if available
        self.load_state()
    
    def save_state(self):
        """Save current state to disk"""
        try:
            state_data = {
                'active_operations': self.active_operations,
                'progress_logs': self.progress_logs,
                'user_paths': self.user_paths,
                'last_cleanup': self.last_cleanup,
                'save_timestamp': datetime.now()
            }
            
            with open(self.state_file, 'wb') as f:
                pickle.dump(state_data, f)
                
        except Exception as e:
            print(f"Warning: Failed to save GUI state: {e}")
    
    def load_state(self):
        """Load state from disk if available"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'rb') as f:
                    state_data = pickle.load(f)
                
                self.active_operations = state_data.get('active_operations', {})
                self.progress_logs = state_data.get('progress_logs', {})
                self.user_paths = state_data.get('user_paths', {})
                self.last_cleanup = state_data.get('last_cleanup', datetime.now())
                
                print(f"Loaded GUI state with {len(self.active_operations)} active operations")
                
                # Clean up old operations on startup
                self.cleanup_old_operations()
                
        except Exception as e:
            print(f"Warning: Failed to load GUI state: {e}")
            # Reset to clean state
            self.active_operations = {}
            self.progress_logs = {}
            self.user_paths = {}
    
    def cleanup_old_operations(self):
        """Clean up operations older than 24 hours"""
        cutoff = datetime.now()
        cutoff = cutoff.replace(hour=cutoff.hour - 24) if cutoff.hour >= 24 else cutoff.replace(day=cutoff.day - 1, hour=cutoff.hour + 24 - 24)
        
        old_ops = []
        for op_id, operation in self.active_operations.items():
            try:
                last_activity = datetime.fromisoformat(operation.get('last_activity', operation.get('start_time', '')))
                if last_activity < cutoff:
                    old_ops.append(op_id)
            except (ValueError, TypeError):
                old_ops.append(op_id)  # Remove operations with invalid timestamps
        
        for op_id in old_ops:
            self.active_operations.pop(op_id, None)
            self.progress_logs.pop(op_id, None)
        
        if old_ops:
            print(f"Cleaned up {len(old_ops)} old operations")
            self.save_state()
    
    def get_recovery_info(self):
        """Get recovery information for client"""
        active_ops = [op for op in self.active_operations.values() 
                     if op.get('status') in ['starting', 'processing', 'extracting', 'consolidating']]
        
        return {
            'hasActiveOperation': len(active_ops) > 0,
            'activeOperation': active_ops[0] if active_ops else None,
            'totalOperations': len(self.active_operations)
        }


# Initialize global state
gui_state = GUIState()

# Create FastAPI app
app = FastAPI(
    title="Google Drive Takeout Restructuring",
    description="Reconstruct Google Drive folder structure from takeout files", 
    version="2.0.0"
)

# Setup templates and static files
templates_dir = Path(__file__).parent / "app" / "gui" / "templates"
static_dir = Path(__file__).parent / "app" / "gui" / "static"

if not templates_dir.exists():
    print(f"Warning: Templates directory not found at {templates_dir}")
    templates_dir = Path(__file__).parent / "templates"

if not static_dir.exists():
    print(f"Warning: Static directory not found at {static_dir}")
    static_dir = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(templates_dir))

# Mount static files
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    print(f"Warning: Could not mount static files - directory not found: {static_dir}")


# Add platform detection and user paths
def detect_user_paths():
    """Detect default paths based on platform"""
    import platform
    
    system = platform.system().lower()
    user_home = Path.home()
    
    if system == "darwin":  # macOS
        return {
            "platform": "macOS",
            "defaultSource": str(user_home / "Downloads" / "Takeout"),
            "defaultOutput": str(user_home / "Desktop" / "Drive Export"),
            "downloadsPath": str(user_home / "Downloads"),
            "desktopPath": str(user_home / "Desktop"),
            "documentsPath": str(user_home / "Documents")
        }
    elif system == "windows":
        return {
            "platform": "Windows", 
            "defaultSource": str(user_home / "Downloads" / "Takeout"),
            "defaultOutput": str(user_home / "Desktop" / "Drive Export"),
            "downloadsPath": str(user_home / "Downloads"),
            "desktopPath": str(user_home / "Desktop"),
            "documentsPath": str(user_home / "Documents")
        }
    else:  # Linux and others
        return {
            "platform": "Linux",
            "defaultSource": str(user_home / "Downloads" / "Takeout"),
            "defaultOutput": str(user_home / "Desktop" / "Drive Export"),
            "downloadsPath": str(user_home / "Downloads"),
            "desktopPath": str(user_home / "Desktop"),
            "documentsPath": str(user_home / "Documents")
        }


# Main routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main GUI page"""
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        print(f"Error serving template: {e}")
        # Fallback to simple response
        return HTMLResponse(f"""
        <html>
        <head><title>GUI Template Error</title></head>
        <body>
            <h1>GUI Template Error</h1>
            <p>Could not load the sophisticated GUI template. Error: {e}</p>
            <p>Template directory: {templates_dir}</p>
            <p>Static directory: {static_dir}</p>
        </body>
        </html>
        """)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "message": "GUI server is running", "active_operations": len(gui_state.active_operations)}


@app.get("/user-paths")
async def get_user_paths():
    """Get platform-specific default paths"""
    return detect_user_paths()


@app.get("/recovery-info")
async def get_recovery_info():
    """Get recovery information for the client"""
    return gui_state.get_recovery_info()


@app.get("/progress/{operation_id}")
async def get_progress(operation_id: str):
    """Get progress for a specific operation"""
    if operation_id not in gui_state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    operation = gui_state.active_operations[operation_id]
    
    # Calculate hang detection info
    try:
        last_activity_str = operation.get('last_activity', operation.get('start_time', ''))
        last_activity = datetime.fromisoformat(last_activity_str)
        minutes_since_activity = (datetime.now() - last_activity).total_seconds() / 60
    except (ValueError, TypeError):
        minutes_since_activity = 0
    
    hang_detection = {
        'minutes_since_activity': minutes_since_activity,
        'is_potentially_hung': minutes_since_activity > 5,
        'should_warn': minutes_since_activity > 10
    }
    
    return {
        'operation': operation,
        'hang_detection': hang_detection,
        'logs_available': len(gui_state.progress_logs.get(operation_id, []))
    }


@app.get("/logs/{operation_id}")
async def get_logs(operation_id: str):
    """Get logs for a specific operation"""
    if operation_id not in gui_state.progress_logs:
        raise HTTPException(status_code=404, detail="Logs not found")
    
    return {
        'operation_id': operation_id,
        'logs': gui_state.progress_logs[operation_id]
    }


class PathValidationRequest(BaseModel):
    path: str


@app.post("/validate-path")
async def validate_path(request: PathValidationRequest):
    """Validate a takeout source path"""
    try:
        path_obj = Path(request.path)
        
        if not path_obj.exists():
            return JSONResponse({
                'success': False,
                'message': 'Path does not exist'
            })
        
        if not path_obj.is_dir():
            return JSONResponse({
                'success': False, 
                'message': 'Path is not a directory'
            })
        
        # Look for ZIP files
        zip_files = []
        total_size = 0
        
        for zip_path in path_obj.glob("*.zip"):
            try:
                size = zip_path.stat().st_size
                zip_files.append({
                    'name': zip_path.name,
                    'size': size,
                    'path': str(zip_path)
                })
                total_size += size
            except OSError:
                continue
        
        # Estimate space requirements (ZIP files expand ~30% on average)
        estimated_extraction_size = total_size * 1.3
        
        # Check available space
        try:
            import shutil
            _, _, free_bytes = shutil.disk_usage(path_obj)
            space_sufficient = free_bytes > estimated_extraction_size
        except:
            free_bytes = 0
            space_sufficient = None
        
        space_info = {
            'total_zip_size_bytes': total_size,
            'estimated_extraction_bytes': estimated_extraction_size,
            'available_space_bytes': free_bytes,
            'space_sufficient': space_sufficient,
            'extraction_space_gb': estimated_extraction_size / (1024**3),
            'available_space_gb': free_bytes / (1024**3) if free_bytes > 0 else 0
        }
        
        return JSONResponse({
            'success': True,
            'path': str(path_obj.absolute()),
            'zip_files': zip_files,
            'space_info': space_info
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Error validating path: {str(e)}'
        })


class PathCreationRequest(BaseModel):
    path: str
    create: bool = False
    type: str = "directory"


@app.post("/validate-and-create-path") 
async def validate_and_create_path(request: PathCreationRequest):
    """Validate and optionally create a path"""
    try:
        path_obj = Path(request.path)
        
        exists = path_obj.exists()
        can_create = False
        created = False
        
        if not exists:
            # Check if we can create it
            parent = path_obj.parent
            can_create = parent.exists() and parent.is_dir()
            
            if request.create and can_create:
                try:
                    if request.type == "directory":
                        path_obj.mkdir(parents=True, exist_ok=True)
                        created = True
                        exists = True
                    else:
                        path_obj.touch()
                        created = True
                        exists = True
                except OSError as e:
                    return JSONResponse({
                        'success': False,
                        'error': f'Could not create path: {e}',
                        'path': str(path_obj.absolute()),
                        'exists': False,
                        'can_create': False
                    })
        
        return JSONResponse({
            'success': True,
            'path': str(path_obj.absolute()),
            'exists': exists,
            'can_create': can_create,
            'created': created
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e),
            'path': request.path,
            'exists': False,
            'can_create': False
        })


class PathCompletionRequest(BaseModel):
    partialPath: str


@app.post("/complete-path")
async def complete_path(request: PathCompletionRequest):
    """Try to complete a partial path"""
    try:
        partial = request.partialPath.strip()
        if not partial:
            return JSONResponse({'success': False})
        
        # Try to resolve the path
        path_obj = Path(partial)
        
        # If it's already absolute and exists, return it
        if path_obj.is_absolute() and path_obj.exists():
            return JSONResponse({
                'success': True,
                'completedPath': str(path_obj.absolute())
            })
        
        # Try common locations
        user_home = Path.home()
        common_locations = [
            user_home / "Downloads",
            user_home / "Desktop", 
            user_home / "Documents",
            user_home,
            Path("/Volumes"),  # macOS external drives
            Path("/media"),    # Linux mounts
        ]
        
        for base_path in common_locations:
            if base_path.exists():
                candidate = base_path / partial
                if candidate.exists():
                    return JSONResponse({
                        'success': True,
                        'completedPath': str(candidate.absolute())
                    })
        
        return JSONResponse({'success': False})
        
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


class DirectoryResolutionRequest(BaseModel):
    directoryName: str
    hasZipFiles: bool = False
    zipFiles: List[str] = []
    directories: List[str] = []
    hasTakeoutStructure: bool = False


@app.post("/resolve-directory-path")
async def resolve_directory_path(request: DirectoryResolutionRequest):
    """Try to resolve a directory name to a full path"""
    try:
        dir_name = request.directoryName.strip()
        if not dir_name:
            return JSONResponse({'success': False})
        
        # Search in common locations
        user_home = Path.home()
        search_locations = [
            user_home / "Downloads",
            user_home / "Desktop",
            user_home / "Documents", 
            user_home,
        ]
        
        # Add external drives on macOS
        volumes_path = Path("/Volumes")
        if volumes_path.exists():
            for volume in volumes_path.iterdir():
                if volume.is_dir() and not volume.name.startswith('.'):
                    search_locations.append(volume)
        
        # Search for directories matching the name
        for base_path in search_locations:
            if not base_path.exists():
                continue
                
            try:
                candidate = base_path / dir_name
                if candidate.exists() and candidate.is_dir():
                    return JSONResponse({
                        'success': True,
                        'resolvedPath': str(candidate.absolute())
                    })
                    
                # Also try searching subdirectories
                for sub_dir in base_path.iterdir():
                    if sub_dir.is_dir() and sub_dir.name == dir_name:
                        return JSONResponse({
                            'success': True,
                            'resolvedPath': str(sub_dir.absolute())
                        })
            except (OSError, PermissionError):
                continue
        
        return JSONResponse({'success': False})
        
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


class OutputPathSuggestionRequest(BaseModel):
    folderName: str


@app.post("/suggest-output-paths")
async def suggest_output_paths(request: OutputPathSuggestionRequest):
    """Get suggested output paths for a folder name"""
    try:
        folder_name = request.folderName.strip()
        if not folder_name:
            return JSONResponse({'success': False, 'suggestions': []})
        
        user_home = Path.home()
        suggestions = []
        
        # Common output locations
        base_locations = [
            (user_home / "Desktop", "Desktop"),
            (user_home / "Documents", "Documents"), 
            (user_home / "Downloads", "Downloads"),
            (user_home, "Home"),
        ]
        
        # Add external drives on macOS
        volumes_path = Path("/Volumes")
        if volumes_path.exists():
            for volume in volumes_path.iterdir():
                if volume.is_dir() and not volume.name.startswith('.'):
                    base_locations.append((volume, f"External Drive ({volume.name})"))
        
        for base_path, location_name in base_locations:
            if not base_path.exists():
                continue
                
            suggested_path = base_path / folder_name
            
            try:
                # Check if we can write to the parent directory
                can_create = base_path.is_dir() and os.access(base_path, os.W_OK)
                exists = suggested_path.exists()
                
                suggestions.append({
                    'path': str(suggested_path.absolute()),
                    'location': location_name,
                    'exists': exists,
                    'can_create': can_create and not exists
                })
            except (OSError, PermissionError):
                continue
        
        return JSONResponse({
            'success': True,
            'suggestions': suggestions[:6]  # Limit to 6 suggestions
        })
        
    except Exception as e:
        return JSONResponse({'success': False, 'suggestions': [], 'error': str(e)})


class OpenFolderRequest(BaseModel):
    path: str


@app.post("/open-folder")
async def open_folder(request: OpenFolderRequest):
    """Open a folder in the system file manager"""
    try:
        import subprocess
        import platform
        
        folder_path = Path(request.path)
        if not folder_path.exists():
            return JSONResponse({
                'success': False,
                'message': 'Folder does not exist'
            })
        
        system = platform.system().lower()
        if system == "darwin":  # macOS
            subprocess.run(["open", str(folder_path)], check=True)
        elif system == "windows":
            subprocess.run(["explorer", str(folder_path)], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(folder_path)], check=True)
        
        return JSONResponse({
            'success': True,
            'message': 'Folder opened successfully'
        })
        
    except subprocess.CalledProcessError:
        return JSONResponse({
            'success': False,
            'message': 'Failed to open folder'
        })
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


# Note: Router will be included after app initialization to avoid circular imports


def open_browser(port: int = 8000):
    """Open browser after a short delay"""
    time.sleep(1.5)
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass


def run():
    """Start the GUI server"""
    port = 8000
    
    print("🚀 Starting Google Drive Takeout Restructuring GUI...")
    print(f"🌐 Server will be available at: http://localhost:{port}")
    print("⏳ Starting server...")
    
    # Include the processing router now to avoid circular imports
    try:
        from app.gui.routers.processing import router as processing_router
        app.include_router(processing_router, prefix="", tags=["processing"])
        print("✅ Successfully included processing router")
    except Exception as e:
        print(f"❌ Failed to include processing router: {e}")
    
    # Start browser in background thread
    browser_thread = threading.Thread(target=open_browser, args=(port,))
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start the server
    uvicorn.run(
        app,
        host="127.0.0.1", 
        port=port,
        log_level="info",
        access_log=False
    )


if __name__ == "__main__":
    run()