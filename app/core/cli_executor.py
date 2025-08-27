"""
CLI Executor Bridge for GUI Integration
Executes CLI commands and streams progress back to the GUI
"""
from __future__ import annotations

import subprocess
import threading
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import logging


class CLIExecutor:
    """Bridge between GUI and CLI for executing commands with progress tracking"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_processes: Dict[str, subprocess.Popen] = {}
    
    def build_extract_command(self, zip_path: str, output_path: str, verbose: bool = True) -> List[str]:
        """Build CLI command for extracting takeout ZIP files"""
        cmd = ["python", "-m", "app.cli"]
        
        if verbose:
            cmd.append("--verbose")
        
        cmd.extend(["extract", str(zip_path), "--output", str(output_path)])
        
        return cmd
    
    def build_rebuild_command(self, 
                            input_path: str, 
                            output_path: str, 
                            options: Dict[str, Any]) -> List[str]:
        """Build CLI command for rebuilding Drive structure"""
        cmd = ["python", "-m", "app.cli"]
        
        # Add verbose flag for detailed output
        if options.get('verbose', True):
            cmd.append("--verbose")
        
        # Add the rebuild command
        cmd.append("rebuild")
        
        # Add input and output paths
        cmd.extend([str(input_path), str(output_path)])
        
        # Add optional flags
        if options.get('dry_run', False):
            cmd.append("--dry-run")
        
        if options.get('force', False):
            cmd.append("--force")
        
        if options.get('verify', False):
            cmd.append("--verify")
        
        return cmd
    
    def build_verify_command(self, source_path: str, dest_path: str, verbose: bool = True) -> List[str]:
        """Build CLI command for verifying reconstruction"""
        cmd = ["python", "-m", "app.cli"]
        
        if verbose:
            cmd.append("--verbose")
        
        cmd.extend(["verify", str(source_path), str(dest_path)])
        
        return cmd
    
    def execute_with_progress(self, 
                            cmd: List[str], 
                            operation_id: str,
                            progress_callback: Optional[Callable[[Dict], None]] = None) -> int:
        """
        Execute CLI command and stream progress to callback
        
        Args:
            cmd: Command to execute
            operation_id: Unique ID for this operation
            progress_callback: Function to call with progress updates
            
        Returns:
            Exit code of the process
        """
        try:
            self.logger.info(f"Executing command: {' '.join(cmd)}")
            
            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Store the process for potential cancellation
            self.active_processes[operation_id] = process
            
            # Parse output and send progress updates
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                    
                line = line.strip()
                if not line:
                    continue
                
                # Parse progress from CLI output
                progress_data = self._parse_progress_line(line)
                
                # Send to callback
                if progress_callback:
                    progress_callback(progress_data)
                
                # Also log it
                self.logger.debug(f"CLI output: {line}")
            
            # Wait for process to complete
            return_code = process.wait()
            
            # Clean up
            if operation_id in self.active_processes:
                del self.active_processes[operation_id]
            
            # Send completion update
            if progress_callback:
                progress_callback({
                    'type': 'status',
                    'status': 'completed' if return_code == 0 else 'failed',
                    'message': 'Process completed' if return_code == 0 else f'Process failed with code {return_code}',
                    'return_code': return_code
                })
            
            return return_code
            
        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            
            # Clean up
            if operation_id in self.active_processes:
                del self.active_processes[operation_id]
            
            # Send error update
            if progress_callback:
                progress_callback({
                    'type': 'error',
                    'status': 'failed',
                    'message': str(e)
                })
            
            return -1
    
    def _parse_progress_line(self, line: str) -> Dict[str, Any]:
        """Parse a line of CLI output to extract progress information"""
        progress_data = {
            'type': 'log',
            'message': line,
            'raw': line
        }
        
        # Look for percentage patterns (e.g., "45.2%", "Processing: 50%")
        percent_match = re.search(r'(\d+\.?\d*)\s*%', line)
        if percent_match:
            progress_data['type'] = 'progress'
            progress_data['percent'] = float(percent_match.group(1))
        
        # Look for file processing patterns
        if 'Processing file' in line or 'Processing:' in line:
            progress_data['type'] = 'progress'
            # Extract filename if present
            file_match = re.search(r'Processing[:\s]+(.+)', line)
            if file_match:
                progress_data['current_file'] = file_match.group(1).strip()
        
        # Look for status keywords
        if any(keyword in line.lower() for keyword in ['starting', 'extracting', 'rebuilding', 'verifying']):
            progress_data['type'] = 'status'
            progress_data['operation'] = line
        
        # Look for statistics
        if 'files' in line.lower() or 'copied' in line.lower() or 'skipped' in line.lower():
            progress_data['type'] = 'stats'
            
            # Try to extract numbers
            numbers = re.findall(r'\d+', line)
            if numbers:
                progress_data['stats'] = {
                    'value': int(numbers[0]) if numbers else 0,
                    'description': line
                }
        
        # Look for errors
        if any(keyword in line.lower() for keyword in ['error', 'failed', 'exception']):
            progress_data['type'] = 'error'
            progress_data['level'] = 'error'
        
        # Look for warnings
        if any(keyword in line.lower() for keyword in ['warning', 'warn']):
            progress_data['type'] = 'warning'
            progress_data['level'] = 'warning'
        
        # Look for success indicators
        if any(keyword in line.lower() for keyword in ['complete', 'success', 'done', 'finished']):
            progress_data['type'] = 'success'
            progress_data['level'] = 'success'
        
        return progress_data
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a running operation"""
        if operation_id in self.active_processes:
            try:
                process = self.active_processes[operation_id]
                process.terminate()
                
                # Give it time to terminate gracefully
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    process.kill()
                
                # Clean up
                del self.active_processes[operation_id]
                
                self.logger.info(f"Cancelled operation {operation_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error cancelling operation {operation_id}: {e}")
                return False
        
        return False
    
    def execute_async(self, 
                     cmd: List[str], 
                     operation_id: str,
                     progress_callback: Optional[Callable[[Dict], None]] = None) -> threading.Thread:
        """Execute command in a background thread"""
        thread = threading.Thread(
            target=self.execute_with_progress,
            args=(cmd, operation_id, progress_callback),
            daemon=True
        )
        thread.start()
        return thread