# Testing commands
# Usage: just testing::unit, just testing::integration, etc.

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()

# Run unit tests only (excludes integration tests)
unit:
    uv run pytest {{project_root}}/tests/unit

# Run tests with coverage (excludes integration tests)
cov:
    cd {{project_root}} && uv run pytest tests/unit --cov=freecad_mcp --cov-report=term-missing --cov-report=html:{{project_root}}/htmlcov

# Run tests without slow markers (excludes integration tests)
fast:
    uv run pytest {{project_root}}/tests/unit -m "not slow"

# Run only integration tests (requires running FreeCAD MCP bridge)
integration:
    uv run pytest {{project_root}}/tests/integration -v

# Run tests with verbose output (excludes integration tests)
verbose:
    uv run pytest {{project_root}}/tests/unit -v --tb=long

# Run all tests including integration (auto-starts FreeCAD headless)
# Runs unit tests first (no FreeCAD needed), then delegates to integration-freecad-auto
all:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Running unit tests..."
    echo ""
    uv run pytest "{{project_root}}/tests/unit" -v

    echo ""
    echo "Unit tests passed! Now running integration tests..."
    echo ""

    # Delegate to integration-freecad-auto for FreeCAD lifecycle management
    just testing::integration-freecad-auto

# Run tests in watch mode (re-runs on file changes)
# Note: --config specifies .pytest-watch.cfg to avoid pytest-watch parsing
# pyproject.toml as INI (it fails on valid TOML [[array.tables]] syntax)
watch:
    #!/usr/bin/env bash
    set -euo pipefail

    echo ""
    echo "========================================"
    echo "  WATCH MODE - Running initial tests..."
    echo "========================================"
    echo ""

    uv run pytest-watch \
        --config "{{project_root}}/.pytest-watch.cfg" \
        --afterrun "echo '' && echo '========================================' && echo '  WATCHING for file changes...' && echo '  Press Ctrl+C to exit watch mode' && echo '========================================' && echo ''" \
        "{{project_root}}/tests/unit"

# Run integration tests with automatic FreeCAD headless startup
integration-freecad-auto:
    #!/usr/bin/env bash
    set -euo pipefail

    # Track whether we started FreeCAD (so cleanup knows to stop it)
    STARTED_FREECAD=false

    # Cleanup function to ensure FreeCAD is stopped
    # We kill by port since the subshell approach makes PID tracking unreliable
    cleanup() {
        if [ "$STARTED_FREECAD" = true ]; then
            echo ""
            echo "Stopping FreeCAD..."
            # Kill processes on our ports - these are the ones we started
            lsof -ti:9875 | xargs kill 2>/dev/null || true
            lsof -ti:9876 | xargs kill 2>/dev/null || true
            # Wait briefly for graceful shutdown
            sleep 1
            # Force kill if still running
            lsof -ti:9875 | xargs kill -9 2>/dev/null || true
            lsof -ti:9876 | xargs kill -9 2>/dev/null || true
        fi
    }

    # Set trap to cleanup on exit, interrupt, or error
    trap cleanup EXIT INT TERM

    echo "Starting FreeCAD headless server for integration tests..."
    echo ""

    # Check if a bridge is already running and responsive
    if curl -s http://localhost:9875 > /dev/null 2>&1; then
        # Try to ping - if it responds, there's a healthy bridge already running
        if python3 -c "import xmlrpc.client; print(xmlrpc.client.ServerProxy('http://localhost:9875').ping())" 2>/dev/null | grep -q "pong"; then
            echo "ERROR: A FreeCAD MCP bridge is already running on port 9875."
            echo ""
            echo "Options:"
            echo "  1. Use 'just testing::integration' to run tests against the existing bridge"
            echo "  2. Stop the existing FreeCAD instance and try again"
            echo "  3. If this is a zombie process, kill it with: lsof -ti:9875 | xargs kill -9"
            exit 1
        else
            # Port is bound but not responding to ping - likely a zombie
            echo "WARNING: Port 9875 is bound but not responding (zombie process?)"
            echo "Attempting to kill zombie process..."
            lsof -ti:9875 | xargs kill -9 2>/dev/null || true
            lsof -ti:9876 | xargs kill -9 2>/dev/null || true
            sleep 2
        fi
    fi

    # Mark that we're starting FreeCAD (for cleanup)
    STARTED_FREECAD=true

    # Start FreeCAD headless in background
    # Redirect stderr to suppress "terminated by signal" messages from just
    # Background process won't fail the script when killed by cleanup trap
    just freecad::run-headless 2>/dev/null &

    # Give FreeCAD time to start the XML-RPC server
    echo "Waiting for FreeCAD MCP bridge to start..."
    sleep 5

    # Check if the bridge is ready
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! curl -s http://localhost:9875 > /dev/null 2>&1; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "ERROR: FreeCAD MCP bridge did not start within timeout"
            exit 1
        fi
        echo "  Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
        sleep 1
    done

    echo "FreeCAD MCP bridge is ready!"
    echo ""

    # Run integration tests
    TEST_EXIT_CODE=0
    uv run pytest "{{project_root}}/tests/integration" -v || TEST_EXIT_CODE=$?

    # Cleanup is handled by trap
    exit $TEST_EXIT_CODE
