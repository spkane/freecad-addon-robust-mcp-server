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
quick:
    uv run pytest {{project_root}}/tests/unit -m "not slow"

# Run only integration tests (requires running FreeCAD Robust MCP Bridge)
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

    # Source shared bridge helper functions
    . "{{project_root}}/scripts/bridge-helpers.sh"

    # Track whether we started FreeCAD (so cleanup knows to stop it)
    STARTED_FREECAD=false

    # Cleanup function to ensure FreeCAD is stopped
    # We kill by port since the subshell approach makes PID tracking unreliable
    cleanup() {
        if [ "$STARTED_FREECAD" = true ]; then
            echo ""
            echo "Stopping FreeCAD..."
            graceful_kill_bridge_ports
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
            echo "ERROR: A FreeCAD Robust MCP Bridge is already running on port 9875."
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
    echo "Waiting for FreeCAD Robust MCP Bridge to start..."
    sleep 5

    # Check if the bridge is ready (verify XML-RPC ping, not just port open)
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! uv run python -c "import socket; socket.setdefaulttimeout(2); import xmlrpc.client; print(xmlrpc.client.ServerProxy('http://localhost:9875').ping())" 2>/dev/null | grep -q "pong"; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "ERROR: FreeCAD Robust MCP Bridge did not start within timeout"
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

    echo "FreeCAD Robust MCP Bridge is ready!"
    echo ""

    # Run integration tests
    TEST_EXIT_CODE=0
    uv run pytest "{{project_root}}/tests/integration" -v || TEST_EXIT_CODE=$?

    # Cleanup is handled by trap
    exit $TEST_EXIT_CODE

# =============================================================================
# Test Setup
# =============================================================================

# Check if test dependencies are installed (fails if any are missing)
check-deps:
    @uv run python -c "import pytest" 2>/dev/null && echo "✓ pytest installed" || { echo "✗ pytest not installed"; exit 1; }
    @uv run python -c "import pytest_cov" 2>/dev/null && echo "✓ pytest-cov installed" || { echo "✗ pytest-cov not installed"; exit 1; }
    @uv run python -c "import pytest_asyncio" 2>/dev/null && echo "✓ pytest-asyncio installed" || { echo "✗ pytest-asyncio not installed"; exit 1; }

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
# Release Testing (Comprehensive Pre-Release Validation)
# =============================================================================

# Run all tests required before a release can be created
# This includes: unit tests, headless integration, GUI integration, Docker, and just commands
# All tests must pass for a release to proceed.
release-test:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "============================================================"
    echo "  RELEASE TEST SUITE"
    echo "  All tests must pass before creating a release"
    echo "============================================================"
    echo ""

    # Track overall test results
    TESTS_PASSED=true
    # Arrays to track failures (name and command)
    declare -a FAILED_NAMES=()
    declare -a FAILED_COMMANDS=()

    # Helper function to record test failure
    record_failure() {
        TESTS_PASSED=false
        FAILED_NAMES+=("$1")
        FAILED_COMMANDS+=("$2")
    }

    # -------------------------------------------------------------------------
    # Step 1: Unit Tests with Coverage
    # -------------------------------------------------------------------------
    echo "============================================================"
    echo "  Step 1/5: Unit Tests with Coverage"
    echo "============================================================"
    echo ""

    if just testing::cov; then
        echo ""
        echo "✓ Unit tests passed"
    else
        echo ""
        echo "✗ Unit tests FAILED"
        record_failure "Unit tests with coverage" "just testing::cov"
    fi
    echo ""

    # -------------------------------------------------------------------------
    # Step 2: Headless Integration Tests
    # -------------------------------------------------------------------------
    echo "============================================================"
    echo "  Step 2/5: Headless Integration Tests"
    echo "============================================================"
    echo ""

    if just testing::integration-headless-release; then
        echo ""
        echo "✓ Headless integration tests passed"
    else
        echo ""
        echo "✗ Headless integration tests FAILED"
        record_failure "Headless integration tests" "just testing::integration-headless-release"
    fi
    echo ""

    # -------------------------------------------------------------------------
    # Step 3: GUI Integration Tests
    # -------------------------------------------------------------------------
    echo "============================================================"
    echo "  Step 3/5: GUI Integration Tests"
    echo "============================================================"
    echo ""

    if just testing::integration-gui-release; then
        echo ""
        echo "✓ GUI integration tests passed"
    else
        echo ""
        echo "✗ GUI integration tests FAILED"
        record_failure "GUI integration tests" "just testing::integration-gui-release"
    fi
    echo ""

    # -------------------------------------------------------------------------
    # Step 4: Docker Integration Test
    # -------------------------------------------------------------------------
    echo "============================================================"
    echo "  Step 4/5: Docker Integration Test"
    echo "============================================================"
    echo ""

    if just docker::test; then
        echo ""
        echo "✓ Docker integration test passed"
    else
        echo ""
        echo "✗ Docker integration test FAILED"
        record_failure "Docker integration test" "just docker::test"
    fi
    echo ""

    # -------------------------------------------------------------------------
    # Step 5: Just Command Tests
    # -------------------------------------------------------------------------
    echo "============================================================"
    echo "  Step 5/5: Just Command Tests"
    echo "============================================================"
    echo ""

    if just testing::just-all; then
        echo ""
        echo "✓ Just command tests passed"
    else
        echo ""
        echo "✗ Just command tests FAILED"
        record_failure "Just command tests" "just testing::just-all"
    fi
    echo ""

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    echo "============================================================"
    echo "  RELEASE TEST SUMMARY"
    echo "============================================================"
    echo ""

    if [ "$TESTS_PASSED" = true ]; then
        echo "✓ ALL TESTS PASSED - Ready for release!"
        echo ""
        echo "============================================================"
        echo "  NEXT STEPS FOR RELEASE"
        echo "============================================================"
        echo ""
        echo "1. UPDATE RELEASE NOTES (for each component you're releasing):"
        echo ""
        echo "   Edit the RELEASE_NOTES.md file for each component:"
        echo "     - MCP Server:  src/freecad_mcp/RELEASE_NOTES.md"
        echo "     - Workbench:   addon/FreecadRobustMCPBridge/RELEASE_NOTES.md"
        echo ""
        echo "   Add a new version section at the top:"
        echo "     ## Version X.Y.Z (YYYY-MM-DD)"
        echo "     ### Added"
        echo "     - New feature description"
        echo "     ### Changed"
        echo "     - Change description"
        echo "     ### Fixed"
        echo "     - Bug fix description"
        echo ""
        echo "   Tip: Use 'just release::draft-notes <component>' to generate draft notes"
        echo "   from git commits since the last release."
        echo ""
        echo "2. BUMP VERSIONS (for workbench only - MCP server auto-bumps from tag):"
        echo ""
        echo "   just release::bump-workbench <version>"
        echo ""
        echo "3. COMMIT AND PUSH your RELEASE_NOTES.md and version bump changes"
        echo ""
        echo "4. CREATE RELEASE TAGS:"
        echo ""
        echo "   just release::tag-mcp-server <version>"
        echo "   just release::tag-workbench <version>"
        echo ""
        echo "NOTE: The MCP server version is determined by the git tag, so no bump needed."
        echo "NOTE: Release workflows extract notes from each component's RELEASE_NOTES.md."
    else
        echo "✗ SOME TESTS FAILED - Cannot proceed with release"
        echo ""
        echo "============================================================"
        echo "  FAILED TESTS"
        echo "============================================================"
        echo ""
        for i in "${!FAILED_NAMES[@]}"; do
            echo "  ✗ ${FAILED_NAMES[$i]}"
        done
        echo ""
        echo "============================================================"
        echo "  TO RECREATE FAILURES"
        echo "============================================================"
        echo ""
        echo "Run these commands to reproduce the failing tests:"
        echo ""
        for i in "${!FAILED_COMMANDS[@]}"; do
            echo "  ${FAILED_COMMANDS[$i]}"
        done
        echo ""
        echo "Please fix the failing tests before creating a release."
        exit 1
    fi

# Run headless integration tests for release (isolated, starts/stops FreeCAD)
integration-headless-release:
    #!/usr/bin/env bash
    set -euo pipefail

    # Source shared bridge helper functions
    . "{{project_root}}/scripts/bridge-helpers.sh"

    # Track whether we started FreeCAD (so cleanup knows to stop it)
    STARTED_FREECAD=false

    # Cleanup function
    cleanup() {
        if [ "$STARTED_FREECAD" = true ]; then
            echo ""
            echo "Stopping FreeCAD headless..."
            graceful_kill_bridge_ports
        fi
    }

    trap cleanup EXIT
    trap 'cleanup; exit 130' INT
    trap 'cleanup; exit 143' TERM

    echo "Headless Integration Test (Release Mode)"
    echo "----------------------------------------"
    echo ""

    # Check for existing FreeCAD
    if is_bridge_running; then
        echo "ERROR: A FreeCAD Robust MCP Bridge is already running on port 9875."
        echo ""
        echo "For release testing, we need to start FreeCAD fresh."
        echo "Please stop the existing FreeCAD instance and try again."
        echo ""
        echo "You can run: just testing::kill-bridge"
        exit 1
    fi

    # Install latest workbench code to FreeCAD's Mod directory
    # This ensures tests run against the current source code, not stale installed code
    echo "Installing latest workbench code..."
    just install::mcp-bridge-workbench
    echo ""

    # Start FreeCAD headless
    STARTED_FREECAD=true
    echo "Starting FreeCAD headless..."

    FREECAD_LOG="{{project_root}}/freecad-headless-release.log"
    just freecad::run-headless 2>"$FREECAD_LOG" &

    # Wait for bridge to be ready
    echo "Waiting for FreeCAD Robust MCP Bridge to start..."
    MAX_RETRIES=60
    RETRY_COUNT=0
    while ! is_bridge_running; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "ERROR: FreeCAD Robust MCP Bridge did not start within timeout"
            if [ -f "$FREECAD_LOG" ]; then
                echo "--- Last 20 lines of log ---"
                tail -20 "$FREECAD_LOG"
            fi
            exit 1
        fi
        if [ $((RETRY_COUNT % 10)) -eq 0 ]; then
            echo "  Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
        fi
        sleep 1
    done

    echo "FreeCAD Robust MCP Bridge is ready! (headless mode)"
    echo ""

    # Run integration tests
    TEST_EXIT_CODE=0
    uv run pytest "{{project_root}}/tests/integration" -v || TEST_EXIT_CODE=$?

    # Cleanup handled by trap
    rm -f "$FREECAD_LOG" 2>/dev/null || true
    exit $TEST_EXIT_CODE

# Run GUI integration tests for release (isolated, starts/stops FreeCAD)
integration-gui-release:
    #!/usr/bin/env bash
    set -euo pipefail

    # Source shared bridge helper functions
    . "{{project_root}}/scripts/bridge-helpers.sh"

    # Track whether we started FreeCAD (so cleanup knows to stop it)
    STARTED_FREECAD=false

    # Cleanup function
    cleanup() {
        if [ "$STARTED_FREECAD" = true ]; then
            echo ""
            echo "Stopping FreeCAD GUI..."
            graceful_kill_bridge_ports

            # On macOS, also try to quit FreeCAD gracefully
            if [[ "$OSTYPE" == "darwin"* ]]; then
                osascript -e 'tell application "FreeCAD" to quit' 2>/dev/null || true
            fi
        fi
    }

    trap cleanup EXIT
    trap 'cleanup; exit 130' INT
    trap 'cleanup; exit 143' TERM

    echo "GUI Integration Test (Release Mode)"
    echo "------------------------------------"
    echo ""

    # Check for existing FreeCAD
    if is_bridge_running; then
        echo "ERROR: A FreeCAD Robust MCP Bridge is already running on port 9875."
        echo ""
        echo "For release testing, we need to start FreeCAD fresh."
        echo "Please stop the existing FreeCAD instance and try again."
        echo ""
        echo "You can run: just testing::kill-bridge"
        exit 1
    fi

    # Install latest workbench code to FreeCAD's Mod directory
    # This ensures tests run against the current source code, not stale installed code
    echo "Installing latest workbench code..."
    just install::mcp-bridge-workbench
    echo ""

    # Start FreeCAD GUI
    STARTED_FREECAD=true
    echo "Starting FreeCAD GUI..."

    FREECAD_LOG="{{project_root}}/freecad-gui-release.log"

    # Start FreeCAD GUI (this returns immediately on macOS)
    just freecad::run-gui 2>"$FREECAD_LOG" || true

    # Wait for bridge to be ready (GUI takes longer to start)
    echo "Waiting for FreeCAD Robust MCP Bridge to start (GUI mode, may take 30-60s)..."
    MAX_RETRIES=90
    RETRY_COUNT=0
    while ! is_bridge_running; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "ERROR: FreeCAD Robust MCP Bridge did not start within timeout"
            if [ -f "$FREECAD_LOG" ]; then
                echo "--- Last 20 lines of log ---"
                tail -20 "$FREECAD_LOG"
            fi
            exit 1
        fi
        if [ $((RETRY_COUNT % 10)) -eq 0 ]; then
            echo "  Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
        fi
        sleep 1
    done

    echo "FreeCAD Robust MCP Bridge is ready! (GUI mode)"
    echo ""

    # Run integration tests
    TEST_EXIT_CODE=0
    uv run pytest "{{project_root}}/tests/integration" -v || TEST_EXIT_CODE=$?

    # Cleanup handled by trap
    rm -f "$FREECAD_LOG" 2>/dev/null || true
    exit $TEST_EXIT_CODE

# =============================================================================
# Bridge Management
# =============================================================================

# Kill any zombie FreeCAD Robust MCP Bridge processes on the default ports
kill-bridge:
    #!/usr/bin/env bash
    set -euo pipefail

    # Source shared bridge helper functions
    . "{{project_root}}/scripts/bridge-helpers.sh"

    echo "Killing any processes on MCP bridge ports (9875, 9876)..."
    force_kill_bridge_ports
    echo "Done."
