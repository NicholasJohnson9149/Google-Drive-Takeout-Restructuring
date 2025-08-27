# 🧑‍💻 Copilot Instructions for Google Drive Takeout Consolidator

## Project Overview
- **Purpose:** Rebuild Google Drive Takeout zips into their original folder structure via a web GUI (FastAPI + HTMX) or CLI.
- **Major Components:**
  - `app/core/`: Extraction, rebuilding, verification, and logging logic
  - `app/gui/`: FastAPI server, routers, templates, static assets
  - `main_enhanced.py`: Core orchestration, supports both GUI and CLI
  - `start_gui.py`: One-click GUI startup
  - `tests/`: Unit and integration tests (pytest)

## Architecture & Data Flow
- **Frontend:** HTMX-driven drag-and-drop UI (`app/gui/templates/`)
- **Backend:** FastAPI (`app/gui/gui_server.py`) routes to core logic
- **Core Logic:** `SafeTakeoutReconstructor` (in `main_enhanced.py` and `app/core/rebuilder.py`) handles extraction, deduplication, verification, and logging
- **Logs & Manifests:** All operations log to `takeout_logs/` (created next to output dir)
- **Progress:** Real-time updates via callbacks and HTMX polling

## Developer Workflows
- **Start GUI:** `python start_gui.py` (auto-installs dependencies)
- **Manual Start:** `pip install -r requirements.txt && python gui_server.py`
- **Run Tests:** `pytest` (all tests in `tests/`)
- **Debug Mode:** `UVICORN_LOG_LEVEL=debug python gui_server.py`
- **Environment:** Use `gdrive_env/` venv or `environment.yml` for conda

## Project-Specific Patterns
- **Dry Run Mode:** Enabled by default for safety; disables file writes
- **Progress Callbacks:** Pass a callback to core logic for GUI updates
- **Deduplication:** Uses SHA256 hashes; logs duplicates and renames
- **Rollback:** Manifest files allow undoing operations
- **Error Handling:** All errors logged; partial results preserved
- **Path Detection:** OS-specific default output paths
- **Testing:** Fixtures for realistic takeout structures; integration covers full workflow

## Integration Points
- **External:** No external network calls; all local file operations
- **Frontend/Backend:** HTMX for reactive UI, FastAPI for API endpoints
- **Core/GUI:** GUI never modifies core logic; communicates via callbacks

## Examples
- **Add a new router:** Place in `app/gui/routers/`, import in `gui_server.py`
- **Extend core logic:** Update `SafeTakeoutReconstructor` in `main_enhanced.py` and `app/core/rebuilder.py`
- **Add a test:** Place in `tests/unit/` or `tests/integration/`, use pytest fixtures

## Key Files
- `main_enhanced.py`, `app/core/rebuilder.py`, `app/gui/gui_server.py`, `app/gui/templates/index.html`, `tests/integration/test_end_to_end.py`

---
**For more details, see `README_GUI.md`.**
