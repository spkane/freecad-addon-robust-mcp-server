# FreeCAD Robust MCP Suite - Quick Start

This guide gets you up and running quickly. For comprehensive documentation, visit our **[Full Documentation](https://spkane.github.io/freecad-addon-robust-mcp-server/)**.

## Overview

The FreeCAD Robust MCP Suite consists of two components:

| Component              | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| **Robust MCP Bridge**  | FreeCAD workbench that exposes FreeCAD via XML-RPC |
| **Robust MCP Server**  | MCP server that connects AI assistants to FreeCAD  |

## Quick Start

### 1. Install the MCP Bridge in FreeCAD

The workbench is not yet in the public FreeCAD Addon Manager catalog. Install
the pairing-capable server and workbench from the same source checkout:

```bash
# Clone the repository
git clone https://github.com/spkane/freecad-addon-robust-mcp-server.git
cd freecad-addon-robust-mcp-server

# Install the workbench
just install::mcp-bridge-workbench
```

The installer creates the package and manifest under the selected FreeCAD
profile's `Mod/RobustMCPBridge/` directory. Do not copy the repository itself
into `Mod`. See the [installation guide](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/getting-started/installation/)
for versioned profiles, Windows requirements, and compatible release archives.

### 2. Start the MCP Bridge

1. Run `uv run freecad-mcp --pair-bridge` from the checkout as the same user
   who runs FreeCAD.
2. Open FreeCAD and select the **Robust MCP Bridge** workbench.
3. Click **Start MCP Bridge** in the toolbar, unless auto-start is enabled.

The bridge listens on:

- **XML-RPC**: `http://localhost:9875`
- **Socket**: `localhost:9876`

### 3. Install the MCP Server

Use `uv run freecad-mcp` from the same source checkout. Published 0.6.x server
and workbench builds predate pairing and are not compatible with this setup.

### 4. Configure Your AI Assistant

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "freecad": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/freecad-addon-robust-mcp-server", "freecad-mcp"]
    }
  }
}
```

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
uv run freecad-mcp --version

# Check connection status (with FreeCAD running)
uv run freecad-mcp --mode xmlrpc --check
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
