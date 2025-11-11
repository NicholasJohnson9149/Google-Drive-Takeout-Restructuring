from __future__ import annotations

import os
import asyncio
import uvicorn
from pathlib import Path
import webbrowser
import threading
import time

from fastapi import FastAPI, Request
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

# Include routers (no prefix - templates expect routes at root level)
app.include_router(paths_router)
app.include_router(progress_router)
app.include_router(processing_router)
app.include_router(logs_router)
app.include_router(system_router)

# Root route - serve the main page
@app.get("/")
async def root(request: Request):
    """Serve the main GUI page"""
    from fastapi.responses import HTMLResponse

    try:
        # Try to serve the template if it exists
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        # Fallback to simple HTML if template doesn't exist
        print(f"Warning: Could not load template: {e}")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Google Drive Takeout Rebuilder</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body>
            <h1>Google Drive Takeout Rebuilder</h1>
            <p>Template error: {e}</p>
            <p>Template directory: {template_dir}</p>
            <p>Static directory: {static_dir}</p>
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


