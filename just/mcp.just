# Robust MCP Server commands
# Usage: just mcp::run, just mcp::run-debug, etc.
#
# These commands run the Robust MCP Server that connects to FreeCAD.
# Note: FreeCAD must be running with the MCP bridge for the server to connect.
# Start FreeCAD with: just freecad::run-gui or just freecad::run-headless

# Check if FreeCAD bridge is available (test connection without starting server)
check:
    uv run freecad-mcp --check

# Run the Robust MCP Server (stdio mode - default for Claude Code integration)
run:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Checking FreeCAD bridge connection..."
    if uv run freecad-mcp --check; then
        echo ""
        echo "Starting MCP server..."
        uv run freecad-mcp
    else
        echo ""
        echo "Cannot start MCP server - FreeCAD bridge is not available."
        echo "Start FreeCAD with: just freecad::run-gui"
        exit 1
    fi

# Run the Robust MCP Server with debug logging
run-debug:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Checking FreeCAD bridge connection..."
    if uv run freecad-mcp --check; then
        echo ""
        echo "Starting MCP server with debug logging..."
        FREECAD_LOG_LEVEL=DEBUG uv run freecad-mcp
    else
        echo ""
        echo "Cannot start MCP server - FreeCAD bridge is not available."
        echo "Start FreeCAD with: just freecad::run-gui"
        exit 1
    fi

# Run in HTTP mode for remote access (useful for testing or remote clients)
run-http port="8000":
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Checking FreeCAD bridge connection..."
    if uv run freecad-mcp --check; then
        echo ""
        echo "Starting MCP server in HTTP mode on port {{port}}..."
        FREECAD_TRANSPORT=http FREECAD_HTTP_PORT={{port}} uv run freecad-mcp
    else
        echo ""
        echo "Cannot start MCP server - FreeCAD bridge is not available."
        echo "Start FreeCAD with: just freecad::run-gui"
        exit 1
    fi
