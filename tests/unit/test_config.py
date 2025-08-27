"""
Unit tests for the configuration module
"""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from app.config import (
    AppConfig, ServerConfig, PathConfig, ProcessingConfig,
    UIConfig, SecurityConfig, get_dev_config, get_prod_config,
    get_test_config, load_config, get_temp_dir, get_log_dir,
    is_debug, is_path_safe
)


class TestServerConfig:
    """Test cases for ServerConfig"""
    
    def test_default_values(self):
        """Test default server configuration values"""
        config = ServerConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.log_level == "info"
        assert config.access_log is False
        assert config.reload is False
    
    def test_custom_values(self):
        """Test custom server configuration values"""
        config = ServerConfig(
            host="0.0.0.0",
            port=8080,
            log_level="debug",
            reload=True
        )
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.log_level == "debug"
        assert config.reload is True


class TestPathConfig:
    """Test cases for PathConfig"""
    
    def test_default_paths(self):
        """Test default path configuration"""
        config = PathConfig()
        assert config.temp_dir == Path.home() / "Downloads" / "takeout_temp"
        assert config.log_dir == Path.home() / "Desktop" / "takeout_logs"
        assert config.upload_dir == Path.home() / "Downloads" / "takeout_uploads"
    
    def test_custom_paths(self):
        """Test custom path configuration"""
        custom_temp = Path("/custom/temp")
        custom_log = Path("/custom/logs")
        custom_upload = Path("/custom/uploads")
        
        config = PathConfig(
            temp_dir=custom_temp,
            log_dir=custom_log,
            upload_dir=custom_upload
        )
        assert config.temp_dir == custom_temp
        assert config.log_dir == custom_log
        assert config.upload_dir == custom_upload


class TestProcessingConfig:
    """Test cases for ProcessingConfig"""
    
    def test_default_values(self):
        """Test default processing configuration"""
        config = ProcessingConfig()
        assert config.chunk_size == 1024 * 1024  # 1MB
        assert config.max_file_size == 10 * 1024 * 1024 * 1024  # 10GB
        assert config.verify_copies is False
        assert config.max_concurrent_operations == 1
        assert config.hang_detection_timeout == 5
        assert config.operation_timeout == 180
    
    def test_custom_values(self):
        """Test custom processing configuration"""
        config = ProcessingConfig(
            chunk_size=2048,
            verify_copies=True,
            max_concurrent_operations=4
        )
        assert config.chunk_size == 2048
        assert config.verify_copies is True
        assert config.max_concurrent_operations == 4


class TestUIConfig:
    """Test cases for UIConfig"""
    
    def test_default_values(self):
        """Test default UI configuration"""
        config = UIConfig()
        assert config.progress_update_interval == 1000
        assert config.log_display_limit == 100
        assert config.auto_refresh_enabled is True
        assert config.theme == "light"
    
    def test_custom_values(self):
        """Test custom UI configuration"""
        config = UIConfig(
            progress_update_interval=500,
            log_display_limit=50,
            theme="dark"
        )
        assert config.progress_update_interval == 500
        assert config.log_display_limit == 50
        assert config.theme == "dark"


class TestSecurityConfig:
    """Test cases for SecurityConfig"""
    
    def test_default_values(self):
        """Test default security configuration"""
        config = SecurityConfig()
        assert config.max_upload_size == 100 * 1024 * 1024  # 100MB
        assert '.zip' in config.allowed_extensions
        assert '.tar' in config.allowed_extensions
        assert '/System' in config.forbidden_paths
        assert '/Library' in config.forbidden_paths
        assert str(Path.home() / "Desktop") in config.safe_temp_locations
    
    def test_custom_values(self):
        """Test custom security configuration"""
        custom_extensions = {'.custom'}
        custom_forbidden = {'/custom/forbidden'}
        
        config = SecurityConfig(
            max_upload_size=200 * 1024 * 1024,
            allowed_extensions=custom_extensions,
            forbidden_paths=custom_forbidden
        )
        assert config.max_upload_size == 200 * 1024 * 1024
        assert config.allowed_extensions == custom_extensions
        assert config.forbidden_paths == custom_forbidden


class TestAppConfig:
    """Test cases for AppConfig"""
    
    def test_default_app_config(self):
        """Test default application configuration"""
        config = AppConfig()
        assert config.debug is False
        assert config.testing is False
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.paths, PathConfig)
        assert isinstance(config.processing, ProcessingConfig)
        assert isinstance(config.ui, UIConfig)
        assert isinstance(config.security, SecurityConfig)
    
    @patch.dict(os.environ, {'HOST': '0.0.0.0', 'PORT': '9000'})
    def test_env_override_server(self):
        """Test environment variable override for server settings"""
        config = AppConfig()
        assert config.server.host == '0.0.0.0'
        assert config.server.port == 9000
    
    @patch.dict(os.environ, {'DEBUG': 'true'})
    def test_env_override_debug(self):
        """Test environment variable override for debug mode"""
        config = AppConfig()
        assert config.debug is True
        assert config.server.reload is True
        assert config.server.log_level == "debug"
    
    @patch.dict(os.environ, {'TESTING': 'yes'})
    def test_env_override_testing(self):
        """Test environment variable override for testing mode"""
        config = AppConfig()
        assert config.testing is True
    
    def test_ensure_directories(self, tmp_path, monkeypatch):
        """Test directory creation"""
        # Use temporary paths
        temp_dir = tmp_path / "temp"
        log_dir = tmp_path / "logs"
        upload_dir = tmp_path / "uploads"
        
        config = AppConfig()
        config.paths.temp_dir = temp_dir
        config.paths.log_dir = log_dir
        config.paths.upload_dir = upload_dir
        
        # Ensure directories don't exist initially
        assert not temp_dir.exists()
        assert not log_dir.exists()
        assert not upload_dir.exists()
        
        # Create directories
        config.ensure_directories()
        
        # Verify directories were created
        assert temp_dir.exists()
        assert log_dir.exists()
        assert upload_dir.exists()


class TestConfigFactories:
    """Test cases for configuration factory functions"""
    
    def test_get_dev_config(self):
        """Test development configuration"""
        config = get_dev_config()
        assert config.debug is True
        assert config.server.reload is True
        assert config.server.log_level == "debug"
        assert config.ui.auto_refresh_enabled is True
    
    def test_get_prod_config(self):
        """Test production configuration"""
        config = get_prod_config()
        assert config.debug is False
        assert config.server.reload is False
        assert config.server.log_level == "warning"
        assert config.processing.verify_copies is True
    
    def test_get_test_config(self):
        """Test testing configuration"""
        config = get_test_config()
        assert config.testing is True
        assert config.debug is True
        assert config.server.port == 8001
        assert config.paths.temp_dir == Path("/tmp/takeout_test")
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'production'})
    def test_load_config_production(self):
        """Test loading production configuration"""
        config = load_config()
        assert config.debug is False
        assert config.server.log_level == "warning"
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'testing'})
    def test_load_config_testing(self):
        """Test loading testing configuration"""
        config = load_config()
        assert config.testing is True
        assert config.server.port == 8001
    
    def test_load_config_default(self):
        """Test loading default (development) configuration"""
        config = load_config()
        assert config.debug is True
        assert config.server.reload is True
    
    def test_load_config_explicit(self):
        """Test loading configuration with explicit environment"""
        config = load_config('production')
        assert config.debug is False
        
        config = load_config('testing')
        assert config.testing is True
        
        config = load_config('development')
        assert config.debug is True


class TestConvenienceFunctions:
    """Test cases for convenience functions"""
    
    def test_get_temp_dir(self):
        """Test getting temporary directory"""
        from app.config import config
        temp_dir = get_temp_dir()
        assert temp_dir == config.paths.temp_dir
    
    def test_get_log_dir(self):
        """Test getting log directory"""
        from app.config import config
        log_dir = get_log_dir()
        assert log_dir == config.paths.log_dir
    
    def test_is_debug(self):
        """Test checking debug mode"""
        from app.config import config
        debug = is_debug()
        assert debug == config.debug
    
    def test_is_path_safe(self):
        """Test path safety check"""
        # Safe paths
        assert is_path_safe(Path.home() / "Documents" / "test") is True
        assert is_path_safe(Path("/tmp/test")) is True
        
        # Unsafe paths
        assert is_path_safe(Path("/System/Library")) is False
        assert is_path_safe(Path("/usr/bin")) is False
        assert is_path_safe(Path("/sbin/init")) is False
        assert is_path_safe(Path("/Applications/System.app")) is False