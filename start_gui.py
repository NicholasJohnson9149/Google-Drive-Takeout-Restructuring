#!/usr/bin/env python3
"""
Simple startup script for Google Drive Takeout Consolidator GUI
Automatically installs dependencies and starts the web interface
"""

import subprocess
import sys
import os
import webbrowser
import time
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['fastapi', 'uvicorn', 'jinja2']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    return missing_packages

def install_dependencies():
    """Install missing dependencies"""
    print("📦 Installing dependencies...")
    
    # Install from requirements.txt
    result = subprocess.run([
        sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Dependencies installed successfully")
        return True
    else:
        print(f"❌ Failed to install dependencies: {result.stderr}")
        return False

def start_gui():
    """Start the GUI server"""
    print("🚀 Starting Google Drive Takeout Consolidator GUI...")
    print("=" * 60)
    
    try:
        # Import and start the server
        from gui_server import app
        import uvicorn
        
        # Open browser after a short delay
        def open_browser():
            time.sleep(2)
            webbrowser.open('http://localhost:8000')
        
        import threading
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        print("🌐 Opening web interface at: http://localhost:8000")
        print("📁 Drag your Google Takeout zip files to get started!")
        print("⏹️  Press Ctrl+C to stop the server")
        print("=" * 60)
        
        # Start the server
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="warning",  # Reduce noise
            access_log=False
        )
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye! Server stopped.")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False
    
    return True

def main():
    """Main startup function"""
    print("=" * 60)
    print("🗂️  Google Drive Takeout Consolidator")
    print("   Web GUI Startup")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path('gui_server.py').exists():
        print("❌ Error: gui_server.py not found")
        print("   Please run this script from the project directory")
        sys.exit(1)
    
    # Check dependencies
    missing = check_dependencies()
    if missing:
        print(f"📋 Missing dependencies: {', '.join(missing)}")
        if not install_dependencies():
            print("❌ Failed to install dependencies. Please install manually:")
            print("   pip install -r requirements.txt")
            sys.exit(1)
    else:
        print("✅ All dependencies available")
    
    # Start GUI
    if not start_gui():
        sys.exit(1)

if __name__ == "__main__":
    main()
