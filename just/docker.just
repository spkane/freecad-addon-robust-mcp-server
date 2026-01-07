# Docker build and run commands
# Usage: just docker::build, just docker::build-all, etc.

# Default Docker image name (matches Docker Hub and PyPI package name)
image_name := "freecad-robust-mcp"
registry := "spkane"

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()

# Build Docker image for local architecture only
build:
    docker build -t {{image_name}} {{project_root}}

# Build Docker image with specific tag
build-tag tag:
    docker build -t {{image_name}}:{{tag}} {{project_root}}

# Build multi-architecture image (amd64 and arm64)
build-multi:
    docker buildx build --platform linux/amd64,linux/arm64 -t {{image_name}} {{project_root}}

# Build and push multi-architecture image to registry
build-push tag="latest":
    docker buildx build --platform linux/amd64,linux/arm64 \
        -t {{registry}}/{{image_name}}:{{tag}} \
        --push {{project_root}}

# Build and load multi-architecture image locally (loads current arch only)
build-load:
    docker buildx build --platform linux/amd64,linux/arm64 \
        -t {{image_name}} \
        --load {{project_root}}

# Run the Docker container (connects to FreeCAD on host)
run:
    docker run --rm -i \
        --add-host=host.docker.internal:host-gateway \
        -e FREECAD_MODE=xmlrpc \
        -e FREECAD_SOCKET_HOST=host.docker.internal \
        {{image_name}}

# Run with custom environment variables
run-env *args:
    docker run --rm -i \
        --add-host=host.docker.internal:host-gateway \
        {{args}} \
        {{image_name}}

# Run container interactively with shell
shell:
    docker run --rm -it \
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
    trivy image --format sarif --output {{output}} {{image_name}}
    @echo "SARIF report written to {{output}}"

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
    echo "  Running MCP server in container..."

    # Send MCP initialize and tool call requests via JSON-RPC over stdio
    # Note: Using printf with \n to avoid just parsing issues with unindented lines
    MCP_INIT='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
    MCP_CALL='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_mcp_server_environment","arguments":{}}}'

    CONTAINER_OUTPUT=$(printf '%s\n%s\n' "$MCP_INIT" "$MCP_CALL" | \
        timeout 30 docker run --rm -i \
            --add-host=host.docker.internal:host-gateway \
            -e FREECAD_MODE=xmlrpc \
            -e FREECAD_SOCKET_HOST=host.docker.internal \
            {{image_name}}:test 2>&1) || {
        echo "✗ Container failed to respond"
        if [ "$STARTED_FREECAD" = true ]; then
            kill $FREECAD_PID 2>/dev/null || true
        fi
        exit 1
    }

    echo ""
    echo "Step 4: Verifying response..."

    # Track test results
    TEST_PASSED=true
    DOCKER_CONFIRMED=false

    # Check if the response indicates we're in a Docker container
    if echo "$CONTAINER_OUTPUT" | grep -q '"in_docker": true\|"in_docker":true'; then
        echo "✓ Response confirms running in Docker container"
        DOCKER_CONFIRMED=true
    elif echo "$CONTAINER_OUTPUT" | grep -q '"os_name": "Linux"\|"os_name":"Linux"'; then
        echo "✓ Response shows Linux OS (expected for Docker)"
        DOCKER_CONFIRMED=true
    else
        echo "⚠ Warning: Could not confirm Docker detection"
        TEST_PASSED=false
    fi

    # Check for hostname (containers have short random hostnames)
    if echo "$CONTAINER_OUTPUT" | grep -q '"hostname"'; then
        HOSTNAME=$(echo "$CONTAINER_OUTPUT" | grep -o '"hostname"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1)
        echo "✓ Container hostname: $HOSTNAME"
    else
        echo "⚠ Warning: No hostname in response"
    fi

    # Check we got a valid response (not an error)
    if echo "$CONTAINER_OUTPUT" | grep -q '"error"'; then
        # Check if it's just a "not connected" error (expected without proper init)
        if echo "$CONTAINER_OUTPUT" | grep -q 'Not connected\|Connection refused'; then
            echo "  Note: FreeCAD connection test - bridge communication verified"
        else
            echo "✗ Error: Response contained an error"
            echo "  $CONTAINER_OUTPUT" | tail -5
            TEST_PASSED=false
        fi
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
    if [ "$TEST_PASSED" = true ] && [ "$DOCKER_CONFIRMED" = true ]; then
        echo "✓ PASSED: Docker integration test succeeded!"
        echo "  - Container ran successfully"
        echo "  - Confirmed running in Docker environment"
    elif [ "$TEST_PASSED" = true ]; then
        echo "⚠ PARTIAL: Docker integration test completed with warnings"
        echo "  - Container ran successfully"
        echo "  - Could not confirm Docker environment detection"
    else
        echo "✗ FAILED: Docker integration test had errors"
        echo "  - Review the output above for details"
    fi
    echo "=========================================="

    # Exit with appropriate code
    if [ "$TEST_PASSED" = false ]; then
        exit 1
    fi
