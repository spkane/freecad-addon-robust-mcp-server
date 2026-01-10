# Testing commands
# Usage: just testing::unit, just testing::integration, etc.

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()

# Run unit tests only (excludes integration tests)
unit:
    uv run pytest {{project_root}}/tests/unit

# Run tests with coverage (excludes integration tests)
# Note: Uses bash script to ensure .coverage file is created in project root
cov:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{project_root}}"
    uv run pytest tests/unit --cov=freecad_mcp --cov-report=term-missing --cov-report=html:htmlcov

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

    # Helper function to kill process on a port (with fallback for systems without lsof)
    # Usage: kill_port PORT [SIGNAL]
    # Examples: kill_port 9875      (sends SIGTERM)
    #           kill_port 9875 -9   (sends SIGKILL)
    kill_port() {
        local port=$1
        local signal=${2:--TERM}  # Default to SIGTERM if no signal specified
        local pids=""

        if command -v lsof &>/dev/null; then
            # Collect PIDs first, then kill only if non-empty
            pids=$(lsof -ti:"$port" 2>/dev/null || true)
            if [[ -n "$pids" ]]; then
                echo "$pids" | xargs kill "$signal" 2>/dev/null || true
            fi
        elif command -v fuser &>/dev/null; then
            # fuser -k sends SIGKILL by default; use --signal for others
            # Check if port is in use first
            if fuser "$port/tcp" 2>/dev/null; then
                if [ "$signal" = "-9" ] || [ "$signal" = "-KILL" ]; then
                    fuser -k "$port/tcp" 2>/dev/null || true
                else
                    fuser -k --signal "${signal#-}" "$port/tcp" 2>/dev/null || true
                fi
            fi
        fi
    }

    # Cleanup function to ensure FreeCAD is stopped
    # We kill by port since the subshell approach makes PID tracking unreliable
    cleanup() {
        if [ "$STARTED_FREECAD" = true ]; then
            echo ""
            echo "Stopping FreeCAD..."
            # Kill processes on our ports - these are the ones we started
            kill_port 9875
            kill_port 9876
            # Wait briefly for graceful shutdown
            sleep 1
            # Force kill if still running
            kill_port 9875 -9
            kill_port 9876 -9
        fi
    }

    # Set trap: EXIT runs cleanup on normal exit, INT/TERM run cleanup then exit
    trap cleanup EXIT
    trap 'cleanup; exit 130' INT
    trap 'cleanup; exit 143' TERM

    echo "Starting FreeCAD headless server for integration tests..."
    echo ""

    # Check if a bridge is already running and responsive
    if curl -s --connect-timeout 1 --max-time 1 http://localhost:9875 > /dev/null 2>&1; then
        # Try to ping - if it responds, there's a healthy bridge already running
        if uv run python -c "import socket; socket.setdefaulttimeout(2); import xmlrpc.client; print(xmlrpc.client.ServerProxy('http://localhost:9875').ping())" 2>/dev/null | grep -q "pong"; then
            echo "ERROR: A FreeCAD MCP bridge is already running on port 9875."
            echo ""
            echo "Options:"
            echo "  1. Use 'just testing::integration' to run tests against the existing bridge"
            echo "  2. Stop the existing FreeCAD instance and try again"
            echo "  3. If this is a zombie process, run: just testing::kill-bridge"
            exit 1
        else
            # Port is bound but not responding to ping - likely a zombie
            echo "WARNING: Port 9875 is bound but not responding (zombie process?)"
            echo "Attempting to kill zombie process..."
            kill_port 9875 -9
            kill_port 9876 -9
            sleep 2
        fi
    fi

    # Mark that we're starting FreeCAD (for cleanup)
    STARTED_FREECAD=true

    # Start FreeCAD headless in background
    # Redirect stderr to log file (not /dev/null) so startup failures are visible
    # Background process won't fail the script when killed by cleanup trap
    FREECAD_LOG="{{project_root}}/freecad-headless.log"
    just freecad::run-headless 2>"$FREECAD_LOG" &

    # Give FreeCAD time to start the XML-RPC server
    echo "Waiting for FreeCAD MCP bridge to start..."
    sleep 5

    # Check if the bridge is ready (verify XML-RPC ping, not just port open)
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! uv run python -c "import socket; socket.setdefaulttimeout(2); import xmlrpc.client; print(xmlrpc.client.ServerProxy('http://localhost:9875').ping())" 2>/dev/null | grep -q "pong"; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "ERROR: FreeCAD MCP bridge did not start within timeout"
            echo "Check log file for details: $FREECAD_LOG"
            if [ -f "$FREECAD_LOG" ]; then
                echo "--- Last 20 lines of log ---"
                tail -20 "$FREECAD_LOG"
            fi
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

# =============================================================================
# Just Command Tests
# =============================================================================

# Run just command syntax tests (fast, validates all commands parse correctly)
just-syntax:
    uv run pytest {{project_root}}/tests/just_commands -m "just_syntax" -v

# Run just command runtime tests (slower, actually executes commands)
just-runtime:
    uv run pytest {{project_root}}/tests/just_commands -m "just_runtime and not slow" -v

# Run all just command tests
just-all:
    uv run pytest {{project_root}}/tests/just_commands -v

# Run just command release tests (tests release commands with cleanup)
just-release:
    uv run pytest {{project_root}}/tests/just_commands -m "just_release" -v

# =============================================================================
# Bridge Management
# =============================================================================

# Kill any zombie FreeCAD MCP bridge processes on the default ports
kill-bridge:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Killing any processes on MCP bridge ports (9875, 9876)..."

    # Helper function to kill process on a port (with fallback for systems without lsof)
    # Collects PIDs first to avoid calling kill with no arguments
    kill_port() {
        local port=$1
        local pids=""

        if command -v lsof &>/dev/null; then
            # Collect PIDs first, then kill only if non-empty
            pids=$(lsof -ti:"$port" 2>/dev/null || true)
            if [[ -n "$pids" ]]; then
                echo "$pids" | xargs kill -9 2>/dev/null || true
            fi
        elif command -v fuser &>/dev/null; then
            # Check if port is in use first
            if fuser "$port/tcp" 2>/dev/null; then
                fuser -k -9 "$port/tcp" 2>/dev/null || true
            fi
        else
            echo "Warning: Neither lsof nor fuser available, cannot kill port $port"
        fi
    }

    kill_port 9875
    kill_port 9876

    echo "Done."
