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

# Run all tests including integration (requires running FreeCAD MCP bridge)
all:
    uv run pytest {{project_root}}/tests

# Run tests in watch mode (re-runs on file changes)
watch:
    uv run pytest-watch {{project_root}}/tests/unit

# Run integration tests with automatic FreeCAD headless startup
integration-freecad:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Starting FreeCAD headless server for integration tests..."
    echo ""

    # Start FreeCAD headless in background
    just freecad::run-headless &
    FREECAD_PID=$!

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
            kill $FREECAD_PID 2>/dev/null || true
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

    # Stop FreeCAD
    echo ""
    echo "Stopping FreeCAD..."
    kill $FREECAD_PID 2>/dev/null || true

    exit $TEST_EXIT_CODE
