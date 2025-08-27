from __future__ import annotations

import os
import subprocess
import platform
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

# Import from the main gui_server module
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
import gui_server as root_app

router = APIRouter()


@router.post("/open-folder")
async def open_folder(request: Request):
    try:
        data = await request.json()
        folder_path = data.get('path', '')
        
        if not folder_path:
            return JSONResponse({
                'success': False,
                'message': 'No folder path provided'
            })
        
        folder = Path(folder_path)
        if not folder.exists():
            return JSONResponse({
                'success': False,
                'message': f'Folder does not exist: {folder_path}'
            })
        
        if not folder.is_dir():
            return JSONResponse({
                'success': False,
                'message': f'Path is not a directory: {folder_path}'
            })
        
        # Open folder in the system file manager
        system = platform.system().lower()
        
        try:
            if system == 'darwin':  # macOS
                subprocess.run(['open', str(folder)], check=True)
            elif system == 'windows':  # Windows
                os.startfile(str(folder))
            else:  # Linux and others
                subprocess.run(['xdg-open', str(folder)], check=True)
            
            return JSONResponse({
                'success': True,
                'message': f'Opened folder: {folder_path}'
            })
            
        except subprocess.CalledProcessError as e:
            return JSONResponse({
                'success': False,
                'message': f'Failed to open folder: {str(e)}'
            })
        except Exception as e:
            return JSONResponse({
                'success': False,
                'message': f'Error opening folder: {str(e)}'
            })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'message': f'Request failed: {str(e)}'
        })
