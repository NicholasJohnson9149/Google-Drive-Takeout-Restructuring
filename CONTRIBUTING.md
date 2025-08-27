# Contributing to Google Drive Takeout Rebuilder

Thank you for your interest in contributing to this project! We welcome contributions from everyone.

## 🚀 Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/gDrive-consaldator.git
   cd gDrive-consaldator
   ```
3. Create a new branch for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🛠️ Development Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## 📝 Code Style

We use several tools to maintain code quality:

- **Black**: Code formatting (line length: 100)
- **Ruff**: Linting
- **MyPy**: Type checking
- **Pre-commit**: Automatic checks before commits

Run all checks:
```bash
# Format code
black .

# Run linter
ruff check . --fix

# Type checking
mypy app/

# Run all pre-commit hooks
pre-commit run --all-files
```

## 🧪 Testing

All new features should include tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_rebuilder.py

# Run tests in parallel
pytest -n auto
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use fixtures from `tests/conftest.py`
- Aim for >80% code coverage

## 📦 Making Changes

1. **Write your code**: Follow existing patterns and style
2. **Add tests**: Ensure your changes are tested
3. **Update documentation**: Update README.md if needed
4. **Run checks**: Ensure all tests and linting pass
5. **Commit changes**: Write clear, descriptive commit messages

### Commit Message Guidelines

Format:
```
type: subject

body (optional)

footer (optional)
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions or changes
- `chore`: Maintenance tasks

Example:
```
feat: add support for encrypted archives

- Implement decryption for password-protected zips
- Add password prompt in GUI
- Update CLI with --password flag

Closes #123
```

## 🔄 Pull Request Process

1. Update your branch with the latest main:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. Push your changes:
   ```bash
   git push origin feature/your-feature-name
   ```

3. Create a Pull Request on GitHub

4. PR Checklist:
   - [ ] Tests pass locally
   - [ ] Code follows style guidelines
   - [ ] Documentation is updated
   - [ ] PR description explains changes
   - [ ] Related issues are referenced

## 🏗️ Project Structure

```
app/
├── core/         # Core business logic (no UI dependencies)
├── gui/          # Web interface (FastAPI/HTMX)
├── cli.py        # Command-line interface
└── config.py     # Configuration management

tests/
├── unit/         # Unit tests for individual components
├── integration/  # End-to-end integration tests
└── utils.py      # Test utilities and helpers

scripts/          # Standalone utility scripts
docs/            # Documentation
```

## 🎯 Areas for Contribution

### Good First Issues
- Improve error messages
- Add more unit tests
- Update documentation
- Fix typos

### Feature Ideas
- Support for other cloud storage exports
- Batch processing improvements
- Enhanced duplicate detection
- Performance optimizations
- Internationalization (i18n)

### Known Issues
Check the [Issues](https://github.com/NicholasJohnson9149/gDrive-consaldator/issues) page for current bugs and feature requests.

## 🤝 Code of Conduct

Please be respectful and considerate in your interactions:
- Be welcoming to newcomers
- Be patient with questions
- Focus on constructive criticism
- Respect differing opinions

## 📮 Getting Help

- Open an issue for bugs
- Start a discussion for questions
- Check existing issues/PRs before creating new ones
- Join our community discussions

## 📄 License

By contributing, you agree that your contributions will be licensed under the same MIT License that covers this project.

## 🙏 Thank You!

Your contributions make this project better for everyone. Thank you for taking the time to contribute!

---

Happy coding! 🎉