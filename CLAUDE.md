# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Google Drive Takeout Consolidator - A Python-based web application that reconstructs Google Drive folder structure from Google Takeout zip files. The app features a FastAPI backend with HTMX frontend for drag-and-drop zip file processing and real-time progress monitoring.

## Key Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start the GUI server (main entry point)
python main.py
# OR directly:
python gui_server.py

# Run tests with coverage
pytest --cov=app tests/

# Run specific test types
pytest -m unit          # Unit tests only  
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Skip slow tests

# Run linting (if needed - no specific linter configured yet)
# Consider adding: ruff, black, or flake8
```

### Environment Setup
```bash
# Option 1: Using conda (if environment.yml exists)
conda env create -f environment.yml
conda activate gdrive-consolidator

# Option 2: Using pip with virtual environment
python -m venv gdrive_env
source gdrive_env/bin/activate  # On Mac/Linux
gdrive_env\Scripts\activate      # On Windows
pip install -r requirements.txt
```

## Architecture

### Core Structure
```
app/
├── core/           # Business logic modules
│   ├── extractor.py    # Handles zip extraction
│   ├── rebuilder.py    # SafeTakeoutReconstructor - main reconstruction logic
│   ├── verifier.py     # File verification utilities
│   └── logger.py       # ProgressLogger with callback support
├── gui/            # Web interface
│   ├── gui_server.py   # FastAPI server setup
│   ├── routers/        # API endpoints (paths, progress, processing, logs, system)
│   ├── templates/      # Jinja2 HTML templates with HTMX
│   └── static/         # CSS styles
└── config.py       # Pydantic-based configuration management
```

### Key Design Patterns

1. **Progress Callbacks**: The `SafeTakeoutReconstructor` accepts progress callbacks that integrate with the GUI for real-time updates.

2. **Router-based API**: FastAPI routers organize endpoints by functionality:
   - `/paths/*` - File path detection and management
   - `/progress/*` - Real-time progress updates  
   - `/processing/*` - Main processing operations
   - `/logs/*` - Log retrieval and display
   - `/system/*` - System operations

3. **Configuration Management**: `app/config.py` uses Pydantic models for type-safe configuration with environment-based overrides.

4. **State Management**: Uses `gui_state.pkl` for persisting GUI state between sessions.

## Important Implementation Notes

1. **File Path Handling**: The app intelligently detects Google Drive paths across different Takeout structures, handling variations in path formats.

2. **Duplicate Handling**: Implements smart duplicate detection with options for renaming or skipping duplicates.

3. **Safety Features**:
   - Dry run mode by default
   - File verification options
   - Comprehensive logging to `takeout_logs/`
   - Manifest generation for potential rollback

4. **GUI Integration**: The legacy `gui_server.py` at root is imported by the refactored `app/gui/gui_server.py` for backward compatibility.

5. **Testing Strategy**: 
   - Unit tests for core modules
   - Integration tests for end-to-end workflows
   - Test fixtures in `tests/fixtures/`
   - 80% minimum coverage requirement (configured in pytest.ini)

## Current Refactoring Status

The project is undergoing refactoring as per PROJECT_REFACTOR_PLAN.md:
- Core functionality has been migrated to `app/core/`
- GUI components organized under `app/gui/`
- Tests restructured under `tests/`
- Legacy files (main_enhanced.py, various backups) still exist but should be removed after verification

## Common Development Tasks

### Adding New Features
1. Implement core logic in `app/core/`
2. Add API endpoints in `app/gui/routers/`
3. Update templates in `app/gui/templates/`
4. Write tests in corresponding `tests/` directories

### Debugging
- Enable debug mode: `DEBUG=true python main.py`
- Check logs in `takeout_logs/` directory
- Use `UVICORN_LOG_LEVEL=debug` for detailed server logs

### Performance Optimization
- Progress updates batch every 100 files
- Chunk size for file operations: 1MB (configurable in config.py)
- Single concurrent operation by default to prevent system overload