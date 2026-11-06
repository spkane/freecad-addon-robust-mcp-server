# FreeCAD Robust MCP Suite - Quick Start

This guide gets you up and running quickly. For comprehensive documentation, visit our **[Full Documentation](https://spkane.github.io/freecad-addon-robust-mcp-server/)**.

## Overview

The FreeCAD Robust MCP Suite consists of two components:

| Component              | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| **Robust MCP Bridge**  | FreeCAD workbench that exposes FreeCAD via XML-RPC |
| **Robust MCP Server**  | MCP server that connects AI assistants to FreeCAD  |

## Quick Start

### 1. Install the server and workbench

The workbench is not yet in the public FreeCAD Addon Manager catalog. Follow
our [stable Quick Start](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/getting-started/quickstart/)
to install both the MCP server and the compatible workbench archive. Use
version 0.7.0 or later of both components for pairing. The guide covers
versioned FreeCAD profiles, Windows, and source checkout installation.

### 2. Pair and start the bridge

Run `freecad-mcp --pair-bridge` as the user who runs FreeCAD; if already paired,
retain the existing credential. Open FreeCAD, select **Robust MCP Bridge**, and
click **Start MCP Bridge** unless it is already running.

### 3. Configure your AI assistant

Follow the [assistant configuration examples](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/getting-started/quickstart/#4-connect-your-assistant)
for Claude Desktop/CLI, Codex Desktop/CLI, and other MCP clients.

### 4. Verify the installation

```bash
freecad-mcp --version
freecad-mcp --mode xmlrpc --check
```

For development from a source checkout, prefix these commands and the pairing
command with `uv run` from that checkout.

### 5. Start Using It

Your AI assistant can now:

- Create and modify 3D models
- Work with sketches and constraints
- Export to STEP, STL, 3MF formats
- Execute Python code in FreeCAD
- And much more...

## Connection Modes

| Mode     | Description                      | Best For                    |
| -------- | -------------------------------- | --------------------------- |
| `xmlrpc` | XML-RPC connection (port 9875)   | Most users (recommended)    |
| `socket` | JSON-RPC socket (port 9876)      | Alternative protocol        |

## Verify Installation

```bash
# Check MCP server installation
freecad-mcp --version

# Check connection status (with FreeCAD running)
freecad-mcp --mode xmlrpc --check
```

## Full Documentation

For detailed guides, API reference, and advanced configuration:

**[https://spkane.github.io/freecad-addon-robust-mcp-server/](https://spkane.github.io/freecad-addon-robust-mcp-server/)**

### Quick Links

- [Installation Guide](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/getting-started/installation/)
- [Configuration Options](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/getting-started/configuration/)
- [MCP Tools Reference](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/guide/tools/)
- [Troubleshooting](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/USER_GUIDE/#troubleshooting)
- [API Reference](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/api/server/)

## Need Help?

- [GitHub Issues](https://github.com/spkane/freecad-addon-robust-mcp-server/issues)
- [Full Documentation](https://spkane.github.io/freecad-addon-robust-mcp-server/)
