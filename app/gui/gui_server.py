from __future__ import annotations

import os
import asyncio
import uvicorn
from pathlib import Path
import webbrowser
import threading
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routers.paths import router as paths_router
from .routers.progress import router as progress_router
from .routers.processing import router as processing_router
from .routers.logs import router as logs_router
from .routers.system import router as system_router

# Create FastAPI app
app = FastAPI(
    title="Google Drive Takeout Rebuilder",
    description="Reconstruct Google Drive folder structure from takeout files",
    version="1.0.0"
)

# Get template and static directories
template_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

# Mount static files
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup Jinja2 templates
if template_dir.exists():
    templates = Jinja2Templates(directory=template_dir)

# Include routers
app.include_router(paths_router, prefix="/api")
app.include_router(progress_router, prefix="/api")
app.include_router(processing_router, prefix="/api")
app.include_router(logs_router, prefix="/api")
app.include_router(system_router, prefix="/api")

# Root route - serve the main page
@app.get("/")
async def root():
    """Serve the main GUI page"""
    from fastapi import Request
    from fastapi.responses import HTMLResponse
    
    # Create a mock request for template rendering
    class MockRequest:
        def __init__(self):
            self.url = "http://localhost:8000"
    
    request = MockRequest()
    
    # Simple HTML if no template exists
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Google Drive Takeout Rebuilder</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; }
            .status { padding: 20px; border: 1px solid #ddd; margin: 20px 0; }
            button { background: #007bff; color: white; border: none; padding: 10px 20px; cursor: pointer; }
            button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🗂️ Google Drive Takeout Rebuilder</h1>
                <p>Reconstruct your Google Drive folder structure from takeout files</p>
            </div>
            <div class="status">
                <h2>GUI is Running!</h2>
                <p>The web server is successfully running. The full GUI interface would normally be served from templates.</p>
                <p>For now, you can use the CLI interface:</p>
                <pre>takeout-rebuilder --help</pre>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


def open_browser(port: int = 8000):
    """Open browser after a short delay"""
    time.sleep(1.5)  # Wait for server to start
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass  # Fail silently if browser can't be opened


def run():
    """Start the GUI server"""
    port = 8000
    
    print("🚀 Starting Google Drive Takeout Rebuilder GUI...")
    print(f"🌐 Server will be available at: http://localhost:{port}")
    print("⏳ Starting server...")
    
    # Start browser in background thread
    browser_thread = threading.Thread(target=open_browser, args=(port,))
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start the server
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=port, 
        log_level="info", 
        access_log=False
    )


__all__ = ["run"]


