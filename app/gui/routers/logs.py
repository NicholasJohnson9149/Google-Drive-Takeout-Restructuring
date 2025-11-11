from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# Import from centralized state (no more circular dependency!)
from app.gui.state import gui_state

router = APIRouter()


@router.get("/logs/{operation_id}")
async def get_logs(operation_id: str, limit: int = 100):
    """Get logs for a specific operation"""
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
