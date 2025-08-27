from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# Import from the main gui_server module
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
import gui_server as root_app

router = APIRouter()


@router.get("/logs/{operation_id}")
async def get_logs(operation_id: str, limit: int = 100):
    gui_state = root_app.gui_state
    if operation_id not in gui_state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    logs = gui_state.progress_logs.get(operation_id, [])
    
    # Return the most recent logs
    recent_logs = logs[-limit:] if len(logs) > limit else logs
    
    return JSONResponse({
        'logs': recent_logs,
        'total_logs': len(logs),
        'operation_id': operation_id
    })


@router.get("/recovery-info")
async def get_recovery_info():
    gui_state = root_app.gui_state
    recovery_info = gui_state.get_recovery_info()
    return JSONResponse(recovery_info)
