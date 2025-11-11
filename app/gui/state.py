#!/usr/bin/env python3
"""
GUI State Management
Centralized state management for the GUI application with persistence
"""
from __future__ import annotations

import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


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


# Global state instance - single source of truth
gui_state = GUIState()
