# MCP Server commands
# Usage: just mcp::run, just mcp::run-debug, etc.
#
# These commands run the MCP server that connects to FreeCAD.
# Note: FreeCAD must be running with the MCP bridge for the server to connect.
# Start FreeCAD with: just freecad::run-gui or just freecad::run-headless

# Run the MCP server (stdio mode - default for Claude Code integration)
run:
    uv run freecad-mcp

# Run the MCP server with debug logging
run-debug:
    FREECAD_MCP_LOG_LEVEL=DEBUG uv run freecad-mcp

# Run in HTTP mode for remote access (useful for testing or remote clients)
run-http port="8000":
    FREECAD_MCP_TRANSPORT=http FREECAD_MCP_PORT={{port}} uv run freecad-mcp
