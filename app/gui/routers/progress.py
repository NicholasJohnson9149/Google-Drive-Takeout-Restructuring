from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# Import from centralized state (no more circular dependency!)
from app.gui.state import gui_state

router = APIRouter()


@router.get("/progress/{operation_id}")
async def get_progress(operation_id: str):
    # gui_state is now imported directly at module level
    if operation_id not in gui_state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")

    operation = gui_state.active_operations[operation_id]
    recent_logs = gui_state.progress_logs.get(operation_id, [])[-10:]

    # Calculate hang detection
    now = datetime.now()
    last_activity_str = operation.get('last_activity', operation.get('start_time'))
    minutes_since_activity = 0
    is_potentially_hung = False

    if last_activity_str:
        try:
            last_activity = datetime.fromisoformat(last_activity_str)
            minutes_since_activity = (now - last_activity).total_seconds() / 60
            # Consider hung if no activity for >5 minutes and still processing
            is_potentially_hung = (minutes_since_activity > 5 and
                                  operation.get('status') in ['processing', 'starting'])
        except Exception:
            pass

    payload = {
        'operation': operation,
        'recent_logs': recent_logs,
        'hang_detection': {
            'minutes_since_activity': round(minutes_since_activity, 1),
            'is_potentially_hung': is_potentially_hung,
            'last_activity': last_activity_str
        }
    }
    return JSONResponse(payload)


@router.get("/recovery-info")
async def get_recovery_info():
    """Get recovery information for the client"""
    recovery_info = gui_state.get_recovery_info()
    return JSONResponse(recovery_info)


