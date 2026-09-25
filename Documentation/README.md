# FreeCAD Robust MCP Suite - Quick Start

This guide gets you up and running quickly. For comprehensive documentation, visit our **[Full Documentation](https://spkane.github.io/freecad-robust-mcp-and-more/)**.

## Overview

The FreeCAD Robust MCP Suite consists of two components:

| Component              | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| **Robust MCP Bridge**  | FreeCAD workbench that exposes FreeCAD via XML-RPC |
| **Robust MCP Server**  | MCP server that connects AI assistants to FreeCAD  |

## Quick Start

### 1. Install the MCP Bridge in FreeCAD

> **Not in the Addon Manager.** The workbench is not in the FreeCAD Addon
> Manager catalog yet. Searching for "Robust MCP Bridge" there returns
> nothing. Use one of the methods below.

#### Option A: With `just` (recommended)

From a clone of this repository:

```bash
just install::mcp-bridge-workbench
```

This installs the workbench to `Mod/RobustMCPBridge/` and generates its
`package.xml`. Restart FreeCAD, then pick **Robust MCP Bridge** from the
workbench dropdown.

#### Option B: Manual installation

Download the latest release archive from
[GitHub Releases](https://github.com/spkane/freecad-robust-mcp-and-more/releases)
and extract the `RobustMCPBridge` folder into your FreeCAD `Mod` directory:

- **Linux:** `~/.local/share/FreeCAD/Mod/RobustMCPBridge/`
- **macOS:** `~/Library/Application Support/FreeCAD/Mod/RobustMCPBridge/`
- **Windows:** `%APPDATA%\FreeCAD\v1-1\Mod\RobustMCPBridge\`

Do **not** extract to `Mod/freecad/RobustMCPBridge/` — that is the wrong
namespace layout and FreeCAD will not load it.

### 2. Start the MCP Bridge

1. Open FreeCAD
2. The bridge starts automatically (if auto-start is enabled), or
3. Click the **Start MCP Bridge** button in the toolbar

The bridge listens on:

- **XML-RPC**: `http://localhost:9875`
- **Socket**: `localhost:9876`

### 3. Install the MCP Server

```bash
# Install via uv (recommended)
uv tool install freecad-robust-mcp

# Or via pip
pip install freecad-robust-mcp
```

### 4. Configure Your AI Assistant

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "freecad": {
      "command": "freecad-mcp",
      "args": ["--mode", "xmlrpc"]
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
freecad-mcp --version

# Check connection status (with FreeCAD running)
freecad-mcp --mode xmlrpc --test-connection
```

## Full Documentation

For detailed guides, API reference, and advanced configuration:

**[https://spkane.github.io/freecad-robust-mcp-and-more/](https://spkane.github.io/freecad-robust-mcp-and-more/)**

### Quick Links

- [Installation Guide](https://spkane.github.io/freecad-robust-mcp-and-more/getting-started/installation/)
- [Configuration Options](https://spkane.github.io/freecad-robust-mcp-and-more/getting-started/configuration/)
- [MCP Tools Reference](https://spkane.github.io/freecad-robust-mcp-and-more/guide/tools/)
- [Troubleshooting](https://spkane.github.io/freecad-robust-mcp-and-more/guide/troubleshooting/)
- [API Reference](https://spkane.github.io/freecad-robust-mcp-and-more/reference/api/)

## Need Help?

- [GitHub Issues](https://github.com/spkane/freecad-robust-mcp-and-more/issues)
- [Full Documentation](https://spkane.github.io/freecad-robust-mcp-and-more/)
