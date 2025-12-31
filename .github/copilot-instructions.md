# Copilot Instructions for Aider

## Project Overview

Aider is an AI pair programming tool that works in your terminal. It allows developers to collaborate with LLMs to start new projects or build on existing codebases. The project is written in Python and provides a command-line interface for interacting with various LLM providers.

## Code Style and Standards

### Python Compatibility
- Support Python versions: 3.10, 3.11, 3.12
- Use `requires-python = ">=3.10,<3.13"` in pyproject.toml

### Code Style
- Follow PEP 8 style guide
- Maximum line length: 100 characters
- Use Black for code formatting
- Use isort for import sorting
- **No type hints** - the project does not use type hints

### Flake8 Configuration
- Ignore: E203, W503
- Max line length: 100

## Development Setup

### Installation
```bash
# Create virtual environment
python3 -m venv ../aider_venv
source ../aider_venv/bin/activate

# Install in editable mode
pip install -e .

# Install dependencies
pip install -r requirements.txt
pip install -r requirements/requirements-dev.txt
```

### Pre-commit Hooks
- The project uses pre-commit hooks
- Install with: `pre-commit install`
- Run manually: `pre-commit run --all-files`

## Testing

### Test Framework
- Use pytest for all tests
- Test files are in the `tests/` directory
- Test file naming: `test_*.py`
- Test class naming: `TestClassName`

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/basic/test_coder.py

# Run specific test case
pytest tests/basic/test_coder.py::TestCoder::test_specific_case
```

### Test Structure
- Tests are organized in subdirectories: `basic/`, `browser/`, `help/`, `scrape/`
- Fixtures are in `tests/fixtures/`

## Dependency Management

### Adding Dependencies
1. Add to appropriate `.in` file:
   - `requirements.in` - main dependencies
   - `requirements/requirements-dev.in` - development dependencies
   - `requirements/requirements-help.in` - help dependencies
   - `requirements/requirements-browser.in` - browser dependencies
   - `requirements/requirements-playwright.in` - playwright dependencies

2. Compile requirements:
```bash
pip install pip-tools
./scripts/pip-compile.sh
```

3. For upgrades:
```bash
./scripts/pip-compile.sh --upgrade
```

## Project Structure

- `aider/` - Main package directory
- `tests/` - Test files
- `scripts/` - Utility scripts
- `benchmark/` - Benchmarking code
- `docker/` - Docker-related files
- `requirements/` - Dependency files
- `.github/` - GitHub workflows and templates

## Common Patterns

### Main Entry Point
- Entry point: `aider.main:main` (defined in pyproject.toml)
- CLI commands are handled through the main module

### Version Management
- Version is managed by setuptools_scm
- Written to `aider/_version.py`

### Documentation
- Built with Jekyll
- Located in `aider/website/`
- Build with: `bundle exec jekyll build`
- Serve locally: `bundle exec jekyll serve`

## Contributing Guidelines

### Before Submitting PRs
- Run tests with pytest
- Run pre-commit hooks
- For significant changes, discuss in a GitHub issue first
- Review the [Individual Contributor License Agreement](https://aider.chat/docs/legal/contributor-agreement.html)

### Code Review
- Small changes: submit PR directly
- Large changes: discuss in issue first
- Maintain compatibility with Python 3.10-3.12

## CI/CD

- GitHub Actions workflows in `.github/workflows/`
- Tests run on Ubuntu and Windows
- Tests run for Python 3.10-3.12 on CI
- Docker build and test workflow available
- Workflows ignore changes to `aider/website/**` and `README.md`

## Important Notes

- Keep changes minimal and focused
- Follow existing patterns in the codebase
- Write tests for new features
- Update documentation when necessary
- Ensure compatibility across supported Python versions
