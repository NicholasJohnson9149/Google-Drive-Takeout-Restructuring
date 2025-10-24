# 📁 Google Drive Takeout Rebuilder

[![CI](https://github.com/NicholasJohnson9149/gDrive-consaldator/actions/workflows/ci.yml/badge.svg)](https://github.com/NicholasJohnson9149/gDrive-consaldator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Reconstruct your original Google Drive folder structure from Google Takeout archive files. This tool processes extracted Takeout data and rebuilds the complete directory hierarchy, making your files accessible in their original organization.

## ✨ Features

- **🔄 Full Structure Reconstruction**: Rebuilds complete Google Drive folder hierarchy
- **🌐 Web GUI**: User-friendly web interface with drag-and-drop support
- **💻 CLI**: Powerful command-line interface for automation
- **🛡️ Safe Operation**: Dry-run mode, file verification, and rollback support
- **📊 Progress Tracking**: Real-time progress updates and detailed logging
- **🔍 Smart Duplicate Handling**: Intelligent detection and management of duplicate files
- **🚀 Cross-Platform**: Works on Windows, macOS, and Linux

## 🚀 Quick Start

![alt text](<docs/imgs/01 Google Drive Tackout Restructuring - App.png>)

### Option 1: Web GUI (Easiest)

```bash
# Install dependencies
pip install -r requirements.txt

# Start the GUI
python main.py
```

Open your browser to `http://localhost:8000`

### Option 2: Command Line

```bash
# Install as command-line tool
pip install -e .

# Preview reconstruction (dry run)
takeout-rebuilder rebuild ~/Downloads/Takeout ~/Desktop/MyDrive --dry-run

# Execute reconstruction
takeout-rebuilder rebuild ~/Downloads/Takeout ~/Desktop/MyDrive --force

# Verify results
takeout-rebuilder verify ~/Downloads/Takeout ~/Desktop/MyDrive
```

## 📦 Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/NicholasJohnson9149/gDrive-consaldator.git
cd gDrive-consaldator

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Using Conda

```bash
# Create environment from file
conda env create -f environment.yml
conda activate gdrive-consolidator
```

## 📖 Usage Guide

### Web Interface

1. **Start the server**: `python main.py`
2. **Open browser**: Navigate to `http://localhost:8000`
3. **Upload Takeout files**: Drag and drop your ZIP files
4. **Configure output**: Select destination folder
5. **Process**: Click "Start Processing"
6. **Monitor**: Watch real-time progress
7. **Complete**: Access your reconstructed Drive

### Command Line Interface

#### Extract Takeout Archives
```bash
takeout-rebuilder extract ~/Downloads/takeout-*.zip --output ~/Downloads/Takeout
```

#### Rebuild Drive Structure
```bash
# Dry run (preview changes)
takeout-rebuilder rebuild ~/Downloads/Takeout ~/Desktop/MyDrive --dry-run

# Execute reconstruction
takeout-rebuilder rebuild ~/Downloads/Takeout ~/Desktop/MyDrive --force

# With file verification (slower but safer)
takeout-rebuilder rebuild ~/Downloads/Takeout ~/Desktop/MyDrive --verify --force
```

#### Verify Reconstruction
```bash
takeout-rebuilder verify ~/Downloads/Takeout ~/Desktop/MyDrive
```

### Utility Scripts

#### Verify Reconstruction
```bash
python scripts/verify_reconstruction.py ~/Downloads/Takeout ~/Desktop/MyDrive --report verify.txt
```

#### Rollback Changes
```bash
# Preview rollback
python scripts/rollback.py ~/Desktop/takeout_logs/manifest_*.json --dry-run

# Execute rollback
python scripts/rollback.py ~/Desktop/takeout_logs/manifest_*.json --force
```

## 🏗️ Architecture

```
┌─────────────────┐
│   Web Browser   │
└────────┬────────┘
         │ HTTP/HTMX
┌────────▼────────┐
│  FastAPI Server │
└────────┬────────┘
         │
┌────────▼────────┐
│   Core Engine   │
│  (Rebuilder)    │
└────────┬────────┘
         │
┌────────▼────────┐
│  File System    │
└─────────────────┘
```

### Project Structure

```
gDrive-consaldator/
├── app/
│   ├── core/           # Core business logic
│   │   ├── extractor.py
│   │   ├── rebuilder.py
│   │   ├── verifier.py
│   │   └── logger.py
│   ├── gui/            # Web interface
│   │   ├── gui_server.py
│   │   ├── routers/
│   │   ├── templates/
│   │   └── static/
│   ├── cli.py          # CLI interface
│   └── config.py       # Configuration
├── tests/              # Test suite
├── scripts/            # Utility scripts
├── docs/               # Documentation
└── main.py            # Main entry point
```

## 🧪 Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run linting
ruff check .
black --check .
mypy app/
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Skip slow tests
pytest -m "not slow"
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check . --fix

# Type checking
mypy app/
```

## 🐳 Docker Support

```bash
# Build image
docker build -t takeout-rebuilder .

# Run container
docker run -p 8000:8000 -v ~/Downloads:/downloads takeout-rebuilder
```

## 📊 Performance

- **File Processing**: ~1000 files/minute
- **Memory Usage**: < 500MB for typical operations
- **Large Archives**: Handles 100GB+ takeouts efficiently
- **Concurrent Operations**: Configurable parallelism

## 🛡️ Safety Features

- **Dry Run Mode**: Preview all changes before execution
- **File Verification**: Optional hash verification for data integrity
- **Rollback Support**: Undo operations using manifest files
- **Smart Duplicates**: Intelligent handling of duplicate files
- **Comprehensive Logging**: Detailed logs for debugging
- **No Data Loss**: Original files are never modified

## 📝 Configuration

Configuration can be customized via environment variables or config files:

```bash
# Environment variables
export DEBUG=true
export HOST=0.0.0.0
export PORT=8080
```

See `app/config.py` for all configuration options.

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Google Takeout for providing data export functionality
- FastAPI for the excellent web framework
- HTMX for reactive UI without complexity
- The Python community for amazing tools and libraries

## 📮 Support

- **Issues**: [GitHub Issues](https://github.com/NicholasJohnson9149/gDrive-consaldator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/NicholasJohnson9149/gDrive-consaldator/discussions)
- **Wiki**: [Project Wiki](https://github.com/NicholasJohnson9149/gDrive-consaldator/wiki)

---

Made with ❤️ for everyone who needs their Google Drive data back in order.