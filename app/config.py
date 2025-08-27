"""
Configuration module for Google Drive Takeout Consolidator
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel


class ServerConfig(BaseModel):
    """Server configuration settings"""
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"
    access_log: bool = False
    reload: bool = False  # Set to True for development


class PathConfig(BaseModel):
    """Default path configurations"""
    temp_dir: Optional[Path] = None
    log_dir: Optional[Path] = None
    upload_dir: Optional[Path] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        
        # Set default paths if not provided
        if self.temp_dir is None:
            self.temp_dir = Path.home() / "Downloads" / "takeout_temp"
        
        if self.log_dir is None:
            self.log_dir = Path.home() / "Desktop" / "takeout_logs"
        
        if self.upload_dir is None:
            self.upload_dir = Path.home() / "Downloads" / "takeout_uploads"


class ProcessingConfig(BaseModel):
    """Processing configuration settings"""
    chunk_size: int = 1024 * 1024  # 1MB chunks for large file copying
    max_file_size: int = 10 * 1024 * 1024 * 1024  # 10GB max file size
    verify_copies: bool = False  # Whether to verify file copies by default
    max_concurrent_operations: int = 1  # Max concurrent processing operations
    hang_detection_timeout: int = 5  # Minutes before considering operation hung
    operation_timeout: int = 180  # Minutes before hard stop (3 hours)


class UIConfig(BaseModel):
    """UI configuration settings"""
    progress_update_interval: int = 1000  # Milliseconds
    log_display_limit: int = 100  # Max logs to display in UI
    auto_refresh_enabled: bool = True
    theme: str = "light"  # light, dark, auto


class SecurityConfig(BaseModel):
    """Security configuration settings"""
    max_upload_size: int = 100 * 1024 * 1024  # 100MB max upload
    allowed_extensions: set = {'.zip', '.tar', '.gz', '.7z'}
    forbidden_paths: set = {'/System', '/Library', '/usr', '/bin', '/sbin', '/Applications'}
    safe_temp_locations: set = None
    
    def __init__(self, **data):
        super().__init__(**data)
        
        if self.safe_temp_locations is None:
            self.safe_temp_locations = {
                str(Path.home() / "Desktop"),
                str(Path.home() / "Downloads"),
                str(Path.home() / "Documents"),
                "/tmp",
                str(Path.cwd())
            }


class AppConfig(BaseModel):
    """Main application configuration"""
    server: ServerConfig = ServerConfig()
    paths: PathConfig = PathConfig()
    processing: ProcessingConfig = ProcessingConfig()
    ui: UIConfig = UIConfig()
    security: SecurityConfig = SecurityConfig()
    
    # Environment
    debug: bool = False
    testing: bool = False
    
    def __init__(self, **data):
        super().__init__(**data)
        
        # Override with environment variables
        self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Server settings
        if os.getenv('HOST'):
            self.server.host = os.getenv('HOST')
        if os.getenv('PORT'):
            self.server.port = int(os.getenv('PORT'))
        if os.getenv('LOG_LEVEL'):
            self.server.log_level = os.getenv('LOG_LEVEL')
        
        # Debug mode
        if os.getenv('DEBUG'):
            self.debug = os.getenv('DEBUG').lower() in ('true', '1', 'yes')
            if self.debug:
                self.server.reload = True
                self.server.log_level = "debug"
        
        # Testing mode
        if os.getenv('TESTING'):
            self.testing = os.getenv('TESTING').lower() in ('true', '1', 'yes')
    
    def ensure_directories(self):
        """Ensure all configured directories exist"""
        directories = [
            self.paths.temp_dir,
            self.paths.log_dir,
            self.paths.upload_dir
        ]
        
        for directory in directories:
            if directory:
                directory.mkdir(parents=True, exist_ok=True)


# Global configuration instance
config = AppConfig()

# Development configuration
def get_dev_config() -> AppConfig:
    """Get configuration optimized for development"""
    dev_config = AppConfig()
    dev_config.debug = True
    dev_config.server.reload = True
    dev_config.server.log_level = "debug"
    dev_config.ui.auto_refresh_enabled = True
    return dev_config

# Production configuration
def get_prod_config() -> AppConfig:
    """Get configuration optimized for production"""
    prod_config = AppConfig()
    prod_config.debug = False
    prod_config.server.reload = False
    prod_config.server.log_level = "warning"
    prod_config.processing.verify_copies = True
    return prod_config

# Testing configuration
def get_test_config() -> AppConfig:
    """Get configuration optimized for testing"""
    test_config = AppConfig()
    test_config.testing = True
    test_config.debug = True
    test_config.server.port = 8001  # Different port for tests
    test_config.paths.temp_dir = Path("/tmp/takeout_test")
    test_config.paths.log_dir = Path("/tmp/takeout_test_logs")
    test_config.paths.upload_dir = Path("/tmp/takeout_test_uploads")
    return test_config


def load_config(env: str = None) -> AppConfig:
    """Load configuration based on environment"""
    env = env or os.getenv('ENVIRONMENT', 'development')
    
    if env == 'production':
        return get_prod_config()
    elif env == 'testing':
        return get_test_config()
    else:
        return get_dev_config()


# Convenience functions
def get_temp_dir() -> Path:
    """Get the configured temporary directory"""
    return config.paths.temp_dir

def get_log_dir() -> Path:
    """Get the configured log directory"""
    return config.paths.log_dir

def is_debug() -> bool:
    """Check if debug mode is enabled"""
    return config.debug

def is_path_safe(path: Path) -> bool:
    """Check if a path is safe to operate on"""
    path_str = str(path.resolve())
    return not any(path_str.startswith(forbidden) for forbidden in config.security.forbidden_paths)
