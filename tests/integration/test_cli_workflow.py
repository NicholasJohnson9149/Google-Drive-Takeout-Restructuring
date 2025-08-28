"""
Integration tests for CLI workflow
"""
from __future__ import annotations

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.cli import main, handle_extract, handle_rebuild, handle_verify
from tests.utils import (
    create_test_zip, create_takeout_structure, TempDirectoryManager,
    assert_directory_structure, compare_directories
)


class TestCLIWorkflow:
    """Integration tests for complete CLI workflow"""
    
    def test_cli_help(self):
        """Test CLI help output"""
        with patch('sys.argv', ['cli.py', '--help']):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0 or exc.value.code is None
    
    def test_cli_extract_command_help(self):
        """Test extract command help"""
        with patch('sys.argv', ['cli.py', 'extract', '--help']):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0 or exc.value.code is None
    
    def test_cli_rebuild_command_help(self):
        """Test rebuild command help"""
        with patch('sys.argv', ['cli.py', 'rebuild', '--help']):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0 or exc.value.code is None
    
    def test_cli_verify_command_help(self):
        """Test verify command help"""
        with patch('sys.argv', ['cli.py', 'verify', '--help']):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0 or exc.value.code is None
    
    @pytest.mark.slow
    def test_full_cli_workflow(self):
        """Test complete CLI workflow: extract -> rebuild -> verify"""
        with TempDirectoryManager() as temp_dir:
            # Step 1: Create test takeout ZIP
            zip_file = temp_dir / "takeout.zip"
            test_files = {
                "Takeout/Drive/document.txt": "Test document content",
                "Takeout/Drive/Folder1/file1.txt": "File in folder",
                "Takeout/Drive/Folder2/file2.txt": "Another file"
            }
            create_test_zip(zip_file, test_files)
            
            # Step 2: Extract ZIP file
            extract_dir = temp_dir / "extracted"
            with patch('sys.argv', [
                'cli.py', 'extract',
                str(zip_file),
                '--output', str(extract_dir)
            ]):
                result = main()
                assert result == 0
            
            # Verify extraction
            assert extract_dir.exists()
            assert (extract_dir / "Takeout" / "Drive" / "document.txt").exists()
            
            # Step 3: Rebuild Drive structure
            output_dir = temp_dir / "rebuilt"
            with patch('sys.argv', [
                'cli.py', 'rebuild',
                str(extract_dir),
                str(output_dir),
                '--force'  # Skip confirmation
            ]):
                result = main()
                assert result == 0
            
            # Verify rebuild
            assert output_dir.exists()
            assert (output_dir / "document.txt").exists()
            assert (output_dir / "Folder1" / "file1.txt").exists()
            
            # Step 4: Verify reconstruction
            with patch('sys.argv', [
                'cli.py', 'verify',
                str(extract_dir / "Takeout"),  # Verify against the actual Takeout directory
                str(output_dir)
            ]):
                result = main()
                # Should pass verification
                assert result == 0
    
    def test_cli_extract_nonexistent_file(self):
        """Test extracting non-existent file"""
        with TempDirectoryManager() as temp_dir:
            nonexistent = temp_dir / "nonexistent.zip"
            
            with patch('sys.argv', [
                'cli.py', 'extract',
                str(nonexistent)
            ]):
                result = main()
                assert result == 1  # Should fail
    
    def test_cli_rebuild_dry_run(self):
        """Test rebuild with dry run mode"""
        with TempDirectoryManager() as temp_dir:
            # Create test structure
            source_dir = temp_dir / "source"
            create_takeout_structure(source_dir)
            output_dir = temp_dir / "output"
            
            with patch('sys.argv', [
                'cli.py', 'rebuild',
                str(source_dir),
                str(output_dir),
                '--dry-run'
            ]):
                result = main()
                assert result == 0
            
            # Output directory should not have files (dry run)
            assert not output_dir.exists() or len(list(output_dir.rglob('*'))) == 0
    
    def test_cli_verify_mismatch(self):
        """Test verification with mismatched directories"""
        with TempDirectoryManager() as temp_dir:
            # Create two different structures
            dir1 = temp_dir / "dir1"
            dir2 = temp_dir / "dir2"
            
            (dir1 / "file1.txt").parent.mkdir(parents=True, exist_ok=True)
            (dir1 / "file1.txt").write_text("content1")
            
            (dir2 / "file2.txt").parent.mkdir(parents=True, exist_ok=True)
            (dir2 / "file2.txt").write_text("content2")
            
            with patch('sys.argv', [
                'cli.py', 'verify',
                str(dir1),
                str(dir2)
            ]):
                result = main()
                assert result == 1  # Should fail verification
    
    def test_cli_verbose_mode(self):
        """Test CLI with verbose mode"""
        with TempDirectoryManager() as temp_dir:
            source = temp_dir / "source"
            create_takeout_structure(source)
            output = temp_dir / "output"
            
            with patch('sys.argv', [
                'cli.py', '--verbose', 'rebuild',
                str(source),
                str(output),
                '--dry-run'
            ]):
                with patch('app.cli.setup_logging') as mock_logging:
                    result = main()
                    assert result == 0
                    mock_logging.assert_called_once_with(True)
    
    def test_cli_with_config_file(self):
        """Test CLI with custom configuration file"""
        with TempDirectoryManager() as temp_dir:
            # Create a config file
            config_file = temp_dir / "config.json"
            config_file.write_text('{"debug": true}')
            
            source = temp_dir / "source"
            create_takeout_structure(source)
            output = temp_dir / "output"
            
            with patch('sys.argv', [
                'cli.py', '--config', str(config_file),
                'rebuild', str(source), str(output), '--dry-run'
            ]):
                with patch('app.cli.load_config') as mock_load:
                    result = main()
                    assert result == 0
                    mock_load.assert_called_once_with(str(config_file))
    
    def test_cli_invalid_command(self):
        """Test CLI with invalid command"""
        with patch('sys.argv', ['cli.py', 'invalid_command']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    def test_cli_no_command(self):
        """Test CLI with no command"""
        with patch('sys.argv', ['cli.py']):
            result = main()
            assert result == 1
    
    @pytest.mark.parametrize("command,args,expected_func", [
        ('extract', ['input.zip'], 'handle_extract'),
        ('rebuild', ['source', 'dest'], 'handle_rebuild'),
        ('verify', ['source', 'dest'], 'handle_verify')
    ])
    def test_cli_command_dispatch(self, command, args, expected_func):
        """Test that CLI commands are dispatched correctly"""
        with TempDirectoryManager() as temp_dir:
            # Create dummy paths
            full_args = ['cli.py', command]
            for arg in args:
                if '.' in arg:
                    # Looks like a file
                    path = temp_dir / arg
                    if arg.endswith('.zip'):
                        create_test_zip(path, {"test": "data"})
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.touch()
                    full_args.append(str(path))
                else:
                    # Directory
                    path = temp_dir / arg
                    path.mkdir(parents=True, exist_ok=True)
                    full_args.append(str(path))
            
            with patch('sys.argv', full_args):
                with patch(f'app.cli.{expected_func}') as mock_handler:
                    mock_handler.return_value = 0
                    result = main()
                    assert mock_handler.called
                    assert result == 0