from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# Import from the main gui_server module
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
import gui_server as root_app

router = APIRouter()


@router.get("/progress/{operation_id}")
async def get_progress(operation_id: str):
    gui_state = root_app.gui_state  # reuse instance
    if operation_id not in gui_state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")

    hung_ops = gui_state.check_for_hung_operations(timeout_minutes=5)
    if operation_id in hung_ops:
        gui_state.mark_operation_as_hung(operation_id)

    operation = gui_state.active_operations[operation_id]
    recent_logs = gui_state.progress_logs.get(operation_id, [])[-10:]

    now = datetime.now()
    last_activity_str = operation.get('last_activity', operation.get('start_time'))
    minutes_since_activity = 0
    if last_activity_str:
        try:
            last_activity = datetime.fromisoformat(last_activity_str)
            minutes_since_activity = (now - last_activity).total_seconds() / 60
        except Exception:
            pass

    payload = {
        'operation': operation,
        'recent_logs': recent_logs,
        'hang_detection': {
            'minutes_since_activity': round(minutes_since_activity, 1),
            'is_potentially_hung': operation.get('status') == 'hung',
            'last_activity': last_activity_str
        }
    }
    return JSONResponse(payload)


