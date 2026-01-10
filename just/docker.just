# Docker build and run commands
# Usage: just docker::build, just docker::build-all, etc.

# Default Docker image name (matches Docker Hub and PyPI package name)
image_name := "freecad-robust-mcp"
registry := "spkane"
gui_test_image := "freecad-gui-test"

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()

# Build Docker image for local architecture only
build:
    docker build -t {{image_name}} {{project_root}}

# Build Docker image with specific tag
build-tag tag:
    docker build --load -t {{image_name}}:{{tag}} {{project_root}}

# Build multi-architecture image (amd64 and arm64)
# Note: Multi-arch builds cannot be loaded locally; use build-load for local testing
build-multi: setup-buildx
    docker buildx build --platform linux/amd64,linux/arm64 -t {{image_name}} {{project_root}}

# Build and push multi-architecture image to registry
build-push tag="latest": setup-buildx
    docker buildx build --platform linux/amd64,linux/arm64 \
        -t {{registry}}/{{image_name}}:{{tag}} \
        --push {{project_root}}

# Build and load image for current architecture using buildx
build-load:
    #!/usr/bin/env bash
    set -euo pipefail
    # Detect current architecture
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  PLATFORM="linux/amd64" ;;
        aarch64|arm64) PLATFORM="linux/arm64" ;;
        *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    echo "Building for detected architecture: $PLATFORM"
    docker buildx build --platform "$PLATFORM" \
        -t {{image_name}} \
        --load {{project_root}}

# Run the Docker container (connects to FreeCAD on host)
# Note: Ctrl+C exits cleanly (exit code ignored)
run:
    -docker run --rm -i \
        --add-host=host.docker.internal:host-gateway \
        -e FREECAD_MODE=xmlrpc \
        -e FREECAD_SOCKET_HOST=host.docker.internal \
        {{image_name}}

# Run with custom environment variables
# Note: Ctrl+C exits cleanly (exit code ignored)
run-env *args:
    -docker run --rm -i \
        --add-host=host.docker.internal:host-gateway \
        {{args}} \
        {{image_name}}

# Run container interactively with shell
# Note: Exit from shell exits cleanly (exit code ignored)
shell:
    -docker run --rm -it \
        --add-host=host.docker.internal:host-gateway \
        -e FREECAD_MODE=xmlrpc \
        -e FREECAD_SOCKET_HOST=host.docker.internal \
        --entrypoint /bin/sh \
        {{image_name}}

# Show image size and layers
inspect:
    docker images {{image_name}}
    @echo ""
    docker history {{image_name}}

# Remove local Docker image
clean:
    docker rmi {{image_name}} 2>/dev/null || true
    docker rmi {{registry}}/{{image_name}} 2>/dev/null || true

# Remove Docker images and build cache
clean-all:
    docker rmi {{image_name}} 2>/dev/null || true
    docker rmi {{registry}}/{{image_name}} 2>/dev/null || true
    docker builder prune -f
    @echo "Docker images and build cache cleaned."

# Scan Docker image for vulnerabilities (warn on all severities)
scan:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Scanning {{image_name}} for vulnerabilities..."
    echo ""
    trivy image --severity HIGH,CRITICAL {{image_name}}
    echo ""
    echo "Scanning for MEDIUM/LOW (informational)..."
    trivy image --severity MEDIUM,LOW {{image_name}} || true

# Scan Docker image with strict settings (fail on HIGH or CRITICAL)
scan-strict:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Scanning {{image_name}} for HIGH/CRITICAL vulnerabilities..."
    echo "(Build will fail if any HIGH or CRITICAL CVEs are found)"
    echo ""
    trivy image --severity HIGH,CRITICAL --exit-code 1 {{image_name}}
    echo ""
    echo "✓ No HIGH or CRITICAL vulnerabilities found!"
    echo ""
    echo "Scanning for MEDIUM/LOW (informational only)..."
    trivy image --severity MEDIUM,LOW --exit-code 0 {{image_name}} || true

# Scan Docker image and output SARIF report
scan-sarif output="trivy-results.sarif":
    trivy image --format sarif --output {{project_root}}/{{output}} {{image_name}}
    @echo "SARIF report written to {{project_root}}/{{output}}"

# Create and configure buildx builder for multi-arch builds
setup-buildx:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! docker buildx inspect freecad-builder > /dev/null 2>&1; then
        echo "Creating buildx builder 'freecad-builder'..."
        docker buildx create --name freecad-builder --use --bootstrap
    else
        echo "Builder 'freecad-builder' already exists, using it..."
        docker buildx use freecad-builder
    fi
    docker buildx inspect --bootstrap

# Test Docker container integration with FreeCAD
# This builds the image, starts FreeCAD with the bridge, runs the container,
# and verifies communication is working correctly.
test:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "=========================================="
    echo "Docker Integration Test"
    echo "=========================================="
    echo ""

    # Function to check if XML-RPC server is ready using a simple POST request
    check_xmlrpc() {
        # Send a minimal XML-RPC system.listMethods call
        curl -s --max-time 2 -X POST \
            -H "Content-Type: text/xml" \
            -d '<?xml version="1.0"?><methodCall><methodName>system.listMethods</methodName></methodCall>' \
            http://localhost:9875 > /dev/null 2>&1
    }

    # Build the Docker image
    echo "Step 1: Building Docker image..."
    docker build -t {{image_name}}:test {{project_root}}
    echo "✓ Docker image built successfully"
    echo ""

    # Check if FreeCAD bridge is already running
    echo "Step 2: Checking for FreeCAD MCP bridge..."
    if check_xmlrpc; then
        echo "✓ FreeCAD MCP bridge is already running on port 9875"
        STARTED_FREECAD=false
    else
        echo "FreeCAD MCP bridge not detected. Starting FreeCAD headless..."
        echo "  (This may take 30-60 seconds for FreeCAD to initialize...)"

        # Start FreeCAD headless in background, capturing output
        FREECAD_LOG=$(mktemp)
        just freecad::run-headless > "$FREECAD_LOG" 2>&1 &
        FREECAD_PID=$!

        # Wait for bridge to be ready (longer timeout for FreeCAD startup)
        MAX_RETRIES=60
        RETRY_COUNT=0
        while ! check_xmlrpc; do
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
                echo "✗ ERROR: FreeCAD MCP bridge did not start within ${MAX_RETRIES}s"
                echo ""
                echo "FreeCAD log output:"
                cat "$FREECAD_LOG" | tail -30
                rm -f "$FREECAD_LOG"
                kill $FREECAD_PID 2>/dev/null || true
                exit 1
            fi
            # Show progress less frequently to reduce noise
            if [ $((RETRY_COUNT % 5)) -eq 0 ]; then
                echo "  Waiting for bridge... ($RETRY_COUNT/$MAX_RETRIES)"
            fi
            sleep 1
        done
        rm -f "$FREECAD_LOG"
        echo "✓ FreeCAD MCP bridge started (took ${RETRY_COUNT}s)"
        STARTED_FREECAD=true
    fi
    echo ""

    # Run the container and test communication
    echo "Step 3: Running container and testing MCP communication..."
    echo "  Running Robust MCP Server in container..."

    # Send MCP initialize request via JSON-RPC over stdio
    # Using temp file for input so stdin closes after message
    # Note: Container may exit non-zero when stdin closes (ClosedResourceError), which is expected
    MCP_INPUT=$(mktemp)
    # Ensure temp file is cleaned up on any exit (normal, error, or signal)
    trap 'rm -f "$MCP_INPUT"' EXIT
    echo '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' > "$MCP_INPUT"

    # Capture output; ignore exit code since stdin close causes expected error
    CONTAINER_OUTPUT=$(timeout 30 docker run --rm -i \
        --add-host=host.docker.internal:host-gateway \
        -e FREECAD_MODE=xmlrpc \
        -e FREECAD_SOCKET_HOST=host.docker.internal \
        {{image_name}}:test 2>&1 < "$MCP_INPUT" || true)
    # Temp file will be cleaned up by trap on EXIT

    echo ""
    echo "Step 4: Verifying response..."

    # Track test results
    TEST_PASSED=true

    # Check if we got a valid MCP initialize response
    if echo "$CONTAINER_OUTPUT" | grep -q '"result".*"protocolVersion"'; then
        echo "✓ Container responded with valid MCP initialize response"
    else
        echo "✗ Container failed to respond with valid MCP response"
        TEST_PASSED=false
    fi

    # Check for server info in response
    if echo "$CONTAINER_OUTPUT" | grep -q '"serverInfo".*"freecad-mcp"'; then
        echo "✓ Server identified as freecad-mcp"
    else
        echo "⚠ Warning: Could not confirm server identity"
    fi

    # Check for FreeCAD bridge connection in logs
    if echo "$CONTAINER_OUTPUT" | grep -q 'FreeCAD bridge connected\|FreeCAD.*GUI'; then
        echo "✓ FreeCAD bridge connection logged"
    else
        echo "⚠ Warning: No FreeCAD bridge connection in logs"
    fi

    echo ""
    echo "=========================================="
    echo "Raw container output (last 20 lines):"
    echo "=========================================="
    echo "$CONTAINER_OUTPUT" | tail -20
    echo ""

    # Cleanup
    if [ "$STARTED_FREECAD" = true ]; then
        echo "Step 5: Cleaning up..."
        kill $FREECAD_PID 2>/dev/null || true
        echo "✓ Stopped FreeCAD headless server"
    fi

    echo ""
    echo "=========================================="
    if [ "$TEST_PASSED" = true ]; then
        echo "✓ PASSED: Docker integration test succeeded!"
        echo "  - Container built and ran successfully"
        echo "  - Robust MCP Server responded to initialize request"
    else
        echo "✗ FAILED: Docker integration test had errors"
        echo "  - Review the output above for details"
    fi
    echo "=========================================="

    # Exit with appropriate code
    if [ "$TEST_PASSED" = false ]; then
        exit 1
    fi

# ============================================================================
# GUI Test Container (for CI debugging)
# ============================================================================

# Build the GUI test container (replicates GitHub Actions CI environment)
# Supports both x86_64 and aarch64 architectures (downloads correct AppImage)
build-gui-test:
    docker build -f {{project_root}}/tests/ci-test/Dockerfile.gui-test \
        -t {{gui_test_image}} \
        {{project_root}}

# Run GUI test container interactively for debugging
gui-test-shell:
    docker run --rm -it \
        -v {{project_root}}:/workspace \
        {{gui_test_image}} \
        /bin/bash

# Run the automated GUI tests in the container
gui-test-run:
    docker run --rm -i \
        -v {{project_root}}:/workspace \
        {{gui_test_image}} \
        /usr/local/bin/run-gui-test.sh

# Run GUI test with custom command
gui-test-cmd *args:
    docker run --rm -it \
        -v {{project_root}}:/workspace \
        {{gui_test_image}} \
        {{args}}

# Quick rebuild and test cycle for GUI debugging
gui-test: build-gui-test gui-test-run
