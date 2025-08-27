
# Google Drive Takeout Rebuilder — Full Project Refactor Prompt

## Overview
This project reconstructs Google Takeout `.zip` files back into their **original Google Drive folder hierarchy**.  
The current implementation works but is **poorly organized**, with multiple redundant entry points, backup files, and no proper test coverage.

This prompt instructs the coding agent to:
- Restructure the project into a **clean, modular, and testable architecture**.
- Remove unused or legacy code.
- Add **robust unit and integration tests**.
- Package the app as a **standalone executable** for non-technical users.
- Ensure **security** and **local-first execution**.
- Set up **GitHub-friendly workflows**.

---

## Goals
1. Migrate to a **scalable, maintainable architecture**.
2. Consolidate all working logic into clean modules.
3. Add full **test coverage** with pytest.
4. Provide **cross-platform executables** for simple local usage.
5. Ensure **no sensitive data** or API keys are exposed.
6. Prepare the repository for **GitHub releases and CI automation**.

---

## Proposed Project Structure

```
takeout-rebuilder/
├── app/
│   ├── __init__.py
│   ├── gui/                        # Frontend + templates
│   │   ├── templates/
│   │   │   ├── layout.html
│   │   │   ├── index.html
│   │   │   └── partials/
│   │   │       ├── progress.html
│   │   │       ├── logs.html
│   │   │       ├── complete.html
│   │   │       └── errors.html
│   │   ├── static/
│   │   │   ├── css/
│   │   │   │   └── styles.css
│   │   │   ├── js/
│   │   │   │   ├── htmx.min.js
│   │   │   │   └── progress.js
│   │   │   └── uploads/
│   │   └── gui_server.py
│   │
│   ├── core/                       # Business logic
│   │   ├── extractor.py            # Unzip Takeout zips
│   │   ├── rebuilder.py            # Rebuild Drive structure
│   │   ├── verifier.py             # Validate reconstructed output
│   │   ├── logger.py               # Centralized logging
│   │   └── __init__.py
│   │
│   ├── cli.py                      # Optional CLI interface
│   └── config.py                   # Configurations (local paths, logging)
│
├── tests/
│   ├── unit/
│   │   ├── test_extractor.py
│   │   ├── test_rebuilder.py
│   │   ├── test_verifier.py
│   │   └── test_logger.py
│   ├── integration/
│   │   ├── test_end_to_end.py      # Upload → extract → rebuild
│   │   └── test_progress_ui.py
│   ├── fixtures/                   # Sample test data
│   │   ├── simple_takeout.zip
│   │   ├── nested_takeout.zip
│   │   └── conflict_case.zip
│   └── conftest.py                 # Pytest fixtures
│
├── scripts/
│   ├── setup_environment.sh
│   ├── rollback.py
│   └── verify_reconstruction.py
│
├── main.py                         # Single unified entry point
├── requirements.txt
├── environment.yml
├── README.md
└── .env
```

---

## File Mapping (Old → New)

| **Current File**             | **New Location**                     | **Action** |
|----------------------------|---------------------------------|-----------|
| `main.py`                  | `main.py`                       | Unified entrypoint |
| `main_enhanced.py`         | Merged into `core/`             | Remove old file |
| `main_enhanced_v2.py`      | Merged into `core/`             | Remove old file |
| `gui_server.py`            | `app/gui/gui_server.py`         | Keep |
| `gui_server_backup.py`     | **Remove**                      | Backup not needed |
| `start_gui.py`             | Integrated into `main.py`       | Remove old |
| `verify_reconstruction.py` | `scripts/verify_reconstruction.py` | Keep |
| `rollback.py`              | `scripts/rollback.py`           | Keep |
| `test_consolidator.py`     | `tests/unit/test_rebuilder.py`   | Rename |
| `test_external_paths.py`   | `tests/integration/test_external_paths.py` | Keep |
| `test_run.py`              | `tests/integration/test_end_to_end.py` | Keep |
| `templates/index.html`     | `app/gui/templates/index.html`  | Keep |
| Template backups           | **Remove**                      | Obsolete |
| `static/style.css`         | `app/gui/static/css/styles.css` | Keep |

---

## Testing Strategy

### Tools
- **Pytest** → test runner.
- **Pytest-Cov** → code coverage reports.

### Targets
| **Area**       | **Goal Coverage** |
|---------------|--------------------|
| Core modules  | >90%               |
| GUI endpoints | >80%               |
| Integration   | >70%               |

### Run Tests
```bash
pytest --cov=app tests/
```

### Test Types
- **Unit Tests**  
    - Validate `extractor.py`, `rebuilder.py`, `verifier.py`, `logger.py`.
- **Integration Tests**  
    - Simulate `.zip` uploads.
    - Validate reconstructed folder hierarchy.
- **UI Tests**  
    - Verify HTMX endpoints return correct partials.
    - Test progress and logs updates dynamically.

---

## Packaging for Non-Technical Users

### Option A — PyInstaller (Recommended)
```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name "TakeoutRebuilder" main.py
```
- Produces:
  - **Mac/Linux:** `dist/TakeoutRebuilder`
  - **Windows:** `TakeoutRebuilder.exe`
- No Python installation required.

### Option B — Native Installers via Briefcase
```bash
pip install briefcase
briefcase create
briefcase build
briefcase package
```
- Creates a **double-clickable app** with branding and icons.

### Option C — Docker (Optional)
```bash
docker build -t takeout-rebuilder .
docker run -p 5000:5000 takeout-rebuilder
```

---

## GitHub Integration

### 1. Releases
- Use **GitHub Actions** to:
    - Build executables for Mac, Windows, Linux.
    - Attach artifacts to GitHub Releases automatically.

### 2. README Enhancements
Include:
- Project overview.
- Download links for packaged executables.
- Instructions to run from source.
- Instructions to run tests.

---

## Next Steps
1. Refactor the project into the new structure.
2. Remove unused and backup code.
3. Add comprehensive **pytest** coverage.
4. Package with PyInstaller or Briefcase for easy installation.
5. Configure **GitHub Actions** for cross-platform builds and releases.

---

**Important:**  
Do **not** expose any sensitive data or store API keys in the repo.  
All file restructuring and processing **must remain fully local**.
