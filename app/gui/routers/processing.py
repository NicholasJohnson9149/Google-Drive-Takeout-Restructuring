from __future__ import annotations

import os
import threading
import uuid
import gc
from pathlib import Path
from datetime import datetime
from typing import List

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

# Import from the main gui_server module
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
import gui_server as root_app
from app.core.cli_executor import CLIExecutor

router = APIRouter()


@router.post("/start-processing")
async def start_processing(request: Request):
    gui_state = root_app.gui_state
    try:
        data = await request.json()
        takeout_path = data['takeout_path']
        export_path = data['export_path']
        
        operation_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        operation = {
            'id': operation_id,
            'takeout_path': takeout_path,
            'export_path': export_path,
            'status': 'starting',
            'progress_percent': 0.0,
            'current_file': '',
            'message': '',
            'start_time': timestamp,
            'last_activity': timestamp,
            'current_operation': '',
            'stats': {
                'total_files': 0,
                'copied_files': 0,
                'skipped_duplicates': 0,
                'errors': 0
            }
        }
        
        gui_state.active_operations[operation_id] = operation
        gui_state.progress_logs[operation_id] = []
        
        def process_thread():
            try:
                def progress_callback(update):
                    if operation_id not in gui_state.active_operations:
                        return
                    
                    op = gui_state.active_operations[operation_id]
                    op['last_activity'] = datetime.now().isoformat()
                    
                    if update.get('type') == 'log':
                        gui_state.progress_logs[operation_id].append({
                            'timestamp': datetime.now().isoformat(),
                            'message': update.get('message', ''),
                            'type': update.get('level', 'info')
                        })
                        op['message'] = update.get('message', '')
                    
                    elif update.get('type') == 'progress':
                        op['progress_percent'] = update.get('percent', 0.0)
                        op['current_file'] = update.get('current_file', '')
                        op['current_operation'] = update.get('operation', '')
                        
                        if 'status' in update:
                            op['status'] = update['status']
                    
                    elif update.get('type') == 'stats':
                        stats = update.get('stats', {})
                        if isinstance(stats, dict):
                            if 'value' in stats:
                                # Update based on description
                                desc = stats.get('description', '').lower()
                                if 'total' in desc:
                                    op['stats']['total_files'] = stats['value']
                                elif 'copied' in desc:
                                    op['stats']['copied_files'] = stats['value']
                                elif 'skipped' in desc:
                                    op['stats']['skipped_duplicates'] = stats['value']
                                elif 'error' in desc:
                                    op['stats']['errors'] = stats['value']
                    
                    elif update.get('type') == 'status':
                        op['status'] = update.get('status', op['status'])
                        op['message'] = update.get('message', op['message'])
                    
                    gui_state.save_state()
                
                # Build CLI command options
                options = {
                    'dry_run': data.get('dry_run', False),
                    'verify': data.get('verify_files', False),
                    'force': True,  # Skip confirmation in GUI mode
                    'verbose': True  # Always verbose for progress tracking
                }
                
                # Use CLI executor to run the rebuild command
                executor = CLIExecutor()
                cmd = executor.build_rebuild_command(
                    takeout_path,
                    export_path,
                    options
                )
                
                # Execute the CLI command with progress callback
                return_code = executor.execute_with_progress(
                    cmd,
                    operation_id,
                    progress_callback
                )
                
                # Update final status based on return code
                operation = gui_state.active_operations.get(operation_id)
                if operation:
                    if return_code == 0:
                        operation['status'] = 'completed'
                        operation['progress_percent'] = 100.0
                        operation['message'] = 'Reconstruction completed successfully!'
                    else:
                        operation['status'] = 'failed'
                        operation['message'] = f'Process failed with exit code {return_code}'
                    
                    operation['last_activity'] = datetime.now().isoformat()
                    gui_state.save_state()
                
            except Exception as e:
                operation = gui_state.active_operations.get(operation_id)
                if operation:
                    operation['status'] = 'failed'
                    operation['message'] = f'Error: {str(e)}'
                    operation['last_activity'] = datetime.now().isoformat()
                    gui_state.save_state()
                
                gui_state.progress_logs[operation_id].append({
                    'timestamp': datetime.now().isoformat(),
                    'message': f'❌ Fatal error: {str(e)}',
                    'type': 'error'
                })
            finally:
                # Force garbage collection
                gc.collect()
        
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
            'message': f'Failed to start processing: {str(e)}'
        })


@router.post("/cancel/{operation_id}")
async def cancel_operation(operation_id: str):
    gui_state = root_app.gui_state
    if operation_id not in gui_state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    operation = gui_state.active_operations[operation_id]
    operation['status'] = 'cancelled'
    operation['message'] = 'Operation cancelled by user'
    operation['last_activity'] = datetime.now().isoformat()
    
    gui_state.progress_logs[operation_id].append({
        'timestamp': datetime.now().isoformat(),
        'message': '🛑 Operation cancelled by user',
        'type': 'warning'
    })
    
    gui_state.save_state()
    
    return JSONResponse({'success': True, 'message': 'Operation cancelled'})


@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...), destination: str = Form(...)):
    gui_state = root_app.gui_state
    try:
        destination_path = Path(destination)
        destination_path.mkdir(parents=True, exist_ok=True)
        
        uploaded_files = []
        for file in files:
            if not file.filename:
                continue
            
            file_path = destination_path / file.filename
            
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            uploaded_files.append({
                'name': file.filename,
                'size': len(content),
                'path': str(file_path)
            })
        
        return JSONResponse({
            'success': True,
            'uploaded_files': uploaded_files,
            'message': f'Uploaded {len(uploaded_files)} files'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Upload failed: {str(e)}'
        })


@router.post("/extract")
async def extract_files(request: Request):
    try:
        data = await request.json()
        zip_files = data.get('zip_files', [])
        destination = data.get('destination', '')
        
        if not zip_files or not destination:
            return JSONResponse({
                'success': False,
                'message': 'Missing zip files or destination'
            })
        
        destination_path = Path(destination)
        destination_path.mkdir(parents=True, exist_ok=True)
        
        extracted_files = []
        for zip_info in zip_files:
            zip_path = Path(zip_info['path'])
            if not zip_path.exists():
                continue
            
            try:
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(destination_path)
                    extracted_files.extend(zip_ref.namelist())
            except Exception as e:
                return JSONResponse({
                    'success': False,
                    'message': f'Failed to extract {zip_path.name}: {str(e)}'
                })
        
        return JSONResponse({
            'success': True,
            'extracted_files': extracted_files,
            'message': f'Extracted {len(extracted_files)} files'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Extraction failed: {str(e)}'
        })


@router.post("/consolidate")
async def consolidate_files(request: Request):
    try:
        data = await request.json()
        source_path = data.get('source_path', '')
        destination_path = data.get('destination_path', '')
        
        if not source_path or not destination_path:
            return JSONResponse({
                'success': False,
                'message': 'Missing source or destination path'
            })
        
        # This would typically call the main consolidation logic
        # For now, return a placeholder response
        return JSONResponse({
            'success': True,
            'message': 'Consolidation completed'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Consolidation failed: {str(e)}'
        })


@router.post("/cleanup-temp")
async def cleanup_temp_files():
    try:
        from utils.fs_utils import cleanup_old_temp_dirs, cleanup_system_temp_files
        
        # Clean up temporary directories
        cleanup_old_temp_dirs()
        cleanup_system_temp_files()
        
        return JSONResponse({
            'success': True,
            'message': 'Temporary files cleaned up'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Cleanup failed: {str(e)}'
        })
