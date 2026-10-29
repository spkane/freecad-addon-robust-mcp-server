# FreeCAD Robust MCP Suite

## Overview

The FreeCAD Robust MCP Suite enables AI assistants like Claude Code and Cursor
to interact with FreeCAD through the Model Context Protocol (MCP).

## Components

### Robust MCP Bridge (Workbench)

A FreeCAD workbench that exposes FreeCAD's functionality via XML-RPC and
JSON-RPC protocols. The workbench is not yet in the public FreeCAD Addon
Manager catalog; see the [installation guide](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/getting-started/installation/).

**Features:**

- Auto-start on FreeCAD launch (configurable)
- Status bar indicator showing connection state
- Toolbar buttons to start/stop the bridge
- Works in both GUI and headless modes

### Robust MCP Server

A standalone MCP server that connects AI assistants to the bridge.
Install matching server and workbench builds from the same source checkout;
see the [installation guide](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/getting-started/installation/).

**Capabilities:**

- 150+ CAD tools for creating and modifying geometry
- PartDesign and Sketcher support
- Export to STEP, STL, 3MF, OBJ, IGES formats
- Screenshot capture and view control (GUI mode)
- Python code execution in FreeCAD context

## Quick Start

1. Install matching server and workbench builds from the same source checkout
2. Pair the server and bridge with `uv run freecad-mcp --pair-bridge`
3. Start FreeCAD and select the MCP Bridge workbench
4. Click **Start MCP Bridge** unless auto-start is enabled
5. Configure your AI assistant to use the MCP server

## Documentation

For full documentation, visit:
<https://spkane.github.io/freecad-addon-robust-mcp-server/>

## License

- Code: Apache License 2.0; existing MIT-licensed contributions retain their terms
- Icons: CC-BY-NC-SA-4.0
