# FreeCAD MCP Server - Development Workflow Commands
# https://just.systems/
#
# Commands are organized into modules:
#   just docker::build       - Docker commands
#   just quality::check      - Code quality commands
#   just testing::unit       - Testing commands
#   just freecad::run-gui    - FreeCAD commands
#   just documentation::build - Documentation commands
#
# Or use the shortcut commands defined below.

# Import modules
mod docker 'just/docker.just'
mod quality 'just/quality.just'
mod testing 'just/testing.just'
mod freecad 'just/freecad.just'
mod documentation 'just/documentation.just'

# Default recipe - show available commands
default:
    @just --list

# =============================================================================
# Setup & Installation
# =============================================================================

# Install all dependencies
install:
    uv sync --all-extras

# Install pre-commit hooks
setup-hooks:
    uv run pre-commit install
    uv run pre-commit install --hook-type commit-msg

# Full development environment setup
setup: install setup-hooks
    @echo "Development environment ready!"

# Update all dependencies to latest versions
update-deps:
    uv lock --upgrade
    uv sync --all-extras
    uv run pre-commit autoupdate

# =============================================================================
# Shortcut Commands (aliases to module commands)
# =============================================================================

# Run all pre-commit checks (shortcut for quality::check)
check: (quality::check)

# Format code with ruff (shortcut for quality::format)
format: (quality::format)

# Run linting (shortcut for quality::lint)
lint: (quality::lint)

# Run type checking (shortcut for quality::typecheck)
typecheck: (quality::typecheck)

# Run security scanning (shortcut for quality::security)
security: (quality::security)

# Run spell checking (shortcut for quality::spellcheck)
spellcheck: (quality::spellcheck)

# Run all secrets scanners (shortcut for quality::secrets)
secrets: (quality::secrets)

# Lint markdown files (shortcut for quality::markdown-lint)
markdown-lint: (quality::markdown-lint)

# Fix markdown files (shortcut for quality::markdown-fix)
markdown-fix: (quality::markdown-fix)

# Format markdown files (shortcut for quality::markdown-format)
markdown-format: (quality::markdown-format)

# Run unit tests (shortcut for testing::unit)
test: (testing::unit)

# Run tests with coverage (shortcut for testing::cov)
test-cov: (testing::cov)

# Run fast tests (shortcut for testing::fast)
test-fast: (testing::fast)

# Run integration tests (shortcut for testing::integration)
test-integration: (testing::integration)

# Run tests with verbose output (shortcut for testing::verbose)
test-verbose: (testing::verbose)

# Run all tests (shortcut for testing::all)
test-all: (testing::all)

# Build documentation (shortcut for documentation::build)
docs: (documentation::build)

# Serve documentation (shortcut for documentation::serve)
docs-serve: (documentation::serve)

# =============================================================================
# Running the MCP Server
# =============================================================================

# Run the MCP server (stdio mode)
run:
    uv run freecad-mcp

# Run the MCP server with debug logging
run-debug:
    FREECAD_MCP_LOG_LEVEL=DEBUG uv run freecad-mcp

# Run in HTTP mode for remote access
run-http port="8000":
    FREECAD_MCP_TRANSPORT=http FREECAD_MCP_PORT={{port}} uv run freecad-mcp

# =============================================================================
# FreeCAD Shortcuts (aliases to freecad module)
# =============================================================================

# Run FreeCAD GUI with MCP bridge (shortcut for freecad::run-gui)
run-gui: (freecad::run-gui)

# Run FreeCAD headless with MCP bridge (shortcut for freecad::run-headless)
run-headless: (freecad::run-headless)

# Install the StartMCPBridge macro (shortcut for freecad::install-bridge-macro)
install-bridge-macro: (freecad::install-bridge-macro)

# Uninstall the StartMCPBridge macro (shortcut for freecad::uninstall-bridge-macro)
uninstall-bridge-macro: (freecad::uninstall-bridge-macro)

# Install the CutObjectForMagnets macro (shortcut for freecad::install-cut-macro)
install-cut-macro: (freecad::install-cut-macro)

# Uninstall the CutObjectForMagnets macro (shortcut for freecad::uninstall-cut-macro)
uninstall-cut-macro: (freecad::uninstall-cut-macro)

# Install the FreeCAD plugin (shortcut for freecad::install-plugin)
install-freecad-plugin: (freecad::install-plugin)

# Uninstall the FreeCAD plugin (shortcut for freecad::uninstall-plugin)
uninstall-freecad-plugin: (freecad::uninstall-plugin)

# =============================================================================
# Combined Workflows
# =============================================================================

# Run all quality checks and unit tests (use before committing)
all: check test
    @echo "All checks passed!"

# Run integration tests with automatic FreeCAD headless startup
integration: (testing::integration-auto)

# Run all quality checks and ALL tests including integration
all-integration: check test integration
    @echo "All checks and integration tests passed!"

# Full CI pipeline (unit tests only)
ci: check test-cov
    @echo "CI pipeline complete!"

# Clean build artifacts
clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# =============================================================================
# Development Helpers
# =============================================================================

# Open Python REPL with project modules available
repl:
    uv run python -c "import freecad_mcp; print('FreeCAD MCP loaded')" && uv run python

# Show project structure
tree:
    tree -I '__pycache__|*.egg-info|.git|.mypy_cache|.pytest_cache|.ruff_cache|htmlcov|dist|build' -a

# Validate project configuration
validate:
    uv pip check
    uv run validate-pyproject pyproject.toml
