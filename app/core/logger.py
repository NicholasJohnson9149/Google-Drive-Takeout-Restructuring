"""
Centralized logging for the Google Drive Takeout Consolidator
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any


class ProgressLogger:
    """Centralized logger that handles both file logging and progress callbacks"""
    
    def __init__(self, name: str = "takeout_consolidator", log_file: Optional[Path] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (optional)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        # Progress callback for GUI integration
        self.progress_callback: Optional[Callable] = None
        self.operation_id: Optional[str] = None
    
    def set_progress_callback(self, callback: Callable, operation_id: str = None):
        """Set callback function for progress updates"""
        self.progress_callback = callback
        self.operation_id = operation_id
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message)
        if self.progress_callback:
            self.progress_callback({
                'type': 'log',
                'message': message,
                'level': 'info',
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message)
        if self.progress_callback:
            self.progress_callback({
                'type': 'log',
                'message': f'⚠️ {message}',
                'level': 'warning',
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message)
        if self.progress_callback:
            self.progress_callback({
                'type': 'log',
                'message': f'🐛 {message}',
                'level': 'debug',
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message)
        if self.progress_callback:
            self.progress_callback({
                'type': 'log',
                'message': f'❌ {message}',
                'level': 'error',
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def success(self, message: str, **kwargs):
        """Log success message"""
        self.logger.info(message)
        if self.progress_callback:
            self.progress_callback({
                'type': 'log',
                'message': f'✅ {message}',
                'level': 'success',
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def progress(self, percent: float, current_file: str = '', operation: str = '', **kwargs):
        """Update progress information"""
        if self.progress_callback:
            self.progress_callback({
                'type': 'progress',
                'percent': percent,
                'current_file': current_file,
                'operation': operation,
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def stats(self, stats: Dict[str, Any], **kwargs):
        """Update statistics"""
        if self.progress_callback:
            self.progress_callback({
                'type': 'stats',
                'stats': stats,
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })
    
    def status(self, status: str, message: str = '', **kwargs):
        """Update operation status"""
        if self.progress_callback:
            self.progress_callback({
                'type': 'status',
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                **kwargs
            })


def get_logger(name: str = "takeout_consolidator", log_file: Optional[Path] = None) -> ProgressLogger:
    """Get or create a logger instance"""
    return ProgressLogger(name, log_file)
