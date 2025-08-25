# 🗂️ Google Drive Takeout Consolidator - Web GUI

A cross-platform web interface for organizing Google Drive takeout files back into their original folder structure.

## ✨ Features

- **🌐 Cross-Platform**: Works on Mac, Windows, and Linux through your web browser
- **📁 Drag & Drop**: Simple drag-and-drop interface for zip files
- **🔄 Auto-Extract**: Automatically extracts and processes multiple takeout zips
- **📊 Real-Time Progress**: Live progress tracking with statistics
- **🛡️ Safety First**: Smart duplicate detection and file verification
- **📋 Detailed Logging**: Comprehensive logs for troubleshooting
- **🎨 Modern UI**: Clean, responsive interface built with HTMX

## 🚀 Quick Start

### Method 1: One-Click Startup (Easiest)
```bash
python start_gui.py
```
This automatically installs dependencies and opens the web interface.

### Method 2: Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start the GUI server
python gui_server.py
```

Then open your browser to: `http://localhost:8000`

## 📖 How to Use

### Step 1: Upload Takeout Files
1. Download your Google Takeout zip files
2. Drag and drop them into the web interface
3. Files are automatically uploaded and extracted

### Step 2: Configure Output
1. Choose where to save your organized files
2. Optionally enable file verification (slower but safer)
3. Click "Start Processing"

### Step 3: Monitor Progress
- Watch real-time progress with file counts and statistics
- View live log of operations
- See which files are being processed

### Step 4: Review Results
- Get a summary of processed files
- Download detailed logs
- Access your organized Google Drive structure

## 🏗️ Architecture

```
Browser (HTMX Frontend)
    ↓ HTTP/WebSocket
FastAPI Server (Python)
    ↓ Function Calls
SafeTakeoutReconstructor (Core Logic)
    ↓ File Operations
Your Organized Google Drive
```

### Key Components

- **`gui_server.py`**: FastAPI web server with HTMX endpoints
- **`templates/index.html`**: Modern web interface with drag-drop
- **`static/style.css`**: Clean, responsive styling
- **`main_enhanced.py`**: Core consolidation logic (enhanced with GUI hooks)
- **`test_consolidator.py`**: Comprehensive unit and integration tests

## 🧪 Testing

Run the test suite to verify everything works:

```bash
python test_consolidator.py
```

Tests cover:
- ✅ Zip extraction with various scenarios
- ✅ File consolidation logic
- ✅ GUI state management
- ✅ Error handling and edge cases
- ✅ Complete end-to-end workflow

## 🔧 Configuration

### Environment Variables
```bash
# Optional: Change server host/port
export CONSOLIDATOR_HOST=0.0.0.0
export CONSOLIDATOR_PORT=8080
```

### Default Paths
The GUI automatically suggests appropriate directories based on your OS:
- **Mac**: `/Users/username/Desktop/Google Drive Organized`
- **Windows**: `C:\Users\username\Desktop\Google Drive Organized`
- **Linux**: `/home/username/Desktop/Google Drive Organized`

## 🛡️ Safety Features

### Built-in Protections
- **Dry Run Mode**: Preview operations before execution
- **Smart Path Detection**: Automatically handles path variations
- **Duplicate Detection**: Intelligent handling of duplicate files
- **File Verification**: Optional hash verification for data integrity
- **Rollback Capability**: Can undo operations using manifest files
- **Progress Logging**: Detailed logs for debugging and verification

### Error Handling
- Graceful handling of corrupted zip files
- Automatic retry for temporary failures
- Clear error messages with actionable suggestions
- Preservation of partial results on interruption

## 📊 Performance

### Optimization Features
- **Streaming Uploads**: Efficient handling of large zip files
- **Background Processing**: Non-blocking file operations
- **Progress Batching**: Efficient GUI updates (every 100 files)
- **Memory Management**: Limited log retention to prevent memory issues
- **Parallel Extraction**: Concurrent processing where possible

### Resource Requirements
- **RAM**: 1-2 GB recommended for large takeouts
- **Disk**: 2x the size of your takeout (temporary extraction space)
- **Network**: Localhost only (no external connections)

## 🔍 Troubleshooting

### Common Issues

**"No zip files found"**
- Ensure files have .zip extension
- Check that files aren't corrupted

**"Source directory not found"**
- The GUI handles path variations automatically
- Check that the directory actually exists

**"Extraction failed"**
- Some takeout zips may be corrupted
- Check the error log for specific files

**Browser won't open automatically**
- Manually navigate to `http://localhost:8000`
- Check that port 8000 isn't in use

### Debug Mode
Start with debug logging:
```bash
UVICORN_LOG_LEVEL=debug python gui_server.py
```

### Log Locations
All logs are saved to `takeout_logs/` directory:
- `rebuild_log_*.txt` - Main operation log
- `errors_*.txt` - Error details
- `duplicates_*.txt` - Duplicate file handling
- `manifest_*.json` - Operation manifest for rollback

## 🎯 Use Cases

### Perfect For:
- **Large Takeouts**: 100GB+ multi-zip takeouts
- **Non-Technical Users**: Simple web interface
- **Cross-Platform**: Works the same on any OS
- **Team Use**: Multiple people can access the same server
- **Remote Processing**: Can run on a server and access remotely

### Technical Details
- **Web Framework**: FastAPI with HTMX for reactive UI
- **File Processing**: Enhanced version of original CLI tool
- **Frontend**: Vanilla JavaScript with HTMX (no complex frameworks)
- **Styling**: Modern CSS with dark mode support
- **Progress Tracking**: Real-time WebSocket-like updates via HTMX polling

## 🤝 Contributing

The codebase is designed for maintainability:
- **Clean Separation**: GUI layer doesn't modify core logic
- **Comprehensive Tests**: Unit and integration test coverage
- **Type Hints**: Full type annotation for better IDE support
- **Error Handling**: Graceful degradation and clear error messages

## 📄 License

Same as the main project - designed for personal and educational use.

---

**Need help?** Check the logs in `takeout_logs/` directory or run the test suite to verify your setup.

**Want command-line?** The original `main_enhanced.py` still works for CLI usage.
