# Start MCP Bridge - FreeCAD Macro

**Version:** 1.0.0
**FreeCAD Version:** 0.21 or later
**License:** MIT

## Overview

This FreeCAD macro starts the MCP (Model Context Protocol) bridge server, enabling integration between AI assistants (Claude, GPT, and other MCP-compatible tools) and FreeCAD. Once running, AI assistants can control FreeCAD, create and modify 3D models, execute Python code, and more.

## Quick Start

### Installation

```bash
# From the freecad-mcp project directory
just install-bridge-macro
```

### Usage

1. Start FreeCAD
1. Go to **Macro -> Macros...**
1. Select **StartMCPBridge**
1. Click **Execute**

You should see in the FreeCAD console:

```text
MCP Bridge started!
  - XML-RPC: localhost:9875
  - Socket: localhost:9876

You can now use AI assistants with FreeCAD.
```

### Connecting Your MCP Client

After starting the bridge, configure your MCP client (e.g., Claude Code) with:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/freecad-mcp", "freecad-mcp"],
      "env": {
        "FREECAD_MODE": "xmlrpc"
      }
    }
  }
}
```

## Connection Modes

The bridge starts two servers:

| Port | Protocol | Description                           |
| ---- | -------- | ------------------------------------- |
| 9875 | XML-RPC  | Primary connection mode (recommended) |
| 9876 | JSON-RPC | Alternative socket-based connection   |

Configure your MCP client's `FREECAD_MODE` environment variable:

- `xmlrpc` (default) - Uses port 9875
- `socket` - Uses port 9876

## Alternative: Automatic Startup

Instead of running the macro manually each time, you can:

### Option 1: Use `just run-gui`

```bash
just run-gui
```

This starts FreeCAD with the bridge auto-started.

### Option 2: Use `just run-headless`

```bash
just run-headless
```

This starts FreeCAD in headless/console mode with the bridge running. Useful for automation and CI/CD.

## Troubleshooting

### Error: "MCP Bridge macro not properly installed"

The macro wasn't installed correctly. Run:

```bash
just install-bridge-macro
```

### Error: "Failed to import MCP Bridge module"

The freecad-mcp project path is incorrect or the module isn't installed. Ensure:

1. You installed using `just install-bridge-macro` from the project directory
1. The project's Python dependencies are installed (`uv sync`)

### Bridge won't start

Check the FreeCAD console for error messages. Common issues:

1. **Port already in use** - Another instance is running, or another application is using ports 9875/9876
1. **Python path issues** - The project src directory isn't accessible

### MCP client can't connect

1. Ensure the bridge is running (check FreeCAD console)
1. Verify your MCP client configuration
1. Restart your MCP client after configuration changes

## Uninstallation

```bash
just uninstall-bridge-macro
```

## Technical Details

The macro:

1. Adds the freecad-mcp project source to Python's path
1. Imports and instantiates the `FreecadMCPPlugin`
1. Starts both XML-RPC and JSON-RPC servers
1. Registers handlers for executing Python code, managing documents, creating objects, etc.

The bridge runs in FreeCAD's main thread using Qt timers for non-blocking operation.

## License

MIT License - Free to use, modify, and distribute.
