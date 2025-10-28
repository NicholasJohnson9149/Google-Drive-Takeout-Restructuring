# Architecture Overview
## Google Drive Takeout Consolidator

**Version:** 2.0 (Post-Refactoring)
**Last Updated:** 2025-10-24

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interfaces                           │
├──────────────────────┬──────────────────────────────────────┤
│   CLI Interface      │         Web GUI                       │
│   (app/cli.py)       │   (app/gui/gui_server.py)           │
└──────────┬───────────┴──────────────┬───────────────────────┘
           │                          │
           v                          v
┌──────────────────────────────────────────────────────────────┐
│                  Core Business Logic                          │
│                  (app/core/)                                  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  SafeTakeoutReconstructor (rebuilder.py)            │   │
│  │  - Orchestrates the reconstruction process           │   │
│  │  - Uses composition pattern                          │   │
│  └───────────┬───────────────────────┬──────────────────┘   │
│              │                       │                        │
│       ┌──────▼──────┐         ┌─────▼──────┐               │
│       │ FileScanner │         │ PathNorm-  │               │
│       │             │         │  alizer    │               │
│       └─────────────┘         └────────────┘               │
│              │                       │                        │
│       ┌──────▼──────────────────────▼───────────┐           │
│       │      DuplicateChecker                    │           │
│       │      - FAST / HASH / VERIFY modes        │           │
│       └──────────────────────────────────────────┘           │
│                                                               │
│  Supporting Modules:                                         │
│  ├── TakeoutExtractor  (ZIP handling)                       │
│  ├── DriveVerifier     (Verification)                       │
│  ├── ProgressLogger    (Callbacks)                          │
│  └── CLIExecutor       (CLI-GUI bridge)                     │
└──────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Entry Points

#### CLI Entry (`app/cli.py`)
```python
# Commands:
# - extract: Unzip takeout files
# - rebuild: Reconstruct Drive structure
# - verify: Verify reconstruction

python -m app.cli rebuild ~/Downloads/Takeout ~/Desktop/Drive
```

**Features:**
- Rich progress bars
- Colored output
- Dry-run mode
- Conflict resolution options

#### GUI Entry (`main.py` → `gui_server.py` → `app/gui/gui_server.py`)
```
User → main.py (launches server)
       ↓
     gui_server.py (thin wrapper)
       ↓
     app/gui/gui_server.py (FastAPI app)
       ↓
     Routers handle requests
```

**Architecture:**
```
app/gui/
├── gui_server.py       # FastAPI app setup
├── state.py            # GUIState management (NO circular deps)
├── routers/
│   ├── paths.py        # Path validation, suggestions
│   ├── processing.py   # Start/cancel operations
│   ├── progress.py     # Progress polling
│   ├── logs.py         # Log retrieval
│   └── system.py       # System operations
├── templates/          # Jinja2 HTML
│   ├── index.html
│   └── partials/
└── static/
    └── style.css
```

---

### 2. Core Reconstruction Engine

#### SafeTakeoutReconstructor (V2 Architecture)

**Design Pattern:** Composition + Strategy Pattern

```python
class SafeTakeoutReconstructor:
    def __init__(self, takeout_path, export_path, ...):
        # Components (composition)
        self.scanner = FileScanner(source_dir)
        self.path_normalizer = PathNormalizer(dest_dir)
        self.duplicate_checker = DuplicateChecker(strategy)

        # State (dataclasses)
        self.stats = ProcessingStats()
        self.errors: List[ProcessingError] = []

    def rebuild_drive_structure(self):
        with self._managed_resources():  # Context manager
            # 1. Validate inputs
            # 2. Scan source directory
            # 3. Process files
            # 4. Generate manifest
            # 5. Log statistics
```

**Key Improvements Over V1:**
- ✅ Separation of concerns (scanner, normalizer, checker)
- ✅ Dataclasses for structured data
- ✅ Context managers for resource safety
- ✅ Better error tracking
- ✅ Cleaner code (less nesting)

---

### 3. Component Responsibilities

#### FileScanner
**Purpose:** Find and categorize files in takeout directory

```python
class FileScanner:
    def scan(self) -> ScanResult:
        # Walks directory tree
        # Identifies metadata files
        # Returns FileInfo objects
```

**Output:**
```python
@dataclass
class FileInfo:
    path: Path
    size: int
    is_metadata: bool
    relative_path: Path
```

#### PathNormalizer
**Purpose:** Transform takeout paths to clean Drive paths

```python
# Input:  Takeout/Drive/My Files/document.pdf
# Output: /export/My Files/document.pdf

# Input:  Takeout 2/Drive/Photos/image.jpg
# Output: /export/Photos/image.jpg

# Input:  Takeout/metadata.json
# Output: None (skip)
```

**Rules:**
1. Remove "Takeout" wrapper folders
2. Remove "Drive" folder itself
3. Preserve all structure inside Drive/
4. Handle numbered Takeout folders (Takeout 1, Takeout 2, etc.)
5. Skip metadata files

#### DuplicateChecker
**Purpose:** Detect duplicate files with configurable strategies

```python
class DuplicateStrategy(Enum):
    FAST = "fast"       # Size comparison only
    HASH = "hash"       # Size + SHA256 hash
    VERIFY = "verify"   # Full byte-by-byte comparison
```

**Trade-offs:**
- FAST: Fastest, least accurate
- HASH: Good balance (recommended)
- VERIFY: Slowest, most accurate

---

### 4. Data Flow

#### Reconstruction Pipeline

```
1. User Input
   ├── Takeout Path:  ~/Downloads/Takeout
   └── Export Path:   ~/Desktop/MyDrive

2. Initialization
   ├── Create SafeTakeoutReconstructor
   ├── Validate paths exist
   └── Check disk space

3. Scanning Phase
   ├── FileScanner walks directory
   ├── Identifies all files (non-hidden, non-temp)
   ├── Marks metadata files
   └── Returns ScanResult
        ├── files: List[FileInfo]
        ├── total_files: int
        ├── total_size: int
        └── errors: List[str]

4. Processing Phase
   For each file:
   ├── PathNormalizer transforms path
   │   ├── Remove Takeout wrapper
   │   ├── Remove Drive folder
   │   └── Return clean destination path
   │
   ├── DuplicateChecker checks if exists
   │   ├── If duplicate & skip → skip
   │   └── If duplicate & rename → add suffix
   │
   └── Copy file (chunked if > 100MB)
       ├── Create destination directories
       ├── Copy with metadata
       └── Optionally verify

5. Finalization
   ├── Generate manifest (JSON)
   ├── Write error log
   └── Report statistics

6. Cleanup
   └── Context manager closes resources
```

---

### 5. State Management (GUI)

#### GUIState Architecture

**Location:** `app/gui/state.py` (no circular dependencies)

```python
class GUIState:
    """Manages GUI application state"""

    # State stored in gui_state.json (human-readable)
    active_operations: Dict[str, OperationInfo]
    progress_logs: Dict[str, List[LogEntry]]
    user_paths: Dict[str, str]

    def save_state(self):
        # Save to JSON (not pickle)

    def load_state(self):
        # Load from JSON
        # Auto-migrate from pickle if exists

    def cleanup_old_operations(self):
        # Remove operations > 24 hours old
```

**State File Format (JSON):**
```json
{
  "version": 1,
  "active_operations": {
    "uuid-1234": {
      "id": "uuid-1234",
      "takeout_path": "/path/to/takeout",
      "export_path": "/path/to/export",
      "status": "processing",
      "progress_percent": 45.2,
      "current_file": "document.pdf",
      "stats": {
        "total_files": 1000,
        "copied_files": 452
      }
    }
  },
  "user_paths": {
    "last_takeout": "/path/to/takeout",
    "last_export": "/path/to/export"
  },
  "save_timestamp": "2025-10-24T10:30:00"
}
```

---

### 6. GUI-CLI Integration

#### CLIExecutor Bridge

**Problem:** GUI needs progress from CLI commands
**Solution:** CLIExecutor parses CLI output and emits structured events

```python
class CLIExecutor:
    def execute_with_progress(self, cmd, operation_id, callback):
        # Start subprocess
        process = subprocess.Popen(cmd, stdout=PIPE)

        # Parse output line-by-line
        for line in process.stdout:
            progress_data = self._parse_progress_line(line)
            callback(progress_data)

        return process.wait()

    def _parse_progress_line(self, line: str):
        # Extract progress from CLI output
        # - Look for percentages (45.2%)
        # - Look for filenames
        # - Look for status keywords
        return {'type': 'progress', 'percent': 45.2, ...}
```

**Event Types:**
```python
{
  'type': 'progress',  # Progress update
  'percent': 45.2,
  'current_file': 'document.pdf',
  'operation': 'Processing files'
}

{
  'type': 'status',    # Status change
  'status': 'processing',
  'message': 'Starting reconstruction'
}

{
  'type': 'stats',     # Statistics update
  'stats': {'copied_files': 100}
}

{
  'type': 'log',       # General log message
  'message': 'Processing file: doc.pdf',
  'level': 'info'
}
```

---

### 7. Error Handling Strategy

#### Structured Errors

```python
@dataclass
class ProcessingError:
    file_path: str
    error_message: str
    timestamp: str
    error_type: str  # "ScanError", "CopyError", "ValidationError"
```

#### Error Recovery
```python
try:
    # Process file
    copy_file(source, dest)
except Exception as e:
    # Record error but continue
    self.errors.append(ProcessingError(...))
    self.stats.errors += 1
    continue  # Don't stop entire process

# At the end:
if self.errors:
    write_error_log(self.errors)
    return False  # Indicate completion with errors
```

**Error Log Format:**
```
Error Log - 2025-10-24T10:30:00
==================================================

[2025-10-24T10:30:05] CopyError
File: /path/to/source/file.pdf
Error: Permission denied
------------------------------

[2025-10-24T10:30:12] ValidationError
File: /path/to/invalid
Error: File does not exist
------------------------------
```

---

### 8. Testing Architecture

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_rebuilder.py    # Core rebuilder logic
│   ├── test_file_scanner.py
│   ├── test_path_normalizer.py
│   ├── test_duplicate_checker.py
│   └── test_config.py
│
├── integration/             # Multiple components
│   ├── test_rebuilder_integration.py
│   ├── test_cli_workflow.py
│   └── test_end_to_end.py
│
├── e2e/                     # Full workflows
│   └── test_complete_restructuring.py
│
└── regression/              # Edge cases
    └── test_edge_cases_and_errors.py
```

**Test Coverage Target:** ≥ 80%

**Test Strategy:**
- Unit tests: Mock dependencies, test in isolation
- Integration tests: Real file system operations
- E2E tests: Complete user workflows
- Regression tests: Previously found bugs

---

### 9. Configuration Management

```python
# app/config.py
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"

class PathConfig:
    default_source: Path = Path.home() / "Downloads" / "Takeout"
    default_dest: Path = Path.home() / "Desktop" / "Drive Export"
    temp_dir: Path = Path.home() / "Downloads" / "takeout_temp"
    log_dir: Path = Path.home() / "Desktop" / "takeout_logs"

class ProcessingConfig:
    chunk_size: int = 1024 * 1024  # 1MB
    max_file_size: int = 10 * 1024**3  # 10GB
    timeout_seconds: int = 180 * 60  # 3 hours
    duplicate_strategy: str = "hash"
```

**Environment Overrides:**
```bash
export GDRIVE_SERVER_PORT=9000
export GDRIVE_LOG_LEVEL=debug
export GDRIVE_DEFAULT_SOURCE=/custom/path
```

---

### 10. Deployment Architecture

#### Development
```bash
# Start CLI
python -m app.cli rebuild ~/Downloads/Takeout ~/Desktop/Drive

# Start GUI (auto-opens browser)
python main.py
```

#### Production (Future)
```bash
# Package as executable
pyinstaller main.py --onefile --name=gdrive-consolidator

# Docker container
docker build -t gdrive-consolidator .
docker run -p 8000:8000 gdrive-consolidator
```

#### Platform Support
- ✅ macOS (primary development)
- ✅ Windows (tested)
- ✅ Linux (tested)

**Platform-Specific:**
- File system operations (utils/fs_utils.py)
- Trash/delete handling
- Path separators
- File permissions

---

## Key Design Decisions

### 1. Why V2 Over V1?

| Aspect | V1 | V2 | Winner |
|--------|----|----|--------|
| Architecture | Monolithic | Composition | V2 |
| Error Handling | Dict | Dataclass | V2 |
| Resource Cleanup | Manual | Context Manager | V2 |
| Code Organization | 461 lines | Split into modules | V2 |
| Testability | Hard to mock | Easy to mock | V2 |
| Maintainability | Medium | High | V2 |

### 2. Why JSON Over Pickle for State?

| Aspect | Pickle | JSON | Winner |
|--------|--------|------|--------|
| Human-readable | ❌ | ✅ | JSON |
| Version-safe | ❌ | ✅ | JSON |
| Security | ⚠️ Risky | ✅ Safe | JSON |
| Debugging | Hard | Easy | JSON |
| Migration | Difficult | Easy | JSON |

### 3. Why Composition Over Inheritance?

**V1 Approach (Monolithic):**
```python
class SafeTakeoutReconstructor:
    def scan_files(self): ...
    def normalize_path(self): ...
    def check_duplicate(self): ...
    # 461 lines in one class
```

**V2 Approach (Composition):**
```python
class SafeTakeoutReconstructor:
    def __init__(self):
        self.scanner = FileScanner()        # Single responsibility
        self.normalizer = PathNormalizer()  # Single responsibility
        self.checker = DuplicateChecker()   # Single responsibility
```

**Benefits:**
- ✅ Easier to test (mock individual components)
- ✅ Easier to extend (swap implementations)
- ✅ Easier to understand (each class has one job)
- ✅ Easier to debug (smaller units)

---

## Performance Considerations

### Bottlenecks
1. **File I/O** - Copying large files (>100MB)
   - Solution: Chunked copying

2. **Duplicate Detection** - Hashing large files
   - Solution: Configurable strategies (FAST/HASH/VERIFY)

3. **Directory Scanning** - Large takeout archives
   - Solution: Progress callbacks, skip hidden files

### Optimization Strategies
```python
# 1. Chunked copy for large files
if file_size > 100 * 1024 * 1024:  # > 100MB
    _chunked_copy(source, dest, chunk_size=1MB)

# 2. Fast duplicate check first
if source.stat().st_size != dest.stat().st_size:
    return False  # Different sizes, not duplicate

# 3. Batch progress updates
if processed_count % 100 == 0:
    emit_progress_update()
```

### Resource Management
```python
with self._managed_resources():
    # Temporary directory created
    # File handles tracked
    # Resources automatically cleaned up on exit
```

---

## Security Considerations

### Input Validation
```python
# Validate paths before processing
if not source_dir.exists():
    raise ValueError("Source directory does not exist")

if not source_dir.is_dir():
    raise ValueError("Source path is not a directory")
```

### File Operations
```python
# Never use shell=True in subprocess
subprocess.run(["python", "-m", "app.cli"], shell=False)

# Validate file extensions
if not filename.endswith(('.pdf', '.jpg', '.txt', ...)):
    log_warning(f"Unusual file type: {filename}")
```

### State Persistence
```python
# JSON instead of pickle (no code execution)
# JSON schema validation
# Backup before overwriting
```

---

## Future Enhancements

### Planned
1. **Parallel Processing** - Process files in parallel for speed
2. **Resume Support** - Resume interrupted operations
3. **Cloud Storage** - Direct upload to Google Drive, Dropbox, etc.
4. **Better Progress** - File-by-file progress instead of percentage
5. **Undo/Rollback** - Reverse reconstruction using manifest

### Under Consideration
1. **Database State** - SQLite instead of JSON for complex queries
2. **Web Authentication** - Multi-user support
3. **Scheduled Jobs** - Automatic processing of new takeouts
4. **Notifications** - Email/SMS when complete

---

## Related Documents

- [MIGRATION_PLAN.md](MIGRATION_PLAN.md) - How to migrate from V1 to V2
- [CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md) - Summary of cleanup effort
- [CLAUDE.md](CLAUDE.md) - Development guidelines
- [README.md](README.md) - User documentation

---

**Questions?** Review the migration plan or check the code comments.

**Contributing?** Follow the architecture patterns described here.

**Deploying?** Ensure all components are properly configured.
