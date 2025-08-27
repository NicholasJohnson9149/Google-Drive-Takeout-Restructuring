"""
Unit tests for the ProgressLogger module
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from app.core.logger import ProgressLogger, get_logger


class TestProgressLogger:
    """Test cases for ProgressLogger class"""
    
    def test_logger_creation(self):
        """Test basic logger creation"""
        logger = ProgressLogger("test_logger")
        assert logger.name == "test_logger"
        assert logger.progress_callback is None
        assert logger.operation_id is None
    
    def test_logger_with_file(self, temp_dir):
        """Test logger creation with log file"""
        log_file = temp_dir / "test.log"
        logger = ProgressLogger("test_logger", log_file)
        
        assert logger.name == "test_logger"
        assert log_file.parent.exists()  # Should create parent directory
    
    def test_set_progress_callback(self):
        """Test setting progress callback"""
        logger = ProgressLogger("test")
        callback = Mock()
        
        logger.set_progress_callback(callback, "op_123")
        
        assert logger.progress_callback == callback
        assert logger.operation_id == "op_123"
    
    def test_info_logging(self):
        """Test info level logging"""
        logger = ProgressLogger("test")
        callback = Mock()
        logger.set_progress_callback(callback)
        
        logger.info("Test message")
        
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args['type'] == 'log'
        assert call_args['message'] == "Test message"
        assert call_args['level'] == 'info'
    
    def test_warning_logging(self):
        """Test warning level logging"""
        logger = ProgressLogger("test")
        callback = Mock()
        logger.set_progress_callback(callback)
        
        logger.warning("Warning message")
        
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args['type'] == 'log'
        assert "⚠️ Warning message" in call_args['message']
        assert call_args['level'] == 'warning'
    
    def test_error_logging(self):
        """Test error level logging"""
        logger = ProgressLogger("test")
        callback = Mock()
        logger.set_progress_callback(callback)
        
        logger.error("Error message")
        
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args['type'] == 'log'
        assert "❌ Error message" in call_args['message']
        assert call_args['level'] == 'error'
    
    def test_success_logging(self):
        """Test success level logging"""
        logger = ProgressLogger("test")
        callback = Mock()
        logger.set_progress_callback(callback)
        
        logger.success("Success message")
        
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args['type'] == 'log'
        assert "✅ Success message" in call_args['message']
        assert call_args['level'] == 'success'
    
    def test_progress_update(self):
        """Test progress updates"""
        logger = ProgressLogger("test")
        callback = Mock()
        logger.set_progress_callback(callback)
        
        logger.progress(50.0, "current_file.txt", "Processing files")
        
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args['type'] == 'progress'
        assert call_args['percent'] == 50.0
        assert call_args['current_file'] == "current_file.txt"
        assert call_args['operation'] == "Processing files"
    
    def test_stats_update(self):
        """Test statistics updates"""
        logger = ProgressLogger("test")
        callback = Mock()
        logger.set_progress_callback(callback)
        
        stats = {'total_files': 100, 'processed': 50}
        logger.stats(stats)
        
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args['type'] == 'stats'
        assert call_args['stats'] == stats
    
    def test_status_update(self):
        """Test status updates"""
        logger = ProgressLogger("test")
        callback = Mock()
        logger.set_progress_callback(callback)
        
        logger.status("processing", "Processing files...")
        
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args['type'] == 'status'
        assert call_args['status'] == "processing"
        assert call_args['message'] == "Processing files..."
    
    def test_logging_without_callback(self):
        """Test that logging works without callback (no errors)"""
        logger = ProgressLogger("test")
        
        # Should not raise any exceptions
        logger.info("Test message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.progress(50.0)
        logger.stats({'test': 1})
        logger.status("status", "message")
    
    def test_get_logger_function(self):
        """Test the get_logger convenience function"""
        logger = get_logger("test_function")
        assert isinstance(logger, ProgressLogger)
        assert logger.name == "test_function"
    
    def test_get_logger_with_file(self, temp_dir):
        """Test get_logger with log file"""
        log_file = temp_dir / "function_test.log"
        logger = get_logger("test_function", log_file)
        
        assert isinstance(logger, ProgressLogger)
        assert logger.name == "test_function"
